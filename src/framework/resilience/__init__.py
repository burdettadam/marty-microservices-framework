"""
Advanced Resilience Patterns Framework

Provides enterprise-grade resilience patterns for microservices including:
- Circuit Breakers: Prevent cascading failures
- Retry Mechanisms: Exponential backoff and jittered retries
- Bulkhead Isolation: Resource isolation and thread pools
- Timeout Management: Request and operation timeouts
- Fallback Strategies: Graceful degradation patterns
"""

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
from .fallback import (
    CacheFallback,
    FallbackConfig,
    FallbackError,
    FallbackStrategy,
    FunctionFallback,
    StaticFallback,
    with_fallback,
)
from .patterns import (
    ResilienceConfig,
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
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerState",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "circuit_breaker",
    # Retry
    "RetryConfig",
    "RetryStrategy",
    "RetryError",
    "ExponentialBackoff",
    "LinearBackoff",
    "ConstantBackoff",
    "retry_async",
    "retry_with_circuit_breaker",
    # Bulkhead
    "BulkheadConfig",
    "BulkheadPool",
    "BulkheadError",
    "ThreadPoolBulkhead",
    "SemaphoreBulkhead",
    "bulkhead_isolate",
    # Timeout
    "TimeoutConfig",
    "ResilienceTimeoutError",
    "TimeoutManager",
    "with_timeout",
    "timeout_async",
    # Fallback
    "FallbackStrategy",
    "FallbackConfig",
    "FallbackError",
    "StaticFallback",
    "FunctionFallback",
    "CacheFallback",
    "with_fallback",
    # Patterns
    "ResilienceManager",
    "ResilienceConfig",
    "ResiliencePattern",
    "resilience_pattern",
    "initialize_resilience",
]
