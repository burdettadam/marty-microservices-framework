"""
Service Mesh and Orchestration Patterns for Marty Microservices Framework

This module has been decomposed into focused modules for better maintainability.
This file now serves as a compatibility shim that re-exports all classes from
the decomposed modules.

For new development, consider importing directly from the specific modules:
- service_mesh.py: Service mesh configuration and enums
- service_discovery.py: Service registration and health checking
- load_balancing.py: Load balancing algorithms and traffic distribution
- traffic_management.py: Traffic management and routing
"""

from .load_balancing import *  # noqa: F403
from .service_discovery import *  # noqa: F403

# Re-export everything from the decomposed modules for backward compatibility
from .service_mesh import *  # noqa: F403
from .traffic_management import *  # noqa: F403
