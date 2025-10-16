# Petstore Domain API Documentation and Contract Testing Integration

This directory demonstrates the complete integration of the Marty Framework's unified API documentation and contract testing capabilities within the petstore_domain plugin.

## Overview

The petstore domain plugin now serves as a comprehensive example of how to implement:

1. **Enhanced API Documentation** - Rich OpenAPI specifications with detailed metadata
2. **Contract Testing** - Consumer-driven contract testing examples
3. **Version Management** - API versioning and deprecation strategies
4. **Real-world Integration** - Practical examples using existing microservices

## File Structure

```
plugins/petstore_domain/
├── docs_config.py              # Documentation configuration and generation
├── contracts_config.py         # Contract testing examples and management
├── dev/demo_api_features.sh        # Demonstration script for all features
└── app/api/
    └── enhanced_api_routes.py   # FastAPI routes with comprehensive documentation
```

## Key Features Demonstrated

### 1. Enhanced API Documentation (`docs_config.py`)

- **Service Metadata**: Comprehensive service descriptions and version management
- **Multi-version Support**: V1 (legacy) and V2 (current) API documentation
- **Rich OpenAPI Generation**: Detailed schemas, examples, and response descriptions
- **Integration Points**: Shows how to configure documentation for existing services

```python
# Example usage
from examples.demos.petstore_domain.docs_config import PetstoreDocumentationConfig

docs_config = PetstoreDocumentationConfig()
openapi_spec = await docs_config.generate_openapi_spec()
```

### 2. Contract Testing (`contracts_config.py`)

- **Multiple Consumer Types**: Web frontend, mobile app, internal services, external integrations
- **Contract Generation**: Automated contract creation based on service capabilities
- **Version Compatibility**: Cross-version contract testing examples
- **Real-world Scenarios**: Practical contract examples with actual API endpoints

```python
# Example usage
from examples.demos.petstore_domain.contracts_config import PetstoreContractManager

contract_manager = PetstoreContractManager()
frontend_contract = await contract_manager.create_frontend_contract()
```

### 3. Enhanced API Routes (`enhanced_api_routes.py`)

- **Rich OpenAPI Metadata**: Comprehensive endpoint documentation
- **Response Examples**: Interactive documentation with real examples
- **Error Handling**: Documented error responses with consistent formatting
- **Versioning**: Demonstration of deprecated and current API versions
- **Modern Type Annotations**: Python 3.10+ type syntax

## Quick Start

### 1. Run the Demo Script

The demonstration script shows all features in action:

```bash
chmod +x examples/demos/petstore_domain/dev/demo_api_features.sh

# From project root:
./examples/demos/petstore_domain/dev/demo_api_features.sh
```

### 2. Generate API Documentation

```bash
# Generate OpenAPI documentation for petstore service
marty api docs generate --service petstore --version v2 --output docs/

# Generate unified documentation across all services
marty api docs generate-all --format html --output docs/api/
```

### 3. Run Contract Tests

```bash
# Run all contract tests
marty api contracts run --service petstore

# Run specific contract type
marty api contracts run --service petstore --consumer-type frontend

# Validate contracts against running service
marty api contracts validate --service petstore --endpoint http://localhost:8000
```

### 4. Version Management

```bash
# List all API versions
marty api versions list --service petstore

# Compare versions
marty api versions compare --service petstore --from v1 --to v2

# Generate deprecation report
marty api versions deprecation-report --service petstore
```

## API Endpoints Demonstrated

The enhanced API routes showcase comprehensive documentation patterns:

### Public Endpoints
- `GET /petstore-domain/v2/pets` - List pets with filtering and pagination
- `POST /petstore-domain/v2/pets` - Create new pet with validation
- `GET /petstore-domain/v2/pets/{pet_id}` - Get pet details
- `PUT /petstore-domain/v2/pets/{pet_id}` - Update pet information

### Internal Service Endpoints
- `GET /petstore-domain/v2/pets/{pet_id}/availability` - Check availability
- `POST /petstore-domain/v2/pets/{pet_id}/reserve` - Reserve pet for order

### Legacy Endpoints (Deprecated)
- `GET /api/v1/pets` - Legacy endpoint with deprecation warnings

## Key Implementation Patterns

### 1. Comprehensive Response Models

```python
class PetResponse(BaseModel):
    """Standard pet response wrapper."""
    success: bool = Field(default=True, description="Operation success status")
    correlation_id: str = Field(..., description="Request correlation ID")
    timestamp: str = Field(..., description="Response timestamp")
    data: Pet = Field(..., description="Pet data")
```

### 2. Rich OpenAPI Metadata

```python
@router.get(
    "/pets",
    response_model=PetsListResponse,
    summary="List all pets",
    description="Detailed endpoint description with features and business rules",
    response_description="Paginated list of pets with metadata",
    responses={
        200: {"description": "Success", "content": {"application/json": {"example": {...}}}},
        400: {"description": "Bad request", "model": ErrorResponse}
    },
    tags=["pets"],
    operation_id="listPets"
)
```

### 3. Modern Type Annotations

```python
# Using Python 3.10+ union syntax
species: Annotated[str | None, Query(description="Filter by species")] = None
updates: dict[str, Any]
```

### 4. Contract Testing Integration

```python
# Contract creation with realistic scenarios
async def create_frontend_contract(self) -> dict:
    """Create contract for web frontend consumers."""
    return {
        "consumer": {"name": "petstore-web-frontend"},
        "provider": {"name": "petstore-service"},
        "interactions": [
            # Detailed interaction specifications
        ]
    }
```

## Integration with Framework

This petstore domain integration demonstrates how the new API documentation and contract testing features work with:

- **Existing FastAPI Services**: Enhanced route documentation
- **Framework CLI**: Complete CLI integration for docs and contracts
- **Plugin Architecture**: Plugin-specific configuration and customization
- **Testing Infrastructure**: Integration with existing test frameworks
- **Service Discovery**: Automatic service detection and documentation

## Best Practices Demonstrated

1. **Documentation as Code**: Documentation configuration lives with the service code
2. **Version-aware Design**: Clear migration paths and deprecation strategies
3. **Consumer-driven Contracts**: Contracts defined from consumer perspective
4. **Comprehensive Examples**: Real-world scenarios with complete examples
5. **Error Handling**: Consistent error response patterns across all endpoints
6. **Type Safety**: Modern Python type annotations for better developer experience

## Next Steps

To integrate these patterns into your own services:

1. **Copy Configuration Patterns**: Use `docs_config.py` as a template for your service documentation
2. **Enhance Route Documentation**: Apply the patterns from `enhanced_api_routes.py` to your FastAPI routes
3. **Create Service Contracts**: Use `contracts_config.py` as a reference for your contract testing
4. **Use Framework CLI**: Leverage the `marty api` commands for documentation generation and contract testing

This integration serves as both a working example and a comprehensive reference for implementing unified API documentation and contract testing in your microservices.
