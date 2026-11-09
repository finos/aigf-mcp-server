"""
Test suite for ContentService - comprehensive tests for content orchestration.

This module tests the actual ContentService implementation instead of mocking it,
to achieve proper code coverage for the content service functionality.
"""

import logging
import time
from unittest.mock import AsyncMock, patch

import pytest

from finos_mcp import service as facade_module
from finos_mcp.content import cache as cache_module
from finos_mcp.content import fetch as fetch_module
from finos_mcp.content import service as service_module
from finos_mcp.content.service import (
    ContentService,
    ContentServiceManager,
    OperationContext,
    OperationResult,
    ServiceHealth,
    ServiceStatus,
    close_content_service,
    get_content_service,
)
from finos_mcp.fastmcp_main import cleanup_resources


@pytest.mark.unit
class TestContentServiceInitialization:
    """Test ContentService initialization and configuration."""

    def test_content_service_init(self):
        """Test basic ContentService initialization."""
        with patch("finos_mcp.content.service.asyncio.create_task"):
            service = ContentService()

            # Verify initialization
            assert service.total_requests == 0
            assert service.successful_requests == 0
            assert service.failed_requests == 0
            assert service.circuit_breaker_trips == 0
            assert service.start_time is not None
            assert isinstance(service.start_time, float)

            # No components of its own until given some
            assert service._http_client is None
            assert service._cache is None

    def test_service_status_enum(self):
        """Test ServiceStatus enum values."""
        assert ServiceStatus.HEALTHY.value == "healthy"
        assert ServiceStatus.DEGRADED.value == "degraded"
        assert ServiceStatus.FAILING.value == "failing"
        assert ServiceStatus.CRITICAL.value == "critical"

    def test_operation_result_enum(self):
        """Test OperationResult enum values."""
        assert OperationResult.SUCCESS.value == "success"
        assert OperationResult.CACHE_HIT.value == "cache_hit"
        assert OperationResult.FAILURE.value == "failure"


@pytest.mark.unit
class TestServiceHealth:
    """Test ServiceHealth tracking functionality."""

    def test_service_health_creation(self):
        """Test ServiceHealth object creation."""
        health = ServiceHealth(
            status=ServiceStatus.HEALTHY,
            uptime_seconds=3600.0,
            success_rate=0.9,
            last_error=None,
            last_error_time=None,
            total_requests=100,
            successful_requests=90,
            failed_requests=10,
            circuit_breaker_trips=1,
            cache_hit_rate=0.8,
        )

        assert health.status == ServiceStatus.HEALTHY
        assert health.total_requests == 100
        assert health.successful_requests == 90
        assert health.failed_requests == 10
        assert health.circuit_breaker_trips == 1
        assert health.uptime_seconds == 3600.0
        assert health.success_rate == 0.9
        assert health.cache_hit_rate == 0.8

    def test_service_health_to_dict(self):
        """Test ServiceHealth to_dict conversion."""
        health = ServiceHealth(
            status=ServiceStatus.DEGRADED,
            uptime_seconds=1800.0,
            success_rate=0.8,
            last_error="Test error",
            last_error_time=time.time(),
            total_requests=50,
            successful_requests=40,
            failed_requests=10,
            circuit_breaker_trips=2,
            cache_hit_rate=0.75,
        )

        health_dict = health.to_dict()

        assert health_dict["status"] == "degraded"
        assert health_dict["total_requests"] == 50
        assert health_dict["successful_requests"] == 40
        assert health_dict["failed_requests"] == 10
        assert health_dict["circuit_breaker_trips"] == 2
        assert health_dict["uptime_seconds"] == 1800.0
        assert health_dict["success_rate"] == 0.8
        assert health_dict["cache_hit_rate"] == 0.75


@pytest.mark.unit
class TestOperationContext:
    """Test OperationContext functionality."""

    def test_operation_context_creation(self):
        """Test OperationContext initialization."""
        context = OperationContext(
            operation_id="test-op-123",
            doc_type="mitigation",
            filename="test.md",
            url="https://example.com/test.md",
            start_time=time.time(),
            correlation_id="test-123",
        )

        assert context.operation_id == "test-op-123"
        assert context.doc_type == "mitigation"
        assert context.filename == "test.md"
        assert context.url == "https://example.com/test.md"
        assert context.correlation_id == "test-123"
        assert context.start_time is not None
        assert isinstance(context.start_time, float)


