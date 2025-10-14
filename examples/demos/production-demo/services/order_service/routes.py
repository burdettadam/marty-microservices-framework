"""
API routes for order-service service using DRY patterns.
"""


from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from src.order_service.app.core.config import create_order_service_config
from src.order_service.app.services.order_service_service import OrderServiceService

router = APIRouter(tags=["order-service"])

# Dependency to get service configuration
def get_config():
    """Get service configuration."""
    return create_order_service_config()

# Dependency to get service instance
def get_order_service_service(config=Depends(get_config)):
    """Get order-service service instance."""
    return OrderServiceService(config)


# Request/Response models
class StatusResponse(BaseModel):
    """Service status response."""
    service_name: str
    version: str
    is_healthy: bool
    timestamp: str


# Store Domain Models
class OrderItem(BaseModel):
    """Individual item in an order."""
    product_id: str
    quantity: int
    price: float

class OrderRequest(BaseModel):
    """Order creation request."""
    customer_id: str
    items: list[OrderItem]
    shipping_address: str

class OrderResponse(BaseModel):
    """Order creation response."""
    order_id: str
    correlation_id: str
    status: str
    total_amount: float
    processing_time_ms: float
    trace_info: dict


@router.get("/health", response_model=StatusResponse)
async def get_health_status(
    service: OrderServiceService = Depends(get_order_service_service)
) -> StatusResponse:
    """
    Get service health status.

    Returns:
        Service health and status information
    """
    try:
        status = await service.get_status()
        return StatusResponse(**status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/status", response_model=StatusResponse)
async def get_service_status(
    service: OrderServiceService = Depends(get_order_service_service)
) -> StatusResponse:
    """
    Get detailed service status.

    Returns:
        Detailed service status information
    """
    try:
        status = await service.get_detailed_status()
        return StatusResponse(**status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.post("/orders", response_model=OrderResponse)
async def create_order(
    request: OrderRequest,
    service: OrderServiceService = Depends(get_order_service_service)
) -> OrderResponse:
    """
    Create a new order with full transaction tracing.

    Args:
        request: Order creation request with customer and item details
        service: Service instance

    Returns:
        Order creation result with tracing information
    """
    try:
        result = await service.create_order(
            customer_id=request.customer_id,
            items=[item.dict() for item in request.items],
            shipping_address=request.shipping_address
        )
        return OrderResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Order creation failed: {str(e)}")

@router.get("/orders/{order_id}")
async def get_order_status(
    order_id: str,
    service: OrderServiceService = Depends(get_order_service_service)
) -> dict:
    """Get order status and details."""
    try:
        result = await service.get_order_status(order_id=order_id)
        if not result:
            raise HTTPException(status_code=404, detail="Order not found")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status retrieval failed: {str(e)}")

@router.get("/orders")
async def list_orders(
    customer_id: str = None,
    service: OrderServiceService = Depends(get_order_service_service)
) -> dict:
    """List orders, optionally filtered by customer."""
    try:
        result = await service.list_orders(customer_id=customer_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Order listing failed: {str(e)}")
#     try:
#         status = await service.get_document_status(document_id)
#         if not status:
#             raise HTTPException(status_code=404, detail="Document not found")
#         return status
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")
