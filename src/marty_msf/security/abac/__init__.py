"""
ABAC (Attribute-Based Access Control) System

Comprehensive attribute-based access control with policy evaluation,
context-aware decisions, and integration with external policy engines.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Union

from ..exceptions import AuthorizationError, PolicyEvaluationError, SecurityError

logger = logging.getLogger(__name__)


class AttributeType(Enum):
    """Types of attributes used in ABAC policies."""
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    LIST = "list"
    OBJECT = "object"


class PolicyEffect(Enum):
    """Policy evaluation effects."""
    ALLOW = "allow"
    DENY = "deny"
    AUDIT = "audit"  # Allow but log for audit


class ConditionOperator(Enum):
    """Operators for attribute conditions."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUAL = "greater_equal"
    LESS_EQUAL = "less_equal"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    REGEX = "regex"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"


@dataclass
class AttributeCondition:
    """Represents a condition on an attribute."""

    attribute_path: str  # e.g., "principal.department", "environment.time_of_day"
    operator: ConditionOperator
    value: Any
    description: str | None = None

    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate condition against context."""
        try:
            actual_value = self._get_attribute_value(context, self.attribute_path)
            return self._apply_operator(actual_value, self.operator, self.value)
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("Condition evaluation failed for %s: %s", self.attribute_path, e)
            return False

    def _get_attribute_value(self, context: dict[str, Any], path: str) -> Any:
        """Get attribute value from context using dot notation."""
        keys = path.split(".")
        value = context

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None

        return value

    def _apply_operator(self, actual: Any, operator: ConditionOperator, expected: Any) -> bool:
        """Apply operator to compare actual and expected values."""
        if operator == ConditionOperator.EXISTS:
            return actual is not None
        elif operator == ConditionOperator.NOT_EXISTS:
            return actual is None

        if actual is None:
            return False

        if operator == ConditionOperator.EQUALS:
            return actual == expected
        elif operator == ConditionOperator.NOT_EQUALS:
            return actual != expected
        elif operator == ConditionOperator.GREATER_THAN:
            return actual > expected
        elif operator == ConditionOperator.LESS_THAN:
            return actual < expected
        elif operator == ConditionOperator.GREATER_EQUAL:
            return actual >= expected
        elif operator == ConditionOperator.LESS_EQUAL:
            return actual <= expected
        elif operator == ConditionOperator.IN:
            return actual in expected if isinstance(expected, list | set | tuple) else False
        elif operator == ConditionOperator.NOT_IN:
            return actual not in expected if isinstance(expected, list | set | tuple) else True
        elif operator == ConditionOperator.CONTAINS:
            return expected in actual if hasattr(actual, "__contains__") else False
        elif operator == ConditionOperator.STARTS_WITH:
            return str(actual).startswith(str(expected))
        elif operator == ConditionOperator.ENDS_WITH:
            return str(actual).endswith(str(expected))
        elif operator == ConditionOperator.REGEX:
            return bool(re.match(str(expected), str(actual)))

        return False


@dataclass
class ABACPolicy:
    """Represents an ABAC policy with conditions and effect."""

    id: str
    name: str
    description: str
    effect: PolicyEffect
    conditions: list[AttributeCondition] = field(default_factory=list)
    resource_pattern: str | None = None  # Pattern for resources this applies to
    action_pattern: str | None = None    # Pattern for actions this applies to
    priority: int = 100  # Lower number = higher priority
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """Validate policy."""
        if not self.id or not self.name:
            raise ValueError("Policy ID and name are required")

    def matches_request(self, resource: str, action: str) -> bool:
        """Check if policy applies to the given resource and action."""
        if self.resource_pattern and not self._matches_pattern(self.resource_pattern, resource):
            return False

        if self.action_pattern and not self._matches_pattern(self.action_pattern, action):
            return False

        return True

    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate all conditions against context."""
        if not self.is_active:
            return False

        # All conditions must be true for policy to apply
        for condition in self.conditions:
            if not condition.evaluate(context):
                return False

        return True

    def _matches_pattern(self, pattern: str, value: str) -> bool:
        """Check if value matches pattern (supports wildcards and regex)."""
        if pattern == "*":
            return True

        # Simple wildcard support
        if "*" in pattern:
            regex_pattern = pattern.replace("*", ".*")
            return bool(re.match(regex_pattern, value))

        # Check if it's a regex pattern (starts with / and ends with /)
        if pattern.startswith("/") and pattern.endswith("/"):
            regex_pattern = pattern[1:-1]
            return bool(re.match(regex_pattern, value))

        return pattern == value

    def to_dict(self) -> dict[str, Any]:
        """Convert policy to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "effect": self.effect.value,
            "conditions": [
                {
                    "attribute_path": c.attribute_path,
                    "operator": c.operator.value,
                    "value": c.value,
                    "description": c.description
                }
                for c in self.conditions
            ],
            "resource_pattern": self.resource_pattern,
            "action_pattern": self.action_pattern,
            "priority": self.priority,
            "is_active": self.is_active,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class ABACContext:
    """Context for ABAC policy evaluation."""

    principal: dict[str, Any]      # Information about the principal (user/service)
    resource: str                  # Resource being accessed
    action: str                    # Action being performed
    environment: dict[str, Any]    # Environmental context (time, location, etc.)

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary for policy evaluation."""
        return {
            "principal": self.principal,
            "resource": self.resource,
            "action": self.action,
            "environment": self.environment
        }


