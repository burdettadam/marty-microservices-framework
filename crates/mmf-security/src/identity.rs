use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::SecurityError;

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AuthenticationMethod {
    Jwt,
    OAuth2,
    Oidc,
    Saml,
    ApiKey,
    Basic,
    MutualTls,
    Mfa,
    Session,
    ServiceIdentity,
    Environment,
    Ldap,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct AuthenticatedUser {
    pub user_id: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub username: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub email: Option<String>,
    #[serde(default)]
    pub roles: BTreeSet<String>,
    #[serde(default)]
    pub permissions: BTreeSet<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub auth_method: Option<AuthenticationMethod>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub expires_at_ms: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub created_at_ms: Option<u64>,
    #[serde(default)]
    pub attributes: BTreeMap<String, Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub user_type: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub applicant_id: Option<String>,
}

impl AuthenticatedUser {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.user_id.trim().is_empty() {
            return Err(SecurityError::InvalidIdentity(
                "user_id cannot be empty".to_owned(),
            ));
        }
        if self
            .username
            .as_deref()
            .is_some_and(|username| username.trim().is_empty())
        {
            return Err(SecurityError::InvalidIdentity(
                "username cannot be empty".to_owned(),
            ));
        }
        if self
            .email
            .as_deref()
            .is_some_and(|email| !looks_like_email(email))
        {
            return Err(SecurityError::InvalidIdentity(
                "invalid email address".to_owned(),
            ));
        }
        if self.created_at_ms == Some(0) {
            return Err(SecurityError::InvalidIdentity(
                "created_at_ms must be greater than zero".to_owned(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn has_role(&self, role: &str) -> bool {
        self.roles.contains(role)
    }

    #[must_use]
    pub fn has_permission(&self, permission: &str) -> bool {
        self.permissions.contains(permission)
    }

    #[must_use]
    pub fn has_any_role<'a>(&self, roles: impl IntoIterator<Item = &'a str>) -> bool {
        roles.into_iter().any(|role| self.has_role(role))
    }

    #[must_use]
    pub fn has_all_roles<'a>(&self, roles: impl IntoIterator<Item = &'a str>) -> bool {
        roles.into_iter().all(|role| self.has_role(role))
    }

    #[must_use]
    pub fn has_any_permission<'a>(&self, permissions: impl IntoIterator<Item = &'a str>) -> bool {
        permissions
            .into_iter()
            .any(|permission| self.has_permission(permission))
    }

    #[must_use]
    pub fn has_all_permissions<'a>(&self, permissions: impl IntoIterator<Item = &'a str>) -> bool {
        permissions
            .into_iter()
            .all(|permission| self.has_permission(permission))
    }

    #[must_use]
    pub fn is_administrator(&self) -> bool {
        self.user_type.as_deref() == Some("administrator") || self.has_role("administrator")
    }

    #[must_use]
    pub fn is_applicant(&self) -> bool {
        self.user_type.as_deref() == Some("applicant") || self.has_role("applicant")
    }

    #[must_use]
    pub fn is_expired_at(&self, now_ms: u64) -> bool {
        self.expires_at_ms.is_some_and(|expires| now_ms > expires)
    }
}

fn looks_like_email(value: &str) -> bool {
    let Some((local, domain)) = value.split_once('@') else {
        return false;
    };
    !local.is_empty()
        && domain
            .rsplit_once('.')
            .is_some_and(|(host, suffix)| !host.is_empty() && suffix.len() >= 2)
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PrincipalType {
    User,
    Service,
    Device,
    Workload,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SecurityPrincipal {
    pub id: String,
    pub principal_type: PrincipalType,
    #[serde(default)]
    pub roles: BTreeSet<String>,
    #[serde(default)]
    pub permissions: BTreeSet<String>,
    #[serde(default)]
    pub attributes: BTreeMap<String, Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub identity_provider: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub expires_at_ms: Option<u64>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SecurityContext {
    pub principal: SecurityPrincipal,
    pub resource: String,
    pub action: String,
    #[serde(default)]
    pub resource_attributes: BTreeMap<String, Value>,
    #[serde(default)]
    pub environment: BTreeMap<String, Value>,
    #[serde(default)]
    pub request_metadata: BTreeMap<String, Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub request_id: Option<String>,
    pub timestamp_ms: u64,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct AuthenticationResult {
    pub success: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub user: Option<AuthenticatedUser>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error_code: Option<String>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

impl AuthenticationResult {
    pub fn validate(&self) -> Result<(), SecurityError> {
        match (self.success, &self.user, &self.error_code) {
            (true, Some(user), None) => user.validate(),
            (false, None, Some(_)) => Ok(()),
            _ => Err(SecurityError::InvalidAuthenticationResult),
        }
    }
}
