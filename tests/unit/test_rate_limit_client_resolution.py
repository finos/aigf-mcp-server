"""Rate-limit client identity, and the guard that keys on it (``app.py``).

Both classes here exercise ``finos_mcp.app``: ``_resolve_dos_client_id`` decides
*who* a caller is, and ``DoSProtectionMiddleware`` is the thing that must key its
budget on that answer rather than on a shared constant. They moved here whole
from ``test_fastmcp_server.py`` in #141, which was named after a module that no
longer holds any of this.
"""

import ipaddress
from types import SimpleNamespace

import pytest
from mcp import MCPError

from finos_mcp import app as _app
from finos_mcp import fastmcp_server
from finos_mcp.security.dos_middleware import DoSProtectionMiddleware
from finos_mcp.security.request_validator import DoSProtector, RequestSizeValidator


@pytest.mark.unit
class TestRateLimitClientResolution:
    """Rate-limit identity resolution (AIGF-F1, #21).

    Every tool shares one bucket unless the caller is identified per client, so
    these tests pin which identity wins and, more importantly, which inputs are
    refused. X-Forwarded-For is caller-controlled: honouring it from an
    unverified peer would let a client mint a fresh bucket per request.
    """

    @staticmethod
    def _http_request(peer, forwarded=None):
        """Build a stand-in Starlette request with a peer address and headers."""
        request = SimpleNamespace(
            client=SimpleNamespace(host=peer) if peer else None,
            headers={"x-forwarded-for": forwarded} if forwarded else {},
        )
        return request

    @staticmethod
    def _token(subject=None, client_id="client-app"):
        """Build a stand-in access token carrying the given subject claim."""
        return SimpleNamespace(
            claims={"sub": subject} if subject else {}, client_id=client_id
        )

    def _resolve(
        self, monkeypatch, *, peer=None, forwarded=None, token=None, trusted=()
    ):
        """Resolve a client id under a controlled request/auth/proxy context."""
        monkeypatch.setattr(
            _app.settings,
            "dos_trusted_proxy_networks",
            [ipaddress.ip_network(entry) for entry in trusted],
        )
        monkeypatch.setattr(_app, "get_access_token", lambda: token)

        def fake_get_http_request():
            if peer is None and forwarded is None:
                raise RuntimeError("No active HTTP request found.")
            return self._http_request(peer, forwarded)

        monkeypatch.setattr(_app, "get_http_request", fake_get_http_request)
        return _app._resolve_dos_client_id()

    def test_stdio_keeps_its_fixed_identity(self, monkeypatch):
        """Regression guard: stdio is one client per process and must not change."""
        assert self._resolve(monkeypatch) == _app._STDIO_CLIENT_ID
        assert _app._STDIO_CLIENT_ID == "mcp_client"

    def test_distinct_peers_get_distinct_keys(self, monkeypatch):
        """The core fix: two HTTP clients must not share a bucket."""
        first = self._resolve(monkeypatch, peer="203.0.113.5")
        second = self._resolve(monkeypatch, peer="198.51.100.7")

        assert first == "ip:203.0.113.5"
        assert first != second

    def test_jwt_subject_wins_over_address(self, monkeypatch):
        """An attested subject survives NAT and IP rotation, so it is preferred."""
        resolved = self._resolve(
            monkeypatch, peer="203.0.113.5", token=self._token("user-a")
        )

        assert resolved == "jwt:user-a"

    def test_distinct_subjects_from_one_address_get_distinct_keys(self, monkeypatch):
        """Two users behind one NAT must not share a bucket."""
        first = self._resolve(
            monkeypatch, peer="203.0.113.5", token=self._token("user-a")
        )
        second = self._resolve(
            monkeypatch, peer="203.0.113.5", token=self._token("user-b")
        )

        assert first != second

    def test_token_without_subject_is_not_identified_by_its_client_id(
        self, monkeypatch
    ):
        """The verifier refuses a token without sub (#320); only sub is read (#408)."""
        resolved = self._resolve(
            monkeypatch, peer="203.0.113.5", token=self._token(None, "client-app")
        )

        assert resolved == "ip:203.0.113.5"

    def test_forwarded_header_ignored_when_no_proxy_configured(self, monkeypatch):
        """Default posture: the header is not evidence of anything."""
        resolved = self._resolve(monkeypatch, peer="203.0.113.5", forwarded="1.2.3.4")

        assert resolved == "ip:203.0.113.5"

    def test_forwarded_header_ignored_from_untrusted_peer(self, monkeypatch):
        """A direct caller cannot pick its bucket just because a proxy exists."""
        resolved = self._resolve(
            monkeypatch,
            peer="203.0.113.5",
            forwarded="1.2.3.4",
            trusted=["127.0.0.1/32"],
        )

        assert resolved == "ip:203.0.113.5"

    def test_forwarded_header_honoured_from_trusted_peer(self, monkeypatch):
        """Behind a configured proxy, the real client is the one rate limited."""
        resolved = self._resolve(
            monkeypatch,
            peer="127.0.0.1",
            forwarded="1.2.3.4",
            trusted=["127.0.0.1/32"],
        )

        assert resolved == "ip:1.2.3.4"

    def test_prepended_spoof_is_discarded(self, monkeypatch):
        """A client-supplied prefix sits left of our own hops and must be ignored."""
        resolved = self._resolve(
            monkeypatch,
            peer="127.0.0.1",
            forwarded="203.0.113.99, 1.2.3.4, 10.0.0.7",
            trusted=["127.0.0.1/32", "10.0.0.0/8"],
        )

        assert resolved == "ip:1.2.3.4"

    def test_malformed_chain_falls_back_to_peer(self, monkeypatch):
        """A header we cannot parse is a header we do not trust."""
        resolved = self._resolve(
            monkeypatch,
            peer="127.0.0.1",
            forwarded="not-an-ip-address",
            trusted=["127.0.0.1/32"],
        )

        assert resolved == "ip:127.0.0.1"

    def test_all_trusted_chain_falls_back_to_peer(self, monkeypatch):
        """If every hop is ours, no real client is identifiable in the header."""
        resolved = self._resolve(
            monkeypatch,
            peer="127.0.0.1",
            forwarded="10.0.0.7",
            trusted=["127.0.0.1/32", "10.0.0.0/8"],
        )

        assert resolved == "ip:127.0.0.1"

    def test_ipv6_proxy_and_client(self, monkeypatch):
        """IPv6 deployments resolve the same way."""
        resolved = self._resolve(
            monkeypatch,
            peer="::1",
            forwarded="2001:db8::1",
            trusted=["::1/128"],
        )

        assert resolved == "ip:2001:db8::1"

    def test_missing_peer_address_falls_back_to_stdio_identity(self, monkeypatch):
        """An HTTP request without a peer yields no network identity."""
        resolved = self._resolve(monkeypatch, peer=None, forwarded="1.2.3.4")

        assert resolved == _app._STDIO_CLIENT_ID


