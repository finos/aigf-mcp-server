"""
Golden file tests for frontmatter parser with real FINOS documents.

These tests validate that the parser correctly handles real documents
from the FINOS AI Governance Framework repository.
"""

import json
from pathlib import Path

import pytest
import pytest_asyncio

from finos_mcp.content.fetch import get_http_client
from finos_mcp.content.parse import parse_frontmatter


@pytest.fixture(scope="session")
def golden_dir():
    """Get the golden files directory."""
    return Path(__file__).parent.parent / "golden"


@pytest_asyncio.fixture(scope="session")
async def real_documents():
    """Fetch real documents from FINOS repository for testing."""
    documents = {}

    # Sample documents to test with
    test_urls = [
        (
            "mi-1",
            "https://raw.githubusercontent.com/finos/ai-governance-framework/main/docs/_mitigations/mi-1_ai-data-leakage-prevention-and-detection.md",
        ),
        (
            "ri-1",
            "https://raw.githubusercontent.com/finos/ai-governance-framework/main/docs/_risks/ri-1_data-leakage.md",
        ),
        (
            "ri-10",
            "https://raw.githubusercontent.com/finos/ai-governance-framework/main/docs/_risks/ri-10_prompt-injection.md",
        ),
    ]

    try:
        async with await get_http_client() as client:
            for doc_id, url in test_urls:
                try:
                    content = await client.fetch_text(url)
                    documents[doc_id] = content
                except Exception as e:
                    # Skip if can't fetch (e.g., no internet)
                    pytest.skip(f"Could not fetch {doc_id}: {e}")
    except Exception as e:
        pytest.skip(f"HTTP client setup failed: {e}")

    if not documents:
        pytest.skip("No documents could be fetched for testing")

    return documents


