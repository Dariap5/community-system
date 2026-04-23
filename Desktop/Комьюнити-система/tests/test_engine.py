from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.funnels.engine import FunnelEngine
from app.funnels.keyboard_builder import build_keyboard
from app.funnels.message_sender import SendResult, send_block
from app.schemas.step_config import ActionGotoStep, ActionUrl, Button, ButtonGroup, StepConfig, TextMessage


@pytest.mark.asyncio
async def test_engine_instantiation() -> None:
    bot = MagicMock()
    db = AsyncMock()
    engine = FunnelEngine(bot=bot, db=db)
    assert engine.bot is bot
    assert engine.db is db


def test_is_last_message_before_buttons() -> None:
    config = StepConfig(
        blocks=[
            TextMessage(type="text", content="A"),
            TextMessage(type="text", content="B"),
            ButtonGroup(type="buttons", buttons=[]),
        ]
    )
    engine = FunnelEngine(bot=None, db=None)
    assert engine._is_last_message_block(config, 1) is True
    assert engine._is_last_message_block(config, 0) is False


def test_no_buttons_returns_false() -> None:
    config = StepConfig(blocks=[TextMessage(type="text", content="A")])
    engine = FunnelEngine(bot=None, db=None)
    assert engine._is_last_message_block(config, 0) is False


@pytest.mark.asyncio
async def test_button_step_waits_without_completing(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = FunnelEngine(bot=MagicMock(), db=AsyncMock())
    engine._apply_step_tags = AsyncMock()
    engine._resolve_next_step = AsyncMock(side_effect=AssertionError("button steps must not auto-resolve"))
    engine._complete_funnel = AsyncMock(side_effect=AssertionError("button steps must not complete immediately"))

    async def fake_build_keyboard(config: StepConfig, step_id):
        return None

    async def fake_send_block(bot, chat_id, block, reply_markup=None):
        return SendResult.OK

    monkeypatch.setattr("app.funnels.engine.build_keyboard", fake_build_keyboard)
    monkeypatch.setattr("app.funnels.engine.send_block", fake_send_block)

    step = type(
        "Step",
        (),
        {
            "id": uuid4(),
            "funnel_id": uuid4(),
            "config": StepConfig(
                blocks=[
                    TextMessage(type="text", content="Hello"),
                    ButtonGroup(type="buttons", buttons=[Button(text="Go", action=ActionGotoStep(type="goto_step", value="next"))]),
                ]
            ).model_dump(mode="json"),
        },
    )()
    user = type("User", (), {"telegram_id": 12345})()

    await engine.execute_step(user, step)

    engine._resolve_next_step.assert_not_awaited()
    engine._complete_funnel.assert_not_awaited()


@pytest.mark.asyncio
async def test_build_keyboard_creates_callback_buttons(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, str]] = []

    async def fake_store(callback_data: str, step_id, button_id) -> None:
        calls.append((callback_data, str(step_id), str(button_id)))

    monkeypatch.setattr("app.funnels.keyboard_builder.store_callback_reference", fake_store)

    config = StepConfig(
        blocks=[
            TextMessage(type="text", content="Hello"),
            ButtonGroup(
                type="buttons",
                buttons=[
                    Button(text="URL", action=ActionUrl(type="url", value="https://t.me")),
                    Button(text="Goto", action=ActionGotoStep(type="goto_step", value="next_step")),
                ],
            ),
        ]
    )

    markup = await build_keyboard(config, uuid4())
    assert markup is not None
    assert markup.inline_keyboard[0][0].url == "https://t.me"
    assert markup.inline_keyboard[1][0].callback_data.startswith("btn:")
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_send_block_text_message() -> None:
    bot = AsyncMock()
    bot.send_message = AsyncMock()

    result = await send_block(bot, 123, TextMessage(type="text", content="Hello"))

    assert result == SendResult.OK
    bot.send_message.assert_awaited_once()