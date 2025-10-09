# Marty Chassis

A comprehensive chassis for building enterprise-grade microservices with Python. The Marty Chassis provides a unified framework that encapsulates common cross-cutting concerns and eliminates code duplication across microservices.

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-beta-orange)

## Features

- 🚀 **Service Factories**: Create FastAPI, gRPC, or hybrid services with a single function call
- ⚙️ **Configuration Management**: Unified YAML/environment variable configuration system
- 🔐 **Security**: Built-in JWT authentication, RBAC, and API key support
- 📊 **Observability**: Structured logging, Prometheus metrics, and health checks
- 🛡️ **Resilience**: Circuit breakers, retry policies, and bulkhead patterns
- 🌐 **Service Mesh**: Generate Istio and Linkerd manifests automatically
- 🏗️ **Scaffolding**: CLI tool to generate new services from templates
- 📦 **Client Libraries**: HTTP and gRPC clients with built-in resilience
- 🔧 **Development Tools**: Hot reload, debugging support, and developer experience

## Quick Start

### Installation

```bash
pip install marty-chassis
```

### Create Your First Service

```bash
# Create a new FastAPI service
marty-chassis new-service my-api fastapi

# Create a gRPC service
marty-chassis new-service my-grpc-service grpc

# Create a hybrid service (both REST and gRPC)
marty-chassis new-service my-hybrid-service hybrid
```

### Basic Usage

```python
from marty_chassis import create_fastapi_service, ChassisConfig

# Load configuration
config = ChassisConfig.from_env()

# Create a FastAPI service with all cross-cutting concerns
app = create_fastapi_service(config)

# Your service-specific routes
@app.get("/hello")
async def hello():
    return {"message": "Hello from Marty Chassis!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Architecture

The Marty Chassis is built around several core principles:

1. **Convention over Configuration**: Sensible defaults with easy customization
2. **Dependency Injection**: Cross-cutting concerns are injected automatically
3. **Observability First**: Built-in logging, metrics, and health checks
4. **Security by Design**: Authentication and authorization built-in
5. **Cloud Native**: Kubernetes and service mesh ready

### Core Components

```
marty_chassis/
├── config/          # Configuration management
├── security/        # Authentication & authorization
├── logging/         # Structured logging
├── health/          # Health checks
├── metrics/         # Prometheus metrics
├── resilience/      # Circuit breakers & retry
├── factories/       # Service creation
├── clients/         # HTTP & gRPC clients
├── templates/       # Service scaffolding
├── service_mesh/    # Istio/Linkerd manifests
└── cli/            # Command-line tools
```

## Configuration

The chassis uses a unified configuration system that supports both YAML files and environment variables.

### Configuration File (`config.yaml`)

```yaml
environment: development

service:
  name: my-service
  version: 1.0.0
  host: 0.0.0.0
  port: 8000

security:
  jwt_secret: your-secret-key
  jwt_algorithm: HS256
  token_expires_minutes: 30
  enable_rbac: true

observability:
  log_level: INFO
  enable_metrics: true
  metrics_port: 8000

resilience:
  circuit_breaker:
    failure_threshold: 5
    timeout_seconds: 60
  retry_policy:
    max_attempts: 3
    backoff_multiplier: 2.0
```

### Environment Variables

All configuration can be overridden with environment variables:

```bash
export CHASSIS_ENVIRONMENT=production
export CHASSIS_SERVICE__PORT=8080
export CHASSIS_SECURITY__JWT_SECRET=your-production-secret
export CHASSIS_OBSERVABILITY__LOG_LEVEL=WARNING
```

## Service Types

### FastAPI Service

```python
from marty_chassis import create_fastapi_service

app = create_fastapi_service()

@app.get("/api/v1/users")
async def get_users():
    return {"users": []}
```

### gRPC Service

```python
from marty_chassis import create_grpc_service
import my_service_pb2_grpc

class MyServiceImpl(my_service_pb2_grpc.MyServiceServicer):
    async def GetData(self, request, context):
        # Your gRPC implementation
        pass

server = create_grpc_service()
my_service_pb2_grpc.add_MyServiceServicer_to_server(MyServiceImpl(), server)
```

### Hybrid Service

```python
from marty_chassis import create_hybrid_service

