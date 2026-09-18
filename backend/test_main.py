import os

import pytest
from fastapi.testclient import TestClient


os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-secret-with-at-least-thirty-two-characters"
os.environ["SEED_TEST_USERS"] = "true"
os.environ["MAUA_AI_BASE_URL"] = ""

from backend.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def login_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": "ana@teste.maua.ai", "password": "Maua@2026"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_health_exposes_safe_configuration_only(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database_ready"] is True
    assert "maua_ai_api_key" not in response.json()
    assert "jwt_secret" not in response.json()


@pytest.mark.parametrize(
    "email",
    ["ana@teste.maua.ai", "bruno@teste.maua.ai", "carla@teste.maua.ai"],
)
def test_seeded_accounts_can_login(client: TestClient, email: str):
    response = client.post("/api/auth/login", json={"email": email, "password": "Maua@2026"})
    assert response.status_code == 200
    assert response.json()["user"]["email"] == email


def test_registration_login_and_profile(client: TestClient):
    registration = client.post(
        "/api/auth/register",
        json={"name": "Diego Souza", "email": "diego@example.com", "password": "SenhaSegura@2026"},
    )
    assert registration.status_code == 201
    token = registration.json()["access_token"]

    profile = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert profile.status_code == 200
    assert profile.json()["name"] == "Diego Souza"

    duplicate = client.post(
        "/api/auth/register",
        json={"name": "Outro Diego", "email": "DIEGO@example.com", "password": "OutraSenha@2026"},
    )
    assert duplicate.status_code == 409


def test_wrong_password_is_rejected(client: TestClient):
    response = client.post(
        "/api/auth/login",
        json={"email": "ana@teste.maua.ai", "password": "senha-errada"},
    )
    assert response.status_code == 401


def test_chat_requires_authentication(client: TestClient):
    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "Olá"}]})
    assert response.status_code == 401


def test_chat_requires_user_message_last(client: TestClient):
    response = client.post(
        "/api/chat",
        headers=login_headers(client),
        json={"messages": [{"role": "assistant", "content": "Olá"}]},
    )
    assert response.status_code == 422


def test_unconfigured_ai_server_has_clear_error(client: TestClient):
    response = client.post(
        "/api/chat",
        headers=login_headers(client),
        json={"messages": [{"role": "user", "content": "Olá"}]},
    )
    assert response.status_code == 503
    assert "MAUA_AI_BASE_URL" in response.json()["detail"]
