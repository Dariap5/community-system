# Промпт 4 — HTML-админка: воронки, редактор шага, пользователи, аналитика

## Роль

Ты full-stack разработчик. Пишешь простую HTML-админку на Jinja2 + vanilla JavaScript + TailwindCSS (через CDN). Без React, Vue, сборщиков. Цель — работающий интерфейс, не эстетичный шедевр.

## Контекст

Промпты 1, 2, 3 выполнены. БД работает, бот работает, REST API готов на `/api/{secret}/...`. Теперь нужна HTML-админка, которая использует этот API.

Доступ — по секретному пути, без пароля. URL админки: `https://ваш-домен/admin/{ADMIN_SECRET_PATH}/`.

## Архитектурные принципы

### 1. Server-side rendering через Jinja2

Каждая страница — отдельный HTML-шаблон. Никакого SPA, никакой client-side маршрутизации.

### 2. JavaScript — только для интерактивности

JS нужен только для:
- AJAX-запросов к API (fetch)
- Drag & drop шагов
- Динамическое добавление/удаление блоков в редакторе шага

Нет state management, нет компонентов.

### 3. TailwindCSS через CDN

В `<head>` подключаем Tailwind CDN. Никакого билда, никаких PostCSS. Для MVP достаточно.

### 4. Один JS-файл на страницу

`funnel_editor.js`, `step_editor.js` — каждый файл независим, грузится только на своей странице.

## Структура (добавляется к существующему проекту)

```
app/
├── api/
│   ├── routes/
│   │   └── admin_pages.py        # НОВОЕ — HTML-страницы
│   └── main.py                   # ОБНОВИТЬ — подключить admin_pages
├── templates/                     # НОВОЕ
│   └── admin/
│       ├── base.html
│       ├── funnels_list.html
│       ├── funnel_edit.html
│       ├── step_edit.html
│       ├── users.html
│       └── analytics.html
└── static/                        # НОВОЕ
    └── admin/
        ├── common.js              # общие функции (API-клиент)
        ├── funnel_editor.js       # drag&drop шагов, создание/удаление
        └── step_editor.js         # добавление блоков, кнопок
```

## Задача 1 — Обновить app/api/main.py

Добавить:

```python
from fastapi.staticfiles import StaticFiles
from app.api.routes import admin_pages

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(admin_pages.router)
```

## Задача 2 — app/api/routes/admin_pages.py

```python
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, verify_secret
from app.db.models import Funnel, FunnelStep
from app.config import settings

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/admin/{secret}", dependencies=[Depends(verify_secret)])


def _ctx(request: Request, secret: str, **extra):
    """Базовый контекст шаблона."""
    return {
        "request": request,
        "secret": secret,
        "api_base": f"/api/{secret}",
        **extra,
    }


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, secret: str):
    return RedirectResponse(url=f"/admin/{secret}/funnels")


@router.get("/funnels", response_class=HTMLResponse)
async def funnels_list(request: Request, secret: str):
    return templates.TemplateResponse("admin/funnels_list.html", _ctx(request, secret))


@router.get("/funnels/{funnel_id}", response_class=HTMLResponse)
async def funnel_edit(request: Request, secret: str, funnel_id: UUID, db: AsyncSession = Depends(get_db)):
    funnel = await db.get(Funnel, funnel_id)
    if not funnel:
        raise HTTPException(404)
    return templates.TemplateResponse("admin/funnel_edit.html", _ctx(
        request, secret, funnel_id=funnel_id, funnel_name=funnel.name,
    ))


@router.get("/funnels/{funnel_id}/steps/{step_id}", response_class=HTMLResponse)
async def step_edit(request: Request, secret: str, funnel_id: UUID, step_id: UUID, db: AsyncSession = Depends(get_db)):
    step = await db.get(FunnelStep, step_id)
    if not step or step.funnel_id != funnel_id:
        raise HTTPException(404)
    return templates.TemplateResponse("admin/step_edit.html", _ctx(
        request, secret, funnel_id=funnel_id, step_id=step_id, step_name=step.name,
    ))


@router.get("/users", response_class=HTMLResponse)
async def users_list(request: Request, secret: str):
    return templates.TemplateResponse("admin/users.html", _ctx(request, secret))


@router.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request, secret: str):
    return templates.TemplateResponse("admin/analytics.html", _ctx(request, secret))
```

## Задача 3 — app/templates/admin/base.html

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
        <!-- Sidebar -->
        <aside class="w-60 bg-white border-r min-h-screen p-4">
            <h1 class="text-lg font-bold mb-6">Community Bot</h1>
            <nav class="space-y-1">
                <a href="/admin/{{ secret }}/funnels" class="block px-3 py-2 rounded hover:bg-gray-100">Воронки</a>
                <a href="/admin/{{ secret }}/users" class="block px-3 py-2 rounded hover:bg-gray-100">Пользователи</a>
                <a href="/admin/{{ secret }}/analytics" class="block px-3 py-2 rounded hover:bg-gray-100">Аналитика</a>
            </nav>
        </aside>

        <!-- Main -->
        <main class="flex-1 p-8 max-w-6xl">
            {% block content %}{% endblock %}
        </main>
    </div>

    <script>
        window.API_BASE = "{{ api_base }}";
    </script>
    <script src="/static/admin/common.js"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
