from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

import jwt
from fastapi import HTTPException, status
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import get_settings

password_context = PasswordHash.recommended()
ALGORITHM = "HS256"
TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_context.verify(password, password_hash)
    except UnknownHashError:
        return False


def verify_and_update_password(password: str, password_hash: str) -> tuple[bool, str | None]:
    try:
        return password_context.verify_and_update(password, password_hash)
    except UnknownHashError:
        return False, None


def _default_expiration(token_type: TokenType) -> timedelta:
    settings = get_settings()
    if token_type == "access":
        return timedelta(minutes=settings.access_token_expire_minutes)
    return timedelta(days=settings.refresh_token_expire_days)


def create_token(
    user_id: UUID,
    token_type: TokenType,
    expires_delta: timedelta | None = None,
) -> str:
    if token_type not in {"access", "refresh"}:
        raise ValueError("Unsupported token type")
    issued_at = datetime.now(UTC)
    lifetime = expires_delta if expires_delta is not None else _default_expiration(token_type)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": issued_at,
        "exp": issued_at + lifetime,
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, get_settings().jwt_secret_key, algorithm=ALGORITHM)


def decode_token(token: str, expected_type: TokenType) -> UUID:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret_key, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type or not payload.get("sub"):
            raise ValueError("Wrong token type")
        return UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired {expected_type} token",
        ) from error


def decode_access_token(token: str) -> UUID:
    return decode_token(token, "access")


def decode_refresh_token(token: str) -> UUID:
    return decode_token(token, "refresh")
