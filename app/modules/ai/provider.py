import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from pydantic import SecretStr

from app.core.config import get_settings


class AIProviderNotConfigured(RuntimeError):
    """Raised when an AI request is made before an API key is configured."""


class AIProviderRequestFailed(RuntimeError):
    """Raised when the remote provider cannot return a usable response."""


class AIProviderAuthenticationFailed(AIProviderRequestFailed):
    """Raised when DeepSeek rejects the configured API key."""


class AIProviderBalanceExhausted(AIProviderRequestFailed):
    """Raised when the DeepSeek account has insufficient balance."""


class AIProviderRateLimited(AIProviderRequestFailed):
    """Raised when DeepSeek rate-limits the request."""


class AIProvider(Protocol):
    provider_name: str
    model: str

    @property
    def configured(self) -> bool: ...

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, object],
        max_tokens: int = 900,
    ) -> dict[str, Any]: ...


def _parse_json_content(content: str) -> dict[str, Any]:
    value = content.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        value = "\n".join(lines).strip()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise AIProviderRequestFailed("AI provider returned invalid JSON") from error
    if not isinstance(parsed, dict):
        raise AIProviderRequestFailed("AI provider returned an unexpected response shape")
    return parsed


@dataclass(slots=True)
class DeepSeekProvider:
    api_key: SecretStr | None
    base_url: str
    model: str
    timeout_seconds: float
    provider_name: str = "deepseek"
    extra_headers: dict[str, str] | None = None
    request_extra: dict[str, object] | None = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_key.get_secret_value().strip())

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, object],
        max_tokens: int = 900,
    ) -> dict[str, Any]:
        if not self.configured or self.api_key is None:
            raise AIProviderNotConfigured("DeepSeek API key is not configured")

        request_body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                },
            ],
            "response_format": {"type": "json_object"},
            "stream": False,
            "max_tokens": max_tokens,
        }
        if self.request_extra:
            request_body.update(self.request_extra)
        api_key = self.api_key.get_secret_value().strip()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if self.extra_headers:
            headers.update(self.extra_headers)
        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(endpoint, headers=headers, json=request_body)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as error:
            if error.response.status_code in {401, 403}:
                raise AIProviderAuthenticationFailed(
                    f"{self.provider_name} rejected the configured API key"
                ) from error
            if error.response.status_code == 402:
                raise AIProviderBalanceExhausted(
                    f"{self.provider_name} account balance is insufficient"
                ) from error
            if error.response.status_code == 429:
                raise AIProviderRateLimited(
                    f"{self.provider_name} rate limit reached"
                ) from error
            raise AIProviderRequestFailed(
                f"{self.provider_name} API request failed"
            ) from error
        except (httpx.HTTPError, ValueError) as error:
            raise AIProviderRequestFailed(
                f"{self.provider_name} API request failed"
            ) from error

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise AIProviderRequestFailed("DeepSeek API returned an incomplete response") from error
        if not isinstance(content, str) or not content.strip():
            raise AIProviderRequestFailed("DeepSeek API returned an empty response")
        return _parse_json_content(content)


def get_ai_provider() -> AIProvider:
    settings = get_settings()
    provider_name = settings.ai_provider.lower()
    deepseek_key = settings.deepseek_api_key
    openrouter_key = settings.openrouter_api_key
    deepseek_key_value = (
        deepseek_key.get_secret_value().strip() if deepseek_key is not None else ""
    )
    use_openrouter = (
        provider_name == "openrouter"
        or openrouter_key is not None
        or deepseek_key_value.startswith("sk-or-")
    )
    if use_openrouter:
        return DeepSeekProvider(
            api_key=openrouter_key or deepseek_key,
            base_url=settings.openrouter_base_url,
            model=settings.openrouter_model,
            timeout_seconds=settings.openrouter_timeout_seconds,
            provider_name="openrouter",
            extra_headers={
                "HTTP-Referer": settings.openrouter_site_url,
                "X-OpenRouter-Title": settings.openrouter_app_name,
            },
            request_extra={"reasoning": {"effort": "none"}},
        )
    if provider_name != "deepseek":
        return DeepSeekProvider(
            api_key=None,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
            timeout_seconds=settings.deepseek_timeout_seconds,
            provider_name=provider_name,
        )
    return DeepSeekProvider(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        timeout_seconds=settings.deepseek_timeout_seconds,
        request_extra={"thinking": {"type": "disabled"}},
    )