```

## Задача 4 — app/static/admin/common.js

```javascript
// Универсальный API-клиент
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
            body: JSON.stringify(body),
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

// Toast-уведомления
function toast(message, type = 'info') {
    const colors = { info: 'bg-blue-500', success: 'bg-green-500', error: 'bg-red-500' };
    const el = document.createElement('div');
    el.className = `fixed top-4 right-4 ${colors[type]} text-white px-4 py-2 rounded shadow-lg z-50`;
    el.textContent = message;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3000);
}

// Confirm
function confirmAction(message) {
    return confirm(message);
}
```

## Задача 5 — app/templates/admin/funnels_list.html

```html
{% extends "admin/base.html" %}
{% block title %}Воронки{% endblock %}
{% block content %}
<div class="flex items-center justify-between mb-6">
    <h2 class="text-2xl font-bold">Воронки</h2>
    <button id="btn-create" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded">+ Создать воронку</button>
</div>

<div id="funnels-list" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"></div>

<!-- Модалка создания -->
<div id="create-modal" class="hidden fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-40">
    <div class="bg-white p-6 rounded-lg w-full max-w-md">
        <h3 class="text-lg font-bold mb-4">Создать воронку</h3>
        <label class="block mb-3">
            <span class="text-sm">Название</span>
            <input id="new-name" class="mt-1 w-full border rounded px-3 py-2" placeholder="Моя воронка">
        </label>
        <label class="block mb-4">
            <span class="text-sm">Ключ запуска (для deeplink)</span>
            <input id="new-key" class="mt-1 w-full border rounded px-3 py-2" placeholder="my_funnel" pattern="[a-z0-9_]+">
            <span class="text-xs text-gray-500">Только латиница, цифры, подчёркивания</span>
        </label>
        <div class="flex gap-2 justify-end">
            <button id="cancel-create" class="px-4 py-2 border rounded">Отмена</button>
            <button id="confirm-create" class="bg-blue-600 text-white px-4 py-2 rounded">Создать</button>
        </div>
    </div>
</div>
{% endblock %}
{% block scripts %}
<script>
const SECRET = "{{ secret }}";

async function loadFunnels() {
    const funnels = await API.get('/funnels');
    const container = document.getElementById('funnels-list');
    container.innerHTML = '';

    if (!funnels.length) {
        container.innerHTML = '<p class="text-gray-500 col-span-full">Воронок пока нет. Создайте первую.</p>';
        return;
    }

    funnels.forEach(f => {
        const card = document.createElement('div');
        card.className = 'bg-white rounded-lg shadow p-4 border';
        card.innerHTML = `
            <div class="flex items-start justify-between mb-2">
                <h3 class="font-bold text-lg">${escapeHtml(f.name)}</h3>
                <label class="flex items-center cursor-pointer">
                    <input type="checkbox" ${f.is_active ? 'checked' : ''} data-id="${f.id}" class="toggle-active">
                </label>
            </div>
            <div class="text-sm text-gray-500 mb-3">
                ${f.entry_key ? `<code>/start ${f.entry_key}</code>` : '<i>без deeplink</i>'}
            </div>
            <div class="text-xs text-gray-600 mb-4">
                ${f.steps_count} шагов · ${f.active_users_count} активных пользователей
            </div>
            <div class="flex gap-2 text-sm">
                <a href="/admin/${SECRET}/funnels/${f.id}" class="flex-1 text-center bg-blue-50 hover:bg-blue-100 text-blue-700 py-2 rounded">Открыть</a>
                <button class="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded duplicate-btn" data-id="${f.id}">Дубл.</button>
                <button class="px-3 py-2 bg-red-50 hover:bg-red-100 text-red-700 rounded archive-btn" data-id="${f.id}">Архив</button>
            </div>
        `;
        container.appendChild(card);
    });

    // Handlers
    container.querySelectorAll('.toggle-active').forEach(el => {
        el.addEventListener('change', async (e) => {
            const id = e.target.dataset.id;
            try {
                await API.patch(`/funnels/${id}`, { is_active: e.target.checked });
                toast('Обновлено', 'success');
            } catch (err) {
                toast(err.message, 'error');
                e.target.checked = !e.target.checked;
            }
        });
    });

    container.querySelectorAll('.duplicate-btn').forEach(el => {
        el.addEventListener('click', async (e) => {
            const id = e.target.dataset.id;
            try {
                await API.post(`/funnels/${id}/duplicate`);
                toast('Воронка скопирована', 'success');
                loadFunnels();
            } catch (err) { toast(err.message, 'error'); }
        });
    });

    container.querySelectorAll('.archive-btn').forEach(el => {
        el.addEventListener('click', async (e) => {
            if (!confirmAction('Архивировать воронку? Её можно будет восстановить.')) return;
            const id = e.target.dataset.id;
            try {
                await API.delete(`/funnels/${id}`);
                toast('Архивировано', 'success');
                loadFunnels();
            } catch (err) { toast(err.message, 'error'); }
        });
    });
}

