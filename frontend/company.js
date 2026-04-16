'use strict';

/* ============================================================
   SIGNAL META — names, descriptions, severity, thresholds
   ============================================================ */
const SIGNAL_META = {
  F1: {
    name: 'AR Abnormal Growth',
    desc: 'Accounts receivable is growing significantly faster than revenue, suggesting potential channel stuffing or inflated sales recognition.',
    threshold: 'AR/Revenue ratio grows >30% YoY',
    severity: 'high',
  },
  F2: {
    name: 'Cash Flow Divergence',
    desc: 'Net profit is positive but operating cash flow is negative, indicating earnings may not be converting to real cash.',
    threshold: 'Net profit > 0 AND operating cash flow < 0',
    severity: 'high',
  },
  F3: {
    name: 'High Leverage',
    desc: 'Debt-to-assets ratio exceeds 70% for two consecutive years, indicating heavy reliance on debt financing.',
    threshold: 'Total debt / Total assets > 70% for 2 years',
    severity: 'medium',
  },
  F4: {
    name: 'Margin Decline',
    desc: 'Net profit margin has dropped more than 10 percentage points year-over-year, indicating deteriorating profitability.',
    threshold: 'Net margin drops >10pp YoY',
    severity: 'medium',
  },
  G1: {
    name: 'Pledge Ratio Alert',
    desc: 'Controlling shareholders have pledged a significant portion of their shares, creating governance and solvency risk.',
    threshold: 'Pledge ratio > 50%',
    severity: 'medium',
  },
  G3: {
    name: 'Board Independence',
    desc: 'Independent directors constitute less than one-third of the board, potentially weakening oversight.',
    threshold: 'Independent directors < 33% of board',
    severity: 'low',
  },
};

/* ============================================================
   STATE
   ============================================================ */
const state = {
  market: '',
  code:   '',
  data:   null,
  usedMock: false,
  reportLoading: false,
};

/* ============================================================
   MOCK DATA
   ============================================================ */
const MOCK_COMPANY = {
  'CN:600519': {
    company_id: 'CN:600519',
    market: 'CN',
    code: '600519',
    name: '贵州茅台',
    industry: '食品饮料',
    status: 'active',
    summary: {
      total_rules: 6,
      triggered_count: 0,
      status_counts: { triggered: 0, ok: 5, not_available: 1 },
      snapshot_tier: 'real_financial_available',
    },
    financial_signals: [
      {
        signal_id: 'F1', triggered: false, status: 'ok',
        message: 'AR-to-revenue ratio is stable. No abnormal growth detected.',
        values: { curr_ar_ratio: '0.042', prev_ar_ratio: '0.039', change: '+7.7%' },
        year: 2024,
      },
      {
        signal_id: 'F2', triggered: false, status: 'ok',
        message: 'Operating cash flow is strongly positive relative to net profit.',
        values: { net_profit: '¥74.7B', operating_cash_flow: '¥82.1B', ratio: '1.10' },
        year: 2024,
      },
      {
        signal_id: 'F3', triggered: false, status: 'ok',
        message: 'Debt-to-assets ratio is well below the 70% threshold.',
        values: { debt_ratio_curr: '17.2%', debt_ratio_prev: '16.8%' },
        year: 2024,
      },
      {
        signal_id: 'F4', triggered: false, status: 'ok',
        message: 'Net profit margin is stable year-over-year.',
        values: { margin_curr: '48.3%', margin_prev: '49.1%', change: '-0.8pp' },
        year: 2024,
      },
    ],
    governance_signals: [
      {
        signal_id: 'G1', triggered: false, status: 'ok',
        message: 'Controlling shareholder pledge ratio is low.',
        values: { pledge_ratio: '0.0%' },
        year: 2024,
      },
      {
        signal_id: 'G3', triggered: false, status: 'not_available',
        message: 'Board composition data not available.',
        values: {},
        year: 2024,
      },
    ],
  },
  'TW:2330': {
    company_id: 'TW:2330',
    market: 'TW',
    code: '2330',
    name: '台積電',
    industry: '半導體',
    status: 'active',
    summary: {
      total_rules: 6,
      triggered_count: 1,
      status_counts: { triggered: 1, ok: 4, not_available: 1 },
      snapshot_tier: 'real_financial_available',
    },
    financial_signals: [
      {
        signal_id: 'F1', triggered: true, status: 'triggered',
        message: 'AR-to-revenue ratio grew 38.2% YoY, exceeding the 30% trigger threshold.',
        values: { curr_ar_ratio: '0.118', prev_ar_ratio: '0.085', change: '+38.2%' },
        year: 2024,
      },
      {
        signal_id: 'F2', triggered: false, status: 'ok',
        message: 'Operating cash flow remains strongly positive.',
        values: { net_profit: 'NT$1.17T', operating_cash_flow: 'NT$1.34T', ratio: '1.14' },
        year: 2024,
      },
      {
        signal_id: 'F3', triggered: false, status: 'ok',
        message: 'Leverage is within acceptable range.',
        values: { debt_ratio_curr: '24.1%', debt_ratio_prev: '23.4%' },
        year: 2024,
      },
      {
        signal_id: 'F4', triggered: false, status: 'ok',
        message: 'Net profit margin improved year-over-year.',
        values: { margin_curr: '39.0%', margin_prev: '36.5%', change: '+2.5pp' },
        year: 2024,
      },
    ],
    governance_signals: [
      {
        signal_id: 'G1', triggered: false, status: 'ok',
        message: 'No major shareholder pledge detected.',
        values: { pledge_ratio: '0.0%' },
        year: 2024,
      },
      {
        signal_id: 'G3', triggered: false, status: 'not_available',
        message: 'Board composition data not available.',
        values: {},
        year: 2024,
      },
    ],
  },
};

