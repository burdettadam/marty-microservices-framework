"""
Security Hardening Framework Main Module

Main security hardening framework that integrates all security components
including authentication, authorization, cryptography, secrets management,
and security scanning.
"""

import builtins
import uuid
from collections import deque
from typing import Any

from .authentication.manager import AuthenticationManager
from .authorization.manager import AuthorizationManager
from .cryptography.manager import CryptographyManager
from .models import (
    AuthenticationMethod,
    ComplianceStandard,
    SecurityEvent,
    SecurityThreatLevel,
    SecurityToken,
)
from .scanning.scanner import SecurityScanner
from .secrets.manager import SecretsManager


class SecurityHardeningFramework:
    """Main security hardening framework."""

    def __init__(self, service_name: str):
        """Initialize security hardening framework."""
        self.service_name = service_name

        # Core security components
        self.crypto_manager = CryptographyManager(service_name)
        self.auth_manager = AuthenticationManager(service_name, self.crypto_manager)
        self.authz_manager = AuthorizationManager(service_name)
        self.secrets_manager = SecretsManager(service_name, self.crypto_manager)
        self.security_scanner = SecurityScanner(service_name)

        # Security monitoring
        self.security_events: deque = deque(maxlen=10000)
        self.threat_detection_enabled = True

        # Compliance tracking
        self.compliance_standards: builtins.set[ComplianceStandard] = set()
        self.compliance_status: builtins.dict[str, bool] = {}

    def initialize_security(self, config: builtins.dict[str, Any]):
        """Initialize security framework with configuration."""
        # Set up authentication policies
        if "password_policy" in config:
            self.auth_manager.password_policy.update(config["password_policy"])

        # Set up authorization policies
        if "custom_roles" in config:
            for role_name, role_config in config["custom_roles"].items():
                self.authz_manager.create_role(
                    role_name,
                    role_config.get("description", ""),
                    role_config.get("permissions", []),
                    role_config.get("inherits", []),
                )

        # Set up compliance standards
        if "compliance_standards" in config:
            for standard in config["compliance_standards"]:
                try:
                    self.compliance_standards.add(ComplianceStandard(standard))
                except ValueError:
                    print(f"Unknown compliance standard: {standard}")

    def authenticate_principal(
        self,
        principal_id: str,
        credentials: builtins.dict[str, Any],
        method: AuthenticationMethod,
    ) -> SecurityToken | None:
        """Authenticate a principal."""
        token = self.auth_manager.authenticate(principal_id, credentials, method)

        # Log security event
        self._log_security_event(
            event_type="authentication",
            principal_id=principal_id,
            resource="auth_system",
            action="authenticate",
            result="success" if token else "failure",
            threat_level=SecurityThreatLevel.LOW if token else SecurityThreatLevel.MEDIUM,
        )

        return token

    def authorize_action(self, token_id: str, resource: str, action: str) -> bool:
        """Authorize an action for a token holder."""
        # Validate token
        principal = self.auth_manager.validate_token(token_id)
        if not principal:
            self._log_security_event(
                event_type="authorization",
                principal_id=None,
                resource=resource,
                action=action,
                result="blocked",
                threat_level=SecurityThreatLevel.MEDIUM,
                details={"reason": "invalid_token"},
            )
            return False

        # Check authorization
        authorized = self.authz_manager.check_permission(principal, resource, action)

        # Log security event
        self._log_security_event(
            event_type="authorization",
            principal_id=principal.id,
            resource=resource,
            action=action,
            result="success" if authorized else "blocked",
            threat_level=SecurityThreatLevel.LOW if authorized else SecurityThreatLevel.MEDIUM,
        )

        return authorized

    def scan_for_vulnerabilities(
        self, scan_targets: builtins.dict[str, Any]
    ) -> builtins.dict[str, builtins.list]:
        """Perform comprehensive security scan."""
        results = {}

        # Scan code
        if "code" in scan_targets:
            code_vulns = []
            for file_path, content in scan_targets["code"].items():
                vulns = self.security_scanner.scan_code(content, file_path)
                code_vulns.extend(vulns)
            results["code"] = code_vulns

        # Scan configuration
        if "config" in scan_targets:
            config_vulns = self.security_scanner.scan_configuration(scan_targets["config"])
            results["configuration"] = config_vulns

        # Scan dependencies
        if "dependencies" in scan_targets:
            dep_vulns = self.security_scanner.scan_dependencies(scan_targets["dependencies"])
            results["dependencies"] = dep_vulns

        return results

    def get_security_status(self) -> builtins.dict[str, Any]:
        """Get comprehensive security status."""
        # Authentication status
        auth_stats = {
            "active_tokens": len(self.auth_manager.active_tokens),
            "revoked_tokens": len(self.auth_manager.revoked_tokens),
            "locked_accounts": len(self.auth_manager.locked_accounts),
            "registered_principals": len(self.auth_manager.principals),
        }

        # Authorization status
        authz_stats = {
            "defined_roles": len(self.authz_manager.roles),
            "defined_permissions": len(self.authz_manager.permissions),
            "active_policies": len(self.authz_manager.policies),
        }

        # Secrets status
        secrets_stats = {
            "stored_secrets": len(self.secrets_manager.secrets),
            "secrets_requiring_rotation": len(
                self.secrets_manager.get_secrets_requiring_rotation()
            ),
        }

        # Vulnerability status
        vuln_summary = self.security_scanner.get_vulnerability_summary()

        # Recent security events
        recent_events = list(self.security_events)[-10:]

        return {
            "service": self.service_name,
            "authentication": auth_stats,
            "authorization": authz_stats,
            "secrets_management": secrets_stats,
            "vulnerabilities": vuln_summary,
            "recent_security_events": len(recent_events),
            "compliance_standards": [s.value for s in self.compliance_standards],
            "threat_detection_enabled": self.threat_detection_enabled,
        }

    def _log_security_event(
        self,
        event_type: str,
        principal_id: str | None,
        resource: str,
        action: str,
        result: str,
        threat_level: SecurityThreatLevel,
        details: builtins.dict[str, Any] | None = None,
    ):
        """Log security event for audit and monitoring."""
        event = SecurityEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            principal_id=principal_id,
            resource=resource,
            action=action,
            result=result,
            threat_level=threat_level,
            details=details or {},
        )

        self.security_events.append(event)


def create_security_framework(
    service_name: str, config: builtins.dict[str, Any] | None = None
) -> SecurityHardeningFramework:
    """Create security hardening framework instance."""
    framework = SecurityHardeningFramework(service_name)
    if config:
        framework.initialize_security(config)
    return framework
