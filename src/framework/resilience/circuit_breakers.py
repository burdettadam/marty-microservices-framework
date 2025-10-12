"""
Circuit Breaker Implementation for Marty Microservices Framework

This module implements circuit breaker patterns for fault tolerance
and resilience in microservices.
"""

import asyncio
import builtins
import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from typing import Any, TypeVar


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ResilienceMetricType(Enum):
    """Types of resilience metrics."""

    SUCCESS_RATE = "success_rate"
    FAILURE_RATE = "failure_rate"
    RESPONSE_TIME = "response_time"
    CIRCUIT_BREAKER_STATE = "circuit_breaker_state"
    RETRY_COUNT = "retry_count"
    BULKHEAD_UTILIZATION = "bulkhead_utilization"


T = TypeVar("T")


class CircuitBreakerException(Exception):
    """Exception raised when circuit breaker is open."""


class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 3,
        timeout: float = 60.0,
        evaluation_window: int = 100,
        minimum_requests: int = 10,
        failure_rate_threshold: float = 0.5,
    ):
        """Initialize circuit breaker configuration."""
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.evaluation_window = evaluation_window
        self.minimum_requests = minimum_requests
        self.failure_rate_threshold = failure_rate_threshold


class ResilienceMetric:
    """Resilience metric data."""

    def __init__(
        self,
        metric_type: ResilienceMetricType,
        value: float,
        labels: builtins.dict[str, str] | None = None,
    ):
        """Initialize resilience metric."""
        self.metric_type = metric_type
        self.value = value
        self.labels = labels or {}
        self.timestamp = datetime.now(timezone.utc)


class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance."""

    def __init__(self, name: str, config: CircuitBreakerConfig):
        """Initialize circuit breaker."""
        self.name = name
        self.config = config

        # State management
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: datetime | None = None
        self.next_attempt_time: datetime | None = None

        # Metrics tracking
        self.request_history: deque = deque(maxlen=config.evaluation_window)
        self.metrics: deque = deque(maxlen=1000)

        # Thread safety
        self._lock = threading.RLock()

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator for circuit breaker."""

        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return self.execute(lambda: func(*args, **kwargs))

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            return await self.execute_async(lambda: func(*args, **kwargs))

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    def execute(self, operation: Callable[[], T]) -> T:
        """Execute operation with circuit breaker protection."""
        with self._lock:
            # Check if circuit is open
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    self._record_metric(ResilienceMetricType.CIRCUIT_BREAKER_STATE, 0)  # 0 = open
                    raise CircuitBreakerException(f"Circuit breaker {self.name} is open")

            # Execute operation
            start_time = time.time()
            try:
                result = operation()

                # Record success
                execution_time = time.time() - start_time
                self._record_success(execution_time)

                return result

            except Exception as e:
                # Record failure
                execution_time = time.time() - start_time
                self._record_failure(execution_time, e)
                raise

    async def execute_async(self, operation: Callable[[], T]) -> T:
        """Execute async operation with circuit breaker protection."""
        # Note: For async operations, we need to be careful with locks
        # Check if circuit is open
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                self._record_metric(ResilienceMetricType.CIRCUIT_BREAKER_STATE, 0)
                raise CircuitBreakerException(f"Circuit breaker {self.name} is open")

        # Execute operation
        start_time = time.time()
        try:
            if asyncio.iscoroutinefunction(operation):
                result = await operation()
            else:
                result = operation()

            # Record success
            execution_time = time.time() - start_time
            self._record_success(execution_time)

            return result

        except Exception as e:
            # Record failure
            execution_time = time.time() - start_time
            self._record_failure(execution_time, e)
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt to reset."""
        if self.next_attempt_time is None:
            return True

        return datetime.now(timezone.utc) >= self.next_attempt_time

    def _record_success(self, execution_time: float):
        """Record successful operation."""
        self.request_history.append({"success": True, "time": execution_time})

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0

        # Record metrics
        self._record_metric(ResilienceMetricType.SUCCESS_RATE, 1.0)
        self._record_metric(ResilienceMetricType.RESPONSE_TIME, execution_time)
        self._record_metric(ResilienceMetricType.CIRCUIT_BREAKER_STATE, 1)  # 1 = closed/half-open

    def _record_failure(self, execution_time: float, exception: Exception):
        """Record failed operation."""
        self.request_history.append(
            {"success": False, "time": execution_time, "error": str(exception)}
        )

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self._set_next_attempt_time()
        else:
            self.failure_count += 1
            self.last_failure_time = datetime.now(timezone.utc)

            # Check if we should open the circuit
            if self._should_open_circuit():
                self.state = CircuitState.OPEN
                self._set_next_attempt_time()

        # Record metrics
        self._record_metric(ResilienceMetricType.FAILURE_RATE, 1.0)
        self._record_metric(ResilienceMetricType.RESPONSE_TIME, execution_time)

    def _should_open_circuit(self) -> bool:
        """Check if circuit should be opened."""
        if len(self.request_history) < self.config.minimum_requests:
            return False

        # Check failure rate
        recent_requests = list(self.request_history)[-self.config.evaluation_window :]
        if len(recent_requests) >= self.config.minimum_requests:
            failure_rate = sum(1 for r in recent_requests if not r["success"]) / len(
                recent_requests
            )
            return failure_rate >= self.config.failure_rate_threshold

        # Fallback to failure count
        return self.failure_count >= self.config.failure_threshold

    def _set_next_attempt_time(self):
        """Set next attempt time for circuit reset."""
        self.next_attempt_time = datetime.now(timezone.utc) + timedelta(seconds=self.config.timeout)

    def _record_metric(self, metric_type: ResilienceMetricType, value: float):
        """Record resilience metric."""
        metric = ResilienceMetric(
            metric_type=metric_type, value=value, labels={"circuit_breaker": self.name}
        )
        self.metrics.append(metric)

    def get_state(self) -> builtins.dict[str, Any]:
        """Get current circuit breaker state."""
        with self._lock:
            return {
                "name": self.name,
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "total_requests": len(self.request_history),
                "success_rate": self._calculate_success_rate(),
                "next_attempt_time": self.next_attempt_time.isoformat()
                if self.next_attempt_time
                else None,
            }

    def _calculate_success_rate(self) -> float:
        """Calculate current success rate."""
        if not self.request_history:
            return 1.0

        successful = sum(1 for r in self.request_history if r["success"])
        return successful / len(self.request_history)

    def get_metrics(self) -> builtins.list[ResilienceMetric]:
        """Get circuit breaker metrics."""
        return list(self.metrics)

    def reset(self):
        """Reset circuit breaker to closed state."""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            self.next_attempt_time = None
            self.request_history.clear()

        logging.info("Circuit breaker %s has been reset", self.name)