/* ============================================================
   ENTRY POINT
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {
  parseUrlParams();
  checkHealth();
  if (state.market && state.code) {
    loadCompany();
    bindEvents();
  } else {
    renderFatalError('Missing URL parameters. Expected: ?market=CN&code=600519');
  }
});

function parseUrlParams() {
  const p = new URLSearchParams(window.location.search);
  state.market = (p.get('market') || '').toUpperCase();
  state.code   = p.get('code') || '';
}

/* ============================================================
   HEALTH CHECK
   ============================================================ */
async function checkHealth() {
  const dot   = document.getElementById('healthDot');
  const label = document.getElementById('healthLabel');
  try {
    await API.health();
    dot.className   = 'health-dot online';
    label.textContent = 'API Connected';
  } catch {
    dot.className   = 'health-dot offline';
    label.textContent = 'API Offline';
  }
}

/* ============================================================
   LOAD COMPANY DATA
   ============================================================ */
async function loadCompany(fresh = false) {
  setLoadingUI(true);

  try {
    let data;
    try {
      data = await API.getSignals(state.market, state.code, fresh);
      state.usedMock = false;
    } catch (err) {
      console.warn('[company] API unreachable, trying mock:', err.message);
      const key = `${state.market}:${state.code}`;
      data = MOCK_COMPANY[key];
      if (!data) throw new Error(`No mock data for ${key}`);
      state.usedMock = true;
      showToast('Backend not running — showing demo data', 'warning');
    }

    state.data = data;
    renderPage(data);
    updateLastUpdated();
  } catch (err) {
    renderFatalError(err.message);
  } finally {
    setLoadingUI(false);
  }
}

/* ============================================================
   RENDER PAGE
   ============================================================ */
function renderPage(data) {
  renderTopbarId(data);
  renderInfoCard(data);
  renderSummaryCards(data);
  renderSignalSection('financialSignals',  'finMeta',  data.financial_signals  || []);
  renderSignalSection('governanceSignals', 'govMeta',  data.governance_signals || []);
}

