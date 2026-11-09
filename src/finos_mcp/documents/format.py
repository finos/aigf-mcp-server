#!/usr/bin/env python3
# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Turning fetched documents into the names and bodies a tool returns.

Copyright 2025 FINOS

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import asyncio
import re
import sys
import unicodedata
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, NamedTuple

import yaml

from ..content.parse import (
    document_name_from_filename,
    fence_for,
    flatten_for_inline,
    frontmatter_title,
    opening_section_summary,
    parse_yaml_document,
    yaml_description_from_document,
    yaml_title_from_document,
)
from ..exceptions import ContentValidationError
from ..logging import get_logger
from ..service import get_service

logger = get_logger("documents.format")


def _format_framework_name(framework_id: str) -> str:
    """Format framework ID into a readable name."""
    # Only ids of frameworks this server ships belong here. Entries for
    # "gdpr" and "iso-23053" were carried for frameworks this server has never
    # served, so they could never be reached.
    # Every value here is the ``title`` the corresponding document declares,
    # measured against the live corpus. It used to be hand-written and
    # disagreed with the documents for **10 of the 13** -- "Assured Transparency
    # Reporting" for a document titled "Agent Threat Rules (ATR)", and "OWASP
    # Agentic Security Initiative" for "OWASP Top 10 for Agentic Applications",
    # which are not the same names for the same things.
    #
    # That mattered once get_framework started publishing the document's own
    # title: list_frameworks and get_framework then answered with two unrelated
    # names for one document in a single session. Aligning the map removes the
    # disagreement at zero runtime cost.
    #
    # It is still a hardcoded copy, and it will drift again the next time FINOS
    # retitles something. Sourcing these from the documents is #121; the
    # trade-off there is that a listing would have to fetch every document.
    name_map = {
        "atr": "Agent Threat Rules (ATR)",
        "canada-regulations": "Canada AI & Financial-Sector Regulatory References",
        "eu-ai-act": "EU AI Act",
        "ffiec-itbooklets": "FFIEC IT Examination Handbook",
        "iosco-supervisory-toolkit": (
            "IOSCO Supervisory Toolkit for AI Use in Capital Markets"
        ),
        "iso-42001": "ISO/IEC 42001",
        "nist-ai-600-1": "NIST AI 600-1",
        "nist-sp-800-53r5": "NIST SP 800-53 Rev 5",
        "owasp-asi": "OWASP Top 10 for Agentic Applications",
        "owasp-llm": "OWASP LLM Top 10",
        "owasp-ml": "OWASP ML Security Top 10",
        "sr11-7": "SR 11-7: Model Risk Management",
        "uk-regulations": "UK Financial Services AI Regulations",
    }

    return name_map.get(framework_id, framework_id.replace("-", " ").title())


#: The top-level key whose value is the framework's entries, by id.
_ENTRIES_KEY = "entries"

_NULL_TAG = "tag:yaml.org,2002:null"
#: Every way YAML writes a null. A scalar can be tagged one and say something
#: else, ``!!null kept secret``, and that is text the file wrote.
_NULLS = frozenset({"", "~", "null", "Null", "NULL"})
_STRING_TAG = "tag:yaml.org,2002:str"

#: A list number, the one thing that opens a Markdown block without starting
#: with punctuation.
_LIST_NUMBER = re.compile(r"\d{1,9}(?=[.)](\s|$))")

#: The characters that can open a Markdown block from the start of a line: a
#: heading, a quote, a list item, a rule, a setext underline, a fence, a table
#: row or its delimiter, an HTML block.
_BLOCK_OPENERS = frozenset("#>-+*=_~`|:<")

#: The longest body `get_framework` will serve; a longer one is replaced by an
#: error (`request_size_validator`).
_LONGEST_BODY = 1_000_000

#: A line of a commented-out entry, without its ``#``: the id, and a field.
_COMMENTED_ID = re.compile(r"\s*[^\s:#]+:")
_COMMENTED_FIELD = re.compile(r"\s*([\w-]+):(\s.*)?")
#: A word with a capital in it and nothing but letters, where an id would be:
#: ``See:``, ``NOTE:``. None of the 967 ids of the live files has that form
#: (2026-10-11); the 13 that are letters only are lower case.
_COMMENTED_LABEL = re.compile(r"\s*[A-Za-z]*[A-Z][A-Za-z]*:")
#: The fields a commented-out entry is known by; every live entry has both.
_NAMED = frozenset({"title", "url"})

