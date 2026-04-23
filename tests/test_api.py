from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.main import app
from app.config import settings
from app.db.models import Funnel
from app.db.session import AsyncSessionLocal


BASE_URL = f"/api/{settings.admin_secret_path}"


@pytest.mark.asyncio
async def test_health_no_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_wrong_secret_returns_404() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/wrong-secret/funnels")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_list_funnels_includes_welcome() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"{BASE_URL}/funnels")

    assert response.status_code == 200
    assert any(funnel["entry_key"] == "welcome" for funnel in response.json())


@pytest.mark.asyncio
async def test_get_funnel_details() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        funnels_response = await client.get(f"{BASE_URL}/funnels")
        funnel_id = next(item["id"] for item in funnels_response.json() if item["entry_key"] == "welcome")
        response = await client.get(f"{BASE_URL}/funnels/{funnel_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["steps_count"] == 5
    assert len(payload["steps"]) == 5
    assert payload["steps"][0]["step_key"] == "welcome_intro"


@pytest.mark.asyncio
async def test_create_funnel_and_cleanup() -> None:
    entry_key = f"test_{uuid4().hex[:12]}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"{BASE_URL}/funnels",
            json={"name": "Test funnel", "entry_key": entry_key},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Test funnel"
    assert payload["entry_key"] == entry_key

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Funnel).where(Funnel.entry_key == entry_key))
        funnel = result.scalar_one_or_none()
        if funnel is not None:
            await db.delete(funnel)
            await db.commit()


@pytest.mark.asyncio
async def test_duplicate_entry_key_returns_409() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"{BASE_URL}/funnels",
            json={"name": "Duplicate", "entry_key": "welcome"},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


@pytest.mark.asyncio
async def test_analytics_summary() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"{BASE_URL}/analytics/summary")

    assert response.status_code == 200
    payload = response.json()
    assert "total_users_count" in payload
    assert "revenue_total" in payload


@pytest.mark.asyncio
async def test_webhook_ignores_unrelated_events() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/payments/webhook", json={"event": "ping", "object": {}})

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
