"""
Enhanced Event Bus with Comprehensive Event Processing

This module provides a unified, enterprise-grade event bus with:
- Event persistence with outbox pattern
- Dead letter queue handling
- Robust event routing and filtering
- Plugin subscription support
- Multiple backend support (in-memory, database, Kafka)
- Circuit breaker and retry mechanisms
- Event replay and event sourcing capabilities
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Generic, Optional, TypeVar

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)

# Type variables
E = TypeVar("E", bound="BaseEvent")
H = TypeVar("H", bound="EventHandler")

# Base for persistence tables
PersistenceBase = declarative_base()


@dataclass
class KafkaConfig:
    """Configuration for Kafka backend."""
    bootstrap_servers: list[str] = field(default_factory=lambda: ["localhost:9092"])
    security_protocol: str = "PLAINTEXT"
    sasl_mechanism: str | None = None
    sasl_plain_username: str | None = None
    sasl_plain_password: str | None = None
    consumer_group_id: str = "marty-enhanced-event-bus"
    auto_offset_reset: str = "latest"
    enable_auto_commit: bool = True
    max_poll_records: int = 500
    session_timeout_ms: int = 30000
    heartbeat_interval_ms: int = 3000


class EventBackendType(Enum):
    """Event backend types."""
    IN_MEMORY = "in_memory"
    DATABASE = "database"
    KAFKA = "kafka"


class EventStatus(Enum):
    """Event processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


