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
    # Bulkhead
    "BulkheadConfig",
    "BulkheadError",
    "BulkheadPool",
    "CacheFallback",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerState",
    "ConstantBackoff",
    "ExponentialBackoff",
    "FallbackConfig",
    "FallbackError",
    # Fallback
    "FallbackStrategy",
    "FunctionFallback",
    "LinearBackoff",
    "ResilienceConfig",
    # Patterns
    "ResilienceManager",
    "ResiliencePattern",
    "ResilienceTimeoutError",
    # Retry
    "RetryConfig",
    "RetryError",
    "RetryStrategy",
    "SemaphoreBulkhead",
    "StaticFallback",
    "ThreadPoolBulkhead",
    # Timeout
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
]
