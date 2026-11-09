"""Tests for DoS enforcement at the MCP boundary.

These tests drive a real FastMCP server through a real client. That is deliberate:
issue #23 exists because DoSProtector.start_request and
RequestSizeValidator.validate_tool_result_size were thoroughly unit-tested and never
called, so the coverage report asserted protection that did not exist at runtime.
Testing the functions in isolation again would reproduce exactly that mistake.

Every tool below deliberately wraps its body in `except Exception` and returns a normal
payload, mirroring the production tools. If enforcement were to move back inside a tool
body, these tests would go green while the server was defenceless.
"""

import asyncio
import sys
from typing import Any

import pytest
from fastmcp import Client, FastMCP
from mcp import MCPError
from mcp.types import TextContent

from finos_mcp.security.dos_middleware import (
    DoSProtectionMiddleware,
    _measurable_tool_payload,
)
from finos_mcp.security.request_validator import DoSProtector, RequestSizeValidator

# Only markers registered in pyproject.toml may be used; addopts sets --strict-markers.
pytestmark = [pytest.mark.asyncio]

# JSON-RPC's implementation-defined server error. A refusal is a protocol error, not a
# tool result, so a client that backs off can key on the code (#162).
JSONRPC_SERVER_ERROR = -32000


def build_server(
    protector: DoSProtector | None = None,
    validator: RequestSizeValidator | None = None,
    client_id: str = "test-client",
) -> tuple[FastMCP, dict[str, str]]:
    """Build a server guarded by the middleware, with swallowing tools.

    Returns the server and a mutable identity holder, so a test can change who the
    caller is between calls.
    """
    identity = {"id": client_id}
    server = FastMCP("dos-test")
    server.add_middleware(
        DoSProtectionMiddleware(
            protector=protector or DoSProtector(),
            validator=validator or RequestSizeValidator(),
            resolve_client_id=lambda: identity["id"],
        )
    )

    @server.tool()
    async def swallowing_tool() -> str:
        """Mirrors the production tools: catches everything, always answers."""
        try:
            return "SERVED"
        except Exception:  # pragma: no cover - defensive, mirrors production shape
            return "SERVED"

    @server.tool()
    async def sized_tool(size: int) -> str:
        """Return a payload of a caller-chosen size."""
        try:
            return "x" * size
        except Exception:  # pragma: no cover - defensive
            return ""

    @server.tool()
    async def failing_tool() -> str:
        """Always raises, to prove a concurrency slot is not leaked."""
        raise RuntimeError("tool blew up")

    @server.tool()
    async def blocking_tool() -> str:
        """Holds its concurrency slot until released."""
        await _gate.wait()
        return "SERVED"

    return server, identity


_gate = asyncio.Event()


