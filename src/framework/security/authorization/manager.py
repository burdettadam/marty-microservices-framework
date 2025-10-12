"""
Authorization Management Module

Advanced authorization and access control including role-based access control (RBAC),
attribute-based access control (ABAC), access control lists (ACLs), and policy evaluation.
"""

import builtins
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from framework.security.models import SecurityPrincipal


class PolicyEngine:
    """Policy evaluation engine for ABAC."""

    def evaluate_policies(
        self,
        policies: builtins.dict[str, builtins.dict[str, Any]],
        context: builtins.dict[str, Any],
    ) -> bool:
        """Evaluate policies against context."""
        for policy_name, policy_data in policies.items():
            try:
                if self._evaluate_policy(policy_data, context):
                    return True
            except Exception as e:
                print(f"Policy evaluation error for {policy_name}: {e}")

        return False

    def _evaluate_policy(
        self, policy: builtins.dict[str, Any], context: builtins.dict[str, Any]
    ) -> bool:
        """Evaluate a single policy."""
        conditions = policy.get("conditions", [])

        for condition in conditions:
            if not self._evaluate_condition(condition, context):
                return False

        return True

    def _evaluate_condition(
        self, condition: builtins.dict[str, Any], context: builtins.dict[str, Any]
    ) -> bool:
        """Evaluate a single condition."""
        operator = condition.get("operator")
        attribute = condition.get("attribute")
        value = condition.get("value")

        if not all([operator, attribute]):
            return False

        context_value = self._get_context_value(attribute, context)

        if operator == "equals":
            return context_value == value
        if operator == "not_equals":
            return context_value != value
        if operator == "in":
            return context_value in value if isinstance(value, list) else False
        if operator == "greater_than":
            return context_value > value
        if operator == "less_than":
            return context_value < value
        if operator == "matches":
            return re.match(value, str(context_value)) is not None

        return False

    def _get_context_value(self, attribute: str, context: builtins.dict[str, Any]) -> Any:
        """Get value from context using dot notation."""
        keys = attribute.split(".")
        value = context

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            elif hasattr(value, key):
                value = getattr(value, key)
            else:
                return None

        return value


class AuthorizationManager:
    """Advanced authorization and access control."""

    def __init__(self, service_name: str):
        """Initialize authorization manager."""
        self.service_name = service_name

        # Role-based access control
        self.roles: builtins.dict[str, builtins.dict[str, Any]] = {}
        self.permissions: builtins.dict[str, builtins.dict[str, Any]] = {}
        self.role_hierarchy: builtins.dict[str, builtins.list[str]] = {}

        # Attribute-based access control
        self.policies: builtins.dict[str, builtins.dict[str, Any]] = {}
        self.policy_engine = PolicyEngine()

        # Access control lists
        self.resource_acls: builtins.dict[str, builtins.dict[str, builtins.set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )

        # Initialize default roles and permissions
        self._initialize_default_rbac()

    def _initialize_default_rbac(self):
        """Initialize default roles and permissions."""
        # Default permissions
        self.permissions.update(
            {
                "read": {"description": "Read access to resources"},
                "write": {"description": "Write access to resources"},
                "delete": {"description": "Delete access to resources"},
                "admin": {"description": "Administrative access"},
                "execute": {"description": "Execute operations"},
            }
        )

        # Default roles
        self.roles.update(
            {
                "viewer": {
                    "description": "Read-only access",
                    "permissions": ["read"],
                    "inherits": [],
                },
                "editor": {
                    "description": "Read and write access",
                    "permissions": ["read", "write"],
                    "inherits": ["viewer"],
                },
                "admin": {
                    "description": "Full administrative access",
                    "permissions": ["read", "write", "delete", "admin", "execute"],
                    "inherits": ["editor"],
                },
                "service": {
                    "description": "Service-to-service access",
                    "permissions": ["read", "write", "execute"],
                    "inherits": [],
                },
            }
        )

        # Role hierarchy
        self.role_hierarchy = {
            "admin": ["editor", "viewer"],
            "editor": ["viewer"],
            "service": [],
            "viewer": [],
        }

    def create_role(
        self,
        role_name: str,
        description: str,
        permissions: builtins.list[str],
        inherits: builtins.list[str] = None,
    ) -> bool:
        """Create a new role."""
        try:
            if role_name in self.roles:
                return False

            # Validate permissions
            for permission in permissions:
                if permission not in self.permissions:
                    return False

            # Validate inherited roles
            inherits = inherits or []
            for inherited_role in inherits:
                if inherited_role not in self.roles:
                    return False

            self.roles[role_name] = {
                "description": description,
                "permissions": permissions,
                "inherits": inherits,
            }

            # Update role hierarchy
            self.role_hierarchy[role_name] = inherits

            return True

        except Exception as e:
            print(f"Error creating role: {e}")
            return False

    def create_permission(
        self, permission_name: str, description: str, resource_pattern: str = "*"
    ) -> bool:
        """Create a new permission."""
        try:
            self.permissions[permission_name] = {
                "description": description,
                "resource_pattern": resource_pattern,
            }
            return True
        except Exception:
            return False

    def assign_role_to_principal(self, principal_id: str, role_name: str) -> bool:
        """Assign role to principal."""
        if role_name not in self.roles:
            return False

        # This would typically update the principal's roles in the authentication manager
        # For now, we'll just track the assignment
        return True

    def check_permission(self, principal: SecurityPrincipal, resource: str, action: str) -> bool:
        """Check if principal has permission to perform action on resource."""
        try:
            # Check direct permissions
            if action in principal.permissions:
                return True

            # Check role-based permissions
            effective_permissions = self._get_effective_permissions(principal.roles)
            if action in effective_permissions:
                return True

            # Check attribute-based policies
            if self._check_abac_policies(principal, resource, action):
                return True

            # Check ACLs
            if self._check_acl_permission(principal.id, resource, action):
                return True

            return False

        except Exception as e:
            print(f"Permission check error: {e}")
            return False

    def _get_effective_permissions(self, roles: builtins.list[str]) -> builtins.set[str]:
        """Get effective permissions from roles including inheritance."""
        effective_permissions = set()

        def add_role_permissions(role_name: str):
            if role_name in self.roles:
                role_data = self.roles[role_name]
                effective_permissions.update(role_data["permissions"])

                # Add inherited permissions
                for inherited_role in role_data.get("inherits", []):
                    add_role_permissions(inherited_role)

        for role in roles:
            add_role_permissions(role)

        return effective_permissions

    def _check_abac_policies(
        self, principal: SecurityPrincipal, resource: str, action: str
    ) -> bool:
        """Check attribute-based access control policies."""
        # Simplified ABAC implementation
        context = {
            "principal": principal,
            "resource": resource,
            "action": action,
            "time": datetime.now(timezone.utc),
            "security_level": principal.security_level.value,
        }

        return self.policy_engine.evaluate_policies(self.policies, context)

    def _check_acl_permission(self, principal_id: str, resource: str, action: str) -> bool:
        """Check access control list permissions."""
        if resource in self.resource_acls:
            acl = self.resource_acls[resource]
            return principal_id in acl.get(action, set())
        return False

    def grant_acl_permission(self, principal_id: str, resource: str, action: str):
        """Grant ACL permission to principal."""
        self.resource_acls[resource][action].add(principal_id)

    def revoke_acl_permission(self, principal_id: str, resource: str, action: str):
        """Revoke ACL permission from principal."""
        if resource in self.resource_acls:
            self.resource_acls[resource][action].discard(principal_id)
