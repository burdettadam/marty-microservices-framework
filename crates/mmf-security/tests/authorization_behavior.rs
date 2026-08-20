use std::collections::{BTreeMap, BTreeSet};

use mmf_security::*;
use serde_json::{Value, json};

fn fixture() -> Value {
    serde_json::from_str(include_str!(
        "../../../contracts/authorization-adapter-behavior.json"
    ))
    .expect("valid authorization fixture")
}

fn context(timestamp_ms: u64, ip: &str) -> SecurityContext {
    SecurityContext {
        principal: SecurityPrincipal {
            id: "alice".to_owned(),
            principal_type: PrincipalType::User,
            roles: BTreeSet::from(["editor".to_owned()]),
            permissions: BTreeSet::new(),
            attributes: BTreeMap::from([
                ("groups".to_owned(), json!(["engineering"])),
                ("profile".to_owned(), json!({"department": "finance"})),
                ("email".to_owned(), json!("alice@example.com")),
            ]),
            identity_provider: None,
            session_id: None,
            expires_at_ms: None,
        },
        resource: "/api/v1/documents/42".to_owned(),
        action: "write".to_owned(),
        resource_attributes: BTreeMap::from([("classification".to_owned(), json!("internal"))]),
        environment: BTreeMap::new(),
        request_metadata: BTreeMap::from([
            ("client_ip".to_owned(), json!(ip)),
            ("request_method".to_owned(), json!("patch")),
        ]),
        request_id: Some("request-1".to_owned()),
        timestamp_ms,
    }
}

#[test]
fn structured_permission_vectors_match() {
    let fixture = fixture();
    for case in fixture["structured_permissions"].as_array().unwrap() {
        let permission = StructuredPermission::parse(case["permission"].as_str().unwrap()).unwrap();
        let request = case["request"].as_array().unwrap();
        assert_eq!(
            permission.matches(
                request[0].as_str().unwrap(),
                request[1].as_str().unwrap(),
                request[2].as_str().unwrap()
            ),
            case["allowed"].as_bool().unwrap()
        );
        assert_eq!(
            StructuredPermission::parse(&permission.to_string()).unwrap(),
            permission
        );
    }
    assert!(StructuredPermission::parse("invalid").is_err());
}

#[test]
fn managed_rbac_preserves_system_lifecycle_and_inheritance() {
    let fixture = fixture();
    let case = &fixture["rbac"];
    let mut rbac = ManagedRbac::with_system_roles(0);
    for role in case["system_roles"].as_array().unwrap() {
        assert!(rbac.roles().get(role.as_str().unwrap()).unwrap().system);
    }
    let role = ManagedRole {
        name: case["assigned_role"].as_str().unwrap().to_owned(),
        description: "Can deploy releases".to_owned(),
        permissions: BTreeSet::from([StructuredPermission::parse("service:*:deploy").unwrap()]),
        parent_roles: BTreeSet::from([case["parent_role"].as_str().unwrap().to_owned()]),
        metadata: BTreeMap::new(),
        created_at_ms: 1,
        system: false,
        active: true,
    };
    rbac.add_role(role).unwrap();
    rbac.assign(
        case["user"].as_str().unwrap(),
        case["assigned_role"].as_str().unwrap(),
    )
    .unwrap();
    assert!(
        rbac.effective_roles(case["user"].as_str().unwrap())
            .contains("developer")
    );
    for (name, expected) in [
        ("allowed_request", true),
        ("inherited_request", true),
        ("denied_request", false),
    ] {
        let request = case[name].as_array().unwrap();
        assert_eq!(
            rbac.authorize(
                case["user"].as_str().unwrap(),
                request[0].as_str().unwrap(),
                request[1].as_str().unwrap(),
                request[2].as_str().unwrap()
            ),
            expected
        );
    }
    assert!(rbac.remove_role("admin").is_err());
    assert!(
        rbac.remove_role(case["assigned_role"].as_str().unwrap())
            .unwrap()
    );
    assert!(!rbac.authorize(
        case["user"].as_str().unwrap(),
        "service",
        "gateway",
        "deploy"
    ));
}

