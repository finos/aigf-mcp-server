"""
Test suite for FastMCP server implementation.

Tests the modern FastMCP-based server with structured output and decorator-based tools.
"""

import inspect
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from finos_mcp.fastmcp_server import (
    CacheStats,
    DocumentContent,
    DocumentInfo,
    DocumentList,
    Framework,
    FrameworkContent,
    FrameworkList,
    SearchResults,
    ServiceHealth,
    _best_match_index,
    _clean_search_snippet,
    _extract_section,
    _format_document_name,
    get_cache_stats,
    get_framework,
    get_mitigation,
    get_risk,
    get_service_health,
    list_frameworks,
    list_mitigations,
    list_risks,
    mcp,
    search_risks,
)


async def _list_tools():
    """List tools via the current FastMCP API."""
    tools = await mcp.get_tools()
    return list(tools.values())


async def _call_tool(name: str, arguments: dict):
    """Call tools via the current FastMCP API."""
    tools = await mcp.get_tools()
    result = await tools[name].run(arguments)
    return result.content, result.structured_content


async def _invoke_direct_tool(tool_obj, *args, **kwargs):
    """Invoke decorated tools across function and FunctionTool representations."""
    if hasattr(tool_obj, "fn"):
        result = tool_obj.fn(*args, **kwargs)
    else:
        result = tool_obj(*args, **kwargs)

    if inspect.isawaitable(result):
        return await result
    return result


@pytest.mark.unit
class TestFastMCPServer:
    """Test FastMCP server instance and configuration."""

    def test_server_instance(self):
        """Test that FastMCP server is properly instantiated."""
        assert mcp is not None
        assert mcp.name == "finos-ai-governance"

    @pytest.mark.asyncio
    async def test_server_tools_registration(self):
        """Test that tools are properly registered with FastMCP."""
        tools = await _list_tools()

        # Expected tools from our FastMCP server
        expected_tools = {
            "list_frameworks",
            "get_framework",
            "list_risks",
            "list_mitigations",
            "get_service_health",
            "get_cache_stats",
        }

        actual_tools = {tool.name for tool in tools}
        assert expected_tools.issubset(actual_tools)


@pytest.mark.unit
class TestStructuredOutputModels:
    """Test Pydantic models for structured output."""

    def test_framework_model(self):
        """Test Framework model validation."""
        framework = Framework(
            id="test-framework", name="Test Framework", description="A test framework"
        )
        assert framework.id == "test-framework"
        assert framework.name == "Test Framework"
        assert framework.description == "A test framework"

    def test_framework_list_model(self):
        """Test FrameworkList model validation."""
        frameworks = [
            Framework(id="fw1", name="Framework 1", description="Description 1"),
            Framework(id="fw2", name="Framework 2", description="Description 2"),
        ]

        framework_list = FrameworkList(frameworks=frameworks, total_count=2)
        assert len(framework_list.frameworks) == 2
        assert framework_list.total_count == 2
        assert framework_list.frameworks[0].id == "fw1"

    def test_framework_content_model(self):
        """Test FrameworkContent model validation."""
        content = FrameworkContent(
            framework_id="test-fw",
            content="Test content",
            sections=3,
            last_updated="2024-01-01",
        )
        assert content.framework_id == "test-fw"
        assert content.content == "Test content"
        assert content.sections == 3
        assert content.last_updated == "2024-01-01"

    def test_document_list_model(self):
        """Test DocumentList model validation."""
        docs = [
            {
                "id": "doc1",
                "name": "Document 1",
                "filename": "doc1.md",
                "description": "Desc 1",
            },
            {
                "id": "doc2",
                "name": "Document 2",
                "filename": "doc2.md",
                "description": "Desc 2",
            },
        ]

        doc_list = DocumentList(
            documents=docs, total_count=2, document_type="risk", source="test"
        )
        assert len(doc_list.documents) == 2
        assert doc_list.total_count == 2
        assert doc_list.document_type == "risk"

    def test_service_health_model(self):
        """Test ServiceHealth model validation."""
        health = ServiceHealth(
            status="healthy",
            uptime_seconds=123.45,
            version="1.0.0",
            healthy_services=4,
            total_services=4,
        )
        assert health.status == "healthy"
        assert health.uptime_seconds == 123.45
        assert health.version == "1.0.0"
        assert health.healthy_services == 4

    def test_cache_stats_model(self):
        """Test CacheStats model validation."""
        stats = CacheStats(
            total_requests=100, cache_hits=75, cache_misses=25, hit_rate=0.75
        )
        assert stats.total_requests == 100
        assert stats.cache_hits == 75
        assert stats.cache_misses == 25
        assert stats.hit_rate == 0.75


