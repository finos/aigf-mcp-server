"""Registration helpers for MCP prompt templates."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from pydantic import Field

from ...application.services import extract_section


def register_prompts(
    *,
    mcp: Any,
    validate_request_params: Callable[..., None],
    call_registered_tool: Callable[..., Awaitable[Any]],
    prompt_service: Any,
    get_framework_tool: Any,
    get_risk_tool: Any,
    get_mitigation_tool: Any,
    search_risks_tool: Any,
    search_mitigations_tool: Any,
    logger: Any,
) -> None:
    """Register all MCP prompts on the provided FastMCP server."""

    @mcp.prompt(
        title="Framework Compliance Analysis",
        description="Generate a compliance analysis prompt for a use case against a framework.",
    )
    async def analyze_framework_compliance(
        framework: Annotated[
            str,
            Field(
                min_length=1,
                max_length=128,
                description="Framework identifier (e.g., eu-ai-act).",
            ),
        ],
        use_case: Annotated[
            str,
            Field(min_length=1, max_length=4000, description="AI use case to analyze."),
        ],
    ) -> str:
        """Analyze compliance requirements for an AI use case against a framework."""
        validate_request_params(framework=framework, use_case=use_case)
        framework_content = await call_registered_tool(get_framework_tool, framework)

        return prompt_service.compose_framework_compliance(
            framework=framework,
            framework_id=framework_content.framework_id,
            framework_content=framework_content.content,
            use_case=use_case,
        )

    @mcp.prompt(
        title="Risk Assessment Analysis",
        description="Generate a risk assessment prompt using risk category and scenario context.",
    )
    async def risk_assessment_analysis(
        risk_category: Annotated[
            str,
            Field(min_length=1, max_length=128, description="Risk category to assess."),
        ],
        context: Annotated[
            str,
            Field(
                min_length=1,
                max_length=4000,
                description="Scenario context for risk assessment.",
            ),
        ],
    ) -> str:
        """Generate a risk assessment prompt for a specific AI risk category."""
        validate_request_params(risk_category=risk_category, context=context)

        search_query = risk_category.replace("-", " ")
        search_results = await call_registered_tool(
            search_risks_tool, search_query, limit=3
        )

        risk_sections: list[str] = []
        for result in search_results.results:
            risk_id = result.framework_id.removeprefix("risk-")
            try:
                doc = await call_registered_tool(get_risk_tool, risk_id)
                summary = extract_section(
                    doc.content, "Summary", "Overview", "Description"
                )
                if summary:
                    risk_sections.append(f"### {doc.title} ({risk_id})\n{summary}")
            except Exception as exc:
                logger.debug("Skipping risk doc %s in prompt: %s", risk_id, exc)

        risk_info = (
            "\n\n".join(risk_sections)
            if risk_sections
            else "No specific documentation found for this risk category."
        )

        return prompt_service.compose_risk_assessment(
            risk_category=risk_category,
            context=context,
            risk_info=risk_info,
        )

    @mcp.prompt(
        title="Mitigation Strategy Planning",
        description="Generate a mitigation strategy prompt for a specific AI system risk.",
    )
    async def mitigation_strategy_prompt(
        risk_type: Annotated[
            str,
            Field(min_length=1, max_length=128, description="Risk type to mitigate."),
        ],
        system_description: Annotated[
            str,
            Field(
                min_length=1,
                max_length=4000,
                description="Description of the AI system.",
            ),
        ],
    ) -> str:
        """Generate a mitigation strategy prompt for a specific AI system risk."""
        validate_request_params(
            risk_type=risk_type, system_description=system_description
        )

        search_query = risk_type.replace("-", " ")
        mitigation_results = await call_registered_tool(
            search_mitigations_tool, search_query, limit=3
        )

        mitigation_sections: list[str] = []
        for result in mitigation_results.results:
            mitigation_id = result.framework_id.removeprefix("mitigation-")
            try:
                doc = await call_registered_tool(get_mitigation_tool, mitigation_id)
                purpose = extract_section(doc.content, "Purpose", "Summary", "Overview")
                if purpose:
                    mitigation_sections.append(
                        f"### {doc.title} ({mitigation_id})\n{purpose}"
                    )
            except Exception as exc:
                logger.debug(
                    "Skipping mitigation doc %s in prompt: %s", mitigation_id, exc
                )

        mitigation_info = (
            "\n\n".join(mitigation_sections)
            if mitigation_sections
            else "No specific mitigation documentation found for this risk type."
        )

        return prompt_service.compose_mitigation_strategy(
            risk_type=risk_type,
            system_description=system_description,
            mitigation_info=mitigation_info,
        )
