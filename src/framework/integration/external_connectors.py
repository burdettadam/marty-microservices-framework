"""
External System Connectors and Enterprise Service Bus for Marty Microservices Framework

This module implements comprehensive external system integration patterns including
protocol adapters, legacy system connectors, enterprise service bus patterns,
and external API integrations.
"""

import asyncio
import ftplib
import hashlib
import json
import logging
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TypeVar, Union
from urllib.parse import urljoin, urlparse

import aiofiles

# For external system operations
import aiohttp
import paramiko  # For SFTP
import pyodbc  # For database connections
import requests
import yaml


class ConnectorType(Enum):
    """External connector types."""

    REST_API = "rest_api"
    SOAP_API = "soap_api"
    DATABASE = "database"
    FILE_SYSTEM = "file_system"
    FTP = "ftp"
    SFTP = "sftp"
    LEGACY_MAINFRAME = "legacy_mainframe"
    MESSAGE_QUEUE = "message_queue"
    WEBHOOK = "webhook"
    GRAPHQL = "graphql"
    CUSTOM = "custom"


class IntegrationPattern(Enum):
    """Integration patterns."""

    REQUEST_RESPONSE = "request_response"
    FIRE_AND_FORGET = "fire_and_forget"
    POLLING = "polling"
    STREAMING = "streaming"
    BATCH_PROCESSING = "batch_processing"
    EVENT_SUBSCRIPTION = "event_subscription"
    WEBHOOK_CALLBACK = "webhook_callback"


class DataFormat(Enum):
    """Data formats for integration."""

    JSON = "json"
    XML = "xml"
    CSV = "csv"
    FIXED_WIDTH = "fixed_width"
    DELIMITED = "delimited"
    BINARY = "binary"
    YAML = "yaml"
    AVRO = "avro"
    PROTOBUF = "protobuf"


class TransformationType(Enum):
    """Data transformation types."""

    MAPPING = "mapping"
    FILTERING = "filtering"
    AGGREGATION = "aggregation"
    ENRICHMENT = "enrichment"
    VALIDATION = "validation"
    FORMAT_CONVERSION = "format_conversion"
    PROTOCOL_ADAPTATION = "protocol_adaptation"


@dataclass
class ExternalSystemConfig:
    """Configuration for external system connection."""

    system_id: str
    name: str
    connector_type: ConnectorType
    endpoint_url: str

    # Authentication
    auth_type: str = "none"  # none, basic, bearer, oauth2, api_key, certificate
    credentials: Dict[str, str] = field(default_factory=dict)

    # Connection settings
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: int = 5

    # Protocol specific settings
    protocol_settings: Dict[str, Any] = field(default_factory=dict)

    # Data format
    input_format: DataFormat = DataFormat.JSON
    output_format: DataFormat = DataFormat.JSON

    # Health checking
    health_check_enabled: bool = True
    health_check_endpoint: Optional[str] = None
    health_check_interval: int = 60

    # Rate limiting
    rate_limit: Optional[int] = None  # requests per second

    # Circuit breaker
    circuit_breaker_enabled: bool = True
    failure_threshold: int = 5
    recovery_timeout: int = 60

    # Metadata
    version: str = "1.0.0"
    description: str = ""
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class IntegrationRequest:
    """Request for external system integration."""

    request_id: str
    system_id: str
    operation: str
    data: Any

    # Request configuration
    pattern: IntegrationPattern = IntegrationPattern.REQUEST_RESPONSE
    timeout: Optional[int] = None
    retry_policy: Optional[Dict[str, Any]] = None

    # Transformation
    input_transformation: Optional[str] = None
    output_transformation: Optional[str] = None

    # Metadata
    correlation_id: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class IntegrationResponse:
    """Response from external system integration."""

    request_id: str
    success: bool
    data: Any

    # Response metadata
    status_code: Optional[int] = None
    headers: Dict[str, str] = field(default_factory=dict)

    # Error information
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    # Performance metrics
    latency_ms: Optional[float] = None
    retry_count: int = 0

    # Timestamps
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DataTransformation:
    """Data transformation definition."""

    transformation_id: str
    name: str
    transformation_type: TransformationType

    # Transformation logic
    source_schema: Optional[Dict[str, Any]] = None
    target_schema: Optional[Dict[str, Any]] = None
    mapping_rules: List[Dict[str, Any]] = field(default_factory=list)

    # Transformation code
    transformation_script: Optional[str] = None

    # Validation rules
    validation_rules: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    description: str = ""
    version: str = "1.0.0"


