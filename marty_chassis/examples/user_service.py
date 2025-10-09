"""
Example: Complete FastAPI microservice using Marty Chassis

This example demonstrates how to create a fully-featured microservice
using the Marty Chassis with authentication, metrics, and resilience.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from marty_chassis import (
    ChassisConfig,
    CircuitBreaker,
    HealthCheck,
    HTTPClient,
    JWTAuth,
    MetricsCollector,
    RBACMiddleware,
    RetryPolicy,
    create_fastapi_service,
    get_logger,
)

# Configure logging
logger = get_logger(__name__)

# Create configuration
config = ChassisConfig()

# Initialize chassis components
auth = JWTAuth()
rbac = RBACMiddleware()
metrics = MetricsCollector()
health = HealthCheck()
circuit_breaker = CircuitBreaker(failure_threshold=5, timeout_seconds=60)
retry_policy = RetryPolicy(max_attempts=3, base_delay=1.0)


# Data models
class User(BaseModel):
    id: int
    username: str
    email: str
    roles: List[str]
    created_at: datetime


class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Mock database
users_db: Dict[int, User] = {
    1: User(
        id=1,
        username="admin",
        email="admin@example.com",
        roles=["admin", "user"],
        created_at=datetime.now(),
    ),
    2: User(
        id=2,
        username="user",
        email="user@example.com",
        roles=["user"],
        created_at=datetime.now(),
    ),
}

# Mock credentials (in real app, use proper password hashing)
credentials_db = {"admin": "admin123", "user": "user123"}


# Health checks
@health.register("database")
async def check_database():
    """Check database connectivity."""
    # Simulate database check
    await asyncio.sleep(0.1)
    return len(users_db) > 0


@health.register("external_api")
async def check_external_api():
    """Check external API availability."""
    try:
        async with HTTPClient("https://httpbin.org", timeout=5.0) as client:
            response = await client.get("/status/200")
            return response.status_code == 200
    except Exception as e:
        logger.warning("External API check failed", error=str(e))
        return False


# Application lifespan
@asynccontextmanager
async def lifespan(app):
    """Application lifespan manager."""
    logger.info("Starting user service")
    yield
    logger.info("Shutting down user service")


# Create FastAPI app with chassis
app = create_fastapi_service(config, lifespan=lifespan)


# Authentication endpoints
@app.post("/auth/login", response_model=LoginResponse)
async def login(login_request: LoginRequest):
    """User login endpoint."""
    logger.info("Login attempt", username=login_request.username)

    # Validate credentials
    if (
        login_request.username not in credentials_db
        or credentials_db[login_request.username] != login_request.password
    ):
        logger.warning("Invalid login attempt", username=login_request.username)
        metrics.counter("auth_failed_total").inc()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Find user
    user = next(
        (u for u in users_db.values() if u.username == login_request.username), None
    )

    if not user:
        logger.error(
            "User not found after valid credentials", username=login_request.username
        )
        raise HTTPException(status_code=500, detail="Internal server error")

    # Create JWT token
    token_data = {"sub": str(user.id), "username": user.username, "roles": user.roles}
    access_token = auth.create_access_token(token_data)

    logger.info("User logged in successfully", user_id=user.id, username=user.username)
    metrics.counter("auth_success_total").inc()

    return LoginResponse(access_token=access_token)


@app.post("/auth/refresh")
@auth.require_auth
async def refresh_token(current_user: dict = Depends(auth.get_current_user)):
    """Refresh JWT token."""
    logger.info("Token refresh", user_id=current_user["sub"])

    # Create new token with same data
    access_token = auth.create_access_token(current_user)

    return LoginResponse(access_token=access_token)


# User management endpoints
@app.get("/users", response_model=List[User])
@auth.require_auth
@rbac.require_roles(["admin"])
async def get_users(current_user: dict = Depends(auth.get_current_user)):
    """Get all users (admin only)."""
    logger.info("Users list requested", admin_user=current_user["username"])
    metrics.counter("users_list_total").inc()

    return list(users_db.values())


@app.get("/users/{user_id}", response_model=User)
@auth.require_auth
async def get_user(user_id: int, current_user: dict = Depends(auth.get_current_user)):
    """Get user by ID."""
    logger.info(
        "User details requested", user_id=user_id, requester=current_user["username"]
    )

    # Users can view their own profile, admins can view any
    current_user_id = int(current_user["sub"])
    if user_id != current_user_id and not rbac.has_role(current_user, "admin"):
        logger.warning(
            "Unauthorized user access attempt",
            user_id=user_id,
            requester=current_user_id,
        )
        raise HTTPException(status_code=403, detail="Not authorized")

    if user_id not in users_db:
        logger.warning("User not found", user_id=user_id)
        raise HTTPException(status_code=404, detail="User not found")

    metrics.counter("user_details_total").inc()
    return users_db[user_id]


@app.post("/users", response_model=User)
@auth.require_auth
@rbac.require_roles(["admin"])
async def create_user(
    user_create: UserCreate, current_user: dict = Depends(auth.get_current_user)
):
    """Create new user (admin only)."""
    logger.info(
        "User creation requested",
        username=user_create.username,
        admin_user=current_user["username"],
    )

    # Check if username already exists
    if any(u.username == user_create.username for u in users_db.values()):
        logger.warning("Username already exists", username=user_create.username)
        raise HTTPException(status_code=400, detail="Username already exists")

    # Create new user
    new_id = max(users_db.keys()) + 1
    new_user = User(
        id=new_id,
        username=user_create.username,
        email=user_create.email,
        roles=["user"],  # Default role
        created_at=datetime.now(),
    )

    users_db[new_id] = new_user
    credentials_db[user_create.username] = user_create.password

    logger.info(
        "User created successfully", user_id=new_id, username=user_create.username
    )
    metrics.counter("users_created_total").inc()

    return new_user


@app.delete("/users/{user_id}")
@auth.require_auth
@rbac.require_roles(["admin"])
async def delete_user(
    user_id: int, current_user: dict = Depends(auth.get_current_user)
):
    """Delete user (admin only)."""
    logger.info(
        "User deletion requested", user_id=user_id, admin_user=current_user["username"]
    )

    if user_id not in users_db:
        logger.warning("User not found for deletion", user_id=user_id)
        raise HTTPException(status_code=404, detail="User not found")

    # Don't allow deleting yourself
    current_user_id = int(current_user["sub"])
    if user_id == current_user_id:
        logger.warning("Admin attempted to delete self", user_id=user_id)
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    # Remove user
    deleted_user = users_db.pop(user_id)
    credentials_db.pop(deleted_user.username, None)

    logger.info(
        "User deleted successfully", user_id=user_id, username=deleted_user.username
    )
    metrics.counter("users_deleted_total").inc()

    return {"message": "User deleted successfully"}


# External API integration with resilience
@app.get("/external/quote")
@auth.require_auth
@circuit_breaker.protected
@retry_policy.retry
async def get_random_quote(current_user: dict = Depends(auth.get_current_user)):
    """Get random quote from external API."""
    logger.info("Random quote requested", user=current_user["username"])

    async with HTTPClient("https://api.quotegarden.io") as client:
        response = await client.get("/api/v3/quotes/random")
        if response.status_code != 200:
            logger.error("External API error", status_code=response.status_code)
            raise HTTPException(status_code=503, detail="External service unavailable")

        data = await response.json()
        metrics.counter("external_quotes_total").inc()

        return {
            "quote": data.get("data", {}).get("quoteText", "No quote available"),
            "author": data.get("data", {}).get("quoteAuthor", "Unknown"),
        }


# Profile endpoint
@app.get("/profile", response_model=User)
@auth.require_auth
async def get_profile(current_user: dict = Depends(auth.get_current_user)):
    """Get current user's profile."""
    user_id = int(current_user["sub"])
    logger.info("Profile requested", user_id=user_id)

    if user_id not in users_db:
        logger.error("Current user not found in database", user_id=user_id)
        raise HTTPException(status_code=500, detail="User not found")

    metrics.counter("profile_views_total").inc()
    return users_db[user_id]


