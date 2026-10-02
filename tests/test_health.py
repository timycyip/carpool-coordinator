import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.models.health import HealthResponse


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_ok_status(client: TestClient) -> None:
    response = client.get("/health")
    assert response.json() == {"status": "ok"}


def test_health_response_conforms_to_schema(client: TestClient) -> None:
    response = client.get("/health")
    model = HealthResponse.model_validate(response.json())
    assert model.status == "ok"


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/health", None),
        ("post", "/auth/google", {}),
        ("get", "/audit", None),
        ("post", "/sessions", {}),
        ("post", "/sessions/ABC123/admin", {}),
    ],
)
def test_rate_limit_is_applied_to_every_mounted_router(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    payload: dict[str, str] | None,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_PER_IP", "1")
    headers = {"X-Forwarded-For": "192.0.2.10"}
    request = getattr(client, method)

    def send_request() -> Response:
        if payload is None:
            return request(path, headers=headers)
        return request(path, headers=headers, json=payload)

    first = send_request()
    assert first.status_code != 429

    second = send_request()
    assert second.status_code == 429
    assert second.headers["Retry-After"]
    assert second.headers["X-RateLimit-Limit"] == "1"