# Returns both FastAPI app and gRPC server
app, grpc_server = create_hybrid_service()

# Add REST endpoints to app
@app.get("/health")
async def health():
    return {"status": "healthy"}

# Add gRPC services to grpc_server
```

## Security

### JWT Authentication

```python
from marty_chassis.security import JWTAuth

auth = JWTAuth()

# Protect endpoints
@app.get("/protected")
@auth.require_auth
async def protected_endpoint(current_user: dict):
    return {"user": current_user}
```

### Role-Based Access Control (RBAC)

```python
from marty_chassis.security import RBACMiddleware

# Require specific roles
@app.get("/admin-only")
@auth.require_roles(["admin"])
async def admin_endpoint():
    return {"message": "Admin access granted"}
```

## Observability

### Structured Logging

```python
from marty_chassis.logging import get_logger

logger = get_logger(__name__)

logger.info("User login", user_id="12345", ip_address="192.168.1.1")
logger.error("Database error", error="Connection timeout", operation="user_fetch")
```

### Metrics

```python
from marty_chassis.metrics import MetricsCollector

metrics = MetricsCollector()

# Custom metrics
metrics.counter("custom_operations_total").inc()
metrics.histogram("operation_duration_seconds").observe(0.5)
metrics.gauge("queue_size").set(42)
```

### Health Checks

```python
from marty_chassis.health import HealthCheck

health = HealthCheck()

@health.register("database")
async def check_database():
    # Your database health check
    return True

@health.register("external_api")
async def check_external_api():
    # Check external dependencies
    return True
```

## Resilience Patterns

### Circuit Breaker

```python
from marty_chassis.resilience import CircuitBreaker

circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    timeout_seconds=60
)

@circuit_breaker.protected
async def external_api_call():
    # This call is protected by the circuit breaker
    pass
```

### Retry Policy

```python
from marty_chassis.resilience import RetryPolicy

retry_policy = RetryPolicy(
    max_attempts=3,
    backoff_multiplier=2.0
)

@retry_policy.retry
async def unreliable_operation():
    # This operation will be retried on failure
    pass
```

## Client Libraries

### HTTP Client

```python
from marty_chassis.clients import HTTPClient

async with HTTPClient("https://api.example.com") as client:
    # Built-in retry and circuit breaker
    response = await client.get("/users")
    data = await response.json()
```

### gRPC Client

```python
from marty_chassis.clients import GRPCClient

async with GRPCClient("grpc-service:50051") as client:
    # Built-in load balancing and retry
    stub = MyServiceStub(client.channel)
    response = await stub.GetData(request)
```

## CLI Tool

The `marty-chassis` CLI provides powerful scaffolding and management tools.

### New Service

```bash
# Interactive mode
marty-chassis new-service my-service fastapi --interactive

# With options
marty-chassis new-service my-api fastapi \
  --output-dir ./services \
  --service-mesh istio \
  --no-tests

# Available service types
marty-chassis new-service my-service [fastapi|grpc|hybrid]
```

### Service Mesh Integration

```bash
# Generate Istio manifests
marty-chassis new-service my-service fastapi --service-mesh istio

# Generate Linkerd manifests
marty-chassis new-service my-service fastapi --service-mesh linkerd

# Skip service mesh
marty-chassis new-service my-service fastapi --service-mesh none
```

### Run Service

```bash
# Run with auto-reload (development)
marty-chassis run --reload

# Production mode
marty-chassis run --host 0.0.0.0 --port 8000

# With custom config
marty-chassis run --config-file production.yaml
```

### Service Information

```bash
# Show service status
marty-chassis status

# Generate config template
marty-chassis config --generate
```

## Service Mesh Support

The chassis automatically generates Kubernetes manifests and service mesh configurations.

### Generated Files

When you create a service with `--service-mesh istio`, you get:

```
my-service/
├── k8s/
│   ├── istio/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── virtualservice.yaml
│   │   ├── destinationrule.yaml
│   │   └── authorizationpolicy.yaml
│   └── monitoring/
│       ├── servicemonitor.yaml
│       └── prometheusrule.yaml
└── src/
    └── my_service/
        ├── main.py
        ├── config.yaml
        └── ...
