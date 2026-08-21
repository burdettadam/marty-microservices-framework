//! `OpenID` Connect discovery, claims, JWKS, JWT parsing, and validation.

use std::collections::{BTreeMap, BTreeSet};
use std::sync::Arc;

use async_trait::async_trait;
use base64::{Engine, engine::general_purpose::URL_SAFE_NO_PAD};
use rand::Rng;
use serde::de::DeserializeOwned;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::uri::{valid_native_redirect_uri, valid_redirect_uri};
use crate::{OAuth2AccessToken, OAuth2GrantType, OAuth2ResponseType, SecurityError};

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum OidcCapability {
    AuthorizationCode,
    Implicit,
    Hybrid,
    ClientCredentials,
    Password,
    RefreshToken,
    Pkce,
    PkceS256,
    JwtTokens,
    ReferenceTokens,
    Userinfo,
    Introspection,
    Revocation,
    SessionManagement,
    FrontChannelLogout,
    BackChannelLogout,
    Discovery,
    DynamicRegistration,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum OidcClaimType {
    Sub,
    Iss,
    Aud,
    Exp,
    Iat,
    AuthTime,
    Nonce,
    Name,
    GivenName,
    FamilyName,
    MiddleName,
    Nickname,
    PreferredUsername,
    Profile,
    Picture,
    Website,
    Gender,
    Birthdate,
    Zoneinfo,
    Locale,
    UpdatedAt,
    Email,
    EmailVerified,
    PhoneNumber,
    PhoneNumberVerified,
    Address,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct OidcEndpoints {
    pub authorization_endpoint: String,
    pub token_endpoint: String,
    pub userinfo_endpoint: String,
    pub jwks_uri: String,
    pub issuer: String,
    pub registration_endpoint: Option<String>,
    pub introspection_endpoint: Option<String>,
    pub revocation_endpoint: Option<String>,
    pub end_session_endpoint: Option<String>,
    pub check_session_iframe: Option<String>,
    pub device_authorization_endpoint: Option<String>,
}

impl OidcEndpoints {
    pub fn validate(&self) -> Result<(), SecurityError> {
        for (name, endpoint) in [
            (
                "authorization_endpoint",
                self.authorization_endpoint.as_str(),
            ),
            ("token_endpoint", self.token_endpoint.as_str()),
            ("userinfo_endpoint", self.userinfo_endpoint.as_str()),
            ("jwks_uri", self.jwks_uri.as_str()),
            ("issuer", self.issuer.as_str()),
        ] {
            if !valid_oidc_endpoint(endpoint) {
                return Err(SecurityError::InvalidConfiguration(format!(
                    "OIDC {name} must use HTTPS except for loopback testing"
                )));
            }
        }
        for endpoint in [
            self.registration_endpoint.as_deref(),
            self.introspection_endpoint.as_deref(),
            self.revocation_endpoint.as_deref(),
            self.end_session_endpoint.as_deref(),
            self.check_session_iframe.as_deref(),
            self.device_authorization_endpoint.as_deref(),
        ]
        .into_iter()
        .flatten()
        {
            if !valid_oidc_endpoint(endpoint) {
                return Err(SecurityError::InvalidConfiguration(
                    "optional OIDC endpoints must use HTTPS except for loopback testing".into(),
                ));
            }
        }
        Ok(())
    }

    #[must_use]
    pub fn endpoint(&self, endpoint_type: &str) -> Option<&str> {
        match endpoint_type {
            "authorization" => Some(&self.authorization_endpoint),
            "token" => Some(&self.token_endpoint),
            "userinfo" => Some(&self.userinfo_endpoint),
            "jwks" => Some(&self.jwks_uri),
            "registration" => self.registration_endpoint.as_deref(),
            "introspection" => self.introspection_endpoint.as_deref(),
            "revocation" => self.revocation_endpoint.as_deref(),
            "end_session" => self.end_session_endpoint.as_deref(),
            "check_session" => self.check_session_iframe.as_deref(),
            "device_authorization" => self.device_authorization_endpoint.as_deref(),
            _ => None,
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OidcProviderMetadata {
    pub issuer: String,
    pub endpoints: OidcEndpoints,
    #[serde(default)]
    pub response_types_supported: BTreeSet<OAuth2ResponseType>,
    #[serde(default)]
    pub response_modes_supported: BTreeSet<OidcResponseMode>,
    #[serde(default)]
    pub grant_types_supported: BTreeSet<OAuth2GrantType>,
    #[serde(default)]
    pub subject_types_supported: BTreeSet<String>,
    #[serde(default)]
    pub id_token_signing_alg_values_supported: BTreeSet<String>,
    #[serde(default)]
    pub id_token_encryption_alg_values_supported: BTreeSet<String>,
    #[serde(default)]
    pub userinfo_signing_alg_values_supported: BTreeSet<String>,
    #[serde(default)]
    pub userinfo_encryption_alg_values_supported: BTreeSet<String>,
    #[serde(default)]
    pub token_endpoint_auth_methods_supported: BTreeSet<String>,
    #[serde(default)]
    pub scopes_supported: BTreeSet<String>,
    #[serde(default)]
    pub claims_supported: BTreeSet<String>,
    #[serde(default)]
    pub claim_types_supported: BTreeSet<String>,
    #[serde(default)]
    pub code_challenge_methods_supported: BTreeSet<String>,
    #[serde(default)]
    pub capabilities: BTreeSet<OidcCapability>,
    #[serde(default)]
    pub custom_metadata: BTreeMap<String, Value>,
}

impl OidcProviderMetadata {
    pub fn validate(&self) -> Result<(), SecurityError> {
        self.endpoints.validate()?;
        if self.issuer != self.endpoints.issuer {
            return Err(SecurityError::InvalidConfiguration(
                "OIDC metadata issuer must match endpoint issuer".into(),
            ));
        }
        if self.response_types_supported.is_empty()
            || self.subject_types_supported.is_empty()
            || self.id_token_signing_alg_values_supported.is_empty()
        {
            return Err(SecurityError::InvalidConfiguration(
                "OIDC metadata omits required capabilities".into(),
            ));
        }
        if self
            .id_token_signing_alg_values_supported
            .iter()
            .any(|algorithm| algorithm.eq_ignore_ascii_case("none"))
        {
            return Err(SecurityError::InvalidConfiguration(
                "unsigned OIDC ID tokens are not supported".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn supports_pkce(&self) -> bool {
        !self.code_challenge_methods_supported.is_empty()
            || self.capabilities.contains(&OidcCapability::Pkce)
    }

    #[must_use]
    pub fn supports_s256_pkce(&self) -> bool {
        self.code_challenge_methods_supported.contains("S256")
            || self.capabilities.contains(&OidcCapability::PkceS256)
    }

    #[must_use]
    pub fn supports_response_type(&self, response_type: OAuth2ResponseType) -> bool {
        self.response_types_supported.contains(&response_type)
    }

    #[must_use]
    pub fn supports_grant_type(&self, grant_type: OAuth2GrantType) -> bool {
        self.grant_types_supported.contains(&grant_type)
    }

    #[must_use]
    pub fn supports_scope(&self, scope: &str) -> bool {
        self.scopes_supported.contains(scope)
    }

    #[must_use]
    pub fn supports_capability(&self, capability: OidcCapability) -> bool {
        self.capabilities.contains(&capability)
    }

    #[must_use]
    pub fn preferred_signing_algorithm(&self) -> Option<&str> {
        ["EdDSA", "ES256", "ES384", "RS256"]
            .into_iter()
            .find(|algorithm| {
                self.id_token_signing_alg_values_supported
                    .contains(*algorithm)
            })
            .or_else(|| {
                self.id_token_signing_alg_values_supported
                    .iter()
                    .next()
                    .map(String::as_str)
            })
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct OidcProviderConfiguration {
    pub provider_name: String,
    pub issuer_url: String,
    pub client_id: String,
    #[serde(skip_serializing)]
    pub client_secret: Option<String>,
    pub metadata: Option<OidcProviderMetadata>,
    pub discovery_url: Option<String>,
    pub auto_discovery: bool,
    pub discovery_cache_ttl_ms: u64,
    pub redirect_uri: String,
    pub post_logout_redirect_uri: Option<String>,
    #[serde(default)]
    pub default_scopes: BTreeSet<String>,
    pub require_https: bool,
    pub validate_issuer: bool,
    pub validate_audience: bool,
    pub clock_skew_tolerance_seconds: u64,
    pub jwks_cache_ttl_ms: u64,
    pub metadata_cache_ttl_ms: u64,
    pub state_ttl_ms: u64,
    pub nonce_ttl_ms: u64,
    pub last_discovery_attempt_ms: Option<u64>,
    pub last_successful_discovery_ms: Option<u64>,
    pub discovery_error: Option<String>,
}

impl OidcProviderConfiguration {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.provider_name.trim().is_empty()
            || self.client_id.trim().is_empty()
            || !valid_oidc_endpoint(&self.issuer_url)
            || !valid_native_redirect_uri(&self.redirect_uri)
            || !self.default_scopes.contains("openid")
            || self.discovery_cache_ttl_ms == 0
            || self.jwks_cache_ttl_ms == 0
            || self.state_ttl_ms == 0
            || self.nonce_ttl_ms == 0
        {
            return Err(SecurityError::InvalidConfiguration(
                "invalid OIDC provider configuration".into(),
            ));
        }
        if self.require_https && !self.redirect_uri.starts_with("https://") {
            return Err(SecurityError::InvalidConfiguration(
                "OIDC redirect URI must use HTTPS".into(),
            ));
        }
        if let Some(metadata) = &self.metadata {
            metadata.validate()?;
            if self.validate_issuer && metadata.issuer != self.issuer_url {
                return Err(SecurityError::InvalidConfiguration(
                    "discovered OIDC issuer mismatch".into(),
                ));
            }
        }
        Ok(())
    }

    #[must_use]
    pub fn discovery_url(&self) -> String {
        self.discovery_url
            .clone()
            .unwrap_or_else(|| create_discovery_url(&self.issuer_url))
    }

    #[must_use]
    pub fn discovery_needed_at(&self, now_ms: u64) -> bool {
        self.auto_discovery
            && self
                .last_successful_discovery_ms
                .is_none_or(|last| last.saturating_add(self.discovery_cache_ttl_ms) <= now_ms)
    }

    pub fn mark_discovery_success(
        &mut self,
        metadata: OidcProviderMetadata,
        now_ms: u64,
    ) -> Result<(), SecurityError> {
        metadata.validate()?;
        if self.validate_issuer && metadata.issuer != self.issuer_url {
            return Err(SecurityError::Unauthorized(
                "discovered OIDC issuer mismatch".into(),
            ));
        }
        self.metadata = Some(metadata);
        self.last_discovery_attempt_ms = Some(now_ms);
        self.last_successful_discovery_ms = Some(now_ms);
        self.discovery_error = None;
        Ok(())
    }

    pub fn mark_discovery_failure(&mut self, error: impl Into<String>, now_ms: u64) {
        self.last_discovery_attempt_ms = Some(now_ms);
        self.discovery_error = Some(error.into());
    }

    #[must_use]
    pub fn is_discovered(&self) -> bool {
        self.metadata.is_some()
            && self.last_successful_discovery_ms.is_some()
            && self.discovery_error.is_none()
    }

    #[must_use]
    pub fn authorization_endpoint(&self) -> Option<&str> {
        self.metadata
            .as_ref()
            .map(|metadata| metadata.endpoints.authorization_endpoint.as_str())
    }

    #[must_use]
    pub fn token_endpoint(&self) -> Option<&str> {
        self.metadata
            .as_ref()
            .map(|metadata| metadata.endpoints.token_endpoint.as_str())
    }

    #[must_use]
    pub fn userinfo_endpoint(&self) -> Option<&str> {
        self.metadata
            .as_ref()
            .map(|metadata| metadata.endpoints.userinfo_endpoint.as_str())
    }

    #[must_use]
    pub fn jwks_uri(&self) -> Option<&str> {
        self.metadata
            .as_ref()
            .map(|metadata| metadata.endpoints.jwks_uri.as_str())
    }

    #[must_use]
    pub fn supports_flow(&self, flow: &str) -> bool {
        let Some(metadata) = &self.metadata else {
            return false;
        };
        match flow {
            "authorization_code" => {
                metadata.supports_grant_type(OAuth2GrantType::AuthorizationCode)
            }
            "implicit" => metadata.supports_grant_type(OAuth2GrantType::Implicit),
            "hybrid" => [
                OAuth2ResponseType::CodeIdToken,
                OAuth2ResponseType::CodeToken,
                OAuth2ResponseType::CodeTokenIdToken,
            ]
            .into_iter()
            .any(|response| metadata.supports_response_type(response)),
            "client_credentials" => {
                metadata.supports_grant_type(OAuth2GrantType::ClientCredentials)
            }
            "password" => metadata.supports_grant_type(OAuth2GrantType::Password),
            "refresh_token" => metadata.supports_grant_type(OAuth2GrantType::RefreshToken),
            _ => false,
        }
    }

    #[must_use]
    pub fn recommended_scopes(&self, additional: &BTreeSet<String>) -> BTreeSet<String> {
        let mut scopes = self.default_scopes.clone();
        scopes.extend(additional.iter().cloned());
        if let Some(metadata) = &self.metadata
            && !metadata.scopes_supported.is_empty()
        {
            scopes = scopes
                .intersection(&metadata.scopes_supported)
                .cloned()
                .collect();
        }
        scopes.insert("openid".into());
        scopes
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OidcDiscoveryResult {
    pub success: bool,
    pub provider_configuration: Option<OidcProviderConfiguration>,
    pub error_code: Option<String>,
    pub error_message: Option<String>,
    #[serde(default)]
    pub error_details: BTreeMap<String, Value>,
    pub discovery_url: String,
    pub discovery_duration_ms: u64,
    pub discovered_at_ms: u64,
    #[serde(default)]
    pub supported_flows: BTreeSet<OAuth2GrantType>,
    #[serde(default)]
    pub supported_scopes: BTreeSet<String>,
    #[serde(default)]
    pub security_features: BTreeSet<OidcCapability>,
}

impl OidcDiscoveryResult {
    #[must_use]
    pub fn success(
        configuration: OidcProviderConfiguration,
        discovery_url: impl Into<String>,
        duration_ms: u64,
        discovered_at_ms: u64,
    ) -> Self {
        let mut supported_flows = BTreeSet::new();
        let mut supported_scopes = BTreeSet::new();
        let mut security_features = BTreeSet::new();
        if let Some(metadata) = &configuration.metadata {
            supported_flows.clone_from(&metadata.grant_types_supported);
            supported_scopes.clone_from(&metadata.scopes_supported);
            if metadata.supports_pkce() {
                security_features.insert(OidcCapability::Pkce);
            }
            if metadata.supports_s256_pkce() {
                security_features.insert(OidcCapability::PkceS256);
            }
        }
        Self {
            success: true,
            provider_configuration: Some(configuration),
            error_code: None,
            error_message: None,
            error_details: BTreeMap::new(),
            discovery_url: discovery_url.into(),
            discovery_duration_ms: duration_ms,
            discovered_at_ms,
            supported_flows,
            supported_scopes,
            security_features,
        }
    }

    #[must_use]
    pub fn failure(
        configuration: OidcProviderConfiguration,
        error_code: impl Into<String>,
        error_message: impl Into<String>,
        discovery_url: impl Into<String>,
        duration_ms: u64,
        discovered_at_ms: u64,
        error_details: BTreeMap<String, Value>,
    ) -> Self {
        Self {
            success: false,
            provider_configuration: Some(configuration),
            error_code: Some(error_code.into()),
            error_message: Some(error_message.into()),
            error_details,
            discovery_url: discovery_url.into(),
            discovery_duration_ms: duration_ms,
            discovered_at_ms,
            supported_flows: BTreeSet::new(),
            supported_scopes: BTreeSet::new(),
            security_features: BTreeSet::new(),
        }
    }

    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.success
            && (self.provider_configuration.is_none()
                || self.error_code.is_some()
                || self.error_message.is_some())
        {
            return Err(SecurityError::InvalidConfiguration(
                "successful OIDC discovery requires configuration and no error".into(),
            ));
        }
        if !self.success && (self.error_code.is_none() || self.error_message.is_none()) {
            return Err(SecurityError::InvalidConfiguration(
                "failed OIDC discovery requires an error".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum OidcResponseMode {
    Query,
    Fragment,
    FormPost,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum OidcPrompt {
    None,
    Login,
    Consent,
    SelectAccount,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OidcIdToken {
    pub token_id: String,
    pub subject: String,
    pub issuer: String,
    pub audience: BTreeSet<String>,
    pub expires_at_seconds: u64,
    pub issued_at_seconds: u64,
    pub auth_time_seconds: Option<u64>,
    pub nonce: Option<String>,
    #[serde(default)]
    pub claims: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OidcIdTokenIssue {
    pub subject: String,
    pub issuer: String,
    pub audience: BTreeSet<String>,
    #[serde(default)]
    pub claims: BTreeMap<String, Value>,
    pub nonce: Option<String>,
    pub auth_time_seconds: Option<u64>,
    pub now_seconds: u64,
    pub lifetime_seconds: u64,
}

impl OidcIdToken {
    #[must_use]
    pub fn issue(request: OidcIdTokenIssue) -> Self {
        Self {
            token_id: uuid::Uuid::new_v4().to_string(),
            subject: request.subject,
            issuer: request.issuer,
            audience: request.audience,
            expires_at_seconds: request.now_seconds.saturating_add(request.lifetime_seconds),
            issued_at_seconds: request.now_seconds,
            auth_time_seconds: request.auth_time_seconds.or(Some(request.now_seconds)),
            nonce: request.nonce,
            claims: request.claims,
        }
    }

    pub fn validate_at(&self, now_seconds: u64) -> Result<(), SecurityError> {
        if self.token_id.trim().is_empty()
            || self.subject.trim().is_empty()
            || !valid_oidc_endpoint(&self.issuer)
            || self.audience.is_empty()
            || self.expires_at_seconds <= self.issued_at_seconds
            || now_seconds >= self.expires_at_seconds
        {
            return Err(SecurityError::Unauthorized(
                "invalid or expired OIDC ID token".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn payload(&self) -> BTreeMap<String, Value> {
        let mut payload = self.claims.clone();
        payload.insert("jti".into(), Value::String(self.token_id.clone()));
        payload.insert("sub".into(), Value::String(self.subject.clone()));
        payload.insert("iss".into(), Value::String(self.issuer.clone()));
        payload.insert("aud".into(), audience_value(&self.audience));
        payload.insert("exp".into(), self.expires_at_seconds.into());
        payload.insert("iat".into(), self.issued_at_seconds.into());
        if let Some(auth_time) = self.auth_time_seconds {
            payload.insert("auth_time".into(), auth_time.into());
        }
        if let Some(nonce) = &self.nonce {
            payload.insert("nonce".into(), Value::String(nonce.clone()));
        }
        payload
    }

    #[must_use]
    pub fn claim(&self, name: &str) -> Option<Value> {
        self.payload().get(name).cloned()
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OidcUserInfo {
    pub subject: String,
    #[serde(default)]
    pub claims: BTreeMap<String, Value>,
}

impl OidcUserInfo {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.subject.trim().is_empty() {
            Err(SecurityError::InvalidConfiguration(
                "OIDC userinfo subject is required".into(),
            ))
        } else {
            Ok(())
        }
    }

    #[must_use]
    pub fn to_map(&self) -> BTreeMap<String, Value> {
        let mut value = self.claims.clone();
        value.insert("sub".into(), Value::String(self.subject.clone()));
        value
    }

    pub fn from_map(mut value: BTreeMap<String, Value>) -> Result<Self, SecurityError> {
        let subject = value
            .remove("sub")
            .and_then(|value| value.as_str().map(str::to_owned))
            .ok_or_else(|| {
                SecurityError::InvalidConfiguration("OIDC userinfo subject is required".into())
            })?;
        let user_info = Self {
            subject,
            claims: value,
        };
        user_info.validate()?;
        Ok(user_info)
    }

    #[must_use]
    pub fn claim(&self, name: &str) -> Option<&Value> {
        self.claims.get(name)
    }

    #[must_use]
    pub fn has_claim(&self, name: &str) -> bool {
        name == "sub" || self.claims.contains_key(name)
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OidcAuthenticationRequest {
    pub client_id: String,
    pub redirect_uri: String,
    pub response_type: OAuth2ResponseType,
    #[serde(default)]
    pub scopes: BTreeSet<String>,
    pub state: Option<String>,
    pub response_mode: Option<OidcResponseMode>,
    pub nonce: Option<String>,
    pub display: Option<String>,
    #[serde(default)]
    pub prompts: BTreeSet<OidcPrompt>,
    pub max_age_seconds: Option<u64>,
    #[serde(default)]
    pub ui_locales: Vec<String>,
    pub id_token_hint: Option<String>,
    pub login_hint: Option<String>,
    #[serde(default)]
    pub acr_values: Vec<String>,
    #[serde(default)]
    pub claims: BTreeMap<String, Value>,
    pub request_id: String,
    pub created_at_ms: u64,
}

impl OidcAuthenticationRequest {
    pub fn from_query_params(
        params: &BTreeMap<String, String>,
        now_ms: u64,
    ) -> Result<Self, SecurityError> {
        let response_type = serde_json::from_value(Value::String(
            params
                .get("response_type")
                .map_or("code", String::as_str)
                .to_owned(),
        ))
        .map_err(|_| {
            SecurityError::InvalidConfiguration("unsupported OIDC response type".into())
        })?;
        let response_mode = params
            .get("response_mode")
            .map(|value| {
                serde_json::from_value(Value::String(value.clone())).map_err(|_| {
                    SecurityError::InvalidConfiguration("unsupported OIDC response mode".into())
                })
            })
            .transpose()?;
        let prompts = params
            .get("prompt")
            .map_or("", String::as_str)
            .split_whitespace()
            .map(|prompt| {
                serde_json::from_value(Value::String(prompt.to_owned())).map_err(|_| {
                    SecurityError::InvalidConfiguration("unsupported OIDC prompt".into())
                })
            })
            .collect::<Result<_, _>>()?;
        let claims = params
            .get("claims")
            .map(|claims| {
                serde_json::from_str(claims).map_err(|_| {
                    SecurityError::InvalidConfiguration("invalid OIDC claims JSON".into())
                })
            })
            .transpose()?
            .unwrap_or_default();
        let max_age_seconds = params
            .get("max_age")
            .map(|value| {
                value
                    .parse()
                    .map_err(|_| SecurityError::InvalidConfiguration("invalid OIDC max_age".into()))
            })
            .transpose()?;
        let request = Self {
            client_id: oidc_required_param(params, "client_id")?.to_owned(),
            redirect_uri: oidc_required_param(params, "redirect_uri")?.to_owned(),
            response_type,
            scopes: params
                .get("scope")
                .map_or("openid", String::as_str)
                .split_whitespace()
                .map(str::to_owned)
                .collect(),
            state: params.get("state").cloned(),
            response_mode,
            nonce: params.get("nonce").cloned(),
            display: params.get("display").cloned(),
            prompts,
            max_age_seconds,
            ui_locales: split_parameter(params.get("ui_locales")),
            id_token_hint: params.get("id_token_hint").cloned(),
            login_hint: params.get("login_hint").cloned(),
            acr_values: split_parameter(params.get("acr_values")),
            claims,
            request_id: uuid::Uuid::new_v4().to_string(),
            created_at_ms: now_ms,
        };
        request.validate()?;
        Ok(request)
    }

    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.client_id.trim().is_empty()
            || !valid_native_redirect_uri(&self.redirect_uri)
            || !self.scopes.contains("openid")
            || self.request_id.trim().is_empty()
            || (self.prompts.contains(&OidcPrompt::None) && self.prompts.len() > 1)
            || (self.response_type.requires_openid() && self.nonce.is_none())
        {
            return Err(SecurityError::InvalidConfiguration(
                "invalid OIDC authentication request".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn requires_id_token(&self) -> bool {
        self.response_type.requires_openid()
    }

    #[must_use]
    pub fn has_prompt(&self, prompt: OidcPrompt) -> bool {
        self.prompts.contains(&prompt)
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OidcDiscoveryDocument {
    pub metadata: OidcProviderMetadata,
}

impl OidcDiscoveryDocument {
    pub fn validate(&self) -> Result<(), SecurityError> {
        self.metadata.validate()
    }

    pub fn to_value(&self) -> Result<Value, SecurityError> {
        provider_metadata_to_value(&self.metadata)
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub enum JwkType {
    #[serde(rename = "RSA")]
    Rsa,
    #[serde(rename = "EC")]
    Ec,
    #[serde(rename = "oct")]
    Oct,
    #[serde(rename = "OKP")]
    Okp,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub enum JwkUse {
    #[serde(rename = "sig")]
    Signature,
    #[serde(rename = "enc")]
    Encryption,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct Jwk {
    pub kid: String,
    pub kty: JwkType,
    #[serde(rename = "use")]
    pub key_use: Option<JwkUse>,
    #[serde(default)]
    pub key_ops: BTreeSet<String>,
    pub alg: Option<String>,
    pub n: Option<String>,
    pub e: Option<String>,
    pub crv: Option<String>,
    pub x: Option<String>,
    pub y: Option<String>,
    #[serde(skip_serializing)]
    pub k: Option<String>,
    #[serde(default)]
    pub x5c: Vec<String>,
    pub x5t: Option<String>,
    #[serde(rename = "x5t#S256")]
    pub x5t_s256: Option<String>,
    pub x5u: Option<String>,
    #[serde(default, flatten)]
    pub additional_properties: BTreeMap<String, Value>,
}

impl Jwk {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.kid.trim().is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "JWK kid is required".into(),
            ));
        }
        let complete = match self.kty {
            JwkType::Rsa => self.n.is_some() && self.e.is_some(),
            JwkType::Ec => self.crv.is_some() && self.x.is_some() && self.y.is_some(),
            JwkType::Oct => self.k.is_some(),
            JwkType::Okp => self.crv.is_some() && self.x.is_some(),
        };
        if !complete {
            return Err(SecurityError::InvalidConfiguration(
                "JWK key material is incomplete".into(),
            ));
        }
        if self
            .alg
            .as_deref()
            .is_some_and(|alg| alg.eq_ignore_ascii_case("none"))
        {
            return Err(SecurityError::InvalidConfiguration(
                "unsigned JWT algorithm is forbidden".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn is_for_signature(&self) -> bool {
        self.key_use.is_none_or(|usage| usage == JwkUse::Signature)
            && (self.key_ops.is_empty() || self.key_ops.contains("verify"))
    }

    #[must_use]
    pub fn supports_algorithm(&self, algorithm: &str) -> bool {
        if let Some(configured) = &self.alg {
            return configured == algorithm;
        }
        match self.kty {
            JwkType::Rsa => matches!(
                algorithm,
                "RS256" | "RS384" | "RS512" | "PS256" | "PS384" | "PS512"
            ),
            JwkType::Ec => match self.crv.as_deref() {
                Some("P-256") => algorithm == "ES256",
                Some("P-384") => algorithm == "ES384",
                Some("P-521") => algorithm == "ES512",
                Some("secp256k1") => algorithm == "ES256K",
                _ => false,
            },
            JwkType::Oct => matches!(algorithm, "HS256" | "HS384" | "HS512"),
            JwkType::Okp => {
                matches!(self.crv.as_deref(), Some("Ed25519" | "Ed448")) && algorithm == "EdDSA"
            }
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct Jwks {
    pub keys: Vec<Jwk>,
    pub retrieved_at_ms: u64,
    pub cache_control: Option<String>,
    pub etag: Option<String>,
}

impl Jwks {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.keys.is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "JWKS cannot be empty".into(),
            ));
        }
        let mut ids = BTreeSet::new();
        for key in &self.keys {
            key.validate()?;
            if !ids.insert(&key.kid) {
                return Err(SecurityError::Conflict("duplicate JWK kid".into()));
            }
        }
        Ok(())
    }

    #[must_use]
    pub fn key(&self, kid: &str, algorithm: &str) -> Option<&Jwk> {
        self.keys.iter().find(|key| {
            key.kid == kid && key.is_for_signature() && key.supports_algorithm(algorithm)
        })
    }

    #[must_use]
    pub fn key_by_id(&self, kid: &str) -> Option<&Jwk> {
        self.keys.iter().find(|key| key.kid == kid)
    }

    #[must_use]
    pub fn keys_for_algorithm(&self, algorithm: &str) -> Vec<&Jwk> {
        self.keys
            .iter()
            .filter(|key| key.supports_algorithm(algorithm))
            .collect()
    }

    #[must_use]
    pub fn signature_keys(&self) -> Vec<&Jwk> {
        self.keys
            .iter()
            .filter(|key| key.is_for_signature())
            .collect()
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct JwtHeader {
    pub alg: String,
    pub kid: Option<String>,
    pub typ: Option<String>,
    pub jku: Option<String>,
    pub jwk: Option<Jwk>,
    pub x5u: Option<String>,
    #[serde(default)]
    pub x5c: Vec<String>,
    pub x5t: Option<String>,
    #[serde(rename = "x5t#S256")]
    pub x5t_s256: Option<String>,
    pub cty: Option<String>,
    #[serde(default)]
    pub crit: BTreeSet<String>,
    #[serde(default, flatten)]
    pub additional_claims: BTreeMap<String, Value>,
}

impl JwtHeader {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if !supported_signature_algorithm(&self.alg) {
            return Err(SecurityError::Unauthorized(
                "JWT requires a supported signature algorithm".into(),
            ));
        }
        if !self.crit.is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "unsupported JWT critical headers".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct JwtPayload {
    pub issuer: Option<String>,
    pub subject: Option<String>,
    #[serde(default)]
    pub audiences: BTreeSet<String>,
    pub expires_at_seconds: Option<u64>,
    pub not_before_seconds: Option<u64>,
    pub issued_at_seconds: Option<u64>,
    pub token_id: Option<String>,
    pub nonce: Option<String>,
    pub scope: Option<String>,
    #[serde(default)]
    pub groups: BTreeSet<String>,
    #[serde(default)]
    pub roles: BTreeSet<String>,
    #[serde(default)]
    pub permissions: BTreeSet<String>,
    #[serde(default)]
    pub claims: BTreeMap<String, Value>,
}

impl JwtPayload {
    #[must_use]
    pub fn audiences(&self) -> Vec<&str> {
        self.audiences.iter().map(String::as_str).collect()
    }

    #[must_use]
    pub fn is_expired_at(&self, now_seconds: u64, skew_seconds: u64) -> bool {
        self.expires_at_seconds
            .is_some_and(|expires| now_seconds >= expires.saturating_add(skew_seconds))
    }

    #[must_use]
    pub fn is_not_yet_valid_at(&self, now_seconds: u64, skew_seconds: u64) -> bool {
        self.not_before_seconds
            .is_some_and(|not_before| now_seconds.saturating_add(skew_seconds) < not_before)
    }

    #[must_use]
    pub fn has_scope(&self, scope: &str) -> bool {
        self.scope
            .as_deref()
            .unwrap_or_default()
            .split_whitespace()
            .any(|candidate| candidate == scope)
    }

    #[must_use]
    pub fn claim(&self, name: &str) -> Option<&Value> {
        self.claims.get(name)
    }

    #[must_use]
    pub fn claim_value(&self, name: &str) -> Option<Value> {
        match name {
            "iss" => self.issuer.clone().map(Value::String),
            "sub" => self.subject.clone().map(Value::String),
            "aud" if self.audiences.len() == 1 => {
                self.audiences.first().cloned().map(Value::String)
            }
            "aud" if !self.audiences.is_empty() => Some(Value::Array(
                self.audiences.iter().cloned().map(Value::String).collect(),
            )),
            "exp" => self.expires_at_seconds.map(Value::from),
            "nbf" => self.not_before_seconds.map(Value::from),
            "iat" => self.issued_at_seconds.map(Value::from),
            "jti" => self.token_id.clone().map(Value::String),
            "nonce" => self.nonce.clone().map(Value::String),
            "scope" => self.scope.clone().map(Value::String),
            "groups" => Some(string_set_value(&self.groups)),
            "roles" => Some(string_set_value(&self.roles)),
            "permissions" => Some(string_set_value(&self.permissions)),
            _ => self.claims.get(name).cloned(),
        }
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum OidcTokenType {
    IdToken,
    AccessToken,
    RefreshToken,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TokenStatus {
    Valid,
    Expired,
    InvalidSignature,
    InvalidIssuer,
    InvalidAudience,
    InvalidFormat,
    NotYetValid,
    Revoked,
    UnknownKid,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OidcToken {
    pub token_type: OidcTokenType,
    #[serde(skip_serializing)]
    pub raw_token: String,
    pub header: JwtHeader,
    pub payload: JwtPayload,
    #[serde(skip_serializing)]
    pub signing_input: Vec<u8>,
    #[serde(skip_serializing)]
    pub signature: Vec<u8>,
    pub validation_status: Option<TokenStatus>,
    pub validation_error: Option<String>,
    #[serde(default)]
    pub validation_details: BTreeMap<String, Value>,
    pub validated_at_ms: Option<u64>,
    pub validated_with_key: Option<String>,
    #[serde(default)]
    pub issuer_metadata: BTreeMap<String, Value>,
}

impl OidcToken {
    pub fn parse(raw_token: &str, token_type: OidcTokenType) -> Result<Self, SecurityError> {
        let parts: Vec<_> = raw_token.split('.').collect();
        if parts.len() != 3 || parts.iter().any(|part| part.is_empty()) {
            return Err(SecurityError::Unauthorized(
                "JWT must have three segments".into(),
            ));
        }
        let header = parse_jwt_header(parts[0])?;
        let payload = parse_jwt_payload(parts[1])?;
        let signature = URL_SAFE_NO_PAD
            .decode(parts[2])
            .map_err(|_| SecurityError::Unauthorized("invalid JWT signature encoding".into()))?;
        if signature.is_empty() {
            return Err(SecurityError::Unauthorized(
                "JWT signature is required".into(),
            ));
        }
        if token_type == OidcTokenType::IdToken
            && (payload.issuer.is_none()
                || payload.subject.is_none()
                || payload.audiences.is_empty()
                || payload.expires_at_seconds.is_none()
                || payload.issued_at_seconds.is_none())
        {
            return Err(SecurityError::Unauthorized(
                "OIDC ID token is missing required claims".into(),
            ));
        }
        Ok(Self {
            token_type,
            raw_token: raw_token.into(),
            header,
            payload,
            signing_input: format!("{}.{}", parts[0], parts[1]).into_bytes(),
            signature,
            validation_status: None,
            validation_error: None,
            validation_details: BTreeMap::new(),
            validated_at_ms: None,
            validated_with_key: None,
            issuer_metadata: BTreeMap::new(),
        })
    }

    #[must_use]
    pub fn is_valid(&self) -> bool {
        self.validation_status == Some(TokenStatus::Valid)
    }

    #[must_use]
    pub fn is_expired_at(&self, now_seconds: u64, skew_seconds: u64) -> bool {
        self.payload.is_expired_at(now_seconds, skew_seconds)
    }

    #[must_use]
    pub fn subject(&self) -> Option<&str> {
        self.payload.subject.as_deref()
    }

    #[must_use]
    pub fn claim(&self, name: &str) -> Option<Value> {
        self.payload.claim_value(name)
    }

    #[must_use]
    pub fn has_scope(&self, scope: &str) -> bool {
        self.payload.has_scope(scope)
    }

    #[must_use]
    pub fn has_role(&self, role: &str) -> bool {
        self.payload.roles.contains(role)
    }

    #[must_use]
    pub fn has_permission(&self, permission: &str) -> bool {
        self.payload.permissions.contains(permission)
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct TokenValidationRequest {
    pub raw_token: String,
    pub token_type: OidcTokenType,
    pub expected_issuer: Option<String>,
    #[serde(default)]
    pub expected_audiences: BTreeSet<String>,
    pub expected_nonce: Option<String>,
    pub verify_signature: bool,
    pub verify_expiration: bool,
    pub verify_not_before: bool,
    pub verify_issuer: bool,
    pub verify_audience: bool,
    pub clock_skew_tolerance_seconds: u64,
    pub jwks: Option<Jwks>,
    pub jwks_uri: Option<String>,
}

impl TokenValidationRequest {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.raw_token.trim().is_empty()
            || (self.verify_issuer && self.expected_issuer.is_none())
            || (self.verify_audience && self.expected_audiences.is_empty())
            || (self.verify_signature && self.jwks.is_none())
        {
            return Err(SecurityError::InvalidConfiguration(
                "token validation request is missing required verification material".into(),
            ));
        }
        if let Some(jwks) = &self.jwks {
            jwks.validate()?;
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct TokenValidationResult {
    pub success: bool,
    pub token: Option<OidcToken>,
    pub error_code: Option<TokenStatus>,
    pub error_message: Option<String>,
    #[serde(default)]
    pub validation_errors: Vec<String>,
    pub validation_duration_ms: u64,
    pub key_used: Option<String>,
    pub algorithm_used: Option<String>,
    pub signature_valid: bool,
    pub expiration_valid: bool,
    pub issuer_valid: bool,
    pub audience_valid: bool,
    pub nonce_valid: bool,
}

impl TokenValidationResult {
    #[must_use]
    pub fn failure(
        status: TokenStatus,
        message: impl Into<String>,
        validation_errors: Vec<String>,
        duration_ms: u64,
    ) -> Self {
        Self {
            success: false,
            token: None,
            error_code: Some(status),
            error_message: Some(message.into()),
            validation_errors,
            validation_duration_ms: duration_ms,
            key_used: None,
            algorithm_used: None,
            signature_valid: false,
            expiration_valid: false,
            issuer_valid: false,
            audience_valid: false,
            nonce_valid: false,
        }
    }
}

#[async_trait]
pub trait JwtSignatureVerifier: Send + Sync {
    async fn verify(
        &self,
        algorithm: &str,
        key: &Jwk,
        signing_input: &[u8],
        signature: &[u8],
    ) -> Result<bool, SecurityError>;
}

pub struct OidcTokenValidator {
    signature_verifier: Option<Arc<dyn JwtSignatureVerifier>>,
}

impl OidcTokenValidator {
    #[must_use]
    pub const fn new(signature_verifier: Option<Arc<dyn JwtSignatureVerifier>>) -> Self {
        Self { signature_verifier }
    }

    pub async fn validate(
        &self,
        request: &TokenValidationRequest,
        now_seconds: u64,
        started_at_ms: u64,
        finished_at_ms: u64,
    ) -> Result<TokenValidationResult, SecurityError> {
        request.validate()?;
        let token = OidcToken::parse(&request.raw_token, request.token_type)?;
        let mut result = TokenValidationResult {
            success: false,
            token: None,
            error_code: None,
            error_message: None,
            validation_errors: Vec::new(),
            validation_duration_ms: finished_at_ms.saturating_sub(started_at_ms),
            key_used: None,
            algorithm_used: Some(token.header.alg.clone()),
            signature_valid: !request.verify_signature,
            expiration_valid: !request.verify_expiration,
            issuer_valid: !request.verify_issuer,
            audience_valid: !request.verify_audience,
            nonce_valid: request.expected_nonce.is_none(),
        };

        if request.verify_expiration {
            result.expiration_valid = token.payload.expires_at_seconds.is_some()
                && !token
                    .payload
                    .is_expired_at(now_seconds, request.clock_skew_tolerance_seconds);
            if !result.expiration_valid {
                result.validation_errors.push("token expired".into());
                result.error_code = Some(TokenStatus::Expired);
            }
        }
        if request.verify_not_before
            && token
                .payload
                .is_not_yet_valid_at(now_seconds, request.clock_skew_tolerance_seconds)
        {
            result
                .validation_errors
                .push("token is not yet valid".into());
            result.error_code.get_or_insert(TokenStatus::NotYetValid);
        }
        if request.verify_issuer {
            result.issuer_valid = token.payload.issuer == request.expected_issuer;
            if !result.issuer_valid {
                result.validation_errors.push("issuer mismatch".into());
                result.error_code.get_or_insert(TokenStatus::InvalidIssuer);
            }
        }
        if request.verify_audience {
            result.audience_valid = !token
                .payload
                .audiences
                .is_disjoint(&request.expected_audiences);
            if !result.audience_valid {
                result.validation_errors.push("audience mismatch".into());
                result
                    .error_code
                    .get_or_insert(TokenStatus::InvalidAudience);
            }
        }
        if let Some(expected_nonce) = &request.expected_nonce {
            result.nonce_valid = token.payload.nonce.as_ref() == Some(expected_nonce);
            if !result.nonce_valid {
                result.validation_errors.push("nonce mismatch".into());
                result.error_code.get_or_insert(TokenStatus::InvalidFormat);
            }
        }
        if request.verify_signature {
            let kid =
                token.header.kid.as_deref().ok_or_else(|| {
                    SecurityError::Unauthorized("signed JWT requires a kid".into())
                })?;
            let key = request
                .jwks
                .as_ref()
                .and_then(|jwks| jwks.key(kid, &token.header.alg));
            let Some(key) = key else {
                result.validation_errors.push("unknown signing key".into());
                result.error_code.get_or_insert(TokenStatus::UnknownKid);
                return Ok(result);
            };
            let verifier = self.signature_verifier.as_ref().ok_or_else(|| {
                SecurityError::ProviderUnavailable("JWT signature verifier".into())
            })?;
            result.signature_valid = verifier
                .verify(
                    &token.header.alg,
                    key,
                    &token.signing_input,
                    &token.signature,
                )
                .await?;
            result.key_used = Some(key.kid.clone());
            if !result.signature_valid {
                result.validation_errors.push("invalid signature".into());
                result
                    .error_code
                    .get_or_insert(TokenStatus::InvalidSignature);
            }
        }

        Ok(finish_validation(token, result, finished_at_ms))
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct JwksCache {
    pub issuer: String,
    pub jwks_uri: String,
    pub jwks: Option<Jwks>,
    pub cached_at_ms: Option<u64>,
    pub cache_ttl_ms: u64,
    pub etag: Option<String>,
    pub last_modified: Option<String>,
    pub hit_count: u64,
    pub miss_count: u64,
    pub refresh_count: u64,
}

impl JwksCache {
    #[must_use]
    pub fn is_expired_at(&self, now_ms: u64) -> bool {
        self.jwks.is_none()
            || self
                .cached_at_ms
                .is_none_or(|cached| cached.saturating_add(self.cache_ttl_ms) <= now_ms)
    }

    #[must_use]
    pub fn refresh_needed_at(&self, now_ms: u64) -> bool {
        self.is_expired_at(now_ms)
    }

    pub fn record_hit(&mut self) {
        self.hit_count = self.hit_count.saturating_add(1);
    }

    pub fn record_miss(&mut self) {
        self.miss_count = self.miss_count.saturating_add(1);
    }

    pub fn record_refresh(&mut self) {
        self.refresh_count = self.refresh_count.saturating_add(1);
    }

    pub fn update(&mut self, jwks: Jwks, now_ms: u64) -> Result<(), SecurityError> {
        jwks.validate()?;
        self.etag.clone_from(&jwks.etag);
        self.jwks = Some(jwks);
        self.cached_at_ms = Some(now_ms);
        self.record_refresh();
        Ok(())
    }

    #[must_use]
    pub fn efficiency(&self) -> f64 {
        let total = self.hit_count.saturating_add(self.miss_count);
        if total == 0 {
            0.0
        } else {
            let hits = u32::try_from(self.hit_count).unwrap_or(u32::MAX);
            let total = u32::try_from(total).unwrap_or(u32::MAX);
            f64::from(hits) / f64::from(total)
        }
    }
}

fn finish_validation(
    mut token: OidcToken,
    mut result: TokenValidationResult,
    finished_at_ms: u64,
) -> TokenValidationResult {
    result.success = result.validation_errors.is_empty();
    token.validation_status = Some(if result.success {
        TokenStatus::Valid
    } else {
        result.error_code.unwrap_or(TokenStatus::InvalidFormat)
    });
    token.validated_at_ms = Some(finished_at_ms);
    token.validated_with_key.clone_from(&result.key_used);
    if result.success {
        result.token = Some(token);
    } else {
        result.error_message = Some(result.validation_errors.join("; "));
    }
    result
}

#[async_trait]
pub trait OidcProvider: Send + Sync {
    async fn discover(&self, issuer: &str) -> Result<OidcProviderMetadata, SecurityError>;
    async fn create_id_token(
        &self,
        request: &OidcIdTokenIssue,
    ) -> Result<OidcIdToken, SecurityError>;
    async fn user_info(
        &self,
        access_token: &OAuth2AccessToken,
    ) -> Result<OidcUserInfo, SecurityError>;
    async fn discovery_document(&self) -> Result<OidcDiscoveryDocument, SecurityError>;
    async fn jwks(&self) -> Result<Jwks, SecurityError>;
    async fn sign_id_token(&self, token: &OidcIdToken) -> Result<String, SecurityError>;
    async fn validate_id_token(
        &self,
        request: &TokenValidationRequest,
    ) -> Result<TokenValidationResult, SecurityError>;
    async fn verify_id_token(&self, jwt_token: &str) -> Result<Option<OidcIdToken>, SecurityError>;
    async fn user_claims(
        &self,
        subject: &str,
        scopes: &BTreeSet<String>,
        requested_claims: Option<&BTreeMap<String, Value>>,
    ) -> Result<BTreeMap<String, Value>, SecurityError>;
    async fn validate_authentication_request(
        &self,
        request: &OidcAuthenticationRequest,
    ) -> Result<bool, SecurityError>;
    async fn issuer(&self) -> Result<String, SecurityError>;
    async fn supports_scope(&self, scope: &str) -> Result<bool, SecurityError>;
    async fn supports_response_type(
        &self,
        response_type: OAuth2ResponseType,
    ) -> Result<bool, SecurityError>;
    async fn supported_claims(&self) -> Result<BTreeSet<String>, SecurityError>;
}

#[must_use]
pub fn create_discovery_url(issuer: &str) -> String {
    format!(
        "{}/.well-known/openid-configuration",
        issuer.trim_end_matches('/')
    )
}

pub fn parse_provider_metadata(value: Value) -> Result<OidcProviderMetadata, SecurityError> {
    let Value::Object(values) = value else {
        return Err(SecurityError::InvalidConfiguration(
            "OIDC provider metadata must be an object".into(),
        ));
    };
    let mut values: BTreeMap<String, Value> = values.into_iter().collect();
    let issuer = take_metadata_string(&mut values, "issuer")?;
    let endpoints = OidcEndpoints {
        authorization_endpoint: take_metadata_string(&mut values, "authorization_endpoint")?,
        token_endpoint: take_metadata_string(&mut values, "token_endpoint")?,
        userinfo_endpoint: take_metadata_string(&mut values, "userinfo_endpoint")?,
        jwks_uri: take_metadata_string(&mut values, "jwks_uri")?,
        issuer: issuer.clone(),
        registration_endpoint: take_optional_metadata_string(&mut values, "registration_endpoint")?,
        introspection_endpoint: take_optional_metadata_string(
            &mut values,
            "introspection_endpoint",
        )?,
        revocation_endpoint: take_optional_metadata_string(&mut values, "revocation_endpoint")?,
        end_session_endpoint: take_optional_metadata_string(&mut values, "end_session_endpoint")?,
        check_session_iframe: take_optional_metadata_string(&mut values, "check_session_iframe")?,
        device_authorization_endpoint: take_optional_metadata_string(
            &mut values,
            "device_authorization_endpoint",
        )?,
    };
    let response_types_supported = take_metadata_set(&mut values, "response_types_supported")?;
    let response_modes_supported = take_metadata_set(&mut values, "response_modes_supported")?;
    let grant_types_supported = take_metadata_set(&mut values, "grant_types_supported")?;
    let subject_types_supported = take_metadata_set(&mut values, "subject_types_supported")?;
    let id_token_signing_alg_values_supported =
        take_metadata_set(&mut values, "id_token_signing_alg_values_supported")?;
    let id_token_encryption_alg_values_supported =
        take_metadata_set(&mut values, "id_token_encryption_alg_values_supported")?;
    let userinfo_signing_alg_values_supported =
        take_metadata_set(&mut values, "userinfo_signing_alg_values_supported")?;
    let userinfo_encryption_alg_values_supported =
        take_metadata_set(&mut values, "userinfo_encryption_alg_values_supported")?;
    let token_endpoint_auth_methods_supported =
        take_metadata_set(&mut values, "token_endpoint_auth_methods_supported")?;
    let scopes_supported = take_metadata_set(&mut values, "scopes_supported")?;
    let claims_supported = take_metadata_set(&mut values, "claims_supported")?;
    let claim_types_supported = take_metadata_set(&mut values, "claim_types_supported")?;
    let code_challenge_methods_supported =
        take_metadata_set(&mut values, "code_challenge_methods_supported")?;
    let capabilities = infer_capabilities(
        &endpoints,
        &response_types_supported,
        &grant_types_supported,
        &id_token_signing_alg_values_supported,
        &code_challenge_methods_supported,
        &values,
    );
    let metadata = OidcProviderMetadata {
        issuer,
        endpoints,
        response_types_supported,
        response_modes_supported,
        grant_types_supported,
        subject_types_supported,
        id_token_signing_alg_values_supported,
        id_token_encryption_alg_values_supported,
        userinfo_signing_alg_values_supported,
        userinfo_encryption_alg_values_supported,
        token_endpoint_auth_methods_supported,
        scopes_supported,
        claims_supported,
        claim_types_supported,
        code_challenge_methods_supported,
        capabilities,
        custom_metadata: values,
    };
    metadata.validate()?;
    Ok(metadata)
}

fn provider_metadata_to_value(metadata: &OidcProviderMetadata) -> Result<Value, SecurityError> {
    let mut values = metadata.custom_metadata.clone();
    values.insert("issuer".into(), metadata.issuer.clone().into());
    insert_endpoint_values(&mut values, &metadata.endpoints);
    for (name, value) in [
        (
            "response_types_supported",
            serde_json::to_value(&metadata.response_types_supported),
        ),
        (
            "response_modes_supported",
            serde_json::to_value(&metadata.response_modes_supported),
        ),
        (
            "grant_types_supported",
            serde_json::to_value(&metadata.grant_types_supported),
        ),
        (
            "subject_types_supported",
            serde_json::to_value(&metadata.subject_types_supported),
        ),
        (
            "id_token_signing_alg_values_supported",
            serde_json::to_value(&metadata.id_token_signing_alg_values_supported),
        ),
        (
            "id_token_encryption_alg_values_supported",
            serde_json::to_value(&metadata.id_token_encryption_alg_values_supported),
        ),
        (
            "userinfo_signing_alg_values_supported",
            serde_json::to_value(&metadata.userinfo_signing_alg_values_supported),
        ),
        (
            "userinfo_encryption_alg_values_supported",
            serde_json::to_value(&metadata.userinfo_encryption_alg_values_supported),
        ),
        (
            "token_endpoint_auth_methods_supported",
            serde_json::to_value(&metadata.token_endpoint_auth_methods_supported),
        ),
        (
            "scopes_supported",
            serde_json::to_value(&metadata.scopes_supported),
        ),
        (
            "claims_supported",
            serde_json::to_value(&metadata.claims_supported),
        ),
        (
            "claim_types_supported",
            serde_json::to_value(&metadata.claim_types_supported),
        ),
        (
            "code_challenge_methods_supported",
            serde_json::to_value(&metadata.code_challenge_methods_supported),
        ),
    ] {
        values.insert(
            name.into(),
            value.map_err(|_| {
                SecurityError::InvalidConfiguration("cannot serialize OIDC metadata".into())
            })?,
        );
    }
    Ok(Value::Object(values.into_iter().collect()))
}

#[must_use]
pub fn generate_nonce() -> String {
    let mut value = [0_u8; 32];
    rand::rng().fill(&mut value);
    URL_SAFE_NO_PAD.encode(value)
}

#[must_use]
pub fn claims_for_scopes(scopes: &BTreeSet<String>) -> BTreeSet<String> {
    let mut claims = BTreeSet::new();
    if scopes.contains("openid") {
        claims.insert("sub".into());
    }
    if scopes.contains("profile") {
        claims.extend(
            [
                "name",
                "family_name",
                "given_name",
                "middle_name",
                "nickname",
                "preferred_username",
                "profile",
                "picture",
                "website",
                "gender",
                "birthdate",
                "zoneinfo",
                "locale",
                "updated_at",
            ]
            .into_iter()
            .map(str::to_owned),
        );
    }
    if scopes.contains("email") {
        claims.extend(["email".into(), "email_verified".into()]);
    }
    if scopes.contains("address") {
        claims.insert("address".into());
    }
    if scopes.contains("phone") {
        claims.extend(["phone_number".into(), "phone_number_verified".into()]);
    }
    claims
}

pub fn parse_jwt_header(encoded: &str) -> Result<JwtHeader, SecurityError> {
    let bytes = decode_json_segment(encoded, "JWT header")?;
    let header: JwtHeader = serde_json::from_slice(&bytes)
        .map_err(|_| SecurityError::Unauthorized("invalid JWT header JSON".into()))?;
    header.validate()?;
    Ok(header)
}

pub fn parse_jwt_payload(encoded: &str) -> Result<JwtPayload, SecurityError> {
    let bytes = decode_json_segment(encoded, "JWT payload")?;
    let mut value: BTreeMap<String, Value> = serde_json::from_slice(&bytes)
        .map_err(|_| SecurityError::Unauthorized("invalid JWT payload JSON".into()))?;
    let issuer = take_string(&mut value, "iss")?;
    let subject = take_string(&mut value, "sub")?;
    let audiences = take_audiences(&mut value)?;
    let expires_at_seconds = take_u64(&mut value, "exp")?;
    let not_before_seconds = take_u64(&mut value, "nbf")?;
    let issued_at_seconds = take_u64(&mut value, "iat")?;
    let token_id = take_string(&mut value, "jti")?;
    let nonce = take_string(&mut value, "nonce")?;
    let scope = take_string(&mut value, "scope")?;
    let groups = take_string_set(&mut value, "groups")?;
    let roles = take_string_set(&mut value, "roles")?;
    let permissions = take_string_set(&mut value, "permissions")?;
    Ok(JwtPayload {
        issuer,
        subject,
        audiences,
        expires_at_seconds,
        not_before_seconds,
        issued_at_seconds,
        token_id,
        nonce,
        scope,
        groups,
        roles,
        permissions,
        claims: value,
    })
}

fn decode_json_segment(encoded: &str, name: &str) -> Result<Vec<u8>, SecurityError> {
    if encoded.len() > 64 * 1024 {
        return Err(SecurityError::InvalidConfiguration(format!(
            "{name} exceeds size limit"
        )));
    }
    URL_SAFE_NO_PAD
        .decode(encoded)
        .map_err(|_| SecurityError::Unauthorized(format!("invalid {name} encoding")))
}

fn take_string(
    values: &mut BTreeMap<String, Value>,
    name: &str,
) -> Result<Option<String>, SecurityError> {
    match values.remove(name) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(value)) => Ok(Some(value)),
        Some(_) => Err(SecurityError::Unauthorized(format!(
            "JWT {name} claim has invalid type"
        ))),
    }
}

fn take_u64(
    values: &mut BTreeMap<String, Value>,
    name: &str,
) -> Result<Option<u64>, SecurityError> {
    match values.remove(name) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::Number(value)) => value.as_u64().map(Some).ok_or_else(|| {
            SecurityError::Unauthorized(format!("JWT {name} claim has invalid value"))
        }),
        Some(_) => Err(SecurityError::Unauthorized(format!(
            "JWT {name} claim has invalid type"
        ))),
    }
}

fn take_audiences(values: &mut BTreeMap<String, Value>) -> Result<BTreeSet<String>, SecurityError> {
    match values.remove("aud") {
        None => Ok(BTreeSet::new()),
        Some(Value::String(value)) => Ok(BTreeSet::from([value])),
        Some(Value::Array(values)) => values
            .into_iter()
            .map(|value| {
                value.as_str().map(str::to_owned).ok_or_else(|| {
                    SecurityError::Unauthorized("JWT aud claim has invalid type".into())
                })
            })
            .collect(),
        Some(_) => Err(SecurityError::Unauthorized(
            "JWT aud claim has invalid type".into(),
        )),
    }
}

fn take_string_set(
    values: &mut BTreeMap<String, Value>,
    name: &str,
) -> Result<BTreeSet<String>, SecurityError> {
    match values.remove(name) {
        None => Ok(BTreeSet::new()),
        Some(Value::Array(values)) => values
            .into_iter()
            .map(|value| {
                value.as_str().map(str::to_owned).ok_or_else(|| {
                    SecurityError::Unauthorized(format!("JWT {name} claim has invalid type"))
                })
            })
            .collect(),
        Some(_) => Err(SecurityError::Unauthorized(format!(
            "JWT {name} claim has invalid type"
        ))),
    }
}

fn take_metadata_string(
    values: &mut BTreeMap<String, Value>,
    name: &str,
) -> Result<String, SecurityError> {
    take_optional_metadata_string(values, name)?.ok_or_else(|| {
        SecurityError::InvalidConfiguration(format!("OIDC metadata is missing {name}"))
    })
}

fn take_optional_metadata_string(
    values: &mut BTreeMap<String, Value>,
    name: &str,
) -> Result<Option<String>, SecurityError> {
    match values.remove(name) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(value)) if !value.trim().is_empty() => Ok(Some(value)),
        Some(_) => Err(SecurityError::InvalidConfiguration(format!(
            "OIDC metadata {name} must be a non-empty string"
        ))),
    }
}

fn take_metadata_set<T>(
    values: &mut BTreeMap<String, Value>,
    name: &str,
) -> Result<BTreeSet<T>, SecurityError>
where
    T: DeserializeOwned + Ord,
{
    match values.remove(name) {
        None | Some(Value::Null) => Ok(BTreeSet::new()),
        Some(value) => serde_json::from_value(value).map_err(|_| {
            SecurityError::InvalidConfiguration(format!("OIDC metadata {name} has invalid values"))
        }),
    }
}

fn infer_capabilities(
    endpoints: &OidcEndpoints,
    responses: &BTreeSet<OAuth2ResponseType>,
    grants: &BTreeSet<OAuth2GrantType>,
    signing_algorithms: &BTreeSet<String>,
    pkce_methods: &BTreeSet<String>,
    custom_metadata: &BTreeMap<String, Value>,
) -> BTreeSet<OidcCapability> {
    let mut capabilities = BTreeSet::from([OidcCapability::Discovery, OidcCapability::Userinfo]);
    for (grant, capability) in [
        (
            OAuth2GrantType::AuthorizationCode,
            OidcCapability::AuthorizationCode,
        ),
        (OAuth2GrantType::Implicit, OidcCapability::Implicit),
        (
            OAuth2GrantType::ClientCredentials,
            OidcCapability::ClientCredentials,
        ),
        (OAuth2GrantType::Password, OidcCapability::Password),
        (OAuth2GrantType::RefreshToken, OidcCapability::RefreshToken),
    ] {
        if grants.contains(&grant) {
            capabilities.insert(capability);
        }
    }
    if responses.iter().any(|response| {
        matches!(
            response,
            OAuth2ResponseType::CodeIdToken
                | OAuth2ResponseType::CodeToken
                | OAuth2ResponseType::CodeTokenIdToken
        )
    }) {
        capabilities.insert(OidcCapability::Hybrid);
    }
    if !pkce_methods.is_empty() {
        capabilities.insert(OidcCapability::Pkce);
    }
    if pkce_methods.contains("S256") {
        capabilities.insert(OidcCapability::PkceS256);
    }
    if !signing_algorithms.is_empty() {
        capabilities.insert(OidcCapability::JwtTokens);
    }
    for (present, capability) in [
        (
            endpoints.registration_endpoint.is_some(),
            OidcCapability::DynamicRegistration,
        ),
        (
            endpoints.introspection_endpoint.is_some(),
            OidcCapability::Introspection,
        ),
        (
            endpoints.revocation_endpoint.is_some(),
            OidcCapability::Revocation,
        ),
        (
            endpoints.check_session_iframe.is_some(),
            OidcCapability::SessionManagement,
        ),
        (
            endpoints.end_session_endpoint.is_some(),
            OidcCapability::SessionManagement,
        ),
        (
            custom_metadata
                .get("frontchannel_logout_supported")
                .and_then(Value::as_bool)
                .unwrap_or(false),
            OidcCapability::FrontChannelLogout,
        ),
        (
            custom_metadata
                .get("backchannel_logout_supported")
                .and_then(Value::as_bool)
                .unwrap_or(false),
            OidcCapability::BackChannelLogout,
        ),
    ] {
        if present {
            capabilities.insert(capability);
        }
    }
    capabilities
}

fn insert_endpoint_values(values: &mut BTreeMap<String, Value>, endpoints: &OidcEndpoints) {
    for (name, value) in [
        ("authorization_endpoint", &endpoints.authorization_endpoint),
        ("token_endpoint", &endpoints.token_endpoint),
        ("userinfo_endpoint", &endpoints.userinfo_endpoint),
        ("jwks_uri", &endpoints.jwks_uri),
    ] {
        values.insert(name.into(), value.clone().into());
    }
    for (name, value) in [
        ("registration_endpoint", &endpoints.registration_endpoint),
        ("introspection_endpoint", &endpoints.introspection_endpoint),
        ("revocation_endpoint", &endpoints.revocation_endpoint),
        ("end_session_endpoint", &endpoints.end_session_endpoint),
        ("check_session_iframe", &endpoints.check_session_iframe),
        (
            "device_authorization_endpoint",
            &endpoints.device_authorization_endpoint,
        ),
    ] {
        if let Some(value) = value {
            values.insert(name.into(), value.clone().into());
        }
    }
}

fn oidc_required_param<'a>(
    params: &'a BTreeMap<String, String>,
    name: &str,
) -> Result<&'a str, SecurityError> {
    params
        .get(name)
        .map(String::as_str)
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| {
            SecurityError::InvalidConfiguration(format!("OIDC request is missing {name}"))
        })
}

fn split_parameter(value: Option<&String>) -> Vec<String> {
    value
        .map_or("", String::as_str)
        .split_whitespace()
        .map(str::to_owned)
        .collect()
}

fn string_set_value(values: &BTreeSet<String>) -> Value {
    Value::Array(values.iter().cloned().map(Value::String).collect())
}

fn audience_value(values: &BTreeSet<String>) -> Value {
    if values.len() == 1 {
        Value::String(values.first().cloned().unwrap_or_default())
    } else {
        string_set_value(values)
    }
}

fn valid_oidc_endpoint(value: &str) -> bool {
    valid_redirect_uri(value)
}

fn supported_signature_algorithm(algorithm: &str) -> bool {
    matches!(
        algorithm,
        "RS256"
            | "RS384"
            | "RS512"
            | "PS256"
            | "PS384"
            | "PS512"
            | "ES256"
            | "ES384"
            | "ES512"
            | "ES256K"
            | "HS256"
            | "HS384"
            | "HS512"
            | "EdDSA"
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Deserialize)]
    struct Fixture {
        schema_version: u32,
        oidc: OidcCase,
        oidc_query: BTreeMap<String, String>,
        discovery_metadata: Value,
        jwt: JwtCase,
        jwks: JwksCase,
    }

    #[derive(Deserialize)]
    struct OidcCase {
        issuer: String,
        discovery_url: String,
        authorization_endpoint: String,
        token_endpoint: String,
        userinfo_endpoint: String,
        jwks_uri: String,
        subject: String,
        audience: String,
        supported_scopes: BTreeSet<String>,
        supported_grants: BTreeSet<OAuth2GrantType>,
        supported_responses: BTreeSet<OAuth2ResponseType>,
        supported_algorithms: BTreeSet<String>,
        scope_claims: BTreeMap<String, BTreeSet<String>>,
    }

    #[derive(Deserialize)]
    struct JwtCase {
        encoded_header: String,
        encoded_payload: String,
        encoded_signature: String,
        kid: String,
        algorithm: String,
        expires_at_seconds: u64,
        valid_at_seconds: u64,
        expired_at_seconds: u64,
    }

    #[derive(Deserialize)]
    struct JwksCase {
        kid: String,
        kty: JwkType,
        #[serde(rename = "use")]
        key_use: JwkUse,
        algorithm: String,
        modulus: String,
        exponent: String,
        cache_ttl_ms: u64,
    }

    fn fixture() -> Fixture {
        let fixture: Fixture = serde_json::from_str(include_str!(
            "../../../contracts/identity-oauth-oidc-behavior.json"
        ))
        .expect("valid OAuth/OIDC behavior fixture");
        assert_eq!(fixture.schema_version, 1);
        fixture
    }

    fn metadata(case: &OidcCase) -> OidcProviderMetadata {
        OidcProviderMetadata {
            issuer: case.issuer.clone(),
            endpoints: OidcEndpoints {
                authorization_endpoint: case.authorization_endpoint.clone(),
                token_endpoint: case.token_endpoint.clone(),
                userinfo_endpoint: case.userinfo_endpoint.clone(),
                jwks_uri: case.jwks_uri.clone(),
                issuer: case.issuer.clone(),
                registration_endpoint: None,
                introspection_endpoint: None,
                revocation_endpoint: None,
                end_session_endpoint: None,
                check_session_iframe: None,
                device_authorization_endpoint: None,
            },
            response_types_supported: case.supported_responses.clone(),
            response_modes_supported: BTreeSet::from([OidcResponseMode::Query]),
            grant_types_supported: case.supported_grants.clone(),
            subject_types_supported: BTreeSet::from(["public".into()]),
            id_token_signing_alg_values_supported: case.supported_algorithms.clone(),
            id_token_encryption_alg_values_supported: BTreeSet::new(),
            userinfo_signing_alg_values_supported: BTreeSet::new(),
            userinfo_encryption_alg_values_supported: BTreeSet::new(),
            token_endpoint_auth_methods_supported: BTreeSet::from(["client_secret_basic".into()]),
            scopes_supported: case.supported_scopes.clone(),
            claims_supported: case.scope_claims.values().flatten().cloned().collect(),
            claim_types_supported: BTreeSet::from(["normal".into()]),
            code_challenge_methods_supported: BTreeSet::from(["S256".into()]),
            capabilities: BTreeSet::from([
                OidcCapability::AuthorizationCode,
                OidcCapability::PkceS256,
                OidcCapability::Discovery,
            ]),
            custom_metadata: BTreeMap::new(),
        }
    }

    fn key(case: &JwksCase) -> Jwk {
        Jwk {
            kid: case.kid.clone(),
            kty: case.kty,
            key_use: Some(case.key_use),
            key_ops: BTreeSet::from(["verify".into()]),
            alg: Some(case.algorithm.clone()),
            n: Some(case.modulus.clone()),
            e: Some(case.exponent.clone()),
            crv: None,
            x: None,
            y: None,
            k: None,
            x5c: Vec::new(),
            x5t: None,
            x5t_s256: None,
            x5u: None,
            additional_properties: BTreeMap::new(),
        }
    }

    #[test]
    fn discovery_metadata_and_claims_match_language_neutral_contract() {
        let fixture = fixture();
        assert_eq!(
            create_discovery_url(&fixture.oidc.issuer),
            fixture.oidc.discovery_url
        );
        let metadata = metadata(&fixture.oidc);
        metadata.validate().unwrap();
        assert!(metadata.supports_pkce());
        assert_eq!(metadata.preferred_signing_algorithm(), Some("ES256"));
        for (scope, expected) in fixture.oidc.scope_claims {
            assert_eq!(claims_for_scopes(&BTreeSet::from([scope])), expected);
        }
    }

    #[test]
    fn flat_discovery_and_authentication_query_preserve_complete_behavior() {
        let fixture = fixture();
        let parsed = parse_provider_metadata(fixture.discovery_metadata).unwrap();
        assert!(parsed.supports_grant_type(OAuth2GrantType::AuthorizationCode));
        assert!(parsed.supports_grant_type(OAuth2GrantType::ClientCredentials));
        assert!(parsed.supports_s256_pkce());
        assert!(parsed.supports_capability(OidcCapability::DynamicRegistration));
        assert!(parsed.supports_capability(OidcCapability::Introspection));
        assert_eq!(
            parsed.custom_metadata.get("vendor_extension"),
            Some(&Value::String("preserved".into()))
        );
        let document = OidcDiscoveryDocument {
            metadata: parsed.clone(),
        };
        let serialized = document.to_value().unwrap();
        let roundtrip = parse_provider_metadata(serialized).unwrap();
        assert_eq!(roundtrip, parsed);

        let request = OidcAuthenticationRequest::from_query_params(&fixture.oidc_query, 1).unwrap();
        assert!(request.requires_id_token());
        assert!(request.has_prompt(OidcPrompt::Login));
        assert!(request.has_prompt(OidcPrompt::Consent));
        assert_eq!(request.max_age_seconds, Some(300));
        assert_eq!(request.ui_locales, ["en", "fr"]);

        let mut configuration = OidcProviderConfiguration {
            provider_name: "fixture".into(),
            issuer_url: fixture.oidc.issuer,
            client_id: fixture.oidc.audience,
            client_secret: Some("secret".into()),
            metadata: None,
            discovery_url: None,
            auto_discovery: true,
            discovery_cache_ttl_ms: 86_400_000,
            redirect_uri: request.redirect_uri,
            post_logout_redirect_uri: None,
            default_scopes: BTreeSet::from(["openid".into(), "profile".into()]),
            require_https: true,
            validate_issuer: true,
            validate_audience: true,
            clock_skew_tolerance_seconds: 300,
            jwks_cache_ttl_ms: 3_600_000,
            metadata_cache_ttl_ms: 86_400_000,
            state_ttl_ms: 600_000,
            nonce_ttl_ms: 600_000,
            last_discovery_attempt_ms: None,
            last_successful_discovery_ms: None,
            discovery_error: None,
        };
        configuration.mark_discovery_success(roundtrip, 10).unwrap();
        assert!(configuration.is_discovered());
        assert!(configuration.supports_flow("authorization_code"));
        assert!(
            configuration
                .recommended_scopes(&BTreeSet::from(["unsupported".into()]))
                .contains("openid")
        );
    }

    #[test]
    fn jwt_and_jwks_parsing_matches_language_neutral_contract() {
        let fixture = fixture();
        let header = parse_jwt_header(&fixture.jwt.encoded_header).unwrap();
        assert_eq!(header.kid.as_deref(), Some(fixture.jwt.kid.as_str()));
        assert_eq!(header.alg, fixture.jwt.algorithm);
        let payload = parse_jwt_payload(&fixture.jwt.encoded_payload).unwrap();
        assert_eq!(
            payload.issuer.as_deref(),
            Some(fixture.oidc.issuer.as_str())
        );
        assert_eq!(
            payload.subject.as_deref(),
            Some(fixture.oidc.subject.as_str())
        );
        assert!(payload.audiences.contains(&fixture.oidc.audience));
        assert_eq!(
            payload.expires_at_seconds,
            Some(fixture.jwt.expires_at_seconds)
        );
        assert!(!payload.is_expired_at(fixture.jwt.valid_at_seconds, 0));
        assert!(payload.is_expired_at(fixture.jwt.expires_at_seconds, 0));
        assert!(payload.is_expired_at(fixture.jwt.expired_at_seconds, 0));
        assert!(payload.has_scope("profile"));

        let jwks = Jwks {
            keys: vec![key(&fixture.jwks)],
            retrieved_at_ms: 1,
            cache_control: None,
            etag: Some("fixture".into()),
        };
        jwks.validate().unwrap();
        assert!(
            jwks.key(&fixture.jwks.kid, &fixture.jwks.algorithm)
                .is_some()
        );
        assert!(jwks.key("unknown", &fixture.jwks.algorithm).is_none());

        let mut inferred = key(&fixture.jwks);
        inferred.alg = None;
        assert!(inferred.supports_algorithm("PS512"));
        assert!(!inferred.supports_algorithm("HS256"));
        let mut ec = inferred;
        ec.kty = JwkType::Ec;
        ec.n = None;
        ec.e = None;
        ec.crv = Some("P-256".into());
        ec.x = Some("x".into());
        ec.y = Some("y".into());
        assert!(ec.supports_algorithm("ES256"));
        assert!(!ec.supports_algorithm("ES384"));
    }

    #[test]
    fn id_token_userinfo_and_claim_access_preserve_behavior() {
        let fixture = fixture();
        let token = OidcIdToken::issue(OidcIdTokenIssue {
            subject: fixture.oidc.subject.clone(),
            issuer: fixture.oidc.issuer.clone(),
            audience: BTreeSet::from([fixture.oidc.audience.clone()]),
            claims: BTreeMap::from([("email".into(), Value::String("alex@example.com".into()))]),
            nonce: Some("nonce-123".into()),
            auth_time_seconds: None,
            now_seconds: 1,
            lifetime_seconds: 3_600,
        });
        token.validate_at(2).unwrap();
        assert_eq!(
            token.claim("sub"),
            Some(Value::String(fixture.oidc.subject))
        );
        assert_eq!(
            token.claim("email"),
            Some(Value::String("alex@example.com".into()))
        );
        assert_eq!(
            token.payload().get("aud"),
            Some(&Value::String(fixture.oidc.audience))
        );
        let user_info = OidcUserInfo::from_map(BTreeMap::from([
            ("sub".into(), Value::String("user-123".into())),
            ("name".into(), Value::String("Alex".into())),
        ]))
        .unwrap();
        assert!(user_info.has_claim("sub"));
        assert!(user_info.has_claim("name"));
        assert_eq!(user_info.to_map().get("sub").unwrap(), "user-123");
    }

    struct SuccessfulVerifier;

    #[async_trait]
    impl JwtSignatureVerifier for SuccessfulVerifier {
        async fn verify(
            &self,
            _algorithm: &str,
            _key: &Jwk,
            _signing_input: &[u8],
            signature: &[u8],
        ) -> Result<bool, SecurityError> {
            Ok(signature == b"signature")
        }
    }

    #[tokio::test]
    async fn token_validation_is_componentized_and_fail_closed() {
        let fixture = fixture();
        let raw = format!(
            "{}.{}.{}",
            fixture.jwt.encoded_header, fixture.jwt.encoded_payload, fixture.jwt.encoded_signature
        );
        let jwks = Jwks {
            keys: vec![key(&fixture.jwks)],
            retrieved_at_ms: 1,
            cache_control: None,
            etag: None,
        };
        let request = TokenValidationRequest {
            raw_token: raw,
            token_type: OidcTokenType::IdToken,
            expected_issuer: Some(fixture.oidc.issuer),
            expected_audiences: BTreeSet::from([fixture.oidc.audience]),
            expected_nonce: Some("nonce-123".into()),
            verify_signature: true,
            verify_expiration: true,
            verify_not_before: true,
            verify_issuer: true,
            verify_audience: true,
            clock_skew_tolerance_seconds: 0,
            jwks: Some(jwks),
            jwks_uri: None,
        };
        let missing = OidcTokenValidator::new(None)
            .validate(&request, fixture.jwt.valid_at_seconds, 1, 2)
            .await;
        assert!(matches!(
            missing,
            Err(SecurityError::ProviderUnavailable(_))
        ));
        let result = OidcTokenValidator::new(Some(Arc::new(SuccessfulVerifier)))
            .validate(&request, fixture.jwt.valid_at_seconds, 1, 2)
            .await
            .unwrap();
        assert!(result.success);
        assert!(result.signature_valid);

        let expired = OidcTokenValidator::new(Some(Arc::new(SuccessfulVerifier)))
            .validate(&request, fixture.jwt.expired_at_seconds, 1, 2)
            .await
            .unwrap();
        assert!(!expired.success);
        assert_eq!(expired.error_code, Some(TokenStatus::Expired));
    }

    #[test]
    fn caches_requests_and_malformed_tokens_fail_closed() {
        let fixture = fixture();
        let mut cache = JwksCache {
            issuer: fixture.oidc.issuer,
            jwks_uri: fixture.oidc.jwks_uri,
            jwks: None,
            cached_at_ms: None,
            cache_ttl_ms: fixture.jwks.cache_ttl_ms,
            etag: None,
            last_modified: None,
            hit_count: 0,
            miss_count: 0,
            refresh_count: 0,
        };
        assert!(cache.is_expired_at(1));
        cache.record_hit();
        cache.record_miss();
        assert!((cache.efficiency() - 0.5).abs() < f64::EPSILON);
        assert!(OidcToken::parse("not-a-jwt", OidcTokenType::IdToken).is_err());
        assert!(parse_jwt_header("e30").is_err());
        let unsupported = URL_SAFE_NO_PAD.encode(br#"{"alg":"unknown"}"#);
        assert!(parse_jwt_header(&unsupported).is_err());
    }
}
