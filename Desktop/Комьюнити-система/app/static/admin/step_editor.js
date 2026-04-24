const stepEditorState = window.PAGE_DATA;
const funnelId = stepEditorState.funnel_id;
const stepId = stepEditorState.step_id;

const editorState = {
    messages: [],
    buttons: [],
};

function newId() {
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function renderMessages() {
    const list = document.getElementById('messages-list');
    list.innerHTML = '';

    if (!editorState.messages.length) {
        list.innerHTML = '<div class="rounded-xl border border-dashed border-slate-300 p-5 text-sm text-slate-500">Сообщений пока нет</div>';
        return;
    }

    editorState.messages.forEach((message, index) => {
        const card = document.createElement('section');
        card.className = 'rounded-xl border border-slate-200 bg-slate-50 p-4';

        const controls = document.createElement('div');
        controls.className = 'mb-3 flex items-center justify-between gap-3';
        controls.innerHTML = `
            <div class="flex items-center gap-2">
                <span class="rounded-full bg-slate-900 px-2 py-0.5 text-xs text-white">${index + 1}</span>
                <span class="font-medium">${message.type === 'text' ? 'Текст' : message.type === 'photo' ? 'Фото' : 'Документ'}</span>
            </div>
            <div class="flex gap-2 text-sm">
                <button class="move-up rounded-lg border border-slate-300 px-2 py-1 ${index === 0 ? 'opacity-40' : ''}" data-index="${index}" ${index === 0 ? 'disabled' : ''}>↑</button>
                <button class="move-down rounded-lg border border-slate-300 px-2 py-1 ${index === editorState.messages.length - 1 ? 'opacity-40' : ''}" data-index="${index}" ${index === editorState.messages.length - 1 ? 'disabled' : ''}>↓</button>
                <button class="delete-message rounded-lg border border-rose-200 px-2 py-1 text-rose-700" data-index="${index}">×</button>
            </div>
        `;
        card.appendChild(controls);

        if (message.type === 'text') {
            const textarea = document.createElement('textarea');
            textarea.className = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm';
            textarea.rows = 4;
            textarea.value = message.content || '';
            textarea.addEventListener('input', (event) => {
                message.content = event.currentTarget.value;
            });
            card.appendChild(textarea);
        } else {
            const fileId = document.createElement('input');
            fileId.className = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm';
            fileId.placeholder = 'Telegram file_id';
            fileId.value = message.file_id || '';
            fileId.addEventListener('input', (event) => {
                message.file_id = event.currentTarget.value;
            });

            const caption = document.createElement('input');
            caption.className = 'mt-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm';
            caption.placeholder = 'Подпись (опционально)';
            caption.value = message.caption || '';
            caption.addEventListener('input', (event) => {
                message.caption = event.currentTarget.value;
            });

            card.appendChild(fileId);
            card.appendChild(caption);
        }

        const footer = document.createElement('label');
        footer.className = 'mt-3 flex items-center gap-2 text-sm text-slate-600';
        footer.innerHTML = `Задержка после, сек <input type="number" min="0" class="w-24 rounded-lg border border-slate-300 px-2 py-1" value="${message.delay_after || 0}">`;
        const delayInput = footer.querySelector('input');
        delayInput.addEventListener('input', (event) => {
            message.delay_after = Number(event.currentTarget.value || 0);
        });
        card.appendChild(footer);

        list.appendChild(card);
    });

    list.querySelectorAll('.delete-message').forEach((button) => {
        button.addEventListener('click', () => {
            editorState.messages.splice(Number(button.dataset.index), 1);
            renderMessages();
        });
    });

    list.querySelectorAll('.move-up').forEach((button) => {
        button.addEventListener('click', () => {
            const index = Number(button.dataset.index);
            if (index <= 0) return;
            [editorState.messages[index - 1], editorState.messages[index]] = [editorState.messages[index], editorState.messages[index - 1]];
            renderMessages();
        });
    });

    list.querySelectorAll('.move-down').forEach((button) => {
        button.addEventListener('click', () => {
            const index = Number(button.dataset.index);
            if (index >= editorState.messages.length - 1) return;
            [editorState.messages[index + 1], editorState.messages[index]] = [editorState.messages[index], editorState.messages[index + 1]];
            renderMessages();
        });
    });
}

function renderButtons() {
    const list = document.getElementById('buttons-list');
    list.innerHTML = '';

    if (!editorState.buttons.length) {
        list.innerHTML = '<div class="rounded-xl border border-dashed border-slate-300 p-5 text-sm text-slate-500">Кнопок пока нет</div>';
        return;
    }

    editorState.buttons.forEach((button, index) => {
        const card = document.createElement('section');
        card.className = 'rounded-xl border border-slate-200 bg-slate-50 p-4';
        card.innerHTML = `
            <div class="mb-3 flex items-center justify-between gap-3">
                <span class="font-medium">Кнопка ${index + 1}</span>
                <button class="delete-button rounded-lg border border-rose-200 px-2 py-1 text-sm text-rose-700" data-index="${index}">Удалить</button>
            </div>
            <div class="grid gap-3 md:grid-cols-3">
                <input class="button-text rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Текст кнопки" value="${escapeHtml(button.text || '')}">
                <select class="button-type rounded-lg border border-slate-300 px-3 py-2 text-sm">
                    <option value="url" ${button.action_type === 'url' ? 'selected' : ''}>URL</option>
                    <option value="goto_step" ${button.action_type === 'goto_step' ? 'selected' : ''}>goto_step</option>
                    <option value="add_tag" ${button.action_type === 'add_tag' ? 'selected' : ''}>add_tag</option>
                    <option value="pay_product" ${button.action_type === 'pay_product' ? 'selected' : ''}>pay_product</option>
                </select>
                <input class="button-value rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Значение" value="${escapeHtml(button.action_value || '')}">
            </div>
        `;

        const [textInput, typeSelect, valueInput] = card.querySelectorAll('input, select');
        textInput.addEventListener('input', (event) => {
            button.text = event.currentTarget.value;
        });
        typeSelect.addEventListener('change', (event) => {
            button.action_type = event.currentTarget.value;
        });
        valueInput.addEventListener('input', (event) => {
            button.action_value = event.currentTarget.value;
        });

        list.appendChild(card);
    });

    list.querySelectorAll('.delete-button').forEach((button) => {
        button.addEventListener('click', () => {
            editorState.buttons.splice(Number(button.dataset.index), 1);
            renderButtons();
        });
    });
}

async function loadStep() {
    const [step, steps] = await Promise.all([
        API.get(`/funnels/${funnelId}/steps/${stepId}`),
        API.get(`/funnels/${funnelId}/steps`),
    ]);

    document.getElementById('step-title').textContent = step.name;
    document.getElementById('name').value = step.name;
    document.getElementById('step_key').value = step.step_key;
    document.getElementById('is_active').checked = step.is_active;
    document.getElementById('delay_before').value = step.config.delay_before_seconds || 0;
    document.getElementById('wait_for_payment').checked = Boolean(step.config.wait_for_payment);
    document.getElementById('add_tags').value = (step.config.add_tags_after || []).join(', ');

    const nextStepSelect = document.getElementById('next_step');
    nextStepSelect.innerHTML = '<option value="auto">Автоматически</option><option value="end">Конец воронки</option>';
    for (const item of steps) {
        if (item.id === stepId) continue;
        const option = document.createElement('option');
        option.value = item.step_key;
        option.textContent = `${item.name} (${item.step_key})`;
        nextStepSelect.appendChild(option);
    }
    nextStepSelect.value = step.config.next_step || 'auto';

    editorState.messages = [];
    editorState.buttons = [];

    for (const block of step.config.blocks || []) {
        if (block.type === 'buttons') {
            for (const button of block.buttons || []) {
                editorState.buttons.push({
                    id: button.id || newId(),
                    text: button.text || '',
                    action_type: button.action?.type || 'url',
                    action_value: button.action?.value || '',
                });
            }
            continue;
        }

        editorState.messages.push({
            id: block.id || newId(),
            type: block.type,
            content: block.content || '',
            file_id: block.file_id || '',
            caption: block.caption || '',
            delay_after: block.delay_after || 0,
        });
    }

    renderMessages();
    renderButtons();
}

document.querySelectorAll('.add-msg').forEach((button) => {
    button.addEventListener('click', () => {
        editorState.messages.push({
            id: newId(),
            type: button.dataset.type,
            content: '',
            file_id: '',
            caption: '',
            delay_after: 0,
        });
        renderMessages();
    });
});

document.getElementById('add-btn').addEventListener('click', () => {
    editorState.buttons.push({
        id: newId(),
        text: '',
        action_type: 'url',
        action_value: '',
    });
    renderButtons();
});

document.getElementById('btn-save').addEventListener('click', async() => {
    const blocks = editorState.messages.map((message) => {
        const block = {
            id: message.id,
            type: message.type,
            delay_after: Number(message.delay_after || 0),
        };
        if (message.type === 'text') {
            block.content = message.content;
        } else {
            block.file_id = message.file_id;
            block.caption = message.caption || null;
        }
        return block;
    });

    if (editorState.buttons.length) {
        blocks.push({
            id: newId(),
            type: 'buttons',
            buttons: editorState.buttons.map((button) => ({
                id: button.id,
                text: button.text,
                action: {
                    type: button.action_type,
                    value: button.action_value,
                },
            })),
        });
    }

    try {
        await API.put(`/funnels/${funnelId}/steps/${stepId}`, {
            name: document.getElementById('name').value.trim(),
            step_key: document.getElementById('step_key').value.trim(),
            is_active: document.getElementById('is_active').checked,
            config: {
                delay_before_seconds: Number(document.getElementById('delay_before').value || 0),
                wait_for_payment: document.getElementById('wait_for_payment').checked,
                blocks,
                add_tags_after: document.getElementById('add_tags').value.split(',').map((tag) => tag.trim()).filter(Boolean),
                next_step: document.getElementById('next_step').value,
            },
        });
        toast('Сохранено', 'success');
    } catch (error) {
        toast(error.message, 'error');
    }
});

loadStep();