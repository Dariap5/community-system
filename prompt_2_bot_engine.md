# Промпт 2 — Бот, движок воронок, меню пользователя

## Роль

Ты senior Python-разработчик, специализирующийся на Telegram-ботах на aiogram 3. Знаешь особенности Telegram API (rate limits, IPv4/IPv6, parse_mode, file_id для медиа). Пишешь production-код с обработкой ошибок, retry-логикой, идемпотентностью.

## Контекст

Промпт 1 выполнен: проект создан, БД с 7 таблицами, модели, Pydantic-схема `StepConfig`, seed с воронкой `welcome`, Docker Compose.

Этот промпт добавляет **бот и движок воронок**. После этого промпта бот должен уметь:
1. Принимать `/start` и `/start XXX` (deeplink)
2. Запускать воронку и выполнять её шаги
3. Отправлять текст, фото, документы с задержками
4. Обрабатывать нажатия inline-кнопок (4 типа действий)
5. Показывать пользователю постоянное меню (Reply Keyboard)
6. Работать с отложенными задачами через Celery (задержки перед шагами > 60 сек)

Оплата и API — в следующих промптах. Здесь заглушка на кнопке "pay_product".

## Критически важно: IPv4-only сессия

На российских VPS IPv6 не маршрутизируется внутри Docker. Это вызывает таймауты при подключении к api.telegram.org. Нужно принудительно использовать IPv4 через кастомную aiogram-сессию:

```python
import socket
from aiohttp import TCPConnector, ClientSession
from aiogram.client.session.aiohttp import AiohttpSession

class IPv4OnlySession(AiohttpSession):
    async def create_session(self) -> ClientSession:
        if self._session is None or self._session.closed:
            connector = TCPConnector(family=socket.AF_INET)
            self._session = ClientSession(connector=connector)
        return self._session
```

Используй эту сессию при создании `Bot(...)`.

## Архитектурные принципы

### 1. Единый движок

`FunnelEngine` — единственная точка, которая отправляет сообщения пользователю в рамках воронки. Никакой дублирующей логики отправки.

### 2. Идемпотентность

Каждое выполнение шага помечается `execution_id`. Если Celery повторит задачу — проверяем, что шаг ещё не выполнен.

### 3. Короткие задержки inline, длинные через Celery

- Задержка ≤ 60 секунд — `asyncio.sleep()` в той же корутине
- Задержка > 60 секунд — записываем `ScheduledTask`, Celery Beat её подхватит

### 4. Rate limiting

Если Telegram возвращает `TelegramRetryAfter` — ждём и повторяем. Если `TelegramBadRequest` (например, пользователь заблокировал бота) — помечаем воронку как `paused` для этого пользователя.

### 5. Graceful handling

Если в шаге несколько сообщений и одно не отправилось — логируем, но продолжаем остальные.

## Структура (добавляется к существующему проекту)

```
app/
├── bot/                           # НОВОЕ
│   ├── __init__.py
│   ├── main.py                    # точка входа бота
│   ├── handlers.py                # /start и callback-кнопки
│   └── keyboards.py               # Reply Keyboard для меню
├── funnels/                       # НОВОЕ
│   ├── __init__.py
│   ├── engine.py                  # FunnelEngine
│   ├── message_sender.py          # отправка одного блока
│   ├── keyboard_builder.py        # построение inline-клавиатуры
│   └── actions.py                 # обработчики 4 типов кнопок
├── tasks/                         # НОВОЕ
│   ├── __init__.py
│   ├── celery_app.py              # Celery app
│   └── funnel_tasks.py            # отложенные задачи
```

## Задача 1 — Целиком переписать docker-compose.yml

Добавить сервисы `bot`, `worker`, `beat`:

```yaml
services:
  db:
    # ... как было

  redis:
    # ... как было

  init-db:
    # ... как было

  bot:
    build: .
    command: python -m app.bot.main
    env_file: .env
    depends_on:
      init-db:
        condition: service_completed_successfully
      redis:
        condition: service_healthy
    restart: unless-stopped

  worker:
    build: .
    command: celery -A app.tasks.celery_app worker --loglevel=INFO
    env_file: .env
    depends_on:
      init-db:
        condition: service_completed_successfully
      redis:
        condition: service_healthy
    restart: unless-stopped

  beat:
    build: .
    command: celery -A app.tasks.celery_app beat --loglevel=INFO
    env_file: .env
    depends_on:
      init-db:
        condition: service_completed_successfully
      redis:
        condition: service_healthy
    restart: unless-stopped

volumes:
  db_data:
```