@pytest.mark.unit
class TestContentServiceOperations:
    """Test ContentService main operations."""

    @pytest.fixture
    async def service(self):
        """Create a ContentService instance for testing with proper cleanup."""
        with patch("finos_mcp.content.service.asyncio.create_task"):
            service_instance = ContentService()
            yield service_instance
            # Ensure proper cleanup after each test
            try:
                await service_instance.close()
            except Exception:  # noqa: S110
                # Ignore cleanup errors in tests - exceptions during test cleanup are expected
                pass

    @pytest.mark.asyncio
    async def test_get_health_status(self, service):
        """Test health status reporting."""
        # Set some statistics
        service.total_requests = 100
        service.successful_requests = 85
        service.failed_requests = 15

        # Two failures of the content host, as the HTTP client's breaker counts
        # them
        breaker = await service.content_host_breaker()
        breaker.on_failure("fetch failed")
        breaker.on_failure("fetch failed")

        health = await service.get_health_status()

        assert isinstance(health, ServiceHealth)
        assert health.total_requests == 100
        assert health.successful_requests == 85
        assert health.failed_requests == 15
        assert health.circuit_breaker_trips == 2
        assert health.success_rate == 0.85
        assert health.uptime_seconds > 0

    @pytest.mark.asyncio
    async def test_get_health_status_determines_status(self, service):
        """Test health status determination based on success rate."""
        # Test healthy status (>= 90% success rate)
        service.total_requests = 100
        service.successful_requests = 95
        service.failed_requests = 5
        health = await service.get_health_status()
        assert health.status == ServiceStatus.HEALTHY

        # Test degraded status (>= 70% success rate)
        service.successful_requests = 75
        service.failed_requests = 25
        health = await service.get_health_status()
        assert health.status == ServiceStatus.DEGRADED

        # Test failing status (>= 50% success rate)
        service.successful_requests = 55
        service.failed_requests = 45
        health = await service.get_health_status()
        assert health.status == ServiceStatus.FAILING

        # Test critical status (< 50% success rate)
        service.successful_requests = 30
        service.failed_requests = 70
        health = await service.get_health_status()
        assert health.status == ServiceStatus.CRITICAL

    @pytest.mark.asyncio
    async def test_get_service_diagnostics(self, service):
        """Test service diagnostics retrieval."""
        diagnostics = await service.get_service_diagnostics()

        assert "service_health" in diagnostics
        assert "cache_statistics" in diagnostics
        assert "error_boundaries" in diagnostics
        # cache_warming_statistics removed from service diagnostics

        # Verify structure
        assert isinstance(diagnostics["service_health"], dict)
        assert isinstance(diagnostics["cache_statistics"], dict)
        assert isinstance(diagnostics["error_boundaries"], dict)
        # cache_warming_statistics removed from diagnostics

    @pytest.mark.asyncio
    async def test_cache_statistics_via_diagnostics(self, service):
        """Test cache statistics access through get_service_diagnostics."""
        # Ensure cache is enabled and initialized
        service.settings.enable_cache = True
        await service._get_cache()  # Initialize cache

        diagnostics = await service.get_service_diagnostics()

        # Verify cache statistics are included in diagnostics
        assert "cache_statistics" in diagnostics
        cache_stats = diagnostics["cache_statistics"]

        # Verify expected cache statistics structure (based on actual implementation)
        expected_keys = {"hits", "misses", "hit_rate", "current_size", "max_size"}
        assert set(cache_stats.keys()).issuperset(expected_keys)

        # Verify data types
        assert isinstance(cache_stats["hits"], int)
        assert isinstance(cache_stats["misses"], int)
        assert isinstance(cache_stats["hit_rate"], int | float)
        assert isinstance(cache_stats["current_size"], int)
        assert isinstance(cache_stats["max_size"], int)

    # Cache warming stats test removed - functionality no longer exists


