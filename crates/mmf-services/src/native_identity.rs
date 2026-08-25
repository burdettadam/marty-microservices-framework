//! Native first-party password and JWT provider adapters.

use std::collections::{BTreeMap, BTreeSet};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use async_trait::async_trait;
use base64::Engine as _;
use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use mmf_security::jwt_hmac::HmacJwtCodec;
use mmf_security::{
    AuthenticatedUser, AuthenticationRequest, AuthenticationResult, Authenticator, SecurityError,
};
use rand::Rng as _;
use scrypt::{Params as ScryptParams, scrypt};
use serde_json::{Map, Value, json};
use sha2::{Digest as _, Sha256};
use tokio::sync::RwLock;
use uuid::Uuid;

use crate::ServiceError;
use crate::identity::{ApiKeyProvider, IdentityTokenProvider, PasswordProvider};

pub trait PasswordHashProvider: Send + Sync {
    fn hash(&self, password: &[u8]) -> Result<String, ServiceError>;
    fn verify(&self, password: &[u8], encoded: &str) -> Result<bool, ServiceError>;
}

#[derive(Default)]
pub struct ScryptPasswordHashProvider;

impl PasswordHashProvider for ScryptPasswordHashProvider {
    fn hash(&self, password: &[u8]) -> Result<String, ServiceError> {
        if password.is_empty() {
            return Err(ServiceError::InvalidConfiguration(
                "password cannot be empty".into(),
            ));
        }
        let salt = rand::random::<[u8; 16]>();
        let params = ScryptParams::RECOMMENDED;
        let mut output = [0_u8; ScryptParams::RECOMMENDED_LEN];
        scrypt(password, &salt, &params, &mut output)
            .map_err(|_| ServiceError::Operation("password hashing failed".into()))?;
        Ok(format!(
            "$scrypt${}${}${}${}${}",
            params.log_n(),
            params.r(),
            params.p(),
            URL_SAFE_NO_PAD.encode(salt),
            URL_SAFE_NO_PAD.encode(output)
        ))
    }

    fn verify(&self, password: &[u8], encoded: &str) -> Result<bool, ServiceError> {
        let mut fields = encoded.split('$');
        let valid_prefix = fields.next() == Some("") && fields.next() == Some("scrypt");
        let log_n = fields.next().and_then(|value| value.parse::<u8>().ok());
        let r = fields.next().and_then(|value| value.parse::<u32>().ok());
        let p = fields.next().and_then(|value| value.parse::<u32>().ok());
        let salt = fields
            .next()
            .and_then(|value| URL_SAFE_NO_PAD.decode(value).ok());
        let expected = fields
            .next()
            .and_then(|value| URL_SAFE_NO_PAD.decode(value).ok());
        if !valid_prefix || fields.next().is_some() {
            return Err(ServiceError::Operation(
                "stored password hash is invalid".into(),
            ));
        }
        let (Some(log_n), Some(r), Some(p), Some(salt), Some(expected)) =
            (log_n, r, p, salt, expected)
        else {
            return Err(ServiceError::Operation(
                "stored password hash is invalid".into(),
            ));
        };
        let params = ScryptParams::new(log_n, r, p)
            .map_err(|_| ServiceError::Operation("stored password hash is invalid".into()))?;
        let mut computed = vec![0_u8; expected.len()];
        scrypt(password, &salt, &params, &mut computed)
            .map_err(|_| ServiceError::Operation("password verification failed".into()))?;
        Ok(constant_time_equal(&computed, &expected))
    }
}

#[derive(Clone, Debug)]
#[allow(clippy::struct_excessive_bools)]
pub struct NativePasswordPolicy {
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
}

impl Default for NativePasswordPolicy {
    fn default() -> Self {
        Self {
            min_length: 8,
            max_length: 128,
            require_uppercase: true,
            require_lowercase: true,
            require_numbers: true,
            require_special_characters: false,
            special_characters: "!@#$%^&*()_+-=[]{}|;:,.<>?".into(),
            max_login_attempts: 5,
            lockout_duration_ms: 900_000,
            password_expiry_ms: 7_776_000_000,
        }
    }
}

