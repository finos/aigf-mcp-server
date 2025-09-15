"""
Tests for enterprise Python patterns implementation.
Domain Events, CQRS, and Message Bus for MCP server.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from finos_mcp.internal.enterprise_patterns import (
    CQRS,
    Command,
    CommandHandler,
    DocumentRetrievedEvent,
    DomainEvent,
    EventBus,
    GetDocumentDetailsQuery,
    LogSearchCommand,
    MessageBus,
    Query,
    QueryHandler,
    SearchCompletedEvent,
    SearchMitigationsQuery,
    UpdateSearchCacheCommand,
)


class TestDomainEvent:
    """Test domain event system."""

    def test_event_creation(self):
        """Test creating domain events."""
        event = DomainEvent(
            event_type="test_event", data={"key": "value"}, timestamp=datetime.now()
        )

        assert event.event_type == "test_event"
        assert event.data["key"] == "value"
        assert isinstance(event.timestamp, datetime)

    def test_search_completed_event(self):
        """Test search completed event."""
        event = SearchCompletedEvent(
            query="data leakage",
            results=[{"title": "mi-1"}, {"title": "mi-2"}],
            user_id="test_user",
        )

        assert event.event_type == "search_completed"
        assert event.query == "data leakage"
        assert len(event.results) == 2
        assert event.user_id == "test_user"

    def test_document_retrieved_event(self):
        """Test document retrieved event."""
        event = DocumentRetrievedEvent(
            document_id="mi-1", document_type="mitigation", user_id="test_user"
        )

        assert event.event_type == "document_retrieved"
        assert event.document_id == "mi-1"
        assert event.document_type == "mitigation"


class TestEventBus:
    """Test event bus implementation."""

    def test_event_bus_creation(self):
        """Test creating event bus."""
        bus = EventBus()
        assert bus is not None
        assert len(bus._handlers) == 0

    def test_register_handler(self):
        """Test registering event handlers."""
        bus = EventBus()
        handler = Mock()

        bus.register("test_event", handler)

        assert "test_event" in bus._handlers
        assert handler in bus._handlers["test_event"]

    def test_publish_event(self):
        """Test publishing events."""
        bus = EventBus()
        handler = Mock()
        bus.register("test_event", handler)

        event = DomainEvent(
            event_type="test_event", data={"test": True}, timestamp=datetime.now()
        )

        bus.publish(event)

        handler.assert_called_once_with(event)

    def test_multiple_handlers(self):
        """Test multiple handlers for same event."""
        bus = EventBus()
        handler1 = Mock()
        handler2 = Mock()

        bus.register("test_event", handler1)
        bus.register("test_event", handler2)

        event = DomainEvent("test_event", {}, datetime.now())
        bus.publish(event)

        handler1.assert_called_once_with(event)
        handler2.assert_called_once_with(event)

    def test_no_handlers_for_event(self):
        """Test publishing event with no handlers."""
        bus = EventBus()
        event = DomainEvent("unknown_event", {}, datetime.now())

        # Should not raise exception
        bus.publish(event)

    def test_decorator_handler_registration(self):
        """Test decorator-based handler registration."""
        bus = EventBus()

        @bus.handler("decorated_event")
        def handle_decorated(event):
            event.data["handled"] = True

        event = DomainEvent("decorated_event", {}, datetime.now())
        bus.publish(event)

        assert event.data["handled"] is True


class TestCQRS:
    """Test CQRS (Command Query Responsibility Separation)."""

    def test_command_creation(self):
        """Test creating commands."""
        command = UpdateSearchCacheCommand(
            query="test query", results=[{"title": "result1"}]
        )

        assert isinstance(command, Command)
        assert command.query == "test query"
        assert len(command.results) == 1

    def test_query_creation(self):
        """Test creating queries."""
        query = SearchMitigationsQuery(query="data leakage", exact_match=False)

        assert isinstance(query, Query)
        assert query.query == "data leakage"
        assert query.exact_match is False

    def test_command_handler(self):
        """Test command handler."""
        handler = CommandHandler()
        command = LogSearchCommand(query="test", results_count=5, user_id="user1")

        # Should be able to handle command
        assert hasattr(handler, "handle")

    def test_query_handler(self):
        """Test query handler."""
        handler = QueryHandler()
        query = GetDocumentDetailsQuery(document_id="mi-1")

        # Should be able to handle query
        assert hasattr(handler, "handle")

    @pytest.mark.asyncio
    async def test_cqrs_integration(self):
        """Test CQRS integration with event bus."""
        event_bus = EventBus()
        cqrs = CQRS(event_bus)

        # Mock handlers
        command_handler = AsyncMock()
        query_handler = AsyncMock(return_value={"result": "test"})

        cqrs.register_command_handler(UpdateSearchCacheCommand, command_handler)
        cqrs.register_query_handler(SearchMitigationsQuery, query_handler)

        # Test command execution
        command = UpdateSearchCacheCommand("test", [])
        await cqrs.execute_command(command)
        command_handler.assert_called_once_with(command)

        # Test query execution
        query = SearchMitigationsQuery("test", False)
        result = await cqrs.execute_query(query)
        query_handler.assert_called_once_with(query)
        assert result["result"] == "test"


class TestMessageBus:
    """Test message bus implementation."""

    def test_message_bus_creation(self):
        """Test creating message bus."""
        bus = MessageBus()
        assert bus is not None
        assert len(bus._queues) == 0

    @pytest.mark.asyncio
    async def test_send_message(self):
        """Test sending messages."""
        bus = MessageBus()
        message = {"type": "test", "data": "hello"}

        await bus.send(message, "test_topic")

        # Message should be in queue
        assert "test_topic" in bus._queues
        queue = bus._queues["test_topic"]
        assert queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_receive_message(self):
        """Test receiving messages."""
        bus = MessageBus()
        message = {"type": "test", "data": "hello"}

        await bus.send(message, "test_topic")
        received = await bus.receive("test_topic")

        assert received == message

    @pytest.mark.asyncio
    async def test_subscribe_to_topic(self):
        """Test subscribing to topics."""
        bus = MessageBus()
        messages = []

        # Subscribe with handler
        async def handler(msg):
            messages.append(msg)

        bus.subscribe("test_topic", handler)

        # Send message
        test_message = {"data": "test"}
        await bus.send(test_message, "test_topic")

        # Wait for handler to process
        await asyncio.sleep(0.01)

        assert len(messages) == 1
        assert messages[0] == test_message

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        """Test multiple subscribers to same topic."""
        bus = MessageBus()
        messages1 = []
        messages2 = []

        async def handler1(msg):
            messages1.append(msg)

        async def handler2(msg):
            messages2.append(msg)

        bus.subscribe("shared_topic", handler1)
        bus.subscribe("shared_topic", handler2)

        message = {"data": "broadcast"}
        await bus.send(message, "shared_topic")
        await asyncio.sleep(0.01)

        assert len(messages1) == 1
        assert len(messages2) == 1
        assert messages1[0] == messages2[0] == message


class TestMCPIntegration:
    """Test integration with MCP server patterns."""

    @pytest.mark.asyncio
    async def test_search_with_events(self):
        """Test search operation with domain events."""
        event_bus = EventBus()
        events_received = []

        @event_bus.handler("search_completed")
        def log_search(event):
            events_received.append(event)

        # Simulate search operation
        query = "data leakage"
        results = [{"title": "mi-1"}, {"title": "mi-2"}]

        # Publish search completed event
        event = SearchCompletedEvent(query, results, "user1")
        event_bus.publish(event)

        assert len(events_received) == 1
        assert events_received[0].query == query
        assert len(events_received[0].results) == 2

    @pytest.mark.asyncio
    async def test_cqrs_with_mcp_operations(self):
        """Test CQRS with MCP operations."""
        event_bus = EventBus()
        cqrs = CQRS(event_bus)

        # Mock MCP operation handlers
        search_handler = AsyncMock(return_value=[{"title": "mi-1"}])
        cache_handler = AsyncMock()

        cqrs.register_query_handler(SearchMitigationsQuery, search_handler)
        cqrs.register_command_handler(UpdateSearchCacheCommand, cache_handler)

        # Execute query (read operation)
        query = SearchMitigationsQuery("data leakage", False)
        results = await cqrs.execute_query(query)

        # Execute command (write operation)
        command = UpdateSearchCacheCommand("data leakage", results)
        await cqrs.execute_command(command)

        search_handler.assert_called_once_with(query)
        cache_handler.assert_called_once_with(command)

    @pytest.mark.asyncio
    async def test_message_bus_mcp_integration(self):
        """Test message bus integration with MCP services."""
        bus = MessageBus()
        processed_messages = []

        # Simulate MCP service handler
        async def content_service_handler(message):
            if message["type"] == "search_request":
                # Simulate search processing
                processed_messages.append(
                    {
                        "type": "search_response",
                        "query": message["query"],
                        "results": ["mi-1", "mi-2"],
                    }
                )

        bus.subscribe("content_service", content_service_handler)

        # Send search request
        await bus.send(
            {"type": "search_request", "query": "AI governance"}, "content_service"
        )

        await asyncio.sleep(0.01)

        assert len(processed_messages) == 1
        assert processed_messages[0]["type"] == "search_response"
        assert "mi-1" in processed_messages[0]["results"]

    @pytest.mark.asyncio
    async def test_full_enterprise_pattern_integration(self):
        """Test all patterns working together."""
        # Setup components
        event_bus = EventBus()
        message_bus = MessageBus()
        cqrs = CQRS(event_bus)

        # Track events and messages
        events_received = []
        messages_received = []

        @event_bus.handler("search_completed")
        def track_event(event):
            events_received.append(event)

        async def track_message(message):
            messages_received.append(message)

        message_bus.subscribe("analytics", track_message)

        # Simulate MCP tool operation
        search_query = SearchMitigationsQuery("prompt injection", False)
        mock_handler = AsyncMock(return_value=[{"title": "ri-10"}])
        cqrs.register_query_handler(SearchMitigationsQuery, mock_handler)

        # Execute query through CQRS
        results = await cqrs.execute_query(search_query)

        # Publish domain event
        search_event = SearchCompletedEvent("prompt injection", results, "user1")
        event_bus.publish(search_event)

        # Send analytics message
        await message_bus.send(
            {
                "event_type": "search_completed",
                "query": "prompt injection",
                "user_id": "user1",
            },
            "analytics",
        )

        await asyncio.sleep(0.01)

        # Verify all patterns worked
        assert len(events_received) == 1
        assert len(messages_received) == 1
        assert events_received[0].query == "prompt injection"
        assert messages_received[0]["query"] == "prompt injection"
        mock_handler.assert_called_once_with(search_query)
