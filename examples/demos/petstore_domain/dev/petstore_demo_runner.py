#!/usr/bin/env python3
"""
Petstore Domain Demo Runner

This comprehensive demo runner exercises all MMF features through the petstore domain:
- Pet catalog browsing
- Order creation and processing
- Payment integration
- Delivery coordination
- Service monitoring and health checks
- Error handling and resilience patterns
- Performance testing

Run: python petstore_demo_runner.py
"""
import asyncio
import json
import logging
import random
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PetstoreTestResult:
    """Test result for petstore operations"""
    operation: str
    success: bool
    duration_ms: float
    error_message: Optional[str] = None
    correlation_id: Optional[str] = None
    order_id: Optional[str] = None


@dataclass
class PetstoreTestScenario:
    """Test scenario configuration"""
    name: str
    description: str
    operations_per_minute: int
    duration_minutes: int
    error_simulation: bool = False


class PetstoreDemoRunner:
    """
    Comprehensive demo runner for the petstore domain.

    Exercises all MMF features including:
    - Service discovery and health checks
    - Business logic execution
    - Error handling and resilience
    - Performance monitoring
    - Correlation ID tracking
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize the demo runner"""
        self.base_url = base_url
        self.session = None
        self.results: List[PetstoreTestResult] = []
        self.total_operations = 0
        self.successful_operations = 0
        self.failed_operations = 0

        # Test data
        self.customer_ids = ["customer-001", "customer-002"]
        self.pet_ids = ["golden-retriever-001", "persian-cat-002", "cockatiel-003", "goldfish-004"]
        self.payment_methods = ["credit_card", "debit_card", "paypal"]

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def check_services_health(self) -> Dict[str, Any]:
        """Check health of all petstore services"""
        logger.info("🏥 Checking service health...")

        services = [
            "petstore-domain",
            "payment-service",
            "delivery-board"
        ]

        health_results = {}

        for service in services:
            try:
                start_time = time.time()
                async with self.session.get(
                    f"{self.base_url}/api/{service}/health",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    duration_ms = (time.time() - start_time) * 1000

                    if response.status == 200:
                        health_data = await response.json()
                        health_results[service] = {
                            "status": "healthy",
                            "response_time_ms": duration_ms,
                            "details": health_data
                        }
                        logger.info(f"✅ {service}: healthy ({duration_ms:.1f}ms)")
                    else:
                        health_results[service] = {
                            "status": "unhealthy",
                            "response_time_ms": duration_ms,
                            "error": f"HTTP {response.status}"
                        }
                        logger.warning(f"❌ {service}: unhealthy (HTTP {response.status})")

            except Exception as e:
                health_results[service] = {
                    "status": "error",
                    "error": str(e)
                }
                logger.error(f"💥 {service}: error - {e}")

        return health_results

    async def browse_pets(self, category: str = None, max_price: float = None, correlation_id: str = None) -> PetstoreTestResult:
        """Test pet browsing functionality"""
        start_time = time.time()

        try:
            params = {}
            if category:
                params['category'] = category
            if max_price:
                params['max_price'] = max_price
            if correlation_id:
                params['correlation_id'] = correlation_id

            async with self.session.get(
                f"{self.base_url}/api/petstore-domain/browse-pets",
                params=params,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                duration_ms = (time.time() - start_time) * 1000

                if response.status == 200:
                    data = await response.json()
                    return PetstoreTestResult(
                        operation="browse_pets",
                        success=True,
                        duration_ms=duration_ms,
                        correlation_id=data.get('correlation_id')
                    )
                else:
                    error_text = await response.text()
                    return PetstoreTestResult(
                        operation="browse_pets",
                        success=False,
                        duration_ms=duration_ms,
                        error_message=f"HTTP {response.status}: {error_text}"
                    )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return PetstoreTestResult(
                operation="browse_pets",
                success=False,
                duration_ms=duration_ms,
                error_message=str(e)
            )

    async def get_pet_details(self, pet_id: str, correlation_id: str = None) -> PetstoreTestResult:
        """Test pet details retrieval"""
        start_time = time.time()

        try:
            params = {'pet_id': pet_id}
            if correlation_id:
                params['correlation_id'] = correlation_id

            async with self.session.get(
                f"{self.base_url}/api/petstore-domain/pet-details",
                params=params,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                duration_ms = (time.time() - start_time) * 1000

                if response.status == 200:
                    data = await response.json()
                    return PetstoreTestResult(
                        operation="get_pet_details",
                        success=True,
                        duration_ms=duration_ms,
                        correlation_id=data.get('correlation_id')
                    )
                else:
                    error_text = await response.text()
                    return PetstoreTestResult(
                        operation="get_pet_details",
                        success=False,
                        duration_ms=duration_ms,
                        error_message=f"HTTP {response.status}: {error_text}"
                    )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return PetstoreTestResult(
                operation="get_pet_details",
                success=False,
                duration_ms=duration_ms,
                error_message=str(e)
            )

    async def create_order(self, customer_id: str, pet_id: str, special_instructions: str = "", correlation_id: str = None) -> PetstoreTestResult:
        """Test order creation"""
        start_time = time.time()

        try:
            payload = {
                'customer_id': customer_id,
                'pet_id': pet_id,
                'special_instructions': special_instructions
            }
            if correlation_id:
                payload['correlation_id'] = correlation_id

            async with self.session.post(
                f"{self.base_url}/api/petstore-domain/create-order",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                duration_ms = (time.time() - start_time) * 1000

                if response.status == 200:
                    data = await response.json()
                    order_id = data.get('order', {}).get('order_id')
                    return PetstoreTestResult(
                        operation="create_order",
                        success=True,
                        duration_ms=duration_ms,
                        correlation_id=data.get('correlation_id'),
                        order_id=order_id
                    )
                else:
                    error_text = await response.text()
                    return PetstoreTestResult(
                        operation="create_order",
                        success=False,
                        duration_ms=duration_ms,
                        error_message=f"HTTP {response.status}: {error_text}"
                    )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return PetstoreTestResult(
                operation="create_order",
                success=False,
                duration_ms=duration_ms,
                error_message=str(e)
            )

    async def process_payment(self, order_id: str, payment_method: str, correlation_id: str = None) -> PetstoreTestResult:
        """Test payment processing"""
        start_time = time.time()

        try:
            payload = {
                'order_id': order_id,
                'payment_method': payment_method
            }
            if correlation_id:
                payload['correlation_id'] = correlation_id

            async with self.session.post(
                f"{self.base_url}/api/petstore-domain/process-payment",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                duration_ms = (time.time() - start_time) * 1000

                if response.status == 200:
                    data = await response.json()
                    return PetstoreTestResult(
                        operation="process_payment",
                        success=True,
                        duration_ms=duration_ms,
                        correlation_id=data.get('correlation_id'),
                        order_id=order_id
                    )
                else:
                    error_text = await response.text()
                    return PetstoreTestResult(
                        operation="process_payment",
                        success=False,
                        duration_ms=duration_ms,
                        error_message=f"HTTP {response.status}: {error_text}",
                        order_id=order_id
                    )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return PetstoreTestResult(
                operation="process_payment",
                success=False,
                duration_ms=duration_ms,
                error_message=str(e),
                order_id=order_id
            )

    async def get_order_status(self, order_id: str, correlation_id: str = None) -> PetstoreTestResult:
        """Test order status retrieval"""
        start_time = time.time()

        try:
            params = {'order_id': order_id}
            if correlation_id:
                params['correlation_id'] = correlation_id

            async with self.session.get(
                f"{self.base_url}/api/petstore-domain/order-status",
                params=params,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                duration_ms = (time.time() - start_time) * 1000

                if response.status == 200:
                    data = await response.json()
                    return PetstoreTestResult(
                        operation="get_order_status",
                        success=True,
                        duration_ms=duration_ms,
                        correlation_id=data.get('correlation_id'),
                        order_id=order_id
                    )
                else:
                    error_text = await response.text()
                    return PetstoreTestResult(
                        operation="get_order_status",
                        success=False,
                        duration_ms=duration_ms,
                        error_message=f"HTTP {response.status}: {error_text}",
                        order_id=order_id
                    )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return PetstoreTestResult(
                operation="get_order_status",
                success=False,
                duration_ms=duration_ms,
                error_message=str(e),
                order_id=order_id
            )

    async def run_complete_customer_journey(self, customer_id: str = None, correlation_id: str = None) -> List[PetstoreTestResult]:
        """Run a complete customer journey from browsing to order tracking"""
        if customer_id is None:
            customer_id = random.choice(self.customer_ids)
        if correlation_id is None:
            correlation_id = f"journey-{int(time.time())}-{random.randint(1000, 9999)}"

        logger.info(f"🛒 Starting customer journey for {customer_id} [{correlation_id}]")

        journey_results = []

        # Step 1: Browse pets
        logger.info(f"  📱 Step 1: Browsing pets...")
        browse_result = await self.browse_pets(correlation_id=correlation_id)
        journey_results.append(browse_result)

        if not browse_result.success:
            logger.error(f"  ❌ Browse failed: {browse_result.error_message}")
            return journey_results

        # Step 2: Get pet details
        pet_id = random.choice(self.pet_ids)
        logger.info(f"  🐾 Step 2: Getting details for {pet_id}...")
        details_result = await self.get_pet_details(pet_id, correlation_id=correlation_id)
        journey_results.append(details_result)

        if not details_result.success:
            logger.error(f"  ❌ Pet details failed: {details_result.error_message}")
            return journey_results

        # Step 3: Create order
        special_instructions = random.choice([
            "Please handle with care",
            "Delivery between 9-12 AM",
            "Call before delivery",
            "Leave at front door",
            ""
        ])
        logger.info(f"  📦 Step 3: Creating order...")
        order_result = await self.create_order(customer_id, pet_id, special_instructions, correlation_id=correlation_id)
        journey_results.append(order_result)

        if not order_result.success:
            logger.error(f"  ❌ Order creation failed: {order_result.error_message}")
            return journey_results

        order_id = order_result.order_id
        logger.info(f"  ✅ Order created: {order_id}")

        # Step 4: Process payment
        payment_method = random.choice(self.payment_methods)
        logger.info(f"  💳 Step 4: Processing payment with {payment_method}...")
        payment_result = await self.process_payment(order_id, payment_method, correlation_id=correlation_id)
        journey_results.append(payment_result)

        if not payment_result.success:
            logger.warning(f"  ⚠️ Payment failed: {payment_result.error_message}")
        else:
            logger.info(f"  ✅ Payment processed successfully")

        # Step 5: Check order status
        logger.info(f"  📋 Step 5: Checking order status...")
        status_result = await self.get_order_status(order_id, correlation_id=correlation_id)
        journey_results.append(status_result)

        if status_result.success:
            logger.info(f"  ✅ Journey completed successfully for {customer_id}")
        else:
            logger.error(f"  ❌ Status check failed: {status_result.error_message}")

        return journey_results

    async def run_scenario(self, scenario: PetstoreTestScenario) -> Dict[str, Any]:
        """Run a test scenario"""
        logger.info(f"🎭 Running scenario: {scenario.name}")
        logger.info(f"   Description: {scenario.description}")
        logger.info(f"   Operations per minute: {scenario.operations_per_minute}")
        logger.info(f"   Duration: {scenario.duration_minutes} minutes")

        scenario_results = []
        start_time = time.time()
        operations_interval = 60.0 / scenario.operations_per_minute  # seconds between operations

        scenario_end_time = start_time + (scenario.duration_minutes * 60)

        operation_count = 0
        while time.time() < scenario_end_time:
            operation_start = time.time()

            # Run a customer journey
            journey_results = await self.run_complete_customer_journey()
            scenario_results.extend(journey_results)
            operation_count += 1

            # Calculate how long to wait before next operation
            operation_duration = time.time() - operation_start
            wait_time = max(0, operations_interval - operation_duration)

            if wait_time > 0:
                await asyncio.sleep(wait_time)

        scenario_duration = time.time() - start_time

        # Calculate statistics
        successful_ops = sum(1 for r in scenario_results if r.success)
        failed_ops = len(scenario_results) - successful_ops
        avg_duration = sum(r.duration_ms for r in scenario_results) / len(scenario_results) if scenario_results else 0

        scenario_summary = {
            "scenario": scenario.name,
            "duration_seconds": scenario_duration,
            "total_operations": len(scenario_results),
            "successful_operations": successful_ops,
            "failed_operations": failed_ops,
            "success_rate": (successful_ops / len(scenario_results)) * 100 if scenario_results else 0,
            "average_duration_ms": avg_duration,
            "operations_per_second": len(scenario_results) / scenario_duration,
            "customer_journeys": operation_count
        }

        logger.info(f"📊 Scenario '{scenario.name}' completed:")
        logger.info(f"   Total operations: {scenario_summary['total_operations']}")
        logger.info(f"   Success rate: {scenario_summary['success_rate']:.1f}%")
        logger.info(f"   Average duration: {scenario_summary['average_duration_ms']:.1f}ms")
        logger.info(f"   Ops/second: {scenario_summary['operations_per_second']:.2f}")

        return scenario_summary

    async def run_comprehensive_demo(self) -> Dict[str, Any]:
        """Run the comprehensive petstore demo"""
        logger.info("🚀 Starting Petstore Domain Comprehensive Demo")
        logger.info("=" * 60)

        demo_start_time = time.time()

        # Phase 1: Health checks
        logger.info("📋 Phase 1: Service Health Checks")
        health_results = await self.check_services_health()

        # Check if all services are healthy
        all_healthy = all(
            result.get('status') == 'healthy'
            for result in health_results.values()
        )

        if not all_healthy:
            logger.warning("⚠️ Some services are not healthy, but continuing with demo...")

        # Phase 2: Single customer journey
        logger.info("\n📋 Phase 2: Single Customer Journey Test")
        single_journey = await self.run_complete_customer_journey()

        # Phase 3: Light load testing
        logger.info("\n📋 Phase 3: Light Load Testing")
        light_load_scenario = PetstoreTestScenario(
            name="Light Load",
            description="Steady customer activity",
            operations_per_minute=5,
            duration_minutes=2
        )
        light_load_results = await self.run_scenario(light_load_scenario)

        # Phase 4: Burst testing
        logger.info("\n📋 Phase 4: Burst Load Testing")
        burst_scenario = PetstoreTestScenario(
            name="Burst Load",
            description="High customer activity burst",
            operations_per_minute=15,
            duration_minutes=1
        )
        burst_results = await self.run_scenario(burst_scenario)

        # Phase 5: Final health check
        logger.info("\n📋 Phase 5: Final Service Health Check")
        final_health = await self.check_services_health()

        demo_duration = time.time() - demo_start_time

        # Compile final report
        demo_report = {
            "demo_duration_seconds": demo_duration,
            "timestamp": datetime.utcnow().isoformat(),
            "initial_health_check": health_results,
            "final_health_check": final_health,
            "single_journey_operations": len(single_journey),
            "single_journey_success_rate": (sum(1 for r in single_journey if r.success) / len(single_journey)) * 100 if single_journey else 0,
            "light_load_scenario": light_load_results,
            "burst_load_scenario": burst_results,
            "mmf_features_exercised": [
                "service_health_monitoring",
                "correlation_id_tracking",
                "business_logic_execution",
                "error_handling",
                "performance_testing",
                "load_balancing",
                "async_operations",
                "comprehensive_logging"
            ]
        }

        logger.info("\n" + "=" * 60)
        logger.info("🎉 Petstore Domain Demo Completed Successfully!")
        logger.info(f"📊 Demo Duration: {demo_duration:.1f} seconds")
        logger.info(f"🎯 Single Journey Success Rate: {demo_report['single_journey_success_rate']:.1f}%")
        logger.info(f"🔥 Light Load Success Rate: {light_load_results['success_rate']:.1f}%")
        logger.info(f"💥 Burst Load Success Rate: {burst_results['success_rate']:.1f}%")
        logger.info("=" * 60)

        return demo_report


async def main():
    """Main demo execution"""
    print("🏪 Petstore Domain Demo Runner")
    print("=" * 50)
    print("This demo will exercise all MMF features through the petstore domain:")
    print("• Service health monitoring")
    print("• Pet catalog browsing")
    print("• Order creation and processing")
    print("• Payment integration")
    print("• Load testing and performance")
    print("• Error handling and resilience")
    print("• Correlation ID tracking")
    print("=" * 50)

    # Check if services are running
    base_url = "http://localhost:8000"
    print(f"\n🔍 Testing connection to {base_url}...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/health", timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    print("✅ Services are running!")
                else:
                    print(f"⚠️ Got HTTP {response.status}, but continuing...")
    except Exception as e:
        print(f"❌ Cannot connect to services: {e}")
        print("💡 Make sure to start the services first:")
        print("   cd plugins/petstore_domain")
        print("   ./dev/run_services.sh")
        return

    print("\n🚀 Starting comprehensive demo in 3 seconds...")
    await asyncio.sleep(3)

    async with PetstoreDemoRunner(base_url) as demo_runner:
        demo_report = await demo_runner.run_comprehensive_demo()

        # Save report to file
        report_filename = f"petstore_demo_report_{int(time.time())}.json"
        with open(report_filename, 'w') as f:
            json.dump(demo_report, f, indent=2)

        print(f"\n📄 Demo report saved to: {report_filename}")


if __name__ == "__main__":
    asyncio.run(main())
