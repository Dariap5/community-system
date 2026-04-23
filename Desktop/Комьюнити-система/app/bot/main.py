from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from app.bot.handlers import router as main_router
from app.bot.session import IPv4OnlySession
from app.config import settings


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_bot() -> None:
    session = IPv4OnlySession()
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
        session=session,
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(main_router)

    try:
        logger.info("Starting bot polling...")
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run_bot())