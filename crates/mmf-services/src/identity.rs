use std::collections::{BTreeMap, BTreeSet};
use std::sync::Arc;

use async_trait::async_trait;
use mmf_security::{
    AuthenticatedUser, AuthenticationMethod, AuthenticationRequest, Authenticator, MfaProvider,
    SessionStore,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::sync::RwLock;
use uuid::Uuid;

use crate::ServiceError;

pub use mmf_security::mfa;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AuthenticationStatus {
    Success,
    Failed,
    Pending,
    Expired,
    Locked,
    InvalidCredentials,
    AccountDisabled,
    RequiresMfa,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum AuthenticationErrorCode {
    MissingCredentials,
    InvalidUsername,
    InvalidPassword,
    AccountLocked,
    AccountDisabled,
    AccountExpired,
    PasswordExpired,
    TooManyAttempts,
    TokenExpired,
    TokenInvalid,
    MfaRequired,
    MfaInvalid,
    MethodNotSupported,
    ProviderNotFound,
    InternalError,
    ServiceUnavailable,
}

impl AuthenticationErrorCode {
    #[must_use]
    fn from_provider_code(code: Option<&str>) -> Self {
        match code {
            Some("MISSING_CREDENTIALS" | "NO_CREDENTIALS") => Self::MissingCredentials,
            Some("INVALID_USERNAME" | "USER_NOT_FOUND") => Self::InvalidUsername,
            Some("INVALID_PASSWORD") => Self::InvalidPassword,
            Some("ACCOUNT_LOCKED") => Self::AccountLocked,
            Some("ACCOUNT_DISABLED") => Self::AccountDisabled,
            Some("ACCOUNT_EXPIRED") => Self::AccountExpired,
            Some("PASSWORD_EXPIRED") => Self::PasswordExpired,
            Some("TOO_MANY_ATTEMPTS") => Self::TooManyAttempts,
            Some("TOKEN_EXPIRED") => Self::TokenExpired,
            Some("MFA_REQUIRED") => Self::MfaRequired,
            Some("MFA_INVALID") => Self::MfaInvalid,
            Some("METHOD_NOT_SUPPORTED" | "UNKNOWN_AUTH_METHOD") => Self::MethodNotSupported,
            Some("PROVIDER_NOT_FOUND") => Self::ProviderNotFound,
            Some("SERVICE_UNAVAILABLE") => Self::ServiceUnavailable,
            Some("INTERNAL_ERROR") => Self::InternalError,
            _ => Self::TokenInvalid,
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct IdentityAuthenticationResult {
    pub status: AuthenticationStatus,
    pub authenticated_user: Option<AuthenticatedUser>,
    pub error_message: Option<String>,
    pub error_code: Option<AuthenticationErrorCode>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
    pub attempted_at_ms: u64,
}

impl IdentityAuthenticationResult {
    pub fn validate(&self) -> Result<(), ServiceError> {
        match self.status {
            AuthenticationStatus::Success => {
                let user = self.authenticated_user.as_ref().ok_or_else(|| {
                    ServiceError::InvalidConfiguration(
                        "successful authentication requires a user".into(),
                    )
                })?;
                user.validate()
                    .map_err(|error| ServiceError::InvalidConfiguration(error.to_string()))?;
                if self.error_message.is_some() || self.error_code.is_some() {
                    return Err(ServiceError::InvalidConfiguration(
                        "successful authentication cannot include an error".into(),
                    ));
                }
            }
            AuthenticationStatus::Failed
            | AuthenticationStatus::Expired
            | AuthenticationStatus::Locked
            | AuthenticationStatus::InvalidCredentials
            | AuthenticationStatus::AccountDisabled => {
                if self.authenticated_user.is_some()
                    || self.error_message.as_deref().is_none_or(str::is_empty)
                    || self.error_code.is_none()
                {
                    return Err(ServiceError::InvalidConfiguration(
                        "failed authentication requires an error and no user".into(),
                    ));
                }
            }
            AuthenticationStatus::RequiresMfa => {
                if self.error_code != Some(AuthenticationErrorCode::MfaRequired) {
                    return Err(ServiceError::InvalidConfiguration(
                        "MFA result requires MFA_REQUIRED".into(),
                    ));
                }
            }
            AuthenticationStatus::Pending => {}
        }
        Ok(())
    }

    #[must_use]
    pub fn success(user: AuthenticatedUser, attempted_at_ms: u64) -> Self {
        Self {
            status: AuthenticationStatus::Success,
            authenticated_user: Some(user),
            error_message: None,
            error_code: None,
            metadata: BTreeMap::new(),
            attempted_at_ms,
        }
    }

    #[must_use]
    pub fn failure(
        status: AuthenticationStatus,
        message: impl Into<String>,
        code: AuthenticationErrorCode,
        attempted_at_ms: u64,
    ) -> Self {
        Self {
            status,
            authenticated_user: None,
            error_message: Some(message.into()),
            error_code: Some(code),
            metadata: BTreeMap::new(),
            attempted_at_ms,
        }
    }

    #[must_use]
    pub const fn is_successful(&self) -> bool {
        matches!(self.status, AuthenticationStatus::Success)
    }

    #[must_use]
    pub const fn failed(&self) -> bool {
        matches!(
            self.status,
            AuthenticationStatus::Failed
                | AuthenticationStatus::Expired
                | AuthenticationStatus::Locked
                | AuthenticationStatus::InvalidCredentials
                | AuthenticationStatus::AccountDisabled
        )
    }

    #[must_use]
    pub const fn requires_action(&self) -> bool {
        matches!(
            self.status,
            AuthenticationStatus::Pending | AuthenticationStatus::RequiresMfa
        )
    }
}

#[derive(Default)]
pub struct AuthenticationManager {
    providers: RwLock<BTreeMap<AuthenticationMethod, Arc<dyn Authenticator>>>,
}

impl AuthenticationManager {
    pub async fn register(&self, method: AuthenticationMethod, provider: Arc<dyn Authenticator>) {
        self.providers.write().await.insert(method, provider);
    }

    pub async fn unregister(&self, method: AuthenticationMethod) -> bool {
        self.providers.write().await.remove(&method).is_some()
    }

    pub async fn supported_methods(&self) -> BTreeSet<AuthenticationMethod> {
        self.providers.read().await.keys().copied().collect()
    }

    pub async fn authenticate(
        &self,
        method: AuthenticationMethod,
        request: &AuthenticationRequest,
        now_ms: u64,
    ) -> IdentityAuthenticationResult {
        let provider = self.providers.read().await.get(&method).cloned();
        let Some(provider) = provider else {
            return IdentityAuthenticationResult::failure(
                AuthenticationStatus::Failed,
                format!("authentication method {method:?} is not supported"),
                AuthenticationErrorCode::MethodNotSupported,
                now_ms,
            );
        };
        match provider.authenticate(request).await {
            Ok(result) if result.success => {
                if let Some(user) = result.user {
                    IdentityAuthenticationResult::success(user, now_ms)
                } else {
                    IdentityAuthenticationResult::failure(
                        AuthenticationStatus::Failed,
                        "provider returned success without a user",
                        AuthenticationErrorCode::InternalError,
                        now_ms,
                    )
                }
            }
            Ok(result) => {
                let code =
                    AuthenticationErrorCode::from_provider_code(result.error_code.as_deref());
                IdentityAuthenticationResult::failure(
                    AuthenticationStatus::InvalidCredentials,
                    result
                        .error
                        .unwrap_or_else(|| "authentication failed".into()),
                    code,
                    now_ms,
                )
            }
            Err(_) => IdentityAuthenticationResult::failure(
                AuthenticationStatus::Failed,
                "authentication service unavailable",
                AuthenticationErrorCode::ServiceUnavailable,
                now_ms,
            ),
        }
    }

    pub async fn try_methods(
        &self,
        requests: &[(AuthenticationMethod, AuthenticationRequest)],
        now_ms: u64,
    ) -> IdentityAuthenticationResult {
        let mut last = None;
        for (method, request) in requests {
            let result = self.authenticate(*method, request, now_ms).await;
            if result.is_successful() {
                return result;
            }
            last = Some(result);
        }
        last.unwrap_or_else(|| {
            IdentityAuthenticationResult::failure(
                AuthenticationStatus::Failed,
                "no credentials provided",
                AuthenticationErrorCode::MissingCredentials,
                now_ms,
            )
        })
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum OAuth2GrantType {
    AuthorizationCode,
    RefreshToken,
    ClientCredentials,
    DeviceCode,
    TokenExchange,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct OAuth2Client {
    pub client_id: String,
    pub client_secret_reference: Option<String>,
    #[serde(default)]
    pub redirect_uris: BTreeSet<String>,
    #[serde(default)]
    pub grant_types: BTreeSet<OAuth2GrantType>,
    #[serde(default)]
    pub scopes: BTreeSet<String>,
    pub confidential: bool,
    pub enabled: bool,
}

impl OAuth2Client {
    pub fn validate(&self) -> Result<(), ServiceError> {
        if self.client_id.trim().is_empty() {
            return Err(ServiceError::InvalidConfiguration(
                "OAuth2 client id is required".into(),
            ));
        }
        if self
            .grant_types
            .contains(&OAuth2GrantType::AuthorizationCode)
            && self.redirect_uris.is_empty()
        {
            return Err(ServiceError::InvalidConfiguration(
                "authorization-code clients require a redirect URI".into(),
            ));
        }
        if self.confidential
            && self
                .client_secret_reference
                .as_deref()
                .is_none_or(str::is_empty)
        {
            return Err(ServiceError::ProviderUnavailable(
                "confidential OAuth2 client secret reference is required".into(),
            ));
        }
        if self
            .redirect_uris
            .iter()
            .any(|uri| !uri.starts_with("https://") && !uri.starts_with("http://localhost"))
        {
            return Err(ServiceError::InvalidConfiguration(
                "OAuth2 redirect URIs require HTTPS except localhost".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct AuthorizationCode {
    pub code_id: String,
    pub client_id: String,
    pub user_id: String,
    pub redirect_uri: String,
    pub scopes: BTreeSet<String>,
    pub code_challenge: Option<String>,
    pub created_at_ms: u64,
    pub expires_at_ms: u64,
    pub consumed_at_ms: Option<u64>,
}

impl AuthorizationCode {
    #[must_use]
    pub fn new(
        client_id: impl Into<String>,
        user_id: impl Into<String>,
        redirect_uri: impl Into<String>,
        scopes: BTreeSet<String>,
        code_challenge: Option<String>,
        now_ms: u64,
        lifetime_ms: u64,
    ) -> Self {
        Self {
            code_id: Uuid::new_v4().to_string(),
            client_id: client_id.into(),
            user_id: user_id.into(),
            redirect_uri: redirect_uri.into(),
            scopes,
            code_challenge,
            created_at_ms: now_ms,
            expires_at_ms: now_ms.saturating_add(lifetime_ms),
            consumed_at_ms: None,
        }
    }

    pub fn consume(&mut self, now_ms: u64) -> Result<(), ServiceError> {
        if self.consumed_at_ms.is_some() {
            return Err(ServiceError::Conflict(
                "authorization code already consumed".into(),
            ));
        }
        if now_ms > self.expires_at_ms {
            return Err(ServiceError::Unauthorized(
                "authorization code expired".into(),
            ));
        }
        self.consumed_at_ms = Some(now_ms);
        Ok(())
    }
}

#[async_trait]
pub trait IdentityTokenProvider: Send + Sync {
    async fn issue(
        &self,
        user: &AuthenticatedUser,
        scopes: &BTreeSet<String>,
    ) -> Result<Value, ServiceError>;
    async fn validate(&self, token: &str) -> Result<AuthenticatedUser, ServiceError>;
    async fn refresh(&self, refresh_token: &str) -> Result<Value, ServiceError>;
    async fn revoke(&self, token: &str) -> Result<(), ServiceError>;
}

#[async_trait]
pub trait PasswordProvider: Send + Sync {
    async fn verify(&self, user_id: &str, password: &[u8]) -> Result<bool, ServiceError>;
    async fn change(
        &self,
        user_id: &str,
        current: &[u8],
        replacement: &[u8],
    ) -> Result<(), ServiceError>;
}

#[async_trait]
pub trait ApiKeyProvider: Send + Sync {
    async fn authenticate(&self, api_key: &[u8]) -> Result<AuthenticatedUser, ServiceError>;
    async fn create(&self, user_id: &str, scopes: BTreeSet<String>) -> Result<Value, ServiceError>;
    async fn revoke(&self, key_id: &str) -> Result<(), ServiceError>;
}

#[async_trait]
pub trait MutualTlsProvider: Send + Sync {
    async fn authenticate_certificate(
        &self,
        certificate_chain_der: &[Vec<u8>],
    ) -> Result<AuthenticatedUser, ServiceError>;
}

pub struct IdentityProviders {
    pub token: Option<Arc<dyn IdentityTokenProvider>>,
    pub password: Option<Arc<dyn PasswordProvider>>,
    pub api_key: Option<Arc<dyn ApiKeyProvider>>,
    pub mutual_tls: Option<Arc<dyn MutualTlsProvider>>,
    pub mfa: Option<Arc<dyn MfaProvider>>,
    pub sessions: Option<Arc<dyn SessionStore>>,
}

impl IdentityProviders {
    pub fn validate(&self, required: &BTreeSet<AuthenticationMethod>) -> Result<(), ServiceError> {
        let mut missing = Vec::new();
        for method in required {
            let available = match method {
                AuthenticationMethod::Jwt
                | AuthenticationMethod::OAuth2
                | AuthenticationMethod::Oidc => self.token.is_some(),
                AuthenticationMethod::ApiKey => self.api_key.is_some(),
                AuthenticationMethod::Basic => self.password.is_some(),
                AuthenticationMethod::MutualTls | AuthenticationMethod::ServiceIdentity => {
                    self.mutual_tls.is_some()
                }
                AuthenticationMethod::Session => self.sessions.is_some(),
            };
            if !available {
                missing.push(format!("{method:?}"));
            }
        }
        if missing.is_empty() {
            Ok(())
        } else {
            Err(ServiceError::ProviderUnavailable(missing.join(", ")))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use mmf_security::{AuthenticationResult as SecurityAuthenticationResult, SecurityError};

    #[derive(Deserialize)]
    struct Fixture {
        schema_version: u32,
        user: UserCase,
        results: ResultCase,
        oauth_client: OAuthClientCase,
        authorization_code: AuthorizationCodeCase,
    }

    #[derive(Deserialize)]
    struct UserCase {
        user_id: String,
        username: String,
        email: String,
        roles: BTreeSet<String>,
        permissions: BTreeSet<String>,
    }

    #[derive(Deserialize)]
    struct ResultCase {
        success_status: AuthenticationStatus,
        failure_status: AuthenticationStatus,
        failure_message: String,
        failure_code: AuthenticationErrorCode,
        mfa_status: AuthenticationStatus,
        mfa_code: AuthenticationErrorCode,
    }

    #[derive(Deserialize)]
    struct OAuthClientCase {
        client_id: String,
        secret_reference: String,
        redirect_uris: BTreeSet<String>,
        grant_types: BTreeSet<OAuth2GrantType>,
        scopes: BTreeSet<String>,
        confidential: bool,
    }

    #[derive(Deserialize)]
    #[allow(clippy::struct_field_names)]
    struct AuthorizationCodeCase {
        created_at_ms: u64,
        lifetime_ms: u64,
        consume_at_ms: u64,
        expired_at_ms: u64,
    }

    fn fixture() -> Fixture {
        serde_json::from_str(include_str!(
            "../../../contracts/identity-service-behavior.json"
        ))
        .expect("valid identity behavior fixture")
    }

    fn user(case: &UserCase) -> AuthenticatedUser {
        AuthenticatedUser {
            user_id: case.user_id.clone(),
            username: Some(case.username.clone()),
            email: Some(case.email.clone()),
            roles: case.roles.clone(),
            permissions: case.permissions.clone(),
            session_id: None,
            auth_method: Some(AuthenticationMethod::Jwt),
            expires_at_ms: None,
            attributes: BTreeMap::new(),
            user_type: None,
            applicant_id: None,
        }
    }

    #[test]
    fn language_neutral_authentication_result_contract() {
        let fixture = fixture();
        assert_eq!(fixture.schema_version, 1);
        let success = IdentityAuthenticationResult::success(user(&fixture.user), 1);
        assert_eq!(success.status, fixture.results.success_status);
        assert!(success.is_successful());
        assert!(!success.failed());
        success.validate().expect("valid success");

        let failure = IdentityAuthenticationResult::failure(
            fixture.results.failure_status,
            fixture.results.failure_message,
            fixture.results.failure_code,
            1,
        );
        assert!(failure.failed());
        failure.validate().expect("valid failure");

        let mfa = IdentityAuthenticationResult {
            status: fixture.results.mfa_status,
            authenticated_user: None,
            error_message: Some("Multi-factor authentication required".into()),
            error_code: Some(fixture.results.mfa_code),
            metadata: BTreeMap::new(),
            attempted_at_ms: 1,
        };
        assert!(mfa.requires_action());
        mfa.validate().expect("valid MFA result");
    }

    #[test]
    fn invalid_authentication_results_fail_closed() {
        let missing_user = IdentityAuthenticationResult {
            status: AuthenticationStatus::Success,
            authenticated_user: None,
            error_message: None,
            error_code: None,
            metadata: BTreeMap::new(),
            attempted_at_ms: 0,
        };
        assert!(missing_user.validate().is_err());
        let missing_error = IdentityAuthenticationResult {
            status: AuthenticationStatus::Failed,
            authenticated_user: None,
            error_message: None,
            error_code: None,
            metadata: BTreeMap::new(),
            attempted_at_ms: 0,
        };
        assert!(missing_error.validate().is_err());
    }

    #[test]
    fn language_neutral_oauth_client_contract() {
        let case = fixture().oauth_client;
        let client = OAuth2Client {
            client_id: case.client_id,
            client_secret_reference: Some(case.secret_reference),
            redirect_uris: case.redirect_uris.clone(),
            grant_types: case.grant_types,
            scopes: case.scopes.clone(),
            confidential: case.confidential,
            enabled: true,
        };
        client.validate().expect("valid client");
        assert!(
            client
                .redirect_uris
                .contains("https://client.example/callback")
        );
        assert!(
            client
                .scopes
                .is_superset(&BTreeSet::from(["openid".into(), "email".into()]))
        );
        assert!(
            !client
                .redirect_uris
                .contains("https://attacker.example/callback")
        );
    }

    #[test]
    fn machine_clients_do_not_require_browser_redirects() {
        let client = OAuth2Client {
            client_id: "machine-client".into(),
            client_secret_reference: Some("secret://identity/machine-client".into()),
            redirect_uris: BTreeSet::new(),
            grant_types: BTreeSet::from([OAuth2GrantType::ClientCredentials]),
            scopes: BTreeSet::from(["service:read".into()]),
            confidential: true,
            enabled: true,
        };
        client.validate().expect("valid machine client");

        let browser_client = OAuth2Client {
            grant_types: BTreeSet::from([OAuth2GrantType::AuthorizationCode]),
            ..client
        };
        assert!(matches!(
            browser_client.validate(),
            Err(ServiceError::InvalidConfiguration(_))
        ));
    }

    #[test]
    fn authorization_code_is_expiring_and_one_time() {
        let case = fixture().authorization_code;
        let mut code = AuthorizationCode::new(
            "client",
            "user",
            "https://client.example/callback",
            BTreeSet::from(["openid".into()]),
            Some("challenge".into()),
            case.created_at_ms,
            case.lifetime_ms,
        );
        code.consume(case.consume_at_ms).expect("first use");
        assert!(matches!(
            code.consume(case.consume_at_ms),
            Err(ServiceError::Conflict(_))
        ));

        let mut expired = AuthorizationCode::new(
            "client",
            "user",
            "https://client.example/callback",
            BTreeSet::new(),
            None,
            case.created_at_ms,
            case.lifetime_ms,
        );
        assert!(matches!(
            expired.consume(case.expired_at_ms),
            Err(ServiceError::Unauthorized(_))
        ));
    }

    struct SuccessfulAuthenticator(AuthenticatedUser);

    struct FailedAuthenticator;

    #[async_trait]
    impl Authenticator for SuccessfulAuthenticator {
        async fn authenticate(
            &self,
            _request: &AuthenticationRequest,
        ) -> Result<SecurityAuthenticationResult, SecurityError> {
            Ok(SecurityAuthenticationResult {
                success: true,
                user: Some(self.0.clone()),
                error: None,
                error_code: None,
                metadata: BTreeMap::new(),
            })
        }
    }

    #[async_trait]
    impl Authenticator for FailedAuthenticator {
        async fn authenticate(
            &self,
            _request: &AuthenticationRequest,
        ) -> Result<SecurityAuthenticationResult, SecurityError> {
            Ok(SecurityAuthenticationResult {
                success: false,
                user: None,
                error: Some("password rejected".into()),
                error_code: Some("INVALID_PASSWORD".into()),
                metadata: BTreeMap::new(),
            })
        }
    }

    #[tokio::test]
    async fn manager_routes_to_native_providers_and_missing_methods_fail_closed() {
        let fixture = fixture();
        let manager = AuthenticationManager::default();
        let request = AuthenticationRequest {
            scheme: "Bearer".into(),
            credential: "opaque-to-orchestrator".into(),
            metadata: BTreeMap::new(),
        };
        let missing = manager
            .authenticate(AuthenticationMethod::Jwt, &request, 1)
            .await;
        assert_eq!(
            missing.error_code,
            Some(AuthenticationErrorCode::MethodNotSupported)
        );
        manager
            .register(
                AuthenticationMethod::Jwt,
                Arc::new(SuccessfulAuthenticator(user(&fixture.user))),
            )
            .await;
        let success = manager
            .authenticate(AuthenticationMethod::Jwt, &request, 2)
            .await;
        assert!(success.is_successful());

        manager
            .register(AuthenticationMethod::Basic, Arc::new(FailedAuthenticator))
            .await;
        let failure = manager
            .authenticate(AuthenticationMethod::Basic, &request, 3)
            .await;
        assert_eq!(
            failure.error_code,
            Some(AuthenticationErrorCode::InvalidPassword)
        );
    }

    #[test]
    fn required_provider_composition_fails_closed() {
        let providers = IdentityProviders {
            token: None,
            password: None,
            api_key: None,
            mutual_tls: None,
            mfa: None,
            sessions: None,
        };
        assert!(matches!(
            providers.validate(&BTreeSet::from([
                AuthenticationMethod::Jwt,
                AuthenticationMethod::MutualTls
            ])),
            Err(ServiceError::ProviderUnavailable(_))
        ));
    }
}
