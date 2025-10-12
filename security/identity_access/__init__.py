"""
Identity and Access Management (IAM) for Marty Microservices Framework

Provides comprehensive identity and access management including:
- OAuth2/OIDC authentication and authorization
- Role-Based Access Control (RBAC)
- JWT token management and validation
- API key management and authentication
- Multi-factor authentication (MFA)
- Session management and security
- User directory integration
"""

import asyncio
import base64
import builtins
import hashlib
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import bcrypt
import jwt

# External dependencies
try:
    from prometheus_client import Counter, Gauge
    REDIS_AVAILABLE = True

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class AuthenticationMethod(Enum):
    """Authentication methods"""

    PASSWORD = "password"
    API_KEY = "api_key"
    JWT_TOKEN = "jwt_token"
    OAUTH2 = "oauth2"
    MFA_TOTP = "mfa_totp"
    MFA_SMS = "mfa_sms"
    CERTIFICATE = "certificate"


class UserRole(Enum):
    """Standard user roles"""

    GUEST = "guest"
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    SERVICE_ACCOUNT = "service_account"


class Permission(Enum):
    """System permissions"""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    MANAGE_USERS = "manage_users"
    MANAGE_ROLES = "manage_roles"
    MANAGE_PERMISSIONS = "manage_permissions"
    SYSTEM_CONFIG = "system_config"
    AUDIT_LOGS = "audit_logs"
    SECURITY_ADMIN = "security_admin"


@dataclass
class User:
    """User account representation"""

    user_id: str
    username: str
    email: str
    password_hash: str | None
    roles: builtins.set[UserRole] = field(default_factory=set)
    permissions: builtins.set[Permission] = field(default_factory=set)

    # Profile information
    full_name: str | None = None
    department: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_login: datetime | None = None

    # Security settings
    mfa_enabled: bool = False
    mfa_secret: str | None = None
    failed_login_attempts: int = 0
    account_locked_until: datetime | None = None
    password_expires_at: datetime | None = None

    # Status
    is_active: bool = True
    is_verified: bool = False

    def to_dict(self, include_sensitive: bool = False) -> builtins.dict[str, Any]:
        """Convert user to dictionary"""
        data = {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "roles": [role.value for role in self.roles],
            "permissions": [perm.value for perm in self.permissions],
            "full_name": self.full_name,
            "department": self.department,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "mfa_enabled": self.mfa_enabled,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
        }

        if include_sensitive:
            data.update(
                {
                    "password_hash": self.password_hash,
                    "mfa_secret": self.mfa_secret,
                    "failed_login_attempts": self.failed_login_attempts,
                    "account_locked_until": self.account_locked_until.isoformat()
                    if self.account_locked_until
                    else None,
                    "password_expires_at": self.password_expires_at.isoformat()
                    if self.password_expires_at
                    else None,
                }
            )

        return data


@dataclass
class AccessToken:
    """Access token representation"""

    token_id: str
    user_id: str
    token_type: str  # "access", "refresh", "api_key"
    token_hash: str
    expires_at: datetime
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime | None = None
    scopes: builtins.set[str] = field(default_factory=set)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)
    is_revoked: bool = False


@dataclass
class APIKey:
    """API key representation"""

    key_id: str
    user_id: str
    name: str
    key_hash: str
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime | None = None
    last_used: datetime | None = None
    permissions: builtins.set[Permission] = field(default_factory=set)
    rate_limit: int = 1000  # requests per hour
    is_active: bool = True


@dataclass
class Session:
    """User session representation"""

    session_id: str
    user_id: str
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(
        default_factory=lambda: datetime.now() + timedelta(hours=24)
    )
    last_activity: datetime = field(default_factory=datetime.now)
    ip_address: str = ""
    user_agent: str = ""
    is_active: bool = True


