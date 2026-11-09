# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The GitHub REST API, asked one way: list a content directory.

One place for the Authorization header, for reading a refusal, and for the
backoff that follows one. Discovery lists the three content directories.
Until #312 the document route also got a file here when
raw.githubusercontent.com could not serve it; each caller used to carry its own
copy of the header and its own throttle rule, and the rules differed: one
needed "rate limit" in the message, the other the quota header at zero, so one
403 was a throttle to one caller and an error to the other. Only discovery
backed off, so the document route kept asking an API that had just throttled
the listing (#310). Document bodies now come from the content host only, and
the throttle rule here still reads that host's 429 for the document route.

The backoff is one per process. A throttled answer starts it for as long as
``Retry-After`` or ``X-RateLimit-Reset`` says, or :data:`THROTTLE_BACKOFF_SECONDS`
when neither is sent. An answer that says nothing about the host, a 4xx that
is not a throttle, starts none for a file; a listing of a configured directory
that fails for any reason starts the failure backoff, since every tool call
lists and a misconfigured path would otherwise spend the hourly budget three
requests at a time. While it runs, neither call sends a request: it raises the
error class of the answer that started it, with ``retry_after`` set.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, NamedTuple

import httpx
from pydantic import SecretStr

from ..config import get_settings
from ..exceptions import GitHubDiscoveryError, GitHubRateLimitError
from ..logging import get_logger
from ..security.repo_target import RepoTarget
from .fetch import HTTPClient

logger = get_logger("github_api")

#: After a failure that is not a throttle: a transport error, a 5xx, a
#: listing refused for any reason. Shorter than the list file's hour, so a
#: transient blip does not cost an hour of stale answers; in debug mode
#: :data:`DEBUG_FAILURE_BACKOFF_SECONDS`.
FAILURE_BACKOFF_SECONDS = 300
DEBUG_FAILURE_BACKOFF_SECONDS = 30

#: After a throttle whose answer names no reset time.
THROTTLE_BACKOFF_SECONDS = 60

#: The longest a header can make the backoff; GitHub's primary limit resets
#: within the hour.
BACKOFF_CEILING_SECONDS = 3600


@dataclass
class GitHubFileInfo:
    """A file in a content directory, by name.

    The listing used to carry each entry's path, blob SHA, size and download
    URL, which no consumer read; an entry GitHub sent without one of them
    failed the whole listing (#327). The name is what the tools list and
    what a document fetch is built from.
    """

    filename: str


#: A document name: letters, digits, dot, underscore and hyphen, nothing a
#: path or a sentence could carry. A name reaches the client as the document's
#: id and is what a fetch URL is built from.
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class ContentDirectory(NamedTuple):
    """One of the three content directories and the names it holds.

    The live listing and the list file apply the same rule (#294): the listing
    used to be filtered by extension only, the file not at all, so a planted
    name on disk was served as an id on every call.
    """

    subdir: str
    """Relative to the path prefix carried by base_url, e.g. "_risks"."""
    prefix: str
    """What every file name in it starts with; empty for the frameworks."""
    extension: str

    def holds(self, name: str) -> bool:
        return (
            name.startswith(self.prefix)
            and name.endswith(self.extension)
            and len(name) > len(self.prefix) + len(self.extension)
            and _NAME.fullmatch(name) is not None
        )


# Framework reference YAMLs live under _data/references; _data itself holds
# taxonomy files (ai_use_cases, data_classification, ai_deployment_model),
# which are not governance frameworks.
MITIGATIONS = ContentDirectory("_mitigations", "mi-", ".md")
RISKS = ContentDirectory("_risks", "ri-", ".md")
FRAMEWORKS = ContentDirectory("_data/references", "", ".yml")

#: The directory each document type is read from: the one statement of it
#: for the document route and the document tools (#380).
DIRECTORIES = {"mitigation": MITIGATIONS, "risk": RISKS, "framework": FRAMEWORKS}


_backoff_until: datetime | None = None
_backoff_follows_a_throttle = False


def seconds_until_asked_again() -> int:
    """How long the API is left alone from now; 0 when it may be asked."""
    global _backoff_until
    if _backoff_until is None:
        return 0
    remaining = (_backoff_until - datetime.now(UTC)).total_seconds()
    if remaining <= 0:
        _backoff_until = None
        return 0
    return max(1, int(remaining + 0.999))


def backing_off() -> bool:
    """True while a recent refusal is still being backed off."""
    return seconds_until_asked_again() > 0


def reset_backoff() -> None:
    """Forget the backoff. For tests; the server never calls it."""
    global _backoff_until
    _backoff_until = None


def _back_off(seconds: int, *, throttled: bool) -> None:
    global _backoff_until, _backoff_follows_a_throttle
    until = datetime.now(UTC) + timedelta(seconds=min(seconds, BACKOFF_CEILING_SECONDS))
    if _backoff_until is not None and _backoff_until >= until:
        return
    _backoff_until = until
    _backoff_follows_a_throttle = throttled


def _failure_backoff_seconds() -> int:
    if get_settings().debug_mode:
        return DEBUG_FAILURE_BACKOFF_SECONDS
    return FAILURE_BACKOFF_SECONDS


def retry_after_if_rate_limited(
    status_code: int | None, headers: Any, message: str = ""
) -> int | None:
    """Seconds to wait if this answer is GitHub throttling us, else None.

    The three ways GitHub says so: raw.githubusercontent.com answers 429 with
    no quota headers; the Contents API answers 403 with ``X-RateLimit-Remaining``
    at zero and a message naming the rate limit; a secondary limit answers 403
    or 429 with ``Retry-After`` and quota to spare. A 403 that says none of
    these is a permissions failure, and reporting it as "retry in 60s" would
    send the caller into a pointless loop. Every other status is not a
    throttle, so a 404 is never dressed up as one.
    """
    if status_code not in (403, 429):
        return None

    headers = headers or {}
    try:
        remaining = headers.get("X-RateLimit-Remaining")
        retry_after = headers.get("Retry-After")
        reset = headers.get("X-RateLimit-Reset")
    except AttributeError:
        return None

    if status_code == 403 and not (
        str(remaining) == "0"
        or retry_after is not None
        or "rate limit" in message.lower()
    ):
        return None

    if retry_after is not None and str(retry_after).strip().isdigit():
        return int(str(retry_after).strip())

    if reset is not None and str(reset).strip().isdigit():
        delta = int(str(reset).strip()) - int(time.time())
        if 0 < delta <= BACKOFF_CEILING_SECONDS:
            return delta

    return THROTTLE_BACKOFF_SECONDS


def _headers(token: SecretStr | None) -> dict[str, str]:
    if token is None:
        return {}
    return {
        "Authorization": f"token {token.get_secret_value()}",
        "Accept": "application/vnd.github.v3+json",
    }


def _message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(body, dict):
        return str(body.get("message", ""))
    return ""


async def _answer(
    client: HTTPClient, url: str, token: SecretStr | None, doing: str
) -> httpx.Response:
    """The 200 answer to ``url``, or the refusal as an exception.

    Raises without a request while backing off. Starts the backoff on a
    transport failure (the client raised), a throttle, or a 5xx.
    """
    remaining = seconds_until_asked_again()
    if remaining:
        error_class = (
            GitHubRateLimitError
            if _backoff_follows_a_throttle
            else GitHubDiscoveryError
        )
        raise error_class(
            f"GitHub API not asked while {doing}: backing off for {remaining} s "
            f"after a recent {'throttle' if _backoff_follows_a_throttle else 'failure'}",
            retry_after=remaining,
        )

    try:
        response = await client.get(url, headers=_headers(token))
    except Exception:
        _back_off(_failure_backoff_seconds(), throttled=False)
        raise

    if response.status_code == 200:
        return response

    message = _message(response)
    retry_after = retry_after_if_rate_limited(
        response.status_code, response.headers, message
    )
    if retry_after is not None:
        _back_off(retry_after, throttled=True)
        raise GitHubRateLimitError(
            f"GitHub API rate limit exhausted while {doing}: {message}",
            retry_after=retry_after,
        )
    if response.status_code >= 500:
        _back_off(_failure_backoff_seconds(), throttled=False)
    raise GitHubDiscoveryError(
        f"GitHub API returned {response.status_code} while {doing}: {message}",
        status_code=response.status_code,
    )


def _file_names(response: httpx.Response, doing: str) -> list[str]:
    """The names of the file entries in a directory listing.

    Raises:
        GitHubDiscoveryError: the answer is not a directory listing -- not
            JSON, not an array, or an entry that is not an object or is a
            file with no name. These once escaped as ValueError,
            AttributeError or KeyError, which started no backoff (#367).
    """
    try:
        payload = response.json()
        if isinstance(payload, list):
            return [str(item["name"]) for item in payload if item.get("type") == "file"]
        # A directory listing is always a JSON array. Anything else means the
        # path is wrong or the response is an error object not classified
        # by _answer.
        shape = type(payload).__name__
    except (ValueError, AttributeError, KeyError) as error:
        shape = f"{type(error).__name__} ({error})"
    raise GitHubDiscoveryError(
        f"GitHub API returned {shape}, not a directory listing, while {doing}"
    )


async def list_directory(
    client: HTTPClient,
    repo_target: RepoTarget,
    directory: ContentDirectory,
    token: SecretStr | None = None,
) -> list[GitHubFileInfo]:
    """The document names in a content directory, sorted.

    Args:
        client: The shared HTTP client.
        repo_target: Where the content lives; builds the Contents API URL.
        directory: Which directory, relative to the path prefix carried by
            base_url: repo_target applies the prefix. Only the names it
            ``holds`` are returned.
        token: ``FINOS_MCP_GITHUB_TOKEN``, when set.

    Raises:
        GitHubRateLimitError: GitHub throttled the request, or is being
            backed off after throttling one.
        GitHubDiscoveryError: any other answer that is not a directory
            listing, or one that lists no document name: a content directory
            holds documents, so an empty one means the documents moved or
            were renamed, not that there are none (#317). A refused listing
            of any kind starts the failure backoff.
    """
    doing = f"listing {directory.subdir}"
    try:
        response = await _answer(
            client, repo_target.api_contents_url(directory.subdir), token, doing
        )
        names = _file_names(response, doing)
        ignored = [name for name in names if not directory.holds(name)]
        if ignored:
            logger.debug(
                "Ignoring %d file(s) in %s that are not document names",
                len(ignored),
                directory.subdir,
            )
        files = [GitHubFileInfo(filename=n) for n in names if directory.holds(n)]
        if not files:
            raise GitHubDiscoveryError(
                f"GitHub API listed no document name while {doing}: "
                f"{len(names)} files, {len(ignored)} ignored"
            )
    except GitHubDiscoveryError:
        if not backing_off():
            _back_off(_failure_backoff_seconds(), throttled=False)
        raise

    files.sort(key=lambda f: f.filename)
    return files