## Задача 2 — app/bot/main.py

```python
import socket
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp import TCPConnector, ClientSession

from app.config import settings
from app.bot.handlers import router as main_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class IPv4OnlySession(AiohttpSession):
    """Форсим IPv4, потому что внутри Docker на VPS IPv6 не работает."""
    async def create_session(self) -> ClientSession:
        if self._session is None or self._session.closed:
            connector = TCPConnector(family=socket.AF_INET, limit=100, ttl_dns_cache=300)
            self._session = ClientSession(connector=connector)
        return self._session


async def run_bot() -> None:
    session = IPv4OnlySession()
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
        session=session,
    )
    dp = Dispatcher()
    dp.include_router(main_router)

    logger.info("Starting bot polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run_bot())
```

## Задача 3 — app/bot/keyboards.py

Постоянное меню (Reply Keyboard) с 4 кнопками:

```python
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


MENU_PRODUCTS = "🛍 Продукты"
MENU_MY_SUBS = "📂 Мои подписки"
MENU_SUPPORT = "❓ Поддержка"
MENU_OFFER = "📄 Оферта"


def main_menu() -> ReplyKeyboardMarkup:
    """Постоянное меню пользователя, всегда видимое."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MENU_PRODUCTS), KeyboardButton(text=MENU_MY_SUBS)],
            [KeyboardButton(text=MENU_SUPPORT), KeyboardButton(text=MENU_OFFER)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
```

## Задача 4 — app/bot/handlers.py

Обработчики:
- `/start` и `/start <param>` — создание/обновление пользователя, запуск воронки
- Callback кнопки — обработка нажатий inline-кнопок
- Reply Keyboard кнопки (меню) — 4 обработчика

```python
from aiogram import Router, types, F
from aiogram.filters import CommandStart, CommandObject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models import User, Funnel, Purchase, PaymentStatus, UserTag
from app.config import settings
from app.funnels.engine import FunnelEngine
from app.bot.keyboards import main_menu, MENU_PRODUCTS, MENU_MY_SUBS, MENU_SUPPORT, MENU_OFFER
from app.products import PRODUCTS

router = Router()


@router.message(CommandStart(deep_link=True))
async def handle_start_with_deeplink(message: types.Message, command: CommandObject):
    deeplink = command.args
    await _handle_start(message, deeplink=deeplink)


@router.message(CommandStart())
async def handle_start_plain(message: types.Message):
    await _handle_start(message, deeplink=None)


async def _handle_start(message: types.Message, deeplink: str | None):
    async with AsyncSessionLocal() as db:
        # Создать или обновить пользователя
        user = await db.get(User, message.from_user.id)
        if not user:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                source_deeplink=deeplink,
            )
            db.add(user)
            await db.commit()
            # Заново загружаем для relationships
            user = await db.get(User, message.from_user.id)

        # Показать меню
        await message.answer(
            "Привет! 👋",
            reply_markup=main_menu(),
        )

        # Определить воронку: по deeplink или дефолтную
        funnel_key = deeplink or settings.default_funnel_key
        result = await db.execute(select(Funnel).where(
            Funnel.entry_key == funnel_key,
            Funnel.is_active == True,
        ))
        funnel = result.scalar_one_or_none()

        if not funnel:
            return  # просто меню без запуска воронки

        # Запустить воронку
        from aiogram import Bot
        bot = message.bot
        engine = FunnelEngine(bot=bot, db=db)
        await engine.start_funnel(user, funnel)


@router.callback_query(F.data.startswith("btn:"))
async def handle_button_click(callback: types.CallbackQuery):
    await callback.answer()  # убрать loader сразу

    # Парсинг callback_data: "btn:<step_id>:<button_id>"
    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    _, step_id_str, button_id_str = parts

    async with AsyncSessionLocal() as db:
        user = await db.get(User, callback.from_user.id)
        if not user:
            return

        engine = FunnelEngine(bot=callback.bot, db=db)
        await engine.handle_button_click(user, step_id_str, button_id_str)


# ===== Меню пользователя =====

@router.message(F.text == MENU_PRODUCTS)
async def handle_menu_products(message: types.Message):
    if not PRODUCTS:
        await message.answer("Пока нет доступных продуктов")
        return
    text = "<b>Доступные продукты:</b>\n\n"
    for pid, product in PRODUCTS.items():
        text += f"• <b>{product['name']}</b> — {product['price']} ₽\n{product['description']}\n\n"
    text += "Чтобы купить — пройдите через /start и выберите подходящий вариант."
    await message.answer(text)


@router.message(F.text == MENU_MY_SUBS)
async def handle_menu_my_subs(message: types.Message):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Purchase).where(
                Purchase.user_id == message.from_user.id,
                Purchase.status == PaymentStatus.paid,
            ).order_by(Purchase.paid_at.desc())
        )
        purchases = result.scalars().all()

        if not purchases:
            await message.answer("У вас пока нет активных подписок.")
            return

        # Получить теги для определения треков
        tag_result = await db.execute(select(UserTag).where(UserTag.user_id == message.from_user.id))
        tags = {t.tag for t in tag_result.scalars().all()}

        text = "<b>Ваши подписки:</b>\n\n"
        for p in purchases:
            product = PRODUCTS.get(p.product_id, {"name": p.product_id})
            text += f"• {product['name']} ({p.paid_at.strftime('%d.%m.%Y') if p.paid_at else '—'})\n"

            # Если есть комьюнити — показать ссылки
            if p.product_id == "community":
                text += f"  Общий чат: {settings.community_chat_url}\n"
                if "track_career" in tags:
                    text += f"  Трек Карьера: {settings.track_career_url}\n"
                if "track_business" in tags:
                    text += f"  Трек Бизнес: {settings.track_business_url}\n"
                if "track_selfdev" in tags:
                    text += f"  Трек Саморазвитие: {settings.track_selfdev_url}\n"

        await message.answer(text)


@router.message(F.text == MENU_SUPPORT)
async def handle_menu_support(message: types.Message):
    username = settings.support_username
    if username:
        text = f"По всем вопросам пишите: @{username}"
    else:
        text = "Контакт поддержки скоро появится"
    await message.answer(text)


@router.message(F.text == MENU_OFFER)
async def handle_menu_offer(message: types.Message):
    url = settings.offer_url
    if url:
        await message.answer(f"Оферта доступна по ссылке:\n{url}")
    else:
        await message.answer("Оферта скоро будет доступна")
```

