//! Mutual-TLS certificate models, policy, configuration, authentication state, and ports.
//!
//! X.509 parsing, path construction, signature verification, CRL verification, and OCSP
//! cryptography remain provider effects supplied by `marty-core` adapters. This module owns the
//! reusable MMF behavior around those effects and never treats a missing provider as success.

use std::collections::{BTreeMap, BTreeSet};
use std::fmt::Write as _;
use std::sync::Arc;

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha1::Sha1;
use sha2::{Digest, Sha256};
use uuid::Uuid;

use crate::{AuthenticatedUser, SecurityError};

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CertificateStatus {
    Valid,
    Expired,
    NotYetValid,
    Revoked,
    UnknownCa,
    InvalidSignature,
    UntrustedCa,
    ChainInvalid,
    ParsingError,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CertificateType {
    Client,
    Server,
    Ca,
    Intermediate,
    Root,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CertificateError {
    MissingCertificate,
    InvalidPem,
    InvalidDer,
    ParsingFailed,
    Expired,
    NotYetValid,
    Revoked,
    UnknownIssuer,
    UntrustedIssuer,
    InvalidSignature,
    InvalidChain,
    InvalidKeyUsage,
    InvalidExtendedKeyUsage,
    WeakKey,
    UnsupportedAlgorithm,
    HostnameMismatch,
    IdentityMappingFailed,
    ProviderUnavailable,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct SubjectAlternativeName {
    #[serde(default)]
    pub dns_names: BTreeSet<String>,
    #[serde(default)]
    pub ip_addresses: BTreeSet<String>,
    #[serde(default)]
    pub email_addresses: BTreeSet<String>,
    #[serde(default)]
    pub uris: BTreeSet<String>,
    #[serde(default)]
    pub user_principal_names: BTreeSet<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct BasicConstraints {
    pub is_ca: bool,
    pub path_length: Option<u32>,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct KeyUsage {
    pub digital_signature: bool,
    pub content_commitment: bool,
    pub key_encipherment: bool,
    pub data_encipherment: bool,
    pub key_agreement: bool,
    pub key_cert_sign: bool,
    pub crl_sign: bool,
    pub encipher_only: bool,
    pub decipher_only: bool,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct ExtendedKeyUsage {
    #[serde(default)]
    pub purposes: BTreeSet<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct AuthorityKeyIdentifier {
    pub key_identifier: Option<String>,
    pub authority_cert_issuer: Option<String>,
    pub authority_cert_serial_number: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct SubjectKeyIdentifier {
    pub key_identifier: String,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct CrlDistributionPoints {
    #[serde(default)]
    pub urls: BTreeSet<String>,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct AuthorityInformationAccess {
    #[serde(default)]
    pub ocsp_urls: BTreeSet<String>,
    #[serde(default)]
    pub ca_issuer_urls: BTreeSet<String>,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct CertificatePolicies {
    #[serde(default)]
    pub policy_oids: BTreeSet<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(tag = "kind", content = "value", rename_all = "snake_case")]
pub enum CertificateExtension {
    SubjectAlternativeName(SubjectAlternativeName),
    BasicConstraints(BasicConstraints),
    KeyUsage(KeyUsage),
    ExtendedKeyUsage(ExtendedKeyUsage),
    AuthorityKeyIdentifier(AuthorityKeyIdentifier),
    SubjectKeyIdentifier(SubjectKeyIdentifier),
    CrlDistributionPoints(CrlDistributionPoints),
    AuthorityInformationAccess(AuthorityInformationAccess),
    CertificatePolicies(CertificatePolicies),
    Unsupported,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct X509Extension {
    pub oid: String,
    pub critical: bool,
    #[serde(skip_serializing)]
    pub raw_value: Vec<u8>,
    pub parsed: CertificateExtension,
}

impl X509Extension {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.oid.trim().is_empty() || self.raw_value.is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "X.509 extension requires an OID and value".into(),
            ));
        }
        if self.critical && self.parsed == CertificateExtension::Unsupported {
            return Err(SecurityError::Unauthorized(
                "unsupported critical X.509 extension".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct CertificateSubject {
    pub common_name: Option<String>,
    pub organization: Option<String>,
    pub organizational_unit: Option<String>,
    pub country: Option<String>,
    pub state: Option<String>,
    pub locality: Option<String>,
    pub email_address: Option<String>,
    pub serial_number: Option<String>,
    pub domain_component: Option<String>,
    pub user_id: Option<String>,
}

impl CertificateSubject {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if [
            self.common_name.as_deref(),
            self.organization.as_deref(),
            self.organizational_unit.as_deref(),
            self.email_address.as_deref(),
            self.user_id.as_deref(),
        ]
        .into_iter()
        .flatten()
        .all(str::is_empty)
        {
            return Err(SecurityError::InvalidConfiguration(
                "certificate subject requires an identifying field".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn display_name(&self) -> &str {
        self.common_name
            .as_deref()
            .or(self.email_address.as_deref())
            .or(self.user_id.as_deref())
            .or(self.organization.as_deref())
            .unwrap_or("Unknown Subject")
    }

    #[must_use]
    pub fn matches_identity(&self, identity: &str) -> bool {
        [
            self.common_name.as_deref(),
            self.email_address.as_deref(),
            self.user_id.as_deref(),
        ]
        .into_iter()
        .flatten()
        .any(|candidate| candidate.eq_ignore_ascii_case(identity))
    }
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct CertificateIssuer {
    pub common_name: Option<String>,
    pub organization: Option<String>,
    pub organizational_unit: Option<String>,
    pub country: Option<String>,
    pub state: Option<String>,
    pub locality: Option<String>,
    pub ca_identifier: Option<String>,
}

impl CertificateIssuer {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if [
            self.common_name.as_deref(),
            self.organization.as_deref(),
            self.ca_identifier.as_deref(),
        ]
        .into_iter()
        .flatten()
        .all(str::is_empty)
        {
            return Err(SecurityError::InvalidConfiguration(
                "certificate issuer requires an identifying field".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn display_name(&self) -> &str {
        self.common_name
            .as_deref()
            .or(self.organization.as_deref())
            .or(self.ca_identifier.as_deref())
            .unwrap_or("Unknown Issuer")
    }

    #[must_use]
    pub fn matches_ca(&self, ca_name: &str) -> bool {
        let ca_name = ca_name.to_ascii_lowercase();
        [
            self.common_name.as_deref(),
            self.organization.as_deref(),
            self.ca_identifier.as_deref(),
        ]
        .into_iter()
        .flatten()
        .any(|candidate| candidate.to_ascii_lowercase().contains(&ca_name))
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ClientCertificate {
    #[serde(skip_serializing)]
    pub pem_data: String,
    #[serde(default, skip_serializing)]
    pub der_data: Vec<u8>,
    pub serial_number: Option<String>,
    pub fingerprint_sha1: Option<String>,
    pub fingerprint_sha256: Option<String>,
    pub not_valid_before_ms: Option<u64>,
    pub not_valid_after_ms: Option<u64>,
    pub subject: Option<CertificateSubject>,
    pub issuer: Option<CertificateIssuer>,
    pub certificate_type: CertificateType,
    #[serde(default)]
    pub key_usage: BTreeSet<String>,
    #[serde(default)]
    pub extended_key_usage: BTreeSet<String>,
    #[serde(default)]
    pub subject_alternative_name: SubjectAlternativeName,
    pub signature_algorithm: Option<String>,
    pub public_key_algorithm: Option<String>,
    pub public_key_size: Option<u32>,
    pub is_self_signed: bool,
    pub ca_certificate: Option<Box<ClientCertificate>>,
    #[serde(default)]
    pub extensions: Vec<X509Extension>,
}

impl ClientCertificate {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if !self
            .pem_data
            .trim_start()
            .starts_with("-----BEGIN CERTIFICATE-----")
            || !self
                .pem_data
                .trim_end()
                .ends_with("-----END CERTIFICATE-----")
        {
            return Err(SecurityError::InvalidConfiguration(
                "invalid PEM certificate envelope".into(),
            ));
        }
        if self
            .not_valid_before_ms
            .zip(self.not_valid_after_ms)
            .is_some_and(|(before, after)| before > after)
        {
            return Err(SecurityError::InvalidConfiguration(
                "certificate validity interval is inverted".into(),
            ));
        }
        if let Some(subject) = &self.subject {
            subject.validate()?;
        }
        if let Some(issuer) = &self.issuer {
            issuer.validate()?;
        }
        for extension in &self.extensions {
            extension.validate()?;
        }
        Ok(())
    }

    #[must_use]
    pub fn is_valid_at(&self, now_ms: u64) -> bool {
        self.not_valid_before_ms
            .is_none_or(|before| now_ms >= before)
            && self.not_valid_after_ms.is_none_or(|after| now_ms <= after)
    }

    #[must_use]
    pub fn is_expired_at(&self, now_ms: u64) -> bool {
        self.not_valid_after_ms.is_some_and(|after| now_ms > after)
    }

    #[must_use]
    pub fn expires_soon_at(&self, now_ms: u64, warning_window_ms: u64) -> bool {
        self.not_valid_after_ms
            .is_some_and(|after| after <= now_ms.saturating_add(warning_window_ms))
    }

    #[must_use]
    pub fn fingerprint(&self, algorithm: FingerprintAlgorithm) -> Option<&str> {
        match algorithm {
            FingerprintAlgorithm::Sha1 => self.fingerprint_sha1.as_deref(),
            FingerprintAlgorithm::Sha256 => self.fingerprint_sha256.as_deref(),
        }
    }

    #[must_use]
    pub fn has_key_usage(&self, usage: &str) -> bool {
        self.key_usage
            .iter()
            .any(|candidate| candidate.eq_ignore_ascii_case(usage))
    }

    #[must_use]
    pub fn has_extended_key_usage(&self, usage: &str) -> bool {
        self.extended_key_usage
            .iter()
            .any(|candidate| candidate.eq_ignore_ascii_case(usage))
    }

    #[must_use]
    pub fn matches_hostname(&self, hostname: &str) -> bool {
        self.subject
            .as_ref()
            .and_then(|subject| subject.common_name.as_deref())
            .is_some_and(|common_name| common_name.eq_ignore_ascii_case(hostname))
            || self
                .subject_alternative_name
                .dns_names
                .iter()
                .any(|candidate| hostname_matches(candidate, hostname))
    }

    #[must_use]
    pub fn matches_email(&self, email: &str) -> bool {
        self.subject
            .as_ref()
            .and_then(|subject| subject.email_address.as_deref())
            .is_some_and(|candidate| candidate.eq_ignore_ascii_case(email))
            || self
                .subject_alternative_name
                .email_addresses
                .iter()
                .any(|candidate| candidate.eq_ignore_ascii_case(email))
    }

    #[must_use]
    pub fn trust_chain_depth(&self) -> usize {
        let mut depth = 0;
        let mut current = self.ca_certificate.as_deref();
        while let Some(certificate) = current {
            depth += 1;
            current = certificate.ca_certificate.as_deref();
        }
        depth
    }
}

fn hostname_matches(pattern: &str, hostname: &str) -> bool {
    if pattern.eq_ignore_ascii_case(hostname) {
        return true;
    }
    let Some(suffix) = pattern.strip_prefix("*.") else {
        return false;
    };
    let Some(prefix) = hostname
        .to_ascii_lowercase()
        .strip_suffix(&format!(".{}", suffix.to_ascii_lowercase()))
        .map(str::to_owned)
    else {
        return false;
    };
    !prefix.is_empty() && !prefix.contains('.')
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum FingerprintAlgorithm {
    Sha1,
    Sha256,
}

pub fn calculate_certificate_fingerprint(
    certificate_data: &[u8],
    algorithm: FingerprintAlgorithm,
) -> Result<String, SecurityError> {
    if certificate_data.is_empty() {
        return Err(SecurityError::InvalidConfiguration(
            "certificate data cannot be empty".into(),
        ));
    }
    let bytes = match algorithm {
        FingerprintAlgorithm::Sha1 => Sha1::digest(certificate_data).to_vec(),
        FingerprintAlgorithm::Sha256 => Sha256::digest(certificate_data).to_vec(),
    };
    let mut fingerprint = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        write!(&mut fingerprint, "{byte:02X}").map_err(|_| {
            SecurityError::InvalidConfiguration("cannot format certificate fingerprint".into())
        })?;
    }
    Ok(fingerprint)
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CertificateTrustLevel {
    Full,
    Conditional,
    Revoked,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct CertificateAuthority {
    pub ca_name: String,
    pub ca_certificate: ClientCertificate,
    pub trusted: bool,
    pub trust_level: CertificateTrustLevel,
    pub can_issue_client_certs: bool,
    pub can_issue_server_certs: bool,
    pub can_issue_ca_certs: bool,
    pub check_revocation: bool,
    pub require_valid_chain: bool,
    #[serde(default)]
    pub crl_urls: BTreeSet<String>,
    #[serde(default)]
    pub ocsp_urls: BTreeSet<String>,
}

impl CertificateAuthority {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.ca_name.trim().is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "certificate authority name cannot be empty".into(),
            ));
        }
        self.ca_certificate.validate()?;
        Ok(())
    }

    #[must_use]
    pub fn is_trusted(&self) -> bool {
        self.trusted && self.trust_level != CertificateTrustLevel::Revoked
    }

    #[must_use]
    pub fn can_issue(&self, certificate_type: CertificateType) -> bool {
        match certificate_type {
            CertificateType::Client => self.can_issue_client_certs,
            CertificateType::Server => self.can_issue_server_certs,
            CertificateType::Ca | CertificateType::Intermediate | CertificateType::Root => {
                self.can_issue_ca_certs
            }
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct CertificateRevocationList {
    pub issuer: CertificateIssuer,
    pub this_update_ms: u64,
    pub next_update_ms: Option<u64>,
    #[serde(default)]
    pub revoked_serial_numbers: BTreeSet<String>,
    pub crl_url: Option<String>,
    #[serde(skip_serializing)]
    pub crl_data: Option<String>,
}

impl CertificateRevocationList {
    pub fn validate(&self) -> Result<(), SecurityError> {
        self.issuer.validate()?;
        if self
            .next_update_ms
            .is_some_and(|next| next < self.this_update_ms)
        {
            return Err(SecurityError::InvalidConfiguration(
                "CRL update interval is inverted".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn is_current_at(&self, now_ms: u64) -> bool {
        now_ms >= self.this_update_ms && self.next_update_ms.is_none_or(|next| now_ms <= next)
    }

    #[must_use]
    pub fn is_certificate_revoked(&self, serial_number: &str) -> bool {
        self.revoked_serial_numbers.contains(serial_number)
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(default)]
#[allow(clippy::struct_excessive_bools)]
pub struct CertificateValidationPolicy {
    pub check_expiration: bool,
    pub check_not_yet_valid: bool,
    pub check_signature: bool,
    pub require_trusted_ca: bool,
    pub allow_self_signed: bool,
    pub max_chain_depth: usize,
    pub require_client_auth_eku: bool,
    pub allowed_key_usages: BTreeSet<String>,
    pub check_crl: bool,
    pub check_ocsp: bool,
    pub require_revocation_check: bool,
    pub validate_hostname: bool,
    pub validate_email: bool,
    pub allowed_sans: BTreeSet<String>,
    pub min_key_size: u32,
    pub allowed_signature_algorithms: BTreeSet<String>,
    pub time_tolerance_ms: u64,
}

impl Default for CertificateValidationPolicy {
    fn default() -> Self {
        Self {
            check_expiration: true,
            check_not_yet_valid: true,
            check_signature: true,
            require_trusted_ca: true,
            allow_self_signed: false,
            max_chain_depth: 10,
            require_client_auth_eku: true,
            allowed_key_usages: ["digital_signature", "key_encipherment", "key_agreement"]
                .into_iter()
                .map(str::to_owned)
                .collect(),
            check_crl: true,
            check_ocsp: false,
            require_revocation_check: false,
            validate_hostname: false,
            validate_email: false,
            allowed_sans: BTreeSet::new(),
            min_key_size: 2_048,
            allowed_signature_algorithms: [
                "sha256WithRSAEncryption",
                "ecdsa-with-SHA256",
                "rsaPSS",
            ]
            .into_iter()
            .map(str::to_owned)
            .collect(),
            time_tolerance_ms: 300_000,
        }
    }
}

impl CertificateValidationPolicy {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.max_chain_depth == 0 || self.min_key_size < 1_024 {
            return Err(SecurityError::InvalidConfiguration(
                "certificate policy requires a positive chain depth and secure key size".into(),
            ));
        }
        if !self.check_crl && !self.check_ocsp && self.require_revocation_check {
            return Err(SecurityError::InvalidConfiguration(
                "required revocation checking has no enabled method".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn is_signature_algorithm_allowed(&self, algorithm: &str) -> bool {
        self.allowed_signature_algorithms.contains(algorithm)
    }

    #[must_use]
    pub fn is_key_usage_valid<'a>(&self, usages: impl IntoIterator<Item = &'a str>) -> bool {
        usages.into_iter().all(|usage| {
            self.allowed_key_usages
                .iter()
                .any(|allowed| allowed.eq_ignore_ascii_case(usage))
        })
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct CertificateValidationResult {
    pub status: CertificateStatus,
    pub is_valid: bool,
    pub is_trusted: bool,
    #[serde(default)]
    pub validation_errors: Vec<String>,
    #[serde(default)]
    pub validation_warnings: Vec<String>,
    pub certificate: Option<ClientCertificate>,
    #[serde(default)]
    pub trust_chain: Vec<ClientCertificate>,
    pub validated_at_ms: u64,
    pub validation_policy: Option<CertificateValidationPolicy>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

impl CertificateValidationResult {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.is_valid
            && (!self.validation_errors.is_empty() || self.status != CertificateStatus::Valid)
        {
            return Err(SecurityError::InvalidAuthenticationResult);
        }
        if self.is_trusted && !self.is_valid {
            return Err(SecurityError::InvalidAuthenticationResult);
        }
        Ok(())
    }

    #[must_use]
    pub fn has_errors(&self) -> bool {
        !self.validation_errors.is_empty()
    }

    #[must_use]
    pub fn has_warnings(&self) -> bool {
        !self.validation_warnings.is_empty()
    }

    #[must_use]
    pub fn error_summary(&self) -> String {
        if self.validation_errors.is_empty() {
            "No errors".to_owned()
        } else {
            self.validation_errors.join("; ")
        }
    }

    #[must_use]
    pub fn with_error(mut self, error: impl Into<String>) -> Self {
        self.status = CertificateStatus::InvalidSignature;
        self.is_valid = false;
        self.is_trusted = false;
        self.validation_errors.push(error.into());
        self
    }

    #[must_use]
    pub fn with_warning(mut self, warning: impl Into<String>) -> Self {
        self.validation_warnings.push(warning.into());
        self
    }
}

#[must_use]
pub fn create_validation_result(
    status: CertificateStatus,
    is_valid: bool,
    certificate: Option<ClientCertificate>,
    errors: Vec<String>,
    warnings: Vec<String>,
    validated_at_ms: u64,
) -> CertificateValidationResult {
    CertificateValidationResult {
        status,
        is_valid,
        is_trusted: is_valid,
        validation_errors: errors,
        validation_warnings: warnings,
        certificate,
        trust_chain: Vec::new(),
        validated_at_ms,
        validation_policy: None,
        metadata: BTreeMap::new(),
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TrustStoreType {
    FileSystem,
    Pkcs11,
    Windows,
    MacosKeychain,
    Database,
    Ldap,
    Custom,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RevocationCheckMethod {
    Crl,
    Ocsp,
    Both,
    None,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CertificateSource {
    HttpHeader,
    TlsHandshake,
    RequestBody,
    QueryParam,
    Custom,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct TrustStoreConfiguration {
    pub store_type: TrustStoreType,
    pub store_path: Option<String>,
    #[serde(skip_serializing)]
    pub store_password: Option<String>,
    #[serde(default)]
    pub ca_cert_files: Vec<String>,
    pub ca_cert_directory: Option<String>,
    pub pkcs11_module: Option<String>,
    pub pkcs11_slot: Option<u64>,
    #[serde(skip_serializing)]
    pub pkcs11_pin: Option<String>,
    #[serde(skip_serializing)]
    pub db_connection_string: Option<String>,
    pub ca_table_name: String,
    pub ldap_server_url: Option<String>,
    pub ldap_base_dn: Option<String>,
    pub ldap_bind_dn: Option<String>,
    #[serde(skip_serializing)]
    pub ldap_bind_password: Option<String>,
    pub enable_ca_cache: bool,
    pub ca_cache_ttl_ms: u64,
    pub max_cached_cas: usize,
    pub auto_reload_cas: bool,
    pub reload_interval_ms: u64,
}

impl TrustStoreConfiguration {
    pub fn validate(&self) -> Result<(), SecurityError> {
        let present =
            |value: &Option<String>| value.as_deref().is_some_and(|v| !v.trim().is_empty());
        let valid_backend = match self.store_type {
            TrustStoreType::FileSystem => {
                !self.ca_cert_files.is_empty()
                    || present(&self.ca_cert_directory)
                    || present(&self.store_path)
            }
            TrustStoreType::Pkcs11 => present(&self.pkcs11_module),
            TrustStoreType::Database => present(&self.db_connection_string),
            TrustStoreType::Ldap => present(&self.ldap_server_url) && present(&self.ldap_base_dn),
            TrustStoreType::Windows | TrustStoreType::MacosKeychain | TrustStoreType::Custom => {
                true
            }
        };
        if !valid_backend {
            return Err(SecurityError::InvalidConfiguration(
                "trust store is missing backend-specific configuration".into(),
            ));
        }
        if self.ca_cache_ttl_ms == 0 || self.max_cached_cas == 0 || self.reload_interval_ms == 0 {
            return Err(SecurityError::InvalidConfiguration(
                "trust store cache and reload limits must be positive".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct RevocationCheckConfiguration {
    pub check_method: RevocationCheckMethod,
    pub crl_cache_enabled: bool,
    pub crl_cache_ttl_ms: u64,
    pub crl_download_timeout_ms: u64,
    pub crl_max_size_mb: usize,
    pub ocsp_timeout_ms: u64,
    pub ocsp_max_retries: usize,
    pub ocsp_cache_ttl_ms: u64,
    pub fail_on_revocation_check_error: bool,
    pub allow_revocation_check_bypass: bool,
    pub parallel_revocation_checks: bool,
    pub max_concurrent_checks: usize,
}

impl Default for RevocationCheckConfiguration {
    fn default() -> Self {
        Self {
            check_method: RevocationCheckMethod::Crl,
            crl_cache_enabled: true,
            crl_cache_ttl_ms: 3_600_000,
            crl_download_timeout_ms: 30_000,
            crl_max_size_mb: 50,
            ocsp_timeout_ms: 10_000,
            ocsp_max_retries: 3,
            ocsp_cache_ttl_ms: 1_800_000,
            fail_on_revocation_check_error: false,
            allow_revocation_check_bypass: false,
            parallel_revocation_checks: true,
            max_concurrent_checks: 10,
        }
    }
}

impl RevocationCheckConfiguration {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.crl_cache_ttl_ms == 0
            || self.crl_download_timeout_ms == 0
            || self.crl_max_size_mb == 0
            || self.ocsp_timeout_ms == 0
            || self.ocsp_cache_ttl_ms == 0
            || self.max_concurrent_checks == 0
        {
            return Err(SecurityError::InvalidConfiguration(
                "revocation limits and timeouts must be positive".into(),
            ));
        }
        if self.check_method == RevocationCheckMethod::None && self.fail_on_revocation_check_error {
            return Err(SecurityError::InvalidConfiguration(
                "revocation failures cannot be required when checking is disabled".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct CertificateValidationConfiguration {
    pub strict_validation: bool,
    pub allow_self_signed: bool,
    pub require_key_usage: bool,
    pub require_extended_key_usage: bool,
    pub max_chain_length: usize,
    pub verify_chain_signatures: bool,
    pub require_complete_chain: bool,
    pub check_validity_period: bool,
    pub allow_not_yet_valid: bool,
    pub clock_skew_tolerance_ms: u64,
    pub min_rsa_key_size: u32,
    pub min_ecc_key_size: u32,
    pub allowed_signature_algorithms: BTreeSet<String>,
    pub required_key_usages: BTreeSet<String>,
    pub required_extended_key_usages: BTreeSet<String>,
    pub require_common_name: bool,
    pub allow_wildcard_cn: bool,
    pub validate_subject_alt_names: bool,
    pub require_trusted_issuer: bool,
    pub allowed_issuers: BTreeSet<String>,
    pub blocked_issuers: BTreeSet<String>,
}

impl Default for CertificateValidationConfiguration {
    fn default() -> Self {
        Self {
            strict_validation: true,
            allow_self_signed: false,
            require_key_usage: true,
            require_extended_key_usage: true,
            max_chain_length: 10,
            verify_chain_signatures: true,
            require_complete_chain: true,
            check_validity_period: true,
            allow_not_yet_valid: false,
            clock_skew_tolerance_ms: 300_000,
            min_rsa_key_size: 2_048,
            min_ecc_key_size: 256,
            allowed_signature_algorithms: [
                "sha256WithRSAEncryption",
                "sha384WithRSAEncryption",
                "sha512WithRSAEncryption",
                "ecdsa-with-SHA256",
                "ecdsa-with-SHA384",
                "ecdsa-with-SHA512",
                "rsaPSS",
            ]
            .into_iter()
            .map(str::to_owned)
            .collect(),
            required_key_usages: ["digital_signature"]
                .into_iter()
                .map(str::to_owned)
                .collect(),
            required_extended_key_usages: ["client_auth"].into_iter().map(str::to_owned).collect(),
            require_common_name: false,
            allow_wildcard_cn: false,
            validate_subject_alt_names: true,
            require_trusted_issuer: true,
            allowed_issuers: BTreeSet::new(),
            blocked_issuers: BTreeSet::new(),
        }
    }
}

impl CertificateValidationConfiguration {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.max_chain_length == 0
            || self.min_rsa_key_size < 1_024
            || self.min_ecc_key_size < 256
        {
            return Err(SecurityError::InvalidConfiguration(
                "certificate validation security limits are invalid".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct CertificateExtractionConfiguration {
    pub certificate_source: CertificateSource,
    pub certificate_header_name: String,
    pub certificate_header_encoding: String,
    pub certificate_param_name: String,
    pub certificate_param_encoding: String,
    pub certificate_body_field: String,
    pub certificate_body_format: String,
    pub auto_detect_format: bool,
    pub support_certificate_chain: bool,
    pub validate_on_extraction: bool,
    pub require_certificate: bool,
}

impl Default for CertificateExtractionConfiguration {
    fn default() -> Self {
        Self {
            certificate_source: CertificateSource::TlsHandshake,
            certificate_header_name: "X-Client-Cert".into(),
            certificate_header_encoding: "pem".into(),
            certificate_param_name: "client_cert".into(),
            certificate_param_encoding: "url_encoded_pem".into(),
            certificate_body_field: "client_certificate".into(),
            certificate_body_format: "json".into(),
            auto_detect_format: true,
            support_certificate_chain: true,
            validate_on_extraction: true,
            require_certificate: true,
        }
    }
}

impl CertificateExtractionConfiguration {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if !matches!(
            self.certificate_header_encoding.as_str(),
            "pem" | "der" | "base64"
        ) {
            return Err(SecurityError::InvalidConfiguration(
                "invalid certificate header encoding".into(),
            ));
        }
        if !matches!(
            self.certificate_body_format.as_str(),
            "json" | "form" | "raw"
        ) {
            return Err(SecurityError::InvalidConfiguration(
                "invalid certificate body format".into(),
            ));
        }
        for required in [
            &self.certificate_header_name,
            &self.certificate_param_name,
            &self.certificate_body_field,
        ] {
            if required.trim().is_empty() {
                return Err(SecurityError::InvalidConfiguration(
                    "certificate extraction field names cannot be empty".into(),
                ));
            }
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct MtlsConfiguration {
    pub trust_store: TrustStoreConfiguration,
    pub revocation_check: RevocationCheckConfiguration,
    pub certificate_validation: CertificateValidationConfiguration,
    pub certificate_extraction: CertificateExtractionConfiguration,
    pub enable_mtls_auth: bool,
    pub enable_certificate_caching: bool,
    pub enable_revocation_checking: bool,
    pub enable_certificate_pinning: bool,
    pub certificate_cache_size: usize,
    pub certificate_cache_ttl_ms: u64,
    pub validation_timeout_ms: u64,
    pub log_certificate_details: bool,
    pub log_validation_failures: bool,
    pub audit_certificate_usage: bool,
    pub map_certificate_to_user: bool,
    pub user_id_source: String,
    #[serde(default)]
    pub user_role_mapping: BTreeMap<String, Vec<String>>,
    pub development_mode: bool,
    pub allow_untrusted_certs: bool,
    pub skip_hostname_verification: bool,
    #[serde(default)]
    pub pinned_certificates: BTreeMap<String, String>,
    #[serde(default)]
    pub pinned_ca_certificates: BTreeSet<String>,
}

impl MtlsConfiguration {
    pub fn validate(&self) -> Result<(), SecurityError> {
        self.trust_store.validate()?;
        self.revocation_check.validate()?;
        self.certificate_validation.validate()?;
        self.certificate_extraction.validate()?;
        if !self.development_mode && (self.allow_untrusted_certs || self.skip_hostname_verification)
        {
            return Err(SecurityError::InvalidConfiguration(
                "production mTLS cannot allow untrusted certificates or skip hostname verification"
                    .into(),
            ));
        }
        if self.certificate_cache_size == 0
            || self.certificate_cache_ttl_ms == 0
            || self.validation_timeout_ms == 0
        {
            return Err(SecurityError::InvalidConfiguration(
                "mTLS cache and validation limits must be positive".into(),
            ));
        }
        if !matches!(
            self.user_id_source.as_str(),
            "subject_cn" | "subject_email" | "subject_serial" | "san_email" | "custom"
        ) {
            return Err(SecurityError::InvalidConfiguration(
                "invalid mTLS user ID source".into(),
            ));
        }
        if self.enable_certificate_pinning
            && self.pinned_certificates.is_empty()
            && self.pinned_ca_certificates.is_empty()
        {
            return Err(SecurityError::InvalidConfiguration(
                "certificate pinning requires at least one certificate or CA pin".into(),
            ));
        }
        Ok(())
    }

    pub fn development() -> Result<Self, SecurityError> {
        let config = Self {
            trust_store: file_based_trust_store("./dev_certs/ca", Vec::new())?,
            revocation_check: RevocationCheckConfiguration {
                check_method: RevocationCheckMethod::None,
                ..RevocationCheckConfiguration::default()
            },
            certificate_validation: CertificateValidationConfiguration {
                strict_validation: false,
                allow_self_signed: true,
                require_key_usage: false,
                require_extended_key_usage: false,
                clock_skew_tolerance_ms: 3_600_000,
                ..CertificateValidationConfiguration::default()
            },
            certificate_extraction: CertificateExtractionConfiguration::default(),
            enable_mtls_auth: true,
            enable_certificate_caching: true,
            enable_revocation_checking: false,
            enable_certificate_pinning: false,
            certificate_cache_size: 1_000,
            certificate_cache_ttl_ms: 1_800_000,
            validation_timeout_ms: 30_000,
            log_certificate_details: true,
            log_validation_failures: true,
            audit_certificate_usage: false,
            map_certificate_to_user: true,
            user_id_source: "subject_cn".into(),
            user_role_mapping: BTreeMap::new(),
            development_mode: true,
            allow_untrusted_certs: true,
            skip_hostname_verification: true,
            pinned_certificates: BTreeMap::new(),
            pinned_ca_certificates: BTreeSet::new(),
        };
        config.validate()?;
        Ok(config)
    }

    pub fn production(ca_directory: impl Into<String>) -> Result<Self, SecurityError> {
        let config = Self {
            trust_store: file_based_trust_store(ca_directory, Vec::new())?,
            revocation_check: RevocationCheckConfiguration {
                check_method: RevocationCheckMethod::Both,
                fail_on_revocation_check_error: true,
                ..RevocationCheckConfiguration::default()
            },
            certificate_validation: CertificateValidationConfiguration::default(),
            certificate_extraction: CertificateExtractionConfiguration::default(),
            enable_mtls_auth: true,
            enable_certificate_caching: true,
            enable_revocation_checking: true,
            enable_certificate_pinning: false,
            certificate_cache_size: 1_000,
            certificate_cache_ttl_ms: 1_800_000,
            validation_timeout_ms: 30_000,
            log_certificate_details: true,
            log_validation_failures: true,
            audit_certificate_usage: true,
            map_certificate_to_user: true,
            user_id_source: "subject_cn".into(),
            user_role_mapping: BTreeMap::new(),
            development_mode: false,
            allow_untrusted_certs: false,
            skip_hostname_verification: false,
            pinned_certificates: BTreeMap::new(),
            pinned_ca_certificates: BTreeSet::new(),
        };
        config.validate()?;
        Ok(config)
    }

    pub fn high_security(
        pkcs11_module: impl Into<String>,
        pinned_ca_certificates: BTreeSet<String>,
    ) -> Result<Self, SecurityError> {
        let mut config = Self::production("unused-for-pkcs11")?;
        config.trust_store = pkcs11_trust_store(pkcs11_module, 0, None)?;
        config.trust_store.ca_cache_ttl_ms = 1_800_000;
        config.certificate_validation.min_rsa_key_size = 4_096;
        config.certificate_validation.min_ecc_key_size = 384;
        config.certificate_validation.max_chain_length = 5;
        config.certificate_validation.clock_skew_tolerance_ms = 60_000;
        config.revocation_check.crl_cache_ttl_ms = 900_000;
        config.revocation_check.ocsp_timeout_ms = 5_000;
        config.enable_certificate_pinning = true;
        config.pinned_ca_certificates = pinned_ca_certificates;
        config.certificate_cache_ttl_ms = 300_000;
        config.validation_timeout_ms = 10_000;
        config.validate()?;
        Ok(config)
    }
}

pub fn file_based_trust_store(
    ca_directory: impl Into<String>,
    ca_cert_files: Vec<String>,
) -> Result<TrustStoreConfiguration, SecurityError> {
    let configuration = TrustStoreConfiguration {
        store_type: TrustStoreType::FileSystem,
        store_path: None,
        store_password: None,
        ca_cert_files,
        ca_cert_directory: Some(ca_directory.into()),
        pkcs11_module: None,
        pkcs11_slot: None,
        pkcs11_pin: None,
        db_connection_string: None,
        ca_table_name: "trusted_cas".into(),
        ldap_server_url: None,
        ldap_base_dn: None,
        ldap_bind_dn: None,
        ldap_bind_password: None,
        enable_ca_cache: true,
        ca_cache_ttl_ms: 86_400_000,
        max_cached_cas: 1_000,
        auto_reload_cas: true,
        reload_interval_ms: 3_600_000,
    };
    configuration.validate()?;
    Ok(configuration)
}

pub fn pkcs11_trust_store(
    module_path: impl Into<String>,
    slot: u64,
    pin: Option<String>,
) -> Result<TrustStoreConfiguration, SecurityError> {
    let configuration = TrustStoreConfiguration {
        store_type: TrustStoreType::Pkcs11,
        store_path: None,
        store_password: None,
        ca_cert_files: Vec::new(),
        ca_cert_directory: None,
        pkcs11_module: Some(module_path.into()),
        pkcs11_slot: Some(slot),
        pkcs11_pin: pin,
        db_connection_string: None,
        ca_table_name: "trusted_cas".into(),
        ldap_server_url: None,
        ldap_base_dn: None,
        ldap_bind_dn: None,
        ldap_bind_password: None,
        enable_ca_cache: true,
        ca_cache_ttl_ms: 86_400_000,
        max_cached_cas: 1_000,
        auto_reload_cas: true,
        reload_interval_ms: 3_600_000,
    };
    configuration.validate()?;
    Ok(configuration)
}

pub fn common_mtls_configuration(
    trust_store_path: Option<String>,
    ca_cert_files: Vec<String>,
    strict_validation: bool,
    check_revocation: bool,
) -> Result<MtlsConfiguration, SecurityError> {
    if trust_store_path.as_deref().is_none_or(str::is_empty) && ca_cert_files.is_empty() {
        return Err(SecurityError::InvalidConfiguration(
            "common mTLS configuration requires explicit trust material".into(),
        ));
    }
    let mut config = MtlsConfiguration::production(
        trust_store_path
            .clone()
            .unwrap_or_else(|| "explicit-files".into()),
    )?;
    config.trust_store.store_path = trust_store_path;
    config.trust_store.ca_cert_files = ca_cert_files;
    config.certificate_validation.strict_validation = strict_validation;
    config.certificate_validation.require_trusted_issuer = strict_validation;
    config.enable_revocation_checking = check_revocation;
    config.revocation_check.check_method = if check_revocation {
        RevocationCheckMethod::Crl
    } else {
        RevocationCheckMethod::None
    };
    config.revocation_check.fail_on_revocation_check_error = false;
    config.validate()?;
    Ok(config)
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MtlsAuthenticationStatus {
    Success,
    Failed,
    Pending,
    Expired,
    Revoked,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum UserMappingMethod {
    SubjectCn,
    SubjectEmail,
    SubjectSerial,
    SanEmail,
    SanUpn,
    IssuerSerial,
    Fingerprint,
    Custom,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct CertificateIdentity {
    pub user_id: String,
    pub user_email: Option<String>,
    pub user_name: Option<String>,
    pub user_principal_name: Option<String>,
    pub certificate_fingerprint: String,
    pub certificate_serial: String,
    pub certificate_issuer: String,
    pub certificate_subject: String,
    pub organization: Option<String>,
    pub organizational_unit: Option<String>,
    pub department: Option<String>,
    pub title: Option<String>,
    #[serde(default)]
    pub custom_attributes: BTreeMap<String, String>,
    #[serde(default)]
    pub groups: BTreeSet<String>,
    #[serde(default)]
    pub roles: BTreeSet<String>,
}

impl CertificateIdentity {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.user_id.trim().is_empty() {
            return Err(SecurityError::InvalidIdentity(
                "mTLS user ID cannot be empty".into(),
            ));
        }
        if self
            .user_email
            .as_deref()
            .is_some_and(|email| !email.contains('@'))
        {
            return Err(SecurityError::InvalidIdentity(
                "invalid mTLS email address".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct MtlsAuthenticationContext {
    pub request_id: String,
    pub client_ip: String,
    pub user_agent: Option<String>,
    pub request_timestamp_ms: u64,
    pub tls_version: Option<String>,
    pub cipher_suite: Option<String>,
    pub client_certificate_chain_length: usize,
    pub certificate_source: String,
    pub certificate_header: Option<String>,
    pub authentication_method: String,
    pub trust_store_used: Option<String>,
    pub ca_certificate_used: Option<String>,
    pub requires_additional_auth: bool,
    pub security_level: String,
    #[serde(default)]
    pub compliance_flags: BTreeSet<String>,
}

impl MtlsAuthenticationContext {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.request_id.trim().is_empty() || self.client_ip.trim().is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "mTLS request ID and client IP cannot be empty".into(),
            ));
        }
        if self.client_certificate_chain_length == 0 {
            return Err(SecurityError::InvalidConfiguration(
                "mTLS certificate chain cannot be empty".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct MtlsAuthenticationResult {
    pub status: MtlsAuthenticationStatus,
    pub authenticated: bool,
    pub client_certificate: Option<ClientCertificate>,
    pub validation_result: Option<CertificateValidationResult>,
    pub certificate_identity: Option<CertificateIdentity>,
    pub mapped_user: Option<AuthenticatedUser>,
    pub user_id: Option<String>,
    pub context: Option<MtlsAuthenticationContext>,
    pub error_code: Option<String>,
    pub error_message: Option<String>,
    #[serde(default)]
    pub error_details: BTreeMap<String, Value>,
    pub trust_level: String,
    pub authentication_strength: String,
    pub requires_step_up_auth: bool,
    pub session_id: Option<String>,
    pub session_expiry_ms: Option<u64>,
    pub max_session_duration_ms: u64,
    pub authenticated_at_ms: u64,
    pub authentication_duration_ms: u64,
    pub validation_duration_ms: u64,
    #[serde(default)]
    pub granted_roles: BTreeSet<String>,
    #[serde(default)]
    pub granted_permissions: BTreeSet<String>,
    #[serde(default)]
    pub access_constraints: BTreeMap<String, Value>,
}

impl MtlsAuthenticationResult {
    pub fn validate(&self) -> Result<(), SecurityError> {
        let success = self.status == MtlsAuthenticationStatus::Success;
        if self.authenticated != success
            || (self.authenticated && self.certificate_identity.is_none())
        {
            return Err(SecurityError::InvalidAuthenticationResult);
        }
        if self.authenticated
            && self
                .validation_result
                .as_ref()
                .is_none_or(|result| !result.is_valid || !result.is_trusted)
        {
            return Err(SecurityError::InvalidAuthenticationResult);
        }
        Ok(())
    }

    pub fn success(
        certificate: ClientCertificate,
        validation_result: CertificateValidationResult,
        identity: CertificateIdentity,
        context: MtlsAuthenticationContext,
        user: Option<AuthenticatedUser>,
        authenticated_at_ms: u64,
    ) -> Result<Self, SecurityError> {
        validation_result.validate()?;
        identity.validate()?;
        context.validate()?;
        if !validation_result.is_valid || !validation_result.is_trusted {
            return Err(SecurityError::InvalidAuthenticationResult);
        }
        let user_id = user
            .as_ref()
            .map(|mapped| mapped.user_id.clone())
            .or_else(|| Some(identity.user_id.clone()));
        let result = Self {
            status: MtlsAuthenticationStatus::Success,
            authenticated: true,
            client_certificate: Some(certificate),
            validation_result: Some(validation_result),
            certificate_identity: Some(identity.clone()),
            mapped_user: user,
            user_id,
            context: Some(context),
            error_code: None,
            error_message: None,
            error_details: BTreeMap::new(),
            trust_level: "high".into(),
            authentication_strength: "strong".into(),
            requires_step_up_auth: false,
            session_id: None,
            session_expiry_ms: None,
            max_session_duration_ms: 28_800_000,
            authenticated_at_ms,
            authentication_duration_ms: 0,
            validation_duration_ms: 0,
            granted_roles: identity.roles,
            granted_permissions: BTreeSet::new(),
            access_constraints: BTreeMap::new(),
        };
        result.validate()?;
        Ok(result)
    }

    #[must_use]
    pub fn failure(
        error_code: impl Into<String>,
        error_message: impl Into<String>,
        authenticated_at_ms: u64,
    ) -> Self {
        Self {
            status: MtlsAuthenticationStatus::Failed,
            authenticated: false,
            client_certificate: None,
            validation_result: None,
            certificate_identity: None,
            mapped_user: None,
            user_id: None,
            context: None,
            error_code: Some(error_code.into()),
            error_message: Some(error_message.into()),
            error_details: BTreeMap::new(),
            trust_level: "none".into(),
            authentication_strength: "weak".into(),
            requires_step_up_auth: false,
            session_id: None,
            session_expiry_ms: None,
            max_session_duration_ms: 28_800_000,
            authenticated_at_ms,
            authentication_duration_ms: 0,
            validation_duration_ms: 0,
            granted_roles: BTreeSet::new(),
            granted_permissions: BTreeSet::new(),
            access_constraints: BTreeMap::new(),
        }
    }

    #[must_use]
    pub fn revoked(
        certificate: ClientCertificate,
        validation_result: CertificateValidationResult,
        context: MtlsAuthenticationContext,
        reason: impl Into<String>,
        authenticated_at_ms: u64,
    ) -> Self {
        let reason = reason.into();
        let mut result = Self::failure(
            "CERTIFICATE_REVOKED",
            format!("Certificate has been revoked: {reason}"),
            authenticated_at_ms,
        );
        result.status = MtlsAuthenticationStatus::Revoked;
        result.client_certificate = Some(certificate);
        result.validation_result = Some(validation_result);
        result.context = Some(context);
        result
            .error_details
            .insert("revocation_reason".into(), Value::String(reason));
        result
    }

    #[must_use]
    pub fn has_role(&self, role: &str) -> bool {
        self.granted_roles.contains(role)
    }

    #[must_use]
    pub fn has_permission(&self, permission: &str) -> bool {
        self.granted_permissions.contains(permission)
    }

    #[must_use]
    pub fn is_session_valid_at(&self, now_ms: u64) -> bool {
        self.authenticated && self.session_expiry_ms.is_none_or(|expiry| now_ms < expiry)
    }

    #[must_use]
    pub fn remaining_session_time_at(&self, now_ms: u64) -> Option<u64> {
        self.session_expiry_ms
            .map(|expiry| expiry.saturating_sub(now_ms))
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct MtlsUserMapping {
    pub mapping_method: UserMappingMethod,
    pub user_id_pattern: Option<String>,
    pub email_pattern: Option<String>,
    pub name_pattern: Option<String>,
    pub use_subject_cn: bool,
    pub use_subject_email: bool,
    pub use_subject_ou: bool,
    pub use_san_email: bool,
    pub use_san_upn: bool,
    pub use_san_dns: bool,
    pub default_domain: Option<String>,
    #[serde(default)]
    pub email_domain_mapping: BTreeMap<String, String>,
    pub user_id_transformation: String,
    pub role_mapping_enabled: bool,
    #[serde(default)]
    pub role_mapping_rules: BTreeMap<String, Vec<String>>,
    #[serde(default)]
    pub default_roles: BTreeSet<String>,
    pub map_organizational_info: bool,
    #[serde(default)]
    pub department_mapping: BTreeMap<String, String>,
}

impl MtlsUserMapping {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if !matches!(
            self.user_id_transformation.as_str(),
            "lowercase" | "uppercase" | "none"
        ) {
            return Err(SecurityError::InvalidConfiguration(
                "invalid mTLS user ID transformation".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn transform_user_id(&self, user_id: &str) -> String {
        match self.user_id_transformation.as_str() {
            "lowercase" => user_id.to_lowercase(),
            "uppercase" => user_id.to_uppercase(),
            _ => user_id.to_owned(),
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct MtlsSession {
    pub session_id: String,
    pub user_id: String,
    pub certificate_fingerprint: String,
    pub certificate_serial: String,
    pub certificate_issuer: String,
    pub created_at_ms: u64,
    pub expires_at_ms: Option<u64>,
    pub last_activity_ms: u64,
    pub is_active: bool,
    pub client_ip: String,
    pub user_agent: Option<String>,
    pub authentication_context: Option<MtlsAuthenticationContext>,
    pub trust_level: String,
    pub authentication_strength: String,
    pub requires_revalidation: bool,
    #[serde(default)]
    pub session_attributes: BTreeMap<String, Value>,
    #[serde(default)]
    pub granted_roles: BTreeSet<String>,
    #[serde(default)]
    pub granted_permissions: BTreeSet<String>,
}

impl MtlsSession {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.session_id.trim().is_empty()
            || self.user_id.trim().is_empty()
            || self.certificate_fingerprint.trim().is_empty()
            || self.certificate_serial.trim().is_empty()
            || self.certificate_issuer.trim().is_empty()
            || self.client_ip.trim().is_empty()
        {
            return Err(SecurityError::InvalidSessionState);
        }
        if self
            .expires_at_ms
            .is_some_and(|expiry| expiry < self.created_at_ms)
        {
            return Err(SecurityError::InvalidSessionState);
        }
        Ok(())
    }

    pub fn update_activity(&mut self, now_ms: u64) -> Result<(), SecurityError> {
        if now_ms < self.created_at_ms {
            return Err(SecurityError::InvalidSessionState);
        }
        self.last_activity_ms = now_ms;
        Ok(())
    }

    #[must_use]
    pub fn is_expired_at(&self, now_ms: u64) -> bool {
        self.expires_at_ms.is_some_and(|expiry| now_ms > expiry)
    }

    #[must_use]
    pub fn is_valid_at(&self, now_ms: u64) -> bool {
        self.is_active && !self.is_expired_at(now_ms)
    }

    pub fn invalidate(&mut self) {
        self.is_active = false;
    }
    pub fn add_role(&mut self, role: impl Into<String>) {
        self.granted_roles.insert(role.into());
    }
    pub fn remove_role(&mut self, role: &str) {
        self.granted_roles.remove(role);
    }
    pub fn add_permission(&mut self, permission: impl Into<String>) {
        self.granted_permissions.insert(permission.into());
    }
    pub fn remove_permission(&mut self, permission: &str) {
        self.granted_permissions.remove(permission);
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct MtlsAuthenticationEvent {
    pub event_id: String,
    pub event_type: String,
    pub event_timestamp_ms: u64,
    pub authentication_result: MtlsAuthenticationResult,
    pub user_id: Option<String>,
    pub client_ip: String,
    pub certificate_fingerprint: String,
    pub certificate_issuer: String,
    pub certificate_subject: String,
    pub trust_level: String,
    pub risk_score: u8,
    #[serde(default)]
    pub anomaly_flags: BTreeSet<String>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

impl MtlsAuthenticationEvent {
    pub fn new(
        event_type: impl Into<String>,
        authentication_result: MtlsAuthenticationResult,
        event_timestamp_ms: u64,
    ) -> Self {
        Self {
            event_id: Uuid::new_v4().to_string(),
            event_type: event_type.into(),
            event_timestamp_ms,
            authentication_result,
            user_id: None,
            client_ip: String::new(),
            certificate_fingerprint: String::new(),
            certificate_issuer: String::new(),
            certificate_subject: String::new(),
            trust_level: "none".into(),
            risk_score: 0,
            anomaly_flags: BTreeSet::new(),
            metadata: BTreeMap::new(),
        }
    }

    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.event_id.trim().is_empty()
            || self.event_type.trim().is_empty()
            || self.risk_score > 100
        {
            return Err(SecurityError::InvalidConfiguration(
                "invalid mTLS authentication event".into(),
            ));
        }
        self.authentication_result.validate()
    }
}

/// Transport-neutral certificate material extracted by an HTTP/TLS adapter.
#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct CertificateRequestInput {
    #[serde(default)]
    pub tls_chain_der: Vec<Vec<u8>>,
    #[serde(default)]
    pub headers: BTreeMap<String, String>,
    #[serde(default)]
    pub query: BTreeMap<String, String>,
    pub body: Option<Value>,
}

#[async_trait]
pub trait CertificateParser: Send + Sync {
    async fn parse_pem(&self, pem: &str) -> Result<ClientCertificate, SecurityError>;
    async fn parse_der(&self, der: &[u8]) -> Result<ClientCertificate, SecurityError>;
}

#[async_trait]
pub trait CertificateValidator: Send + Sync {
    async fn validate_certificate(
        &self,
        certificate: &ClientCertificate,
        supplied_chain: &[ClientCertificate],
        policy: &CertificateValidationPolicy,
        now_ms: u64,
    ) -> Result<CertificateValidationResult, SecurityError>;
}

#[async_trait]
pub trait TrustStore: Send + Sync {
    async fn trusted_authorities(&self) -> Result<Vec<CertificateAuthority>, SecurityError>;
    async fn find_issuer(
        &self,
        issuer: &CertificateIssuer,
    ) -> Result<Option<CertificateAuthority>, SecurityError>;
    async fn reload(&self) -> Result<(), SecurityError>;
}

#[async_trait]
pub trait RevocationProvider: Send + Sync {
    async fn check_revocation(
        &self,
        certificate: &ClientCertificate,
        method: RevocationCheckMethod,
        now_ms: u64,
    ) -> Result<CertificateStatus, SecurityError>;
}

#[async_trait]
pub trait CertificateExtractor: Send + Sync {
    async fn extract(
        &self,
        input: &CertificateRequestInput,
        configuration: &CertificateExtractionConfiguration,
    ) -> Result<Vec<ClientCertificate>, SecurityError>;
}

#[async_trait]
pub trait MtlsIdentityMapper: Send + Sync {
    async fn map_identity(
        &self,
        certificate: &ClientCertificate,
        mapping: &MtlsUserMapping,
    ) -> Result<CertificateIdentity, SecurityError>;
}

#[async_trait]
pub trait MtlsAuthenticator: Send + Sync {
    async fn authenticate(
        &self,
        input: &CertificateRequestInput,
        context: &MtlsAuthenticationContext,
        configuration: &MtlsConfiguration,
        now_ms: u64,
    ) -> Result<MtlsAuthenticationResult, SecurityError>;
}

/// Complete provider set required by the canonical mTLS orchestration path.
#[derive(Default)]
pub struct MtlsProviders {
    pub parser: Option<Arc<dyn CertificateParser>>,
    pub validator: Option<Arc<dyn CertificateValidator>>,
    pub trust_store: Option<Arc<dyn TrustStore>>,
    pub revocation: Option<Arc<dyn RevocationProvider>>,
    pub extractor: Option<Arc<dyn CertificateExtractor>>,
    pub identity_mapper: Option<Arc<dyn MtlsIdentityMapper>>,
    pub authenticator: Option<Arc<dyn MtlsAuthenticator>>,
}

impl MtlsProviders {
    pub fn validate(&self, configuration: &MtlsConfiguration) -> Result<(), SecurityError> {
        configuration.validate()?;
        let mut missing = Vec::new();
        if self.parser.is_none() {
            missing.push("certificate_parser");
        }
        if self.validator.is_none() {
            missing.push("certificate_validator");
        }
        if self.trust_store.is_none() {
            missing.push("trust_store");
        }
        if configuration.enable_revocation_checking && self.revocation.is_none() {
            missing.push("revocation_provider");
        }
        if self.extractor.is_none() {
            missing.push("certificate_extractor");
        }
        if configuration.map_certificate_to_user && self.identity_mapper.is_none() {
            missing.push("identity_mapper");
        }
        if self.authenticator.is_none() {
            missing.push("mtls_authenticator");
        }
        if missing.is_empty() {
            Ok(())
        } else {
            Err(SecurityError::RequiredProvidersUnavailable(missing))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture() -> Value {
        serde_json::from_str(include_str!(
            "../../../contracts/identity-mtls-behavior.json"
        ))
        .expect("valid mTLS behavioral fixture")
    }

    fn fixture_certificate() -> ClientCertificate {
        let fixture = fixture();
        let certificate = &fixture["certificate"];
        ClientCertificate {
            pem_data: certificate["pem_data"].as_str().expect("PEM").to_owned(),
            der_data: certificate["der_text"]
                .as_str()
                .expect("DER text")
                .as_bytes()
                .to_vec(),
            serial_number: certificate["serial_number"].as_str().map(str::to_owned),
            fingerprint_sha1: certificate["fingerprint_sha1"].as_str().map(str::to_owned),
            fingerprint_sha256: certificate["fingerprint_sha256"]
                .as_str()
                .map(str::to_owned),
            not_valid_before_ms: certificate["not_valid_before_ms"].as_u64(),
            not_valid_after_ms: certificate["not_valid_after_ms"].as_u64(),
            subject: Some(CertificateSubject {
                common_name: Some("device.example.com".into()),
                organization: Some("Example Org".into()),
                organizational_unit: Some("Identity".into()),
                email_address: Some("alex@example.com".into()),
                user_id: Some("user-123".into()),
                ..CertificateSubject::default()
            }),
            issuer: Some(CertificateIssuer {
                common_name: Some("Example Root CA".into()),
                organization: Some("Example Trust".into()),
                ca_identifier: Some("ca-123".into()),
                ..CertificateIssuer::default()
            }),
            certificate_type: CertificateType::Client,
            key_usage: ["digital_signature"]
                .into_iter()
                .map(str::to_owned)
                .collect(),
            extended_key_usage: ["client_auth"].into_iter().map(str::to_owned).collect(),
            subject_alternative_name: SubjectAlternativeName {
                dns_names: ["*.service.example.com"]
                    .into_iter()
                    .map(str::to_owned)
                    .collect(),
                email_addresses: ["alex@example.com"]
                    .into_iter()
                    .map(str::to_owned)
                    .collect(),
                ..SubjectAlternativeName::default()
            },
            signature_algorithm: Some("sha256WithRSAEncryption".into()),
            public_key_algorithm: Some("RSA".into()),
            public_key_size: Some(2_048),
            is_self_signed: false,
            ca_certificate: None,
            extensions: Vec::new(),
        }
    }

    #[test]
    fn language_neutral_certificate_behavior() {
        let fixture = fixture();
        assert_eq!(fixture["schema_version"], 1);
        let certificate = fixture_certificate();
        certificate.validate().expect("valid fixture certificate");
        let case = &fixture["certificate"];
        assert!(certificate.is_valid_at(case["valid_at_ms"].as_u64().expect("valid time")));
        assert!(
            !certificate.is_valid_at(case["not_yet_valid_at_ms"].as_u64().expect("early time"))
        );
        assert!(certificate.is_expired_at(case["expired_at_ms"].as_u64().expect("expired time")));
        assert!(certificate.expires_soon_at(
            case["warning_at_ms"].as_u64().expect("warning time"),
            case["warning_window_ms"].as_u64().expect("warning window"),
        ));
        assert!(certificate.has_key_usage(case["key_usage"].as_str().expect("key usage")));
        assert!(
            certificate.has_extended_key_usage(case["extended_key_usage"].as_str().expect("EKU"))
        );
        assert!(certificate.matches_hostname(case["exact_hostname"].as_str().expect("exact host")));
        assert!(
            certificate
                .matches_hostname(case["wildcard_hostname"].as_str().expect("wildcard host"))
        );
        assert!(
            !certificate.matches_hostname(
                case["invalid_deep_wildcard_hostname"]
                    .as_str()
                    .expect("deep host")
            )
        );
        assert!(certificate.matches_email(case["matching_email"].as_str().expect("email")));
        let der = case["der_text"].as_str().expect("DER text").as_bytes();
        assert_eq!(
            calculate_certificate_fingerprint(der, FingerprintAlgorithm::Sha1).expect("SHA-1"),
            case["fingerprint_sha1"]
        );
        assert_eq!(
            calculate_certificate_fingerprint(der, FingerprintAlgorithm::Sha256).expect("SHA-256"),
            case["fingerprint_sha256"]
        );
    }

    #[test]
    fn language_neutral_authority_revocation_and_policy_behavior() {
        let fixture = fixture();
        let certificate = fixture_certificate();
        let authority = CertificateAuthority {
            ca_name: fixture["authority"]["ca_name"]
                .as_str()
                .expect("CA name")
                .into(),
            ca_certificate: certificate.clone(),
            trusted: true,
            trust_level: CertificateTrustLevel::Full,
            can_issue_client_certs: true,
            can_issue_server_certs: true,
            can_issue_ca_certs: false,
            check_revocation: true,
            require_valid_chain: true,
            crl_urls: BTreeSet::new(),
            ocsp_urls: BTreeSet::new(),
        };
        assert!(authority.is_trusted());
        assert!(authority.can_issue(CertificateType::Client));
        assert!(!authority.can_issue(CertificateType::Ca));

        let crl = CertificateRevocationList {
            issuer: certificate.issuer.clone().expect("issuer"),
            this_update_ms: fixture["crl"]["this_update_ms"]
                .as_u64()
                .expect("this update"),
            next_update_ms: fixture["crl"]["next_update_ms"].as_u64(),
            revoked_serial_numbers: fixture["crl"]["revoked_serial_numbers"]
                .as_array()
                .expect("serials")
                .iter()
                .map(|value| value.as_str().expect("serial").to_owned())
                .collect(),
            crl_url: None,
            crl_data: None,
        };
        assert!(crl.is_current_at(fixture["crl"]["current_at_ms"].as_u64().expect("current")));
        assert!(!crl.is_current_at(fixture["crl"]["stale_at_ms"].as_u64().expect("stale")));
        assert!(crl.is_certificate_revoked("DEAD"));

        let policy = CertificateValidationPolicy::default();
        assert!(
            policy.is_signature_algorithm_allowed(
                fixture["validation"]["allowed_signature_algorithm"]
                    .as_str()
                    .expect("algorithm")
            )
        );
        assert!(
            !policy.is_signature_algorithm_allowed(
                fixture["validation"]["blocked_signature_algorithm"]
                    .as_str()
                    .expect("blocked algorithm")
            )
        );
        assert!(policy.is_key_usage_valid(["digital_signature", "key_encipherment"]));
        assert!(!policy.is_key_usage_valid(["certificate_signing"]));
    }

    #[test]
    fn complete_configuration_factories_are_valid_and_secrets_are_redacted() {
        let fixture = fixture();
        let development = MtlsConfiguration::development().expect("development config");
        assert_eq!(
            development.trust_store.ca_cert_directory.as_deref(),
            fixture["configuration"]["development_ca_directory"].as_str()
        );
        let production = MtlsConfiguration::production(
            fixture["configuration"]["production_ca_directory"]
                .as_str()
                .expect("production CA"),
        )
        .expect("production config");
        assert!(production.revocation_check.fail_on_revocation_check_error);
        let pins = ["ABCD".to_owned()].into_iter().collect();
        let high = MtlsConfiguration::high_security(
            fixture["configuration"]["pkcs11_module"]
                .as_str()
                .expect("PKCS#11 module"),
            pins,
        )
        .expect("high-security config");
        assert_eq!(high.trust_store.store_type, TrustStoreType::Pkcs11);
        let store = pkcs11_trust_store("module", 0, Some("secret".into())).expect("PKCS#11 store");
        assert!(
            !serde_json::to_string(&store)
                .expect("serialize")
                .contains("secret")
        );
        assert!(common_mtls_configuration(None, Vec::new(), true, true).is_err());
    }

    #[test]
    #[allow(clippy::too_many_lines)]
    fn authentication_and_session_contracts_fail_closed() {
        let fixture = fixture();
        let certificate = fixture_certificate();
        let validation = create_validation_result(
            CertificateStatus::Valid,
            true,
            Some(certificate.clone()),
            Vec::new(),
            Vec::new(),
            5_000,
        );
        let identity = CertificateIdentity {
            user_id: fixture["authentication"]["user_id"]
                .as_str()
                .expect("user ID")
                .into(),
            user_email: fixture["authentication"]["email"]
                .as_str()
                .map(str::to_owned),
            user_name: None,
            user_principal_name: None,
            certificate_fingerprint: fixture["authentication"]["fingerprint"]
                .as_str()
                .expect("fingerprint")
                .into(),
            certificate_serial: "01AB".into(),
            certificate_issuer: "Example Root CA".into(),
            certificate_subject: "device.example.com".into(),
            organization: None,
            organizational_unit: None,
            department: None,
            title: None,
            custom_attributes: BTreeMap::new(),
            groups: BTreeSet::new(),
            roles: BTreeSet::new(),
        };
        let context = MtlsAuthenticationContext {
            request_id: fixture["authentication"]["request_id"]
                .as_str()
                .expect("request ID")
                .into(),
            client_ip: fixture["authentication"]["client_ip"]
                .as_str()
                .expect("client IP")
                .into(),
            user_agent: None,
            request_timestamp_ms: 5_000,
            tls_version: Some("TLSv1.3".into()),
            cipher_suite: None,
            client_certificate_chain_length: 1,
            certificate_source: "tls_handshake".into(),
            certificate_header: None,
            authentication_method: "mtls".into(),
            trust_store_used: None,
            ca_certificate_used: None,
            requires_additional_auth: false,
            security_level: "standard".into(),
            compliance_flags: BTreeSet::new(),
        };
        let mut result = MtlsAuthenticationResult::success(
            certificate,
            validation,
            identity,
            context,
            None,
            5_000,
        )
        .expect("successful result");
        result.granted_roles.insert(
            fixture["authentication"]["role"]
                .as_str()
                .expect("role")
                .into(),
        );
        result.granted_permissions.insert(
            fixture["authentication"]["permission"]
                .as_str()
                .expect("permission")
                .into(),
        );
        assert!(result.has_role("issuer"));
        assert!(result.has_permission("credential:issue"));

        let mut session = MtlsSession {
            session_id: fixture["authentication"]["session_id"]
                .as_str()
                .expect("session ID")
                .into(),
            user_id: "user-123".into(),
            certificate_fingerprint: "fingerprint".into(),
            certificate_serial: "01AB".into(),
            certificate_issuer: "Example Root CA".into(),
            created_at_ms: fixture["authentication"]["session_created_at_ms"]
                .as_u64()
                .expect("created"),
            expires_at_ms: fixture["authentication"]["session_expires_at_ms"].as_u64(),
            last_activity_ms: 1_000,
            is_active: true,
            client_ip: "192.0.2.10".into(),
            user_agent: None,
            authentication_context: None,
            trust_level: "high".into(),
            authentication_strength: "strong".into(),
            requires_revalidation: false,
            session_attributes: BTreeMap::new(),
            granted_roles: BTreeSet::new(),
            granted_permissions: BTreeSet::new(),
        };
        assert!(
            session.is_valid_at(
                fixture["authentication"]["session_active_at_ms"]
                    .as_u64()
                    .expect("active")
            )
        );
        assert!(
            session.is_expired_at(
                fixture["authentication"]["session_expired_at_ms"]
                    .as_u64()
                    .expect("expired")
            )
        );
        session.invalidate();
        assert!(!session.is_valid_at(5_000));

        let invalid = create_validation_result(
            CertificateStatus::Valid,
            true,
            None,
            vec!["unexpected".into()],
            Vec::new(),
            0,
        );
        assert!(invalid.validate().is_err());
        let providers = MtlsProviders::default();
        assert!(matches!(
            providers.validate(&MtlsConfiguration::development().expect("configuration")),
            Err(SecurityError::RequiredProvidersUnavailable(_))
        ));
    }
}