#: A link reference definition. Only this much of a line that opens with a
#: bracket is structure; "[Draft] guidance" is text.
_LINK_DEFINITION = re.compile(r"\[[^\]]*\]:")


class _FrameworkDocument(NamedTuple):
    """What `get_framework` serves for one framework file."""

    body: str
    #: The entries the body lists; 0 for a file served as it was written.
    entries: int


class _Entry(NamedTuple):
    key: yaml.ScalarNode
    fields: list[tuple[str, yaml.ScalarNode]]


class _Shape(NamedTuple):
    """A framework file that can be written out in full."""

    fields: list[tuple[str, yaml.ScalarNode]]
    entries: list[_Entry]


def _inline(value: object) -> str:
    """A document value on one line and in full; "" if it has no such form."""
    return flatten_for_inline(value, limit=sys.maxsize)


def _is_null(node: yaml.Node) -> bool:
    """Whether `node` is a null that says nothing."""
    return (
        isinstance(node, yaml.ScalarNode)
        and node.tag == _NULL_TAG
        and _inline(node.value) in _NULLS
    )


def _said(node: yaml.ScalarNode) -> str:
    """What a scalar says, as the file wrote it; "" for a null.

    The text of the node, not the value it parses to: ``1.10`` is a version
    and ``no`` a word, and written out from the parse they were ``1.1`` and
    ``false``, and the ids ``"5.1"`` and ``5.1`` one entry.
    """
    return "" if _is_null(node) else _inline(node.value)


def _as_a_heading(title: str) -> str:
    """`title` as the heading shows it: no format characters, single spaces.

    What `content.parse._bounded_title` does to a title it accepts, so that
    the ``title`` field can be told from the heading above it. Written out
    from `_said` the two differed by a zero-width space, and the body read
    ``# AB`` over ``title: A B``.
    """
    seen = "".join(ch for ch in title if unicodedata.category(ch) != "Cf")
    return " ".join(seen.split())


def _line(text: str) -> str:
    """`text` as the start of a line that cannot open a Markdown block.

    The body is Markdown a model reads, and a description, a url or a field
    name is written at the start of a line of it. One beginning ``# `` or
    ``- `` would be a heading or a list item of the document's own making, so
    the character that would open the block is escaped. Anything else is left
    as written.
    """
    if text[:1] in _BLOCK_OPENERS or _LINK_DEFINITION.match(text):
        return "\\" + text
    numbered = _LIST_NUMBER.match(text)
    if numbered:
        return f"{numbered.group()}\\{text[numbered.end() :]}"
    return text


def _fields(node: yaml.Node) -> list[tuple[str, yaml.ScalarNode]] | None:
    """A mapping of one-line values as (key, value) pairs, else None.

    Nothing at all is a mapping of none: ``a:`` and ``a: {}`` are one entry.
    """
    if _is_null(node):
        return []
    if not isinstance(node, yaml.MappingNode):
        return None
    fields = []
    for key, value in node.value:
        if not isinstance(key, yaml.ScalarNode) or not _said(key):
            return None
        if not isinstance(value, yaml.ScalarNode):
            return None
        fields.append((_said(key), value))
    return fields


def _framework_shape(root: yaml.Node | None, size: int) -> _Shape | None:
    """`root` as a framework that can be written out in full, else None.

    A framework is a mapping of one-line values plus ``entries``, which maps
    an id to a mapping of one-line values; every live file is. The answer is
    for the whole file: one list nested in one entry and the file is served as
    it was written, because writing out the part that fits would drop the part
    that does not. A framework with no entries has the shape, and none.

    `size` is the length of the file. A file cannot say more than it is long
    unless it says something many times over through an alias, and written out
    that was 400MB from a file of 200KB. An alias that fits in a body this
    server would serve is written out; past that the file is served as it was
    written, and the count stops there too, since walking what one alias
    repeats took 25 seconds on its own.
    """
    if not isinstance(root, yaml.MappingNode):
        return None
    shape = _Shape([], [])
    room = max(size, _LONGEST_BODY)
    seen_entries = False
    for key, value in root.value:
        if not isinstance(key, yaml.ScalarNode) or not _said(key):
            return None
        if key.value != _ENTRIES_KEY:
            if not isinstance(value, yaml.ScalarNode):
                return None
            shape.fields.append((_said(key), value))
            room -= len(key.value) + len(value.value)
            continue
        if seen_entries:
            return None
        seen_entries = True
        if _is_null(value):
            continue
        if not isinstance(value, yaml.MappingNode):
            return None
        for entry_id, entry in value.value:
            fields = _fields(entry)
            if fields is None or not isinstance(entry_id, yaml.ScalarNode):
                return None
            if not _said(entry_id):
                return None
            shape.entries.append(_Entry(entry_id, fields))
            room -= len(entry_id.value)
            room -= sum(len(name) + len(node.value) for name, node in fields)
            if room < 0:
                return None
    return shape if room >= 0 else None


