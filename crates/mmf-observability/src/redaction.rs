use std::collections::BTreeSet;

use serde::{Deserialize, Serialize};
use serde_json::Value;

/// Recursive structured-data redaction used before data reaches any sink.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(default)]
pub struct RedactionPolicy {
    pub replacement: String,
    pub sensitive_key_fragments: BTreeSet<String>,
}

impl Default for RedactionPolicy {
    fn default() -> Self {
        Self {
            replacement: "[REDACTED]".to_owned(),
            sensitive_key_fragments: [
                "authorization",
                "client_secret",
                "cookie",
                "credential_jwt",
                "password",
                "private_key",
                "refresh_token",
                "secret",
                "session",
                "token",
                "verifiable_credential",
            ]
            .into_iter()
            .map(str::to_owned)
            .collect(),
        }
    }
}

impl RedactionPolicy {
    #[must_use]
    pub fn redact(&self, value: &Value) -> Value {
        match value {
            Value::Object(object) => Value::Object(
                object
                    .iter()
                    .map(|(key, value)| {
                        let value = if self.is_sensitive_key(key) {
                            Value::String(self.replacement.clone())
                        } else {
                            self.redact(value)
                        };
                        (key.clone(), value)
                    })
                    .collect(),
            ),
            Value::Array(values) => {
                Value::Array(values.iter().map(|value| self.redact(value)).collect())
            }
            Value::String(text) if looks_like_secret(text) => {
                Value::String(self.replacement.clone())
            }
            other => other.clone(),
        }
    }

    #[must_use]
    pub fn is_sensitive_key(&self, key: &str) -> bool {
        let normalized = key.to_ascii_lowercase().replace('-', "_");
        self.sensitive_key_fragments
            .iter()
            .any(|fragment| normalized.contains(fragment))
    }
}

fn looks_like_secret(value: &str) -> bool {
    let trimmed = value.trim();
    trimmed
        .get(..7)
        .is_some_and(|prefix| prefix.eq_ignore_ascii_case("bearer "))
        || trimmed.starts_with("-----BEGIN PRIVATE KEY-----")
        || trimmed.starts_with("-----BEGIN ENCRYPTED PRIVATE KEY-----")
}
