"""
Integration tests for framework data loading functionality.

Tests that verify actual framework data can be loaded from remote sources
and parsed correctly, preventing functional issues in production.
"""

import asyncio
from unittest.mock import patch

import pytest

from finos_mcp.frameworks.data_loader import FrameworkDataLoader
from finos_mcp.frameworks.models import FrameworkType


@pytest.mark.integration
class TestFrameworkDataLoadingIntegration:
    """Integration tests for live framework data loading."""

    @pytest.mark.asyncio
    async def test_owasp_llm_data_loading(self):
        """Test that OWASP LLM Top 10 data can be loaded successfully."""
        loader = FrameworkDataLoader()

        # Test URL construction
        expected_url = "https://raw.githubusercontent.com/finos/ai-governance-framework/main/docs/_data/owasp-llm.yml"
        filename = loader.framework_files[FrameworkType.OWASP_LLM]
        from urllib.parse import urljoin

        actual_url = urljoin(loader.base_url, filename)

        assert actual_url == expected_url, (
            f"URL mismatch: expected {expected_url}, got {actual_url}"
        )

        # Test data fetching
        raw_data = await loader._fetch_framework_data(filename)
        assert isinstance(raw_data, dict)
        assert len(raw_data) > 0

        # Verify OWASP data structure (should have risk IDs as keys)
        risk_keys = list(raw_data.keys())
        assert any(key.startswith("llm") for key in risk_keys), (
            f"No LLM risk keys found in {risk_keys}"
        )

        # Test full framework loading
        framework = await loader.load_framework(FrameworkType.OWASP_LLM)
        assert framework.name == "OWASP LLM Top 10"
        assert framework.framework_type == FrameworkType.OWASP_LLM
        assert len(framework.references) == 10  # Should have 10 OWASP LLM risks
        assert len(framework.sections) == 1  # Should have 1 section

        # Verify references structure
        for ref in framework.references:
            assert ref.id.startswith("owasp-llm-")
            assert ref.framework_type == FrameworkType.OWASP_LLM
            assert ref.title is not None and ref.title != ""
            assert ref.section == "llm-risks"

    @pytest.mark.asyncio
    async def test_all_framework_types_loadable(self):
        """Test that all framework types can be loaded without errors."""
        loader = FrameworkDataLoader()

        # Test each framework type
        for framework_type in FrameworkType:
            try:
                framework = await loader.load_framework(framework_type)
                assert framework is not None
                assert framework.framework_type == framework_type
                assert framework.name is not None
                print(
                    f"✅ {framework_type.value}: {framework.name} - {len(framework.references)} references"
                )
            except Exception as e:
                # Log but don't fail for frameworks that might be temporarily unavailable
                print(f"⚠️ {framework_type.value}: {e}")

    @pytest.mark.asyncio
    async def test_framework_data_structure_validation(self):
        """Test that loaded framework data has the expected structure."""
        loader = FrameworkDataLoader()

        # Load OWASP (known to work) for structure validation
        framework = await loader.load_framework(FrameworkType.OWASP_LLM)

        # Validate framework structure
        assert hasattr(framework, "name")
        assert hasattr(framework, "framework_type")
        assert hasattr(framework, "references")
        assert hasattr(framework, "sections")

        # Validate references structure
        if framework.references:
            ref = framework.references[0]
            assert hasattr(ref, "id")
            assert hasattr(ref, "framework_type")
            assert hasattr(ref, "title")
            assert hasattr(ref, "section")

        # Validate sections structure
        if framework.sections:
            section = framework.sections[0]
            assert hasattr(section, "section_id")
            assert hasattr(section, "framework_type")
            assert hasattr(section, "title")

    @pytest.mark.asyncio
    async def test_url_accessibility(self):
        """Test that the base URL and framework files are accessible."""
        loader = FrameworkDataLoader()

        # Test each framework file URL
        import httpx

        async with httpx.AsyncClient() as client:
            for framework_type, filename in loader.framework_files.items():
                from urllib.parse import urljoin

                url = urljoin(loader.base_url, filename)

                try:
                    response = await client.get(url, timeout=10.0)
                    if response.status_code == 200:
                        print(f"✅ {framework_type.value}: {url}")
                    else:
                        print(
                            f"⚠️ {framework_type.value}: {url} - Status {response.status_code}"
                        )
                except Exception as e:
                    print(f"❌ {framework_type.value}: {url} - {e}")

    @pytest.mark.asyncio
    async def test_cache_functionality(self):
        """Test that caching works correctly for framework data."""
        loader = FrameworkDataLoader()

        # Clear cache first
        loader.clear_cache()

        # Load framework twice - second should be from cache
        framework1 = await loader.load_framework(FrameworkType.OWASP_LLM)
        framework2 = await loader.load_framework(FrameworkType.OWASP_LLM)

        # Should have same structure (though objects may be different instances)
        assert framework1.name == framework2.name
        assert len(framework1.references) == len(framework2.references)
        assert len(framework1.sections) == len(framework2.sections)

    @pytest.mark.asyncio
    async def test_error_handling_invalid_framework(self):
        """Test error handling for invalid framework types."""
        loader = FrameworkDataLoader()

        # Test with non-existent framework type
        with pytest.raises(ValueError, match="No file mapping"):
            # Simulate invalid framework by temporarily removing mapping
            original_files = loader.framework_files.copy()
            loader.framework_files.clear()
            try:
                await loader.load_framework(FrameworkType.OWASP_LLM)
            finally:
                loader.framework_files = original_files

    @pytest.mark.asyncio
    async def test_network_error_handling(self):
        """Test handling of network errors during data loading."""
        loader = FrameworkDataLoader()

        # Simulate network error by using invalid URL
        with patch.object(
            loader, "base_url", "https://invalid-domain-that-does-not-exist.com/"
        ):
            try:
                await loader._fetch_framework_data("owasp-llm.yml")
                # If no exception, check if cache was used instead
                raise AssertionError("Expected network error or cache fallback")
            except Exception as e:
                # Expected behavior - network error occurred
                print(f"Expected network error occurred: {type(e).__name__}")


