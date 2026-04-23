# Промпт 3 — REST API для админки + Webhook платежей ЮKassa

## Роль

Ты senior backend-разработчик на FastAPI. Промпты 1 и 2 выполнены — БД и бот работают. Сейчас добавляешь HTTP-слой: REST API для админки (Промпт 4 будет использовать эти эндпоинты) и webhook для подтверждения оплат от ЮKassa.

## Контекст

Проект `community-bot`. Бот на aiogram 3 работает. Воронки сохраняются в `funnel_steps.config` как JSONB, валидация через Pydantic-схему `app/schemas/step_config.py`. В БД есть 7 таблиц. Seed создал воронку `welcome`.

Этот промпт добавляет:
1. FastAPI-приложение в `app/api/main.py`
2. REST API для управления воронками и шагами (`/api/funnels/*`)
3. REST API для просмотра пользователей и аналитики (`/api/users`, `/api/analytics`)
4. Webhook для ЮKassa (`/payments/webhook`)
5. Интеграцию с движком: после оплаты воронка продолжается

## Архитектурные принципы

### 1. Шаг — атомарный объект

Никаких отдельных эндпоинтов для сообщений или кнопок. Только `PUT /api/funnels/{id}/steps/{step_id}` с полным `config`.

### 2. Защита админки — по секретному пути

В `.env` есть `ADMIN_SECRET_PATH`. Все эндпоинты админки префиксуются этим значением:
- `/admin/{ADMIN_SECRET_PATH}/funnels` (Промпт 4 — HTML)
- `/api/{ADMIN_SECRET_PATH}/funnels` (этот промпт — REST)

Без знания секрета эндпоинты отдают 404. Проще, чем пароли.

### 3. Единый формат ошибок

```json
{"error": {"code": "not_found", "message": "..."}}
```

### 4. ЮKassa webhook — идемпотентен

Если ЮKassa пришлёт один и тот же event дважды — второй игнорируем. Проверяем `payment_provider_id` в таблице `purchases`.

## Структура (добавляется к существующему проекту)

```
app/
├── api/                           # НОВОЕ
│   ├── __init__.py
│   ├── main.py                    # FastAPI app, middleware, error handlers
│   ├── deps.py                    # dependencies: get_db, verify_admin
│   └── routes/
│       ├── __init__.py
│       ├── funnels.py             # /api/{secret}/funnels/*
│       ├── users.py               # /api/{secret}/users
│       ├── analytics.py           # /api/{secret}/analytics
│       └── payments.py            # /payments/webhook
├── schemas/
│   └── api.py                     # НОВОЕ — Pydantic-схемы для API
└── services/                      # НОВОЕ
    ├── __init__.py
    └── funnels.py                 # бизнес-логика для funnels API
```

## Задача 1 — Обновить docker-compose.yml

Добавить сервис `api`:

```yaml
  api:
    build: .
    command: uvicorn app.api.main:app --host 0.0.0.0 --port 8000
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      init-db:
        condition: service_completed_successfully
    restart: unless-stopped
```

Остальные сервисы не трогать.

## Задача 2 — app/schemas/api.py

```python
from typing import Optional, List, Literal
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from app.schemas.step_config import StepConfig


# ===== Воронки =====

class FunnelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    entry_key: Optional[str] = Field(default=None, max_length=120, pattern=r"^[a-z0-9_]+$")
    cross_entry_behavior: Literal["allow", "deny"] = "deny"


class FunnelUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    entry_key: Optional[str] = Field(default=None, max_length=120, pattern=r"^[a-z0-9_]+$")
    is_active: Optional[bool] = None
    is_archived: Optional[bool] = None
    cross_entry_behavior: Optional[Literal["allow", "deny"]] = None


class StepSummary(BaseModel):
    id: UUID
    order: int
    name: str
    step_key: str
    is_active: bool
    first_message_preview: str  # первые 80 символов первого текстового сообщения


class FunnelRead(BaseModel):
    id: UUID
    name: str
    entry_key: Optional[str]
    is_active: bool
    is_archived: bool
    cross_entry_behavior: str
    created_at: datetime
    updated_at: datetime
    steps_count: int
    active_users_count: int

    model_config = {"from_attributes": True}


class FunnelDetail(FunnelRead):
    steps: List[StepSummary] = []


# ===== Шаги =====

class StepCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    step_key: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_]+$")
    order: Optional[int] = None
    config: StepConfig = StepConfig()


class StepUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    step_key: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_]+$")
    is_active: bool = True
    config: StepConfig


class StepReorder(BaseModel):
    step_ids_in_order: List[UUID]


class StepRead(BaseModel):
    id: UUID
    funnel_id: UUID
    order: int
    name: str
    step_key: str
    is_active: bool
    config: StepConfig
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ===== Пользователи =====

class UserListItem(BaseModel):
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    current_funnel_name: Optional[str]
    current_step_name: Optional[str]
    tags: List[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ===== Аналитика =====

class AnalyticsSummary(BaseModel):
    new_users_count: int
    total_users_count: int
    payments_count: int
    revenue_total: float
    conversion_percent: float  # /start → первая оплата


class FunnelAnalytics(BaseModel):
    funnel_id: UUID
    funnel_name: str
    steps_stats: List[dict]  # [{step_name, users_count, percent}, ...]


# ===== Ошибки =====

class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
```

