'use strict';

const t = (zh, en) => window._currentLang === 'zh' ? zh : en;

const state = {
  recentlyViewed: [],
  searchTimer: null,
};

document.addEventListener('DOMContentLoaded', () => {
  loadRecentlyViewed();
  bindEvents();
  checkHealth();
  loadHomeData();
});

async function checkHealth() {
  const dot = document.getElementById('healthDot');
  const label = document.getElementById('healthLabel');
  try {
    await API.health();
    dot.className = 'health-dot health-dot--ok';
    label.textContent = t('API 已连接', 'API Connected');
  } catch {
    dot.className = 'health-dot health-dot--err';
    label.textContent = t('API 离线', 'API Offline');
  }
}

async function loadHomeData() {
  let topData = { total: 0, results: [] };
  let candidatesData = { total: 0, results: [] };

  const [topResult, candidatesResult] = await Promise.allSettled([
    API.getTop({ limit: 200 }),
    API.getCandidates({ limit: 5 }),
  ]);

  if (topResult.status === 'fulfilled') {
    topData = topResult.value;
  } else {
    console.warn('[FSM] top signals unreachable, using mock data:', topResult.reason?.message || topResult.reason);
    topData = MOCK_DATA.top;
    showToast(t('信号排行接口异常，首页部分使用演示数据', 'Signals endpoint failed, part of the homepage is showing demo data'), 'warning');
  }

  if (candidatesResult.status === 'fulfilled') {
    candidatesData = candidatesResult.value;
  } else {
    console.warn('[FSM] candidates preview unavailable:', candidatesResult.reason?.message || candidatesResult.reason);
    showToast(t('候选池接口加载失败，首页候选摘要暂不可用', 'Candidates endpoint failed, homepage preview is temporarily unavailable'), 'warning');
  }

  renderHomeSummary(candidatesData.total || 0, topData.total || 0);
  renderCandidatePreview(candidatesData.results || []);
  renderRuleDistribution(topData.results || []);
}

function renderHomeSummary(candidatesTotal, highRiskTotal) {
  document.getElementById('homeCandidatesCount').textContent = candidatesTotal.toLocaleString();
  document.getElementById('homeHighRiskCount').textContent = highRiskTotal.toLocaleString();
}

function renderCandidatePreview(results) {
  const container = document.getElementById('candidatePreview');
  if (!results.length) {
    container.innerHTML = `<div class="empty-state" style="padding:24px">
      <p>${t('暂无候选池数据', 'No candidate preview available')}</p>
      <span>${t('稍后刷新或进入候选池查看', 'Refresh later or open Candidates for the full list')}</span>
    </div>`;
    return;
  }

  container.innerHTML = results.map(item => {
    const check = item.financial_check || { status: 'no_data', triggered_signals: [], triggered_count: 0 };
    const signalText = check.triggered_signals?.length ? check.triggered_signals.join(', ') : t('无触发', 'No triggers');
    return `
      <a class="candidate-preview-item" href="company.html?market=CN&code=${encodeURIComponent(item.code)}&from=candidates">
        <div class="candidate-preview-main">
          <div class="candidate-preview-head">
            <span class="badge badge-market badge-market-cn">CN</span>
            <span class="candidate-preview-name">${esc(item.name)}</span>
            <span class="candidate-preview-code">${esc(item.code)}</span>
          </div>
          <div class="candidate-preview-meta">
            <span>${t('候选原因：', 'Candidate: ')}${esc(item.candidate_reason || '—')}</span>
            <span>${t('换手：', 'Turnover: ')}${formatPct(item.turnover)}</span>
          </div>
        </div>
        <div class="candidate-preview-side">
          ${renderFinancialCheckBadge(check)}
          <span class="candidate-preview-signals">${esc(signalText)}</span>
        </div>
      </a>`;
  }).join('');
}

function renderFinancialCheckBadge(check) {
  const status = check?.status || 'no_data';
  const map = {
    high_risk: { cls: 'badge-high-risk', zh: '高风险', en: 'High Risk' },
    warning: { cls: 'badge-warning', zh: '预警', en: 'Warning' },
    pass: { cls: 'badge-pass', zh: '通过', en: 'Pass' },
    no_data: { cls: 'badge-no-data', zh: '无数据', en: 'No Data' },
  };
  const item = map[status] || map.no_data;
  return `<span class="badge financial-check-badge ${item.cls}">${t(item.zh, item.en)}</span>`;
}

function renderRuleDistribution(results) {
  const dist = {};
  results.forEach(item => {
    [...(item.financial_signals || []), ...(item.governance_signals || [])].forEach(sig => {
      if (sig.triggered) dist[sig.signal_id] = (dist[sig.signal_id] || 0) + 1;
    });
  });

  const entries = Object.entries(dist)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);

  const wrap = document.getElementById('ruleDistribution');
  if (!entries.length) {
    wrap.innerHTML = `<div class="empty-state" style="padding:20px">
      <p>${t('暂无规则分布数据', 'No rule distribution data')}</p>
    </div>`;
    return;
  }

  const max = Math.max(...entries.map(([, count]) => count));
  wrap.innerHTML = entries.map(([rule, count]) => `
    <div class="rule-bar-item">
      <div class="rule-bar-top">
        <span class="badge badge-rule">${rule}</span>
        <span class="rule-bar-name">${ruleLabel(rule)}</span>
        <span class="rule-bar-count">${count.toLocaleString()}</span>
      </div>
      <div class="rule-bar-track">
        <div class="rule-bar-fill" style="width:${(count / max) * 100}%"></div>
      </div>
    </div>`).join('');
}