@pytest.mark.unit
class TestGetDocumentFunctionality:
    """Test the core get_document functionality to boost coverage."""

    @pytest.fixture
    async def service(self):
        """Create a ContentService instance for testing with proper cleanup."""
        with patch("finos_mcp.content.service.asyncio.create_task"):
            service_instance = ContentService()
            yield service_instance
            try:
                await service_instance.close()
            except Exception:  # noqa: S110
                # Ignore cleanup errors in tests - exceptions during test cleanup are expected
                pass

    @pytest.mark.asyncio
    async def test_a_parse_failure_is_raised_and_counted(self, service):
        """It escaped get_document without touching failed_requests (#366)."""
        from finos_mcp.exceptions import ContentValidationError

        with (
            patch.object(service, "_cache_get_with_boundary", return_value=None),
            patch.object(
                service,
                "_fetch_content_with_boundary",
                return_value="---\nt: a\n---\nb",
            ),
            patch(
                "finos_mcp.content.service.parse_frontmatter",
                side_effect=ValueError("broken"),
            ),
        ):
            with pytest.raises(ContentValidationError):
                await service.get_document("risk", "ri-1_x.md")

        assert service.failed_requests == 1
        assert service.successful_requests == 0

    @pytest.mark.asyncio
    async def test_get_document_mitigation_success(self, service):
        """Test successful mitigation document retrieval."""
        with (
            patch.object(service, "_fetch_content_with_boundary") as mock_fetch,
            patch.object(service, "_parse_content_with_boundary") as mock_parse,
            patch.object(service, "_cache_set_with_boundary") as mock_cache_set,
        ):
            # Mock successful responses
            mock_fetch.return_value = "---\ntitle: Test Mitigation\n---\nContent"
            mock_parse.return_value = (
                {"title": "Test Mitigation", "metadata": {"type": "mitigation"}},
                "Content",
            )
            mock_cache_set.return_value = None

            result = await service.get_document("mitigation", "test-file.md")

            assert result is not None
            assert result["filename"] == "test-file.md"
            assert result["type"] == "mitigation"
            assert result["metadata"]["title"] == "Test Mitigation"
            assert result["content"] == "Content"

            # Verify the correct URL was constructed
            mock_fetch.assert_called_once()
            call_args = mock_fetch.call_args[0]
            assert "test-file.md" in call_args[0]  # URL contains filename

    @pytest.mark.asyncio
    async def test_get_document_risk_success(self, service):
        """Test successful risk document retrieval."""
        with (
            patch.object(service, "_fetch_content_with_boundary") as mock_fetch,
            patch.object(service, "_parse_content_with_boundary") as mock_parse,
            patch.object(service, "_cache_set_with_boundary") as mock_cache_set,
        ):
            mock_fetch.return_value = "---\ntitle: Test Risk\n---\nRisk content"
            mock_parse.return_value = (
                {"title": "Test Risk", "metadata": {"type": "risk"}},
                "Risk content",
            )
            mock_cache_set.return_value = None

            result = await service.get_document("risk", "test-risk.md")

            assert result is not None
            assert result["filename"] == "test-risk.md"
            assert result["type"] == "risk"
            assert result["metadata"]["title"] == "Test Risk"
            assert result["content"] == "Risk content"

            # Verify risk URL was used
            mock_fetch.assert_called_once()
            call_args = mock_fetch.call_args[0]
            assert "test-risk.md" in call_args[0]

    @pytest.mark.asyncio
    async def test_get_document_with_ttl_override(self, service):
        """Test document retrieval with custom TTL."""
        with (
            patch.object(service, "_cache_get_with_boundary") as mock_cache_get,
            patch.object(service, "_fetch_content_with_boundary") as mock_fetch,
            patch.object(service, "_parse_content_with_boundary") as mock_parse,
            patch.object(service, "_cache_set_with_boundary") as mock_cache_set,
        ):
            # Mock cache miss
            mock_cache_get.return_value = None
            mock_fetch.return_value = "---\ntitle: Test\n---\nContent"
            mock_parse.return_value = ({"title": "Test"}, "Content")
            mock_cache_set.return_value = None

            result = await service.get_document(
                "mitigation", "test.md", ttl_override=7200
            )

            assert result is not None
            # Verify TTL override was passed to cache operations
            mock_cache_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_document_fetch_failure(self, service):
        """Test document retrieval when fetch fails.

        The one fetch route is patched (#312 removed the Contents API fallback
        that used to make this test reach api.github.com, see #119).
        """
        with (
            patch.object(service, "_cache_get_with_boundary") as mock_cache_get,
            patch.object(service, "_fetch_content_with_boundary") as mock_fetch,
        ):
            mock_cache_get.return_value = None  # Cache miss
            mock_fetch.return_value = None  # content host failure

            result = await service.get_document("mitigation", "missing-file.md")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_document_parse_failure(self, service):
        """Test document retrieval when parsing fails."""
        with (
            patch.object(service, "_cache_get_with_boundary") as mock_cache_get,
            patch.object(service, "_fetch_content_with_boundary") as mock_fetch,
            patch.object(service, "_parse_content_with_boundary") as mock_parse,
        ):
            mock_cache_get.return_value = None
            mock_fetch.return_value = "invalid content"
            mock_parse.return_value = None  # Parse failure

            result = await service.get_document("mitigation", "bad-file.md")

            assert result is None


