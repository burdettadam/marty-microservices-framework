"""
Advanced Resilience Patterns Framework

Provides enterprise-grade resilience patterns for microservices including:
- Circuit Breakers: Prevent cascading failures
- Retry Mechanisms: Exponential backoff and jittered retries
- Bulkhead Isolation: Resource isolation and thread pools
- Connection Pools: HTTP, Redis, and database connection pooling
- Timeout Management: Request and operation timeouts
- Fallback Strategies: Graceful degradation patterns
- Chaos Engineering: Fault injection and resilience testing
- Enhanced Monitoring: Comprehensive metrics and health checks
- Middleware Integration: FastAPI and other framework integration
"""

# Import basic resilience patterns
from .bulkhead import (
    BulkheadConfig,
    BulkheadError,
    BulkheadPool,
    SemaphoreBulkhead,
    ThreadPoolBulkhead,
    bulkhead_isolate,
)
from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerState,
    circuit_breaker,
)

# Import connection pools and middleware
from .connection_pools import (
    ConnectionPoolManager,
    HealthCheckConfig,
    HTTPConnectionPool,
    HTTPPoolConfig,
    PoolConfig,
    PoolHealthChecker,
    RedisConnectionPool,
    RedisPoolConfig,
)
from .connection_pools.manager import (
    close_all_pools,
    get_pool,
    get_pool_manager,
    initialize_pools,
)

# Enhanced resilience patterns will be imported when available
# from .enhanced import (...) - Module not yet implemented
# from .external_dependencies import (...) - Module not yet implemented
from .fallback import (
    CacheFallback,
    FallbackConfig,
    FallbackError,
    FallbackStrategy,
    FunctionFallback,
    StaticFallback,
    with_fallback,
)
from .middleware import (
    ResilienceConfig,
    ResilienceMiddleware,
    ResilienceService,
    close_resilience_service,
    get_resilience_service,
    resilient,
)
from .patterns import (
    ResilienceManager,
    ResiliencePattern,
    initialize_resilience,
    resilience_pattern,
)
from .retry import (
    ConstantBackoff,
    ExponentialBackoff,
    LinearBackoff,
    RetryConfig,
    RetryError,
    RetryStrategy,
    retry_async,
    retry_with_circuit_breaker,
)
from .timeout import (
    ResilienceTimeoutError,
    TimeoutConfig,
    TimeoutManager,
    timeout_async,
    with_timeout,
)

__all__ = [
    # Basic resilience patterns
    "BulkheadConfig",
    "BulkheadError",
    "BulkheadPool",
    "CacheFallback",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerState",
    "ConstantBackoff",
    "ExponentialBackoff",
    "FallbackConfig",
    "FallbackError",
    "FallbackStrategy",
    "FunctionFallback",
    "LinearBackoff",
    "ResilienceConfig",
    "ResilienceManager",
    "ResiliencePattern",
    "ResilienceTimeoutError",
    "RetryConfig",
    "RetryError",
    "RetryStrategy",
    "SemaphoreBulkhead",
    "StaticFallback",
    "ThreadPoolBulkhead",
    "TimeoutConfig",
    "TimeoutManager",
    "bulkhead_isolate",
    "circuit_breaker",
    "initialize_resilience",
    "resilience_pattern",
    "retry_async",
    "retry_with_circuit_breaker",
    "timeout_async",
    "with_fallback",
    "with_timeout",
    # Connection pools and middleware (new)
    "HTTPConnectionPool",
    "HTTPPoolConfig",
    "RedisConnectionPool",
    "RedisPoolConfig",
    "ConnectionPoolManager",
    "PoolConfig",
    "PoolHealthChecker",
    "HealthCheckConfig",
    "ResilienceMiddleware",
    "ResilienceService",
    "ResilienceConfig",
    "resilient",
    "get_pool_manager",
    "initialize_pools",
    "get_pool",
    "close_all_pools",
    "get_resilience_service",
    "close_resilience_service",
]
