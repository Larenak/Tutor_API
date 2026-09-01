import asyncio
import json

import httpx
import pytest
from pydantic import SecretStr

from app.modules.ai.provider import (
    AIProviderAuthenticationFailed,
    DeepSeekProvider,
)


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
