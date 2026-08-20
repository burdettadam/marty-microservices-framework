use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::ObservabilityError;

pub const CORRELATION_ID_HEADER: &str = "X-MMF-Correlation-ID";
pub const REQUEST_ID_HEADER: &str = "X-MMF-Request-ID";
pub const USER_ID_HEADER: &str = "X-MMF-User-ID";
pub const SESSION_ID_HEADER: &str = "X-MMF-Session-ID";
pub const PLUGIN_ID_HEADER: &str = "X-MMF-Plugin-ID";
pub const OPERATION_ID_HEADER: &str = "X-MMF-Operation-ID";
pub const TRACE_ID_HEADER: &str = "X-Trace-ID";
pub const SPAN_ID_HEADER: &str = "X-Span-ID";
pub const TRACEPARENT_HEADER: &str = "traceparent";
pub const TRACESTATE_HEADER: &str = "tracestate";
pub const BAGGAGE_HEADER: &str = "baggage";

/// Service correlation values propagated over HTTP, gRPC metadata, events,
/// and structured logs.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct CorrelationContext {
    pub correlation_id: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub request_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub user_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub plugin_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub operation_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub trace_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub span_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub parent_request_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub service_name: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub operation_name: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub plugin_version: Option<String>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub custom_tags: BTreeMap<String, String>,
}

impl Default for CorrelationContext {
    fn default() -> Self {
        Self {
            correlation_id: Uuid::new_v4().to_string(),
            request_id: Some(Uuid::new_v4().to_string()),
            user_id: None,
            session_id: None,
            plugin_id: None,
            operation_id: None,
            trace_id: None,
            span_id: None,
            parent_request_id: None,
            service_name: None,
            operation_name: None,
            plugin_version: None,
            custom_tags: BTreeMap::new(),
        }
    }
}

impl CorrelationContext {
    #[must_use]
    pub fn from_headers(headers: &BTreeMap<String, String>) -> Self {
        let normalized = headers
            .iter()
            .map(|(key, value)| (key.to_ascii_lowercase(), value.clone()))
            .collect::<BTreeMap<_, _>>();
        let get = |name: &str| normalized.get(&name.to_ascii_lowercase()).cloned();
        Self {
            correlation_id: get(CORRELATION_ID_HEADER)
                .unwrap_or_else(|| Uuid::new_v4().to_string()),
            request_id: get(REQUEST_ID_HEADER).or_else(|| Some(Uuid::new_v4().to_string())),
            user_id: get(USER_ID_HEADER),
            session_id: get(SESSION_ID_HEADER),
            plugin_id: get(PLUGIN_ID_HEADER),
            operation_id: get(OPERATION_ID_HEADER),
            trace_id: get(TRACE_ID_HEADER),
            span_id: get(SPAN_ID_HEADER),
            parent_request_id: None,
            service_name: None,
            operation_name: None,
            plugin_version: None,
            custom_tags: BTreeMap::new(),
        }
    }

    #[must_use]
    pub fn to_headers(&self) -> BTreeMap<String, String> {
        let mut headers = BTreeMap::from([(
            CORRELATION_ID_HEADER.to_owned(),
            self.correlation_id.clone(),
        )]);
        insert_optional(&mut headers, REQUEST_ID_HEADER, self.request_id.as_deref());
        insert_optional(&mut headers, USER_ID_HEADER, self.user_id.as_deref());
        insert_optional(&mut headers, SESSION_ID_HEADER, self.session_id.as_deref());
        insert_optional(&mut headers, PLUGIN_ID_HEADER, self.plugin_id.as_deref());
        insert_optional(
            &mut headers,
            OPERATION_ID_HEADER,
            self.operation_id.as_deref(),
        );
        insert_optional(&mut headers, TRACE_ID_HEADER, self.trace_id.as_deref());
        insert_optional(&mut headers, SPAN_ID_HEADER, self.span_id.as_deref());
        headers
    }

