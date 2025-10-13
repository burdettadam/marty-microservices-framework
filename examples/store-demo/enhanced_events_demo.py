"""
Enhanced MMF Store Demo - Event Publishing Example

This service demonstrates comprehensive event publishing patterns:
- Unified event publishing system
- Different event types (audit, notification, business)
- Event-driven architecture patterns
- Async event handling
- Event correlation and tracing

This incorporates functionality from simple_event_example.py and enhanced_integration_demo.py
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime

# Mock framework imports (these would be real in production)
try:
    from framework.events import (
        AuditEventType,
        NotificationEventType,
        get_event_publisher,
    )
except ImportError:
    # Fallback implementations for demo
    class AuditEventType:
        USER_LOGIN = "user.login"
        ORDER_CREATED = "order.created"
        PAYMENT_PROCESSED = "payment.processed"
        INVENTORY_UPDATED = "inventory.updated"

    class NotificationEventType:
        ORDER_CONFIRMATION = "notification.order_confirmation"
        PAYMENT_FAILED = "notification.payment_failed"
        LOW_INVENTORY = "notification.low_inventory"

    class MockEventPublisher:
        def __init__(self):
            self.published_events = []

        async def publish_audit_event(self, event_type: str, details: dict, correlation_id: str = None):
            event = {
                "type": "audit",
                "event_type": event_type,
                "details": details,
                "correlation_id": correlation_id or str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat(),
                "service": "store-demo"
            }
            self.published_events.append(event)
            print(f"📤 Audit Event Published: {event_type}")
            print(f"   Details: {json.dumps(details, indent=2)}")

        async def publish_notification_event(self, event_type: str, details: dict, correlation_id: str = None):
            event = {
                "type": "notification",
                "event_type": event_type,
                "details": details,
                "correlation_id": correlation_id or str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat(),
                "service": "store-demo"
            }
            self.published_events.append(event)
            print(f"📨 Notification Event Published: {event_type}")
            print(f"   Details: {json.dumps(details, indent=2)}")

        async def publish_business_event(self, event_type: str, details: dict, correlation_id: str = None):
            event = {
                "type": "business",
                "event_type": event_type,
                "details": details,
                "correlation_id": correlation_id or str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat(),
                "service": "store-demo"
            }
            self.published_events.append(event)
            print(f"🏢 Business Event Published: {event_type}")
            print(f"   Details: {json.dumps(details, indent=2)}")

        async def close(self):
            print(f"📊 Total events published: {len(self.published_events)}")

    async def get_event_publisher():
        return MockEventPublisher()

logger = logging.getLogger(__name__)

class StoreEventManager:
    """Enhanced event management for store operations"""

    def __init__(self):
        self.publisher = None
        self.correlation_id = str(uuid.uuid4())

    async def initialize(self):
        """Initialize the event publisher"""
        self.publisher = await get_event_publisher()
        logger.info("Event publisher initialized")

    async def publish_order_events(self, order_data: dict) -> str:
        """Publish events related to order processing"""
        order_id = order_data.get("order_id", str(uuid.uuid4()))
        customer_id = order_data.get("customer_id", "unknown")
        correlation_id = str(uuid.uuid4())

        # 1. Audit event for order creation
        await self.publisher.publish_audit_event(
            AuditEventType.ORDER_CREATED,
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "items": order_data.get("items", []),
                "total_amount": order_data.get("total", 0.0),
                "created_by": "store-service"
            },
            correlation_id
        )

        # 2. Business event for downstream processing
        await self.publisher.publish_business_event(
            "order.processing.started",
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "requires_payment": True,
                "requires_inventory_check": True,
                "priority": order_data.get("priority", "normal")
            },
            correlation_id
        )

        # 3. Notification event for customer
        await self.publisher.publish_notification_event(
            NotificationEventType.ORDER_CONFIRMATION,
            {
                "recipient": customer_id,
                "order_id": order_id,
                "message": f"Your order {order_id} has been received and is being processed.",
                "channel": "email"
            },
            correlation_id
        )

        return correlation_id

    async def publish_payment_events(self, payment_data: dict, correlation_id: str = None):
        """Publish events related to payment processing"""
        payment_id = payment_data.get("payment_id", str(uuid.uuid4()))
        order_id = payment_data.get("order_id")
        success = payment_data.get("success", False)

        if success:
            # Successful payment
            await self.publisher.publish_audit_event(
                AuditEventType.PAYMENT_PROCESSED,
                {
                    "payment_id": payment_id,
                    "order_id": order_id,
                    "amount": payment_data.get("amount", 0.0),
                    "payment_method": payment_data.get("method", "credit_card"),
                    "status": "completed"
                },
                correlation_id
            )

            await self.publisher.publish_business_event(
                "payment.completed",
                {
                    "payment_id": payment_id,
                    "order_id": order_id,
                    "next_step": "fulfill_order"
                },
                correlation_id
            )
        else:
            # Failed payment
            await self.publisher.publish_audit_event(
                "payment.failed",
                {
                    "payment_id": payment_id,
                    "order_id": order_id,
                    "amount": payment_data.get("amount", 0.0),
                    "failure_reason": payment_data.get("error", "unknown"),
                    "retry_count": payment_data.get("retry_count", 0)
                },
                correlation_id
            )

            await self.publisher.publish_notification_event(
                NotificationEventType.PAYMENT_FAILED,
                {
                    "recipient": payment_data.get("customer_id"),
                    "order_id": order_id,
                    "message": "Payment failed. Please check your payment method.",
                    "channel": "email"
                },
                correlation_id
            )

    async def publish_inventory_events(self, inventory_data: dict, correlation_id: str = None):
        """Publish events related to inventory management"""
        product_id = inventory_data.get("product_id")
        quantity_change = inventory_data.get("quantity_change", 0)
        current_stock = inventory_data.get("current_stock", 0)

        # Audit event for inventory change
        await self.publisher.publish_audit_event(
            AuditEventType.INVENTORY_UPDATED,
            {
                "product_id": product_id,
                "quantity_change": quantity_change,
                "previous_stock": current_stock - quantity_change,
                "current_stock": current_stock,
                "operation": inventory_data.get("operation", "update")
            },
            correlation_id
        )

        # Check for low inventory
        low_stock_threshold = inventory_data.get("low_stock_threshold", 10)
        if current_stock <= low_stock_threshold:
            await self.publisher.publish_notification_event(
                NotificationEventType.LOW_INVENTORY,
                {
                    "product_id": product_id,
                    "current_stock": current_stock,
                    "threshold": low_stock_threshold,
                    "message": f"Product {product_id} is running low on inventory",
                    "recipient": "inventory-manager"
                },
                correlation_id
            )

            await self.publisher.publish_business_event(
                "inventory.low_stock",
                {
                    "product_id": product_id,
                    "current_stock": current_stock,
                    "suggested_reorder": low_stock_threshold * 3,
                    "priority": "high" if current_stock <= 2 else "medium"
                },
                correlation_id
            )

    async def demonstrate_event_flow(self):
        """Demonstrate a complete order flow with events"""
        print("\n=== Store Event Flow Demonstration ===\n")

        # Simulate order processing
        order_data = {
            "order_id": "ORD-12345",
            "customer_id": "CUST-789",
            "items": [
                {"product_id": "PROD-001", "quantity": 2, "price": 29.99},
                {"product_id": "PROD-002", "quantity": 1, "price": 15.50}
            ],
            "total": 75.48,
            "priority": "high"
        }

        print("🛒 Processing Order Flow...")
        correlation_id = await self.publish_order_events(order_data)

        # Simulate inventory check
        print("\n📦 Processing Inventory Updates...")
        for item in order_data["items"]:
            await self.publish_inventory_events({
                "product_id": item["product_id"],
                "quantity_change": -item["quantity"],
                "current_stock": 5,  # Low stock to trigger notification
                "operation": "reserved",
                "low_stock_threshold": 10
            }, correlation_id)

        # Simulate payment processing (success case)
        print("\n💳 Processing Payment (Success)...")
        await self.publish_payment_events({
            "payment_id": "PAY-456",
            "order_id": order_data["order_id"],
            "customer_id": order_data["customer_id"],
            "amount": order_data["total"],
            "method": "credit_card",
            "success": True
        }, correlation_id)

        # Simulate payment failure case
        print("\n💳 Processing Payment (Failure Scenario)...")
        await self.publish_payment_events({
            "payment_id": "PAY-457",
            "order_id": "ORD-12346",
            "customer_id": "CUST-790",
            "amount": 45.99,
            "method": "credit_card",
            "success": False,
            "error": "insufficient_funds",
            "retry_count": 1
        })

    async def close(self):
        """Close the event publisher"""
        if self.publisher:
            await self.publisher.close()

async def demonstrate_store_events():
    """Demonstrate event publishing in store demo"""
    print("=== Store Demo Event Publishing Framework ===\n")

    event_manager = StoreEventManager()

    try:
        await event_manager.initialize()

        print("📡 Event Publishing Features:")
        print("   ✅ Audit Events (compliance, security)")
        print("   ✅ Notification Events (customer communications)")
        print("   ✅ Business Events (process orchestration)")
        print("   ✅ Event Correlation (distributed tracing)")
        print("   ✅ Async Event Handling")

        await event_manager.demonstrate_event_flow()

        print("\n✅ Event demonstration completed successfully!")

    except Exception as e:
        logger.error(f"Error during event demonstration: {e}")
    finally:
        await event_manager.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(demonstrate_store_events())
