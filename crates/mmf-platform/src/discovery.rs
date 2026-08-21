use std::collections::{BTreeMap, BTreeSet, VecDeque};

use rand::prelude::IndexedRandom;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::PlatformError;

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ServiceStatus {
    Unknown,
    Starting,
    Healthy,
    Unhealthy,
    Critical,
    Maintenance,
    Terminating,
    Terminated,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum HealthStatus {
    Unknown,
    Healthy,
    Unhealthy,
    Timeout,
    Error,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum EndpointProtocol {
    Http,
    Https,
    Tcp,
    Udp,
    Grpc,
    WebSocket,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ServiceEndpoint {
    pub host: String,
    pub port: u16,
    pub protocol: EndpointProtocol,
    pub path: String,
    pub verify_tls: bool,
    pub connect_timeout_ms: u64,
    pub read_timeout_ms: u64,
}

impl ServiceEndpoint {
    pub fn validate(&self) -> Result<(), PlatformError> {
        if self.host.trim().is_empty() || self.port == 0 {
            return Err(PlatformError::InvalidConfiguration(
                "endpoint requires a host and nonzero port".into(),
            ));
        }
        if self.protocol == EndpointProtocol::Https && !self.verify_tls {
            return Err(PlatformError::InvalidConfiguration(
                "HTTPS endpoints must verify TLS".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn url(&self) -> String {
        let scheme = match self.protocol {
            EndpointProtocol::Http => "http",
            EndpointProtocol::Https => "https",
            EndpointProtocol::Tcp => "tcp",
            EndpointProtocol::Udp => "udp",
            EndpointProtocol::Grpc => "grpc",
            EndpointProtocol::WebSocket => "ws",
        };
        let path = if self.path.is_empty() {
            String::new()
        } else if self.path.starts_with('/') {
            self.path.clone()
        } else {
            format!("/{}", self.path)
        };
        format!("{scheme}://{}:{}{path}", self.host, self.port)
    }
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct ServiceMetadata {
    pub version: String,
    pub environment: String,
    pub weight: u32,
    pub region: String,
    pub availability_zone: String,
    pub deployment_id: Option<String>,
    pub build_id: Option<String>,
    pub git_commit: Option<String>,
    pub max_connections: Option<u32>,
    #[serde(default)]
    pub tags: BTreeSet<String>,
    #[serde(default)]
    pub labels: BTreeMap<String, String>,
    #[serde(default)]
    pub annotations: BTreeMap<String, String>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct HealthCheckConfig {
    pub path: Option<String>,
    pub tcp_port: Option<u16>,
    pub expected_status: u16,
    pub interval_ms: u64,
    pub timeout_ms: u64,
    pub failure_threshold: u32,
    pub success_threshold: u32,
}

impl HealthCheckConfig {
    #[must_use]
    pub const fn is_valid(&self) -> bool {
        (self.path.is_some() || self.tcp_port.is_some())
            && self.interval_ms > 0
            && self.timeout_ms > 0
            && self.failure_threshold > 0
            && self.success_threshold > 0
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ServiceInstance {
    pub service_name: String,
    pub instance_id: String,
    pub endpoint: ServiceEndpoint,
    pub metadata: ServiceMetadata,
    pub health_check: Option<HealthCheckConfig>,
    pub status: ServiceStatus,
    pub health_status: HealthStatus,
    pub registered_at_ms: u64,
    pub last_seen_ms: u64,
    pub total_requests: u64,
    pub total_failures: u64,
    pub active_connections: u32,
    pub response_times_ms: VecDeque<u64>,
    pub circuit_breaker_open: bool,
}

impl ServiceInstance {
    pub fn new(
        service_name: impl Into<String>,
        endpoint: ServiceEndpoint,
        now_ms: u64,
    ) -> Result<Self, PlatformError> {
        endpoint.validate()?;
        let service_name = service_name.into();
        if service_name.trim().is_empty() {
            return Err(PlatformError::InvalidConfiguration(
                "service name must not be empty".into(),
            ));
        }
        Ok(Self {
            service_name,
            instance_id: Uuid::new_v4().to_string(),
            endpoint,
            metadata: ServiceMetadata {
                version: "1.0.0".into(),
                environment: "production".into(),
                weight: 100,
                region: "default".into(),
                availability_zone: "default".into(),
                ..ServiceMetadata::default()
            },
            health_check: None,
            status: ServiceStatus::Unknown,
            health_status: HealthStatus::Unknown,
            registered_at_ms: now_ms,
            last_seen_ms: now_ms,
            total_requests: 0,
            total_failures: 0,
            active_connections: 0,
            response_times_ms: VecDeque::new(),
            circuit_breaker_open: false,
        })
    }

    pub fn update_health(&mut self, health: HealthStatus, now_ms: u64) {
        self.health_status = health;
        self.last_seen_ms = now_ms;
        self.status = match health {
            HealthStatus::Healthy => ServiceStatus::Healthy,
            HealthStatus::Unhealthy | HealthStatus::Timeout | HealthStatus::Error => {
                ServiceStatus::Unhealthy
            }
            HealthStatus::Unknown => self.status,
        };
    }

    pub fn record_request(&mut self, response_time_ms: u64, success: bool, now_ms: u64) {
        self.total_requests = self.total_requests.saturating_add(1);
        self.total_failures = self.total_failures.saturating_add(u64::from(!success));
        self.last_seen_ms = now_ms;
        self.response_times_ms.push_back(response_time_ms);
        if self.response_times_ms.len() > 100 {
            self.response_times_ms.pop_front();
        }
    }

    #[must_use]
    #[allow(clippy::cast_precision_loss)]
    pub fn success_rate(&self) -> f64 {
        if self.total_requests == 0 {
            1.0
        } else {
            (self.total_requests - self.total_failures) as f64 / self.total_requests as f64
        }
    }

    #[must_use]
    #[allow(clippy::cast_precision_loss)]
    pub fn average_response_time_ms(&self) -> f64 {
        if self.response_times_ms.is_empty() {
            0.0
        } else {
            self.response_times_ms.iter().sum::<u64>() as f64 / self.response_times_ms.len() as f64
        }
    }

    #[must_use]
    pub const fn is_available(&self) -> bool {
        matches!(self.status, ServiceStatus::Healthy | ServiceStatus::Unknown)
            && matches!(
                self.health_status,
                HealthStatus::Healthy | HealthStatus::Unknown
            )
            && !self.circuit_breaker_open
    }
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct ServiceQuery {
    pub service_name: String,
    pub version: Option<String>,
    pub environment: Option<String>,
    pub zone: Option<String>,
    pub region: Option<String>,
    #[serde(default)]
    pub tags: BTreeSet<String>,
    #[serde(default)]
    pub labels: BTreeMap<String, String>,
    #[serde(default)]
    pub protocols: BTreeSet<EndpointProtocol>,
    pub healthy_only: bool,
}

#[derive(Default)]
pub struct InMemoryRegistry {
    instances: BTreeMap<String, BTreeMap<String, ServiceInstance>>,
}

impl InMemoryRegistry {
    pub fn register(&mut self, instance: ServiceInstance) -> Result<(), PlatformError> {
        let service = self
            .instances
            .entry(instance.service_name.clone())
            .or_default();
        if service.contains_key(&instance.instance_id) {
            return Err(PlatformError::Conflict(instance.instance_id));
        }
        service.insert(instance.instance_id.clone(), instance);
        Ok(())
    }

    pub fn deregister(&mut self, service: &str, instance_id: &str) -> bool {
        self.instances
            .get_mut(service)
            .is_some_and(|instances| instances.remove(instance_id).is_some())
    }

    #[must_use]
    pub fn discover(&self, query: &ServiceQuery) -> Vec<ServiceInstance> {
        self.instances
            .get(&query.service_name)
            .into_iter()
            .flat_map(BTreeMap::values)
            .filter(|instance| !query.healthy_only || instance.is_available())
            .filter(|instance| {
                query
                    .version
                    .as_ref()
                    .is_none_or(|value| &instance.metadata.version == value)
                    && query
                        .environment
                        .as_ref()
                        .is_none_or(|value| &instance.metadata.environment == value)
                    && query
                        .zone
                        .as_ref()
                        .is_none_or(|value| &instance.metadata.availability_zone == value)
                    && query
                        .region
                        .as_ref()
                        .is_none_or(|value| &instance.metadata.region == value)
                    && query.tags.is_subset(&instance.metadata.tags)
                    && query.labels.iter().all(|(key, value)| {
                        instance
                            .metadata
                            .labels
                            .get(key)
                            .is_some_and(|found| found == value)
                    })
                    && (query.protocols.is_empty()
                        || query.protocols.contains(&instance.endpoint.protocol))
            })
            .cloned()
            .collect()
    }

    #[must_use]
    pub fn service_names(&self) -> Vec<String> {
        self.instances.keys().cloned().collect()
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum LoadBalancingStrategy {
    RoundRobin,
    WeightedRoundRobin,
    LeastConnections,
    Random,
    ConsistentHash,
    LocalityAware,
    Adaptive,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct LoadBalancingContext {
    pub hash_key: Option<String>,
    pub client_ip: Option<String>,
    pub session_id: Option<String>,
    pub preferred_zone: Option<String>,
    pub preferred_region: Option<String>,
    #[serde(default)]
    pub excluded_instances: BTreeSet<String>,
}

#[derive(Default)]
pub struct LoadBalancer {
    cursors: BTreeMap<String, u64>,
}

impl LoadBalancer {
    pub fn select(
        &mut self,
        service_name: &str,
        strategy: LoadBalancingStrategy,
        instances: &[ServiceInstance],
        context: &LoadBalancingContext,
    ) -> Result<ServiceInstance, PlatformError> {
        let mut available: Vec<_> = instances
            .iter()
            .filter(|instance| {
                instance.is_available()
                    && !context.excluded_instances.contains(&instance.instance_id)
            })
            .cloned()
            .collect();
        available.sort_by(|left, right| left.instance_id.cmp(&right.instance_id));
        if available.is_empty() {
            return Err(PlatformError::NoHealthyInstance(service_name.into()));
        }
        match strategy {
            LoadBalancingStrategy::RoundRobin => {
                let cursor = self.cursors.entry(service_name.into()).or_default();
                let index = usize::try_from(*cursor % available.len() as u64).unwrap_or(0);
                *cursor = cursor.saturating_add(1);
                Ok(available[index].clone())
            }
            LoadBalancingStrategy::WeightedRoundRobin => {
                let total: u64 = available
                    .iter()
                    .map(|item| u64::from(item.metadata.weight))
                    .sum();
                if total == 0 {
                    return Ok(available[0].clone());
                }
                let cursor = self.cursors.entry(service_name.into()).or_default();
                let target = *cursor % total;
                *cursor = cursor.saturating_add(1);
                let mut cumulative = 0;
                Ok(available
                    .iter()
                    .find(|item| {
                        cumulative += u64::from(item.metadata.weight);
                        target < cumulative
                    })
                    .unwrap_or(&available[0])
                    .clone())
            }
            LoadBalancingStrategy::LeastConnections => available
                .into_iter()
                .min_by_key(|instance| instance.active_connections)
                .ok_or_else(|| PlatformError::NoHealthyInstance(service_name.into())),
            LoadBalancingStrategy::Random => available
                .choose(&mut rand::rng())
                .cloned()
                .ok_or_else(|| PlatformError::NoHealthyInstance(service_name.into())),
            LoadBalancingStrategy::ConsistentHash => {
                let key = context
                    .hash_key
                    .as_deref()
                    .or(context.session_id.as_deref())
                    .or(context.client_ip.as_deref())
                    .unwrap_or(service_name);
                let available_len = u64::try_from(available.len()).unwrap_or(u64::MAX);
                let index = usize::try_from(stable_hash(key) % available_len).unwrap_or(0);
                Ok(available[index].clone())
            }
            LoadBalancingStrategy::LocalityAware => {
                let selected = context
                    .preferred_zone
                    .as_ref()
                    .and_then(|zone| {
                        available
                            .iter()
                            .find(|item| &item.metadata.availability_zone == zone)
                    })
                    .or_else(|| {
                        context.preferred_region.as_ref().and_then(|region| {
                            available
                                .iter()
                                .find(|item| &item.metadata.region == region)
                        })
                    })
                    .unwrap_or(&available[0]);
                Ok(selected.clone())
            }
            LoadBalancingStrategy::Adaptive => available
                .into_iter()
                .max_by(|left, right| {
                    adaptive_score(left)
                        .partial_cmp(&adaptive_score(right))
                        .unwrap_or(std::cmp::Ordering::Equal)
                })
                .ok_or_else(|| PlatformError::NoHealthyInstance(service_name.into())),
        }
    }
}

#[must_use]
pub fn stable_hash(value: &str) -> u64 {
    value
        .as_bytes()
        .iter()
        .fold(14_695_981_039_346_656_037, |hash, byte| {
            (hash ^ u64::from(*byte)).wrapping_mul(1_099_511_628_211)
        })
}

fn adaptive_score(instance: &ServiceInstance) -> f64 {
    let latency_factor = 1.0 / (1.0 + instance.average_response_time_ms());
    let capacity_factor = instance.metadata.max_connections.map_or(1.0, |maximum| {
        1.0 - (f64::from(instance.active_connections) / f64::from(maximum.max(1)))
    });
    instance.success_rate() * latency_factor * capacity_factor.max(0.0)
}
