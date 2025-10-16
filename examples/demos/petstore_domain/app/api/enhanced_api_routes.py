"""
Enhanced Petstore API Routes with Documentation and Contract Testing Integration

This module demonstrates how to enhance existing FastAPI routes with comprehensive
API documentation metadata and contract testing integration points.

Features:
- Rich OpenAPI metadata for better documentation
- Response examples for interactive docs
- Version-aware endpoint definitions
- Contract testing integration hooks
- Deprecation warnings and migration guides

Author: Marty Framework Team
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Create enhanced router with comprehensive metadata
router = APIRouter(
    prefix="/petstore-domain/v2",
    tags=["petstore-v2"],
    responses={
        404: {"description": "Resource not found"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"}
    }
)

# Enhanced Pydantic models with documentation
class PetBase(BaseModel):
    """Base pet model with common fields."""
    name: str = Field(..., description="Pet name", example="Buddy")
    species: str = Field(..., description="Pet species", example="dog")
    breed: str | None = Field(default=None, description="Pet breed", example="Golden Retriever")
    age: int = Field(..., ge=0, le=30, description="Pet age in years", example=3)
    price: float = Field(..., gt=0, description="Pet price in USD", example=599.99)

class Pet(PetBase):
    """Complete pet model with ID and status."""
    id: str = Field(..., description="Unique pet identifier", example="pet-001")
    status: str = Field(default="available", description="Pet availability status", example="available")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Last update timestamp")

class PetResponse(BaseModel):
    """Standard pet response wrapper."""
    success: bool = Field(default=True, description="Operation success status")
    correlation_id: str = Field(..., description="Request correlation ID", example="req-123")
    timestamp: str = Field(..., description="Response timestamp", example="2025-10-15T10:00:00Z")
    data: Pet = Field(..., description="Pet data")

class PetsListResponse(BaseModel):
    """Paginated pets list response."""
    success: bool = Field(default=True, description="Operation success status")
    correlation_id: str = Field(..., description="Request correlation ID", example="req-124")
    timestamp: str = Field(..., description="Response timestamp", example="2025-10-15T10:01:00Z")
    data: dict[str, Any] = Field(..., description="Response data with pets and pagination")

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str = Field(..., description="Error message", example="Pet not found")
    error_code: str = Field(..., description="Specific error code", example="PET_NOT_FOUND")
    correlation_id: str = Field(..., description="Request correlation ID", example="req-125")
    timestamp: str = Field(..., description="Error timestamp", example="2025-10-15T10:02:00Z")

# Enhanced endpoints with comprehensive documentation
@router.get(
    "/pets",
    response_model=PetsListResponse,
    summary="List all pets",
    description="""
    Retrieve a paginated list of available pets with optional filtering.

    This endpoint supports:
    - Pagination with configurable page size
    - Filtering by species, breed, and status
    - Sorting by price, age, or name
    - Mobile-optimized responses

    **Rate Limiting**: 100 requests per minute for standard users, 1000 for premium.

    **Caching**: Responses are cached for 5 minutes.
    """,
    response_description="Paginated list of pets with metadata",
    responses={
        200: {
            "description": "Successful response with pets list",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "correlation_id": "req-124",
                        "timestamp": "2025-10-15T10:01:00Z",
                        "data": {
                            "pets": [
                                {
                                    "id": "pet-001",
                                    "name": "Buddy",
                                    "species": "dog",
                                    "breed": "Golden Retriever",
                                    "age": 3,
                                    "status": "available",
                                    "price": 599.99,
                                    "created_at": "2025-10-01T10:00:00Z"
                                }
                            ],
                            "pagination": {
                                "page": 1,
                                "size": 10,
                                "total": 1,
                                "total_pages": 1
                            }
                        }
                    }
                }
            }
        }
    },
    tags=["pets"],
    operation_id="listPets"
)
async def list_pets(
    page: Annotated[int, Query(description="Page number", ge=1, example=1)] = 1,
    size: Annotated[int, Query(description="Page size", ge=1, le=100, example=10)] = 10,
    species: Annotated[str | None, Query(description="Filter by species", example="dog")] = None,
    breed: Annotated[str | None, Query(description="Filter by breed", example="Golden Retriever")] = None,
    status: Annotated[str | None, Query(description="Filter by status", example="available")] = None,
    mobile: Annotated[bool | None, Query(description="Mobile-optimized response")] = False,
    authorization: Annotated[str, Header(description="JWT token", example="Bearer jwt-token")] = None,
    user_agent: Annotated[str | None, Header(alias="User-Agent", description="Client user agent")] = None
):
    """List pets with advanced filtering and pagination."""
    # Implementation would go here
    # For demo purposes, return mock data

    correlation_id = f"req-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    mock_pets = [
        {
            "id": "pet-001",
            "name": "Buddy",
            "species": "dog",
            "breed": "Golden Retriever",
            "age": 3,
            "status": "available",
            "price": 599.99,
            "created_at": "2025-10-01T10:00:00Z"
        }
    ]

    if mobile:
        # Mobile-optimized response
        mock_pets[0]["thumbnail"] = "https://cdn.petstore.com/thumbs/pet-001.jpg"
        pagination = {"page": page, "size": size, "has_more": False}
    else:
        # Standard pagination
        pagination = {"page": page, "size": size, "total": 1, "total_pages": 1}

    return {
        "success": True,
        "correlation_id": correlation_id,
        "timestamp": datetime.now().isoformat(),
        "data": {
            "pets": mock_pets,
            "pagination": pagination
        }
    }

@router.post(
    "/pets",
    response_model=PetResponse,
    status_code=201,
    summary="Create a new pet",
    description="""
    Create a new pet in the system with comprehensive validation.

    **Features**:
    - Automatic ID generation
    - Duplicate name detection
    - Price validation
    - Image upload support (multipart)

    **Business Rules**:
    - Pet names must be unique within the same species
    - Age must be realistic for the species
    - Price must be within market range

    **Events Published**:
    - `pet.created` with pet details
    - `inventory.updated` with stock changes
    """,
    response_description="Created pet with generated ID",
    responses={
        201: {
            "description": "Pet created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "correlation_id": "req-125",
                        "timestamp": "2025-10-15T10:03:00Z",
                        "data": {
                            "id": "pet-002",
                            "name": "Max",
                            "species": "cat",
                            "breed": "Persian",
                            "age": 2,
                            "status": "available",
                            "price": 450.00,
                            "created_at": "2025-10-15T10:03:00Z"
                        }
                    }
                }
            }
        },
        400: {
            "description": "Invalid pet data",
            "model": ErrorResponse
        }
    },
    tags=["pets"],
    operation_id="createPet"
)
async def create_pet(
    pet: PetBase,
    authorization: Annotated[str, Header(description="JWT token", example="Bearer jwt-token")] = None
):
    """Create a new pet with validation and event publishing."""
    correlation_id = f"req-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Mock implementation
    new_pet = Pet(
        id=f"pet-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        **pet.model_dump(),
        status="available",
        created_at=datetime.now()
    )

    return {
        "success": True,
        "correlation_id": correlation_id,
        "timestamp": datetime.now().isoformat(),
        "data": new_pet.model_dump()
    }

@router.get(
    "/pets/{pet_id}",
    response_model=PetResponse,
    summary="Get pet by ID",
    description="""
    Retrieve detailed information about a specific pet.

    **Caching**: Individual pet data is cached for 10 minutes.

    **Related Data**: Includes availability status and reservation information.
    """,
    response_description="Pet details with current status",
    responses={
        200: {
            "description": "Pet found and returned",
            "model": PetResponse
        },
        404: {
            "description": "Pet not found",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": "Pet not found",
                        "error_code": "PET_NOT_FOUND",
                        "correlation_id": "req-126",
                        "timestamp": "2025-10-15T10:04:00Z"
                    }
                }
            }
        }
    },
    tags=["pets"],
    operation_id="getPetById"
)
async def get_pet(
    pet_id: Annotated[str, Path(description="Pet unique identifier", example="pet-001")],
    authorization: Annotated[str, Header(description="JWT token", example="Bearer jwt-token")] = None
):
    """Get a specific pet by ID."""
    correlation_id = f"req-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    if pet_id == "nonexistent":
        return JSONResponse(
            status_code=404,
            content={
                "error": "Pet not found",
                "error_code": "PET_NOT_FOUND",
                "correlation_id": correlation_id,
                "timestamp": datetime.now().isoformat()
            }
        )

    # Mock pet data
    mock_pet = {
        "id": pet_id,
        "name": "Buddy",
        "species": "dog",
        "breed": "Golden Retriever",
        "age": 3,
        "status": "available",
        "price": 599.99,
        "created_at": "2025-10-01T10:00:00Z"
    }

    return {
        "success": True,
        "correlation_id": correlation_id,
        "timestamp": datetime.now().isoformat(),
        "data": mock_pet
    }

@router.put(
    "/pets/{pet_id}",
    response_model=PetResponse,
    summary="Update pet details",
    description="""
    Update existing pet information with partial updates supported.

    **Features**:
    - Partial updates (only provided fields are updated)
    - Version conflict detection
    - Price change notifications
    - Audit trail logging

    **Events Published**:
    - `pet.updated` with change details
    - `pet.price_changed` if price is modified
    """,
    response_description="Updated pet information",
    tags=["pets"],
    operation_id="updatePet"
)
async def update_pet(
    pet_id: Annotated[str, Path(description="Pet unique identifier", example="pet-001")],
    updates: dict[str, Any],
    authorization: Annotated[str, Header(description="JWT token", example="Bearer jwt-token")] = None
):
    """Update a pet's information."""
    correlation_id = f"req-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Mock updated pet data
    mock_pet = {
        "id": pet_id,
        "name": updates.get("name", "Buddy Updated"),
        "species": "dog",
        "breed": "Golden Retriever",
        "age": 3,
        "status": "available",
        "price": updates.get("price", 649.99),
        "created_at": "2025-10-01T10:00:00Z",
        "updated_at": datetime.now().isoformat()
    }

    return {
        "success": True,
        "correlation_id": correlation_id,
        "timestamp": datetime.now().isoformat(),
        "data": mock_pet
    }

