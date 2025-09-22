"""
Request size validation and DoS protection for the MCP server.

Provides comprehensive protection against denial of service attacks through
oversized requests, request flooding, and resource exhaustion.
"""

import json
import time
import uuid
from collections import defaultdict, deque
from threading import Lock
from typing import Any

from ..logging import get_logger

logger = get_logger(__name__)


class RequestSizeValidator:
    """Validate request sizes to prevent DoS attacks through oversized requests."""

    def __init__(
        self,
        max_tool_result_size: int = 5_000_000,  # 5MB
        max_resource_size: int = 1_000_000,  # 1MB
        max_request_params_size: int = 100_000,  # 100KB
        max_concurrent_memory_mb: int = 50,  # 50MB total concurrent
    ):
        """Initialize request size validator.

        Args:
            max_tool_result_size: Maximum size for tool results in bytes
            max_resource_size: Maximum size for individual resources in bytes
            max_request_params_size: Maximum size for request parameters in bytes
            max_concurrent_memory_mb: Maximum total concurrent memory usage in MB
        """
        self.max_tool_result_size = max_tool_result_size
        self.max_resource_size = max_resource_size
        self.max_request_params_size = max_request_params_size
        self.max_concurrent_memory = max_concurrent_memory_mb * 1_000_000

        # Track concurrent memory usage
        self._concurrent_requests: dict[str, int] = {}
        self._memory_lock = Lock()

    def validate_tool_result_size(self, result: list[Any]) -> None:
        """Validate tool result size.

        Args:
            result: Tool execution result

        Raises:
            ValueError: If result exceeds size limit
        """
        total_size = self._calculate_content_size(result)

        if total_size > self.max_tool_result_size:
            logger.warning(
                f"Tool result size exceeded limit: {total_size} bytes > {self.max_tool_result_size} bytes"
            )
            raise ValueError(f"Tool result exceeds size limit ({total_size} bytes)")

    def validate_resource_size(self, content: str | None) -> None:
        """Validate resource content size.

        Args:
            content: Resource content

        Raises:
            ValueError: If content exceeds size limit
        """
        if content is None:
            return

        size = len(content.encode("utf-8"))

        if size > self.max_resource_size:
            logger.warning(
                f"Resource size exceeded limit: {size} bytes > {self.max_resource_size} bytes"
            )
            raise ValueError(f"Resource content exceeds size limit ({size} bytes)")

    def validate_request_params_size(self, params: dict[str, Any]) -> None:
        """Validate request parameters size.

        Args:
            params: Request parameters

        Raises:
            ValueError: If parameters exceed size limit
        """
        size = self._calculate_content_size(params)

        if size > self.max_request_params_size:
            logger.warning(
                f"Request parameters size exceeded limit: {size} bytes > {self.max_request_params_size} bytes"
            )
            raise ValueError(f"Request parameters exceed size limit ({size} bytes)")

    def validate_concurrent_memory_usage(self, request_sizes: list[int]) -> None:
        """Validate that concurrent requests don't exceed memory limits.

        Args:
            request_sizes: List of sizes for concurrent requests

        Raises:
            ValueError: If total concurrent usage exceeds limit
        """
        total_concurrent = sum(request_sizes)

        if total_concurrent > self.max_concurrent_memory:
            logger.warning(
                f"Concurrent memory usage exceeded limit: {total_concurrent} bytes > {self.max_concurrent_memory} bytes"
            )
            raise ValueError(
                f"Total concurrent memory usage exceeds limit ({total_concurrent} bytes)"
            )

    def start_request_tracking(self, request_id: str, size: int) -> None:
        """Start tracking memory usage for a request.

        Args:
            request_id: Unique request identifier
            size: Memory size being used by the request
        """
        with self._memory_lock:
            self._concurrent_requests[request_id] = size

    def complete_request_tracking(self, request_id: str) -> None:
        """Complete tracking for a request.

        Args:
            request_id: Request identifier to stop tracking
        """
        with self._memory_lock:
            self._concurrent_requests.pop(request_id, None)

    def get_current_memory_usage(self) -> int:
        """Get current total memory usage across all tracked requests."""
        with self._memory_lock:
            return sum(self._concurrent_requests.values())

    def _calculate_content_size(self, content: Any) -> int:
        """Calculate the size of content in bytes.

        Args:
            content: Content to measure

        Returns:
            Size in bytes
        """
        try:
            if content is None:
                return 0

            if isinstance(content, (str, bytes)):
                return len(
                    content.encode("utf-8") if isinstance(content, str) else content
                )

            if isinstance(content, (list, tuple)):
                return sum(self._calculate_content_size(item) for item in content)

            if isinstance(content, dict):
                total = 0
                for key, value in content.items():
                    total += self._calculate_content_size(key)
                    total += self._calculate_content_size(value)
                return total

            # For other types, serialize to JSON to get approximate size
            return len(json.dumps(content, default=str).encode("utf-8"))

        except Exception as e:
            logger.warning(f"Failed to calculate content size: {e}")
            # Return a conservative estimate
            return len(str(content).encode("utf-8"))


