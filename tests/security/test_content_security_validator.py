"""The fetch target checks: why_not_a_fetch_target and the host allowlist.

The SSRF cases below once ran against ``ContentSecurityValidator.is_safe_url``,
which repeated ``why_not_a_fetch_target`` with a looser scheme rule (#379).
"""

import pytest

from finos_mcp.config import get_settings
from finos_mcp.content.fetch import HTTPClient
from finos_mcp.security.content_filter import is_allowed_fetch_target
from finos_mcp.security.repo_target import why_not_a_fetch_target


class TestFetchTargetForm:
    """What a URL must be before its host is even looked up."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://api.github.com/repos/owner/repo",
            "https://example.com/path/to/resource",
            "https://subdomain.domain.com/file.json",
            "https://cdn.example.com/assets/data.yaml",
        ],
    )
    def test_public_https_urls_pass(self, url):
        assert why_not_a_fetch_target(url) is None

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost:8080/admin",
            "http://example.com/doc.md",  # plaintext: is_safe_url let this through
            "https://127.0.0.1/internal",
            "https://192.168.1.1/config",
            "ftp://example.com/file",
            "file:///etc/passwd",
            "javascript:alert('xss')",
            "data:text/html,<script>alert('xss')</script>",
            "mailto:contact@example.com",  # is_safe_url let this through
            "https://10.0.0.1/internal",
        ],
    )
    def test_dangerous_urls_are_refused(self, url):
        assert why_not_a_fetch_target(url), f"should be refused: {url}"


class TestSSRFAddressBlocking:
    """Regression tests for SSRF bypasses (AIGF-F4)."""

    @pytest.mark.parametrize(
        "hostname",
        [
            "169.254.169.254",  # cloud instance metadata (IMDS)
            "169.254.1.1",  # link-local
            "127.0.0.2",  # loopback beyond the literal 127.0.0.1
            "127.255.255.254",  # top of 127.0.0.0/8
            "0.0.0.0",  # unspecified  # noqa: S104
            "[::1]",  # IPv6 loopback
            "[::ffff:127.0.0.1]",  # IPv4-mapped IPv6 loopback
            "[::]",  # IPv6 unspecified
            "[fd00::1]",  # IPv6 unique local
            "[fe80::1]",  # IPv6 link-local
            "100.64.0.1",  # CGNAT shared address space
            "10.0.0.1",
            "172.16.0.1",
            "192.168.1.1",
            "localhost",  # by name
        ],
    )
    def test_internal_addresses_blocked(self, hostname):
        """Internal and non-globally-routable addresses must be rejected."""
        assert why_not_a_fetch_target(f"https://{hostname}/internal"), (
            f"Internal address should be blocked: {hostname}"
        )

    @pytest.mark.parametrize(
        "hostname",
        ["8.8.8.8", "185.199.108.153", "raw.githubusercontent.com"],
    )
    def test_public_addresses_still_allowed(self, hostname):
        """The predicate must not over-block genuinely public targets."""
        assert why_not_a_fetch_target(f"https://{hostname}/path") is None


class TestFetchTargetAllowlist:
    """Tests for the outbound fetch host allowlist (AIGF-F4)."""

    ALLOWED = frozenset({"raw.githubusercontent.com", "api.github.com"})

    @pytest.mark.parametrize(
        "url",
        [
            "https://raw.githubusercontent.com/finos/ai-governance-framework/main/docs/x.md",
            "https://api.github.com/repos/finos/ai-governance-framework/contents/docs",
        ],
    )
    def test_github_hosts_allowed(self, url):
        """The content hosts this server actually uses must pass."""
        assert is_allowed_fetch_target(url, self.ALLOWED)

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/doc.md",  # arbitrary public host
            "https://raw.githubusercontent.com.evil.tld/x",  # suffix lookalike
            "https://evil.tld/raw.githubusercontent.com",  # path lookalike
            "http://raw.githubusercontent.com/x",  # plaintext scheme
            "mailto:contact@example.com",  # no hostname
            "https:///path-only",  # empty hostname
        ],
    )
    def test_non_allowlisted_targets_blocked(self, url):
        """Anything outside the allowlist must be rejected."""
        assert not is_allowed_fetch_target(url, self.ALLOWED)

    @pytest.mark.parametrize("hostname", ["2130706433", "0x7f.0.0.1", "0177.0.0.1"])
    def test_encoded_ip_literals_blocked_by_allowlist(self, hostname):
        """Encoded IP literals resolve to loopback but do not parse as IPs.

        ipaddress.ip_address() cannot parse these, so why_not_a_fetch_target()
        lets them through by design. The allowlist is what actually stops them, which is
        why it must not be weakened to a suffix or pattern match.
        """
        url = f"https://{hostname}/internal"
        assert why_not_a_fetch_target(url) is None, (
            "documents the known gap in the IP-literal check"
        )
        assert not is_allowed_fetch_target(url, self.ALLOWED)


class TestHTTPClientFetchGating:
    """The allowlist must be enforced on the real outbound request path."""

    async def test_make_request_rejects_non_allowlisted_host(self):
        """A disallowed host is rejected before any socket work happens."""
        client = HTTPClient()
        try:
            with pytest.raises(ValueError, match="non-allowlisted host"):
                await client._make_request("GET", "https://example.com/doc.md")
        finally:
            await client.close()

    async def test_make_request_rejects_internal_address(self):
        """Internal addresses are reported as unsafe, not as an allowlist miss."""
        client = HTTPClient()
        try:
            with pytest.raises(ValueError, match="Blocked unsafe URL"):
                await client._make_request(
                    "GET", "https://169.254.169.254/latest/meta-data/"
                )
        finally:
            await client.close()

    async def test_base_url_host_is_allowlisted(self):
        """A configured base_url host must be reachable (mirror deployments)."""
        settings = get_settings()
        mirror = settings.model_copy(
            update={"base_url": "https://ghe.internal-mirror.example/docs"}
        )
        client = HTTPClient(settings=mirror)
        try:
            assert "ghe.internal-mirror.example" in client._allowed_fetch_hosts
            assert "raw.githubusercontent.com" in client._allowed_fetch_hosts
        finally:
            await client.close()
