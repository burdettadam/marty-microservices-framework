"""
Enhanced Authorization Module for Marty Microservices Framework

Provides comprehensive authorization and access control including:
- Role-based access control (RBAC)
- Attribute-based access control (ABAC)
- Policy-as-Code with OPA and Oso integration
- Multi-engine policy evaluation
- Real-time authorization decisions
"""

from .manager import AuthorizationManager, PolicyEngine
from .policy_engine import (
    BuiltinPolicyEngine,
    DecisionType,
    OPAPolicyEngine,
    OsoPolicyEngine,
    PolicyContext,
    PolicyDecision,
)
from .policy_engine import PolicyEngine as PolicyEngineEnum
from .policy_engine import PolicyManager, PolicyType

__all__ = [
    "AuthorizationManager",
    "PolicyEngine",
    "PolicyManager",
    "PolicyContext",
    "PolicyDecision",
    "DecisionType",
    "PolicyType",
    "PolicyEngineEnum",
    "OPAPolicyEngine",
    "OsoPolicyEngine",
    "BuiltinPolicyEngine"
]
