const API = '';
let token = localStorage.getItem('token');
let charts = {};
let refreshTimer = null;
let logTimer = null;

// ============ ELECTRON DETECTION ============
(function initElectron() {
    if (window.electronAPI?.isElectron) {
        document.body.classList.add('electron-app');
        document.getElementById('custom-titlebar').style.display = 'flex';
        window.electronAPI.onMaximized((isMaximized) => {
            const btn = document.getElementById('btn-maximize');
            if (btn) btn.innerHTML = isMaximized
                ? '<svg width="12" height="12" viewBox="0 0 12 12"><rect x="2.5" y="0.5" width="8" height="8" rx="1" stroke="currentColor" stroke-width="1" fill="none"/><rect x="0.5" y="2.5" width="8" height="8" rx="1" stroke="currentColor" stroke-width="1" fill="none"/></svg>'
                : '<svg width="12" height="12" viewBox="0 0 12 12"><rect x="1" y="1" width="10" height="10" rx="1.5" stroke="currentColor" stroke-width="1" fill="none"/></svg>';
        });
    }
})();

// ============ TOAST ============
function toast(msg, type = 'info') {
    const c = document.getElementById('toast-container');
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    const icons = {
        success: '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="#10b981" stroke-width="1.5"/><path d="M5 8L7 10L11 6" stroke="#10b981" stroke-width="1.5" stroke-linecap="round"/></svg>',
        error: '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="#ef4444" stroke-width="1.5"/><path d="M5.5 5.5L10.5 10.5M10.5 5.5L5.5 10.5" stroke="#ef4444" stroke-width="1.5" stroke-linecap="round"/></svg>',
        info: '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="#06b6d4" stroke-width="1.5"/><path d="M8 7V11M8 5.5V5" stroke="#06b6d4" stroke-width="1.5" stroke-linecap="round"/></svg>'
    };
    t.innerHTML = `${icons[type] || icons.info}<span>${msg}</span>`;
    c.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateX(80px)'; t.style.transition = 'all .3s'; setTimeout(() => t.remove(), 300); }, 3000);
}

// ============ AUTH ============
function switchAuth(panel) {
    document.querySelectorAll('.auth-panel').forEach(p => p.classList.remove('active'));
    document.getElementById(panel + '-panel').classList.add('active');
    document.querySelectorAll('.field-error').forEach(e => e.classList.add('hidden'));
}

async function handleLogin(e) {
    e.preventDefault();
    const btn = document.getElementById('login-btn');
    btn.classList.add('loading'); btn.querySelector('span').textContent = 'Signing in...';
    try {
        const fd = new URLSearchParams();
        fd.append('username', document.getElementById('login-email').value);
        fd.append('password', document.getElementById('login-password').value);
        const res = await fetch(`${API}/api/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: fd });
        if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Login failed'); }
        const data = await res.json();
        token = data.access_token;
        localStorage.setItem('token', token);
        toast('Welcome back!', 'success');
        enterDashboard();
    } catch (err) {
        const el = document.getElementById('login-error');
        el.textContent = err.message; el.classList.remove('hidden');
        toast(err.message, 'error');
    } finally { btn.classList.remove('loading'); btn.querySelector('span').textContent = 'Sign In'; }
}

async function handleRegister(e) {
    e.preventDefault();
    const btn = document.getElementById('reg-btn');
    btn.classList.add('loading'); btn.querySelector('span').textContent = 'Creating...';
    try {
        const res = await fetch(`${API}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: document.getElementById('reg-email').value, password: document.getElementById('reg-password').value, full_name: document.getElementById('reg-name').value })
        });
        if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Failed'); }
        toast('Account created! Please sign in.', 'success');
        document.getElementById('login-email').value = document.getElementById('reg-email').value;
        switchAuth('login');
    } catch (err) {
        const el = document.getElementById('register-error');
        el.textContent = err.message; el.classList.remove('hidden');
        toast(err.message, 'error');
    } finally { btn.classList.remove('loading'); btn.querySelector('span').textContent = 'Create Account'; }
}

