"""The canonical environment example covers the public Settings fields (#68).

Coverage requires an assignment, including a commented optional assignment;
mentioning a variable in prose alone does not tell an operator how to set it.
Conversely, even prose must not advertise a FINOS_MCP variable that Settings
does not expose. Properties derived from fields are not environment settings.
"""

import os
import re
from pathlib import Path

import pytest

from finos_mcp.config import ENV_FILE_VARIABLE, Settings

pytestmark = pytest.mark.unit

_ASSIGNMENT = re.compile(
    r"^[ \t]*(?:#[ \t]*)?(?:export[ \t]+)?"
    r"(FINOS_MCP_[A-Z0-9_]+)[ \t]*=[ \t]*(.*)$",
    re.MULTILINE | re.IGNORECASE,
)
_REFERENCE = re.compile(r"\bFINOS_MCP_[A-Z0-9_]+\b", re.IGNORECASE)


def _assignments(text: str) -> dict[str, list[str]]:
    assignments: dict[str, list[str]] = {}
    for name, value in _ASSIGNMENT.findall(text):
        assignments.setdefault(name.upper(), []).append(value)
    return assignments


def test_environment_example_covers_settings_in_both_directions(
    pytestconfig: pytest.Config,
) -> None:
    text = (Path(str(pytestconfig.rootpath)) / ".env.example").read_text(
        encoding="utf-8"
    )
    # These public fields use the prefix configured by Settings; derived
    # properties such as repo_target do not appear in model_fields.
    fields = Settings.model_fields
    assert len(fields) >= 1, "Settings exposes no fields to the environment-doc guard"
    expected = {
        f"{Settings.model_config['env_prefix']}{name}".upper() for name in fields
    }
    documented = _assignments(text)
    missing = sorted(expected - documented.keys())
    assert not missing, f".env.example is missing Settings assignments: {missing}"

    # The file may say how it is read; it cannot assign that variable, which
    # is read before the file is (#283).
    assert ENV_FILE_VARIABLE not in documented, (
        f".env.example assigns {ENV_FILE_VARIABLE}, which no file can set"
    )
    unknown = sorted(
        {name.upper() for name in _REFERENCE.findall(text)}
        - expected
        - {ENV_FILE_VARIABLE}
    )
    assert not unknown, (
        f".env.example names variables Settings does not expose: {unknown}"
    )


@pytest.mark.parametrize("field", ["enable_cache"])
@pytest.mark.parametrize("enabled", [True, False])
def test_documented_true_by_default_settings_load_from_an_env_file(
    pytestconfig: pytest.Config,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    enabled: bool,
) -> None:
    """Exercise the example value and its opposite so defaults cannot mask no-ops."""
    for name in tuple(os.environ):
        if name.upper().startswith("FINOS_MCP_"):
            monkeypatch.delenv(name)
    text = (Path(str(pytestconfig.rootpath)) / ".env.example").read_text(
        encoding="utf-8"
    )
    name = f"FINOS_MCP_{field.upper()}"
    examples = _assignments(text).get(name, [])
    assert examples, f"missing environment example for {name}"

    defaults = Settings(_env_file=None)
    assert getattr(defaults, field) is True, (
        f"{name} no longer defaults to the documented true"
    )

    # The first assignment is the primary example; later commented scenarios
    # may repeat a setting, as they already do for logging and caching.
    # Use the actual documented value for the true case. The false control
    # proves that ignoring the variable cannot accidentally satisfy this test.
    value = examples[0] if enabled else "false"
    env_file = tmp_path / "example.env"
    env_file.write_text(f"{name}={value}\n", encoding="utf-8")
    configured = Settings(_env_file=env_file)
    assert getattr(configured, field) is enabled, (
        f"{name}={value} did not configure {field} to {enabled}"
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("FINOS_MCP_LOG_LEVEL=DEBUG\n", {"FINOS_MCP_LOG_LEVEL": ["DEBUG"]}),
        ("# FINOS_MCP_LOG_LEVEL=INFO\n", {"FINOS_MCP_LOG_LEVEL": ["INFO"]}),
        (
            "  # export finos_mcp_log_level = DEBUG\n",
            {"FINOS_MCP_LOG_LEVEL": ["DEBUG"]},
        ),
        ("# Configure FINOS_MCP_LOG_LEVEL for logging.\n", {}),
        (
            "FINOS_MCP_LOG_LEVEL=INFO\n# FINOS_MCP_LOG_LEVEL=DEBUG\n",
            {"FINOS_MCP_LOG_LEVEL": ["INFO", "DEBUG"]},
        ),
    ],
)
def test_example_scanner_distinguishes_assignments_from_mentions(
    text: str, expected: dict[str, list[str]]
) -> None:
    assert _assignments(text) == expected, (
        "environment example assignment scanner changed"
    )
