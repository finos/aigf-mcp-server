"""
Tests for advanced MCP capabilities.
Multi-tenant support, plugin architecture, and extensibility patterns.
"""

from unittest.mock import patch

import pytest

from finos_mcp.internal.advanced_mcp_capabilities import (
    AdvancedMCPServer,
    Plugin,
    PluginManager,
    ResourceIsolation,
    Tenant,
    TenantManager,
)


class TestTenant:
    """Test tenant management functionality."""

    def test_tenant_creation(self):
        """Test creating tenant."""
        tenant = Tenant(
            id="tenant_1", name="Test Tenant", config={"max_resources": 100}
        )
        assert tenant.id == "tenant_1"
        assert tenant.name == "Test Tenant"
        assert tenant.config["max_resources"] == 100
        assert tenant.active is True

    def test_tenant_resource_limits(self):
        """Test tenant resource limit checking."""
        tenant = Tenant(
            id="tenant_1",
            name="Test Tenant",
            config={"max_resources": 5, "max_tools": 3},
        )

        assert tenant.can_add_resource() is True
        tenant.resource_count = 5
        assert tenant.can_add_resource() is False

        assert tenant.can_add_tool() is True
        tenant.tool_count = 3
        assert tenant.can_add_tool() is False

    def test_tenant_deactivation(self):
        """Test tenant deactivation."""
        tenant = Tenant(id="tenant_1", name="Test")
        assert tenant.active is True

        tenant.deactivate()
        assert tenant.active is False


class TestTenantManager:
    """Test tenant management system."""

    def test_manager_creation(self):
        """Test creating tenant manager."""
        manager = TenantManager()
        assert len(manager.tenants) == 0
        assert manager.isolation is not None

    def test_tenant_registration(self):
        """Test tenant registration."""
        manager = TenantManager()

        tenant_config = {"name": "Test Tenant", "config": {"max_resources": 100}}

        tenant_id = manager.register_tenant("tenant_1", tenant_config)
        assert tenant_id == "tenant_1"
        assert "tenant_1" in manager.tenants
        assert manager.tenants["tenant_1"].name == "Test Tenant"

    def test_duplicate_tenant_registration(self):
        """Test duplicate tenant registration."""
        manager = TenantManager()

        tenant_config = {"name": "Test Tenant"}
        manager.register_tenant("tenant_1", tenant_config)

        with pytest.raises(ValueError, match="Tenant tenant_1 already exists"):
            manager.register_tenant("tenant_1", tenant_config)

    @pytest.mark.asyncio
    async def test_tenant_context_switching(self):
        """Test tenant context switching."""
        manager = TenantManager()
        manager.register_tenant("tenant_1", {"name": "Tenant 1"})

        async with manager.tenant_context("tenant_1") as ctx:
            assert ctx.tenant_id == "tenant_1"
            assert ctx.tenant.name == "Tenant 1"

    def test_tenant_resource_isolation(self):
        """Test tenant resource isolation."""
        manager = TenantManager()
        manager.register_tenant("tenant_1", {"name": "Tenant 1"})
        manager.register_tenant("tenant_2", {"name": "Tenant 2"})

        # Add resources to different tenants
        manager.isolation.add_resource(
            "tenant_1", "resource_1", {"data": "tenant1_data"}
        )
        manager.isolation.add_resource(
            "tenant_2", "resource_2", {"data": "tenant2_data"}
        )

        # Check isolation
        tenant1_resources = manager.isolation.get_resources("tenant_1")
        tenant2_resources = manager.isolation.get_resources("tenant_2")

        assert "resource_1" in tenant1_resources
        assert "resource_2" not in tenant1_resources
        assert "resource_2" in tenant2_resources
        assert "resource_1" not in tenant2_resources


