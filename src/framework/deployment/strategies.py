"""
Deployment Strategies Compatibility Shim

This module provides backward compatibility for the decomposed deployment strategies.
The original monolithic strategies.py has been broken down into multiple modules:

- enums.py: Deployment-related enumerations
- models.py: Data models and dataclasses
- orchestrator.py: Main deployment orchestration logic
- managers/: Specialized manager classes for infrastructure, traffic, validation, features, and rollback

For new code, prefer importing directly from the specific modules.
This compatibility layer is maintained for existing code.
"""

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