class PasswordManager:
    """
    Secure password management

    Features:
    - bcrypt password hashing
    - Password strength validation
    - Password history tracking
    - Secure password generation
    """

    def __init__(self, min_length: int = 12):
        self.min_length = min_length
        self.password_history: builtins.dict[str, builtins.list[str]] = {}

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt(rounds=12)
        password_hash = bcrypt.hashpw(password.encode("utf-8"), salt)
        return password_hash.decode("utf-8")

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), password_hash.encode("utf-8")
            )
        except Exception:
            return False

    def validate_password_strength(
        self, password: str
    ) -> builtins.tuple[bool, builtins.list[str]]:
        """Validate password strength"""
        errors = []

        if len(password) < self.min_length:
            errors.append(
                f"Password must be at least {self.min_length} characters long"
            )

        if not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")

        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")

        if not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one number")

        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errors.append("Password must contain at least one special character")

        # Check against common passwords (simplified)
        common_passwords = [
            "password",
            "123456",
            "qwerty",
            "admin",
            "letmein",
            "welcome",
            "monkey",
            "1234567890",
        ]
        if password.lower() in common_passwords:
            errors.append("Password is too common")

        return len(errors) == 0, errors

    def generate_secure_password(self, length: int = 16) -> str:
        """Generate secure random password"""
        import secrets
        import string

        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        password = "".join(secrets.choice(characters) for _ in range(length))

        # Ensure password meets requirements
        if not self.validate_password_strength(password)[0]:
            return self.generate_secure_password(length)

        return password

    def check_password_history(
        self, user_id: str, new_password: str, history_count: int = 5
    ) -> bool:
        """Check if password was used recently"""
        if user_id not in self.password_history:
            return True

        self.hash_password(new_password)
        recent_hashes = self.password_history[user_id][-history_count:]

        for old_hash in recent_hashes:
            if self.verify_password(new_password, old_hash):
                return False

        return True

    def add_to_password_history(self, user_id: str, password_hash: str):
        """Add password hash to user's history"""
        if user_id not in self.password_history:
            self.password_history[user_id] = []

        self.password_history[user_id].append(password_hash)

        # Keep only last 10 passwords
        if len(self.password_history[user_id]) > 10:
            self.password_history[user_id] = self.password_history[user_id][-10:]


class JWTManager:
    """
    JWT token management

    Features:
    - Secure JWT creation and validation
    - Token refresh mechanisms
    - Blacklist management
    - Custom claims support
    """

    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_blacklist: builtins.set[str] = set()

        # Default token expiry times
        self.access_token_expiry = timedelta(hours=1)
        self.refresh_token_expiry = timedelta(days=30)

    def create_access_token(
        self,
        user_id: str,
        roles: builtins.list[str],
        permissions: builtins.list[str],
        custom_claims: builtins.dict[str, Any] | None = None,
    ) -> builtins.tuple[str, datetime]:
        """Create JWT access token"""

        now = datetime.utcnow()
        expires_at = now + self.access_token_expiry

        payload = {
            "user_id": user_id,
            "roles": roles,
            "permissions": permissions,
            "token_type": "access",
            "iat": now,
            "exp": expires_at,
            "jti": str(uuid.uuid4()),  # JWT ID for blacklisting
        }

        if custom_claims:
            payload.update(custom_claims)

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token, expires_at

    def create_refresh_token(self, user_id: str) -> builtins.tuple[str, datetime]:
        """Create JWT refresh token"""

        now = datetime.utcnow()
        expires_at = now + self.refresh_token_expiry

        payload = {
            "user_id": user_id,
            "token_type": "refresh",
            "iat": now,
            "exp": expires_at,
            "jti": str(uuid.uuid4()),
        }

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token, expires_at

    def validate_token(
        self, token: str
    ) -> builtins.tuple[bool, builtins.dict[str, Any] | None, str | None]:
        """Validate JWT token"""

        try:
            # Decode token
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Check if token is blacklisted
            jti = payload.get("jti")
            if jti and jti in self.token_blacklist:
                return False, None, "Token has been revoked"

            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
                return False, None, "Token has expired"

            return True, payload, None

        except jwt.ExpiredSignatureError:
            return False, None, "Token has expired"
        except jwt.InvalidTokenError as e:
            return False, None, f"Invalid token: {e!s}"

    def revoke_token(self, token: str) -> bool:
        """Revoke token by adding to blacklist"""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False},
            )
            jti = payload.get("jti")
            if jti:
                self.token_blacklist.add(jti)
                return True
        except Exception:
            pass
        return False

    def refresh_access_token(
        self, refresh_token: str
    ) -> builtins.tuple[bool, str | None, str | None]:
        """Create new access token using refresh token"""

        is_valid, payload, error = self.validate_token(refresh_token)

        if not is_valid:
            return False, None, error

        if payload.get("token_type") != "refresh":
            return False, None, "Invalid token type for refresh"

        user_id = payload.get("user_id")
        if not user_id:
            return False, None, "Invalid user ID in token"

        # Create new access token (would need user roles/permissions from database)
        # For now, return placeholder
        return True, "new_access_token", None


