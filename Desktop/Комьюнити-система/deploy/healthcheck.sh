#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="/var/www/community-system-new"
HEALTH_URL="${HEALTH_URL:-http://localhost:8000/health}"

if [[ -f "$PROJECT_DIR/.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$PROJECT_DIR/.env"
    set +a
fi

send_alert() {
    local message="$1"

    if [[ -n "${BOT_TOKEN:-}" && -n "${ALERT_TELEGRAM_CHAT_ID:-}" ]]; then
        curl -fsS "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
            --data-urlencode "chat_id=${ALERT_TELEGRAM_CHAT_ID}" \
            --data-urlencode "text=${message}" >/dev/null || true
    else
        printf '%s\n' "$message" >&2
    fi
}

health_code="$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" || true)"
if [[ "$health_code" != "200" ]]; then
    send_alert "Community Bot API healthcheck failed on ${HOSTNAME:-server}: ${HEALTH_URL} returned ${health_code:-no response}"
fi

if [[ -d "$PROJECT_DIR" ]]; then
    bot_logs="$(cd "$PROJECT_DIR" && docker compose logs --tail=10 bot 2>&1 || true)"
    if echo "$bot_logs" | grep -q "Traceback"; then
        send_alert "Community Bot bot logs contain Traceback on ${HOSTNAME:-server}"
    fi
fi