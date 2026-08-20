"""HTTP authentication boundary for the Rust identity service.

The Petstore remains an orchestration example. Token parsing, signature
verification, claim validation, and identity policy are owned by the Rust
identity service; this module only forwards bearer tokens and exposes the
validated principal to FastAPI handlers.
"""

from __future__ import annotations

import os
from collections.abc import Collection
from typing import Any

import httpx
from fastapi import HTTPException, Request, status
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

DEFAULT_EXCLUDED_PATHS = frozenset(
    {"/health", "/docs", "/openapi.json", "/redoc", "/auth/jwt/health"}
)


def _matches_path(path: str, patterns: Collection[str]) -> bool:
    """Match an exact path or a segment-safe ``/*`` prefix."""
    for pattern in patterns:
        if pattern.endswith("/*"):
            prefix = pattern[:-2].rstrip("/")
            if path == prefix or path.startswith(f"{prefix}/"):
                return True
        elif path == pattern:
            return True
    return False


class RustIdentityMiddleware:
    """Fail-closed ASGI adapter for Rust identity token validation."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        identity_service_url: str | None = None,
        excluded_paths: Collection[str] = DEFAULT_EXCLUDED_PATHS,
        optional_paths: Collection[str] = (),
        timeout_seconds: float = 2.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.app = app
        self.identity_service_url = (
            identity_service_url or os.getenv("IDENTITY_SERVICE_URL") or "http://127.0.0.1:8003"
        ).rstrip("/")
        self.excluded_paths = frozenset(excluded_paths)
        self.optional_paths = frozenset(optional_paths)
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or _matches_path(scope.get("path", ""), self.excluded_paths):
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        optional = _matches_path(path, self.optional_paths)
        authorization = Headers(scope=scope).get("authorization")
        if authorization is None:
            if optional:
                self._set_user(scope, None)
                await self.app(scope, receive, send)
            else:
                await self._error(
                    send,
                    status.HTTP_401_UNAUTHORIZED,
                    "Authorization header required",
                )
            return

        scheme, separator, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not separator or not token.strip():
            await self._error(
                send,
                status.HTTP_401_UNAUTHORIZED,
                "Invalid authorization header format",
            )
            return

        try:
            async with httpx.AsyncClient(
                base_url=self.identity_service_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    "/auth/validate",
                    headers={"Authorization": f"Bearer {token.strip()}"},
                )
        except httpx.RequestError:
            await self._error(
                send,
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Identity backend unavailable",
            )
            return

        if response.status_code >= 500:
            await self._error(
                send,
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Identity backend unavailable",
            )
            return
        if response.status_code != status.HTTP_200_OK:
            await self._error(send, status.HTTP_401_UNAUTHORIZED, "Authentication failed")
            return

        try:
            validation = response.json()
        except ValueError:
            await self._error(
                send,
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Invalid identity backend response",
            )
            return

        if not isinstance(validation, dict) or validation.get("valid") is not True:
            if optional:
                self._set_user(scope, None)
                await self.app(scope, receive, send)
            else:
                await self._error(send, status.HTTP_401_UNAUTHORIZED, "Authentication failed")
            return

        self._set_user(scope, validation)
        await self.app(scope, receive, send)

    @staticmethod
    def _set_user(scope: Scope, user: dict[str, Any] | None) -> None:
        state = scope.setdefault("state", {})
        state["authenticated_user"] = user
        state["is_authenticated"] = user is not None

    @staticmethod
    async def _error(send: Send, status_code: int, detail: str) -> None:
        response = JSONResponse(
            {"detail": detail},
            status_code=status_code,
            headers={"WWW-Authenticate": "Bearer"}
            if status_code == status.HTTP_401_UNAUTHORIZED
            else None,
        )
        await response(
            {"type": "http", "asgi": {"version": "3.0"}},
            _empty_receive,
            send,
        )


async def _empty_receive() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}


def add_rust_identity_middleware(
    app: Any,
    *,
    identity_service_url: str | None = None,
    excluded_paths: Collection[str] = DEFAULT_EXCLUDED_PATHS,
    optional_paths: Collection[str] = (),
    transport: httpx.AsyncBaseTransport | None = None,
) -> None:
    """Attach the Rust identity-service boundary to a FastAPI application."""
    app.add_middleware(
        RustIdentityMiddleware,
        identity_service_url=identity_service_url,
        excluded_paths=excluded_paths,
        optional_paths=optional_paths,
        transport=transport,
    )


def get_current_user(request: Request) -> dict[str, Any] | None:
    """Return the principal supplied by the Rust identity service."""
    return getattr(request.state, "authenticated_user", None)


def require_authenticated_user(request: Request) -> dict[str, Any]:
    """Require a principal previously validated by the Rust identity service."""
    user = get_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
