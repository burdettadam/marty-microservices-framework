//! Canonical Cedar authorization for verified credential evidence.

use serde::{Deserialize, Serialize};
use serde_json::json;

use crate::{
    CedarAuthorizationDecision, CedarAuthorizationRequest, CedarConfig, CedarPolicyEngine,
    SecurityError,
};

const SCHEMA: &str = r#"
namespace MIP {
  type CredentialContext = {
    credential_format: String,
    compliance_code: String,
    issuer_id: String,
    issuer_trust_level: Long,
    credential_age_seconds: Long,
    revocation_checked: Bool,
    revocation_required: Bool,
    is_revoked: Bool,
    is_expired: Bool,
    holder_binding_present: Bool,
    algorithm: String,
  };

  entity Organization {};
  entity User in [Organization] { email: String, status: String };
  entity Credential in [Organization] {
    format: String,
    status: String,
    compliance_code: String,
    issuer_id: String,
    trust_level: Long,
  };

  action "credentials:verify" appliesTo {
    principal: [User],
    resource: [Credential],
    context: CredentialContext,
  };
}
"#;

const POLICIES: &str = r#"
@id("permit-valid-credentials")
permit (principal, action == MIP::Action::"credentials:verify", resource)
when {
  !context.is_revoked &&
  !context.is_expired &&
  context.issuer_trust_level >= 50
};

@id("deny-revoked-credentials")
forbid (principal, action == MIP::Action::"credentials:verify", resource)
when { context.is_revoked };

@id("deny-expired-credentials")
forbid (principal, action == MIP::Action::"credentials:verify", resource)
when { context.is_expired };

@id("deny-untrusted-issuers")
forbid (principal, action == MIP::Action::"credentials:verify", resource)
when { context.issuer_trust_level < 10 };

@id("icao-dtc-format-requirement")
forbid (principal, action == MIP::Action::"credentials:verify", resource)
when {
  context.compliance_code == "ICAO_DTC" &&
  context.credential_format != "MDOC"
};

@id("icao-dtc-holder-binding")
forbid (principal, action == MIP::Action::"credentials:verify", resource)
when {
  context.compliance_code == "ICAO_DTC" &&
  !context.holder_binding_present
};

@id("aamva-mdl-format-requirement")
forbid (principal, action == MIP::Action::"credentials:verify", resource)
when {
  context.compliance_code == "AAMVA_MDL" &&
  context.credential_format != "MDOC"
};

@id("aamva-mdl-holder-binding")
forbid (principal, action == MIP::Action::"credentials:verify", resource)
when {
  context.compliance_code == "AAMVA_MDL" &&
  !context.holder_binding_present
};

@id("eudi-pid-format-requirement")
forbid (principal, action == MIP::Action::"credentials:verify", resource)
when {
  context.compliance_code == "EUDI_PID" &&
  context.credential_format != "SD_JWT_VC"
};

@id("eudi-pid-holder-binding")
forbid (principal, action == MIP::Action::"credentials:verify", resource)
when {
  context.compliance_code == "EUDI_PID" &&
  !context.holder_binding_present
};

@id("deny-weak-algorithms")
forbid (principal, action == MIP::Action::"credentials:verify", resource)
when { context.algorithm == "RS256" || context.algorithm == "RS384" };

@id("high-assurance-freshness")
forbid (principal, action == MIP::Action::"credentials:verify", resource)
when {
  (context.compliance_code == "ICAO_DTC" ||
   context.compliance_code == "AAMVA_MDL" ||
   context.compliance_code == "EUDI_PID") &&
  context.credential_age_seconds > 86400
};
"#;

/// Verified, verifier-owned facts accepted by the bundled credential policy.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
#[allow(clippy::struct_excessive_bools)]
pub struct CredentialVerificationAuthorizationFacts {
    pub organization_id: String,
    pub credential_format: String,
    pub compliance_code: String,
    pub issuer_id: String,
    pub issuer_trust_level: u32,
    pub credential_age_seconds: u64,
    pub revocation_checked: bool,
    pub revocation_required: bool,
    pub is_revoked: bool,
    pub is_expired: bool,
    pub holder_binding_present: bool,
    pub algorithm: String,
}

/// Immutable, feature-complete credential-verification Cedar preset.
#[derive(Clone, Debug)]
pub struct CredentialVerificationPolicyEngine {
    cedar: CedarPolicyEngine,
}

impl CredentialVerificationPolicyEngine {
    /// Load and strictly validate the bundled schema and policies.
    pub fn new() -> Result<Self, SecurityError> {
        Ok(Self {
            cedar: CedarPolicyEngine::from_human_schema(POLICIES, SCHEMA, CedarConfig::default())?,
        })
    }

