//! Axum transport and reusable authorization policy for the built-in identity service.

use std::collections::{BTreeMap, BTreeSet};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use async_trait::async_trait;
use axum::body::Body;
use axum::extract::{Extension, Request, State};
use axum::http::{HeaderMap, StatusCode};
use axum::middleware::{self, Next};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use mmf_security::AuthenticatedUser;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

use crate::ServiceError;
use crate::identity::{AuthenticationManager, IdentityProviders};
use crate::identity_usecases::{
    BasicAuthenticationRequest, ChangePasswordRequest, CreateApiKeyRequest, IdentityUseCases,
    TokenAuthenticationRequest,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PathAccess {
    Public,
    Optional,
    Required,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct IdentityHttpPolicy {
    #[serde(default)]
    pub public_paths: BTreeSet<String>,
    #[serde(default)]
    pub optional_paths: BTreeSet<String>,
    #[serde(default)]
    pub match_path_prefixes: bool,
}

impl Default for IdentityHttpPolicy {
    fn default() -> Self {
        Self {
            public_paths: BTreeSet::from([
                "/health".into(),
                "/plugins".into(),
                "/authenticate".into(),
                "/auth/login".into(),
                "/auth/validate".into(),
                "/auth/jwt/authenticate".into(),
                "/auth/jwt/validate".into(),
                "/auth/jwt/health".into(),
            ]),
            optional_paths: BTreeSet::new(),
            match_path_prefixes: false,
        }
    }
}

impl IdentityHttpPolicy {
    fn path_matches(&self, configured: &str, actual: &str) -> bool {
        actual == configured
            || (self.match_path_prefixes
                && actual
                    .strip_prefix(configured)
                    .is_some_and(|suffix| suffix.starts_with('/')))
    }

    #[must_use]
    pub fn access_for(&self, path: &str) -> PathAccess {
        if self
            .public_paths
            .iter()
            .any(|configured| self.path_matches(configured, path))
        {
            PathAccess::Public
        } else if self
            .optional_paths
            .iter()
            .any(|configured| self.path_matches(configured, path))
        {
            PathAccess::Optional
        } else {
            PathAccess::Required
        }
    }

    pub fn bearer_token<'a>(&self, headers: &'a HeaderMap) -> Result<&'a str, IdentityHttpError> {
        let value = headers
            .get(axum::http::header::AUTHORIZATION)
            .ok_or_else(|| {
                IdentityHttpError::unauthorized(
                    "AUTHORIZATION_REQUIRED",
                    "Authorization header required",
                )
            })?
            .to_str()
            .map_err(|_| {
                IdentityHttpError::unauthorized(
                    "AUTHORIZATION_INVALID",
                    "Invalid authorization header format",
                )
            })?;
        let mut pieces = value.split_whitespace();
        let scheme = pieces.next().unwrap_or_default();
        let token = pieces.next().unwrap_or_default();
        if !scheme.eq_ignore_ascii_case("bearer") || token.is_empty() || pieces.next().is_some() {
            return Err(IdentityHttpError::unauthorized(
                "AUTHORIZATION_INVALID",
                "Invalid authorization header format",
            ));
        }
        Ok(token)
    }

    pub fn require_role(
        &self,
        user: &AuthenticatedUser,
        role: &str,
    ) -> Result<(), IdentityHttpError> {
        if user.has_role(role) {
            Ok(())
        } else {
            Err(IdentityHttpError::forbidden(
                "ROLE_REQUIRED",
                "Required role is missing",
            ))
        }
    }

    pub fn require_permission(
        &self,
        user: &AuthenticatedUser,
        permission: &str,
    ) -> Result<(), IdentityHttpError> {
        if user.is_administrator() || user.has_permission("*") || user.has_permission(permission) {
            Ok(())
        } else {
            Err(IdentityHttpError::forbidden(
                "PERMISSION_REQUIRED",
                "Required permission is missing",
            ))
        }
    }
}

#[derive(Clone)]
pub struct IdentityHttpState {
    pub manager: Arc<AuthenticationManager>,
    pub providers: Arc<IdentityProviders>,
    pub policy: IdentityHttpPolicy,
    pub plugins: Option<Arc<dyn PluginDiagnosticsProvider>>,
}