impl From<&crate::identity_config::PasswordAuthenticationConfig> for NativePasswordPolicy {
    fn from(config: &crate::identity_config::PasswordAuthenticationConfig) -> Self {
        Self {
            min_length: config.min_length,
            max_length: config.max_length,
            require_uppercase: config.require_uppercase,
            require_lowercase: config.require_lowercase,
            require_numbers: config.require_numbers,
            require_special_characters: config.require_special_characters,
            special_characters: config.special_characters.clone(),
            max_login_attempts: config.max_login_attempts,
            lockout_duration_ms: config.lockout_duration_ms,
            password_expiry_ms: config.password_expiry_ms,
        }
    }
}

impl NativePasswordPolicy {
    fn validate(&self, password: &[u8]) -> Result<(), ServiceError> {
        let password = std::str::from_utf8(password).map_err(|_| {
            ServiceError::InvalidConfiguration("password must be valid UTF-8".into())
        })?;
        let valid = (self.min_length..=self.max_length).contains(&password.chars().count())
            && (!self.require_uppercase || password.chars().any(char::is_uppercase))
            && (!self.require_lowercase || password.chars().any(char::is_lowercase))
            && (!self.require_numbers || password.chars().any(char::is_numeric))
            && (!self.require_special_characters
                || password
                    .chars()
                    .any(|character| self.special_characters.contains(character)));
        if valid {
            Ok(())
        } else {
            Err(ServiceError::InvalidConfiguration(
                "password does not satisfy the configured policy".into(),
            ))
        }
    }
}

#[derive(Clone)]
struct PasswordUser {
    user: AuthenticatedUser,
    password_hash: String,
    failed_attempts: usize,
    locked_until_ms: Option<u64>,
    password_changed_at_ms: u64,
}

pub struct NativeBasicAuthenticator {
    users: RwLock<BTreeMap<String, PasswordUser>>,
    hasher: Arc<dyn PasswordHashProvider>,
    policy: NativePasswordPolicy,
}

impl NativeBasicAuthenticator {
    #[must_use]
    pub fn new(hasher: Arc<dyn PasswordHashProvider>) -> Self {
        Self {
            users: RwLock::new(BTreeMap::new()),
            hasher,
            policy: NativePasswordPolicy::default(),
        }
    }

    #[must_use]
    pub fn with_policy(
        hasher: Arc<dyn PasswordHashProvider>,
        policy: NativePasswordPolicy,
    ) -> Self {
        Self {
            users: RwLock::new(BTreeMap::new()),
            hasher,
            policy,
        }
    }

    pub async fn register(
        &self,
        username: impl Into<String>,
        password: &[u8],
        user: AuthenticatedUser,
    ) -> Result<(), ServiceError> {
        self.policy.validate(password)?;
        self.register_seed_user(username, password, user).await
    }

    pub async fn register_seed_user(
        &self,
        username: impl Into<String>,
        password: &[u8],
        user: AuthenticatedUser,
    ) -> Result<(), ServiceError> {
        let username = username.into();
        if username.trim().is_empty() {
            return Err(ServiceError::InvalidConfiguration(
                "username cannot be empty".into(),
            ));
        }
        user.validate()
            .map_err(|error| ServiceError::InvalidConfiguration(error.to_string()))?;
        let password_hash = self.hasher.hash(password)?;
        let mut users = self.users.write().await;
        if users.contains_key(&username)
            || users
                .values()
                .any(|entry| entry.user.user_id == user.user_id)
        {
            return Err(ServiceError::Conflict(
                "username or user ID is already registered".into(),
            ));
        }
        users.insert(
            username,
            PasswordUser {
                user,
                password_hash,
                failed_attempts: 0,
                locked_until_ms: None,
                password_changed_at_ms: now_millis(),
            },
        );
        Ok(())
    }

    async fn entry_for(&self, identity: &str) -> Option<PasswordUser> {
        let users = self.users.read().await;
        users.get(identity).cloned().or_else(|| {
            users
                .values()
                .find(|entry| entry.user.user_id == identity)
                .cloned()
        })
    }
}

