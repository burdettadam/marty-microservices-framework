//! Canonical MMF messaging and event primitives.
//!
//! This crate replaces the overlapping Python core messaging, extended
//! messaging, enhanced event bus, and outbox contracts with one envelope and
//! one provider-neutral surface. Durable workflow and CQRS crates compose this
//! crate instead of implementing their own buses, retry policies, or stores.

#![forbid(unsafe_code)]

mod event;
mod memory;
mod model;
mod ports;
mod routing;
mod store;

pub use event::*;
pub use memory::*;
pub use model::*;
pub use ports::*;
pub use routing::*;
pub use store::*;

use mmf_core::{ErrorCode, MmfError};
use thiserror::Error;

#[derive(Clone, Debug, Eq, Error, PartialEq)]
pub enum MessagingError {
    #[error("invalid messaging configuration: {0}")]
    InvalidConfiguration(String),
    #[error("messaging backend is unavailable: {0}")]
    BackendUnavailable(String),
    #[error("message serialization failed: {0}")]
    Serialization(String),
    #[error("message has expired")]
    Expired,
    #[error("message was already processed: {0}")]
    Duplicate(String),
    #[error("message could not be routed: {0}")]
    Unroutable(String),
    #[error("message version conflict: expected {expected}, actual {actual}")]
    VersionConflict { expected: u64, actual: u64 },
    #[error("messaging operation is unsupported by the selected backend: {0}")]
    Unsupported(String),
    #[error("messaging storage failed: {0}")]
    Storage(String),
}

impl From<MessagingError> for MmfError {
    fn from(error: MessagingError) -> Self {
        let code = match &error {
            MessagingError::InvalidConfiguration(_) => ErrorCode::Configuration,
            MessagingError::BackendUnavailable(_) => ErrorCode::DependencyUnavailable,
            MessagingError::Duplicate(_) | MessagingError::VersionConflict { .. } => {
                ErrorCode::Conflict
            }
            MessagingError::Expired | MessagingError::Unroutable(_) => ErrorCode::InvalidState,
            MessagingError::Unsupported(_)
            | MessagingError::Serialization(_)
            | MessagingError::Storage(_) => ErrorCode::InvalidInput,
        };
        MmfError::new(code, error.to_string())
    }
}

#[cfg(test)]
mod tests {
    use std::collections::BTreeMap;

    use serde::Deserialize;
    use serde_json::json;

    use super::*;

    #[derive(Deserialize)]
    struct Fixture {
        schema_version: u32,
        priorities: Vec<PriorityCase>,
        message_state: MessageStateCase,
        routing: RoutingCase,
        pattern_recommendations: Vec<PatternCase>,
    }

    #[derive(Deserialize)]
    struct PriorityCase {
        name: String,
        value: u8,
    }

    #[derive(Deserialize)]
    struct MessageStateCase {
        now_ms: u64,
        future_expiry_ms: u64,
        past_expiry_ms: u64,
        retry_cases: Vec<RetryCase>,
    }

    #[derive(Deserialize)]
    struct RetryCase {
        retry_count: u32,
        max_retries: u32,
        expected: bool,
    }

    #[derive(Deserialize)]
    struct RoutingCase {
        default_topic: String,
        default_key: String,
        rules: Vec<RoutingRule>,
        cases: Vec<RouteCase>,
    }

    #[derive(Deserialize)]
    struct RouteCase {
        input: String,
        topic: String,
        routing_key: String,
        matched_rule: Option<String>,
    }

    #[derive(Deserialize)]
    struct PatternCase {
        use_case: String,
        response_needed: bool,
        ordering_required: bool,
        high_throughput: bool,
        expected: MessagingPattern,
    }

    fn fixture() -> Fixture {
        serde_json::from_str(include_str!("../../../contracts/messaging-behavior.json"))
            .expect("valid messaging behavior fixture")
    }

    fn message(id: &str, routing_key: &str) -> Message {
        Message {
            metadata: MessageMetadata {
                message_id: id.to_owned(),
                correlation_id: None,
                causation_id: None,
                tenant_id: None,
                source_service: Some("contract".into()),
                target_service: None,
                trace_parent: None,
                created_at_ms: 1,
                scheduled_at_ms: None,
                expires_at_ms: None,
                schema_version: 1,
                content_type: "application/json".into(),
                content_encoding: "utf-8".into(),
                partition_key: Some("account-1".into()),
                ordering_key: None,
                deduplication_key: None,
                headers: BTreeMap::new(),
            },
            kind: EventKind::Domain,
            message_type: "user.created".into(),
            pattern: MessagingPattern::PublishSubscribe,
            delivery_guarantee: DeliveryGuarantee::AtLeastOnce,
            priority: MessagePriority::Normal,
            status: MessageStatus::Pending,
            topic: "events.default".into(),
            routing_key: routing_key.into(),
            reply_to: None,
            payload: json!({"user_id": "123"}),
            retry_count: 0,
            max_retries: 3,
        }
    }

