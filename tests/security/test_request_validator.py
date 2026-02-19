"""Tests for request validation and DoS protection."""

import asyncio
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
            max_request_params_size=200,  # 200B for testing
            max_concurrent_memory_mb=1,  # 1MB for testing
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

    def test_request_params_size_validation_success(self):
        """Test successful request parameters validation."""
        small_params = {"key": "value", "num": 42}
        # Should not raise exception
        self.validator.validate_request_params_size(small_params)

    def test_request_params_size_validation_failure(self):
        """Test request parameters size limit enforcement."""
        large_params = {"large_key": "x" * 300}  # Over 200B limit
        with pytest.raises(ValueError, match="Request parameters exceed size limit"):
            self.validator.validate_request_params_size(large_params)

    def test_concurrent_memory_validation_success(self):
        """Test successful concurrent memory validation."""
        request_sizes = [100, 200, 300]  # Total: 600B, under 1MB limit
        # Should not raise exception
        self.validator.validate_concurrent_memory_usage(request_sizes)

    def test_concurrent_memory_validation_failure(self):
        """Test concurrent memory limit enforcement."""
        request_sizes = [500000, 600000]  # Total: 1.1MB, over 1MB limit
        with pytest.raises(
            ValueError, match="Total concurrent memory usage exceeds limit"
        ):
            self.validator.validate_concurrent_memory_usage(request_sizes)

    @pytest.mark.asyncio
    async def test_request_tracking_lifecycle(self):
        """Test complete request tracking lifecycle."""
        request_id = "test-request-123"
        size = 1000

        # Start tracking
        await self.validator.start_request_tracking(request_id, size)

        # Verify memory usage
        current_usage = await self.validator.get_current_memory_usage()
        assert current_usage == size

        # Complete tracking
        await self.validator.complete_request_tracking(request_id)

        # Verify memory freed
        current_usage = await self.validator.get_current_memory_usage()
        assert current_usage == 0

    @pytest.mark.asyncio
    async def test_multiple_request_tracking(self):
        """Test tracking multiple concurrent requests."""
        requests = [
            ("req1", 100),
            ("req2", 200),
            ("req3", 300),
        ]

        # Start tracking all requests
        for req_id, size in requests:
            await self.validator.start_request_tracking(req_id, size)

        # Verify total memory usage
        current_usage = await self.validator.get_current_memory_usage()
        assert current_usage == 600

        # Complete one request
        await self.validator.complete_request_tracking("req2")

        # Verify reduced memory usage
        current_usage = await self.validator.get_current_memory_usage()
        assert current_usage == 400

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
        nested = {"level": 1}
        for i in range(2, 1000):  # Create very deep nesting
            nested = {"level": i, "nested": nested}

        # Should not crash or take too long
        size = self.validator._calculate_content_size(nested)
        assert isinstance(size, int)
        assert size > 0

    def test_content_size_calculation_circular_reference(self):
        """Test content size calculation with circular references."""
        # Create circular reference
        obj1 = {"name": "obj1"}
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
        problematic_obj.__str__ = Mock(side_effect=Exception("Mock error"))
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
            request_timeout_seconds=2,
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

    @pytest.mark.asyncio
    async def test_request_timeout_cleanup(self):
        """Test automatic cleanup of timed-out requests."""
        client_id = "test-client"

        # Mock current time to simulate timeout
        original_get_time = self.protector._get_current_time
        mock_time = 1000.0

        def mock_get_time():
            return mock_time

        self.protector._get_current_time = mock_get_time

        try:
            # Start a request
            request_id = await self.protector.start_request(client_id)

            # Advance time beyond timeout
            mock_time += 5.0  # 5 seconds > 2 second timeout

            # Start another request (should trigger cleanup)
            await self.protector.start_request(client_id)

            # Verify stats show cleanup happened
            stats = await self.protector.get_client_stats(client_id)
            assert stats["concurrent_requests"] == 1  # Old request cleaned up

        finally:
            # Restore original time function
            self.protector._get_current_time = original_get_time

    @pytest.mark.asyncio
    async def test_client_stats(self):
        """Test client statistics retrieval."""
        client_id = "test-client"

        # Initial stats
        stats = await self.protector.get_client_stats(client_id)
        assert stats["requests_last_minute"] == 0
        assert stats["concurrent_requests"] == 0
        assert stats["rate_limit"] == 5
        assert stats["concurrent_limit"] == 3

        # After making requests
        await self.protector.check_rate_limit(client_id)
        await self.protector.check_rate_limit(client_id)
        request_id = await self.protector.start_request(client_id)

        stats = await self.protector.get_client_stats(client_id)
        assert stats["requests_last_minute"] == 2
        assert stats["concurrent_requests"] == 1

    @pytest.mark.asyncio
    async def test_rate_limit_cleanup(self):
        """Test rate limit history cleanup."""
        client_id = "test-client"

        # Mock time control
        mock_time = 1000.0
        original_get_time = self.protector._get_current_time

        def get_mock_time():
            return mock_time

        self.protector._get_current_time = get_mock_time

        try:
            # Make requests
            for _ in range(3):
                await self.protector.check_rate_limit(client_id)

            # Advance time by more than 60 seconds
            mock_time += 70.0

            # Make another request (should trigger cleanup)
            await self.protector.check_rate_limit(client_id)

            # Verify old requests were cleaned up
            stats = await self.protector.get_client_stats(client_id)
            assert stats["requests_last_minute"] == 1  # Only latest request

        finally:
            self.protector._get_current_time = original_get_time

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

        self.protector._get_current_time = mock_get_time

        try:
            # Trigger periodic cleanup
            await self.protector.periodic_cleanup()

            # Verify cleanup timestamp updated
            assert self.protector._last_cleanup > start_time

        finally:
            self.protector._get_current_time = original_get_time

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

    def test_request_timeout_detection(self):
        """Test request timeout detection."""
        client_id = "test-client"
        request_id = "test-request"

        # Mock a timed-out request
        mock_time = 1000.0
        self.protector._concurrent_requests[client_id] = {request_id: mock_time}

        original_get_time = self.protector._get_current_time

        def mock_get_time():
            return mock_time + 5.0  # 5 seconds > 2 second timeout

        self.protector._get_current_time = mock_get_time

        try:
            # Should detect timeout
            is_timed_out = self.protector._is_request_timed_out(client_id, request_id)
            assert is_timed_out

            # Non-existent request should not be timed out
            is_timed_out = self.protector._is_request_timed_out(
                "other-client", "other-req"
            )
            assert not is_timed_out

        finally:
            self.protector._get_current_time = original_get_time


