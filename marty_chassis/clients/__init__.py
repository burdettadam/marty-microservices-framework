"""
Client libraries for the Marty Chassis.

This module provides HTTP and gRPC client libraries with built-in:
- Authentication (JWT, API keys)
- Retry policies and circuit breaking
- Request/response logging
- Metrics collection
- Timeout handling
"""

import time
from typing import Any, Dict, Optional, Union

import grpc
import httpx
from grpc import aio

from marty_chassis.config import ChassisConfig
from marty_chassis.exceptions import ClientError
from marty_chassis.logger import get_logger
from marty_chassis.resilience import CircuitBreaker, RetryPolicy
from marty_chassis.security import TokenData

logger = get_logger(__name__)


class HTTPClient:
    """HTTP client with chassis features."""

    def __init__(
        self,
        base_url: str,
        config: ChassisConfig | None = None,
        timeout: float = 30.0,
        enable_retry: bool = True,
        enable_circuit_breaker: bool = True,
        auth_token: str | None = None,
        api_key: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.config = config or ChassisConfig.from_env()
        self.timeout = timeout
        self.auth_token = auth_token
        self.api_key = api_key

        # Initialize resilience patterns
        self.retry_policy = None
        if enable_retry:
            self.retry_policy = RetryPolicy(
                max_attempts=self.config.resilience.retry_attempts,
                min_wait=1.0,
                max_wait=60.0,
                multiplier=self.config.resilience.retry_backoff_factor,
                retry_exceptions=(httpx.HTTPError, httpx.TimeoutException),
                name=f"http_client_{base_url}",
            )

        self.circuit_breaker = None
        if enable_circuit_breaker:
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=self.config.resilience.circuit_breaker_failure_threshold,
                recovery_timeout=self.config.resilience.circuit_breaker_recovery_timeout,
                expected_exception=httpx.HTTPError,
                name=f"http_client_{base_url}",
            )

        # Create HTTP client
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
        )

        logger.info("HTTP client initialized", base_url=base_url)

    def _get_headers(
        self, additional_headers: dict[str, str] | None = None
    ) -> dict[str, str]:
        """Get request headers with authentication."""
        headers = {
            "User-Agent": f"marty-chassis/{self.config.service.version}",
            "Content-Type": "application/json",
        }

        # Add authentication headers
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        elif self.api_key:
            headers[self.config.security.api_key_header] = self.api_key

        # Add additional headers
        if additional_headers:
            headers.update(additional_headers)

        return headers

    async def _make_request(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | str | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make HTTP request with resilience patterns."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        request_headers = self._get_headers(headers)

        async def _request():
            start_time = time.time()

            try:
                response = await self.client.request(
                    method=method,
                    url=url,
                    json=data if isinstance(data, dict) else None,
                    content=data if isinstance(data, str) else None,
                    params=params,
                    headers=request_headers,
                )

                duration = time.time() - start_time
                logger.info(
                    "HTTP request completed",
                    method=method,
                    url=url,
                    status_code=response.status_code,
                    duration_ms=round(duration * 1000, 2),
                )

                response.raise_for_status()
                return response

            except httpx.HTTPError as e:
                duration = time.time() - start_time
                logger.error(
                    "HTTP request failed",
                    method=method,
                    url=url,
                    error=str(e),
                    duration_ms=round(duration * 1000, 2),
                )
                raise ClientError(
                    f"HTTP request failed: {e}", details={"url": url, "method": method}
                )

        # Apply circuit breaker
        if self.circuit_breaker:
            response = await self.circuit_breaker.acall(_request)
        else:
            response = await _request()

        # Apply retry policy
        if self.retry_policy:
            response = await self.retry_policy.execute(lambda: response)

        return response

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make GET request."""
        return await self._make_request("GET", path, params=params, headers=headers)

    async def post(
        self,
        path: str,
        data: dict[str, Any] | str | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make POST request."""
        return await self._make_request(
            "POST", path, data=data, params=params, headers=headers
        )

    async def put(
        self,
        path: str,
        data: dict[str, Any] | str | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make PUT request."""
        return await self._make_request(
            "PUT", path, data=data, params=params, headers=headers
        )

    async def delete(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make DELETE request."""
        return await self._make_request("DELETE", path, params=params, headers=headers)

    async def patch(
        self,
        path: str,
        data: dict[str, Any] | str | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make PATCH request."""
        return await self._make_request(
            "PATCH", path, data=data, params=params, headers=headers
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
        logger.info("HTTP client closed")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class GRPCClient:
    """gRPC client with chassis features."""

    def __init__(
        self,
        server_address: str,
        config: ChassisConfig | None = None,
        timeout: float = 30.0,
        enable_retry: bool = True,
        enable_circuit_breaker: bool = True,
        auth_token: str | None = None,
        use_tls: bool = False,
        tls_cert_path: str | None = None,
    ):
        self.server_address = server_address
        self.config = config or ChassisConfig.from_env()
        self.timeout = timeout
        self.auth_token = auth_token
        self.use_tls = use_tls
        self.tls_cert_path = tls_cert_path

        # Initialize resilience patterns
        self.retry_policy = None
        if enable_retry:
            self.retry_policy = RetryPolicy(
                max_attempts=self.config.resilience.retry_attempts,
                min_wait=1.0,
                max_wait=60.0,
                multiplier=self.config.resilience.retry_backoff_factor,
                retry_exceptions=(grpc.RpcError,),
                name=f"grpc_client_{server_address}",
            )

        self.circuit_breaker = None
        if enable_circuit_breaker:
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=self.config.resilience.circuit_breaker_failure_threshold,
                recovery_timeout=self.config.resilience.circuit_breaker_recovery_timeout,
                expected_exception=grpc.RpcError,
                name=f"grpc_client_{server_address}",
            )

        # Create gRPC channel
        if self.use_tls:
            if self.tls_cert_path:
                with open(self.tls_cert_path, "rb") as f:
                    credentials = grpc.ssl_channel_credentials(f.read())
            else:
                credentials = grpc.ssl_channel_credentials()
            self.channel = aio.secure_channel(server_address, credentials)
        else:
            self.channel = aio.insecure_channel(server_address)

        logger.info("gRPC client initialized", server_address=server_address)

    def _get_metadata(self) -> list:
        """Get gRPC metadata with authentication."""
        metadata = []

        if self.auth_token:
            metadata.append(("authorization", f"Bearer {self.auth_token}"))

        metadata.append(("user-agent", f"marty-chassis/{self.config.service.version}"))

        return metadata

    async def call_unary_unary(
        self,
        method: str,
        request_serializer,
        response_deserializer,
        request,
        timeout: float | None = None,
    ):
        """Make unary-unary gRPC call."""

        async def _call():
            start_time = time.time()

            try:
                call = aio.unary_unary(
                    self.channel,
                    method,
                    request_serializer=request_serializer,
                    response_deserializer=response_deserializer,
                )

                response = await call(
                    request,
                    timeout=timeout or self.timeout,
                    metadata=self._get_metadata(),
                )

                duration = time.time() - start_time
                logger.info(
                    "gRPC call completed",
                    method=method,
                    duration_ms=round(duration * 1000, 2),
                )

                return response

            except grpc.RpcError as e:
                duration = time.time() - start_time
                logger.error(
                    "gRPC call failed",
                    method=method,
                    error=str(e),
                    status_code=e.code().name if hasattr(e, "code") else "UNKNOWN",
                    duration_ms=round(duration * 1000, 2),
                )
                raise ClientError(f"gRPC call failed: {e}", details={"method": method})

        # Apply circuit breaker
        if self.circuit_breaker:
            response = await self.circuit_breaker.acall(_call)
        else:
            response = await _call()

        # Apply retry policy
        if self.retry_policy:
            response = await self.retry_policy.execute(lambda: response)

        return response

    async def call_unary_stream(
        self,
        method: str,
        request_serializer,
        response_deserializer,
        request,
        timeout: float | None = None,
    ):
        """Make unary-stream gRPC call."""

        async def _call():
            start_time = time.time()

            try:
                call = aio.unary_stream(
                    self.channel,
                    method,
                    request_serializer=request_serializer,
                    response_deserializer=response_deserializer,
                )

                response_stream = call(
                    request,
                    timeout=timeout or self.timeout,
                    metadata=self._get_metadata(),
                )

                logger.info("gRPC streaming call started", method=method)
                return response_stream

            except grpc.RpcError as e:
                duration = time.time() - start_time
                logger.error(
                    "gRPC streaming call failed",
                    method=method,
                    error=str(e),
                    status_code=e.code().name if hasattr(e, "code") else "UNKNOWN",
                    duration_ms=round(duration * 1000, 2),
                )
                raise ClientError(
                    f"gRPC streaming call failed: {e}", details={"method": method}
                )

        # Apply circuit breaker
        if self.circuit_breaker:
            response = await self.circuit_breaker.acall(_call)
        else:
            response = await _call()

        return response

    async def close(self) -> None:
        """Close the gRPC channel."""
        await self.channel.close()
        logger.info("gRPC client closed")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class ClientFactory:
    """Factory for creating configured clients."""

    def __init__(self, config: ChassisConfig | None = None):
        self.config = config or ChassisConfig.from_env()

    def create_http_client(
        self,
        base_url: str,
        timeout: float | None = None,
        enable_retry: bool = True,
        enable_circuit_breaker: bool = True,
        auth_token: str | None = None,
        api_key: str | None = None,
    ) -> HTTPClient:
        """Create an HTTP client with default configuration."""
        return HTTPClient(
            base_url=base_url,
            config=self.config,
            timeout=timeout or self.config.resilience.timeout_seconds,
            enable_retry=enable_retry,
            enable_circuit_breaker=enable_circuit_breaker,
            auth_token=auth_token,
            api_key=api_key,
        )

    def create_grpc_client(
        self,
        server_address: str,
        timeout: float | None = None,
        enable_retry: bool = True,
        enable_circuit_breaker: bool = True,
        auth_token: str | None = None,
        use_tls: bool = False,
        tls_cert_path: str | None = None,
    ) -> GRPCClient:
        """Create a gRPC client with default configuration."""
        return GRPCClient(
            server_address=server_address,
            config=self.config,
            timeout=timeout or self.config.resilience.timeout_seconds,
            enable_retry=enable_retry,
            enable_circuit_breaker=enable_circuit_breaker,
            auth_token=auth_token,
            use_tls=use_tls,
            tls_cert_path=tls_cert_path,
        )
