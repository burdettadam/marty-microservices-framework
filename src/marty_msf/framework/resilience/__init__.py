"""
Advanced Resilience Patterns Framework

Provides enterprise-grade resilience patterns for microservices including:
- Circuit Breakers: Prevent cascading failures
- Retry Mechanisms: Exponential backoff and jittered retries
- Bulkhead Isolation: Resource isolation and thread pools
- Timeout Management: Request and operation timeouts
- Fallback Strategies: Graceful degradation patterns
- Chaos Engineering: Fault injection and resilience testing
- Enhanced Monitoring: Comprehensive metrics and health checks
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

# Import enhanced resilience patterns (ported from Marty)
from .enhanced import (  # Advanced retry mechanisms; Chaos engineering; Enhanced circuit breaker; Graceful degradation; gRPC interceptors; Monitoring; Outbound calls
    AdvancedRetryConfig,
    AdvancedRetryManager,
    AdvancedRetryMetrics,
    BackoffStrategy,
    DynamicBackoff,
    EnhancedCircuitBreakerConfig,
    ExponentialJitteredBackoff,
    FixedBackoff,
    FriedCircuitError,
    IncrementalBackoff,
    PolynomialBackoff,
    async_call_with_resilience,
    async_retry_with_advanced_policy,
    get_client_resilience_config,
    register_retry_manager_for_monitoring,
    retry_with_advanced_policy,
)
from .external_dependencies import (
    DependencyType,
    ExternalDependencyConfig,
    ExternalDependencyManager,
    api_call,
    cache_call,
    database_call,
    get_external_dependency_manager,
    register_api_dependency,
    register_cache_dependency,
    register_database_dependency,
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
    # Enhanced resilience patterns (from Marty)
    "AdvancedRetryConfig",
    "AdvancedRetryManager",
    "AdvancedRetryMetrics",
    "async_call_with_resilience",
    "async_retry_with_advanced_policy",
    "AsyncResilienceClientInterceptor",
    "BackoffStrategy",
    "CachedValueProvider",
    "chaos_context",
    "ChaosConfig",
    "ChaosInjector",
    "ChaosType",
    "CompositeResilienceInterceptor",
    "DefaultErrorClassifier",
    "DefaultValueProvider",
    "DegradationLevel",
    "EnhancedCircuitBreaker",
    "EnhancedCircuitBreakerConfig",
    "EnhancedResilienceServerInterceptor",
    "ErrorClassifier",
    "FallbackProvider",
    "FeatureToggle",
    "generate_resilience_health_report",
    "get_all_retry_manager_stats",
    "get_global_monitor",
    "get_resilience_health_status",
    "get_retry_manager",
    "GracefulDegradationManager",
    "HealthBasedDegradationMonitor",
    "register_circuit_breaker_for_monitoring",
    "register_retry_manager_for_monitoring",
    "ResilienceClientInterceptor",
    "ResilienceHealthCheck",
    "ResilienceMonitor",
    "ResilienceTestSuite",
    "retry_with_advanced_policy",
    "RetryResult",
    "ServiceFallbackProvider",
    # External dependency management
    "DependencyType",
    "ExternalDependencyConfig",
    "ExternalDependencyManager",
    "api_call",
    "cache_call",
    "database_call",
    "get_external_dependency_manager",
    "register_api_dependency",
    "register_cache_dependency",
    "register_database_dependency",
]
