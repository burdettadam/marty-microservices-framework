"""
Enterprise API Gateway Service Template

This template provides a comprehensive API gateway implementation with:
- Dynamic service discovery
- Load balancing
- Circuit breaker patterns
- Rate limiting
- Authentication/Authorization
- Request/Response transformation
- Metrics and monitoring
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from framework.discovery import (
    ConsulServiceRegistry,
    DiscoveryManagerConfig,
    ServiceDiscoveryManager,
)
from framework.gateway import (
    APIGateway,
    AuthConfig,
    AuthenticationType,
    CircuitBreakerConfig,
    GatewayConfig,
    LoadBalancingStrategy,
    RateLimitConfig,
    RouteConfig,
    RouteRule,
    RoutingMethod,
    ServiceInstance,
)
from framework.resilience import BulkheadConfig
from framework.resilience import CircuitBreakerConfig as ResilienceCircuitBreakerConfig
from framework.resilience import ResilienceConfig, ResiliencePattern, RetryConfig
from marty_chassis.config import ChassisConfig, load_config
from marty_chassis.logger import get_logger
from marty_chassis.metrics import MetricsCollector

logger = get_logger(__name__)

# Global gateway instance
gateway: APIGateway = None
discovery_manager: ServiceDiscoveryManager = None
metrics: MetricsCollector = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    global gateway, discovery_manager, metrics

    try:
        # Load configuration
        config = load_config()
        logger.info("Starting API Gateway service...")

        # Initialize metrics
        metrics = MetricsCollector("api_gateway")

        # Initialize service discovery
        discovery_config = DiscoveryManagerConfig(
            service_name="api-gateway",
            registry_type="consul",  # or "etcd", "kubernetes", "memory"
            load_balancing_enabled=True,
            health_check_enabled=True,
            health_check_interval=30,
        )
        discovery_manager = ServiceDiscoveryManager(discovery_config)
        await discovery_manager.start()

        # Initialize API Gateway
        gateway_config = GatewayConfig(
            gateway_id="main-gateway",
            host="0.0.0.0",
            port=8080,
            enable_cors=True,
            enable_metrics=True,
            enable_health_checks=True,
            default_timeout=30,
            max_concurrent_requests=1000,
        )

        gateway = APIGateway(gateway_config)
        await gateway.start()

        # Register with service discovery
        gateway_instance = ServiceInstance(
            service_name="api-gateway",
            instance_id="gateway-001",
            endpoint=f"http://localhost:8080",
            metadata={
                "version": "1.0.0",
                "environment": config.environment.value,
                "gateway_type": "main",
            },
        )
        await discovery_manager.register_service(gateway_instance)

        # Configure routes from configuration
        await configure_gateway_routes(gateway, config)

        logger.info("API Gateway service started successfully")
        yield

    except Exception as e:
        logger.error(f"Failed to start API Gateway: {e}")
        raise
    finally:
        # Cleanup
        if gateway:
            await gateway.stop()
        if discovery_manager:
            await discovery_manager.stop()
        logger.info("API Gateway service stopped")


async def configure_gateway_routes(gateway: APIGateway, config: ChassisConfig):
    """Configure gateway routes from configuration."""

    # Example route configurations
    routes = [
        # User Service Routes
        RouteConfig(
            name="user_service_v1",
            rule=RouteRule(
                path_pattern="/api/v1/users/**",
                methods=[
                    RoutingMethod.GET,
                    RoutingMethod.POST,
                    RoutingMethod.PUT,
                    RoutingMethod.DELETE,
                ],
            ),
            target_service="user-service",
            load_balancing_strategy=LoadBalancingStrategy.ROUND_ROBIN,
            auth=AuthConfig(
                type=AuthenticationType.JWT,
                secret_key=config.security.jwt_secret
                if hasattr(config, "security")
                else "secret",
            ),
            rate_limit=RateLimitConfig(requests_per_second=100, burst_size=200),
            circuit_breaker=CircuitBreakerConfig(
                failure_threshold=5, timeout_seconds=30, half_open_max_calls=3
            ),
            enable_caching=True,
            cache_ttl=300,
            priority=100,
        ),
        # Order Service Routes
        RouteConfig(
            name="order_service_v1",
            rule=RouteRule(
                path_pattern="/api/v1/orders/**",
                methods=[RoutingMethod.GET, RoutingMethod.POST, RoutingMethod.PUT],
            ),
            target_service="order-service",
            load_balancing_strategy=LoadBalancingStrategy.LEAST_CONNECTIONS,
            auth=AuthConfig(
                type=AuthenticationType.JWT,
                secret_key=config.security.jwt_secret
                if hasattr(config, "security")
                else "secret",
            ),
            rate_limit=RateLimitConfig(requests_per_second=50, burst_size=100),
            circuit_breaker=CircuitBreakerConfig(
                failure_threshold=3, timeout_seconds=20
            ),
            priority=90,
        ),
        # Product Service Routes (Public API)
        RouteConfig(
            name="product_service_public",
            rule=RouteRule(
                path_pattern="/api/v1/products/**", methods=[RoutingMethod.GET]
            ),
            target_service="product-service",
            load_balancing_strategy=LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN,
            rate_limit=RateLimitConfig(requests_per_second=200, burst_size=500),
            circuit_breaker=CircuitBreakerConfig(
                failure_threshold=10, timeout_seconds=60
            ),
            enable_caching=True,
            cache_ttl=600,
            priority=80,
        ),
        # Health Check Route
        RouteConfig(
            name="health_check",
            rule=RouteRule(path_pattern="/health/**", methods=[RoutingMethod.GET]),
            target_service="health-service",
            load_balancing_strategy=LoadBalancingStrategy.ROUND_ROBIN,
            priority=200,
        ),
    ]

    # Add routes to gateway
    for route in routes:
        gateway.add_route(route)
        logger.info(f"Added route: {route.name} -> {route.target_service}")


# FastAPI app initialization
app = FastAPI(
    title="Enterprise API Gateway",
    description="Comprehensive API Gateway with service discovery, load balancing, and resilience patterns",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def gateway_middleware(request: Request, call_next):
    """Gateway processing middleware."""
    if not gateway:
        return JSONResponse(
            status_code=503, content={"error": "Gateway not initialized"}
        )

    try:
        # Convert FastAPI request to gateway request
        gateway_request = await convert_fastapi_request(request)

        # Process through gateway
        gateway_response = await gateway.handle_request(gateway_request)

        # Convert gateway response to FastAPI response
        return convert_gateway_response(gateway_response)

    except Exception as e:
        logger.error(f"Gateway processing error: {e}")
        metrics.increment("gateway_errors") if metrics else None
        return JSONResponse(
            status_code=500, content={"error": "Internal gateway error"}
        )


async def convert_fastapi_request(request: Request):
    """Convert FastAPI request to gateway request format."""
    from framework.gateway.core import GatewayRequest, HTTPMethod

    # Read body
    body = await request.body()

    # Convert method
    method_map = {
        "GET": HTTPMethod.GET,
        "POST": HTTPMethod.POST,
        "PUT": HTTPMethod.PUT,
        "DELETE": HTTPMethod.DELETE,
        "PATCH": HTTPMethod.PATCH,
        "HEAD": HTTPMethod.HEAD,
        "OPTIONS": HTTPMethod.OPTIONS,
    }

    return GatewayRequest(
        method=method_map.get(request.method, HTTPMethod.GET),
        path=str(request.url.path),
        query_params=dict(request.query_params),
        headers=dict(request.headers),
        body=body,
        client_ip=request.client.host if request.client else "unknown",
    )


def convert_gateway_response(gateway_response):
    """Convert gateway response to FastAPI response."""
    return JSONResponse(
        status_code=gateway_response.status_code,
        content=gateway_response.get_json_body() if gateway_response.body else {},
        headers=dict(gateway_response.headers),
    )


# Health check endpoints
@app.get("/health")
async def health_check():
    """Gateway health check."""
    try:
        gateway_healthy = gateway and await gateway.get_health_status()
        discovery_healthy = discovery_manager and discovery_manager.is_healthy()

        return {
            "status": "healthy"
            if gateway_healthy and discovery_healthy
            else "unhealthy",
            "gateway": "healthy" if gateway_healthy else "unhealthy",
            "discovery": "healthy" if discovery_healthy else "unhealthy",
            "timestamp": metrics.get_timestamp() if metrics else None,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503, content={"status": "unhealthy", "error": str(e)}
        )


@app.get("/metrics")
async def get_metrics():
    """Get gateway metrics."""
    if not metrics:
        return {"error": "Metrics not available"}

    gateway_stats = await gateway.get_stats() if gateway else {}
    discovery_stats = discovery_manager.get_stats() if discovery_manager else {}

    return {
        "gateway": gateway_stats,
        "discovery": discovery_stats,
        "metrics": metrics.get_all_metrics(),
    }


@app.get("/routes")
async def get_routes():
    """Get configured routes."""
    if not gateway:
        return {"error": "Gateway not available"}

    return {"routes": gateway.get_route_summary(), "total_routes": len(gateway.routes)}


# Service discovery endpoints
@app.get("/services")
async def get_services():
    """Get discovered services."""
    if not discovery_manager:
        return {"error": "Service discovery not available"}

    return await discovery_manager.get_all_services()


@app.get("/services/{service_name}")
async def get_service_instances(service_name: str):
    """Get instances of a specific service."""
    if not discovery_manager:
        raise HTTPException(status_code=503, detail="Service discovery not available")

    instances = await discovery_manager.discover_service(service_name)
    return {
        "service_name": service_name,
        "instances": [instance.to_dict() for instance in instances],
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False, log_level="info")
