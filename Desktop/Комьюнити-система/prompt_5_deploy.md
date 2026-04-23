# Промпт 5 — Деплой на VPS и финальные тесты end-to-end

## Роль

Ты DevOps-инженер с опытом деплоя Docker-приложений на VPS, настройки nginx, SSL-сертификатов и webhook-интеграций. Доводишь проект до продакшена, где реальные пользователи могут зайти и купить.

## Контекст

Промпты 1-4 выполнены. Локально работает:
- Бот отвечает на `/start` и `/start welcome`
- Админка доступна на `http://localhost:8000/admin/{secret}/`
- API документирован в Swagger UI
- Webhook от ЮKassa обрабатывается (на localhost — заглушка)

Теперь нужно **развернуть это на продакшене** с настоящим доменом и HTTPS, чтобы:
1. Бот работал 24/7 на VPS
2. Админка была доступна по `https://admin.domain.ru/admin/{secret}/`
3. ЮKassa могла слать webhook на `https://admin.domain.ru/payments/webhook`
4. Связка бот ↔ API ↔ платёжка работала end-to-end

## Предусловия — что должно быть у пользователя

Перед началом работы у вас должно быть:
1. VPS с Ubuntu 22.04+ и установленным Docker + docker-compose
2. Домен с настройкой DNS A-записи на IP вашего VPS (например, `admin.yoursite.ru`)
3. Токен Telegram-бота от BotFather
4. Аккаунт ЮKassa с shop_id и secret_key (или Robokassa)

Если чего-то нет — укажу, что делать, в конце промпта.

## Архитектура деплоя

```
┌─────────────────┐
│ Интернет        │
│ - пользователи  │
│ - Telegram      │
│ - ЮKassa        │
└────────┬────────┘
         │ HTTPS :443
         │
┌────────▼────────┐
│ nginx (на хосте)│
│ - SSL termination
│ - reverse proxy │
└────────┬────────┘
         │ HTTP :8000 (локально)
         │
┌────────▼────────┐
│ Docker stack    │
│ - db            │
│ - redis         │
│ - api (FastAPI) │
│ - bot           │
│ - worker        │
│ - beat          │
└─────────────────┘
```

Nginx на хосте VPS, Docker-стек отдаёт всё на `localhost:8000`.

## Задача 1 — Подготовить VPS

Подключись на VPS по SSH. Выполни проверки и установи недостающее:

```bash
# Проверка Docker
docker --version
docker compose version

# Если нет — установить
curl -fsSL https://get.docker.com | sh
sudo systemctl enable docker

# Проверка nginx
nginx -v

# Если нет — установить
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx

# Открыть порты
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw --force enable
```

## Задача 2 — Выкачать проект и настроить .env

```bash
# Выбрать место
sudo mkdir -p /var/www/community-bot
sudo chown -R $USER:$USER /var/www/community-bot
cd /var/www/community-bot

# Клонировать (замени URL на ваш репо)
git clone https://github.com/YOUR_USER/community-bot.git .

# Скопировать .env
cp .env.example .env
nano .env
```

В `.env` заполнить **настоящие** значения:

```bash
# База
POSTGRES_USER=community_user
POSTGRES_PASSWORD=<длинный случайный пароль>
POSTGRES_DB=community_db
DATABASE_URL=postgresql+asyncpg://community_user:<пароль>@db:5432/community_db

# Redis
REDIS_URL=redis://redis:6379/0

# Бот
BOT_TOKEN=<реальный токен от BotFather>

# Админка — ВАЖНО: сгенерировать длинную случайную строку
ADMIN_SECRET_PATH=<случайная строка 32+ символов>
# Сгенерировать: python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# ЮKassa (если есть)
YOOKASSA_SHOP_ID=<shop_id>
YOOKASSA_SECRET_KEY=<secret_key>

# Ссылки на чаты комьюнити
COMMUNITY_CHAT_URL=https://t.me/+xxxxxxxxx
TRACK_CAREER_URL=https://t.me/+xxxxxxxxx
TRACK_BUSINESS_URL=https://t.me/+xxxxxxxxx
TRACK_SELFDEV_URL=https://t.me/+xxxxxxxxx

# Прочее
SUPPORT_USERNAME=ваш_username
OFFER_URL=https://ваш-сайт/offer
DEFAULT_FUNNEL_KEY=welcome
```

## Задача 3 — Запустить Docker-стек

