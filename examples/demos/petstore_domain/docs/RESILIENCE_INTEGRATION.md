# Petstore Resilience Framework Integration

This document describes the integration of the enhanced resilience framework with bulkheads, timeouts, and external dependency management into the petstore domain plugin.

## 🏗️ Architecture Overview

The petstore domain now demonstrates a complete enterprise-grade resilience framework with:

### Core Resilience Components

1. **Bulkhead Isolation Patterns**
   - **Semaphore Bulkheads**: For lightweight resource isolation (database, cache, message queue)
   - **Thread Pool Bulkheads**: For CPU-intensive or blocking operations (external APIs)

2. **Timeout Management**
   - Dependency-specific timeout configurations
   - Automatic timeout handling per external service type

3. **External Dependency Management**
   - Centralized registration and configuration
   - Decorator-based usage patterns
   - Automatic circuit breaker integration

4. **Circuit Breaker Integration**
   - Configurable failure thresholds
   - Automatic recovery and health monitoring

## 📁 File Structure

```
plugins/petstore_domain/
├── app/services/
│   ├── enhanced_petstore_service.py      # Main service with resilience integration
│   └── petstore_resilience_service.py    # Dedicated resilience management service
├── config/
│   └── enhanced_config.yaml              # Resilience configuration
├── demo_resilience.py                    # Comprehensive resilience demo
├── dev/run_resilience_demo.sh           # Demo runner script
└── RESILIENCE_INTEGRATION.md            # This documentation
```

## 🔧 Configuration

The resilience framework is configured through `config/enhanced_config.yaml`:

### Bulkhead Configuration

```yaml
resilience:
  bulkheads:
    database:
      type: "semaphore"
      max_concurrent: 10
    external_api:
      type: "thread_pool"
      max_workers: 5
    cache:
      type: "semaphore"
      max_concurrent: 100
    message_queue:
      type: "semaphore"
      max_concurrent: 20
    file_system:
      type: "semaphore"
      max_concurrent: 8
```

### External Dependencies

```yaml
resilience:
  external_dependencies:
    petstore_database:
      max_concurrent: 10
      timeout_seconds: 10.0
      enable_circuit_breaker: true
    payment_gateway:
      max_concurrent: 5
      timeout_seconds: 25.0
      enable_circuit_breaker: true
    redis_cache:
      max_concurrent: 100
      timeout_seconds: 1.5
      enable_circuit_breaker: false
    kafka_events:
      max_concurrent: 20
      timeout_seconds: 8.0
      enable_circuit_breaker: true
    ml_pet_advisor:
      max_concurrent: 6
      timeout_seconds: 30.0
      enable_circuit_breaker: true
```

## 🚀 Usage Examples

### Basic Service Initialization

```python
from app.services.enhanced_petstore_service import EnhancedPetstoreDomainService

# Initialize with resilience configuration
config = load_config("config/enhanced_config.yaml")
service = EnhancedPetstoreDomainService(config=config)
```

### Resilient Operations

```python
# Get pet with caching and ML recommendations
pet_result = await service.get_pet_with_cache_and_recommendations(
    pet_id="pet_123",
    customer_id="customer_456"
)

# Create order with full resilience patterns
order_result = await service.create_order_with_resilience(
    customer_id="customer_789",
    pet_id="pet_001",
    payment_data={"amount": 299.99, "payment_method": "credit_card"}
)

# Check resilience health
health = await service.get_resilience_health()
```

### Direct Resilient Operations

```python
from app.services.petstore_resilience_service import PetstoreResilientOperations

operations = PetstoreResilientOperations(resilience_manager)

# Database operations with bulkhead isolation
pet_data = await operations.get_pet_from_database("pet_123")

# External API calls with timeout and circuit breaker
payment_result = await operations.process_payment_external({
    "customer_id": "customer_456",
    "amount": 199.99
})

# Cache operations with fast timeout
catalog = await operations.get_pet_catalog_from_cache("dogs")
```

## 🧪 Demo and Testing

### Running the Demo

