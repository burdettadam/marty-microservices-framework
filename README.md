# Marty Microservices Framework

A comprehensive, standalone framework for building enterprise-grade microservices with Python, FastAPI, gRPC, and modern development practices.

## 🎯 Overview

The Marty Microservices Framework is a complete toolkit for building production-ready microservices. It provides:

- **Service Templates** - Pre-built templates for common service patterns
- **Code Generation** - Automated service scaffolding with DRY principles
- **Enterprise Framework** - Security, database, configuration, and audit logging
- **Security Framework** - Comprehensive security middleware, authentication, rate limiting, and audit tools
- **Enterprise Observability** - Kafka events, Prometheus monitoring, load testing
- **Best Practices** - Enterprise-grade patterns and configurations
- **Testing Framework** - Comprehensive validation and testing tools

## 🏗️ Framework Structure

```
marty-microservices-framework/
├── src/                        # Enterprise framework components
│   └── framework/             # Core enterprise framework
│       ├── security/          # Enterprise security (auth, RBAC, middleware)
│       ├── database/          # Database utilities (repository patterns, transactions)
│       ├── audit/             # Audit logging (encryption, compliance, SIEM)
│       └── config.py          # Environment-based configuration management
├── security/                   # Comprehensive security framework
│   ├── middleware/            # Security middleware (auth, rate limiting, headers)
│   ├── policies/              # RBAC and Kubernetes security policies
│   ├── tools/                 # Security audit and scanning tools
│   ├── scanners/              # Automated security scanners
│   └── README.md              # Security framework documentation
├── k8s/                        # Kubernetes manifests and Kind configurations
│   ├── kind-cluster-config.yaml # Kind cluster setup for development
│   ├── observability/         # Observability stack (Prometheus, Grafana, Kafka)
│   └── service-mesh/          # Service mesh configurations (Istio/Linkerd)
├── scripts/                    # Framework tools and utilities
│   ├── generate_service.py    # Service generator with K8s and service mesh support
│   ├── setup-cluster.sh       # Kind cluster setup with service mesh
│   ├── cleanup.sh             # Cluster cleanup script
│   ├── validate.sh            # Cluster validation script
│   ├── validate_templates.py  # Template validator
│   ├── test_framework.py      # Comprehensive testing
│   ├── validate_observability.py # Observability validation
│   └── setup_framework.sh     # Framework setup script
├── service/                    # Service templates
│   ├── fastapi_service/       # REST API services
│   ├── grpc_service/          # gRPC services
│   ├── hybrid_service/        # Combined REST + gRPC
│   ├── auth_service/          # Authentication services
│   ├── database_service/      # Database-backed services
│   ├── caching_service/       # Redis caching services
│   └── message_queue_service/ # Message queue services
├── service-mesh/              # Service mesh policies and configurations
│   ├── istio/                 # Istio configurations and policies
│   ├── linkerd/               # Linkerd configurations and policies
│   ├── dashboards/            # Service mesh Grafana dashboards
│   └── monitoring/            # Service mesh alert rules
├── observability/              # Enterprise observability stack
│   ├── kafka/                 # Event streaming infrastructure
│   ├── monitoring/            # Prometheus, Grafana, Alertmanager configs
│   ├── metrics/               # Metrics collection framework
│   └── load_testing/          # Performance testing tools
├── microservice_project_template/ # Complete project template with K8s manifests
│   └── k8s/                   # Kubernetes manifests with service mesh support
│       ├── base/              # Base Kubernetes resources
│       ├── overlays/          # Kustomize overlays for different environments
│       └── service-mesh/      # Service mesh specific configurations
├── tests/                     # Framework tests
├── .pre-commit-config.yaml    # Git hooks for code quality
├── .gitignore                 # Git ignore patterns
├── requirements.txt           # Core dependencies
├── requirements-dev.txt       # Development dependencies
├── mypy.ini                   # Type checking configuration
└── README.md                  # This file
```

## 🚀 Quick Start

### 1. Setup Framework

```bash
# Clone the standalone framework
git clone <repository-url> marty-microservices-framework
cd marty-microservices-framework

# Run setup script (installs dependencies and validates)
./scripts/setup_framework.sh
```

