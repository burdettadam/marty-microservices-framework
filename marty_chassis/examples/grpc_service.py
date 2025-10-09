"""
Example: gRPC microservice using Marty Chassis

This example demonstrates how to create a gRPC service with the chassis.
"""

import asyncio
from collections.abc import AsyncGenerator

import grpc
from marty_chassis import (
    ChassisConfig,
    HealthCheck,
    MetricsCollector,
    create_grpc_service,
    get_logger,
)

# Configure logging
logger = get_logger(__name__)

# Create configuration
config = ChassisConfig()

# Initialize chassis components
metrics = MetricsCollector()
health = HealthCheck()


# Simple proto definitions (would normally be generated from .proto files)
class EchoRequest:
    def __init__(self, message: str):
        self.message = message


class EchoResponse:
    def __init__(self, message: str):
        self.message = message


class CalculateRequest:
    def __init__(self, a: float, b: float, operation: str):
        self.a = a
        self.b = b
        self.operation = operation


class CalculateResponse:
    def __init__(self, result: float):
        self.result = result


# gRPC Service Implementation
class EchoServicer:
    """Example gRPC service implementation."""

    async def Echo(
        self, request: EchoRequest, context: grpc.aio.ServicerContext
    ) -> EchoResponse:
        """Echo the received message."""
        logger.info("Echo request received", message=request.message)
        metrics.counter("echo_requests_total").inc()

        # Simulate some processing
        await asyncio.sleep(0.1)

        response_message = f"Echo: {request.message}"
        logger.info("Echo response sent", response=response_message)

        return EchoResponse(message=response_message)

    async def StreamEcho(
        self,
        request_iterator: AsyncGenerator[EchoRequest, None],
        context: grpc.aio.ServicerContext,
    ) -> AsyncGenerator[EchoResponse, None]:
        """Streaming echo service."""
        logger.info("Stream echo session started")
        metrics.counter("stream_echo_sessions_total").inc()

        async for request in request_iterator:
            logger.debug("Stream echo message", message=request.message)
            metrics.counter("stream_echo_messages_total").inc()

            response = EchoResponse(message=f"Stream Echo: {request.message}")
            yield response

        logger.info("Stream echo session ended")


class CalculatorServicer:
    """Example calculator gRPC service."""

    async def Calculate(
        self, request: CalculateRequest, context: grpc.aio.ServicerContext
    ) -> CalculateResponse:
        """Perform basic arithmetic operations."""
        logger.info(
            "Calculate request", a=request.a, b=request.b, operation=request.operation
        )

        metrics.counter("calculate_requests_total", ["operation"]).labels(
            operation=request.operation
        ).inc()

        try:
            if request.operation == "add":
                result = request.a + request.b
            elif request.operation == "subtract":
                result = request.a - request.b
            elif request.operation == "multiply":
                result = request.a * request.b
            elif request.operation == "divide":
                if request.b == 0:
                    await context.abort(
                        grpc.StatusCode.INVALID_ARGUMENT, "Division by zero"
                    )
                result = request.a / request.b
            else:
                await context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT,
                    f"Unknown operation: {request.operation}",
                )

            logger.info("Calculate result", result=result)
            return CalculateResponse(result=result)

        except Exception as e:
            logger.error("Calculate error", error=str(e))
            metrics.counter("calculate_errors_total").inc()
            await context.abort(grpc.StatusCode.INTERNAL, "Calculation failed")


# Health checks
@health.register("grpc_server")
async def check_grpc_server():
    """Check gRPC server health."""
    # In a real app, this would check server status
    return True


@health.register("calculator_service")
async def check_calculator():
    """Check calculator service health."""
    # Test basic calculation
    try:
        test_result = 2 + 2
        return test_result == 4
    except Exception:
        return False


async def serve():
    """Start the gRPC server."""
    logger.info("Starting gRPC service")

    # Create gRPC server with chassis
    server = create_grpc_service(config)

    # Add service implementations
    EchoServicer()
    CalculatorServicer()

    # In a real app, these would be properly registered with generated stubs
    # server.add_servicer(echo_servicer)
    # server.add_servicer(calculator_servicer)

    # Add insecure port (in production, use secure port with TLS)
    listen_addr = f"{config.service.host}:{config.service.port}"
    server.add_insecure_port(listen_addr)

    logger.info("gRPC server starting", address=listen_addr)
    await server.start()

    try:
        logger.info("gRPC server started successfully")
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        await server.stop(grace=5.0)
        logger.info("gRPC server stopped")


if __name__ == "__main__":
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
