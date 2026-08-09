from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.responses import SuccessResponse, success
from app.database.session import get_db
from app.modules.users.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.users.schemas import UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=SuccessResponse[UserRead])
async def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> SuccessResponse[UserRead]:
    return success(UserRead.model_validate(current_user))


@router.patch("/me", response_model=SuccessResponse[UserRead])
async def update_me(
    payload: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse[UserRead]:
    existing_user = await db.scalar(
        select(User).where(User.display_name == payload.display_name, User.id != current_user.id)
    )
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Display name already exists")
    current_user.display_name = payload.display_name
    await db.commit()
    await db.refresh(current_user)
    return success(UserRead.model_validate(current_user))