function logout() {
    token = null; localStorage.removeItem('token');
    stopRefresh();
    document.getElementById('dashboard-screen').classList.remove('active');
    document.getElementById('auth-screen').style.display = 'flex';
    toast('Signed out', 'info');
}

// ============ API ============
async function apiGet(path) {
    const r = await fetch(`${API}${path}`, { headers: { 'Authorization': `Bearer ${token}` } });
    if (r.status === 401) { logout(); throw new Error('Session expired'); }
    if (!r.ok) throw new Error(`API error ${r.status}`);
    return r.json();
}
async function apiPost(path, body) {
    const r = await fetch(`${API}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` }, body: JSON.stringify(body) });
    if (r.status === 401) { logout(); throw new Error('Session expired'); }
    if (!r.ok) throw new Error(`API error ${r.status}`);
    return r.json();
}

// ============ DASHBOARD ============
let ws = null;

function enterDashboard() {
    document.getElementById('auth-screen').style.display = 'none';
    document.getElementById('dashboard-screen').classList.add('active');
    loadUserInfo();
    loadDashboard();
    startRefresh();
    connectWebSocket();
}

function connectWebSocket() {
    if (ws) ws.close();
    const wsUrl = `ws://${window.location.host}/ws?token=${token}`;
    ws = new WebSocket(wsUrl);
    ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.type === 'cost_update') {
            toast(`New call: ${msg.data.model} — $${msg.data.cost.toFixed(6)}`, 'info');
            if (document.getElementById('section-overview').classList.contains('active')) loadDashboard(true);
        } else if (msg.type === 'alert') {
            toast(msg.data.message, 'error');
            loadAlertBadge();
        }
    };
    ws.onclose = () => setTimeout(connectWebSocket, 5000);
}

async function loadUserInfo() {
    try {
        const u = await apiGet('/api/auth/me');
        document.getElementById('user-name').textContent = u.full_name || 'User';
        document.getElementById('user-email').textContent = u.email;
        document.getElementById('user-avatar').textContent = (u.full_name || u.email)[0].toUpperCase();
    } catch(e) {}
}

function startRefresh() { stopRefresh(); refreshTimer = setInterval(() => { if (document.getElementById('section-overview').classList.contains('active')) loadDashboard(true); }, 30000); }
function stopRefresh() { if (refreshTimer) clearInterval(refreshTimer); }

async function loadDashboard(silent) {
    try {
        const d = await apiGet('/api/dashboard');
        setVal('stat-today', d.total_cost_today, '$');
        setVal('stat-week', d.total_cost_week, '$');
        setVal('stat-month', d.total_cost_month, '$');
        document.getElementById('stat-calls').textContent = d.total_calls_today.toLocaleString();
        document.getElementById('stat-tokens').textContent = fmtNum(d.total_tokens_today);
        document.getElementById('stat-latency').textContent = d.avg_latency_today.toFixed(0) + 'ms';
        document.getElementById('stat-errors').textContent = d.error_rate_today.toFixed(1) + '%';
        document.getElementById('stat-cache').textContent = d.cache_hit_rate.toFixed(1) + '%';
        chartDaily(d.daily_costs); chartHourly(d.hourly_costs_today);
        chartModel(d.model_breakdown); chartProvider(d.provider_breakdown);
        loadForecast(); loadAlertBadge();
        if (!silent) toast('Dashboard loaded', 'success');
    } catch (e) { if (!silent) toast('Failed to load', 'error'); }
}