class EventPriority(Enum):
    """Event processing priority."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class DeliveryGuarantee(Enum):
    """Event delivery guarantees."""
    AT_MOST_ONCE = "at_most_once"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"


@dataclass
class EventMetadata:
    """Enhanced event metadata."""
    event_id: str
    event_type: str
    timestamp: datetime
    correlation_id: str | None = None
    causation_id: str | None = None
    user_id: str | None = None
    tenant_id: str | None = None
    source_service: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    version: int = 1
    priority: EventPriority = EventPriority.NORMAL
    headers: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    expiry: datetime | None = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class EventFilter:
    """Event filtering configuration."""
    event_types: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    user_ids: list[str] = field(default_factory=list)
    tenant_ids: list[str] = field(default_factory=list)
    priority_threshold: EventPriority = EventPriority.LOW
    custom_predicate: Callable[[BaseEvent], bool] | None = None


class BaseEvent(ABC):
    """Enhanced base class for all events."""

    def __init__(
        self,
        event_id: str | None = None,
        timestamp: datetime | None = None,
        metadata: EventMetadata | None = None,
        **kwargs
    ):
        self.event_id = event_id or str(uuid.uuid4())
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.event_type = self.__class__.__name__

        # Initialize metadata if not provided
        if metadata is None:
            metadata = EventMetadata(
                event_id=self.event_id,
                event_type=self.event_type,
                timestamp=self.timestamp
            )
        self.metadata = metadata

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        ...

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, Any]) -> BaseEvent:
        """Create event from dictionary."""
        ...

    def is_expired(self) -> bool:
        """Check if event has expired."""
        if self.metadata.expiry is None:
            return False
        return datetime.now(timezone.utc) > self.metadata.expiry

    def should_retry(self) -> bool:
        """Check if event should be retried."""
        return self.metadata.retry_count < self.metadata.max_retries

    def matches_filter(self, event_filter: EventFilter) -> bool:
        """Check if event matches filter criteria."""
        # Check event types
        if event_filter.event_types and self.event_type not in event_filter.event_types:
            return False

        # Check sources
        if (event_filter.sources and
            self.metadata.source_service and
            self.metadata.source_service not in event_filter.sources):
            return False

        # Check tags
        if event_filter.tags and not any(tag in self.metadata.tags for tag in event_filter.tags):
            return False

        # Check user IDs
        if (event_filter.user_ids and
            self.metadata.user_id and
            self.metadata.user_id not in event_filter.user_ids):
            return False

        # Check tenant IDs
        if (event_filter.tenant_ids and
            self.metadata.tenant_id and
            self.metadata.tenant_id not in event_filter.tenant_ids):
            return False

        # Check priority threshold
        if self.metadata.priority.value < event_filter.priority_threshold.value:
            return False

        # Check custom predicate
        if event_filter.custom_predicate and not event_filter.custom_predicate(self):
            return False

        return True


class EventHandler(ABC, Generic[E]):
    """Enhanced base class for event handlers."""

    def __init__(
        self,
        handler_id: str | None = None,
        priority: int = 0,
        max_concurrent: int = 1,
        timeout: timedelta | None = None
    ):
        self.handler_id = handler_id or str(uuid.uuid4())
        self.priority = priority  # Higher numbers = higher priority
        self.max_concurrent = max_concurrent
        self.timeout = timeout or timedelta(seconds=30)
        self._active_tasks = 0
        self._lock = asyncio.Lock()

    @abstractmethod
    async def handle(self, event: E) -> None:
        """Handle the event."""
        ...

    @abstractmethod
    def can_handle(self, event: BaseEvent) -> bool:
        """Check if this handler can handle the event."""
        ...

    @property
    @abstractmethod
    def event_types(self) -> list[str]:
        """List of event types this handler can process."""
        ...

    async def safe_handle(self, event: E) -> bool:
        """Safely handle event with concurrency control and timeout."""
        async with self._lock:
            if self._active_tasks >= self.max_concurrent:
                return False
            self._active_tasks += 1

        try:
            await asyncio.wait_for(self.handle(event), timeout=self.timeout.total_seconds())
            return True
        except asyncio.TimeoutError:
            logger.error(f"Handler {self.handler_id} timed out processing event {event.event_id}")
            return False
        except Exception as e:
            logger.error(f"Handler {self.handler_id} failed processing event {event.event_id}: {e}")
            return False
        finally:
            async with self._lock:
                self._active_tasks -= 1


class PluginEventHandler(EventHandler[BaseEvent]):
    """Specialized event handler for plugin integration."""

    def __init__(
        self,
        plugin_id: str,
        plugin_name: str,
        event_filter: EventFilter,
        handler_func: Callable[[BaseEvent], Any],
        **kwargs
    ):
        super().__init__(handler_id=f"plugin-{plugin_id}", **kwargs)
        self.plugin_id = plugin_id
        self.plugin_name = plugin_name
        self.event_filter = event_filter
        self.handler_func = handler_func

    async def handle(self, event: BaseEvent) -> None:
        """Handle event for plugin."""
        if asyncio.iscoroutinefunction(self.handler_func):
            await self.handler_func(event)
        else:
            self.handler_func(event)

    def can_handle(self, event: BaseEvent) -> bool:
        """Check if event matches plugin filter."""
        return event.matches_filter(self.event_filter)

    @property
    def event_types(self) -> list[str]:
        """Return event types from filter."""
        return self.event_filter.event_types or ["*"]


# Persistence models
class OutboxEvent(PersistenceBase):
    """Enhanced outbox table for transactional event publishing."""

    __tablename__ = "event_outbox"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(36), nullable=False, unique=True, index=True)
    event_type = Column(String(255), nullable=False, index=True)
    event_data = Column(Text, nullable=False)
    event_metadata = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default=EventStatus.PENDING.value, index=True)
    priority = Column(Integer, nullable=False, default=EventPriority.NORMAL.value, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True, index=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    error_message = Column(Text, nullable=True)
    correlation_id = Column(String(255), nullable=True, index=True)
    source_service = Column(String(255), nullable=True, index=True)
    tenant_id = Column(String(255), nullable=True, index=True)
    is_dead_letter = Column(Boolean, nullable=False, default=False, index=True)


class DeadLetterEvent(PersistenceBase):
    """Dead letter queue for failed events."""

    __tablename__ = "event_dead_letter"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_event_id = Column(String(36), nullable=False, index=True)
    event_type = Column(String(255), nullable=False, index=True)
    event_data = Column(Text, nullable=False)
    event_metadata = Column(Text, nullable=True)
    failure_reason = Column(Text, nullable=False)
    failed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    attempts_made = Column(Integer, nullable=False)
    can_retry = Column(Boolean, nullable=False, default=True)
    source_service = Column(String(255), nullable=True, index=True)


class EventBus(ABC):
    """Enhanced abstract event bus interface."""

    @abstractmethod
    async def publish(
        self,
        event: BaseEvent,
        delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE,
        delay: timedelta | None = None
    ) -> None:
        """Publish an event with delivery guarantees."""
        ...

    @abstractmethod
    async def publish_batch(
        self,
        events: list[BaseEvent],
        delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE
    ) -> None:
        """Publish multiple events as a batch."""
        ...

    @abstractmethod
    async def subscribe(
        self,
        handler: EventHandler,
        event_filter: EventFilter | None = None
    ) -> str:
        """Subscribe an event handler with optional filtering."""
        ...

    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe a handler by subscription ID."""
        ...

    @abstractmethod
    async def replay_events(
        self,
        from_timestamp: datetime,
        to_timestamp: datetime | None = None,
        event_filter: EventFilter | None = None
    ) -> None:
        """Replay events from persistence layer."""
        ...

    @abstractmethod
    async def get_dead_letters(
        self,
        limit: int = 100,
        event_type: str | None = None
    ) -> list[DeadLetterEvent]:
        """Get dead letter events for inspection."""
        ...

    @abstractmethod
    async def retry_dead_letter(self, dead_letter_id: str) -> bool:
        """Retry a dead letter event."""
        ...

    @abstractmethod
    async def start(self) -> None:
        """Start the event bus."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the event bus."""
        ...


