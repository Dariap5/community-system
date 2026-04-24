const funnelEditorState = window.PAGE_DATA;
const funnelId = funnelEditorState.funnel_id;
const stepsContainer = document.getElementById('steps-list');
const addStepModal = document.getElementById('add-step-modal');
let draggedStep = null;

stepsContainer.addEventListener('dragover', (event) => {
    event.preventDefault();
    if (!draggedStep) {
        return;
    }

    const afterElement = getDragAfterElement(stepsContainer, event.clientY);
    if (afterElement == null) {
        stepsContainer.appendChild(draggedStep);
    } else {
        stepsContainer.insertBefore(draggedStep, afterElement);
    }
});

function openStepModal() {
    addStepModal.classList.remove('hidden');
    addStepModal.classList.add('flex');
}

function closeStepModal() {
    addStepModal.classList.add('hidden');
    addStepModal.classList.remove('flex');
}

function updateDeeplinkPreview(entryKey) {
    const preview = document.getElementById('deeplink-preview');
    if (!entryKey) {
        preview.textContent = '';
        return;
    }
    preview.innerHTML = `Ссылка: <code class="rounded bg-slate-100 px-1 py-0.5">/start ${escapeHtml(entryKey)}</code>`;
}

async function saveOrder() {
    const stepIds = Array.from(stepsContainer.querySelectorAll('[data-step-id]')).map((element) => element.dataset.stepId);
    if (!stepIds.length) {
        return;
    }
    await API.post(`/funnels/${funnelId}/steps/reorder`, { step_ids_in_order: stepIds });
}

function attachDnD() {
    stepsContainer.querySelectorAll('[data-step-id]').forEach((card) => {
        card.addEventListener('dragstart', () => {
            draggedStep = card;
            card.classList.add('opacity-50');
        });
        card.addEventListener('dragend', async() => {
            if (draggedStep) {
                draggedStep.classList.remove('opacity-50');
                draggedStep = null;
                try {
                    await saveOrder();
                    await loadFunnel();
                } catch (error) {
                    toast(error.message, 'error');
                }
            }
        });
    });
}

function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('[data-step-id]:not(.opacity-50)')];
    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) {
            return { offset, element: child };
        }
        return closest;
    }, { offset: Number.NEGATIVE_INFINITY, element: null }).element;
}

async function loadFunnel() {
    const funnel = await API.get(`/funnels/${funnelId}`);
    document.getElementById('funnel-title').textContent = funnel.name;
    document.getElementById('funnel-name').value = funnel.name;
    document.getElementById('funnel-key').value = funnel.entry_key || '';
    document.getElementById('funnel-behavior').value = funnel.cross_entry_behavior;
    document.getElementById('funnel-active').checked = funnel.is_active;
    updateDeeplinkPreview(funnel.entry_key);

    stepsContainer.innerHTML = '';
    if (!funnel.steps.length) {
        stepsContainer.innerHTML = '<div class="rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">Шагов пока нет</div>';
        return;
    }

    for (const [index, step] of funnel.steps.entries()) {
        const card = document.createElement('article');
        card.className = 'step-card cursor-move rounded-xl border border-slate-200 bg-slate-50 p-4';
        card.draggable = true;
        card.dataset.stepId = step.id;
        card.innerHTML = `
            <div class="flex items-start justify-between gap-3">
                <div>
                    <div class="flex flex-wrap items-center gap-2">
                        <span class="rounded-full bg-slate-900 px-2 py-0.5 text-xs text-white">${index + 1}</span>
                        <h4 class="text-base font-semibold">${escapeHtml(step.name)}</h4>
                        <code class="rounded bg-white px-2 py-0.5 text-xs text-slate-500">${escapeHtml(step.step_key)}</code>
                        ${step.is_active ? '' : '<span class="rounded-full bg-slate-200 px-2 py-0.5 text-xs text-slate-600">выключен</span>'}
                    </div>
                    <p class="mt-2 text-sm text-slate-600">${escapeHtml(step.first_message_preview || 'Без превью')}</p>
                </div>
                <div class="flex shrink-0 items-center gap-2">
                    <a href="/admin/${funnelEditorState.secret}/funnels/${funnelId}/steps/${step.id}" class="rounded-lg bg-white px-3 py-2 text-sm hover:bg-slate-100">Редактировать</a>
                    <button type="button" class="delete-step rounded-lg border border-rose-200 px-3 py-2 text-sm text-rose-700 hover:bg-rose-50" data-step-id="${step.id}">Удалить</button>
                </div>
            </div>
        `;
        stepsContainer.appendChild(card);
    }

    stepsContainer.querySelectorAll('.delete-step').forEach((button) => {
        button.addEventListener('click', async(event) => {
            event.preventDefault();
            if (!confirmAction('Удалить шаг?')) {
                return;
            }
            try {
                await API.delete(`/funnels/${funnelId}/steps/${button.dataset.stepId}`);
                toast('Удалено', 'success');
                await loadFunnel();
            } catch (error) {
                toast(error.message, 'error');
            }
        });
    });

    attachDnD();
}

document.getElementById('funnel-key').addEventListener('input', (event) => updateDeeplinkPreview(event.currentTarget.value.trim()));
document.getElementById('btn-save-funnel').type = 'button';
document.getElementById('btn-save-funnel').addEventListener('click', async(event) => {
    event.preventDefault();
    try {
        await API.patch(`/funnels/${funnelId}`, {
            name: document.getElementById('funnel-name').value.trim(),
            entry_key: document.getElementById('funnel-key').value.trim() || null,
            cross_entry_behavior: document.getElementById('funnel-behavior').value,
            is_active: document.getElementById('funnel-active').checked,
        });
        toast('Сохранено', 'success');
    } catch (error) {
        toast(error.message, 'error');
    }
});

document.getElementById('btn-add-step').type = 'button';
document.getElementById('btn-add-step').addEventListener('click', (event) => {
    event.preventDefault();
    openStepModal();
});
document.getElementById('cancel-add-step').type = 'button';
document.getElementById('cancel-add-step').addEventListener('click', (event) => {
    event.preventDefault();
    closeStepModal();
});
addStepModal.addEventListener('click', (event) => {
    if (event.target === addStepModal) {
        closeStepModal();
    }
});
document.getElementById('confirm-add-step').type = 'button';
document.getElementById('confirm-add-step').addEventListener('click', async(event) => {
    event.preventDefault();
    const name = document.getElementById('step-name').value.trim();
    const stepKey = document.getElementById('step-key').value.trim();

    if (!name || !stepKey) {
        toast('Заполните название и ключ', 'error');
        return;
    }

    try {
        const step = await API.post(`/funnels/${funnelId}/steps`, {
            name,
            step_key: stepKey,
            config: {},
        });
        closeStepModal();
        window.location.href = `/admin/${funnelEditorState.secret}/funnels/${funnelId}/steps/${step.id}`;
    } catch (error) {
        toast(error.message, 'error');
    }
});

loadFunnel();