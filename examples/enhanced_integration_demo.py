#!/usr/bin/env python3
"""
Example integration demonstrating how Marty services can use the enhanced MMF.

This script shows the unified APIs and demonstrates the complete integration
of resilience, logging, and testing capabilities.
"""

import asyncio
import time
from typing import Any

# Unified logging framework
from framework.logging import get_unified_logger

# Enhanced MMF imports - all the capabilities Marty needs
from framework.resilience import (  # Advanced retry with sophisticated backoff; Enhanced circuit breaker with monitoring; Chaos engineering for testing; Graceful degradation; Comprehensive outbound call resilience
    AdvancedRetryConfig,
    BackoffStrategy,
    ChaosConfig,
    ChaosType,
    DefaultValueProvider,
    EnhancedCircuitBreakerConfig,
    FeatureToggle,
    GracefulDegradationManager,
    async_call_with_resilience,
    chaos_context,
    get_circuit_breaker,
)

# Enhanced testing framework
from framework.testing.enhanced_testing import (
    ContractTestConfig,
    EnhancedTestRunner,
    PerformanceBaseline,
)


class ExampleMartyService:
    """Example service demonstrating enhanced MMF integration."""

    def __init__(self, service_name: str = "example-service"):
        # Set up unified logging with full context
        self.logger = get_unified_logger(
            service_name=service_name,
            enable_json_logging=True,
            enable_trace_context=True,
            enable_correlation=True,
        )

        # Set up resilience patterns
        self.circuit_breaker = get_circuit_breaker(
            "example_circuit",
            EnhancedCircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=30.0,
                failure_rate_threshold=0.5,
                minimum_throughput=5,
            ),
        )

        # Set up graceful degradation
        self.degradation_manager = GracefulDegradationManager()
        self.degradation_manager.add_fallback_provider(
            "user_cache", DefaultValueProvider({"id": "unknown", "name": "Anonymous User"})
        )
        self.degradation_manager.add_feature_toggle(
            "premium_features", FeatureToggle("premium_features", enabled=True)
        )

        # Set up testing framework
        self.test_runner = EnhancedTestRunner(service_name)

        self.logger.log_service_startup(
            {"version": "1.0.0", "features": ["resilience", "logging", "testing"]}
        )

    async def call_external_service(self, user_id: str) -> dict[str, Any]:
        """Example external service call with comprehensive resilience."""

        async def external_api_call() -> dict[str, Any]:
            """Simulate external API call that might fail."""
            # Simulate some processing time
            await asyncio.sleep(0.1)

            # Simulate occasional failures for demonstration
            import random

            if random.random() < 0.2:  # 20% failure rate
                raise ConnectionError("External service unavailable")

            return {"user_id": user_id, "name": f"User {user_id}", "status": "active"}

        # Configure advanced retry with jittered exponential backoff
        retry_config = AdvancedRetryConfig(
            max_attempts=3,
            base_delay=0.5,
            max_delay=5.0,
            backoff_strategy=BackoffStrategy.JITTERED_EXPONENTIAL,
            backoff_multiplier=2.0,
            jitter=True,
            retryable_exceptions=(ConnectionError, TimeoutError),
            non_retryable_exceptions=(ValueError,),
        )

        # Configure circuit breaker
        circuit_config = EnhancedCircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
            failure_rate_threshold=0.5,
        )

        try:
            # Call with comprehensive resilience patterns
            result = await async_call_with_resilience(
                external_api_call,
                retry_config=retry_config,
                circuit_breaker_config=circuit_config,
                circuit_breaker_name="external_service",
            )

            self.logger.log_request_end(
                request_id=f"req_{user_id}",
                operation="get_user",
                duration=0.1,
                success=True,
                user_id=user_id,
            )

            return result

        except Exception as e:
            # Graceful degradation - return cached/default value
            fallback_user = self.degradation_manager.get_fallback_value(
                "user_cache", {"user_id": user_id}
            )

            self.logger.log_request_end(
                request_id=f"req_{user_id}",
                operation="get_user",
                duration=0.1,
                success=False,
                error=str(e),
                fallback_used=True,
            )

            return fallback_user

    async def health_check(self) -> dict[str, Any]:
        """Service health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "circuit_breakers": {
                name: cb.get_state().value
                for name, cb in [(self.circuit_breaker.name, self.circuit_breaker)]
            },
            "features": {
                name: toggle.is_enabled()
                for name, toggle in self.degradation_manager.feature_toggles.items()
            },
        }

    async def run_comprehensive_tests(self) -> dict[str, Any]:
        """Run comprehensive test suite demonstrating enhanced testing."""

        # Contract testing
        contract_config = ContractTestConfig(
            service_name="example-service",
            endpoints=["/users/{id}", "/health"],
            expected_response_times={"/users/{id}": 1.0, "/health": 0.5},
            health_check_endpoints=["/health"],
        )

        async def contract_test_function(endpoint: str):
            """Mock contract test function."""
            if endpoint == "/health":
                return await self.health_check()
            else:
                return await self.call_external_service("test_user")

        contract_results = await self.test_runner.run_contract_tests(
            contract_config, contract_test_function
        )

        # Chaos engineering tests
        async def chaos_target():
            """Target function for chaos testing."""
            return await self.call_external_service("chaos_test_user")

        chaos_results = await self.test_runner.run_chaos_tests(
            chaos_target, "external_service_chaos_test"
        )

        # Performance testing
        performance_baseline = PerformanceBaseline(
            endpoint="/users/{id}",
            max_response_time=2.0,
            max_memory_usage=100.0,
            max_cpu_usage=50.0,
            min_throughput=10.0,
        )

        async def performance_target():
            """Target function for performance testing."""
            return await self.call_external_service("perf_test_user")

        performance_result = await self.test_runner.run_performance_tests(
            performance_target,
            performance_baseline,
            "external_service_performance",
            iterations=5,
        )

        # Generate quality report
        quality_report = self.test_runner.generate_quality_report()

        return {
            "contract_tests": len(contract_results),
            "chaos_tests": len(chaos_results),
            "performance_test": performance_result.success,
            "quality_gates": quality_report["all_gates_passed"],
            "test_summary": self.test_runner.get_test_summary(),
            "recommendations": quality_report["recommendations"],
        }

    async def demonstrate_chaos_testing(self) -> dict[str, Any]:
        """Demonstrate chaos engineering capabilities."""
        results = {}

        # Network delay chaos
        async with chaos_context(
            ChaosConfig(
                chaos_type=ChaosType.NETWORK_DELAY,
                probability=1.0,  # Always inject for demo
                duration_seconds=2.0,
                intensity=0.5,  # Moderate delay
            )
        ):
            start_time = time.time()
            try:
                result = await self.call_external_service("chaos_delay_user")
                results["network_delay"] = {
                    "success": True,
                    "duration": time.time() - start_time,
                    "result": result,
                }
            except Exception as e:  # noqa: BLE001
                results["network_delay"] = {
                    "success": False,
                    "duration": time.time() - start_time,
                    "error": str(e),
                }

        # Service failure chaos
        async with chaos_context(
            ChaosConfig(
                chaos_type=ChaosType.SERVICE_UNAVAILABLE,
                probability=1.0,  # Always inject for demo
                intensity=1.0,
            )
        ):
            start_time = time.time()
            try:
                result = await self.call_external_service("chaos_failure_user")
                results["service_failure"] = {
                    "success": True,
                    "duration": time.time() - start_time,
                    "result": result,
                }
            except Exception as e:  # noqa: BLE001
                results["service_failure"] = {
                    "success": False,
                    "duration": time.time() - start_time,
                    "error": str(e),
                }

        return results


async def main():
    """Main demonstration function."""
    print("🚀 Marty MMF Enhanced Framework Integration Demo")
    print("=" * 60)

    # Create example service
    service = ExampleMartyService("demo-service")

    print("\n📊 1. Testing normal service operation...")
    normal_result = await service.call_external_service("normal_user")
    print(f"   Result: {normal_result}")

    print("\n🔧 2. Testing health check...")
    health = await service.health_check()
    print(f"   Health: {health}")

    print("\n🧪 3. Running comprehensive test suite...")
    test_results = await service.run_comprehensive_tests()
    print(
        f"   Tests completed: {test_results['contract_tests']} contract, "
        f"{test_results['chaos_tests']} chaos"
    )
    print(f"   Quality gates passed: {test_results['quality_gates']}")
    print(f"   Recommendations: {test_results['recommendations']}")

    print("\n💥 4. Demonstrating chaos engineering...")
    chaos_results = await service.demonstrate_chaos_testing()
    print(f"   Network delay test: {'✅' if chaos_results['network_delay']['success'] else '❌'}")
    print(
        f"   Service failure test: {'✅' if chaos_results['service_failure']['success'] else '❌'}"
    )

    print("\n✅ Demo completed! The enhanced MMF provides:")
    print("   • Advanced resilience patterns (retry, circuit breaker, degradation)")
    print("   • Comprehensive testing (contract, chaos, performance, quality gates)")
    print("   • Unified structured logging (JSON, trace correlation, context)")
    print("   • All features Marty needs for complete migration to MMF")


if __name__ == "__main__":
    asyncio.run(main())
