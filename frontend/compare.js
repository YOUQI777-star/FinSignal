'use strict';

const RULE_IDS = ['F1', 'F2', 'F3', 'F4', 'G1', 'G3'];

const RULE_NAMES = {
  F1: 'AR Abnormal Growth',
  F2: 'Cash Flow Divergence',
  F3: 'High Leverage',
  F4: 'Margin Decline',
  G1: 'Pledge Ratio',
  G3: 'Board Independence',
};

/* ============================================================
   MOCK DATA
   ============================================================ */
const MOCK_COMPARE = {
  results: [
    {
      company_id: 'CN:600519', market: 'CN', code: '600519', name: '贵州茅台',
      summary: { total_rules: 6, triggered_count: 0, snapshot_tier: 'real_financial_available' },
      financial_signals:  [
        { signal_id: 'F1', triggered: false, status: 'ok' },
        { signal_id: 'F2', triggered: false, status: 'ok' },
        { signal_id: 'F3', triggered: false, status: 'ok' },
        { signal_id: 'F4', triggered: false, status: 'ok' },
      ],
      governance_signals: [
        { signal_id: 'G1', triggered: false, status: 'ok' },
        { signal_id: 'G3', triggered: false, status: 'not_available' },
      ],
    },
    {
      company_id: 'TW:2330', market: 'TW', code: '2330', name: '台積電',
      summary: { total_rules: 6, triggered_count: 1, snapshot_tier: 'real_financial_available' },
      financial_signals:  [
        { signal_id: 'F1', triggered: true,  status: 'triggered' },
        { signal_id: 'F2', triggered: false, status: 'ok' },
        { signal_id: 'F3', triggered: false, status: 'ok' },
        { signal_id: 'F4', triggered: false, status: 'ok' },
      ],
      governance_signals: [
        { signal_id: 'G1', triggered: false, status: 'ok' },
        { signal_id: 'G3', triggered: false, status: 'not_available' },
      ],
    },
    {
      company_id: 'CN:000002', market: 'CN', code: '000002', name: '万科A',
      summary: { total_rules: 6, triggered_count: 3, snapshot_tier: 'real_financial_available' },
      financial_signals:  [
        { signal_id: 'F1', triggered: true,  status: 'triggered' },
        { signal_id: 'F2', triggered: false, status: 'ok' },
        { signal_id: 'F3', triggered: true,  status: 'triggered' },
        { signal_id: 'F4', triggered: true,  status: 'triggered' },
      ],
      governance_signals: [
        { signal_id: 'G1', triggered: false, status: 'ok' },
        { signal_id: 'G3', triggered: false, status: 'not_available' },
      ],
    },
  ],
};

/* ============================================================
   ENTRY POINT
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  document.getElementById('compareBtn').addEventListener('click', runCompare);
  document.getElementById('codesInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') runCompare();
  });

  // Pre-fill from URL ?codes=...
  const p = new URLSearchParams(window.location.search);
  const codes = p.get('codes');
  if (codes) {
    document.getElementById('codesInput').value = codes;
    runCompare();
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
   COMPARE
   ============================================================ */
