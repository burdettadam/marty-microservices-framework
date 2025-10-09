"""
Structured Logging Plugin Example.

This plugin demonstrates how to implement logging enhancements
using the event handler plugin interface.
"""

import json
import time
from typing import Any

from ..decorators import plugin
from ..interfaces import IEventHandlerPlugin, PluginContext, PluginMetadata


@plugin(
    name="structured-logging",
    version="1.0.0",
    description="Structured logging enhancement plugin",
    author="Marty Team",
    provides=["logging", "structured-logs", "audit"],
)
class StructuredLoggingPlugin(IEventHandlerPlugin):
    """
    Structured logging plugin.

    This plugin demonstrates:
    - Event handler implementation
    - Log enhancement and formatting
    - Audit trail creation
    - Event subscription
    """

    def __init__(self):
        super().__init__()
        self.log_format = "json"
        self.audit_enabled = True
        self.log_file_path = None
        self.events_logged = 0

    async def initialize(self, context: PluginContext) -> None:
        """Initialize the structured logging plugin."""
        await super().initialize(context)

        # Get configuration
        self.log_format = context.get_config("log_format", "json")
        self.audit_enabled = context.get_config("audit_enabled", True)
        self.log_file_path = context.get_config("log_file_path")

        # Register logging service
        if context.service_registry:
            context.service_registry.register_service(
                "structured-logging",
                {
                    "type": "logging",
                    "plugin": self.plugin_metadata.name,
                    "format": self.log_format,
                    "audit_enabled": self.audit_enabled,
                    "tags": ["logging", "audit", "structured"],
                },
            )

        self.logger.info("Structured logging plugin initialized")

    @property
    def plugin_metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        return PluginMetadata(
            name="structured-logging",
            version="1.0.0",
            description="Structured logging enhancement plugin",
            author="Marty Team",
            provides=["logging", "structured-logs", "audit"],
        )

    def get_event_subscriptions(self) -> dict[str, str]:
        """
        Return event subscriptions for this plugin.

        Returns:
            Dict mapping event types to handler method names
        """
        return {
            "request.completed": "handle_request_completed",
            "request.failed": "handle_request_failed",
            "service.registered": "handle_service_registered",
            "service.unregistered": "handle_service_unregistered",
            "plugin.started": "handle_plugin_started",
            "plugin.stopped": "handle_plugin_stopped",
            "auth.login": "handle_auth_event",
            "auth.logout": "handle_auth_event",
            "auth.failed": "handle_auth_event",
        }

    async def handle_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """
        Handle an event by routing to specific handler.

        Args:
            event_type: Type of the event
            event_data: Event payload data
        """
        subscriptions = self.get_event_subscriptions()
        handler_name = subscriptions.get(event_type)

        if handler_name and hasattr(self, handler_name):
            handler = getattr(self, handler_name)
            await handler(event_data)
        else:
            # Default handler for unspecified events
            await self.handle_generic_event(event_type, event_data)

    async def handle_request_completed(self, event_data: dict[str, Any]) -> None:
        """Handle request completed event."""
        log_entry = self._create_log_entry(
            "REQUEST_COMPLETED",
            event_data,
            {
                "correlation_id": event_data.get("correlation_id"),
                "processing_time": event_data.get("processing_time"),
                "status": event_data.get("status"),
                "endpoint": event_data.get("endpoint", "unknown"),
            },
        )

        await self._write_log(log_entry)
        self.events_logged += 1

    async def handle_request_failed(self, event_data: dict[str, Any]) -> None:
        """Handle request failed event."""
        log_entry = self._create_log_entry(
            "REQUEST_FAILED",
            event_data,
            {
                "correlation_id": event_data.get("correlation_id"),
                "processing_time": event_data.get("processing_time"),
                "error": event_data.get("error"),
                "endpoint": event_data.get("endpoint", "unknown"),
            },
        )

        await self._write_log(log_entry, level="ERROR")
        self.events_logged += 1

    async def handle_service_registered(self, event_data: dict[str, Any]) -> None:
        """Handle service registered event."""
        if self.audit_enabled:
            log_entry = self._create_log_entry(
                "SERVICE_REGISTERED",
                event_data,
                {
                    "service_name": event_data.get("name"),
                    "service_host": event_data.get("host"),
                    "service_port": event_data.get("port"),
                    "tags": event_data.get("tags", []),
                },
            )

            await self._write_log(log_entry, level="INFO", category="AUDIT")
            self.events_logged += 1

    async def handle_service_unregistered(self, event_data: dict[str, Any]) -> None:
        """Handle service unregistered event."""
        if self.audit_enabled:
            log_entry = self._create_log_entry(
                "SERVICE_UNREGISTERED",
                event_data,
                {
                    "service_name": event_data.get("name"),
                    "service_id": event_data.get("service_id"),
                },
            )

            await self._write_log(log_entry, level="INFO", category="AUDIT")
            self.events_logged += 1

    async def handle_plugin_started(self, event_data: dict[str, Any]) -> None:
        """Handle plugin started event."""
        if self.audit_enabled:
            log_entry = self._create_log_entry(
                "PLUGIN_STARTED",
                event_data,
                {
                    "plugin_name": event_data.get("plugin_name"),
                    "plugin_version": event_data.get("plugin_version"),
                },
            )

            await self._write_log(log_entry, level="INFO", category="AUDIT")
            self.events_logged += 1

    async def handle_plugin_stopped(self, event_data: dict[str, Any]) -> None:
        """Handle plugin stopped event."""
        if self.audit_enabled:
            log_entry = self._create_log_entry(
                "PLUGIN_STOPPED",
                event_data,
                {"plugin_name": event_data.get("plugin_name")},
            )

            await self._write_log(log_entry, level="INFO", category="AUDIT")
            self.events_logged += 1

    async def handle_auth_event(self, event_data: dict[str, Any]) -> None:
        """Handle authentication events."""
        if self.audit_enabled:
            event_type = event_data.get("event_type", "AUTH_EVENT")
            log_entry = self._create_log_entry(
                event_type.upper(),
                event_data,
                {
                    "user_id": event_data.get("user_id"),
                    "ip_address": event_data.get("ip_address"),
                    "user_agent": event_data.get("user_agent"),
                    "success": event_data.get("success", True),
                },
            )

            level = "WARNING" if not event_data.get("success", True) else "INFO"
            await self._write_log(log_entry, level=level, category="SECURITY")
            self.events_logged += 1

    async def handle_generic_event(
        self, event_type: str, event_data: dict[str, Any]
    ) -> None:
        """Handle generic events."""
        log_entry = self._create_log_entry(f"EVENT_{event_type.upper()}", event_data)
        await self._write_log(log_entry, level="DEBUG")
        self.events_logged += 1

    def _create_log_entry(
        self,
        event_type: str,
        event_data: dict[str, Any],
        structured_data: dict[str, Any] = None,
    ) -> dict[str, Any]:
        """
        Create a structured log entry.

        Args:
            event_type: Type of event
            event_data: Original event data
            structured_data: Additional structured data

        Returns:
            Structured log entry
        """
        log_entry = {
            "timestamp": time.time(),
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime()),
            "event_type": event_type,
            "plugin": self.plugin_metadata.name,
            "plugin_version": self.plugin_metadata.version,
            "source": event_data.get("source", "unknown"),
            "event_id": f"{self.plugin_metadata.name}-{self.events_logged + 1}",
        }

        # Add structured data
        if structured_data:
            log_entry["data"] = structured_data

        # Add original event data for reference
        log_entry["raw_event"] = event_data

        return log_entry

    async def _write_log(
        self,
        log_entry: dict[str, Any],
        level: str = "INFO",
        category: str = "APPLICATION",
    ) -> None:
        """
        Write log entry to configured destinations.

        Args:
            log_entry: Structured log entry
            level: Log level
            category: Log category
        """
        # Add metadata
        log_entry["level"] = level
        log_entry["category"] = category

        # Format based on configuration
        if self.log_format == "json":
            formatted_log = json.dumps(log_entry, default=str)
        else:
            # Simple text format
            formatted_log = (
                f"[{log_entry['timestamp_iso']}] {level} {category} "
                f"{log_entry['event_type']}: {log_entry.get('data', {})}"
            )

        # Write to logger
        if level == "ERROR":
            self.logger.error(formatted_log)
        elif level == "WARNING":
            self.logger.warning(formatted_log)
        elif level == "DEBUG":
            self.logger.debug(formatted_log)
        else:
            self.logger.info(formatted_log)

        # Write to file if configured
        if self.log_file_path:
            try:
                with open(self.log_file_path, "a") as f:
                    f.write(formatted_log + "\n")
            except Exception as e:
                self.logger.error(f"Failed to write to log file: {e}")

    async def health_check(self) -> dict[str, Any]:
        """Perform health check."""
        health = await super().health_check()

        # Add logging-specific health information
        health["details"] = {
            "log_format": self.log_format,
            "audit_enabled": self.audit_enabled,
            "log_file_path": self.log_file_path,
            "events_logged": self.events_logged,
            "subscriptions": list(self.get_event_subscriptions().keys()),
        }

        return health
