use std::collections::{BTreeMap, BTreeSet};

use async_trait::async_trait;
use serde::{Deserialize, Serialize};

use crate::{
    AuthenticationResult, AuthorizationDecision, RateLimitQuota, RateLimitResult, RateLimitRule,
    SecurityContext, SecurityError, SessionData,
};

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum KmsProviderType {
    Aws,
    Azure,
    Gcp,
    Vault,
    OpenBao,
    Pkcs11,
    Remote,
    Test,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum KeyAlgorithm {
    Ed25519,
    Es256,
    Es384,
    Rsa2048,
    Rsa3072,
    Rsa4096,
    Aes128Gcm,
    Aes256Gcm,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum KeyOperation {
    Sign,
    Verify,
    Encrypt,
    Decrypt,
    Wrap,
    Unwrap,
    Derive,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct KeyMetadata {
    pub key_id: String,
    pub algorithm: KeyAlgorithm,
    pub provider: KmsProviderType,
    pub operations: BTreeSet<KeyOperation>,
    pub created_at_ms: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub expires_at_ms: Option<u64>,
    #[serde(default)]
    pub labels: BTreeMap<String, String>,
    #[serde(default)]
    pub public_key: Vec<u8>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct SignatureRequest {
    pub key_id: String,
    pub algorithm: KeyAlgorithm,
    pub message: Vec<u8>,
    #[serde(default)]
    pub context: BTreeMap<String, String>,
}

#[async_trait]
pub trait KmsProvider: Send + Sync {
    async fn create_key(
        &self,
        algorithm: KeyAlgorithm,
        operations: BTreeSet<KeyOperation>,
        labels: BTreeMap<String, String>,
    ) -> Result<KeyMetadata, SecurityError>;
    async fn metadata(&self, key_id: &str) -> Result<KeyMetadata, SecurityError>;
    async fn sign(&self, request: SignatureRequest) -> Result<Vec<u8>, SecurityError>;
    async fn verify(
        &self,
        request: SignatureRequest,
        signature: &[u8],
    ) -> Result<bool, SecurityError>;
    async fn encrypt(&self, key_id: &str, plaintext: &[u8]) -> Result<Vec<u8>, SecurityError>;
    async fn decrypt(&self, key_id: &str, ciphertext: &[u8]) -> Result<Vec<u8>, SecurityError>;
    async fn rotate(&self, key_id: &str) -> Result<KeyMetadata, SecurityError>;
    async fn disable(&self, key_id: &str) -> Result<(), SecurityError>;
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct AuthenticationRequest {
    pub scheme: String,
    #[serde(skip_serializing)]
    pub credential: String,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
}

#[async_trait]
pub trait Authenticator: Send + Sync {
    async fn authenticate(
        &self,
        request: &AuthenticationRequest,
    ) -> Result<AuthenticationResult, SecurityError>;
}

#[async_trait]
pub trait IdentityProvider: Send + Sync {
    async fn authorization_url(
        &self,
        state: &str,
        redirect_uri: &str,
    ) -> Result<String, SecurityError>;
    async fn exchange_code(
        &self,
        code: &str,
        redirect_uri: &str,
    ) -> Result<AuthenticationResult, SecurityError>;
    async fn refresh(&self, refresh_token: &str) -> Result<AuthenticationResult, SecurityError>;
    async fn revoke(&self, token: &str) -> Result<(), SecurityError>;
}

#[async_trait]
pub trait PolicyProvider: Send + Sync {
    async fn authorize(
        &self,
        context: &SecurityContext,
    ) -> Result<AuthorizationDecision, SecurityError>;
}

#[async_trait]
pub trait SessionStore: Send + Sync {
    async fn create(&self, session: SessionData) -> Result<(), SecurityError>;
    async fn get(&self, session_id: &str) -> Result<Option<SessionData>, SecurityError>;
    async fn replace(&self, session: SessionData) -> Result<(), SecurityError>;
    async fn delete(&self, session_id: &str) -> Result<(), SecurityError>;
    async fn list_for_user(&self, user_id: &str) -> Result<Vec<SessionData>, SecurityError>;
}

#[async_trait]
pub trait DistributedRateLimiter: Send + Sync {
    async fn check(
        &self,
        rule: &RateLimitRule,
        quota: &RateLimitQuota,
        now_ms: u64,
    ) -> Result<RateLimitResult, SecurityError>;
}

#[async_trait]
pub trait SecretManager: Send + Sync {
    async fn get(&self, key: &str) -> Result<Vec<u8>, SecurityError>;
    async fn put(&self, key: &str, value: &[u8]) -> Result<(), SecurityError>;
    async fn delete(&self, key: &str) -> Result<(), SecurityError>;
    async fn rotate(&self, key: &str) -> Result<(), SecurityError>;
}