def _comment(line: str, indent: int) -> str | None:
    """What a comment line at `indent` says, or None if it is not a comment.

    "" for a blank line, a rule, and a comment at another indent: that one
    belongs to whatever is written at its own depth, and the comment beyond it
    is still read.
    """
    text = line.strip()
    if not text:
        return ""
    if not text.startswith("#"):
        return None
    if len(line) - len(line.lstrip()) != indent:
        return ""
    text = text.strip("#").strip()
    return text if any(map(str.isalnum, text)) else ""


def _commented_out(lines: list[str]) -> bool:
    """Whether the comment `lines` are entries with a ``#`` in front of them.

    ``# b:`` over ``#   title: old`` is YAML the file no longer says, and as
    a heading it read ``## b: title: old``. It is told from a comment by its
    lines alone: an id of one word with nothing after it, then lines set
    further in that each name a field, a ``title`` and a ``url`` among them.
    Every entry of the live files has both. A colon is not enough --
    ``# Section: Model Validation`` heads a group in `sr11-7` -- and neither
    is a label over one such line, ``# See:`` over ``#   url: ...``. Nor is a
    capitalised word over both fields: ``# See:`` over a ``title`` and a
    ``url`` is a reference someone wrote, and was dropped (#263).

    Not parsed. As YAML ``# Tier 1:`` over ``#   Scope: banks`` is an entry
    too, and was dropped; and a comment of nested brackets cost what parsing
    them costs, 19 seconds for a file under 1MB.

    The rule is narrow on purpose: a comment dropped by mistake is gone
    without a trace, and a commented-out entry shown by mistake is a strange
    heading a reader can see. So an entry commented out in any other shape
    is still written as a comment -- one beside a remark in the same run of
    lines, one without a title or without a url, one with a value over
    several lines, a quoted id with a space in it, the flow form
    ``b: {title: old}``, an id that is a capitalised word.
    """
    written = [line.strip().lstrip("#").rstrip() for line in lines]
    depth = [len(line) - len(line.lstrip()) for line in written]
    named: set[str] = set()
    for index, line in enumerate(written):
        if depth[index] == depth[0]:
            # An id, and the entry before it was a whole one.
            if not _COMMENTED_ID.fullmatch(line) or (index and not named >= _NAMED):
                return False
            if _COMMENTED_LABEL.fullmatch(line):
                return False
            named = set()
            continue
        field = _COMMENTED_FIELD.fullmatch(line)
        if depth[index] < depth[0] or not field:
            return False
        named.add(field.group(1))
    return named >= _NAMED


def _comments_in(lines: list[str], indent: int) -> str:
    """What the comment `lines` say, on one line.

    A blank line, a rule or a comment at another indent ends one run of
    lines and begins the next, and a run that is a commented-out entry says
    nothing (`_commented_out`).
    """
    said: list[str] = []
    run: list[str] = []
    for line in [*lines, ""]:
        if _comment(line, indent):
            run.append(line)
            continue
        if not _commented_out(run):
            said.extend(_comment(each, indent) or "" for each in run)
        run = []
    return _inline(" ".join(said))


def _comments_from(lines: list[str]) -> list[str]:
    """The lines `lines` opens with that are comments or blank."""
    opening = []
    for line in lines:
        if line.strip() and not line.strip().startswith("#"):
            break
        opening.append(line)
    return opening


