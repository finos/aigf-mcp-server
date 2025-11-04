"""
Test suite for SHA-based content validation in GitHubDiscoveryService.

Tests the smart cache validation that uses GitHub SHA hashes to detect
content changes and extend cache TTL when content is unchanged.
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from finos_mcp.content.discovery import (
    DiscoveryResult,
    GitHubDiscoveryService,
    GitHubFileInfo,
)


@pytest.mark.unit
class TestSHAValidation:
    """Test SHA-based content validation logic."""

    def test_shas_match_identical_lists(self):
        """Test that identical file lists match."""
        service = GitHubDiscoveryService()

        files1 = [
            GitHubFileInfo(
                filename="ri-1_test.md",
                path="docs/_risks/ri-1_test.md",
                sha="abc123",
                size=1000,
                download_url="https://example.com/file1",
            ),
            GitHubFileInfo(
                filename="ri-2_test.md",
                path="docs/_risks/ri-2_test.md",
                sha="def456",
                size=2000,
                download_url="https://example.com/file2",
            ),
        ]

        files2 = [
            GitHubFileInfo(
                filename="ri-1_test.md",
                path="docs/_risks/ri-1_test.md",
                sha="abc123",
                size=1000,
                download_url="https://example.com/file1",
            ),
            GitHubFileInfo(
                filename="ri-2_test.md",
                path="docs/_risks/ri-2_test.md",
                sha="def456",
                size=2000,
                download_url="https://example.com/file2",
            ),
        ]

        assert service._shas_match(files1, files2) is True

    def test_shas_match_modified_file(self):
        """Test that modified files are detected via SHA change."""
        service = GitHubDiscoveryService()

        cached_files = [
            GitHubFileInfo(
                filename="ri-1_test.md",
                path="docs/_risks/ri-1_test.md",
                sha="abc123",  # Old SHA
                size=1000,
                download_url="https://example.com/file1",
            ),
        ]

        current_files = [
            GitHubFileInfo(
                filename="ri-1_test.md",
                path="docs/_risks/ri-1_test.md",
                sha="xyz789",  # New SHA - file was modified
                size=1000,
                download_url="https://example.com/file1",
            ),
        ]

        assert service._shas_match(cached_files, current_files) is False

    def test_shas_match_added_file(self):
        """Test that added files are detected."""
        service = GitHubDiscoveryService()

        cached_files = [
            GitHubFileInfo(
                filename="ri-1_test.md",
                path="docs/_risks/ri-1_test.md",
                sha="abc123",
                size=1000,
                download_url="https://example.com/file1",
            ),
        ]

        current_files = [
            GitHubFileInfo(
                filename="ri-1_test.md",
                path="docs/_risks/ri-1_test.md",
                sha="abc123",
                size=1000,
                download_url="https://example.com/file1",
            ),
            GitHubFileInfo(
                filename="ri-2_new.md",  # New file
                path="docs/_risks/ri-2_new.md",
                sha="def456",
                size=2000,
                download_url="https://example.com/file2",
            ),
        ]

        assert service._shas_match(cached_files, current_files) is False

    def test_shas_match_removed_file(self):
        """Test that removed files are detected."""
        service = GitHubDiscoveryService()

        cached_files = [
            GitHubFileInfo(
                filename="ri-1_test.md",
                path="docs/_risks/ri-1_test.md",
                sha="abc123",
                size=1000,
                download_url="https://example.com/file1",
            ),
            GitHubFileInfo(
                filename="ri-2_removed.md",  # This will be removed
                path="docs/_risks/ri-2_removed.md",
                sha="def456",
                size=2000,
                download_url="https://example.com/file2",
            ),
        ]

        current_files = [
            GitHubFileInfo(
                filename="ri-1_test.md",
                path="docs/_risks/ri-1_test.md",
                sha="abc123",
                size=1000,
                download_url="https://example.com/file1",
            ),
        ]

        assert service._shas_match(cached_files, current_files) is False

    def test_shas_match_empty_lists(self):
        """Test that empty lists match."""
        service = GitHubDiscoveryService()

        assert service._shas_match([], []) is True

    @pytest.mark.asyncio
    async def test_content_unchanged_all_match(self):
        """Test that content_unchanged returns True when all SHAs match."""
        service = GitHubDiscoveryService()

        # Create cached result
        cached_result = DiscoveryResult(
            mitigation_files=[
                GitHubFileInfo(
                    filename="mi-1_test.md",
                    path="docs/_mitigations/mi-1_test.md",
                    sha="abc123",
                    size=1000,
                    download_url="https://example.com/mi1",
                )
            ],
            risk_files=[
                GitHubFileInfo(
                    filename="ri-1_test.md",
                    path="docs/_risks/ri-1_test.md",
                    sha="def456",
                    size=2000,
                    download_url="https://example.com/ri1",
                )
            ],
            framework_files=[
                GitHubFileInfo(
                    filename="framework.yml",
                    path="docs/_data/framework.yml",
                    sha="ghi789",
                    size=3000,
                    download_url="https://example.com/fw1",
                )
            ],
            source="cache",
        )

        # Mock _fetch_directory to return files with same SHAs
        with patch.object(
            service, "_fetch_directory", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = [
                cached_result.mitigation_files,  # Same mitigations
                cached_result.risk_files,  # Same risks
                cached_result.framework_files,  # Same frameworks
            ]

            result = await service._content_unchanged(cached_result)

            assert result is True
            assert mock_fetch.call_count == 3

    @pytest.mark.asyncio
    async def test_content_unchanged_mitigation_changed(self):
        """Test that content_unchanged returns False when mitigations change."""
        service = GitHubDiscoveryService()

        cached_result = DiscoveryResult(
            mitigation_files=[
                GitHubFileInfo(
                    filename="mi-1_test.md",
                    path="docs/_mitigations/mi-1_test.md",
                    sha="abc123",  # Old SHA
                    size=1000,
                    download_url="https://example.com/mi1",
                )
            ],
            risk_files=[],
            framework_files=[],
            source="cache",
        )

        # Mock _fetch_directory to return modified mitigation
        with patch.object(
            service, "_fetch_directory", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = [
                GitHubFileInfo(
                    filename="mi-1_test.md",
                    path="docs/_mitigations/mi-1_test.md",
                    sha="xyz789",  # New SHA - file changed
                    size=1000,
                    download_url="https://example.com/mi1",
                )
            ]

            result = await service._content_unchanged(cached_result)

            assert result is False

    @pytest.mark.asyncio
    async def test_content_unchanged_api_failure(self):
        """Test that content_unchanged fails safe on API errors."""
        service = GitHubDiscoveryService()

        cached_result = DiscoveryResult(
            mitigation_files=[],
            risk_files=[],
            framework_files=[],
            source="cache",
        )

        # Mock both get_http_client and _fetch_directory
        with patch(
            "finos_mcp.content.discovery.get_http_client", new_callable=AsyncMock
        ) as mock_client:
            mock_client.return_value = MagicMock()

            with patch.object(
                service, "_fetch_directory", new_callable=AsyncMock
            ) as mock_fetch:
                # Use a specific exception type that's caught
                import httpx

                mock_fetch.side_effect = httpx.HTTPError("API Error")

                result = await service._content_unchanged(cached_result)

                # Should fail safe and assume content changed
                assert result is False

    @pytest.mark.asyncio
    async def test_load_expired_cache_valid_file(self, tmp_path):
        """Test loading expired cache file for SHA comparison."""
        service = GitHubDiscoveryService()
        service.cache_dir = tmp_path

        # Create a valid cache file
        cache_data = {
            "mitigation_files": [
                {
                    "filename": "mi-1_test.md",
                    "path": "docs/_mitigations/mi-1_test.md",
                    "sha": "abc123",
                    "size": 1000,
                    "download_url": "https://example.com/mi1",
                    "last_modified": None,
                }
            ],
            "risk_files": [],
            "framework_files": [],
            "source": "github_api",
            "cache_expires": (
                datetime.now(timezone.utc) - timedelta(hours=1)
            ).isoformat(),  # Expired
            "rate_limit_remaining": 100,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }

        cache_file = tmp_path / "github_discovery.json"
        cache_file.write_text(json.dumps(cache_data))

        # Load expired cache
        result = await service._load_expired_cache()

        assert result is not None
        assert len(result.mitigation_files) == 1
        assert result.mitigation_files[0].sha == "abc123"

    @pytest.mark.asyncio
    async def test_load_expired_cache_missing_file(self, tmp_path):
        """Test loading expired cache when file doesn't exist."""
        service = GitHubDiscoveryService()
        service.cache_dir = tmp_path

        result = await service._load_expired_cache()

        assert result is None

    @pytest.mark.asyncio
    async def test_load_expired_cache_corrupted_file(self, tmp_path):
        """Test loading expired cache with corrupted JSON."""
        service = GitHubDiscoveryService()
        service.cache_dir = tmp_path

        # Create corrupted cache file
        cache_file = tmp_path / "github_discovery.json"
        cache_file.write_text("{ invalid json }")

        result = await service._load_expired_cache()

        assert result is None


