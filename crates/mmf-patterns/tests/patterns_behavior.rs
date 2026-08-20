use std::collections::BTreeMap;
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};

use async_trait::async_trait;
use mmf_patterns::*;
use serde_json::{Value, json};

fn fixture() -> Value {
    serde_json::from_str(include_str!(
        "../../../contracts/workflow-patterns-behavior.json"
    ))
    .expect("valid patterns fixture")
}

fn event(id: &str, kind: &str, version: u64, data: Value) -> DomainEvent {
    DomainEvent {
        event_id: id.to_owned(),
        aggregate_id: "order-1".to_owned(),
        aggregate_type: "Order".to_owned(),
        event_type: kind.to_owned(),
        version,
        occurred_at_ms: version,
        data,
        metadata: BTreeMap::new(),
    }
}

#[tokio::test]
async fn event_stream_concurrency_replay_and_snapshots_match_contract() {
    let case = &fixture()["event_stream"];
    let store = InMemoryEventStore::default();
    let stream = case["stream_id"].as_str().unwrap();
    let events = vec![
        event(
            "event-1",
            case["event_types"][0].as_str().unwrap(),
            1,
            json!({"status": "created", "amount": 1250}),
        ),
        event(
            "event-2",
            case["event_types"][1].as_str().unwrap(),
            2,
            json!({"status": "paid"}),
        ),
    ];
    assert_eq!(store.append(stream, 0, events.clone()).await.unwrap(), 2);
    assert!(matches!(
        store
            .append(
                stream,
                case["stale_expected_version"].as_u64().unwrap(),
                vec![event("event-3", "Stale", 3, json!({}))]
            )
            .await,
        Err(PatternError::Concurrency { .. })
    ));
    let loaded = store.load(stream, 1, None).await.unwrap();
    assert_eq!(loaded.events, events);

    let mut aggregate = AggregateDocument::new("order-1", "Order");
    aggregate.replay(&loaded.events).unwrap();
    assert_eq!(aggregate.state, case["final_state"]);
    let snapshot = aggregate.snapshot(10);
    assert_eq!(snapshot.version, case["snapshot_version"].as_u64().unwrap());
    let snapshots = InMemorySnapshotStore::default();
    snapshots.save(snapshot.clone()).await.unwrap();
    assert_eq!(snapshots.load("order-1").await.unwrap(), Some(snapshot));
}

struct CountingCommandHandler(Arc<AtomicUsize>);

#[async_trait]
impl CommandHandler for CountingCommandHandler {
    async fn handle(&self, command: &Command) -> Result<CommandResult, PatternError> {
        self.0.fetch_add(1, Ordering::SeqCst);
        Ok(CommandResult {
            success: true,
            value: command.payload.clone(),
            emitted_event_ids: vec!["event-1".to_owned()],
            error: None,
        })
    }
}

struct EchoQueryHandler;

#[async_trait]
impl QueryHandler for EchoQueryHandler {
    async fn handle(&self, query: &Query) -> Result<Value, PatternError> {
        Ok(query.payload.clone())
    }
}

#[tokio::test]
async fn cqrs_routes_and_deduplicates_commands() {
    let case = &fixture()["cqrs"];
    let count = Arc::new(AtomicUsize::new(0));
    let mut bus = CqrsBus::default();
    bus.register_command(
        case["command_type"].as_str().unwrap(),
        Arc::new(CountingCommandHandler(count.clone())),
    )
    .unwrap();
    bus.register_query(
        case["query_type"].as_str().unwrap(),
        Arc::new(EchoQueryHandler),
    )
    .unwrap();
    let command = Command {
        id: case["command_id"].as_str().unwrap().to_owned(),
        command_type: case["command_type"].as_str().unwrap().to_owned(),
        aggregate_id: Some("order-1".to_owned()),
        correlation_id: None,
        causation_id: None,
        issued_at_ms: 0,
        payload: json!({"amount": 1250}),
        metadata: BTreeMap::new(),
    };
    let first = bus.execute_command(&command).await.unwrap();
    let replay = bus.execute_command(&command).await.unwrap();
    assert_eq!(first, replay);
    assert_eq!(
        count.load(Ordering::SeqCst),
        usize::try_from(case["handler_invocations"].as_u64().unwrap()).unwrap()
    );
    let query = Query {
        id: case["query_id"].as_str().unwrap().to_owned(),
        query_type: case["query_type"].as_str().unwrap().to_owned(),
        correlation_id: None,
        issued_at_ms: 0,
        mode: QueryExecutionMode::Sync,
        payload: json!({"id": "order-1"}),
        metadata: BTreeMap::new(),
    };
    assert_eq!(bus.execute_query(&query).await.unwrap(), query.payload);
}

