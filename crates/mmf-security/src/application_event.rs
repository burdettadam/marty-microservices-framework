//! Purpose-bound authentication and replay protection for internal events.
//!
//! The verifier is transport-neutral: HTTP headers and gRPC metadata are
//! normalized into the same map, while replay persistence is supplied through
//! a small atomic consume port. Callers may authenticate first, durably reserve
//! work, and consume replay state immediately before external side effects.

use std::collections::BTreeMap;

use async_trait::async_trait;
use chrono::{DateTime, SecondsFormat, Utc};
use hmac::{Hmac, KeyInit, Mac};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use thiserror::Error;
use uuid::Uuid;

type HmacSha256 = Hmac<Sha256>;

pub const APPLICATION_EVENT_PRODUCER: &str = "marty-applicant-service";
pub const APPLICATION_EVENT_AUDIENCE: &str = "marty-flow-application-approved";
pub const APPLICATION_EVENT_SIGNATURE_VERSION: &str = "v1";
pub const APPLICATION_EVENT_REPLAY_KEY_PREFIX: &str = "marty:application-approved:v1:";

pub const HEADER_EVENT_PRODUCER: &str = "x-marty-event-producer";
pub const HEADER_EVENT_AUDIENCE: &str = "x-marty-event-audience";
pub const HEADER_EVENT_ID: &str = "x-marty-event-id";
pub const HEADER_EVENT_TIMESTAMP: &str = "x-marty-event-timestamp";
pub const HEADER_EVENT_SIGNATURE_VERSION: &str = "x-marty-event-signature-version";
pub const HEADER_EVENT_SIGNATURE: &str = "x-marty-event-signature";

const REQUIRED_HEADERS: [&str; 6] = [
    HEADER_EVENT_PRODUCER,
    HEADER_EVENT_AUDIENCE,
    HEADER_EVENT_ID,
    HEADER_EVENT_TIMESTAMP,
    HEADER_EVENT_SIGNATURE_VERSION,
    HEADER_EVENT_SIGNATURE,
];

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ApplicationEventEvidence {
    pub producer: String,
    pub audience: String,
    pub event_id_sha256: String,
    pub payload_sha256: String,
    pub authenticated_at: String,
}

impl ApplicationEventEvidence {
    #[must_use]
    pub fn replay_key(&self) -> String {
        format!(
            "{APPLICATION_EVENT_REPLAY_KEY_PREFIX}{}",
            self.event_id_sha256
        )
    }
}

#[derive(Clone, Debug)]
pub struct ApplicationEventAuthenticator {
    secret: Vec<u8>,
    max_age_seconds: i64,
    replay_ttl_seconds: u64,
}

impl ApplicationEventAuthenticator {
    pub fn new(
        secret: impl AsRef<[u8]>,
        max_age_seconds: i64,
        replay_ttl_seconds: u64,
    ) -> Result<Self, ApplicationEventAuthError> {
        let secret = secret.as_ref();
        if secret.len() < 32 || max_age_seconds <= 0 {
            return Err(ApplicationEventAuthError::Configuration);
        }
        let max_age =
            u64::try_from(max_age_seconds).map_err(|_| ApplicationEventAuthError::Configuration)?;
        if replay_ttl_seconds < max_age {
            return Err(ApplicationEventAuthError::Configuration);
        }
        Ok(Self {
            secret: secret.to_vec(),
            max_age_seconds,
            replay_ttl_seconds,
        })
    }

    #[must_use]
    pub const fn max_age_seconds(&self) -> i64 {
        self.max_age_seconds
    }

    #[must_use]
    pub const fn replay_ttl_seconds(&self) -> u64 {
        self.replay_ttl_seconds
    }

    pub fn sign(
        &self,
        event: &Value,
        event_id: &str,
        signed_at: i64,
    ) -> Result<BTreeMap<String, String>, ApplicationEventAuthError> {
        Uuid::parse_str(event_id).map_err(|_| ApplicationEventAuthError::InvalidEventId)?;
        let payload_sha256 = sha256_hex(&canonical_event_payload(event)?);
        let timestamp = signed_at.to_string();
        let signature = self.signature(event_id, &timestamp, &payload_sha256)?;
        Ok(BTreeMap::from([
            (
                HEADER_EVENT_PRODUCER.into(),
                APPLICATION_EVENT_PRODUCER.into(),
            ),
            (
                HEADER_EVENT_AUDIENCE.into(),
                APPLICATION_EVENT_AUDIENCE.into(),
            ),
            (HEADER_EVENT_ID.into(), event_id.into()),
            (HEADER_EVENT_TIMESTAMP.into(), timestamp),
            (
                HEADER_EVENT_SIGNATURE_VERSION.into(),
                APPLICATION_EVENT_SIGNATURE_VERSION.into(),
            ),
            (HEADER_EVENT_SIGNATURE.into(), signature),
        ]))
    }

