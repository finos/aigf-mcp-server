"""Tests for the line that records who called which tool (#271).

The calls go through a real FastMCP server and a real client, with the DoS
middleware registered the way `app.py` registers it, because a call the DoS
middleware refuses never reaches a middleware registered after it.
"""

import asyncio
import logging

import pytest
from fastmcp import Client, FastMCP
from mcp import MCPError

from finos_mcp import fastmcp_server
from finos_mcp.security.dos_middleware import DoSProtectionMiddleware
from finos_mcp.security.request_validator import DoSProtector, RequestSizeValidator
from finos_mcp.security.tool_call_log import ToolCallLogMiddleware

# Only markers registered in pyproject.toml may be used; addopts sets --strict-markers.
pytestmark = [pytest.mark.asyncio]

# The child logger carries its own level and does not propagate, so the capture
# must name it.
LOGGER = "finos-ai-governance-mcp.finos_mcp.security.tool_call_log"

CALLER = "jwt:alice"
ARGUMENT_VALUE = "argument-value-that-must-not-be-logged"


def build_server(max_requests_per_minute: int = 600) -> FastMCP:
    """Build a server with both middlewares in the order `app.py` uses."""
    server = FastMCP("tool-call-log-test")
    server.add_middleware(ToolCallLogMiddleware(resolve_client_id=lambda: CALLER))
    server.add_middleware(
        DoSProtectionMiddleware(
            protector=DoSProtector(max_requests_per_minute=max_requests_per_minute),
            validator=RequestSizeValidator(),
            resolve_client_id=lambda: CALLER,
        )
    )

    @server.tool()
    async def echo_tool(text: str = "") -> str:
        """Return the argument."""
        return text

    @server.tool()
    async def failing_tool() -> str:
        """Always raises."""
        raise RuntimeError("tool blew up")

    @server.resource("test://docs/{doc_id}")
    async def doc_resource(doc_id: str) -> str:
        """The same document a get tool would serve (#315)."""
        return f"document {doc_id}"

    @server.resource("test://broken/{doc_id}")
    async def broken_resource(doc_id: str) -> str:
        """Refuses the way resources.py does for an unknown id or a failed load."""
        raise MCPError(code=-32603, message=f"no document {doc_id}")

    @server.prompt()
    async def echo_prompt(text: str = "") -> str:
        """A prompt with one caller-supplied argument."""
        return f"prompt over {text}"

    return server


