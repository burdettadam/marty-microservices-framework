"""
Event bus ifrom typing import (
    Type,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    dict,
    list,
    type,
)n with transactional outbox pattern.
Provides reliable event publishing with guaranteed delivery and transaction support.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)
# Type variables
EventType = TypeVar("EventType", bound="BaseEvent")
HandlerType = TypeVar("HandlerType", bound="EventHandler")
# Base for outbox table
OutboxBase = declarative_base()


class EventStatus(Enum):
    """Event processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BaseEvent(ABC):
    """Base class for all events."""

    def __init__(self, event_id: str | None = None, timestamp: datetime | None = None):
        self.event_id = event_id or str(uuid.uuid4())
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.event_type = self.__class__.__name__

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        ...

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, Any]) -> BaseEvent:
        """Create event from dictionary."""
        ...


class EventHandler(ABC):
    """Base class for event handlers."""

    @abstractmethod
    async def handle(self, event: BaseEvent) -> None:
        """Handle an event."""
        ...

    @property
    @abstractmethod
    def event_types(self) -> list[str]:
        """List of event types this handler can process."""
        ...


@dataclass
class EventMetadata:
    """Event metadata for processing."""

    event_id: str
    event_type: str
    correlation_id: str | None = None
    causation_id: str | None = None
    user_id: str | None = None
    tenant_id: str | None = None
    source_service: str | None = None
    version: int = 1
    headers: dict[str, str] = field(default_factory=dict)


class OutboxEvent(OutboxBase):
    """Outbox table for transactional event publishing."""

    __tablename__ = "event_outbox"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(36), nullable=False, unique=True)
    event_type = Column(String(255), nullable=False)
    event_data = Column(Text, nullable=False)
    metadata = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default=EventStatus.PENDING.value)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    processed_at = Column(DateTime(timezone=True), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    error_message = Column(Text, nullable=True)

    def __repr__(self):
        return f"<OutboxEvent(id={self.id}, event_type={self.event_type}, status={self.status})>"


class EventBus(ABC):
    """Abstract event bus interface."""

    @abstractmethod
    async def publish(
        self, event: BaseEvent, metadata: EventMetadata | None = None
    ) -> None:
        """Publish an event."""
        ...

    @abstractmethod
    async def subscribe(self, handler: EventHandler) -> None:
        """Subscribe an event handler."""
        ...

    @abstractmethod
    async def unsubscribe(self, handler: EventHandler) -> None:
        """Unsubscribe an event handler."""
        ...

    @abstractmethod
    async def start(self) -> None:
        """Start the event bus."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the event bus."""
        ...


class InMemoryEventBus(EventBus):
    """In-memory event bus implementation for testing."""

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = {}
        self._running = False

    async def publish(
        self, event: BaseEvent, metadata: EventMetadata | None = None
    ) -> None:
        """Publish an event immediately."""
        if not self._running:
            logger.warning("Event bus not running, event will be processed immediately")
        event_type = event.event_type
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                await handler.handle(event)
            except Exception as e:
                logger.error(
                    "Error handling event %s with handler %s: %s",
                    event.event_id,
                    handler.__class__.__name__,
                    e,
                )

    async def subscribe(self, handler: EventHandler) -> None:
        """Subscribe an event handler."""
        for event_type in handler.event_types:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)
        logger.info(
            "Subscribed handler %s for events: %s",
            handler.__class__.__name__,
            handler.event_types,
        )

    async def unsubscribe(self, handler: EventHandler) -> None:
        """Unsubscribe an event handler."""
        for event_type in handler.event_types:
            if event_type in self._handlers:
                self._handlers[event_type] = [
                    h for h in self._handlers[event_type] if h != handler
                ]
        logger.info("Unsubscribed handler %s", handler.__class__.__name__)

    async def start(self) -> None:
        """Start the event bus."""
        self._running = True
        logger.info("In-memory event bus started")

    async def stop(self) -> None:
        """Stop the event bus."""
        self._running = False
        logger.info("In-memory event bus stopped")


