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
- Circuit breakers for fault tolerance
- Retry mechanisms with exponential backoff
- Bulkhead isolation patterns
- Timeout handling and graceful degradation

#### Event-Driven Architecture (`src/framework/events/`)
- Event bus for inter-service communication
- Message queue integration (Kafka, RabbitMQ)
- Event sourcing capabilities
- CQRS pattern support

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
- Istio/Linkerd integration
- Traffic management and routing
- Security policies and mTLS
- Observability and monitoring

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

- **[Plugin Development Guide](guides/plugin-system.md)**
- **[Testing Strategy](development/TESTING_STRATEGY.md)**
- **[Migration Guide](guides/MIGRATION_GUIDE.md)**
- **[Observability Setup](guides/observability.md)**
- **[CLI Usage](guides/CLI_README.md)**

---

This architecture supports the framework's mission of providing enterprise-grade microservices capabilities while maintaining developer productivity and operational excellence.
