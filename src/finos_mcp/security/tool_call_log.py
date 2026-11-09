# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""One log line per call: who called which tool, read which resource or
requested which prompt, and how it ended (#271, #315).

The line is written in FastMCP middleware registered before
`DoSProtectionMiddleware`, so it runs outside it. A call that the rate or
concurrency limit refuses never reaches a middleware registered after the DoS
one, and a refused call is one a deployer wants to see.

Argument values are not logged. The tool name, the resource URI or the prompt
name is the only caller-chosen text on the line, since the name of a tool that
does not exist is whatever the caller sent, and it is written with `repr` so
it cannot start a second line. A resource serves the same document as the get
tool for its id, so a read without a line was a way to fetch unrecorded (#315).
"""

from collections.abc import Callable
from typing import Any

from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from mcp import MCPError

from ..logging import get_logger
from .dos_middleware import _RATE_LIMIT_ERROR_CODE

logger = get_logger(__name__)


class ToolCallLogMiddleware(Middleware):
    """Write one INFO line for every tool call, resource read and prompt request."""

    def __init__(self, resolve_client_id: Callable[[], str]) -> None:
        """Initialize the middleware.

        Args:
            resolve_client_id: Returns the calling client's identity, the same
                one the rate limit is counted under.
        """
        self._resolve_client_id = resolve_client_id

    async def on_call_tool(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]
    ) -> Any:
        """Log the tool name, the caller, the outcome and the request id."""
        name = getattr(context.message, "name", "<unknown>")
        return await self._logged("Tool call tool", name, context, call_next)

    async def on_read_resource(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]
    ) -> Any:
        """Log the resource URI, the caller, the outcome and the request id."""
        uri = str(getattr(context.message, "uri", "<unknown>"))
        return await self._logged("Resource read uri", uri, context, call_next)

    async def on_get_prompt(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]
    ) -> Any:
        """Log the prompt name, the caller, the outcome and the request id."""
        name = getattr(context.message, "name", "<unknown>")
        return await self._logged("Prompt request prompt", name, context, call_next)

    async def _logged(
        self,
        label: str,
        name: str,
        context: MiddlewareContext[Any],
        call_next: CallNext[Any, Any],
    ) -> Any:
        """Run the call and write its line whatever happens.

        The outcome is `ok` when the call returned a result, `refused` when the
        rate or concurrency limit refused it, `error` for any other failure and
        `cancelled` when the call was cancelled. The resource handlers refuse an
        unknown id with an MCPError too, so the limits are told apart by their
        error code, not by the exception type (#404). A tool that could not reach GitHub and answered
        from its fallback returned a result, so it is `ok`.
        """
        outcome = "cancelled"
        try:
            result = await call_next(context)
        except MCPError as error:
            outcome = "refused" if error.code == _RATE_LIMIT_ERROR_CODE else "error"
            raise
        except Exception:
            outcome = "error"
            raise
        else:
            outcome = "ok"
            return result
        finally:
            request = context.fastmcp_context
            logger.info(
                "%s=%r caller=%s outcome=%s request_id=%s",
                label,
                name,
                self._resolve_client_id(),
                outcome,
                request.request_id if request is not None else "-",
            )