@pytest.fixture(autouse=True)
def _fresh_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give each test its own gate.

    An ``asyncio.Event`` binds to the first loop that waits on it, and each
    test runs on its own loop, so the second test to use the module's gate saw
    ``blocking_tool`` raise "bound to a different event loop" at once and free
    its slot (found by #288: the test passed alone and failed in the file).
    """
    monkeypatch.setattr(sys.modules[__name__], "_gate", asyncio.Event())


async def _call_until_rejected(
    client: Client[Any], budget: int
) -> tuple[int, MCPError | None]:
    """Spend the budget on swallowing_tool, returning (calls served, the rejection).

    The client's own initialize and tools/list requests count against the same
    bucket, so the exact number of tool calls a caller gets is not fixed. Looping
    until the rejection arrives keeps the test honest about what it is asserting:
    that the limit reaches the caller at all.
    """
    served = 0
    for _ in range(budget + 2):
        try:
            result = await client.call_tool("swallowing_tool", {}, raise_on_error=False)
        except MCPError as rejection:
            return served, rejection
        assert not result.is_error, "the limit arrived as a tool result"
        block = result.content[0]
        assert isinstance(block, TextContent)
        assert block.text == "SERVED"
        served += 1
    return served, None


class TestRateLimitReachesTheClient:
    """The finding behind #23's third consequence, restated as a test."""

    async def test_rate_limited_call_is_rejected_not_quietly_served(self):
        """A tool that swallows exceptions must not be able to swallow the limit.

        Before this fix the guard lived inside each tool's try block, so an
        over-budget caller received a normal success payload while the server
        logged a rate-limit warning to nobody.
        """
        budget = 6
        server, _ = build_server(protector=DoSProtector(max_requests_per_minute=budget))

        async with Client(server) as client:
            served, rejection = await _call_until_rejected(client, budget)

        assert rejection is not None, "the limit never reached the caller"
        assert rejection.code == JSONRPC_SERVER_ERROR
        assert "rate limit" in rejection.message.lower()
        # Session setup (initialize, tools/list) also spends budget, so the caller
        # gets at most the budget through, never more.
        assert served <= budget

    async def test_each_client_gets_its_own_budget(self):
        """Regression guard for #30: identity must still key the bucket."""
        budget = 6
        server, identity = build_server(
            protector=DoSProtector(max_requests_per_minute=budget),
            client_id="jwt:noisy",
        )

        async with Client(server) as client:
            _, rejection = await _call_until_rejected(client, budget)
            assert rejection is not None

            identity["id"] = "jwt:quiet"
            fresh = await client.call_tool("swallowing_tool", {}, raise_on_error=False)

        assert not fresh.is_error, "one client's spending starved another"
        assert fresh.content[0].text == "SERVED"


class TestConcurrencyLimit:
    """dos_max_concurrent_requests must bound something."""

    async def test_extra_concurrent_request_is_rejected(self):
        server, _ = build_server(
            protector=DoSProtector(
                max_requests_per_minute=100, max_concurrent_requests=2
            )
        )
        _gate.clear()

        async with Client(server) as client:
            held = [
                asyncio.create_task(client.call_tool("blocking_tool", {}))
                for _ in range(2)
            ]
            await asyncio.sleep(0.1)  # let both occupy their slots

            with pytest.raises(MCPError) as overflow:
                await client.call_tool("swallowing_tool", {}, raise_on_error=False)
            assert overflow.value.code == JSONRPC_SERVER_ERROR
            assert "concurrent" in overflow.value.message.lower()

            _gate.set()
            await asyncio.gather(*held)

            # Slots freed: the next caller gets through.
            recovered = await client.call_tool(
                "swallowing_tool", {}, raise_on_error=False
            )

        assert not recovered.is_error

    async def test_slot_is_released_when_the_tool_raises(self):
        """The try/finally acceptance criterion.

        Without the finally, a tool that raises leaks its slot permanently and the
        concurrency limit degrades into a total outage after N failures.
        """
        server, _ = build_server(
            protector=DoSProtector(
                max_requests_per_minute=100, max_concurrent_requests=1
            )
        )

        async with Client(server) as client:
            for _ in range(3):
                failed = await client.call_tool(
                    "failing_tool", {}, raise_on_error=False
                )
                assert failed.is_error

            after = await client.call_tool("swallowing_tool", {}, raise_on_error=False)

        assert not after.is_error, "a raising tool leaked its concurrency slot"
        assert after.content[0].text == "SERVED"


class TestToolResultSize:
    """validate_tool_result_size must actually measure the payload."""

    async def test_oversized_result_is_blocked(self):
        server, _ = build_server(
            validator=RequestSizeValidator(max_tool_result_size=10_000)
        )

        async with Client(server) as client:
            result = await client.call_tool(
                "sized_tool", {"size": 50_000}, raise_on_error=False
            )

        assert result.is_error
        assert "size limit" in result.content[0].text.lower()

    async def test_normal_result_passes(self):
        server, _ = build_server(
            validator=RequestSizeValidator(max_tool_result_size=10_000)
        )

        async with Client(server) as client:
            result = await client.call_tool(
                "sized_tool", {"size": 100}, raise_on_error=False
            )

        assert not result.is_error
        assert len(result.content[0].text) >= 100


class TestMeasurableToolPayload:
    """Guards the trap that makes the naive wiring a no-op.

    RequestSizeValidator._calculate_content_size falls back to str(obj)[:1000] for
    types it does not recognise. ToolResult.content holds TextContent models, not
    strings, so handing it the raw block list measures a 10MB response as 1000 bytes.
    """

    async def test_text_blocks_are_measured_at_full_size(self):
        payload = "A" * 100_000
        blocks = [TextContent(type="text", text=payload)]

        measured = RequestSizeValidator()._calculate_content_size(
            _measurable_tool_payload(blocks, None)
        )

        assert measured >= 100_000

    async def test_raw_content_blocks_would_be_undercounted(self):
        """Documents why the extraction exists; fails if the fallback ever changes."""
        blocks = [TextContent(type="text", text="A" * 100_000)]

        naive = RequestSizeValidator()._calculate_content_size(blocks)

        assert naive < 10_000, (
            "measuring ContentBlocks directly no longer undercounts; "
            "re-check whether _measurable_tool_payload is still needed"
        )

    async def test_structured_content_is_counted(self):
        structured = {"content": "B" * 50_000}

        measured = RequestSizeValidator()._calculate_content_size(
            _measurable_tool_payload([], structured)
        )

        assert measured >= 50_000


class TestASlotIsHeldForTheWholeCall:
    """#288: a call that outlives the request timeout kept its slot in name only.

    ``_cleanup_timed_out_requests`` dropped a slot after the timeout while the
    call ran on, so the limit bounded only fast calls, and a slow content host,
    the moment the limit is for, freed a slot every 30 s. The middleware already
    releases every slot in ``finally``, so the expiry repaired nothing. It is
    gone, with its setting; a slot is held until the call returns.
    """

    async def test_a_third_call_is_refused_while_two_slow_ones_run(self):
        server, _ = build_server(
            protector=DoSProtector(
                max_requests_per_minute=100, max_concurrent_requests=2
            )
        )
        _gate.clear()

        async with Client(server) as client:
            held = [
                asyncio.create_task(client.call_tool("blocking_tool", {}))
                for _ in range(2)
            ]
            # Longer than the 1 s expiry the RED run of this test was given,
            # which let the third call through: the two calls are still
            # running, and must still hold their slots.
            await asyncio.sleep(1.2)

            with pytest.raises(MCPError) as overflow:
                await client.call_tool("swallowing_tool", {}, raise_on_error=False)
            assert overflow.value.code == JSONRPC_SERVER_ERROR
            assert "concurrent" in overflow.value.message.lower()

            _gate.set()
            await asyncio.gather(*held)
