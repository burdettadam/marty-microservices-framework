//! Rich, deterministic identity-session lifecycle built on the canonical session state.

use std::collections::{BTreeMap, BTreeSet};

use base64::{Engine as _, engine::general_purpose::URL_SAFE_NO_PAD};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use uuid::Uuid;

use crate::{SecurityError, SessionState};

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct SessionTimeout {
    pub idle_timeout_ms: u64,
    pub absolute_timeout_ms: u64,
    pub extend_on_activity: bool,
}

impl Default for SessionTimeout {
    fn default() -> Self {
        Self {
            idle_timeout_ms: 1_800_000,
            absolute_timeout_ms: 28_800_000,
            extend_on_activity: true,
        }
    }
}

impl SessionTimeout {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.idle_timeout_ms == 0
            || self.absolute_timeout_ms == 0
            || self.idle_timeout_ms > self.absolute_timeout_ms
        {
            return Err(SecurityError::InvalidConfiguration(
                "idle timeout must be positive and no greater than absolute timeout".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn expiry_at(&self, created_at_ms: u64, activity_at_ms: u64) -> u64 {
        activity_at_ms
            .saturating_add(self.idle_timeout_ms)
            .min(created_at_ms.saturating_add(self.absolute_timeout_ms))
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SessionSecurityContext {
    pub ip_address: String,
    pub user_agent: Option<String>,
    pub secure_connection: bool,
    pub client_fingerprint: Option<String>,
    #[serde(default)]
    pub location_info: BTreeMap<String, Value>,
    pub created_at_ms: u64,
}

impl SessionSecurityContext {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.ip_address.trim().is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "session security context requires an IP address".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn matches(&self, other: &Self, strict: bool) -> bool {
        self.ip_address == other.ip_address && (!strict || self.user_agent == other.user_agent)
    }
}

#[must_use]
pub fn session_security_violations(
    expected: &SessionSecurityContext,
    current: &SessionSecurityContext,
    detect_hijacking: bool,
) -> Vec<String> {
    if !detect_hijacking {
        return Vec::new();
    }
    let mut violations = Vec::new();
    if expected.ip_address != current.ip_address {
        violations.push("IP address mismatch detected".into());
    }
    if expected.user_agent.is_some()
        && current.user_agent.is_some()
        && expected.user_agent != current.user_agent
    {
        violations.push("User agent mismatch detected".into());
    }
    violations
}

pub fn session_expiration_at(
    timeout: SessionTimeout,
    created_at_ms: u64,
    last_accessed_ms: u64,
    now_ms: u64,
    requested_timeout_ms: Option<u64>,
    default_timeout_ms: u64,
    max_timeout_ms: u64,
) -> Result<u64, SecurityError> {
    timeout.validate()?;
    if default_timeout_ms == 0 || max_timeout_ms == 0 || default_timeout_ms > max_timeout_ms {
        return Err(SecurityError::InvalidConfiguration(
            "default and maximum session timeouts are invalid".into(),
        ));
    }
    let requested = requested_timeout_ms
        .unwrap_or(default_timeout_ms)
        .min(max_timeout_ms);
    if requested == 0 {
        return Err(SecurityError::InvalidConfiguration(
            "session timeout must be positive".into(),
        ));
    }
    Ok(last_accessed_ms
        .saturating_add(timeout.idle_timeout_ms)
        .min(created_at_ms.saturating_add(timeout.absolute_timeout_ms))
        .min(now_ms.saturating_add(requested)))
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SessionActivity {
    pub action: String,
    pub timestamp_ms: u64,
    pub ip_address: Option<String>,
    pub user_agent: Option<String>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

impl SessionActivity {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.action.trim().is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "session activity action cannot be empty".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SessionAttributes {
    #[serde(default)]
    pub attributes: BTreeMap<String, Value>,
    pub created_at_ms: u64,
    pub updated_at_ms: u64,
}

impl SessionAttributes {
    #[must_use]
    pub fn new(now_ms: u64) -> Self {
        Self {
            attributes: BTreeMap::new(),
            created_at_ms: now_ms,
            updated_at_ms: now_ms,
        }
    }

    #[must_use]
    pub fn get(&self, key: &str) -> Option<&Value> {
        self.attributes.get(key)
    }

    #[must_use]
    pub fn contains(&self, key: &str) -> bool {
        self.attributes.contains_key(key)
    }

    #[must_use]
    pub fn with_attribute(mut self, key: impl Into<String>, value: Value, now_ms: u64) -> Self {
        self.attributes.insert(key.into(), value);
        self.updated_at_ms = now_ms;
        self
    }

    #[must_use]
    pub fn without_attribute(mut self, key: &str, now_ms: u64) -> Self {
        self.attributes.remove(key);
        self.updated_at_ms = now_ms;
        self
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ManagedSession {
    pub session_id: String,
    pub user_id: String,
    pub state: SessionState,
    pub security_context: SessionSecurityContext,
    pub timeout: SessionTimeout,
    pub data: SessionAttributes,
    pub created_at_ms: u64,
    pub last_accessed_at_ms: u64,
    pub expires_at_ms: u64,
    pub invalidated_at_ms: Option<u64>,
    #[serde(default)]
    pub activity_log: Vec<SessionActivity>,
    pub auth_method: Option<String>,
    pub mfa_completed: bool,
    #[serde(default)]
    pub roles: BTreeSet<String>,
    #[serde(default)]
    pub permissions: BTreeSet<String>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

impl ManagedSession {
    pub fn create_at(
        user_id: impl Into<String>,
        security_context: SessionSecurityContext,
        timeout: SessionTimeout,
        auth_method: Option<String>,
        roles: BTreeSet<String>,
        permissions: BTreeSet<String>,
        now_ms: u64,
    ) -> Result<Self, SecurityError> {
        security_context.validate()?;
        timeout.validate()?;
        let user_id = user_id.into();
        if user_id.trim().is_empty() {
            return Err(SecurityError::InvalidIdentity(
                "session user ID cannot be empty".into(),
            ));
        }
        let activity = SessionActivity {
            action: "session_created".into(),
            timestamp_ms: now_ms,
            ip_address: Some(security_context.ip_address.clone()),
            user_agent: security_context.user_agent.clone(),
            metadata: BTreeMap::new(),
        };
        Ok(Self {
            session_id: generate_session_id(32),
            user_id,
            state: SessionState::Active,
            security_context,
            timeout,
            data: SessionAttributes::new(now_ms),
            created_at_ms: now_ms,
            last_accessed_at_ms: now_ms,
            expires_at_ms: timeout.expiry_at(now_ms, now_ms),
            invalidated_at_ms: None,
            activity_log: vec![activity],
            auth_method,
            mfa_completed: false,
            roles,
            permissions,
            metadata: BTreeMap::new(),
        })
    }

    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.session_id.trim().is_empty() || self.user_id.trim().is_empty() {
            return Err(SecurityError::InvalidSessionState);
        }
        self.security_context.validate()?;
        self.timeout.validate()?;
        if self.last_accessed_at_ms < self.created_at_ms
            || self.expires_at_ms < self.created_at_ms
            || self
                .invalidated_at_ms
                .is_some_and(|invalidated| invalidated < self.created_at_ms)
        {
            return Err(SecurityError::InvalidSessionState);
        }
        for activity in &self.activity_log {
            activity.validate()?;
        }
        Ok(())
    }

    #[must_use]
    pub fn is_expired_at(&self, now_ms: u64) -> bool {
        now_ms >= self.expires_at_ms
            || now_ms
                >= self
                    .created_at_ms
                    .saturating_add(self.timeout.absolute_timeout_ms)
            || self.state == SessionState::Expired
    }

    #[must_use]
    pub fn is_active_at(&self, now_ms: u64) -> bool {
        self.state == SessionState::Active
            && self.invalidated_at_ms.is_none()
            && !self.is_expired_at(now_ms)
    }

    pub fn access_at(
        &mut self,
        context: Option<&SessionSecurityContext>,
        action: impl Into<String>,
        now_ms: u64,
    ) -> Result<(), SecurityError> {
        if !self.is_active_at(now_ms) {
            return Err(SecurityError::InvalidSessionState);
        }
        if context.is_some_and(|candidate| !self.security_context.matches(candidate, false)) {
            return Err(SecurityError::Unauthorized(
                "session security context mismatch".into(),
            ));
        }
        let absolute_expiry = self
            .created_at_ms
            .saturating_add(self.timeout.absolute_timeout_ms);
        if now_ms >= absolute_expiry {
            self.state = SessionState::Expired;
            self.invalidated_at_ms = Some(now_ms);
            return Err(SecurityError::InvalidSessionState);
        }
        self.last_accessed_at_ms = now_ms;
        if self.timeout.extend_on_activity {
            self.expires_at_ms = self.timeout.expiry_at(self.created_at_ms, now_ms);
        }
        let activity = SessionActivity {
            action: action.into(),
            timestamp_ms: now_ms,
            ip_address: context.map(|value| value.ip_address.clone()),
            user_agent: context.and_then(|value| value.user_agent.clone()),
            metadata: BTreeMap::new(),
        };
        activity.validate()?;
        self.activity_log.push(activity);
        Ok(())
    }

    pub fn invalidate_at(&mut self, reason: impl Into<String>, now_ms: u64) {
        self.state = SessionState::Invalidated;
        self.invalidated_at_ms = Some(now_ms);
        self.activity_log.push(SessionActivity {
            action: "session_invalidated".into(),
            timestamp_ms: now_ms,
            ip_address: None,
            user_agent: None,
            metadata: BTreeMap::from([("reason".into(), Value::String(reason.into()))]),
        });
    }

    pub fn terminate_at(&mut self, reason: impl Into<String>, now_ms: u64) {
        self.state = SessionState::Terminated;
        self.invalidated_at_ms = Some(now_ms);
        self.activity_log.push(SessionActivity {
            action: "session_terminated".into(),
            timestamp_ms: now_ms,
            ip_address: None,
            user_agent: None,
            metadata: BTreeMap::from([("reason".into(), Value::String(reason.into()))]),
        });
    }

    pub fn suspend(&mut self) {
        self.state = SessionState::Suspended;
    }

    pub fn resume(&mut self, now_ms: u64) -> Result<(), SecurityError> {
        if self.state != SessionState::Suspended || self.is_expired_at(now_ms) {
            return Err(SecurityError::InvalidSessionState);
        }
        self.state = SessionState::Active;
        Ok(())
    }

    pub fn set_data(&mut self, key: impl Into<String>, value: Value, now_ms: u64) {
        self.data = self.data.clone().with_attribute(key, value, now_ms);
    }

    pub fn remove_data(&mut self, key: &str, now_ms: u64) {
        self.data = self.data.clone().without_attribute(key, now_ms);
    }

    #[must_use]
    pub fn has_role(&self, role: &str) -> bool {
        self.roles.contains(role)
    }

    #[must_use]
    pub fn has_permission(&self, permission: &str) -> bool {
        self.permissions.contains(permission)
    }

    #[must_use]
    pub fn recent_activity(&self, limit: usize) -> Vec<&SessionActivity> {
        let mut activity: Vec<_> = self.activity_log.iter().collect();
        activity.sort_by_key(|entry| std::cmp::Reverse(entry.timestamp_ms));
        activity.truncate(limit);
        activity
    }
}

#[must_use]
pub fn generate_session_id(entropy_bytes: usize) -> String {
    generate_identifier("", entropy_bytes.max(16))
}

#[must_use]
pub fn generate_session_token(entropy_bytes: usize) -> String {
    generate_identifier("", entropy_bytes.max(32))
}

fn generate_identifier(prefix: &str, entropy_bytes: usize) -> String {
    let mut bytes = Vec::with_capacity(entropy_bytes);
    while bytes.len() < entropy_bytes {
        bytes.extend_from_slice(Uuid::new_v4().as_bytes());
    }
    bytes.truncate(entropy_bytes);
    format!("{prefix}{}", URL_SAFE_NO_PAD.encode(bytes))
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

    fn context(ip: &str, user_agent: &str) -> SessionSecurityContext {
        SessionSecurityContext {
            ip_address: ip.into(),
            user_agent: Some(user_agent.into()),
            secure_connection: true,
            client_fingerprint: None,
            location_info: BTreeMap::new(),
            created_at_ms: 1_000,
        }
    }

    #[test]
    fn language_neutral_lifecycle_and_security_context() {
        let fixture = fixture();
        let timeout_case = &fixture["timeout"];
        let security_case = &fixture["security_context"];
        let primary = context(
            security_case["ip_address"].as_str().expect("IP"),
            security_case["user_agent"].as_str().expect("agent"),
        );
        let other_agent = context(
            security_case["ip_address"].as_str().expect("IP"),
            security_case["other_user_agent"]
                .as_str()
                .expect("other agent"),
        );
        assert!(!primary.matches(&other_agent, true));
        assert!(primary.matches(&other_agent, false));
        let timeout = SessionTimeout {
            idle_timeout_ms: timeout_case["idle_timeout_ms"].as_u64().expect("idle"),
            absolute_timeout_ms: timeout_case["absolute_timeout_ms"]
                .as_u64()
                .expect("absolute"),
            extend_on_activity: true,
        };
        let created = timeout_case["created_at_ms"].as_u64().expect("created");
        let mut session = ManagedSession::create_at(
            "user-123",
            primary,
            timeout,
            Some("oidc".into()),
            BTreeSet::new(),
            BTreeSet::new(),
            created,
        )
        .expect("session");
        assert_eq!(session.expires_at_ms, timeout_case["first_expiry_ms"]);
        session
            .access_at(
                None,
                "accessed",
                timeout_case["accessed_at_ms"].as_u64().expect("accessed"),
            )
            .expect("access");
        assert_eq!(session.expires_at_ms, timeout_case["extended_expiry_ms"]);
        assert!(session.is_expired_at(timeout_case["expired_at_ms"].as_u64().expect("expired")));
    }

    #[test]
    fn role_permission_data_and_termination_behavior() {
        let fixture = fixture();
        let case = &fixture["session"];
        let mut session = ManagedSession::create_at(
            case["user_id"].as_str().expect("user"),
            context("192.0.2.10", "agent"),
            SessionTimeout::default(),
            case["auth_method"].as_str().map(str::to_owned),
            [case["role"].as_str().expect("role").to_owned()]
                .into_iter()
                .collect(),
            [case["permission"].as_str().expect("permission").to_owned()]
                .into_iter()
                .collect(),
            1_000,
        )
        .expect("session");
        assert!(session.has_role("issuer"));
        assert!(session.has_permission("credential:issue"));
        session.set_data("tenant", Value::String("example".into()), 2_000);
        assert_eq!(
            session.data.get("tenant"),
            Some(&Value::String("example".into()))
        );
        session.invalidate_at(case["invalidation_reason"].as_str().expect("reason"), 3_000);
        assert_eq!(session.state, SessionState::Invalidated);
        assert!(!session.is_active_at(3_000));
        assert!(generate_session_id(32).len() >= 43);
        assert!(generate_session_token(64).len() >= 86);
    }
}
