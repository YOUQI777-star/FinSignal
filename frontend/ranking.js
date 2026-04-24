'use strict';
const t = (zh, en) => window._currentLang === 'zh' ? zh : en;

const state = {
  filters:   { market: '', signal_id: '', limit: 50 },
  allResults: [],
  loading:   false,
  searchQ:   '',
  meta:      { source: '', scoreModel: '', sortMode: '' },
};

/* ============================================================
   ENTRY POINT
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  bindEvents();
  loadRanking();
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
   LOAD
   ============================================================ */
async function loadRanking() {
  if (state.loading) return;
  state.loading = true;
  setLoadingUI(true);

  try {
    const data = await API.getTop(state.filters);
    state.allResults = data.results || [];
    state.meta = {
      source: data.source || '',
      scoreModel: data.score_model || '',
      sortMode: data.sort_mode || '',
    };
    renderTable();
    updateTableInfo(data.total, state.allResults.length);
    document.getElementById('lastUpdated').textContent =
      t(`更新于 ${new Date().toLocaleTimeString()}`, `Updated: ${new Date().toLocaleTimeString()}`);
  } catch (err) {
    renderError(err.message);
  } finally {
    state.loading = false;
    setLoadingUI(false);
  }
}

/* ============================================================
   RENDER
   ============================================================ */