function setVal(id, target, p) {
    const el = document.getElementById(id);
    const cur = parseFloat(el.textContent.replace(/[^0-9.]/g, '')) || 0;
    const diff = target - cur, steps = 18, step = diff / steps;
    let i = 0;
    const iv = setInterval(() => { i++; el.textContent = p + (cur + step * i).toFixed(4); if (i >= steps) { el.textContent = p + target.toFixed(4); clearInterval(iv); } }, 18);
}
function fmtNum(n) { return n >= 1e6 ? (n/1e6).toFixed(1)+'M' : n >= 1e3 ? (n/1e3).toFixed(1)+'K' : n.toLocaleString(); }

async function loadForecast() {
    try {
        const d = await apiGet('/api/forecast');
        document.getElementById('forecast-projected').textContent = '$' + d.projected_monthly_cost.toFixed(2);
        document.getElementById('forecast-daily').textContent = '$' + d.average_daily_cost.toFixed(4);
        document.getElementById('forecast-days').textContent = d.days_remaining;
        document.getElementById('forecast-spent').textContent = '$' + d.total_spent_so_far.toFixed(2);
        const b = document.getElementById('forecast-trend-badge');
        b.textContent = d.trend[0].toUpperCase() + d.trend.slice(1);
        b.className = 'card-badge ' + (d.trend === 'increasing' ? '' : d.trend === 'decreasing' ? 'green' : '');
        if (d.trend === 'increasing') { b.style.background = 'rgba(239,68,68,.1)'; b.style.color = '#ef4444'; }
        else if (d.trend === 'decreasing') { b.style.background = 'rgba(16,185,129,.1)'; b.style.color = '#10b981'; }
        else { b.style.background = ''; b.style.color = ''; }
    } catch(e) {}
}

// ============ CHARTS ============
const cDef = { responsive: true, maintainAspectRatio: true, plugins: { legend: { display: false } }, animation: { duration: 700 } };

function chartDaily(data) {
    if (charts.d) charts.d.destroy();
    const ctx = document.getElementById('dailyChart').getContext('2d');
    const g = ctx.createLinearGradient(0, 0, 0, 240); g.addColorStop(0, 'rgba(99,102,241,.25)'); g.addColorStop(1, 'rgba(99,102,241,0)');
    charts.d = new Chart(ctx, { type: 'bar', data: { labels: data.map(d => d.date.slice(5)), datasets: [{ data: data.map(d => d.total_cost), backgroundColor: g, borderColor: 'rgba(99,102,241,.7)', borderWidth: 1, borderRadius: 5, borderSkipped: false }] }, options: { ...cDef, scales: { x: { ticks: { color: '#55556a', font: { size: 10 } }, grid: { display: false }, border: { display: false } }, y: { ticks: { color: '#55556a', callback: v => '$'+v, font: { size: 10 } }, grid: { color: 'rgba(255,255,255,.03)' }, border: { display: false } } } } });
}

function chartHourly(data) {
    if (charts.h) charts.h.destroy();
    const ctx = document.getElementById('hourlyChart').getContext('2d');
    const g = ctx.createLinearGradient(0, 0, 0, 240); g.addColorStop(0, 'rgba(6,182,212,.2)'); g.addColorStop(1, 'rgba(6,182,212,0)');
    const hrs = Array.from({length:24},(_,i)=>i), map = Object.fromEntries(data.map(d=>[d.hour,d.total_cost]));
    charts.h = new Chart(ctx, { type: 'line', data: { labels: hrs.map(h=>h+':00'), datasets: [{ data: hrs.map(h=>map[h]||0), borderColor: '#06b6d4', backgroundColor: g, fill: true, tension: .4, pointRadius: 3, pointBackgroundColor: '#06b6d4', pointBorderColor: '#08080d', pointBorderWidth: 2, pointHoverRadius: 6 }] }, options: { ...cDef, scales: { x: { ticks: { color: '#55556a', font: { size: 10 } }, grid: { display: false }, border: { display: false } }, y: { ticks: { color: '#55556a', callback: v => '$'+v, font: { size: 10 } }, grid: { color: 'rgba(255,255,255,.03)' }, border: { display: false } } } } });
}

