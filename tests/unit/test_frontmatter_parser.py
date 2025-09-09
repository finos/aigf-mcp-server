"""
Unit tests for frontmatter parser functionality.

Tests comprehensive edge cases including malformed YAML, BOM markers,
encoding issues, and various delimiter styles.
"""

import codecs
from unittest.mock import patch

import pytest

from finos_mcp.content.parse import (
    FrontmatterParser,
    get_parser_stats,
    parse_frontmatter,
    reset_parser_stats,
)


@pytest.fixture
def parser():
    """Create a fresh parser instance for testing."""
    return FrontmatterParser()


@pytest.fixture
def reset_stats():
    """Reset global parser stats before each test."""
    reset_parser_stats()
    yield
    reset_parser_stats()


@pytest.mark.unit
class TestFrontmatterParser:
    """Test the FrontmatterParser class."""

    def test_basic_frontmatter_parsing(self, parser):
        """Test basic YAML frontmatter parsing."""
        content = """---
title: Test Document
author: Test Author
published: true
sequence: 1
---

# Main Content

This is the body of the document."""

        frontmatter, body = parser.parse(content)

        assert frontmatter["title"] == "Test Document"
        assert frontmatter["author"] == "Test Author"
        assert frontmatter["published"] is True
        assert frontmatter["sequence"] == 1
        assert body.startswith("# Main Content")

    def test_no_frontmatter(self, parser):
        """Test content without frontmatter."""
        content = """# Just a regular document

No frontmatter here."""

        frontmatter, body = parser.parse(content)

        assert frontmatter == {}
        assert body == content

    def test_empty_frontmatter(self, parser):
        """Test empty frontmatter section."""
        content = """---
---

# Content after empty frontmatter"""

        frontmatter, body = parser.parse(content)

        assert frontmatter == {}
        assert body.strip() == "# Content after empty frontmatter"

    def test_malformed_yaml_recovery(self, parser):
        """Test recovery from malformed YAML."""
        content = """---
title: Test Document
author: John Doe: Senior Developer
published: true
invalid_yaml: [broken
---

Content here."""

        frontmatter, body = parser.parse(content)

        # Should still extract what it can
        assert "title" in frontmatter
        assert frontmatter["title"] == "Test Document"
        assert "published" in frontmatter
        assert body.strip() == "Content here."

    def test_bom_detection_utf8(self, parser):
        """Test BOM detection for UTF-8."""
        content = (
            codecs.BOM_UTF8.decode("utf-8")
            + """---
title: Document with BOM
---

Content with BOM marker."""
        )

        frontmatter, body = parser.parse(content)

        assert frontmatter["title"] == "Document with BOM"
        assert body.strip() == "Content with BOM marker."
        assert parser.stats["bom_detected"] == 1

    def test_bom_detection_utf16(self, parser):
        """Test BOM detection for UTF-16."""
        content_with_bom = (
            codecs.BOM_UTF16_LE
            + """---
title: UTF-16 Document
---

UTF-16 content.""".encode("utf-16-le")
        )

        frontmatter, body = parser.parse(content_with_bom)

        assert frontmatter["title"] == "UTF-16 Document"
        assert body.strip() == "UTF-16 content."
        assert parser.stats["bom_detected"] == 1

    def test_alternative_delimiters(self, parser):
        """Test that only standard YAML delimiters are supported (KISS principle)."""
        # Non-YAML delimiters should not be parsed as frontmatter
        toml_content = """+++
title = "TOML Style"
+++

TOML content."""

        frontmatter, body = parser.parse(toml_content)
        # Should not parse TOML - return empty frontmatter and full body
        assert frontmatter == {}
        assert "+++" in body  # Body should contain the entire content

    def test_cross_platform_line_endings(self, parser):
        """Test handling of different line endings."""
        # Windows line endings
        content_windows = "---\r\ntitle: Windows Doc\r\n---\r\n\r\nWindows content."

        frontmatter, body = parser.parse(content_windows)

        assert frontmatter["title"] == "Windows Doc"
        assert "Windows content." in body

    def test_unicode_normalization(self, parser):
        """Test Unicode normalization."""
        # Content with non-normalized Unicode
        content = """---
title: Café
author: Naïve
---

Unicode content with accents: café, naïve."""

        frontmatter, body = parser.parse(content)

        assert frontmatter["title"] == "Café"
        assert frontmatter["author"] == "Naïve"
        assert "café" in body

    def test_excessive_whitespace_normalization(self, parser):
        """Test normalization of excessive whitespace."""
        content = """---
title: Spaced Document


author: Test Author
---



# Content


With lots of spaces."""

        frontmatter, body = parser.parse(content)

        assert frontmatter["title"] == "Spaced Document"
        assert frontmatter["author"] == "Test Author"
        # Should normalize excessive newlines
        assert "\n\n\n" not in body

    def test_yaml_type_conversion(self, parser):
        """Test YAML type conversion."""
        content = """---
title: Type Test
number: 42
float_num: 3.14
boolean_true: true
boolean_false: false
null_value: null
list_value:
  - item1
  - item2
---

Content."""

        frontmatter, body = parser.parse(content)

        assert isinstance(frontmatter["number"], int)
        assert frontmatter["number"] == 42
        assert isinstance(frontmatter["float_num"], float)
        assert frontmatter["float_num"] == 3.14
        assert isinstance(frontmatter["boolean_true"], bool)
        assert frontmatter["boolean_true"] is True
        assert isinstance(frontmatter["boolean_false"], bool)
        assert frontmatter["boolean_false"] is False
        assert frontmatter["null_value"] is None
        assert isinstance(frontmatter["list_value"], list)
        assert len(frontmatter["list_value"]) == 2

    def test_manual_yaml_extraction(self, parser):
        """Test manual extraction when YAML parsing fails."""
        # Completely broken YAML that should trigger manual extraction
        content = """---
title: Manual Extraction Test
author: Test Author
broken_syntax: [invalid yaml without closing bracket
another_field: valid_value
---

Manual extraction content."""

        frontmatter, body = parser.parse(content)

        # Should extract what it can manually
        assert "title" in frontmatter or "_parsing_error" in frontmatter
        assert body.strip() == "Manual extraction content."

    def test_encoding_error_handling(self, parser):
        """Test handling of encoding errors."""
        # Simulate encoding issues by providing invalid UTF-8 bytes
        with patch.object(parser, "detect_and_remove_bom") as mock_bom:
            mock_bom.return_value = ("corrupted content", None)

            frontmatter, body = parser.parse("corrupted content")

            # Should handle gracefully without crashing
            assert isinstance(frontmatter, dict)
            assert isinstance(body, str)

    def test_parser_statistics(self, parser):
        """Test parser statistics tracking."""
        initial_stats = parser.get_stats()
        assert initial_stats["parsed"] == 0
        assert initial_stats["failed"] == 0
        assert initial_stats["bom_detected"] == 0

        # Parse a document
        content = """---
title: Stats Test
---

Content."""

        parser.parse(content)

        stats = parser.get_stats()
        assert stats["parsed"] == 1
        assert stats["failed"] == 0

    def test_extremely_long_content(self, parser):
        """Test handling of very large documents."""
        # Create a large document
        large_content = "x" * 10000
        content = f"""---
title: Large Document
---

{large_content}"""

        frontmatter, body = parser.parse(content)

        assert frontmatter["title"] == "Large Document"
        assert len(body.strip()) == 10000

    def test_nested_yaml_structures(self, parser):
        """Test parsing of nested YAML structures."""
        content = """---
title: Nested Test
metadata:
  created: "2025-09-03"  # Quoted to prevent date conversion
  tags:
    - yaml
    - test
  config:
    enabled: true
    settings:
      timeout: 30
---

Nested content."""

        frontmatter, body = parser.parse(content)

        assert frontmatter["title"] == "Nested Test"
        assert frontmatter["metadata"]["created"] == "2025-09-03"
        assert "yaml" in frontmatter["metadata"]["tags"]
        assert frontmatter["metadata"]["config"]["settings"]["timeout"] == 30

    def test_special_characters_in_values(self, parser):
        """Test handling of special characters in YAML values."""
        content = """---
title: "Special Characters: @#$%^&*()"
description: 'Single quotes with "double quotes" inside'
url: https://example.com/path?param=value&other=123
---

Special character content."""

        frontmatter, body = parser.parse(content)

        assert "Special Characters: @#$%^&*()" in frontmatter["title"]
        assert '"double quotes"' in frontmatter["description"]
        assert frontmatter["url"] == "https://example.com/path?param=value&other=123"


