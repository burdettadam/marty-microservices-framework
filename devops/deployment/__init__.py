"""
Advanced Deployment Strategies Integration Module

Provides the main interface for the Advanced Deployment Strategies component
of the Marty Microservices Framework's DevOps automation.

This module integrates:
- Multiple deployment strategies (Blue-Green, Canary, Rolling)
- Traffic management and routing
- Deployment automation and orchestration
- Feature flag management
- Health monitoring and validation
"""

from typing import List, Optional, Tuple

from .automation import (  # Automation engine; Configuration; Components
    DeploymentAutomationEngine,
    DeploymentPipeline,
    DeploymentTrigger,
    Environment,
    EnvironmentConfig,
    FeatureFlagManager,
    HealthMonitor,
    PipelineExecution,
    ValidationLevel,
)
from .strategies import (  # Core deployment strategies; Configuration classes; Strategy implementations
    BlueGreenDeploymentStrategy,
    CanaryDeploymentStrategy,
    DeploymentOperation,
    DeploymentOrchestrator,
    DeploymentPhase,
    DeploymentStrategy,
    DeploymentTarget,
    DeploymentValidation,
    RollingDeploymentStrategy,
    TrafficSplit,
    TrafficSplitMethod,
)
from .traffic_management import (  # Traffic management; Traffic managers
    IstioTrafficManager,
    NginxTrafficManager,
    RoutingRule,
    TrafficBackend,
    TrafficDestination,
    TrafficManagerFactory,
    TrafficOrchestrator,
    TrafficPolicy,
    TrafficRoute,
)

# Version information
__version__ = "1.0.0"
__author__ = "Marty Microservices Framework"

# Main exports
__all__ = [
    # Strategy enums and classes
    "DeploymentStrategy",
    "DeploymentPhase",
    "DeploymentTarget",
    "DeploymentValidation",
    "DeploymentOperation",
    # Strategy implementations
    "BlueGreenDeploymentStrategy",
    "CanaryDeploymentStrategy",
    "RollingDeploymentStrategy",
    "DeploymentOrchestrator",
    # Traffic management
    "TrafficBackend",
    "RoutingRule",
    "TrafficDestination",
    "TrafficRoute",
    "TrafficPolicy",
    "TrafficSplit",
    "TrafficSplitMethod",
    "IstioTrafficManager",
    "NginxTrafficManager",
    "TrafficManagerFactory",
    "TrafficOrchestrator",
    # Automation
    "Environment",
    "DeploymentTrigger",
    "ValidationLevel",
    "EnvironmentConfig",
    "DeploymentPipeline",
    "PipelineExecution",
    "FeatureFlagManager",
    "HealthMonitor",
    "DeploymentAutomationEngine",
]


def create_deployment_orchestrator():
    """
    Create a deployment orchestrator with all strategies enabled

    Returns:
        DeploymentOrchestrator: Configured orchestrator instance
    """
    return DeploymentOrchestrator()


def create_traffic_orchestrator(backend=TrafficBackend.ISTIO):
    """
    Create a traffic orchestrator with specified backend

    Args:
        backend: Traffic management backend to use

    Returns:
        TrafficOrchestrator: Configured traffic orchestrator
    """
    return TrafficOrchestrator(backend)


def create_automation_engine():
    """
    Create a deployment automation engine with all components

    Returns:
        DeploymentAutomationEngine: Configured automation engine
    """
    return DeploymentAutomationEngine()


def create_simple_deployment_target(
    name: str,
    namespace: str = "default",
    replicas: int = 3,
    image: str = "",
    tag: str = "latest",
) -> DeploymentTarget:
    """
    Create a simple deployment target configuration

    Args:
        name: Application name
        namespace: Kubernetes namespace
        replicas: Number of replicas
        image: Container image
        tag: Image tag

    Returns:
        DeploymentTarget: Configured deployment target
    """
    return DeploymentTarget(
        name=name, namespace=namespace, replicas=replicas, image=image, tag=tag
    )


def create_standard_validation() -> DeploymentValidation:
    """
    Create standard validation configuration

    Returns:
        DeploymentValidation: Standard validation config
    """
    return DeploymentValidation(
        enabled=True,
        health_check_enabled=True,
        performance_check_enabled=True,
        auto_rollback_enabled=True,
        error_threshold=0.05,
        custom_validations=[
            {"name": "database_connectivity", "type": "database_connectivity"}
        ],
    )


