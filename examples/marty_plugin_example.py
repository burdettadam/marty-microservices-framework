"""
Example: Using the Marty Trust PKI Plugin with MMF

This example demonstrates how to load and use the Marty Trust PKI plugin
within the MMF framework.
"""

import asyncio
import logging
from pathlib import Path

from plugins.marty import MartyTrustPKIPlugin

from framework.config import create_plugin_config_manager
from framework.plugins import DirectoryPluginDiscoverer, PluginContext, PluginManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Main example function."""
    logger.info("Starting Marty Trust PKI Plugin Example")

    try:
        # 1. Setup configuration management
        config_manager = create_plugin_config_manager(
            config_dir="./config",
            plugin_config_dir="./config/plugins"
        )

        # 2. Create plugin context with MMF services
        # In a real implementation, these would be actual MMF service instances
        context = PluginContext(
            config=None,  # Legacy config, replaced by config_manager
            config_manager=config_manager,
            database_manager=MockDatabaseService(),
            security_manager=MockSecurityService(),
            observability_manager=MockObservabilityService(),
            cache_manager=MockCacheService(),
            event_bus=MockEventBus()
        )

        # 3. Initialize plugin manager
        plugin_manager = PluginManager(context)

        # 4. Load Marty plugin directly
        marty_plugin = MartyTrustPKIPlugin()
        await plugin_manager.load_plugin_instance(marty_plugin, "marty")

        # 5. Start the plugin
        await plugin_manager.start_plugin("marty")

        # 6. Demonstrate plugin usage
        await demonstrate_plugin_usage(marty_plugin)

        # 7. Check plugin health
        health_status = await marty_plugin.get_health_status()
        logger.info("Plugin health status: %s", health_status)

        # 8. Stop the plugin
        await plugin_manager.stop_plugin("marty")

    except Exception as e:
        logger.error("Example failed: %s", e)
        raise


async def demonstrate_plugin_usage(plugin: MartyTrustPKIPlugin):
    """Demonstrate using the plugin services."""
    logger.info("Demonstrating Marty Trust PKI Plugin usage")

    # Get the document signer service
    doc_signer = plugin.get_service("document_signer")
    if doc_signer:
        # Sign a document
        test_document = b"This is a test document to sign"
        signature_result = await doc_signer.sign_document(
            test_document,
            "RSA-SHA256"
        )
        logger.info("Document signed: %s", signature_result.get("algorithm"))

        # Verify the signature
        is_valid = await doc_signer.verify_signature(test_document, signature_result)
        logger.info("Signature valid: %s", is_valid)

    # Get the trust anchor service
    trust_anchor = plugin.get_service("trust_anchor")
    if trust_anchor:
        # Validate a certificate chain
        test_chain = [b"cert1_data", b"cert2_data", b"root_cert_data"]
        validation_result = await trust_anchor.validate_trust_chain(test_chain)
        logger.info("Trust chain validation: %s", validation_result.get("valid"))

    # Get the PKD service
    pkd = plugin.get_service("pkd")
    if pkd:
        # Lookup a public key
        key_info = await pkd.lookup_public_key("CN=Test Subject")
        logger.info("PKD lookup result: %s", key_info.get("algorithm") if key_info else "Not found")

    # Get the certificate validation service
    cert_validator = plugin.get_service("certificate_validation")
    if cert_validator:
        # Validate a certificate
        test_cert = b"test_certificate_data"
        validation_result = await cert_validator.validate_certificate(test_cert)
        logger.info("Certificate validation: %s", validation_result.get("status"))


# Mock MMF services for demonstration
class MockDatabaseService:
    """Mock database service."""
    async def execute_query(self, query: str, params=None):
        logger.debug("Mock database query: %s", query)
        return {"rows": []}


class MockSecurityService:
    """Mock security service."""
    async def sign_data(self, data: bytes, key_id: str):
        logger.debug("Mock signing data with key: %s", key_id)
        return b"mock_signature"

    async def verify_signature(self, data: bytes, signature: bytes, key_id: str):
        logger.debug("Mock verifying signature with key: %s", key_id)
        return True


class MockObservabilityService:
    """Mock observability service."""
    def get_metrics_collector(self):
        return MockMetricsCollector()

    def get_tracer(self):
        return MockTracer()


class MockMetricsCollector:
    """Mock metrics collector."""
    def increment_counter(self, name: str, labels=None):
        logger.debug("Mock metric counter: %s", name)

    def start_timer(self, name: str, labels=None):
        return MockTimer()


class MockTimer:
    """Mock timer."""
    def stop(self):
        logger.debug("Mock timer stopped")


class MockTracer:
    """Mock tracer."""
    def start_span(self, name: str):
        return MockSpan()


class MockSpan:
    """Mock span."""
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def set_attribute(self, key: str, value):
        logger.debug("Mock span attribute: %s = %s", key, value)


class MockCacheService:
    """Mock cache service."""
    async def get(self, key: str):
        logger.debug("Mock cache get: %s", key)
        return None

    async def set(self, key: str, value, ttl: int = 300):
        logger.debug("Mock cache set: %s (TTL: %d)", key, ttl)


class MockEventBus:
    """Mock event bus."""
    async def publish(self, event_type: str, data):
        logger.debug("Mock event published: %s", event_type)

    async def process_async(self, handler, *args, **kwargs):
        logger.debug("Mock async event processing")


if __name__ == "__main__":
    asyncio.run(main())
