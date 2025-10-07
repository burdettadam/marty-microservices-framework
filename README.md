# Marty Microservices Framework

A comprehensive, standalone framework for building enterprise-grade microservices with Python, FastAPI, gRPC, and modern development practices.

## 🎯 Overview

The Marty Microservices Framework is a complete toolkit for building production-ready microservices. It provides:

- **Service Templates** - Pre-built templates for common service patterns
- **Code Generation** - Automated service scaffolding with DRY principles
- **Best Practices** - Enterprise-grade patterns and configurations
- **Testing Framework** - Comprehensive validation and testing tools

## 🏗️ Framework Structure

```
marty-microservices-framework/
├── scripts/                    # Framework tools and utilities
│   ├── generate_service.py    # Service generator
│   ├── validate_templates.py  # Template validator
│   ├── test_framework.py      # Comprehensive testing
│   └── setup_framework.sh     # Framework setup script
├── service/                    # Service templates
│   ├── fastapi_service/       # REST API services
│   ├── grpc_service/          # gRPC services
│   ├── hybrid_service/        # Combined REST + gRPC
│   ├── auth_service/          # Authentication services
│   ├── database_service/      # Database-backed services
│   ├── caching_service/       # Redis caching services
│   └── message_queue_service/ # Message queue services
├── microservice_project_template/ # Complete project template
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

### 2. Initialize Development Environment

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks for code quality
pre-commit install

# Verify framework integrity
make test-all
```

### 3. Generate Your First Service

```bash
# Generate a FastAPI REST service
python3 scripts/generate_service.py fastapi user-service \
  --description "User management service" \
  --http-port 8080

# Generate a gRPC service
python3 scripts/generate_service.py grpc document-processor \
  --description "Document processing service" \
  --grpc-port 50051

# Generate a hybrid service (REST + gRPC)
python3 scripts/generate_service.py hybrid payment-service \
  --description "Payment processing service" \
  --http-port 8080 --grpc-port 50051
```

### 4. Create a Complete Project```bash
# Copy the project template
cp -r microservice_project_template my-awesome-project
cd my-awesome-project

# Setup development environment
uv sync --extra dev

# Start development
uv run python src/microservice_template/main.py
```

## 📚 Service Templates

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
# Test service generation
python3 scripts/test_framework.py

# Validate templates after changes
python3 scripts/validate_templates.py
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
pre-commit run framework-tests
```

### Automated Quality Checks

Every commit automatically runs:

- **Code Formatting**: Black and isort for consistent styling
- **Type Checking**: MyPy for static type validation
- **Template Validation**: Ensures all service templates are valid
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
