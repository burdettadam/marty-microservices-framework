"""
Event Publishing Decorators

Decorators for automatic event publishing on method success/failure.
"""

import functools
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from .publisher import get_event_publisher
from .types import AuditEventType, EventMetadata, EventPriority

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def audit_event(
    event_type: AuditEventType,
    action: str,
    resource_type: str,
    resource_id_field: str | None = None,
    success_only: bool = False,
    include_args: bool = False,
    include_result: bool = False,
    priority: EventPriority = EventPriority.NORMAL,
) -> Callable[[F], F]:
    """
    Decorator to automatically publish audit events when a method is called.

    Args:
        event_type: Type of audit event
        action: Action being audited
        resource_type: Type of resource being acted upon
        resource_id_field: Field name or path to extract resource ID from args/kwargs
        success_only: Only publish event on successful execution
        include_args: Include method arguments in event data
        include_result: Include method result in event data
        priority: Event priority level

    Example:
        @audit_event(
            event_type=AuditEventType.DATA_CREATED,
            action="create_user",
            resource_type="user",
            resource_id_field="user_id"
        )
        async def create_user(self, user_id: str, user_data: dict):
            # Method implementation
            pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            success = False
            result = None
            error = None

            try:
                result = await func(*args, **kwargs)
                success = True
                return result
            except Exception as e:
                error = e
                if not success_only:
                    # Re-raise after logging event
                    raise
            finally:
                if success or not success_only:
                    await _publish_audit_event(
                        event_type=event_type,
                        action=action,
                        resource_type=resource_type,
                        resource_id_field=resource_id_field,
                        args=args,
                        kwargs=kwargs,
                        result=result,
                        success=success,
                        error=error,
                        include_args=include_args,
                        include_result=include_result,
                        priority=priority,
                    )

            if error:
                raise error

        return wrapper  # type: ignore

    return decorator


def domain_event(
    aggregate_type: str,
    event_type: str,
    aggregate_id_field: str,
    success_only: bool = True,
    include_args: bool = True,
    include_result: bool = False,
) -> Callable[[F], F]:
    """
    Decorator to automatically publish domain events when a method is called.

    Args:
        aggregate_type: Type of domain aggregate
        event_type: Type of domain event
        aggregate_id_field: Field name to extract aggregate ID from args/kwargs
        success_only: Only publish event on successful execution
        include_args: Include method arguments in event data
        include_result: Include method result in event data

    Example:
        @domain_event(
            aggregate_type="user",
            event_type="user_created",
            aggregate_id_field="user_id"
        )
        async def create_user(self, user_id: str, user_data: dict):
            # Method implementation
            pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            success = False
            result = None

            try:
                result = await func(*args, **kwargs)
                success = True
                return result
            except Exception:
                if not success_only:
                    # Publish event even on failure
                    await _publish_domain_event(
                        aggregate_type=aggregate_type,
                        event_type=f"{event_type}_failed",
                        aggregate_id_field=aggregate_id_field,
                        args=args,
                        kwargs=kwargs,
                        result=None,
                        include_args=include_args,
                        include_result=False,
                    )
                raise
            finally:
                if success:
                    await _publish_domain_event(
                        aggregate_type=aggregate_type,
                        event_type=event_type,
                        aggregate_id_field=aggregate_id_field,
                        args=args,
                        kwargs=kwargs,
                        result=result,
                        include_args=include_args,
                        include_result=include_result,
                    )

        return wrapper  # type: ignore

    return decorator


def publish_on_success(
    topic: str,
    event_type: str,
    key_field: str | None = None,
    include_args: bool = True,
    include_result: bool = True,
) -> Callable[[F], F]:
    """
    Decorator to publish a custom event when a method succeeds.

    Args:
        topic: Kafka topic name
        event_type: Type of event
        key_field: Field name to extract partition key from args/kwargs
        include_args: Include method arguments in event data
        include_result: Include method result in event data

    Example:
        @publish_on_success(
            topic="user.events",
            event_type="user_login_successful",
            key_field="user_id"
        )
        async def authenticate_user(self, user_id: str, password: str):
            # Method implementation
            pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            # Extract data for event
            event_data = {}
            if include_args:
                event_data["args"] = _serialize_args(args, kwargs)
            if include_result:
                event_data["result"] = _serialize_result(result)

            # Extract partition key
            key = _extract_field_value(key_field, args, kwargs) if key_field else None

            # Publish event
            publisher = get_event_publisher()
            await publisher.publish_custom_event(
                topic=topic, event_type=event_type, payload=event_data, key=key
            )

            return result

        return wrapper  # type: ignore

    return decorator


def publish_on_error(
    topic: str,
    event_type: str,
    key_field: str | None = None,
    include_args: bool = True,
    include_error: bool = True,
) -> Callable[[F], F]:
    """
    Decorator to publish a custom event when a method fails.

    Args:
        topic: Kafka topic name
        event_type: Type of event
        key_field: Field name to extract partition key from args/kwargs
        include_args: Include method arguments in event data
        include_error: Include error information in event data

    Example:
        @publish_on_error(
            topic="user.events",
            event_type="user_login_failed",
            key_field="user_id"
        )
        async def authenticate_user(self, user_id: str, password: str):
            # Method implementation
            pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Extract data for event
                event_data = {}
                if include_args:
                    event_data["args"] = _serialize_args(args, kwargs)
                if include_error:
                    event_data["error"] = {"type": e.__class__.__name__, "message": str(e)}

                # Extract partition key
                key = _extract_field_value(key_field, args, kwargs) if key_field else None

                # Publish event
                try:
                    publisher = get_event_publisher()
                    await publisher.publish_custom_event(
                        topic=topic, event_type=event_type, payload=event_data, key=key
                    )
                except Exception as publish_error:
                    logger.error(f"Failed to publish error event: {publish_error}")

                # Re-raise original exception
                raise

        return wrapper  # type: ignore

    return decorator


