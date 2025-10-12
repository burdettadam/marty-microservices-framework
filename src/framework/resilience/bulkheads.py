"""
Bulkhead pattern implementation for resource isolation and fault containment.

The bulkhead pattern isolates critical resources to prevent cascading failures
by separating thread pools, connection pools, and other shared resources.
"""

import asyncio
import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

T = TypeVar('T')

logger = logging.getLogger(__name__)


class BulkheadType(Enum):
    """Types of bulkhead isolation patterns."""
    THREAD_POOL = "thread_pool"
    CONNECTION_POOL = "connection_pool"
    CIRCUIT_BREAKER = "circuit_breaker"
    QUEUE = "queue"
    SEMAPHORE = "semaphore"


class ResourceStatus(Enum):
    """Status of a bulkhead resource."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    ISOLATED = "isolated"


@dataclass
class BulkheadConfig:
    """Configuration for bulkhead isolation."""
    name: str
    bulkhead_type: BulkheadType
    max_concurrent: int = 10
    max_queue_size: int = 100
    timeout_seconds: float = 30.0
    isolation_threshold: int = 5
    recovery_time_seconds: float = 60.0
    enable_monitoring: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BulkheadMetrics:
    """Metrics for bulkhead monitoring."""
    total_requests: int = 0
    active_requests: int = 0
    queued_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rejected_requests: int = 0
    average_response_time: float = 0.0
    last_failure_time: float | None = None
    consecutive_failures: int = 0


class ResourcePool:
    """Base class for resource pools with bulkhead isolation."""

    def __init__(self, config: BulkheadConfig):
        self.config = config
        self.status = ResourceStatus.HEALTHY
        self.metrics = BulkheadMetrics()
        self._lock = threading.RLock()
        self._last_health_check = time.time()

    def acquire(self, timeout: float | None = None) -> bool:
        """Acquire a resource from the pool."""
        raise NotImplementedError

    def release(self) -> None:
        """Release a resource back to the pool."""
        raise NotImplementedError

    def is_healthy(self) -> bool:
        """Check if the resource pool is healthy."""
        with self._lock:
            if self.metrics.consecutive_failures >= self.config.isolation_threshold:
                return False
            return self.status in [ResourceStatus.HEALTHY, ResourceStatus.DEGRADED]

    def update_metrics(self, success: bool, response_time: float) -> None:
        """Update pool metrics."""
        with self._lock:
            self.metrics.total_requests += 1

            if success:
                self.metrics.successful_requests += 1
                self.metrics.consecutive_failures = 0
            else:
                self.metrics.failed_requests += 1
                self.metrics.consecutive_failures += 1
                self.metrics.last_failure_time = time.time()

            # Update average response time using exponential moving average
            alpha = 0.1
            self.metrics.average_response_time = (
                alpha * response_time +
                (1 - alpha) * self.metrics.average_response_time
            )


class ThreadPoolBulkhead(ResourcePool):
    """Thread pool bulkhead for isolating CPU-bound operations."""

    def __init__(self, config: BulkheadConfig):
        super().__init__(config)
        self._executor = ThreadPoolExecutor(
            max_workers=config.max_concurrent,
            thread_name_prefix=f"bulkhead-{config.name}"
        )
        self._active_futures: dict[str, Future] = {}

    def submit(self, fn: Callable[..., T], *args, **kwargs) -> Future[T]:
        """Submit a task to the thread pool bulkhead."""
        if not self.is_healthy():
            raise RuntimeError(f"Bulkhead {self.config.name} is not healthy")

        future = self._executor.submit(fn, *args, **kwargs)
        future_id = str(id(future))

        with self._lock:
            self._active_futures[future_id] = future
            self.metrics.active_requests += 1

        def cleanup_future():
            with self._lock:
                self._active_futures.pop(future_id, None)
                self.metrics.active_requests -= 1

        future.add_done_callback(lambda f: cleanup_future())
        return future

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the thread pool."""
        self._executor.shutdown(wait=wait)

    def acquire(self, timeout: float | None = None) -> bool:
        """Check if resources are available."""
        with self._lock:
            return len(self._active_futures) < self.config.max_concurrent

    def release(self) -> None:
        """Release is handled automatically by future completion."""
        pass


