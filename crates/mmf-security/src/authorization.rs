use std::collections::{BTreeMap, BTreeSet};
use std::net::IpAddr;

use async_trait::async_trait;
use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::{AuthorizationDecision, PolicyEffect, SecurityContext, SecurityError};

#[derive(Clone, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
pub struct StructuredPermission {
    pub resource_type: String,
    pub resource_id: String,
    pub action: String,
}

impl StructuredPermission {
    pub fn parse(value: &str) -> Result<Self, SecurityError> {
        let parts = value.split(':').collect::<Vec<_>>();
        if parts.len() != 3 || parts.iter().any(|part| part.is_empty()) {
            return Err(SecurityError::InvalidPolicy(format!(
                "invalid permission format: {value}"
            )));
        }
        Ok(Self {
            resource_type: parts[0].to_owned(),
            resource_id: parts[1].to_owned(),
            action: parts[2].to_owned(),
        })
    }

    #[must_use]
    pub fn matches(&self, resource_type: &str, resource_id: &str, action: &str) -> bool {
        glob_matches(&self.resource_type, resource_type)
            && glob_matches(&self.resource_id, resource_id)
            && glob_matches(&self.action, action)
    }
}

impl std::fmt::Display for StructuredPermission {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            formatter,
            "{}:{}:{}",
            self.resource_type, self.resource_id, self.action
        )
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ManagedRole {
    pub name: String,
    pub description: String,
    #[serde(default)]
    pub permissions: BTreeSet<StructuredPermission>,
    #[serde(default)]
    pub parent_roles: BTreeSet<String>,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
    pub created_at_ms: u64,
    #[serde(default)]
    pub system: bool,
    #[serde(default = "default_true")]
    pub active: bool,
}

