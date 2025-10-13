"""
Message Routing and Exchange Management

Provides advanced message routing capabilities including content-based routing,
header-based routing, topic patterns, and routing rules with dynamic updates.
"""

import builtins
import fnmatch
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from re import Pattern
from typing import Any

from .core import Message

logger = logging.getLogger(__name__)


class RoutingType(Enum):
    """Message routing types."""

    DIRECT = "direct"
    TOPIC = "topic"
    FANOUT = "fanout"
    HEADERS = "headers"
    CONTENT = "content"
    CUSTOM = "custom"


class MatchType(Enum):
    """Pattern matching types."""

    EXACT = "exact"
    WILDCARD = "wildcard"
    REGEX = "regex"
    GLOB = "glob"


@dataclass
class RoutingRule:
    """Message routing rule definition."""

    # Rule identification
    name: str
    priority: int = 0  # Higher priority rules are evaluated first
    enabled: bool = True

    # Routing configuration
    routing_type: RoutingType = RoutingType.DIRECT
    pattern: str = ""
    match_type: MatchType = MatchType.EXACT

    # Target configuration
    target_queues: builtins.list[str] = field(default_factory=list)
    target_exchanges: builtins.list[str] = field(default_factory=list)

    # Conditions
    header_conditions: builtins.dict[str, Any] = field(default_factory=dict)
    content_conditions: builtins.dict[str, Any] = field(default_factory=dict)

    # Custom routing function
    custom_router: Callable[[Message], builtins.list[str]] | None = None

    # Filters
    message_filter: Callable[[Message], bool] | None = None

    # Metadata
    description: str = ""
    created_at: float = field(default_factory=time.time)
    tags: builtins.set[str] = field(default_factory=set)

    # Statistics
    match_count: int = 0
    last_match_time: float | None = None


@dataclass
class RoutingConfig:
    """Configuration for message routing."""

    # Default routing
    default_queue: str | None = None
    default_exchange: str | None = None

    # Routing behavior
    allow_multiple_targets: bool = True
    stop_on_first_match: bool = False
    require_explicit_routing: bool = False

    # Performance
    enable_caching: bool = True
    cache_ttl: float = 300.0  # 5 minutes
    max_cache_size: int = 10000

    # Monitoring
    enable_metrics: bool = True
    log_routing_decisions: bool = False

    # Fallback behavior
    on_no_match: str = "default"  # "default", "drop", "error"
    on_routing_error: str = "default"  # "default", "drop", "error"


