use std::collections::{BTreeMap, BTreeSet};
use std::sync::{Arc, Mutex};

use async_trait::async_trait;
use mmf_testkit::*;
use serde_json::{Value, json};

fn fixture() -> Value {
    serde_json::from_str(include_str!("../../../contracts/testkit-behavior.json"))
        .expect("valid testkit fixture")
}

#[test]
fn performance_metrics_and_load_patterns_match_contract() {
    let fixture = fixture();
    let case = &fixture["metrics"];
    let mut collector = MetricsCollector::default();
    for response in case["responses"].as_array().unwrap() {
        collector.record(ResponseMetric {
            started_at_ms: 0,
            duration_ms: response["duration_ms"].as_u64().unwrap(),
            status_code: response["status_code"]
                .as_u64()
                .and_then(|value| u16::try_from(value).ok()),
            bytes: response["bytes"].as_u64().unwrap(),
            error: response["error"].as_str().map(ToOwned::to_owned),
        });
    }
    let metrics = collector.aggregate(case["elapsed_ms"].as_u64().unwrap());
    assert_eq!(metrics.total_requests, case["total"]);
    assert_eq!(metrics.successful_requests, case["successful"]);
    assert_eq!(metrics.failed_requests, case["failed"]);
    assert!((metrics.mean_response_ms - case["mean_ms"].as_f64().unwrap()).abs() < f64::EPSILON);
    assert!((metrics.p50_response_ms - case["p50_ms"].as_f64().unwrap()).abs() < f64::EPSILON);
    assert!((metrics.p95_response_ms - case["p95_ms"].as_f64().unwrap()).abs() < f64::EPSILON);
    assert!((metrics.p99_response_ms - case["p99_ms"].as_f64().unwrap()).abs() < f64::EPSILON);
    assert!((metrics.error_rate - case["error_rate"].as_f64().unwrap()).abs() < f64::EPSILON);

    let load = &fixture["load_patterns"];
    let base = LoadConfiguration {
        pattern: LoadPattern::RampUp,
        users: u32::try_from(load["users"].as_u64().unwrap()).unwrap(),
        duration_ms: load["duration_ms"].as_u64().unwrap(),
        ramp_up_ms: load["duration_ms"].as_u64().unwrap(),
        requests_per_second: None,
        think_time_min_ms: 0,
        think_time_max_ms: 0,
        step_users: 10,
        step_interval_ms: 1_000,
        spike_users: 500,
    };
    for vector in load["ramp_at_ms"].as_array().unwrap() {
        assert_eq!(
            base.users_at(vector[0].as_u64().unwrap()),
            u32::try_from(vector[1].as_u64().unwrap()).unwrap()
        );
    }
    let spike = LoadConfiguration {
        pattern: LoadPattern::Spike,
        ..base
    };
    for vector in load["spike_at_ms"].as_array().unwrap() {
        assert_eq!(
            spike.users_at(vector[0].as_u64().unwrap()),
            u32::try_from(vector[1].as_u64().unwrap()).unwrap()
        );
    }
}

