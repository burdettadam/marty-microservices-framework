"""
Resilience and Fault Tolerance Framework for Marty Microservices

This module provides comprehensive resilience patterns including circuit breakers,
retry logic, bulkhead isolation, timeout management, and chaos engineering
capabilities for production reliability.
"""

import asyncio
import builtins
import logging
import random

# For statistics and analysis
import statistics
import threading
import time
import uuid
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as ConcurrentTimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, dict, list, set


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class RetryStrategy(Enum):
    """Retry strategy types."""

    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    RANDOM_JITTER = "random_jitter"


class BulkheadType(Enum):
    """Bulkhead isolation types."""

    THREAD_POOL = "thread_pool"
    SEMAPHORE = "semaphore"
    RATE_LIMIT = "rate_limit"


class ChaosExperimentType(Enum):
    """Types of chaos experiments."""

    LATENCY_INJECTION = "latency_injection"
    FAILURE_INJECTION = "failure_injection"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    NETWORK_PARTITION = "network_partition"
    CPU_STRESS = "cpu_stress"
    MEMORY_STRESS = "memory_stress"


class ResilienceMetricType(Enum):
    """Types of resilience metrics."""

    SUCCESS_RATE = "success_rate"
    FAILURE_RATE = "failure_rate"
    RESPONSE_TIME = "response_time"
    CIRCUIT_BREAKER_STATE = "circuit_breaker_state"
    RETRY_COUNT = "retry_count"
    BULKHEAD_UTILIZATION = "bulkhead_utilization"


@dataclass
class RetryConfig:
    """Configuration for retry logic."""

    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    backoff_multiplier: float = 2.0
    jitter_range: float = 0.1  # 10% jitter
    retryable_exceptions: builtins.list[type] = field(
        default_factory=lambda: [Exception]
    )
    non_retryable_exceptions: builtins.list[type] = field(default_factory=list)


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5
    success_threshold: int = 3
    timeout: float = 60.0  # seconds
    evaluation_window: int = 100  # number of requests
    minimum_requests: int = 10
    failure_rate_threshold: float = 0.5  # 50%


@dataclass
class BulkheadConfig:
    """Configuration for bulkhead isolation."""

    type: BulkheadType = BulkheadType.THREAD_POOL
    max_concurrent: int = 10
    queue_size: int = 100
    timeout: float = 30.0  # seconds
    isolation_key: str = "default"


@dataclass
class TimeoutConfig:
    """Configuration for timeout management."""

    connect_timeout: float = 5.0  # seconds
    read_timeout: float = 30.0  # seconds
    total_timeout: float = 60.0  # seconds
    enable_adaptive: bool = True
    percentile_threshold: float = 0.95  # 95th percentile


@dataclass
class ResilienceMetric:
    """Resilience metric data point."""

    metric_type: ResilienceMetricType
    value: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    labels: builtins.dict[str, str] = field(default_factory=dict)


@dataclass
class ChaosExperiment:
    """Chaos engineering experiment."""

    experiment_id: str
    name: str
    experiment_type: ChaosExperimentType
    target_services: builtins.list[str]
    parameters: builtins.dict[str, Any]
    duration_seconds: int
    probability: float = 1.0  # 100% by default
    schedule: str | None = None  # Cron-like schedule
    is_active: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


T = TypeVar("T")


class CircuitBreakerException(Exception):
    """Exception raised when circuit breaker is open."""


class BulkheadRejectionException(Exception):
    """Exception raised when bulkhead rejects request."""


class TimeoutException(Exception):
    """Exception raised when operation times out."""


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
                    self._record_metric(
                        ResilienceMetricType.CIRCUIT_BREAKER_STATE, 0
                    )  # 0 = open
                    raise CircuitBreakerException(
                        f"Circuit breaker {self.name} is open"
                    )

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
        self._record_metric(
            ResilienceMetricType.CIRCUIT_BREAKER_STATE, 1
        )  # 1 = closed/half-open

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
        self.next_attempt_time = datetime.now(timezone.utc) + timedelta(
            seconds=self.config.timeout
        )

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


