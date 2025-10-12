"""
External System Connectors - Compatibility Layer

DEPRECATED: This is a compatibility shim that imports from the decomposed package.
Please import directly from 'framework.integration.external_connectors' package instead.

New import path: from framework.integration.external_connectors import ConnectorType, ...

Components migrated to decomposed package:
- ConnectorType, DataFormat, IntegrationPattern, TransformationType (enums)
- ExternalSystemConfig, IntegrationRequest, IntegrationResponse, DataTransformation (config)
- ExternalSystemConnector (base)
- DataTransformationEngine (transformation)
- RESTAPIConnector (connectors.rest_api)

Components still in this file (pending migration):
- DatabaseConnector
- FileSystemConnector
- ExternalSystemManager
- create_external_integration_platform function
"""

import warnings

# Import from decomposed package for backward compatibility
from .external_connectors import (
    ConnectorType,
    DataTransformation,
    ExternalSystemConfig,
    ExternalSystemConnector,
    IntegrationRequest,
    IntegrationResponse,
    TransformationType,
)

# Import specific connectors
from .external_connectors.connectors.rest_api import RESTAPIConnector

# Issue deprecation warning
warnings.warn(
    "Importing from framework.integration.external_connectors.py is deprecated. "
    "Please import directly from 'framework.integration.external_connectors' package.",
    DeprecationWarning,
    stacklevel=2
)

# Components that still need to be migrated to decomposed package
import asyncio
import builtins
import json
import logging
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import aiofiles
import pyodbc  # For database connections
import yaml
from defusedxml import ElementTree as ET

# Note: The following classes have been migrated to the decomposed package:
# - ConnectorType, DataFormat, IntegrationPattern, TransformationType (enums)
# - ExternalSystemConfig, IntegrationRequest, IntegrationResponse, DataTransformation (config classes)
# - ExternalSystemConnector (base class)
# - RESTAPIConnector (REST connector)
# - DataTransformationEngine (transformation engine)
#
# They are imported above from the decomposed package for backward compatibility.

# ============================================================================
# COMPONENTS STILL REQUIRING MIGRATION
# ============================================================================
# The following components are still in this file and should be migrated
# to the decomposed package structure in future updates:


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
            logging.exception(f"Failed to connect to database: {e}")
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
            logging.exception(f"Failed to disconnect from database: {e}")
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
                result = [dict(zip(columns, row, strict=False)) for row in rows]

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
                    result = [dict(zip(columns, row, strict=False)) for row in rows]
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
            logging.exception(f"Database health check failed: {e}")
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
            logging.error(f"Cannot access file system path: {self.base_path}")
            return False

        except Exception as e:
            logging.exception(f"File system connection error: {e}")
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
                async with aiofiles.open(full_path) as file:
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
            logging.exception(f"File system health check failed: {e}")
            return False