function escapeHtml(s) {
    return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// Create modal
document.getElementById('btn-create').addEventListener('click', () => {
    document.getElementById('create-modal').classList.remove('hidden');
});
document.getElementById('cancel-create').addEventListener('click', () => {
    document.getElementById('create-modal').classList.add('hidden');
});
document.getElementById('confirm-create').addEventListener('click', async () => {
    const name = document.getElementById('new-name').value.trim();
    const key = document.getElementById('new-key').value.trim();
    if (!name) { toast('Введите название', 'error'); return; }
    try {
        const f = await API.post('/funnels', { name, entry_key: key || null });
        toast('Создано', 'success');
        document.getElementById('create-modal').classList.add('hidden');
        document.getElementById('new-name').value = '';
        document.getElementById('new-key').value = '';
        window.location.href = `/admin/${SECRET}/funnels/${f.id}`;
    } catch (err) {
        toast(err.message, 'error');
    }
});

loadFunnels();
</script>
{% endblock %}
```

## Задача 6 — app/templates/admin/funnel_edit.html

```html
{% extends "admin/base.html" %}
{% block title %}{{ funnel_name }}{% endblock %}
{% block content %}
<div class="mb-4">
    <a href="/admin/{{ secret }}/funnels" class="text-sm text-gray-500 hover:underline">← К списку воронок</a>
</div>

<div class="flex items-center justify-between mb-6">
    <h2 id="funnel-title" class="text-2xl font-bold">{{ funnel_name }}</h2>
    <button id="btn-add-step" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded">+ Добавить шаг</button>
</div>

<!-- Настройки воронки -->
<details class="mb-6 bg-white rounded-lg shadow">
    <summary class="p-4 cursor-pointer font-medium">⚙ Настройки воронки</summary>
    <div class="p-4 pt-0 space-y-3">
        <label class="block">
            <span class="text-sm text-gray-600">Название</span>
            <input id="funnel-name" class="mt-1 w-full border rounded px-3 py-2">
        </label>
        <label class="block">
            <span class="text-sm text-gray-600">Ключ запуска (entry_key)</span>
            <input id="funnel-key" class="mt-1 w-full border rounded px-3 py-2" pattern="[a-z0-9_]+">
            <div id="deeplink-preview" class="text-xs text-gray-500 mt-1"></div>
        </label>
        <label class="block">
            <span class="text-sm text-gray-600">При повторном входе из другой воронки</span>
            <select id="funnel-behavior" class="mt-1 w-full border rounded px-3 py-2">
                <option value="deny">Не перезапускать (оставить в текущей)</option>
                <option value="allow">Запустить параллельно</option>
            </select>
        </label>
        <button id="btn-save-funnel" class="bg-green-600 text-white px-4 py-2 rounded">Сохранить настройки</button>
    </div>
</details>

<!-- Список шагов -->
<div id="steps-list" class="space-y-2"></div>

<!-- Модалка создания шага -->
<div id="add-step-modal" class="hidden fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-40">
    <div class="bg-white p-6 rounded-lg w-full max-w-md">
        <h3 class="text-lg font-bold mb-4">Новый шаг</h3>
        <label class="block mb-3">
            <span class="text-sm">Название</span>
            <input id="step-name" class="mt-1 w-full border rounded px-3 py-2" placeholder="Приветствие">
        </label>
        <label class="block mb-4">
            <span class="text-sm">Технический ключ</span>
            <input id="step-key" class="mt-1 w-full border rounded px-3 py-2" pattern="[a-z0-9_]+" placeholder="welcome">
        </label>
        <div class="flex gap-2 justify-end">
            <button id="cancel-add-step" class="px-4 py-2 border rounded">Отмена</button>
            <button id="confirm-add-step" class="bg-blue-600 text-white px-4 py-2 rounded">Создать</button>
        </div>
    </div>
</div>
{% endblock %}
{% block scripts %}
<script>
const SECRET = "{{ secret }}";
const FUNNEL_ID = "{{ funnel_id }}";

async function loadFunnel() {
    const funnel = await API.get(`/funnels/${FUNNEL_ID}`);
    document.getElementById('funnel-name').value = funnel.name;
    document.getElementById('funnel-key').value = funnel.entry_key || '';
    document.getElementById('funnel-behavior').value = funnel.cross_entry_behavior;
    updateDeeplink(funnel.entry_key);

    const list = document.getElementById('steps-list');
    list.innerHTML = '';

    if (!funnel.steps.length) {
        list.innerHTML = '<div class="bg-white rounded p-6 text-center text-gray-500">Шагов пока нет. Добавьте первый.</div>';
        return;
    }

    funnel.steps.forEach((step, i) => {
        const card = document.createElement('div');
        card.className = 'bg-white rounded-lg shadow p-4 border cursor-move';
        card.draggable = true;
        card.dataset.id = step.id;
        card.innerHTML = `
            <div class="flex items-start gap-3">
                <div class="text-gray-400 text-xl">⋮⋮</div>
                <div class="flex-1">
                    <div class="flex items-center gap-2 mb-1">
                        <span class="font-medium">${i + 1}. ${escapeHtml(step.name)}</span>
                        <code class="text-xs text-gray-500 bg-gray-100 px-1">${escapeHtml(step.step_key)}</code>
                        ${step.is_active ? '' : '<span class="text-xs text-gray-500">(выключен)</span>'}
                    </div>
                    <div class="text-sm text-gray-600">${escapeHtml(step.first_message_preview || '—')}</div>
                </div>
                <div class="flex gap-2">
                    <a href="/admin/${SECRET}/funnels/${FUNNEL_ID}/steps/${step.id}" class="bg-blue-50 hover:bg-blue-100 text-blue-700 px-3 py-1 rounded text-sm">Редактировать</a>
                    <button class="bg-red-50 hover:bg-red-100 text-red-700 px-3 py-1 rounded text-sm delete-step" data-id="${step.id}">Удалить</button>
                </div>
            </div>
        `;
        list.appendChild(card);
    });

    attachDragDrop(list);
    attachDeleteHandlers(list);
}

function updateDeeplink(key) {
    const preview = document.getElementById('deeplink-preview');
    if (key) preview.innerHTML = `Ссылка: <code>/start ${key}</code> <button onclick="navigator.clipboard.writeText('/start ${key}').then(()=>toast('Скопировано','success'))" class="ml-2 text-blue-600">копировать</button>`;
    else preview.textContent = '';
}

document.getElementById('funnel-key').addEventListener('input', (e) => updateDeeplink(e.target.value));

document.getElementById('btn-save-funnel').addEventListener('click', async () => {
    try {
        await API.patch(`/funnels/${FUNNEL_ID}`, {
            name: document.getElementById('funnel-name').value,
            entry_key: document.getElementById('funnel-key').value || null,
            cross_entry_behavior: document.getElementById('funnel-behavior').value,
        });
        toast('Сохранено', 'success');
    } catch (err) { toast(err.message, 'error'); }
});

// Add step
document.getElementById('btn-add-step').addEventListener('click', () => {
    document.getElementById('add-step-modal').classList.remove('hidden');
});
document.getElementById('cancel-add-step').addEventListener('click', () => {
    document.getElementById('add-step-modal').classList.add('hidden');
});
document.getElementById('confirm-add-step').addEventListener('click', async () => {
    const name = document.getElementById('step-name').value.trim();
    const key = document.getElementById('step-key').value.trim();
    if (!name || !key) { toast('Заполните поля', 'error'); return; }
    try {
        const s = await API.post(`/funnels/${FUNNEL_ID}/steps`, { name, step_key: key, config: {} });
        document.getElementById('add-step-modal').classList.add('hidden');
        window.location.href = `/admin/${SECRET}/funnels/${FUNNEL_ID}/steps/${s.id}`;
    } catch (err) { toast(err.message, 'error'); }
});

function attachDeleteHandlers(container) {
    container.querySelectorAll('.delete-step').forEach(el => {
        el.addEventListener('click', async (e) => {
            e.stopPropagation();
            if (!confirmAction('Удалить шаг?')) return;
            try {
                await API.delete(`/funnels/${FUNNEL_ID}/steps/${e.target.dataset.id}`);
                toast('Удалено', 'success');
                loadFunnel();
            } catch (err) { toast(err.message, 'error'); }
        });
    });
}

function attachDragDrop(container) {
    let dragged = null;
    container.addEventListener('dragstart', e => {
        if (e.target.classList.contains('bg-white')) {
            dragged = e.target;
            e.target.style.opacity = '0.5';
        }
    });
    container.addEventListener('dragend', async e => {
        if (dragged) {
            dragged.style.opacity = '';
            dragged = null;
            // Отправить новый порядок
            const ids = Array.from(container.querySelectorAll('[data-id]')).map(el => el.dataset.id);
            try {
                await API.post(`/funnels/${FUNNEL_ID}/steps/reorder`, { step_ids_in_order: ids });
                toast('Порядок обновлён', 'success');
                loadFunnel();
            } catch (err) { toast(err.message, 'error'); }
        }
    });
    container.addEventListener('dragover', e => {
        e.preventDefault();
        const after = getAfter(container, e.clientY);
        if (!after) container.appendChild(dragged);
        else container.insertBefore(dragged, after);
    });
}

function getAfter(container, y) {
    const items = [...container.querySelectorAll('[data-id]:not(.dragging)')];
    return items.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) return { offset, element: child };
        return closest;
    }, { offset: -Infinity }).element;
}

