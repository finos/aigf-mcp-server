"""No tracked file names the repository this work was developed in (#387).

The project's home is ``finos/aigf-mcp-server``. Every link, clone command,
``$id`` or ``gh --repo`` example that named the development repository sent a
reader away from it. The maintainer's GitHub
handle (CODEOWNERS) is not a repository path and stays allowed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

# Assembled from its parts, so this file does not name it.
_DEVELOPMENT_REPOSITORY = "hugo-calderon" + "/" + "finos-mcp-server"


def _tracked_files(root: Path) -> list[Path]:
    listed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        capture_output=True,
        check=True,
    ).stdout.split(b"\0")
    return [root / name.decode() for name in listed if name]


def test_no_tracked_file_names_the_development_repository(
    pytestconfig: pytest.Config,
) -> None:
    root = Path(pytestconfig.rootpath)
    files = _tracked_files(root)
    assert len(files) > 100, f"git ls-files listed only {len(files)} files"

    naming = sorted(
        path.relative_to(root).as_posix()
        for path in files
        if path.is_file()
        and _DEVELOPMENT_REPOSITORY.casefold()
        in path.read_bytes().decode("utf-8", "replace").casefold()
    )

    assert not naming, (
        f"These tracked files name {_DEVELOPMENT_REPOSITORY}, a private "
        f"repository no reader can open: {naming}. Name finos/aigf-mcp-server."
    )
