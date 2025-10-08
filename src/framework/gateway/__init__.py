"""
Gateway Package.

Provides comprehensive API Gateway infrastructure including:
- Dynamic routing and load balancing
- Rate limiting and circuit breakers
- Authentication and authorization
- Middleware system for request/response processing
- Service discovery and health checking
- Performance monitoring and metrics

Available Classes:
- APIGateway: Main gateway implementation
- RouteConfig: Route configuration with rules and policies
- ServiceInstance: Service instance registration
- ServiceRegistry: Service discovery and health checking
- LoadBalancer: Various load balancing algorithms
- RateLimiter: Rate limiting implementations
- Authenticator: Authentication providers
- Middleware: Request/response processing middleware
- CircuitBreaker: Resilience pattern implementation

Supported Features:
- HTTP/HTTPS routing with multiple load balancing algorithms
- JWT, API Key, OAuth2 authentication
- Token bucket, sliding window rate limiting
- CORS, security headers, logging middleware
- Circuit breaker pattern and health checking
- Performance metrics and monitoring
"""

# New enterprise gateway components
from .api_gateway import (
    APIGateway,
    APIKeyAuthenticator,
    AuthConfig,
    AuthenticationType,
    Authenticator,
    CircuitBreaker,
    GatewayStats,
    JWTAuthenticator,
    LeastConnectionsLoadBalancer,
    LoadBalancer,
    LoadBalancingAlgorithm,
    RateLimitAlgorithm,
    RateLimitConfig,
    RateLimiter,
    RoundRobinLoadBalancer,
    RouteConfig,
    RouteRule,
    RoutingMethod,
    ServiceInstance,
    ServiceRegistry,
    TokenBucketRateLimiter,
    create_gateway,
    create_jwt_auth_route,
    create_rate_limited_route,
    gateway_context,
    get_gateway,
)
from .middleware import (
    CachingMiddleware,
    CORSMiddleware,
    LoggingMiddleware,
    MetricsMiddleware,
    Middleware,
    MiddlewareChain,
    MiddlewareContext,
    SecurityMiddleware,
    TransformationMiddleware,
    ValidationMiddleware,
    create_api_validation_middleware,
    create_standard_middleware_chain,
    create_transformation_middleware,
)

__all__ = [
    # Core Gateway Components
    "RoutingMethod",
    "LoadBalancingAlgorithm",
    "RateLimitAlgorithm",
    "AuthenticationType",
    "ServiceInstance",
    "RouteRule",
    "RateLimitConfig",
    "AuthConfig",
    "RouteConfig",
    "GatewayStats",
    # Rate Limiting
    "RateLimiter",
    "TokenBucketRateLimiter",
    # Load Balancing
    "LoadBalancer",
    "RoundRobinLoadBalancer",
    "LeastConnectionsLoadBalancer",
    # Authentication
    "Authenticator",
    "JWTAuthenticator",
    "APIKeyAuthenticator",
    # Resilience
    "CircuitBreaker",
    # Service Discovery
    "ServiceRegistry",
    # Main Gateway
    "APIGateway",
    "get_gateway",
    "create_gateway",
    "gateway_context",
    # Utility Functions
    "create_jwt_auth_route",
    "create_rate_limited_route",
    # Middleware Components
    "MiddlewareContext",
    "Middleware",
    "LoggingMiddleware",
    "CORSMiddleware",
    "ValidationMiddleware",
    "CachingMiddleware",
    "MetricsMiddleware",
    "TransformationMiddleware",
    "SecurityMiddleware",
    "MiddlewareChain",
    "create_standard_middleware_chain",
    "create_api_validation_middleware",
    "create_transformation_middleware",
]

# New enterprise gateway components
from .api_gateway import (
    APIGateway,
    APIKeyAuthenticator,
    AuthConfig,
    AuthenticationType,
    Authenticator,
    CircuitBreaker,
    GatewayStats,
    JWTAuthenticator,
    LeastConnectionsLoadBalancer,
    LoadBalancer,
    LoadBalancingAlgorithm,
    RateLimitAlgorithm,
    RateLimitConfig,
    RateLimiter,
    RoundRobinLoadBalancer,
    RouteConfig,
    RouteRule,
    RoutingMethod,
    ServiceInstance,
    ServiceRegistry,
    TokenBucketRateLimiter,
    create_gateway,
    create_jwt_auth_route,
    create_rate_limited_route,
    gateway_context,
    get_gateway,
)
from .middleware import (
    CachingMiddleware,
    CORSMiddleware,
    LoggingMiddleware,
    MetricsMiddleware,
    Middleware,
    MiddlewareChain,
    MiddlewareContext,
    SecurityMiddleware,
    TransformationMiddleware,
    ValidationMiddleware,
    create_api_validation_middleware,
    create_standard_middleware_chain,
    create_transformation_middleware,
)

