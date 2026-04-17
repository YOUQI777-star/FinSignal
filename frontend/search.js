'use strict';

const state = {
  timer:    null,
  market:   '',
  lastQ:    '',
  recent:   [],
};

const MOCK_RESULTS = [
  { market: 'CN', code: '600519', name: '贵州茅台' },
  { market: 'CN', code: '000002', name: '万科A' },
  { market: 'CN', code: '600036', name: '招商银行' },
  { market: 'TW', code: '2330',   name: '台積電' },
  { market: 'TW', code: '2412',   name: '中華電信' },
  { market: 'TW', code: '2454',   name: '聯發科' },
];

/* ============================================================
   ENTRY POINT
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  loadRecent();
  bindEvents();

  // Pre-fill from URL ?q=...
  const p = new URLSearchParams(window.location.search);
  const q = p.get('q');
  if (q) {
    document.getElementById('searchInput').value = q;
    document.getElementById('clearBtn').style.display = 'flex';
    doSearch(q);
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
   RECENTLY VIEWED
   ============================================================ */
function loadRecent() {
  try { state.recent = JSON.parse(localStorage.getItem('fsm_recent') || '[]'); }
  catch { state.recent = []; }
  renderRecent();
}

function addToRecent(company) {
  state.recent = state.recent.filter(
    r => !(r.market === company.market && r.code === company.code)
  );
  state.recent.unshift(company);
  state.recent = state.recent.slice(0, 8);
  localStorage.setItem('fsm_recent', JSON.stringify(state.recent));
  renderRecent();
}

function renderRecent() {
  const section = document.getElementById('recentSection');
  const grid    = document.getElementById('recentGrid');

  // Hide recently viewed section when results are showing
  const resultsVisible = document.getElementById('resultsSection').style.display !== 'none';
  if (!state.recent.length || resultsVisible) {
    section.style.display = 'none';
    return;
  }

  section.style.display = 'block';
  grid.innerHTML = state.recent.map(r => {
    const mkt = (r.market || '').toLowerCase();
    return `
      <a href="company.html?market=${r.market}&code=${esc(r.code)}"
         class="srch-recent-card"
         onclick="addToRecent({market:'${r.market}',code:'${esc(r.code)}',name:'${esc(r.name||'')}'})"
      >
        <span class="badge badge-market badge-market-${mkt}">${r.market}</span>
        <span class="srch-recent-name">${esc(r.name || r.code)}</span>
        <span class="srch-recent-code">${esc(r.code)}</span>
      </a>`;
  }).join('');
}

/* ============================================================
   SEARCH
   ============================================================ */
function handleInput(e) {
  const q = e.target.value;
  document.getElementById('clearBtn').style.display = q ? 'flex' : 'none';

  clearTimeout(state.timer);
  if (!q.trim()) {
    clearResults();
    return;
  }
  state.timer = setTimeout(() => doSearch(q.trim()), 280);
}

async function doSearch(q) {
  state.lastQ = q;
  setLoading(true);

  try {
    let data;
    try {
      data = await API.search(q);
    } catch (err) {
      console.warn('[search] API unreachable, using mock:', err.message);
      // simple front-end filter on mock
      const lq = q.toLowerCase();
      data = {
        results: MOCK_RESULTS.filter(r =>
          r.name.toLowerCase().includes(lq) ||
          r.code.toLowerCase().includes(lq)
        ),
      };
      showToast('Backend not running — showing demo data', 'warning');
    }

    // Apply market tab filter client-side
    let results = data.results || [];
    if (state.market) {
      results = results.filter(r => r.market === state.market);
    }

    renderResults(results, q);
  } catch (err) {
    renderError(err.message);
  } finally {
    setLoading(false);
  }
}

