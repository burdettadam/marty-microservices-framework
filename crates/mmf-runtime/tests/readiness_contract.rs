use mmf_core::{BuildInfo, ComponentHealth, ErrorCode, HealthStatus, LifecycleState};
use mmf_runtime::RuntimeState;
use serde::Deserialize;

#[derive(Deserialize)]
struct Contract {
    schema_version: u32,
    required_initial_status: String,
    activation_requirement: String,
    live_readiness_requirement: String,
    required_degraded_is_ready: bool,
    optional_degraded_is_ready: bool,
    component_name_bytes: Vec<usize>,
    failure_code: String,
    failure_detail: String,
    failure_order: String,
}

#[test]
fn language_neutral_required_readiness_contract() {
    let contract: Contract =
        serde_json::from_str(include_str!("../../../contracts/runtime-readiness.json"))
            .expect("contract");
    assert_eq!(contract.schema_version, 1);
    assert_eq!(contract.required_initial_status, "unknown");
    assert_eq!(contract.activation_requirement, "all_required_healthy");
    assert_eq!(contract.live_readiness_requirement, "all_required_healthy");
    assert!(!contract.required_degraded_is_ready);
    assert!(contract.optional_degraded_is_ready);
    assert_eq!(contract.component_name_bytes, [1, 128]);
    assert_eq!(contract.failure_code, "dependency_unavailable");
    assert_eq!(contract.failure_detail, "components");
    assert_eq!(contract.failure_order, "lexicographic");

    let state = RuntimeState::new(BuildInfo {
        service: "contract".into(),
        version: "1".into(),
        build_revision: "test".into(),
        enabled_features: Vec::new(),
    });
    state.register_required_component("zeta").expect("zeta");
    state.register_required_component("alpha").expect("alpha");
    state
        .transition(LifecycleState::Initialized)
        .expect("initialize");
    state.transition(LifecycleState::Starting).expect("start");
    let error = state
        .transition(LifecycleState::Active)
        .expect_err("must fail closed");
    assert_eq!(error.code, ErrorCode::DependencyUnavailable);
    assert_eq!(error.details["components"], "alpha,zeta");

    for component in ["alpha", "zeta"] {
        state
            .set_component_health(
                component,
                ComponentHealth {
                    status: HealthStatus::Healthy,
                    message: None,
                },
            )
            .expect("health");
    }
    state.transition(LifecycleState::Active).expect("active");
    assert!(state.readiness().expect("readiness").ready);
}
