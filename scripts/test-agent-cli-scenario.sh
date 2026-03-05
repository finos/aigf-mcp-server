#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/venv/bin/python}"
CONFIG_FILE="${CONFIG_FILE:-/tmp/finos-inspector-config.json}"
SERVER_NAME="${SERVER_NAME:-finos}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-60}"
FILTER="${FILTER:-}"
RUN_UNAVAILABLE_SCENARIO="${RUN_UNAVAILABLE_SCENARIO:-1}"
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

RUN_PRIMARY_SCENARIO=1
if [[ "$RUN_UNAVAILABLE_SCENARIO" == "1" && -n "$FILTER" && "$FILTER" == *"UNAVAILABLE"* ]]; then
  RUN_PRIMARY_SCENARIO=0
fi

if [[ "$RUN_PRIMARY_SCENARIO" == "1" ]]; then
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
fi

if [[ "$RUN_UNAVAILABLE_SCENARIO" == "1" ]]; then
  UNAVAILABLE_CONFIG_FILE="${UNAVAILABLE_CONFIG_FILE:-/tmp/finos-inspector-config-unavailable.json}"
  UNAVAILABLE_SERVER_NAME="${UNAVAILABLE_SERVER_NAME:-finos-unavailable}"
  DISCOVERY_TMP_DIR="${DISCOVERY_TMP_DIR:-/tmp/finos-discovery-unavailable-$$}"
  mkdir -p "$DISCOVERY_TMP_DIR"

  cat >"$UNAVAILABLE_CONFIG_FILE" <<JSON
{
  "mcpServers": {
    "${UNAVAILABLE_SERVER_NAME}": {
      "command": "${PYTHON_BIN}",
      "args": ["-m", "finos_mcp.fastmcp_main"],
      "env": {
        "FINOS_MCP_CACHE_SECRET": "${FINOS_MCP_CACHE_SECRET}",
        "FINOS_MCP_DISCOVERY_CACHE_DIR": "${DISCOVERY_TMP_DIR}",
        "FINOS_MCP_GITHUB_API_BASE_URL": "https://127.0.0.1.invalid"
      }
    }
  }
}
JSON

  echo "Generated unavailable-scenario config: $UNAVAILABLE_CONFIG_FILE"
  echo "Running discovery-unavailable failback scenario..."

  "$PYTHON_BIN" "$ROOT_DIR/scripts/e2e_smoke_test.py" \
    --config "$UNAVAILABLE_CONFIG_FILE" \
    --server "$UNAVAILABLE_SERVER_NAME" \
    --timeout "$TIMEOUT_SECONDS" \
    --include-unavailable \
    --filter "UNAVAILABLE"
fi

echo "Scenario execution completed."
