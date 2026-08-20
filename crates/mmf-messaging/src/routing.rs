use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

use crate::{Message, MessagingError};

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MatchType {
    Exact,
    Prefix,
    Suffix,
    Contains,
    Wildcard,
    Headers,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct RoutingRule {
    pub name: String,
    pub pattern: String,
    pub match_type: MatchType,
    pub topic: String,
    pub routing_key: String,
    pub priority: i32,
    #[serde(default)]
    pub headers: BTreeMap<String, String>,
}

impl RoutingRule {
    #[must_use]
    pub fn matches(&self, message: &Message) -> bool {
        match self.match_type {
            MatchType::Exact => message.routing_key == self.pattern,
            MatchType::Prefix => message.routing_key.starts_with(&self.pattern),
            MatchType::Suffix => message.routing_key.ends_with(&self.pattern),
            MatchType::Contains => message.routing_key.contains(&self.pattern),
            MatchType::Wildcard => wildcard_matches(&self.pattern, &message.routing_key),
            MatchType::Headers => self.headers.iter().all(|(key, value)| {
                message
                    .metadata
                    .headers
                    .get(key)
                    .is_some_and(|found| found == value)
            }),
        }
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Route {
    pub topic: String,
    pub routing_key: String,
    pub matched_rule: Option<String>,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct Router {
    pub default_topic: String,
    pub default_routing_key: String,
    #[serde(default)]
    rules: Vec<RoutingRule>,
}

impl Router {
    #[must_use]
    pub fn new(default_topic: impl Into<String>, default_routing_key: impl Into<String>) -> Self {
        Self {
            default_topic: default_topic.into(),
            default_routing_key: default_routing_key.into(),
            rules: Vec::new(),
        }
    }

    pub fn add_rule(&mut self, rule: RoutingRule) -> Result<(), MessagingError> {
        if rule.name.trim().is_empty() || rule.topic.trim().is_empty() {
            return Err(MessagingError::InvalidConfiguration(
                "routing rules require a name and topic".into(),
            ));
        }
        self.rules.retain(|item| item.name != rule.name);
        self.rules.push(rule);
        self.rules.sort_by(|left, right| {
            right
                .priority
                .cmp(&left.priority)
                .then(left.name.cmp(&right.name))
        });
        Ok(())
    }

    pub fn remove_rule(&mut self, name: &str) -> bool {
        let before = self.rules.len();
        self.rules.retain(|rule| rule.name != name);
        before != self.rules.len()
    }

    #[must_use]
    pub fn rules(&self) -> &[RoutingRule] {
        &self.rules
    }

    pub fn route(&self, message: &Message) -> Result<Route, MessagingError> {
        if let Some(rule) = self.rules.iter().find(|rule| rule.matches(message)) {
            return Ok(Route {
                topic: rule.topic.clone(),
                routing_key: rule.routing_key.clone(),
                matched_rule: Some(rule.name.clone()),
            });
        }
        let topic = if self.default_topic.is_empty() {
            message.topic.clone()
        } else {
            self.default_topic.clone()
        };
        let routing_key = if self.default_routing_key.is_empty() {
            message.routing_key.clone()
        } else {
            self.default_routing_key.clone()
        };
        if topic.is_empty() {
            return Err(MessagingError::Unroutable(
                message.metadata.message_id.clone(),
            ));
        }
        Ok(Route {
            topic,
            routing_key,
            matched_rule: None,
        })
    }
}

#[must_use]
pub fn wildcard_matches(pattern: &str, value: &str) -> bool {
    let pattern: Vec<char> = pattern.chars().collect();
    let value: Vec<char> = value.chars().collect();
    let (mut pattern_index, mut value_index, mut star, mut retry) = (0, 0, None, 0);
    while value_index < value.len() {
        if pattern_index < pattern.len()
            && (pattern[pattern_index] == '?' || pattern[pattern_index] == value[value_index])
        {
            pattern_index += 1;
            value_index += 1;
        } else if pattern_index < pattern.len() && pattern[pattern_index] == '*' {
            star = Some(pattern_index);
            retry = value_index;
            pattern_index += 1;
        } else if let Some(star_index) = star {
            pattern_index = star_index + 1;
            retry += 1;
            value_index = retry;
        } else {
            return false;
        }
    }
    while pattern_index < pattern.len() && pattern[pattern_index] == '*' {
        pattern_index += 1;
    }
    pattern_index == pattern.len()
}