@router.get(
    "/pets/{pet_id}/availability",
    summary="Check pet availability",
    description="""
    Check if a pet is available for purchase or reservation.

    **Internal API**: This endpoint is primarily for service-to-service communication.

    **Response includes**:
    - Current availability status
    - Stock count
    - Reservation information
    - Estimated availability time
    """,
    response_description="Pet availability status",
    tags=["pets", "internal"],
    operation_id="checkPetAvailability"
)
async def check_pet_availability(
    pet_id: Annotated[str, Path(description="Pet unique identifier", example="pet-001")],
    authorization: Annotated[str, Header(description="Service token", example="Bearer service-token")] = None,
    x_service_name: Annotated[str | None, Header(alias="X-Service-Name", description="Calling service name", example="order-service")] = None
):
    """Check pet availability for internal services."""
    correlation_id = f"svc-req-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    return {
        "success": True,
        "correlation_id": correlation_id,
        "timestamp": datetime.now().isoformat(),
        "data": {
            "pet_id": pet_id,
            "available": True,
            "stock_count": 1,
            "reserved_until": None,
            "estimated_availability": None
        }
    }

@router.post(
    "/pets/{pet_id}/reserve",
    summary="Reserve pet for order",
    description="""
    Reserve a pet for a specific order with timeout.

    **Internal API**: Used by order service for inventory management.

    **Features**:
    - Automatic timeout handling
    - Idempotent operations
    - Reservation conflict detection
    """,
    response_description="Reservation confirmation",
    tags=["pets", "internal"],
    operation_id="reservePet"
)
async def reserve_pet(
    pet_id: Annotated[str, Path(description="Pet unique identifier", example="pet-001")],
    reservation_data: dict[str, Any],
    authorization: Annotated[str, Header(description="Service token", example="Bearer service-token")] = None,
    x_service_name: Annotated[str | None, Header(alias="X-Service-Name", description="Calling service name", example="order-service")] = None
):
    """Reserve a pet for order processing."""
    correlation_id = f"svc-req-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    if pet_id == "out-of-stock-pet":
        return JSONResponse(
            status_code=409,
            content={
                "error": "Insufficient stock",
                "error_code": "INSUFFICIENT_STOCK",
                "correlation_id": correlation_id,
                "timestamp": datetime.now().isoformat()
            }
        )

    return {
        "success": True,
        "correlation_id": correlation_id,
        "timestamp": datetime.now().isoformat(),
        "data": {
            "pet_id": pet_id,
            "reservation_id": f"res-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "reserved_until": "2025-10-15T10:20:00Z",
            "order_id": reservation_data.get("order_id"),
            "customer_id": reservation_data.get("customer_id")
        }
    }

# Legacy v1 compatibility endpoint (deprecated)
@router.get(
    "/api/v1/pets",
    summary="List pets (Legacy v1.0 - DEPRECATED)",
    description="""
    **⚠️ DEPRECATED**: This endpoint is deprecated and will be removed on 2024-12-31.

    Please migrate to `/petstore-domain/v2/pets` for the new API format.

    **Migration Guide**: https://docs.petstore.example.com/migration/v1-to-v2
    """,
    deprecated=True,
    tags=["pets", "legacy"],
    operation_id="listPetsLegacy"
)
async def list_pets_legacy():
    """Legacy v1.0 pets endpoint - deprecated."""
    return {
        "pets": [
            {
                "id": 1,
                "name": "Buddy",
                "type": "dog",
                "price": 599.99
            }
        ],
        "total": 1
    }

# Add the enhanced router to the existing petstore routes
# This would typically be done in the main routes file