@pytest.mark.unit
class TestErrorBoundaryProtection:
    """Test error boundary protection functionality to boost coverage."""

    @pytest.fixture
    async def service(self):
        """Create a ContentService instance for testing with proper cleanup."""
        with patch("finos_mcp.content.service.asyncio.create_task"):
            service_instance = ContentService()
            yield service_instance
            try:
                await service_instance.close()
            except Exception:  # noqa: S110
                # Ignore cleanup errors in tests - exceptions during test cleanup are expected
                pass

    @pytest.mark.asyncio
    async def test_the_content_host_breaker_is_the_http_clients(self, service):
        """The service reads the HTTP client's per-host breaker; it keeps none."""
        breaker = await service.content_host_breaker()
        client = await service._get_http_client()

        assert breaker is client.circuit_breaker(service.settings.base_url)
        assert breaker.state == "closed"
        assert not hasattr(service, "fetch_circuit_breaker")

    @pytest.mark.asyncio
    async def test_get_document_cache_hit(self, service):
        """Test get_document with cache hit scenario."""
        cached_doc = {
            "filename": "cached.md",
            "type": "mitigation",
            "metadata": {"title": "Cached Doc"},
            "content": "Cached content",
            "retrieved_at": time.time(),
        }

        with patch.object(service, "_cache_get_with_boundary") as mock_cache_get:
            mock_cache_get.return_value = cached_doc

            result = await service.get_document("mitigation", "cached.md")

            assert result == cached_doc
            mock_cache_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_service_manager_patterns(self, service):
        """Test ContentServiceManager functionality."""
        from finos_mcp.content.service import ContentServiceManager

        # Test singleton behavior
        manager1 = ContentServiceManager()
        manager2 = ContentServiceManager()
        assert manager1 is manager2

        # Test service instance retrieval
        with patch.object(manager1, "_content_service", service):
            instance = await manager1.get_content_service()
            assert instance is service

    @pytest.mark.asyncio
    async def test_operation_context_usage(self, service):
        """Test OperationContext creation and usage."""
        from finos_mcp.content.service import OperationContext

        context = OperationContext(
            operation_id="test-op-123",
            doc_type="mitigation",
            filename="test.md",
            url="https://example.com/test.md",
            start_time=1234567890.0,
            correlation_id="test-corr-456",
            cache_enabled=True,
            ttl_override=3600.0,
        )

        assert context.operation_id == "test-op-123"
        assert context.doc_type == "mitigation"
        assert context.filename == "test.md"
        assert context.url == "https://example.com/test.md"
        assert context.start_time == 1234567890.0
        assert context.correlation_id == "test-corr-456"
        assert context.cache_enabled is True
        assert context.ttl_override == 3600.0


@pytest.mark.unit
class TestContentServiceManager:
    """Test ContentServiceManager functionality."""

    def test_content_service_manager_singleton_pattern(self):
        """Test that ContentServiceManager maintains singleton pattern."""
        manager1 = ContentServiceManager()
        manager2 = ContentServiceManager()

        # Should be the same instance
        assert manager1 is manager2

    @pytest.mark.asyncio
    async def test_get_content_service_function(self):
        """Test the get_content_service function."""
        # Clear any existing service
        ContentServiceManager._instance = None
        # Reset the manager's internal service instance
        manager = ContentServiceManager()
        manager._content_service = None

        service = await get_content_service()

        assert isinstance(service, ContentService)

        # Second call should return the same instance
        service2 = await get_content_service()
        assert service is service2

    @pytest.mark.asyncio
    async def test_close_content_service_function(self):
        """Test the close_content_service function."""
        # Initialize service first
        await get_content_service()

        # Close should not raise exceptions
        await close_content_service()

        # Manager should be reset
        # Verify the service was closed
        manager = ContentServiceManager()
        assert manager._content_service is None


