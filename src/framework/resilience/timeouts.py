"""
Timeout patterns implementation for preventing resource exhaustion and deadlocks.

This module provides configurable timeout mechanisms for various operations
including async/await, thread-based operations, and HTTP requests.
"""

import asyncio
import functools
import logging
import signal
import threading
import time
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


class TimeoutType(Enum):
    """Types of timeout mechanisms."""

    ASYNC = "async"
    THREAD = "thread"
    SIGNAL = "signal"
    FUTURE = "future"


class TimeoutAction(Enum):
    """Actions to take when timeout occurs."""

    RAISE_EXCEPTION = "raise_exception"
    RETURN_DEFAULT = "return_default"
    LOG_WARNING = "log_warning"
    CANCEL_OPERATION = "cancel_operation"


@dataclass
class TimeoutConfig:
    """Configuration for timeout operations."""

    name: str
    timeout_seconds: float
    timeout_type: TimeoutType = TimeoutType.ASYNC
    action: TimeoutAction = TimeoutAction.RAISE_EXCEPTION
    default_value: Any = None
    retry_count: int = 0
    retry_delay: float = 1.0
    enable_logging: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TimeoutMetrics:
    """Metrics for timeout monitoring."""

    total_operations: int = 0
    successful_operations: int = 0
    timeout_operations: int = 0
    average_execution_time: float = 0.0
    max_execution_time: float = 0.0
    min_execution_time: float = float("inf")


class TimeoutException(Exception):
    """Exception raised when an operation times out."""

    def __init__(self, message: str, timeout_seconds: float, operation_name: str = ""):
        super().__init__(message)
        self.timeout_seconds = timeout_seconds
        self.operation_name = operation_name


class AsyncTimeoutManager:
    """Manager for async operation timeouts."""

    def __init__(self, config: TimeoutConfig):
        self.config = config
        self.metrics = TimeoutMetrics()
        self._lock = threading.Lock()

    async def execute(self, coro: Awaitable[T], timeout: float | None = None) -> T:
        """Execute an async operation with timeout."""
        timeout_value = timeout or self.config.timeout_seconds
        start_time = time.time()

        try:
            result = await asyncio.wait_for(coro, timeout=timeout_value)
            execution_time = time.time() - start_time
            self._update_metrics(True, execution_time)
            return result

        except asyncio.TimeoutError as e:
            execution_time = time.time() - start_time
            self._update_metrics(False, execution_time)

            if self.config.action == TimeoutAction.RAISE_EXCEPTION:
                raise TimeoutException(
                    f"Operation timed out after {timeout_value} seconds",
                    timeout_value,
                    self.config.name,
                ) from e
            elif self.config.action == TimeoutAction.RETURN_DEFAULT:
                if self.config.enable_logging:
                    logger.warning(
                        f"Operation {self.config.name} timed out, returning default value"
                    )
                return self.config.default_value
            elif self.config.action == TimeoutAction.LOG_WARNING:
                logger.warning(
                    f"Operation {self.config.name} timed out after {timeout_value} seconds"
                )
                raise TimeoutException(
                    f"Operation timed out after {timeout_value} seconds",
                    timeout_value,
                    self.config.name,
                ) from e

    def _update_metrics(self, success: bool, execution_time: float) -> None:
        """Update timeout metrics."""
        with self._lock:
            self.metrics.total_operations += 1

            if success:
                self.metrics.successful_operations += 1
            else:
                self.metrics.timeout_operations += 1

            # Update timing metrics
            alpha = 0.1
            self.metrics.average_execution_time = (
                alpha * execution_time + (1 - alpha) * self.metrics.average_execution_time
            )

            self.metrics.max_execution_time = max(self.metrics.max_execution_time, execution_time)

            if execution_time < self.metrics.min_execution_time:
                self.metrics.min_execution_time = execution_time


