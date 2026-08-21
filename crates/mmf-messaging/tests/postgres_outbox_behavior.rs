#![cfg(feature = "postgres")]

use std::collections::BTreeMap;

use mmf_messaging::{
    DeliveryGuarantee, EventKind, Message, MessageMetadata, MessagePriority, MessageStatus,
    MessagingPattern, PostgresOutboxStore,
};
use serde_json::json;
use sqlx::postgres::PgPoolOptions;

fn message(id: &str, now_ms: u64) -> Message {
    Message {
        metadata: MessageMetadata {
            message_id: id.into(),
            correlation_id: None,
            causation_id: None,
            tenant_id: Some("tenant-1".into()),
            source_service: None,
            target_service: None,
            trace_parent: None,
            created_at_ms: now_ms,
            scheduled_at_ms: None,
            expires_at_ms: None,
            schema_version: 1,
            content_type: "application/json".into(),
            content_encoding: "utf-8".into(),
            partition_key: Some("tenant-1".into()),
            ordering_key: None,
            deduplication_key: Some(id.into()),
            headers: BTreeMap::new(),
        },
        kind: EventKind::Domain,
        message_type: "contract.created".into(),
        pattern: MessagingPattern::PublishSubscribe,
        delivery_guarantee: DeliveryGuarantee::AtLeastOnce,
        priority: MessagePriority::Normal,
        status: MessageStatus::Pending,
        topic: "contract.events".into(),
        routing_key: "contract.created".into(),
        reply_to: None,
        payload: json!({"id": id}),
        retry_count: 0,
        max_retries: 1,
    }
}

#[test]
fn migration_owns_fenced_outbox_and_inbox_state() {
    let sql = include_str!("../migrations/0001_postgres_outbox.sql");
    for required in [
        "CREATE TABLE IF NOT EXISTS mmf_messaging.outbox_messages",
        "CREATE TABLE IF NOT EXISTS mmf_messaging.inbox_messages",
        "lease_token TEXT",
        "lease_expires_at_ms BIGINT",
        "processed_at_ms BIGINT",
        "PRIMARY KEY (source_service, message_id)",
    ] {
        assert!(
            sql.contains(required),
            "missing migration contract: {required}"
        );
    }
}

#[tokio::test]
async fn live_postgres_outbox_is_atomic_fenced_and_recoverable_when_available() {
    let Ok(url) = std::env::var("MMF_POSTGRES_TEST_URL") else {
        return;
    };
    let pool = PgPoolOptions::new()
        .max_connections(2)
        .connect(&url)
        .await
        .expect("connect PostgreSQL");
    let source = format!("mmf-contract-{}", uuid::Uuid::new_v4());
    let store = PostgresOutboxStore::new(pool, source, 8).expect("outbox store");
    store.migrate().await.expect("migrate outbox");
    store.health().await.expect("outbox health");
    let now = 1_800_000_000_000_u64;

    store.enqueue(message("first", now)).await.expect("enqueue");
    assert!(store.enqueue(message("first", now)).await.is_err());
    assert_eq!(store.pending_count(now).await.expect("pending"), 1);
    let first = store
        .claim_due(now, 1_000, 1, None)
        .await
        .expect("claim")
        .pop()
        .expect("claimed entry");
    let first_lease = first.lease_token.expect("lease token");
    let recovered = store
        .claim_due(now + 1_001, 1_000, 1, None)
        .await
        .expect("recover claim")
        .pop()
        .expect("recovered entry");
    let recovered_lease = recovered.lease_token.expect("recovered lease");
    assert!(
        store
            .mark_processed_by_lease("first", &first_lease, now + 1_002)
            .await
            .is_err()
    );
    assert_eq!(
        store
            .mark_failed_by_lease(
                "first",
                &recovered_lease,
                "unavailable",
                Some(now + 2_000),
                now + 1_002,
            )
            .await
            .expect("dead letter"),
        MessageStatus::DeadLetter
    );
    assert_eq!(store.dead_letters(10).await.expect("dead letters").len(), 1);
    assert!(store.requeue_dead_letter("first").await.expect("requeue"));

    store
        .begin_inbox("incoming", now)
        .await
        .expect("begin inbox");
    assert!(store.begin_inbox("incoming", now).await.is_err());
    let claimed = store
        .claim_due(now + 2_000, 1_000, 1, None)
        .await
        .expect("claim replay")
        .pop()
        .expect("replayed entry");
    store
        .mark_processed_by_lease(
            "first",
            claimed.lease_token.as_deref().expect("lease"),
            now + 2_001,
        )
        .await
        .expect("complete");
    assert_eq!(
        store
            .entry("first")
            .await
            .expect("entry")
            .expect("stored")
            .status,
        MessageStatus::Processed
    );
    assert_eq!(
        store.replay_ids(None, 10).await.expect("replay IDs"),
        ["first"]
    );
    assert_eq!(store.cleanup(now + 3_000).await.expect("cleanup"), (1, 1));
}
