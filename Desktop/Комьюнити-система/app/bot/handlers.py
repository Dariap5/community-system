from __future__ import annotations

from aiogram import F, Router, types
from aiogram.filters import CommandObject, CommandStart
from sqlalchemy import String, cast, func, select

from app.bot.keyboards import MENU_MY_SUBS, MENU_OFFER, MENU_PRODUCTS, MENU_SUPPORT, main_menu
from app.config import settings
from app.db.models import Funnel, FunnelStep, PaymentStatus, Purchase, User, UserTag
from app.db.session import AsyncSessionLocal
from app.funnels.actions import handle_action
from app.funnels.callback_store import resolve_callback_reference
from app.funnels.engine import FunnelEngine
from app.products import PRODUCTS
from app.schemas.step_config import ButtonGroup, StepConfig


router = Router()


@router.message(CommandStart(deep_link=True))
async def handle_start_with_deeplink(message: types.Message, command: CommandObject) -> None:
    await _handle_start(message, deeplink=command.args or None)


@router.message(CommandStart())
async def handle_start_plain(message: types.Message) -> None:
    await _handle_start(message, deeplink=None)


async def _handle_start(message: types.Message, deeplink: str | None) -> None:
    async with AsyncSessionLocal() as db:
        user = await db.get(User, message.from_user.id)
        if user is None:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                source_deeplink=deeplink,
            )
            db.add(user)
            await db.commit()
            user = await db.get(User, message.from_user.id)
        elif deeplink and not user.source_deeplink:
            user.source_deeplink = deeplink
            await db.commit()

        await message.answer("Привет! 👋", reply_markup=main_menu())

        funnel_key = deeplink or settings.default_funnel_key
        result = await db.execute(
            select(Funnel).where(
                Funnel.entry_key == funnel_key,
                Funnel.is_active.is_(True),
            )
        )
        funnel = result.scalar_one_or_none()
        if funnel is None:
            return

        engine = FunnelEngine(bot=message.bot, db=db)
        await engine.start_funnel(user, funnel)


@router.callback_query(F.data.startswith("btn:"))
async def handle_button_click(callback: types.CallbackQuery) -> None:
    await callback.answer()

    async with AsyncSessionLocal() as db:
        user = await db.get(User, callback.from_user.id)
        if user is None:
            return

        engine = FunnelEngine(bot=callback.bot, db=db)
        await engine.handle_button_click(user, callback.data or "")


@router.message(F.text == MENU_PRODUCTS)
async def handle_menu_products(message: types.Message) -> None:
    if not PRODUCTS:
        await message.answer("Пока нет доступных продуктов")
        return

    text = ["<b>Доступные продукты:</b>", ""]
    for product_id, product in PRODUCTS.items():
        text.append(f"• <b>{product['name']}</b> — {product['price']} ₽")
        text.append(str(product["description"]))
        text.append("")

    text.append("Чтобы купить — пройдите через /start и выберите подходящий вариант.")
    await message.answer("\n".join(text))


@router.message(F.text == MENU_MY_SUBS)
async def handle_menu_my_subs(message: types.Message) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Purchase)
            .where(
                Purchase.user_id == message.from_user.id,
                Purchase.status == PaymentStatus.paid,
            )
            .order_by(Purchase.paid_at.desc())
        )
        purchases = result.scalars().all()

        if not purchases:
            await message.answer("У вас пока нет активных подписок.")
            return

        tag_result = await db.execute(select(UserTag).where(UserTag.user_id == message.from_user.id))
        tags = {tag.tag for tag in tag_result.scalars().all()}

        text = ["<b>Ваши подписки:</b>", ""]
        for purchase in purchases:
            product = PRODUCTS.get(purchase.product_id, {"name": purchase.product_id})
            paid_at = purchase.paid_at.strftime("%d.%m.%Y") if purchase.paid_at else "—"
            text.append(f"• {product['name']} ({paid_at})")

            if purchase.product_id == "community":
                text.append(f"  Общий чат: {settings.community_chat_url}")
                if "track_career" in tags:
                    text.append(f"  Трек Карьера: {settings.track_career_url}")
                if "track_business" in tags:
                    text.append(f"  Трек Бизнес: {settings.track_business_url}")
                if "track_selfdev" in tags:
                    text.append(f"  Трек Саморазвитие: {settings.track_selfdev_url}")

            text.append("")

        await message.answer("\n".join(text))


@router.message(F.text == MENU_SUPPORT)
async def handle_menu_support(message: types.Message) -> None:
    if settings.support_username:
        await message.answer(f"По всем вопросам пишите: @{settings.support_username}")
    else:
        await message.answer("Контакт поддержки скоро появится")


@router.message(F.text == MENU_OFFER)
async def handle_menu_offer(message: types.Message) -> None:
    if settings.offer_url:
        await message.answer(f"Оферта доступна по ссылке:\n{settings.offer_url}")
    else:
        await message.answer("Оферта скоро будет доступна")