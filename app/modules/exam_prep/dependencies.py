from typing import Annotated

from fastapi import Depends, HTTPException, Query

from app.modules.users.dependencies import get_current_user
from app.modules.users.models import User

CurrentUser = Annotated[User, Depends(get_current_user)]


def owned_session(user: User, session_id: str | None) -> str:
    """The authenticated account owns progress, never a client-chosen identifier."""
    owner = str(user.id)
    if session_id is not None and session_id != owner:
        raise HTTPException(status_code=403, detail="Access to this learning session is denied")
    return owner


def get_learning_session(
    user: CurrentUser,
    session_id: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
) -> str:
    return owned_session(user, session_id)


LearningSession = Annotated[str, Depends(get_learning_session)]
