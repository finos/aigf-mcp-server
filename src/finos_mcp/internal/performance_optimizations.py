"""
Performance optimization patterns for MCP server.
Request coalescing, background tasks, and smart caching.
"""

import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class CacheEntry:
    """Smart cache entry with TTL support."""

    value: Any
    expires_at: float
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return time.time() > self.expires_at

    def touch(self):
        """Update access statistics."""
        self.last_accessed = time.time()
        self.access_count += 1


class SmartCache:
    """Smart cache with TTL and LRU eviction."""

    def __init__(self, max_size: int = 1000, default_ttl: float = 300.0):
        """Initialize smart cache."""
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = {"hits": 0, "misses": 0}

    def get(self, key: str) -> Any | None:
        """Get value from cache."""
        if key not in self._cache:
            self._stats["misses"] += 1
            return None

        entry = self._cache[key]

        if entry.is_expired():
            del self._cache[key]
            self._stats["misses"] += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        entry.touch()
        self._stats["hits"] += 1
        return entry.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Set value in cache with optional TTL."""
        expires_at = time.time() + (ttl if ttl is not None else self.default_ttl)

        if key in self._cache:
            # Update existing entry
            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)
            self._cache.move_to_end(key)
        else:
            # Add new entry
            if len(self._cache) >= self.max_size:
                # Remove least recently used
                self._cache.popitem(last=False)

            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)

    async def warm(self, key: str, warmer: Callable) -> None:
        """Warm cache with computed value."""
        if key not in self._cache:
            value = await warmer(key)
            self.set(key, value)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0.0

        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": hit_rate,
            "entries": len(self._cache),
            "max_size": self.max_size
        }

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._stats = {"hits": 0, "misses": 0}


class RequestCoalescer:
    """Request coalescing to reduce duplicate work."""

    def __init__(self, max_batch_size: int = 10, batch_timeout: float = 0.1):
        """Initialize request coalescer."""
        self.max_batch_size = max_batch_size
        self.batch_timeout = batch_timeout
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._batch_queues: dict[str, list] = {}

    async def coalesce(self, key: str, request: dict[str, Any], handler: Callable) -> Any:
        """Coalesce identical requests."""
        request_key = self._generate_key(key, request)

        # If request is already pending, wait for it
        if request_key in self._pending_requests:
            return await self._pending_requests[request_key]

        # Create new pending request
        future = asyncio.Future()
        self._pending_requests[request_key] = future

        # Start handler in background to allow other requests to coalesce
        async def handle_request():
            try:
                result = await handler(request)
                if not future.done():
                    future.set_result(result)
                return result
            except Exception as e:
                if not future.done():
                    future.set_exception(e)
                raise
            finally:
                # Cleanup
                self._pending_requests.pop(request_key, None)

        # Start handler as background task
        task = asyncio.create_task(handle_request())
        # Store reference to prevent garbage collection
        self._tasks = getattr(self, '_tasks', set())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

        # Return result from future
        return await future

    async def coalesce_batch(self, operation: str, request: dict[str, Any], batch_handler: Callable) -> Any:
        """Coalesce requests into batches."""
        if operation not in self._batch_queues:
            self._batch_queues[operation] = []

        # Add request to batch
        future = asyncio.Future()
        self._batch_queues[operation].append((request, future))

        # Process batch if full or after timeout
        if len(self._batch_queues[operation]) >= self.max_batch_size:
            await self._process_batch(operation, batch_handler)
        else:
            # Schedule timeout processing
            task = asyncio.create_task(self._timeout_batch_processing(operation, batch_handler))
            # Store reference to prevent garbage collection
            self._timeout_tasks = getattr(self, '_timeout_tasks', set())
            self._timeout_tasks.add(task)
            task.add_done_callback(self._timeout_tasks.discard)

        return await future

    async def _process_batch(self, operation: str, batch_handler: Callable) -> None:
        """Process a batch of requests."""
        if operation not in self._batch_queues or not self._batch_queues[operation]:
            return

        batch = self._batch_queues[operation][:]
        self._batch_queues[operation] = []

        requests = [req for req, _ in batch]
        futures = [future for _, future in batch]

        try:
            results = await batch_handler(requests)
            for i, future in enumerate(futures):
                if not future.done():
                    result = results[i] if i < len(results) else None
                    future.set_result(result)
        except Exception as e:
            for future in futures:
                if not future.done():
                    future.set_exception(e)

    async def _timeout_batch_processing(self, operation: str, batch_handler: Callable) -> None:
        """Process batch after timeout."""
        await asyncio.sleep(self.batch_timeout)
        await self._process_batch(operation, batch_handler)

    def _generate_key(self, operation: str, request: dict[str, Any]) -> str:
        """Generate unique key for request."""
        # Sort dictionary for consistent key generation
        sorted_request = json.dumps(request, sort_keys=True)
        request_hash = hashlib.sha256(f"{operation}:{sorted_request}".encode()).hexdigest()
        return f"{operation}:{request_hash}"


@dataclass
class TaskInfo:
    """Background task information."""

    task_id: str
    name: str
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    result: Any = None
    error: Exception | None = None
    priority: int = 5  # Lower number = higher priority

    def __lt__(self, other):
        """Compare tasks for priority queue."""
        if not isinstance(other, TaskInfo):
            return NotImplemented
        return self.priority < other.priority


class BackgroundTaskManager:
    """Manage background tasks with concurrency control."""

    def __init__(self, max_concurrent_tasks: int = 10, task_cleanup_interval: float = 300.0):
        """Initialize background task manager."""
        self.max_concurrent_tasks = max_concurrent_tasks
        self.task_cleanup_interval = task_cleanup_interval
        self._tasks: dict[str, TaskInfo] = {}
        self._running_tasks: set[str] = set()
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)

    async def submit_task(self, name: str, coro_func: Callable, *args, priority: int = 5, **kwargs) -> str:
        """Submit background task."""
        task_id = str(uuid4())
        task_info = self._create_task_info(name, priority)
        task_info.task_id = task_id
        self._tasks[task_id] = task_info

        # Create and start task
        task = asyncio.create_task(self._run_task(task_id, coro_func, *args, **kwargs))
        # Store reference to prevent garbage collection
        self._background_tasks = getattr(self, '_background_tasks', set())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        return task_id

    async def _run_task(self, task_id: str, coro_func: Callable, *args, **kwargs) -> None:
        """Run individual task with concurrency control."""
        async with self._semaphore:
            task_info = self._tasks.get(task_id)
            if not task_info:
                return

            self._running_tasks.add(task_id)
            task_info.status = "running"

            try:
                result = await coro_func(*args, **kwargs)
                task_info.result = result
                task_info.status = "completed"
                task_info.completed_at = time.time()
            except Exception as e:
                task_info.error = e
                task_info.status = "failed"
                task_info.completed_at = time.time()
            finally:
                self._running_tasks.discard(task_id)

                # Schedule cleanup
                task = asyncio.create_task(self._cleanup_task_after_delay(task_id))
                # Store reference to prevent garbage collection
                self._cleanup_tasks = getattr(self, '_cleanup_tasks', set())
                self._cleanup_tasks.add(task)
                task.add_done_callback(self._cleanup_tasks.discard)

    async def _cleanup_task_after_delay(self, task_id: str) -> None:
        """Cleanup task after delay."""
        await asyncio.sleep(self.task_cleanup_interval)
        self._tasks.pop(task_id, None)

    async def get_task_result(self, task_id: str) -> Any:
        """Get task result."""
        task_info = self._tasks.get(task_id)
        if not task_info:
            raise ValueError(f"Task {task_id} not found")

        # Wait for completion
        while task_info.status in ["pending", "running"]:
            await asyncio.sleep(0.01)

        if task_info.status == "failed" and task_info.error:
            raise task_info.error

        return task_info.result

    def get_task_status(self, task_id: str) -> str:
        """Get task status."""
        task_info = self._tasks.get(task_id)
        return task_info.status if task_info else "not_found"

    def _create_task_info(self, name: str, priority: int = 5) -> TaskInfo:
        """Create task info structure."""
        return TaskInfo(
            task_id="",  # Will be set by submit_task
            name=name,
            priority=priority
        )

