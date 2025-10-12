"""
Comprehensive example demonstrating the enterprise database framework.

This example shows:
- Database per service configuration
- Repository pattern usage
- Transaction management
- Model definitions with audit capabilities
- Database utilities
"""

import asyncio
import builtins
import logging

from framework.database import (
    AuditMixin,
    BaseModel,
    DatabaseConfig,
    DatabaseManager,
    DatabaseType,
    DatabaseUtilities,
    IsolationLevel,
    Repository,
    SoftDeleteMixin,
    TimestampMixin,
    TransactionConfig,
    transactional,
)
from sqlalchemy import Boolean, Column, Integer, String, Text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Example model with audit capabilities
class User(BaseModel, TimestampMixin, AuditMixin, SoftDeleteMixin):
    """User model with full audit capabilities."""

    __tablename__ = "users"

    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    full_name = Column(String(200))
    is_active = Column(Boolean, default=True)
    bio = Column(Text)


class Post(BaseModel, TimestampMixin, AuditMixin, SoftDeleteMixin):
    """Post model with audit capabilities."""

    __tablename__ = "posts"

    title = Column(String(200), nullable=False)
    content = Column(Text)
    author_id = Column(Integer, nullable=False)  # Foreign key to users
    is_published = Column(Boolean, default=False)


