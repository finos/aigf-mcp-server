"""``get_framework`` serves a document, not a dump of the YAML (#192).

Every framework body used to open with a "Framework Structure" list of the
file's top-level keys -- ``title``, ``description``, ``source_url`` presented
as "main sections" -- then the heading ``### entries: entries``, then the raw
YAML in a code fence. ``sections`` counted the top-level keys: 4 for a
framework of 306 articles.

All 13 live files have one shape: a title, a description, usually a
``source_url``, and ``entries`` mapping an id to a title, a url and a few
other fields. Four of them group their entries under YAML comments. These pin
how that shape is written out, and that a file of any other shape is served
whole rather than half-rendered.
"""

from __future__ import annotations

from typing import Any

import pytest

from finos_mcp.content.parse import parse_yaml_document, yaml_title_from_document
from finos_mcp.documents import format as format_module
from finos_mcp.documents import tools as document_tools
from finos_mcp.documents.format import _framework_document

_FRAMEWORK = """\
title: "SR 11-7: Model Risk Management"
description: "Supervisory guidance on model risk management."
source_url: "https://example.invalid/sr1107.htm"

entries:
  overview:
    title: 'SR 11-7: Overview'
    url: https://example.invalid/overview.htm

  # Section: Model Validation
  s3:
    title: 'SR 11-7 S3: Model Validation'
    url: https://example.invalid/s3.pdf
    issuer: FRB
    description: >
      Validation is the set of processes
      intended to verify that models perform as expected.
  s3-eval:
    title: Evaluation of conceptual soundness
    url: https://example.invalid/s3.pdf
    superseded_by: s3
"""

_RENDERED = """\
# SR 11-7: Model Risk Management

Supervisory guidance on model risk management.

Source: https://example.invalid/sr1107.htm

- **overview**: SR 11-7: Overview
  https://example.invalid/overview.htm

## Section: Model Validation

- **s3**: SR 11-7 S3: Model Validation
  https://example.invalid/s3.pdf
  issuer: FRB
  Validation is the set of processes intended to verify that models perform as expected.
- **s3-eval**: Evaluation of conceptual soundness
  https://example.invalid/s3.pdf
  superseded_by: s3"""


def _render(document: str, title: str = "T") -> str:
    return _framework_document(document, title).body


@pytest.mark.unit
def test_a_framework_is_written_out_as_a_document() -> None:
    """Title, description, source, then each entry with its id, name and text."""
    assert _render(_FRAMEWORK, "SR 11-7: Model Risk Management") == _RENDERED


@pytest.mark.unit
@pytest.mark.parametrize(
    "generated",
    ["entries", "Framework Structure", "main sections", "Raw YAML", "```", "title"],
)
def test_nothing_is_written_that_the_framework_did_not_say(generated: str) -> None:
    """No heading from a container key, no key list, no copy of the YAML."""
    assert generated not in _render(_FRAMEWORK, "SR 11-7: Model Risk Management")


@pytest.mark.unit
def test_entry_count_counts_the_entries() -> None:
    """Not the top-level keys, which were 4 for every framework that has a source."""
    assert _framework_document(_FRAMEWORK, "T").entries == 3


