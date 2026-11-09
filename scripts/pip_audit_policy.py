#!/usr/bin/env python3
"""Single source of truth for the pip-audit suppression list.

Every dependency audit in this repository -- two GitHub workflows, four shell
scripts and the pre-commit hook -- runs through ``scripts/pip-audit-scan.sh``,
which asks this module which ``--ignore-vuln`` flags to pass. The suppressions
themselves are declared once, in ``pyproject.toml``::

    [tool.finos.pip-audit]
    ignore = [
      { id = "GHSA-...", reason = "why", review_by = "2026-12-01" },
    ]

Each entry must carry a rationale and a review date, and an entry past its
review date fails the build. Both rules exist because of what they would have
caught: the list previously lived inline at six call sites, five of them with
no rationale at all, and the one suppression that did carry a review date
(``REVIEW-BY: 2026-04-01``) was still in place months after the underlying
advisory had been fixed upstream.

pip-audit has no configuration-file or environment-variable support for
``--ignore-vuln`` (verified against pip-audit 2.9.0 ``--help``), so the flags
must be injected on the command line. That is the whole reason this module
exists.

This file is build tooling and deliberately lives outside ``src/`` so it never
ships in the wheel. It uses only the standard library.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

__all__ = [
    "PolicyError",
    "Suppression",
    "ignore_flags",
    "load_policy",
    "parse_policy",
]

_TOOL_TABLE = ("tool", "finos", "pip-audit")
_IGNORE_KEY = "ignore"
_TABLE_PATH = ".".join(_TOOL_TABLE) + "." + _IGNORE_KEY


class PolicyError(ValueError):
    """A suppression entry is malformed, undocumented, or overdue for review."""


@dataclass(frozen=True)
class Suppression:
    """One advisory deliberately excluded from failing the build."""

    id: str
    reason: str
    review_by: date


def _require_text(entry: dict[str, Any], key: str, position: int) -> str:
    """Return a non-blank string field, or explain precisely what is missing."""
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PolicyError(
            f"{_TABLE_PATH}[{position}] must declare a non-empty {key!r}. "
            f"Got {value!r}. Every suppression needs an advisory id and a "
            f"written rationale, or a reviewer cannot tell whether it still "
            f"applies."
        )
    return value.strip()


def _require_review_date(entry: dict[str, Any], position: int) -> date:
    """Return the entry's ``review_by`` date, accepting TOML dates or strings."""
    value = entry.get("review_by")

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise PolicyError(
                f"{_TABLE_PATH}[{position}] has a malformed 'review_by': "
                f"{value!r}. Use an ISO date such as 2026-12-01."
            ) from exc

    raise PolicyError(
        f"{_TABLE_PATH}[{position}] must declare a 'review_by' date. "
        f"Got {value!r}. A suppression with no expiry is never re-read."
    )


def _check_not_expired(suppressions: Sequence[Suppression], today: date) -> None:
    """Fail on any suppression whose review date has already passed."""
    overdue = [item for item in suppressions if item.review_by < today]
    if not overdue:
        return

    details = "; ".join(
        f"{item.id} (review_by {item.review_by.isoformat()}, reason: {item.reason})"
        for item in overdue
    )
    raise PolicyError(
        f"These pip-audit suppressions are past their review date as of "
        f"{today.isoformat()}: {details}. Re-confirm the advisory still has no "
        f"fix and extend 'review_by', or remove the suppression."
    )


def _check_no_duplicates(suppressions: Sequence[Suppression]) -> None:
    """Fail on a repeated advisory id, which would mean two rationales."""
    counts = Counter(item.id for item in suppressions)
    duplicates = sorted(item_id for item_id, count in counts.items() if count > 1)
    if duplicates:
        raise PolicyError(
            f"{_TABLE_PATH} declares these advisory ids more than once: "
            f"{duplicates}. One advisory gets one rationale."
        )


def parse_policy(document: str, *, today: date) -> list[Suppression]:
    """Parse and validate a suppression policy from TOML text.

    Raises:
        PolicyError: if any entry is malformed, undocumented, duplicated, or
            past its ``review_by`` date.
    """
    try:
        data: Any = tomllib.loads(document)
    except tomllib.TOMLDecodeError as exc:
        raise PolicyError(f"could not parse the suppression policy: {exc}") from exc

    for key in _TOOL_TABLE:
        data = data.get(key, {}) if isinstance(data, dict) else {}

    if not isinstance(data, dict):
        raise PolicyError(f"[{'.'.join(_TOOL_TABLE)}] must be a table")

    raw_entries = data.get(_IGNORE_KEY, [])
    if not isinstance(raw_entries, list):
        raise PolicyError(
            f"{_TABLE_PATH} must be an array of tables, got "
            f"{type(raw_entries).__name__}"
        )

    suppressions: list[Suppression] = []
    for position, entry in enumerate(raw_entries):
        if not isinstance(entry, dict):
            raise PolicyError(
                f"{_TABLE_PATH}[{position}] must be a table with 'id', "
                f"'reason' and 'review_by' keys, got {entry!r}"
            )
        suppressions.append(
            Suppression(
                id=_require_text(entry, "id", position),
                reason=_require_text(entry, "reason", position),
                review_by=_require_review_date(entry, position),
            )
        )

    _check_no_duplicates(suppressions)
    _check_not_expired(suppressions, today)
    return suppressions


def load_policy(pyproject: Path, *, today: date) -> list[Suppression]:
    """Load and validate the suppression policy declared in ``pyproject.toml``."""
    return parse_policy(pyproject.read_text(encoding="utf-8"), today=today)


def ignore_flags(suppressions: Sequence[Suppression]) -> list[str]:
    """Return the ``--ignore-vuln`` flags pip-audit should be invoked with.

    An empty policy yields an empty list, which is the correct current state:
    nothing suppressed, nothing passed.
    """
    flags: list[str] = []
    for item in suppressions:
        flags.extend(("--ignore-vuln", item.id))
    return flags


def main(argv: Sequence[str] | None = None) -> int:
    """Validate the declared policy and optionally print pip-audit flags."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "pyproject.toml",
        help="path to pyproject.toml (default: the repository's own)",
    )
    parser.add_argument(
        "--print-flags",
        action="store_true",
        help="print each pip-audit flag on its own line",
    )
    args = parser.parse_args(argv)

    try:
        suppressions = load_policy(args.pyproject, today=date.today())
    except (PolicyError, OSError) as exc:
        print(f"pip-audit suppression policy is invalid: {exc}", file=sys.stderr)
        return 1

    if args.print_flags:
        for flag in ignore_flags(suppressions):
            print(flag)
    else:
        print(
            f"pip-audit suppression policy OK: {len(suppressions)} active "
            f"suppression(s) in {args.pyproject}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
