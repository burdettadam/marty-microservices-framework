use std::{collections::BTreeSet, path::Path};

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

#[derive(Debug, Deserialize)]
struct RetirementEvidence {
    schema_version: u32,
    status: String,
    canonical_rust_replacement_commit: String,
    python_freeze_commit: String,
    consumer_audit: ConsumerAudit,
    aggregate_beta: AggregateBeta,
    retention: Retention,
}

#[derive(Debug, Deserialize)]
struct ConsumerAudit {
    supported_python_package_consumers: u32,
    supported_python_import_consumers: u32,
    rust_capability_count: usize,
    language_neutral_contract_count: usize,
}

#[derive(Debug, Deserialize)]
struct AggregateBeta {
    release: String,
    release_commit: String,
    source_snapshot: String,
    stack_release_run_id: u64,
    beta_lifecycle_run_id: u64,
    deployment_manifest_sha256: String,
    stack_manifest_sha256: String,
    production_invariant_sha256: String,
}

#[derive(Debug, Deserialize)]
struct Retention {
    copy_count: u32,
    complete_git_bundle_sha256: String,
    python_releases: Vec<PythonRelease>,
}

#[derive(Debug, Deserialize)]
struct PythonRelease {
    version: String,
    wheel_sha256: String,
    sdist_sha256: String,
    sbom_sha256: String,
    checksums_sha256: String,
}

#[derive(Debug, Deserialize)]
struct RetainedContracts {
    schema_version: u32,
    inventory_source_commit: String,
    contracts: BTreeSet<String>,
}

fn retained_contracts() -> RetainedContracts {
    serde_json::from_str(include_str!(
        "../../../contracts/python-retirement-contract-inventory.json"
    ))
    .expect("versioned retirement contract inventory")
}

fn missing_contracts<'a>(
    baseline: &'a BTreeSet<String>,
    current: &'a BTreeSet<String>,
) -> Vec<&'a String> {
    baseline.difference(current).collect()
}

fn assert_retained_contract_inventory(recorded_count: usize) {
    // Keep the last recorded evidence/count unchanged as the platform grows.
    // Every named baseline contract must remain; an unrelated new JSON file
    // cannot compensate for deleting an old one, even at the same total count.
    let baseline = retained_contracts();
    assert_eq!(baseline.schema_version, 1);
    assert_eq!(
        baseline.inventory_source_commit,
        "020beffb4da1e0ef52b4330b55c3b4633022d529"
    );
    assert_eq!(baseline.contracts.len(), recorded_count);
    for name in &baseline.contracts {
        assert_eq!(
            Path::new(name).file_name(),
            Some(std::ffi::OsStr::new(name))
        );
        assert_eq!(
            Path::new(name).extension(),
            Some(std::ffi::OsStr::new("json"))
        );
    }
    let contracts = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../contracts");
    let retained_names = std::fs::read_dir(contracts)
        .expect("contracts directory")
        .map(|entry| entry.expect("read contract entry"))
        .filter(|entry| {
            entry
                .path()
                .extension()
                .is_some_and(|extension| extension == "json")
                && entry.file_type().expect("contract file type").is_file()
        })
        .map(|entry| {
            entry
                .file_name()
                .into_string()
                .expect("UTF-8 contract filename")
        })
        .collect::<BTreeSet<_>>();
    let missing = missing_contracts(&baseline.contracts, &retained_names);
    assert!(
        missing.is_empty(),
        "retired behavior contracts removed: {missing:?}"
    );
}

#[test]
fn every_intended_capability_has_one_rust_owner() {
    let inventory: Inventory =
        serde_json::from_str(include_str!("../../../contracts/mmf-capabilities.json"))
            .expect("valid capability inventory");
    assert_eq!(inventory.schema_version, 1);
    assert_eq!(inventory.capabilities.len(), 18);

    let mut ids = BTreeSet::new();
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    for capability in inventory.capabilities {
        assert!(
            ids.insert(capability.id.clone()),
            "duplicate {}",
            capability.id
        );
        assert!(capability.owner.starts_with("mmf-"), "non-MMF owner");
        assert_eq!(
            capability.status, "native-active",
            "inactive {}",
            capability.id
        );
        assert!(
            root.join("crates")
                .join(&capability.owner)
                .join("Cargo.toml")
                .is_file(),
            "missing canonical owner crate {}",
            capability.owner
        );
    }
}

