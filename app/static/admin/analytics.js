async function loadAnalytics() {
    const days = document.getElementById('period').value;
    const [summary, funnels] = await Promise.all([
        API.get(`/analytics/summary?period_days=${days}`),
        API.get('/analytics/funnels'),
    ]);

    document.getElementById('summary').innerHTML = `
        <div class="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><div class="text-3xl font-semibold">${summary.new_users_count}</div><div class="mt-1 text-sm text-slate-500">Новых пользователей</div></div>
        <div class="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><div class="text-3xl font-semibold">${summary.total_users_count}</div><div class="mt-1 text-sm text-slate-500">Всего пользователей</div></div>
        <div class="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><div class="text-3xl font-semibold">${summary.payments_count}</div><div class="mt-1 text-sm text-slate-500">Оплат</div></div>
        <div class="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><div class="text-3xl font-semibold">${Number(summary.revenue_total).toFixed(0)} ₽</div><div class="mt-1 text-sm text-slate-500">Выручка</div></div>
        <div class="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200"><div class="text-3xl font-semibold">${summary.conversion_percent}%</div><div class="mt-1 text-sm text-slate-500">Конверсия</div></div>
    `;

    const funnelsContainer = document.getElementById('funnels-stats');
    if (!funnels.length) {
        funnelsContainer.innerHTML = '<div class="rounded-2xl bg-white p-5 text-sm text-slate-500 ring-1 ring-slate-200">Воронок нет</div>';
        return;
    }

    funnelsContainer.innerHTML = funnels.map((funnel) => `
        <article class="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
            <h4 class="text-lg font-semibold">${escapeHtml(funnel.funnel_name)}</h4>
            <div class="mt-4 space-y-3">
                ${(funnel.steps_stats || []).map((step) => `
                    <div class="flex items-center gap-3">
                        <div class="w-56 shrink-0 text-sm text-slate-600">${escapeHtml(step.step_name)}</div>
                        <div class="h-3 flex-1 overflow-hidden rounded-full bg-slate-100">
                            <div class="h-full rounded-full bg-slate-900" style="width: ${Number(step.percent || 0)}%"></div>
                        </div>
                        <div class="w-28 text-right text-sm text-slate-600">${step.users_count} (${step.percent}%)</div>
                    </div>
                `).join('')}
            </div>
        </article>
    `).join('');
}

document.getElementById('period').addEventListener('change', () => loadAnalytics());

loadAnalytics();