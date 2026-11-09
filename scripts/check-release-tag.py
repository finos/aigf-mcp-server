#!/usr/bin/env python3
"""Refuse a release whose tag the build cannot use, or whose files it does not name.

``release.yml`` names a release from the pushed tag, and ``setuptools_scm``
names the built files from git. The two could disagree in two ways: the
workflow's pattern accepts ``v0.0.0-ci.3``, a name every install and build of
the tagged commit stops on (#253), and a release was created as
``v0.0.0-ci.2`` with files named ``0.1.1rc2.dev113`` (#252).

    python scripts/check-release-tag.py v1.2.3              # the tag name
    python scripts/check-release-tag.py v1.2.3 --dist dist  # and the built files

The first form is the first command the workflow runs, before the project is
installed. The second runs after the build: when a commit carries two tags,
``setuptools_scm`` picks one of them itself, so only the file names say which
version was built.

With ``--github-output FILE`` an accepted tag also adds ``prerelease=true`` or
``prerelease=false`` to the file. The workflow marked a prerelease by a ``-``
in the tag, which is not what makes a version one: ``v1.2.3.rc1`` is the
release candidate ``1.2.3rc1``, and ``v1.2.3-1`` is the post-release
``1.2.3.post1`` (#256).

tests/unit/test_release_workflow.py runs both forms and reads the workflow for
the steps that call them.
"""

import argparse
import re
import sys
from pathlib import Path

from packaging.utils import (
    InvalidSdistFilename,
    InvalidWheelFilename,
    parse_sdist_filename,
    parse_wheel_filename,
)
from packaging.version import InvalidVersion, Version

#: ``vX.Y.Z`` with an optional ``-suffix`` or ``.suffix``. Matched with
#: ``fullmatch``: ``$`` also matches before a trailing newline, and ``Version``
#: strips whitespace, so a name ending in a newline would pass both.
_TAG = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.]+)?")


def release_version(tag: str) -> Version:
    """Return the version the build derives from ``tag``, or raise ``ValueError``."""
    if not _TAG.fullmatch(tag):
        raise ValueError(
            f"{tag!r} is not a release tag: expected vX.Y.Z, optionally followed "
            "by a suffix such as -rc.1"
        )
    try:
        return Version(tag.removeprefix("v"))
    except InvalidVersion:
        raise ValueError(
            f"{tag!r} is not a version the build can parse, so setuptools_scm "
            "stops on it. Use a suffix Python's version rules know, such as "
            "-rc.1, -a.1, -b.1, .post1 or .dev1. If the tag is already pushed, "
            "delete it: every build of that commit fails while it exists"
        ) from None


def built_versions(dist: Path) -> dict[str, Version]:
    """Return the version in the name of every file in ``dist``."""
    versions: dict[str, Version] = {}
    for path in sorted(dist.iterdir()):
        try:
            if path.name.endswith(".whl"):
                versions[path.name] = parse_wheel_filename(path.name)[1]
            else:
                versions[path.name] = parse_sdist_filename(path.name)[1]
        except (InvalidSdistFilename, InvalidWheelFilename):
            raise ValueError(
                f"{path.name} in {dist} is neither a source archive nor a wheel"
            ) from None
    return versions


def check_files(tag: str, dist: Path) -> None:
    """Raise ``ValueError`` unless ``dist`` holds one archive and one wheel of ``tag``."""
    expected = release_version(tag)
    if not dist.is_dir():
        raise ValueError(f"{dist} is not a directory, so no file was built")
    versions = built_versions(dist)
    wheels = [name for name in versions if name.endswith(".whl")]
    archives = [name for name in versions if not name.endswith(".whl")]
    if len(wheels) != 1 or len(archives) != 1:
        raise ValueError(
            f"{dist} must hold one source archive and one wheel, found "
            f"{sorted(versions) or 'no file'}"
        )
    wrong = sorted(name for name, version in versions.items() if version != expected)
    if wrong:
        raise ValueError(
            f"tag {tag} is version {expected}, but the build produced {wrong}. "
            "The tagged commit is not the one that was built, or it carries "
            "another tag that setuptools_scm chose instead"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("tag", help="the pushed tag, such as v1.2.3")
    parser.add_argument(
        "--dist",
        type=Path,
        help="also require this directory to hold the files built for the tag",
    )
    parser.add_argument(
        "--github-output",
        type=Path,
        metavar="FILE",
        help="also add prerelease=true or prerelease=false to this file",
    )
    args = parser.parse_args()
    try:
        if args.dist is None:
            version = release_version(args.tag)
        else:
            check_files(args.tag, args.dist)
            version = release_version(args.tag)
    except ValueError as error:
        print(f"Refusing to release: {error}.", file=sys.stderr)
        return 1
    if args.github_output is not None:
        # True for an alpha, beta, release candidate or development version.
        answer = "true" if version.is_prerelease else "false"
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(f"prerelease={answer}\n")
    print(f"{args.tag} is version {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
