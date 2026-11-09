"""A throttled request must not look like a missing document.

Before these behaviours existed, an exhausted GitHub budget and a document that
does not exist produced the same string -- "Failed to load content for X" -- and
search answered "0 results" for "we were blocked". An assistant relays both as
established fact, which is the worst possible failure for a compliance tool: the
user is told a framework is unavailable, or that nothing matched, when neither is
true.

Every test here asserts the *distinction*, not just the happy path. A test that
only checked the throttled message would still pass if "not found" were given the
same text.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import pytest

from finos_mcp.content import service as service_module
from finos_mcp.content.service import (
    OperationContext,
    _rate_limit_retry_after,
)
from finos_mcp.exceptions import (
    ContentLoadingError,
    GitHubRateLimitError,
    UnknownDocumentError,
)


@pytest.mark.unit
class TestRateLimitDetection:
    """A throttle on the raw route is found through the wrapped exception.

    The rule that reads an answer is ``github_api.retry_after_if_rate_limited``
    since #310, tested in test_github_api.py; this is the raw route's use of it.
    """

    def test_throttle_is_found_through_a_wrapped_exception_chain(self) -> None:
        """The 429 is re-wrapped as ContentLoadingError before anyone can see it."""
        inner = httpx.HTTPStatusError(
            "throttled",
            request=httpx.Request("GET", "https://raw.githubusercontent.com/x"),
            response=httpx.Response(429),
        )
        try:
            try:
                raise inner
            except httpx.HTTPStatusError as exc:
                raise ContentLoadingError(
                    source="u", details="d", retry_after=60
                ) from exc
        except ContentLoadingError as outer:
            assert _rate_limit_retry_after(outer) == 60

    def test_unrelated_failures_are_not_reported_as_throttles(self) -> None:
        assert _rate_limit_retry_after(ValueError("nope")) is None

    def test_a_cyclic_exception_chain_terminates(self) -> None:
        """__cause__ can be made to loop; the walk must not hang the server."""
        a = ValueError("a")
        b = ValueError("b")
        a.__cause__ = b
        b.__cause__ = a
        assert _rate_limit_retry_after(a) is None


@pytest.mark.unit
class TestOperationContextCarriesTheReason:
    def test_context_defaults_to_no_recorded_failure(self) -> None:
        ctx = OperationContext(
            operation_id="op",
            doc_type="framework",
            filename="f.yml",
            url="https://example.invalid/f.yml",
            start_time=time.time(),
        )
        assert ctx.retry_after is None


@pytest.mark.unit
class TestToolsDistinguishThrottledFromMissing:
    """The behaviour a caller actually sees."""

    @pytest.fixture
    def throttled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _raise(self: Any, *args: Any, **kwargs: Any) -> None:
            raise GitHubRateLimitError("retry in 60 seconds")

        monkeypatch.setattr(service_module.ContentService, "get_document", _raise)

    async def test_get_framework_raises_and_says_what_to_do(
        self, throttled: None
    ) -> None:
        from finos_mcp.documents import tools as doc_tools

        with pytest.raises(GitHubRateLimitError) as excinfo:
            await doc_tools.get_framework(framework_id="eu-ai-act")

        message = str(excinfo.value)
        # Names the cause, says it is temporary, and gives the remedy.
        assert "rate limiting" in message
        assert "temporary throttle" in message
        assert "FINOS_MCP_GITHUB_TOKEN" in message
        # And must not be mistakable for a missing document.
        assert "not found" not in message.lower()

    async def test_missing_framework_is_still_reported_as_missing(self) -> None:
        """The negative case. Without it, "everything raises" would pass above."""
        from finos_mcp.documents import tools as doc_tools

        with pytest.raises(UnknownDocumentError) as excinfo:
            await doc_tools.get_framework(framework_id="no-such-framework-xyz")
        assert not isinstance(excinfo.value, GitHubRateLimitError)
        assert "'no-such-framework-xyz'" in str(excinfo.value)
        assert "rate limiting" not in str(excinfo.value)

    async def test_search_does_not_answer_no_matches_when_blocked(
        self, throttled: None
    ) -> None:
        """The dangerous one: an empty result set reads as an authoritative answer."""
        from finos_mcp.search import tools as search_tools

        # Framework search has no metadata tier, so the body is always fetched
        # and the throttle is actually reached.
        with pytest.raises(GitHubRateLimitError):
            await search_tools.search_frameworks(
                query="supervisory colleges notification", limit=3
            )
