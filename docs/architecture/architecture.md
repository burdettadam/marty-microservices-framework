# Marty Microservices Framework Architecture

This document provides a comprehensive overview of the Marty Microservices Framework architecture, design principles, and component interactions.

## 🏗️ High-Level Architecture

The Marty Microservices Framework follows a layered, plugin-based architecture designed for enterprise-grade microservices:

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   FastAPI   │  │    gRPC     │  │      Hybrid         │ │
│  │  Services   │  │  Services   │  │     Services        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────┐
│                   Framework Layer                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Auth/Authz  │  │  Database   │  │    Configuration    │ │
│  │ Middleware  │  │  Manager    │  │      Manager        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Observability│  │  Resilience │  │     Event Bus       │ │
│  │   System    │  │  Patterns   │  │    & Messaging      │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────┐
│                    Plugin Layer                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Plugin    │  │   Plugin    │  │      Plugin         │ │
│  │  Manager    │  │ Discovery   │  │    Lifecycle        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────┐
│                Infrastructure Layer                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Kubernetes  │  │ Service     │  │     Monitoring      │ │
│  │ Deployment  │  │   Mesh      │  │    & Logging        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 🧱 Core Components

### 1. Application Layer

#### Service Templates
- **FastAPI Services**: REST API microservices with automatic documentation
- **gRPC Services**: High-performance RPC services with protocol buffers
- **Hybrid Services**: Combined REST and gRPC endpoints in a single service

#### Key Features:
- Automatic dependency injection
- Built-in health checks and metrics endpoints
- Standardized error handling and logging
- Hot-reloadable configuration

### 2. Framework Layer

#### Authentication & Authorization (`src/framework/security/`)
- JWT token validation and generation
- Role-based access control (RBAC)
- Rate limiting and throttling
- Audit logging for security events

#### Database Management (`src/framework/database/`)
- Connection pooling and management
- Transaction handling with async support
- Repository pattern implementation
- Database migration utilities
- Multi-database support (PostgreSQL, MySQL, MongoDB)

#### Configuration Management (`src/framework/config/`)
- Environment-based configuration
- YAML/JSON configuration files
- Secret management integration
- Runtime configuration updates

#### Observability (`src/framework/observability/`)
- Distributed tracing with OpenTelemetry
- Prometheus metrics collection
- Structured logging with correlation IDs
- Performance monitoring and alerting

#### Resilience Patterns (`src/framework/resilience/`)

The framework provides enterprise-grade resilience patterns for building fault-tolerant microservices:

**Core Patterns:**
- **Circuit Breakers**: Automatic fault tolerance with configurable failure thresholds and recovery timeouts
- **Retry Mechanisms**: Intelligent retry with exponential backoff, jitter, and circuit breaker integration
- **Bulkhead Isolation**: Resource isolation using thread pools and semaphores to prevent cascade failures
- **Timeout Management**: Comprehensive timeout handling with dependency-specific configurations
- **Fallback Strategies**: Graceful degradation with cached responses, default values, and alternative flows

**External Dependency Management:**
- **Bulkhead Isolation per Dependency**: Separate resource pools for different external services (database, APIs, cache)
- **Configurable Timeout Strategies**: Dependency-specific timeouts (database: 10s, APIs: 15s, cache: 2s)
- **Circuit Breaker Integration**: Automatic circuit breaking based on failure rates and thresholds
- **Adaptive Configurations**: Environment-specific settings (development, testing, production)

**Implementation Features:**
- **Thread-Pool Bulkheads**: For CPU-intensive operations with configurable worker limits
- **Semaphore Bulkheads**: For I/O operations with high concurrency support
- **External Dependency Registration**: Simple API for registering and configuring dependencies
- **Comprehensive Metrics**: Real-time monitoring of bulkhead utilization, circuit breaker states, and timeout rates
- **Health Checks**: Integrated health monitoring with resilience pattern statistics

**Configuration Example:**
```yaml
resilience:
  bulkheads:
    database:
      max_concurrent: 10
      timeout_seconds: 10.0
      enable_circuit_breaker: true
    external_api:
      max_concurrent: 15
      timeout_seconds: 15.0
      circuit_breaker_failure_threshold: 3
```

