from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.main import app
from app.modules.ai import provider as provider_module
from app.modules.ai.provider import (
    AIProviderAuthenticationFailed,
    AIProviderBalanceExhausted,
    AIProviderRateLimited,
    DeepSeekProvider,
    get_ai_provider,
)


class StubAIProvider:
    provider_name = "deepseek"
    model = "deepseek-test"
    configured = True

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, object],
        max_tokens: int = 650,
        json_schema: dict[str, Any] | None = None,
        schema_name: str = "ai_response",
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_payload": user_payload,
                "max_tokens": max_tokens,
                "json_schema": json_schema,
                "schema_name": schema_name,
            }
        )
        return dict(self.response)


class FailingAIProvider(StubAIProvider):
    def __init__(self, error: Exception) -> None:
        super().__init__({})
        self.error = error

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, object],
        max_tokens: int = 650,
        json_schema: dict[str, Any] | None = None,
        schema_name: str = "ai_response",
    ) -> dict[str, Any]:
        raise self.error


def _current_lesson(client: TestClient, session_id: str) -> dict[str, object]:
    response = client.get(
        "/api/v1/exam/math-profile/lesson/current",
        params={"session_id": session_id},
    )
    assert response.status_code == 200
    return response.json()["data"]


def _complete_theory(client: TestClient, session_id: str, lesson: dict[str, object]) -> None:
    response = client.post(
        "/api/v1/exam/math-profile/lesson/theory/complete",
        json={"session_id": session_id, "lesson_unit_id": lesson["unit_id"]},
    )
    assert response.status_code == 200


def test_ai_status_reports_provider_without_exposing_key(client: TestClient) -> None:
    provider = StubAIProvider({})
    app.dependency_overrides[get_ai_provider] = lambda: provider

    response = client.get("/api/v1/ai/status")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "provider": "deepseek",
        "model": "deepseek-test",
        "configured": True,
        "capabilities": ["theory_explanation", "task_hints", "error_analysis"],
    }
    assert "key" not in response.text.lower()


def test_openrouter_key_in_legacy_variable_is_forced_to_free_router(monkeypatch) -> None:
    settings = SimpleNamespace(
        ai_provider="deepseek",
        deepseek_api_key=SecretStr("sk-or-v1-test"),
        deepseek_base_url="https://api.deepseek.com",
        deepseek_model="deepseek-v4-flash",
        deepseek_timeout_seconds=30.0,
        openrouter_api_key=None,
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_model="deepseek/deepseek-v4-flash-0731",
        openrouter_free_only=True,
        openrouter_timeout_seconds=25.0,
        openrouter_max_retries=2,
        openrouter_site_url="http://127.0.0.1:8000",
        openrouter_app_name="AI Tutor",
    )
    monkeypatch.setattr(provider_module, "get_settings", lambda: settings)

    provider = get_ai_provider()

    assert provider.provider_name == "openrouter"
    assert provider.base_url == "https://openrouter.ai/api/v1"
    assert provider.model == "openrouter/free"
    assert provider.extra_headers == {
        "HTTP-Referer": "http://127.0.0.1:8000",
        "X-OpenRouter-Title": "AI Tutor",
    }
    assert provider.request_extra == {
        "provider": {
            "sort": "throughput",
            "allow_fallbacks": True,
            "require_parameters": True,
            "max_price": {"prompt": 0, "completion": 0, "request": 0},
        },
        "plugins": [{"id": "response-healing"}],
    }
    assert provider.timeout_seconds == 25.0
    assert provider.max_retries == 2


def test_free_only_mode_allows_an_explicit_free_model(monkeypatch) -> None:
    settings = SimpleNamespace(
        ai_provider="openrouter",
        deepseek_api_key=None,
        deepseek_base_url="https://api.deepseek.com",
        deepseek_model="deepseek-v4-flash",
        deepseek_timeout_seconds=30.0,
        openrouter_api_key=SecretStr("sk-or-v1-test"),
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_model="minimax/minimax-m3:free",
        openrouter_free_only=True,
        openrouter_timeout_seconds=25.0,
        openrouter_max_retries=2,
        openrouter_site_url="http://127.0.0.1:8000",
        openrouter_app_name="AI Tutor",
    )
    monkeypatch.setattr(provider_module, "get_settings", lambda: settings)

    provider = get_ai_provider()

    assert provider.model == "minimax/minimax-m3:free"
    assert provider.request_extra["provider"]["max_price"] == {
        "prompt": 0,
        "completion": 0,
        "request": 0,
    }