@pytest.mark.integration
class TestFrontmatterGoldenFiles:
    """Test frontmatter parsing against real FINOS documents."""

    @pytest.mark.asyncio
    async def test_mitigation_document_parsing(self, real_documents):
        """Test parsing of real mitigation document."""
        if "mi-1" not in real_documents:
            pytest.skip("mi-1 document not available")

        content = real_documents["mi-1"]
        frontmatter, body = parse_frontmatter(content)

        # Validate expected frontmatter fields for mitigation
        assert "sequence" in frontmatter
        assert "title" in frontmatter
        assert "doc-status" in frontmatter
        assert "type" in frontmatter

        # Validate types and values
        assert isinstance(frontmatter["sequence"], int)
        assert isinstance(frontmatter["title"], str)
        assert len(frontmatter["title"]) > 0
        assert frontmatter["type"] == "mitigation"

        # Validate body content
        assert isinstance(body, str)
        assert len(body) > 100  # Should have substantial content
        assert "## Purpose" in body or "# Purpose" in body  # Standard section

    @pytest.mark.asyncio
    async def test_risk_document_parsing(self, real_documents):
        """Test parsing of real risk documents."""
        for risk_id in ["ri-1", "ri-10"]:
            if risk_id not in real_documents:
                continue

            content = real_documents[risk_id]
            frontmatter, body = parse_frontmatter(content)

            # Validate expected frontmatter fields for risks
            assert "sequence" in frontmatter
            assert "title" in frontmatter
            assert "doc-status" in frontmatter

            # Validate types and values
            assert isinstance(frontmatter["sequence"], int)
            assert isinstance(frontmatter["title"], str)
            assert len(frontmatter["title"]) > 0

            # Check for references (common in FINOS docs)
            if "references" in frontmatter:
                assert isinstance(frontmatter["references"], list)
                assert len(frontmatter["references"]) > 0

            # Validate body content
            assert isinstance(body, str)
            assert len(body) > 50  # Should have content

    @pytest.mark.asyncio
    async def test_frontmatter_consistency(self, real_documents):
        """Test consistency of frontmatter parsing across documents."""
        all_frontmatters = {}

        for doc_id, content in real_documents.items():
            frontmatter, body = parse_frontmatter(content)
            all_frontmatters[doc_id] = frontmatter

        # Validate that all documents have consistent required fields
        required_fields = ["sequence", "title", "doc-status"]

        for doc_id, frontmatter in all_frontmatters.items():
            for field in required_fields:
                assert field in frontmatter, f"Missing {field} in {doc_id}"
                assert frontmatter[field] is not None, f"Null {field} in {doc_id}"
                assert frontmatter[field] != "", f"Empty {field} in {doc_id}"

    @pytest.mark.asyncio
    async def test_document_structure_validation(self, real_documents):
        """Test that parsed documents maintain expected structure."""
        for doc_id, content in real_documents.items():
            frontmatter, body = parse_frontmatter(content)

            # Validate sequence numbers are reasonable
            if "sequence" in frontmatter:
                sequence = frontmatter["sequence"]
                assert 1 <= sequence <= 100, (
                    f"Sequence {sequence} out of range in {doc_id}"
                )

            # Validate status values are expected
            if "doc-status" in frontmatter:
                valid_statuses = ["ACTIVE", "DRAFT", "DEPRECATED", "ARCHIVED"]
                status = frontmatter["doc-status"]
                assert status in valid_statuses, f"Invalid status {status} in {doc_id}"

            # Validate body has markdown structure
            if body:
                # Should have headings
                has_headings = any(line.startswith("#") for line in body.split("\n"))
                assert has_headings, f"No headings found in body of {doc_id}"

    def test_create_golden_reference_files(self, real_documents, golden_dir, request):
        """Create golden reference files for frontmatter parsing (run manually)."""
        # Only run if explicitly requested
        if not request.config.getoption("--update-golden", default=False):
            pytest.skip("Golden file update not requested")

        golden_dir.mkdir(exist_ok=True)

        for doc_id, content in real_documents.items():
            frontmatter, body = parse_frontmatter(content)

            golden_data = {
                "document_id": doc_id,
                "frontmatter": frontmatter,
                "body_length": len(body),
                "body_preview": body[:200] + "..." if len(body) > 200 else body,
                "has_references": "references" in frontmatter,
                "reference_count": len(frontmatter.get("references", [])),
                "parsing_successful": True,
            }

            golden_file = golden_dir / f"frontmatter_{doc_id}.json"
            with open(golden_file, "w", encoding="utf-8") as f:
                json.dump(golden_data, f, indent=2, ensure_ascii=False)

    def test_validate_against_golden_files(self, real_documents, golden_dir):
        """Validate parsing results against golden reference files."""
        for doc_id, content in real_documents.items():
            golden_file = golden_dir / f"frontmatter_{doc_id}.json"

            if not golden_file.exists():
                pytest.skip(f"No golden file for {doc_id}")

            with open(golden_file, encoding="utf-8") as f:
                expected = json.load(f)

            frontmatter, body = parse_frontmatter(content)

            # Validate key consistency
            assert frontmatter.get("sequence") == expected["frontmatter"].get(
                "sequence"
            )
            assert frontmatter.get("title") == expected["frontmatter"].get("title")
            assert frontmatter.get("doc-status") == expected["frontmatter"].get(
                "doc-status"
            )

            # Validate structure consistency
            assert len(body) >= expected["body_length"] * 0.9  # Allow 10% variance
            assert ("references" in frontmatter) == expected["has_references"]

            if "references" in frontmatter:
                actual_ref_count = len(frontmatter["references"])
                expected_ref_count = expected["reference_count"]
                assert actual_ref_count == expected_ref_count


@pytest.mark.integration
class TestFrontmatterPerformance:
    """Test frontmatter parser performance with real documents."""

    @pytest.mark.asyncio
    async def test_parsing_performance(self, real_documents):
        """Test parser performance with real documents."""
        import time

        if not real_documents:
            pytest.skip("No real documents available for performance testing")

        # Warm up
        for content in list(real_documents.values())[:1]:
            parse_frontmatter(content)

        # Measure parsing time
        total_time = 0.0
        total_docs = 0

        for doc_id, content in real_documents.items():
            start_time = time.time()
            frontmatter, body = parse_frontmatter(content)
            end_time = time.time()

            parse_time = end_time - start_time
            total_time += parse_time
            total_docs += 1

            # Each document should parse quickly
            assert parse_time < 1.0, (
                f"Parsing {doc_id} took {parse_time:.3f}s (too slow)"
            )

        if total_docs > 0:
            avg_time = total_time / total_docs
            print(f"\nAverage parsing time: {avg_time:.3f}s per document")
            assert avg_time < 0.5, f"Average parsing time {avg_time:.3f}s too slow"

    @pytest.mark.asyncio
    async def test_memory_usage(self, real_documents):
        """Test memory usage during parsing."""
        import os

        import psutil

        if not real_documents:
            pytest.skip("No real documents available for memory testing")

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Parse all documents multiple times
        for _ in range(5):
            for content in real_documents.values():
                frontmatter, body = parse_frontmatter(content)

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 50MB)
        assert memory_increase < 50 * 1024 * 1024, (
            f"Memory increased by {memory_increase / 1024 / 1024:.1f}MB"
        )


def pytest_addoption(parser):
    """Add pytest command line options."""
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Update golden reference files",
    )