#[async_trait]
impl Authenticator for NativeBasicAuthenticator {
    async fn authenticate(
        &self,
        request: &AuthenticationRequest,
    ) -> Result<AuthenticationResult, SecurityError> {
        let Some((username, password)) = request.credential.split_once(':') else {
            return Ok(AuthenticationResult {
                success: false,
                user: None,
                error: Some("username and password are required".into()),
                error_code: Some("MISSING_CREDENTIALS".into()),
                metadata: BTreeMap::new(),
            });
        };
        let Some(entry) = self.entry_for(username).await else {
            return Ok(AuthenticationResult {
                success: false,
                user: None,
                error: Some("invalid credentials".into()),
                error_code: Some("INVALID_USERNAME".into()),
                metadata: BTreeMap::new(),
            });
        };
        let now = now_millis();
        if entry.locked_until_ms.is_some_and(|locked| locked > now) {
            return Ok(AuthenticationResult {
                success: false,
                user: None,
                error: Some("account is temporarily locked".into()),
                error_code: Some("ACCOUNT_LOCKED".into()),
                metadata: BTreeMap::new(),
            });
        }
        if entry
            .password_changed_at_ms
            .saturating_add(self.policy.password_expiry_ms)
            <= now
        {
            return Ok(AuthenticationResult {
                success: false,
                user: None,
                error: Some("password has expired".into()),
                error_code: Some("PASSWORD_EXPIRED".into()),
                metadata: BTreeMap::new(),
            });
        }
        let valid = self
            .hasher
            .verify(password.as_bytes(), &entry.password_hash)
            .map_err(|error| SecurityError::ProviderUnavailable(error.to_string()))?;
        let mut users = self.users.write().await;
        if let Some(stored) = users.get_mut(username) {
            if valid {
                stored.failed_attempts = 0;
                stored.locked_until_ms = None;
            } else {
                stored.failed_attempts = stored.failed_attempts.saturating_add(1);
                if stored.failed_attempts >= self.policy.max_login_attempts {
                    stored.locked_until_ms =
                        Some(now.saturating_add(self.policy.lockout_duration_ms));
                }
            }
        }
        Ok(if valid {
            AuthenticationResult {
                success: true,
                user: Some(entry.user),
                error: None,
                error_code: None,
                metadata: BTreeMap::new(),
            }
        } else {
            AuthenticationResult {
                success: false,
                user: None,
                error: Some("invalid credentials".into()),
                error_code: Some("INVALID_PASSWORD".into()),
                metadata: BTreeMap::new(),
            }
        })
    }
}

#[async_trait]
impl PasswordProvider for NativeBasicAuthenticator {
    async fn verify(&self, user_id: &str, password: &[u8]) -> Result<bool, ServiceError> {
        let entry = self
            .entry_for(user_id)
            .await
            .ok_or_else(|| ServiceError::NotFound("user was not found".into()))?;
        self.hasher.verify(password, &entry.password_hash)
    }

    async fn change(
        &self,
        user_id: &str,
        current: &[u8],
        replacement: &[u8],
    ) -> Result<(), ServiceError> {
        self.policy.validate(replacement)?;
        let replacement_hash = self.hasher.hash(replacement)?;
        let mut users = self.users.write().await;
        let (_, entry) = users
            .iter_mut()
            .find(|(username, entry)| username.as_str() == user_id || entry.user.user_id == user_id)
            .ok_or_else(|| ServiceError::NotFound("user was not found".into()))?;
        if !self.hasher.verify(current, &entry.password_hash)? {
            return Err(ServiceError::Unauthorized(
                "current password is invalid".into(),
            ));
        }
        entry.password_hash = replacement_hash;
        entry.failed_attempts = 0;
        entry.locked_until_ms = None;
        entry.password_changed_at_ms = now_millis();
        Ok(())
    }
}

#[derive(Clone)]
struct ApiKeyEntry {
    digest: [u8; 32],
    user: AuthenticatedUser,
    key_name: Option<String>,
    expires_at_ms: Option<u64>,
    usage_count: u64,
    last_used_at_ms: Option<u64>,
}

#[derive(Clone, Debug)]
pub struct NativeApiKeyPolicy {
    pub entropy_bytes: usize,
    pub prefix: String,
    pub default_expiry_ms: u64,
    pub max_keys_per_user: usize,
    pub rotation_warning_ms: u64,
    pub enable_usage_tracking: bool,
}

