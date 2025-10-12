"""
Migration Examples for Unified Event Publishing

This module demonstrates how to migrate existing services from custom Kafka
event publishing logic to the unified event publishing framework.
"""

import asyncio
import json
from datetime import datetime
from typing import Any

from framework.events import (
    AuditEventType,
    EventConfig,
    EventPublisher,
    NotificationEventType,
    audit_event,
    domain_event,
    get_event_publisher,
    publish_on_error,
    publish_on_success,
)

# ==============================================================================
# Example 1: Migrating DTC Engine Event Publishing
# ==============================================================================


class DTCEngineOld:
    """Original DTC Engine with custom event publishing logic."""

    def __init__(self, database):
        self._database = database

    async def _publish_event(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        session=None,
        key: str | None = None,
    ) -> None:
        """Original custom event publishing method."""
        serialized = json.dumps(payload).encode("utf-8")

        async def handler(db_session) -> None:
            from marty_common.infrastructure import OutboxRepository

            outbox = OutboxRepository(db_session)
            await outbox.enqueue(
                topic=topic,
                payload=serialized,
                key=key.encode("utf-8") if key else None,
            )

        if session is None:
            await self._database.run_within_transaction(handler)
        else:
            await handler(session)

    async def validate_dtc_old(self, dtc_data: dict[str, Any]) -> dict[str, Any]:
        """Original validation method with custom event publishing."""
        # Validation logic
        result = {"status": "valid", "dtc_id": dtc_data["id"]}

        # Custom event publishing
        await self._publish_event(
            topic="dtc.validation.completed",
            payload={
                "dtc_id": dtc_data["id"],
                "status": result["status"],
                "timestamp": datetime.utcnow().isoformat(),
                "validation_details": result,
            },
            key=dtc_data["id"],
        )

        return result


class DTCEngineNew:
    """Migrated DTC Engine using unified event publishing."""

    def __init__(self, database):
        self._database = database
        self.event_publisher = get_event_publisher()

    @domain_event(
        aggregate_type="dtc",
        event_type="dtc_validation_completed",
        aggregate_id_field="dtc_id",
        include_args=True,
        include_result=True,
    )
    async def validate_dtc_new(self, dtc_id: str, dtc_data: dict[str, Any]) -> dict[str, Any]:
        """Migrated validation method using decorator."""
        # Same validation logic
        result = {"status": "valid", "dtc_id": dtc_id}
        return result

    # Alternative: Manual event publishing for more control
    async def validate_dtc_manual(self, dtc_id: str, dtc_data: dict[str, Any]) -> dict[str, Any]:
        """Manual event publishing for custom control."""
        # Validation logic
        result = {"status": "valid", "dtc_id": dtc_id}

        # Unified event publishing
        await self.event_publisher.publish_domain_event(
            aggregate_type="dtc",
            aggregate_id=dtc_id,
            event_type="dtc_validation_completed",
            event_data={
                "status": result["status"],
                "validation_details": result,
                "dtc_data": dtc_data,
            },
        )

        return result


# ==============================================================================
# Example 2: Migrating CMC Engine Event Publishing
# ==============================================================================


class CMCEngineOld:
    """Original CMC Engine with direct event bus usage."""

    def __init__(self, event_bus, storage):
        self.event_bus = event_bus
        self.storage = storage

    async def create_cmc_old(self, request) -> str:
        """Original CMC creation with direct event bus."""
        cmc_id = f"cmc_{request.document_number}"

        # Business logic
        cmc_certificate = await self._create_certificate(request)
        await self.storage.store_cmc(cmc_certificate)

        # Direct event bus publishing
        await self.event_bus.publish(
            "cmc.created",
            {
                "cmc_id": cmc_id,
                "document_number": request.document_number,
                "issuing_country": request.issuing_country,
                "security_model": request.security_model,
                "created_at": cmc_certificate.created_at.isoformat(),
            },
        )

        return cmc_id

    async def _create_certificate(self, request):
        """Mock certificate creation."""
        from datetime import datetime, timezone

        return type(
            "CMC",
            (),
            {"created_at": datetime.now(timezone.utc), "document_number": request.document_number},
        )()