### 2. Setup Kubernetes Development Environment

```bash
# Create Kind cluster with observability and service mesh
./scripts/setup-cluster.sh

# Or with specific service mesh
./scripts/setup-cluster.sh --service-mesh istio
./scripts/setup-cluster.sh --service-mesh linkerd
./scripts/setup-cluster.sh --service-mesh none --no-observability

# Validate cluster setup
./scripts/validate.sh
```

### 3. Generate Your First Service

```bash
# Generate a FastAPI REST service
python3 scripts/generate_service.py fastapi user-service \
  --description "User management service" \
  --http-port 8080

# Generate a gRPC service with service mesh
python3 scripts/generate_service.py grpc document-processor \
  --description "Document processing service" \
  --grpc-port 50051 \
  --service-mesh --service-mesh-type istio

# Generate a hybrid service (REST + gRPC) for production
python3 scripts/generate_service.py hybrid payment-service \
  --description "Payment processing service" \
  --http-port 8080 --grpc-port 50051 \
  --service-mesh --namespace production --domain api.company.com
```

### 4. Deploy to Kubernetes

```bash
# Deploy generated service to Kind cluster
cd src/user_service
kubectl apply -k k8s/base/

# Deploy with service mesh (Istio/Linkerd)
kubectl apply -k k8s/overlays/service-mesh/

# Verify deployment
kubectl get pods -n microservice-framework
kubectl get virtualservices -n microservice-framework  # For Istio
kubectl get servers -n microservice-framework          # For Linkerd
```

### 5. Access Services and Dashboards

```bash
# Port forward to access services locally
kubectl port-forward -n observability svc/grafana 3000:3000 &
kubectl port-forward -n observability svc/prometheus 9090:9090 &

# Service mesh dashboards
kubectl port-forward -n istio-system svc/istio-ingressgateway 80:80 &  # Istio
linkerd viz dashboard &                                                  # Linkerd

# Access dashboards
open http://localhost:3000  # Grafana (admin/admin)
open http://localhost:9090  # Prometheus
```

## 🛡️ Security Framework

The framework includes a comprehensive security module providing enterprise-grade security capabilities:

### Security Features

- **Authentication Middleware**: JWT-based authentication with RBAC support
- **Rate Limiting**: Distributed rate limiting with Redis backend
- **Security Headers**: CSP, HSTS, CORS, and security header management
- **Security Scanning**: Automated vulnerability scanning and auditing
- **Policy Management**: RBAC policies and Kubernetes security policies

### Quick Security Setup

```python
from fastapi import FastAPI
from security import (
    AuthenticationMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    create_security_headers_config
)

app = FastAPI()

# Add security middleware stack
app.add_middleware(
    SecurityHeadersMiddleware,
    config=create_security_headers_config(environment="production")
)

app.add_middleware(
    RateLimitMiddleware,
    redis_url="redis://localhost:6379",
    default_requests_per_hour=1000
)

app.add_middleware(
    AuthenticationMiddleware,
    jwt_secret_key=os.getenv("JWT_SECRET_KEY"),
    excluded_paths=["/health", "/docs"]
)
```

### Security Scanning

```bash
# Run comprehensive security audit
./security/scanners/security_scan.sh

# Run specific security checks
python security/tools/security_audit.py --verbose
```

For detailed security documentation, see [Security Framework README](security/README.md).

## 🎭 Service Mesh Integration

The framework provides first-class support for service mesh technologies:

### Istio Service Mesh

- **Traffic Management**: VirtualServices, DestinationRules, Gateways
- **Security**: mTLS, Authorization Policies, PeerAuthentication
- **Observability**: Prometheus metrics, distributed tracing, access logs
- **Circuit Breaking**: Outlier detection and connection pooling

### Linkerd Service Mesh

- **Traffic Management**: HTTPRoutes, Servers, load balancing
- **Security**: mTLS by default, ServerAuthorization policies
- **Observability**: Built-in Prometheus metrics, Grafana dashboards
- **Performance**: Ultra-lightweight proxy with minimal overhead

