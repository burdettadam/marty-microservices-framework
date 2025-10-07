from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

import pytest
from microservice_template.config import AppSettings
from microservice_template.server import GRPCServer


@pytest.fixture(scope="session")
def settings() -> AppSettings:
    return AppSettings(grpc_host="127.0.0.1", metrics_port=9001)


@pytest.fixture(scope="session")
def event_loop() -> (
    Iterator[asyncio.AbstractEventLoop]
):  # pragma: no cover - pytest hook
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@asynccontextmanager
async def _running_server(settings: AppSettings) -> AsyncIterator[AppSettings]:
    server = GRPCServer(settings)
    await server.start()
    try:
        yield settings
    finally:
        await server.stop()


@pytest.fixture(name="grpc_server")
async def fixture_grpc_server(settings: AppSettings) -> AsyncIterator[AppSettings]:
    async with _running_server(settings) as ctx:
        yield ctx
