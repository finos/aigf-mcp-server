"""``search_frameworks`` is a literal find: the phrase, whole words, catalog order.

It used to rank. A query absent as a phrase fell back to its longest single
word, and results were ordered by a match-quality signal. Neither could be
made accurate on a corpus that changes daily (#208), so the tool now claims
only what it can keep: every framework that says the phrase, in the order
``list_frameworks`` gives them, with the passage and a count.

Each corpus below is laid out so the removed behaviour gives a different
answer: the old ranker would reorder it, the old fallback would add to it, or
the old substring match would find more in it.

The file keeps its name because ``search/ranking.py`` kept its own.
"""

from __future__ import annotations

import pytest

from finos_mcp import fastmcp_server
from finos_mcp.documents.format import _framework_document
from finos_mcp.search import engine as _search_engine
from finos_mcp.search import ranking as search_ranking
from finos_mcp.search import tools as _search_tools

# Catalog order is neither the order of the counts nor its reverse, so any
# ordering by how often a framework says the phrase moves at least one entry.
_SAYS_THE_PHRASE = [
    ("a_says-it-once", "Reviewers may meet prompt injection in sampled outputs."),
    (
        "b_says-it-three-times",
        "Prompt-injection filtering. A firewall inspects for prompt injection, "
        "and blocks PROMPT_INJECTION payloads.",
    ),
    ("c_never-says-it", "Injection of a prompt is covered elsewhere."),
    ("d_says-it-twice", "Prompt injection is logged. Alert on prompt injection."),
]

# Every word of "data poisoning" appears in the first two, the phrase only in
# the third. The single-word fallback returned all three, phrase last-listed.
_WORDS_WITHOUT_THE_PHRASE = [
    ("a_token-data-only", "Retention of data across the estate must be logged."),
    ("b_token-poisoning-only", "Dependency poisoning of an upstream package."),
    ("c_body-has-phrase", "An attacker performs data poisoning of the index."),
]


def _stub_framework_corpus(
    monkeypatch, corpus: list[tuple[str, str]], entry_count: int = 1
) -> None:
    from finos_mcp.models import Framework, FrameworkContent, FrameworkList

    async def _list(*_args, **_kwargs):
        return FrameworkList(
            frameworks=[
                Framework(id=fid, name=fid, description="") for fid, _ in corpus
            ],
            total_count=len(corpus),
            source="github_api",
        )

    bodies = dict(corpus)

    async def _get(framework_id, *_args, **_kwargs):
        return FrameworkContent(
            framework_id=framework_id,
            title=framework_id,
            content=bodies[framework_id],
            entry_count=entry_count,
        )

    monkeypatch.setattr(_search_tools, "list_frameworks", _list)
    monkeypatch.setattr(_search_engine, "get_framework", _get)


@pytest.mark.unit
class TestTheToolIsALiteralFind:
    """The contract of #208, at the tool."""

    @pytest.mark.asyncio
    async def test_results_come_back_in_catalog_order(self, monkeypatch) -> None:
        _stub_framework_corpus(monkeypatch, _SAYS_THE_PHRASE)

        found = await _search_tools.search_frameworks(query="prompt injection", limit=5)

        assert [item.document_id for item in found.results] == [
            "a_says-it-once",
            "b_says-it-three-times",
            "d_says-it-twice",
        ]

    @pytest.mark.asyncio
    async def test_each_result_says_how_often_the_framework_says_it(
        self, monkeypatch
    ) -> None:
        """Every spelling counts: hyphenated, spaced, underscored, any case."""
        _stub_framework_corpus(monkeypatch, _SAYS_THE_PHRASE)

        found = await _search_tools.search_frameworks(query="prompt injection", limit=5)

        assert [item.occurrences for item in found.results] == [1, 3, 2]

    @pytest.mark.asyncio
    async def test_words_of_the_query_apart_are_not_a_match(self, monkeypatch) -> None:
        _stub_framework_corpus(monkeypatch, _WORDS_WITHOUT_THE_PHRASE)

        found = await _search_tools.search_frameworks(query="data poisoning", limit=5)

        assert [item.document_id for item in found.results] == ["c_body-has-phrase"]
        assert found.total_found == 1

    @pytest.mark.asyncio
    async def test_a_phrase_no_framework_says_finds_nothing(self, monkeypatch) -> None:
        """Both words are in the corpus; the phrase is not."""
        _stub_framework_corpus(monkeypatch, _WORDS_WITHOUT_THE_PHRASE)

        found = await _search_tools.search_frameworks(query="poisoning data", limit=5)

        assert found.results == []
        assert found.total_found == 0

    @pytest.mark.asyncio
    async def test_limit_takes_the_first_listed_and_total_counts_them_all(
        self, monkeypatch
    ) -> None:
        _stub_framework_corpus(monkeypatch, _SAYS_THE_PHRASE)

        found = await _search_tools.search_frameworks(query="prompt injection", limit=2)

        assert [item.document_id for item in found.results] == [
            "a_says-it-once",
            "b_says-it-three-times",
        ]
        assert found.total_found == 3

    @pytest.mark.asyncio
    async def test_the_result_quotes_the_text_as_the_framework_wrote_it(
        self, monkeypatch
    ) -> None:
        _stub_framework_corpus(monkeypatch, _SAYS_THE_PHRASE)

        found = await _search_tools.search_frameworks(query="prompt injection", limit=5)

        assert found.results[1].content.startswith("Prompt-injection filtering.")