const fn default_true() -> bool {
    true
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct ManagedRbac {
    roles: BTreeMap<String, ManagedRole>,
    user_roles: BTreeMap<String, BTreeSet<String>>,
}

impl ManagedRbac {
    #[must_use]
    pub fn with_system_roles(created_at_ms: u64) -> Self {
        let mut manager = Self::default();
        for (name, description, permissions) in [
            (
                "admin",
                "System administrator with full access",
                vec![("*", "*", "*")],
            ),
            (
                "service_manager",
                "Can manage services and configurations",
                vec![
                    ("service", "*", "*"),
                    ("config", "*", "read"),
                    ("config", "*", "update"),
                    ("deployment", "*", "*"),
                ],
            ),
            (
                "developer",
                "Developer with read access and limited write access",
                vec![
                    ("service", "*", "read"),
                    ("config", "public", "read"),
                    ("log", "application", "read"),
                    ("metric", "*", "read"),
                ],
            ),
            (
                "viewer",
                "Read-only access to non-sensitive resources",
                vec![
                    ("service", "*", "read"),
                    ("config", "public", "read"),
                    ("metric", "*", "read"),
                ],
            ),
            (
                "service_account",
                "Limited access for automated systems",
                vec![
                    ("service", "own", "read"),
                    ("service", "own", "update"),
                    ("config", "own", "read"),
                ],
            ),
        ] {
            let role = ManagedRole {
                name: name.to_owned(),
                description: description.to_owned(),
                permissions: permissions
                    .into_iter()
                    .map(
                        |(resource_type, resource_id, action)| StructuredPermission {
                            resource_type: resource_type.to_owned(),
                            resource_id: resource_id.to_owned(),
                            action: action.to_owned(),
                        },
                    )
                    .collect(),
                parent_roles: BTreeSet::new(),
                metadata: BTreeMap::new(),
                created_at_ms,
                system: true,
                active: true,
            };
            manager.roles.insert(name.to_owned(), role);
        }
        manager
    }

    pub fn add_role(&mut self, role: ManagedRole) -> Result<(), SecurityError> {
        self.validate_role(&role, None)?;
        if self.roles.contains_key(&role.name) {
            return Err(SecurityError::InvalidPolicy(format!(
                "role '{}' already exists",
                role.name
            )));
        }
        self.roles.insert(role.name.clone(), role);
        self.validate_acyclic()
    }

    pub fn update_role(&mut self, role: ManagedRole) -> Result<(), SecurityError> {
        let current = self.roles.get(&role.name).ok_or_else(|| {
            SecurityError::InvalidPolicy(format!("role '{}' does not exist", role.name))
        })?;
        if current.system && !role.system {
            return Err(SecurityError::InvalidPolicy(
                "system role protection cannot be removed".to_owned(),
            ));
        }
        self.validate_role(&role, Some(&role.name))?;
        let previous = self.roles.insert(role.name.clone(), role);
        if let Err(error) = self.validate_acyclic() {
            if let Some(previous) = previous {
                self.roles.insert(previous.name.clone(), previous);
            }
            return Err(error);
        }
        Ok(())
    }

    pub fn remove_role(&mut self, role_name: &str) -> Result<bool, SecurityError> {
        let Some(role) = self.roles.get(role_name) else {
            return Ok(false);
        };
        if role.system {
            return Err(SecurityError::InvalidPolicy(format!(
                "cannot remove system role: {role_name}"
            )));
        }
        self.roles.remove(role_name);
        for roles in self.user_roles.values_mut() {
            roles.remove(role_name);
        }
        for role in self.roles.values_mut() {
            role.parent_roles.remove(role_name);
        }
        Ok(true)
    }

    pub fn assign(&mut self, user_id: &str, role_name: &str) -> Result<(), SecurityError> {
        if user_id.trim().is_empty() {
            return Err(SecurityError::InvalidIdentity(
                "user ID is required".to_owned(),
            ));
        }
        let role = self.roles.get(role_name).ok_or_else(|| {
            SecurityError::InvalidPolicy(format!("role '{role_name}' does not exist"))
        })?;
        if !role.active {
            return Err(SecurityError::InvalidPolicy(format!(
                "role '{role_name}' is inactive"
            )));
        }
        self.user_roles
            .entry(user_id.to_owned())
            .or_default()
            .insert(role_name.to_owned());
        Ok(())
    }

    #[must_use]
    pub fn unassign(&mut self, user_id: &str, role_name: &str) -> bool {
        self.user_roles
            .get_mut(user_id)
            .is_some_and(|roles| roles.remove(role_name))
    }

    #[must_use]
    pub fn direct_roles(&self, user_id: &str) -> BTreeSet<String> {
        self.user_roles.get(user_id).cloned().unwrap_or_default()
    }

    #[must_use]
    pub fn effective_roles(&self, user_id: &str) -> BTreeSet<String> {
        let mut roles = BTreeSet::new();
        for role in self.direct_roles(user_id) {
            self.collect_roles(&role, &mut roles);
        }
        roles
    }

    #[must_use]
    pub fn permissions(&self, user_id: &str) -> BTreeSet<StructuredPermission> {
        self.effective_roles(user_id)
            .iter()
            .filter_map(|name| self.roles.get(name))
            .flat_map(|role| role.permissions.iter().cloned())
            .collect()
    }

    #[must_use]
    pub fn authorize(
        &self,
        user_id: &str,
        resource_type: &str,
        resource_id: &str,
        action: &str,
    ) -> bool {
        self.permissions(user_id)
            .iter()
            .any(|permission| permission.matches(resource_type, resource_id, action))
    }

    #[must_use]
    pub fn roles(&self) -> &BTreeMap<String, ManagedRole> {
        &self.roles
    }

    fn validate_role(
        &self,
        role: &ManagedRole,
        replacing: Option<&str>,
    ) -> Result<(), SecurityError> {
        if role.name.trim().is_empty() {
            return Err(SecurityError::InvalidPolicy(
                "role name is required".to_owned(),
            ));
        }
        for parent in &role.parent_roles {
            if parent == &role.name
                || (!self.roles.contains_key(parent) && replacing != Some(parent))
            {
                return Err(SecurityError::InvalidPolicy(format!(
                    "invalid parent role '{parent}'"
                )));
            }
        }
        Ok(())
    }

    fn collect_roles(&self, role_name: &str, result: &mut BTreeSet<String>) {
        if !result.insert(role_name.to_owned()) {
            return;
        }
        if let Some(role) = self.roles.get(role_name) {
            for parent in &role.parent_roles {
                self.collect_roles(parent, result);
            }
        }
    }

    fn validate_acyclic(&self) -> Result<(), SecurityError> {
        for name in self.roles.keys() {
            let mut path = BTreeSet::new();
            if self.role_has_cycle(name, &mut path, &mut BTreeSet::new()) {
                return Err(SecurityError::InvalidPolicy(format!(
                    "role inheritance cycle at {name}"
                )));
            }
        }
        Ok(())
    }

    fn role_has_cycle(
        &self,
        name: &str,
        path: &mut BTreeSet<String>,
        done: &mut BTreeSet<String>,
    ) -> bool {
        if done.contains(name) {
            return false;
        }
        if !path.insert(name.to_owned()) {
            return true;
        }
        let cyclic = self.roles.get(name).is_some_and(|role| {
            role.parent_roles
                .iter()
                .any(|parent| self.role_has_cycle(parent, path, done))
        });
        path.remove(name);
        done.insert(name.to_owned());
        cyclic
    }
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct AclConditions {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub time_range: Option<UtcTimeRange>,
    #[serde(default)]
    pub ip_ranges: Vec<String>,
    #[serde(default)]
    pub request_methods: BTreeSet<String>,
    #[serde(default)]
    pub resource_attributes: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct UtcTimeRange {
    pub start: String,
    pub end: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct AclEntry {
    pub resource_pattern: String,
    pub principal: String,
    pub permissions: BTreeSet<String>,
    pub effect: PolicyEffect,
    #[serde(default)]
    pub conditions: AclConditions,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct AclResourceType {
    pub name: String,
    pub pattern: String,
    #[serde(default)]
    pub default_permissions: BTreeSet<String>,
    #[serde(default)]
    pub attributes: BTreeMap<String, String>,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct AclEngine {
    entries: Vec<AclEntry>,
    resource_types: BTreeMap<String, AclResourceType>,
    role_defaults: BTreeMap<String, BTreeSet<String>>,
}

impl AclEngine {
    pub fn replace_entries(&mut self, entries: Vec<AclEntry>) -> Result<(), SecurityError> {
        for entry in &entries {
            validate_acl_entry(entry)?;
        }
        self.entries = entries;
        Ok(())
    }

    pub fn add_entry(&mut self, entry: AclEntry) -> Result<(), SecurityError> {
        validate_acl_entry(&entry)?;
        self.entries.push(entry);
        Ok(())
    }

    #[must_use]
    pub fn remove_entries(&mut self, resource_pattern: &str, principal: &str) -> usize {
        let before = self.entries.len();
        self.entries.retain(|entry| {
            entry.resource_pattern != resource_pattern || entry.principal != principal
        });
        before - self.entries.len()
    }

    pub fn register_resource_type(
        &mut self,
        resource_type: AclResourceType,
    ) -> Result<(), SecurityError> {
        if resource_type.name.trim().is_empty() || !valid_glob(&resource_type.pattern) {
            return Err(SecurityError::InvalidPolicy(
                "invalid ACL resource type".to_owned(),
            ));
        }
        self.resource_types
            .insert(resource_type.name.clone(), resource_type);
        Ok(())
    }

    pub fn set_role_defaults(
        &mut self,
        role: impl Into<String>,
        permissions: BTreeSet<String>,
    ) -> Result<(), SecurityError> {
        let role = role.into();
        if role.trim().is_empty()
            || permissions
                .iter()
                .any(|permission| permission.trim().is_empty())
        {
            return Err(SecurityError::InvalidPolicy(
                "invalid ACL default permissions".to_owned(),
            ));
        }
        self.role_defaults.insert(role, permissions);
        Ok(())
    }

    #[must_use]
    pub fn entries(&self) -> &[AclEntry] {
        &self.entries
    }

    #[must_use]
    pub fn conflicts(&self) -> Vec<String> {
        let mut result = Vec::new();
        for (index, left) in self.entries.iter().enumerate() {
            for right in self.entries.iter().skip(index + 1) {
                if left.resource_pattern == right.resource_pattern
                    && left.principal == right.principal
                    && left.effect != right.effect
                    && !left.permissions.is_disjoint(&right.permissions)
                {
                    result.push(format!(
                        "conflicting ACL rules for {} on {}",
                        left.principal, left.resource_pattern
                    ));
                }
            }
        }
        result
    }

    #[must_use]
    pub fn effective_permissions(&self, context: &SecurityContext) -> BTreeSet<String> {
        let groups = principal_groups(context);
        let mut allowed = BTreeSet::new();
        let mut denied = BTreeSet::new();
        for entry in &self.entries {
            if glob_matches(&entry.resource_pattern, &context.resource)
                && principal_matches(entry, context, &groups)
                && conditions_match(&entry.conditions, context)
            {
                match entry.effect {
                    PolicyEffect::Allow => allowed.extend(entry.permissions.iter().cloned()),
                    PolicyEffect::Deny => denied.extend(entry.permissions.iter().cloned()),
                }
            }
        }
        allowed.retain(|permission| !denied.contains(permission));
        if allowed.is_empty() {
            for role in &context.principal.roles {
                if let Some(permissions) = self.role_defaults.get(role) {
                    allowed.extend(permissions.iter().cloned());
                }
            }
            if let Some(kind) = self.resource_type(&context.resource) {
                allowed.extend(kind.default_permissions.iter().cloned());
            }
        }
        allowed
    }

    #[must_use]
    pub fn authorize(&self, context: &SecurityContext) -> AuthorizationDecision {
        let groups = principal_groups(context);
        let applicable = self
            .entries
            .iter()
            .filter(|entry| {
                glob_matches(&entry.resource_pattern, &context.resource)
                    && principal_matches(entry, context, &groups)
                    && entry
                        .permissions
                        .iter()
                        .any(|permission| glob_matches(permission, &context.action))
                    && conditions_match(&entry.conditions, context)
            })
            .collect::<Vec<_>>();
        let evaluated = applicable
            .iter()
            .map(|entry| format!("acl:{}:{}", entry.principal, entry.resource_pattern))
            .collect();
        if applicable
            .iter()
            .any(|entry| entry.effect == PolicyEffect::Deny)
        {
            return AuthorizationDecision::deny("explicit ACL deny", evaluated);
        }
        if applicable
            .iter()
            .any(|entry| entry.effect == PolicyEffect::Allow)
        {
            return AuthorizationDecision::allow("explicit ACL allow", evaluated);
        }
        let defaults = self.effective_permissions(context);
        if defaults
            .iter()
            .any(|permission| glob_matches(permission, &context.action))
        {
            AuthorizationDecision::allow("ACL default permission", evaluated)
        } else {
            AuthorizationDecision::deny("no ACL rule grants access", evaluated)
        }
    }

    fn resource_type(&self, resource: &str) -> Option<&AclResourceType> {
        self.resource_types
            .values()
            .find(|kind| glob_matches(&kind.pattern, resource))
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CompositeStrategy {
    Any,
    All,
    DenyOverrides,
}

#[must_use]
pub fn combine_decisions(
    strategy: CompositeStrategy,
    decisions: &[AuthorizationDecision],
) -> AuthorizationDecision {
    let policies = decisions
        .iter()
        .flat_map(|decision| decision.policies_evaluated.iter().cloned())
        .collect();
    if decisions.is_empty() {
        return AuthorizationDecision::deny("no authorizers configured", policies);
    }
    match strategy {
        CompositeStrategy::Any => decisions
            .iter()
            .find(|decision| decision.allowed)
            .cloned()
            .unwrap_or_else(|| {
                AuthorizationDecision::deny("all authorizers denied access", policies)
            }),
        CompositeStrategy::All => decisions
            .iter()
            .find(|decision| !decision.allowed)
            .cloned()
            .unwrap_or_else(|| {
                AuthorizationDecision::allow("all authorizers allowed access", policies)
            }),
        CompositeStrategy::DenyOverrides => {
            if decisions.iter().any(|decision| !decision.allowed) {
                AuthorizationDecision::deny("an authorizer explicitly denied access", policies)
            } else {
                AuthorizationDecision::allow("all authorizers allowed access", policies)
            }
        }
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PolicyBackendKind {
    Opa,
    Oso,
    Builtin,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct PolicyBundle {
    pub id: String,
    pub language: String,
    pub source: String,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
}

#[async_trait]
pub trait ExternalPolicyEngine: Send + Sync {
    fn kind(&self) -> PolicyBackendKind;
    async fn load(&self, bundles: &[PolicyBundle]) -> Result<(), SecurityError>;
    async fn validate(&self, bundles: &[PolicyBundle]) -> Result<Vec<String>, SecurityError>;
    async fn authorize(
        &self,
        context: &SecurityContext,
    ) -> Result<AuthorizationDecision, SecurityError>;
}

#[derive(Clone, Debug, Default)]
pub struct UnavailablePolicyEngine;

#[async_trait]
impl ExternalPolicyEngine for UnavailablePolicyEngine {
    fn kind(&self) -> PolicyBackendKind {
        PolicyBackendKind::Builtin
    }

    async fn load(&self, _bundles: &[PolicyBundle]) -> Result<(), SecurityError> {
        Err(SecurityError::RequiredProvidersUnavailable(vec![
            "external_policy_engine",
        ]))
    }

    async fn validate(&self, _bundles: &[PolicyBundle]) -> Result<Vec<String>, SecurityError> {
        Err(SecurityError::RequiredProvidersUnavailable(vec![
            "external_policy_engine",
        ]))
    }

    async fn authorize(
        &self,
        _context: &SecurityContext,
    ) -> Result<AuthorizationDecision, SecurityError> {
        Err(SecurityError::RequiredProvidersUnavailable(vec![
            "external_policy_engine",
        ]))
    }
}

fn validate_acl_entry(entry: &AclEntry) -> Result<(), SecurityError> {
    if entry.resource_pattern.trim().is_empty()
        || entry.principal.trim().is_empty()
        || entry.permissions.is_empty()
        || entry
            .permissions
            .iter()
            .any(|permission| permission.trim().is_empty())
        || !valid_glob(&entry.resource_pattern)
    {
        return Err(SecurityError::InvalidPolicy("invalid ACL entry".to_owned()));
    }
    if let Some(range) = &entry.conditions.time_range {
        parse_hhmm(&range.start)
            .zip(parse_hhmm(&range.end))
            .ok_or_else(|| SecurityError::InvalidPolicy("invalid ACL time range".to_owned()))?;
    }
    for range in &entry.conditions.ip_ranges {
        parse_network(range)?;
    }
    Ok(())
}

fn principal_groups(context: &SecurityContext) -> BTreeSet<String> {
    context
        .principal
        .attributes
        .get("groups")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .map(ToOwned::to_owned)
        .collect()
}

fn principal_matches(
    entry: &AclEntry,
    context: &SecurityContext,
    groups: &BTreeSet<String>,
) -> bool {
    entry.principal == "*"
        || entry.principal == context.principal.id
        || entry
            .principal
            .strip_prefix("role:")
            .is_some_and(|role| context.principal.roles.contains(role))
        || entry
            .principal
            .strip_prefix("group:")
            .is_some_and(|group| groups.contains(group))
}

fn conditions_match(conditions: &AclConditions, context: &SecurityContext) -> bool {
    if let Some(range) = &conditions.time_range {
        let minute = (context.timestamp_ms / 60_000) % (24 * 60);
        let Some((start, end)) = parse_hhmm(&range.start).zip(parse_hhmm(&range.end)) else {
            return false;
        };
        if if start <= end {
            minute < start || minute > end
        } else {
            minute > end && minute < start
        } {
            return false;
        }
    }
    if !conditions.ip_ranges.is_empty() {
        let Some(ip) = context
            .request_metadata
            .get("client_ip")
            .and_then(Value::as_str)
            .and_then(|value| value.parse::<IpAddr>().ok())
        else {
            return false;
        };
        if !conditions
            .ip_ranges
            .iter()
            .any(|network| network_contains(network, ip))
        {
            return false;
        }
    }
    if !conditions.request_methods.is_empty() {
        let Some(method) = context
            .request_metadata
            .get("request_method")
            .and_then(Value::as_str)
        else {
            return false;
        };
        if !conditions
            .request_methods
            .iter()
            .any(|allowed| allowed.eq_ignore_ascii_case(method))
        {
            return false;
        }
    }
    for (name, expected) in &conditions.resource_attributes {
        let actual = context.resource_attributes.get(name).or_else(|| {
            context
                .request_metadata
                .get("resource_attributes")
                .and_then(Value::as_object)
                .and_then(|values| values.get(name))
        });
        let matches = expected
            .as_array()
            .map_or(actual == Some(expected), |values| {
                actual.is_some_and(|actual| values.contains(actual))
            });
        if !matches {
            return false;
        }
    }
    true
}

fn parse_hhmm(value: &str) -> Option<u64> {
    let (hours, minutes) = value.split_once(':')?;
    let hours = hours.parse::<u64>().ok()?;
    let minutes = minutes.parse::<u64>().ok()?;
    (hours < 24 && minutes < 60).then_some(hours * 60 + minutes)
}

fn parse_network(value: &str) -> Result<(IpAddr, u8), SecurityError> {
    let (address, prefix) = value
        .split_once('/')
        .ok_or_else(|| SecurityError::InvalidPolicy(format!("invalid IP range: {value}")))?;
    let address = address
        .parse::<IpAddr>()
        .map_err(|_| SecurityError::InvalidPolicy(format!("invalid IP range: {value}")))?;
    let prefix = prefix
        .parse::<u8>()
        .map_err(|_| SecurityError::InvalidPolicy(format!("invalid IP range: {value}")))?;
    let maximum = if address.is_ipv4() { 32 } else { 128 };
    if prefix > maximum {
        return Err(SecurityError::InvalidPolicy(format!(
            "invalid IP range: {value}"
        )));
    }
    Ok((address, prefix))
}

fn network_contains(network: &str, address: IpAddr) -> bool {
    let Ok((base, prefix)) = parse_network(network) else {
        return false;
    };
    match (base, address) {
        (IpAddr::V4(base), IpAddr::V4(address)) => {
            let mask = if prefix == 0 {
                0
            } else {
                u32::MAX << (32 - prefix)
            };
            u32::from(base) & mask == u32::from(address) & mask
        }
        (IpAddr::V6(base), IpAddr::V6(address)) => {
            let mask = if prefix == 0 {
                0
            } else {
                u128::MAX << (128 - prefix)
            };
            u128::from(base) & mask == u128::from(address) & mask
        }
        _ => false,
    }
}

fn valid_glob(pattern: &str) -> bool {
    glob_regex(pattern).is_some()
}

fn glob_matches(pattern: &str, value: &str) -> bool {
    glob_regex(pattern).is_some_and(|regex| regex.is_match(value))
}

fn glob_regex(pattern: &str) -> Option<Regex> {
    let mut expression = String::from("^");
    for character in pattern.chars() {
        match character {
            '*' => expression.push_str(".*"),
            '?' => expression.push('.'),
            other => expression.push_str(&regex::escape(&other.to_string())),
        }
    }
    expression.push('$');
    Regex::new(&expression).ok()
}
