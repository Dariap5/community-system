"""Seed data for the initial funnel."""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db.models import Funnel, FunnelCrossEntryBehavior, FunnelStep
from app.db.session import AsyncSessionLocal
from app.schemas.step_config import (
    ActionAddTag,
    ActionGotoStep,
    ActionPayProduct,
    Button,
    ButtonGroup,
    StepConfig,
    TextMessage,
)


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(Funnel).where(Funnel.entry_key == "welcome"))
        if existing.scalar_one_or_none() is not None:
            print("Funnel 'welcome' already exists, skipping seed")
            return

        funnel = Funnel(
            name="Приветственная воронка",
            entry_key="welcome",
            is_active=True,
            cross_entry_behavior=FunnelCrossEntryBehavior.deny,
        )
        db.add(funnel)
        await db.flush()

        step1 = FunnelStep(
            funnel_id=funnel.id,
            order=1,
            name="Приветствие",
            step_key="welcome_intro",
            config=StepConfig(
                blocks=[
                    TextMessage(
                        type="text",
                        content="<b>Добро пожаловать!</b>\n\nРад видеть тебя здесь. Расскажу про наше комьюнити.",
                        delay_after=0,
                    ),
                    ButtonGroup(
                        type="buttons",
                        buttons=[
                            Button(text="Узнать про комьюнити", action=ActionGotoStep(type="goto_step", value="track_choice")),
                        ],
                    ),
                ],
            ).model_dump(mode="json"),
        )
        db.add(step1)

        step2 = FunnelStep(
            funnel_id=funnel.id,
            order=2,
            name="Выбор трека",
            step_key="track_choice",
            config=StepConfig(
                blocks=[
                    TextMessage(
                        type="text",
                        content="В комьюнити три направления. Выбери то, что тебе ближе:",
                        delay_after=0,
                    ),
                    ButtonGroup(
                        type="buttons",
                        buttons=[
                            Button(text="Карьера", action=ActionGotoStep(type="goto_step", value="track_career")),
                            Button(text="Бизнес", action=ActionGotoStep(type="goto_step", value="track_business")),
                            Button(text="Саморазвитие", action=ActionGotoStep(type="goto_step", value="track_selfdev")),
                        ],
                    ),
                ],
            ).model_dump(mode="json"),
        )
        db.add(step2)

        step3a = FunnelStep(
            funnel_id=funnel.id,
            order=3,
            name="Трек: Карьера",
            step_key="track_career",
            config=StepConfig(
                blocks=[
                    TextMessage(
                        type="text",
                        content="<b>Трек Карьера</b>\n\nОписание трека, что в нём есть, результаты участников.",
                        delay_after=0,
                    ),
                    ButtonGroup(
                        type="buttons",
                        buttons=[
                            Button(text="Оплатить 2990 ₽", action=ActionPayProduct(type="pay_product", value="community")),
                        ],
                    ),
                ],
                add_tags_after=["track_career"],
                next_step="end",
            ).model_dump(mode="json"),
        )
        db.add(step3a)

        step3b = FunnelStep(
            funnel_id=funnel.id,
            order=4,
            name="Трек: Бизнес",
            step_key="track_business",
            config=StepConfig(
                blocks=[
                    TextMessage(
                        type="text",
                        content="<b>Трек Бизнес</b>\n\nОписание трека.",
                        delay_after=0,
                    ),
                    ButtonGroup(
                        type="buttons",
                        buttons=[
                            Button(text="Оплатить 2990 ₽", action=ActionPayProduct(type="pay_product", value="community")),
                        ],
                    ),
                ],
                add_tags_after=["track_business"],
                next_step="end",
            ).model_dump(mode="json"),
        )
        db.add(step3b)

        step3c = FunnelStep(
            funnel_id=funnel.id,
            order=5,
            name="Трек: Саморазвитие",
            step_key="track_selfdev",
            config=StepConfig(
                blocks=[
                    TextMessage(
                        type="text",
                        content="<b>Трек Саморазвитие</b>\n\nОписание трека.",
                        delay_after=0,
                    ),
                    ButtonGroup(
                        type="buttons",
                        buttons=[
                            Button(text="Оплатить 2990 ₽", action=ActionPayProduct(type="pay_product", value="community")),
                        ],
                    ),
                ],
                add_tags_after=["track_selfdev"],
                next_step="end",
            ).model_dump(mode="json"),
        )
        db.add(step3c)

        await db.commit()
        print("Seed successful: funnel 'welcome' with 5 steps created")


if __name__ == "__main__":
    asyncio.run(seed())