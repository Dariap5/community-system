from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_secret
from app.db.models import Funnel, FunnelStep
from app.schemas.api import (
    FunnelCreate,
    FunnelDetail,
    FunnelRead,
    FunnelUpdate,
    StepCreate,
    StepRead,
    StepReorder,
    StepSummary,
    StepUpdate,
)
from app.services.funnels import (
    duplicate_funnel,
    extract_first_message_preview,
    get_funnel_with_stats,
    get_next_order,
    has_active_users_on_step,
)


router = APIRouter(prefix="/api/{secret}", dependencies=[Depends(verify_secret)])


async def _get_funnel_or_404(db: AsyncSession, funnel_id: UUID) -> Funnel:
    funnel = await db.get(Funnel, funnel_id)
    if funnel is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Funnel not found"},
        )
    return funnel


async def _get_step_or_404(db: AsyncSession, funnel_id: UUID, step_id: UUID) -> FunnelStep:
    step = await db.get(FunnelStep, step_id)
    if step is None or step.funnel_id != funnel_id:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Step not found"},
        )
    return step


async def _shift_step_orders(db: AsyncSession, funnel_id: UUID, starting_order: int) -> None:
    result = await db.execute(
        select(FunnelStep)
        .where(FunnelStep.funnel_id == funnel_id, FunnelStep.order >= starting_order)
        .order_by(FunnelStep.order.desc())
    )
    for step in result.scalars().all():
        step.order += 1


@router.get("/funnels", response_model=list[FunnelRead])
async def list_funnels(include_archived: bool = False, db: AsyncSession = Depends(get_db)):
    query = select(Funnel)
    if not include_archived:
        query = query.where(Funnel.is_archived.is_(False))
    result = await db.execute(query.order_by(Funnel.created_at.desc()))
    funnels = result.scalars().all()

    items = []
    for funnel in funnels:
        stats = await get_funnel_with_stats(db, funnel.id)
        if stats is not None:
            items.append(stats)
    return items


@router.post("/funnels", response_model=FunnelRead, status_code=201)
async def create_funnel(data: FunnelCreate, db: AsyncSession = Depends(get_db)):
    funnel = Funnel(
        name=data.name,
        entry_key=data.entry_key,
        cross_entry_behavior=data.cross_entry_behavior,
    )
    db.add(funnel)
    await db.commit()
    return await get_funnel_with_stats(db, funnel.id)


@router.get("/funnels/{funnel_id}", response_model=FunnelDetail)
async def get_funnel(funnel_id: UUID, db: AsyncSession = Depends(get_db)):
    stats = await get_funnel_with_stats(db, funnel_id)
    if stats is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Funnel not found"},
        )

    result = await db.execute(
        select(FunnelStep).where(FunnelStep.funnel_id == funnel_id).order_by(FunnelStep.order)
    )
    steps = [
        StepSummary(
            id=step.id,
            order=step.order,
            name=step.name,
            step_key=step.step_key,
            is_active=step.is_active,
            first_message_preview=extract_first_message_preview(step.config),
        )
        for step in result.scalars().all()
    ]
    return {**stats, "steps": steps}


@router.patch("/funnels/{funnel_id}", response_model=FunnelRead)
async def update_funnel(funnel_id: UUID, data: FunnelUpdate, db: AsyncSession = Depends(get_db)):
    funnel = await _get_funnel_or_404(db, funnel_id)
    payload = data.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(funnel, field, value)
    await db.commit()
    return await get_funnel_with_stats(db, funnel_id)


@router.delete("/funnels/{funnel_id}", status_code=204)
async def archive_funnel(funnel_id: UUID, db: AsyncSession = Depends(get_db)):
    funnel = await _get_funnel_or_404(db, funnel_id)
    funnel.is_archived = True
    funnel.is_active = False
    await db.commit()


