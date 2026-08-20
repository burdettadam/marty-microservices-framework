"""Language-neutral behavior contract shared with ``mmf-resilience``."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from mmf.framework.resilience.domain.config import (
    BulkheadConfig,
    CircuitBreakerConfig,
    RetryConfig,
    RetryStrategy,
)
from mmf.framework.resilience.domain.exceptions import (
    BulkheadError,
    CircuitBreakerError,
    CircuitBreakerState,
    RetryError,
)
from mmf.framework.resilience.infrastructure.adapters.bulkhead import SemaphoreBulkhead
from mmf.framework.resilience.infrastructure.adapters.circuit_breaker import CircuitBreaker
from mmf.framework.resilience.infrastructure.adapters.fallback import (
    ChainFallback,
    FallbackConfig,
    FallbackError,
    FallbackStrategy,
)
from mmf.framework.resilience.infrastructure.adapters.retry import (
    ConstantBackoff,
    ExponentialBackoff,
    LinearBackoff,
    RetryManager,
)


CONTRACT = json.loads(
    (Path(__file__).parents[3] / "contracts" / "resilience-behavior.json").read_text(
        encoding="utf-8"
    )
)


def test_backoff_contract() -> None:
    for case in CONTRACT["backoff_cases"]:
        match case["strategy"]:
            case "constant":
                strategy = ConstantBackoff(jitter=False)
            case "linear":
                strategy = LinearBackoff(increment=case["base_ms"], jitter=False)
            case "exponential":
                strategy = ExponentialBackoff(multiplier=case["multiplier"], jitter=False)
            case unknown:
                raise AssertionError(f"unknown strategy: {unknown}")

        actual = strategy.calculate_delay(
            case["attempt"], case["base_ms"], case["max_ms"]
        )
        assert actual == case["expected_ms"]


@pytest.mark.asyncio
async def test_circuit_breaker_contract() -> None:
    case = CONTRACT["circuit_breaker"]
    circuit = CircuitBreaker(
        "contract",
        CircuitBreakerConfig(
            failure_threshold=case["failure_threshold"],
            success_threshold=case["success_threshold"],
            timeout_seconds=0.01,
        ),
    )

    async def fail() -> None:
        raise ValueError("failure")

    for _ in range(case["open_after_failures"]):
        with pytest.raises(ValueError):
            await circuit.call(fail)
    assert circuit.state is CircuitBreakerState.OPEN

    if case["reject_while_open"]:
        with pytest.raises(CircuitBreakerError):
            await circuit.call(lambda: "blocked")

    await asyncio.sleep(0.02)
    assert await circuit.call(lambda: "probe") == "probe"
    assert (circuit.state is CircuitBreakerState.HALF_OPEN) is case["half_open_after_timeout"]
    for _ in range(case["close_after_half_open_successes"] - 1):
        assert await circuit.call(lambda: "probe") == "probe"
    assert circuit.state is CircuitBreakerState.CLOSED


@pytest.mark.asyncio
async def test_retry_contract() -> None:
    case = CONTRACT["retry"]
    calls = 0

    async def eventually_succeeds() -> str:
        nonlocal calls
        calls += 1
        if calls <= case["failures_before_success"]:
            raise RuntimeError("retryable")
        return "ok"

    manager = RetryManager(
        RetryConfig(
            max_attempts=case["max_attempts"],
            base_delay=0,
            max_delay=0,
            strategy=RetryStrategy.CONSTANT,
            jitter=False,
        )
    )
    assert await manager.execute_async(eventually_succeeds) == "ok"
    assert calls == case["expected_attempts"]

    calls = 0

    async def fatal() -> None:
        nonlocal calls
        calls += 1
        raise ValueError("fatal")

    manager = RetryManager(
        RetryConfig(
            max_attempts=case["max_attempts"],
            base_delay=0,
            non_retryable_exceptions=(ValueError,),
        )
    )
    with pytest.raises(RetryError):
        await manager.execute_async(fatal)
    assert calls == case["non_retryable_expected_attempts"]


@pytest.mark.asyncio
async def test_bulkhead_contract() -> None:
    case = CONTRACT["bulkhead"]
    bulkhead = SemaphoreBulkhead(
        "contract",
        BulkheadConfig(
            max_concurrent=case["max_concurrent"],
            timeout_seconds=0.01,
            reject_on_full=case["reject_on_full"],
        ),
    )
    release = asyncio.Event()
    entered = asyncio.Event()

    async def held_operation() -> None:
        entered.set()
        await release.wait()

    active = asyncio.create_task(bulkhead.execute_async(held_operation))
    await entered.wait()
    with pytest.raises(BulkheadError):
        await bulkhead.execute_async(lambda: None)
    release.set()
    await active
    assert bulkhead.get_stats()["rejected_requests"] == case["expected_rejections"]


class _RecordingFallback(FallbackStrategy):
    def __init__(self, name: str, observed: list[str], succeeds: bool) -> None:
        super().__init__(name, FallbackConfig())
        self._observed = observed
        self._succeeds = succeeds

    async def execute_fallback(
        self, original_error: Exception, *args: Any, **kwargs: Any
    ) -> str:
        del args, kwargs
        self._observed.append(self.name)
        if self._succeeds:
            return "fallback"
        raise FallbackError(f"{self.name} unavailable", original_error, 1)


@pytest.mark.asyncio
async def test_fallback_order_contract() -> None:
    expected = CONTRACT["fallback_order"]
    observed: list[str] = []
    strategies = [
        _RecordingFallback(name, observed, succeeds=name == "static") for name in expected
    ]
    chain = ChainFallback("contract", strategies)
    assert await chain.execute_fallback(RuntimeError("primary")) == "fallback"
    assert observed == expected