    pub fn sign_new(
        &self,
        event: &Value,
        signed_at: i64,
    ) -> Result<BTreeMap<String, String>, ApplicationEventAuthError> {
        self.sign(event, &Uuid::new_v4().to_string(), signed_at)
    }

    pub fn authenticate(
        &self,
        event: &Value,
        metadata: &BTreeMap<String, String>,
        now: i64,
    ) -> Result<ApplicationEventEvidence, ApplicationEventAuthError> {
        let metadata = normalize_metadata(metadata);
        if REQUIRED_HEADERS
            .iter()
            .any(|name| metadata.get(*name).is_none_or(String::is_empty))
        {
            return Err(ApplicationEventAuthError::MissingAuthentication);
        }
        if metadata.get(HEADER_EVENT_PRODUCER).map(String::as_str)
            != Some(APPLICATION_EVENT_PRODUCER)
            || metadata.get(HEADER_EVENT_AUDIENCE).map(String::as_str)
                != Some(APPLICATION_EVENT_AUDIENCE)
        {
            return Err(ApplicationEventAuthError::WrongPurpose);
        }
        if metadata
            .get(HEADER_EVENT_SIGNATURE_VERSION)
            .map(String::as_str)
            != Some(APPLICATION_EVENT_SIGNATURE_VERSION)
        {
            return Err(ApplicationEventAuthError::UnsupportedVersion);
        }

        let event_id = metadata
            .get(HEADER_EVENT_ID)
            .ok_or(ApplicationEventAuthError::MissingAuthentication)?;
        Uuid::parse_str(event_id).map_err(|_| ApplicationEventAuthError::InvalidEnvelope)?;
        let signed_at = metadata
            .get(HEADER_EVENT_TIMESTAMP)
            .ok_or(ApplicationEventAuthError::MissingAuthentication)?
            .parse::<i64>()
            .map_err(|_| ApplicationEventAuthError::InvalidEnvelope)?;
        if now.abs_diff(signed_at) > self.max_age_seconds.unsigned_abs() {
            return Err(ApplicationEventAuthError::StaleEvent);
        }

        let payload_sha256 = sha256_hex(&canonical_event_payload(event)?);
        let supplied = metadata
            .get(HEADER_EVENT_SIGNATURE)
            .ok_or(ApplicationEventAuthError::MissingAuthentication)?;
        self.verify_signature(event_id, &signed_at.to_string(), &payload_sha256, supplied)?;

        let authenticated_at = DateTime::<Utc>::from_timestamp(now, 0)
            .ok_or(ApplicationEventAuthError::InvalidEnvelope)?
            .to_rfc3339_opts(SecondsFormat::Secs, false);
        Ok(ApplicationEventEvidence {
            producer: APPLICATION_EVENT_PRODUCER.into(),
            audience: APPLICATION_EVENT_AUDIENCE.into(),
            event_id_sha256: sha256_hex(event_id.as_bytes()),
            payload_sha256,
            authenticated_at,
        })
    }

    pub async fn consume(
        &self,
        evidence: &ApplicationEventEvidence,
        replay_store: &dyn ApplicationEventReplayStore,
    ) -> Result<(), ApplicationEventAuthError> {
        let consumed = replay_store
            .consume(
                &evidence.replay_key(),
                &evidence.payload_sha256,
                self.replay_ttl_seconds,
            )
            .await
            .map_err(|_| ApplicationEventAuthError::ReplayStoreUnavailable)?;
        if consumed {
            Ok(())
        } else {
            Err(ApplicationEventAuthError::ReplayedEvent)
        }
    }

