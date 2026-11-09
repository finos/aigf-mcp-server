# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""
Request size validation and DoS protection for the MCP server.

Provides comprehensive protection against denial of service attacks through
oversized requests, request flooding, and resource exhaustion.

This module holds the state and the limit checks only. They are enforced at the MCP
protocol boundary by security.dos_middleware; adding a check here without a call site
there produces a control that looks tested and protects nothing (issue #23).

Per-request memory accounting was removed deliberately: nothing populated it, it
duplicates the limits the OS and container runtime already impose, and wiring it would
have meant threading a size estimate through every call site for no added protection.
"""

import asyncio
import time
import uuid
from collections import defaultdict, deque
from typing import Any

from ..logging import get_logger

logger = get_logger(__name__)


class RequestSizeValidator:
    """Validate request sizes to prevent DoS attacks through oversized requests."""

    def __init__(
        self,
        max_tool_result_size: int = 5_000_000,  # 5MB
        max_resource_size: int = 1_000_000,  # 1MB
    ):
        """Initialize request size validator.

        Request parameters have no limit here: each one is bounded by the
        ``Field`` its tool, resource or prompt declares, and fastmcp refuses a
        value over that bound before the function runs (#322).

        Args:
            max_tool_result_size: Maximum size for tool results in bytes
            max_resource_size: Maximum size for individual resources in bytes
        """
        self.max_tool_result_size = max_tool_result_size
        self.max_resource_size = max_resource_size

    def validate_tool_result_size(self, result: list[Any]) -> None:
        """Validate tool result size.

        Callers must pass values this class can measure at full size - str, bytes,
        list or dict. Anything else is truncated to 1000 bytes by
        _calculate_content_size, which would silently disable this limit. See
        security.dos_middleware._measurable_tool_payload.

        Args:
            result: Tool execution result

        Raises:
            ValueError: If result exceeds size limit
        """
        total_size = self._calculate_content_size(result)

        if total_size > self.max_tool_result_size:
            logger.warning(
                "Tool result size exceeded limit: %d bytes > %d bytes",
                total_size,
                self.max_tool_result_size,
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
                "Resource size exceeded limit: %d bytes > %d bytes",
                size,
                self.max_resource_size,
            )
            raise ValueError(f"Resource content exceeds size limit ({size} bytes)")

    def _calculate_content_size(self, content: Any) -> int:
        """Calculate the size of content in bytes with protection against infinite recursion.

        Args:
            content: Content to measure

        Returns:
            Size in bytes
        """
        try:
            # Use iterative approach to prevent recursion errors
            total_size = 0
            stack = [content]
            visited = set()  # Track visited objects to prevent circular references
            max_items = 10000  # Limit to prevent DoS through massive structures
            items_processed = 0

            while stack and items_processed < max_items:
                current = stack.pop()
                items_processed += 1

                # Skip None values
                if current is None:
                    continue

                # Get object ID for circular reference detection
                obj_id = id(current)
                if obj_id in visited:
                    continue  # Skip already processed objects
                visited.add(obj_id)

                # Handle different types
                if isinstance(current, str | bytes):
                    total_size += len(
                        current.encode("utf-8") if isinstance(current, str) else current
                    )
                elif isinstance(current, list | tuple):
                    # Add items to stack for processing (limit depth)
                    if len(stack) < 1000:  # Prevent stack overflow
                        stack.extend(current)
                    else:
                        # Fallback: estimate size without deep traversal
                        total_size += len(str(current)[:1000].encode("utf-8"))
                elif isinstance(current, dict):
                    # Add keys and values to stack for processing (limit depth)
                    if len(stack) < 1000:  # Prevent stack overflow
                        for key, value in current.items():
                            stack.append(key)
                            stack.append(value)
                    else:
                        # Fallback: estimate size without deep traversal
                        total_size += len(str(current)[:1000].encode("utf-8"))
                else:
                    # For other types, get string representation size (limited)
                    str_repr = str(current)[:1000]  # Limit string length
                    total_size += len(str_repr.encode("utf-8"))

            # If we hit the item limit, add a conservative estimate for remaining
            if items_processed >= max_items and stack:
                logger.warning(
                    "Content structure too large, using conservative estimate"
                )
                total_size += (
                    len(stack) * 100
                )  # Conservative estimate per remaining item

            return total_size

        except (RecursionError, MemoryError) as e:
            logger.warning("Recursion or memory error calculating content size: %s", e)
            # Very conservative fallback
            return 1000000  # 1MB conservative estimate

        except Exception as e:
            logger.warning("Failed to calculate content size: %s", e)
            # Return a conservative estimate
            try:
                return len(str(content)[:1000].encode("utf-8"))
            except Exception:
                return 1000  # Minimal fallback


class DoSProtector:
    """Protect against denial of service attacks through request flooding and resource exhaustion."""

    def __init__(
        self,
        max_requests_per_minute: int = 60,
        max_concurrent_requests: int = 10,
        cleanup_interval_seconds: int = 60,
        max_tracked_clients: int = 10000,
    ):
        """Initialize DoS protector.

        A concurrency slot is held until the call that took it returns; the
        middleware releases it in ``finally``. There is no expiry: one gave a
        running call's slot away after a timeout, so the limit bounded only
        fast calls (#288).

        Args:
            max_requests_per_minute: Maximum requests per client per minute
            max_concurrent_requests: Maximum concurrent requests per client
            cleanup_interval_seconds: How often to clean up old tracking data
            max_tracked_clients: Upper bound on distinct client keys held in memory
        """
        self.max_requests_per_minute = max_requests_per_minute
        self.max_concurrent_requests = max_concurrent_requests
        self.cleanup_interval = cleanup_interval_seconds
        self.max_tracked_clients = max_tracked_clients

        # Rate limiting tracking
        # Each deque holds request timestamps (time.time() floats) for one client.
        self._request_history: dict[str, deque[float]] = defaultdict(deque)
        self._concurrent_requests: dict[str, dict[str, float]] = defaultdict(dict)
        self._last_cleanup = time.time()
        self._lock = asyncio.Lock()

    async def check_rate_limit(self, client_id: str) -> bool:
        """Check if client is within rate limits.

        Args:
            client_id: Client identifier

        Returns:
            True if request is allowed, False if rate limited
        """
        current_time = self._get_current_time()

        async with self._lock:
            # Must run before the defaultdict access below, which would otherwise
            # create the entry and hide the fact that this client is new.
            if client_id not in self._request_history:
                self._evict_if_at_capacity(current_time)

            # Clean up old requests
            self._cleanup_old_requests(client_id, current_time)

            # Check if client has exceeded rate limit
            request_count = len(self._request_history[client_id])

            if request_count >= self.max_requests_per_minute:
                logger.warning(
                    "Rate limit exceeded for client %s: %d requests in last minute",
                    client_id,
                    request_count,
                )
                return False

            # Add current request to history
            self._request_history[client_id].append(current_time)
            return True

    async def start_request(self, client_id: str) -> str:
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

        async with self._lock:
            # Check concurrent request limit
            concurrent_count = len(self._concurrent_requests[client_id])

            if concurrent_count >= self.max_concurrent_requests:
                logger.warning(
                    "Concurrent request limit exceeded for client %s: %d requests",
                    client_id,
                    concurrent_count,
                )
                raise ValueError(
                    f"Too many concurrent requests ({concurrent_count}/{self.max_concurrent_requests})"
                )

            # Track the new request
            self._concurrent_requests[client_id][request_id] = current_time
            logger.debug("Started request %s for client %s", request_id, client_id)

            return request_id

    async def complete_request(self, client_id: str, request_id: str) -> None:
        """Complete tracking for a request.

        Args:
            client_id: Client identifier
            request_id: Request identifier
        """
        async with self._lock:
            if client_id in self._concurrent_requests:
                self._concurrent_requests[client_id].pop(request_id, None)
                logger.debug(
                    "Completed request %s for client %s", request_id, client_id
                )

    def _evict_if_at_capacity(self, current_time: float) -> None:
        """Make room for a new client key, bounding tracked-client memory.

        Client keys are derived from caller identity, so a spray of requests from
        many distinct sources would otherwise grow the tracking tables without
        limit between the 60s periodic_cleanup passes.

        Expired entries are dropped first. If that frees nothing, the client with
        the fewest requests in the window is evicted, ties broken by whichever
        was least recently active.

        Evicting by lowest request count is the security-relevant choice, and the
        reason is not obvious. Evicting the least recently active instead looks
        reasonable but is exploitable: a client that has just burst up to its
        limit has an older last-request timestamp than a spray of fresh keys, so
        an attacker at the limit could spray max_tracked_clients keys, evict
        their own entry, and come back with a clean budget. Ordering by request
        count makes the entry nearest its limit the last one evicted, so
        displacing it costs the attacker more requests than the limit it buys.
        """
        if len(self._request_history) < self.max_tracked_clients:
            return

        for tracked_id in list(self._request_history.keys()):
            self._cleanup_old_requests(tracked_id, current_time)
            if not self._request_history[
                tracked_id
            ] and not self._concurrent_requests.get(tracked_id):
                del self._request_history[tracked_id]
                self._concurrent_requests.pop(tracked_id, None)

        if len(self._request_history) < self.max_tracked_clients:
            return

        def eviction_rank(tracked_id: str) -> tuple[int, float]:
            history = self._request_history[tracked_id]
            return (len(history), history[-1] if history else 0.0)

        evicted_id = min(self._request_history, key=eviction_rank)
        logger.warning(
            "Client tracking table full (%d entries); evicting least active client %s",
            self.max_tracked_clients,
            evicted_id,
        )
        del self._request_history[evicted_id]
        self._concurrent_requests.pop(evicted_id, None)

    def _cleanup_old_requests(self, client_id: str, current_time: float) -> None:
        """Clean up request history older than 1 minute."""
        cutoff_time = current_time - 60  # 1 minute ago

        history = self._request_history[client_id]
        while history and history[0] < cutoff_time:
            history.popleft()

    def _get_current_time(self) -> float:
        """Get current time (mockable for testing)."""
        return time.time()

    async def periodic_cleanup(self) -> None:
        """Perform periodic cleanup of old tracking data."""
        current_time = self._get_current_time()

        if current_time - self._last_cleanup < self.cleanup_interval:
            return

        async with self._lock:
            # Clean up all clients
            for client_id in list(self._request_history.keys()):
                self._cleanup_old_requests(client_id, current_time)

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
