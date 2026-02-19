#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/venv/bin/python}"

cd "$ROOT_DIR"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python runtime not found at $PYTHON_BIN" >&2
  exit 1
fi

# Required by startup validation during test collection/imports.
export FINOS_MCP_CACHE_SECRET="${FINOS_MCP_CACHE_SECRET:-test_cache_secret_for_local_ci_32chars}"

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
"$PYTHON_BIN" -m mypy src/finos_mcp \
  --show-error-codes \
  --show-error-context \
  --txt-report security-reports/mypy-report \
  --strict-optional \
  --warn-redundant-casts \
  --warn-unused-ignores

echo "==> Pytest + coverage"
"$PYTHON_BIN" -m pytest tests/ \
  --cov=src/finos_mcp \
  --cov-report=json:coverage-reports/coverage.json \
  --cov-report=xml:coverage-reports/coverage.xml \
  --cov-report=html:coverage-reports/html \
  --junit-xml=coverage-reports/pytest.xml \
  --cov-fail-under=65 \
  --tb=short \
  --quiet

echo "==> pip-audit"
"$PYTHON_BIN" -m pip install pip-audit
"$PYTHON_BIN" -m pip_audit --format json --output security-reports/pip-audit-report.json \
  --ignore-vuln GHSA-7gcm-g887-7qv7 \
  --ignore-vuln GHSA-w8v5-vhqr-4h9v

echo "Local CI parity checks passed."
