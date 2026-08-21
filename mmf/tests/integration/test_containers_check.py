import pytest
import redis.asyncio as redis
from testcontainers.redis import RedisContainer


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_container_connection(
    real_database_connection,
):
    """Verify that the Postgres container is running and accessible."""
    result = await real_database_connection.fetchval("SELECT 1")
    assert result == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_container_connection(redis_container: RedisContainer):
    """Verify that the Redis container is running and accessible."""
    redis_url = f"redis://localhost:{redis_container.get_exposed_port(6379)}/0"
    client = redis.from_url(redis_url)
    try:
        await client.set("test_key", "test_value")
        value = await client.get("test_key")
        assert value == b"test_value"
    finally:
        await client.aclose()