def _entry_comments(lines: list[str], entries: list[_Entry]) -> list[str]:
    """The comment above each entry, then the comment after the last one.

    A comment is the only grouping these files have -- ``# Section: Model
    Validation``, ``# 2025 edition (superseded ...)`` -- and a parse drops it.
    The lines of one comment are joined; a rule of dashes says nothing and is
    passed over.

    Only the lines between two entries are read, by the marks of the nodes
    either side, and only at the indent the ids are written at. The last line
    of a block scalar or of a quoted title can begin with ``#`` too, and is
    inside the entry above.

    Comments anywhere else -- after a value, between the fields of an entry,
    above the title -- are not read. Reading them means finding where a
    comment begins, which a ``#`` inside a quoted or a block value does not
    say and the parser does not keep; the marks of two entries bound the
    lines between them and nothing bounds the rest. Every worded comment
    line of the live files, 41 on 2026-10-10, is above an entry or after the
    last one (#214).
    """
    comments = []
    floor = indent = 0
    for entry in entries:
        first = entry.key.start_mark.line
        indent = len(lines[first]) - len(lines[first].lstrip())
        above = _comments_from(lines[floor:first][::-1])[::-1]
        comments.append(_comments_in(above, indent))
        # Where the entry's last value ends. A block scalar ends at the start
        # of the line after it, anything else part-way along its own.
        end = (entry.fields[-1][1] if entry.fields else entry.key).end_mark
        floor = max(first + 1, end.line if end.column == 0 else end.line + 1)
    after = _comments_from(lines[floor:]) if entries else []
    return [*comments, _comments_in(after, indent)]


def _entry_lines(entry: _Entry) -> list[str]:
    """One entry as a list item: its id and title, then a line for each field."""
    title = url = description = ""
    named = []
    for name, node in entry.fields:
        text = _said(node)
        if not text:
            continue
        if name == "title" and not title:
            title = text
        elif name == "description" and not description:
            description = text
        elif name == "url" and not url and node.tag == _STRING_TAG:
            # A url that is a number is a field like any other: on a line of
            # its own it would read as a link.
            url = text
        else:
            named.append(f"{name}: {text}")
    # An id of asterisks alone would close the emphasis and leave a rule.
    key = _said(entry.key).replace("*", "\\*")
    rest = [text for text in (url, *named, description) if text]
    return [
        f"- **{key}**" + (f": {title}" if title else ""),
        *(f"  {_line(text)}" for text in rest),
    ]


def _framework_document(yaml_content: str, display_title: str) -> _FrameworkDocument:
    """A framework file as the document `get_framework` serves.

    The title, the description, the source, then each entry under its id, with
    the comment above an entry as a heading. Apart from the label ``Source:``
    and the names of the fields, nothing is written that the file does not
    say: this used to list the top-level keys as "main sections", head the
    entries ``### entries: entries`` and append the whole file in a code fence
    (#192).

    Every value is flattened onto one line and cannot open a block of its own
    (`_line`). A file that failed to parse, or is not shaped like a framework
    (`_framework_shape`), is served as written inside a fence it cannot close.

    Read from the node tree, not from the parse the caller holds for the
    title: the tree has each scalar as the file wrote it and the line it is
    on, which is what the comments are found by. That is a second pass over
    the file, and like the first it must run off the event loop.

    Takes the already-resolved display title rather than deriving its own from
    the id. The heading and the ``title`` field must not disagree: sourcing the
    field from the document while the heading came from the name map would have
    made `get_framework("atr")` answer "Agent Threat Rules (ATR)" above a body
    headed "Assured Transparency Reporting", contradicting itself in a single
    payload.
    """
    fence = fence_for(yaml_content)
    as_written = _FrameworkDocument(
        f"# {display_title}\n\n{fence}yaml\n{yaml_content}\n{fence}", 0
    )
    try:
        root = yaml.compose(yaml_content, Loader=yaml.SafeLoader)
        shape = _framework_shape(root, len(yaml_content))
        if shape is None:
            return as_written

        blocks = [f"# {display_title}"]
        description = source = ""
        other = []
        for name, node in shape.fields:
            text = _said(node)
            if name == "description" and not description:
                description = text
            elif name == "source_url" and not source and node.tag == _STRING_TAG:
                source = text
            elif name == "title" and _as_a_heading(node.value) == display_title:
                # The heading already.
                continue
            elif text:
                # Whatever else the file says about itself, a title the
                # heading could not use included: one over several lines is
                # rejected as a name, and is still something the file says.
                other.append(_line(f"{name}: {text}"))
        if description:
            blocks.append(_line(description))
        if source:
            blocks.append(f"Source: {source}")
        blocks.extend(other)

        # The same line breaks YAML counts, so a mark's line is an index here.
        comments = _entry_comments(yaml_content.splitlines(), shape.entries)
        items: list[str] = []
        for entry, heading in zip(shape.entries, comments, strict=False):
            if heading:
                if items:
                    blocks.append("\n".join(items))
                    items = []
                blocks.append(f"## {heading}")
            items.extend(_entry_lines(entry))
        if items:
            blocks.append("\n".join(items))
        if shape.entries and comments[-1]:
            blocks.append(_line(comments[-1]))
        return _FrameworkDocument("\n\n".join(blocks), len(shape.entries))

    except Exception:
        return as_written


