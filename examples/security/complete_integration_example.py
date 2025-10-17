"""
Complete integration example showing how to use the enhanced security features
of the Marty Microservices Framework.

⚠️  NOTE: This example needs to be updated to use the Unified Security Framework.
    Many of the imports and APIs used here have been deprecated in favor of the
    new unified approach. Please see basic_security_example.py and
    unified_security_demo.py for updated examples.

This example demonstrates (deprecated):
1. HashiCorp Vault integration for secret management
2. Policy-based authorization with multiple engines
3. API Gateway security middleware
4. gRPC security interceptors
5. Certificate management and mTLS
"""

import asyncio
import json
import logging
from datetime import timedelta
from typing import Any, Dict

import grpc
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPBearer

from marty_msf.security.grpc_interceptors import (
    create_authentication_interceptor,
    create_authorization_interceptor,
    create_secret_injection_interceptor,
    get_principal_from_context,
    get_secrets_from_context,
)

# Import Marty MSF security components
from marty_msf.security.secrets import (
    SecretBackend,
    SecretManager,
    SecretType,
    VaultAuthMethod,
    VaultClient,
    VaultConfig,
)
from marty_msf.security.unified_framework import (
    SecurityContext,
    SecurityPolicyType,
    SecurityPrincipal,
    UnifiedSecurityFramework,
    create_unified_security_framework,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SecurityIntegrationExample:
    """Complete security integration example"""

    def __init__(self):
        self.app = FastAPI(title="Secure Microservice Example")
        self.vault_client = None
        self.secret_manager = None
        self.policy_manager = None

    async def initialize_security(self) -> None:
        """Initialize all security components"""

        # 1. Initialize Vault client
        vault_config = VaultConfig(
            url="http://localhost:8200",
            auth_method=VaultAuthMethod.TOKEN,
            token="hvs.dev-token"  # In production, use proper auth method
        )

        self.vault_client = VaultClient(vault_config)

        try:
            await self.vault_client.authenticate()
            logger.info("Vault authentication successful")
        except Exception as e:
            logger.warning(f"Vault authentication failed: {e}")
            logger.info("Continuing with mock secret backend")

        # 2. Initialize secret manager with multiple backends
        self.secret_manager = SecretManager(
            service_name="example_service",
            vault_client=self.vault_client,
            backends=[
                SecretBackend.VAULT,      # Primary: Vault
                SecretBackend.KUBERNETES, # Fallback: K8s secrets
                SecretBackend.ENVIRONMENT # Last resort: Environment vars
            ]
        )

        # 3. Initialize policy manager with multiple engines
        self.policy_manager = PolicyManager(
            primary_engine=PolicyEngineEnum.BUILTIN,
            fallback_engines=[PolicyEngineEnum.OPA, PolicyEngineEnum.OSO]
        )

        # Load sample policies
        await self._load_sample_policies()

        # 4. Setup API Gateway security middleware
        middleware = await create_enhanced_security_middleware(
            secret_manager=self.secret_manager,
            policy_manager=self.policy_manager,
            vault_config={
                "url": "http://localhost:8200",
                "auth_method": "token",
                "token": "hvs.dev-token"
            },
            require_mtls=False,  # Set to True in production
            audit_enabled=True
        )

        self.app.add_middleware(EnhancedSecurityMiddleware, middleware=middleware)

        logger.info("Security initialization completed")

    async def _load_sample_policies(self) -> None:
        """Load sample RBAC and ABAC policies"""

        # RBAC Policy for user management
        rbac_policy = {
            "id": "user_management_rbac",
            "rules": [
                {
                    "resource": "/api/v1/users/*",
                    "action": "*",
                    "principal": {"roles": ["admin"]},
                    "effect": "allow"
                },
                {
                    "resource": "/api/v1/users/*",
                    "action": "GET",
                    "principal": {"roles": ["user"]},
                    "effect": "allow"
                }
            ]
        }

        await self.policy_manager.load_policy(
            "rbac_users",
            json.dumps(rbac_policy)
        )

        # ABAC Policy for financial operations
        abac_policy = {
            "id": "financial_abac",
            "rules": [
                {
                    "resource": "/api/v1/transactions/*",
                    "action": "POST",
                    "principal": {"roles": ["finance_manager"]},
                    "environment": {
                        "business_hours": True,
                        "transaction_amount": {"operator": ">", "value": 10000}
                    },
                    "effect": "allow"
                }
            ]
        }

        await self.policy_manager.load_policy(
            "abac_financial",
            json.dumps(abac_policy)
        )

        logger.info("Sample policies loaded")

    async def setup_secrets(self) -> None:
        """Setup sample secrets in various backends"""

        # Store API keys
        await self.secret_manager.set_secret(
            "api_keys/external_service",
            "sk-example-key-12345",
            secret_type=SecretType.API_KEY
        )

        # Store database credentials with rotation
        await self.secret_manager.set_secret(
            "database/connection_string",
            "postgresql://user:pass@localhost/db",
            secret_type=SecretType.CONNECTION_STRING,
            rotation_interval=timedelta(days=30)
        )

        # Store JWT signing key
        await self.secret_manager.set_secret(
            "jwt/signing_key",
            "super-secret-jwt-key",
            secret_type=SecretType.ENCRYPTION_KEY
        )

        logger.info("Sample secrets configured")

    def setup_api_routes(self) -> None:
        """Setup API routes with security"""

        security = HTTPBearer()

        @self.app.get("/api/v1/users")
        async def list_users(token: str = Depends(security)):
            """List users - requires authentication and authorization"""
            # Security middleware handles auth/authz automatically
            return {"users": ["alice", "bob", "charlie"]}

        @self.app.post("/api/v1/transactions")
        async def create_transaction(
            transaction_data: Dict[str, Any],
            token: str = Depends(security)
        ):
            """Create transaction - requires high-level authorization"""
            # Get secrets for external API calls
            api_key = await self.secret_manager.get_secret("api_keys/external_service")

            return {
                "transaction_id": "txn_12345",
                "status": "pending",
                "external_api_used": bool(api_key)
            }

        @self.app.get("/api/v1/health")
        async def health_check():
            """Health check endpoint - no authentication required"""
            vault_status = await self.vault_client.health_check() if self.vault_client else False
            policy_status = await self.policy_manager.health_check()

            return {
                "status": "healthy",
                "vault_connected": vault_status,
                "policy_engine_active": policy_status,
                "secrets_backend": self.secret_manager.current_backend.value
            }

    def create_grpc_server(self) -> grpc.aio.Server:
        """Create gRPC server with security interceptors"""

        # Create security interceptors
        auth_interceptor = create_authentication_interceptor(
            secret_manager=self.secret_manager,
            jwt_secret_key="jwt/signing_key",
            require_mtls=False
        )

        authz_interceptor = create_authorization_interceptor(
            policy_manager=self.policy_manager
        )

        secret_interceptor = create_secret_injection_interceptor(
            secret_manager=self.secret_manager,
            secret_keys=["api_keys/external_service", "database/connection_string"]
        )

        # Create server with interceptors
        server = grpc.aio.server(
            interceptors=[auth_interceptor, authz_interceptor, secret_interceptor]
        )

        logger.info("gRPC server created with security interceptors")
        return server

    async def demonstrate_policy_evaluation(self) -> None:
        """Demonstrate policy evaluation with different scenarios"""

        scenarios = [
            {
                "name": "Admin accessing users",
                "request": AuthorizationRequest(
                    principal={"roles": ["admin"], "user_id": "admin_user"},
                    action="GET",
                    resource="/api/v1/users/list",
                    environment={"source_ip": "10.0.1.100"}
                )
            },
            {
                "name": "Regular user accessing users",
                "request": AuthorizationRequest(
                    principal={"roles": ["user"], "user_id": "regular_user"},
                    action="GET",
                    resource="/api/v1/users/list",
                    environment={"source_ip": "192.168.1.50"}
                )
            },
            {
                "name": "Finance manager high-value transaction",
                "request": AuthorizationRequest(
                    principal={"roles": ["finance_manager"], "user_id": "fm_user"},
                    action="POST",
                    resource="/api/v1/transactions/create",
                    environment={
                        "transaction_amount": 15000,
                        "business_hours": True,
                        "source_ip": "10.0.1.200"
                    }
                )
            }
        ]

        logger.info("Demonstrating policy evaluation scenarios:")

        for scenario in scenarios:
            try:
                result = await self.policy_manager.evaluate(
                    scenario["request"],
                    policy_ids=["rbac_users", "abac_financial"]
                )

                logger.info(f"  {scenario['name']}: {'ALLOWED' if result.allowed else 'DENIED'}")
                if result.reason:
                    logger.info(f"    Reason: {result.reason}")

            except Exception as e:
                logger.error(f"  {scenario['name']}: ERROR - {e}")

    async def demonstrate_secret_operations(self) -> None:
        """Demonstrate secret management operations"""

        logger.info("Demonstrating secret management:")

        # Get secret
        api_key = await self.secret_manager.get_secret("api_keys/external_service")
        logger.info(f"  Retrieved API key: {api_key[:10]}...")

        # Check secret metadata
        metadata = self.secret_manager.get_secret_metadata("api_keys/external_service")
        logger.info(f"  Secret metadata: {metadata}")

        # List secrets needing rotation
        secrets_to_rotate = self.secret_manager.get_secrets_needing_rotation()
        logger.info(f"  Secrets needing rotation: {secrets_to_rotate}")

        # Generate certificate (if Vault is available)
        if self.vault_client and await self.vault_client.health_check():
            try:
                cert_data = await self.vault_client.generate_certificate(
                    common_name="example.service.local",
                    alt_names=["example.service", "localhost"],
                    ttl="24h"
                )
                logger.info("  Generated certificate successfully")
            except Exception as e:
                logger.warning(f"  Certificate generation failed: {e}")

async def main():
    """Main example function"""

    # Create and initialize the security example
    example = SecurityIntegrationExample()

    try:
        # Initialize all security components
        await example.initialize_security()

        # Setup secrets
        await example.setup_secrets()

        # Setup API routes
        example.setup_api_routes()

        # Demonstrate policy evaluation
        await example.demonstrate_policy_evaluation()

        # Demonstrate secret operations
        await example.demonstrate_secret_operations()

        # Create gRPC server (for demonstration)
        grpc_server = example.create_grpc_server()

        logger.info("Security integration example completed successfully!")
        logger.info("FastAPI app is ready to serve requests")
        logger.info("gRPC server is configured with security interceptors")

        # In a real application, you would start the servers here:
        # import uvicorn
        # uvicorn.run(example.app, host="0.0.0.0", port=8000)

    except Exception as e:
        logger.error(f"Example failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
