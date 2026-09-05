use std::{
    future::pending,
    sync::{Arc, Mutex},
    time::Duration,
};

use mmf_runtime::managed_task::{CleanupOutcome, ManagedTask, TaskJoinError, TaskOutcome};
use serde_json::Value;
use tokio::sync::{Notify, Semaphore};

#[derive(Default)]
struct State {
    events: Mutex<Vec<&'static str>>,
    operation_entered: Notify,
    cleanup_entered: Notify,
    cleanup_completed: Notify,
}

impl State {
    fn record(&self, event: &'static str) {
        self.events.lock().unwrap().push(event);
    }
}

struct OperationScope(Arc<State>);

impl Drop for OperationScope {
    fn drop(&mut self) {
        self.0.record("operation_dropped");
    }
}

async fn observed(signal: &Notify) {
    tokio::time::timeout(Duration::from_secs(5), signal.notified())
        .await
        .expect("owned lifecycle signal");
}

#[tokio::test]
async fn every_frozen_exit_awaits_operation_cleanup_and_disposal_before_join() {
    assert_frozen_exits().await;
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn frozen_disposal_order_also_holds_across_runtime_threads() {
    assert_frozen_exits().await;
}

async fn assert_frozen_exits() {
    let contract: Value =
        serde_json::from_str(include_str!("../../../contracts/async-task-lifecycle.json")).unwrap();
    assert_eq!(contract["schema"], "mmf.async-task-lifecycle/v1");
    assert_eq!(contract["cleanup_cancellable"], false);
    let cases = contract["cases"].as_array().unwrap();
    assert_eq!(cases.len(), 3);
    for case in cases {
        let mode = case["operation"].as_str().unwrap().to_owned();
        let state = Arc::new(State::default());
        let operation_state = state.clone();
        let cleanup_state = state.clone();
        let operation_gate = Arc::new(Semaphore::new(0));
        let operation_release = operation_gate.clone();
        let cleanup_gate = Arc::new(Semaphore::new(0));
        let cleanup_release = cleanup_gate.clone();
        let task = ManagedTask::spawn(
            async move {
                let _scope = OperationScope(operation_state.clone());
                operation_state.record("operation_entered");
                operation_state.operation_entered.notify_one();
                operation_gate.acquire().await.unwrap().forget();
                match mode.as_str() {
                    "return" => Ok(7),
                    "error" => Err("original operation failure"),
                    "cancel" => pending().await,
                    _ => panic!("unknown frozen operation mode"),
                }
            },
            move || async move {
                cleanup_state.record("cleanup_entered");
                cleanup_state.cleanup_entered.notify_one();
                cleanup_gate.acquire().await.unwrap().forget();
                cleanup_state.record("cleanup_completed");
                Ok::<(), &'static str>(())
            },
        );
        observed(&state.operation_entered).await;
        let cancellation = task.cancellation_handle();
        if case["operation"] == "cancel" {
            assert!(cancellation.cancel());
        } else {
            operation_release.add_permits(1);
        }
        observed(&state.cleanup_entered).await;
        assert_eq!(
            *state.events.lock().unwrap(),
            ["operation_entered", "operation_dropped", "cleanup_entered"]
        );
        assert!(
            !cancellation.cancel(),
            "cancellation must not abort disposal"
        );
        let mut joined = Box::pin(task.join());
        assert!(
            tokio::time::timeout(Duration::from_millis(20), &mut joined)
                .await
                .is_err(),
            "join acknowledged unfinished disposal"
        );
        cleanup_release.add_permits(1);
        let completion = tokio::time::timeout(Duration::from_secs(5), joined)
            .await
            .unwrap()
            .unwrap();
        state.record("join_completed");
        assert_eq!(completion.cleanup, CleanupOutcome::Completed);
        let category = match completion.outcome {
            TaskOutcome::Completed(value) => {
                assert_eq!(value, 7);
                "completed"
            }
            TaskOutcome::Failed(error) => {
                assert_eq!(error, "original operation failure");
                "failed"
            }
            TaskOutcome::Cancelled => "cancelled",
            TaskOutcome::Panicked => panic!("unexpected operation panic"),
        };
        assert_eq!(category, case["outcome"].as_str().unwrap());
        assert_eq!(
            serde_json::json!(*state.events.lock().unwrap()),
            contract["order"]
        );
    }
}

#[tokio::test]
async fn operation_panic_still_awaits_cleanup() {
    let completion = ManagedTask::spawn(
        async {
            panic!("synthetic operation panic");
            #[allow(unreachable_code)]
            Ok::<(), ()>(())
        },
        || async { Ok::<(), ()>(()) },
    )
    .join()
    .await
    .unwrap();
    assert_eq!(completion.outcome, TaskOutcome::Panicked);
    assert_eq!(completion.cleanup, CleanupOutcome::Completed);
}

#[tokio::test]
async fn cleanup_failure_does_not_erase_operation_failure() {
    let completion = ManagedTask::spawn(async { Err::<(), _>("operation failure") }, || async {
        Err::<(), _>("cleanup failure")
    })
    .join()
    .await
    .unwrap();
    assert_eq!(completion.outcome, TaskOutcome::Failed("operation failure"));
    assert_eq!(
        completion.cleanup,
        CleanupOutcome::Failed("cleanup failure")
    );
}

#[tokio::test]
async fn synchronous_cleanup_factory_panic_retains_operation_outcome() {
    let completion = ManagedTask::spawn(async { Ok::<_, ()>(9) }, || {
        panic!("synthetic cleanup factory panic");
        #[allow(unreachable_code)]
        async {
            Ok::<(), ()>(())
        }
    })
    .join()
    .await
    .unwrap();
    assert_eq!(completion.outcome, TaskOutcome::Completed(9));
    assert_eq!(completion.cleanup, CleanupOutcome::Panicked);
}

#[tokio::test]
async fn pre_start_cancellation_drops_unpolled_operation_before_disposal() {
    let state = Arc::new(State::default());
    let scope = OperationScope(state.clone());
    let cleanup_state = state.clone();
    let task = ManagedTask::spawn(
        async move {
            let _scope = scope;
            panic!("pre-cancelled operation must not start");
            #[allow(unreachable_code)]
            Ok::<(), ()>(())
        },
        move || async move {
            cleanup_state.record("cleanup_completed");
            Ok::<(), ()>(())
        },
    );
    assert!(task.cancel());
    let completion = task.join().await.unwrap();
    assert_eq!(completion.outcome, TaskOutcome::Cancelled);
    assert_eq!(completion.cleanup, CleanupOutcome::Completed);
    assert_eq!(
        *state.events.lock().unwrap(),
        ["operation_dropped", "cleanup_completed"]
    );
}

#[tokio::test]
async fn dropping_owner_requests_cancellation_without_aborting_cleanup() {
    for drop_join in [false, true] {
        assert_dropped_owner_disposes(drop_join).await;
    }
}

async fn assert_dropped_owner_disposes(drop_join: bool) {
    let state = Arc::new(State::default());
    let operation_state = state.clone();
    let cleanup_state = state.clone();
    let task = ManagedTask::spawn(
        async move {
            let _scope = OperationScope(operation_state.clone());
            operation_state.operation_entered.notify_one();
            pending::<Result<(), ()>>().await
        },
        move || async move {
            cleanup_state.record("cleanup_completed");
            cleanup_state.cleanup_completed.notify_one();
            Ok::<(), ()>(())
        },
    );
    observed(&state.operation_entered).await;
    if drop_join {
        let mut joined = Box::pin(task.join());
        assert!(
            tokio::time::timeout(Duration::from_millis(20), &mut joined)
                .await
                .is_err()
        );
        drop(joined);
    } else {
        drop(task);
    }
    observed(&state.cleanup_completed).await;
    assert_eq!(
        *state.events.lock().unwrap(),
        ["operation_dropped", "cleanup_completed"]
    );
}

#[tokio::test]
async fn pre_start_destructor_panic_still_disposes_initialized_resources() {
    struct PanickingDrop;
    impl Drop for PanickingDrop {
        fn drop(&mut self) {
            panic!("synthetic unpolled operation destructor panic");
        }
    }
    let guard = PanickingDrop;
    let task = ManagedTask::spawn(
        async move {
            let _guard = guard;
            pending::<Result<(), ()>>().await
        },
        || async { Ok::<(), ()>(()) },
    );
    assert!(task.cancel());
    let completion = task.join().await.unwrap();
    assert_eq!(completion.outcome, TaskOutcome::Panicked);
    assert_eq!(completion.cleanup, CleanupOutcome::Completed);
}

#[tokio::test]
async fn panic_result_destructor_cannot_run_before_resource_disposal() {
    struct PanicPayload(Arc<State>);
    impl Drop for PanicPayload {
        fn drop(&mut self) {
            self.0.record("panic_payload_dropped");
            panic!("synthetic panic result destructor");
        }
    }
    let state = Arc::new(State::default());
    let operation_state = state.clone();
    let cleanup_state = state.clone();
    let task = ManagedTask::spawn(
        async move {
            std::panic::panic_any(PanicPayload(operation_state));
            #[allow(unreachable_code)]
            Ok::<(), ()>(())
        },
        move || async move {
            cleanup_state.record("cleanup_completed");
            Ok::<(), ()>(())
        },
    );
    // Releasing an exceptional result can itself fail. That must remain a
    // failed observation, never an acknowledgment of successful execution.
    assert_eq!(task.join().await, Err(TaskJoinError::SupervisorPanicked));
    assert_eq!(
        *state.events.lock().unwrap(),
        ["cleanup_completed", "panic_payload_dropped"]
    );
}