function escapeHtml(s) {
    return (s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

loadFunnel();
</script>
{% endblock %}
```

## Задача 7 — app/templates/admin/step_edit.html

**Это самый большой шаблон.** Редактор шага с возможностью:
- Менять название, ключ, задержку, wait_for_payment, теги после шага, next_step
- Добавлять сообщения (текст/фото/документ) с задержкой между ними
- Менять порядок сообщений (кнопки вверх/вниз, без drag&drop для простоты)
- Добавлять блок кнопок с 4 типами действий

Полный HTML + JS (длинный, ~400 строк):

```html
{% extends "admin/base.html" %}
{% block title %}Редактор шага{% endblock %}
{% block content %}
<div class="mb-4 flex items-center justify-between">
    <div>
        <a href="/admin/{{ secret }}/funnels/{{ funnel_id }}" class="text-sm text-gray-500 hover:underline">← К шагам воронки</a>
    </div>
    <button id="btn-save" class="bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded font-medium">Сохранить</button>
</div>

<h2 class="text-2xl font-bold mb-6">{{ step_name }}</h2>

<div class="bg-white rounded-lg shadow p-6 mb-6 space-y-4">
    <div class="grid grid-cols-2 gap-4">
        <label>
            <span class="text-sm text-gray-600">Название</span>
            <input id="name" class="mt-1 w-full border rounded px-3 py-2">
        </label>
        <label>
            <span class="text-sm text-gray-600">Ключ (step_key)</span>
            <input id="step_key" class="mt-1 w-full border rounded px-3 py-2" pattern="[a-z0-9_]+">
        </label>
    </div>
    <label class="flex items-center gap-2">
        <input type="checkbox" id="is_active" class="h-4 w-4">
        <span>Шаг активен</span>
    </label>
    <div class="grid grid-cols-2 gap-4">
        <label>
            <span class="text-sm text-gray-600">Задержка перед шагом (секунды)</span>
            <input id="delay_before" type="number" min="0" class="mt-1 w-full border rounded px-3 py-2">
        </label>
        <label class="flex items-end gap-2">
            <input type="checkbox" id="wait_for_payment" class="h-4 w-4">
            <span>Ждать оплату</span>
        </label>
    </div>
</div>

<!-- Сообщения -->
<div class="mb-6">
    <h3 class="font-bold mb-3">Сообщения</h3>
    <div id="messages-list" class="space-y-2"></div>
    <div class="mt-3 flex gap-2">
        <button class="add-msg bg-gray-100 hover:bg-gray-200 px-3 py-2 rounded text-sm" data-type="text">+ Текст</button>
        <button class="add-msg bg-gray-100 hover:bg-gray-200 px-3 py-2 rounded text-sm" data-type="photo">+ Фото</button>
        <button class="add-msg bg-gray-100 hover:bg-gray-200 px-3 py-2 rounded text-sm" data-type="document">+ Документ</button>
    </div>
</div>

<!-- Кнопки -->
<div class="mb-6">
    <h3 class="font-bold mb-3">Кнопки (inline)</h3>
    <div id="buttons-list" class="space-y-2"></div>
    <button id="add-btn" class="mt-3 bg-gray-100 hover:bg-gray-200 px-3 py-2 rounded text-sm">+ Добавить кнопку</button>
</div>

<!-- После шага -->
<details class="bg-white rounded-lg shadow p-6">
    <summary class="cursor-pointer font-medium">После шага</summary>
    <div class="mt-4 space-y-3">
        <label class="block">
            <span class="text-sm text-gray-600">Добавить теги (через запятую)</span>
            <input id="add_tags" class="mt-1 w-full border rounded px-3 py-2">
        </label>
        <label class="block">
            <span class="text-sm text-gray-600">Следующий шаг</span>
            <select id="next_step" class="mt-1 w-full border rounded px-3 py-2">
                <option value="auto">Автоматически (следующий по порядку)</option>
                <option value="end">Конец воронки</option>
            </select>
        </label>
    </div>
</details>
{% endblock %}
{% block scripts %}
<script>
const FUNNEL_ID = "{{ funnel_id }}";
const STEP_ID = "{{ step_id }}";

let STATE = {
    messages: [],  // [{id, type, content, file_id, caption, delay_after}]
    buttons: [],   // [{id, text, action_type, action_value}]
};

function uuid() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
        const r = Math.random() * 16 | 0;
        return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });
}

