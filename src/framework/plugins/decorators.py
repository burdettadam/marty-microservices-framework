"""
Decorators for MMF plugin services.

This module provides decorators that plugin services can use to integrate
with MMF infrastructure components like authentication, metrics, tracing,
and event handling.
"""

import functools
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


def plugin_service(name: str | None = None,
                  version: str = "1.0.0",
                  description: str = "",
                  dependencies: list[str] | None = None):
    """Decorator to mark a class as a plugin service.

    Args:
        name: Service name (defaults to class name)
        version: Service version
        description: Service description
        dependencies: List of service dependencies
    """
    def decorator(cls):
        cls._mmf_service_name = name or cls.__name__
        cls._mmf_service_version = version
        cls._mmf_service_description = description
        cls._mmf_service_dependencies = dependencies or []
        return cls
    return decorator


def requires_auth(roles: list[str] | None = None,
                 permissions: list[str] | None = None,
                 optional: bool = False):
    """Decorator to require authentication for a method.

    Args:
        roles: Required user roles
        permissions: Required permissions
        optional: Whether auth is optional
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Authentication logic would be implemented by MMF security
            # This is a placeholder for the decorator structure

            if hasattr(self, 'context') and self.context.security:
                auth_result = await self.context.security.authenticate_request(
                    roles=roles,
                    permissions=permissions,
                    optional=optional
                )

                if not auth_result.authenticated and not optional:
                    raise PermissionError("Authentication required")

                # Add auth info to kwargs for the method
                kwargs['_auth_result'] = auth_result

            return await func(self, *args, **kwargs)

        # Mark function as requiring auth using setattr to avoid type checker issues
        wrapper._requires_auth = True
        wrapper._auth_roles = roles or []
        wrapper._auth_permissions = permissions or []
        wrapper._auth_optional = optional

        return wrapper
    return decorator


def track_metrics(metric_name: str | None = None,
                 labels: dict[str, str] | None = None,
                 timing: bool = True,
                 counter: bool = True):
    """Decorator to track metrics for a method.

    Args:
        metric_name: Custom metric name (defaults to method name)
        labels: Additional metric labels
        timing: Whether to track execution time
        counter: Whether to track call count
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Metrics logic would be implemented by MMF observability
            metric_name_actual = metric_name or func.__name__
            labels_actual = labels or {}

            if hasattr(self, 'context') and self.context.observability:
                metrics = self.context.observability.get_metrics_collector()

                # Start timing if enabled
                timer = None
                if timing:
                    timer = metrics.start_timer(f"{metric_name_actual}_duration", labels_actual)

                try:
                    result = await func(self, *args, **kwargs)

                    # Increment success counter
                    if counter:
                        success_labels = {**labels_actual, "status": "success"}
                        metrics.increment_counter(f"{metric_name_actual}_total", success_labels)

                    return result

                except Exception as e:
                    # Increment error counter
                    if counter:
                        error_labels = {**labels_actual, "status": "error", "error_type": type(e).__name__}
                        metrics.increment_counter(f"{metric_name_actual}_total", error_labels)
                    raise

                finally:
                    # Stop timing
                    if timer:
                        timer.stop()
            else:
                return await func(self, *args, **kwargs)

        # Mark function as tracked using setattr to avoid type checker issues
        wrapper._tracks_metrics = True
        wrapper._metric_name = metric_name
        wrapper._metric_labels = labels or {}

        return wrapper
    return decorator


