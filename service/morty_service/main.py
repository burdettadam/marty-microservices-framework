"""
Main entry point for the Morty service.

This demonstrates how to create a microservice using hexagonal architecture
with the Marty Chassis framework.
"""

from marty_chassis import ChassisConfig, create_hexagonal_service

# Service configuration
SERVICE_CONFIG = {
    "event_topic_prefix": "morty",
    "from_email": "morty@company.com",
}

# Create the application using hexagonal architecture
app = create_hexagonal_service(
    service_module="service.morty_service", service_config=SERVICE_CONFIG
)

if __name__ == "__main__":
    import uvicorn

    # Load configuration
    config = ChassisConfig.from_env()

    # Run the service
    uvicorn.run(
        app,
        host=config.service.host,
        port=config.service.port,
        log_level=config.observability.log_level.lower(),
    )