#[test]
fn contract_levels_and_fault_schedule_are_deterministic() {
    let case = &fixture()["contract"];
    let expected = ContractResponse {
        status_code: 200,
        headers: BTreeMap::new(),
        body: case["expected_body"].clone(),
    };
    let mut actual_body = case["expected_body"].as_object().unwrap().clone();
    actual_body.extend(case["extra_body"].as_object().unwrap().clone());
    let actual = ContractResponse {
        status_code: 200,
        headers: BTreeMap::new(),
        body: Value::Object(actual_body),
    };
    assert_eq!(
        verify_response(&expected, &actual, VerificationLevel::Lenient).len(),
        0
    );
    assert_eq!(
        verify_response(&expected, &actual, VerificationLevel::Strict).len(),
        1
    );
    let missing = ContractResponse {
        status_code: 200,
        headers: BTreeMap::new(),
        body: json!({"id": "123"}),
    };
    assert_eq!(
        verify_response(&expected, &missing, VerificationLevel::Standard).len(),
        1
    );

    let fault = &fixture()["faults"];
    let mut injector = FaultInjector::default();
    injector
        .add(FaultRule {
            operation: fault["operation"].as_str().unwrap().to_owned(),
            fail_on_calls: fault["fail_on_calls"]
                .as_array()
                .unwrap()
                .iter()
                .map(|value| value.as_u64().unwrap())
                .collect::<BTreeSet<_>>(),
            error: "planned".to_owned(),
        })
        .unwrap();
    let actual = (0..5)
        .map(|_| injector.check(fault["operation"].as_str().unwrap()).is_ok())
        .collect::<Vec<_>>();
    let expected = fault["results"]
        .as_array()
        .unwrap()
        .iter()
        .map(|value| value.as_bool().unwrap())
        .collect::<Vec<_>>();
    assert_eq!(actual, expected);
}

#[derive(Default)]
struct RecordingChaosProvider {
    calls: Mutex<Vec<String>>,
}

#[async_trait]
impl ChaosProvider for RecordingChaosProvider {
    async fn inject(
        &self,
        _chaos_type: ChaosType,
        _targets: &[ChaosTarget],
        _parameters: &ChaosParameters,
    ) -> Result<String, TestkitError> {
        self.calls.lock().unwrap().push("inject".to_owned());
        Ok("injection-1".to_owned())
    }
    async fn recover(&self, _injection_id: &str) -> Result<(), TestkitError> {
        self.calls.lock().unwrap().push("recover".to_owned());
        Ok(())
    }
    async fn cleanup(&self, _injection_id: &str) -> Result<(), TestkitError> {
        self.calls.lock().unwrap().push("cleanup".to_owned());
        Ok(())
    }
}

struct HealthyProbe;
#[async_trait]
impl SteadyStateProbe for HealthyProbe {
    fn name(&self) -> &'static str {
        "health"
    }
    async fn check(&self) -> Result<bool, TestkitError> {
        Ok(true)
    }
}

#[tokio::test]
async fn chaos_always_recovers_and_cleans_up() {
    let case = &fixture()["chaos"];
    let provider = RecordingChaosProvider::default();
    let mut experiment = ChaosExperiment {
        id: "experiment-1".to_owned(),
        name: "delay".to_owned(),
        chaos_type: ChaosType::NetworkDelay,
        scope: ChaosScope::SingleInstance,
        targets: vec![ChaosTarget {
            id: "target-1".to_owned(),
            service: "gateway".to_owned(),
            instance: None,
            labels: BTreeMap::new(),
        }],
        parameters: ChaosParameters {
            duration_ms: case["duration_ms"].as_u64().unwrap(),
            intensity: case["intensity"].as_f64().unwrap(),
            latency_ms: Some(100),
            loss_percent: None,
            metadata: BTreeMap::new(),
        },
        phase: ExperimentPhase::Created,
        injection_id: None,
    };
    experiment
        .run(&provider, &[Arc::new(HealthyProbe)])
        .await
        .unwrap();
    assert_eq!(experiment.phase, ExperimentPhase::Completed);
    assert_eq!(
        *provider.calls.lock().unwrap(),
        vec!["inject", "recover", "cleanup"]
    );
}

#[test]
fn deterministic_clock_ids_and_event_collector_support_service_tests() {
    let clock = DeterministicClock::default();
    clock.advance_ms(42);
    assert_eq!(clock.now_ms(), 42);
    let ids = DeterministicIds::new(["one".to_owned(), "two".to_owned()]);
    assert_eq!(ids.next().unwrap(), "one");
    assert_eq!(ids.next().unwrap(), "two");
    assert!(ids.next().is_err());
    let mut events = EventCollector::default();
    events.record(json!({"type": "created"}));
    assert_eq!(events.matching("created").len(), 1);
}