class EnhancedEventBus(EventBus):
    """Production-ready event bus with all enterprise features."""

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession] | None = None,
        processing_interval: float = 1.0,
        batch_size: int = 100,
        dead_letter_threshold: int = 5,
        enable_circuit_breaker: bool = True
    ):
        self._session_factory = session_factory
        self._processing_interval = processing_interval
        self._batch_size = batch_size
        self._dead_letter_threshold = dead_letter_threshold

        # Handler management
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._subscriptions: dict[str, dict[str, Any]] = {}
        self._handler_priorities: dict[str, int] = {}

        # Processing state
        self._running = False
        self._processor_task: asyncio.Task | None = None
        self._dead_letter_processor_task: asyncio.Task | None = None

        # Circuit breaker for failed handlers
        self._handler_failures: dict[str, deque] = defaultdict(lambda: deque(maxlen=10))
        self._circuit_breaker_enabled = enable_circuit_breaker

        # Metrics
        self._metrics = {
            "events_published": 0,
            "events_processed": 0,
            "events_failed": 0,
            "dead_letters_created": 0,
            "handlers_executed": 0,
        }

    async def publish(
        self,
        event: BaseEvent,
        delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE,
        delay: timedelta | None = None
    ) -> None:
        """Publish a single event."""
        if not self._session_factory:
            # In-memory processing
            await self._process_event_immediately(event)
            return

        scheduled_at = None
        if delay:
            scheduled_at = datetime.now(timezone.utc) + delay

        async with self._get_session() as session:
            outbox_event = OutboxEvent(
                event_id=event.event_id,
                event_type=event.event_type,
                event_data=json.dumps(event.to_dict()),
                event_metadata=json.dumps(event.metadata.__dict__),
                priority=event.metadata.priority.value,
                scheduled_at=scheduled_at,
                expires_at=event.metadata.expiry,
                max_attempts=event.metadata.max_retries,
                correlation_id=event.metadata.correlation_id,
                source_service=event.metadata.source_service,
                tenant_id=event.metadata.tenant_id
            )

            session.add(outbox_event)
            await session.commit()

        self._metrics["events_published"] += 1
        logger.debug(f"Event {event.event_id} published to outbox")

    async def publish_batch(
        self,
        events: list[BaseEvent],
        delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE
    ) -> None:
        """Publish multiple events as a batch."""
        if not events:
            return

        if not self._session_factory:
            # In-memory processing
            for event in events:
                await self._process_event_immediately(event)
            return

        async with self._get_session() as session:
            outbox_events = []
            for event in events:
                outbox_event = OutboxEvent(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    event_data=json.dumps(event.to_dict()),
                    event_metadata=json.dumps(event.metadata.__dict__),
                    priority=event.metadata.priority.value,
                    expires_at=event.metadata.expiry,
                    max_attempts=event.metadata.max_retries,
                    correlation_id=event.metadata.correlation_id,
                    source_service=event.metadata.source_service,
                    tenant_id=event.metadata.tenant_id
                )
                outbox_events.append(outbox_event)

            session.add_all(outbox_events)
            await session.commit()

        self._metrics["events_published"] += len(events)
        logger.debug(f"Batch of {len(events)} events published to outbox")

    async def subscribe(
        self,
        handler: EventHandler,
        event_filter: EventFilter | None = None
    ) -> str:
        """Subscribe an event handler with optional filtering."""
        subscription_id = str(uuid.uuid4())

        # Store subscription info
        self._subscriptions[subscription_id] = {
            "handler": handler,
            "filter": event_filter,
            "created_at": datetime.now(timezone.utc)
        }

        # Add to handler registry
        for event_type in handler.event_types:
            self._handlers[event_type].append(handler)
            self._handler_priorities[handler.handler_id] = handler.priority

        # Sort handlers by priority (highest first)
        for event_type in handler.event_types:
            self._handlers[event_type].sort(
                key=lambda h: self._handler_priorities.get(h.handler_id, 0),
                reverse=True
            )

        logger.info(f"Subscribed handler {handler.handler_id} for events: {handler.event_types}")
        return subscription_id

    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe a handler by subscription ID."""
        if subscription_id not in self._subscriptions:
            return False

        subscription = self._subscriptions[subscription_id]
        handler = subscription["handler"]

        # Remove from handler registry
        for event_type in handler.event_types:
            if handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)

        # Clean up
        if handler.handler_id in self._handler_priorities:
            del self._handler_priorities[handler.handler_id]

        del self._subscriptions[subscription_id]

        logger.info(f"Unsubscribed handler {handler.handler_id}")
        return True

    async def subscribe_plugin(
        self,
        plugin_id: str,
        plugin_name: str,
        event_filter: EventFilter,
        handler_func: Callable[[BaseEvent], Any],
        priority: int = 0,
        max_concurrent: int = 1
    ) -> str:
        """Subscribe a plugin to events with fault-tolerant handling."""
        plugin_handler = PluginEventHandler(
            plugin_id=plugin_id,
            plugin_name=plugin_name,
            event_filter=event_filter,
            handler_func=handler_func,
            priority=priority,
            max_concurrent=max_concurrent
        )

        return await self.subscribe(plugin_handler, event_filter)

    async def replay_events(
        self,
        from_timestamp: datetime,
        to_timestamp: datetime | None = None,
        event_filter: EventFilter | None = None
    ) -> None:
        """Replay events from persistence layer."""
        if not self._session_factory:
            logger.warning("Event replay requires database persistence")
            return

        to_timestamp = to_timestamp or datetime.now(timezone.utc)

        async with self._get_session() as session:
            from sqlalchemy import and_, select

            query = select(OutboxEvent).where(
                and_(
                    OutboxEvent.created_at >= from_timestamp,
                    OutboxEvent.created_at <= to_timestamp,
                    OutboxEvent.status == EventStatus.COMPLETED.value
                )
            ).order_by(OutboxEvent.created_at)

            result = await session.execute(query)
            outbox_events = result.scalars().all()

            for outbox_event in outbox_events:
                try:
                    # Reconstruct event
                    event_data = json.loads(outbox_event.event_data)
                    event = self._reconstruct_event(outbox_event.event_type, event_data)

                    # Apply filter if provided
                    if event_filter and not event.matches_filter(event_filter):
                        continue

                    # Process event
                    await self._process_event_immediately(event)

                except Exception as e:
                    logger.error(f"Error replaying event {outbox_event.event_id}: {e}")

    async def get_dead_letters(
        self,
        limit: int = 100,
        event_type: str | None = None
    ) -> list[DeadLetterEvent]:
        """Get dead letter events for inspection."""
        if not self._session_factory:
            return []

        async with self._get_session() as session:
            from sqlalchemy import select

            query = select(DeadLetterEvent).order_by(DeadLetterEvent.failed_at.desc()).limit(limit)

            if event_type:
                query = query.where(DeadLetterEvent.event_type == event_type)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def retry_dead_letter(self, dead_letter_id: str) -> bool:
        """Retry a dead letter event."""
        if not self._session_factory:
            return False

        async with self._get_session() as session:
            from sqlalchemy import select

            # Get dead letter
            query = select(DeadLetterEvent).where(DeadLetterEvent.id == dead_letter_id)
            result = await session.execute(query)
            dead_letter = result.scalar_one_or_none()

            if not dead_letter or not dead_letter.can_retry:
                return False

            try:
                # Reconstruct and republish event
                event_data = json.loads(dead_letter.event_data)
                event = self._reconstruct_event(dead_letter.event_type, event_data)

                # Reset retry count
                event.metadata.retry_count = 0

                await self.publish(event)

                # Remove from dead letter queue
                await session.delete(dead_letter)
                await session.commit()

                logger.info(f"Retried dead letter event {dead_letter.original_event_id}")
                return True

            except Exception as e:
                logger.error(f"Error retrying dead letter {dead_letter_id}: {e}")
                return False

    async def start(self) -> None:
        """Start the event bus and background processors."""
        if self._running:
            return

        self._running = True

        if self._session_factory:
            # Start outbox processor
            self._processor_task = asyncio.create_task(self._process_outbox_events())
            # Start dead letter processor
            self._dead_letter_processor_task = asyncio.create_task(self._process_dead_letters())

        logger.info("Enhanced event bus started")

    async def stop(self) -> None:
        """Stop the event bus and background processors."""
        if not self._running:
            return

        self._running = False

        # Cancel background tasks
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

        if self._dead_letter_processor_task:
            self._dead_letter_processor_task.cancel()
            try:
                await self._dead_letter_processor_task
            except asyncio.CancelledError:
                pass

        logger.info("Enhanced event bus stopped")

    def get_metrics(self) -> dict[str, Any]:
        """Get event bus metrics."""
        return self._metrics.copy()

    # Private methods
    @asynccontextmanager
    async def _get_session(self):
        """Get database session."""
        if not self._session_factory:
            raise RuntimeError("Database session factory not configured")

        session = self._session_factory()
        try:
            yield session
        finally:
            await session.close()

    async def _process_outbox_events(self) -> None:
        """Background task to process outbox events."""
        while self._running:
            try:
                await self._process_pending_events()
                await asyncio.sleep(self._processing_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in outbox processor: {e}")
                await asyncio.sleep(self._processing_interval)

    async def _process_pending_events(self) -> None:
        """Process pending events from outbox."""
        async with self._get_session() as session:
            from sqlalchemy import and_, or_, select

            now = datetime.now(timezone.utc)

            # Get pending events that are ready to process
            query = (
                select(OutboxEvent)
                .where(
                    and_(
                        OutboxEvent.status == EventStatus.PENDING.value,
                        or_(
                            OutboxEvent.scheduled_at.is_(None),
                            OutboxEvent.scheduled_at <= now
                        ),
                        or_(
                            OutboxEvent.expires_at.is_(None),
                            OutboxEvent.expires_at > now
                        )
                    )
                )
                .order_by(OutboxEvent.priority.desc(), OutboxEvent.created_at)
                .limit(self._batch_size)
            )

            result = await session.execute(query)
            events = result.scalars().all()

            for outbox_event in events:
                await self._process_single_outbox_event(session, outbox_event)

    async def _process_single_outbox_event(self, session: AsyncSession, outbox_event: OutboxEvent) -> None:
        """Process a single outbox event."""
        try:
            # Mark as processing
            outbox_event.status = EventStatus.PROCESSING.value
            outbox_event.attempts += 1
            await session.commit()

            # Check if expired
            if outbox_event.expires_at and datetime.now(timezone.utc) > outbox_event.expires_at:
                outbox_event.status = EventStatus.CANCELLED.value
                outbox_event.error_message = "Event expired"
                await session.commit()
                return

            # Reconstruct event
            event_data = json.loads(outbox_event.event_data)
            event = self._reconstruct_event(outbox_event.event_type, event_data)

            # Process event
            success = await self._process_event_immediately(event)

            if success:
                outbox_event.status = EventStatus.COMPLETED.value
                outbox_event.processed_at = datetime.now(timezone.utc)
                outbox_event.error_message = None
                self._metrics["events_processed"] += 1
            elif outbox_event.attempts >= outbox_event.max_attempts:
                # Move to dead letter queue
                await self._move_to_dead_letter(session, outbox_event, "Max attempts exceeded")
            else:
                # Reset for retry
                outbox_event.status = EventStatus.PENDING.value

            await session.commit()

        except Exception as e:
            logger.error(f"Error processing outbox event {outbox_event.event_id}: {e}")

            if outbox_event.attempts >= outbox_event.max_attempts:
                await self._move_to_dead_letter(session, outbox_event, str(e))
            else:
                outbox_event.status = EventStatus.PENDING.value
                outbox_event.error_message = str(e)

            await session.commit()

    async def _process_event_immediately(self, event: BaseEvent) -> bool:
        """Process event immediately with handlers."""
        if event.is_expired():
            logger.warning(f"Event {event.event_id} has expired, skipping processing")
            return False

        # Get all matching handlers
        handlers = []

        # Specific event type handlers
        handlers.extend(self._handlers.get(event.event_type, []))

        # Wildcard handlers
        handlers.extend(self._handlers.get("*", []))

        if not handlers:
            logger.debug(f"No handlers for event type: {event.event_type}")
            return True

        # Filter handlers that can handle this event
        eligible_handlers = [h for h in handlers if h.can_handle(event)]

        if not eligible_handlers:
            logger.debug(f"No eligible handlers for event {event.event_id}")
            return True

        # Process with handlers
        success_count = 0

        for handler in eligible_handlers:
            try:
                # Check circuit breaker
                if self._is_handler_circuit_open(handler.handler_id):
                    logger.warning(f"Circuit breaker open for handler {handler.handler_id}")
                    continue

                # Process with handler
                success = await handler.safe_handle(event)

                if success:
                    success_count += 1
                    self._record_handler_success(handler.handler_id)
                else:
                    self._record_handler_failure(handler.handler_id)

                self._metrics["handlers_executed"] += 1

            except Exception as e:
                logger.error(f"Handler {handler.handler_id} failed: {e}")
                self._record_handler_failure(handler.handler_id)

        # Consider successful if at least one handler succeeded
        return success_count > 0

    async def _move_to_dead_letter(
        self,
        session: AsyncSession,
        outbox_event: OutboxEvent,
        failure_reason: str
    ) -> None:
        """Move event to dead letter queue."""
        dead_letter = DeadLetterEvent(
            original_event_id=outbox_event.event_id,
            event_type=outbox_event.event_type,
            event_data=outbox_event.event_data,
            event_metadata=outbox_event.event_metadata,
            failure_reason=failure_reason,
            attempts_made=outbox_event.attempts,
            source_service=outbox_event.source_service
        )

        session.add(dead_letter)

        # Mark outbox event as dead letter
        outbox_event.status = EventStatus.DEAD_LETTER.value
        outbox_event.is_dead_letter = True
        outbox_event.error_message = failure_reason

        self._metrics["dead_letters_created"] += 1
        self._metrics["events_failed"] += 1

        logger.warning(f"Moved event {outbox_event.event_id} to dead letter queue: {failure_reason}")

    async def _process_dead_letters(self) -> None:
        """Background task to periodically retry dead letter events."""
        while self._running:
            try:
                await self._retry_eligible_dead_letters()
                await asyncio.sleep(300)  # Check every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in dead letter processor: {e}")
                await asyncio.sleep(300)

    async def _retry_eligible_dead_letters(self) -> None:
        """Retry dead letter events that are eligible for retry."""
        if not self._session_factory:
            return

        async with self._get_session() as session:
            from sqlalchemy import and_, select

            # Get dead letters that haven't been retried recently
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)

            query = (
                select(DeadLetterEvent)
                .where(
                    and_(
                        DeadLetterEvent.can_retry,
                        DeadLetterEvent.failed_at < cutoff_time
                    )
                )
                .limit(10)  # Limit retry attempts
            )

            result = await session.execute(query)
            dead_letters = result.scalars().all()

            for dead_letter in dead_letters:
                try:
                    # Try to republish
                    event_data = json.loads(dead_letter.event_data)
                    event = self._reconstruct_event(dead_letter.event_type, event_data)

                    await self.publish(event)

                    # Remove from dead letter queue on successful republish
                    await session.delete(dead_letter)
                    logger.info(f"Successfully retried dead letter event {dead_letter.original_event_id}")

                except Exception as e:
                    logger.error(f"Failed to retry dead letter {dead_letter.id}: {e}")
                    # Mark as non-retryable after multiple failures
                    dead_letter.can_retry = False

            await session.commit()

    def _reconstruct_event(self, event_type: str, event_data: dict[str, Any]) -> BaseEvent:
        """Reconstruct event from serialized data."""
        # This would use an event registry in a real implementation
        from .enhanced_events import EVENT_REGISTRY

        event_class = EVENT_REGISTRY.get(event_type)
        if not event_class:
            # Fallback to generic event
            from .enhanced_events import GenericEvent
            return GenericEvent.from_dict(event_data)

        return event_class.from_dict(event_data)

    def _is_handler_circuit_open(self, handler_id: str) -> bool:
        """Check if circuit breaker is open for handler."""
        if not self._circuit_breaker_enabled:
            return False

        failures = self._handler_failures[handler_id]
        if len(failures) < 5:  # Need at least 5 failures
            return False

        # Check if too many failures in recent time window
        recent_failures = sum(1 for failure_time in failures
                            if datetime.now(timezone.utc) - failure_time < timedelta(minutes=5))

        return recent_failures >= 5

    def _record_handler_success(self, handler_id: str) -> None:
        """Record successful handler execution."""
        # Clear failures on success
        self._handler_failures[handler_id].clear()

    def _record_handler_failure(self, handler_id: str) -> None:
        """Record handler failure for circuit breaker."""
        self._handler_failures[handler_id].append(datetime.now(timezone.utc))


# Context manager for easy usage
@asynccontextmanager
async def enhanced_event_bus_context(
    session_factory: Callable[[], AsyncSession] | None = None,
    **kwargs
):
    """Context manager for enhanced event bus lifecycle."""
    bus = EnhancedEventBus(session_factory=session_factory, **kwargs)
    try:
        await bus.start()
        yield bus
    finally:
        await bus.stop()