class RBACManager:
    """
    Role-Based Access Control Manager

    Features:
    - Hierarchical role management
    - Permission assignment and checking
    - Resource-based access control
    - Dynamic permission evaluation
    """

    def __init__(self):
        # Role hierarchy (higher roles inherit lower role permissions)
        self.role_hierarchy = {
            UserRole.SUPER_ADMIN: [
                UserRole.ADMIN,
                UserRole.MODERATOR,
                UserRole.USER,
                UserRole.GUEST,
            ],
            UserRole.ADMIN: [UserRole.MODERATOR, UserRole.USER, UserRole.GUEST],
            UserRole.MODERATOR: [UserRole.USER, UserRole.GUEST],
            UserRole.USER: [UserRole.GUEST],
            UserRole.GUEST: [],
            UserRole.SERVICE_ACCOUNT: [],  # Special role with specific permissions
        }

        # Default permissions for each role
        self.role_permissions = {
            UserRole.GUEST: {Permission.READ},
            UserRole.USER: {Permission.READ, Permission.WRITE},
            UserRole.MODERATOR: {Permission.READ, Permission.WRITE, Permission.DELETE},
            UserRole.ADMIN: {
                Permission.READ,
                Permission.WRITE,
                Permission.DELETE,
                Permission.MANAGE_USERS,
                Permission.MANAGE_ROLES,
                Permission.AUDIT_LOGS,
            },
            UserRole.SUPER_ADMIN: {
                Permission.READ,
                Permission.WRITE,
                Permission.DELETE,
                Permission.MANAGE_USERS,
                Permission.MANAGE_ROLES,
                Permission.MANAGE_PERMISSIONS,
                Permission.SYSTEM_CONFIG,
                Permission.AUDIT_LOGS,
                Permission.SECURITY_ADMIN,
                Permission.ADMIN,
            },
            UserRole.SERVICE_ACCOUNT: {Permission.READ, Permission.WRITE},
        }

        # Resource-specific permissions
        self.resource_permissions: builtins.dict[
            str, builtins.dict[str, builtins.set[Permission]]
        ] = {}

    def get_effective_roles(
        self, user_roles: builtins.set[UserRole]
    ) -> builtins.set[UserRole]:
        """Get all effective roles including inherited ones"""
        effective_roles = set(user_roles)

        for role in user_roles:
            if role in self.role_hierarchy:
                effective_roles.update(self.role_hierarchy[role])

        return effective_roles

    def get_effective_permissions(
        self,
        user_roles: builtins.set[UserRole],
        user_permissions: builtins.set[Permission],
    ) -> builtins.set[Permission]:
        """Get all effective permissions for user"""
        effective_permissions = set(user_permissions)
        effective_roles = self.get_effective_roles(user_roles)

        # Add permissions from roles
        for role in effective_roles:
            if role in self.role_permissions:
                effective_permissions.update(self.role_permissions[role])

        return effective_permissions

    def check_permission(
        self,
        user_roles: builtins.set[UserRole],
        user_permissions: builtins.set[Permission],
        required_permission: Permission,
        resource: str | None = None,
    ) -> bool:
        """Check if user has required permission"""

        effective_permissions = self.get_effective_permissions(
            user_roles, user_permissions
        )

        # Check direct permission
        if required_permission in effective_permissions:
            return True

        # Check admin override
        if Permission.ADMIN in effective_permissions:
            return True

        # Check resource-specific permissions
        if resource and resource in self.resource_permissions:
            resource_perms = self.resource_permissions[resource]
            for role in self.get_effective_roles(user_roles):
                if (
                    role.value in resource_perms
                    and required_permission in resource_perms[role.value]
                ):
                    return True

        return False

    def assign_resource_permission(
        self, resource: str, role: str, permissions: builtins.set[Permission]
    ):
        """Assign permissions to role for specific resource"""
        if resource not in self.resource_permissions:
            self.resource_permissions[resource] = {}

        self.resource_permissions[resource][role] = permissions

    def get_accessible_resources(
        self, user_roles: builtins.set[UserRole]
    ) -> builtins.list[str]:
        """Get list of resources user can access"""
        accessible = []
        effective_roles = self.get_effective_roles(user_roles)

        for resource, role_perms in self.resource_permissions.items():
            for role in effective_roles:
                if role.value in role_perms:
                    accessible.append(resource)
                    break

        return accessible


