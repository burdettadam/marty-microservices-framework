# Marty Microservices Framework

A comprehensive, production-ready framework for building enterprise-grade microservices with Python, FastAPI, gRPC, and modern development practices.

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

# Create a complete project
make new NAME=my-awesome-project
cd my-awesome-project
make dev
```

## 🏪 Store Demo - Complete Microservices Example

Experience a full e-commerce microservices demo with realistic load testing:

```bash
# Quick start with Docker Compose
cd examples/store-demo
docker compose up -d
docker compose exec demo-runner python /app/mmf_demo_runner.py

# View results at:
# - Reports: ./reports/ (JSON + text files)
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000
```

**What's included:**
- 🛒 **Order Service** - Order processing with audit logging
- 💳 **Payment Service** - Payment processing with fraud detection
- 📦 **Inventory Service** - Stock management and reservations
- 📊 **Analytics** - Performance monitoring and bottleneck analysis
- 🎯 **Load Testing** - Realistic failure scenarios (63-70% success rate)

➡️ **[Complete Store Demo Guide](docs/STORE_DEMO.md)**

## 🧪 Testing

```bash
# Run all tests
make test

# Run specific test types
make test-unit           # Unit tests only
make test-integration    # Integration tests
make test-kind          # Kubernetes E2E tests
```

## 🎯 What's Included

- **🏗️ Service Templates** - Pre-built FastAPI, gRPC, and hybrid service templates
- **⚡ Code Generation** - Automated service scaffolding with `make generate`
- **🛡️ Enterprise Security** - Authentication, authorization, rate limiting, audit logging
- **📊 Observability** - Monitoring, tracing, metrics, and health checks
- **🔧 Plugin System** - Extensible architecture with plugin management
- **🧪 Testing Framework** - Comprehensive testing utilities and patterns
- **📦 Project Templates** - Complete project structure with best practices

## 📚 Documentation

- **[Architecture Overview](docs/architecture.md)** - Comprehensive framework architecture
- **[Complete Documentation](docs/README.md)** - Full documentation index
- **[CLI Guide](docs/guides/CLI_README.md)** - Command-line usage ([Quick Reference](CLI_README.md))
- **[Migration Guide](docs/guides/MIGRATION_GUIDE.md)** - Migrating existing services
- **[Plugin System](docs/guides/plugin-system.md)** - Plugin development
- **[Observability](docs/guides/observability.md)** - Monitoring setup

## 🛠️ Common Commands

```bash
# Local Development Environment
make kind-up             # Start local Kubernetes + observability stack
make kind-status         # Check cluster status
make kind-logs           # View service logs
make kind-down           # Stop cluster

# Development
make dev                 # Setup development environment
make check               # Run all code quality checks
make fix                 # Fix formatting and linting issues

# Testing
make test                # Run all tests
make test-coverage       # Run tests with coverage report
make test-quick          # Fast tests with fail-fast

# Generation
make generate TYPE=fastapi NAME=user-service
make generate TYPE=grpc NAME=data-processor
make new NAME=payment-system

# Utilities
make clean               # Clean build artifacts
make docs                # Show documentation links
make status              # Show framework status
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `make test`
5. Run quality checks: `make check`
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Documentation**: [docs/README.md](docs/README.md)
- **Development Scripts**: [scripts/README.md](scripts/README.md)
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions

---

**Ready to build amazing microservices?** Start with `make setup` and `make docs`! 🚀
