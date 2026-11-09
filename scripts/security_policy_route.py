#!/usr/bin/env python3
"""Say which reporting route ``SECURITY.md`` describes, and whether it is the true one.

GitHub private vulnerability reporting exists only on a public repository,
and only once it is enabled there. ``SECURITY.md`` therefore has two correct
forms, and each is wrong where the other is right (#138, #389):

``private``
    The document says private reporting is not available. Correct on a
    private repository, and on a public one where reporting is not enabled.

``public``
    The document links the "Report a vulnerability" form
    (``/security/advisories/new``). Correct once the repository is public
    and private reporting is enabled on it.

``policy_state`` is the one definition of the two forms.
``tests/unit/test_security_policy.py`` uses it to require that the document is
in exactly one of them, and ``scripts/check-security-policy.sh`` (go-live Gate
11) compares that form with what GitHub reports.

Usage: security_policy_route.py {private|public} [PATH]

This file is build tooling and deliberately lives outside ``src/`` so it never
ships in the wheel. It uses only the standard library.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from pathlib import Path

STATES = ("private", "public")

_MENTION = re.compile(r"private(ly)?\s+(vulnerability\s+)?report", re.IGNORECASE)
_UNAVAILABLE = re.compile(
    r"not\s+(yet\s+)?(currently\s+)?(available|enabled)|only\s+.{0,40}public",
    re.IGNORECASE,
)
_REPORT_FORM = "/security/advisories/new"


def _paragraphs(text: str) -> list[str]:
    """Return the Markdown paragraphs of ``text``, each without newlines.

    Prose is soft-wrapped, so a statement is bounded by its paragraph, not by
    its line.
    """
    return [
        " ".join(block.split()) for block in re.split(r"\n\s*\n", text) if block.strip()
    ]


def policy_state(text: str) -> str:
    """Return ``"private"`` or ``"public"`` for the form ``text`` is in.

    Raises ``ValueError`` when the document is in neither form or in both: it
    does not mention private reporting, it mentions it without saying either
    that it is unavailable or where the form is, or it says it is unavailable
    and links the form as well.
    """
    mentions = [p for p in _paragraphs(text) if _MENTION.search(p)]
    if not mentions:
        raise ValueError(
            "the policy does not mention GitHub private vulnerability reporting"
        )
    unavailable = any(_UNAVAILABLE.search(p) for p in mentions)
    offered = _REPORT_FORM in text
    if unavailable and offered:
        raise ValueError(
            "the policy says private vulnerability reporting is not available "
            f"and also links {_REPORT_FORM}; it must do one or the other"
        )
    if not unavailable and not offered:
        raise ValueError(
            "the policy mentions private vulnerability reporting without saying "
            f"it is not available and without linking {_REPORT_FORM}"
        )
    return "public" if offered else "private"


def check(text: str, visibility: str) -> str | None:
    """Return why ``text`` is wrong where the form is ``visibility``, or None."""
    try:
        state = policy_state(text)
    except ValueError as error:
        return str(error)
    if state == visibility:
        return None
    if visibility == "public":
        return (
            "private vulnerability reporting is available here and SECURITY.md "
            "still says it is not. Rewrite the reporting section to link the "
            f"form at {_REPORT_FORM}."
        )
    return (
        f"SECURITY.md links {_REPORT_FORM}, and private vulnerability reporting "
        "is not available here: the repository is private, or reporting is not "
        "enabled on it. Remove the link, or enable reporting with "
        "gh api -X PUT repos/OWNER/REPO/private-vulnerability-reporting."
    )


def main(argv: Sequence[str]) -> int:
    """Check the policy at ``argv[1]`` against the visibility in ``argv[0]``."""
    if not 1 <= len(argv) <= 2 or argv[0] not in STATES:
        print(
            f"usage: {Path(__file__).name} {{private|public}} [PATH]", file=sys.stderr
        )
        return 2
    path = Path(argv[1]) if len(argv) == 2 else Path("SECURITY.md")
    problem = check(path.read_text(encoding="utf-8"), argv[0])
    if problem:
        print(f"FAIL - {problem}", file=sys.stderr)
        return 1
    form = (
        "links the reporting form"
        if argv[0] == "public"
        else "says the reporting form is not available"
    )
    print(f"{path} {form}, which is true here.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
