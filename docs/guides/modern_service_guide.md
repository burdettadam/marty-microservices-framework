# Modern Service Creation Guide

This guide explains how to create new services using the unified configuration system.

## Quick Start

1. **Copy the configuration template:**
   ```bash
   cp marty-microservices-framework/templates/service_config_template.yaml config/services/your_service.yaml
   ```

2. **Copy the service template:**
   ```bash
   cp marty-microservices-framework/templates/modern_service_template.py src/services/your_service/modern_your_service.py
   ```

3. **Customize the templates:**
   - Replace `{{SERVICE_NAME}}` with your service name (snake_case)
   - Replace `{{SERVICE_NAME_UPPER}}` with your service name (UPPER_CASE)
   - Replace `{{SERVICE_NAME_PASCAL}}` with your service name (PascalCase)

## Configuration Template Variables

The configuration template uses these variables that you need to replace:

- `{{SERVICE_NAME}}`: Your service name in snake_case (e.g., `document_signer`)
- `{{SERVICE_NAME_UPPER}}`: Your service name in UPPER_CASE (e.g., `DOCUMENT_SIGNER`)

## Service Template Variables

The service template uses these variables:

- `{{SERVICE_NAME}}`: Your service name in snake_case (e.g., `document_signer`)
- `{{SERVICE_NAME_PASCAL}}`: Your service name in PascalCase (e.g., `DocumentSigner`)

## Configuration Sections

### Required Sections

Every service should have these sections:

#### Database Configuration
```yaml
database:
  your_service:
    host: "${YOUR_SERVICE_DB_HOST:-localhost}"
    port: ${YOUR_SERVICE_DB_PORT:-5432}
    database: "${YOUR_SERVICE_DB_NAME:-marty_your_service}"
    username: "${YOUR_SERVICE_DB_USER:-your_service_user}"
    password: "${YOUR_SERVICE_DB_PASSWORD:-change_me_in_production}"
```

#### Security Configuration
```yaml
security:
  grpc_tls:
    enabled: true
    mtls: true
    # ... TLS settings
  auth:
    required: true
    # ... authentication settings
  authz:
    enabled: true
    # ... authorization settings
```

#### Service Discovery
```yaml
service_discovery:
  hosts:
    your_service: "${YOUR_SERVICE_HOST:-your-service}"
    # ... other services
  ports:
    your_service: ${YOUR_SERVICE_PORT:-8080}
    # ... other services
```

### Optional Sections

Include these sections only if your service needs them:

#### Cryptographic Configuration
For services that need signing/encryption:
```yaml
cryptographic:
  signing:
    algorithm: "rsa2048"
    key_id: "your-service-default"
    # ... signing settings
  vault:
    url: "${VAULT_ADDR:-https://vault.internal:8200}"
    # ... vault settings
```

#### Trust Store Configuration
For services that need to validate certificates:
```yaml
trust_store:
  trust_anchor:
    certificate_store_path: "${CERT_STORE_PATH:-/app/data/trust}"
    # ... trust anchor settings
  pkd:
    service_url: "${PKD_SERVICE_URL:-http://pkd-service:8089}"
    # ... PKD settings
```

## Service Implementation

### Basic Service Structure

```python
from framework.config_factory import create_service_config

class ModernYourService:
    def __init__(self, config_path: str = "config/services/your_service.yaml"):
        # Load unified configuration
        self.config = create_service_config(config_path)

        # Extract configuration sections
        self.db_config = self.config.database.get_config("your_service")
        self.security_config = self.config.security
        self.service_discovery = self.config.service_discovery

        # Optional configurations
        self.crypto_config = getattr(self.config, 'cryptographic', None)
        self.trust_store_config = getattr(self.config, 'trust_store', None)
```

### Configuration Usage Patterns

#### Database Access
```python
async def _init_database(self):
    self.db_pool = await create_pool(
        host=self.db_config.host,
        port=self.db_config.port,
        database=self.db_config.database,
        user=self.db_config.username,
        password=self.db_config.password
    )
```

#### Service Communication
```python
def get_document_signer_endpoint(self):
    host = self.service_discovery.hosts.get("document_signer")
    port = self.service_discovery.ports.get("document_signer")
    return f"{host}:{port}"
```

#### Cryptographic Operations
```python
async def _init_cryptographic(self):
    if self.crypto_config and self.crypto_config.signing:
        self.signing_key = load_key(
            self.crypto_config.signing.key_directory,
            self.crypto_config.signing.key_id
        )
```

#### Trust Store Access
```python
async def _init_trust_store(self):
    if self.trust_store_config and self.trust_store_config.trust_anchor:
        self.trust_store = TrustStore(
            self.trust_store_config.trust_anchor.certificate_store_path
        )
```

## Environment Variables

Each service should use environment variables for configuration values:

### Database Variables
- `{SERVICE}_DB_HOST`: Database host
- `{SERVICE}_DB_PORT`: Database port
- `{SERVICE}_DB_NAME`: Database name
- `{SERVICE}_DB_USER`: Database username
- `{SERVICE}_DB_PASSWORD`: Database password

### Service Variables
- `{SERVICE}_HOST`: Service host name
- `{SERVICE}_PORT`: Service port
- `LOG_LEVEL`: Logging level
- `METRICS_PORT`: Metrics server port

### Security Variables
- `TLS_SERVER_CERT`: TLS server certificate
- `TLS_SERVER_KEY`: TLS server key
- `TLS_CLIENT_CA`: Client CA certificate
- `JWT_SECRET`: JWT signing secret

## Best Practices

### 1. Configuration Validation
Always validate configuration on startup:
```python
def __init__(self, config_path: str):
    self.config = create_service_config(config_path)
    self._validate_config()

def _validate_config(self):
    if not self.config.database:
        raise ValueError("Database configuration is required")
    # ... other validations
```

### 2. Graceful Shutdown
Implement proper shutdown handling:
```python
async def stop(self):
    # Stop background tasks
    await self._stop_background_tasks()

    # Stop servers
    if self.grpc_server:
        await self.grpc_server.stop(grace=30)

    # Close database connections
    if self.db_pool:
        await self.db_pool.close()
```

### 3. Error Handling
Use proper error handling and logging:
```python
async def process_operation(self, request):
    try:
        result = await self._do_operation(request)
        self.logger.info(f"Operation completed: {request.get('id')}")
        return result
    except Exception as e:
        self.logger.error(f"Operation failed: {e}")
        raise
```

### 4. Monitoring Integration
Include monitoring and health checks:
```python
async def _start_metrics_server(self):
    if self.config.monitoring and self.config.monitoring.enabled:
        from prometheus_client import start_http_server
        start_http_server(self.config.monitoring.metrics_port)
```

## Testing

Create tests that use the same configuration system:

```python
import pytest
from your_service.modern_your_service import ModernYourService

@pytest.fixture
async def service():
    service = ModernYourService("tests/fixtures/test_config.yaml")
    await service.start()
    yield service
    await service.stop()

async def test_operation(service):
    result = await service.process_operation({"id": "test"})
    assert result["status"] == "success"
```

## Migration from Legacy

To migrate existing services:

1. **Create modern configuration:** Use the template to create a modern config file
2. **Update service class:** Modify to use `create_service_config()`
3. **Remove legacy imports:** Remove old configuration managers
4. **Update tests:** Use new configuration system in tests
5. **Update deployment:** Use new environment variables

## Examples

See these implemented examples:
- `src/services/document_signer/modern_document_signer.py`
- `src/trust_anchor/modern_trust_anchor.py`
- `config/services/document_signer.yaml`
- `config/services/trust_anchor.yaml`
