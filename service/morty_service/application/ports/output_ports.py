"""
Output ports (interfaces) for external dependencies.

These interfaces define the contracts that infrastructure adapters must implement.
The application layer depends on these abstractions, not on concrete implementations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from ...domain.entities import Task, User
from ...domain.events import DomainEvent


class TaskRepositoryPort(ABC):
    """Port for task persistence operations."""

    @abstractmethod
    async def save(self, task: Task) -> None:
        """Save a task to the repository."""
        pass

    @abstractmethod
    async def find_by_id(self, task_id: UUID) -> Optional[Task]:
        """Find a task by its ID."""
        pass

    @abstractmethod
    async def find_by_assignee(self, user_id: UUID) -> List[Task]:
        """Find all tasks assigned to a specific user."""
        pass

    @abstractmethod
    async def find_by_status(self, status: str) -> List[Task]:
        """Find all tasks with a specific status."""
        pass

    @abstractmethod
    async def find_all(
        self, limit: Optional[int] = None, offset: int = 0
    ) -> List[Task]:
        """Find all tasks with optional pagination."""
        pass

    @abstractmethod
    async def delete(self, task_id: UUID) -> bool:
        """Delete a task by its ID. Returns True if deleted."""
        pass

    @abstractmethod
    async def count_by_user_and_status(self, user_id: UUID, status: str) -> int:
        """Count tasks for a user with a specific status."""
        pass


class UserRepositoryPort(ABC):
    """Port for user persistence operations."""

    @abstractmethod
    async def save(self, user: User) -> None:
        """Save a user to the repository."""
        pass

    @abstractmethod
    async def find_by_id(self, user_id: UUID) -> Optional[User]:
        """Find a user by their ID."""
        pass

    @abstractmethod
    async def find_by_email(self, email: str) -> Optional[User]:
        """Find a user by their email address."""
        pass

    @abstractmethod
    async def find_active_users(self) -> List[User]:
        """Find all active users."""
        pass

    @abstractmethod
    async def find_all(
        self, limit: Optional[int] = None, offset: int = 0
    ) -> List[User]:
        """Find all users with optional pagination."""
        pass

    @abstractmethod
    async def delete(self, user_id: UUID) -> bool:
        """Delete a user by their ID. Returns True if deleted."""
        pass


class EventPublisherPort(ABC):
    """Port for publishing domain events."""

    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """Publish a single domain event."""
        pass

    @abstractmethod
    async def publish_batch(self, events: List[DomainEvent]) -> None:
        """Publish multiple domain events as a batch."""
        pass


class NotificationPort(ABC):
    """Port for sending notifications."""

    @abstractmethod
    async def send_task_assigned_notification(
        self, user_email: str, task_title: str, task_id: UUID
    ) -> None:
        """Send notification when a task is assigned."""
        pass

    @abstractmethod
    async def send_task_completed_notification(
        self, user_email: str, task_title: str, task_id: UUID
    ) -> None:
        """Send notification when a task is completed."""
        pass

    @abstractmethod
    async def send_user_workload_alert(
        self, user_email: str, pending_task_count: int
    ) -> None:
        """Send alert when user workload is high."""
        pass


class CachePort(ABC):
    """Port for caching operations."""

    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        """Get a value from cache."""
        pass

    @abstractmethod
    async def set(
        self, key: str, value: str, ttl_seconds: Optional[int] = None
    ) -> None:
        """Set a value in cache with optional TTL."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a value from cache."""
        pass

    @abstractmethod
    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate all cache keys matching a pattern."""
        pass


class UnitOfWorkPort(ABC):
    """Port for managing database transactions."""

    @abstractmethod
    async def __aenter__(self):
        """Enter the transaction context."""
        pass

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the transaction context, rolling back on error."""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commit the current transaction."""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the current transaction."""
        pass