function renderResults(results, q) {
  document.getElementById('initialState').style.display    = 'none';
  document.getElementById('recentSection').style.display   = 'none';
  document.getElementById('resultsSection').style.display  = 'block';

  const meta = document.getElementById('resultsMeta');
  const mktSuffix = state.market ? ` in ${state.market}` : '';
  meta.textContent = results.length
    ? `${results.length} result${results.length > 1 ? 's' : ''} for "${q}"${mktSuffix}`
    : `No results for "${q}"${mktSuffix}`;

  const container = document.getElementById('resultsContainer');

  if (!results.length) {
    container.innerHTML = `
      <div class="empty-state" style="padding:var(--s8) var(--s6)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
          <circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <p>No companies found</p>
        <span>Try a different name, code, or switch markets</span>
      </div>`;
    return;
  }

  const rows = results.map(r => {
    const mkt = (r.market || '').toLowerCase();
    return `<tr>
      <td class="col-company">
        <div class="company-cell">
          <span class="company-name">${highlight(esc(r.name || '—'), q)}</span>
          <span class="company-code">${highlight(esc(r.code), q)}</span>
        </div>
      </td>
      <td class="col-market">
        <span class="badge badge-market badge-market-${mkt}">${r.market}</span>
      </td>
      <td class="col-action" style="text-align:right;display:flex;gap:var(--s2);justify-content:flex-end;padding:11px var(--s4)">
        <a href="company.html?market=${r.market}&code=${esc(r.code)}"
           class="btn-view"
           onclick="addToRecent({market:'${r.market}',code:'${esc(r.code)}',name:'${esc(r.name||'')}'})">
          View →
        </a>
        <a href="reports.html?market=${r.market}&code=${esc(r.code)}"
           class="btn btn--outline" style="height:30px;font-size:var(--f-xs);padding:0 10px">
          Report
        </a>
      </td>
    </tr>`;
  }).join('');

  container.innerHTML = `
    <table class="signal-table">
      <thead>
        <tr>
          <th class="col-company">Company</th>
          <th class="col-market">Market</th>
          <th style="text-align:right">Actions</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function renderError(msg) {
  document.getElementById('initialState').style.display   = 'none';
  document.getElementById('resultsSection').style.display = 'block';
  document.getElementById('resultsContainer').innerHTML = `
    <div class="error-state" style="padding:var(--s8) var(--s6)">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
      <p>Search failed</p>
      <span>${esc(msg)}</span>
    </div>`;
}

function clearResults() {
  document.getElementById('resultsSection').style.display = 'none';
  document.getElementById('initialState').style.display   = 'block';
  renderRecent();
}

/* ============================================================
   EVENTS
   ============================================================ */
function bindEvents() {
  document.getElementById('searchInput').addEventListener('input', handleInput);

  document.getElementById('clearBtn').addEventListener('click', () => {
    document.getElementById('searchInput').value = '';
    document.getElementById('clearBtn').style.display = 'none';
    clearResults();
  });

  document.getElementById('searchInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      clearTimeout(state.timer);
      const q = e.target.value.trim();
      if (q) doSearch(q);
    }
  });

  // Market tabs
  document.querySelectorAll('.srch-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.srch-tab').forEach(t => t.classList.remove('srch-tab--active'));
      tab.classList.add('srch-tab--active');
      state.market = tab.dataset.market;
      const q = document.getElementById('searchInput').value.trim();
      if (q) doSearch(q);
    });
  });

  document.getElementById('clearRecentBtn').addEventListener('click', () => {
    state.recent = [];
    localStorage.removeItem('fsm_recent');
    renderRecent();
  });
}

/* ============================================================
   HELPERS
   ============================================================ */
function highlight(text, q) {
  if (!q) return text;
  // q is already esc'd via the caller; re-escape the query for regex
  const safe = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return text.replace(new RegExp(`(${safe})`, 'gi'), '<mark class="srch-hl">$1</mark>');
}

function setLoading(on) {
  document.getElementById('loadingTag').style.display = on ? 'flex' : 'none';
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

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