#: Fan-out once the probe below has succeeded.
#:
#: This alone does **not** keep a listing under ContentService's fetch
#: circuit-breaker threshold of 5 (content/service.py:217), and an earlier
#: comment here wrongly claimed it did. The budget is checked after increment,
#: so with slow failures all N in-flight tasks fail before `exhausted` takes
#: effect -- measured with a 50ms failing stub: 4 attempts, 4 cumulative
#: failures. The breaker counts cumulatively and resets only on success, so two
#: listings in a row could reach 8 and open it. What actually holds the line is
#: the serial probe: the common case is a backend that is wholly down, and the
#: probe makes that cost exactly one failure per listing.
_TITLE_FETCH_CONCURRENCY = 4

#: Stop resolving titles once this many documents have failed. Titles are
#: best-effort enrichment -- the listing is already correct without them -- so
#: there is nothing to gain from asking a failing backend once per document, and
#: a great deal to lose: the failures land on a breaker shared with get_* and
#: search_*, and CircuitBreaker counts them *cumulatively*, resetting only on a
#: success. Bounding concurrency alone therefore does not protect it.
#:
#: **One, not two.** With a budget of 2 the serial probe below did not hold the
#: line: the probe's failure left the count at 1, the fan-out launched anyway,
#: and four more failed before the budget tripped. Measured with a 50ms failing
#: stub: 5 attempts per listing, which is the breaker's threshold on its own. At
#: 1 the probe's failure trips the budget immediately and the fan-out never
#: starts -- measured, 1 attempt. The cost is that a single transient failure
#: gives the rest of that listing derived names, which is the same answer the
#: listing gave before #118 and is recoverable on the next call.
#:
#: **The coupling itself is deliberate, and it is new (#121).** Before titles
#: were resolved here a listing did no document fetches at all, so it could not
#: touch the HTTP client's breaker for the content host however badly the
#: backend was behaving. It can now, and the breaker is shared: opening it fails ``get_*``
#: and ``search_*`` fast for 60s, so a listing could take down tools that were
#: working. A separate breaker for listings was the alternative and was not
#: taken -- two breakers over one backend disagree about whether that backend is
#: healthy, and the listing's would learn nothing the shared one had not already
#: seen. Instead the listing is made cheap enough to share: probe serially,
#: stop at the first failure, and give the rest derived names. Measured against
#: a total outage: 1 failed fetch per listing, 2 across the two a ``search_*``
#: triggers -- against a threshold of 5.
_TITLE_FETCH_FAILURE_BUDGET = 1

#: Hard ceiling on documents a single listing will fetch titles for. The
#: discovery result is whatever the upstream repository contains, not the
#: bounded lists built into discovery, so without this a listing's cost is
#: set by a third party. Beyond the ceiling the remaining entries keep their
#: derived names.
_TITLE_FETCH_MAX_DOCUMENTS = 100


def _cut_short_reason(*, exhausted: bool) -> str:
    """Why a listing stopped fetching, for the one warning an operator sees.

    One reason since #312: the failure budget. A second, a fall back to the
    metered Contents API route, went with that route.
    """
    if not exhausted:
        return ""
    return ", and the rest were not attempted because the failure budget was spent"


class ListedDocument(NamedTuple):
    """What a listing says about one document, beyond its id."""

    name: str
    #: The document's own words, or ``None``. Never generated: a listing used
    #: to publish ``"Risk document: <title>"`` here, which told a model choosing
    #: a document nothing the name had not (#191).
    description: str | None


#: What ``extract`` hands back: the declared title and the description, either
#: of which the document may not have.
_Extracted = tuple[str | None, str | None]