/* ---------- Topbar ID strip ---------- */
function renderTopbarId(data) {
  const el  = document.getElementById('coTopbarId');
  const mkt = (data.market || '').toLowerCase();
  el.innerHTML = `
    <span class="badge badge-market badge-market-${mkt}">${data.market}</span>
    <span class="co-topbar-name">${esc(data.name || data.code)}</span>
    <span class="co-topbar-code">${esc(data.code)}</span>`;
  document.title = `${data.name || data.code} — FinSignal`;
}

/* ---------- Company info card ---------- */
function renderInfoCard(data) {
  const card = document.getElementById('coInfoCard');
  card.classList.remove('skeleton-wrap');

  const mkt      = (data.market || '').toLowerCase();
  const tier     = data.summary?.snapshot_tier ?? '';
  const avatarTx = (data.code || '').slice(0, 3);

  card.innerHTML = `
    <div class="co-info-main">
      <div class="co-avatar">${esc(avatarTx)}</div>
      <div class="co-info-text">
        <div class="co-name">${esc(data.name || '—')}</div>
        <div class="co-meta-row">
          <span class="badge badge-market badge-market-${mkt}">${data.market}</span>
          <span class="co-code-mono">${esc(data.code)}</span>
          ${data.industry ? `<span class="co-separator">·</span><span class="co-industry">${esc(data.industry)}</span>` : ''}
          ${data.status   ? `<span class="co-separator">·</span><span class="co-industry">${esc(data.status)}</span>` : ''}
        </div>
      </div>
    </div>
    <div class="co-info-aside">
      <span class="tier-badge ${tierClass(tier)}">${tierLabel(tier)}</span>
      ${state.usedMock ? '<span class="badge badge-na">Demo Data</span>' : ''}
    </div>`;
}

/* ---------- Summary cards ---------- */
function renderSummaryCards(data) {
  const s    = data.summary || {};
  const tier = s.snapshot_tier ?? '';
  const sc   = s.status_counts || {};
  const cnt  = s.triggered_count ?? 0;

  const container = document.getElementById('summaryCards');
  container.innerHTML = `
    <div class="scard">
      <div class="scard-icon scard-icon--total">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="9 11 12 14 22 4"></polyline>
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
        </svg>
      </div>
      <div class="scard-body">
        <div class="scard-value">${s.total_rules ?? '—'}</div>
        <div class="scard-label">Rules Evaluated</div>
      </div>
    </div>

    <div class="scard ${cnt > 0 ? 'scard--alert' : ''}">
      <div class="scard-icon scard-icon--signal">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
          <line x1="12" y1="9" x2="12" y2="13"></line>
          <line x1="12" y1="17" x2="12.01" y2="17"></line>
        </svg>
      </div>
      <div class="scard-body">
        <div class="scard-value">${cnt}</div>
        <div class="scard-label">Triggered Signals</div>
      </div>
      ${cnt > 0 ? `<div class="scard-note">${cnt} rule${cnt > 1 ? 's' : ''} require attention</div>` : ''}
    </div>

    <div class="scard">
      <div class="scard-icon scard-icon--tier">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
          <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
          <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
        </svg>
      </div>
      <div class="scard-body">
        <div class="scard-value"><span class="tier-badge ${tierClass(tier)}">${tierLabel(tier)}</span></div>
        <div class="scard-label">Data Tier</div>
      </div>
    </div>

    <div class="scard">
      <div class="scard-icon scard-icon--status">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
      </div>
      <div class="scard-body">
        <div class="scard-value">${s.total_rules ?? '—'}</div>
        <div class="scard-label">Rule Coverage</div>
        <div class="status-breakdown">
          <span class="status-dot-item">
            <span class="status-dot status-dot--triggered"></span>${sc.triggered ?? 0} triggered
          </span>
          <span class="status-dot-item">
            <span class="status-dot status-dot--ok"></span>${sc.ok ?? 0} ok
          </span>
          <span class="status-dot-item">
            <span class="status-dot status-dot--na"></span>${sc.not_available ?? 0} n/a
          </span>
        </div>
      </div>
    </div>`;
}

