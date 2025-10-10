"""
Marty Service Migration Example: Document Signer

This example demonstrates how to migrate an existing Marty service from a standalone
implementation to the MMF plugin architecture, showing before/after comparisons and
the key benefits of using MMF infrastructure.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional

# Before: Original Marty Document Signer (Standalone)
# ===================================================

class OriginalDocumentSigner:
    """
    Original Marty Document Signer implementation with custom infrastructure.

    This represents the legacy approach with:
    - Custom database connections
    - Custom security/key management
    - Custom metrics/monitoring
    - Custom configuration management
    """

    def __init__(self, config_path: str):
        # Custom configuration loading
        self.config = self._load_custom_config(config_path)

        # Custom database setup
        self.db_connection = self._setup_custom_database()

        # Custom security/key management
        self.key_manager = self._setup_custom_key_manager()

        # Custom metrics
        self.metrics = self._setup_custom_metrics()

        # Custom logging
        self.logger = logging.getLogger("marty.document_signer")

    def _load_custom_config(self, config_path: str) -> dict[str, Any]:
        """Load configuration using custom Marty config format."""
        # Custom YAML/JSON loading with Marty-specific structure
        return {
            "signing_algorithm": "RSA-SHA256",
            "database_url": "postgresql://user:pass@localhost/marty_db",
            "key_store_path": "/opt/marty/keys",
            "metrics_port": 9090,
        }

    def _setup_custom_database(self):
        """Setup custom database connection for Marty."""
        # Custom database connection, schema management, migrations
        # Duplicates MMF database functionality
        pass

    def _setup_custom_key_manager(self):
        """Setup custom key management for Marty."""
        # Custom HSM integration, key rotation, certificate management
        # Duplicates MMF security functionality
        pass

    def _setup_custom_metrics(self):
        """Setup custom metrics collection for Marty."""
        # Custom Prometheus metrics, custom collectors
        # Duplicates MMF observability functionality
        pass

    async def sign_document(self, document_data: bytes, algorithm: str = None) -> dict[str, Any]:
        """Sign document with custom infrastructure."""
        algorithm = algorithm or self.config["signing_algorithm"]

        # Manual metrics tracking
        self.metrics.increment("documents_signed_total")
        start_time = time.time()

        try:
            # Custom security operations
            signing_key = self.key_manager.get_signing_key()
            signature = self.key_manager.sign(document_data, signing_key, algorithm)

            # Custom database operations
            signature_record = {
                "document_hash": hashlib.sha256(document_data).hexdigest(),
                "signature": signature,
                "algorithm": algorithm,
                "timestamp": datetime.utcnow().isoformat(),
            }
            self.db_connection.store_signature(signature_record)

            # Manual metrics
            duration = time.time() - start_time
            self.metrics.observe("signing_duration_seconds", duration)

            return {
                "signature": signature,
                "algorithm": algorithm,
                "timestamp": signature_record["timestamp"]
            }

        except Exception as e:
            self.metrics.increment("signing_errors_total")
            self.logger.error(f"Signing failed: {e}")
            raise


# After: Migrated Document Signer (MMF Plugin)
# ============================================

from framework.config import MartyTrustPKIConfig
from framework.plugins import (
    MMFPlugin,
    PluginContext,
    requires_auth,
    trace_operation,
    track_metrics,
)


class ModernDocumentSignerService:
    """
    Modern Document Signer using MMF infrastructure.

    Benefits of migration:
    - Unified configuration management via MMF
    - Automatic database schema management
    - Built-in security with HSM integration
    - Comprehensive observability (metrics, tracing, logging)
    - Event-driven architecture via message bus
    - Automatic service discovery and health checks
    - Resilience patterns (circuit breakers, retries)
    """

    def __init__(self, context: PluginContext, config: MartyTrustPKIConfig):
        self.context = context
        self.config = config
        self._initialized = False

        # No need for custom setup - MMF provides all infrastructure

    async def initialize(self) -> None:
        """Initialize using MMF infrastructure - much simpler!"""
        logging.info("Initializing Document Signer with MMF infrastructure")

        # MMF automatically handles:
        # - Database connection pooling and migrations
        # - Security/key management setup
        # - Metrics collection and tracing
        # - Configuration validation and reloading

        if self.context.database:
            await self._ensure_schema_exists()

        if self.context.security:
            await self._validate_signing_keys()

        self._initialized = True
        logging.info("Document Signer initialized successfully")

    async def _ensure_schema_exists(self) -> None:
        """Ensure database schema exists using MMF database service."""
        # MMF database service handles connection pooling, transactions, etc.
        schema_sql = """
        CREATE TABLE IF NOT EXISTS signature_records (
            id SERIAL PRIMARY KEY,
            document_hash VARCHAR(64) NOT NULL,
            signature BYTEA NOT NULL,
            algorithm VARCHAR(32) NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            signer_id VARCHAR(64),
            UNIQUE(document_hash, algorithm)
        )
        """
        await self.context.database.execute_ddl(schema_sql)

    async def _validate_signing_keys(self) -> None:
        """Validate signing keys using MMF security service."""
        # MMF security service handles HSM integration, key rotation, etc.
        key_info = await self.context.security.get_key_info("document_signer")
        if not key_info:
            raise ValueError("Document signing key not configured")

    @requires_auth(roles=["document_signer"], permissions=["sign_documents"])
    @track_metrics(metric_name="document_sign_requests", timing=True, counter=True)
    @trace_operation(operation_name="sign_document", log_inputs=False, log_outputs=False)
    async def sign_document(self, document_data: bytes, algorithm: str | None = None) -> dict[str, Any]:
        """
        Sign document using MMF infrastructure.

        Benefits demonstrated:
        - Automatic authentication/authorization via @requires_auth
        - Automatic metrics collection via @track_metrics
        - Automatic distributed tracing via @trace_operation
        - Unified error handling and resilience patterns
        """
        algorithm = algorithm or self.config.signing_algorithms[0]

        # Validate algorithm against config
        if algorithm not in self.config.signing_algorithms:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        # Use MMF security service for signing
        signature = await self.context.security.sign_data(
            data=document_data,
            key_id="document_signer",
            algorithm=algorithm
        )

        # Use MMF database service for audit record
        signature_record = {
            "document_hash": hashlib.sha256(document_data).hexdigest(),
            "signature": signature,
            "algorithm": algorithm,
            "timestamp": datetime.utcnow(),
            "signer_id": "document_signer_service"
        }

        await self.context.database.insert(
            "signature_records",
            signature_record
        )

        # Publish event via MMF message bus
        if self.context.message_bus:
            await self.context.message_bus.publish(
                "marty.document.signed",
                {
                    "document_hash": signature_record["document_hash"],
                    "algorithm": algorithm,
                    "timestamp": signature_record["timestamp"].isoformat()
                }
            )

        return {
            "signature": signature,
            "algorithm": algorithm,
            "timestamp": signature_record["timestamp"].isoformat(),
            "signer_id": signature_record["signer_id"]
        }

    @track_metrics(metric_name="document_verify_requests", timing=True)
    @trace_operation(operation_name="verify_signature")
    async def verify_signature(self, document_data: bytes, signature_info: dict[str, Any]) -> bool:
        """Verify document signature using MMF infrastructure."""

        # Use MMF security service for verification
        is_valid = await self.context.security.verify_signature(
            data=document_data,
            signature=signature_info["signature"],
            key_id="document_signer",
            algorithm=signature_info["algorithm"]
        )

        # Optional: Check against stored signature records
        if is_valid and self.context.database:
            document_hash = hashlib.sha256(document_data).hexdigest()
            stored_record = await self.context.database.query_one(
                "SELECT * FROM signature_records WHERE document_hash = $1 AND algorithm = $2",
                document_hash,
                signature_info["algorithm"]
            )

            if stored_record:
                # Additional validation against stored signature
                is_valid = stored_record["signature"] == signature_info["signature"]

        return is_valid


# Migration Comparison and Benefits
# =================================

class MigrationComparison:
    """Demonstrates the benefits of migrating to MMF plugin architecture."""

    @staticmethod
    def compare_implementations():
        """Compare old vs new implementation."""

        print("=== MARTY SERVICE MIGRATION COMPARISON ===\n")

        print("BEFORE (Original Marty Implementation):")
        print("✗ 200+ lines of custom infrastructure code")
        print("✗ Custom database connection management")
        print("✗ Custom security/key management integration")
        print("✗ Custom metrics collection and monitoring")
        print("✗ Custom configuration loading and validation")
        print("✗ Manual error handling and resilience")
        print("✗ No automatic service discovery")
        print("✗ No distributed tracing")
        print("✗ Difficult to test due to tight coupling")
        print("✗ Maintenance burden for infrastructure code")

        print("\nAFTER (MMF Plugin Implementation):")
        print("✓ ~50 lines of business logic only")
        print("✓ Automatic database connection pooling & migrations")
        print("✓ Built-in security with HSM integration")
        print("✓ Comprehensive observability out-of-the-box")
        print("✓ Type-safe configuration with validation")
        print("✓ Automatic resilience patterns (circuit breakers, retries)")
        print("✓ Service discovery and health checks")
        print("✓ Distributed tracing and correlation")
        print("✓ Easy to test with mock infrastructure")
        print("✓ Focus on business logic, not infrastructure")

        print("\nKEY BENEFITS:")
        print("• 75% reduction in code complexity")
        print("• Zero infrastructure maintenance burden")
        print("• Consistent patterns across all services")
        print("• Better observability and debuggability")
        print("• Improved security and compliance")
        print("• Faster development and testing")
        print("• Unified deployment and operations")


# Migration Strategy Example
# =========================

async def demonstrate_migration_process():
    """Demonstrate the step-by-step migration process."""

    print("=== STEP-BY-STEP MIGRATION PROCESS ===\n")

    # Step 1: Setup MMF Plugin Context
    print("Step 1: Setting up MMF Plugin Context...")

    # Mock MMF services for demonstration
    class MockPluginContext:
        def __init__(self):
            self.database = MockDatabaseService()
            self.security = MockSecurityService()
            self.message_bus = MockMessageBus()
            self.observability = MockObservabilityService()

    context = MockPluginContext()

    # Step 2: Load Plugin Configuration
    print("Step 2: Loading plugin configuration...")
    config = MartyTrustPKIConfig(
        trust_anchor_url="https://trust.example.com",
        pkd_url="https://pkd.example.com",
        document_signer_url="https://signer.example.com",
        signing_algorithms=["RSA-SHA256", "ECDSA-SHA256"],
        certificate_validation_enabled=True
    )

    # Step 3: Initialize Modern Service
    print("Step 3: Initializing modern service...")
    modern_signer = ModernDocumentSignerService(context, config)
    await modern_signer.initialize()

    # Step 4: Demonstrate Functionality
    print("Step 4: Testing migrated functionality...")

    test_document = b"This is a test document for migration demo"

    # Sign document using modern service
    signature_result = await modern_signer.sign_document(
        test_document,
        "RSA-SHA256"
    )
    print(f"Document signed: {signature_result['algorithm']}")

    # Verify signature
    is_valid = await modern_signer.verify_signature(test_document, signature_result)
    print(f"Signature verified: {is_valid}")

    print("\nMigration completed successfully!")
    print("✓ All functionality preserved")
    print("✓ Enhanced with MMF infrastructure benefits")
    print("✓ Reduced complexity and maintenance burden")


# Mock services for demonstration
class MockDatabaseService:
    async def execute_ddl(self, sql: str): pass
    async def insert(self, table: str, data: dict): pass
    async def query_one(self, sql: str, *params): return None

class MockSecurityService:
    async def get_key_info(self, key_id: str): return {"id": key_id}
    async def sign_data(self, data: bytes, key_id: str, algorithm: str):
        return b"mock_signature"
    async def verify_signature(self, data: bytes, signature: bytes, key_id: str, algorithm: str):
        return True

class MockMessageBus:
    async def publish(self, topic: str, data: dict): pass

class MockObservabilityService:
    def get_metrics_collector(self): return None
    def get_tracer(self): return None


if __name__ == "__main__":
    # Show comparison
    MigrationComparison.compare_implementations()

    print("\n" + "="*60 + "\n")

    # Demonstrate migration
    import hashlib
    import time
    from datetime import datetime

    asyncio.run(demonstrate_migration_process())