async def _served_by_the_tool(monkeypatch: pytest.MonkeyPatch, document: str) -> Any:
    """`get_framework` over a discovery and a content service that hold one file."""
    from finos_mcp.content.discovery import (
        DiscoveryResult,
        DiscoveryServiceManager,
        GitHubFileInfo,
    )

    class _Discovery:
        async def discover_content(self) -> DiscoveryResult:
            return DiscoveryResult(
                mitigation_files=[],
                risk_files=[],
                framework_files=[GitHubFileInfo(filename="sr11-7.yml")],
                source="github_api",
            )

    class _Service:
        async def get_document(self, _doc_type: str, _filename: str) -> dict[str, str]:
            return {"content": document}

    async def _discovery(_self: object) -> _Discovery:
        return _Discovery()

    async def _get_service() -> _Service:
        return _Service()

    monkeypatch.setattr(DiscoveryServiceManager, "get_discovery_service", _discovery)
    monkeypatch.setattr(document_tools, "get_service", _get_service)
    return await document_tools.get_framework("sr11-7")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_the_tool_serves_that_document_and_counts_its_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    served = await _served_by_the_tool(monkeypatch, _FRAMEWORK)

    assert served.content == _RENDERED
    assert served.entry_count == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_the_tool_counts_no_entries_in_a_file_it_serves_as_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Three top-level lines with a colon, which is what used to be counted."""
    document = "title: T\nannex:\n  title: X\nnotes: [a, b]\n"

    served = await _served_by_the_tool(monkeypatch, document)

    assert served.content == f"# T\n\n```yaml\n{document}\n```"
    assert served.entry_count == 0


@pytest.mark.unit
class TestTheCommentAboveAnEntryIsItsHeading:
    """A comment is the only grouping these files have, and a parse drops it."""

    def test_a_comment_over_several_lines_is_one_heading(self) -> None:
        document = (
            "entries:\n"
            "  # ------------------------------------\n"
            "  # Tier 3 - Federal guidance (analogous; not\n"
            "  # directly binding)\n"
            "  # ------------------------------------\n"
            "\n"
            "  cppa:\n"
            "    title: Privacy bill\n"
        )

        assert _render(document).splitlines()[2:] == [
            "## Tier 3 - Federal guidance (analogous; not directly binding)",
            "",
            "- **cppa**: Privacy bill",
        ]

    def test_a_rule_alone_is_not_a_heading(self) -> None:
        document = "entries:\n  # ----------\n  a:\n    title: One\n"

        assert "#" not in _render(document)[1:]

    def test_a_quoted_or_numeric_id_still_finds_its_comment(self) -> None:
        document = (
            "entries:\n"
            "  # First\n"
            "  '2-1':\n"
            "    title: One\n"
            "  # Second\n"
            "  2024:\n"
            "    title: Two\n"
        )

        rendered = _render(document)

        assert rendered.index("## First") < rendered.index("- **2-1**: One")
        assert rendered.index("## Second") < rendered.index("- **2024**: Two")

    def test_a_hash_line_inside_an_entry_is_text_not_a_heading(self) -> None:
        """The last line of a block scalar sits directly above the next id."""
        document = (
            "entries:\n"
            "  a:\n"
            "    description: |\n"
            "      Run this:\n"
            "      # not a comment\n"
            "  b:\n"
            "    title: Two\n"
        )

        rendered = _render(document)

        assert "Run this: # not a comment" in rendered
        assert "## " not in rendered

    def test_a_comment_elsewhere_in_the_file_is_not_a_heading(self) -> None:
        document = (
            "# About this file\n"
            "title: T\n"
            "entries:\n"
            "  a:\n"
            "    title: One  # trailing\n"
            "    # inside the entry\n"
            "    url: https://example.invalid/a\n"
        )

        assert "#" not in _render(document)[1:]


@pytest.mark.unit
class TestACommentThatIsNotAHeading:
    def test_the_comment_after_the_last_entry_closes_the_document(self) -> None:
        """`canada-regulations` ends with a note on a bill that has no entry."""
        document = (
            "entries:\n"
            "  a:\n"
            "    title: One\n"
            "\n"
            "  # NOTE: Bill C-27 died on the order paper.\n"
            "  # Re-add an entry if a successor is introduced.\n"
        )

        assert _render(document) == (
            "# T\n\n- **a**: One\n\nNOTE: Bill C-27 died on the order paper. "
            "Re-add an entry if a successor is introduced."
        )

    def test_a_comment_at_the_depth_of_a_field_is_not_the_next_heading(self) -> None:
        document = (
            "entries:\n"
            "  a:\n"
            "    title: One\n"
            "    # about the entry above\n"
            "  b:\n"
            "    title: Two\n"
        )

        assert _render(document) == "# T\n\n- **a**: One\n- **b**: Two"

    def test_a_comment_straight_after_a_block_of_text_is_a_heading(self) -> None:
        document = (
            "entries:\n"
            "  a:\n"
            "    description: |\n"
            "      Text.\n"
            "  # Second group\n"
            "  b:\n"
            "    title: Two\n"
        )

        assert _render(document) == (
            "# T\n\n- **a**\n  Text.\n\n## Second group\n\n- **b**: Two"
        )

    def test_a_comment_at_another_depth_does_not_hide_the_one_above_it(self) -> None:
        document = (
            "entries:\n"
            "  a:\n"
            "    title: One\n"
            "  # Section A\n"
            "      # an aside\n"
            "  b:\n"
            "    title: Two\n"
        )

        assert _render(document) == (
            "# T\n\n- **a**: One\n\n## Section A\n\n- **b**: Two"
        )

    def test_the_last_line_of_a_quoted_value_is_not_a_comment(self) -> None:
        document = (
            "entries:\n"
            "  a:\n"
            '    title: "One\n'
            '  # still the title"\n'
            "  b:\n"
            "    title: Two\n"
        )

        assert _render(document) == (
            "# T\n\n- **a**: One # still the title\n- **b**: Two"
        )

    def test_an_id_written_twice_keeps_the_comment_above_each(self) -> None:
        """A parse keeps one of them; the file wrote two."""
        document = (
            "entries:\n"
            "  # First\n"
            "  a:\n"
            "    title: One\n"
            "  b:\n"
            "    title: Two\n"
            "  # Second\n"
            "  a:\n"
            "    title: Three\n"
        )

        assert _render(document).splitlines()[2:] == [
            "## First",
            "",
            "- **a**: One",
            "- **b**: Two",
            "",
            "## Second",
            "",
            "- **a**: Three",
        ]
        assert _framework_document(document, "T").entries == 3


@pytest.mark.unit
class TestAnEntryThatIsCommentedOut:
    """It is YAML the file no longer says, not a name for the entries below.

    ``# b:`` over ``#   title: old`` was written ``## b: title: old`` (#214).
    """

    def test_it_is_not_a_heading(self) -> None:
        document = (
            "entries:\n"
            "  a:\n"
            "    title: One\n"
            "  # b:\n"
            "  #   title: old\n"
            "  #   url: https://example.invalid/b\n"
            "  #   issuer: OSFI\n"
            "  c:\n"
            "    title: Three\n"
        )

        assert _render(document) == "# T\n\n- **a**: One\n- **c**: Three"

    def test_however_its_lines_are_marked(self) -> None:
        document = (
            "entries:\n"
            "  ## b:  \n"
            "  ##   url: https://example.invalid/b  \n"
            "  ##   title: old\n"
            "  c:\n"
            "    title: Three\n"
        )

        assert _render(document) == "# T\n\n- **c**: Three"

    def test_the_comment_beside_it_still_is(self) -> None:
        document = (
            "entries:\n"
            "  # Tier 2\n"
            "\n"
            "  # b:\n"
            "  #   title: old\n"
            "  #   url: u\n"
            "  # ----------\n"
            "  # Guidance\n"
            "  c:\n"
            "    title: Three\n"
        )

        assert _render(document) == "# T\n\n## Tier 2 Guidance\n\n- **c**: Three"

    def test_several_of_them_are_not_a_heading(self) -> None:
        document = (
            "entries:\n"
            "  #b:\n"
            "  #  title: old\n"
            "  #  url: u\n"
            "  #c:\n"
            "  #  url: u\n"
            "  #  title: older\n"
            "  d:\n"
            "    title: Four\n"
        )

        assert _render(document) == "# T\n\n- **d**: Four"

    def test_a_comment_at_another_depth_ends_it(self) -> None:
        document = (
            "entries:\n"
            "  # Tier 2\n"
            "      # an aside\n"
            "  # b:\n"
            "  #   title: old\n"
            "  #   url: u\n"
            "  c:\n"
            "    title: Three\n"
        )

        assert _render(document) == "# T\n\n## Tier 2\n\n- **c**: Three"

    def test_a_comment_of_brackets_is_a_comment(self) -> None:
        """Parsed, 600 of them overran the stack and the file was served fenced."""
        nested = "[" * 600 + "]" * 600
        document = f"entries:\n  # a: {nested}\n  x:\n    title: One\n"

        assert _render(document) == f"# T\n\n## a: {nested}\n\n- **x**: One"

    def test_it_does_not_close_the_document(self) -> None:
        document = (
            "entries:\n  a:\n    title: One\n  # b:\n  #   title: old\n  #   url: u\n"
        )

        assert _render(document) == "# T\n\n- **a**: One"

    @pytest.mark.parametrize(
        "comment",
        [
            "Section: Model Validation",
            "NOTE: verify annually",
            "Tier 1:",
            "Tier 1:\n  # Prudential",
            "Scope: banks\n  # Issuer: OSFI",
            "Tier 1:\n  #   Scope: banks",
            "Tier 1:\n  #   Prudential: capital\n  #   Conduct: consumer duty",
            "Annex:\n  #   note: x\n  # b:\n  #   title: old\n  #   url: u",
            "b:\n  #   title: old\n  #   url: u\n  # c:\n  #   title: older",
            "Superseded:\n  #   see: https://example.invalid/new",
            "See:\n  #   url: https://example.invalid/guide",
            "NOTE:\n  #   title: fields below were renamed in 2025",
            "Tier 1:\n  #   title: Prudential\n  #   url: https://example.invalid/t",
            "Tier 1: {see: annex}",
            "b:\n  #   title: old\n  #   url: u\n  # and a remark",
            "b:\n  #   title: old\n  #   url: u\n  #   and a wrapped line",
            "title: old\n  # url: u",
            "Scope: banks\n  #   title: old\n  #   url: u",
            "  Scope:\n  # title: old\n  # url: u",
            # A capitalised word is a label, whatever is under it (#263).
            "See:\n  #   title: NIST AI RMF\n  #   url: https://example.invalid/rmf",
            "NOTE:\n  #   title: renamed\n  #   url: https://example.invalid/n",
        ],
    )
    def test_a_comment_with_a_colon_in_it_is_still_a_heading(
        self, comment: str
    ) -> None:
        """Three live headings are ``Section: ...``, and a label over a field is one.

        Read as YAML, ``Tier 1:`` over ``Scope: banks`` is an entry, and the
        heading was dropped with nothing to show for it.
        """
        document = f"entries:\n  # {comment}\n  a:\n    title: One\n"
        heading = " ".join(comment.replace("#", "").split())

        assert _render(document) == f"# T\n\n## {heading}\n\n- **a**: One"


@pytest.mark.unit
class TestAValueIsWrittenAsTheFileWroteIt:
    """Not as the value it parses to."""

    @pytest.mark.parametrize(
        "written", ["1.10", "010", "0x10", "1:30", "no", "2024-05-01", "~x"]
    )
    def test_a_value_that_parses_to_something_else(self, written: str) -> None:
        document = f"entries:\n  a:\n    title: One\n    field: {written}\n"

        assert _render(document) == f"# T\n\n- **a**: One\n  field: {written}"

    def test_ids_that_parse_to_the_same_number_are_separate_entries(self) -> None:
        document = (
            'entries:\n  "5.1":\n    title: Policy\n'
            "  5.10:\n    title: Tenth\n  yes:\n    title: Word\n"
        )

        assert _render(document) == (
            "# T\n\n- **5.1**: Policy\n- **5.10**: Tenth\n- **yes**: Word"
        )

    def test_an_id_of_asterisks_does_not_close_its_own_emphasis(self) -> None:
        """`- *****` is a rule inside the list item."""
        document = 'entries:\n  "*":\n    title: One\n  "* *":\n    url: u\n'

        assert _render(document) == "# T\n\n- **\\***: One\n- **\\* \\***\n  u"


@pytest.mark.unit
def test_a_file_that_says_far_more_than_it_is_long_is_served_as_written() -> None:
    """An alias repeats a value at no cost to the file.

    Written out, 4000 aliases of a 100KB value were 400MB from a file of
    200KB, built before the response size was checked.
    """
    words = "word " * 2000
    aliases = "".join(f"  e{n}:\n    description: *words\n" for n in range(150))
    document = f'words: &words "{words}"\nentries:\n{aliases}'
    assert len(document) < 20_000 and len(words) * 150 > format_module._LONGEST_BODY

    served = _framework_document(document, "T")

    assert served == (f"# T\n\n```yaml\n{document}\n```", 0)


@pytest.mark.unit
def test_an_alias_repeated_outside_the_entries_counts_the_same() -> None:
    words = "word " * 2000
    aliases = "".join(f"k{n}: *words\n" for n in range(150))
    document = f'words: &words "{words}"\n{aliases}'

    assert _framework_document(document, "T").body.startswith("# T\n\n```yaml\n")


@pytest.mark.unit
def test_what_an_alias_repeats_is_not_walked_past_the_longest_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Counting it all first took 25 seconds and 1.7GB on a file of 220KB."""
    fields = ", ".join(f"k{n}: v" for n in range(100))
    aliases = "".join(f"  e{n}: *m\n" for n in range(400))
    document = f"entries:\n  a: &m {{{fields}}}\n{aliases}"
    walked: list[int] = []
    fields_of = format_module._fields

    def _counted(node):
        walked.append(1)
        return fields_of(node)

    monkeypatch.setattr(format_module, "_LONGEST_BODY", 5_000)
    monkeypatch.setattr(format_module, "_fields", _counted)

    assert _framework_document(document, "T").entries == 0
    assert len(walked) < 40, "every alias was walked before the file was refused"


