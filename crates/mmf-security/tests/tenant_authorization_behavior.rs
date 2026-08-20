use std::{collections::BTreeSet, path::PathBuf};

use mmf_security::{TenantAuthorizationFailure, TenantMembership, authorize_tenant_membership};
use serde::Deserialize;

#[derive(Deserialize)]
struct Contract {
    schema_version: u32,
    cases: Vec<Case>,
}

#[derive(Deserialize)]
struct Case {
    name: String,
    principal_id: String,
    tenant_id: String,
    membership: String,
    permission: String,
    owner_only: bool,
    result: String,
}

fn membership(kind: &str) -> Option<TenantMembership> {
    match kind {
        "none" => None,
        "matching_active" | "matching_inactive" | "matching_owner" => Some(TenantMembership {
            principal_id: "user-1".into(),
            tenant_id: "org-1".into(),
            status: if kind == "matching_inactive" {
                "suspended".into()
            } else {
                "active".into()
            },
            role_names: BTreeSet::from(["member".into()]),
            permissions: BTreeSet::from(["flow-definition:view".into()]),
            is_owner: kind == "matching_owner",
        }),
        unknown => panic!("unknown membership fixture: {unknown}"),
    }
}

#[test]
fn tenant_authorization_matches_language_neutral_vectors() {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../contracts/tenant-authorization-behavior.json");
    let contract: Contract = serde_json::from_slice(&std::fs::read(path).unwrap()).unwrap();
    assert_eq!(contract.schema_version, 1);
    for case in contract.cases {
        let membership = membership(&case.membership);
        let result = authorize_tenant_membership(
            &case.permission,
            &case.principal_id,
            &case.tenant_id,
            membership.as_ref(),
            case.owner_only,
        );
        let actual = match result {
            Ok(()) => "allow",
            Err(TenantAuthorizationFailure::AuthenticationRequired) => "authentication_required",
            Err(TenantAuthorizationFailure::MembershipMissing) => "membership_missing",
            Err(TenantAuthorizationFailure::MembershipInactive) => "membership_inactive",
            Err(TenantAuthorizationFailure::ActionNotAuthorized) => "action_not_authorized",
        };
        assert_eq!(actual, case.result, "{}", case.name);
    }
}