```bash
cd /var/www/community-bot
docker compose up -d --build
sleep 15

# Проверить статус
docker compose ps
# Все сервисы должны быть Up

# Проверить логи бота — не должно быть traceback
docker compose logs --tail=30 bot
# Ожидаем: "Run polling for bot @xxx"

# Проверить API
curl http://localhost:8000/health
# {"status": "ok"}

# Проверить, что админка отвечает (без домена ещё)
curl -I http://localhost:8000/admin/<ADMIN_SECRET_PATH>/funnels
# 200 OK
```

## Задача 4 — Настроить nginx

Создать конфиг `/etc/nginx/sites-available/community-bot`:

```nginx
server {
    listen 80;
    server_name admin.yoursite.ru;  # ЗАМЕНИТЬ на ваш домен

    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
```

Активировать:

```bash
sudo ln -s /etc/nginx/sites-available/community-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Проверить, что работает по HTTP:

```bash
curl -I http://admin.yoursite.ru/health
# 200 OK
```

## Задача 5 — Получить SSL-сертификат

```bash
sudo certbot --nginx -d admin.yoursite.ru
# Следовать инструкциям: email, согласие, редирект HTTP → HTTPS — да
```

Certbot автоматически обновит nginx-конфиг, добавив SSL. Проверить:

```bash
curl -I https://admin.yoursite.ru/health
# 200 OK
```

Автообновление сертификатов уже настроено через systemd timer. Проверить:

```bash
sudo systemctl status certbot.timer
```

## Задача 6 — Настроить webhook ЮKassa

Войти в личный кабинет ЮKassa → Интеграция → HTTP-уведомления.

Добавить URL: `https://admin.yoursite.ru/payments/webhook`

Включить события:
- `payment.succeeded`
- `payment.waiting_for_capture` (опционально)

ЮKassa тестирует webhook — должен вернуть 200. Если нет — проверить логи api:

```bash
docker compose logs --tail=50 api
```

## Задача 7 — Создать первую рабочую воронку

Открыть админку: `https://admin.yoursite.ru/admin/<ADMIN_SECRET_PATH>/funnels`

Должна быть seed-воронка `welcome` с 5 шагами.

Отредактировать её под реальный сценарий:

1. **Шаг 1 — Приветствие** — текст под ваш продукт
2. **Шаг 2 — Выбор трека** — 3 кнопки на треки
3. **Шаги 3-5** — описание каждого трека и кнопка оплаты

Через админку изменить тексты, сохранить.

## Задача 8 — End-to-end тест

### Тест 1 — Запуск воронки

1. Открыть бот в Telegram
2. Отправить `/start welcome`
3. Должно прийти приветствие + кнопка "Узнать про комьюнити"
4. Нажать → должны прийти 3 кнопки треков
5. Нажать "Карьера" → должен прийти текст про трек + кнопка "Оплатить"

### Тест 2 — Оплата (тестовая)

1. Нажать "Оплатить 2990 ₽"
2. Должна прийти ссылка на ЮKassa
3. Оплатить тестовой картой (ЮKassa даёт номера для теста)
4. Вернуться в Telegram
5. Должны прийти ссылки на комьюнити и трек Карьера

### Тест 3 — Админка видит всё

1. Открыть админку → Пользователи
2. Вы должны быть в списке с тегом `track_career` и воронкой `welcome`
3. Открыть Аналитика
4. Должно быть: 1 новый пользователь, 1 оплата, выручка 2990 ₽, конверсия 100%

## Задача 9 — Настроить автозапуск и мониторинг

### Автозапуск Docker при ребуте VPS

Docker уже настроен на автостарт (`systemctl enable docker`), но убедитесь, что контейнеры с `restart: unless-stopped` в `docker-compose.yml` перезапускаются. В вашем compose это должно быть уже настроено.

Тест:

```bash
sudo reboot
# Подождать 1 минуту, зайти снова
docker compose ps
# Все сервисы должны быть Up без ручного запуска
```

### Простой мониторинг

Создать скрипт `/var/www/community-bot/healthcheck.sh`:

```bash
#!/bin/bash
# Проверяет, что бот и API работают, отправляет алерт в Telegram если нет

HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)

if [ "$HEALTH" != "200" ]; then
    # Послать алерт вам в Telegram через простой curl
    curl -s "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d "chat_id=YOUR_TELEGRAM_ID" \
        -d "text=🚨 API не отвечает на сервере"
fi

BOT_LOGS=$(docker compose logs --tail=10 bot 2>&1)
if echo "$BOT_LOGS" | grep -q "Traceback"; then
    curl -s "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d "chat_id=YOUR_TELEGRAM_ID" \
        -d "text=🚨 Ошибка в боте: $(echo $BOT_LOGS | tail -c 500)"
fi
```

