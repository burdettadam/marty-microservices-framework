//! Canonical session audit events, batches, and provider ports.

use std::collections::{BTreeMap, BTreeSet};
use std::sync::Arc;

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use uuid::Uuid;

use crate::{ManagedSession, SecurityError, SessionConfiguration, SessionEventType};

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum EventSeverity {
    Low,
    Medium,
    High,
    Critical,
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct SessionEventMetadata {
    pub ip_address: Option<String>,
    pub user_agent: Option<String>,
    pub request_id: Option<String>,
    pub client_fingerprint: Option<String>,
    #[serde(default)]
    pub geo_location: BTreeMap<String, Value>,
    #[serde(default)]
    pub device_info: BTreeMap<String, Value>,
    pub application_id: Option<String>,
    pub service_name: Option<String>,
    pub environment: Option<String>,
    #[serde(default)]
    pub custom_data: BTreeMap<String, Value>,
}

impl SessionEventMetadata {
    #[must_use]
    pub fn with_custom_data(mut self, key: impl Into<String>, value: Value) -> Self {
        self.custom_data.insert(key.into(), value);
        self
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum SessionEventDetails {
    None,
    Access {
        action: String,
    },
    Expiration {
        reason: String,
    },
    SecurityViolation {
        violation_type: String,
        risk_score: f64,
        recommended_action: String,
    },
    Authentication {
        auth_method: String,
        mfa_used: bool,
        device_trusted: bool,
    },
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SessionEvent {
    pub event_id: String,
    pub session_id: String,
    pub user_id: String,
    pub event_type: SessionEventType,
    pub timestamp_ms: u64,
    pub message: Option<String>,
    pub severity: EventSeverity,
    pub metadata: SessionEventMetadata,
    pub correlation_id: Option<String>,
    pub parent_event_id: Option<String>,
    #[serde(default)]
    pub before_state: BTreeMap<String, Value>,
    #[serde(default)]
    pub after_state: BTreeMap<String, Value>,
    #[serde(default)]
    pub event_data: BTreeMap<String, Value>,
    pub details: SessionEventDetails,
    pub processed: bool,
    pub processed_at_ms: Option<u64>,
    #[serde(default)]
    pub processing_errors: Vec<String>,
}

impl SessionEvent {
    #[must_use]
    #[allow(clippy::too_many_arguments)]
    pub fn create_at(
        session_id: impl Into<String>,
        user_id: impl Into<String>,
        event_type: SessionEventType,
        message: Option<String>,
        severity: EventSeverity,
        metadata: SessionEventMetadata,
        details: SessionEventDetails,
        now_ms: u64,
    ) -> Self {
        Self {
            event_id: Uuid::new_v4().to_string(),
            session_id: session_id.into(),
            user_id: user_id.into(),
            event_type,
            timestamp_ms: now_ms,
            message,
            severity,
            metadata,
            correlation_id: None,
            parent_event_id: None,
            before_state: BTreeMap::new(),
            after_state: BTreeMap::new(),
            event_data: BTreeMap::new(),
            details,
            processed: false,
            processed_at_ms: None,
            processing_errors: Vec::new(),
        }
    }

    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.event_id.trim().is_empty()
            || self.session_id.trim().is_empty()
            || self.user_id.trim().is_empty()
        {
            return Err(SecurityError::InvalidConfiguration(
                "session event identifiers cannot be empty".into(),
            ));
        }
        match (&self.event_type, &self.details) {
            (
                SessionEventType::AuthenticationSuccess
                | SessionEventType::AuthenticationFailure
                | SessionEventType::MfaCompleted,
                SessionEventDetails::Authentication { .. },
            )
            | (
                SessionEventType::SecurityViolation,
                SessionEventDetails::SecurityViolation { .. },
            )
            | (SessionEventType::SessionExpired, SessionEventDetails::Expiration { .. })
            | (SessionEventType::SessionAccessed, SessionEventDetails::Access { .. }) => {}
            (event_type, SessionEventDetails::None)
                if !matches!(
                    event_type,
                    SessionEventType::AuthenticationSuccess
                        | SessionEventType::AuthenticationFailure
                        | SessionEventType::MfaCompleted
                        | SessionEventType::SecurityViolation
                        | SessionEventType::SessionExpired
                        | SessionEventType::SessionAccessed
                ) => {}
            _ => {
                return Err(SecurityError::InvalidConfiguration(
                    "session event type and details do not match".into(),
                ));
            }
        }
        if let SessionEventDetails::SecurityViolation { risk_score, .. } = &self.details
            && (!(0.0..=1.0).contains(risk_score) || !risk_score.is_finite())
        {
            return Err(SecurityError::InvalidConfiguration(
                "session security risk score must be between zero and one".into(),
            ));
        }
        if self.processed != self.processed_at_ms.is_some() {
            return Err(SecurityError::InvalidConfiguration(
                "processed session event requires a processing timestamp".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn mark_processed_at(mut self, errors: Vec<String>, now_ms: u64) -> Self {
        self.processed = true;
        self.processed_at_ms = Some(now_ms);
        self.processing_errors = errors;
        self
    }

    #[must_use]
    pub fn with_correlation_id(mut self, correlation_id: impl Into<String>) -> Self {
        self.correlation_id = Some(correlation_id.into());
        self
    }

    #[must_use]
    pub fn with_state_change(
        mut self,
        before_state: BTreeMap<String, Value>,
        after_state: BTreeMap<String, Value>,
    ) -> Self {
        self.before_state = before_state;
        self.after_state = after_state;
        self
    }

    #[must_use]
    pub fn is_security_event(&self) -> bool {
        matches!(
            self.event_type,
            SessionEventType::SecurityViolation
                | SessionEventType::IpAddressChanged
                | SessionEventType::UserAgentChanged
                | SessionEventType::ConcurrentSessionDetected
                | SessionEventType::SuspiciousActivity
                | SessionEventType::AuthenticationFailure
                | SessionEventType::SessionTerminated
        )
    }

    #[must_use]
    pub fn requires_immediate_attention(&self) -> bool {
        self.severity >= EventSeverity::High || self.is_security_event()
    }

    #[must_use]
    pub fn created(session_id: &str, user_id: &str, now_ms: u64) -> Self {
        Self::create_at(
            session_id,
            user_id,
            SessionEventType::SessionCreated,
            Some(format!("Session created for user {user_id}")),
            EventSeverity::Low,
            SessionEventMetadata::default(),
            SessionEventDetails::None,
            now_ms,
        )
    }

    #[must_use]
    pub fn accessed(session_id: &str, user_id: &str, action: &str, now_ms: u64) -> Self {
        Self::create_at(
            session_id,
            user_id,
            SessionEventType::SessionAccessed,
            Some(format!("Session {action} by user {user_id}")),
            EventSeverity::Low,
            SessionEventMetadata::default(),
            SessionEventDetails::Access {
                action: action.into(),
            },
            now_ms,
        )
    }

    #[must_use]
    pub fn expired(session_id: &str, user_id: &str, reason: &str, now_ms: u64) -> Self {
        Self::create_at(
            session_id,
            user_id,
            SessionEventType::SessionExpired,
            Some(format!(
                "Session expired for user {user_id} due to {reason}"
            )),
            EventSeverity::Medium,
            SessionEventMetadata::default(),
            SessionEventDetails::Expiration {
                reason: reason.into(),
            },
            now_ms,
        )
    }

    #[must_use]
    pub fn security_violation(
        session_id: &str,
        user_id: &str,
        violation_type: &str,
        risk_score: f64,
        now_ms: u64,
    ) -> Self {
        Self::create_at(
            session_id,
            user_id,
            SessionEventType::SecurityViolation,
            Some(format!("Security violation detected: {violation_type}")),
            EventSeverity::High,
            SessionEventMetadata::default(),
            SessionEventDetails::SecurityViolation {
                violation_type: violation_type.into(),
                risk_score,
                recommended_action: String::new(),
            },
            now_ms,
        )
    }

    #[must_use]
    pub fn authentication(
        session_id: &str,
        user_id: &str,
        event_type: SessionEventType,
        auth_method: &str,
        mfa_used: bool,
        now_ms: u64,
    ) -> Self {
        let severity = if event_type == SessionEventType::AuthenticationFailure {
            EventSeverity::Medium
        } else {
            EventSeverity::Low
        };
        Self::create_at(
            session_id,
            user_id,
            event_type,
            Some(format!("Authentication event for user {user_id}")),
            severity,
            SessionEventMetadata::default(),
            SessionEventDetails::Authentication {
                auth_method: auth_method.into(),
                mfa_used,
                device_trusted: false,
            },
            now_ms,
        )
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SessionEventBatch {
    pub batch_id: String,
    pub events: Vec<SessionEvent>,
    pub created_at_ms: u64,
    pub processed: bool,
    pub processed_at_ms: Option<u64>,
}

impl SessionEventBatch {
    pub fn create_at(events: Vec<SessionEvent>, now_ms: u64) -> Result<Self, SecurityError> {
        if events.is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "session event batch cannot be empty".into(),
            ));
        }
        Ok(Self {
            batch_id: generate_batch_id(),
            events,
            created_at_ms: now_ms,
            processed: false,
            processed_at_ms: None,
        })
    }

    #[must_use]
    pub fn mark_processed_at(mut self, now_ms: u64) -> Self {
        self.processed = true;
        self.processed_at_ms = Some(now_ms);
        self
    }

    #[must_use]
    pub fn events_by_type(&self, event_type: SessionEventType) -> Vec<&SessionEvent> {
        self.events
            .iter()
            .filter(|event| event.event_type == event_type)
            .collect()
    }

    #[must_use]
    pub fn security_events(&self) -> Vec<&SessionEvent> {
        self.events
            .iter()
            .filter(|event| event.is_security_event())
            .collect()
    }

    #[must_use]
    pub fn high_severity_events(&self) -> Vec<&SessionEvent> {
        self.events
            .iter()
            .filter(|event| event.severity >= EventSeverity::High)
            .collect()
    }

    #[must_use]
    pub fn unprocessed_events(&self) -> Vec<&SessionEvent> {
        self.events
            .iter()
            .filter(|event| !event.processed)
            .collect()
    }

    #[must_use]
    pub fn session_count(&self) -> usize {
        self.events
            .iter()
            .map(|event| &event.session_id)
            .collect::<BTreeSet<_>>()
            .len()
    }

    #[must_use]
    pub fn user_count(&self) -> usize {
        self.events
            .iter()
            .map(|event| &event.user_id)
            .collect::<BTreeSet<_>>()
            .len()
    }
}

#[must_use]
pub fn generate_event_id() -> String {
    Uuid::new_v4().to_string()
}

#[must_use]
pub fn generate_batch_id() -> String {
    format!("batch_{}", Uuid::new_v4())
}

#[must_use]
pub fn generate_correlation_id() -> String {
    format!("corr_{}", Uuid::new_v4())
}

#[async_trait]
pub trait ManagedSessionStore: Send + Sync {
    async fn create(&self, session: &ManagedSession) -> Result<(), SecurityError>;
    async fn get(&self, session_id: &str) -> Result<Option<ManagedSession>, SecurityError>;
    async fn replace(&self, session: &ManagedSession) -> Result<(), SecurityError>;
    async fn delete(&self, session_id: &str) -> Result<bool, SecurityError>;
    async fn active_for_user(&self, user_id: &str) -> Result<Vec<ManagedSession>, SecurityError>;
    async fn expired_before(
        &self,
        before_ms: u64,
        limit: usize,
    ) -> Result<Vec<ManagedSession>, SecurityError>;

    async fn health_check(&self) -> Result<(), SecurityError> {
        Ok(())
    }
}

#[async_trait]
pub trait SessionEventPublisher: Send + Sync {
    async fn publish(&self, event: &SessionEvent) -> Result<(), SecurityError>;
    async fn publish_batch(&self, batch: &SessionEventBatch) -> Result<(), SecurityError>;
}

#[async_trait]
pub trait SessionAnalyticsProvider: Send + Sync {
    async fn record(&self, event: &SessionEvent) -> Result<(), SecurityError>;
}

#[async_trait]
pub trait SessionArchiveProvider: Send + Sync {
    async fn archive(&self, sessions: &[ManagedSession]) -> Result<(), SecurityError>;
}

#[derive(Default)]
pub struct SessionProviders {
    pub store: Option<Arc<dyn ManagedSessionStore>>,
    pub events: Option<Arc<dyn SessionEventPublisher>>,
    pub analytics: Option<Arc<dyn SessionAnalyticsProvider>>,
    pub archive: Option<Arc<dyn SessionArchiveProvider>>,
}

impl SessionProviders {
    pub fn validate(&self, configuration: &SessionConfiguration) -> Result<(), SecurityError> {
        configuration.validate()?;
        let mut missing = Vec::new();
        if configuration.enable_session_management && self.store.is_none() {
            missing.push("managed_session_store");
        }
        if configuration.propagate_session_events && self.events.is_none() {
            missing.push("session_event_publisher");
        }
        if configuration.enable_session_analytics && self.analytics.is_none() {
            missing.push("session_analytics_provider");
        }
        if configuration.cleanup.archive_old_sessions && self.archive.is_none() {
            missing.push("session_archive_provider");
        }
        if missing.is_empty() {
            Ok(())
        } else {
            Err(SecurityError::RequiredProvidersUnavailable(missing))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture() -> Value {
        serde_json::from_str(include_str!(
            "../../../contracts/identity-session-behavior.json"
        ))
        .expect("valid session behavioral fixture")
    }

    #[test]
    fn language_neutral_event_and_batch_behavior() {
        let fixture = fixture();
        let case = &fixture["events"];
        let created = SessionEvent::created("session-1", "user-1", 1_000);
        let violation =
            SessionEvent::security_violation("session-1", "user-1", "ip_changed", 0.8, 2_000);
        let failed = SessionEvent::authentication(
            "session-2",
            "user-2",
            SessionEventType::AuthenticationFailure,
            "password",
            false,
            3_000,
        );
        created.validate().expect("created event");
        violation.validate().expect("violation event");
        failed.validate().expect("authentication event");
        assert!(violation.requires_immediate_attention());
        assert!(failed.is_security_event());
        let batch = SessionEventBatch::create_at(vec![created, violation, failed], 4_000)
            .expect("event batch");
        assert_eq!(
            batch.security_events().len(),
            usize::try_from(
                case["security_event_count"]
                    .as_u64()
                    .expect("security count"),
            )
            .expect("security count fits usize")
        );
        assert_eq!(
            batch.session_count(),
            usize::try_from(
                case["unique_session_count"]
                    .as_u64()
                    .expect("session count"),
            )
            .expect("session count fits usize")
        );
        assert_eq!(
            batch.user_count(),
            usize::try_from(case["unique_user_count"].as_u64().expect("user count"))
                .expect("user count fits usize")
        );
        assert!(
            batch
                .batch_id
                .starts_with(case["batch_id_prefix"].as_str().expect("batch prefix"))
        );
        assert!(
            generate_correlation_id().starts_with(
                case["correlation_id_prefix"]
                    .as_str()
                    .expect("correlation prefix")
            )
        );
    }

    #[test]
    fn mismatched_event_details_and_missing_providers_fail_closed() {
        let mut event = SessionEvent::created("session", "user", 0);
        event.event_type = SessionEventType::AuthenticationFailure;
        assert!(event.validate().is_err());
        let providers = SessionProviders::default();
        assert!(matches!(
            providers.validate(&SessionConfiguration::development().expect("configuration")),
            Err(SecurityError::RequiredProvidersUnavailable(_))
        ));
    }
}
