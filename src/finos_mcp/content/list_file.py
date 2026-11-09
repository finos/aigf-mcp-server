# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The discovery list file: the last listing GitHub gave, kept on disk.

One reader, one writer, one format (#311). ``discovery.py`` used to hold two
readers of about forty identical lines that differed in one expiry check, one
log level and one ``unlink``; a writer that repeated a six-field dictionary
three times and stored four fields nothing read back; and a fallback path that
parsed the file three times per call.

The file belongs to the ``base_url`` it was written for (#249): read under
another, it would name the previous repository's documents while bodies are
fetched from the new one. A target the GitHub API cannot address never lists,
so it never has a listing of its own, and a file found there lists GitHub.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ..logging import get_logger
from ..models import ListingSource
from ..security.repo_target import RepoTarget
from .github_api import FRAMEWORKS, MITIGATIONS, RISKS, ContentDirectory, GitHubFileInfo

logger = get_logger("list_file")

FILE_NAME = "github_discovery.json"

#: A file larger than this is not read (#294). A listing of the whole corpus
#: is a few kilobytes; one written before #327, with five fields an entry,
#: about twenty-five. The file is parsed on every call and had no bound.
SIZE_LIMIT_BYTES = 256 * 1024


def default_directory() -> Path:
    """Where the file goes when FINOS_MCP_DISCOVERY_CACHE_DIR is not set.

    The user's cache directory (#293). It used to be ``.cache/discovery``
    under the working directory, which for a stdio server is the client's,
    so a cloned repository that shipped the file supplied the listing.
    """
    cache_home = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(cache_home) / "finos-mcp" / "discovery"


@dataclass
class DiscoveryResult:
    """The document listing, and where it came from.

    ``source`` is ``"github_api"`` for a listing just made, ``"cache"`` for the
    list file while fresh, ``"expired_cache"`` for the list file past its time
    when GitHub cannot be asked, and ``"static_fallback"`` for the lists built
    into the server. The functional gate takes the first two as proof that
    discovery ran (#264).
    """

    mitigation_files: list[GitHubFileInfo]
    risk_files: list[GitHubFileInfo]
    framework_files: list[GitHubFileInfo]
    source: ListingSource
    cache_expires: datetime | None = None

    def files_in(self, directory: ContentDirectory) -> list[GitHubFileInfo]:
        """The files listed for one of the three directories."""
        return {
            MITIGATIONS: self.mitigation_files,
            RISKS: self.risk_files,
            FRAMEWORKS: self.framework_files,
        }[directory]


def resolve_directory(configured: str | None) -> Path | None:
    """The directory the list file lives in, created for this user, or None.

    ``configured`` (FINOS_MCP_DISCOVERY_CACHE_DIR) first; :func:`default_directory`
    when it is not set. None, with one warning naming the directory, when it
    cannot be created or written, is not this user's, or can be written by
    the group or by everyone (#293): the listing is then kept in memory.
    There used to be a fallback to a fixed name under the system temporary
    directory, one any local user could create first, and a directory owned
    by someone else was accepted.
    """
    directory = Path(configured) if configured else default_directory()
    try:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        _must_be_private(directory, directory.stat(), stat.S_ISDIR)
        # A probe with a name of its own. The shared ".write_test" was touched
        # and unlinked by every server starting in the directory, and one
        # unlinking another's probe sent the loser to the temporary directory
        # (#309). The probe stays because a directory that exists but cannot
        # be written would otherwise cost a listing of GitHub on every call.
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".write_test_"):
            pass
    except (OSError, ValueError) as e:
        logger.warning(
            "Not using the discovery cache directory %s, keeping the listing in "
            "memory instead: %s",
            directory,
            e,
        )
        return None
    logger.info("Using discovery cache directory: %s", directory.resolve())
    return directory


def _must_be_private(
    path: Path, status: os.stat_result, is_kind: Callable[[int], bool]
) -> None:
    """Raise ValueError unless ``path`` is this user's own, and others cannot write it.

    ``is_kind`` says what it must be (``stat.S_ISDIR`` or ``stat.S_ISREG``);
    the caller chooses ``stat`` or ``lstat``, so a symlink in place of the file
    is refused while a symlinked directory is judged by its target. The owner
    check needs POSIX ids; where there are none it is skipped.
    """
    if not is_kind(status.st_mode):
        raise ValueError(f"{path} is not what a list file needs there")
    getuid = getattr(os, "getuid", None)
    if getuid is not None and status.st_uid != getuid():
        raise ValueError(f"{path} is owned by uid {status.st_uid}, not this user")
    if status.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ValueError(f"{path} can be written by the group or by everyone")


class ListFile:
    """``github_discovery.json`` in ``directory``, for one repository."""

    def __init__(
        self, directory: Path | None, repo_target: RepoTarget, lifetime_seconds: int
    ) -> None:
        #: None when no directory is usable: the listing is kept in memory.
        self.path = directory / FILE_NAME if directory is not None else None
        self.repo_target = repo_target
        self.lifetime_seconds = lifetime_seconds
        #: The last listing written, served when there is no file (#293).
        self._last: DiscoveryResult | None = None

    def read(self) -> DiscoveryResult | None:
        """The listing on disk for this target, or None.

        ``source`` is ``"cache"`` while the file is within its lifetime and
        ``"expired_cache"`` after. None when there is no file, it was written
        for another ``base_url``, the target has no listing of its own, or
        the file cannot be read. An unreadable file is left where it is: stdio
        clients started in one directory share it, so it may be one another
        process is writing, and the next listing replaces it whole (#309).

        The file is read as the server writes it and no further (#294): one
        above :data:`SIZE_LIMIT_BYTES` is not parsed, a name a directory would
        not have listed makes the file unreadable, and an expiry further away
        than the lifetime reads as expired, since no write of this server
        stamped it. A symlink, or a file owned by someone else or writable by
        others, is not one this server wrote either (#293). Without a usable
        directory the last listing written is served from memory.
        """
        if not self.repo_target.github_api_available:
            return None
        if self.path is None:
            if self._last is None or self._last.cache_expires is None:
                return None
            return replace(self._last, source=self._source(self._last.cache_expires))
        try:
            try:
                status = self.path.lstat()
            except FileNotFoundError:
                return None
            _must_be_private(self.path, status, stat.S_ISREG)
            if status.st_size > SIZE_LIMIT_BYTES:
                raise ValueError(
                    f"{status.st_size} bytes, more than {SIZE_LIMIT_BYTES}"
                )
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            if not self._written_for_this_target(data):
                return None
            expires = datetime.fromisoformat(data["cache_expires"])
            return DiscoveryResult(
                mitigation_files=_entries(data["mitigation_files"], MITIGATIONS),
                risk_files=_entries(data["risk_files"], RISKS),
                framework_files=_entries(data.get("framework_files", []), FRAMEWORKS),
                source=self._source(expires),
                cache_expires=expires,
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, OSError) as e:
            logger.warning(
                "Invalid or inaccessible list file, will list again",
                extra={"error": str(e), "list_file": str(self.path)},
            )
            return None

    def _source(self, expires: datetime) -> ListingSource:
        now = datetime.now(UTC)
        fresh = now <= expires <= now + timedelta(seconds=self.lifetime_seconds)
        return "cache" if fresh else "expired_cache"

    def write(self, listing: DiscoveryResult) -> None:
        """Stamp the listing's expiry and write it; a failed write is a warning.

        Written to a file of its own in the same directory, readable by this
        user only, and renamed into place, so a reader never meets a truncated
        file, a write that fails midway leaves the previous listing intact
        (#309), and a planted symlink is replaced rather than followed (#293).
        The service continues without a file when the filesystem is read-only,
        and keeps the listing in memory when it has no directory at all.
        """
        listing.cache_expires = datetime.now(UTC).replace(microsecond=0) + timedelta(
            seconds=self.lifetime_seconds
        )
        self._last = listing
        if self.path is None:
            return
        data = {
            # Which repository this lists; see _written_for_this_target.
            "base_url": self.repo_target.raw_base_url,
            "cache_expires": listing.cache_expires.isoformat(),
            "mitigation_files": [_entry(f) for f in listing.mitigation_files],
            "risk_files": [_entry(f) for f in listing.risk_files],
            "framework_files": [_entry(f) for f in listing.framework_files],
        }
        try:
            descriptor, temporary = tempfile.mkstemp(
                dir=self.path.parent, prefix=FILE_NAME + ".", suffix=".tmp"
            )
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                os.replace(temporary, self.path)
            except BaseException:
                Path(temporary).unlink(missing_ok=True)
                raise
            logger.debug("List file written to %s", self.path)
        except (OSError, TypeError, ValueError) as e:
            logger.warning(
                "Failed to write the list file (service continues without it): %s",
                str(e),
                extra={"error_type": type(e).__name__, "list_file": str(self.path)},
            )

    def _written_for_this_target(self, data: object) -> bool:
        """Whether a loaded list file lists the repository base_url now names.

        A file that records no base_url was written before the key existed.
        It is read, or every server would drop its listing on the first start
        after the upgrade (#261); the next write records the key. What that
        leaves open is a base_url changed in the same restart as the upgrade.
        """
        if not isinstance(data, dict):
            return False
        written_for = data.get("base_url")
        if written_for == self.repo_target.raw_base_url or written_for is None:
            return True
        logger.debug(
            "Ignoring the discovery list file: it was written for %s, not for "
            "the configured base_url",
            written_for,
        )
        return False


def _entry(info: GitHubFileInfo) -> dict[str, Any]:
    return {"filename": info.filename}


def _entries(
    items: list[dict[str, Any]], directory: ContentDirectory
) -> list[GitHubFileInfo]:
    # Files written before #327 carry path, sha, size, download_url and
    # last_modified beside the name; only the name is read.
    names = [str(item["filename"]) for item in items]
    for name in names:
        if not directory.holds(name):
            raise ValueError(f"{name!r} is not a name {directory.subdir} holds")
    return [GitHubFileInfo(filename=name) for name in names]
