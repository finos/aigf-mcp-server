"""Tests for request validation and DoS protection."""

import asyncio
from typing import Any
from unittest.mock import Mock

import pytest

from finos_mcp.security.request_validator import (
    DoSProtector,
    RequestSizeValidator,
    dos_protector,
    request_size_validator,
)


class TestRequestSizeValidator:
    """Test suite for RequestSizeValidator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = RequestSizeValidator(
            max_tool_result_size=1000,  # 1KB for testing
            max_resource_size=500,  # 500B for testing
        )

    def test_tool_result_size_validation_success(self):
        """Test successful tool result validation."""
        small_result = ["small", "result", {"key": "value"}]
        # Should not raise exception
        self.validator.validate_tool_result_size(small_result)

    def test_tool_result_size_validation_failure(self):
        """Test tool result size limit enforcement."""
        large_result = ["x" * 2000] * 10  # Large result
        with pytest.raises(ValueError, match="Tool result exceeds size limit"):
            self.validator.validate_tool_result_size(large_result)

    def test_resource_size_validation_success(self):
        """Test successful resource size validation."""
        small_content = "x" * 400  # Under 500B limit
        # Should not raise exception
        self.validator.validate_resource_size(small_content)

    def test_resource_size_validation_failure(self):
        """Test resource size limit enforcement."""
        large_content = "x" * 600  # Over 500B limit
        with pytest.raises(ValueError, match="Resource content exceeds size limit"):
            self.validator.validate_resource_size(large_content)

    def test_resource_size_validation_none_content(self):
        """Test resource validation with None content."""
        # Should not raise exception
        self.validator.validate_resource_size(None)

    # Per-request memory accounting (validate_concurrent_memory_usage and the
    # start/complete/get tracking trio) was removed in #23 along with its tests.
    # Nothing ever populated it, so the tests here asserted protection the running
    # server did not have.

    def test_content_size_calculation_basic_types(self):
        """Test content size calculation for basic types."""
        # String
        size = self.validator._calculate_content_size("hello")
        assert size == 5

        # Dict
        size = self.validator._calculate_content_size({"key": "value"})
        assert size > 0

        # List
        size = self.validator._calculate_content_size(["a", "b", "c"])
        assert size > 0

        # None
        size = self.validator._calculate_content_size(None)
        assert size == 0

    def test_content_size_calculation_protection(self):
        """Test content size calculation protection against attacks."""
        # Create deeply nested structure
        nested: dict[str, Any] = {"level": 1}
        for i in range(2, 1000):  # Create very deep nesting
            nested = {"level": i, "nested": nested}

        # Should not crash or take too long
        size = self.validator._calculate_content_size(nested)
        assert isinstance(size, int)
        assert size > 0

    def test_content_size_calculation_circular_reference(self):
        """Test content size calculation with circular references."""
        # Create circular reference
        obj1: dict[str, Any] = {"name": "obj1"}
        obj2 = {"name": "obj2", "ref": obj1}
        obj1["ref"] = obj2

        # Should handle circular references gracefully
        size = self.validator._calculate_content_size(obj1)
        assert isinstance(size, int)
        assert size > 0

    def test_content_size_calculation_error_handling(self):
        """Test content size calculation error handling."""
        # Mock an object that causes errors
        problematic_obj = Mock()
        problematic_obj.__str__ = Mock(side_effect=Exception("Mock error"))  # type: ignore[method-assign]
        problematic_obj.__len__ = Mock(side_effect=Exception("Mock error"))

        # Should return conservative estimate
        size = self.validator._calculate_content_size(problematic_obj)
        assert isinstance(size, int)
        assert size >= 1000  # Conservative fallback


class TestDoSProtector:
    """Test suite for DoSProtector."""

    def setup_method(self):
        """Set up test fixtures."""
        self.protector = DoSProtector(
            max_requests_per_minute=5,
            max_concurrent_requests=3,
            cleanup_interval_seconds=1,
        )

    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self):
        """Test rate limiting enforcement."""
        client_id = "test-client"

        # Should allow requests up to limit
        for i in range(5):
            allowed = await self.protector.check_rate_limit(client_id)
            assert allowed, f"Request {i} should be allowed"

        # Should block additional requests
        blocked = await self.protector.check_rate_limit(client_id)
        assert not blocked, "Request should be blocked due to rate limit"

    @pytest.mark.asyncio
    async def test_concurrent_request_limit(self):
        """Test concurrent request limit enforcement."""
        client_id = "test-client"

        # Start requests up to limit
        request_ids = []
        for _i in range(3):
            request_id = await self.protector.start_request(client_id)
            request_ids.append(request_id)

        # Should block additional concurrent request
        with pytest.raises(ValueError, match="Too many concurrent requests"):
            await self.protector.start_request(client_id)

        # Complete one request
        await self.protector.complete_request(client_id, request_ids[0])

        # Should now allow new request
        new_request_id = await self.protector.start_request(client_id)
        assert new_request_id is not None

    # test_client_stats was removed in #23 with DoSProtector.get_client_stats: the
    # method had no call site in src/, so the test asserted behaviour of dead code.

    @pytest.mark.asyncio
    async def test_rate_limit_cleanup(self):
        """Test rate limit history cleanup."""
        client_id = "test-client"

        # Mock time control
        mock_time = 1000.0
        original_get_time = self.protector._get_current_time

        def get_mock_time():
            return mock_time

        self.protector._get_current_time = get_mock_time  # type: ignore[method-assign]

        try:
            # Make requests
            for _ in range(3):
                await self.protector.check_rate_limit(client_id)

            # Advance time by more than 60 seconds
            mock_time += 70.0

            # Make another request (should trigger cleanup)
            await self.protector.check_rate_limit(client_id)

            # Verify old requests were cleaned up
            assert len(self.protector._request_history[client_id]) == 1

        finally:
            self.protector._get_current_time = original_get_time  # type: ignore[method-assign]

    @pytest.mark.asyncio
    async def test_periodic_cleanup(self):
        """Test periodic cleanup functionality."""
        client_id = "test-client"

        # Add some data
        await self.protector.check_rate_limit(client_id)
        request_id = await self.protector.start_request(client_id)

        # Mock time to trigger cleanup
        original_get_time = self.protector._get_current_time
        start_time = self.protector._last_cleanup

        def mock_get_time():
            return start_time + 70.0  # Beyond cleanup interval

        self.protector._get_current_time = mock_get_time  # type: ignore[method-assign]

        try:
            # Trigger periodic cleanup
            await self.protector.periodic_cleanup()

            # Verify cleanup timestamp updated
            assert self.protector._last_cleanup > start_time

        finally:
            self.protector._get_current_time = original_get_time  # type: ignore[method-assign]

    @pytest.mark.asyncio
    async def test_multiple_clients_isolation(self):
        """Test that different clients are properly isolated."""
        client1 = "client-1"
        client2 = "client-2"

        # Client 1 reaches rate limit
        for _ in range(5):
            await self.protector.check_rate_limit(client1)

        # Client 1 should be blocked
        blocked = await self.protector.check_rate_limit(client1)
        assert not blocked

        # Client 2 should still be allowed
        allowed = await self.protector.check_rate_limit(client2)
        assert allowed


class TestDoSProtectorClientTracking:
    """Bounds on the per-client tracking tables.

    Client keys are derived from caller identity, so a caller that can vary its
    identity can create keys. These tests pin the two properties that keeps safe:
    memory stays bounded, and creating keys cannot buy back rate-limit budget.
    """

    @pytest.mark.asyncio
    async def test_tracking_table_stays_bounded_under_many_clients(self):
        """Distinct client keys never grow the table past the configured cap."""
        protector = DoSProtector(max_requests_per_minute=5, max_tracked_clients=10)

        for index in range(200):
            await protector.check_rate_limit(f"client-{index}")

        assert len(protector._request_history) <= 10

    @pytest.mark.asyncio
    async def test_rate_limited_client_survives_key_spray(self):
        """A client at its limit is not evicted by a spray of new client keys.

        Regression test for an eviction policy that ordered by least-recently-active:
        a client that has just burst to its limit has an older last-request time than
        freshly created keys, so spraying keys would evict the attacker's own entry
        and hand back a clean budget.
        """
        protector = DoSProtector(max_requests_per_minute=5, max_tracked_clients=10)

        for _ in range(5):
            await protector.check_rate_limit("at-limit")
        assert not await protector.check_rate_limit("at-limit")

        # Spray well past the cap, forcing repeated eviction.
        for index in range(200):
            await protector.check_rate_limit(f"spray-{index}")

        assert "at-limit" in protector._request_history
        assert not await protector.check_rate_limit("at-limit")

    @pytest.mark.asyncio
    async def test_expired_entries_are_reclaimed_before_eviction(self):
        """Entries that aged out are dropped rather than evicting a live client."""
        protector = DoSProtector(max_requests_per_minute=5, max_tracked_clients=10)
        current_time = 1000.0
        protector._get_current_time = lambda: current_time  # type: ignore[method-assign]

        # Fill the table to capacity so the next new client triggers eviction.
        for index in range(10):
            await protector.check_rate_limit(f"stale-{index}")
        assert len(protector._request_history) == 10

        # Move past the 60s rate-limit window so every entry above is expired.
        current_time = 1100.0
        await protector.check_rate_limit("fresh")

        # The reclaim pass drops all ten expired entries, so nothing live is lost.
        assert protector._request_history.keys() == {"fresh"}

    @pytest.mark.asyncio
    async def test_default_cap_is_generous_enough_for_real_traffic(self):
        """The default bound is not so tight that ordinary client counts evict."""
        protector = DoSProtector()

        assert protector.max_tracked_clients >= 1000


class TestRequestValidatorIntegration:
    """Integration tests for request validation components."""

    @pytest.mark.asyncio
    async def test_concurrent_slots_are_tracked_and_released(self):
        """Slots occupy and free correctly under the concurrency cap."""
        protector = DoSProtector(max_concurrent_requests=2)
        client_id = "integration-test"

        request1_id = await protector.start_request(client_id)
        request2_id = await protector.start_request(client_id)
        assert len(protector._concurrent_requests[client_id]) == 2

        with pytest.raises(ValueError, match="Too many concurrent requests"):
            await protector.start_request(client_id)

        await protector.complete_request(client_id, request1_id)
        assert len(protector._concurrent_requests[client_id]) == 1

        # A freed slot is reusable.
        request3_id = await protector.start_request(client_id)
        assert request3_id not in (request1_id, request2_id)

    def test_global_instances_available(self):
        """Test that global instances are properly initialized."""
        # Verify global instances exist and are correct type
        assert isinstance(request_size_validator, RequestSizeValidator)
        assert isinstance(dos_protector, DoSProtector)

        # Verify they have reasonable default configurations
        assert request_size_validator.max_tool_result_size > 0
        assert dos_protector.max_requests_per_minute > 0

    @pytest.mark.asyncio
    async def test_stress_testing(self):
        """Basic stress test for request validation."""
        protector = DoSProtector(
            max_requests_per_minute=100, max_concurrent_requests=50
        )

        client_id = "stress-test"

        # Simulate multiple rapid requests
        tasks = []
        for i in range(20):

            async def make_request(req_num):
                if await protector.check_rate_limit(client_id):
                    request_id = await protector.start_request(client_id)

                    # Simulate work
                    await asyncio.sleep(0.01)

                    await protector.complete_request(client_id, request_id)

            tasks.append(make_request(i))

        # Should complete without errors
        await asyncio.gather(*tasks, return_exceptions=True)

        # Every slot taken was given back.
        assert protector._concurrent_requests[client_id] == {}

    @pytest.mark.asyncio
    async def test_error_recovery(self):
        """Completing an unknown or already-completed request must not error."""
        protector = DoSProtector()

        client_id = "error-test"

        request_id = await protector.start_request(client_id)

        await protector.complete_request(client_id, request_id)
        await protector.complete_request(client_id, request_id)  # Should not error

        # Should still work after errors
        new_request_id = await protector.start_request(client_id)
        assert new_request_id is not None