@dataclass
class PolicyEvaluationResult:
    """Result of ABAC policy evaluation."""

    decision: PolicyEffect
    applicable_policies: list[str] = field(default_factory=list)
    evaluation_time_ms: float = 0.0
    context_snapshot: dict[str, Any] | None = None
    error: str | None = None


class ABACManager:
    """Comprehensive ABAC management system."""

    def __init__(self):
        """Initialize ABAC manager."""
        self.policies: dict[str, ABACPolicy] = {}
        self.policy_cache: dict[str, PolicyEvaluationResult] = {}
        self.cache_enabled = True
        self.default_effect = PolicyEffect.DENY

        # Initialize default policies
        self._initialize_default_policies()

    def _initialize_default_policies(self):
        """Create default ABAC policies."""
        # Admin access policy
        admin_policy = ABACPolicy(
            id="admin_access",
            name="Admin Full Access",
            description="Administrators have full access to all resources",
            effect=PolicyEffect.ALLOW,
            priority=10
        )
        admin_policy.conditions.append(
            AttributeCondition(
                attribute_path="principal.roles",
                operator=ConditionOperator.CONTAINS,
                value="admin",
                description="User must have admin role"
            )
        )
        self.add_policy(admin_policy)

        # Business hours policy
        business_hours_policy = ABACPolicy(
            id="business_hours_sensitive",
            name="Sensitive Operations During Business Hours",
            description="Sensitive operations only allowed during business hours",
            effect=PolicyEffect.ALLOW,
            resource_pattern="/api/v1/sensitive/*",
            priority=50
        )
        business_hours_policy.conditions.extend([
            AttributeCondition(
                attribute_path="environment.business_hours",
                operator=ConditionOperator.EQUALS,
                value=True,
                description="Must be during business hours"
            ),
            AttributeCondition(
                attribute_path="principal.department",
                operator=ConditionOperator.IN,
                value=["finance", "admin"],
                description="Must be in authorized department"
            )
        ])
        self.add_policy(business_hours_policy)

        # High-value transaction policy
        high_value_transaction = ABACPolicy(
            id="high_value_transaction",
            name="High Value Transaction Approval",
            description="High value transactions require manager approval",
            effect=PolicyEffect.ALLOW,
            resource_pattern="/api/v1/transactions/*",
            action_pattern="POST",
            priority=30
        )
        high_value_transaction.conditions.extend([
            AttributeCondition(
                attribute_path="environment.transaction_amount",
                operator=ConditionOperator.GREATER_THAN,
                value=10000,
                description="Transaction amount exceeds threshold"
            ),
            AttributeCondition(
                attribute_path="principal.roles",
                operator=ConditionOperator.CONTAINS,
                value="finance_manager",
                description="Must have finance manager role"
            )
        ])
        self.add_policy(high_value_transaction)

        # Default deny policy (lowest priority)
        default_deny = ABACPolicy(
            id="default_deny",
            name="Default Deny",
            description="Default deny all access",
            effect=PolicyEffect.DENY,
            priority=1000
        )
        self.add_policy(default_deny)

        logger.info("Initialized default ABAC policies")

    def add_policy(self, policy: ABACPolicy) -> bool:
        """Add a new ABAC policy."""
        try:
            if policy.id in self.policies:
                raise ValueError(f"Policy '{policy.id}' already exists")

            self.policies[policy.id] = policy
            self._clear_cache()

            logger.info("Added ABAC policy: %s", policy.id)
            return True

        except (ValueError, TypeError) as e:
            logger.error("Failed to add ABAC policy %s: %s", policy.id, e)
            return False

    def remove_policy(self, policy_id: str) -> bool:
        """Remove an ABAC policy."""
        try:
            if policy_id in self.policies:
                del self.policies[policy_id]
                self._clear_cache()
                logger.info("Removed ABAC policy: %s", policy_id)
                return True
            return False

        except (KeyError, ValueError) as e:
            logger.error("Failed to remove ABAC policy %s: %s", policy_id, e)
            return False

    def evaluate_access(self, context: ABACContext) -> PolicyEvaluationResult:
        """Evaluate access request against ABAC policies."""
        start_time = datetime.now()

        try:
            # Check cache
            cache_key = self._get_cache_key(context)
            if self.cache_enabled and cache_key in self.policy_cache:
                return self.policy_cache[cache_key]

            # Get applicable policies sorted by priority
            applicable_policies = self._get_applicable_policies(context.resource, context.action)
            applicable_policies.sort(key=lambda p: p.priority)

            evaluation_context = context.to_dict()
            decision = self.default_effect
            matched_policies = []

            # Evaluate policies in priority order
            for policy in applicable_policies:
                if policy.evaluate(evaluation_context):
                    matched_policies.append(policy.id)
                    decision = policy.effect

                    # First matching policy determines decision
                    break

            # Calculate evaluation time
            evaluation_time = (datetime.now() - start_time).total_seconds() * 1000

            result = PolicyEvaluationResult(
                decision=decision,
                applicable_policies=matched_policies,
                evaluation_time_ms=evaluation_time,
                context_snapshot=evaluation_context
            )

            # Cache result
            if self.cache_enabled:
                self.policy_cache[cache_key] = result

            logger.debug(
                "ABAC evaluation: %s for %s on %s (%sms, %d policies matched)",
                decision.value, context.action, context.resource,
                f"{evaluation_time:.2f}", len(matched_policies)
            )

            return result

        except (ValueError, TypeError, KeyError) as e:
            logger.error("ABAC evaluation failed: %s", e)
            return PolicyEvaluationResult(
                decision=PolicyEffect.DENY,
                error=str(e)
            )

    def check_access(
        self,
        principal: dict[str, Any],
        resource: str,
        action: str,
        environment: dict[str, Any] | None = None
    ) -> bool:
        """Check if access should be allowed."""
        context = ABACContext(
            principal=principal,
            resource=resource,
            action=action,
            environment=environment or {}
        )

        result = self.evaluate_access(context)
        return result.decision in [PolicyEffect.ALLOW, PolicyEffect.AUDIT]

    def require_access(
        self,
        principal: dict[str, Any],
        resource: str,
        action: str,
        environment: dict[str, Any] | None = None
    ):
        """Require access or raise AuthorizationError."""
        if not self.check_access(principal, resource, action, environment):
            raise AuthorizationError(
                f"ABAC policy denied access to {action} on {resource}",
                resource=resource,
                action=action,
                context={
                    "principal": principal,
                    "environment": environment or {}
                }
            )

    def _get_applicable_policies(self, resource: str, action: str) -> list[ABACPolicy]:
        """Get policies that apply to the given resource and action."""
        applicable = []

        for policy in self.policies.values():
            if policy.is_active and policy.matches_request(resource, action):
                applicable.append(policy)

        return applicable

    def _get_cache_key(self, context: ABACContext) -> str:
        """Generate cache key for context."""
        # Create a simple hash of the context
        context_str = json.dumps(context.to_dict(), sort_keys=True)
        return f"abac:{hash(context_str)}"

    def _clear_cache(self):
        """Clear policy evaluation cache."""
        self.policy_cache.clear()

    def load_policies_from_config(self, config_data: dict[str, Any]) -> bool:
        """Load ABAC policies from configuration."""
        try:
            policies_data = config_data.get("policies", [])

            for policy_data in policies_data:
                policy = ABACPolicy(
                    id=policy_data["id"],
                    name=policy_data["name"],
                    description=policy_data["description"],
                    effect=PolicyEffect(policy_data["effect"]),
                    resource_pattern=policy_data.get("resource_pattern"),
                    action_pattern=policy_data.get("action_pattern"),
                    priority=policy_data.get("priority", 100),
                    is_active=policy_data.get("is_active", True),
                    metadata=policy_data.get("metadata", {})
                )

                # Load conditions
                for condition_data in policy_data.get("conditions", []):
                    condition = AttributeCondition(
                        attribute_path=condition_data["attribute_path"],
                        operator=ConditionOperator(condition_data["operator"]),
                        value=condition_data["value"],
                        description=condition_data.get("description")
                    )
                    policy.conditions.append(condition)

                self.add_policy(policy)

            logger.info("Loaded %d ABAC policies from configuration", len(policies_data))
            return True

        except (ValueError, KeyError, TypeError) as e:
            logger.error("Failed to load ABAC policies from config: %s", e)
            return False

    def export_policies_to_config(self) -> dict[str, Any]:
        """Export ABAC policies to configuration format."""
        policies_data = []

        for policy in self.policies.values():
            policies_data.append(policy.to_dict())

        return {"policies": policies_data}

    def get_policy_info(self, policy_id: str) -> dict[str, Any] | None:
        """Get detailed information about a policy."""
        if policy_id not in self.policies:
            return None

        return self.policies[policy_id].to_dict()

    def list_policies(self, active_only: bool = False) -> list[dict[str, Any]]:
        """List all ABAC policies."""
        policies = []
        for policy in self.policies.values():
            if not active_only or policy.is_active:
                policies.append(policy.to_dict())

        return sorted(policies, key=lambda p: p["priority"])

    def test_policy(
        self,
        policy_id: str,
        test_contexts: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Test a policy against multiple contexts."""
        if policy_id not in self.policies:
            raise ValueError(f"Policy '{policy_id}' not found")

        policy = self.policies[policy_id]
        results = []

        for i, context_data in enumerate(test_contexts):
            try:
                context = ABACContext(
                    principal=context_data.get("principal", {}),
                    resource=context_data.get("resource", ""),
                    action=context_data.get("action", ""),
                    environment=context_data.get("environment", {})
                )

                matches = policy.matches_request(context.resource, context.action)
                evaluates = policy.evaluate(context.to_dict()) if matches else False

                results.append({
                    "test_case": i + 1,
                    "context": context_data,
                    "matches_request": matches,
                    "conditions_pass": evaluates,
                    "would_apply": matches and evaluates
                })

            except (ValueError, KeyError, TypeError) as e:
                results.append({
                    "test_case": i + 1,
                    "context": context_data,
                    "error": str(e)
                })

        return results


# Global ABAC manager instance
_abac_manager: ABACManager | None = None


def get_abac_manager() -> ABACManager:
    """Get global ABAC manager instance."""
    global _abac_manager
    if _abac_manager is None:
        _abac_manager = ABACManager()
    return _abac_manager


def reset_abac_manager():
    """Reset global ABAC manager (for testing)."""
    global _abac_manager
    _abac_manager = None


__all__ = [
    "AttributeCondition",
    "ABACPolicy",
    "ABACContext",
    "ABACManager",
    "PolicyEvaluationResult",
    "AttributeType",
    "PolicyEffect",
    "ConditionOperator",
    "get_abac_manager",
    "reset_abac_manager"
]