class TestRequestValidatorIntegration:
    """Integration tests for request validation components."""

    @pytest.mark.asyncio
    async def test_validator_integration(self):
        """Test integration between size validator and DoS protector."""
        size_validator = RequestSizeValidator(max_concurrent_memory_mb=1)
        dos_protector = DoSProtector(max_concurrent_requests=2)

        client_id = "integration-test"

        # Start requests with size tracking
        request1_id = await dos_protector.start_request(client_id)
        await size_validator.start_request_tracking(request1_id, 500000)  # 500KB

        request2_id = await dos_protector.start_request(client_id)
        await size_validator.start_request_tracking(request2_id, 400000)  # 400KB

        # Verify memory usage
        memory_usage = await size_validator.get_current_memory_usage()
        assert memory_usage == 900000

        # Complete requests
        await dos_protector.complete_request(client_id, request1_id)
        await size_validator.complete_request_tracking(request1_id)

        # Verify memory reduced
        memory_usage = await size_validator.get_current_memory_usage()
        assert memory_usage == 400000

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
        validator = RequestSizeValidator()
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
                    await validator.start_request_tracking(request_id, 1000)

                    # Simulate work
                    await asyncio.sleep(0.01)

                    await protector.complete_request(client_id, request_id)
                    await validator.complete_request_tracking(request_id)

            tasks.append(make_request(i))

        # Should complete without errors
        await asyncio.gather(*tasks, return_exceptions=True)

        # Verify cleanup
        memory_usage = await validator.get_current_memory_usage()
        assert memory_usage == 0

    @pytest.mark.asyncio
    async def test_error_recovery(self):
        """Test error recovery in request validation."""
        validator = RequestSizeValidator()
        protector = DoSProtector()

        client_id = "error-test"

        # Start request
        request_id = await protector.start_request(client_id)
        await validator.start_request_tracking(request_id, 1000)

        # Simulate error by completing tracking multiple times
        await validator.complete_request_tracking(request_id)
        await validator.complete_request_tracking(request_id)  # Should not error

        # Should still work after errors
        new_request_id = await protector.start_request(client_id)
        assert new_request_id is not None
