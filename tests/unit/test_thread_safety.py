# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The cache manager is one object however many threads ask for it."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from finos_mcp.content.cache import CacheManager

pytestmark = pytest.mark.unit


class TestSingletonThreadSafety:
    def test_cache_manager_is_one_object_under_concurrent_construction(self) -> None:
        with ThreadPoolExecutor(max_workers=10) as executor:
            instances = list(executor.map(lambda _: CacheManager(), range(100)))
        assert all(instance is instances[0] for instance in instances), (
            "Singleton pattern broken under concurrent access"
        )

    def test_cache_manager_is_one_object_from_a_cold_start(self) -> None:
        held = CacheManager._instance
        CacheManager._instance = None
        instances: list[CacheManager] = []
        try:
            threads = [
                threading.Thread(target=lambda: instances.append(CacheManager()))
                for _ in range(50)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            assert len(instances) == 50
            assert all(instance is instances[0] for instance in instances)
        finally:
            CacheManager._instance = held
