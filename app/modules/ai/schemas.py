from typing import Literal

from pydantic import BaseModel, Field


class ExplainTheoryCreate(BaseModel):
    session_id: str = Field(default="local-student", min_length=1, max_length=80)
    lesson_unit_id: str = Field(min_length=1, max_length=100)
    theory_section_id: str = Field(min_length=1, max_length=100)
    question: str = Field(
        default="Объясни этот раздел проще и проверь, понял ли я его.",
        min_length=1,
        max_length=500,
    )


class HintCreate(BaseModel):
    session_id: str = Field(default="local-student", min_length=1, max_length=80)
    lesson_unit_id: str = Field(min_length=1, max_length=100)
    lesson_task_key: str = Field(min_length=1, max_length=140)
    level: int = Field(default=1, ge=1, le=3)


class AnalyzeErrorCreate(BaseModel):
    session_id: str = Field(default="local-student", min_length=1, max_length=80)
    attempt_id: str = Field(min_length=1, max_length=100)


class AIStatusRead(BaseModel):
    provider: str
    model: str
    configured: bool
    capabilities: list[str]


class TheoryExplanationGenerated(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    explanation: str = Field(min_length=1, max_length=2500)
    example: str = Field(min_length=1, max_length=1200)
    check_question: str = Field(min_length=1, max_length=500)


class TheoryExplanationRead(TheoryExplanationGenerated):
    type: Literal["theory_explanation"] = "theory_explanation"
    provider: str
    model: str
    theory_section_id: str


class HintGenerated(BaseModel):
    focus: str = Field(min_length=1, max_length=300)
    hint: str = Field(min_length=1, max_length=1000)
    self_check: str = Field(min_length=1, max_length=500)


class HintRead(HintGenerated):
    type: Literal["task_hint"] = "task_hint"
    provider: str
    model: str
    level: int
    lesson_task_key: str


class ErrorAnalysisGenerated(BaseModel):
    diagnosis: str = Field(min_length=1, max_length=500)
    evidence: str = Field(min_length=1, max_length=700)
    explanation: str = Field(min_length=1, max_length=1800)
    micro_lesson: str = Field(min_length=1, max_length=1600)
    next_action: str = Field(min_length=1, max_length=500)
    confidence_note: str = Field(min_length=1, max_length=400)


class ErrorAnalysisRead(ErrorAnalysisGenerated):
    type: Literal["error_analysis"] = "error_analysis"
    provider: str
    model: str
    attempt_id: str
