# Промпт 1 — Фундамент: проект, БД, модели, Pydantic-схема, seed

## Роль

Ты senior Python backend-разработчик. Создаёшь новый проект с нуля. Специализация — aiogram 3, FastAPI, SQLAlchemy 2 async, PostgreSQL, Docker Compose. Пишешь чистый минималистичный код, без лишних абстракций. Type hints везде. Pydantic для валидации.

## Контекст

Это **новый репозиторий** для Telegram-бота комьюнити. Предыдущий проект был монорепой с лендингом и ботом, это создавало проблемы. Сейчас создаём отдельный, изолированный проект только под бот и админку.

Бот нужен для продажи цифрового продукта "Комьюнити" через воронки сообщений. У пользователя в боте есть меню (Продукты, Мои подписки, Поддержка, Оферта). Бот отправляет шаги воронки с текстом/фото/документами и кнопками. После нажатия кнопки оплаты — запускается платёжка (ЮKassa), после webhook-подтверждения оплаты воронка продолжается.

Этот промпт создаёт **только фундамент**: структуру проекта, БД, модели, валидацию. Логику бота и API — в следующих промптах.

## Стек

- Python 3.11+
- aiogram 3.x (будет в Промпте 2)
- FastAPI (будет в Промпте 3)
- SQLAlchemy 2 (async)
- PostgreSQL 16
- Alembic для миграций
- Celery + Redis (будет в Промпте 2, сейчас только настроить модель задач)
- Pydantic v2
- Docker Compose для всех сервисов

## Структура нового проекта

Создаёшь в новом пустом репозитории:

```
community-bot/
├── .env.example
├── .gitignore
├── .dockerignore
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── README.md
├── alembic.ini
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_schema.py
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── products.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── models.py
│   │   ├── session.py
│   │   └── seed.py
│   └── schemas/
│       ├── __init__.py
│       └── step_config.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── test_models.py
```

Папки `app/bot/`, `app/api/`, `app/funnels/`, `app/tasks/` в этом промпте **не создаём** — они будут в следующих промптах.

## Задача 1 — pyproject.toml и зависимости

```toml
[project]
name = "community-bot"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "aiogram>=3.4.1",
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "sqlalchemy[asyncio]>=2.0.25",
    "asyncpg>=0.29.0",
    "alembic>=1.13.1",
    "pydantic>=2.5.3",
    "pydantic-settings>=2.1.0",
    "celery>=5.3.6",
    "redis>=5.0.1",
    "jinja2>=3.1.3",
    "python-multipart>=0.0.6",
    "cryptography>=42.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.4",
    "httpx>=0.26.0",
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["app*"]
```

## Задача 2 — .env.example и .gitignore

**.env.example:**
```bash
# Database
POSTGRES_USER=community_user
POSTGRES_PASSWORD=changeme
POSTGRES_DB=community_db
DATABASE_URL=postgresql+asyncpg://community_user:changeme@db:5432/community_db

# Redis
REDIS_URL=redis://redis:6379/0

# Telegram
BOT_TOKEN=

# Admin (без пароля, по секретному URL)
ADMIN_SECRET_PATH=change-this-long-random-string

# Payments (ЮKassa)
YOOKASSA_SHOP_ID=
YOOKASSA_SECRET_KEY=

# Community links (отправляются после оплаты)
COMMUNITY_CHAT_URL=https://t.me/+xxxxxxxxx
TRACK_CAREER_URL=https://t.me/+xxxxxxxxx
TRACK_BUSINESS_URL=https://t.me/+xxxxxxxxx
TRACK_SELFDEV_URL=https://t.me/+xxxxxxxxx

# Support
SUPPORT_USERNAME=your_username
OFFER_URL=https://your-landing.com/offer

# Default funnel (запускается при /start без параметра)
DEFAULT_FUNNEL_KEY=welcome
```

**.gitignore:**
```
.env
.venv/
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
dist/
build/
.DS_Store
.vscode/
.idea/
```

**.dockerignore:**
```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.git/
.env
README.md
tests/
```

## Задача 3 — docker-compose.yml

```yaml
services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - db_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  init-db:
    build: .
    command: sh -c "alembic upgrade head && python -m app.db.seed"
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    restart: "no"

volumes:
  db_data:
```

