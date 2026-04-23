from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from aiogram import Bot
from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Funnel,
    FunnelCrossEntryBehavior,
    FunnelStatus,
    FunnelStep,
    ScheduledTask,
    ScheduledTaskStatus,
    User,
    UserFunnelState,
    UserTag,
)
from app.funnels.actions import handle_action
from app.funnels.callback_store import resolve_callback_reference
from app.funnels.keyboard_builder import build_keyboard
from app.funnels.message_sender import SendResult, send_block
from app.schemas.step_config import ButtonGroup, StepConfig


logger = logging.getLogger(__name__)

INLINE_DELAY_THRESHOLD = 60


class FunnelEngine:
    """Оркестратор воронок: запуск, выполнение шагов и реакции на кнопки."""

    def __init__(self, bot: Bot, db: AsyncSession) -> None:
        self.bot = bot
        self.db = db

    async def start_funnel(self, user: User, funnel: Funnel) -> None:
        result = await self.db.execute(
            select(UserFunnelState).where(
                UserFunnelState.user_id == user.telegram_id,
                UserFunnelState.status == FunnelStatus.active,
            )
        )
        active_states = result.scalars().all()

        if active_states and funnel.cross_entry_behavior == FunnelCrossEntryBehavior.deny:
            logger.info("User %s already has an active funnel, skipping %s", user.telegram_id, funnel.entry_key)
            return

        first_step = await self._get_first_step(funnel.id)
        if first_step is None:
            logger.warning("Funnel %s has no steps", funnel.id)
            return

        state = UserFunnelState(
            user_id=user.telegram_id,
            funnel_id=funnel.id,
            current_step_id=first_step.id,
            status=FunnelStatus.active,
        )
        self.db.add(state)
        await self.db.commit()

        await self.execute_step(user, first_step)

    async def execute_step(
        self,
        user: User,
        step: FunnelStep,
        *,
        start_index: int = 0,
        skip_initial_delay: bool = False,
    ) -> None:
        try:
            config = StepConfig(**step.config)
        except Exception as exc:
            logger.error("Invalid step config %s: %s", step.id, exc)
            return

        if not skip_initial_delay and config.delay_before_seconds > 0:
            if config.delay_before_seconds <= INLINE_DELAY_THRESHOLD:
                await asyncio.sleep(config.delay_before_seconds)
            else:
                await self._schedule_step_run(
                    user=user,
                    step=step,
                    delay_seconds=config.delay_before_seconds,
                    start_index=start_index,
                    skip_initial_delay=True,
                )
                return

        keyboard = await build_keyboard(config, step.id)

        for index, block in enumerate(config.blocks[start_index:], start=start_index):
            if block.type == "buttons":
                continue

            reply_markup = keyboard if self._is_last_message_block(config, index) else None
            result = await send_block(self.bot, user.telegram_id, block, reply_markup=reply_markup)

            if result in {SendResult.BLOCKED, SendResult.BAD_REQUEST}:
                await self._pause_active_funnels(user.telegram_id)
                return

            if result is SendResult.FAILED:
                logger.warning("Message block %s failed for user %s, continuing", getattr(block, "id", None), user.telegram_id)

            delay_after = getattr(block, "delay_after", 0)
            if delay_after > 0:
                if delay_after <= INLINE_DELAY_THRESHOLD:
                    await asyncio.sleep(delay_after)
                else:
                    await self._schedule_step_run(
                        user=user,
                        step=step,
                        delay_seconds=delay_after,
                        start_index=index + 1,
                        skip_initial_delay=True,
                    )
                    return

        await self._apply_step_tags(user.telegram_id, config)

        if config.wait_for_payment:
            logger.info("Step %s waits for payment", step.id)
            return

        if any(isinstance(block, ButtonGroup) for block in config.blocks):
            logger.info("Step %s waits for button action", step.id)
            return

        next_step = await self._resolve_next_step(step, config)
        if next_step is not None:
            await self._update_user_state(user, step.funnel_id, next_step.id)
            await self.execute_step(user, next_step)
        else:
            await self._complete_funnel(user, step.funnel_id)

    async def handle_button_click(self, user: User, callback_data: str) -> None:
        parts = callback_data.split(":")
        if len(parts) != 3:
            return

        _, step_short, button_short = parts

        resolved = await resolve_callback_reference(callback_data)
        step: FunnelStep | None = None
        button = None

        if resolved is not None:
            step_id, button_id = resolved
            step = await self.db.get(FunnelStep, step_id)
            if step is not None:
                button = self._find_button_by_full_id(StepConfig(**step.config), button_id)

        if step is None:
            step = await self._find_step_by_short_id(step_short)
        if step is None:
            return

        if button is None:
            button = self._find_button_by_short_id(StepConfig(**step.config), button_short)
        if button is None:
            return

        await handle_action(
            bot=self.bot,
            db=self.db,
            user=user,
            action=button.action,
            engine=self,
            current_step=step,
        )

    async def continue_after_payment(self, user: User, funnel_id: UUID) -> None:
        result = await self.db.execute(
            select(UserFunnelState).where(
                UserFunnelState.user_id == user.telegram_id,
                UserFunnelState.funnel_id == funnel_id,
                UserFunnelState.status == FunnelStatus.active,
            )
            .order_by(UserFunnelState.started_at.desc(), UserFunnelState.updated_at.desc())
            .limit(1)
        )
        state = result.scalars().first()
        if state is None or state.current_step_id is None:
            return

        current_step = await self.db.get(FunnelStep, state.current_step_id)
        if current_step is None:
            return

        config = StepConfig(**current_step.config)
        next_step = await self._resolve_next_step(current_step, config)
        if next_step is not None:
            await self._update_user_state(user, funnel_id, next_step.id)
            await self.execute_step(user, next_step)

    async def _get_first_step(self, funnel_id: UUID) -> FunnelStep | None:
        result = await self.db.execute(
            select(FunnelStep)
            .where(FunnelStep.funnel_id == funnel_id, FunnelStep.is_active.is_(True))
            .order_by(FunnelStep.order)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _resolve_next_step(self, current: FunnelStep, config: StepConfig) -> FunnelStep | None:
        if config.next_step == "end":
            return None

        if config.next_step == "auto":
            result = await self.db.execute(
                select(FunnelStep)
                .where(
                    FunnelStep.funnel_id == current.funnel_id,
                    FunnelStep.order > current.order,
                    FunnelStep.is_active.is_(True),
                )
                .order_by(FunnelStep.order)
                .limit(1)
            )
            return result.scalar_one_or_none()

        result = await self.db.execute(
            select(FunnelStep).where(
                FunnelStep.funnel_id == current.funnel_id,
                FunnelStep.step_key == config.next_step,
            )
        )
        return result.scalar_one_or_none()

    async def _update_user_state(self, user: User, funnel_id: UUID, step_id: UUID) -> None:
        result = await self.db.execute(
            select(UserFunnelState).where(
                UserFunnelState.user_id == user.telegram_id,
                UserFunnelState.funnel_id == funnel_id,
                UserFunnelState.status == FunnelStatus.active,
            )
            .order_by(UserFunnelState.started_at.desc(), UserFunnelState.updated_at.desc())
            .limit(1)
        )
        state = result.scalars().first()
        if state is not None:
            state.current_step_id = step_id
            state.status = FunnelStatus.active
            await self.db.commit()

    async def _complete_funnel(self, user: User, funnel_id: UUID) -> None:
        result = await self.db.execute(
            select(UserFunnelState).where(
                UserFunnelState.user_id == user.telegram_id,
                UserFunnelState.funnel_id == funnel_id,
                UserFunnelState.status == FunnelStatus.active,
            )
            .order_by(UserFunnelState.started_at.desc(), UserFunnelState.updated_at.desc())
            .limit(1)
        )
        state = result.scalars().first()
        if state is not None:
            state.status = FunnelStatus.completed
            await self.db.commit()

    async def _pause_active_funnels(self, user_id: int) -> None:
        result = await self.db.execute(
            select(UserFunnelState).where(
                UserFunnelState.user_id == user_id,
                UserFunnelState.status == FunnelStatus.active,
            )
        )
        states = result.scalars().all()
        for state in states:
            state.status = FunnelStatus.paused
        if states:
            await self.db.commit()

    async def _apply_step_tags(self, user_id: int, config: StepConfig) -> None:
        for tag in config.add_tags_after:
            existing = await self.db.execute(
                select(UserTag).where(UserTag.user_id == user_id, UserTag.tag == tag)
            )
            if existing.scalar_one_or_none() is None:
                self.db.add(UserTag(user_id=user_id, tag=tag))
        await self.db.commit()

    async def _schedule_step_run(
        self,
        *,
        user: User,
        step: FunnelStep,
        delay_seconds: int,
        start_index: int,
        skip_initial_delay: bool,
    ) -> None:
        execute_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        task = ScheduledTask(
            user_id=user.telegram_id,
            task_type="execute_step",
            payload={
                "step_id": str(step.id),
                "start_index": start_index,
                "skip_initial_delay": skip_initial_delay,
            },
            execute_at=execute_at,
            status=ScheduledTaskStatus.pending,
        )
        self.db.add(task)
        await self.db.commit()
        logger.info("Scheduled step %s for %s", step.id, execute_at)

    async def _find_step_by_short_id(self, step_short: str) -> FunnelStep | None:
        result = await self.db.execute(
            select(FunnelStep).where(
                func.replace(cast(FunnelStep.id, String), "-", "").like(f"{step_short}%")
            )
        )
        return result.scalar_one_or_none()

    def _find_button_by_short_id(self, config: StepConfig, button_short: str):
        for block in config.blocks:
            if isinstance(block, ButtonGroup):
                for button in block.buttons:
                    if button.id.hex.startswith(button_short):
                        return button
        return None

    def _find_button_by_full_id(self, config: StepConfig, button_id: UUID):
        for block in config.blocks:
            if isinstance(block, ButtonGroup):
                for button in block.buttons:
                    if button.id == button_id:
                        return button
        return None

    def _is_last_message_block(self, config: StepConfig, current_index: int) -> bool:
        button_group_index: int | None = None
        for index, block in enumerate(config.blocks):
            if block.type == "buttons":
                button_group_index = index
                break

        if button_group_index is None:
            return False

        last_message_index = -1
        for index in range(button_group_index):
            if config.blocks[index].type != "buttons":
                last_message_index = index

        return current_index == last_message_index