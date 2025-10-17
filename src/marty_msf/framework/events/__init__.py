"""
Event-driven architecture components for enterprise microservices.

This package provides:
- Event bus with transactional outbox pattern
- Event handlers and subscription management
- Domain and system events
- Event registry and serialization
- Unified event publishing utilities for audit, notification, and domain events
"""

# Unified event publishing components
from .config import EventConfig, EventPublisherConfig
from .decorators import audit_event, domain_event, publish_on_error, publish_on_success

# Enhanced event bus - the primary event system
from .enhanced_event_bus import (
    BaseEvent,
    DeadLetterEvent,
    DeliveryGuarantee,
    EnhancedEventBus,
    EventBackendType,
    EventBus,
    EventFilter,
    EventHandler,
    EventMetadata,
    EventPriority,
    EventStatus,
    KafkaConfig,
    OutboxEvent,
    PluginEventHandler,
    enhanced_event_bus_context,
)

# Enhanced event types
from .enhanced_events import EVENT_REGISTRY, DomainEvent, EventRegistry
from .enhanced_events import GenericEvent as Event
from .enhanced_events import SystemEvent, register_event
from .exceptions import EventPublishingError
from .publisher import EventPublisher, get_event_publisher
from .types import AuditEventType, NotificationEventType

# Create aliases for commonly used types
# Event class is now concrete and exported directly

__all__ = [
    # Enhanced event bus components
    "BaseEvent",
    "EventBus",
    "EnhancedEventBus",
    "EventHandler",
    "EventMetadata",
    "EventStatus",
    "EventPriority",
    "DeliveryGuarantee",
    "EventFilter",
    "PluginEventHandler",
    "OutboxEvent",
    "DeadLetterEvent",
    "enhanced_event_bus_context",
    "KafkaConfig",
    "EventBackendType",
    # Enhanced event types
    "EVENT_REGISTRY",
    "DomainEvent",
    "Event",
    "EventRegistry",
    "SystemEvent",
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
