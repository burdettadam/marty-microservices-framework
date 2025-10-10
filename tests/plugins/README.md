# Plugin System Test Documentation

## Overview

This comprehensive test suite validates the MMF plugin system implementation including core infrastructure, service management, plugin discovery, configuration handling, and the Marty Trust PKI plugin.

## Test Structure

```
tests/plugins/
├── __init__.py              # Test fixtures and common utilities
├── conftest.py             # Pytest configuration and fixtures
├── test_core.py            # Core plugin system tests
├── test_services.py        # Service management tests
├── test_discovery.py       # Plugin discovery tests
├── test_config.py          # Configuration management tests
├── test_marty_plugin.py    # Marty plugin specific tests
├── test_integration.py     # End-to-end integration tests
├── requirements-test.txt   # Test dependencies
├── pyproject.toml         # Test configuration
├── run_tests.sh           # Test execution script
└── README.md              # This documentation
```

## Test Categories

### Unit Tests (`pytest -m unit`)

- **Core Plugin System** (`test_core.py`)
  - Plugin lifecycle management
  - Context creation and injection
  - Plugin metadata handling
  - Manager operations
  - Error handling

- **Service Management** (`test_services.py`)
  - Service definition and registration
  - Service lifecycle and routing
  - Service discovery mechanisms
  - Plugin service integration

- **Discovery System** (`test_discovery.py`)
  - Directory-based plugin discovery
  - Package-based plugin discovery
  - Composite discovery strategies
  - Plugin loading and validation

- **Configuration** (`test_config.py`)
  - Plugin configuration loading
  - Marty-specific configuration
  - Environment-specific settings
  - Configuration validation

- **Marty Plugin** (`test_marty_plugin.py`)
  - Plugin initialization and lifecycle
  - Service integration with MMF infrastructure
  - PKI-specific functionality
  - Trust anchor and certificate operations

### Integration Tests (`pytest -m integration`)

- **Full Plugin Lifecycle** (`test_integration.py`)
  - Plugin discovery to shutdown workflow
  - Service registration and routing
  - MMF infrastructure integration
  - Real workflow testing
  - Error handling and recovery
  - Performance characteristics

## Running Tests

### Prerequisites

1. Python 3.11+ installed
2. uv package manager installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
3. Virtual environment managed by uv
4. Project dependencies installed

### Quick Start

```bash
# Navigate to test directory
cd tests/plugins

# Run all tests
./run_tests.sh

# Run specific test categories
./run_tests.sh --unit
./run_tests.sh --integration
./run_tests.sh --all

# Run with verbose output
./run_tests.sh --verbose

# Run specific test
./run_tests.sh --test test_core
```

### Manual Test Execution

```bash
# Install test dependencies with uv
uv pip install -r requirements-test.txt

# Set Python path
export PYTHONPATH="../../src:$PYTHONPATH"

# Run tests with pytest
pytest -v
pytest -m unit
pytest -m integration
pytest --cov=src/framework/plugins --cov=src/plugins
```

## Test Configuration

### Pytest Configuration (`pyproject.toml`)

- **Coverage**: Tracks code coverage for plugin system
- **Markers**: Categorizes tests (unit, integration, performance, security)
- **Async Support**: Handles async/await test functions
- **Reporting**: Generates HTML and XML coverage reports

### Test Fixtures (`conftest.py`)

- **mock_mmf_services**: Mock MMF infrastructure services
- **test_plugin_directory**: Temporary plugin directory for testing
- **test_config_directory**: Temporary configuration directory
- **plugin_test_data**: Common test data and scenarios

## Test Coverage

The test suite aims for comprehensive coverage of:

- ✅ Plugin lifecycle management (initialize, start, stop)
- ✅ Service registration and discovery
- ✅ Configuration loading and validation
- ✅ MMF infrastructure integration
- ✅ Error handling and recovery
- ✅ Plugin dependency resolution
- ✅ Route mounting and request handling
- ✅ Health checking and monitoring
- ✅ Marty plugin services (Document Signer, Trust Anchor, PKD, Certificate Validation)

## Mock Infrastructure

The test suite uses comprehensive mocks for MMF services:

- **Database Service**: DDL execution, CRUD operations
- **Security Service**: Key management, signing, verification
- **Cache Service**: Get, set, delete, pattern operations
- **Message Bus**: Publish, subscribe, unsubscribe
- **Observability**: Metrics collection, distributed tracing
- **Configuration**: Plugin config loading and management

## Performance Testing

Performance tests validate:

- Plugin startup time (< 5 seconds for initialization)
- Health check response time (< 1 second)
- Concurrent plugin operations
- Memory usage patterns
- Service registration overhead

## Security Testing

Security tests cover:

- Configuration data handling
- Sensitive data masking
- Access control mechanisms
- Certificate validation
- Cryptographic operations

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure PYTHONPATH includes `src` directory
2. **Missing Dependencies**: Run `pip install -r requirements-test.txt`
3. **Async Test Failures**: Check pytest-asyncio configuration
4. **Mock Issues**: Verify mock services are properly configured

### Debug Mode

```bash
# Run tests with debug output
pytest -v -s --tb=long

# Run specific failing test
pytest -v test_core.py::TestPluginLifecycle::test_plugin_initialization

# Run with pdb debugger
pytest --pdb
```

### Coverage Analysis

```bash
# Generate detailed coverage report
pytest --cov=src --cov-report=html --cov-report=term-missing

# View coverage in browser
open htmlcov/index.html
```

## Continuous Integration

The test suite is designed for CI/CD integration:

- **Exit Codes**: Non-zero exit on test failures
- **XML Output**: Compatible with CI reporting systems
- **Coverage Reports**: Integrate with coverage tracking services
- **Parallel Execution**: Supports test parallelization

### CI Configuration Example

```yaml
# GitHub Actions example
- name: Run Plugin Tests
  run: |
    cd tests/plugins
    ./run_tests.sh --all --no-coverage
```

## Test Data

Test data includes:

- Sample plugin manifests and implementations
- Configuration files (JSON, YAML)
- PKI test certificates and keys
- Mock service responses
- Error scenarios and edge cases

## Extending Tests

### Adding New Tests

1. Create test file following naming convention (`test_*.py`)
2. Add appropriate markers (`@pytest.mark.unit`, etc.)
3. Use existing fixtures from `conftest.py`
4. Follow async test patterns for async functionality
5. Add mock data to `plugin_test_data` fixture if needed

### Custom Fixtures

```python
@pytest.fixture
def custom_plugin():
    """Create custom test plugin."""
    # Implementation
    yield plugin
    # Cleanup
```

### Mock Services

```python
def test_custom_service(mock_mmf_services):
    """Test using mock MMF services."""
    # Configure mocks
    mock_mmf_services.database.query_one.return_value = {"id": 1}

    # Test implementation
    # Assertions
```

## Validation Results

The test suite validates that the plugin system:

- ✅ Successfully loads and manages plugins
- ✅ Integrates with MMF infrastructure services
- ✅ Handles configuration correctly
- ✅ Provides service discovery and registration
- ✅ Maintains plugin isolation and error boundaries
- ✅ Supports the Marty Trust PKI plugin migration
- ✅ Meets performance requirements
- ✅ Handles security considerations appropriately

## Next Steps

After successful test execution:

1. Review coverage reports for any gaps
2. Run tests in different environments (dev, staging)
3. Integrate with CI/CD pipeline
4. Monitor test execution time and optimize as needed
5. Add additional test scenarios based on real usage patterns