## Задача 5 — app/funnels/engine.py

```python
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from typing import Optional

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import (
    Funnel, FunnelStep, User, UserFunnelState, UserTag,
    FunnelStatus, FunnelCrossEntryBehavior, ScheduledTask, ScheduledTaskStatus,
)
from app.schemas.step_config import (
    StepConfig, TextMessage, PhotoMessage, DocumentMessage, ButtonGroup,
    ActionUrl, ActionGotoStep, ActionAddTag, ActionPayProduct,
)
from app.funnels.message_sender import send_block
from app.funnels.keyboard_builder import build_keyboard
from app.funnels.actions import handle_action

logger = logging.getLogger(__name__)

INLINE_DELAY_THRESHOLD = 60  # задержки ≤ этого — inline, иначе Celery


class FunnelEngine:
    """Оркестратор воронок: запуск, выполнение шагов, обработка кнопок."""

    def __init__(self, bot: Bot, db: AsyncSession):
        self.bot = bot
        self.db = db

    async def start_funnel(self, user: User, funnel: Funnel) -> None:
        """Запустить воронку для пользователя. Проверяет cross_entry."""
        # Проверка активных воронок
        result = await self.db.execute(
            select(UserFunnelState).where(
                UserFunnelState.user_id == user.telegram_id,
                UserFunnelState.status == FunnelStatus.active,
            )
        )
        active_states = result.scalars().all()

        if active_states and funnel.cross_entry_behavior == FunnelCrossEntryBehavior.deny:
            logger.info(f"User {user.telegram_id} already in funnel, deny new one")
            return

        # Найти первый шаг
        first_step = await self._get_first_step(funnel.id)
        if not first_step:
            logger.warning(f"Funnel {funnel.id} has no steps")
            return

        # Создать состояние
        state = UserFunnelState(
            user_id=user.telegram_id,
            funnel_id=funnel.id,
            current_step_id=first_step.id,
            status=FunnelStatus.active,
        )
        self.db.add(state)
        await self.db.commit()

        # Выполнить первый шаг
        await self.execute_step(user, first_step)

    async def execute_step(self, user: User, step: FunnelStep) -> None:
        """Выполнить шаг: отправить сообщения, обновить состояние."""
        try:
            config = StepConfig(**step.config)
        except Exception as e:
            logger.error(f"Invalid step config {step.id}: {e}")
            return

        # Задержка перед шагом
        if config.delay_before_seconds > 0:
            if config.delay_before_seconds <= INLINE_DELAY_THRESHOLD:
                await asyncio.sleep(config.delay_before_seconds)
            else:
                # Создаём ScheduledTask, выходим
                execute_at = datetime.now(timezone.utc) + timedelta(seconds=config.delay_before_seconds)
                task = ScheduledTask(
                    user_id=user.telegram_id,
                    task_type="execute_step",
                    payload={"step_id": str(step.id)},
                    execute_at=execute_at,
                )
                self.db.add(task)
                await self.db.commit()
                logger.info(f"Step {step.id} deferred to {execute_at}")
                return

        # Построить клавиатуру
        keyboard = build_keyboard(config, step.id)

        # Отправить сообщения по порядку
        for i, block in enumerate(config.blocks):
            if block.type == "buttons":
                # Кнопки прикрепляются к ПОСЛЕДНЕМУ предыдущему сообщению — в Telegram это так работает
                continue

            # Определяем, нужно ли прикреплять клавиатуру именно к этому сообщению
            # Правило: если это последнее сообщение перед ButtonGroup или последнее в blocks — клавиатура идёт сюда
            is_last_message_before_buttons = self._is_last_message_block(config, i)
            markup = keyboard if is_last_message_before_buttons else None

            await send_block(self.bot, user.telegram_id, block, reply_markup=markup)

            if block.delay_after > 0:
                if block.delay_after <= INLINE_DELAY_THRESHOLD:
                    await asyncio.sleep(block.delay_after)
                else:
                    # Длинная задержка посередине шага — редкий кейс, но поддерживаем
                    # В MVP просто спим, потому что такой шаг будет редким
                    await asyncio.sleep(block.delay_after)

        # Добавить теги после шага
        for tag in config.add_tags_after:
            existing = await self.db.execute(
                select(UserTag).where(UserTag.user_id == user.telegram_id, UserTag.tag == tag)
            )
            if not existing.scalar_one_or_none():
                self.db.add(UserTag(user_id=user.telegram_id, tag=tag))
        await self.db.commit()

        # Если wait_for_payment — останавливаемся и ждём webhook
        if config.wait_for_payment:
            logger.info(f"Step {step.id} waits for payment")
            return

        # Переход к следующему шагу
        next_step = await self._resolve_next_step(step, config)
        if next_step:
            await self._update_user_state(user, step.funnel_id, next_step.id)
            await self.execute_step(user, next_step)
        else:
            # Конец воронки
            await self._complete_funnel(user, step.funnel_id)

    async def handle_button_click(self, user: User, step_id_str: str, button_id_str: str) -> None:
        """Обработать нажатие inline-кнопки."""
        try:
            step_id = UUID(step_id_str)
            button_id = UUID(button_id_str)
        except ValueError:
            return

        step = await self.db.get(FunnelStep, step_id)
        if not step:
            return

        config = StepConfig(**step.config)
        # Найти кнопку в config
        button = None
        for block in config.blocks:
            if block.type == "buttons":
                for btn in block.buttons:
                    if btn.id == button_id:
                        button = btn
                        break
        if not button:
            return

        # Выполнить действие
        await handle_action(
            bot=self.bot,
            db=self.db,
            user=user,
            action=button.action,
            engine=self,
            current_step=step,
        )

    async def continue_after_payment(self, user: User, funnel_id: UUID) -> None:
        """Вызывается из webhook оплаты (Промпт 3). Продолжает воронку после ожидания."""
        result = await self.db.execute(
            select(UserFunnelState).where(
                UserFunnelState.user_id == user.telegram_id,
                UserFunnelState.funnel_id == funnel_id,
                UserFunnelState.status == FunnelStatus.active,
            )
        )
        state = result.scalar_one_or_none()
        if not state or not state.current_step_id:
            return

        current_step = await self.db.get(FunnelStep, state.current_step_id)
        if not current_step:
            return

        config = StepConfig(**current_step.config)
        next_step = await self._resolve_next_step(current_step, config)
        if next_step:
            await self._update_user_state(user, funnel_id, next_step.id)
            await self.execute_step(user, next_step)

    # ===== helpers =====

    async def _get_first_step(self, funnel_id: UUID) -> Optional[FunnelStep]:
        result = await self.db.execute(
            select(FunnelStep)
            .where(FunnelStep.funnel_id == funnel_id, FunnelStep.is_active == True)
            .order_by(FunnelStep.order)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _resolve_next_step(self, current: FunnelStep, config: StepConfig) -> Optional[FunnelStep]:
        if config.next_step == "end":
            return None
        if config.next_step == "auto":
            # Следующий по order
            result = await self.db.execute(
                select(FunnelStep)
                .where(
                    FunnelStep.funnel_id == current.funnel_id,
                    FunnelStep.order > current.order,
                    FunnelStep.is_active == True,
                )
                .order_by(FunnelStep.order)
                .limit(1)
            )
            return result.scalar_one_or_none()
        # По step_key
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
            )
        )
        state = result.scalar_one_or_none()
        if state:
            state.current_step_id = step_id
            await self.db.commit()

    async def _complete_funnel(self, user: User, funnel_id: UUID) -> None:
        result = await self.db.execute(
            select(UserFunnelState).where(
                UserFunnelState.user_id == user.telegram_id,
                UserFunnelState.funnel_id == funnel_id,
            )
        )
        state = result.scalar_one_or_none()
        if state:
            state.status = FunnelStatus.completed
            await self.db.commit()

    def _is_last_message_block(self, config: StepConfig, current_index: int) -> bool:
        """
        Определить, нужно ли прикрепить клавиатуру к блоку с индексом current_index.
        Правило: клавиатура прикрепляется к ПОСЛЕДНЕМУ сообщению перед ButtonGroup.
        Если ButtonGroup отсутствует — клавиатуры нет.
        """
        # Найти первый ButtonGroup
        button_group_index = None
        for i, block in enumerate(config.blocks):
            if block.type == "buttons":
                button_group_index = i
                break

        if button_group_index is None:
            return False

        # Ищем последний message-блок ПЕРЕД button_group_index
        last_msg_index = -1
        for i in range(button_group_index):
            if config.blocks[i].type != "buttons":
                last_msg_index = i

        return current_index == last_msg_index
```

