from __future__ import annotations

from typing import Any, cast

import grpc
import pytest
from microservice_template.config import AppSettings
from microservice_template.observability.metrics import MetricsServer
from microservice_template.proto import greeter_pb2
from microservice_template.service import GreeterService


class _FakeContext:
    async def abort(
        self, *args: Any, **kwargs: Any
    ) -> None:  # pragma: no cover - not used
        raise NotImplementedError


@pytest.mark.unit
@pytest.mark.asyncio
async def test_say_hello_generates_greeting() -> None:
    settings = AppSettings(grpc_host="127.0.0.1")
    metrics = MetricsServer(host="127.0.0.1", port=9999)
    service = GreeterService(settings=settings, metrics=metrics)

    response = await service.SayHello(
        greeter_pb2.HelloRequest(name="Marty"),
        cast(grpc.aio.ServicerContext, _FakeContext()),
    )

    assert response.message == "Hello, Marty!"
    assert isinstance(response.trace_id, str)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_health_check_returns_version() -> None:
    settings = AppSettings(version="1.2.3")
    metrics = MetricsServer(host="127.0.0.1", port=9999)
    service = GreeterService(settings=settings, metrics=metrics)

    response = await service.HealthCheck(
        greeter_pb2.HealthCheckRequest(),
        cast(grpc.aio.ServicerContext, _FakeContext()),
    )

    assert response.status == "SERVING"
    assert response.version == "1.2.3"
    assert response.uptime.endswith("s")