## Задача 3 — app/api/deps.py

```python
from fastapi import Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.config import settings


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def verify_secret(secret: str = Path(...)) -> str:
    """Проверить секретный путь админки. Без знания секрета — 404."""
    if secret != settings.admin_secret_path:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not Found"}})
    return secret
```

## Задача 4 — app/api/main.py

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError

from app.api.routes import funnels, users, analytics, payments

app = FastAPI(title="Community Bot API", version="0.1.0")


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": "Invalid request", "details": exc.errors()}},
    )


@app.exception_handler(IntegrityError)
async def integrity_handler(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={"error": {"code": "conflict", "message": "Resource already exists"}},
    )


@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": str(exc)}},
    )


# Health check — доступен всем
@app.get("/health")
async def health():
    return {"status": "ok"}


# Роуты
app.include_router(funnels.router)
app.include_router(users.router)
app.include_router(analytics.router)
app.include_router(payments.router)
```

## Задача 5 — app/services/funnels.py

```python
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from app.db.models import Funnel, FunnelStep, UserFunnelState, FunnelStatus
from app.schemas.step_config import StepConfig, TextMessage


async def get_funnel_with_stats(db: AsyncSession, funnel_id: UUID) -> dict:
    funnel = await db.get(Funnel, funnel_id)
    if not funnel:
        return None

    steps_count_q = await db.execute(
        select(func.count(FunnelStep.id)).where(FunnelStep.funnel_id == funnel_id)
    )
    steps_count = steps_count_q.scalar_one()

    active_users_q = await db.execute(
        select(func.count(UserFunnelState.id)).where(
            UserFunnelState.funnel_id == funnel_id,
            UserFunnelState.status == FunnelStatus.active,
        )
    )
    active_users_count = active_users_q.scalar_one()

    return {
        "id": funnel.id,
        "name": funnel.name,
        "entry_key": funnel.entry_key,
        "is_active": funnel.is_active,
        "is_archived": funnel.is_archived,
        "cross_entry_behavior": funnel.cross_entry_behavior.value,
        "created_at": funnel.created_at,
        "updated_at": funnel.updated_at,
        "steps_count": steps_count,
        "active_users_count": active_users_count,
    }


def extract_first_message_preview(config_dict: dict) -> str:
    """Достать первые 80 символов первого TextMessage для превью в списке шагов."""
    try:
        config = StepConfig(**config_dict)
        for block in config.blocks:
            if isinstance(block, TextMessage):
                text = block.content[:80]
                return text + "..." if len(block.content) > 80 else text
    except Exception:
        pass
    return ""


async def get_next_order(db: AsyncSession, funnel_id: UUID) -> int:
    result = await db.execute(
        select(func.max(FunnelStep.order)).where(FunnelStep.funnel_id == funnel_id)
    )
    max_order = result.scalar_one()
    return (max_order or 0) + 1


async def has_active_users_on_step(db: AsyncSession, step_id: UUID) -> bool:
    result = await db.execute(
        select(func.count(UserFunnelState.id)).where(
            UserFunnelState.current_step_id == step_id,
            UserFunnelState.status == FunnelStatus.active,
        )
    )
    return result.scalar_one() > 0