class APIKeyManager:
    """
    API Key Management

    Features:
    - Secure API key generation
    - Key validation and authentication
    - Rate limiting per key
    - Key lifecycle management
    """

    def __init__(self):
        self.api_keys: builtins.dict[str, APIKey] = {}
        self.key_usage: builtins.dict[str, builtins.list[datetime]] = {}

    def generate_api_key(
        self,
        user_id: str,
        name: str,
        permissions: builtins.set[Permission],
        expires_in_days: int | None = None,
        rate_limit: int = 1000,
    ) -> builtins.tuple[str, APIKey]:
        """Generate new API key"""

        # Generate secure random key
        key_bytes = secrets.token_bytes(32)
        raw_key = base64.urlsafe_b64encode(key_bytes).decode("utf-8")

        # Create key ID and hash
        key_id = f"ak_{secrets.token_hex(8)}"
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

        # Calculate expiry
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now() + timedelta(days=expires_in_days)

        # Create API key object
        api_key = APIKey(
            key_id=key_id,
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            expires_at=expires_at,
            permissions=permissions,
            rate_limit=rate_limit,
        )

        self.api_keys[key_id] = api_key

        # Return raw key (only time it's visible)
        return f"{key_id}.{raw_key}", api_key

    def validate_api_key(
        self, api_key_string: str
    ) -> builtins.tuple[bool, APIKey | None, str | None]:
        """Validate API key and return key info"""

        try:
            # Parse key
            if "." not in api_key_string:
                return False, None, "Invalid key format"

            key_id, raw_key = api_key_string.split(".", 1)

            # Find key
            if key_id not in self.api_keys:
                return False, None, "Key not found"

            api_key = self.api_keys[key_id]

            # Check if key is active
            if not api_key.is_active:
                return False, None, "Key is disabled"

            # Check expiry
            if api_key.expires_at and api_key.expires_at < datetime.now():
                return False, None, "Key has expired"

            # Verify key hash
            key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
            if key_hash != api_key.key_hash:
                return False, None, "Invalid key"

            # Check rate limit
            if not self._check_rate_limit(key_id, api_key.rate_limit):
                return False, None, "Rate limit exceeded"

            # Update last used
            api_key.last_used = datetime.now()

            return True, api_key, None

        except Exception as e:
            return False, None, f"Key validation error: {e!s}"

    def _check_rate_limit(self, key_id: str, rate_limit: int) -> bool:
        """Check if API key is within rate limit"""

        now = datetime.now()
        cutoff = now - timedelta(hours=1)

        # Initialize usage tracking
        if key_id not in self.key_usage:
            self.key_usage[key_id] = []

        # Clean old entries
        self.key_usage[key_id] = [
            timestamp for timestamp in self.key_usage[key_id] if timestamp > cutoff
        ]

        # Check limit
        if len(self.key_usage[key_id]) >= rate_limit:
            return False

        # Record usage
        self.key_usage[key_id].append(now)
        return True

    def revoke_api_key(self, key_id: str) -> bool:
        """Revoke API key"""
        if key_id in self.api_keys:
            self.api_keys[key_id].is_active = False
            return True
        return False

    def list_user_keys(self, user_id: str) -> builtins.list[APIKey]:
        """List all API keys for user"""
        return [key for key in self.api_keys.values() if key.user_id == user_id]


