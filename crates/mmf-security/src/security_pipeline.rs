//! Provider-neutral request security pipeline replacing the legacy Python coordinator.

use std::collections::BTreeMap;
use std::sync::Arc;

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::session_manager::{SessionManager, SessionRequestContext, SessionRequestErrorCode};
use crate::{
    AuditEvent, Auditor, AuthenticatedUser, AuthenticationMethod, AuthenticationRequest,
    Authenticator, AuthorizationDecision, DistributedRateLimiter, PolicyProvider, PrincipalType,
    RateLimitQuota, RateLimitResult, RateLimitRule, SecurityContext, SecurityError,
    SecurityPrincipal, generate_event_id,
};

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SecurityPipelineRequest {
    pub session: SessionRequestContext,
    pub authentication: Option<AuthenticationRequest>,
    pub rate_quota: RateLimitQuota,
    pub resource: String,
    pub action: String,
    #[serde(default)]
    pub resource_attributes: BTreeMap<String, Value>,
    #[serde(default)]
    pub environment: BTreeMap<String, Value>,
    #[serde(default)]
    pub request_metadata: BTreeMap<String, Value>,
    pub request_id: Option<String>,
    pub require_authentication: bool,
    pub require_authorization: bool,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SecurityPipelineResult {
    pub user: Option<AuthenticatedUser>,
    pub session_id: Option<String>,
    pub rate_limit: Option<RateLimitResult>,
    pub authorization: Option<AuthorizationDecision>,
    pub security_headers: BTreeMap<String, String>,
    pub execution_order: Vec<String>,
}

#[derive(Default)]
pub struct SecurityPipelineProviders {
    pub sessions: Option<Arc<SessionManager>>,
    pub authenticator: Option<Arc<dyn Authenticator>>,
    pub rate_limiter: Option<Arc<dyn DistributedRateLimiter>>,
    pub policy: Option<Arc<dyn PolicyProvider>>,
    pub auditor: Option<Arc<dyn Auditor>>,
}

pub struct SecurityPipeline {
    providers: SecurityPipelineProviders,
    rate_rule: Option<RateLimitRule>,
    session_cookie_name: String,
    session_header_name: String,
}

impl SecurityPipeline {
    pub fn new(
        providers: SecurityPipelineProviders,
        rate_rule: Option<RateLimitRule>,
        session_cookie_name: impl Into<String>,
        session_header_name: impl Into<String>,
    ) -> Result<Self, SecurityError> {
        if let Some(rule) = &rate_rule {
            rule.validate()?;
            if providers.rate_limiter.is_none() {
                return Err(SecurityError::RequiredProvidersUnavailable(vec![
                    "distributed_rate_limiter",
                ]));
            }
        }
        let session_cookie_name = session_cookie_name.into();
        let session_header_name = session_header_name.into();
        if session_cookie_name.trim().is_empty() || session_header_name.trim().is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "session cookie and header names cannot be empty".into(),
            ));
        }
        Ok(Self {
            providers,
            rate_rule,
            session_cookie_name,
            session_header_name,
        })
    }

    #[allow(clippy::too_many_lines)]
    pub async fn process(
        &self,
        request: &SecurityPipelineRequest,
    ) -> Result<SecurityPipelineResult, SecurityError> {
        let mut execution_order = Vec::new();
        let rate_limit = if let Some(rule) = &self.rate_rule {
            execution_order.push("rate_limit".into());
            let limiter = self.providers.rate_limiter.as_ref().ok_or_else(|| {
                SecurityError::RequiredProvidersUnavailable(vec!["distributed_rate_limiter"])
            })?;
            let result = limiter
                .check(rule, &request.rate_quota, request.session.now_ms)
                .await?;
            if !result.allowed {
                return Err(SecurityError::RateLimitExceeded);
            }
            Some(result)
        } else {
            None
        };

        execution_order.push("session".into());
        let session = match &self.providers.sessions {
            Some(manager) => manager
                .resolve_request(
                    &request.session,
                    &self.session_cookie_name,
                    &self.session_header_name,
                )
                .await
                .map_err(map_session_error)?,
            None if request.session.require_session => {
                return Err(SecurityError::RequiredProvidersUnavailable(vec![
                    "session_manager",
                ]));
            }
            None => None,
        };

        execution_order.push("authentication".into());
        let user = if let Some(session) = &session {
            Some(AuthenticatedUser {
                user_id: session.user_id.clone(),
                username: None,
                email: None,
                roles: session.roles.clone(),
                permissions: session.permissions.clone(),
                session_id: Some(session.session_id.clone()),
                auth_method: Some(AuthenticationMethod::Session),
                expires_at_ms: Some(session.expires_at_ms),
                created_at_ms: Some(session.created_at_ms),
                attributes: session.data.attributes.clone(),
                user_type: None,
                applicant_id: None,
            })
        } else if let Some(authentication) = &request.authentication {
            let authenticator = self.providers.authenticator.as_ref().ok_or_else(|| {
                SecurityError::RequiredProvidersUnavailable(vec!["authenticator"])
            })?;
            let result = authenticator.authenticate(authentication).await?;
            result.validate()?;
            if !result.success {
                return Err(SecurityError::Authentication(
                    result
                        .error
                        .unwrap_or_else(|| "authentication failed".into()),
                ));
            }
            result.user
        } else if request.require_authentication {
            return Err(SecurityError::Authentication(
                "authentication credentials are required".into(),
            ));
        } else {
            None
        };

        execution_order.push("authorization".into());
        let authorization = if request.require_authorization {
            let user = user.as_ref().ok_or_else(|| {
                SecurityError::Authorization("authorization requires an identity".into())
            })?;
            let policy = self.providers.policy.as_ref().ok_or_else(|| {
                SecurityError::RequiredProvidersUnavailable(vec!["policy_provider"])
            })?;
            let decision = policy
                .authorize(&SecurityContext {
                    principal: principal(user),
                    resource: request.resource.clone(),
                    action: request.action.clone(),
                    resource_attributes: request.resource_attributes.clone(),
                    environment: request.environment.clone(),
                    request_metadata: request.request_metadata.clone(),
                    request_id: request.request_id.clone(),
                    timestamp_ms: request.session.now_ms,
                })
                .await?;
            if !decision.allowed {
                return Err(SecurityError::Authorization(decision.reason));
            }
            Some(decision)
        } else {
            None
        };

        Ok(SecurityPipelineResult {
            session_id: session.map(|value| value.session_id),
            user,
            rate_limit,
            authorization,
            security_headers: security_headers(),
            execution_order,
        })
    }

    pub async fn health_check(&self) -> BTreeMap<String, String> {
        let mut components = BTreeMap::new();
        components.insert(
            "rate_limiter".into(),
            if self.rate_rule.is_none() || self.providers.rate_limiter.is_some() {
                "ok"
            } else {
                "unavailable"
            }
            .into(),
        );
        let session_status = match &self.providers.sessions {
            Some(manager) if manager.health_check().await.is_ok() => "ok",
            Some(_) => "unavailable",
            None => "disabled",
        };
        components.insert("session_manager".into(), session_status.into());
        components.insert(
            "authenticator".into(),
            if self.providers.authenticator.is_some() {
                "ok"
            } else {
                "unavailable"
            }
            .into(),
        );
        components.insert(
            "policy_provider".into(),
            if self.providers.policy.is_some() {
                "ok"
            } else {
                "unavailable"
            }
            .into(),
        );
        components.insert(
            "auditor".into(),
            if self.providers.auditor.is_some() {
                "ok"
            } else {
                "disabled"
            }
            .into(),
        );
        components
    }

    /// Record a normalized security event through the configured native audit provider.
    pub async fn record_security_event(
        &self,
        event_type: impl Into<String>,
        request: &SecurityPipelineRequest,
        outcome: impl Into<String>,
        details: BTreeMap<String, Value>,
    ) -> Result<(), SecurityError> {
        let auditor = self
            .providers
            .auditor
            .as_ref()
            .ok_or_else(|| SecurityError::RequiredProvidersUnavailable(vec!["auditor"]))?;
        auditor
            .record(AuditEvent {
                event_id: generate_event_id(),
                event_type: event_type.into(),
                timestamp_ms: request.session.now_ms,
                actor_id: request.rate_quota.user_id.clone(),
                action: request.action.clone(),
                resource: request.resource.clone(),
                outcome: outcome.into(),
                request_id: request.request_id.clone(),
                source_ip: request
                    .session
                    .security_context
                    .as_ref()
                    .map(|context| context.ip_address.clone()),
                details,
            })
            .await
    }
}