### Service Mesh Features

```bash
# Generate service with Istio configuration
python3 scripts/generate_service.py fastapi api-gateway \
  --service-mesh --service-mesh-type istio \
  --namespace production

# Generated files include:
# ├── k8s/service-mesh/istio.yaml       # VirtualService, DestinationRule
# ├── k8s/service-mesh/linkerd.yaml     # Servers, ServerAuthorization
# └── k8s/overlays/service-mesh/        # Service mesh overlay
```

## � Service Mesh Architecture

The framework provides comprehensive service mesh integration that can be configured during service generation or deployed separately for existing services.

### Istio Service Mesh

**Traffic Management:**
```yaml
# VirtualService for advanced routing
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: api-gateway
spec:
  http:
  - match:
    - uri:
        prefix: /api/v1
    route:
    - destination:
        host: api-gateway
        subset: v1
      weight: 90
    - destination:
        host: api-gateway
        subset: v2
      weight: 10
  - fault:
      delay:
        percentage:
          value: 0.1
        fixedDelay: 5s
```

**Security Policies:**
```yaml
# mTLS and Authorization
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: api-gateway-authz
spec:
  rules:
  - from:
    - source:
        principals: ["cluster.local/ns/microservice-framework/sa/frontend"]
  - to:
    - operation:
        methods: ["GET", "POST"]
        paths: ["/api/v1/*"]
```

**Circuit Breaker:**
```yaml
# DestinationRule for resilience
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: api-gateway
spec:
  host: api-gateway
  trafficPolicy:
    outlierDetection:
      consecutive5xxErrors: 5
      interval: 30s
      baseEjectionTime: 30s
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        http1MaxPendingRequests: 50
        maxRequestsPerConnection: 5
```

### Linkerd Service Mesh

**Traffic Routing:**
```yaml
# HTTPRoute for traffic splitting
apiVersion: gateway.networking.k8s.io/v1beta1
kind: HTTPRoute
metadata:
  name: api-gateway-route
spec:
  parentRefs:
  - name: default-gateway
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /api/v1
    backendRefs:
    - name: api-gateway-v1
      port: 8080
      weight: 90
    - name: api-gateway-v2
      port: 8080
      weight: 10
```

**Authorization:**
```yaml
# ServerAuthorization for security
apiVersion: policy.linkerd.io/v1beta1
kind: ServerAuthorization
metadata:
  name: api-gateway-authz
spec:
  server:
    name: api-gateway-server
  requiredRoutes:
  - pathRegex: /api/v1/.*
    methods: ["GET", "POST"]
  client:
    meshTLS:
      serviceAccounts:
      - name: frontend
        namespace: microservice-framework
```

### Service Mesh Features

**Observability Integration:**
- **Metrics**: Automatic collection of request metrics, latency percentiles, error rates
- **Tracing**: Distributed tracing with Jaeger integration
- **Logs**: Structured access logs with correlation IDs
- **Dashboards**: Pre-configured Grafana dashboards for service mesh metrics

**Security Features:**
- **mTLS**: Automatic mutual TLS for all service-to-service communication
- **Authorization**: Fine-grained access control policies
- **Network Policies**: Kubernetes NetworkPolicy integration
- **Security Scanning**: Vulnerability assessment for service mesh components

**Traffic Management:**
- **Load Balancing**: Round robin, least connection, consistent hash algorithms
- **Traffic Splitting**: Canary deployments and A/B testing
- **Circuit Breaking**: Automatic failure detection and recovery
- **Retry Logic**: Configurable retry policies with exponential backoff

### Service Mesh Deployment

**Automated Setup:**
```bash
# Setup Kind cluster with service mesh
./scripts/setup-cluster.sh --service-mesh istio

# Deploy service with service mesh
python3 scripts/generate_service.py fastapi payment-service \
  --service-mesh --service-mesh-type istio \
  --namespace production

# Apply service mesh configuration
kubectl apply -k src/payment_service/k8s/overlays/service-mesh/
```