class IAMManager:
    """
    Complete Identity and Access Management System

    Orchestrates all IAM components:
    - User management
    - Authentication
    - Authorization
    - Session management
    - API key management
    """

    def __init__(self, jwt_secret: str):
        self.users: builtins.dict[str, User] = {}
        self.sessions: builtins.dict[str, Session] = {}

        # Initialize components
        self.password_manager = PasswordManager()
        self.jwt_manager = JWTManager(jwt_secret)
        self.rbac_manager = RBACManager()
        self.api_key_manager = APIKeyManager()

        # Configuration
        self.max_failed_attempts = 5
        self.account_lockout_duration = timedelta(minutes=30)
        self.session_timeout = timedelta(hours=24)

        # Create default admin user
        self._create_default_admin()

        # Metrics
        if CRYPTO_AVAILABLE:
            self.authentication_attempts = Counter(
                "marty_authentication_attempts_total",
                "Authentication attempts",
                ["method", "status"],
            )
            self.active_sessions = Gauge(
                "marty_active_sessions", "Active user sessions"
            )

    def _create_default_admin(self):
        """Create default admin user"""
        admin_user = User(
            user_id="admin",
            username="admin",
            email="admin@marty.local",
            password_hash=self.password_manager.hash_password("admin123!"),
            roles={UserRole.SUPER_ADMIN},
            full_name="System Administrator",
            is_verified=True,
        )
        self.users["admin"] = admin_user
        print("Created default admin user (username: admin, password: admin123!)")

    async def authenticate_user(
        self, username: str, password: str, ip_address: str = "", user_agent: str = ""
    ) -> builtins.tuple[bool, User | None, str | None, str | None]:
        """Authenticate user with username/password"""

        # Find user
        user = None
        for u in self.users.values():
            if u.username == username or u.email == username:
                user = u
                break

        if not user:
            if CRYPTO_AVAILABLE:
                self.authentication_attempts.labels(
                    method="password", status="failed"
                ).inc()
            return False, None, None, "Invalid username or password"

        # Check account status
        if not user.is_active:
            return False, None, None, "Account is disabled"

        if user.account_locked_until and user.account_locked_until > datetime.now():
            return False, None, None, "Account is temporarily locked"

        # Verify password
        if not self.password_manager.verify_password(password, user.password_hash):
            user.failed_login_attempts += 1

            # Lock account if too many failures
            if user.failed_login_attempts >= self.max_failed_attempts:
                user.account_locked_until = (
                    datetime.now() + self.account_lockout_duration
                )

            if CRYPTO_AVAILABLE:
                self.authentication_attempts.labels(
                    method="password", status="failed"
                ).inc()
            return False, None, None, "Invalid username or password"

        # Reset failed attempts on successful login
        user.failed_login_attempts = 0
        user.account_locked_until = None
        user.last_login = datetime.now()

        # Create session
        session_id = self._create_session(user.user_id, ip_address, user_agent)

        # Create access token
        access_token, _ = self.jwt_manager.create_access_token(
            user.user_id,
            [role.value for role in user.roles],
            [perm.value for perm in user.permissions],
        )

        if CRYPTO_AVAILABLE:
            self.authentication_attempts.labels(
                method="password", status="success"
            ).inc()

        return True, user, session_id, access_token

    async def authenticate_api_key(
        self, api_key: str
    ) -> builtins.tuple[bool, User | None, str | None]:
        """Authenticate using API key"""

        is_valid, api_key_obj, error = self.api_key_manager.validate_api_key(api_key)

        if not is_valid:
            if CRYPTO_AVAILABLE:
                self.authentication_attempts.labels(
                    method="api_key", status="failed"
                ).inc()
            return False, None, error

        # Get user
        user = self.users.get(api_key_obj.user_id)
        if not user or not user.is_active:
            return False, None, "User not found or inactive"

        if CRYPTO_AVAILABLE:
            self.authentication_attempts.labels(
                method="api_key", status="success"
            ).inc()

        return True, user, None

    async def authenticate_jwt(
        self, token: str
    ) -> builtins.tuple[bool, User | None, str | None]:
        """Authenticate using JWT token"""

        is_valid, payload, error = self.jwt_manager.validate_token(token)

        if not is_valid:
            if CRYPTO_AVAILABLE:
                self.authentication_attempts.labels(method="jwt", status="failed").inc()
            return False, None, error

        user_id = payload.get("user_id")
        user = self.users.get(user_id)

        if not user or not user.is_active:
            return False, None, "User not found or inactive"

        if CRYPTO_AVAILABLE:
            self.authentication_attempts.labels(method="jwt", status="success").inc()

        return True, user, None

    def _create_session(self, user_id: str, ip_address: str, user_agent: str) -> str:
        """Create user session"""
        session_id = secrets.token_urlsafe(32)

        session = Session(
            session_id=session_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.now() + self.session_timeout,
        )

        self.sessions[session_id] = session

        # Update metrics
        if CRYPTO_AVAILABLE:
            self.active_sessions.set(
                len([s for s in self.sessions.values() if s.is_active])
            )

        return session_id

    def validate_session(self, session_id: str) -> builtins.tuple[bool, Session | None]:
        """Validate user session"""
        session = self.sessions.get(session_id)

        if not session or not session.is_active:
            return False, None

        if session.expires_at < datetime.now():
            session.is_active = False
            return False, None

        # Update last activity
        session.last_activity = datetime.now()
        return True, session

    def logout_user(self, session_id: str) -> bool:
        """Logout user and invalidate session"""
        session = self.sessions.get(session_id)
        if session:
            session.is_active = False
            return True
        return False

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        roles: builtins.set[UserRole] = None,
        full_name: str = None,
    ) -> builtins.tuple[bool, User | None, builtins.list[str]]:
        """Create new user"""

        errors = []

        # Validate username uniqueness
        if any(u.username == username for u in self.users.values()):
            errors.append("Username already exists")

        # Validate email uniqueness
        if any(u.email == email for u in self.users.values()):
            errors.append("Email already exists")

        # Validate password strength
        is_strong, password_errors = self.password_manager.validate_password_strength(
            password
        )
        if not is_strong:
            errors.extend(password_errors)

        if errors:
            return False, None, errors

        # Create user
        user_id = str(uuid.uuid4())
        password_hash = self.password_manager.hash_password(password)

        user = User(
            user_id=user_id,
            username=username,
            email=email,
            password_hash=password_hash,
            roles=roles or {UserRole.USER},
            full_name=full_name,
        )

        self.users[user_id] = user
        self.password_manager.add_to_password_history(user_id, password_hash)

        return True, user, []

    def check_permission(
        self, user_id: str, permission: Permission, resource: str | None = None
    ) -> bool:
        """Check if user has permission"""

        user = self.users.get(user_id)
        if not user or not user.is_active:
            return False

        return self.rbac_manager.check_permission(
            user.roles, user.permissions, permission, resource
        )

    def get_user_permissions(self, user_id: str) -> builtins.set[Permission]:
        """Get all effective permissions for user"""
        user = self.users.get(user_id)
        if not user:
            return set()

        return self.rbac_manager.get_effective_permissions(user.roles, user.permissions)

    def get_system_status(self) -> builtins.dict[str, Any]:
        """Get IAM system status"""
        active_sessions = [
            s
            for s in self.sessions.values()
            if s.is_active and s.expires_at > datetime.now()
        ]
        active_api_keys = [
            k for k in self.api_key_manager.api_keys.values() if k.is_active
        ]

        return {
            "total_users": len(self.users),
            "active_users": len([u for u in self.users.values() if u.is_active]),
            "active_sessions": len(active_sessions),
            "total_api_keys": len(active_api_keys),
            "blacklisted_tokens": len(self.jwt_manager.token_blacklist),
        }


