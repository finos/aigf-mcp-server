"""Rate limiting utilities for GitHub API and general request management.

Copyright 2024 Hugo Calderon

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Implements intelligent rate limiting with exponential backoff, respect for
GitHub's rate limit headers, and graceful degradation when limits are approached.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Optional, TypeVar

import httpx

from ..config import get_settings
from ..logging import get_logger

T = TypeVar("T")

logger = get_logger("rate_limiter")


@dataclass
class RateLimitInfo:
    """Rate limit information from GitHub API."""

    remaining: int
    limit: int
    reset_time: int
    retry_after: int | None = None


@dataclass
class RateLimiter:
    """Intelligent rate limiter for GitHub API requests.

    Features:
    - Respects GitHub's rate limit headers
    - Exponential backoff for retries
    - Configurable delays and buffers
    - Automatic fallback when approaching limits
    """

    # Configuration from settings
    min_delay: float = field(
        default_factory=lambda: get_settings().github_api_delay_seconds
    )
    max_retries: int = field(
        default_factory=lambda: get_settings().github_api_max_retries
    )
    backoff_factor: float = field(
        default_factory=lambda: get_settings().github_api_backoff_factor
    )
    rate_limit_buffer: int = field(
        default_factory=lambda: get_settings().github_api_rate_limit_buffer
    )

    # Internal state
    last_request_time: float = field(default_factory=time.time)
    current_rate_limit: RateLimitInfo | None = None
    consecutive_failures: int = 0

    def __post_init__(self) -> None:
        """Initialize rate limiter with current settings."""
        settings = get_settings()
        self.min_delay = settings.github_api_delay_seconds
        self.max_retries = settings.github_api_max_retries
        self.backoff_factor = settings.github_api_backoff_factor
        self.rate_limit_buffer = settings.github_api_rate_limit_buffer

    async def wait_if_needed(self) -> None:
        """Wait if minimum delay hasn't passed since last request."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_delay:
            delay = self.min_delay - time_since_last
            logger.debug("Rate limiting: waiting %.2fs", delay)
            await asyncio.sleep(delay)

        self.last_request_time = time.time()

    def should_proceed_with_request(self) -> bool:
        """Check if we should proceed with a request based on current rate limits.

        Returns:
            False if we're too close to rate limit and should wait

        """
        if not self.current_rate_limit:
            return True

        if self.current_rate_limit.remaining <= self.rate_limit_buffer:
            logger.warning(
                "Approaching GitHub API rate limit: %s remaining, buffer is %s",
                self.current_rate_limit.remaining,
                self.rate_limit_buffer,
            )
            return False

        return True

    def update_rate_limit_info(self, response: httpx.Response) -> None:
        """Update rate limit information from GitHub API response headers."""
        try:
            remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
            limit = int(response.headers.get("X-RateLimit-Limit", 5000))
            reset_time = int(
                response.headers.get("X-RateLimit-Reset", time.time() + 3600)
            )
            retry_after = None

            if "Retry-After" in response.headers:
                retry_after = int(response.headers["Retry-After"])

            self.current_rate_limit = RateLimitInfo(
                remaining=remaining,
                limit=limit,
                reset_time=reset_time,
                retry_after=retry_after,
            )

            logger.debug(
                "Updated rate limit: %s/%s remaining, resets at %s",
                remaining,
                limit,
                reset_time,
                extra={
                    "rate_limit_remaining": remaining,
                    "rate_limit_limit": limit,
                    "rate_limit_reset": reset_time,
                },
            )

        except (ValueError, TypeError) as e:
            logger.warning("Failed to parse rate limit headers: %s", e)

    def calculate_retry_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt using exponential backoff.

        Args:
            attempt: Current retry attempt (0-based)

        Returns:
            Delay in seconds

        """
        # Base delay starts at min_delay and increases exponentially
        base_delay = self.min_delay * (self.backoff_factor**attempt)

        # If we have rate limit info and are close to limit, add extra delay
        if (
            self.current_rate_limit
            and self.current_rate_limit.remaining <= self.rate_limit_buffer
        ):
            # If we have retry_after, use that
            if self.current_rate_limit.retry_after:
                return float(self.current_rate_limit.retry_after)

            # Otherwise, wait until rate limit resets
            reset_delay = max(0, self.current_rate_limit.reset_time - time.time())
            if reset_delay > 0 and reset_delay < 3600:  # Don't wait more than 1 hour
                return reset_delay

        # Cap the delay at a reasonable maximum
        return min(base_delay, 300)  # Max 5 minutes

    async def execute_with_retry(
        self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
    ) -> T:
        """Execute a function with retry logic and rate limiting.

        Args:
            func: Async function to execute
            *args: Arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result of the function call

        Raises:
            Last exception if all retries failed

        """
        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                # Wait for rate limiting before request
                await self.wait_if_needed()

                # Check if we should proceed (not too close to rate limit)
                if not self.should_proceed_with_request():
                    if attempt == 0:  # Only log on first attempt
                        logger.warning(
                            "Skipping GitHub API request due to rate limit proximity"
                        )
                    # Create a mock request for HTTPStatusError
                    mock_request = httpx.Request(
                        "GET", "https://api.github.com/rate_limit"
                    )
                    mock_response = httpx.Response(429, request=mock_request)
                    raise httpx.HTTPStatusError(
                        "Rate limit proximity",
                        request=mock_request,
                        response=mock_response,
                    )

                # Execute the function
                result = await func(*args, **kwargs)

                # Reset consecutive failures on success
                self.consecutive_failures = 0

                return result

            except httpx.HTTPStatusError as e:
                last_exception = e

                # Update rate limit info if available
                if hasattr(e, "response") and e.response:
                    self.update_rate_limit_info(e.response)

                # Handle specific HTTP errors
                if e.response and e.response.status_code == 403:
                    # Rate limit exceeded
                    self.consecutive_failures += 1
                    if attempt < self.max_retries:
                        delay = self.calculate_retry_delay(attempt)
                        logger.warning(
                            "GitHub API rate limit hit, retrying in %.1fs (attempt %s/%s)",
                            delay,
                            attempt + 1,
                            self.max_retries + 1,
                        )
                        await asyncio.sleep(delay)
                        continue
                    logger.error("GitHub API rate limit exceeded, no more retries")
                    break

                elif e.response and e.response.status_code == 429:
                    # Too many requests
                    self.consecutive_failures += 1
                    if attempt < self.max_retries:
                        delay = self.calculate_retry_delay(attempt)
                        logger.warning(
                            "GitHub API too many requests, retrying in %.1fs (attempt %s/%s)",
                            delay,
                            attempt + 1,
                            self.max_retries + 1,
                        )
                        await asyncio.sleep(delay)
                        continue
                    logger.error("GitHub API too many requests, no more retries")
                    break

                else:
                    # Other HTTP errors - don't retry
                    break

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exception = e
                self.consecutive_failures += 1

                if attempt < self.max_retries:
                    delay = self.calculate_retry_delay(attempt)
                    logger.warning(
                        "GitHub API connection error, retrying in %.1fs (attempt %s/%s): %s",
                        delay,
                        attempt + 1,
                        self.max_retries + 1,
                        e,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.error(
                    "GitHub API connection failed after %s retries: %s",
                    self.max_retries,
                    e,
                )
                break

            except (
                ValueError,
                TypeError,
                RuntimeError,
                asyncio.CancelledError,
                asyncio.TimeoutError,
            ) as e:
                # Unexpected errors - don't retry
                last_exception = Exception(str(e))
                logger.error("Unexpected error in rate-limited execution: %s", e)
                break

        # All retries exhausted
        if last_exception:
            raise last_exception

        # This should never happen, but satisfy MyPy
        raise RuntimeError("Function completed without success or exception")


class RateLimiterManager:
    """Singleton manager for the global GitHub API rate limiter instance."""

    _instance: Optional["RateLimiterManager"] = None
    _github_rate_limiter: RateLimiter | None = None

    def __new__(cls) -> "RateLimiterManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_github_rate_limiter(self) -> RateLimiter:
        """Get the global GitHub API rate limiter instance."""
        if self._github_rate_limiter is None:
            self._github_rate_limiter = RateLimiter()
        return self._github_rate_limiter


# Global rate limiter manager instance
_rate_limiter_manager = RateLimiterManager()


def get_github_rate_limiter() -> RateLimiter:
    """Get the global GitHub API rate limiter instance."""
    return _rate_limiter_manager.get_github_rate_limiter()


async def rate_limited_github_request(
    client: httpx.AsyncClient, method: str, url: str, **kwargs: Any
) -> httpx.Response:
    """Make a rate-limited GitHub API request.

    Args:
        client: HTTP client to use
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        **kwargs: Additional arguments for the request

    Returns:
        HTTP response

    Raises:
        httpx.HTTPStatusError: On HTTP errors
        httpx.TimeoutException: On timeouts

    """
    limiter = get_github_rate_limiter()

    async def make_request() -> httpx.Response:
        response = await client.request(method, url, **kwargs)

        # Update rate limit info from response
        limiter.update_rate_limit_info(response)

        # Raise for HTTP errors
        response.raise_for_status()

        return response

    return await limiter.execute_with_retry(make_request)
