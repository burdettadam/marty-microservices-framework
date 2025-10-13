"""
Enhanced MMF Store Demo - Security Framework Example

This service demonstrates comprehensive security patterns:
- JWT authentication and authorization
- API key authentication
- Role-based access control (RBAC)
- Rate limiting
- Security middleware
- Input validation and sanitization

This incorporates functionality from security_example.py
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# Mock framework imports (these would be real in production)
try:
    from framework.security import (
        APIKeyConfig,
        JWTConfig,
        SecurityConfig,
        SecurityLevel,
    )
except ImportError:
    # Fallback implementations for demo
    class SecurityLevel:
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"

    class SecurityConfig:
        def __init__(self, level=SecurityLevel.MEDIUM):
            self.level = level

    class APIKeyConfig:
        def __init__(self, keys: list[str]):
            self.keys = keys

    class JWTConfig:
        def __init__(self, secret_key: str, algorithm: str = "HS256"):
            self.secret_key = secret_key
            self.algorithm = algorithm

logger = logging.getLogger(__name__)

# Security models
class User(BaseModel):
    user_id: str
    username: str
    email: str
    roles: list[str]
    permissions: list[str]

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

class SecureStoreService:
    """Enhanced store service with comprehensive security"""

    def __init__(self):
        self.app = FastAPI(title="Secure Store Service", version="1.0.0")
        self.security = HTTPBearer()
        self.jwt_secret = "demo-secret-key-change-in-production"
        self.valid_api_keys = {"demo-api-key-1", "demo-api-key-2"}

        # Mock user database
        self.users = {
            "admin": {
                "user_id": str(uuid.uuid4()),
                "username": "admin",
                "email": "admin@store.com",
                "password": "admin123",  # In production, this would be hashed
                "roles": ["admin", "manager"],
                "permissions": ["read", "write", "delete", "manage_users"]
            },
            "manager": {
                "user_id": str(uuid.uuid4()),
                "username": "manager",
                "email": "manager@store.com",
                "password": "manager123",
                "roles": ["manager"],
                "permissions": ["read", "write", "manage_orders"]
            },
            "user": {
                "user_id": str(uuid.uuid4()),
                "username": "user",
                "email": "user@store.com",
                "password": "user123",
                "roles": ["customer"],
                "permissions": ["read", "place_orders"]
            }
        }

        # Rate limiting storage (in production, use Redis)
        self.rate_limit_storage: dict[str, list[datetime]] = {}

        self._setup_routes()

    def create_jwt_token(self, user_data: dict) -> str:
        """Create JWT token for authenticated user"""
        expiry = datetime.utcnow() + timedelta(hours=24)
        payload = {
            "user_id": user_data["user_id"],
            "username": user_data["username"],
            "roles": user_data["roles"],
            "permissions": user_data["permissions"],
            "exp": expiry
        }
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    def verify_jwt_token(self, token: str) -> dict | None:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

    def verify_api_key(self, api_key: str) -> bool:
        """Verify API key"""
        return api_key in self.valid_api_keys

    def check_rate_limit(self, identifier: str, max_requests: int = 100, window_minutes: int = 60) -> bool:
        """Simple rate limiting implementation"""
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=window_minutes)

        if identifier not in self.rate_limit_storage:
            self.rate_limit_storage[identifier] = []

        # Clean old requests
        self.rate_limit_storage[identifier] = [
            req_time for req_time in self.rate_limit_storage[identifier]
            if req_time > window_start
        ]

        # Check if under limit
        if len(self.rate_limit_storage[identifier]) >= max_requests:
            return False

        # Add current request
        self.rate_limit_storage[identifier].append(now)
        return True

    async def get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())) -> User:
        """Get current authenticated user"""
        token = credentials.credentials
        payload = self.verify_jwt_token(token)

        return User(
            user_id=payload["user_id"],
            username=payload["username"],
            email=f"{payload['username']}@store.com",
            roles=payload["roles"],
            permissions=payload["permissions"]
        )

    def require_role(self, required_role: str):
        """Dependency to require specific role"""
        async def check_role(current_user: User = Depends(self.get_current_user)):
            if required_role not in current_user.roles:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied. Required role: {required_role}"
                )
            return current_user
        return check_role

    def require_permission(self, required_permission: str):
        """Dependency to require specific permission"""
        async def check_permission(current_user: User = Depends(self.get_current_user)):
            if required_permission not in current_user.permissions:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied. Required permission: {required_permission}"
                )
            return current_user
        return check_permission

    def _setup_routes(self):
        """Setup secure API routes"""

        @self.app.middleware("http")
        async def security_middleware(request: Request, call_next):
            """Security middleware for rate limiting and logging"""
            client_ip = request.client.host

            # Rate limiting
            if not self.check_rate_limit(client_ip):
                raise HTTPException(status_code=429, detail="Rate limit exceeded")

            # Security headers
            response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"

            return response

        @self.app.post("/auth/login", response_model=TokenResponse)
        async def login(login_request: LoginRequest):
            """Authenticate user and return JWT token"""
            user_data = self.users.get(login_request.username)

            if not user_data or user_data["password"] != login_request.password:
                raise HTTPException(status_code=401, detail="Invalid credentials")

            token = self.create_jwt_token(user_data)

            return TokenResponse(
                access_token=token,
                token_type="bearer",
                expires_in=86400  # 24 hours
            )

        @self.app.get("/auth/me", response_model=User)
        async def get_current_user_info(current_user: User = Depends(self.get_current_user)):
            """Get current user information"""
            return current_user

        @self.app.get("/orders")
        async def get_orders(current_user: User = Depends(self.require_permission("read"))):
            """Get orders - requires read permission"""
            return {
                "orders": [
                    {"id": "1", "customer": current_user.username, "total": 29.99},
                    {"id": "2", "customer": current_user.username, "total": 15.50}
                ]
            }

        @self.app.post("/orders")
        async def create_order(
            order_data: dict,
            current_user: User = Depends(self.require_permission("place_orders"))
        ):
            """Create order - requires place_orders permission"""
            return {
                "order_id": str(uuid.uuid4()),
                "customer": current_user.username,
                "status": "created",
                "data": order_data
            }

        @self.app.get("/admin/users")
        async def get_users(current_user: User = Depends(self.require_role("admin"))):
            """Get all users - admin only"""
            return {
                "users": [
                    {k: v for k, v in user.items() if k != "password"}
                    for user in self.users.values()
                ]
            }

        @self.app.delete("/admin/orders/{order_id}")
        async def delete_order(
            order_id: str,
            current_user: User = Depends(self.require_permission("delete"))
        ):
            """Delete order - requires delete permission"""
            return {"message": f"Order {order_id} deleted by {current_user.username}"}

        @self.app.get("/health")
        async def health_check():
            """Public health check endpoint"""
            return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

async def demonstrate_security_features():
    """Demonstrate security features in store demo"""
    print("=== Store Demo Security Framework ===\n")

    service = SecureStoreService()

    print("🔒 Security Features Implemented:")
    print("   ✅ JWT Authentication")
    print("   ✅ Role-Based Access Control (RBAC)")
    print("   ✅ Permission-Based Authorization")
    print("   ✅ Rate Limiting")
    print("   ✅ Security Headers")
    print("   ✅ Input Validation")

    print("\n👥 Available Test Users:")
    for username, user_data in service.users.items():
        print(f"   - {username}: roles={user_data['roles']}, permissions={user_data['permissions']}")

    print("\n🛡️ Protected Endpoints:")
    print("   - GET /orders (requires 'read' permission)")
    print("   - POST /orders (requires 'place_orders' permission)")
    print("   - GET /admin/users (requires 'admin' role)")
    print("   - DELETE /admin/orders/{id} (requires 'delete' permission)")

    print("\n🚀 To test security features:")
    print("   1. Start the service: uvicorn enhanced_security_demo:service.app")
    print("   2. Login: POST /auth/login with username/password")
    print("   3. Use returned JWT token in Authorization header")
    print("   4. Test different endpoints with different user roles")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    service = SecureStoreService()
    asyncio.run(demonstrate_security_features())
