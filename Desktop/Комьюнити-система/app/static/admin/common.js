const API = {
    base: window.API_BASE,

    asyncget(path) {
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
            return new Error(data.error ? .message || `HTTP ${res.status}`);
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
    return (s || '').toString().replace(/[&<>"]|'/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}