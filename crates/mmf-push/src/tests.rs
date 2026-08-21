use std::collections::{BTreeMap, VecDeque};
use std::sync::{Arc, Mutex};

use async_trait::async_trait;
use serde::Deserialize;
use serde_json::{Value, json};

use super::*;

#[derive(Deserialize)]
struct Fixture {
    schema_version: u32,
    channels: Vec<String>,
    priorities: Vec<String>,
    statuses: Vec<String>,
    expiry: ExpiryFixture,
    fcm: FcmFixture,
    sse: SseFixture,
    lifecycle_error_mappings: LifecycleFixture,
    webhook_signature: SignatureFixture,
    webhook_destination_registry: DestinationRegistryFixture,
    webhook_event_signature: EventSignatureFixture,
    failure_contracts: FailureFixture,
}

#[derive(Deserialize)]
struct ExpiryFixture {
    created_at_ms: u64,
    ttl_seconds: u64,
    not_expired_at_ms: u64,
    expired_at_ms: u64,
}

#[derive(Deserialize)]
struct FcmFixture {
    message_id: String,
    token: String,
    priority: PushPriority,
    ttl_seconds: u64,
    collapse_key: String,
    content_available: bool,
    mutable_content: bool,
    data: BTreeMap<String, Value>,
    expected: FcmExpected,
}

#[derive(Deserialize)]
struct FcmExpected {
    android_priority: String,
    apns_priority: String,
    android_ttl: String,
    active: String,
    attempt: String,
    roles: String,
}

#[derive(Deserialize)]
struct SseFixture {
    message_id: String,
    event_type: String,
    expected_event_id: String,
    expected_user_connections: Vec<String>,
    expected_organization_connections: Vec<String>,
}

#[derive(Deserialize)]
struct LifecycleFixture {
    fcm: BTreeMap<String, TokenInvalidationReason>,
    apns: BTreeMap<String, TokenInvalidationReason>,
}

#[derive(Deserialize)]
struct SignatureFixture {
    body: String,
    secret: String,
    expected: String,
}

#[derive(Deserialize)]
struct DestinationRegistryFixture {
    configuration: String,
    accepted: Vec<[String; 2]>,
    rejected: Vec<[String; 2]>,
}

#[derive(Deserialize)]
struct EventSignatureFixture {
    secret: String,
    audience: String,
    event: String,
    event_id: String,
    timestamp: String,
    payload: Value,
    expected: String,
}

#[derive(Deserialize)]
struct FailureFixture {
    missing_adapter: String,
    expired: String,
    missing_fcm_tokens: String,
    missing_webhook_endpoints: String,
    invalid_token: String,
    open_circuit: String,
}

fn fixture() -> Fixture {
    serde_json::from_str(include_str!("../../../contracts/push-behavior.json"))
        .expect("valid push behavior fixture")
}

#[test]
fn language_neutral_models_and_expiry_contract() {
    let fixture = fixture();
    assert_eq!(fixture.schema_version, 1);
    assert_eq!(
        serde_json::to_value([
            PushChannel::Fcm,
            PushChannel::Apns,
            PushChannel::Sse,
            PushChannel::Webhook,
            PushChannel::Webpush,
            PushChannel::Websocket,
        ])
        .expect("channels"),
        json!(fixture.channels)
    );
    assert_eq!(
        serde_json::to_value([
            PushPriority::Low,
            PushPriority::Normal,
            PushPriority::High,
            PushPriority::Critical,
        ])
        .expect("priorities"),
        json!(fixture.priorities)
    );
    assert_eq!(
        serde_json::to_value([
            PushStatus::Pending,
            PushStatus::Sending,
            PushStatus::Delivered,
            PushStatus::Failed,
            PushStatus::Expired,
            PushStatus::Rejected,
        ])
        .expect("statuses"),
        json!(fixture.statuses)
    );
    let message = PushMessage {
        created_at_ms: fixture.expiry.created_at_ms,
        ttl_seconds: fixture.expiry.ttl_seconds,
        ..PushMessage::default()
    };
    assert!(!message.is_expired_at(fixture.expiry.not_expired_at_ms));
    assert!(message.is_expired_at(fixture.expiry.expired_at_ms));
}