**Usage Patterns:**
```python
# Register external dependencies
register_database_dependency("user_db", max_concurrent=10)
register_api_dependency("payment_gateway", max_concurrent=5)

# Use decorators for automatic resilience
@database_call(dependency_name="user_db", operation_name="get_user")
async def get_user(user_id: str) -> dict:
    # Database call automatically protected by bulkhead and timeout
    return await db.get_user(user_id)
```

#### Event-Driven Architecture (`src/framework/events/`)
- Event bus for inter-service communication
- Message queue integration (Kafka, RabbitMQ)
- Event sourcing capabilities
- CQRS pattern support

#### **Extended Messaging System (`src/framework/messaging/`)**

The framework provides a comprehensive, unified messaging system supporting multiple backends and messaging patterns for enterprise-grade microservices communication.

**Core Components:**

##### Unified Event Bus (`unified_event_bus.py`)
- **Single API for All Patterns**: Unified interface supporting pub/sub, request/response, stream processing, and point-to-point messaging
- **Backend Abstraction**: Automatic backend selection based on messaging pattern and requirements
- **Pattern-Specific Optimizations**: Each pattern uses the most appropriate backend automatically
- **Smart Backend Selection**: Uses PatternSelector for intelligent backend recommendation

##### Supported Backends
1. **NATS Backend** (`nats_backend.py`)
   - High-performance, low-latency messaging
   - JetStream support for stream processing
   - Request/response with built-in timeouts
   - Excellent for micro-service communication

2. **AWS SNS Backend** (`aws_sns_backend.py`)
   - Cloud-native pub/sub and broadcast messaging
   - FIFO topics with exactly-once delivery
   - Message filtering and attributes
   - Dead letter queue support

3. **RabbitMQ Backend** (Enhanced existing implementation)
   - Complex routing and exchange patterns
   - Message persistence and clustering
   - Priority queues and TTL support
   - Traditional enterprise messaging

4. **Kafka Backend** (Enhanced existing implementation)
   - High-throughput stream processing
   - Event replay capabilities
   - Partitioned topics for scalability
   - Real-time analytics pipelines

5. **Redis Backend** (Enhanced existing implementation)
   - Lightweight pub/sub for caching scenarios
   - Streams for simple event processing
   - In-memory performance

##### Messaging Patterns

**Publish/Subscribe Pattern:**
```python
# Publish domain events
await event_bus.publish_event(
    event_type="user_registered",
    data={"user_id": "123", "email": "user@example.com"}
)

# Subscribe to events
await event_bus.subscribe_to_events(
    event_types=["user_registered", "user_updated"],
    handler=handle_user_events
)
```

**Request/Response Pattern:**
```python
# Send query and get response
response = await event_bus.query(
    query_type="get_user_profile",
    data={"user_id": "123"},
    target_service="user_service"
)
```

**Stream Processing Pattern:**
```python
# Process event streams in batches
await event_bus.process_stream(
    stream_name="analytics_events",
    processor=process_analytics_batch,
    consumer_group="analytics_processor",
    batch_size=100
)
```

**Point-to-Point Pattern:**
```python
# Send commands to specific services
await event_bus.send_command(
    command_type="process_payment",
    data={"order_id": "123", "amount": 99.99},
    target_service="payment_service"
)
```

##### Enhanced Saga Integration (`saga_integration.py`)

**Distributed Saga Orchestration:**
- **Enhanced Saga Orchestrator**: Uses unified event bus for saga coordination
- **Multi-Backend Saga Support**: Saga events can use different backends for different steps
- **Compensation Logic**: Automatic compensation handling with event-driven rollback
- **Saga State Management**: Persistent saga state with event sourcing

**Example Saga Implementation:**
```python
class OrderProcessingSaga:
    def __init__(self):
        self.steps = [
            {"step_name": "validate_order", "service": "order_service"},
            {"step_name": "reserve_inventory", "service": "inventory_service"},
            {"step_name": "process_payment", "service": "payment_service"},
            {"step_name": "ship_order", "service": "shipping_service"}
        ]

# Create distributed saga manager
saga_manager = create_distributed_saga_manager(event_bus)
saga_manager.register_saga("order_processing", OrderProcessingSaga)

# Start saga
saga_id = await saga_manager.create_and_start_saga(
    "order_processing",
    {"order_id": "123", "customer_id": "456"}
)
```

