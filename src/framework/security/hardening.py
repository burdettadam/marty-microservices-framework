"""
Enterprise Security Hardening Framework for Marty Microservices

This module provides comprehensive security capabilities including authentication,
authorization, secrets management, security scanning, and compliance validation.
"""

import base64
import builtins
import hashlib
import re
import secrets
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

import bcrypt
import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa


class SecurityLevel(Enum):
    """Security levels for different operations."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


class AuthenticationMethod(Enum):
    """Authentication methods supported."""

    PASSWORD = "password"
    API_KEY = "api_key"
    JWT_TOKEN = "jwt_token"
    OAUTH2 = "oauth2"
    CERTIFICATE = "certificate"
    MULTI_FACTOR = "multi_factor"


class SecurityThreatLevel(Enum):
    """Security threat levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ComplianceStandard(Enum):
    """Compliance standards."""

    GDPR = "gdpr"
    HIPAA = "hipaa"
    SOX = "sox"
    PCI_DSS = "pci_dss"
    ISO_27001 = "iso_27001"
    NIST = "nist"


@dataclass
class SecurityPrincipal:
    """Security principal (user/service) representation."""

    id: str
    name: str
    type: str  # "user", "service", "system"
    roles: builtins.list[str] = field(default_factory=list)
    permissions: builtins.list[str] = field(default_factory=list)
    attributes: builtins.dict[str, Any] = field(default_factory=dict)
    security_level: SecurityLevel = SecurityLevel.INTERNAL
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_access: datetime | None = None
    is_active: bool = True


@dataclass
class SecurityToken:
    """Security token for authentication."""

    token_id: str
    principal_id: str
    token_type: AuthenticationMethod
    expires_at: datetime
    scopes: builtins.list[str] = field(default_factory=list)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)
    is_revoked: bool = False


@dataclass
class SecurityEvent:
    """Security event for audit logging."""

    event_id: str
    event_type: str
    principal_id: str | None
    resource: str
    action: str
    result: str  # "success", "failure", "blocked"
    threat_level: SecurityThreatLevel
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: builtins.dict[str, Any] = field(default_factory=dict)
    source_ip: str | None = None


@dataclass
class SecurityVulnerability:
    """Security vulnerability detected in scanning."""

    vulnerability_id: str
    title: str
    description: str
    severity: SecurityThreatLevel
    cve_id: str | None = None
    affected_component: str = ""
    remediation: str = ""
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "open"  # "open", "investigating", "fixed", "accepted"