@router.post("/funnels/{funnel_id}/duplicate", response_model=FunnelRead, status_code=201)
async def duplicate_funnel_endpoint(funnel_id: UUID, db: AsyncSession = Depends(get_db)):
    new_funnel = await duplicate_funnel(db, funnel_id)
    if new_funnel is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Funnel not found"},
        )
    stats = await get_funnel_with_stats(db, new_funnel.id)
    if stats is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Funnel not found"},
        )
    return stats


@router.get("/funnels/{funnel_id}/steps", response_model=list[StepRead])
async def list_steps(funnel_id: UUID, db: AsyncSession = Depends(get_db)):
    await _get_funnel_or_404(db, funnel_id)
    result = await db.execute(
        select(FunnelStep).where(FunnelStep.funnel_id == funnel_id).order_by(FunnelStep.order)
    )
    return list(result.scalars().all())


@router.post("/funnels/{funnel_id}/steps", response_model=StepRead, status_code=201)
async def create_step(funnel_id: UUID, data: StepCreate, db: AsyncSession = Depends(get_db)):
    await _get_funnel_or_404(db, funnel_id)

    if data.order is None:
        order = await get_next_order(db, funnel_id)
    else:
        order = data.order
        await _shift_step_orders(db, funnel_id, order)
        await db.flush()

    step = FunnelStep(
        funnel_id=funnel_id,
        order=order,
        name=data.name,
        step_key=data.step_key,
        config=data.config.model_dump(mode="json"),
        is_active=True,
    )
    db.add(step)
    await db.commit()
    await db.refresh(step)
    return step


@router.get("/funnels/{funnel_id}/steps/{step_id}", response_model=StepRead)
async def get_step(funnel_id: UUID, step_id: UUID, db: AsyncSession = Depends(get_db)):
    return await _get_step_or_404(db, funnel_id, step_id)


@router.put("/funnels/{funnel_id}/steps/{step_id}", response_model=StepRead)
async def update_step(funnel_id: UUID, step_id: UUID, data: StepUpdate, db: AsyncSession = Depends(get_db)):
    step = await _get_step_or_404(db, funnel_id, step_id)
    step.name = data.name
    step.step_key = data.step_key
    step.is_active = data.is_active
    step.config = data.config.model_dump(mode="json")
    await db.commit()
    await db.refresh(step)
    return step


@router.delete("/funnels/{funnel_id}/steps/{step_id}", status_code=204)
async def delete_step(funnel_id: UUID, step_id: UUID, db: AsyncSession = Depends(get_db)):
    step = await _get_step_or_404(db, funnel_id, step_id)
    if await has_active_users_on_step(db, step_id):
        raise HTTPException(
            status_code=409,
            detail={"code": "conflict", "message": "Step has active users"},
        )
    await db.delete(step)
    await db.commit()


@router.post("/funnels/{funnel_id}/steps/reorder", response_model=list[StepRead])
async def reorder_steps(funnel_id: UUID, data: StepReorder, db: AsyncSession = Depends(get_db)):
    await _get_funnel_or_404(db, funnel_id)
    result = await db.execute(select(FunnelStep).where(FunnelStep.funnel_id == funnel_id))
    steps = {step.id: step for step in result.scalars().all()}

    ordered_ids = list(data.step_ids_in_order)
    if len(ordered_ids) != len(steps) or set(ordered_ids) != set(steps):
        raise HTTPException(
            status_code=400,
            detail={"code": "bad_request", "message": "Step IDs don't match funnel steps"},
        )

    offset = len(steps)
    for temp_order, step_id in enumerate(ordered_ids, start=1):
        steps[step_id].order = temp_order + offset

    await db.flush()

    for new_order, step_id in enumerate(ordered_ids, start=1):
        steps[step_id].order = new_order

    await db.commit()
    result = await db.execute(
        select(FunnelStep).where(FunnelStep.funnel_id == funnel_id).order_by(FunnelStep.order)
    )
    return list(result.scalars().all())