    pub async fn authenticate_and_consume(
        &self,
        event: &Value,
        metadata: &BTreeMap<String, String>,
        now: i64,
        replay_store: &dyn ApplicationEventReplayStore,
    ) -> Result<ApplicationEventEvidence, ApplicationEventAuthError> {
        let evidence = self.authenticate(event, metadata, now)?;
        self.consume(&evidence, replay_store).await?;
        Ok(evidence)
    }

    fn signature(
        &self,
        event_id: &str,
        timestamp: &str,
        payload_sha256: &str,
    ) -> Result<String, ApplicationEventAuthError> {
        let input = [
            APPLICATION_EVENT_SIGNATURE_VERSION,
            APPLICATION_EVENT_PRODUCER,
            APPLICATION_EVENT_AUDIENCE,
            event_id,
            timestamp,
            payload_sha256,
        ]
        .join("\n");
        let mut mac = HmacSha256::new_from_slice(&self.secret)
            .map_err(|_| ApplicationEventAuthError::Configuration)?;
        mac.update(input.as_bytes());
        Ok(hex_encode(&mac.finalize().into_bytes()))
    }

    fn verify_signature(
        &self,
        event_id: &str,
        timestamp: &str,
        payload_sha256: &str,
        supplied: &str,
    ) -> Result<(), ApplicationEventAuthError> {
        let supplied =
            decode_hex_32(supplied).ok_or(ApplicationEventAuthError::InvalidSignature)?;
        let input = [
            APPLICATION_EVENT_SIGNATURE_VERSION,
            APPLICATION_EVENT_PRODUCER,
            APPLICATION_EVENT_AUDIENCE,
            event_id,
            timestamp,
            payload_sha256,
        ]
        .join("\n");
        let mut mac = HmacSha256::new_from_slice(&self.secret)
            .map_err(|_| ApplicationEventAuthError::Configuration)?;
        mac.update(input.as_bytes());
        mac.verify_slice(&supplied)
            .map_err(|_| ApplicationEventAuthError::InvalidSignature)
    }
}

#[async_trait]
pub trait ApplicationEventReplayStore: Send + Sync {
    async fn consume(
        &self,
        key: &str,
        payload_sha256: &str,
        ttl_seconds: u64,
    ) -> Result<bool, ApplicationEventReplayStoreError>;
}

#[derive(Clone, Copy, Debug, Error)]
#[error("application event replay store is unavailable")]
pub struct ApplicationEventReplayStoreError;

#[derive(Clone, Copy, Debug, Eq, Error, PartialEq)]
pub enum ApplicationEventAuthError {
    #[error("application event authentication configuration is invalid")]
    Configuration,
    #[error("application event payload is not canonicalizable")]
    InvalidPayload,
    #[error("application event id must be a UUID")]
    InvalidEventId,
    #[error("application event authentication is required")]
    MissingAuthentication,
    #[error("application event producer or audience is invalid")]
    WrongPurpose,
    #[error("application event signature version is unsupported")]
    UnsupportedVersion,
    #[error("application event id or timestamp is invalid")]
    InvalidEnvelope,
    #[error("application event is outside its freshness window")]
    StaleEvent,
    #[error("application event signature is invalid")]
    InvalidSignature,
    #[error("application event was already consumed")]
    ReplayedEvent,
    #[error("application event replay store is unavailable")]
    ReplayStoreUnavailable,
}

impl ApplicationEventAuthError {
    #[must_use]
    pub const fn code(self) -> &'static str {
        match self {
            Self::Configuration => "configuration_error",
            Self::InvalidPayload => "invalid_payload",
            Self::InvalidEventId => "invalid_event_id",
            Self::MissingAuthentication => "missing_authentication",
            Self::WrongPurpose => "wrong_purpose",
            Self::UnsupportedVersion => "unsupported_version",
            Self::InvalidEnvelope => "invalid_envelope",
            Self::StaleEvent => "stale_event",
            Self::InvalidSignature => "invalid_signature",
            Self::ReplayedEvent => "replayed_event",
            Self::ReplayStoreUnavailable => "replay_store_unavailable",
        }
    }
}

pub fn canonical_event_payload(event: &Value) -> Result<Vec<u8>, ApplicationEventAuthError> {
    if !event.is_object() {
        return Err(ApplicationEventAuthError::InvalidPayload);
    }
    serde_json::to_vec(&sorted_json(event)).map_err(|_| ApplicationEventAuthError::InvalidPayload)
}

