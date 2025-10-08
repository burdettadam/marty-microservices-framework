"""
Security Policies and Authentication

Comprehensive security management for service mesh including authentication,
authorization, TLS configuration, and certificate management.
"""

import asyncio
import base64
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
)

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

logger = logging.getLogger(__name__)


class AuthenticationMode(Enum):
    """Authentication modes."""

    PERMISSIVE = "permissive"
    STRICT = "strict"
    DISABLE = "disable"


class TLSMode(Enum):
    """TLS modes for service communication."""

    DISABLE = "DISABLE"
    SIMPLE = "SIMPLE"
    MUTUAL = "MUTUAL"
    ISTIO_MUTUAL = "ISTIO_MUTUAL"


class JWTAlgorithm(Enum):
    """JWT signing algorithms."""

    RS256 = "RS256"
    HS256 = "HS256"
    ES256 = "ES256"


class PolicyAction(Enum):
    """Policy actions."""

    ALLOW = "ALLOW"
    DENY = "DENY"


@dataclass
class TLSConfig:
    """TLS configuration for services."""

    mode: TLSMode = TLSMode.ISTIO_MUTUAL
    client_certificate: Optional[str] = None
    private_key: Optional[str] = None
    ca_certificates: Optional[str] = None
    server_certificate: Optional[str] = None

    # Advanced TLS settings
    min_protocol_version: str = "TLSV1_2"
    max_protocol_version: str = "TLSV1_3"
    cipher_suites: List[str] = field(default_factory=list)
    subject_alt_names: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mode": self.mode.value,
            "client_certificate": self.client_certificate,
            "private_key": self.private_key,
            "ca_certificates": self.ca_certificates,
            "server_certificate": self.server_certificate,
            "min_protocol_version": self.min_protocol_version,
            "max_protocol_version": self.max_protocol_version,
            "cipher_suites": self.cipher_suites,
            "subject_alt_names": self.subject_alt_names,
        }


@dataclass
class JWTRule:
    """JWT validation rule."""

    issuer: str
    audiences: List[str] = field(default_factory=list)
    jwks_uri: Optional[str] = None
    jwks: Optional[str] = None
    jwt_headers: List[str] = field(default_factory=lambda: ["authorization"])
    jwt_params: List[str] = field(default_factory=list)

    # JWT validation settings
    forward_original_token: bool = False
    output_payload_to_header: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "issuer": self.issuer,
            "audiences": self.audiences,
            "jwks_uri": self.jwks_uri,
            "jwks": self.jwks,
            "jwt_headers": self.jwt_headers,
            "jwt_params": self.jwt_params,
            "forward_original_token": self.forward_original_token,
            "output_payload_to_header": self.output_payload_to_header,
        }


@dataclass
class AuthenticationPolicy:
    """Authentication policy for services."""

    name: str
    namespace: str = "default"
    targets: List[Dict[str, Any]] = field(default_factory=list)

    # Peer authentication
    peer_authentication_mode: AuthenticationMode = AuthenticationMode.STRICT

    # Request authentication
    jwt_rules: List[JWTRule] = field(default_factory=list)

    # Metadata
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)

    def add_target(self, name: str, port: Optional[int] = None) -> None:
        """Add authentication target."""
        target = {"name": name}
        if port:
            target["port"] = port
        self.targets.append(target)

    def add_jwt_rule(self, jwt_rule: JWTRule) -> None:
        """Add JWT validation rule."""
        self.jwt_rules.append(jwt_rule)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "namespace": self.namespace,
            "targets": self.targets,
            "peer_authentication_mode": self.peer_authentication_mode.value,
            "jwt_rules": [rule.to_dict() for rule in self.jwt_rules],
            "labels": self.labels,
            "annotations": self.annotations,
        }


@dataclass
class PeerAuthentication:
    """Peer authentication configuration."""

    name: str
    namespace: str = "default"
    selector: Dict[str, str] = field(default_factory=dict)
    mtls_mode: AuthenticationMode = AuthenticationMode.STRICT

    # Port-specific mTLS
    port_level_mtls: Dict[int, AuthenticationMode] = field(default_factory=dict)

    # Metadata
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)

    def set_port_mtls(self, port: int, mode: AuthenticationMode) -> None:
        """Set mTLS mode for specific port."""
        self.port_level_mtls[port] = mode

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "namespace": self.namespace,
            "selector": self.selector,
            "mtls_mode": self.mtls_mode.value,
            "port_level_mtls": {
                port: mode.value for port, mode in self.port_level_mtls.items()
            },
            "labels": self.labels,
            "annotations": self.annotations,
        }


