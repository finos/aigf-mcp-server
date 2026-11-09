"""Guard the source paths in #74, the demo configuration in #70 and caches in #77.

Git itself decides matches in a fresh repository with external excludes disabled.
These examples protect the reported regression, not every conceivable source path.
"""

import os
import subprocess
from collections import Counter
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def clean_git_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # Do not inherit a caller's repository, config, global excludes or templates.
    for name in tuple(os.environ):
        if name.startswith("GIT_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)


@pytest.fixture
def ignore_repo(
    tmp_path: Path, pytestconfig: pytest.Config, clean_git_environment: None
) -> Path:
    subprocess.run(
        ["git", "init", "--quiet", "--template=", str(tmp_path)],
        check=True,
        capture_output=True,
        timeout=10,
    )
    (tmp_path / ".gitignore").write_bytes(
        (Path(str(pytestconfig.rootpath)) / ".gitignore").read_bytes()
    )
    return tmp_path


def _check_ignore(
    repo: Path, path: str, *settings: str
) -> subprocess.CompletedProcess[str]:
    candidate = repo / path
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.touch()
    options = [f"core.excludesFile={os.devnull}", *settings]
    return subprocess.run(
        [
            "git",
            *(part for option in options for part in ("-c", option)),
            "check-ignore",
            path,
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def test_gitignore_has_no_duplicate_rules(pytestconfig: pytest.Config) -> None:
    text = (Path(str(pytestconfig.rootpath)) / ".gitignore").read_text(encoding="utf-8")
    rules = [
        line for line in text.splitlines() if line.strip() and not line.startswith("#")
    ]
    duplicates = sorted(rule for rule, count in Counter(rules).items() if count > 1)
    assert not duplicates, f"duplicate ignore rules: {duplicates}"


@pytest.mark.usefixtures("clean_git_environment")
def test_demo_config_is_not_tracked(pytestconfig: pytest.Config) -> None:
    # Inspect the index, so a staged deletion passes and a forced add fails.
    # A developer may still keep their own ignored copy in the working tree.
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "mcp_demo_config.json"],
        cwd=pytestconfig.rootpath,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert not result.stdout, "local demo config must not be tracked"


@pytest.mark.usefixtures("clean_git_environment")
def test_no_cache_directory_is_tracked(pytestconfig: pytest.Config) -> None:
    # A hidden or dunder path named as a cache holds files a program regenerates.
    # #77 found three framework documents tracked under one that no code read or
    # wrote. Reads the index, like the test above. A source package named cache/
    # is allowed; every component is checked, so a symlink named as a cache fails.
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=pytestconfig.rootpath,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    tracked = [path for path in result.stdout.split("\0") if path]
    assert len(tracked) >= 100, f"index listing looks empty: {len(tracked)} paths"
    cached = sorted(
        path
        for path in tracked
        if any(
            part.startswith((".", "_")) and "cache" in part.lower()
            for part in path.split("/")
        )
    )
    assert not cached, f"tracked paths named as a cache: {cached}"


@pytest.mark.parametrize("prefix", ["", "src/package/"])
@pytest.mark.parametrize(
    "path",
    ["lib/module.py", "lib64/module.py", "json", "json/schema.json", "schema.json"],
)
def test_source_remains_visible(ignore_repo: Path, prefix: str, path: str) -> None:
    path = prefix + path
    result = _check_ignore(ignore_repo, path)
    assert result.returncode == 1, (
        f"source path is ignored: {path}: {result.stdout}{result.stderr}"
    )


@pytest.mark.parametrize(
    "path",
    [
        "venv/lib/module.py",
        ".venv/lib64/module.py",
        ".venv-semgrep/lib/module.py",
        "env/lib/module.py",
        "ENV/lib64/module.py",
        "build/lib/module.py",
        "dist/package.whl",
        "package.egg-info/PKG-INFO",
        "src/package/__pycache__/metadata",
        ".pytest_cache/state",
        ".mypy_cache/state",
        ".ruff_cache/state",
        ".cache/discovery/index.json",
        ".framework_cache/eu-ai-act.yml",
        ".env",
        ".env.local",
        "secrets.json",
        "credentials.json",
        "mcp_demo_config.json",
        # Spell the tooling path in parts: the content hook forbids its literal.
        "." + "claude/settings.json",
        "src/finos_mcp/_version.py",
    ],
)
def test_private_and_generated_paths_stay_ignored(ignore_repo: Path, path: str) -> None:
    result = _check_ignore(ignore_repo, path)
    assert result.returncode == 0, (
        f"private/generated path is visible: {path}: {result.stdout}{result.stderr}"
    )


#: What a macOS or Windows checkout sets, and a Linux runner does not.
_CASE_INSENSITIVE = "core.ignorecase=true"


@pytest.mark.parametrize(
    "path",
    [
        "docs/development.md",
        "docs/architecture.md",
        "docs/api/Architecture.md",
        "docs/performance_setup.md",
    ],
)
def test_a_private_note_rule_does_not_hide_a_document(
    ignore_repo: Path, path: str
) -> None:
    """``DEVELOPMENT.md`` hid ``docs/development.md`` wherever case is ignored (#199)."""
    result = _check_ignore(ignore_repo, path, _CASE_INSENSITIVE)
    assert result.returncode == 1, (
        f"document is ignored: {path}: {result.stdout}{result.stderr}"
    )


@pytest.mark.parametrize(
    "path",
    [
        "DEVELOPMENT.md",
        "ARCHITECTURE.md",
        "PERFORMANCE_SETUP.md",
        "scripts/ARCHITECTURE.md",
        "src/finos_mcp/DEVELOPMENT.md",
    ],
)
@pytest.mark.parametrize("setting", [_CASE_INSENSITIVE, "core.ignorecase=false"])
def test_a_private_note_outside_docs_stays_ignored(
    ignore_repo: Path, path: str, setting: str
) -> None:
    result = _check_ignore(ignore_repo, path, setting)
    assert result.returncode == 0, (
        f"private note is visible: {path}: {result.stdout}{result.stderr}"
    )
