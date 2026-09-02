import asyncio
import json

import httpx
import pytest
from pydantic import SecretStr

from app.modules.ai.provider import (
    AIProviderAuthenticationFailed,
    AIProviderRequestFailed,
    DeepSeekProvider,
    _parse_json_content,
)


def test_json_parser_extracts_object_from_surrounding_text() -> None:
    assert _parse_json_content('Explanation first. {"answer":"ok"} End.') == {
        "answer": "ok"
    }


def test_json_parser_rejects_text_without_an_object() -> None:
    with pytest.raises(AIProviderRequestFailed):
        _parse_json_content("No structured response was produced.")


def test_openrouter_retries_transient_error_and_uses_strict_schema() -> None:
    requests: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return httpx.Response(502, json={"error": {"message": "upstream failed"}})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"answer":"ok"}'}}]},
        )

    provider = DeepSeekProvider(
        api_key=SecretStr("sk-or-test"),
        base_url="https://openrouter.ai/api/v1",
        model="deepseek/test",
        timeout_seconds=3,
        provider_name="openrouter",
        request_extra={
            "provider": {
                "sort": "throughput",
                "allow_fallbacks": True,
                "require_parameters": True,
            }
        },
        max_retries=1,
        retry_base_seconds=0,
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(
        provider.generate_json(
            system_prompt="Return JSON.",
            user_payload={"question": "test"},
            max_tokens=120,
            json_schema={
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
                "additionalProperties": False,
            },
            schema_name="TestAnswer",
        )
    )

    assert result == {"answer": "ok"}
    assert len(requests) == 2
    assert requests[0]["max_tokens"] == 120
    assert requests[0]["provider"]["sort"] == "throughput"
    assert requests[0]["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "TestAnswer",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
                "additionalProperties": False,
            },
        },
    }


def test_openrouter_does_not_retry_invalid_key() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, json={"error": {"message": "invalid key"}})

    provider = DeepSeekProvider(
        api_key=SecretStr("sk-or-invalid"),
        base_url="https://openrouter.ai/api/v1",
        model="deepseek/test",
        timeout_seconds=3,
        provider_name="openrouter",
        max_retries=2,
        retry_base_seconds=0,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(AIProviderAuthenticationFailed):
        asyncio.run(
            provider.generate_json(
                system_prompt="Return JSON.",
                user_payload={"question": "test"},
            )
        )

    assert calls == 1


def test_free_router_retries_transient_provider_404() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                404,
                json={
                    "error": {
                        "message": "Provider returned error",
                        "code": 404,
                        "metadata": {
                            "previous_errors": [
                                {
                                    "code": 429,
                                    "message": "temporarily rate-limited upstream",
                                }
                            ]
                        },
                    }
                },
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"answer":"ok"}'}}]},
        )

    provider = DeepSeekProvider(
        api_key=SecretStr("sk-or-test"),
        base_url="https://openrouter.ai/api/v1",
        model="openrouter/free",
        timeout_seconds=3,
        provider_name="openrouter",
        max_retries=1,
        retry_base_seconds=0,
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(
        provider.generate_json(
            system_prompt="Return JSON.",
            user_payload={"question": "test"},
        )
    )

    assert result == {"answer": "ok"}
    assert calls == 2


def test_free_router_uses_json_object_and_includes_schema_in_prompt() -> None:
    request_body: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        request_body.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"answer":"ok"}'}}]},
        )

    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    provider = DeepSeekProvider(
        api_key=SecretStr("sk-or-test"),
        base_url="https://openrouter.ai/api/v1",
        model="openrouter/free",
        timeout_seconds=3,
        provider_name="openrouter",
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(
        provider.generate_json(
            system_prompt="Return JSON.",
            user_payload={"question": "test"},
            json_schema=schema,
        )
    )

    assert result == {"answer": "ok"}
    assert request_body["response_format"] == {"type": "json_object"}
    assert request_body["max_tokens"] == 1300
    assert "каждое поле из required" in request_body["messages"][0]["content"]
    prompt_payload = json.loads(request_body["messages"][1]["content"])
    assert prompt_payload == {
        "input": {"question": "test"},
        "output_schema": schema,
    }


def test_provider_retries_json_missing_a_required_field() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        content = "{}" if calls == 1 else '{"answer":"ok"}'
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )

    provider = DeepSeekProvider(
        api_key=SecretStr("sk-or-test"),
        base_url="https://openrouter.ai/api/v1",
        model="openrouter/free",
        timeout_seconds=3,
        provider_name="openrouter",
        max_retries=1,
        retry_base_seconds=0,
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(
        provider.generate_json(
            system_prompt="Return JSON.",
            user_payload={"question": "test"},
            json_schema={
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
                "additionalProperties": False,
            },
        )
    )

    assert result == {"answer": "ok"}
    assert calls == 2
