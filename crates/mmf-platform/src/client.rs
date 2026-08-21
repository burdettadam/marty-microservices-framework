//! Bounded provider-neutral outbound HTTP shared by MMF services.

use std::{collections::BTreeMap, time::Duration};

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

#[derive(Clone)]
pub struct ReqwestOutboundHttpClient {
    client: reqwest::Client,
}

impl ReqwestOutboundHttpClient {
    pub fn new(timeout: Duration) -> Result<Self, PlatformError> {
        if timeout.is_zero() || timeout > Duration::from_mins(5) {
            return Err(PlatformError::InvalidConfiguration(
                "outbound HTTP timeout must be in 1ms..=300s".into(),
            ));
        }
        let client = reqwest::Client::builder()
            .timeout(timeout)
            .redirect(reqwest::redirect::Policy::none())
            .build()
            .map_err(|error| PlatformError::InvalidConfiguration(error.to_string()))?;
        Ok(Self { client })
    }
}

#[async_trait]
impl OutboundHttpClient for ReqwestOutboundHttpClient {
    async fn execute(
        &self,
        request: OutboundHttpRequest,
    ) -> Result<OutboundHttpResponse, PlatformError> {
        request.validate()?;
        let method = match request.method {
            OutboundHttpMethod::Get => reqwest::Method::GET,
            OutboundHttpMethod::Post => reqwest::Method::POST,
            OutboundHttpMethod::Put => reqwest::Method::PUT,
            OutboundHttpMethod::Patch => reqwest::Method::PATCH,
            OutboundHttpMethod::Delete => reqwest::Method::DELETE,
        };
        let mut builder = self.client.request(method, &request.url);
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

fn map_reqwest_error(error: &reqwest::Error) -> PlatformError {
    if error.is_timeout() {
        PlatformError::UpstreamTimeout(error.to_string())
    } else {
        PlatformError::UpstreamTransport(error.to_string())
    }
}
