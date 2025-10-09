"""
FastAPI service factory for the Marty Chassis.

This module provides factory functions to create FastAPI applications with
all cross-cutting concerns automatically configured.
"""

from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from ..config import ChassisConfig
from ..health import HealthManager, get_health_manager, setup_default_health_checks
from ..logger import LogConfig, get_logger, init_global_logger, set_correlation_id
from ..metrics import (
    MetricsCollector,
    get_metrics_response,
    init_metrics,
    prometheus_middleware,
)
from ..security import JWTAuth, RBACMiddleware, SecurityMiddleware

logger = get_logger(__name__)


def create_fastapi_service(
    name: str,
    config: Optional[ChassisConfig] = None,
    enable_auth: bool = True,
    enable_metrics: bool = True,
    enable_health_checks: bool = True,
    enable_cors: bool = True,
    trusted_hosts: Optional[List[str]] = None,
    custom_middleware: Optional[List[Any]] = None,
) -> FastAPI:
    """
    Create a FastAPI application with all chassis features enabled.

    Args:
        name: Service name
        config: Chassis configuration (loads from env if not provided)
        enable_auth: Enable JWT/API key authentication
        enable_metrics: Enable Prometheus metrics
        enable_health_checks: Enable health check endpoints
        enable_cors: Enable CORS middleware
        trusted_hosts: List of trusted host patterns
        custom_middleware: Additional middleware to add

    Returns:
        Configured FastAPI application
    """
    if config is None:
        config = ChassisConfig.from_env()

    # Initialize logging
    log_config = LogConfig(
        service_name=name,
        service_version=config.service.version,
        level=config.observability.log_level,
        format_type=config.observability.log_format,
    )
    init_global_logger(log_config)

    logger.info("Creating FastAPI service", service_name=name)

    # Create FastAPI app
    app = FastAPI(
        title=config.service.name or name,
        description=config.service.description,
        version=config.service.version,
        debug=config.service.debug,
        docs_url="/docs" if config.service.debug else None,
        redoc_url="/redoc" if config.service.debug else None,
    )

    # Add trusted hosts middleware
    if trusted_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

    # Add CORS middleware
    if enable_cors and config.security.enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.security.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Initialize metrics
    if enable_metrics and config.observability.enable_metrics:
        metrics_collector = init_metrics(name, config.service.version)

        # Add metrics middleware
        @app.middleware("http")
        async def metrics_middleware(request: Request, call_next):
            middleware = prometheus_middleware(metrics_collector)
            return await middleware(request, call_next)

        # Add metrics endpoint
        @app.get("/metrics", include_in_schema=False)
        async def metrics_endpoint():
            return get_metrics_response()

        logger.info("Metrics enabled", endpoint="/metrics")

    # Initialize security
    security_middleware = None
    if enable_auth:
        jwt_auth = JWTAuth(config.security)
        rbac = RBACMiddleware()
        security_middleware = SecurityMiddleware(jwt_auth=jwt_auth, rbac=rbac)

        # Add security middleware
        @app.middleware("http")
        async def auth_middleware(request: Request, call_next):
            # Set correlation ID for request tracking
            correlation_id = request.headers.get("X-Correlation-ID")
            set_correlation_id(correlation_id)

            # Continue with request
            response = await call_next(request)

            # Add correlation ID to response
            if correlation_id:
                response.headers["X-Correlation-ID"] = correlation_id

            return response

        logger.info("Authentication enabled")

    # Initialize health checks
    if enable_health_checks:
        health_manager = get_health_manager()
        setup_default_health_checks()

        @app.get("/health", include_in_schema=False)
        async def health_endpoint():
            """Health check endpoint."""
            status = await health_manager.get_health_status()
            status_code = 200 if status["status"] == "healthy" else 503
            return Response(
                content=str(status),
                status_code=status_code,
                media_type="application/json",
            )

        @app.get("/health/ready", include_in_schema=False)
        async def readiness_endpoint():
            """Readiness check endpoint."""
            status = await health_manager.get_readiness_status()
            status_code = 200 if status["status"] == "healthy" else 503
            return Response(
                content=str(status),
                status_code=status_code,
                media_type="application/json",
            )

        @app.get("/health/live", include_in_schema=False)
        async def liveness_endpoint():
            """Liveness check endpoint."""
            status = await health_manager.get_liveness_status()
            return Response(
                content=str(status),
                status_code=200,
                media_type="application/json",
            )

        logger.info(
            "Health checks enabled",
            endpoints=["/health", "/health/ready", "/health/live"],
        )

    # Add custom middleware
    if custom_middleware:
        for middleware in custom_middleware:
            app.add_middleware(middleware)
        logger.info(f"Added {len(custom_middleware)} custom middleware")

    # Store configuration and security middleware for access by routes
    app.state.config = config
    app.state.security_middleware = security_middleware

    logger.info("FastAPI service created successfully", service_name=name)

    return app


def add_security_to_app(
    app: FastAPI,
    jwt_auth: JWTAuth,
    rbac: Optional[RBACMiddleware] = None,
) -> SecurityMiddleware:
    """
    Add security middleware to an existing FastAPI app.

    Args:
        app: FastAPI application
        jwt_auth: JWT authentication handler
        rbac: RBAC middleware (optional)

    Returns:
        SecurityMiddleware instance
    """
    security_middleware = SecurityMiddleware(jwt_auth=jwt_auth, rbac=rbac)
    app.state.security_middleware = security_middleware

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        # Set correlation ID for request tracking
        correlation_id = request.headers.get("X-Correlation-ID")
        set_correlation_id(correlation_id)

        # Continue with request
        response = await call_next(request)

        # Add correlation ID to response
        if correlation_id:
            response.headers["X-Correlation-ID"] = correlation_id

        return response

    logger.info("Security middleware added to FastAPI app")
    return security_middleware


def add_metrics_to_app(
    app: FastAPI, service_name: str, service_version: str = "1.0.0"
) -> MetricsCollector:
    """
    Add metrics collection to an existing FastAPI app.

    Args:
        app: FastAPI application
        service_name: Service name for metrics
        service_version: Service version

    Returns:
        MetricsCollector instance
    """
    metrics_collector = init_metrics(service_name, service_version)

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        middleware = prometheus_middleware(metrics_collector)
        return await middleware(request, call_next)

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint():
        return get_metrics_response()

    logger.info("Metrics middleware added to FastAPI app")
    return metrics_collector


def add_health_checks_to_app(app: FastAPI) -> HealthManager:
    """
    Add health check endpoints to an existing FastAPI app.

    Args:
        app: FastAPI application

    Returns:
        HealthManager instance
    """
    health_manager = get_health_manager()
    setup_default_health_checks()

    @app.get("/health", include_in_schema=False)
    async def health_endpoint():
        """Health check endpoint."""
        status = await health_manager.get_health_status()
        status_code = 200 if status["status"] == "healthy" else 503
        return Response(
            content=str(status),
            status_code=status_code,
            media_type="application/json",
        )

    @app.get("/health/ready", include_in_schema=False)
    async def readiness_endpoint():
        """Readiness check endpoint."""
        status = await health_manager.get_readiness_status()
        status_code = 200 if status["status"] == "healthy" else 503
        return Response(
            content=str(status),
            status_code=status_code,
            media_type="application/json",
        )

    @app.get("/health/live", include_in_schema=False)
    async def liveness_endpoint():
        """Liveness check endpoint."""
        status = await health_manager.get_liveness_status()
        return Response(
            content=str(status),
            status_code=200,
            media_type="application/json",
        )

    logger.info("Health check endpoints added to FastAPI app")
    return health_manager
