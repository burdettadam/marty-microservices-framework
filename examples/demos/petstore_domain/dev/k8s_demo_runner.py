#!/usr/bin/env python3
"""
Enhanced Petstore Kubernetes Demo Runner
Demonstrates all MMF capabilities in a Kubernetes environment
"""

import argparse
import asyncio
import json
import logging
import os
import random
import time
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PetstoreKubernetesDemoRunner:
    """Demo runner for the enhanced petstore on Kubernetes"""

    def __init__(self, base_url: str = "http://localhost:30080"):
        self.base_url = base_url.rstrip('/')
        self.api_base = f"{self.base_url}/petstore-domain"
        self.session: Optional[aiohttp.ClientSession] = None
        self.correlation_id = f"demo-{int(time.time())}"

        # Demo scenarios configuration
        self.demo_scenarios = [
            "health_check",
            "feature_flags_demo",
            "pet_browsing",
            "order_processing_saga",
            "resilience_patterns",
            "observability_demo",
            "security_demo",
            "caching_demo",
            "configuration_demo"
        ]

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'Content-Type': 'application/json',
                'X-Correlation-ID': self.correlation_id,
                'User-Agent': 'PetstoreKubernetesDemo/1.0'
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make HTTP request with error handling"""
        url = f"{self.api_base}{endpoint}"

        try:
            async with self.session.request(method, url, **kwargs) as response:
                content_type = response.headers.get('Content-Type', '')

                if 'application/json' in content_type:
                    data = await response.json()
                else:
                    text = await response.text()
                    data = {'response': text}

                return {
                    'status': response.status,
                    'data': data,
                    'headers': dict(response.headers)
                }

        except Exception as e:
            logger.error(f"Request failed for {method} {url}: {e}")
            return {
                'status': 500,
                'data': {'error': str(e)},
                'headers': {}
            }

    def print_section(self, title: str, description: str = ""):
        """Print formatted section header"""
        print(f"\n{'='*80}")
        print(f"🚀 {title}")
        if description:
            print(f"   {description}")
        print(f"{'='*80}")

    def print_result(self, result: Dict, title: str = ""):
        """Print formatted result"""
        status = result.get('status', 'unknown')
        status_emoji = "✅" if status == 200 else "❌" if status >= 400 else "⚠️"

        print(f"\n{status_emoji} {title} (Status: {status})")

        if result.get('data'):
            print(f"📄 Response: {json.dumps(result['data'], indent=2)}")

        # Show correlation tracking
        headers = result.get('headers', {})
        if 'x-correlation-id' in headers:
            print(f"🔗 Correlation ID: {headers['x-correlation-id']}")
        if 'x-request-id' in headers:
            print(f"🆔 Request ID: {headers['x-request-id']}")

    async def health_check_demo(self):
        """Test health check endpoint"""
        self.print_section(
            "Health Check Demo",
            "Testing service health and readiness"
        )

        result = await self.make_request('GET', '/health')
        self.print_result(result, "Health Check")

        # Test detailed health
        result = await self.make_request('GET', '/health/detailed')
        self.print_result(result, "Detailed Health Check")

    async def feature_flags_demo(self):
        """Demonstrate feature flags"""
        self.print_section(
            "Feature Flags Demo",
            "Testing dynamic feature flag behavior"
        )

        # Test feature flag endpoint
        result = await self.make_request('GET', '/features')
        self.print_result(result, "Feature Flags List")

        # Test specific feature
        result = await self.make_request('GET', '/features/enhanced_recommendations')
        self.print_result(result, "Enhanced Recommendations Feature")

    async def pet_browsing_demo(self):
        """Demonstrate pet browsing with caching"""
        self.print_section(
            "Pet Browsing Demo",
            "Testing pet browsing with Redis caching and metrics"
        )

        # Browse pets (should hit cache on subsequent calls)
        for i in range(3):
            result = await self.make_request('GET', '/pets/browse')
            self.print_result(result, f"Pet Browse (Call {i+1})")
            await asyncio.sleep(1)

        # Search pets
        result = await self.make_request('GET', '/pets/search?category=dog&available=true')
        self.print_result(result, "Pet Search")

        # Get specific pet
        result = await self.make_request('GET', '/pets/1')
        self.print_result(result, "Get Pet by ID")

    async def order_processing_saga_demo(self):
        """Demonstrate saga-based order processing"""
        self.print_section(
            "Order Processing Saga Demo",
            "Testing event-driven order processing with compensation"
        )

        # Create a successful order
        order_data = {
            "pet_id": 1,
            "quantity": 2,
            "customer_id": f"customer-{random.randint(1000, 9999)}",
            "special_requests": "Please include a toy"
        }

        result = await self.make_request('POST', '/orders', json=order_data)
        self.print_result(result, "Create Order (Success Path)")

        if result['status'] == 200:
            order_id = result['data'].get('order_id')
            if order_id:
                # Check order status
                await asyncio.sleep(2)
                result = await self.make_request('GET', f'/orders/{order_id}')
                self.print_result(result, "Order Status Check")

        # Create a failing order to demonstrate compensation
        failing_order = {
            "pet_id": 99999,  # Non-existent pet
            "quantity": 1,
            "customer_id": "test-customer"
        }

        result = await self.make_request('POST', '/orders', json=failing_order)
        self.print_result(result, "Create Order (Failure Path)")

    async def resilience_patterns_demo(self):
        """Demonstrate resilience patterns"""
        self.print_section(
            "Resilience Patterns Demo",
            "Testing circuit breakers, retries, and timeouts"
        )

        # Test circuit breaker with multiple rapid calls
        for i in range(5):
            result = await self.make_request('GET', '/pets/recommendations')
            self.print_result(result, f"Recommendations (Circuit Breaker Test {i+1})")
            await asyncio.sleep(0.5)

        # Test timeout behavior
        result = await self.make_request('GET', '/pets/slow-operation')
        self.print_result(result, "Slow Operation (Timeout Test)")

    async def observability_demo(self):
        """Demonstrate observability features"""
        self.print_section(
            "Observability Demo",
            "Testing metrics, tracing, and logging"
        )

        # Generate various operations for observability
        operations = [
            ('GET', '/pets/browse'),
            ('GET', '/pets/1'),
            ('GET', '/orders/recent'),
            ('GET', '/analytics/popular-pets'),
        ]

        for method, endpoint in operations:
            result = await self.make_request(method, endpoint)
            self.print_result(result, f"Operation: {method} {endpoint}")
            await asyncio.sleep(1)

        # Get metrics
        result = await self.make_request('GET', '/metrics')
        self.print_result(result, "Prometheus Metrics")

    async def security_demo(self):
        """Demonstrate security features"""
        self.print_section(
            "Security Demo",
            "Testing rate limiting and authentication"
        )

        # Test rate limiting by making rapid requests
        print("Testing rate limiting with rapid requests...")
        for i in range(10):
            result = await self.make_request('GET', '/pets/browse')
            status = result.get('status')
            if status == 429:
                print(f"⚠️ Rate limit hit after {i+1} requests")
                break
            await asyncio.sleep(0.1)

        # Test protected endpoint
        result = await self.make_request('GET', '/admin/stats')
        self.print_result(result, "Protected Admin Endpoint (No Auth)")

    async def caching_demo(self):
        """Demonstrate Redis caching"""
        self.print_section(
            "Caching Demo",
            "Testing Redis cache performance"
        )

        # Clear cache first
        result = await self.make_request('POST', '/cache/clear')
        self.print_result(result, "Cache Clear")

        # First call (cache miss)
        start_time = time.time()
        result = await self.make_request('GET', '/pets/popular')
        first_call_time = time.time() - start_time
        self.print_result(result, f"Popular Pets (Cache Miss) - {first_call_time:.3f}s")

        # Second call (cache hit)
        start_time = time.time()
        result = await self.make_request('GET', '/pets/popular')
        second_call_time = time.time() - start_time
        self.print_result(result, f"Popular Pets (Cache Hit) - {second_call_time:.3f}s")

        print(f"📈 Cache speedup: {first_call_time/second_call_time:.2f}x faster")

    async def configuration_demo(self):
        """Demonstrate configuration management"""
        self.print_section(
            "Configuration Demo",
            "Testing dynamic configuration and feature flags"
        )

        # Get current configuration
        result = await self.make_request('GET', '/config/current')
        self.print_result(result, "Current Configuration")

        # Get environment info
        result = await self.make_request('GET', '/config/environment')
        self.print_result(result, "Environment Information")

    async def run_scenario(self, scenario: str):
        """Run a specific demo scenario"""
        scenario_map = {
            "health_check": self.health_check_demo,
            "feature_flags_demo": self.feature_flags_demo,
            "pet_browsing": self.pet_browsing_demo,
            "order_processing_saga": self.order_processing_saga_demo,
            "resilience_patterns": self.resilience_patterns_demo,
            "observability_demo": self.observability_demo,
            "security_demo": self.security_demo,
            "caching_demo": self.caching_demo,
            "configuration_demo": self.configuration_demo,
        }

        if scenario in scenario_map:
            await scenario_map[scenario]()
        else:
            logger.error(f"Unknown scenario: {scenario}")

    async def run_full_demo(self):
        """Run all demo scenarios"""
        print(f"""