class UserService:
    """Example service using the database framework."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.user_repository = Repository(db_manager, User)
        self.post_repository = Repository(db_manager, Post)
        self.db_utils = DatabaseUtilities(db_manager)

    async def initialize(self):
        """Initialize the service and create tables."""
        await self.db_manager.initialize()
        await self.db_manager.create_tables()
        logger.info("User service initialized")

    @transactional()
    async def create_user(
        self, username: str, email: str, full_name: str, created_by: str = "system"
    ) -> User:
        """Create a new user with transaction management."""
        user_data = {
            "username": username,
            "email": email,
            "full_name": full_name,
            "created_by": created_by,
        }

        user = await self.user_repository.create(user_data)
        logger.info("Created user: %s", user.username)
        return user

    async def get_user_by_username(self, username: str) -> User | None:
        """Get user by username."""
        users = await self.user_repository.find_by_field("username", username)
        return users[0] if users else None

    async def update_user(self, user_id: int, **updates) -> User | None:
        """Update user with audit trail."""
        return await self.user_repository.update(user_id, updates)

    async def delete_user(self, user_id: int, hard_delete: bool = False) -> bool:
        """Delete user (soft delete by default)."""
        return await self.user_repository.delete(user_id, hard_delete=hard_delete)

    async def search_users(
        self, search_term: str, skip: int = 0, limit: int = 10
    ) -> builtins.list[User]:
        """Search users by name or username."""
        return await self.user_repository.search(
            search_term=search_term,
            search_fields=["username", "full_name", "email"],
            skip=skip,
            limit=limit,
        )

    @transactional(config=TransactionConfig(isolation_level=IsolationLevel.REPEATABLE_READ))
    async def create_user_with_post(
        self,
        username: str,
        email: str,
        full_name: str,
        post_title: str,
        post_content: str,
    ) -> tuple[User, Post]:
        """Create user and post in a single transaction."""
        # Create user
        user = await self.create_user(username, email, full_name)

        # Create post for the user
        post_data = {
            "title": post_title,
            "content": post_content,
            "author_id": user.id,
            "created_by": username,
        }

        post = await self.post_repository.create(post_data)

        logger.info("Created user %s with post %s", user.username, post.title)
        return user, post

    async def get_user_posts(self, user_id: int) -> builtins.list[Post]:
        """Get all posts by a user."""
        return await self.post_repository.find_by_field("author_id", user_id)

    async def bulk_create_users(self, users_data: builtins.list[dict]) -> builtins.list[User]:
        """Create multiple users in bulk."""
        return await self.user_repository.bulk_create(users_data)

    async def get_service_stats(self) -> dict:
        """Get service statistics."""
        user_count = await self.user_repository.count()
        post_count = await self.post_repository.count()
        active_users = await self.user_repository.count(is_active=True)

        return {
            "total_users": user_count,
            "active_users": active_users,
            "total_posts": post_count,
            "database_health": await self.db_utils.check_connection(),
        }

    async def cleanup_old_data(self, days: int = 30) -> dict:
        """Clean up old soft-deleted data."""
        cleaned_users = await self.db_utils.clean_soft_deleted(User, days)
        cleaned_posts = await self.db_utils.clean_soft_deleted(Post, days)

        return {"cleaned_users": cleaned_users, "cleaned_posts": cleaned_posts}

    async def close(self):
        """Close database connections."""
        await self.db_manager.close()


async def demonstrate_database_framework():
    """Demonstrate the enterprise database framework."""
    print("=== Enterprise Database Framework Demo ===\n")

    # 1. Configure database for service
    print("1. Configuring database for user-service...")
    config = DatabaseConfig(
        service_name="user-service",
        database="user_service_db",
        db_type=DatabaseType.SQLITE,  # Using SQLite for demo
        host="",  # Not needed for SQLite
        port=0,  # Not needed for SQLite
        username="",  # Not needed for SQLite
        password="",  # Not needed for SQLite
    )
    print(f"   ✓ Configured database: {config.database}")

    # 2. Create service with database manager
    print("\n2. Initializing user service...")
    db_manager = DatabaseManager(config)
    user_service = UserService(db_manager)
    await user_service.initialize()
    print("   ✓ Service initialized with database tables created")

    try:
        # 3. Create users
        print("\n3. Creating users...")
        user1 = await user_service.create_user(
            username="john_doe",
            email="john@example.com",
            full_name="John Doe",
            created_by="admin",
        )
        print(f"   ✓ Created user: {user1.username} (ID: {user1.id})")

        user2 = await user_service.create_user(
            username="jane_smith",
            email="jane@example.com",
            full_name="Jane Smith",
            created_by="admin",
        )
        print(f"   ✓ Created user: {user2.username} (ID: {user2.id})")

        # 4. Create user with post in single transaction
        print("\n4. Creating user with post in transaction...")
        user3, post1 = await user_service.create_user_with_post(
            username="bob_writer",
            email="bob@example.com",
            full_name="Bob Writer",
            post_title="My First Post",
            post_content="This is my first blog post!",
        )
        print(f"   ✓ Created user {user3.username} with post '{post1.title}'")

        # 5. Bulk create users
        print("\n5. Bulk creating users...")
        bulk_users_data = [
            {
                "username": "alice",
                "email": "alice@example.com",
                "full_name": "Alice Wonder",
                "created_by": "system",
            },
            {
                "username": "charlie",
                "email": "charlie@example.com",
                "full_name": "Charlie Brown",
                "created_by": "system",
            },
            {
                "username": "diana",
                "email": "diana@example.com",
                "full_name": "Diana Prince",
                "created_by": "system",
            },
        ]
        bulk_users = await user_service.bulk_create_users(bulk_users_data)
        print(f"   ✓ Bulk created {len(bulk_users)} users")

        # 6. Search users
        print("\n6. Searching users...")
        search_results = await user_service.search_users("john")
        print(f"   ✓ Found {len(search_results)} users matching 'john':")
        for user in search_results:
            print(f"     - {user.username}: {user.full_name}")

        # 7. Update user
        print("\n7. Updating user...")
        updated_user = await user_service.update_user(
            user1.id, bio="Software developer and coffee enthusiast", updated_by="admin"
        )
        print(f"   ✓ Updated user {updated_user.username} with bio")

        # 8. Get service statistics
        print("\n8. Getting service statistics...")
        stats = await user_service.get_service_stats()
        print("   ✓ Service statistics:")
        print(f"     - Total users: {stats['total_users']}")
        print(f"     - Active users: {stats['active_users']}")
        print(f"     - Total posts: {stats['total_posts']}")
        print(f"     - Database status: {stats['database_health']['status']}")

        # 9. Demonstrate soft delete
        print("\n9. Demonstrating soft delete...")
        await user_service.delete_user(user2.id)
        print(f"   ✓ Soft deleted user {user2.username}")

        # Verify user is soft deleted (not in normal queries)
        found_user = await user_service.get_user_by_username("jane_smith")
        print(f"   ✓ User lookup after soft delete: {'Found' if found_user else 'Not found'}")

        # 10. Database utilities
        print("\n10. Using database utilities...")
        db_utils = DatabaseUtilities(db_manager)

        # Get database info
        db_info = await db_utils.get_database_info()
        print(f"   ✓ Database type: {db_info['database_type']}")
        print(f"   ✓ Database version: {db_info.get('version', 'N/A')}")

        # List tables
        tables = await db_utils.list_tables()
        print(f"   ✓ Tables in database: {', '.join(tables)}")

        # Get table info
        user_table_info = await db_utils.get_table_info("users")
        print(f"   ✓ Users table has {user_table_info['row_count']} rows")

        print("\n=== Demo completed successfully! ===")

    except Exception as e:
        print(f"\n❌ Error during demo: {e}")
        logger.exception("Demo failed")

    finally:
        # Clean up
        print("\n11. Cleaning up...")
        await user_service.close()
        print("   ✓ Database connections closed")


async def demonstrate_advanced_features():
    """Demonstrate advanced features of the database framework."""
    print("\n=== Advanced Features Demo ===\n")

    # Configure another service to show database per service isolation
    config = DatabaseConfig(
        service_name="post-service",
        database="post_service_db",
        db_type=DatabaseType.SQLITE,
        host="",
        port=0,
        username="",
        password="",
    )

    db_manager = DatabaseManager(config)
    await db_manager.initialize()

    try:
        # 1. Transaction with different isolation levels
        print("1. Testing transaction isolation levels...")

        from framework.database import (
            IsolationLevel,
            TransactionConfig,
            TransactionManager,
        )

        transaction_manager = TransactionManager(db_manager)

        async def demo_transaction_operation(session):
            # This would be a real database operation
            await session.execute("SELECT 1")
            return "Transaction completed"

        # Test with SERIALIZABLE isolation
        config = TransactionConfig(
            isolation_level=IsolationLevel.SERIALIZABLE, max_retries=3, retry_delay=0.1
        )

        result = await transaction_manager.retry_transaction(
            demo_transaction_operation, config=config
        )
        print(f"   ✓ SERIALIZABLE transaction: {result}")

        # 2. Bulk operations
        print("\n2. Testing bulk operations...")

        operations = [
            lambda: asyncio.sleep(0.01),  # Simulate DB operation
            lambda: asyncio.sleep(0.01),  # Simulate DB operation
            lambda: asyncio.sleep(0.01),  # Simulate DB operation
        ]

        results = await transaction_manager.bulk_transaction(operations)
        print(f"   ✓ Completed {len(results)} bulk operations")

        # 3. Connection pool status
        print("\n3. Checking connection pool status...")

        utils = DatabaseUtilities(db_manager)
        pool_status = await utils.get_connection_pool_status()
        print("   ✓ Connection pool status:")
        for key, value in pool_status.items():
            print(f"     - {key}: {value}")

        print("\n=== Advanced features demo completed! ===")

    except Exception as e:
        print(f"\n❌ Error in advanced demo: {e}")
        logger.exception("Advanced demo failed")

    finally:
        await db_manager.close()


if __name__ == "__main__":
    # Run the comprehensive demo
    asyncio.run(demonstrate_database_framework())

    # Run advanced features demo
    asyncio.run(demonstrate_advanced_features())
