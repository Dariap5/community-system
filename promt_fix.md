# Промпт 4.1 — Патч: починить админку в браузере

## Роль

Senior full-stack, задача — точечная починка без переделки. Два конкретных бага в shared-слое админки, из-за которых все страницы не работают в браузере.

## Контекст

Промпты 3 и 4 выполнены. HTML и JS файлы существуют, но в браузере админка не функционирует из-за двух багов:

1. **`app/templates/admin/base.html`** — блок, передающий данные из Python в JS (`window.PAGE_DATA`), рендерится как сырая Jinja-разметка вместо JSON-объекта. Нужен фильтр `| tojson` или прямая передача.

2. **`app/static/admin/common.js`** — у API-клиента метод называется `asyncget(...)` (слитно) вместо `async get(...)`. Все страницы падают с `API.get is not a function` при попытке загрузить данные.

Кроме того, в `docker-compose.yml` API-сервис опубликован на порту `8001`, а не `8000`. Это не блокирует работу, но нарушает ожидания из предыдущих промптов — лучше привести к `8000`.

## Задачи

### Задача 1 — Починить common.js

Файл `app/static/admin/common.js`. Найди метод `asyncget` (или любые подобные слитные варианты `asyncpost`, `asyncput`, `asyncpatch`, `asyncdelete`). Исправь на правильный JS-синтаксис с пробелом: `async get`, `async post` и т.д.

Финальный минимально корректный вариант файла:

```javascript
const API = {
    base: window.API_BASE,

    async get(path) {
        const res = await fetch(this.base + path);
        if (!res.ok) throw await this._err(res);
        return res.json();
    },

    async post(path, body) {
        const res = await fetch(this.base + path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: body ? JSON.stringify(body) : undefined,
        });
        if (!res.ok) throw await this._err(res);
        return res.status === 204 ? null : res.json();
    },

    async put(path, body) {
        const res = await fetch(this.base + path, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!res.ok) throw await this._err(res);
        return res.json();
    },

    async patch(path, body) {
        const res = await fetch(this.base + path, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!res.ok) throw await this._err(res);
        return res.json();
    },

    async delete(path) {
        const res = await fetch(this.base + path, { method: 'DELETE' });
        if (!res.ok && res.status !== 204) throw await this._err(res);
    },

    async _err(res) {
        try {
            const data = await res.json();
            return new Error(data.error?.message || `HTTP ${res.status}`);
        } catch {
            return new Error(`HTTP ${res.status}`);
        }
    },
};

function toast(message, type = 'info') {
    const colors = { info: 'bg-blue-500', success: 'bg-green-500', error: 'bg-red-500' };
    const el = document.createElement('div');
    el.className = `fixed top-4 right-4 ${colors[type]} text-white px-4 py-2 rounded shadow-lg z-50`;
    el.textContent = message;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3000);
}

function confirmAction(message) {
    return confirm(message);
}

function escapeHtml(s) {
    return (s || '').toString().replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
```

Обрати внимание:
- Все методы — это shorthand syntax для методов объекта в JS (`async methodName()`), пробел между `async` и именем метода **обязателен**
- Добавлена глобальная `escapeHtml` чтобы все страницы могли её использовать без дублирования кода
- В `post` добавлена обработка body=null (для POST-запросов без тела, например duplicate)

### Задача 2 — Починить base.html

Файл `app/templates/admin/base.html`. Найди блок, который пытается передать данные в JS (скорее всего там есть попытка использовать `window.PAGE_DATA` или похожее). Сейчас он либо рендерится как сырая Jinja-разметка, либо ссылается на переменные, которые не экранированы в JSON.

Правильный подход — передавать через `| tojson` фильтр Jinja. Убедись, что в шаблоне `base.html` внутри `<head>` или в начале `<body>` есть такой блок:

```html
<script>
    window.API_BASE = {{ api_base | tojson }};
    window.ADMIN_SECRET = {{ secret | tojson }};
</script>
```

Фильтр `| tojson` — это Jinja2-фильтр из FastAPI's Jinja2Templates, который корректно сериализует Python-значения в JSON-безопасную JavaScript-строку (с экранированием кавычек, юникода и т.д.).

Проверь, что:
1. Переменные `api_base` и `secret` передаются в контекст из `admin_pages.py` (они уже передаются через функцию `_ctx`)
2. Скрипт `/static/admin/common.js` подключается **после** этого блока, чтобы он увидел `window.API_BASE`
3. Если в файле есть другие блоки с `window.PAGE_DATA` — удалить их или тоже привести к формату `| tojson`

