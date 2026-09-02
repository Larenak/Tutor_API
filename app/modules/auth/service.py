from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.security import (
    create_token,
    decode_refresh_token,
    hash_password,
    verify_and_update_password,
)
from app.modules.auth.models import RefreshSession, UserCredential
from app.modules.auth.schemas import LogoutRead, TokenRead
from app.modules.users.models import User, UserStatus


def _token_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def _issue_tokens(db: AsyncSession, user_id: UUID) -> TokenRead:
    settings = get_settings()
    access = create_token(user_id, "access")
    refresh_token = create_token(user_id, "refresh")
    db.add(
        RefreshSession(
            user_id=user_id,
            token_hash=_token_hash(refresh_token),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    return TokenRead(user_id=user_id, access_token=access, refresh_token=refresh_token)


async def _duplicate_registration_error(
    db: AsyncSession,
    normalized_email: str,
    display_name: str,
) -> HTTPException:
    if await db.scalar(select(UserCredential.id).where(UserCredential.email == normalized_email)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    if await db.scalar(select(User.id).where(User.display_name == display_name)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Display name already exists")
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account already exists")


async def register(db: AsyncSession, email: str, password: str, display_name: str) -> TokenRead:
    normalized_email = email.strip().lower()
    normalized_display_name = display_name.strip()
    if await db.scalar(select(UserCredential).where(UserCredential.email == normalized_email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    if await db.scalar(select(User).where(User.display_name == normalized_display_name)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Display name already exists")
    user = User(display_name=normalized_display_name)
    db.add(user)
    await db.flush()
    password_hash = await run_in_threadpool(hash_password, password)
    db.add(UserCredential(user_id=user.id, email=normalized_email, password_hash=password_hash))
    tokens = _issue_tokens(db, user.id)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise await _duplicate_registration_error(
            db, normalized_email, normalized_display_name
        ) from error
    return tokens


async def login(db: AsyncSession, email: str, password: str) -> TokenRead:
    credential = await db.scalar(
        select(UserCredential)
        .join(User, User.id == UserCredential.user_id)
        .where(
            UserCredential.email == email.strip().lower(),
            User.status == UserStatus.ACTIVE,
        )
    )
    password_valid, updated_hash = await run_in_threadpool(
        verify_and_update_password,
        password,
        credential.password_hash if credential is not None else _DUMMY_PASSWORD_HASH,
    )
    if credential is None or not password_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if updated_hash is not None:
        credential.password_hash = updated_hash
    tokens = _issue_tokens(db, credential.user_id)
    await db.commit()
    return tokens


async def refresh(db: AsyncSession, refresh_token: str) -> TokenRead:
    user_id = decode_refresh_token(refresh_token)
    session = await db.scalar(
        select(RefreshSession)
        .join(User, User.id == RefreshSession.user_id)
        .where(
            RefreshSession.token_hash == _token_hash(refresh_token),
            User.status == UserStatus.ACTIVE,
        )
        .with_for_update()
    )
    if (
        session is None
        or session.user_id != user_id
        or session.revoked_at is not None
        or session.expires_at <= datetime.now(UTC)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    session.revoked_at = datetime.now(UTC)
    tokens = _issue_tokens(db, user_id)
    await db.commit()
    return tokens


async def logout(db: AsyncSession, refresh_token: str, user_id: UUID) -> LogoutRead:
    session = await db.scalar(
        select(RefreshSession)
        .where(
            RefreshSession.token_hash == _token_hash(refresh_token),
            RefreshSession.user_id == user_id,
        )
        .with_for_update()
    )
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        await db.commit()
    return LogoutRead()


_DUMMY_PASSWORD_HASH = hash_password("auth-timing-placeholder")