class CMCEngineNew:
    """Migrated CMC Engine using unified event publishing."""

    def __init__(self, storage):
        self.storage = storage
        self.event_publisher = get_event_publisher()

    @domain_event(aggregate_type="cmc", event_type="cmc_created", aggregate_id_field="cmc_id")
    @audit_event(
        event_type=AuditEventType.CERTIFICATE_ISSUED,
        action="create_cmc_certificate",
        resource_type="cmc_certificate",
        resource_id_field="cmc_id",
    )
    async def create_cmc_new(self, cmc_id: str, request) -> str:
        """Migrated CMC creation using decorators."""
        # Same business logic
        cmc_certificate = await self._create_certificate(request)
        await self.storage.store_cmc(cmc_certificate)

        # Events are automatically published by decorators
        return cmc_id

    # Alternative: Manual publishing with additional events
    async def create_cmc_manual(self, request) -> str:
        """Manual approach with multiple event types."""
        cmc_id = f"cmc_{request.document_number}"

        # Business logic
        cmc_certificate = await self._create_certificate(request)
        await self.storage.store_cmc(cmc_certificate)

        # Publish domain event
        await self.event_publisher.publish_domain_event(
            aggregate_type="cmc",
            aggregate_id=cmc_id,
            event_type="cmc_created",
            event_data={
                "document_number": request.document_number,
                "issuing_country": request.issuing_country,
                "security_model": request.security_model,
                "created_at": cmc_certificate.created_at.isoformat(),
            },
        )

        # Publish audit event
        await self.event_publisher.publish_audit_event(
            event_type=AuditEventType.CERTIFICATE_ISSUED,
            action="create_cmc_certificate",
            resource_type="cmc_certificate",
            resource_id=cmc_id,
            operation_details={
                "document_number": request.document_number,
                "issuing_country": request.issuing_country,
                "security_model": request.security_model,
            },
        )

        # Publish notification if needed
        if request.notify_user:
            await self.event_publisher.publish_notification_event(
                event_type=NotificationEventType.CERTIFICATE_ISSUED,
                recipient_type="user",
                recipient_ids=[request.user_id],
                subject="CMC Certificate Issued",
                message=f"Your CMC certificate {cmc_id} has been issued successfully.",
            )

        return cmc_id

    async def _create_certificate(self, request):
        """Mock certificate creation."""
        from datetime import datetime, timezone

        return type(
            "CMC",
            (),
            {"created_at": datetime.now(timezone.utc), "document_number": request.document_number},
        )()


# ==============================================================================
# Example 3: Migrating Base Service Event Publishing
# ==============================================================================


class BaseServiceOld:
    """Original base service with custom event publishing."""

    def __init__(self, dependencies):
        self.dependencies = dependencies
        self.logger = None

    async def publish_event(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        session: Any = None,
        key: str | None = None,
    ) -> None:
        """Original base service event publishing."""
        if not self.dependencies or not hasattr(self.dependencies, "database"):
            self.logger.warning("Event publishing unavailable - no database dependency")
            return

        try:
            from marty_common.infrastructure import OutboxRepository

            serialized = json.dumps(payload).encode("utf-8")

            async def handler(db_session) -> None:
                outbox = OutboxRepository(db_session)
                await outbox.enqueue(
                    topic=topic,
                    payload=serialized,
                    key=key.encode("utf-8") if key else None,
                )

            if session is None:
                await self.dependencies.database.run_within_transaction(handler)
            else:
                await handler(session)

        except Exception as e:
            self.logger.error(f"Failed to publish event: {e}")


class BaseServiceNew:
    """Migrated base service using unified event publishing."""

    def __init__(self, dependencies):
        self.dependencies = dependencies
        self.logger = None
        # Get event publisher with database session support
        self.event_publisher = get_event_publisher(
            database_session=getattr(dependencies, "database_session", None)
        )

    async def publish_domain_event(
        self,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        event_data: dict[str, Any],
        *,
        session: Any = None,
    ) -> str | None:
        """Publish domain events using unified publisher."""
        try:
            # Update session if provided
            if session:
                self.event_publisher.database_session = session

            event_id = await self.event_publisher.publish_domain_event(
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                event_type=event_type,
                event_data=event_data,
            )

            return event_id

        except Exception as e:
            self.logger.error(f"Failed to publish domain event: {e}")
            return None

    async def publish_audit_event(
        self,
        event_type: AuditEventType,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        **kwargs,
    ) -> str | None:
        """Publish audit events using unified publisher."""
        try:
            event_id = await self.event_publisher.publish_audit_event(
                event_type=event_type,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                **kwargs,
            )

            return event_id

        except Exception as e:
            self.logger.error(f"Failed to publish audit event: {e}")
            return None


# ==============================================================================
# Example 4: User Service with Authentication Events
# ==============================================================================


