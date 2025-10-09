"""
Health check system for the Marty Chassis.

This module provides:
- Comprehensive health check framework
- Built-in health checks for common dependencies
- Health status aggregation and reporting
- Integration with FastAPI health endpoints
"""

import asyncio
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel

from ..exceptions import HealthCheckError
from ..logger import get_logger

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """Health check status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheckResult(BaseModel):
    """Result of a health check."""

    name: str
    status: HealthStatus
    message: str
    details: Dict[str, Any] = {}
    duration_ms: float
    timestamp: float


class HealthCheck(ABC):
    """Abstract base class for health checks."""

    def __init__(self, name: str, timeout: float = 5.0):
        self.name = name
        self.timeout = timeout

    @abstractmethod
    async def check(self) -> HealthCheckResult:
        """Perform the health check."""
        pass

    async def run_check(self) -> HealthCheckResult:
        """Run the health check with timeout and error handling."""
        start_time = time.time()

        try:
            result = await asyncio.wait_for(self.check(), timeout=self.timeout)
            result.duration_ms = (time.time() - start_time) * 1000
            result.timestamp = time.time()
            return result
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            logger.warning(
                f"Health check '{self.name}' timed out", duration_ms=duration_ms
            )
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check timed out after {self.timeout}s",
                duration_ms=duration_ms,
                timestamp=time.time(),
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Health check '{self.name}' failed",
                error=str(e),
                duration_ms=duration_ms,
            )
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {e}",
                details={"error": str(e)},
                duration_ms=duration_ms,
                timestamp=time.time(),
            )


class DatabaseHealthCheck(HealthCheck):
    """Health check for database connectivity."""

    def __init__(
        self, name: str = "database", database_url: str = "", timeout: float = 5.0
    ):
        super().__init__(name, timeout)
        self.database_url = database_url

    async def check(self) -> HealthCheckResult:
        """Check database connectivity."""
        # This is a simple example - in practice, you'd use your actual DB client
        try:
            # Simulate database ping
            await asyncio.sleep(0.1)  # Simulate DB query time

            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message="Database connection is healthy",
                details={
                    "database_url": self.database_url.split("@")[-1]
                    if "@" in self.database_url
                    else ""
                },
                duration_ms=0,  # Will be set by run_check
                timestamp=0,  # Will be set by run_check
            )
        except Exception as e:
            raise HealthCheckError(f"Database health check failed: {e}")


class HTTPHealthCheck(HealthCheck):
    """Health check for HTTP dependencies."""

    def __init__(
        self, name: str, url: str, timeout: float = 5.0, expected_status: int = 200
    ):
        super().__init__(name, timeout)
        self.url = url
        self.expected_status = expected_status

    async def check(self) -> HealthCheckResult:
        """Check HTTP endpoint availability."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(self.url, timeout=self.timeout)

                if response.status_code == self.expected_status:
                    return HealthCheckResult(
                        name=self.name,
                        status=HealthStatus.HEALTHY,
                        message=f"HTTP endpoint is healthy (status: {response.status_code})",
                        details={
                            "url": self.url,
                            "status_code": response.status_code,
                            "response_time_ms": response.elapsed.total_seconds() * 1000,
                        },
                        duration_ms=0,
                        timestamp=0,
                    )
                else:
                    return HealthCheckResult(
                        name=self.name,
                        status=HealthStatus.DEGRADED,
                        message=f"HTTP endpoint returned unexpected status: {response.status_code}",
                        details={
                            "url": self.url,
                            "status_code": response.status_code,
                            "expected_status": self.expected_status,
                        },
                        duration_ms=0,
                        timestamp=0,
                    )
        except Exception as e:
            raise HealthCheckError(f"HTTP health check failed: {e}")


class MemoryHealthCheck(HealthCheck):
    """Health check for memory usage."""

    def __init__(
        self,
        name: str = "memory",
        warning_threshold: float = 0.8,
        critical_threshold: float = 0.9,
    ):
        super().__init__(name)
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    async def check(self) -> HealthCheckResult:
        """Check memory usage."""
        try:
            import psutil

            memory = psutil.virtual_memory()
            usage_percent = memory.percent / 100.0

            if usage_percent >= self.critical_threshold:
                status = HealthStatus.UNHEALTHY
                message = f"Critical memory usage: {usage_percent:.1%}"
            elif usage_percent >= self.warning_threshold:
                status = HealthStatus.DEGRADED
                message = f"High memory usage: {usage_percent:.1%}"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage is normal: {usage_percent:.1%}"

            return HealthCheckResult(
                name=self.name,
                status=status,
                message=message,
                details={
                    "usage_percent": usage_percent,
                    "total_bytes": memory.total,
                    "available_bytes": memory.available,
                    "used_bytes": memory.used,
                },
                duration_ms=0,
                timestamp=0,
            )
        except ImportError:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.DEGRADED,
                message="psutil not available, cannot check memory",
                duration_ms=0,
                timestamp=0,
            )
        except Exception as e:
            raise HealthCheckError(f"Memory health check failed: {e}")


