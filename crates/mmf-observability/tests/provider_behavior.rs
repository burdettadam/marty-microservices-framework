use std::collections::{BTreeMap, BTreeSet};

use mmf_observability::{
    AlertSeverity, AlertTransition, AnomalyDetector, CapacityPlanner, DescriptiveStatistics,
    HealthCheckResult, HealthStatus, InstrumentationConfig, MetricAggregation, MetricPoint,
    MetricWindow, MonitoringAlertRule, ServiceHealthReport, ServiceMetrics, SystemMetricsSnapshot,
    ThresholdOperator, TrendAnalysis,
};
use serde::Deserialize;

#[derive(Deserialize)]
struct Fixture {
    schema_version: u32,
    aggregations: Aggregations,
    thresholds: Vec<ThresholdCase>,
    health_rollups: Vec<HealthRollup>,
    trend: TrendCase,
    capacity: CapacityCase,
}

#[derive(Deserialize)]
struct Aggregations {
    values: Vec<f64>,
    expected: BTreeMap<String, f64>,
}

#[derive(Deserialize)]
struct ThresholdCase {
    operator: ThresholdOperator,
    value: f64,
    threshold: f64,
    triggered: bool,
}

#[derive(Deserialize)]
struct HealthRollup {
    statuses: Vec<HealthStatus>,
    expected: HealthStatus,
}

#[derive(Deserialize)]
struct TrendCase {
    points: Vec<MetricPoint>,
    direction: mmf_observability::TrendDirection,
    slope_per_second: f64,
    r_squared: f64,
    mean: f64,
    median: f64,
    p95: f64,
    p99: f64,
}

#[derive(Deserialize)]
struct CapacityCase {
    metric_name: String,
    points: Vec<MetricPoint>,
    horizon_seconds: u64,
    predicted_usage: f64,
    time_to_threshold_seconds: f64,
    recommendation_prefix: String,
}

fn fixture() -> Fixture {
    serde_json::from_str(include_str!(
        "../../../contracts/observability-provider-behavior.json"
    ))
    .expect("valid observability provider fixture")
}

#[test]
fn metric_windows_and_thresholds_match_the_shared_contract() {
    let fixture = fixture();
    assert_eq!(fixture.schema_version, 1);
    let mut window = MetricWindow::new(60_000, 100).expect("valid window");
    for (index, value) in fixture.aggregations.values.iter().copied().enumerate() {
        window
            .add(
                MetricPoint {
                    timestamp_ms: index as u64,
                    value,
                },
                10,
            )
            .expect("valid point");
    }
    let cases = [
        ("sum", MetricAggregation::Sum),
        ("average", MetricAggregation::Average),
        ("min", MetricAggregation::Min),
        ("max", MetricAggregation::Max),
        ("count", MetricAggregation::Count),
        ("p95", MetricAggregation::P95),
        ("p99", MetricAggregation::P99),
        ("latest", MetricAggregation::Latest),
    ];
    for (name, aggregation) in cases {
        assert_eq!(
            window.aggregate(aggregation, 10),
            fixture.aggregations.expected.get(name).copied()
        );
    }
    for case in fixture.thresholds {
        assert_eq!(
            case.operator.evaluate(case.value, case.threshold),
            case.triggered
        );
    }
}

#[test]
fn health_rollup_uses_worst_component_status() {
    for case in fixture().health_rollups {
        let checks = case
            .statuses
            .into_iter()
            .enumerate()
            .map(|(index, status)| {
                let name = format!("check-{index}");
                (
                    name.clone(),
                    HealthCheckResult {
                        name,
                        status,
                        message: None,
                        details: BTreeMap::new(),
                        timestamp_ms: 1,
                        duration_ms: Some(1.0),
                    },
                )
            })
            .collect();
        assert_eq!(
            ServiceHealthReport::aggregate("service", 1, checks, ServiceMetrics::default()).status,
            case.expected
        );
    }
}