class TestPlugin:
    """Test plugin system functionality."""

    def test_plugin_creation(self):
        """Test creating plugin."""
        plugin = Plugin(name="test_plugin", version="1.0.0", description="Test plugin")
        assert plugin.name == "test_plugin"
        assert plugin.version == "1.0.0"
        assert plugin.enabled is True
        assert len(plugin.hooks) == 0

    def test_plugin_hooks(self):
        """Test plugin hook registration."""
        plugin = Plugin(name="test_plugin")

        @plugin.hook("before_request")
        async def handle_before_request(context):
            return {"modified": True}

        assert "before_request" in plugin.hooks
        assert len(plugin.hooks["before_request"]) == 1

    def test_plugin_enable_disable(self):
        """Test plugin enable/disable."""
        plugin = Plugin(name="test_plugin")
        assert plugin.enabled is True

        plugin.disable()
        assert plugin.enabled is False

        plugin.enable()
        assert plugin.enabled is True

    @pytest.mark.asyncio
    async def test_plugin_initialization(self):
        """Test plugin initialization."""
        plugin = Plugin(name="test_plugin")
        init_called = False

        @plugin.hook("initialize")
        async def init_plugin(context):
            nonlocal init_called
            init_called = True
            return {"initialized": True}

        await plugin.initialize({})
        assert init_called is True

    @pytest.mark.asyncio
    async def test_plugin_cleanup(self):
        """Test plugin cleanup."""
        plugin = Plugin(name="test_plugin")
        cleanup_called = False

        @plugin.hook("cleanup")
        async def cleanup_plugin(context):
            nonlocal cleanup_called
            cleanup_called = True

        await plugin.cleanup()
        assert cleanup_called is True


class TestPluginManager:
    """Test plugin management system."""

    def test_manager_creation(self):
        """Test creating plugin manager."""
        manager = PluginManager()
        assert len(manager.plugins) == 0
        assert manager.registry is not None

    def test_plugin_registration(self):
        """Test plugin registration."""
        manager = PluginManager()
        plugin = Plugin(name="test_plugin")

        manager.register_plugin(plugin)
        assert "test_plugin" in manager.plugins
        assert manager.plugins["test_plugin"] == plugin

    def test_duplicate_plugin_registration(self):
        """Test duplicate plugin registration."""
        manager = PluginManager()
        plugin = Plugin(name="test_plugin")

        manager.register_plugin(plugin)

        with pytest.raises(ValueError, match="Plugin test_plugin already registered"):
            manager.register_plugin(plugin)

    @pytest.mark.asyncio
    async def test_plugin_loading(self):
        """Test loading plugin from path."""
        manager = PluginManager()

        # Mock plugin loading
        with patch.object(manager, "_load_plugin_from_path") as mock_load:
            mock_plugin = Plugin(name="loaded_plugin")
            mock_load.return_value = mock_plugin

            result = await manager.load_plugin("path/to/plugin.py")
            assert result == mock_plugin
            assert "loaded_plugin" in manager.plugins

    @pytest.mark.asyncio
    async def test_hook_execution(self):
        """Test executing plugin hooks."""
        manager = PluginManager()

        plugin1 = Plugin(name="plugin1")
        plugin2 = Plugin(name="plugin2")

        results = []

        @plugin1.hook("test_hook")
        async def hook1(context):
            results.append("plugin1")
            return {"from": "plugin1"}

        @plugin2.hook("test_hook")
        async def hook2(context):
            results.append("plugin2")
            return {"from": "plugin2"}

        manager.register_plugin(plugin1)
        manager.register_plugin(plugin2)

        hook_results = await manager.execute_hook("test_hook", {})

        assert len(results) == 2
        assert "plugin1" in results
        assert "plugin2" in results
        assert len(hook_results) == 2

    @pytest.mark.asyncio
    async def test_disabled_plugin_hooks_skipped(self):
        """Test that disabled plugins don't execute hooks."""
        manager = PluginManager()

        plugin = Plugin(name="test_plugin")
        executed = False

        @plugin.hook("test_hook")
        async def hook(context):
            nonlocal executed
            executed = True

        manager.register_plugin(plugin)
        plugin.disable()

        await manager.execute_hook("test_hook", {})
        assert executed is False