async def _resolve_titles(
    doc_type: str,
    filenames: Sequence[str],
    extract: Callable[[Mapping[str, Any]], Awaitable[_Extracted]],
    fallback: Callable[[str], str],
) -> list[ListedDocument]:
    """Each document's declared title and description.

    The title falls back to a derived name; the description has no fallback and
    is ``None`` for a document that could not be read or does not carry one.
    Both come from the one fetch per document this already made for the title,
    so descriptions cost no extra requests.

    Listings used to derive every name from the filename, so a client browsing
    risks saw ``Ri 10_Prompt Injection`` and, on opening the same document,
    ``Prompt Injection``. The catalog and the document disagreed about what the
    document was called (#118).

    ``extract`` and ``fallback`` are parameters because the two catalogs differ:
    risks and mitigations carry their title in Markdown frontmatter and fall back
    to the title-cased display name, while frameworks are plain YAML and fall
    back to the hardcoded name map.

    **A ``None`` return counts as a failure, and that is the whole point.**
    ``ContentService.get_document`` *returns* ``None`` for nearly every ordinary
    failure -- raw fetch failed, API fallback failed, breaker already open, and
    its entire catch-all block. It raises ``GitHubRateLimitError``, and
    ``ContentValidationError`` for a document it fetched but could not parse,
    which is local and not charged to the fetch budget (#366). An earlier
    version of this function keyed the budget solely on an exception, so
    measured against a stub returning ``None``: 23 of 23 documents attempted and
    **zero** warnings -- the budget and the warning both dead, while the
    docstring claimed they protected the breaker.
    """
    if not filenames:
        return []

    try:
        service = await get_service()
    except Exception as e:
        # Caught here rather than left to propagate: escaping this function
        # lands in the caller's blanket handler, which would discard a
        # *successful* live discovery and answer from the static list with
        # source="static_fallback".
        logger.warning(
            "Content service unavailable, listing %s with derived names: %s",
            doc_type,
            e,
        )
        return [ListedDocument(fallback(name), None) for name in filenames]

    budgeted = filenames[:_TITLE_FETCH_MAX_DOCUMENTS]
    semaphore = asyncio.Semaphore(_TITLE_FETCH_CONCURRENCY)
    failures = 0
    untitled = 0
    skipped = 0
    exhausted = False

    async def _name_for(filename: str) -> ListedDocument:
        nonlocal failures, untitled, skipped, exhausted
        title = None
        description = None
        if exhausted:
            # The failure budget protects the circuit breaker shared with
            # ``get_*`` and ``search_*``.
            skipped += 1
        else:
            async with semaphore:
                # Re-checked after acquiring: the budget may have been spent
                # while this call queued behind the semaphore.
                if exhausted:
                    skipped += 1
                else:
                    fetched = False
                    try:
                        doc = await service.get_document(doc_type, filename)
                        fetched = isinstance(doc, Mapping)
                        # extract() is inside the guard, not after it. gather()
                        # runs without return_exceptions, so anything escaping
                        # here lands in the caller's blanket handler, which
                        # discards a *successful* live discovery and answers
                        # from the static list -- the exact failure the
                        # get_service() guard above exists to prevent. It is
                        # reachable: asyncio.to_thread raises RuntimeError once
                        # the default executor is shut down. (A YAML error is
                        # not one: parse_yaml_document catches every Exception,
                        # MemoryError included, through _load_yaml.)
                        if isinstance(doc, Mapping):
                            title, description = await extract(doc)
                    except Exception as e:
                        # Deliberately broad and deliberately not re-raised: one
                        # document's failure must cost that entry its title and
                        # nothing more. A ContentValidationError is a document
                        # that was fetched and did not parse (#366): local, so
                        # charged as untitled below, not to the fetch budget.
                        fetched = fetched or isinstance(e, ContentValidationError)
                        title = None
                        logger.debug(
                            "Title resolution raised for %s/%s: %s",
                            doc_type,
                            filename,
                            e,
                        )
                    if fetched:
                        # An extract() failure is charged here, not to the fetch
                        # budget. That budget exists solely to protect the shared
                        # fetch circuit breaker, and extract() is CPU-side and
                        # local -- a to_thread RuntimeError or a YAML alias bomb
                        # says nothing about the backend's health. Charging it
                        # there meant one unparseable document on the probe
                        # stopped all remaining I/O and cost every other entry
                        # its title, contradicting the comment above.
                        if title is None:
                            untitled += 1
                    else:
                        failures += 1
                        if failures >= _TITLE_FETCH_FAILURE_BUDGET:
                            exhausted = True
        return ListedDocument(title or fallback(filename), description)

    # One document, alone, before any fan-out. A wholly unavailable backend is
    # the common failure, and probing serially makes it cost a single failure
    # against the shared breaker instead of a concurrent burst of them. On
    # success the breaker's counter is reset, so the fan-out starts from zero.
    first = await _name_for(budgeted[0])
    rest = await asyncio.gather(*(_name_for(name) for name in budgeted[1:]))
    names = [first, *rest]
    names.extend(
        ListedDocument(fallback(name), None)
        for name in filenames[_TITLE_FETCH_MAX_DOCUMENTS:]
    )

    # Three separate things produce a derived name: a failed fetch, a document
    # with no usable title, and every document skipped once the budget tripped.
    # Each is counted as it happens. Summing only the first two reported
    # "2 of 23" when all 23 were filename-derived, and this warning is the only
    # signal an operator gets. Counting instead by re-comparing each published
    # name to fallback(name) would be wrong in the other direction: a document
    # whose declared title equals its derived name is not a fallback.
    beyond_ceiling = len(filenames) - len(budgeted)
    derived = failures + untitled + skipped + beyond_ceiling
    if derived:
        # Counted as they happen rather than by re-comparing published names to
        # fallback(name): a document whose declared title equals its derived
        # name is not a fallback, and counting it as one made two numbers in
        # this same message disagree about the same document.
        logger.warning(
            "Published %d of %d %s names from filenames rather than from the "
            "documents: %d unreadable, %d with no usable title, %d past the "
            "fetch ceiling%s. The listing "
            "is otherwise indistinguishable from success -- correct ids, "
            "plausible names, live source -- so this is the only signal",
            derived,
            len(filenames),
            doc_type,
            failures,
            untitled,
            beyond_ceiling,
            _cut_short_reason(exhausted=exhausted),
        )
    return names


