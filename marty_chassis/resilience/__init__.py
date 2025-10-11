"""
Resilience patterns for the Marty Chassis.

This module provides:
- Circuit breaker pattern implementation
- Retry policies with exponential backoff
- Bulkhead pattern for resource isolation
- Timeout handling
- Fallback mechanisms
"""

import asyncio
import functools
import time
from collections.abc import Callable
from enum import Enum
from typing import Any, Optional, TypeVar, Union

from tenacity import (
    AsyncRetrying,
    RetryError,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..exceptions import CircuitBreakerError
from ..logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker implementation for handling failures gracefully."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        name: str | None = None,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name or "circuit_breaker"

        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.state = CircuitState.CLOSED

        logger.info(
            "Circuit breaker initialized",
            name=self.name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )

    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt to reset."""
        if self.last_failure_time is None:
            return False

        return (time.time() - self.last_failure_time) >= self.recovery_timeout

    def _record_success(self) -> None:
        """Record successful operation."""
        self.failure_count = 0
        self.last_failure_time = None
        if self.state != CircuitState.CLOSED:
            logger.info("Circuit breaker reset to CLOSED", name=self.name)
            self.state = CircuitState.CLOSED

    def _record_failure(self) -> None:
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            if self.state == CircuitState.CLOSED:
                logger.warning(
                    "Circuit breaker opened due to failures",
                    name=self.name,
                    failure_count=self.failure_count,
                )
                self.state = CircuitState.OPEN
            elif self.state == CircuitState.HALF_OPEN:
                logger.warning(
                    "Circuit breaker re-opened after half-open failure",
                    name=self.name,
                )
                self.state = CircuitState.OPEN

    def _can_execute(self) -> bool:
        """Check if operation can be executed."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                logger.info(
                    "Circuit breaker transitioning to HALF_OPEN", name=self.name
                )
                self.state = CircuitState.HALF_OPEN
                return True
            return False

        # HALF_OPEN state
        return True

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection."""
        if not self._can_execute():
            logger.warning("Circuit breaker is OPEN, rejecting call", name=self.name)
            raise CircuitBreakerError(
                f"Circuit breaker '{self.name}' is OPEN",
                error_code="CIRCUIT_BREAKER_OPEN",
            )

        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except self.expected_exception as e:
            self._record_failure()
            logger.warning(
                "Circuit breaker recorded failure",
                name=self.name,
                error=str(e),
                failure_count=self.failure_count,
            )
            raise

    async def acall(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute async function with circuit breaker protection."""
        if not self._can_execute():
            logger.warning(
                "Circuit breaker is OPEN, rejecting async call", name=self.name
            )
            raise CircuitBreakerError(
                f"Circuit breaker '{self.name}' is OPEN",
                error_code="CIRCUIT_BREAKER_OPEN",
            )

        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except self.expected_exception as e:
            self._record_failure()
            logger.warning(
                "Circuit breaker recorded async failure",
                name=self.name,
                error=str(e),
                failure_count=self.failure_count,
            )
            raise

    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        return self.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit breaker is closed."""
        return self.state == CircuitState.CLOSED

    @property
    def is_half_open(self) -> bool:
        """Check if circuit breaker is half-open."""
        return self.state == CircuitState.HALF_OPEN


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: type = Exception,
    name: str | None = None,
):
    """Decorator for circuit breaker pattern."""

    def decorator(func):
        breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            name=name or func.__name__,
        )

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await breaker.acall(func, *args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    return decorator


class RetryPolicy:
    """Retry policy with exponential backoff."""

    def __init__(
        self,
        max_attempts: int = 3,
        min_wait: float = 1.0,
        max_wait: float = 60.0,
        multiplier: float = 2.0,
        retry_exceptions: tuple = (Exception,),
        name: str | None = None,
    ):
        self.max_attempts = max_attempts
        self.min_wait = min_wait
        self.max_wait = max_wait
        self.multiplier = multiplier
        self.retry_exceptions = retry_exceptions
        self.name = name or "retry_policy"

        logger.info(
            "Retry policy initialized",
            name=self.name,
            max_attempts=max_attempts,
            min_wait=min_wait,
            max_wait=max_wait,
        )

    def _create_retrying(self) -> AsyncRetrying:
        """Create tenacity AsyncRetrying instance."""
        return AsyncRetrying(
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_exponential(
                multiplier=self.multiplier,
                min=self.min_wait,
                max=self.max_wait,
            ),
            retry=retry_if_exception_type(self.retry_exceptions),
            before_sleep=before_sleep_log(logger, level="WARNING"),
            reraise=True,
        )

    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with retry policy."""
        retrying = self._create_retrying()

        try:
            async for attempt in retrying:
                with attempt:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
        except RetryError as e:
            logger.error(
                "Retry policy exhausted",
                name=self.name,
                attempts=self.max_attempts,
                last_error=str(e.last_attempt.exception()),
            )
            raise e.last_attempt.exception()


def retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    multiplier: float = 2.0,
    retry_exceptions: tuple = (Exception,),
    name: str | None = None,
):
    """Decorator for retry pattern."""

    def decorator(func):
        policy = RetryPolicy(
            max_attempts=max_attempts,
            min_wait=min_wait,
            max_wait=max_wait,
            multiplier=multiplier,
            retry_exceptions=retry_exceptions,
            name=name or func.__name__,
        )

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await policy.execute(func, *args, **kwargs)

        return async_wrapper

    return decorator


