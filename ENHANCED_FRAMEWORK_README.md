# Enhanced Marty Microservices Framework (MMF)

## 🎯 Framework Enhancement Summary

The Marty Microservices Framework has been significantly enhanced to address all gaps preventing Marty's complete migration. The framework now provides enterprise-grade capabilities that combine the best of both Marty's existing patterns and MMF's architectural foundations.

### ✅ What's New

- **🛡️ Advanced Resilience Patterns** - Enhanced circuit breakers, sophisticated retry mechanisms, chaos engineering
- **🧪 Comprehensive Testing Framework** - Contract testing, chaos engineering, performance baselines, quality gates
- **📝 Unified Logging Framework** - JSON structured logging with trace correlation and service context
- **🔗 Complete Integration** - All components work together seamlessly with consistent APIs

## 🏗️ Enhanced Architecture

```
Enhanced MMF Framework
├── 🛡️ Resilience (src/framework/resilience/)
│   ├── Basic Patterns (circuit breaker, retry, bulkhead, timeout, fallback)
│   └── Enhanced Patterns (enhanced/)
│       ├── advanced_retry.py - Sophisticated retry with 6 backoff strategies
│       ├── enhanced_circuit_breaker.py - Monitoring, failure rates, sliding windows
│       ├── chaos_engineering.py - Fault injection and resilience testing
│       ├── graceful_degradation.py - Feature toggles and fallback providers
│       ├── grpc_interceptors.py - Enhanced gRPC client/server interceptors
│       ├── monitoring.py - Comprehensive health checks and metrics
│       └── outbound_resilience.py - Unified outbound call resilience
│
├── 🧪 Testing (src/framework/testing/)
│   ├── Core Testing (test_automation.py, core.py)
│   └── Enhanced Testing
│       └── enhanced_testing.py - Contract, chaos, performance, quality gates
│
├── 📝 Logging (src/framework/logging/)
│   └── __init__.py - Unified structured logging with trace correlation
│
├── 🏭 Generators (src/framework/generators/)
├── 📊 Audit (src/framework/audit/)
├── 🗄️ Database (src/framework/database/)
└── 🌐 Networking (src/framework/networking/)
```

## 🚀 Quick Start Guide

### 1. Enhanced Resilience

```python
from framework.resilience import (
    # Advanced retry with multiple backoff strategies
    AdvancedRetryConfig, BackoffStrategy, async_retry_with_advanced_policy,

    # Enhanced circuit breakers with monitoring
    EnhancedCircuitBreaker, EnhancedCircuitBreakerConfig,

    # Chaos engineering for testing
    ChaosConfig, ChaosType, chaos_context,

    # Unified outbound call resilience
    async_call_with_resilience
)

# Configure advanced retry with jittered exponential backoff
retry_config = AdvancedRetryConfig(
    max_attempts=5,
    backoff_strategy=BackoffStrategy.JITTERED_EXPONENTIAL,
    base_delay=1.0,
    max_delay=30.0,
    retryable_exceptions=(ConnectionError, TimeoutError),
)

# Configure enhanced circuit breaker with failure rate monitoring
circuit_config = EnhancedCircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=60.0,
    failure_rate_threshold=0.5,  # 50% failure rate triggers open
    minimum_throughput=10,       # Minimum calls before rate calculation
)

# Use unified resilience for outbound calls
result = await async_call_with_resilience(
    external_api_call,
    retry_config=retry_config,
    circuit_breaker_config=circuit_config,
    circuit_breaker_name="external_service"
)
```

### 2. Comprehensive Testing

```python
from framework.testing.enhanced_testing import (
    EnhancedTestRunner, ContractTestConfig, PerformanceBaseline
)

# Set up enhanced test runner
test_runner = EnhancedTestRunner("my-service")

# Contract testing with SLA validation
contract_config = ContractTestConfig(
    service_name="user-service",
    endpoints=["/users", "/health"],
    expected_response_times={"/users": 2.0, "/health": 0.5}
)
contract_results = await test_runner.run_contract_tests(config, test_function)

# Chaos engineering tests
chaos_results = await test_runner.run_chaos_tests(target_function)

# Performance baseline testing
baseline = PerformanceBaseline(
    endpoint="/users",
    max_response_time=1.0,
    max_memory_usage=512.0,
    max_cpu_usage=80.0,
    min_throughput=100.0
)
perf_result = await test_runner.run_performance_tests(target_function, baseline)

# Quality gates validation
quality_report = test_runner.generate_quality_report()
print(f"All quality gates passed: {quality_report['all_gates_passed']}")
```

### 3. Unified Logging

```python
from framework.logging import get_unified_logger, setup_unified_logging

# Service-wide logging setup
logger = setup_unified_logging(
    service_name="user-service",
    log_level="INFO",
    enable_json=True,      # JSON structured logging
    enable_trace=True,     # OpenTelemetry trace correlation
    enable_correlation=True # Request correlation IDs
)

# Rich logging methods
logger.log_service_startup({"version": "1.2.3", "env": "production"})
logger.log_request_start("req-123", "create_user", user_id="user-456")
logger.log_performance_metric("api_latency", 45.2, "ms", endpoint="/users")
logger.log_business_event("user_created", user_id="user-456", plan="premium")
logger.log_security_event("login_attempt", severity="warning", ip="192.168.1.100")

# Automatic context in JSON output:
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "service": "user-service",
  "trace_id": "abc123...",
  "span_id": "def456...",
  "correlation_id": "req-123",
  "message": "User created successfully",
  "user_id": "user-456",
  "plan": "premium"
}
```