class LegacyDataTransformationEngine:
    """Legacy engine for data transformations between systems."""

    def __init__(self):
        """Initialize transformation engine."""
        self.transformations: builtins.dict[str, DataTransformation] = {}
        self.custom_transformers: builtins.dict[str, Callable] = {}

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
            logging.exception(f"Failed to register transformation: {e}")
            return False

    def register_custom_transformer(self, name: str, transformer: Callable) -> bool:
        """Register custom transformer function."""
        try:
            self.custom_transformers[name] = transformer
            logging.info(f"Registered custom transformer: {name}")
            return True

        except Exception as e:
            logging.exception(f"Failed to register custom transformer: {e}")
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

            if transformation.transformation_type == TransformationType.FILTERING:
                return self._apply_filtering_transformation(data, transformation)

            if (
                transformation.transformation_type
                == TransformationType.FORMAT_CONVERSION
            ):
                return self._apply_format_conversion(data, transformation)

            if transformation.transformation_type == TransformationType.VALIDATION:
                return self._apply_validation(data, transformation)

            if transformation.transformation_type == TransformationType.ENRICHMENT:
                return self._apply_enrichment(data, transformation)

            # Execute custom transformation script
            if transformation.transformation_script:
                return self._execute_transformation_script(
                    data, transformation.transformation_script
                )
            return data

        except Exception as e:
            logging.exception(f"Transformation error: {e}")
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

        if isinstance(data, dict):
            # Filter object fields
            if self._matches_filter_conditions(data, transformation.mapping_rules):
                return data
            return None

        return data

    def _matches_filter_conditions(
        self,
        item: builtins.dict[str, Any],
        conditions: builtins.list[builtins.dict[str, Any]],
    ) -> bool:
        """Check if item matches filter conditions."""
        for condition in conditions:
            field = condition.get("field")
            operator = condition.get("operator", "eq")
            value = condition.get("value")

            item_value = item.get(field)

            if (operator == "eq" and item_value != value) or (
                operator == "ne" and item_value == value
            ):
                return False
            if (
                (operator == "gt" and (item_value is None or item_value <= value))
                or (operator == "lt" and (item_value is None or item_value >= value))
                or (
                    operator == "contains"
                    and (item_value is None or value not in str(item_value))
                )
                or (
                    operator == "in" and (item_value is None or item_value not in value)
                )
            ):
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
        if converter_name in self.custom_transformers:
            return self.custom_transformers[converter_name](data)
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

                elif rule_type == "range" and isinstance(field_value, int | float):
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
        # Security: Replace dangerous exec() with safer alternatives
        # Only allow specific safe transformations

        # Define safe transformation functions
        safe_functions = {
            "json": json,
            "datetime": datetime,
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "sorted": sorted,
            "reversed": reversed,
            "sum": sum,
            "min": min,
            "max": max,
        }

        local_vars = {"data": data, "result": data}

        try:
            # Security: Instead of exec(), use a restricted evaluation
            # This is a simplified safe transformation - in production use a proper
            # sandboxed scripting engine like RestrictedPython

            # For basic transformations, create a safe evaluation context
            if script.strip().startswith("result = "):
                # Allow only simple result assignments
                expression = script.strip()[9:]  # Remove 'result = '

                # Basic safety check - only allow alphanumeric, dots, brackets, and basic operators
                import re

                if re.match(r'^[a-zA-Z0-9\[\]{}().,_\'":\s+-]*$', expression):
                    try:
                        # Very basic evaluation for simple data transformations
                        result = eval(
                            expression,
                            {"__builtins__": {}},
                            {**safe_functions, **local_vars},
                        )
                        return result
                    except Exception as transform_error:
                        logging.debug(
                            "Safe transformation script failed to evaluate: %s",
                            transform_error,
                            exc_info=True,
                        )

            # Fallback: log the script and return original data
            logging.warning(f"Unsafe transformation script blocked: {script[:100]}...")
            return data

        except Exception as e:
            logging.exception(f"Transformation script error: {e}")
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
        return f"<data>{data}</data>"

    def _xml_to_json(self, xml_data: str) -> builtins.dict[str, Any]:
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
            logging.exception(f"XML parsing error: {e}")
            return {"error": f"Invalid XML: {e}"}

    def _csv_to_json(self, csv_data: str) -> builtins.list[builtins.dict[str, Any]]:
        """Convert CSV to JSON."""
        import csv
        import io

        reader = csv.DictReader(io.StringIO(csv_data))
        return list(reader)

    def _json_to_csv(self, json_data: builtins.list[builtins.dict[str, Any]]) -> str:
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
        self, data: builtins.dict[str, Any], separator: str = "."
    ) -> builtins.dict[str, Any]:
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
        self, data: builtins.dict[str, Any], separator: str = "."
    ) -> builtins.dict[str, Any]:
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
        self.connectors: builtins.dict[str, ExternalSystemConnector] = {}
        self.connector_factories: builtins.dict[ConnectorType, type] = {
            ConnectorType.REST_API: RESTAPIConnector,
            ConnectorType.DATABASE: DatabaseConnector,
            ConnectorType.FILE_SYSTEM: FileSystemConnector,
        }

        self.transformation_engine = LegacyDataTransformationEngine()

        # Health monitoring
        self.health_check_tasks: builtins.dict[str, asyncio.Task] = {}

        # Request tracking
        self.active_requests: builtins.dict[str, IntegrationRequest] = {}

        # Metrics
        self.metrics: builtins.dict[str, Any] = defaultdict(int)

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
            logging.exception(f"Failed to add external system: {e}")
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
            logging.exception(f"Failed to remove external system: {e}")
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
                logging.exception(f"Health monitor error for {system_id}: {e}")
                await asyncio.sleep(connector.config.health_check_interval)

    def get_system_status(self, system_id: str) -> builtins.dict[str, Any] | None:
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

    def get_manager_status(self) -> builtins.dict[str, Any]:
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


def create_external_integration_platform() -> builtins.dict[str, Any]:
    """Create external integration platform."""
    manager = ExternalSystemManager()
    transformation_engine = LegacyDataTransformationEngine()

    return {"manager": manager, "transformation_engine": transformation_engine}