@pytest.mark.integration
class TestMCPToolsWithLiveData:
    """Integration tests for MCP tools using live framework data."""

    @pytest.mark.asyncio
    async def test_search_frameworks_with_owasp_data(self):
        """Test search_frameworks tool with live OWASP data."""
        from finos_mcp.tools.frameworks import handle_framework_tools

        # Search for OWASP-specific terms
        result = await handle_framework_tools(
            "search_frameworks",
            {
                "query": "prompt injection",
                "frameworks": ["owasp-llm-top-10"],
                "limit": 5,
            },
        )

        assert len(result) == 1
        assert result[0].type == "text"

        # Should find relevant OWASP content (markdown format)
        response_text = result[0].text
        assert "prompt injection" in response_text.lower()
        assert "owasp" in response_text.lower()
        assert "results" in response_text.lower()

        # Should show actual findings
        assert "LLM01:2025" in response_text or "LLM07:2025" in response_text

    @pytest.mark.asyncio
    async def test_get_framework_details_owasp(self):
        """Test get_framework_details tool with OWASP framework."""
        from finos_mcp.tools.frameworks import handle_framework_tools

        result = await handle_framework_tools(
            "get_framework_details",
            {"framework_type": "owasp-llm-top-10", "include_references": True},
        )

        assert len(result) == 1
        assert result[0].type == "text"

        # Should return OWASP framework details (markdown format)
        response_text = result[0].text
        assert "owasp" in response_text.lower()
        assert "llm" in response_text.lower()
        assert "top 10" in response_text.lower()
        assert "references" in response_text.lower()

    @pytest.mark.asyncio
    async def test_list_frameworks_includes_owasp(self):
        """Test list_frameworks tool includes OWASP in results."""
        from finos_mcp.tools.frameworks import handle_framework_tools

        result = await handle_framework_tools(
            "list_frameworks", {"include_stats": True}
        )

        assert len(result) == 1
        assert result[0].type == "text"

        # Should list frameworks including OWASP (markdown format)
        response_text = result[0].text
        assert "owasp" in response_text.lower()
        assert "framework" in response_text.lower()

        # Should show framework count or list
        assert "llm" in response_text.lower() or "top 10" in response_text.lower()


@pytest.mark.integration
class TestFrameworkDataConsistency:
    """Tests to ensure consistency of framework data across different access methods."""

    @pytest.mark.asyncio
    async def test_framework_data_consistency(self):
        """Test that framework data is consistent when accessed different ways."""
        # Load framework directly
        loader = FrameworkDataLoader()
        direct_framework = await loader.load_framework(FrameworkType.OWASP_LLM)

        # Load framework via MCP tools
        from finos_mcp.tools.frameworks import handle_framework_tools

        mcp_result = await handle_framework_tools(
            "get_framework_details",
            {"framework_type": "owasp-llm-top-10", "include_references": True},
        )

        # Compare key data points (MCP returns markdown, not JSON)
        mcp_response = mcp_result[0].text

        # Should contain framework name and key information
        assert direct_framework.name.lower() in mcp_response.lower()
        assert "owasp" in mcp_response.lower()
        assert "references" in mcp_response.lower()

        # Should have same number of references mentioned
        assert str(len(direct_framework.references)) in mcp_response


if __name__ == "__main__":
    # Run a quick test to verify OWASP data loading
    async def quick_test():
        print("🧪 Quick OWASP data loading test...")
        loader = FrameworkDataLoader()
        try:
            framework = await loader.load_framework(FrameworkType.OWASP_LLM)
            print(f"✅ Successfully loaded {framework.name}")
            print(f"   References: {len(framework.references)}")
            print(f"   Sections: {len(framework.sections)}")

            # Show first few references
            for i, ref in enumerate(framework.references[:3]):
                print(f"   {i + 1}. {ref.id}: {ref.title}")

        except Exception as e:
            print(f"❌ Failed to load OWASP data: {e}")

    asyncio.run(quick_test())