@pytest.mark.unit
class TestDoSProtectionUsesResolvedClient:
    """The guard must key on the resolved caller, not a shared constant.

    Resolving the identity correctly is useless if the guard still passes a fixed id,
    which is exactly the defect in AIGF-F1 (#21).

    Enforcement moved from the tool bodies into DoSProtectionMiddleware in #23, so
    these drive the middleware. End-to-end coverage that a rejection actually reaches
    the caller lives in tests/security/test_dos_middleware.py.
    """

    @staticmethod
    def _middleware(protector, identity):
        return DoSProtectionMiddleware(
            protector=protector,
            validator=RequestSizeValidator(),
            resolve_client_id=lambda: identity(),
        )

    @staticmethod
    async def _pass_through(_context):
        return "ok"

    @pytest.mark.asyncio
    async def test_one_client_exhausting_its_budget_does_not_block_another(self):
        """The finding, restated as a test: a noisy client must not starve others."""
        protector = DoSProtector(max_requests_per_minute=3)
        identity = "ip:203.0.113.5"
        middleware = self._middleware(protector, lambda: identity)

        for _ in range(3):
            await middleware.on_request(None, self._pass_through)
        with pytest.raises(MCPError, match="Rate limit exceeded") as refusal:
            await middleware.on_request(None, self._pass_through)
        # JSON-RPC's implementation-defined server error (#162).
        assert refusal.value.code == -32000

        # A different caller arrives; its budget must be untouched.
        identity = "ip:198.51.100.7"
        assert await middleware.on_request(None, self._pass_through) == "ok"

    @pytest.mark.asyncio
    async def test_budget_is_tracked_under_the_resolved_key(self):
        """Guards against the id being resolved and then quietly discarded."""
        protector = DoSProtector(max_requests_per_minute=10)
        middleware = self._middleware(protector, lambda: "jwt:user-a")

        await middleware.on_request(None, self._pass_through)

        assert "jwt:user-a" in protector._request_history

    @pytest.mark.asyncio
    async def test_the_server_registers_the_middleware(self):
        """A resolver and a protector are worthless if nothing installs the guard."""
        assert any(
            isinstance(mw, DoSProtectionMiddleware)
            for mw in fastmcp_server.mcp.middleware
        )