def trace_operation(operation_name: str | None = None,
                   tags: dict[str, str] | None = None,
                   log_inputs: bool = False,
                   log_outputs: bool = False):
    """Decorator to add distributed tracing to a method.

    Args:
        operation_name: Custom operation name (defaults to method name)
        tags: Additional span tags
        log_inputs: Whether to log input parameters
        log_outputs: Whether to log output values
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            operation_name_actual = operation_name or func.__name__
            tags_actual = tags or {}

            if hasattr(self, 'context') and self.context.observability:
                tracer = self.context.observability.get_tracer()

                with tracer.start_span(operation_name_actual) as span:
                    # Add tags
                    for key, value in tags_actual.items():
                        span.set_attribute(key, value)

                    # Log inputs if enabled
                    if log_inputs:
                        span.set_attribute("input.args", str(args))
                        span.set_attribute("input.kwargs", str(kwargs))

                    try:
                        result = await func(self, *args, **kwargs)

                        # Log outputs if enabled
                        if log_outputs:
                            span.set_attribute("output.result", str(result))

                        span.set_attribute("status", "success")
                        return result

                    except Exception as e:
                        span.set_attribute("status", "error")
                        span.set_attribute("error.type", type(e).__name__)
                        span.set_attribute("error.message", str(e))
                        raise
            else:
                return await func(self, *args, **kwargs)

        # Mark function as traced using setattr to avoid type checker issues
        wrapper._traces_operation = True
        wrapper._operation_name = operation_name
        wrapper._trace_tags = tags or {}

        return wrapper
    return decorator


def event_handler(event_type: str,
                 filter_condition: Callable[[Any], bool] | None = None,
                 retry_attempts: int = 3,
                 async_processing: bool = False):
    """Decorator to mark a method as an event handler.

    Args:
        event_type: Type of event to handle
        filter_condition: Optional filter function for events
        retry_attempts: Number of retry attempts on failure
        async_processing: Whether to process events asynchronously
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, event, *args, **kwargs):
            # Event handling logic would be implemented by MMF event bus

            # Apply filter if provided
            if filter_condition and not filter_condition(event):
                return

            # Process event with retry logic
            for attempt in range(retry_attempts + 1):
                try:
                    if async_processing:
                        # Schedule for background processing
                        if hasattr(self, 'context') and self.context.event_bus:
                            await self.context.event_bus.process_async(
                                func, self, event, *args, **kwargs
                            )
                        return
                    else:
                        return await func(self, event, *args, **kwargs)

                except Exception as e:
                    if attempt < retry_attempts:
                        logger.warning(f"Event handler {func.__name__} failed (attempt {attempt + 1}), retrying: {e}")
                    else:
                        logger.error(f"Event handler {func.__name__} failed after {retry_attempts + 1} attempts: {e}")
                        raise

        # Mark function as event handler using setattr to avoid type checker issues
        wrapper._event_handler = True
        wrapper._event_type = event_type
        wrapper._filter_condition = filter_condition
        wrapper._retry_attempts = retry_attempts
        wrapper._async_processing = async_processing

        return wrapper
    return decorator


def cache_result(ttl: int = 300,
                key_generator: Callable | None = None,
                invalidate_on: list[str] | None = None):
    """Decorator to cache method results.

    Args:
        ttl: Time to live in seconds
        key_generator: Function to generate cache key
        invalidate_on: List of events that should invalidate cache
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            if hasattr(self, 'context') and self.context.cache:
                cache = self.context.cache

                # Generate cache key
                if key_generator:
                    cache_key = key_generator(self, *args, **kwargs)
                else:
                    cache_key = f"{self.__class__.__name__}.{func.__name__}:{hash((args, tuple(sorted(kwargs.items()))))}"

                # Try to get from cache
                cached_result = await cache.get(cache_key)
                if cached_result is not None:
                    return cached_result

                # Execute function and cache result
                result = await func(self, *args, **kwargs)
                await cache.set(cache_key, result, ttl=ttl)

                return result
            else:
                return await func(self, *args, **kwargs)

        # Mark function as cached using setattr to avoid type checker issues
        wrapper._cached = True
        wrapper._cache_ttl = ttl
        wrapper._key_generator = key_generator
        wrapper._invalidate_on = invalidate_on or []

        return wrapper
    return decorator


def rate_limit(requests_per_second: int = 10,
              burst_size: int | None = None,
              key_generator: Callable | None = None):
    """Decorator to apply rate limiting to a method.

    Args:
        requests_per_second: Maximum requests per second
        burst_size: Maximum burst size (defaults to requests_per_second)
        key_generator: Function to generate rate limit key
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            if hasattr(self, 'context') and self.context.security:
                rate_limiter = self.context.security.get_rate_limiter()

                # Generate rate limit key
                if key_generator:
                    rate_key = key_generator(self, *args, **kwargs)
                else:
                    rate_key = f"{self.__class__.__name__}.{func.__name__}"

                # Check rate limit
                allowed = await rate_limiter.check_rate_limit(
                    key=rate_key,
                    requests_per_second=requests_per_second,
                    burst_size=burst_size or requests_per_second
                )

                if not allowed:
                    raise PermissionError("Rate limit exceeded")

            return await func(self, *args, **kwargs)

        # Mark function as rate limited using setattr to avoid type checker issues
        wrapper._rate_limited = True
        wrapper._requests_per_second = requests_per_second
        wrapper._burst_size = burst_size
        wrapper._rate_key_generator = key_generator

        return wrapper
    return decorator
