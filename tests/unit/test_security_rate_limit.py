"""
Test suite for rate limiting functionality.

Tests the RateLimiter, RateLimitInfo, and rate limiting utilities.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from finos_mcp.security.rate_limit import (
    RateLimiter,
    RateLimiterManager,
    RateLimitInfo,
    get_github_rate_limiter,
    rate_limited_github_request,
)


@pytest.mark.unit
class TestRateLimitInfo:
    """Test RateLimitInfo dataclass."""

    def test_rate_limit_info_creation(self):
        """Test basic RateLimitInfo creation."""
        info = RateLimitInfo(
            remaining=4900,
            limit=5000,
            reset_time=int(time.time()) + 3600,
            retry_after=None,
        )

        assert info.remaining == 4900
        assert info.limit == 5000
        assert info.reset_time > time.time()
        assert info.retry_after is None

    def test_rate_limit_info_with_retry_after(self):
        """Test RateLimitInfo with retry_after value."""
        info = RateLimitInfo(
            remaining=0, limit=5000, reset_time=int(time.time()) + 3600, retry_after=60
        )

        assert info.remaining == 0
        assert info.retry_after == 60


@pytest.mark.unit
class TestRateLimiter:
    """Test RateLimiter functionality."""

    def test_rate_limiter_creation(self):
        """Test basic RateLimiter creation."""
        limiter = RateLimiter()

        assert hasattr(limiter, "min_delay")
        assert hasattr(limiter, "max_retries")
        assert hasattr(limiter, "backoff_factor")
        assert hasattr(limiter, "rate_limit_buffer")
        assert limiter.current_rate_limit is None

    def test_rate_limiter_default_values(self):
        """Test RateLimiter default values."""
        limiter = RateLimiter()

        # Check that all default values are reasonable numbers
        assert isinstance(limiter.min_delay, float)
        assert isinstance(limiter.max_retries, int)
        assert isinstance(limiter.backoff_factor, float)
        assert isinstance(limiter.rate_limit_buffer, int)
        assert limiter.min_delay > 0
        assert limiter.max_retries >= 0
        assert limiter.backoff_factor >= 1.0

    def test_should_proceed_initially(self):
        """Test that requests are allowed initially."""
        limiter = RateLimiter()

        assert limiter.should_proceed_with_request() is True

    def test_should_proceed_with_rate_limit_info(self):
        """Test should_proceed_with_request with rate limit info."""
        limiter = RateLimiter()

        # Set rate limit info indicating we're not near the limit
        limiter.current_rate_limit = RateLimitInfo(
            remaining=100, limit=5000, reset_time=int(time.time()) + 3600
        )

        # Should still allow requests when remaining > buffer
        assert limiter.should_proceed_with_request() is True

    def test_should_proceed_when_near_limit(self):
        """Test should_proceed_with_request when rate limit is nearly exhausted."""
        limiter = RateLimiter()

        # Set rate limit info indicating we're very close to limit (within buffer)
        limiter.current_rate_limit = RateLimitInfo(
            remaining=5,  # Less than typical buffer size
            limit=5000,
            reset_time=int(time.time()) + 3600,
        )

        # Should not allow requests when remaining <= buffer
        assert limiter.should_proceed_with_request() is False

    def test_wait_if_needed_method_exists(self):
        """Test that wait_if_needed method exists."""
        limiter = RateLimiter()

        # Check that the async method exists
        assert hasattr(limiter, "wait_if_needed")
        assert callable(limiter.wait_if_needed)

    def test_calculate_retry_delay_method_exists(self):
        """Test that calculate_retry_delay method exists."""
        limiter = RateLimiter()

        # Check that the method exists
        assert hasattr(limiter, "calculate_retry_delay")
        assert callable(limiter.calculate_retry_delay)

        # Test basic delay calculation
        delay = limiter.calculate_retry_delay(0)
        assert isinstance(delay, float)
        assert delay >= 0

    def test_update_rate_limit_info_from_response(self):
        """Test updating rate limit info from HTTP response."""
        limiter = RateLimiter()

        # Mock HTTP response with rate limit headers
        mock_response = MagicMock()
        mock_response.headers = {
            "X-RateLimit-Remaining": "4000",
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Reset": str(int(time.time()) + 1800),
        }

        limiter.update_rate_limit_info(mock_response)

        assert limiter.current_rate_limit is not None
        assert limiter.current_rate_limit.remaining == 4000
        assert limiter.current_rate_limit.limit == 5000

    def test_calculate_retry_delay_basic(self):
        """Test basic retry delay calculation."""
        limiter = RateLimiter()

        delay0 = limiter.calculate_retry_delay(0)
        delay1 = limiter.calculate_retry_delay(1)
        delay2 = limiter.calculate_retry_delay(2)

        # Delays should increase exponentially
        assert delay0 <= delay1 <= delay2
        assert all(isinstance(d, float) for d in [delay0, delay1, delay2])

    def test_calculate_retry_delay_with_rate_limit(self):
        """Test retry delay calculation with rate limit info."""
        limiter = RateLimiter()

        # Set up rate limit close to buffer
        limiter.current_rate_limit = RateLimitInfo(
            remaining=5, limit=5000, reset_time=int(time.time()) + 60
        )

        delay = limiter.calculate_retry_delay(0)

        # Should return a reasonable delay
        assert isinstance(delay, float)
        assert delay >= 0
        assert delay <= 300  # Max 5 minutes as per implementation

    @pytest.mark.asyncio
    async def test_wait_if_needed_basic(self):
        """Test wait_if_needed basic functionality."""
        limiter = RateLimiter()

        # Should not raise exceptions
        start_time = time.time()
        await limiter.wait_if_needed()
        elapsed = time.time() - start_time

        # Should complete reasonably quickly (within min_delay)
        assert elapsed <= limiter.min_delay + 0.1

    @pytest.mark.asyncio
    async def test_execute_with_retry_basic(self):
        """Test execute_with_retry with successful function."""
        limiter = RateLimiter()

        async def mock_function():
            return "success"

        result = await limiter.execute_with_retry(mock_function)
        assert result == "success"


@pytest.mark.unit
class TestRateLimiterManager:
    """Test RateLimiterManager singleton."""

    def test_rate_limiter_manager_singleton(self):
        """Test that RateLimiterManager is a singleton."""
        manager1 = RateLimiterManager()
        manager2 = RateLimiterManager()

        assert manager1 is manager2

    def test_get_github_rate_limiter_function(self):
        """Test get_github_rate_limiter function."""
        limiter = get_github_rate_limiter()

        assert isinstance(limiter, RateLimiter)

        # Second call should return the same instance
        limiter2 = get_github_rate_limiter()
        assert limiter is limiter2


@pytest.mark.unit
class TestRateLimitedRequest:
    """Test rate_limited_github_request function."""

    @pytest.mark.asyncio
    async def test_rate_limited_request_success(self):
        """Test successful rate limited request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response

        with patch(
            "finos_mcp.security.rate_limit.get_github_rate_limiter"
        ) as mock_get_limiter:
            mock_limiter = MagicMock()
            mock_limiter.execute_with_retry = AsyncMock(return_value=mock_response)
            mock_get_limiter.return_value = mock_limiter

            result = await rate_limited_github_request(
                client=mock_client, method="GET", url="https://api.github.com/test"
            )

            assert result == mock_response
            mock_limiter.execute_with_retry.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limited_request_with_kwargs(self):
        """Test rate limited request with additional kwargs."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response

        with patch(
            "finos_mcp.security.rate_limit.get_github_rate_limiter"
        ) as mock_get_limiter:
            mock_limiter = MagicMock()
            mock_limiter.execute_with_retry = AsyncMock(return_value=mock_response)
            mock_get_limiter.return_value = mock_limiter

            result = await rate_limited_github_request(
                client=mock_client,
                method="POST",
                url="https://api.github.com/test",
                json={"data": "test"},
                headers={"Authorization": "token test"},
            )

            assert result == mock_response
            mock_limiter.execute_with_retry.assert_called_once()