class RetryMechanism:
    """Advanced retry mechanism with multiple strategies."""

    def __init__(self, name: str, config: RetryConfig):
        """Initialize retry mechanism."""
        self.name = name
        self.config = config

        # Metrics tracking
        self.metrics: deque = deque(maxlen=1000)

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator for retry mechanism."""

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
        """Execute operation with retry logic."""
        last_exception = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                result = operation()

                # Record success metric
                if attempt > 1:
                    self._record_retry_metric(attempt - 1)

                return result

            except Exception as e:
                last_exception = e

                # Check if exception is retryable
                if not self._is_retryable_exception(e):
                    raise

                # Don't retry on last attempt
                if attempt == self.config.max_attempts:
                    break

                # Calculate delay and wait
                delay = self._calculate_delay(attempt)
                time.sleep(delay)

        # Record final failure
        self._record_retry_metric(self.config.max_attempts)

        # Raise the last exception
        if last_exception:
            raise last_exception
        raise Exception("Max retry attempts exceeded")

    async def execute_async(self, operation: Callable[[], T]) -> T:
        """Execute async operation with retry logic."""
        last_exception = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                if asyncio.iscoroutinefunction(operation):
                    result = await operation()
                else:
                    result = operation()

                # Record success metric
                if attempt > 1:
                    self._record_retry_metric(attempt - 1)

                return result

            except Exception as e:
                last_exception = e

                # Check if exception is retryable
                if not self._is_retryable_exception(e):
                    raise

                # Don't retry on last attempt
                if attempt == self.config.max_attempts:
                    break

                # Calculate delay and wait
                delay = self._calculate_delay(attempt)
                await asyncio.sleep(delay)

        # Record final failure
        self._record_retry_metric(self.config.max_attempts)

        # Raise the last exception
        if last_exception:
            raise last_exception
        raise Exception("Max retry attempts exceeded")

    def _is_retryable_exception(self, exception: Exception) -> bool:
        """Check if exception is retryable."""
        # Check non-retryable exceptions first
        for exc_type in self.config.non_retryable_exceptions:
            if isinstance(exception, exc_type):
                return False

        # Check retryable exceptions
        for exc_type in self.config.retryable_exceptions:
            if isinstance(exception, exc_type):
                return True

        return False

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt."""
        if self.config.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.config.base_delay

        elif self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.config.base_delay * (
                self.config.backoff_multiplier ** (attempt - 1)
            )

        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.base_delay * attempt

        elif self.config.strategy == RetryStrategy.RANDOM_JITTER:
            base_delay = self.config.base_delay * (
                self.config.backoff_multiplier ** (attempt - 1)
            )
            jitter = (
                base_delay * self.config.jitter_range * (random.random() * 2 - 1)
            )  # ±jitter_range
            delay = base_delay + jitter

        else:
            delay = self.config.base_delay

        # Apply max delay limit
        return min(delay, self.config.max_delay)

    def _record_retry_metric(self, retry_count: int):
        """Record retry metric."""
        metric = ResilienceMetric(
            metric_type=ResilienceMetricType.RETRY_COUNT,
            value=retry_count,
            labels={"retry_mechanism": self.name},
        )
        self.metrics.append(metric)


