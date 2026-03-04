"""Unit tests for framework use-cases."""

import pytest

from finos_mcp.application.use_cases.framework_use_cases import (
    execute_get_framework,
    execute_list_frameworks,
    format_framework_name,
)


class _FakeFileInfo:
    def __init__(self, filename: str):
        self.filename = filename


class _FakeRepo:
    async def discover_framework_file_infos(self):
        return [_FakeFileInfo("eu-ai-act.yml"), _FakeFileInfo("nist-ai-600-1.yml")]

    async def discover_framework_filenames(self):
        return ["eu-ai-act.yml", "nist-ai-600-1.yml"]

    async def get_framework_document(self, filename: str):
        if filename == "eu-ai-act.yml":
            return {"content": "# Header\nsection: value"}
        return None


@pytest.mark.unit
class TestFrameworkUseCases:
    @pytest.mark.asyncio
    async def test_execute_list_frameworks(self):
        payload = await execute_list_frameworks(
            repository=_FakeRepo(),
            static_framework_files=["fallback.yml"],
            logger=type("L", (), {"error": lambda *args, **kwargs: None})(),
        )
        assert payload["total_count"] == 2
        assert payload["frameworks"][0]["id"] == "eu-ai-act"

    @pytest.mark.asyncio
    async def test_execute_get_framework_found(self):
        payload = await execute_get_framework(
            framework_id="eu-ai-act",
            repository=_FakeRepo(),
            static_framework_files=[],
            format_yaml_content=lambda c, f: c,
            validate_resource_size=lambda _: None,
            safe_external_error=lambda e, m: m,
            logger=type("L", (), {"warning": lambda *args, **kwargs: None})(),
        )
        assert payload["framework_id"] == "eu-ai-act"
        assert payload["sections"] >= 1

    def test_format_framework_name_default(self):
        assert format_framework_name("eu-ai-act") == "EU AI Act 2024"
        assert format_framework_name("custom-framework") == "Custom Framework"
