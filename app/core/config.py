from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str
    environment: str
    database_url: str
    jwt_secret_key: str = Field(min_length=16)
    access_token_expire_minutes: int = Field(gt=0)
    refresh_token_expire_days: int = Field(gt=0)
    cors_origins: str
    ai_provider: str = "deepseek"
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_timeout_seconds: float = 30.0
    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openrouter/free"
    openrouter_free_only: bool = True
    openrouter_timeout_seconds: float = 25.0
    openrouter_max_retries: int = 2
    openrouter_site_url: str = "http://127.0.0.1:8000"
    openrouter_app_name: str = "AI Tutor"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_jwt_secret(self) -> "Settings":
        if self.environment.lower() in {"production", "prod"} and len(self.jwt_secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 characters in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
