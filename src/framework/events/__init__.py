"""
Event-driven architecture components for enterprise microservices.

This package provides:
- Event bus with transactional outbox pattern
- Event handlers and subscription management
- Domain and system events
- Event registry and serialization
"""

from .event_bus import (
    EVENT_REGISTRY,
    BaseEvent,
    DomainEvent,
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

__all__ = [
    "EVENT_REGISTRY",
    "BaseEvent",
    "DomainEvent",
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
]
