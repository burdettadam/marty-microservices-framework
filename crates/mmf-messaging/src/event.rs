use std::collections::{BTreeMap, BTreeSet};
use std::sync::RwLock;

use serde::{Deserialize, Serialize};

use crate::{EventKind, Message, MessagePriority, MessagingError};

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct EventFilter {
    #[serde(default)]
    pub message_types: BTreeSet<String>,
    #[serde(default)]
    pub kinds: BTreeSet<EventKind>,
    pub source_service: Option<String>,
    pub tenant_id: Option<String>,
    pub minimum_priority: Option<MessagePriority>,
    #[serde(default)]
    pub required_headers: BTreeMap<String, String>,
}

impl EventFilter {
    #[must_use]
    pub fn matches(&self, message: &Message) -> bool {
        (self.message_types.is_empty() || self.message_types.contains(&message.message_type))
            && (self.kinds.is_empty() || self.kinds.contains(&message.kind))
            && self
                .source_service
                .as_ref()
                .is_none_or(|source| message.metadata.source_service.as_ref() == Some(source))
            && self
                .tenant_id
                .as_ref()
                .is_none_or(|tenant| message.metadata.tenant_id.as_ref() == Some(tenant))
            && self
                .minimum_priority
                .is_none_or(|priority| message.priority >= priority)
            && self.required_headers.iter().all(|(key, value)| {
                message
                    .metadata
                    .headers
                    .get(key)
                    .is_some_and(|found| found == value)
            })
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct EventTypeRegistration {
    pub message_type: String,
    pub kind: EventKind,
    pub schema_version: u32,
    pub plugin_id: Option<String>,
}

#[derive(Default)]
pub struct EventRegistry {
    registrations: RwLock<BTreeMap<String, EventTypeRegistration>>,
}

impl EventRegistry {
    pub fn register(&self, registration: EventTypeRegistration) -> Result<(), MessagingError> {
        if registration.message_type.trim().is_empty() || registration.schema_version == 0 {
            return Err(MessagingError::InvalidConfiguration(
                "event registration requires a type and nonzero schema version".into(),
            ));
        }
        let key = registration.message_type.clone();
        let mut registrations = self
            .registrations
            .write()
            .map_err(|error| MessagingError::Storage(error.to_string()))?;
        if registrations.contains_key(&key) {
            return Err(MessagingError::InvalidConfiguration(format!(
                "event type {key} is already registered"
            )));
        }
        registrations.insert(key, registration);
        Ok(())
    }

    pub fn unregister_plugin(&self, plugin_id: &str) -> Result<usize, MessagingError> {
        let mut registrations = self
            .registrations
            .write()
            .map_err(|error| MessagingError::Storage(error.to_string()))?;
        let before = registrations.len();
        registrations.retain(|_, value| value.plugin_id.as_deref() != Some(plugin_id));
        Ok(before - registrations.len())
    }

    pub fn get(&self, message_type: &str) -> Result<Option<EventTypeRegistration>, MessagingError> {
        self.registrations
            .read()
            .map(|items| items.get(message_type).cloned())
            .map_err(|error| MessagingError::Storage(error.to_string()))
    }

    pub fn list(&self) -> Result<Vec<EventTypeRegistration>, MessagingError> {
        self.registrations
            .read()
            .map(|items| items.values().cloned().collect())
            .map_err(|error| MessagingError::Storage(error.to_string()))
    }
}
