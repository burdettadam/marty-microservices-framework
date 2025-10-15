# Enhanced Security Architecture

## Overview

The Marty Microservices Framework has been enhanced with enterprise-grade security features, including HashiCorp Vault integration for secret management and policy-based authorization using Open Policy Agent (OPA), Oso, and builtin engines. This document outlines the security architecture decisions, infrastructure requirements, and implementation details.

## Security Architecture Principles

### 1. Zero Trust Security Model
- **Principle**: Never trust, always verify
- **Implementation**: Every request is authenticated and authorized
- **Components**: mTLS, JWT verification, certificate-based authentication
- **Benefits**: Reduced attack surface, improved compliance

### 2. Defense in Depth
- **Principle**: Multiple layers of security controls
- **Implementation**: API gateway, service mesh, application-level security
- **Components**: Authentication, authorization, encryption, audit logging
- **Benefits**: Redundant protection, graceful degradation

### 3. Secret Zero
- **Principle**: No hardcoded secrets in code or configuration
- **Implementation**: Dynamic secret retrieval from secure stores
- **Components**: HashiCorp Vault, Kubernetes secrets, encrypted storage
- **Benefits**: Reduced secret sprawl, automatic rotation

### 4. Policy as Code
- **Principle**: Authorization policies defined as code
- **Implementation**: Version-controlled policy definitions
- **Components**: OPA Rego policies, Oso Polar policies, JSON rules
- **Benefits**: Auditability, consistency, rapid deployment

## Architecture Components

### 1. Secret Management Layer

#### HashiCorp Vault Integration
```python
# Core component: VaultClient
from marty_msf.security.secrets import VaultClient, VaultConfig

vault_client = VaultClient(VaultConfig(
    url="https://vault.company.com",
    auth_method=VaultAuthMethod.KUBERNETES,
    role="marty-msf-service"
))
```

**Capabilities:**
- Multiple authentication methods (Token, Kubernetes, AWS IAM, AppRole, UserPass)
- Secret engines (KV v2, Database, PKI, Transit)
- Certificate generation and management
- Encryption as a service
- Automatic secret rotation

**Infrastructure Requirements:**
- HashiCorp Vault cluster (minimum 3 nodes for HA)
- Vault Agent for local caching (optional)
- Network connectivity to Vault API
- Service accounts with appropriate roles

#### Multi-Backend Secret Manager
```python
# Enhanced secret manager with fallback
secret_manager = SecretManager(
    service_name="payment-service",
    vault_client=vault_client,
    backends=[
        SecretBackend.VAULT,      # Primary
        SecretBackend.KUBERNETES, # Fallback
        SecretBackend.ENVIRONMENT # Last resort
    ]
)
```

**Features:**
- Backend preference ordering
- Automatic failover
- Secret metadata tracking
- Health monitoring
- Rotation management

### 2. Authorization Layer

#### Policy Engine Architecture
```python
# Multi-engine policy manager
policy_manager = PolicyManager(
    primary_engine=PolicyEngineEnum.OPA,
    fallback_engines=[PolicyEngineEnum.OSO, PolicyEngineEnum.BUILTIN]
)
```

**Engine Capabilities:**

| Engine | Use Case | Strengths | Language |
|--------|----------|-----------|----------|
| OPA | Complex ABAC policies | Rego language, external data | Rego |
| Oso | Fine-grained permissions | Python integration, flexible | Polar |
| Builtin | Simple RBAC | Fast evaluation, JSON config | JSON |

**Policy Examples:**

**RBAC (Role-Based Access Control):**
```json
{
  "rules": [
    {
      "resource": "/api/v1/users/*",
      "action": "GET",
      "principal": {"roles": ["admin", "user"]},
      "effect": "allow"
    }
  ]
}
```

**ABAC (Attribute-Based Access Control):**
```rego
allow if {
    input.action == "POST"
    input.resource == "/api/v1/transactions"
    "finance_manager" in input.principal.roles
    input.environment.transaction_amount > 10000
    business_hours
}
```

### 3. Gateway Security Integration

#### Enhanced Security Middleware
```python
# FastAPI integration
middleware = await create_enhanced_security_middleware(
    secret_manager=secret_manager,
    policy_manager=policy_manager,
    require_mtls=True,
    audit_enabled=True
)
```

**Security Pipeline:**
1. **Request Authentication**
   - mTLS certificate validation
   - JWT token verification
   - API key validation

2. **Authorization Evaluation**
   - Policy engine consultation
   - Context-aware decisions
   - Audit logging