function chartModel(data) {
    if (charts.m) charts.m.destroy();
    const cols = ['#6366f1','#8b5cf6','#06b6d4','#10b981','#f59e0b','#ef4444','#ec4899','#14b8a6'];
    charts.m = new Chart(document.getElementById('modelChart'), { type: 'doughnut', data: { labels: data.map(d=>d.model), datasets: [{ data: data.map(d=>d.total_cost), backgroundColor: cols.slice(0,data.length), borderWidth: 0, hoverOffset: 6 }] }, options: { ...cDef, cutout: '62%', plugins: { legend: { position: 'right', labels: { color: '#9494a8', font: { size: 11 }, padding: 6, boxWidth: 10, borderRadius: 3 } } } } });
}

function chartProvider(data) {
    if (charts.p) charts.p.destroy();
    const cols = { openai: '#10b981', groq: '#8b5cf6', google: '#3b82f6', anthropic: '#f59e0b', mistral: '#ec4899' };
    charts.p = new Chart(document.getElementById('providerChart'), { type: 'doughnut', data: { labels: data.map(d=>d.provider[0].toUpperCase()+d.provider.slice(1)), datasets: [{ data: data.map(d=>d.total_cost), backgroundColor: data.map(d=>cols[d.provider]||'#6b7280'), borderWidth: 0, hoverOffset: 6 }] }, options: { ...cDef, cutout: '62%', plugins: { legend: { position: 'right', labels: { color: '#9494a8', font: { size: 11 }, padding: 8, boxWidth: 10, borderRadius: 3 } } } } });
}

// ============ LOGS ============
function debounceLogs() { clearTimeout(logTimer); logTimer = setTimeout(() => loadLogs(), 300); }

async function loadLogs(page = 1) {
    let url = `/api/logs?page=${page}&page_size=20`;
    const p = document.getElementById('filter-provider').value;
    const s = document.getElementById('filter-status').value;
    const m = document.getElementById('filter-model')?.value || '';
    const pr = document.getElementById('filter-project')?.value || '';
    if (p) url += `&provider=${p}`; if (s) url += `&status=${s}`; if (m) url += `&model=${m}`; if (pr) url += `&project=${pr}`;
    try {
        const d = await apiGet(url);
        const tb = document.getElementById('logs-body');
        const em = document.getElementById('logs-empty');
        tb.innerHTML = ''; em.classList.toggle('hidden', d.logs.length > 0);
        d.logs.forEach(l => {
            const r = document.createElement('tr');
            r.innerHTML = `<td style="color:var(--text-2)">${new Date(l.created_at).toLocaleString()}</td><td style="text-transform:capitalize;font-weight:500">${l.provider}</td><td>${l.model}</td><td>${l.input_tokens.toLocaleString()}</td><td>${l.output_tokens.toLocaleString()}</td><td style="font-weight:600;color:var(--cyan)">$${l.cost.toFixed(6)}</td><td>${l.latency_ms.toFixed(0)}ms</td><td class="${l.status==='success'?'s-success':'s-error'}">${l.status==='success'?'✓':'✗'} ${l.status}</td><td class="${l.cache_hit?'cache-yes':'cache-no'}">${l.cache_hit?'HIT':'MISS'}</td>`;
            tb.appendChild(r);
        });
        pag(d.total_pages, d.page);
    } catch(e) {}
}

function pag(total, cur) {
    const c = document.getElementById('logs-pagination'); c.innerHTML = '';
    if (total <= 1) return;
    for (let i = 1; i <= Math.min(total, 10); i++) { const b = document.createElement('button'); b.textContent = i; b.className = i === cur ? 'active' : ''; b.onclick = () => loadLogs(i); c.appendChild(b); }
}

async function exportCSV() {
    try {
        const r = await fetch(`${API}/api/export?format=csv`, { headers: { 'Authorization': `Bearer ${token}` } });
        const blob = await r.blob(); const url = URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = `llm_costs_${new Date().toISOString().slice(0,10)}.csv`; a.click();
        URL.revokeObjectURL(url); toast('CSV exported', 'success');
    } catch(e) { toast('Export failed', 'error'); }
}

