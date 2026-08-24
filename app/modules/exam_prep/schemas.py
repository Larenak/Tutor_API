from typing import Literal

from pydantic import BaseModel, Field


class AttemptCreate(BaseModel):
    session_id: str = Field(default="local-student", min_length=1, max_length=80)
    task_id: str = Field(min_length=1, max_length=40)
    answer: str = Field(min_length=1, max_length=500)
    duration_seconds: int = Field(default=0, ge=0, le=14_400)
    mode: Literal["diagnostic", "practice", "homework"] = "diagnostic"
    lesson_unit_id: str | None = Field(default=None, min_length=1, max_length=100)


class TheoryCompletionCreate(BaseModel):
    session_id: str = Field(default="local-student", min_length=1, max_length=80)
    lesson_unit_id: str = Field(min_length=1, max_length=100)


class TaskStatusUpdate(BaseModel):
    published: bool
