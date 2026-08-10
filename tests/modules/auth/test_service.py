from collections.abc import Awaitable
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.security import verify_password
from app.modules.auth.models import RefreshSession, UserCredential
from app.modules.auth.service import login, register
from app.modules.users.models import User


class FakeSession:
    def __init__(self, scalar_results: list[object | None]) -> None:
        self._scalar_results = iter(scalar_results)
        self.added: list[object] = []
        self.commit_calls = 0

    async def scalar(self, _: object) -> object | None:
        return next(self._scalar_results)

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        user = next(instance for instance in self.added if isinstance(instance, User))
        user.id = uuid4()

    async def commit(self) -> None:
        self.commit_calls += 1


def test_register_creates_user_credentials_and_refresh_session() -> None:
    db = FakeSession([None, None])

    tokens = run(register(db, "Student@Example.com", "strong password", "Student"))

    user = next(instance for instance in db.added if isinstance(instance, User))
    credential = next(instance for instance in db.added if isinstance(instance, UserCredential))
    session = next(instance for instance in db.added if isinstance(instance, RefreshSession))
    assert tokens.user_id == user.id
    assert credential.user_id == user.id
    assert credential.email == "student@example.com"
    assert verify_password("strong password", credential.password_hash)
    assert session.user_id == user.id
    assert db.commit_calls == 2


def test_register_rejects_duplicate_email() -> None:
    existing_credential = UserCredential(user_id=uuid4(), email="student@example.com", password_hash="hash")
    db = FakeSession([existing_credential])

    with pytest.raises(HTTPException, match="Email already exists") as error:
        run(register(db, "student@example.com", "strong password", "Student"))

    assert error.value.status_code == 409
    assert db.added == []


def test_login_rejects_incorrect_password() -> None:
    db = FakeSession([None])

    with pytest.raises(HTTPException, match="Invalid email or password") as error:
        run(login(db, "student@example.com", "incorrect password"))

    assert error.value.status_code == 401


def run(awaitable: Awaitable[object]) -> object:
    import asyncio

    return asyncio.run(awaitable)