## Задача 6 — app/funnels/message_sender.py

```python
import asyncio
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter, TelegramForbiddenError

from app.schemas.step_config import TextMessage, PhotoMessage, DocumentMessage

logger = logging.getLogger(__name__)

RETRY_ATTEMPTS = 3


async def send_block(bot: Bot, chat_id: int, block, reply_markup=None) -> bool:
    """Отправить один блок. Возвращает True при успехе."""
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
                logger.warning(f"Unknown block type: {type(block)}")
                return False
            return True

        except TelegramRetryAfter as e:
            logger.warning(f"Rate limited, sleeping {e.retry_after}s")
            await asyncio.sleep(e.retry_after)

        except TelegramForbiddenError:
            logger.info(f"User {chat_id} blocked the bot")
            return False

        except TelegramBadRequest as e:
            logger.error(f"BadRequest to {chat_id}: {e}")
            return False

        except Exception as e:
            logger.error(f"Unexpected error sending to {chat_id}: {e}")
            await asyncio.sleep(1)

    return False
```

## Задача 7 — app/funnels/keyboard_builder.py

```python
from uuid import UUID
from typing import Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.schemas.step_config import StepConfig, ButtonGroup, ActionUrl


def build_keyboard(config: StepConfig, step_id: UUID) -> Optional[InlineKeyboardMarkup]:
    """Собрать inline-клавиатуру из первого ButtonGroup в config."""
    button_group = None
    for block in config.blocks:
        if isinstance(block, ButtonGroup):
            button_group = block
            break

    if not button_group or not button_group.buttons:
        return None

    rows = []
    for button in button_group.buttons:
        if isinstance(button.action, ActionUrl):
            kb = InlineKeyboardButton(text=button.text, url=button.action.value)
        else:
            # callback_data: "btn:<step_id_short>:<button_id_short>"
            # Telegram лимит 64 байта, поэтому обрезаем UUID до 8 символов
            step_short = str(step_id).replace("-", "")[:12]
            btn_short = str(button.id).replace("-", "")[:12]
            kb = InlineKeyboardButton(
                text=button.text,
                callback_data=f"btn:{step_short}:{btn_short}",
            )
        rows.append([kb])

    return InlineKeyboardMarkup(inline_keyboard=rows)
```

