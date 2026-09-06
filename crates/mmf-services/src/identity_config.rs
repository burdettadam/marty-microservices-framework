//! Complete built-in identity-service configuration.
//!
//! Reusable MFA and session behavior is reused from `mmf-security`; this module only owns
//! service/provider wiring. Secrets are accepted as provider input and never serialized.

use std::collections::{BTreeMap, BTreeSet};

use mmf_config::{ConfigSnapshot, SecretRegistry};
use mmf_security::{MfaConfig, MtlsConfiguration, SessionConfiguration};
use serde::{Deserialize, Serialize};

use crate::ServiceError;

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum IdentityEnvironment {
    Development,
    Testing,
    Staging,
    Production,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AuthenticationProviderType {
    Basic,
    ApiKey,
    Jwt,
    #[serde(rename = "oauth2")]
    OAuth2,
    Oidc,
    Saml,
    #[serde(rename = "mtls")]
    MutualTls,
    Mfa,
    Session,
    Environment,
    Ldap,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PasswordHashAlgorithm {
    Bcrypt,
    Scrypt,
    Argon2id,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct PasswordAuthenticationConfig {
    pub hash_algorithm: PasswordHashAlgorithm,
    pub hash_cost: u32,
    pub min_length: usize,
    pub max_length: usize,
    pub require_uppercase: bool,
    pub require_lowercase: bool,
    pub require_numbers: bool,
    pub require_special_characters: bool,
    pub special_characters: String,
    pub max_login_attempts: usize,
    pub lockout_duration_ms: u64,
    pub password_expiry_ms: u64,
    pub create_default_users: bool,
    pub default_admin_username: String,
    #[serde(skip_serializing)]
    pub default_admin_password: Option<String>,
}

impl Default for PasswordAuthenticationConfig {
    fn default() -> Self {
        let policy = crate::native_identity::NativePasswordPolicy::configured();
        Self {
            hash_algorithm: PasswordHashAlgorithm::Bcrypt,
            hash_cost: 12,
            min_length: policy.min_length,
            max_length: policy.max_length,
            require_uppercase: policy.require_uppercase,
            require_lowercase: policy.require_lowercase,
            require_numbers: policy.require_numbers,
            require_special_characters: policy.require_special_characters,
            special_characters: policy.special_characters,
            max_login_attempts: policy.max_login_attempts,
            lockout_duration_ms: policy.lockout_duration_ms,
            password_expiry_ms: policy.password_expiry_ms,
            create_default_users: true,
            default_admin_username: "admin".into(),
            default_admin_password: None,
        }
    }
}

impl PasswordAuthenticationConfig {
    pub fn validate(&self) -> Result<(), ServiceError> {
        let valid_cost = match self.hash_algorithm {
            PasswordHashAlgorithm::Bcrypt => (4..=31).contains(&self.hash_cost),
            PasswordHashAlgorithm::Scrypt | PasswordHashAlgorithm::Argon2id => self.hash_cost > 0,
        };
        if !valid_cost
            || self.min_length < 8
            || self.min_length > self.max_length
            || self.max_login_attempts == 0
            || self.lockout_duration_ms == 0
            || self.password_expiry_ms == 0
            || self.default_admin_username.trim().is_empty()
            || (self.require_special_characters && self.special_characters.is_empty())
        {
            return Err(ServiceError::InvalidConfiguration(
                "invalid password policy".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ApiKeyConfiguration {
    pub entropy_bytes: usize,
    pub prefix: String,
    pub default_expiry_ms: u64,
    pub max_keys_per_user: usize,
    pub enable_rotation: bool,
    pub rotation_warning_ms: u64,
    pub requests_per_minute: u64,
    pub enable_usage_tracking: bool,
    pub create_demo_keys: bool,
}

impl Default for ApiKeyConfiguration {
    fn default() -> Self {
        Self {
            entropy_bytes: 32,
            prefix: "mmf_".into(),
            default_expiry_ms: 31_536_000_000,
            max_keys_per_user: 10,
            enable_rotation: true,
            rotation_warning_ms: 2_592_000_000,
            requests_per_minute: 1_000,
            enable_usage_tracking: true,
            create_demo_keys: true,
        }
    }
}

impl ApiKeyConfiguration {
    pub fn validate(&self) -> Result<(), ServiceError> {
        if self.entropy_bytes < 32
            || self.prefix.is_empty()
            || self.default_expiry_ms == 0
            || self.max_keys_per_user == 0
            || self.rotation_warning_ms >= self.default_expiry_ms
            || self.requests_per_minute == 0
        {
            return Err(ServiceError::InvalidConfiguration(
                "invalid API-key configuration".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct JwtAuthenticationConfig {
    #[serde(skip_serializing)]
    pub key_material: Option<String>,
    pub algorithm: String,
    pub access_token_lifetime_ms: u64,
    pub refresh_token_lifetime_ms: u64,
    pub verify_signature: bool,
    pub verify_expiration: bool,
    pub verify_issued_at: bool,
    pub verify_not_before: bool,
    pub verify_issuer: bool,
    pub verify_audience: bool,
    pub issuer: String,
    pub audience: BTreeSet<String>,
    pub allow_refresh: bool,
    pub max_refresh_count: usize,
    #[serde(default)]
    pub excluded_paths: BTreeSet<String>,
    #[serde(default)]
    pub optional_paths: BTreeSet<String>,
}

impl JwtAuthenticationConfig {
    pub fn development(key_material: Option<String>) -> Self {
        Self {
            key_material,
            algorithm: "HS256".into(),
            access_token_lifetime_ms: 3_600_000,
            refresh_token_lifetime_ms: 604_800_000,
            verify_signature: true,
            verify_expiration: true,
            verify_issued_at: true,
            verify_not_before: true,
            verify_issuer: false,
            verify_audience: false,
            issuer: "marty-dev".into(),
            audience: ["marty-dev-services".into()].into_iter().collect(),
            allow_refresh: true,
            max_refresh_count: 3,
            excluded_paths: [
                "/health",
                "/docs",
                "/openapi.json",
                "/redoc",
                "/auth/jwt/health",
                "/dev/*",
            ]
            .into_iter()
            .map(str::to_owned)
            .collect(),
            optional_paths: ["/admin/debug", "/metrics"]
                .into_iter()
                .map(str::to_owned)
                .collect(),
        }
    }

    pub fn production(key_material: impl Into<String>) -> Result<Self, ServiceError> {
        let key_material = key_material.into();
        if key_material.trim().is_empty() {
            return Err(ServiceError::InvalidConfiguration(
                "production JWT key material is required".into(),
            ));
        }
        let configuration = Self {
            key_material: Some(key_material),
            algorithm: "HS256".into(),
            access_token_lifetime_ms: 1_800_000,
            refresh_token_lifetime_ms: 604_800_000,
            verify_signature: true,
            verify_expiration: true,
            verify_issued_at: true,
            verify_not_before: true,
            verify_issuer: true,
            verify_audience: true,
            issuer: "marty-microservices".into(),
            audience: ["marty-services".into()].into_iter().collect(),
            allow_refresh: true,
            max_refresh_count: 3,
            excluded_paths: ["/health", "/docs", "/openapi.json", "/auth/jwt/health"]
                .into_iter()
                .map(str::to_owned)
                .collect(),
            optional_paths: BTreeSet::new(),
        };
        configuration.validate(true)?;
        Ok(configuration)
    }

    pub fn validate(&self, production: bool) -> Result<(), ServiceError> {
        if !matches!(
            self.algorithm.as_str(),
            "HS256" | "HS384" | "HS512" | "RS256" | "RS384" | "RS512" | "ES256" | "ES384" | "EdDSA"
        ) {
            return Err(ServiceError::InvalidConfiguration(
                "unsupported JWT algorithm".into(),
            ));
        }
        if self.access_token_lifetime_ms == 0
            || self.refresh_token_lifetime_ms == 0
            || self.max_refresh_count == 0
            || self.issuer.trim().is_empty()
            || self.audience.is_empty()
        {
            return Err(ServiceError::InvalidConfiguration(
                "invalid JWT lifetime or claims configuration".into(),
            ));
        }
        if production
            && (!self.verify_signature
                || !self.verify_expiration
                || !self.verify_issuer
                || !self.verify_audience
                || self
                    .key_material
                    .as_deref()
                    .is_none_or(|material| material.trim().is_empty()))
        {
            return Err(ServiceError::InvalidConfiguration(
                "production JWT validation must be fully enabled with key material".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct FederatedOAuthConfiguration {
    pub provider_name: String,
    pub client_id: String,
    #[serde(skip_serializing)]
    pub client_secret: Option<String>,
    pub authorization_url: String,
    pub token_url: String,
    pub userinfo_url: Option<String>,
    pub jwks_url: Option<String>,
    pub scopes: BTreeSet<String>,
    pub user_id_claim: String,
    pub username_claim: String,
    pub email_claim: String,
    pub pkce_enabled: bool,
    pub state_validation: bool,
    pub nonce_validation: bool,
}

impl Default for FederatedOAuthConfiguration {
    fn default() -> Self {
        Self {
            provider_name: "oauth2".into(),
            client_id: String::new(),
            client_secret: None,
            authorization_url: String::new(),
            token_url: String::new(),
            userinfo_url: None,
            jwks_url: None,
            scopes: ["openid", "profile", "email"]
                .into_iter()
                .map(str::to_owned)
                .collect(),
            user_id_claim: "sub".into(),
            username_claim: "preferred_username".into(),
            email_claim: "email".into(),
            pkce_enabled: true,
            state_validation: true,
            nonce_validation: true,
        }
    }
}

impl FederatedOAuthConfiguration {
    pub fn validate(&self) -> Result<(), ServiceError> {
        if self.provider_name.trim().is_empty()
            || self.client_id.trim().is_empty()
            || self.authorization_url.trim().is_empty()
            || self.token_url.trim().is_empty()
            || self.scopes.is_empty()
            || !self.pkce_enabled
            || !self.state_validation
        {
            return Err(ServiceError::InvalidConfiguration(
                "enabled OAuth2/OIDC requires complete fail-closed provider configuration".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct SamlConfiguration {
    pub idp_entity_id: String,
    pub idp_sso_url: String,
    #[serde(skip_serializing)]
    pub idp_x509_certificate: String,
    pub sp_entity_id: String,
    pub sp_acs_url: String,
    pub sp_sls_url: Option<String>,
    pub name_id_format: String,
    pub attribute_mapping: BTreeMap<String, String>,
    pub require_assertion_signature: bool,
    pub require_response_signature: bool,
}

impl Default for SamlConfiguration {
    fn default() -> Self {
        Self {
            idp_entity_id: String::new(),
            idp_sso_url: String::new(),
            idp_x509_certificate: String::new(),
            sp_entity_id: "mmf-identity-service".into(),
            sp_acs_url: String::new(),
            sp_sls_url: None,
            name_id_format: "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent".into(),
            attribute_mapping: BTreeMap::from([
                ("user_id".into(), "uid".into()),
                ("username".into(), "username".into()),
                ("email".into(), "email".into()),
                ("first_name".into(), "givenName".into()),
                ("last_name".into(), "sn".into()),
            ]),
            require_assertion_signature: true,
            require_response_signature: true,
        }
    }
}

impl SamlConfiguration {
    pub fn validate(&self) -> Result<(), ServiceError> {
        if [
            &self.idp_entity_id,
            &self.idp_sso_url,
            &self.idp_x509_certificate,
            &self.sp_entity_id,
            &self.sp_acs_url,
            &self.name_id_format,
        ]
        .into_iter()
        .any(|value| value.trim().is_empty())
            || !self.require_assertion_signature
            || !self.require_response_signature
        {
            return Err(ServiceError::InvalidConfiguration(
                "enabled SAML requires complete IdP and SP configuration".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct LdapConfiguration {
    pub server_url: String,
    pub base_dn: String,
    pub bind_dn: Option<String>,
    #[serde(skip_serializing)]
    pub bind_password: Option<String>,
    pub user_filter: String,
    pub group_filter: Option<String>,
    pub use_start_tls: bool,
}

impl LdapConfiguration {
    pub fn validate(&self) -> Result<(), ServiceError> {
        if self.server_url.trim().is_empty()
            || self.base_dn.trim().is_empty()
            || self.user_filter.trim().is_empty()
        {
            return Err(ServiceError::InvalidConfiguration(
                "enabled LDAP requires server, base DN, and user filter".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct IdentitySecurityConfiguration {
    pub enable_rate_limiting: bool,
    pub login_requests_per_minute: u64,
    pub api_requests_per_minute: u64,
    pub allowed_ips: BTreeSet<String>,
    pub blocked_ips: BTreeSet<String>,
    pub enable_audit_logging: bool,
    pub log_successful_logins: bool,
    pub log_failed_logins: bool,
    pub log_logout_events: bool,
    pub enable_security_headers: bool,
    pub csrf_protection: bool,
    pub enable_at_rest_encryption: bool,
    #[serde(skip_serializing)]
    pub encryption_key: Option<String>,
}

impl Default for IdentitySecurityConfiguration {
    fn default() -> Self {
        Self {
            enable_rate_limiting: true,
            login_requests_per_minute: 5,
            api_requests_per_minute: 100,
            allowed_ips: BTreeSet::new(),
            blocked_ips: BTreeSet::new(),
            enable_audit_logging: true,
            log_successful_logins: true,
            log_failed_logins: true,
            log_logout_events: true,
            enable_security_headers: true,
            csrf_protection: true,
            enable_at_rest_encryption: false,
            encryption_key: None,
        }
    }
}

impl IdentitySecurityConfiguration {
    pub fn validate(&self) -> Result<(), ServiceError> {
        if self.login_requests_per_minute == 0
            || self.api_requests_per_minute == 0
            || !self.allowed_ips.is_disjoint(&self.blocked_ips)
            || (self.enable_at_rest_encryption
                && self
                    .encryption_key
                    .as_deref()
                    .is_none_or(|key| key.trim().is_empty()))
        {
            return Err(ServiceError::InvalidConfiguration(
                "invalid identity security configuration".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct IdentityServiceConfiguration {
    pub service_name: String,
    pub service_version: String,
    pub environment: IdentityEnvironment,
    pub debug: bool,
    pub enabled_providers: BTreeSet<AuthenticationProviderType>,
    pub default_provider: AuthenticationProviderType,
    pub password: PasswordAuthenticationConfig,
    pub api_key: ApiKeyConfiguration,
    pub jwt: JwtAuthenticationConfig,
    pub federated_oauth: Option<FederatedOAuthConfiguration>,
    pub saml: Option<SamlConfiguration>,
    pub ldap: Option<LdapConfiguration>,
    pub mfa: MfaConfig,
    pub mutual_tls: Option<MtlsConfiguration>,
    pub session: SessionConfiguration,
    pub security: IdentitySecurityConfiguration,
    pub enable_user_registration: bool,
    pub enable_password_reset: bool,
    pub enable_account_lockout: bool,
    pub user_table_name: String,
    pub session_table_name: String,
    pub api_key_table_name: String,
    pub audit_table_name: String,
}

impl IdentityServiceConfiguration {
    /// Decode the identity section from an already-layered MMF snapshot.
    pub fn from_snapshot(snapshot: &ConfigSnapshot) -> Result<Self, ServiceError> {
        Self::decode_snapshot_value(&snapshot.value)
    }

    /// Resolve secret references through canonical `mmf-config` providers before decoding.
    pub fn from_snapshot_with_secrets(
        snapshot: &ConfigSnapshot,
        secrets: &SecretRegistry,
    ) -> Result<Self, ServiceError> {
        let resolved = secrets
            .resolve_value(&snapshot.value)
            .map_err(|error| ServiceError::ProviderUnavailable(error.to_string()))?;
        Self::decode_snapshot_value(&resolved)
    }

    fn decode_snapshot_value(value: &serde_json::Value) -> Result<Self, ServiceError> {
        let identity = value
            .pointer("/services/identity")
            .or_else(|| value.get("identity"))
            .ok_or_else(|| {
                ServiceError::InvalidConfiguration(
                    "identity configuration section is missing".into(),
                )
            })?;
        let configuration: Self = serde_json::from_value(identity.clone()).map_err(|error| {
            ServiceError::InvalidConfiguration(format!(
                "identity configuration could not be decoded: {error}"
            ))
        })?;
        configuration.validate()?;
        Ok(configuration)
    }

    #[allow(clippy::too_many_lines)]
    pub fn validate(&self) -> Result<(), ServiceError> {
        if self.service_name.trim().is_empty()
            || self.service_version.trim().is_empty()
            || !self.enabled_providers.contains(&self.default_provider)
        {
            return Err(ServiceError::InvalidConfiguration(
                "default authentication provider must be enabled".into(),
            ));
        }
        self.password.validate()?;
        self.api_key.validate()?;
        self.jwt
            .validate(self.environment == IdentityEnvironment::Production)?;
        self.security.validate()?;
        self.mfa
            .validate()
            .map_err(|error| ServiceError::InvalidConfiguration(error.to_string()))?;
        self.session
            .validate()
            .map_err(|error| ServiceError::InvalidConfiguration(error.to_string()))?;
        if self
            .enabled_providers
            .contains(&AuthenticationProviderType::OAuth2)
            || self
                .enabled_providers
                .contains(&AuthenticationProviderType::Oidc)
        {
            self.federated_oauth
                .as_ref()
                .ok_or_else(|| {
                    ServiceError::InvalidConfiguration(
                        "enabled OAuth2/OIDC requires provider configuration".into(),
                    )
                })?
                .validate()?;
        }
        if self
            .enabled_providers
            .contains(&AuthenticationProviderType::Saml)
        {
            self.saml
                .as_ref()
                .ok_or_else(|| {
                    ServiceError::InvalidConfiguration(
                        "enabled SAML requires complete IdP and SP configuration".into(),
                    )
                })?
                .validate()?;
        }
        if self
            .enabled_providers
            .contains(&AuthenticationProviderType::Ldap)
        {
            self.ldap
                .as_ref()
                .ok_or_else(|| {
                    ServiceError::InvalidConfiguration(
                        "enabled LDAP requires provider configuration".into(),
                    )
                })?
                .validate()?;
        }
        if self
            .enabled_providers
            .contains(&AuthenticationProviderType::MutualTls)
        {
            self.mutual_tls
                .as_ref()
                .ok_or_else(|| {
                    ServiceError::InvalidConfiguration(
                        "enabled mTLS requires trust configuration".into(),
                    )
                })?
                .validate()
                .map_err(|error| ServiceError::InvalidConfiguration(error.to_string()))?;
        }
        if self.environment == IdentityEnvironment::Production {
            if self.password.create_default_users
                || self.password.default_admin_password.as_deref() == Some("admin123")
            {
                return Err(ServiceError::InvalidConfiguration(
                    "production cannot use a default administrator password".into(),
                ));
            }
            if self.debug
                || !self.security.enable_audit_logging
                || !self.security.csrf_protection
                || !self.jwt.verify_signature
            {
                return Err(ServiceError::InvalidConfiguration(
                    "production identity security controls must remain enabled".into(),
                ));
            }
        }
        for table in [
            &self.user_table_name,
            &self.session_table_name,
            &self.api_key_table_name,
            &self.audit_table_name,
        ] {
            if !valid_identifier(table) {
                return Err(ServiceError::InvalidConfiguration(
                    "identity table names must be safe SQL identifiers".into(),
                ));
            }
        }
        Ok(())
    }

    pub fn development() -> Result<Self, ServiceError> {
        let password = PasswordAuthenticationConfig {
            default_admin_password: Some("admin123".into()),
            ..PasswordAuthenticationConfig::default()
        };
        let security = IdentitySecurityConfiguration {
            enable_rate_limiting: false,
            ..IdentitySecurityConfiguration::default()
        };
        let configuration = Self {
            service_name: "mmf-identity-service".into(),
            service_version: "1.0.0".into(),
            environment: IdentityEnvironment::Development,
            debug: true,
            enabled_providers: [
                AuthenticationProviderType::Basic,
                AuthenticationProviderType::ApiKey,
                AuthenticationProviderType::Jwt,
            ]
            .into_iter()
            .collect(),
            default_provider: AuthenticationProviderType::Jwt,
            password,
            api_key: ApiKeyConfiguration::default(),
            jwt: JwtAuthenticationConfig::development(Some(
                "dev-secret-key-change-in-production".into(),
            )),
            federated_oauth: None,
            saml: None,
            ldap: None,
            mfa: MfaConfig::default(),
            mutual_tls: None,
            session: SessionConfiguration::development()
                .map_err(|error| ServiceError::InvalidConfiguration(error.to_string()))?,
            security,
            enable_user_registration: true,
            enable_password_reset: true,
            enable_account_lockout: true,
            user_table_name: "users".into(),
            session_table_name: "user_sessions".into(),
            api_key_table_name: "api_keys".into(),
            audit_table_name: "audit_log".into(),
        };
        configuration.validate()?;
        Ok(configuration)
    }

    pub fn testing() -> Result<Self, ServiceError> {
        let mut configuration = Self::development()?;
        configuration.environment = IdentityEnvironment::Testing;
        configuration.password.create_default_users = false;
        configuration.password.default_admin_password = None;
        configuration.api_key.create_demo_keys = false;
        configuration.jwt.access_token_lifetime_ms = 300_000;
        configuration.jwt.key_material = Some("test-secret-key".into());
        configuration.session = SessionConfiguration::development()
            .map_err(|error| ServiceError::InvalidConfiguration(error.to_string()))?;
        configuration.validate()?;
        Ok(configuration)
    }

    pub fn staging(
        jwt_key_material: impl Into<String>,
        session_storage_url: impl Into<String>,
    ) -> Result<Self, ServiceError> {
        let mut configuration = Self::production(jwt_key_material, session_storage_url)?;
        configuration.environment = IdentityEnvironment::Staging;
        configuration.validate()?;
        Ok(configuration)
    }

    pub fn production(
        jwt_key_material: impl Into<String>,
        session_storage_url: impl Into<String>,
    ) -> Result<Self, ServiceError> {
        let password = PasswordAuthenticationConfig {
            create_default_users: false,
            default_admin_password: None,
            ..PasswordAuthenticationConfig::default()
        };
        let api_key = ApiKeyConfiguration {
            create_demo_keys: false,
            ..ApiKeyConfiguration::default()
        };
        let configuration = Self {
            service_name: "mmf-identity-service".into(),
            service_version: "1.0.0".into(),
            environment: IdentityEnvironment::Production,
            debug: false,
            enabled_providers: [
                AuthenticationProviderType::Basic,
                AuthenticationProviderType::ApiKey,
                AuthenticationProviderType::Jwt,
            ]
            .into_iter()
            .collect(),
            default_provider: AuthenticationProviderType::Jwt,
            password,
            api_key,
            jwt: JwtAuthenticationConfig::production(jwt_key_material)?,
            federated_oauth: None,
            saml: None,
            ldap: None,
            mfa: MfaConfig::default(),
            mutual_tls: None,
            session: SessionConfiguration::production(session_storage_url)
                .map_err(|error| ServiceError::InvalidConfiguration(error.to_string()))?,
            security: IdentitySecurityConfiguration::default(),
            enable_user_registration: true,
            enable_password_reset: true,
            enable_account_lockout: true,
            user_table_name: "users".into(),
            session_table_name: "user_sessions".into(),
            api_key_table_name: "api_keys".into(),
            audit_table_name: "audit_log".into(),
        };
        configuration.validate()?;
        Ok(configuration)
    }
}

fn valid_identifier(identifier: &str) -> bool {
    let mut characters = identifier.chars();
    characters
        .next()
        .is_some_and(|character| character == '_' || character.is_ascii_alphabetic())
        && characters.all(|character| character == '_' || character.is_ascii_alphanumeric())
}

#[cfg(test)]
mod tests {
    use super::*;
    use mmf_config::{ConfigSnapshot, SecretRegistry};
    use serde_json::Value;

    fn fixture() -> Value {
        serde_json::from_str(include_str!(
            "../../../contracts/identity-service-configuration-behavior.json"
        ))
        .expect("valid identity configuration fixture")
    }

    #[test]
    fn language_neutral_environment_factories() {
        let fixture = fixture();
        let development = IdentityServiceConfiguration::development().expect("development");
        assert_eq!(
            development.debug,
            fixture["environments"]["development"]["debug"]
        );
        assert_eq!(
            development.jwt.access_token_lifetime_ms,
            fixture["environments"]["development"]["access_token_expiry_ms"]
        );
        let testing = IdentityServiceConfiguration::testing().expect("testing");
        assert_eq!(
            testing.jwt.access_token_lifetime_ms,
            fixture["environments"]["testing"]["access_token_expiry_ms"]
        );
        let production = IdentityServiceConfiguration::production(
            "production-key-material",
            "redis://identity.example.test/0",
        )
        .expect("production");
        assert_eq!(
            production.debug,
            fixture["environments"]["production"]["debug"]
        );
        assert!(production.security.enable_audit_logging);
        let serialized = serde_json::to_string(&production).expect("serialize");
        assert!(!serialized.contains("production-key-material"));
        assert!(!serialized.contains("redis://"));
    }

    #[test]
    fn every_intended_provider_is_represented() {
        let fixture = fixture();
        let providers: BTreeSet<AuthenticationProviderType> = fixture["providers"]
            .as_array()
            .expect("providers")
            .iter()
            .map(|provider| serde_json::from_value(provider.clone()).expect("provider enum"))
            .collect();
        assert_eq!(providers.len(), 11);
        assert!(providers.contains(&AuthenticationProviderType::Ldap));
        assert!(providers.contains(&AuthenticationProviderType::MutualTls));
        assert!(providers.contains(&AuthenticationProviderType::Environment));
    }

    #[test]
    fn insecure_or_incomplete_configuration_fails_closed() {
        assert!(JwtAuthenticationConfig::production("").is_err());
        let mut configuration = IdentityServiceConfiguration::development().expect("development");
        configuration.default_provider = AuthenticationProviderType::Saml;
        assert!(configuration.validate().is_err());
        configuration
            .enabled_providers
            .insert(AuthenticationProviderType::Saml);
        assert!(configuration.validate().is_err());
        let mut jwt = JwtAuthenticationConfig::development(Some("key".into()));
        jwt.algorithm = "none".into();
        assert!(jwt.validate(false).is_err());
    }

    #[test]
    fn canonical_config_snapshots_replace_service_local_file_and_environment_loading() {
        let expected = IdentityServiceConfiguration::development().expect("development");
        let snapshot = ConfigSnapshot {
            revision: 7,
            value: serde_json::json!({
                "services": {
                    "identity": serde_json::to_value(&expected).expect("configuration")
                }
            }),
            layers: vec!["base".into(), "development".into(), "environment".into()],
        };
        let decoded = IdentityServiceConfiguration::from_snapshot(&snapshot).expect("snapshot");
        assert_eq!(decoded.environment, IdentityEnvironment::Development);
        assert_eq!(decoded.service_name, expected.service_name);
        assert!(
            IdentityServiceConfiguration::from_snapshot(&ConfigSnapshot {
                revision: 1,
                value: serde_json::json!({"services": {}}),
                layers: vec![],
            })
            .is_err()
        );
        let decoded = IdentityServiceConfiguration::from_snapshot_with_secrets(
            &snapshot,
            &SecretRegistry::new(),
        )
        .expect("snapshot without references");
        assert_eq!(decoded.environment, IdentityEnvironment::Development);
    }
}
