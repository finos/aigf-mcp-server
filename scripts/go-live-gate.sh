#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Resolved through the one shim every gate uses, so this script cannot audit a
# different environment than the hooks and ci-local.sh do (#89).
if ! PYTHON_BIN="$("$ROOT_DIR/scripts/project-python.sh" --print-interpreter)"; then
  exit 1
fi
REQUIRE_CLEAN="${REQUIRE_CLEAN:-1}"

cd "$ROOT_DIR"

step() {
  printf "\n==> %s\n" "$1"
}

fail() {
  printf "\n[FAIL] %s\n" "$1" >&2
  exit 1
}

pass() {
  printf "[PASS] %s\n" "$1"
}

step "Gate 1: Ensure development-only folders are not tracked"
# DEV_ONLY_PATTERN is defined once, in the file Gate 9 reads too (#130). Gate 1
# asks the question of the index; Gate 9 asks it of the refs on the remote.
# shellcheck source=scripts/dev-only-paths.sh
source "$ROOT_DIR/scripts/dev-only-paths.sh"
if command -v rg >/dev/null 2>&1; then
  HAS_DEV_ONLY_TRACKED=$(git ls-files | rg "$DEV_ONLY_PATTERN" || true)
else
  HAS_DEV_ONLY_TRACKED=$(git ls-files | grep -E "$DEV_ONLY_PATTERN" || true)
fi

if [[ -n "$HAS_DEV_ONLY_TRACKED" ]]; then
  printf "%s\n" "$HAS_DEV_ONLY_TRACKED"
  fail "Development-only folders are tracked in git"
fi
pass "No development-only tracked folders detected"

step "Gate 2: Ensure working tree is clean"
if [[ "$REQUIRE_CLEAN" == "1" ]]; then
  if [[ -n "$(git status --porcelain)" ]]; then
    git status --short
    fail "Working tree is not clean (set REQUIRE_CLEAN=0 to bypass)"
  fi
  pass "Working tree is clean"
else
  echo "[WARN] REQUIRE_CLEAN=0, skipping clean-tree enforcement"
fi

step "Gate 3: Lint and typing checks"
"$PYTHON_BIN" -m ruff check src/ tests/
"$PYTHON_BIN" -m ruff format --check src/ tests/
"$PYTHON_BIN" -m mypy
pass "Ruff and MyPy checks passed"

step "Gate 4: Regression test suite"
# test_published_surface.py is the tool/prompt/resource contract. It is listed
# here because #143 deleted test_assembled_server_calls.py, whose
# test_server_tools_registration was the only thing in this gate that asserted
# anything about the published tool set -- and it only checked that 6 named
# tools were a *subset* of what is registered, so it could not see an added or
# renamed tool at all. The replacement asserts exact equality over the published set.
"$PYTHON_BIN" -m pytest -q \
    tests/unit/test_config_validation.py \
    tests/unit/test_published_surface.py \
    tests/unit/test_rate_limit_client_resolution.py \
    tests/unit/test_structured_output_models.py \
    tests/unit/test_tool_results.py \
    tests/integration/test_fastmcp_integration.py
pass "Core regression suite passed"

step "Gate 5: Live stdio MCP test"
FINOS_RUN_LIVE_MCP_TEST=1 "$PYTHON_BIN" -m pytest -q tests/integration/test_live_mcp_server.py
pass "Live stdio MCP test passed"

step "Gate 6: Live HTTP MCP test"
./scripts/test-http-transport.sh
pass "Live HTTP MCP test passed"

step "Gate 7: Live HTTP auth boundary test"
./scripts/test-auth-http-transport.sh
pass "Live HTTP auth boundary test passed"

step "Gate 8: Dependency vulnerability scan"
PIP_AUDIT_LOG="$(mktemp)"
PIP_AUDIT_MAX_RETRIES=3
PIP_AUDIT_ATTEMPT=1
while [[ "$PIP_AUDIT_ATTEMPT" -le "$PIP_AUDIT_MAX_RETRIES" ]]; do
  # Suppressions come from [tool.finos.pip-audit] in pyproject.toml, never inline.
  if PYTHON_BIN="$PYTHON_BIN" "$ROOT_DIR/scripts/pip-audit-scan.sh" \
    >"$PIP_AUDIT_LOG" 2>&1; then
    pass "pip-audit passed"
    rm -f "$PIP_AUDIT_LOG"
    break
  fi

  if rg -q "(ConnectionError|Connection aborted|Connection reset|Max retries exceeded|Failed to resolve|NameResolutionError)" "$PIP_AUDIT_LOG" 2>/dev/null || \
     grep -Eq "(ConnectionError|Connection aborted|Connection reset|Max retries exceeded|Failed to resolve|NameResolutionError)" "$PIP_AUDIT_LOG"; then
    if [[ "$PIP_AUDIT_ATTEMPT" -lt "$PIP_AUDIT_MAX_RETRIES" ]]; then
      echo "[WARN] pip-audit network failure on attempt $PIP_AUDIT_ATTEMPT/$PIP_AUDIT_MAX_RETRIES; retrying..."
      sleep 3
      PIP_AUDIT_ATTEMPT=$((PIP_AUDIT_ATTEMPT + 1))
      continue
    fi
  fi

  cat "$PIP_AUDIT_LOG"
  rm -f "$PIP_AUDIT_LOG"
  fail "pip-audit failed"
done

step "Gate 9: Refs published to the remote"
# Gate 1 reads git ls-files, which is HEAD. Tag v0.1.0 published a tree of
# eight development-only files while Gate 1 reported PASS (#130).
./scripts/scan-published-refs.sh "${GO_LIVE_REMOTE:-origin}"
pass "No branch or tag on the remote publishes development-only files"

step "Gate 10: CODEOWNERS owners resolve"
# Every line named an unrelated account and nothing local could tell (#158).
# Asks GitHub about HEAD, so HEAD must already be pushed, and it reads the
# pushed file: with REQUIRE_CLEAN=0, uncommitted CODEOWNERS edits are unchecked.
./scripts/check-codeowners.sh
pass "Every CODEOWNERS owner is an account GitHub can resolve"

step "Gate 11: SECURITY.md describes the reporting route this repository has"
# Private vulnerability reporting exists only on a public repository, so the
# document is correct in one form while private and in another once public
# (#138). GO_LIVE_VISIBILITY=public checks it before the visibility changes.
./scripts/check-security-policy.sh
pass "SECURITY.md matches the repository's visibility"

step "Manual infrastructure gates (must be validated outside this script)"
echo "- TLS termination and certificate policy at ingress"
echo "- Secret manager wiring and rotation policy"
echo "- Monitoring/alerting dashboards and on-call runbook"
echo "- Rollback rehearsal and release artifact provenance"

printf "\nAll automated go-live gates passed.\n"