**Важно:** в `handlers.py` callback-handler парсит `step_short` и `btn_short` — это первые 12 символов UUID без дефисов. Чтобы найти реальный шаг и кнопку, делаем поиск по `LIKE`:

```python
# в handlers.py, замените парсинг на:
async def _find_step_by_short_id(db: AsyncSession, step_short: str):
    # step_short — 12 символов UUID без дефисов
    # Преобразуем в паттерн с дефисами
    full_uuid_pattern = f"{step_short[:8]}-{step_short[8:12]}-%"
    result = await db.execute(
        select(FunnelStep).where(FunnelStep.id.cast(String).like(full_uuid_pattern))
    )
    return result.scalar_one_or_none()
```

Или проще: сохранять маппинг `short_id → full_id` в Redis на TTL 24 часа. Для MVP достаточно `LIKE`-запроса.

## Задача 8 — app/funnels/actions.py

```python
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal

from app.db.models import User, UserTag, Purchase, PaymentStatus, FunnelStep
from app.schemas.step_config import (
    ButtonAction, ActionUrl, ActionGotoStep, ActionAddTag, ActionPayProduct,
)
from app.products import PRODUCTS


async def handle_action(
    bot: Bot,
    db: AsyncSession,
    user: User,
    action: ButtonAction,
    engine,
    current_step: FunnelStep,
) -> None:
    """Диспетчер действий кнопки."""

    if isinstance(action, ActionUrl):
        # URL обрабатывает сам Telegram, сюда не попадаем
        return

    if isinstance(action, ActionAddTag):
        existing = await db.execute(
            select(UserTag).where(UserTag.user_id == user.telegram_id, UserTag.tag == action.value)
        )
        if not existing.scalar_one_or_none():
            db.add(UserTag(user_id=user.telegram_id, tag=action.value))
            await db.commit()
        return

    if isinstance(action, ActionGotoStep):
        # Найти целевой шаг в той же воронке
        result = await db.execute(
            select(FunnelStep).where(
                FunnelStep.funnel_id == current_step.funnel_id,
                FunnelStep.step_key == action.value,
            )
        )
        target = result.scalar_one_or_none()
        if target:
            await engine._update_user_state(user, current_step.funnel_id, target.id)
            await engine.execute_step(user, target)
        return

    if isinstance(action, ActionPayProduct):
        product = PRODUCTS.get(action.value)
        if not product:
            await bot.send_message(user.telegram_id, "Продукт не найден")
            return

        # В MVP для Промпта 2 — ЗАГЛУШКА. Реальная оплата через ЮKassa в Промпте 3.
        # Создаём Purchase и отправляем сообщение с ссылкой-заглушкой.
        purchase = Purchase(
            user_id=user.telegram_id,
            product_id=action.value,
            amount=Decimal(product["price"]),
            status=PaymentStatus.pending,
        )
        db.add(purchase)
        await db.commit()

        await bot.send_message(
            user.telegram_id,
            f"💳 Оплата продукта <b>{product['name']}</b>\n"
            f"Сумма: {product['price']} ₽\n\n"
            f"<i>Заглушка для Промпта 2. В Промпте 3 будет реальная ссылка на оплату.</i>",
            parse_mode="HTML",
        )
        return
```