#[test]
fn python_retirement_has_consumer_beta_and_recovery_proof() {
    let evidence: RetirementEvidence = serde_json::from_str(include_str!(
        "../../../contracts/python-retirement-evidence.json"
    ))
    .expect("valid retirement evidence");

    assert_eq!(evidence.schema_version, 1);
    assert_eq!(evidence.status, "complete");
    assert_eq!(
        evidence.canonical_rust_replacement_commit,
        "1c6a9d180fec3670b435d36fda5170a669405ab2"
    );
    assert_eq!(
        evidence.python_freeze_commit,
        "d2875946ac45cdb98876508da1a5a5924c19857e"
    );
    assert_eq!(
        evidence.consumer_audit.supported_python_package_consumers,
        0
    );
    assert_eq!(evidence.consumer_audit.supported_python_import_consumers, 0);
    assert_eq!(evidence.consumer_audit.rust_capability_count, 18);
    assert_eq!(evidence.consumer_audit.language_neutral_contract_count, 41);

    assert_retained_contract_inventory(evidence.consumer_audit.language_neutral_contract_count);

    assert_eq!(evidence.aggregate_beta.release, "marty-ui@1.1.202");
    assert_eq!(
        evidence.aggregate_beta.release_commit,
        "4cd635c5316ef69d38a6eb85a163656104c7b229"
    );
    assert_eq!(
        evidence.aggregate_beta.source_snapshot,
        "fe1867e91535265f57acab467598517fdb60068e"
    );
    assert_eq!(evidence.aggregate_beta.stack_release_run_id, 32_899_928_838);
    assert_eq!(
        evidence.aggregate_beta.beta_lifecycle_run_id,
        32_905_906_875
    );
    for digest in [
        &evidence.aggregate_beta.deployment_manifest_sha256,
        &evidence.aggregate_beta.stack_manifest_sha256,
        &evidence.aggregate_beta.production_invariant_sha256,
        &evidence.retention.complete_git_bundle_sha256,
    ] {
        assert_eq!(digest.len(), 64);
        assert!(
            digest
                .chars()
                .all(|character| character.is_ascii_hexdigit())
        );
    }

    assert_eq!(evidence.retention.copy_count, 2);
    assert_eq!(evidence.retention.python_releases.len(), 2);
    assert_eq!(
        evidence
            .retention
            .python_releases
            .iter()
            .map(|release| release.version.as_str())
            .collect::<BTreeSet<_>>(),
        BTreeSet::from(["1.0.0", "1.0.2"])
    );
    for release in evidence.retention.python_releases {
        for digest in [
            release.wheel_sha256,
            release.sdist_sha256,
            release.sbom_sha256,
            release.checksums_sha256,
        ] {
            assert_eq!(digest.len(), 64);
            assert!(
                digest
                    .chars()
                    .all(|character| character.is_ascii_hexdigit())
            );
        }
    }
}

#[test]
fn retired_python_source_and_packaging_are_absent() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    for retired in [
        "mmf",
        "examples",
        "ops",
        "scripts",
        "tools",
        "deploy",
        "platform_plugins",
        "test_reports",
        "pyproject.toml",
        "uv.lock",
        "MANIFEST.in",
        ".python-version",
        ".secrets.baseline",
    ] {
        assert!(
            !root.join(retired).exists(),
            "retired path returned: {retired}"
        );
    }

    assert!(
        root.join(".github/workflows/release.yml").is_file(),
        "Rust release channel is required after Python publication retirement"
    );
    assert!(
        root.join("dependency-health.yml").is_file(),
        "Rust dependency-health policy is required"
    );
}

#[test]
fn retirement_inventory_allows_growth_but_rejects_replacement_at_equal_count() {
    let baseline = retained_contracts().contracts;
    let mut current = baseline.clone();
    current.insert("new-native-capability.json".to_owned());
    assert!(missing_contracts(&baseline, &current).is_empty());
    let removed = baseline.first().expect("nonempty baseline").clone();
    current.remove(&removed);
    assert_eq!(current.len(), baseline.len());
    assert_eq!(missing_contracts(&baseline, &current), vec![&removed]);
}

#[test]
fn release_checksums_match_github_asset_names() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let workflow = std::fs::read_to_string(root.join(".github/workflows/release.yml"))
        .expect("read Rust release workflow");

    assert!(
        workflow.contains("> \"release/${crate}.txt\""),
        "crate manifests must be emitted at the release root"
    );
    assert!(
        !workflow.contains("release/package-manifests"),
        "GitHub flattens release assets, so checksums cannot contain nested manifest paths"
    );
    assert!(
        workflow.contains("find release-assets -mindepth 2 -type f"),
        "the release job must reject nested assets before generating checksums"
    );
}

#[test]
fn required_license_check_runs_for_every_protected_change() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let workflow = std::fs::read_to_string(root.join(".github/workflows/license-compliance.yml"))
        .expect("read Rust license workflow")
        .replace("\r\n", "\n");

    assert!(workflow.contains("pull_request:\n    branches: [main]"));
    assert!(workflow.contains("merge_group:\n    types: [checks_requested]"));
    assert!(
        !workflow.contains("    paths:"),
        "a required check must not be skipped by path filters"
    );
}
