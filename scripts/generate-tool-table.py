#!/usr/bin/env python3
"""Write the tool table in ``README.md`` from the tools the server publishes.

The table was typed by hand in nine documents and drifted twice (#47, #66).
This writes the one copy that is kept outside the reference: each tool's name
and the opening paragraph of the description the server sends a client, between
the two marker comments in the README.

    python scripts/generate-tool-table.py           # rewrite the table
    python scripts/generate-tool-table.py --check   # exit 1 if it is stale

tests/unit/test_generated_tool_table.py runs the same comparison, so a tool
added, removed or re-described without running this fails the unit suite.
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# Add src to path for imports
sys.path.insert(0, str(_ROOT / "src"))

README = _ROOT / "README.md"

BEGIN = (
    "<!-- tool-table:begin - written by scripts/generate-tool-table.py, "
    "do not edit by hand -->"
)
END = "<!-- tool-table:end -->"

FRAMEWORK_CATEGORY = "Framework Access Tools"
RISK_CATEGORY = "Risk & Mitigation Tools"
SYSTEM_CATEGORY = "System Monitoring Tools"

#: The categories in the order the table presents them.
CATEGORIES = (FRAMEWORK_CATEGORY, RISK_CATEGORY, SYSTEM_CATEGORY)

#: The document kind a tool is about -> its category. A tool about anything
#: else is service machinery.
_CATEGORY_BY_SUBJECT = {
    "framework": FRAMEWORK_CATEGORY,
    "frameworks": FRAMEWORK_CATEGORY,
    "risk": RISK_CATEGORY,
    "risks": RISK_CATEGORY,
    "mitigation": RISK_CATEGORY,
    "mitigations": RISK_CATEGORY,
}

_VERB = re.compile(r"^[a-z]+_")


def category_of(name: str) -> str:
    """Return the category a tool belongs to, from the subject in its name."""
    return _CATEGORY_BY_SUBJECT.get(_VERB.sub("", name, count=1), SYSTEM_CATEGORY)


def summary_of(name: str, description: str | None) -> str:
    """Return the opening paragraph of a tool's description as one table cell."""
    paragraph = (description or "").strip().split("\n\n", 1)[0]
    summary = " ".join(paragraph.split()).replace("|", "\\|")
    if not summary:
        raise ValueError(f"{name} has no description to put in the table")
    return summary


def render(tools: list[tuple[str, str | None]]) -> str:
    """Return the marked block for ``(name, description)`` pairs, in that order."""
    lines = [BEGIN]
    for category in CATEGORIES:
        members = [tool for tool in tools if category_of(tool[0]) == category]
        if not members:
            continue
        lines += [
            "",
            f"### {category} ({len(members)})",
            "",
            "| Tool | What it does |",
            "|------|--------------|",
        ]
        lines += [
            f"| `{name}` | {summary_of(name, description)} |"
            for name, description in members
        ]
    lines += ["", END]
    return "\n".join(lines)


def replace_block(text: str, block: str) -> str:
    """Return ``text`` with what lies between the two markers replaced."""
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError(
            f"expected exactly one {BEGIN!r} and one {END!r}, found "
            f"{text.count(BEGIN)} and {text.count(END)}"
        )
    start, end = text.index(BEGIN), text.index(END)
    if end < start:
        raise ValueError(f"{END!r} comes before {BEGIN!r}")
    return text[:start] + block + text[end + len(END) :]


async def published_tools() -> list[tuple[str, str | None]]:
    """The tools the assembled server lists, in the order it lists them."""
    from finos_mcp.fastmcp_server import mcp

    return [(tool.name, tool.description) for tool in await mcp.list_tools()]


def main(argv: list[str] | None = None, readme: Path = README) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="change nothing; exit 1 if the table is not what would be written",
    )
    args = parser.parse_args(argv)

    current = readme.read_text(encoding="utf-8")
    wanted = replace_block(current, render(asyncio.run(published_tools())))
    if wanted == current:
        print(f"{readme.name}: tool table is up to date")
        return 0
    if args.check:
        print(
            f"{readme.name}: tool table is stale. "
            "Run: python scripts/generate-tool-table.py",
            file=sys.stderr,
        )
        return 1
    readme.write_text(wanted, encoding="utf-8")
    print(f"{readme.name}: tool table rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
