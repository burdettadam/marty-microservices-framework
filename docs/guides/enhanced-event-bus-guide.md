# Enhanced Event Bus Guide

This guide covers the Enhanced Event Bus system in the Marty Microservices Framework, which provides a unified, enterprise-grade event publishing system.

## Overview

The Enhanced Event Bus provides:

- **Unified Interface**: Single event bus supporting all event patterns
- **Kafka-Only Backend**: Production-ready, simplified architecture
- **Transactional Outbox**: ACID compliance for event publishing
- **Rich Metadata**: Comprehensive event context and tracing
- **Pattern Support**: Built-in support for domain, audit, and integration events
- **Resilience**: Circuit breakers, retries, and dead letter queues

## Quick Start

### Basic Setup

```python
from marty_msf.framework.events import EnhancedEventBus, KafkaConfig, BaseEvent, EventMetadata
import uuid
from datetime import datetime, timezone

# Create event bus
kafka_config = KafkaConfig(
    bootstrap_servers=["localhost:9092"],
    consumer_group_id="my-service"
)
event_bus = EnhancedEventBus(kafka_config)

# Start the event bus
await event_bus.start()
```

### Publishing Events

```python
# Create an event
event = BaseEvent(
    event_type="user.created",
    data={
        "user_id": "user-123",
        "email": "user@example.com",
        "created_at": datetime.now(timezone.utc).isoformat()
    },
    metadata=EventMetadata(
        event_id=str(uuid.uuid4()),
        event_type="user.created",
        timestamp=datetime.now(timezone.utc),
        correlation_id="user-123"
    )
)

# Publish the event
await event_bus.publish(event)
```

### Using Transactional Outbox

```python
from marty_msf.framework.events import OutboxConfig
from sqlalchemy.orm import Session

# Configure outbox pattern
outbox_config = OutboxConfig(
    database_url="postgresql://user:pass@localhost/db",
    batch_size=100,
    max_retries=3
)

event_bus = EnhancedEventBus(kafka_config, outbox_config)
await event_bus.start()

# Publish with transaction
async with database_session() as session:
    # Your database operations here
    user = User(email="user@example.com")
    session.add(user)

    # Publish event within same transaction
    event = BaseEvent(
        event_type="user.created",
        data={"user_id": user.id, "email": user.email},
        metadata=EventMetadata(
            event_id=str(uuid.uuid4()),
            event_type="user.created",
            timestamp=datetime.now(timezone.utc),
            correlation_id=user.id
        )
    )

    await event_bus.publish_transactional(event, session)
    session.commit()  # Event and data committed together
```

## Enhanced Publishing Methods

### Retry with Exponential Backoff

```python
# Automatic retry with exponential backoff
await event_bus.publish_with_retry(
    event=event,
    max_retries=3,
    backoff_factor=2.0
)
```

### Batch Publishing

```python
events = [event1, event2, event3]

# Direct batch publishing
await event_bus.publish_batch(events)

# Transactional batch publishing
async with database_session() as session:
    await event_bus.publish_batch(events, use_transaction=True, session=session)
    session.commit()
```

### Scheduled Publishing

```python
from datetime import timedelta

# Schedule event for future publishing
future_time = datetime.now(timezone.utc) + timedelta(hours=1)
await event_bus.publish_scheduled(event, future_time)
```

## Pattern-Based Publishing

### Domain Aggregate Events

```python
# Domain aggregate pattern
await event_bus.publish_domain_aggregate_event(
    aggregate_type="user",
    aggregate_id="user-123",
    event_type="profile_updated",
    event_data={"email": "new@example.com"},
    version=2
)
```

### Saga Events

```python
# Saga orchestration events
async with database_session() as session:
    await event_bus.publish_saga_event(
        saga_id="order-saga-456",
        saga_type="order_processing",
        event_type="payment_requested",
        event_data={"order_id": "order-789", "amount": 99.99},
        session=session
    )
    session.commit()
```

## Using Decorators

The Enhanced Event Bus works with decorators for automatic event publishing:

### Audit Events

