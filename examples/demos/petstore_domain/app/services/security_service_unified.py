"""
Security service for the PetStore Domain plugin.

This service manages the initialization and coordination of all security components
using the unified security framework.
"""
import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import PetstoreDomainConfig

# Import Marty MSF unified security framework
from marty_msf.security.unified_framework import (
    SecurityContext,
    SecurityPolicyType,
    SecurityPrincipal,
    UnifiedSecurityFramework,
    create_unified_security_framework,
)

SECURITY_AVAILABLE = True

logger = logging.getLogger(__name__)

class PetStoreSecurityService:
    """
    Main security service for the PetStore domain using Unified Security Framework.

    Coordinates all security-related functionality through the unified framework:
    - Authentication and authorization
    - Policy management
    - Security metrics and monitoring
    """

    def __init__(self, config: PetstoreDomainConfig):
        self.config = config
        self.security_framework = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize unified security framework"""
        if self._initialized:
            return

        logger.info("Initializing PetStore security service with unified framework...")

        try:
            # Configuration for unified security framework
            security_config = {
                "default_identity_provider": "local",
                "policy_cache_ttl": 300,
                "audit_enabled": True,
                "service_mesh_enabled": False,
                "compliance_scanning_enabled": False
            }

            # Initialize unified security framework
            self.security_framework = await create_unified_security_framework(security_config)

            if not self.security_framework:
                raise Exception("Failed to initialize unified security framework")

            # Load default policies
            await self._load_default_policies()

            self._initialized = True
            logger.info("Security service initialized successfully with unified framework")

        except Exception as e:
            logger.error(f"Failed to initialize security service: {e}")
            raise

    async def _load_default_policies(self) -> None:
        """Load default policies into the unified framework"""
        try:
            # Define PetStore RBAC policies
            petstore_policies = [
                {
                    "id": "petstore_admin_policy",
                    "type": SecurityPolicyType.RBAC.value,
                    "rules": [
                        {
                            "resource": "/api/v1/pets/*",
                            "action": "*",
                            "principal": {"roles": ["admin"]},
                            "effect": "allow"
                        },
                        {
                            "resource": "/api/v1/users/*",
                            "action": "*",
                            "principal": {"roles": ["admin"]},
                            "effect": "allow"
                        }
                    ]
                },
                {
                    "id": "petstore_user_policy",
                    "type": SecurityPolicyType.RBAC.value,
                    "rules": [
                        {
                            "resource": "/api/v1/pets",
                            "action": "GET",
                            "principal": {"roles": ["user", "admin"]},
                            "effect": "allow"
                        },
                        {
                            "resource": "/api/v1/pets/{id}",
                            "action": "GET",
                            "principal": {"roles": ["user", "admin"]},
                            "effect": "allow"
                        }
                    ]
                }
            ]

            # Load policies into policy engines
            for policy_engine in self.security_framework.policy_engines.values():
                if hasattr(policy_engine, 'load_policies'):
                    await policy_engine.load_policies(petstore_policies)
                    logger.info("PetStore policies loaded successfully")
                    break
            else:
                logger.warning("No compatible policy engine found for loading policies")

        except Exception as e:
            logger.error(f"Failed to load default policies: {e}")

    async def authorize_request(self, principal_data: dict[str, Any], resource: str, action: str) -> dict[str, Any]:
        """Authorize a request using the unified security framework"""
        if not self._initialized or not self.security_framework:
            return {"allowed": False, "reason": "Security framework not initialized"}

        try:
            # Create security principal
            principal = SecurityPrincipal(
                id=principal_data.get("id", "anonymous"),
                type=principal_data.get("type", "user"),
                roles=set(principal_data.get("roles", [])),
                attributes=principal_data.get("attributes", {})
            )

            # Perform authorization check
            decision = await self.security_framework.authorize(principal, resource, action)

            return {
                "allowed": decision.allowed,
                "reason": decision.reason,
                "evaluation_time_ms": decision.evaluation_time_ms,
                "policies_evaluated": decision.policies_evaluated
            }

        except Exception as e:
            logger.error(f"Authorization error: {e}")
            return {"allowed": False, "reason": f"Authorization error: {e}"}

    async def get_secret(self, key: str) -> str | None:
        """Get secret - placeholder for unified framework secret management"""
        logger.warning("Secret management to be implemented with unified framework")
        # TODO: Implement secret management through unified framework
        return None

    async def health_check(self) -> dict[str, Any]:
        """Check health of security components"""
        if not self._initialized:
            return {
                "initialized": False,
                "vault": {"healthy": False},
                "policy_engine": {"healthy": False},
                "secret_manager": {"healthy": False}
            }

        try:
            return {
                "initialized": True,
                "security_framework": {
                    "healthy": self.security_framework is not None,
                    "identity_providers": len(self.security_framework.identity_providers) if self.security_framework else 0,
                    "policy_engines": len(self.security_framework.policy_engines) if self.security_framework else 0,
                    "active_sessions": len(self.security_framework.active_sessions) if self.security_framework else 0,
                    "metrics": self.security_framework.metrics if self.security_framework else {}
                }
            }

        except Exception as e:
            logger.error(f"Health check error: {e}")
            return {
                "initialized": True,
                "security_framework": {"healthy": False, "error": str(e)}
            }

    async def shutdown(self) -> None:
        """Shutdown security service"""
        logger.info("Shutting down PetStore security service")
        # TODO: Add cleanup logic for unified framework if needed
        self._initialized = False
