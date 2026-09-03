from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.responses import SuccessResponse, success
from app.modules.ai.provider import AIProvider, get_ai_provider
from app.modules.ai.schemas import (
    AIStatusRead,
    AnalyzeAssessmentCreate,
    AnalyzeErrorCreate,
    AssessmentAnalysisRead,
    ErrorAnalysisRead,
    ExplainTheoryCreate,
    HintCreate,
    HintRead,
    TheoryExplanationRead,
)
from app.modules.ai.service import (
    analyze_assessment,
    analyze_error,
    explain_theory,
    generate_hint,
    get_ai_status,
)

router = APIRouter(prefix="/ai", tags=["AI tutor"])
ProviderDependency = Annotated[AIProvider, Depends(get_ai_provider)]


@router.get("/status", response_model=SuccessResponse[AIStatusRead])
async def ai_status(provider: ProviderDependency) -> SuccessResponse[AIStatusRead]:
    return success(get_ai_status(provider))


@router.post("/explain-theory", response_model=SuccessResponse[TheoryExplanationRead])
async def explain_current_theory(
    payload: ExplainTheoryCreate,
    provider: ProviderDependency,
) -> SuccessResponse[TheoryExplanationRead]:
    return success(await explain_theory(payload, provider))


@router.post("/hint", response_model=SuccessResponse[HintRead])
async def hint_for_current_task(
    payload: HintCreate,
    provider: ProviderDependency,
) -> SuccessResponse[HintRead]:
    return success(await generate_hint(payload, provider))


@router.post("/analyze-error", response_model=SuccessResponse[ErrorAnalysisRead])
async def analyze_attempt_error(
    payload: AnalyzeErrorCreate,
    provider: ProviderDependency,
) -> SuccessResponse[ErrorAnalysisRead]:
    return success(await analyze_error(payload, provider))


@router.post(
    "/analyze-assessment",
    response_model=SuccessResponse[AssessmentAnalysisRead],
)
async def analyze_failed_assessment(
    payload: AnalyzeAssessmentCreate,
    provider: ProviderDependency,
) -> SuccessResponse[AssessmentAnalysisRead]:
    return success(await analyze_assessment(payload, provider))
