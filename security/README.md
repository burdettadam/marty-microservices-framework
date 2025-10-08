# Security Framework for Microservices

A comprehensive security framework providing enterprise-grade security capabilities for microservices applications.

## 🛡️ Overview

This security framework provides a complete suite of security tools and middleware designed specifically for microservices architectures:

- **Authentication & Authorization**: JWT-based authentication with RBAC support
- **Rate Limiting**: Advanced rate limiting with Redis-backed sliding window algorithm
- **Security Headers**: Comprehensive security headers with CSP, HSTS, and more
- **Security Scanning**: Automated vulnerability scanning and security auditing
- **Policy Enforcement**: RBAC policies and Kubernetes security policies
- **Secret Management**: Secure configuration and secret handling patterns

## 🚀 Quick Start

### 1. Basic Security Setup

```python
from fastapi import FastAPI
from security import (
    AuthenticationMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    create_security_headers_config
)

app = FastAPI()

# Add security middleware (order matters!)
app.add_middleware(
    SecurityHeadersMiddleware,
    config=create_security_headers_config(environment="production")
)

app.add_middleware(
    RateLimitMiddleware,
    redis_url="redis://localhost:6379",
    default_requests_per_hour=1000
)

app.add_middleware(
    AuthenticationMiddleware,
    jwt_secret_key="your-secret-key",
    excluded_paths=["/health", "/docs"]
)
```

### 2. Protecting Endpoints with Roles

```python
from fastapi import Depends
from security import require_roles, get_current_user_dependency

# Protect endpoint with role requirement
@app.post("/admin/users")
@require_roles(["admin", "user_manager"])
async def create_user():
    return {"message": "User created"}

# Get current user in endpoint
@app.get("/profile")
async def get_profile(user=Depends(get_current_user_dependency(security_config))):
    return {"user_id": user["user_id"], "roles": user["roles"]}
```

### 3. Custom Rate Limiting

```python
from security import rate_limit

@app.post("/upload")
@rate_limit(requests=5, window_seconds=300)  # 5 uploads per 5 minutes
async def upload_file():
    return {"message": "File uploaded"}
```

## 📦 Components

### Authentication Middleware

- JWT token validation and generation
- Role-based access control (RBAC)
- Session management
- Security audit logging
- Rate limiting per user

```python
from security.middleware.auth_middleware import AuthenticationMiddleware, SecurityConfig

config = SecurityConfig(
    jwt_secret_key="your-secret-key",
    jwt_expiration_hours=24,
    enable_audit_logging=True,
    redis_url="redis://localhost:6379"
)

middleware = AuthenticationMiddleware(app, config)
```

### Rate Limiting Middleware

- Sliding window algorithm
- Per-user, per-IP, and per-endpoint limits
- Redis-backed distributed rate limiting
- Burst limit support
- Configurable rules

```python
from security.middleware.rate_limiting import RateLimitMiddleware, RateLimitConfig, RateLimitRule

config = RateLimitConfig(
    redis_url="redis://localhost:6379",
    default_rule=RateLimitRule(requests=1000, window_seconds=3600),
    per_endpoint_rules={
        "POST:/auth/login": RateLimitRule(requests=5, window_seconds=300)
    }
)

middleware = RateLimitMiddleware(app, config)
```

### Security Headers Middleware

- Content Security Policy (CSP)
- HTTP Strict Transport Security (HSTS)
- X-Frame-Options, X-Content-Type-Options
- CORS configuration
- Permissions Policy

```python
from security.middleware.security_headers import SecurityHeadersMiddleware, SecurityHeadersConfig

config = SecurityHeadersConfig(
    environment="production",
    api_only=True,
    cors_allow_origins=["https://your-frontend.com"]
)

middleware = SecurityHeadersMiddleware(app, config)
```

## 🔧 Security Tools

### Security Scanner

Comprehensive security analysis tool:

```bash
# Run full security audit
./security/scanners/security_scan.sh

# Run specific scans
./security/scanners/security_scan.sh deps        # Dependencies only
./security/scanners/security_scan.sh code        # Code analysis only
./security/scanners/security_scan.sh secrets     # Secrets scanning
./security/scanners/security_scan.sh containers  # Container security
```

### Security Audit Tool

Python-based comprehensive security auditor:

```bash
# Run security audit
python security/tools/security_audit.py

# With custom project root
python security/tools/security_audit.py --project-root /path/to/project

# Verbose output
python security/tools/security_audit.py --verbose
```

## 📋 Security Policies

### RBAC Policies