@pytest.mark.unit
class TestErrorBoundaries:
    """Test error boundary functionality."""

    @pytest.fixture
    async def service(self):
        """Create a ContentService instance for testing with proper cleanup."""
        with patch("finos_mcp.content.service.asyncio.create_task"):
            service_instance = ContentService()
            yield service_instance
            try:
                await service_instance.close()
            except Exception:  # noqa: S110
                # Ignore cleanup errors in tests - exceptions during test cleanup are expected
                pass

    @pytest.mark.asyncio
    async def test_error_boundary_stats_in_diagnostics(self, service):
        """The diagnostics report the content host's breaker as the health tool reads it."""
        breaker = await service.content_host_breaker()
        for _ in range(5):
            breaker.on_failure("fetch failed")

        diagnostics = await service.get_service_diagnostics()

        fetch = diagnostics["error_boundaries"]["fetch"]
        assert fetch["status"] == "open"
        assert fetch["failure_count"] == 5
        assert fetch["last_failure_time"] == breaker.last_failure_time

        breaker.on_success()
        diagnostics = await service.get_service_diagnostics()
        assert diagnostics["error_boundaries"]["fetch"]["status"] == "closed"


@pytest.mark.unit
class TestServiceStatistics:
    """Test service statistics tracking."""

    @pytest.fixture
    async def service(self):
        """Create a ContentService instance for testing with proper cleanup."""
        with patch("finos_mcp.content.service.asyncio.create_task"):
            service_instance = ContentService()
            yield service_instance
            try:
                await service_instance.close()
            except Exception:  # noqa: S110
                # Ignore cleanup errors in tests - exceptions during test cleanup are expected
                pass

    def test_initial_statistics(self, service):
        """Test initial statistics values."""
        assert service.total_requests == 0
        assert service.successful_requests == 0
        assert service.failed_requests == 0
        assert service.circuit_breaker_trips == 0

    @pytest.mark.asyncio
    async def test_statistics_tracking(self, service):
        """Test manual statistics updates."""
        # Simulate some operations
        service.total_requests = 10
        service.successful_requests = 8
        service.failed_requests = 2

        # One failure of the content host
        (await service.content_host_breaker()).on_failure("fetch failed")

        health = await service.get_health_status()
        assert health.total_requests == 10
        assert health.successful_requests == 8
        assert health.failed_requests == 2
        assert health.circuit_breaker_trips == 1
        assert health.success_rate == 0.8

    @pytest.mark.asyncio
    async def test_success_rate_calculation_edge_cases(self, service):
        """Test success rate calculation edge cases."""
        # No requests - actual implementation returns 0.0 when no successful requests
        health = await service.get_health_status()
        assert health.success_rate == 0.0  # 0% when no successful requests

        # Only successful requests
        service.total_requests = 5
        service.successful_requests = 5
        service.failed_requests = 0
        health = await service.get_health_status()
        assert health.success_rate == 1.0

        # Only failed requests
        service.successful_requests = 0
        service.failed_requests = 5
        health = await service.get_health_status()
        assert health.success_rate == 0.0


#: The logger this module writes shutdown records to -- both the service and its
#: manager use ``get_logger("content_service")``. Spelled out rather than read off
#: the module, and asserted on each record, because ``caplog.at_level`` names a
#: logger it will happily create if it does not exist: a test naming the wrong
#: one still sees the records via the handler pytest attaches to the
#: non-propagating parent, and passes while pinning nothing.
SERVICE_LOGGER = "finos-ai-governance-mcp.content_service"

#: The logger ``cleanup_resources()`` writes the shutdown summary to. Spelled
#: out for the same reason, and needed here because the summary is the record
#: #100 is about and it is not written by ``service.py``.
CLEANUP_LOGGER = "finos-ai-governance-mcp.fastmcp_main"