    #[test]
    fn language_neutral_message_contract() {
        let fixture = fixture();
        assert_eq!(fixture.schema_version, 1);
        let priorities = [
            ("low", MessagePriority::Low),
            ("normal", MessagePriority::Normal),
            ("high", MessagePriority::High),
            ("critical", MessagePriority::Critical),
        ];
        for case in fixture.priorities {
            let priority = priorities
                .iter()
                .find(|(name, _)| *name == case.name)
                .map(|(_, priority)| *priority)
                .expect("known priority");
            assert_eq!(priority.value(), case.value);
        }
        let case = fixture.message_state;
        let mut candidate = message("expiry", "events");
        assert!(!candidate.metadata.is_expired(case.now_ms));
        candidate.metadata.expires_at_ms = Some(case.future_expiry_ms);
        assert!(!candidate.metadata.is_expired(case.now_ms));
        candidate.metadata.expires_at_ms = Some(case.past_expiry_ms);
        assert!(candidate.metadata.is_expired(case.now_ms));
        for retry in case.retry_cases {
            candidate.retry_count = retry.retry_count;
            candidate.max_retries = retry.max_retries;
            assert_eq!(candidate.can_retry(), retry.expected);
        }
    }

    #[test]
    fn language_neutral_routing_contract() {
        let case = fixture().routing;
        let mut router = Router::new(case.default_topic, case.default_key);
        for rule in case.rules {
            router.add_rule(rule).expect("valid rule");
        }
        for route_case in case.cases {
            let route = router
                .route(&message("route", &route_case.input))
                .expect("route");
            assert_eq!(route.topic, route_case.topic);
            assert_eq!(route.routing_key, route_case.routing_key);
            assert_eq!(route.matched_rule, route_case.matched_rule);
        }
    }

    #[test]
    fn language_neutral_pattern_contract() {
        for case in fixture().pattern_recommendations {
            assert_eq!(
                recommend_pattern(
                    &case.use_case,
                    case.ordering_required,
                    case.response_needed,
                    case.high_throughput,
                ),
                case.expected
            );
        }
    }

    #[test]
    fn outbox_inbox_and_dead_letter_are_fail_closed() {
        let mut store = InMemoryDeliveryStore::default();
        let partition = store.enqueue(message("one", "events"), 8).expect("enqueue");
        assert_eq!(partition, stable_partition("account-1", 8));
        assert!(matches!(
            store.enqueue(message("one", "events"), 8),
            Err(MessagingError::Duplicate(_))
        ));
        store.begin_inbox("one", 1).expect("begin inbox");
        assert!(matches!(
            store.begin_inbox("one", 2),
            Err(MessagingError::Duplicate(_))
        ));
        for attempt in 0..4 {
            store.mark_processing("one").expect("processing");
            let status = store
                .mark_failed("one", "unavailable", Some(attempt + 10), attempt + 1)
                .expect("failure transition");
            if attempt < 3 {
                assert_eq!(status, MessageStatus::Retry);
            } else {
                assert_eq!(status, MessageStatus::DeadLetter);
            }
        }
        assert_eq!(store.dead_letters().len(), 1);
        assert!(store.requeue_dead_letter("one").expect("requeue"));
    }

    #[tokio::test]
    async fn memory_transport_filters_orders_schedules_and_acknowledges() {
        let transport = MemoryTransport::new(MessagingConfig::default()).expect("transport");
        transport.connect().await.expect("connect");
        transport
            .subscribe(Subscription {
                id: "users".into(),
                topic: "events.default".into(),
                consumer_group: Some("contract".into()),
                filter: EventFilter {
                    message_types: ["user.created".to_owned()].into(),
                    ..EventFilter::default()
                },
            })
            .await
            .expect("subscribe");
        let mut normal = message("normal", "events");
        normal.metadata.scheduled_at_ms = Some(5);
        transport.publish(normal).await.expect("normal publish");
        let mut critical = message("critical", "events");
        critical.priority = MessagePriority::Critical;
        transport.publish(critical).await.expect("critical publish");
        let first = transport.poll("users", 10, 1).await.expect("first poll");
        assert_eq!(first.len(), 1);
        assert_eq!(first[0].metadata.message_id, "critical");
        transport
            .acknowledge("users", "critical")
            .await
            .expect("acknowledge");
        let second = transport.poll("users", 10, 5).await.expect("second poll");
        assert_eq!(second.len(), 1);
        transport
            .reject("users", second[0].clone(), false, "invalid", 5)
            .await
            .expect("reject");
        assert_eq!(transport.dead_letters().len(), 1);
    }

    #[test]
    fn production_transport_configuration_fails_closed() {
        let config = MessagingConfig {
            backend: BackendType::Kafka,
            endpoint: None,
            ..MessagingConfig::default()
        };
        assert!(matches!(
            config.validate(),
            Err(MessagingError::BackendUnavailable(_))
        ));
    }
}