#[test]
fn language_neutral_fcm_payload_contract() {
    let fixture = fixture().fcm;
    let message = PushMessage {
        id: fixture.message_id,
        title: "Credential ready".into(),
        body: "Open your wallet".into(),
        priority: fixture.priority,
        ttl_seconds: fixture.ttl_seconds,
        collapse_key: Some(fixture.collapse_key),
        content_available: fixture.content_available,
        mutable_content: fixture.mutable_content,
        data: fixture.data,
        ..PushMessage::default()
    };
    let payload = FcmAdapter::build_message(&message, &fixture.token);
    assert_eq!(
        payload["android"]["priority"],
        fixture.expected.android_priority
    );
    assert_eq!(
        payload["apns"]["headers"]["apns-priority"],
        fixture.expected.apns_priority
    );
    assert_eq!(payload["android"]["ttl"], fixture.expected.android_ttl);
    assert_eq!(payload["data"]["active"], fixture.expected.active);
    assert_eq!(payload["data"]["attempt"], fixture.expected.attempt);
    assert_eq!(payload["data"]["roles"], fixture.expected.roles);
    assert_eq!(payload["apns"]["payload"]["aps"]["content-available"], 1);
    assert_eq!(payload["apns"]["payload"]["aps"]["mutable-content"], 1);
}

#[tokio::test]
async fn language_neutral_sse_targeting_and_event_contract() {
    let fixture = fixture().sse;
    let adapter = SseAdapter::new(SseConfig::default()).expect("SSE config");
    adapter.start().await.expect("start");
    let mut user_a = adapter.add_connection(
        &fixture.expected_user_connections[0],
        Some("user-1".into()),
        None,
        None,
        1,
    );
    let mut user_b = adapter.add_connection(
        &fixture.expected_user_connections[1],
        Some("user-1".into()),
        None,
        None,
        2,
    );
    let mut organization = adapter.add_connection(
        &fixture.expected_organization_connections[0],
        None,
        Some("org-1".into()),
        None,
        3,
    );
    let message = PushMessage {
        id: fixture.message_id,
        target: PushTarget {
            user_id: Some("user-1".into()),
            channels: vec![PushChannel::Sse],
            ..PushTarget::default()
        },
        data: BTreeMap::from([("event_type".into(), json!(fixture.event_type))]),
        ..PushMessage::default()
    };
    let result = adapter.send(&message, 10).await.expect("send");
    assert_eq!(result.metadata["connections_sent"], 2);
    let first = user_a.next().await.expect("user A event");
    assert!(first.contains(&format!("id: {}", fixture.expected_event_id)));
    assert!(user_b.next().await.is_some());
    assert!(organization.try_next().is_err());

    let organization_message = PushMessage {
        target: PushTarget {
            organization_id: Some("org-1".into()),
            channels: vec![PushChannel::Sse],
            ..PushTarget::default()
        },
        ..message
    };
    adapter
        .send(&organization_message, 11)
        .await
        .expect("organization send");
    assert!(organization.next().await.is_some());
}

#[test]
fn language_neutral_lifecycle_mapping_and_redaction_contract() {
    let fixture = fixture().lifecycle_error_mappings;
    for (code, expected) in fixture.fcm {
        assert_eq!(reason_from_fcm_error(&code), expected);
    }
    for (code, expected) in fixture.apns {
        assert_eq!(reason_from_apns_error(&code), expected);
    }
    let event = TokenInvalidationEvent {
        token: "secret-device-token-that-is-longer-than-twenty".into(),
        channel: PushChannel::Fcm,
        reason: TokenInvalidationReason::Unregistered,
        reason_detail: None,
        device_id: None,
        user_id: None,
        organization_id: None,
        error_code: None,
        error_message: None,
        occurred_at_ms: 1,
        correlation_id: None,
    };
    let payload = event.redacted_payload();
    assert!(payload.get("token").is_none());
    assert_eq!(
        payload["token_fingerprint"].as_str().map(str::len),
        Some(64)
    );
}

#[test]
fn language_neutral_webhook_signature_contract() {
    let fixture = fixture().webhook_signature;
    let signature = WebhookAdapter::sign_payload(fixture.body.as_bytes(), &fixture.secret);
    assert_eq!(signature, fixture.expected);
    assert!(WebhookAdapter::verify_signature(
        fixture.body.as_bytes(),
        &fixture.secret,
        &signature
    ));
    assert!(!WebhookAdapter::verify_signature(
        b"altered",
        &fixture.secret,
        &signature
    ));
}

#[test]
fn webhook_destinations_are_tenant_bound_and_template_safe() {
    let case = fixture().webhook_destination_registry;
    let registry = WebhookDestinationRegistry::parse(&case.configuration).unwrap();
    for [tenant, destination] in case.accepted {
        registry.require(&tenant, &destination).unwrap();
    }
    for [tenant, destination] in case.rejected {
        assert!(registry.require(&tenant, &destination).is_err());
    }
    assert_eq!(registry.templates("org-a").len(), 2);
    assert!(
        WebhookDestinationRegistry::parse("org-a|https://x.test/__MARTY_TOKEN__/__MARTY_TOKEN__")
            .is_err()
    );
    assert!(WebhookDestinationRegistry::parse("org-a|https://user:pass@x.test/hook").is_err());
}