@pytest.fixture
def _isolate_global_managers():
    """Empty the cache and HTTP-client singletons, and put them back after.

    Any test that drives the real ``cleanup_resources()`` needs this.
    ``fastmcp_main`` imports its closers from ``.content.cache`` and
    ``.content.fetch`` directly, so patching the names ``service.py`` sees does
    nothing to positions 2 and 3 -- they run the genuine ``close_http_client()``
    and ``close_cache()`` against the process-wide managers.

    Emptying them first is also what makes the composition faithful rather than
    merely safe: on the server's own path position 1 has already cleared both by
    the time positions 2 and 3 run, so ``None`` is the state they really see.
    Restoring afterwards is not optional, and the reason is the two assignments
    below rather than anything ``close_cache()`` does: this fixture nulls
    ``CacheManager``'s cache, loop and lock and ``HTTPClientManager``'s client
    and loop, and without the restore every later test in the process runs
    against emptied managers.

    It used to have a second reason -- position 3 fell through to
    ``_ensure_loop_context()``, which rebound ``CacheManager._loop`` to this
    test's loop and installed a fresh ``asyncio.Lock`` on it (issue #106). The
    early return added for #106 removed that, so do not check the old reason,
    find it no longer holds, and delete the ``finally``; the first reason is
    sufficient on its own.
    """
    cache_manager = cache_module._cache_manager
    http_manager = fetch_module._http_client_manager
    saved_cache = cache_manager._cache
    saved_http = (http_manager._http_client, http_manager._loop)

    cache_manager._cache = None
    http_manager._http_client, http_manager._loop = None, None
    try:
        yield
    finally:
        cache_manager._cache = saved_cache
        http_manager._http_client, http_manager._loop = saved_http