🐾 Enhanced Petstore Kubernetes Demo
🔗 Correlation ID: {self.correlation_id}
🎯 Target: {self.api_base}
⏰ Started: {datetime.now().isoformat()}
""")

        # Wait for service to be ready
        print("🔄 Waiting for service to be ready...")
        max_retries = 30
        for i in range(max_retries):
            try:
                result = await self.make_request('GET', '/health')
                if result['status'] == 200:
                    print("✅ Service is ready!")
                    break
            except:
                pass

            if i == max_retries - 1:
                print("❌ Service not ready after maximum retries")
                return

            print(f"⏳ Waiting... ({i+1}/{max_retries})")
            await asyncio.sleep(2)

        # Run all scenarios
        for scenario in self.demo_scenarios:
            try:
                await self.run_scenario(scenario)
                await asyncio.sleep(2)  # Pause between scenarios
            except Exception as e:
                logger.error(f"Error in scenario {scenario}: {e}")

        self.print_section(
            "Demo Complete! 🎉",
            "Check the monitoring dashboards for observability data"
        )

        print(f"""
📊 Monitoring URLs:
   • Grafana:    http://localhost:30030 (admin/admin)
   • Prometheus: http://localhost:30090
   • Jaeger:     http://localhost:30686

🔧 Debug Commands:
   kubectl logs -f deployment/petstore-domain -n petstore
   kubectl get pods -n petstore
   kubectl describe pod <pod-name> -n petstore
""")

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Enhanced Petstore Kubernetes Demo')
    parser.add_argument('--url', default='http://localhost:30080',
                       help='Base URL for the petstore service')
    parser.add_argument('--scenario', choices=['all'] + [
        'health_check', 'feature_flags_demo', 'pet_browsing',
        'order_processing_saga', 'resilience_patterns', 'observability_demo',
        'security_demo', 'caching_demo', 'configuration_demo'
    ], default='all', help='Scenario to run')
    parser.add_argument('--repeat', type=int, default=1,
                       help='Number of times to repeat the demo')

    args = parser.parse_args()

    for i in range(args.repeat):
        if args.repeat > 1:
            print(f"\n🔄 Demo Run {i+1}/{args.repeat}")

        async with PetstoreKubernetesDemoRunner(args.url) as demo:
            if args.scenario == 'all':
                await demo.run_full_demo()
            else:
                await demo.run_scenario(args.scenario)

        if i < args.repeat - 1:
            print(f"\n⏳ Waiting 10 seconds before next run...")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
