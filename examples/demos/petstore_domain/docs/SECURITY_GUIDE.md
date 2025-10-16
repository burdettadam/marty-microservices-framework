# PetStore Comprehensive Configuration Guide

## Overview
This guide provides complete configuration instructions for the enhanced security features integrated into the PetStore domain plugin.

## Security Components

### 1. HashiCorp Vault Integration
Configure Vault for secret management:

```yaml
# config/plugins/marty.yaml
vault:
  enabled: true
  url: "https://vault.example.com:8200"
  auth_method: "token"  # Options: token, kubernetes, aws_iam
  mount_path: "secret/"

  # Token authentication
  token: "${VAULT_TOKEN}"

  # Kubernetes authentication
  kubernetes:
    role: "petstore-service"
    service_account_token_path: "/var/run/secrets/kubernetes.io/serviceaccount/token"

  # AWS IAM authentication
  aws_iam:
    role: "petstore-vault-role"
    region: "us-west-2"
```

### 2. Policy Engines

#### Open Policy Agent (OPA)
```yaml
opa:
  enabled: true
  server_url: "http://opa:8181"
  policy_package: "petstore.authz"
  timeout: 5
```

#### Oso Policy Engine
```yaml
oso:
  enabled: true
  policy_file: "config/policies/authorization.polar"
  reload_on_change: true
```

### 3. mTLS Configuration
```yaml
mtls:
  enabled: true
  ca_cert_path: "/etc/ssl/certs/ca.pem"
  client_cert_path: "/etc/ssl/certs/client.pem"
  client_key_path: "/etc/ssl/private/client.key"
  verify_client_cert: true
  allowed_dns_names:
    - "*.petstore.local"
    - "*.internal.example.com"
```

### 4. JWT Authentication
```yaml
jwt:
  secret_key: "${JWT_SECRET_KEY}"
  algorithm: "HS256"
  access_token_expire_minutes: 30
  refresh_token_expire_days: 30
  issuer: "petstore-service"
  audience: "petstore-api"
```

### 5. API Keys
```yaml
api_keys:
  enabled: true
  header_name: "X-API-Key"
  query_param_name: "api_key"
  # Keys stored in Vault under api_keys/ path
```

## Environment Variables

### Required Variables
```bash
# Basic Configuration
ENVIRONMENT=development
LOG_LEVEL=INFO

# Security
JWT_SECRET_KEY=your-super-secret-jwt-key-here
API_SECRET_KEY=your-api-secret-key-here

# Vault Configuration
VAULT_ENABLED=true
VAULT_URL=https://vault.example.com:8200
VAULT_TOKEN=your-vault-token-here
VAULT_AUTH_METHOD=token
VAULT_MOUNT_PATH=secret/

# Policy Engines
OPA_ENABLED=false
OPA_SERVER_URL=http://opa:8181
OPA_POLICY_PACKAGE=petstore.authz

OSO_ENABLED=true
OSO_POLICY_FILE=config/policies/authorization.polar

# mTLS
MTLS_ENABLED=false
MTLS_CA_CERT_PATH=/etc/ssl/certs/ca.pem
MTLS_CLIENT_CERT_PATH=/etc/ssl/certs/client.pem
MTLS_CLIENT_KEY_PATH=/etc/ssl/private/client.key
MTLS_VERIFY_CLIENT_CERT=true

# Audit
AUDIT_ENABLED=true
AUDIT_LOG_LEVEL=INFO
AUDIT_LOG_FILE=logs/security_audit.log
AUDIT_LOG_MAX_SIZE=10485760
AUDIT_LOG_BACKUP_COUNT=5
```

## Policy Configuration

### RBAC Policies (JSON Format)
The system supports role-based access control through JSON policies:

```json
{
  "version": "1.0",
  "name": "petstore_rbac",
  "description": "Role-based access control for PetStore domain",
  "rules": [
    {
      "id": "public_pets_read",
      "effect": "allow",
      "principals": ["*"],
      "actions": ["GET"],
      "resources": ["/api/v1/pets/*/public"],
      "conditions": {}
    },
    {
      "id": "authenticated_pets_access",
      "effect": "allow",
      "principals": ["role:user", "role:admin"],
      "actions": ["GET", "POST"],
      "resources": ["/api/v1/pets", "/api/v1/pets/*"],
      "conditions": {}
    }
  ]
}
```