def call_lines(
    caplog: pytest.LogCaptureFixture, prefix: str = "Tool call "
) -> list[str]:
    """The captured lines with `prefix`, each from the logger under test at INFO."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == LOGGER
        and record.levelno == logging.INFO
        and record.getMessage().startswith(prefix)
    ]


tool_call_lines = call_lines


async def test_a_served_call_is_logged_once_without_argument_values(caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER):
        async with Client(build_server()) as client:
            result = await client.call_tool("echo_tool", {"text": ARGUMENT_VALUE})
    assert result.content[0].text == ARGUMENT_VALUE

    (line,) = tool_call_lines(caplog)
    assert line.startswith(
        "Tool call tool='echo_tool' caller=jwt:alice outcome=ok request_id="
    )
    request_id = line.rsplit("request_id=", 1)[1]
    assert request_id.isdigit(), line
    assert ARGUMENT_VALUE not in caplog.text


async def test_a_tool_that_raises_is_logged_as_an_error(caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER):
        async with Client(build_server()) as client:
            result = await client.call_tool("failing_tool", {}, raise_on_error=False)
    assert result.is_error

    (line,) = tool_call_lines(caplog)
    assert "tool='failing_tool' caller=jwt:alice outcome=error " in line


async def test_an_unknown_tool_name_cannot_start_a_second_line(caplog):
    """The name of a tool that does not exist is whatever the caller sent."""
    forged = "nope\nTool call tool='get_risk' caller=jwt:bob outcome=ok"
    with caplog.at_level(logging.INFO, logger=LOGGER):
        async with Client(build_server()) as client:
            result = await client.call_tool(forged, {}, raise_on_error=False)
    assert result.is_error

    (line,) = tool_call_lines(caplog)
    assert "\n" not in line
    assert "caller=jwt:alice outcome=error " in line


async def test_a_call_the_rate_limit_refuses_is_logged_as_refused(caplog):
    """The reason the line is written outside the DoS middleware."""
    with caplog.at_level(logging.INFO, logger=LOGGER):
        # The client's own initialize request spends budget too.
        async with Client(build_server(max_requests_per_minute=3)) as client:
            with pytest.raises(MCPError, match="Rate limit exceeded"):
                for _ in range(4):
                    await client.call_tool("echo_tool", {})

    lines = tool_call_lines(caplog)
    assert lines, "no tool call was logged"
    assert "tool='echo_tool' caller=jwt:alice outcome=refused " in lines[-1]
    assert all(" outcome=ok " in line for line in lines[:-1])


async def test_a_cancelled_call_is_logged_as_cancelled(caplog):
    """Cancellation is not an Exception, and the call still leaves its line."""
    middleware = ToolCallLogMiddleware(resolve_client_id=lambda: CALLER)

    class Message:
        name = "echo_tool"

    class Context:
        message = Message()
        fastmcp_context = None

    async def cancelled(_context):
        raise asyncio.CancelledError

    with caplog.at_level(logging.INFO, logger=LOGGER):
        with pytest.raises(asyncio.CancelledError):
            await middleware.on_call_tool(Context(), cancelled)  # type: ignore[arg-type]

    (line,) = tool_call_lines(caplog)
    assert line == (
        "Tool call tool='echo_tool' caller=jwt:alice outcome=cancelled request_id=-"
    )


async def test_a_served_resource_read_is_logged_once(caplog):
    """`finos://risks/{id}` serves what `get_risk` serves; a read is a call (#315)."""
    with caplog.at_level(logging.INFO, logger=LOGGER):
        async with Client(build_server()) as client:
            await client.read_resource("test://docs/" + ARGUMENT_VALUE)

    (line,) = call_lines(caplog, "Resource read ")
    assert line == (
        f"Resource read uri='test://docs/{ARGUMENT_VALUE}' caller=jwt:alice "
        "outcome=ok request_id=2"
    )
    assert not call_lines(caplog, "Tool call ")


async def test_a_served_prompt_request_is_logged_once_without_argument_values(
    caplog,
):
    with caplog.at_level(logging.INFO, logger=LOGGER):
        async with Client(build_server()) as client:
            await client.get_prompt("echo_prompt", {"text": ARGUMENT_VALUE})

    (line,) = call_lines(caplog, "Prompt request ")
    assert line == (
        "Prompt request prompt='echo_prompt' caller=jwt:alice outcome=ok request_id=2"
    )
    assert ARGUMENT_VALUE not in caplog.text


async def test_a_resource_read_the_rate_limit_refuses_is_logged_as_refused(caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER):
        async with Client(build_server(max_requests_per_minute=3)) as client:
            with pytest.raises(MCPError, match="Rate limit exceeded"):
                for _ in range(4):
                    await client.read_resource("test://docs/1")

    lines = call_lines(caplog, "Resource read ")
    assert lines, "no resource read was logged"
    assert "uri='test://docs/1' caller=jwt:alice outcome=refused " in lines[-1]
    assert all(" outcome=ok " in line for line in lines[:-1])


async def test_a_resource_read_that_fails_is_logged_as_an_error(caplog):
    """`refused` means a limit refused the call; any other failure is `error` (#404).

    The resource handlers answer an unknown id with an MCPError too, so the
    outcome cannot be read from the exception type alone.
    """
    with caplog.at_level(logging.INFO, logger=LOGGER):
        async with Client(build_server()) as client:
            with pytest.raises(MCPError, match="no document"):
                await client.read_resource("test://broken/1")

    (line,) = call_lines(caplog, "Resource read ")
    assert " outcome=error " in line, line


async def test_a_prompt_request_the_rate_limit_refuses_is_logged_as_refused(caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER):
        async with Client(build_server(max_requests_per_minute=3)) as client:
            with pytest.raises(MCPError, match="Rate limit exceeded"):
                for _ in range(4):
                    await client.get_prompt("echo_prompt", {"text": "x"})

    lines = call_lines(caplog, "Prompt request ")
    assert lines, "no prompt request was logged"
    assert "prompt='echo_prompt' caller=jwt:alice outcome=refused " in lines[-1]
    assert all(" outcome=ok " in line for line in lines[:-1])


async def test_the_server_logs_refused_calls_too():
    """`app.py` registers the line before the DoS middleware, so outside it."""
    kinds = [type(middleware) for middleware in fastmcp_server.mcp.middleware]
    assert kinds.count(ToolCallLogMiddleware) == 1
    assert kinds.index(ToolCallLogMiddleware) < kinds.index(DoSProtectionMiddleware)