##### Pattern Selection Guidelines

**Backend Selection Matrix:**

| Use Case | Scale | Recommended Backend | Pattern |
|----------|-------|-------------------|---------|
| Real-time notifications | High | NATS | Pub/Sub |
| Task queues | Medium | RabbitMQ | Point-to-Point |
| Analytics processing | High | Kafka | Stream Processing |
| Micro-service communication | Medium | NATS | Request/Response |
| Cloud-native pub/sub | Any | AWS SNS | Pub/Sub |
| Financial transactions | High | Kafka + NATS | Stream + Request/Response |

**When to Use Each Pattern:**

- **Pub/Sub**: Multiple services need to react to the same event (user registration, order updates)
- **Request/Response**: Immediate response required (authentication, payment authorization)
- **Stream Processing**: Continuous data flows with ordering (analytics, financial transactions)
- **Point-to-Point**: Task processing with guaranteed delivery (background jobs, email sending)

##### Configuration and Deployment

**Backend Configuration:**
```python
# Configure multiple backends
nats_config = NATSConfig(servers=["nats://localhost:4222"])
aws_config = AWSSNSConfig(region_name="us-east-1")

event_bus.register_backend(MessageBackendType.NATS, NATSBackend(nats_config))
event_bus.register_backend(MessageBackendType.AWS_SNS, AWSSNSBackend(aws_config))
```

**Infrastructure Requirements:**
- **NATS**: Lightweight, minimal infrastructure
- **AWS SNS**: Managed service, no infrastructure needed
- **RabbitMQ**: Cluster deployment with persistence
- **Kafka**: High-availability cluster with storage
- **Redis**: In-memory cluster for caching scenarios

**Deployment Strategy:**
- **Development**: In-memory backend for testing
- **Staging**: Single-node NATS for integration testing
- **Production**: Multi-backend setup based on use case requirements

#### **Data Consistency Patterns (`src/marty_msf/patterns/`)**
- **Saga Orchestration**: Long-running transaction coordination with compensation handlers
- **Transactional Outbox Pattern**: ACID-compliant event publishing with reliability guarantees
- **CQRS (Command Query Responsibility Segregation)**: Optimized read/write model separation
- **Event Sourcing Integration**: State reconstruction from event streams with snapshot support

##### Kafka Infrastructure Decision
The framework adopts **Apache Kafka with KRaft mode** for production event streaming:

- **Modern KRaft Mode**: Uses Kafka's new consensus protocol (KIP-500) eliminating Zookeeper dependency
- **Simplified Operations**: Reduces infrastructure complexity and operational overhead
- **Better Performance**: Improved startup times and reduced resource consumption
- **Future-Proof**: Zookeeper-based deployments are deprecated in Kafka 4.0+

**Alternative Configurations Evaluated:**
- **Bitnami Kafka**: Rejected due to unstable `latest` tag and Zookeeper dependency
- **Confluent Platform 6.x**: Rejected due to outdated version and Zookeeper requirement
- **Wurstmeister Kafka**: Rejected due to deprecated/unmaintained image
- **Apache Kafka without Zookeeper**: Rejected to maintain production parity

**Selected**: Confluent Platform 7.4.0 + Zookeeper for production parity across all environments

**Configuration Location**: `ops/k8s/observability/kafka.yaml` (used for both development and production)

### 3. Plugin Layer

#### Plugin Management (`src/framework/plugins/`)
- Dynamic plugin discovery and loading
- Lifecycle management (initialize, start, stop)
- Dependency resolution between plugins
- Hot-pluggable architecture

#### Extension Points
- Custom middleware registration
- Database provider plugins
- Authentication provider plugins
- Monitoring and metrics plugins

### 4. Infrastructure Layer

#### Kubernetes Integration
- Helm charts for service deployment
- Kustomize configurations for environment management
- Health check and readiness probes
- Resource management and scaling

#### Message Streaming Infrastructure
- **Apache Kafka (KRaft Mode)**: Production event streaming without Zookeeper
- **Development Configuration**: Single-node setup with auto-topic creation
- **Production Configuration**: Multi-node setup with observability integration
- **High Availability**: Replication and persistence configured for durability