**Manual Configuration:**
```bash
# Install Istio
istioctl install --set values.defaultRevision=default

# Enable namespace for injection
kubectl label namespace microservice-framework istio-injection=enabled

# Install Linkerd
linkerd install | kubectl apply -f -
linkerd viz install | kubectl apply -f -

# Inject existing deployments
kubectl get deploy -o yaml | linkerd inject - | kubectl apply -f -
```

**Validation:**
```bash
# Validate service mesh installation
./scripts/validate.sh --service-mesh

# Check mTLS status
istioctl authn tls-check api-gateway.microservice-framework.svc.cluster.local

# Verify Linkerd
linkerd check
linkerd viz stat deploy
```

## �📚 Service Templates

### FastAPI Service (`fastapi_service`)
- **Purpose**: HTTP REST API services
- **Features**: FastAPI, Pydantic, OpenAPI docs, health checks
- **Use Cases**: Web APIs, REST microservices, admin interfaces

### gRPC Service (`grpc_service`)
- **Purpose**: High-performance RPC services
- **Features**: Protocol Buffers, type safety, streaming
- **Use Cases**: Internal service communication, high-throughput APIs

### Hybrid Service (`hybrid_service`)
- **Purpose**: Combined REST and gRPC endpoints
- **Features**: Best of both worlds, flexible client support
- **Use Cases**: Services needing both web and internal APIs

### Authentication Service (`auth_service`)
- **Purpose**: User authentication and authorization
- **Features**: JWT tokens, OAuth2, RBAC, MFA, session management
- **Use Cases**: User login, access control, identity management

### Database Service (`database_service`)
- **Purpose**: Data persistence and management
- **Features**: SQLAlchemy ORM, PostgreSQL, migrations, connection pooling
- **Use Cases**: Data storage, CRUD operations, data modeling

### Caching Service (`caching_service`)
- **Purpose**: High-performance caching layer
- **Features**: Redis integration, cache patterns, distributed locking
- **Use Cases**: Performance optimization, session storage, rate limiting

### Message Queue Service (`message_queue_service`)
- **Purpose**: Asynchronous messaging and event processing
- **Features**: Kafka, RabbitMQ, Redis support, producers/consumers
- **Use Cases**: Event-driven architecture, background processing, notifications

## 🔍 Enterprise Observability Stack

The framework includes a comprehensive observability infrastructure that provides enterprise-grade monitoring, event streaming, and performance analysis capabilities - based on proven patterns from production microservices.

### 📊 **Kafka Event Streaming** (`observability/kafka/`)

Enterprise event bus for microservice communication with:

- **Event Bus**: Async publishing/consumption with aiokafka integration
- **Standard Event Format**: Correlation IDs, structured messages, distributed tracing
- **Topic Patterns**: Service and domain event organization
- **Monitoring**: Kafka UI, consumer lag tracking, throughput metrics

**Quick Start:**
```bash
# Start Kafka infrastructure on Kubernetes
kubectl apply -f k8s/observability/kafka.yaml

# Verify Kafka deployment
kubectl get pods -n observability | grep kafka

# Port forward to access Kafka UI
kubectl port-forward -n observability svc/kafka-ui 8080:8080

# Access Kafka UI
open http://localhost:8080
```

**Usage Example:**
```python
from observability.kafka import EventBus, KafkaConfig, publish_domain_event

# Setup event bus
kafka_config = KafkaConfig(bootstrap_servers=["localhost:9092"])
event_bus = EventBus(kafka_config, "user-service")
await event_bus.start()

# Publish domain event
await publish_domain_event(
    event_bus,
    domain="user",
    event_type="user.created",
    data={"user_id": user.id, "email": user.email},
    correlation_id=request.correlation_id
)
```

### 📈 **Monitoring Stack** (`observability/monitoring/`)

Complete monitoring with Prometheus, Grafana, and Alertmanager:

- **Prometheus**: Metrics collection from all services
- **Grafana**: Rich dashboards for service and business metrics
- **Alertmanager**: Smart alerting with team routing and runbook links
- **Alert Rules**: Pre-configured alerts for errors, latency, resource usage

