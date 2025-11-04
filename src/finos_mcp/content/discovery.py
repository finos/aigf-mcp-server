"""GitHub API Content Discovery for FINOS MCP Server.

Dynamically discovers mitigation and risk files from the FINOS AI Governance Framework
repository using the GitHub API, with intelligent caching and graceful fallback.
"""

import asyncio
import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

from ..config import get_settings
from ..health import get_health_monitor
from ..logging import get_logger
from .fetch import HTTPClient, get_http_client

# Removed security rate limiting - using simple HTTP requests

logger = get_logger("content_discovery")

# Static fallback lists (auto-generated - do not edit manually)
# To update: python scripts/update-static-fallback.py
# Last updated: 2025-10-27
STATIC_MITIGATION_FILES = [
    "mi-10_ai-model-version-pinning.md",
    "mi-11_human-feedback-loop-for-ai-systems.md",
    "mi-12_role-based-access-control-for-ai-data.md",
    "mi-13_providing-citations-and-source-traceability-for-ai-generated-information.md",
    "mi-14_encryption-of-ai-data-at-rest.md",
    "mi-15_using-large-language-models-for-automated-evaluation-llm-as-a-judge-.md",
    "mi-16_preserving-source-data-access-controls-in-ai-systems.md",
    "mi-17_ai-firewall-implementation-and-management.md",
    "mi-18_agent-authority-least-privilege-framework.md",
    "mi-19_tool-chain-validation-and-sanitization.md",
    "mi-1_ai-data-leakage-prevention-and-detection.md",
    "mi-20_mcp-server-security-governance.md",
    "mi-21_agent-decision-audit-and-explainability.md",
    "mi-22_multi-agent-isolation-and-segmentation.md",
    "mi-23_agentic-system-credential-protection-framework.md",
    "mi-2_data-filtering-from-external-knowledge-bases.md",
    "mi-3_user-app-model-firewalling-filtering.md",
    "mi-4_ai-system-observability.md",
    "mi-5_system-acceptance-testing.md",
    "mi-6_data-quality-classification-sensitivity.md",
    "mi-7_legal-and-contractual-frameworks-for-ai-systems.md",
    "mi-8_quality-of-service-qos-and-ddos-prevention-for-ai-systems.md",
    "mi-9_ai-system-alerting-and-denial-of-wallet-dow-spend-monitoring.md",
]

STATIC_RISK_FILES = [
    "ri-10_prompt-injection.md",
    "ri-14_inadequate-system-alignment.md",
    "ri-16_bias-and-discrimination.md",
    "ri-17_lack-of-explainability.md",
    "ri-18_model-overreach-expanded-use.md",
    "ri-19_data-quality-and-drift.md",
    "ri-1_information-leaked-to-hosted-model.md",
    "ri-20_reputational-risk.md",
    "ri-22_regulatory-compliance-and-oversight.md",
    "ri-23_intellectual-property-ip-and-copyright.md",
    "ri-24_agent-action-authorization-bypass.md",
    "ri-25_tool-chain-manipulation-and-injection.md",
    "ri-26_mcp-server-supply-chain-compromise.md",
    "ri-27_agent-state-persistence-poisoning.md",
    "ri-28_multi-agent-trust-boundary-violations.md",
    "ri-29_agent-mediated-credential-discovery-and-harvesting.md",
    "ri-2_information-leaked-to-vector-store.md",
    "ri-4_hallucination-and-inaccurate-outputs.md",
    "ri-5_foundation-model-versioning.md",
    "ri-6_non-deterministic-behaviour.md",
    "ri-7_availability-of-foundational-model.md",
    "ri-8_tampering-with-the-foundational-model.md",
    "ri-9_data-poisoning.md",
]

STATIC_FRAMEWORK_FILES = [
    "eu-ai-act.yml",
    "ffiec-itbooklets.yml",
    "iso-42001.yml",
    "nist-ai-600-1.yml",
    "nist-sp-800-53r5.yml",
    "owasp-llm.yml",
    "owasp-ml.yml",
]