```python
from marty_msf.framework.events import audit_event, AuditEventType

class UserService:
    @audit_event(
        event_type=AuditEventType.DATA_CREATED,
        action="create_user",
        resource_type="user",
        resource_id_field="user_id",
        include_args=True
    )
    async def create_user(self, user_id: str, user_data: dict) -> User:
        # Implementation creates user
        return user
```

### Domain Events

```python
from marty_msf.framework.events import domain_event

class UserService:
    @domain_event(
        aggregate_type="user",
        event_type="user_updated",
        aggregate_id_field="user_id"
    )
    async def update_user(self, user_id: str, updates: dict) -> User:
        # Implementation updates user
        return updated_user
```

## Configuration

### Kafka Configuration

```python
kafka_config = KafkaConfig(
    bootstrap_servers=["kafka1:9092", "kafka2:9092"],
    security_protocol="SASL_SSL",
    sasl_mechanism="PLAIN",
    sasl_plain_username="username",
    sasl_plain_password="password",
    consumer_group_id="my-service-group",
    auto_offset_reset="latest"
)
```

### Outbox Configuration

```python
outbox_config = OutboxConfig(
    database_url="postgresql://user:pass@localhost/db",
    batch_size=50,
    poll_interval=timedelta(seconds=10),
    max_retries=5,
    retry_delay=timedelta(seconds=60),
    enable_dead_letter_queue=True
)
```

## Event Subscription

```python
from marty_msf.framework.events import EventHandler

class UserEventHandler(EventHandler):
    async def handle(self, event: BaseEvent) -> None:
        if event.event_type == "user.created":
            # Handle user creation
            print(f"User created: {event.data['user_id']}")

# Subscribe to events
handler = UserEventHandler()
await event_bus.subscribe("user.created", handler)
```

## Error Handling

The Enhanced Event Bus provides built-in error handling:

- **Dead Letter Queue**: Failed events are moved to DLQ for manual inspection
- **Circuit Breaker**: Automatic failure detection and recovery
- **Retry Logic**: Configurable retry attempts with exponential backoff
- **Monitoring**: Comprehensive metrics and logging

```python
# Configure error handling
event_bus = EnhancedEventBus(
    kafka_config=kafka_config,
    outbox_config=outbox_config,
    max_retries=3,
    enable_dlq=True,
    dlq_topic_suffix=".failed"
)
```

## Best Practices

1. **Use Transactional Outbox**: For critical business events that must be published
2. **Set Correlation IDs**: Enable distributed tracing across services
3. **Include Rich Metadata**: Add context for debugging and monitoring
4. **Use Event Priorities**: Ensure critical events are processed first
5. **Handle Dead Letter Queue**: Monitor and process failed events
6. **Use Structured Data**: Keep event data JSON-serializable
7. **Version Events**: Include version information for schema evolution

## Testing

```python
import pytest

@pytest.fixture
async def event_bus():
    # In-memory configuration for testing
    kafka_config = KafkaConfig(bootstrap_servers=["localhost:9092"])
    bus = EnhancedEventBus(kafka_config)
    await bus.start()
    yield bus
    await bus.stop()

async def test_event_publishing(event_bus):
    event = BaseEvent(
        event_type="test.event",
        data={"test": True},
        metadata=EventMetadata(
            event_id=str(uuid.uuid4()),
            event_type="test.event",
            timestamp=datetime.now(timezone.utc)
        )
    )

    # This should not raise an exception
    await event_bus.publish(event)
```

## Migration from Old Event Systems

The Enhanced Event Bus replaces all previous event publishing systems:

- **EventPublisher** → Use `EnhancedEventBus.publish()`
- **OutboxRepository** → Use `EnhancedEventBus.publish_transactional()`
- **Event Streaming Core** → Use `EnhancedEventBus` with subscriptions
- **Domain Events** → Use `publish_domain_aggregate_event()`

The Enhanced Event Bus provides a single, unified interface that supports all previous patterns while adding new capabilities for enterprise scenarios.

---

This unified approach eliminates architectural confusion while providing enterprise-grade features for production deployments.
