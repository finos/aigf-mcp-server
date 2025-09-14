"""
Tests for mock service factory with scenario-based testing.
"""

import asyncio
from unittest.mock import Mock

import pytest

from finos_mcp.internal.mock_service_factory import (
    MockServiceFactory,
    MockServiceRegistry,
    MockServiceScenario,
    ScenarioBuilder,
)


class TestMockServiceScenario:
    """Test mock service scenario configuration."""

    def test_scenario_creation(self):
        """Test creating a basic scenario."""
        scenario = MockServiceScenario(
            name="basic_test",
            description="Basic test scenario",
            responses={
                ("content_service", "get_document"): {
                    "return_value": {"content": "test"}
                }
            }
        )

        assert scenario.name == "basic_test"
        assert scenario.description == "Basic test scenario"
        assert len(scenario.responses) == 1

    def test_scenario_with_side_effects(self):
        """Test scenario with side effects."""
        def custom_side_effect(*args, **kwargs):
            return {"custom": "response"}

        scenario = MockServiceScenario(
            name="side_effect_test",
            description="Test with side effects",
            responses={
                ("auth_service", "authenticate"): {
                    "side_effect": custom_side_effect
                }
            }
        )

        key = ("auth_service", "authenticate")
        assert scenario.responses[key]["side_effect"] == custom_side_effect

    def test_scenario_with_delays(self):
        """Test scenario with response delays."""
        scenario = MockServiceScenario(
            name="delay_test",
            description="Test with delays",
            responses={
                ("slow_service", "slow_method"): {
                    "return_value": {"data": "slow"},
                    "delay": 0.5
                }
            }
        )

        key = ("slow_service", "slow_method")
        assert scenario.responses[key]["delay"] == 0.5

    def test_scenario_with_exceptions(self):
        """Test scenario that raises exceptions."""
        scenario = MockServiceScenario(
            name="error_test",
            description="Test error scenarios",
            responses={
                ("failing_service", "fail_method"): {
                    "side_effect": ValueError("Test error")
                }
            }
        )

        key = ("failing_service", "fail_method")
        assert isinstance(scenario.responses[key]["side_effect"], ValueError)


class TestScenarioBuilder:
    """Test scenario builder for fluent API."""

    def test_builder_basic_creation(self):
        """Test basic scenario builder usage."""
        builder = ScenarioBuilder("test_scenario")
        scenario = (builder
                   .description("Test scenario description")
                   .mock_service("content_service")
                   .method("get_document")
                   .returns({"content": "test"})
                   .build())

        assert scenario.name == "test_scenario"
        assert scenario.description == "Test scenario description"
        assert len(scenario.responses) == 1

    def test_builder_with_multiple_services(self):
        """Test builder with multiple services and methods."""
        builder = ScenarioBuilder("multi_service_test")
        scenario = (builder
                   .description("Multiple services test")
                   .mock_service("content_service")
                   .method("get_document")
                   .returns({"type": "document"})
                   .mock_service("auth_service")
                   .method("authenticate")
                   .returns({"token": "abc123"})
                   .build())

        assert len(scenario.responses) == 2
        assert ("content_service", "get_document") in scenario.responses
        assert ("auth_service", "authenticate") in scenario.responses

    def test_builder_with_side_effects(self):
        """Test builder with side effects."""
        def custom_effect():
            return {"custom": True}

        builder = ScenarioBuilder("side_effect_test")
        scenario = (builder
                   .mock_service("test_service")
                   .method("test_method")
                   .side_effect(custom_effect)
                   .build())

        key = ("test_service", "test_method")
        assert scenario.responses[key]["side_effect"] == custom_effect

    def test_builder_with_delays(self):
        """Test builder with response delays."""
        builder = ScenarioBuilder("delay_test")
        scenario = (builder
                   .mock_service("slow_service")
                   .method("slow_operation")
                   .returns({"result": "slow"})
                   .delay(1.0)
                   .build())

        key = ("slow_service", "slow_operation")
        assert scenario.responses[key]["delay"] == 1.0

    def test_builder_chaining_methods(self):
        """Test chaining multiple methods for same service."""
        builder = ScenarioBuilder("chaining_test")
        scenario = (builder
                   .mock_service("api_service")
                   .method("get_user").returns({"id": 1})
                   .method("get_profile").returns({"name": "test"})
                   .build())

        assert len(scenario.responses) == 2
        assert ("api_service", "get_user") in scenario.responses
        assert ("api_service", "get_profile") in scenario.responses