class ExternalSystemConnector(ABC):
    """Abstract base class for external system connectors."""

    def __init__(self, config: ExternalSystemConfig):
        """Initialize connector with configuration."""
        self.config = config
        self.connected = False
        self.circuit_breaker_state = "closed"
        self.failure_count = 0
        self.last_failure_time = None

        # Metrics
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_latency": 0.0,
        }

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to external system."""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from external system."""
        pass

    @abstractmethod
    async def execute_request(self, request: IntegrationRequest) -> IntegrationResponse:
        """Execute request against external system."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check health of external system."""
        pass

    def is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is open."""
        if self.circuit_breaker_state == "open":
            if self.last_failure_time:
                elapsed = time.time() - self.last_failure_time
                if elapsed > self.config.recovery_timeout:
                    self.circuit_breaker_state = "half_open"
                    return False
            return True
        return False

    def record_success(self):
        """Record successful request."""
        self.failure_count = 0
        if self.circuit_breaker_state == "half_open":
            self.circuit_breaker_state = "closed"

        self.metrics["successful_requests"] += 1

    def record_failure(self):
        """Record failed request."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.config.failure_threshold:
            self.circuit_breaker_state = "open"

        self.metrics["failed_requests"] += 1


class RESTAPIConnector(ExternalSystemConnector):
    """REST API connector implementation."""

    def __init__(self, config: ExternalSystemConfig):
        """Initialize REST API connector."""
        super().__init__(config)
        self.session = None

    async def connect(self) -> bool:
        """Establish HTTP session."""
        try:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
            self.connected = True

            logging.info(f"Connected to REST API: {self.config.endpoint_url}")
            return True

        except Exception as e:
            logging.error(f"Failed to connect to REST API: {e}")
            return False

    async def disconnect(self) -> bool:
        """Close HTTP session."""
        try:
            if self.session:
                await self.session.close()

            self.connected = False
            logging.info(f"Disconnected from REST API: {self.config.endpoint_url}")
            return True

        except Exception as e:
            logging.error(f"Failed to disconnect from REST API: {e}")
            return False

    async def execute_request(self, request: IntegrationRequest) -> IntegrationResponse:
        """Execute REST API request."""
        start_time = time.time()

        try:
            # Check circuit breaker
            if self.is_circuit_breaker_open():
                raise Exception("Circuit breaker is open")

            # Prepare request
            url = urljoin(self.config.endpoint_url, request.operation)
            headers = self._prepare_headers(request.headers)

            # Execute HTTP request
            method = request.data.get("method", "GET").upper()
            request_data = request.data.get("body")
            params = request.data.get("params")

            async with self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=request_data if isinstance(request_data, dict) else None,
                data=request_data if isinstance(request_data, (str, bytes)) else None,
                params=params,
            ) as response:
                response_data = await response.text()

                # Try to parse as JSON
                try:
                    if response.content_type == "application/json":
                        response_data = await response.json()
                except:
                    pass  # Keep as text

                latency = (time.time() - start_time) * 1000

                # Record metrics
                self.metrics["total_requests"] += 1
                self.metrics["total_latency"] += latency

                if 200 <= response.status < 300:
                    self.record_success()

                    return IntegrationResponse(
                        request_id=request.request_id,
                        success=True,
                        data=response_data,
                        status_code=response.status,
                        headers=dict(response.headers),
                        latency_ms=latency,
                    )
                else:
                    self.record_failure()

                    return IntegrationResponse(
                        request_id=request.request_id,
                        success=False,
                        data=response_data,
                        status_code=response.status,
                        error_code=str(response.status),
                        error_message=f"HTTP {response.status}: {response.reason}",
                        latency_ms=latency,
                    )

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            self.record_failure()

            return IntegrationResponse(
                request_id=request.request_id,
                success=False,
                data=None,
                error_message=str(e),
                latency_ms=latency,
            )

    def _prepare_headers(self, request_headers: Dict[str, str]) -> Dict[str, str]:
        """Prepare HTTP headers with authentication."""
        headers = request_headers.copy()

        # Add authentication headers
        auth_type = self.config.auth_type
        credentials = self.config.credentials

        if auth_type == "bearer":
            token = credentials.get("token")
            if token:
                headers["Authorization"] = f"Bearer {token}"

        elif auth_type == "api_key":
            api_key = credentials.get("api_key")
            key_header = credentials.get("key_header", "X-API-Key")
            if api_key:
                headers[key_header] = api_key

        elif auth_type == "basic":
            username = credentials.get("username")
            password = credentials.get("password")
            if username and password:
                import base64

                auth_string = base64.b64encode(
                    f"{username}:{password}".encode()
                ).decode()
                headers["Authorization"] = f"Basic {auth_string}"

        # Set default content type
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        return headers

    async def health_check(self) -> bool:
        """Check REST API health."""
        try:
            health_endpoint = self.config.health_check_endpoint or "/health"
            url = urljoin(self.config.endpoint_url, health_endpoint)

            async with self.session.get(url) as response:
                return 200 <= response.status < 300

        except Exception as e:
            logging.error(f"REST API health check failed: {e}")
            return False