class BulkheadIsolation:
    """Bulkhead isolation for resource protection."""

    def __init__(self, name: str, config: BulkheadConfig):
        """Initialize bulkhead isolation."""
        self.name = name
        self.config = config

        # Initialize isolation mechanism based on type
        if config.type == BulkheadType.THREAD_POOL:
            self.executor = ThreadPoolExecutor(
                max_workers=config.max_concurrent, thread_name_prefix=f"bulkhead-{name}"
            )
        elif config.type == BulkheadType.SEMAPHORE:
            self.semaphore = threading.Semaphore(config.max_concurrent)
            self.async_semaphore = asyncio.Semaphore(config.max_concurrent)
        elif config.type == BulkheadType.RATE_LIMIT:
            self.rate_limiter = RateLimiter(config.max_concurrent, window_seconds=1)

        # Metrics tracking
        self.metrics: deque = deque(maxlen=1000)
        self.current_utilization = 0
        self._lock = threading.Lock()

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator for bulkhead isolation."""

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
        """Execute operation with bulkhead isolation."""
        if self.config.type == BulkheadType.THREAD_POOL:
            return self._execute_with_thread_pool(operation)
        if self.config.type == BulkheadType.SEMAPHORE:
            return self._execute_with_semaphore(operation)
        if self.config.type == BulkheadType.RATE_LIMIT:
            return self._execute_with_rate_limit(operation)
        raise ValueError(f"Unsupported bulkhead type: {self.config.type}")

    async def execute_async(self, operation: Callable[[], T]) -> T:
        """Execute async operation with bulkhead isolation."""
        if self.config.type == BulkheadType.SEMAPHORE:
            return await self._execute_async_with_semaphore(operation)
        if self.config.type == BulkheadType.RATE_LIMIT:
            return await self._execute_async_with_rate_limit(operation)
        # For thread pool, we'll run in executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute, operation)

    def _execute_with_thread_pool(self, operation: Callable[[], T]) -> T:
        """Execute operation using thread pool."""
        try:
            future: Future = self.executor.submit(operation)
            result = future.result(timeout=self.config.timeout)

            self._record_utilization_metric()
            return result

        except ConcurrentTimeoutError:
            raise TimeoutException(f"Operation timed out in bulkhead {self.name}")
        except Exception as e:
            if "rejected" in str(e).lower():
                raise BulkheadRejectionException(
                    f"Request rejected by bulkhead {self.name}"
                )
            raise

    def _execute_with_semaphore(self, operation: Callable[[], T]) -> T:
        """Execute operation using semaphore."""
        acquired = self.semaphore.acquire(timeout=self.config.timeout)
        if not acquired:
            raise BulkheadRejectionException(
                f"Could not acquire semaphore in bulkhead {self.name}"
            )

        try:
            with self._lock:
                self.current_utilization += 1

            result = operation()
            self._record_utilization_metric()
            return result

        finally:
            with self._lock:
                self.current_utilization -= 1
            self.semaphore.release()

    async def _execute_async_with_semaphore(self, operation: Callable[[], T]) -> T:
        """Execute async operation using semaphore."""
        try:
            await asyncio.wait_for(
                self.async_semaphore.acquire(), timeout=self.config.timeout
            )
        except asyncio.TimeoutError:
            raise BulkheadRejectionException(
                f"Could not acquire semaphore in bulkhead {self.name}"
            )

        try:
            with self._lock:
                self.current_utilization += 1

            if asyncio.iscoroutinefunction(operation):
                result = await operation()
            else:
                result = operation()

            self._record_utilization_metric()
            return result

        finally:
            with self._lock:
                self.current_utilization -= 1
            self.async_semaphore.release()

    def _execute_with_rate_limit(self, operation: Callable[[], T]) -> T:
        """Execute operation with rate limiting."""
        if not self.rate_limiter.acquire():
            raise BulkheadRejectionException(
                f"Rate limit exceeded in bulkhead {self.name}"
            )

        result = operation()
        self._record_utilization_metric()
        return result

    async def _execute_async_with_rate_limit(self, operation: Callable[[], T]) -> T:
        """Execute async operation with rate limiting."""
        if not await self.rate_limiter.acquire_async():
            raise BulkheadRejectionException(
                f"Rate limit exceeded in bulkhead {self.name}"
            )

        if asyncio.iscoroutinefunction(operation):
            result = await operation()
        else:
            result = operation()

        self._record_utilization_metric()
        return result

    def _record_utilization_metric(self):
        """Record bulkhead utilization metric."""
        utilization = self.current_utilization / self.config.max_concurrent
        metric = ResilienceMetric(
            metric_type=ResilienceMetricType.BULKHEAD_UTILIZATION,
            value=utilization,
            labels={"bulkhead": self.name, "type": self.config.type.value},
        )
        self.metrics.append(metric)

    def get_utilization(self) -> builtins.dict[str, Any]:
        """Get current bulkhead utilization."""
        return {
            "name": self.name,
            "type": self.config.type.value,
            "current_utilization": self.current_utilization,
            "max_concurrent": self.config.max_concurrent,
            "utilization_percentage": (
                self.current_utilization / self.config.max_concurrent
            )
            * 100,
        }

    def shutdown(self):
        """Shutdown bulkhead resources."""
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=True)


class RateLimiter:
    """Simple rate limiter implementation."""

    def __init__(self, max_requests: int, window_seconds: int = 1):
        """Initialize rate limiter."""
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: deque = deque()
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        """Acquire rate limit token."""
        with self._lock:
            now = time.time()

            # Remove old requests outside window
            while self.requests and self.requests[0] <= now - self.window_seconds:
                self.requests.popleft()

            # Check if we can make request
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True

            return False

    async def acquire_async(self) -> bool:
        """Acquire rate limit token asynchronously."""
        # For simplicity, using the same logic as sync version
        return self.acquire()


class TimeoutManager:
    """Advanced timeout management with adaptive timeouts."""

    def __init__(self, name: str, config: TimeoutConfig):
        """Initialize timeout manager."""
        self.name = name
        self.config = config

        # Response time tracking for adaptive timeouts
        self.response_times: deque = deque(maxlen=1000)
        self.adaptive_timeout = config.total_timeout

        # Metrics tracking
        self.metrics: deque = deque(maxlen=1000)

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator for timeout management."""

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
        """Execute operation with timeout."""
        timeout = self._get_effective_timeout()

        start_time = time.time()

        # For sync operations, we'll use threading
        result_container = {"result": None, "exception": None}

        def run_operation():
            try:
                result_container["result"] = operation()
            except Exception as e:
                result_container["exception"] = e

        thread = threading.Thread(target=run_operation)
        thread.start()
        thread.join(timeout)

        execution_time = time.time() - start_time

        if thread.is_alive():
            # Operation timed out
            self._record_timeout_metric(execution_time, timed_out=True)
            raise TimeoutException(f"Operation timed out after {timeout} seconds")

        # Operation completed
        self.response_times.append(execution_time)
        self._update_adaptive_timeout()
        self._record_timeout_metric(execution_time, timed_out=False)

        if result_container["exception"]:
            raise result_container["exception"]

        return result_container["result"]

    async def execute_async(self, operation: Callable[[], T]) -> T:
        """Execute async operation with timeout."""
        timeout = self._get_effective_timeout()

        start_time = time.time()

        try:
            if asyncio.iscoroutinefunction(operation):
                result = await asyncio.wait_for(operation(), timeout=timeout)
            else:
                result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, operation),
                    timeout=timeout,
                )

            execution_time = time.time() - start_time
            self.response_times.append(execution_time)
            self._update_adaptive_timeout()
            self._record_timeout_metric(execution_time, timed_out=False)

            return result

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            self._record_timeout_metric(execution_time, timed_out=True)
            raise TimeoutException(f"Operation timed out after {timeout} seconds")

    def _get_effective_timeout(self) -> float:
        """Get effective timeout value."""
        if self.config.enable_adaptive and len(self.response_times) >= 10:
            return self.adaptive_timeout
        return self.config.total_timeout

    def _update_adaptive_timeout(self):
        """Update adaptive timeout based on response times."""
        if not self.config.enable_adaptive or len(self.response_times) < 10:
            return

        # Calculate percentile-based timeout
        sorted_times = sorted(self.response_times)
        percentile_index = int(len(sorted_times) * self.config.percentile_threshold)
        percentile_time = sorted_times[min(percentile_index, len(sorted_times) - 1)]

        # Add buffer to percentile time
        buffer_factor = 1.5
        new_timeout = percentile_time * buffer_factor

        # Apply bounds
        min_timeout = self.config.total_timeout * 0.5
        max_timeout = self.config.total_timeout * 2.0

        self.adaptive_timeout = max(min_timeout, min(new_timeout, max_timeout))

    def _record_timeout_metric(self, execution_time: float, timed_out: bool):
        """Record timeout-related metrics."""
        # Record response time
        metric = ResilienceMetric(
            metric_type=ResilienceMetricType.RESPONSE_TIME,
            value=execution_time,
            labels={"timeout_manager": self.name, "timed_out": str(timed_out)},
        )
        self.metrics.append(metric)

    def get_timeout_stats(self) -> builtins.dict[str, Any]:
        """Get timeout statistics."""
        if not self.response_times:
            return {
                "name": self.name,
                "configured_timeout": self.config.total_timeout,
                "adaptive_timeout": self.adaptive_timeout,
                "sample_count": 0,
            }

        return {
            "name": self.name,
            "configured_timeout": self.config.total_timeout,
            "adaptive_timeout": self.adaptive_timeout,
            "sample_count": len(self.response_times),
            "avg_response_time": statistics.mean(self.response_times),
            "median_response_time": statistics.median(self.response_times),
            "p95_response_time": statistics.quantiles(self.response_times, n=20)[18]
            if len(self.response_times) >= 20
            else max(self.response_times),
            "max_response_time": max(self.response_times),
            "min_response_time": min(self.response_times),
        }