async def duplicate_funnel(db: AsyncSession, source_id: UUID) -> Funnel:
    """Копия воронки со всеми шагами, UUID внутри config перегенерируются."""
    import uuid as _uuid
    import json

    source = await db.get(Funnel, source_id)
    if not source:
        return None

    new_funnel = Funnel(
        name=f"{source.name} (копия)",
        entry_key=None,  # не дублируем — потенциальный конфликт
        is_active=False,
        cross_entry_behavior=source.cross_entry_behavior,
    )
    db.add(new_funnel)
    await db.flush()

    steps_result = await db.execute(
        select(FunnelStep).where(FunnelStep.funnel_id == source_id).order_by(FunnelStep.order)
    )
    for step in steps_result.scalars().all():
        # Перегенерируем все UUID внутри config.blocks
        config_dict = json.loads(json.dumps(step.config))  # deep copy
        for block in config_dict.get("blocks", []):
            block["id"] = str(_uuid.uuid4())
            if block.get("type") == "buttons":
                for btn in block.get("buttons", []):
                    btn["id"] = str(_uuid.uuid4())

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
```

## Задача 6 — app/api/routes/funnels.py

Полный CRUD для воронок и шагов. Роутер с префиксом `/api/{secret}/funnels`:

```python
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_db, verify_secret
from app.db.models import Funnel, FunnelStep, FunnelCrossEntryBehavior
from app.schemas.api import (
    FunnelCreate, FunnelUpdate, FunnelRead, FunnelDetail, StepSummary,
    StepCreate, StepUpdate, StepReorder, StepRead,
)
from app.schemas.step_config import StepConfig
from app.services.funnels import (
    get_funnel_with_stats, extract_first_message_preview,
    get_next_order, has_active_users_on_step, duplicate_funnel,
)

router = APIRouter(prefix="/api/{secret}", dependencies=[Depends(verify_secret)])


# ===== Воронки =====

@router.get("/funnels", response_model=list[FunnelRead])
async def list_funnels(include_archived: bool = False, db: AsyncSession = Depends(get_db)):
    query = select(Funnel)
    if not include_archived:
        query = query.where(Funnel.is_archived == False)
    result = await db.execute(query.order_by(Funnel.created_at.desc()))
    funnels = result.scalars().all()
    return [await get_funnel_with_stats(db, f.id) for f in funnels]


@router.post("/funnels", response_model=FunnelRead, status_code=201)
async def create_funnel(data: FunnelCreate, db: AsyncSession = Depends(get_db)):
    funnel = Funnel(
        name=data.name,
        entry_key=data.entry_key,
        cross_entry_behavior=FunnelCrossEntryBehavior(data.cross_entry_behavior),
    )
    db.add(funnel)
    await db.commit()
    return await get_funnel_with_stats(db, funnel.id)


@router.get("/funnels/{funnel_id}", response_model=FunnelDetail)
async def get_funnel(funnel_id: UUID, db: AsyncSession = Depends(get_db)):
    stats = await get_funnel_with_stats(db, funnel_id)
    if not stats:
        raise HTTPException(404, {"error": {"code": "not_found", "message": "Funnel not found"}})

    steps_result = await db.execute(
        select(FunnelStep).where(FunnelStep.funnel_id == funnel_id).order_by(FunnelStep.order)
    )
    steps = [
        StepSummary(
            id=s.id,
            order=s.order,
            name=s.name,
            step_key=s.step_key,
            is_active=s.is_active,
            first_message_preview=extract_first_message_preview(s.config),
        )
        for s in steps_result.scalars().all()
    ]
    return {**stats, "steps": steps}


@router.patch("/funnels/{funnel_id}", response_model=FunnelRead)
async def update_funnel(funnel_id: UUID, data: FunnelUpdate, db: AsyncSession = Depends(get_db)):
    funnel = await db.get(Funnel, funnel_id)
    if not funnel:
        raise HTTPException(404, {"error": {"code": "not_found", "message": "Funnel not found"}})

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "cross_entry_behavior" and value:
            value = FunnelCrossEntryBehavior(value)
        setattr(funnel, field, value)
    await db.commit()
    return await get_funnel_with_stats(db, funnel_id)


@router.delete("/funnels/{funnel_id}", status_code=204)
async def archive_funnel(funnel_id: UUID, db: AsyncSession = Depends(get_db)):
    funnel = await db.get(Funnel, funnel_id)
    if not funnel:
        raise HTTPException(404, {"error": {"code": "not_found", "message": "Funnel not found"}})
    funnel.is_archived = True
    funnel.is_active = False
    await db.commit()


