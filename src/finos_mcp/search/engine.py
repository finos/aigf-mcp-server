#!/usr/bin/env python3
# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Searching one framework.

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

from ..documents.tools import get_framework
from ..models import Framework, SearchResult
from ..search.ranking import _find_phrase, _passage

#: How a line of the body begins if a heading can be above it: the heading
#: itself, the line an entry opens with, a line of an entry's fields. A
#: paragraph begins with none of them (`documents.format._line`).
_UNDER_A_HEADING = ("## ", "- ", "  ")


def _section_above(text: str, start: int, fallback: str) -> str:
    """The heading the match at `start` is under; else `fallback`.

    `get_framework` writes the comment above a group of entries as a ``## ``
    heading, and no value of the document can begin a line of the body, so a
    line that begins with one is a heading. This used to read the YAML
    comments themselves, in the ten lines above the match.

    It is still a comment, promoted: a ``# NOTE:`` above an entry is reported
    as its section just the same.

    Only an entry is under a heading. The paragraphs of the body -- the
    description above the entries, the note a file closes with below them --
    are under none, and a match in the note that closes `canada-regulations`
    was reported under the last heading of the file (#214).
    """
    line_end = text.find("\n", start)
    lines = text[: line_end if line_end != -1 else len(text)].split("\n")
    if not lines[-1].startswith(_UNDER_A_HEADING):
        return fallback
    for line in reversed(lines):
        if line.startswith("## "):
            return line[3:].strip()
    return fallback


async def _search_single_framework(
    framework: Framework, query: str
) -> SearchResult | None:
    """Look for the phrase in one framework; None if it is not there.

    At most one result per framework: `limit` in search_frameworks counts
    frameworks, not matches. The result quotes the passage around the first
    occurrence and says how many there are.

    Nothing is caught here. None means the framework was read and does not
    say the phrase, and an exception is never turned into one: which
    exceptions are a framework to leave out and which are a search that
    failed is for search_frameworks to say (#224).
    """
    content = await get_framework(framework.id)

    # The body is the document and nothing else: the title, the description,
    # each entry. It used to open with a summary this server wrote, which had
    # to be skipped (#192).
    document = content.content
    found = _find_phrase(query, document)
    if found is None:
        return None

    return SearchResult(
        document_id=framework.id,
        # A file served as it was written has no entries and no headings: a
        # line of it that begins ``## `` is a YAML comment (#214).
        section=(
            _section_above(document, found.start, framework.name)
            if content.entry_count
            else framework.name
        ),
        content=_passage(document, found.start, found.end),
        occurrences=found.occurrences,
    )