/* ---------- Signal section ---------- */
function renderSignalSection(containerId, metaId, signals) {
  const container = document.getElementById(containerId);
  const meta      = document.getElementById(metaId);

  const triggered = signals.filter(s => s.status === 'triggered' || s.triggered).length;
  meta.textContent = signals.length
    ? `${signals.length} rules · ${triggered} triggered`
    : '0 rules';

  if (!signals.length) {
    container.innerHTML = '<div class="sig-empty">No signals in this category</div>';
    return;
  }

  container.innerHTML = signals.map(sig => renderSigCard(sig)).join('');
}

function renderSigCard(sig) {
  const meta   = SIGNAL_META[sig.signal_id] || {};
  const status = sig.status || (sig.triggered ? 'triggered' : 'ok');
  const cardCls = status === 'triggered' ? 'sig-card--triggered'
                : status === 'not_available' ? 'sig-card--na'
                : 'sig-card--ok';

  const statusBadge = status === 'triggered'
    ? '<span class="badge badge-triggered">Triggered</span>'
    : status === 'not_available'
    ? '<span class="badge badge-na">N/A</span>'
    : '<span class="badge badge-ok">OK</span>';

  // Use severity from actual signal data, fall back to SIGNAL_META
  const severity = sig.severity || meta.severity;
  const sevBadge = severity
    ? `<span class="badge badge-${severity}">${severity.charAt(0).toUpperCase() + severity.slice(1)}</span>`
    : '';

  const message  = sig.message || meta.desc || '—';
  // Use threshold from actual signal data, fall back to SIGNAL_META
  const thresholdText = sig.threshold || meta.threshold;
  const threshold = thresholdText
    ? `<div class="sig-threshold">
        <span class="sig-threshold-label">Threshold:</span>
        <span class="sig-threshold-val">${esc(thresholdText)}</span>
       </div>`
    : '';

  // Field is 'value' from backend (not 'values')
  const valBlock = renderValues(sig.value !== undefined ? sig.value : sig.values);

  // Use signal name from data if available, fall back to SIGNAL_META
  const sigName = sig.name || meta.name || sig.signal_id;

  const footer = sig.year
    ? `<div class="sig-card-ft">
        <span class="sig-ft-item"><span class="sig-ft-label">Year:</span> ${sig.year}</span>
        ${sig.source ? `<span class="sig-ft-item"><span class="sig-ft-label">Source:</span> ${esc(sig.source)}</span>` : ''}
       </div>`
    : '';

  return `
    <div class="sig-card ${cardCls}">
      <div class="sig-card-hd">
        <div class="sig-card-badges">
          <span class="badge badge-rule">${esc(sig.signal_id)}</span>
          <span class="sig-name">${esc(sigName)}</span>
        </div>
        <div class="sig-card-status">
          ${sevBadge}
          ${statusBadge}
        </div>
      </div>
      <div class="sig-card-body">
        <p class="sig-message">${esc(message)}</p>
        ${threshold}
        ${valBlock}
      </div>
      ${footer}
    </div>`;
}

function renderValues(values) {
  if (!values || typeof values !== 'object') return '';

  // Array of time-series objects: [{period, field1, field2}, ...]
  if (Array.isArray(values)) {
    if (!values.length) return '';
    return renderTimeSeriesValue(values);
  }

  const entries = Object.entries(values);
  if (!entries.length) return '';

  // Object with one or more array values → render each
  const hasArray = entries.some(([, v]) => Array.isArray(v));
  if (hasArray) {
    return entries.map(([k, v]) => {
      if (Array.isArray(v)) {
        if (!v.length) return '';
        return renderTimeSeriesValue(v, k);
      }
      return `<div class="val-grid"><div class="val-item"><span class="val-key">${esc(k.replace(/_/g, ' '))}</span><span class="val-value">${esc(String(v ?? '—'))}</span></div></div>`;
    }).join('');
  }

  // Regular key-value grid
  return `<div class="val-grid">
    ${entries.map(([k, v]) => `
      <div class="val-item">
        <span class="val-key">${esc(k.replace(/_/g, ' '))}</span>
        <span class="val-value">${esc(String(v ?? '—'))}</span>
      </div>`).join('')}
  </div>`;
}

