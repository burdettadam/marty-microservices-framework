"""
FastAPI application factory and main application setup.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import api_router
from .config import get_settings
from .database import create_tables, engine
from .middleware import LoggingMiddleware, MetricsMiddleware, SecurityMiddleware
from .services.discovery import ServiceDiscoveryService
from .services.metrics import MetricsCollector

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    settings = get_settings()
    logger.info("Starting Marty Dashboard", version=settings.version)

    # Create database tables
    await create_tables()

    # Initialize services
    service_discovery = ServiceDiscoveryService()
    metrics_collector = MetricsCollector()

    # Start background tasks
    await service_discovery.start()
    await metrics_collector.start()

    # Store services in app state
    app.state.service_discovery = service_discovery
    app.state.metrics_collector = metrics_collector

    yield

    # Cleanup
    await service_discovery.stop()
    await metrics_collector.stop()
    logger.info("Marty Dashboard stopped")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Marty Dashboard",
        description="Management Dashboard for Marty Microservices Framework",
        version=settings.version,
        openapi_url="/api/openapi.json" if settings.debug else None,
        docs_url="/api/docs" if settings.debug else None,
        redoc_url="/api/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # Trust proxy headers
    if settings.trusted_hosts:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.trusted_hosts,
        )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware
    app.add_middleware(SecurityMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(LoggingMiddleware)

    # API routes
    app.include_router(api_router, prefix="/api")

    # Static files (React frontend)
    if settings.serve_frontend:
        app.mount("/static", StaticFiles(directory="static"), name="static")

        @app.get("/{path:path}")
        async def serve_frontend(path: str):
            """Serve React frontend for all non-API routes."""
            return StaticFiles(directory="static").get_response("index.html", None)

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception", exc_info=exc, path=request.url.path)
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )

    # Health check
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": "marty-dashboard",
            "version": settings.version,
        }

    return app


# Create application instance
app = create_app()