Финальная минимальная структура `base.html`:

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Админка{% endblock %} — Community Bot</title>
    <script src="https://cdn.tailwindcss.com"></script>
    {% block head %}{% endblock %}
</head>
<body class="bg-gray-50 min-h-screen">
    <div class="flex">
        <aside class="w-60 bg-white border-r min-h-screen p-4">
            <h1 class="text-lg font-bold mb-6">Community Bot</h1>
            <nav class="space-y-1">
                <a href="/admin/{{ secret }}/funnels" class="block px-3 py-2 rounded hover:bg-gray-100">Воронки</a>
                <a href="/admin/{{ secret }}/users" class="block px-3 py-2 rounded hover:bg-gray-100">Пользователи</a>
                <a href="/admin/{{ secret }}/analytics" class="block px-3 py-2 rounded hover:bg-gray-100">Аналитика</a>
            </nav>
        </aside>
        <main class="flex-1 p-8 max-w-6xl">
            {% block content %}{% endblock %}
        </main>
    </div>

    <script>
        window.API_BASE = {{ api_base | tojson }};
        window.ADMIN_SECRET = {{ secret | tojson }};
    </script>
    <script src="/static/admin/common.js"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
```

### Задача 3 — Привести порт в docker-compose.yml к 8000

Файл `docker-compose.yml`. Найди сервис `api` и проверь маппинг портов. Должно быть:

```yaml
  api:
    # ... остальные настройки
    ports:
      - "8000:8000"
```

Если сейчас стоит `"8001:8000"` — изменить на `"8000:8000"`. Если есть переменная `API_PORT` с дефолтом `8001` — изменить дефолт на `8000` или убрать переменную и захардкодить.

### Задача 4 — Проверить все страницы в браузере

После применения правок:

1. Пересобрать и перезапустить api:
```bash
docker compose up -d --build api
```

2. Открыть в браузере (подставить свой `ADMIN_SECRET_PATH` из `.env`):

- `http://localhost:8000/admin/<SECRET>/funnels` — должен показать список воронок с seed-воронкой `welcome`
- `http://localhost:8000/admin/<SECRET>/funnels/<funnel_id>` — должен показать список шагов
- `http://localhost:8000/admin/<SECRET>/funnels/<funnel_id>/steps/<step_id>` — должен открыть редактор
- `http://localhost:8000/admin/<SECRET>/users` — должна показать таблицу
- `http://localhost:8000/admin/<SECRET>/analytics` — должна показать цифры

3. Открыть DevTools (F12) → Console. **Не должно быть красных ошибок**. Особенно проверить отсутствие:
   - `API.get is not a function`
   - `Unexpected token`
   - `Uncaught SyntaxError`

4. В Network-вкладке убедиться, что запросы к `/api/<SECRET>/...` возвращают 200.

## Acceptance

**Покажи в ответе:**

1. Diff или полное содержимое `common.js` после правки (чтобы было видно `async get`, а не `asyncget`)
2. Diff или полное содержимое блока `<script>` в `base.html` с `| tojson`
3. Строку из `docker-compose.yml` с портами api-сервиса
4. Скриншоты (или текстовое описание) 4 страниц админки в браузере:
   - Список воронок — должен показать `welcome`
   - Редактор воронки — должен показать 5 шагов
   - Редактор шага — должен показать поля с данными
   - Аналитика — должна показать цифры
5. Вывод DevTools Console — должен быть пустым или содержать только информационные логи, но не ошибки

Если любая из страниц не работает — покажи точную ошибку из консоли, будем разбираться.

## Важные замечания

- Не меняй ничего, кроме `common.js`, `base.html` и `docker-compose.yml`. Если видишь желание "заодно улучшить" что-то ещё — не делай этого. Только точечный патч.
- Если в `base.html` уже есть блок `window.PAGE_DATA` с какой-то логикой — удали его. Вместо этого используй простой блок с `api_base` и `secret`.
- Не трогай страницы `users.js`, `analytics.js`, `funnels_list.js` и т.д. — они используют `API.get`, и после починки `common.js` сами заработают.
- Если при проверке `/admin/<SECRET>/funnels/<uuid>/steps/<uuid>` не находишь UUID шага — открой любой шаг из seed-воронки через dev-tools БД (`SELECT id FROM funnel_steps LIMIT 1;`).