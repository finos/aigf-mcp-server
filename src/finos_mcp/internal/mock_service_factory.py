"""
Mock service factory with scenario-based testing.
Provides comprehensive mock service creation with predefined scenarios.
"""

import asyncio
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, Mock


@dataclass
class MockServiceScenario:
    """Configuration for a mock service testing scenario."""

    name: str
    description: str = ""
    responses: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self):
        """Validate scenario configuration."""
        if not self.name:
            raise ValueError("Scenario name is required")


class ScenarioBuilder:
    """Fluent API builder for creating mock service scenarios."""

    def __init__(self, name: str):
        """Initialize scenario builder with name."""
        self.name = name
        self._description = ""
        self._current_service = None
        self._responses = {}

    def description(self, desc: str) -> 'ScenarioBuilder':
        """Set scenario description."""
        self._description = desc
        return self

    def mock_service(self, service_name: str) -> 'ScenarioBuilder':
        """Set current service for method configuration."""
        self._current_service = service_name
        return self

    def method(self, method_name: str) -> 'ScenarioBuilder':
        """Configure method for current service."""
        if not self._current_service:
            raise ValueError("Must call mock_service() before method()")

        self._current_method = method_name
        key = (self._current_service, method_name)
        if key not in self._responses:
            self._responses[key] = {}

        return self

    def returns(self, value: Any) -> 'ScenarioBuilder':
        """Set return value for current method."""
        if not hasattr(self, '_current_method'):
            raise ValueError("Must call method() before returns()")

        key = (self._current_service, self._current_method)
        self._responses[key]["return_value"] = value
        return self

    def side_effect(self, effect: Callable | Exception) -> 'ScenarioBuilder':
        """Set side effect for current method."""
        if not hasattr(self, '_current_method'):
            raise ValueError("Must call method() before side_effect()")

        key = (self._current_service, self._current_method)
        self._responses[key]["side_effect"] = effect
        return self

    def delay(self, seconds: float) -> 'ScenarioBuilder':
        """Set response delay for current method."""
        if not hasattr(self, '_current_method'):
            raise ValueError("Must call method() before delay()")

        key = (self._current_service, self._current_method)
        self._responses[key]["delay"] = seconds
        return self

    def build(self) -> MockServiceScenario:
        """Build the scenario from current configuration."""
        return MockServiceScenario(
            name=self.name,
            description=self._description,
            responses=self._responses.copy()
        )


class MockServiceRegistry:
    """Registry for managing mock service instances."""

    def __init__(self):
        """Initialize empty registry."""
        self._services = {}
        self._types = {}

    def register(self, name: str, service: Any, service_type: type | None = None) -> None:
        """Register a service with optional type checking."""
        if service_type and not isinstance(service, service_type):
            raise TypeError(f"Service {name} must be instance of {service_type}")

        self._services[name] = service
        if service_type:
            self._types[name] = service_type

    def unregister(self, name: str) -> None:
        """Unregister a service."""
        self._services.pop(name, None)
        self._types.pop(name, None)

    def get_service(self, name: str) -> Any:
        """Get registered service by name."""
        return self._services.get(name)

    def list_services(self) -> list[str]:
        """List all registered service names."""
        return list(self._services.keys())

    def clear(self) -> None:
        """Clear all registered services."""
        self._services.clear()
        self._types.clear()


class MockServiceFactory:
    """Factory for creating mock services based on scenarios."""

    def __init__(self):
        """Initialize factory with registry."""
        self.registry = MockServiceRegistry()

    def create_mocks(self, scenario: MockServiceScenario) -> dict[str, Any]:
        """Create mock services from scenario configuration."""
        mocks = {}

        # Group responses by service
        services = {}
        for (service_name, method_name), config in scenario.responses.items():
            if service_name not in services:
                services[service_name] = {}
            services[service_name][method_name] = config

        # Create mocks for each service
        for service_name, methods in services.items():
            mock_service = Mock()

            for method_name, config in methods.items():
                # Create method mock
                method_mock = self._create_method_mock(config)
                setattr(mock_service, method_name, method_mock)

            mocks[service_name] = mock_service

        return mocks

    def _create_method_mock(self, config: dict[str, Any]) -> Mock | AsyncMock:
        """Create a method mock based on configuration."""
        # Always use AsyncMock for consistency in testing environment
        # This allows tests to use await uniformly
        mock = AsyncMock()

        # Configure async mock
        if "return_value" in config:
            if "delay" in config:
                async def delayed_return(*args, **kwargs):
                    await asyncio.sleep(config["delay"])
                    return config["return_value"]
                mock.side_effect = delayed_return
            else:
                mock.return_value = config["return_value"]
        elif "side_effect" in config:
            if "delay" in config and not asyncio.iscoroutinefunction(config["side_effect"]):
                original_side_effect = config["side_effect"]
                async def delayed_side_effect(*args, **kwargs):
                    await asyncio.sleep(config["delay"])
                    if isinstance(original_side_effect, Exception):
                        raise original_side_effect
                    elif callable(original_side_effect):
                        return original_side_effect(*args, **kwargs)
                    else:
                        return original_side_effect
                mock.side_effect = delayed_side_effect
            else:
                mock.side_effect = config["side_effect"]

        return mock

    @contextmanager
    def scenario_context(self, scenario: MockServiceScenario):
        """Context manager for using scenario mocks."""
        mocks = self.create_mocks(scenario)

        # Register mocks in registry
        for name, mock in mocks.items():
            self.registry.register(name, mock)

        try:
            yield mocks
        finally:
            # Clean up registered mocks
            for name in mocks.keys():
                self.registry.unregister(name)
