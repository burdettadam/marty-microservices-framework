"""
Integration setup for observability components
"""

from observability.kafka import EventBus, KafkaConfig, event_bus_context
from observability.metrics import MetricsCollector, MetricsConfig

__all__ = [
    "EventBus",
    "KafkaConfig",
    "MetricsCollector",
    "MetricsConfig",
    "event_bus_context",
    "setup_observability",
]


async def setup_observability(
    service_name: str,
    service_version: str = "1.0.0",
    kafka_bootstrap_servers: list[str] = None,
    enable_metrics: bool = True,
    enable_events: bool = True,
) -> tuple[MetricsCollector | None, EventBus | None]:
    """
    Setup complete observability stack for a microservice

    Args:
        service_name: Name of the microservice
        service_version: Version of the microservice
        kafka_bootstrap_servers: Kafka bootstrap servers
        enable_metrics: Whether to enable metrics collection
        enable_events: Whether to enable event bus

    Returns:
        Tuple of (metrics_collector, event_bus)
    """
    metrics_collector = None
    event_bus = None

    if enable_metrics:
        metrics_config = MetricsConfig(service_name=service_name, service_version=service_version)
        metrics_collector = MetricsCollector(metrics_config)

    if enable_events:
        kafka_config = KafkaConfig(
            bootstrap_servers=kafka_bootstrap_servers or ["localhost:9092"],
            consumer_group_id=f"{service_name}-consumer",
        )
        event_bus = EventBus(kafka_config, service_name)
        await event_bus.start()

    return metrics_collector, event_bus