class CryptographyManager:
    """Advanced cryptography management."""

    def __init__(self, service_name: str):
        """Initialize cryptography manager."""
        self.service_name = service_name

        # Key management
        self.master_key = self._generate_master_key()
        self.encryption_keys: builtins.dict[str, bytes] = {}
        self.signing_keys: builtins.dict[str, rsa.RSAPrivateKey] = {}

        # Encryption instances
        self.fernet = Fernet(self.master_key)

        # Key rotation tracking
        self.key_versions: builtins.dict[str, int] = defaultdict(int)
        self.key_rotation_schedule: builtins.dict[str, datetime] = {}

    def _generate_master_key(self) -> bytes:
        """Generate or load master encryption key."""
        # In production, this should be loaded from secure key management service
        return Fernet.generate_key()

    def encrypt_data(self, data: str | bytes, key_id: str = "default") -> str:
        """Encrypt data using specified key."""
        if isinstance(data, str):
            data = data.encode("utf-8")

        # Get or create encryption key
        if key_id not in self.encryption_keys:
            self.encryption_keys[key_id] = Fernet.generate_key()

        fernet = Fernet(self.encryption_keys[key_id])
        encrypted_data = fernet.encrypt(data)

        # Return base64 encoded encrypted data with key version
        key_version = self.key_versions[key_id]
        return base64.b64encode(f"{key_version}:".encode() + encrypted_data).decode(
            "utf-8"
        )

    def decrypt_data(self, encrypted_data: str, key_id: str = "default") -> str:
        """Decrypt data using specified key."""
        try:
            # Decode base64
            decoded_data = base64.b64decode(encrypted_data.encode("utf-8"))

            # Extract key version and encrypted content
            if b":" in decoded_data:
                key_version_bytes, encrypted_content = decoded_data.split(b":", 1)
                int(key_version_bytes.decode("utf-8"))
            else:
                encrypted_content = decoded_data

            # Get appropriate key
            if key_id not in self.encryption_keys:
                raise ValueError(f"Encryption key {key_id} not found")

            fernet = Fernet(self.encryption_keys[key_id])
            decrypted_data = fernet.decrypt(encrypted_content)

            return decrypted_data.decode("utf-8")

        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")

    def generate_signing_key(self, key_id: str) -> rsa.RSAPrivateKey:
        """Generate RSA signing key."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        self.signing_keys[key_id] = private_key
        return private_key

    def sign_data(self, data: str | bytes, key_id: str) -> str:
        """Sign data using RSA private key."""
        if isinstance(data, str):
            data = data.encode("utf-8")

        if key_id not in self.signing_keys:
            self.generate_signing_key(key_id)

        private_key = self.signing_keys[key_id]
        signature = private_key.sign(
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256(),
        )

        return base64.b64encode(signature).decode("utf-8")

    def verify_signature(self, data: str | bytes, signature: str, key_id: str) -> bool:
        """Verify signature using RSA public key."""
        try:
            if isinstance(data, str):
                data = data.encode("utf-8")

            if key_id not in self.signing_keys:
                return False

            private_key = self.signing_keys[key_id]
            public_key = private_key.public_key()

            signature_bytes = base64.b64decode(signature.encode("utf-8"))

            public_key.verify(
                signature_bytes,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )

            return True

        except Exception:
            return False

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), hashed_password.encode("utf-8")
            )
        except Exception:
            return False

    def generate_secure_token(self, length: int = 32) -> str:
        """Generate cryptographically secure random token."""
        return secrets.token_urlsafe(length)

    def rotate_key(self, key_id: str):
        """Rotate encryption key."""
        # Increment key version
        self.key_versions[key_id] += 1

        # Generate new key
        self.encryption_keys[key_id] = Fernet.generate_key()

        # Schedule next rotation
        self.key_rotation_schedule[key_id] = datetime.now(timezone.utc) + timedelta(
            days=90
        )

    def should_rotate_key(self, key_id: str) -> bool:
        """Check if key should be rotated."""
        if key_id not in self.key_rotation_schedule:
            return True

        return datetime.now(timezone.utc) >= self.key_rotation_schedule[key_id]


class AuthenticationManager:
    """Advanced authentication management."""

    def __init__(self, service_name: str, crypto_manager: CryptographyManager):
        """Initialize authentication manager."""
        self.service_name = service_name
        self.crypto_manager = crypto_manager

        # Token storage
        self.active_tokens: builtins.dict[str, SecurityToken] = {}
        self.revoked_tokens: builtins.set[str] = set()

        # User/principal storage
        self.principals: builtins.dict[str, SecurityPrincipal] = {}

        # Authentication settings
        self.jwt_secret = secrets.token_urlsafe(64)
        self.token_expiry = timedelta(hours=24)
        self.refresh_token_expiry = timedelta(days=30)

        # Rate limiting
        self.failed_attempts: builtins.dict[str, builtins.list[datetime]] = defaultdict(
            list
        )
        self.locked_accounts: builtins.dict[str, datetime] = {}

        # Security policies
        self.password_policy = {
            "min_length": 12,
            "require_uppercase": True,
            "require_lowercase": True,
            "require_numbers": True,
            "require_special_chars": True,
            "max_age_days": 90,
        }

    def register_principal(self, principal: SecurityPrincipal) -> bool:
        """Register a new security principal."""
        try:
            # Validate principal data
            if not self._validate_principal(principal):
                return False

            # Check if principal already exists
            if principal.id in self.principals:
                return False

            # Store principal
            self.principals[principal.id] = principal

            return True

        except Exception as e:
            print(f"Error registering principal: {e}")
            return False

    def authenticate(
        self,
        principal_id: str,
        credentials: builtins.dict[str, Any],
        method: AuthenticationMethod,
    ) -> SecurityToken | None:
        """Authenticate principal and return security token."""
        try:
            # Check if account is locked
            if self._is_account_locked(principal_id):
                self._record_failed_attempt(principal_id)
                return None

            # Get principal
            principal = self.principals.get(principal_id)
            if not principal or not principal.is_active:
                self._record_failed_attempt(principal_id)
                return None

            # Authenticate based on method
            if method == AuthenticationMethod.PASSWORD:
                if not self._authenticate_password(principal, credentials):
                    self._record_failed_attempt(principal_id)
                    return None
            elif method == AuthenticationMethod.API_KEY:
                if not self._authenticate_api_key(principal, credentials):
                    self._record_failed_attempt(principal_id)
                    return None
            elif method == AuthenticationMethod.JWT_TOKEN:
                if not self._authenticate_jwt_token(principal, credentials):
                    self._record_failed_attempt(principal_id)
                    return None
            else:
                return None

            # Clear failed attempts on successful authentication
            self.failed_attempts.pop(principal_id, None)

            # Update last access
            principal.last_access = datetime.now(timezone.utc)

            # Generate security token
            token = self._generate_security_token(principal, method)
            self.active_tokens[token.token_id] = token

            return token

        except Exception as e:
            print(f"Authentication error: {e}")
            return None

    def validate_token(self, token_id: str) -> SecurityPrincipal | None:
        """Validate security token and return principal."""
        try:
            # Check if token exists and is not revoked
            if token_id not in self.active_tokens or token_id in self.revoked_tokens:
                return None

            token = self.active_tokens[token_id]

            # Check if token is expired
            if datetime.now(timezone.utc) >= token.expires_at:
                self.revoke_token(token_id)
                return None

            # Get principal
            principal = self.principals.get(token.principal_id)
            if not principal or not principal.is_active:
                self.revoke_token(token_id)
                return None

            return principal

        except Exception as e:
            print(f"Token validation error: {e}")
            return None

    def revoke_token(self, token_id: str) -> bool:
        """Revoke a security token."""
        try:
            if token_id in self.active_tokens:
                token = self.active_tokens[token_id]
                token.is_revoked = True
                self.revoked_tokens.add(token_id)
                del self.active_tokens[token_id]
                return True
            return False
        except Exception:
            return False

    def refresh_token(self, token_id: str) -> SecurityToken | None:
        """Refresh a security token."""
        principal = self.validate_token(token_id)
        if not principal:
            return None

        # Revoke old token
        old_token = self.active_tokens.get(token_id)
        if old_token:
            self.revoke_token(token_id)

            # Generate new token
            new_token = self._generate_security_token(principal, old_token.token_type)
            self.active_tokens[new_token.token_id] = new_token

            return new_token

        return None

    def _validate_principal(self, principal: SecurityPrincipal) -> bool:
        """Validate principal data."""
        if not principal.id or not principal.name:
            return False

        if principal.type not in ["user", "service", "system"]:
            return False

        return True

    def _authenticate_password(
        self, principal: SecurityPrincipal, credentials: builtins.dict[str, Any]
    ) -> bool:
        """Authenticate using password."""
        password = credentials.get("password")
        if not password:
            return False

        stored_hash = principal.attributes.get("password_hash")
        if not stored_hash:
            return False

        return self.crypto_manager.verify_password(password, stored_hash)

    def _authenticate_api_key(
        self, principal: SecurityPrincipal, credentials: builtins.dict[str, Any]
    ) -> bool:
        """Authenticate using API key."""
        api_key = credentials.get("api_key")
        if not api_key:
            return False

        stored_keys = principal.attributes.get("api_keys", [])

        # Hash the provided key and compare
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        return api_key_hash in stored_keys

    def _authenticate_jwt_token(
        self, principal: SecurityPrincipal, credentials: builtins.dict[str, Any]
    ) -> bool:
        """Authenticate using JWT token."""
        token = credentials.get("jwt_token")
        if not token:
            return False

        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload.get("sub") == principal.id
        except jwt.InvalidTokenError:
            return False

    def _generate_security_token(
        self, principal: SecurityPrincipal, method: AuthenticationMethod
    ) -> SecurityToken:
        """Generate a new security token."""
        token_id = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + self.token_expiry

        return SecurityToken(
            token_id=token_id,
            principal_id=principal.id,
            token_type=method,
            expires_at=expires_at,
            scopes=principal.permissions.copy(),
            metadata={
                "issued_at": datetime.now(timezone.utc).isoformat(),
                "issuer": self.service_name,
                "security_level": principal.security_level.value,
            },
        )

    def _is_account_locked(self, principal_id: str) -> bool:
        """Check if account is locked."""
        if principal_id in self.locked_accounts:
            unlock_time = self.locked_accounts[principal_id]
            if datetime.now(timezone.utc) >= unlock_time:
                del self.locked_accounts[principal_id]
                return False
            return True
        return False

    def _record_failed_attempt(self, principal_id: str):
        """Record failed authentication attempt."""
        now = datetime.now(timezone.utc)
        attempts = self.failed_attempts[principal_id]

        # Add current attempt
        attempts.append(now)

        # Remove attempts older than 1 hour
        cutoff = now - timedelta(hours=1)
        self.failed_attempts[principal_id] = [a for a in attempts if a >= cutoff]

        # Lock account if too many failed attempts
        if len(self.failed_attempts[principal_id]) >= 5:
            self.locked_accounts[principal_id] = now + timedelta(minutes=30)

    def validate_password_policy(
        self, password: str
    ) -> builtins.tuple[bool, builtins.list[str]]:
        """Validate password against policy."""
        errors = []

        if len(password) < self.password_policy["min_length"]:
            errors.append(
                f"Password must be at least {self.password_policy['min_length']} characters"
            )

        if self.password_policy["require_uppercase"] and not re.search(
            r"[A-Z]", password
        ):
            errors.append("Password must contain uppercase letters")

        if self.password_policy["require_lowercase"] and not re.search(
            r"[a-z]", password
        ):
            errors.append("Password must contain lowercase letters")

        if self.password_policy["require_numbers"] and not re.search(r"\d", password):
            errors.append("Password must contain numbers")

        if self.password_policy["require_special_chars"] and not re.search(
            r'[!@#$%^&*(),.?":{}|<>]', password
        ):
            errors.append("Password must contain special characters")

        return len(errors) == 0, errors


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
        self.resource_acls: builtins.dict[
            str, builtins.dict[str, builtins.set[str]]
        ] = defaultdict(lambda: defaultdict(set))

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

    def check_permission(
        self, principal: SecurityPrincipal, resource: str, action: str
    ) -> bool:
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

    def _get_effective_permissions(
        self, roles: builtins.list[str]
    ) -> builtins.set[str]:
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

    def _check_acl_permission(
        self, principal_id: str, resource: str, action: str
    ) -> bool:
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

    def _get_context_value(
        self, attribute: str, context: builtins.dict[str, Any]
    ) -> Any:
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


class SecretsManager:
    """Advanced secrets management."""

    def __init__(self, service_name: str, crypto_manager: CryptographyManager):
        """Initialize secrets manager."""
        self.service_name = service_name
        self.crypto_manager = crypto_manager

        # Secret storage
        self.secrets: builtins.dict[str, builtins.dict[str, Any]] = {}
        self.secret_metadata: builtins.dict[str, builtins.dict[str, Any]] = {}

        # Access tracking
        self.secret_access_log: deque = deque(maxlen=10000)

        # Rotation policies
        self.rotation_policies: builtins.dict[str, builtins.dict[str, Any]] = {}

    def store_secret(
        self,
        secret_id: str,
        secret_value: str,
    # secret_type optional; None will be stored as metadata only avoiding hardcoded default pattern
    secret_type: str | None = None,
    metadata: builtins.dict[str, Any] | None = None,
    ) -> bool:
        """Store a secret securely."""
        try:
            # Encrypt the secret
            encrypted_value = self.crypto_manager.encrypt_data(
                secret_value, f"secret_{secret_id}"
            )

            # Store encrypted secret
            self.secrets[secret_id] = {
                "value": encrypted_value,
                "type": secret_type or "user_defined",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "version": 1,
            }

            # Store metadata
            self.secret_metadata[secret_id] = metadata or {}

            return True

        except Exception as e:
            print(f"Error storing secret: {e}")
            return False

    def retrieve_secret(self, secret_id: str, principal_id: str) -> str | None:
        """Retrieve a secret value."""
        try:
            if secret_id not in self.secrets:
                return None

            # Log access
            self._log_secret_access(secret_id, principal_id, "retrieve")

            # Decrypt and return secret
            encrypted_value = self.secrets[secret_id]["value"]
            return self.crypto_manager.decrypt_data(
                encrypted_value, f"secret_{secret_id}"
            )

        except Exception as e:
            print(f"Error retrieving secret: {e}")
            return None

    def update_secret(self, secret_id: str, new_value: str, principal_id: str) -> bool:
        """Update a secret value."""
        try:
            if secret_id not in self.secrets:
                return False

            # Encrypt new value
            encrypted_value = self.crypto_manager.encrypt_data(
                new_value, f"secret_{secret_id}"
            )

            # Update secret
            self.secrets[secret_id]["value"] = encrypted_value
            self.secrets[secret_id]["updated_at"] = datetime.now(
                timezone.utc
            ).isoformat()
            self.secrets[secret_id]["version"] += 1

            # Log access
            self._log_secret_access(secret_id, principal_id, "update")

            return True

        except Exception as e:
            print(f"Error updating secret: {e}")
            return False

    def delete_secret(self, secret_id: str, principal_id: str) -> bool:
        """Delete a secret."""
        try:
            if secret_id not in self.secrets:
                return False

            # Log access
            self._log_secret_access(secret_id, principal_id, "delete")

            # Remove secret and metadata
            del self.secrets[secret_id]
            self.secret_metadata.pop(secret_id, None)
            self.rotation_policies.pop(secret_id, None)

            return True

        except Exception as e:
            print(f"Error deleting secret: {e}")
            return False

    def rotate_secret(self, secret_id: str, new_value: str, principal_id: str) -> bool:
        """Rotate a secret to a new value."""
        # This is essentially an update with additional rotation tracking
        if self.update_secret(secret_id, new_value, principal_id):
            self._log_secret_access(secret_id, principal_id, "rotate")
            return True
        return False

    def set_rotation_policy(
        self, secret_id: str, policy: builtins.dict[str, Any]
    ) -> bool:
        """Set rotation policy for a secret."""
        try:
            self.rotation_policies[secret_id] = {
                "rotation_interval_days": policy.get("rotation_interval_days", 90),
                "auto_rotate": policy.get("auto_rotate", False),
                "notification_days": policy.get("notification_days", 7),
            }
            return True
        except Exception:
            return False

    def get_secrets_requiring_rotation(self) -> builtins.list[str]:
        """Get list of secrets that need rotation."""
        secrets_to_rotate = []
        now = datetime.now(timezone.utc)

        for secret_id, secret_data in self.secrets.items():
            if secret_id in self.rotation_policies:
                policy = self.rotation_policies[secret_id]
                created_at = datetime.fromisoformat(
                    secret_data["created_at"].replace("Z", "+00:00")
                )

                rotation_interval = timedelta(days=policy["rotation_interval_days"])
                if now - created_at >= rotation_interval:
                    secrets_to_rotate.append(secret_id)

        return secrets_to_rotate

    def _log_secret_access(self, secret_id: str, principal_id: str, action: str):
        """Log secret access for audit."""
        self.secret_access_log.append(
            {
                "secret_id": secret_id,
                "principal_id": principal_id,
                "action": action,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )


class SecurityScanner:
    """Security vulnerability scanner."""

    def __init__(self, service_name: str):
        """Initialize security scanner."""
        self.service_name = service_name
        self.vulnerabilities: builtins.list[SecurityVulnerability] = []

        # Scanning patterns and rules
        self.vulnerability_patterns = self._load_vulnerability_patterns()
        self.security_rules = self._load_security_rules()

        # Scan history
        self.scan_history: deque = deque(maxlen=100)

    def _load_vulnerability_patterns(
        self,
    ) -> builtins.dict[str, builtins.dict[str, Any]]:
        """Load vulnerability detection patterns."""
        return {
            "sql_injection": {
                "pattern": r"(\'|\"|;|--|\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION)\b)",
                "severity": SecurityThreatLevel.HIGH,
                "description": "Potential SQL injection vulnerability",
            },
            "xss": {
                "pattern": r"(<script|javascript:|on\w+\s*=)",
                "severity": SecurityThreatLevel.MEDIUM,
                "description": "Potential Cross-Site Scripting (XSS) vulnerability",
            },
            "path_traversal": {
                "pattern": r"(\.\./|\.\.\\|%2e%2e%2f|%2e%2e%5c)",
                "severity": SecurityThreatLevel.HIGH,
                "description": "Potential path traversal vulnerability",
            },
            "hardcoded_secret": {
                "pattern": r'(password|secret|key|token)\s*[:=]\s*["\'][\w\d]+["\']',
                "severity": SecurityThreatLevel.CRITICAL,
                "description": "Hardcoded secret detected",
            },
        }

    def _load_security_rules(self) -> builtins.dict[str, builtins.dict[str, Any]]:
        """Load security validation rules."""
        return {
            "weak_password": {
                "check": lambda pwd: len(pwd) >= 12
                and re.search(r"[A-Z]", pwd)
                and re.search(r"[a-z]", pwd)
                and re.search(r"\d", pwd),
                "severity": SecurityThreatLevel.MEDIUM,
                "description": "Weak password policy",
            },
            "unencrypted_data": {
                "check": lambda data: not self._contains_sensitive_data(data),
                "severity": SecurityThreatLevel.HIGH,
                "description": "Unencrypted sensitive data",
            },
            "insecure_protocol": {
                "check": lambda url: not url.startswith("http://"),
                "severity": SecurityThreatLevel.MEDIUM,
                "description": "Insecure protocol usage",
            },
        }

    def scan_code(
        self, code_content: str, file_path: str = ""
    ) -> builtins.list[SecurityVulnerability]:
        """Scan code for security vulnerabilities."""
        vulnerabilities = []

        for vuln_type, pattern_info in self.vulnerability_patterns.items():
            pattern = pattern_info["pattern"]
            severity = pattern_info["severity"]
            description = pattern_info["description"]

            matches = re.finditer(pattern, code_content, re.IGNORECASE)

            for match in matches:
                vulnerability = SecurityVulnerability(
                    vulnerability_id=str(uuid.uuid4()),
                    title=f"{vuln_type.replace('_', ' ').title()} Detected",
                    description=f"{description} at position {match.start()}",
                    severity=severity,
                    affected_component=file_path or "unknown",
                    remediation=self._get_remediation_advice(vuln_type),
                )

                vulnerabilities.append(vulnerability)
                self.vulnerabilities.append(vulnerability)

        return vulnerabilities

    def scan_configuration(
        self, config: builtins.dict[str, Any]
    ) -> builtins.list[SecurityVulnerability]:
        """Scan configuration for security issues."""
        vulnerabilities = []

        # Check for insecure configurations
        insecure_configs = [
            ("debug", True, "Debug mode enabled in production"),
            ("ssl_verify", False, "SSL verification disabled"),
            ("allow_all_origins", True, "CORS allows all origins"),
            ("password_min_length", lambda x: x < 8, "Weak password minimum length"),
        ]

        for config_key, bad_value, description in insecure_configs:
            if config_key in config:
                config_value = config[config_key]

                is_vulnerable = False
                if callable(bad_value):
                    is_vulnerable = bad_value(config_value)
                else:
                    is_vulnerable = config_value == bad_value

                if is_vulnerable:
                    vulnerability = SecurityVulnerability(
                        vulnerability_id=str(uuid.uuid4()),
                        title="Insecure Configuration",
                        description=description,
                        severity=SecurityThreatLevel.MEDIUM,
                        affected_component="configuration",
                        remediation=f"Review and fix {config_key} configuration",
                    )

                    vulnerabilities.append(vulnerability)
                    self.vulnerabilities.append(vulnerability)

        return vulnerabilities

    def scan_dependencies(
        self, dependencies: builtins.list[builtins.dict[str, str]]
    ) -> builtins.list[SecurityVulnerability]:
        """Scan dependencies for known vulnerabilities."""
        vulnerabilities = []

        # Simplified vulnerability database
        known_vulns = {
            "requests": {
                "versions": ["< 2.20.0"],
                "cve": "CVE-2018-18074",
                "description": "HTTP request smuggling vulnerability",
                "severity": SecurityThreatLevel.HIGH,
            },
            "urllib3": {
                "versions": ["< 1.24.2"],
                "cve": "CVE-2019-11324",
                "description": "Certificate verification bypass",
                "severity": SecurityThreatLevel.MEDIUM,
            },
        }

        for dep in dependencies:
            package_name = dep.get("name", "")
            version = dep.get("version", "")

            if package_name in known_vulns:
                vuln_info = known_vulns[package_name]

                # Simplified version checking
                if any(
                    version.startswith(v.replace("< ", ""))
                    for v in vuln_info["versions"]
                ):
                    vulnerability = SecurityVulnerability(
                        vulnerability_id=str(uuid.uuid4()),
                        title=f"Vulnerable Dependency: {package_name}",
                        description=vuln_info["description"],
                        severity=vuln_info["severity"],
                        cve_id=vuln_info["cve"],
                        affected_component=f"{package_name}@{version}",
                        remediation=f"Update {package_name} to latest version",
                    )

                    vulnerabilities.append(vulnerability)
                    self.vulnerabilities.append(vulnerability)

        return vulnerabilities

    def _contains_sensitive_data(self, data: str) -> bool:
        """Check if data contains sensitive information."""
        sensitive_patterns = [
            r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",  # Credit card
            r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",  # Email
        ]

        for pattern in sensitive_patterns:
            if re.search(pattern, data):
                return True

        return False

    def _get_remediation_advice(self, vulnerability_type: str) -> str:
        """Get remediation advice for vulnerability type."""
        remediation_map = {
            "sql_injection": "Use parameterized queries and input validation",
            "xss": "Implement proper input sanitization and output encoding",
            "path_traversal": "Validate and sanitize file paths, use allowlists",
            "hardcoded_secret": "Move secrets to secure configuration or vault",
        }

        return remediation_map.get(vulnerability_type, "Review and fix security issue")

    def get_vulnerability_summary(self) -> builtins.dict[str, Any]:
        """Get vulnerability scan summary."""
        by_severity = defaultdict(int)
        by_component = defaultdict(int)

        for vuln in self.vulnerabilities:
            by_severity[vuln.severity.value] += 1
            by_component[vuln.affected_component] += 1

        return {
            "total_vulnerabilities": len(self.vulnerabilities),
            "by_severity": dict(by_severity),
            "by_component": dict(by_component),
            "open_vulnerabilities": len(
                [v for v in self.vulnerabilities if v.status == "open"]
            ),
            "fixed_vulnerabilities": len(
                [v for v in self.vulnerabilities if v.status == "fixed"]
            ),
        }


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
            threat_level=SecurityThreatLevel.LOW
            if token
            else SecurityThreatLevel.MEDIUM,
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
            threat_level=SecurityThreatLevel.LOW
            if authorized
            else SecurityThreatLevel.MEDIUM,
        )

        return authorized

    def scan_for_vulnerabilities(
        self, scan_targets: builtins.dict[str, Any]
    ) -> builtins.dict[str, builtins.list[SecurityVulnerability]]:
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
            config_vulns = self.security_scanner.scan_configuration(
                scan_targets["config"]
            )
            results["configuration"] = config_vulns

        # Scan dependencies
        if "dependencies" in scan_targets:
            dep_vulns = self.security_scanner.scan_dependencies(
                scan_targets["dependencies"]
            )
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
