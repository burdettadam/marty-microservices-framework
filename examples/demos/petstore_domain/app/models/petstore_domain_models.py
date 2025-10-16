"""
Data Models for PetstoreDomain Service

This module defines Pydantic models for request/response validation
and data structures following the Marty framework patterns.

Add your specific data models while maintaining proper validation and documentation.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


class ServiceStatus(str, Enum):
    """Service status enumeration"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"

class OperationStatus(str, Enum):
    """Operation status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class BaseResponse(BaseModel):
    """Base response model with common fields"""
    success: bool = Field(..., description="Operation success status")
    correlation_id: str = Field(..., description="Request correlation ID")
    timestamp: str = Field(..., description="Response timestamp")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ErrorResponse(BaseModel):
    """Standard error response model"""
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Specific error code")
    correlation_id: str = Field(..., description="Request correlation ID")
    timestamp: str = Field(..., description="Error timestamp")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")

class PetstoreDomainRequest(BaseModel):
    """
    Base request model for PetstoreDomain operations.

    Customize this model for your specific request requirements.
    """
    operation_type: str = Field(..., description="Type of operation to perform")
    data: Dict[str, Any] = Field(..., description="Operation data")
    options: Optional[Dict[str, Any]] = Field(None, description="Additional options")

    @validator('operation_type')
    def validate_operation_type(cls, v):
        """Validate operation type"""
        allowed_operations = [
            "process",
            "validate",
            "transform",
            "analyze"
            # Add your specific operations here
        ]
        if v not in allowed_operations:
            raise ValueError(f"Operation type must be one of: {allowed_operations}")
        return v

    @validator('data')
    def validate_data_not_empty(cls, v):
        """Ensure data is not empty"""
        if not v:
            raise ValueError("Data cannot be empty")
        return v

class PetstoreDomainResponse(BaseResponse):
    """
    Response model for PetstoreDomain operations.

    Customize this model for your specific response requirements.
    """
    operation_type: str = Field(..., description="Type of operation performed")
    data: Dict[str, Any] = Field(..., description="Response data")
    processing_time_ms: Optional[float] = Field(None, description="Processing time in milliseconds")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class HealthCheckResponse(BaseModel):
    """Health check response model"""
    status: ServiceStatus = Field(..., description="Service health status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    timestamp: str = Field(..., description="Health check timestamp")
    checks: Optional[Dict[str, Any]] = Field(None, description="Individual health check results")
    uptime_seconds: Optional[float] = Field(None, description="Service uptime in seconds")

class MetricsResponse(BaseModel):
    """Metrics response model"""
    service: str = Field(..., description="Service name")
    timestamp: str = Field(..., description="Metrics timestamp")
    metrics: Dict[str, Any] = Field(..., description="Service metrics")

class ConfigurationResponse(BaseModel):
    """Configuration response model (for debugging)"""
    service: str = Field(..., description="Service name")
    environment: str = Field(..., description="Environment")
    configuration: Dict[str, Any] = Field(..., description="Configuration summary")
    timestamp: str = Field(..., description="Configuration timestamp")

# Business Domain Models
# Add your specific business models below

class BusinessEntity(BaseModel):
    """
    Example business entity model.

    Replace this with your actual business entities.
    """
    id: str = Field(..., description="Entity identifier")
    name: str = Field(..., description="Entity name")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    status: str = Field(default="active", description="Entity status")

    @validator('name')
    def validate_name(cls, v):
        """Validate entity name"""
        if not v or len(v.strip()) == 0:
            raise ValueError("Name cannot be empty")
        return v.strip()

class ProcessingResult(BaseModel):
    """
    Model for processing operation results.

    Customize based on your processing requirements.
    """
    operation_id: str = Field(..., description="Operation identifier")
    status: OperationStatus = Field(..., description="Processing status")
    input_data: Dict[str, Any] = Field(..., description="Input data")
    output_data: Optional[Dict[str, Any]] = Field(None, description="Output data")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    started_at: datetime = Field(..., description="Processing start time")
    completed_at: Optional[datetime] = Field(None, description="Processing completion time")
    processing_time_ms: Optional[float] = Field(None, description="Processing time in milliseconds")

    @validator('processing_time_ms')
    def validate_processing_time(cls, v):
        """Validate processing time is positive"""
        if v is not None and v < 0:
            raise ValueError("Processing time cannot be negative")
        return v

class ValidationRequest(BaseModel):
    """Request model for data validation operations"""
    data: Dict[str, Any] = Field(..., description="Data to validate")
    validation_rules: Optional[List[str]] = Field(None, description="Specific validation rules to apply")
    strict_mode: bool = Field(default=False, description="Enable strict validation mode")

class ValidationResponse(BaseResponse):
    """Response model for validation operations"""
    valid: bool = Field(..., description="Overall validation result")
    errors: List[str] = Field(default=[], description="Validation errors")
    warnings: List[str] = Field(default=[], description="Validation warnings")
    data: Dict[str, Any] = Field(..., description="Validated data")

class BatchOperationRequest(BaseModel):
    """Request model for batch operations"""
    operations: List[PetstoreDomainRequest] = Field(..., description="List of operations to perform")
    batch_options: Optional[Dict[str, Any]] = Field(None, description="Batch processing options")

    @validator('operations')
    def validate_operations_not_empty(cls, v):
        """Ensure operations list is not empty"""
        if not v:
            raise ValueError("Operations list cannot be empty")
        return v

class BatchOperationResponse(BaseResponse):
    """Response model for batch operations"""
    total_operations: int = Field(..., description="Total number of operations")
    successful_operations: int = Field(..., description="Number of successful operations")
    failed_operations: int = Field(..., description="Number of failed operations")
    results: List[PetstoreDomainResponse] = Field(..., description="Individual operation results")
    batch_processing_time_ms: Optional[float] = Field(None, description="Total batch processing time")

# Pagination Models
class PaginationRequest(BaseModel):
    """Request model for paginated operations"""
    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    page_size: int = Field(default=10, ge=1, le=100, description="Number of items per page")
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: Optional[str] = Field(default="asc", description="Sort order (asc/desc)")

    @validator('sort_order')
    def validate_sort_order(cls, v):
        """Validate sort order"""
        if v and v.lower() not in ['asc', 'desc']:
            raise ValueError("Sort order must be 'asc' or 'desc'")
        return v.lower() if v else v

class PaginatedResponse(BaseModel):
    """Response model for paginated data"""
    items: List[Any] = Field(..., description="Items in the current page")
    total_items: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    current_page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_previous: bool = Field(..., description="Whether there is a previous page")

# Add more models specific to your business domain below
# Examples:
# - User models
# - Product models
# - Transaction models
# - Configuration models
# - Audit models
# etc.