#[derive(Default)]
struct ParticipantProvider {
    fail_prepare_for: Option<String>,
}

#[async_trait]
impl TransactionParticipantProvider for ParticipantProvider {
    async fn prepare(
        &self,
        _transaction_id: &str,
        participant: &TransactionParticipant,
        _context: &Value,
    ) -> Result<(), PatternError> {
        if self.fail_prepare_for.as_deref() == Some(&participant.service_name) {
            Err(PatternError::Operation("prepare failed".to_owned()))
        } else {
            Ok(())
        }
    }
    async fn commit(
        &self,
        _transaction_id: &str,
        _participant: &TransactionParticipant,
    ) -> Result<(), PatternError> {
        Ok(())
    }
    async fn abort(
        &self,
        _transaction_id: &str,
        _participant: &TransactionParticipant,
    ) -> Result<(), PatternError> {
        Ok(())
    }
}

fn participants() -> Vec<ParticipantRegistration> {
    vec![
        ParticipantRegistration {
            id: "participant-1".to_owned(),
            service_name: "inventory".to_owned(),
            endpoint: "https://inventory".to_owned(),
        },
        ParticipantRegistration {
            id: "participant-2".to_owned(),
            service_name: "payments".to_owned(),
            endpoint: "https://payments".to_owned(),
        },
    ]
}

#[tokio::test]
async fn two_phase_commit_failure_abort_and_timeout_are_explicit() {
    let case = &fixture()["transaction"];
    let coordinator = DistributedTransactionCoordinator::default();
    coordinator
        .begin(
            case["transaction_id"].as_str().unwrap(),
            "coordinator",
            participants(),
            case["timeout_ms"].as_u64().unwrap(),
            0,
            json!({}),
        )
        .unwrap();
    assert!(
        coordinator
            .prepare(
                case["transaction_id"].as_str().unwrap(),
                &ParticipantProvider::default(),
                1
            )
            .await
            .unwrap()
    );
    assert!(
        coordinator
            .commit(
                case["transaction_id"].as_str().unwrap(),
                &ParticipantProvider::default(),
                2
            )
            .await
            .unwrap()
    );
    assert_eq!(
        coordinator
            .get(case["transaction_id"].as_str().unwrap())
            .unwrap()
            .unwrap()
            .state,
        TransactionState::Committed
    );

    coordinator
        .begin(
            "transaction-fail",
            "coordinator",
            participants(),
            100,
            0,
            json!({}),
        )
        .unwrap();
    let provider = ParticipantProvider {
        fail_prepare_for: Some("payments".to_owned()),
    };
    assert!(
        !coordinator
            .prepare("transaction-fail", &provider, 1)
            .await
            .unwrap()
    );
    assert!(
        coordinator
            .abort("transaction-fail", &ParticipantProvider::default(), 2)
            .await
            .unwrap()
    );
    assert_eq!(
        coordinator.get("transaction-fail").unwrap().unwrap().state,
        TransactionState::Aborted
    );

    coordinator
        .begin(
            "transaction-timeout",
            "coordinator",
            participants(),
            100,
            0,
            json!({}),
        )
        .unwrap();
    assert_eq!(
        coordinator.expire(100).unwrap(),
        vec!["transaction-timeout"]
    );
}

#[test]
fn consistency_configuration_fails_closed() {
    let case = &fixture()["consistency"];
    let valid = ConsistencyPolicy {
        level: ConsistencyLevel::Strong,
        read_quorum: u32::try_from(case["read_quorum"].as_u64().unwrap()).unwrap(),
        write_quorum: u32::try_from(case["write_quorum"].as_u64().unwrap()).unwrap(),
        replication_factor: u32::try_from(case["replication_factor"].as_u64().unwrap()).unwrap(),
        maximum_staleness_ms: 0,
        conflict_resolution: ConflictResolution::Reject,
    };
    assert!(valid.validate().is_ok());
    let invalid = ConsistencyPolicy {
        read_quorum: 1,
        write_quorum: 1,
        ..valid
    };
    assert!(invalid.validate().is_err());
}
