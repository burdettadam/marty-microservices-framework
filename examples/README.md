# Event Publishing Examples

This directory contains examples demonstrating how to use the unified event publishing system in the Marty Microservices Framework.

## Files

### `simple_event_example.py`
A basic example showing:
- How to set up and use the EventPublisher
- Publishing different types of events (audit, notification, domain, custom)
- Using decorators for automatic event publishing

**Run with:**
```bash
cd marty-microservices-framework
python examples/simple_event_example.py
```

### `event_publishing_migration.py`
Comprehensive migration examples showing:
- Before/after code for migrating from custom event publishing
- Examples from real Marty services (DTC Engine, CMC Engine, Base Service)
- Different migration approaches (decorators vs manual)
- Complete user service example with authentication events

**Use as reference for:**
- Migrating existing services to the unified event system
- Understanding different event publishing patterns
- Seeing real-world usage examples

## Prerequisites

### 1. Install Dependencies
```bash
# Install the framework in development mode
pip install -e .

# Or install specific dependencies
pip install aiokafka pydantic sqlalchemy
```

### 2. Start Kafka (Optional)
For examples that actually publish to Kafka:

```bash
# Start Kafka infrastructure
cd observability/kafka
docker-compose -f docker-compose.kafka.yml up -d

# Verify Kafka is running
docker-compose -f docker-compose.kafka.yml ps
```

### 3. Set Environment Variables
```bash
export KAFKA_BROKERS=localhost:9092
export SERVICE_NAME=example-service
export EVENT_TOPIC_PREFIX=marty
```

## Running Examples

### Simple Example (No Kafka Required)
```bash
python examples/simple_event_example.py
```

### With Real Kafka
```bash
# Start Kafka first
docker-compose -f observability/kafka/docker-compose.kafka.yml up -d

# Run example
python examples/simple_event_example.py

# Check Kafka UI (optional)
open http://localhost:8080
```

### Testing Migration Patterns
```bash
python examples/event_publishing_migration.py
```

## Example Output

```
🎯 Unified Event Publishing Example
====================================
🚀 Starting Event Publishing Example
✅ Event publisher started

📋 Publishing audit event...
✅ Audit event published: 123e4567-e89b-12d3-a456-426614174000

📧 Publishing notification event...
✅ Notification event published: 456e7890-e89b-12d3-a456-426614174001

🏗️ Publishing domain event...
✅ Domain event published: 789e0123-e89b-12d3-a456-426614174002

🎯 Publishing custom event...
✅ Custom event published: 012e3456-e89b-12d3-a456-426614174003

🎉 All events published successfully!

ℹ️  Check your Kafka topics:
   - marty.audit.events
   - marty.notification.events
   - marty.example-service.example.example_created
   - marty.example.custom.events
```

## Migration Checklist

When migrating a service to use unified event publishing:

### 1. ✅ Replace Custom Event Publishing
- [ ] Remove custom `_publish_event` methods
- [ ] Remove direct Kafka producer usage
- [ ] Remove custom outbox implementations

### 2. ✅ Add Framework Dependencies
```python
from framework.events import (
    get_event_publisher,
    EventPublisher,
    AuditEventType,
    NotificationEventType,
    audit_event,
    domain_event,
    publish_on_success,
    publish_on_error
)
```

### 3. ✅ Choose Migration Approach

**Option A: Decorators (Recommended)**
```python
@audit_event(
    event_type=AuditEventType.DATA_CREATED,
    action="create_resource",
    resource_type="my_resource",
    resource_id_field="resource_id"
)
async def create_resource(self, resource_id: str, data: dict):
    # Business logic
    pass
```

**Option B: Manual Publishing**
```python
async def create_resource(self, resource_id: str, data: dict):
    # Business logic

    # Manual event publishing
    publisher = get_event_publisher()
    await publisher.publish_audit_event(
        event_type=AuditEventType.DATA_CREATED,
        action="create_resource",
        resource_type="my_resource",
        resource_id=resource_id
    )
```

### 4. ✅ Update Configuration
```python
# Environment-based (recommended)
publisher = get_event_publisher()

# Or explicit configuration
config = EventConfig(
    service_name="my-service",
    kafka_brokers=["localhost:9092"],
    use_outbox_pattern=True
)
publisher = EventPublisher(config)
```

### 5. ✅ Update Tests
```python
@pytest.fixture
def mock_event_publisher():
    return AsyncMock(spec=EventPublisher)

async def test_creates_resource(mock_event_publisher):
    service = MyService(event_publisher=mock_event_publisher)
    await service.create_resource("res-123", {"key": "value"})

    mock_event_publisher.publish_audit_event.assert_called_once()
```

## Event Types Reference

### Audit Events
Use for compliance, security monitoring, and debugging:
```python
AuditEventType.DATA_CREATED      # Resource creation
AuditEventType.DATA_UPDATED      # Resource modification
AuditEventType.DATA_DELETED      # Resource deletion
AuditEventType.USER_LOGIN        # Authentication
AuditEventType.PERMISSION_DENIED # Authorization failures
AuditEventType.CERTIFICATE_ISSUED # Certificate operations
```

### Notification Events
Use for user communications and alerts:
```python
NotificationEventType.USER_WELCOME          # Welcome messages
NotificationEventType.CERTIFICATE_EXPIRING  # Certificate alerts
NotificationEventType.SYSTEM_ALERT          # System notifications
NotificationEventType.POLICY_UPDATED        # Policy changes
```

### Domain Events
Use for business logic and inter-service communication:
```python
# Custom domain events using aggregate and event type
await publisher.publish_domain_event(
    aggregate_type="user",
    aggregate_id="user-123",
    event_type="user_profile_updated",
    event_data={"fields": ["email", "name"]}
)
```

## Troubleshooting

### Import Errors
```bash
# Make sure you're in the framework directory
cd marty-microservices-framework

# Install in development mode
pip install -e .
```

### Kafka Connection Issues
```bash
# Check if Kafka is running
docker-compose -f observability/kafka/docker-compose.kafka.yml ps

# Check Kafka logs
docker-compose -f observability/kafka/docker-compose.kafka.yml logs kafka

# Restart Kafka
docker-compose -f observability/kafka/docker-compose.kafka.yml restart
```

### Event Not Appearing
1. Check topic names match expected patterns
2. Verify Kafka UI at http://localhost:8080
3. Check service logs for event publishing errors
4. Ensure outbox pattern is properly configured for transactional events

## Next Steps

1. **Read the full guide**: [docs/event-publishing-guide.md](../docs/event-publishing-guide.md)
2. **Review migration examples**: [event_publishing_migration.py](./event_publishing_migration.py)
3. **Start migrating your service**: Use the checklist above
4. **Set up monitoring**: Configure event metrics and observability

For questions or issues, refer to the main framework documentation.