fn sorted_json(value: &Value) -> Value {
    match value {
        Value::Object(object) => {
            let mut keys = object.keys().collect::<Vec<_>>();
            keys.sort_unstable();
            let mut sorted = serde_json::Map::with_capacity(object.len());
            for key in keys {
                sorted.insert(key.clone(), sorted_json(&object[key]));
            }
            Value::Object(sorted)
        }
        Value::Array(values) => Value::Array(values.iter().map(sorted_json).collect()),
        scalar => scalar.clone(),
    }
}

fn normalize_metadata(metadata: &BTreeMap<String, String>) -> BTreeMap<String, String> {
    metadata
        .iter()
        .map(|(key, value)| (key.to_ascii_lowercase(), value.trim().to_owned()))
        .collect()
}

fn sha256_hex(input: &[u8]) -> String {
    hex_encode(&Sha256::digest(input))
}

fn hex_encode(input: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut encoded = String::with_capacity(input.len() * 2);
    for byte in input {
        encoded.push(char::from(HEX[usize::from(byte >> 4)]));
        encoded.push(char::from(HEX[usize::from(byte & 0x0f)]));
    }
    encoded
}

fn decode_hex_32(input: &str) -> Option<[u8; 32]> {
    let bytes = input.as_bytes();
    if bytes.len() != 64 {
        return None;
    }
    let mut decoded = [0_u8; 32];
    for (index, pair) in bytes.chunks_exact(2).enumerate() {
        decoded[index] = (hex_value(pair[0])? << 4) | hex_value(pair[1])?;
    }
    Some(decoded)
}

