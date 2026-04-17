'use strict';

const state = {
  market:        '',
  code:          '',
  generating:    false,
  lastReportText: '',
};

/* ============================================================
   ENTRY POINT
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  bindEvents();

  // Pre-fill from URL ?market=CN&code=600519
  const p = new URLSearchParams(window.location.search);
  const market = p.get('market');
  const code   = p.get('code');
  if (market && code) {
    document.getElementById('marketSelect').value = market;
    document.getElementById('codeInput').value   = code;
    generateReport();
  }
});

async function checkHealth() {
  const dot = document.getElementById('healthDot');
  const lbl = document.getElementById('healthLabel');
  try {
    await API.health();
    dot.className = 'health-dot online';
    lbl.textContent = (window._currentLang === 'zh') ? 'API 已连接' : 'API Connected';
  } catch {
    dot.className = 'health-dot offline';
    lbl.textContent = (window._currentLang === 'zh') ? 'API 离线' : 'API Offline';
  }
}

/* ============================================================
   GENERATE
   ============================================================ */
async function generateReport() {
  const market = document.getElementById('marketSelect').value.trim().toUpperCase();
  const code   = document.getElementById('codeInput').value.trim();
  const errEl  = document.getElementById('formError');

  // Validation
  if (!market) {
    showFormError('Please select a market.');
    return;
  }
  if (!code) {
    showFormError('Please enter a company code.');
    return;
  }
  errEl.style.display = 'none';

  state.market = market;
  state.code   = code;
  state.generating = true;

  setLoading(true);
  showGenerating();

  try {
    const result = await API.generateReport(market, code);
    const text   = result.report_markdown || result.report || result.content || result.text
      || JSON.stringify(result, null, 2);

    state.lastReportText = text;
    renderReport(text, market, code, result);
    showToast('Report generated', 'success');
  } catch (err) {
    renderReportError(err.message);
    showToast('Failed to generate report', 'error');
  } finally {
    state.generating = false;
    setLoading(false);
  }
}

/* ============================================================
   RENDER
   ============================================================ */
function showGenerating() {
  document.getElementById('reportOutput').innerHTML = `
    <div class="loading-state" style="padding:var(--s8) var(--s6)">
      <div class="loading-dots"><span></span><span></span><span></span></div>
      <p>Generating AI risk analysis…</p>
      <span>This may take a few seconds</span>
    </div>`;
  document.getElementById('copyBtn').style.display = 'none';
  document.getElementById('reportMeta').textContent = '';
}

function renderReport(text, market, code, raw) {
  // Company meta card
  const metaCard = document.getElementById('metaCard');
  const metaBody = document.getElementById('metaCardBody');
  const mkt      = market.toLowerCase();

  // backend returns company_id, title; name comes from signal result or title
  const name      = raw.name || raw.company_name
    || (raw.title ? raw.title.replace(/\s*风险摘要.*/, '') : null)
    || code;
  const tier      = raw.snapshot_tier || raw.summary?.snapshot_tier || '';
  const triggered = raw.triggered_count ?? raw.summary?.triggered_count ?? null;

  metaBody.innerHTML = `
    <div class="rpt-meta-row">
      <span class="badge badge-market badge-market-${mkt}">${market}</span>
      <span style="font-size:var(--f-base);font-weight:700;color:var(--txt-1)">${esc(name)}</span>
      <code style="font-size:var(--f-sm);font-family:'SF Mono',monospace;color:var(--txt-3);background:var(--page-bg);padding:1px 6px;border-radius:3px;border:1px solid var(--border)">${esc(code)}</code>
    </div>
    <div style="display:flex;align-items:center;gap:var(--s3);margin-top:var(--s3);flex-wrap:wrap">
      ${tier ? `<span class="tier-badge ${tierClass(tier)}">${tierLabel(tier)}</span>` : ''}
      ${triggered !== null ? `<span class="trigger-count ${countClass(triggered)}" style="width:auto;padding:0 8px">${triggered} triggered</span>` : ''}
      <a href="company.html?market=${market}&code=${esc(code)}" class="btn btn--outline" style="height:28px;font-size:var(--f-xs)">
        View Detail →
      </a>
    </div>`;
  metaCard.style.display = 'block';

  // Report output
  document.getElementById('reportOutput').innerHTML =
    `<pre class="rpt-report-text">${esc(text)}</pre>`;

  document.getElementById('copyBtn').style.display = 'block';
  document.getElementById('reportMeta').textContent =
    `Generated ${new Date().toLocaleTimeString()}`;
  document.getElementById('lastUpdated').textContent =
    `Updated: ${new Date().toLocaleTimeString()}`;
}

function renderReportError(msg) {
  document.getElementById('reportOutput').innerHTML = `
    <div class="error-state" style="padding:var(--s8) var(--s6)">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
      <p>Report generation failed</p>
      <span>${esc(msg)}</span>
      <button class="btn btn--primary" style="margin-top:8px" onclick="generateReport()">Retry</button>
    </div>`;
  document.getElementById('copyBtn').style.display = 'none';
}

/* ============================================================
   EVENTS
   ============================================================ */
function bindEvents() {
  document.getElementById('generateBtn').addEventListener('click', generateReport);

  document.getElementById('codeInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') generateReport();
  });

  document.getElementById('copyBtn').addEventListener('click', () => {
    const el = document.querySelector('.rpt-report-text');
    if (!el) return;
    navigator.clipboard.writeText(el.textContent || '').then(() => {
      showToast('Copied to clipboard', 'success');
    }).catch(() => {
      showToast('Copy failed — please select and copy manually', 'error');
    });
  });
}

/* ============================================================
   HELPERS
   ============================================================ */
function setPreset(market, code) {
  document.getElementById('marketSelect').value = market;
  document.getElementById('codeInput').value    = code;
  document.getElementById('formError').style.display = 'none';
}

function setLoading(on) {
  document.getElementById('loadingTag').style.display = on ? 'flex' : 'none';
  document.getElementById('generateBtn').disabled = on;
}

function showFormError(msg) {
  const el = document.getElementById('formError');
  el.textContent    = msg;
  el.style.display  = 'block';
}

function showToast(msg, type = 'info') {
  const c = document.getElementById('toastContainer');
  const t = document.createElement('div');
  t.className = `toast toast--${type}`;
  t.textContent = msg;
  c.appendChild(t);
  requestAnimationFrame(() => requestAnimationFrame(() => t.classList.add('show')));
  setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 260); }, 4000);
}

function countClass(n) {
  if (n >= 3) return 'cnt-high';
  if (n === 2) return 'cnt-medium';
  if (n === 1) return 'cnt-low';
  return 'cnt-zero';
}
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
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
