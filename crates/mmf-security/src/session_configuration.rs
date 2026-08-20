//! Complete identity-session configuration with fail-closed production factories.

use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::SecurityError;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SessionStorageType {
    InMemory,
    Redis,
    Database,
    Distributed,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SessionSecurityLevel {
    Strict,
    Standard,
    Lenient,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SessionCleanupStrategy {
    Immediate,
    Background,
    OnAccess,
    Scheduled,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SessionSerializationFormat {
    Json,
    MessagePack,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct SessionTimeoutPolicy {
    pub default_timeout_ms: u64,
    pub max_timeout_ms: u64,
    pub idle_timeout_ms: u64,
    pub absolute_timeout_ms: u64,
    pub extend_on_activity: bool,
    pub warn_before_expiry: bool,
    pub warning_threshold_ms: u64,
    pub extension_grace_period_ms: u64,
    pub max_extensions: usize,
}

impl Default for SessionTimeoutPolicy {
    fn default() -> Self {
        Self {
            default_timeout_ms: 1_800_000,
            max_timeout_ms: 28_800_000,
            idle_timeout_ms: 1_800_000,
            absolute_timeout_ms: 28_800_000,
            extend_on_activity: true,
            warn_before_expiry: true,
            warning_threshold_ms: 300_000,
            extension_grace_period_ms: 120_000,
            max_extensions: 5,
        }
    }
}

impl SessionTimeoutPolicy {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.default_timeout_ms == 0
            || self.max_timeout_ms == 0
            || self.default_timeout_ms > self.max_timeout_ms
        {
            return Err(SecurityError::InvalidConfiguration(
                "default session timeout must be positive and no greater than maximum timeout"
                    .into(),
            ));
        }
        if self.idle_timeout_ms == 0
            || self.absolute_timeout_ms == 0
            || self.idle_timeout_ms >= self.absolute_timeout_ms
        {
            return Err(SecurityError::InvalidConfiguration(
                "idle timeout must be less than absolute timeout".into(),
            ));
        }
        if self.warning_threshold_ms >= self.idle_timeout_ms {
            return Err(SecurityError::InvalidConfiguration(
                "session warning threshold must be less than idle timeout".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn warning_at(&self, expiry_ms: u64) -> Option<u64> {
        self.warn_before_expiry
            .then(|| expiry_ms.saturating_sub(self.warning_threshold_ms))
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct SessionProtectionPolicy {
    pub validate_ip_address: bool,
    pub allow_ip_changes: bool,
    pub ip_change_detection: bool,
    pub validate_user_agent: bool,
    pub allow_user_agent_changes: bool,
    pub user_agent_strict_match: bool,
    pub require_secure_connection: bool,
    pub session_fingerprinting: bool,
    pub detect_concurrent_sessions: bool,
    pub max_concurrent_sessions: usize,
    pub rotate_session_on_auth: bool,
    pub rotate_session_on_privilege_change: bool,
    pub rotation_interval_ms: Option<u64>,
    pub track_login_attempts: bool,
    pub max_failed_attempts: usize,
    pub lockout_duration_ms: u64,
    pub geo_restrictions_enabled: bool,
    #[serde(default)]
    pub allowed_countries: BTreeSet<String>,
    #[serde(default)]
    pub blocked_countries: BTreeSet<String>,
}

impl Default for SessionProtectionPolicy {
    fn default() -> Self {
        Self {
            validate_ip_address: true,
            allow_ip_changes: false,
            ip_change_detection: true,
            validate_user_agent: true,
            allow_user_agent_changes: true,
            user_agent_strict_match: false,
            require_secure_connection: true,
            session_fingerprinting: true,
            detect_concurrent_sessions: true,
            max_concurrent_sessions: 3,
            rotate_session_on_auth: true,
            rotate_session_on_privilege_change: true,
            rotation_interval_ms: None,
            track_login_attempts: true,
            max_failed_attempts: 5,
            lockout_duration_ms: 900_000,
            geo_restrictions_enabled: false,
            allowed_countries: BTreeSet::new(),
            blocked_countries: BTreeSet::new(),
        }
    }
}

impl SessionProtectionPolicy {
    #[must_use]
    pub fn for_level(level: SessionSecurityLevel) -> Self {
        match level {
            SessionSecurityLevel::Strict => Self {
                user_agent_strict_match: true,
                max_concurrent_sessions: 1,
                ..Self::default()
            },
            SessionSecurityLevel::Standard => Self::default(),
            SessionSecurityLevel::Lenient => Self {
                validate_ip_address: false,
                allow_ip_changes: true,
                validate_user_agent: false,
                require_secure_connection: false,
                session_fingerprinting: false,
                max_concurrent_sessions: 10,
                track_login_attempts: false,
                ..Self::default()
            },
        }
    }

    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.max_concurrent_sessions == 0 || self.max_failed_attempts == 0 {
            return Err(SecurityError::InvalidConfiguration(
                "session security limits must be positive".into(),
            ));
        }
        if self.rotation_interval_ms == Some(0) {
            return Err(SecurityError::InvalidConfiguration(
                "session rotation interval must be positive".into(),
            ));
        }
        if !self.allowed_countries.is_disjoint(&self.blocked_countries) {
            return Err(SecurityError::InvalidConfiguration(
                "a country cannot be both allowed and blocked".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct SessionStorageConfiguration {
    pub storage_type: SessionStorageType,
    #[serde(skip_serializing)]
    pub connection_string: Option<String>,
    pub key_prefix: String,
    pub serialization_format: SessionSerializationFormat,
    pub compression_enabled: bool,
    pub connection_pool_size: usize,
    pub connection_timeout_ms: u64,
    pub operation_timeout_ms: u64,
    pub persistence_enabled: bool,
    pub backup_enabled: bool,
    pub backup_interval_ms: u64,
}

impl Default for SessionStorageConfiguration {
    fn default() -> Self {
        Self {
            storage_type: SessionStorageType::InMemory,
            connection_string: None,
            key_prefix: "session:".into(),
            serialization_format: SessionSerializationFormat::Json,
            compression_enabled: false,
            connection_pool_size: 10,
            connection_timeout_ms: 5_000,
            operation_timeout_ms: 30_000,
            persistence_enabled: true,
            backup_enabled: false,
            backup_interval_ms: 3_600_000,
        }
    }
}

impl SessionStorageConfiguration {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if matches!(
            self.storage_type,
            SessionStorageType::Redis
                | SessionStorageType::Database
                | SessionStorageType::Distributed
        ) && self
            .connection_string
            .as_deref()
            .is_none_or(|value| value.trim().is_empty())
        {
            return Err(SecurityError::InvalidConfiguration(
                "external session storage requires a connection string".into(),
            ));
        }
        if self.key_prefix.is_empty()
            || self.connection_pool_size == 0
            || self.connection_timeout_ms == 0
            || self.operation_timeout_ms == 0
            || self.backup_interval_ms == 0
        {
            return Err(SecurityError::InvalidConfiguration(
                "session storage limits and key prefix must be positive".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct SessionCleanupConfiguration {
    pub strategy: SessionCleanupStrategy,
    pub cleanup_interval_ms: u64,
    pub batch_size: usize,
    pub max_cleanup_duration_ms: u64,
    pub keep_expired_sessions_ms: u64,
    pub keep_invalidated_sessions_ms: u64,
    pub archive_old_sessions: bool,
    pub cleanup_during_peak_hours: bool,
    pub peak_hours_start: u8,
    pub peak_hours_end: u8,
}

impl Default for SessionCleanupConfiguration {
    fn default() -> Self {
        Self {
            strategy: SessionCleanupStrategy::Background,
            cleanup_interval_ms: 900_000,
            batch_size: 100,
            max_cleanup_duration_ms: 300_000,
            keep_expired_sessions_ms: 604_800_000,
            keep_invalidated_sessions_ms: 2_592_000_000,
            archive_old_sessions: false,
            cleanup_during_peak_hours: false,
            peak_hours_start: 9,
            peak_hours_end: 17,
        }
    }
}

impl SessionCleanupConfiguration {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.cleanup_interval_ms < 60_000
            || self.batch_size == 0
            || self.max_cleanup_duration_ms == 0
            || self.peak_hours_start > 23
            || self.peak_hours_end > 23
        {
            return Err(SecurityError::InvalidConfiguration(
                "invalid session cleanup limits or peak hours".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn should_run_at_hour(&self, hour: u8) -> bool {
        self.cleanup_during_peak_hours || hour < self.peak_hours_start || hour > self.peak_hours_end
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct SessionConfiguration {
    pub timeout_policy: SessionTimeoutPolicy,
    pub protection_policy: SessionProtectionPolicy,
    pub storage: SessionStorageConfiguration,
    pub cleanup: SessionCleanupConfiguration,
    pub enable_session_management: bool,
    pub enable_session_analytics: bool,
    pub enable_session_debugging: bool,
    pub integrate_with_authentication: bool,
    pub sync_with_user_roles: bool,
    pub propagate_session_events: bool,
    pub enable_session_monitoring: bool,
    pub alert_on_suspicious_activity: bool,
    pub session_metrics_enabled: bool,
    pub development_mode: bool,
    pub allow_insecure_cookies: bool,
    pub disable_csrf_protection: bool,
    #[serde(default)]
    pub custom_session_attributes: BTreeMap<String, Value>,
    #[serde(default)]
    pub extensions: BTreeMap<String, Value>,
}

impl Default for SessionConfiguration {
    fn default() -> Self {
        Self {
            timeout_policy: SessionTimeoutPolicy::default(),
            protection_policy: SessionProtectionPolicy::default(),
            storage: SessionStorageConfiguration::default(),
            cleanup: SessionCleanupConfiguration::default(),
            enable_session_management: true,
            enable_session_analytics: false,
            enable_session_debugging: false,
            integrate_with_authentication: true,
            sync_with_user_roles: true,
            propagate_session_events: false,
            enable_session_monitoring: true,
            alert_on_suspicious_activity: true,
            session_metrics_enabled: true,
            development_mode: false,
            allow_insecure_cookies: false,
            disable_csrf_protection: false,
            custom_session_attributes: BTreeMap::new(),
            extensions: BTreeMap::new(),
        }
    }
}

impl SessionConfiguration {
    pub fn validate(&self) -> Result<(), SecurityError> {
        self.timeout_policy.validate()?;
        self.protection_policy.validate()?;
        self.storage.validate()?;
        self.cleanup.validate()?;
        if !self.development_mode && (self.allow_insecure_cookies || self.disable_csrf_protection) {
            return Err(SecurityError::InvalidConfiguration(
                "insecure session settings are development-only".into(),
            ));
        }
        if !self.enable_session_management
            && (self.enable_session_analytics || self.enable_session_monitoring)
        {
            return Err(SecurityError::InvalidConfiguration(
                "session analytics and monitoring require session management".into(),
            ));
        }
        Ok(())
    }

    pub fn development() -> Result<Self, SecurityError> {
        let configuration = Self {
            timeout_policy: SessionTimeoutPolicy {
                idle_timeout_ms: 28_800_000,
                absolute_timeout_ms: 86_400_000,
                warn_before_expiry: false,
                ..SessionTimeoutPolicy::default()
            },
            protection_policy: SessionProtectionPolicy::for_level(SessionSecurityLevel::Lenient),
            storage: SessionStorageConfiguration::default(),
            cleanup: SessionCleanupConfiguration {
                cleanup_interval_ms: 3_600_000,
                keep_expired_sessions_ms: 3_600_000,
                ..SessionCleanupConfiguration::default()
            },
            enable_session_management: true,
            enable_session_analytics: false,
            enable_session_debugging: true,
            integrate_with_authentication: true,
            sync_with_user_roles: true,
            propagate_session_events: true,
            enable_session_monitoring: true,
            alert_on_suspicious_activity: true,
            session_metrics_enabled: true,
            development_mode: true,
            allow_insecure_cookies: true,
            disable_csrf_protection: false,
            custom_session_attributes: BTreeMap::new(),
            extensions: BTreeMap::new(),
        };
        configuration.validate()?;
        Ok(configuration)
    }

    pub fn production(redis_url: impl Into<String>) -> Result<Self, SecurityError> {
        let configuration = Self {
            timeout_policy: SessionTimeoutPolicy::default(),
            protection_policy: SessionProtectionPolicy::default(),
            storage: SessionStorageConfiguration {
                storage_type: SessionStorageType::Redis,
                connection_string: Some(redis_url.into()),
                backup_enabled: true,
                ..SessionStorageConfiguration::default()
            },
            cleanup: SessionCleanupConfiguration {
                archive_old_sessions: true,
                ..SessionCleanupConfiguration::default()
            },
            enable_session_management: true,
            enable_session_analytics: false,
            enable_session_debugging: false,
            integrate_with_authentication: true,
            sync_with_user_roles: true,
            propagate_session_events: true,
            enable_session_monitoring: true,
            alert_on_suspicious_activity: true,
            session_metrics_enabled: true,
            development_mode: false,
            allow_insecure_cookies: false,
            disable_csrf_protection: false,
            custom_session_attributes: BTreeMap::new(),
            extensions: BTreeMap::new(),
        };
        configuration.validate()?;
        Ok(configuration)
    }

    pub fn high_security(database_url: impl Into<String>) -> Result<Self, SecurityError> {
        let mut configuration = Self::production("unused-for-database")?;
        configuration.timeout_policy = SessionTimeoutPolicy {
            idle_timeout_ms: 900_000,
            absolute_timeout_ms: 14_400_000,
            warning_threshold_ms: 120_000,
            max_extensions: 3,
            ..SessionTimeoutPolicy::default()
        };
        configuration.protection_policy = SessionProtectionPolicy {
            user_agent_strict_match: true,
            max_concurrent_sessions: 1,
            rotation_interval_ms: Some(3_600_000),
            max_failed_attempts: 3,
            lockout_duration_ms: 3_600_000,
            ..SessionProtectionPolicy::default()
        };
        configuration.storage = SessionStorageConfiguration {
            storage_type: SessionStorageType::Database,
            connection_string: Some(database_url.into()),
            compression_enabled: true,
            backup_enabled: true,
            ..SessionStorageConfiguration::default()
        };
        configuration.cleanup = SessionCleanupConfiguration {
            strategy: SessionCleanupStrategy::Immediate,
            keep_expired_sessions_ms: 86_400_000,
            keep_invalidated_sessions_ms: 604_800_000,
            archive_old_sessions: true,
            ..SessionCleanupConfiguration::default()
        };
        configuration.validate()?;
        Ok(configuration)
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
    fn language_neutral_configuration_factories_and_levels() {
        let fixture = fixture();
        let case = &fixture["configuration"];
        let development = SessionConfiguration::development().expect("development");
        assert_eq!(
            development.timeout_policy.idle_timeout_ms,
            case["development_idle_timeout_ms"]
        );
        let production =
            SessionConfiguration::production(case["redis_url"].as_str().expect("Redis URL"))
                .expect("production");
        assert_eq!(
            production.timeout_policy.idle_timeout_ms,
            case["production_idle_timeout_ms"]
        );
        let high = SessionConfiguration::high_security(
            case["database_url"].as_str().expect("database URL"),
        )
        .expect("high security");
        assert_eq!(
            high.timeout_policy.idle_timeout_ms,
            case["high_security_idle_timeout_ms"]
        );
        assert_eq!(
            SessionProtectionPolicy::for_level(SessionSecurityLevel::Strict)
                .max_concurrent_sessions,
            1
        );
        assert_eq!(
            SessionProtectionPolicy::for_level(SessionSecurityLevel::Standard)
                .max_concurrent_sessions,
            3
        );
        assert_eq!(
            SessionProtectionPolicy::for_level(SessionSecurityLevel::Lenient)
                .max_concurrent_sessions,
            10
        );
        assert!(
            !serde_json::to_string(&production)
                .expect("serialize")
                .contains("redis://")
        );
    }

    #[test]
    fn invalid_configuration_fails_closed() {
        let mut timeout = SessionTimeoutPolicy::default();
        timeout.idle_timeout_ms = timeout.absolute_timeout_ms;
        assert!(timeout.validate().is_err());
        let storage = SessionStorageConfiguration {
            storage_type: SessionStorageType::Redis,
            ..SessionStorageConfiguration::default()
        };
        assert!(storage.validate().is_err());
        let mut production =
            SessionConfiguration::production("redis://example").expect("production");
        production.allow_insecure_cookies = true;
        assert!(production.validate().is_err());
    }
}
