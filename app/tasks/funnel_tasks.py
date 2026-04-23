from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.session import IPv4OnlySession
from app.config import settings
from app.db.models import FunnelStep, ScheduledTask, ScheduledTaskStatus, User
from app.db.session import AsyncSessionLocal
from app.funnels.engine import FunnelEngine
from app.tasks.celery_app import celery_app


logger = logging.getLogger(__name__)


@celery_app.task
def process_scheduled_tasks() -> None:
    asyncio.run(_process())


async def _process() -> None:
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        async with db.begin():
            result = await db.execute(
                select(ScheduledTask)
                .where(
                    ScheduledTask.status == ScheduledTaskStatus.pending,
                    ScheduledTask.execute_at <= now,
                )
                .order_by(ScheduledTask.execute_at)
                .limit(10)
                .with_for_update(skip_locked=True)
            )
            tasks = result.scalars().all()
            for task in tasks:
                task.status = ScheduledTaskStatus.processing

        for task in tasks:
            try:
                await _process_task(db, task)
                task.status = ScheduledTaskStatus.done
            except Exception:
                logger.exception("Task %s failed", task.id)
                task.status = ScheduledTaskStatus.failed
            await db.commit()


async def _process_task(db: AsyncSession, task: ScheduledTask) -> None:
    payload = task.payload or {}
    step_id = UUID(str(payload["step_id"]))
    start_index = int(payload.get("start_index", 0))
    skip_initial_delay = bool(payload.get("skip_initial_delay", False))

    step = await db.get(FunnelStep, step_id)
    user = await db.get(User, task.user_id)
    if step is None or user is None:
        return

    session = IPv4OnlySession()
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
        session=session,
    )

    try:
        engine = FunnelEngine(bot=bot, db=db)
        await engine.execute_step(user, step, start_index=start_index, skip_initial_delay=skip_initial_delay)
    finally:
        await bot.session.close()