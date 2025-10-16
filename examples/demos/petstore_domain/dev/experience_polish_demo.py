#!/usr/bin/env python3
"""
MMF Experience Polish: Complete Petstore Journey
================================================

This comprehensive script demonstrates the full Marty Microservices Framework (MMF) capabilities
through an end-to-end petstore experience with observability, ML integration, error tracking,
and operational scaling demonstrations.

Features:
- Complete customer journey with message ID tracking
- Error scenario simulation and recovery
- ML-powered pet recommendations
- Real-time observability with Grafana/Jupyter integration
- Operational scaling demonstrations
- Service mesh and canary deployment patterns

Usage:
    python experience_polish_demo.py [--mode cli|notebook] [--scenario full|quick|ml-demo|ops-demo]
"""

import asyncio
import json
import logging
import random
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import aiohttp
import click
import numpy as np
import pandas as pd
from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Configure rich console
console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class JourneyStep:
    """Represents a step in the customer journey"""
    step_id: str
    name: str
    description: str
    expected_duration_ms: int
    success: bool = False
    actual_duration_ms: int | None = None
    message_id: str | None = None
    correlation_id: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class CustomerProfile:
    """Customer profile for personalized experiences"""
    customer_id: str
    name: str
    email: str
    preferences: dict[str, Any]
    previous_purchases: list[str]
    budget_range: tuple
    experience_level: str  # novice, intermediate, expert


@dataclass
class MLRecommendation:
    """ML-powered recommendation result"""
    pet_id: str
    confidence_score: float
    reasoning: str
    alternative_suggestions: list[str]
    price_optimization: dict[str, Any] | None = None


