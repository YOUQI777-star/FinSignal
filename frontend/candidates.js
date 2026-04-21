'use strict';

/* ============================================================
   CANDIDATES PAGE
   持续换手候选池 — realtime /api/candidates (30-min in-memory cache)
   ============================================================ */

const t = (zh, en) => window._currentLang === 'zh' ? zh : en;

const state = {
  data:     null,
  filtered: [],
  page:     1,
  pageSize: 100,
  restoreAnchor: '',
  scrollTop: 0,
  tradingDate: '',
  baseTradingDate: '',
  refreshing: false,
};

const FILTERS_KEY = 'fsm_candidates_filters_v1';
const RETURN_KEY = 'fsm_candidates_return_v1';
const DEFAULT_FILTERS = {
  turnoverMin: '2',
  turnoverMax: '',
  priceMax: '20',
  circMvMax: '80',
  pctMax: '9',
  excludeSt: true,
  page: 1,
};

// ── Health check ─────────────────────────────────────────────────────────────
async function checkHealth() {
  const dot   = document.getElementById('healthDot');
  const label = document.getElementById('healthLabel');
  try {
    await API.health();
    dot.className     = 'health-dot health-dot--ok';
    label.textContent = (window._currentLang === 'zh') ? 'API 已连接' : 'API Connected';
  } catch {
    dot.className     = 'health-dot health-dot--err';
    label.textContent = (window._currentLang === 'zh') ? 'API 离线' : 'API Offline';
  }
}

// ── Load candidates from API ─────────────────────────────────────────────────
async function loadCandidates({ forceRefresh = false } = {}) {
  state.refreshing = forceRefresh;
  setLoading(true);
  document.getElementById('tableContainer').innerHTML = '';
  document.getElementById('tableInfo').textContent    = '';

  try {
    const params = buildParams();
    if (forceRefresh) params.refresh = '1';
    params.page = String(state.page);
    params.page_size = String(state.pageSize);
    const data = await API.getCandidates(params);
    state.data     = data;
    state.filtered = data.results || [];
    persistCandidatesState();
    syncStateToUrl();
    renderTable(state.filtered);
    renderMeta(data);
    renderPagination(data);
  } catch (err) {
    renderError(err.message);
  } finally {
    state.refreshing = false;
    setLoading(false);
    document.getElementById('lastUpdated').textContent =
      'Updated ' + new Date().toLocaleTimeString();
  }
}

// ── Build query params from filter inputs ────────────────────────────────────
function buildParams() {
  const p = {};
  const turnoverMin = parseFloat(document.getElementById('fTurnoverMin').value);
  const turnoverMax = parseFloat(document.getElementById('fTurnoverMax').value);
  const priceMax    = parseFloat(document.getElementById('fPriceMax').value);
  const circMvMax   = parseFloat(document.getElementById('fCircMvMax').value);
  const pctMax      = parseFloat(document.getElementById('fPctMax').value);
  const excludeSt   = document.getElementById('fExcludeSt').checked;

  if (!isNaN(turnoverMin)) p.turnover_min = turnoverMin;
  if (!isNaN(turnoverMax)) p.turnover_max = turnoverMax;
  if (!isNaN(priceMax))    p.price_max    = priceMax;
  if (!isNaN(circMvMax))   p.circ_mv_max  = circMvMax;
  if (!isNaN(pctMax))      p.pct_max      = pctMax;
  p.exclude_st = excludeSt ? '1' : '0';
  if (state.tradingDate) p.trading_date = state.tradingDate;
  return p;
}

// ── Render helpers ────────────────────────────────────────────────────────────
const _timeFmt = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', second: '2-digit',
  hour12: false,
});

const _dateFmt = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'UTC',   // trading_date is already local date (no TZ shift needed)
  year: 'numeric', month: '2-digit', day: '2-digit',
});

const _WDAY_ZH = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
const _WDAY_EN = ['Sun',  'Mon',  'Tue',  'Wed',  'Thu',  'Fri',  'Sat'];

