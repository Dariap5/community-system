"""Pytest fixtures for API tests.

Supports two modes:
1. Docker Compose - uses DATABASE_URL from .env (main CI path)
2. Local - if TEST_DATABASE_URL is provided, it overrides DATABASE_URL
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


test_database_url = os.getenv("TEST_DATABASE_URL")
if test_database_url:
    os.environ["DATABASE_URL"] = test_database_url


@pytest_asyncio.fixture
async def client() -> AsyncClient:
	"""HTTP client for API tests."""

	from app.api.main import app

	async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
		yield http_client


@pytest.fixture
def secret() -> str:
	"""Admin secret from settings."""

	from app.config import settings

	return settings.admin_secret_path


@pytest.fixture
def api_base(secret: str) -> str:
	"""Base API path with the secret embedded."""

	return f"/api/{secret}"