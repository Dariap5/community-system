# Production deploy

This repository already has the runtime pieces needed for VPS deployment:

- FastAPI health endpoint: [`app/api/main.py`](../app/api/main.py)
- Admin pages under `/admin/{secret}`: [`app/api/routes/admin_pages.py`](../app/api/routes/admin_pages.py)
- Payment webhook: [`app/api/routes/payments.py`](../app/api/routes/payments.py)
- Docker stack: [`docker-compose.yml`](../docker-compose.yml)

The missing pieces for production are the host-level nginx config, SSL via certbot, and a couple of operational scripts. Those are included in `deploy/`.

## 1. Push the code

From your local machine:

```bash
git status
git add docker-compose.yml .env.example README.md deploy docs
git commit -m "Add production deploy assets"
git push origin main
```

## 2. Prepare the VPS

```bash
ssh user@your-vps-ip
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
curl -fsSL https://get.docker.com | sh
sudo systemctl enable --now docker
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw --force enable
```

## 3. Clone into a separate folder

```bash
sudo mkdir -p /var/www/community-system-new
sudo chown -R "$USER:$USER" /var/www/community-system-new
cd /var/www/community-system-new
git clone https://github.com/YOUR_USER/community-system.git .
cp .env.example .env
nano .env
```

Fill in the real values in `.env`:

```bash
POSTGRES_USER=community_user
POSTGRES_PASSWORD=<long-random-password>
POSTGRES_DB=community_db
DATABASE_URL=postgresql+asyncpg://community_user:<password>@db:5432/community_db
REDIS_URL=redis://redis:6379/0
BOT_TOKEN=<telegram-bot-token>
ADMIN_SECRET_PATH=<random-32+ char secret>
YOOKASSA_SHOP_ID=<shop_id>
YOOKASSA_SECRET_KEY=<secret_key>
COMMUNITY_CHAT_URL=https://t.me/+xxxxxxxxx
TRACK_CAREER_URL=https://t.me/+xxxxxxxxx
TRACK_BUSINESS_URL=https://t.me/+xxxxxxxxx
TRACK_SELFDEV_URL=https://t.me/+xxxxxxxxx
SUPPORT_USERNAME=your_username
OFFER_URL=https://your-domain/offer
DEFAULT_FUNNEL_KEY=welcome
ALERT_TELEGRAM_CHAT_ID=<your-telegram-id>
```

## 4. Start the stack

```bash
docker compose up -d --build
docker compose ps
sleep 15
curl http://localhost:8000/health
curl -I http://localhost:8000/admin/<ADMIN_SECRET_PATH>/funnels
```

The API port is bound to `127.0.0.1:8000`, so nginx can proxy to it without exposing Docker directly to the internet.

## 5. Configure nginx

Copy the sample config from [`deploy/nginx/community-bot.conf`](../deploy/nginx/community-bot.conf) to `/etc/nginx/sites-available/community-bot`, replace `admin.yoursite.ru`, and enable it:

```bash
sudo ln -s /etc/nginx/sites-available/community-bot /etc/nginx/sites-enabled/community-bot
sudo nginx -t
sudo systemctl reload nginx
curl -I http://admin.yoursite.ru/health
```

## 6. Enable SSL

```bash
sudo certbot --nginx -d admin.yoursite.ru
curl -I https://admin.yoursite.ru/health
sudo systemctl status certbot.timer
```

## 7. Configure the YooKassa webhook

Add this URL in YooKassa:

```text
https://admin.yoursite.ru/payments/webhook
```

Recommended events:

- `payment.succeeded`
- `payment.waiting_for_capture`

## 8. Monitoring and backups

Healthcheck script: [`deploy/healthcheck.sh`](../deploy/healthcheck.sh)

Backup script: [`deploy/backup.sh`](../deploy/backup.sh)

Example cron entries:

```bash
*/5 * * * * cd /var/www/community-system-new && bash deploy/healthcheck.sh
0 3 * * * cd /var/www/community-system-new && bash deploy/backup.sh
```

## 9. Verify end to end

```bash
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getMe"
curl https://admin.yoursite.ru/health
curl -I https://admin.yoursite.ru/admin/<ADMIN_SECRET_PATH>/funnels
curl -X POST https://admin.yoursite.ru/payments/webhook -H "Content-Type: application/json" -d '{"event":"test"}'
docker compose ps
```

## 10. If something is broken

Start with logs:

```bash
docker compose logs --tail=100 api
docker compose logs --tail=100 bot
docker compose logs --tail=100 worker
```

If Docker is not running on macOS/Linux, start Docker Desktop or the Docker service first. If port `8000` is occupied, stop the old stack before starting the new one.