function renderMeta(data) {
  const zh = window._currentLang === 'zh';
  if (!state.baseTradingDate) {
    state.baseTradingDate = data.fallback_from || data.trading_date || '';
  }
  document.getElementById('tableInfo').textContent =
    zh
      ? `${data.total} 只候选股 · 第 ${data.page || 1}/${data.total_pages || 1} 页`
      : `${data.total} candidates · Page ${data.page || 1}/${data.total_pages || 1}`;

  // Corresponding trading date (from backend calendar lookup)
  const tradingEl = document.getElementById('tradingDateDisplay');
  if (data.trading_date && tradingEl) {
    // Parse as UTC noon to avoid date-boundary shift on any timezone
    const d    = new Date(data.trading_date + 'T12:00:00Z');
    const wday = zh ? _WDAY_ZH[d.getUTCDay()] : _WDAY_EN[d.getUTCDay()];
    const dateStr = _dateFmt.format(d);
    tradingEl.textContent = zh ? `${dateStr}（${wday}）` : `${dateStr} (${wday})`;
    tradingEl.style.setProperty('color', '#111827', 'important');
  }
  const prevBtn = document.getElementById('prevTradingDateBtn');
  if (prevBtn) {
    const isHistoricalView = Boolean(state.tradingDate) || Boolean(data.fallback_used);
    prevBtn.style.display = isHistoricalView || data.previous_trading_date ? '' : 'none';
    prevBtn.textContent = isHistoricalView ? t('返回', 'Back') : t('前一天', 'Previous Day');
  }

  // Server-side AKShare fetch time (stays the same while cache is live)
  const serverEl = document.getElementById('serverFetchTime');
  const serverLabelEl = document.querySelector('[data-i18n="cand_akshare_label"]');
  if (data.generated_at && serverEl) {
    serverEl.textContent = _timeFmt.format(new Date(data.generated_at));
  } else if (serverEl) {
    serverEl.textContent = (
      data.source === 'history'
      || data.source === 'history_fallback'
      || data.source === 'snapshot'
    )
      ? t('历史缓存', 'History cache')
      : '—';
  }
  if (serverLabelEl) {
    if (data.source === 'snapshot') {
      serverLabelEl.textContent = t('快照时间：', 'Snapshot:');
    } else if (data.source === 'history' || data.source === 'history_fallback') {
      serverLabelEl.textContent = t('历史来源：', 'History:');
    } else {
      serverLabelEl.textContent = t('AKShare 抓取：', 'AKShare Fetch:');
    }
  }

  // Client-side request time (always "now")
  const clientEl = document.getElementById('clientFetchTime');
  if (clientEl) {
    clientEl.textContent = _timeFmt.format(new Date());
  }

  const infoEl = document.getElementById('tableInfo');
  if (data.fallback_used && infoEl) {
    infoEl.textContent += zh
      ? ` · 已自动回退到 ${data.trading_date}`
      : ` · Auto-fallback to ${data.trading_date}`;
  }
}

function renderPagination(data) {
  const wrap = document.getElementById('paginationBar');
  if (!wrap) return;

  const page = data.page || 1;
  const total = data.total || 0;
  const totalPages = data.total_pages || 1;

  if (totalPages <= 1) {
    wrap.style.display = 'none';
    wrap.innerHTML = '';
    return;
  }

  wrap.style.display = '';
  wrap.innerHTML = `
    <div class="pagination-summary">
      ${window._currentLang === 'zh' ? `共 ${total} 条，当前第 ${page} / ${totalPages} 页` : `${total} total, page ${page} / ${totalPages}`}
    </div>
    <div class="pagination-actions">
      <button class="btn btn--outline pagination-btn" data-page="${page - 1}" ${page <= 1 ? 'disabled' : ''}>${t('上一页', 'Prev')}</button>
      <button class="btn btn--outline pagination-btn" data-page="${page + 1}" ${page >= totalPages ? 'disabled' : ''}>${t('下一页', 'Next')}</button>
    </div>`;

  wrap.querySelectorAll('.pagination-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const nextPage = Number(btn.dataset.page);
      if (!nextPage || nextPage === state.page) return;
      state.page = nextPage;
      loadCandidates();
    });
  });
}