def test_ai_explains_only_a_section_from_current_lesson(client: TestClient) -> None:
    session_id = "ai-theory-student"
    lesson = _current_lesson(client, session_id)
    section = lesson["theory"]["sections"][0]
    provider = StubAIProvider(
        {
            "title": "Почему берём конец минус начало",
            "explanation_style": "why",
            "explanation": "Вычитание показывает движение от A к B.",
            "key_rule": "AB = (xB − xA; yB − yA)",
            "steps": ["Запишите координаты A.", "Вычтите их из координат B."],
            "example": "Три клетки вправо и две вниз дают (3; −2).",
            "common_mistake": "Если поменять точки местами, получится вектор BA.",
            "check_question": "Какой знак будет у второй координаты при движении вниз?",
            "check_answer": "минус",
            "accepted_answers": ["минус", "отрицательный", "отрицательный знак"],
            "check_hint": "Вспомните, как направлена положительная полуось y.",
            "check_explanation": "При движении вниз координата y уменьшается.",
        }
    )
    app.dependency_overrides[get_ai_provider] = lambda: provider

    response = client.post(
        "/api/v1/ai/explain-theory",
        json={
            "session_id": session_id,
            "lesson_unit_id": lesson["unit_id"],
            "theory_section_id": section["id"],
            "question": "Объясни проще",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["theory_section_id"] == section["id"]
    assert data["provider"] == "deepseek"
    assert data["question"] == "Объясни проще"
    assert data["explanation_style"] == "why"
    assert data["check_answer"] == "минус"
    assert "отрицательный" in data["accepted_answers"]
    context = provider.calls[0]["user_payload"]["context"]
    assert context["section"]["id"] == section["id"]
    assert context["student_question"] == "Объясни проще"
    assert provider.calls[0]["max_tokens"] == 650
    assert provider.calls[0]["schema_name"] == "TheoryExplanationGenerated"
    assert provider.calls[0]["json_schema"]["additionalProperties"] is False
    assert "Ответь именно на student_question" in provider.calls[0]["system_prompt"]
    assert "В check_hint не раскрывай ответ" in provider.calls[0]["system_prompt"]


def test_ai_hint_is_bound_to_current_roadmap_practice_task(client: TestClient) -> None:
    session_id = "ai-hint-student"
    lesson = _current_lesson(client, session_id)
    provider = StubAIProvider(
        {
            "focus": "Вспомните формулу длины",
            "hint": "Сначала возведите обе координаты в квадрат.",
            "self_check": "Обе ли координаты вошли под корень?",
        }
    )
    app.dependency_overrides[get_ai_provider] = lambda: provider

    locked_response = client.post(
        "/api/v1/ai/hint",
        json={
            "session_id": session_id,
            "lesson_unit_id": lesson["unit_id"],
            "lesson_task_key": lesson["practice_task"]["lesson_task_key"],
            "level": 1,
        },
    )
    assert locked_response.status_code == 409
    assert provider.calls == []

    _complete_theory(client, session_id, lesson)
    practice_lesson = _current_lesson(client, session_id)
    response = client.post(
        "/api/v1/ai/hint",
        json={
            "session_id": session_id,
            "lesson_unit_id": practice_lesson["unit_id"],
            "lesson_task_key": practice_lesson["practice_task"]["lesson_task_key"],
            "level": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["level"] == 1
    assert provider.calls[0]["user_payload"]["context"]["task"]["prompt"]


def test_ai_analyzes_only_a_saved_incorrect_attempt(client: TestClient) -> None:
    session_id = "ai-error-student"
    lesson = _current_lesson(client, session_id)
    _complete_theory(client, session_id, lesson)
    practice_lesson = _current_lesson(client, session_id)
    task = practice_lesson["practice_task"]
    attempt_response = client.post(
        "/api/v1/exam/math-profile/attempts",
        json={
            "session_id": session_id,
            "task_id": task["id"],
            "answer": "999",
            "duration_seconds": 45,
            "mode": "practice",
            "lesson_unit_id": practice_lesson["unit_id"],
            "lesson_task_key": task["lesson_task_key"],
        },
    )
    assert attempt_response.status_code == 200
    attempt_id = attempt_response.json()["data"]["attempt"]["id"]
    provider = StubAIProvider(
        {
            "diagnosis": "Ответ не совпадает с результатом вычисления длины.",
            "evidence": "Отправлен ответ 999, проверенный ответ другой.",
            "explanation": "Нужно применить теорему Пифагора к координатам.",
            "micro_lesson": "Длина (x; y) равна корню из суммы квадратов координат.",
            "next_action": "Повторите формулу и решите следующую задачу урока.",
            "confidence_note": "Ход решения не введён, поэтому точный ошибочный шаг неизвестен.",
        }
    )
    app.dependency_overrides[get_ai_provider] = lambda: provider

    response = client.post(
        "/api/v1/ai/analyze-error",
        json={"session_id": session_id, "attempt_id": attempt_id},
    )

    assert response.status_code == 200
    assert response.json()["data"]["attempt_id"] == attempt_id
    context = provider.calls[0]["user_payload"]["context"]
    assert context["student_attempt"]["answer"] == "999"
    assert context["verified_solution"]
    assert "short answer" in context["evidence_limit"]


def test_ai_request_without_key_returns_safe_service_message(client: TestClient) -> None:
    session_id = "ai-no-key-student"
    lesson = _current_lesson(client, session_id)
    section = lesson["theory"]["sections"][0]
    provider = DeepSeekProvider(
        api_key=None,
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
        timeout_seconds=1,
    )
    app.dependency_overrides[get_ai_provider] = lambda: provider

    response = client.post(
        "/api/v1/ai/explain-theory",
        json={
            "session_id": session_id,
            "lesson_unit_id": lesson["unit_id"],
            "theory_section_id": section["id"],
            "question": "Объясни",
        },
    )

    assert response.status_code == 503
    assert "DEEPSEEK_API_KEY" in response.json()["detail"]


def test_ai_request_reports_invalid_deepseek_key(client: TestClient) -> None:
    session_id = "ai-invalid-key-student"
    lesson = _current_lesson(client, session_id)
    section = lesson["theory"]["sections"][0]
    provider = FailingAIProvider(AIProviderAuthenticationFailed("invalid key"))
    app.dependency_overrides[get_ai_provider] = lambda: provider

    response = client.post(
        "/api/v1/ai/explain-theory",
        json={
            "session_id": session_id,
            "lesson_unit_id": lesson["unit_id"],
            "theory_section_id": section["id"],
            "question": "Объясни",
        },
    )

    assert response.status_code == 503
    assert "отклонил API-ключ" in response.json()["detail"]


def test_ai_request_reports_balance_and_rate_limit(client: TestClient) -> None:
    session_id = "ai-provider-errors-student"
    lesson = _current_lesson(client, session_id)
    section = lesson["theory"]["sections"][0]
    request_body = {
        "session_id": session_id,
        "lesson_unit_id": lesson["unit_id"],
        "theory_section_id": section["id"],
        "question": "Объясни",
    }

    provider = FailingAIProvider(AIProviderBalanceExhausted("no balance"))
    app.dependency_overrides[get_ai_provider] = lambda: provider
    balance_response = client.post("/api/v1/ai/explain-theory", json=request_body)

    provider.error = AIProviderRateLimited("rate limit")
    rate_response = client.post("/api/v1/ai/explain-theory", json=request_body)

    assert balance_response.status_code == 503
    assert "балансе DeepSeek" in balance_response.json()["detail"]
    assert rate_response.status_code == 429
    assert "частоту запросов" in rate_response.json()["detail"]