async function load() {
    const step = await API.get(`/funnels/${FUNNEL_ID}/steps/${STEP_ID}`);
    document.getElementById('name').value = step.name;
    document.getElementById('step_key').value = step.step_key;
    document.getElementById('is_active').checked = step.is_active;
    document.getElementById('delay_before').value = step.config.delay_before_seconds || 0;
    document.getElementById('wait_for_payment').checked = step.config.wait_for_payment || false;
    document.getElementById('add_tags').value = (step.config.add_tags_after || []).join(', ');

    // Парсим blocks в STATE
    STATE.messages = [];
    STATE.buttons = [];
    for (const block of (step.config.blocks || [])) {
        if (block.type === 'buttons') {
            for (const btn of block.buttons) {
                STATE.buttons.push({
                    id: btn.id || uuid(),
                    text: btn.text,
                    action_type: btn.action.type,
                    action_value: btn.action.value,
                });
            }
        } else {
            STATE.messages.push({
                id: block.id || uuid(),
                type: block.type,
                content: block.content || '',
                file_id: block.file_id || '',
                caption: block.caption || '',
                delay_after: block.delay_after || 0,
            });
        }
    }

    // Загрузить список шагов для селектора next_step
    const allSteps = await API.get(`/funnels/${FUNNEL_ID}/steps`);
    const selector = document.getElementById('next_step');
    for (const s of allSteps) {
        if (s.id === STEP_ID) continue;
        const opt = document.createElement('option');
        opt.value = s.step_key;
        opt.textContent = `→ ${s.name} (${s.step_key})`;
        selector.appendChild(opt);
    }
    selector.value = step.config.next_step || 'auto';

    renderMessages();
    renderButtons();
}

