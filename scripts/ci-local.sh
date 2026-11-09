#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

# Resolved once here and reused by every phase below, so this script and the
# pre-commit hooks it eventually runs agree on which interpreter is being
# measured. The shim also refuses to proceed when the resolved environment
# contradicts pyproject.toml -- the check that would have caught the project
# venv sitting at fastmcp 2.14.5 against a declared >=3.4.7,<4 (#89).
if ! PYTHON_BIN="$("$ROOT_DIR/scripts/project-python.sh" --print-interpreter)"; then
  exit 1
fi
export PYTHON_BIN

# Checked here rather than at the pre-commit phase at the end of this script, so
# a missing dev extra is reported in a second instead of after a full run.
if ! "$PYTHON_BIN" -c "import pre_commit" >/dev/null 2>&1; then
  echo "pre-commit is not installed in $PYTHON_BIN." >&2
  echo "Install the dev extra:  $PYTHON_BIN -m pip install -e '.[security,dev]'" >&2
  exit 1
fi

# main is production and branch protection is unavailable on this repository, so
# .pre-commit-config.yaml names the pre-push hook as the one place enforcement
# actually happens. That claim was false on a clean checkout: nothing installed
# the hooks and nothing noticed, because an uninstalled hook and a passing hook
# look identical from the outside (#56). Checked here because this is the script
# a developer runs before pushing -- and checked via `git rev-parse --git-path`
# rather than a literal .git/hooks so it stays correct inside a worktree, where
# .git is a file and the hooks live in the main repository.
HOOK_PATH="$(git rev-parse --git-path hooks/pre-push 2>/dev/null || true)"
if [[ -z "$HOOK_PATH" || ! -x "$HOOK_PATH" ]]; then
  echo "The pre-push hook is not installed, so the functional gate cannot run." >&2
  echo "That gate is the only enforcement point this repository has: branch" >&2
  echo "protection is unavailable, so a red CI check cannot block a merge." >&2
  echo "Install it:  $PYTHON_BIN -m pre_commit install" >&2
  exit 1
fi


mkdir -p security-reports coverage-reports

echo "==> Ensure CI helper deps"
"$PYTHON_BIN" -m pip install lxml

echo "==> Bandit"
"$PYTHON_BIN" -m bandit -c config/security/bandit.yml -r src/ \
  --format json \
  --output security-reports/bandit-report.json \
  --severity-level low \
  --confidence-level medium

echo "==> Semgrep"
./scripts/semgrep-isolated.sh --config config/security/semgrep.yml src/ \
  --json \
  --output security-reports/semgrep-report.json \
  --metrics=off

echo "==> Pylint"
set +e
"$PYTHON_BIN" -m pylint src/ --output-format=json --reports=yes --score=yes > security-reports/pylint-report.json
PYLINT_EXIT_CODE=$?
set -e
if [[ "$PYLINT_EXIT_CODE" -ne 0 ]]; then
  echo "Pylint failed with exit code $PYLINT_EXIT_CODE" >&2
  exit "$PYLINT_EXIT_CODE"
fi

echo "==> Ruff lint + format"
"$PYTHON_BIN" -m ruff check src/ tests/ scripts/
"$PYTHON_BIN" -m ruff format --check src/ tests/ scripts/

echo "==> MyPy"
# No rule flags: [tool.mypy] in pyproject.toml is the single source of truth,
# targets included (src/finos_mcp and tests, #343), so this run and a bare
# `mypy` enforce exactly the same thing.
"$PYTHON_BIN" -m mypy \
  --show-error-codes \
  --show-error-context \
  --txt-report security-reports/mypy-report

echo "==> Pytest + coverage"
# No explicit path and no --cov-fail-under: testpaths and the coverage floor
# both come from pyproject.toml, matching CI exactly.
"$PYTHON_BIN" -m pytest \
  --cov=src/finos_mcp \
  --cov-report=json:coverage-reports/coverage.json \
  --cov-report=xml:coverage-reports/coverage.xml \
  --cov-report=html:coverage-reports/html \
  --junit-xml=coverage-reports/pytest.xml \
  --tb=short \
  --quiet

echo "==> pip-audit"
# Suppressions come from [tool.finos.pip-audit] in pyproject.toml, never inline.
PYTHON_BIN="$PYTHON_BIN" ./scripts/pip-audit-scan.sh \
  --format json --output security-reports/pip-audit-report.json

echo "==> pre-commit"
# The hooks are the only gate with no equivalent above: detect-secrets,
# end-of-file-fixer, check-yaml, check-toml and the Claude-content blockers run
# nowhere else, so without this a green local run could still fail CI -- which
# is exactly how a broken semgrep hook and a failing detect-secrets hook both
# reached main.
#
# The tool hooks do repeat work the phases above already did. That is the
# honest cost of running the same gate CI runs: every one of them is
# repo: local + language: system, so they re-run *these* tools with *this*
# configuration rather than introducing a second toolchain, and the repeat
# costs roughly a minute.
"$PYTHON_BIN" -m pre_commit run --all-files

echo "==> Functional gate (live MCP)"
# Mirrors the functional-gate job in security-analysis.yml. main is production,
# so this suite must be green before a merge; it drives the real server over
# stdio and asserts on the content of every answer rather than its shape.
#
# It reaches GitHub. Unauthenticated that is 60 requests/hour per IP, and the
# suite asserts source is "github_api" or "cache", so a spent budget fails here
# rather than passing on static-fallback or expired-list data -- the fallback
# ships the correct filenames even when discovery is misconfigured, so a pass on
# it would prove nothing.
#
# The auth HTTP suite runs beside it; it needs no network (#342).
FINOS_RUN_LIVE_MCP_TEST=1 FINOS_RUN_AUTH_HTTP_TEST=1 "$PYTHON_BIN" -m pytest -q \
  tests/integration/test_live_mcp_server.py \
  tests/integration/test_auth_http_transport.py

echo "Local CI parity checks passed."
