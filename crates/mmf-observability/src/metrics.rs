use std::collections::{BTreeMap, BTreeSet};
use std::fmt::Write;
use std::sync::{Arc, Mutex};

use serde::{Deserialize, Serialize};

use crate::ObservabilityError;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MetricType {
    Counter,
    Gauge,
    Histogram,
    Summary,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct MetricDefinition {
    pub name: String,
    pub metric_type: MetricType,
    pub help: String,
    #[serde(default)]
    pub namespace: String,
    #[serde(default)]
    pub labels: BTreeSet<String>,
    #[serde(default)]
    pub buckets: Vec<f64>,
    #[serde(default = "default_max_series")]
    pub max_series: usize,
}

const fn default_max_series() -> usize {
    1_000
}

impl MetricDefinition {
    pub fn validate(&self) -> Result<(), ObservabilityError> {
        if !valid_metric_name(&self.name)
            || (!self.namespace.is_empty() && !valid_metric_name(&self.namespace))
        {
            return Err(ObservabilityError::InvalidMetricName(self.full_name()));
        }
        if self.help.trim().is_empty() || self.max_series == 0 {
            return Err(ObservabilityError::InvalidMetricDefinition(
                self.full_name(),
            ));
        }
        if self.labels.iter().any(|label| !valid_label_name(label)) {
            return Err(ObservabilityError::InvalidMetricDefinition(
                self.full_name(),
            ));
        }
        if self.metric_type == MetricType::Histogram
            && (self.buckets.is_empty()
                || self.buckets.iter().any(|bucket| !bucket.is_finite())
                || self.buckets.windows(2).any(|pair| pair[0] >= pair[1]))
        {
            return Err(ObservabilityError::InvalidMetricDefinition(
                self.full_name(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn full_name(&self) -> String {
        if self.namespace.is_empty() {
            self.name.clone()
        } else {
            format!("{}_{}", self.namespace, self.name)
        }
    }
}

#[derive(Clone, Debug, Eq, Ord, PartialEq, PartialOrd)]
struct SeriesKey(Vec<(String, String)>);

impl SeriesKey {
    fn new(
        labels: BTreeMap<String, String>,
        expected: &BTreeSet<String>,
    ) -> Result<Self, ObservabilityError> {
        let actual = labels.keys().cloned().collect::<BTreeSet<_>>();
        if &actual != expected {
            return Err(ObservabilityError::MetricLabelMismatch {
                expected: expected.clone(),
                actual,
            });
        }
        Ok(Self(labels.into_iter().collect()))
    }

    fn render(&self, extra: Option<(&str, String)>) -> String {
        let labels = self
            .0
            .iter()
            .map(|(key, value)| format!("{key}=\"{}\"", escape_label(value)))
            .chain(extra.map(|(key, value)| format!("{key}=\"{}\"", escape_label(&value))))
            .collect::<Vec<_>>();
        if labels.is_empty() {
            String::new()
        } else {
            format!("{{{}}}", labels.join(","))
        }
    }
}

#[derive(Clone, Debug)]
struct HistogramSeries {
    buckets: Vec<u64>,
    count: u64,
    sum: f64,
}

#[derive(Clone, Debug)]
enum MetricSeries {
    Counter(BTreeMap<SeriesKey, f64>),
    Gauge(BTreeMap<SeriesKey, f64>),
    Histogram(BTreeMap<SeriesKey, HistogramSeries>),
    Summary(BTreeMap<SeriesKey, (u64, f64)>),
}

impl MetricSeries {
    fn len(&self) -> usize {
        match self {
            Self::Counter(series) | Self::Gauge(series) => series.len(),
            Self::Histogram(series) => series.len(),
            Self::Summary(series) => series.len(),
        }
    }

    fn contains(&self, key: &SeriesKey) -> bool {
        match self {
            Self::Counter(series) | Self::Gauge(series) => series.contains_key(key),
            Self::Histogram(series) => series.contains_key(key),
            Self::Summary(series) => series.contains_key(key),
        }
    }
}

#[derive(Clone, Debug)]
struct MetricFamily {
    definition: MetricDefinition,
    series: MetricSeries,
}

impl MetricFamily {
    fn new(definition: MetricDefinition) -> Self {
        let series = match definition.metric_type {
            MetricType::Counter => MetricSeries::Counter(BTreeMap::new()),
            MetricType::Gauge => MetricSeries::Gauge(BTreeMap::new()),
            MetricType::Histogram => MetricSeries::Histogram(BTreeMap::new()),
            MetricType::Summary => MetricSeries::Summary(BTreeMap::new()),
        };
        Self { definition, series }
    }

    fn guard_cardinality(&self, key: &SeriesKey) -> Result<(), ObservabilityError> {
        if !self.series.contains(key) && self.series.len() >= self.definition.max_series {
            return Err(ObservabilityError::MetricCardinalityExceeded(
                self.definition.full_name(),
            ));
        }
        Ok(())
    }
}

/// Provider-neutral registry with Prometheus exposition and cardinality limits.
#[derive(Clone, Debug, Default)]
pub struct MetricRegistry {
    families: Arc<Mutex<BTreeMap<String, MetricFamily>>>,
}

impl MetricRegistry {
    pub fn register(&self, definition: MetricDefinition) -> Result<(), ObservabilityError> {
        definition.validate()?;
        let name = definition.full_name();
        let mut families = self.lock_families();
        if let Some(existing) = families.get(&name) {
            if existing.definition == definition {
                return Ok(());
            }
            return Err(ObservabilityError::MetricAlreadyRegistered(name));
        }
        families.insert(name, MetricFamily::new(definition));
        Ok(())
    }

    pub fn increment(
        &self,
        name: &str,
        labels: BTreeMap<String, String>,
        amount: f64,
    ) -> Result<(), ObservabilityError> {
        if !amount.is_finite() || amount < 0.0 {
            return Err(ObservabilityError::InvalidMetricValue(name.to_owned()));
        }
        let mut families = self.lock_families();
        let family = family_mut(&mut families, name)?;
        if family.definition.metric_type != MetricType::Counter {
            return Err(ObservabilityError::MetricTypeMismatch(name.to_owned()));
        }
        let key = SeriesKey::new(labels, &family.definition.labels)?;
        family.guard_cardinality(&key)?;
        let MetricSeries::Counter(series) = &mut family.series else {
            unreachable!("metric type and storage are constructed together")
        };
        *series.entry(key).or_default() += amount;
        Ok(())
    }

    pub fn set_gauge(
        &self,
        name: &str,
        labels: BTreeMap<String, String>,
        value: f64,
    ) -> Result<(), ObservabilityError> {
        if !value.is_finite() {
            return Err(ObservabilityError::InvalidMetricValue(name.to_owned()));
        }
        let mut families = self.lock_families();
        let family = family_mut(&mut families, name)?;
        if family.definition.metric_type != MetricType::Gauge {
            return Err(ObservabilityError::MetricTypeMismatch(name.to_owned()));
        }
        let key = SeriesKey::new(labels, &family.definition.labels)?;
        family.guard_cardinality(&key)?;
        let MetricSeries::Gauge(series) = &mut family.series else {
            unreachable!("metric type and storage are constructed together")
        };
        series.insert(key, value);
        Ok(())
    }

    pub fn observe(
        &self,
        name: &str,
        labels: BTreeMap<String, String>,
        value: f64,
    ) -> Result<(), ObservabilityError> {
        if !value.is_finite() {
            return Err(ObservabilityError::InvalidMetricValue(name.to_owned()));
        }
        let mut families = self.lock_families();
        let family = family_mut(&mut families, name)?;
        let key = SeriesKey::new(labels, &family.definition.labels)?;
        family.guard_cardinality(&key)?;
        match &mut family.series {
            MetricSeries::Histogram(series) => {
                let entry = series.entry(key).or_insert_with(|| HistogramSeries {
                    buckets: vec![0; family.definition.buckets.len()],
                    count: 0,
                    sum: 0.0,
                });
                for (count, upper_bound) in entry.buckets.iter_mut().zip(&family.definition.buckets)
                {
                    if value <= *upper_bound {
                        *count = count.saturating_add(1);
                    }
                }
                entry.count = entry.count.saturating_add(1);
                entry.sum += value;
            }
            MetricSeries::Summary(series) => {
                let entry = series.entry(key).or_default();
                entry.0 = entry.0.saturating_add(1);
                entry.1 += value;
            }
            MetricSeries::Counter(_) | MetricSeries::Gauge(_) => {
                return Err(ObservabilityError::MetricTypeMismatch(name.to_owned()));
            }
        }
        Ok(())
    }

    #[must_use]
    pub fn render_prometheus(&self) -> String {
        let families = self.lock_families();
        let mut output = String::new();
        for (name, family) in families.iter() {
            let metric_type = match family.definition.metric_type {
                MetricType::Counter => "counter",
                MetricType::Gauge => "gauge",
                MetricType::Histogram => "histogram",
                MetricType::Summary => "summary",
            };
            let _ = writeln!(output, "# HELP {name} {}", family.definition.help);
            let _ = writeln!(output, "# TYPE {name} {metric_type}");
            match &family.series {
                MetricSeries::Counter(series) | MetricSeries::Gauge(series) => {
                    for (key, value) in series {
                        let _ = writeln!(output, "{name}{} {value}", key.render(None));
                    }
                }
                MetricSeries::Histogram(series) => {
                    for (key, value) in series {
                        for (upper_bound, count) in
                            family.definition.buckets.iter().zip(&value.buckets)
                        {
                            let _ = writeln!(
                                output,
                                "{name}_bucket{} {count}",
                                key.render(Some(("le", upper_bound.to_string())))
                            );
                        }
                        let _ = writeln!(
                            output,
                            "{name}_bucket{} {}",
                            key.render(Some(("le", "+Inf".to_owned()))),
                            value.count
                        );
                        let _ = writeln!(output, "{name}_sum{} {}", key.render(None), value.sum);
                        let _ =
                            writeln!(output, "{name}_count{} {}", key.render(None), value.count);
                    }
                }
                MetricSeries::Summary(series) => {
                    for (key, (count, sum)) in series {
                        let _ = writeln!(output, "{name}_sum{} {sum}", key.render(None));
                        let _ = writeln!(output, "{name}_count{} {count}", key.render(None));
                    }
                }
            }
        }
        output
    }

    fn lock_families(&self) -> std::sync::MutexGuard<'_, BTreeMap<String, MetricFamily>> {
        self.families
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
    }
}

fn family_mut<'a>(
    families: &'a mut BTreeMap<String, MetricFamily>,
    name: &str,
) -> Result<&'a mut MetricFamily, ObservabilityError> {
    families
        .get_mut(name)
        .ok_or_else(|| ObservabilityError::MetricNotRegistered(name.to_owned()))
}

fn valid_metric_name(name: &str) -> bool {
    let mut bytes = name.bytes();
    bytes.next().is_some_and(|byte| {
        (byte.is_ascii_alphabetic() || byte == b'_' || byte == b':')
            && bytes.all(|item| item.is_ascii_alphanumeric() || matches!(item, b'_' | b':'))
    })
}

fn valid_label_name(name: &str) -> bool {
    let mut bytes = name.bytes();
    bytes.next().is_some_and(|byte| {
        (byte.is_ascii_alphabetic() || byte == b'_')
            && bytes.all(|item| item.is_ascii_alphanumeric() || item == b'_')
    })
}

fn escape_label(value: &str) -> String {
    value
        .replace('\\', "\\\\")
        .replace('\n', "\\n")
        .replace('"', "\\\"")
}