## Задача 9 — app/tasks/celery_app.py и funnel_tasks.py

```python
# app/tasks/celery_app.py
from celery import Celery
from app.config import settings

celery_app = Celery(
    "community_bot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.funnel_tasks"],
)

celery_app.conf.beat_schedule = {
    "process-scheduled-tasks-every-30s": {
        "task": "app.tasks.funnel_tasks.process_scheduled_tasks",
        "schedule": 30.0,
    },
}

celery_app.conf.timezone = "UTC"
```

```python
# app/tasks/funnel_tasks.py
import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, update

from app.tasks.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.db.models import ScheduledTask, ScheduledTaskStatus, User, FunnelStep

logger = logging.getLogger(__name__)


@celery_app.task
def process_scheduled_tasks():
    """Запускается раз в 30 секунд, обрабатывает pending-задачи с наступившим execute_at."""
    asyncio.run(_process())


async def _process():
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(ScheduledTask).where(
                ScheduledTask.status == ScheduledTaskStatus.pending,
                ScheduledTask.execute_at <= now,
            ).limit(10)
        )
        tasks = result.scalars().all()

        for task in tasks:
            task.status = ScheduledTaskStatus.processing
            await db.commit()

            try:
                if task.task_type == "execute_step":
                    await _execute_step_task(db, task)
                task.status = ScheduledTaskStatus.done
            except Exception as e:
                logger.error(f"Task {task.id} failed: {e}")
                task.status = ScheduledTaskStatus.failed

            await db.commit()


async def _execute_step_task(db, task: ScheduledTask):
    """Выполнить отложенный шаг."""
    step_id = UUID(task.payload["step_id"])
    step = await db.get(FunnelStep, step_id)
    user = await db.get(User, task.user_id)
    if not step or not user:
        return

    # Важно: здесь нужен bot. Создаём новую сессию для worker.
    from app.bot.main import IPv4OnlySession
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from app.config import settings
    from app.funnels.engine import FunnelEngine

    session = IPv4OnlySession()
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"), session=session)

    try:
        engine = FunnelEngine(bot=bot, db=db)
        await engine.execute_step(user, step)
    finally:
        await session.close()
```

