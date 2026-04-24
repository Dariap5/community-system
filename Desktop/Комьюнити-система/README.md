# Community Bot

Telegram-бот, FastAPI API и админка для воронок, оплат, пользователей и аналитики.

## Текущее состояние

- Локальный Docker smoke test проходит: compose `tests` profile — `18/18`.
- Уже исправлены и находятся в рабочем дереве:
  - `app/static/admin/step_editor.js` — шаги больше не открываются пустыми из-за бага в optional chaining;
  - `app/services/funnels.py` — сериализация `cross_entry_behavior` больше не падает, если ORM возвращает строку вместо enum.
- Следующий обязательный шаг перед передачей в прод: обновить VPS этим кодом и перезапустить сервисы, чтобы live-версия увидела фиксы.

## Статус по промптам

- Промпт 1 — готов и проверен.
- Промпт 2 — готов и проверен.
- Промпт 3 — готов и проверен.
- Промпт 4 — готов и проверен.
- Промпт 5 — реализован локально и проверен в Docker, но live VPS ещё нужно синхронизировать и после этого вручную проверить `/start` и админку на боевом токене.

## ⚠️ Перед деплоем на продакшн

Обязательно проверить:

1. **BOT_TOKEN** — токен боевого бота (не dev-бота)
2. **ADMIN_SECRET_PATH** — не значение по умолчанию, а длинная случайная строка (32+ символов)
3. **POSTGRES_PASSWORD** — не `change_me_in_production`
4. **Ссылки на чаты комьюнити** — ведут на реальные чаты (не тестовые)
5. **SUPPORT_USERNAME** — корректный username для поддержки
6. **OFFER_URL** — настоящая ссылка на оферту
7. **ЮKassa** — если подключаете оплату, заполнить `YOOKASSA_SHOP_ID` и `YOOKASSA_SECRET_KEY`, и добавить webhook URL в личном кабинете ЮKassa

После проверки — следовать [docs/deployment.md](docs/deployment.md).

## Структура проекта

```text
.
├── .dockerignore
├── .env
├── .env.example
├── .gitignore
├── Dockerfile
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
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py
│   │   ├── main.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── analytics.py
│   │       ├── funnels.py
│   │       ├── payments.py
│   │       └── users.py
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── handlers.py
│   │   ├── keyboards.py
│   │   ├── main.py
│   │   └── session.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── models.py
│   │   ├── seed.py
│   │   └── session.py
│   ├── funnels/
│   │   ├── __init__.py
│   │   ├── actions.py
│   │   ├── callback_store.py
│   │   ├── engine.py
│   │   ├── keyboard_builder.py
│   │   └── message_sender.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── api.py
│   │   └── step_config.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── funnels.py
│   │   └── payments.py
│   └── tasks/
│       ├── __init__.py
│       ├── celery_app.py
│       └── funnel_tasks.py
├── build/
├── community_bot.egg-info/
├── deploy/
│   ├── backup.sh
│   ├── healthcheck.sh
│   └── nginx/
│       └── community-bot.conf
├── docs/
│   └── deployment.md
├── mvp_spec_final.md
├── prompt_1_foundation.md
├── prompt_2_bot_engine.md
├── prompt_3_api_payments.md
├── prompt_4_admin_ui.md
├── prompt_5_deploy.md
├── promt_fix.md
├── pyproject.toml
└── tests/
  ├── __init__.py
  ├── conftest.py
  ├── test_api.py
  ├── test_engine.py
  └── test_models.py
```

Локальные/генерируемые каталоги, которые не являются исходниками: `.venv/`, `.pytest_cache/`, `build/`, `community_bot.egg-info/`.

## Что где лежит

