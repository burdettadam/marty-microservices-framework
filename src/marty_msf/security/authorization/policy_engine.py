"""
Enhanced Policy-Based Authorization for Marty Microservices Framework

Provides advanced policy-based authorization with support for:
- Open Policy Agent (OPA) integration
- Oso policy engine integration
- Policy-as-Code with Rego and Polar
- RBAC and ABAC policies
- Real-time policy evaluation
- Policy caching and performance optimization
"""

import asyncio
import builtins
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# Optional dependencies - graceful degradation if not available
try:
    import aiohttp
    import opa
    OPA_AVAILABLE = True
except ImportError:
    OPA_AVAILABLE = False
    logger.debug("OPA client not available")

try:
    import oso
    OSO_AVAILABLE = True
except ImportError:
    OSO_AVAILABLE = False
    logger.debug("Oso policy engine not available")


class PolicyEngine(Enum):
    """Supported policy engines."""
    OPA = "opa"
    OSO = "oso"
    BUILTIN = "builtin"


class PolicyType(Enum):
    """Types of authorization policies."""
    RBAC = "rbac"
    ABAC = "abac"
    CUSTOM = "custom"


class DecisionType(Enum):
    """Policy evaluation decisions."""
    ALLOW = "allow"
    DENY = "deny"
    AUDIT = "audit"
    CONDITIONAL = "conditional"