#### Service Mesh Support
- **Dual Mesh Strategy**: First-class support for both Istio and Linkerd
- **Automatic Sidecar Injection**: Transparent proxy injection for all services
- **Traffic Management**: Advanced routing, load balancing, and fault tolerance
- **Security Policies**: Mutual TLS (mTLS) and fine-grained authorization
- **Observability Integration**: Seamless metrics, tracing, and logging

**Service Mesh Features:**
- **Circuit Breakers**: Automatic failure detection and service protection
- **Retry Policies**: Intelligent retry mechanisms with exponential backoff
- **Rate Limiting**: Request throttling and quota management
- **Fault Injection**: Chaos engineering for resilience testing
- **Traffic Splitting**: Blue-green and canary deployment support

**Operational Benefits:**
- **Zero-Code Implementation**: Infrastructure-level resilience patterns
- **Consistent Policy Enforcement**: Uniform policies across all services
- **Enhanced Security**: Network-level encryption and authentication
- **Simplified Operations**: Centralized configuration and monitoring

#### Kustomize Integration
- **Environment Management**: Streamlined configuration across dev/staging/prod
- **Service Mesh Overlays**: Automated generation of mesh-specific configurations
- **Policy Templates**: Reusable templates for common resilience patterns
- **GitOps Ready**: Declarative configurations for continuous deployment

## 🔧 Design Principles

### 1. Modularity
- **Loose Coupling**: Components interact through well-defined interfaces
- **High Cohesion**: Related functionality is grouped together
- **Plugin Architecture**: Extensible through plugins without core changes

### 2. Scalability
- **Horizontal Scaling**: Services can be scaled independently
- **Asynchronous Processing**: Non-blocking I/O and async/await patterns
- **Resource Efficiency**: Optimized for containerized environments

### 3. Reliability
- **Fault Tolerance**: Graceful handling of failures with resilience patterns
- **Observability**: Comprehensive monitoring and debugging capabilities
- **Testing**: Built-in testing framework with multiple test types

### 4. Security
- **Defense in Depth**: Multiple layers of security controls
- **Zero Trust**: No implicit trust between components
- **Compliance**: Built-in support for security standards and auditing

## 🔄 Request Flow

### Typical Request Lifecycle:

1. **Ingress**: Request enters through load balancer/ingress controller
2. **Service Mesh**: Traffic routing and security policies applied
3. **Authentication**: JWT validation and user context establishment
4. **Authorization**: Permission checks against RBAC policies
5. **Rate Limiting**: Request throttling and quota enforcement
6. **Business Logic**: Core service logic execution
7. **Database Operations**: Transactional data operations
8. **Event Publishing**: Asynchronous event notifications
9. **Response**: Structured response with proper error handling
10. **Observability**: Metrics, traces, and logs captured

## 📊 Data Flow Patterns

### 1. Synchronous Communication
- **REST APIs**: HTTP/HTTPS for external interfaces
- **gRPC**: High-performance internal service communication
- **GraphQL**: Flexible data querying (optional)

### 2. Asynchronous Communication
- **Event Bus**: In-memory event routing
- **Message Queues**: Persistent message delivery
- **Event Sourcing**: Immutable event logging

### 3. Data Persistence
- **Transactional Data**: ACID-compliant database operations
- **Event Store**: Immutable event history
- **Caching**: Redis/Memcached for performance optimization

## 🛡️ Security Architecture

### Multi-Layer Security Model:

1. **Network Security**: TLS/mTLS encryption, network policies
2. **Authentication**: JWT tokens, OAuth2/OIDC integration
3. **Authorization**: RBAC with fine-grained permissions
4. **Data Protection**: Encryption at rest and in transit
5. **Audit Trail**: Comprehensive security event logging

## 🔍 Monitoring & Observability

### Three Pillars of Observability:

1. **Metrics**: Prometheus metrics with Grafana dashboards
2. **Logs**: Structured logging with ELK/EFK stack integration
3. **Traces**: Distributed tracing with Jaeger/Zipkin

### Health Monitoring:
- **Health Checks**: Kubernetes-compatible health endpoints
- **SLA/SLO Tracking**: Performance and availability monitoring
- **Alerting**: Proactive issue detection and notification

## 🚀 Deployment Patterns

### 1. Container-First Design
- **Docker**: Containerized service packaging
- **Multi-stage Builds**: Optimized container images
- **Security Scanning**: Vulnerability detection in images