def create_environment_config(
    name: str,
    environment: Environment,
    namespace: Optional[str] = None,
    replicas: int = 3,
    validation_level: ValidationLevel = ValidationLevel.STANDARD,
) -> EnvironmentConfig:
    """
    Create environment configuration

    Args:
        name: Environment name
        environment: Environment type
        namespace: Kubernetes namespace (defaults to name)
        replicas: Minimum replicas
        validation_level: Validation strictness

    Returns:
        EnvironmentConfig: Configured environment
    """
    return EnvironmentConfig(
        name=name,
        environment=environment,
        namespace=namespace or name,
        min_replicas=replicas,
        validation_level=validation_level,
    )


# Convenience functions for common deployment patterns
class DeploymentPatterns:
    """
    Pre-configured deployment patterns for common use cases
    """

    @staticmethod
    def microservice_pipeline(
        app_name: str, environments: Optional[List[str]] = None
    ) -> DeploymentPipeline:
        """
        Create a standard microservice deployment pipeline

        Args:
            app_name: Application name
            environments: List of environment names (default: dev, staging, prod)

        Returns:
            DeploymentPipeline: Configured pipeline
        """
        if environments is None:
            environments = ["development", "staging", "production"]

        env_configs = []
        env_map = {
            "development": Environment.DEVELOPMENT,
            "staging": Environment.STAGING,
            "production": Environment.PRODUCTION,
        }

        for env_name in environments:
            env_type = env_map.get(env_name, Environment.DEVELOPMENT)

            # Configure environment-specific settings
            if env_name == "development":
                replicas = 1
                validation = ValidationLevel.BASIC
            elif env_name == "staging":
                replicas = 2
                validation = ValidationLevel.STANDARD
            else:  # production
                replicas = 3
                validation = ValidationLevel.STRICT

            env_config = create_environment_config(
                name=env_name,
                environment=env_type,
                replicas=replicas,
                validation_level=validation,
            )
            env_configs.append(env_config)

        return DeploymentPipeline(
            name=f"{app_name}-pipeline",
            application_name=app_name,
            environments=env_configs,
            strategy_per_env={
                "development": DeploymentStrategy.ROLLING,
                "staging": DeploymentStrategy.CANARY,
                "production": DeploymentStrategy.BLUE_GREEN,
            },
            approval_required={"production": True},
            auto_promote={"development": True, "staging": True, "production": False},
        )

    @staticmethod
    def canary_traffic_route(
        app_name: str,
        stable_weight: int = 90,
        canary_weight: int = 10,
        namespace: str = "default",
    ) -> TrafficRoute:
        """
        Create a canary traffic route configuration

        Args:
            app_name: Application name
            stable_weight: Percentage of traffic to stable version
            canary_weight: Percentage of traffic to canary version
            namespace: Kubernetes namespace

        Returns:
            TrafficRoute: Configured traffic route
        """
        stable_dest = TrafficDestination(
            name=f"{app_name}-stable",
            host=f"{app_name}.{namespace}.svc.cluster.local",
            port=80,
            weight=stable_weight,
            subset="stable",
            labels={"version": "stable"},
        )

        canary_dest = TrafficDestination(
            name=f"{app_name}-canary",
            host=f"{app_name}.{namespace}.svc.cluster.local",
            port=80,
            weight=canary_weight,
            subset="canary",
            labels={"version": "canary"},
        )

        return TrafficRoute(
            name=f"{app_name}-canary-route",
            rule_type=RoutingRule.WEIGHTED,
            destinations=[stable_dest, canary_dest],
            match_paths=["/"],
            timeout=30,
            retries=3,
        )

    @staticmethod
    def blue_green_deployment_config(
        app_name: str,
        image: str,
        new_tag: str,
        namespace: str = "default",
        replicas: int = 3,
    ) -> Tuple[DeploymentTarget, DeploymentValidation]:
        """
        Create blue-green deployment configuration

        Args:
            app_name: Application name
            image: Container image
            new_tag: New image tag to deploy
            namespace: Kubernetes namespace
            replicas: Number of replicas

        Returns:
            Tuple of (DeploymentTarget, DeploymentValidation)
        """
        target = DeploymentTarget(
            name=app_name,
            namespace=namespace,
            replicas=replicas,
            image=image,
            tag=new_tag,
            labels={"app": app_name, "deployment-strategy": "blue-green"},
        )

        validation = DeploymentValidation(
            enabled=True,
            health_check_enabled=True,
            performance_check_enabled=True,
            auto_rollback_enabled=True,
            error_threshold=0.02,  # Strict for blue-green
            custom_validations=[
                {"name": "smoke_test", "type": "smoke_test"},
                {"name": "integration_test", "type": "integration_test"},
            ],
        )

        return target, validation


# Export patterns class
__all__.append("DeploymentPatterns")