```

### Istio Features

- **Traffic Management**: VirtualService with routing, retries, and timeouts
- **Security**: AuthorizationPolicy with RBAC
- **Observability**: Distributed tracing and metrics
- **Resilience**: Circuit breakers and load balancing

### Linkerd Features

- **Traffic Splitting**: Canary deployments and A/B testing
- **Service Profiles**: Route-based metrics and policies
- **Automatic mTLS**: Secure service-to-service communication
- **Traffic Policies**: Retry budgets and timeouts

## Templates

The chassis includes built-in templates for common service patterns.

### Built-in Templates

- **FastAPI Service**: REST API with OpenAPI documentation
- **gRPC Service**: Protocol buffer-based RPC service
- **Hybrid Service**: Combined REST and gRPC endpoints
- **Background Worker**: Celery-based task processing
- **Event Processor**: Event-driven service with Kafka/RabbitMQ

### Custom Templates

```python
from marty_chassis.templates import TemplateGenerator

generator = TemplateGenerator()

# Use custom template
generator.generate_service(
    service_name="my-service",
    service_type="fastapi",
    output_dir="./output",
    custom_template="./my-template"
)
```

## Development

### Setup Development Environment

```bash
git clone https://github.com/marty-team/marty-chassis
cd marty-chassis
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

### Code Quality

```bash
# Linting
ruff check .

# Type checking
mypy marty_chassis/

# Formatting
black marty_chassis/
```

## Examples

### Microservice with Authentication

```python
from marty_chassis import create_fastapi_service, ChassisConfig
from marty_chassis.security import JWTAuth

config = ChassisConfig.from_env()
app = create_fastapi_service(config)
auth = JWTAuth()

@app.post("/login")
async def login(credentials: dict):
    # Validate credentials
    if valid_credentials(credentials):
        token = auth.create_access_token({"sub": credentials["username"]})
        return {"access_token": token}
    raise HTTPException(401, "Invalid credentials")

@app.get("/profile")
@auth.require_auth
async def get_profile(current_user: dict):
    return {"user": current_user}
```

### Service with External Dependencies

```python
from marty_chassis import create_fastapi_service
from marty_chassis.clients import HTTPClient
from marty_chassis.resilience import CircuitBreaker

app = create_fastapi_service()
circuit_breaker = CircuitBreaker(failure_threshold=3)

@app.get("/external-data")
@circuit_breaker.protected
async def get_external_data():
    async with HTTPClient("https://api.external.com") as client:
        response = await client.get("/data")
        return await response.json()
```

### Event-Driven Service

```python
from marty_chassis import create_fastapi_service
from marty_chassis.logging import get_logger

app = create_fastapi_service()
logger = get_logger(__name__)

@app.post("/events")
async def handle_event(event: dict):
    logger.info("Event received", event_type=event.get("type"))

    # Process event
    await process_event(event)

    return {"status": "processed"}
```

## Best Practices

### Configuration

1. **Use environment-specific configs**: Separate configs for dev/test/prod
2. **Leverage environment variables**: Override sensitive values via env vars
3. **Validate configuration**: Use Pydantic models for validation
4. **Document config options**: Include comments in YAML files

### Security

1. **Always use HTTPS in production**: Configure TLS properly
2. **Rotate JWT secrets regularly**: Use strong, unique secrets
3. **Implement proper RBAC**: Define granular permissions
4. **Validate all inputs**: Use Pydantic models for request validation

### Observability

1. **Use structured logging**: Include correlation IDs and context
2. **Define SLIs/SLOs**: Monitor error rates, latency, and availability
3. **Create meaningful alerts**: Alert on business metrics, not just infrastructure
4. **Implement health checks**: Check all dependencies

### Resilience

1. **Implement circuit breakers**: Protect against cascading failures
2. **Use retry with backoff**: Avoid overwhelming downstream services
3. **Set proper timeouts**: Don't wait indefinitely for responses
4. **Design for failure**: Assume dependencies will fail

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- 📖 **Documentation**: [https://marty-chassis.readthedocs.io](https://marty-chassis.readthedocs.io)
- 🐛 **Issues**: [GitHub Issues](https://github.com/marty-team/marty-chassis/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/marty-team/marty-chassis/discussions)
- 📧 **Email**: team@marty.dev

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a list of changes.
