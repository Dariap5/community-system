from __future__ import annotations

from decimal import Decimal
from typing import Any

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FunnelStep, PaymentStatus, Purchase, User, UserTag
from app.products import PRODUCTS
from app.schemas.step_config import ActionAddTag, ActionGotoStep, ActionPayProduct, ActionUrl, ButtonAction
from app.services.payments import PaymentProviderError, create_payment_offer


async def handle_action(
    bot: Bot,
    db: AsyncSession,
    user: User,
    action: ButtonAction,
    engine: Any,
    current_step: FunnelStep,
) -> None:
    if isinstance(action, ActionUrl):
        return

    if isinstance(action, ActionAddTag):
        existing = await db.execute(
            select(UserTag).where(UserTag.user_id == user.telegram_id, UserTag.tag == action.value)
        )
        if existing.scalar_one_or_none() is None:
            db.add(UserTag(user_id=user.telegram_id, tag=action.value))
            await db.commit()
        return

    if isinstance(action, ActionGotoStep):
        result = await db.execute(
            select(FunnelStep).where(
                FunnelStep.funnel_id == current_step.funnel_id,
                FunnelStep.step_key == action.value,
            )
        )
        target = result.scalar_one_or_none()
        if target is not None:
            await engine._update_user_state(user, current_step.funnel_id, target.id)
            await engine.execute_step(user, target)
        return

    if isinstance(action, ActionPayProduct):
        product = PRODUCTS.get(action.value)
        if product is None:
            await bot.send_message(user.telegram_id, "Продукт не найден")
            return

        amount = Decimal(str(product["price"]))

        try:
            offer = await create_payment_offer(
                bot,
                product_id=action.value,
                product_name=product["name"],
                amount=amount,
                user_id=user.telegram_id,
            )
        except PaymentProviderError:
            await bot.send_message(user.telegram_id, "Не удалось создать платёж. Попробуйте позже.")
            return

        if offer.is_stub:
            purchase = Purchase(
                user_id=user.telegram_id,
                funnel_id=current_step.funnel_id,
                product_id=action.value,
                amount=amount,
                status=PaymentStatus.pending,
            )
            db.add(purchase)
            await db.commit()

            await bot.send_message(
                user.telegram_id,
                (
                    f"💳 Оплата продукта <b>{product['name']}</b>\n"
                    f"Сумма: {product['price']} ₽\n\n"
                    "<i>Заглушка для Промпта 2. В Промпте 3 будет реальная ссылка на оплату.</i>"
                ),
                parse_mode="HTML",
            )
            return

        purchase = Purchase(
            user_id=user.telegram_id,
            funnel_id=current_step.funnel_id,
            product_id=action.value,
            amount=amount,
            status=PaymentStatus.pending,
            payment_provider_id=offer.provider_payment_id,
        )
        db.add(purchase)
        await db.commit()

        pay_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"Оплатить {product['price']} ₽",
                        url=offer.payment_url or "https://t.me",
                    )
                ]
            ]
        )

        await bot.send_message(
            user.telegram_id,
            (
                f"💳 Для оплаты <b>{product['name']}</b> нажмите кнопку ниже.\n"
                "После оплаты вернитесь в бот — доступ откроется автоматически."
            ),
            parse_mode="HTML",
            reply_markup=pay_kb,
        )
        return