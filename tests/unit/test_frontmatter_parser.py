"""
Unit tests for frontmatter parser functionality.

Tests comprehensive edge cases including malformed YAML, BOM markers,
encoding issues, and various delimiter styles.
"""

import codecs
import datetime
import sys
from unittest.mock import patch

import pytest
import yaml

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

    def test_malformed_yaml_gives_no_metadata(self, parser):
        """Malformed frontmatter is not repaired line by line (#359)."""
        content = """---
title: Test Document
author: John Doe: Senior Developer
published: true
invalid_yaml: [broken
---

Content here."""

        frontmatter, body = parser.parse(content)

        assert set(frontmatter) == {"_parsing_error", "_raw_frontmatter"}
        assert body == "Content here."

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

    def test_excessive_whitespace_is_kept(self, parser):
        """Blank lines in frontmatter and body do not stop the parse."""
        content = """---
title: Spaced Document


author: Test Author
---



# Content


With lots of spaces."""

        frontmatter, body = parser.parse(content)

        assert frontmatter["title"] == "Spaced Document"
        assert frontmatter["author"] == "Test Author"
        # The body is served as written: its blank lines stay (#352).
        assert body == "# Content\n\n\nWith lots of spaces."

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

    @pytest.mark.parametrize("value", ["!!int x"])
    def test_a_value_safe_load_refuses_gives_no_metadata(self, parser, value):
        """safe_load raises ValueError or AttributeError here, not YAMLError.

        parse() caught it and served the raw frontmatter as the body (#359).
        """
        frontmatter, body = parser.parse(f"---\ntitle: A\nd: {value}\n---\nbody")

        assert set(frontmatter) == {"_parsing_error", "_raw_frontmatter"}
        assert body == "body"
        assert parser.get_stats()["malformed_yaml"] == 1

    @pytest.mark.parametrize("error", [ValueError, RecursionError, KeyError])
    def test_a_failed_step_raises_rather_than_serving_the_raw_text(self, parser, error):
        """It answered ({}, content): the whole document, frontmatter
        included, published as the body (#366). The old test mocked the step
        to succeed, so it never reached the handler."""
        with patch.object(parser, "detect_and_remove_bom", side_effect=error("broken")):
            with pytest.raises(error, match="broken"):
                parser.parse("---\ntitle: A\n---\nbody")

        assert parser.get_stats()["failed"] == 1

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


@pytest.mark.unit
class TestFrontmatterOnlyAtTheStart:
    """Frontmatter opens the document; a later pair of rules is body (#350)."""

    def test_two_rules_in_the_body_are_not_frontmatter(self, parser):
        content = "# Intro\n\nText\n\n---\n\nmiddle: x\n\n---\n\nEnd"

        frontmatter, body = parser.parse(content)

        assert frontmatter == {}
        assert body == content

    def test_frontmatter_then_rules_in_the_body(self, parser):
        content = "---\ntitle: A\n---\n\nText\n\n---\n\nmiddle: x\n\n---\n\nEnd"

        frontmatter, body = parser.parse(content)

        assert frontmatter == {"title": "A"}
        assert body == "Text\n\n---\n\nmiddle: x\n\n---\n\nEnd"


@pytest.mark.unit
class TestFrontmatterThatEndsTheDocument:
    """A closing `---` may be the last line, with nothing after it (#351)."""

    def test_a_document_that_is_only_frontmatter(self, parser):
        frontmatter, body = parser.parse("---\ntitle: A\n---")

        assert frontmatter == {"title": "A"}
        assert body == ""

    def test_trailing_whitespace_after_the_closing_rule(self, parser):
        frontmatter, body = parser.parse("---\ntitle: A\n---  \n\n")

        assert frontmatter == {"title": "A"}
        assert body == ""

    def test_a_longer_rule_does_not_close_frontmatter(self, parser):
        frontmatter, _ = parser.parse("---\ntitle: A\n----")

        assert frontmatter == {}


@pytest.mark.unit
class TestTheBodyIsServedAsWritten:
    """The parser does not rewrite the characters or blank lines of a body (#352)."""

    def test_compatibility_characters_and_code_block_blank_lines(self, parser):
        body = "```\na\n\n\n\nb\n```\nx\u00b2 \ufb01 \uff21"

        _, parsed = parser.parse("---\ntitle: A\n---\n" + body)

        assert parsed == body

    @pytest.mark.parametrize(
        "head", ["---\ntitle: A\n---\n", "---\ntitle: A\n---\n\n  \n", ""]
    )
    def test_the_first_line_keeps_its_indentation(self, parser, head):
        """An indented code block that opens a body stays code (#370).

        Only the blank lines above it go.
        """
        body = "    indented code\n    more code\n\nprose"

        _, parsed = parser.parse(head + body)

        assert parsed == body

    def test_line_endings_are_still_normalized(self, parser):
        _, parsed = parser.parse("---\r\ntitle: A\r\n---\r\none\r\ntwo\rthree")

        assert parsed == "one\ntwo\nthree"


@pytest.mark.unit
class TestUtf32ByteOrderMarks:
    """A UTF-32 BOM is not read as the UTF-16 BOM it starts with (#353)."""

    @pytest.mark.parametrize("encoding", ["utf-32", "utf-32-le", "utf-32-be"])
    def test_utf32_bytes_decode_as_utf32(self, parser, encoding):
        text = "---\ntitle: A\n---\nbody"
        raw = text.encode(encoding)
        if encoding != "utf-32":
            bom = (
                codecs.BOM_UTF32_LE if encoding.endswith("le") else codecs.BOM_UTF32_BE
            )
            raw = bom + raw

        frontmatter, body = parser.parse(raw)

        assert frontmatter == {"title": "A"}
        assert body == "body"


