from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.dependencies import get_current_user
from app.modules.users.models import User, UserRole, UserStatus


def current_user() -> User:
    return User(id=uuid4(), display_name="Student", role=UserRole.STUDENT, status=UserStatus.ACTIVE)


def test_get_me_requires_access_token(client: TestClient) -> None:
    response = client.get("/api/v1/users/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_get_me_returns_current_user(client: TestClient) -> None:
    user = current_user()
    app.dependency_overrides[get_current_user] = lambda: user

    response = client.get("/api/v1/users/me")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "id": str(user.id),
        "display_name": "Student",
        "role": "student",
        "status": "active",
    }


def test_update_me_changes_display_name(client: TestClient, db: AsyncMock) -> None:
    user = current_user()
    db.scalar.return_value = None
    app.dependency_overrides[get_current_user] = lambda: user

    response = client.patch("/api/v1/users/me", json={"display_name": "New name"})

    assert response.status_code == 200
    assert user.display_name == "New name"
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(user)


def test_update_me_rejects_existing_display_name(client: TestClient, db: AsyncMock) -> None:
    user = current_user()
    db.scalar.return_value = current_user()
    app.dependency_overrides[get_current_user] = lambda: user

    response = client.patch("/api/v1/users/me", json={"display_name": "Taken"})

    assert response.status_code == 409
    assert response.json()["detail"] == "Display name already exists"
    db.commit.assert_not_awaited()
