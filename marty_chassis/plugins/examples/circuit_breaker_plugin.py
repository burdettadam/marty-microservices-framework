"""
Circuit Breaker Plugin Example.

This plugin demonstrates circuit breaker patterns with timers,
failure tracking, and automatic recovery mechanisms.
"""

import asyncio
import random
import time
from enum import Enum
from typing import Any, Dict, Optional

from ..decorators import plugin
from ..interfaces import IMiddlewarePlugin, PluginContext, PluginMetadata


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@plugin(
    name="circuit-breaker",
    version="1.0.0",
    description="Circuit breaker middleware with failure tracking and recovery",
    author="Marty Team",
    provides=["circuit-breaker", "resilience", "fault-tolerance"],
)
class CircuitBreakerPlugin(IMiddlewarePlugin):
    """
    Circuit breaker plugin for demonstration.

    This plugin demonstrates:
    - Circuit breaker pattern implementation
    - Failure rate monitoring with timers
    - Automatic state transitions
    - Recovery testing mechanisms
    - Detailed observability and metrics
    """

    def __init__(self):
        super().__init__()

        # Circuit breaker configuration
        self.failure_threshold = 5  # failures before opening
        self.failure_rate_threshold = 0.5  # 50% failure rate threshold
        self.recovery_timeout = 30.0  # seconds before trying half-open
        self.success_threshold = 3  # successes to close from half-open
        self.monitoring_window = 60.0  # seconds for failure rate calculation

        # Circuit state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self.state_change_time = time.time()

        # Request tracking for failure rate
        self.request_history: list = []  # (timestamp, success)

        # Metrics
        self.total_requests = 0
        self.blocked_requests = 0
        self.state_transitions = {
            CircuitState.CLOSED: 0,
            CircuitState.OPEN: 0,
            CircuitState.HALF_OPEN: 0,
        }

        # Timers for testing
        self._recovery_timer: Optional[asyncio.Task] = None

    async def initialize(self, context: PluginContext) -> None:
        """Initialize the circuit breaker plugin."""
        await super().initialize(context)

        # Get configuration
        self.failure_threshold = context.get_config("failure_threshold", 5)
        self.failure_rate_threshold = context.get_config("failure_rate_threshold", 0.5)
        self.recovery_timeout = context.get_config("recovery_timeout", 30.0)
        self.success_threshold = context.get_config("success_threshold", 3)
        self.monitoring_window = context.get_config("monitoring_window", 60.0)

        # Register circuit breaker service
        if context.service_registry:
            context.service_registry.register_service(
                "circuit-breaker",
                {
                    "type": "middleware",
                    "plugin": self.plugin_metadata.name,
                    "state": self.state.value,
                    "tags": ["circuit-breaker", "resilience", "middleware"],
                },
            )

        self.logger.info(
            f"Circuit breaker initialized with failure_threshold={self.failure_threshold}"
        )

    async def start(self) -> None:
        """Start the circuit breaker plugin."""
        await super().start()

        # Publish plugin started event
        if self.context and self.context.event_bus:
            await self.context.event_bus.publish(
                "circuit_breaker.started",
                {
                    "plugin": self.plugin_metadata.name,
                    "initial_state": self.state.value,
                    "config": {
                        "failure_threshold": self.failure_threshold,
                        "failure_rate_threshold": self.failure_rate_threshold,
                        "recovery_timeout": self.recovery_timeout,
                    },
                },
                source=self.plugin_metadata.name,
            )

        self.logger.info("Circuit breaker started")

    async def stop(self) -> None:
        """Stop the circuit breaker plugin."""
        await super().stop()

        # Cancel recovery timer
        if self._recovery_timer and not self._recovery_timer.done():
            self._recovery_timer.cancel()
            try:
                await self._recovery_timer
            except asyncio.CancelledError:
                pass

        self.logger.info("Circuit breaker stopped")

    @property
    def plugin_metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        return PluginMetadata(
            name="circuit-breaker",
            version="1.0.0",
            description="Circuit breaker middleware with failure tracking and recovery",
            author="Marty Team",
            provides=["circuit-breaker", "resilience", "fault-tolerance"],
        )

    async def process_request(self, request: Any, call_next) -> Any:
        """
        Process request through circuit breaker.

        Args:
            request: The incoming request object
            call_next: Function to call the next middleware/handler

        Returns:
            Response object

        Raises:
            Exception: If circuit is open or request fails
        """
        self.total_requests += 1
        request_start_time = time.time()

        # Check if circuit allows request
        if not await self._can_execute_request():
            self.blocked_requests += 1

            # Publish blocked request event
            if self.context and self.context.event_bus:
                await self.context.event_bus.publish(
                    "circuit_breaker.request_blocked",
                    {
                        "state": self.state.value,
                        "failure_count": self.failure_count,
                        "blocked_requests": self.blocked_requests,
                    },
                    source=self.plugin_metadata.name,
                )

            raise Exception(f"Circuit breaker is {self.state.value} - request blocked")

        # Execute request
        try:
            response = await call_next(request)

            # Record success
            request_duration = time.time() - request_start_time
            await self._record_success(request_duration)

            return response

        except Exception as e:
            # Record failure
            request_duration = time.time() - request_start_time
            await self._record_failure(str(e), request_duration)
            raise

    def get_middleware_priority(self) -> int:
        """Return middleware priority (run early to protect downstream)."""
        return 5  # High priority to protect downstream services

    async def _can_execute_request(self) -> bool:
        """Check if the circuit breaker allows request execution."""
        current_time = time.time()

        if self.state == CircuitState.CLOSED:
            return True

        elif self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if current_time - self.state_change_time >= self.recovery_timeout:
                await self._transition_to_half_open()
                return True
            return False

        elif self.state == CircuitState.HALF_OPEN:
            # Allow limited requests to test recovery
            return True

        return False

    async def _record_success(self, duration: float) -> None:
        """Record a successful request."""
        current_time = time.time()

        # Add to request history
        self.request_history.append((current_time, True))
        self._cleanup_old_requests(current_time)

        # Handle state-specific logic
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1

            if self.success_count >= self.success_threshold:
                await self._transition_to_closed()

        # Publish success event
        if self.context and self.context.event_bus:
            await self.context.event_bus.publish(
                "circuit_breaker.request_success",
                {
                    "state": self.state.value,
                    "duration": duration,
                    "success_count": self.success_count,
                },
                source=self.plugin_metadata.name,
            )

    async def _record_failure(self, error: str, duration: float) -> None:
        """Record a failed request."""
        current_time = time.time()

        # Add to request history
        self.request_history.append((current_time, False))
        self._cleanup_old_requests(current_time)

        self.failure_count += 1
        self.last_failure_time = current_time

        # Check if we should open the circuit
        if self.state == CircuitState.CLOSED:
            failure_rate = self._calculate_failure_rate()

            if (
                self.failure_count >= self.failure_threshold
                or failure_rate >= self.failure_rate_threshold
            ):
                await self._transition_to_open()

        elif self.state == CircuitState.HALF_OPEN:
            # Any failure in half-open state reopens the circuit
            await self._transition_to_open()

        # Publish failure event
        if self.context and self.context.event_bus:
            await self.context.event_bus.publish(
                "circuit_breaker.request_failure",
                {
                    "state": self.state.value,
                    "error": error,
                    "duration": duration,
                    "failure_count": self.failure_count,
                    "failure_rate": self._calculate_failure_rate(),
                },
                source=self.plugin_metadata.name,
            )

    def _calculate_failure_rate(self) -> float:
        """Calculate failure rate within the monitoring window."""
        current_time = time.time()
        cutoff_time = current_time - self.monitoring_window

        # Filter requests within monitoring window
        recent_requests = [
            success
            for timestamp, success in self.request_history
            if timestamp >= cutoff_time
        ]

        if not recent_requests:
            return 0.0

        failures = sum(1 for success in recent_requests if not success)
        return failures / len(recent_requests)

    def _cleanup_old_requests(self, current_time: float) -> None:
        """Remove old requests from history."""
        cutoff_time = current_time - self.monitoring_window
        self.request_history = [
            (timestamp, success)
            for timestamp, success in self.request_history
            if timestamp >= cutoff_time
        ]

    async def _transition_to_closed(self) -> None:
        """Transition circuit to CLOSED state."""
        old_state = self.state
        self.state = CircuitState.CLOSED
        self.state_change_time = time.time()
        self.failure_count = 0
        self.success_count = 0
        self.state_transitions[CircuitState.CLOSED] += 1

        # Cancel recovery timer if running
        if self._recovery_timer and not self._recovery_timer.done():
            self._recovery_timer.cancel()

        await self._publish_state_change(old_state, self.state)
        self.logger.info("Circuit breaker transitioned to CLOSED")

    async def _transition_to_open(self) -> None:
        """Transition circuit to OPEN state."""
        old_state = self.state
        self.state = CircuitState.OPEN
        self.state_change_time = time.time()
        self.success_count = 0
        self.state_transitions[CircuitState.OPEN] += 1

        # Start recovery timer
        self._recovery_timer = asyncio.create_task(self._recovery_timer_task())

        await self._publish_state_change(old_state, self.state)
        self.logger.warning(
            f"Circuit breaker OPENED after {self.failure_count} failures"
        )

    async def _transition_to_half_open(self) -> None:
        """Transition circuit to HALF_OPEN state."""
        old_state = self.state
        self.state = CircuitState.HALF_OPEN
        self.state_change_time = time.time()
        self.success_count = 0
        self.state_transitions[CircuitState.HALF_OPEN] += 1

        await self._publish_state_change(old_state, self.state)
        self.logger.info(
            "Circuit breaker transitioned to HALF_OPEN for recovery testing"
        )

    async def _recovery_timer_task(self) -> None:
        """Recovery timer task for automatic state transitions."""
        try:
            await asyncio.sleep(self.recovery_timeout)

            if self.state == CircuitState.OPEN:
                await self._transition_to_half_open()

        except asyncio.CancelledError:
            pass

    async def _publish_state_change(
        self, old_state: CircuitState, new_state: CircuitState
    ) -> None:
        """Publish state change event."""
        if self.context and self.context.event_bus:
            await self.context.event_bus.publish(
                "circuit_breaker.state_changed",
                {
                    "old_state": old_state.value,
                    "new_state": new_state.value,
                    "failure_count": self.failure_count,
                    "failure_rate": self._calculate_failure_rate(),
                    "timestamp": time.time(),
                },
                source=self.plugin_metadata.name,
            )

    async def get_circuit_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        current_time = time.time()

        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_rate": self._calculate_failure_rate(),
            "total_requests": self.total_requests,
            "blocked_requests": self.blocked_requests,
            "time_in_current_state": current_time - self.state_change_time,
            "state_transitions": dict(self.state_transitions),
            "last_failure_time": self.last_failure_time,
            "config": {
                "failure_threshold": self.failure_threshold,
                "failure_rate_threshold": self.failure_rate_threshold,
                "recovery_timeout": self.recovery_timeout,
                "success_threshold": self.success_threshold,
                "monitoring_window": self.monitoring_window,
            },
        }

    async def force_state_change(self, new_state: str) -> None:
        """Manually force a state change (for testing)."""
        try:
            target_state = CircuitState(new_state)
            old_state = self.state

            if target_state == CircuitState.CLOSED:
                await self._transition_to_closed()
            elif target_state == CircuitState.OPEN:
                await self._transition_to_open()
            elif target_state == CircuitState.HALF_OPEN:
                await self._transition_to_half_open()

            self.logger.info(
                f"Manually changed circuit breaker state from {old_state.value} to {target_state.value}"
            )

        except ValueError:
            raise ValueError(
                f"Invalid state: {new_state}. Valid states: {[s.value for s in CircuitState]}"
            )

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check with circuit breaker status."""
        health = await super().health_check()

        # Add circuit breaker specific health information
        stats = await self.get_circuit_stats()

        health["details"] = {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_rate": stats["failure_rate"],
            "total_requests": self.total_requests,
            "blocked_requests": self.blocked_requests,
            "time_in_current_state": stats["time_in_current_state"],
        }

        # Health status based on circuit state and failure rate
        if self.state == CircuitState.OPEN:
            health["healthy"] = False
        elif stats["failure_rate"] > 0.8:  # Very high failure rate
            health["healthy"] = False
        else:
            health["healthy"] = True

        return health
