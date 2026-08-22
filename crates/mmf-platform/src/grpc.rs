use std::{fs, path::Path, time::Duration};

use serde::{Deserialize, Serialize};
use tonic::transport::{
    Certificate, Channel, ClientTlsConfig, Endpoint, Identity, ServerTlsConfig,
};
use url::Url;

use crate::PlatformError;

/// Installs MMF's process-wide Rustls crypto policy when no provider has been
/// selected yet.
///
/// Dependency feature unification can make both Rustls providers available in
/// a service process. Rustls deliberately refuses to choose between them, so
/// MMF selects the ring provider before constructing any gRPC TLS state.
pub fn install_default_crypto_provider() -> Result<(), PlatformError> {
    if rustls::crypto::CryptoProvider::get_default().is_none()
        && rustls::crypto::ring::default_provider()
            .install_default()
            .is_err()
        && rustls::crypto::CryptoProvider::get_default().is_none()
    {
        return Err(PlatformError::ProviderUnavailable(
            "Rustls crypto provider".into(),
        ));
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum GrpcTransportSecurity {
    #[default]
    Plaintext,
    ServerTls,
    MutualTls,
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum GrpcTrustMode {
    #[default]
    NativeRoots,
    CustomCa,
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum GrpcServerClientAuthentication {
    #[default]
    Disabled,
    Required,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct GrpcChannelConfig {
    pub target: String,
    #[serde(default)]
    pub security: GrpcTransportSecurity,
    #[serde(default)]
    pub trust: GrpcTrustMode,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub server_name: Option<String>,
    #[serde(default = "default_connect_timeout_ms")]
    pub connect_timeout_ms: u64,
    #[serde(default = "default_request_timeout_ms")]
    pub request_timeout_ms: u64,
    #[serde(default = "default_tcp_keepalive_ms")]
    pub tcp_keepalive_ms: u64,
    #[serde(default = "default_http2_keepalive_interval_ms")]
    pub http2_keepalive_interval_ms: u64,
    #[serde(default = "default_http2_keepalive_timeout_ms")]
    pub http2_keepalive_timeout_ms: u64,
}

impl GrpcChannelConfig {
    pub fn validate(&self, material: &GrpcTlsMaterial) -> Result<(), PlatformError> {
        let url = validated_target(&self.target)?;
        bounded_milliseconds(self.connect_timeout_ms, "connect timeout")?;
        bounded_milliseconds(self.request_timeout_ms, "request timeout")?;
        bounded_milliseconds(self.tcp_keepalive_ms, "TCP keepalive")?;
        bounded_milliseconds(
            self.http2_keepalive_interval_ms,
            "HTTP/2 keepalive interval",
        )?;
        bounded_milliseconds(self.http2_keepalive_timeout_ms, "HTTP/2 keepalive timeout")?;
        if let Some(server_name) = &self.server_name {
            validate_server_name(server_name)?;
        }
        match self.security {
            GrpcTransportSecurity::Plaintext => {
                if url.scheme() != "http"
                    || self.trust != GrpcTrustMode::NativeRoots
                    || self.server_name.is_some()
                    || !material.is_empty()
                {
                    return Err(invalid("plaintext gRPC configuration includes TLS state"));
                }
            }
            GrpcTransportSecurity::ServerTls | GrpcTransportSecurity::MutualTls => {
                if url.scheme() != "https" {
                    return Err(invalid("TLS gRPC target must use https"));
                }
                match self.trust {
                    GrpcTrustMode::NativeRoots if material.ca_certificate_pem.is_some() => {
                        return Err(invalid("native-root trust cannot include a custom CA"));
                    }
                    GrpcTrustMode::CustomCa => validate_certificate(
                        material.ca_certificate_pem.as_deref(),
                        "custom CA certificate",
                    )?,
                    GrpcTrustMode::NativeRoots => {}
                }
                validate_client_identity(self.security, material)?;
            }
        }
        Ok(())
    }
}

impl Default for GrpcChannelConfig {
    fn default() -> Self {
        Self {
            target: "http://127.0.0.1:50051".into(),
            security: GrpcTransportSecurity::Plaintext,
            trust: GrpcTrustMode::NativeRoots,
            server_name: None,
            connect_timeout_ms: default_connect_timeout_ms(),
            request_timeout_ms: default_request_timeout_ms(),
            tcp_keepalive_ms: default_tcp_keepalive_ms(),
            http2_keepalive_interval_ms: default_http2_keepalive_interval_ms(),
            http2_keepalive_timeout_ms: default_http2_keepalive_timeout_ms(),
        }
    }
}

#[derive(Clone, Default)]
pub struct GrpcTlsMaterial {
    pub ca_certificate_pem: Option<Vec<u8>>,
    pub client_certificate_pem: Option<Vec<u8>>,
    pub client_private_key_pem: Option<Vec<u8>>,
}

#[derive(Clone)]
pub struct GrpcServerTlsMaterial {
    client_authentication: GrpcServerClientAuthentication,
    ca_certificate_pem: Option<Vec<u8>>,
    server_certificate_pem: Vec<u8>,
    server_private_key_pem: Vec<u8>,
}

impl GrpcServerTlsMaterial {
    pub fn from_pem_files(
        ca_certificate: &Path,
        server_certificate: &Path,
        server_private_key: &Path,
    ) -> Result<Self, PlatformError> {
        Self::new(
            read_required_secret(ca_certificate, "workload CA certificate")?,
            read_required_secret(server_certificate, "workload server certificate")?,
            read_required_secret(server_private_key, "workload server private key")?,
        )
    }

    pub fn from_server_pem_files(
        server_certificate: &Path,
        server_private_key: &Path,
    ) -> Result<Self, PlatformError> {
        Self::server_only(
            read_required_secret(server_certificate, "workload server certificate")?,
            read_required_secret(server_private_key, "workload server private key")?,
        )
    }

    pub fn new(
        ca_certificate_pem: Vec<u8>,
        server_certificate_pem: Vec<u8>,
        server_private_key_pem: Vec<u8>,
    ) -> Result<Self, PlatformError> {
        Self::with_client_authentication(
            GrpcServerClientAuthentication::Required,
            Some(ca_certificate_pem),
            server_certificate_pem,
            server_private_key_pem,
        )
    }

    pub fn server_only(
        server_certificate_pem: Vec<u8>,
        server_private_key_pem: Vec<u8>,
    ) -> Result<Self, PlatformError> {
        Self::with_client_authentication(
            GrpcServerClientAuthentication::Disabled,
            None,
            server_certificate_pem,
            server_private_key_pem,
        )
    }

    pub fn with_client_authentication(
        client_authentication: GrpcServerClientAuthentication,
        ca_certificate_pem: Option<Vec<u8>>,
        server_certificate_pem: Vec<u8>,
        server_private_key_pem: Vec<u8>,
    ) -> Result<Self, PlatformError> {
        match client_authentication {
            GrpcServerClientAuthentication::Disabled if ca_certificate_pem.is_some() => {
                return Err(invalid(
                    "server-only TLS cannot include a client CA certificate",
                ));
            }
            GrpcServerClientAuthentication::Required => validate_certificate(
                ca_certificate_pem.as_deref(),
                "workload client CA certificate",
            )?,
            GrpcServerClientAuthentication::Disabled => {}
        }
        validate_certificate(Some(&server_certificate_pem), "workload server certificate")?;
        validate_private_key(Some(&server_private_key_pem), "workload server private key")?;
        install_default_crypto_provider()?;
        Ok(Self {
            client_authentication,
            ca_certificate_pem,
            server_certificate_pem,
            server_private_key_pem,
        })
    }

    #[must_use]
    pub const fn client_authentication(&self) -> GrpcServerClientAuthentication {
        self.client_authentication
    }

    #[must_use]
    pub fn server_tls_config(&self) -> ServerTlsConfig {
        let config = ServerTlsConfig::new().identity(Identity::from_pem(
            self.server_certificate_pem.clone(),
            self.server_private_key_pem.clone(),
        ));
        match (&self.client_authentication, &self.ca_certificate_pem) {
            (GrpcServerClientAuthentication::Required, Some(certificate)) => {
                config.client_ca_root(Certificate::from_pem(certificate.clone()))
            }
            (GrpcServerClientAuthentication::Disabled, None) => config,
            _ => unreachable!("validated server TLS material has a consistent client CA policy"),
        }
    }
}

impl GrpcTlsMaterial {
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.ca_certificate_pem.is_none()
            && self.client_certificate_pem.is_none()
            && self.client_private_key_pem.is_none()
    }

    pub fn from_pem_files(
        ca_certificate: Option<&Path>,
        client_certificate: Option<&Path>,
        client_private_key: Option<&Path>,
    ) -> Result<Self, PlatformError> {
        Ok(Self {
            ca_certificate_pem: read_secret(ca_certificate)?,
            client_certificate_pem: read_secret(client_certificate)?,
            client_private_key_pem: read_secret(client_private_key)?,
        })
    }
}

#[derive(Clone)]
pub struct GrpcChannelFactory {
    config: GrpcChannelConfig,
    material: GrpcTlsMaterial,
}

impl GrpcChannelFactory {
    pub fn new(
        config: GrpcChannelConfig,
        material: GrpcTlsMaterial,
    ) -> Result<Self, PlatformError> {
        config.validate(&material)?;
        if config.security != GrpcTransportSecurity::Plaintext {
            install_default_crypto_provider()?;
        }
        Ok(Self { config, material })
    }

    #[must_use]
    pub const fn config(&self) -> &GrpcChannelConfig {
        &self.config
    }

    pub fn endpoint(&self) -> Result<Endpoint, PlatformError> {
        self.config.validate(&self.material)?;
        let mut endpoint = Endpoint::from_shared(self.config.target.clone())
            .map_err(|_| invalid("gRPC target is invalid"))?
            .connect_timeout(Duration::from_millis(self.config.connect_timeout_ms))
            .timeout(Duration::from_millis(self.config.request_timeout_ms))
            .tcp_keepalive(Some(Duration::from_millis(self.config.tcp_keepalive_ms)))
            .http2_keep_alive_interval(Duration::from_millis(
                self.config.http2_keepalive_interval_ms,
            ))
            .keep_alive_timeout(Duration::from_millis(
                self.config.http2_keepalive_timeout_ms,
            ))
            .keep_alive_while_idle(true);
        if self.config.security != GrpcTransportSecurity::Plaintext {
            let host = Url::parse(&self.config.target)
                .ok()
                .and_then(|url| url.host_str().map(str::to_owned))
                .ok_or_else(|| invalid("gRPC target host is invalid"))?;
            let mut tls =
                ClientTlsConfig::new().domain_name(self.config.server_name.clone().unwrap_or(host));
            tls = match self.config.trust {
                GrpcTrustMode::NativeRoots => tls.with_native_roots(),
                GrpcTrustMode::CustomCa => tls.ca_certificate(Certificate::from_pem(
                    self.material
                        .ca_certificate_pem
                        .clone()
                        .ok_or_else(|| invalid("custom CA certificate is required"))?,
                )),
            };
            if self.config.security == GrpcTransportSecurity::MutualTls {
                tls = tls.identity(Identity::from_pem(
                    self.material
                        .client_certificate_pem
                        .clone()
                        .ok_or_else(|| invalid("client certificate is required"))?,
                    self.material
                        .client_private_key_pem
                        .clone()
                        .ok_or_else(|| invalid("client private key is required"))?,
                ));
            }
            endpoint = endpoint
                .tls_config(tls)
                .map_err(|_| invalid("gRPC TLS material is invalid"))?;
        }
        Ok(endpoint)
    }

    pub fn connect_lazy(&self) -> Result<Channel, PlatformError> {
        self.endpoint().map(|endpoint| endpoint.connect_lazy())
    }

    pub async fn connect(&self) -> Result<Channel, PlatformError> {
        self.endpoint()?
            .connect()
            .await
            .map_err(|_| PlatformError::ProviderUnavailable("gRPC dependency".into()))
    }
}

fn validated_target(target: &str) -> Result<Url, PlatformError> {
    let url = Url::parse(target).map_err(|_| invalid("gRPC target is invalid"))?;
    if !matches!(url.scheme(), "http" | "https")
        || url.host_str().is_none()
        || !url.username().is_empty()
        || url.password().is_some()
        || !matches!(url.path(), "" | "/")
        || url.query().is_some()
        || url.fragment().is_some()
    {
        return Err(invalid(
            "gRPC target must be a credential-free HTTP(S) origin",
        ));
    }
    Ok(url)
}

fn validate_server_name(value: &str) -> Result<(), PlatformError> {
    let candidate = Url::parse(&format!("https://{value}"))
        .map_err(|_| invalid("gRPC TLS server name is invalid"))?;
    if candidate.host_str() != Some(value)
        || candidate.port().is_some()
        || candidate.path() != "/"
        || candidate.query().is_some()
        || candidate.fragment().is_some()
    {
        return Err(invalid("gRPC TLS server name is invalid"));
    }
    Ok(())
}

fn validate_client_identity(
    security: GrpcTransportSecurity,
    material: &GrpcTlsMaterial,
) -> Result<(), PlatformError> {
    match security {
        GrpcTransportSecurity::ServerTls => {
            if material.client_certificate_pem.is_some()
                || material.client_private_key_pem.is_some()
            {
                return Err(invalid("server-only TLS cannot include a client identity"));
            }
        }
        GrpcTransportSecurity::MutualTls => {
            validate_certificate(
                material.client_certificate_pem.as_deref(),
                "client certificate",
            )?;
            validate_private_key(
                material.client_private_key_pem.as_deref(),
                "client private key",
            )?;
        }
        GrpcTransportSecurity::Plaintext => {}
    }
    Ok(())
}

fn validate_certificate(value: Option<&[u8]>, name: &str) -> Result<(), PlatformError> {
    value
        .filter(|value| pem_contains(value, b"-----BEGIN CERTIFICATE-----"))
        .map(|_| ())
        .ok_or_else(|| invalid(&format!("{name} is missing or malformed")))
}

fn validate_private_key(value: Option<&[u8]>, name: &str) -> Result<(), PlatformError> {
    value
        .filter(|value| {
            [
                b"-----BEGIN PRIVATE KEY-----".as_slice(),
                b"-----BEGIN RSA PRIVATE KEY-----".as_slice(),
                b"-----BEGIN EC PRIVATE KEY-----".as_slice(),
            ]
            .iter()
            .any(|marker| pem_contains(value, marker))
        })
        .map(|_| ())
        .ok_or_else(|| invalid(&format!("{name} is missing or malformed")))
}

fn pem_contains(value: &[u8], marker: &[u8]) -> bool {
    !value.is_empty() && value.windows(marker.len()).any(|window| window == marker)
}

fn read_secret(path: Option<&Path>) -> Result<Option<Vec<u8>>, PlatformError> {
    path.map(|path| {
        fs::read(path).map_err(|_| {
            PlatformError::InvalidConfiguration("gRPC TLS secret could not be read".into())
        })
    })
    .transpose()
}

fn read_required_secret(path: &Path, name: &str) -> Result<Vec<u8>, PlatformError> {
    fs::read(path)
        .map_err(|_| PlatformError::InvalidConfiguration(format!("{name} could not be read")))
}

fn bounded_milliseconds(value: u64, name: &str) -> Result<(), PlatformError> {
    if (1..=300_000).contains(&value) {
        Ok(())
    } else {
        Err(invalid(&format!("{name} must be between 1 and 300000 ms")))
    }
}

fn invalid(message: &str) -> PlatformError {
    PlatformError::InvalidConfiguration(message.into())
}

const fn default_connect_timeout_ms() -> u64 {
    5_000
}

const fn default_request_timeout_ms() -> u64 {
    10_000
}

const fn default_tcp_keepalive_ms() -> u64 {
    30_000
}

const fn default_http2_keepalive_interval_ms() -> u64 {
    30_000
}

const fn default_http2_keepalive_timeout_ms() -> u64 {
    10_000
}

#[cfg(test)]
mod tests {
    use super::{GrpcServerClientAuthentication, GrpcServerTlsMaterial};

    const CERTIFICATE: &[u8] = b"-----BEGIN CERTIFICATE-----\nfixture\n-----END CERTIFICATE-----\n";
    const PRIVATE_KEY: &[u8] = b"-----BEGIN PRIVATE KEY-----\nfixture\n-----END PRIVATE KEY-----\n";

    #[test]
    fn workload_server_tls_requires_complete_pem_material() {
        let material = GrpcServerTlsMaterial::new(
            CERTIFICATE.to_vec(),
            CERTIFICATE.to_vec(),
            PRIVATE_KEY.to_vec(),
        )
        .expect("complete material");
        let _configuration = material.server_tls_config();
        assert_eq!(
            material.client_authentication(),
            GrpcServerClientAuthentication::Required
        );

        let server_only =
            GrpcServerTlsMaterial::server_only(CERTIFICATE.to_vec(), PRIVATE_KEY.to_vec())
                .expect("server-only material");
        let _configuration = server_only.server_tls_config();
        assert_eq!(
            server_only.client_authentication(),
            GrpcServerClientAuthentication::Disabled
        );

        assert!(
            GrpcServerTlsMaterial::new(Vec::new(), CERTIFICATE.to_vec(), PRIVATE_KEY.to_vec())
                .is_err()
        );
        assert!(
            GrpcServerTlsMaterial::new(CERTIFICATE.to_vec(), Vec::new(), PRIVATE_KEY.to_vec())
                .is_err()
        );
        assert!(
            GrpcServerTlsMaterial::new(CERTIFICATE.to_vec(), CERTIFICATE.to_vec(), Vec::new())
                .is_err()
        );
        assert!(GrpcServerTlsMaterial::server_only(Vec::new(), PRIVATE_KEY.to_vec()).is_err());
        assert!(GrpcServerTlsMaterial::server_only(CERTIFICATE.to_vec(), Vec::new()).is_err());
    }
}