__all__ = [
    # Core Gateway Components
    "RoutingMethod",
    "LoadBalancingAlgorithm",
    "RateLimitAlgorithm",
    "AuthenticationType",
    "ServiceInstance",
    "RouteRule",
    "RateLimitConfig",
    "AuthConfig",
    "RouteConfig",
    "GatewayStats",
    # Rate Limiting
    "RateLimiter",
    "TokenBucketRateLimiter",
    # Load Balancing
    "LoadBalancer",
    "RoundRobinLoadBalancer",
    "LeastConnectionsLoadBalancer",
    # Authentication
    "Authenticator",
    "JWTAuthenticator",
    "APIKeyAuthenticator",
    # Resilience
    "CircuitBreaker",
    # Service Discovery
    "ServiceRegistry",
    # Main Gateway
    "APIGateway",
    "get_gateway",
    "create_gateway",
    "gateway_context",
    # Utility Functions
    "create_jwt_auth_route",
    "create_rate_limited_route",
    # Middleware Components
    "MiddlewareContext",
    "Middleware",
    "LoggingMiddleware",
    "CORSMiddleware",
    "ValidationMiddleware",
    "CachingMiddleware",
    "MetricsMiddleware",
    "TransformationMiddleware",
    "SecurityMiddleware",
    "MiddlewareChain",
    "create_standard_middleware_chain",
    "create_api_validation_middleware",
    "create_transformation_middleware",
    "TokenManager",
    "TokenStore",
    "TokenValidator",
]

# Configuration management
from .config import (  # Configuration loaders; Dynamic configuration; Configuration formats; Configuration management
    ConfigLoader,
    ConfigManager,
    ConfigRegistry,
    ConfigUpdater,
    ConfigValidator,
    ConfigWatcher,
    DatabaseConfigLoader,
    DynamicConfig,
    EnvironmentConfigLoader,
    FileConfigLoader,
    JSONConfig,
    TOMLConfig,
    YAMLConfig,
)

# Core gateway components
from .core import (  # Main gateway classes; Request/Response handling; Route management; Middleware system; Plugin system; Error handling
    APIGateway,
    AuthenticationError,
    GatewayConfig,
    GatewayContext,
    GatewayError,
    GatewayRequest,
    GatewayResponse,
    Middleware,
    MiddlewareChain,
    MiddlewareRegistry,
    Plugin,
    PluginConfig,
    PluginManager,
    RateLimitExceededError,
    RequestContext,
    Route,
    RouteConfig,
    RouteGroup,
    RouteMatcher,
    RouteNotFoundError,
    UpstreamError,
)

# Main gateway factory and utilities
from .factory import (  # Gateway factory; Preset configurations; Utilities
    BasicGatewayConfig,
    ConfigUtils,
    EnterpriseGatewayConfig,
    GatewayBuilder,
    GatewayFactory,
    GatewayUtils,
    MicroservicesGatewayConfig,
    RouterUtils,
    create_gateway,
)

# Load balancing integration
from .load_balancing import (  # Gateway load balancer; Upstream management; Service discovery integration; Failover and retry
    CircuitBreakerIntegration,
    DiscoveryConfig,
    FailoverManager,
    GatewayLoadBalancer,
    LoadBalancingConfig,
    LoadBalancingStrategy,
    RetryPolicy,
    ServiceDiscoveryIntegration,
    UpstreamConfig,
    UpstreamHealthChecker,
    UpstreamManager,
)

# Monitoring and observability
from .monitoring import (  # Gateway metrics; Request tracing; Logging system; Health checks; Performance monitoring
    AccessLogger,
    DistributedTracing,
    ErrorLogger,
    GatewayLogger,
    GatewayMetrics,
    HealthChecker,
    HealthEndpoint,
    LatencyTracker,
    MetricsCollector,
    MetricsExporter,
    PerformanceMonitor,
    RequestTracer,
    StatusReporter,
    ThroughputMonitor,
    TraceContext,
)

# Plugin system
from .plugins import (  # Built-in plugins; Plugin development; Plugin management; Extension points
    CachingPlugin,
    CompressionPlugin,
    ErrorHook,
    LifecycleHook,
    LoggingPlugin,
    MetricsPlugin,
    PluginContext,
    PluginInterface,
    PluginLifecycle,
    PluginLoader,
    PluginRegistry,
    PluginValidator,
    RequestHook,
    ResponseHook,
)

# Rate limiting
from .rate_limiting import (  # Rate limiter implementations; Rate limiting strategies; Storage backends; Rate limit exceptions
    DatabaseStorage,
    FixedWindowLimiter,
    LeakyBucketLimiter,
    MemoryStorage,
    RateLimitConfig,
    RateLimiter,
    RateLimitError,
    RateLimitExceeded,
    RateLimitRule,
    RateLimitStorage,
    RateLimitStrategy,
    RedisStorage,
    SlidingWindowLimiter,
    TokenBucketLimiter,
)