@pytest.mark.unit
class TestContentServiceShutdownReporting:
    """What shutdown says it did, for the resources it is the one that closes.

    ``ContentService.close()`` -- not ``cleanup_resources()`` -- is what closes
    the cache and the HTTP client on the server's own path: ``cleanup_resources()``
    reaches ``close_content_service()`` first, and by the time positions 2 and 3
    run, both singletons are already ``None``. So this is where a shutdown
    transcript is actually written, and where a false claim does its damage.
    """

    @pytest.mark.asyncio
    async def test_close_does_not_claim_the_resources_were_closed(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Returning without raising is not the same as having closed anything.

        Both closers legitimately *discard* their resource and return normally
        when the loop that created it is dead, each saying so at INFO. Reporting
        "Cache closed successfully" on the strength of a clean return put a
        contradiction one line below the truth, in the DEBUG transcript someone
        reads while hunting a resource that outlived the process.
        """
        service = ContentService()

        with (
            patch("finos_mcp.content.service.close_cache", AsyncMock()),
            patch("finos_mcp.content.service.close_http_client", AsyncMock()),
            caplog.at_level(logging.DEBUG, logger=SERVICE_LOGGER),
        ):
            await service.close()

        claims = [
            r.getMessage()
            for r in caplog.records
            if r.name == SERVICE_LOGGER and "closed successfully" in r.getMessage()
        ]
        assert claims == [], (
            f"close() may only report that the call returned, not that the "
            f"resource was closed; got {claims}"
        )

        # A prohibition on its own protects the old phrase from coming back and
        # nothing else: deleting both replacement lines outright left this test,
        # and the whole file, green. What the DEBUG transcript is actually for is
        # showing that each close was reached, so pin the lines that show it.
        returned = [
            r.getMessage()
            for r in caplog.records
            if r.name == SERVICE_LOGGER and r.levelno == logging.DEBUG
        ]
        assert returned == ["Cache close returned", "HTTP client close returned"], (
            f"both closes must be recorded, in order; got {returned}"
        )

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolate_global_managers")
    async def test_a_failed_shutdown_reaches_the_summary_as_an_ERROR(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A resource that failed to close must be visible to `grep ERROR`.

        Driven through the production composition rather than a stub, because
        the stub is what hid this. A bare object whose ``close()`` raises does
        reach ``close_content_service()``'s handler -- but production never puts
        anything except a ``ContentService`` on that manager, and a
        ``ContentService`` catches both of its own awaits. So the only failures a
        real shutdown can have are a failing ``close_cache()`` and a failing
        ``close_http_client()``, and against those the transcript used to read:

            WARNING content_service  Error closing cache: ...
            WARNING content_service  Error closing HTTP client: ...
            INFO    content_service  Content service shutdown complete
            INFO    content_service  Global content service closed
            INFO    fastmcp_main     Resource cleanup completed successfully

        Zero ERROR records for two stranded resources -- the exact condition
        #100 exists to remove, surviving the fix for it because the test that
        checked the fix never built a real service.
        """
        manager = service_module._content_service_manager
        saved = manager._content_service

        service = ContentService()
        manager._content_service = service

        # Read inside the try, because the ``finally`` below puts ``saved`` back
        # and an assertion after it would be measuring the value the singleton
        # held before this test ran. Mutation-checked: with the read after the
        # restore, replacing ``close_content_service()``'s
        # ``finally: self._content_service = None`` with ``finally: pass`` left
        # this test green.
        cleared: object = "cleanup_resources() did not return"

        # Positions 2 and 3 run the real closers -- only position 1's are
        # patched below -- so state what they find. On the server's path
        # position 1 has already cleared both; here it fails before it can, and
        # the fixture has cleared them instead.
        assert cache_module._cache_manager._cache is None
        assert fetch_module._http_client_manager._http_client is None

        boom = RuntimeError("Event loop is closed")
        try:
            with (
                patch(
                    "finos_mcp.content.service.close_cache",
                    AsyncMock(side_effect=boom),
                ),
                patch(
                    "finos_mcp.content.service.close_http_client",
                    AsyncMock(side_effect=boom),
                ),
                caplog.at_level(logging.DEBUG, logger=SERVICE_LOGGER),
                caplog.at_level(logging.DEBUG, logger=CLEANUP_LOGGER),
            ):
                await cleanup_resources()
            cleared = manager._content_service
        finally:
            manager._content_service = saved

        errors = [
            r
            for r in caplog.records
            if r.levelno >= logging.ERROR and r.name == CLEANUP_LOGGER
        ]
        assert len(errors) == 1, (
            "two resources failed to close, so shutdown must produce an ERROR "
            f"record; got {[(r.levelname, r.name, r.getMessage()) for r in caplog.records]}"
        )
        assert "content service" in errors[0].getMessage(), errors[0].getMessage()

        # The individual failures stay at WARNING and keep naming the resource,
        # which is the only place the specific resource appears at all.
        warnings = [
            r.getMessage()
            for r in caplog.records
            if r.levelno == logging.WARNING and r.name == SERVICE_LOGGER
        ]
        assert warnings == [
            "Error closing cache: Event loop is closed",
            "Error closing HTTP client: Event loop is closed",
        ], f"got {warnings}"

        # Nothing on the failure path may claim a clean close. Each of these
        # three lines did, in this order, directly under the two warnings above.
        messages = [r.getMessage() for r in caplog.records]
        for claim in (
            "Content service shutdown complete",
            "Global content service closed",
            "Resource cleanup completed successfully",
        ):
            assert not any(claim in m for m in messages), (
                f"a shutdown that stranded two resources reported {claim!r}"
            )

        assert cleared is None, (
            f"the reference must be cleared on the failure path too; got {cleared!r}"
        )

    @pytest.mark.asyncio
    async def test_a_failed_close_leaves_the_service_reusable(self) -> None:
        """Both references are dropped whether or not their close succeeded.

        ``_cache`` was never cleared at all and ``_http_client`` was cleared
        after its await, so a raise left it set. A service that survives a failed
        close is still reachable through ``ContentServiceManager``, whose
        reference ``close_content_service()`` clears only in its own
        ``finally``, and it then serves from a client the manager has already
        released, and from a ``TTLCache`` whose
        ``asyncio.Lock`` belongs to a loop that is gone: the first
        ``cache.get()`` from a new loop raises "got Future attached to a
        different loop".
        """
        service = ContentService()

        boom = RuntimeError("Event loop is closed")
        with (
            patch("finos_mcp.content.service.close_cache", AsyncMock(side_effect=boom)),
            patch(
                "finos_mcp.content.service.close_http_client",
                AsyncMock(side_effect=boom),
            ),
            pytest.raises(RuntimeError, match="cache, HTTP client"),
        ):
            await service.close()

    @pytest.mark.asyncio
    async def test_a_failing_cache_close_does_not_strand_the_http_client(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Raising is deferred until every close has been attempted.

        The paired control for the test above: reporting the failure upward is
        only safe if it happens *after* the second close, and raising at the
        first ``except`` would strand the HTTP client on every failing shutdown
        while still producing the ERROR record the test above asserts.
        """
        service = ContentService()

        http_close = AsyncMock()
        with (
            patch(
                "finos_mcp.content.service.close_cache",
                AsyncMock(side_effect=RuntimeError("Event loop is closed")),
            ),
            patch("finos_mcp.content.service.close_http_client", http_close),
            caplog.at_level(logging.DEBUG, logger=SERVICE_LOGGER),
        ):
            with pytest.raises(RuntimeError, match="failed to close: cache"):
                await service.close()

        http_close.assert_awaited_once()
        assert service._http_client is None, (
            "the HTTP client was closed but the service kept its reference"
        )


@pytest.fixture
def _isolate_the_service_singleton():
    """Empty the content-service singleton, and put it back after.

    Only one singleton is named here, and that is the point of #114 rather
    than an oversight in the fixture: after the collapse there is exactly one
    manager holding a ``ContentService``. A fixture that had to reset two
    would be re-stating the defect these tests exist to close.
    """
    manager = service_module._content_service_manager
    saved = manager._content_service
    manager._content_service = None
    try:
        yield
    finally:
        manager._content_service = saved


@pytest.mark.unit
@pytest.mark.usefixtures("_isolate_the_service_singleton")
class TestOneManagerHoldsTheService:
    """#114: two singletons held one service and only one was on shutdown.

    ``AsyncServiceManager`` memoised what ``ContentServiceManager`` already
    held -- the same instance, measured by identity -- so it was a consumer
    caching a manager's object, the shape #124 fixed one layer down inside
    ``ContentService`` itself.

    What that cost is not the stale reference the issue's title describes. It
    is that the two singletons *disagree* after a shutdown, and the second
    shutdown then closes nothing while reporting success::

        shutdown 1 closed:                      [<the service>]
        still serving the same instance:        True
        ContentServiceManager singleton empty:  True
        shutdown 2 closed:                      NOTHING
        ...while the service is still live:     True

    Both tests below drive ``get_service()`` rather than
    ``get_content_service()`` deliberately: the tool bodies call the first, so
    it is the surface a caller actually reaches, and asserting on the second
    would pass against the unfixed code.
    """

    async def test_the_service_shutdown_closed_is_not_handed_out_again(self) -> None:
        """Shutdown closes the service; the next caller must not get that one."""
        first = await facade_module.get_service()
        assert service_module._content_service_manager._content_service is first, (
            "get_service() did not populate the singleton shutdown reaches, so "
            "this test would not exercise the path #114 is about"
        )

        await close_content_service()
        assert service_module._content_service_manager._content_service is None, (
            "shutdown did not clear the singleton; the precondition is not met"
        )

        second = await facade_module.get_service()
        assert second is not first, (
            "get_service() handed back the service shutdown had just closed, so "
            "a second manager is still holding it"
        )

    async def test_a_second_shutdown_closes_what_the_first_one_left(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The strand: two disagreeing singletons make a shutdown a silent no-op.

        The counter wraps the real ``close()`` rather than replacing it, so the
        service is genuinely closed and the second shutdown is measured against
        the same object graph production would have.
        """
        closed: list[int] = []
        real_close = service_module.ContentService.close

        async def counting_close(inner_self: ContentService) -> None:
            closed.append(id(inner_self))
            await real_close(inner_self)

        monkeypatch.setattr(service_module.ContentService, "close", counting_close)

        service = await facade_module.get_service()
        await close_content_service()
        assert closed == [id(service)], (
            f"the first shutdown did not close the service; got {closed}"
        )

        # The server keeps serving between the two shutdowns, which is what an
        # in-process restart does and what makes the second one non-trivial.
        still_serving = await facade_module.get_service()

        closed.clear()
        await close_content_service()
        assert closed == [id(still_serving)], (
            "the second shutdown closed nothing while a live ContentService was "
            "still reachable through get_service(); it reported success having "
            f"stranded it. closed={closed}"
        )
