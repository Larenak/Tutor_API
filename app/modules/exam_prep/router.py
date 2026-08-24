from typing import Annotated

from fastapi import APIRouter, Query

from app.api.responses import SuccessResponse, success
from app.modules.exam_prep.schemas import AttemptCreate, TaskStatusUpdate, TheoryCompletionCreate
from app.modules.exam_prep.service import (
    complete_lesson_theory,
    get_admin_dashboard,
    get_admin_users,
    get_analytics,
    get_current_lesson,
    get_overview,
    get_roadmap,
    list_tasks,
    list_theory,
    set_task_status,
    submit_attempt,
)

router = APIRouter(prefix="/exam/math-profile", tags=["Profile mathematics prototype"])


@router.get("/overview", response_model=SuccessResponse[dict[str, object]])
async def overview() -> SuccessResponse[dict[str, object]]:
    return success(get_overview())


@router.get("/tasks", response_model=SuccessResponse[list[dict[str, object]]])
async def tasks(
    topic_id: str | None = None,
    difficulty: str | None = None,
) -> SuccessResponse[list[dict[str, object]]]:
    return success(list_tasks(topic_id=topic_id, difficulty=difficulty))


@router.get("/theory", response_model=SuccessResponse[list[dict[str, object]]])
async def theory(topic_id: str | None = None) -> SuccessResponse[list[dict[str, object]]]:
    return success(list_theory(topic_id=topic_id))


@router.post("/attempts", response_model=SuccessResponse[dict[str, object]])
async def create_attempt(payload: AttemptCreate) -> SuccessResponse[dict[str, object]]:
    return success(
        submit_attempt(
            session_id=payload.session_id,
            task_id=payload.task_id,
            answer=payload.answer,
            duration_seconds=payload.duration_seconds,
            mode=payload.mode,
            lesson_unit_id=payload.lesson_unit_id,
        )
    )


@router.get("/lesson/current", response_model=SuccessResponse[dict[str, object]])
async def current_lesson(
    session_id: Annotated[str, Query(min_length=1, max_length=80)] = "local-student",
) -> SuccessResponse[dict[str, object]]:
    return success(get_current_lesson(session_id))


@router.post(
    "/lesson/theory/complete",
    response_model=SuccessResponse[dict[str, object]],
)
async def complete_theory(
    payload: TheoryCompletionCreate,
) -> SuccessResponse[dict[str, object]]:
    return success(complete_lesson_theory(payload.session_id, payload.lesson_unit_id))


@router.get("/analytics", response_model=SuccessResponse[dict[str, object]])
async def analytics(
    session_id: Annotated[str, Query(min_length=1, max_length=80)] = "local-student",
) -> SuccessResponse[dict[str, object]]:
    return success(get_analytics(session_id))


@router.get("/roadmap", response_model=SuccessResponse[dict[str, object]])
async def roadmap(
    session_id: Annotated[str, Query(min_length=1, max_length=80)] = "local-student",
) -> SuccessResponse[dict[str, object]]:
    return success(get_roadmap(session_id))


@router.get("/admin/dashboard", response_model=SuccessResponse[dict[str, object]])
async def admin_dashboard() -> SuccessResponse[dict[str, object]]:
    return success(get_admin_dashboard())


@router.get("/admin/users", response_model=SuccessResponse[list[dict[str, object]]])
async def admin_users() -> SuccessResponse[list[dict[str, object]]]:
    return success(get_admin_users())


@router.get("/admin/tasks", response_model=SuccessResponse[list[dict[str, object]]])
async def admin_tasks() -> SuccessResponse[list[dict[str, object]]]:
    return success(list_tasks(include_unpublished=True))


@router.patch("/admin/tasks/{task_id}/status", response_model=SuccessResponse[dict[str, object]])
async def update_task_status(
    task_id: str,
    payload: TaskStatusUpdate,
) -> SuccessResponse[dict[str, object]]:
    return success(set_task_status(task_id, payload.published))