// ============ CALCULATOR ============
const PRICING = {
    openai: {'gpt-4o':{input:2.5,output:10},'gpt-4o-mini':{input:.15,output:.6},'gpt-4-turbo':{input:10,output:30},'gpt-4':{input:30,output:60},'gpt-3.5-turbo':{input:.5,output:1.5},'o1':{input:15,output:60},'o1-mini':{input:3,output:12}},
    groq: {'llama-3.3-70b-versatile':{input:.59,output:.79},'llama-3.1-8b-instant':{input:.05,output:.08},'mixtral-8x7b-32768':{input:.24,output:.24},'gemma2-9b-it':{input:.2,output:.2}},
    google: {'gemini-2.0-flash':{input:.1,output:.4},'gemini-2.0-flash-lite':{input:.075,output:.3},'gemini-1.5-pro':{input:1.25,output:5},'gemini-1.5-flash':{input:.075,output:.3}},
    anthropic: {'claude-sonnet-4-20250514':{input:3,output:15},'claude-3-5-sonnet-20241022':{input:3,output:15},'claude-3-5-haiku-20241022':{input:.8,output:4},'claude-3-opus-20240229':{input:15,output:75}},
    mistral: {'mistral-large-latest':{input:2,output:6},'mistral-small-latest':{input:.2,output:.6}}
};

function updateModelList() {
    const prov = document.getElementById('calc-provider').value;
    const sel = document.getElementById('calc-model');
    sel.innerHTML = Object.keys(PRICING[prov]||{}).map(m=>`<option value="${m}">${m}</option>`).join('');
    calculateCost();
}
function calculateCost() {
    const prov = document.getElementById('calc-provider').value, model = document.getElementById('calc-model').value;
    const inp = parseInt(document.getElementById('calc-input').value)||0, out = parseInt(document.getElementById('calc-output').value)||0, calls = parseInt(document.getElementById('calc-calls').value)||1;
    const pr = PRICING[prov]?.[model]||{input:1,output:3};
    const ic = (inp/1e6)*pr.input, oc = (out/1e6)*pr.output, pc = ic+oc, tot = pc*calls;
    document.getElementById('calc-total').textContent = '$'+tot.toFixed(6);
    document.getElementById('calc-per-call').textContent = '$'+pc.toFixed(6);
    document.getElementById('calc-input-cost').textContent = '$'+(ic*calls).toFixed(6);
    document.getElementById('calc-output-cost').textContent = '$'+(oc*calls).toFixed(6);
    document.getElementById('calc-input-rate').textContent = '$'+pr.input.toFixed(2);
    document.getElementById('calc-output-rate').textContent = '$'+pr.output.toFixed(2);
}

// ============ COMPARISON ============
async function loadComparison() {
    try {
        const d = await apiGet('/api/comparison');
        const tb = document.getElementById('comparison-body'), em = document.getElementById('comparison-empty');
        tb.innerHTML = ''; em.classList.toggle('hidden', d.length > 0);
        d.forEach(r => { const tr = document.createElement('tr'); tr.innerHTML = `<td style="font-weight:500">${r.model}</td><td style="text-transform:capitalize">${r.provider}</td><td style="font-weight:600;color:var(--cyan)">$${r.avg_cost_per_call.toFixed(6)}</td><td>${r.avg_latency.toFixed(0)}ms</td><td>${r.total_calls.toLocaleString()}</td><td>${fmtNum(r.total_tokens)}</td><td class="${r.success_rate>=95?'s-success':'s-error'}">${r.success_rate}%</td>`; tb.appendChild(tr); });
    } catch(e) {}
}

