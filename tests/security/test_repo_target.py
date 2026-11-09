"""Tests for deriving every GitHub fetch target from the configured base_url.

The defect these cover: the raw-content path honoured FINOS_MCP_BASE_URL while
the GitHub API path and the discovery service hardcoded
finos/ai-governance-framework on the main branch. Because the API path is tried
first, a server configured against a fork served upstream content instead.
"""

from dataclasses import FrozenInstanceError

import pytest

from finos_mcp.config import get_settings
from finos_mcp.content.discovery import GitHubDiscoveryService
from finos_mcp.content.list_file import ListFile
from finos_mcp.security.repo_target import RepoTarget, resolve_repo_target

UPSTREAM_BASE_URL = (
    "https://raw.githubusercontent.com/finos/ai-governance-framework/main/docs"
)
FORK_BASE_URL = "https://raw.githubusercontent.com/acme/governance-fork/release/docs"
MIRROR_BASE_URL = "https://ghe.internal-mirror.example/docs"


def _settings_with(base_url: str):
    """Return real settings with base_url overridden (mirror-test pattern)."""
    return get_settings().model_copy(update={"base_url": base_url})


class TestUpstreamDefault:
    """The default configuration must resolve to exactly today's behaviour."""

    def test_default_base_url_derives_upstream_coordinates(self):
        target = resolve_repo_target(UPSTREAM_BASE_URL)

        assert target.owner == "finos"
        assert target.repo == "ai-governance-framework"
        assert target.ref == "main"
        assert target.path_prefix == "docs"
        assert target.github_api_available is True

    def test_api_url_addresses_the_same_document_as_before(self):
        """Same document as the previously hardcoded URL, now pinned to the ref.

        The ref query parameter is new: without it the API serves the default
        branch, which would diverge from base_url on any other branch.
        """
        target = resolve_repo_target(UPSTREAM_BASE_URL)

        assert target.repo_path("_mitigations", "mi-1_example.md") == (
            "docs/_mitigations/mi-1_example.md"
        )
        assert target.api_contents_url("_mitigations", "mi-1_example.md") == (
            "https://api.github.com/repos/finos/ai-governance-framework"
            "/contents/docs/_mitigations/mi-1_example.md?ref=main"
        )

    def test_framework_subdirectory_resolves_under_data_references(self):
        target = resolve_repo_target(UPSTREAM_BASE_URL)

        assert (
            target.repo_path("_data/references", "owasp-llm.yml")
            == "docs/_data/references/owasp-llm.yml"
        )


class TestForkAndRef:
    """A configured fork must be followed on every axis, ref included."""

    def test_fork_owner_repo_and_ref_are_followed(self):
        target = resolve_repo_target(FORK_BASE_URL)

        assert (target.owner, target.repo, target.ref) == (
            "acme",
            "governance-fork",
            "release",
        )

    def test_api_url_targets_the_fork_not_upstream(self):
        target = resolve_repo_target(FORK_BASE_URL)
        api_url = target.api_contents_url("_risks", "ri-1.md")

        assert "acme/governance-fork" in api_url
        assert "finos/ai-governance-framework" not in api_url

    def test_api_url_pins_the_configured_ref(self):
        """Without an explicit ref the API would serve the default branch."""
        target = resolve_repo_target(FORK_BASE_URL)

        assert target.api_contents_url("_risks", "ri-1.md").endswith("?ref=release")

    def test_repository_root_layout_without_a_path_prefix(self):
        """A repo serving docs at its root has an empty prefix, not 'docs'."""
        target = resolve_repo_target(
            "https://raw.githubusercontent.com/acme/flat-repo/main"
        )

        assert target.path_prefix == ""
        assert target.repo_path("_risks", "ri-1.md") == "_risks/ri-1.md"

    def test_nested_path_prefix_is_preserved(self):
        target = resolve_repo_target(
            "https://raw.githubusercontent.com/acme/repo/main/site/docs"
        )

        assert target.path_prefix == "site/docs"
        assert target.repo_path("_risks") == "site/docs/_risks"


class TestMalformedGitHubUrls:
    """A raw.githubusercontent.com URL that cannot address a repo is a config error."""

    @pytest.mark.parametrize(
        "base_url",
        [
            "https://raw.githubusercontent.com",  # no path at all
            "https://raw.githubusercontent.com/finos",  # owner only
            "https://raw.githubusercontent.com/finos/repo",  # no ref
            "https://raw.githubusercontent.com//repo/main/docs",  # empty owner
            "https://raw.githubusercontent.com/finos//main/docs",  # empty repo
            "https://raw.githubusercontent.com/../repo/main/docs",  # traversal
            "https://raw.githubusercontent.com/finos/repo/main/../../etc",  # traversal
        ],
    )
    def test_unusable_github_url_is_rejected(self, base_url):
        with pytest.raises(ValueError):
            resolve_repo_target(base_url)


