"""Tests for the new standardized error handling and recovery mechanisms."""

import asyncio
import time

import pytest

from finos_mcp.error_boundary import (
    CircuitBreaker,
    ErrorRecoveryContext,
    error_boundary,
    get_error_recovery_context,
    safe_async_operation,
    with_retry,
)
from finos_mcp.exceptions import (
    ContentLoadingError,
    ContentNotFoundError,
    HTTPClientError,
    MCPServerError,
    RateLimitExceededError,
    ServiceUnavailableError,
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

        # RateLimitExceededError
        rate_error = RateLimitExceededError("client-123", "requests_per_minute", 50, 30)
        assert rate_error.error_code == "RATE_LIMIT_EXCEEDED"
        assert rate_error.recoverable is False
        assert "client-123" in rate_error.message


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_success(self):
        """Test circuit breaker allows successful operations."""
        circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1)

        @circuit_breaker
        async def successful_operation():
            return "success"

        result = await successful_operation()
        assert result == "success"
        assert circuit_breaker.state == "closed"
        assert circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_threshold(self):
        """Test circuit breaker opens after failure threshold."""
        circuit_breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1)

        @circuit_breaker
        async def failing_operation():
            raise ValueError("Simulated failure")

        # First failure
        with pytest.raises(ValueError):
            await failing_operation()
        assert circuit_breaker.state == "closed"
        assert circuit_breaker.failure_count == 1

        # Second failure - should open circuit
        with pytest.raises(ValueError):
            await failing_operation()
        assert circuit_breaker.state == "open"
        assert circuit_breaker.failure_count == 2

        # Third call should be blocked by circuit breaker
        from finos_mcp.exceptions import CircuitBreakerError

        with pytest.raises(CircuitBreakerError):
            await failing_operation()

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery after timeout."""
        circuit_breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        call_count = 0

        @circuit_breaker
        async def operation_that_recovers():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First failure")
            return "success"

        # First call fails and opens circuit
        with pytest.raises(ValueError):
            await operation_that_recovers()
        assert circuit_breaker.state == "open"

        # Wait for recovery timeout
        await asyncio.sleep(0.2)

        # Next call should succeed and close circuit
        result = await operation_that_recovers()
        assert result == "success"
        assert circuit_breaker.state == "closed"


class TestRetryDecorator:
    """Test retry mechanism with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retry_success_on_first_attempt(self):
        """Test retry decorator when function succeeds immediately."""

        @with_retry(max_attempts=3)
        async def successful_function():
            return "success"

        result = await successful_function()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self):
        """Test retry succeeds after some failures."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)  # Fast retry for testing
        async def function_succeeds_on_third_try():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ContentLoadingError("source", "temporary failure")
            return "success"

        result = await function_succeeds_on_third_try()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_failure_after_max_attempts(self):
        """Test retry fails after exhausting max attempts."""
        call_count = 0

        @with_retry(max_attempts=2, base_delay=0.01)
        async def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise HTTPClientError("http://example.com", 500, "Server error")

        with pytest.raises(HTTPClientError):
            await always_failing_function()
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_non_retryable_exception(self):
        """Test retry doesn't retry non-retryable exceptions."""
        call_count = 0

        @with_retry(max_attempts=3)
        async def function_with_non_retryable_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("This should not be retried")

        with pytest.raises(ValueError):
            await function_with_non_retryable_error()
        assert call_count == 1  # Should only be called once


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

    @pytest.mark.asyncio
    async def test_error_boundary_suppression(self):
        """Test error boundary can suppress exceptions."""
        async with error_boundary("test_operation", suppress_exceptions=True):
            raise ValueError("This should be suppressed")
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


