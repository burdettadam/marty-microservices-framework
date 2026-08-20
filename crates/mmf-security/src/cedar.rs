//! Fail-closed Cedar policy loading and authorization.

use std::{collections::BTreeMap, str::FromStr};

use async_trait::async_trait;
use cedar_policy::{
    Authorizer, Context, Decision, Entities, EntityId, EntityTypeName, EntityUid, PolicySet,
    Request, Schema, ValidationMode, Validator,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::{AuthorizationDecision, PolicyProvider, SecurityContext, SecurityError};

const DEFAULT_MAX_DOCUMENT_BYTES: usize = 1024 * 1024;

fn empty_entities() -> Value {
    Value::Array(Vec::new())
}

/// Entity types used when adapting MMF's provider-neutral security context.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(default)]
pub struct CedarEntityTypes {
    pub principal: String,
    pub action: String,
    pub resource: String,
}

impl Default for CedarEntityTypes {
    fn default() -> Self {
        Self {
            principal: "User".into(),
            action: "Action".into(),
            resource: "Resource".into(),
        }
    }
}

/// Bounded policy-engine configuration. A schema is always required.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(default)]
pub struct CedarConfig {
    pub entity_types: CedarEntityTypes,
    pub max_policy_bytes: usize,
    pub max_schema_bytes: usize,
    pub max_entities_bytes: usize,
    pub max_context_bytes: usize,
}

impl Default for CedarConfig {
    fn default() -> Self {
        Self {
            entity_types: CedarEntityTypes::default(),
            max_policy_bytes: DEFAULT_MAX_DOCUMENT_BYTES,
            max_schema_bytes: DEFAULT_MAX_DOCUMENT_BYTES,
            max_entities_bytes: DEFAULT_MAX_DOCUMENT_BYTES,
            max_context_bytes: DEFAULT_MAX_DOCUMENT_BYTES,
        }
    }
}

impl CedarConfig {
    fn validate(&self) -> Result<(), SecurityError> {
        if self.max_policy_bytes == 0
            || self.max_schema_bytes == 0
            || self.max_entities_bytes == 0
            || self.max_context_bytes == 0
        {
            return Err(SecurityError::InvalidPolicy(
                "Cedar document limits must be nonzero".into(),
            ));
        }
        for (name, value) in [
            ("principal", &self.entity_types.principal),
            ("action", &self.entity_types.action),
            ("resource", &self.entity_types.resource),
        ] {
            EntityTypeName::from_str(value).map_err(|error| {
                SecurityError::InvalidPolicy(format!("invalid Cedar {name} entity type: {error}"))
            })?;
        }
        Ok(())
    }
}

/// A provider-neutral Cedar request with JSON context and entity data.
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct CedarAuthorizationRequest {
    pub principal_type: String,
    pub principal_id: String,
    pub action_type: String,
    pub action_id: String,
    pub resource_type: String,
    pub resource_id: String,
    #[serde(default)]
    pub context: Value,
    #[serde(default = "empty_entities")]
    pub entities: Value,
}

/// Stable diagnostics returned by the canonical Cedar adapter.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct CedarAuthorizationDecision {
    pub allowed: bool,
    pub determining_policies: Vec<String>,
    pub errors: Vec<String>,
}

/// A validated and immutable Cedar policy set.
#[derive(Clone, Debug)]
pub struct CedarPolicyEngine {
    policies: PolicySet,
    schema: Schema,
    config: CedarConfig,
}

impl CedarPolicyEngine {
    /// Parse and validate a Cedar policy and JSON schema before accepting traffic.
    pub fn from_json_schema(
        policy_source: &str,
        schema: Value,
        config: CedarConfig,
    ) -> Result<Self, SecurityError> {
        config.validate()?;
        check_text_size("policy", policy_source, config.max_policy_bytes)?;
        check_json_size("schema", &schema, config.max_schema_bytes)?;
        if policy_source.trim().is_empty() {
            return Err(SecurityError::InvalidPolicy(
                "Cedar policy document must not be empty".into(),
            ));
        }
        let policies = PolicySet::from_str(policy_source).map_err(|error| {
            SecurityError::InvalidPolicy(format!("invalid Cedar policy: {error}"))
        })?;
        let schema = Schema::from_json_value(schema).map_err(|error| {
            SecurityError::InvalidPolicy(format!("invalid Cedar schema: {error}"))
        })?;
        let validation = Validator::new(schema.clone()).validate(&policies, ValidationMode::Strict);
        if !validation.validation_passed() {
            let errors = validation
                .validation_errors()
                .map(ToString::to_string)
                .collect::<Vec<_>>()
                .join("; ");
            return Err(SecurityError::InvalidPolicy(format!(
                "Cedar policy failed schema validation: {errors}"
            )));
        }
        Ok(Self {
            policies,
            schema,
            config,
        })
    }