@dataclass
class RequestAuthentication:
    """Request authentication configuration."""

    name: str
    namespace: str = "default"
    selector: Dict[str, str] = field(default_factory=dict)
    jwt_rules: List[JWTRule] = field(default_factory=list)

    # Metadata
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)

    def add_jwt_rule(self, jwt_rule: JWTRule) -> None:
        """Add JWT rule."""
        self.jwt_rules.append(jwt_rule)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "namespace": self.namespace,
            "selector": self.selector,
            "jwt_rules": [rule.to_dict() for rule in self.jwt_rules],
            "labels": self.labels,
            "annotations": self.annotations,
        }


@dataclass
class RBACRule:
    """Role-based access control rule."""

    from_sources: List[Dict[str, Any]] = field(default_factory=list)
    to_operations: List[Dict[str, Any]] = field(default_factory=list)
    when_conditions: List[Dict[str, Any]] = field(default_factory=list)

    def add_source_principal(self, principal: str) -> None:
        """Add source principal."""
        self.from_sources.append({"principals": [principal]})

    def add_source_namespace(self, namespace: str) -> None:
        """Add source namespace."""
        self.from_sources.append({"namespaces": [namespace]})

    def add_operation(self, methods: List[str] = None, paths: List[str] = None) -> None:
        """Add operation constraint."""
        operation = {}
        if methods:
            operation["methods"] = methods
        if paths:
            operation["paths"] = paths
        self.to_operations.append(operation)

    def add_condition(self, key: str, values: List[str]) -> None:
        """Add when condition."""
        self.when_conditions.append({"key": key, "values": values})

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "from": self.from_sources,
            "to": self.to_operations,
            "when": self.when_conditions,
        }


@dataclass
class AuthorizationPolicy:
    """Authorization policy for access control."""

    name: str
    namespace: str = "default"
    selector: Dict[str, str] = field(default_factory=dict)
    action: PolicyAction = PolicyAction.ALLOW
    rules: List[RBACRule] = field(default_factory=list)

    # Metadata
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)

    def add_rule(self, rule: RBACRule) -> None:
        """Add authorization rule."""
        self.rules.append(rule)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "namespace": self.namespace,
            "selector": self.selector,
            "action": self.action.value,
            "rules": [rule.to_dict() for rule in self.rules],
            "labels": self.labels,
            "annotations": self.annotations,
        }


@dataclass
class RBACPolicy:
    """RBAC policy configuration."""

    name: str
    namespace: str = "default"
    inclusion_list: List[str] = field(default_factory=list)
    exclusion_list: List[str] = field(default_factory=list)

    def add_inclusion(self, service: str) -> None:
        """Add service to inclusion list."""
        self.inclusion_list.append(service)

    def add_exclusion(self, service: str) -> None:
        """Add service to exclusion list."""
        self.exclusion_list.append(service)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "namespace": self.namespace,
            "inclusion_list": self.inclusion_list,
            "exclusion_list": self.exclusion_list,
        }


@dataclass
class SecurityContext:
    """Security context for service communication."""

    service_account: str
    namespace: str = "default"
    trust_domain: str = "cluster.local"

    # Certificates
    workload_certificate: Optional[str] = None
    workload_private_key: Optional[str] = None
    root_ca_certificate: Optional[str] = None

    # Identity
    identity: Optional[str] = None

    def get_spiffe_identity(self) -> str:
        """Get SPIFFE identity."""
        if self.identity:
            return self.identity

        return f"spiffe://{self.trust_domain}/ns/{self.namespace}/sa/{self.service_account}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "service_account": self.service_account,
            "namespace": self.namespace,
            "trust_domain": self.trust_domain,
            "workload_certificate": self.workload_certificate,
            "workload_private_key": self.workload_private_key,
            "root_ca_certificate": self.root_ca_certificate,
            "identity": self.get_spiffe_identity(),
        }