/* ============================================================
   TIME-SERIES VALUE RENDERER
   Renders [{period, key1, key2}, ...] as mini table + sparklines.
   ============================================================ */
function renderTimeSeriesValue(rows, label) {
  if (!rows.length) return '';
  const headers = Object.keys(rows[0]);
  const numericKeys = headers.filter(h => h !== 'period' && typeof rows[0][h] === 'number');

  // Build mini table
  const table = `
    <table class="val-mini-table">
      <thead><tr>${headers.map(h => `<th>${esc(h.replace(/_/g, ' '))}</th>`).join('')}</tr></thead>
      <tbody>
        ${rows.map(row => `<tr>${
          headers.map(h => {
            const v = row[h];
            const formatted = typeof v === 'number' ? formatBigNum(v) : esc(String(v ?? '—'));
            return `<td>${formatted}</td>`;
          }).join('')
        }</tr>`).join('')}
      </tbody>
    </table>`;

  // Generate sparkline canvases for numeric columns
  const sparklines = numericKeys.map(key => {
    const pts = rows.map(r => r[key]).filter(v => v != null);
    if (pts.length < 2) return '';
    const id = `spark_${Math.random().toString(36).slice(2)}`;
    // Schedule draw after DOM insert
    requestAnimationFrame(() => {
      const canvas = document.getElementById(id);
      if (canvas) drawSparkline(canvas, pts);
    });
    return `
      <div class="sparkline-wrap">
        <span class="sparkline-label">${esc(key.replace(/_/g, ' '))}</span>
        <canvas id="${id}" class="sparkline-canvas" width="180" height="36"></canvas>
      </div>`;
  }).join('');

  return table + (sparklines ? `<div class="sparkline-row">${sparklines}</div>` : '');
}

function drawSparkline(canvas, values) {
  const ctx  = canvas.getContext('2d');
  const W    = canvas.width;
  const H    = canvas.height;
  const pad  = 4;

  const min  = Math.min(...values);
  const max  = Math.max(...values);
  const range = max - min || 1;

  const toX = i => pad + (i / (values.length - 1)) * (W - pad * 2);
  const toY = v => H - pad - ((v - min) / range) * (H - pad * 2);

  ctx.clearRect(0, 0, W, H);

  // Fill area
  ctx.beginPath();
  ctx.moveTo(toX(0), H);
  values.forEach((v, i) => ctx.lineTo(toX(i), toY(v)));
  ctx.lineTo(toX(values.length - 1), H);
  ctx.closePath();
  ctx.fillStyle = 'rgba(30,64,175,0.08)';
  ctx.fill();

  // Line
  ctx.beginPath();
  values.forEach((v, i) => {
    if (i === 0) ctx.moveTo(toX(i), toY(v));
    else ctx.lineTo(toX(i), toY(v));
  });
  ctx.strokeStyle = '#1e40af';
  ctx.lineWidth   = 1.5;
  ctx.lineJoin    = 'round';
  ctx.stroke();

  // Dots
  values.forEach((v, i) => {
    ctx.beginPath();
    ctx.arc(toX(i), toY(v), 2.5, 0, Math.PI * 2);
    ctx.fillStyle = '#1e40af';
    ctx.fill();
  });

  // Last value dot highlight
  const last = values.length - 1;
  const isDown = values[last] < values[last - 1];
  ctx.beginPath();
  ctx.arc(toX(last), toY(values[last]), 3.5, 0, Math.PI * 2);
  ctx.fillStyle = isDown ? '#dc2626' : '#16a34a';
  ctx.fill();
}