#[test]
fn trend_statistics_and_capacity_match_the_shared_contract() {
    let fixture = fixture();
    let analysis = TrendAnalysis::calculate(&fixture.trend.points).expect("valid trend");
    assert_eq!(analysis.direction, fixture.trend.direction);
    assert!((analysis.slope_per_second - fixture.trend.slope_per_second).abs() < 1e-12);
    assert!((analysis.r_squared - fixture.trend.r_squared).abs() < 1e-12);
    let values = fixture
        .trend
        .points
        .iter()
        .map(|point| point.value)
        .collect::<Vec<_>>();
    let statistics = DescriptiveStatistics::calculate(&values).expect("valid statistics");
    assert!((statistics.mean - fixture.trend.mean).abs() < 1e-12);
    assert!((statistics.median - fixture.trend.median).abs() < 1e-12);
    assert!((statistics.p95 - fixture.trend.p95).abs() < 1e-12);
    assert!((statistics.p99 - fixture.trend.p99).abs() < 1e-12);

    let capacity = fixture.capacity;
    let prediction = CapacityPlanner::default()
        .predict(
            &capacity.metric_name,
            &capacity.points,
            capacity.horizon_seconds,
        )
        .expect("valid prediction");
    assert!((prediction.predicted_usage - capacity.predicted_usage).abs() < 1e-9);
    assert!(
        (prediction.time_to_threshold_seconds.expect("threshold")
            - capacity.time_to_threshold_seconds)
            .abs()
            < 1e-6
    );
    assert!(
        prediction
            .recommended_action
            .starts_with(&capacity.recommendation_prefix)
    );
}

#[test]
fn alert_state_is_deduplicated_resolved_and_cooled_down() {
    let mut engine = mmf_observability::AlertEngine::default();
    engine
        .add_rule(MonitoringAlertRule {
            name: "latency".into(),
            metric_name: "latency_ms".into(),
            operator: ThresholdOperator::GreaterThan,
            threshold: 100.0,
            severity: AlertSeverity::Critical,
            description: "Latency high".into(),
            aggregation: MetricAggregation::P95,
            window_ms: 60_000,
            for_ms: 1_000,
            cooldown_ms: 5_000,
            dependencies: BTreeSet::default(),
            enabled: true,
        })
        .expect("valid rule");
    assert_eq!(
        engine.evaluate("latency", 101.0, 1).expect("evaluate"),
        AlertTransition::NoChange
    );
    assert!(matches!(
        engine.evaluate("latency", 101.0, 1_001).expect("trigger"),
        AlertTransition::Triggered(_)
    ));
    assert_eq!(engine.active_alerts().len(), 1);
    assert!(matches!(
        engine.evaluate("latency", 90.0, 2_000).expect("resolve"),
        AlertTransition::Resolved(_)
    ));
    assert_eq!(
        engine.evaluate("latency", 101.0, 3_000).expect("cooldown"),
        AlertTransition::Suppressed
    );
}

#[test]
fn anomaly_and_instrumentation_inputs_fail_closed() {
    let mut detector = AnomalyDetector::new(10, 100);
    for value in [9.8, 10.0, 10.2, 9.9, 10.1, 10.0, 9.7, 10.3, 9.8, 10.2] {
        detector.observe("latency", value).expect("baseline");
    }
    assert!(detector.is_anomaly("latency", 20.0, 0.5).expect("score"));
    assert!(detector.is_anomaly("latency", 20.0, 1.1).is_err());

    let instrumentation = InstrumentationConfig {
        enabled_targets: BTreeSet::default(),
        excluded_paths: BTreeSet::from(["/health".into()]),
        capture_request_headers: BTreeSet::from(["authorization".into()]),
        capture_response_headers: BTreeSet::default(),
        static_attributes: BTreeMap::default(),
    };
    assert!(instrumentation.validate().is_err());
    assert!(
        SystemMetricsSnapshot {
            timestamp_ms: 1,
            cpu_usage: 1.1,
            memory_usage: 0.5,
            disk_usage: 0.5,
            network_receive_bytes: 0,
            network_transmit_bytes: 0,
            attributes: BTreeMap::default(),
        }
        .validate()
        .is_err()
    );
}
