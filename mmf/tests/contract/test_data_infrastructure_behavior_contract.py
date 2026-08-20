import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[3]
FIXTURE = json.loads((ROOT / "contracts" / "data-infrastructure-behavior.json").read_text())


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CACHE_TYPES = _load(
    "mmf_contract_cache_types",
    ROOT / "mmf" / "framework" / "infrastructure" / "cache" / "types.py",
)
PERSISTENCE = _load(
    "mmf_contract_persistence",
    ROOT / "mmf" / "framework" / "infrastructure" / "persistence.py",
)
SQL_UTILS = _load(
    "mmf_contract_sql_utils",
    ROOT / "mmf" / "framework" / "infrastructure" / "sql_utils.py",
)


def test_cache_serialization_and_stats_contract() -> None:
    case = FIXTURE["cache"]
    serializer = CACHE_TYPES.CacheSerializer(CACHE_TYPES.SerializationFormat.JSON)
    encoded = serializer.serialize(case["json_value"])
    assert serializer.deserialize(encoded) == case["json_value"]
    stats = CACHE_TYPES.CacheStats(hits=case["hits"], misses=case["misses"])
    assert stats.hit_rate == pytest.approx(case["hit_rate"])


def test_read_model_query_contract() -> None:
    async def run() -> list[str]:
        store = PERSISTENCE.InMemoryReadModelStore()
        for model in FIXTURE["read_models"]:
            await store.save("users", model["id"], model)
        query = FIXTURE["query"]
        operation = {f"${query['operator']}": query["value"]}
        results = await store.query(
            "users",
            filters={query["field"]: operation},
            sort_by=query["sort_by"],
            sort_order="desc",
        )
        return [result["id"] for result in results]

    assert asyncio.run(run()) == FIXTURE["query"]["expected_ids"]


def test_sql_escaping_contract() -> None:
    case = FIXTURE["sql"]
    assert SQL_UTILS.SQLGenerator.quote_identifier(case["identifier"]) == case["quoted_identifier"]
    assert SQL_UTILS.SQLGenerator.format_sql_literal(case["string"]) == case["string_literal"]
    legacy_json = SQL_UTILS.SQLGenerator.format_sql_literal(case["json"])
    assert json.loads(legacy_json.removeprefix("'").removesuffix("'")) == case["json"]
    with pytest.raises(ValueError):
        SQL_UTILS.SQLGenerator.quote_identifier("users; DROP TABLE users")
