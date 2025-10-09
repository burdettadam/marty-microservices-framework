"""
JWT Authentication Plugin Example.

This plugin demonstrates how to implement authentication
functionality using the service plugin interface.
"""

from typing import Any

import jwt

from ..decorators import plugin
from ..interfaces import IServicePlugin, PluginContext, PluginMetadata


@plugin(
    name="jwt-authentication",
    version="1.0.0",
    description="JWT-based authentication service plugin",
    author="Marty Team",
    provides=["authentication", "jwt", "token-validation"],
)
class JWTAuthenticationPlugin(IServicePlugin):
    """
    JWT Authentication plugin that provides token validation services.

    This plugin demonstrates:
    - Service registration and discovery
    - Configuration access
    - Event handling
    - Security services
    """

    def __init__(self):
        super().__init__()
        self.jwt_secret: str | None = None
        self.jwt_algorithm: str = "HS256"
        self.token_expiry: int = 3600  # 1 hour

    async def initialize(self, context: PluginContext) -> None:
        """Initialize the authentication plugin."""
        await super().initialize(context)

        # Get configuration
        self.jwt_secret = context.get_config("jwt_secret")
        self.jwt_algorithm = context.get_config("jwt_algorithm", "HS256")
        self.token_expiry = context.get_config("token_expiry", 3600)

        if not self.jwt_secret:
            raise ValueError("JWT secret is required for authentication plugin")

        # Register authentication service
        if context.service_registry:
            context.service_registry.register_service(
                "authentication",
                {
                    "type": "jwt",
                    "plugin": self.plugin_metadata.name,
                    "methods": ["validate_token", "generate_token"],
                    "tags": ["auth", "security", "jwt"],
                },
            )

        self.logger.info("JWT Authentication plugin initialized")

    async def start(self) -> None:
        """Start the authentication plugin."""
        await super().start()

        # Publish plugin started event
        if self.context and self.context.event_bus:
            await self.context.event_bus.publish(
                "auth.plugin.started",
                {"plugin": self.plugin_metadata.name},
                source=self.plugin_metadata.name,
            )

    async def on_service_register(self, service_info: dict[str, Any]) -> None:
        """Called when a service is being registered."""
        # Automatically add authentication requirement to services
        if service_info.get("require_auth", True):
            service_info["auth_provider"] = self.plugin_metadata.name
            self.logger.debug(
                f"Added auth requirement to service: {service_info.get('name', 'unknown')}"
            )

    async def on_service_unregister(self, service_info: dict[str, Any]) -> None:
        """Called when a service is being unregistered."""
        self.logger.debug(
            f"Service unregistered: {service_info.get('name', 'unknown')}"
        )

    def generate_token(self, user_id: str, claims: dict[str, Any] | None = None) -> str:
        """
        Generate a JWT token for a user.

        Args:
            user_id: User identifier
            claims: Additional claims to include

        Returns:
            JWT token string
        """
        import time

        if not self.jwt_secret:
            raise ValueError("JWT secret not configured")

        payload = {
            "user_id": user_id,
            "iat": int(time.time()),
            "exp": int(time.time()) + self.token_expiry,
        }

        if claims:
            payload.update(claims)

        token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
        self.logger.debug(f"Generated token for user: {user_id}")

        return token

    def validate_token(self, token: str) -> dict[str, Any]:
        """
        Validate a JWT token.

        Args:
            token: JWT token to validate

        Returns:
            Decoded token payload

        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        if not self.jwt_secret:
            raise ValueError("JWT secret not configured")

        try:
            payload = jwt.decode(
                token, self.jwt_secret, algorithms=[self.jwt_algorithm]
            )
            self.logger.debug(
                f"Validated token for user: {payload.get('user_id', 'unknown')}"
            )
            return payload
        except jwt.ExpiredSignatureError:
            self.logger.warning("Token validation failed: expired")
            raise
        except jwt.InvalidTokenError as e:
            self.logger.warning(f"Token validation failed: {e}")
            raise

    async def check_health(self) -> dict[str, Any]:
        """Perform health check."""
        health = await super().health_check()

        # Add authentication-specific health checks
        health["details"] = {
            "jwt_algorithm": self.jwt_algorithm,
            "token_expiry": self.token_expiry,
            "secret_configured": bool(self.jwt_secret),
        }

        return health

    async def handle_authentication_request(
        self, request_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Handle authentication request.

        Args:
            request_data: Authentication request data

        Returns:
            Authentication result
        """
        auth_type = request_data.get("type", "token")

        if auth_type == "token":
            token = request_data.get("token")
            if not token:
                return {"success": False, "error": "Token required"}

            try:
                payload = self.validate_token(token)
                return {
                    "success": True,
                    "user_id": payload.get("user_id"),
                    "claims": payload,
                }
            except jwt.InvalidTokenError as e:
                return {"success": False, "error": str(e)}

        elif auth_type == "credentials":
            # In a real implementation, you would validate credentials
            # against a user store
            username = request_data.get("username")
            password = request_data.get("password")

            if username and password:
                # Mock authentication - in reality, check against user store
                if username == "admin" and password == "secret":
                    token = self.generate_token(username)
                    return {"success": True, "user_id": username, "token": token}

            return {"success": False, "error": "Invalid credentials"}

        return {"success": False, "error": "Unsupported authentication type"}

    @property
    def plugin_metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        return self._plugin_metadata
