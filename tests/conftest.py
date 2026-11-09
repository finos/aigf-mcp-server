"""
Shared pytest fixtures for FINOS MCP Server tests.

Provides common fixtures for integration and unit tests.
"""

import asyncio
import json
import subprocess
import sys
import tempfile
import time
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


@pytest.fixture
def mcp_server_process() -> Generator[subprocess.Popen[str], None, None]:
    """Start MCP server process for testing.

    Yields:
        Running subprocess.Popen instance for the MCP server
    """
    # Use virtual environment script only - never fall back to global
    import os

    venv_script = os.path.join(os.path.dirname(sys.executable), "finos-mcp")
    if not os.path.exists(venv_script):
        raise RuntimeError(
            f"finos-mcp script not found in virtual environment: {venv_script}. "
            "Run 'pip install -e .' to install the package in development mode."
        )
    script_path = venv_script

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
def mcp_initialization_request() -> dict[str, Any]:
    """Standard MCP initialization request.

    Returns:
        MCP initialization request dictionary
    """
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
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

    def make_request(
        method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
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
) -> AsyncGenerator[subprocess.Popen[str], None]:
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
def mcp_server_direct() -> Generator[subprocess.Popen[str], None, None]:
    """Start MCP server via direct module execution for comparison testing.

    Yields:
        Running subprocess.Popen instance for the FastMCP server (direct module)
    """
    # Start server via direct module execution using FastMCP
    process = subprocess.Popen(
        [sys.executable, "-m", "finos_mcp.fastmcp_main"],
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


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Temporary directory fixture."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_mcp_requests() -> dict[str, dict[str, Any]]:
    """Sample MCP request templates."""
    return {
        "initialize": {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0.0"},
            },
        },
        "list_tools": {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        "list_resources": {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "resources/list",
            "params": {},
        },
    }


@pytest.fixture
def console_script_runner():
    """Console script runner fixture."""

    def run_script(args: list[str], timeout: float = 5.0, input_data: str = "") -> Any:
        """Run console script and return result."""

        class Result:
            def __init__(self, returncode: int, stdout: str, stderr: str):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        try:
            if args[0] == "which":
                # Handle 'which' command specially
                import shutil

                script_path = shutil.which(args[1])
                if script_path:
                    return Result(0, script_path, "")
                else:
                    return Result(1, "", f"{args[1]} not found")

            # Run the actual command
            process = subprocess.run(
                args,
                input=input_data,
                text=True,
                capture_output=True,
                timeout=timeout,
            )
            return Result(process.returncode, process.stdout, process.stderr)
        except subprocess.TimeoutExpired:
            return Result(-1, "", "Timeout")
        except Exception as e:
            return Result(1, "", str(e))

    return run_script


@pytest.fixture
def error_scenarios() -> dict[str, Any]:
    """Error scenario test data."""
    return {
        "invalid_json": '{"jsonrpc": "2.0", "id": 1, "method": "test"',  # Malformed JSON
        "missing_jsonrpc": {"id": 1, "method": "test", "params": {}},
        "invalid_method": {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "nonexistent_method",
            "params": {},
        },
        "malformed_params": {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": "invalid_params_type",
        },
    }


# NOTE: an autouse `setup_test_environment` fixture used to live here. It set
# FINOS_MCP_VALIDATION_MODE=disabled, which read as "the whole suite, including
# tests/security/, runs with validation switched off". It did not: Settings has
# no `validation_mode` field, the name appears nowhere in src/, and
# pydantic-settings only consults the environment per declared field, so the
# variable was never read. A module-scope setdefault of FINOS_MCP_CACHE_SECRET
# replaced it, and went with the setting (#302).


@pytest.fixture
def fast_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """The HTTP client's retry layer waits for nothing between attempts.

    It still makes every attempt, so a test counts the requests a call costs
    without the 0.5 to 10 seconds of jittered wait before each repeat.
    """
    import tenacity

    from finos_mcp.content.fetch import HTTPClient

    monkeypatch.setattr(HTTPClient._make_request.retry, "wait", tenacity.wait_none())


@pytest.fixture(autouse=True)
def _no_github_backoff_from_an_earlier_test() -> Generator[None, None, None]:
    """Each test starts with the GitHub API backoff clear.

    The backoff is one per process (#310): a test that provokes a refusal
    would otherwise leave every later test's listing and API fetch refused
    without a request, in a way that depends on the order the tests ran.
    """
    from finos_mcp.content import github_api

    github_api.reset_backoff()
    yield
    github_api.reset_backoff()


@pytest.fixture(scope="session")
def key_pair() -> tuple[bytes, str]:
    """An RSA private key and the PEM of its public half (#381).

    One per run: three test modules generated the same 2048-bit key each.
    """
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem.decode("utf-8")
