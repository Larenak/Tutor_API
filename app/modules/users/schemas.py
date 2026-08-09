from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.users.models import UserRole, UserStatus


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    role: UserRole
    status: UserStatus


class UserUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
