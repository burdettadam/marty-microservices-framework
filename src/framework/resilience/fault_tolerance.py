"""
Fault Tolerance and Resilience Patterns for Marty Microservices Framework

This module has been decomposed into focused modules for better maintainability.
This file now serves as a compatibility shim that re-exports all classes from
the decomposed modules.

For new development, consider importing directly from the specific modules:
- circuit_breakers.py: Circuit breaker fault tolerance patterns
- retry_logic.py: Retry patterns with configurable backoff strategies
- bulkheads.py: Bulkhead patterns for resource isolation
- timeouts.py: Timeout patterns for preventing resource exhaustion
- chaos_engineering.py: Chaos engineering for testing system resilience
- metrics.py: Comprehensive metrics collection and monitoring
"""

from .bulkheads import *  # noqa: F403
from .chaos_engineering import *  # noqa: F403

# Re-export everything from the decomposed modules for backward compatibility
from .circuit_breakers import *  # noqa: F403
from .metrics import *  # noqa: F403
from .retry_logic import *  # noqa: F403
from .timeouts import *  # noqa: F403