3. **Secret Injection**
   - Automatic secret resolution
   - Context-based secret access
   - Secure secret transmission

### 4. gRPC Security Interceptors

#### Service-to-Service Security
```python
# gRPC server with security
server = grpc.aio.server(interceptors=[
    create_authentication_interceptor(secret_manager),
    create_authorization_interceptor(policy_manager),
    create_secret_injection_interceptor(secret_manager)
])
```

**Interceptor Functions:**
- **Authentication**: Certificate and token validation
- **Authorization**: Policy-based access control
- **Secret Injection**: Automatic secret provisioning
- **Audit Logging**: Comprehensive request tracking

## Infrastructure Requirements

### 1. HashiCorp Vault Deployment

#### Production Deployment
```yaml
# Minimum requirements
Resources:
  - CPU: 2 cores per node
  - Memory: 4GB per node
  - Storage: 100GB SSD per node
  - Network: High availability networking

High Availability:
  - 3+ Vault nodes
  - Raft or Consul storage backend
  - Load balancer with health checks
  - Auto-unseal with cloud KMS
```

#### Development Setup
```bash
# Docker Compose for development
docker-compose -f examples/security/vault-configs/docker-compose.yaml up -d
```

### 2. Policy Engine Infrastructure

#### Open Policy Agent (OPA)
```yaml
# Kubernetes deployment
Resources:
  - CPU: 100m-500m
  - Memory: 128Mi-512Mi
  - Replicas: 2+ for HA

Configuration:
  - Bundle server for policy distribution
  - Decision logging
  - Status reporting
```

#### Oso Integration
```python
# In-process policy evaluation
# No additional infrastructure required
# Policies loaded from configuration
```

### 3. Certificate Management

#### PKI Infrastructure
```
Certificate Hierarchy:
├── Root CA (Vault)
├── Intermediate CA (Per Environment)
└── Service Certificates (Short-lived, 24h TTL)

Rotation Strategy:
- Automatic certificate renewal
- Graceful service restart
- Certificate monitoring and alerting
```

### 4. Networking and Security

#### Network Security
```yaml
Network Policies:
  - Vault access restricted to authenticated services
  - mTLS for all service-to-service communication
  - Network segmentation by environment
  - Firewall rules for external access

Load Balancing:
  - TLS termination at load balancer
  - Backend certificate validation
  - Health check endpoints
```

## Security Patterns and Best Practices

### 1. Authentication Patterns

#### Service-to-Service Authentication
```python
# mTLS with short-lived certificates
@app.middleware("https")
async def verify_client_cert(request: Request, call_next):
    cert = request.client.cert
    if not verify_certificate(cert):
        raise HTTPException(401, "Invalid certificate")
    return await call_next(request)
```

#### User Authentication
```python
# JWT with Vault-managed signing keys
async def verify_jwt_token(token: str) -> dict:
    signing_key = await secret_manager.get_secret("jwt/signing_key")
    return jwt.decode(token, signing_key, algorithms=["HS256"])
```

### 2. Authorization Patterns

#### Context-Aware Authorization
```python
# Request context evaluation
auth_request = AuthorizationRequest(
    principal={"user_id": user.id, "roles": user.roles},
    action=request.method,
    resource=request.url.path,
    environment={
        "source_ip": request.client.host,
        "time": datetime.now(),
        "user_agent": request.headers.get("user-agent")
    }
)
```

#### Policy Composition
```python
# Multiple policy evaluation
policies = ["rbac_users", "abac_financial", "compliance_policy"]
result = await policy_manager.evaluate(auth_request, policies)
```

### 3. Secret Management Patterns

#### Dynamic Secret Retrieval
```python
# Secrets retrieved at runtime
@app.dependency
async def get_database_credentials():
    return await secret_manager.get_secret("database/credentials")
```

#### Secret Rotation
```python
# Automatic rotation monitoring
@background_task
async def monitor_secret_rotation():
    secrets_to_rotate = secret_manager.get_secrets_needing_rotation()
    for secret_key in secrets_to_rotate:
        await secret_manager.rotate_secret(secret_key)
```

## Compliance and Audit

### 1. Audit Logging
```python
# Comprehensive audit trail
audit_event = {
    "timestamp": datetime.utcnow(),
    "service": "payment-service",
    "user_id": principal.user_id,
    "action": "create_transaction",
    "resource": "/api/v1/transactions",
    "decision": "allow",
    "policy_engine": "opa",
    "source_ip": request.client.host
}
```