#[test]
fn abac_supports_nested_attributes_regex_and_deny_precedence() {
    let fixture = fixture();
    let case = &fixture["abac"];
    let mut engine = AbacEngine::default();
    engine
        .replace_policies(vec![
            AbacPolicy {
                id: "allow-finance".to_owned(),
                effect: PolicyEffect::Allow,
                priority: 100,
                enabled: true,
                resources: vec!["/api/v1/documents/?*".to_owned()],
                actions: vec!["write".to_owned()],
                conditions: vec![AttributeCondition {
                    source: AttributeSource::Subject,
                    attribute: case["nested_path"].as_str().unwrap().to_owned(),
                    operator: ConditionOperator::Equal,
                    value: case["nested_value"].clone(),
                }],
            },
            AbacPolicy {
                id: "deny-unapproved-email".to_owned(),
                effect: PolicyEffect::Deny,
                priority: 1,
                enabled: true,
                resources: vec!["*".to_owned()],
                actions: vec!["write".to_owned()],
                conditions: vec![AttributeCondition {
                    source: AttributeSource::Subject,
                    attribute: case["regex_path"].as_str().unwrap().to_owned(),
                    operator: ConditionOperator::NotEqual,
                    value: json!(case["matching_email"].as_str().unwrap()),
                }],
            },
        ])
        .unwrap();
    assert!(
        engine
            .authorize(&context(84_600_000, "10.20.30.40"))
            .allowed
    );

    let regex = AttributeCondition {
        source: AttributeSource::Subject,
        attribute: case["regex_path"].as_str().unwrap().to_owned(),
        operator: ConditionOperator::Regex,
        value: case["regex"].clone(),
    };
    assert!(regex.matches(&context(0, "10.0.0.1")));
    let mut invalid = AbacEngine::default();
    assert!(
        invalid
            .replace_policies(vec![AbacPolicy {
                id: "invalid-regex".to_owned(),
                effect: PolicyEffect::Allow,
                priority: 0,
                enabled: true,
                resources: vec![],
                actions: vec![],
                conditions: vec![AttributeCondition {
                    source: AttributeSource::Subject,
                    attribute: "email".to_owned(),
                    operator: ConditionOperator::Regex,
                    value: json!("[")
                }]
            }])
            .is_err()
    );
}

#[test]
fn acl_conditions_deny_precedence_defaults_and_conflicts_are_deterministic() {
    let fixture = fixture();
    let case = &fixture["acl"];
    let conditions = AclConditions {
        time_range: Some(serde_json::from_value(case["time_range"].clone()).unwrap()),
        ip_ranges: vec![case["ip_range"].as_str().unwrap().to_owned()],
        request_methods: BTreeSet::from([case["request_method"].as_str().unwrap().to_owned()]),
        resource_attributes: serde_json::from_value(case["resource_attribute"].clone()).unwrap(),
    };
    let allow = AclEntry {
        resource_pattern: case["resource_pattern"].as_str().unwrap().to_owned(),
        principal: case["principal"].as_str().unwrap().to_owned(),
        permissions: BTreeSet::from([case["permission"].as_str().unwrap().to_owned()]),
        effect: PolicyEffect::Allow,
        conditions: conditions.clone(),
    };
    let mut engine = AclEngine::default();
    engine.add_entry(allow.clone()).unwrap();
    assert!(
        engine
            .authorize(&context(
                case["matching_timestamp_ms"].as_u64().unwrap(),
                case["matching_ip"].as_str().unwrap()
            ))
            .allowed
    );
    assert!(
        !engine
            .authorize(&context(
                case["non_matching_timestamp_ms"].as_u64().unwrap(),
                case["matching_ip"].as_str().unwrap()
            ))
            .allowed
    );
    assert!(
        !engine
            .authorize(&context(
                case["matching_timestamp_ms"].as_u64().unwrap(),
                case["non_matching_ip"].as_str().unwrap()
            ))
            .allowed
    );
    let mut deny = allow;
    deny.effect = PolicyEffect::Deny;
    engine.add_entry(deny).unwrap();
    assert!(
        !engine
            .authorize(&context(
                case["matching_timestamp_ms"].as_u64().unwrap(),
                case["matching_ip"].as_str().unwrap()
            ))
            .allowed
    );
    assert_eq!(engine.conflicts().len(), 1);
    assert_eq!(
        engine.remove_entries(
            case["resource_pattern"].as_str().unwrap(),
            case["principal"].as_str().unwrap()
        ),
        2
    );
}

#[test]
fn composite_and_external_policy_paths_fail_closed() {
    let allow = AuthorizationDecision::allow("allow", vec!["allow".to_owned()]);
    let deny = AuthorizationDecision::deny("deny", vec!["deny".to_owned()]);
    assert!(combine_decisions(CompositeStrategy::Any, &[deny.clone(), allow.clone()]).allowed);
    assert!(combine_decisions(CompositeStrategy::All, &[allow.clone(), allow.clone()]).allowed);
    assert!(!combine_decisions(CompositeStrategy::All, &[allow.clone(), deny.clone()]).allowed);
    assert!(!combine_decisions(CompositeStrategy::DenyOverrides, &[allow, deny]).allowed);
    assert!(!combine_decisions(CompositeStrategy::Any, &[]).allowed);

    let runtime = tokio::runtime::Runtime::new().unwrap();
    let error = runtime
        .block_on(UnavailablePolicyEngine.load(&[]))
        .unwrap_err();
    assert!(matches!(
        error,
        SecurityError::RequiredProvidersUnavailable(_)
    ));
}