function renderMessages() {
    const list = document.getElementById('messages-list');
    list.innerHTML = '';
    STATE.messages.forEach((msg, i) => {
        const card = document.createElement('div');
        card.className = 'bg-white rounded-lg shadow p-4';
        let bodyHtml = '';
        if (msg.type === 'text') {
            bodyHtml = `<textarea class="w-full border rounded p-2" rows="3" data-field="content" data-idx="${i}">${escapeHtml(msg.content)}</textarea>`;
        } else {
            bodyHtml = `
                <input placeholder="Telegram file_id" value="${escapeHtml(msg.file_id)}" class="w-full border rounded p-2 mb-2" data-field="file_id" data-idx="${i}">
                <input placeholder="Подпись (опционально)" value="${escapeHtml(msg.caption)}" class="w-full border rounded p-2" data-field="caption" data-idx="${i}">
            `;
        }
        card.innerHTML = `
            <div class="flex items-center justify-between mb-2">
                <span class="font-medium">${i + 1}. ${msg.type === 'text' ? '📝 Текст' : msg.type === 'photo' ? '🖼 Фото' : '📎 Документ'}</span>
                <div class="flex gap-1">
                    <button class="px-2 py-1 border rounded text-sm move-up" data-idx="${i}" ${i === 0 ? 'disabled' : ''}>↑</button>
                    <button class="px-2 py-1 border rounded text-sm move-down" data-idx="${i}" ${i === STATE.messages.length - 1 ? 'disabled' : ''}>↓</button>
                    <button class="px-2 py-1 border rounded text-sm text-red-600 delete-msg" data-idx="${i}">×</button>
                </div>
            </div>
            ${bodyHtml}
            <label class="block mt-2 text-sm">
                Задержка после: <input type="number" min="0" value="${msg.delay_after}" class="w-20 border rounded p-1" data-field="delay_after" data-idx="${i}"> сек
            </label>
        `;
        list.appendChild(card);
    });

    list.querySelectorAll('[data-field]').forEach(el => {
        el.addEventListener('input', (e) => {
            const i = parseInt(e.target.dataset.idx);
            const field = e.target.dataset.field;
            STATE.messages[i][field] = field === 'delay_after' ? parseInt(e.target.value) : e.target.value;
        });
    });
    list.querySelectorAll('.delete-msg').forEach(el => {
        el.addEventListener('click', (e) => {
            const i = parseInt(e.target.dataset.idx);
            STATE.messages.splice(i, 1);
            renderMessages();
        });
    });
    list.querySelectorAll('.move-up').forEach(el => {
        el.addEventListener('click', (e) => {
            const i = parseInt(e.target.dataset.idx);
            if (i > 0) {
                [STATE.messages[i-1], STATE.messages[i]] = [STATE.messages[i], STATE.messages[i-1]];
                renderMessages();
            }
        });
    });
    list.querySelectorAll('.move-down').forEach(el => {
        el.addEventListener('click', (e) => {
            const i = parseInt(e.target.dataset.idx);
            if (i < STATE.messages.length - 1) {
                [STATE.messages[i], STATE.messages[i+1]] = [STATE.messages[i+1], STATE.messages[i]];
                renderMessages();
            }
        });
    });
}

