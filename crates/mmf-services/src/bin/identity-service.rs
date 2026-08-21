use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::error::Error;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use mmf_security::jwt_hmac::{HmacJwtAlgorithm, HmacJwtCodec};
use mmf_security::{AuthenticatedUser, AuthenticationMethod};
use mmf_services::identity::{
    ApiKeyProvider, AuthenticationManager, IdentityProviders, IdentityTokenProvider,
    PasswordProvider,
};
use mmf_services::identity_http::{
    IdentityHttpPolicy, IdentityHttpState, MmfPluginDiagnostics, identity_router,
};
use mmf_services::native_identity::{
    InMemoryTokenRevocationStore, NativeApiKeyProvider, NativeBasicAuthenticator,
    NativeJwtIdentityProvider, ScryptPasswordHashProvider,
};

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let environment = env::var("MMF_ENVIRONMENT").unwrap_or_else(|_| "development".into());
    let production = environment.eq_ignore_ascii_case("production");
    let jwt_key = required_or_development_default(
        "MMF_JWT_KEY",
        "development-only-jwt-key-change-me",
        production,
    )?;
    let admin_password =
        required_or_development_default("MMF_ADMIN_PASSWORD", "admin123", production)?;
    let admin_username = env::var("MMF_ADMIN_USERNAME").unwrap_or_else(|_| "admin".into());
    let issuer = env::var("MMF_JWT_ISSUER").unwrap_or_else(|_| "marty-microservices".into());
    let audience = env::var("MMF_JWT_AUDIENCE").unwrap_or_else(|_| "marty-services".into());
    let bind = env::var("MMF_BIND").unwrap_or_else(|_| "0.0.0.0:8000".into());

    let admin = AuthenticatedUser {
        user_id: "user_admin".into(),
        username: Some(admin_username.clone()),
        email: Some("admin@example.com".into()),
        roles: BTreeSet::from(["administrator".into()]),
        permissions: BTreeSet::from(["*".into()]),
        session_id: None,
        auth_method: Some(AuthenticationMethod::Basic),
        expires_at_ms: None,
        created_at_ms: Some(now_millis()),
        attributes: BTreeMap::new(),
        user_type: Some("administrator".into()),
        applicant_id: None,
    };

    let basic = Arc::new(NativeBasicAuthenticator::new(Arc::new(
        ScryptPasswordHashProvider,
    )));
    basic
        .register_seed_user(&admin_username, admin_password.as_bytes(), admin.clone())
        .await?;
    let api_keys = Arc::new(NativeApiKeyProvider::default());
    api_keys.register_user(admin.clone()).await?;
    let codec = HmacJwtCodec::new(
        jwt_key.as_bytes(),
        HmacJwtAlgorithm::HS256,
        issuer,
        audience,
        3_600,
    )?;
    let tokens = Arc::new(NativeJwtIdentityProvider::new(
        codec,
        Arc::new(InMemoryTokenRevocationStore::default()),
    ));

    let manager = Arc::new(AuthenticationManager::default());
    manager
        .register(AuthenticationMethod::Basic, basic.clone())
        .await;
    let password: Arc<dyn PasswordProvider> = basic;
    let api_key: Arc<dyn ApiKeyProvider> = api_keys;
    let token: Arc<dyn IdentityTokenProvider> = tokens;
    let app = identity_router(IdentityHttpState {
        manager,
        providers: Arc::new(IdentityProviders {
            token: Some(token),
            password: Some(password),
            api_key: Some(api_key),
            mutual_tls: None,
            mfa: None,
            sessions: None,
            federated: BTreeMap::new(),
        }),
        policy: IdentityHttpPolicy::default(),
        plugins: Some(Arc::new(MmfPluginDiagnostics::new(Arc::new(
            mmf_plugins::PluginManager::default(),
        )))),
    });
    let listener = tokio::net::TcpListener::bind(&bind).await?;
    axum::serve(listener, app).await?;
    Ok(())
}

fn required_or_development_default(
    name: &str,
    development_default: &str,
    production: bool,
) -> Result<String, Box<dyn Error>> {
    match env::var(name) {
        Ok(value) if !value.trim().is_empty() => Ok(value),
        _ if production => Err(format!("{name} is required in production").into()),
        _ => Ok(development_default.into()),
    }
}

fn now_millis() -> u64 {
    let millis = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis();
    u64::try_from(millis).unwrap_or(u64::MAX)
}