function formatBigNum(n) {
  if (Math.abs(n) >= 1e12) return (n / 1e12).toFixed(2) + 'T';
  if (Math.abs(n) >= 1e9)  return (n / 1e9).toFixed(2)  + 'B';
  if (Math.abs(n) >= 1e6)  return (n / 1e6).toFixed(2)  + 'M';
  if (Math.abs(n) >= 1e4)  return (n / 1e4).toFixed(1)  + 'W';
  return n.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

/* ============================================================
   REPORT GENERATION
   ============================================================ */
async function generateReport() {
  if (state.reportLoading) return;
  state.reportLoading = true;

  const btn    = document.getElementById('generateReportBtn');
  const body   = document.getElementById('reportBody');
  const copy   = document.getElementById('copyReportBtn');

  btn.disabled = true;
  copy.style.display = 'none';

  body.innerHTML = `
    <div class="report-generating">
      <div class="loading-dots"><span></span><span></span><span></span></div>
      <span>Generating AI risk analysis…</span>
    </div>`;

  try {
    const result = await API.generateReport(state.market, state.code);
    const text   = result.report || result.content || result.text || JSON.stringify(result, null, 2);

    body.innerHTML = `<pre class="report-content">${esc(text)}</pre>`;
    copy.style.display = 'block';
    showToast('Report generated', 'success');
  } catch (err) {
    body.innerHTML = `
      <div class="report-placeholder">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        <p>Report generation failed</p>
        <span>${esc(err.message)}</span>
      </div>`;
    showToast('Failed to generate report', 'error');
  } finally {
    state.reportLoading = false;
    btn.disabled = false;
  }
}

function copyReport() {
  const el = document.querySelector('.report-content');
  if (!el) return;
  navigator.clipboard.writeText(el.textContent || '').then(() => {
    showToast('Copied to clipboard', 'success');
  });
}

/* ============================================================
   UI HELPERS
   ============================================================ */
function setLoadingUI(on) {
  const tag = document.getElementById('loadingTag');
  const btn = document.getElementById('refreshBtn');
  tag.style.display = on ? 'flex' : 'none';
  btn.classList.toggle('spinning', on);
}

function updateLastUpdated() {
  const el = document.getElementById('lastUpdated');
  if (el) el.textContent = `Updated: ${new Date().toLocaleTimeString()}`;
}

function renderFatalError(msg) {
  document.getElementById('coInfoCard').innerHTML = '';
  document.getElementById('summaryCards').innerHTML = '';
  document.getElementById('financialSignals').innerHTML = `
    <div class="error-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
      <p>Failed to load company</p>
      <span>${esc(msg)}</span>
      <button class="btn btn--primary" style="margin-top:8px" onclick="loadCompany()">Retry</button>
    </div>`;
  document.getElementById('governanceSignals').innerHTML = '';
}

function showToast(msg, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;
  toast.textContent = msg;
  container.appendChild(toast);
  requestAnimationFrame(() => {
    requestAnimationFrame(() => toast.classList.add('show'));
  });
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 260);
  }, 4000);
}

/* ============================================================
   EVENT BINDING
   ============================================================ */
function bindEvents() {
  document.getElementById('refreshBtn').addEventListener('click', () => loadCompany(true));
  document.getElementById('generateReportBtn').addEventListener('click', generateReport);
  document.getElementById('copyReportBtn').addEventListener('click', copyReport);
}

/* ============================================================
   UTILITY
   ============================================================ */
function tierClass(t) {
  if (t === 'real_financial_available')    return 'tier-full';
  if (t === 'partial_financial_available') return 'tier-partial';
  return 'tier-shell';
}

function tierLabel(t) {
  if (t === 'real_financial_available')    return 'Full Data';
  if (t === 'partial_financial_available') return 'Partial';
  return 'Shell Only';
}

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