# Custom metrics endpoint
@app.get("/metrics/summary")
@auth.require_auth
@rbac.require_roles(["admin"])
async def get_metrics_summary(current_user: dict = Depends(auth.get_current_user)):
    """Get service metrics summary (admin only)."""
    logger.info("Metrics summary requested", admin_user=current_user["username"])

    return {
        "total_users": len(users_db),
        "service_health": await health.check_all(),
        "uptime": "System uptime would be calculated here",
        "version": config.service.version,
    }


# Example of background task
@app.post("/users/{user_id}/send-email")
@auth.require_auth
@rbac.require_roles(["admin"])
async def send_user_email(
    user_id: int, message: str, current_user: dict = Depends(auth.get_current_user)
):
    """Send email to user (simulated background task)."""
    logger.info(
        "Email send requested", user_id=user_id, admin_user=current_user["username"]
    )

    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")

    user = users_db[user_id]

    # Simulate async email sending
    async def send_email():
        await asyncio.sleep(1)  # Simulate email service delay
        logger.info("Email sent successfully", user_id=user_id, email=user.email)
        metrics.counter("emails_sent_total").inc()

    # In a real app, this would be a proper background task
    asyncio.create_task(send_email())

    return {"message": f"Email queued for {user.email}"}


if __name__ == "__main__":
    import uvicorn

    logger.info(
        "Starting user service", host=config.service.host, port=config.service.port
    )

    uvicorn.run(
        app,
        host=config.service.host,
        port=config.service.port,
        reload=config.environment.value == "development",
    )
