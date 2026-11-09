"""Guards that ``scripts/README.md`` is the inventory of ``scripts/``.

Three scripts were reachable from nothing but that README (#75): a version
bumper that read ``target-version = "py310"`` as the project version and
stopped there, and two validators, one calling the other, that nothing called.
The README listed all three as maintained while leaving out eight scripts the
gates run, so being listed said nothing about a script either way.

The first test wants an entry, in one spelling, for every script in the index.
The second wants every ``scripts/...`` path the README mentions, in any
spelling, to be in the index. "Tracked" is ``git ls-files``: a file deleted
from disk but not from the index still counts. What neither can close: the
description beside an entry can be wrong, including its *manual* marking, and
a listed script can still be one nobody runs. That is a judgement made when
the entry is written.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_SCRIPTS = "scripts"
_INVENTORY = "scripts/README.md"
# An entry is a list item that opens with the script's path in backticks.
_ENTRY = re.compile(r"^- `(scripts/[^`\s]+)`\s*$", re.MULTILINE)
# Any path into the directory, however the line around it is written. A stale
# entry spelled `* scripts/x.sh` or followed by a remark is still a stale entry.
_MENTION = re.compile(r"scripts/[A-Za-z0-9_./-]*[A-Za-z0-9_]")


def _repo_root(pytestconfig: pytest.Config) -> Path:
    return Path(str(pytestconfig.rootpath))


def _tracked_scripts(root: Path) -> set[str]:
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", _SCRIPTS],
        cwd=root,
        capture_output=True,
        check=True,
    ).stdout
    tracked = {path.decode("utf-8") for path in listed.split(b"\0") if path}
    return tracked - {_INVENTORY}


def _inventory_text(root: Path) -> str:
    return (root / _INVENTORY).read_text(encoding="utf-8")


def _listed_scripts(root: Path) -> list[str]:
    return _ENTRY.findall(_inventory_text(root))


def test_the_inventory_lists_every_tracked_script(
    pytestconfig: pytest.Config,
) -> None:
    root = _repo_root(pytestconfig)
    tracked = _tracked_scripts(root)
    assert len(tracked) >= 10, f"only {len(tracked)} tracked scripts were found"

    unlisted = sorted(tracked - set(_listed_scripts(root)))
    assert not unlisted, (
        f"{_INVENTORY} does not list {unlisted}. Add an entry saying what runs "
        "each one, or delete the script."
    )


def test_the_inventory_names_no_script_that_is_not_tracked(
    pytestconfig: pytest.Config,
) -> None:
    root = _repo_root(pytestconfig)
    mentioned = set(_MENTION.findall(_inventory_text(root)))
    assert len(mentioned) >= 10, (
        f"only {len(mentioned)} script paths were read from {_INVENTORY}"
    )

    missing = sorted(mentioned - _tracked_scripts(root) - {_INVENTORY})
    assert not missing, f"{_INVENTORY} names {missing}, which git does not track."

    listed = _listed_scripts(root)
    repeated = sorted({path for path in listed if listed.count(path) > 1})
    assert not repeated, f"{_INVENTORY} lists {repeated} more than once."