    /// Evaluate authenticated evidence. Invalid or incomplete facts are errors, never permits.
    pub fn authorize(
        &self,
        facts: &CredentialVerificationAuthorizationFacts,
    ) -> Result<CedarAuthorizationDecision, SecurityError> {
        validate_facts(facts)?;
        let trust_level = i64::from(facts.issuer_trust_level);
        let credential_age_seconds = i64::try_from(facts.credential_age_seconds).map_err(|_| {
            SecurityError::Authorization("credential age exceeds Cedar Long range".into())
        })?;
        self.cedar.authorize_request(CedarAuthorizationRequest {
            principal_type: "MIP::User".into(),
            principal_id: "verifier".into(),
            action_type: "MIP::Action".into(),
            action_id: "credentials:verify".into(),
            resource_type: "MIP::Credential".into(),
            resource_id: "presented-credential".into(),
            context: json!({
                "credential_format": facts.credential_format,
                "compliance_code": facts.compliance_code,
                "issuer_id": facts.issuer_id,
                "issuer_trust_level": trust_level,
                "credential_age_seconds": credential_age_seconds,
                "revocation_checked": facts.revocation_checked,
                "revocation_required": facts.revocation_required,
                "is_revoked": facts.is_revoked,
                "is_expired": facts.is_expired,
                "holder_binding_present": facts.holder_binding_present,
                "algorithm": facts.algorithm,
            }),
            entities: json!([
                {
                    "uid": {"type": "MIP::User", "id": "verifier"},
                    "attrs": {"email": "", "status": "ACTIVE"},
                    "parents": [{"type": "MIP::Organization", "id": facts.organization_id}]
                },
                {
                    "uid": {"type": "MIP::Organization", "id": facts.organization_id},
                    "attrs": {},
                    "parents": []
                },
                {
                    "uid": {"type": "MIP::Credential", "id": "presented-credential"},
                    "attrs": {
                        "format": facts.credential_format,
                        "status": "ACTIVE",
                        "compliance_code": facts.compliance_code,
                        "issuer_id": facts.issuer_id,
                        "trust_level": trust_level
                    },
                    "parents": [{"type": "MIP::Organization", "id": facts.organization_id}]
                }
            ]),
        })
    }
}

impl Default for CredentialVerificationPolicyEngine {
    fn default() -> Self {
        Self::new().expect("bundled credential-verification Cedar policy must be valid")
    }
}

fn validate_facts(facts: &CredentialVerificationAuthorizationFacts) -> Result<(), SecurityError> {
    for (name, value) in [
        ("organization_id", facts.organization_id.as_str()),
        ("credential_format", facts.credential_format.as_str()),
        ("compliance_code", facts.compliance_code.as_str()),
        ("issuer_id", facts.issuer_id.as_str()),
        ("algorithm", facts.algorithm.as_str()),
    ] {
        if value.trim().is_empty() || value.len() > 4_096 {
            return Err(SecurityError::Authorization(format!(
                "credential authorization {name} must be non-empty and bounded"
            )));
        }
    }
    if facts.issuer_trust_level > 100 {
        return Err(SecurityError::Authorization(
            "credential authorization trust level must be between 0 and 100".into(),
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Value;

    #[derive(Deserialize)]
    struct Contract {
        schema_version: u32,
        base_facts: CredentialVerificationAuthorizationFacts,
        cases: Vec<Case>,
    }

    #[derive(Deserialize)]
    struct Case {
        name: String,
        patch: Value,
        allowed: bool,
    }

    #[test]
    fn language_neutral_credential_verification_contract() {
        let contract: Contract = serde_json::from_str(include_str!(
            "../../../contracts/credential-verification-authorization-behavior.json"
        ))
        .unwrap();
        assert_eq!(contract.schema_version, 1);
        let engine = CredentialVerificationPolicyEngine::new().unwrap();
        for case in contract.cases {
            let mut value = serde_json::to_value(&contract.base_facts).unwrap();
            for (key, patch) in case.patch.as_object().unwrap() {
                value[key] = patch.clone();
            }
            let facts: CredentialVerificationAuthorizationFacts =
                serde_json::from_value(value).unwrap();
            let decision = engine.authorize(&facts).unwrap();
            assert_eq!(decision.allowed, case.allowed, "{}", case.name);
        }
    }

    #[test]
    fn invalid_facts_fail_closed() {
        let mut facts: CredentialVerificationAuthorizationFacts = serde_json::from_value(json!({
            "organization_id": "org-1",
            "credential_format": "SD_JWT_VC",
            "compliance_code": "UNSPECIFIED",
            "issuer_id": "did:example:issuer",
            "issuer_trust_level": 87,
            "credential_age_seconds": 30,
            "revocation_checked": false,
            "revocation_required": false,
            "is_revoked": false,
            "is_expired": false,
            "holder_binding_present": true,
            "algorithm": "EdDSA"
        }))
        .unwrap();
        let engine = CredentialVerificationPolicyEngine::new().unwrap();
        facts.issuer_trust_level = 101;
        assert!(engine.authorize(&facts).is_err());
        facts.issuer_trust_level = 87;
        facts.algorithm.clear();
        assert!(engine.authorize(&facts).is_err());
    }
}
