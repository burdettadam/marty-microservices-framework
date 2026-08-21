//! Bounded provider-neutral outbound HTTP shared by MMF services.

use std::{
    collections::{BTreeMap, BTreeSet},
    net::{IpAddr, Ipv4Addr, Ipv6Addr, SocketAddr},
    sync::Arc,
    time::Duration,
};

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use url::Url;

use crate::PlatformError;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum OutboundHttpMethod {
    Get,
    Post,
    Put,
    Patch,
    Delete,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct OutboundHttpRequest {
    pub method: OutboundHttpMethod,
    pub url: String,
    #[serde(default)]
    pub headers: BTreeMap<String, String>,
    pub body: Option<Vec<u8>>,
    pub maximum_response_bytes: usize,
}

impl OutboundHttpRequest {
    pub fn validate(&self) -> Result<(), PlatformError> {
        let url = Url::parse(&self.url).map_err(|_| {
            PlatformError::InvalidConfiguration("outbound HTTP URL is invalid".into())
        })?;
        if !matches!(url.scheme(), "http" | "https")
            || url.host_str().is_none()
            || !url.username().is_empty()
            || url.password().is_some()
            || self.maximum_response_bytes == 0
            || self.maximum_response_bytes > 64 * 1024 * 1024
        {
            return Err(PlatformError::InvalidConfiguration(
                "outbound HTTP requires an uncredentialed HTTP(S) URL and a 1..=64 MiB response bound"
                    .into(),
            ));
        }
        for (name, value) in &self.headers {
            reqwest::header::HeaderName::from_bytes(name.as_bytes()).map_err(|_| {
                PlatformError::InvalidConfiguration("outbound HTTP header name is invalid".into())
            })?;
            reqwest::header::HeaderValue::from_str(value).map_err(|_| {
                PlatformError::InvalidConfiguration("outbound HTTP header value is invalid".into())
            })?;
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct OutboundHttpResponse {
    pub status: u16,
    pub headers: BTreeMap<String, String>,
    pub body: Vec<u8>,
}

impl OutboundHttpResponse {
    pub fn json_object(&self, operation: &str) -> Result<serde_json::Value, PlatformError> {
        let value: serde_json::Value = serde_json::from_slice(&self.body)
            .map_err(|_| PlatformError::Operation(format!("{operation} returned invalid JSON")))?;
        if !value.is_object() {
            return Err(PlatformError::Operation(format!(
                "{operation} must return a JSON object"
            )));
        }
        Ok(value)
    }
}

#[async_trait]
pub trait OutboundHttpClient: Send + Sync {
    async fn execute(
        &self,
        request: OutboundHttpRequest,
    ) -> Result<OutboundHttpResponse, PlatformError>;
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct OutboundDestinationPolicy {
    #[serde(default)]
    pub allowed_non_public_hosts: BTreeSet<String>,
}

impl OutboundDestinationPolicy {
    #[must_use]
    pub fn public_https() -> Self {
        Self {
            allowed_non_public_hosts: BTreeSet::new(),
        }
    }

    /// Validates the logical URL and every resolved address before a caller
    /// pins those addresses into its HTTP transport.
    pub fn validate_resolved(
        &self,
        url: &Url,
        addresses: &[SocketAddr],
    ) -> Result<(), PlatformError> {
        let host = url.host_str().ok_or_else(|| {
            PlatformError::InvalidConfiguration("outbound HTTP host is missing".into())
        })?;
        if url.scheme() != "https"
            || url.port().is_some()
            || url.query().is_some()
            || url.fragment().is_some()
            || !url.username().is_empty()
            || url.password().is_some()
            || addresses.is_empty()
        {
            return Err(PlatformError::InvalidConfiguration(
                "outbound destination violates its URL policy".into(),
            ));
        }
        let private_host_is_approved = self
            .allowed_non_public_hosts
            .iter()
            .any(|allowed| allowed.eq_ignore_ascii_case(host));
        if !private_host_is_approved
            && addresses
                .iter()
                .any(|address| !is_public_destination(address.ip()))
        {
            return Err(PlatformError::InvalidConfiguration(
                "outbound destination resolved to a non-public address".into(),
            ));
        }
        Ok(())
    }
}

#[async_trait]
pub trait OutboundHostResolver: Send + Sync {
    async fn resolve(&self, host: &str, port: u16) -> Result<Vec<SocketAddr>, PlatformError>;
}

#[derive(Clone, Copy, Debug, Default)]
pub struct TokioOutboundHostResolver;

#[async_trait]
impl OutboundHostResolver for TokioOutboundHostResolver {
    async fn resolve(&self, host: &str, port: u16) -> Result<Vec<SocketAddr>, PlatformError> {
        let addresses = tokio::net::lookup_host((host, port))
            .await
            .map_err(|error| PlatformError::UpstreamTransport(error.to_string()))?;
        Ok(addresses.collect())
    }
}

#[derive(Clone)]
pub struct ReqwestOutboundHttpClient {
    client: reqwest::Client,
    timeout: Duration,
    destination_policy: Option<OutboundDestinationPolicy>,
    resolver: Arc<dyn OutboundHostResolver>,
}

impl ReqwestOutboundHttpClient {
    pub fn new(timeout: Duration) -> Result<Self, PlatformError> {
        if timeout.is_zero() || timeout > Duration::from_mins(5) {
            return Err(PlatformError::InvalidConfiguration(
                "outbound HTTP timeout must be in 1ms..=300s".into(),
            ));
        }
        Ok(Self {
            client: http_client(timeout, None)?,
            timeout,
            destination_policy: None,
            resolver: Arc::new(TokioOutboundHostResolver),
        })
    }

    pub fn new_guarded(
        timeout: Duration,
        policy: OutboundDestinationPolicy,
    ) -> Result<Self, PlatformError> {
        let mut client = Self::new(timeout)?;
        client.destination_policy = Some(policy);
        Ok(client)
    }

    #[must_use]
    pub fn with_resolver(mut self, resolver: Arc<dyn OutboundHostResolver>) -> Self {
        self.resolver = resolver;
        self
    }

    async fn client_for_request(
        &self,
        request: &OutboundHttpRequest,
    ) -> Result<reqwest::Client, PlatformError> {
        let Some(policy) = &self.destination_policy else {
            return Ok(self.client.clone());
        };
        let url = Url::parse(&request.url).map_err(|_| {
            PlatformError::InvalidConfiguration("outbound HTTP URL is invalid".into())
        })?;
        let host = url.host_str().ok_or_else(|| {
            PlatformError::InvalidConfiguration("outbound HTTP host is missing".into())
        })?;
        let port = url.port_or_known_default().ok_or_else(|| {
            PlatformError::InvalidConfiguration("outbound HTTP port is unknown".into())
        })?;
        let addresses = match host.parse::<IpAddr>() {
            Ok(address) => vec![SocketAddr::new(address, port)],
            Err(_) => self.resolver.resolve(host, port).await?,
        };
        policy.validate_resolved(&url, &addresses)?;
        http_client(self.timeout, Some((host, &addresses)))
    }
}

#[async_trait]
impl OutboundHttpClient for ReqwestOutboundHttpClient {
    async fn execute(
        &self,
        request: OutboundHttpRequest,
    ) -> Result<OutboundHttpResponse, PlatformError> {
        request.validate()?;
        let client = self.client_for_request(&request).await?;
        let method = match request.method {
            OutboundHttpMethod::Get => reqwest::Method::GET,
            OutboundHttpMethod::Post => reqwest::Method::POST,
            OutboundHttpMethod::Put => reqwest::Method::PUT,
            OutboundHttpMethod::Patch => reqwest::Method::PATCH,
            OutboundHttpMethod::Delete => reqwest::Method::DELETE,
        };
        let mut builder = client.request(method, &request.url);
        for (name, value) in &request.headers {
            builder = builder.header(name, value);
        }
        if let Some(body) = request.body {
            builder = builder.body(body);
        }
        let mut response = builder
            .send()
            .await
            .map_err(|error| map_reqwest_error(&error))?;
        if response
            .content_length()
            .is_some_and(|length| length > request.maximum_response_bytes as u64)
        {
            return Err(PlatformError::Operation(
                "outbound HTTP response exceeds its configured bound".into(),
            ));
        }
        let status = response.status().as_u16();
        let headers = response
            .headers()
            .iter()
            .filter_map(|(name, value)| {
                value
                    .to_str()
                    .ok()
                    .map(|value| (name.as_str().to_owned(), value.to_owned()))
            })
            .collect();
        let mut body = Vec::new();
        while let Some(chunk) = response
            .chunk()
            .await
            .map_err(|error| map_reqwest_error(&error))?
        {
            if body.len().saturating_add(chunk.len()) > request.maximum_response_bytes {
                return Err(PlatformError::Operation(
                    "outbound HTTP response exceeds its configured bound".into(),
                ));
            }
            body.extend_from_slice(&chunk);
        }
        Ok(OutboundHttpResponse {
            status,
            headers,
            body,
        })
    }
}

fn http_client(
    timeout: Duration,
    resolution: Option<(&str, &[SocketAddr])>,
) -> Result<reqwest::Client, PlatformError> {
    if timeout.is_zero() || timeout > Duration::from_mins(5) {
        return Err(PlatformError::InvalidConfiguration(
            "outbound HTTP timeout must be in 1ms..=300s".into(),
        ));
    }
    let mut builder = reqwest::Client::builder()
        .timeout(timeout)
        .redirect(reqwest::redirect::Policy::none());
    if let Some((host, addresses)) = resolution {
        builder = builder.resolve_to_addrs(host, addresses);
    }
    builder
        .build()
        .map_err(|error| PlatformError::InvalidConfiguration(error.to_string()))
}

fn is_public_destination(address: IpAddr) -> bool {
    match address {
        IpAddr::V4(address) => is_public_ipv4(address),
        IpAddr::V6(address) => is_public_ipv6(address),
    }
}

fn is_public_ipv4(address: Ipv4Addr) -> bool {
    let octets = address.octets();
    !(address.is_private()
        || address.is_loopback()
        || address.is_link_local()
        || address.is_broadcast()
        || address.is_documentation()
        || address.is_multicast()
        || address.is_unspecified()
        || octets[0] == 0
        || (octets[0] == 100 && (64..=127).contains(&octets[1]))
        || (octets[0] == 198 && (18..=19).contains(&octets[1]))
        || octets[0] >= 240)
}

fn is_public_ipv6(address: Ipv6Addr) -> bool {
    let segments = address.segments();
    !(address.is_loopback()
        || address.is_unspecified()
        || address.is_multicast()
        || (segments[0] & 0xfe00) == 0xfc00
        || (segments[0] & 0xffc0) == 0xfe80
        || (segments[0] == 0x2001 && segments[1] == 0x0db8))
}

fn map_reqwest_error(error: &reqwest::Error) -> PlatformError {
    if error.is_timeout() {
        PlatformError::UpstreamTimeout(error.to_string())
    } else {
        PlatformError::UpstreamTransport(error.to_string())
    }
}