class ThreadTimeoutManager:
    """Manager for thread-based operation timeouts."""

    def __init__(self, config: TimeoutConfig):
        self.config = config
        self.metrics = TimeoutMetrics()
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._lock = threading.Lock()

    def execute(self, func: Callable[..., T], *args, timeout: float | None = None, **kwargs) -> T:
        """Execute a function with timeout in a separate thread."""
        timeout_value = timeout or self.config.timeout_seconds
        start_time = time.time()

        try:
            future = self._executor.submit(func, *args, **kwargs)
            result = future.result(timeout=timeout_value)
            execution_time = time.time() - start_time
            self._update_metrics(True, execution_time)
            return result

        except FutureTimeoutError as e:
            execution_time = time.time() - start_time
            self._update_metrics(False, execution_time)

            if self.config.action == TimeoutAction.RAISE_EXCEPTION:
                raise TimeoutException(
                    f"Operation timed out after {timeout_value} seconds",
                    timeout_value,
                    self.config.name,
                ) from e
            elif self.config.action == TimeoutAction.RETURN_DEFAULT:
                if self.config.enable_logging:
                    logger.warning(
                        f"Operation {self.config.name} timed out, returning default value"
                    )
                return self.config.default_value

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the thread pool executor."""
        self._executor.shutdown(wait=wait)

    def _update_metrics(self, success: bool, execution_time: float) -> None:
        """Update timeout metrics."""
        with self._lock:
            self.metrics.total_operations += 1

            if success:
                self.metrics.successful_operations += 1
            else:
                self.metrics.timeout_operations += 1

            # Update timing metrics
            alpha = 0.1
            self.metrics.average_execution_time = (
                alpha * execution_time + (1 - alpha) * self.metrics.average_execution_time
            )

            self.metrics.max_execution_time = max(self.metrics.max_execution_time, execution_time)

            if execution_time < self.metrics.min_execution_time:
                self.metrics.min_execution_time = execution_time


class SignalTimeoutManager:
    """Manager for signal-based operation timeouts (UNIX only)."""

    def __init__(self, config: TimeoutConfig):
        self.config = config
        self.metrics = TimeoutMetrics()
        self._lock = threading.Lock()
        self._original_handler = None

    def execute(self, func: Callable[..., T], *args, timeout: float | None = None, **kwargs) -> T:
        """Execute a function with signal-based timeout."""
        timeout_value = timeout or self.config.timeout_seconds
        start_time = time.time()

        def timeout_handler(signum, frame):
            raise TimeoutException(
                f"Operation timed out after {timeout_value} seconds",
                timeout_value,
                self.config.name,
            )

        # Set up signal handler
        self._original_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(timeout_value))

        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            self._update_metrics(True, execution_time)
            return result

        except TimeoutException:
            execution_time = time.time() - start_time
            self._update_metrics(False, execution_time)

            if self.config.action == TimeoutAction.RETURN_DEFAULT:
                if self.config.enable_logging:
                    logger.warning(
                        f"Operation {self.config.name} timed out, returning default value"
                    )
                return self.config.default_value
            raise

        finally:
            # Clean up signal handler
            signal.alarm(0)
            if self._original_handler:
                signal.signal(signal.SIGALRM, self._original_handler)

    def _update_metrics(self, success: bool, execution_time: float) -> None:
        """Update timeout metrics."""
        with self._lock:
            self.metrics.total_operations += 1

            if success:
                self.metrics.successful_operations += 1
            else:
                self.metrics.timeout_operations += 1


class TimeoutManager:
    """Unified timeout manager supporting multiple timeout mechanisms."""

    def __init__(self):
        self._managers: dict[
            str, AsyncTimeoutManager | ThreadTimeoutManager | SignalTimeoutManager
        ] = {}
        self._lock = threading.Lock()

    def register_config(self, config: TimeoutConfig) -> None:
        """Register a timeout configuration."""
        with self._lock:
            if config.timeout_type == TimeoutType.ASYNC:
                manager = AsyncTimeoutManager(config)
            elif config.timeout_type == TimeoutType.THREAD:
                manager = ThreadTimeoutManager(config)
            elif config.timeout_type == TimeoutType.SIGNAL:
                manager = SignalTimeoutManager(config)
            else:
                raise ValueError(f"Unsupported timeout type: {config.timeout_type}")

            self._managers[config.name] = manager

    def get_manager(self, name: str) -> Any:
        """Get a timeout manager by name."""
        with self._lock:
            return self._managers.get(name)

    def get_all_metrics(self) -> dict[str, TimeoutMetrics]:
        """Get metrics for all timeout managers."""
        with self._lock:
            return {name: manager.metrics for name, manager in self._managers.items()}

    def shutdown(self) -> None:
        """Shutdown all timeout managers."""
        with self._lock:
            for manager in self._managers.values():
                if hasattr(manager, "shutdown"):
                    manager.shutdown()


# Decorators for timeout protection
def with_async_timeout(
    timeout_seconds: float,
    action: TimeoutAction = TimeoutAction.RAISE_EXCEPTION,
    default_value: Any = None,
):
    """Decorator for async functions with timeout protection."""

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            config = TimeoutConfig(
                name=func.__name__,
                timeout_seconds=timeout_seconds,
                timeout_type=TimeoutType.ASYNC,
                action=action,
                default_value=default_value,
            )
            manager = AsyncTimeoutManager(config)
            return await manager.execute(func(*args, **kwargs))

        return wrapper

    return decorator


def with_thread_timeout(
    timeout_seconds: float,
    action: TimeoutAction = TimeoutAction.RAISE_EXCEPTION,
    default_value: Any = None,
):
    """Decorator for sync functions with thread-based timeout protection."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            config = TimeoutConfig(
                name=func.__name__,
                timeout_seconds=timeout_seconds,
                timeout_type=TimeoutType.THREAD,
                action=action,
                default_value=default_value,
            )
            manager = ThreadTimeoutManager(config)
            return manager.execute(func, *args, **kwargs)

        return wrapper

    return decorator


# Global timeout manager instance
default_timeout_manager = TimeoutManager()


def create_async_timeout_manager(name: str, timeout_seconds: float) -> AsyncTimeoutManager:
    """Create and register an async timeout manager."""
    config = TimeoutConfig(
        name=name, timeout_seconds=timeout_seconds, timeout_type=TimeoutType.ASYNC
    )
    default_timeout_manager.register_config(config)
    return default_timeout_manager.get_manager(name)


def create_thread_timeout_manager(name: str, timeout_seconds: float) -> ThreadTimeoutManager:
    """Create and register a thread timeout manager."""
    config = TimeoutConfig(
        name=name, timeout_seconds=timeout_seconds, timeout_type=TimeoutType.THREAD
    )
    default_timeout_manager.register_config(config)
    return default_timeout_manager.get_manager(name)