class DatabaseConnector(ExternalSystemConnector):
    """Database connector implementation."""

    def __init__(self, config: ExternalSystemConfig):
        """Initialize database connector."""
        super().__init__(config)
        self.connection = None
        self.connection_pool = None

    async def connect(self) -> bool:
        """Establish database connection."""
        try:
            # Parse connection string
            connection_string = self.config.endpoint_url

            # Create connection (simplified - would use async database drivers in production)
            self.connection = pyodbc.connect(connection_string)
            self.connected = True

            logging.info(f"Connected to database: {self.config.name}")
            return True

        except Exception as e:
            logging.error(f"Failed to connect to database: {e}")
            return False

    async def disconnect(self) -> bool:
        """Close database connection."""
        try:
            if self.connection:
                self.connection.close()

            self.connected = False
            logging.info(f"Disconnected from database: {self.config.name}")
            return True

        except Exception as e:
            logging.error(f"Failed to disconnect from database: {e}")
            return False

    async def execute_request(self, request: IntegrationRequest) -> IntegrationResponse:
        """Execute database request."""
        start_time = time.time()

        try:
            # Check circuit breaker
            if self.is_circuit_breaker_open():
                raise Exception("Circuit breaker is open")

            cursor = self.connection.cursor()

            # Execute based on operation type
            operation_type = request.operation.lower()

            if operation_type == "query":
                # SELECT query
                sql = request.data.get("sql")
                params = request.data.get("params", [])

                cursor.execute(sql, params)
                columns = [column[0] for column in cursor.description]
                rows = cursor.fetchall()

                # Convert to list of dictionaries
                result = [dict(zip(columns, row)) for row in rows]

            elif operation_type in ["insert", "update", "delete"]:
                # DML operations
                sql = request.data.get("sql")
                params = request.data.get("params", [])

                cursor.execute(sql, params)
                self.connection.commit()

                result = {"affected_rows": cursor.rowcount}

            elif operation_type == "procedure":
                # Stored procedure call
                procedure_name = request.data.get("procedure_name")
                params = request.data.get("params", [])

                cursor.execute(
                    f"EXEC {procedure_name} {','.join(['?' for _ in params])}", params
                )

                # Get results
                if cursor.description:
                    columns = [column[0] for column in cursor.description]
                    rows = cursor.fetchall()
                    result = [dict(zip(columns, row)) for row in rows]
                else:
                    result = {"procedure_executed": True}

            else:
                raise ValueError(f"Unsupported operation: {operation_type}")

            cursor.close()

            latency = (time.time() - start_time) * 1000
            self.record_success()

            return IntegrationResponse(
                request_id=request.request_id,
                success=True,
                data=result,
                latency_ms=latency,
            )

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            self.record_failure()

            return IntegrationResponse(
                request_id=request.request_id,
                success=False,
                data=None,
                error_message=str(e),
                latency_ms=latency,
            )

    async def health_check(self) -> bool:
        """Check database health."""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            return True

        except Exception as e:
            logging.error(f"Database health check failed: {e}")
            return False