@router.post("/funnels/{funnel_id}/duplicate", response_model=FunnelRead, status_code=201)
async def duplicate_funnel_endpoint(funnel_id: UUID, db: AsyncSession = Depends(get_db)):
    new_funnel = await duplicate_funnel(db, funnel_id)
    if not new_funnel:
        raise HTTPException(404, {"error": {"code": "not_found", "message": "Funnel not found"}})
    return await get_funnel_with_stats(db, new_funnel.id)


# ===== Шаги =====

@router.get("/funnels/{funnel_id}/steps", response_model=list[StepRead])
async def list_steps(funnel_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FunnelStep).where(FunnelStep.funnel_id == funnel_id).order_by(FunnelStep.order)
    )
    return list(result.scalars().all())


@router.post("/funnels/{funnel_id}/steps", response_model=StepRead, status_code=201)
async def create_step(funnel_id: UUID, data: StepCreate, db: AsyncSession = Depends(get_db)):
    order = data.order if data.order is not None else await get_next_order(db, funnel_id)
    step = FunnelStep(
        funnel_id=funnel_id,
        order=order,
        name=data.name,
        step_key=data.step_key,
        config=data.config.model_dump(mode="json"),
    )
    db.add(step)
    await db.commit()
    return step


@router.get("/funnels/{funnel_id}/steps/{step_id}", response_model=StepRead)
async def get_step(funnel_id: UUID, step_id: UUID, db: AsyncSession = Depends(get_db)):
    step = await db.get(FunnelStep, step_id)
    if not step or step.funnel_id != funnel_id:
        raise HTTPException(404, {"error": {"code": "not_found", "message": "Step not found"}})
    return step


@router.put("/funnels/{funnel_id}/steps/{step_id}", response_model=StepRead)
async def update_step(funnel_id: UUID, step_id: UUID, data: StepUpdate, db: AsyncSession = Depends(get_db)):
    step = await db.get(FunnelStep, step_id)
    if not step or step.funnel_id != funnel_id:
        raise HTTPException(404, {"error": {"code": "not_found", "message": "Step not found"}})
    step.name = data.name
    step.step_key = data.step_key
    step.is_active = data.is_active
    step.config = data.config.model_dump(mode="json")
    await db.commit()
    return step


@router.delete("/funnels/{funnel_id}/steps/{step_id}", status_code=204)
async def delete_step(funnel_id: UUID, step_id: UUID, db: AsyncSession = Depends(get_db)):
    step = await db.get(FunnelStep, step_id)
    if not step or step.funnel_id != funnel_id:
        raise HTTPException(404, {"error": {"code": "not_found", "message": "Step not found"}})
    if await has_active_users_on_step(db, step_id):
        raise HTTPException(409, {"error": {"code": "conflict", "message": "Step has active users"}})
    await db.delete(step)
    await db.commit()


@router.post("/funnels/{funnel_id}/steps/reorder", response_model=list[StepRead])
async def reorder_steps(funnel_id: UUID, data: StepReorder, db: AsyncSession = Depends(get_db)):
    # Проверить, что все ID принадлежат воронке
    result = await db.execute(
        select(FunnelStep).where(FunnelStep.funnel_id == funnel_id)
    )
    steps = {s.id: s for s in result.scalars().all()}
    if set(data.step_ids_in_order) != set(steps.keys()):
        raise HTTPException(400, {"error": {"code": "bad_request", "message": "Step IDs don't match funnel steps"}})

    for new_order, step_id in enumerate(data.step_ids_in_order, start=1):
        steps[step_id].order = new_order
    await db.commit()

    result = await db.execute(
        select(FunnelStep).where(FunnelStep.funnel_id == funnel_id).order_by(FunnelStep.order)
    )
    return list(result.scalars().all())