@pytest.mark.unit
class TestFastMCPTools:
    """Test FastMCP tool functions with structured output."""

    @pytest.mark.asyncio
    async def test_list_frameworks(self):
        """Test list_frameworks tool returns structured FrameworkList."""
        result = await _invoke_direct_tool(list_frameworks)

        assert isinstance(result, FrameworkList)
        assert result.total_count > 0
        assert len(result.frameworks) == result.total_count

        # Check first framework structure
        framework = result.frameworks[0]
        assert isinstance(framework, Framework)
        assert framework.id
        assert framework.name
        assert framework.description

    @pytest.mark.asyncio
    async def test_get_framework_valid_framework(self):
        """Test get_framework with valid framework ID."""
        result = await _invoke_direct_tool(get_framework, "nist-ai-rmf")

        assert isinstance(result, FrameworkContent)
        assert result.framework_id == "nist-ai-rmf"
        assert result.content
        assert result.sections >= 0

    @pytest.mark.asyncio
    async def test_get_framework_invalid_framework(self):
        """Test get_framework with invalid framework ID."""
        result = await _invoke_direct_tool(get_framework, "invalid-framework")

        assert isinstance(result, FrameworkContent)
        assert result.framework_id == "invalid-framework"
        assert "not found" in result.content.lower()
        assert result.sections == 0

    @pytest.mark.asyncio
    async def test_list_risks(self):
        """Test list_risks tool returns structured DocumentList."""
        result = await _invoke_direct_tool(list_risks)

        assert isinstance(result, DocumentList)
        assert result.document_type == "risk"
        assert result.total_count > 0
        assert len(result.documents) == result.total_count

        # Check document structure
        doc = result.documents[0]
        assert hasattr(doc, "id") and doc.id
        assert hasattr(doc, "name") and doc.name
        assert hasattr(doc, "description") and doc.description

    @pytest.mark.asyncio
    async def test_list_mitigations(self):
        """Test list_mitigations tool returns structured DocumentList."""
        result = await _invoke_direct_tool(list_mitigations)

        assert isinstance(result, DocumentList)
        assert result.document_type == "mitigation"
        assert result.total_count > 0
        assert len(result.documents) == result.total_count

    @pytest.mark.asyncio
    async def test_get_service_health(self):
        """Test get_service_health tool returns structured ServiceHealth."""
        result = await _invoke_direct_tool(get_service_health)

        assert isinstance(result, ServiceHealth)
        assert result.status == "healthy"
        assert result.uptime_seconds > 0
        assert result.version
        assert result.healthy_services > 0
        assert result.total_services > 0

    @pytest.mark.asyncio
    async def test_get_cache_stats(self):
        """Test get_cache_stats tool returns structured CacheStats."""
        result = await _invoke_direct_tool(get_cache_stats)

        assert isinstance(result, CacheStats)
        assert result.total_requests >= 0
        assert result.cache_hits >= 0
        assert result.cache_misses >= 0
        assert 0 <= result.hit_rate <= 1


@pytest.mark.unit
class TestFastMCPIntegration:
    """Test FastMCP server integration and tool calls."""

    @pytest.mark.asyncio
    async def test_mcp_call_tool_list_frameworks(self):
        """Test calling list_frameworks through FastMCP server."""
        result = await _call_tool("list_frameworks", {})

        # FastMCP returns tuple: (TextContent, structured_data)
        text_content, structured_data = result

        # Verify structured data
        assert isinstance(structured_data, dict)
        assert "frameworks" in structured_data
        assert "total_count" in structured_data
        assert structured_data["total_count"] > 0

    @pytest.mark.asyncio
    async def test_mcp_call_tool_get_service_health(self):
        """Test calling get_service_health through FastMCP server."""
        result = await _call_tool("get_service_health", {})

        text_content, structured_data = result

        assert isinstance(structured_data, dict)
        assert structured_data["status"] == "healthy"
        assert "version" in structured_data
        assert "uptime_seconds" in structured_data

    @pytest.mark.asyncio
    async def test_mcp_call_tool_with_parameters(self):
        """Test calling tool with parameters through FastMCP server."""
        result = await _call_tool("get_framework", {"framework": "gdpr"})

        text_content, structured_data = result

        assert isinstance(structured_data, dict)
        assert structured_data["framework_id"] == "gdpr"
        assert "content" in structured_data
        assert "sections" in structured_data

    @pytest.mark.asyncio
    async def test_mcp_invalid_tool_call(self):
        """Test calling non-existent tool raises appropriate error."""
        with pytest.raises(Exception):  # FastMCP will raise an exception
            await _call_tool("nonexistent_tool", {})