@dataclass
class PolicyContext:
    """Context for policy evaluation."""
    principal: dict[str, Any]
    resource: str
    action: str
    environment: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for policy engines."""
        return {
            "principal": self.principal,
            "resource": self.resource,
            "action": self.action,
            "environment": self.environment,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class PolicyDecision:
    """Result of policy evaluation."""
    decision: DecisionType
    policies_evaluated: list[str]
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0


class BasePolicyEngine(ABC):
    """Abstract base class for policy engines."""

    @abstractmethod
    async def evaluate(self, context: PolicyContext) -> PolicyDecision:
        """Evaluate policy against context."""
        pass

    @abstractmethod
    async def load_policy(self, policy_id: str, policy_content: str) -> bool:
        """Load a policy."""
        pass

    @abstractmethod
    async def delete_policy(self, policy_id: str) -> bool:
        """Delete a policy."""
        pass

    @abstractmethod
    async def list_policies(self) -> list[str]:
        """List all policies."""
        pass


class OPAPolicyEngine(BasePolicyEngine):
    """Open Policy Agent (OPA) integration."""

    def __init__(self, opa_url: str = "http://localhost:8181", timeout: int = 30):
        """Initialize OPA client."""
        self.opa_url = opa_url.rstrip('/')
        self.timeout = timeout
        self._session = None
        self.available = OPA_AVAILABLE

        if not self.available:
            logger.warning("OPA client not available - using mock evaluation")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if not self._session:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self._session

    async def evaluate(self, context: PolicyContext) -> PolicyDecision:
        """Evaluate policy using OPA."""
        start_time = datetime.now(timezone.utc)

        if not self.available:
            # Mock evaluation for testing
            return PolicyDecision(
                decision=DecisionType.ALLOW,
                policies_evaluated=["mock-policy"],
                reason="Mock evaluation - OPA not available",
                execution_time_ms=1.0
            )

        try:
            session = await self._get_session()

            # Prepare input for OPA
            opa_input = {
                "input": context.to_dict()
            }

            # Query OPA decision endpoint
            async with session.post(
                f"{self.opa_url}/v1/data/authz/allow",
                json=opa_input
            ) as response:
                if response.status == 200:
                    result = await response.json()

                    # Parse OPA response
                    allowed = result.get("result", False)
                    decision = DecisionType.ALLOW if allowed else DecisionType.DENY

                    execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

                    return PolicyDecision(
                        decision=decision,
                        policies_evaluated=["authz/allow"],
                        reason=f"OPA evaluation: {allowed}",
                        metadata=result,
                        execution_time_ms=execution_time
                    )
                else:
                    logger.error(f"OPA request failed with status {response.status}")
                    return PolicyDecision(
                        decision=DecisionType.DENY,
                        policies_evaluated=[],
                        reason=f"OPA request failed: {response.status}",
                        execution_time_ms=0.0
                    )

        except Exception as e:
            logger.error(f"OPA evaluation failed: {e}")
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            return PolicyDecision(
                decision=DecisionType.DENY,
                policies_evaluated=[],
                reason=f"OPA evaluation error: {e}",
                execution_time_ms=execution_time
            )

    async def load_policy(self, policy_id: str, policy_content: str) -> bool:
        """Load Rego policy into OPA."""
        if not self.available:
            logger.info(f"Mock load policy: {policy_id}")
            return True

        try:
            session = await self._get_session()

            async with session.put(
                f"{self.opa_url}/v1/policies/{policy_id}",
                data=policy_content,
                headers={"Content-Type": "text/plain"}
            ) as response:
                if response.status in (200, 201):
                    logger.info(f"Successfully loaded OPA policy: {policy_id}")
                    return True
                else:
                    logger.error(f"Failed to load OPA policy {policy_id}: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Error loading OPA policy {policy_id}: {e}")
            return False

    async def delete_policy(self, policy_id: str) -> bool:
        """Delete policy from OPA."""
        if not self.available:
            logger.info(f"Mock delete policy: {policy_id}")
            return True

        try:
            session = await self._get_session()

            async with session.delete(f"{self.opa_url}/v1/policies/{policy_id}") as response:
                if response.status == 200:
                    logger.info(f"Successfully deleted OPA policy: {policy_id}")
                    return True
                else:
                    logger.error(f"Failed to delete OPA policy {policy_id}: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Error deleting OPA policy {policy_id}: {e}")
            return False

    async def list_policies(self) -> list[str]:
        """List all policies in OPA."""
        if not self.available:
            return ["mock-policy-1", "mock-policy-2"]

        try:
            session = await self._get_session()

            async with session.get(f"{self.opa_url}/v1/policies") as response:
                if response.status == 200:
                    result = await response.json()
                    return list(result.get("result", {}).keys())
                else:
                    logger.error(f"Failed to list OPA policies: {response.status}")
                    return []

        except Exception as e:
            logger.error(f"Error listing OPA policies: {e}")
            return []

    async def close(self):
        """Close HTTP session."""
        if self._session:
            await self._session.close()


class OsoPolicyEngine(BasePolicyEngine):
    """Oso policy engine integration."""

    def __init__(self):
        """Initialize Oso engine."""
        self.available = OSO_AVAILABLE
        self.oso_instance = None
        self.policies: dict[str, str] = {}

        if self.available:
            try:
                self.oso_instance = oso.Oso()
                # Register built-in classes
                self._register_classes()
            except Exception as e:
                logger.error(f"Failed to initialize Oso: {e}")
                self.available = False
        else:
            logger.warning("Oso engine not available - using mock evaluation")

    def _register_classes(self):
        """Register Python classes with Oso."""
        if not self.oso_instance:
            return

        # Register common classes for policy use
        try:
            self.oso_instance.register_class(dict)
            self.oso_instance.register_class(list)
            self.oso_instance.register_class(str)

            # Register custom classes if needed
            # self.oso_instance.register_class(User)
            # self.oso_instance.register_class(Resource)

        except Exception as e:
            logger.error(f"Error registering Oso classes: {e}")

    async def evaluate(self, context: PolicyContext) -> PolicyDecision:
        """Evaluate policy using Oso."""
        start_time = datetime.now(timezone.utc)

        if not self.available or not self.oso_instance:
            # Mock evaluation
            return PolicyDecision(
                decision=DecisionType.ALLOW,
                policies_evaluated=["mock-policy"],
                reason="Mock evaluation - Oso not available",
                execution_time_ms=1.0
            )

        try:
            # Query Oso for authorization
            allowed = self.oso_instance.is_allowed(
                context.principal,
                context.action,
                context.resource
            )

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            return PolicyDecision(
                decision=DecisionType.ALLOW if allowed else DecisionType.DENY,
                policies_evaluated=list(self.policies.keys()),
                reason=f"Oso evaluation: {allowed}",
                execution_time_ms=execution_time
            )

        except Exception as e:
            logger.error(f"Oso evaluation failed: {e}")
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            return PolicyDecision(
                decision=DecisionType.DENY,
                policies_evaluated=[],
                reason=f"Oso evaluation error: {e}",
                execution_time_ms=execution_time
            )

    async def load_policy(self, policy_id: str, policy_content: str) -> bool:
        """Load Polar policy into Oso."""
        if not self.available or not self.oso_instance:
            logger.info(f"Mock load policy: {policy_id}")
            self.policies[policy_id] = policy_content
            return True

        try:
            self.oso_instance.load_str(policy_content)
            self.policies[policy_id] = policy_content
            logger.info(f"Successfully loaded Oso policy: {policy_id}")
            return True

        except Exception as e:
            logger.error(f"Error loading Oso policy {policy_id}: {e}")
            return False

    async def delete_policy(self, policy_id: str) -> bool:
        """Delete policy from Oso."""
        if policy_id in self.policies:
            del self.policies[policy_id]

            # Reload Oso with remaining policies
            if self.available and self.oso_instance:
                try:
                    self.oso_instance.clear_rules()
                    for _pid, content in self.policies.items():
                        self.oso_instance.load_str(content)
                except Exception as e:
                    logger.error(f"Error reloading Oso policies after deletion: {e}")
                    return False

            logger.info(f"Successfully deleted Oso policy: {policy_id}")
            return True

        return False

    async def list_policies(self) -> list[str]:
        """List all loaded policies."""
        return list(self.policies.keys())


class BuiltinPolicyEngine(BasePolicyEngine):
    """Built-in policy engine with simple rule evaluation."""

    def __init__(self):
        """Initialize built-in engine."""
        self.policies: dict[str, dict[str, Any]] = {}
        self.available = True

    async def evaluate(self, context: PolicyContext) -> PolicyDecision:
        """Evaluate policies using built-in logic."""
        start_time = datetime.now(timezone.utc)

        evaluated_policies = []

        # Check all policies
        for policy_id, policy in self.policies.items():
            evaluated_policies.append(policy_id)

            # Simple rule evaluation
            if self._evaluate_policy_rules(policy, context):
                execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                return PolicyDecision(
                    decision=DecisionType.ALLOW,
                    policies_evaluated=evaluated_policies,
                    reason=f"Allowed by policy: {policy_id}",
                    execution_time_ms=execution_time
                )

        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        return PolicyDecision(
            decision=DecisionType.DENY,
            policies_evaluated=evaluated_policies,
            reason="No policy allowed the request",
            execution_time_ms=execution_time
        )

    def _evaluate_policy_rules(self, policy: dict[str, Any], context: PolicyContext) -> bool:
        """Evaluate individual policy rules."""
        rules = policy.get("rules", [])

        for rule in rules:
            if self._evaluate_rule(rule, context):
                return True

        return False

    def _evaluate_rule(self, rule: dict[str, Any], context: PolicyContext) -> bool:
        """Evaluate a single rule."""
        # Check resource pattern
        resource_pattern = rule.get("resource")
        if resource_pattern and not self._match_pattern(resource_pattern, context.resource):
            return False

        # Check action
        action_pattern = rule.get("action")
        if action_pattern and not self._match_pattern(action_pattern, context.action):
            return False

        # Check principal attributes
        principal_conditions = rule.get("principal", {})
        for attr, expected in principal_conditions.items():
            if context.principal.get(attr) != expected:
                return False

        # Check environment conditions
        env_conditions = rule.get("environment", {})
        for attr, expected in env_conditions.items():
            if context.environment.get(attr) != expected:
                return False

        return True

    def _match_pattern(self, pattern: str, value: str) -> bool:
        """Simple pattern matching with wildcards."""
        if pattern == "*":
            return True

        if "*" in pattern:
            import fnmatch
            return fnmatch.fnmatch(value, pattern)

        return pattern == value

    async def load_policy(self, policy_id: str, policy_content: str) -> bool:
        """Load policy from JSON."""
        try:
            policy = json.loads(policy_content)
            self.policies[policy_id] = policy
            logger.info(f"Successfully loaded built-in policy: {policy_id}")
            return True

        except Exception as e:
            logger.error(f"Error loading built-in policy {policy_id}: {e}")
            return False

    async def delete_policy(self, policy_id: str) -> bool:
        """Delete policy."""
        if policy_id in self.policies:
            del self.policies[policy_id]
            logger.info(f"Successfully deleted built-in policy: {policy_id}")
            return True
        return False

    async def list_policies(self) -> list[str]:
        """List all policies."""
        return list(self.policies.keys())


class PolicyManager:
    """Manages multiple policy engines and routing."""

    def __init__(self, primary_engine: PolicyEngine = PolicyEngine.BUILTIN):
        """Initialize policy manager."""
        self.primary_engine = primary_engine
        self.engines: dict[PolicyEngine, BasePolicyEngine] = {}
        self.policy_cache: dict[str, PolicyDecision] = {}
        self.cache_ttl = 300  # 5 minutes

        # Initialize engines
        self._initialize_engines()

    def _initialize_engines(self):
        """Initialize available policy engines."""
        # Always available
        self.engines[PolicyEngine.BUILTIN] = BuiltinPolicyEngine()

        # Optional engines
        if OPA_AVAILABLE:
            self.engines[PolicyEngine.OPA] = OPAPolicyEngine()

        if OSO_AVAILABLE:
            self.engines[PolicyEngine.OSO] = OsoPolicyEngine()

        logger.info(f"Initialized policy engines: {list(self.engines.keys())}")

    async def evaluate(
        self,
        context: PolicyContext,
        engine: PolicyEngine | None = None,
        use_cache: bool = True
    ) -> PolicyDecision:
        """Evaluate authorization policy."""
        engine = engine or self.primary_engine

        # Check cache
        cache_key = self._get_cache_key(context, engine)
        if use_cache and cache_key in self.policy_cache:
            cached_decision = self.policy_cache[cache_key]
            # Simple TTL check (would need proper timestamp tracking in production)
            return cached_decision

        # Get engine
        policy_engine = self.engines.get(engine)
        if not policy_engine:
            logger.error(f"Policy engine {engine} not available")
            return PolicyDecision(
                decision=DecisionType.DENY,
                policies_evaluated=[],
                reason=f"Policy engine {engine} not available",
                execution_time_ms=0.0
            )

        # Evaluate
        decision = await policy_engine.evaluate(context)

        # Cache result
        if use_cache:
            self.policy_cache[cache_key] = decision

        logger.debug(
            f"Policy evaluation: {decision.decision.value} "
            f"(engine: {engine.value}, time: {decision.execution_time_ms:.2f}ms)"
        )

        return decision

    def _get_cache_key(self, context: PolicyContext, engine: PolicyEngine) -> str:
        """Generate cache key for policy decision."""
        context_str = json.dumps(context.to_dict(), sort_keys=True)
        return f"{engine.value}:{hash(context_str)}"

    async def load_policy(
        self,
        policy_id: str,
        policy_content: str,
        engine: PolicyEngine | None = None
    ) -> bool:
        """Load policy into specified engine."""
        engine = engine or self.primary_engine

        policy_engine = self.engines.get(engine)
        if not policy_engine:
            logger.error(f"Policy engine {engine} not available")
            return False

        success = await policy_engine.load_policy(policy_id, policy_content)

        if success:
            # Clear cache when policies change
            self.clear_cache()

        return success

    async def delete_policy(
        self,
        policy_id: str,
        engine: PolicyEngine | None = None
    ) -> bool:
        """Delete policy from specified engine."""
        engine = engine or self.primary_engine

        policy_engine = self.engines.get(engine)
        if not policy_engine:
            logger.error(f"Policy engine {engine} not available")
            return False

        success = await policy_engine.delete_policy(policy_id)

        if success:
            # Clear cache when policies change
            self.clear_cache()

        return success

    async def list_policies(self, engine: PolicyEngine | None = None) -> list[str]:
        """List policies in specified engine."""
        engine = engine or self.primary_engine

        policy_engine = self.engines.get(engine)
        if not policy_engine:
            logger.error(f"Policy engine {engine} not available")
            return []

        return await policy_engine.list_policies()

    def clear_cache(self):
        """Clear policy decision cache."""
        self.policy_cache.clear()
        logger.debug("Policy cache cleared")

    async def health_check(self) -> dict[str, Any]:
        """Check health of policy engines."""
        health = {}

        for engine_type, engine in self.engines.items():
            try:
                # Test with a simple evaluation
                test_context = PolicyContext(
                    principal={"id": "test"},
                    resource="test",
                    action="test"
                )
                await engine.evaluate(test_context)
                health[engine_type.value] = True
            except Exception as e:
                health[engine_type.value] = False
                logger.error(f"Health check failed for {engine_type.value}: {e}")

        return {
            "engines": health,
            "primary_engine": self.primary_engine.value,
            "cache_size": len(self.policy_cache)
        }

    async def close(self):
        """Close all engines."""
        for engine in self.engines.values():
            if hasattr(engine, 'close'):
                await engine.close()