class TestNonGitHubHosts:
    """Mirrors and GHE cannot be addressed through api.github.com."""

    def test_mirror_disables_the_github_api(self):
        target = resolve_repo_target(MIRROR_BASE_URL)

        assert target.github_api_available is False
        assert target.owner is None
        assert target.repo is None
        assert target.ref is None

    def test_mirror_api_url_raises_rather_than_falling_back_to_upstream(self):
        target = resolve_repo_target(MIRROR_BASE_URL)

        with pytest.raises(ValueError):
            target.api_contents_url("_risks", "ri-1.md")

    def test_suffix_lookalike_host_is_not_treated_as_github(self):
        """Same exact-match reasoning as is_allowed_fetch_target()."""
        target = resolve_repo_target(
            "https://raw.githubusercontent.com.evil.tld/finos/repo/main/docs"
        )

        assert target.github_api_available is False


class TestNormalization:
    """Cosmetic differences in base_url must not change the resolved target."""

    def test_trailing_slash_is_ignored(self):
        assert resolve_repo_target(UPSTREAM_BASE_URL + "/") == resolve_repo_target(
            UPSTREAM_BASE_URL
        )

    def test_host_matching_is_case_insensitive(self):
        target = resolve_repo_target(
            "https://RAW.GithubUserContent.com/finos/ai-governance-framework/main/docs"
        )

        assert target.github_api_available is True
        assert target.owner == "finos"

    def test_target_is_immutable(self):
        target = resolve_repo_target(UPSTREAM_BASE_URL)

        # A frozen dataclass raises FrozenInstanceError, not a generic error.
        # Asserting the field name proves the write to `owner` is what was
        # refused, rather than some unrelated attribute failure.
        with pytest.raises(FrozenInstanceError, match="cannot assign to field 'owner'"):
            target.owner = "attacker"  # type: ignore[misc]


class TestSettingsIntegration:
    """Settings must expose one resolved target, not a second source of truth."""

    def test_settings_expose_the_resolved_target(self):
        settings = _settings_with(FORK_BASE_URL)

        assert isinstance(settings.repo_target, RepoTarget)
        assert settings.repo_target.owner == "acme"
        assert settings.repo_target.ref == "release"

    def test_startup_validation_rejects_an_unusable_github_base_url(self):
        settings = _settings_with("https://raw.githubusercontent.com/finos")

        with pytest.raises(ValueError, match="base_url"):
            settings.validate_startup()


class TestContentServiceTargets:
    """The API content path must follow base_url, not the upstream constant."""

    async def test_repo_paths_follow_the_configured_prefix(self):
        """The in-repo prefix came from base_url on one path and 'docs/' on the other."""
        settings = _settings_with(
            "https://raw.githubusercontent.com/acme/repo/main/site/docs"
        )

        assert settings.repo_target.repo_path("_mitigations", "mi-1.md") == (
            "site/docs/_mitigations/mi-1.md"
        )


class TestDiscoveryTargets:
    """Discovery listings and static fallback URLs must follow base_url too."""

    @staticmethod
    def _discovery(monkeypatch, base_url: str) -> GitHubDiscoveryService:
        settings = _settings_with(base_url)
        monkeypatch.setattr(
            "finos_mcp.content.discovery.get_settings", lambda *a, **k: settings
        )
        return GitHubDiscoveryService()

    def test_directory_listing_targets_the_fork(self, monkeypatch):
        discovery = self._discovery(monkeypatch, FORK_BASE_URL)

        target = discovery.repo_target
        assert (target.owner, target.repo) == ("acme", "governance-fork")
        assert target.repo_path("_mitigations") == "docs/_mitigations"
        assert target.repo_path("_risks") == "docs/_risks"
        assert target.repo_path("_data/references") == "docs/_data/references"

    async def test_the_listing_requests_one_prefixed_url_per_directory(
        self, monkeypatch
    ):
        """Directory listings take a subdir; repo_target adds the prefix once.

        Passing a repository-root path would silently apply the prefix twice
        ("docs/docs/_risks"), and the listing would answer 404 for every
        directory.
        """
        discovery = self._discovery(monkeypatch, UPSTREAM_BASE_URL)
        requested: list[str] = []

        async def _record(client, repo_target, directory, token=None):
            requested.append(repo_target.api_contents_url(directory.subdir))
            return []

        monkeypatch.setattr("finos_mcp.content.github_api.list_directory", _record)
        monkeypatch.setattr(
            "finos_mcp.content.discovery.get_http_client", lambda *a, **k: _none()
        )

        await discovery._fetch_from_github()

        assert len(requested) == 3
        for url in requested:
            assert "/contents/docs/_" in url, url
            assert "docs/docs" not in url, url

    async def test_mirror_config_skips_the_github_api_discovery(
        self, monkeypatch, tmp_path
    ):
        """No owner/repo can be derived, so no API request may be attempted."""
        discovery = self._discovery(monkeypatch, MIRROR_BASE_URL)

        async def _no_client(*args, **kwargs):
            raise AssertionError("GitHub API discovery attempted for a mirror base_url")

        monkeypatch.setattr("finos_mcp.content.discovery.get_http_client", _no_client)
        discovery.list_file = ListFile(tmp_path, discovery.repo_target, 3600)

        result = await discovery.discover_content()

        assert result.source == "static_fallback"


async def _none(*args, **kwargs):
    """Awaitable returning None, for cache lookups that must miss."""
    return None