function renderTable(rows) {
  const container = document.getElementById('tableContainer');

  if (!rows.length) {
    const zh = window._currentLang === 'zh';
    container.innerHTML = `
      <div class="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="40" height="40">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <p>${zh ? '没有符合条件的候选股' : 'No candidates found'}</p>
        <span>${zh ? '尝试放宽筛选条件' : 'Try relaxing the filters'}</span>
      </div>`;
    return;
  }

  const cols = [
    { key: '#',                label: '#',                              align: 'right' },
    { key: 'code',             label: t('代码',      'Code'),           align: 'left'  },
    { key: 'name',             label: t('名称',      'Name'),           align: 'left'  },
    { key: 'candidate_score',  label: t('综合评分',   'Score'),          align: 'right' },
    { key: 'financial_check',  label: t('财务状态',   'Financial Check'), align: 'left'  },
    { key: 'triggered_signals',label: t('触发信号',   'Triggered Signals'), align: 'left' },
    { key: 'current_price',    label: t('现价 (元)', 'Price (¥)'),      align: 'right' },
    { key: 'turnover',         label: t('今日换手%', 'Turnover%'),      align: 'right' },
    { key: 'pct_change',       label: t('今日涨幅%', 'Change%'),        align: 'right' },
    { key: 'circ_mv',          label: t('流通市值 (亿)', 'Circ.Cap(bn)'), align: 'right' },
    { key: 'candidate_reason', label: t('要点',      'Notes'),          align: 'left'  },
  ];

  const thead = `<thead><tr>${cols.map(c =>
    `<th style="text-align:${c.align}">${c.label}</th>`
  ).join('')}</tr></thead>`;

  const fmt = (v, digits = 2, suffix = '') =>
    v != null && isFinite(v) ? v.toFixed(digits) + suffix : '—';
  const rowOffset = ((state.data?.page || 1) - 1) * (state.data?.page_size || state.pageSize);

  const tbody = rows.map((r, i) => {
    const pct    = r.pct_change;
    const pctCls = pct > 0 ? 'pct-up' : pct < 0 ? 'pct-dn' : '';
    const pctStr = pct != null && isFinite(pct)
      ? (pct > 0 ? `+${pct.toFixed(2)}%` : `${pct.toFixed(2)}%`)
      : '—';
    const financialCheck = r.financial_check || { status: 'no_data', triggered_signals: [], triggered_count: 0 };
    const triggeredSignals = financialCheck.triggered_signals?.length
      ? financialCheck.triggered_signals.join(', ')
      : t('无触发', 'None');

    const cells = [
      `<td style="text-align:right;color:var(--text-secondary)">${rowOffset + i + 1}</td>`,
      `<td><span class="badge badge-market badge-market-cn">CN</span> <code style="font-size:12px">${esc(r.code)}</code></td>`,
      `<td style="font-weight:500">${esc(r.name)}</td>`,
      `<td style="text-align:right;font-variant-numeric:tabular-nums;font-weight:600;color:var(--txt-1)">${fmt(r.candidate_score, 1)}</td>`,
      `<td>${renderFinancialCheck(financialCheck)}</td>`,
      `<td><span class="candidate-signal-list">${esc(triggeredSignals)}</span></td>`,
      `<td style="text-align:right;font-variant-numeric:tabular-nums">${fmt(r.current_price, 3)}</td>`,
      `<td style="text-align:right;font-variant-numeric:tabular-nums;color:var(--brand)">${fmt(r.turnover, 2, '%')}</td>`,
      `<td style="text-align:right" class="${pctCls}">${pctStr}</td>`,
      `<td style="text-align:right;font-variant-numeric:tabular-nums">${fmt(r.circ_mv, 1)}</td>`,
      `<td style="color:var(--text-secondary);font-size:12px">${esc(r.candidate_reason || '—')}</td>`,
    ];

    return `<tr class="clickable-row" data-code="${esc(r.code)}" data-market="CN">
      ${cells.join('')}
    </tr>`;
  }).join('');

  container.innerHTML = `<table class="data-table">${thead}<tbody>${tbody}</tbody></table>`;

  // Row click → company detail
  container.querySelectorAll('.clickable-row').forEach(row => {
    row.addEventListener('click', () => {
      const code   = row.dataset.code;
      const market = row.dataset.market;
      persistCandidatesState();
      saveReturnAnchor(code);
      window.location.href = `company.html?market=${market}&code=${code}&from=candidates`;
    });
  });

  restoreReturnAnchor(container, rows);
}

