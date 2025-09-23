"""
Unit tests for thread safety of singleton patterns.

Tests that singleton patterns are thread-safe and don't create
multiple instances under concurrent access.
"""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from finos_mcp.content.cache import CacheManager


@pytest.mark.unit
class TestSingletonThreadSafety:
    """Test thread safety of singleton patterns."""

    def test_cache_manager_thread_safety(self):
        """Test CacheManager singleton is thread-safe."""
        # Set environment variable for cache security
        original_key = os.environ.get("FINOS_MCP_CACHE_SECRET")
        test_key = "test_thread_safety_key_" + "a" * 10  # 32 char minimum
        os.environ["FINOS_MCP_CACHE_SECRET"] = test_key

        try:
            instances = []

            def create_instance():
                """Create a CacheManager instance."""
                manager = CacheManager()
                instances.append(manager)
                return manager

            # Create multiple instances concurrently
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(create_instance) for _ in range(100)]
                results = [future.result() for future in futures]

            # All instances should be the same object
            first_instance = results[0]
            for instance in results:
                assert instance is first_instance, (
                    "Singleton pattern broken under concurrent access"
                )

            # All collected instances should also be the same
            first_collected = instances[0]
            for instance in instances:
                assert instance is first_collected, "Collected instances not identical"

        finally:
            # Restore original environment variable
            if original_key:
                os.environ["FINOS_MCP_CACHE_SECRET"] = original_key
            else:
                os.environ.pop("FINOS_MCP_CACHE_SECRET", None)

    def test_cache_manager_double_check_locking(self):
        """Test that double-check locking pattern works correctly."""
        # Set environment variable for cache security
        original_key = os.environ.get("FINOS_MCP_CACHE_SECRET")
        test_key = "test_double_check_key_" + "a" * 10  # 32 char minimum
        os.environ["FINOS_MCP_CACHE_SECRET"] = test_key

        try:
            # Reset singleton state by accessing private attributes
            # This is for testing only
            CacheManager._instance = None

            instances = []
            creation_times = []

            def create_and_time():
                """Create instance and record timing."""
                start_time = time.perf_counter()
                manager = CacheManager()
                end_time = time.perf_counter()
                instances.append(manager)
                creation_times.append(end_time - start_time)

            # Create instances concurrently
            threads = []
            for _ in range(50):
                thread = threading.Thread(target=create_and_time)
                threads.append(thread)

            # Start all threads at roughly the same time
            for thread in threads:
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            # Verify singleton property
            first_instance = instances[0]
            for instance in instances:
                assert instance is first_instance

            # Verify we actually have the expected number of instances
            assert len(instances) == 50

        finally:
            # Restore original environment variable
            if original_key:
                os.environ["FINOS_MCP_CACHE_SECRET"] = original_key
            else:
                os.environ.pop("FINOS_MCP_CACHE_SECRET", None)