class TestSafeAsyncOperation:
    """Test safe async operation decorator."""

    @pytest.mark.asyncio
    async def test_safe_operation_success(self):
        """Test safe operation returns result on success."""

        @safe_async_operation("test_operation")
        async def successful_operation():
            return "success"

        result = await successful_operation()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_safe_operation_failure_with_fallback(self):
        """Test safe operation returns fallback on failure."""

        @safe_async_operation("test_operation", fallback_value="fallback")
        async def failing_operation():
            raise ValueError("Simulated failure")

        result = await failing_operation()
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_safe_operation_failure_without_fallback(self):
        """Test safe operation returns None on failure without fallback."""

        @safe_async_operation("test_operation")
        async def failing_operation():
            raise ContentLoadingError("source", "failure")

        result = await failing_operation()
        assert result is None

    @pytest.mark.asyncio
    async def test_safe_operation_no_logging(self):
        """Test safe operation can disable error logging."""

        @safe_async_operation("test_operation", log_errors=False)
        async def failing_operation():
            raise ValueError("This error should not be logged")

        result = await failing_operation()
        assert result is None


class TestErrorRecoveryContext:
    """Test error recovery context management."""

    def test_error_recovery_context_singleton(self):
        """Test error recovery context is a singleton."""
        context1 = get_error_recovery_context()
        context2 = get_error_recovery_context()
        assert context1 is context2

    def test_should_attempt_recovery_initial(self):
        """Test recovery is allowed initially."""
        context = ErrorRecoveryContext()
        assert context.should_attempt_recovery("test_operation") is True

    def test_should_attempt_recovery_after_failures(self):
        """Test recovery attempts are limited."""
        context = ErrorRecoveryContext()

        # Record multiple failures
        for _ in range(3):
            context.record_recovery_attempt("test_operation", success=False)

        # Should not allow more attempts
        assert (
            context.should_attempt_recovery("test_operation", max_attempts=3) is False
        )

    def test_should_attempt_recovery_after_cooldown(self):
        """Test recovery is allowed after cooldown period."""
        context = ErrorRecoveryContext()

        # Record failure and set old timestamp
        context.record_recovery_attempt("test_operation", success=False)
        context.last_errors["test_operation"] = time.time() - 400  # 400 seconds ago

        # Should allow recovery after cooldown
        assert context.should_attempt_recovery("test_operation", cooldown=300) is True

    def test_recovery_attempt_reset_on_success(self):
        """Test recovery counters reset on success."""
        context = ErrorRecoveryContext()

        # Record failures
        context.record_recovery_attempt("test_operation", success=False)
        context.record_recovery_attempt("test_operation", success=False)
        assert context.recovery_attempts.get("test_operation", 0) == 2

        # Record success
        context.record_recovery_attempt("test_operation", success=True)
        assert context.recovery_attempts.get("test_operation", 0) == 0


class TestIntegratedErrorHandling:
    """Test integrated error handling scenarios."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_retry(self):
        """Test circuit breaker and retry working together."""
        from finos_mcp.exceptions import CircuitBreakerError

        circuit_breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        call_count = 0

        # Add CircuitBreakerError to retryable exceptions for this test
        @with_retry(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(
                ContentLoadingError,
                HTTPClientError,
                ServiceUnavailableError,
                CircuitBreakerError,
            ),
        )
        @circuit_breaker
        async def complex_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                raise ContentLoadingError("source", "failure")
            return "success"

        # Circuit breaker will open, but retry will eventually get CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            await complex_operation()

    @pytest.mark.asyncio
    async def test_error_boundary_with_safe_operation(self):
        """Test error boundary and safe operation integration."""

        @safe_async_operation("test_op", fallback_value="safe_fallback")
        async def risky_operation():
            async with error_boundary("inner_operation"):
                raise ValueError("Test error")

        result = await risky_operation()
        assert result == "safe_fallback"

    @pytest.mark.asyncio
    async def test_full_error_handling_stack(self):
        """Test complete error handling stack."""
        circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=1)
        call_count = 0

        @safe_async_operation("safe_op", fallback_value="ultimate_fallback")
        @with_retry(max_attempts=2, base_delay=0.01)
        @circuit_breaker
        async def complex_operation_with_recovery():
            nonlocal call_count
            call_count += 1
            async with error_boundary("complex_op"):
                if call_count == 1:
                    raise HTTPClientError("http://example.com", 500)
                elif call_count == 2:
                    raise ContentLoadingError("source", "temp failure")
                else:
                    return "finally_success"

        result = await complex_operation_with_recovery()
        # Should either succeed or return fallback
        assert result in ["finally_success", "ultimate_fallback"]