class DiskHealthCheck(HealthCheck):
    """Health check for disk usage."""

    def __init__(
        self,
        name: str = "disk",
        path: str = "/",
        warning_threshold: float = 0.8,
        critical_threshold: float = 0.9,
    ):
        super().__init__(name)
        self.path = path
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    async def check(self) -> HealthCheckResult:
        """Check disk usage."""
        try:
            import psutil

            disk = psutil.disk_usage(self.path)
            usage_percent = disk.used / disk.total

            if usage_percent >= self.critical_threshold:
                status = HealthStatus.UNHEALTHY
                message = f"Critical disk usage: {usage_percent:.1%}"
            elif usage_percent >= self.warning_threshold:
                status = HealthStatus.DEGRADED
                message = f"High disk usage: {usage_percent:.1%}"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk usage is normal: {usage_percent:.1%}"

            return HealthCheckResult(
                name=self.name,
                status=status,
                message=message,
                details={
                    "path": self.path,
                    "usage_percent": usage_percent,
                    "total_bytes": disk.total,
                    "free_bytes": disk.free,
                    "used_bytes": disk.used,
                },
                duration_ms=0,
                timestamp=0,
            )
        except ImportError:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.DEGRADED,
                message="psutil not available, cannot check disk",
                duration_ms=0,
                timestamp=0,
            )
        except Exception as e:
            raise HealthCheckError(f"Disk health check failed: {e}")


class HealthManager:
    """Manager for running and aggregating health checks."""

    def __init__(self):
        self.checks: List[HealthCheck] = []

    def add_check(self, check: HealthCheck) -> None:
        """Add a health check."""
        self.checks.append(check)
        logger.info(f"Added health check: {check.name}")

    def remove_check(self, name: str) -> None:
        """Remove a health check by name."""
        self.checks = [check for check in self.checks if check.name != name]
        logger.info(f"Removed health check: {name}")

    async def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all health checks concurrently."""
        if not self.checks:
            return {}

        logger.debug(f"Running {len(self.checks)} health checks")

        tasks = [check.run_check() for check in self.checks]
        results = await asyncio.gather(*tasks)

        return {result.name: result for result in results}

    async def get_health_status(self) -> Dict[str, Any]:
        """Get aggregated health status."""
        results = await self.run_all_checks()

        if not results:
            return {
                "status": HealthStatus.HEALTHY,
                "message": "No health checks configured",
                "checks": {},
                "timestamp": time.time(),
            }

        # Determine overall status
        statuses = [result.status for result in results.values()]

        if HealthStatus.UNHEALTHY in statuses:
            overall_status = HealthStatus.UNHEALTHY
            message = "One or more health checks are unhealthy"
        elif HealthStatus.DEGRADED in statuses:
            overall_status = HealthStatus.DEGRADED
            message = "One or more health checks are degraded"
        else:
            overall_status = HealthStatus.HEALTHY
            message = "All health checks are healthy"

        return {
            "status": overall_status,
            "message": message,
            "checks": {name: result.dict() for name, result in results.items()},
            "timestamp": time.time(),
        }

    async def get_readiness_status(self) -> Dict[str, Any]:
        """Get readiness status (critical checks only)."""
        # For now, treat all checks as critical
        # In the future, we could add a 'critical' flag to health checks
        return await self.get_health_status()

    async def get_liveness_status(self) -> Dict[str, Any]:
        """Get liveness status (basic service health)."""
        # Simple liveness check - service is running
        return {
            "status": HealthStatus.HEALTHY,
            "message": "Service is alive",
            "timestamp": time.time(),
        }


# Global health manager instance
_global_health_manager: Optional[HealthManager] = None


def get_health_manager() -> HealthManager:
    """Get the global health manager."""
    global _global_health_manager
    if _global_health_manager is None:
        _global_health_manager = HealthManager()
    return _global_health_manager


def setup_default_health_checks(
    database_url: Optional[str] = None,
    external_dependencies: Optional[List[str]] = None,
) -> None:
    """Setup default health checks."""
    manager = get_health_manager()

    # Add memory check
    manager.add_check(MemoryHealthCheck())

    # Add disk check
    manager.add_check(DiskHealthCheck())

    # Add database check if URL provided
    if database_url:
        manager.add_check(DatabaseHealthCheck(database_url=database_url))

    # Add HTTP checks for external dependencies
    if external_dependencies:
        for i, url in enumerate(external_dependencies):
            name = f"dependency_{i+1}"
            manager.add_check(HTTPHealthCheck(name=name, url=url))