```

## Задача 7 — app/api/routes/users.py

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, verify_secret
from app.db.models import User, UserFunnelState, FunnelStep, Funnel, FunnelStatus
from app.schemas.api import UserListItem

router = APIRouter(prefix="/api/{secret}", dependencies=[Depends(verify_secret)])


@router.get("/users", response_model=list[UserListItem])
async def list_users(limit: int = 100, offset: int = 0, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User)
        .options(selectinload(User.tags), selectinload(User.funnel_states))
        .order_by(User.created_at.desc())
        .limit(limit).offset(offset)
    )
    users = result.scalars().all()

    items = []
    for user in users:
        # Текущее активное состояние
        active_state = next(
            (s for s in user.funnel_states if s.status == FunnelStatus.active), None
        )
        funnel_name = step_name = None
        if active_state:
            funnel = await db.get(Funnel, active_state.funnel_id)
            step = await db.get(FunnelStep, active_state.current_step_id) if active_state.current_step_id else None
            funnel_name = funnel.name if funnel else None
            step_name = step.name if step else None

        items.append(UserListItem(
            telegram_id=user.telegram_id,
            username=user.username,
            first_name=user.first_name,
            current_funnel_name=funnel_name,
            current_step_name=step_name,
            tags=[t.tag for t in user.tags],
            created_at=user.created_at,
        ))
    return items
```

## Задача 8 — app/api/routes/analytics.py

```python
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_db, verify_secret
from app.db.models import User, Purchase, PaymentStatus, Funnel, FunnelStep, UserFunnelState
from app.schemas.api import AnalyticsSummary, FunnelAnalytics

router = APIRouter(prefix="/api/{secret}", dependencies=[Depends(verify_secret)])


@router.get("/analytics/summary", response_model=AnalyticsSummary)
async def get_summary(period_days: int = Query(default=30, ge=1), db: AsyncSession = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=period_days)

    new_users_q = await db.execute(
        select(func.count(User.telegram_id)).where(User.created_at >= since)
    )
    new_users = new_users_q.scalar_one()

    total_users_q = await db.execute(select(func.count(User.telegram_id)))
    total_users = total_users_q.scalar_one()

    payments_q = await db.execute(
        select(func.count(Purchase.id)).where(
            Purchase.status == PaymentStatus.paid,
            Purchase.paid_at >= since,
        )
    )
    payments_count = payments_q.scalar_one()

    revenue_q = await db.execute(
        select(func.coalesce(func.sum(Purchase.amount), 0)).where(
            Purchase.status == PaymentStatus.paid,
            Purchase.paid_at >= since,
        )
    )
    revenue = float(revenue_q.scalar_one())

    # Конверсия: пользователей с хотя бы 1 оплатой / всего пользователей
    users_with_payment_q = await db.execute(
        select(func.count(func.distinct(Purchase.user_id))).where(Purchase.status == PaymentStatus.paid)
    )
    users_with_payment = users_with_payment_q.scalar_one()
    conversion = (users_with_payment / total_users * 100) if total_users else 0

    return AnalyticsSummary(
        new_users_count=new_users,
        total_users_count=total_users,
        payments_count=payments_count,
        revenue_total=revenue,
        conversion_percent=round(conversion, 2),
    )


@router.get("/analytics/funnels", response_model=list[FunnelAnalytics])
async def get_funnel_analytics(db: AsyncSession = Depends(get_db)):
    """Для каждой активной воронки — сколько пользователей на каждом шаге."""
    funnels_q = await db.execute(
        select(Funnel).where(Funnel.is_archived == False)
    )
    funnels = funnels_q.scalars().all()

    result = []
    for funnel in funnels:
        steps_q = await db.execute(
            select(FunnelStep).where(FunnelStep.funnel_id == funnel.id).order_by(FunnelStep.order)
        )
        steps = steps_q.scalars().all()

        # Считаем, сколько пользователей прошли каждый шаг
        # Прошедший шаг = пользователь был на нём или дальше
        # Упрощение: считаем уникальных пользователей, у которых current_step_id = step.id или order >= step.order
        steps_stats = []
        first_count = None
        for step in steps:
            count_q = await db.execute(
                select(func.count(func.distinct(UserFunnelState.user_id))).where(
                    UserFunnelState.funnel_id == funnel.id,
                )
            )
            total_in_funnel = count_q.scalar_one()

            # Пользователи на этом шаге или дальше
            ahead_q = await db.execute(
                select(func.count(func.distinct(UserFunnelState.user_id))).where(
                    UserFunnelState.funnel_id == funnel.id,
                    UserFunnelState.current_step_id.in_(
                        select(FunnelStep.id).where(
                            FunnelStep.funnel_id == funnel.id,
                            FunnelStep.order >= step.order,
                        )
                    ),
                )
            )
            ahead_count = ahead_q.scalar_one()

            if first_count is None:
                first_count = total_in_funnel or 1  # чтобы не было деления на 0

            percent = (ahead_count / first_count * 100) if first_count else 0
            steps_stats.append({
                "step_name": step.name,
                "users_count": ahead_count,
                "percent": round(percent, 1),
            })

        result.append(FunnelAnalytics(
            funnel_id=funnel.id,
            funnel_name=funnel.name,
            steps_stats=steps_stats,
        ))

    return result
```

