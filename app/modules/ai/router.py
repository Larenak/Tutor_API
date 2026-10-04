from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.responses import SuccessResponse, success
from app.modules.ai.provider import AIProvider, get_ai_provider
from app.modules.ai.schemas import (
    AIStatusRead,
    AnalyzeErrorCreate,
    ErrorAnalysisRead,
    ExplainTheoryCreate,
    HintCreate,
    HintRead,
    TheoryExplanationRead,
)
from app.modules.ai.service import (
    analyze_error,
    explain_theory,
    generate_hint,
    get_ai_status,
)
from app.modules.exam_prep.dependencies import CurrentUser, owned_session

router = APIRouter(prefix="/ai", tags=["AI tutor"])
ProviderDependency = Annotated[AIProvider, Depends(get_ai_provider)]


@router.get("/status", response_model=SuccessResponse[AIStatusRead])
async def ai_status(provider: ProviderDependency) -> SuccessResponse[AIStatusRead]:
    return success(get_ai_status(provider))


@router.post("/explain-theory", response_model=SuccessResponse[TheoryExplanationRead])
async def explain_current_theory(
    payload: ExplainTheoryCreate,
    user: CurrentUser,
    provider: ProviderDependency,
) -> SuccessResponse[TheoryExplanationRead]:
    session_id = owned_session(user, payload.session_id)
    return success(await explain_theory(payload.model_copy(update={"session_id": session_id}), provider))


@router.post("/hint", response_model=SuccessResponse[HintRead])
async def hint_for_current_task(
    payload: HintCreate,
    user: CurrentUser,
    provider: ProviderDependency,
) -> SuccessResponse[HintRead]:
    session_id = owned_session(user, payload.session_id)
    return success(await generate_hint(payload.model_copy(update={"session_id": session_id}), provider))


@router.post("/analyze-error", response_model=SuccessResponse[ErrorAnalysisRead])
async def analyze_attempt_error(
    payload: AnalyzeErrorCreate,
    user: CurrentUser,
    provider: ProviderDependency,
) -> SuccessResponse[ErrorAnalysisRead]:
    session_id = owned_session(user, payload.session_id)
    return success(await analyze_error(payload.model_copy(update={"session_id": session_id}), provider))