### 2. Compliance Controls
- **PCI DSS**: Secret encryption, access logging, network segmentation
- **SOX**: Policy versioning, approval workflows, audit trails
- **GDPR**: Data access controls, encryption at rest and in transit
- **HIPAA**: Authentication requirements, audit logging, data encryption

## Monitoring and Observability

### 1. Security Metrics
```python
# Key security metrics
metrics = {
    "authentication_failures": Counter(),
    "authorization_denials": Counter(),
    "secret_rotation_events": Counter(),
    "certificate_expiration_warnings": Counter(),
    "policy_evaluation_latency": Histogram()
}
```

### 2. Health Checks
```python
# Security health monitoring
@app.get("/health/security")
async def security_health():
    return {
        "vault_connected": await vault_client.health_check(),
        "policy_engines_active": await policy_manager.health_check(),
        "certificates_valid": await check_certificate_validity(),
        "secret_rotation_current": check_rotation_status()
    }
```

## Migration and Deployment

### 1. Migration Strategy
```
Phase 1: Infrastructure Setup
- Deploy Vault cluster
- Configure authentication methods
- Setup initial policies

Phase 2: Secret Migration
- Migrate secrets from existing stores
- Update service configurations
- Test secret retrieval

Phase 3: Policy Implementation
- Deploy authorization policies
- Enable policy enforcement
- Monitor and adjust

Phase 4: Full Security Enablement
- Enable mTLS everywhere
- Activate audit logging
- Performance optimization
```

### 2. Rollback Plan
```
Emergency Procedures:
1. Disable policy enforcement
2. Fallback to environment secrets
3. Use bypass authentication
4. Restore from backups
5. Gradual re-enablement
```

## Performance Considerations

### 1. Latency Optimization
- **Secret Caching**: Local cache with TTL
- **Policy Caching**: In-memory policy evaluation
- **Connection Pooling**: Reuse Vault connections
- **Async Operations**: Non-blocking secret retrieval

### 2. Scalability
- **Horizontal Scaling**: Multiple policy engine instances
- **Load Distribution**: Round-robin policy evaluation
- **Resource Limits**: CPU and memory constraints
- **Circuit Breakers**: Fallback mechanisms

## Troubleshooting Guide

### 1. Common Issues

#### Vault Authentication Failures
```bash
# Check Vault status
vault status

# Verify authentication
vault auth -method=kubernetes role=marty-msf

# Check policies
vault policy read marty-msf-policy
```

#### Policy Evaluation Errors
```bash
# Test policy evaluation
curl -X POST http://opa:8181/v1/data/authz/allow \
  -d '{"input": {"principal": {...}, "action": "GET", "resource": "/api/users"}}'

# Check policy syntax
opa fmt --diff policy.rego
```

#### Certificate Issues
```bash
# Check certificate validity
openssl x509 -in cert.pem -text -noout

# Verify certificate chain
openssl verify -CAfile ca.pem cert.pem
```

### 2. Debugging Tools

#### Security Audit Script
```python
# Comprehensive security audit
async def security_audit():
    results = {
        "vault_health": await vault_client.health_check(),
        "expired_secrets": get_expired_secrets(),
        "policy_conflicts": check_policy_conflicts(),
        "certificate_expiry": check_certificate_expiry()
    }
    return results
```

## Future Enhancements

### 1. Planned Features
- **Dynamic Policy Updates**: Real-time policy reloading
- **Advanced Threat Detection**: ML-based anomaly detection
- **Secret Scanning**: Automated secret detection in code
- **Compliance Automation**: Automated compliance reporting

### 2. Integration Roadmap
- **Service Mesh Integration**: Istio/Linkerd policy integration
- **Cloud Provider Integration**: AWS/Azure/GCP native services
- **Third-Party Tools**: Integration with security scanners
- **API Security**: Rate limiting, DDoS protection

## Conclusion

The enhanced security architecture provides enterprise-grade security capabilities while maintaining the simplicity and flexibility of the Marty Microservices Framework. The multi-layered approach ensures robust protection against various threat vectors while supporting compliance requirements and operational excellence.

Key benefits:
- **Reduced Security Risk**: Comprehensive protection across all layers
- **Improved Compliance**: Built-in audit and control capabilities
- **Operational Efficiency**: Automated secret management and policy enforcement
- **Developer Productivity**: Simple APIs and graceful degradation
- **Future-Proof Design**: Extensible architecture for emerging threats