function renderFinancialCheck(check) {
  const map = {
    high_risk: { cls: 'badge-high-risk', zh: '高风险', en: 'High Risk' },
    warning:   { cls: 'badge-warning',   zh: '预警',   en: 'Warning' },
    pass:      { cls: 'badge-pass',      zh: '通过',   en: 'Pass' },
    no_data:   { cls: 'badge-no-data',   zh: '无数据', en: 'No Data' },
  };
  const item = map[check?.status] || map.no_data;
  return `<span class="badge financial-check-badge ${item.cls}">${t(item.zh, item.en)}</span>`;
}

function renderError(msg) {
  const container = document.getElementById('tableContainer');
  const pagination = document.getElementById('paginationBar');
  const zh = window._currentLang === 'zh';
  pagination.style.display = 'none';
  pagination.innerHTML = '';
  container.innerHTML = `
    <div class="empty-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="40" height="40">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
      <p>${zh ? '加载失败' : 'Load failed'}</p>
      <span>${esc(msg)}</span>
    </div>`;
  document.getElementById('tableInfo').textContent = '';
}

function setLoading(on) {
  document.getElementById('loadingTag').style.display = on ? '' : 'none';
  const loadingTag = document.getElementById('loadingTag');
  if (loadingTag) {
    loadingTag.textContent = state.refreshing
      ? t('刷新中', 'Refreshing')
      : t('加载中', 'Loading');
  }
}

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Controls ──────────────────────────────────────────────────────────────────
document.getElementById('applyBtn').addEventListener('click', () => {
  state.page = 1;
  loadCandidates();
});
document.getElementById('refreshBtn').addEventListener('click', () => {
  state.page = 1;
  loadCandidates({ forceRefresh: true });
});
document.getElementById('resetBtn').addEventListener('click', () => {
  applyStoredFilters(DEFAULT_FILTERS);
  state.page = 1;
  state.tradingDate = '';
  state.baseTradingDate = '';
  persistCandidatesState();
  loadCandidates();
});
document.getElementById('prevTradingDateBtn').addEventListener('click', () => {
  const isHistoricalView = Boolean(state.tradingDate) || Boolean(state.data?.fallback_used);
  if (isHistoricalView) {
    state.tradingDate = '';
    state.page = 1;
    loadCandidates({ forceRefresh: true });
    return;
  }
  if (!state.data?.previous_trading_date) return;
  state.tradingDate = state.data.previous_trading_date;
  state.page = 1;
  loadCandidates();
});

// Enter key in any filter input triggers apply
document.getElementById('filterBar').addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    state.page = 1;
    loadCandidates();
  }
});

// ── Init ──────────────────────────────────────────────────────────────────────
restoreCandidatesState();
checkHealth();
loadCandidates();

function restoreCandidatesState() {
  const query = new URLSearchParams(window.location.search);
  const queryState = {
    turnoverMin: query.get('turnover_min'),
    turnoverMax: query.get('turnover_max'),
    priceMax: query.get('price_max'),
    circMvMax: query.get('circ_mv_max'),
    pctMax: query.get('pct_max'),
    excludeSt: query.get('exclude_st'),
    page: query.get('page'),
    tradingDate: query.get('trading_date'),
  };
  try {
    const saved = JSON.parse(localStorage.getItem(FILTERS_KEY) || 'null');
    const merged = {
      ...DEFAULT_FILTERS,
      ...(saved && typeof saved === 'object' ? saved : {}),
      ...(queryState.turnoverMin != null ? { turnoverMin: queryState.turnoverMin } : {}),
      ...(queryState.turnoverMax != null ? { turnoverMax: queryState.turnoverMax } : {}),
      ...(queryState.priceMax != null ? { priceMax: queryState.priceMax } : {}),
      ...(queryState.circMvMax != null ? { circMvMax: queryState.circMvMax } : {}),
      ...(queryState.pctMax != null ? { pctMax: queryState.pctMax } : {}),
      ...(queryState.excludeSt != null ? { excludeSt: queryState.excludeSt !== '0' } : {}),
      ...(queryState.page != null ? { page: Number(queryState.page) } : {}),
      ...(queryState.tradingDate != null ? { tradingDate: queryState.tradingDate } : {}),
    };
    applyStoredFilters(merged);
    state.page = Number(merged.page) > 0 ? Number(merged.page) : 1;
    state.tradingDate = merged.tradingDate || '';
    state.baseTradingDate = '';
  } catch {
    applyStoredFilters(DEFAULT_FILTERS);
    state.page = 1;
    state.tradingDate = '';
    state.baseTradingDate = '';
  }
}

