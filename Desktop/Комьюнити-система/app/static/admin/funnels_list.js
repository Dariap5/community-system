const funnelsListState = window.PAGE_DATA;
const funnelsContainer = document.getElementById('funnels-list');
const createModal = document.getElementById('create-modal');
const archivedToggle = document.getElementById('show-archived');

function openCreateModal() {
    createModal.classList.remove('hidden');
    createModal.classList.add('flex');
}

function closeCreateModal() {
    createModal.classList.add('hidden');
    createModal.classList.remove('flex');
}

async function loadFunnels() {
    const funnels = await API.get(`/funnels?include_archived=${archivedToggle.checked ? 'true' : 'false'}`);
    funnelsContainer.innerHTML = '';

    if (!funnels.length) {
        funnelsContainer.innerHTML = '<div class="col-span-full rounded-2xl bg-white p-6 text-sm text-slate-500 ring-1 ring-slate-200">Воронок пока нет</div>';
        return;
    }

    for (const funnel of funnels) {
        const card = document.createElement('article');
        card.className = 'rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200';
        card.innerHTML = `
            <div class="mb-3 flex items-start justify-between gap-3">
                <div>
                    <h3 class="text-lg font-semibold">${escapeHtml(funnel.name)}</h3>
                    <p class="mt-1 text-xs text-slate-500">${funnel.entry_key ? `/start ${escapeHtml(funnel.entry_key)}` : 'без deeplink'}</p>
                </div>
                <label class="inline-flex items-center gap-2 text-xs text-slate-500">
                    <input type="checkbox" class="toggle-active rounded border-slate-300" data-id="${funnel.id}" ${funnel.is_active ? 'checked' : ''} ${funnel.is_archived ? 'disabled' : ''}>
                    Активна
                </label>
            </div>
            <div class="mb-4 flex items-center gap-2 text-xs text-slate-500">
                <span>${funnel.steps_count} шагов</span>
                <span>•</span>
                <span>${funnel.active_users_count} активных</span>
                ${funnel.is_archived ? '<span class="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600">архив</span>' : ''}
            </div>
            <div class="flex gap-2">
                <a href="/admin/${funnelsListState.secret}/funnels/${funnel.id}" class="flex-1 rounded-lg bg-slate-900 px-3 py-2 text-center text-sm font-medium text-white hover:bg-slate-700">Открыть</a>
                <button type="button" class="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 duplicate-funnel" data-id="${funnel.id}">Дубль</button>
                <button type="button" class="rounded-lg border border-rose-200 px-3 py-2 text-sm text-rose-700 hover:bg-rose-50 archive-funnel" data-id="${funnel.id}" ${funnel.is_archived ? 'disabled' : ''}>Архив</button>
            </div>
        `;
        funnelsContainer.appendChild(card);
    }

    funnelsContainer.querySelectorAll('.toggle-active').forEach((element) => {
        element.addEventListener('change', async (event) => {
            const target = event.currentTarget;
            try {
                await API.patch(`/funnels/${target.dataset.id}`, { is_active: target.checked });
                toast('Сохранено', 'success');
            } catch (error) {
                target.checked = !target.checked;
                toast(error.message, 'error');
            }
        });
    });

    funnelsContainer.querySelectorAll('.duplicate-funnel').forEach((element) => {
        element.addEventListener('click', async (event) => {
            event.preventDefault();
            try {
                await API.post(`/funnels/${event.currentTarget.dataset.id}/duplicate`);
                toast('Воронка скопирована', 'success');
                await loadFunnels();
            } catch (error) {
                toast(error.message, 'error');
            }
        });
    });

    funnelsContainer.querySelectorAll('.archive-funnel').forEach((element) => {
        element.addEventListener('click', async (event) => {
            event.preventDefault();
            if (!confirmAction('Архивировать воронку?')) {
                return;
            }
            try {
                await API.delete(`/funnels/${event.currentTarget.dataset.id}`);
                toast('В архиве', 'success');
                await loadFunnels();
            } catch (error) {
                toast(error.message, 'error');
            }
        });
    });
}

document.getElementById('btn-create').type = 'button';
document.getElementById('btn-create').addEventListener('click', (event) => {
    event.preventDefault();
    openCreateModal();
});
document.getElementById('cancel-create').type = 'button';
document.getElementById('cancel-create').addEventListener('click', (event) => {
    event.preventDefault();
    closeCreateModal();
});
createModal.addEventListener('click', (event) => {
    if (event.target === createModal) {
        closeCreateModal();
    }
});
document.getElementById('confirm-create').type = 'button';
document.getElementById('confirm-create').addEventListener('click', async (event) => {
    event.preventDefault();
    const name = document.getElementById('new-name').value.trim();
    const entryKey = document.getElementById('new-key').value.trim();

    if (!name) {
        toast('Введите название', 'error');
        return;
    }

    try {
        const funnel = await API.post('/funnels', {
            name,
            entry_key: entryKey || null,
        });
        toast('Создано', 'success');
        closeCreateModal();
        window.location.href = `/admin/${funnelsListState.secret}/funnels/${funnel.id}`;
    } catch (error) {
        toast(error.message, 'error');
    }
});

archivedToggle.addEventListener('change', () => loadFunnels());

loadFunnels();