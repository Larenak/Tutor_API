from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.database.session import get_db
from app.main import app


@pytest.fixture
def db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def client(db: AsyncMock) -> AsyncGenerator[TestClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncMock, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
