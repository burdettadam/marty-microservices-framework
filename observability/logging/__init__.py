"""
Structured Logging Framework for Marty Microservices Framework

Provides comprehensive structured logging capabilities with:
- JSON structured logging format
- Correlation IDs and trace context integration
- Performance metrics and business event logging
- Integration with ELK/EFK stack
- Centralized log aggregation and analysis
"""

import builtins
import importlib.util
import json
import logging
import sys
import time
import traceback
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

# OpenTelemetry integration availability check
OTEL_AVAILABLE = importlib.util.find_spec("opentelemetry") is not None

if OTEL_AVAILABLE:
    try:
        from opentelemetry.trace import get_current_span
    except ImportError:
        OTEL_AVAILABLE = False

# FastAPI integration availability check
FASTAPI_AVAILABLE = importlib.util.find_spec("fastapi") is not None

if FASTAPI_AVAILABLE:
    try:
        from fastapi import Request
        from starlette.middleware.base import BaseHTTPMiddleware
    except ImportError:
        FASTAPI_AVAILABLE = False


class LogLevel(Enum):
    """Standard log levels"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(Enum):
    """Categories for log classification"""

    APPLICATION = "application"
    SECURITY = "security"
    PERFORMANCE = "performance"
    BUSINESS = "business"
    INFRASTRUCTURE = "infrastructure"
    AUDIT = "audit"
    ACCESS = "access"
    ERROR = "error"
    MONITORING = "monitoring"


@dataclass
class LogContext:
    """Context information for logging"""

    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str | None = None
    span_id: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    service_name: str = "unknown"
    service_version: str = "1.0.0"
    environment: str = "production"
    namespace: str = "default"
    custom_fields: builtins.dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        # Remove None values and empty custom_fields
        result = {k: v for k, v in result.items() if v is not None}
        if not result.get("custom_fields"):
            result.pop("custom_fields", None)
        return result


@dataclass
class StructuredLogEntry:
    """Structured log entry"""

    timestamp: str
    level: str
    message: str
    category: str
    service_name: str
    context: builtins.dict[str, Any]
    fields: builtins.dict[str, Any] = field(default_factory=dict)
    error: builtins.dict[str, Any] | None = None
    performance: builtins.dict[str, Any] | None = None
    business: builtins.dict[str, Any] | None = None

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(asdict(self), default=str, ensure_ascii=False)


class StructuredLogger:
    """
    Enhanced structured logger with comprehensive features

    Features:
    - JSON structured output
    - Automatic trace context injection
    - Performance metrics logging
    - Business event logging
    - Error tracking with stack traces
    - Correlation ID management
    """

    def __init__(
        self,
        name: str,
        service_name: str = "microservice",
        service_version: str = "1.0.0",
        environment: str = "production",
        namespace: str = "default",
        log_level: LogLevel = LogLevel.INFO,
        enable_console_output: bool = True,
        enable_file_output: bool = False,
        file_path: str | None = None,
        max_field_length: int = 1000,
    ):
        self.name = name
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment
        self.namespace = namespace
        self.max_field_length = max_field_length

        # Create underlying logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.value))

        # Clear existing handlers
        self.logger.handlers.clear()

        # Setup handlers
        if enable_console_output:
            self._setup_console_handler()

        if enable_file_output and file_path:
            self._setup_file_handler(file_path)

        # Context storage
        self._context_stack: builtins.list[LogContext] = []

        self.logger.info(f"Structured logger initialized for {service_name}")

    def _setup_console_handler(self):
        """Setup console handler with JSON formatter"""
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(self._create_json_formatter())
        self.logger.addHandler(handler)

    def _setup_file_handler(self, file_path: str):
        """Setup file handler with JSON formatter"""
        handler = logging.FileHandler(file_path)
        handler.setFormatter(self._create_json_formatter())
        self.logger.addHandler(handler)

    def _create_json_formatter(self):
        """Create JSON formatter"""
        return JsonFormatter(self)

    def _get_current_context(self) -> LogContext:
        """Get current logging context"""
        if self._context_stack:
            return self._context_stack[-1]

        # Create default context
        context = LogContext(
            service_name=self.service_name,
            service_version=self.service_version,
            environment=self.environment,
            namespace=self.namespace,
        )

        # Add trace context if available
        if OTEL_AVAILABLE:
            current_span = get_current_span()
            if current_span and current_span.get_span_context().is_valid:
                context.trace_id = format(current_span.get_span_context().trace_id, "032x")
                context.span_id = format(current_span.get_span_context().span_id, "016x")

        return context

    @contextmanager
    def context(self, **kwargs):
        """Context manager for temporary context"""
        current_context = self._get_current_context()
        new_context = LogContext(
            correlation_id=kwargs.get("correlation_id", current_context.correlation_id),
            trace_id=kwargs.get("trace_id", current_context.trace_id),
            span_id=kwargs.get("span_id", current_context.span_id),
            user_id=kwargs.get("user_id", current_context.user_id),
            session_id=kwargs.get("session_id", current_context.session_id),
            request_id=kwargs.get("request_id", current_context.request_id),
            service_name=current_context.service_name,
            service_version=current_context.service_version,
            environment=current_context.environment,
            namespace=current_context.namespace,
            custom_fields={
                **current_context.custom_fields,
                **kwargs.get("custom_fields", {}),
            },
        )

        self._context_stack.append(new_context)
        try:
            yield new_context
        finally:
            self._context_stack.pop()

    def _truncate_field(self, value: Any) -> Any:
        """Truncate field value if too long"""
        if isinstance(value, str) and len(value) > self.max_field_length:
            return value[: self.max_field_length] + "... [truncated]"
        return value

    def _create_log_entry(
        self,
        level: LogLevel,
        message: str,
        category: LogCategory,
        fields: builtins.dict[str, Any] | None = None,
        error: Exception | None = None,
        performance_data: builtins.dict[str, Any] | None = None,
        business_data: builtins.dict[str, Any] | None = None,
    ) -> StructuredLogEntry:
        """Create structured log entry"""
        context = self._get_current_context()

        # Process fields
        processed_fields = {}
        if fields:
            for key, value in fields.items():
                processed_fields[key] = self._truncate_field(value)

        # Process error information
        error_data = None
        if error:
            error_data = {
                "type": type(error).__name__,
                "message": str(error),
                "stack_trace": traceback.format_exc() if error.__traceback__ else None,
            }

        return StructuredLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level.value,
            message=message,
            category=category.value,
            service_name=self.service_name,
            context=context.to_dict(),
            fields=processed_fields,
            error=error_data,
            performance=performance_data,
            business=business_data,
        )

    def debug(
        self,
        message: str,
        category: LogCategory = LogCategory.APPLICATION,
        fields: builtins.dict[str, Any] | None = None,
        **kwargs,
    ):
        """Debug level logging"""
        log_entry = self._create_log_entry(LogLevel.DEBUG, message, category, fields, **kwargs)
        self.logger.debug(log_entry.to_json())

    def info(
        self,
        message: str,
        category: LogCategory = LogCategory.APPLICATION,
        fields: builtins.dict[str, Any] | None = None,
        **kwargs,
    ):
        """Info level logging"""
        log_entry = self._create_log_entry(LogLevel.INFO, message, category, fields, **kwargs)
        self.logger.info(log_entry.to_json())

    def warning(
        self,
        message: str,
        category: LogCategory = LogCategory.APPLICATION,
        fields: builtins.dict[str, Any] | None = None,
        **kwargs,
    ):
        """Warning level logging"""
        log_entry = self._create_log_entry(LogLevel.WARNING, message, category, fields, **kwargs)
        self.logger.warning(log_entry.to_json())

    def error(
        self,
        message: str,
        error: Exception | None = None,
        category: LogCategory = LogCategory.ERROR,
        fields: builtins.dict[str, Any] | None = None,
        **kwargs,
    ):
        """Error level logging"""
        log_entry = self._create_log_entry(
            LogLevel.ERROR, message, category, fields, error=error, **kwargs
        )
        self.logger.error(log_entry.to_json())

    def critical(
        self,
        message: str,
        error: Exception | None = None,
        category: LogCategory = LogCategory.ERROR,
        fields: builtins.dict[str, Any] | None = None,
        **kwargs,
    ):
        """Critical level logging"""
        log_entry = self._create_log_entry(
            LogLevel.CRITICAL, message, category, fields, error=error, **kwargs
        )
        self.logger.critical(log_entry.to_json())

    def security(
        self,
        message: str,
        security_event: str,
        user_id: str | None = None,
        source_ip: str | None = None,
        fields: builtins.dict[str, Any] | None = None,
    ):
        """Security event logging"""
        security_fields = {
            "security_event": security_event,
            **({"user_id": user_id} if user_id else {}),
            **({"source_ip": source_ip} if source_ip else {}),
            **(fields or {}),
        }

        log_entry = self._create_log_entry(
            LogLevel.WARNING, message, LogCategory.SECURITY, security_fields
        )
        self.logger.warning(log_entry.to_json())

    def performance(
        self,
        message: str,
        operation: str,
        duration_ms: float,
        fields: builtins.dict[str, Any] | None = None,
    ):
        """Performance logging"""
        performance_data = {
            "operation": operation,
            "duration_ms": duration_ms,
            "timestamp": time.time(),
        }

        log_entry = self._create_log_entry(
            LogLevel.INFO,
            message,
            LogCategory.PERFORMANCE,
            fields,
            performance_data=performance_data,
        )
        self.logger.info(log_entry.to_json())

    def business(
        self,
        message: str,
        event_type: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        amount: float | None = None,
        currency: str | None = None,
        fields: builtins.dict[str, Any] | None = None,
    ):
        """Business event logging"""
        business_data = {
            "event_type": event_type,
            **({"entity_type": entity_type} if entity_type else {}),
            **({"entity_id": entity_id} if entity_id else {}),
            **({"amount": amount} if amount is not None else {}),
            **({"currency": currency} if currency else {}),
        }

        log_entry = self._create_log_entry(
            LogLevel.INFO,
            message,
            LogCategory.BUSINESS,
            fields,
            business_data=business_data,
        )
        self.logger.info(log_entry.to_json())

    def audit(
        self,
        message: str,
        action: str,
        resource: str,
        user_id: str | None = None,
        success: bool = True,
        fields: builtins.dict[str, Any] | None = None,
    ):
        """Audit logging"""
        audit_fields = {
            "action": action,
            "resource": resource,
            "success": success,
            **({"user_id": user_id} if user_id else {}),
            **(fields or {}),
        }

        log_entry = self._create_log_entry(LogLevel.INFO, message, LogCategory.AUDIT, audit_fields)
        self.logger.info(log_entry.to_json())

    def access(
        self,
        message: str,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        user_id: str | None = None,
        source_ip: str | None = None,
        user_agent: str | None = None,
    ):
        """Access logging"""
        access_fields = {
            "http_method": method,
            "http_path": path,
            "http_status": status_code,
            "response_time_ms": duration_ms,
            **({"user_id": user_id} if user_id else {}),
            **({"source_ip": source_ip} if source_ip else {}),
            **({"user_agent": user_agent} if user_agent else {}),
        }

        log_entry = self._create_log_entry(
            LogLevel.INFO, message, LogCategory.ACCESS, access_fields
        )
        self.logger.info(log_entry.to_json())


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""

    def __init__(self, structured_logger: StructuredLogger):
        super().__init__()
        self.structured_logger = structured_logger

    def format(self, record):
        # The record message should already be JSON from StructuredLogger
        return record.getMessage()


class LoggingMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for request/response logging"""

    def __init__(self, app, logger: StructuredLogger):
        super().__init__(app)
        self.logger = logger

    async def dispatch(self, request: Request, call_next):
        # Generate request ID
        request_id = str(uuid.uuid4())
        start_time = time.time()

        # Extract user information if available
        user_id = getattr(request.state, "user_id", None)

        # Create context for this request
        with self.logger.context(
            request_id=request_id,
            user_id=user_id,
            custom_fields={
                "request_method": request.method,
                "request_path": str(request.url.path),
                "request_query": str(request.url.query) if request.url.query else None,
            },
        ):
            # Log request
            self.logger.access(
                f"Request started: {request.method} {request.url.path}",
                method=request.method,
                path=str(request.url.path),
                status_code=0,  # Not yet available
                duration_ms=0,  # Not yet available
                source_ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )

            try:
                # Process request
                response = await call_next(request)

                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Log response
                self.logger.access(
                    f"Request completed: {request.method} {request.url.path} -> {response.status_code}",
                    method=request.method,
                    path=str(request.url.path),
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    user_id=user_id,
                    source_ip=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                )

                return response

            except Exception as e:
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Log error
                self.logger.error(
                    f"Request failed: {request.method} {request.url.path}",
                    error=e,
                    fields={
                        "request_method": request.method,
                        "request_path": str(request.url.path),
                        "duration_ms": duration_ms,
                    },
                )

                raise


@contextmanager
def performance_logger(logger: StructuredLogger, operation: str, **fields):
    """Context manager for performance logging"""
    start_time = time.time()

    logger.debug(f"Starting operation: {operation}", fields=fields)

    try:
        yield
        duration_ms = (time.time() - start_time) * 1000
        logger.performance(
            f"Operation completed: {operation}",
            operation=operation,
            duration_ms=duration_ms,
            fields=fields,
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Operation failed: {operation}",
            error=e,
            fields={**fields, "duration_ms": duration_ms},
        )
        raise


# Factory functions
def create_structured_logger(
    service_name: str,
    environment: str = "production",
    log_level: LogLevel = LogLevel.INFO,
    **kwargs,
) -> StructuredLogger:
    """Create a structured logger with default configuration"""
    return StructuredLogger(
        name=service_name,
        service_name=service_name,
        environment=environment,
        log_level=log_level,
        **kwargs,
    )


def setup_fastapi_logging(app, service_name: str, **logger_kwargs) -> StructuredLogger:
    """Setup FastAPI with structured logging middleware"""
    logger = create_structured_logger(service_name, **logger_kwargs)
    app.add_middleware(LoggingMiddleware, logger=logger)
    return logger
