from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth import router as auth_router
from app.modules.auth.schemas import LogoutRead, TokenRead
from app.modules.users.dependencies import get_current_user
from app.modules.users.models import User, UserRole, UserStatus


def test_register_returns_tokens_from_auth_service(
    client: TestClient, db: AsyncMock, monkeypatch
) -> None:
    token_data = TokenRead(user_id=uuid4(), access_token="access", refresh_token="refresh")
    register = AsyncMock(return_value=token_data)
    monkeypatch.setattr(auth_router, "register", register)

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "student@example.com", "password": "strong password", "display_name": "Student"},
    )

    assert response.status_code == 201
    assert response.json()["data"] == {
        "user_id": str(token_data.user_id),
        "access_token": "access",
        "refresh_token": "refresh",
        "token_type": "bearer",
    }
    register.assert_awaited_once_with(db, "student@example.com", "strong password", "Student")


def test_register_validates_payload_before_calling_service(client: TestClient, monkeypatch) -> None:
    register = AsyncMock()
    monkeypatch.setattr(auth_router, "register", register)

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "short", "display_name": ""},
    )

    assert response.status_code == 422
    register.assert_not_awaited()


def test_login_returns_tokens_from_auth_service(
    client: TestClient, db: AsyncMock, monkeypatch
) -> None:
    token_data = TokenRead(user_id=uuid4(), access_token="access", refresh_token="refresh")
    login = AsyncMock(return_value=token_data)
    monkeypatch.setattr(auth_router, "login", login)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "student@example.com", "password": "strong password"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["access_token"] == "access"
    login.assert_awaited_once_with(db, "student@example.com", "strong password")


def test_refresh_returns_rotated_tokens_from_auth_service(
    client: TestClient, db: AsyncMock, monkeypatch
) -> None:
    token_data = TokenRead(user_id=uuid4(), access_token="new-access", refresh_token="new-refresh")
    refresh = AsyncMock(return_value=token_data)
    monkeypatch.setattr(auth_router, "refresh", refresh)

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "old-refresh"})

    assert response.status_code == 200
    assert response.json()["data"]["refresh_token"] == "new-refresh"
    refresh.assert_awaited_once_with(db, "old-refresh")


def test_logout_requires_an_authenticated_user(
    client: TestClient, monkeypatch
) -> None:
    logout = AsyncMock(return_value=LogoutRead())
    monkeypatch.setattr(auth_router, "logout", logout)

    response = client.post("/api/v1/auth/logout", json={"refresh_token": "refresh"})

    assert response.status_code == 401
    logout.assert_not_awaited()


def test_logout_revokes_the_current_session(
    client: TestClient, db: AsyncMock, monkeypatch
) -> None:
    user = User(
        id=uuid4(),
        display_name="Student",
        role=UserRole.STUDENT,
        status=UserStatus.ACTIVE,
    )
    app.dependency_overrides[get_current_user] = lambda: user
    logout = AsyncMock(return_value=LogoutRead())
    monkeypatch.setattr(auth_router, "logout", logout)

    response = client.post("/api/v1/auth/logout", json={"refresh_token": "refresh"})

    assert response.status_code == 200
    assert response.json()["data"] == {"logged_out": True}
    logout.assert_awaited_once_with(db, "refresh", user.id)