@pytest.mark.unit
class TestErrorHandling:
    """Test error handling in FastMCP tools."""

    @pytest.mark.asyncio
    async def test_framework_content_error_handling(self):
        """Test that framework content errors are handled gracefully."""
        result = await _invoke_direct_tool(get_framework, "nonexistent-framework")

        assert isinstance(result, FrameworkContent)
        assert "not found" in result.content.lower()
        assert result.sections == 0

    def test_pydantic_validation_errors(self):
        """Test that Pydantic models validate input correctly."""
        # Test missing required fields
        with pytest.raises(ValidationError):
            Framework()  # Missing required fields

        # Test invalid data types
        with pytest.raises(ValidationError):
            CacheStats(
                total_requests="invalid",  # Should be int
                cache_hits=75,
                cache_misses=25,
                hit_rate=0.75,
            )


@pytest.mark.unit
class TestFormatDocumentName:
    """Tests for the _format_document_name helper."""

    def test_basic_risk_name(self):
        assert (
            _format_document_name("ri-9_data-poisoning.md", "ri-")
            == "Data Poisoning (RI-9)"
        )

    def test_basic_mitigation_name(self):
        assert (
            _format_document_name(
                "mi-1_ai-data-leakage-prevention-and-detection.md", "mi-"
            )
            == "AI Data Leakage Prevention and Detection (MI-1)"
        )

    def test_acronym_mcp_uppercased(self):
        result = _format_document_name("mi-20_mcp-server-security-governance.md", "mi-")
        assert result == "MCP Server Security Governance (MI-20)"

    def test_acronym_llm_uppercased(self):
        result = _format_document_name("ri-10_prompt-injection.md", "ri-")
        assert "RI-10" in result
        assert result.startswith("Prompt Injection")

    def test_trailing_dash_stripped(self):
        result = _format_document_name(
            "mi-15_using-large-language-models-for-automated-evaluation-llm-as-a-judge-.md",
            "mi-",
        )
        assert not result.endswith("(MI-15) ")
        assert not result.endswith("- (MI-15)")
        assert "LLM" in result
        assert "MI-15" in result

    def test_number_in_parentheses(self):
        result = _format_document_name("ri-16_bias-and-discrimination.md", "ri-")
        assert result == "Bias and Discrimination (RI-16)"

    def test_strips_prefix_correctly(self):
        """Prefix should not appear in the output name."""
        result = _format_document_name(
            "ri-4_hallucination-and-inaccurate-outputs.md", "ri-"
        )
        assert not result.startswith("Ri ")
        assert "RI-4" in result

    def test_list_risks_names_are_clean(self):
        """Integration check: list_risks documents must not contain old-style names."""
        from finos_mcp.content.discovery import STATIC_RISK_FILES

        for filename in STATIC_RISK_FILES:
            name = _format_document_name(filename, "ri-")
            assert not name.startswith("Ri "), f"Old prefix in: {name}"
            assert "RI-" in name, f"Missing number badge in: {name}"

    def test_list_mitigations_names_are_clean(self):
        """Integration check: list_mitigations documents must not contain old-style names."""
        from finos_mcp.content.discovery import STATIC_MITIGATION_FILES

        for filename in STATIC_MITIGATION_FILES:
            name = _format_document_name(filename, "mi-")
            assert not name.startswith("Mi "), f"Old prefix in: {name}"
            assert "MI-" in name, f"Missing number badge in: {name}"


