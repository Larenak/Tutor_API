from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.responses import SuccessResponse, success
from app.database.session import get_db
from app.modules.auth.schemas import LoginRequest, RefreshRequest, RegisterRequest, TokenRead
from app.modules.auth.service import login, refresh, register

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
