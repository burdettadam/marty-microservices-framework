//! Transport-neutral built-in identity use cases.

use std::collections::{BTreeMap, BTreeSet};

use mmf_security::{AuthenticatedUser, AuthenticationMethod, AuthenticationRequest};
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::ServiceError;
use crate::identity::{
    AuthenticationErrorCode, AuthenticationManager, AuthenticationStatus,
    IdentityAuthenticationResult, IdentityProviders,
};

#[derive(Clone, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(transparent)]
pub struct UserId(String);

impl UserId {
    pub fn new(value: impl Into<String>) -> Result<Self, ServiceError> {
        let value = value.into();
        if value.trim().is_empty() {
            return Err(ServiceError::InvalidConfiguration(
                "UserId cannot be empty".into(),
            ));
        }
        Ok(Self(value))
    }

    #[must_use]
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct Principal {
    pub user_id: UserId,
    pub username: String,
    pub authenticated_at_ms: u64,
    pub expires_at_ms: Option<u64>,
}

impl Principal {
    pub fn validate(&self) -> Result<(), ServiceError> {
        if self.username.trim().is_empty()
            || self
                .expires_at_ms
                .is_some_and(|expiry| expiry < self.authenticated_at_ms)
        {
            return Err(ServiceError::InvalidConfiguration(
                "invalid authenticated principal".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn is_expired_at(&self, now_ms: u64) -> bool {
        self.expires_at_ms.is_some_and(|expiry| now_ms >= expiry)
    }
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct IdentityAuthenticationContext {
    pub client_ip: Option<String>,
    pub user_agent: Option<String>,
    pub session_id: Option<String>,
    pub request_id: Option<String>,
    pub timestamp_ms: Option<u64>,
    #[serde(default)]
    pub additional_context: BTreeMap<String, Value>,
}

impl IdentityAuthenticationContext {
    #[must_use]
    pub fn provider_metadata(&self) -> BTreeMap<String, String> {
        let mut metadata = BTreeMap::new();
        for (key, value) in [
            ("client_ip", self.client_ip.as_deref()),
            ("user_agent", self.user_agent.as_deref()),
            ("session_id", self.session_id.as_deref()),
            ("request_id", self.request_id.as_deref()),
        ] {
            if let Some(value) = value {
                metadata.insert(key.into(), value.into());
            }
        }
        metadata
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct BasicAuthenticationRequest {
    pub username: String,
    #[serde(skip_serializing)]
    pub password: String,
    pub context: Option<IdentityAuthenticationContext>,
}

impl BasicAuthenticationRequest {
    pub fn validate(&self) -> Result<(), ServiceError> {
        if self.username.trim().is_empty() {
            return Err(ServiceError::InvalidConfiguration(
                "Username is required".into(),
            ));
        }
        if self.password.is_empty() {
            return Err(ServiceError::InvalidConfiguration(
                "Password is required".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ChangePasswordRequest {
    pub username: String,
    #[serde(skip_serializing)]
    pub current_password: String,
    #[serde(skip_serializing)]
    pub new_password: String,
    pub context: Option<IdentityAuthenticationContext>,
}

impl ChangePasswordRequest {
    pub fn validate(&self) -> Result<(), ServiceError> {
        if self.username.trim().is_empty() {
            return Err(ServiceError::InvalidConfiguration(
                "Username is required".into(),
            ));
        }
        if self.current_password.is_empty() {
            return Err(ServiceError::InvalidConfiguration(
                "Current password is required".into(),
            ));
        }
        if self.new_password.len() < 8 {
            return Err(ServiceError::InvalidConfiguration(
                "New password must be at least 8 characters long".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct OperationResult {
    pub success: bool,
    pub message: String,
    pub error_code: Option<String>,
    pub value: Option<Value>,
}

impl OperationResult {
    #[must_use]
    pub fn success(message: impl Into<String>, value: Option<Value>) -> Self {
        Self {
            success: true,
            message: message.into(),
            error_code: None,
            value,
        }
    }

    #[must_use]
    pub fn failure(message: impl Into<String>, error_code: impl Into<String>) -> Self {
        Self {
            success: false,
            message: message.into(),
            error_code: Some(error_code.into()),
            value: None,
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ApiKeyAuthenticationRequest {
    #[serde(skip_serializing)]
    pub api_key: String,
    pub context: Option<IdentityAuthenticationContext>,
}

impl ApiKeyAuthenticationRequest {
    pub fn validate(&self) -> Result<(), ServiceError> {
        if self.api_key.is_empty() {
            Err(ServiceError::InvalidConfiguration(
                "API key is required".into(),
            ))
        } else {
            Ok(())
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct CreateApiKeyRequest {
    pub user_id: String,
    pub key_name: Option<String>,
    pub expires_at_ms: Option<u64>,
    #[serde(default)]
    pub permissions: BTreeSet<String>,
    pub context: Option<IdentityAuthenticationContext>,
}

impl CreateApiKeyRequest {
    pub fn validate(&self, now_ms: u64) -> Result<(), ServiceError> {
        if self.user_id.trim().is_empty()
            || self
                .key_name
                .as_deref()
                .is_some_and(|name| name.trim().is_empty())
            || self.expires_at_ms.is_some_and(|expiry| expiry <= now_ms)
        {
            return Err(ServiceError::InvalidConfiguration(
                "invalid API-key creation request".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct TokenAuthenticationRequest {
    #[serde(skip_serializing)]
    pub token: String,
}

impl TokenAuthenticationRequest {
    pub fn validate(&self) -> Result<(), ServiceError> {
        if self.token.is_empty() {
            Err(ServiceError::InvalidConfiguration(
                "Token is required".into(),
            ))
        } else {
            Ok(())
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct TokenValidationResult {
    pub is_valid: bool,
    pub user: Option<AuthenticatedUser>,
    pub error_message: Option<String>,
    pub error_code: Option<AuthenticationErrorCode>,
}

impl TokenValidationResult {
    #[must_use]
    pub fn success(user: AuthenticatedUser) -> Self {
        Self {
            is_valid: true,
            user: Some(user),
            error_message: None,
            error_code: None,
        }
    }

    #[must_use]
    pub fn failure(message: impl Into<String>, code: AuthenticationErrorCode) -> Self {
        Self {
            is_valid: false,
            user: None,
            error_message: Some(message.into()),
            error_code: Some(code),
        }
    }
}

pub struct IdentityUseCases<'a> {
    pub manager: &'a AuthenticationManager,
    pub providers: &'a IdentityProviders,
}

impl IdentityUseCases<'_> {
    pub async fn authenticate_basic(
        &self,
        request: &BasicAuthenticationRequest,
        now_ms: u64,
    ) -> Result<IdentityAuthenticationResult, ServiceError> {
        request.validate()?;
        let provider_request = AuthenticationRequest {
            scheme: "basic".into(),
            credential: format!("{}:{}", request.username, request.password),
            metadata: request.context.as_ref().map_or_else(
                BTreeMap::new,
                IdentityAuthenticationContext::provider_metadata,
            ),
        };
        Ok(self
            .manager
            .authenticate(AuthenticationMethod::Basic, &provider_request, now_ms)
            .await)
    }

    pub async fn change_password(&self, request: &ChangePasswordRequest) -> OperationResult {
        if let Err(error) = request.validate() {
            return OperationResult::failure(error.to_string(), "VALIDATION_ERROR");
        }
        let Some(provider) = &self.providers.password else {
            return OperationResult::failure(
                "password provider is unavailable",
                "PROVIDER_NOT_FOUND",
            );
        };
        match provider
            .change(
                &request.username,
                request.current_password.as_bytes(),
                request.new_password.as_bytes(),
            )
            .await
        {
            Ok(()) => OperationResult::success("Password changed successfully", None),
            Err(error) => OperationResult::failure(error.to_string(), "CHANGE_FAILED"),
        }
    }

    pub async fn authenticate_api_key(
        &self,
        request: &ApiKeyAuthenticationRequest,
        now_ms: u64,
    ) -> Result<IdentityAuthenticationResult, ServiceError> {
        request.validate()?;
        let Some(provider) = &self.providers.api_key else {
            return Ok(IdentityAuthenticationResult::failure(
                AuthenticationStatus::Failed,
                "API-key provider is unavailable",
                AuthenticationErrorCode::ProviderNotFound,
                now_ms,
            ));
        };
        Ok(
            match provider.authenticate(request.api_key.as_bytes()).await {
                Ok(user) => IdentityAuthenticationResult::success(user, now_ms),
                Err(error) => IdentityAuthenticationResult::failure(
                    AuthenticationStatus::InvalidCredentials,
                    error.to_string(),
                    AuthenticationErrorCode::ApiKeyInvalid,
                    now_ms,
                ),
            },
        )
    }

    pub async fn create_api_key(
        &self,
        request: &CreateApiKeyRequest,
        now_ms: u64,
    ) -> OperationResult {
        if let Err(error) = request.validate(now_ms) {
            return OperationResult::failure(error.to_string(), "VALIDATION_ERROR");
        }
        let Some(provider) = &self.providers.api_key else {
            return OperationResult::failure(
                "API-key provider is unavailable",
                "PROVIDER_NOT_FOUND",
            );
        };
        match provider
            .create(
                &request.user_id,
                request.key_name.as_deref(),
                request.expires_at_ms,
                request.permissions.clone(),
            )
            .await
        {
            Ok(value) => OperationResult::success("API key created successfully", Some(value)),
            Err(error) => OperationResult::failure(error.to_string(), "INTERNAL_ERROR"),
        }
    }

    pub async fn revoke_api_key(&self, api_key_id: &str) -> OperationResult {
        if api_key_id.is_empty() {
            return OperationResult::failure("API key is required", "VALIDATION_ERROR");
        }
        let Some(provider) = &self.providers.api_key else {
            return OperationResult::failure(
                "API-key provider is unavailable",
                "PROVIDER_NOT_FOUND",
            );
        };
        match provider.revoke(api_key_id).await {
            Ok(()) => OperationResult::success("API key revoked successfully", None),
            Err(error) => OperationResult::failure(error.to_string(), "KEY_NOT_FOUND"),
        }
    }

    pub async fn authenticate_token(
        &self,
        request: &TokenAuthenticationRequest,
        now_ms: u64,
    ) -> Result<IdentityAuthenticationResult, ServiceError> {
        request.validate()?;
        let result = self.validate_token(request).await;
        Ok(match result.user {
            Some(user) if result.is_valid => IdentityAuthenticationResult::success(user, now_ms),
            _ => IdentityAuthenticationResult::failure(
                AuthenticationStatus::InvalidCredentials,
                result
                    .error_message
                    .unwrap_or_else(|| "token validation failed".into()),
                result
                    .error_code
                    .unwrap_or(AuthenticationErrorCode::TokenInvalid),
                now_ms,
            ),
        })
    }

    pub async fn issue_token(
        &self,
        user: &AuthenticatedUser,
        scopes: &BTreeSet<String>,
    ) -> OperationResult {
        if let Err(error) = user.validate() {
            return OperationResult::failure(error.to_string(), "VALIDATION_ERROR");
        }
        let Some(provider) = &self.providers.token else {
            return OperationResult::failure("token provider is unavailable", "PROVIDER_NOT_FOUND");
        };
        match provider.issue(user, scopes).await {
            Ok(value) => OperationResult::success("Token issued successfully", Some(value)),
            Err(error) => OperationResult::failure(error.to_string(), "TOKEN_ISSUE_FAILED"),
        }
    }

    pub async fn refresh_token(&self, token: &str) -> OperationResult {
        if token.is_empty() {
            return OperationResult::failure("Token is required", "VALIDATION_ERROR");
        }
        let Some(provider) = &self.providers.token else {
            return OperationResult::failure("token provider is unavailable", "PROVIDER_NOT_FOUND");
        };
        match provider.refresh(token).await {
            Ok(value) => OperationResult::success("Token refreshed successfully", Some(value)),
            Err(error) => OperationResult::failure(error.to_string(), "TOKEN_REFRESH_FAILED"),
        }
    }

    pub async fn revoke_token(&self, token: &str) -> OperationResult {
        if token.is_empty() {
            return OperationResult::failure("Token is required", "VALIDATION_ERROR");
        }
        let Some(provider) = &self.providers.token else {
            return OperationResult::failure("token provider is unavailable", "PROVIDER_NOT_FOUND");
        };
        match provider.revoke(token).await {
            Ok(()) => OperationResult::success("Successfully logged out", None),
            Err(error) => OperationResult::failure(error.to_string(), "TOKEN_REVOKE_FAILED"),
        }
    }

    pub async fn validate_token(
        &self,
        request: &TokenAuthenticationRequest,
    ) -> TokenValidationResult {
        if let Err(error) = request.validate() {
            return TokenValidationResult::failure(
                error.to_string(),
                AuthenticationErrorCode::TokenInvalid,
            );
        }
        let Some(provider) = &self.providers.token else {
            return TokenValidationResult::failure(
                "token provider is unavailable",
                AuthenticationErrorCode::ProviderNotFound,
            );
        };
        match provider.validate(&request.token).await {
            Ok(user) => TokenValidationResult::success(user),
            Err(error) => TokenValidationResult::failure(
                format!("Token validation failed: {error}"),
                AuthenticationErrorCode::TokenInvalid,
            ),
        }
    }
}

#[cfg(test)]
mod tests {
    use std::sync::Arc;

    use async_trait::async_trait;
    use mmf_security::{AuthenticationResult as ProviderResult, Authenticator, SecurityError};

    use super::*;
    use crate::identity::{ApiKeyProvider, IdentityTokenProvider, PasswordProvider};

    fn fixture() -> Value {
        serde_json::from_str(include_str!(
            "../../../contracts/identity-service-orchestration-behavior.json"
        ))
        .expect("valid orchestration behavior fixture")
    }

    fn user() -> AuthenticatedUser {
        AuthenticatedUser {
            user_id: "user-123".into(),
            username: Some("alex".into()),
            email: Some("alex@example.com".into()),
            roles: ["issuer".into()].into_iter().collect(),
            permissions: ["credential:issue".into()].into_iter().collect(),
            session_id: None,
            auth_method: Some(AuthenticationMethod::Basic),
            expires_at_ms: Some(10_000),
            created_at_ms: Some(1_000),
            attributes: BTreeMap::new(),
            user_type: None,
            applicant_id: None,
        }
    }

    struct SuccessfulAuthenticator;

    #[async_trait]
    impl Authenticator for SuccessfulAuthenticator {
        async fn authenticate(
            &self,
            _: &AuthenticationRequest,
        ) -> Result<ProviderResult, SecurityError> {
            Ok(ProviderResult {
                success: true,
                user: Some(user()),
                error: None,
                error_code: None,
                metadata: BTreeMap::new(),
            })
        }
    }

    struct TestPassword;
    #[async_trait]
    impl PasswordProvider for TestPassword {
        async fn verify(&self, _: &str, _: &[u8]) -> Result<bool, ServiceError> {
            Ok(true)
        }
        async fn change(&self, _: &str, _: &[u8], _: &[u8]) -> Result<(), ServiceError> {
            Ok(())
        }
    }

    struct TestApiKey;
    #[async_trait]
    impl ApiKeyProvider for TestApiKey {
        async fn authenticate(&self, _: &[u8]) -> Result<AuthenticatedUser, ServiceError> {
            Ok(user())
        }
        async fn create(
            &self,
            _: &str,
            _: Option<&str>,
            _: Option<u64>,
            _: BTreeSet<String>,
        ) -> Result<Value, ServiceError> {
            Ok(Value::String("mmf_new_key".into()))
        }
        async fn revoke(&self, _: &str) -> Result<(), ServiceError> {
            Ok(())
        }
    }

    struct TestToken;
    #[async_trait]
    impl IdentityTokenProvider for TestToken {
        async fn issue(
            &self,
            _: &AuthenticatedUser,
            _: &BTreeSet<String>,
        ) -> Result<Value, ServiceError> {
            Ok(Value::Null)
        }
        async fn validate(&self, _: &str) -> Result<AuthenticatedUser, ServiceError> {
            Ok(user())
        }
        async fn refresh(&self, _: &str) -> Result<Value, ServiceError> {
            Ok(Value::Null)
        }
        async fn revoke(&self, _: &str) -> Result<(), ServiceError> {
            Ok(())
        }
    }

    fn providers() -> IdentityProviders {
        IdentityProviders {
            token: Some(Arc::new(TestToken)),
            password: Some(Arc::new(TestPassword)),
            api_key: Some(Arc::new(TestApiKey)),
            mutual_tls: None,
            mfa: None,
            sessions: None,
            federated: BTreeMap::new(),
        }
    }

    #[tokio::test]
    async fn language_neutral_use_cases_preserve_behavior_without_serializing_secrets() {
        let fixture = fixture();
        assert_eq!(fixture["schema_version"], 1);
        let manager = AuthenticationManager::default();
        manager
            .register(
                AuthenticationMethod::Basic,
                Arc::new(SuccessfulAuthenticator),
            )
            .await;
        let providers = providers();
        let use_cases = IdentityUseCases {
            manager: &manager,
            providers: &providers,
        };
        let basic = BasicAuthenticationRequest {
            username: fixture["requests"]["username"]
                .as_str()
                .expect("username")
                .into(),
            password: fixture["requests"]["password"]
                .as_str()
                .expect("password")
                .into(),
            context: None,
        };
        assert!(
            use_cases
                .authenticate_basic(&basic, 1_000)
                .await
                .expect("basic")
                .is_successful()
        );
        assert!(
            !serde_json::to_string(&basic)
                .expect("serialize")
                .contains(fixture["requests"]["password"].as_str().expect("password"))
        );
        let change = ChangePasswordRequest {
            username: fixture["requests"]["username"]
                .as_str()
                .expect("username")
                .into(),
            current_password: fixture["requests"]["password"]
                .as_str()
                .expect("password")
                .into(),
            new_password: fixture["requests"]["new_password"]
                .as_str()
                .expect("new password")
                .into(),
            context: None,
        };
        assert!(use_cases.change_password(&change).await.success);
        let api_result = use_cases
            .authenticate_api_key(
                &ApiKeyAuthenticationRequest {
                    api_key: fixture["requests"]["api_key"]
                        .as_str()
                        .expect("API key")
                        .into(),
                    context: None,
                },
                1_000,
            )
            .await
            .expect("API key");
        assert!(api_result.is_successful());
        assert!(
            use_cases
                .validate_token(&TokenAuthenticationRequest {
                    token: fixture["requests"]["token"].as_str().expect("token").into()
                })
                .await
                .is_valid
        );
    }

    #[test]
    fn principal_and_requests_fail_closed_at_boundaries() {
        let fixture = fixture();
        let principal = Principal {
            user_id: UserId::new(fixture["user"]["user_id"].as_str().expect("user ID"))
                .expect("user ID"),
            username: fixture["user"]["username"]
                .as_str()
                .expect("username")
                .into(),
            authenticated_at_ms: fixture["principal"]["authenticated_at_ms"]
                .as_u64()
                .expect("authenticated at"),
            expires_at_ms: Some(
                fixture["principal"]["expires_at_ms"]
                    .as_u64()
                    .expect("expires at"),
            ),
        };
        assert!(
            !principal.is_expired_at(
                fixture["principal"]["active_at_ms"]
                    .as_u64()
                    .expect("active at")
            )
        );
        assert!(
            principal.is_expired_at(
                fixture["principal"]["expired_at_ms"]
                    .as_u64()
                    .expect("expired at")
            )
        );
        assert!(UserId::new("").is_err());
        assert!(
            BasicAuthenticationRequest {
                username: String::new(),
                password: "secret".into(),
                context: None
            }
            .validate()
            .is_err()
        );
        assert!(
            TokenAuthenticationRequest {
                token: String::new()
            }
            .validate()
            .is_err()
        );
    }
}
