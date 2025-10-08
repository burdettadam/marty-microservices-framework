"""
Enterprise database framework for microservices.

This module provides:
- Database per service isolation
- Repository patterns
- Transaction management
- Connection pooling
- Audit logging capabilities
- Database utilities

Example usage:
    from framework.database import DatabaseConfig, DatabaseManager, Repository

    # Configure database for a service
    config = DatabaseConfig(
        service_name="user-service",
        database="user_db",
        host="localhost",
        port=5432,
        username="user_svc",
        password="password"
    )

    # Create database manager
    db_manager = DatabaseManager(config)
    await db_manager.initialize()

    # Create repository
    user_repository = Repository(db_manager, UserModel)

    # Use repository
    user = await user_repository.create({"name": "John", "email": "john@example.com"})
"""

from .config import ConnectionPoolConfig, DatabaseConfig, DatabaseType
from .manager import (
    ConnectionError,
    DatabaseError,
    DatabaseManager,
    close_all_database_managers,
    create_database_manager,
    get_database_manager,
    health_check_all_databases,
    register_database_manager,
)
from .models import (
    AuditMixin,
    BaseModel,
    FullAuditModel,
    MetadataMixin,
    ServiceAuditLog,
    ServiceConfiguration,
    ServiceHealthCheck,
    SimpleModel,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
)
from .repository import (
    BaseRepository,
    ConflictError,
    NotFoundError,
    Repository,
    RepositoryError,
    ValidationError,
    create_repository,
)
from .transaction import (
    DeadlockError,
    IsolationLevel,
    RetryableError,
    TransactionConfig,
    TransactionError,
    TransactionManager,
    execute_bulk_operations,
    execute_in_transaction,
    execute_with_savepoints,
    handle_database_errors,
    transactional,
)
from .utilities import (
    DatabaseUtilities,
    check_all_database_connections,
    cleanup_all_soft_deleted,
    get_database_utilities,
)

__all__ = [
    # Config
    "DatabaseType",
    "ConnectionPoolConfig",
    "DatabaseConfig",
    # Models
    "BaseModel",
    "TimestampMixin",
    "AuditMixin",
    "SoftDeleteMixin",
    "UUIDMixin",
    "MetadataMixin",
    "FullAuditModel",
    "SimpleModel",
    "ServiceAuditLog",
    "ServiceConfiguration",
    "ServiceHealthCheck",
    # Manager
    "DatabaseManager",
    "DatabaseError",
    "ConnectionError",
    "get_database_manager",
    "create_database_manager",
    "register_database_manager",
    "close_all_database_managers",
    "health_check_all_databases",
    # Repository
    "BaseRepository",
    "Repository",
    "RepositoryError",
    "NotFoundError",
    "ConflictError",
    "ValidationError",
    "create_repository",
    # Transaction
    "IsolationLevel",
    "TransactionConfig",
    "TransactionManager",
    "TransactionError",
    "DeadlockError",
    "RetryableError",
    "transactional",
    "handle_database_errors",
    "execute_in_transaction",
    "execute_bulk_operations",
    "execute_with_savepoints",
    # Utilities
    "DatabaseUtilities",
    "get_database_utilities",
    "check_all_database_connections",
    "cleanup_all_soft_deleted",
]

# Version
__version__ = "1.0.0"
