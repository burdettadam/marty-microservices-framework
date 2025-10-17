"""
Marty Microservices Framework

Enterprise-grade framework for building production-ready microservices with Python.
"""

__version__ = "1.0.0"

# Import core components for convenient access
from .events import (
    BaseEvent,
    DeliveryGuarantee,
    EnhancedEventBus,
    EventBus,
    EventMetadata,
    EventPriority,
    EventStatus,
    KafkaConfig,
    OutboxConfig,
)

# Core framework components are available as submodules
# Observability and security are now top-level packages

__all__ = [
    "__version__",
    # Primary event system
    "EnhancedEventBus",
    "EventBus",
    "BaseEvent",
    "EventMetadata",
    "KafkaConfig",
    "OutboxConfig",
    "EventStatus",
    "EventPriority",
    "DeliveryGuarantee",
]