impl Default for NativeApiKeyPolicy {
    fn default() -> Self {
        Self::from(&crate::identity_config::ApiKeyConfiguration::default())
    }
}

impl From<&crate::identity_config::ApiKeyConfiguration> for NativeApiKeyPolicy {
    fn from(config: &crate::identity_config::ApiKeyConfiguration) -> Self {
        Self {
            entropy_bytes: config.entropy_bytes,
            prefix: config.prefix.clone(),
            default_expiry_ms: config.default_expiry_ms,
            max_keys_per_user: config.max_keys_per_user,
            rotation_warning_ms: config.rotation_warning_ms,
            enable_usage_tracking: config.enable_usage_tracking,
        }
    }
}

pub struct NativeApiKeyProvider {
    users: RwLock<BTreeMap<String, AuthenticatedUser>>,
    keys: RwLock<BTreeMap<String, ApiKeyEntry>>,
    policy: NativeApiKeyPolicy,
}

impl Default for NativeApiKeyProvider {
    fn default() -> Self {
        Self::new(NativeApiKeyPolicy::default())
    }
}

impl NativeApiKeyProvider {
    #[must_use]
    pub fn new(policy: NativeApiKeyPolicy) -> Self {
        Self {
            users: RwLock::new(BTreeMap::new()),
            keys: RwLock::new(BTreeMap::new()),
            policy,
        }
    }

    pub async fn register_user(&self, user: AuthenticatedUser) -> Result<(), ServiceError> {
        user.validate()
            .map_err(|error| ServiceError::InvalidConfiguration(error.to_string()))?;
        self.users.write().await.insert(user.user_id.clone(), user);
        Ok(())
    }

    fn digest(api_key: &[u8]) -> [u8; 32] {
        Sha256::digest(api_key).into()
    }

    pub async fn metadata(&self, key_id: &str) -> Option<Value> {
        self.keys.read().await.get(key_id).map(|entry| {
            json!({
                "key_id": key_id,
                "key_name": entry.key_name,
                "user_id": entry.user.user_id,
                "expires_at_ms": entry.expires_at_ms,
                "rotation_warning_at_ms": entry.expires_at_ms.map(|expiry| {
                    expiry.saturating_sub(self.policy.rotation_warning_ms)
                }),
                "usage_count": entry.usage_count,
                "last_used_at_ms": entry.last_used_at_ms
            })
        })
    }
}

#[async_trait]
impl ApiKeyProvider for NativeApiKeyProvider {
    async fn authenticate(&self, api_key: &[u8]) -> Result<AuthenticatedUser, ServiceError> {
        let digest = Self::digest(api_key);
        let now = now_millis();
        let mut keys = self.keys.write().await;
        let entry = keys
            .values_mut()
            .find(|entry| {
                constant_time_equal(&entry.digest, &digest)
                    && entry.expires_at_ms.is_none_or(|expiry| expiry > now)
            })
            .ok_or_else(|| ServiceError::Unauthorized("API key is invalid or expired".into()))?;
        if self.policy.enable_usage_tracking {
            entry.usage_count = entry.usage_count.saturating_add(1);
            entry.last_used_at_ms = Some(now);
        }
        Ok(entry.user.clone())
    }

