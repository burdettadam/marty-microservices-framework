"""
Database models and connection management.
"""

from collections.abc import AsyncGenerator

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

from .config import get_settings

settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
Base = declarative_base()


class Service(Base):
    """Service model for tracking registered services."""

    __tablename__ = "services"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    address = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    health_check_url = Column(String)
    status = Column(String, default="unknown")
    tags = Column(JSON, default=list)
    metadata = Column(JSON, default=dict)
    last_seen = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ServiceMetrics(Base):
    """Service metrics model."""

    __tablename__ = "service_metrics"
    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String, index=True, nullable=False)
    metric_name = Column(String, nullable=False)
    metric_value = Column(String, nullable=False)
    metric_type = Column(String, nullable=False)
    labels = Column(JSON, default=dict)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class Configuration(Base):
    """Configuration model for storing service configurations."""

    __tablename__ = "configurations"
    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String, index=True, nullable=False)
    config_key = Column(String, nullable=False)
    config_value = Column(Text, nullable=False)
    environment = Column(String, default="default")
    is_secret = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Alert(Base):
    """Alert model for system alerts."""

    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String, index=True)
    alert_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, default="active")
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True))


async def create_tables():
    """Create database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