class ChaosEngineeringEngine:
    """Chaos engineering engine for resilience testing."""

    def __init__(self, service_name: str):
        """Initialize chaos engineering engine."""
        self.service_name = service_name

        # Active experiments
        self.experiments: builtins.dict[str, ChaosExperiment] = {}
        self.active_experiments: builtins.set[str] = set()

        # Experiment execution
        self.experiment_tasks: builtins.dict[str, asyncio.Task] = {}

        # Metrics and results
        self.experiment_results: deque = deque(maxlen=1000)

        # Safety controls
        self.max_concurrent_experiments = 3
        self.global_kill_switch = False

    def create_experiment(
        self,
        name: str,
        experiment_type: ChaosExperimentType,
        target_services: builtins.list[str],
        parameters: builtins.dict[str, Any],
        duration_seconds: int,
        probability: float = 1.0,
    ) -> str:
        """Create a new chaos experiment."""
        experiment_id = str(uuid.uuid4())

        experiment = ChaosExperiment(
            experiment_id=experiment_id,
            name=name,
            experiment_type=experiment_type,
            target_services=target_services,
            parameters=parameters,
            duration_seconds=duration_seconds,
            probability=probability,
        )

        self.experiments[experiment_id] = experiment
        return experiment_id

    async def start_experiment(self, experiment_id: str) -> bool:
        """Start a chaos experiment."""
        if self.global_kill_switch:
            return False

        if experiment_id not in self.experiments:
            return False

        if len(self.active_experiments) >= self.max_concurrent_experiments:
            return False

        experiment = self.experiments[experiment_id]
        experiment.is_active = True
        self.active_experiments.add(experiment_id)

        # Start experiment task
        task = asyncio.create_task(self._run_experiment(experiment))
        self.experiment_tasks[experiment_id] = task

        return True

    async def stop_experiment(self, experiment_id: str) -> bool:
        """Stop a chaos experiment."""
        if experiment_id not in self.experiments:
            return False

        experiment = self.experiments[experiment_id]
        experiment.is_active = False

        if experiment_id in self.active_experiments:
            self.active_experiments.remove(experiment_id)

        if experiment_id in self.experiment_tasks:
            task = self.experiment_tasks[experiment_id]
            task.cancel()
            del self.experiment_tasks[experiment_id]

        return True

    async def _run_experiment(self, experiment: ChaosExperiment):
        """Run a chaos experiment."""
        try:
            start_time = datetime.now(timezone.utc)

            # Log experiment start
            logging.info(f"Starting chaos experiment: {experiment.name}")

            # Run experiment based on type
            if experiment.experiment_type == ChaosExperimentType.LATENCY_INJECTION:
                await self._inject_latency(experiment)
            elif experiment.experiment_type == ChaosExperimentType.FAILURE_INJECTION:
                await self._inject_failures(experiment)
            elif experiment.experiment_type == ChaosExperimentType.RESOURCE_EXHAUSTION:
                await self._exhaust_resources(experiment)
            elif experiment.experiment_type == ChaosExperimentType.NETWORK_PARTITION:
                await self._simulate_network_partition(experiment)
            elif experiment.experiment_type == ChaosExperimentType.CPU_STRESS:
                await self._stress_cpu(experiment)
            elif experiment.experiment_type == ChaosExperimentType.MEMORY_STRESS:
                await self._stress_memory(experiment)

            # Wait for experiment duration
            await asyncio.sleep(experiment.duration_seconds)

            end_time = datetime.now(timezone.utc)

            # Record experiment result
            result = {
                "experiment_id": experiment.experiment_id,
                "name": experiment.name,
                "type": experiment.experiment_type.value,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration": experiment.duration_seconds,
                "status": "completed",
                "target_services": experiment.target_services,
            }

            self.experiment_results.append(result)

            logging.info(f"Completed chaos experiment: {experiment.name}")

        except asyncio.CancelledError:
            logging.info(f"Chaos experiment cancelled: {experiment.name}")
        except Exception as e:
            logging.exception(f"Error in chaos experiment {experiment.name}: {e}")
        finally:
            # Cleanup
            experiment.is_active = False
            if experiment.experiment_id in self.active_experiments:
                self.active_experiments.remove(experiment.experiment_id)
            if experiment.experiment_id in self.experiment_tasks:
                del self.experiment_tasks[experiment.experiment_id]

    async def _inject_latency(self, experiment: ChaosExperiment):
        """Inject artificial latency."""
        delay_ms = experiment.parameters.get("delay_ms", 1000)

        # This would integrate with service mesh or proxy to inject latency
        # For demo purposes, we'll just log the action
        logging.info(
            f"Injecting {delay_ms}ms latency for services: {experiment.target_services}"
        )

    async def _inject_failures(self, experiment: ChaosExperiment):
        """Inject service failures."""
        failure_rate = experiment.parameters.get("failure_rate", 0.1)

        # This would integrate with service mesh to inject failures
        logging.info(
            f"Injecting {failure_rate*100}% failure rate for services: {experiment.target_services}"
        )

    async def _exhaust_resources(self, experiment: ChaosExperiment):
        """Exhaust system resources."""
        resource_type = experiment.parameters.get("resource_type", "memory")

        logging.info(
            f"Exhausting {resource_type} resources for services: {experiment.target_services}"
        )

    async def _simulate_network_partition(self, experiment: ChaosExperiment):
        """Simulate network partition."""
        partition_type = experiment.parameters.get("partition_type", "split_brain")

        logging.info(
            f"Simulating {partition_type} network partition for services: {experiment.target_services}"
        )

    async def _stress_cpu(self, experiment: ChaosExperiment):
        """Stress CPU resources."""
        cpu_percent = experiment.parameters.get("cpu_percent", 80)

        logging.info(
            f"Stressing CPU to {cpu_percent}% for services: {experiment.target_services}"
        )

    async def _stress_memory(self, experiment: ChaosExperiment):
        """Stress memory resources."""
        memory_percent = experiment.parameters.get("memory_percent", 80)

        logging.info(
            f"Stressing memory to {memory_percent}% for services: {experiment.target_services}"
        )

    def set_kill_switch(self, enabled: bool):
        """Set global kill switch for all experiments."""
        self.global_kill_switch = enabled

        if enabled:
            # Stop all active experiments
            for experiment_id in list(self.active_experiments):
                asyncio.create_task(self.stop_experiment(experiment_id))

    def get_experiment_status(self) -> builtins.dict[str, Any]:
        """Get status of all experiments."""
        return {
            "total_experiments": len(self.experiments),
            "active_experiments": len(self.active_experiments),
            "completed_experiments": len(self.experiment_results),
            "kill_switch_enabled": self.global_kill_switch,
            "max_concurrent": self.max_concurrent_experiments,
            "active_experiment_ids": list(self.active_experiments),
        }


