"""Prompt composition helpers for MCP prompt handlers."""

from __future__ import annotations


class PromptCompositionService:
    """Compose user-facing prompt templates from gathered context."""

    def compose_framework_compliance(
        self,
        *,
        framework: str,
        framework_id: str,
        framework_content: str,
        use_case: str,
    ) -> str:
        """Compose a framework compliance analysis prompt."""
        return f"""You are an AI governance expert. Analyze the following AI use case for compliance with the {framework} framework.

FRAMEWORK: {framework_id}
FRAMEWORK CONTENT:
{framework_content[:2000]}...

USE CASE TO ANALYZE:
{use_case}

Please provide:
1. Key compliance requirements that apply to this use case
2. Potential risks and mitigation strategies
3. Specific sections of the framework that are most relevant
4. Recommended next steps for ensuring compliance

Focus on practical, actionable guidance."""

    def compose_risk_assessment(
        self,
        *,
        risk_category: str,
        context: str,
        risk_info: str,
    ) -> str:
        """Compose a risk assessment analysis prompt."""
        return f"""You are an AI risk assessment specialist. Conduct a thorough risk assessment for the following scenario.

RISK CATEGORY: {risk_category}
SCENARIO: {context}

RELEVANT RISK DOCUMENTATION:
{risk_info}

Please provide:
1. Likelihood assessment (High/Medium/Low) with justification
2. Impact assessment (High/Medium/Low) with potential consequences
3. Specific risk factors present in this scenario
4. Recommended mitigation strategies
5. Monitoring and detection approaches

Be specific and actionable in your recommendations."""

    def compose_mitigation_strategy(
        self,
        *,
        risk_type: str,
        system_description: str,
        mitigation_info: str,
    ) -> str:
        """Compose a mitigation strategy planning prompt."""
        return f"""You are an AI safety engineer tasked with developing mitigation strategies.

RISK TYPE: {risk_type}
AI SYSTEM: {system_description}

AVAILABLE MITIGATION STRATEGIES:
{mitigation_info}

Please develop a comprehensive mitigation plan that includes:
1. Preventive measures to reduce risk likelihood
2. Detective controls to identify when risks occur
3. Corrective actions to respond to incidents
4. Technical implementation details
5. Monitoring and validation approaches
6. Timeline and resource requirements

Prioritize practical, implementable solutions."""
