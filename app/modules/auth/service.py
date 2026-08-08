from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import ALGORITHM, create_token, hash_password, verify_password
from app.modules.auth.models import RefreshSession, UserCredential
from app.modules.auth.schemas import TokenRead
from app.modules.users.models import User


def _token_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()


async def _issue_tokens(db: AsyncSession, user_id: UUID) -> TokenRead:
    settings = get_settings()
    access = create_token(user_id, "access", timedelta(minutes=settings.access_token_expire_minutes))
    refresh_token = create_token(user_id, "refresh", timedelta(days=settings.refresh_token_expire_days))
    db.add(RefreshSession(user_id=user_id, token_hash=_token_hash(refresh_token), expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)))
    await db.commit()
    return TokenRead(user_id=user_id, access_token=access, refresh_token=refresh_token)


async def register(db: AsyncSession, email: str, password: str, display_name: str | None) -> TokenRead:
    normalized_email = email.lower()
    if await db.scalar(select(UserCredential).where(UserCredential.email == normalized_email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    user = User(display_name=display_name)
    db.add(user)
    await db.flush()
    db.add(UserCredential(user_id=user.id, email=normalized_email, password_hash=hash_password(password)))
    await db.commit()
    return await _issue_tokens(db, user.id)


async def login(db: AsyncSession, email: str, password: str) -> TokenRead:
    credential = await db.scalar(select(UserCredential).where(UserCredential.email == email.lower()))
    if credential is None or not verify_password(password, credential.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return await _issue_tokens(db, credential.user_id)


async def refresh(db: AsyncSession, refresh_token: str) -> TokenRead:
    try:
        payload = jwt.decode(refresh_token, get_settings().jwt_secret_key, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh" or not payload.get("sub"):
            raise ValueError("Wrong token type")
        user_id = UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from error
    session = await db.scalar(select(RefreshSession).where(RefreshSession.token_hash == _token_hash(refresh_token)))
    if session is None or session.revoked_at is not None or session.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Expired refresh token")
    session.revoked_at = datetime.now(UTC)
    await db.commit()
    return await _issue_tokens(db, user_id)