@pytest.mark.unit
class TestStaticFallbackSync:
    """Test static fallback synchronization checking."""

    def test_check_static_fallback_sync_all_match(self):
        """Test that no warnings when static lists match."""
        service = GitHubDiscoveryService()

        # Get current static lists
        from finos_mcp.content.discovery import (
            STATIC_FRAMEWORK_FILES,
            STATIC_MITIGATION_FILES,
            STATIC_RISK_FILES,
        )

        # Create result that matches static lists exactly
        current_result = DiscoveryResult(
            mitigation_files=[
                GitHubFileInfo(
                    filename=f,
                    path=f"docs/_mitigations/{f}",
                    sha="test",
                    size=100,
                    download_url=f"https://example.com/{f}",
                )
                for f in STATIC_MITIGATION_FILES
            ],
            risk_files=[
                GitHubFileInfo(
                    filename=f,
                    path=f"docs/_risks/{f}",
                    sha="test",
                    size=100,
                    download_url=f"https://example.com/{f}",
                )
                for f in STATIC_RISK_FILES
            ],
            framework_files=[
                GitHubFileInfo(
                    filename=f,
                    path=f"docs/_data/{f}",
                    sha="test",
                    size=100,
                    download_url=f"https://example.com/{f}",
                )
                for f in STATIC_FRAMEWORK_FILES
            ],
            source="github_api",
        )

        # Should not raise any warnings
        with patch("finos_mcp.content.discovery.logger") as mock_logger:
            service._check_static_fallback_sync(current_result)

            # Should log debug (not warning) when synchronized
            mock_logger.debug.assert_called_once()
            mock_logger.warning.assert_not_called()

    def test_check_static_fallback_sync_mitigation_mismatch(self):
        """Test that warnings are logged when mitigations don't match."""
        service = GitHubDiscoveryService()

        current_result = DiscoveryResult(
            mitigation_files=[
                GitHubFileInfo(
                    filename="mi-99_new_mitigation.md",  # Not in static list
                    path="docs/_mitigations/mi-99_new_mitigation.md",
                    sha="test",
                    size=100,
                    download_url="https://example.com/mi99",
                )
            ],
            risk_files=[],
            framework_files=[],
            source="github_api",
        )

        with patch("finos_mcp.content.discovery.logger") as mock_logger:
            service._check_static_fallback_sync(current_result)

            # Should log warnings about mismatch
            assert mock_logger.warning.call_count >= 2  # Mismatch + update message