#[must_use]
pub fn security_headers() -> BTreeMap<String, String> {
    BTreeMap::from([
        ("X-Content-Type-Options".into(), "nosniff".into()),
        ("X-Frame-Options".into(), "DENY".into()),
        ("X-XSS-Protection".into(), "1; mode=block".into()),
        (
            "Strict-Transport-Security".into(),
            "max-age=31536000; includeSubDomains".into(),
        ),
    ])
}

fn principal(user: &AuthenticatedUser) -> SecurityPrincipal {
    SecurityPrincipal {
        id: user.user_id.clone(),
        principal_type: PrincipalType::User,
        roles: user.roles.clone(),
        permissions: user.permissions.clone(),
        attributes: user.attributes.clone(),
        identity_provider: user
            .auth_method
            .map(|method| format!("{method:?}").to_lowercase()),
        session_id: user.session_id.clone(),
        expires_at_ms: user.expires_at_ms,
    }
}

fn map_session_error(error: crate::session_manager::SessionRequestError) -> SecurityError {
    match error.code {
        SessionRequestErrorCode::SessionRequired
        | SessionRequestErrorCode::SessionInvalid
        | SessionRequestErrorCode::SessionContextMismatch => {
            SecurityError::Unauthorized(error.message)
        }
        SessionRequestErrorCode::BackendUnavailable => {
            SecurityError::ProviderUnavailable(error.message)
        }
    }
}

