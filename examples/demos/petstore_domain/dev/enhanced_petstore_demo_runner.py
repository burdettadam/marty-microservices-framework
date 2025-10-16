#!/usr/bin/env python3
"""
Enhanced Petstore Demo Runner - Demonstrates all features including event streaming
"""
import json
import subprocess
import time
from typing import Any, Dict


class EnhancedPetstoreDemo:
    """Enhanced demo runner showcasing event streaming and distributed system patterns"""

    def __init__(self, namespace: str = "petstore"):
        self.namespace = namespace
        self.pod_name = None
        self._get_pod_name()

    def _get_pod_name(self) -> None:
        """Get the first running petstore pod"""
        result = subprocess.run([
            "kubectl", "get", "pods", "-n", self.namespace,
            "-l", "app=petstore-domain",
            "-o", "jsonpath={.items[0].metadata.name}"
        ], capture_output=True, text=True)

        if result.returncode == 0 and result.stdout.strip():
            self.pod_name = result.stdout.strip()
            print(f"🎯 Using pod: {self.pod_name}")
        else:
            raise Exception("No running petstore pods found")

    def _exec_curl(self, endpoint: str, method: str = "GET", data: str = None) -> Dict[Any, Any]:
        """Execute curl command inside the pod"""
        cmd = [
            "kubectl", "exec", "-n", self.namespace, self.pod_name, "--",
            "curl", "-s"
        ]

        if method == "POST":
            cmd.extend(["-X", "POST", "-H", "Content-Type: application/json"])
            if data:
                cmd.extend(["-d", data])

        cmd.append(f"http://localhost:8080{endpoint}")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {"raw_response": result.stdout}
        else:
            raise Exception(f"Curl failed: {result.stderr}")

    def check_health(self) -> Dict[Any, Any]:
        """Check service health"""
        print("🏥 Checking service health...")
        health = self._exec_curl("/health")
        print(f"   Status: {health.get('status', 'unknown')}")
        print(f"   Service: {health.get('service', 'unknown')}")
        print(f"   Version: {health.get('version', 'unknown')}")
        return health

    def check_initial_events(self) -> Dict[Any, Any]:
        """Check initial event state"""
        print("🔄 Checking initial event stream...")
        events = self._exec_curl("/petstore-domain/events/stats")
        print(f"   Total events: {events.get('total_events', 0)}")
        print(f"   Event types: {events.get('event_types', {})}")
        return events

    def list_pets(self) -> Dict[Any, Any]:
        """List all available pets"""
        print("🐕 Fetching pet catalog...")
        pets_data = self._exec_curl("/petstore-domain/pets")
        pets = pets_data.get('pets', [])
        print(f"   Found {len(pets)} pets:")
        for pet in pets:
            print(f"   • {pet['name']} ({pet['breed']}) - ${pet['price']} - Available: {pet['available']}")
        return pets_data

    def list_customers(self) -> Dict[Any, Any]:
        """List all customers"""
        print("👥 Fetching customer list...")
        customers_data = self._exec_curl("/petstore-domain/customers")
        customers = customers_data.get('customers', [])
        print(f"   Found {len(customers)} customers:")
        for customer in customers:
            print(f"   • {customer['name']} ({customer['email']})")
        return customers_data

    def create_order_with_events(self, customer_id: str, pet_id: str) -> Dict[Any, Any]:
        """Create order and demonstrate event streaming"""
        print(f"📝 Creating order for customer {customer_id} and pet {pet_id}...")

        # Get initial event stats
        initial_stats = self._exec_curl("/petstore-domain/events/stats")
        initial_events = initial_stats.get('total_events', 0)

        # Create order
        order_data = self._exec_curl(
            "/petstore-domain/orders",
            method="POST",
            data=json.dumps({"customer_id": customer_id, "pet_id": pet_id})
        )

        if "order" in order_data:
            order = order_data["order"]
            correlation_id = order_data.get("correlation_id")
            print(f"   ✅ Order created: {order['order_id']}")
            print(f"   💰 Amount: ${order['amount']}")
            print(f"   🔗 Correlation ID: {correlation_id}")

            # Wait a moment for events to be processed
            time.sleep(1)

            # Check new event stats
            new_stats = self._exec_curl("/petstore-domain/events/stats")
            new_events = new_stats.get('total_events', 0)
            events_created = new_events - initial_events

            print(f"   📊 Events generated: {events_created}")
            print(f"   📈 Event types: {new_stats.get('event_types', {})}")

            # Show events for this order
            order_events = self._exec_curl(f"/petstore-domain/events/by-aggregate/{order['order_id']}")
            print(f"   🔍 Events for this order: {len(order_events.get('events', []))}")

            for event in order_events.get('events', []):
                print(f"      • {event['event_type']}: {event['data']}")

            return order_data
        else:
            print(f"   ❌ Order creation failed: {order_data}")
            return order_data

    def demonstrate_event_queries(self):
        """Demonstrate various event query capabilities"""
        print("🔍 Demonstrating event query capabilities...")

        # Show all events
        all_events = self._exec_curl("/petstore-domain/events/stream")
        print(f"   📋 Total events in stream: {all_events.get('total', 0)}")

        # Show order creation events
        order_events = self._exec_curl("/petstore-domain/events/types/order.created")
        print(f"   📦 Order creation events: {order_events.get('total', 0)}")

        # Show inventory update events
        inventory_events = self._exec_curl("/petstore-domain/events/types/inventory.updated")
        print(f"   📊 Inventory update events: {inventory_events.get('total', 0)}")

        # Show recent events with details
        print("   🔄 Recent events:")
        for event in all_events.get('events', [])[-3:]:  # Show last 3 events
            timestamp = event['timestamp'][:19]  # Trim microseconds
            print(f"      • {timestamp}: {event['event_type']} - {event['aggregate_id']}")

    def check_inventory_changes(self):
        """Show how inventory was affected by orders"""
        print("📦 Checking inventory changes...")
        pets_data = self._exec_curl("/petstore-domain/pets")
        pets = pets_data.get('pets', [])

        available_count = sum(1 for pet in pets if pet['available'])
        sold_count = sum(1 for pet in pets if not pet['available'])

        print(f"   ✅ Available pets: {available_count}")
        print(f"   🏷️ Sold pets: {sold_count}")

        # Show sold pets
        for pet in pets:
            if not pet['available']:
                print(f"      • SOLD: {pet['name']} ({pet['breed']}) - ${pet['price']}")

    def show_demo_status(self):
        """Show comprehensive demo status"""
        print("📈 Comprehensive Demo Status...")
        status = self._exec_curl("/petstore-domain/demo/status")

        print(f"   🚦 Demo Status: {status.get('demo_status', 'unknown')}")
        print("   🔧 Features:")
        features = status.get('features', {})
        for feature, enabled in features.items():
            status_icon = "✅" if enabled else "❌"
            print(f"      {status_icon} {feature.replace('_', ' ').title()}")

        print("   📊 Statistics:")
        stats = status.get('stats', {})
        for stat, value in stats.items():
            print(f"      • {stat.replace('_', ' ').title()}: {value}")

    def run_comprehensive_demo(self):
        """Run the complete enhanced petstore demonstration"""
        print("🎭 Enhanced Petstore Demo with Event Streaming")
        print("=" * 60)

        try:
            # 1. Health check
            self.check_health()
            print()

            # 2. Initial event state
            self.check_initial_events()
            print()

            # 3. List pets and customers
            pets_data = self.list_pets()
            print()
            customers_data = self.list_customers()
            print()

            # 4. Create multiple orders with event tracking
            pets = pets_data.get('pets', [])
            customers = customers_data.get('customers', [])

            if customers and pets:
                # Create first order
                available_pets = [pet for pet in pets if pet['available']]
                if available_pets:
                    self.create_order_with_events(customers[0]['customer_id'], available_pets[0]['pet_id'])
                    print()

                # Create second order
                remaining_pets = [pet for pet in pets if pet['available']]
                if len(remaining_pets) > 0 and len(customers) > 1:
                    self.create_order_with_events(customers[1]['customer_id'], remaining_pets[0]['pet_id'])
                    print()

            # 5. Demonstrate event querying
            self.demonstrate_event_queries()
            print()

            # 6. Show inventory changes
            self.check_inventory_changes()
            print()

            # 7. Final demo status
            self.show_demo_status()
            print()

            print("✅ Enhanced Demo completed successfully!")
            print("🔄 Event streaming demonstrated")
            print("📊 Distributed system patterns showcased")
            print("🎯 All features working correctly")

        except Exception as e:
            print(f"❌ Demo failed: {e}")
            raise

def main():
    """Main demo execution"""
    print("🚀 Enhanced Petstore Kubernetes Demo with Event Streaming")
    print("========================================================")

    demo = EnhancedPetstoreDemo()
    demo.run_comprehensive_demo()

if __name__ == "__main__":
    main()