class BulkheadPattern:
    """Bulkhead pattern for resource isolation."""

    def __init__(self, max_concurrent: int = 10, name: str | None = None):
        self.max_concurrent = max_concurrent
        self.name = name or "bulkhead"
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_requests = 0

        logger.info(
            "Bulkhead pattern initialized",
            name=self.name,
            max_concurrent=max_concurrent,
        )

    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with bulkhead protection."""
        async with self.semaphore:
            self.active_requests += 1

            try:
                logger.debug(
                    "Bulkhead: executing request",
                    name=self.name,
                    active_requests=self.active_requests,
                )

                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            finally:
                self.active_requests -= 1
                logger.debug(
                    "Bulkhead: request completed",
                    name=self.name,
                    active_requests=self.active_requests,
                )

    @property
    def available_permits(self) -> int:
        """Get number of available permits."""
        return self.semaphore._value

    @property
    def is_full(self) -> bool:
        """Check if bulkhead is at capacity."""
        return self.available_permits == 0


def bulkhead(max_concurrent: int = 10, name: str | None = None):
    """Decorator for bulkhead pattern."""

    def decorator(func):
        pattern = BulkheadPattern(
            max_concurrent=max_concurrent, name=name or func.__name__
        )

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await pattern.execute(func, *args, **kwargs)

        return async_wrapper

    return decorator


class TimeoutHandler:
    """Timeout handler for operations."""

    def __init__(self, timeout_seconds: float, name: str | None = None):
        self.timeout_seconds = timeout_seconds
        self.name = name or "timeout_handler"

        logger.info(
            "Timeout handler initialized",
            name=self.name,
            timeout_seconds=timeout_seconds,
        )

    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with timeout."""
        try:
            if asyncio.iscoroutinefunction(func):
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.timeout_seconds,
                )
            else:
                # For sync functions, run in thread pool with timeout
                loop = asyncio.get_event_loop()
                return await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: func(*args, **kwargs)),
                    timeout=self.timeout_seconds,
                )
        except asyncio.TimeoutError:
            logger.warning(
                "Operation timed out",
                name=self.name,
                timeout_seconds=self.timeout_seconds,
            )
            raise


def timeout(timeout_seconds: float, name: str | None = None):
    """Decorator for timeout handling."""

    def decorator(func):
        handler = TimeoutHandler(
            timeout_seconds=timeout_seconds, name=name or func.__name__
        )

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await handler.execute(func, *args, **kwargs)

        return async_wrapper

    return decorator


class ResilienceStack:
    """Combine multiple resilience patterns."""

    def __init__(
        self,
        circuit_breaker_config: dict[str, Any] | None = None,
        retry_config: dict[str, Any] | None = None,
        bulkhead_config: dict[str, Any] | None = None,
        timeout_config: dict[str, Any] | None = None,
        name: str | None = None,
    ):
        self.name = name or "resilience_stack"

        # Initialize patterns
        self.circuit_breaker = (
            CircuitBreaker(**circuit_breaker_config) if circuit_breaker_config else None
        )
        self.retry_policy = RetryPolicy(**retry_config) if retry_config else None
        self.bulkhead = BulkheadPattern(**bulkhead_config) if bulkhead_config else None
        self.timeout_handler = (
            TimeoutHandler(**timeout_config) if timeout_config else None
        )

        logger.info(
            "Resilience stack initialized",
            name=self.name,
            patterns=[
                name
                for name, pattern in [
                    ("circuit_breaker", self.circuit_breaker),
                    ("retry_policy", self.retry_policy),
                    ("bulkhead", self.bulkhead),
                    ("timeout_handler", self.timeout_handler),
                ]
                if pattern is not None
            ],
        )

    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with all configured resilience patterns."""

        async def _execute():
            result = func

            # Apply timeout if configured
            if self.timeout_handler:

                def result():
                    return self.timeout_handler.execute(func, *args, **kwargs)

                args, kwargs = (), {}

            # Apply bulkhead if configured
            if self.bulkhead:
                original_result = result

                def result():
                    return self.bulkhead.execute(original_result, *args, **kwargs)

                args, kwargs = (), {}

            # Apply circuit breaker if configured
            if self.circuit_breaker:
                original_result = result
                if asyncio.iscoroutinefunction(func):

                    def result():
                        return self.circuit_breaker.acall(
                            original_result, *args, **kwargs
                        )

                else:

                    def result():
                        return self.circuit_breaker.call(
                            original_result, *args, **kwargs
                        )

                args, kwargs = (), {}

            # Execute the function
            if asyncio.iscoroutinefunction(result) or asyncio.iscoroutine(result):
                return (
                    await result(*args, **kwargs) if args or kwargs else await result()
                )
            else:
                return result(*args, **kwargs) if args or kwargs else result()

        # Apply retry if configured
        if self.retry_policy:
            return await self.retry_policy.execute(_execute)
        else:
            return await _execute()


def resilience_stack(
    circuit_breaker_config: dict[str, Any] | None = None,
    retry_config: dict[str, Any] | None = None,
    bulkhead_config: dict[str, Any] | None = None,
    timeout_config: dict[str, Any] | None = None,
    name: str | None = None,
):
    """Decorator for applying multiple resilience patterns."""

    def decorator(func):
        stack = ResilienceStack(
            circuit_breaker_config=circuit_breaker_config,
            retry_config=retry_config,
            bulkhead_config=bulkhead_config,
            timeout_config=timeout_config,
            name=name or func.__name__,
        )

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await stack.execute(func, *args, **kwargs)

        return async_wrapper

    return decorator
