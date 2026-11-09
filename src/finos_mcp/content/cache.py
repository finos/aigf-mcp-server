# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The document cache: an in-process dict with a TTL, an LRU bound and copies.

One entry per parsed document, keyed by the service; a corpus of a few
hundred documents, far under the bound. Expiry is enforced on read and the
bound on write, so there is no background task, and no ``await`` ever sat
inside a locked block, so there is no lock: nothing here belongs to an event
loop (#305).

The entries used to be serialised into an HMAC-SHA256 envelope keyed by
``FINOS_MCP_CACHE_SECRET``, with compression, a pickle-magic check and a
compression-ratio check on bytes the cache itself had written. The store is
process memory that nothing persists and whose key was read in the same
process, so the envelope stopped no attacker; it cost about 400 lines, a
mandatory setting on networked transports, and the defects of #303 and #304.
Decided on 2026-10-13 (#302): it is gone. What it gave that is
kept: a private copy on read, because the service mutates the document it
is handed, and one on write for the same reason.

The methods stay ``async`` so the callers, which await them, are unchanged.
"""

from __future__ import annotations

import copy
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass
from typing import Any, Generic, TypeVar

from ..config import get_settings
from ..logging import get_logger

logger = get_logger("cache")

K = TypeVar("K")
T = TypeVar("T")


@dataclass
class CacheStats:
    """What the cache has done since it was built, for the health tool."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    evictions: int = 0
    current_size: int = 0
    max_size: int = 0

    @property
    def hit_rate(self) -> float:
        reads = self.hits + self.misses
        return self.hits / reads if reads else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "hit_rate": self.hit_rate}


class TTLCache(Generic[K, T]):
    """Least-recently-used entries with a time to live."""

    def __init__(self, max_size: int = 1000, default_ttl: float = 3600.0) -> None:
        """
        Args:
            max_size: Entries held at most; the least recently used goes first.
            default_ttl: Seconds an entry lives unless ``set`` says otherwise;
                0 means it never expires.
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        #: key -> (value, expiry as time.time() or None), oldest use first.
        self._entries: OrderedDict[K, tuple[T, float | None]] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._sets = 0
        self._evictions = 0

    async def get(self, key: K) -> T | None:
        """The entry's value as a private copy, or None if absent or expired."""
        entry = self._entries.get(key)
        if entry is None:
            self._misses += 1
            return None
        value, expires_at = entry
        if expires_at is not None and time.time() >= expires_at:
            del self._entries[key]
            self._misses += 1
            return None
        self._entries.move_to_end(key)
        self._hits += 1
        return copy.deepcopy(value)

    async def set(self, key: K, value: T, ttl: float | None = None) -> None:
        """Hold a private copy of ``value`` for ``ttl`` seconds (0: for ever)."""
        lifetime = self.default_ttl if ttl is None else ttl
        expires_at = time.time() + lifetime if lifetime > 0 else None
        self._entries[key] = (copy.deepcopy(value), expires_at)
        self._entries.move_to_end(key)
        self._sets += 1
        while len(self._entries) > self.max_size:
            evicted, _ = self._entries.popitem(last=False)
            self._evictions += 1
            logger.debug("Cache evicted least recently used entry: %s", evicted)

    async def clear(self) -> None:
        self._entries.clear()

    async def get_stats(self) -> CacheStats:
        return CacheStats(
            hits=self._hits,
            misses=self._misses,
            sets=self._sets,
            evictions=self._evictions,
            current_size=len(self._entries),
            max_size=self.max_size,
        )


class CacheManager:
    """Owns the one cache of the process; built on first use from the settings."""

    _instance: CacheManager | None = None
    _cache: TTLCache[str, Any] | None = None

    def __new__(cls) -> CacheManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_cache(self) -> TTLCache[str, Any]:
        if self._cache is None:
            settings = get_settings()
            self._cache = TTLCache(
                max_size=settings.cache_max_size,
                default_ttl=float(settings.cache_ttl_seconds),
            )
            logger.info(
                "Document cache ready: up to %d entries, %d s each",
                settings.cache_max_size,
                settings.cache_ttl_seconds,
            )
        return self._cache

    async def close_cache(self) -> None:
        """Empty the cache and let go of it; the next ``get_cache`` builds anew."""
        cache, self._cache = self._cache, None
        if cache is not None:
            await cache.clear()


_cache_manager = CacheManager()


async def get_cache() -> TTLCache[str, Any]:
    """The process's document cache."""
    return await _cache_manager.get_cache()


async def close_cache() -> None:
    """Empty and release the process's document cache."""
    await _cache_manager.close_cache()