// ============ BUDGET ============
async function loadBudget() {
    try { const d = await apiGet('/api/budget'); document.getElementById('budget-daily').value = d.daily_limit||''; document.getElementById('budget-monthly').value = d.monthly_limit||''; document.getElementById('budget-email').value = d.alert_email||''; document.getElementById('budget-slack').value = d.alert_slack_webhook||''; } catch(e) {}
}
async function saveBudget() {
    try { await apiPost('/api/budget', { daily_limit: parseFloat(document.getElementById('budget-daily').value)||0, monthly_limit: parseFloat(document.getElementById('budget-monthly').value)||0, alert_email: document.getElementById('budget-email').value||null, alert_slack_webhook: document.getElementById('budget-slack').value||null }); toast('Budget saved', 'success'); } catch(e) { toast('Failed to save', 'error'); }
}

// ============ ALERTS ============
async function loadAlertBadge() {
    try { const d = await apiGet('/api/alerts?unread_only=true'); const b = document.getElementById('alert-badge'); if (d.length > 0) { b.textContent = d.length; b.classList.remove('hidden'); } else b.classList.add('hidden'); } catch(e) {}
}
async function loadAlerts() {
    try {
        const d = await apiGet('/api/alerts');
        const c = document.getElementById('alerts-list');
        if (!d.length) { c.innerHTML = '<div class="empty-state"><p>No alerts yet</p></div>'; return; }
        c.innerHTML = d.map(a => `<div class="alert-item ${!a.is_read?'unread':''}"><span class="alert-msg">${a.message}</span><span class="alert-time">${new Date(a.created_at).toLocaleString()}</span></div>`).join('');
    } catch(e) {}
}

// ============ NAVIGATION ============
const titles = {
    overview: ['Overview', 'Real-time spending dashboard'],
    logs: ['API Logs', 'Detailed history of all tracked calls'],
    calculator: ['Cost Calculator', 'Estimate costs before making calls'],
    comparison: ['Model Comparison', 'Compare cost, latency & performance'],
    budget: ['Budget & Alerts', 'Set spending limits & notifications'],
    alerts: ['Alerts', 'Budget warnings & system notifications'],
    optimize: ['Optimizer', 'AI-powered cost reduction suggestions'],
    pricing: ['Model Pricing', 'Current pricing per 1M tokens'],
    plans: ['Plans', 'Choose a plan that fits your usage'],
    'api-ref': ['API Reference', 'Integrate cost tracking into your app'],
    settings: ['Settings', 'Manage your account']
};

function showSection(name, el) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.sidebar-link').forEach(l => l.classList.remove('active'));
    document.getElementById('section-' + name).classList.add('active');
    if (el) el.classList.add('active');
    const t = titles[name] || ['', ''];
    document.querySelector('.page-title h1').textContent = t[0];
    document.querySelector('.page-title p').textContent = t[1];
    if (name === 'logs') loadLogs();
    if (name === 'comparison') loadComparison();
    if (name === 'budget') loadBudget();
    if (name === 'alerts') loadAlerts();
    if (name === 'calculator') updateModelList();
    if (name === 'optimize') loadOptimizer();
    if (name === 'pricing') renderPricing();
    if (name === 'plans') loadPlans();
    if (name === 'settings') loadSettings();
    document.getElementById('sidebar').classList.remove('open');
}

function toggleSidebar() { document.getElementById('sidebar').classList.toggle('open'); }

// ============ PRICING ============
function renderPricing() {
    const grid = document.getElementById('pricing-grid');
    const colors = { openai: '#10b981', groq: '#8b5cf6', google: '#3b82f6', anthropic: '#f59e0b', mistral: '#ec4899' };
    const provNames = { openai: 'OpenAI', groq: 'Groq', google: 'Google AI Studio', anthropic: 'Anthropic', mistral: 'Mistral' };

    grid.innerHTML = Object.entries(PRICING).map(([prov, models]) => `
        <div class="pricing-provider">
            <h4><span class="prov-dot" style="background:${colors[prov]}"></span>${provNames[prov] || prov}</h4>
            ${Object.entries(models).map(([name, p]) => `
                <div class="pricing-model">
                    <span class="pm-name">${name}</span>
                    <span class="pm-rates">In: <span>$${p.input.toFixed(2)}</span> Out: <span>$${p.output.toFixed(2)}</span></span>
                </div>
            `).join('')}
        </div>
    `).join('');
}

