"""Behavior tests for the Petstore-to-Rust identity boundary."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from examples.petstore_domain.identity import (
    add_rust_identity_middleware,
    require_authenticated_user,
)

CONTRACT = json.loads(
    (Path(__file__).parents[3] / "contracts" / "identity-service-http-behavior.json").read_text(
        encoding="utf-8"
    )
)


def _app(transport: httpx.AsyncBaseTransport) -> FastAPI:
    app = FastAPI()
    add_rust_identity_middleware(
        app,
        identity_service_url="http://identity.test",
        transport=transport,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/private")
    async def private(
        user: dict = Depends(require_authenticated_user),
    ) -> dict:
        return {"user": user}

    return app


def test_public_path_does_not_contact_identity_backend() -> None:
    def unexpected(request: httpx.Request) -> httpx.Response:
        pytest.fail(f"unexpected identity request: {request.url}")

    with TestClient(_app(httpx.MockTransport(unexpected))) as client:
        response = client.get(CONTRACT["routes"]["health"])

    assert response.status_code == 200


def test_validated_principal_is_exposed_to_handler() -> None:
    def validate(request: httpx.Request) -> httpx.Response:
        assert request.url.path == CONTRACT["routes"]["validate"]
        assert request.headers["Authorization"] == "Bearer fixture.jwt.token"
        return httpx.Response(
            200,
            json={
                "valid": True,
                "user_id": "user-1",
                "username": "alex",
                "roles": ["issuer"],
                "permissions": ["credential:issue"],
            },
        )

    with TestClient(_app(httpx.MockTransport(validate))) as client:
        response = client.get(
            "/private",
            headers={"Authorization": "Bearer fixture.jwt.token"},
        )

    assert response.status_code == 200
    assert response.json()["user"]["user_id"] == "user-1"


@pytest.mark.parametrize(
    ("authorization", "detail"),
    [
        (None, CONTRACT["failures"]["missing_bearer"]),
        ("Basic abc", CONTRACT["failures"]["invalid_bearer"]),
    ],
)
def test_missing_or_malformed_bearer_fails_closed(
    authorization: str | None,
    detail: str,
) -> None:
    def unexpected(request: httpx.Request) -> httpx.Response:
        pytest.fail(f"unexpected identity request: {request.url}")

    headers = {"Authorization": authorization} if authorization else {}
    with TestClient(_app(httpx.MockTransport(unexpected))) as client:
        response = client.get("/private", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": detail}


def test_invalid_token_fails_closed() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"valid": False}))
    with TestClient(_app(transport)) as client:
        response = client.get(
            "/private",
            headers={"Authorization": "Bearer rejected"},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication failed"}


def test_unavailable_backend_fails_closed() -> None:
    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with TestClient(_app(httpx.MockTransport(unavailable))) as client:
        response = client.get(
            "/private",
            headers={"Authorization": "Bearer fixture.jwt.token"},
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "Identity backend unavailable"}