    async fn create(
        &self,
        user_id: &str,
        key_name: Option<&str>,
        expires_at_ms: Option<u64>,
        scopes: BTreeSet<String>,
    ) -> Result<Value, ServiceError> {
        if key_name.is_some_and(|name| name.trim().is_empty())
            || expires_at_ms.is_some_and(|expiry| expiry <= now_millis())
        {
            return Err(ServiceError::InvalidConfiguration(
                "invalid API-key metadata".into(),
            ));
        }
        let mut user = self
            .users
            .read()
            .await
            .get(user_id)
            .cloned()
            .ok_or_else(|| ServiceError::NotFound("user was not found".into()))?;
        if !scopes.is_empty() {
            user.permissions = scopes;
        }
        let mut keys = self.keys.write().await;
        if keys
            .values()
            .filter(|entry| entry.user.user_id == user_id)
            .count()
            >= self.policy.max_keys_per_user
        {
            return Err(ServiceError::Conflict(
                "maximum API keys per user reached".into(),
            ));
        }
        let key_id = Uuid::new_v4().to_string();
        let mut entropy = vec![0_u8; self.policy.entropy_bytes];
        rand::rng().fill_bytes(&mut entropy);
        let secret = format!("{}{}", self.policy.prefix, URL_SAFE_NO_PAD.encode(entropy));
        let expires_at_ms = Some(
            expires_at_ms
                .unwrap_or_else(|| now_millis().saturating_add(self.policy.default_expiry_ms)),
        );
        keys.insert(
            key_id.clone(),
            ApiKeyEntry {
                digest: Self::digest(secret.as_bytes()),
                user,
                key_name: key_name.map(str::to_owned),
                expires_at_ms,
                usage_count: 0,
                last_used_at_ms: None,
            },
        );
        Ok(json!({
            "api_key": secret,
            "key_id": key_id,
            "key_name": key_name,
            "expires_at_ms": expires_at_ms
        }))
    }

    async fn revoke(&self, key_id: &str) -> Result<(), ServiceError> {
        self.keys
            .write()
            .await
            .remove(key_id)
            .map(drop)
            .ok_or_else(|| ServiceError::NotFound("API key was not found".into()))
    }
}

#[async_trait]
pub trait TokenRevocationStore: Send + Sync {
    async fn revoke(&self, token_id: &str, expires_at_seconds: u64) -> Result<(), ServiceError>;
    async fn is_revoked(&self, token_id: &str, now_seconds: u64) -> Result<bool, ServiceError>;
}

#[derive(Default)]
pub struct InMemoryTokenRevocationStore {
    revoked: RwLock<BTreeMap<String, u64>>,
}

#[async_trait]
impl TokenRevocationStore for InMemoryTokenRevocationStore {
    async fn revoke(&self, token_id: &str, expires_at_seconds: u64) -> Result<(), ServiceError> {
        if token_id.is_empty() {
            return Err(ServiceError::InvalidConfiguration(
                "token ID cannot be empty".into(),
            ));
        }
        self.revoked
            .write()
            .await
            .insert(token_id.into(), expires_at_seconds);
        Ok(())
    }

    async fn is_revoked(&self, token_id: &str, now_seconds: u64) -> Result<bool, ServiceError> {
        let mut revoked = self.revoked.write().await;
        revoked.retain(|_, expiry| *expiry > now_seconds);
        Ok(revoked.contains_key(token_id))
    }
}

pub struct NativeJwtIdentityProvider {
    codec: HmacJwtCodec,
    revocations: Arc<dyn TokenRevocationStore>,
}

impl NativeJwtIdentityProvider {
    #[must_use]
    pub fn new(codec: HmacJwtCodec, revocations: Arc<dyn TokenRevocationStore>) -> Self {
        Self { codec, revocations }
    }

    async fn verified_claims(&self, token: &str) -> Result<Map<String, Value>, ServiceError> {
        let now = now_seconds();
        let claims = self
            .codec
            .verify(token, now)
            .map_err(|error| ServiceError::Unauthorized(error.to_string()))?;
        let token_id = claims
            .get("jti")
            .and_then(Value::as_str)
            .ok_or_else(|| ServiceError::Unauthorized("token ID is missing".into()))?;
        if self.revocations.is_revoked(token_id, now).await? {
            return Err(ServiceError::Unauthorized("token has been revoked".into()));
        }
        Ok(claims)
    }

    fn issue_user(&self, user: &AuthenticatedUser) -> Result<Value, ServiceError> {
        let user = serde_json::to_value(user)
            .map_err(|_| ServiceError::Operation("user token encoding failed".into()))?;
        let token = self
            .codec
            .issue(Map::from_iter([("user".into(), user)]), now_seconds())
            .map_err(|error| ServiceError::Operation(error.to_string()))?;
        Ok(json!({
            "token": token,
            "expires_in": self.codec.lifetime_seconds()
        }))
    }
}