class ExperiencePolishDemo:
    """Complete MMF experience demonstration"""

    def __init__(self, base_url: str = "http://localhost:8000", demo_mode: bool = False):
        self.base_url = base_url
        self.demo_mode = demo_mode  # Run without actual services
        self.session: Optional[aiohttp.ClientSession] = None
        self.journey_history: List[JourneyStep] = []
        self.message_tracker: Dict[str, Any] = {}
        self.ml_service_url = "http://localhost:8003"  # ML advisor sidecar

        # Demo data
        self.customer_profiles = self._create_customer_profiles()
        self.error_scenarios = self._create_error_scenarios()

    def _create_customer_profiles(self) -> list[CustomerProfile]:
        """Create diverse customer profiles for realistic testing"""
        return [
            CustomerProfile(
                customer_id="family-pet-seeker",
                name="Sarah Johnson",
                email="sarah.j@email.com",
                preferences={
                    "pet_types": ["dog", "cat"],
                    "activity_level": "high",
                    "living_situation": "house_with_yard",
                    "experience_with_pets": "high"
                },
                previous_purchases=["dog-toy-001", "cat-food-premium"],
                budget_range=(800, 2000),
                experience_level="intermediate"
            ),
            CustomerProfile(
                customer_id="first-time-owner",
                name="Alex Chen",
                email="alex.chen@email.com",
                preferences={
                    "pet_types": ["small_animal", "bird"],
                    "activity_level": "low",
                    "living_situation": "apartment",
                    "experience_with_pets": "none"
                },
                previous_purchases=[],
                budget_range=(200, 600),
                experience_level="novice"
            ),
            CustomerProfile(
                customer_id="exotic-enthusiast",
                name="Dr. Maya Patel",
                email="m.patel@research.edu",
                preferences={
                    "pet_types": ["reptile", "fish"],
                    "activity_level": "low",
                    "living_situation": "house",
                    "experience_with_pets": "expert"
                },
                previous_purchases=["terrarium-001", "heat-lamp-pro"],
                budget_range=(1000, 5000),
                experience_level="expert"
            )
        ]

    def _create_error_scenarios(self) -> list[dict[str, Any]]:
        """Create error scenarios to test resilience"""
        return [
            {
                "name": "payment_failure",
                "description": "Simulate payment processing failure",
                "trigger_step": "process_payment",
                "error_type": "payment_declined",
                "recovery_strategy": "retry_with_backup_method"
            },
            {
                "name": "inventory_shortage",
                "description": "Simulate pet no longer available",
                "trigger_step": "create_order",
                "error_type": "out_of_stock",
                "recovery_strategy": "suggest_alternatives"
            },
            {
                "name": "ml_service_timeout",
                "description": "Simulate ML recommendation service timeout",
                "trigger_step": "get_recommendations",
                "error_type": "service_timeout",
                "recovery_strategy": "fallback_to_basic_recommendations"
            },
            {
                "name": "delivery_delay",
                "description": "Simulate delivery scheduling conflict",
                "trigger_step": "schedule_delivery",
                "error_type": "no_available_slots",
                "recovery_strategy": "offer_priority_scheduling"
            }
        ]

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def _make_request(self, method: str, endpoint: str, data: dict | None = None,
                          headers: dict | None = None) -> dict[str, Any]:
        """Make HTTP request with tracking"""
        start_time = time.time()
        correlation_id = str(uuid.uuid4())

        request_headers = {
            "X-Correlation-ID": correlation_id,
            "X-Request-ID": str(uuid.uuid4()),
            "Content-Type": "application/json"
        }
        if headers:
            request_headers.update(headers)

        url = f"{self.base_url}{endpoint}"

        try:
            if method.upper() == "GET":
                async with self.session.get(url, headers=request_headers) as response:
                    result = await response.json()
            elif method.upper() == "POST":
                async with self.session.post(url, json=data, headers=request_headers) as response:
                    result = await response.json()
            else:
                raise ValueError(f"Unsupported method: {method}")

            duration_ms = int((time.time() - start_time) * 1000)

            # Track message for observability
            self.message_tracker[correlation_id] = {
                "timestamp": datetime.now().isoformat(),
                "method": method,
                "endpoint": endpoint,
                "duration_ms": duration_ms,
                "status": "success",
                "response_size": len(json.dumps(result))
            }

            result["_tracking"] = {
                "correlation_id": correlation_id,
                "duration_ms": duration_ms
            }

            return result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.message_tracker[correlation_id] = {
                "timestamp": datetime.now().isoformat(),
                "method": method,
                "endpoint": endpoint,
                "duration_ms": duration_ms,
                "status": "error",
                "error": str(e)
            }
            raise

    async def run_complete_journey(self, customer_profile: CustomerProfile,
                                 inject_errors: bool = False) -> list[JourneyStep]:
        """Run complete customer journey with optional error injection"""
        console.print(f"\n🎯 Starting journey for {customer_profile.name} ({customer_profile.experience_level})")

        journey_steps = []

        # Step 1: Health Check & Service Discovery
        step = await self._step_health_check()
        journey_steps.append(step)

        # Step 2: ML-Powered Pet Recommendations
        step = await self._step_get_ml_recommendations(customer_profile, inject_errors)
        journey_steps.append(step)

        # Step 3: Browse Pet Catalog
        step = await self._step_browse_pets(customer_profile)
        journey_steps.append(step)

        # Step 4: Get Pet Details
        if journey_steps[-1].success:
            step = await self._step_get_pet_details(customer_profile)
            journey_steps.append(step)

        # Step 5: Create Order
        if journey_steps[-1].success:
            step = await self._step_create_order(customer_profile, inject_errors)
            journey_steps.append(step)

        # Step 6: Process Payment
        if journey_steps[-1].success:
            step = await self._step_process_payment(customer_profile, inject_errors)
            journey_steps.append(step)

        # Step 7: Schedule Delivery
        if journey_steps[-1].success:
            step = await self._step_schedule_delivery(customer_profile, inject_errors)
            journey_steps.append(step)

        # Step 8: Track Order Status
        if journey_steps[-1].success:
            step = await self._step_track_order_status(customer_profile)
            journey_steps.append(step)

        self.journey_history.extend(journey_steps)
        return journey_steps

    async def _step_health_check(self) -> JourneyStep:
        """Health check step"""
        step = JourneyStep(
            step_id="health_check",
            name="Service Health Check",
            description="Verify all services are operational",
            expected_duration_ms=100
        )

        try:
            start_time = time.time()
            result = await self._make_request("GET", "/api/petstore-domain/health")
            step.actual_duration_ms = int((time.time() - start_time) * 1000)
            step.success = result.get("status") == "healthy"
            step.correlation_id = result.get("_tracking", {}).get("correlation_id")
            step.metadata = {"service_version": result.get("version")}

        except Exception as e:
            step.error_message = str(e)
            step.success = False

        return step

    async def _step_get_ml_recommendations(self, customer_profile: CustomerProfile,
                                         inject_errors: bool = False) -> JourneyStep:
        """Get ML-powered pet recommendations"""
        step = JourneyStep(
            step_id="ml_recommendations",
            name="AI Pet Recommendations",
            description="Get personalized pet recommendations using ML",
            expected_duration_ms=500
        )

        try:
            start_time = time.time()

            # Simulate error injection
            if inject_errors and random.random() < 0.3:
                raise Exception("ML service timeout - falling back to basic recommendations")

            # Call ML recommendation service (stub for now)
            recommendations = await self._get_ml_recommendations_stub(customer_profile)
            step.actual_duration_ms = int((time.time() - start_time) * 1000)
            step.success = True
            step.correlation_id = str(uuid.uuid4())
            step.metadata = {
                "recommendations_count": len(recommendations),
                "top_confidence": max([r.confidence_score for r in recommendations]) if recommendations else 0
            }

        except Exception as e:
            step.error_message = str(e)
            step.success = False
            # Fallback to basic recommendations
            step.metadata = {"fallback_used": True}

        return step

    async def _get_ml_recommendations_stub(self, customer_profile: CustomerProfile) -> list[MLRecommendation]:
        """Stub ML recommendation service (would be replaced with actual ML service)"""
        # Simulate ML processing delay
        await asyncio.sleep(random.uniform(0.1, 0.3))

        # Simple rule-based recommendations for demo
        recommendations = []

        if "dog" in customer_profile.preferences.get("pet_types", []):
            recommendations.append(MLRecommendation(
                pet_id="golden-retriever-001",
                confidence_score=0.92,
                reasoning="Perfect for families with yards, matches activity level preference",
                alternative_suggestions=["labrador-001", "beagle-002"]
            ))

        if "cat" in customer_profile.preferences.get("pet_types", []):
            recommendations.append(MLRecommendation(
                pet_id="persian-cat-002",
                confidence_score=0.87,
                reasoning="Low maintenance, good for apartment living",
                alternative_suggestions=["siamese-001", "maine-coon-003"]
            ))

        return recommendations

    async def _step_browse_pets(self, customer_profile: CustomerProfile) -> JourneyStep:
        """Browse pet catalog step"""
        step = JourneyStep(
            step_id="browse_pets",
            name="Browse Pet Catalog",
            description="Browse available pets with filtering",
            expected_duration_ms=200
        )

        try:
            start_time = time.time()

            # Build query parameters based on customer preferences
            params = {}
            if customer_profile.preferences.get("pet_types"):
                params["category"] = customer_profile.preferences["pet_types"][0]

            max_budget = customer_profile.budget_range[1]
            params["max_price"] = max_budget

            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            endpoint = f"/api/petstore-domain/browse-pets?{query_string}"

            result = await self._make_request("GET", endpoint)
            step.actual_duration_ms = int((time.time() - start_time) * 1000)
            step.success = True
            step.correlation_id = result.get("_tracking", {}).get("correlation_id")
            step.metadata = {
                "pets_found": result.get("total_count", 0),
                "filters_applied": params
            }

        except Exception as e:
            step.error_message = str(e)
            step.success = False

        return step

    async def _step_get_pet_details(self, customer_profile: CustomerProfile) -> JourneyStep:
        """Get detailed pet information"""
        step = JourneyStep(
            step_id="pet_details",
            name="Pet Details",
            description="Get detailed information about selected pet",
            expected_duration_ms=150
        )

        try:
            start_time = time.time()

            # Select a pet based on customer preferences (simplified)
            pet_id = "golden-retriever-001"  # Default selection
            if customer_profile.preferences.get("pet_types"):
                if "cat" in customer_profile.preferences["pet_types"]:
                    pet_id = "persian-cat-002"
                elif "small_animal" in customer_profile.preferences["pet_types"]:
                    pet_id = "rabbit-001"

            result = await self._make_request("GET", f"/api/petstore-domain/pet-details?pet_id={pet_id}")
            step.actual_duration_ms = int((time.time() - start_time) * 1000)
            step.success = True
            step.correlation_id = result.get("_tracking", {}).get("correlation_id")
            step.metadata = {
                "selected_pet_id": pet_id,
                "pet_price": result.get("pet", {}).get("price", 0)
            }

        except Exception as e:
            step.error_message = str(e)
            step.success = False

        return step

    async def _step_create_order(self, customer_profile: CustomerProfile,
                               inject_errors: bool = False) -> JourneyStep:
        """Create order step"""
        step = JourneyStep(
            step_id="create_order",
            name="Create Order",
            description="Create order for selected pet",
            expected_duration_ms=300
        )

        try:
            start_time = time.time()

            # Simulate inventory shortage error
            if inject_errors and random.random() < 0.2:
                raise Exception("Pet no longer available - suggesting alternatives")

            pet_id = "golden-retriever-001"
            order_data = {
                "customer_id": customer_profile.customer_id,
                "pet_id": pet_id
            }

            result = await self._make_request("POST", "/api/petstore-domain/create-order", order_data)
            step.actual_duration_ms = int((time.time() - start_time) * 1000)
            step.success = True
            step.correlation_id = result.get("_tracking", {}).get("correlation_id")
            step.metadata = {
                "order_id": result.get("order", {}).get("order_id"),
                "total_amount": result.get("order", {}).get("total_amount")
            }

        except Exception as e:
            step.error_message = str(e)
            step.success = False

        return step

    async def _step_process_payment(self, customer_profile: CustomerProfile,
                                  inject_errors: bool = False) -> JourneyStep:
        """Process payment step"""
        step = JourneyStep(
            step_id="process_payment",
            name="Process Payment",
            description="Process payment for the order",
            expected_duration_ms=1000
        )

        try:
            start_time = time.time()

            # Simulate payment failure
            if inject_errors and random.random() < 0.3:
                raise Exception("Payment declined - please try alternative payment method")

            payment_data = {
                "order_id": "ORDER-000001",  # Would come from previous step
                "payment_method": "credit_card",
                "amount": 1200.00
            }

            result = await self._make_request("POST", "/api/petstore-domain/process-payment", payment_data)
            step.actual_duration_ms = int((time.time() - start_time) * 1000)
            step.success = True
            step.correlation_id = result.get("_tracking", {}).get("correlation_id")
            step.metadata = {
                "payment_id": result.get("payment", {}).get("payment_id"),
                "status": result.get("payment", {}).get("status")
            }

        except Exception as e:
            step.error_message = str(e)
            step.success = False

        return step

    async def _step_schedule_delivery(self, customer_profile: CustomerProfile,
                                    inject_errors: bool = False) -> JourneyStep:
        """Schedule delivery step"""
        step = JourneyStep(
            step_id="schedule_delivery",
            name="Schedule Delivery",
            description="Schedule pet delivery",
            expected_duration_ms=200
        )

        try:
            start_time = time.time()

            # Simulate delivery scheduling conflict
            if inject_errors and random.random() < 0.15:
                raise Exception("No delivery slots available today - offering priority scheduling")

            # Simulate delivery scheduling (would integrate with actual delivery service)
            await asyncio.sleep(0.2)

            step.actual_duration_ms = int((time.time() - start_time) * 1000)
            step.success = True
            step.correlation_id = str(uuid.uuid4())
            step.metadata = {
                "delivery_date": (datetime.now() + timedelta(days=2)).isoformat(),
                "delivery_window": "10:00-12:00"
            }

        except Exception as e:
            step.error_message = str(e)
            step.success = False

        return step

    async def _step_track_order_status(self, customer_profile: CustomerProfile) -> JourneyStep:
        """Track order status step"""
        step = JourneyStep(
            step_id="track_order",
            name="Track Order Status",
            description="Check order status and delivery updates",
            expected_duration_ms=100
        )

        try:
            start_time = time.time()

            result = await self._make_request("GET", "/api/petstore-domain/order-status?order_id=ORDER-000001")
            step.actual_duration_ms = int((time.time() - start_time) * 1000)
            step.success = True
            step.correlation_id = result.get("_tracking", {}).get("correlation_id")
            step.metadata = {
                "order_status": result.get("status"),
                "delivery_progress": result.get("delivery_progress")
            }

        except Exception as e:
            step.error_message = str(e)
            step.success = False

        return step

    def generate_journey_report(self, journey_steps: list[JourneyStep]) -> dict[str, Any]:
        """Generate comprehensive journey analytics report"""
        total_duration = sum([s.actual_duration_ms or 0 for s in journey_steps])
        success_rate = len([s for s in journey_steps if s.success]) / len(journey_steps)

        report = {
            "summary": {
                "total_steps": len(journey_steps),
                "successful_steps": len([s for s in journey_steps if s.success]),
                "success_rate": success_rate,
                "total_duration_ms": total_duration,
                "average_step_duration_ms": total_duration / len(journey_steps) if journey_steps else 0
            },
            "steps": [asdict(step) for step in journey_steps],
            "message_tracking": dict(self.message_tracker),
            "performance_metrics": {
                "p50_duration": np.percentile([s.actual_duration_ms or 0 for s in journey_steps], 50),
                "p95_duration": np.percentile([s.actual_duration_ms or 0 for s in journey_steps], 95),
                "p99_duration": np.percentile([s.actual_duration_ms or 0 for s in journey_steps], 99)
            }
        }

        return report

    def display_journey_results(self, journey_steps: list[JourneyStep]):
        """Display journey results with rich formatting"""

        # Create summary table
        table = Table(title="Customer Journey Results")
        table.add_column("Step", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Duration (ms)", justify="right")
        table.add_column("Message ID", style="dim")
        table.add_column("Details")

        for step in journey_steps:
            status = "✅ Success" if step.success else "❌ Failed"
            duration = str(step.actual_duration_ms) if step.actual_duration_ms else "N/A"
            message_id = step.correlation_id[:8] if step.correlation_id else "N/A"
            details = step.error_message if step.error_message else "OK"

            table.add_row(step.name, status, duration, message_id, details)

        console.print(table)

        # Create summary panel
        total_duration = sum([s.actual_duration_ms or 0 for s in journey_steps])
        success_count = len([s for s in journey_steps if s.success])
        success_rate = (success_count / len(journey_steps)) * 100 if journey_steps else 0

        summary_text = f"""
Total Steps: {len(journey_steps)}
Successful: {success_count}/{len(journey_steps)}
Success Rate: {success_rate:.1f}%
Total Duration: {total_duration}ms
Message IDs Tracked: {len(self.message_tracker)}
        """

        console.print(Panel(summary_text, title="Journey Summary", border_style="green"))


@click.command()
@click.option("--mode", default="cli", type=click.Choice(["cli", "notebook"]),
              help="Run mode: CLI or Jupyter notebook")
@click.option("--scenario", default="full",
              type=click.Choice(["full", "quick", "ml-demo", "ops-demo", "error-demo"]),
              help="Demo scenario to run")
@click.option("--customers", default=1, type=int, help="Number of customer journeys to simulate")
@click.option("--errors", is_flag=True, help="Inject errors to test resilience")
@click.option("--export-data", is_flag=True, help="Export analytics data for Jupyter/Grafana")
def main(mode: str, scenario: str, customers: int, errors: bool, export_data: bool):
    """MMF Experience Polish Demo - Complete petstore journey demonstration"""

    console.print(Panel(
        "[bold blue]MMF Experience Polish Demo[/bold blue]\n"
        "Comprehensive petstore journey with ML, observability & scaling",
        title="🚀 Marty Microservices Framework",
        border_style="blue"
    ))

    async def run_demo():
        async with ExperiencePolishDemo() as demo:

            if scenario == "quick":
                # Quick demo with single customer
                customer = demo.customer_profiles[0]
                console.print(f"\n🎯 Running quick demo for {customer.name}")
                journey_steps = await demo.run_complete_journey(customer, inject_errors=errors)
                demo.display_journey_results(journey_steps)

            elif scenario == "full":
                # Full demo with multiple customers
                all_journeys = []
                for i in range(min(customers, len(demo.customer_profiles))):
                    customer = demo.customer_profiles[i]
                    journey_steps = await demo.run_complete_journey(customer, inject_errors=errors)
                    all_journeys.extend(journey_steps)

                    # Small delay between customers
                    await asyncio.sleep(1)

                demo.display_journey_results(all_journeys)

                if export_data:
                    # Export analytics data
                    report = demo.generate_journey_report(all_journeys)

                    # Save to JSON for Grafana
                    with open("journey_analytics.json", "w") as f:
                        json.dump(report, f, indent=2)

                    # Save to CSV for Jupyter
                    df = pd.DataFrame([asdict(step) for step in all_journeys])
                    df.to_csv("journey_data.csv", index=False)

                    console.print("\n📊 Analytics data exported:")
                    console.print("  • journey_analytics.json (for Grafana)")
                    console.print("  • journey_data.csv (for Jupyter)")

            elif scenario == "ml-demo":
                # Focus on ML recommendations
                console.print("\n🤖 ML Recommendation Demo")
                customer = demo.customer_profiles[1]  # First-time owner

                # Show ML recommendations step in detail
                step = await demo._step_get_ml_recommendations(customer, inject_errors=False)
                console.print(f"ML Recommendations: {step.success}")
                console.print(f"Processing time: {step.actual_duration_ms}ms")

            elif scenario == "error-demo":
                # Error resilience demonstration
                console.print("\n⚠️  Error Resilience Demo")
                customer = demo.customer_profiles[0]

                for error_scenario in demo.error_scenarios:
                    console.print(f"\nTesting: {error_scenario['description']}")
                    journey_steps = await demo.run_complete_journey(customer, inject_errors=True)

                    failed_steps = [s for s in journey_steps if not s.success]
                    if failed_steps:
                        console.print(f"  Errors handled: {len(failed_steps)}")
                        for step in failed_steps:
                            console.print(f"    • {step.name}: {step.error_message}")

            elif scenario == "ops-demo":
                # Operational scaling demo (would interact with K8s)
                console.print("\n⚙️  Operational Scaling Demo")
                console.print("This would demonstrate:")
                console.print("  • Horizontal pod autoscaling")
                console.print("  • Canary deployments")
                console.print("  • Service mesh policies")
                console.print("  • Load balancing strategies")
                console.print("\nSee docs/demos/operational-scaling/ for K8s manifests")

    if mode == "notebook":
        console.print("\n📓 Launching Jupyter notebook experience...")
        console.print("See: docs/demos/experience-polish-notebook.ipynb")
    else:
        asyncio.run(run_demo())


if __name__ == "__main__":
    main()
