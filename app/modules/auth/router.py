from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.responses import SuccessResponse, success
from app.database.session import get_db
from app.modules.auth.schemas import (
    LoginRequest,
    LogoutRead,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenRead,
)
from app.modules.auth.service import login, logout, refresh, register
from app.modules.users.dependencies import get_current_user
from app.modules.users.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=SuccessResponse[TokenRead])
async def register_account(
    payload: RegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> SuccessResponse[TokenRead]:
    return success(await register(db, payload.email, payload.password, payload.display_name))


@router.post("/login", response_model=SuccessResponse[TokenRead])
async def login_account(
    payload: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> SuccessResponse[TokenRead]:
    return success(await login(db, payload.email, payload.password))


@router.post("/refresh", response_model=SuccessResponse[TokenRead])
async def refresh_session(
    payload: RefreshRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> SuccessResponse[TokenRead]:
    return success(await refresh(db, payload.refresh_token))


@router.post("/logout", response_model=SuccessResponse[LogoutRead])
async def logout_account(
    payload: LogoutRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse[LogoutRead]:
    return success(await logout(db, payload.refresh_token, current_user.id))