Role-based access control with comprehensive policy definitions:

```yaml
# security/policies/rbac_policies.yaml
roles:
  admin:
    permissions:
      - "*:*:*"

  developer:
    permissions:
      - "services:*:read"
      - "configs:*:read"
      - "code:*:create"
      - "code:*:update"
```

### Kubernetes Security Policies

Production-ready Kubernetes security configurations:

- Network policies for micro-segmentation
- Pod security standards
- RBAC configurations
- Security contexts and resource limits

```yaml
# Example network policy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

## 🏗️ Architecture

### Security Middleware Stack

```
┌─────────────────────────────────────┐
│           Request                   │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│     Security Headers Middleware    │
│  (CSP, HSTS, CORS, etc.)          │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│     Rate Limiting Middleware       │
│  (Per-user, per-IP, per-endpoint)  │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│   Authentication Middleware        │
│  (JWT validation, RBAC, audit)     │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│         Application                 │
└─────────────────────────────────────┘
```

### Security Features

- **Defense in Depth**: Multiple layers of security controls
- **Zero Trust**: Verify every request and user
- **Principle of Least Privilege**: Minimal required permissions
- **Security by Default**: Secure defaults with opt-out for relaxed policies
- **Audit Everything**: Comprehensive security logging and monitoring

## 🔒 Best Practices

### 1. Middleware Order

Always add middleware in the correct order:

1. Security Headers (first)
2. Rate Limiting
3. Authentication (last)

### 2. Secret Management

```python
import os
from security import SecurityConfig

# Use environment variables for secrets
config = SecurityConfig(
    jwt_secret_key=os.getenv("JWT_SECRET_KEY"),
    redis_url=os.getenv("REDIS_URL")
)
```

### 3. Environment-Specific Configurations

```python
# Production
config = create_security_headers_config(
    environment="production",
    api_only=True,
    allow_origins=["https://your-app.com"]
)

# Development
config = create_security_headers_config(
    environment="development",
    allow_origins=["http://localhost:3000"]
)
```

### 4. Rate Limiting Strategy

```python
# API tier-based rate limiting
rate_limits = {
    "free_tier": RateLimitRule(requests=100, window_seconds=3600),
    "premium_tier": RateLimitRule(requests=1000, window_seconds=3600),
    "enterprise_tier": RateLimitRule(requests=10000, window_seconds=3600)
}
```

## 📊 Monitoring and Alerting

### Security Metrics

The framework automatically exports security metrics:

- Authentication attempts and failures
- Rate limit hits and violations
- Security header compliance
- Policy violations

### Audit Logging

Comprehensive security audit logs:

```json
{
  "timestamp": "2023-10-07T10:30:00Z",
  "event_type": "authentication",
  "user_id": "user123",
  "endpoint": "/api/users",
  "method": "POST",
  "ip_address": "192.168.1.100",
  "success": true
}
```

## 🧪 Testing Security

### Unit Tests

```python
import pytest
from security.middleware.auth_middleware import JWTAuthenticator, SecurityConfig

def test_jwt_validation():
    config = SecurityConfig(jwt_secret_key="test-key")
    auth = JWTAuthenticator(config)

    token = auth.create_access_token("user123", ["user"])
    payload = auth.verify_token(token)

    assert payload["sub"] == "user123"
    assert "user" in payload["roles"]
```

### Integration Tests

```python
from fastapi.testclient import TestClient

def test_protected_endpoint():
    client = TestClient(app)

    # Test without authentication
    response = client.get("/protected")
    assert response.status_code == 401

    # Test with valid token
    headers = {"Authorization": f"Bearer {valid_token}"}
    response = client.get("/protected", headers=headers)
    assert response.status_code == 200
```

## 🚨 Security Scanning

### Automated Scanning

The framework includes automated security scanning that checks for:

- Code vulnerabilities (Bandit, Semgrep)
- Dependency vulnerabilities (Safety, pip-audit)
- Container security issues
- Configuration security problems
- Infrastructure security gaps

### CI/CD Integration

```yaml
# .github/workflows/security.yml
name: Security Scan
on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run Security Scan
        run: |
          ./security/scanners/security_scan.sh
          python security/tools/security_audit.py
```

## 📚 Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [Kubernetes Security Best Practices](https://kubernetes.io/docs/concepts/security/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)

## 🤝 Contributing

1. Follow security best practices in all contributions
2. Add security tests for new features
3. Update security documentation
4. Run security scans before submitting PRs

## 📄 License

This security framework is part of the Marty Microservices Framework and follows the same licensing terms.
