from __future__ import annotations

import asyncio
import logging
from enum import Enum

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup

from app.schemas.step_config import DocumentMessage, PhotoMessage, TextMessage


logger = logging.getLogger(__name__)

RETRY_ATTEMPTS = 3


class SendResult(str, Enum):
    OK = "ok"
    BLOCKED = "blocked"
    BAD_REQUEST = "bad_request"
    FAILED = "failed"


async def send_block(
    bot: Bot,
    chat_id: int,
    block: TextMessage | PhotoMessage | DocumentMessage,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> SendResult:
    for attempt in range(RETRY_ATTEMPTS):
        try:
            if isinstance(block, TextMessage):
                await bot.send_message(
                    chat_id=chat_id,
                    text=block.content,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
            elif isinstance(block, PhotoMessage):
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=block.file_id,
                    caption=block.caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
            elif isinstance(block, DocumentMessage):
                await bot.send_document(
                    chat_id=chat_id,
                    document=block.file_id,
                    caption=block.caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
            else:
                logger.warning("Unknown block type: %s", type(block))
                return SendResult.FAILED

            return SendResult.OK

        except TelegramRetryAfter as exc:
            logger.warning("Rate limited, sleeping %ss", exc.retry_after)
            await asyncio.sleep(exc.retry_after)
        except TelegramForbiddenError as exc:
            logger.info("User %s blocked the bot: %s", chat_id, exc)
            return SendResult.BLOCKED
        except TelegramBadRequest as exc:
            logger.error("BadRequest to %s: %s", chat_id, exc)
            return SendResult.BAD_REQUEST
        except Exception:
            logger.exception("Unexpected error sending to %s", chat_id)
            if attempt < RETRY_ATTEMPTS - 1:
                await asyncio.sleep(1)

    return SendResult.FAILED