```bash
chmod +x dev/run_resilience_demo.sh

# Run the demo
./dev/run_resilience_demo.sh
```

Or run directly with Python:

```bash
cd plugins/petstore_domain
python3 demo_resilience.py
```

### Demo Features

The resilience demo demonstrates:

1. **Health Monitoring**: Real-time resilience health status
2. **Pet Operations**: Cache-first retrieval with ML recommendations
3. **Order Creation**: Full business transaction with multiple dependencies
4. **Bulkhead Isolation**: Concurrent load testing showing resource isolation
5. **Scenario Testing**: Error handling, timeout management, circuit breaker behavior

### Sample Demo Output

```
🚀 PETSTORE RESILIENCE FRAMEWORK DEMO
============================================================

RESILIENCE HEALTH CHECK
============================================================
{
  "service": "petstore_domain",
  "resilience_framework": "enabled",
  "overall_status": "healthy",
  "dependencies": {
    "petstore_database": {
      "status": "healthy",
      "bulkhead_utilization": "2/10",
      "success_rate": "100.00%",
      "circuit_breaker_state": "closed"
    },
    "payment_gateway": {
      "status": "healthy",
      "bulkhead_utilization": "1/5",
      "success_rate": "95.50%",
      "circuit_breaker_state": "closed"
    }
  }
}

BULKHEAD ISOLATION DEMO
============================================================
🚧 Testing bulkhead isolation with concurrent requests...
📊 Executing 15 database, 8 API, and 50 cache operations...

📈 Bulkhead Isolation Results:
   Database: 10/15 successful (5 rejected by bulkhead)
   API: 5/8 successful (3 rejected by bulkhead)
   Cache: 50/50 successful (within capacity)
   Total execution time: 2.15 seconds
```

## 🏛️ Architecture Components

### PetstoreResilienceManager

The central resilience management component that:
- Registers external dependencies with appropriate bulkheads
- Configures timeouts and circuit breakers
- Provides health monitoring and statistics

### PetstoreResilientOperations

Provides resilient operation methods with decorators:
- `@database_call`: Database operations with semaphore bulkhead
- `@api_call`: External API calls with thread-pool bulkhead
- `@cache_call`: Cache operations with fast timeout
- `@resilience_pattern`: Custom resilience configuration

### External Dependencies

The framework manages five types of external dependencies:

1. **Database** (`petstore_database`)
   - Semaphore bulkhead (10 concurrent)
   - 10-second timeout
   - Circuit breaker enabled

2. **Payment Gateway** (`payment_gateway`)
   - Thread-pool bulkhead (5 workers)
   - 25-second timeout
   - Circuit breaker enabled

3. **Cache** (`redis_cache`)
   - Semaphore bulkhead (100 concurrent)
   - 1.5-second timeout
   - Circuit breaker disabled (cache failures are non-critical)

4. **Message Queue** (`kafka_events`)
   - Semaphore bulkhead (20 concurrent)
   - 8-second timeout
   - Circuit breaker enabled

5. **ML Service** (`ml_pet_advisor`)
   - Thread-pool bulkhead (6 workers)
   - 30-second timeout
   - Circuit breaker enabled

## 📊 Monitoring and Observability

### Health Endpoint

The service provides comprehensive health information:

```python
health = await service.get_resilience_health()
```

Returns:
- Overall system health status
- Per-dependency health metrics
- Bulkhead utilization statistics
- Circuit breaker states
- Success/failure rates

### Metrics Available

- **Bulkhead Utilization**: Current load vs. capacity
- **Request Counts**: Total, successful, rejected requests
- **Success Rates**: Percentage of successful operations
- **Circuit Breaker States**: Open/closed/half-open status
- **Response Times**: Operation timing statistics

## 🔄 Business Transaction Flow

The `complete_pet_order_with_recommendations` method demonstrates a complex business transaction using multiple resilient dependencies:

1. **Pet Retrieval** (Database)
   - Semaphore bulkhead isolation
   - 10-second timeout
   - Circuit breaker protection

