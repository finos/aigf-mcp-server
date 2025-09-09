"""
Quick coverage boost tests for security rate limit module.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from finos_mcp.security.rate_limit import RateLimiter, RateLimiterManager, RateLimitInfo


@pytest.mark.unit
class TestRateLimiterCoverage:
    """Quick tests to boost rate limiter coverage."""

    def test_rate_limit_info_creation(self):
        """Test RateLimitInfo initialization."""
        reset_time = int(time.time() + 3600)
        info = RateLimitInfo(
            remaining=100, limit=5000, reset_time=reset_time, retry_after=30
        )

        assert info.remaining == 100
        assert info.limit == 5000
        assert info.reset_time == reset_time
        assert info.retry_after == 30

    def test_rate_limit_info_without_retry_after(self):
        """Test RateLimitInfo without retry_after."""
        info = RateLimitInfo(
            remaining=1000, limit=5000, reset_time=int(time.time() + 3600)
        )

        assert info.remaining == 1000
        assert info.retry_after is None

    def test_rate_limiter_initialization(self):
        """Test RateLimiter initialization."""
        limiter = RateLimiter()

        # Check defaults are set
        assert limiter.min_delay >= 0
        assert limiter.max_retries > 0
        assert limiter.backoff_factor > 0
        assert limiter.rate_limit_buffer >= 0
        assert limiter.last_request_time > 0
        assert limiter.consecutive_failures == 0

    @patch("finos_mcp.security.rate_limit.get_settings")
    def test_rate_limiter_settings_integration(self, mock_get_settings):
        """Test RateLimiter uses settings correctly."""
        mock_settings = MagicMock()
        mock_settings.github_api_delay_seconds = 0.5
        mock_settings.github_api_max_retries = 5
        mock_settings.github_api_backoff_factor = 2.0
        mock_settings.github_api_rate_limit_buffer = 10
        mock_get_settings.return_value = mock_settings

        limiter = RateLimiter()

        assert limiter.min_delay == 0.5
        assert limiter.max_retries == 5
        assert limiter.backoff_factor == 2.0
        assert limiter.rate_limit_buffer == 10

    def test_rate_limiter_should_proceed_no_rate_limit(self):
        """Test should_proceed_with_request when no rate limit info."""
        limiter = RateLimiter()
        limiter.current_rate_limit = None

        # Without rate limit info, should proceed
        result = limiter.should_proceed_with_request()
        assert result is True

    def test_rate_limiter_should_proceed_plenty_remaining(self):
        """Test should_proceed_with_request with plenty of requests remaining."""
        limiter = RateLimiter(rate_limit_buffer=10)
        limiter.current_rate_limit = RateLimitInfo(
            remaining=1000, limit=5000, reset_time=int(time.time() + 3600)
        )

        result = limiter.should_proceed_with_request()
        assert result is True

    @patch("finos_mcp.security.rate_limit.get_settings")
    def test_rate_limiter_should_proceed_low_remaining(self, mock_get_settings):
        """Test should_proceed_with_request when near rate limit."""
        mock_settings = MagicMock()
        mock_settings.github_api_delay_seconds = 1.0
        mock_settings.github_api_max_retries = 3
        mock_settings.github_api_backoff_factor = 2.0
        mock_settings.github_api_rate_limit_buffer = 50
        mock_get_settings.return_value = mock_settings

        limiter = RateLimiter()
        limiter.current_rate_limit = RateLimitInfo(
            remaining=30,  # Below buffer of 50
            limit=5000,
            reset_time=int(time.time() + 3600),
        )

        result = limiter.should_proceed_with_request()
        assert result is False

    @pytest.mark.asyncio
    async def test_rate_limiter_wait_if_needed_no_wait(self):
        """Test wait_if_needed when no wait is needed."""
        limiter = RateLimiter(min_delay=0.1)
        limiter.last_request_time = time.time() - 1.0  # Long ago

        start_time = time.time()
        await limiter.wait_if_needed()
        elapsed = time.time() - start_time

        # Should be very quick since enough time has passed
        assert elapsed < 0.05

    @pytest.mark.asyncio
    async def test_rate_limiter_wait_if_needed_with_delay(self):
        """Test wait_if_needed when delay is needed."""
        limiter = RateLimiter(min_delay=0.1)
        limiter.last_request_time = time.time()  # Just now

        start_time = time.time()
        await limiter.wait_if_needed()
        elapsed = time.time() - start_time

        # Should have waited at least min_delay
        assert elapsed >= 0.09  # Allow small timing variation

    def test_rate_limiter_manager_singleton(self):
        """Test RateLimiterManager singleton pattern."""
        manager1 = RateLimiterManager()
        manager2 = RateLimiterManager()

        assert manager1 is manager2


@pytest.mark.unit
class TestRateLimitUtilityFunctions:
    """Test rate limit utility functions."""

    def test_get_github_rate_limiter(self):
        """Test global rate limiter getter."""
        from finos_mcp.security.rate_limit import get_github_rate_limiter

        limiter1 = get_github_rate_limiter()
        limiter2 = get_github_rate_limiter()

        assert isinstance(limiter1, RateLimiter)
        assert limiter1 is limiter2  # Should return same instance

    @pytest.mark.asyncio
    async def test_rate_limited_github_request_success(self):
        """Test successful rate-limited GitHub request."""

        from finos_mcp.security.rate_limit import rate_limited_github_request

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.headers = {
            "X-RateLimit-Remaining": "4999",
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Reset": str(int(time.time() + 3600)),
        }
        mock_response.raise_for_status.return_value = None
        mock_client.request.return_value = mock_response

        response = await rate_limited_github_request(
            mock_client, "GET", "https://api.github.com/user"
        )

        assert response == mock_response
        mock_client.request.assert_called_once_with(
            "GET", "https://api.github.com/user"
        )
        mock_response.raise_for_status.assert_called_once()


@pytest.mark.unit
class TestRateLimiterAdvanced:
    """Advanced rate limiter functionality tests."""

    def test_update_rate_limit_info_valid_headers(self):
        """Test updating rate limit info from response headers."""

        limiter = RateLimiter()

        # Mock response with rate limit headers
        mock_response = MagicMock()
        mock_response.headers = {
            "X-RateLimit-Remaining": "4500",
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Reset": str(int(time.time() + 3600)),
            "Retry-After": "60",
        }

        limiter.update_rate_limit_info(mock_response)

        assert limiter.current_rate_limit is not None
        assert limiter.current_rate_limit.remaining == 4500
        assert limiter.current_rate_limit.limit == 5000
        assert limiter.current_rate_limit.retry_after == 60

    def test_update_rate_limit_info_invalid_headers(self):
        """Test handling invalid rate limit headers."""
        limiter = RateLimiter()

        mock_response = MagicMock()
        mock_response.headers = {
            "X-RateLimit-Remaining": "invalid",
            "X-RateLimit-Limit": "not_a_number",
        }

        # Should not crash on invalid headers
        limiter.update_rate_limit_info(mock_response)

        # Rate limit info should remain None or have defaults
        assert (
            limiter.current_rate_limit is None
            or limiter.current_rate_limit.remaining >= 0
        )

    def test_calculate_retry_delay_exponential(self):
        """Test exponential backoff calculation."""
        limiter = RateLimiter(min_delay=1.0, backoff_factor=2.0)

        delay_0 = limiter.calculate_retry_delay(0)
        delay_1 = limiter.calculate_retry_delay(1)
        delay_2 = limiter.calculate_retry_delay(2)

        assert delay_0 == 1.0  # 1.0 * 2^0
        assert delay_1 == 2.0  # 1.0 * 2^1
        assert delay_2 == 4.0  # 1.0 * 2^2

    @patch("finos_mcp.security.rate_limit.get_settings")
    def test_calculate_retry_delay_with_retry_after(self, mock_get_settings):
        """Test retry delay with Retry-After header."""
        mock_settings = MagicMock()
        mock_settings.github_api_delay_seconds = 1.0
        mock_settings.github_api_max_retries = 3
        mock_settings.github_api_backoff_factor = 2.0
        mock_settings.github_api_rate_limit_buffer = 100
        mock_get_settings.return_value = mock_settings

        limiter = RateLimiter()
        limiter.current_rate_limit = RateLimitInfo(
            remaining=50,  # Below buffer of 100
            limit=5000,
            reset_time=int(time.time() + 3600),
            retry_after=120,
        )

        delay = limiter.calculate_retry_delay(0)
        assert delay == 120.0  # Should use retry_after

    @patch("finos_mcp.security.rate_limit.get_settings")
    def test_calculate_retry_delay_max_cap(self, mock_get_settings):
        """Test retry delay maximum cap."""
        mock_settings = MagicMock()
        mock_settings.github_api_delay_seconds = 1.0
        mock_settings.github_api_max_retries = 3
        mock_settings.github_api_backoff_factor = 10.0  # High backoff factor
        mock_settings.github_api_rate_limit_buffer = 10
        mock_get_settings.return_value = mock_settings

        limiter = RateLimiter()

        # Very high attempt should be capped at 300 seconds
        delay = limiter.calculate_retry_delay(10)
        assert delay <= 300

    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self):
        """Test successful execution with retry logic."""
        limiter = RateLimiter(min_delay=0.01)  # Fast for testing

        async def mock_func():
            return "success"

        result = await limiter.execute_with_retry(mock_func)
        assert result == "success"
        assert limiter.consecutive_failures == 0

    @pytest.mark.asyncio
    @patch("finos_mcp.security.rate_limit.get_settings")
    async def test_execute_with_retry_http_403_retry(self, mock_get_settings):
        """Test retry on HTTP 403 (rate limit) error."""
        mock_settings = MagicMock()
        mock_settings.github_api_delay_seconds = 0.01  # Very fast for testing
        mock_settings.github_api_max_retries = 2  # Allow more retries
        mock_settings.github_api_backoff_factor = 1.0
        mock_settings.github_api_rate_limit_buffer = 10
        mock_get_settings.return_value = mock_settings

        limiter = RateLimiter()

        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call fails with 403 but has sufficient remaining requests
                mock_response = MagicMock()
                mock_response.status_code = 403
                mock_response.headers = {"X-RateLimit-Remaining": "100"}  # Above buffer
                raise httpx.HTTPStatusError(
                    "Rate limited", request=None, response=mock_response
                )
            return "success"

        # This test would take too long with real delays, so let's simplify it
        with patch.object(
            limiter, "calculate_retry_delay", return_value=0.001
        ):  # Very short delay
            result = await limiter.execute_with_retry(mock_func)
            assert result == "success"
            assert call_count == 2  # Should have retried once