class TestResourceIsolation:
    """Test resource isolation functionality."""

    def test_isolation_creation(self):
        """Test creating resource isolation."""
        isolation = ResourceIsolation()
        assert len(isolation.tenant_resources) == 0

    def test_resource_addition(self):
        """Test adding resources to tenant."""
        isolation = ResourceIsolation()

        isolation.add_resource("tenant_1", "resource_1", {"data": "test"})

        resources = isolation.get_resources("tenant_1")
        assert "resource_1" in resources
        assert resources["resource_1"]["data"] == "test"

    def test_resource_removal(self):
        """Test removing resources from tenant."""
        isolation = ResourceIsolation()

        isolation.add_resource("tenant_1", "resource_1", {"data": "test"})
        isolation.remove_resource("tenant_1", "resource_1")

        resources = isolation.get_resources("tenant_1")
        assert "resource_1" not in resources

    def test_tenant_cleanup(self):
        """Test cleaning up all tenant resources."""
        isolation = ResourceIsolation()

        isolation.add_resource("tenant_1", "resource_1", {"data": "test1"})
        isolation.add_resource("tenant_1", "resource_2", {"data": "test2"})

        isolation.cleanup_tenant("tenant_1")

        resources = isolation.get_resources("tenant_1")
        assert len(resources) == 0

    def test_cross_tenant_isolation(self):
        """Test that tenants can't access each other's resources."""
        isolation = ResourceIsolation()

        isolation.add_resource("tenant_1", "resource_1", {"data": "tenant1"})
        isolation.add_resource("tenant_2", "resource_2", {"data": "tenant2"})

        tenant1_resources = isolation.get_resources("tenant_1")
        tenant2_resources = isolation.get_resources("tenant_2")

        assert "resource_1" in tenant1_resources
        assert "resource_2" not in tenant1_resources
        assert "resource_2" in tenant2_resources
        assert "resource_1" not in tenant2_resources


class TestAdvancedMCPServer:
    """Test advanced MCP server functionality."""

    @pytest.mark.asyncio
    async def test_server_creation(self):
        """Test creating advanced MCP server."""
        server = AdvancedMCPServer()
        assert server.tenant_manager is not None
        assert server.plugin_manager is not None

    @pytest.mark.asyncio
    async def test_multi_tenant_request_handling(self):
        """Test handling requests with tenant context."""
        server = AdvancedMCPServer()

        # Register tenant
        server.tenant_manager.register_tenant("tenant_1", {"name": "Test Tenant"})

        # Mock request handler
        handled_requests = []

        async def mock_handler(request, tenant_context=None):
            handled_requests.append(
                {
                    "request": request,
                    "tenant": tenant_context.tenant_id if tenant_context else None,
                }
            )
            return {"result": "success"}

        server._base_handler = mock_handler

        # Handle request with tenant context
        result = await server.handle_request(
            {"method": "test", "params": {}}, tenant_id="tenant_1"
        )

        assert result["result"] == "success"
        assert len(handled_requests) == 1
        assert handled_requests[0]["tenant"] == "tenant_1"

    @pytest.mark.asyncio
    async def test_plugin_integration(self):
        """Test plugin integration with request handling."""
        server = AdvancedMCPServer()

        # Create and register plugin
        plugin = Plugin(name="test_plugin")
        hook_executed = False

        @plugin.hook("before_request")
        async def before_request(context):
            nonlocal hook_executed
            hook_executed = True
            context["request"]["modified"] = True

        server.plugin_manager.register_plugin(plugin)

        # Mock base handler
        async def mock_handler(request, tenant_context=None):
            return {"modified": request.get("modified", False)}

        server._base_handler = mock_handler

        # Handle request
        result = await server.handle_request({"method": "test"})

        assert hook_executed is True
        assert result["modified"] is True

    @pytest.mark.asyncio
    async def test_tenant_resource_limits(self):
        """Test tenant resource limit enforcement."""
        server = AdvancedMCPServer()

        # Register tenant with limits
        server.tenant_manager.register_tenant(
            "tenant_1", {"name": "Limited Tenant", "config": {"max_resources": 1}}
        )

        tenant = server.tenant_manager.tenants["tenant_1"]

        # Add resource within limit
        result1 = await server.add_tenant_resource(
            "tenant_1", "resource_1", {"data": "test"}
        )
        assert result1 is True
        assert tenant.resource_count == 1

        # Try to add resource beyond limit
        result2 = await server.add_tenant_resource(
            "tenant_1", "resource_2", {"data": "test"}
        )
        assert result2 is False
        assert tenant.resource_count == 1

    @pytest.mark.asyncio
    async def test_plugin_error_handling(self):
        """Test plugin error handling."""
        server = AdvancedMCPServer()

        # Create plugin with failing hook
        plugin = Plugin(name="failing_plugin")

        @plugin.hook("before_request")
        async def failing_hook(context):
            raise ValueError("Plugin error")

        server.plugin_manager.register_plugin(plugin)

        # Mock base handler
        async def mock_handler(request, tenant_context=None):
            return {"result": "success"}

        server._base_handler = mock_handler

        # Handle request - should not fail due to plugin error
        result = await server.handle_request({"method": "test"})
        assert result["result"] == "success"