    #[must_use]
    pub fn to_log_fields(&self) -> BTreeMap<String, String> {
        let mut fields =
            BTreeMap::from([("correlation_id".to_owned(), self.correlation_id.clone())]);
        insert_optional(&mut fields, "request_id", self.request_id.as_deref());
        insert_optional(&mut fields, "user_id", self.user_id.as_deref());
        insert_optional(&mut fields, "session_id", self.session_id.as_deref());
        insert_optional(&mut fields, "plugin_id", self.plugin_id.as_deref());
        insert_optional(&mut fields, "operation_id", self.operation_id.as_deref());
        insert_optional(&mut fields, "trace_id", self.trace_id.as_deref());
        insert_optional(&mut fields, "span_id", self.span_id.as_deref());
        insert_optional(
            &mut fields,
            "parent_request_id",
            self.parent_request_id.as_deref(),
        );
        insert_optional(&mut fields, "service_name", self.service_name.as_deref());
        insert_optional(
            &mut fields,
            "operation_name",
            self.operation_name.as_deref(),
        );
        insert_optional(
            &mut fields,
            "plugin_version",
            self.plugin_version.as_deref(),
        );
        fields.extend(
            self.custom_tags
                .iter()
                .map(|(key, value)| (format!("tag_{key}"), value.clone())),
        );
        fields
    }

    #[must_use]
    pub fn child(&self, operation_name: impl Into<String>) -> Self {
        Self {
            correlation_id: self.correlation_id.clone(),
            request_id: Some(Uuid::new_v4().to_string()),
            user_id: self.user_id.clone(),
            session_id: self.session_id.clone(),
            plugin_id: self.plugin_id.clone(),
            operation_id: self.operation_id.clone(),
            trace_id: self.trace_id.clone(),
            span_id: self.span_id.clone(),
            parent_request_id: self.request_id.clone(),
            service_name: self.service_name.clone(),
            operation_name: Some(operation_name.into()),
            plugin_version: self.plugin_version.clone(),
            custom_tags: BTreeMap::new(),
        }
    }
}

fn insert_optional(destination: &mut BTreeMap<String, String>, key: &str, value: Option<&str>) {
    if let Some(value) = value {
        destination.insert(key.to_owned(), value.to_owned());
    }
}

/// Strict W3C trace-context representation. Invalid or all-zero identifiers
/// are rejected instead of creating disconnected, misleading traces.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct TraceContext {
    pub version: u8,
    pub trace_id: String,
    pub parent_id: String,
    pub trace_flags: u8,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tracestate: Option<String>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub baggage: BTreeMap<String, String>,
}

impl TraceContext {
    pub fn parse(traceparent: &str) -> Result<Self, ObservabilityError> {
        let parts = traceparent.split('-').collect::<Vec<_>>();
        if parts.len() != 4
            || parts[0].len() != 2
            || parts[1].len() != 32
            || parts[2].len() != 16
            || parts[3].len() != 2
        {
            return Err(ObservabilityError::InvalidTraceContext);
        }
        let version = parse_hex_byte(parts[0])?;
        let trace_flags = parse_hex_byte(parts[3])?;
        if version == u8::MAX
            || !is_lower_hex(parts[1])
            || !is_lower_hex(parts[2])
            || parts[1].bytes().all(|byte| byte == b'0')
            || parts[2].bytes().all(|byte| byte == b'0')
        {
            return Err(ObservabilityError::InvalidTraceContext);
        }
        Ok(Self {
            version,
            trace_id: parts[1].to_owned(),
            parent_id: parts[2].to_owned(),
            trace_flags,
            tracestate: None,
            baggage: BTreeMap::new(),
        })
    }

    #[must_use]
    pub fn traceparent(&self) -> String {
        format!(
            "{:02x}-{}-{}-{:02x}",
            self.version, self.trace_id, self.parent_id, self.trace_flags
        )
    }

    #[must_use]
    pub const fn sampled(&self) -> bool {
        self.trace_flags & 1 == 1
    }

    #[must_use]
    pub fn to_headers(&self) -> BTreeMap<String, String> {
        let mut headers = BTreeMap::from([(TRACEPARENT_HEADER.to_owned(), self.traceparent())]);
        insert_optional(&mut headers, TRACESTATE_HEADER, self.tracestate.as_deref());
        if !self.baggage.is_empty() {
            headers.insert(
                BAGGAGE_HEADER.to_owned(),
                self.baggage
                    .iter()
                    .map(|(key, value)| format!("{key}={value}"))
                    .collect::<Vec<_>>()
                    .join(","),
            );
        }
        headers
    }
}

fn parse_hex_byte(value: &str) -> Result<u8, ObservabilityError> {
    if !is_lower_hex(value) {
        return Err(ObservabilityError::InvalidTraceContext);
    }
    u8::from_str_radix(value, 16).map_err(|_| ObservabilityError::InvalidTraceContext)
}

fn is_lower_hex(value: &str) -> bool {
    value
        .bytes()
        .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}
