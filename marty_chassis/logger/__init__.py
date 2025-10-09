"""
Structured logging framework for the Marty Chassis.

This module provides:
- Structured logging with JSON output
- Correlation ID tracking across requests
- Context-aware logging with automatic metadata
- Performance monitoring and request tracing
- Configurable log levels and formats
"""

import contextvars
import json
import logging
import logging.config
import sys
import time
import traceback
import uuid
from typing import Any, Optional, Set, Union, dict

import structlog
from pythonjsonlogger import jsonlogger

from ..config import LogLevel
from ..exceptions import ConfigurationError

# Context variables for correlation tracking
correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
user_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "user_id", default=None
)


class CorrelationIDProcessor:
    """Processor to add correlation IDs to log records."""

    def __call__(self, logger, method_name, event_dict):
        correlation_id = correlation_id_var.get()
        if correlation_id:
            event_dict["correlation_id"] = correlation_id

        request_id = request_id_var.get()
        if request_id:
            event_dict["request_id"] = request_id

        user_id = user_id_var.get()
        if user_id:
            event_dict["user_id"] = user_id

        return event_dict


class TimestampProcessor:
    """Processor to add timestamps to log records."""

    def __call__(self, logger, method_name, event_dict):
        event_dict["timestamp"] = time.time()
        return event_dict


class ServiceInfoProcessor:
    """Processor to add service information to log records."""

    def __init__(self, service_name: str, service_version: str = "1.0.0"):
        self.service_name = service_name
        self.service_version = service_version

    def __call__(self, logger, method_name, event_dict):
        event_dict["service_name"] = self.service_name
        event_dict["service_version"] = self.service_version
        return event_dict


class ExceptionProcessor:
    """Processor to format exceptions in log records."""

    def __call__(self, logger, method_name, event_dict):
        exc_info = event_dict.pop("exc_info", None)
        if exc_info:
            if exc_info is True:
                exc_info = sys.exc_info()

            if exc_info[0] is not None:
                event_dict["exception"] = {
                    "type": exc_info[0].__name__,
                    "message": str(exc_info[1]),
                    "traceback": "".join(traceback.format_tb(exc_info[2]))
                    if exc_info[2]
                    else "",
                }
        return event_dict


class LogConfig:
    """Configuration class for logging setup."""

    def __init__(
        self,
        service_name: str,
        service_version: str = "1.0.0",
        level: LogLevel = LogLevel.INFO,
        format_type: str = "json",
        enable_correlation: bool = True,
        log_file: str | None = None,
    ):
        self.service_name = service_name
        self.service_version = service_version
        self.level = level
        self.format_type = format_type
        self.enable_correlation = enable_correlation
        self.log_file = log_file


def setup_logging(config: LogConfig) -> None:
    """
    Setup structured logging with the given configuration.

    Args:
        config: LogConfig instance with logging configuration
    """
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        TimestampProcessor(),
        ServiceInfoProcessor(config.service_name, config.service_version),
        ExceptionProcessor(),
    ]

    if config.enable_correlation:
        processors.insert(-1, CorrelationIDProcessor())

    if config.format_type == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    handlers = ["console"]
    if config.log_file:
        handlers.append("file")

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": jsonlogger.JsonFormatter,
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
            },
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": config.level.value,
                "formatter": "json" if config.format_type == "json" else "standard",
                "stream": sys.stdout,
            },
        },
        "loggers": {
            "": {
                "handlers": ["console"],
                "level": config.level.value,
                "propagate": False,
            },
        },
    }

    if config.log_file:
        logging_config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": config.level.value,
            "formatter": "json" if config.format_type == "json" else "standard",
            "filename": config.log_file,
            "maxBytes": 10 * 1024 * 1024,  # 10MB
            "backupCount": 5,
        }
        logging_config["loggers"][""]["handlers"].append("file")

    try:
        logging.config.dictConfig(logging_config)
    except Exception as e:
        raise ConfigurationError(f"Failed to configure logging: {e}")


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name, typically __name__

    Returns:
        Configured structlog.BoundLogger instance
    """
    return structlog.get_logger(name)


def set_correlation_id(correlation_id: str | None = None) -> str:
    """
    Set correlation ID for the current context.

    Args:
        correlation_id: Correlation ID to set, or None to generate a new one

    Returns:
        The correlation ID that was set
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())

    correlation_id_var.set(correlation_id)
    return correlation_id


def get_correlation_id() -> str | None:
    """Get the current correlation ID."""
    return correlation_id_var.get()


def set_request_id(request_id: str) -> None:
    """Set request ID for the current context."""
    request_id_var.set(request_id)


def get_request_id() -> str | None:
    """Get the current request ID."""
    return request_id_var.get()


def set_user_id(user_id: str) -> None:
    """Set user ID for the current context."""
    user_id_var.set(user_id)


def get_user_id() -> str | None:
    """Get the current user ID."""
    return user_id_var.get()


def clear_context() -> None:
    """Clear all context variables."""
    correlation_id_var.set(None)
    request_id_var.set(None)
    user_id_var.set(None)


class RequestLogger:
    """Context manager for request-scoped logging."""

    def __init__(
        self,
        logger: structlog.BoundLogger,
        operation: str,
        correlation_id: str | None = None,
        request_id: str | None = None,
        user_id: str | None = None,
        **kwargs,
    ):
        self.logger = logger
        self.operation = operation
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.request_id = request_id
        self.user_id = user_id
        self.extra_context = kwargs
        self.start_time: float | None = None

    def __enter__(self):
        self.start_time = time.time()

        # Set context variables
        set_correlation_id(self.correlation_id)
        if self.request_id:
            set_request_id(self.request_id)
        if self.user_id:
            set_user_id(self.user_id)

        # Log operation start
        self.logger.info(
            "Operation started", operation=self.operation, **self.extra_context
        )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - (self.start_time or 0)

        if exc_type is None:
            self.logger.info(
                "Operation completed",
                operation=self.operation,
                duration_ms=round(duration * 1000, 2),
                **self.extra_context,
            )
        else:
            self.logger.error(
                "Operation failed",
                operation=self.operation,
                duration_ms=round(duration * 1000, 2),
                error_type=exc_type.__name__,
                error_message=str(exc_val),
                **self.extra_context,
                exc_info=True,
            )

        # Clear context
        clear_context()


def log_performance(func):
    """
    Decorator to log function performance.

    Args:
        func: Function to wrap

    Returns:
        Wrapped function with performance logging
    """
    logger = get_logger(func.__module__)

    def wrapper(*args, **kwargs):
        with RequestLogger(logger, f"{func.__name__}"):
            return func(*args, **kwargs)

    return wrapper


# Global logger instance
_global_logger: structlog.BoundLogger | None = None


def init_global_logger(config: LogConfig) -> None:
    """Initialize the global logger with configuration."""
    global _global_logger
    setup_logging(config)
    _global_logger = get_logger("marty_chassis")


def get_global_logger() -> structlog.BoundLogger:
    """Get the global logger instance."""
    global _global_logger
    if _global_logger is None:
        # Initialize with default config
        config = LogConfig("marty_chassis")
        init_global_logger(config)
    return _global_logger