@pytest.mark.unit
class TestCleanSearchSnippet:
    """Tests for the _clean_search_snippet helper."""

    def test_returns_prose_around_match(self):
        text = "## Summary\n\nData poisoning occurs when adversaries tamper with training data.\n\n## Description\n\nMore detail here."
        snippet = _clean_search_snippet(text, "poisoning", text.index("poisoning"))
        assert "poisoning" in snippet.lower()
        assert len(snippet) > 20

    def test_skips_url_field_lines(self):
        text = "## Links\n\nurl: https://example.com/path\nSome prose content here about the topic.\nurl: https://other.com"
        snippet = _clean_search_snippet(text, "prose", text.index("prose"))
        assert "https://" not in snippet
        assert "prose" in snippet.lower()

    def test_skips_bare_url_lines(self):
        text = "Before text.\nhttps://example.com/very/long/url\nAfter prose text with the query term."
        snippet = _clean_search_snippet(text, "prose", text.index("prose"))
        assert "https://" not in snippet

    def test_truncates_long_snippets(self):
        long_text = "word " * 200
        snippet = _clean_search_snippet(long_text, "word", 0)
        assert len(snippet) <= 283  # 280 + "..."

    def test_fallback_when_no_prose(self):
        text = "url: https://a.com\nurl: https://b.com"
        snippet = _clean_search_snippet(text, "query", 0)
        assert len(snippet) > 0  # never empty


@pytest.mark.unit
class TestExtractSection:
    """Tests for the _extract_section helper."""

    _DOC = (
        "## Summary\n\nThis is the summary text describing the risk.\n\n"
        "## Description\n\nDetailed description follows here.\n\n"
        "## Links\n\nurl: https://example.com"
    )

    def test_extracts_named_section(self):
        result = _extract_section(self._DOC, "Summary")
        assert "summary text" in result.lower()
        assert "Description" not in result

    def test_first_matching_header_wins(self):
        result = _extract_section(self._DOC, "Summary", "Description")
        assert "summary text" in result.lower()

    def test_falls_back_to_second_header(self):
        result = _extract_section(self._DOC, "Overview", "Description")
        assert "Detailed description" in result

    def test_returns_empty_when_no_match(self):
        result = _extract_section(self._DOC, "NonExistent")
        assert result == ""

    def test_respects_max_chars(self):
        long_body = "x " * 1000
        doc = f"## Summary\n\n{long_body}"
        result = _extract_section(doc, "Summary", max_chars=50)
        assert len(result) <= 50

    def test_purpose_header(self):
        doc = "## Purpose\n\nThis mitigation addresses the risk by applying controls.\n\n## Implementation\n\nSteps here."
        result = _extract_section(doc, "Purpose")
        assert "controls" in result
        assert "Steps" not in result


@pytest.mark.unit
class TestTitleField:
    """Tests for the title field on DocumentInfo and Framework models (MCP 2025-06-18)."""

    def test_document_info_has_title_field(self):
        """DocumentInfo accepts and stores a title."""
        doc = DocumentInfo(
            id="9_data-poisoning",
            name="Data Poisoning (RI-9)",
            filename="ri-9_data-poisoning.md",
            title="Data Poisoning (RI-9)",
        )
        assert doc.title == "Data Poisoning (RI-9)"

    def test_document_info_title_optional(self):
        """DocumentInfo title defaults to None for backwards compatibility."""
        doc = DocumentInfo(
            id="9_data-poisoning",
            name="Data Poisoning (RI-9)",
            filename="ri-9_data-poisoning.md",
        )
        assert doc.title is None

    def test_framework_has_title_field(self):
        """Framework accepts and stores a title."""
        fw = Framework(
            id="nist-ai-rmf",
            name="NIST AI Risk Management Framework",
            description="A framework for AI risk management",
            title="NIST AI Risk Management Framework",
        )
        assert fw.title == "NIST AI Risk Management Framework"

    def test_framework_title_optional(self):
        """Framework title defaults to None for backwards compatibility."""
        fw = Framework(
            id="nist-ai-rmf",
            name="NIST AI Risk Management Framework",
            description="A framework for AI risk management",
        )
        assert fw.title is None

    @pytest.mark.asyncio
    async def test_list_risks_documents_have_title(self):
        """list_risks must set title on every returned document."""
        result = await _invoke_direct_tool(list_risks)
        assert isinstance(result, DocumentList)
        for doc in result.documents:
            assert doc.title is not None, f"Missing title on risk doc: {doc.id}"
            assert len(doc.title) > 0

    @pytest.mark.asyncio
    async def test_list_mitigations_documents_have_title(self):
        """list_mitigations must set title on every returned document."""
        result = await _invoke_direct_tool(list_mitigations)
        assert isinstance(result, DocumentList)
        for doc in result.documents:
            assert doc.title is not None, f"Missing title on mitigation doc: {doc.id}"
            assert len(doc.title) > 0

    @pytest.mark.asyncio
    async def test_list_frameworks_have_title(self):
        """list_frameworks must set title on every returned framework."""
        result = await _invoke_direct_tool(list_frameworks)
        assert isinstance(result, FrameworkList)
        for fw in result.frameworks:
            assert fw.title is not None, f"Missing title on framework: {fw.id}"
            assert len(fw.title) > 0


