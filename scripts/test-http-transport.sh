#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/venv/bin/python}"
HOST="${FINOS_MCP_MCP_HOST:-127.0.0.1}"
PORT="${FINOS_MCP_MCP_PORT:-18080}"
URL="http://${HOST}:${PORT}/mcp"
LOG_FILE="${LOG_FILE:-/tmp/finos_mcp_http_test.log}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python runtime not found at $PYTHON_BIN"
  echo "Set PYTHON_BIN=/path/to/python and retry."
  exit 1
fi

echo "Starting MCP server in HTTP mode at ${HOST}:${PORT}"
# Networked transports refuse to start without auth (see Settings.validate_startup).
# This probe deliberately runs unauthenticated to exercise the transport itself,
# so it opts out explicitly. Never set this outside local testing.
FINOS_MCP_ALLOW_INSECURE_HTTP=true \
FINOS_MCP_MCP_TRANSPORT=http \
FINOS_MCP_MCP_HOST="$HOST" \
FINOS_MCP_MCP_PORT="$PORT" \
  "$PYTHON_BIN" -m finos_mcp.fastmcp_main >"$LOG_FILE" 2>&1 &
SERVER_PID=$!

cleanup() {
  kill "$SERVER_PID" >/dev/null 2>&1 || true
  wait "$SERVER_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Poll for the listener instead of sleeping a fixed time: startup includes
# imports and fastmcp's version check, and on a cold machine that can take
# longer than any constant chosen here.
"$PYTHON_BIN" - "$HOST" "$PORT" <<'WAIT'
import socket
import sys
import time

host, port = sys.argv[1], int(sys.argv[2])
deadline = time.monotonic() + 30
while time.monotonic() < deadline:
    with socket.socket() as probe:
        probe.settimeout(0.5)
        if probe.connect_ex((host, port)) == 0:
            raise SystemExit(0)
    time.sleep(0.2)
print(f"FAIL: no server on {host}:{port} within 30s", file=sys.stderr)
raise SystemExit(1)
WAIT

echo "Running MCP streamable HTTP probe against ${URL}"
"$PYTHON_BIN" - <<'PY'
import asyncio
import os
import sys

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main() -> int:
    host = os.getenv("FINOS_MCP_MCP_HOST", "127.0.0.1")
    port = os.getenv("FINOS_MCP_MCP_PORT", "18080")
    url = f"http://{host}:{port}/mcp"

    async with streamable_http_client(url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            tool_names = {tool.name for tool in tools_result.tools}
            if "get_service_health" not in tool_names:
                print("FAIL: expected get_service_health tool not found", file=sys.stderr)
                return 1

            health_result = await session.call_tool("get_service_health", {})
            if not health_result.content:
                print("FAIL: empty get_service_health response", file=sys.stderr)
                return 1

            print(f"PASS: connected to {url}")
            print(f"PASS: discovered {len(tool_names)} tools")
            return 0


raise SystemExit(asyncio.run(main()))
PY

echo "HTTP transport test completed successfully."
