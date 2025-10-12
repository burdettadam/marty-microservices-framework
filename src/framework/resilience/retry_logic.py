"""
Retry Logic Implementation for Marty Microservices Framework

This module implements retry patterns and backoff strategies
for resilient microservices communication.
"""

import asyncio
import builtins
import logging
import random
import time
from collections.abc import Callable
from enum import Enum
from functools import wraps
from typing import TypeVar


class RetryStrategy(Enum):
    """Retry strategy types."""

    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    RANDOM_JITTER = "random_jitter"


T = TypeVar("T")


class RetryConfig:
    """Configuration for retry logic."""

    def __init__(
        self,
        max_attempts: int = 3,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_multiplier: float = 2.0,
        jitter_range: float = 0.1,
        retryable_exceptions: builtins.list[type] | None = None,
        non_retryable_exceptions: builtins.list[type] | None = None,
    ):
        """Initialize retry configuration."""
        self.max_attempts = max_attempts
        self.strategy = strategy
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.jitter_range = jitter_range
        self.retryable_exceptions = retryable_exceptions or [Exception]
        self.non_retryable_exceptions = non_retryable_exceptions or []


class RetryMechanism:
    """Retry mechanism with configurable strategies."""

    def __init__(self, name: str, config: RetryConfig):
        """Initialize retry mechanism."""
        self.name = name
        self.config = config

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator for retry mechanism."""

        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return self.execute(lambda: func(*args, **kwargs))

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            return await self.execute_async(lambda: func(*args, **kwargs))

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return wrapper

    def execute(self, operation: Callable[[], T]) -> T:
        """Execute operation with retry logic."""
        last_exception = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                result = operation()
                if attempt > 1:
                    logging.info(
                        "Retry %s succeeded on attempt %d/%d",
                        self.name,
                        attempt,
                        self.config.max_attempts,
                    )
                return result

            except Exception as e:
                last_exception = e

                # Check if exception is retryable
                if not self._is_retryable_exception(e):
                    logging.warning("Non-retryable exception in %s: %s", self.name, str(e))
                    raise

                if attempt < self.config.max_attempts:
                    delay = self._calculate_delay(attempt)
                    logging.warning(
                        "Retry %s failed (attempt %d/%d), retrying in %.2fs: %s",
                        self.name,
                        attempt,
                        self.config.max_attempts,
                        delay,
                        str(e),
                    )
                    time.sleep(delay)
                else:
                    logging.error(
                        "Retry %s exhausted all attempts (%d/%d): %s",
                        self.name,
                        attempt,
                        self.config.max_attempts,
                        str(e),
                    )

        # All attempts failed
        if last_exception:
            raise last_exception
        raise RuntimeError(f"Retry {self.name} failed without capturing exception")

    async def execute_async(self, operation: Callable[[], T]) -> T:
        """Execute async operation with retry logic."""
        last_exception = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                if asyncio.iscoroutinefunction(operation):
                    result = await operation()
                else:
                    result = operation()

                if attempt > 1:
                    logging.info(
                        "Async retry %s succeeded on attempt %d/%d",
                        self.name,
                        attempt,
                        self.config.max_attempts,
                    )
                return result

            except Exception as e:
                last_exception = e

                # Check if exception is retryable
                if not self._is_retryable_exception(e):
                    logging.warning("Non-retryable exception in async %s: %s", self.name, str(e))
                    raise

                if attempt < self.config.max_attempts:
                    delay = self._calculate_delay(attempt)
                    logging.warning(
                        "Async retry %s failed (attempt %d/%d), retrying in %.2fs: %s",
                        self.name,
                        attempt,
                        self.config.max_attempts,
                        delay,
                        str(e),
                    )
                    await asyncio.sleep(delay)
                else:
                    logging.error(
                        "Async retry %s exhausted all attempts (%d/%d): %s",
                        self.name,
                        attempt,
                        self.config.max_attempts,
                        str(e),
                    )

        # All attempts failed
        if last_exception:
            raise last_exception
        raise RuntimeError(f"Async retry {self.name} failed without capturing exception")

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
        """Calculate retry delay based on strategy."""
        strategy = self.config.strategy

        if strategy == RetryStrategy.FIXED_DELAY:
            delay = self.config.base_delay

        elif strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.config.base_delay * (self.config.backoff_multiplier ** (attempt - 1))

        elif strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.base_delay * attempt

        elif strategy == RetryStrategy.RANDOM_JITTER:
            delay = self.config.base_delay + random.uniform(
                -self.config.jitter_range, self.config.jitter_range
            )

        else:
            delay = self.config.base_delay

        # Apply jitter for exponential and linear backoff
        if strategy in [RetryStrategy.EXPONENTIAL_BACKOFF, RetryStrategy.LINEAR_BACKOFF]:
            jitter = delay * self.config.jitter_range * random.uniform(-1, 1)
            delay += jitter

        # Ensure delay is within bounds
        delay = max(0, min(delay, self.config.max_delay))

        return delay

    def get_config(self) -> RetryConfig:
        """Get retry configuration."""
        return self.config


# Utility functions for common retry patterns
def with_retry(
    max_attempts: int = 3,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator factory for retry logic."""
    config = RetryConfig(
        max_attempts=max_attempts,
        strategy=strategy,
        base_delay=base_delay,
        max_delay=max_delay,
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        retry_mechanism = RetryMechanism(func.__name__, config)
        return retry_mechanism(func)

    return decorator


def create_retry_config(
    max_attempts: int = 3,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: builtins.list[type] | None = None,
) -> RetryConfig:
    """Create a retry configuration with common defaults."""
    return RetryConfig(
        max_attempts=max_attempts,
        strategy=strategy,
        base_delay=base_delay,
        max_delay=max_delay,
        retryable_exceptions=retryable_exceptions or [ConnectionError, TimeoutError],
    )