@pytest.mark.unit
class TestDocumentContentTitle:
    """Tests that get_risk and get_mitigation return formatted human-readable titles."""

    @pytest.mark.asyncio
    async def test_get_risk_title_is_formatted(self):
        mock_service = AsyncMock()
        mock_service.get_document.return_value = {"content": "Risk content here"}
        with patch(
            "finos_mcp.fastmcp_server.get_service",
            new_callable=AsyncMock,
            return_value=mock_service,
        ):
            result = await _invoke_direct_tool(get_risk, "9_data-poisoning")
        assert isinstance(result, DocumentContent)
        assert result.title == "Data Poisoning (RI-9)"

    @pytest.mark.asyncio
    async def test_get_mitigation_title_is_formatted(self):
        mock_service = AsyncMock()
        mock_service.get_document.return_value = {"content": "Mitigation content here"}
        with patch(
            "finos_mcp.fastmcp_server.get_service",
            new_callable=AsyncMock,
            return_value=mock_service,
        ):
            result = await _invoke_direct_tool(
                get_mitigation, "1_ai-data-leakage-prevention-and-detection"
            )
        assert isinstance(result, DocumentContent)
        assert result.title == "AI Data Leakage Prevention and Detection (MI-1)"


@pytest.mark.unit
class TestBestMatchIndex:
    """Tests for the _best_match_index search helper.

    Return type is (int, bool) — (char_index, is_exact_phrase).
    """

    def test_exact_phrase_match_index(self):
        idx, is_exact = _best_match_index("data poisoning occurs", "data poisoning")
        assert idx >= 0
        assert is_exact is True

    def test_exact_phrase_is_flagged_exact(self):
        _, is_exact = _best_match_index("model hallucination risk", "hallucination")
        assert is_exact is True

    def test_token_fallback_finds_match(self):
        # "customer data privacy" -> tokens ["customer","data","privacy"]
        # "data" is in the content
        idx, is_exact = _best_match_index(
            "sensitive data leakage", "customer data privacy"
        )
        assert idx >= 0
        assert is_exact is False

    def test_token_fallback_is_not_flagged_exact(self):
        _, is_exact = _best_match_index("only data here", "customer data privacy")
        assert is_exact is False

    def test_stop_words_only_returns_minus_one(self):
        idx, is_exact = _best_match_index("some content here", "the is are")
        assert idx == -1
        assert is_exact is False

    def test_no_match_returns_minus_one(self):
        idx, is_exact = _best_match_index("hello world", "xyzzy foobar")
        assert idx == -1
        assert is_exact is False


@pytest.mark.unit
class TestSearchRanking:
    """Exact-phrase results must rank above token-fallback results (T8)."""

    def test_sort_key_exact_before_fallback(self):
        """Pure sort-key test — no network.  Exact matches must precede token fallbacks."""
        from finos_mcp.fastmcp_server import SearchResult

        exact_late = (
            SearchResult(framework_id="risk-a", section="S", content="x"),
            True,  # is_exact
            800,  # match_index — late in document
        )
        fallback_early = (
            SearchResult(framework_id="risk-b", section="S", content="x"),
            False,  # token fallback
            5,  # match_index — very early
        )
        exact_early = (
            SearchResult(framework_id="risk-c", section="S", content="x"),
            True,
            10,
        )

        tagged = [exact_late, fallback_early, exact_early]
        tagged.sort(key=lambda x: (not x[1], x[2]))

        ids = [t[0].framework_id for t in tagged]
        # exact_early first, exact_late second, fallback_early last
        assert ids == ["risk-c", "risk-a", "risk-b"]

    @pytest.mark.asyncio
    async def test_search_risks_token_fallback_still_returns_results(self):
        """Token-fallback queries still return results (T7 regression)."""
        result = await _invoke_direct_tool(
            search_risks, "customer data privacy", limit=5
        )
        assert isinstance(result, SearchResults)
        assert result.total_found >= 1
