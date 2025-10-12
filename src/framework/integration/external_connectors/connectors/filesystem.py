"""Filesystem connector implementation for external systems."""

import logging
import os
import time
from pathlib import Path

from ..base import ExternalSystemConnector
from ..config import ExternalSystemConfig, IntegrationRequest, IntegrationResponse


class FileSystemConnector(ExternalSystemConnector):
    """File system connector implementation.

    NOTE: This is a basic implementation for local filesystem operations.
    For production use with remote filesystems (S3, Azure Blob, etc.):
    1. Install appropriate SDK (boto3, azure-storage-blob, etc.)
    2. Add proper authentication handling
    3. Implement retry logic for network operations
    4. Add streaming support for large files
    """

    def __init__(self, config: ExternalSystemConfig):
        """Initialize file system connector."""
        super().__init__(config)
        self.base_path = Path(config.endpoint_url or "/tmp")

    async def connect(self) -> bool:
        """Connect to file system."""
        try:
            # Ensure the base path exists and is accessible
            self.base_path.mkdir(parents=True, exist_ok=True)
            if not os.access(self.base_path, os.R_OK | os.W_OK):
                raise PermissionError(f"No read/write access to {self.base_path}")

            logging.info(f"Connected to file system: {self.base_path}")
            self.connected = True
            return True
        except Exception as e:
            logging.exception(f"Failed to connect to file system: {e}")
            return False

    async def disconnect(self) -> bool:
        """Disconnect from file system."""
        try:
            # No actual disconnect needed for local filesystem
            self.connected = False
            logging.info(f"Disconnected from file system: {self.base_path}")
            return True
        except Exception as e:
            logging.exception(f"Failed to disconnect from file system: {e}")
            return False

    async def execute_request(self, request: IntegrationRequest) -> IntegrationResponse:
        """Execute file system request."""
        start_time = time.time()

        try:
            # Check circuit breaker
            if self.is_circuit_breaker_open():
                raise Exception("Circuit breaker is open")

            # TODO: Implement file system operations based on request
            # This is a placeholder implementation
            operation = request.data.get("operation", "read") if request.data else "read"
            file_path = request.data.get("file_path", "test.txt") if request.data else "test.txt"

            full_path = self.base_path / file_path

            if operation == "read":
                if full_path.exists():
                    content = full_path.read_text()
                    result_data = {"content": content, "size": len(content)}
                else:
                    raise FileNotFoundError(f"File not found: {file_path}")
            elif operation == "write":
                content = request.data.get("content", "") if request.data else ""
                full_path.write_text(content)
                result_data = {"bytes_written": len(content)}
            elif operation == "list":
                files = [f.name for f in self.base_path.iterdir() if f.is_file()]
                result_data = {"files": files, "count": len(files)}
            else:
                raise ValueError(f"Unsupported operation: {operation}")

            latency = (time.time() - start_time) * 1000
            self.record_success()

            return IntegrationResponse(
                request_id=request.request_id,
                success=True,
                data=result_data,
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
            # Check if base path is accessible
            return self.connected and self.base_path.exists() and os.access(self.base_path, os.R_OK | os.W_OK)
        except Exception as e:
            logging.exception(f"File system health check failed: {e}")
            return False
