from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, verify_secret
from app.db.models import Funnel, FunnelStep, FunnelStatus, User, UserFunnelState
from app.schemas.api import UserListItem


router = APIRouter(prefix="/api/{secret}", dependencies=[Depends(verify_secret)])


@router.get("/users", response_model=list[UserListItem])
async def list_users(limit: int = 100, offset: int = 0, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User)
        .options(selectinload(User.tags), selectinload(User.funnel_states))
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    users = result.scalars().all()

    active_states: list[UserFunnelState] = []
    for user in users:
        active_states.extend([state for state in user.funnel_states if state.status == FunnelStatus.active])

    funnel_ids = {state.funnel_id for state in active_states}
    step_ids = {state.current_step_id for state in active_states if state.current_step_id is not None}

    funnels_map: dict[object, Funnel] = {}
    if funnel_ids:
        funnels_result = await db.execute(select(Funnel).where(Funnel.id.in_(funnel_ids)))
        funnels_map = {funnel.id: funnel for funnel in funnels_result.scalars().all()}

    steps_map: dict[object, FunnelStep] = {}
    if step_ids:
        steps_result = await db.execute(select(FunnelStep).where(FunnelStep.id.in_(step_ids)))
        steps_map = {step.id: step for step in steps_result.scalars().all()}

    items: list[UserListItem] = []
    fallback_time = datetime.min.replace(tzinfo=timezone.utc)

    for user in users:
        active = [state for state in user.funnel_states if state.status == FunnelStatus.active]
        active_state = max(active, key=lambda state: state.started_at or fallback_time) if active else None

        funnel_name = None
        step_name = None
        if active_state is not None:
            funnel = funnels_map.get(active_state.funnel_id)
            step = steps_map.get(active_state.current_step_id) if active_state.current_step_id else None
            funnel_name = funnel.name if funnel else None
            step_name = step.name if step else None

        items.append(
            UserListItem(
                telegram_id=user.telegram_id,
                username=user.username,
                first_name=user.first_name,
                current_funnel_name=funnel_name,
                current_step_name=step_name,
                tags=[tag.tag for tag in user.tags],
                created_at=user.created_at,
            )
        )

    return items