2. **Cache Check** (Redis)
   - Fast 1.5-second timeout
   - High concurrency (100)
   - Non-critical (no circuit breaker)

3. **ML Recommendations** (External API)
   - Thread-pool bulkhead
   - 30-second timeout
   - Degradation on failure

4. **Payment Processing** (External Gateway)
   - Thread-pool bulkhead
   - 25-second timeout
   - Critical path with circuit breaker

5. **Database Updates** (Database)
   - Inventory and order persistence
   - Same bulkhead as retrieval

6. **Event Publishing** (Message Queue)
   - Async event streaming
   - Fire-and-forget pattern
   - Circuit breaker for reliability

## 🛡️ Resilience Patterns Demonstrated

### Bulkhead Isolation
- **Resource Isolation**: Different dependency types use separate resource pools
- **Failure Containment**: Issues with one dependency don't affect others
- **Load Management**: Prevents resource exhaustion

### Timeout Management
- **Dependency-Specific**: Different timeouts for different service types
- **Automatic Handling**: Graceful timeout with appropriate responses
- **Circuit Breaker Integration**: Timeouts contribute to failure counting

### Circuit Breaker Protection
- **Failure Detection**: Automatic failure threshold monitoring
- **Service Protection**: Prevents cascading failures
- **Automatic Recovery**: Self-healing when services recover

### Graceful Degradation
- **Non-Critical Services**: ML recommendations can fail without blocking orders
- **Cache Fallback**: Cache misses don't prevent operations
- **Event Publishing**: Order completion isn't blocked by event failures

## 🚦 Error Handling Scenarios

The demo includes several error scenarios:

1. **Database Errors**: Simulated with special pet ID "error_pet"
2. **Payment Failures**: High amounts trigger payment gateway errors
3. **Bulkhead Rejection**: Excess concurrent requests are rejected
4. **Timeout Scenarios**: Long-running operations are terminated
5. **Circuit Breaker Trips**: Repeated failures open circuit breakers

## 🔧 Configuration Customization

### Environment-Specific Settings

Different environments can have different resilience settings:

```yaml
# Production
resilience:
  external_dependencies:
    payment_gateway:
      max_concurrent: 10    # Higher capacity
      timeout_seconds: 30.0 # Longer timeout

# Development
resilience:
  external_dependencies:
    payment_gateway:
      max_concurrent: 2     # Lower capacity
      timeout_seconds: 5.0  # Shorter timeout
```

### Tuning Guidelines

1. **Bulkhead Sizing**: Base on expected load and resource capacity
2. **Timeout Values**: Consider 95th percentile response times + buffer
3. **Circuit Breaker Thresholds**: Balance sensitivity vs. stability
4. **Thread Pool Sizing**: Match available CPU cores and I/O patterns

## 🔮 Future Enhancements

Potential improvements to the resilience integration:

1. **Metrics Export**: Prometheus/Grafana integration
2. **Dynamic Configuration**: Runtime bulkhead and timeout adjustment
3. **Advanced Circuit Breakers**: Sliding window failure detection
4. **Retry Policies**: Exponential backoff with jitter
5. **Rate Limiting**: Token bucket and sliding window rate limiters
6. **Adaptive Timeouts**: Machine learning-based timeout optimization

## 📚 Related Documentation

- [Main Resilience Framework Documentation](../../docs/architecture/resilience-framework.md)
- [Bulkhead Patterns Guide](../../docs/guides/bulkhead-patterns.md)
- [External Dependency Management](../../docs/guides/external-dependencies.md)
- [MMF Event Streaming](../../docs/guides/event-streaming.md)

## 🤝 Contributing

When extending the resilience integration:

1. Follow the existing patterns for decorator usage
2. Add appropriate bulkhead configurations for new dependencies
3. Include health monitoring for new operations
4. Update the demo to showcase new features
5. Document configuration options and tuning guidelines

---

*This resilience integration demonstrates enterprise-grade patterns for building fault-tolerant, scalable microservices with comprehensive observability and operational excellence.*