class TransactionalOutboxEventBus(EventBus):
    """Event bus with transactional outbox pattern."""

    def __init__(self, session_factory: Callable[[], AsyncSession]):
        self._session_factory = session_factory
        self._handlers: dict[str, list[EventHandler]] = {}
        self._running = False
        self._processor_task: asyncio.Task | None = None
        self._processing_interval = 5.0  # seconds

    async def publish(
        self, event: BaseEvent, metadata: EventMetadata | None = None
    ) -> None:
        """Publish an event to the outbox."""
        async with self._get_session() as session:
            # Serialize event data
            event_data = json.dumps(event.to_dict())
            metadata_data = json.dumps(metadata.__dict__ if metadata else {})
            # Create outbox entry
            outbox_event = OutboxEvent(
                event_id=event.event_id,
                event_type=event.event_type,
                event_data=event_data,
                metadata=metadata_data,
            )
            session.add(outbox_event)
            await session.commit()
            logger.debug("Event %s published to outbox", event.event_id)

    async def subscribe(self, handler: EventHandler) -> None:
        """Subscribe an event handler."""
        for event_type in handler.event_types:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)
        logger.info(
            "Subscribed handler %s for events: %s",
            handler.__class__.__name__,
            handler.event_types,
        )

    async def unsubscribe(self, handler: EventHandler) -> None:
        """Unsubscribe an event handler."""
        for event_type in handler.event_types:
            if event_type in self._handlers:
                self._handlers[event_type] = [
                    h for h in self._handlers[event_type] if h != handler
                ]
        logger.info("Unsubscribed handler %s", handler.__class__.__name__)

    async def start(self) -> None:
        """Start the event bus and background processor."""
        if self._running:
            return
        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())
        logger.info("Transactional outbox event bus started")

    async def stop(self) -> None:
        """Stop the event bus and background processor."""
        if not self._running:
            return
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        logger.info("Transactional outbox event bus stopped")

    @asynccontextmanager
    async def _get_session(self) -> AsyncIterator[AsyncSession]:
        """Get database session."""
        session = self._session_factory()
        try:
            yield session
        finally:
            await session.close()

    async def _process_events(self) -> None:
        """Background task to process outbox events."""
        while self._running:
            try:
                await self._process_pending_events()
                await asyncio.sleep(self._processing_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in event processor: %s", e)
                await asyncio.sleep(self._processing_interval)

    async def _process_pending_events(self) -> None:
        """Process pending events from the outbox."""
        async with self._get_session() as session:
            # Get pending events
            from sqlalchemy import select

            stmt = (
                select(OutboxEvent)
                .where(OutboxEvent.status == EventStatus.PENDING.value)
                .order_by(OutboxEvent.created_at)
                .limit(10)
            )
            result = await session.execute(stmt)
            events = result.scalars().all()
            for outbox_event in events:
                await self._process_single_event(session, outbox_event)

    async def _process_single_event(
        self, session: AsyncSession, outbox_event: OutboxEvent
    ) -> None:
        """Process a single outbox event."""
        try:
            # Mark as processing
            outbox_event.status = EventStatus.PROCESSING.value
            outbox_event.attempts += 1
            await session.commit()
            # Get handlers for this event type
            handlers = self._handlers.get(outbox_event.event_type, [])
            if not handlers:
                logger.warning(
                    "No handlers for event type: %s", outbox_event.event_type
                )
                outbox_event.status = EventStatus.COMPLETED.value
                outbox_event.processed_at = datetime.now(timezone.utc)
                await session.commit()
                return
            # Deserialize event data
            event_data = json.loads(outbox_event.event_data)
            event = self._reconstruct_event(outbox_event.event_type, event_data)
            # Process with each handler
            success = True
            for handler in handlers:
                try:
                    await handler.handle(event)
                except Exception as e:
                    logger.error(
                        "Handler %s failed for event %s: %s",
                        handler.__class__.__name__,
                        outbox_event.event_id,
                        e,
                    )
                    success = False
                    break
            if success:
                outbox_event.status = EventStatus.COMPLETED.value
                outbox_event.processed_at = datetime.now(timezone.utc)
                outbox_event.error_message = None
            elif outbox_event.attempts >= outbox_event.max_attempts:
                outbox_event.status = EventStatus.FAILED.value
                outbox_event.error_message = "Max attempts exceeded"
            else:
                outbox_event.status = EventStatus.PENDING.value
            await session.commit()
        except Exception as e:
            logger.error("Error processing event %s: %s", outbox_event.event_id, e)
            outbox_event.status = EventStatus.FAILED.value
            outbox_event.error_message = str(e)
            await session.commit()

    def _reconstruct_event(
        self, event_type: str, event_data: dict[str, Any]
    ) -> BaseEvent:
        """Reconstruct event from data."""
        # This is a simplified reconstruction - in practice you'd have a registry
        # of event types to classes
        from .events import EVENT_REGISTRY

        event_class = EVENT_REGISTRY.get(event_type)
        if not event_class:
            raise ValueError(f"Unknown event type: {event_type}")
        return event_class.from_dict(event_data)


class EventRegistry:
    """Registry for event types."""

    def __init__(self):
        self._events: dict[str, type[BaseEvent]] = {}

    def register(self, event_class: type[BaseEvent]) -> None:
        """Register an event class."""
        self._events[event_class.__name__] = event_class
        logger.debug("Registered event type: %s", event_class.__name__)

    def get(self, event_type: str) -> type[BaseEvent] | None:
        """Get event class by type name."""
        return self._events.get(event_type)

    def list_types(self) -> list[str]:
        """List all registered event types."""
        return list(self._events.keys())


# Global event registry
EVENT_REGISTRY = EventRegistry()


def register_event(event_class: type[BaseEvent]) -> type[BaseEvent]:
    """Decorator to register an event class."""
    EVENT_REGISTRY.register(event_class)
    return event_class


# Common event types
@register_event
class DomainEvent(BaseEvent):
    """Base domain event."""

    def __init__(self, aggregate_id: str, aggregate_type: str, **kwargs):
        super().__init__(**kwargs)
        self.aggregate_id = aggregate_id
        self.aggregate_type = aggregate_type

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainEvent:
        return cls(
            event_id=data["event_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            aggregate_id=data["aggregate_id"],
            aggregate_type=data["aggregate_type"],
        )


@register_event
class SystemEvent(BaseEvent):
    """System-level event."""

    def __init__(
        self, source: str, action: str, details: dict[str, Any] | None = None, **kwargs
    ):
        super().__init__(**kwargs)
        self.source = source
        self.action = action
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "action": self.action,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SystemEvent:
        return cls(
            event_id=data["event_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data["source"],
            action=data["action"],
            details=data.get("details", {}),
        )


# Utility functions
async def publish_domain_event(
    event_bus: EventBus,
    aggregate_id: str,
    aggregate_type: str,
    event_type: str = "DomainEvent",
    metadata: EventMetadata | None = None,
    **kwargs,
) -> None:
    """Publish a domain event."""
    event = DomainEvent(
        aggregate_id=aggregate_id, aggregate_type=aggregate_type, **kwargs
    )
    await event_bus.publish(event, metadata)


async def publish_system_event(
    event_bus: EventBus,
    source: str,
    action: str,
    details: dict[str, Any] | None = None,
    metadata: EventMetadata | None = None,
    **kwargs,
) -> None:
    """Publish a system event."""
    event = SystemEvent(source=source, action=action, details=details, **kwargs)
    await event_bus.publish(event, metadata)


# Context manager for event publishing within transactions
@asynccontextmanager
async def event_transaction(
    event_bus: TransactionalOutboxEventBus, session: AsyncSession
) -> AsyncIterator[list[BaseEvent]]:
    """Context manager for collecting events within a transaction."""
    events: list[BaseEvent] = []
    try:
        yield events
        # Publish all collected events
        for event in events:
            await event_bus.publish(event)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