@pytest.mark.unit
class TestGlobalParserFunctions:
    """Test global parser functions."""

    def test_global_parse_function(self, reset_stats):
        """Test global parse_frontmatter function."""
        content = """---
title: Global Test
---

Global content."""

        frontmatter, body = parse_frontmatter(content)

        assert frontmatter["title"] == "Global Test"
        assert body.strip() == "Global content."

    def test_global_stats_functions(self, reset_stats):
        """Test global statistics functions."""
        # Parse a document to generate stats
        parse_frontmatter("---\ntitle: Test\n---\nContent.")

        stats = get_parser_stats()
        assert stats["parsed"] >= 1

        # Reset stats
        reset_parser_stats()

        new_stats = get_parser_stats()
        assert new_stats["parsed"] == 0
        assert new_stats["failed"] == 0

    def test_multiple_documents_stats(self, reset_stats):
        """Test statistics across multiple document parsing."""
        documents = [
            "---\ntitle: Doc1\n---\nContent1",
            "---\ntitle: Doc2\n---\nContent2",
            "Just content without frontmatter",
            # Malformed YAML
            "---\ntitle: Doc3\nbroken: [invalid\n---\nContent3",
        ]

        for doc in documents:
            parse_frontmatter(doc)

        stats = get_parser_stats()
        assert stats["parsed"] == len(documents)
        # Should have some malformed YAML
        assert stats["malformed_yaml"] > 0