class FileSystemConnector(ExternalSystemConnector):
    """File system connector implementation."""

    def __init__(self, config: ExternalSystemConfig):
        """Initialize file system connector."""
        super().__init__(config)
        self.base_path = config.endpoint_url

    async def connect(self) -> bool:
        """Validate file system access."""
        try:
            import os

            if os.path.exists(self.base_path) and os.access(self.base_path, os.R_OK):
                self.connected = True
                logging.info(f"Connected to file system: {self.base_path}")
                return True
            else:
                logging.error(f"Cannot access file system path: {self.base_path}")
                return False

        except Exception as e:
            logging.error(f"File system connection error: {e}")
            return False

    async def disconnect(self) -> bool:
        """Disconnect from file system."""
        self.connected = False
        return True

    async def execute_request(self, request: IntegrationRequest) -> IntegrationResponse:
        """Execute file system request."""
        start_time = time.time()

        try:
            # Check circuit breaker
            if self.is_circuit_breaker_open():
                raise Exception("Circuit breaker is open")

            operation = request.operation.lower()
            file_path = request.data.get("file_path")
            full_path = f"{self.base_path}/{file_path}".replace("//", "/")

            if operation == "read":
                # Read file
                async with aiofiles.open(full_path, "r") as file:
                    content = await file.read()

                # Parse content based on format
                if file_path.endswith(".json"):
                    content = json.loads(content)
                elif file_path.endswith(".yaml") or file_path.endswith(".yml"):
                    content = yaml.safe_load(content)

                result = {"content": content, "file_path": file_path}

            elif operation == "write":
                # Write file
                content = request.data.get("content")

                # Format content
                if file_path.endswith(".json"):
                    content = json.dumps(content, indent=2)
                elif file_path.endswith(".yaml") or file_path.endswith(".yml"):
                    content = yaml.dump(content, default_flow_style=False)

                async with aiofiles.open(full_path, "w") as file:
                    await file.write(content)

                result = {"written": True, "file_path": file_path}

            elif operation == "list":
                # List directory contents
                import os

                directory = request.data.get("directory", "")
                full_dir_path = f"{self.base_path}/{directory}".replace("//", "/")

                files = []
                for item in os.listdir(full_dir_path):
                    item_path = os.path.join(full_dir_path, item)
                    files.append(
                        {
                            "name": item,
                            "is_directory": os.path.isdir(item_path),
                            "size": os.path.getsize(item_path)
                            if os.path.isfile(item_path)
                            else None,
                            "modified": datetime.fromtimestamp(
                                os.path.getmtime(item_path)
                            ).isoformat(),
                        }
                    )

                result = {"files": files, "directory": directory}

            elif operation == "delete":
                # Delete file
                import os

                os.remove(full_path)
                result = {"deleted": True, "file_path": file_path}

            else:
                raise ValueError(f"Unsupported operation: {operation}")

            latency = (time.time() - start_time) * 1000
            self.record_success()

            return IntegrationResponse(
                request_id=request.request_id,
                success=True,
                data=result,
                latency_ms=latency,
            )

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            self.record_failure()

            return IntegrationResponse(
                request_id=request.request_id,
                success=False,
                data=None,
                error_message=str(e),
                latency_ms=latency,
            )

    async def health_check(self) -> bool:
        """Check file system health."""
        try:
            import os

            return os.path.exists(self.base_path) and os.access(self.base_path, os.R_OK)

        except Exception as e:
            logging.error(f"File system health check failed: {e}")
            return False


