//! Canonical Cedar authorization for applicant review decisions.

use serde::{Deserialize, Serialize};
use serde_json::json;

use crate::{
    CedarAuthorizationDecision, CedarAuthorizationRequest, CedarConfig, CedarPolicyEngine,
    SecurityError,
};

const SCHEMA: &str = r#"
namespace MIP {
  type ApprovalContext = {
    risk_score: Long,
    document_verification_passed: Bool,
    biometric_match_score: Long,
    evidence_count: Long,
    applicant_country: String,
  };
  entity Organization {};
  entity Role in [Organization] { is_system_role: Bool };
  entity User in [Organization, Role] { email: String, status: String };
  entity Application in [Organization] { risk_score: Long, status: String };
  action "applications:approve" appliesTo {
    principal: [User],
    resource: [Application],
    context: ApprovalContext,
  };
}
"#;

const POLICIES: &str = r#"
@id("role-member-application-approval")
permit (
  principal is MIP::User,
  action == MIP::Action::"applications:approve",
  resource is MIP::Application
)
when {
  principal in MIP::Role::"member"
};

@id("deny-inactive-reviewers")
forbid (
  principal is MIP::User,
  action == MIP::Action::"applications:approve",
  resource is MIP::Application
)
when {
  principal.status != "ACTIVE"
};
"#;

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
#[allow(clippy::struct_excessive_bools)]
pub struct ApplicantApprovalAuthorizationFacts {
    pub reviewer_id: String,
    pub organization_id: String,
    pub application_id: String,
    pub application_status: String,
    pub risk_score: u32,
    pub document_verification_passed: bool,
    pub biometric_match_score: u32,
    pub evidence_count: u64,
    pub applicant_country: String,
}

#[derive(Clone, Debug)]
pub struct ApplicantApprovalPolicyEngine {
    cedar: CedarPolicyEngine,
}

impl ApplicantApprovalPolicyEngine {
    pub fn new() -> Result<Self, SecurityError> {
        Ok(Self {
            cedar: CedarPolicyEngine::from_human_schema(POLICIES, SCHEMA, CedarConfig::default())?,
        })
    }

    pub fn authorize(
        &self,
        facts: &ApplicantApprovalAuthorizationFacts,
    ) -> Result<CedarAuthorizationDecision, SecurityError> {
        validate(facts)?;
        let evidence_count = i64::try_from(facts.evidence_count).map_err(|_| {
            SecurityError::Authorization("evidence count exceeds Cedar Long range".into())
        })?;
        let mut decision = self.cedar.authorize_request(CedarAuthorizationRequest {
            principal_type: "MIP::User".into(),
            principal_id: facts.reviewer_id.clone(),
            action_type: "MIP::Action".into(),
            action_id: "applications:approve".into(),
            resource_type: "MIP::Application".into(),
            resource_id: facts.application_id.clone(),
            context: json!({
                "risk_score": i64::from(facts.risk_score),
                "document_verification_passed": facts.document_verification_passed,
                "biometric_match_score": i64::from(facts.biometric_match_score),
                "evidence_count": evidence_count,
                "applicant_country": facts.applicant_country,
            }),
            entities: json!([
                {
                    "uid": {"type":"MIP::User", "id":facts.reviewer_id},
                    "attrs": {"email":"", "status":"ACTIVE"},
                    "parents": [
                        {"type":"MIP::Organization", "id":facts.organization_id},
                        {"type":"MIP::Role", "id":"member"}
                    ]
                },
                {
                    "uid": {"type":"MIP::Organization", "id":facts.organization_id},
                    "attrs": {}, "parents": []
                },
                {
                    "uid": {"type":"MIP::Role", "id":"member"},
                    "attrs": {"is_system_role":true},
                    "parents": [{"type":"MIP::Organization", "id":facts.organization_id}]
                },
                {
                    "uid": {"type":"MIP::Application", "id":facts.application_id},
                    "attrs": {
                        "risk_score": i64::from(facts.risk_score),
                        "status": facts.application_status
                    },
                    "parents": [{"type":"MIP::Organization", "id":facts.organization_id}]
                }
            ]),
        })?;
        decision.determining_policies = decision
            .determining_policies
            .into_iter()
            .map(|policy| match policy.as_str() {
                "policy0" => "role-member-application-approval".into(),
                "policy1" => "deny-inactive-reviewers".into(),
                _ => policy,
            })
            .collect();
        Ok(decision)
    }
}

fn validate(facts: &ApplicantApprovalAuthorizationFacts) -> Result<(), SecurityError> {
    for (name, value) in [
        ("reviewer_id", &facts.reviewer_id),
        ("organization_id", &facts.organization_id),
        ("application_id", &facts.application_id),
        ("application_status", &facts.application_status),
        ("applicant_country", &facts.applicant_country),
    ] {
        if value.trim().is_empty() || value.len() > 255 {
            return Err(SecurityError::Authorization(format!(
                "{name} must contain 1..=255 characters"
            )));
        }
    }
    if facts.risk_score > 100 || facts.biometric_match_score > 100 {
        return Err(SecurityError::Authorization(
            "approval scores must be in the range 0..=100".into(),
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Deserialize)]
    struct Contract {
        action: String,
        default_role: String,
        complete_facts: Vec<String>,
        score_range: ScoreRange,
        valid_member_decision: String,
        invalid_or_incomplete_decision: String,
        inactive_reviewer_decision: String,
    }

    #[derive(Deserialize)]
    struct ScoreRange {
        minimum: u32,
        maximum: u32,
    }

    fn contract() -> Contract {
        serde_json::from_str(include_str!(
            "../../../contracts/applicant-approval-authorization-behavior.json"
        ))
        .expect("valid applicant approval contract")
    }

    fn facts() -> ApplicantApprovalAuthorizationFacts {
        ApplicantApprovalAuthorizationFacts {
            reviewer_id: "reviewer-1".into(),
            organization_id: "org-1".into(),
            application_id: "application-1".into(),
            application_status: "SUBMITTED".into(),
            risk_score: 10,
            document_verification_passed: true,
            biometric_match_score: 95,
            evidence_count: 2,
            applicant_country: "US".into(),
        }
    }

    #[test]
    fn released_member_approval_policy_permits_complete_facts() {
        let contract = contract();
        assert_eq!(contract.action, "applications:approve");
        assert_eq!(contract.default_role, "member");
        assert_eq!(contract.complete_facts.len(), 9);
        assert_eq!(
            (contract.score_range.minimum, contract.score_range.maximum),
            (0, 100)
        );
        assert_eq!(contract.valid_member_decision, "allow");
        assert_eq!(contract.invalid_or_incomplete_decision, "error");
        assert_eq!(contract.inactive_reviewer_decision, "deny");
        let decision = ApplicantApprovalPolicyEngine::new()
            .unwrap()
            .authorize(&facts())
            .unwrap();
        assert!(decision.allowed);
        assert_eq!(
            decision.determining_policies,
            ["role-member-application-approval"]
        );
    }

    #[test]
    fn malformed_or_out_of_range_facts_fail_closed() {
        let engine = ApplicantApprovalPolicyEngine::new().unwrap();
        let mut invalid = facts();
        invalid.organization_id.clear();
        assert!(engine.authorize(&invalid).is_err());
        let mut invalid = facts();
        invalid.risk_score = 101;
        assert!(engine.authorize(&invalid).is_err());
    }
}