function ruleLabel(rule) {
  const labels = {
    F1: t('应收异常', 'AR Growth'),
    F2: t('现金流背离', 'Cash Flow'),
    F3: t('高杠杆', 'Leverage'),
    F4: t('利润率下滑', 'Margin'),
    G1: t('高质押', 'Pledge'),
    G3: t('董事会独立性', 'Board'),
  };
  return labels[rule] || rule;
}

function loadRecentlyViewed() {
  try {
    state.recentlyViewed = JSON.parse(localStorage.getItem('fsm_recent') || '[]');
  } catch {
    state.recentlyViewed = [];
  }
  renderRecentlyViewed();
}

function renderRecentlyViewed() {
  const el = document.getElementById('recentList');
  const clearBtn = document.getElementById('clearRecent');
  if (!state.recentlyViewed.length) {
    el.innerHTML = `<p class="empty-hint" data-i18n="dash_no_recent">${t('暂无浏览记录', 'No recent history')}</p>`;
    clearBtn.style.display = 'none';
    return;
  }

  clearBtn.style.display = 'inline-flex';
  el.innerHTML = state.recentlyViewed.map(item => `
    <a class="recent-item" href="company.html?market=${encodeURIComponent(item.market)}&code=${encodeURIComponent(item.code)}">
      <span class="badge badge-market badge-market-${String(item.market || '').toLowerCase()}">${esc(item.market)}</span>
      <span class="recent-name">${esc(item.name || item.code)}</span>
      <span class="recent-code">${esc(item.code)}</span>
    </a>`).join('');
}

function bindEvents() {
  document.getElementById('searchInput').addEventListener('input', handleSearchInput);
  document.getElementById('searchClear').addEventListener('click', () => {
    const input = document.getElementById('searchInput');
    input.value = '';
    input.focus();
    toggleClear(false);
    closeDropdown();
  });
  document.getElementById('clearRecent').addEventListener('click', clearRecentlyViewed);
  document.addEventListener('click', event => {
    if (!document.getElementById('searchWrap').contains(event.target)) closeDropdown();
  });
}

function handleSearchInput(e) {
  const value = e.target.value.trim();
  toggleClear(!!value);
  clearTimeout(state.searchTimer);

  if (!value) {
    closeDropdown();
    return;
  }

  state.searchTimer = setTimeout(async () => {
    try {
      const data = await API.search(value);
      renderSearchDropdown(data.results || []);
    } catch (err) {
      console.warn('[FSM] search failed:', err.message);
      closeDropdown();
    }
  }, 220);
}

function renderSearchDropdown(results) {
  const dropdown = document.getElementById('searchDropdown');
  if (!results.length) {
    dropdown.innerHTML = `<div class="search-empty">${t('无匹配结果', 'No matches found')}</div>`;
    dropdown.classList.add('open');
    return;
  }

  dropdown.innerHTML = results.slice(0, 8).map(item => `
    <button class="search-result-item" data-market="${item.market}" data-code="${item.code}" data-name="${esc(item.name)}">
      <span class="badge badge-market badge-market-${String(item.market || '').toLowerCase()}">${esc(item.market)}</span>
      <span class="search-result-name">${esc(item.name)}</span>
      <span class="search-result-code">${esc(item.code)}</span>
    </button>`).join('');

  dropdown.querySelectorAll('.search-result-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const { market, code, name } = btn.dataset;
      addToRecent({ market, code, name });
      window.location.href = `company.html?market=${market}&code=${code}`;
    });
  });

  dropdown.classList.add('open');
}

function toggleClear(on) {
  document.getElementById('searchClear').style.display = on ? 'inline-flex' : 'none';
}

function closeDropdown() {
  const dropdown = document.getElementById('searchDropdown');
  dropdown.classList.remove('open');
  dropdown.innerHTML = '';
}

function addToRecent(item) {
  const deduped = state.recentlyViewed.filter(existing => !(existing.market === item.market && existing.code === item.code));
  state.recentlyViewed = [item, ...deduped].slice(0, 8);
  localStorage.setItem('fsm_recent', JSON.stringify(state.recentlyViewed));
  renderRecentlyViewed();
}

function clearRecentlyViewed() {
  state.recentlyViewed = [];
  localStorage.removeItem('fsm_recent');
  renderRecentlyViewed();
}

function showToast(msg, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;
  toast.textContent = msg;
  container.appendChild(toast);
  requestAnimationFrame(() => requestAnimationFrame(() => toast.classList.add('show')));
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 260);
  }, 3200);
}

function formatPct(value) {
  if (value == null || !isFinite(value)) return '—';
  return `${Number(value).toFixed(2)}%`;
}

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
