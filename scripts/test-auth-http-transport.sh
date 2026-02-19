#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python runtime not found at $PYTHON_BIN"
  echo "Set PYTHON_BIN=/path/to/python and retry."
  exit 1
fi

cd "$ROOT_DIR"
echo "Running live HTTP auth integration test..."
FINOS_RUN_AUTH_HTTP_TEST=1 "$PYTHON_BIN" -m pytest -q tests/integration/test_auth_http_transport.py
echo "Auth HTTP transport test completed successfully."
