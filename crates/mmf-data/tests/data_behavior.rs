use std::collections::BTreeMap;

use mmf_data::{
    CacheSerializer, CacheStats, CacheStore, Filter, InMemoryReadModelStore, MemoryCache,
    PostgresSql, ReadModelQuery, ReadModelStore, SerializationFormat, SortOrder,
};
use serde::Deserialize;
use serde_json::{Value, json};

#[derive(Deserialize)]
struct Fixture {
    schema_version: u32,
    cache: CacheCase,
    read_models: Vec<Value>,
    query: QueryCase,
    sql: SqlCase,
}

#[derive(Deserialize)]
struct CacheCase {
    json_value: Value,
    hits: u64,
    misses: u64,
    hit_rate: f64,
    ttl_ms: u64,
}

#[derive(Deserialize)]
struct QueryCase {
    field: String,
    operator: String,
    value: Value,
    sort_by: String,
    sort_order: SortOrder,
    expected_ids: Vec<String>,
}

#[derive(Deserialize)]
struct SqlCase {
    identifier: String,
    quoted_identifier: String,
    string: String,
    string_literal: String,
    json: Value,
    json_literal: String,
}

fn fixture() -> Fixture {
    serde_json::from_str(include_str!(
        "../../../contracts/data-infrastructure-behavior.json"
    ))
    .expect("valid data fixture")
}

#[tokio::test]
async fn cache_serialization_ttl_stats_and_sorted_sets_match_contract() {
    let fixture = fixture();
    assert_eq!(fixture.schema_version, 1);
    let serializer = CacheSerializer::new(SerializationFormat::Json).expect("JSON serializer");
    let bytes = serializer
        .serialize(&fixture.cache.json_value)
        .expect("serialize");
    assert_eq!(
        serializer.deserialize(&bytes).expect("deserialize"),
        fixture.cache.json_value
    );
    assert!(CacheSerializer::new(SerializationFormat::Pickle).is_err());

    let cache = MemoryCache::default();
    cache
        .set("one-time", b"challenge".to_vec(), Some(60), 100)
        .await
        .expect("set one-time value");
    assert_eq!(
        cache.take("one-time", 100).await.expect("take value"),
        Some(b"challenge".to_vec())
    );
    assert_eq!(
        cache.take("one-time", 100).await.expect("replay take"),
        None
    );

    assert_eq!(
        cache
            .sadd(
                "sessions",
                vec![b"session-2".to_vec(), b"session-1".to_vec()],
                100,
            )
            .await
            .expect("add set members"),
        2
    );
    assert_eq!(
        cache.smembers("sessions", 100).await.expect("set members"),
        [b"session-1".to_vec(), b"session-2".to_vec()]
    );
    assert_eq!(
        cache
            .srem("sessions", vec![b"session-1".to_vec()], 100)
            .await
            .expect("remove set member"),
        1
    );
    assert!(cache.expire("sessions", 1, 100).await.expect("set TTL"));
    assert!(
        cache
            .smembers("sessions", 1_100)
            .await
            .expect("expired set")
            .is_empty()
    );

    cache.set("key", bytes, Some(1), 100).await.expect("set");
    assert!(cache.get("key", 100).await.expect("get").is_some());
    assert!(
        cache
            .get("key", 100 + fixture.cache.ttl_ms)
            .await
            .expect("expiry")
            .is_none()
    );
    let stats = CacheStats {
        hits: fixture.cache.hits,
        misses: fixture.cache.misses,
        ..CacheStats::default()
    };
    assert!((stats.hit_rate() - fixture.cache.hit_rate).abs() < 1e-12);

    cache
        .zadd(
            "scores",
            BTreeMap::from([(b"low".to_vec(), 1.0), (b"high".to_vec(), 3.0)]),
        )
        .await
        .expect("zadd");
    assert_eq!(
        cache
            .zrevrangebyscore("scores", 3.0, 0.0, 0, None)
            .await
            .expect("range"),
        [b"high".to_vec(), b"low".to_vec()]
    );
}

#[tokio::test]
async fn cache_set_if_absent_is_a_single_winner_expiring_lease() {
    let cache = MemoryCache::default();
    assert!(
        cache
            .set_if_absent("lease", b"first".to_vec(), Some(1), 100)
            .await
            .expect("first lease")
    );
    assert!(
        !cache
            .set_if_absent("lease", b"second".to_vec(), Some(1), 100)
            .await
            .expect("contended lease")
    );
    assert!(
        cache
            .set_if_absent("lease", b"third".to_vec(), Some(1), 1_100)
            .await
            .expect("expired lease replacement")
    );
    assert_eq!(
        cache.get("lease", 1_100).await.expect("replacement lease"),
        Some(b"third".to_vec())
    );
}

#[tokio::test]
async fn read_model_filter_sort_and_pagination_match_contract() {
    let fixture = fixture();
    let store = InMemoryReadModelStore::default();
    for model in fixture.read_models {
        let id = model["id"].as_str().expect("id").to_owned();
        store.save("users", &id, model).await.expect("save");
    }
    let filter = match fixture.query.operator.as_str() {
        "gt" => Filter::Gt(fixture.query.value),
        other => panic!("unsupported fixture operator: {other}"),
    };
    let results = store
        .query(
            "users",
            &ReadModelQuery {
                filters: BTreeMap::from([(fixture.query.field, filter)]),
                sort_by: Some(fixture.query.sort_by),
                sort_order: fixture.query.sort_order,
                page: 1,
                page_size: 20,
            },
        )
        .await
        .expect("query");
    let ids = results
        .iter()
        .map(|model| model["id"].as_str().expect("id").to_owned())
        .collect::<Vec<_>>();
    assert_eq!(ids, fixture.query.expected_ids);
    assert_eq!(
        store.count("users", &BTreeMap::new()).await.expect("count"),
        3
    );
}

#[test]
fn sql_generation_is_validated_and_escaped() {
    let case = fixture().sql;
    assert_eq!(
        PostgresSql::quote_identifier(&case.identifier).expect("quote"),
        case.quoted_identifier
    );
    assert!(PostgresSql::quote_identifier("users; DROP TABLE users").is_err());
    assert_eq!(
        PostgresSql::literal(&Value::String(case.string)).expect("literal"),
        case.string_literal
    );
    assert_eq!(
        PostgresSql::literal(&case.json).expect("JSON"),
        case.json_literal
    );
    let insert = PostgresSql::insert(
        "audit_events",
        &["id".into(), "details".into()],
        &[vec![json!(1), json!({"result": "ok"})]],
    )
    .expect("insert");
    assert!(insert.contains("INSERT INTO \"audit_events\""));
    assert!(insert.contains("::jsonb"));
}
