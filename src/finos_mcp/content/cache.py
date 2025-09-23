"""Caching layer with TTL and eviction policies for FINOS MCP Server.

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

This module provides a comprehensive caching system with:
- Time-To-Live (TTL) expiration
- Least Recently Used (LRU) eviction policy
- Cache hit/miss metrics and monitoring
- Configurable cache sizes and timeouts
- Thread-safe operations for concurrent access
"""

import asyncio
import gzip
import json
import os
import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, Optional, TypeVar

from ..config import get_settings
from ..logging import get_logger
from .cache_models import (
    CacheSecurityError,
    CacheValidationError,
    secure_cache_deserializer,
    secure_cache_serializer,
)

logger = get_logger("cache")

# Memory allocation limits for security
MAX_OBJECT_SIZE = 10_000_000  # 10MB maximum for individual objects
MAX_COMPRESSION_RATIO = 100  # Maximum compression ratio to prevent bombs

T = TypeVar("T")
K = TypeVar("K")


class CacheOperation(Enum):
    """Cache operation types for monitoring."""

    HIT = "hit"
    MISS = "miss"
    SET = "set"
    DELETE = "delete"
    EXPIRE = "expire"
    EVICT = "evict"
    CLEAR = "clear"


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with TTL and access tracking.

    Attributes:
        value: The cached value
        created_at: Timestamp when entry was created
        accessed_at: Timestamp when entry was last accessed
        expires_at: Timestamp when entry expires (None for no expiration)
        access_count: Number of times entry has been accessed
        size_bytes: Estimated size of the entry in bytes

    """

    value: T
    created_at: float
    accessed_at: float
    expires_at: float | None
    access_count: int = 0
    size_bytes: int = 0

    def is_expired(self, current_time: float | None = None) -> bool:
        """Check if the entry has expired."""
        if self.expires_at is None:
            return False

        if current_time is None:
            current_time = time.time()

        return current_time >= self.expires_at

    def touch(self, current_time: float | None = None) -> None:
        """Update access time and count."""
        if current_time is None:
            current_time = time.time()

        self.accessed_at = current_time
        self.access_count += 1

    def age_seconds(self, current_time: float | None = None) -> float:
        """Get age of entry in seconds."""
        if current_time is None:
            current_time = time.time()

        return current_time - self.created_at

    def time_to_expiry(self, current_time: float | None = None) -> float | None:
        """Get time until expiry in seconds (None if no expiration)."""
        if self.expires_at is None:
            return None

        if current_time is None:
            current_time = time.time()

        return max(0, self.expires_at - current_time)


@dataclass  # pylint: disable=too-many-instance-attributes
class CacheStats:
    """Cache statistics and metrics."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    expires: int = 0
    evictions: int = 0
    clears: int = 0
    current_size: int = 0
    max_size: int = 0
    memory_usage_bytes: int = 0
    hit_rate: float = 0.0

    def update_hit_rate(self) -> None:
        """Update calculated hit rate."""
        total = self.hits + self.misses
        self.hit_rate = (self.hits / total) if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        self.update_hit_rate()
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "expires": self.expires,
            "evictions": self.evictions,
            "clears": self.clears,
            "current_size": self.current_size,
            "max_size": self.max_size,
            "memory_usage_bytes": self.memory_usage_bytes,
            "hit_rate": round(self.hit_rate, 3),
        }


class CacheInterface(ABC, Generic[K, T]):
    """Abstract interface for cache implementations."""

    @abstractmethod
    async def get(self, key: K) -> T | None:
        """Get value from cache."""
        ...

    @abstractmethod
    async def set(self, key: K, value: T, ttl: float | None = None) -> None:
        """Set value in cache with optional TTL."""
        ...

    @abstractmethod
    async def delete(self, key: K) -> bool:
        """Delete value from cache. Returns True if key existed."""
        ...

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache entries."""
        ...

    @abstractmethod
    async def exists(self, key: K) -> bool:
        """Check if key exists in cache."""
        ...

    @abstractmethod
    async def size(self) -> int:
        """Get current cache size."""
        ...

    @abstractmethod
    async def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        ...

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Remove expired entries. Returns number of entries removed."""
        ...


