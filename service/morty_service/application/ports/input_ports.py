"""
Input ports (interfaces) for the application layer.

These interfaces define the contracts that external adapters (HTTP, gRPC, etc.)
must implement to interact with the application's use cases.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID


# Data Transfer Objects (DTOs) for input/output
@dataclass
class CreateTaskCommand:
    """Command for creating a new task."""

    title: str
    description: str
    priority: str = "medium"
    assignee_id: Optional[UUID] = None


@dataclass
class UpdateTaskCommand:
    """Command for updating an existing task."""

    task_id: UUID
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None


@dataclass
class AssignTaskCommand:
    """Command for assigning a task to a user."""

    task_id: UUID
    assignee_id: UUID


@dataclass
class CreateUserCommand:
    """Command for creating a new user."""

    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None


@dataclass
class TaskDTO:
    """Data Transfer Object for task information."""

    id: UUID
    title: str
    description: str
    priority: str
    status: str
    assignee_id: Optional[UUID]
    assignee_name: Optional[str]
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None


@dataclass
class UserDTO:
    """Data Transfer Object for user information."""

    id: UUID
    first_name: str
    last_name: str
    email: str
    phone: Optional[str]
    active: bool
    pending_task_count: int
    completed_task_count: int
    created_at: str
    updated_at: str


@dataclass
class UserWorkloadDTO:
    """Data Transfer Object for user workload information."""

    user_id: UUID
    pending_task_count: int
    completed_task_count: int
    workload_score: int
    is_overloaded: bool
    priority_distribution: dict


# Input Port Interfaces
class TaskManagementPort(ABC):
    """Input port for task management operations."""

    @abstractmethod
    async def create_task(self, command: CreateTaskCommand) -> TaskDTO:
        """Create a new task."""
        ...

    @abstractmethod
    async def update_task(self, command: UpdateTaskCommand) -> TaskDTO:
        """Update an existing task."""
        ...

    @abstractmethod
    async def assign_task(self, command: AssignTaskCommand) -> TaskDTO:
        """Assign a task to a user."""
        ...

    @abstractmethod
    async def complete_task(self, task_id: UUID) -> TaskDTO:
        """Mark a task as completed."""
        ...

    @abstractmethod
    async def get_task(self, task_id: UUID) -> Optional[TaskDTO]:
        """Get a task by its ID."""
        ...

    @abstractmethod
    async def get_tasks_by_assignee(self, user_id: UUID) -> List[TaskDTO]:
        """Get all tasks assigned to a specific user."""
        ...

    @abstractmethod
    async def get_tasks_by_status(self, status: str) -> List[TaskDTO]:
        """Get all tasks with a specific status."""
        ...

    @abstractmethod
    async def get_all_tasks(
        self, limit: Optional[int] = None, offset: int = 0
    ) -> List[TaskDTO]:
        """Get all tasks with optional pagination."""
        ...

    @abstractmethod
    async def delete_task(self, task_id: UUID) -> bool:
        """Delete a task by its ID."""
        ...


class UserManagementPort(ABC):
    """Input port for user management operations."""

    @abstractmethod
    async def create_user(self, command: CreateUserCommand) -> UserDTO:
        """Create a new user."""
        pass

    @abstractmethod
    async def get_user(self, user_id: UUID) -> Optional[UserDTO]:
        """Get a user by their ID."""
        pass

    @abstractmethod
    async def get_user_by_email(self, email: str) -> Optional[UserDTO]:
        """Get a user by their email address."""
        pass

    @abstractmethod
    async def get_all_users(
        self, limit: Optional[int] = None, offset: int = 0
    ) -> List[UserDTO]:
        """Get all users with optional pagination."""
        pass

    @abstractmethod
    async def activate_user(self, user_id: UUID) -> UserDTO:
        """Activate a user."""
        pass

    @abstractmethod
    async def deactivate_user(self, user_id: UUID) -> UserDTO:
        """Deactivate a user."""
        pass

    @abstractmethod
    async def get_user_workload(self, user_id: UUID) -> UserWorkloadDTO:
        """Get workload information for a user."""
        pass

    @abstractmethod
    async def find_best_assignee(self, task_priority: str) -> Optional[UserDTO]:
        """Find the best user to assign a task to."""
        pass

    @abstractmethod
    async def delete_user(self, user_id: UUID) -> bool:
        """Delete a user by their ID."""
        pass


class HealthCheckPort(ABC):
    """Input port for health check operations."""

    @abstractmethod
    async def check_health(self) -> dict:
        """Perform a health check of the service."""
        pass

    @abstractmethod
    async def check_readiness(self) -> dict:
        """Check if the service is ready to serve requests."""
        pass
