# Community Bot

Минимальный фундамент для Telegram-бота комьюнити.

## Быстрый старт

1. Скопируй `.env.example` в `.env` и заполни `BOT_TOKEN` и `ADMIN_SECRET_PATH`.
2. Подними инфраструктуру: `docker compose up -d db redis`.
3. Прогони миграции и seed: `docker compose up init-db`.
4. Для локальных тестов установи dev-зависимости: `pip install -e ".[dev]"`.

## Production deploy

Для VPS, nginx, SSL, webhook и финальных проверок см. [docs/deployment.md](docs/deployment.md).

Готовые артефакты лежат здесь:

- [deploy/nginx/community-bot.conf](deploy/nginx/community-bot.conf)
- [deploy/healthcheck.sh](deploy/healthcheck.sh)
- [deploy/backup.sh](deploy/backup.sh)