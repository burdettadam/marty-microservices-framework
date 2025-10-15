"""
Extended Messaging System Components.

This module provides the extended messaging capabilities including:
- Unified Event Bus with multiple backend support
- Extended backend implementations (NATS, AWS SNS)
- Enhanced Saga integration
- Pattern-specific abstractions
"""

from .aws_sns_backend import AWSSNSBackend, AWSSNSConfig

# Core extended messaging architecture
from .extended_architecture import (
    MessageBackendType,
    MessagingPattern,
    PatternSelector,
    UnifiedEventBus,
)

# Backend implementations
from .nats_backend import NATSBackend, NATSConfig, NATSMessage

# Enhanced Saga integration
from .saga_integration import (
    DistributedSagaManager,
    EnhancedSagaOrchestrator,
    create_distributed_saga_manager,
)

# Unified event bus implementation
from .unified_event_bus import UnifiedEventBusImpl, create_unified_event_bus

__all__ = [
    # Core types and interfaces
    "MessageBackendType",
    "MessagingPattern",
    "PatternSelector",
    "UnifiedEventBus",
    # Backend implementations
    "NATSBackend",
    "NATSConfig",
    "NATSMessage",
    "AWSSNSBackend",
    "AWSSNSConfig",
    # Unified event bus
    "UnifiedEventBusImpl",
    "create_unified_event_bus",
    # Enhanced Saga integration
    "DistributedSagaManager",
    "EnhancedSagaOrchestrator",
    "create_distributed_saga_manager",
]