#[async_trait]
pub trait PluginDiagnosticsProvider: Send + Sync {
    async fn diagnostics(&self) -> Result<BTreeMap<String, Value>, ServiceError>;
}

pub struct MmfPluginDiagnostics {
    manager: Arc<mmf_plugins::PluginManager>,
}

impl MmfPluginDiagnostics {
    #[must_use]
    pub fn new(manager: Arc<mmf_plugins::PluginManager>) -> Self {
        Self { manager }
    }
}

#[async_trait]
impl PluginDiagnosticsProvider for MmfPluginDiagnostics {
    async fn diagnostics(&self) -> Result<BTreeMap<String, Value>, ServiceError> {
        Ok(self
            .manager
            .list()
            .into_iter()
            .map(|(name, status)| {
                let version = self
                    .manager
                    .registry
                    .get(&name)
                    .map_or_else(|| "unknown".into(), |plugin| plugin.metadata.version);
                (
                    name,
                    json!({
                        "status": status,
                        "version": version
                    }),
                )
            })
            .collect())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ErrorResponse {
    pub error: String,
    pub message: String,
    pub code: String,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct IdentityHttpError {
    status: StatusCode,
    code: String,
    message: String,
}

impl IdentityHttpError {
    fn new(status: StatusCode, code: impl Into<String>, message: impl Into<String>) -> Self {
        Self {
            status,
            code: code.into(),
            message: message.into(),
        }
    }

    fn bad_request(code: &str, message: impl Into<String>) -> Self {
        Self::new(StatusCode::BAD_REQUEST, code, message)
    }

    fn unauthorized(code: &str, message: impl Into<String>) -> Self {
        Self::new(StatusCode::UNAUTHORIZED, code, message)
    }

    fn forbidden(code: &str, message: impl Into<String>) -> Self {
        Self::new(StatusCode::FORBIDDEN, code, message)
    }

    fn unavailable(code: &str, message: impl Into<String>) -> Self {
        Self::new(StatusCode::SERVICE_UNAVAILABLE, code, message)
    }
}

impl IntoResponse for IdentityHttpError {
    fn into_response(self) -> Response {
        let mut response = (
            self.status,
            Json(ErrorResponse {
                error: self.code.clone(),
                message: self.message,
                code: self.code,
            }),
        )
            .into_response();
        if self.status == StatusCode::UNAUTHORIZED {
            response.headers_mut().insert(
                axum::http::header::WWW_AUTHENTICATE,
                axum::http::HeaderValue::from_static("Bearer"),
            );
        }
        response
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct LoginRequest {
    pub username: String,
    #[serde(skip_serializing)]
    pub password: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct TokenResponse {
    pub token: String,
    pub token_type: String,
    pub expires_in: u64,
    pub user_id: String,
    pub username: String,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ValidateTokenResponse {
    pub valid: bool,
    pub user_id: Option<String>,
    pub username: Option<String>,
    pub email: Option<String>,
    #[serde(default)]
    pub roles: BTreeSet<String>,
    #[serde(default)]
    pub permissions: BTreeSet<String>,
    pub expires_at: Option<String>,
    pub expires_at_ms: Option<u64>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct UserResponse {
    pub user_id: String,
    pub username: String,
    pub email: Option<String>,
    pub roles: BTreeSet<String>,
    pub permissions: BTreeSet<String>,
    pub auth_method: Option<String>,
    pub created_at: Option<String>,
    pub expires_at: Option<String>,
    pub created_at_ms: Option<u64>,
    pub expires_at_ms: Option<u64>,
    pub metadata: BTreeMap<String, Value>,
    pub user_metadata: BTreeMap<String, Value>,
    pub attributes: BTreeMap<String, Value>,
}

impl From<AuthenticatedUser> for UserResponse {
    fn from(user: AuthenticatedUser) -> Self {
        let attributes = user.attributes;
        Self {
            username: user
                .username
                .clone()
                .unwrap_or_else(|| user.user_id.clone()),
            user_id: user.user_id,
            email: user.email,
            roles: user.roles,
            permissions: user.permissions,
            auth_method: user
                .auth_method
                .map(|method| format!("{method:?}").to_lowercase()),
            created_at: user.created_at_ms.map(rfc3339_from_millis),
            expires_at: user.expires_at_ms.map(rfc3339_from_millis),
            created_at_ms: user.created_at_ms,
            expires_at_ms: user.expires_at_ms,
            metadata: attributes.clone(),
            user_metadata: attributes.clone(),
            attributes,
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct TokenBody {
    #[serde(skip_serializing)]
    pub token: String,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ApiKeyRevokeRequest {
    pub api_key_id: String,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct HealthResponse {
    pub status: String,
    pub service: String,
    pub backend: String,
    pub version: String,
    pub providers: BTreeMap<String, bool>,
}

pub fn identity_router(state: IdentityHttpState) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/plugins", get(plugins))
        .route("/authenticate", post(legacy_authenticate))
        .route("/auth/login", post(login))
        .route("/auth/validate", post(validate_header))
        .route("/auth/me", get(me))
        .route("/auth/refresh", post(refresh))
        .route("/auth/logout", post(logout))
        .route("/auth/jwt/authenticate", post(authenticate_body))
        .route("/auth/jwt/validate", post(validate_jwt_body))
        .route("/auth/jwt/health", get(health))
        .route("/auth/password/change", post(change_password))
        .route("/auth/api-keys/create", post(create_api_key))
        .route("/auth/api-keys/revoke", post(revoke_api_key))
        .route_layer(middleware::from_fn_with_state(
            state.clone(),
            identity_authentication_middleware,
        ))
        .with_state(state)
}

async fn identity_authentication_middleware(
    State(state): State<IdentityHttpState>,
    mut request: Request,
    next: Next,
) -> Result<Response<Body>, IdentityHttpError> {
    let access = state.policy.access_for(request.uri().path());
    if access == PathAccess::Public {
        return Ok(next.run(request).await);
    }
    let token = match state.policy.bearer_token(request.headers()) {
        Ok(token) => token,
        Err(_) if access == PathAccess::Optional => return Ok(next.run(request).await),
        Err(_) => {
            return Err(IdentityHttpError::unauthorized(
                "AUTHENTICATION_REQUIRED",
                "Authentication required",
            ));
        }
    };
    let Some(provider) = &state.providers.token else {
        return Err(IdentityHttpError::unavailable(
            "NATIVE_BACKEND_UNAVAILABLE",
            "token provider is unavailable",
        ));
    };
    match provider.validate(token).await {
        Ok(user) => {
            request.extensions_mut().insert(user);
            Ok(next.run(request).await)
        }
        Err(_) if access == PathAccess::Optional => Ok(next.run(request).await),
        Err(_) => Err(IdentityHttpError::unauthorized(
            "TOKEN_INVALID",
            "Invalid or expired token",
        )),
    }
}

async fn health(State(state): State<IdentityHttpState>) -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "healthy".into(),
        service: "identity".into(),
        backend: "rust".into(),
        version: env!("CARGO_PKG_VERSION").into(),
        providers: BTreeMap::from([
            ("api_key".into(), state.providers.api_key.is_some()),
            ("mfa".into(), state.providers.mfa.is_some()),
            ("mtls".into(), state.providers.mutual_tls.is_some()),
            ("password".into(), state.providers.password.is_some()),
            ("session".into(), state.providers.sessions.is_some()),
            ("token".into(), state.providers.token.is_some()),
        ]),
    })
}

async fn plugins(State(state): State<IdentityHttpState>) -> Result<Json<Value>, IdentityHttpError> {
    let plugins = match &state.plugins {
        Some(provider) => provider.diagnostics().await.map_err(|error| {
            IdentityHttpError::unavailable("PLUGIN_DIAGNOSTICS_UNAVAILABLE", error.to_string())
        })?,
        None => BTreeMap::new(),
    };
    Ok(Json(json!({ "plugins": plugins })))
}

async fn login(
    State(state): State<IdentityHttpState>,
    Json(request): Json<LoginRequest>,
) -> Result<Json<TokenResponse>, IdentityHttpError> {
    let use_cases = use_cases(&state);
    let result = use_cases
        .authenticate_basic(
            &BasicAuthenticationRequest {
                username: request.username.clone(),
                password: request.password,
                context: None,
            },
            now_ms(),
        )
        .await
        .map_err(|error| IdentityHttpError::bad_request("INVALID_REQUEST", error.to_string()))?;
    let user = result.authenticated_user.ok_or_else(|| {
        IdentityHttpError::unauthorized(
            "INVALID_CREDENTIALS",
            result
                .error_message
                .unwrap_or_else(|| "Invalid credentials".into()),
        )
    })?;
    let issued = use_cases.issue_token(&user, &user.permissions).await;
    let envelope = token_envelope(issued)?;
    Ok(Json(TokenResponse {
        token: envelope.token,
        token_type: "Bearer".into(),
        expires_in: envelope.expires_in,
        user_id: user.user_id.clone(),
        username: user.username.unwrap_or(request.username),
    }))
}

async fn legacy_authenticate(
    State(state): State<IdentityHttpState>,
    Json(request): Json<LoginRequest>,
) -> Json<Value> {
    match login(State(state), Json(request)).await {
        Ok(Json(response)) => Json(json!({
            "success": true,
            "user_id": response.user_id,
            "username": response.username,
            "token": response.token,
            "token_type": response.token_type,
            "expires_in": response.expires_in,
            "authenticated_at": rfc3339_from_millis(now_ms()),
            "expires_at": rfc3339_from_millis(
                now_ms().saturating_add(response.expires_in.saturating_mul(1_000))
            )
        })),
        Err(error) => Json(json!({
            "success": false,
            "error_message": error.message,
            "error_code": error.code
        })),
    }
}

async fn validate_header(
    State(state): State<IdentityHttpState>,
    headers: HeaderMap,
) -> Result<Json<ValidateTokenResponse>, IdentityHttpError> {
    let token = state.policy.bearer_token(&headers)?;
    Ok(Json(validate(&state, token).await))
}

async fn validate_jwt_body(
    State(state): State<IdentityHttpState>,
    Json(body): Json<TokenBody>,
) -> Json<Value> {
    let result = use_cases(&state)
        .validate_token(&TokenAuthenticationRequest { token: body.token })
        .await;
    match result.user.filter(|_| result.is_valid) {
        Some(user) => Json(json!({
            "is_valid": true,
            "user": UserResponse::from(user),
            "error_message": null
        })),
        None => Json(json!({
            "is_valid": false,
            "user": null,
            "error_message": result.error_message
        })),
    }
}

async fn authenticate_body(
    State(state): State<IdentityHttpState>,
    Json(body): Json<TokenBody>,
) -> Result<Json<Value>, IdentityHttpError> {
    let result = use_cases(&state)
        .authenticate_token(&TokenAuthenticationRequest { token: body.token }, now_ms())
        .await
        .map_err(|error| IdentityHttpError::bad_request("INVALID_REQUEST", error.to_string()))?;
    result.authenticated_user.map_or_else(
        || {
            Err(IdentityHttpError::unauthorized(
                "TOKEN_INVALID",
                result
                    .error_message
                    .unwrap_or_else(|| "Authentication failed".into()),
            ))
        },
        |user| {
            Ok(Json(json!({
                "status": "success",
                "user": UserResponse::from(user),
                "error_code": null,
                "error_message": null,
                "metadata": result.metadata
            })))
        },
    )
}

async fn validate(state: &IdentityHttpState, token: &str) -> ValidateTokenResponse {
    let result = use_cases(state)
        .validate_token(&TokenAuthenticationRequest {
            token: token.into(),
        })
        .await;
    let Some(user) = result.user else {
        return ValidateTokenResponse {
            valid: false,
            user_id: None,
            username: None,
            email: None,
            roles: BTreeSet::new(),
            permissions: BTreeSet::new(),
            expires_at: None,
            expires_at_ms: None,
        };
    };
    ValidateTokenResponse {
        valid: result.is_valid,
        user_id: Some(user.user_id),
        username: user.username,
        email: user.email,
        roles: user.roles,
        permissions: user.permissions,
        expires_at: user.expires_at_ms.map(rfc3339_from_millis),
        expires_at_ms: user.expires_at_ms,
    }
}

async fn me(request: Request) -> Result<Json<UserResponse>, IdentityHttpError> {
    request
        .extensions()
        .get::<AuthenticatedUser>()
        .cloned()
        .map(UserResponse::from)
        .map(Json)
        .ok_or_else(|| {
            IdentityHttpError::unauthorized("AUTHENTICATION_REQUIRED", "Authentication required")
        })
}

async fn refresh(
    State(state): State<IdentityHttpState>,
    headers: HeaderMap,
) -> Result<Json<TokenResponse>, IdentityHttpError> {
    let token = state.policy.bearer_token(&headers)?;
    let refreshed = use_cases(&state).refresh_token(token).await;
    let envelope = token_envelope(refreshed)?;
    let user = state
        .providers
        .token
        .as_ref()
        .ok_or_else(|| {
            IdentityHttpError::unavailable(
                "NATIVE_BACKEND_UNAVAILABLE",
                "token provider is unavailable",
            )
        })?
        .validate(&envelope.token)
        .await
        .map_err(|_| {
            IdentityHttpError::unauthorized("TOKEN_REFRESH_FAILED", "Token refresh failed")
        })?;
    Ok(Json(TokenResponse {
        token: envelope.token,
        token_type: "Bearer".into(),
        expires_in: envelope.expires_in,
        user_id: user.user_id.clone(),
        username: user.username.unwrap_or(user.user_id),
    }))
}

async fn logout(
    State(state): State<IdentityHttpState>,
    headers: HeaderMap,
) -> Result<Json<Value>, IdentityHttpError> {
    let token = state.policy.bearer_token(&headers)?;
    let result = use_cases(&state).revoke_token(token).await;
    if result.success {
        Ok(Json(json!({ "message": result.message })))
    } else {
        Err(IdentityHttpError::unauthorized(
            result
                .error_code
                .as_deref()
                .unwrap_or("TOKEN_REVOKE_FAILED"),
            result.message,
        ))
    }
}

async fn change_password(
    Extension(caller): Extension<AuthenticatedUser>,
    State(state): State<IdentityHttpState>,
    Json(request): Json<ChangePasswordRequest>,
) -> Result<Json<Value>, IdentityHttpError> {
    if !caller.is_administrator()
        && caller.user_id != request.username
        && caller.username.as_deref() != Some(request.username.as_str())
    {
        return Err(IdentityHttpError::forbidden(
            "PASSWORD_CHANGE_FORBIDDEN",
            "Password changes are limited to the authenticated user",
        ));
    }
    operation_response(use_cases(&state).change_password(&request).await)
}

async fn create_api_key(
    Extension(caller): Extension<AuthenticatedUser>,
    State(state): State<IdentityHttpState>,
    Json(request): Json<CreateApiKeyRequest>,
) -> Result<Json<Value>, IdentityHttpError> {
    if !caller.is_administrator() && caller.user_id != request.user_id {
        return Err(IdentityHttpError::forbidden(
            "API_KEY_CREATE_FORBIDDEN",
            "API keys may only be created for the authenticated user",
        ));
    }
    operation_response(use_cases(&state).create_api_key(&request, now_ms()).await)
}

async fn revoke_api_key(
    Extension(caller): Extension<AuthenticatedUser>,
    State(state): State<IdentityHttpState>,
    Json(request): Json<ApiKeyRevokeRequest>,
) -> Result<Json<Value>, IdentityHttpError> {
    if !caller.is_administrator()
        && !caller.has_permission("*")
        && !caller.has_permission("api_key:revoke")
    {
        return Err(IdentityHttpError::forbidden(
            "API_KEY_REVOKE_FORBIDDEN",
            "API-key revoke permission is required",
        ));
    }
    operation_response(use_cases(&state).revoke_api_key(&request.api_key_id).await)
}

fn operation_response(
    result: crate::identity_usecases::OperationResult,
) -> Result<Json<Value>, IdentityHttpError> {
    if result.success {
        Ok(Json(json!({
            "success": true,
            "message": result.message,
            "value": result.value
        })))
    } else {
        Err(IdentityHttpError::bad_request(
            result.error_code.as_deref().unwrap_or("OPERATION_FAILED"),
            result.message,
        ))
    }
}

fn use_cases(state: &IdentityHttpState) -> IdentityUseCases<'_> {
    IdentityUseCases {
        manager: &state.manager,
        providers: &state.providers,
    }
}

struct TokenEnvelope {
    token: String,
    expires_in: u64,
}

fn token_envelope(
    result: crate::identity_usecases::OperationResult,
) -> Result<TokenEnvelope, IdentityHttpError> {
    if !result.success {
        return Err(IdentityHttpError::unavailable(
            result
                .error_code
                .as_deref()
                .unwrap_or("TOKEN_OPERATION_FAILED"),
            result.message,
        ));
    }
    let value = result.value.ok_or_else(|| {
        IdentityHttpError::unavailable(
            "INVALID_PROVIDER_RESULT",
            "token provider returned no token",
        )
    })?;
    let (token, expires_in) = match value {
        Value::String(token) => (token, 3_600),
        Value::Object(values) => {
            let token = values
                .get("token")
                .or_else(|| values.get("access_token"))
                .and_then(Value::as_str)
                .unwrap_or_default()
                .to_owned();
            let expires_in = values
                .get("expires_in")
                .and_then(Value::as_u64)
                .unwrap_or(3_600);
            (token, expires_in)
        }
        _ => (String::new(), 0),
    };
    if token.is_empty() || expires_in == 0 {
        return Err(IdentityHttpError::unavailable(
            "INVALID_PROVIDER_RESULT",
            "token provider returned an invalid token envelope",
        ));
    }
    Ok(TokenEnvelope { token, expires_in })
}

fn now_ms() -> u64 {
    let millis = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis();
    u64::try_from(millis).unwrap_or(u64::MAX)
}

fn rfc3339_from_millis(timestamp_ms: u64) -> String {
    let total_seconds = timestamp_ms / 1_000;
    let milliseconds = timestamp_ms % 1_000;
    let days = i64::try_from(total_seconds / 86_400).unwrap_or(i64::MAX);
    let seconds_of_day = total_seconds % 86_400;
    let (year, month, day) = civil_from_days(days);
    let hour = seconds_of_day / 3_600;
    let minute = (seconds_of_day % 3_600) / 60;
    let second = seconds_of_day % 60;
    format!("{year:04}-{month:02}-{day:02}T{hour:02}:{minute:02}:{second:02}.{milliseconds:03}Z")
}

fn civil_from_days(days_since_epoch: i64) -> (i64, u64, u64) {
    let adjusted = days_since_epoch.saturating_add(719_468);
    let era = if adjusted >= 0 {
        adjusted
    } else {
        adjusted - 146_096
    } / 146_097;
    let day_of_era = adjusted - era * 146_097;
    let year_of_era =
        (day_of_era - day_of_era / 1_460 + day_of_era / 36_524 - day_of_era / 146_096) / 365;
    let mut year = year_of_era + era * 400;
    let day_of_year = day_of_era - (365 * year_of_era + year_of_era / 4 - year_of_era / 100);
    let month_prime = (5 * day_of_year + 2) / 153;
    let day = day_of_year - (153 * month_prime + 2) / 5 + 1;
    let month = month_prime + if month_prime < 10 { 3 } else { -9 };
    year += i64::from(month <= 2);
    (
        year,
        u64::try_from(month).unwrap_or_default(),
        u64::try_from(day).unwrap_or_default(),
    )
}

#[cfg(test)]
mod tests {
    use std::sync::atomic::{AtomicBool, Ordering};

    use axum::http::{Method, Request as HttpRequest};
    use http_body_util::BodyExt;
    use mmf_security::{
        AuthenticationMethod, AuthenticationRequest, AuthenticationResult, Authenticator,
        SecurityError,
    };
    use tower::ServiceExt;

    use super::*;
    use crate::identity::{IdentityTokenProvider, PasswordProvider};

    #[derive(Deserialize)]
    struct Fixture {
        schema_version: u32,
        routes: BTreeMap<String, String>,
        credentials: FixtureCredentials,
        responses: FixtureResponses,
        authorization: FixtureAuthorization,
        failures: FixtureFailures,
    }

    #[derive(Deserialize)]
    struct FixtureCredentials {
        username: String,
        password: String,
        token: String,
        refresh_token: String,
    }

    #[derive(Deserialize)]
    struct FixtureResponses {
        service: String,
        backend: String,
        version: String,
        token_type: String,
        expires_in: u64,
        logout_message: String,
    }

    #[derive(Deserialize)]
    struct FixtureAuthorization {
        role: String,
        permission: String,
        missing_role: String,
        missing_permission: String,
    }

    #[derive(Deserialize)]
    struct FixtureFailures {
        missing_bearer: String,
        invalid_bearer: String,
        authentication_required: String,
        role_forbidden: String,
        permission_forbidden: String,
    }

    fn fixture() -> Fixture {
        serde_json::from_str(include_str!(
            "../../../contracts/identity-service-http-behavior.json"
        ))
        .expect("valid HTTP behavior fixture")
    }

    fn user(fixture: &Fixture) -> AuthenticatedUser {
        AuthenticatedUser {
            user_id: "user-123".into(),
            username: Some(fixture.credentials.username.clone()),
            email: Some("alex@example.com".into()),
            roles: BTreeSet::from([fixture.authorization.role.clone()]),
            permissions: BTreeSet::from([fixture.authorization.permission.clone()]),
            session_id: None,
            auth_method: Some(AuthenticationMethod::Basic),
            expires_at_ms: None,
            created_at_ms: Some(1_000),
            attributes: BTreeMap::new(),
            user_type: None,
            applicant_id: None,
        }
    }

    struct TestAuthenticator(AuthenticatedUser);

    #[async_trait]
    impl Authenticator for TestAuthenticator {
        async fn authenticate(
            &self,
            _: &AuthenticationRequest,
        ) -> Result<AuthenticationResult, SecurityError> {
            Ok(AuthenticationResult {
                success: true,
                user: Some(self.0.clone()),
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

    struct TestToken {
        user: AuthenticatedUser,
        revoked: AtomicBool,
        token: String,
        refresh_token: String,
    }

    #[async_trait]
    impl IdentityTokenProvider for TestToken {
        async fn issue(
            &self,
            _: &AuthenticatedUser,
            _: &BTreeSet<String>,
        ) -> Result<Value, ServiceError> {
            Ok(json!({ "token": self.token, "expires_in": 3600 }))
        }

        async fn validate(&self, token: &str) -> Result<AuthenticatedUser, ServiceError> {
            if token == self.token || token == self.refresh_token {
                Ok(self.user.clone())
            } else {
                Err(ServiceError::Unauthorized("invalid token".into()))
            }
        }

        async fn refresh(&self, token: &str) -> Result<Value, ServiceError> {
            if token == self.token || token == self.refresh_token {
                Ok(json!({ "token": self.refresh_token, "expires_in": 3600 }))
            } else {
                Err(ServiceError::Unauthorized("invalid token".into()))
            }
        }

        async fn revoke(&self, _: &str) -> Result<(), ServiceError> {
            self.revoked.store(true, Ordering::SeqCst);
            Ok(())
        }
    }

    async fn app(fixture: &Fixture) -> Router {
        let manager = Arc::new(AuthenticationManager::default());
        manager
            .register(
                AuthenticationMethod::Basic,
                Arc::new(TestAuthenticator(user(fixture))),
            )
            .await;
        let token = Arc::new(TestToken {
            user: user(fixture),
            revoked: AtomicBool::new(false),
            token: fixture.credentials.token.clone(),
            refresh_token: fixture.credentials.refresh_token.clone(),
        });
        identity_router(IdentityHttpState {
            manager,
            providers: Arc::new(IdentityProviders {
                token: Some(token),
                password: Some(Arc::new(TestPassword)),
                api_key: None,
                mutual_tls: None,
                mfa: None,
                sessions: None,
                federated: BTreeMap::new(),
            }),
            policy: IdentityHttpPolicy::default(),
            plugins: None,
        })
    }

    async fn send(
        app: &Router,
        method: Method,
        uri: &str,
        body: Value,
        bearer: Option<&str>,
    ) -> (StatusCode, Value) {
        let mut request = HttpRequest::builder()
            .method(method)
            .uri(uri)
            .header("content-type", "application/json");
        if let Some(token) = bearer {
            request = request.header("authorization", format!("Bearer {token}"));
        }
        let response = app
            .clone()
            .oneshot(request.body(Body::from(body.to_string())).expect("request"))
            .await
            .expect("response");
        let status = response.status();
        let bytes = response
            .into_body()
            .collect()
            .await
            .expect("body")
            .to_bytes();
        let value = serde_json::from_slice(&bytes).unwrap_or(Value::Null);
        (status, value)
    }

    #[tokio::test]
    async fn language_neutral_http_routes_preserve_identity_behavior() {
        let fixture = fixture();
        assert_eq!(fixture.schema_version, 1);
        let app = app(&fixture).await;
        let (status, health) = send(
            &app,
            Method::GET,
            &fixture.routes["health"],
            Value::Null,
            None,
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(health["service"], fixture.responses.service);
        assert_eq!(health["backend"], fixture.responses.backend);
        assert_eq!(health["version"], fixture.responses.version);

        let (status, login) = send(
            &app,
            Method::POST,
            &fixture.routes["login"],
            json!({
                "username": fixture.credentials.username,
                "password": fixture.credentials.password
            }),
            None,
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(login["token_type"], fixture.responses.token_type);
        assert_eq!(login["expires_in"], fixture.responses.expires_in);
        assert_eq!(login["token"], fixture.credentials.token);

        let (status, legacy) = send(
            &app,
            Method::POST,
            &fixture.routes["legacy_authenticate"],
            json!({
                "username": fixture.credentials.username,
                "password": fixture.credentials.password
            }),
            None,
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(legacy["success"], true);
        assert_eq!(legacy["token"], fixture.credentials.token);
        assert!(legacy["authenticated_at"].as_str().is_some());

        let (status, current) = send(
            &app,
            Method::GET,
            &fixture.routes["me"],
            Value::Null,
            Some(&fixture.credentials.token),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(current["username"], fixture.credentials.username);
        assert_eq!(current["created_at"], "1970-01-01T00:00:01.000Z");

        let (status, validation) = send(
            &app,
            Method::POST,
            &fixture.routes["validate"],
            Value::Null,
            Some(&fixture.credentials.token),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(validation["valid"], true);

        let (status, jwt_authentication) = send(
            &app,
            Method::POST,
            &fixture.routes["jwt_authenticate"],
            json!({"token": fixture.credentials.token}),
            None,
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(jwt_authentication["status"], "success");
        assert_eq!(
            jwt_authentication["user"]["username"],
            fixture.credentials.username
        );

        let (status, jwt_validation) = send(
            &app,
            Method::POST,
            &fixture.routes["jwt_validate"],
            json!({"token": fixture.credentials.token}),
            None,
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(jwt_validation["is_valid"], true);

        let (status, logout) = send(
            &app,
            Method::POST,
            &fixture.routes["logout"],
            Value::Null,
            Some(&fixture.credentials.token),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(logout["message"], fixture.responses.logout_message);
    }

    #[tokio::test]
    async fn middleware_and_authorization_fail_closed() {
        let fixture = fixture();
        let app = app(&fixture).await;
        let (status, body) =
            send(&app, Method::GET, &fixture.routes["me"], Value::Null, None).await;
        assert_eq!(status, StatusCode::UNAUTHORIZED);
        assert_eq!(body["message"], fixture.failures.authentication_required);

        let policy = IdentityHttpPolicy::default();
        let user = user(&fixture);
        policy
            .require_role(&user, &fixture.authorization.role)
            .expect("role");
        policy
            .require_permission(&user, &fixture.authorization.permission)
            .expect("permission");
        assert_eq!(
            policy
                .require_role(&user, &fixture.authorization.missing_role)
                .expect_err("missing role")
                .message,
            fixture.failures.role_forbidden
        );
        assert_eq!(
            policy
                .require_permission(&user, &fixture.authorization.missing_permission)
                .expect_err("missing permission")
                .message,
            fixture.failures.permission_forbidden
        );
        let missing = policy.bearer_token(&HeaderMap::new()).expect_err("missing");
        assert_eq!(missing.message, fixture.failures.missing_bearer);
        let mut invalid_headers = HeaderMap::new();
        invalid_headers.insert(
            axum::http::header::AUTHORIZATION,
            axum::http::HeaderValue::from_static("Basic secret"),
        );
        assert_eq!(
            policy
                .bearer_token(&invalid_headers)
                .expect_err("invalid")
                .message,
            fixture.failures.invalid_bearer
        );
    }
}
