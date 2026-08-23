from pydantic import BaseModel, Field


class AttemptCreate(BaseModel):
    session_id: str = Field(default="local-student", min_length=1, max_length=80)
    task_id: str = Field(min_length=1, max_length=40)
    answer: str = Field(min_length=1, max_length=500)
    duration_seconds: int = Field(default=0, ge=0, le=14_400)


class TaskStatusUpdate(BaseModel):
    published: bool
