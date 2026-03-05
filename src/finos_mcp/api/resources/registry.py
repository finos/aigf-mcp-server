"""Registration helpers for MCP resource endpoints."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from pydantic import Field


def register_resources(
    *,
    mcp: Any,
    resource_annotations: Callable[..., dict[str, object]],
    validate_request_params: Callable[..., None],
    call_registered_tool: Callable[..., Awaitable[Any]],
    safe_resource_content: Callable[[str, str], str],
    safe_external_error: Callable[[Exception, str], str],
    get_framework_tool: Any,
    get_risk_tool: Any,
    get_mitigation_tool: Any,
    logger: Any,
) -> None:
    """Register all MCP resources on the provided FastMCP server."""

    @mcp.resource(
        "finos://frameworks/{framework_id}",
        name="Framework Document",
        title="Framework Resource",
        description="Framework content from FINOS AI governance corpus.",
        mime_type="text/markdown",
        annotations=resource_annotations(priority=0.9),
    )
    async def get_framework_resource(
        framework_id: Annotated[
            str,
            Field(
                min_length=1,
                max_length=128,
                description="Framework identifier from list_frameworks().",
            ),
        ],
    ) -> str:
        """Get framework content as a resource."""
        try:
            validate_request_params(framework_id=framework_id)
            content = await call_registered_tool(get_framework_tool, framework_id)
            return safe_resource_content(content.content, f"framework:{framework_id}")
        except Exception as exc:
            logger.error("Failed to get framework resource %s: %s", framework_id, exc)
            return safe_external_error(exc, "Error loading framework resource.")

    @mcp.resource(
        "finos://risks/{risk_id}",
        name="Risk Document",
        title="Risk Resource",
        description="Risk documentation from FINOS AI governance corpus.",
        mime_type="text/markdown",
        annotations=resource_annotations(priority=0.85),
    )
    async def get_risk_resource(
        risk_id: Annotated[
            str,
            Field(
                min_length=1,
                max_length=256,
                description="Risk identifier from list_risks().",
            ),
        ],
    ) -> str:
        """Get risk document as a resource."""
        try:
            validate_request_params(risk_id=risk_id)
            content = await call_registered_tool(get_risk_tool, risk_id)
            return safe_resource_content(content.content, f"risk:{risk_id}")
        except Exception as exc:
            logger.error("Failed to get risk resource %s: %s", risk_id, exc)
            return safe_external_error(exc, "Error loading risk resource.")

    @mcp.resource(
        "finos://mitigations/{mitigation_id}",
        name="Mitigation Document",
        title="Mitigation Resource",
        description="Mitigation documentation from FINOS AI governance corpus.",
        mime_type="text/markdown",
        annotations=resource_annotations(priority=0.85),
    )
    async def get_mitigation_resource(
        mitigation_id: Annotated[
            str,
            Field(
                min_length=1,
                max_length=256,
                description="Mitigation identifier from list_mitigations().",
            ),
        ],
    ) -> str:
        """Get mitigation document as a resource."""
        try:
            validate_request_params(mitigation_id=mitigation_id)
            content = await call_registered_tool(get_mitigation_tool, mitigation_id)
            return safe_resource_content(content.content, f"mitigation:{mitigation_id}")
        except Exception as exc:
            logger.error("Failed to get mitigation resource %s: %s", mitigation_id, exc)
            return safe_external_error(exc, "Error loading mitigation resource.")