@pytest.mark.unit
class TestRealWorldScenarios:
    """Test real-world frontmatter parsing scenarios."""

    def test_finos_mitigation_format(self, parser):
        """Test parsing FINOS mitigation document format."""
        content = """---
sequence: 1
title: AI Data Leakage Prevention and Detection
doc-status: ACTIVE
type: mitigation
references:
  - ISO 42001
  - NIST AI RMF
---

## Purpose

This mitigation addresses data leakage prevention."""

        frontmatter, body = parser.parse(content)

        assert frontmatter["sequence"] == 1
        assert frontmatter["title"] == "AI Data Leakage Prevention and Detection"
        assert frontmatter["doc-status"] == "ACTIVE"
        assert frontmatter["type"] == "mitigation"
        assert isinstance(frontmatter["references"], list)
        assert "ISO 42001" in frontmatter["references"]
        assert body.startswith("## Purpose")

    def test_finos_risk_format(self, parser):
        """Test parsing FINOS risk document format."""
        content = """---
sequence: 10
title: Prompt Injection
doc-status: ACTIVE
references:
  - OWASP LLM Top 10
  - NIST AI RMF
---

## Summary

Prompt injection is a vulnerability..."""

        frontmatter, body = parser.parse(content)

        assert frontmatter["sequence"] == 10
        assert frontmatter["title"] == "Prompt Injection"
        assert frontmatter["doc-status"] == "ACTIVE"
        assert isinstance(frontmatter["references"], list)
        assert "OWASP LLM Top 10" in frontmatter["references"]
        assert body.startswith("## Summary")

    def test_github_flavored_frontmatter(self, parser):
        """Test GitHub-flavored frontmatter variations."""
        content = """---
layout: post
permalink: /test/
published: 2025-09-03 10:30:00 +0000
categories:
  - testing
  - yaml
tags: [frontmatter, github, markdown]
---

# GitHub Flavored Content

This simulates GitHub Pages frontmatter."""

        frontmatter, body = parser.parse(content)

        assert frontmatter["layout"] == "post"
        assert frontmatter["permalink"] == "/test/"
        assert isinstance(frontmatter["categories"], list)
        assert isinstance(frontmatter["tags"], list)
        assert "frontmatter" in frontmatter["tags"]
