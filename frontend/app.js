'use strict';
const t = (zh, en) => window._currentLang === 'zh' ? zh : en;

/* ============================================================
   STATE
   ============================================================ */
const state = {
  filters:    { market: '', signal_id: '', limit: 50 },
  loading:    false,
  usedMock:   false,
  recentlyViewed: [],
  searchTimer: null,
};

/* ============================================================
   ENTRY POINT
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {
  loadRecentlyViewed();
  bindEvents();
  checkHealth();
  loadTopSignals();
});

/* ============================================================
   HEALTH CHECK
   ============================================================ */
async function checkHealth() {
  const dot   = document.getElementById('healthDot');
  const label = document.getElementById('healthLabel');
  try {
    await API.health();
    dot.className   = 'health-dot online';
    label.textContent = (window._currentLang === 'zh') ? 'API 已连接' : 'API Connected';
  } catch {
    dot.className   = 'health-dot offline';
    label.textContent = (window._currentLang === 'zh') ? 'API 离线' : 'API Offline';
  }
}

/* ============================================================
   LOAD SIGNAL RANKING
   ============================================================ */
async function loadTopSignals() {
  if (state.loading) return;
  state.loading = true;

  setLoadingUI(true);

  try {
    let data;
    try {
      data = await API.getTop(state.filters);
      state.usedMock = false;
    } catch (err) {
      console.warn('[FSM] API unreachable, using mock data:', err.message);
      data = MOCK_DATA.top;
      state.usedMock = true;
      showToast(t('后端未运行 — 显示演示数据', 'Backend not running — showing demo data'), 'warning');
    }

    renderTable(data.results || []);
    renderRuleDistribution(data.results || []);
    updateTableInfo(data.total, (data.results || []).length);
    updateLastUpdated();
  } catch (err) {
    renderError(err.message);
  } finally {
    state.loading = false;
    setLoadingUI(false);
  }
}

/* ============================================================
   TABLE RENDERING
   ============================================================ */