@pytest.mark.unit
def test_a_value_reused_through_an_alias_is_written_out() -> None:
    """Thirty entries naming one issuer say more than the file is long."""
    reused = "".join(f"  e{n}:\n    issuer: *i\n" for n in range(30))
    document = (
        f"entries:\n  a:\n    issuer: &i Canadian Securities Administrators\n{reused}"
    )

    served = _framework_document(document, "T")

    assert served.entries == 31
    assert served.body.count("issuer: Canadian Securities Administrators") == 31


@pytest.mark.unit
def test_only_an_entry_is_a_list_item() -> None:
    """`entry_count` is the number of them, and a reader counts the same."""
    document = "title: T\nversion: 2\nlicense: CC\nentries:\n  a:\n    title: One\n"

    served = _framework_document(document, "T")

    assert served.body == "# T\n\nversion: 2\n\nlicense: CC\n\n- **a**: One"
    assert served.entries == served.body.count("- **") == 1


@pytest.mark.unit
def test_entries_with_nothing_under_it_is_a_framework_with_none() -> None:
    assert _framework_document("title: T\nentries:\n", "T") == ("# T", 0)


@pytest.mark.unit
class TestWhatIsLeftOut:
    def test_a_field_with_no_value_is_not_written(self) -> None:
        """``url:`` with nothing after it parses to None, which is not a link."""
        document = "entries:\n  a:\n    title: One\n    url:\n    issuer:\n"

        assert _render(document) == "# T\n\n- **a**: One"

    @pytest.mark.parametrize("null", ["~", "null", "Null"])
    def test_a_null_is_no_value_however_it_is_spelled(self, null: str) -> None:
        document = f"entries:\n  a:\n    title: One\n    url: {null}\n"

        assert _render(document) == "# T\n\n- **a**: One"

    @pytest.mark.parametrize(
        "document",
        [
            "note: !!null kept secret\n",
            "entries:\n  a:\n    note: !!null kept secret\n",
        ],
    )
    def test_text_tagged_as_a_null_is_still_text(self, document: str) -> None:
        """A parse gives None for it; the file wrote two words (#214)."""
        assert "note: kept secret" in _render(document)

    @pytest.mark.parametrize(
        "document",
        ["entries:\n  a: !!null kept secret\n", "entries: !!null kept secret\n"],
    )
    def test_text_tagged_as_a_null_is_not_an_empty_mapping(self, document: str) -> None:
        assert _render(document) == f"# T\n\n```yaml\n{document}\n```"

    def test_a_null_of_spaces_is_still_a_null(self) -> None:
        document = 'entries:\n  a: !!null " "\n  b:\n    note: !!null " "\n'

        assert _render(document) == "# T\n\n- **a**\n- **b**"

    def test_an_entry_with_nothing_under_it_is_its_id(self) -> None:
        document = "entries:\n  a:\n  b: {}\n  c:\n    title: Three\n"

        assert _render(document) == "# T\n\n- **a**\n- **b**\n- **c**: Three"

    def test_an_entry_without_a_title_is_its_id(self) -> None:
        document = "entries:\n  a:\n    url: https://example.invalid/a\n"

        assert _render(document) == "# T\n\n- **a**\n  https://example.invalid/a"

    def test_a_url_that_is_not_text_is_labelled_not_presented_as_a_link(self) -> None:
        document = "entries:\n  a:\n    title: One\n    url: 42\n"

        assert _render(document) == "# T\n\n- **a**: One\n  url: 42"

    def test_a_source_that_is_not_text_is_labelled_too(self) -> None:
        assert _render("source_url: 42\n") == "# T\n\nsource_url: 42"

    def test_the_declared_title_is_not_repeated_under_the_heading(self) -> None:
        assert _render("title: The Name\n", "The Name") == "# The Name"

    @pytest.mark.parametrize(
        "title",
        ["The N\u200bame", "The Na\u202eme", "The Nam\u00ade", '"The  Name"'],
    )
    def test_a_title_the_heading_tidied_is_not_repeated_either(
        self, title: str
    ) -> None:
        """The heading drops a character nobody sees; it is the same title.

        A zero-width space in it and the body read ``# AB`` over
        ``title: A B`` (#214).
        """
        document = f"title: {title}\n"
        declared = yaml_title_from_document(parse_yaml_document(document))
        assert declared == "The Name", "the fixture must be a usable title"

        assert _render(document, declared) == "# The Name"

    def test_a_title_the_heading_could_not_use_is_still_shown(self) -> None:
        """A rejected title falls back to the name map; its text is not lost."""
        document = "title: |\n  Name\n  second line\n"

        assert _render(document, "Fallback") == (
            "# Fallback\n\ntitle: Name second line"
        )

    def test_another_top_level_value_is_shown_under_its_key(self) -> None:
        document = "title: T\nversion: 2\ndescription: Words.\n"

        assert _render(document) == "# T\n\nWords.\n\nversion: 2"

    def test_a_long_description_is_not_cut(self) -> None:
        words = "word " * 400
        document = f"description: {words}\nentries:\n  a:\n    description: {words}\n"

        assert _render(document).count(words.strip()) == 2


