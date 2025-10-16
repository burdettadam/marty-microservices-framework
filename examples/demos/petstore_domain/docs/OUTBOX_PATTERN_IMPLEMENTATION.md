# Outbox Pattern Implementation in Petstore Demo

This document describes the transactional outbox pattern implementation added to the Petstore Domain plugin, demonstrating enterprise-grade data consistency patterns in the Marty Microservices Framework.

## Overview

The transactional outbox pattern ensures reliable event publishing by storing events in the same database transaction as business data, eliminating the dual-write problem and providing ACID guarantees for both business operations and event publishing.

## Implementation Details

### Core Components

1. **OutboxEvent Model** (`app/services/outbox_event_service.py`)
   - Database table for storing events awaiting publication
   - Includes retry logic, correlation IDs, and error tracking

2. **PetstoreOutboxEventService**
   - Service managing the entire outbox lifecycle
   - Background processing for event publication
   - Integration with Kafka message brokers

3. **Enhanced API Routes** (`app/api/outbox_routes.py`)
   - Demonstrates outbox pattern in real business operations
   - Endpoints for pets, orders, and user management

### Database Schema

```sql
CREATE TABLE outbox_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_id VARCHAR(255) NOT NULL,
    aggregate_type VARCHAR(100) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    event_data TEXT NOT NULL,
    correlation_id VARCHAR(255),
    topic VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    retry_count INTEGER DEFAULT 0,
    is_processed BOOLEAN DEFAULT FALSE,
    error_message TEXT
);

CREATE INDEX idx_outbox_events_aggregate_id ON outbox_events(aggregate_id);
CREATE INDEX idx_outbox_events_created_at ON outbox_events(created_at);
CREATE INDEX idx_outbox_events_is_processed ON outbox_events(is_processed);
```

## API Endpoints

### Core Outbox Pattern Endpoints

#### Create Pet with Outbox
```http
POST /api/v1/petstore-outbox/pets
Content-Type: application/json

{
    "name": "Buddy",
    "species": "dog",
    "breed": "Golden Retriever",
    "age": 3,
    "price": 1200.00,
    "category": "friendly",
    "description": "A friendly and energetic dog"
}
```

#### Create Order with Outbox
```http
POST /api/v1/petstore-outbox/orders
Content-Type: application/json

{
    "customer_id": "customer_123",
    "pet_id": "pet_456",
    "quantity": 1,
    "special_instructions": "Please handle with care"
}
```

#### Register User with Outbox
```http
POST /api/v1/petstore-outbox/users/user_789/register
Content-Type: application/json

{
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+1234567890"
}
```

### Monitoring and Management

#### Get Outbox Metrics
```http
GET /api/v1/petstore-outbox/metrics
```

Response:
```json
{
    "outbox_metrics": {
        "pending_events": 5,
        "failed_events": 0,
        "processed_today": 245,
        "running": true,
        "kafka_connected": true
    },
    "service_status": "running",
    "kafka_status": "connected",
    "timestamp": "2025-10-15T10:30:00Z"
}
```

#### Health Check
```http
GET /api/v1/petstore-outbox/health
```

## Configuration

### Environment Variables

```bash
# Database Configuration
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/petstore

# Kafka Configuration
KAFKA_BROKERS=localhost:9092
KAFKA_TOPIC_PREFIX=petstore

# Outbox Configuration
OUTBOX_BATCH_SIZE=100
OUTBOX_POLLING_INTERVAL=1.0
OUTBOX_MAX_RETRIES=5
```

### Configuration in Code

```python
from app.services.outbox_event_service import PetstoreOutboxEventService

# Initialize with custom configuration
outbox_service = PetstoreOutboxEventService(
    database_url="postgresql+asyncpg://user:pass@host:5432/db"
)

# Start the service
await outbox_service.start()
```

## Usage Examples

### Basic Usage - Pet Creation

```python
async def create_pet_example():
    async with outbox_event_service.get_session() as session:
        # Save pet data to database
        pet = Pet(
            id="pet_123",
            name="Max",
            species="dog",
            price=800.00
        )
        session.add(pet)

        # Enqueue event in same transaction
        event_id = await outbox_event_service.publish_pet_event(
            session=session,
            pet_id="pet_123",
            event_type="created",
            pet_data={
                "name": "Max",
                "species": "dog",
                "price": 800.00
            },
            correlation_id="corr_456"
        )

        # Transaction commits automatically
        # Event will be published by background processor
```

### Order Processing Workflow