#[async_trait]
impl IdentityTokenProvider for NativeJwtIdentityProvider {
    async fn issue(
        &self,
        user: &AuthenticatedUser,
        scopes: &BTreeSet<String>,
    ) -> Result<Value, ServiceError> {
        let mut scoped_user = user.clone();
        if !scopes.is_empty() {
            scoped_user.permissions.clone_from(scopes);
        }
        self.issue_user(&scoped_user)
    }

    async fn validate(&self, token: &str) -> Result<AuthenticatedUser, ServiceError> {
        let claims = self.verified_claims(token).await?;
        serde_json::from_value(
            claims
                .get("user")
                .cloned()
                .ok_or_else(|| ServiceError::Unauthorized("token user is missing".into()))?,
        )
        .map_err(|_| ServiceError::Unauthorized("token user is invalid".into()))
    }

    async fn refresh(&self, token: &str) -> Result<Value, ServiceError> {
        let user = self.validate(token).await?;
        let claims = self.verified_claims(token).await?;
        let token_id = claims
            .get("jti")
            .and_then(Value::as_str)
            .ok_or_else(|| ServiceError::Unauthorized("token ID is missing".into()))?;
        let expires = claims
            .get("exp")
            .and_then(Value::as_u64)
            .ok_or_else(|| ServiceError::Unauthorized("token expiry is missing".into()))?;
        self.revocations.revoke(token_id, expires).await?;
        self.issue_user(&user)
    }

    async fn revoke(&self, token: &str) -> Result<(), ServiceError> {
        let claims = self.verified_claims(token).await?;
        let token_id = claims
            .get("jti")
            .and_then(Value::as_str)
            .ok_or_else(|| ServiceError::Unauthorized("token ID is missing".into()))?;
        let expires = claims
            .get("exp")
            .and_then(Value::as_u64)
            .ok_or_else(|| ServiceError::Unauthorized("token expiry is missing".into()))?;
        self.revocations.revoke(token_id, expires).await
    }
}

fn now_seconds() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

fn now_millis() -> u64 {
    let millis = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis();
    u64::try_from(millis).unwrap_or(u64::MAX)
}

#[inline(never)]
fn constant_time_equal(left: &[u8], right: &[u8]) -> bool {
    if left.len() != right.len() {
        return false;
    }
    let mut difference = 0_u8;
    for (left, right) in left.iter().zip(right) {
        difference |= left ^ right;
    }
    difference == 0
}

#[cfg(test)]
mod tests {
    use mmf_security::AuthenticationMethod;
    use mmf_security::jwt_hmac::HmacJwtAlgorithm;

