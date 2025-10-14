"""
API router for the dashboard application.
"""

from fastapi import APIRouter

from .endpoints import alerts, auth, config, metrics, services

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(services.router, prefix="/services", tags=["Services"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["Metrics"])
api_router.include_router(config.router, prefix="/config", tags=["Configuration"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])


@api_router.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Marty Dashboard API",
        "version": "1.0.0",
        "docs": "/api/docs",
    }