### Oso Polar Policies
Define authorization logic using Oso's Polar language:

```polar
# Basic pet access rules
allow(actor, "GET", resource) if {
    resource.type == "pet" and
    resource.visibility == "public"
}

allow(actor, "GET", resource) if {
    resource.type == "pet" and
    actor.has_role("user")
}
```

## Deployment Instructions

### 1. Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export ENVIRONMENT=development
export JWT_SECRET_KEY=dev-secret-key
export VAULT_ENABLED=false
export OSO_ENABLED=true

# Run the service
python main.py
```

### 2. Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: petstore-service
spec:
  template:
    spec:
      containers:
      - name: petstore
        image: petstore:latest
        env:
        - name: VAULT_TOKEN
          valueFrom:
            secretKeyRef:
              name: vault-secrets
              key: token
        - name: JWT_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: jwt-secrets
              key: secret-key
        volumeMounts:
        - name: tls-certs
          mountPath: /etc/ssl/certs
          readOnly: true
      volumes:
      - name: tls-certs
        secret:
          secretName: petstore-tls
```

### 3. Docker Compose
```yaml
version: '3.8'
services:
  petstore:
    build: .
    environment:
      - ENVIRONMENT=production
      - VAULT_ENABLED=true
      - VAULT_URL=https://vault:8200
    volumes:
      - ./config:/app/config
      - ./certs:/etc/ssl/certs
    depends_on:
      - vault
      - opa
```

## Security Features

### Authentication Methods
1. **JWT Tokens**: Bearer token authentication with configurable expiration
2. **API Keys**: Header or query parameter based authentication
3. **mTLS**: Mutual TLS certificate authentication for service-to-service communication

### Authorization Engines
1. **Built-in RBAC**: JSON-based role and policy definitions
2. **Open Policy Agent (OPA)**: External policy server for complex authorization
3. **Oso**: Embedded policy engine with Polar language support

### Secret Management
- **HashiCorp Vault**: Centralized secret storage and rotation
- **Multiple Auth Methods**: Token, Kubernetes, AWS IAM
- **Automatic Secret Refresh**: Background token renewal

### Audit Logging
- **Comprehensive Logging**: All security events logged with context
- **Structured Format**: JSON formatted logs for easy parsing
- **Configurable Rotation**: File size and count based rotation

## Testing

### Unit Tests
```bash
# Run security component tests
pytest tests/unit/security/

# Run integration tests
pytest tests/integration/security/
```

### Security Validation
```bash
# Test authentication
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://localhost:8000/api/v1/pets

# Test API key authentication
curl -H "X-API-Key: YOUR_API_KEY" \
     http://localhost:8000/api/v1/pets

# Test admin endpoint (requires admin role)
curl -H "Authorization: Bearer ADMIN_JWT_TOKEN" \
     http://localhost:8000/api/v1/admin/stats
```

## Troubleshooting

### Common Issues

1. **JWT Token Validation Fails**
   - Check JWT_SECRET_KEY environment variable
   - Verify token hasn't expired
   - Ensure correct algorithm (HS256)

2. **Vault Connection Issues**
   - Verify VAULT_URL is accessible
   - Check VAULT_TOKEN is valid
   - Ensure proper network connectivity

3. **Policy Engine Errors**
   - Validate policy syntax
   - Check policy file paths
   - Verify OPA server connectivity

4. **mTLS Certificate Issues**
   - Verify certificate paths
   - Check certificate validity
   - Ensure proper CA chain

### Debug Mode
Enable debug logging for detailed security information:

```bash
export LOG_LEVEL=DEBUG
export AUDIT_LOG_LEVEL=DEBUG
```

## Production Considerations

### Security Hardening
1. Use strong, unique secret keys
2. Enable mTLS for service-to-service communication
3. Implement proper certificate rotation
4. Use Vault for all sensitive configuration
5. Enable comprehensive audit logging

### Performance Optimization
1. Cache policy decisions when possible
2. Use connection pooling for external services
3. Implement circuit breakers for resilience
4. Monitor security middleware performance

### Monitoring
1. Set up alerts for authentication failures
2. Monitor policy decision latency
3. Track secret rotation success/failure
4. Monitor audit log ingestion

This completes the comprehensive security integration for the PetStore domain plugin.