# Routing engine
from .routing import (  # Router implementations; Route matching; Route builders; Routing configuration
    CompositeRouter,
    ExactMatcher,
    HeaderRouter,
    HostRouter,
    PathMatcher,
    PathRouter,
    RegexMatcher,
    RouteBuilder,
    Router,
    RouterBuilder,
    RoutingConfig,
    RoutingRule,
    RoutingStrategy,
    WildcardMatcher,
)

# Security features
from .security import (  # Security middleware; CORS configuration; Security headers; Input validation; DDoS protection
    ContentSecurityPolicy,
    CORSConfig,
    CORSMiddleware,
    CORSPolicy,
    DDoSProtection,
    InputValidationMiddleware,
    IPBlacklist,
    IPWhitelist,
    RequestThrottling,
    RequestValidator,
    SecurityHeadersConfig,
    SecurityHeadersMiddleware,
    SecurityMiddleware,
    ValidationError,
    ValidationRule,
)

# Request/Response transformation
from .transformation import (  # Transformer implementations; Transformation rules; Content transformation; Header manipulation; Body manipulation
    BodyFilter,
    BodyMapper,
    BodyTransformer,
    BodyValidator,
    ContentTypeTransformer,
    FormDataTransformer,
    HeaderFilter,
    HeaderInjector,
    HeaderMapper,
    HeaderTransformer,
    JSONTransformer,
    RequestTransformer,
    ResponseTransformer,
    TransformationConfig,
    TransformationPipeline,
    TransformationRule,
    Transformer,
    XMLTransformer,
)

# WebSocket and real-time support
from .websocket import (  # WebSocket gateway; Connection management; Message routing; SSE support; Real-time features
    BroadcastManager,
    ChannelManager,
    ConnectionManager,
    ConnectionPool,
    ConnectionRegistry,
    EventStream,
    MessageFilter,
    MessageRouter,
    MessageTransformer,
    SSEConfig,
    SSEGateway,
    SubscriptionManager,
    WebSocketConfig,
    WebSocketGateway,
    WebSocketHandler,
)

# Version and metadata
__version__ = "1.0.0"
__author__ = "Marty Framework Team"
__description__ = "Comprehensive API Gateway Framework for Microservices"

# Export main classes for easy access
__all__ = [
    # Core classes
    "APIGateway",
    "GatewayConfig",
    "GatewayContext",
    "Route",
    "RouteConfig",
    "Middleware",
    "Plugin",
    # Main components
    "Router",
    "RateLimiter",
    "AuthProvider",
    "Transformer",
    "GatewayLoadBalancer",
    "SecurityMiddleware",
    "GatewayMetrics",
    "WebSocketGateway",
    # Factory and builders
    "create_gateway",
    "GatewayBuilder",
    "RouteBuilder",
    # Configuration
    "ConfigLoader",
    "DynamicConfig",
    # Exceptions
    "GatewayError",
    "RouteNotFoundError",
    "AuthenticationError",
    "RateLimitExceededError",
    # Version
    "__version__",
]


# Module-level convenience functions
def quick_gateway(config_file: str = None, **kwargs):
    """
    Create a gateway with minimal configuration.

    Args:
        config_file: Path to configuration file
        **kwargs: Additional configuration options

    Returns:
        Configured APIGateway instance
    """
    from .factory import create_gateway

    return create_gateway(config_file=config_file, **kwargs)


def basic_router():
    """Create a basic router with common routes."""
    from .routing import RouterBuilder

    return RouterBuilder().build()


def standard_middleware():
    """Get standard middleware chain for common use cases."""
    from .core import MiddlewareChain
    from .monitoring import GatewayMetrics
    from .security import CORSMiddleware, SecurityHeadersMiddleware

    chain = MiddlewareChain()
    chain.add(CORSMiddleware())
    chain.add(SecurityHeadersMiddleware())
    chain.add(GatewayMetrics())

    return chain


# Gateway presets
BASIC_GATEWAY_FEATURES = ["routing", "rate_limiting", "auth", "monitoring"]

ENTERPRISE_GATEWAY_FEATURES = [
    "routing",
    "rate_limiting",
    "auth",
    "transformation",
    "load_balancing",
    "security",
    "monitoring",
    "websocket",
    "plugins",
]

MICROSERVICES_GATEWAY_FEATURES = [
    "routing",
    "rate_limiting",
    "auth",
    "load_balancing",
    "service_discovery",
    "circuit_breaker",
    "monitoring",
    "transformation",
]
