from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_secret
from app.db.models import Funnel, FunnelStep, Purchase, PaymentStatus, User, UserFunnelState
from app.schemas.api import AnalyticsSummary, FunnelAnalytics


router = APIRouter(prefix="/api/{secret}", dependencies=[Depends(verify_secret)])


@router.get("/analytics/summary", response_model=AnalyticsSummary)
async def get_summary(period_days: int = Query(default=30, ge=1), db: AsyncSession = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=period_days)

    new_users_result = await db.execute(select(func.count(User.telegram_id)).where(User.created_at >= since))
    new_users_count = new_users_result.scalar_one()

    total_users_result = await db.execute(select(func.count(User.telegram_id)))
    total_users_count = total_users_result.scalar_one()

    payments_result = await db.execute(
        select(func.count(Purchase.id)).where(
            Purchase.status == PaymentStatus.paid,
            Purchase.paid_at >= since,
        )
    )
    payments_count = payments_result.scalar_one()

    revenue_result = await db.execute(
        select(func.coalesce(func.sum(Purchase.amount), 0)).where(
            Purchase.status == PaymentStatus.paid,
            Purchase.paid_at >= since,
        )
    )
    revenue_total = float(revenue_result.scalar_one())

    # `/start` в текущей модели хранится как `users.created_at`.
    # Конверсия считается по когорте новых пользователей периода: сколько из них
    # дошло хотя бы до одной оплаты после своего старта.
    paid_users_result = await db.execute(
        select(func.count(func.distinct(User.telegram_id)))
        .select_from(User)
        .join(Purchase, Purchase.user_id == User.telegram_id)
        .where(
            User.created_at >= since,
            Purchase.status == PaymentStatus.paid,
            Purchase.paid_at >= since,
            Purchase.paid_at >= User.created_at,
        )
    )
    paid_users_count = paid_users_result.scalar_one()
    conversion_percent = (paid_users_count / new_users_count * 100) if new_users_count else 0.0

    return AnalyticsSummary(
        new_users_count=new_users_count,
        total_users_count=total_users_count,
        payments_count=payments_count,
        revenue_total=revenue_total,
        conversion_percent=round(conversion_percent, 2),
    )


@router.get("/analytics/funnels", response_model=list[FunnelAnalytics])
async def get_funnel_analytics(db: AsyncSession = Depends(get_db)):
    funnels_result = await db.execute(select(Funnel).where(Funnel.is_archived.is_(False)))
    funnels = funnels_result.scalars().all()

    response: list[FunnelAnalytics] = []
    for funnel in funnels:
        steps_result = await db.execute(
            select(FunnelStep).where(FunnelStep.funnel_id == funnel.id).order_by(FunnelStep.order)
        )
        steps = steps_result.scalars().all()

        state_orders_result = await db.execute(
            select(UserFunnelState.user_id, FunnelStep.order)
            .select_from(UserFunnelState)
            .outerjoin(FunnelStep, UserFunnelState.current_step_id == FunnelStep.id)
            .where(UserFunnelState.funnel_id == funnel.id)
        )

        max_order_by_user: dict[int, int] = {}
        for user_id, step_order in state_orders_result.all():
            current_order = int(step_order or 0)
            previous_order = max_order_by_user.get(user_id, 0)
            if current_order > previous_order:
                max_order_by_user[user_id] = current_order

        total_users = len(max_order_by_user)
        steps_stats: list[dict[str, object]] = []
        for step in steps:
            users_count = sum(1 for current_order in max_order_by_user.values() if current_order >= step.order)
            percent = round(users_count / total_users * 100, 1) if total_users else 0.0
            steps_stats.append(
                {
                    "step_name": step.name,
                    "users_count": users_count,
                    "percent": percent,
                }
            )

        response.append(
            FunnelAnalytics(
                funnel_id=funnel.id,
                funnel_name=funnel.name,
                steps_stats=steps_stats,
            )
        )

    return response
