#!/usr/bin/env python3
"""
Production Demo Runner for Marty Microservices Framework

This demonstrates production-quality services generated using official templates.
Unlike the simplified store-demo, this uses real framework components and
enterprise patterns.
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import aiohttp


class TeeOutput:
    """Capture output to both console and file"""
    def __init__(self, file_path):
        self.file = open(file_path, 'w')
        self.stdout = sys.stdout

    def write(self, data):
        self.stdout.write(data)
        self.file.write(data)
        self.file.flush()

    def flush(self):
        self.stdout.flush()
        self.file.flush()

    def close(self):
        self.file.close()

class ProductionDemoRunner:
    """Production demo runner using generated services"""

    def __init__(self):
        self.base_url = "http://localhost"
        self.services = {
            "order": f"{self.base_url}:8001",
            "payment": f"{self.base_url}:8002",
            "inventory": f"{self.base_url}:8003"
        }
        self.results = {}
        self.reports_dir = Path("reports")
        self.reports_dir.mkdir(exist_ok=True)

    async def run_demo(self):
        """Run the complete production demo"""
        print("🏭 Production Demo - Marty Microservices Framework")
        print("=" * 60)
        print("🎯 Generated Services with Enterprise Patterns")
        print("📊 Full Observability and Tracing")
        print("🔧 Production-Ready Architecture")
        print()

        try:
            # Check service health
            await self.check_services()

            # Run demo scenarios
            await self.demo_order_flow()
            await self.demo_load_testing()

            # Generate reports
            await self.generate_reports()

            print("\n✅ Production demo completed successfully!")
            print(f"📋 Reports available in: {self.reports_dir}")

        except Exception as e:
            print(f"\n❌ Demo failed: {str(e)}")
            raise

    async def check_services(self):
        """Check all services are healthy"""
        print("🔍 Checking service health...")

        for service_name, url in self.services.items():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{url}/health", timeout=5) as response:
                        if response.status == 200:
                            data = await response.json()
                            print(f"✅ {service_name.title()} Service: {data.get('status', 'healthy')}")
                        else:
                            print(f"⚠️  {service_name.title()} Service: HTTP {response.status}")
            except Exception as e:
                print(f"❌ {service_name.title()} Service: {str(e)}")
                raise ConnectionError(f"{service_name} service unavailable")

        print()

    async def demo_order_flow(self):
        """Demonstrate complete order processing flow"""
        print("📦 Demonstrating Order Processing Flow")
        print("-" * 40)

        # Sample order
        order_data = {
            "customer_id": "CUST-12345",
            "items": [
                {"product_id": "PROD-001", "quantity": 2, "price": 29.99},
                {"product_id": "PROD-002", "quantity": 1, "price": 49.99}
            ],
            "shipping_address": "123 Demo Street, Example City, EX 12345"
        }

        start_time = time.time()

        try:
            async with aiohttp.ClientSession() as session:
                # Create order
                print(f"📋 Creating order for customer {order_data['customer_id']}")

                async with session.post(
                    f"{self.services['order']}/orders",
                    json=order_data,
                    headers={"Content-Type": "application/json"}
                ) as response:

                    if response.status == 200:
                        result = await response.json()
                        processing_time = time.time() - start_time

                        print("✅ Order created successfully!")
                        print(f"   Order ID: {result.get('order_id')}")
                        print(f"   Status: {result.get('status')}")
                        print(f"   Total: ${result.get('total_amount', 0):.2f}")
                        print(f"   Processing Time: {processing_time:.2f}s")
                        print(f"   Correlation ID: {result.get('correlation_id')}")

                        # Store results
                        self.results['order_creation'] = {
                            "success": True,
                            "order_id": result.get('order_id'),
                            "processing_time_seconds": processing_time,
                            "total_amount": result.get('total_amount'),
                            "trace_info": result.get('trace_info', {})
                        }

                        # Get order status
                        await self.check_order_status(result.get('order_id'))

                    else:
                        error_text = await response.text()
                        print(f"❌ Order creation failed: HTTP {response.status}")
                        print(f"   Error: {error_text}")

                        self.results['order_creation'] = {
                            "success": False,
                            "error": f"HTTP {response.status}: {error_text}",
                            "processing_time_seconds": time.time() - start_time
                        }

        except Exception as e:
            print(f"❌ Order flow error: {str(e)}")
            self.results['order_creation'] = {
                "success": False,
                "error": str(e),
                "processing_time_seconds": time.time() - start_time
            }

        print()

    async def check_order_status(self, order_id):
        """Check order status"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.services['order']}/orders/{order_id}") as response:
                    if response.status == 200:
                        order_data = await response.json()
                        print("📋 Order Status Retrieved:")
                        print(f"   Status: {order_data.get('status')}")
                        print(f"   Created: {order_data.get('created_at')}")
                        print(f"   Payment ID: {order_data.get('payment_id')}")
                        print(f"   Reservation ID: {order_data.get('reservation_id')}")
                    else:
                        print(f"⚠️  Could not retrieve order status: HTTP {response.status}")
        except Exception as e:
            print(f"⚠️  Order status check failed: {str(e)}")

    async def demo_load_testing(self):
        """Simulate load testing"""
        print("⚡ Load Testing Simulation")
        print("-" * 30)

        num_requests = 10
        concurrent_requests = 3

        print(f"🔄 Sending {num_requests} concurrent orders ({concurrent_requests} at a time)")

        async def create_test_order(order_num):
            order_data = {
                "customer_id": f"LOAD-TEST-{order_num:03d}",
                "items": [
                    {"product_id": "LOAD-PROD-001", "quantity": 1, "price": 19.99}
                ],
                "shipping_address": f"Load Test Address {order_num}"
            }

            start_time = time.time()
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.services['order']}/orders",
                        json=order_data,
                        timeout=10
                    ) as response:
                        processing_time = time.time() - start_time
                        success = response.status == 200

                        if success:
                            result = await response.json()
                            return {
                                "order_num": order_num,
                                "success": True,
                                "processing_time": processing_time,
                                "order_id": result.get('order_id')
                            }
                        else:
                            return {
                                "order_num": order_num,
                                "success": False,
                                "processing_time": processing_time,
                                "error": f"HTTP {response.status}"
                            }
            except Exception as e:
                return {
                    "order_num": order_num,
                    "success": False,
                    "processing_time": time.time() - start_time,
                    "error": str(e)
                }

        # Run load test
        semaphore = asyncio.Semaphore(concurrent_requests)

        async def bounded_create_order(order_num):
            async with semaphore:
                return await create_test_order(order_num)

        load_start_time = time.time()

        tasks = [bounded_create_order(i) for i in range(1, num_requests + 1)]
        results = await asyncio.gather(*tasks)

        total_time = time.time() - load_start_time

        # Analyze results
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]

        if successful:
            avg_time = sum(r['processing_time'] for r in successful) / len(successful)
            max_time = max(r['processing_time'] for r in successful)
            min_time = min(r['processing_time'] for r in successful)
        else:
            avg_time = max_time = min_time = 0

        print("📊 Load Test Results:")
        print(f"   Total Requests: {num_requests}")
        print(f"   Successful: {len(successful)} ({len(successful)/num_requests*100:.1f}%)")
        print(f"   Failed: {len(failed)} ({len(failed)/num_requests*100:.1f}%)")
        print(f"   Total Time: {total_time:.2f}s")
        print(f"   Requests/sec: {num_requests/total_time:.2f}")
        print(f"   Avg Response Time: {avg_time:.3f}s")
        print(f"   Min Response Time: {min_time:.3f}s")
        print(f"   Max Response Time: {max_time:.3f}s")

        # Store load test results
        self.results['load_test'] = {
            "total_requests": num_requests,
            "successful_requests": len(successful),
            "failed_requests": len(failed),
            "success_rate": len(successful)/num_requests*100,
            "total_time_seconds": total_time,
            "requests_per_second": num_requests/total_time,
            "avg_response_time": avg_time,
            "min_response_time": min_time,
            "max_response_time": max_time,
            "detailed_results": results
        }

        print()

    async def generate_reports(self):
        """Generate demo reports"""
        print("📋 Generating Reports...")

        # Create timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save JSON report
        json_file = self.reports_dir / f"production_demo_results_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump({
                "demo_type": "production",
                "timestamp": datetime.now().isoformat(),
                "services_tested": list(self.services.keys()),
                "results": self.results,
                "summary": {
                    "total_tests": len(self.results),
                    "successful_tests": sum(1 for r in self.results.values()
                                          if isinstance(r, dict) and r.get('success', False))
                }
            }, f, indent=2)

        print(f"💾 JSON report saved: {json_file}")
        print("📊 View detailed results and metrics in the JSON file")

async def main():
    """Main demo runner"""
    # Setup output capture
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    text_output_file = reports_dir / f"production_demo_output_{timestamp}.txt"

    # Redirect output to both console and file
    original_stdout = sys.stdout
    sys.stdout = TeeOutput(text_output_file)

    try:
        demo = ProductionDemoRunner()
        await demo.run_demo()
    finally:
        # Restore original stdout
        if hasattr(sys.stdout, 'close'):
            sys.stdout.close()
        sys.stdout = original_stdout

        print(f"\n📄 Complete output saved: {text_output_file}")

if __name__ == "__main__":
    asyncio.run(main())