Добавить в cron — каждые 5 минут:

```bash
crontab -e
# Вставить:
*/5 * * * * cd /var/www/community-bot && bash healthcheck.sh
```

## Задача 10 — Добавить резервное копирование БД

Простой скрипт `/var/www/community-bot/backup.sh`:

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/community-bot"
mkdir -p $BACKUP_DIR

cd /var/www/community-bot
docker compose exec -T db pg_dump -U community_user community_db | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Удалить бекапы старше 7 дней
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
```

В cron — ежедневно в 3:00:

```bash
0 3 * * * bash /var/www/community-bot/backup.sh
```

## Задача 11 — Финальный чеклист

Пройтись перед "сдачей":

- [ ] Бот отвечает на `/start` в production
- [ ] Админка открывается по HTTPS
- [ ] SSL-сертификат валидный (зелёный замок в браузере)
- [ ] Webhook ЮKassa настроен и отвечает 200
- [ ] Реальная оплата проходит end-to-end
- [ ] После оплаты пользователь получает ссылки на чаты
- [ ] В админке видны пользователи и аналитика
- [ ] Автозапуск после ребута VPS работает
- [ ] Бекап БД запускается раз в день
- [ ] Healthcheck отправляет алерты при проблемах

## Acceptance criteria

```bash
# 1. Бот жив
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getMe" | python3 -m json.tool

# 2. API отвечает через HTTPS
curl https://admin.yoursite.ru/health

# 3. Админка доступна
curl -I https://admin.yoursite.ru/admin/<SECRET>/funnels
# 200 OK

# 4. Webhook принимает POST
curl -X POST https://admin.yoursite.ru/payments/webhook -H "Content-Type: application/json" -d '{"event":"test"}'
# 200 (в логах должно быть "YooKassa webhook: {event: test}")

# 5. SSL работает
openssl s_client -connect admin.yoursite.ru:443 < /dev/null 2>&1 | grep -E "subject=|issuer="

# 6. Все контейнеры Up
docker compose ps

# 7. Реальный Telegram-тест
# Зайти в бота, пройти всю воронку до "Оплатить" (можно не платить реально)
```

**Покажи:**
1. Скриншот админки через HTTPS (`https://admin.yoursite.ru/admin/.../funnels`)
2. Скриншот бота в Telegram с пройденной воронкой
3. Вывод `docker compose ps` с работающими сервисами
4. Ответ certbot про сертификат (action date)

## Если нет чего-то из предусловий

### Нет VPS

Рекомендую **Hetzner** (Германия, 3-5€/мес). Зарегистрировать, создать CX22, Ubuntu 24.04. Через 5 минут — готовый VPS.

Альтернативы в РФ: **TimeWeb**, **Reg.ru** — но могут быть проблемы с доступом к Telegram API (как в прошлый раз). Hetzner решает это.

### Нет домена

Купить на **nic.ru** или **reg.ru** за 200-1000 руб/год. После покупки в панели DNS добавить A-запись:

```
Тип: A
Имя: admin (или @ для корня)
Значение: <IP вашего VPS>
TTL: 300
```

Ждать 5-30 минут для распространения.

### Нет ЮKassa

Зарегистрироваться на [yookassa.ru](https://yookassa.ru), пройти верификацию (займёт 1-3 дня для юр.лиц, быстрее для самозанятых/ИП). В MVP можно запускать без платёжки — заглушка из Промпта 2 работает, заменится автоматически когда появятся ключи.

### Нет опыта с nginx/SSL

Сделать по шагам выше строго, без пропусков. Если что-то не получается — покажи вывод команд, разберёмся.

## Важные замечания

- **Секреты** — никогда не коммить `.env` в git. Убедиться, что он в `.gitignore`.
- **ADMIN_SECRET_PATH** должен быть действительно случайным и длинным. Никому не давать.
- **BOT_TOKEN** тоже секрет. Если утечёт — BotFather → `/revoke`.
- **Обновления проекта:** когда будут изменения в коде, делать:
  ```bash
  cd /var/www/community-bot
  git pull
  docker compose up -d --build
  ```
- **Ошибки в проде** — всегда сначала `docker compose logs --tail=100 <service>`, потом искать причину.

После выполнения всех acceptance — **MVP готов к продакшену**. Принимай заказы.