#[cfg(test)]
mod tests {
    use async_trait::async_trait;
    use tokio::sync::Mutex;

    use super::*;
    use crate::{AuthenticationResult, RateLimitScope, RateLimitStrategy};

    struct AllowAuthenticator;

    #[async_trait]
    impl Authenticator for AllowAuthenticator {
        async fn authenticate(
            &self,
            _request: &AuthenticationRequest,
        ) -> Result<AuthenticationResult, SecurityError> {
            Ok(AuthenticationResult {
                success: true,
                user: Some(AuthenticatedUser {
                    user_id: "user-123".into(),
                    username: Some("alex".into()),
                    email: None,
                    roles: ["issuer".into()].into_iter().collect(),
                    permissions: ["credential:issue".into()].into_iter().collect(),
                    session_id: None,
                    auth_method: Some(AuthenticationMethod::Jwt),
                    expires_at_ms: Some(10_000),
                    created_at_ms: Some(1_000),
                    attributes: BTreeMap::new(),
                    user_type: None,
                    applicant_id: None,
                }),
                error: None,
                error_code: None,
                metadata: BTreeMap::new(),
            })
        }
    }

    struct AllowRateLimiter;

    #[async_trait]
    impl DistributedRateLimiter for AllowRateLimiter {
        async fn check(
            &self,
            rule: &RateLimitRule,
            _quota: &RateLimitQuota,
            now_ms: u64,
        ) -> Result<RateLimitResult, SecurityError> {
            Ok(RateLimitResult {
                allowed: true,
                rule_name: rule.name.clone(),
                current_count: 1,
                limit: rule.limit,
                remaining: rule.limit.saturating_sub(1),
                reset_at_ms: now_ms.saturating_add(rule.window_ms),
                retry_after_ms: 0,
            })
        }
    }

    struct AllowPolicy;

    #[async_trait]
    impl PolicyProvider for AllowPolicy {
        async fn authorize(
            &self,
            context: &SecurityContext,
        ) -> Result<AuthorizationDecision, SecurityError> {
            if context.principal.permissions.contains("credential:issue") {
                Ok(AuthorizationDecision::allow(
                    "fixture policy",
                    vec!["fixture".into()],
                ))
            } else {
                Ok(AuthorizationDecision::deny(
                    "missing permission",
                    vec!["fixture".into()],
                ))
            }
        }
    }

    #[derive(Default)]
    struct RecordingAuditor {
        events: Mutex<Vec<AuditEvent>>,
    }

    #[async_trait]
    impl Auditor for RecordingAuditor {
        async fn record(&self, event: AuditEvent) -> Result<(), SecurityError> {
            self.events.lock().await.push(event);
            Ok(())
        }
    }

    fn fixture() -> Value {
        serde_json::from_str(include_str!(
            "../../../contracts/session-platform-behavior.json"
        ))
        .expect("valid session platform fixture")
    }

    fn rule() -> RateLimitRule {
        RateLimitRule {
            name: "api".into(),
            scope: RateLimitScope::PerUser,
            strategy: RateLimitStrategy::FixedWindow,
            limit: 10,
            window_ms: 60_000,
            burst_size: 0,
            enabled: true,
        }
    }

