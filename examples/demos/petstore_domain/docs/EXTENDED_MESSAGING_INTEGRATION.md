# Petstore Domain Extended Messaging Integration

This document describes how the petstore domain plugin integrates with the extended messaging system to provide enhanced communication patterns and distributed transaction capabilities.

## Overview

The petstore domain now supports extended messaging capabilities alongside the existing Kafka integration, providing:

- **Unified Event Bus**: Single API for all messaging patterns
- **Multiple Backend Support**: NATS, AWS SNS, Kafka, RabbitMQ, Redis
- **Enhanced Saga Orchestration**: Distributed transaction management
- **Pattern-Specific Optimizations**: Optimized backends for different messaging patterns

## Architecture Integration

```
┌─────────────────────────────────────────────────────────────────┐
│                    Petstore Domain Service                     │
├─────────────────────────────────────────────────────────────────┤
│  Enhanced Petstore Service │ Extended Messaging Service        │
├─────────────────────────────────────────────────────────────────┤
│                    Unified Event Bus                           │
├─────────────────────────────────────────────────────────────────┤
│  NATS Backend  │ AWS SNS Backend │ Kafka │ RabbitMQ │ Redis    │
└─────────────────────────────────────────────────────────────────┘
```

## New Components

### 1. Petstore Extended Messaging Service

**File**: `app/services/petstore_extended_messaging_service.py`

Provides petstore-specific messaging functionality:

- **Event Types**: `PetstoreEventType` enum with domain-specific events
- **Messaging Patterns**: `PetstoreMessagingPattern` enum for pattern classification
- **Domain Operations**: High-level methods for order processing, inventory management
- **Saga Integration**: Enhanced saga orchestration for distributed transactions

Key Methods:
- `publish_inventory_event()`: Broadcast inventory changes
- `publish_order_event()`: Stream order events for analytics
- `send_payment_command()`: Direct payment processing
- `query_inventory_status()`: Real-time inventory queries
- `start_order_processing_saga()`: Distributed order workflow

### 2. Enhanced Petstore Service Integration

**File**: `app/services/enhanced_petstore_service.py` (modified)

The existing enhanced petstore service now integrates extended messaging:

- **Service Initialization**: Automatically configures extended messaging
- **Order Processing**: Uses extended messaging for order workflow
- **Inventory Management**: Publishes inventory events via extended messaging
- **Customer Notifications**: Sends notifications through unified event bus

New Methods:
- `browse_pets_with_extended_messaging()`: Pet browsing with messaging integration
- Enhanced `_create_order_direct()`: Order creation with messaging patterns

## Messaging Patterns by Use Case

### 1. Inventory Management (Pub/Sub Pattern)

**Backend**: NATS
**Use Case**: Broadcast inventory changes to multiple services

```python
# Publish inventory update
await extended_messaging_service.publish_inventory_event(
    PetstoreEventType.PET_UPDATED,
    {
        "pet_id": "golden-retriever-001",
        "available": False,
        "reserved_for_order": "ORD-123"
    }
)
```

**Subscribers**: Warehouse service, accounting service, CRM system

### 2. Order Analytics (Streaming Pattern)

**Backend**: Kafka
**Use Case**: High-volume order events for analytics and reporting

```python
# Stream order events
await extended_messaging_service.publish_order_event(
    PetstoreEventType.ORDER_CREATED,
    {
        "order_id": "ORD-123",
        "customer_id": "CUST-456",
        "pet_id": "golden-retriever-001",
        "amount": 1200.00
    }
)
```

**Consumers**: Analytics service, reporting service, business intelligence

### 3. Payment Processing (Point-to-Point Pattern)

**Backend**: NATS
**Use Case**: Direct payment processing commands

```python
# Send payment command
await extended_messaging_service.send_payment_command({
    "order_id": "ORD-123",
    "amount": 1200.00,
    "payment_method": "credit_card",
    "customer_id": "CUST-456"
})
```

**Target**: Payment service only

### 4. Inventory Queries (Request/Response Pattern)

**Backend**: NATS
**Use Case**: Real-time inventory status checks

```python
# Query inventory status
inventory_status = await extended_messaging_service.query_inventory_status(
    "golden-retriever-001"
)
```

**Response**: Immediate inventory availability status

### 5. Customer Notifications (Pub/Sub Pattern)

**Backend**: NATS
**Use Case**: Multi-channel customer notifications

```python
# Send customer notification
await extended_messaging_service.notify_customer(
    "CUST-456",
    {
        "type": "order_confirmation",
        "message": "Your order has been confirmed",
        "channels": ["email", "sms", "push"]
    }
)
```

**Subscribers**: Email service, SMS service, push notification service

## Enhanced Saga Orchestration

The petstore domain now supports distributed saga orchestration for complex order processing workflows.

### Order Processing Saga Flow

1. **Validate Inventory** → Reserve pet
   - **Compensation**: Release pet reservation

2. **Process Payment** → Charge customer
   - **Compensation**: Refund payment

3. **Arrange Shipping** → Schedule delivery
   - **Compensation**: Cancel shipping

4. **Update Inventory** → Mark pet as sold
   - **Compensation**: Restore pet availability

5. **Send Confirmation** → Notify customer
   - **Compensation**: Send cancellation notice

### Saga Usage Example