**Quick Start:**
```bash
# Start monitoring stack on Kubernetes
kubectl apply -f k8s/observability/prometheus.yaml
kubectl apply -f k8s/observability/grafana.yaml

# Verify monitoring deployment
kubectl get pods -n observability | grep -E "(prometheus|grafana)"

# Port forward to access dashboards
kubectl port-forward -n observability svc/grafana 3000:3000 &
kubectl port-forward -n observability svc/prometheus 9090:9090 &

# Access dashboards
open http://localhost:3000  # Grafana (admin/admin)
open http://localhost:9090  # Prometheus
```

**Included Dashboards:**
- **Microservice Detail**: gRPC metrics, latency percentiles, error rates
- **Platform Overview**: System health, resource usage, service topology
- **Business Metrics**: Transaction volume, success rates, revenue tracking
- **Kafka Monitoring**: Throughput, consumer lag, partition health

### 🎯 **Metrics Collection** (`observability/metrics/`)

Standardized metrics collection for all microservices:

- **gRPC Metrics**: Request rates, latency percentiles, error rates by method
- **Business Metrics**: Transaction tracking, conversion rates, revenue metrics
- **System Metrics**: Database connections, cache hit rates, resource usage
- **Custom Metrics**: Easy creation of service-specific metrics

**Usage Example:**
```python
from observability.metrics import MetricsCollector, MetricsConfig, grpc_metrics_decorator

# Setup metrics
metrics_config = MetricsConfig(service_name="user-service", service_version="1.2.0")
metrics = MetricsCollector(metrics_config)

# Automatic gRPC metrics
@grpc_metrics_decorator(metrics)
async def get_user(request):
    return await user_service.get_user(request.user_id)

# Custom business metrics
revenue_counter = metrics.create_custom_counter(
    name="revenue_total",
    description="Total revenue processed",
    labels=["currency", "region"]
)
```

### ⚡ **Load Testing & Performance Analysis** (`observability/load_testing/`)

Comprehensive performance testing and capacity planning:

- **gRPC Load Testing**: Service-specific performance validation
- **HTTP Load Testing**: REST API performance analysis
- **Real-time Monitoring**: Live performance metrics during tests
- **Detailed Reporting**: P95/P99 latency, throughput, error analysis

**Quick Start:**
```bash
# Run load test examples
python3 observability/load_testing/examples.py grpc
python3 observability/load_testing/examples.py http
python3 observability/load_testing/examples.py stress
```

**Usage Example:**
```python
from observability.load_testing import LoadTestConfig, LoadTestRunner

# Configure load test
config = LoadTestConfig(
    target_host="localhost",
    target_port=50051,
    concurrent_users=50,
    test_duration_seconds=300,
    protocol="grpc"
)

# Run test with real-time monitoring
runner = LoadTestRunner()
report = await runner.run_load_test(config)

# Detailed performance analysis
runner.print_summary(report)  # P95: 45ms, P99: 120ms, 500 RPS
```

### 🚀 **Getting Started with Observability**

1. **Start Complete Stack**:
   ```bash
   # Setup Kubernetes cluster with observability
   ./scripts/setup-cluster.sh

   # Or deploy individual components
   kubectl apply -f k8s/observability/kafka.yaml
   kubectl apply -f k8s/observability/prometheus.yaml
   kubectl apply -f k8s/observability/grafana.yaml

   # Verify deployment
   kubectl get pods -n observability
   ```

2. **Integrate with Your Service**:
   ```python
   from observability import setup_observability

   # One-line setup
   metrics, event_bus = await setup_observability(
       service_name="my-service",
       service_version="1.0.0"
   )
   ```

3. **Access Dashboards**:
   - **Grafana**: http://localhost:3000 (comprehensive service dashboards)
   - **Kafka UI**: http://localhost:8080 (event streaming management)
   - **Prometheus**: http://localhost:9090 (metrics and alerting)
   - **Jaeger**: http://localhost:16686 (distributed tracing)

### 📋 **Production SLOs & Best Practices**

**Target SLOs:**
- **Availability**: 99.9% uptime
- **Latency**: P95 < 500ms, P99 < 1000ms
- **Error Rate**: < 1% for business operations
- **Throughput**: 1000+ RPS per service instance

