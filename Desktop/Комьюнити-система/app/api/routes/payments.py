from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.bot.session import IPv4OnlySession
from app.config import settings
from app.db.models import FunnelStatus, PaymentStatus, Purchase, User, UserFunnelState
from app.funnels.engine import FunnelEngine


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments")


@router.post("/webhook")
async def yookassa_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    event = data.get("event")
    obj = data.get("object", {})

    if event not in {"payment.succeeded", "payment.waiting_for_capture"}:
        return {"status": "ignored"}

    payment_id = obj.get("id")
    if not payment_id:
        raise HTTPException(
            status_code=400,
            detail={"code": "bad_request", "message": "Missing payment id"},
        )

    async with db.begin():
        result = await db.execute(
            select(Purchase).where(Purchase.payment_provider_id == payment_id).with_for_update()
        )
        purchase = result.scalar_one_or_none()

        if purchase is None:
            return {"status": "not_found"}

        if purchase.status == PaymentStatus.paid:
            return {"status": "already_processed"}

        purchase.status = PaymentStatus.paid
        purchase.paid_at = datetime.now(timezone.utc)

    user = await db.get(User, purchase.user_id)
    if user is None:
        return {"status": "ok"}

    target_funnel_id = purchase.funnel_id
    if target_funnel_id is None:
        state_result = await db.execute(
            select(UserFunnelState)
            .where(
                UserFunnelState.user_id == user.telegram_id,
                UserFunnelState.status == FunnelStatus.active,
            )
            .order_by(UserFunnelState.started_at.desc(), UserFunnelState.updated_at.desc())
            .limit(1)
        )
        state = state_result.scalars().first()
        if state is None:
            return {"status": "ok"}
        target_funnel_id = state.funnel_id

    if target_funnel_id is None:
        return {"status": "ok"}

    session = IPv4OnlySession()
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"), session=session)
    try:
        engine = FunnelEngine(bot=bot, db=db)
        await engine.continue_after_payment(user, target_funnel_id)
    finally:
        await bot.session.close()

    return {"status": "ok"}
