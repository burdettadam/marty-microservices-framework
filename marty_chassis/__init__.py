"""
Marty Chassis - Enterprise Microservices Framework

A comprehensive chassis for building enterprise-grade microservices with Python,
providing unified configuration, security, observability, and service creation.

Key Features:
- Unified configuration management (YAML, env vars, runtime overrides)
- Structured logging with correlation IDs and JSON output
- JWT/RBAC security for REST and gRPC services
- Health checks and Prometheus metrics
- Circuit breaker patterns and resilience
- Service factory functions for FastAPI, gRPC, and hybrid services
- REST and gRPC client libraries with built-in retry and auth
- CLI tool for scaffolding new services
- Service mesh integration (Istio/Linkerd)

Usage:
    >>> from marty_chassis import create_fastapi_service, create_grpc_service
    >>> from marty_chassis.config import ChassisConfig
    >>> from marty_chassis.security import JWTAuth, RBACMiddleware

    # Create a FastAPI service with all cross-cutting concerns
    >>> app = create_fastapi_service(
    ...     name="my-service",
    ...     config=ChassisConfig.from_env(),
    ...     enable_auth=True,
    ...     enable_metrics=True
    ... )
"""

__version__ = "0.1.0"
__author__ = "Marty Team"
__email__ = "team@marty.dev"

# Client libraries
from .clients import GRPCClient, HTTPClient

# Configuration system
from .config import ChassisConfig, ConfigManager

# Exceptions
from .exceptions import ChassisError, ConfigurationError, ServiceError, ValidationError

# Core factory functions
from .factories.fastapi_factory import create_fastapi_service
from .factories.grpc_factory import create_grpc_service
from .factories.hexagonal_factory import create_hexagonal_service
from .factories.hybrid_factory import create_hybrid_service

# Health and metrics
from .health import HealthCheck, HealthStatus

# Logging
from .logger import LogConfig, get_logger, setup_logging
from .metrics import MetricsCollector, prometheus_middleware

# Plugin system
from .plugins import (
    CoreServices,
    ExtensionPoint,
    ExtensionPointManager,
    IEventHandlerPlugin,
    IHealthPlugin,
    IMetricsPlugin,
    IMiddlewarePlugin,
    IPlugin,
    IServicePlugin,
    PluginContext,
    PluginEnabledServiceFactory,
    PluginManager,
    PluginMetadata,
    PluginState,
    create_plugin_enabled_fastapi_service,
    event_handler,
    middleware,
    plugin,
    service_hook,
)

# Resilience patterns
from .resilience import BulkheadPattern, CircuitBreaker, RetryPolicy

# Security components
from .security import (
    APIKeyAuth,
    AuthenticationError,
    AuthorizationError,
    JWTAuth,
    RBACMiddleware,
    SecurityConfig,
)
from .service_mesh import ManifestGenerator, ServiceMeshGenerator

# Templates and service mesh
from .templates import ServiceTemplate, TemplateGenerator

__all__ = [
    # Version and metadata
    "__version__",
    "__author__",
    "__email__",
    # Core factory functions
    "create_fastapi_service",
    "create_grpc_service",
    "create_hexagonal_service",
    "create_hybrid_service",
    # Configuration
    "ChassisConfig",
    "ConfigManager",
    # Security
    "JWTAuth",
    "RBACMiddleware",
    "SecurityConfig",
    "APIKeyAuth",
    "AuthenticationError",
    "AuthorizationError",
    # Health and metrics
    "HealthCheck",
    "HealthStatus",
    "MetricsCollector",
    "prometheus_middleware",
    # Resilience
    "CircuitBreaker",
    "RetryPolicy",
    "BulkheadPattern",
    # Clients
    "HTTPClient",
    "GRPCClient",
    # Templates and service mesh
    "TemplateGenerator",
    "ServiceTemplate",
    "ManifestGenerator",
    "ServiceMeshGenerator",
    # Logging
    "setup_logging",
    "get_logger",
    "LogConfig",
    # Exceptions
    "ChassisError",
    "ConfigurationError",
    "ServiceError",
    "ValidationError",
    # Plugin system
    "IPlugin",
    "IServicePlugin",
    "IMiddlewarePlugin",
    "IEventHandlerPlugin",
    "IHealthPlugin",
    "IMetricsPlugin",
    "PluginManager",
    "PluginContext",
    "PluginMetadata",
    "PluginState",
    "CoreServices",
    "ExtensionPointManager",
    "ExtensionPoint",
    "plugin",
    "service_hook",
    "middleware",
    "event_handler",
]