@pytest.mark.unit
class TestSHAValidationIntegration:
    """Integration tests for SHA validation in discover_content flow."""

    @pytest.mark.asyncio
    async def test_discover_content_cache_extended_when_unchanged(self, tmp_path):
        """Test that cache TTL is extended when SHAs match."""
        service = GitHubDiscoveryService()
        service.cache_dir = tmp_path

        # Create expired cache
        old_expires = datetime.now(timezone.utc) - timedelta(minutes=5)
        cache_data = {
            "mitigation_files": [
                {
                    "filename": "mi-1_test.md",
                    "path": "docs/_mitigations/mi-1_test.md",
                    "sha": "abc123",
                    "size": 1000,
                    "download_url": "https://example.com/mi1",
                    "last_modified": None,
                }
            ],
            "risk_files": [],
            "framework_files": [],
            "source": "github_api",
            "cache_expires": old_expires.isoformat(),
            "rate_limit_remaining": 100,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }

        cache_file = tmp_path / "github_discovery.json"
        cache_file.write_text(json.dumps(cache_data))

        # Mock _fetch_directory to return same files (SHAs match)
        with patch.object(
            service, "_fetch_directory", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = [
                [
                    GitHubFileInfo(
                        filename="mi-1_test.md",
                        path="docs/_mitigations/mi-1_test.md",
                        sha="abc123",  # Same SHA
                        size=1000,
                        download_url="https://example.com/mi1",
                    )
                ],
                [],  # risks
                [],  # frameworks
            ]

            result = await service.discover_content()

            # Cache should be extended, not re-fetched
            assert result is not None
            assert result.source == "cache"

            # Verify cache file was updated with new expiry
            updated_cache = json.loads(cache_file.read_text())
            new_expires = datetime.fromisoformat(updated_cache["cache_expires"])
            assert new_expires > old_expires

    @pytest.mark.asyncio
    async def test_discover_content_fetches_when_sha_changed(self, tmp_path):
        """Test that fresh content is fetched when SHAs don't match."""
        service = GitHubDiscoveryService()
        service.cache_dir = tmp_path

        # Create expired cache
        cache_data = {
            "mitigation_files": [
                {
                    "filename": "mi-1_test.md",
                    "path": "docs/_mitigations/mi-1_test.md",
                    "sha": "abc123",  # Old SHA
                    "size": 1000,
                    "download_url": "https://example.com/mi1",
                    "last_modified": None,
                }
            ],
            "risk_files": [],
            "framework_files": [],
            "source": "github_api",
            "cache_expires": (
                datetime.now(timezone.utc) - timedelta(minutes=5)
            ).isoformat(),
            "rate_limit_remaining": 100,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }

        cache_file = tmp_path / "github_discovery.json"
        cache_file.write_text(json.dumps(cache_data))

        # Mock to return different SHA first (for comparison), then full fetch
        call_count = 0

        async def mock_fetch_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:  # First 3 calls are for SHA comparison
                return [
                    GitHubFileInfo(
                        filename="mi-1_test.md",
                        path="docs/_mitigations/mi-1_test.md",
                        sha="xyz789",  # Different SHA - content changed
                        size=1000,
                        download_url="https://example.com/mi1",
                    )
                ]
            else:  # Subsequent calls are for full fetch
                return [
                    GitHubFileInfo(
                        filename="mi-1_test.md",
                        path="docs/_mitigations/mi-1_test.md",
                        sha="xyz789",
                        size=1000,
                        download_url="https://example.com/mi1",
                    )
                ]

        with patch.object(
            service, "_fetch_directory", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = mock_fetch_side_effect

            result = await service.discover_content()

            # Should have fetched fresh content
            assert result is not None
            # Note: During comparison, it detects change and fetches fresh
            assert mock_fetch.call_count >= 3
