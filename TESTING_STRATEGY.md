# MMF Testing Strategy

## Overview

This document outlines the comprehensive testing strategy for the Marty Microservices Framework (MMF), emphasizing consistency, minimal mocking, and comprehensive coverage across all components.

## Testing Philosophy

### Core Principles

1. **Real Over Mock**: Test with real implementations whenever possible. Use mocking only for external dependencies that cannot be easily controlled (external APIs, slow databases in unit tests).

2. **Test Pyramid**: Follow the testing pyramid principle:
   - **Unit Tests (70%)**: Fast, isolated tests for individual components
   - **Integration Tests (20%)**: Test component interactions with real dependencies
   - **E2E Tests (10%)**: Full workflow validation

3. **Consistency**: Use standardized patterns, fixtures, and utilities across all test modules.

4. **Fast Feedback**: Tests should run quickly and provide clear, actionable feedback.

## Test Structure

```
tests/
├── conftest.py                 # Global fixtures and configuration
├── unit/                       # Unit tests (isolated component testing)
│   ├── conftest.py            # Unit test specific fixtures
│   ├── framework/             # Framework component tests
│   │   ├── test_config.py
│   │   ├── test_messaging.py
│   │   └── ...
│   └── utils/                 # Utility function tests
├── integration/               # Integration tests (component interactions)
│   ├── conftest.py            # Integration test fixtures
│   ├── test_event_bus.py      # Real event bus with embedded Kafka
│   ├── test_database.py       # Real database interactions
│   └── test_service_mesh.py   # Service discovery and mesh
├── e2e/                       # End-to-end tests (full workflows)
│   ├── conftest.py            # E2E test fixtures
│   ├── test_service_lifecycle.py
│   └── test_deployment.py
├── fixtures/                  # Shared test fixtures and data
│   ├── __init__.py
│   ├── database.py            # Database setup and teardown
│   ├── events.py              # Event bus setup
│   └── services.py            # Test service instances
└── utils/                     # Testing utilities and helpers
    ├── __init__.py
    ├── assertions.py          # Custom assertions
    ├── containers.py          # Test container management
    └── generators.py          # Test data generators
```

## Testing Guidelines

### Unit Tests
- Test individual components in isolation
- Use real implementations of framework utilities
- Mock only external dependencies (APIs, databases)
- Focus on business logic and edge cases

### Integration Tests
- Test component interactions with real dependencies
- Use embedded databases/message brokers when possible
- Test configuration and dependency injection
- Validate data flow between components

### E2E Tests
- Test complete user workflows
- Use real services in containers
- Validate system behavior under realistic conditions
- Include performance and reliability testing

## Test Utilities

### Custom Assertions
- Framework-specific assertion helpers
- Async operation validators
- Event verification utilities

### Test Containers
- Embedded Kafka for event testing
- In-memory databases for fast tests
- Redis containers for caching tests

### Data Generators
- Realistic test data creation
- Event payload generators
- Configuration builders

## Coverage Goals

- **Overall Coverage**: Minimum 85%
- **Critical Paths**: 95% coverage for core framework components
- **Business Logic**: 90% coverage for service implementations
- **Integration Points**: 80% coverage for external integrations

## Running Tests

```bash
# All tests
uv run pytest

# Unit tests only
uv run pytest tests/unit/

# Integration tests
uv run pytest tests/integration/

# E2E tests
uv run pytest tests/e2e/

# With coverage
uv run pytest --cov=src/ --cov-report=html --cov-report=term

# Performance tests
uv run pytest tests/e2e/ -m performance

# Specific component
uv run pytest tests/unit/framework/test_messaging.py -v
```

## Continuous Integration

Tests are organized to support different CI stages:

1. **Fast Tests**: Unit tests run on every commit
2. **Integration Tests**: Run on PR creation
3. **E2E Tests**: Run on main branch and releases
4. **Performance Tests**: Scheduled runs and release validation

## Best Practices

1. **Test Naming**: Use descriptive test names that explain the scenario
2. **Test Data**: Use realistic test data, avoid magic numbers
3. **Cleanup**: Ensure proper cleanup in teardown methods
4. **Isolation**: Tests should not depend on each other
5. **Documentation**: Document complex test scenarios
6. **Maintenance**: Keep tests updated with code changes