```python
async def process_order_example():
    async with outbox_event_service.get_session() as session:
        # Create order
        order = Order(
            id="order_789",
            customer_id="customer_123",
            pet_id="pet_456",
            status="pending"
        )
        session.add(order)

        # Publish order created event
        await outbox_event_service.publish_order_event(
            session=session,
            order_id="order_789",
            event_type="created",
            order_data={
                "customer_id": "customer_123",
                "pet_id": "pet_456",
                "status": "pending"
            }
        )

        # Update order status
        order.status = "confirmed"

        # Publish order confirmed event
        await outbox_event_service.publish_order_event(
            session=session,
            order_id="order_789",
            event_type="confirmed",
            order_data={
                "status": "confirmed",
                "confirmed_at": datetime.utcnow().isoformat()
            }
        )
```

## Monitoring and Observability

### Key Metrics

- **Pending Events**: Number of events waiting to be published
- **Failed Events**: Events that exceeded maximum retry attempts
- **Processing Rate**: Events processed per second
- **Retry Rate**: Percentage of events requiring retries
- **Kafka Connection Status**: Health of message broker connection

### Logging

The implementation provides structured logging for:
- Event enqueueing within transactions
- Background processing status
- Retry attempts and failures
- Kafka publishing success/failure

### Grafana Dashboard

Key metrics to monitor:
```promql
# Pending events gauge
petstore_outbox_pending_events

# Processing rate
rate(petstore_outbox_processed_total[5m])

# Error rate
rate(petstore_outbox_errors_total[5m])

# Processing latency
petstore_outbox_processing_duration_seconds
```

## Error Handling

### Automatic Retry

- Failed events are automatically retried with exponential backoff
- Maximum retry attempts configurable (default: 5)
- Events exceeding max retries moved to failed state for manual investigation

### Dead Letter Queue

- Events that cannot be processed are preserved for analysis
- Error messages captured for debugging
- Manual reprocessing capabilities for recovered systems

### Circuit Breaker

- Kafka connection failures trigger circuit breaker
- Prevents cascade failures during broker outages
- Automatic recovery when broker becomes available

## Performance Considerations

### Batch Processing

- Events processed in configurable batches (default: 100)
- Reduces database queries and improves throughput
- Batch timeout prevents indefinite waiting

### Database Optimization

- Indexes on aggregate_id, created_at, and is_processed columns
- Connection pooling for database efficiency
- Prepared statements for better performance

### Kafka Optimization

- Producer configured with idempotence enabled
- Compression and batching for network efficiency
- Persistent connections with connection pooling

## Testing

### Unit Tests

```python
async def test_outbox_event_creation():
    async with outbox_service.get_session() as session:
        event_id = await outbox_service.publish_pet_event(
            session=session,
            pet_id="test_pet",
            event_type="created",
            pet_data={"name": "Test Pet"},
            correlation_id="test_correlation"
        )

        assert event_id is not None
        # Verify event was saved in database
```

### Integration Tests

```python
async def test_end_to_end_processing():
    # Create pet with outbox event
    response = await client.post("/api/v1/petstore-outbox/pets", json={
        "name": "Integration Test Pet",
        "species": "cat",
        "price": 500.00
    })

    assert response.status_code == 200

    # Wait for background processing
    await asyncio.sleep(2)

    # Verify event was published to Kafka
    # (requires Kafka test container)
```

## Best Practices

### Transaction Management

1. Always use the outbox service's session context manager
2. Keep transactions short to avoid lock contention
3. Handle transaction failures gracefully

### Event Design

1. Include all necessary data in event payload
2. Use correlation IDs for request tracing
3. Design events for forward compatibility

### Monitoring

1. Set up alerts for failed events
2. Monitor processing lag regularly
3. Track Kafka connection health

### Scaling

1. Increase batch size for higher throughput
2. Run multiple outbox processors for load distribution
3. Partition Kafka topics by aggregate ID

## Troubleshooting

### Common Issues

1. **Events not being processed**
   - Check Kafka broker connectivity
   - Verify database connection
   - Check for failed transactions

2. **High retry rates**
   - Investigate Kafka broker performance
   - Check network connectivity
   - Verify topic configuration

3. **Processing lag**
   - Increase batch size
   - Scale outbox processors
   - Optimize database queries

### Debugging Tools

```bash
# Check outbox table directly
SELECT * FROM outbox_events WHERE is_processed = false ORDER BY created_at DESC LIMIT 10;

# Monitor failed events
SELECT * FROM outbox_events WHERE retry_count >= 5 AND is_processed = false;

# Check processing metrics
curl http://localhost:8080/api/v1/petstore-outbox/metrics
```

## Conclusion

The outbox pattern implementation in the Petstore demo provides a robust foundation for reliable event publishing in distributed systems. It demonstrates enterprise-grade data consistency patterns while maintaining simplicity and observability.

For more information on the complete data consistency patterns implementation, see the [Data Consistency Patterns Documentation](../../../docs/data-consistency-patterns.md).
