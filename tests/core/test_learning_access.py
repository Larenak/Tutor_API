from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_token
from app.modules.exam_prep.service import reset_demo_state
from app.modules.users.models import User, UserRole, UserStatus

OWNER = UUID("00000000-0000-4000-8000-000000000011")
OTHER = UUID("00000000-0000-4000-8000-000000000012")
BASE = "/api/v1/exam/math-profile"
PRIVATE_PATHS = ["/theory/completed", "/lesson/current", "/homework/current",
                 "/analytics", "/roadmap", "/dashboard"]


@pytest.fixture(autouse=True)
def clean_progress():
    reset_demo_state()


def login(db: AsyncMock, user_id: UUID) -> dict[str, str]:
    db.get.return_value = User(id=user_id, display_name="Test", role=UserRole.STUDENT,
                              status=UserStatus.ACTIVE)
    return {"Authorization": f"Bearer {create_token(user_id, "access")}"}


@pytest.mark.parametrize("path", PRIVATE_PATHS)
def test_private_learning_requires_login(client: TestClient, path: str):
    assert client.get(BASE + path).status_code == 401


@pytest.mark.parametrize("path", PRIVATE_PATHS)
def test_cannot_read_another_account(client: TestClient, db: AsyncMock, path: str):
    headers = login(db, OWNER)
    assert client.get(BASE + path, headers=headers).status_code == 200
    assert client.get(BASE + path, headers=headers,
                      params={"session_id": str(OTHER)}).status_code == 403


@pytest.mark.parametrize("path,payload", [
    (BASE + "/attempts", {"task_id": "math-04", "answer": "0.1"}),
    (BASE + "/lesson/theory/complete", {"lesson_unit_id": "vectors"}),
    ("/api/v1/ai/explain-theory", {"lesson_unit_id": "vectors", "theory_section_id": "x"}),
    ("/api/v1/ai/hint", {"lesson_unit_id": "vectors", "lesson_task_key": "x"}),
    ("/api/v1/ai/analyze-error", {"attempt_id": "x"}),
])
def test_writes_and_ai_reject_foreign_session(client: TestClient, db: AsyncMock,
                                            path: str, payload: dict):
    assert client.post(path, json=payload).status_code == 401
    headers = login(db, OWNER)
    assert client.post(path, headers=headers,
                       json={**payload, "session_id": str(OTHER)}).status_code == 403


def test_progress_is_owned_by_authenticated_account(client: TestClient, db: AsyncMock):
    headers = login(db, OWNER)
    response = client.post(BASE + "/attempts", headers=headers,
                           json={"task_id": "math-04", "answer": "0.1"})
    assert response.status_code == 200
    assert client.get(BASE + "/analytics", headers=headers).json()["data"]["summary"]["attempts"] == 1
    headers = login(db, OTHER)
    assert client.get(BASE + "/analytics", headers=headers).json()["data"]["summary"]["attempts"] == 0
    assert client.get(BASE + "/admin/dashboard", headers=headers).status_code == 403


def test_ui_security_headers(client: TestClient):
    response = client.get("/")
    policy = response.headers["content-security-policy"]
    assert "script-src 'self';" in policy
    assert "frame-ancestors 'none'" in policy
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/assets/app.js").headers["content-security-policy"] == policy
    assert "content-security-policy" not in client.get("/docs").headers
