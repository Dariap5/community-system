from __future__ import annotations

import logging
from uuid import UUID

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.funnels.callback_store import store_callback_reference
from app.schemas.step_config import ActionUrl, ButtonGroup, StepConfig


logger = logging.getLogger(__name__)


def _short_uuid(value: UUID) -> str:
    return value.hex[:12]


async def build_keyboard(config: StepConfig, step_id: UUID) -> InlineKeyboardMarkup | None:
    button_group = next((block for block in config.blocks if isinstance(block, ButtonGroup)), None)
    if button_group is None or not button_group.buttons:
        return None

    rows: list[list[InlineKeyboardButton]] = []
    step_short = _short_uuid(step_id)

    for button in button_group.buttons:
        if isinstance(button.action, ActionUrl):
            rows.append([InlineKeyboardButton(text=button.text, url=button.action.value)])
            continue

        button_short = _short_uuid(button.id)
        callback_data = f"btn:{step_short}:{button_short}"

        try:
            await store_callback_reference(callback_data, step_id, button.id)
        except Exception as exc:  # pragma: no cover - Redis may be unavailable in tests
            logger.warning("Failed to cache callback mapping for %s: %s", callback_data, exc)

        rows.append([InlineKeyboardButton(text=button.text, callback_data=callback_data)])

    return InlineKeyboardMarkup(inline_keyboard=rows)