class DataTransformationEngine:
    """Engine for data transformations between systems."""

    def __init__(self):
        """Initialize transformation engine."""
        self.transformations: Dict[str, DataTransformation] = {}
        self.custom_transformers: Dict[str, Callable] = {}

        # Built-in transformers
        self.built_in_transformers = {
            "json_to_xml": self._json_to_xml,
            "xml_to_json": self._xml_to_json,
            "csv_to_json": self._csv_to_json,
            "json_to_csv": self._json_to_csv,
            "flatten_json": self._flatten_json,
            "unflatten_json": self._unflatten_json,
        }

    def register_transformation(self, transformation: DataTransformation) -> bool:
        """Register data transformation."""
        try:
            self.transformations[transformation.transformation_id] = transformation
            logging.info(f"Registered transformation: {transformation.name}")
            return True

        except Exception as e:
            logging.error(f"Failed to register transformation: {e}")
            return False

    def register_custom_transformer(self, name: str, transformer: Callable) -> bool:
        """Register custom transformer function."""
        try:
            self.custom_transformers[name] = transformer
            logging.info(f"Registered custom transformer: {name}")
            return True

        except Exception as e:
            logging.error(f"Failed to register custom transformer: {e}")
            return False

    def transform_data(self, data: Any, transformation_id: str) -> Any:
        """Apply transformation to data."""
        transformation = self.transformations.get(transformation_id)
        if not transformation:
            raise ValueError(f"Transformation not found: {transformation_id}")

        try:
            # Apply transformation based on type
            if transformation.transformation_type == TransformationType.MAPPING:
                return self._apply_mapping_transformation(data, transformation)

            elif transformation.transformation_type == TransformationType.FILTERING:
                return self._apply_filtering_transformation(data, transformation)

            elif (
                transformation.transformation_type
                == TransformationType.FORMAT_CONVERSION
            ):
                return self._apply_format_conversion(data, transformation)

            elif transformation.transformation_type == TransformationType.VALIDATION:
                return self._apply_validation(data, transformation)

            elif transformation.transformation_type == TransformationType.ENRICHMENT:
                return self._apply_enrichment(data, transformation)

            else:
                # Execute custom transformation script
                if transformation.transformation_script:
                    return self._execute_transformation_script(
                        data, transformation.transformation_script
                    )
                else:
                    return data

        except Exception as e:
            logging.error(f"Transformation error: {e}")
            raise

    def _apply_mapping_transformation(
        self, data: Any, transformation: DataTransformation
    ) -> Any:
        """Apply field mapping transformation."""
        if not isinstance(data, dict):
            return data

        result = {}

        for rule in transformation.mapping_rules:
            source_field = rule.get("source_field")
            target_field = rule.get("target_field")
            default_value = rule.get("default_value")

            if source_field in data:
                result[target_field] = data[source_field]
            elif default_value is not None:
                result[target_field] = default_value

        return result

    def _apply_filtering_transformation(
        self, data: Any, transformation: DataTransformation
    ) -> Any:
        """Apply filtering transformation."""
        if isinstance(data, list):
            # Filter array items
            filtered_items = []

            for item in data:
                if self._matches_filter_conditions(item, transformation.mapping_rules):
                    filtered_items.append(item)

            return filtered_items

        elif isinstance(data, dict):
            # Filter object fields
            if self._matches_filter_conditions(data, transformation.mapping_rules):
                return data
            else:
                return None

        return data

    def _matches_filter_conditions(
        self, item: Dict[str, Any], conditions: List[Dict[str, Any]]
    ) -> bool:
        """Check if item matches filter conditions."""
        for condition in conditions:
            field = condition.get("field")
            operator = condition.get("operator", "eq")
            value = condition.get("value")

            item_value = item.get(field)

            if operator == "eq" and item_value != value:
                return False
            elif operator == "ne" and item_value == value:
                return False
            elif operator == "gt" and (item_value is None or item_value <= value):
                return False
            elif operator == "lt" and (item_value is None or item_value >= value):
                return False
            elif operator == "contains" and (
                item_value is None or value not in str(item_value)
            ):
                return False
            elif operator == "in" and (item_value is None or item_value not in value):
                return False

        return True

    def _apply_format_conversion(
        self, data: Any, transformation: DataTransformation
    ) -> Any:
        """Apply format conversion transformation."""
        source_format = (
            transformation.source_schema.get("format")
            if transformation.source_schema
            else "json"
        )
        target_format = (
            transformation.target_schema.get("format")
            if transformation.target_schema
            else "json"
        )

        converter_name = f"{source_format}_to_{target_format}"

        if converter_name in self.built_in_transformers:
            return self.built_in_transformers[converter_name](data)
        elif converter_name in self.custom_transformers:
            return self.custom_transformers[converter_name](data)
        else:
            return data

    def _apply_validation(self, data: Any, transformation: DataTransformation) -> Any:
        """Apply validation transformation."""
        errors = []

        for rule in transformation.validation_rules:
            field = rule.get("field")
            rule_type = rule.get("type")
            parameters = rule.get("parameters", {})

            if isinstance(data, dict) and field in data:
                field_value = data[field]

                if rule_type == "required" and field_value is None:
                    errors.append(f"Field {field} is required")

                elif rule_type == "type" and not isinstance(
                    field_value, parameters.get("expected_type")
                ):
                    errors.append(
                        f"Field {field} must be of type {parameters.get('expected_type')}"
                    )

                elif rule_type == "range" and isinstance(field_value, (int, float)):
                    min_val = parameters.get("min")
                    max_val = parameters.get("max")

                    if min_val is not None and field_value < min_val:
                        errors.append(f"Field {field} must be >= {min_val}")

                    if max_val is not None and field_value > max_val:
                        errors.append(f"Field {field} must be <= {max_val}")

                elif rule_type == "pattern" and isinstance(field_value, str):
                    import re

                    pattern = parameters.get("pattern")
                    if pattern and not re.match(pattern, field_value):
                        errors.append(f"Field {field} does not match pattern {pattern}")

        if errors:
            raise ValueError(f"Validation errors: {'; '.join(errors)}")

        return data

    def _apply_enrichment(self, data: Any, transformation: DataTransformation) -> Any:
        """Apply data enrichment transformation."""
        if not isinstance(data, dict):
            return data

        enriched_data = data.copy()

        for rule in transformation.mapping_rules:
            enrichment_type = rule.get("type")

            if enrichment_type == "add_timestamp":
                enriched_data["enriched_at"] = datetime.now(timezone.utc).isoformat()

            elif enrichment_type == "add_field":
                field_name = rule.get("field_name")
                field_value = rule.get("field_value")
                enriched_data[field_name] = field_value

            elif enrichment_type == "lookup":
                # Placeholder for external lookup
                lookup_field = rule.get("lookup_field")
                lookup_value = data.get(lookup_field)

                if lookup_value:
                    # Simulate lookup result
                    enriched_data[
                        f"{lookup_field}_enriched"
                    ] = f"enriched_{lookup_value}"

        return enriched_data

    def _execute_transformation_script(self, data: Any, script: str) -> Any:
        """Execute transformation script."""
        # This is a simplified implementation
        # In production, would use a secure scripting engine

        local_vars = {"data": data, "result": data}

        try:
            exec(script, {"json": json, "datetime": datetime}, local_vars)
            return local_vars.get("result", data)
        except Exception as e:
            logging.error(f"Transformation script error: {e}")
            raise

    # Built-in transformation functions
    def _json_to_xml(self, data: Any) -> str:
        """Convert JSON to XML."""

        def dict_to_xml(d, root_name="root"):
            xml_str = f"<{root_name}>"

            for key, value in d.items():
                if isinstance(value, dict):
                    xml_str += dict_to_xml(value, key)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            xml_str += dict_to_xml(item, key)
                        else:
                            xml_str += f"<{key}>{item}</{key}>"
                else:
                    xml_str += f"<{key}>{value}</{key}>"

            xml_str += f"</{root_name}>"
            return xml_str

        if isinstance(data, dict):
            return dict_to_xml(data)
        else:
            return f"<data>{data}</data>"

    def _xml_to_json(self, xml_data: str) -> Dict[str, Any]:
        """Convert XML to JSON."""
        try:
            root = ET.fromstring(xml_data)

            def xml_to_dict(element):
                result = {}

                # Add attributes
                if element.attrib:
                    result.update(element.attrib)

                # Add text content
                if element.text and element.text.strip():
                    if element.attrib or len(element) > 0:
                        result["_text"] = element.text.strip()
                    else:
                        return element.text.strip()

                # Add child elements
                for child in element:
                    child_data = xml_to_dict(child)

                    if child.tag in result:
                        # Convert to list if multiple elements with same tag
                        if not isinstance(result[child.tag], list):
                            result[child.tag] = [result[child.tag]]
                        result[child.tag].append(child_data)
                    else:
                        result[child.tag] = child_data

                return result

            return {root.tag: xml_to_dict(root)}

        except ET.ParseError as e:
            logging.error(f"XML parsing error: {e}")
            return {"error": f"Invalid XML: {e}"}

    def _csv_to_json(self, csv_data: str) -> List[Dict[str, Any]]:
        """Convert CSV to JSON."""
        import csv
        import io

        reader = csv.DictReader(io.StringIO(csv_data))
        return [row for row in reader]

    def _json_to_csv(self, json_data: List[Dict[str, Any]]) -> str:
        """Convert JSON to CSV."""
        import csv
        import io

        if not json_data:
            return ""

        output = io.StringIO()

        # Get all unique field names
        fieldnames = set()
        for row in json_data:
            fieldnames.update(row.keys())

        fieldnames = sorted(fieldnames)

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for row in json_data:
            writer.writerow(row)

        return output.getvalue()

    def _flatten_json(
        self, data: Dict[str, Any], separator: str = "."
    ) -> Dict[str, Any]:
        """Flatten nested JSON object."""

        def _flatten(obj, parent_key=""):
            items = []

            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_key = f"{parent_key}{separator}{key}" if parent_key else key
                    items.extend(_flatten(value, new_key).items())
            elif isinstance(obj, list):
                for i, value in enumerate(obj):
                    new_key = f"{parent_key}{separator}{i}" if parent_key else str(i)
                    items.extend(_flatten(value, new_key).items())
            else:
                return {parent_key: obj}

            return dict(items)

        return _flatten(data)

    def _unflatten_json(
        self, data: Dict[str, Any], separator: str = "."
    ) -> Dict[str, Any]:
        """Unflatten flattened JSON object."""
        result = {}

        for key, value in data.items():
            keys = key.split(separator)
            current = result

            for k in keys[:-1]:
                if k.isdigit():
                    k = int(k)
                    if not isinstance(current, list):
                        current = []

                    # Extend list if necessary
                    while len(current) <= k:
                        current.append({})

                    current = current[k]
                else:
                    if k not in current:
                        current[k] = {}
                    current = current[k]

            final_key = keys[-1]
            if final_key.isdigit():
                final_key = int(final_key)
                if not isinstance(current, list):
                    current = []

                while len(current) <= final_key:
                    current.append(None)

                current[final_key] = value
            else:
                current[final_key] = value

        return result


