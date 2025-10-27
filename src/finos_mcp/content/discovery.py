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

# Static fallback lists (used when GitHub API is unavailable)
STATIC_MITIGATION_FILES = [
    "mi-1_ai-data-leakage-prevention-and-detection.md",
    "mi-2_data-filtering-from-external-knowledge-bases.md",
    "mi-3_user-app-model-firewalling-filtering.md",
    "mi-4_ai-system-observability.md",
    "mi-5_system-acceptance-testing.md",
    "mi-6_data-quality-classification-sensitivity.md",
    "mi-7_legal-and-contractual-frameworks-for-ai-systems.md",
    "mi-8_quality-of-service-qos-and-ddos-prevention-for-ai-systems.md",
    "mi-9_ai-system-alerting-and-denial-of-wallet-dow-spend-monitoring.md",
    "mi-10_ai-model-version-pinning.md",
    "mi-11_ai-system-governance-and-compliance-attestation-and-validation.md",
    "mi-12_ai-system-interaction-logging.md",
    "mi-13_ai-system-vulnerability-assessment-and-penetration-testing.md",
    "mi-14_ai-training-and-test-data-purging.md",
    "mi-15_responsible-ai-data-governance.md",
    "mi-16_ai-system-evaluation-and-validation.md",
    "mi-17_responsible-ai-governance-data-integration-and-security.md",
]

STATIC_RISK_FILES = [
    "ri-1_adversarial-behavior-against-ai-systems.md",
    "ri-2_prompt-injection.md",
    "ri-3_training-data-poisoning.md",
    "ri-5_supply-chain-compromises.md",
    "ri-6_data-leakage.md",
    "ri-7_ai-system-availability-and-performance.md",
    "ri-8_ai-system-configuration-and-third-party-integrations.md",
    "ri-9_ai-system-governance-and-security.md",
    "ri-10_over-reliance-on-generated-content.md",
    "ri-11_data-extraction-and-inference.md",
    "ri-12_ai-system-backdoors.md",
    "ri-13_ai-system-unintended-bias.md",
    "ri-14_ai-system-misinformation-generation.md",
    "ri-15_ai-system-privacy-and-confidentiality.md",
    "ri-16_ai-system-governance-data-and-business-model-risks.md",
    "ri-19_ai-system-operational-data-security.md",
    "ri-23_ai-system-reliability-and-quality.md",
]

STATIC_FRAMEWORK_FILES = [
    "nist-ai-600-1.yml",
    "eu-ai-act.yml",
    "gdpr.yml",
    "owasp-llm.yml",
    "iso-23053.yml",
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
        """Discover mitigation and risk files with caching and fallback."""
        try:
            # Try to load from cache first
            cached_result = await self._load_from_cache()
            if cached_result:
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

            # Fetch from GitHub API
            github_result = await self._fetch_from_github()
            if github_result:
                # Save to cache
                await self._save_to_cache(github_result)
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