function renderButtons() {
    const list = document.getElementById('buttons-list');
    list.innerHTML = '';
    STATE.buttons.forEach((btn, i) => {
        const card = document.createElement('div');
        card.className = 'bg-white rounded-lg shadow p-3 grid grid-cols-[1fr_1fr_1fr_auto] gap-2 items-center';
        card.innerHTML = `
            <input value="${escapeHtml(btn.text)}" placeholder="Текст кнопки" class="border rounded p-2" data-field="text" data-idx="${i}" maxlength="64">
            <select class="border rounded p-2" data-field="action_type" data-idx="${i}">
                <option value="url" ${btn.action_type === 'url' ? 'selected' : ''}>Открыть ссылку</option>
                <option value="goto_step" ${btn.action_type === 'goto_step' ? 'selected' : ''}>Перейти на шаг</option>
                <option value="add_tag" ${btn.action_type === 'add_tag' ? 'selected' : ''}>Добавить тег</option>
                <option value="pay_product" ${btn.action_type === 'pay_product' ? 'selected' : ''}>Оплатить продукт</option>
            </select>
            <input value="${escapeHtml(btn.action_value)}" placeholder="Значение" class="border rounded p-2" data-field="action_value" data-idx="${i}">
            <button class="px-2 py-1 border rounded text-red-600 delete-btn" data-idx="${i}">×</button>
        `;
        list.appendChild(card);
    });
    list.querySelectorAll('[data-field]').forEach(el => {
        el.addEventListener('input', (e) => {
            STATE.buttons[parseInt(e.target.dataset.idx)][e.target.dataset.field] = e.target.value;
        });
        el.addEventListener('change', (e) => {
            STATE.buttons[parseInt(e.target.dataset.idx)][e.target.dataset.field] = e.target.value;
        });
    });
    list.querySelectorAll('.delete-btn').forEach(el => {
        el.addEventListener('click', (e) => {
            STATE.buttons.splice(parseInt(e.target.dataset.idx), 1);
            renderButtons();
        });
    });
}

document.querySelectorAll('.add-msg').forEach(el => {
    el.addEventListener('click', () => {
        STATE.messages.push({
            id: uuid(),
            type: el.dataset.type,
            content: '',
            file_id: '',
            caption: '',
            delay_after: 0,
        });
        renderMessages();
    });
});

document.getElementById('add-btn').addEventListener('click', () => {
    STATE.buttons.push({ id: uuid(), text: '', action_type: 'url', action_value: '' });
    renderButtons();
});

document.getElementById('btn-save').addEventListener('click', async () => {
    // Собираем blocks: сначала сообщения в порядке, потом ButtonGroup (если есть кнопки)
    const blocks = STATE.messages.map(m => {
        const b = { id: m.id, type: m.type, delay_after: m.delay_after };
        if (m.type === 'text') b.content = m.content;
        else { b.file_id = m.file_id; b.caption = m.caption; }
        return b;
    });
    if (STATE.buttons.length) {
        blocks.push({
            id: uuid(),
            type: 'buttons',
            buttons: STATE.buttons.map(btn => ({
                id: btn.id,
                text: btn.text,
                action: { type: btn.action_type, value: btn.action_value },
            })),
        });
    }

    const payload = {
        name: document.getElementById('name').value,
        step_key: document.getElementById('step_key').value,
        is_active: document.getElementById('is_active').checked,
        config: {
            delay_before_seconds: parseInt(document.getElementById('delay_before').value) || 0,
            wait_for_payment: document.getElementById('wait_for_payment').checked,
            blocks,
            add_tags_after: document.getElementById('add_tags').value.split(',').map(t => t.trim()).filter(Boolean),
            next_step: document.getElementById('next_step').value,
        },
    };

    try {
        await API.put(`/funnels/${FUNNEL_ID}/steps/${STEP_ID}`, payload);
        toast('Сохранено', 'success');
    } catch (err) {
        toast('Ошибка: ' + err.message, 'error');
    }
});

