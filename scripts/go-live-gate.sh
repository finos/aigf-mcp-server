#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/venv/bin/python}"
REQUIRE_CLEAN="${REQUIRE_CLEAN:-1}"
FINOS_MCP_CACHE_SECRET="${FINOS_MCP_CACHE_SECRET:-test_cache_secret_for_go_live_gates_32chars}"
export FINOS_MCP_CACHE_SECRET

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

if [[ ! -x "$PYTHON_BIN" ]]; then
  fail "Python runtime not found at $PYTHON_BIN"
fi

step "Gate 1: Ensure development-only folders are not tracked"
DEV_ONLY_PATTERN='^(\.claude/|skills/|venv/|\.venv/|\.cache/)'
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
"$PYTHON_BIN" -m mypy src/finos_mcp
pass "Ruff and MyPy checks passed"

step "Gate 4: Regression test suite"
"$PYTHON_BIN" -m pytest -q tests/unit/test_config_validation.py tests/unit/test_fastmcp_server.py tests/integration/test_fastmcp_integration.py
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
  if "$PYTHON_BIN" -m pip_audit \
    --ignore-vuln GHSA-7gcm-g887-7qv7 \
    --ignore-vuln GHSA-w8v5-vhqr-4h9v >"$PIP_AUDIT_LOG" 2>&1; then
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

step "Manual infrastructure gates (must be validated outside this script)"
echo "- TLS termination and certificate policy at ingress"
echo "- Secret manager wiring and rotation policy"
echo "- Monitoring/alerting dashboards and on-call runbook"
echo "- Rollback rehearsal and release artifact provenance"

printf "\nAll automated go-live gates passed.\n"
