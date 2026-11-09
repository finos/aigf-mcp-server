#!/usr/bin/env python3
# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Finding a phrase in a document and quoting the passage around it. No I/O.

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

import re
import unicodedata
from functools import lru_cache
from typing import NamedTuple

# Hyphen-minus, underscore, and what documents and pasted queries carry in
# place of the first: the Unicode hyphen, non-breaking hyphen, figure dash and
# en dash, the minus sign, the small and the fullwidth hyphen-minus.
#
# Not the em dash or the horizontal bar. Those end a clause, as a comma does,
# and a phrase does not span one: every em dash of the live files, 23 on
# 2026-10-10, stands between two spaces, and folded to a space
# "AI use \u2014 an investor-protection control" would say "use an investor"
# (#212).
_SEPARATORS = str.maketrans(
    dict.fromkeys("-_\u2010\u2011\u2012\u2013\u2212\ufe63\uff0d", " ")
)


def _fold(text: str) -> str:
    """Lower-case `text` and turn word separators into spaces, for comparison.

    A searcher means the same thing by "prompt-injection", "prompt_injection"
    and "prompt injection", and the corpus itself writes "third-party" where a
    caller types "third party". Measured before this existed (#185):
    "data-poisoning" found no risk where "data poisoning" found 18.

    Each separator becomes exactly one space and every character stays one
    character, so an index into the folded text is an index into the original
    and passages are still cut from the text as the document wrote it.
    `str.lower` alone does not keep that promise: U+0130 lower-cases to two
    characters and moved every index after it (#188). A character like that is
    left as written.

    The rest of such a text is still lower-cased as a whole, with a capital I
    standing where the character was. A character at a time, a capital sigma
    is never the final one, and a Greek word was not found in its own capitals
    once the text held a U+0130 anywhere (#212).
    """
    lowered = text.lower()
    if len(lowered) != len(text):
        uneven = {char for char in set(text) if len(char.lower()) != 1}
        stood_in = text.translate(dict.fromkeys(map(ord, uneven), "I")).lower()
        lowered = "".join(
            written if written in uneven else low
            for written, low in zip(text, stood_in, strict=True)
        )
    return lowered.translate(_SEPARATORS)


def _fold_query(query: str) -> str:
    """The query as a phrase to look for; empty if it held only separators.

    Runs of separators collapse to one space here and only here, so
    "data - poisoning" and "data--poisoning" are the phrase "data poisoning".
    The text being searched is never collapsed: that would move its indices.

    Composed after it is folded, and by what composes the text
    (`_composed`): where that leaves a letter as it was written, a query
    copied from the text has to be left the same way to be found in it.
    """
    return _composed(" ".join(_fold(query).split()))[0]


# A URL of any scheme, or the target of a Markdown link or image: `](target)`,
# `](target "title")` and `](<target>)`. The text of the link is not part of
# the match and stays searchable.
#
# A URL ends at whitespace or at a character that closes what it was written
# in (a quote, an angle bracket, a table bar), so the text after `href="..."`
# is not blanked with it. Every repeat is bounded: a target is looked for after
# each `](`, and an unbounded scan from each of thousands of them took twelve
# seconds on a 75k body.
#
# A target may hold parentheses that close, one pair inside another and no
# deeper: `](wiki/Data_(computing))`. It used to end at the first `)`, and the
# rest of it was searched (#212). One that never closes still ends there.
_LINK_TARGET = re.compile(
    r"""(?<![a-z0-9+.])[a-z][a-z0-9+.]{0,15}://[^\s<>"'|]+"""
    r"""|(?<=\])\((?:<[^>\n]{0,500}>"""
    r"""|(?:[^()\n]|\([^()\n]{0,500}\)){0,500}"""
    r"""|[^)\n]{0,500})\)""",
    re.IGNORECASE,
)

# What this does not recognise is still searched: a bare path or host with no
# scheme, a target with parentheses three deep, and the target of a link
# reference definition, `[id]: target`.
#
# Nothing tells `example.com/a_b.md` from "Node.js/Express" or from the
# "consent/opt-out" of a live file, nor `[q]: docs/a_b.md` from "[Standard]:
# ISO/IEC 42001 applies" -- and `get_framework` escapes a line that opens like
# a definition, so in the body searched here it is text by this server's own
# hand (`documents.format._line`). Text blanked by mistake is a document that
# no longer says what it says, where a target searched by mistake is a passage
# a reader can see (#212).