class CertificateManager:
    """Certificate management for service mesh."""

    def __init__(self, trust_domain: str = "cluster.local"):
        self.trust_domain = trust_domain
        self._ca_certificate: Optional[x509.Certificate] = None
        self._ca_private_key: Optional[rsa.RSAPrivateKey] = None
        self._certificates: Dict[str, Dict[str, Any]] = {}

    def generate_ca_certificate(self, common_name: str = "Istio CA") -> Tuple[str, str]:
        """Generate CA certificate and private key."""
        # Generate private key
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        # Generate certificate
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(x509.NameOID.COMMON_NAME, common_name),
                x509.NameAttribute(x509.NameOID.ORGANIZATION_NAME, "Istio"),
                x509.NameAttribute(x509.NameOID.ORGANIZATIONAL_UNIT_NAME, "Istio CA"),
            ]
        )

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=365 * 10))  # 10 years
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None), critical=True
            )
            .add_extension(
                x509.KeyUsage(
                    key_cert_sign=True,
                    crl_sign=True,
                    digital_signature=False,
                    key_encipherment=False,
                    key_agreement=False,
                    content_commitment=False,
                    data_encipherment=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(private_key, hashes.SHA256())
        )

        self._ca_certificate = cert
        self._ca_private_key = private_key

        # Serialize to PEM format
        cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        return cert_pem, key_pem

    def generate_workload_certificate(
        self, service_account: str, namespace: str
    ) -> Tuple[str, str]:
        """Generate workload certificate for service."""
        if not self._ca_certificate or not self._ca_private_key:
            raise ValueError("CA certificate not initialized")

        # Generate private key
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        # SPIFFE identity
        spiffe_id = f"spiffe://{self.trust_domain}/ns/{namespace}/sa/{service_account}"

        # Generate certificate
        subject = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, spiffe_id)])

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(self._ca_certificate.subject)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=90))  # 90 days
            .add_extension(
                x509.SubjectAlternativeName(
                    [x509.UniformResourceIdentifier(spiffe_id)]
                ),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_encipherment=True,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    content_commitment=False,
                    data_encipherment=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage(
                    [
                        x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
                        x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,
                    ]
                ),
                critical=True,
            )
            .sign(self._ca_private_key, hashes.SHA256())
        )

        # Serialize to PEM format
        cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        # Store certificate
        cert_id = f"{namespace}/{service_account}"
        self._certificates[cert_id] = {
            "certificate": cert_pem,
            "private_key": key_pem,
            "spiffe_id": spiffe_id,
            "issued_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=90),
        }

        return cert_pem, key_pem

    def get_certificate(
        self, service_account: str, namespace: str
    ) -> Optional[Dict[str, Any]]:
        """Get certificate for service."""
        cert_id = f"{namespace}/{service_account}"
        return self._certificates.get(cert_id)

    def revoke_certificate(self, service_account: str, namespace: str) -> None:
        """Revoke certificate."""
        cert_id = f"{namespace}/{service_account}"
        if cert_id in self._certificates:
            del self._certificates[cert_id]

    def list_certificates(self) -> List[Dict[str, Any]]:
        """List all certificates."""
        return list(self._certificates.values())


class JWTPolicy:
    """JWT policy management."""

    def __init__(
        self, private_key: str = None, algorithm: JWTAlgorithm = JWTAlgorithm.RS256
    ):
        self.algorithm = algorithm
        self.private_key = private_key
        self._public_keys: Dict[str, str] = {}

    def generate_token(
        self,
        payload: Dict[str, Any],
        issuer: str,
        audience: str,
        expires_in: timedelta = timedelta(hours=1),
    ) -> str:
        """Generate JWT token."""
        now = datetime.utcnow()

        claims = {
            "iss": issuer,
            "aud": audience,
            "iat": int(now.timestamp()),
            "exp": int((now + expires_in).timestamp()),
            "jti": str(uuid.uuid4()),
        }
        claims.update(payload)

        return jwt.encode(claims, self.private_key, algorithm=self.algorithm.value)

    def validate_token(
        self, token: str, public_key: str, issuer: str = None, audience: str = None
    ) -> Dict[str, Any]:
        """Validate JWT token."""
        try:
            payload = jwt.decode(
                token,
                public_key,
                algorithms=[self.algorithm.value],
                issuer=issuer,
                audience=audience,
            )
            return payload
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid JWT token: {e}")

    def add_public_key(self, key_id: str, public_key: str) -> None:
        """Add public key for validation."""
        self._public_keys[key_id] = public_key

    def get_jwks(self) -> Dict[str, Any]:
        """Get JSON Web Key Set."""
        keys = []
        for key_id, public_key in self._public_keys.items():
            # This is a simplified JWKS - in production, you'd properly format the key
            keys.append(
                {
                    "kid": key_id,
                    "kty": "RSA",
                    "use": "sig",
                    "alg": self.algorithm.value,
                    "n": base64.urlsafe_b64encode(public_key.encode()).decode(),
                    "e": "AQAB",
                }
            )

        return {"keys": keys}