    use super::*;

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
            roles: BTreeSet::from(["issuer".into()]),
            permissions: BTreeSet::from(["credential:issue".into()]),
            session_id: None,
            auth_method: Some(AuthenticationMethod::Basic),
            expires_at_ms: None,
            created_at_ms: Some(1_000),
            attributes: BTreeMap::new(),
            user_type: None,
            applicant_id: None,
        }
    }

    #[tokio::test]
    async fn native_password_and_token_providers_round_trip_and_revoke() {
        let fixture = fixture();
        let passwords = NativeBasicAuthenticator::new(Arc::new(ScryptPasswordHashProvider));
        passwords
            .register(
                fixture["requests"]["username"].as_str().expect("username"),
                fixture["requests"]["password"]
                    .as_str()
                    .expect("password")
                    .as_bytes(),
                user(),
            )
            .await
            .expect("register");
        let authentication = passwords
            .authenticate(&AuthenticationRequest {
                scheme: "basic".into(),
                credential: "alex:Correct-Horse-42!".into(),
                metadata: BTreeMap::new(),
            })
            .await
            .expect("authenticate");
        assert!(authentication.success);
        assert!(
            !passwords
                .authenticate(&AuthenticationRequest {
                    scheme: "basic".into(),
                    credential: "alex:wrong".into(),
                    metadata: BTreeMap::new(),
                })
                .await
                .expect("authenticate")
                .success
        );

        let codec = HmacJwtCodec::new(
            b"0123456789abcdef0123456789abcdef",
            HmacJwtAlgorithm::HS256,
            "mmf",
            "services",
            3_600,
        )
        .expect("codec");
        let tokens = NativeJwtIdentityProvider::new(
            codec,
            Arc::new(InMemoryTokenRevocationStore::default()),
        );
        let value = tokens
            .issue(&user(), &BTreeSet::new())
            .await
            .expect("issue");
        let token = value["token"].as_str().expect("token");
        assert_eq!(
            tokens.validate(token).await.expect("validate").user_id,
            "user-123"
        );
        tokens.revoke(token).await.expect("revoke");
        assert!(tokens.validate(token).await.is_err());

        let api_keys = NativeApiKeyProvider::default();
        api_keys.register_user(user()).await.expect("register user");
        let created = api_keys
            .create(
                "user-123",
                Some("automation"),
                Some(now_millis() + 60_000),
                BTreeSet::from(["credential:issue".into()]),
            )
            .await
            .expect("create API key");
        let raw_key = created["api_key"].as_str().expect("raw API key");
        let key_id = created["key_id"].as_str().expect("key ID");
        assert_eq!(
            api_keys
                .authenticate(raw_key.as_bytes())
                .await
                .expect("authenticate API key")
                .user_id,
            "user-123"
        );
        assert_eq!(
            api_keys.metadata(key_id).await.expect("metadata")["key_name"],
            "automation"
        );
        api_keys.revoke(key_id).await.expect("revoke API key");
        assert!(api_keys.authenticate(raw_key.as_bytes()).await.is_err());
    }

    #[test]
    fn pre_upgrade_scrypt_vector_remains_verifiable() {
        // RFC 7914's first vector also freezes the persisted hash format across
        // scrypt crate upgrades. Existing password records must remain usable.
        let encoded = concat!(
            "$scrypt$4$1$1$$",
            "d9ZXYjhleyA7GcpCwYoEl_FrSETjB0ro39_6P-3iFEL80Aad7QlI-",
            "DJqdToPyB8X6NPg-y4NNijPNeIMONGJBg"
        );
        let hasher = ScryptPasswordHashProvider;

        assert!(hasher.verify(b"", encoded).expect("valid RFC vector"));
        assert!(!hasher.verify(b"not-empty", encoded).expect("valid hash"));
    }

    struct FastTestHasher;

    impl PasswordHashProvider for FastTestHasher {
        fn hash(&self, password: &[u8]) -> Result<String, ServiceError> {
            String::from_utf8(password.to_vec())
                .map_err(|_| ServiceError::Operation("test hash failed".into()))
        }

        fn verify(&self, password: &[u8], encoded: &str) -> Result<bool, ServiceError> {
            Ok(constant_time_equal(password, encoded.as_bytes()))
        }
    }

    #[tokio::test]
    async fn password_policy_attempt_limits_and_lockout_are_behavioral_and_fail_closed() {
        let fixture: Value = serde_json::from_str(include_str!(
            "../../../contracts/identity-service-configuration-behavior.json"
        ))
        .expect("valid configuration behavior fixture");
        let max_attempts = usize::try_from(
            fixture["password"]["max_login_attempts"]
                .as_u64()
                .expect("max attempts"),
        )
        .expect("usize attempts");
        let policy = NativePasswordPolicy {
            max_login_attempts: max_attempts,
            lockout_duration_ms: fixture["password"]["lockout_ms"].as_u64().expect("lockout"),
            ..NativePasswordPolicy::default()
        };
        let passwords = NativeBasicAuthenticator::with_policy(Arc::new(FastTestHasher), policy);
        passwords
            .register("alex", b"Correct-Horse-42!", user())
            .await
            .expect("register");
        for _ in 0..max_attempts {
            let rejected = passwords
                .authenticate(&AuthenticationRequest {
                    scheme: "basic".into(),
                    credential: "alex:wrong-password".into(),
                    metadata: BTreeMap::new(),
                })
                .await
                .expect("rejected");
            assert!(!rejected.success);
        }
        let locked = passwords
            .authenticate(&AuthenticationRequest {
                scheme: "basic".into(),
                credential: "alex:Correct-Horse-42!".into(),
                metadata: BTreeMap::new(),
            })
            .await
            .expect("locked");
        assert_eq!(locked.error_code.as_deref(), Some("ACCOUNT_LOCKED"));
        assert!(
            passwords
                .change("alex", b"Correct-Horse-42!", b"short")
                .await
                .is_err()
        );
    }
}