# What a link target is blanked with. Not part of any word, and refused in a
# query, which could otherwise ask for the blanks themselves.
_BLANK = "\0"

# What `(?<!\w)` and `(?!\w)` refuse beside a phrase.
_WORD_CHARACTER = re.compile(r"\w")

# The categories of a character that is written on or between letters and is
# not one: the three kinds of combining mark, and format characters.
_PART_OF_A_LETTER = frozenset({"Mn", "Mc", "Me", "Cf"})

# Characters of context quoted either side of a match.
_PASSAGE_RADIUS = 150


def _searchable(text: str) -> str:
    """`text` folded for comparison, with every link target blanked out.

    Since #185 a spaced phrase matches hyphenated text, and nothing is more
    hyphenated than a URL: "data poisoning" matched inside
    `ri-2_data-poisoning.md` and the result quoted the address (#188). A
    framework is mostly titles and the URLs they point to, so the address is
    blanked rather than searched.

    Blanked, not removed: each character becomes `_BLANK`, so the indices still
    line up with the original, a word next to a link is still a word, and the
    words either side of a link are not next to each other.
    """
    blanked = _LINK_TARGET.sub(lambda match: _BLANK * len(match.group()), text)
    return _fold(blanked)


# A run of characters that are not ASCII, with the ASCII character before it
# if there is one: an accent written apart composes with the "e" before it,
# and nothing composes with what is before an ASCII character.
_COMPOSABLE = re.compile(r"[\x00-\x7f]?[^\x00-\x7f]+")

# The longest letter-with-its-accents that is composed. A longer one is left
# as written: putting the accents of one in order costs the square of their
# number, and a megabyte of them after one letter took 198 seconds.
_LONGEST_COMPOSED = 32


def _units(run: str) -> list[int]:
    """Where each unit of `run` ends: a character and what composes with it.

    Accents compose with the letter before them, and so does a character
    that is no accent but has a composed form with the one before it: the
    vowel of a Hangul syllable written as jamo, or a half-width voiced mark
    after its half-width katakana. Judged by `_plain`, the form compared.
    """
    ends: list[int] = []
    begun = 0
    for at in range(1, len(run)):
        if unicodedata.combining(run[at]):
            continue
        unit = run[begun:at]
        if len(unit) < _LONGEST_COMPOSED and _plain(unit + run[at]) != _plain(
            unit
        ) + _plain(run[at]):
            continue
        ends.append(at)
        begun = at
    return [*ends, len(run)]


@lru_cache(maxsize=4096)
def _plain_character(char: str) -> str:
    """A full-width or half-width form, or a letter ligature, as plain text.

    The parser stopped writing NFKC into the served body (#352), which is
    right for the reader, and "financial" was then not found where a framework
    writes it with the "\ufb01" ligature (#361). The comparison folds these
    here instead -- and only these: all of NFKC also turned "\u2122" into
    "TM", glued to the word before it, so "acme" was not found in
    "Acme\u2122", and a spacing accent into a space that split a word.
    """
    decomposition = unicodedata.decomposition(char)
    tag = decomposition.split(" ", 1)[0] if decomposition.startswith("<") else ""
    if tag in ("<wide>", "<narrow>") or (
        tag == "<compat>" and unicodedata.category(char).startswith("L")
    ):
        return unicodedata.normalize("NFKC", char)
    return char


def _plain(unit: str) -> str:
    """`unit` composed, its plain characters folded, composed again, and folded
    as `_fold` folds the text: a full-width low line becomes "_", then a space.

    Composed again because a folded letter can compose with the mark after
    it: a half-width katakana with a half-width voiced mark, or a full-width
    "e" with a combining acute, was not found by the composed form.
    """
    composed = unicodedata.normalize("NFC", unit)
    plain = unicodedata.normalize("NFC", "".join(map(_plain_character, composed)))
    return _fold(plain)