## 🎯 Migration from Marty Legacy

### Before (Marty Legacy)
```python
# Old Marty imports
from marty_common.resilience import CircuitBreaker, retry_with_advanced_policy
from marty_common.logging.consolidated_logging import ServiceLogger
from tests.e2e.test_chaos_engineering import ChaosInjector

# Separate, inconsistent APIs
circuit_breaker = CircuitBreaker("service", config)
logger = ServiceLogger("service", __name__)
chaos = ChaosInjector()
```

### After (Enhanced MMF)
```python
# New unified MMF imports
from framework.resilience import EnhancedCircuitBreaker, async_retry_with_advanced_policy, ChaosInjector
from framework.logging import get_unified_logger
from framework.testing.enhanced_testing import EnhancedTestRunner

# Consistent, enhanced APIs
circuit_breaker = EnhancedCircuitBreaker("service", config)  # More features
logger = get_unified_logger("service")                       # Better structured logging
test_runner = EnhancedTestRunner("service")                  # Comprehensive testing
```

## 🔧 Key Improvements

### Resilience Enhancements
- **6 Backoff Strategies**: Constant, Linear, Exponential, Fibonacci, Random, Jittered Exponential
- **Smart Error Classification**: Configurable retryable vs non-retryable exceptions
- **Failure Rate Monitoring**: Circuit breakers with sliding windows and rate thresholds
- **Chaos Engineering**: Built-in fault injection for resilience validation
- **Graceful Degradation**: Feature toggles and fallback value providers

### Testing Enhancements
- **Contract Testing**: Endpoint validation with SLA checking
- **Chaos Engineering**: Comprehensive fault injection scenarios
- **Performance Baselines**: Automated performance regression detection
- **Quality Gates**: Configurable thresholds with automated validation
- **Rich Reporting**: Detailed test results with recommendations

### Logging Enhancements
- **JSON Structured**: Machine-readable logs with full context
- **Trace Correlation**: Automatic OpenTelemetry trace_id/span_id injection
- **Correlation IDs**: Request tracking across service boundaries
- **Service Context**: Rich service lifecycle and business event logging
- **Flexible Configuration**: Environment-based format and context control

## 📊 Quality Gates

The enhanced framework includes built-in quality gates:

- ✅ **Success Rate** ≥ 95% (configurable)
- ✅ **Average Test Duration** ≤ 10 seconds (configurable)
- ✅ **Chaos Test Coverage** ≥ 20% (configurable)
- ✅ **Performance Tests** ≥ 1 (configurable)

Quality gates are automatically validated and provide actionable recommendations.

## 🧪 Example: Complete Integration

See `examples/enhanced_integration_demo.py` for a complete demonstration showing:

- ✅ Advanced resilience patterns in action
- ✅ Comprehensive testing with all test types
- ✅ Unified logging with full context
- ✅ Chaos engineering demonstrations
- ✅ Quality gates validation

```bash
cd marty-microservices-framework
python examples/enhanced_integration_demo.py
```

## 📋 Framework Comparison

| Capability | Marty Legacy | Basic MMF | Enhanced MMF |
|------------|--------------|-----------|--------------|
| Circuit Breakers | ✅ Advanced | ✅ Basic | ✅ Enhanced + Monitoring |
| Retry Mechanisms | ✅ 4 strategies | ✅ 3 strategies | ✅ 6 strategies + Metrics |
| Chaos Engineering | ✅ Custom | ❌ None | ✅ Integrated Framework |
| Contract Testing | ✅ Custom | ❌ Basic | ✅ Enhanced with SLA |
| Performance Testing | ✅ Custom | ❌ Basic | ✅ Baseline Validation |
| Quality Gates | ✅ Custom | ❌ None | ✅ Automated Validation |
| JSON Logging | ✅ Custom | ✅ Audit Only | ✅ Unified Framework |
| Trace Correlation | ✅ Custom | ❌ Limited | ✅ Full OpenTelemetry |
| Service Lifecycle | ✅ Custom | ❌ None | ✅ Standardized Methods |
| API Consistency | ❌ Mixed | ✅ Good | ✅ Excellent |

## 🎉 Result: Complete Migration Capability

With these enhancements, **Marty can now fully migrate to MMF** without losing any existing capabilities while gaining:

- 🔄 **Standardized APIs** across all resilience, testing, and logging
- 📈 **Enhanced Capabilities** beyond what either framework provided alone
- 🎯 **Quality Assurance** with automated quality gates and comprehensive testing
- 🔍 **Better Observability** with structured logging and trace correlation
- 🛠️ **Reduced Maintenance** by consolidating into a single, well-architected framework

The enhanced MMF provides everything needed for enterprise-grade microservices development with a consistent, powerful, and well-integrated set of patterns and tools.
