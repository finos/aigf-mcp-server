"""Unit tests for prompt composition service."""

from __future__ import annotations

import pytest

from finos_mcp.application.services import PromptCompositionService


@pytest.mark.unit
class TestPromptCompositionService:
    """Validate prompt text composition behavior."""

    def test_compose_framework_compliance(self):
        service = PromptCompositionService()
        prompt = service.compose_framework_compliance(
            framework="eu-ai-act",
            framework_id="eu-ai-act",
            framework_content="# EU AI Act\n\nSome controls",
            use_case="Credit underwriting model",
        )

        assert "eu-ai-act framework" in prompt
        assert "Credit underwriting model" in prompt
        assert "Recommended next steps for ensuring compliance" in prompt

    def test_compose_risk_assessment(self):
        service = PromptCompositionService()
        prompt = service.compose_risk_assessment(
            risk_category="prompt injection",
            context="Public chatbot with plugin access",
            risk_info="### Prompt Injection (RI-10)\nSummary text",
        )

        assert "RISK CATEGORY: prompt injection" in prompt
        assert "Public chatbot with plugin access" in prompt
        assert "Likelihood assessment" in prompt

    def test_compose_mitigation_strategy(self):
        service = PromptCompositionService()
        prompt = service.compose_mitigation_strategy(
            risk_type="data leakage",
            system_description="LLM assistant handling internal documents",
            mitigation_info="### Data Leakage Prevention (MI-1)\nPurpose text",
        )

        assert "RISK TYPE: data leakage" in prompt
        assert "LLM assistant handling internal documents" in prompt
        assert "Prioritize practical, implementable solutions." in prompt
