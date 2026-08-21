use std::collections::BTreeSet;

use serde::Deserialize;

#[derive(Debug, Deserialize)]
struct Inventory {
    schema_version: u32,
    capabilities: Vec<Capability>,
}

#[derive(Debug, Deserialize)]
struct Capability {
    id: String,
    owner: String,
    status: String,
}

#[test]
fn every_intended_capability_has_one_rust_owner() {
    let inventory: Inventory =
        serde_json::from_str(include_str!("../../../contracts/mmf-capabilities.json"))
            .expect("valid capability inventory");
    assert_eq!(inventory.schema_version, 1);
    assert_eq!(inventory.capabilities.len(), 18);

    let mut ids = BTreeSet::new();
    for capability in inventory.capabilities {
        assert!(
            ids.insert(capability.id.clone()),
            "duplicate {}",
            capability.id
        );
        assert!(capability.owner.starts_with("mmf-"), "non-MMF owner");
        assert!(
            matches!(
                capability.status.as_str(),
                "planned" | "foundation-active" | "active" | "migrated"
            ),
            "unknown status for {}",
            capability.id
        );
    }
}