### 2. Kubernetes Native
- **Helm Charts**: Templated Kubernetes deployments
- **Operators**: Custom resource management
- **GitOps**: Declarative deployment workflows

### 3. Environment Management
- **Configuration**: Environment-specific settings
- **Secrets**: Secure credential management
- **Feature Flags**: Runtime behavior control

## 📈 Performance Considerations

### Optimization Strategies:
- **Connection Pooling**: Efficient database connections
- **Caching**: Multi-level caching strategies
- **Async Processing**: Non-blocking operation patterns
- **Resource Limits**: Memory and CPU management
- **Auto-scaling**: Dynamic resource allocation

## 🔮 Extensibility

### Plugin Development:
1. **Interface Implementation**: Follow framework interfaces
2. **Lifecycle Management**: Proper initialization and cleanup
3. **Configuration**: Plugin-specific configuration support
4. **Testing**: Unit and integration test requirements

### Custom Components:
- **Middleware**: Request/response processing
- **Providers**: Database, authentication, monitoring providers
- **Handlers**: Custom business logic handlers
- **Validators**: Data validation and transformation

## 🔌 Adapter Readiness & Optional Extras

| Adapter | Status | Notes |
| --- | --- | --- |
| Client-side discovery | Production-ready | Uses the in-memory registry API and participates in the shared caching layer. |
| Server-side discovery | Production-ready | Communicates with HTTP discovery services; requires reachable discovery endpoint. |
| Hybrid discovery | Production-ready | Combines client- and server-side adapters; falls back automatically if the preferred path fails. |
| Service mesh discovery | Preview (stub) | Requires a Kubernetes client via `mesh_config["client_factory"]`. Set `allow_stub: True` only for local development to use the `MockKubernetesClient`, which returns no endpoints. |
| External connectors (REST, gRPC, SOAP) | Production-ready | Provide retry and circuit breaker integration out of the box. |
| Marketplace connectors marked “sandbox” | Experimental | Use behind feature flags until validation is complete. |

> **Tip:** See `src/framework/discovery/clients/service_mesh.py` for guidance on wiring a real mesh adapter and the guardrails that prevent the stub from shipping unchecked.

### Optional Dependency Groups

Heavy observability and analytics toolchains are now distributed via extras so base installations remain lightweight:

- `pip install marty-msf[observability]` – Prometheus client library and OpenTelemetry SDK/exporters.
- `pip install marty-msf[analytics]` – Data analysis and load-testing stack (NumPy, Matplotlib, Seaborn, Locust).
- `pip install marty-msf[all]` – Installs all optional extras alongside the microservices and cloud integrations.

## 📚 Related Documentation

- **[Data Consistency Patterns](../data-consistency-patterns.md)** - Comprehensive guide to saga, outbox, and CQRS patterns
- **[Plugin Development Guide](guides/plugin-system.md)**
- **[Testing Strategy](development/TESTING_STRATEGY.md)**
- **[Migration Guide](guides/MIGRATION_GUIDE.md)**
- **[Observability Setup](guides/observability.md)**
- **[CLI Usage](guides/CLI_README.md)**

## 🎯 Recent Architecture Enhancements

### Data Consistency Patterns Implementation (October 2025)

The framework has been enhanced with enterprise-grade data consistency patterns to address the challenges of distributed transaction management and reliable event publishing in microservices architectures.

#### **Key Implementation Decisions:**

1. **Saga Orchestration Enhancement**
   - **Decision**: Enhanced existing `saga.py` with advanced compensation handlers rather than creating from scratch
   - **Rationale**: Preserved existing integrations while adding enterprise features like parallel execution and state management
   - **Location**: `src/marty_msf/patterns/saga/` (enhanced existing implementation)

2. **Transactional Outbox Pattern**
   - **Decision**: Implemented comprehensive outbox pattern with batch processing and dead letter queues
   - **Rationale**: Ensures ACID compliance for business data and events, eliminates dual-write problems
   - **Features**:
     - Batch processing for performance (configurable batch sizes)
     - Dead letter queue handling for failed events
     - Multi-broker support (Kafka/RabbitMQ)
     - Retry mechanisms with exponential backoff
   - **Location**: `src/marty_msf/patterns/outbox/enhanced_outbox.py`