const fn hex_value(value: u8) -> Option<u8> {
    match value {
        b'0'..=b'9' => Some(value - b'0'),
        b'a'..=b'f' => Some(value - b'a' + 10),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use std::sync::Arc;

    use serde::Deserialize;
    use tokio::sync::Mutex;

    use super::*;

    #[derive(Deserialize)]
    struct Contract {
        schema_version: u32,
        producer: String,
        audience: String,
        signature_version: String,
        secret: String,
        event_id: String,
        signed_at: i64,
        event: Value,
        canonical_payload: String,
        payload_sha256: String,
        event_id_sha256: String,
        signature: String,
        authenticated_at: String,
        max_age_seconds: i64,
        replay_ttl_seconds: u64,
        replay_key_prefix: String,
        failure_codes: Vec<String>,
    }

    #[derive(Default)]
    struct MemoryReplayStore {
        values: Arc<Mutex<BTreeMap<String, String>>>,
        unavailable: bool,
    }

    #[async_trait]
    impl ApplicationEventReplayStore for MemoryReplayStore {
        async fn consume(
            &self,
            key: &str,
            payload_sha256: &str,
            _ttl_seconds: u64,
        ) -> Result<bool, ApplicationEventReplayStoreError> {
            if self.unavailable {
                return Err(ApplicationEventReplayStoreError);
            }
            let mut values = self.values.lock().await;
            if values.contains_key(key) {
                return Ok(false);
            }
            values.insert(key.into(), payload_sha256.into());
            Ok(true)
        }
    }

    fn contract() -> Contract {
        serde_json::from_str(include_str!(
            "../../../contracts/application-event-auth-behavior.json"
        ))
        .expect("valid application event contract")
    }

    fn authenticator(contract: &Contract) -> ApplicationEventAuthenticator {
        ApplicationEventAuthenticator::new(
            contract.secret.as_bytes(),
            contract.max_age_seconds,
            contract.replay_ttl_seconds,
        )
        .expect("valid authenticator")
    }

    #[test]
    fn canonical_signature_and_minimized_evidence_match_shared_vector() {
        let contract = contract();
        assert_eq!(contract.schema_version, 1);
        assert_eq!(contract.producer, APPLICATION_EVENT_PRODUCER);
        assert_eq!(contract.audience, APPLICATION_EVENT_AUDIENCE);
        assert_eq!(
            contract.signature_version,
            APPLICATION_EVENT_SIGNATURE_VERSION
        );
        assert_eq!(
            contract.replay_key_prefix,
            APPLICATION_EVENT_REPLAY_KEY_PREFIX
        );
        assert_eq!(
            String::from_utf8(canonical_event_payload(&contract.event).expect("canonical"))
                .expect("UTF-8"),
            contract.canonical_payload
        );

        let auth = authenticator(&contract);
        let metadata = auth
            .sign(&contract.event, &contract.event_id, contract.signed_at)
            .expect("signed");
        assert_eq!(metadata[HEADER_EVENT_SIGNATURE], contract.signature);
        let evidence = auth
            .authenticate(&contract.event, &metadata, contract.signed_at)
            .expect("authenticated");
        assert_eq!(evidence.payload_sha256, contract.payload_sha256);
        assert_eq!(evidence.event_id_sha256, contract.event_id_sha256);
        assert_eq!(evidence.authenticated_at, contract.authenticated_at);
        assert!(
            !serde_json::to_string(&evidence)
                .expect("evidence")
                .contains("application-1")
        );
    }

    #[tokio::test]
    async fn tampering_freshness_purpose_and_replay_fail_closed() {
        let contract = contract();
        let auth = authenticator(&contract);
        let metadata = auth
            .sign(&contract.event, &contract.event_id, contract.signed_at)
            .expect("signed");

        let mut tampered = contract.event.clone();
        tampered["organization_id"] = Value::String("org-attacker".into());
        assert_eq!(
            auth.authenticate(&tampered, &metadata, contract.signed_at),
            Err(ApplicationEventAuthError::InvalidSignature)
        );
        assert_eq!(
            auth.authenticate(
                &contract.event,
                &metadata,
                contract.signed_at + contract.max_age_seconds + 1
            ),
            Err(ApplicationEventAuthError::StaleEvent)
        );
        let mut wrong = metadata.clone();
        wrong.insert(HEADER_EVENT_AUDIENCE.into(), "other".into());
        assert_eq!(
            auth.authenticate(&contract.event, &wrong, contract.signed_at),
            Err(ApplicationEventAuthError::WrongPurpose)
        );

        let evidence = auth
            .authenticate(&contract.event, &metadata, contract.signed_at)
            .expect("authenticated");
        let store = MemoryReplayStore::default();
        auth.consume(&evidence, &store)
            .await
            .expect("first consume");
        assert_eq!(
            auth.consume(&evidence, &store).await,
            Err(ApplicationEventAuthError::ReplayedEvent)
        );
    }

    #[tokio::test]
    async fn shared_store_race_has_one_winner_and_unavailability_is_explicit() {
        let contract = contract();
        let auth = authenticator(&contract);
        let metadata = auth
            .sign(&contract.event, &contract.event_id, contract.signed_at)
            .expect("signed");
        let evidence = auth
            .authenticate(&contract.event, &metadata, contract.signed_at)
            .expect("authenticated");
        let store = Arc::new(MemoryReplayStore::default());
        let (left, right) = tokio::join!(
            auth.consume(&evidence, store.as_ref()),
            auth.consume(&evidence, store.as_ref())
        );
        assert_eq!(usize::from(left.is_ok()) + usize::from(right.is_ok()), 1);

        let unavailable = MemoryReplayStore {
            unavailable: true,
            ..MemoryReplayStore::default()
        };
        assert_eq!(
            auth.consume(&evidence, &unavailable).await,
            Err(ApplicationEventAuthError::ReplayStoreUnavailable)
        );
    }

    #[test]
    fn configuration_and_failure_codes_are_stable() {
        let contract = contract();
        assert_eq!(
            ApplicationEventAuthenticator::new("short", 60, 300)
                .expect_err("short key")
                .code(),
            "configuration_error"
        );
        assert_eq!(
            ApplicationEventAuthenticator::new(&contract.secret, 120, 60)
                .expect_err("short TTL")
                .code(),
            "configuration_error"
        );
        let actual = [
            ApplicationEventAuthError::Configuration,
            ApplicationEventAuthError::InvalidPayload,
            ApplicationEventAuthError::InvalidEventId,
            ApplicationEventAuthError::MissingAuthentication,
            ApplicationEventAuthError::WrongPurpose,
            ApplicationEventAuthError::UnsupportedVersion,
            ApplicationEventAuthError::InvalidEnvelope,
            ApplicationEventAuthError::StaleEvent,
            ApplicationEventAuthError::InvalidSignature,
            ApplicationEventAuthError::ReplayedEvent,
            ApplicationEventAuthError::ReplayStoreUnavailable,
        ]
        .map(ApplicationEventAuthError::code);
        assert_eq!(actual.as_slice(), contract.failure_codes);
    }
}