class ExternalSystemManager:
    """Manages external system connectors and integrations."""

    def __init__(self):
        """Initialize external system manager."""
        self.connectors: Dict[str, ExternalSystemConnector] = {}
        self.connector_factories: Dict[ConnectorType, type] = {
            ConnectorType.REST_API: RESTAPIConnector,
            ConnectorType.DATABASE: DatabaseConnector,
            ConnectorType.FILE_SYSTEM: FileSystemConnector,
        }

        self.transformation_engine = DataTransformationEngine()

        # Health monitoring
        self.health_check_tasks: Dict[str, asyncio.Task] = {}

        # Request tracking
        self.active_requests: Dict[str, IntegrationRequest] = {}

        # Metrics
        self.metrics: Dict[str, Any] = defaultdict(int)

        # Thread safety
        self._lock = threading.RLock()

    def register_connector_factory(
        self, connector_type: ConnectorType, factory_class: type
    ):
        """Register connector factory for custom connector types."""
        self.connector_factories[connector_type] = factory_class
        logging.info(f"Registered connector factory: {connector_type}")

    async def add_external_system(self, config: ExternalSystemConfig) -> bool:
        """Add external system configuration."""
        try:
            # Create connector instance
            factory_class = self.connector_factories.get(config.connector_type)
            if not factory_class:
                raise ValueError(f"Unsupported connector type: {config.connector_type}")

            connector = factory_class(config)

            # Connect to system
            success = await connector.connect()
            if not success:
                return False

            with self._lock:
                self.connectors[config.system_id] = connector

            # Start health monitoring
            if config.health_check_enabled:
                await self._start_health_monitoring(config.system_id)

            logging.info(f"Added external system: {config.name}")
            return True

        except Exception as e:
            logging.error(f"Failed to add external system: {e}")
            return False

    async def remove_external_system(self, system_id: str) -> bool:
        """Remove external system."""
        try:
            with self._lock:
                connector = self.connectors.get(system_id)
                if not connector:
                    return False

                # Disconnect
                await connector.disconnect()

                # Remove from registry
                del self.connectors[system_id]

            # Stop health monitoring
            await self._stop_health_monitoring(system_id)

            logging.info(f"Removed external system: {system_id}")
            return True

        except Exception as e:
            logging.error(f"Failed to remove external system: {e}")
            return False

    async def execute_integration_request(
        self, request: IntegrationRequest
    ) -> IntegrationResponse:
        """Execute integration request."""
        try:
            # Track request
            self.active_requests[request.request_id] = request
            self.metrics["total_requests"] += 1

            # Get connector
            connector = self.connectors.get(request.system_id)
            if not connector:
                raise ValueError(f"System not found: {request.system_id}")

            # Apply input transformation
            if request.input_transformation:
                request.data = self.transformation_engine.transform_data(
                    request.data, request.input_transformation
                )

            # Execute request
            response = await connector.execute_request(request)

            # Apply output transformation
            if request.output_transformation and response.success:
                response.data = self.transformation_engine.transform_data(
                    response.data, request.output_transformation
                )

            # Update metrics
            if response.success:
                self.metrics["successful_requests"] += 1
            else:
                self.metrics["failed_requests"] += 1

            return response

        except Exception as e:
            self.metrics["failed_requests"] += 1

            return IntegrationResponse(
                request_id=request.request_id,
                success=False,
                data=None,
                error_message=str(e),
            )

        finally:
            # Clean up request tracking
            self.active_requests.pop(request.request_id, None)

    async def _start_health_monitoring(self, system_id: str):
        """Start health monitoring for system."""
        connector = self.connectors.get(system_id)
        if not connector:
            return

        task = asyncio.create_task(self._health_monitor_loop(system_id))
        self.health_check_tasks[system_id] = task

    async def _stop_health_monitoring(self, system_id: str):
        """Stop health monitoring for system."""
        if system_id in self.health_check_tasks:
            task = self.health_check_tasks[system_id]
            task.cancel()
            del self.health_check_tasks[system_id]

    async def _health_monitor_loop(self, system_id: str):
        """Health monitoring loop."""
        connector = self.connectors.get(system_id)
        if not connector:
            return

        while True:
            try:
                healthy = await connector.health_check()

                if healthy:
                    logging.debug(f"Health check passed for system: {system_id}")
                else:
                    logging.warning(f"Health check failed for system: {system_id}")

                await asyncio.sleep(connector.config.health_check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Health monitor error for {system_id}: {e}")
                await asyncio.sleep(connector.config.health_check_interval)

    def get_system_status(self, system_id: str) -> Optional[Dict[str, Any]]:
        """Get status of external system."""
        connector = self.connectors.get(system_id)
        if not connector:
            return None

        return {
            "system_id": system_id,
            "connected": connector.connected,
            "circuit_breaker_state": connector.circuit_breaker_state,
            "failure_count": connector.failure_count,
            "metrics": connector.metrics,
        }

    def get_manager_status(self) -> Dict[str, Any]:
        """Get manager status and metrics."""
        with self._lock:
            connected_systems = sum(1 for c in self.connectors.values() if c.connected)

            return {
                "total_systems": len(self.connectors),
                "connected_systems": connected_systems,
                "active_requests": len(self.active_requests),
                "health_monitors": len(self.health_check_tasks),
                "metrics": dict(self.metrics),
            }


def create_external_integration_platform() -> Dict[str, Any]:
    """Create external integration platform."""
    manager = ExternalSystemManager()
    transformation_engine = DataTransformationEngine()

    return {"manager": manager, "transformation_engine": transformation_engine}
