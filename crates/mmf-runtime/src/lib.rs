//! Shared lifecycle, health, readiness, and version HTTP surface for MMF services.

#![forbid(unsafe_code)]

mod services;

pub use services::*;

use std::{
    collections::BTreeMap,
    sync::{Arc, RwLock},
};

use axum::{
    Json, Router,
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::get,
};
use mmf_core::{
    BuildInfo, ComponentHealth, ErrorCode, HealthReport, HealthStatus, LifecycleState, MmfError,
};
use serde::Serialize;

#[derive(Clone)]
pub struct RuntimeState {
    inner: Arc<RwLock<RuntimeInner>>,
}

struct RuntimeInner {
    build: BuildInfo,
    lifecycle: LifecycleState,
    components: BTreeMap<String, ComponentHealth>,
}

#[derive(Debug, Serialize)]
pub struct ReadinessReport {
    pub ready: bool,
    pub lifecycle: LifecycleState,
    pub health: HealthStatus,
}

impl RuntimeState {
    #[must_use]
    pub fn new(build: BuildInfo) -> Self {
        Self {
            inner: Arc::new(RwLock::new(RuntimeInner {
                build,
                lifecycle: LifecycleState::Created,
                components: BTreeMap::new(),
            })),
        }
    }

    pub fn transition(&self, next: LifecycleState) -> Result<(), MmfError> {
        self.inner
            .write()
            .map_err(|_| MmfError::new(ErrorCode::Internal, "runtime lock poisoned"))?
            .lifecycle
            .transition_to(next)
    }

    pub fn set_component_health(
        &self,
        name: impl Into<String>,
        health: ComponentHealth,
    ) -> Result<(), MmfError> {
        self.inner
            .write()
            .map_err(|_| MmfError::new(ErrorCode::Internal, "runtime lock poisoned"))?
            .components
            .insert(name.into(), health);
        Ok(())
    }

    pub fn health(&self) -> Result<HealthReport, MmfError> {
        let inner = self
            .inner
            .read()
            .map_err(|_| MmfError::new(ErrorCode::Internal, "runtime lock poisoned"))?;
        Ok(HealthReport::from_components(inner.components.clone()))
    }

    pub fn readiness(&self) -> Result<ReadinessReport, MmfError> {
        let inner = self
            .inner
            .read()
            .map_err(|_| MmfError::new(ErrorCode::Internal, "runtime lock poisoned"))?;
        let health = HealthReport::from_components(inner.components.clone()).status;
        Ok(ReadinessReport {
            ready: inner.lifecycle == LifecycleState::Active
                && matches!(health, HealthStatus::Healthy | HealthStatus::Degraded),
            lifecycle: inner.lifecycle,
            health,
        })
    }

    pub fn build_info(&self) -> Result<BuildInfo, MmfError> {
        self.inner
            .read()
            .map(|inner| inner.build.clone())
            .map_err(|_| MmfError::new(ErrorCode::Internal, "runtime lock poisoned"))
    }
}

pub fn system_router(state: RuntimeState) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/ready", get(readiness))
        .route("/version", get(version))
        .with_state(state)
}

async fn health(State(state): State<RuntimeState>) -> Response {
    match state.health() {
        Ok(report) => {
            let status = if report.status == HealthStatus::Unhealthy {
                StatusCode::SERVICE_UNAVAILABLE
            } else {
                StatusCode::OK
            };
            (status, Json(report)).into_response()
        }
        Err(error) => internal_error(error),
    }
}

async fn readiness(State(state): State<RuntimeState>) -> Response {
    match state.readiness() {
        Ok(report) => {
            let status = if report.ready {
                StatusCode::OK
            } else {
                StatusCode::SERVICE_UNAVAILABLE
            };
            (status, Json(report)).into_response()
        }
        Err(error) => internal_error(error),
    }
}

async fn version(State(state): State<RuntimeState>) -> Response {
    match state.build_info() {
        Ok(build) => (StatusCode::OK, Json(build)).into_response(),
        Err(error) => internal_error(error),
    }
}

fn internal_error(error: MmfError) -> Response {
    (StatusCode::INTERNAL_SERVER_ERROR, Json(error)).into_response()
}

#[cfg(test)]
mod tests {
    use axum::{body::Body, http::Request};
    use http_body_util::BodyExt;
    use mmf_core::{BuildInfo, ComponentHealth, HealthStatus, LifecycleState};
    use serde_json::Value;
    use tower::ServiceExt;

    use super::{RuntimeState, system_router};

    fn runtime() -> RuntimeState {
        RuntimeState::new(BuildInfo {
            service: "contract-service".to_owned(),
            version: "1.2.3".to_owned(),
            build_revision: "abc123".to_owned(),
            enabled_features: vec!["http".to_owned()],
        })
    }

    #[tokio::test]
    async fn readiness_fails_closed_until_active_and_healthy() {
        let state = runtime();
        let router = system_router(state.clone());
        let unavailable = router
            .clone()
            .oneshot(Request::get("/ready").body(Body::empty()).expect("request"))
            .await
            .expect("response");
        assert_eq!(unavailable.status(), 503);

        state
            .transition(LifecycleState::Initialized)
            .expect("initialize");
        state.transition(LifecycleState::Starting).expect("start");
        state.transition(LifecycleState::Active).expect("active");
        state
            .set_component_health(
                "database",
                ComponentHealth {
                    status: HealthStatus::Healthy,
                    message: None,
                },
            )
            .expect("health");

        let available = router
            .oneshot(Request::get("/ready").body(Body::empty()).expect("request"))
            .await
            .expect("response");
        assert_eq!(available.status(), 200);
        let body: Value = serde_json::from_slice(
            &available
                .into_body()
                .collect()
                .await
                .expect("body")
                .to_bytes(),
        )
        .expect("json");
        assert_eq!(body["ready"], true);
        assert_eq!(body["lifecycle"], "active");
    }
}