**Alert Severity Levels:**
- **Critical**: Service down, >20% error rate, >3s latency
- **Warning**: >5% error rate, >1s latency, resource exhaustion
- **Info**: Unusual patterns, capacity planning alerts

**Load Testing Scenarios:**
- **Normal Load**: 10 concurrent users, 100 RPS
- **Peak Load**: 50 concurrent users, 500 RPS
- **Stress Test**: 100+ concurrent users, 1000+ RPS
- **Endurance**: Extended duration tests (1+ hours)

## 🛠️ Framework Tools

### Service Generator (`generate_service.py`)
Generates new microservices from templates with customizable parameters.

```bash
python3 scripts/generate_service.py <type> <name> [options]

# Examples:
python3 scripts/generate_service.py fastapi api-gateway --http-port 8080
python3 scripts/generate_service.py grpc data-processor --grpc-port 50052
python3 scripts/generate_service.py hybrid user-service --description "User management"
```

**Options:**
- `--description`: Service description
- `--author`: Author name
- `--http-port`: HTTP port for FastAPI services
- `--grpc-port`: gRPC port for gRPC services
- `--output-dir`: Output directory (default: ./src)

### Template Validator (`validate_templates.py`)
Validates all service templates for syntax and structural correctness.

```bash
python3 scripts/validate_templates.py
```

**Validates:**
- Jinja2 template syntax
- Generated Python code validity
- Template structure and required files
- Variable interpolation

### Framework Tester (`test_framework.py`)
Comprehensive testing of the entire framework.

```bash
python3 scripts/test_framework.py
```

**Tests:**
- Template validation
- Service generation for all types
- Framework structure integrity
- Script functionality
- Feature completeness

### Observability Validator (`validate_observability.py`)
Validates all observability components for correctness and integration.

```bash
python3 scripts/validate_observability.py
```

**Validates:**
- Kafka configuration files and connectivity
- Prometheus and alert rule syntax
- Grafana dashboard JSON structure
- Metrics collection functionality
- Load testing component integration
- Kubernetes manifests and deployments
- Service mesh configurations

## 🏃‍♂️ Development Workflow

### 1. Planning Phase
```bash
# Validate framework before starting
python3 scripts/test_framework.py
```

### 2. Service Development
```bash
# Generate service scaffolding
python3 scripts/generate_service.py fastapi my-service

# Navigate to generated service
cd src/my_service

# Implement business logic
# - Edit app/services/my_service_service.py
# - Add API endpoints in app/api/routes.py
# - Configure in app/core/config.py
```

### 3. Testing & Validation

```bash
# Test framework and service generation
python3 scripts/test_framework.py

# Validate templates after changes
python3 scripts/validate_templates.py

# Test Kubernetes deployment
kubectl apply --dry-run=client -k src/my_service/k8s/base/

# Validate Kind cluster and services
./scripts/validate.sh

# Run service mesh validation
./scripts/validate.sh --service-mesh
```

### Kubernetes Testing

```bash
# Deploy test service to Kind cluster
cd src/my_service
kubectl apply -k k8s/base/

# Verify deployment status
kubectl get pods -n microservice-framework
kubectl describe deployment my-service -n microservice-framework

# Test service connectivity
kubectl port-forward -n microservice-framework svc/my-service 8080:8080

# Test service mesh configuration (if enabled)
kubectl get virtualservices -n microservice-framework  # Istio
kubectl get servers -n microservice-framework          # Linkerd

# Clean up test deployment
kubectl delete -k k8s/base/
```

## � Git Setup & Code Quality

### Pre-commit Hooks

The framework includes comprehensive pre-commit hooks that ensure code quality:

```bash
# Install pre-commit hooks (done automatically during setup)
pre-commit install

# Run hooks manually on all files
pre-commit run --all-files

# Run specific hooks
pre-commit run mypy-type-check
pre-commit run template-validation
pre-commit run observability-validation
pre-commit run framework-tests
```

### Automated Quality Checks

Every commit automatically runs:

