#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/venv/bin/python}"
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

if [[ ! -x "$PYTHON_BIN" ]]; then
  fail "Python runtime not found at $PYTHON_BIN"
fi

step "Gate 1: Ensure development-only folders are not tracked"
if git ls-files | rg -q "^(\\.claude/|skills/|venv/|\\.venv/|\\.cache/)"; then
  git ls-files | rg "^(\\.claude/|skills/|venv/|\\.venv/|\\.cache/)"
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
"$PYTHON_BIN" -m pip_audit \
  --ignore-vuln GHSA-7gcm-g887-7qv7 \
  --ignore-vuln GHSA-w8v5-vhqr-4h9v
pass "pip-audit passed"

step "Manual infrastructure gates (must be validated outside this script)"
echo "- TLS termination and certificate policy at ingress"
echo "- Secret manager wiring and rotation policy"
echo "- Monitoring/alerting dashboards and on-call runbook"
echo "- Rollback rehearsal and release artifact provenance"

printf "\nAll automated go-live gates passed.\n"
