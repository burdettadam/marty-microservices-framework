"""
Deployment Strategies Compatibility Shim

DEPRECATED: This is a compatibility shim that imports from the decomposed package.
Please import directly from 'framework.deployment.strategies' package instead.

New import path: from framework.deployment.strategies import DeploymentStrategy, ...

The original monolithic strategies.py has been broken down into multiple modules:

- enums.py: Deployment-related enumerations
- models.py: Data models and dataclasses
- orchestrator.py: Main deployment orchestration logic
- managers/: Specialized manager classes for infrastructure, traffic, validation, features, and rollback

For new code, prefer importing directly from the specific modules.
This compatibility layer is maintained for existing code.
"""

import warnings

# Re-export all public classes and functions from the decomposed modules
from .strategies import (  # Enums; Models; Managers; Orchestrator
    Deployment,
    DeploymentEvent,
    DeploymentOrchestrator,
    DeploymentPhase,
    DeploymentStatus,
    DeploymentStrategy,
    DeploymentTarget,
    DeploymentValidation,
    EnvironmentType,
    FeatureFlag,
    FeatureFlagManager,
    FeatureFlagType,
    InfrastructureManager,
    RollbackConfiguration,
    RollbackManager,
    ServiceVersion,
    TrafficManager,
    TrafficSplit,
    ValidationManager,
    ValidationResult,
    ValidationRunResult,
    create_deployment_orchestrator,
)

# Issue deprecation warning
warnings.warn(
    "Importing from framework.deployment.strategies.py is deprecated. "
    "Please import directly from 'framework.deployment.strategies' package.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = [
    # Enums
    "DeploymentPhase",
    "DeploymentStatus",
    "DeploymentStrategy",
    "EnvironmentType",
    "FeatureFlagType",
    "ValidationResult",
    # Models
    "Deployment",
    "DeploymentEvent",
    "DeploymentTarget",
    "DeploymentValidation",
    "FeatureFlag",
    "RollbackConfiguration",
    "ServiceVersion",
    "TrafficSplit",
    # Managers
    "FeatureFlagManager",
    "InfrastructureManager",
    "RollbackManager",
    "TrafficManager",
    "ValidationManager",
    "ValidationRunResult",
    # Orchestrator
    "DeploymentOrchestrator",
    "create_deployment_orchestrator",
]