В этом промпте только `db`, `redis` и `init-db`. Сервисы `bot`, `api`, `worker`, `beat` — добавятся в следующих промптах.

## Задача 4 — Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir -e .

CMD ["python", "-m", "app.bot.main"]
```

## Задача 5 — app/config.py

```python
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    database_url: str
    redis_url: str

    # Telegram
    bot_token: str

    # Admin
    admin_secret_path: str = "change-me"

    # Payments
    yookassa_shop_id: Optional[str] = None
    yookassa_secret_key: Optional[str] = None

    # Community
    community_chat_url: str = ""
    track_career_url: str = ""
    track_business_url: str = ""
    track_selfdev_url: str = ""

    # Support
    support_username: str = ""
    offer_url: str = ""

    # Default
    default_funnel_key: str = "welcome"

    class Config:
        env_file = ".env"
        case_sensitive = False

def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

## Задача 6 — app/products.py

```python
"""
Хардкод продуктов. В MVP не выносится в БД.
Ключ продукта используется в ButtonAction.type='pay_product'.
"""

PRODUCTS = {
    "community": {
        "name": "Доступ в комьюнити",
        "price": 2990,  # в рублях
        "description": "Закрытое комьюнити с материалами и сообществом",
    },
    # Добавляйте новые продукты сюда. Ключ — любой латинский идентификатор.
}

def get_product(product_id: str) -> dict | None:
    return PRODUCTS.get(product_id)
```

## Задача 7 — app/db/base.py и app/db/session.py

**base.py:**
```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

**session.py:**
```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

## Задача 8 — app/db/models.py (7 таблиц)

```python
import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, ForeignKey, Index,
    Integer, Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FunnelCrossEntryBehavior(str, enum.Enum):
    allow = "allow"  # разрешить параллельный запуск
    deny = "deny"    # не запускать, если уже в другой воронке


class FunnelStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    completed = "completed"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"
    refunded = "refunded"


class ScheduledTaskStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    source_deeplink: Mapped[str | None] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    tags: Mapped[list["UserTag"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    funnel_states: Mapped[list["UserFunnelState"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    purchases: Mapped[list["Purchase"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserTag(Base):
    __tablename__ = "user_tags"
    __table_args__ = (UniqueConstraint("user_id", "tag", name="uq_user_tags"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id", ondelete="CASCADE"), primary_key=True)
    tag: Mapped[str] = mapped_column(String(128), primary_key=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="tags")


class Funnel(Base):
    __tablename__ = "funnels"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entry_key: Mapped[str | None] = mapped_column(String(120), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    cross_entry_behavior: Mapped[FunnelCrossEntryBehavior] = mapped_column(
        Enum(FunnelCrossEntryBehavior), default=FunnelCrossEntryBehavior.deny
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    steps: Mapped[list["FunnelStep"]] = relationship(
        back_populates="funnel",
        cascade="all, delete-orphan",
        order_by="FunnelStep.order",
    )


class FunnelStep(Base):
    __tablename__ = "funnel_steps"
    __table_args__ = (
        UniqueConstraint("funnel_id", "step_key", name="uq_funnel_step_key"),
        Index("ix_funnel_steps_funnel_order", "funnel_id", "order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    funnel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("funnels.id", ondelete="CASCADE"))
    order: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(255))
    step_key: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    funnel: Mapped["Funnel"] = relationship(back_populates="steps")


class UserFunnelState(Base):
    __tablename__ = "user_funnel_state"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id", ondelete="CASCADE"), index=True)
    funnel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("funnels.id", ondelete="CASCADE"), index=True)
    current_step_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("funnel_steps.id", ondelete="SET NULL"))
    status: Mapped[FunnelStatus] = mapped_column(Enum(FunnelStatus), default=FunnelStatus.active)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="funnel_states")


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(String(100))  # ключ из app/products.py
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.pending)
    payment_provider_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="purchases")


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id", ondelete="CASCADE"), index=True)
    task_type: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    execute_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[ScheduledTaskStatus] = mapped_column(Enum(ScheduledTaskStatus), default=ScheduledTaskStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

## Задача 9 — app/schemas/step_config.py (упрощённая схема)

```python
from typing import Literal, List, Optional, Union
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