class SecurityPolicyManager:
    """Comprehensive security policy management."""

    def __init__(self):
        self._authentication_policies: Dict[str, AuthenticationPolicy] = {}
        self._authorization_policies: Dict[str, AuthorizationPolicy] = {}
        self._peer_authentications: Dict[str, PeerAuthentication] = {}
        self._request_authentications: Dict[str, RequestAuthentication] = {}
        self._rbac_policies: Dict[str, RBACPolicy] = {}
        self.certificate_manager = CertificateManager()
        self.jwt_policy = JWTPolicy()

    async def create_authentication_policy(self, policy: AuthenticationPolicy) -> None:
        """Create authentication policy."""
        key = f"{policy.namespace}/{policy.name}"
        self._authentication_policies[key] = policy
        logger.info(f"Created authentication policy: {key}")

    async def create_authorization_policy(self, policy: AuthorizationPolicy) -> None:
        """Create authorization policy."""
        key = f"{policy.namespace}/{policy.name}"
        self._authorization_policies[key] = policy
        logger.info(f"Created authorization policy: {key}")

    async def create_peer_authentication(self, policy: PeerAuthentication) -> None:
        """Create peer authentication policy."""
        key = f"{policy.namespace}/{policy.name}"
        self._peer_authentications[key] = policy
        logger.info(f"Created peer authentication: {key}")

    async def create_request_authentication(
        self, policy: RequestAuthentication
    ) -> None:
        """Create request authentication policy."""
        key = f"{policy.namespace}/{policy.name}"
        self._request_authentications[key] = policy
        logger.info(f"Created request authentication: {key}")

    async def create_rbac_policy(self, policy: RBACPolicy) -> None:
        """Create RBAC policy."""
        key = f"{policy.namespace}/{policy.name}"
        self._rbac_policies[key] = policy
        logger.info(f"Created RBAC policy: {key}")

    async def get_security_configuration(self, namespace: str = None) -> Dict[str, Any]:
        """Get security configuration."""
        config = {
            "authentication_policies": {},
            "authorization_policies": {},
            "peer_authentications": {},
            "request_authentications": {},
            "rbac_policies": {},
        }

        for key, policy in self._authentication_policies.items():
            if namespace is None or policy.namespace == namespace:
                config["authentication_policies"][key] = policy.to_dict()

        for key, policy in self._authorization_policies.items():
            if namespace is None or policy.namespace == namespace:
                config["authorization_policies"][key] = policy.to_dict()

        for key, policy in self._peer_authentications.items():
            if namespace is None or policy.namespace == namespace:
                config["peer_authentications"][key] = policy.to_dict()

        for key, policy in self._request_authentications.items():
            if namespace is None or policy.namespace == namespace:
                config["request_authentications"][key] = policy.to_dict()

        for key, policy in self._rbac_policies.items():
            if namespace is None or policy.namespace == namespace:
                config["rbac_policies"][key] = policy.to_dict()

        return config

    async def issue_workload_certificate(
        self, service_account: str, namespace: str
    ) -> SecurityContext:
        """Issue workload certificate and create security context."""
        cert_pem, key_pem = self.certificate_manager.generate_workload_certificate(
            service_account, namespace
        )

        security_context = SecurityContext(
            service_account=service_account,
            namespace=namespace,
            workload_certificate=cert_pem,
            workload_private_key=key_pem,
        )

        return security_context


# Utility functions


def create_jwt_rule(
    issuer: str, jwks_uri: str = None, audiences: List[str] = None
) -> JWTRule:
    """Create JWT rule."""
    return JWTRule(issuer=issuer, jwks_uri=jwks_uri, audiences=audiences or [])


def create_rbac_rule() -> RBACRule:
    """Create RBAC rule."""
    return RBACRule()


def create_tls_config(mode: TLSMode = TLSMode.ISTIO_MUTUAL) -> TLSConfig:
    """Create TLS configuration."""
    return TLSConfig(mode=mode)


def create_security_context(
    service_account: str, namespace: str = "default"
) -> SecurityContext:
    """Create security context."""
    return SecurityContext(service_account=service_account, namespace=namespace)