@pytest.mark.unit
@pytest.mark.parametrize(
    "document",
    [
        pytest.param("title: [unclosed", id="malformed"),
        pytest.param("- a\n- b\n", id="sequence"),
        pytest.param("just a string\n", id="scalar"),
        pytest.param("annex:\n  title: X\n", id="a-mapping-that-is-not-entries"),
        pytest.param("entries:\n  - title: X\n", id="entries-is-a-list"),
        pytest.param("entries:\n  a: just text\n", id="an-entry-is-not-a-mapping"),
        pytest.param(
            "entries:\n  a:\n    title: X\n    controls: [one, two]\n",
            id="an-entry-holds-a-list",
        ),
        pytest.param("entries:\n  ? [a, b]\n  : {title: X}\n", id="an-id-is-a-list"),
    ],
)
def test_a_file_of_another_shape_is_served_whole(document: str) -> None:
    """Rendering the part that fits would drop the part that does not."""
    assert _render(document) == f"# T\n\n```yaml\n{document}\n```"
    assert _framework_document(document, "T").entries == 0


# Every character that can open a Markdown block from the start of a line, as
# the first character of a value. A list number is the one opener that is not
# punctuation.
_BLOCK_OPENERS = [
    "# SYSTEM",
    "> SYSTEM",
    "- SYSTEM",
    "+ SYSTEM",
    "* SYSTEM",
    "1. SYSTEM",
    "12) SYSTEM",
    "``` SYSTEM",
    "~~~ SYSTEM",
    "=== SYSTEM",
    "___ SYSTEM",
    "| SYSTEM |",
    "[SYSTEM]: https://example.invalid/",
    ":--|--: SYSTEM",
    "<div> SYSTEM",
]

