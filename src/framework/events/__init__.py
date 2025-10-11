"""
Event-driven architecture components for enterprise microservices.

This package provides:
- Event bus with transactional outbox pattern
- Event handlers and subscription management
- Domain and system events
- Event registry and serialization
- Unified event publishing utilities for audit, notification, and domain events
"""

# New unified event publishing components
from .config import EventConfig, EventPublisherConfig
from .decorators import audit_event, domain_event, publish_on_error, publish_on_success
from .event_bus import (
    EVENT_REGISTRY,
    BaseEvent,
    DomainEvent,
    Event,
    EventBus,
    EventHandler,
    EventMetadata,
    EventRegistry,
    EventStatus,
    InMemoryEventBus,
    OutboxEvent,
    SystemEvent,
    TransactionalOutboxEventBus,
    event_transaction,
    publish_domain_event,
    publish_system_event,
    register_event,
)
from .exceptions import EventPublishingError
from .publisher import EventPublisher, get_event_publisher
from .types import AuditEventType, EventPriority, NotificationEventType

# Create aliases for commonly used types
# Event class is now concrete and exported directly

__all__ = [
    # Existing event bus components
    "EVENT_REGISTRY",
    "BaseEvent",
    "DomainEvent",
    "Event",
    "EventBus",
    "EventHandler",
    "EventMetadata",
    "EventRegistry",
    "EventStatus",
    "InMemoryEventBus",
    "OutboxEvent",
    "SystemEvent",
    "TransactionalOutboxEventBus",
    "event_transaction",
    "publish_domain_event",
    "publish_system_event",
    "register_event",
    # New unified event publishing components
    "EventConfig",
    "EventPublisherConfig",
    "EventPublisher",
    "get_event_publisher",
    "audit_event",
    "domain_event",
    "publish_on_success",
    "publish_on_error",
    "AuditEventType",
    "NotificationEventType",
    "EventPriority",
    "EventPublishingError",
]
