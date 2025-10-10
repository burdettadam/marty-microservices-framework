"""
Authorization and Role-Based Access Control (RBAC) for the enterprise security framework.
"""

import builtins
import logging
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Callable, Dict, Optional, Set

from .auth import AuthenticatedUser
from .errors import AuthorizationError, InsufficientPermissionsError

logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """Permission levels for granular access control."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"


@dataclass
class Permission:
    """Represents a specific permission."""

    name: str
    resource: str
    level: PermissionLevel
    description: str | None = None

    def __str__(self) -> str:
        return f"{self.resource}:{self.level.value}"

    def matches(self, required_permission: str) -> bool:
        """Check if this permission matches a required permission string."""
        return str(self) == required_permission


@dataclass
class Role:
    """Represents a role with associated permissions."""

    name: str
    permissions: builtins.set[Permission] = field(default_factory=set)
    description: str | None = None
    inherits_from: builtins.set[str] = field(default_factory=set)

    def add_permission(self, permission: Permission) -> None:
        """Add a permission to this role."""
        self.permissions.add(permission)

    def has_permission(self, permission_string: str) -> bool:
        """Check if this role has a specific permission."""
        return any(perm.matches(permission_string) for perm in self.permissions)

    def get_all_permissions(
        self, role_registry: builtins.dict[str, "Role"]
    ) -> builtins.set[Permission]:
        """Get all permissions including inherited ones."""
        all_permissions = self.permissions.copy()

        for parent_role_name in self.inherits_from:
            if parent_role_name in role_registry:
                parent_role = role_registry[parent_role_name]
                all_permissions.update(parent_role.get_all_permissions(role_registry))

        return all_permissions


class RoleBasedAccessControl:
    """Role-Based Access Control system."""

    def __init__(self):
        self.roles: builtins.dict[str, Role] = {}
        self.permissions: builtins.dict[str, Permission] = {}
        self._setup_default_roles()

    def _setup_default_roles(self) -> None:
        """Setup default roles and permissions."""
        # Default permissions
        self.register_permission(
            Permission("read", "api", PermissionLevel.READ, "API read access")
        )
        self.register_permission(
            Permission("write", "api", PermissionLevel.WRITE, "API write access")
        )
        self.register_permission(
            Permission("delete", "api", PermissionLevel.DELETE, "API delete access")
        )
        self.register_permission(
            Permission(
                "admin", "system", PermissionLevel.ADMIN, "System administration"
            )
        )

        # Default roles
        user_role = Role("user", description="Basic user role")
        user_role.add_permission(self.permissions["api:read"])

        admin_role = Role("admin", description="Administrator role")
        admin_role.add_permission(self.permissions["api:read"])
        admin_role.add_permission(self.permissions["api:write"])
        admin_role.add_permission(self.permissions["api:delete"])
        admin_role.add_permission(self.permissions["system:admin"])

        service_role = Role("service", description="Service-to-service role")
        service_role.add_permission(self.permissions["api:read"])
        service_role.add_permission(self.permissions["api:write"])

        self.roles["user"] = user_role
        self.roles["admin"] = admin_role
        self.roles["service"] = service_role

    def register_permission(self, permission: Permission) -> None:
        """Register a new permission."""
        self.permissions[str(permission)] = permission

    def register_role(self, role: Role) -> None:
        """Register a new role."""
        self.roles[role.name] = role

    def check_permission(
        self, user: AuthenticatedUser, required_permission: str
    ) -> bool:
        """Check if a user has a specific permission."""
        # Check direct permissions
        if required_permission in user.permissions:
            return True

        # Check role-based permissions
        for role_name in user.roles:
            if role_name in self.roles:
                role = self.roles[role_name]
                if role.has_permission(required_permission):
                    return True

                # Check inherited permissions
                all_permissions = role.get_all_permissions(self.roles)
                for perm in all_permissions:
                    if perm.matches(required_permission):
                        return True

        return False

    def check_role(self, user: AuthenticatedUser, required_role: str) -> bool:
        """Check if a user has a specific role."""
        return required_role in user.roles

    def get_user_permissions(self, user: AuthenticatedUser) -> builtins.set[str]:
        """Get all permissions for a user."""
        all_permissions = set(user.permissions)

        for role_name in user.roles:
            if role_name in self.roles:
                role = self.roles[role_name]
                role_permissions = role.get_all_permissions(self.roles)
                all_permissions.update(str(perm) for perm in role_permissions)

        return all_permissions

    def assign_role_to_user(self, user: AuthenticatedUser, role_name: str) -> bool:
        """Assign a role to a user."""
        if role_name not in self.roles:
            logger.warning("Role '%s' not found", role_name)
            return False

        if role_name not in user.roles:
            user.roles.append(role_name)

        return True

    def revoke_role_from_user(self, user: AuthenticatedUser, role_name: str) -> bool:
        """Revoke a role from a user."""
        if role_name in user.roles:
            user.roles.remove(role_name)
            return True
        return False


# Global RBAC instance
_rbac_instance: RoleBasedAccessControl | None = None


def get_rbac() -> RoleBasedAccessControl:
    """Get the global RBAC instance."""
    # Using module-level variable instead of global
    if "_rbac_instance" not in globals() or globals()["_rbac_instance"] is None:
        globals()["_rbac_instance"] = RoleBasedAccessControl()
    return globals()["_rbac_instance"]


def require_permission(permission: str, raise_exception: bool = True):
    """Decorator to require a specific permission."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Try to find user in kwargs or request context
            user = kwargs.get("user") or kwargs.get("current_user")

            # For FastAPI, check if we have a request object
            request = kwargs.get("request")
            if request and hasattr(request, "state") and hasattr(request.state, "user"):
                user = request.state.user

            if not user:
                if raise_exception:
                    raise AuthorizationError("No authenticated user found")
                return {"error": "Authentication required", "status_code": 401}

            rbac = get_rbac()
            if not rbac.check_permission(user, permission):
                if raise_exception:
                    raise InsufficientPermissionsError(permission)
                return {"error": f"Permission denied: {permission}", "status_code": 403}

            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Try to find user in kwargs or request context
            user = kwargs.get("user") or kwargs.get("current_user")

            # For FastAPI, check if we have a request object
            request = kwargs.get("request")
            if request and hasattr(request, "state") and hasattr(request.state, "user"):
                user = request.state.user

            if not user:
                if raise_exception:
                    raise AuthorizationError("No authenticated user found")
                return {"error": "Authentication required", "status_code": 401}

            rbac = get_rbac()
            if not rbac.check_permission(user, permission):
                if raise_exception:
                    raise InsufficientPermissionsError(permission)
                return {"error": f"Permission denied: {permission}", "status_code": 403}

            return func(*args, **kwargs)

        # Return appropriate wrapper based on whether function is async
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def require_role(role: str, raise_exception: bool = True):
    """Decorator to require a specific role."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Try to find user in kwargs or request context
            user = kwargs.get("user") or kwargs.get("current_user")

            # For FastAPI, check if we have a request object
            request = kwargs.get("request")
            if request and hasattr(request, "state") and hasattr(request.state, "user"):
                user = request.state.user

            if not user:
                if raise_exception:
                    raise AuthorizationError("No authenticated user found")
                return {"error": "Authentication required", "status_code": 401}

            rbac = get_rbac()
            if not rbac.check_role(user, role):
                if raise_exception:
                    raise AuthorizationError(f"Role required: {role}")
                return {"error": f"Role required: {role}", "status_code": 403}

            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Try to find user in kwargs or request context
            user = kwargs.get("user") or kwargs.get("current_user")

            # For FastAPI, check if we have a request object
            request = kwargs.get("request")
            if request and hasattr(request, "state") and hasattr(request.state, "user"):
                user = request.state.user

            if not user:
                if raise_exception:
                    raise AuthorizationError("No authenticated user found")
                return {"error": "Authentication required", "status_code": 401}

            rbac = get_rbac()
            if not rbac.check_role(user, role):
                if raise_exception:
                    raise AuthorizationError(f"Role required: {role}")
                return {"error": f"Role required: {role}", "status_code": 403}

            return func(*args, **kwargs)

        # Return appropriate wrapper based on whether function is async
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def has_permission(user: AuthenticatedUser, permission: str) -> bool:
    """Check if a user has a specific permission."""
    rbac = get_rbac()
    return rbac.check_permission(user, permission)


def has_role(user: AuthenticatedUser, role: str) -> bool:
    """Check if a user has a specific role."""
    rbac = get_rbac()
    return rbac.check_role(user, role)