class RoutingEngine:
    """Message routing engine with rule-based routing."""

    def __init__(self, config: RoutingConfig):
        self.config = config
        self._rules: builtins.list[RoutingRule] = []
        self._routing_cache: builtins.dict[str, builtins.list[str]] = {}
        self._cache_timestamps: builtins.dict[str, float] = {}

        # Compiled patterns for performance
        self._compiled_patterns: builtins.dict[str, Pattern] = {}

        # Statistics
        self._total_routed = 0
        self._cache_hits = 0
        self._cache_misses = 0

    def add_rule(self, rule: RoutingRule):
        """Add a routing rule."""
        self._rules.append(rule)
        self._sort_rules()
        self._clear_cache()
        logger.info("Added routing rule: %s", rule.name)

    def remove_rule(self, rule_name: str) -> bool:
        """Remove a routing rule by name."""
        for i, rule in enumerate(self._rules):
            if rule.name == rule_name:
                self._rules.pop(i)
                self._clear_cache()
                logger.info("Removed routing rule: %s", rule_name)
                return True
        return False

    def update_rule(self, rule_name: str, updates: builtins.dict[str, Any]) -> bool:
        """Update a routing rule."""
        for rule in self._rules:
            if rule.name == rule_name:
                for key, value in updates.items():
                    if hasattr(rule, key):
                        setattr(rule, key, value)

                self._sort_rules()
                self._clear_cache()
                logger.info("Updated routing rule: %s", rule_name)
                return True
        return False

    def get_rule(self, rule_name: str) -> RoutingRule | None:
        """Get a routing rule by name."""
        for rule in self._rules:
            if rule.name == rule_name:
                return rule
        return None

    def list_rules(self, enabled_only: bool = False) -> builtins.list[RoutingRule]:
        """List all routing rules."""
        if enabled_only:
            return [rule for rule in self._rules if rule.enabled]
        return self._rules.copy()

    def _sort_rules(self):
        """Sort rules by priority (highest first)."""
        self._rules.sort(key=lambda r: (-r.priority, r.name))

    def _clear_cache(self):
        """Clear routing cache."""
        self._routing_cache.clear()
        self._cache_timestamps.clear()

    def _get_cache_key(self, message: Message) -> str:
        """Generate cache key for message."""
        # Create a key based on routing-relevant message properties
        key_parts = [
            message.headers.routing_key,
            message.headers.exchange or "",
            str(sorted(message.headers.custom.items())),
        ]
        return "|".join(key_parts)

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid."""
        if not self.config.enable_caching:
            return False

        if cache_key not in self._cache_timestamps:
            return False

        age = time.time() - self._cache_timestamps[cache_key]
        return age < self.config.cache_ttl

    def route_message(self, message: Message) -> builtins.list[str]:
        """
        Route a message to appropriate targets.

        Args:
            message: Message to route

        Returns:
            List of target queue/exchange names
        """
        try:
            # Check cache first
            cache_key = self._get_cache_key(message)

            if self._is_cache_valid(cache_key):
                self._cache_hits += 1
                targets = self._routing_cache[cache_key]
                if self.config.log_routing_decisions:
                    logger.debug("Cache hit for message routing: %s -> %s", message.id, targets)
                return targets

            self._cache_misses += 1

            # Route message through rules
            targets = self._route_through_rules(message)

            # Cache result
            if self.config.enable_caching and len(self._routing_cache) < self.config.max_cache_size:
                self._routing_cache[cache_key] = targets
                self._cache_timestamps[cache_key] = time.time()

            # Update statistics
            self._total_routed += 1

            if self.config.log_routing_decisions:
                logger.info("Routed message %s to targets: %s", message.id, targets)

            return targets

        except Exception as e:
            logger.error("Error routing message %s: %s", message.id, e)
            return self._handle_routing_error(message)

    def _route_through_rules(self, message: Message) -> builtins.list[str]:
        """Route message through enabled rules."""
        targets = []
        matched_rules = []

        for rule in self._rules:
            if not rule.enabled:
                continue

            if self._rule_matches_message(rule, message):
                matched_rules.append(rule)
                rule_targets = self._get_rule_targets(rule, message)

                # Update rule statistics
                rule.match_count += 1
                rule.last_match_time = time.time()

                if self.config.allow_multiple_targets:
                    targets.extend(rule_targets)
                else:
                    targets = rule_targets

                if self.config.stop_on_first_match:
                    break

        # Remove duplicates while preserving order
        unique_targets = []
        seen = set()
        for target in targets:
            if target not in seen:
                unique_targets.append(target)
                seen.add(target)

        # Handle no matches
        if not unique_targets:
            return self._handle_no_match(message)

        return unique_targets

    def _rule_matches_message(self, rule: RoutingRule, message: Message) -> bool:
        """Check if a rule matches a message."""
        try:
            # Apply message filter first
            if rule.message_filter and not rule.message_filter(message):
                return False

            # Route by type
            if rule.routing_type == RoutingType.DIRECT:
                return self._match_direct(rule, message)

            if rule.routing_type == RoutingType.TOPIC:
                return self._match_topic(rule, message)

            if rule.routing_type == RoutingType.FANOUT:
                return True  # Fanout matches all messages

            if rule.routing_type == RoutingType.HEADERS:
                return self._match_headers(rule, message)

            if rule.routing_type == RoutingType.CONTENT:
                return self._match_content(rule, message)

            if rule.routing_type == RoutingType.CUSTOM:
                return self._match_custom(rule, message)

            return False

        except Exception as e:
            logger.error("Error evaluating rule %s for message %s: %s", rule.name, message.id, e)
            return False

    def _match_direct(self, rule: RoutingRule, message: Message) -> bool:
        """Match direct routing rule."""
        routing_key = message.headers.routing_key

        if rule.match_type == MatchType.EXACT:
            return routing_key == rule.pattern

        if rule.match_type == MatchType.WILDCARD or rule.match_type == MatchType.GLOB:
            return fnmatch.fnmatch(routing_key, rule.pattern)

        if rule.match_type == MatchType.REGEX:
            pattern = self._get_compiled_pattern(rule.name, rule.pattern)
            return bool(pattern.match(routing_key))

        return False

    def _match_topic(self, rule: RoutingRule, message: Message) -> bool:
        """Match topic routing rule."""
        routing_key = message.headers.routing_key
        pattern = rule.pattern

        # Convert topic pattern to regex
        # * matches exactly one word
        # # matches zero or more words
        regex_pattern = pattern.replace(".", r"\.")
        regex_pattern = regex_pattern.replace("*", r"[^.]+")
        regex_pattern = regex_pattern.replace("#", r".*")
        regex_pattern = f"^{regex_pattern}$"

        compiled_pattern = self._get_compiled_pattern(f"{rule.name}_topic", regex_pattern)
        return bool(compiled_pattern.match(routing_key))

    def _match_headers(self, rule: RoutingRule, message: Message) -> bool:
        """Match headers routing rule."""
        for header_name, expected_value in rule.header_conditions.items():
            # Check custom headers
            if header_name in message.headers.custom:
                actual_value = message.headers.custom[header_name]
            else:
                # Check standard headers
                actual_value = getattr(message.headers, header_name, None)

            if not self._values_match(actual_value, expected_value):
                return False

        return True

    def _match_content(self, rule: RoutingRule, message: Message) -> bool:
        """Match content-based routing rule."""
        # This is a simplified implementation
        # In practice, you might want more sophisticated content inspection
        content = str(message.body)

        for key, expected_value in rule.content_conditions.items():
            if key == "contains":
                if expected_value not in content:
                    return False
            elif key == "starts_with":
                if not content.startswith(expected_value):
                    return False
            elif key == "ends_with":
                if not content.endswith(expected_value):
                    return False
            elif key == "regex":
                pattern = self._get_compiled_pattern(f"{rule.name}_content", expected_value)
                if not pattern.search(content):
                    return False

        return True

    def _match_custom(self, rule: RoutingRule, message: Message) -> bool:
        """Match custom routing rule."""
        if rule.custom_router:
            # Custom router returns targets, but we just need to know if it matches
            targets = rule.custom_router(message)
            return bool(targets)
        return False

    def _values_match(self, actual: Any, expected: Any) -> bool:
        """Check if two values match with type coercion."""
        if actual is None:
            return expected is None

        # Handle different types
        if isinstance(expected, str) and not isinstance(actual, str):
            actual = str(actual)
        elif isinstance(expected, int | float) and isinstance(actual, str):
            try:
                actual = type(expected)(actual)
            except (ValueError, TypeError):
                return False

        return actual == expected

    def _get_compiled_pattern(self, cache_key: str, pattern: str) -> Pattern:
        """Get compiled regex pattern with caching."""
        if cache_key not in self._compiled_patterns:
            self._compiled_patterns[cache_key] = re.compile(pattern)
        return self._compiled_patterns[cache_key]

    def _get_rule_targets(self, rule: RoutingRule, message: Message) -> builtins.list[str]:
        """Get targets for a matched rule."""
        if rule.routing_type == RoutingType.CUSTOM and rule.custom_router:
            return rule.custom_router(message)

        # Combine queue and exchange targets
        targets = []
        targets.extend(rule.target_queues)
        targets.extend(rule.target_exchanges)

        return targets

    def _handle_no_match(self, message: Message) -> builtins.list[str]:
        """Handle case where no rules match."""
        if self.config.on_no_match == "default":
            targets = []
            if self.config.default_queue:
                targets.append(self.config.default_queue)
            if self.config.default_exchange:
                targets.append(self.config.default_exchange)
            return targets

        if self.config.on_no_match == "drop":
            logger.warning("Dropping message %s - no routing rules matched", message.id)
            return []

        if self.config.on_no_match == "error":
            raise RuntimeError(f"No routing rules matched for message {message.id}")

        return []

    def _handle_routing_error(self, message: Message) -> builtins.list[str]:
        """Handle routing error."""
        if self.config.on_routing_error == "default":
            return self._handle_no_match(message)

        if self.config.on_routing_error == "drop":
            logger.warning("Dropping message %s due to routing error", message.id)
            return []

        if self.config.on_routing_error == "error":
            raise

        return []

    def get_stats(self) -> builtins.dict[str, Any]:
        """Get routing engine statistics."""
        cache_hit_rate = 0.0
        if self._cache_hits + self._cache_misses > 0:
            cache_hit_rate = self._cache_hits / (self._cache_hits + self._cache_misses)

        rule_stats = []
        for rule in self._rules:
            rule_stats.append(
                {
                    "name": rule.name,
                    "enabled": rule.enabled,
                    "priority": rule.priority,
                    "match_count": rule.match_count,
                    "last_match_time": rule.last_match_time,
                }
            )

        return {
            "total_routed": self._total_routed,
            "cache_stats": {
                "hits": self._cache_hits,
                "misses": self._cache_misses,
                "hit_rate": cache_hit_rate,
                "size": len(self._routing_cache),
            },
            "rules": {
                "total": len(self._rules),
                "enabled": len([r for r in self._rules if r.enabled]),
                "disabled": len([r for r in self._rules if not r.enabled]),
            },
            "rule_stats": rule_stats,
        }

    def clear_stats(self):
        """Clear routing statistics."""
        self._total_routed = 0
        self._cache_hits = 0
        self._cache_misses = 0

        for rule in self._rules:
            rule.match_count = 0
            rule.last_match_time = None


class MessageRouter:
    """High-level message router with multiple routing engines."""

    def __init__(self):
        self._engines: builtins.dict[str, RoutingEngine] = {}
        self._default_engine: str | None = None

    def add_engine(self, name: str, engine: RoutingEngine, is_default: bool = False):
        """Add a routing engine."""
        self._engines[name] = engine

        if is_default or not self._default_engine:
            self._default_engine = name

    def remove_engine(self, name: str):
        """Remove a routing engine."""
        if name in self._engines:
            del self._engines[name]

            if self._default_engine == name:
                self._default_engine = next(iter(self._engines), None)

    def route(self, message: Message, engine_name: str | None = None) -> builtins.list[str]:
        """Route a message using specified or default engine."""
        engine_name = engine_name or self._default_engine

        if not engine_name or engine_name not in self._engines:
            raise ValueError(f"Unknown routing engine: {engine_name}")

        engine = self._engines[engine_name]
        return engine.route_message(message)

    def get_engine(self, name: str) -> RoutingEngine | None:
        """Get a routing engine by name."""
        return self._engines.get(name)

    def list_engines(self) -> builtins.list[str]:
        """List all routing engine names."""
        return list(self._engines.keys())

    def get_all_stats(self) -> builtins.dict[str, Any]:
        """Get statistics for all routing engines."""
        return {name: engine.get_stats() for name, engine in self._engines.items()}


# Predefined routing rule builders
class RoutingRuleBuilder:
    """Builder for creating common routing rules."""

    @staticmethod
    def direct_route(
        name: str, routing_key: str, target_queue: str, priority: int = 0
    ) -> RoutingRule:
        """Create a direct routing rule."""
        return RoutingRule(
            name=name,
            priority=priority,
            routing_type=RoutingType.DIRECT,
            pattern=routing_key,
            match_type=MatchType.EXACT,
            target_queues=[target_queue],
        )

    @staticmethod
    def topic_route(
        name: str,
        topic_pattern: str,
        target_queues: builtins.list[str],
        priority: int = 0,
    ) -> RoutingRule:
        """Create a topic routing rule."""
        return RoutingRule(
            name=name,
            priority=priority,
            routing_type=RoutingType.TOPIC,
            pattern=topic_pattern,
            target_queues=target_queues,
        )

    @staticmethod
    def fanout_route(
        name: str, target_queues: builtins.list[str], priority: int = 0
    ) -> RoutingRule:
        """Create a fanout routing rule."""
        return RoutingRule(
            name=name,
            priority=priority,
            routing_type=RoutingType.FANOUT,
            target_queues=target_queues,
        )

    @staticmethod
    def header_route(
        name: str,
        header_conditions: builtins.dict[str, Any],
        target_queues: builtins.list[str],
        priority: int = 0,
    ) -> RoutingRule:
        """Create a header-based routing rule."""
        return RoutingRule(
            name=name,
            priority=priority,
            routing_type=RoutingType.HEADERS,
            header_conditions=header_conditions,
            target_queues=target_queues,
        )

    @staticmethod
    def content_route(
        name: str,
        content_conditions: builtins.dict[str, Any],
        target_queues: builtins.list[str],
        priority: int = 0,
    ) -> RoutingRule:
        """Create a content-based routing rule."""
        return RoutingRule(
            name=name,
            priority=priority,
            routing_type=RoutingType.CONTENT,
            content_conditions=content_conditions,
            target_queues=target_queues,
        )

    @staticmethod
    def custom_route(
        name: str,
        custom_router: Callable[[Message], builtins.list[str]],
        priority: int = 0,
    ) -> RoutingRule:
        """Create a custom routing rule."""
        return RoutingRule(
            name=name,
            priority=priority,
            routing_type=RoutingType.CUSTOM,
            custom_router=custom_router,
        )
