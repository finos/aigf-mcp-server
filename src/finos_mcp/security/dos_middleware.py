# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""DoS enforcement at the MCP protocol boundary.

Rate limiting, per-client concurrency and tool-response size are enforced here, in
FastMCP middleware, rather than inside the tool functions themselves.

The distinction is the whole point of this module. Every tool in this server wraps its
body in `except Exception` and degrades to a fallback payload, which is correct
behaviour for a content lookup but fatal for a guard: a limit raised inside a tool body
was caught by that same handler and the over-budget caller received a normal success
response. Middleware runs outside the tool function, so a rejection raised here cannot
be swallowed by the code it is meant to constrain.

Why this is not FastMCP's built-in middleware
---------------------------------------------
FastMCP ships `RateLimitingMiddleware` and `ResponseLimitingMiddleware`, and the
rate-limiting half of this module could be replaced by the former: it supports the
per-client keying this server needs, via its `get_client_id` hook. Two things are not
covered, which is why this module stays:

* There is no built-in concurrency limiter. The bounded in-flight slot below, and its
  release on the error path, have no upstream equivalent.
* `ResponseLimitingMiddleware` *truncates* an oversized response and returns success.
  This server rejects it instead. Truncation would hand the caller a silently
  incomplete document, which for governance content is worse than a clear error.

Adopting the built-in rate limiter is not planned: it would change the key a
caller is counted under and the error a refused call gets, and no issue asks
for either.
"""

from collections.abc import Callable
from typing import Any

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools import ToolResult
from mcp import MCPError

from ..logging import get_logger
from .request_validator import DoSProtector, RequestSizeValidator

logger = get_logger(__name__)

# JSON-RPC implementation-defined server error, matching the code FastMCP's own
# rate-limiting middleware returns for a refused request.
_RATE_LIMIT_ERROR_CODE = -32000


def _measurable_tool_payload(
    content: list[Any], structured_content: dict[str, Any] | None
) -> list[Any]:
    """Flatten a tool response into values RequestSizeValidator can measure.

    RequestSizeValidator._calculate_content_size only measures str, bytes, list and
    dict at full size; anything else falls back to str(obj)[:1000]. ToolResult.content
    holds TextContent models, not strings, so handing the block list over unchanged
    measures a 10MB response as 1000 bytes and the limit silently never fires.

    Both content blocks and structured content are transmitted to the client, so both
    count toward the response budget.
    """
    payload: list[Any] = []
    for block in content:
        for attribute in ("text", "data", "blob"):
            value = getattr(block, attribute, None)
            if value is not None:
                payload.append(value)
                break
        else:
            # Unknown block type: measure its serialised form rather than skipping it.
            dump = getattr(block, "model_dump", None)
            payload.append(dump() if callable(dump) else block)

    if structured_content is not None:
        payload.append(structured_content)

    return payload


class DoSProtectionMiddleware(Middleware):
    """Enforce rate, concurrency and response-size limits on client requests."""

    def __init__(
        self,
        protector: DoSProtector,
        validator: RequestSizeValidator,
        resolve_client_id: Callable[[], str],
    ) -> None:
        """Initialize the middleware.

        Args:
            protector: Shared DoS protector holding per-client request state.
            validator: Shared size validator holding the response size budget.
            resolve_client_id: Returns the calling client's identity. Injected rather
                than imported so this module stays independent of application settings.
        """
        self._protector = protector
        self._validator = validator
        self._resolve_client_id = resolve_client_id

    async def on_request(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]
    ) -> Any:
        """Apply rate and concurrency limits to every client request."""
        await self._protector.periodic_cleanup()
        client_id = self._resolve_client_id()
        # Logged so an operator can confirm a trusted-proxy allowlist actually
        # resolves the client they expect, rather than guessing at the config.
        logger.debug("Rate-limit key resolved to %s", client_id)

        if not await self._protector.check_rate_limit(client_id):
            raise MCPError(
                code=_RATE_LIMIT_ERROR_CODE,
                message="Rate limit exceeded. Please slow down and try again later.",
            )

        try:
            request_id = await self._protector.start_request(client_id)
        except ValueError as e:
            raise MCPError(code=_RATE_LIMIT_ERROR_CODE, message=str(e)) from e

        try:
            return await call_next(context)
        finally:
            # Must release on the error path too. A leaked slot is permanent, so
            # without this a handful of failing requests becomes a total outage for
            # that client once max_concurrent_requests slots are stuck.
            await self._protector.complete_request(client_id, request_id)

    async def on_call_tool(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]
    ) -> Any:
        """Reject a tool response that exceeds the configured size budget."""
        result = await call_next(context)

        if isinstance(result, ToolResult):
            payload = _measurable_tool_payload(
                result.content, result.structured_content
            )
        else:  # pragma: no cover - defensive, FastMCP returns ToolResult here
            payload = [result]

        try:
            self._validator.validate_tool_result_size(payload)
        except ValueError as e:
            tool_name = getattr(context.message, "name", "<unknown>")
            logger.warning("Tool %s produced an oversized response: %s", tool_name, e)
            raise ToolError(str(e)) from e

        return result
