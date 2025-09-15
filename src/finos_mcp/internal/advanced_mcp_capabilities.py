"""
Advanced MCP capabilities for enterprise deployments.
Multi-tenant support, plugin architecture, and extensibility patterns.
"""

import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class Tenant:
    """Multi-tenant support with resource isolation."""

    id: str
    name: str
    config: dict[str, Any] = field(default_factory=dict)
    active: bool = True
    resource_count: int = 0
    tool_count: int = 0
    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())

    def can_add_resource(self) -> bool:
        """Check if tenant can add more resources."""
        max_resources = self.config.get("max_resources", float("inf"))
        return self.resource_count < max_resources

    def can_add_tool(self) -> bool:
        """Check if tenant can add more tools."""
        max_tools = self.config.get("max_tools", float("inf"))
        return self.tool_count < max_tools

    def deactivate(self) -> None:
        """Deactivate tenant."""
        self.active = False

    def activate(self) -> None:
        """Activate tenant."""
        self.active = True


@dataclass
class TenantContext:
    """Context for tenant operations."""

    tenant_id: str
    tenant: Tenant
    request_id: str = field(default_factory=lambda: str(uuid4()))


class ResourceIsolation:
    """Resource isolation for multi-tenant environments."""

    def __init__(self):
        """Initialize resource isolation."""
        self.tenant_resources: dict[str, dict[str, Any]] = {}

    def add_resource(
        self, tenant_id: str, resource_id: str, resource_data: Any
    ) -> None:
        """Add resource to tenant."""
        if tenant_id not in self.tenant_resources:
            self.tenant_resources[tenant_id] = {}
        self.tenant_resources[tenant_id][resource_id] = resource_data

    def remove_resource(self, tenant_id: str, resource_id: str) -> None:
        """Remove resource from tenant."""
        if tenant_id in self.tenant_resources:
            self.tenant_resources[tenant_id].pop(resource_id, None)

    def get_resources(self, tenant_id: str) -> dict[str, Any]:
        """Get all resources for tenant."""
        return self.tenant_resources.get(tenant_id, {})

    def cleanup_tenant(self, tenant_id: str) -> None:
        """Clean up all resources for tenant."""
        self.tenant_resources.pop(tenant_id, None)


class TenantManager:
    """Manage multiple tenants with isolation."""

    def __init__(self):
        """Initialize tenant manager."""
        self.tenants: dict[str, Tenant] = {}
        self.isolation = ResourceIsolation()

    def register_tenant(self, tenant_id: str, tenant_config: dict[str, Any]) -> str:
        """Register new tenant."""
        if tenant_id in self.tenants:
            raise ValueError(f"Tenant {tenant_id} already exists")

        tenant = Tenant(
            id=tenant_id,
            name=tenant_config.get("name", tenant_id),
            config=tenant_config.get("config", {}),
        )

        self.tenants[tenant_id] = tenant
        logger.info(f"Registered tenant: {tenant_id}")
        return tenant_id

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        """Get tenant by ID."""
        return self.tenants.get(tenant_id)

    def deactivate_tenant(self, tenant_id: str) -> None:
        """Deactivate tenant."""
        if tenant_id in self.tenants:
            self.tenants[tenant_id].deactivate()
            self.isolation.cleanup_tenant(tenant_id)

    @asynccontextmanager
    async def tenant_context(self, tenant_id: str):
        """Create tenant context for operations."""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        if not tenant.active:
            raise ValueError(f"Tenant {tenant_id} is not active")

        context = TenantContext(tenant_id=tenant_id, tenant=tenant)
        try:
            yield context
        finally:
            # Cleanup context if needed
            pass


class PluginHook:
    """Plugin hook definition."""

    def __init__(self, name: str, handler: Callable):
        """Initialize plugin hook."""
        self.name = name
        self.handler = handler