async def _publish_audit_event(
    event_type: AuditEventType,
    action: str,
    resource_type: str,
    resource_id_field: str | None,
    args: tuple,
    kwargs: dict,
    result: Any,
    success: bool,
    error: Exception | None,
    include_args: bool,
    include_result: bool,
    priority: EventPriority,
) -> None:
    """Internal helper to publish audit events."""
    try:
        # Extract resource ID
        resource_id = (
            _extract_field_value(resource_id_field, args, kwargs) if resource_id_field else None
        )

        # Build operation details
        operation_details = {}
        if include_args:
            operation_details["args"] = _serialize_args(args, kwargs)
        if include_result and result is not None:
            operation_details["result"] = _serialize_result(result)

        # Create metadata
        metadata = EventMetadata(
            service_name="unknown",  # Will be set by publisher
            priority=priority,
        )

        # Publish audit event
        publisher = get_event_publisher()
        await publisher.publish_audit_event(
            event_type=event_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata,
            operation_details=operation_details,
            success=success,
            error_message=str(error) if error else None,
            error_code=error.__class__.__name__ if error else None,
        )

    except Exception as e:
        logger.error(f"Failed to publish audit event: {e}")


async def _publish_domain_event(
    aggregate_type: str,
    event_type: str,
    aggregate_id_field: str,
    args: tuple,
    kwargs: dict,
    result: Any,
    include_args: bool,
    include_result: bool,
) -> None:
    """Internal helper to publish domain events."""
    try:
        # Extract aggregate ID
        aggregate_id = _extract_field_value(aggregate_id_field, args, kwargs)
        if not aggregate_id:
            logger.warning(f"Could not extract aggregate ID from field: {aggregate_id_field}")
            return

        # Build event data
        event_data = {}
        if include_args:
            event_data.update(_serialize_args(args, kwargs))
        if include_result and result is not None:
            event_data["result"] = _serialize_result(result)

        # Publish domain event
        publisher = get_event_publisher()
        await publisher.publish_domain_event(
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id),
            event_type=event_type,
            event_data=event_data,
        )

    except Exception as e:
        logger.error(f"Failed to publish domain event: {e}")


def _extract_field_value(field_path: str, args: tuple, kwargs: dict) -> Any:
    """Extract a field value from method arguments."""
    if not field_path:
        return None

    # Try kwargs first
    if field_path in kwargs:
        return kwargs[field_path]

    # Handle nested field paths (e.g., "user.id")
    parts = field_path.split(".")

    # Check if first part is in kwargs
    if parts[0] in kwargs:
        value = kwargs[parts[0]]
        for part in parts[1:]:
            if hasattr(value, part):
                value = getattr(value, part)
            elif isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        return value

    # Try to match positional arguments by name (basic heuristic)
    # This is limited - in practice, use kwargs for reliable field extraction
    if len(args) > 0 and parts[0] in ["self", "cls"]:
        # Skip self/cls and try next argument
        if len(args) > 1:
            return args[1]

    return None


def _serialize_args(args: tuple, kwargs: dict) -> dict[str, Any]:
    """Serialize method arguments for event data."""
    serialized = {}

    # Add positional args (skip self/cls)
    if args:
        start_idx = 1 if len(args) > 0 and hasattr(args[0], "__class__") else 0
        for i, arg in enumerate(args[start_idx:]):
            serialized[f"arg_{i}"] = _serialize_value(arg)

    # Add keyword args
    for key, value in kwargs.items():
        serialized[key] = _serialize_value(value)

    return serialized


def _serialize_result(result: Any) -> Any:
    """Serialize method result for event data."""
    return _serialize_value(result)


def _serialize_value(value: Any) -> Any:
    """Serialize a value for JSON encoding."""
    try:
        # Handle common types
        if value is None or isinstance(value, str | int | float | bool):
            return value

        if isinstance(value, list | tuple):
            return [_serialize_value(item) for item in value]

        if isinstance(value, dict):
            return {k: _serialize_value(v) for k, v in value.items()}

        # Handle objects with dict() method (Pydantic models, etc.)
        if hasattr(value, "dict") and callable(value.dict):
            return value.dict()

        # Handle objects with __dict__ attribute
        if hasattr(value, "__dict__"):
            return {
                k: _serialize_value(v) for k, v in value.__dict__.items() if not k.startswith("_")
            }

        # Fallback to string representation
        return str(value)

    except Exception:
        # Last resort - return string representation
        return str(value)