    /// Evaluate one request. Invalid request data is an error, never an allow.
    pub fn authorize_request(
        &self,
        request: CedarAuthorizationRequest,
    ) -> Result<CedarAuthorizationDecision, SecurityError> {
        check_json_size(
            "entities",
            &request.entities,
            self.config.max_entities_bytes,
        )?;
        check_json_size("context", &request.context, self.config.max_context_bytes)?;

        let principal = entity_uid(&request.principal_type, &request.principal_id)?;
        let action = entity_uid(&request.action_type, &request.action_id)?;
        let resource = entity_uid(&request.resource_type, &request.resource_id)?;
        let entities =
            Entities::from_json_value(request.entities, Some(&self.schema)).map_err(|error| {
                SecurityError::Authorization(format!("invalid Cedar entities: {error}"))
            })?;
        let context = Context::from_json_value(request.context, Some((&self.schema, &action)))
            .map_err(|error| {
                SecurityError::Authorization(format!("invalid Cedar context: {error}"))
            })?;
        let request = Request::new(principal, action, resource, context, Some(&self.schema))
            .map_err(|error| {
                SecurityError::Authorization(format!("invalid Cedar request: {error}"))
            })?;
        let response = Authorizer::new().is_authorized(&request, &self.policies, &entities);
        let mut determining_policies = response
            .diagnostics()
            .reason()
            .map(ToString::to_string)
            .collect::<Vec<_>>();
        determining_policies.sort();
        let mut errors = response
            .diagnostics()
            .errors()
            .map(ToString::to_string)
            .collect::<Vec<_>>();
        errors.sort();
        Ok(CedarAuthorizationDecision {
            allowed: response.decision() == Decision::Allow && errors.is_empty(),
            determining_policies,
            errors,
        })
    }

    fn provider_request(&self, context: &SecurityContext) -> CedarAuthorizationRequest {
        let mut cedar_context = BTreeMap::new();
        cedar_context.extend(context.environment.clone());
        for (key, value) in &context.request_metadata {
            cedar_context
                .entry(key.clone())
                .or_insert_with(|| value.clone());
        }
        CedarAuthorizationRequest {
            principal_type: self.config.entity_types.principal.clone(),
            principal_id: context.principal.id.clone(),
            action_type: self.config.entity_types.action.clone(),
            action_id: context.action.clone(),
            resource_type: self.config.entity_types.resource.clone(),
            resource_id: context.resource.clone(),
            context: Value::Object(cedar_context.into_iter().collect()),
            entities: empty_entities(),
        }
    }
}

#[async_trait]
impl PolicyProvider for CedarPolicyEngine {
    async fn authorize(
        &self,
        context: &SecurityContext,
    ) -> Result<AuthorizationDecision, SecurityError> {
        let decision = self.authorize_request(self.provider_request(context))?;
        if !decision.errors.is_empty() {
            return Err(SecurityError::Authorization(format!(
                "Cedar evaluation failed: {}",
                decision.errors.join("; ")
            )));
        }
        let reason = if decision.allowed {
            "Cedar policy allowed the request"
        } else {
            "Cedar policy denied the request"
        };
        Ok(if decision.allowed {
            AuthorizationDecision::allow(reason, decision.determining_policies)
        } else {
            AuthorizationDecision::deny(reason, decision.determining_policies)
        })
    }
}

fn entity_uid(entity_type: &str, entity_id: &str) -> Result<EntityUid, SecurityError> {
    let entity_type = EntityTypeName::from_str(entity_type).map_err(|error| {
        SecurityError::Authorization(format!("invalid Cedar entity type: {error}"))
    })?;
    let entity_id = EntityId::from_str(entity_id).map_err(|error| {
        SecurityError::Authorization(format!("invalid Cedar entity id: {error}"))
    })?;
    Ok(EntityUid::from_type_name_and_id(entity_type, entity_id))
}

fn check_text_size(name: &str, value: &str, maximum: usize) -> Result<(), SecurityError> {
    if value.len() > maximum {
        return Err(SecurityError::InvalidPolicy(format!(
            "Cedar {name} exceeds the {maximum}-byte limit"
        )));
    }
    Ok(())
}