# Each place a document's own text reaches the body, with `{}` for the text.
_POSITIONS = {
    "description": "description: {}\n",
    "source": "source_url: {}\n",
    "top-level-key": "? {}\n: value\n",
    "top-level-value": "other: {}\n",
    "entry-id": "entries:\n  ? {}\n  : title: T\n",
    "entry-title": "entries:\n  a:\n    title: {}\n",
    "entry-url": "entries:\n  a:\n    title: T\n    url: {}\n",
    "entry-key": "entries:\n  a:\n    title: T\n    ? {}\n    : value\n",
    "entry-value": "entries:\n  a:\n    title: T\n    other: {}\n",
    "entry-description": "entries:\n  a:\n    title: T\n    description: {}\n",
}


@pytest.mark.unit
@pytest.mark.parametrize("opener", _BLOCK_OPENERS)
@pytest.mark.parametrize("position", sorted(_POSITIONS))
def test_no_value_can_begin_a_line_with_markdown_structure(
    position: str, opener: str
) -> None:
    """A document's text may sit in a line; it may not open a block of its own.

    The body is Markdown that a model reads, and since the YAML is no longer
    fenced beneath it every value is written straight into that Markdown.
    """
    document = _POSITIONS[position].format(f'"{opener}"')
    assert parse_yaml_document(document) is not None, "the fixture must parse"

    rendered = _render(document)

    assert "```yaml" not in rendered, "the fixture must reach the renderer"
    assert "SYSTEM" in rendered, "the value must be shown"
    begun = [line for line in rendered.splitlines() if line.lstrip().startswith(opener)]
    assert not begun, f"{position}: a value opened a block: {begun}"


