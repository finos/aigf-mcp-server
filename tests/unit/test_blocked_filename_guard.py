"""Behaviour of the staged-filename guard, driven as pre-commit drives it.

``scripts/scan-blocked-filenames.sh`` is the body of the ``block-dev-only-files``
hook. It used to walk the working tree with ``find``, carrying a hardcoded list
of directory names to skip; a virtualenv named anything else -- measured with
``.venv312`` -- tripped a ``CRITICAL SECURITY`` failure on vendored library
files nobody wrote and nobody can delete (#84, and #56 before it).

These tests run the script against a real throwaway repository, because the
defects that mattered were all about *which set of files it looks at*, and that
is only observable with an index to look at.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

GUARD = Path(__file__).resolve().parents[2] / "scripts" / "scan-blocked-filenames.sh"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "test")
    return repo


def _run(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(GUARD)], cwd=repo, capture_output=True, text=True, check=False
    )


def test_a_staged_file_named_for_the_tooling_is_blocked(tmp_path: Path) -> None:
    """The rule the policy actually states: no tracked filename may carry it."""
    repo = _repo(tmp_path)
    (repo / "claude-notes.md").write_text("internal\n", encoding="utf-8")
    _git(repo, "add", "claude-notes.md")

    result = _run(repo)

    assert result.returncode == 1, (
        "A staged file whose name carries the tooling token was allowed through. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "claude-notes.md" in result.stderr, (
        "The guard blocked without naming the offending file, which leaves a "
        f"contributor nothing to act on. stderr={result.stderr!r}"
    )


def test_removing_such_a_file_is_allowed(tmp_path: Path) -> None:
    """The guard must not block its own remedy.

    Measured on the real hook before this change: staging the deletion of
    ``config/examples/claude-desktop-config.json`` -- the one tracked file that
    matched -- exited 1. A rule that forbids adding a file *and* forbids
    removing it makes the file permanent, which is the opposite of the policy.
    """
    repo = _repo(tmp_path)
    (repo / "claude-notes.md").write_text("internal\n", encoding="utf-8")
    _git(repo, "add", "claude-notes.md")
    _git(repo, "-c", "core.hooksPath=/dev/null", "commit", "-qm", "seed")
    _git(repo, "rm", "-q", "claude-notes.md")

    result = _run(repo)

    assert result.returncode == 0, (
        "The guard blocked a staged deletion, so a file matching the rule can "
        f"never be removed. stderr={result.stderr!r}"
    )


def test_an_ignored_working_tree_file_never_fires(tmp_path: Path) -> None:
    """#84's acceptance criterion, as a test.

    The old guard ran ``find .`` and skipped a hardcoded list of five directory
    names. A virtualenv named anything else -- measured with ``.venv312`` --
    still matched the vendored ``mcp/cli/claude.py`` that every install of the
    ``mcp`` package ships, and reported a ``CRITICAL SECURITY`` failure on a
    file the contributor did not write and cannot delete. The list enumerated
    names, so it could never be complete; reading the index instead is what
    makes the whole class impossible.

    An innocuous file is staged on purpose: with an empty index the guard would
    pass without deciding anything, and a test that cannot fail is not a test.
    """
    repo = _repo(tmp_path)
    vendored = (
        repo / ".venv312" / "lib" / "python3.12" / "site-packages" / "mcp" / "cli"
    )
    vendored.mkdir(parents=True)
    (vendored / "claude.py").write_text(
        "# vendored by the mcp package\n", encoding="utf-8"
    )
    (repo / ".gitignore").write_text(".venv312/\n", encoding="utf-8")
    (repo / "README.md").write_text("real work\n", encoding="utf-8")
    _git(repo, "add", ".gitignore", "README.md")

    result = _run(repo)

    assert result.returncode == 0, (
        "The guard fired on an ignored virtualenv the contributor did not "
        f"write. stderr={result.stderr!r}"
    )


def test_the_token_is_caught_anywhere_in_the_path(tmp_path: Path) -> None:
    """Why one guard replaced two.

    The hook this one absorbed matched ``(^|/)\\.?claude`` -- a path *segment*
    that starts with the token. It therefore missed ``src/my_claude.py`` and
    ``notes-claude.md``, which are exactly the shape a leaked session file
    takes. The surviving rule is the substring one, so its match set strictly
    contains the absorbed hook's; dropping the narrower guard loses nothing.
    """
    repo = _repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "my_claude.py").write_text("notes\n", encoding="utf-8")
    _git(repo, "add", "src/my_claude.py")

    result = _run(repo)

    assert result.returncode == 1, (
        "A mid-name match was allowed through, so the surviving guard does not "
        f"subsume the one it replaced. stderr={result.stderr!r}"
    )
    assert "my_claude.py" in result.stderr