class DoSProtector:
    """Protect against denial of service attacks through request flooding and resource exhaustion."""

    def __init__(
        self,
        max_requests_per_minute: int = 60,
        max_concurrent_requests: int = 10,
        request_timeout_seconds: int = 30,
        cleanup_interval_seconds: int = 60,
    ):
        """Initialize DoS protector.

        Args:
            max_requests_per_minute: Maximum requests per client per minute
            max_concurrent_requests: Maximum concurrent requests per client
            request_timeout_seconds: Timeout for individual requests
            cleanup_interval_seconds: How often to clean up old tracking data
        """
        self.max_requests_per_minute = max_requests_per_minute
        self.max_concurrent_requests = max_concurrent_requests
        self.request_timeout = request_timeout_seconds
        self.cleanup_interval = cleanup_interval_seconds

        # Rate limiting tracking
        self._request_history: dict[str, deque] = defaultdict(deque)
        self._concurrent_requests: dict[str, dict[str, float]] = defaultdict(dict)
        self._last_cleanup = time.time()
        self._lock = Lock()

    def check_rate_limit(self, client_id: str) -> bool:
        """Check if client is within rate limits.

        Args:
            client_id: Client identifier

        Returns:
            True if request is allowed, False if rate limited
        """
        current_time = self._get_current_time()

        with self._lock:
            # Clean up old requests
            self._cleanup_old_requests(client_id, current_time)

            # Check if client has exceeded rate limit
            request_count = len(self._request_history[client_id])

            if request_count >= self.max_requests_per_minute:
                logger.warning(
                    f"Rate limit exceeded for client {client_id}: {request_count} requests in last minute"
                )
                return False

            # Add current request to history
            self._request_history[client_id].append(current_time)
            return True

    def start_request(self, client_id: str) -> str:
        """Start tracking a concurrent request.

        Args:
            client_id: Client identifier

        Returns:
            Request ID for tracking

        Raises:
            ValueError: If client has too many concurrent requests
        """
        current_time = self._get_current_time()
        request_id = str(uuid.uuid4())

        with self._lock:
            # Clean up timed out requests
            self._cleanup_timed_out_requests(client_id, current_time)

            # Check concurrent request limit
            concurrent_count = len(self._concurrent_requests[client_id])

            if concurrent_count >= self.max_concurrent_requests:
                logger.warning(
                    f"Concurrent request limit exceeded for client {client_id}: {concurrent_count} requests"
                )
                raise ValueError(
                    f"Too many concurrent requests ({concurrent_count}/{self.max_concurrent_requests})"
                )

            # Track the new request
            self._concurrent_requests[client_id][request_id] = current_time
            logger.debug(f"Started request {request_id} for client {client_id}")

            return request_id

    def complete_request(self, client_id: str, request_id: str) -> None:
        """Complete tracking for a request.

        Args:
            client_id: Client identifier
            request_id: Request identifier
        """
        with self._lock:
            if client_id in self._concurrent_requests:
                self._concurrent_requests[client_id].pop(request_id, None)
                logger.debug(f"Completed request {request_id} for client {client_id}")

    def get_client_stats(self, client_id: str) -> dict[str, Any]:
        """Get statistics for a client.

        Args:
            client_id: Client identifier

        Returns:
            Dictionary with client statistics
        """
        current_time = self._get_current_time()

        with self._lock:
            self._cleanup_old_requests(client_id, current_time)
            self._cleanup_timed_out_requests(client_id, current_time)

            return {
                "requests_last_minute": len(self._request_history[client_id]),
                "concurrent_requests": len(self._concurrent_requests[client_id]),
                "rate_limit": self.max_requests_per_minute,
                "concurrent_limit": self.max_concurrent_requests,
            }

    def _cleanup_old_requests(self, client_id: str, current_time: float) -> None:
        """Clean up request history older than 1 minute."""
        cutoff_time = current_time - 60  # 1 minute ago

        history = self._request_history[client_id]
        while history and history[0] < cutoff_time:
            history.popleft()

    def _cleanup_timed_out_requests(self, client_id: str, current_time: float) -> None:
        """Clean up requests that have timed out."""
        if client_id not in self._concurrent_requests:
            return

        timed_out = []
        for request_id, start_time in self._concurrent_requests[client_id].items():
            if current_time - start_time > self.request_timeout:
                timed_out.append(request_id)

        for request_id in timed_out:
            self._concurrent_requests[client_id].pop(request_id, None)
            logger.warning(f"Request {request_id} for client {client_id} timed out")

    def _is_request_timed_out(self, client_id: str, request_id: str) -> bool:
        """Check if a specific request has timed out."""
        if client_id not in self._concurrent_requests:
            return False

        if request_id not in self._concurrent_requests[client_id]:
            return False

        start_time = self._concurrent_requests[client_id][request_id]
        return (self._get_current_time() - start_time) > self.request_timeout

    def _get_current_time(self) -> float:
        """Get current time (mockable for testing)."""
        return time.time()

    def periodic_cleanup(self) -> None:
        """Perform periodic cleanup of old tracking data."""
        current_time = self._get_current_time()

        if current_time - self._last_cleanup < self.cleanup_interval:
            return

        with self._lock:
            # Clean up all clients
            for client_id in list(self._request_history.keys()):
                self._cleanup_old_requests(client_id, current_time)
                self._cleanup_timed_out_requests(client_id, current_time)

                # Remove empty client entries
                if (
                    not self._request_history[client_id]
                    and not self._concurrent_requests[client_id]
                ):
                    del self._request_history[client_id]
                    del self._concurrent_requests[client_id]

            self._last_cleanup = current_time


# Global instances for easy access
request_size_validator = RequestSizeValidator()
dos_protector = DoSProtector()
