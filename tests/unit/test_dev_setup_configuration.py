# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The setup scripts hand a developer the file the server reads (#198, #219).

``scripts/dev-setup.sh`` wrote ``.env.dev`` and ``scripts/dev-quick-setup.sh``
wrote ``.env.local``. ``Settings`` read ``.env`` and nothing else, so a
developer who followed either script edited a file with no effect.
``.env.dev`` also carried two settings the server does not have, which stop
it at startup once the file is renamed to the one that is read, and it was
not git-ignored while the script asked for a GitHub token to be put in it.

Both scripts now copy ``.env.example`` to ``.env`` when there is none.
``.env.example`` is held against ``Settings`` by
``test_environment_documentation.py``, so there is one list of settings.

Since #283 no file is read unless ``FINOS_MCP_ENV_FILE`` names it, so each
script must also tell the developer to set that variable to the file.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from finos_mcp.config import ENV_FILE_VARIABLE, Settings

pytestmark = pytest.mark.unit

#: script, and the function in it that prepares the configuration.
SETUP_SCRIPTS = [
    ("scripts/dev-setup.sh", "setup_dev_config"),
    ("scripts/dev-quick-setup.sh", "setup_environment"),
]


def _prepare(root: Path, script: str, function: str, project: Path) -> None:
    """Run one script's configuration step against a scratch project."""
    completed = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; PROJECT_ROOT="$PWD"; "$2"',
            "bash",
            str(root / script),
            function,
        ],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def _env_files(project: Path) -> set[str]:
    return {entry.name for entry in project.iterdir() if entry.name.startswith(".env")}


@pytest.mark.parametrize(("script", "function"), SETUP_SCRIPTS)
def test_setup_gives_a_developer_the_file_the_server_reads(
    pytestconfig: pytest.Config, tmp_path: Path, script: str, function: str
) -> None:
    root = Path(str(pytestconfig.rootpath))
    example = (root / ".env.example").read_text(encoding="utf-8")
    (tmp_path / ".env.example").write_text(example, encoding="utf-8")

    _prepare(root, script, function, tmp_path)

    assert Settings.model_config["env_file"] is None, (
        "Settings reads a file of its own again, so this test and both scripts "
        "are preparing the wrong one"
    )
    assert _env_files(tmp_path) == {".env.example", ".env"}, (
        f"{script} left a configuration file the server does not read"
    )
    assert (tmp_path / ".env").read_text(encoding="utf-8") == example
    # The server reads the file only when told to; the script says how.
    assert f"{ENV_FILE_VARIABLE}=" in (root / script).read_text(encoding="utf-8"), (
        f"{script} prepares .env without saying to set {ENV_FILE_VARIABLE} to it"
    )
    # The point of the file: the server starts with it. An unknown key in an
    # env file stops startup (#194).
    Settings(_env_file=tmp_path / ".env")


@pytest.mark.parametrize(("script", "function"), SETUP_SCRIPTS)
def test_setup_leaves_an_existing_configuration_alone(
    pytestconfig: pytest.Config, tmp_path: Path, script: str, function: str
) -> None:
    root = Path(str(pytestconfig.rootpath))
    (tmp_path / ".env.example").write_text("FINOS_MCP_LOG_LEVEL=INFO\n")
    mine = "FINOS_MCP_LOG_LEVEL=DEBUG\n"
    (tmp_path / ".env").write_text(mine)

    _prepare(root, script, function, tmp_path)

    assert (tmp_path / ".env").read_text() == mine
    assert _env_files(tmp_path) == {".env.example", ".env"}


_SETTING_NAME = re.compile(r"\bFINOS_MCP_[A-Z0-9_]+\b")


def _unknown_settings(root: Path) -> dict[str, set[str]]:
    """Per tracked script, the ``FINOS_MCP_*`` names ``Settings`` does not have."""
    prefix = Settings.model_config["env_prefix"]
    known = {f"{prefix}{name}".upper() for name in Settings.model_fields}
    known.add(ENV_FILE_VARIABLE)  # read before the settings, not one of them
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "scripts"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    scripts = [entry for entry in tracked.split("\0") if entry]
    assert scripts, "no script was scanned"

    unknown: dict[str, set[str]] = {}
    for script in scripts:
        text = (root / script).read_text(encoding="utf-8", errors="replace")
        if names := set(_SETTING_NAME.findall(text)) - known:
            unknown[script] = names
    return unknown


def test_no_script_names_a_setting_the_server_does_not_have(
    pytestconfig: pytest.Config,
) -> None:
    """A name is enough: a script that reads or prints one misleads as well."""
    unknown = {
        script: sorted(names)
        for script, names in _unknown_settings(Path(str(pytestconfig.rootpath))).items()
    }

    assert not unknown, f"these scripts name settings Settings does not have: {unknown}"


#: ``.venv`` as a directory name, not ``.venv-semgrep`` or ``.venv312``.
_DOT_VENV = re.compile(r"(?<![\w-])\.venv(?![\w-])")


def test_no_script_uses_a_virtualenv_the_gates_do_not_look_for(
    pytestconfig: pytest.Config,
) -> None:
    """The setup scripts make the ``venv/`` every gate resolves (#407).

    ``scripts/project-python.sh`` looks for ``$PYTHON_BIN``, ``venv/bin/python``
    and ``$VIRTUAL_ENV``. Five scripts made and used ``.venv``, so after the
    documented setup ``ci-local.sh`` in a new shell found no virtualenv.
    """
    root = Path(str(pytestconfig.rootpath))
    scripts = sorted((root / "scripts").glob("*.sh"))
    assert len(scripts) >= 5, f"only {len(scripts)} scripts found"
    # dev-only-paths.sh names .venv/ among the directories that must never be
    # committed; a comment may recall the old name.
    naming = [
        f"{script.name}:{number}"
        for script in scripts
        if script.name != "dev-only-paths.sh"
        for number, line in enumerate(script.read_text("utf-8").splitlines(), 1)
        if _DOT_VENV.search(line) and not line.lstrip().startswith("#")
    ]
    assert not naming, f"these script lines use .venv instead of venv/: {naming}"
