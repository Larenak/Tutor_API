from collections.abc import Awaitable
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import create_token
from app.modules.users.dependencies import get_current_admin, get_current_user
from app.modules.users.models import User, UserRole, UserStatus


class FakeSession:
    def __init__(self, user: User | None) -> None:
        self.user = user

    async def get(self, _: type[User], __: object) -> User | None:
        return self.user


def test_current_user_dependency_returns_active_user() -> None:
    user = User(id=uuid4(), display_name="Student", role=UserRole.STUDENT, status=UserStatus.ACTIVE)
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=create_token(user.id, "access", expires_delta=None)
    )

    result = run(get_current_user(credentials, FakeSession(user)))

    assert result is user


def test_current_user_dependency_rejects_blocked_user() -> None:
    user = User(id=uuid4(), display_name="Blocked", role=UserRole.STUDENT, status=UserStatus.BLOCKED)
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=create_token(user.id, "access", expires_delta=None)
    )

    with pytest.raises(HTTPException, match="User is unavailable") as error:
        run(get_current_user(credentials, FakeSession(user)))

    assert error.value.status_code == 401


def test_current_admin_returns_an_admin_user() -> None:
    user = User(id=uuid4(), display_name="Admin", role=UserRole.ADMIN, status=UserStatus.ACTIVE)

    assert run(get_current_admin(user)) is user


def test_current_admin_rejects_a_student() -> None:
    user = User(id=uuid4(), display_name="Student", role=UserRole.STUDENT, status=UserStatus.ACTIVE)

    with pytest.raises(HTTPException, match="Administrator access required") as error:
        run(get_current_admin(user))

    assert error.value.status_code == 403


def run(awaitable: Awaitable[object]) -> object:
    import asyncio

    return asyncio.run(awaitable)
