"""
Enterprise Python patterns for MCP server.
Domain Events, CQRS, and Message Bus with backward compatibility.
"""

import asyncio
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class DomainEvent:
    """Base domain event."""

    event_type: str
    data: dict[str, Any]
    timestamp: datetime


@dataclass
class SearchCompletedEvent(DomainEvent):
    """Event fired when search is completed."""

    query: str
    results: list[dict[str, Any]]
    user_id: str

    def __init__(self, query: str, results: list[dict[str, Any]], user_id: str):
        super().__init__(
            event_type="search_completed",
            data={"query": query, "results": results, "user_id": user_id},
            timestamp=datetime.now()
        )
        self.query = query
        self.results = results
        self.user_id = user_id


@dataclass
class DocumentRetrievedEvent(DomainEvent):
    """Event fired when document is retrieved."""

    document_id: str
    document_type: str
    user_id: str

    def __init__(self, document_id: str, document_type: str, user_id: str):
        super().__init__(
            event_type="document_retrieved",
            data={"document_id": document_id, "document_type": document_type, "user_id": user_id},
            timestamp=datetime.now()
        )
        self.document_id = document_id
        self.document_type = document_type
        self.user_id = user_id


class EventBus:
    """Simple event bus for domain events."""

    def __init__(self):
        """Initialize event bus."""
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def register(self, event_type: str, handler: Callable[[DomainEvent], None]) -> None:
        """Register event handler."""
        self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> None:
        """Publish event to all registered handlers."""
        for handler in self._handlers.get(event.event_type, []):
            try:
                handler(event)
            except Exception:
                # Log error but don't stop other handlers (KISS approach)
                pass

    def handler(self, event_type: str):
        """Decorator for registering event handlers."""
        def decorator(func):
            self.register(event_type, func)
            return func
        return decorator


# CQRS Base Classes
class Command:
    """Base class for commands (write operations)."""
    pass


class Query:
    """Base class for queries (read operations)."""
    pass


# MCP-specific Commands
@dataclass
class UpdateSearchCacheCommand(Command):
    """Command to update search cache."""

    query: str
    results: list[dict[str, Any]]


@dataclass
class LogSearchCommand(Command):
    """Command to log search operation."""

    query: str
    results_count: int
    user_id: str


# MCP-specific Queries
@dataclass
class SearchMitigationsQuery(Query):
    """Query to search mitigations."""

    query: str
    exact_match: bool = False


@dataclass
class GetDocumentDetailsQuery(Query):
    """Query to get document details."""

    document_id: str


class CommandHandler:
    """Base command handler."""

    async def handle(self, command: Command) -> None:
        """Handle command."""
        pass


class QueryHandler:
    """Base query handler."""

    async def handle(self, query: Query) -> Any:
        """Handle query and return result."""
        pass


class CQRS:
    """Command Query Responsibility Separation implementation."""

    def __init__(self, event_bus: EventBus):
        """Initialize CQRS with event bus."""
        self.event_bus = event_bus
        self._command_handlers: dict[type[Command], Callable] = {}
        self._query_handlers: dict[type[Query], Callable] = {}

    def register_command_handler(self, command_type: type[Command], handler: Callable) -> None:
        """Register command handler."""
        self._command_handlers[command_type] = handler

    def register_query_handler(self, query_type: type[Query], handler: Callable) -> None:
        """Register query handler."""
        self._query_handlers[query_type] = handler

    async def execute_command(self, command: Command) -> None:
        """Execute command through registered handler."""
        handler = self._command_handlers.get(type(command))
        if handler:
            await handler(command)

    async def execute_query(self, query: Query) -> Any:
        """Execute query through registered handler."""
        handler = self._query_handlers.get(type(query))
        if handler:
            return await handler(query)
        return None


class MessageBus:
    """Simple async message bus."""

    def __init__(self):
        """Initialize message bus."""
        self._queues: dict[str, asyncio.Queue] = {}
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)

    async def send(self, message: dict[str, Any], topic: str) -> None:
        """Send message to topic."""
        # Add to queue
        if topic not in self._queues:
            self._queues[topic] = asyncio.Queue()

        await self._queues[topic].put(message)

        # Notify subscribers
        for subscriber in self._subscribers[topic]:
            try:
                # Run subscriber in background to avoid blocking
                task = asyncio.create_task(subscriber(message))
                # Store task reference to prevent garbage collection
                self._tasks = getattr(self, '_tasks', set())
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
            except Exception:
                # Log error but continue (KISS approach)
                pass

    async def receive(self, topic: str) -> dict[str, Any]:
        """Receive message from topic."""
        if topic not in self._queues:
            self._queues[topic] = asyncio.Queue()

        return await self._queues[topic].get()

    def subscribe(self, topic: str, handler: Callable) -> None:
        """Subscribe to topic with handler."""
        self._subscribers[topic].append(handler)
