use std::{collections::BTreeSet, path::PathBuf};

use mmf_platform::{GrpcServerClientAuthentication, GrpcServerTlsMaterial, PlatformError};
use serde::Deserialize;

const CERTIFICATE: &[u8] = b"-----BEGIN CERTIFICATE-----\nZml4dHVyZQ==\n-----END CERTIFICATE-----";
const PRIVATE_KEY: &[u8] = b"-----BEGIN PRIVATE KEY-----\nZml4dHVyZQ==\n-----END PRIVATE KEY-----";

#[derive(Deserialize)]
struct Contract {
    schema_version: u32,
    accepted: Vec<Case>,
    rejected: Vec<Case>,
    requirements: Requirements,
}

#[derive(Deserialize)]
struct Case {
    name: String,
    client_authentication: GrpcServerClientAuthentication,
    material: BTreeSet<String>,
}

#[derive(Deserialize)]
struct Requirements {
    partial_identity: String,
    client_ca_without_client_authentication: String,
    mutual_tls_client_certificate: String,
    plaintext: String,
}

fn contract() -> Contract {
    let path =
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../contracts/grpc-server-behavior.json");
    serde_json::from_slice(&std::fs::read(path).expect("gRPC server fixture"))
        .expect("valid gRPC server fixture")
}

fn material(case: &Case) -> Result<GrpcServerTlsMaterial, PlatformError> {
    let certificate = if case.material.contains("server_certificate") {
        CERTIFICATE.to_vec()
    } else {
        Vec::new()
    };
    let private_key = if case.material.contains("server_private_key") {
        PRIVATE_KEY.to_vec()
    } else {
        Vec::new()
    };
    GrpcServerTlsMaterial::with_client_authentication(
        case.client_authentication,
        case.material
            .contains("client_ca_certificate")
            .then(|| CERTIFICATE.to_vec()),
        certificate,
        private_key,
    )
}

#[test]
fn language_neutral_grpc_server_policy_fails_closed() {
    let contract = contract();
    assert_eq!(contract.schema_version, 1);
    for case in &contract.accepted {
        let result = material(case);
        assert!(result.is_ok(), "{}", case.name);
        let _configuration = result.expect("accepted material").server_tls_config();
    }
    for case in &contract.rejected {
        assert!(material(case).is_err(), "{}", case.name);
    }
}

#[test]
fn server_contract_freezes_downgrade_and_identity_requirements() {
    let requirements = contract().requirements;
    assert_eq!(requirements.partial_identity, "reject");
    assert_eq!(
        requirements.client_ca_without_client_authentication,
        "reject"
    );
    assert_eq!(requirements.mutual_tls_client_certificate, "required");
    assert_eq!(requirements.plaintext, "configured_outside_tls_material");
}
