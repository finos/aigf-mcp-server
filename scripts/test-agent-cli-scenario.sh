#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/venv/bin/python}"
CONFIG_FILE="${CONFIG_FILE:-/tmp/finos-inspector-config.json}"
SERVER_NAME="${SERVER_NAME:-finos}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-60}"
FILTER="${FILTER:-}"
FINOS_MCP_CACHE_SECRET="${FINOS_MCP_CACHE_SECRET:-local-dev-cache-secret-0123456789abcdef}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python runtime not found at $PYTHON_BIN"
  echo "Set PYTHON_BIN=/path/to/python and retry."
  exit 1
fi

cat >"$CONFIG_FILE" <<JSON
{
  "mcpServers": {
    "${SERVER_NAME}": {
      "command": "${PYTHON_BIN}",
      "args": ["-m", "finos_mcp.fastmcp_main"],
      "env": {
        "FINOS_MCP_CACHE_SECRET": "${FINOS_MCP_CACHE_SECRET}"
      }
    }
  }
}
JSON

echo "Generated inspector config: $CONFIG_FILE"
echo "Using FINOS_MCP_CACHE_SECRET from environment or local default."
echo "Running agent-style MCP scenario via Inspector CLI..."

CMD=(
  "$PYTHON_BIN"
  "$ROOT_DIR/scripts/e2e_smoke_test.py"
  --config "$CONFIG_FILE"
  --server "$SERVER_NAME"
  --timeout "$TIMEOUT_SECONDS"
)

if [[ -n "$FILTER" ]]; then
  CMD+=(--filter "$FILTER")
fi

"${CMD[@]}"

echo "Scenario execution completed."