@pytest.mark.unit
class TestDeeplyNestedFrontmatter:
    """Nesting deep enough to exhaust the stack is unparseable, not fatal (#354)."""

    def test_the_body_is_still_served(self, parser):
        nesting = "[" * (sys.getrecursionlimit() * 5)

        frontmatter, body = parser.parse(f"---\nt: {nesting}\n---\nbody")

        assert body == "body"
        assert "recursion" in frontmatter["_parsing_error"]
        assert parser.get_stats()["malformed_yaml"] == 1


@pytest.mark.unit
class TestMalformedFrontmatterIsNotRepaired:
    """No line-by-line repair: it returned wrong data as a success (#359)."""

    def test_a_block_scalar_does_not_become_keys(self, parser):
        result = parser.parse_yaml_safely(
            "title: T\ndescription: |\n  Note: a\n  b\nbad: ["
        )

        assert set(result) == {"_parsing_error", "_raw_frontmatter"}

    def test_a_nested_mapping_is_not_flattened(self, parser):
        result = parser.parse_yaml_safely("parent:\n  child: a: b\n  other: c")

        assert set(result) == {"_parsing_error", "_raw_frontmatter"}


@pytest.mark.unit
def test_a_reset_restores_every_counter_a_new_parser_has(reset_stats):
    """The reset and the constructor share one list of counters (#358)."""
    parse_frontmatter("---\ntitle: A\n---\nbody")

    reset_parser_stats()

    assert get_parser_stats() == FrontmatterParser().get_stats()


@pytest.mark.unit
class TestFormatCharactersBeforeTheFrontmatter:
    """A zero-width character before `---` does not hide the frontmatter (#362)."""

    @pytest.mark.parametrize(
        "lead", ["\ufeff", "\ufeff\ufeff", "\u200b", "\u2060", "\ufeff \u200b\n"]
    )
    def test_the_frontmatter_is_still_read(self, parser, lead):
        frontmatter, body = parser.parse(f"{lead}---\ntitle: A\n---\nbody")

        assert frontmatter == {"title": "A"}
        assert body == "body"

    @pytest.mark.parametrize("mark", ["\u200f", "\u202b", "\u2067"])
    def test_a_document_without_frontmatter_keeps_its_direction_mark(
        self, parser, mark
    ):
        frontmatter, body = parser.parse(f"{mark}\u0645\u0631\u062d\u0628\u0627")

        assert frontmatter == {}
        assert body.startswith(mark)

    def test_a_rule_that_opens_a_document_is_not_frontmatter(self, parser):
        frontmatter, body = parser.parse("\u200f---\nbody text after a rule")

        assert frontmatter == {}
        assert body == "\u200f---\nbody text after a rule"

    def test_a_format_character_inside_the_body_is_kept(self, parser):
        _, body = parser.parse("---\ntitle: A\n---\nzero\u200bwidth")

        assert body == "zero\u200bwidth"


@pytest.mark.unit
@pytest.mark.parametrize("frontmatter", ["Just text", "- a\n- b", "42"])
def test_frontmatter_that_is_not_a_mapping_gives_no_metadata(parser, frontmatter):
    """Valid YAML, but no keys: nothing to invent a `content` key for (#363)."""
    metadata, body = parser.parse(f"---\n{frontmatter}\n---\nbody")

    assert set(metadata) == {"_parsing_error", "_raw_frontmatter"}
    assert "not a mapping" in metadata["_parsing_error"]
    assert parser.get_stats()["malformed_yaml"] == 1
    assert body == "body"


@pytest.mark.unit
def test_frontmatter_and_framework_documents_load_yaml_in_one_place(
    parser, monkeypatch
):
    """One catch around safe_load, not two copies that drift (#364)."""
    from finos_mcp.content import parse

    monkeypatch.setattr(parse, "_load_yaml", lambda text: (None, ValueError("one")))

    assert parse.parse_yaml_document("title: A") is None
    assert parser.parse_yaml_safely("title: A")["_parsing_error"] == "one"


@pytest.mark.unit
class TestAnImpossibleDateIsText:
    """One impossible date does not discard the other fields (#365)."""

    def test_the_title_beside_it_is_kept(self, parser):
        frontmatter, body = parser.parse(
            "---\ntitle: A\nlast_updated: 2024-02-30\n---\nbody"
        )

        assert frontmatter == {"title": "A", "last_updated": "2024-02-30"}
        assert body == "body"

    def test_a_tagged_value_that_is_no_timestamp_is_text(self, parser):
        frontmatter, _ = parser.parse(
            "---\ntitle: A\nreviewed: !!timestamp soon\n---\nb"
        )

        assert frontmatter == {"title": "A", "reviewed": "soon"}

    def test_a_real_date_is_still_a_date(self, parser):
        frontmatter, _ = parser.parse("---\nlast_updated: 2024-02-29\n---\nbody")

        assert frontmatter == {"last_updated": datetime.date(2024, 2, 29)}

    def test_a_framework_document_with_one_is_still_parsed(self):
        from finos_mcp.content.parse import parse_yaml_document

        assert parse_yaml_document("title: T\nreviewed: 2023-13-01") == {
            "title": "T",
            "reviewed": "2023-13-01",
        }

    def test_the_loader_is_still_safe(self):
        """_load_yaml uses yaml.load with a SafeLoader subclass; prove it."""
        from finos_mcp.content.parse import _load_yaml

        result, error = _load_yaml("x: !!python/object/apply:os.getcwd []")

        assert result is None
        assert isinstance(error, yaml.constructor.ConstructorError)