- **Code Formatting**: Black and isort for consistent styling
- **Type Checking**: MyPy for static type validation
- **Template Validation**: Ensures all service templates are valid
- **Observability Validation**: Validates Kafka, Prometheus, and monitoring configs
- **Framework Tests**: Comprehensive framework functionality tests
- **Service Generation**: Smoke tests for service generation
- **Documentation**: Consistency checks for documentation
- **Dependencies**: Validation of framework dependencies

### Development Commands

```bash
# Run all quality checks
make test-all              # Tests + type checking
make typecheck             # MyPy type checking only
make validate              # Template validation only

# Code quality
pre-commit run --all-files # All pre-commit hooks
```

### Git Workflow

```bash
# Standard development workflow
git add .                  # Stage changes
git commit -m "message"    # Triggers pre-commit hooks automatically
git push                   # Push changes

# If pre-commit hooks fail:
# 1. Review and fix reported issues
# 2. Re-stage files: git add .
# 3. Commit again: git commit -m "fix: address code quality issues"
```

## �📦 Project Template

The `microservice_project_template` provides a complete project structure with:

- **Modern Python Setup**: UV package management, Python 3.10+
- **Development Tools**: Pre-commit hooks, linting, type checking
- **Testing Framework**: Pytest with coverage and parallel execution
- **CI/CD Pipeline**: GitHub Actions for testing and deployment
- **Docker Support**: Multi-stage builds, development/production configs
- **Kubernetes**: Deployment manifests and observability
- **Documentation**: Architecture docs, API specs, development guides

### Using the Project Template

```bash
# Create new project
cp -r microservice_project_template my-new-service
cd my-new-service

# Customize for your needs
# - Update pyproject.toml with your service details
# - Modify src/microservice_template/ to your service name
# - Update configuration in config files
# - Customize Kubernetes manifests

# Setup development environment
uv sync --extra dev

# Start development
make dev
```

## 🔧 Customization

### Adding New Templates

1. **Create Template Directory**:
   ```bash
   mkdir service/my_custom_service
   ```

2. **Add Template Files**:
   ```bash
   # Create Jinja2 templates (.j2 extension)
   touch service/my_custom_service/main.py.j2
   touch service/my_custom_service/config.py.j2
   ```

3. **Update Generator** (if needed):
   Edit `scripts/generate_service.py` to add new service type.

4. **Validate**:
   ```bash
   python3 scripts/validate_templates.py
   ```

### Template Variables

All templates have access to these variables:

- `service_name`: Hyphenated service name (e.g., "user-service")
- `service_package`: Python package name (e.g., "user_service")
- `service_class`: PascalCase class name (e.g., "UserService")
- `service_description`: Human-readable description
- `author`: Author name
- `grpc_port`: gRPC port number
- `http_port`: HTTP port number

## 🔍 Type Safety & Code Quality

The framework includes comprehensive type checking with MyPy to ensure code quality and developer experience.

### Type Checking Configuration

The framework uses strict MyPy configuration (`mypy.ini`) with:
- **Strict mode**: Comprehensive type checking
- **Error codes**: Detailed error reporting
- **Import following**: Full dependency analysis
- **Cache optimization**: Fast incremental checking

### Running Type Checks

```bash
# Basic type checking
make typecheck
python3 -m mypy scripts/ --config-file mypy.ini

# Strict type checking with detailed output
make typecheck-strict

# Run all tests including type checking
make test-all
```

### Type Annotations

All framework scripts include comprehensive type annotations:

```python
from typing import Dict, List, Any, Optional
from pathlib import Path

def generate_service(
    service_type: str,
    service_name: str,
    **options: Any
) -> None:
    """Generate a new service from templates."""
```

### Generated Code Quality

Templates generate type-safe code with:
- Full type annotations
- Proper return types
- Generic type usage
- Optional type handling

### Development Benefits

Type checking provides:
- **Early Error Detection**: Catch issues before runtime
- **Better IDE Support**: Enhanced autocomplete and navigation
- **Code Documentation**: Types serve as inline documentation
- **Refactoring Safety**: Confident code changes
- **Team Collaboration**: Clear interfaces and contracts