def _composed(text: str) -> tuple[str, list[tuple[int, int]] | None]:
    """`text` with each letter and its accent as one character, and where
    each character of the result was written in `text`; None if `text` is
    unchanged.

    A file saved on one system writes "\u00e9" as one character and a query
    typed on another writes it as an "e" and a combining accent. Nothing but
    the bytes differs, and neither was found in the other (#212). Hangul
    written as jamo is the same case. A full-width letter or a ligature
    also becomes its plain form (`_plain_character`), so "financial" is found
    where the text writes "\ufb01nancial" (#361).

    Composing changes the length, so this cannot keep the promise `_fold`
    keeps. The places are kept instead: a character of a unit that composing
    changed is placed at the whole unit, a letter with its accents
    (`_units`). Every live body is composed already and holds none of those
    forms (all 13 framework files on 2026-10-20), and such a text is returned
    as it is.
    """
    if unicodedata.is_normalized("NFC", text) and all(
        _plain_character(char) == char for char in set(text) if char > "\x7f"
    ):
        return text, None
    pieces: list[str] = []
    written: list[tuple[int, int]] = []

    def _as_written(start: int, end: int) -> None:
        pieces.append(text[start:end])
        written.extend((at, at + 1) for at in range(start, end))

    done = 0
    for run in _COMPOSABLE.finditer(text):
        _as_written(done, run.start())
        start = run.start()
        for length in _units(run.group()):
            end = run.start() + length
            unit = text[start:end]
            piece = unit
            if len(unit) <= _LONGEST_COMPOSED:
                piece = _plain(unit)
            if piece == unit:
                _as_written(start, end)
            else:
                pieces.append(piece)
                written.extend([(start, end)] * len(piece))
            start = end
        done = run.end()
    _as_written(done, len(text))
    return "".join(pieces), written


def _is_a_word_character(word: str) -> bool:
    """Whether `word`, read from this end, opens with a word character.

    An accent written apart is not one to `\\w`, and it is part of the letter
    it is on: "\u0915\u0940" ends in a vowel sign and is a word all the same.
    So is a joiner a pasted query can end with, which nobody sees. A query of
    nothing else is held to the rule too, or it is found inside every word
    that has the accent.
    """
    for character in word:
        if unicodedata.category(character) not in _PART_OF_A_LETTER:
            return _WORD_CHARACTER.match(character) is not None
    return True


class _Found(NamedTuple):
    """Where a text first says a phrase, and how many times it says it.

    `start` and `end` index the text as written.
    """

    start: int
    end: int
    occurrences: int


def _find_phrase(query: str, text: str | None) -> _Found | None:
    """Find `query` in `text` as one phrase of whole words, or None.

    The words must follow one another, separated by spaces, line breaks or the
    separators `_fold` turns into spaces, and the phrase must not begin or end
    inside a longer word: "rag" is not found in "storage", nor "act" in
    "practice" (#190). Case is ignored. The query is text, never a pattern.

    Only a word can be inside a longer word. A phrase that begins or ends
    with punctuation is found wherever it is written: "(b)" in "Article 3(b)",
    which the rule above used to refuse it (#212).

    There is no fallback to a single word. A query no document says as a
    phrase finds nothing, which is the answer (#208).
    """
    words = _fold_query(query).split()
    if not words or not text or _BLANK in query:
        return None

    # `\w` rather than `\b`: a query may begin or end with punctuation ("c++"),
    # where `\b` would demand a word character on the other side.
    phrase = r"\s+".join(map(re.escape, words))
    if _is_a_word_character(words[0]):
        phrase = r"(?<!\w)" + phrase
    if _is_a_word_character(words[-1][::-1]):
        phrase += r"(?!\w)"

    searchable, written = _composed(_searchable(text))
    matches = list(re.finditer(phrase, searchable))
    if not matches:
        return None
    start, end = matches[0].span()
    if written is not None:
        start, end = written[start][0], written[end - 1][1]
    return _Found(start, end, len(matches))


def _passage(text: str, start: int, end: int) -> str:
    """The text around `text[start:end]`, cut between words.

    Snippets were cut at a fixed character offset and began mid-word (#188).
    The window is narrowed to the nearest whitespace instead, which also means
    a URL is quoted whole or not at all. Runs of whitespace become one space:
    a framework is indented YAML, and its line breaks say nothing in a quote.
    """
    low = max(0, start - _PASSAGE_RADIUS)
    if low > 0:
        while low < start and not text[low - 1].isspace():
            low += 1
    high = min(len(text), end + _PASSAGE_RADIUS)
    if high < len(text):
        while high > end and not text[high].isspace():
            high -= 1

    passage = " ".join(text[low:high].split())
    if text[:low].strip():
        passage = "..." + passage
    if text[high:].strip():
        passage += "..."
    return passage
