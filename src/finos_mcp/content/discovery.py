# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Which documents the content repository holds.

A listing of the three content directories through the GitHub API
(``github_api``), kept on disk for an hour (``list_file``), with the lists
built into the package (``static_catalog``) as the last resort.
``discover_content`` gives the order; the tools read the result's file names
and nothing else.
"""

import asyncio
from collections.abc import Mapping
from typing import Optional

import httpx

from ..config import get_settings
from ..exceptions import (
    CircuitBreakerError,
    GitHubDiscoveryError,
    GitHubRateLimitError,
)
from ..logging import get_logger
from . import github_api
from .fetch import get_http_client
from .github_api import FRAMEWORKS, MITIGATIONS, RISKS, GitHubFileInfo
from .list_file import DiscoveryResult, ListFile, resolve_directory
from .static_catalog import (
    STATIC_FRAMEWORK_FILES,
    STATIC_MITIGATION_FILES,
    STATIC_RISK_FILES,
)

__all__ = [
    "DiscoveryResult",
    "DiscoveryServiceManager",
    "GitHubDiscoveryService",
    "GitHubFileInfo",
]

logger = get_logger("content_discovery")


class GitHubDiscoveryService:
    """Service for discovering content from GitHub repository."""

    def __init__(self) -> None:
        self.settings = get_settings()

        # GitHub API configuration, derived from base_url so discovery cannot
        # target a different repository than the content fetches do.
        self.repo_target = self.settings.repo_target

        # Cache duration (1 hour for production, 5 minutes for development)
        self.cache_duration_seconds = 3600 if not self.settings.debug_mode else 300
        self.list_file = ListFile(
            resolve_directory(self.settings.discovery_cache_dir),
            self.repo_target,
            self.cache_duration_seconds,
        )
        # The listing in flight, shared by every call that arrives while it
        # runs (#292); None between listings. See _list_github_once.
        self._listing: asyncio.Task[DiscoveryResult | None] | None = None

    def _note_discovery_failure(self, errors: Mapping[str, BaseException]) -> None:
        """Log one classified message per discovery failure.

        One place for both failure paths: the gather results, which never raise
        because of ``return_exceptions=True``, and the ``except`` clause around
        the request. Missing the first of those is what left the retry storm in
        place after the backoff was added.

        The backoff itself is github_api's: a refused listing starts it there,
        and the next call finds ``backing_off()`` true and lists nothing.
        Discovery used to keep its own, and the document route, which asks
        the same API, had none (#310).
        """
        backing_off_seconds = github_api.seconds_until_asked_again()
        rate_limited = [
            subdir
            for subdir, err in errors.items()
            if isinstance(err, GitHubRateLimitError)
        ]
        if rate_limited:
            # WARNING, not ERROR: being throttled is the routine outcome of
            # running unauthenticated (60 requests/hour per IP), not a defect.
            # The expired list file serves the request, or the static catalog
            # (callers see source="static_fallback") when there is none.
            logger.warning(
                "GitHub API rate limit exhausted; serving the last listing on "
                "disk, or the static catalog if there is none. "
                "Set FINOS_MCP_GITHUB_TOKEN to raise the limit to 5000/hour.",
                extra={
                    "directories": sorted(errors),
                    "backing_off_seconds": backing_off_seconds,
                },
            )
        else:
            first = next(iter(errors.values()))
            logger.error(
                "GitHub content discovery failed; serving the last listing on "
                "disk, or the static catalog if there is none.",
                extra={
                    "directories": sorted(errors),
                    "error": str(first),
                    "error_type": type(first).__name__,
                    "backing_off_seconds": backing_off_seconds,
                },
            )

    async def discover_content(self) -> DiscoveryResult:
        """The document listing: the list file while fresh, else one listing of GitHub.

        An expired list file used to be kept when a comparison of its SHAs
        with a fresh listing found nothing changed. The comparison was the
        same three requests as the listing it saved, and on a change the
        listing followed anyway, so it cost nothing when content was unchanged
        and three requests when it was (#308). The order is now: a fresh list
        file; one listing of the three directories, written and served; the
        expired list file when GitHub cannot be asked; the static catalog.

        The list file is read once per call (#311): it used to be parsed up
        to three times on the fallback path. Calls that arrive while a listing
        is in flight await that listing rather than start their own (#292).
        """
        on_disk = self.list_file.read()
        if on_disk is not None and on_disk.source == "cache":
            logger.info(
                "Content discovery served from cache",
                extra={
                    "source": "cache",
                    "mitigation_count": len(on_disk.mitigation_files),
                    "risk_count": len(on_disk.risk_files),
                    "framework_count": len(on_disk.framework_files),
                    "expires": (
                        on_disk.cache_expires.isoformat()
                        if on_disk.cache_expires
                        else None
                    ),
                },
            )
            return on_disk

        try:
            github_result = await self._list_github_once()
            if github_result:
                return github_result

        except (
            TimeoutError,
            httpx.HTTPError,
            CircuitBreakerError,
            OSError,
            ValueError,
            KeyError,
        ) as e:
            logger.warning(
                "GitHub API discovery failed, using fallback",
                extra={"error": str(e), "error_type": type(e).__name__},
            )

        # The last listing GitHub gave is newer than the static catalog, so an
        # expired list file for this target is served before it (#260). Its
        # expiry is not moved: the next call past the backoff asks again. A
        # target the API cannot address never has a listing of its own.
        # It is named "expired_cache", not "cache": nothing has confirmed it
        # within the hour, and the functional gate takes "cache" as proof that
        # discovery ran (#264).
        if on_disk is not None:
            logger.info(
                "Content discovery served from the expired list file",
                extra={
                    "source": "expired_cache",
                    "expired": (
                        on_disk.cache_expires.isoformat()
                        if on_disk.cache_expires
                        else None
                    ),
                },
            )
            return on_disk

        # Fallback to static lists
        return self._create_static_fallback()

    async def _list_github_once(self) -> DiscoveryResult | None:
        """One listing of GitHub, shared by every call made while it runs.

        Every call used to list for itself, so ten calls arriving at the list
        file's expiry (the default per-client concurrency) issued thirty
        requests, half the unauthenticated hourly budget, and the backoff that
        followed left the document route without budget too (#292). The first
        call starts the listing as a task; the others await the same task, and
        the file is written once. The task is shielded: a client that hangs up
        mid-call cancels its own tool task, not the listing the others await.
        """
        if self._listing is None:
            self._listing = asyncio.create_task(self._list_github_and_record())
            self._listing.add_done_callback(self._forget_listing)
        return await asyncio.shield(self._listing)

    def _forget_listing(self, _: asyncio.Task[DiscoveryResult | None]) -> None:
        self._listing = None

    async def _list_github_and_record(self) -> DiscoveryResult | None:
        github_result = await self._fetch_from_github()
        if github_result:
            self.list_file.write(github_result)
            logger.info(
                "Content discovery via GitHub API successful",
                extra={
                    "source": "github_api",
                    "mitigation_count": len(github_result.mitigation_files),
                    "risk_count": len(github_result.risk_files),
                    "framework_count": len(github_result.framework_files),
                },
            )
        return github_result

    async def _fetch_from_github(self) -> DiscoveryResult | None:
        """Fetch file listings from GitHub API using shared HTTP client."""
        if not self.repo_target.github_api_available:
            # base_url names a host api.github.com cannot address. Listing the
            # upstream repository here would describe content this server does
            # not serve, so fall back to the static lists instead.
            logger.info(
                "Skipping GitHub API discovery: the configured base_url host is "
                "not addressable through the GitHub API"
            )
            return None

        backing_off_seconds = github_api.seconds_until_asked_again()
        if backing_off_seconds:
            # A recent request was refused. Returning None here serves the
            # expired list file, or the static catalog, without issuing three
            # more requests that would be refused the same way.
            logger.debug(
                "Skipping GitHub API discovery: backing off for %s s after a "
                "recent refusal",
                backing_off_seconds,
            )
            return None

        client = await get_http_client()
        try:
            # The three directories, listed concurrently.
            token = self.settings.github_token
            mitigation_files, risk_files, framework_files = await asyncio.gather(
                github_api.list_directory(client, self.repo_target, MITIGATIONS, token),
                github_api.list_directory(client, self.repo_target, RISKS, token),
                github_api.list_directory(client, self.repo_target, FRAMEWORKS, token),
                return_exceptions=True,
            )

            # Handle exceptions from the concurrent requests.
            #
            # gather(return_exceptions=True) turns a failure into a *return value*,
            # so these paths never raise and never reached the `except` block
            # below -- which is why the backoff added there had no effect and one
            # sweep still logged 74 failures. Classify, back off, and return here.
            #
            # All three directories are fetched from the same host with the same
            # credentials, so they fail together; reporting each one separately
            # said "mitigation files" three times for a single cause.
            failures = {
                MITIGATIONS.subdir: mitigation_files,
                RISKS.subdir: risk_files,
                FRAMEWORKS.subdir: framework_files,
            }
            errors = {
                subdir: result
                for subdir, result in failures.items()
                if isinstance(result, Exception)
            }
            if errors:
                self._note_discovery_failure(errors)
                return None

            # Defensive type guards — assert statements are stripped by -O
            # and would silently pass invalid types; use explicit checks instead.
            if not isinstance(mitigation_files, list):
                raise TypeError(
                    f"Expected list for mitigation_files, got {type(mitigation_files)}"
                )
            if not isinstance(risk_files, list):
                raise TypeError(f"Expected list for risk_files, got {type(risk_files)}")
            if not isinstance(framework_files, list):
                raise TypeError(
                    f"Expected list for framework_files, got {type(framework_files)}"
                )

            logger.info(
                "GitHub API discovery successful",
                extra={
                    "mitigation_count": len(mitigation_files),
                    "risk_count": len(risk_files),
                    "framework_count": len(framework_files),
                },
            )

            return DiscoveryResult(
                mitigation_files=mitigation_files,
                risk_files=risk_files,
                framework_files=framework_files,
                source="github_api",
            )

        except (
            TimeoutError,
            httpx.HTTPError,
            CircuitBreakerError,
            GitHubDiscoveryError,
            ValueError,
            TypeError,
            KeyError,
        ) as e:
            # Same classification as the gather path above: one helper, so
            # the two cannot drift.
            self._note_discovery_failure({"discovery": e})
            return None

    def _create_static_fallback(self) -> DiscoveryResult:
        """The listing built into the package, ``static_catalog``."""
        mitigation_files = [GitHubFileInfo(filename=f) for f in STATIC_MITIGATION_FILES]
        risk_files = [GitHubFileInfo(filename=f) for f in STATIC_RISK_FILES]
        framework_files = [GitHubFileInfo(filename=f) for f in STATIC_FRAMEWORK_FILES]

        logger.info(
            "Using static fallback for content discovery",
            extra={
                "mitigation_count": len(mitigation_files),
                "risk_count": len(risk_files),
                "framework_count": len(framework_files),
            },
        )

        return DiscoveryResult(
            mitigation_files=mitigation_files,
            risk_files=risk_files,
            framework_files=framework_files,
            source="static_fallback",
        )


class DiscoveryServiceManager:
    """Singleton manager for the global discovery service instance."""

    _instance: Optional["DiscoveryServiceManager"] = None
    _discovery_service: GitHubDiscoveryService | None = None

    def __new__(cls) -> "DiscoveryServiceManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_discovery_service(self) -> GitHubDiscoveryService:
        """Get or create the global discovery service instance."""
        if self._discovery_service is None:
            self._discovery_service = GitHubDiscoveryService()
        return self._discovery_service