function syncStateToUrl() {
  const params = new URLSearchParams();
  const filterState = currentFilterState();
  params.set('turnover_min', filterState.turnoverMin);
  if (filterState.turnoverMax) params.set('turnover_max', filterState.turnoverMax);
  params.set('price_max', filterState.priceMax);
  params.set('circ_mv_max', filterState.circMvMax);
  params.set('pct_max', filterState.pctMax);
  params.set('exclude_st', filterState.excludeSt ? '1' : '0');
  params.set('page', String(state.page));
  if (state.tradingDate) params.set('trading_date', state.tradingDate);
  history.replaceState(null, '', `${window.location.pathname}?${params.toString()}`);
}

function currentFilterState() {
  return {
    turnoverMin: document.getElementById('fTurnoverMin').value,
    turnoverMax: document.getElementById('fTurnoverMax').value,
    priceMax: document.getElementById('fPriceMax').value,
    circMvMax: document.getElementById('fCircMvMax').value,
    pctMax: document.getElementById('fPctMax').value,
    excludeSt: document.getElementById('fExcludeSt').checked,
  };
}

function applyStoredFilters(filters) {
  document.getElementById('fTurnoverMin').value = filters.turnoverMin ?? DEFAULT_FILTERS.turnoverMin;
  document.getElementById('fTurnoverMax').value = filters.turnoverMax ?? DEFAULT_FILTERS.turnoverMax;
  document.getElementById('fPriceMax').value = filters.priceMax ?? DEFAULT_FILTERS.priceMax;
  document.getElementById('fCircMvMax').value = filters.circMvMax ?? DEFAULT_FILTERS.circMvMax;
  document.getElementById('fPctMax').value = filters.pctMax ?? DEFAULT_FILTERS.pctMax;
  document.getElementById('fExcludeSt').checked = Boolean(filters.excludeSt);
}

function persistCandidatesState() {
  const payload = {
    ...currentFilterState(),
    page: state.page,
    tradingDate: state.tradingDate,
  };
  localStorage.setItem(FILTERS_KEY, JSON.stringify(payload));
}

function saveReturnAnchor(code) {
  sessionStorage.setItem(RETURN_KEY, JSON.stringify({
    code,
    page: state.page,
    scrollTop: window.scrollY || 0,
    ts: Date.now(),
  }));
}

function restoreReturnAnchor(container, rows) {
  let payload = null;
  try {
    payload = JSON.parse(sessionStorage.getItem(RETURN_KEY) || 'null');
  } catch {}
  if (!payload || payload.page !== (state.data?.page || state.page)) return;
  const row = container.querySelector(`.clickable-row[data-code="${CSS.escape(payload.code || '')}"]`);
  if (!row) {
    if (Number.isFinite(payload.scrollTop)) {
      requestAnimationFrame(() => window.scrollTo({ top: Number(payload.scrollTop), behavior: 'auto' }));
    } else {
      const approxIndex = rows.findIndex(item => item.code === payload.code);
      if (approxIndex >= 0) {
        requestAnimationFrame(() => window.scrollTo({ top: approxIndex * 56, behavior: 'auto' }));
      }
    }
    sessionStorage.removeItem(RETURN_KEY);
    return;
  }
  requestAnimationFrame(() => row.scrollIntoView({ block: 'center', behavior: 'auto' }));
  sessionStorage.removeItem(RETURN_KEY);
}
