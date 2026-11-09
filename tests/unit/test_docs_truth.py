"""Guards that the documentation tells the truth about the tool surface.

This drift has already happened once: the docs claimed 21 tools when 11
existed, the nine copies were corrected by hand, and no invariant was added. It
drifted again within months, the same way (#47, #66).
Correcting nine copies a second time buys exactly as much time as it bought the
first time, so these tests are the part that has to land with the correction.

These tests assert eleven invariants:

1. **Name closure.** No live document names a tool the server does not publish.
   This is the invariant that kills the ``21 tools`` class: dead names like
   ``get_framework_content`` survive in prose long after the symbol is gone,
   and an LLM caller reading the docs as a contract will call them.
2. **Category closure.** Every category heading's membership and its
   parenthesised count are *derived* from the published tool list, never typed.
   Nine documents split the 11 tools as 5 framework / 4 risk-and-mitigation /
   2 system. The arithmetic was right and the membership was not: ``list_risks``
   and ``get_risk`` were filed under "Framework Access Tools", separated from
   ``search_risks`` (#66). A count stated in a sentence is derived the same way.
3. **The scanners can fail.** Each scanner is run against a synthetic document
   carrying a known-false claim and must reject it, and each is asserted to have
   scanned a non-zero number of real files. A scanner that globs nothing is
   otherwise indistinguishable from one that passes -- a trap this repository
   has hit before.
4. **Nothing under ``docs/`` escapes.** Every tracked file there is one the
   scanners read. #72 was an HTML deck with a miscounted inventory that none of
   them had opened.
5. **The names from last time stay out.** The fifteen tools the docs once
   described and the server never had, and the wrong name they used for
   ``get_framework``, are listed in ``_NEVER_IMPLEMENTED_TOOLS`` and may not
   appear in a live document, in prose or in a code example.
   ``BUGFIX_SUMMARY.md`` held those names until #73 deleted the file.
6. **Errors are shown as the server sends them.** No document shows a JSON
   object with a top-level ``error`` key, a shape the docs described for
   months and no tool has ever returned (#217), and the sentences the error
   reference quotes are built from the exception classes that write them.
7. **The inventory is not copied again.** The documents that list every tool
   are named in ``_DOCUMENTS_CARRYING_A_FULL_INVENTORY``. A new copy fails, and
   so does a removed one, until the list is amended. Two remain and neither
   is typed by hand unchecked: the README's table is written by
   ``scripts/generate-tool-table.py`` (``test_generated_tool_table.py``), and
   ``docs/api/mcp-tools.md`` is read back against the server
   (``test_tools_reference_matches_server.py``).
8. **Every class the docs name exists.** A backticked CamelCase name is defined
   under ``src/`` or listed in ``_EXTERNAL_SYMBOLS``, and each entry there must
   still be named by a live document (#65).
9. **The FINOS charter stays stated.** ``CONTRIBUTING.md`` keeps its IP-policy
   and CLA clauses and no live document denies the affiliation, whoever
   ``NOTICE`` names as the copyright owner (#80).
10. **No number without a source.** No live document states a response time,
    because nothing in the repository measures one, and a cache lifetime a
    document states is one the configuration has. The docs gave three
    lifetimes where the server has one, and times no test produced (#236).
11. **The base response is one the server sends.** The example under "Base
    Response Structure" is compared with a result taken from the assembled
    server. It showed a text block alone while every tool also returned
    structured content (#236).

**Why the corpus is defined by location.** The scan covers ``README.md``,
``CONTRIBUTING.md`` and everything under ``docs/``. ``CHANGELOG.md`` is a
point-in-time record: each entry describes what was true when it was written,
and it contains dead tool names *on purpose*, because naming them is how it
records what was fixed.
Excluding it by **class** -- a live contract lives in ``docs/`` or is the
README -- rather than by name avoids the allowlist #47 warned about, where the
remedy for a new failure becomes "append one more entry".

The tool list is read from ``PUBLISHED_TOOLS``, which
``tests/unit/test_published_surface.py`` declares to be the single source of
truth for the inventory and asserts against the running server. So the chain is
docs -> PUBLISHED_TOOLS (here, offline) -> the assembled server (there), and no
part of it needs the network. A doc gate that reached GitHub would inherit the
unauthenticated 60 requests/hour budget and start failing for reasons that have
nothing to do with the documentation.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

pytestmark = pytest.mark.unit

#: Category titles, in the order the documents present them. The membership of
#: each is derived below rather than listed, so this names the *vocabulary* the
#: docs use and never the answer.
_FRAMEWORK_CATEGORY = "Framework Access Tools"
_RISK_CATEGORY = "Risk & Mitigation Tools"
_SYSTEM_CATEGORY = "System Monitoring Tools"

#: Subject -> the category that subject belongs to. A tool's subject is its name
#: with the verb stripped and the plural dropped, so ``list_frameworks``,
#: ``get_framework`` and ``search_frameworks`` all reduce to ``framework``.
#: Anything whose subject is not a document kind is service machinery.
_CATEGORY_BY_SUBJECT = {
    "framework": _FRAMEWORK_CATEGORY,
    "risk": _RISK_CATEGORY,
    "mitigation": _RISK_CATEGORY,
}

_VERB_PREFIX = re.compile(r"^(?:list|get|search)_")


def _repo_root(pytestconfig: pytest.Config) -> Path:
    return Path(str(pytestconfig.rootpath))


def _published_tools(root: Path) -> dict[str, set[str]]:
    """The declared tool inventory, asserted against the server elsewhere."""
    sys.path.insert(0, str(root / "tests" / "unit"))
    try:
        from test_published_surface import (  # type: ignore[import-not-found]
            PUBLISHED_TOOLS,
        )

        return dict(PUBLISHED_TOOLS)
    finally:
        sys.path.pop(0)


def _category_of(tool: str) -> str:
    """Return the category ``tool`` belongs to, derived from its name."""
    subject = _VERB_PREFIX.sub("", tool)
    return _CATEGORY_BY_SUBJECT.get(subject.rstrip("s"), _SYSTEM_CATEGORY)


def _expected_categories(tools: dict[str, set[str]]) -> dict[str, set[str]]:
    """Return ``{category title: members}`` for the published tool list."""
    categories: dict[str, set[str]] = {}
    for tool in tools:
        categories.setdefault(_category_of(tool), set()).add(tool)
    return categories


def _tracked(root: Path, *pathspecs: str) -> list[str]:
    """Index entries under the given pathspecs, as repository-relative paths."""
    listing = subprocess.run(
        ["git", "ls-files", "-z", *pathspecs],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [entry for entry in listing.split("\0") if entry]


def _live_docs(root: Path) -> list[Path]:
    """Every tracked document that is a live contract rather than a record.

    Defined by location, not by a list of exceptions: the README, the
    contributor guide, and everything under ``docs/``.
    """
    return [
        root / entry
        for entry in _tracked(root, "README.md", "CONTRIBUTING.md", "docs")
        if entry.endswith(".md") and (root / entry).is_file()
    ]


def test_everything_tracked_under_docs_is_a_document_the_scanners_read(
    pytestconfig: pytest.Config,
) -> None:
    """Nothing under ``docs/`` sits outside the corpus the tests below scan.

    ``_live_docs`` keeps only ``.md`` entries, so a file of any other type under
    ``docs/`` is skipped without a word. #72 found an HTML slide deck there with
    a caption reading "11 enterprise-grade tools" over a five-category split
    summing to twelve, and no invariant in this module had ever opened it.

    This rejects every other file type, images included. Before adding one,
    either teach the scanners to read it or exempt its type here with the
    reason it can carry no claim about the tools. Being opened is all this
    guarantees: the scanners would not have caught that caption's wording.
    """
    root = _repo_root(pytestconfig)
    tracked = _tracked(root, "docs")
    assert len(tracked) >= 10, f"docs/ listing looks empty: {len(tracked)} paths"
    unread = sorted(
        set(tracked) - {str(doc.relative_to(root)) for doc in _live_docs(root)}
    )
    assert not unread, (
        f"tracked under docs/ but read by no documentation test: {unread}"
    )


#: A backticked identifier shaped like one of this server's tools: a known verb,
#: an underscore, then a subject. Deliberately narrower than "any backticked
#: snake_case word", which would sweep up parameter names, settings and Python
#: functions that are not tools at all.
_TOOL_SHAPED = re.compile(r"`((?:list|get|search)_[a-z_]+)`")

#: The three category titles, as an alternation. Named once so the two shapes
#: below cannot drift apart.
_TITLES = "|".join(
    re.escape(title)
    for title in (_FRAMEWORK_CATEGORY, _RISK_CATEGORY, _SYSTEM_CATEGORY)
)

#: A category announced as a markdown heading, optionally carrying its count as
#: ``(3)`` or ``(3 tools)``.
_CATEGORY_IN_HEADING = re.compile(
    rf"^(#{{1,6}})\s+({_TITLES})(?:\s*\((\d+)(?:\s+tools?)?\))?",
    re.MULTILINE,
)

#: A category announced as a bolded table row. ``docs/README.md`` puts the count
#: inside the bold, ``docs/api/README.md`` puts it in the next cell.
_CATEGORY_IN_TABLE_ROW = re.compile(
    rf"^\|\s*\*\*({_TITLES})(?:\s*\((\d+)\))?\*\*\s*\|\s*(?:(\d+)\s+tools?)?",
    re.MULTILINE,
)

#: Any markdown heading, with its level.
_ANY_HEADING = re.compile(r"^(#{1,6})\s", re.MULTILINE)

#: The level recorded for a table-row category. Higher than any real heading, so
#: such a section ends at the very next heading or category row -- a table row
#: has no children to contain.
_TABLE_ROW_LEVEL = 99


class _Category:
    """One category announcement in one document."""

    def __init__(self, start: int, title: str, claimed: str | None, level: int):
        self.start, self.title, self.level = start, title, level
        self.claimed = int(claimed) if claimed is not None else None


def _categories_in(text: str) -> list[_Category]:
    """Every category announcement in ``text``, in document order."""
    found = [
        _Category(m.start(), m.group(2), m.group(3), len(m.group(1)))
        for m in _CATEGORY_IN_HEADING.finditer(text)
    ]
    found += [
        _Category(m.start(), m.group(1), m.group(2) or m.group(3), _TABLE_ROW_LEVEL)
        for m in _CATEGORY_IN_TABLE_ROW.finditer(text)
    ]
    return sorted(found, key=lambda category: category.start)


def _section_body(text: str, category: _Category) -> str:
    """Return the span a category owns.

    Markdown nesting decides this, not proximity. A ``##`` category ends at the
    next heading of the same or higher level and **contains its ``###``
    children** -- ``docs/api/mcp-tools.md`` gives every tool its own ``###``
    sub-heading, so a body bounded at the next heading of any level is empty and
    the membership check silently passes on a document that misfiles two tools.
    A table-row category has no children and ends at the next row or heading.
    """
    body_start = (
        text.index("\n", category.start) + 1
        if "\n" in text[category.start :]
        else len(text)
    )
    ends = [
        match.start()
        for match in _ANY_HEADING.finditer(text, body_start)
        if len(match.group(1)) <= category.level
    ]
    ends += [
        other.start for other in _categories_in(text) if other.start > category.start
    ]
    return text[body_start : min(ends) if ends else len(text)]


#: A fenced code block. Stripped before anything else looks for headings: a
#: ``# Request`` comment inside a ```python fence is indistinguishable from an
#: H1, and ``docs/api/response-schemas.md`` has six of them. Bounding on those
#: truncated the first category after two tools and left the misfiled
#: ``list_risks`` and ``get_risk`` outside the span, so the membership check
#: passed on a document that was wrong.
_FENCED_BLOCK = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)

#: A tool named as a numbered entry rather than in backticks:
#: ``### 4. list_risks Response`` and ``**4. list_risks** - ...``. Two documents
#: present their inventory this way and name no tool in backticks at all, so
#: without this their membership was never checked -- only their counts were.
_TOOL_NUMBERED = re.compile(
    r"^(?:#{1,6}\s+|\*\*)\d+\.\s+((?:list|get|search)_[a-z_]+)\b",
    re.MULTILINE,
)


def _strip_fences(text: str) -> str:
    """Blank out fenced code, preserving line count so line numbers stay true."""
    return _FENCED_BLOCK.sub(lambda match: "\n" * match.group(0).count("\n"), text)


def _tool_names_in(text: str) -> set[str]:
    return set(_TOOL_SHAPED.findall(text)) | set(_TOOL_NUMBERED.findall(text))


def test_no_live_document_names_a_tool_the_server_does_not_publish(
    pytestconfig: pytest.Config,
) -> None:
    """A dead tool name in the docs is a call an LLM caller will actually make.

    The docs are the contract a model reads before choosing a tool, so a name
    that no longer exists is not a cosmetic error -- it produces a failed call
    with no way for the caller to know the documentation was wrong rather than
    its own request. ``CHANGELOG.md`` still carries
    ``get_framework_details``, ``get_compliance_analysis`` and
    ``search_framework_references`` from the last time this happened, which is
    why the corpus here is live documents only.

    Scoped to *tool-shaped* backticked names -- a known verb prefix, then a
    subject. A guard over every backticked ``snake_case`` word would accuse
    parameter names, settings and ordinary Python functions, and an invariant
    that accuses correct prose is worse than no invariant.

    A name that is tool-shaped but **defined in** ``src/`` is not a stale tool
    claim either. ``docs/api/framework-architecture.md`` documents
    ``ContentService``'s real surface, which includes ``get_document``,
    ``get_health_status`` and ``get_service_diagnostics``: methods, not tools,
    and correct. Subtracting the defined symbols keeps the dead-name check --
    ``get_framework_content`` is defined nowhere -- while dropping that whole
    class of false accusation.
    """
    root = _repo_root(pytestconfig)
    published = set(_published_tools(root))
    defined = _defined_symbols(root)
    docs = _live_docs(root)

    assert len(docs) >= 10, (
        f"found only {len(docs)} live documents, so this invariant would pass "
        "by scanning almost nothing. It exists to read the whole live corpus."
    )

    offenders: dict[str, list[str]] = {}
    for doc in docs:
        unknown = sorted(
            _tool_names_in(_strip_fences(doc.read_text(encoding="utf-8")))
            - published
            - defined
        )
        if unknown:
            offenders[str(doc.relative_to(root))] = unknown

    assert not offenders, (
        f"These live documents name tools the server does not publish: "
        f"{offenders}. The published inventory is {sorted(published)}. Either "
        "the name is stale and the document is wrong, or the tool was removed "
        "and its documentation was not."
    )


#: The fifteen tools the documentation once described and the server never had,
#: plus ``get_framework_content``, the name the documentation used for
#: ``get_framework``. ``BUGFIX_SUMMARY.md`` recorded all sixteen until #73
#: deleted it. They are kept because the invariant above cannot see all of
#: them: five do not start with ``list_``, ``get_`` or ``search_``, so
#: ``_TOOL_SHAPED`` does not match them, and it does not read fenced code at all.
_NEVER_IMPLEMENTED_TOOLS = frozenset(
    {
        "advanced_search_frameworks",
        "bulk_export_frameworks",
        "export_framework_data",
        "find_compliance_gaps",
        "get_compliance_analysis",
        "get_framework_content",
        "get_framework_correlations",
        "get_framework_details",
        "get_mitigation_details",
        "get_related_controls",
        "get_risk_details",
        "get_service_metrics",
        "list_all_mitigations",
        "list_all_risks",
        "reset_service_health",
        "search_framework_references",
    }
)

#: Any identifier, so a register name is matched whole and never as part of a
#: longer one.
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _never_implemented_in(documents: dict[str, str]) -> dict[str, list[str]]:
    """Register names each document uses as a whole identifier, fences included.

    Markdown renders ``get\\_risk\\_details`` as the name itself, so an escaped
    underscore is read as a plain one.
    """
    return {
        name: sorted(found)
        for name, text in documents.items()
        if (
            found := set(_IDENTIFIER.findall(text.replace("\\_", "_")))
            & _NEVER_IMPLEMENTED_TOOLS
        )
    }


def test_no_live_document_names_a_tool_that_was_documented_but_never_built(
    pytestconfig: pytest.Config,
) -> None:
    """The names the docs got wrong last time may not come back.

    Unlike the invariant above this reads the whole document, fenced code
    included, and matches any identifier: a ``call_tool("export_framework_data")``
    example is the form a caller copies. That is affordable only because the
    register is a closed list of names known to be wrong.

    A name leaves the register when the server starts publishing a tool by that
    name; the first assertion says so.
    """
    root = _repo_root(pytestconfig)
    docs = _live_docs(root)

    revived = sorted(_NEVER_IMPLEMENTED_TOOLS & set(_published_tools(root)))
    assert not revived, (
        f"{revived} are published tools now, so they are no longer names the "
        "server never had. Remove them from _NEVER_IMPLEMENTED_TOOLS."
    )

    assert len(docs) >= 10, (
        f"found only {len(docs)} live documents, so this invariant would pass "
        "by scanning almost nothing. It exists to read the whole live corpus."
    )

    offenders = _never_implemented_in(
        {str(doc.relative_to(root)): doc.read_text(encoding="utf-8") for doc in docs}
    )
    assert not offenders, (
        f"These live documents use names of tools that were documented but "
        f"never built: {offenders}. A reader who sees the name, even as a "
        "helper in an example, may call it as a tool."
    )


def test_every_category_heading_matches_the_published_inventory(
    pytestconfig: pytest.Config,
) -> None:
    """A hand-typed category count stays plausible long after it stops being true.

    ``Framework Access Tools (5)`` was arithmetically consistent with
    ``Risk & Mitigation Tools (4)`` and ``System Monitoring Tools (2)``: the
    three sum to 11, which is the right number of tools. What was wrong was the
    membership -- ``list_risks`` and ``get_risk`` sat under "Framework Access"
    while ``search_risks`` sat under "Risk & Mitigation" (#66). A count check
    alone would have passed on all nine copies, so this asserts the *set* and
    reads the count as a second, weaker claim about it.

    Membership is derived from the tool names, never listed here: a tool's
    subject is its name with the verb prefix stripped, and the subject decides
    the category. So a twelfth tool lands in a category automatically, and a
    document that files it elsewhere fails.
    """
    root = _repo_root(pytestconfig)
    tools = _published_tools(root)
    expected = _expected_categories(tools)

    assert sum(len(members) for members in expected.values()) == len(tools), (
        "the derived categories do not partition the published tool list"
    )

    problems: list[str] = []
    headings_seen = 0
    for doc in _live_docs(root):
        text = _strip_fences(doc.read_text(encoding="utf-8"))
        for category in _categories_in(text):
            headings_seen += 1
            title, claimed = category.title, category.claimed
            members = expected[title]
            listed = _tool_names_in(_section_body(text, category))
            where = (
                f"{doc.relative_to(root)}:{text[: category.start].count(chr(10)) + 1}"
            )
            if claimed is not None and claimed != len(members):
                problems.append(
                    f"{where} claims {title} ({claimed}) but the published "
                    f"inventory puts {len(members)} tools there"
                )
            if listed and listed != members:
                problems.append(
                    f"{where} files {sorted(listed)} under {title}, but that "
                    f"category is {sorted(members)}"
                )

    assert headings_seen >= 6, (
        f"found only {headings_seen} category headings, so this invariant would "
        "pass by scanning almost nothing."
    )
    assert not problems, (
        "These category headings disagree with the published tool inventory:\n  "
        + "\n  ".join(problems)
        + "\nThe inventory is the source of truth; move the tool in the document, "
        "or change the tool's name if its subject really changed."
    )


#: A prose claim about the size of the whole inventory: "11 MCP tools", "11
#: tools", "(11 Total)". Lines announcing a *category* are excluded, because
#: ``docs/api/README.md`` writes its category sizes as "3 tools" in a table cell
#: and those are claims about a part, not the whole.
_TOTAL_CLAIM = re.compile(
    r"(\d+)\s+(?:MCP\s+)?tools\b|\((\d+)\s+Total\)", re.IGNORECASE
)

#: A prose claim about how many categories there are.
_CATEGORY_COUNT_CLAIM = re.compile(r"(\d+)\s+categories\b", re.IGNORECASE)


def _claims_in(text: str, titles: tuple[str, ...]) -> list[tuple[int, str, int]]:
    """Return ``(line number, kind, claimed number)`` for every count claim."""
    claims = []
    for number, line in enumerate(text.split("\n"), start=1):
        if any(title in line for title in titles):
            continue
        for match in _TOTAL_CLAIM.finditer(line):
            claims.append((number, "tools", int(match.group(1) or match.group(2))))
        for match in _CATEGORY_COUNT_CLAIM.finditer(line):
            claims.append((number, "categories", int(match.group(1))))
    return claims


def test_every_prose_count_claim_matches_the_published_inventory(
    pytestconfig: pytest.Config,
) -> None:
    """ "21 tools" was prose, and prose is where the last drift survived longest.

    The count in a sentence outlives the table it describes, because nothing
    about "provides 11 MCP tools" looks stale when a twelfth is added. This is
    the claim that was wrong last time, corrected by hand in nine files with no
    invariant attached, so it is the one most worth deriving.

    Category announcements are excluded: ``docs/api/README.md`` writes its
    category sizes as "3 tools" in a table cell, which is a claim about a part
    and is checked against that category's membership by the invariant above.
    Counting it as a claim about the whole would accuse a correct line.

    Starts green -- all fifteen claims are right today. That is exactly why the
    synthetic proof below exists: a scanner whose corpus contains no defect is
    indistinguishable from one that matches nothing.
    """
    root = _repo_root(pytestconfig)
    tools = _published_tools(root)
    expected = _expected_categories(tools)
    titles = (_FRAMEWORK_CATEGORY, _RISK_CATEGORY, _SYSTEM_CATEGORY)
    truth = {"tools": len(tools), "categories": len(expected)}

    wrong: list[str] = []
    claims_seen = 0
    for doc in _live_docs(root):
        text = _strip_fences(doc.read_text(encoding="utf-8"))
        for line_number, kind, claimed in _claims_in(text, titles):
            claims_seen += 1
            if claimed != truth[kind]:
                wrong.append(
                    f"{doc.relative_to(root)}:{line_number} claims {claimed} "
                    f"{kind}, but the server publishes {truth[kind]}"
                )

    # 9 since the duplicated pages went (#414); the floor notices a scanner
    # that reads nothing, it does not count copies.
    assert claims_seen >= 8, (
        f"found only {claims_seen} count claims, so this invariant would pass "
        "by scanning almost nothing."
    )
    assert not wrong, (
        "These documents state a count the server contradicts:\n  " + "\n  ".join(wrong)
    )


#: A line that *lists* a tool: a table row, list item, heading or bold numbered
#: entry that opens with its name, in backticks or bare. A tool named in the
#: middle of a sentence ("Use `list_risks` to see...") is a use of the name and
#: not an entry, which is what lets a page of use cases cover the whole surface
#: without being a copy of the table.
_INVENTORY_ENTRY = re.compile(
    r"^(?:\|\s*|\s*[-*]\s+|#{1,6}\s+(?:\d+\.\s+)?|\*\*\d+\.\s+)"
    r"`?((?:list|get|search)_[a-z_]+)\b",
    re.MULTILINE,
)


def _tools_listed_in(text: str) -> set[str]:
    return set(_INVENTORY_ENTRY.findall(text))


#: The live documents that carry a *complete* inventory -- an entry for every
#: published tool in one file. There were eight, all typed by hand (#66).
#: ``docs/api/mcp-tools.md`` is the one reference, held to the server by
#: ``test_tools_reference_matches_server.py``, and ``README.md`` holds a table
#: ``scripts/generate-tool-table.py`` writes. Nothing else lists the tools.
#: Frozen so another copy cannot arrive quietly, and asserted in both
#: directions so that dropping one has to come here and say so.
_DOCUMENTS_CARRYING_A_FULL_INVENTORY = frozenset(
    {
        "README.md",
        "docs/api/mcp-tools.md",
    }
)


def test_no_further_document_duplicates_the_whole_tool_inventory(
    pytestconfig: pytest.Config,
) -> None:
    """Every copy of the inventory is a place the next rename has to reach.

    The invariants above check that the copies *agree*; none of them limits how
    many there are, and a new one would pass all of them on the day it landed
    and drift on some later day. Nine copies were hand-corrected once already,
    which bought months (#47, #66).

    So this pins the set. Adding a document that lists every tool fails until
    someone decides that is really what they want, and *removing* one fails
    too, so a consolidation has to come here and say so.

    **Residual, stated rather than implied.** "Carries an inventory" means an
    entry per tool: a table row, list item or heading that opens with the name
    (``_INVENTORY_ENTRY``). A document that names every tool inside sentences
    or ``tool(...)`` call examples is not counted --
    ``docs/user-guide/getting-started.md`` and the use cases in
    ``docs/README.md`` do -- because counting those would make the remedy "use
    fewer examples". Their names are still held to the server by the name
    invariant above.
    """
    root = _repo_root(pytestconfig)
    published = set(_published_tools(root))

    carrying = {
        str(doc.relative_to(root))
        for doc in _live_docs(root)
        if published <= _tools_listed_in(_strip_fences(doc.read_text(encoding="utf-8")))
    }

    assert carrying == set(_DOCUMENTS_CARRYING_A_FULL_INVENTORY), (
        "the set of documents carrying a complete tool inventory has changed.\n"
        f"  new copies: {sorted(carrying - _DOCUMENTS_CARRYING_A_FULL_INVENTORY)}\n"
        f"  gone: {sorted(_DOCUMENTS_CARRYING_A_FULL_INVENTORY - carrying)}\n"
        "A new copy is one more place the next rename has to reach: link to "
        "docs/api/mcp-tools.md instead. If a copy was removed, take it off the "
        "frozen list above."
    )


#: Backticked CamelCase names that are *not* this project's code, each with
#: whose they are. Asserted to still appear in the docs, so an entry cannot
#: outlive the sentence that needed it.
_EXTERNAL_SYMBOLS = {
    "JWTVerifier": "fastmcp's token verifier, named in deployment.md's auth section",
    "MCPError": "the mcp SDK's JSON-RPC error, caught in integration-guide.md",
    "ValueError": "Python's built-in, raised by ContentService.get_document",
    "FastMCP": "the fastmcp server class this project constructs",
}


def _defined_symbols(root: Path) -> set[str]:
    """Every class, function and module-level constant defined under ``src/``.

    The leading ``\\s*`` is load-bearing: without it ``^def`` matches only
    module-level functions, and every *method* is invisible. That made this
    scanner report ``ContentService.get_document`` as undefined while the
    method sat in ``content/service.py``.
    """
    defined: set[str] = set()
    for path in (root / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        defined |= set(
            re.findall(
                r"^\s*(?:class|def|async def)\s+([A-Za-z_][A-Za-z0-9_]*)",
                text,
                re.MULTILINE,
            )
        )
        defined |= set(
            re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)\s*[:=]", text, re.MULTILINE)
        )
    return defined


#: A backticked CamelCase identifier -- the shape a class name takes. Narrow on
#: purpose: snake_case would sweep up parameter names, settings and shell words,
#: and an invariant that accuses correct prose is worse than no invariant.
_BACKTICKED_CLASS = re.compile(r"`([A-Z][A-Za-z0-9]*[a-z][A-Za-z0-9]*)`")

#: Language literals that match the CamelCase shape and are not class
#: references. ``None`` is the one that matters: documenting that a function
#: returns ``None`` rather than raising is exactly the kind of true, useful
#: sentence this invariant must not accuse.
_NOT_A_CLASS = frozenset({"None", "True", "False"})


def test_every_class_named_in_the_docs_exists_in_the_source(
    pytestconfig: pytest.Config,
) -> None:
    """Documentation of code that does not exist is worse than none of it.

    ``docs/api/framework-architecture.md`` described a design this codebase has
    never had: ``FrameworkDataLoader``, ``FrameworkQueryEngine``,
    ``CrossFrameworkMapper``, an ``ExportEngine`` and a ``handle_framework_tool``
    entry point, plus two dataclasses and two ``ContentService`` methods that do
    not exist (#65). A reader cannot tell an architecture document that is out
    of date from one that was never true, so they trust it and lose.

    Scoped to backticked CamelCase, which is what a class reference looks like
    in prose. The measurement that justifies the scope: across every live
    document there are nine such names, and before this invariant five resolved
    in ``src/`` and four did not -- three of them the fictions above. That is a
    small enough surface to check exactly and a low enough noise floor to be
    worth asserting.

    Definition detection is deliberately loose -- any ``class``/``def`` name or
    module-level binding under ``src/`` counts, with no attempt to resolve the
    module a document meant. A stricter rule would need the docs to spell out
    import paths they do not use, and the failure this catches is a name that
    exists *nowhere*.
    """
    root = _repo_root(pytestconfig)
    defined = _defined_symbols(root)

    assert len(defined) >= 200, (
        f"the source scanner found only {len(defined)} definitions under src/, "
        "so it is not reading the tree and every check below would pass "
        "vacuously. This is a count rather than a list of expected names on "
        "purpose: naming one class here means renaming that class trips this "
        "assertion instead of the one the rename should trip."
    )

    unknown: dict[str, list[str]] = {}
    names_seen = 0
    for doc in _live_docs(root):
        text = _strip_fences(doc.read_text(encoding="utf-8"))
        found = set(_BACKTICKED_CLASS.findall(text))
        names_seen += len(found)
        missing = sorted(found - defined - set(_EXTERNAL_SYMBOLS) - _NOT_A_CLASS)
        if missing:
            unknown[str(doc.relative_to(root))] = missing

    assert names_seen >= 5, (
        f"found only {names_seen} backticked class names, so this invariant "
        "would pass by scanning almost nothing."
    )
    assert not unknown, (
        f"These documents name classes that do not exist in src/: {unknown}. "
        "Either the symbol was renamed and the document was not updated, or the "
        "document is describing something that was never built. If the name "
        "belongs to a dependency, record it in _EXTERNAL_SYMBOLS with whose it is."
    )


def test_the_external_symbol_register_dies_by_removal(
    pytestconfig: pytest.Config,
) -> None:
    """An exemption must expire when the sentence that needed it is deleted.

    ``_EXTERNAL_SYMBOLS`` is the escape hatch for names this project documents
    but does not define. Left unchecked it would accumulate: every future false
    positive has "add one more entry" as its cheapest remedy, and the register
    would become the exclusion list this repository has had to unwind twice.
    """
    root = _repo_root(pytestconfig)
    documented: set[str] = set()
    for doc in _live_docs(root):
        documented |= set(
            _BACKTICKED_CLASS.findall(_strip_fences(doc.read_text(encoding="utf-8")))
        )

    stale = sorted(set(_EXTERNAL_SYMBOLS) - documented)
    assert not stale, (
        f"_EXTERNAL_SYMBOLS exempts names no live document mentions: {stale}. "
        "Delete the entry along with the sentence that needed it."
    )


#: Phrasings that deny a relationship with FINOS. Narrow on purpose: the claim
#: being forbidden is *non-affiliation*, not every use of the word independent.
_AFFILIATION_DENIALS = (
    "not officially affiliated",
    "not affiliated with finos",
    "unaffiliated with finos",
    "independent project",
)


def test_affiliation_guard_accepts_personal_copyright(
    tmp_path: Path, pytestconfig: pytest.Config
) -> None:
    """Copyright ownership is independent of the retained FINOS charter."""
    root = _repo_root(pytestconfig)
    (tmp_path / "NOTICE").write_text("Copyright 2025 FINOS\n", encoding="utf-8")
    (tmp_path / "CONTRIBUTING.md").write_text(
        (root / "CONTRIBUTING.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("# MCP server\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, timeout=10)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, timeout=10)
    # Exercise the same entry point as the real-repository guard. The small
    # config object only supplies pytest's filesystem boundary.
    test_no_document_denies_the_retained_finos_governance(
        cast(pytest.Config, SimpleNamespace(rootpath=tmp_path))
    )


def test_no_document_denies_the_retained_finos_governance(
    pytestconfig: pytest.Config,
) -> None:
    """Personal copyright and FINOS governance can coexist (#80).

    The retained charter, not the owner named in NOTICE, is the source of this
    contract. Its IP-policy and CLA clauses must remain explicit. Merely
    crediting FINOS content is no evidence of software ownership or governance.
    This is a narrow prose-drift guard, not a general affiliation classifier.
    """
    root = _repo_root(pytestconfig)
    charter = (root / "CONTRIBUTING.md").read_text(encoding="utf-8")
    paragraphs = [" ".join(p.split()) for p in charter.split("\n\n")]
    assert any(
        "The project is also governed by" in p
        and "FINOS [IP Policy]" in p
        and "https://community.finos.org/governance-docs/IP-policy.pdf" in p
        for p in paragraphs
    ), "CONTRIBUTING.md no longer declares governance under the FINOS IP Policy"
    assert any(
        "All contributors must have a contributor license agreement (CLA) on file with FINOS"
        in p
        and "before their pull requests will be merged" in p
        for p in paragraphs
    ), "CONTRIBUTING.md no longer requires a FINOS CLA before merge"

    offenders: dict[str, list[str]] = {}
    for doc in _live_docs(root):
        text = doc.read_text(encoding="utf-8").lower()
        found = [phrase for phrase in _AFFILIATION_DENIALS if phrase in text]
        if found:
            offenders[str(doc.relative_to(root))] = found

    assert not offenders, (
        f"These documents deny a relationship with FINOS while "
        f"CONTRIBUTING.md retains FINOS governance and its CLA requirement: "
        f"{offenders}. Say what is actually true -- the framework documents are "
        "FINOS's work under CC BY 4.0 and the server is a separate Apache-2.0 "
        "implementation -- rather than denying the affiliation."
    )


#: A fenced ``json`` block and its body.
_JSON_FENCE = re.compile(r"^```json\n(.*?)^```", re.MULTILINE | re.DOTALL)

#: An object whose first key is ``error``: the shape the docs invented.
_ERROR_OBJECT = re.compile(r'\A\s*\{\s*"error"\s*:')


def _error_objects_in(text: str) -> list[int]:
    """Line numbers of the JSON examples that open with an ``error`` key."""
    return [
        text.count("\n", 0, block.start()) + 1
        for block in _JSON_FENCE.finditer(text)
        if _ERROR_OBJECT.match(block.group(1))
    ]


def test_no_live_document_shows_an_error_object_the_server_never_sends(
    pytestconfig: pytest.Config,
) -> None:
    """A failed tool call is a result with ``isError: true`` and a text block.

    Two documents showed ``{"error": {"code": "VALIDATION_ERROR", ...}}`` and
    ``{"error": ..., "message": ..., "details": ...}``. A client written to
    those examples reads a key that never arrives (#217).

    Closes the route by which it was written, an example in a ``json`` fence.
    It does not read prose, so a sentence describing such an object passes.
    """
    root = _repo_root(pytestconfig)
    documents = _live_docs(root)
    assert documents, "no live document was scanned"

    offenders = {
        str(document.relative_to(root)): lines
        for document in documents
        if (lines := _error_objects_in(document.read_text(encoding="utf-8")))
    }

    assert not offenders, (
        f'these JSON examples open with an "error" key: {offenders}. No tool, '
        "resource or prompt returns that object. Show the result a client "
        "session receives."
    )


#: ``#123`` or ``PR #88``: a development-tracker number. ``#L10``-style anchors
#: and Markdown headings (``#`` then a space) do not match.
_TRACKER_NUMBER = re.compile(r"(?<![\w/&])#\d{2,4}\b")


def test_no_user_document_cites_a_development_tracker_number(
    pytestconfig: pytest.Config,
) -> None:
    """The user docs say what is true, not which issue made it so (#414).

    The numbers are the fork's issue tracker, which an upstream reader cannot
    open. Code and tests keep them; CONTRIBUTING.md is the FINOS charter and
    is not scanned here.
    """
    root = _repo_root(pytestconfig)
    documents = [d for d in _live_docs(root) if d.name != "CONTRIBUTING.md"]
    assert len(documents) >= 10, f"only {len(documents)} user documents were read"

    cited = {
        f"{document.relative_to(root)}:{number}": match.group()
        for document in documents
        for number, line in enumerate(
            document.read_text(encoding="utf-8").splitlines(), 1
        )
        for match in _TRACKER_NUMBER.finditer(line)
    }
    assert not cited, f"these lines cite a tracker number: {cited}"


def _github_anchor(heading: str) -> str:
    """The id GitHub gives a heading: lowercase, punctuation dropped, spaces to -."""
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def test_every_relative_link_in_a_live_document_resolves(
    pytestconfig: pytest.Config,
) -> None:
    """Each topic lives in one document and the others link to it (#414).

    A link is then the only route to the topic, so a moved file or a renamed
    heading breaks the route without a word. Links inside code fences are not
    links and are skipped.
    """
    root = _repo_root(pytestconfig)
    documents = _live_docs(root)
    texts = {
        d.resolve(): re.sub(r"```.*?```", "", d.read_text("utf-8"), flags=re.DOTALL)
        for d in documents
    }
    anchors = {
        path: {_github_anchor(h) for h in re.findall(r"^#+ (.+)$", text, re.M)}
        for path, text in texts.items()
    }

    links = 0
    broken = []
    for path, text in texts.items():
        for link in re.findall(r"\]\(([^)\s]+)\)", text):
            if re.match(r"[a-z]+:", link):
                continue
            links += 1
            target_name, _, anchor = link.partition("#")
            target = (path.parent / target_name).resolve() if target_name else path
            where = f"{path.relative_to(root)} -> {link}"
            if not target.exists():
                broken.append(f"{where} (no such file)")
            elif anchor and target in anchors and anchor not in anchors[target]:
                broken.append(f"{where} (no such heading)")
    assert links >= 40, f"only {links} relative links were read"
    assert not broken, f"these links lead nowhere: {broken}"


def test_every_json_example_in_a_live_document_parses(
    pytestconfig: pytest.Config,
) -> None:
    """A reader copies a ``json`` block into a client configuration (#410).

    The troubleshooting guide's block carried a ``// Use full path`` comment, so
    the configuration it showed did not load.
    """
    root = _repo_root(pytestconfig)
    blocks = []
    for document in _live_docs(root):
        text = document.read_text(encoding="utf-8")
        blocks += [
            (f"{document.relative_to(root)}:{text.count(chr(10), 0, b.start()) + 1}", b)
            for b in _JSON_FENCE.finditer(text)
        ]
    assert len(blocks) >= 10, f"only {len(blocks)} json blocks were read"

    broken = []
    for where, block in blocks:
        try:
            json.loads(block.group(1))
        except json.JSONDecodeError as error:
            broken.append(f"{where}: {error}")
    assert not broken, f"these json blocks do not parse: {broken}"


def test_the_error_reference_quotes_the_sentences_the_server_writes(
    pytestconfig: pytest.Config,
) -> None:
    """The quoted messages and codes are built here from what produces them.

    The reference was wrong because it was typed from an idea of the server.
    Each sentence below comes from the exception class a client's message is
    taken from, so rewording one fails this until the reference follows.
    """
    from mcp.types import INTERNAL_ERROR, INVALID_PARAMS

    from finos_mcp.exceptions import (
        DocumentUnavailableError,
        SearchFailedError,
        UnknownDocumentError,
    )
    from finos_mcp.security.dos_middleware import _RATE_LIMIT_ERROR_CODE

    reference = (_repo_root(pytestconfig) / "docs/api/response-schemas.md").read_text(
        encoding="utf-8"
    )

    sentences = [
        UnknownDocumentError("does-not-exist", "risk", "list_risks").message,
        *(
            DocumentUnavailableError("<id>", "risk", reason).message
            for reason in (
                DocumentUnavailableError.NOT_LOADED,
                DocumentUnavailableError.TOO_LARGE,
                DocumentUnavailableError.EMPTY,
            )
        ),
        SearchFailedError(SearchFailedError.NOTHING_READ).message,
        SearchFailedError(SearchFailedError.UNEXPECTED).message,
    ]
    missing = [sentence for sentence in sentences if sentence not in reference]
    assert not missing, (
        f"docs/api/response-schemas.md does not quote these messages: {missing}"
    )

    codes = {
        "an unknown id on a resource": INVALID_PARAMS,
        "a document that could not be served": INTERNAL_ERROR,
        "a request over the server's limits": _RATE_LIMIT_ERROR_CODE,
    }
    unquoted = {
        what: code for what, code in codes.items() if f"`{code}`" not in reference
    }
    assert not unquoted, (
        f"docs/api/response-schemas.md does not give these JSON-RPC codes: {unquoted}"
    )


_SYNTHETIC_ERROR_OBJECT = """
# Errors

```json
{
  "error": {"code": "VALIDATION_ERROR"}
}
```

```json
{
  "isError": true,
  "content": [{"type": "text", "text": "an \"error\": inside a real result"}]
}
```
"""

_SYNTHETIC_DEAD_NAME = """
# Tools

- `get_framework_content` - a tool this server has never published
"""

_SYNTHETIC_NEVER_BUILT = """
```python
mcp_client.call_tool("export_framework_data", {})
```

Not the same identifiers: `get_risk_details_v2`, `my_list_all_risks`.

Escaped for Markdown, and rendered as the name: get\\_risk\\_details.
"""

_SYNTHETIC_WRONG_COUNT = """
## Framework Access Tools (5)

- `list_frameworks` - fine
- `get_framework` - fine
- `search_frameworks` - fine
"""

_SYNTHETIC_WRONG_MEMBERSHIP = """
## Framework Access Tools (3)

- `list_frameworks` - fine
- `get_framework` - fine
- `get_risk` - filed under the wrong category
"""

_SYNTHETIC_WRONG_TOTAL = """
The server provides 21 MCP tools organized in 3 categories.
"""

_SYNTHETIC_CATEGORY_SIZE = """
| **Framework Access Tools** | 3 tools | a claim about a part, not the whole |
"""

_SYNTHETIC_SUBHEADINGS = """
## Framework Access Tools (3)

### `list_frameworks`
Fine.

### `get_risk`
Filed under the wrong category, and only visible if the section contains its
sub-headings.

## Risk & Mitigation Tools (6)
"""

#: One entry in each shape the eight copies used, then two names that are used
#: in a sentence and must not count.
_SYNTHETIC_ENTRIES = """
| `list_frameworks` | List the frameworks |
| get_framework | 50-500KB | 1MB |
- `search_frameworks` - Find a phrase
### `list_risks`
### 5. get_risk Response
**9. get_cache_stats** - Cache statistics

- **Browse**: Use `list_mitigations` to see them all
1. *"Check service health"* -> Uses `get_service_health`
"""

#: Four response times, then two cache lifetimes, then three lines that state
#: neither: a duration that is not about a cache, a number that is not a
#: duration, and a client-side example.
_SYNTHETIC_TIMINGS = """
- **Cached content**: <0.1ms response time
| Search operations | 10-100ms | 200-1000 ms |
- Sub-5 milliseconds for a listing
Answers in 250 microseconds.
- Risk/mitigation lists: Cached for 30 minutes
The cache holds search results for 15-minute periods.
## Quick Start (5 minutes)
- `FINOS_MCP_CACHE_MAX_SIZE` is 1000 by default
self.cache_ttl = timedelta(minutes=30)
"""

_SYNTHETIC_FENCED_COMMENT = """
## Framework Access Tools (3)

```python
# Request
mcp_client.call_tool("list_frameworks", {})
```
"""


def test_the_scanners_reject_synthetic_false_claims() -> None:
    """A scanner that finds nothing looks exactly like a corpus with no defects.

    Both invariants above pass today only because the documents are correct. If
    a regex stopped matching -- a heading gained a colon, backticks became bold
    -- they would keep passing, and the silence would read as health. So each
    scanner is run here against a document written to be wrong, and must say so.

    These are deliberately exercised against synthetic strings rather than
    against the real tree, for the same reason the pip-audit suppression policy
    in ``test_ci_config_drift.py`` is: a check that only ever inspects correct
    data never runs the rule it claims to enforce.
    """
    assert _error_objects_in(_SYNTHETIC_ERROR_OBJECT) == [4], (
        "the error-object scanner no longer finds an example that opens with an "
        '"error" key, or now accuses a real result that merely contains the word'
    )

    published = {"list_frameworks", "get_framework", "search_frameworks", "get_risk"}

    assert _tool_names_in(_SYNTHETIC_DEAD_NAME) - published == {
        "get_framework_content"
    }, "the name scanner no longer detects a tool name the server does not publish"

    assert _never_implemented_in(
        {"fenced.md": _SYNTHETIC_NEVER_BUILT, "clean.md": _SYNTHETIC_WRONG_COUNT}
    ) == {"fenced.md": ["export_framework_data", "get_risk_details"]}, (
        "the never-built scanner no longer finds a register name inside fenced "
        "code or behind escaped underscores, or now matches a longer identifier "
        "that merely contains one"
    )

    wrong_count = _CATEGORY_IN_HEADING.search(_SYNTHETIC_WRONG_COUNT)
    assert wrong_count is not None, "the heading scanner no longer matches a heading"
    assert wrong_count.group(3) == "5", "the heading scanner no longer reads the count"
    assert len(_tool_names_in(_SYNTHETIC_WRONG_COUNT)) == 3, (
        "the heading scanner no longer reads a category's members"
    )

    membership = _CATEGORY_IN_HEADING.search(_SYNTHETIC_WRONG_MEMBERSHIP)
    assert membership is not None
    assert _tool_names_in(_SYNTHETIC_WRONG_MEMBERSHIP) != {
        "list_frameworks",
        "get_framework",
        "search_frameworks",
    }, "the membership scanner no longer distinguishes a misfiled tool"

    titles = (_FRAMEWORK_CATEGORY, _RISK_CATEGORY, _SYSTEM_CATEGORY)
    assert _claims_in(_SYNTHETIC_WRONG_TOTAL, titles) == [
        (2, "tools", 21),
        (2, "categories", 3),
    ], "the count scanner no longer reads a prose total"
    assert _claims_in(_SYNTHETIC_CATEGORY_SIZE, titles) == [], (
        "the count scanner now reads a category's size as a claim about the "
        "whole inventory, which would accuse a correct line"
    )

    nested = _SYNTHETIC_SUBHEADINGS
    category = _categories_in(nested)[0]
    assert _tool_names_in(_section_body(nested, category)) == {
        "list_frameworks",
        "get_risk",
    }, (
        "a category no longer contains its sub-headings, so a document that "
        "gives each tool its own ### section is no longer checked"
    )

    assert _tools_listed_in(_SYNTHETIC_ENTRIES) == {
        "list_frameworks",
        "get_framework",
        "search_frameworks",
        "list_risks",
        "get_risk",
        "get_cache_stats",
    }, (
        "the entry scanner no longer reads every shape a listing takes, or now "
        "counts a tool named inside a sentence as an entry"
    )

    assert _response_times_in(_SYNTHETIC_TIMINGS) == [2, 3, 4, 5], (
        "the response-time scanner no longer reads every spelling of a time in "
        "milliseconds, or now accuses a line that states none"
    )
    assert _cache_lifetimes_in(_SYNTHETIC_TIMINGS) == [(6, 1800), (7, 900)], (
        "the lifetime scanner no longer reads a duration beside the word cache, "
        "or now reads a duration that is not about a cache"
    )

    unstripped = _ANY_HEADING.findall(_SYNTHETIC_FENCED_COMMENT)
    assert len(unstripped) == 2, (
        "the synthetic no longer contains both a real heading and a # comment "
        "inside a fence, so it cannot demonstrate the difference"
    )
    assert len(_ANY_HEADING.findall(_strip_fences(_SYNTHETIC_FENCED_COMMENT))) == 1, (
        "a # comment inside a fenced code block is still being read as a "
        "heading, which truncates the section it falls inside"
    )


def test_the_category_derivation_covers_every_published_tool(
    pytestconfig: pytest.Config,
) -> None:
    """The derivation must not quietly file an unrecognised tool as machinery.

    ``_category_of`` falls back to "System Monitoring Tools" for any subject it
    does not recognise, which is right for ``get_service_health`` and
    ``get_cache_stats`` and wrong for a future ``list_controls``. The fallback
    is what makes the rule total, so it needs a bound: the two tools that land
    there today are named, and a third arriving fails this until someone decides
    which category it belongs to.
    """
    root = _repo_root(pytestconfig)
    tools = _published_tools(root)
    machinery = {tool for tool in tools if _category_of(tool) == _SYSTEM_CATEGORY}

    assert machinery == {"get_service_health", "get_cache_stats"}, (
        f"these tools fall through to {_SYSTEM_CATEGORY!r}: {sorted(machinery)}. "
        "The fallback exists for service machinery, not for document tools whose "
        "subject _CATEGORY_BY_SUBJECT does not name yet -- add the subject there "
        "if a new document kind was published."
    )


# --- Invariants 10 and 11: numbers and examples with a source (#236) ---------

_RESPONSE_SCHEMAS = "docs/api/response-schemas.md"

#: A figure in milliseconds or finer, the unit a response time is quoted in,
#: or the same said without a figure: ``<0.1ms``, ``200 msec``, ``sub-millisecond``.
_RESPONSE_TIME = re.compile(
    r"\d\s?(?:ms|msecs?|µs|ns|(?i:milli|micro|nano)seconds?)\b"
    r"|(?i:\bsub-?(?:milli|micro)second)"
)

#: A whole number of seconds, minutes, hours or days: ``30 minutes``, ``1-hour``,
#: ``30 min``, ``15 mins``, ``90 secs``.
_DURATION = re.compile(
    r"\b(\d+)[ -]?(sec(?:ond)?|min(?:ute)?|hour|hr|day)s?\b", re.IGNORECASE
)
_SECONDS_IN = {"sec": 1, "min": 60, "hou": 3600, "hr": 3600, "day": 86400}

#: The words the docs use for a cache: the noun, and "kept" for what it does.
_MENTIONS_A_CACHE = re.compile(r"cach|\bkept\b|\bTTL\b|lifetime", re.IGNORECASE)


def _response_times_in(text: str) -> list[int]:
    """Line numbers that state a time in milliseconds or microseconds."""
    return [
        number
        for number, line in enumerate(text.splitlines(), start=1)
        if _RESPONSE_TIME.search(line)
    ]


def _durations_in(line: str) -> list[int]:
    """Each duration a line states, in seconds."""
    return [
        int(count) * _SECONDS_IN[unit.lower()[:3].rstrip("s")]
        for count, unit in _DURATION.findall(line)
    ]


def _cache_lifetimes_in(text: str) -> list[tuple[int, int]]:
    """``(line number, seconds)`` for each duration on a line that names a cache."""
    return [
        (number, seconds)
        for number, line in enumerate(text.splitlines(), start=1)
        if _MENTIONS_A_CACHE.search(line)
        for seconds in _durations_in(line)
    ]


def _section(text: str, heading: str) -> str:
    """The body under ``heading``, up to the next heading of any level."""
    start = text.index(f"{heading}\n") + len(heading) + 1
    following = _ANY_HEADING.search(_blank_fences(text), start)
    return text[start : following.start() if following else len(text)]


def _blank_fences(text: str) -> str:
    """``text`` with each fenced block overwritten by spaces, offsets kept."""
    return _FENCED_BLOCK.sub(lambda block: re.sub(r"[^\n]", " ", block.group(0)), text)


def _document_lifetime() -> SimpleNamespace:
    """The default and the bounds of the one document lifetime the server has."""
    from finos_mcp.config import Settings

    field = Settings.model_fields["cache_ttl_seconds"]
    bounds = {
        name: getattr(constraint, name)
        for constraint in field.metadata
        for name in ("ge", "le")
        if hasattr(constraint, name)
    }
    return SimpleNamespace(default=field.default, least=bounds["ge"], most=bounds["le"])


def _listing_lifetimes(monkeypatch: pytest.MonkeyPatch, directory: Path) -> set[int]:
    """How long the discovery service keeps the document list, debug off and on."""
    from finos_mcp.config import get_settings
    from finos_mcp.content import discovery

    lifetimes = set()
    for debug_mode in (False, True):
        settings = get_settings().model_copy(
            update={"debug_mode": debug_mode, "discovery_cache_dir": str(directory)}
        )
        monkeypatch.setattr(
            discovery, "get_settings", lambda settings=settings: settings
        )
        lifetimes.add(discovery.GitHubDiscoveryService().cache_duration_seconds)
    return lifetimes


def test_no_live_document_states_a_response_time(pytestconfig: pytest.Config) -> None:
    """No test or benchmark here produces a response time, so none is stated.

    Four documents stated response times, among them under 0.1ms for a cached
    answer and 10 to 100ms for a search. Nothing had measured any (#236).

    Closes the unit those figures were written in. A time stated in seconds,
    or in words, passes.
    """
    root = _repo_root(pytestconfig)
    documents = _live_docs(root)
    assert documents, "no live document was scanned"

    offenders = {
        str(document.relative_to(root)): lines
        for document in documents
        if (lines := _response_times_in(document.read_text(encoding="utf-8")))
    }

    assert not offenders, (
        f"these lines state a time in milliseconds: {offenders}. Nothing in the "
        "repository measures a response time. Remove the figure, or add the "
        "measurement that produces it and read the figure from there."
    )


def test_every_cache_lifetime_in_the_docs_is_one_the_code_has(
    pytestconfig: pytest.Config, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A lifetime in the docs is the document lifetime, a bound of it, or the listing's.

    The reference gave 30 minutes for the listings and 15 for search results.
    The server keeps a document for ``cache_ttl_seconds`` and the document list
    for an hour, and keeps no search result at all (#236).

    Under "Caching Behavior" each cache's row must state that cache's own
    lifetimes. Elsewhere this reads a whole number with a unit on a line that
    names a cache, and accepts any lifetime the code has, so a right figure
    beside the wrong cache passes there, and so does "for an hour" in words.
    """
    root = _repo_root(pytestconfig)
    document = _document_lifetime()
    listing = _listing_lifetimes(monkeypatch, tmp_path)
    in_the_code = {document.default, document.least, document.most} | listing

    documents = _live_docs(root)
    assert documents, "no live document was scanned"
    offenders = {
        str(path.relative_to(root)): wrong
        for path in documents
        if (
            wrong := [
                (line, seconds)
                for line, seconds in _cache_lifetimes_in(
                    path.read_text(encoding="utf-8")
                )
                if seconds not in in_the_code
            ]
        )
    }
    assert not offenders, (
        f"these (line, seconds) are cache lifetimes the code does not have: "
        f"{offenders}. The code has {sorted(in_the_code)} seconds."
    )

    caching = _section(
        (root / _RESPONSE_SCHEMAS).read_text(encoding="utf-8"), "### Caching Behavior"
    )
    stated = {
        seconds for line in caching.splitlines() for seconds in _durations_in(line)
    }
    assert stated <= in_the_code, (
        f"Caching Behavior states {sorted(stated - in_the_code)} seconds, which "
        f"no cache in the code has. The code has {sorted(in_the_code)}."
    )
    from finos_mcp.content.list_file import FILE_NAME

    rows = {
        "FINOS_MCP_CACHE_TTL_SECONDS": {document.default},
        FILE_NAME: listing,
    }
    for marker, lifetimes in rows.items():
        row = [line for line in caching.splitlines() if marker in line]
        assert len(row) == 1, f"Caching Behavior has {len(row)} rows naming {marker}"
        assert set(_durations_in(row[0])) == lifetimes, (
            f"the row naming {marker} states {sorted(set(_durations_in(row[0])))} "
            f"seconds and the code has {sorted(lifetimes)} for that cache."
        )
    for name, value in vars(document).items():
        assert f"`{value}`" in caching, (
            f"Caching Behavior does not give `{value}`, the {name} value of "
            "FINOS_MCP_CACHE_TTL_SECONDS."
        )


async def test_the_base_response_example_is_a_result_the_server_sends(
    pytestconfig: pytest.Config,
) -> None:
    """The example is compared with ``get_service_health`` from the assembled server.

    It showed ``content`` alone. A client written to it never read
    ``structuredContent``, which every tool sends (#236).

    Compares shape, not values: the uptime and the version differ per session.
    """
    from fastmcp import Client

    from finos_mcp.fastmcp_server import mcp

    section = _section(
        (_repo_root(pytestconfig) / _RESPONSE_SCHEMAS).read_text(encoding="utf-8"),
        "### Base Response Structure",
    )
    fence = _JSON_FENCE.search(section)
    assert fence is not None, "Base Response Structure has no json example"
    example = json.loads(fence.group(1))

    async with Client(mcp) as client:
        result = await client.call_tool_mcp("get_service_health", {})
    sent = result.model_dump(by_alias=True, exclude_none=True)
    assert sent["structuredContent"], "the server sent no structured content"

    assert set(example) <= set(sent), (
        f"the example has {sorted(set(example) - set(sent))}, which the server "
        "does not send"
    )
    assert "structuredContent" in example, "the example leaves out structuredContent"
    assert set(example["structuredContent"]) == set(sent["structuredContent"]), (
        "the example's structuredContent and the server's have different fields: "
        f"{sorted(set(example['structuredContent']) ^ set(sent['structuredContent']))}"
    )
    assert example["isError"] is sent["isError"] is False
    assert [block["type"] for block in example["content"]] == [
        block["type"] for block in sent["content"]
    ], "the example and the server send different content blocks"
    assert json.loads(example["content"][0]["text"]) == example["structuredContent"], (
        "the example's text block is not its structuredContent as JSON, which is "
        "what the server sends"
    )
    assert json.loads(sent["content"][0]["text"]) == sent["structuredContent"], (
        "the server's text block is no longer its structuredContent as JSON, so "
        "the sentence above the example is false"
    )
