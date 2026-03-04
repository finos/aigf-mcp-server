"""Shared text parsing helpers for search and prompt composition flows."""

from __future__ import annotations

import re

_SNIPPET_URL_LINE = re.compile(r"^\s*(url|reference|href)\s*:", re.IGNORECASE)
_SNIPPET_BARE_URL = re.compile(r"^\s*https?://\S+\s*$")
_SECTION_HEADER = re.compile(r"^#{1,3}\s+", re.MULTILINE)
_SEARCH_STOP_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "are",
    "was",
    "were",
    "have",
    "has",
    "had",
    "about",
    "into",
    "after",
    "before",
    "between",
    "through",
}


def extract_section(content: str, *headers: str, max_chars: int = 800) -> str:
    """Extract the text body of the first matching markdown section."""
    for header in headers:
        pattern = re.compile(
            r"^#{1,3}\s+" + re.escape(header) + r"\s*$", re.IGNORECASE | re.MULTILINE
        )
        match = pattern.search(content)
        if not match:
            continue
        start = match.end()
        next_header = _SECTION_HEADER.search(content, start)
        body = content[
            start : next_header.start() if next_header else len(content)
        ].strip()
        if body:
            return body[:max_chars]
    return ""


def best_match_index(content: str, query: str) -> tuple[int, bool]:
    """Return (char_index, is_exact_phrase) for the best match of query in content."""
    lower = content.lower()

    idx = lower.find(query.lower())
    if idx != -1:
        return idx, True

    tokens = sorted(
        (
            token
            for token in query.lower().split()
            if len(token) > 2 and token not in _SEARCH_STOP_WORDS
        ),
        key=len,
        reverse=True,
    )
    for token in tokens:
        idx = lower.find(token)
        if idx != -1:
            return idx, False

    return -1, False


def clean_search_snippet(text: str, query: str, match_index: int) -> str:
    """Extract a concise prose-only snippet around a search match."""
    lines = text.splitlines()

    offset = 0
    match_line = 0
    for index, line in enumerate(lines):
        if offset + len(line) >= match_index:
            match_line = index
            break
        offset += len(line) + 1

    def _is_prose(line: str) -> bool:
        candidate = line.strip()
        return (
            bool(candidate)
            and not _SNIPPET_URL_LINE.match(candidate)
            and not _SNIPPET_BARE_URL.match(candidate)
            and not candidate.startswith("```")
        )

    context = lines[max(0, match_line - 4) : match_line + 5]
    prose = [line.strip() for line in context if _is_prose(line)]

    snippet = " ".join(prose)
    if len(snippet) > 280:
        snippet = snippet[:280] + "..."
    return snippet or f"Found '{query}' in document content"
