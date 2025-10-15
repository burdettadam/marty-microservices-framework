"""
Simplified integration example with corrected imports and API usage.
This example shows the basic integration patterns without advanced features.
"""

import asyncio
import json
import logging
from datetime import timedelta
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPBearer

from marty_msf.security.authorization import PolicyEngineEnum, PolicyManager

# Import Marty MSF security components
from marty_msf.security.secrets import (
    SecretManager,
    SecretType,
    VaultClient,
    VaultConfig,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BasicSecurityExample:
    """Basic security integration example"""

    def __init__(self):
        self.app = FastAPI(title="Basic Secure Service")
        self.vault_client = None
        self.secret_manager = None
        self.policy_manager = None

    async def initialize_security(self) -> None:
        """Initialize security components"""

        # 1. Initialize Vault client
        vault_config = VaultConfig(
            url="http://localhost:8200",
            token="hvs.dev-token"
        )

        self.vault_client = VaultClient(vault_config)

        try:
            await self.vault_client.authenticate()
            logger.info("Vault authentication successful")
        except Exception as e:
            logger.warning(f"Vault authentication failed: {e}")

        # 2. Initialize secret manager
        self.secret_manager = SecretManager(
            service_name="basic_example",
            vault_client=self.vault_client
        )

        # 3. Initialize policy manager
        self.policy_manager = PolicyManager(
            primary_engine=PolicyEngineEnum.BUILTIN
        )

        # Load basic policy
        await self._load_basic_policy()

        logger.info("Security initialization completed")

    async def _load_basic_policy(self) -> None:
        """Load a basic RBAC policy"""

        policy = {
            "id": "basic_rbac",
            "rules": [
                {
                    "resource": "/api/v1/users",
                    "action": "GET",
                    "principal": {"roles": ["admin", "user"]},
                    "effect": "allow"
                },
                {
                    "resource": "/api/v1/admin/*",
                    "action": "*",
                    "principal": {"roles": ["admin"]},
                    "effect": "allow"
                }
            ]
        }

        await self.policy_manager.add_policy("basic_rbac", policy)
        logger.info("Basic policy loaded")

    async def setup_secrets(self) -> None:
        """Setup basic secrets"""

        # Store an API key
        await self.secret_manager.store_secret(
            "external_api_key",
            "sk-example-12345"
        )

        # Store database URL
        await self.secret_manager.store_secret(
            "database_url",
            "postgresql://user:pass@localhost/db"
        )

        logger.info("Basic secrets configured")

    def setup_routes(self) -> None:
        """Setup API routes"""

        security = HTTPBearer()

        @self.app.get("/api/v1/users")
        async def list_users():
            """List users"""
            return {"users": ["alice", "bob"]}

        @self.app.get("/api/v1/secrets")
        async def get_secret_info():
            """Get information about stored secrets"""
            try:
                api_key = await self.secret_manager.get_secret("external_api_key")
                return {
                    "has_api_key": bool(api_key),
                    "vault_connected": await self.vault_client.health_check() if self.vault_client else False
                }
            except Exception as e:
                return {"error": str(e)}

        @self.app.get("/health")
        async def health():
            """Health check"""
            return {"status": "healthy"}

async def main():
    """Run the basic example"""

    example = BasicSecurityExample()

    try:
        await example.initialize_security()
        await example.setup_secrets()
        example.setup_routes()

        logger.info("Basic security example ready!")
        logger.info("Use: uvicorn basic_security_example:example.app --reload")

    except Exception as e:
        logger.error(f"Example failed: {e}")

# Global instance for uvicorn
example_instance = BasicSecurityExample()

if __name__ == "__main__":
    asyncio.run(main())