- `app/api` — FastAPI-приложение, зависимости и HTTP-роуты (`analytics`, `funnels`, `payments`, `users`).
- `app/bot` — Telegram-бот на aiogram: запуск, обработчики, клавиатуры и сессия.
- `app/db` — SQLAlchemy-модели, сессия, seed и общая база моделей.
- `app/funnels` — движок воронок, обработка callback-данных, построение клавиатур и отправка сообщений.
- `app/schemas` — Pydantic-схемы API и конфигурации шагов.
- `app/services` — сервисный слой для воронок и платежей.
- `app/tasks` — Celery app, периодические и фоновые задачи.
- `alembic` — миграции БД; сейчас основа — `001_initial_schema.py`.
- `tests` — API smoke tests, тесты движка и моделей.
- `deploy` — готовые артефакты для VPS: nginx-конфиг, healthcheck и backup.
- `docs/deployment.md` — пошаговый деплой на VPS и финальные проверки.
- `mvp_spec_final.md` и `prompt_*.md` — спецификация и контекст реализации по промптам.

## Текущие проблемы и caveats

- В этом рабочем дереве Git-история расходится с `origin/main`: обычный `git push` отклоняется, потому что remote был force-update и сейчас нужен аккуратный merge/rebase в чистом flat checkout, а не простой fast-forward.
- Для Telegram-бота должен быть ровно один polling-инстанс на один токен. При параллельном локальном стеке появляется `TelegramConflictError`; сейчас дубль-стек остановлен, а свежие логи bot чистые.
- Продакшен-VPS ещё нужно обновить этим кодом и перезапустить стек. Локальные фиксы уже сделаны, но live-сервер может быть на старой версии.
- Вне Docker Compose база не резолвится по имени `db`: локальные интеграционные тесты нужно запускать внутри compose-сети или с отдельным тестовым `DATABASE_URL`.
- Runtime-образ Docker не содержит dev-зависимости и тесты по умолчанию, поэтому smoke tests надо запускать с установкой `.[dev]` внутри контейнера или из отдельной dev-среды.
- На macOS Docker может спотыкаться о путь с кириллицей. Для smoke tests использовался ASCII-symlink вида `/tmp/community-system`.
- `.env` содержит реальные секреты и должен оставаться локальным файлом, не попадать в git.
- Перед передачей в прод нужно перепроверить публичные URL в `.env` (`OFFER_URL`, ссылки на чаты треков и `COMMUNITY_CHAT_URL`) и убедиться, что они совпадают с фактическим доменом и маршрутом после деплоя.

## Что уже проверено

- `node --check` для admin JS проходил после фикса `app/static/admin/step_editor.js`.
- Docker smoke test для API прошёл успешно: `tests/test_api.py` — 8 passed.
- Docker smoke test для всего compose-стека с профилем `tests` прошёл успешно: `18 passed`.
- В коде уже исправлены две проблемы, найденные во время проверки:
  - пустой редактор шага;
  - падение `get_funnel_with_stats()` на `cross_entry_behavior.value`.

## Быстрый старт

1. Скопируй `.env.example` в `.env` и заполни секреты и URL-ы. Минимум нужны `BOT_TOKEN`, `ADMIN_SECRET_PATH`, `DATABASE_URL`, `REDIS_URL`, `COMMUNITY_CHAT_URL`, `TRACK_CAREER_URL`, `TRACK_BUSINESS_URL`, `TRACK_SELFDEV_URL`, `SUPPORT_USERNAME`, `OFFER_URL`, `DEFAULT_FUNNEL_KEY`.
2. Подними весь стек: `docker compose -f docker-compose.yml -p community-bot up -d --build`.
3. Проверь здоровье API: `curl http://localhost:8000/health`.
4. Проверь админку: `curl -I http://localhost:8000/admin/<ADMIN_SECRET_PATH>/funnels`.
5. Для smoke tests поставь dev-зависимости внутри контейнера и прогони `pytest` из compose-сети.

## Production deploy

Для VPS, nginx, SSL, webhook и финальных проверок см. [docs/deployment.md](docs/deployment.md).

Готовые артефакты лежат здесь:

- [deploy/nginx/community-bot.conf](deploy/nginx/community-bot.conf)
- [deploy/healthcheck.sh](deploy/healthcheck.sh)
- [deploy/backup.sh](deploy/backup.sh)