// ============ PLANS / SUBSCRIPTION ============
async function loadPlans() {
    try {
        const [plans, cur] = await Promise.all([apiGet('/api/plans'), apiGet('/api/plan')]);
        renderPlans(plans, cur);
        renderPlanBanner(cur);
    } catch(e) { toast('Failed to load plans', 'error'); }
}

function fmtCount(n) {
    if (n >= 1e9) return (n/1e9).toFixed(1) + 'B';
    if (n >= 1e6) return (n/1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n/1e3).toFixed(1) + 'K';
    return n.toLocaleString();
}

function usageBar(cur) {
    const callsPct = cur.calls_limit ? Math.min(100, (cur.calls_used / cur.calls_limit) * 100) : 0;
    const tokensPct = cur.tokens_limit ? Math.min(100, (cur.tokens_used / cur.tokens_limit) * 100) : 0;
    return `
        <div class="usage-block">
            <div class="usage-label"><span>Calls</span><span>${fmtCount(cur.calls_used)} / ${fmtCount(cur.calls_limit)}</span></div>
            <div class="usage-track"><div class="usage-fill ${callsPct >= 90 ? 'danger' : ''}" style="width:${callsPct}%"></div></div>
        </div>
        <div class="usage-block" style="margin-top:12px">
            <div class="usage-label"><span>Tokens</span><span>${fmtCount(cur.tokens_used)} / ${fmtCount(cur.tokens_limit)}</span></div>
            <div class="usage-track"><div class="usage-fill ${tokensPct >= 90 ? 'danger' : ''}" style="width:${tokensPct}%"></div></div>
        </div>
    `;
}

function renderPlanBanner(cur) {
    const el = document.getElementById('plan-banner');
    const renew = cur.renews_at ? new Date(cur.renews_at).toLocaleDateString() : '';
    el.innerHTML = `
        <div class="plan-banner-inner">
            <div>
                <div class="plan-banner-label">Current Plan</div>
                <div class="plan-banner-name">${cur.name}</div>
            </div>
            <div style="flex:1;min-width:200px;max-width:340px">${usageBar(cur)}</div>
            ${renew ? `<div class="plan-banner-renew">Renews ${renew}</div>` : ''}
        </div>
    `;
}

function renderPlans(plans, cur) {
    const grid = document.getElementById('plans-grid');
    const theme = { free: 'free', pro: 'pro', business: 'business' };
    grid.innerHTML = plans.map(p => {
        const isCurrent = p.id === cur.plan;
        const popular = p.id === 'pro';
        return `
            <div class="plan-card ${theme[p.id] || ''} ${isCurrent ? 'current' : ''} ${popular ? 'popular' : ''}" style="--accent:${p.id==='pro'?'var(--cyan)':p.id==='business'?'var(--purple)':'var(--green)'}">
                <div class="plan-head">
                    <h3>${p.name}</h3>
                    ${popular ? '<span class="plan-flag">POPULAR</span>' : ''}
                </div>
                <div class="plan-price">
                    <span class="plan-price-currency">$${p.price_monthly === 0 ? '0' : p.price_monthly}</span>
                    <span class="plan-price-period">/month</span>
                </div>
                <div class="plan-sub">${fmtCount(p.calls_per_month)} calls · ${fmtCount(p.tokens_per_month)} tokens</div>
                <ul class="plan-features">
                    ${p.features.map(f => `<li><span class="plan-check">✓</span>${f}</li>`).join('')}
                </ul>
                <button class="btn-plan ${isCurrent ? 'current' : ''}" ${isCurrent ? 'disabled' : ''} data-plan="${p.id}" onclick="choosePlan('${p.id}', this)">
                    ${isCurrent ? 'Your Current Plan' : p.price_monthly === 0 ? 'Start Free' : `Upgrade to ${p.name}`}
                </button>
            </div>
        `;
    }).join('');
}