class TTLCache(CacheInterface[K, T]):  # pylint: disable=too-many-instance-attributes
    """In-memory cache with TTL and LRU eviction policy.

    Features:
    - Time-To-Live expiration with automatic cleanup
    - Least Recently Used eviction when cache is full
    - Thread-safe operations
    - Comprehensive metrics and monitoring
    - Configurable size limits
    - Background cleanup task
    - Optional gzip compression for 60-80% memory reduction
    """

    def __init__(
        self,
        max_size: int = 1000,
        *,
        default_ttl: float | None = None,
        cleanup_interval: float = 60.0,
        enable_background_cleanup: bool = True,
        enable_compression: bool = True,
    ):
        """Initialize TTL cache.

        Args:
            max_size: Maximum number of entries in cache
            default_ttl: Default TTL in seconds (None for no expiration)
            cleanup_interval: Background cleanup interval in seconds
            enable_background_cleanup: Enable automatic background cleanup
            enable_compression: Enable gzip compression for memory efficiency

        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval
        self.enable_compression = enable_compression

        # Thread-safe storage using OrderedDict for LRU behavior
        self._cache: OrderedDict[K, CacheEntry[T]] = OrderedDict()
        self._lock = threading.RLock()

        # Statistics
        self._stats = CacheStats(max_size=max_size)

        # Background cleanup task
        self._cleanup_task: asyncio.Task[None] | None = None
        self._enable_background_cleanup = enable_background_cleanup
        if enable_background_cleanup:
            self._start_cleanup_task()

    def _start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        try:
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._background_cleanup())
        except RuntimeError as e:
            if "no running event loop" in str(e):
                logger.debug("Cannot start cache cleanup: no event loop running")
                # Cleanup will be started when cache is accessed in async context
            else:
                raise

    async def start(self) -> None:
        """Start async components of the cache.

        This method must be called in an async context to start background tasks.
        """
        if self._enable_background_cleanup and (
            self._cleanup_task is None or self._cleanup_task.done()
        ):
            self._start_cleanup_task()
            logger.debug("Cache background cleanup started in async context")

    async def _background_cleanup(self) -> None:
        """Background task to clean up expired entries."""
        logger.debug("Started cache background cleanup task")

        try:
            while True:
                await asyncio.sleep(self.cleanup_interval)

                try:
                    expired_count = await self.cleanup_expired()
                    if expired_count > 0:
                        logger.debug(
                            "Background cleanup removed %s expired entries",
                            expired_count,
                        )
                except (
                    asyncio.TimeoutError,
                    RuntimeError,
                    ValueError,
                    KeyError,
                    AttributeError,
                ) as e:
                    logger.error("Error in background cache cleanup: %s", e)

        except asyncio.CancelledError:
            logger.debug("Cache background cleanup task cancelled")
            raise
        except (asyncio.TimeoutError, RuntimeError, ValueError, TypeError) as e:
            logger.error("Unexpected error in background cache cleanup: %s", e)

    def _compress_value(self, value: T, key: str) -> tuple[Any, int]:
        """Secure serialize value using JSON with optional compression.

        Returns:
            Tuple of (serialized_value, actual_size_bytes)

        """
        try:
            # Get security key for HMAC
            secret_key = self._get_cache_security_key()

            # Secure serialize using JSON + Pydantic validation
            serialized = secure_cache_serializer(
                data=value,
                key=key,
                ttl=int(self.default_ttl or 0),
                secret_key=secret_key,
            )
            serialized_bytes = serialized.encode("utf-8")

            # Memory limit check - reject objects that are too large
            if len(serialized_bytes) > MAX_OBJECT_SIZE:
                raise ValueError(
                    f"Object size {len(serialized_bytes)} bytes exceeds maximum "
                    f"allowed size of {MAX_OBJECT_SIZE} bytes. This prevents "
                    "memory exhaustion attacks."
                )

            if not self.enable_compression:
                return serialized_bytes, len(serialized_bytes)

            # Only compress if serialized data is reasonably large (> 100 bytes)
            if len(serialized_bytes) > 100:
                compressed = gzip.compress(serialized_bytes, compresslevel=6)
                # Only use compression if it actually saves space
                if len(compressed) < len(serialized_bytes):
                    logger.debug(
                        "Compressed value: %s -> %s bytes (%.1f%% reduction)",
                        len(serialized_bytes),
                        len(compressed),
                        (1 - len(compressed) / len(serialized_bytes)) * 100,
                    )
                    return compressed, len(compressed)

            # Return original serialized value if compression not beneficial
            return serialized_bytes, len(serialized_bytes)

        except (
            CacheValidationError,
            CacheSecurityError,
            gzip.BadGzipFile,
            TypeError,
            ValueError,
            MemoryError,
        ) as e:
            logger.warning("Secure serialization failed: %s", e)
            # Raise security errors to prevent unsafe fallbacks
            if isinstance(e, (CacheValidationError, CacheSecurityError)):
                raise
            # Check if this is a memory/size limit error that should be enforced
            if isinstance(e, ValueError) and (
                "exceeds maximum" in str(e) or "Object size" in str(e)
            ):
                logger.error("Memory limit exceeded - blocking cache operation: %s", e)
                raise e
            return self._fallback_json_serialize(
                value
            ), self._estimate_uncompressed_size(value)

    def _decompress_value(self, stored_value: Any) -> T:
        """Securely deserialize value from JSON with optional decompression."""
        if not isinstance(stored_value, bytes):
            # Handle legacy or direct JSON strings
            if isinstance(stored_value, str):
                return self._secure_deserialize_json(stored_value)
            return stored_value

        try:
            # Security check: detect potential pickle data
            if len(stored_value) >= 2:
                # Check for pickle magic bytes (0x80 0x03 for protocol 3, etc.)
                if stored_value[:2] in [
                    b"\x80\x03",
                    b"\x80\x04",
                    b"\x80\x05",
                ] or stored_value.startswith(b"c"):
                    raise CacheSecurityError(
                        "Potential pickle data detected - rejected for security"
                    )

                # Check for gzip header followed by pickle magic
                if stored_value.startswith(b"\x1f\x8b"):  # gzip magic
                    try:
                        # Protection against decompression bombs
                        if (
                            len(stored_value) < MAX_OBJECT_SIZE
                        ):  # Only attempt if reasonable size
                            decompressed = gzip.decompress(stored_value)
                            # Check compression ratio to prevent decompression bombs
                            compression_ratio = len(decompressed) / len(stored_value)
                            if compression_ratio > MAX_COMPRESSION_RATIO:
                                raise ValueError(
                                    f"Compression ratio {compression_ratio:.1f} exceeds maximum "
                                    f"allowed ratio of {MAX_COMPRESSION_RATIO}. This prevents "
                                    "decompression bomb attacks."
                                )
                            if len(decompressed) >= 2 and (
                                decompressed[:2]
                                in [b"\x80\x03", b"\x80\x04", b"\x80\x05"]
                                or decompressed.startswith(b"c")
                            ):
                                raise CacheSecurityError(
                                    "Potential compressed pickle data detected - rejected for security"
                                )
                        else:
                            raise ValueError(
                                f"Compressed data size {len(stored_value)} exceeds safety limit"
                            )
                    except gzip.BadGzipFile:
                        pass  # Not gzip, continue with normal processing

            # Get security key for HMAC verification
            secret_key = self._get_cache_security_key()

            if self.enable_compression:
                try:
                    # Protection against decompression bombs
                    if len(stored_value) > MAX_OBJECT_SIZE:
                        raise ValueError(
                            f"Compressed data size {len(stored_value)} exceeds safety limit"
                        )

                    # Try to decompress - if it fails, assume it's not compressed
                    decompressed = gzip.decompress(stored_value)

                    # Check compression ratio to prevent decompression bombs
                    compression_ratio = len(decompressed) / len(stored_value)
                    if compression_ratio > MAX_COMPRESSION_RATIO:
                        raise ValueError(
                            f"Compression ratio {compression_ratio:.1f} exceeds maximum "
                            f"allowed ratio of {MAX_COMPRESSION_RATIO}. This prevents "
                            "decompression bomb attacks."
                        )

                    json_str = decompressed.decode("utf-8")
                except (gzip.BadGzipFile, UnicodeDecodeError):
                    # Not compressed, treat as direct JSON
                    json_str = stored_value.decode("utf-8")
                except ValueError as e:
                    # Memory/compression ratio limits exceeded
                    logger.error("Decompression security limit exceeded: %s", e)
                    raise CacheSecurityError(
                        f"Decompression failed security checks: {e}"
                    ) from e
            else:
                json_str = stored_value.decode("utf-8")

            # Additional security check: ensure it looks like JSON
            json_str = json_str.strip()
            if not (
                json_str.startswith(("{", "[", '"'))
                or json_str in ("true", "false", "null")
                or json_str.replace("-", "").replace(".", "").isdigit()
            ):
                raise CacheSecurityError("Data does not appear to be valid JSON")

            # Securely deserialize using JSON + Pydantic validation
            return secure_cache_deserializer(json_str, secret_key)

        except (
            CacheValidationError,
            CacheSecurityError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as e:
            logger.error("Secure deserialization failed: %s", e)
            # For security errors, do not return potentially unsafe data
            if isinstance(e, (CacheValidationError, CacheSecurityError)):
                raise
            # For other errors, do not attempt fallback - safer to fail
            raise CacheValidationError(f"Cache data validation failed: {e}") from e

    def _estimate_uncompressed_size(self, value: T) -> int:
        """Estimate size of uncompressed value in bytes."""
        try:
            if isinstance(value, str):
                return len(value.encode("utf-8"))
            if isinstance(value, bytes):
                return len(value)
            elif isinstance(value, int | float):
                return 8
            elif isinstance(value, bool):
                return 1
            elif isinstance(value, list | tuple):
                return sum(self._estimate_uncompressed_size(item) for item in value)
            elif isinstance(value, dict):
                return sum(
                    self._estimate_uncompressed_size(k)
                    + self._estimate_uncompressed_size(v)
                    for k, v in value.items()
                )
            else:
                # Fallback: rough estimate based on string representation
                return len(str(value)) * 2
        except (TypeError, ValueError, AttributeError, MemoryError):
            return 100  # Default estimate if calculation fails

    def _record_operation(
        self, operation: CacheOperation, key: K | None = None
    ) -> None:
        """Record cache operation for metrics."""
        if operation == CacheOperation.HIT:
            self._stats.hits += 1
        elif operation == CacheOperation.MISS:
            self._stats.misses += 1
        elif operation == CacheOperation.SET:
            self._stats.sets += 1
        elif operation == CacheOperation.DELETE:
            self._stats.deletes += 1
        elif operation == CacheOperation.EXPIRE:
            self._stats.expires += 1
        elif operation == CacheOperation.EVICT:
            self._stats.evictions += 1
        elif operation == CacheOperation.CLEAR:
            self._stats.clears += 1

        # Update current size and memory usage
        self._stats.current_size = len(self._cache)
        self._stats.memory_usage_bytes = sum(
            entry.size_bytes for entry in self._cache.values()
        )

    def _get_cache_security_key(self) -> str:
        """Get security key for HMAC operations.

        Raises:
            ValueError: If FINOS_MCP_CACHE_SECRET environment variable is not set
                       or does not meet minimum security requirements
        """
        security_key = os.environ.get("FINOS_MCP_CACHE_SECRET")

        if not security_key:
            raise ValueError(
                "FINOS_MCP_CACHE_SECRET environment variable must be set. "
                "Generate a secure key with: python -c 'import secrets; print(secrets.token_hex(32))'"
            )

        # Ensure minimum key length for security (32 chars minimum)
        if len(security_key) < 32:
            raise ValueError(
                f"Cache security key must be at least 32 characters. "
                f"Current length: {len(security_key)}. "
                "Generate a secure key with: python -c 'import secrets; print(secrets.token_hex(32))'"
            )

        return security_key

    def _fallback_json_serialize(self, value: Any) -> bytes:
        """Fallback JSON serialization without Pydantic validation."""
        try:
            # Basic JSON serialization for simple data types
            json_str = json.dumps(value, default=str, separators=(",", ":"))
            return json_str.encode("utf-8")
        except (TypeError, ValueError) as e:
            logger.error("Fallback JSON serialization failed: %s", e)
            # Return a safe representation
            safe_repr = {"error": "serialization_failed", "type": str(type(value))}
            return json.dumps(safe_repr).encode("utf-8")

    def _fallback_json_deserialize(self, stored_value: Any) -> Any:
        """Fallback JSON deserialization for non-Pydantic data."""
        try:
            if isinstance(stored_value, bytes):
                json_str = stored_value.decode("utf-8")
            else:
                json_str = str(stored_value)

            return json.loads(json_str)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error("Fallback JSON deserialization failed: %s", e)
            return None

    def _secure_deserialize_json(self, json_str: str) -> Any:
        """Secure deserialize JSON string with validation."""
        try:
            secret_key = self._get_cache_security_key()
            return secure_cache_deserializer(json_str, secret_key)
        except (CacheValidationError, CacheSecurityError) as e:
            logger.error("Secure JSON deserialization failed: %s", e)
            # For security errors, return None rather than potentially unsafe data
            return None

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._cache:
            return

        # Remove the first item (least recently used)
        key, _ = self._cache.popitem(last=False)
        self._record_operation(CacheOperation.EVICT, key)

        logger.debug("Evicted LRU entry: %s", key)

    def _move_to_end(self, key: K) -> None:
        """Move key to end of OrderedDict (most recently used)."""
        self._cache.move_to_end(key)

    async def get(self, key: K) -> T | None:
        """Get value from cache."""
        current_time = time.time()

        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._record_operation(CacheOperation.MISS, key)
                return None

            # Check if expired
            if entry.is_expired(current_time):
                del self._cache[key]
                self._record_operation(CacheOperation.EXPIRE, key)
                self._record_operation(CacheOperation.MISS, key)
                logger.debug("Cache entry expired: %s", key)
                return None

            # Update access info and move to end (most recently used)
            entry.touch(current_time)
            self._move_to_end(key)

            self._record_operation(CacheOperation.HIT, key)
            return self._decompress_value(entry.value)

    async def set(self, key: K, value: T, ttl: float | None = None) -> None:
        """Set value in cache with optional TTL."""
        current_time = time.time()

        # Use default TTL if not specified
        if ttl is None:
            ttl = self.default_ttl

        # Calculate expiration time
        expires_at = None
        if ttl is not None and ttl > 0:
            expires_at = current_time + ttl

        # Secure serialize value and get actual size
        stored_value, size_bytes = self._compress_value(value, str(key))

        with self._lock:
            # Create new entry with potentially compressed value
            entry = CacheEntry(
                value=stored_value,
                created_at=current_time,
                accessed_at=current_time,
                expires_at=expires_at,
                access_count=1,
                size_bytes=size_bytes,
            )

            # If key already exists, this is an update
            if key in self._cache:
                self._cache[key] = entry
                self._move_to_end(key)
            else:
                # Check if we need to evict entries
                while len(self._cache) >= self.max_size:
                    self._evict_lru()

                # Add new entry
                self._cache[key] = entry

            self._record_operation(CacheOperation.SET, key)

    async def delete(self, key: K) -> bool:
        """Delete value from cache. Returns True if key existed."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._record_operation(CacheOperation.DELETE, key)
                return True
            return False

    async def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._record_operation(CacheOperation.CLEAR)

    async def exists(self, key: K) -> bool:
        """Check if key exists in cache."""
        current_time = time.time()

        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False

            # Check if expired
            if entry.is_expired(current_time):
                del self._cache[key]
                self._record_operation(CacheOperation.EXPIRE, key)
                return False

            return True

    async def size(self) -> int:
        """Get current cache size."""
        with self._lock:
            return len(self._cache)

    async def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._lock:
            # Update current metrics
            self._record_operation(
                CacheOperation.HIT
            )  # Dummy operation to update stats
            self._stats.hits -= 1  # Remove the dummy hit

            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                sets=self._stats.sets,
                deletes=self._stats.deletes,
                expires=self._stats.expires,
                evictions=self._stats.evictions,
                clears=self._stats.clears,
                current_size=self._stats.current_size,
                max_size=self._stats.max_size,
                memory_usage_bytes=self._stats.memory_usage_bytes,
                hit_rate=self._stats.hit_rate,
            )

    async def cleanup_expired(self) -> int:
        """Remove expired entries. Returns number of entries removed."""
        current_time = time.time()
        expired_keys = []

        with self._lock:
            for key, entry in list(self._cache.items()):
                if entry.is_expired(current_time):
                    expired_keys.append(key)

            # Remove expired entries
            for key in expired_keys:
                del self._cache[key]
                self._record_operation(CacheOperation.EXPIRE, key)

        if expired_keys:
            logger.debug("Cleaned up %s expired cache entries", len(expired_keys))

        return len(expired_keys)

    async def get_entry_info(self, key: K) -> dict[str, Any] | None:
        """Get detailed information about a cache entry."""
        current_time = time.time()

        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None

            return {
                "key": str(key),
                "created_at": entry.created_at,
                "accessed_at": entry.accessed_at,
                "expires_at": entry.expires_at,
                "access_count": entry.access_count,
                "size_bytes": entry.size_bytes,
                "age_seconds": entry.age_seconds(current_time),
                "time_to_expiry": entry.time_to_expiry(current_time),
                "is_expired": entry.is_expired(current_time),
            }

    async def close(self) -> None:
        """Close cache and cleanup resources."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        await self.clear()
        logger.debug("Cache closed and cleaned up")


class CacheManager:
    """Singleton manager for the global cache instance."""

    _instance: Optional["CacheManager"] = None
    _cache: TTLCache[str, Any] | None = None
    _lock = threading.Lock()

    def __new__(cls) -> "CacheManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    async def get_cache(self) -> TTLCache[str, Any]:
        """Get or create global cache instance.

        Returns:
            Global TTL cache instance configured with application settings

        """
        if self._cache is None:
            with self._lock:
                # Double-check pattern to prevent race conditions
                if self._cache is None:
                    settings = get_settings()

                    # Get cache configuration from settings
                    max_size = getattr(settings, "cache_max_size", 1000)
                    default_ttl = getattr(settings, "cache_ttl_seconds", 3600.0)

                    self._cache = TTLCache(
                        max_size=max_size,
                        default_ttl=default_ttl,
                        cleanup_interval=60.0,  # Cleanup every minute
                        enable_background_cleanup=True,
                        enable_compression=True,  # Enable gzip compression for 60-80% memory reduction
                    )

            logger.info(
                "Initialized cache with max_size=%s, ttl=%ss, compression=enabled",
                max_size,
                default_ttl,
            )

            # Start async components if we're in an async context
            try:
                await self._cache.start()
            except RuntimeError:
                # Not in async context, that's okay
                pass

        return self._cache

    async def close_cache(self) -> None:
        """Close and cleanup global cache."""
        if self._cache is not None:
            await self._cache.close()
            self._cache = None
            logger.info("Global cache closed")


# Global cache manager instance
_cache_manager = CacheManager()


async def get_cache() -> TTLCache[str, Any]:
    """Get or create global cache instance.

    Returns:
        Global TTL cache instance configured with application settings

    """
    return await _cache_manager.get_cache()


async def close_cache() -> None:
    """Close and cleanup global cache."""
    await _cache_manager.close_cache()