function renderTable() {
  const q       = state.searchQ.toLowerCase();
  const results = q
    ? state.allResults.filter(r =>
        (r.name || '').toLowerCase().includes(q) ||
        (r.code || '').toLowerCase().includes(q))
    : state.allResults;

  const container = document.getElementById('tableContainer');

  if (!results.length) {
    container.innerHTML = `
      <div class="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
          <circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <p>${t('暂无信号', 'No results found')}</p>
        <span>${q ? t('没有匹配的公司', 'No companies match your search filter') : t('尝试调整筛选条件', 'Try adjusting your market or rule filter')}</span>
      </div>`;
    return;
  }

  const rows = results.map((item, idx) => {
    const triggered = getTriggeredRuleIds(item);
    const count     = item.summary?.triggered_count ?? 0;
    const tier      = item.summary?.snapshot_tier   ?? '';
    const mkt       = (item.market || '').toLowerCase();
    const nameSafe  = esc(item.name || '—');
    const score     = item.candidate_score;

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
      <td class="col-count">
        <span class="trigger-count ${scoreClass(score)}">${score != null ? Number(score).toFixed(1) : '—'}</span>
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
        <a href="company.html?market=${item.market}&code=${esc(item.code)}&from=ranking" class="btn-view">${t('查看 →', 'View →')}</a>
      </td>
    </tr>`;
  }).join('');

  const zh = window._currentLang === 'zh';
  container.innerHTML = `
    <div class="ranking-score-note">
      ${zh
        ? '信号排名按触发数量优先、综合评分次排序。结构评分 = 吸筹活跃×0.30 + 价格结构×0.28 + 量价配合×0.27 + 板块共振×0.15 ± 结构修正'
        : 'Signal ranking sorts by triggered count first, then structure score. Structure Score = activity base×0.30 + price structure×0.28 + volume-price×0.27 + sector resonance×0.15 ± structural adjustments'}
    </div>
    <table class="signal-table">
      <thead>
        <tr>
          <th class="col-idx">#</th>
          <th class="col-company">${zh ? '公司' : 'Company'}</th>
          <th class="col-market">${zh ? '市场' : 'Market'}</th>
          <th class="col-count">${zh ? '触发' : 'Triggered'}</th>
          <th class="col-count">${zh ? '综合评分' : 'Score'}</th>
          <th class="col-rules">${zh ? '触发规则' : 'Triggered Rules'}</th>
          <th class="col-tier">${zh ? '数据级别' : 'Data Tier'}</th>
          <th class="col-action">${zh ? '操作' : 'Action'}</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
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
      <button class="btn btn--primary" style="margin-top:8px" onclick="loadRanking()">${t('重试', 'Retry')}</button>
    </div>`;
}

function updateTableInfo(total, shown) {
  const el = document.getElementById('tableInfo');
  if (total != null) {
    const zh = window._currentLang === 'zh';
    const sourceLabel = state.meta.source === 'signals_cache'
      ? t('信号缓存', 'Signals cache')
      : (state.meta.source || '—');
    const modelLabel = state.meta.scoreModel || '—';
    el.textContent = zh
      ? `显示 ${shown} / ${(total || 0).toLocaleString()} 家公司 · 来源：${sourceLabel} · 评分模型：${modelLabel}`
      : `Showing ${shown} of ${(total || 0).toLocaleString()} companies · Source: ${sourceLabel} · Score model: ${modelLabel}`;
  }
}

/* ============================================================
   EVENTS
   ============================================================ */
function bindEvents() {
  document.getElementById('marketFilter').addEventListener('change', e => {
    state.filters.market = e.target.value;
    loadRanking();
  });

  document.getElementById('signalFilter').addEventListener('change', e => {
    state.filters.signal_id = e.target.value;
    loadRanking();
  });

  document.getElementById('limitSelect').addEventListener('change', e => {
    state.filters.limit = parseInt(e.target.value, 10);
    loadRanking();
  });

  document.getElementById('refreshBtn').addEventListener('click', loadRanking);

  document.getElementById('searchInput').addEventListener('input', e => {
    state.searchQ = e.target.value.trim();
    renderTable();
  });

  document.getElementById('exportBtn').addEventListener('click', exportCSV);
}

/* ============================================================
   CSV EXPORT
   ============================================================ */
function exportCSV() {
  const q = state.searchQ.toLowerCase();
  const results = q
    ? state.allResults.filter(r =>
        (r.name || '').toLowerCase().includes(q) ||
        (r.code || '').toLowerCase().includes(q))
    : state.allResults;

  if (!results.length) {
    showToast(t('无数据可导出', 'No data to export'), 'error');
    return;
  }

  const headers = ['Rank', 'Name', 'Code', 'Market', 'Triggered', 'Score', 'Triggered Rules', 'Score Formula', 'Data Tier'];
  const rows = results.map((r, idx) => {
    const triggered = getTriggeredRuleIds(r).join(' ');
    const tier = tierLabel(r.summary?.snapshot_tier ?? '');
    const count = r.summary?.triggered_count ?? 0;
    return [
      idx + 1,
      `"${(r.name || '').replace(/"/g, '""')}"`,
      r.code,
      r.market,
      count,
      r.candidate_score ?? '',
      `"${triggered}"`,
      `"${(r.score_formula || '').replace(/"/g, '""')}"`,
      tier,
    ].join(',');
  });

  const csv = [headers.join(','), ...rows].join('\n');
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  const mkt  = state.filters.market || 'all';
  const sig  = state.filters.signal_id || 'all';
  a.href     = url;
  a.download = `fsm_ranking_${mkt}_${sig}_${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  showToast(t(`已导出 ${results.length} 行`, `Exported ${results.length} rows`), 'success');
}

/* ============================================================
   HELPERS
   ============================================================ */
function setLoadingUI(on) {
  document.getElementById('loadingTag').style.display = on ? 'flex' : 'none';
  document.getElementById('refreshBtn').classList.toggle('spinning', on);
  if (on) {
    document.getElementById('tableContainer').innerHTML = `
      <div class="loading-state">
        <div class="loading-dots"><span></span><span></span><span></span></div>
        <p>${t('获取信号数据中…', 'Fetching signal data…')}</p>
      </div>`;
  }
}

function getTriggeredRuleIds(item) {
  return [...(item.financial_signals || []), ...(item.governance_signals || [])]
    .filter(s => s.triggered).map(s => s.signal_id);
}

function showToast(msg, type = 'info') {
  const c = document.getElementById('toastContainer');
  const el = document.createElement('div');
  el.className = `toast toast--${type}`;
  el.textContent = msg;
  c.appendChild(el);
  requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add('show')));
  setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 260); }, 4000);
}

function countClass(n) {
  if (n >= 3) return 'cnt-high';
  if (n === 2) return 'cnt-medium';
  if (n === 1) return 'cnt-low';
  return 'cnt-zero';
}
function scoreClass(n) {
  const score = Number(n);
  if (!Number.isFinite(score)) return 'cnt-zero';
  if (score >= 80) return 'cnt-high';
  if (score >= 65) return 'cnt-medium';
  if (score >= 50) return 'cnt-low';
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
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
