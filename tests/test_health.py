from fastapi.testclient import TestClient

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
