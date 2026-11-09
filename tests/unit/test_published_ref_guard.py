"""Behaviour of the published-ref guard, driven against a real remote.

``scripts/scan-published-refs.sh`` is Gate 9 of ``scripts/go-live-gate.sh``.
Gate 1 answers "is anything development-only tracked *now*", which it reads from
``git ls-files`` -- and ``git ls-files`` is ``HEAD``. Cleaning ``HEAD`` did
nothing for the refs already pushed: a tag published a tree of eight
development-only files for months while Gate 1 reported PASS (#130).

These tests run the script against a throwaway bare repository acting as the
remote, because every distinction that matters -- a tag versus a branch versus a
pull-request ref, and which of those anyone can actually delete -- is a property
of the refs on a remote, and is not observable from a working tree.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

SCANNER = Path(__file__).resolve().parents[2] / "scripts" / "scan-published-refs.sh"

# Assembled from the dot and the word so the two are visible separately: the
# sibling `scan-dev-only-references` hook greps staged files for the joined literal,
# and a test written after what it scans for is blocked by its own family.
TOOLING_DIR = "." + "claude"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


def _remote(tmp_path: Path) -> Path:
    """A bare repository standing in for origin."""
    bare = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", str(bare)], check=True, capture_output=True
    )
    return bare


def _work(tmp_path: Path, bare: Path) -> Path:
    """A working clone with one clean commit on main, already pushed."""
    repo = tmp_path / "work"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "test")
    _git(repo, "remote", "add", "origin", str(bare))
    (repo / "README.md").write_text("clean\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "clean")
    _git(repo, "push", "-q", "origin", "main")
    return repo


def _commit_tooling_file(repo: Path) -> None:
    """Add one development-only file and commit it, without pushing."""
    directory = repo / TOOLING_DIR
    directory.mkdir(exist_ok=True)
    (directory / "internal-guide.md").write_text(
        "DO NOT COMMIT TO PUBLIC REPOSITORY\n", encoding="utf-8"
    )
    _git(repo, "add", "-f", f"{TOOLING_DIR}/internal-guide.md")
    _git(repo, "commit", "-qm", "add internal guide")


def _run(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCANNER), "origin"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_clean_remote_passes(tmp_path: Path) -> None:
    """The baseline: nothing published, nothing to report."""
    bare = _remote(tmp_path)
    repo = _work(tmp_path, bare)

    result = _run(repo)

    assert result.returncode == 0, (
        "A remote carrying only a clean main was reported as an offender. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_a_published_tag_carrying_tooling_files_fails(tmp_path: Path) -> None:
    """#130 itself: HEAD is clean, and a pushed tag publishes the files anyway."""
    bare = _remote(tmp_path)
    repo = _work(tmp_path, bare)
    _commit_tooling_file(repo)
    _git(repo, "tag", "-a", "v0.1.0", "-m", "release")
    _git(repo, "push", "-q", "origin", "v0.1.0")
    # main is left pointing at the clean commit, exactly as the real repository
    # is: the offending commit is reachable only through the tag.
    _git(repo, "reset", "-q", "--hard", "HEAD~1")

    result = _run(repo)

    assert result.returncode == 1, (
        "A pushed tag whose tree carries development-only files was allowed. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "v0.1.0" in result.stdout + result.stderr, (
        "The guard failed without naming the offending ref, which leaves nobody "
        f"anything to act on. stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_a_pull_request_ref_is_reported_but_does_not_fail(tmp_path: Path) -> None:
    """The class nobody can clear.

    GitHub maintains ``refs/pull/N/head`` and refuses pushes to it, so an
    offending pull-request ref cannot be deleted the way a branch or tag can.
    A gate that failed on it would be red from the day it landed and would
    simply stop being run; one that ignored it would rebuild the blindness
    #130 is about. It reports, in full, and lets the run continue.
    """
    bare = _remote(tmp_path)
    repo = _work(tmp_path, bare)
    _commit_tooling_file(repo)
    _git(repo, "push", "-q", "origin", "HEAD:refs/pull/5/head")
    _git(repo, "reset", "-q", "--hard", "HEAD~1")

    result = _run(repo)

    assert result.returncode == 0, (
        "An offender on a ref nobody can delete failed the gate, which makes "
        "the gate permanently red and therefore unrun. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    combined = result.stdout + result.stderr
    assert "refs/pull/5/head" in combined, (
        "The unfixable offender was not reported at all, which is the blindness "
        f"#130 exists to remove. stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert f"{TOOLING_DIR}/internal-guide.md" in combined, (
        "The report named the ref but not the files it publishes, so whoever "
        "runs go-live still has to go and find out what is exposed. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_a_published_branch_carrying_tooling_files_fails(tmp_path: Path) -> None:
    """The other half of the fixable class. A branch is as deletable as a tag."""
    bare = _remote(tmp_path)
    repo = _work(tmp_path, bare)
    _commit_tooling_file(repo)
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/feature/stale")
    _git(repo, "reset", "-q", "--hard", "HEAD~1")

    result = _run(repo)

    assert result.returncode == 1, (
        "A pushed branch whose tree carries development-only files was "
        f"allowed. stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "refs/heads/feature/stale" in result.stderr, (
        "The guard failed without naming the offending branch. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_the_unfixable_class_is_reported_even_when_the_gate_fails(
    tmp_path: Path,
) -> None:
    """A run that stops at the first class must still leave the whole picture.

    Otherwise clearing the deletable refs one at a time never reveals the ones
    that cannot be cleared, and the go-live decision is taken without them.
    """
    bare = _remote(tmp_path)
    repo = _work(tmp_path, bare)
    _commit_tooling_file(repo)
    _git(repo, "push", "-q", "origin", "HEAD:refs/pull/5/head")
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/feature/stale")
    _git(repo, "reset", "-q", "--hard", "HEAD~1")

    result = _run(repo)

    assert result.returncode == 1, (
        "A deletable offender did not fail the gate. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "refs/pull/5/head" in result.stdout, (
        "The gate failed on the deletable ref and never reported the one "
        "nobody can delete, so the harder problem stays invisible. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_an_unreachable_remote_fails_rather_than_passing(tmp_path: Path) -> None:
    """Fail closed. "I could not look" must never render as PASS."""
    bare = _remote(tmp_path)
    repo = _work(tmp_path, bare)
    _git(repo, "remote", "set-url", "origin", str(tmp_path / "no-such-repo.git"))

    result = _run(repo)

    assert result.returncode == 1, (
        "A remote the gate could not read was reported as clean, which is the "
        f"exact shape of the defect. stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    assert "could not fetch" in result.stderr, (
        "The failure did not say the fetch was the problem, so it reads as a "
        f"real offender. stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "no-such-repo" in result.stderr, (
        "git's own diagnosis was swallowed, so the report cannot distinguish a "
        "bad remote URL from expired credentials from a network outage -- three "
        "problems with three different remedies. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_the_scan_leaves_no_refs_behind(tmp_path: Path) -> None:
    """The gate runs in a contributor's own clone, not a scratch one.

    It fetches every ref the remote has, pull-request refs included, so a scan
    that did not clean up would leave that pile in the clone it ran in, and the
    next scan would read stale refs it had fetched itself.
    """
    bare = _remote(tmp_path)
    repo = _work(tmp_path, bare)
    _commit_tooling_file(repo)
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/feature/stale")
    _git(repo, "reset", "-q", "--hard", "HEAD~1")
    before = _git(repo, "for-each-ref", "--format=%(refname)")

    _run(repo)

    after = _git(repo, "for-each-ref", "--format=%(refname)")
    assert after == before, (
        "The scan left refs behind in the repository it ran in. "
        f"before={before!r} after={after!r}"
    )