```python
# Start order processing saga
saga_id = await extended_messaging_service.start_order_processing_saga({
    "order_id": "ORD-123",
    "customer_id": "CUST-456",
    "pet_id": "golden-retriever-001",
    "total_amount": 1200.00,
    "shipping_address": "123 Main St, City, State"
})

# Check saga status
status = await extended_messaging_service.get_saga_status(saga_id)
```

## Configuration

### Extended Messaging Configuration

**File**: `config/enhanced_config.yaml`

```yaml
extended_messaging:
  enabled: true

  # NATS Configuration
  nats:
    enabled: true
    servers: ["nats://nats.messaging.svc.cluster.local:4222"]
    jetstream_enabled: true

  # AWS SNS Configuration
  aws_sns:
    enabled: false  # Disabled by default for local dev
    region_name: "us-east-1"
    fifo_topics: true

  # Backend Selection Strategy
  backend_selection:
    default_backend: "nats"
    pattern_preferences:
      pub_sub: "nats"
      point_to_point: "nats"
      request_response: "nats"
      streaming: "kafka"
```

### Pattern-Specific Configuration

```yaml
patterns:
  inventory_events:
    pattern: "pub_sub"
    backend: "nats"
    retention_days: 7

  order_events:
    pattern: "streaming"
    backend: "kafka"
    retention_days: 30

  customer_notifications:
    pattern: "pub_sub"
    backend: "nats"
    retention_days: 3
```

## Deployment Considerations

### Local Development

```yaml
extended_messaging:
  nats:
    servers: ["nats://localhost:4222"]
  aws_sns:
    enabled: false
```

### Production Environment

```yaml
extended_messaging:
  nats:
    servers:
      - "nats://nats-1.messaging.svc.cluster.local:4222"
      - "nats://nats-2.messaging.svc.cluster.local:4222"
      - "nats://nats-3.messaging.svc.cluster.local:4222"
  aws_sns:
    enabled: true
    region_name: "us-east-1"
    fifo_topics: true
```

## Migration Strategy

### Phase 1: Parallel Operation
- Extended messaging runs alongside existing Kafka
- Gradual migration of messaging patterns
- Feature flags control which system to use

### Phase 2: Pattern-Specific Migration
- Move inventory events to NATS (pub/sub)
- Keep order analytics on Kafka (streaming)
- Migrate notifications to NATS (pub/sub)

### Phase 3: Full Integration
- All new features use unified event bus
- Legacy Kafka integration remains for analytics
- Extended messaging becomes primary system

## Monitoring and Observability

### Metrics

- **Message throughput**: Messages per second by pattern/backend
- **Saga completion rate**: Successful vs failed sagas
- **Backend health**: Connection status and performance
- **Pattern distribution**: Usage by messaging pattern

### Logging

- **Message tracing**: Correlation IDs across services
- **Saga tracking**: Step-by-step saga execution
- **Error handling**: Backend failures and fallbacks
- **Performance metrics**: Message latency and processing time

## Testing

### Unit Tests

Test individual messaging components:
- Extended messaging service methods
- Pattern selection logic
- Configuration parsing
- Error handling

### Integration Tests

Test cross-service communication:
- End-to-end order processing
- Saga orchestration
- Backend failover
- Message delivery guarantees

### Load Tests

Test performance characteristics:
- High-volume order processing
- Concurrent saga execution
- Backend scalability
- Message throughput limits

## Examples

### Running the Examples

```bash
# From the petstore_domain directory
python petstore_extended_messaging_examples.py
```

The examples demonstrate:
- Order processing with extended messaging
- Pet browsing with analytics events
- Saga orchestration
- Configuration examples
- Deployment scenarios

### Expected Output

```
🐕 Petstore Extended Messaging Demonstration
============================================================
✅ Petstore service initialized with extended messaging

📋 Browsing pets with extended messaging...
   Found 2 dogs under $1500
   - Buddy (Golden Retriever): $1200.0
   - Max (Labrador): $1000.0

🛒 Creating order with extended messaging saga...
   ✅ Order created: ORD-20251015-001
   📊 Saga status: in_progress

📈 Checking order status...
   Order ORD-20251015-001: payment_processing

🔄 Extended Messaging Patterns Used:
   📢 Pub/Sub: Inventory updates and customer notifications
   🎯 Point-to-Point: Payment processing commands
   🔄 Request/Response: Inventory status queries
   📊 Streaming: Order analytics and events
```

## Future Enhancements

### Planned Features

1. **Circuit Breaker Integration**: Automatic fallback to alternative backends
2. **Message Transformation**: Format conversion between backends
3. **Dead Letter Queue**: Enhanced error handling and message recovery
4. **Schema Registry**: Message schema validation and evolution
5. **Advanced Routing**: Content-based message routing

### Performance Optimizations

1. **Connection Pooling**: Reuse connections across requests
2. **Message Batching**: Batch multiple messages for efficiency
3. **Compression**: Compress large messages
4. **Caching**: Cache frequently accessed data
5. **Load Balancing**: Distribute load across backend instances

## Conclusion

The petstore domain's integration with extended messaging provides a robust foundation for scalable, distributed e-commerce operations. The unified event bus approach simplifies development while providing the flexibility to choose optimal backends for different messaging patterns.

The implementation demonstrates real-world usage of advanced messaging patterns including:
- Event-driven architecture
- Saga pattern for distributed transactions
- Cross-service communication
- Pattern-specific backend optimization

This integration serves as a comprehensive example of how to leverage the extended messaging system in domain-specific applications while maintaining backward compatibility and enabling gradual migration strategies.
