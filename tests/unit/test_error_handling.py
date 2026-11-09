"""Tests for the new standardized error handling and recovery mechanisms."""

import asyncio

import pytest

from finos_mcp.error_boundary import CircuitBreaker, error_boundary
from finos_mcp.exceptions import (
    ContentLoadingError,
    ContentNotFoundError,
    MCPServerError,
    ToolExecutionError,
)


class TestMCPServerError:
    """Test structured exception base class."""

    def test_basic_error_creation(self):
        """Test basic error creation and properties."""
        error = MCPServerError(
            message="Test error",
            error_code="TEST_ERROR",
            context={"test": "value"},
            recoverable=True,
        )

        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.error_code == "TEST_ERROR"
        assert error.context == {"test": "value"}
        assert error.recoverable is True

    def test_error_to_dict(self):
        """Test error serialization to dictionary."""
        error = MCPServerError(
            message="Test error",
            error_code="TEST_ERROR",
            context={"test": "value"},
            recoverable=False,
        )

        error_dict = error.to_dict()
        expected = {
            "error_type": "MCPServerError",
            "message": "Test error",
            "error_code": "TEST_ERROR",
            "context": {"test": "value"},
            "recoverable": False,
        }

        assert error_dict == expected

    def test_derived_error_classes(self):
        """Test specific error classes work correctly."""
        # ContentNotFoundError
        content_error = ContentNotFoundError("test-resource", "framework")
        assert content_error.error_code == "CONTENT_NOT_FOUND"
        assert content_error.recoverable is False
        assert "test-resource" in content_error.message

        # ContentLoadingError
        loading_error = ContentLoadingError("github", "API rate limit", retry_after=60)
        assert loading_error.error_code == "CONTENT_LOADING_FAILED"
        assert loading_error.recoverable is True
        assert loading_error.context["retry_after"] == 60


class TestCircuitBreaker:
    """The breaker as the fetch client drives it: ask, then report (#376)."""

    def test_a_success_keeps_it_closed(self):
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1)

        assert breaker.can_execute()
        breaker.on_success()

        assert breaker.state == "closed"
        assert breaker.failure_count == 0

    def test_it_opens_at_the_failure_threshold_and_refuses(self):
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1)

        breaker.on_failure("first")
        assert breaker.state == "closed"
        assert breaker.failure_count == 1
        assert breaker.can_execute()

        breaker.on_failure("second")
        assert breaker.state == "open"
        assert breaker.failure_count == 2
        assert not breaker.can_execute()

    async def test_it_lets_one_call_through_after_the_timeout_and_closes_on_success(
        self,
    ):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        breaker.on_failure("first")
        assert not breaker.can_execute()

        await asyncio.sleep(0.2)

        assert breaker.can_execute()
        assert breaker.state == "half-open"
        breaker.on_success()
        assert breaker.state == "closed"


class TestErrorBoundary:
    """Test error boundary context manager."""

    @pytest.mark.asyncio
    async def test_error_boundary_success(self):
        """Test error boundary allows successful operations."""
        async with error_boundary("test_operation"):
            result = "success"
        assert result == "success"

    @pytest.mark.asyncio
    async def test_error_boundary_structured_exception(self):
        """Test error boundary handles structured exceptions."""
        with pytest.raises(ContentNotFoundError):
            async with error_boundary("test_operation"):
                raise ContentNotFoundError("test-resource")

    @pytest.mark.asyncio
    async def test_error_boundary_unstructured_exception(self):
        """Test error boundary converts unstructured exceptions."""
        with pytest.raises(ToolExecutionError) as exc_info:
            async with error_boundary("test_operation"):
                raise ValueError("Unexpected error")

        assert exc_info.value.error_code == "TOOL_EXECUTION_FAILED"
        assert "ValueError" in exc_info.value.message

        # Should not raise exception

    @pytest.mark.asyncio
    async def test_error_boundary_with_context(self):
        """Test error boundary includes context in error reporting."""
        with pytest.raises(ToolExecutionError) as exc_info:
            async with error_boundary(
                "test_operation", context={"user_id": "123", "action": "test"}
            ):
                raise RuntimeError("Context test")

        assert exc_info.value.context["user_id"] == "123"
        assert exc_info.value.context["action"] == "test"