async function choosePlan(planId, btn) {
    if (btn.disabled) return;
    btn.classList.add('loading'); btn.textContent = 'Processing...';
    try {
        const res = await fetch(`${API}/api/subscribe`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ plan: planId })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed');
        if (data.checkout_url) {
            window.location.href = data.checkout_url;
        } else {
            toast(data.message || 'Plan updated', 'success');
            loadPlans();
        }
    } catch(e) {
        toast(e.message, 'error');
        btn.classList.remove('loading');
        btn.textContent = planId === 'free' ? 'Start Free' : 'Upgrade';
    }
}

// ============ COPY CODE ============
function copyCode(btn) {
    const pre = btn.closest('.code-block').querySelector('pre');
    navigator.clipboard.writeText(pre.textContent).then(() => {
        btn.textContent = 'Copied!';
        btn.classList.add('copied');
        setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
    });
}

// ============ SETTINGS ============
async function loadSettings() {
    try {
        const u = await apiGet('/api/auth/me');
        document.getElementById('settings-name').value = u.full_name || '';
        document.getElementById('settings-email').value = u.email;
    } catch(e) {}
}

// ============ OPTIMIZER ============
async function loadOptimizer() {
    try {
        const d = await apiGet('/api/optimize');

        const statsHtml = `
            <div class="stat-card">
                <div class="stat-label">30-Day Spend</div>
                <div class="stat-value cyan">$${d.total_cost_30d.toFixed(4)}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Potential Savings</div>
                <div class="stat-value green">$${d.potential_savings.toFixed(4)}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total Calls</div>
                <div class="stat-value">${d.total_calls_30d.toLocaleString()}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Models Used</div>
                <div class="stat-value purple">${d.models_used}</div>
            </div>
        `;
        document.getElementById('optimize-stats').innerHTML = statsHtml;

        const sugContainer = document.getElementById('optimize-suggestions');
        if (!d.suggestions.length) {
            sugContainer.innerHTML = '<div class="empty-state"><p>No suggestions yet — start tracking API calls</p></div>';
            return;
        }

        const typeColors = { optimization: 'var(--green)', performance: 'var(--orange)', caching: 'var(--cyan)', summary: 'var(--text-2)', info: 'var(--text-3)' };
        const typeIcons = { optimization: '💰', performance: '⚡', caching: '🗄️', summary: '📊', info: 'ℹ️' };

        sugContainer.innerHTML = d.suggestions.map(s => `
            <div class="card" style="margin-bottom:12px;border-left:3px solid ${typeColors[s.type] || 'var(--border)'}">
                <div style="display:flex;align-items:flex-start;gap:12px">
                    <span style="font-size:20px">${typeIcons[s.type] || '💡'}</span>
                    <div style="flex:1">
                        <p style="margin:0;font-weight:500">${s.message}</p>
                        ${s.estimated_saving ? `<p style="margin:6px 0 0;color:var(--green);font-size:13px;font-weight:600">Save $${s.estimated_saving.toFixed(4)}/month</p>` : ''}
                    </div>
                    <span style="padding:4px 10px;background:rgba(255,255,255,.05);border-radius:12px;font-size:11px;font-weight:600;color:${typeColors[s.type]}">${s.type.toUpperCase()}</span>
                </div>
            </div>
        `).join('');
    } catch(e) {
        document.getElementById('optimize-suggestions').innerHTML = '<div class="empty-state"><p>Track some API calls first to see optimization suggestions</p></div>';
    }
}

// ============ INIT ============
document.addEventListener('DOMContentLoaded', () => { if (token) enterDashboard(); });
