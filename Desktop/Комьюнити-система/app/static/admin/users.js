async function loadUsers() {
    const users = await API.get('/users');
    const body = document.getElementById('users-body');

    if (!users.length) {
        body.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-sm text-slate-500">Пользователей пока нет</td></tr>';
        return;
    }

    body.innerHTML = users.map((user) => `
        <tr class="align-top hover:bg-slate-50">
            <td class="px-4 py-3">${user.username ? '@' + escapeHtml(user.username) : '—'}</td>
            <td class="px-4 py-3 font-mono text-xs">${user.telegram_id}</td>
            <td class="px-4 py-3">${escapeHtml(user.current_funnel_name || '—')}</td>
            <td class="px-4 py-3">${escapeHtml(user.current_step_name || '—')}</td>
            <td class="px-4 py-3">${(user.tags || []).map((tag) => `<span class="mr-1 inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700">${escapeHtml(tag)}</span>`).join('') || '—'}</td>
            <td class="px-4 py-3">${new Date(user.created_at).toLocaleString('ru-RU')}</td>
        </tr>
    `).join('');
}

loadUsers();