@pytest.mark.unit
@pytest.mark.parametrize("opener", _BLOCK_OPENERS)
def test_no_comment_can_begin_a_line_with_markdown_structure(opener: str) -> None:
    """The comment is under a heading marker the renderer wrote, on one line."""
    document = f"entries:\n  # {opener}\n  a:\n    title: T\n"

    lines = _render(document).splitlines()

    assert any("SYSTEM" in line for line in lines), "the comment must be shown"
    assert [line for line in lines if "SYSTEM" in line and line[:3] != "## "] == []


@pytest.mark.unit
@pytest.mark.parametrize("opener", _BLOCK_OPENERS)
def test_no_closing_comment_can_begin_a_line_with_markdown_structure(
    opener: str,
) -> None:
    """The comment after the last entry is a paragraph, under no marker."""
    document = f"entries:\n  a:\n    title: T\n  # {opener}\n"

    lines = _render(document).splitlines()

    assert any("SYSTEM" in line for line in lines), "the comment must be shown"
    assert [line for line in lines if line.startswith(opener.lstrip("# "))] == []


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    [
        '"Quoted" guidance',
        "(EU) 2024/1689",
        "[Draft] guidance",
        "2024 guidance",
        "3.5 controls",
    ],
)
def test_ordinary_text_is_left_as_written(value: str) -> None:
    """Only a character that would open a block is escaped."""
    document = f"description: '{value}'\n"

    assert _render(document) == f"# T\n\n{value}"
