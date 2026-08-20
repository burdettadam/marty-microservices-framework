use std::collections::{BTreeMap, BTreeSet};

use mmf_workflow::*;
use serde_json::{Value, json};

fn fixture() -> Value {
    serde_json::from_str(include_str!(
        "../../../contracts/workflow-patterns-behavior.json"
    ))
    .expect("valid workflow fixture")
}

fn definition() -> WorkflowDefinition {
    WorkflowDefinition {
        id: "order-fulfillment".to_owned(),
        version: 1,
        timeout_ms: Some(300_000),
        steps: vec![
            StepDefinition {
                id: "reserve".to_owned(),
                step_type: StepType::Action,
                dependencies: BTreeSet::new(),
                retry: WorkflowRetryPolicy::default(),
                timeout_ms: Some(10_000),
                compensation: Some("release_inventory".to_owned()),
                configuration: json!({"action": "reserve_inventory"}),
            },
            StepDefinition {
                id: "charge".to_owned(),
                step_type: StepType::Action,
                dependencies: BTreeSet::from(["reserve".to_owned()]),
                retry: WorkflowRetryPolicy::default(),
                timeout_ms: Some(10_000),
                compensation: Some("refund_payment".to_owned()),
                configuration: json!({"action": "charge_payment"}),
            },
            StepDefinition {
                id: "notify".to_owned(),
                step_type: StepType::Action,
                dependencies: BTreeSet::from(["charge".to_owned()]),
                retry: WorkflowRetryPolicy::default(),
                timeout_ms: Some(10_000),
                compensation: None,
                configuration: json!({"action": "notify"}),
            },
        ],
    }
}

#[test]
fn retries_dependencies_and_reverse_compensation_match_contract() {
    let case = &fixture()["workflow"];
    let definition = definition();
    let mut execution = WorkflowExecution::create(
        &definition,
        case["execution_id"].as_str().unwrap(),
        case["correlation_id"].as_str().unwrap(),
        0,
        BTreeMap::new(),
    )
    .unwrap();
    execution.start(0).unwrap();
    assert_eq!(execution.ready_steps(&definition, 0), vec!["reserve"]);
    assert!(execution.begin_step(&definition, "charge", 0).is_err());

    execution.begin_step(&definition, "reserve", 0).unwrap();
    execution
        .complete_step(
            &definition,
            "reserve",
            StepResult {
                success: true,
                ..StepResult::default()
            },
            1,
        )
        .unwrap();
    execution.begin_step(&definition, "charge", 1).unwrap();
    execution
        .complete_step(
            &definition,
            "charge",
            StepResult {
                success: false,
                error: Some("temporary".to_owned()),
                should_retry: true,
                ..StepResult::default()
            },
            2,
        )
        .unwrap();
    assert_eq!(
        execution.steps["charge"].available_at_ms,
        Some(2 + case["retry_delay_ms"].as_u64().unwrap())
    );
    execution.begin_step(&definition, "charge", 1_002).unwrap();
    execution
        .complete_step(
            &definition,
            "charge",
            StepResult {
                success: true,
                ..StepResult::default()
            },
            1_003,
        )
        .unwrap();
    execution.begin_step(&definition, "notify", 1_003).unwrap();
    execution
        .complete_step(
            &definition,
            "notify",
            StepResult {
                success: false,
                error: Some("permanent".to_owned()),
                ..StepResult::default()
            },
            1_004,
        )
        .unwrap();

    let mut order = Vec::new();
    while let Some((step, _action)) = execution.next_compensation(&definition) {
        order.push(step.clone());
        execution.begin_compensation(&step, 2_000).unwrap();
        execution
            .complete_compensation(&definition, &step, true, 2_001)
            .unwrap();
    }
    let expected = case["compensation_order"]
        .as_array()
        .unwrap()
        .iter()
        .map(|value| value.as_str().unwrap().to_owned())
        .collect::<Vec<_>>();
    assert_eq!(order, expected);
    assert_eq!(execution.status, WorkflowStatus::Compensated);
}

#[test]
fn cycles_timeouts_waits_loops_and_repository_are_fail_closed() {
    let mut cyclic = definition();
    cyclic.steps[0].dependencies.insert("notify".to_owned());
    assert!(cyclic.validate().is_err());

    let mut execution = WorkflowExecution::create(
        &definition(),
        "workflow-2",
        "correlation-2",
        0,
        BTreeMap::new(),
    )
    .unwrap();
    execution.start(0).unwrap();
    assert!(execution.enforce_timeout(&definition(), 300_000).unwrap());
    assert_eq!(execution.status, WorkflowStatus::TimedOut);

    let repository = InMemoryWorkflowRepository::default();
    let runtime = tokio::runtime::Runtime::new().unwrap();
    runtime
        .block_on(repository.save(execution.clone()))
        .unwrap();
    assert_eq!(
        runtime
            .block_on(repository.load("workflow-2"))
            .unwrap()
            .unwrap(),
        execution
    );
}
