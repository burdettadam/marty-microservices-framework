"""
Example plugins demonstrating the plugin architecture.

This package contains example plugins that showcase different
types of plugin functionality and extension points.
"""

from .authentication_plugin import JWTAuthenticationPlugin
from .logging_plugin import StructuredLoggingPlugin
from .metrics_plugin import CustomMetricsPlugin
from .middleware_plugin import RequestTracingPlugin
from .service_discovery_plugin import ConsulServiceDiscoveryPlugin

__all__ = [
    "JWTAuthenticationPlugin",
    "StructuredLoggingPlugin",
    "CustomMetricsPlugin",
    "ConsulServiceDiscoveryPlugin",
    "RequestTracingPlugin",
]
