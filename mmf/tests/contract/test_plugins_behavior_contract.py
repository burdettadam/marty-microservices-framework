"""Behavioral contract for the surviving Python plugin public surface."""

import json
from pathlib import Path

import pytest

from mmf.core.plugins import (
    PluginContextBuilder,
    PluginMetadata,
    PluginStatus,
    RouteMethod,
    ServiceDefinition,
    ServiceStatus,
)
from mmf.framework.infrastructure.plugin_config import PluginConfigSection


FIXTURE = json.loads(
    (Path(__file__).parents[3] / "contracts" / "plugins-behavior.json").read_text(
        encoding="utf-8"
    )
)


def test_plugin_models_and_defaults_match_contract() -> None:
    assert [item.value for item in PluginStatus] == FIXTURE["plugin_statuses"]
    assert [item.value for item in ServiceStatus] == FIXTURE["service_statuses"]
    assert [item.value for item in RouteMethod] == FIXTURE["route_methods"]
    metadata = PluginMetadata(name="audit", version="1.0.0")
    assert metadata.api_version == FIXTURE["default_metadata"]["api_version"]
    assert metadata.min_mmf_version == FIXTURE["default_metadata"]["min_mmf_version"]
    context = (
        PluginContextBuilder("audit")
        .with_config({"enabled": True})
        .with_cache("cache-provider")
        .build()
    )
    assert context.plugin_id == "audit"
    assert context.config == {"enabled": True}
    assert context.cache == "cache-provider"


def test_service_and_config_validation_contract() -> None:
    with pytest.raises(ValueError, match="Service name is required"):
        ServiceDefinition(name="")
    defaults = PluginConfigSection().model_dump()
    assert defaults["enabled"] is FIXTURE["config"]["defaults"]["enabled"]
