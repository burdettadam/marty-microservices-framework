"""
Order processing and workflow management service

This is a FastAPI service generated with enterprise infrastructure:
- OpenTelemetry distributed tracing
- Comprehensive health monitoring and metrics
- Repository pattern for data access
- Event-driven architecture
- Structured configuration management
"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from framework.config import BaseServiceConfig
from observability import auto_instrument, init_tracing, instrument_fastapi
from observability.monitoring import ServiceMonitor

from .routes import router


class OrderServiceConfig(BaseServiceConfig):
    """Configuration for order-service service."""

    service_name: str = "order-service"
    host: str = "0.0.0.0"
    port: int = 8001
    debug: bool = False
    docs_enabled: bool = True



# Global references
config = OrderServiceConfig()
monitor: ServiceMonitor = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan with proper startup and shutdown."""
    global monitor
    # Startup
    print(f"Starting {config.service_name} with enterprise infrastructure...")

    # Initialize observability
    init_tracing(service_name=config.service_name)
    auto_instrument()
    instrument_fastapi()


    # Start monitoring
    monitor = ServiceMonitor(config.service_name)
    monitor.start_monitoring()
    app.state.monitor = monitor

    print(f"{config.service_name} started successfully")

    yield

    # Shutdown
    print(f"Shutting down {config.service_name}...")

    if monitor:
        monitor.stop_monitoring()


    print(f"{config.service_name} shutdown complete")


def create_app() -> FastAPI:
    """
    Create FastAPI application with enterprise infrastructure.

    This sets up:
    - Distributed tracing and observability
    - Health monitoring and metrics
    - Database access with repository pattern
    - Event-driven architecture
    - Comprehensive error handling
    """

    # Initialize FastAPI with enterprise configuration
    app = FastAPI(
        title=config.service_name.replace("_", " ").title(),
        description="Order processing and workflow management service",
        version="1.0.0",
        debug=config.debug,
        docs_url="/docs" if config.docs_enabled else None,
        redoc_url="/redoc" if config.docs_enabled else None,
        lifespan=lifespan,
    )

    # Setup enterprise patterns
    setup_middleware(app, service_config)
    setup_error_handlers(app)

    # Include API routes
    app.include_router(router, prefix="/api/v1")

    # Setup logging using DRY patterns
    config.setup_logging()

    return app


def main() -> None:
    """Run the FastAPI application."""
    app = create_app()
    config = create_order_service_config()

    # Run with uvicorn using DRY configuration
    uvicorn.run(
        app,
        host=config.host,
        port=config.http_port,
        log_level=getattr(config, 'log_level', 'info').lower(),
        reload=config.debug,
    )


if __name__ == "__main__":
    main()
