"""Guards that the README's tool table is the one the server would write.

The tool inventory was typed by hand in nine documents and drifted twice (#47,
#66). The copies were reduced to a reference and this table, and the table is
written by ``scripts/generate-tool-table.py`` from the tools the assembled
server lists. These tests are what makes "generated" true on every commit
rather than on the day the script was last run: the README is compared with
what the script would write now.

What this does not close: the summaries are the opening paragraph of each
tool's description, so a description that is wrong produces a table that is
wrong in the same words. ``test_tool_description_truth.py`` is the guard for
the descriptions themselves.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest

from finos_mcp.fastmcp_server import mcp
from tests.helpers import load_module

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "generate-tool-table.py"


def _load_script() -> ModuleType:
    return load_module(_SCRIPT, "generate_tool_table")


async def _served() -> list[tuple[str, str | None]]:
    return [(tool.name, tool.description) for tool in await mcp.list_tools()]


async def test_the_readme_table_is_what_the_script_writes_today() -> None:
    """A tool added, removed or re-described without running the script fails."""
    script = _load_script()
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    tools = await _served()
    assert len(tools) >= 5, f"the server listed only {len(tools)} tools"

    block = script.render(tools)
    for name, _ in tools:
        assert f"| `{name}` |" in block, f"{name} has no row in the rendered table"

    assert script.replace_block(readme, block) == readme, (
        "the tool table in README.md is not what the server's tools produce. "
        "Run: python scripts/generate-tool-table.py"
    )


def test_a_tool_lands_under_the_category_its_name_puts_it_in() -> None:
    script = _load_script()
    block = script.render(
        [
            ("get_cache_stats", "Cache numbers."),
            ("list_risks", "Every risk.\n\nMore about risks."),
            ("search_frameworks", "Find a\n    phrase."),
            ("get_mitigation", "One | mitigation."),
        ]
    )
    assert block == "\n".join(
        [
            script.BEGIN,
            "",
            "### Framework Access Tools (1)",
            "",
            "| Tool | What it does |",
            "|------|--------------|",
            "| `search_frameworks` | Find a phrase. |",
            "",
            "### Risk & Mitigation Tools (2)",
            "",
            "| Tool | What it does |",
            "|------|--------------|",
            "| `list_risks` | Every risk. |",
            "| `get_mitigation` | One \\| mitigation. |",
            "",
            "### System Monitoring Tools (1)",
            "",
            "| Tool | What it does |",
            "|------|--------------|",
            "| `get_cache_stats` | Cache numbers. |",
            "",
            script.END,
        ]
    )


@pytest.mark.parametrize("description", [None, "", "  \n\n  "])
def test_a_tool_without_a_description_is_refused(description: str | None) -> None:
    """An empty cell would be written and then pass the comparison forever."""
    script = _load_script()
    with pytest.raises(ValueError, match="list_risks has no description"):
        script.render([("list_risks", description)])


def test_only_what_lies_between_the_markers_is_replaced() -> None:
    script = _load_script()
    page = f"before\n{script.BEGIN}\nold table\n{script.END}\nafter\n"
    assert script.replace_block(page, f"{script.BEGIN}\nnew\n{script.END}") == (
        f"before\n{script.BEGIN}\nnew\n{script.END}\nafter\n"
    )


@pytest.mark.parametrize(
    ("page", "message"),
    [
        ("no markers at all", "found 0 and 0"),
        ("{begin}\n{begin}\n{end}", "found 2 and 1"),
        ("{begin}\nnever closed", "found 1 and 0"),
        ("{end}\n{begin}", "comes before"),
    ],
)
def test_a_page_whose_markers_are_wrong_is_refused(page: str, message: str) -> None:
    """Without both markers, in order, there is no telling what to overwrite."""
    script = _load_script()
    text = page.format(begin=script.BEGIN, end=script.END)
    with pytest.raises(ValueError, match=message):
        script.replace_block(text, "anything")


def test_check_reports_a_stale_table_and_changes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    script = _load_script()
    stale = f"# Title\n\n{script.BEGIN}\nold table\n{script.END}\n\ntail\n"
    readme = tmp_path / "README.md"
    readme.write_text(stale, encoding="utf-8")

    assert script.main(["--check"], readme=readme) == 1
    assert "tool table is stale" in capsys.readouterr().err
    assert readme.read_text(encoding="utf-8") == stale

    assert script.main([], readme=readme) == 0
    written = readme.read_text(encoding="utf-8")
    assert written.startswith("# Title\n\n" + script.BEGIN)
    assert written.endswith(script.END + "\n\ntail\n")
    assert "| `list_frameworks` |" in written

    assert script.main(["--check"], readme=readme) == 0
    assert script.main([], readme=readme) == 0
    assert readme.read_text(encoding="utf-8") == written
