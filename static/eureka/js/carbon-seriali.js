/* CARBON Dashboard — Seriali per Reparto */

const THEME_KEY = 'carbon-theme';
const API_BASE = (document.body.dataset.apiBase || '/carbon/seriali/').replace(/\/?$/, '/');

function apiUrl(path, query) {
    const clean = String(path || '').replace(/^\//, '');
    const qs = query ? String(query) : '';
    return `${API_BASE}${clean}${qs ? `?${qs}` : ''}`;
}

function getTheme() {
    return document.documentElement.getAttribute('data-theme') || 'dark';
}

function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function chartThemeColors() {
    return {
        text: cssVar('--chart-text') || '#7a849e',
        grid: cssVar('--chart-grid') || 'rgba(255,255,255,0.04)',
        border: cssVar('--chart-border') || '#06080f',
        cyan: cssVar('--cyan') || '#22d3ee',
        emerald: cssVar('--emerald') || '#34d399',
        amber: cssVar('--amber') || '#fbbf24',
        violet: cssVar('--violet') || '#a78bfa',
        fillEmerald: cssVar('--chart-fill-emerald'),
        fillAmber: cssVar('--chart-fill-amber'),
        fillCyan: cssVar('--chart-fill-cyan'),
        fillCyanBar: cssVar('--chart-fill-cyan-bar'),
        fillEmeraldBar: cssVar('--chart-fill-emerald-bar'),
        fillViolet: cssVar('--chart-fill-violet'),
    };
}

function getChartDefaults() {
    const c = chartThemeColors();
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: c.text, font: { family: 'Outfit', size: 11 } } } },
        scales: {
            x: { ticks: { color: c.text, font: { family: 'JetBrains Mono', size: 10 } }, grid: { color: c.grid } },
            y: { ticks: { color: c.text, font: { family: 'JetBrains Mono', size: 10 } }, grid: { color: c.grid } },
        },
    };
}

function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_KEY, theme);
    refreshAll();
}

function toggleTheme() {
    setTheme(getTheme() === 'dark' ? 'light' : 'dark');
}

let charts = {};

function getFilters() {
    return {
        codartser: document.getElementById('filter-codartser').value.trim(),
        reparto: document.getElementById('filter-reparto').value,
        operatore: document.getElementById('filter-operatore').value,
        stato: document.getElementById('filter-stato').value,
        stampo: document.getElementById('filter-stampo').value,
        da: document.getElementById('filter-da').value,
        a: document.getElementById('filter-a').value,
    };
}

function buildQuery(params, omit = []) {
    const f = getFilters();
    const q = new URLSearchParams();
    if (f.codartser) q.set('codartser', f.codartser);
    if (f.reparto) q.set('reparto', f.reparto);
    if (f.operatore) q.set('operatore', f.operatore);
    if (f.stato) q.set('stato', f.stato);
    if (!omit.includes('stampo') && f.stampo) q.set('stampo', f.stampo);
    if (f.da) q.set('da', f.da);
    if (f.a) q.set('a', f.a);
    Object.entries(params || {}).forEach(([k, v]) => q.set(k, v));
    return q.toString();
}

async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
}

