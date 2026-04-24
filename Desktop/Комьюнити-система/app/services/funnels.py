from __future__ import annotations

import json
import uuid
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Funnel, FunnelCrossEntryBehavior, FunnelStatus, FunnelStep, UserFunnelState
from app.schemas.step_config import StepConfig, TextMessage


def _cross_entry_behavior_value(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


async def get_funnel_with_stats(db: AsyncSession, funnel_id: UUID) -> dict[str, object] | None:
    funnel = await db.get(Funnel, funnel_id)
    if funnel is None:
        return None

    steps_count_result = await db.execute(select(func.count(FunnelStep.id)).where(FunnelStep.funnel_id == funnel_id))
    steps_count = int(steps_count_result.scalar_one())

    active_users_result = await db.execute(
        select(func.count(func.distinct(UserFunnelState.user_id))).where(
            UserFunnelState.funnel_id == funnel_id,
            UserFunnelState.status == FunnelStatus.active,
        )
    )
    active_users_count = int(active_users_result.scalar_one())

    return {
        "id": funnel.id,
        "name": funnel.name,
        "entry_key": funnel.entry_key,
        "is_active": funnel.is_active,
        "is_archived": funnel.is_archived,
        "cross_entry_behavior": _cross_entry_behavior_value(funnel.cross_entry_behavior),
        "created_at": funnel.created_at,
        "updated_at": funnel.updated_at,
        "steps_count": steps_count,
        "active_users_count": active_users_count,
    }


def extract_first_message_preview(config_dict: dict[str, object]) -> str:
    try:
        config = StepConfig(**config_dict)
        for block in config.blocks:
            if isinstance(block, TextMessage):
                preview = block.content[:80]
                return preview + "..." if len(block.content) > 80 else preview
    except Exception:
        return ""
    return ""


async def get_next_order(db: AsyncSession, funnel_id: UUID) -> int:
    result = await db.execute(select(func.max(FunnelStep.order)).where(FunnelStep.funnel_id == funnel_id))
    max_order = result.scalar_one()
    return int(max_order or 0) + 1


async def has_active_users_on_step(db: AsyncSession, step_id: UUID) -> bool:
    result = await db.execute(
        select(func.count(UserFunnelState.id)).where(
            UserFunnelState.current_step_id == step_id,
            UserFunnelState.status == FunnelStatus.active,
        )
    )
    return int(result.scalar_one()) > 0


async def duplicate_funnel(db: AsyncSession, source_id: UUID) -> Funnel | None:
    source = await db.get(Funnel, source_id)
    if source is None:
        return None

    new_funnel = Funnel(
        name=f"{source.name} (копия)",
        entry_key=None,
        is_active=False,
        is_archived=False,
        cross_entry_behavior=_cross_entry_behavior_value(source.cross_entry_behavior),
    )
    db.add(new_funnel)
    await db.flush()

    result = await db.execute(select(FunnelStep).where(FunnelStep.funnel_id == source_id).order_by(FunnelStep.order))
    for step in result.scalars().all():
        config_dict = json.loads(json.dumps(step.config))
        for block in config_dict.get("blocks", []):
            if isinstance(block, dict):
                block["id"] = str(uuid.uuid4())
                if block.get("type") == "buttons":
                    for button in block.get("buttons", []):
                        if isinstance(button, dict):
                            button["id"] = str(uuid.uuid4())

        new_step = FunnelStep(
            funnel_id=new_funnel.id,
            order=step.order,
            name=step.name,
            step_key=step.step_key,
            is_active=step.is_active,
            config=config_dict,
        )
        db.add(new_step)

    await db.commit()
    await db.refresh(new_funnel)
    return new_funnel
