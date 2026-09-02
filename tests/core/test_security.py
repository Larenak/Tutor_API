from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.security import create_token, decode_access_token, hash_password, verify_password


def test_password_hash_is_verifiable_and_does_not_contain_password() -> None:
    password = "Correct horse battery staple 2026"

    password_hash = hash_password(password)

    assert password not in password_hash
    assert verify_password(password, password_hash)
    assert not verify_password("incorrect password", password_hash)


def test_malformed_password_hash_fails_closed() -> None:
    assert not verify_password("password", "not-a-supported-hash")


def test_decode_access_token_returns_token_subject() -> None:
    user_id = uuid4()
    token = create_token(user_id, "access", timedelta(minutes=5))

    assert decode_access_token(token) == user_id


def test_decode_access_token_rejects_refresh_token() -> None:
    token = create_token(uuid4(), "refresh", timedelta(minutes=5))

    with pytest.raises(HTTPException, match="Invalid or expired access token") as error:
        decode_access_token(token)

    assert error.value.status_code == 401


def test_tokens_issued_for_the_same_user_are_unique() -> None:
    user_id = uuid4()

    first = create_token(user_id, "refresh")
    second = create_token(user_id, "refresh")

    assert first != second
