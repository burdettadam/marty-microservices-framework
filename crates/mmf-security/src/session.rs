use std::collections::BTreeMap;
use std::sync::{Arc, Mutex};

use serde::{Deserialize, Serialize};
use serde_json::Value;
use uuid::Uuid;

use crate::SecurityError;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SessionState {
    Active,
    Expired,
    Terminated,
    Invalid,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SessionEventType {
    Logout,
    Timeout,
    SecurityViolation,
    AdminTermination,
    PasswordChange,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SessionData {
    pub session_id: String,
    pub user_id: String,
    pub created_at_ms: u64,
    pub last_accessed_ms: u64,
    pub expires_at_ms: u64,
    pub state: SessionState,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ip_address: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub user_agent: Option<String>,
    #[serde(default)]
    pub attributes: BTreeMap<String, Value>,
    #[serde(default)]
    pub security_context: BTreeMap<String, Value>,
}

impl SessionData {
    #[must_use]
    pub fn create_at(user_id: impl Into<String>, now_ms: u64, timeout_ms: u64) -> Self {
        Self {
            session_id: Uuid::new_v4().to_string(),
            user_id: user_id.into(),
            created_at_ms: now_ms,
            last_accessed_ms: now_ms,
            expires_at_ms: now_ms.saturating_add(timeout_ms),
            state: SessionState::Active,
            ip_address: None,
            user_agent: None,
            attributes: BTreeMap::new(),
            security_context: BTreeMap::new(),
        }
    }

    #[must_use]
    pub fn is_expired_at(&self, now_ms: u64) -> bool {
        now_ms >= self.expires_at_ms || self.state != SessionState::Active
    }

    #[must_use]
    pub fn time_remaining_at(&self, now_ms: u64) -> u64 {
        if self.is_expired_at(now_ms) {
            0
        } else {
            self.expires_at_ms.saturating_sub(now_ms)
        }
    }

    pub fn extend_at(&mut self, now_ms: u64, duration_ms: u64) -> Result<(), SecurityError> {
        if self.state != SessionState::Active {
            return Err(SecurityError::InvalidSessionState);
        }
        self.last_accessed_ms = now_ms;
        self.expires_at_ms = now_ms.saturating_add(duration_ms);
        Ok(())
    }

    pub fn touch_at(&mut self, now_ms: u64) -> Result<(), SecurityError> {
        if self.state != SessionState::Active || now_ms >= self.expires_at_ms {
            return Err(SecurityError::InvalidSessionState);
        }
        self.last_accessed_ms = now_ms;
        Ok(())
    }

    pub fn terminate_at(&mut self, now_ms: u64, reason: SessionEventType) {
        self.state = SessionState::Terminated;
        self.attributes.insert(
            "termination_reason".to_owned(),
            Value::String(reason_name(reason).to_owned()),
        );
        self.attributes
            .insert("terminated_at_ms".to_owned(), Value::from(now_ms));
    }

    pub fn invalidate(&mut self) {
        self.state = SessionState::Invalid;
    }

    #[must_use]
    pub fn cache_key(&self, prefix: &str) -> String {
        format!("{prefix}:{}", self.session_id)
    }
}

fn reason_name(reason: SessionEventType) -> &'static str {
    match reason {
        SessionEventType::Logout => "logout",
        SessionEventType::Timeout => "timeout",
        SessionEventType::SecurityViolation => "security_violation",
        SessionEventType::AdminTermination => "admin_termination",
        SessionEventType::PasswordChange => "password_change",
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct SessionLifecycle {
    pub default_timeout_ms: u64,
    pub max_timeout_ms: u64,
    pub idle_timeout_ms: u64,
    pub absolute_timeout_ms: u64,
    pub extend_on_activity: bool,
    pub require_ip_consistency: bool,
    pub require_user_agent_consistency: bool,
}

impl SessionLifecycle {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.default_timeout_ms == 0
            || self.max_timeout_ms == 0
            || self.idle_timeout_ms == 0
            || self.absolute_timeout_ms == 0
            || self.default_timeout_ms > self.max_timeout_ms
        {
            return Err(SecurityError::InvalidSessionConfiguration);
        }
        Ok(())
    }

    pub fn expiration_at(
        &self,
        created_at_ms: u64,
        last_accessed_ms: u64,
        now_ms: u64,
        requested_timeout_ms: Option<u64>,
    ) -> Result<u64, SecurityError> {
        self.validate()?;
        let timeout = requested_timeout_ms
            .unwrap_or(self.default_timeout_ms)
            .min(self.max_timeout_ms);
        Ok(last_accessed_ms
            .saturating_add(self.idle_timeout_ms)
            .min(created_at_ms.saturating_add(self.absolute_timeout_ms))
            .min(now_ms.saturating_add(timeout)))
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct SessionSecurityPolicy {
    pub require_secure_transport: bool,
    pub enforce_same_origin: bool,
    pub detect_session_hijacking: bool,
    pub max_sessions_per_user: usize,
    pub lock_on_security_violation: bool,
    pub notification_on_new_session: bool,
    pub log_all_session_events: bool,
}

impl SessionSecurityPolicy {
    #[must_use]
    pub fn violations(
        &self,
        session: &SessionData,
        current_ip: Option<&str>,
        current_user_agent: Option<&str>,
    ) -> Vec<String> {
        if !self.detect_session_hijacking {
            return Vec::new();
        }
        let mut violations = Vec::new();
        if session.ip_address.as_deref().is_some()
            && current_ip.is_some()
            && session.ip_address.as_deref() != current_ip
        {
            violations.push("IP address mismatch detected".to_owned());
        }
        if session.user_agent.as_deref().is_some()
            && current_user_agent.is_some()
            && session.user_agent.as_deref() != current_user_agent
        {
            violations.push("User agent mismatch detected".to_owned());
        }
        violations
    }
}

#[derive(Clone, Debug, Default)]
pub struct InMemorySessionStore {
    sessions: Arc<Mutex<BTreeMap<String, SessionData>>>,
}

impl InMemorySessionStore {
    pub fn create(
        &self,
        session: SessionData,
        max_sessions_per_user: usize,
    ) -> Result<(), SecurityError> {
        let mut sessions = self
            .sessions
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        let active = sessions
            .values()
            .filter(|stored| {
                stored.user_id == session.user_id && stored.state == SessionState::Active
            })
            .count();
        if active >= max_sessions_per_user {
            return Err(SecurityError::SessionLimitExceeded);
        }
        if sessions.contains_key(&session.session_id) {
            return Err(SecurityError::SessionAlreadyExists);
        }
        sessions.insert(session.session_id.clone(), session);
        Ok(())
    }

    #[must_use]
    pub fn get(&self, session_id: &str) -> Option<SessionData> {
        self.sessions
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .get(session_id)
            .cloned()
    }

    pub fn replace(&self, session: SessionData) -> Result<(), SecurityError> {
        let mut sessions = self
            .sessions
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        if !sessions.contains_key(&session.session_id) {
            return Err(SecurityError::SessionNotFound);
        }
        sessions.insert(session.session_id.clone(), session);
        Ok(())
    }

    pub fn remove(&self, session_id: &str) -> Option<SessionData> {
        self.sessions
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .remove(session_id)
    }
}
