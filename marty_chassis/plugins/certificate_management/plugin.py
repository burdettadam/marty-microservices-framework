"""
Main Certificate Management Plugin implementation.

This module contains the primary plugin class that integrates with the
Marty Microservices Framework and orchestrates all certificate management
functionality.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

# Note: These imports assume MMF provides these components
# In a real implementation, these would need to be adapted to the actual MMF API
try:
    from marty_chassis.plugins import IServicePlugin, plugin
except ImportError:
    # Fallback for development/testing when MMF isn't available
    from abc import ABC, abstractmethod

    class IServicePlugin(ABC):
        """Fallback interface for development."""
        @abstractmethod
        async def initialize(self, context): pass
        @abstractmethod
        async def start(self): pass
        @abstractmethod
        async def stop(self): pass

    def plugin(**kwargs):
        """Fallback decorator for development."""
        def decorator(cls):
            cls._plugin_metadata = kwargs
            return cls
        return decorator

from .config import ConfigurationLoader
from .exceptions import (
    CertificateConfigurationError,
    CertificateManagementError,
    CertificateNotFoundError,
)
from .interfaces import (
    ICertificateAuthorityClient,
    ICertificateParser,
    ICertificateStore,
    ICertificateValidator,
    INotificationProvider,
)
from .models import (
    CertificateInfo,
    CertificateManagementConfig,
    CertificateMetrics,
    CertificateOperation,
    NotificationRecord,
)


@plugin(
    name="certificate-management",
    version="1.0.0",
    description="Comprehensive certificate management with monitoring and notifications",
    author="Marty Team",
    provides=["certificate-management", "pki", "security", "monitoring"],
    dependencies=["observability", "security"]
)
class CertificateManagementPlugin(IServicePlugin):
    """
    Certificate Management Plugin for MMF.

    Provides comprehensive certificate lifecycle management including:
    - Certificate Authority integration
    - Certificate storage and retrieval
    - Certificate parsing and validation
    - Expiry monitoring and notifications
    - Certificate rotation and automation
    """

    def __init__(self):
        super().__init__()
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.config: CertificateManagementConfig = ConfigurationLoader.get_default_config()

        # Component registries
        self.ca_clients: dict[str, ICertificateAuthorityClient] = {}
        self.certificate_stores: dict[str, ICertificateStore] = {}
        self.parsers: dict[str, ICertificateParser] = {}
        self.notification_providers: dict[str, INotificationProvider] = {}
        self.validators: dict[str, ICertificateValidator] = {}

        # Background tasks
        self.expiry_monitor_task: asyncio.Task | None = None
        self.metrics_collection_task: asyncio.Task | None = None

        # State tracking
        self.notification_history: list[NotificationRecord] = []
        self.operation_history: list[CertificateOperation] = []
        self.current_metrics: CertificateMetrics = CertificateMetrics()

        # Shutdown flag
        self._shutdown_event = asyncio.Event()

    async def initialize(self, context):
        """Initialize the certificate management plugin."""
        # Update logger if provided by context
        if hasattr(context, 'logger') and context.logger:
            self.logger = context.logger

        self.logger.info("Initializing Certificate Management Plugin")

        try:
            # Load and validate configuration
            context_config = getattr(context, 'config', {})
            self.config = self._load_config(context_config)

            # Register extension points
            await self._register_extension_points(context)

            # Initialize core components
            await self._initialize_components()

            self.logger.info("Certificate Management Plugin initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize Certificate Management Plugin: {e}")
            raise CertificateConfigurationError(f"Plugin initialization failed: {e}")

    async def start(self):
        """Start the certificate management services."""
        self.logger.info("Starting Certificate Management Plugin services")

        try:
            # Start background monitoring tasks
            if self.config.expiry_monitoring.enabled:
                self.expiry_monitor_task = asyncio.create_task(self._expiry_monitoring_loop())
                self.logger.info("Certificate expiry monitoring started")

            # Start metrics collection
            if self.config.metrics_enabled:
                self.metrics_collection_task = asyncio.create_task(self._metrics_collection_loop())
                self.logger.info("Certificate metrics collection started")

            # Register health checks
            await self._register_health_checks()

            self.logger.info("Certificate Management Plugin services started")

        except Exception as e:
            self.logger.error(f"Failed to start Certificate Management Plugin: {e}")
            raise

    async def stop(self):
        """Stop the certificate management services."""
        self.logger.info("Stopping Certificate Management Plugin")

        # Signal shutdown
        self._shutdown_event.set()

        # Cancel background tasks
        tasks_to_cancel = []
        if self.expiry_monitor_task:
            tasks_to_cancel.append(self.expiry_monitor_task)
        if self.metrics_collection_task:
            tasks_to_cancel.append(self.metrics_collection_task)

        for task in tasks_to_cancel:
            task.cancel()

        # Wait for tasks to complete
        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

        # Cleanup resources
        await self._cleanup_resources()

        self.logger.info("Certificate Management Plugin stopped")

    # Certificate Authority Operations

    async def register_ca_client(self, name: str, client: ICertificateAuthorityClient):
        """Register a Certificate Authority client."""
        self.ca_clients[name] = client
        self.logger.info(f"Registered CA client: {name}")

        # Update metrics
        await self._update_metrics()

    async def unregister_ca_client(self, name: str):
        """Unregister a Certificate Authority client."""
        if name in self.ca_clients:
            del self.ca_clients[name]
            self.logger.info(f"Unregistered CA client: {name}")

    async def get_certificates_from_ca(self, ca_name: str, filter_params: dict[str, Any] | None = None) -> list[CertificateInfo]:
        """Get certificates from a specific CA."""
        if ca_name not in self.ca_clients:
            raise CertificateNotFoundError(f"CA client '{ca_name}' not found")

        try:
            operation = self._create_operation("get_certificates", ca_name=ca_name)
            certificates = await self.ca_clients[ca_name].get_certificates(filter_params)

            operation.status = "success"
            operation.metadata = {"certificate_count": len(certificates)}
            self._record_operation(operation)

            return certificates

        except Exception as e:
            operation.status = "failed"
            operation.error_message = str(e)
            self._record_operation(operation)
            raise

    async def get_expiring_certificates(self, ca_name: str, days_threshold: int) -> list[CertificateInfo]:
        """Get expiring certificates from a CA."""
        if ca_name not in self.ca_clients:
            raise CertificateNotFoundError(f"CA client '{ca_name}' not found")

        try:
            operation = self._create_operation("get_expiring_certificates", ca_name=ca_name)
            certificates = await self.ca_clients[ca_name].get_expiring_certificates(days_threshold)

            operation.status = "success"
            operation.metadata = {
                "certificate_count": len(certificates),
                "days_threshold": days_threshold
            }
            self._record_operation(operation)

            return certificates

        except Exception as e:
            operation.status = "failed"
            operation.error_message = str(e)
            self._record_operation(operation)
            raise

    # Certificate Store Operations

    async def register_certificate_store(self, name: str, store: ICertificateStore):
        """Register a certificate storage backend."""
        self.certificate_stores[name] = store
        self.logger.info(f"Registered certificate store: {name}")

    async def store_certificate(self, store_name: str, cert_id: str, cert_data: bytes, metadata: dict[str, Any] | None = None):
        """Store a certificate in the specified store."""
        if store_name not in self.certificate_stores:
            raise CertificateNotFoundError(f"Certificate store '{store_name}' not found")

        try:
            operation = self._create_operation("store_certificate", certificate_id=cert_id, store_name=store_name)
            await self.certificate_stores[store_name].store_certificate(cert_id, cert_data, metadata)

            operation.status = "success"
            self._record_operation(operation)

        except Exception as e:
            operation.status = "failed"
            operation.error_message = str(e)
            self._record_operation(operation)
            raise

    async def retrieve_certificate(self, store_name: str, cert_id: str) -> bytes | None:
        """Retrieve a certificate from the specified store."""
        if store_name not in self.certificate_stores:
            raise CertificateNotFoundError(f"Certificate store '{store_name}' not found")

        try:
            operation = self._create_operation("retrieve_certificate", certificate_id=cert_id, store_name=store_name)
            cert_data = await self.certificate_stores[store_name].retrieve_certificate(cert_id)

            operation.status = "success" if cert_data else "not_found"
            self._record_operation(operation)

            return cert_data

        except Exception as e:
            operation.status = "failed"
            operation.error_message = str(e)
            self._record_operation(operation)
            raise

    # Certificate Parsing Operations

    async def register_certificate_parser(self, name: str, parser: ICertificateParser):
        """Register a certificate parser."""
        self.parsers[name] = parser
        self.logger.info(f"Registered certificate parser: {name}")

    def parse_certificate(self, parser_name: str, cert_data: bytes) -> CertificateInfo:
        """Parse certificate using the specified parser."""
        if parser_name not in self.parsers:
            raise CertificateNotFoundError(f"Certificate parser '{parser_name}' not found")

        return self.parsers[parser_name].parse_certificate(cert_data)

    # Notification Operations

    async def register_notification_provider(self, name: str, provider: INotificationProvider):
        """Register a notification provider."""
        self.notification_providers[name] = provider
        self.logger.info(f"Registered notification provider: {name}")

    async def send_expiry_notification(self, cert_info: CertificateInfo, days_remaining: int):
        """Send expiry notification using all registered providers."""
        notifications_sent = 0

        for name, provider in self.notification_providers.items():
            try:
                success = await provider.send_expiry_notification(cert_info, days_remaining)
                if success:
                    notifications_sent += 1
                    self.logger.info(f"Expiry notification sent via {name}")

                    # Record notification
                    self._record_notification(
                        cert_info.serial_number,
                        "expiry",
                        name,
                        "sent",
                        days_remaining
                    )
                else:
                    self.logger.warning(f"Failed to send notification via {name}")

            except Exception as e:
                self.logger.error(f"Error sending notification via {name}: {e}")
                self._record_notification(
                    cert_info.serial_number,
                    "expiry",
                    name,
                    "failed",
                    days_remaining,
                    str(e)
                )

        return notifications_sent

    # Metrics and Monitoring

    async def get_metrics(self) -> CertificateMetrics:
        """Get current certificate metrics."""
        await self._update_metrics()
        return self.current_metrics

    async def get_operation_history(self, limit: int = 100) -> list[CertificateOperation]:
        """Get recent operation history."""
        return self.operation_history[-limit:] if limit > 0 else self.operation_history

    async def get_notification_history(self, limit: int = 100) -> list[NotificationRecord]:
        """Get recent notification history."""
        return self.notification_history[-limit:] if limit > 0 else self.notification_history

    # Private Methods

    def _load_config(self, context_config: dict[str, Any]) -> CertificateManagementConfig:
        """Load and validate plugin configuration."""
        cert_config = context_config.get("certificate_management", {})

        try:
            if cert_config:
                return ConfigurationLoader.load_from_dict(cert_config)
            else:
                # Try loading from environment variables if no config provided
                return ConfigurationLoader.load_from_environment()
        except Exception:
            # Fallback to default configuration
            return ConfigurationLoader.get_default_config()

    async def _register_extension_points(self, context):
        """Register extension points for the plugin."""
        # TODO: Implement extension point registration
        pass

    async def _initialize_components(self):
        """Initialize plugin components."""
        # TODO: Initialize default components based on configuration
        pass

    async def _register_health_checks(self):
        """Register health checks for the plugin."""
        # TODO: Implement health check registration
        pass

    async def _cleanup_resources(self):
        """Cleanup plugin resources."""
        # Close CA client connections
        for ca_client in self.ca_clients.values():
            if hasattr(ca_client, 'close'):
                try:
                    close_method = ca_client.close
                    if asyncio.iscoroutinefunction(close_method):
                        await close_method()
                    else:
                        close_method()
                except Exception as e:
                    self.logger.warning(f"Error closing CA client: {e}")

        # Close certificate store connections
        for store in self.certificate_stores.values():
            if hasattr(store, 'close'):
                try:
                    close_method = store.close
                    if asyncio.iscoroutinefunction(close_method):
                        await close_method()
                    else:
                        close_method()
                except Exception as e:
                    self.logger.warning(f"Error closing certificate store: {e}")

    async def _expiry_monitoring_loop(self):
        """Background task for monitoring certificate expiry."""
        while not self._shutdown_event.is_set():
            try:
                await self._check_certificate_expiry()

                # Wait for next check
                interval_seconds = self.config.expiry_monitoring.check_interval_hours * 3600
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=interval_seconds
                )

            except asyncio.TimeoutError:
                continue  # Normal timeout, continue monitoring
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in expiry monitoring: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retry

    async def _metrics_collection_loop(self):
        """Background task for collecting metrics."""
        while not self._shutdown_event.is_set():
            try:
                await self._update_metrics()

                # Wait 5 minutes between metric updates
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=300
                )

            except asyncio.TimeoutError:
                continue  # Normal timeout, continue collection
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in metrics collection: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retry

    async def _check_certificate_expiry(self):
        """Check for expiring certificates and send notifications."""
        for ca_name, ca_client in self.ca_clients.items():
            try:
                # Check for certificates expiring within the maximum threshold
                max_days = max(self.config.expiry_monitoring.notification_days)
                expiring_certs = await ca_client.get_expiring_certificates(max_days)

                for cert in expiring_certs:
                    days_remaining = cert.days_until_expiry

                    # Check if we should send notification for this threshold
                    if days_remaining in self.config.expiry_monitoring.notification_days:
                        if await self._should_send_notification(cert, days_remaining):
                            await self.send_expiry_notification(cert, days_remaining)

            except Exception as e:
                self.logger.error(f"Error checking expiry for CA {ca_name}: {e}")

    async def _should_send_notification(self, cert: CertificateInfo, days_remaining: int) -> bool:
        """Check if notification should be sent based on history."""
        if not self.config.expiry_monitoring.history_enabled:
            return True

        # Check if we've already sent a notification for this certificate and threshold
        for record in self.notification_history:
            if (record.certificate_serial == cert.serial_number and
                record.notification_type == "expiry" and
                record.days_remaining == days_remaining and
                record.status == "sent"):
                return False

        return True

    async def _update_metrics(self):
        """Update certificate metrics."""
        metrics = CertificateMetrics()

        # Collect metrics from all CA clients
        for ca_name, ca_client in self.ca_clients.items():
            try:
                certificates = await ca_client.get_certificates()

                for cert in certificates:
                    metrics.total_certificates += 1

                    if cert.status.value == "valid":
                        metrics.valid_certificates += 1
                    elif cert.status.value == "expired":
                        metrics.expired_certificates += 1
                    elif cert.status.value == "revoked":
                        metrics.revoked_certificates += 1

                    # Check if expiring soon (within 30 days)
                    if cert.days_until_expiry <= 30:
                        metrics.expiring_soon += 1

                    # Count by type
                    cert_type = cert.certificate_type.value
                    metrics.certificates_by_type[cert_type] = metrics.certificates_by_type.get(cert_type, 0) + 1

                    # Count by CA
                    metrics.certificates_by_ca[ca_name] = metrics.certificates_by_ca.get(ca_name, 0) + 1

                    # Count by country
                    if cert.country_code:
                        metrics.certificates_by_country[cert.country_code] = metrics.certificates_by_country.get(cert.country_code, 0) + 1

            except Exception as e:
                self.logger.error(f"Error collecting metrics from CA {ca_name}: {e}")

        metrics.last_updated = datetime.now()
        self.current_metrics = metrics

    def _create_operation(self, operation_type: str, **kwargs) -> CertificateOperation:
        """Create a new operation record."""
        return CertificateOperation(
            operation_id=str(uuid.uuid4()),
            operation_type=operation_type,
            **kwargs
        )

    def _record_operation(self, operation: CertificateOperation):
        """Record an operation in history."""
        self.operation_history.append(operation)

        # Keep only last 1000 operations
        if len(self.operation_history) > 1000:
            self.operation_history = self.operation_history[-1000:]

    def _record_notification(self, cert_serial: str, notification_type: str, provider: str, status: str, days_remaining: int | None = None, error_message: str | None = None):
        """Record a notification in history."""
        record = NotificationRecord(
            notification_id=str(uuid.uuid4()),
            certificate_serial=cert_serial,
            notification_type=notification_type,
            provider=provider,
            recipient="admin",  # TODO: Make this configurable
            sent_at=datetime.now(),
            status=status,
            days_remaining=days_remaining,
            error_message=error_message
        )

        self.notification_history.append(record)

        # Keep only last 1000 notifications
        if len(self.notification_history) > 1000:
            self.notification_history = self.notification_history[-1000:]
