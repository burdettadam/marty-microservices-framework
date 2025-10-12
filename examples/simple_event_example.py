"""
Simple Event Publishing Example

A minimal example showing how to use the unified event publishing system.
"""

import asyncio
import os
from datetime import datetime
from typing import Any

# Set up the example environment
os.environ["SERVICE_NAME"] = "example-service"
os.environ["KAFKA_BROKERS"] = "localhost:9092"
os.environ["EVENT_TOPIC_PREFIX"] = "marty"

async def main():
    """Simple example of using the event publishing system."""

    publisher: Any | None = None

    try:
        from framework.events import (
            AuditEventType,
            NotificationEventType,
            get_event_publisher,
        )

        print("🚀 Starting Event Publishing Example")

        # Get the event publisher (uses environment configuration)
        publisher = get_event_publisher()
        await publisher.start()

        print("✅ Event publisher started")

        # 1. Publish an audit event
        print("\n📋 Publishing audit event...")
        audit_event_id = await publisher.publish_audit_event(
            event_type=AuditEventType.DATA_CREATED,
            action="create_example_resource",
            resource_type="example",
            resource_id="example-123",
            operation_details={
                "created_by": "system",
                "timestamp": datetime.utcnow().isoformat(),
                "example_data": {"key": "value"}
            }
        )
        print(f"✅ Audit event published: {audit_event_id}")

        # 2. Publish a notification event
        print("\n📧 Publishing notification event...")
        notification_event_id = await publisher.publish_notification_event(
            event_type=NotificationEventType.SYSTEM_ALERT,
            recipient_type="admin",
            recipient_ids=["admin-1", "admin-2"],
            subject="System Example Alert",
            message="This is an example system alert notification.",
            channels=["email", "webhook"]
        )
        print(f"✅ Notification event published: {notification_event_id}")

        # 3. Publish a domain event
        print("\n🏗️ Publishing domain event...")
        domain_event_id = await publisher.publish_domain_event(
            aggregate_type="example",
            aggregate_id="example-123",
            event_type="example_created",
            event_data={
                "name": "Example Resource",
                "status": "active",
                "created_at": datetime.utcnow().isoformat(),
                "properties": {
                    "color": "blue",
                    "size": "medium"
                }
            }
        )
        print(f"✅ Domain event published: {domain_event_id}")

        # 4. Publish a custom event
        print("\n🎯 Publishing custom event...")
        custom_event_id = await publisher.publish_custom_event(
            topic="example.custom.events",
            event_type="custom_example_event",
            payload={
                "event_source": "example_script",
                "event_time": datetime.utcnow().isoformat(),
                "custom_data": {
                    "metric": "performance",
                    "value": 42,
                    "unit": "ms"
                }
            },
            key="example-123"
        )
        print(f"✅ Custom event published: {custom_event_id}")

        print("\n🎉 All events published successfully!")
        print("\nℹ️  Check your Kafka topics:")
        print("   - marty.audit.events")
        print("   - marty.notification.events")
        print("   - marty.example-service.example.example_created")
        print("   - marty.example.custom.events")

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running from the framework directory")
        print("and that all dependencies are installed.")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure Kafka is running on localhost:9092")

    finally:
        if publisher:
            try:
                await publisher.stop()
                print("\n🛑 Event publisher stopped")
            except Exception as stop_error:
                print(f"Warning: Failed to stop publisher cleanly: {stop_error}")


async def decorator_example():
    """Example showing event publishing decorators."""

    try:
        from framework.events import (
            AuditEventType,
            audit_event,
            domain_event,
            publish_on_success,
        )

        print("\n🎭 Decorator Example")

        class ExampleService:
            def __init__(self):
                pass

            @audit_event(
                event_type=AuditEventType.DATA_CREATED,
                action="create_resource",
                resource_type="example_resource",
                resource_id_field="resource_id"
            )
            @domain_event(
                aggregate_type="example_resource",
                event_type="resource_created",
                aggregate_id_field="resource_id"
            )
            async def create_resource(self, resource_id: str, resource_data: dict):
                """Method with automatic event publishing via decorators."""
                print(f"   Creating resource: {resource_id}")
                print(f"   Data: {resource_data}")

                # Simulate some work
                await asyncio.sleep(0.1)

                return {"id": resource_id, "status": "created", **resource_data}

            @publish_on_success(
                topic="operations.events",
                event_type="operation_completed",
                key_field="operation_id"
            )
            async def perform_operation(self, operation_id: str, operation_type: str):
                """Method with success event publishing."""
                print(f"   Performing operation: {operation_id} ({operation_type})")

                # Simulate work
                await asyncio.sleep(0.1)

                return {"operation_id": operation_id, "result": "success"}

        # Use the service
        service = ExampleService()

        print("Creating resource with decorators...")
        result = await service.create_resource(
            "resource-456",
            {"name": "Example Resource", "type": "demo"}
        )
        print(f"✅ Resource created: {result}")

        print("\nPerforming operation with success event...")
        result = await service.perform_operation("op-789", "example_operation")
        print(f"✅ Operation completed: {result}")

        print("✅ Decorator examples completed")

    except ImportError as e:
        print(f"❌ Import error: {e}")

    except Exception as e:
        print(f"❌ Error in decorator example: {e}")


if __name__ == "__main__":
    print("🎯 Unified Event Publishing Example")
    print("====================================")

    asyncio.run(main())
    asyncio.run(decorator_example())

    print("\n📖 For more examples, see:")
    print("   - examples/event_publishing_migration.py")
    print("   - docs/event-publishing-guide.md")
    print("\n💡 To run with real Kafka:")
    print("   1. Start Kafka: docker-compose -f observability/kafka/docker-compose.kafka.yml up")
    print("   2. Run this script: python examples/simple_event_example.py")
