from __future__ import annotations

import grpc
import pytest
from microservice_template.proto import greeter_pb2, greeter_pb2_grpc


@pytest.mark.integration
@pytest.mark.asyncio
async def test_grpc_round_trip(grpc_server) -> None:
    endpoint = f"{grpc_server.grpc_host}:{grpc_server.grpc_port}"
    async with grpc.aio.insecure_channel(endpoint) as channel:
        stub = greeter_pb2_grpc.GreeterServiceStub(channel)
        response = await stub.SayHello(greeter_pb2.HelloRequest(name="Integration"))

    assert response.message == "Hello, Integration!"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_check(grpc_server) -> None:
    endpoint = f"{grpc_server.grpc_host}:{grpc_server.grpc_port}"
    async with grpc.aio.insecure_channel(endpoint) as channel:
        stub = greeter_pb2_grpc.GreeterServiceStub(channel)
        response = await stub.HealthCheck(greeter_pb2.HealthCheckRequest())

    assert response.status == "SERVING"
