from __future__ import annotations

import json
from uuid import UUID

from redis.asyncio import Redis

from app.config import settings


CALLBACK_TTL_SECONDS = 24 * 60 * 60
CALLBACK_KEY_PREFIX = "callback-map:"


def _redis_client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


async def store_callback_reference(callback_data: str, step_id: UUID, button_id: UUID) -> None:
    client = _redis_client()
    try:
        payload = json.dumps({"step_id": str(step_id), "button_id": str(button_id)})
        await client.setex(f"{CALLBACK_KEY_PREFIX}{callback_data}", CALLBACK_TTL_SECONDS, payload)
    finally:
        await client.aclose()


async def resolve_callback_reference(callback_data: str) -> tuple[UUID, UUID] | None:
    client = _redis_client()
    try:
        payload = await client.get(f"{CALLBACK_KEY_PREFIX}{callback_data}")
    finally:
        await client.aclose()

    if not payload:
        return None

    data = json.loads(payload)
    return UUID(data["step_id"]), UUID(data["button_id"])