## Задача 9 — app/api/routes/payments.py (ЮKassa webhook)

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.api.deps import get_db
from app.db.models import Purchase, PaymentStatus, User, UserFunnelState, FunnelStatus
from app.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments")


@router.post("/webhook")
async def yookassa_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Webhook от ЮKassa.
    
    Формат события: {"event": "payment.succeeded", "object": {"id": "...", "status": "succeeded", ...}}
    
    Идемпотентность: проверяем payment_provider_id, дубли игнорируем.
    """
    data = await request.json()
    logger.info(f"YooKassa webhook: {data}")

    event = data.get("event")
    obj = data.get("object", {})

    if event not in ("payment.succeeded", "payment.waiting_for_capture"):
        return {"status": "ignored"}

    payment_id = obj.get("id")
    if not payment_id:
        raise HTTPException(400, "missing payment id")

    # Найти Purchase по payment_provider_id
    result = await db.execute(
        select(Purchase).where(Purchase.payment_provider_id == payment_id)
    )
    purchase = result.scalar_one_or_none()

    if not purchase:
        logger.warning(f"Purchase with provider_id {payment_id} not found")
        return {"status": "not_found"}

    if purchase.status == PaymentStatus.paid:
        # Идемпотентность: уже обработано
        return {"status": "already_processed"}

    # Отметить как оплаченный
    purchase.status = PaymentStatus.paid
    purchase.paid_at = datetime.now(timezone.utc)
    await db.commit()

    # Продолжить воронку, если пользователь на шаге с wait_for_payment
    user = await db.get(User, purchase.user_id)
    if user:
        state_q = await db.execute(
            select(UserFunnelState).where(
                UserFunnelState.user_id == user.telegram_id,
                UserFunnelState.status == FunnelStatus.active,
            )
        )
        state = state_q.scalar_one_or_none()
        if state:
            # Запустить движок
            from app.bot.main import IPv4OnlySession
            from aiogram import Bot
            from aiogram.client.default import DefaultBotProperties
            from app.funnels.engine import FunnelEngine

            session = IPv4OnlySession()
            bot = Bot(
                token=settings.bot_token,
                default=DefaultBotProperties(parse_mode="HTML"),
                session=session,
            )
            try:
                engine = FunnelEngine(bot=bot, db=db)
                await engine.continue_after_payment(user, state.funnel_id)
            finally:
                await session.close()

    return {"status": "ok"}
```

## Задача 10 — Обновить ActionPayProduct в app/funnels/actions.py

Реальная интеграция с ЮKassa (заменяет заглушку из Промпта 2):

```python
# В функции handle_action, ветка ActionPayProduct:

if isinstance(action, ActionPayProduct):
    product = PRODUCTS.get(action.value)
    if not product:
        await bot.send_message(user.telegram_id, "Продукт не найден")
        return

    # Если ЮKassa не настроена — заглушка
    if not settings.yookassa_shop_id or not settings.yookassa_secret_key:
        # ... предыдущая заглушка
        return

    # Создать платёж через ЮKassa
    import uuid as _uuid
    import base64
    import httpx

    idempotence_key = str(_uuid.uuid4())
    auth = base64.b64encode(
        f"{settings.yookassa_shop_id}:{settings.yookassa_secret_key}".encode()
    ).decode()

    payload = {
        "amount": {"value": f"{product['price']:.2f}", "currency": "RUB"},
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": f"https://t.me/{(await bot.get_me()).username}",
        },
        "description": product["name"],
        "metadata": {
            "user_id": str(user.telegram_id),
            "product_id": action.value,
        },
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.yookassa.ru/v3/payments",
            json=payload,
            headers={
                "Authorization": f"Basic {auth}",
                "Idempotence-Key": idempotence_key,
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )

    if resp.status_code != 200:
        await bot.send_message(user.telegram_id, "Не удалось создать платёж. Попробуйте позже.")
        return

    payment_data = resp.json()
    payment_url = payment_data["confirmation"]["confirmation_url"]

    # Записать Purchase
    purchase = Purchase(
        user_id=user.telegram_id,
        product_id=action.value,
        amount=Decimal(product["price"]),
        status=PaymentStatus.pending,
        payment_provider_id=payment_data["id"],
    )
    db.add(purchase)
    await db.commit()

    # Отправить ссылку пользователю
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Оплатить {product['price']} ₽", url=payment_url)]
    ])
    await bot.send_message(
        user.telegram_id,
        f"💳 Для оплаты <b>{product['name']}</b> нажмите кнопку ниже.\n"
        f"После оплаты вернитесь в бот — доступ откроется автоматически.",
        parse_mode="HTML",
        reply_markup=pay_kb,
    )
    return
```

Добавить `httpx>=0.26.0` в зависимости (если ещё нет).

## Задача 11 — Добавить httpx в pyproject.toml

```toml
dependencies = [
    # ... существующие
    "httpx>=0.26.0",
]
```

## Задача 12 — Тесты

Создай `tests/test_api.py` с минимум 5 тестами (используй httpx.AsyncClient):

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.api.main import app
from app.config import settings


BASE_URL = f"/api/{settings.admin_secret_path}"


@pytest.mark.asyncio
async def test_health_no_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_wrong_secret_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/wrong-secret/funnels")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_funnels():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"{BASE_URL}/funnels")
    assert resp.status_code == 200
    # seed создал welcome
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_create_funnel():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(f"{BASE_URL}/funnels", json={"name": "Test funnel", "entry_key": "test_xyz"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Test funnel"


@pytest.mark.asyncio
async def test_duplicate_entry_key_returns_409():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # welcome уже существует в seed
        resp = await client.post(f"{BASE_URL}/funnels", json={"name": "Duplicate", "entry_key": "welcome"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_analytics_summary():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"{BASE_URL}/analytics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_users_count" in data
    assert "revenue_total" in data
```

## Acceptance criteria

```bash
# 1. Пересобрать и запустить
docker compose up -d --build
sleep 10

# 2. Проверить сервисы
docker compose ps
# api должен быть Up

# 3. Health check
curl -s http://localhost:8000/health

# 4. Swagger UI (открыть в браузере)
# http://localhost:8000/docs

# 5. Список воронок (подставь секрет из .env)
SECRET=$(grep ADMIN_SECRET_PATH .env | cut -d= -f2)
curl -s "http://localhost:8000/api/$SECRET/funnels" | python3 -m json.tool
# Должна быть воронка welcome

# 6. Неправильный секрет
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8000/api/wrong/funnels"
# Должно быть 404

# 7. Получить детали воронки со списком шагов
FUNNEL_ID=$(curl -s "http://localhost:8000/api/$SECRET/funnels" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
curl -s "http://localhost:8000/api/$SECRET/funnels/$FUNNEL_ID" | python3 -m json.tool
# Должны быть steps_count и список шагов

# 8. Аналитика
curl -s "http://localhost:8000/api/$SECRET/analytics/summary" | python3 -m json.tool

# 9. Тесты
docker compose exec api pytest tests/test_api.py -v
# Все тесты должны пройти
```

**Покажи реальный вывод каждой команды.**

## Важные замечания

- **Webhook URL для ЮKassa:** `https://ваш-домен/payments/webhook`. ЮKassa не умеет отправлять на IP, нужен домен с HTTPS. Для разработки можно использовать ngrok.
- **ЮKassa на тестовом режиме:** если у вас нет настоящих ключей, оставьте `YOOKASSA_SHOP_ID` и `YOOKASSA_SECRET_KEY` пустыми — будет работать заглушка из Промпта 2.
- **Не трогай** `app/bot/`, `app/funnels/engine.py` кроме `actions.py` (там обновление).
- **Pydantic v2 дискриминация:** если при парсинге `StepConfig` из API падает ошибка "can't determine discriminator" — добавь discriminator вручную в Union через `Field(discriminator='type')`.
- **CORS:** в Промпте 4 (HTML-админка) нужен CORS. Пока не добавляй — нечему обращаться.

После успешного выполнения acceptance — промпт закрыт.