class ResilienceFramework:
    """Main resilience and fault tolerance framework."""

    def __init__(self, service_name: str):
        """Initialize resilience framework."""
        self.service_name = service_name

        # Core resilience components
        self.circuit_breakers: builtins.dict[str, CircuitBreaker] = {}
        self.retry_mechanisms: builtins.dict[str, RetryMechanism] = {}
        self.bulkheads: builtins.dict[str, BulkheadIsolation] = {}
        self.timeout_managers: builtins.dict[str, TimeoutManager] = {}

        # Chaos engineering
        self.chaos_engine = ChaosEngineeringEngine(service_name)

        # Metrics aggregation
        self.all_metrics: deque = deque(maxlen=10000)

        # Health monitoring
        self.health_checks: builtins.dict[str, Callable] = {}
        self.health_status: builtins.dict[str, bool] = {}

    def create_circuit_breaker(
        self, name: str, config: CircuitBreakerConfig = None
    ) -> CircuitBreaker:
        """Create circuit breaker."""
        config = config or CircuitBreakerConfig()
        circuit_breaker = CircuitBreaker(name, config)
        self.circuit_breakers[name] = circuit_breaker
        return circuit_breaker

    def create_retry_mechanism(
        self, name: str, config: RetryConfig = None
    ) -> RetryMechanism:
        """Create retry mechanism."""
        config = config or RetryConfig()
        retry_mechanism = RetryMechanism(name, config)
        self.retry_mechanisms[name] = retry_mechanism
        return retry_mechanism

    def create_bulkhead(
        self, name: str, config: BulkheadConfig = None
    ) -> BulkheadIsolation:
        """Create bulkhead isolation."""
        config = config or BulkheadConfig()
        bulkhead = BulkheadIsolation(name, config)
        self.bulkheads[name] = bulkhead
        return bulkhead

    def create_timeout_manager(
        self, name: str, config: TimeoutConfig = None
    ) -> TimeoutManager:
        """Create timeout manager."""
        config = config or TimeoutConfig()
        timeout_manager = TimeoutManager(name, config)
        self.timeout_managers[name] = timeout_manager
        return timeout_manager

    def register_health_check(self, name: str, check_function: Callable[[], bool]):
        """Register health check function."""
        self.health_checks[name] = check_function

    async def run_health_checks(self) -> builtins.dict[str, bool]:
        """Run all health checks."""
        results = {}

        for name, check_function in self.health_checks.items():
            try:
                if asyncio.iscoroutinefunction(check_function):
                    result = await check_function()
                else:
                    result = check_function()
                results[name] = bool(result)
            except Exception as e:
                logging.exception(f"Health check {name} failed: {e}")
                results[name] = False

        self.health_status.update(results)
        return results

    def get_overall_resilience_status(self) -> builtins.dict[str, Any]:
        """Get overall resilience status."""
        # Circuit breaker status
        cb_status = {}
        for name, cb in self.circuit_breakers.items():
            cb_status[name] = cb.get_state()

        # Bulkhead utilization
        bulkhead_status = {}
        for name, bulkhead in self.bulkheads.items():
            bulkhead_status[name] = bulkhead.get_utilization()

        # Timeout statistics
        timeout_status = {}
        for name, tm in self.timeout_managers.items():
            timeout_status[name] = tm.get_timeout_stats()

        # Chaos engineering status
        chaos_status = self.chaos_engine.get_experiment_status()

        # Aggregate metrics
        recent_metrics = list(self.all_metrics)[-100:]  # Last 100 metrics

        return {
            "service": self.service_name,
            "circuit_breakers": cb_status,
            "bulkheads": bulkhead_status,
            "timeout_managers": timeout_status,
            "chaos_engineering": chaos_status,
            "health_checks": self.health_status,
            "recent_metrics_count": len(recent_metrics),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def shutdown(self):
        """Shutdown all resilience components."""
        # Shutdown bulkheads
        for bulkhead in self.bulkheads.values():
            bulkhead.shutdown()

        # Stop all chaos experiments
        self.chaos_engine.set_kill_switch(True)


def create_resilience_framework(service_name: str) -> ResilienceFramework:
    """Create resilience framework instance."""
    return ResilienceFramework(service_name)


# Convenience decorators for common patterns
def with_circuit_breaker(name: str, config: CircuitBreakerConfig = None):
    """Decorator to add circuit breaker to function."""

    def decorator(func):
        cb = CircuitBreaker(name, config or CircuitBreakerConfig())
        return cb(func)

    return decorator


def with_retry(name: str, config: RetryConfig = None):
    """Decorator to add retry logic to function."""

    def decorator(func):
        retry = RetryMechanism(name, config or RetryConfig())
        return retry(func)

    return decorator


def with_bulkhead(name: str, config: BulkheadConfig = None):
    """Decorator to add bulkhead isolation to function."""

    def decorator(func):
        bulkhead = BulkheadIsolation(name, config or BulkheadConfig())
        return bulkhead(func)

    return decorator


def with_timeout(name: str, config: TimeoutConfig = None):
    """Decorator to add timeout management to function."""

    def decorator(func):
        timeout_mgr = TimeoutManager(name, config or TimeoutConfig())
        return timeout_mgr(func)

    return decorator


def resilient(
    circuit_breaker_config: CircuitBreakerConfig = None,
    retry_config: RetryConfig = None,
    bulkhead_config: BulkheadConfig = None,
    timeout_config: TimeoutConfig = None,
):
    """Decorator to add complete resilience patterns to function."""

    def decorator(func):
        func_name = func.__name__

        # Apply patterns in order: timeout -> bulkhead -> circuit breaker -> retry
        decorated_func = func

        if timeout_config:
            timeout_mgr = TimeoutManager(f"{func_name}_timeout", timeout_config)
            decorated_func = timeout_mgr(decorated_func)

        if bulkhead_config:
            bulkhead = BulkheadIsolation(f"{func_name}_bulkhead", bulkhead_config)
            decorated_func = bulkhead(decorated_func)

        if circuit_breaker_config:
            cb = CircuitBreaker(f"{func_name}_circuit_breaker", circuit_breaker_config)
            decorated_func = cb(decorated_func)

        if retry_config:
            retry = RetryMechanism(f"{func_name}_retry", retry_config)
            decorated_func = retry(decorated_func)

        return decorated_func

    return decorator
