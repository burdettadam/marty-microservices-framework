"""
Configuration Management

Comprehensive configuration management for service mesh including
validation, synchronization, and policy management.
"""

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class ConfigFormat(Enum):
    """Configuration formats."""

    JSON = "json"
    YAML = "yaml"
    TOML = "toml"


class ValidationLevel(Enum):
    """Configuration validation levels."""

    STRICT = "strict"
    WARNING = "warning"
    PERMISSIVE = "permissive"


@dataclass
class ValidationResult:
    """Configuration validation result."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        """Add validation error."""
        self.errors.append(message)
        self.valid = False

    def add_warning(self, message: str) -> None:
        """Add validation warning."""
        self.warnings.append(message)

    def add_suggestion(self, message: str) -> None:
        """Add validation suggestion."""
        self.suggestions.append(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
        }


@dataclass
class ServiceMeshConfiguration:
    """Service mesh configuration."""

    # Core settings
    mesh_id: str
    provider: str
    namespace: str = "istio-system"
    version: str = "1.0"

    # Feature flags
    mtls_enabled: bool = True
    tracing_enabled: bool = True
    metrics_enabled: bool = True
    security_enabled: bool = True

    # Traffic management
    default_timeout_seconds: int = 30
    default_retries: int = 3
    circuit_breaker_enabled: bool = True
    load_balancing_algorithm: str = "round_robin"

    # Security settings
    rbac_enabled: bool = True
    jwt_validation_enabled: bool = False
    certificate_auto_rotation: bool = True
    certificate_lifetime_days: int = 90

    # Observability settings
    telemetry_v2_enabled: bool = True
    access_logging_enabled: bool = True
    prometheus_enabled: bool = True
    jaeger_enabled: bool = True
    grafana_enabled: bool = True

    # Resource limits
    proxy_cpu_limit: str = "100m"
    proxy_memory_limit: str = "128Mi"
    proxy_cpu_request: str = "50m"
    proxy_memory_request: str = "64Mi"

    # Custom configuration
    custom_config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServiceMeshConfiguration":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class PolicyConfiguration:
    """Policy configuration container."""

    authentication_policies: list[dict[str, Any]] = field(default_factory=list)
    authorization_policies: list[dict[str, Any]] = field(default_factory=list)
    peer_authentications: list[dict[str, Any]] = field(default_factory=list)
    request_authentications: list[dict[str, Any]] = field(default_factory=list)
    rbac_policies: list[dict[str, Any]] = field(default_factory=list)

    def add_authentication_policy(self, policy: dict[str, Any]) -> None:
        """Add authentication policy."""
        self.authentication_policies.append(policy)

    def add_authorization_policy(self, policy: dict[str, Any]) -> None:
        """Add authorization policy."""
        self.authorization_policies.append(policy)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class SecurityConfiguration:
    """Security configuration container."""

    # mTLS settings
    mtls_mode: str = "STRICT"
    mtls_permissive_services: list[str] = field(default_factory=list)

    # Certificate settings
    root_ca_certificate: str | None = None
    certificate_chain: str | None = None
    trust_domain: str = "cluster.local"

    # JWT settings
    jwt_issuers: list[str] = field(default_factory=list)
    jwt_audiences: list[str] = field(default_factory=list)
    jwks_uri: str | None = None

    # RBAC settings
    rbac_inclusion_services: list[str] = field(default_factory=list)
    rbac_exclusion_services: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class ObservabilityConfiguration:
    """Observability configuration container."""

    # Metrics settings
    metrics_port: int = 15090
    metrics_path: str = "/stats/prometheus"
    metrics_scrape_interval: str = "30s"

    # Tracing settings
    tracing_sampling_rate: float = 0.1
    jaeger_endpoint: str | None = None
    zipkin_endpoint: str | None = None

    # Logging settings
    access_log_format: str = "json"
    access_log_encoding: str = "utf-8"
    log_level: str = "info"

    # Telemetry settings
    telemetry_filters: list[str] = field(default_factory=list)
    telemetry_providers: list[str] = field(
        default_factory=lambda: ["prometheus", "jaeger"]
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class TrafficConfiguration:
    """Traffic management configuration container."""

    # Load balancing
    default_lb_algorithm: str = "round_robin"
    session_affinity_enabled: bool = False

    # Circuit breaker settings
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout_seconds: int = 60

    # Retry settings
    default_retry_attempts: int = 3
    retry_backoff_seconds: float = 1.0
    retry_max_backoff_seconds: float = 10.0

    # Timeout settings
    default_request_timeout_seconds: int = 30
    default_idle_timeout_seconds: int = 300

    # Connection pool settings
    max_connections: int = 100
    max_pending_requests: int = 100
    max_requests_per_connection: int = 10

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class ConfigValidator(ABC):
    """Abstract configuration validator."""

    @abstractmethod
    def validate(self, config: dict[str, Any]) -> ValidationResult:
        """Validate configuration."""
        raise NotImplementedError


class MeshConfigValidator(ConfigValidator):
    """Service mesh configuration validator."""

    def __init__(self, validation_level: ValidationLevel = ValidationLevel.STRICT):
        self.validation_level = validation_level
        self._rules: list[Callable[[dict[str, Any]], ValidationResult]] = []
        self._setup_default_rules()

    def _setup_default_rules(self) -> None:
        """Setup default validation rules."""
        self._rules.extend(
            [
                self._validate_required_fields,
                self._validate_provider,
                self._validate_namespace,
                self._validate_timeouts,
                self._validate_resource_limits,
                self._validate_security_settings,
            ]
        )

    def add_rule(self, rule: Callable[[dict[str, Any]], ValidationResult]) -> None:
        """Add custom validation rule."""
        self._rules.append(rule)

    def validate(self, config: dict[str, Any]) -> ValidationResult:
        """Validate mesh configuration."""
        result = ValidationResult(valid=True)

        for rule in self._rules:
            rule_result = rule(config)

            # Merge results
            result.errors.extend(rule_result.errors)
            result.warnings.extend(rule_result.warnings)
            result.suggestions.extend(rule_result.suggestions)

            if not rule_result.valid:
                result.valid = False

        return result

    def _validate_required_fields(self, config: dict[str, Any]) -> ValidationResult:
        """Validate required fields."""
        result = ValidationResult(valid=True)

        required_fields = ["mesh_id", "provider"]
        for field_name in required_fields:
            if field_name not in config:
                result.add_error(f"Required field '{field_name}' is missing")

        return result

    def _validate_provider(self, config: dict[str, Any]) -> ValidationResult:
        """Validate provider configuration."""
        result = ValidationResult(valid=True)

        valid_providers = ["istio", "linkerd", "consul_connect", "envoy", "kuma"]
        provider = config.get("provider", "").lower()

        if provider not in valid_providers:
            result.add_error(
                f"Invalid provider '{provider}'. Valid providers: {valid_providers}"
            )

        return result

    def _validate_namespace(self, config: dict[str, Any]) -> ValidationResult:
        """Validate namespace configuration."""
        result = ValidationResult(valid=True)

        namespace = config.get("namespace", "")
        if namespace and not namespace.replace("-", "").replace("_", "").isalnum():
            result.add_warning(f"Namespace '{namespace}' contains special characters")

        return result

    def _validate_timeouts(self, config: dict[str, Any]) -> ValidationResult:
        """Validate timeout settings."""
        result = ValidationResult(valid=True)

        timeout_fields = ["default_timeout_seconds"]
        for timeout_field in timeout_fields:
            if timeout_field in config:
                value = config[timeout_field]
                if not isinstance(value, int) or value <= 0:
                    result.add_error(f"'{timeout_field}' must be a positive integer")
                elif value > 3600:  # 1 hour
                    result.add_warning(f"'{timeout_field}' value {value} is very high")

        return result

    def _validate_resource_limits(self, config: dict[str, Any]) -> ValidationResult:
        """Validate resource limits."""
        result = ValidationResult(valid=True)

        resource_fields = ["proxy_cpu_limit", "proxy_memory_limit"]
        for resource_field in resource_fields:
            if resource_field in config:
                value = config[resource_field]
                if not isinstance(value, str):
                    result.add_error(f"'{resource_field}' must be a string")

        return result

    def _validate_security_settings(self, config: dict[str, Any]) -> ValidationResult:
        """Validate security settings."""
        result = ValidationResult(valid=True)

        if config.get("mtls_enabled", True) is False:
            result.add_warning("mTLS is disabled - this reduces security")

        if config.get("security_enabled", True) is False:
            result.add_warning("Security features are disabled")

        return result


class ConfigSynchronizer:
    """Configuration synchronization manager."""

    def __init__(self):
        self._configurations: dict[str, dict[str, Any]] = {}
        self._watchers: list[Callable[[str, dict[str, Any]], None]] = []
        self._last_sync: datetime | None = None

    def register_configuration(self, name: str, config: dict[str, Any]) -> None:
        """Register configuration."""
        self._configurations[name] = config.copy()
        self._notify_watchers(name, config)

    def update_configuration(self, name: str, updates: dict[str, Any]) -> None:
        """Update configuration."""
        if name in self._configurations:
            self._configurations[name].update(updates)
            self._notify_watchers(name, self._configurations[name])
        else:
            raise ValueError(f"Configuration '{name}' not found")

    def get_configuration(self, name: str) -> dict[str, Any] | None:
        """Get configuration."""
        return self._configurations.get(name)

    def list_configurations(self) -> list[str]:
        """List configuration names."""
        return list(self._configurations.keys())

    def add_watcher(self, watcher: Callable[[str, dict[str, Any]], None]) -> None:
        """Add configuration watcher."""
        self._watchers.append(watcher)

    def _notify_watchers(self, name: str, config: dict[str, Any]) -> None:
        """Notify configuration watchers."""
        for watcher in self._watchers:
            try:
                watcher(name, config)
            except Exception as e:
                logger.error(f"Configuration watcher error: {e}")

    def sync_configurations(self) -> dict[str, Any]:
        """Synchronize configurations."""
        self._last_sync = datetime.utcnow()

        sync_result = {
            "synchronized_at": self._last_sync.isoformat(),
            "configuration_count": len(self._configurations),
            "configurations": list(self._configurations.keys()),
        }

        logger.info(f"Synchronized {len(self._configurations)} configurations")
        return sync_result

    def export_configurations(self, format: ConfigFormat = ConfigFormat.YAML) -> str:
        """Export configurations."""
        if format == ConfigFormat.JSON:
            return json.dumps(self._configurations, indent=2)
        if format == ConfigFormat.YAML:
            return yaml.dump(self._configurations, default_flow_style=False)
        raise ValueError(f"Unsupported format: {format}")

    def import_configurations(
        self, data: str, format: ConfigFormat = ConfigFormat.YAML
    ) -> None:
        """Import configurations."""
        if format == ConfigFormat.JSON:
            configs = json.loads(data)
        elif format == ConfigFormat.YAML:
            configs = yaml.safe_load(data)
        else:
            raise ValueError(f"Unsupported format: {format}")

        for name, config in configs.items():
            self.register_configuration(name, config)


class ConfigurationManager:
    """Comprehensive configuration management."""

    def __init__(self):
        self.mesh_config: ServiceMeshConfiguration | None = None
        self.policy_config = PolicyConfiguration()
        self.security_config = SecurityConfiguration()
        self.observability_config = ObservabilityConfiguration()
        self.traffic_config = TrafficConfiguration()

        self.validator = MeshConfigValidator()
        self.synchronizer = ConfigSynchronizer()

    def set_mesh_configuration(
        self, config: ServiceMeshConfiguration
    ) -> ValidationResult:
        """Set mesh configuration."""
        # Validate configuration
        validation_result = self.validator.validate(config.to_dict())

        if (
            validation_result.valid
            or self.validator.validation_level != ValidationLevel.STRICT
        ):
            self.mesh_config = config
            self.synchronizer.register_configuration("mesh", config.to_dict())

        return validation_result

    def update_mesh_configuration(self, updates: dict[str, Any]) -> ValidationResult:
        """Update mesh configuration."""
        if not self.mesh_config:
            raise ValueError("Mesh configuration not initialized")

        # Create updated config for validation
        current_config = self.mesh_config.to_dict()
        current_config.update(updates)

        # Validate updates
        validation_result = self.validator.validate(current_config)

        if (
            validation_result.valid
            or self.validator.validation_level != ValidationLevel.STRICT
        ):
            # Apply updates
            for key, value in updates.items():
                if hasattr(self.mesh_config, key):
                    setattr(self.mesh_config, key, value)

            self.synchronizer.update_configuration("mesh", updates)

        return validation_result

    def get_complete_configuration(self) -> dict[str, Any]:
        """Get complete configuration."""
        return {
            "mesh": self.mesh_config.to_dict() if self.mesh_config else {},
            "policy": self.policy_config.to_dict(),
            "security": self.security_config.to_dict(),
            "observability": self.observability_config.to_dict(),
            "traffic": self.traffic_config.to_dict(),
        }

    def apply_configuration_template(self, template_name: str) -> None:
        """Apply configuration template."""
        templates = {
            "production": self._get_production_template(),
            "development": self._get_development_template(),
            "testing": self._get_testing_template(),
        }

        if template_name not in templates:
            raise ValueError(f"Unknown template: {template_name}")

        template = templates[template_name]

        # Apply mesh configuration
        if "mesh" in template:
            mesh_config = ServiceMeshConfiguration.from_dict(template["mesh"])
            self.set_mesh_configuration(mesh_config)

        # Apply other configurations
        if "security" in template:
            self.security_config = SecurityConfiguration(**template["security"])

        if "observability" in template:
            self.observability_config = ObservabilityConfiguration(
                **template["observability"]
            )

        if "traffic" in template:
            self.traffic_config = TrafficConfiguration(**template["traffic"])

    def _get_production_template(self) -> dict[str, Any]:
        """Get production configuration template."""
        return {
            "mesh": {
                "mesh_id": "production-mesh",
                "provider": "istio",
                "mtls_enabled": True,
                "security_enabled": True,
                "rbac_enabled": True,
                "default_timeout_seconds": 30,
                "circuit_breaker_enabled": True,
            },
            "security": {"mtls_mode": "STRICT", "trust_domain": "cluster.local"},
            "observability": {
                "tracing_sampling_rate": 0.01,  # 1% for production
                "log_level": "warn",
            },
            "traffic": {"circuit_breaker_enabled": True, "default_retry_attempts": 3},
        }

    def _get_development_template(self) -> dict[str, Any]:
        """Get development configuration template."""
        return {
            "mesh": {
                "mesh_id": "development-mesh",
                "provider": "istio",
                "mtls_enabled": False,  # Relaxed for development
                "security_enabled": True,
                "rbac_enabled": False,
                "default_timeout_seconds": 60,
                "circuit_breaker_enabled": False,
            },
            "security": {"mtls_mode": "PERMISSIVE"},
            "observability": {
                "tracing_sampling_rate": 1.0,  # 100% for development
                "log_level": "debug",
            },
            "traffic": {"circuit_breaker_enabled": False, "default_retry_attempts": 1},
        }

    def _get_testing_template(self) -> dict[str, Any]:
        """Get testing configuration template."""
        return {
            "mesh": {
                "mesh_id": "testing-mesh",
                "provider": "istio",
                "mtls_enabled": True,
                "security_enabled": True,
                "rbac_enabled": True,
                "default_timeout_seconds": 10,  # Fast timeouts for testing
                "circuit_breaker_enabled": True,
            },
            "security": {"mtls_mode": "STRICT"},
            "observability": {
                "tracing_sampling_rate": 1.0,  # 100% for testing
                "log_level": "info",
            },
            "traffic": {
                "circuit_breaker_enabled": True,
                "circuit_breaker_threshold": 2,  # Lower threshold for testing
                "default_retry_attempts": 1,
            },
        }


# Utility functions


def create_mesh_configuration(
    mesh_id: str, provider: str, **kwargs
) -> ServiceMeshConfiguration:
    """Create mesh configuration."""
    return ServiceMeshConfiguration(mesh_id=mesh_id, provider=provider, **kwargs)


def validate_configuration(
    config: dict[str, Any], validation_level: ValidationLevel = ValidationLevel.STRICT
) -> ValidationResult:
    """Validate configuration."""
    validator = MeshConfigValidator(validation_level)
    return validator.validate(config)


def create_configuration_manager() -> ConfigurationManager:
    """Create configuration manager."""
    return ConfigurationManager()
