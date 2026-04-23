from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass
from decimal import Decimal

import httpx
from aiogram import Bot

from app.config import settings


@dataclass(slots=True)
class PaymentOffer:
    provider: str
    provider_payment_id: str | None
    payment_url: str | None
    is_stub: bool = False


class PaymentProviderError(RuntimeError):
    pass


async def create_payment_offer(
    bot: Bot,
    *,
    product_id: str,
    product_name: str,
    amount: Decimal,
    user_id: int,
) -> PaymentOffer:
    if not settings.yookassa_shop_id or not settings.yookassa_secret_key:
        return PaymentOffer(provider="stub", provider_payment_id=None, payment_url=None, is_stub=True)

    bot_username = (await bot.get_me()).username or ""
    auth = base64.b64encode(f"{settings.yookassa_shop_id}:{settings.yookassa_secret_key}".encode()).decode()

    payload = {
        "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": f"https://t.me/{bot_username}" if bot_username else "https://t.me",
        },
        "description": product_name,
        "metadata": {
            "user_id": str(user_id),
            "product_id": product_id,
        },
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            "https://api.yookassa.ru/v3/payments",
            json=payload,
            headers={
                "Authorization": f"Basic {auth}",
                "Idempotence-Key": uuid.uuid4().hex,
                "Content-Type": "application/json",
            },
        )

    if response.status_code >= 400:
        raise PaymentProviderError(f"YooKassa returned {response.status_code}")

    data = response.json()
    return PaymentOffer(
        provider="yookassa",
        provider_payment_id=data["id"],
        payment_url=data["confirmation"]["confirmation_url"],
        is_stub=False,
    )