function escapeHtml(s) {
    return (s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

load();
</script>
{% endblock %}
```

## Задача 8 — app/templates/admin/users.html

```html
{% extends "admin/base.html" %}
{% block title %}Пользователи{% endblock %}
{% block content %}
<h2 class="text-2xl font-bold mb-6">Пользователи</h2>
<div class="bg-white rounded-lg shadow overflow-x-auto">
    <table class="w-full text-sm">
        <thead class="bg-gray-50 text-left">
            <tr>
                <th class="p-3">Username</th>
                <th class="p-3">Telegram ID</th>
                <th class="p-3">Воронка</th>
                <th class="p-3">Шаг</th>
                <th class="p-3">Теги</th>
                <th class="p-3">Дата</th>
            </tr>
        </thead>
        <tbody id="users-body"></tbody>
    </table>
</div>
{% endblock %}
{% block scripts %}
<script>
async function load() {
    const users = await API.get('/users');
    const tbody = document.getElementById('users-body');
    tbody.innerHTML = users.map(u => `
        <tr class="border-t">
            <td class="p-3">${u.username ? '@' + escapeHtml(u.username) : '—'}</td>
            <td class="p-3 font-mono text-xs">${u.telegram_id}</td>
            <td class="p-3">${escapeHtml(u.current_funnel_name || '—')}</td>
            <td class="p-3">${escapeHtml(u.current_step_name || '—')}</td>
            <td class="p-3">${u.tags.map(t => `<span class="bg-gray-100 px-2 py-0.5 rounded text-xs">${escapeHtml(t)}</span>`).join(' ')}</td>
            <td class="p-3">${new Date(u.created_at).toLocaleDateString('ru-RU')}</td>
        </tr>
    `).join('') || '<tr><td colspan="6" class="p-6 text-center text-gray-500">Пользователей пока нет</td></tr>';
}
function escapeHtml(s) { return (s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
load();
</script>
{% endblock %}
```

## Задача 9 — app/templates/admin/analytics.html

```html
{% extends "admin/base.html" %}
{% block title %}Аналитика{% endblock %}
{% block content %}
<div class="flex items-center justify-between mb-6">
    <h2 class="text-2xl font-bold">Аналитика</h2>
    <select id="period" class="border rounded p-2">
        <option value="7">7 дней</option>
        <option value="30" selected>30 дней</option>
        <option value="365">Год</option>
    </select>
</div>

<div id="summary" class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8"></div>

<h3 class="text-xl font-bold mb-4">Воронки</h3>
<div id="funnels-stats" class="space-y-4"></div>
{% endblock %}
{% block scripts %}
<script>
async function load() {
    const days = document.getElementById('period').value;
    const [summary, funnels] = await Promise.all([
        API.get(`/analytics/summary?period_days=${days}`),
        API.get('/analytics/funnels'),
    ]);

    document.getElementById('summary').innerHTML = `
        <div class="bg-white rounded-lg shadow p-4"><div class="text-3xl font-bold">${summary.new_users_count}</div><div class="text-sm text-gray-500">Новых юзеров</div></div>
        <div class="bg-white rounded-lg shadow p-4"><div class="text-3xl font-bold">${summary.total_users_count}</div><div class="text-sm text-gray-500">Всего юзеров</div></div>
        <div class="bg-white rounded-lg shadow p-4"><div class="text-3xl font-bold">${summary.payments_count}</div><div class="text-sm text-gray-500">Оплат</div></div>
        <div class="bg-white rounded-lg shadow p-4"><div class="text-3xl font-bold">${summary.revenue_total.toFixed(0)} ₽</div><div class="text-sm text-gray-500">Выручка</div></div>
        <div class="bg-white rounded-lg shadow p-4"><div class="text-3xl font-bold">${summary.conversion_percent}%</div><div class="text-sm text-gray-500">Конверсия</div></div>
    `;

    document.getElementById('funnels-stats').innerHTML = funnels.map(f => `
        <div class="bg-white rounded-lg shadow p-4">
            <h4 class="font-bold mb-3">${escapeHtml(f.funnel_name)}</h4>
            <div class="space-y-1">
                ${f.steps_stats.map(s => `
                    <div class="flex items-center gap-3">
                        <div class="flex-1">${escapeHtml(s.step_name)}</div>
                        <div class="w-32 bg-gray-100 rounded h-6 overflow-hidden">
                            <div class="bg-blue-500 h-full" style="width: ${s.percent}%"></div>
                        </div>
                        <div class="w-24 text-sm text-gray-600">${s.users_count} (${s.percent}%)</div>
                    </div>
                `).join('')}
            </div>
        </div>
    `).join('') || '<p class="text-gray-500">Активных воронок нет</p>';
}
document.getElementById('period').addEventListener('change', load);
function escapeHtml(s) { return (s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
load();
</script>
{% endblock %}
```

## Acceptance criteria

```bash
# 1. Пересобрать
docker compose up -d --build

# 2. Открыть в браузере:
# http://localhost:8000/admin/<ADMIN_SECRET_PATH>/

# Ожидается: переадресация на /funnels
# Должна быть воронка welcome

# 3. Клик по воронке welcome
# Открывается редактор с 5 шагами

# 4. Клик по шагу "Приветствие"
# Открывается редактор шага с полями и сообщением

# 5. Изменить текст сообщения, нажать "Сохранить"
# Toast "Сохранено"

# 6. Проверить в Telegram
# Написать боту /reset (если есть) или удалить свои user_tags и user_funnel_state
# /start → должен прийти изменённый текст

# 7. Пройти по всем разделам: пользователи, аналитика
# Должны показывать данные
```

**Покажи скриншоты всех 4 страниц (воронки, редактор воронки, редактор шага, аналитика).**

## Важные замечания

- **Для загрузки file_id** проще всего отправить файл боту в `@RawDataBot` в Telegram — он покажет file_id. Потом вставить в админку.
- **TailwindCSS через CDN** — не для production, но для MVP подходит. Потом при желании можно перейти на сборку.
- **Нет preview.** Тестирование через Telegram.
- **Все JSON-endpoints уже готовы** из Промпта 3 — не нужно их менять.

После выполнения — промпт закрыт.
