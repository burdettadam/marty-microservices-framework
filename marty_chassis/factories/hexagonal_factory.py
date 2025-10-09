"""
Hexagonal architecture factory for the Marty Chassis.

This factory creates services using hexagonal (ports & adapters) architecture,
providing dependency injection and proper separation of concerns.
"""

from typing import Any, Dict, Optional

from fastapi import FastAPI
from marty_chassis.config import ChassisConfig
from marty_chassis.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logger = get_logger(__name__)


class HexagonalServiceFactory:
    """Factory for creating services with hexagonal architecture."""

    def __init__(self, config: ChassisConfig):
        self.config = config
        self._database_engine = None
        self._session_factory = None

    async def create_service(
        self, service_module: str, service_config: Optional[Dict[str, Any]] = None
    ) -> FastAPI:
        """
        Create a service using hexagonal architecture.

        Args:
            service_module: Python module path containing the service implementation
            service_config: Additional service-specific configuration

        Returns:
            Configured FastAPI application
        """
        logger.info(f"Creating hexagonal service: {service_module}")

        # Import the service module dynamically
        import importlib

        module = importlib.import_module(service_module)

        # Initialize infrastructure adapters
        await self._setup_infrastructure()

        # Create output port implementations (adapters)
        output_adapters = await self._create_output_adapters(service_config or {})

        # Create use cases with injected dependencies
        use_cases = await self._create_use_cases(module, output_adapters)

        # Create input adapters (HTTP, gRPC, etc.)
        input_adapters = await self._create_input_adapters(module, use_cases)

        # Create and configure FastAPI app
        app = await self._create_fastapi_app(input_adapters)

        logger.info(f"Successfully created hexagonal service: {service_module}")
        return app

    async def _setup_infrastructure(self) -> None:
        """Setup infrastructure components like database."""
        if hasattr(self.config, "database") and self.config.database.url:
            self._database_engine = create_async_engine(
                self.config.database.url,
                echo=self.config.database.debug,
                pool_pre_ping=True,
            )

            self._session_factory = sessionmaker(
                self._database_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            logger.info("Database infrastructure initialized")

    async def _create_output_adapters(
        self, service_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create output adapter implementations."""
        adapters = {}

        # Database adapters
        if self._session_factory:
            from .infrastructure.adapters.database_adapters import (
                SQLAlchemyTaskRepository,
                SQLAlchemyUnitOfWork,
                SQLAlchemyUserRepository,
            )

            # Create a session for this request context
            session = self._session_factory()

            adapters["task_repository"] = SQLAlchemyTaskRepository(session)
            adapters["user_repository"] = SQLAlchemyUserRepository(session)
            adapters["unit_of_work"] = SQLAlchemyUnitOfWork(session)

        # Event adapters
        from .infrastructure.adapters.event_adapters import (
            EmailNotificationService,
            KafkaEventPublisher,
            RedisCache,
        )

        # Configure based on chassis config
        kafka_config = getattr(self.config, "kafka", None)
        adapters["event_publisher"] = KafkaEventPublisher(
            kafka_producer=kafka_config.producer if kafka_config else None,
            topic_prefix=service_config.get("event_topic_prefix", "morty"),
        )

        email_config = getattr(self.config, "email", None)
        adapters["notification_service"] = EmailNotificationService(
            email_client=email_config.client if email_config else None,
            from_email=service_config.get("from_email", "noreply@morty.dev"),
        )

        redis_config = getattr(self.config, "redis", None)
        adapters["cache"] = RedisCache(
            redis_client=redis_config.client if redis_config else None
        )

        logger.info("Output adapters created")
        return adapters

    async def _create_use_cases(
        self, service_module: Any, output_adapters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create use case implementations with injected dependencies."""
        use_cases = {}

        # Check if the service module has use cases
        if hasattr(service_module, "application") and hasattr(
            service_module.application, "use_cases"
        ):
            use_cases_module = service_module.application.use_cases

            # Create task management use case
            if hasattr(use_cases_module, "TaskManagementUseCase"):
                use_cases["task_management"] = use_cases_module.TaskManagementUseCase(
                    task_repository=output_adapters["task_repository"],
                    user_repository=output_adapters["user_repository"],
                    event_publisher=output_adapters["event_publisher"],
                    notification_service=output_adapters["notification_service"],
                    cache=output_adapters["cache"],
                    unit_of_work=output_adapters["unit_of_work"],
                )

            # Create user management use case
            if hasattr(use_cases_module, "UserManagementUseCase"):
                use_cases["user_management"] = use_cases_module.UserManagementUseCase(
                    user_repository=output_adapters["user_repository"],
                    task_repository=output_adapters["task_repository"],
                    event_publisher=output_adapters["event_publisher"],
                    notification_service=output_adapters["notification_service"],
                    cache=output_adapters["cache"],
                    unit_of_work=output_adapters["unit_of_work"],
                )

        logger.info("Use cases created with dependency injection")
        return use_cases

    async def _create_input_adapters(
        self, service_module: Any, use_cases: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create input adapter implementations."""
        adapters = {}

        # Check if the service module has HTTP adapter
        if (
            hasattr(service_module, "infrastructure")
            and hasattr(service_module.infrastructure, "adapters")
            and hasattr(service_module.infrastructure.adapters, "http_adapter")
        ):
            http_adapter_class = (
                service_module.infrastructure.adapters.http_adapter.HTTPAdapter
            )
            adapters["http"] = http_adapter_class(
                task_management=use_cases.get("task_management"),
                user_management=use_cases.get("user_management"),
            )

        # Could add gRPC adapter here if needed
        # if hasattr(service_module.infrastructure.adapters, 'grpc_adapter'):
        #     adapters['grpc'] = ...

        logger.info("Input adapters created")
        return adapters

    async def _create_fastapi_app(self, input_adapters: Dict[str, Any]) -> FastAPI:
        """Create and configure the FastAPI application."""
        app = FastAPI(
            title=self.config.service.name,
            version=self.config.service.version,
            description=f"Hexagonal architecture implementation of {self.config.service.name}",
        )

        # Add HTTP adapter routes
        if "http" in input_adapters:
            app.include_router(
                input_adapters["http"].router, prefix="/api/v1", tags=["morty"]
            )

        # Add health check endpoints
        @app.get("/health")
        async def health_check():
            return {"status": "healthy", "service": self.config.service.name}

        @app.get("/ready")
        async def readiness_check():
            # Could add more sophisticated readiness checks here
            return {"status": "ready", "service": self.config.service.name}

        logger.info("FastAPI application configured")
        return app


def create_hexagonal_service(
    service_module: str,
    config: Optional[ChassisConfig] = None,
    service_config: Optional[Dict[str, Any]] = None,
) -> FastAPI:
    """
    Create a service using hexagonal architecture.

    This is the main entry point for creating hexagonal services with the chassis.

    Args:
        service_module: Python module path containing the service implementation
        config: Chassis configuration (uses environment if not provided)
        service_config: Additional service-specific configuration

    Returns:
        Configured FastAPI application

    Example:
        app = create_hexagonal_service(
            "service.morty_service",
            service_config={
                "event_topic_prefix": "morty",
                "from_email": "morty@company.com"
            }
        )
    """
    if config is None:
        config = ChassisConfig.from_env()

    factory = HexagonalServiceFactory(config)

    # For now, we'll create this synchronously, but in a real implementation
    # you might want to use an async context manager or startup events
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        app = loop.run_until_complete(
            factory.create_service(service_module, service_config)
        )
        return app
    finally:
        loop.close()