#[test]
fn webhook_destination_registry_reports_when_no_destinations_are_registered() {
    assert!(WebhookDestinationRegistry::default().is_empty());
    assert!(WebhookDestinationRegistry::parse(" ; ").unwrap().is_empty());
    assert!(
        !WebhookDestinationRegistry::parse("org-a|https://x.test/hook")
            .unwrap()
            .is_empty()
    );
}

#[test]
fn webhook_event_signature_binds_headers_and_canonical_payload() {
    let case = fixture().webhook_event_signature;
    let signature = sign_event(
        &case.secret,
        &case.audience,
        &case.event,
        &case.event_id,
        &case.timestamp,
        &case.payload,
    )
    .unwrap();
    assert_eq!(signature, case.expected);
    assert!(verify_event_signature(
        &signature,
        &case.secret,
        &case.audience,
        &case.event,
        &case.event_id,
        &case.timestamp,
        &case.payload,
    ));
    assert!(!verify_event_signature(
        &signature,
        &case.secret,
        &case.audience,
        &case.event,
        "another-event",
        &case.timestamp,
        &case.payload,
    ));
    assert!(
        sign_event(
            "weak",
            &case.audience,
            &case.event,
            &case.event_id,
            &case.timestamp,
            &case.payload,
        )
        .is_err()
    );
}

#[tokio::test]
async fn manager_and_mock_fail_closed_contract() {
    let failures = fixture().failure_contracts;
    let manager = PushManager::default();
    let message = PushMessage {
        id: "missing-adapter".into(),
        target: PushTarget {
            channels: vec![PushChannel::Apns],
            ..PushTarget::default()
        },
        created_at_ms: 1,
        ..PushMessage::default()
    };
    let results = manager.send(&message, None, 2).await;
    assert_eq!(
        results[0].error_code.as_deref(),
        Some(failures.missing_adapter.as_str())
    );

    let expired = PushMessage {
        ttl_seconds: 1,
        ..message.clone()
    };
    let results = manager.send(&expired, None, 1_002).await;
    assert_eq!(
        results[0].error_code.as_deref(),
        Some(failures.expired.as_str())
    );

    let adapter = Arc::new(
        MockPushAdapter::new(
            MockPushConfig {
                invalid_tokens: ["invalid".into()].into(),
                deterministic_outcomes: VecDeque::from([true]),
                ..MockPushConfig::default()
            },
            None,
        )
        .expect("mock"),
    );
    adapter.start().await.expect("start");
    let invalid = PushMessage {
        target: PushTarget {
            device_tokens: vec!["invalid".into()],
            ..PushTarget::default()
        },
        ..PushMessage::default()
    };
    let result = adapter.send(&invalid, 2).await.expect("invalid result");
    assert_eq!(
        result.error_code.as_deref(),
        Some(failures.invalid_token.as_str())
    );
    assert_eq!(adapter.sent_count(), 1);
    adapter
        .assert_sent(Some(1), None, None)
        .expect("count assertion");
    assert!(
        adapter
            .assert_message_sent_to(None, Some("invalid"))
            .is_ok()
    );
}

struct SuccessfulMockHandler;

#[async_trait]
impl MockPushHandler for SuccessfulMockHandler {
    async fn send(&self, message: &PushMessage, now_ms: u64) -> Result<PushResult, PushError> {
        let mut result = PushResult::delivered(&message.id, PushChannel::Fcm, now_ms);
        result
            .metadata
            .insert("custom_handler".into(), Value::Bool(true));
        Ok(result)
    }
}

#[tokio::test]
async fn mock_custom_handler_and_reset_preserve_test_utilities() {
    let adapter = MockPushAdapter::new(MockPushConfig::default(), None).expect("mock");
    adapter.set_custom_handler(Arc::new(SuccessfulMockHandler));
    let result = adapter
        .send(&PushMessage::default(), 10)
        .await
        .expect("custom result");
    assert_eq!(result.metadata["custom_handler"], true);
    assert!(adapter.last_message().is_some());
    adapter.reset();
    assert_eq!(adapter.sent_count(), 0);
}

struct QueueFcmProvider {
    responses: Mutex<VecDeque<Result<FcmProviderResponse, PushError>>>,
}

#[async_trait]
impl FcmProvider for QueueFcmProvider {
    async fn start(&self, _config: &FcmConfig) -> Result<(), PushError> {
        Ok(())
    }

    async fn stop(&self) -> Result<(), PushError> {
        Ok(())
    }

    async fn send(
        &self,
        _config: &FcmConfig,
        _message: &Value,
    ) -> Result<FcmProviderResponse, PushError> {
        self.responses
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .pop_front()
            .unwrap_or_else(|| {
                Err(PushError::ProviderUnavailable(
                    "empty provider queue".into(),
                ))
            })
    }

