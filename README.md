# Marty Microservices Framework

A comprehensive, production-ready framework for building enterprise-grade microservices with Python, FastAPI, gRPC, and modern development practices.

## 📁 Project Structure

```
.
├── README.md
├── Makefile
├── pyproject.toml
├── docs/                       # Documentation
│   ├── guides/                 # Development guides
│   ├── architecture/           # Architecture documentation
│   └── demos/                  # Demo documentation & quickstarts
├── src/                        # Source code
│   └── marty_msf/              # Main framework package
│       ├── framework/          # Core framework modules
│       ├── cli/                # Command-line interface
│       ├── security/           # Security modules
│       └── observability/      # Monitoring & observability
├── services/                   # Service templates & examples
│   ├── fastapi/                # FastAPI service templates
│   ├── grpc/                   # gRPC service templates
│   ├── hybrid/                 # Hybrid service templates
│   └── shared/                 # Shared service components & Jinja assets
├── examples/                   # Usage examples
│   ├── demos/                  # Demo applications
│   │   ├── order-service/      # Order service demo
│   │   ├── payment-service/    # Payment service demo
│   │   ├── inventory-service/  # Inventory service demo
│   │   └── runner/             # Demo runner scripts
│   └── notebooks/              # Jupyter notebooks for tutorials
├── ops/                        # Operations & deployment
│   ├── k8s/                    # Kubernetes manifests
│   ├── service-mesh/           # Service mesh configuration
│   ├── dashboards/             # Monitoring dashboards
│   └── ci-cd/                  # CI/CD pipelines
├── scripts/                    # Utility scripts
│   ├── dev/                    # Development scripts
│   └── tooling/                # Build & maintenance tools
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   ├── e2e/                    # End-to-end tests
│   └── quality/                # Code quality & lint tests
├── tools/                      # Development tools
│   └── scaffolding/            # Project generators & templates
└── var/                        # Runtime files (gitignored logs, pids, reports)
```

## 🚀 Quick Start - Local Development Environment

### Get Started in 2 Minutes!

```bash
# 1. Clone and setup
git clone https://github.com/your-org/marty-microservices-framework.git
cd marty-microservices-framework
make setup

# 2. Start local Kubernetes cluster with full observability stack
make kind-up
```

**That's it!** You now have a complete local development environment running:

- 🎯 **Prometheus**: http://localhost:9090 (metrics & monitoring)
- 📊 **Grafana**: http://localhost:3000 (dashboards - login: admin/admin)
- ☸️ **Kubernetes cluster**: Full local cluster for development
- 🔍 **Complete observability stack**: Logging, metrics, tracing

### Other Development Commands

```bash
# Check cluster status
make kind-status

# View logs
make kind-logs

# Stop the cluster
make kind-down

# Restart everything
make kind-restart
```

## 🛠️ Create Your First Service

```bash
# Generate a FastAPI service
make generate TYPE=fastapi NAME=my-api

# Generate a gRPC service
make generate TYPE=grpc NAME=my-grpc-service

# Generate a hybrid service (FastAPI + gRPC)
make generate TYPE=hybrid NAME=my-hybrid-service
```

## 📚 Framework Components

### Core Framework (`src/marty_msf/framework/`)
- **API Gateway**: Intelligent routing and load balancing
- **Service Discovery**: Consul-based service registration
- **Configuration Management**: Centralized config with hot-reload
- **Event Streaming**: Kafka integration for messaging
- **Database Integration**: Multi-database support with connection pooling
- **Caching**: Redis-based distributed caching
- **Performance Monitoring**: Real-time metrics and profiling

### CLI Tools (`src/marty_msf/cli/`)
- Project scaffolding and code generation
- Service templates and boilerplate
- Dependency management
- Docker and Kubernetes deployment automation
- Configuration validation and management

### Security (`src/marty_msf/security/`)
- JWT-based authentication and authorization
- OAuth2 and OpenID Connect integration
- Rate limiting and DDoS protection
- Zero-trust networking components
- Certificate management

### Observability (`src/marty_msf/observability/`)
- Prometheus metrics collection
- Grafana dashboard templates
- Distributed tracing with Jaeger
- Structured logging
- Performance analytics and alerting

## 🎯 Running Demo Applications

The framework includes several demo applications to showcase different patterns:

```bash
# Run the complete store demo (order, payment, inventory services)
cd examples/demos/runner
./start_demo.sh

# Stop the demo
./stop_demo.sh
```

### Demo Services:
- **Order Service**: Handles order processing and workflow
- **Payment Service**: Manages payment processing and transactions
- **Inventory Service**: Tracks inventory levels and stock management

## 🧪 Testing

The framework includes comprehensive testing at multiple levels:

```bash
# Run unit tests
make test-unit

# Run integration tests
make test-integration

# Run end-to-end tests
make test-e2e

# Run all tests with coverage
make test-all
```

## 📖 Documentation

- **[Architecture Guide](docs/architecture/)**: System design and patterns
- **[Development Guides](docs/guides/)**: Setup and development workflows
- **[Demo Documentation](docs/demos/)**: Tutorial walkthroughs
- **[API Reference](docs/api/)**: Complete API documentation

## 🛠️ Development

### Prerequisites
- Python 3.10+
- Docker & Docker Compose
- kubectl
- Make

### Development Setup
```bash
# Install development dependencies
make install-dev

# Set up pre-commit hooks
make setup-hooks

# Run code quality checks
make lint

# Run security scans
make security
```

## 🚢 Deployment

The framework supports multiple deployment targets:

```bash
# Deploy to local Kubernetes
make deploy-local

# Deploy to staging
make deploy-staging

# Deploy to production
make deploy-prod
```

## 📋 License

MIT License - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📞 Support

- 📧 Email: team@marty-msf.com
- 🐛 Issues: [GitHub Issues](https://github.com/marty-framework/marty-microservices-framework/issues)
- 📖 Documentation: [marty-msf.readthedocs.io](https://marty-msf.readthedocs.io)
