# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The document cache: an in-process dict with a TTL, an LRU bound and copies.

Decided on 2026-10-13 (#302): the HMAC envelope, its compression,
its pickle and ratio checks and ``FINOS_MCP_CACHE_SECRET`` are gone. The
store is an ``OrderedDict`` in process memory that nothing persists and
whose key was read in the same process, so the envelope stopped no attacker
and cost about 400 lines, a mandatory setting on networked transports, and
the defects of #303 (a frontmatter date stored without a hash and refused on
every read) and #304 (a bad entry raised from ``get``, counted as a hit, and
tripped a breaker that switched the cache off). What the envelope gave that
must be kept is a private copy on read, since the service mutates the
document it is handed.

With it go the lock and the background cleanup task (#305): no ``await``
sat inside any locked block, expiry is enforced on read and the bound on
write, and they were the only loop-bound state. A cache built on one loop
is read on another.
"""

from __future__ import annotations

import ast
import asyncio
import datetime
import re
from pathlib import Path
from typing import Any

import pytest

from finos_mcp.config import Settings
from finos_mcp.content import cache as cache_module
from finos_mcp.content.cache import CacheManager, TTLCache, close_cache, get_cache

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[2] / "src" / "finos_mcp"


@pytest.fixture
def cache() -> TTLCache[str, dict[str, Any]]:
    return TTLCache(max_size=3, default_ttl=60.0)


class TestGetAndSet:
    async def test_a_value_set_is_got(
        self, cache: TTLCache[str, dict[str, Any]]
    ) -> None:
        await cache.set("a", {"title": "A"})
        assert await cache.get("a") == {"title": "A"}

    async def test_a_missing_key_is_none(
        self, cache: TTLCache[str, dict[str, Any]]
    ) -> None:
        assert await cache.get("nothing") is None

    async def test_a_key_set_again_holds_the_new_value(
        self, cache: TTLCache[str, dict[str, Any]]
    ) -> None:
        await cache.set("a", {"v": 1})
        await cache.set("a", {"v": 2})
        assert await cache.get("a") == {"v": 2}

    async def test_the_reader_gets_a_private_copy(
        self, cache: TTLCache[str, dict[str, Any]]
    ) -> None:
        """The service mutates the document it is handed (#302)."""
        await cache.set("a", {"sections": ["one"]})
        first = await cache.get("a")
        assert first is not None
        first["sections"].append("two")
        assert await cache.get("a") == {"sections": ["one"]}

    async def test_the_writer_keeps_a_private_copy(
        self, cache: TTLCache[str, dict[str, Any]]
    ) -> None:
        document = {"sections": ["one"]}
        await cache.set("a", document)
        document["sections"].append("two")
        assert await cache.get("a") == {"sections": ["one"]}

    async def test_a_frontmatter_date_round_trips(
        self, cache: TTLCache[str, dict[str, Any]]
    ) -> None:
        """#303: ``date: 2024-01-01`` parses to a date; it was refused on read."""
        document = {"metadata": {"date": datetime.date(2024, 1, 1)}, "content": "x"}
        await cache.set("risk:ri-1.md", document)
        assert await cache.get("risk:ri-1.md") == document

    async def test_a_large_repetitive_value_round_trips(self) -> None:
        """#302: the ratio check refused a legitimate 420 kB table-like value."""
        cache: TTLCache[str, dict[str, Any]] = TTLCache(max_size=10, default_ttl=60.0)
        rows = [{"id": n, "name": "row", "value": "x" * 20} for n in range(20_000)]
        await cache.set("table", {"rows": rows})
        got = await cache.get("table")
        assert got is not None
        assert got["rows"] == rows


class TestExpiry:
    async def test_an_expired_entry_is_a_miss(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        now = [1000.0]
        monkeypatch.setattr("finos_mcp.content.cache.time.time", lambda: now[0])
        cache: TTLCache[str, str] = TTLCache(max_size=3, default_ttl=10.0)
        await cache.set("a", "A")
        now[0] += 9.0
        assert await cache.get("a") == "A"
        now[0] += 2.0
        assert await cache.get("a") is None
        assert (await cache.get_stats()).misses == 1

    async def test_a_per_entry_ttl_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        now = [1000.0]
        monkeypatch.setattr("finos_mcp.content.cache.time.time", lambda: now[0])
        cache: TTLCache[str, str] = TTLCache(max_size=3, default_ttl=10.0)
        await cache.set("a", "A", ttl=100.0)
        now[0] += 50.0
        assert await cache.get("a") == "A"

    async def test_a_zero_ttl_means_no_expiry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``.env.example`` says a TTL of 0 caches indefinitely."""
        now = [1000.0]
        monkeypatch.setattr("finos_mcp.content.cache.time.time", lambda: now[0])
        cache: TTLCache[str, str] = TTLCache(max_size=3, default_ttl=0)
        await cache.set("a", "A")
        now[0] += 10**9
        assert await cache.get("a") == "A"


class TestBound:
    async def test_the_oldest_unused_entry_is_evicted(
        self, cache: TTLCache[str, dict[str, Any]]
    ) -> None:
        for key in ("a", "b", "c"):
            await cache.set(key, {"k": key})
        await cache.get("a")  # a is now the most recently used
        await cache.set("d", {"k": "d"})
        assert await cache.get("b") is None, "the least recently used entry stayed"
        assert await cache.get("a") == {"k": "a"}
        assert (await cache.get_stats()).evictions == 1

    async def test_clear_empties_the_cache(
        self, cache: TTLCache[str, dict[str, Any]]
    ) -> None:
        await cache.set("a", {})
        await cache.clear()
        assert await cache.get("a") is None
        assert (await cache.get_stats()).current_size == 0


class TestStats:
    async def test_hits_misses_sets_and_size_are_counted(
        self, cache: TTLCache[str, dict[str, Any]]
    ) -> None:
        await cache.set("a", {})
        await cache.get("a")
        await cache.get("b")
        stats = await cache.get_stats()
        assert (
            stats.hits,
            stats.misses,
            stats.sets,
            stats.current_size,
            stats.max_size,
        ) == (
            1,
            1,
            1,
            1,
            3,
        )
        assert stats.hit_rate == 0.5
        assert stats.to_dict()["hits"] == 1


class TestNotLoopBound:
    def test_a_cache_built_on_one_loop_is_read_on_another(self) -> None:
        """#305: nothing in the cache belongs to an event loop."""
        cache: TTLCache[str, str] = TTLCache(max_size=3, default_ttl=60.0)
        asyncio.run(cache.set("a", "A"))
        assert asyncio.run(cache.get("a")) == "A"

    def test_the_module_imports_no_asyncio(self) -> None:
        source = (SRC / "content" / "cache.py").read_text(encoding="utf-8")
        names = {
            alias.name
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Import | ast.ImportFrom)
            for alias in (
                node.names
                if isinstance(node, ast.Import)
                else [ast.alias(name=node.module or "")]
            )
        }
        assert "asyncio" not in names, "the cache holds loop-bound state again"


class TestTheSingleton:
    async def test_get_cache_returns_one_cache_built_from_the_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(cache_module._cache_manager, "_cache", None)
        first = await get_cache()
        assert await get_cache() is first
        settings = Settings()
        stats = await first.get_stats()
        assert stats.max_size == settings.cache_max_size

    async def test_close_cache_empties_and_unbinds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(cache_module._cache_manager, "_cache", None)
        cache = await get_cache()
        await cache.set("a", "A")
        await close_cache()
        assert cache_module._cache_manager._cache is None
        assert await cache.get("a") is None

    def test_the_manager_is_one_object(self) -> None:
        assert CacheManager() is CacheManager()


def test_a_networked_server_needs_no_cache_secret() -> None:
    """#302's acceptance: an http server starts with no FINOS_MCP_CACHE_SECRET."""
    Settings(
        mcp_transport="http", mcp_host="127.0.0.1", allow_insecure_http=True
    ).validate_startup()
    assert "cache_secret" not in Settings.model_fields


def test_every_public_name_in_the_cache_module_has_a_caller() -> None:
    """#305: the interface, the adapters and the unused stats fields are gone."""
    source = (SRC / "content" / "cache.py").read_text(encoding="utf-8")
    public = [
        node.name
        for node in ast.parse(source).body
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and not node.name.startswith("_")
    ]
    assert public, "no public names found"
    others = "\n".join(
        path.read_text(encoding="utf-8")
        for path in SRC.rglob("*.py")
        if path.name != "cache.py"
    )
    unused = [name for name in public if not re.search(rf"\b{name}\b", others)]
    assert not unused, f"public cache names nothing in src uses: {unused}"
