import json
from pathlib import Path

from mmf.framework.infrastructure.dependency_injection import (
    DIContainer,
    LambdaFactory,
    ServiceScope,
)


FIXTURE = json.loads(
    (Path(__file__).parents[3] / "contracts" / "config-runtime-behavior.json").read_text()
)


class Service:
    pass


def test_dependency_lifetime_contract() -> None:
    expected = FIXTURE["lifetimes"]

    singleton = DIContainer()
    singleton.clear()
    singleton.register_service(
        Service,
        factory=LambdaFactory(Service, lambda _: Service()),
        is_singleton=True,
    )
    assert (
        singleton.get_service_typed(Service) is singleton.get_service_typed(Service)
    ) is expected["singleton_same"]

    transient = DIContainer()
    transient.clear()
    transient.register_service(
        Service,
        factory=LambdaFactory(Service, lambda _: Service()),
        is_singleton=False,
    )
    assert (
        transient.get_service_typed(Service) is transient.get_service_typed(Service)
    ) is expected["transient_same"]

    first = ServiceScope("first")
    second = ServiceScope("second")
    first_service = Service()
    first.set_service(Service, first_service)
    second.set_service(Service, Service())
    assert (first.get_service(Service) is first_service) is expected["scope_same"]
    assert (
        first.get_service(Service) is second.get_service(Service)
    ) is expected["cross_scope_same"]


def test_hosting_contract_has_one_result_per_case() -> None:
    # The legacy unified-config module is currently unimportable because it
    # references a removed secrets package. The neutral fixture still locks
    # its documented detection order for the Rust owner and future adapters.
    assert FIXTURE["schema_version"] == 1
    assert all(case["expected"] for case in FIXTURE["hosting"])
