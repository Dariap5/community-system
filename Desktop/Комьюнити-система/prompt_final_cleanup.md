# Промпт-патч — Финальная подготовка перед деплоем

## Роль

Senior разработчик, задача — убрать последние шероховатости перед деплоем на продакшн. Никаких новых фич, только приведение проекта в состояние "можно развернуть спокойно".

## Контекст

Промпты 1-4 выполнены, smoke-тесты проходят (8/8). В рабочем дереве уже исправлены два runtime-бага:
- `app/static/admin/step_editor.js` — пустой редактор шага
- `app/services/funnels.py` — сериализация `cross_entry_behavior`

Но есть несколько неидеальных мест, которые стоит закрыть перед деплоем, чтобы потом не ловить их в проде.

## Задачи

### Задача 1 — Сделать тестовое окружение самодостаточным

**Проблема:** `tests/conftest.py` пустой, `app/db/session.py` жёстко привязан к `settings.database_url`. Из-за этого тесты нельзя запустить вне Docker Compose сети.

**Решение:** добавить в `conftest.py` минимальную конфигурацию, которая позволяет запускать тесты против отдельной тестовой БД через переменную окружения `TEST_DATABASE_URL`, с фолбэком на основную БД.

Перепиши `tests/conftest.py`:

```python
"""
Pytest fixtures для тестов.

Поддерживает два режима:
1. Docker compose — использует DATABASE_URL из .env (основной режим CI)
2. Локально — можно передать TEST_DATABASE_URL для отдельной БД
"""

import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


@pytest_asyncio.fixture
async def client():
    """HTTP-клиент для API-тестов."""
    from app.api.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def secret() -> str:
    """Админский секрет из settings."""
    from app.config import settings
    return settings.admin_secret_path


@pytest.fixture
def api_base(secret) -> str:
    """База API-эндпоинтов с секретом."""
    return f"/api/{secret}"
```

В `pyproject.toml` убедиться, что есть:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

### Задача 2 — Добавить цель для запуска тестов в Docker

**Проблема:** для прогона тестов надо вручную ставить dev-зависимости в контейнер.

**Решение:** добавить в `docker-compose.yml` отдельный сервис `tests` с профилем:

```yaml
  tests:
    build: .
    profiles: ["tests"]
    command: sh -c "pip install -e .[dev] && pytest tests/ -v"
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./tests:/app/tests:ro
```

Теперь запуск тестов:
```bash
docker compose --profile tests up tests
```

Основные сервисы (api, bot, worker, beat, db, redis) при `docker compose up -d` не трогают этот сервис, потому что у него профиль `tests`.

### Задача 3 — Проверить и привести в порядок .env.example

**Проблема:** README упоминает, что нужно проверить публичные URL перед деплоем. Важно, чтобы `.env.example` был полным и понятным.

Перепиши `.env.example` с комментариями для каждого раздела:

```bash
# ==========================================
# БАЗА ДАННЫХ
# ==========================================
POSTGRES_USER=community_user
POSTGRES_PASSWORD=change_me_in_production
POSTGRES_DB=community_db
DATABASE_URL=postgresql+asyncpg://community_user:change_me_in_production@db:5432/community_db

# ==========================================
# REDIS
# ==========================================
REDIS_URL=redis://redis:6379/0

# ==========================================
# TELEGRAM БОТ
# ==========================================
# Получить через @BotFather
BOT_TOKEN=

# ==========================================
# АДМИНКА
# ==========================================
# Секретный путь для доступа к админке.
# Сгенерировать: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
ADMIN_SECRET_PATH=change_me_to_random_string

# ==========================================
# ПЛАТЕЖИ (ЮKassa)
# ==========================================
# Если оставить пустыми — будет заглушка без реальной оплаты
YOOKASSA_SHOP_ID=
YOOKASSA_SECRET_KEY=

# ==========================================
# ССЫЛКИ НА ЧАТЫ КОМЬЮНИТИ
# ==========================================
# Отправляются пользователю после оплаты в зависимости от выбранного трека
# ВАЖНО: перепроверить перед деплоем — это то, что получат реальные клиенты
COMMUNITY_CHAT_URL=https://t.me/+XXXXXXXXXXXXXXX
TRACK_CAREER_URL=https://t.me/+XXXXXXXXXXXXXXX
TRACK_BUSINESS_URL=https://t.me/+XXXXXXXXXXXXXXX
TRACK_SELFDEV_URL=https://t.me/+XXXXXXXXXXXXXXX

# ==========================================
# ПОДДЕРЖКА И ДОКУМЕНТЫ
# ==========================================
# Username без @ — сюда пользователи пишут через меню "Поддержка"
SUPPORT_USERNAME=your_support_username

# URL оферты (например, на лендинге)
OFFER_URL=https://your-landing.com/offer

# ==========================================
# СЦЕНАРИЙ ПО УМОЛЧАНИЮ
# ==========================================
# Какая воронка запускается при /start без параметра (entry_key воронки)
DEFAULT_FUNNEL_KEY=welcome
```

### Задача 4 — Добавить pre-deploy чеклист в README

В `README.md` добавить секцию перед `## Быстрый старт`:

```markdown
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
```