class SemaphoreBulkhead(ResourcePool):
    """Semaphore-based bulkhead for limiting concurrent operations."""

    def __init__(self, config: BulkheadConfig):
        super().__init__(config)
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
        self._async_semaphore = threading.Semaphore(config.max_concurrent)

    async def acquire_async(self, timeout: float | None = None) -> bool:
        """Acquire semaphore asynchronously."""
        try:
            if timeout:
                await asyncio.wait_for(
                    self._semaphore.acquire(),
                    timeout=timeout
                )
            else:
                await self._semaphore.acquire()

            with self._lock:
                self.metrics.active_requests += 1
            return True

        except asyncio.TimeoutError:
            with self._lock:
                self.metrics.rejected_requests += 1
            return False

    def release_async(self) -> None:
        """Release semaphore asynchronously."""
        self._semaphore.release()
        with self._lock:
            self.metrics.active_requests -= 1

    def acquire(self, timeout: float | None = None) -> bool:
        """Acquire semaphore synchronously."""
        acquired = self._async_semaphore.acquire(timeout=timeout)
        if acquired:
            with self._lock:
                self.metrics.active_requests += 1
        else:
            with self._lock:
                self.metrics.rejected_requests += 1
        return acquired

    def release(self) -> None:
        """Release semaphore synchronously."""
        self._async_semaphore.release()
        with self._lock:
            self.metrics.active_requests -= 1


class BulkheadManager:
    """Manager for multiple bulkhead instances."""

    def __init__(self):
        self._bulkheads: dict[str, ResourcePool] = {}
        self._lock = threading.RLock()

    def register_bulkhead(self, bulkhead: ResourcePool) -> None:
        """Register a bulkhead instance."""
        with self._lock:
            self._bulkheads[bulkhead.config.name] = bulkhead

    def get_bulkhead(self, name: str) -> ResourcePool | None:
        """Get a bulkhead by name."""
        with self._lock:
            return self._bulkheads.get(name)

    def get_all_metrics(self) -> dict[str, BulkheadMetrics]:
        """Get metrics for all bulkheads."""
        with self._lock:
            return {
                name: bulkhead.metrics
                for name, bulkhead in self._bulkheads.items()
            }

    def health_check(self) -> dict[str, bool]:
        """Perform health check on all bulkheads."""
        with self._lock:
            return {
                name: bulkhead.is_healthy()
                for name, bulkhead in self._bulkheads.items()
            }


# Decorator for automatic bulkhead protection
def with_bulkhead(bulkhead_name: str, manager: BulkheadManager):
    """Decorator to protect function calls with bulkhead pattern."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            bulkhead = manager.get_bulkhead(bulkhead_name)
            if not bulkhead:
                raise ValueError(f"Bulkhead {bulkhead_name} not found")

            if not bulkhead.is_healthy():
                raise RuntimeError(f"Bulkhead {bulkhead_name} is not healthy")

            start_time = time.time()
            try:
                if not bulkhead.acquire(timeout=bulkhead.config.timeout_seconds):
                    raise RuntimeError(f"Bulkhead {bulkhead_name} capacity exceeded")

                result = func(*args, **kwargs)
                response_time = time.time() - start_time
                bulkhead.update_metrics(True, response_time)
                return result

            except Exception:
                response_time = time.time() - start_time
                bulkhead.update_metrics(False, response_time)
                raise
            finally:
                bulkhead.release()

        return wrapper
    return decorator


# Global bulkhead manager instance
default_bulkhead_manager = BulkheadManager()


def create_thread_pool_bulkhead(name: str, max_workers: int = 10) -> ThreadPoolBulkhead:
    """Create and register a thread pool bulkhead."""
    config = BulkheadConfig(
        name=name,
        bulkhead_type=BulkheadType.THREAD_POOL,
        max_concurrent=max_workers
    )
    bulkhead = ThreadPoolBulkhead(config)
    default_bulkhead_manager.register_bulkhead(bulkhead)
    return bulkhead


def create_semaphore_bulkhead(name: str, max_concurrent: int = 10) -> SemaphoreBulkhead:
    """Create and register a semaphore bulkhead."""
    config = BulkheadConfig(
        name=name,
        bulkhead_type=BulkheadType.SEMAPHORE,
        max_concurrent=max_concurrent
    )
    bulkhead = SemaphoreBulkhead(config)
    default_bulkhead_manager.register_bulkhead(bulkhead)
    return bulkhead