function animateValue(el, target) {
    const duration = 800;
    const start = parseInt(el.textContent.replace(/\./g, '')) || 0;
    const diff = target - start;
    const t0 = performance.now();
    function step(now) {
        const p = Math.min((now - t0) / duration, 1);
        el.textContent = Math.round(start + diff * (1 - Math.pow(1 - p, 3))).toLocaleString('it-IT');
        if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
}

function destroyChart(key) {
    if (charts[key]) { charts[key].destroy(); charts[key] = null; }
}

function avanzamentoBadge(stato) {
    if (stato === 'COMPLETATO') return '<span class="badge-stato badge-completato">COMPLETATO</span>';
    if (stato === 'DA TERMINARE') return '<span class="badge-stato badge-da-terminare">DA TERMINARE</span>';
    return `<span class="badge-stato">${stato}</span>`;
}

async function loadKPI() {
    const d = await fetchJSON(apiUrl('api/kpi/', buildQuery()));
    animateValue(document.getElementById('kpi-totale'), d.totale_seriali);
    animateValue(document.getElementById('kpi-completati'), d.completati);
    animateValue(document.getElementById('kpi-da-terminare'), d.da_terminare);
    animateValue(document.getElementById('kpi-reparti'), d.reparti_coinvolti);
    animateValue(document.getElementById('kpi-rilavorazioni'), d.rilavorazioni);
}

async function loadSerialiLista() {
    const d = await fetchJSON(apiUrl('api/seriali-lista/', buildQuery({ limit: 200 })));
    const tbody = document.getElementById('table-seriali');
    document.getElementById('table-count-seriali').textContent = `${d.total} righe`;
    if (!d.rows.length) {
        tbody.innerHTML = '<tr><td colspan="18" class="loading-row">Nessun seriale con INIZIO trovato</td></tr>';
        return;
    }
    const opeCols = Array.from({ length: 10 }, (_, i) => `operatore${i + 1}`);
    tbody.innerHTML = d.rows.map(r => `
        <tr class="${r.stato === 'DA TERMINARE' ? 'row-alert' : ''}">
            <td><strong>${r.seriale}</strong></td>
            <td>${r.cod_reparto}</td>
            <td>${r.descr_reparto}</td>
            <td>${avanzamentoBadge(r.stato)}</td>
            <td>${r.data_inizio}</td>
            <td>${r.data_fine}</td>
            <td>${r.codart}</td>
            <td>${r.codstampo}</td>
            ${opeCols.map(k => `<td class="operatore-cell" title="${r[k]}">${r[k]}</td>`).join('')}
        </tr>
    `).join('');
}

async function loadStato() {
    const d = await fetchJSON(apiUrl('api/seriali-stato/', buildQuery()));
    const c = chartThemeColors();
    destroyChart('stato');
    charts.stato = new Chart(document.getElementById('chart-stato'), {
        type: 'doughnut',
        data: {
            labels: d.labels,
            datasets: [{
                data: d.valori,
                backgroundColor: d.labels.map(l => l === 'COMPLETATO' ? c.emerald : c.amber),
                borderColor: c.border, borderWidth: 3, hoverOffset: 10,
            }],
        },
        options: {
            responsive: true, maintainAspectRatio: false, cutout: '62%',
            plugins: { legend: { position: 'bottom', labels: { color: c.text, padding: 14, font: { family: 'Outfit', size: 12 } } } },
        },
    });
}

async function loadReparto() {
    const d = await fetchJSON(apiUrl('api/seriali-reparto/', buildQuery()));
    const c = chartThemeColors();
    destroyChart('reparto');
    const labels = d.labels || [];
    const completati = d.completati || [];
    const daTerminare = d.da_terminare || [];

    charts.reparto = new Chart(document.getElementById('chart-reparto'), {
        type: 'bar',
        data: {
            labels,
            datasets: [
                {
                    label: 'Completati',
                    data: completati,
                    backgroundColor: c.fillEmerald,
                    borderColor: c.emerald,
                    borderWidth: 1,
                    borderRadius: 4,
                },
                {
                    label: 'Da terminare',
                    data: daTerminare,
                    backgroundColor: c.fillAmber,
                    borderColor: c.amber,
                    borderWidth: 1,
                    borderRadius: 4,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: c.text, font: { family: 'Outfit', size: 12 } },
                },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y}`,
                    },
                },
            },
            scales: {
                x: {
                    ticks: {
                        color: c.text,
                        font: { family: 'JetBrains Mono', size: 9 },
                        maxRotation: 45,
                        minRotation: 0,
                    },
                    grid: { color: c.grid },
                },
                y: {
                    beginAtZero: true,
                    ticks: {
                        color: c.text,
                        font: { family: 'JetBrains Mono', size: 10 },
                        precision: 0,
                    },
                    grid: { color: c.grid },
                },
            },
        },
    });
}

async function loadGiorno() {
    const d = await fetchJSON(apiUrl('api/lavorazioni-giorno/', buildQuery()));
    const c = chartThemeColors();
    destroyChart('giorno');
    charts.giorno = new Chart(document.getElementById('chart-giorno'), {
        type: 'line',
        data: {
            labels: d.labels,
            datasets: [{
                label: 'Registrazioni', data: d.valori,
                borderColor: c.cyan, backgroundColor: c.fillCyan,
                fill: true, tension: 0.35, pointRadius: 4, borderWidth: 2,
            }],
        },
        options: { ...getChartDefaults(), plugins: { legend: { display: false } } },
    });
}

async function loadExtra() {
    const d = await fetchJSON(apiUrl('api/lavorazioni-extra/', buildQuery({ limit: 8 })));
    const c = chartThemeColors();
    destroyChart('extra');
    charts.extra = new Chart(document.getElementById('chart-extra'), {
        type: 'bar',
        data: {
            labels: d.labels,
            datasets: [{ label: 'Occorrenze', data: d.valori, backgroundColor: c.fillViolet, borderRadius: 6 }],
        },
        options: { ...getChartDefaults(), indexAxis: 'y', plugins: { legend: { display: false } } },
    });
}

async function loadStampiOpzioni() {
    const select = document.getElementById('filter-stampo');
    const current = select.value;
    const f = getFilters();
    const q = new URLSearchParams();
    if (f.da) q.set('da', f.da);
    if (f.a) q.set('a', f.a);
    const d = await fetchJSON(apiUrl('api/stampi-opzioni/', q.toString()));
    select.innerHTML = '<option value="">Tutti</option>';
    if (d.richiede_periodo) {
        const hint = document.createElement('option');
        hint.disabled = true;
        hint.textContent = '— Imposta Dal/Al —';
        select.appendChild(hint);
        select.value = '';
        return;
    }
    d.stampi.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s;
        opt.textContent = s;
        select.appendChild(opt);
    });
    if (current && d.stampi.includes(current)) {
        select.value = current;
    } else if (current && !d.stampi.includes(current)) {
        select.value = '';
    }
}

async function loadStampi() {
    const d = await fetchJSON(apiUrl('api/stampi-seriali/', buildQuery()));
    const c = chartThemeColors();
    destroyChart('stampi');
    charts.stampi = new Chart(document.getElementById('chart-stampi'), {
        type: 'bar',
        data: {
            labels: d.labels,
            datasets: [
                { label: 'Partite', data: d.partite, backgroundColor: c.fillCyanBar, borderRadius: 6 },
                { label: 'Seriali', data: d.seriali, backgroundColor: c.fillEmeraldBar, borderRadius: 6 },
            ],
        },
        options: getChartDefaults(),
    });
}

async function loadTableStampi() {
    const d = await fetchJSON(apiUrl('api/stampi-dettaglio/', buildQuery({ limit: 10 })));
    const tbody = document.getElementById('table-stampi');
    document.getElementById('table-count-stampi').textContent = `${d.rows.length} record`;
    if (!d.rows.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading-row">Nessun dato</td></tr>';
        return;
    }
    tbody.innerHTML = d.rows.map(r => `
        <tr>
            <td>${r.id}</td>
            <td><strong>${r.stampo}</strong></td>
            <td>${r.cod_reparto}<br><span class="table-sub">${r.descr_reparto}</span></td>
            <td>${r.key_lav}</td>
            <td>${r.num_seriali}</td>
            <td class="seriali-cell">${r.seriali.join('<br>') || '—'}</td>
            <td>${r.sacco}</td>
        </tr>
    `).join('');
}

async function refreshAll() {
    try {
        await loadStampiOpzioni();
        await Promise.all([
            loadKPI(), loadSerialiLista(), loadStato(), loadReparto(),
            loadGiorno(), loadExtra(), loadStampi(), loadTableStampi(),
        ]);
    } catch (err) {
        console.error('Errore dashboard:', err);
        alert('Errore aggiornamento dati. Controlla i filtri inseriti.');
    }
}

function updateClock() {
    document.getElementById('clock').textContent = new Date().toLocaleString('it-IT', {
        weekday: 'short', day: '2-digit', month: 'short',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
}

function todayInputValue() {
    const d = new Date();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${d.getFullYear()}-${m}-${day}`;
}

function initDefaultDates() {
    const today = todayInputValue();
    document.getElementById('filter-da').value = today;
    document.getElementById('filter-a').value = today;
}

document.getElementById('btn-apply').addEventListener('click', refreshAll);
document.getElementById('btn-theme').addEventListener('click', toggleTheme);
document.getElementById('btn-reset').addEventListener('click', () => {
    ['filter-codartser', 'filter-reparto', 'filter-operatore', 'filter-stato', 'filter-stampo']
        .forEach(id => document.getElementById(id).value = '');
    initDefaultDates();
    document.getElementById('codartser-suggestions').innerHTML = '';
    refreshAll();
});

let suggestTimer;
document.getElementById('filter-codartser').addEventListener('input', (e) => {
    clearTimeout(suggestTimer);
    const q = e.target.value.trim();
    if (q.length < 2) return;
    suggestTimer = setTimeout(async () => {
        try {
            const d = await fetchJSON(apiUrl('api/codartser-suggest/', `q=${encodeURIComponent(q)}`));
            document.getElementById('codartser-suggestions').innerHTML =
                d.suggestions.map(s => `<option value="${s}">`).join('');
        } catch (_) {}
    }, 300);
});

updateClock();
setInterval(updateClock, 1000);
initDefaultDates();
refreshAll();
setInterval(refreshAll, 60000);