### Задача 5 — Синхронизация локальной версии с VPS

**Проблема:** на VPS сейчас старая версия кода. Два локальных фикса (пустой редактор шага + enum-сериализация) не применены в продакшене.

**Действие:** 

1. Убедиться, что все локальные изменения закоммичены:
```bash
git status
# если есть незакоммиченное — закоммитить
git add .
git commit -m "fix: step editor empty + enum serialization"
git push origin main
```

2. На VPS:
```bash
cd /var/www/community-bot  # или где там развёрнут проект
git pull origin main
docker compose up -d --build
docker compose ps
docker compose logs --tail=30 api
docker compose logs --tail=30 bot
```

3. Проверить, что после обновления:
   - Админка открывается в браузере
   - Редактор шага показывает все поля (не пустой)
   - Воронки отображаются
   - Bot отвечает на `/start`

### Задача 6 — Проверить полный список Docker-сервисов в compose

Проверь `docker-compose.yml` — должны быть 6 основных сервисов + `init-db` + `tests` (с профилем):

- `db` (PostgreSQL)
- `redis`
- `init-db` (разовый, применяет миграции и seed)
- `api` (FastAPI, порт 8000)
- `bot` (aiogram polling)
- `worker` (Celery worker)
- `beat` (Celery beat)
- `tests` (с профилем "tests")

Убедиться, что:
- `restart: unless-stopped` стоит у `api`, `bot`, `worker`, `beat`
- `depends_on` с `condition: service_healthy` для `db` и `redis`
- У `api` порт `8000:8000` (не 8001)
- `init-db` с `restart: "no"` (разовый)

## Acceptance criteria

Покажи в ответе:

1. **Локальный прогон тестов** через Docker:
```bash
docker compose --profile tests up tests
# Должно быть: 8 passed (или больше, если добавил новые)
```

2. **Проверка docker-compose.yml**:
```bash
docker compose config | grep -A 2 "ports:"
# У api должно быть 8000:8000
```

3. **Финальный smoke-test всех критических точек**:
```bash
# Поднять стек
docker compose up -d --build
sleep 15

# 1. Health
curl http://localhost:8000/health

# 2. Swagger
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/docs
# 200

# 3. Админка (с реальным SECRET из .env)
SECRET=$(grep ADMIN_SECRET_PATH .env | cut -d= -f2)
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8000/admin/$SECRET/funnels"
# 200

# 4. API воронок
curl -s "http://localhost:8000/api/$SECRET/funnels" | python3 -m json.tool | head -20
# Должна быть воронка welcome

# 5. Логи всех сервисов — без ошибок
docker compose logs --tail=10 api bot worker beat | grep -iE "error|traceback" || echo "Ошибок нет"
```

4. **Статус Git**:
```bash
git status
# Рабочее дерево чистое

git log --oneline -5
# Последние коммиты с внятными сообщениями
```

5. **Если есть доступ к VPS** — обновление и проверка:
```bash
ssh your_vps "cd /var/www/community-bot && git pull && docker compose up -d --build && docker compose ps"
```

## Важные замечания

- **Не трогай никакую бизнес-логику.** Только `conftest.py`, `docker-compose.yml`, `.env.example`, `README.md`.
- **Не меняй модели, эндпоинты, templates, JS.** Они уже работают (8/8 тестов).
- **Задача 5 требует Git и VPS** — если VPS недоступен, напиши об этом, остальные задачи выполни.
- **После этого промпта** — проект готов к финальному Промпту 5 (настройка nginx, SSL, webhook ЮKassa на боевом домене).

## Что пользователь должен сделать отдельно (вне промпта)

Это я сообщаю Дарье, не Copilot'у:

---

### Для Дарьи — что сделать вручную

**Перед запуском Промпта 5 (деплой) приготовь:**

1. **VPS** — есть, на нём уже что-то было. Если Docker установлен — хорошо. Если нет — поставь:
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo systemctl enable docker
   ```

2. **Домен** для админки — купи короткий поддомен, например `admin.твойсайт.ru`. В DNS-панели добавь A-запись на IP VPS.

3. **ЮKassa аккаунт** — если хочешь принимать оплату:
   - Зарегистрируйся на [yookassa.ru](https://yookassa.ru)
   - Для самозанятых/ИП верификация занимает час
   - Получи `shop_id` и `secret_key` в личном кабинете
   - Если пока нет — пропускаем, бот работает с заглушкой

4. **Реальные ссылки на чаты комьюнити** — создай приватные Telegram-группы для трёх треков (Карьера, Бизнес, Саморазвитие) и общую. Получи invite-ссылки. Они попадут в `.env`:
   ```
   COMMUNITY_CHAT_URL=https://t.me/+...
   TRACK_CAREER_URL=https://t.me/+...
   TRACK_BUSINESS_URL=https://t.me/+...
   TRACK_SELFDEV_URL=https://t.me/+...
   ```

5. **Текст оферты** — либо ссылка на готовую, либо пока заглушка типа `https://твой-лендинг.ru/offer`.

6. **Контакт для поддержки** — свой `@username` без @ в переменной `SUPPORT_USERNAME`.

Когда всё это будет — запускаем Промпт 5 (деплой).
