"""
Core Event Streaming Abstractions

Fundamental classes and interfaces for event-driven architecture,
event sourcing, and stream processing capabilities.
"""

import asyncio
import builtins
import json
import logging
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
E = TypeVar("E", bound="Event")


class EventType(Enum):
    """Standard event types."""

    DOMAIN = "domain"
    INTEGRATION = "integration"
    NOTIFICATION = "notification"
    SYSTEM = "system"
    ERROR = "error"
    AUDIT = "audit"


@dataclass(frozen=True)
class EventMetadata:
    """Event metadata containing tracking and context information."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    causation_id: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    version: int = 1

    # Source information
    source_service: str | None = None
    source_user: str | None = None
    source_system: str | None = None

    # Context
    tenant_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None

    # Routing
    topic: str | None = None
    partition_key: str | None = None

    # Additional metadata
    properties: builtins.dict[str, Any] = field(default_factory=dict)

    def with_causation(self, causation_id: str) -> "EventMetadata":
        """Create new metadata with causation relationship."""
        return EventMetadata(
            event_id=str(uuid.uuid4()),
            correlation_id=self.correlation_id,
            causation_id=causation_id,
            timestamp=datetime.utcnow(),
            version=self.version,
            source_service=self.source_service,
            source_user=self.source_user,
            source_system=self.source_system,
            tenant_id=self.tenant_id,
            trace_id=self.trace_id,
            span_id=self.span_id,
            topic=self.topic,
            partition_key=self.partition_key,
            properties=self.properties.copy(),
        )


@dataclass
class Event:
    """Base event class for all domain and integration events."""

    # Event identification
    aggregate_id: str
    event_type: str
    event_data: builtins.dict[str, Any]
    metadata: EventMetadata = field(default_factory=EventMetadata)

    # Event categorization
    event_category: EventType = EventType.DOMAIN
    aggregate_type: str | None = None
    event_version: int = 1

    @property
    def event_id(self) -> str:
        """Get event ID from metadata."""
        return self.metadata.event_id

    @property
    def correlation_id(self) -> str:
        """Get correlation ID from metadata."""
        return self.metadata.correlation_id

    @property
    def timestamp(self) -> datetime:
        """Get event timestamp."""
        return self.metadata.timestamp

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_id": self.metadata.event_id,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "event_type": self.event_type,
            "event_category": self.event_category.value,
            "event_version": self.event_version,
            "event_data": self.event_data,
            "metadata": {
                "correlation_id": self.metadata.correlation_id,
                "causation_id": self.metadata.causation_id,
                "timestamp": self.metadata.timestamp.isoformat(),
                "version": self.metadata.version,
                "source_service": self.metadata.source_service,
                "source_user": self.metadata.source_user,
                "source_system": self.metadata.source_system,
                "tenant_id": self.metadata.tenant_id,
                "trace_id": self.metadata.trace_id,
                "span_id": self.metadata.span_id,
                "topic": self.metadata.topic,
                "partition_key": self.metadata.partition_key,
                "properties": self.metadata.properties,
            },
        }

    @classmethod
    def from_dict(cls, data: builtins.dict[str, Any]) -> "Event":
        """Create event from dictionary."""
        metadata_data = data.get("metadata", {})

        metadata = EventMetadata(
            event_id=data["event_id"],
            correlation_id=metadata_data.get("correlation_id", str(uuid.uuid4())),
            causation_id=metadata_data.get("causation_id"),
            timestamp=datetime.fromisoformat(metadata_data["timestamp"])
            if metadata_data.get("timestamp")
            else datetime.utcnow(),
            version=metadata_data.get("version", 1),
            source_service=metadata_data.get("source_service"),
            source_user=metadata_data.get("source_user"),
            source_system=metadata_data.get("source_system"),
            tenant_id=metadata_data.get("tenant_id"),
            trace_id=metadata_data.get("trace_id"),
            span_id=metadata_data.get("span_id"),
            topic=metadata_data.get("topic"),
            partition_key=metadata_data.get("partition_key"),
            properties=metadata_data.get("properties", {}),
        )

        return cls(
            aggregate_id=data["aggregate_id"],
            event_type=data["event_type"],
            event_data=data["event_data"],
            metadata=metadata,
            event_category=EventType(data.get("event_category", "domain")),
            aggregate_type=data.get("aggregate_type"),
            event_version=data.get("event_version", 1),
        )


class EventSerializer(ABC):
    """Abstract event serializer interface."""

    @abstractmethod
    def serialize(self, event: Event) -> bytes:
        """Serialize event to bytes."""
        raise NotImplementedError

    @abstractmethod
    def deserialize(self, data: bytes) -> Event:
        """Deserialize bytes to event."""
        raise NotImplementedError


class JSONEventSerializer(EventSerializer):
    """JSON-based event serializer."""

    def serialize(self, event: Event) -> bytes:
        """Serialize event to JSON bytes."""
        return json.dumps(event.to_dict()).encode("utf-8")

    def deserialize(self, data: bytes) -> Event:
        """Deserialize JSON bytes to event."""
        event_dict = json.loads(data.decode("utf-8"))
        return Event.from_dict(event_dict)


class EventHandler(ABC, Generic[E]):
    """Abstract event handler interface."""

    @abstractmethod
    async def handle(self, event: E) -> None:
        """Handle the event."""
        raise NotImplementedError

    @abstractmethod
    def can_handle(self, event: Event) -> bool:
        """Check if this handler can handle the event."""
        raise NotImplementedError


class EventStore(ABC):
    """Abstract event store interface for persistence."""

    @abstractmethod
    async def append_events(
        self,
        stream_id: str,
        events: builtins.list[Event],
        expected_version: int | None = None,
    ) -> None:
        """Append events to a stream."""
        raise NotImplementedError

    @abstractmethod
    async def get_events(
        self, stream_id: str, from_version: int = 0, to_version: int | None = None
    ) -> builtins.list[Event]:
        """Get events from a stream."""
        raise NotImplementedError

    @abstractmethod
    async def get_stream_version(self, stream_id: str) -> int:
        """Get current version of a stream."""
        raise NotImplementedError

    @abstractmethod
    async def stream_exists(self, stream_id: str) -> bool:
        """Check if stream exists."""
        raise NotImplementedError

    @abstractmethod
    async def delete_stream(self, stream_id: str) -> None:
        """Delete a stream."""
        raise NotImplementedError


class InMemoryEventStore(EventStore):
    """In-memory event store implementation for testing."""

    def __init__(self):
        self._streams: builtins.dict[str, builtins.list[Event]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def append_events(
        self,
        stream_id: str,
        events: builtins.list[Event],
        expected_version: int | None = None,
    ) -> None:
        """Append events to stream."""
        async with self._lock:
            current_version = len(self._streams[stream_id])

            if expected_version is not None and current_version != expected_version:
                raise ValueError(
                    f"Expected version {expected_version}, but stream is at version {current_version}"
                )

            self._streams[stream_id].extend(events)

    async def get_events(
        self, stream_id: str, from_version: int = 0, to_version: int | None = None
    ) -> builtins.list[Event]:
        """Get events from stream."""
        async with self._lock:
            events = self._streams[stream_id]

            if to_version is None:
                return events[from_version:]
            return events[from_version : to_version + 1]

    async def get_stream_version(self, stream_id: str) -> int:
        """Get current stream version."""
        async with self._lock:
            return len(self._streams[stream_id])

    async def stream_exists(self, stream_id: str) -> bool:
        """Check if stream exists."""
        async with self._lock:
            return stream_id in self._streams

    async def delete_stream(self, stream_id: str) -> None:
        """Delete stream."""
        async with self._lock:
            if stream_id in self._streams:
                del self._streams[stream_id]


class EventStream:
    """Event stream for reading events."""

    def __init__(self, stream_id: str, events: builtins.list[Event]):
        self.stream_id = stream_id
        self.events = events
        self.version = len(events)

    def __iter__(self) -> Iterator[Event]:
        """Iterate over events."""
        return iter(self.events)

    def __len__(self) -> int:
        """Get number of events."""
        return len(self.events)

    def __getitem__(self, index: int) -> Event:
        """Get event by index."""
        return self.events[index]

    def slice(
        self, from_version: int = 0, to_version: int | None = None
    ) -> "EventStream":
        """Get slice of events."""
        if to_version is None:
            sliced_events = self.events[from_version:]
        else:
            sliced_events = self.events[from_version : to_version + 1]

        return EventStream(self.stream_id, sliced_events)


class EventBus(ABC):
    """Abstract event bus for publishing and subscribing to events."""

    @abstractmethod
    async def publish(self, event: Event) -> None:
        """Publish an event."""
        raise NotImplementedError

    @abstractmethod
    async def publish_batch(self, events: builtins.list[Event]) -> None:
        """Publish multiple events."""
        raise NotImplementedError

    @abstractmethod
    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe handler to event type."""
        raise NotImplementedError

    @abstractmethod
    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Unsubscribe handler from event type."""
        raise NotImplementedError


class InMemoryEventBus(EventBus):
    """In-memory event bus implementation."""

    def __init__(self):
        self._handlers: builtins.dict[str, builtins.list[EventHandler]] = defaultdict(
            list
        )
        self._global_handlers: builtins.list[EventHandler] = []
        self._lock = asyncio.Lock()

    async def publish(self, event: Event) -> None:
        """Publish single event."""
        await self.publish_batch([event])

    async def publish_batch(self, events: builtins.list[Event]) -> None:
        """Publish multiple events."""
        for event in events:
            await self._dispatch_event(event)

    async def _dispatch_event(self, event: Event) -> None:
        """Dispatch event to handlers."""
        async with self._lock:
            # Get specific handlers
            handlers = self._handlers.get(event.event_type, []).copy()
            # Add global handlers
            handlers.extend(self._global_handlers)

        # Execute handlers concurrently
        tasks = []
        for handler in handlers:
            if handler.can_handle(event):
                tasks.append(asyncio.create_task(handler.handle(event)))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe handler to event type."""
        if event_type == "*":
            self._global_handlers.append(handler)
        else:
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Unsubscribe handler from event type."""
        if event_type == "*":
            if handler in self._global_handlers:
                self._global_handlers.remove(handler)
        elif handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)


class EventDispatcher:
    """Event dispatcher orchestrating store and bus operations."""

    def __init__(self, event_store: EventStore, event_bus: EventBus):
        self.event_store = event_store
        self.event_bus = event_bus

    async def dispatch_events(
        self,
        stream_id: str,
        events: builtins.list[Event],
        expected_version: int | None = None,
    ) -> None:
        """Store events and publish to bus."""
        # Store events first
        await self.event_store.append_events(stream_id, events, expected_version)

        # Then publish to bus
        await self.event_bus.publish_batch(events)

    async def replay_events(self, stream_id: str, from_version: int = 0) -> None:
        """Replay events from store to bus."""
        events = await self.event_store.get_events(stream_id, from_version)
        await self.event_bus.publish_batch(events)


class EventProcessingError(Exception):
    """Exception raised during event processing."""

    def __init__(self, message: str, event: Event, original_error: Exception = None):
        super().__init__(message)
        self.event = event
        self.original_error = original_error


class EventSubscription:
    """Event subscription configuration."""

    def __init__(
        self,
        event_type: str,
        handler: EventHandler,
        group_id: str | None = None,
        auto_ack: bool = True,
        max_retries: int = 3,
        backoff_multiplier: float = 2.0,
    ):
        self.event_type = event_type
        self.handler = handler
        self.group_id = group_id
        self.auto_ack = auto_ack
        self.max_retries = max_retries
        self.backoff_multiplier = backoff_multiplier


# Domain event patterns
class DomainEvent(Event):
    """Base class for domain events."""

    def __init__(
        self,
        aggregate_id: str,
        event_type: str,
        event_data: builtins.dict[str, Any],
        metadata: EventMetadata = None,
    ):
        super().__init__(
            aggregate_id=aggregate_id,
            event_type=event_type,
            event_data=event_data,
            metadata=metadata or EventMetadata(),
            event_category=EventType.DOMAIN,
        )


class IntegrationEvent(Event):
    """Base class for integration events."""

    def __init__(
        self,
        aggregate_id: str,
        event_type: str,
        event_data: builtins.dict[str, Any],
        metadata: EventMetadata = None,
    ):
        super().__init__(
            aggregate_id=aggregate_id,
            event_type=event_type,
            event_data=event_data,
            metadata=metadata or EventMetadata(),
            event_category=EventType.INTEGRATION,
        )


# Event factory functions
def create_domain_event(
    aggregate_id: str,
    event_type: str,
    event_data: builtins.dict[str, Any],
    **metadata_kwargs,
) -> DomainEvent:
    """Create a domain event with metadata."""
    metadata = EventMetadata(**metadata_kwargs)
    return DomainEvent(aggregate_id, event_type, event_data, metadata)


def create_integration_event(
    aggregate_id: str,
    event_type: str,
    event_data: builtins.dict[str, Any],
    **metadata_kwargs,
) -> IntegrationEvent:
    """Create an integration event with metadata."""
    metadata = EventMetadata(**metadata_kwargs)
    return IntegrationEvent(aggregate_id, event_type, event_data, metadata)


# Convenience functions for testing
def create_test_event(
    aggregate_id: str = None,
    event_type: str = "TestEvent",
    event_data: builtins.dict[str, Any] = None,
) -> Event:
    """Create a test event."""
    return Event(
        aggregate_id=aggregate_id or str(uuid.uuid4()),
        event_type=event_type,
        event_data=event_data or {"test": True},
        metadata=EventMetadata(),
    )