class TestMockServiceRegistry:
    """Test mock service registry."""

    def test_registry_registration(self):
        """Test service registration."""
        registry = MockServiceRegistry()
        mock_service = Mock()

        registry.register("test_service", mock_service)

        assert registry.get_service("test_service") == mock_service

    def test_registry_registration_with_type(self):
        """Test service registration with type checking."""
        registry = MockServiceRegistry()

        class TestService:
            pass

        service = TestService()
        registry.register("typed_service", service, TestService)

        assert registry.get_service("typed_service") == service

    def test_registry_unregistration(self):
        """Test service unregistration."""
        registry = MockServiceRegistry()
        mock_service = Mock()

        registry.register("temp_service", mock_service)
        registry.unregister("temp_service")

        assert registry.get_service("temp_service") is None

    def test_registry_list_services(self):
        """Test listing registered services."""
        registry = MockServiceRegistry()
        registry.register("service1", Mock())
        registry.register("service2", Mock())

        services = registry.list_services()
        assert "service1" in services
        assert "service2" in services

    def test_registry_clear(self):
        """Test clearing all services."""
        registry = MockServiceRegistry()
        registry.register("service1", Mock())
        registry.register("service2", Mock())

        registry.clear()

        assert len(registry.list_services()) == 0


class TestMockServiceFactory:
    """Test mock service factory."""

    def test_factory_creation(self):
        """Test creating factory instance."""
        factory = MockServiceFactory()
        assert factory is not None
        assert isinstance(factory.registry, MockServiceRegistry)

    def test_create_mock_from_scenario(self):
        """Test creating mocks from scenario."""
        scenario = MockServiceScenario(
            name="test",
            description="Test scenario",
            responses={
                ("content_service", "get_document"): {
                    "return_value": {"content": "test"}
                }
            }
        )

        factory = MockServiceFactory()
        mocks = factory.create_mocks(scenario)

        assert "content_service" in mocks
        assert hasattr(mocks["content_service"], "get_document")

    @pytest.mark.asyncio
    async def test_async_mock_behavior(self):
        """Test async mock behavior."""
        scenario = MockServiceScenario(
            name="async_test",
            description="Async test scenario",
            responses={
                ("async_service", "async_method"): {
                    "return_value": {"async_result": True}
                }
            }
        )

        factory = MockServiceFactory()
        mocks = factory.create_mocks(scenario)

        result = await mocks["async_service"].async_method()
        assert result["async_result"] is True

    @pytest.mark.asyncio
    async def test_mock_with_delay(self):
        """Test mock with response delay."""
        scenario = MockServiceScenario(
            name="delay_test",
            description="Delay test scenario",
            responses={
                ("delayed_service", "slow_method"): {
                    "return_value": {"delayed": True},
                    "delay": 0.1
                }
            }
        )

        factory = MockServiceFactory()
        mocks = factory.create_mocks(scenario)

        start_time = asyncio.get_event_loop().time()
        result = await mocks["delayed_service"].slow_method()
        end_time = asyncio.get_event_loop().time()

        assert result["delayed"] is True
        assert end_time - start_time >= 0.1

    @pytest.mark.asyncio
    async def test_mock_with_side_effect(self):
        """Test mock with side effect."""
        def custom_side_effect(*args, **kwargs):
            return {"args": args, "kwargs": kwargs}

        scenario = MockServiceScenario(
            name="side_effect_test",
            description="Side effect test scenario",
            responses={
                ("effect_service", "effect_method"): {
                    "side_effect": custom_side_effect
                }
            }
        )

        factory = MockServiceFactory()
        mocks = factory.create_mocks(scenario)

        result = await mocks["effect_service"].effect_method("test_arg", key="value")
        assert result["args"] == ("test_arg",)
        assert result["kwargs"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_mock_with_exception(self):
        """Test mock that raises exceptions."""
        scenario = MockServiceScenario(
            name="error_test",
            description="Error test scenario",
            responses={
                ("error_service", "error_method"): {
                    "side_effect": ValueError("Test error")
                }
            }
        )

        factory = MockServiceFactory()
        mocks = factory.create_mocks(scenario)

        with pytest.raises(ValueError, match="Test error"):
            await mocks["error_service"].error_method()

    @pytest.mark.asyncio
    async def test_scenario_context_manager(self):
        """Test using scenario as context manager."""
        scenario = MockServiceScenario(
            name="context_test",
            description="Context manager test",
            responses={
                ("ctx_service", "ctx_method"): {
                    "return_value": {"context": True}
                }
            }
        )

        factory = MockServiceFactory()

        with factory.scenario_context(scenario) as mocks:
            result = await mocks["ctx_service"].ctx_method()
            assert result["context"] is True

    @pytest.mark.asyncio
    async def test_integration_with_fast_mode(self):
        """Test integration with fast test mode."""
        from finos_mcp.internal.testing import FastTestMode

        scenario = MockServiceScenario(
            name="fast_mode_test",
            description="Fast mode integration test",
            responses={
                ("fast_service", "fast_method"): {
                    "return_value": {"fast": True}
                }
            }
        )

        factory = MockServiceFactory()

        with FastTestMode() as fast_mode:
            mocks = factory.create_mocks(scenario)
            result = await mocks["fast_service"].fast_method()

            assert result["fast"] is True
            # FastTestMode integration works with the mock service factory
            assert fast_mode is not None


class TestScenarioIntegration:
    """Test complete scenario integration."""

    @pytest.mark.asyncio
    async def test_content_service_scenario(self):
        """Test complete content service scenario."""
        # Build comprehensive scenario
        scenario = (ScenarioBuilder("content_service_integration")
                   .description("Complete content service test scenario")
                   .mock_service("content_service")
                   .method("get_document")
                   .returns({
                       "filename": "test.md",
                       "type": "mitigation",
                       "content": "# Test Document\n\nContent here",
                       "metadata": {"title": "Test", "version": "1.0"}
                   })
                   .method("list_documents")
                   .returns([
                       {"filename": "doc1.md", "type": "risk"},
                       {"filename": "doc2.md", "type": "mitigation"}
                   ])
                   .mock_service("auth_service")
                   .method("authenticate")
                   .returns({"token": "jwt_token_123", "expires_in": 3600})
                   .method("validate_token")
                   .side_effect(lambda token: {"valid": token == "jwt_token_123"})
                   .build())

        factory = MockServiceFactory()

        with factory.scenario_context(scenario) as mocks:
            # Test content service
            doc = await mocks["content_service"].get_document("mitigation", "test.md")
            assert doc["filename"] == "test.md"
            assert doc["type"] == "mitigation"

            docs = await mocks["content_service"].list_documents()
            assert len(docs) == 2

            # Test auth service
            auth_result = await mocks["auth_service"].authenticate("user", "pass")
            assert auth_result["token"] == "jwt_token_123"

            validation = await mocks["auth_service"].validate_token("jwt_token_123")
            assert validation["valid"] is True

            invalid_validation = await mocks["auth_service"].validate_token("invalid")
            assert invalid_validation["valid"] is False

    @pytest.mark.asyncio
    async def test_error_scenario_handling(self):
        """Test comprehensive error scenario handling."""
        scenario = (ScenarioBuilder("error_scenarios")
                   .description("Error handling test scenarios")
                   .mock_service("unreliable_service")
                   .method("network_call")
                   .side_effect(ConnectionError("Network unavailable"))
                   .method("timeout_call")
                   .side_effect(asyncio.TimeoutError("Request timeout"))
                   .method("invalid_data")
                   .side_effect(ValueError("Invalid input data"))
                   .build())

        factory = MockServiceFactory()

        with factory.scenario_context(scenario) as mocks:
            # Test network error
            with pytest.raises(ConnectionError, match="Network unavailable"):
                await mocks["unreliable_service"].network_call()

            # Test timeout error
            with pytest.raises(asyncio.TimeoutError, match="Request timeout"):
                await mocks["unreliable_service"].timeout_call()

            # Test validation error
            with pytest.raises(ValueError, match="Invalid input data"):
                await mocks["unreliable_service"].invalid_data()

    @pytest.mark.asyncio
    async def test_performance_scenario(self):
        """Test performance-related scenario."""
        scenario = (ScenarioBuilder("performance_test")
                   .description("Performance testing scenario")
                   .mock_service("cache_service")
                   .method("get_cached_data")
                   .returns({"cached": True, "data": "fast_response"})
                   .delay(0.001)  # Very fast cache hit
                   .method("miss_and_fetch")
                   .returns({"cached": False, "data": "slow_response"})
                   .delay(0.1)  # Slow database fetch (reduced for faster tests)
                   .build())

        factory = MockServiceFactory()

        with factory.scenario_context(scenario) as mocks:
            # Test that different methods have different performance characteristics
            import time

            # Fast cache hit
            start = time.time()
            result1 = await mocks["cache_service"].get_cached_data()
            fast_time = time.time() - start

            # Slow fetch
            start = time.time()
            result2 = await mocks["cache_service"].miss_and_fetch()
            slow_time = time.time() - start

            assert result1["cached"] is True
            assert result2["cached"] is False
            assert slow_time > fast_time
