"""Language-neutral behavioral contract for the Python-to-Rust platform port."""

from __future__ import annotations

import json
from pathlib import Path

from mmf.discovery.domain.load_balancing import (
    LoadBalancer,
    LoadBalancingConfig,
    TrafficPolicy,
)
from mmf.discovery.domain.models import ServiceEndpoint, ServiceInstance, ServiceMetadata
from mmf.framework.deployment.domain.enums import DeploymentStatus, DeploymentStrategy
from mmf.framework.gateway.domain.services import (
    ExactMatcher,
    PrefixMatcher,
    RegexMatcher,
    TemplateMatcher,
    WildcardMatcher,
)


CONTRACT = json.loads(
    (Path(__file__).parents[3] / "contracts" / "platform-behavior.json").read_text(
        encoding="utf-8"
    )
)


def test_endpoint_contract() -> None:
    from mmf.discovery.domain.models import ServiceInstanceType

    protocols = {protocol.value: protocol for protocol in ServiceInstanceType}
    for case in CONTRACT["endpoints"]:
        endpoint = ServiceEndpoint(
            host=case["host"],
            port=case["port"],
            protocol=protocols[case["protocol"]],
            path=case["path"],
            ssl_enabled=case["protocol"] == "https",
        )
        assert endpoint.get_url() == case["url"]


def test_route_matching_contract() -> None:
    matchers = {
        "exact": ExactMatcher(),
        "prefix": PrefixMatcher(),
        "regex": RegexMatcher(),
        "wildcard": WildcardMatcher(),
        "template": TemplateMatcher(),
    }
    for case in CONTRACT["route_matches"]:
        matcher = matchers[case["match_type"]]
        assert matcher.matches(case["pattern"], case["path"]) is case["matched"]
        assert matcher.extract_params(case["pattern"], case["path"]) == case["params"]


def _instances() -> list[ServiceInstance]:
    return [
        ServiceInstance(
            service_name="gateway",
            instance_id=case["id"],
            endpoint=ServiceEndpoint(host=case["host"], port=8080),
            metadata=ServiceMetadata(
                weight=case["weight"],
                region=case["region"],
                availability_zone=case["zone"],
            ),
        )
        for case in CONTRACT["load_balancing"]["instances"]
    ]


def test_load_balancing_contract() -> None:
    case = CONTRACT["load_balancing"]
    instances = _instances()
    for instance, fixture in zip(instances, case["instances"], strict=True):
        instance.active_connections = fixture["connections"]

    round_robin = LoadBalancer(LoadBalancingConfig(policy=TrafficPolicy.ROUND_ROBIN))
    assert [
        round_robin.select_instance("gateway", instances).instance_id
        for _ in case["round_robin_sequence"]
    ] == case["round_robin_sequence"]

    least = LoadBalancer(LoadBalancingConfig(policy=TrafficPolicy.LEAST_CONN))
    assert least.select_instance("gateway", instances).instance_id == case["least_connections"]

    locality = LoadBalancer(LoadBalancingConfig(policy=TrafficPolicy.LOCALITY_AWARE))
    assert (
        locality.select_instance(
            "gateway", instances, {"region": "us-east-1", "zone": "us-east-1a"}
        ).instance_id
        == case["same_zone"]
    )
    assert (
        locality.select_instance(
            "gateway", instances[1:], {"region": "us-east-1", "zone": "missing"}
        ).instance_id
        == case["same_region"]
    )


def test_deployment_enums_contract() -> None:
    case = CONTRACT["deployment"]
    assert set(case["statuses"]).issubset({status.value for status in DeploymentStatus})
    assert set(case["strategies"]).issubset({strategy.value for strategy in DeploymentStrategy})
    assert case["production_requires_digest"] is True