class Plugin:
    """Plugin for extending MCP server functionality."""

    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        description: str = "",
        dependencies: list[str] | None = None,
    ):
        """Initialize plugin."""
        self.name = name
        self.version = version
        self.description = description
        self.dependencies = dependencies or []
        self.enabled = True
        self.hooks: dict[str, list[Callable]] = {}
        self.config: dict[str, Any] = {}

    def hook(self, hook_name: str):
        """Decorator for registering plugin hooks."""

        def decorator(handler):
            if hook_name not in self.hooks:
                self.hooks[hook_name] = []
            self.hooks[hook_name].append(handler)
            return handler

        return decorator

    def enable(self) -> None:
        """Enable plugin."""
        self.enabled = True

    def disable(self) -> None:
        """Disable plugin."""
        self.enabled = False

    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize plugin with config."""
        self.config = config
        if "initialize" in self.hooks:
            for handler in self.hooks["initialize"]:
                await handler(config)

    async def cleanup(self) -> None:
        """Cleanup plugin resources."""
        if "cleanup" in self.hooks:
            for handler in self.hooks["cleanup"]:
                await handler({})


class PluginRegistry:
    """Registry for plugin discovery and management."""

    def __init__(self):
        """Initialize plugin registry."""
        self.available_plugins: dict[str, dict[str, Any]] = {}

    def register_plugin_info(self, plugin_info: dict[str, Any]) -> None:
        """Register plugin information."""
        name = plugin_info["name"]
        self.available_plugins[name] = plugin_info

    def list_available_plugins(self) -> list[dict[str, Any]]:
        """List all available plugins."""
        return list(self.available_plugins.values())

    def get_plugin_info(self, name: str) -> dict[str, Any] | None:
        """Get plugin information."""
        return self.available_plugins.get(name)


class PluginManager:
    """Manage plugins and hook execution."""

    def __init__(self):
        """Initialize plugin manager."""
        self.plugins: dict[str, Plugin] = {}
        self.registry = PluginRegistry()

    def register_plugin(self, plugin: Plugin) -> None:
        """Register plugin."""
        if plugin.name in self.plugins:
            raise ValueError(f"Plugin {plugin.name} already registered")

        self.plugins[plugin.name] = plugin
        logger.info(f"Registered plugin: {plugin.name} v{plugin.version}")

    def unregister_plugin(self, plugin_name: str) -> None:
        """Unregister plugin."""
        if plugin_name in self.plugins:
            del self.plugins[plugin_name]
            logger.info(f"Unregistered plugin: {plugin_name}")

    def get_plugin(self, name: str) -> Plugin | None:
        """Get plugin by name."""
        return self.plugins.get(name)

    async def load_plugin(self, plugin_path: str) -> Plugin:
        """Load plugin from file."""
        plugin = await self._load_plugin_from_path(plugin_path)
        self.register_plugin(plugin)
        return plugin

    async def _load_plugin_from_path(self, plugin_path: str) -> Plugin:
        """Load plugin from path."""
        # Mock implementation for testing
        # In real implementation, would dynamically load Python module
        path = Path(plugin_path)
        plugin_name = path.stem
        return Plugin(name=plugin_name, description=f"Loaded from {plugin_path}")

    async def execute_hook(self, hook_name: str, context: dict[str, Any]) -> list[Any]:
        """Execute all hooks for given name."""
        results = []

        for plugin in self.plugins.values():
            if not plugin.enabled:
                continue

            if hook_name in plugin.hooks:
                for handler in plugin.hooks[hook_name]:
                    try:
                        result = await handler(context)
                        if result is not None:
                            results.append(result)
                    except Exception as e:
                        logger.error(
                            f"Error in plugin {plugin.name} hook {hook_name}: {e}"
                        )
                        continue

        return results

    async def initialize_plugins(self) -> None:
        """Initialize all plugins."""
        for plugin in self.plugins.values():
            if plugin.enabled:
                try:
                    await plugin.initialize({})
                except Exception as e:
                    logger.error(f"Error initializing plugin {plugin.name}: {e}")

    async def cleanup_plugins(self) -> None:
        """Cleanup all plugins."""
        for plugin in self.plugins.values():
            try:
                await plugin.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up plugin {plugin.name}: {e}")


class AdvancedMCPServer:
    """Advanced MCP server with multi-tenant and plugin support."""

    def __init__(self):
        """Initialize advanced MCP server."""
        self.tenant_manager = TenantManager()
        self.plugin_manager = PluginManager()
        self._base_handler: Callable | None = None

    async def handle_request(
        self, request: dict[str, Any], tenant_id: str | None = None
    ) -> dict[str, Any]:
        """Handle request with tenant and plugin support."""
        # Create context for plugins
        context = {"request": request, "tenant_id": tenant_id, "server": self}

        # Execute before_request hooks
        await self.plugin_manager.execute_hook("before_request", context)

        # Handle request with tenant context
        result = None
        if tenant_id:
            async with self.tenant_manager.tenant_context(tenant_id) as tenant_context:
                result = await self._handle_with_context(
                    context["request"], tenant_context
                )
        else:
            result = await self._handle_with_context(context["request"], None)

        # Execute after_request hooks
        context["result"] = result
        await self.plugin_manager.execute_hook("after_request", context)

        return result

    async def _handle_with_context(
        self, request: dict[str, Any], tenant_context: TenantContext | None
    ) -> dict[str, Any]:
        """Handle request with tenant context."""
        if self._base_handler:
            return await self._base_handler(request, tenant_context)

        # Default handler
        return {"result": "success", "method": request.get("method")}

    async def add_tenant_resource(
        self, tenant_id: str, resource_id: str, resource_data: Any
    ) -> bool:
        """Add resource to tenant with limit checking."""
        tenant = self.tenant_manager.get_tenant(tenant_id)
        if not tenant:
            return False

        if not tenant.can_add_resource():
            return False

        self.tenant_manager.isolation.add_resource(
            tenant_id, resource_id, resource_data
        )
        tenant.resource_count += 1
        return True

    async def remove_tenant_resource(self, tenant_id: str, resource_id: str) -> bool:
        """Remove resource from tenant."""
        tenant = self.tenant_manager.get_tenant(tenant_id)
        if not tenant:
            return False

        self.tenant_manager.isolation.remove_resource(tenant_id, resource_id)
        if tenant.resource_count > 0:
            tenant.resource_count -= 1
        return True

    async def start(self) -> None:
        """Start the advanced MCP server."""
        await self.plugin_manager.initialize_plugins()
        logger.info("Advanced MCP server started")

    async def stop(self) -> None:
        """Stop the advanced MCP server."""
        await self.plugin_manager.cleanup_plugins()
        logger.info("Advanced MCP server stopped")