## Задача 10 — Тесты

Создай `tests/test_engine.py` с минимум 4 тестами:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from app.funnels.engine import FunnelEngine
from app.schemas.step_config import StepConfig, TextMessage, ButtonGroup, Button, ActionGotoStep


@pytest.mark.asyncio
async def test_engine_instantiation():
    bot = MagicMock()
    db = AsyncMock()
    engine = FunnelEngine(bot=bot, db=db)
    assert engine.bot is bot


def test_is_last_message_before_buttons():
    config = StepConfig(
        blocks=[
            TextMessage(type="text", content="A"),
            TextMessage(type="text", content="B"),
            ButtonGroup(type="buttons", buttons=[]),
        ]
    )
    engine = FunnelEngine(bot=None, db=None)
    # B — последнее сообщение перед кнопками
    assert engine._is_last_message_block(config, 1) is True
    assert engine._is_last_message_block(config, 0) is False


def test_no_buttons_returns_false():
    config = StepConfig(blocks=[TextMessage(type="text", content="A")])
    engine = FunnelEngine(bot=None, db=None)
    assert engine._is_last_message_block(config, 0) is False
```

## Acceptance criteria

```bash
# 1. Пересобрать и запустить всё
docker compose up -d --build
sleep 10

# 2. Проверить, что все сервисы живы
docker compose ps
# Должны быть: db (healthy), redis (healthy), bot (Up), worker (Up), beat (Up)

# 3. Логи бота — НЕ должно быть traceback
docker compose logs --tail=30 bot
# Ожидаем: "Starting bot polling..." и "Run polling for bot @xxx"

# 4. Логи beat — должна быть запись о периодической задаче
docker compose logs --tail=30 beat
# Ожидаем каждые 30 секунд: "Scheduler: Sending due task process-scheduled-tasks-every-30s"

# 5. Прогон тестов
docker compose exec bot pytest tests/ -v
# Все тесты должны пройти

# 6. Реальный тест в Telegram:
#    - Написать боту /start
#    - Должно прийти "Привет!" + меню + начало воронки welcome
#    - Нажать "Узнать про комьюнити" → появится сообщение про треки
#    - Нажать "Карьера" → придёт текст про карьеру + кнопка "Оплатить 2990 ₽"
#    - Нажать кнопку оплаты → придёт заглушка про оплату
```

**Покажи реальный вывод каждой команды и скриншоты из Telegram (или описание, что произошло).**

## Важные замечания

- **Не используй хардкод токена в коде.** Только через settings/env.
- **Короткие ID в callback_data (12 символов от UUID без дефисов) — обязательно.** Без этого Telegram обрезает callback_data до 64 байт, и кнопки ломаются.
- **IPv4-only сессия.** Без неё бот не запустится на VPS.
- **Не создавай раздельных обработчиков для сообщений и для callback в разных файлах.** Всё в `handlers.py`.
- **CommandStart** с `deep_link=True` только в aiogram 3.4+. Проверь версию.
- **Commit после каждого изменения БД.** Не забывай `await db.commit()`.
- **Обработчики меню** (`MENU_PRODUCTS` и т.д.) **должны идти после** обработчиков CommandStart, иначе `/start` может перехватиться как текст.
- **Celery worker и beat — два разных процесса.** Оба должны работать одновременно.

После успешного выполнения всех 6 пунктов acceptance — промпт закрыт, переходим к Промпту 3 (API + webhook платежей).