# ===== Действия кнопок (4 типа) =====

class ActionUrl(BaseModel):
    type: Literal["url"]
    value: str  # URL


class ActionGotoStep(BaseModel):
    type: Literal["goto_step"]
    value: str  # step_key целевого шага


class ActionAddTag(BaseModel):
    type: Literal["add_tag"]
    value: str  # название тега


class ActionPayProduct(BaseModel):
    type: Literal["pay_product"]
    value: str  # product_id из app/products.py


ButtonAction = Union[ActionUrl, ActionGotoStep, ActionAddTag, ActionPayProduct]


# ===== Кнопка =====

class Button(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    text: str = Field(min_length=1, max_length=64)
    action: ButtonAction


# ===== Типы сообщений (3 типа) =====

class TextMessage(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: Literal["text"]
    content: str = Field(max_length=4000)  # HTML-форматированный
    delay_after: int = Field(ge=0, default=0)  # задержка после этого сообщения, в секундах


class PhotoMessage(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: Literal["photo"]
    file_id: str  # Telegram file_id
    caption: Optional[str] = Field(default=None, max_length=1024)
    delay_after: int = Field(ge=0, default=0)


class DocumentMessage(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: Literal["document"]
    file_id: str
    caption: Optional[str] = Field(default=None, max_length=1024)
    delay_after: int = Field(ge=0, default=0)


class ButtonGroup(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: Literal["buttons"]
    buttons: List[Button] = []


Block = Union[TextMessage, PhotoMessage, DocumentMessage, ButtonGroup]


# ===== Шаг =====

class StepConfig(BaseModel):
    """Полная конфигурация одного шага воронки."""
    delay_before_seconds: int = Field(ge=0, default=0)
    wait_for_payment: bool = False
    blocks: List[Block] = []
    add_tags_after: List[str] = []
    next_step: str = "auto"  # "auto" | step_key | "end"
```

## Задача 10 — Alembic

**alembic.ini** — стандартный, со ссылкой на `%(DATABASE_URL)s`:
```ini
[alembic]
script_location = alembic
sqlalchemy.url = driver://user:pass@localhost/dbname

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers = console
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers = console
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

**alembic/env.py** — подключи `settings.database_url` и `Base.metadata`. Миграции должны работать в async-режиме через `async_engine_from_config`.

**alembic/versions/001_initial_schema.py** — **не заглушка**, а полноценная миграция, создающая все 7 таблиц с enum, индексами, foreign keys. Сгенерируй её вручную или через `alembic revision --autogenerate` после создания моделей, но убедись что она реально рабочая.

В миграции должны быть 7 команд `op.create_table`:
- users
- user_tags
- funnels
- funnel_steps
- user_funnel_state
- purchases
- scheduled_tasks

И 4 enum-типа: `funnelcrossentrybehavior`, `funnelstatus`, `paymentstatus`, `scheduledtaskstatus`.

## Задача 11 — app/db/seed.py (стартовая воронка)

Создай одну стартовую воронку `welcome` с 5 шагами, демонстрирующими все возможности:

```python
"""
Seed-скрипт. Создаёт 1 стартовую воронку 'welcome' с примером всех типов шагов.
Идемпотентный — повторный запуск не создаёт дубликатов.
"""

import asyncio
from app.db.session import AsyncSessionLocal
from app.db.models import Funnel, FunnelStep, FunnelCrossEntryBehavior
from app.schemas.step_config import (
    StepConfig, TextMessage, ButtonGroup, Button,
    ActionGotoStep, ActionAddTag, ActionPayProduct, ActionUrl,
)
from sqlalchemy import select
from uuid import uuid4


async def seed():
    async with AsyncSessionLocal() as db:
        # Проверка идемпотентности
        existing = await db.execute(select(Funnel).where(Funnel.entry_key == "welcome"))
        if existing.scalar_one_or_none():
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

        # Шаг 1: приветствие
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

        # Шаг 2: выбор трека
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

        # Шаг 3а: карьера
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

        # Шаг 3б: бизнес
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

        # Шаг 3в: саморазвитие
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
        print(f"Seed successful: funnel 'welcome' with {5} steps created")


if __name__ == "__main__":
    asyncio.run(seed())
```

## Задача 12 — tests/test_models.py

Минимальный тест, чтобы убедиться, что Pydantic-схема работает:

```python
import pytest
from uuid import UUID
from app.schemas.step_config import (
    StepConfig, TextMessage, ButtonGroup, Button,
    ActionUrl, ActionGotoStep, ActionAddTag, ActionPayProduct,
)


def test_empty_step_config():
    config = StepConfig()
    assert config.delay_before_seconds == 0
    assert config.wait_for_payment is False
    assert config.blocks == []
    assert config.next_step == "auto"


def test_step_with_text_and_buttons():
    config = StepConfig(
        blocks=[
            TextMessage(type="text", content="Hello"),
            ButtonGroup(
                type="buttons",
                buttons=[
                    Button(text="URL", action=ActionUrl(type="url", value="https://t.me")),
                    Button(text="Goto", action=ActionGotoStep(type="goto_step", value="next_step")),
                    Button(text="Tag", action=ActionAddTag(type="add_tag", value="clicked")),
                    Button(text="Pay", action=ActionPayProduct(type="pay_product", value="community")),
                ],
            ),
        ]
    )
    assert len(config.blocks) == 2
    assert config.blocks[1].buttons[0].action.type == "url"


def test_serialization_roundtrip():
    config = StepConfig(
        blocks=[TextMessage(type="text", content="Test")],
        add_tags_after=["test_tag"],
    )
    data = config.model_dump(mode="json")
    restored = StepConfig(**data)
    assert restored.blocks[0].content == "Test"
    assert restored.add_tags_after == ["test_tag"]


def test_invalid_action_type_rejected():
    with pytest.raises(Exception):
        StepConfig(
            blocks=[
                ButtonGroup(
                    type="buttons",
                    buttons=[
                        {"text": "Bad", "action": {"type": "unknown", "value": "x"}},
                    ],
                ),
            ]
        )
```

## Acceptance Criteria

Выполни последовательно команды и покажи реальный вывод каждой:

```bash
# 1. Создать .env из шаблона
cp .env.example .env
# Заполнить минимум BOT_TOKEN и ADMIN_SECRET_PATH (любыми значениями)

# 2. Поднять сервисы
docker compose up -d db redis
sleep 5
docker compose ps

# 3. Применить миграции и seed
docker compose up init-db
# Должно выполниться и завершиться без ошибок

# 4. Проверить БД
docker compose exec db psql -U community_user -d community_db -c "\dt"
# Должно быть 7 таблиц + alembic_version

docker compose exec db psql -U community_user -d community_db -c "SELECT COUNT(*) FROM funnels;"
# Должно быть 1

docker compose exec db psql -U community_user -d community_db -c "SELECT COUNT(*) FROM funnel_steps;"
# Должно быть 5

docker compose exec db psql -U community_user -d community_db -c "SELECT step_key, jsonb_pretty(config) FROM funnel_steps LIMIT 1;"
# Должен вернуть валидный JSON

# 5. Прогнать тесты
pip install -e ".[dev]"
pytest tests/ -v
# Все тесты должны пройти
```

**Важно:** покажи реальный вывод каждой команды. Не "должно получиться", а фактический вывод.

## Важные замечания

- Не добавляй в модели ничего, кроме описанного выше. Никаких `Track`, `BotSetting`, `CommunityTrack` — этих таблиц нет.
- Не создавай папки `app/bot/`, `app/api/`, `app/funnels/`, `app/tasks/` — они для следующих промптов.
- `alembic/versions/001_initial_schema.py` должна быть **реально рабочей**, не `pass`. Проверь через прогон миграции на чистой БД.
- Используй `JSONB`, не `JSON` — для индексации и производительности.
- Все `DateTime` с `timezone=True`, для корректной работы с временем.
- В Pydantic-схеме используй `Union` для полиморфных полей (Block, ButtonAction) — Pydantic v2 сам определит тип по полю `type`.
- Если `alembic revision --autogenerate` не запускается из-за проблем с async — напиши миграцию руками согласно моделям. Это долго, но надёжнее.

После успешного выполнения проверок из Acceptance — промпт закрыт, переходим к Промпту 2 (бот + движок).