## 🧪 Testing

The framework includes comprehensive testing at multiple levels:

### Template Testing
```bash
# Validate all templates
python3 scripts/validate_templates.py

# Test specific aspects
python3 scripts/test_framework.py
```

### Generated Service Testing
```bash
# Generate test service
python3 scripts/generate_service.py fastapi test-service

# Verify generated code
cd src/test_service
python3 -m py_compile app/services/test_service_service.py
```

### Integration Testing
```bash
# Full framework test suite
python3 scripts/test_framework.py
```

## 🛡️ Best Practices

### Service Design
- **Single Responsibility**: Each service should have one clear purpose
- **API First**: Design APIs before implementation
- **Configuration**: Use environment variables for all configuration
- **Error Handling**: Implement comprehensive error handling
- **Logging**: Use structured logging throughout

### Development Practices
- **Type Safety**: Use type hints and mypy checking
- **Testing**: Write tests for all business logic
- **Documentation**: Document APIs and complex logic
- **Security**: Follow security best practices
- **Performance**: Profile and optimize critical paths

### Deployment Practices
- **Containerization**: Use Docker for consistent environments
- **Health Checks**: Implement readiness and liveness probes
- **Monitoring**: Add metrics and observability
- **Scaling**: Design for horizontal scaling
- **Secrets**: Use proper secret management

## 📖 Documentation

- **Architecture**: See `microservice_project_template/docs/ARCHITECTURE.md`
- **Development**: See `microservice_project_template/docs/LOCAL_DEVELOPMENT.md`
- **Observability**: See `microservice_project_template/docs/OBSERVABILITY.md`
- **Analytics**: See `microservice_project_template/docs/ANALYTICS.md`

## 🤝 Contributing

1. **Validate Changes**: Always run `python3 scripts/test_framework.py`
2. **Test Templates**: Ensure `python3 scripts/validate_templates.py` passes
3. **Document Changes**: Update relevant documentation
4. **Follow Patterns**: Maintain consistency with existing templates

## 📄 License

This framework is designed for educational and portfolio demonstration purposes.

## 🚀 Next Steps

1. **Explore Templates**: Browse the `service/` directory to understand available patterns
2. **Generate Services**: Start with `python3 scripts/generate_service.py --help`
3. **Customize Framework**: Adapt templates to your specific needs
4. **Build Projects**: Use the project template for complete applications
5. **Contribute**: Add new templates and improve existing ones

---

**Happy Building! 🎉**

For questions, issues, or contributions, please refer to the project documentation or create an issue in the repository.

### 3. `hybrid_service/` - Combined FastAPI + gRPC Service Template
- Uses HybridServiceConfig for both protocols
- Concurrent server management
- Shared business logic between protocols
- Comprehensive testing for both interfaces
- Advanced configuration patterns

### 4. `minimal_service/` - Minimal Service Template
- Uses BaseServiceConfig only
- Minimal dependencies and structure
- Suitable for utility services or lightweight components

## Usage

Templates use Jinja2 templating with these variables:
- `{{service_name}}` - Service name (e.g., "document-validator")
- `{{service_class}}` - Class name (e.g., "DocumentValidator")
- `{{service_package}}` - Package name (e.g., "document_validator")
- `{{service_description}}` - Service description
- `{{author}}` - Author name
- `{{grpc_port}}` - Default gRPC port
- `{{http_port}}` - Default HTTP port (FastAPI services)

## Generated Structure

Each template generates a complete service with:
- Configuration using DRY base classes
- Main service implementation
- Protobuf definitions (for gRPC services)
- Docker configuration using base patterns
- Testing infrastructure with DRY fixtures
- Documentation and README
- CI/CD integration

## Code Reduction

Using these templates, new services automatically inherit:
- 84% reduction in server setup code (via gRPC Service Factory)
- 70% reduction in configuration code (via Base Configuration Classes)
- 78% reduction in test setup code (via DRY Test Infrastructure)
- 60% reduction in Docker configuration (via Base Images)

New services are production-ready with minimal additional code!