async function runCompare() {
  const raw  = document.getElementById('codesInput').value.trim();
  const hint = document.getElementById('inputHint');

  if (!raw) {
    hint.textContent = 'Please enter at least 2 company IDs.';
    hint.style.color = 'var(--c-triggered)';
    return;
  }

  const ids = raw.split(',').map(s => s.trim()).filter(Boolean);
  if (ids.length < 2) {
    hint.textContent = 'Please enter at least 2 company IDs.';
    hint.style.color = 'var(--c-triggered)';
    return;
  }
  if (ids.length > 5) {
    hint.textContent = 'Maximum 5 companies at a time.';
    hint.style.color = 'var(--c-triggered)';
    return;
  }

  hint.textContent = '';
  setLoading(true);

  try {
    let data;
    try {
      data = await API.compare(ids);
    } catch (err) {
      console.warn('[compare] API unreachable, using mock:', err.message);
      data = MOCK_COMPARE;
      showToast('Backend not running — showing demo data', 'warning');
    }

    renderResults(data.results || []);
    document.getElementById('lastUpdated').textContent =
      `Updated: ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    renderError(err.message);
  } finally {
    setLoading(false);
  }
}

/* ============================================================
   RENDER
   ============================================================ */
function renderResults(results) {
  const container = document.getElementById('compareResults');

  if (!results.length) {
    container.innerHTML = `<div class="empty-state"><p>No results returned</p><span>Check the company IDs and try again</span></div>`;
    return;
  }

  container.innerHTML = `
    ${renderSummaryTable(results)}
    ${renderRuleMatrix(results)}`;
}

function renderSummaryTable(results) {
  const rows = results.map(r => {
    const mkt  = (r.market || '').toLowerCase();
    const cnt  = r.summary?.triggered_count ?? 0;
    const tier = r.summary?.snapshot_tier   ?? '';
    return `<tr>
      <td>
        <div class="company-cell">
          <span class="company-name">${esc(r.name || '—')}</span>
        </div>
      </td>
      <td><span class="badge badge-market badge-market-${mkt}">${r.market}</span></td>
      <td><code style="font-family:'SF Mono',monospace;font-size:var(--f-sm);color:var(--txt-2)">${esc(r.code)}</code></td>
      <td><span class="trigger-count ${countClass(cnt)}">${cnt}</span></td>
      <td style="color:var(--txt-2);font-size:var(--f-sm)">${r.summary?.total_rules ?? '—'}</td>
      <td><span class="tier-badge ${tierClass(tier)}">${tierLabel(tier)}</span></td>
      <td>
        <a href="company.html?market=${r.market}&code=${esc(r.code)}" class="btn-view">View →</a>
      </td>
    </tr>`;
  }).join('');

  return `
    <div class="panel" style="margin-top:var(--s5)">
      <div class="panel-header">
        <div class="panel-header-left">
          <h2 class="panel-title">Summary Comparison</h2>
          <span class="panel-meta">${results.length} companies</span>
        </div>
      </div>
      <div class="table-container">
        <table class="signal-table">
          <thead>
            <tr>
              <th>Company</th>
              <th>Market</th>
              <th>Code</th>
              <th>Triggered</th>
              <th>Total Rules</th>
              <th>Data Tier</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
}

function renderRuleMatrix(results) {
  // Build lookup: company_id → { signal_id → status }
  const lookup = {};
  results.forEach(r => {
    lookup[r.company_id] = {};
    [...(r.financial_signals || []), ...(r.governance_signals || [])].forEach(s => {
      lookup[r.company_id][s.signal_id] = s.status || (s.triggered ? 'triggered' : 'ok');
    });
  });

  const colHeaders = results.map(r => {
    const mkt = (r.market || '').toLowerCase();
    return `<th style="text-align:center;min-width:120px">
      <div style="display:flex;flex-direction:column;align-items:center;gap:4px">
        <span class="badge badge-market badge-market-${mkt}">${r.market}</span>
        <span style="font-size:var(--f-xs);font-weight:700;color:var(--txt-1)">${esc(r.name || r.code)}</span>
        <span style="font-size:var(--f-xs);color:var(--txt-3);font-family:'SF Mono',monospace">${esc(r.code)}</span>
      </div>
    </th>`;
  }).join('');

  const rows = RULE_IDS.map(ruleId => {
    const cells = results.map(r => {
      const status = lookup[r.company_id]?.[ruleId];
      return `<td style="text-align:center">${statusCell(status)}</td>`;
    }).join('');
    return `<tr>
      <td style="white-space:nowrap">
        <div style="display:flex;align-items:center;gap:var(--s2)">
          <span class="badge badge-rule">${ruleId}</span>
          <span style="font-size:var(--f-sm);color:var(--txt-2)">${RULE_NAMES[ruleId] || ruleId}</span>
        </div>
      </td>
      ${cells}
    </tr>`;
  }).join('');

  return `
    <div class="panel" style="margin-top:var(--s4)">
      <div class="panel-header">
        <div class="panel-header-left">
          <h2 class="panel-title">Rule Matrix</h2>
          <span class="panel-meta">Per-rule signal status across all companies</span>
        </div>
      </div>
      <div class="table-container">
        <table class="signal-table">
          <thead>
            <tr>
              <th style="min-width:200px">Rule</th>
              ${colHeaders}
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
}

function statusCell(status) {
  if (status === 'triggered') {
    return `<span class="badge badge-triggered" style="font-size:var(--f-xs)">Triggered</span>`;
  }
  if (status === 'ok') {
    return `<span class="badge badge-ok" style="font-size:var(--f-xs)">OK</span>`;
  }
  if (status === 'not_available') {
    return `<span class="badge badge-na" style="font-size:var(--f-xs)">N/A</span>`;
  }
  return `<span style="color:var(--txt-3);font-size:var(--f-sm)">—</span>`;
}

function renderError(msg) {
  document.getElementById('compareResults').innerHTML = `
    <div class="error-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
      <p>Failed to load comparison</p>
      <span>${esc(msg)}</span>
    </div>`;
}

/* ============================================================
   HELPERS
   ============================================================ */
function setPreset(val) {
  document.getElementById('codesInput').value = val;
  document.getElementById('inputHint').textContent = '';
}

function setLoading(on) {
  document.getElementById('loadingTag').style.display = on ? 'flex' : 'none';
  document.getElementById('compareBtn').disabled = on;
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
