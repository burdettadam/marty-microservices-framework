# Example Service Service

Generated service with example_business plugin integration.
Ready for business logic implementation.

## Features

- 🚀 FastAPI-based service
- 🔌 Plugin integration with example_business
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

## Business Logic Implementation

### Add Your Business Logic

1. **Service Logic**: Implement in `app/services/example_service_service.py`
2. **API Endpoints**: Add in `app/api/routes.py`
3. **Plugin Logic**: Implement in `plugins/example_business/example_business_plugin.py`
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

The service integrates with the `example_business` plugin:

- **Plugin Location**: `plugins/example_business/`
- **Business Logic**: `example_business_plugin.py`
- **Configuration**: `plugin.yaml`

### Plugin Development

1. Implement business logic in `ExampleBusinessBusinessLogic`
2. Add methods for your specific business operations
3. Update configuration schema as needed

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