function renderTable(results) {
  const container = document.getElementById('tableContainer');

  if (!results.length) {
    container.innerHTML = `
      <div class="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <p>${t('暂无结果', 'No results found')}</p>
        <span>${t('尝试调整市场或规则筛选', 'Try adjusting your market or rule filter')}</span>
      </div>`;
    return;
  }

  const rows = results.map((item, idx) => {
    const triggered = getTriggeredRuleIds(item);
    const count     = item.summary?.triggered_count ?? 0;
    const tier      = item.summary?.snapshot_tier ?? '';
    const nameSafe  = esc(item.name || '—');
    const mkt       = (item.market || '').toLowerCase();

    return `<tr>
      <td class="col-idx">${idx + 1}</td>
      <td class="col-company">
        <div class="company-cell">
          <span class="company-name">${nameSafe}</span>
          <span class="company-code">${esc(item.code)}</span>
        </div>
      </td>
      <td class="col-market">
        <span class="badge badge-market badge-market-${mkt}">${item.market}</span>
      </td>
      <td class="col-count">
        <span class="trigger-count ${countClass(count)}">${count}</span>
      </td>
      <td class="col-rules">
        <div class="rule-badges">
          ${triggered.length
            ? triggered.map(id => `<span class="badge badge-rule">${id}</span>`).join('')
            : '<span class="no-rules">—</span>'}
        </div>
      </td>
      <td class="col-tier">
        <span class="tier-badge ${tierClass(tier)}">${tierLabel(tier)}</span>
      </td>
      <td class="col-action">
        <button class="btn-view"
          data-market="${item.market}"
          data-code="${esc(item.code)}"
          data-name="${nameSafe}">${t('查看 →', 'View →')}</button>
      </td>
    </tr>`;
  }).join('');

  const zh = window._currentLang === 'zh';
  container.innerHTML = `
    <table class="signal-table">
      <thead>
        <tr>
          <th class="col-idx">#</th>
          <th class="col-company">${zh ? '公司' : 'Company'}</th>
          <th class="col-market">${zh ? '市场' : 'Market'}</th>
          <th class="col-count">${zh ? '触发' : 'Triggered'}</th>
          <th class="col-rules">${zh ? '触发规则' : 'Triggered Rules'}</th>
          <th class="col-tier">${zh ? '数据级别' : 'Data Tier'}</th>
          <th class="col-action">${zh ? '操作' : 'Action'}</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;

  container.querySelectorAll('.btn-view').forEach(btn => {
    btn.addEventListener('click', () => {
      const { market, code, name } = btn.dataset;
      addToRecent({ market, code, name });
      window.location.href = `company.html?market=${market}&code=${code}`;
    });
  });
}

function renderError(msg) {
  document.getElementById('tableContainer').innerHTML = `
    <div class="error-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
      <p>${t('数据加载失败', 'Failed to load data')}</p>
      <span>${esc(msg)}</span>
      <button class="btn btn--primary" style="margin-top:8px" onclick="loadTopSignals()">${t('重试', 'Retry')}</button>
    </div>`;
}

/* ============================================================
   RULE DISTRIBUTION
   ============================================================ */
function renderRuleDistribution(results) {
  const container = document.getElementById('ruleDistribution');

  // Count triggered rules from loaded data
  const counts = {};
  results.forEach(item => {
    [...(item.financial_signals || []), ...(item.governance_signals || [])].forEach(sig => {
      if (sig.triggered) counts[sig.signal_id] = (counts[sig.signal_id] || 0) + 1;
    });
  });

  // Static fallback when no data is available
  if (!Object.keys(counts).length) {
    Object.assign(counts, { F1: 1042, F4: 754, F3: 504, F2: 165 });
  }

  const desc = {
    F1: t('应收账款异常增长', 'AR Abnormal Growth'),
    F2: t('现金流背离', 'Cash Flow Divergence'),
    F3: t('高杠杆风险', 'High Leverage'),
    F4: t('毛利率骤降', 'Margin Decline'),
    G1: t('大股东质押', 'Pledge Ratio'),
    G3: t('独立董事不足', 'Board Independence'),
  };

  const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const max = sorted[0]?.[1] || 1;

  container.innerHTML = sorted.map(([id, n]) => `
    <div class="rule-bar-item">
      <div class="rule-bar-top">
        <span class="badge badge-rule">${id}</span>
        <span class="rule-bar-name">${desc[id] || id}</span>
        <span class="rule-bar-count">${n.toLocaleString()}</span>
      </div>
      <div class="rule-bar-track">
        <div class="rule-bar-fill" style="width:${(n / max * 100).toFixed(1)}%"></div>
      </div>
    </div>`).join('');
}

/* ============================================================
   RECENTLY VIEWED
   ============================================================ */
function loadRecentlyViewed() {
  try { state.recentlyViewed = JSON.parse(localStorage.getItem('fsm_recent') || '[]'); }
  catch { state.recentlyViewed = []; }
  renderRecentlyViewed();
}

function addToRecent(company) {
  state.recentlyViewed = state.recentlyViewed.filter(
    r => !(r.market === company.market && r.code === company.code)
  );
  state.recentlyViewed.unshift(company);
  state.recentlyViewed = state.recentlyViewed.slice(0, 5);
  localStorage.setItem('fsm_recent', JSON.stringify(state.recentlyViewed));
  renderRecentlyViewed();
}

function renderRecentlyViewed() {
  const list  = document.getElementById('recentList');
  const clear = document.getElementById('clearRecent');

  if (!state.recentlyViewed.length) {
    list.innerHTML = `<p class="empty-hint">${t('暂无浏览记录', 'No recent history')}</p>`;
    clear.style.display = 'none';
    return;
  }

  list.innerHTML = state.recentlyViewed.map(r => `
    <a href="company.html?market=${r.market}&code=${r.code}" class="recent-item"
       onclick="addToRecentFromLink(event,'${r.market}','${r.code}','${esc(r.name || '')}')">
      <span class="badge badge-market badge-market-${(r.market||'').toLowerCase()}">${r.market}</span>
      <span class="recent-name">${esc(r.name || r.code)}</span>
      <span class="recent-code">${r.code}</span>
    </a>`).join('');

  clear.style.display = 'block';
}

// Called from inline onclick to update recent before navigating
function addToRecentFromLink(e, market, code, name) {
  addToRecent({ market, code, name });
}

/* ============================================================
   SEARCH
   ============================================================ */
function handleSearchInput(e) {
  const q = e.target.value.trim();
  document.getElementById('searchClear').style.display = q ? 'block' : 'none';

  clearTimeout(state.searchTimer);
  if (!q) { closeDropdown(); return; }

  state.searchTimer = setTimeout(async () => {
    try {
      const data = await API.search(q);
      renderDropdown(data.results || []);
    } catch {
      renderDropdown(null, true);
    }
  }, 300);
}

function renderDropdown(results, error = false) {
  const dd = document.getElementById('searchDropdown');

  if (error) {
    dd.innerHTML = `<div class="search-empty">${t('搜索不可用 — 请检查 API 连接', 'Search unavailable — check API connection')}</div>`;
    dd.classList.add('open');
    return;
  }
  if (!results || !results.length) {
    dd.innerHTML = `<div class="search-empty">${t('未找到公司', 'No companies found')}</div>`;
    dd.classList.add('open');
    return;
  }

  dd.innerHTML = results.slice(0, 8).map(r => `
    <div class="search-result-item"
         data-market="${r.market}"
         data-code="${esc(r.code)}"
         data-name="${esc(r.name || '')}">
      <span class="badge badge-market badge-market-${(r.market||'').toLowerCase()}">${r.market}</span>
      <span class="search-result-name">${esc(r.name || r.code)}</span>
      <span class="search-result-code">${r.code}</span>
    </div>`).join('');

  dd.querySelectorAll('.search-result-item').forEach(item => {
    item.addEventListener('click', () => {
      const { market, code, name } = item.dataset;
      addToRecent({ market, code, name });
      window.location.href = `company.html?market=${market}&code=${code}`;
    });
  });

  dd.classList.add('open');
}

function closeDropdown() {
  const dd = document.getElementById('searchDropdown');
  dd.classList.remove('open');
  dd.innerHTML = '';
}

/* ============================================================
   UI HELPERS
   ============================================================ */
function setLoadingUI(on) {
  const tag = document.getElementById('loadingTag');
  const btn = document.getElementById('refreshBtn');
  tag.style.display = on ? 'flex' : 'none';
  btn.classList.toggle('spinning', on);
  if (on) {
    document.getElementById('tableContainer').innerHTML = `
      <div class="loading-state">
        <div class="loading-dots"><span></span><span></span><span></span></div>
        <p>${t('获取信号数据中…', 'Fetching signal data…')}</p>
      </div>`;
  }
}

function updateTableInfo(total, shown) {
  const el = document.getElementById('tableInfo');
  if (total != null) {
    const suffix = state.usedMock ? ' (demo)' : '';
    el.textContent = t(`显示 ${shown} / ${(total || 0).toLocaleString()} 家公司${suffix}`, `Showing ${shown} of ${(total || 0).toLocaleString()} companies${suffix}`);
  }
}

function updateLastUpdated() {
  document.getElementById('lastUpdated').textContent =
    t(`更新于 ${new Date().toLocaleTimeString()}`, `Updated: ${new Date().toLocaleTimeString()}`);
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
  document.getElementById('marketFilter').addEventListener('change', e => {
    state.filters.market = e.target.value;
    loadTopSignals();
  });

  document.getElementById('signalFilter').addEventListener('change', e => {
    state.filters.signal_id = e.target.value;
    loadTopSignals();
  });

  document.getElementById('limitSelect').addEventListener('change', e => {
    state.filters.limit = parseInt(e.target.value, 10);
    loadTopSignals();
  });

  document.getElementById('refreshBtn').addEventListener('click', loadTopSignals);

  document.getElementById('searchInput').addEventListener('input', handleSearchInput);

  document.getElementById('searchClear').addEventListener('click', () => {
    document.getElementById('searchInput').value = '';
    document.getElementById('searchClear').style.display = 'none';
    closeDropdown();
  });

  document.getElementById('searchInput').addEventListener('keydown', e => {
    if (e.key === 'Escape') closeDropdown();
  });

  document.addEventListener('click', e => {
    if (!document.getElementById('searchWrap').contains(e.target)) closeDropdown();
  });

  document.getElementById('clearRecent').addEventListener('click', () => {
    state.recentlyViewed = [];
    localStorage.removeItem('fsm_recent');
    renderRecentlyViewed();
  });
}

/* ============================================================
   UTILITY
   ============================================================ */
function getTriggeredRuleIds(item) {
  return [
    ...(item.financial_signals  || []),
    ...(item.governance_signals || []),
  ].filter(s => s.triggered).map(s => s.signal_id);
}

function countClass(n) {
  if (n >= 3) return 'cnt-high';
  if (n === 2) return 'cnt-medium';
  if (n === 1) return 'cnt-low';
  return 'cnt-zero';
}

function tierClass(tier) {
  if (tier === 'real_financial_available')    return 'tier-full';
  if (tier === 'partial_financial_available') return 'tier-partial';
  return 'tier-shell';
}

function tierLabel(tier) {
  if (tier === 'real_financial_available')    return t('完整数据', 'Full Data');
  if (tier === 'partial_financial_available') return t('部分数据', 'Partial');
  return t('仅基础', 'Shell Only');
}

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