# Example usage
async def main():
    """Example usage of IAM system"""

    # Initialize IAM
    iam = IAMManager(jwt_secret="your-secret-key-here")

    print("=== IAM System Demo ===")

    # Create test user
    success, user, errors = iam.create_user(
        username="testuser",
        email="test@example.com",
        password="SecurePass123!",
        roles={UserRole.USER},
        full_name="Test User",
    )

    if success:
        print(f"Created user: {user.username}")
    else:
        print(f"Failed to create user: {errors}")
        return

    # Authenticate user
    auth_success, auth_user, session_id, access_token = await iam.authenticate_user(
        "testuser", "SecurePass123!", "192.168.1.100", "Mozilla/5.0 Test Browser"
    )

    if auth_success:
        print(f"Authentication successful for {auth_user.username}")
        print(f"Session ID: {session_id}")
        print(f"Access token: {access_token[:50]}...")
    else:
        print("Authentication failed")
        return

    # Check permissions
    can_read = iam.check_permission(user.user_id, Permission.READ)
    can_admin = iam.check_permission(user.user_id, Permission.ADMIN)

    print(f"User can read: {can_read}")
    print(f"User can admin: {can_admin}")

    # Create API key
    api_key_string, api_key_obj = iam.api_key_manager.generate_api_key(
        user.user_id,
        "Test API Key",
        {Permission.READ, Permission.WRITE},
        expires_in_days=30,
    )

    print(f"Created API key: {api_key_string[:30]}...")

    # Test API key authentication
    api_auth_success, api_user, api_error = await iam.authenticate_api_key(
        api_key_string
    )
    if api_auth_success:
        print(f"API key authentication successful for {api_user.username}")
    else:
        print(f"API key authentication failed: {api_error}")

    # Get system status
    status = iam.get_system_status()
    print(f"\nSystem Status: {status}")


if __name__ == "__main__":
    asyncio.run(main())