    #[tokio::test]
    async fn pipeline_preserves_order_headers_authentication_and_authorization() {
        let fixture = fixture();
        let pipeline = SecurityPipeline::new(
            SecurityPipelineProviders {
                sessions: None,
                authenticator: Some(Arc::new(AllowAuthenticator)),
                rate_limiter: Some(Arc::new(AllowRateLimiter)),
                policy: Some(Arc::new(AllowPolicy)),
                auditor: None,
            },
            Some(rule()),
            "session_id",
            "x-session-id",
        )
        .expect("pipeline");
        let result = pipeline
            .process(&SecurityPipelineRequest {
                session: SessionRequestContext {
                    action: "request".into(),
                    now_ms: 2_000,
                    ..SessionRequestContext::default()
                },
                authentication: Some(AuthenticationRequest {
                    scheme: "bearer".into(),
                    credential: "fixture.jwt.token".into(),
                    metadata: BTreeMap::new(),
                }),
                rate_quota: RateLimitQuota {
                    user_id: Some("user-123".into()),
                    ..RateLimitQuota::default()
                },
                resource: fixture["pipeline"]["resource"]
                    .as_str()
                    .expect("resource")
                    .into(),
                action: fixture["pipeline"]["action"]
                    .as_str()
                    .expect("action")
                    .into(),
                resource_attributes: BTreeMap::new(),
                environment: BTreeMap::new(),
                request_metadata: BTreeMap::new(),
                request_id: Some("request-1".into()),
                require_authentication: true,
                require_authorization: true,
            })
            .await
            .expect("pipeline result");
        assert_eq!(result.user.expect("user").user_id, "user-123");
        assert!(result.authorization.expect("decision").allowed);
        assert_eq!(
            serde_json::to_value(&result.security_headers).expect("headers"),
            fixture["pipeline"]["security_headers"]
        );
        assert_eq!(
            serde_json::to_value(&result.execution_order).expect("order"),
            fixture["pipeline"]["execution_order"]
        );
    }

    #[test]
    fn configured_effects_require_native_providers() {
        assert!(
            SecurityPipeline::new(
                SecurityPipelineProviders::default(),
                Some(rule()),
                "session_id",
                "x-session-id",
            )
            .is_err()
        );
        assert!(
            SecurityPipeline::new(
                SecurityPipelineProviders::default(),
                None,
                "",
                "x-session-id",
            )
            .is_err()
        );
    }

    #[tokio::test]
    async fn security_events_use_the_native_auditor_and_missing_auditors_fail_closed() {
        let request = SecurityPipelineRequest {
            session: SessionRequestContext {
                security_context: Some(crate::SessionSecurityContext {
                    ip_address: "192.0.2.10".into(),
                    user_agent: None,
                    secure_connection: true,
                    client_fingerprint: None,
                    location_info: BTreeMap::new(),
                    created_at_ms: 2_000,
                }),
                now_ms: 2_000,
                ..SessionRequestContext::default()
            },
            authentication: None,
            rate_quota: RateLimitQuota {
                user_id: Some("user-123".into()),
                ..RateLimitQuota::default()
            },
            resource: "credentials/123".into(),
            action: "issue".into(),
            resource_attributes: BTreeMap::new(),
            environment: BTreeMap::new(),
            request_metadata: BTreeMap::new(),
            request_id: Some("request-1".into()),
            require_authentication: false,
            require_authorization: false,
        };
        let missing = SecurityPipeline::new(
            SecurityPipelineProviders::default(),
            None,
            "session_id",
            "x-session-id",
        )
        .expect("pipeline");
        assert!(
            missing
                .record_security_event("request", &request, "allowed", BTreeMap::new())
                .await
                .is_err()
        );

        let auditor = Arc::new(RecordingAuditor::default());
        let pipeline = SecurityPipeline::new(
            SecurityPipelineProviders {
                auditor: Some(auditor.clone()),
                ..SecurityPipelineProviders::default()
            },
            None,
            "session_id",
            "x-session-id",
        )
        .expect("pipeline");
        pipeline
            .record_security_event(
                "request",
                &request,
                "allowed",
                BTreeMap::from([("policy".into(), Value::String("fixture".into()))]),
            )
            .await
            .expect("audit event");
        let events = auditor.events.lock().await;
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].actor_id.as_deref(), Some("user-123"));
        assert_eq!(events[0].source_ip.as_deref(), Some("192.0.2.10"));
        assert_eq!(events[0].request_id.as_deref(), Some("request-1"));
    }
}
