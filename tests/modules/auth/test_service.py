from collections.abc import Awaitable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.security import create_token, hash_password, verify_password
from app.modules.auth.models import RefreshSession, UserCredential
from app.modules.auth.service import login, logout, refresh, register
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

    async def rollback(self) -> None:
        pass


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
    assert db.commit_calls == 1


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


def test_login_issues_a_new_refresh_session() -> None:
    user_id = uuid4()
    credential = UserCredential(
        user_id=user_id,
        email="student@example.com",
        password_hash=hash_password("strong password"),
    )
    db = FakeSession([credential])

    tokens = run(login(db, " Student@Example.com ", "strong password"))

    session = next(instance for instance in db.added if isinstance(instance, RefreshSession))
    assert tokens.user_id == user_id
    assert session.user_id == user_id
    assert db.commit_calls == 1


def test_refresh_rotates_and_revokes_the_previous_session() -> None:
    user_id = uuid4()
    old_token = create_token(user_id, "refresh")
    old_session = RefreshSession(
        user_id=user_id,
        token_hash=sha256(old_token.encode()).hexdigest(),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db = FakeSession([old_session])

    tokens = run(refresh(db, old_token))

    assert old_session.revoked_at is not None
    assert tokens.refresh_token != old_token
    assert len([item for item in db.added if isinstance(item, RefreshSession)]) == 1
    assert db.commit_calls == 1


def test_logout_revokes_only_the_current_users_session() -> None:
    user_id = uuid4()
    session = RefreshSession(
        user_id=user_id,
        token_hash="stored",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db = FakeSession([session])

    result = run(logout(db, "token", user_id))

    assert result.logged_out is True
    assert session.revoked_at is not None
    assert db.commit_calls == 1


def run(awaitable: Awaitable[object]) -> object:
    import asyncio

    return asyncio.run(awaitable)