class TestIntegration:
    """Test integration between components."""

    @pytest.mark.asyncio
    async def test_full_multi_tenant_plugin_flow(self):
        """Test complete multi-tenant plugin flow."""
        server = AdvancedMCPServer()

        # Register tenants
        server.tenant_manager.register_tenant(
            "tenant_1", {"name": "Tenant 1", "config": {"max_resources": 10}}
        )
        server.tenant_manager.register_tenant(
            "tenant_2", {"name": "Tenant 2", "config": {"max_resources": 5}}
        )

        # Create tenant-aware plugin
        plugin = Plugin(name="tenant_plugin")
        plugin_logs = []

        @plugin.hook("before_request")
        async def log_tenant_request(context):
            tenant_id = context.get("tenant_id", "unknown")
            plugin_logs.append(f"Request from {tenant_id}")

        server.plugin_manager.register_plugin(plugin)

        # Mock handler
        async def mock_handler(request, tenant_context=None):
            return {
                "tenant": tenant_context.tenant_id if tenant_context else None,
                "method": request["method"],
            }

        server._base_handler = mock_handler

        # Handle requests from different tenants
        result1 = await server.handle_request({"method": "test1"}, tenant_id="tenant_1")
        result2 = await server.handle_request({"method": "test2"}, tenant_id="tenant_2")

        assert result1["tenant"] == "tenant_1"
        assert result1["method"] == "test1"
        assert result2["tenant"] == "tenant_2"
        assert result2["method"] == "test2"

        assert len(plugin_logs) == 2
        assert "Request from tenant_1" in plugin_logs
        assert "Request from tenant_2" in plugin_logs

    @pytest.mark.asyncio
    async def test_plugin_chain_execution(self):
        """Test multiple plugins executing in chain."""
        server = AdvancedMCPServer()

        # Create multiple plugins
        plugin1 = Plugin(name="plugin1")
        plugin2 = Plugin(name="plugin2")

        execution_order = []

        @plugin1.hook("before_request")
        async def plugin1_hook(context):
            execution_order.append("plugin1")
            context["request"]["processed_by"].append("plugin1")

        @plugin2.hook("before_request")
        async def plugin2_hook(context):
            execution_order.append("plugin2")
            context["request"]["processed_by"].append("plugin2")

        server.plugin_manager.register_plugin(plugin1)
        server.plugin_manager.register_plugin(plugin2)

        # Mock handler
        async def mock_handler(request, tenant_context=None):
            return {"processed_by": request.get("processed_by", [])}

        server._base_handler = mock_handler

        # Handle request
        result = await server.handle_request({"method": "test", "processed_by": []})

        assert len(execution_order) == 2
        assert len(result["processed_by"]) == 2
        assert "plugin1" in result["processed_by"]
        assert "plugin2" in result["processed_by"]
