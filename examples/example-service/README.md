# Example Service

Generated service demonstrating MMF plugin integration patterns.
This example shows how services work with the MMF plugin architecture.

## Features

- 🚀 FastAPI-based service
- 🔌 Plugin integration ready (follows new plugin strategy)
- 🏥 Health checks and monitoring
- 📝 Structured logging with correlation IDs
- ⚙️ Configuration management
- 🧪 Ready for testing

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the service:**
   ```bash
   python main.py
   ```

3. **Check health:**
   ```bash
   curl http://localhost:8080/health
   ```

4. **View API docs:**
   Open http://localhost:8080/docs

## New Plugin Strategy

This service follows the updated MMF plugin architecture:

### Domain Plugins as Top-Level Packages

Plugins are now organized as domain bundles at the top level:

```
plugins/
├── business-logic-plugin/          # Domain plugin
│   ├── __init__.py
│   ├── plugin.py                   # MMFPlugin implementation
│   ├── services/                   # Business services
│   ├── models/                     # Domain models
│   └── api/                        # API endpoints
├── payment-processing/             # Another domain plugin
└── inventory-management/           # Yet another domain plugin
```

### Plugin Registration

Plugins are registered via entry points in `pyproject.toml`:

```toml
[project.entry-points."mmf.plugins"]
business_logic = "plugins.business_logic_plugin:BusinessLogicPlugin"
payment_processing = "plugins.payment_processing:PaymentPlugin"
```

### Service Integration

Services integrate with plugins through the MMF framework:

1. **Service discovers plugins** via entry point discovery
2. **Plugins expose capabilities** through the MMFPlugin interface
3. **Services consume plugin services** through dependency injection

## Business Logic Implementation

### Add Your Business Logic

1. **Service Logic**: Implement in `app/services/example_service_service.py`
2. **API Endpoints**: Add in `app/api/routes.py`
3. **Plugin Integration**: Create top-level plugin packages under `plugins/`
4. **Configuration**: Update `app/core/config.py`

### Example Implementation

```python
# In app/services/example_service_service.py
async def process_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
    # Your business logic here
    result = await self.perform_calculation(data)
    await self.save_to_database(result)
    return result

# In app/api/routes.py
@router.post("/calculate")
async def calculate(request: CalculationRequest):
    service = get_service_instance()
    result = await service.process_request(request.dict())
    return CalculationResponse(**result)
```

## Plugin Integration

This service demonstrates the new MMF plugin architecture:

### Gateway Plugins vs. Service Plugins

MMF supports two types of plugins:

1. **Service Plugins (MMFPlugin)**: Domain bundles that provide business logic and services
   - Located at top-level: `plugins/<domain-plugin>/`
   - Registered via entry points in `pyproject.toml`
   - Implement `MMFPlugin` interface
   - Provide business services and domain logic

2. **Gateway Plugins**: Middleware-like request/response hooks
   - Located in gateway configuration
   - Handle cross-cutting concerns (auth, logging, etc.)
   - Different from domain service plugins

### Creating a Domain Plugin

1. **Create plugin structure**:
   ```bash
   marty service init production my-business-domain
   ```

2. **Implement plugin class**:
   ```python
   # plugins/my_business_domain/plugin.py
   from marty_msf.framework.plugins.core import MMFPlugin

   class MyBusinessDomainPlugin(MMFPlugin):
       def get_metadata(self):
           return {
               "name": "my-business-domain",
               "version": "1.0.0",
               "description": "Business domain logic"
           }
   ```

3. **Register via entry points**:
   ```toml
   [project.entry-points."mmf.plugins"]
   my_business = "plugins.my_business_domain:MyBusinessDomainPlugin"
   ```

### Plugin Development Best Practices

1. **One domain per plugin**: Each plugin represents a business domain
2. **Entry point registration**: Always register plugins via pyproject.toml
3. **Top-level organization**: Place plugins under top-level `plugins/` directory
4. **Avoid embedded plugins**: Don't embed plugins inside individual services

## Configuration

Environment variables can be set in `.env` file:

```bash
SERVICE_NAME=example-service
DEBUG=false
PLUGIN_ENABLED=true
DATABASE_URL=sqlite:///./test.db
```

## Testing

Create tests in the `tests/` directory:

```bash
# Run tests (when implemented)
pytest tests/
```

## Deployment

The service is ready for containerization:

```dockerfile
FROM python:3.11-slim
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
CMD ["python", "main.py"]
```

## Development

1. **Add Database Models**: Create in `app/models/`
2. **Add Business Rules**: Implement in service classes
3. **Add External Integrations**: Create client classes
4. **Add Tests**: Write unit and integration tests
5. **Add Documentation**: Update this README

## API Endpoints

- `GET /` - Service information
- `GET /health` - Health check
- `GET /api/v1/` - Plugin info
- `POST /api/v1/process` - Process business request
- `GET /api/v1/data` - Get business data

## Monitoring

- Logs: `example_service_service.log`
- Audit: `example_service_service_audit.log`
- Health: `/health` endpoint
- Metrics: Ready for Prometheus integration

## Next Steps

1. ✅ Service generated and ready to run
2. 🔧 Implement your business logic
3. 🧪 Add comprehensive tests
4. 📚 Update documentation
5. 🚀 Deploy to your environment

Happy coding! 🎉