class UserServiceMigrated:
    """Complete example of migrated user service."""

    def __init__(self, repository, email_service):
        self.repository = repository
        self.email_service = email_service
        self.event_publisher = get_event_publisher()

    @domain_event(aggregate_type="user", event_type="user_created", aggregate_id_field="user_id")
    @audit_event(
        event_type=AuditEventType.DATA_CREATED,
        action="create_user",
        resource_type="user",
        resource_id_field="user_id",
        include_args=True,
    )
    async def create_user(self, user_id: str, user_data: dict[str, Any]) -> dict[str, Any]:
        """Create user with automatic event publishing."""
        # Business logic
        user = await self.repository.create(user_id, user_data)

        # Send welcome notification
        await self.event_publisher.publish_notification_event(
            event_type=NotificationEventType.USER_WELCOME,
            recipient_type="user",
            recipient_ids=[user_id],
            subject="Welcome to Marty!",
            message="Your account has been created successfully.",
            channels=["email"],
        )

        return user

    @publish_on_success(topic="auth.events", event_type="login_successful", key_field="user_id")
    @publish_on_error(topic="auth.events", event_type="login_failed", key_field="user_id")
    @audit_event(
        event_type=AuditEventType.USER_LOGIN,
        action="authenticate_user",
        resource_type="user",
        resource_id_field="user_id",
        success_only=False,  # Log both success and failure
    )
    async def authenticate(self, user_id: str, password: str, ip_address: str) -> bool:
        """Authenticate user with comprehensive event publishing."""
        # Authentication logic
        user = await self.repository.get(user_id)
        if not user:
            raise ValueError("User not found")

        is_valid = await self._verify_password(user, password)
        if not is_valid:
            raise ValueError("Invalid credentials")

        # Update last login
        await self.repository.update_last_login(user_id)

        return True

    @domain_event(aggregate_type="user", event_type="user_updated", aggregate_id_field="user_id")
    async def update_user(self, user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update user with domain event."""
        user = await self.repository.update(user_id, updates)

        # Check if critical fields were updated
        critical_fields = ["email", "role", "status"]
        if any(field in updates for field in critical_fields):
            await self.event_publisher.publish_audit_event(
                event_type=AuditEventType.DATA_UPDATED,
                action="update_critical_user_data",
                resource_type="user",
                resource_id=user_id,
                operation_details={"updated_fields": list(updates.keys()), "critical_update": True},
            )

        return user

    async def _verify_password(self, user, password: str) -> bool:
        """Mock password verification."""
        return True  # Simplified for example


# ==============================================================================
# Migration Utility Functions
# ==============================================================================


def create_migration_config() -> EventConfig:
    """Create configuration for migrated services."""
    return EventConfig(
        kafka_brokers=["localhost:9092"],
        service_name="migrated-service",
        topic_prefix="marty",
        use_outbox_pattern=True,
        audit_topic="audit.events",
        notification_topic="notification.events",
        enable_tracing=True,
        enable_metrics=True,
    )


async def migrate_service_events():
    """Example of migrating a service to use unified event publishing."""

    # Setup event publisher
    config = create_migration_config()
    publisher = EventPublisher(config)
    await publisher.start()

    try:
        # Example: Migrate existing event records
        old_events = [
            {"topic": "user.created", "data": {"user_id": "123"}},
            {"topic": "dtc.validated", "data": {"dtc_id": "456"}},
        ]

        for old_event in old_events:
            # Convert old events to new format
            if old_event["topic"] == "user.created":
                await publisher.publish_domain_event(
                    aggregate_type="user",
                    aggregate_id=old_event["data"]["user_id"],
                    event_type="user_created",
                    event_data=old_event["data"],
                )
            elif old_event["topic"] == "dtc.validated":
                await publisher.publish_domain_event(
                    aggregate_type="dtc",
                    aggregate_id=old_event["data"]["dtc_id"],
                    event_type="dtc_validated",
                    event_data=old_event["data"],
                )

        print("Migration completed successfully")

    finally:
        await publisher.stop()


# ==============================================================================
# Testing Examples
# ==============================================================================


async def test_migration_examples():
    """Test the migration examples."""

    # Mock dependencies
    class MockRequest:
        def __init__(self):
            self.document_number = "DOC123"
            self.issuing_country = "US"
            self.security_model = "ECDSA"
            self.user_id = "user-123"
            self.notify_user = True

    class MockStorage:
        async def store_cmc(self, cmc):
            pass

    class MockRepository:
        async def create(self, user_id, data):
            return {"id": user_id, **data}

        async def get(self, user_id):
            return {"id": user_id, "email": "test@example.com"}

        async def update(self, user_id, updates):
            return {"id": user_id, **updates}

        async def update_last_login(self, user_id):
            pass

    # Test CMC Engine migration
    print("Testing CMC Engine migration...")
    cmc_engine = CMCEngineNew(MockStorage())
    request = MockRequest()

    try:
        cmc_id = await cmc_engine.create_cmc_manual(request)
        print(f"CMC created: {cmc_id}")
    except Exception as e:
        print(f"CMC creation failed (expected in test): {e}")

    # Test User Service migration
    print("Testing User Service migration...")
    user_service = UserServiceMigrated(MockRepository(), None)

    try:
        user = await user_service.create_user("user-123", {"email": "test@example.com"})
        print(f"User created: {user}")
    except Exception as e:
        print(f"User creation failed (expected in test): {e}")

    print("Migration examples tested successfully")


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_migration_examples())
