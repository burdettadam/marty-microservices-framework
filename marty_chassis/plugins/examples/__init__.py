"""
Example plugins demonstrating the plugin architecture.

This package contains example plugins that showcase different
types of plugin functionality and extension points, including
plugins with timers, simulated work, error scenarios, and
comprehensive observability features.
"""

from .authentication_plugin import JWTAuthenticationPlugin
from .circuit_breaker_plugin import CircuitBreakerPlugin
from .logging_plugin import StructuredLoggingPlugin
from .metrics_plugin import CustomMetricsPlugin
from .middleware_plugin import RequestTracingPlugin
from .monitoring_plugin import PerformanceMonitorPlugin
from .pipeline_plugin import DataProcessingPipelinePlugin
from .service_discovery_plugin import ConsulServiceDiscoveryPlugin
from .simulation_plugin import SimulationServicePlugin

__all__ = [
    "JWTAuthenticationPlugin",
    "StructuredLoggingPlugin",
    "CustomMetricsPlugin",
    "ConsulServiceDiscoveryPlugin",
    "RequestTracingPlugin",
    "SimulationServicePlugin",
    "DataProcessingPipelinePlugin",
    "PerformanceMonitorPlugin",
    "CircuitBreakerPlugin",
]