@dataclass
class GitHubFileInfo:
    """Information about a file discovered from GitHub."""

    filename: str
    path: str
    sha: str
    size: int
    download_url: str
    last_modified: datetime | None = None


@dataclass
class DiscoveryResult:
    """Result of content discovery operation."""

    mitigation_files: list[GitHubFileInfo]
    risk_files: list[GitHubFileInfo]
    framework_files: list[GitHubFileInfo]
    source: str  # "github_api", "cache", or "static_fallback"
    cache_expires: datetime | None = None
    rate_limit_remaining: int | None = None


class GitHubDiscoveryService:
    """Service for discovering content from GitHub repository."""

    def __init__(self) -> None:
        self.settings = get_settings()

        # Try to create cache directory in current working directory
        # If that fails (e.g., read-only filesystem in Claude Desktop),
        # fallback to system temporary directory
        try:
            self.cache_dir = Path(".cache/discovery")
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            # Test write permissions by attempting to create a test file
            test_file = self.cache_dir / ".write_test"
            test_file.touch()
            test_file.unlink()
            logger.info("Using local cache directory: %s", self.cache_dir)
        except (OSError, PermissionError) as e:
            # Fallback to system temporary directory
            temp_base = Path(tempfile.gettempdir())
            self.cache_dir = temp_base / "finos_mcp_cache" / "discovery"
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.warning(
                "Could not create local cache directory (read-only filesystem), "
                "using system temp directory: %s (original error: %s)",
                self.cache_dir,
                str(e),
            )

        # GitHub API configuration
        self.repo_owner = "finos"
        self.repo_name = "ai-governance-framework"
        self.mitigation_path = "docs/_mitigations"
        self.risk_path = "docs/_risks"
        self.framework_path = "docs/_data"

        # Cache duration (1 hour for production, 5 minutes for development)
        self.cache_duration_seconds = 3600 if not self.settings.debug_mode else 300

    async def discover_content(self) -> DiscoveryResult:
        """Discover mitigation and risk files with caching and SHA-based validation."""
        try:
            # Try to load from cache first
            cached_result = await self._load_from_cache()
            if cached_result:
                # Cache is still fresh (time-based)
                logger.info(
                    "Content discovery served from cache",
                    extra={
                        "source": "cache",
                        "mitigation_count": len(cached_result.mitigation_files),
                        "risk_count": len(cached_result.risk_files),
                        "framework_count": len(cached_result.framework_files),
                        "expires": (
                            cached_result.cache_expires.isoformat()
                            if cached_result.cache_expires
                            else None
                        ),
                    },
                )
                return cached_result

            # Cache expired or missing - check if content actually changed (SHA validation)
            if self.settings.enable_sha_validation:
                # Try to load expired cache for SHA comparison
                expired_cache = await self._load_expired_cache()
                if expired_cache:
                    if await self._content_unchanged(expired_cache):
                        # Content hasn't changed - extend cache TTL
                        logger.info(
                            "Cache expired but content unchanged, extending TTL",
                            extra={
                                "mitigation_count": len(expired_cache.mitigation_files),
                                "risk_count": len(expired_cache.risk_files),
                                "framework_count": len(expired_cache.framework_files),
                            },
                        )
                        expired_cache.cache_expires = datetime.now(
                            timezone.utc
                        ).replace(microsecond=0) + timedelta(
                            seconds=self.cache_duration_seconds
                        )
                        await self._save_to_cache(expired_cache)
                        return expired_cache

            # Fetch from GitHub API
            github_result = await self._fetch_from_github()
            if github_result:
                # Save to cache
                await self._save_to_cache(github_result)

                # Check if static fallback needs update
                if self.settings.check_static_fallback:
                    self._check_static_fallback_sync(github_result)

                logger.info(
                    "Content discovery via GitHub API successful",
                    extra={
                        "source": "github_api",
                        "mitigation_count": len(github_result.mitigation_files),
                        "risk_count": len(github_result.risk_files),
                        "framework_count": len(github_result.framework_files),
                        "rate_limit_remaining": github_result.rate_limit_remaining,
                    },
                )
                return github_result

        except (
            httpx.HTTPError,
            httpx.TimeoutException,
            asyncio.TimeoutError,
            OSError,
            ValueError,
            KeyError,
        ) as e:
            logger.warning(
                "GitHub API discovery failed, using fallback",
                extra={"error": str(e), "error_type": type(e).__name__},
            )

        # Fallback to static lists
        return self._create_static_fallback()

    async def _fetch_from_github(self) -> DiscoveryResult | None:
        """Fetch file listings from GitHub API using shared HTTP client."""

        client = await get_http_client()
        try:
            # Fetch all three directories concurrently with rate limiting
            mitigation_task = self._fetch_directory(client, self.mitigation_path, ".md")
            risk_task = self._fetch_directory(client, self.risk_path, ".md")
            framework_task = self._fetch_directory(client, self.framework_path, ".yml")

            mitigation_files, risk_files, framework_files = await asyncio.gather(
                mitigation_task, risk_task, framework_task, return_exceptions=True
            )

            # Handle potential exceptions from concurrent requests
            if isinstance(mitigation_files, Exception):
                logger.error("Failed to fetch mitigation files: %s", mitigation_files)
                return None

            if isinstance(risk_files, Exception):
                logger.error("Failed to fetch risk files: %s", risk_files)
                return None

            if isinstance(framework_files, Exception):
                logger.error("Failed to fetch framework files: %s", framework_files)
                return None

            # At this point, we know all are list[GitHubFileInfo]
            assert isinstance(mitigation_files, list)
            assert isinstance(risk_files, list)
            assert isinstance(framework_files, list)

            # Rate limiting removed for simplicity
            rate_limit_remaining = None

            logger.info(
                "GitHub API discovery successful",
                extra={
                    "mitigation_count": len(mitigation_files),
                    "risk_count": len(risk_files),
                    "framework_count": len(framework_files),
                    "rate_limit_remaining": rate_limit_remaining,
                },
            )

            return DiscoveryResult(
                mitigation_files=mitigation_files,
                risk_files=risk_files,
                framework_files=framework_files,
                source="github_api",
                cache_expires=datetime.now(timezone.utc).replace(microsecond=0)
                + timedelta(seconds=self.cache_duration_seconds),
                rate_limit_remaining=rate_limit_remaining,
            )

        except (
            httpx.HTTPError,
            httpx.TimeoutException,
            asyncio.TimeoutError,
            ValueError,
            TypeError,
            KeyError,
        ) as e:
            # The rate limiter handles retries, so if we get here, all attempts failed
            error_type = type(e).__name__
            if isinstance(e, httpx.TimeoutException):
                logger.warning("GitHub API timeout after retries")
            elif isinstance(e, httpx.HTTPStatusError):
                logger.warning(
                    "GitHub API HTTP error after retries",
                    extra={
                        "status_code": (
                            e.response.status_code if e.response else "unknown"  # pylint: disable=no-member
                        ),
                        "error_type": error_type,
                    },
                )
            else:
                logger.warning(
                    "GitHub API request failed after retries",
                    extra={"error": str(e), "error_type": error_type},
                )
            return None

    async def _fetch_directory(
        self,
        client: HTTPClient,
        directory_path: str,
        file_extension: str = ".md",
    ) -> list[GitHubFileInfo]:
        """Fetch files from a specific directory in the repository with rate limiting."""
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/contents/{directory_path}"

        headers = {}
        # Add GitHub token if available
        github_token = (
            self.settings.github_token
            if hasattr(self.settings, "github_token")
            else None
        )
        if github_token:
            headers["Authorization"] = f"token {github_token}"
            headers["Accept"] = "application/vnd.github.v3+json"

        # Make simple HTTP request
        response = await client.get(url, headers=headers)

        # Store rate limit info for backwards compatibility (dynamic attribute)
        client._last_rate_limit = int(response.headers.get("X-RateLimit-Remaining", 0))  # type: ignore[attr-defined]

        files = []
        for item in response.json():
            if item["type"] == "file" and item["name"].endswith(file_extension):
                files.append(
                    GitHubFileInfo(
                        filename=item["name"],
                        path=item["path"],
                        sha=item["sha"],
                        size=item["size"],
                        download_url=item["download_url"],
                    )
                )

        # Sort by filename for consistency
        files.sort(key=lambda f: f.filename)
        return files

    async def _load_from_cache(self) -> DiscoveryResult | None:
        """Load cached discovery result if still valid."""
        cache_file = self.cache_dir / "github_discovery.json"

        try:
            if not cache_file.exists():
                return None

            with open(cache_file, encoding="utf-8") as f:
                data = json.load(f)

            # Check if cache is still valid
            cache_expires = datetime.fromisoformat(data["cache_expires"])
            if datetime.now(timezone.utc) > cache_expires:
                return None

            # Reconstruct GitHubFileInfo objects
            mitigation_files = [
                GitHubFileInfo(**file_data) for file_data in data["mitigation_files"]
            ]
            risk_files = [
                GitHubFileInfo(**file_data) for file_data in data["risk_files"]
            ]
            framework_files = [
                GitHubFileInfo(**file_data)
                for file_data in data.get("framework_files", [])
            ]

            return DiscoveryResult(
                mitigation_files=mitigation_files,
                risk_files=risk_files,
                framework_files=framework_files,
                source="cache",
                cache_expires=cache_expires,
                rate_limit_remaining=data.get("rate_limit_remaining"),
            )

        except (
            json.JSONDecodeError,
            KeyError,
            ValueError,
            OSError,
            PermissionError,
        ) as e:
            logger.warning(
                "Invalid or inaccessible cache file, will refresh",
                extra={"error": str(e)},
            )
            # Try to remove invalid cache file, but don't fail if we can't
            try:
                cache_file.unlink(missing_ok=True)
            except (OSError, PermissionError):
                pass  # Ignore errors during cleanup
            return None

    async def _save_to_cache(self, result: DiscoveryResult) -> None:
        """Save discovery result to cache.

        Gracefully handles write failures - service continues to work
        without caching if filesystem is read-only.
        """
        cache_file = self.cache_dir / "github_discovery.json"

        try:
            # Convert to serializable format
            data = {
                "mitigation_files": [
                    {
                        "filename": f.filename,
                        "path": f.path,
                        "sha": f.sha,
                        "size": f.size,
                        "download_url": f.download_url,
                        "last_modified": (
                            f.last_modified.isoformat() if f.last_modified else None
                        ),
                    }
                    for f in result.mitigation_files
                ],
                "risk_files": [
                    {
                        "filename": f.filename,
                        "path": f.path,
                        "sha": f.sha,
                        "size": f.size,
                        "download_url": f.download_url,
                        "last_modified": (
                            f.last_modified.isoformat() if f.last_modified else None
                        ),
                    }
                    for f in result.risk_files
                ],
                "framework_files": [
                    {
                        "filename": f.filename,
                        "path": f.path,
                        "sha": f.sha,
                        "size": f.size,
                        "download_url": f.download_url,
                        "last_modified": (
                            f.last_modified.isoformat() if f.last_modified else None
                        ),
                    }
                    for f in result.framework_files
                ],
                "source": "github_api",
                "cache_expires": (
                    result.cache_expires.isoformat() if result.cache_expires else None
                ),
                "rate_limit_remaining": result.rate_limit_remaining,
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }

            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            logger.debug("Discovery cache saved successfully to %s", cache_file)

        except (
            OSError,
            PermissionError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as e:
            logger.warning(
                "Failed to save discovery cache (service continues without caching): %s",
                str(e),
                extra={"error_type": type(e).__name__, "cache_file": str(cache_file)},
            )

    async def _load_expired_cache(self) -> DiscoveryResult | None:
        """Load cache even if expired, for SHA comparison purposes."""
        cache_file = self.cache_dir / "github_discovery.json"

        try:
            if not cache_file.exists():
                return None

            with open(cache_file, encoding="utf-8") as f:
                data = json.load(f)

            # Load cache regardless of expiration time
            cache_expires = datetime.fromisoformat(data["cache_expires"])

            # Reconstruct GitHubFileInfo objects
            mitigation_files = [
                GitHubFileInfo(**file_data) for file_data in data["mitigation_files"]
            ]
            risk_files = [
                GitHubFileInfo(**file_data) for file_data in data["risk_files"]
            ]
            framework_files = [
                GitHubFileInfo(**file_data)
                for file_data in data.get("framework_files", [])
            ]

            return DiscoveryResult(
                mitigation_files=mitigation_files,
                risk_files=risk_files,
                framework_files=framework_files,
                source="cache",
                cache_expires=cache_expires,
                rate_limit_remaining=data.get("rate_limit_remaining"),
            )

        except (
            json.JSONDecodeError,
            KeyError,
            ValueError,
            OSError,
            PermissionError,
        ) as e:
            logger.debug(
                "Could not load expired cache for SHA comparison: %s",
                str(e),
            )
            return None

    async def _content_unchanged(self, cached_result: DiscoveryResult) -> bool:
        """Check if GitHub content SHAs match cached SHAs.

        This makes minimal API calls - just directory listings (metadata),
        not full file downloads.

        Args:
            cached_result: Previously cached discovery result with SHAs

        Returns:
            True if all SHAs match (content unchanged), False otherwise
        """
        try:
            logger.debug("Checking if content changed via SHA comparison")

            # Fetch just the directory listings (cheap API call - metadata only)
            client = await get_http_client()

            current_mitigations = await self._fetch_directory(
                client, self.mitigation_path, ".md"
            )
            current_risks = await self._fetch_directory(client, self.risk_path, ".md")
            current_frameworks = await self._fetch_directory(
                client, self.framework_path, ".yml"
            )

            # Compare SHAs for each category
            if not self._shas_match(
                cached_result.mitigation_files, current_mitigations
            ):
                logger.info("Mitigation files changed, invalidating cache")
                return False

            if not self._shas_match(cached_result.risk_files, current_risks):
                logger.info("Risk files changed, invalidating cache")
                return False

            if not self._shas_match(cached_result.framework_files, current_frameworks):
                logger.info("Framework files changed, invalidating cache")
                return False

            logger.info("All SHAs match - content unchanged since last check")
            return True

        except (
            httpx.HTTPError,
            httpx.TimeoutException,
            asyncio.TimeoutError,
            ValueError,
            TypeError,
            KeyError,
        ) as e:
            logger.warning(
                "SHA comparison failed, assuming content changed: %s",
                str(e),
                extra={"error_type": type(e).__name__},
            )
            return False  # Fail safe - if can't verify, assume changed

    def _shas_match(
        self,
        cached_files: list[GitHubFileInfo],
        current_files: list[GitHubFileInfo],
    ) -> bool:
        """Compare two file lists by SHA hashes.

        Args:
            cached_files: Previously cached file list
            current_files: Current file list from GitHub

        Returns:
            True if all files and their SHAs match, False otherwise
        """
        # Build SHA maps for O(1) lookup
        cached_shas = {f.filename: f.sha for f in cached_files}
        current_shas = {f.filename: f.sha for f in current_files}

        # Check for added/removed files
        if set(cached_shas.keys()) != set(current_shas.keys()):
            added = set(current_shas.keys()) - set(cached_shas.keys())
            removed = set(cached_shas.keys()) - set(current_shas.keys())
            if added:
                logger.info("New files detected: %s", added)
            if removed:
                logger.info("Removed files detected: %s", removed)
            return False

        # Check for modified files (SHA changed)
        for filename, cached_sha in cached_shas.items():
            if current_shas[filename] != cached_sha:
                logger.info(
                    "File modified: %s (SHA changed from %s to %s)",
                    filename,
                    cached_sha[:8],
                    current_shas[filename][:8],
                )
                return False

        return True

    def _check_static_fallback_sync(self, current_result: DiscoveryResult) -> None:
        """Check if static fallback lists match current GitHub state.

        Logs warnings if mismatches are detected, helping developers know
        when to run the update script.

        Args:
            current_result: Current discovery result from GitHub API
        """
        current_mitigations = {f.filename for f in current_result.mitigation_files}
        current_risks = {f.filename for f in current_result.risk_files}
        current_frameworks = {f.filename for f in current_result.framework_files}

        static_mitigations = set(STATIC_MITIGATION_FILES)
        static_risks = set(STATIC_RISK_FILES)
        static_frameworks = set(STATIC_FRAMEWORK_FILES)

        mismatch_detected = False

        # Check mitigations
        if current_mitigations != static_mitigations:
            added = current_mitigations - static_mitigations
            removed = static_mitigations - current_mitigations
            logger.warning(
                "Static mitigation fallback list is outdated",
                extra={
                    "added_count": len(added),
                    "removed_count": len(removed),
                    "added_files": list(added) if added else None,
                    "removed_files": list(removed) if removed else None,
                },
            )
            mismatch_detected = True

        # Check risks
        if current_risks != static_risks:
            added = current_risks - static_risks
            removed = static_risks - current_risks
            logger.warning(
                "Static risk fallback list is outdated",
                extra={
                    "added_count": len(added),
                    "removed_count": len(removed),
                    "added_files": list(added) if added else None,
                    "removed_files": list(removed) if removed else None,
                },
            )
            mismatch_detected = True

        # Check frameworks
        if current_frameworks != static_frameworks:
            added = current_frameworks - static_frameworks
            removed = static_frameworks - current_frameworks
            logger.warning(
                "Static framework fallback list is outdated",
                extra={
                    "added_count": len(added),
                    "removed_count": len(removed),
                    "added_files": list(added) if added else None,
                    "removed_files": list(removed) if removed else None,
                },
            )
            mismatch_detected = True

        if mismatch_detected:
            logger.warning(
                "Static fallback lists need update - run: python scripts/update-static-fallback.py"
            )
        else:
            logger.debug("Static fallback lists are synchronized with GitHub")

    def _create_static_fallback(self) -> DiscoveryResult:
        """Create discovery result from static file lists."""
        mitigation_files = [
            GitHubFileInfo(
                filename=filename,
                path=f"{self.mitigation_path}/{filename}",
                sha="static",
                size=0,
                download_url=f"https://raw.githubusercontent.com/{self.repo_owner}/{self.repo_name}/main/{self.mitigation_path}/{filename}",
            )
            for filename in STATIC_MITIGATION_FILES
        ]

        risk_files = [
            GitHubFileInfo(
                filename=filename,
                path=f"{self.risk_path}/{filename}",
                sha="static",
                size=0,
                download_url=f"https://raw.githubusercontent.com/{self.repo_owner}/{self.repo_name}/main/{self.risk_path}/{filename}",
            )
            for filename in STATIC_RISK_FILES
        ]

        framework_files = [
            GitHubFileInfo(
                filename=filename,
                path=f"{self.framework_path}/{filename}",
                sha="static",
                size=0,
                download_url=f"https://raw.githubusercontent.com/{self.repo_owner}/{self.repo_name}/main/{self.framework_path}/{filename}",
            )
            for filename in STATIC_FRAMEWORK_FILES
        ]

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


# Global discovery service manager instance
_discovery_service_manager = DiscoveryServiceManager()


async def get_discovery_service() -> GitHubDiscoveryService:
    """Get or create the global discovery service instance."""
    return await _discovery_service_manager.get_discovery_service()


async def discover_content() -> DiscoveryResult:
    """Convenient function to discover content using the global service."""
    service = await get_discovery_service()
    start_time = datetime.now()

    try:
        result = await service.discover_content()

        # Record successful discovery for health monitoring
        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
        health_monitor = get_health_monitor()
        health_monitor.record_request(
            "discovery_service", success=True, response_time_ms=elapsed_ms
        )

        return result

    except (
        httpx.HTTPError,
        httpx.TimeoutException,
        asyncio.TimeoutError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
    ):
        # Record failed discovery for health monitoring
        health_monitor = get_health_monitor()
        health_monitor.record_request("discovery_service", success=False)
        raise
