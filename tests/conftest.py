"""
Shared pytest fixtures for FINOS MCP Server tests.

Provides common fixtures for integration and unit tests.
"""

import asyncio
import json
import subprocess
import sys
import time
from typing import Any, AsyncGenerator, Dict, Generator

import pytest


@pytest.fixture
def mcp_server_process() -> Generator[subprocess.Popen, None, None]:
    """Start MCP server process for testing.

    Yields:
        Running subprocess.Popen instance for the MCP server
    """
    # Find finos-mcp script - prefer virtual environment
    import os

    venv_script = os.path.join(os.path.dirname(sys.executable), "finos-mcp")
    script_path = venv_script if os.path.exists(venv_script) else "finos-mcp"

    # Start server process
    process = subprocess.Popen(
        [script_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0,
    )

    # Wait for server to start
    time.sleep(0.5)

    # Ensure server is running
    if process.poll() is not None:
        stdout, stderr = process.communicate()
        raise RuntimeError(f"MCP server failed to start: {stderr}")

    try:
        yield process
    finally:
        # Clean shutdown
        try:
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


@pytest.fixture
def mcp_initialization_request() -> Dict[str, Any]:
    """Standard MCP initialization request.

    Returns:
        MCP initialization request dictionary
    """
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "pytest-test", "version": "1.0.0"},
        },
    }


@pytest.fixture
def mcp_request_factory():
    """Factory function for creating MCP requests.

    Returns:
        Function that creates MCP request dictionaries
    """
    request_id = 1

    def make_request(method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        nonlocal request_id
        request_id += 1

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }

    return make_request


@pytest.fixture
async def mcp_initialized_server(
    mcp_server_process, mcp_initialization_request
) -> Generator[subprocess.Popen, None, None]:
    """MCP server that has been initialized.

    Sends initialization request and validates response.

    Yields:
        Initialized MCP server process
    """
    # Send initialization request
    init_json = json.dumps(mcp_initialization_request) + "\n"
    mcp_server_process.stdin.write(init_json)
    mcp_server_process.stdin.flush()

    # Wait for initialization response
    await asyncio.sleep(0.5)

    # Verify server responded (don't fail if response format is unexpected)
    try:
        import select

        ready, _, _ = select.select([mcp_server_process.stdout], [], [], 1.0)
        if ready:
            response_line = mcp_server_process.stdout.readline()
            if response_line.strip():
                response = json.loads(response_line)
                assert response.get("id") == mcp_initialization_request["id"]
    except (json.JSONDecodeError, ImportError):
        # Windows or invalid JSON - continue anyway
        pass

    yield mcp_server_process


@pytest.fixture
def mcp_server_direct() -> Generator[subprocess.Popen, None, None]:
    """Start MCP server via direct module execution for comparison testing.
    
    Yields:
        Running subprocess.Popen instance for the MCP server (direct module)
    """
    # Start server via direct module execution
    process = subprocess.Popen(
        [sys.executable, "-m", "finos_mcp.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0,
    )
    
    # Wait for server to start
    time.sleep(0.5)
    
    # Ensure server is running
    if process.poll() is not None:
        stdout, stderr = process.communicate()
        raise RuntimeError(f"MCP server (direct module) failed to start: {stderr}")
    
    try:
        yield process
    finally:
        # Clean shutdown
        try:
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
