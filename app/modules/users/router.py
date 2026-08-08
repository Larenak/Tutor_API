from typing import Annotated

from fastapi import APIRouter, Depends
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
    current_user.display_name = payload.display_name
    await db.commit()
    await db.refresh(current_user)
    return success(UserRead.model_validate(current_user))