3. **CQRS Templates and Implementation**
   - **Decision**: Created comprehensive CQRS templates with validation and projection builders
   - **Rationale**: Enables optimal read/write model separation with built-in caching and validation
   - **Features**:
     - Command/Query handlers with generic type support
     - Read model projections with event-driven updates
     - Validation framework for commands and queries
     - Caching layer for performance optimization
   - **Location**: `src/marty_msf/patterns/cqrs/enhanced_cqrs.py`

4. **Unified Configuration System**
   - **Decision**: Created environment-specific configuration management
   - **Rationale**: Supports development, production, and testing environments with different scaling requirements
   - **Features**: Database, event store, message broker, saga, and CQRS configurations
   - **Location**: `src/marty_msf/patterns/config.py`

#### **Architecture Impact:**

- **Reliability**: Transactional outbox ensures no lost events due to system failures
- **Scalability**: CQRS enables independent scaling of read and write operations
- **Consistency**: Saga orchestration manages complex business workflows with proper compensation
- **Observability**: Comprehensive metrics and monitoring for all data consistency operations

#### **Integration with Existing Framework:**

- **Backward Compatibility**: All existing functionality preserved
- **Plugin Integration**: Data consistency patterns available as optional framework capabilities
- **Configuration**: Unified configuration system supports existing and new patterns
- **Testing**: Comprehensive test suite demonstrates integrated usage patterns

#### **Petstore Demo Enhancement:**

The petstore domain plugin has been enhanced to demonstrate the outbox pattern:

- **New Endpoints**: `/api/v1/petstore-outbox/*` showcasing transactional outbox pattern
- **Reliable Events**: All business operations (pet creation, orders, user registration) use outbox pattern
- **Metrics**: Real-time outbox processing metrics available at `/petstore-outbox/metrics`
- **Health Checks**: Outbox-specific health checks for monitoring reliability

#### **Performance Considerations:**

- **Batch Processing**: Outbox events processed in configurable batches (default: 100 events)
- **Connection Pooling**: Optimized database and message broker connections
- **Caching**: Multi-level caching for CQRS read models
- **Async Processing**: Non-blocking outbox event processing

#### **Deployment Requirements:**

- **Database**: PostgreSQL with outbox tables for transactional guarantee
- **Message Brokers**: Kafka or RabbitMQ for reliable event delivery
- **Configuration**: Environment-specific settings for scaling and performance
- **Monitoring**: Integration with existing Prometheus/Grafana observability stack

### 🛠️ CLI Tools and Developer Experience

The framework provides comprehensive command-line tools for development, migration, and operations:

#### Migration Commands (`marty migrate`)
- **helm-to-kustomize**: Convert Helm charts to Kustomize manifests with MMF optimizations
- **generate-overlay**: Create environment-specific Kustomize overlays with service mesh support
- **validate-migration**: Verify migration consistency and functional parity
- **check-compatibility**: Assess Helm chart migration readiness and complexity

#### Service Mesh Commands (`marty service-mesh`)
- **install**: Deploy and configure Istio or Linkerd service mesh with MMF integration
- **apply-policies**: Apply traffic policies (circuit breakers, retries, rate limiting, fault injection)
- **status**: Monitor service mesh health, injection status, and policy compliance

#### Plugin Commands (`marty plugin`)
- **create**: Generate new microservice plugins with architectural patterns
- **add-service**: Add services to existing plugins with feature integration
- **list**: Display available plugins and their configurations

#### Service Generation Features
- **Architectural Patterns**: Support for layered, hexagonal, clean, and CQRS/ES architectures
- **Service Templates**: FastAPI, gRPC, and hybrid service scaffolding
- **Feature Integration**: Database, caching, authentication, and observability components
- **Service Mesh Integration**: Automatic annotation generation and policy application

#### Development Workflow Integration
- **Environment Management**: Seamless dev/staging/prod configuration management
- **Policy Templates**: Pre-configured resilience patterns for common scenarios
- **Monitoring Setup**: Automatic service mesh metrics and dashboard configuration
- **GitOps Support**: Declarative configurations ready for continuous deployment

---

This architecture supports the framework's mission of providing enterprise-grade microservices capabilities while maintaining developer productivity and operational excellence.