    async fn health(&self) -> Result<(), PushError> {
        Ok(())
    }
}

#[tokio::test]
async fn fcm_retries_transient_responses_and_rejects_missing_tokens() {
    let failures = fixture().failure_contracts;
    let provider = Arc::new(QueueFcmProvider {
        responses: Mutex::new(VecDeque::from([
            Ok(FcmProviderResponse {
                status_code: 503,
                provider_message_id: None,
                error_code: Some("UNAVAILABLE".into()),
                error_message: Some("retry".into()),
                retry_after_seconds: None,
            }),
            Ok(FcmProviderResponse {
                status_code: 200,
                provider_message_id: Some("provider-id".into()),
                error_code: None,
                error_message: None,
                retry_after_seconds: None,
            }),
        ])),
    });
    let adapter = FcmAdapter::new(
        FcmConfig {
            project_id: "project".into(),
            credentials: Some(FcmCredentialSource::ApplicationDefault),
            initial_backoff_ms: 0,
            max_backoff_ms: 0,
            ..FcmConfig::default()
        },
        provider,
        None,
    )
    .expect("FCM adapter");
    let missing = adapter
        .send(&PushMessage::default(), 1)
        .await
        .expect("missing tokens result");
    assert_eq!(
        missing.error_code.as_deref(),
        Some(failures.missing_fcm_tokens.as_str())
    );
    let message = PushMessage {
        target: PushTarget {
            device_tokens: vec!["token".into()],
            ..PushTarget::default()
        },
        ..PushMessage::default()
    };
    let delivered = adapter.send(&message, 2).await.expect("delivery");
    assert!(delivered.success);
    assert_eq!(delivered.attempt_number, 2);
}

struct QueueWebhookProvider {
    responses: Mutex<VecDeque<Result<WebhookResponse, PushError>>>,
}

#[async_trait]
impl WebhookProvider for QueueWebhookProvider {
    async fn start(&self) -> Result<(), PushError> {
        Ok(())
    }

    async fn stop(&self) -> Result<(), PushError> {
        Ok(())
    }

    async fn post(&self, _request: &WebhookRequest) -> Result<WebhookResponse, PushError> {
        self.responses
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .pop_front()
            .unwrap_or_else(|| {
                Err(PushError::ProviderUnavailable(
                    "empty provider queue".into(),
                ))
            })
    }

    async fn health(&self) -> Result<(), PushError> {
        Ok(())
    }
}

#[tokio::test]
async fn webhook_retries_and_opens_shared_resilience_circuit() {
    let failures = fixture().failure_contracts;
    let provider = Arc::new(QueueWebhookProvider {
        responses: Mutex::new(VecDeque::from([Ok(WebhookResponse {
            status_code: 503,
            body: "unavailable".into(),
            retry_after_seconds: None,
        })])),
    });
    let adapter = WebhookAdapter::new(
        WebhookConfig {
            max_attempts: 1,
            failure_threshold: 1,
            ..WebhookConfig::default()
        },
        provider,
        Vec::new(),
    )
    .expect("webhook adapter");
    let message = PushMessage {
        target: PushTarget {
            webhook_urls: vec!["https://example.test/hook".into()],
            channels: vec![PushChannel::Webhook],
            ..PushTarget::default()
        },
        ..PushMessage::default()
    };
    let first = adapter.send(&message, 1).await.expect("first");
    assert!(!first.success);
    let second = adapter.send(&message, 2).await.expect("second");
    assert_eq!(second.error_code.as_deref(), Some("ALL_ENDPOINTS_FAILED"));
    assert_eq!(
        adapter.circuit_stats()["https://example.test/hook"].state,
        "open"
    );
    let endpoint = WebhookEndpointConfig {
        url: "https://example.test/hook".into(),
        enabled: true,
        ..WebhookEndpointConfig::default()
    };
    let direct = adapter
        .deliver_to_endpoint(&message, &endpoint, 3)
        .await
        .expect("open circuit result");
    assert_eq!(
        direct.error_code.as_deref(),
        Some(failures.open_circuit.as_str())
    );
}

#[tokio::test]
async fn webhook_missing_endpoints_fails_closed() {
    let failures = fixture().failure_contracts;
    let provider = Arc::new(QueueWebhookProvider {
        responses: Mutex::new(VecDeque::new()),
    });
    let adapter = WebhookAdapter::new(WebhookConfig::default(), provider, Vec::new())
        .expect("webhook adapter");
    let result = adapter
        .send(&PushMessage::default(), 1)
        .await
        .expect("missing endpoint result");
    assert_eq!(
        result.error_code.as_deref(),
        Some(failures.missing_webhook_endpoints.as_str())
    );
}