def _served(document: str) -> str:
    """A framework file as `get_framework` serves it."""
    return _framework_document(document, "The Name").body


_ONE_ENTRY = """\
title: The Name
description: What the framework is for.
source_url: https://example.invalid/framework
entries:
  a:
    title: Drift controls
    url: https://example.invalid/a
"""


@pytest.mark.unit
class TestTheBodyIsTheDocument:
    """What is searched is what `get_framework` serves, and that is the file.

    The body used to open with a summary the server wrote and end with the raw
    YAML. Measured live while it did: "framework structure" was found in 13 of
    13 frameworks, and "eu ai act" three times in a document that says it once.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "query",
        ["framework structure", "raw yaml content", "yaml", "title", "entries", "url"],
    )
    async def test_a_word_the_framework_does_not_say_is_not_a_match(
        self, monkeypatch, query: str
    ) -> None:
        """Not the words the old summary wrote, nor the keys of the YAML."""
        _stub_framework_corpus(monkeypatch, [("a", _served(_ONE_ENTRY))])

        found = await _search_tools.search_frameworks(query=query, limit=5)

        assert found.total_found == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "query", ["the name", "what the framework is for", "drift controls"]
    )
    async def test_what_the_framework_says_once_is_counted_once(
        self, monkeypatch, query: str
    ) -> None:
        _stub_framework_corpus(monkeypatch, [("a", _served(_ONE_ENTRY))])

        found = await _search_tools.search_frameworks(query=query, limit=5)

        assert [item.occurrences for item in found.results] == [1]

    @pytest.mark.asyncio
    async def test_the_passage_reads_as_the_document_does(self, monkeypatch) -> None:
        _stub_framework_corpus(monkeypatch, [("the-id", _served(_ONE_ENTRY))])

        found = await _search_tools.search_frameworks(query="drift controls", limit=5)

        assert found.results[0].content.endswith(
            "- **a**: Drift controls https://example.invalid/a"
        )
        assert found.results[0].section == "the-id"

    @pytest.mark.asyncio
    async def test_a_file_served_as_written_is_searched_as_written(
        self, monkeypatch
    ) -> None:
        """A file that is not shaped like a framework is still a body."""
        _stub_framework_corpus(monkeypatch, [("a", _served("- Drift controls\n"))])

        found = await _search_tools.search_frameworks(query="drift controls", limit=5)

        assert found.total_found == 1


# The only grouping a framework file has is a comment above an entry, which
# `get_framework` writes as a heading. Measured on the live corpus when search
# read the comments itself, a hit in `canada-regulations` reported the section
# "# -----...-----".
_SECTIONED = _served(
    """entries:
  first:
    title: Before any heading
  # Section: Prudential
  # -----------------------------------------------------------------
  osfi-e23:
    title: Model Risk Management
    description: Issued by OSFI.
  # ---------------------------------------------------------------
  # Tier 3 - Federal guidance (analogous; not
  # directly binding)
  # ---------------------------------------------------------------

  cppa:
    title: Privacy bill
  ##   Privacy   ##
  pipeda:
    title: Consent rules
