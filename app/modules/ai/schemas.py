from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


class GeneratedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TheoryExplanationGenerated(GeneratedResponse):
    title: str = Field(
        min_length=1,
        max_length=140,
        description="Короткий заголовок, отражающий конкретный вопрос ученика.",
    )
    explanation_style: Literal[
        "simple",
        "why",
        "algorithm",
        "worked_example",
        "definition",
    ] = Field(description="Способ объяснения, выбранный по формулировке вопроса.")
    explanation: str = Field(
        min_length=1,
        max_length=1000,
        description="Прямой ответ на вопрос ученика простыми короткими предложениями.",
    )
    key_rule: str = Field(
        min_length=1,
        max_length=350,
        description="Одна формула или ключевая мысль, нужная именно для вопроса.",
    )
    steps: list[str] = Field(
        min_length=2,
        max_length=4,
        description="От двух до четырёх коротких шагов рассуждения или решения.",
    )
    example: str = Field(
        min_length=1,
        max_length=800,
        description="Новый полностью разобранный пример с конкретными числами.",
    )
    common_mistake: str = Field(
        min_length=1,
        max_length=400,
        description="Ошибка, наиболее вероятная именно после этого вопроса.",
    )
    check_question: str = Field(
        min_length=1,
        max_length=350,
        description="Один короткий вопрос для проверки понимания, без ответа и подсказки.",
    )
    check_answer: str = Field(
        min_length=1,
        max_length=120,
        description="Короткий эталонный ответ на вопрос для самопроверки.",
    )
    accepted_answers: list[str] = Field(
        min_length=1,
        max_length=6,
        description="Допустимые варианты записи ответа, включая эталонный ответ.",
    )
    check_hint: str = Field(
        min_length=1,
        max_length=300,
        description="Подсказка после первой ошибки, не раскрывающая ответ.",
    )
    check_explanation: str = Field(
        min_length=1,
        max_length=450,
        description="Короткое объяснение правильного ответа после проверки.",
    )


class TheoryExplanationRead(TheoryExplanationGenerated):
    type: Literal["theory_explanation"] = "theory_explanation"
    provider: str
    model: str
    theory_section_id: str
    question: str


class HintGenerated(GeneratedResponse):
    focus: str = Field(min_length=1, max_length=300)
    hint: str = Field(min_length=1, max_length=1000)
    self_check: str = Field(min_length=1, max_length=500)


class HintRead(HintGenerated):
    type: Literal["task_hint"] = "task_hint"
    provider: str
    model: str
    level: int
    lesson_task_key: str


class ErrorAnalysisGenerated(GeneratedResponse):
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
