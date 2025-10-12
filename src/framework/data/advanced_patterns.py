"""
Advanced Data Management Patterns for Marty Microservices Framework

This module has been decomposed into focused modules for better maintainability.
This file now serves as a compatibility shim that re-exports all classes from
the decomposed modules.

For new development, consider importing directly from the specific modules:
- event_sourcing.py: Event sourcing patterns
- cqrs.py: Command Query Responsibility Segregation patterns
- transactions.py: Distributed transaction patterns
- sagas.py: Saga patterns for long-running transactions
- consistency.py: Data consistency patterns
"""

from .consistency_patterns import *  # noqa: F403
from .cqrs_patterns import *  # noqa: F403

# Re-export everything from the decomposed modules for backward compatibility
from .event_sourcing_patterns import *  # noqa: F403
from .saga_patterns import *  # noqa: F403
from .transaction_patterns import *  # noqa: F403
