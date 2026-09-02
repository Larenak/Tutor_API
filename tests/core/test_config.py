import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_requires_a_strong_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(
            app_name="AI Tutor",
            environment="production",
            database_url="postgresql+psycopg://user:password@localhost/database",
            jwt_secret_key="short-secret-123",
            access_token_expire_minutes=15,
            refresh_token_expire_days=30,
            cors_origins="https://example.com",
        )


def test_development_accepts_a_local_jwt_secret() -> None:
    settings = Settings(
        app_name="AI Tutor",
        environment="development",
        database_url="postgresql+psycopg://user:password@localhost/database",
        jwt_secret_key="local-secret-123",
        access_token_expire_minutes=15,
        refresh_token_expire_days=30,
        cors_origins="http://127.0.0.1:8000",
    )

    assert settings.environment == "development"


def test_openrouter_is_free_only_by_default() -> None:
    settings = Settings(
        app_name="AI Tutor",
        environment="development",
        database_url="postgresql+psycopg://user:password@localhost/database",
        jwt_secret_key="local-secret-123",
        access_token_expire_minutes=15,
        refresh_token_expire_days=30,
        cors_origins="http://127.0.0.1:8000",
        _env_file=None,
    )

    assert settings.openrouter_model == "openrouter/free"
    assert settings.openrouter_free_only is True