fn check_json_size(name: &str, value: &Value, maximum: usize) -> Result<(), SecurityError> {
    let size = serde_json::to_vec(value)
        .map_err(|error| SecurityError::InvalidPolicy(format!("invalid Cedar {name}: {error}")))?
        .len();
    if size > maximum {
        return Err(SecurityError::InvalidPolicy(format!(
            "Cedar {name} exceeds the {maximum}-byte limit"
        )));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Deserialize)]
    struct Fixture {
        schema_version: u32,
        cedar: CedarFixture,
    }

    #[derive(Deserialize)]
    struct CedarFixture {
        schema: Value,
        policy: String,
        cases: Vec<CedarCase>,
    }

    #[derive(Deserialize)]
    struct CedarCase {
        principal_id: String,
        resource_id: String,
        tenant: String,
        allowed: bool,
    }

    fn fixture() -> Fixture {
        serde_json::from_str(include_str!(
            "../../../contracts/gateway-runtime-behavior.json"
        ))
        .expect("valid gateway runtime fixture")
    }

    #[test]
    fn language_neutral_cedar_contract() {
        let fixture = fixture();
        assert_eq!(fixture.schema_version, 1);
        let engine = CedarPolicyEngine::from_json_schema(
            &fixture.cedar.policy,
            fixture.cedar.schema,
            CedarConfig::default(),
        )
        .expect("valid policy engine");
        for case in fixture.cedar.cases {
            let decision = engine
                .authorize_request(CedarAuthorizationRequest {
                    principal_type: "User".into(),
                    principal_id: case.principal_id,
                    action_type: "Action".into(),
                    action_id: "read".into(),
                    resource_type: "Document".into(),
                    resource_id: case.resource_id,
                    context: serde_json::json!({"tenant": case.tenant}),
                    entities: empty_entities(),
                })
                .expect("authorization decision");
            assert_eq!(decision.allowed, case.allowed);
        }
    }

    #[test]
    fn invalid_policy_schema_context_and_limits_fail_closed() {
        let fixture = fixture();
        assert!(
            CedarPolicyEngine::from_json_schema(
                "permit(",
                fixture.cedar.schema.clone(),
                CedarConfig::default(),
            )
            .is_err()
        );
        assert!(
            CedarPolicyEngine::from_json_schema(
                &fixture.cedar.policy,
                Value::Null,
                CedarConfig::default(),
            )
            .is_err()
        );
        let engine = CedarPolicyEngine::from_json_schema(
            &fixture.cedar.policy,
            fixture.cedar.schema,
            CedarConfig::default(),
        )
        .expect("valid policy engine");
        let invalid = CedarAuthorizationRequest {
            principal_type: "User".into(),
            principal_id: "alice".into(),
            action_type: "Action".into(),
            action_id: "read".into(),
            resource_type: "Document".into(),
            resource_id: "doc-1".into(),
            context: serde_json::json!({"tenant": 42}),
            entities: empty_entities(),
        };
        assert!(engine.authorize_request(invalid).is_err());
    }

    #[test]
    fn evaluation_diagnostics_are_structured_and_never_allow() {
        let schema = serde_json::json!({
            "": {
                "entityTypes": {
                    "User": {
                        "shape": {
                            "type": "Record",
                            "attributes": {
                                "level": {"type": "String", "required": true}
                            },
                            "additionalAttributes": false
                        }
                    },
                    "Document": {}
                },
                "actions": {
                    "read": {
                        "appliesTo": {
                            "principalTypes": ["User"],
                            "resourceTypes": ["Document"],
                            "context": {"type": "Record", "attributes": {}, "additionalAttributes": false}
                        }
                    }
                }
            }
        });
        let engine = CedarPolicyEngine::from_json_schema(
            "permit(principal, action, resource) when { principal.level == \"admin\" };",
            schema,
            CedarConfig::default(),
        )
        .expect("valid policy engine");
        let decision = engine
            .authorize_request(CedarAuthorizationRequest {
                principal_type: "User".into(),
                principal_id: "missing".into(),
                action_type: "Action".into(),
                action_id: "read".into(),
                resource_type: "Document".into(),
                resource_id: "doc-1".into(),
                context: serde_json::json!({}),
                entities: empty_entities(),
            })
            .expect("structured fail-closed decision");
        assert!(!decision.allowed);
        assert!(!decision.errors.is_empty());
    }
}