async def _resolve_document_names(
    doc_type: str, filenames: Sequence[str]
) -> list[ListedDocument]:
    """Risk and mitigation display names and descriptions.

    The name is the frontmatter title; the description is the first paragraph
    of the section the document opens with.
    """

    async def _extract(doc: Mapping[str, Any]) -> _Extracted:
        return (
            frontmatter_title(doc.get("metadata")),
            opening_section_summary(doc.get("content")),
        )

    return await _resolve_titles(
        doc_type, filenames, _extract, document_name_from_filename
    )


async def _resolve_framework_names(filenames: Sequence[str]) -> list[ListedDocument]:
    """Framework display names and descriptions, from the document's own YAML.

    Both are top-level keys, ``title`` and ``description``, read from one parse.

    Without this, fixing get_framework alone would have *introduced* the very
    defect #118 is about: list_frameworks published the name map's "Assured
    Transparency Reporting" for ``atr`` while get_framework published the
    document's "Agent Threat Rules (ATR)".
    """

    def _declared_title(content: str) -> _Extracted:
        # The parse and the title read as one unit of work, so the whole thing
        # crosses to the worker thread once. `get_framework` splits them only
        # because it needs the parsed document for the body as well.
        parsed = parse_yaml_document(content)
        return (
            yaml_title_from_document(parsed),
            yaml_description_from_document(parsed),
        )

    async def _extract(doc: Mapping[str, Any]) -> _Extracted:
        # Off the event loop. This is a full yaml.safe_load of the whole
        # document, once per framework, and ContentService offloads the
        # equivalent frontmatter parse for the same reason. list_frameworks
        # previously did no content parsing at all; leaving 13 full parses
        # inline would stall every other in-flight request behind them.
        return await asyncio.to_thread(_declared_title, str(doc.get("content", "")))

    def _fallback(filename: str) -> str:
        # _format_framework_name takes an *id*, with the extension already
        # stripped -- its name_map has no "eu-ai-act.yml" key, so handing it the
        # raw filename fell through to filename.replace("-", " ").title() and
        # published "Eu Ai Act.Yml" where main published "EU AI Act". Reachable
        # on three paths: the get_service() failure branch, any framework whose
        # YAML declares no usable title, and everything past the fetch ceiling.
        return _format_framework_name(filename.replace(".yml", "").replace(".yaml", ""))

    return await _resolve_titles("framework", filenames, _extract, _fallback)
