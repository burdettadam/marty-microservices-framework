use std::cmp::Ordering;
use std::collections::{BTreeMap, BTreeSet};

use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::{SecurityContext, SecurityError};

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PolicyEffect {
    Allow,
    Deny,
}

#[derive(Clone, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
pub struct Permission {
    pub resource: String,
    pub action: String,
}

impl Permission {
    #[must_use]
    pub fn matches(&self, resource: &str, action: &str) -> bool {
        wildcard_matches(&self.resource, resource) && wildcard_matches(&self.action, action)
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Role {
    pub name: String,
    #[serde(default)]
    pub permissions: BTreeSet<Permission>,
    #[serde(default)]
    pub parent_roles: BTreeSet<String>,
}

#[derive(Clone, Debug, Default)]
pub struct RbacEngine {
    roles: BTreeMap<String, Role>,
}

impl RbacEngine {
    pub fn register(&mut self, role: Role) -> Result<(), SecurityError> {
        if role.name.trim().is_empty() || role.parent_roles.contains(&role.name) {
            return Err(SecurityError::InvalidPolicy(
                "invalid role or self inheritance".to_owned(),
            ));
        }
        self.roles.insert(role.name.clone(), role);
        self.validate_acyclic()
    }

    #[must_use]
    pub fn authorize(&self, context: &SecurityContext) -> AuthorizationDecision {
        let mut evaluated = Vec::new();
        for role_name in &context.principal.roles {
            let mut visited = BTreeSet::new();
            if self.role_allows(
                role_name,
                &context.resource,
                &context.action,
                &mut visited,
                &mut evaluated,
            ) {
                return AuthorizationDecision::allow(
                    format!("role '{role_name}' grants permission"),
                    evaluated,
                );
            }
        }
        AuthorizationDecision::deny("no role grants permission", evaluated)
    }

    fn role_allows(
        &self,
        role_name: &str,
        resource: &str,
        action: &str,
        visited: &mut BTreeSet<String>,
        evaluated: &mut Vec<String>,
    ) -> bool {
        if !visited.insert(role_name.to_owned()) {
            return false;
        }
        let Some(role) = self.roles.get(role_name) else {
            return false;
        };
        evaluated.push(format!("rbac:{role_name}"));
        role.permissions
            .iter()
            .any(|permission| permission.matches(resource, action))
            || role
                .parent_roles
                .iter()
                .any(|parent| self.role_allows(parent, resource, action, visited, evaluated))
    }

    fn validate_acyclic(&self) -> Result<(), SecurityError> {
        for name in self.roles.keys() {
            let mut path = BTreeSet::new();
            if self.has_cycle(name, &mut path, &mut BTreeSet::new()) {
                return Err(SecurityError::InvalidPolicy(format!(
                    "role inheritance cycle at {name}"
                )));
            }
        }
        Ok(())
    }

    fn has_cycle(
        &self,
        name: &str,
        path: &mut BTreeSet<String>,
        completed: &mut BTreeSet<String>,
    ) -> bool {
        if completed.contains(name) {
            return false;
        }
        if !path.insert(name.to_owned()) {
            return true;
        }
        let cyclic = self.roles.get(name).is_some_and(|role| {
            role.parent_roles
                .iter()
                .any(|parent| self.has_cycle(parent, path, completed))
        });
        path.remove(name);
        completed.insert(name.to_owned());
        cyclic
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AttributeSource {
    Subject,
    Resource,
    Environment,
    Request,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ConditionOperator {
    Equal,
    NotEqual,
    In,
    NotIn,
    Contains,
    StartsWith,
    EndsWith,
    Regex,
    GreaterThan,
    GreaterThanOrEqual,
    LessThan,
    LessThanOrEqual,
    Exists,
    NotExists,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct AttributeCondition {
    pub source: AttributeSource,
    pub attribute: String,
    pub operator: ConditionOperator,
    #[serde(default)]
    pub value: Value,
}

impl AttributeCondition {
    #[must_use]
    pub fn matches(&self, context: &SecurityContext) -> bool {
        let (attributes, prefix) = match self.source {
            AttributeSource::Subject => (&context.principal.attributes, "principal"),
            AttributeSource::Resource => (&context.resource_attributes, "resource"),
            AttributeSource::Environment => (&context.environment, "environment"),
            AttributeSource::Request => (&context.request_metadata, "request"),
        };
        let actual = nested_attribute(attributes, &self.attribute, prefix);
        evaluate_condition(actual, self.operator, &self.value)
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct AbacPolicy {
    pub id: String,
    pub effect: PolicyEffect,
    pub priority: i32,
    #[serde(default = "enabled")]
    pub enabled: bool,
    #[serde(default)]
    pub resources: Vec<String>,
    #[serde(default)]
    pub actions: Vec<String>,
    #[serde(default)]
    pub conditions: Vec<AttributeCondition>,
}

const fn enabled() -> bool {
    true
}

impl AbacPolicy {
    #[must_use]
    pub fn applies(&self, context: &SecurityContext) -> bool {
        self.enabled
            && (self.resources.is_empty()
                || self
                    .resources
                    .iter()
                    .any(|pattern| wildcard_matches(pattern, &context.resource)))
            && (self.actions.is_empty()
                || self
                    .actions
                    .iter()
                    .any(|pattern| wildcard_matches(pattern, &context.action)))
            && self
                .conditions
                .iter()
                .all(|condition| condition.matches(context))
    }
}

#[derive(Clone, Debug, Default)]
pub struct AbacEngine {
    policies: Vec<AbacPolicy>,
}

impl AbacEngine {
    pub fn replace_policies(&mut self, mut policies: Vec<AbacPolicy>) -> Result<(), SecurityError> {
        let mut ids = BTreeSet::new();
        for policy in &policies {
            if policy.id.trim().is_empty() || !ids.insert(policy.id.clone()) {
                return Err(SecurityError::InvalidPolicy(
                    "policy IDs must be non-empty and unique".to_owned(),
                ));
            }
            for condition in &policy.conditions {
                if condition.operator == ConditionOperator::Regex
                    && condition
                        .value
                        .as_str()
                        .is_none_or(|pattern| Regex::new(pattern).is_err())
                {
                    return Err(SecurityError::InvalidPolicy(format!(
                        "policy '{}' contains an invalid regular expression",
                        policy.id
                    )));
                }
            }
        }
        policies.sort_by(|left, right| right.priority.cmp(&left.priority));
        self.policies = policies;
        Ok(())
    }

    #[must_use]
    pub fn authorize(&self, context: &SecurityContext) -> AuthorizationDecision {
        let applicable = self
            .policies
            .iter()
            .filter(|policy| policy.applies(context))
            .collect::<Vec<_>>();
        let evaluated = applicable
            .iter()
            .map(|policy| format!("abac:{}", policy.id))
            .collect::<Vec<_>>();

        if let Some(policy) = applicable
            .iter()
            .find(|policy| policy.effect == PolicyEffect::Deny)
        {
            return AuthorizationDecision::deny(
                format!("explicit deny by policy '{}'", policy.id),
                evaluated,
            );
        }
        if let Some(policy) = applicable
            .iter()
            .find(|policy| policy.effect == PolicyEffect::Allow)
        {
            return AuthorizationDecision::allow(
                format!("allowed by policy '{}'", policy.id),
                evaluated,
            );
        }
        AuthorizationDecision::deny("no policy allowed the request", evaluated)
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct AuthorizationDecision {
    pub allowed: bool,
    pub reason: String,
    #[serde(default)]
    pub policies_evaluated: Vec<String>,
}

impl AuthorizationDecision {
    #[must_use]
    pub fn allow(reason: impl Into<String>, policies_evaluated: Vec<String>) -> Self {
        Self {
            allowed: true,
            reason: reason.into(),
            policies_evaluated,
        }
    }

    #[must_use]
    pub fn deny(reason: impl Into<String>, policies_evaluated: Vec<String>) -> Self {
        Self {
            allowed: false,
            reason: reason.into(),
            policies_evaluated,
        }
    }
}

fn evaluate_condition(
    actual: Option<&Value>,
    operator: ConditionOperator,
    expected: &Value,
) -> bool {
    match operator {
        ConditionOperator::Exists => actual.is_some(),
        ConditionOperator::NotExists => actual.is_none(),
        ConditionOperator::Equal => actual == Some(expected),
        ConditionOperator::NotEqual => actual != Some(expected),
        ConditionOperator::In => expected
            .as_array()
            .is_some_and(|values| actual.is_some_and(|value| values.contains(value))),
        ConditionOperator::NotIn => expected
            .as_array()
            .is_some_and(|values| actual.is_none_or(|value| !values.contains(value))),
        ConditionOperator::Contains => actual.is_some_and(|value| contains(value, expected)),
        ConditionOperator::StartsWith => {
            string_pair(actual, expected).is_some_and(|(value, prefix)| value.starts_with(prefix))
        }
        ConditionOperator::EndsWith => {
            string_pair(actual, expected).is_some_and(|(value, suffix)| value.ends_with(suffix))
        }
        ConditionOperator::Regex => string_pair(actual, expected)
            .and_then(|(value, pattern)| {
                Regex::new(pattern).ok().map(|regex| regex.is_match(value))
            })
            .unwrap_or(false),
        ConditionOperator::GreaterThan => {
            compare_numbers(actual, expected) == Some(Ordering::Greater)
        }
        ConditionOperator::GreaterThanOrEqual => {
            compare_numbers(actual, expected).is_some_and(|ordering| ordering != Ordering::Less)
        }
        ConditionOperator::LessThan => compare_numbers(actual, expected) == Some(Ordering::Less),
        ConditionOperator::LessThanOrEqual => {
            compare_numbers(actual, expected).is_some_and(|ordering| ordering != Ordering::Greater)
        }
    }
}

fn contains(actual: &Value, expected: &Value) -> bool {
    actual
        .as_array()
        .is_some_and(|items| items.contains(expected))
        || string_pair(Some(actual), expected)
            .is_some_and(|(text, fragment)| text.contains(fragment))
}

fn string_pair<'a>(actual: Option<&'a Value>, expected: &'a Value) -> Option<(&'a str, &'a str)> {
    Some((actual?.as_str()?, expected.as_str()?))
}

fn compare_numbers(actual: Option<&Value>, expected: &Value) -> Option<Ordering> {
    actual?.as_f64()?.partial_cmp(&expected.as_f64()?)
}

fn nested_attribute<'a>(
    attributes: &'a BTreeMap<String, Value>,
    path: &str,
    source_prefix: &str,
) -> Option<&'a Value> {
    if let Some(value) = attributes.get(path) {
        return Some(value);
    }
    let path = path
        .strip_prefix(source_prefix)
        .and_then(|rest| rest.strip_prefix('.'))
        .unwrap_or(path);
    let mut segments = path.split('.');
    let mut value = attributes.get(segments.next()?)?;
    for segment in segments {
        value = value.as_object()?.get(segment)?;
    }
    Some(value)
}

fn wildcard_matches(pattern: &str, value: &str) -> bool {
    let mut expression = String::from("^");
    for character in pattern.chars() {
        match character {
            '*' => expression.push_str(".*"),
            '?' => expression.push('.'),
            other => expression.push_str(&regex::escape(&other.to_string())),
        }
    }
    expression.push('$');
    Regex::new(&expression).is_ok_and(|regex| regex.is_match(value))
}