"""
)


@pytest.mark.unit
class TestTheSectionIsTheHeadingTheMatchIsUnder:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("query", "section"),
        [
            ("before any heading", "the-name"),
            ("prudential", "Section: Prudential"),
            ("model risk management", "Section: Prudential"),
            ("issued by osfi", "Section: Prudential"),
            ("consent rules", "Privacy"),
            (
                "privacy bill",
                "Tier 3 - Federal guidance (analogous; not directly binding)",
            ),
        ],
    )
    async def test_it_is_named_without_markup(
        self, monkeypatch, query: str, section: str
    ) -> None:
        """Not a rule of dashes, and no `#` left on it."""
        _stub_framework_corpus(monkeypatch, [("the-name", _SECTIONED)])

        found = await _search_tools.search_frameworks(query=query, limit=1)

        assert [item.section for item in found.results] == [section]

    @pytest.mark.asyncio
    async def test_without_a_heading_it_is_the_framework_name(
        self, monkeypatch
    ) -> None:
        body = _served("entries:\n  # ----------\n  a:\n    title: Consent rules\n")
        _stub_framework_corpus(monkeypatch, [("the-name", body)])

        found = await _search_tools.search_frameworks(query="consent rules", limit=1)

        assert [item.section for item in found.results] == ["the-name"]

    @pytest.mark.asyncio
    async def test_an_entry_far_below_its_heading_is_still_under_it(
        self, monkeypatch
    ) -> None:
        """A heading is structure now; ten lines was the reach of a guess."""
        entries = "".join(f"  e{n}:\n    title: Entry {n}\n" for n in range(40))
        body = _served(f"entries:\n  # Tier 1\n{entries}  z:\n    title: Consent rules")
        _stub_framework_corpus(monkeypatch, [("the-name", body)])

        found = await _search_tools.search_frameworks(query="consent rules", limit=1)

        assert [item.section for item in found.results] == ["Tier 1"]

    @pytest.mark.asyncio
    async def test_a_value_that_looks_like_a_heading_is_not_one(
        self, monkeypatch
    ) -> None:
        body = _served(
            "description: '## Forged'\nentries:\n  a:\n    title: Consent rules\n"
        )
        _stub_framework_corpus(monkeypatch, [("the-name", body)])

        found = await _search_tools.search_frameworks(query="consent rules", limit=1)

        assert [item.section for item in found.results] == ["the-name"]

    @pytest.mark.asyncio
    async def test_the_note_that_closes_the_document_is_under_no_heading(
        self, monkeypatch
    ) -> None:
        """`canada-regulations` ends with a note on a bill that has no entry.

        A match in it was reported under the last heading above, "Tier 4"
        (#214).
        """
        body = _served(
            "entries:\n  # Tier 4\n  a:\n    title: Consent rules\n\n"
            "  # NOTE: Bill C-27 died on the order paper.\n"
        )
        _stub_framework_corpus(monkeypatch, [("the-name", body)])

        found = await _search_tools.search_frameworks(query="Bill C-27", limit=1)

        assert [item.section for item in found.results] == ["the-name"]

    @pytest.mark.asyncio
    async def test_a_file_served_as_written_has_no_headings(self, monkeypatch) -> None:
        """Its lines are YAML, and a comment that opens with `##` is one of them.

        It was reported as the section of every match below it (#214).
        """
        document = (
            "## License\nnotes: [a, b]\nentries:\n  a:\n    title: Consent rules\n"
        )
        served = _framework_document(document, "The Name")
        assert served.entries == 0, "the fixture must be served as written"
        _stub_framework_corpus(monkeypatch, [("the-name", served.body)], entry_count=0)

        found = await _search_tools.search_frameworks(query="consent rules", limit=1)

        assert [item.section for item in found.results] == ["the-name"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_frameworks_publishes_its_result_fields() -> None:
    """A caller that learned these names from the schema keeps finding them."""
    tool = await fastmcp_server.mcp.get_tool("search_frameworks")
    assert tool is not None and tool.output_schema is not None
    result = tool.output_schema["$defs"]["SearchResult"]

    assert set(result["properties"]) == {
        "document_id",
        "section",
        "content",
        "occurrences",
    }
    assert set(result["required"]) == set(result["properties"])
    assert result["properties"]["occurrences"]["type"] == "integer"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_the_description_claims_what_the_tool_does() -> None:
    """Read by the model that decides whether to call it.

    With the risk and mitigation searches gone, a small model reached for this
    tool between ``list_risks`` and ``get_risk`` in 11 of 12 measured runs
    (#208, stage 3). So the description says what it does not cover, and no
    longer says anything about relevance.
    """
    tool = await fastmcp_server.mcp.get_tool("search_frameworks")
    assert tool is not None and tool.description is not None
    description = " ".join(tool.description.split())
    limit = tool.parameters["properties"]["limit"]["description"]
    query = tool.parameters["properties"]["query"]["description"]

    assert "exact phrase" in description
    assert "does not search risks or mitigations" in description
    assert "list_risks" in description and "list_mitigations" in description
    assert "in the order list_frameworks gives them" in description
    assert "exact phrase" in query
    assert "in catalog order" in limit

    for text in (description, limit, query):
        lowered = text.lower()
        for claim in ("best match", "outrank", "relevan", "concept", "single-word"):
            assert claim not in lowered, f"{claim!r} is a claim about ranking: {text}"


# Hyphens and underscores are word separators to a searcher (#185). Measured on
# the live corpus before this held: "data-poisoning" found no risk at all where
# "data poisoning" found 18, and "third party" missed documents that write
# "third-party".
_SEPARATOR_SPELLINGS = [
    "prompt-injection",
    "prompt_injection",
    "Prompt-Injection",
    "prompt\u2011injection",  # non-breaking hyphen
    "prompt\u2010injection",  # Unicode hyphen
    "prompt\u2013injection",  # en dash
    "prompt\u2212injection",  # minus sign
    "prompt\u2012injection",  # figure dash
    "prompt\ufe63injection",  # small hyphen-minus
    "prompt\uff0dinjection",  # fullwidth hyphen-minus
    "prompt--injection",
    "prompt - injection",
    "-prompt-injection-",
    "  prompt   injection ",
]


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("spelling", _SEPARATOR_SPELLINGS)
async def test_a_hyphenated_query_finds_what_the_spaced_one_finds(
    monkeypatch, spelling: str
) -> None:
    """Same frameworks, same passages, same counts, whichever separator was typed."""
    _stub_framework_corpus(monkeypatch, _SAYS_THE_PHRASE)

    spaced = await _search_tools.search_frameworks(query="prompt injection", limit=5)
    other = await _search_tools.search_frameworks(query=spelling, limit=5)

    assert len(spaced.results) == 3, "precondition: the spaced query finds three"
    assert other.results == spaced.results
    assert other.total_found == spaced.total_found


@pytest.mark.unit
class TestFindPhrase:
    """The matcher, at its own boundary."""

    _BODY = "Contracts with third-party vendors must name a data owner."

    def test_a_spaced_query_matches_hyphenated_text(self) -> None:
        found = search_ranking._find_phrase("third party", self._BODY)

        assert found is not None
        assert self._BODY[found.start : found.end] == "third-party"

    def test_a_hyphenated_query_matches_spaced_text(self) -> None:
        body = "Every third party integration is reviewed."

        found = search_ranking._find_phrase("third-party", body)

        assert found is not None
        assert body[found.start : found.end] == "third party"

    def test_the_words_may_be_separated_by_a_line_break(self) -> None:
        """A wrapped line is still the phrase; the query's own spaces collapse too."""
        body = "Scope.\n\n\nVendors  and   third\n    party suppliers are in scope."

        found = search_ranking._find_phrase("third  party", body)

        assert found is not None
        assert body[found.start : found.end] == "third\n    party"

    def test_the_words_must_be_adjacent(self) -> None:
        body = "The third, and last, party to the contract."

        assert search_ranking._find_phrase("third party", body) is None

    @pytest.mark.parametrize("body", [None, "", "Unrelated."])
    def test_a_miss_is_reported_as_a_miss(self, body: str | None) -> None:
        assert search_ranking._find_phrase("data poisoning", body) is None

    @pytest.mark.parametrize("query", ["-", "--", "_", " - "])
    def test_a_query_of_separators_alone_matches_nothing(self, query: str) -> None:
        """Folded to nothing, it must not become the empty string every text contains."""
        assert search_ranking._find_phrase(query, "a - b_c") is None

    def test_the_first_occurrence_is_the_one_reported(self) -> None:
        body = "Drift. " * 3

        found = search_ranking._find_phrase("drift", body)

        assert found is not None
        assert (found.start, found.end, found.occurrences) == (0, 5, 3)

    def test_an_index_is_an_index_into_the_text_as_written(self) -> None:
        """Lower-casing U+0130 yields two characters; folding must not (#188)."""
        body = "\u0130stanbul \u0130\u0130\u0130 office: third-party vendors."

        found = search_ranking._find_phrase("third party", body)

        assert found is not None
        assert found.start == body.index("third-party")
        assert body[found.start : found.end] == "third-party"

    def test_a_query_is_text_not_a_pattern(self) -> None:
        body = "Controls a.c and (b) apply. Use C++ here."

        assert search_ranking._find_phrase("a.c", body) is not None
        assert search_ranking._find_phrase("abc", "a.c") is None
        assert search_ranking._find_phrase("a.c", "abc") is None
        assert search_ranking._find_phrase("(b)", body) is not None
        assert search_ranking._find_phrase("c++", body) is not None

    @pytest.mark.parametrize("dash", "\u2212\u2012\ufe63\uff0d")
    def test_a_character_typed_for_a_hyphen_is_a_separator_in_the_text(
        self, dash: str
    ) -> None:
        """A minus sign and three more that are pasted where a hyphen is meant.

        "risk management" was found in "risk-management" and not in the same
        words joined by U+2212 (#212).
        """
        body = f"A risk{dash}management plan."

        found = search_ranking._find_phrase("risk management", body)

        assert found is not None
        assert body[found.start : found.end] == f"risk{dash}management"

    @pytest.mark.parametrize(
        ("query", "body"),
        [
            ("risk management", "the risk\u2014management disagreed"),
            (
                "use an investor",
                "consent for AI use \u2014 an investor-protection area",
            ),
            ("risk management", "the risk\u2015management disagreed"),
        ],
    )
    def test_an_em_dash_is_punctuation_not_a_separator(
        self, query: str, body: str
    ) -> None:
        """It ends a clause, as a comma does, and a phrase does not span one.

        Every em dash of the live files, 23 on 2026-10-10, stands between two
        spaces. Folded to a space, the second body here would say "use an
        investor", which `iosco-supervisory-toolkit` does not (#212).
        """
        assert search_ranking._find_phrase(query, body) is None
        assert search_ranking._find_phrase(query.split()[-1], body) is not None


@pytest.mark.unit
class TestAQueryEdgedWithPunctuation:
    """Only a word can be inside a longer word (#212).

    The phrase was refused a word character on either side whatever it began
    and ended with, so "(b)" was found in "Article 3 (b)" and not in "Article
    3(b)". The live `eu-ai-act` writes "Article 5(1)" and "Article 6(2)".
    """

    @pytest.mark.parametrize(
        ("query", "body", "written"),
        [
            ("(b)", "Article 3(b) applies", "(b)"),
            ("(1)", "Referred to in Article 5(1), First Subparagraph", "(1)"),
            ("(b)", "Article 3(b)bis applies", "(b)"),
            ("c++", "Built with C++11 and later", "C++"),
            (".net", "An ASP.NET service", ".NET"),
            ("(b) applies", "Article 3(b) applies", "(b) applies"),
            ("article 5(1)", "in Article 5(1)(a)", "Article 5(1)"),
        ],
    )
    def test_it_is_found_beside_a_word_character(
        self, query: str, body: str, written: str
    ) -> None:
        found = search_ranking._find_phrase(query, body)

        assert found is not None
        assert body[found.start : found.end] == written

    @pytest.mark.parametrize(
        ("query", "body"),
        [
            ("(b", "Article 3 (but not 4)"),
            ("b)", "Article 3 (ab) applies"),
            ("act (b)", "The impact (b) is small"),
            ("(b) app", "Article 3(b) applies"),
            ("net", "An ASP.NETWORK service"),
        ],
    )
    def test_an_edge_that_is_a_word_character_is_still_a_whole_word(
        self, query: str, body: str
    ) -> None:
        assert search_ranking._find_phrase(query, body) is None

    @pytest.mark.parametrize(
        ("query", "body"),
        [
            ("\u0915\u0940", "\u0915\u0940\u092e\u0924 \u092c\u0922\u093c\u0940"),
            ("\u0e14\u0e35", "\u0e14\u0e35\u0e21\u0e32\u0e01"),
            ("x\u0302", "x\u0302yz"),
            ("\u0302x", "yz\u0302x"),
            ("\u0940", "\u0915\u0940\u092e\u0924"),
            ("ab\u200c", "ab\u200ccd"),
            ("\u200dab", "x\u200dab"),
        ],
    )
    def test_an_accent_at_the_edge_is_part_of_the_word_it_is_on(
        self, query: str, body: str
    ) -> None:
        """A vowel sign is not a word character, and the letter under it is."""
        assert search_ranking._find_phrase(query, body) is None
        assert search_ranking._find_phrase(query, f"({query})") is not None


# Hangul written as one syllable to a character, and as the jamo it is made of.
_SEOUL = "\uc11c\uc6b8"
_SEOUL_IN_JAMO = "\u1109\u1165\u110b\u116e\u11af"


@pytest.mark.unit
class TestOneCharacterWrittenTwoWays:
    """A letter and its accent may be one character or two (#212).

    A file saved on one system and a query typed on another disagree about
    which, and "caf\u00e9" was not found in the same word written with a
    combining accent.
    """

    @pytest.mark.parametrize(
        ("query", "body", "written"),
        [
            ("caf\u00e9", "A cafe\u0301 au lait", "cafe\u0301"),
            ("cafe\u0301", "A caf\u00e9 au lait", "caf\u00e9"),
            ("CAFE\u0301", "A caf\u00e9 au lait", "caf\u00e9"),
            ("caf\u00e9 au", "A CAFE\u0301\n  au lait", "CAFE\u0301\n  au"),
            (_SEOUL, f"In {_SEOUL_IN_JAMO} today", _SEOUL_IN_JAMO),
            (_SEOUL_IN_JAMO, f"In {_SEOUL} today", _SEOUL),
            ("caf\u00e9", "the \u201ccafe\u0301\u201d is open", "cafe\u0301"),
            ("caf\u00e9", "A cafe\u0301\u2014and more", "cafe\u0301"),
            ("caf\u00e9", "A cafe\u0301", "cafe\u0301"),
            (
                "caf\u00e9",
                "\u00abre\u0301sume\u0301\u00bb \u201ccaf\u00e9\u201d",
                "caf\u00e9",
            ),
            ("\u00e9", "e\u0301\u2014\u0958", "e\u0301"),
            ("q\u0323\u0307", "A q\u0307\u0323 x", "q\u0307\u0323"),
        ],
    )
    def test_it_is_found_and_quoted_as_the_text_wrote_it(
        self, query: str, body: str, written: str
    ) -> None:
        found = search_ranking._find_phrase(query, body)

        assert found is not None
        assert body[found.start : found.end] == written

    def test_an_index_after_it_is_still_an_index_into_the_text(self) -> None:
        """Composed, the text is shorter, and every index after it moved."""
        body = "Cafe\u0301 re\u0301sume\u0301, cafe\u0301: third-party vendors."

        found = search_ranking._find_phrase("third party", body)

        assert found is not None
        assert body[found.start : found.end] == "third-party"

    def test_each_occurrence_is_counted_and_the_first_reported(self) -> None:
        body = "x cafe\u0301, caf\u00e9 and CAFE\u0301."

        found = search_ranking._find_phrase("caf\u00e9", body)

        assert found is not None
        assert (found.start, found.end, found.occurrences) == (2, 7, 3)

    @pytest.mark.parametrize(
        ("query", "written"),
        [
            ("financial", "\ufb01nancial"),
            ("abc", "\uff21\uff22\uff23"),
            # The plain form is folded again: a full-width low line is "_".
            ("data poisoning", "data\uff3fpoisoning"),
            # And composed again with the mark after it.
            ("\u00e9", "\uff45\u0301"),
            ("\u30ac", "\uff76\uff9e"),
        ],
    )
    def test_a_compatibility_character_is_found_as_its_plain_form(
        self, query: str, written: str
    ) -> None:
        """The served body keeps a ligature, a full-width letter or a
        superscript as written since #352; the comparison folds it (#361)."""
        body = f"The {written} sector"

        found = search_ranking._find_phrase(query, body)

        assert found is not None
        assert body[found.start : found.end] == written

    @pytest.mark.parametrize(
        ("query", "body"),
        [
            ("acme", "The Acme\u2122 policy"),
            ("risk", "risk\u2120 here"),
            ("don\u00b4t", "So don\u00b4t do it"),
            ("x\u00b2", "where x\u00b2 grows"),
        ],
    )
    def test_other_compatibility_characters_are_left_as_written(
        self, query: str, body: str
    ) -> None:
        """All of NFKC turned "\u2122" into "TM" glued to the word, and a
        spacing accent into a space; only width forms and ligatures fold."""
        found = search_ranking._find_phrase(query, body)

        assert found is not None
        assert body[found.start : found.end] == query.replace("acme", "Acme")

    def test_the_word_without_its_accent_is_another_word(self) -> None:
        """An accent written apart is not a word character, and "cafe" was
        found in the first four characters of "cafe\u0301"."""
        assert search_ranking._find_phrase("cafe", "A cafe\u0301 au lait") is None
        assert search_ranking._find_phrase("cafe", "A caf\u00e9 au lait") is None

    def test_a_link_target_is_still_not_text(self) -> None:
        body = "re\u0301sume\u0301: https://example.invalid/cafe\u0301-au-lait"

        assert search_ranking._find_phrase("caf\u00e9 au lait", body) is None
        assert search_ranking._find_phrase("r\u00e9sum\u00e9", body) is not None

    @pytest.mark.parametrize(
        "text",
        [
            "plain",
            "",
            "cafe\u0301",
            "\u0301 opens with an accent",
            f"{_SEOUL_IN_JAMO}{_SEOUL} a\u0308\u0301o\u0323\u0302 q\u0307\u0323",
            "e\u0301\0\0e\u0301 \u212b \u1e9b\u0323 \u0130\u0307",
            "\ufb01nancial \uff21\uff22\uff23 x\u00b2 \u2026",
        ],
    )
    def test_composing_piece_by_piece_is_composing_the_whole(self, text: str) -> None:
        """And every character of the result is given a place in the text."""
        composed, written = search_ranking._composed(text)

        assert composed == search_ranking._plain(text)
        if written is None:
            assert composed == text
        else:
            assert len(written) == len(composed)
            for character, (low, high) in zip(composed, written, strict=True):
                assert character in search_ranking._plain(text[low:high])

    # Five accents no two of which are of one class, so that composing has
    # an order to put them in.
    _ACCENTS = "\u0323\u0301\u0327\u031b\u0345"

    def _heap(self, length: int) -> str:
        """A letter under accents, `length` characters in all."""
        return "e" + (self._ACCENTS * length)[: length - 1]

    @pytest.mark.parametrize("length", [5, 32])
    def test_a_letter_under_many_accents_is_composed(self, length: int) -> None:
        import unicodedata

        heap = self._heap(length)
        whole = unicodedata.normalize("NFC", heap)
        assert whole != heap, "precondition: composing changes it"

        composed, written = search_ranking._composed(f"A {heap} x")

        assert composed == f"A {whole} x"
        assert written is not None and written[2] == (2, 2 + length)
        found = search_ranking._find_phrase(whole, f"A {heap} x")
        assert found is not None and (found.start, found.end) == (2, 2 + length)

    def test_a_letter_under_more_accents_than_any_has_is_left_as_written(
        self, monkeypatch
    ) -> None:
        """Putting accents in order costs the square of their number: a
        megabyte of them after one letter took 198 seconds to compose. So
        nothing longer than a letter can be is handed over to be composed,
        and that is what is measured here, not the time."""
        import types
        import unicodedata
        from typing import Literal

        handed_over: list[int] = []

        def _normalize(form: Literal["NFC", "NFD", "NFKC", "NFKD"], text: str) -> str:
            handed_over.append(len(text))
            return unicodedata.normalize(form, text)

        monkeypatch.setattr(
            search_ranking,
            "unicodedata",
            types.SimpleNamespace(
                normalize=_normalize,
                is_normalized=unicodedata.is_normalized,
                combining=unicodedata.combining,
                category=unicodedata.category,
                decomposition=unicodedata.decomposition,
            ),
        )
        heap = self._heap(33)
        # A character that is not ASCII after each heap: `_units` has to
        # decide whether it composes with the heap before it.
        body = f"{heap}\u6771 {heap * 20}\u1161 then cafe\u0301"

        composed, written = search_ranking._composed(body)

        assert composed == body.replace("cafe\u0301", "caf\u00e9")
        assert written is not None and written[33] == (33, 34)
        assert max(handed_over) <= search_ranking._LONGEST_COMPOSED + 1, handed_over

    def test_a_query_copied_from_the_text_is_found_in_it(self) -> None:
        """Where the text is left as written the query is too. Composed
        whole, it was another string and was not found (#212)."""
        heap = self._heap(41)
        tibetan = "\u1e60\u0f73\u0307"

        for copied in (heap, tibetan):
            body = f"x {copied} y"
            found = search_ranking._find_phrase(copied, body)
            assert found is not None, ascii(copied)
            assert body[found.start : found.end] == copied

    def test_a_final_sigma_is_one_beside_a_dotted_capital_i(self) -> None:
        """U+0130 takes the text off `str.lower`, and the rule went with it.

        Lower-cased a character at a time, a capital sigma is never the final
        one, and "\u03bf\u03b4\u03cc\u03c2" was not found in its own capitals
        once the text held a U+0130 anywhere (#212).
        """
        street = "\u039f\u0394\u038c\u03a3"
        body = f"\u0130 {street} and {street}\u0130 too"

        found = search_ranking._find_phrase("\u03bf\u03b4\u03cc\u03c2", body)

        assert found is not None
        assert (found.start, found.end, found.occurrences) == (2, 6, 1)
        assert search_ranking._fold(body) == f"\u0130 {street.lower()} and " + (
            "\u03bf\u03b4\u03cc\u03c3\u0130 too"
        )


@pytest.mark.unit
class TestAWordMatchesOnlyAsAWord:
    """A query used to match inside longer words (#190)."""

    @pytest.mark.parametrize(
        ("query", "body"),
        [
            ("rag", "Encrypted storage, leveraging coverage."),
            ("act", "Good practice has impact."),
            ("-5", "Controls A5, 15 and 5th."),
            ("ai act", "Retain act records; said actively."),
            ("risk management", "A derisk management plan. Risk managements."),
        ],
    )
    def test_inside_a_longer_word_it_is_a_miss(self, query: str, body: str) -> None:
        assert search_ranking._find_phrase(query, body) is None

    @pytest.mark.parametrize(
        "body",
        [
            "RAG pipelines.",
            "Retrieval (RAG).",
            "Uses 'rag', then stops.",
            "storage, then rag",
            "a rag-based system",
            "pre_rag_checks",
            "**rag**: retrieval",
        ],
    )
    def test_next_to_punctuation_or_a_separator_it_is_a_hit(self, body: str) -> None:
        found = search_ranking._find_phrase("rag", body)

        assert found is not None
        assert body[found.start : found.end].lower() == "rag"

    def test_the_count_respects_word_boundaries_too(self) -> None:
        """Measured live before this held: 16 substring hits, 2 of them the word."""
        body = "Storage of RAG data; leverage rag. Coverage, storage, average."

        found = search_ranking._find_phrase("rag", body)

        assert found is not None
        assert found.occurrences == 2
        assert found.start == body.index("RAG")


@pytest.mark.unit
class TestALinkTargetIsNotText:
    """Since #185 a spaced phrase matches hyphenated text, URLs included (#188)."""

    @pytest.mark.parametrize(
        "body",
        [
            "See https://example.invalid/risks/ri-2_data-poisoning.md for more.",
            "url: http://example.invalid/data-poisoning/",
            "Read [the risk](../risks/ri-2_data-poisoning.md) first.",
            "Read [the risk](<../risks/data poisoning.md>) first.",
            'Read [the risk](../risks/ri-2_data-poisoning.md "The risk") first.',
            "Read [the risk](../risks/ri-2 data-poisoning.md) first.",
            "![diagram](img/data-poisoning.png 'A diagram')",
            "url: HTTPS://EXAMPLE.invalid/data-poisoning",
            "See <ftp://example.invalid/data-poisoning>.",
            "Read [the risk](a(b)_data-poisoning.md) first.",
            "Read [it](wiki/Data_(computing)/data-poisoning 'x') first.",
            "Read [it](wiki/data-poisoning_(attack)) first.",
            "Read [it](a(b)c(d)_data-poisoning.md) first.",
        ],
    )
    def test_a_phrase_only_inside_a_link_target_is_a_miss(self, body: str) -> None:
        assert search_ranking._find_phrase("data poisoning", body) is None

    def test_the_text_of_a_link_is_still_searched(self) -> None:
        body = "Read [data poisoning](../risks/ri-2_data-poisoning.md) first."

        found = search_ranking._find_phrase("data poisoning", body)

        assert found is not None
        assert (found.start, found.occurrences) == (body.index("data poisoning"), 1)

    @pytest.mark.parametrize(
        "body",
        [
            "Read [it](a(b)c) on data poisoning",
            "Read [it](a(b data poisoning",
            "As [it](y) says (data poisoning (of an index)) twice",
        ],
    )
    def test_the_text_after_a_target_is_still_searched(self, body: str) -> None:
        found = search_ranking._find_phrase("data poisoning", body)

        assert found is not None
        assert found.occurrences == 1

    @pytest.mark.parametrize(
        ("query", "body"),
        [
            ("data poisoning", "See example.com/ri-2_data-poisoning.md"),
            ("express", "Built on Node.js/Express"),
            ("opt out", "client consent/opt-out for AI use"),
            ("data poisoning", "[q]: docs/ri-2_data-poisoning.md"),
            ("iec 42001", "[Standard]: ISO/IEC 42001 applies"),
            ("output filtering", "\\[Controls]: input/output filtering"),
            ("model.pkl", "[Artefact]: model.pkl"),
        ],
    )
    def test_an_address_with_no_scheme_is_text(self, query: str, body: str) -> None:
        """Nothing tells `example.com/a_b.md` from `Node.js/Express`, and the
        live `iosco-supervisory-toolkit` writes "consent/opt-out". Nor a link
        reference definition from a label over text. A target searched by
        mistake is a passage a reader can see; text blanked by mistake is a
        document that no longer says what it says (#212)."""
        assert search_ranking._find_phrase(query, body) is not None

    def test_text_in_parentheses_is_not_a_link_target(self) -> None:
        body = "Attacks on training sets (data poisoning) are in scope."

        assert search_ranking._find_phrase("data poisoning", body) is not None

    def test_text_after_a_link_is_still_searched(self) -> None:
        """An address ends at a quote, a bracket or a table bar, not only a space."""
        for body in (
            '<a href="https://example.invalid/a">data poisoning</a> is covered',
            "| https://example.invalid/a|data poisoning|",
            "url: 'https://example.invalid/a'# data poisoning",
        ):
            found = search_ranking._find_phrase("data poisoning", body)
            assert found is not None, body
            assert found.start == body.index("data poisoning")

    def test_an_index_after_a_link_is_still_an_index_into_the_text(self) -> None:
        body = (
            "See [it](../risks/x.md) and https://example.invalid/y then data poisoning."
        )

        found = search_ranking._find_phrase("data poisoning", body)

        assert found is not None
        assert body[found.start : found.end] == "data poisoning"

    def test_words_either_side_of_a_link_are_not_a_phrase(self) -> None:
        body = "data https://example.invalid/x poisoning, data [x](y) poisoning"

        assert search_ranking._find_phrase("data poisoning", body) is None

    @pytest.mark.parametrize("query", ["\0", "\0\0", "a \0", "see\0"])
    def test_a_query_cannot_name_the_blank_a_link_was_replaced_with(
        self, query: str
    ) -> None:
        body = "a https://example.invalid/x see [it](../y.md) end"

        assert search_ranking._find_phrase(query, body) is None

    def test_a_word_beside_a_link_is_still_a_word(self) -> None:
        body = "poisoning: https://example.invalid/x data"

        assert search_ranking._find_phrase("poisoning", body) is not None
        assert search_ranking._find_phrase("data", body) is not None

    def test_the_passage_is_cut_around_the_text_not_the_link(self) -> None:
        body = (
            "url: https://example.invalid/data-poisoning/\n"
            + "filler words here. " * 30
            + "An attacker performs data poisoning of the index."
        )

        found = search_ranking._find_phrase("data poisoning", body)

        assert found is not None and found.occurrences == 1
        passage = search_ranking._passage(body, found.start, found.end)
        assert "performs data poisoning of the index." in passage
        assert "example.invalid" not in passage


@pytest.mark.unit
class TestThePassage:
    """Snippets were cut at a fixed character offset, mid-word (#188)."""

    _WORDS = tuple(f"word{n:03d}" for n in range(200))
    _BODY = " ".join(_WORDS[:100]) + " the needle here " + " ".join(_WORDS[100:])

    def _passage(self, body: str, needle: str = "the needle here") -> str:
        start = body.index(needle)
        return search_ranking._passage(body, start, start + len(needle))

    def test_it_starts_and_ends_on_whole_words(self) -> None:
        passage = self._passage(self._BODY)

        assert passage.startswith("...") and passage.endswith("...")
        inner = passage.removeprefix("...").removesuffix("...").split()
        allowed = {*self._WORDS, "the", "needle", "here"}
        assert [word for word in inner if word not in allowed] == []
        assert len(inner) > 20, "precondition: there is context either side"

    def test_it_contains_the_match_and_text_either_side(self) -> None:
        passage = self._passage(self._BODY)

        assert "word099 the needle here word100" in passage

    def test_a_short_text_is_quoted_whole_without_ellipses(self) -> None:
        body = "Only the needle here, nothing more."

        assert self._passage(body) == body

    def test_line_breaks_and_indentation_become_single_spaces(self) -> None:
        body = "entries:\n  s2:\n    title: the needle here\n    url: x\n"

        assert self._passage(body) == "entries: s2: title: the needle here url: x"

    def test_a_url_in_the_passage_is_whole_or_absent(self) -> None:
        url = "https://example.invalid/" + "segment/" * 30
        body = f"{'pad ' * 20}{url} the needle here {url}{' pad' * 20}"

        passage = self._passage(body)

        remainder = passage.replace(url, "")
        assert "example.invalid" not in remainder and "segment/" not in remainder

    def test_a_match_longer_than_the_window_is_still_quoted_whole(self) -> None:
        needle = " ".join(self._WORDS)

        passage = self._passage(f"before {needle} after", needle)

        assert needle in passage
