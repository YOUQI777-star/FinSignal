'use strict';

/* ============================================================
   I18N HELPER
   ============================================================ */
const t = (zh, en) => window._currentLang === 'zh' ? zh : en;

/* ============================================================
   SIGNAL META — names, descriptions, severity, thresholds
   ============================================================ */
const SIGNAL_META = {
  F1: {
    name: () => t('应收账款异常增长', 'AR Abnormal Growth'),
    desc: () => t(
      '应收账款增速远超营收，可能存在渠道压货或虚增收入的风险。',
      'Accounts receivable is growing significantly faster than revenue, suggesting potential channel stuffing or inflated sales recognition.'
    ),
    threshold: 'AR/Revenue ratio grows >30% YoY',
    severity: 'high',
  },
  F2: {
    name: () => t('现金流背离', 'Cash Flow Divergence'),
    desc: () => t(
      '净利润为正但经营性现金流为负，盈利质量存疑，利润可能无法转化为真实现金。',
      'Net profit is positive but operating cash flow is negative, indicating earnings may not be converting to real cash.'
    ),
    threshold: 'Net profit > 0 AND operating cash flow < 0',
    severity: 'high',
  },
  F3: {
    name: () => t('高杠杆风险', 'High Leverage'),
    desc: () => t(
      '连续两年资产负债率超过70%，对债务融资高度依赖，财务风险较高。',
      'Debt-to-assets ratio exceeds 70% for two consecutive years, indicating heavy reliance on debt financing.'
    ),
    threshold: 'Total debt / Total assets > 70% for 2 years',
    severity: 'medium',
  },
  F4: {
    name: () => t('毛利率骤降', 'Margin Decline'),
    desc: () => t(
      '净利率同比下滑超过10个百分点，盈利能力明显恶化。',
      'Net profit margin has dropped more than 10 percentage points year-over-year, indicating deteriorating profitability.'
    ),
    threshold: 'Net margin drops >10pp YoY',
    severity: 'medium',
  },
  G1: {
    name: () => t('大股东高比例质押', 'Pledge Ratio Alert'),
    desc: () => t(
      '控股股东大比例质押股份，存在治理风险和偿债风险。',
      'Controlling shareholders have pledged a significant portion of their shares, creating governance and solvency risk.'
    ),
    threshold: 'Pledge ratio > 50%',
    severity: 'medium',
  },
  G3: {
    name: () => t('两职合一且独董不足', 'Board Independence'),
    desc: () => t(
      '独立董事占比不足董事会三分之一，监督职能可能受到削弱。',
      'Independent directors constitute less than one-third of the board, potentially weakening oversight.'
    ),
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
  sourceFrom: '',
  data:   null,
  usedMock: false,
  reportLoading: false,
  candidateContext: null,
  historyDays: 10,
  historyRange: null,
  historyAutoRetryKey: '',
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
  state.sourceFrom = p.get('from') || '';
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
    label.textContent = (window._currentLang === 'zh') ? 'API 已连接' : 'API Connected';
  } catch {
    dot.className   = 'health-dot offline';
    label.textContent = (window._currentLang === 'zh') ? 'API 离线' : 'API Offline';
  }
}

/* ============================================================
   LOAD COMPANY DATA
   ============================================================ */
async function loadCompany(fresh = false) {
  setLoadingUI(true);
  state.candidateContext = null;

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
    await loadCandidateContext();
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
  renderCandidateContext();
  renderScorePanel(data);
  loadTurnoverHistory();
  renderSummaryCards(data);
  renderSignalSection('financialSignals',  'finMeta',  data.financial_signals  || []);
  renderSignalSection('governanceSignals', 'govMeta',  data.governance_signals || []);
  loadGraph(data.market, data.code);
  initFavoriteBtn();
}

function renderScorePanel(data) {
  const panel = document.getElementById('scorePanel');
  const body = document.getElementById('scorePanelBody');
  const meta = document.getElementById('scorePanelMeta');
  if (!panel || !body || !meta) return;

  const breakdown = data.score_breakdown || state.candidateContext?.score_breakdown;
  const score = data.candidate_score ?? state.candidateContext?.candidate_score;
  const formula = data.score_formula || state.candidateContext?.score_formula;

  if (score == null || !breakdown) {
    panel.style.display = 'none';
    body.innerHTML = '';
    meta.textContent = '';
    return;
  }

  panel.style.display = '';
  meta.textContent = t(`总分 ${Number(score).toFixed(1)}`, `Score ${Number(score).toFixed(1)}`);

  const items = [
    ['换手质量', 'Turnover Quality', breakdown.turnover_quality],
    ['涨幅健康度', 'Pct Health', breakdown.pct_health],
    ['流通市值匹配', 'Circ.MV Fit', breakdown.circ_mv_fit],
    ['持续活跃度', 'Sustained Activity', breakdown.sustained_activity],
    ['结构强度', 'Structure Strength', breakdown.structure_strength],
    ['行业加分', 'Industry Bonus', breakdown.industry_bonus],
  ];
  const scoreValue = Number(score).toFixed(1);

  body.innerHTML = `
    <div class="score-panel-shell">
      <div class="score-panel-hero">
        <div class="score-hero-scorecard">
          <span class="score-hero-label">${t('综合评分', 'Composite Score')}</span>
          <strong class="score-hero-value">${scoreValue}</strong>
          <span class="score-hero-footnote">${t('候选排序主分数', 'Primary candidate ranking score')}</span>
        </div>
        <div class="score-hero-main">
          <div class="score-total-copy">
            <div class="score-total-title">${t('评分公式', 'Score Formula')}</div>
            <div class="score-total-formula">${esc(formula || '—')}</div>
          </div>
          <div class="score-hero-note">
            ${t('分数越高，代表换手质量、持续活跃度与结构强度的综合表现越强。', 'Higher scores indicate stronger combined turnover quality, sustained activity, and structural strength.')}
          </div>
        </div>
      </div>
      <div class="score-breakdown-grid">
        ${items.map(([zh, en, value]) => `
          <div class="score-breakdown-item">
            <span>${t(zh, en)}</span>
            <strong>${value != null ? Number(value).toFixed(1) : '—'}</strong>
          </div>
        `).join('')}
      </div>
    </div>`;
}

async function loadCandidateContext() {
  if (state.market !== 'CN' || state.sourceFrom !== 'candidates') return;
  try {
    state.candidateContext = await API.getCandidateDetail(state.code);
  } catch (err) {
    console.warn('[candidate-context] unavailable:', err.message);
    state.candidateContext = null;
  }
}

function renderCandidateContext() {
  const el = document.getElementById('candidateContext');
  if (!el) return;

  if (state.sourceFrom !== 'candidates' || !state.candidateContext) {
    el.style.display = 'none';
    el.innerHTML = '';
    return;
  }

  const ctx = state.candidateContext;
  const check = ctx.financial_check || { status: 'no_data', triggered_signals: [], triggered_count: 0 };
  const signalText = check.triggered_signals?.length ? check.triggered_signals.join(', ') : t('无触发', 'None');
  const score = ctx.candidate_score != null ? Number(ctx.candidate_score).toFixed(1) : '—';
  const scoreFormula = ctx.score_formula || '—';

  el.style.display = '';
  el.innerHTML = `
    <div class="candidate-context-head">
      <span class="candidate-context-eyebrow">${t('候选池上下文', 'Candidate Context')}</span>
      ${renderFinancialCheckBadge(check)}
    </div>
    <div class="candidate-context-body">
      <div class="candidate-context-item">
        <span class="candidate-context-label">${t('入池原因', 'Why selected')}</span>
        <span class="candidate-context-value">${esc(ctx.candidate_reason || '—')}</span>
      </div>
      <div class="candidate-context-item">
        <span class="candidate-context-label">${t('今日换手', 'Turnover today')}</span>
        <span class="candidate-context-value">${formatMaybePct(ctx.turnover)}</span>
      </div>
      <div class="candidate-context-item">
        <span class="candidate-context-label">${t('触发信号', 'Triggered signals')}</span>
        <span class="candidate-context-value">${esc(signalText)}</span>
      </div>
      <div class="candidate-context-item">
        <span class="candidate-context-label">${t('综合评分', 'Score')}</span>
        <span class="candidate-context-value"><strong>${esc(score)}</strong></span>
      </div>
      <div class="candidate-context-item candidate-context-item--wide">
        <span class="candidate-context-label">${t('评分公式', 'Score formula')}</span>
        <span class="candidate-context-value candidate-context-formula">${esc(scoreFormula)}</span>
      </div>
    </div>`;
}

async function loadTurnoverHistory() {
  const body = document.getElementById('turnoverHistoryBody');
  const meta = document.getElementById('turnoverHistoryMeta');
  if (!body || !meta) return;

  renderTurnoverHistoryState('loading', t('历史换手率加载中…', 'Loading turnover history…'));
  try {
    const params = state.historyRange || { days: state.historyDays };
    const result = await API.getTurnoverHistory(state.market, state.code, params);
    const retryKey = JSON.stringify(params);
    if (
      result.summary?.available_points === 0 &&
      state.market === 'CN' &&
      state.historyAutoRetryKey !== retryKey
    ) {
      state.historyAutoRetryKey = retryKey;
      renderTurnoverHistoryState('hydrating', t('所选区间暂无缓存，正在尝试实时补抓…', 'No cached history for this range, trying live hydration…'));
      const refreshed = await API.getTurnoverHistory(state.market, state.code, params);
      renderTurnoverHistory(refreshed);
      return;
    }
    state.historyAutoRetryKey = '';
    renderTurnoverHistory(result);
  } catch (err) {
    meta.textContent = '';
    renderTurnoverHistoryState('failed', t('历史换手率暂不可用', 'Turnover history unavailable'), err.message);
  }
}

function renderTurnoverHistory(result) {
  const body = document.getElementById('turnoverHistoryBody');
  const meta = document.getElementById('turnoverHistoryMeta');
  const rows = result.results || [];
  const availableRows = rows.filter(item => item.has_data);
  const hydrationStatus = result.hydration?.status || 'not_needed';
  const statusLabel = hydrationStatus === 'success'
    ? t('补抓完成', 'Hydration complete')
    : hydrationStatus === 'hydrating'
      ? t('正在补抓', 'Hydrating')
      : hydrationStatus === 'failed'
        ? t('补抓失败', 'Hydration failed')
        : t('本地历史缓存', 'Cached history');

  meta.textContent = availableRows.length
    ? t(`${availableRows.length} 个有效交易日 · ${statusLabel}`, `${availableRows.length} valid trading days · ${statusLabel}`)
    : t('暂无历史数据', 'No history yet');

  if (!availableRows.length) {
    renderTurnoverHistoryState(
      result.display_status === 'fetch_failed' ? 'failed' : 'empty',
      t('暂无历史换手率数据', 'No turnover history yet'),
      result.hydration?.reason || t('这一时间段还没有可用的换手率历史。', 'No turnover history is available for this range yet.'),
    );
    return;
  }

  const width = 640;
  const height = 276;
  const padLeft = 56;
  const padRight = 20;
  const padTop = 18;
  const padBottom = 36;
  const values = availableRows.map(item => Number(item.turnover_rate ?? 0));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const axisStep = max > 20 ? 4 : 2;
  const axisMax = Math.max(12, Math.ceil(max / axisStep) * axisStep);
  const axisMin = 0;
  const range = axisMax - axisMin || axisStep;
  const axisTicks = [];
  for (let tick = axisMax; tick >= axisMin; tick -= axisStep) {
    axisTicks.push({ value: tick, label: `${tick.toFixed(0)}%` });
  }
  const chartWidth = width - padLeft - padRight;
  const chartHeight = height - padTop - padBottom;
  const coords = rows.map((item, idx) => {
    const x = padLeft + (idx / Math.max(rows.length - 1, 1)) * chartWidth;
    const value = item.has_data ? Number(item.turnover_rate ?? 0) : null;
    const safeValue = value == null ? null : Math.min(Math.max(value, axisMin), axisMax);
    const y = safeValue == null ? null : padTop + (1 - ((safeValue - axisMin) / range)) * chartHeight;
    return { x, y, date: item.date, value, hasData: Boolean(item.has_data) };
  });
  const segments = [];
  let current = [];
  for (const point of coords) {
    if (point.hasData && point.y != null) {
      current.push(point);
    } else if (current.length) {
      segments.push(current);
      current = [];
    }
  }
  if (current.length) segments.push(current);
  const xTickIndexes = Array.from(new Set([
    0,
    Math.floor((rows.length - 1) / 3),
    Math.floor(((rows.length - 1) * 2) / 3),
    rows.length - 1,
  ])).filter(idx => idx >= 0 && idx < rows.length);
  const avg = values.reduce((sum, value) => sum + value, 0) / values.length;
  const sparseMode = availableRows.length <= 3;
  const latestRow = availableRows[availableRows.length - 1];
  const summaryItems = [
    [t('最近值', 'Latest'), `${Number(latestRow?.turnover_rate ?? values[values.length - 1]).toFixed(2)}%`],
    [t('区间均值', 'Average'), `${avg.toFixed(2)}%`],
    [t('最大值', 'High'), `${max.toFixed(2)}%`],
    [t('最小值', 'Low'), `${min.toFixed(2)}%`],
  ];

  body.innerHTML = `
    <div class="turnover-history-shell">
      <div class="turnover-history-summary">
        ${summaryItems.map(([label, value]) => `
          <div class="turnover-summary-pill">
            <span>${esc(label)}</span>
            <strong>${esc(value)}</strong>
          </div>
        `).join('')}
      </div>
      <div class="turnover-history-chart-wrap">
        <div class="turnover-history-status-line">
          <span class="turnover-history-status turnover-history-status--${result.display_status || 'ready'}">${statusLabel}</span>
          <span class="turnover-history-status-meta">${t(`缺失 ${result.summary?.missing_points || 0} 天`, `${result.summary?.missing_points || 0} missing days`)}</span>
        </div>
        <div class="turnover-history-chart-head">
          <span>${t('区间走势', 'Range Trend')}</span>
          <span>${t(`0 值 ${result.summary?.zero_value_points || 0} 天`, `${result.summary?.zero_value_points || 0} zero-value days`)}</span>
        </div>
        <svg class="turnover-history-chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
          ${axisTicks.map((tick) => {
            const y = padTop + (1 - ((tick.value - axisMin) / range)) * chartHeight;
            return `
              <line x1="${padLeft}" y1="${y}" x2="${width - padRight}" y2="${y}" class="turnover-history-grid"></line>
              <text x="${padLeft - 10}" y="${y + 4}" text-anchor="end" class="turnover-history-y-label">${esc(tick.label)}</text>
            `;
          }).join('')}
          <line x1="${padLeft}" y1="${height - padBottom}" x2="${width - padRight}" y2="${height - padBottom}" class="turnover-history-base"></line>
          ${segments.map((segment) => {
            const segmentPoints = segment.map(({ x, y }) => `${x},${y}`).join(' ');
            const areaPoints = sparseMode || segment.length <= 1
              ? ''
              : `${segment[0].x},${height - padBottom} ${segmentPoints} ${segment[segment.length - 1].x},${height - padBottom}`;
            return `
              ${areaPoints ? `<polygon class="turnover-history-area" points="${areaPoints}"></polygon>` : ''}
              ${segment.length > 1 ? `<polyline class="turnover-history-line" points="${segmentPoints}"></polyline>` : ''}
            `;
          }).join('')}
          ${coords.map((item) => {
            if (!item.hasData || item.y == null) {
              return `<circle cx="${item.x}" cy="${height - padBottom}" r="3" class="turnover-history-missing-dot"></circle>`;
            }
            return `<circle cx="${item.x}" cy="${item.y}" r="${sparseMode ? 5.5 : 4.5}" class="turnover-history-dot" data-date="${esc(item.date)}" data-value="${item.value.toFixed(2)}"></circle>`;
          }).join('')}
          ${xTickIndexes.map((idx) => {
            const point = coords[idx];
            return `<text x="${point.x}" y="${height - 10}" text-anchor="${idx === 0 ? 'start' : idx === rows.length - 1 ? 'end' : 'middle'}" class="turnover-history-x-label">${esc(point.date)}</text>`;
          }).join('')}
        </svg>
        <div class="turnover-history-tooltip" id="turnoverHistoryTooltip" style="display:none"></div>
      </div>
    <div class="turnover-history-table">
      ${rows.slice().reverse().map(item => `
        <div class="turnover-history-row ${item.has_data ? '' : 'turnover-history-row--missing'}">
          <span>${esc(item.date)}</span>
          <strong>${item.has_data ? `${Number(item.turnover_rate ?? 0).toFixed(2)}%` : t('未抓到', 'Missing')}</strong>
        </div>`).join('')}
    </div>`;

  bindTurnoverTooltip();
}

function renderTurnoverHistoryState(kind, title, detail = '') {
  const body = document.getElementById('turnoverHistoryBody');
  if (!body) return;
  body.innerHTML = `
    <div class="report-placeholder turnover-history-state turnover-history-state--${kind}">
      <p>${esc(title)}</p>
      ${detail ? `<span>${esc(detail)}</span>` : ''}
    </div>`;
}

function bindTurnoverTooltip() {
  const wrap = document.querySelector('.turnover-history-chart-wrap');
  const tooltip = document.getElementById('turnoverHistoryTooltip');
  if (!wrap || !tooltip) return;
  wrap.querySelectorAll('.turnover-history-dot').forEach(dot => {
    dot.addEventListener('mouseenter', () => {
      tooltip.style.display = 'block';
      tooltip.innerHTML = `
        <strong>${dot.dataset.date}</strong>
        <span>${t('换手率', 'Turnover')}: ${dot.dataset.value}%</span>`;
    });
    dot.addEventListener('mousemove', event => {
      const bounds = wrap.getBoundingClientRect();
      tooltip.style.left = `${event.clientX - bounds.left + 12}px`;
      tooltip.style.top = `${event.clientY - bounds.top - 12}px`;
    });
    dot.addEventListener('mouseleave', () => {
      tooltip.style.display = 'none';
    });
  });
}

/* ============================================================
   SUPPLY CHAIN GRAPH
   ============================================================ */
async function loadGraph(market, code) {
  if (!market || !code) return;
  const section = document.getElementById('graphSection');
  const note    = document.getElementById('graphNote');
  section.style.display = '';
  note.textContent = t('图谱加载中…', 'Loading graph…');
  try {
    const data = await API.getGraph(market, code);
    renderGraph(data);
  } catch (err) {
    note.textContent = t(`图谱不可用：${err.message}`, `Graph unavailable: ${err.message}`);
    document.getElementById('graphMeta').textContent = '';
    console.warn('[graph] failed to load:', err.message);
  }
}

function renderGraph(data) {
  const section = document.getElementById('graphSection');
  const meta    = document.getElementById('graphMeta');
  const note    = document.getElementById('graphNote');
  const nodes   = data.nodes || [];
  const edges   = data.edges || [];

  if (!nodes.length) {
    note.textContent = data.message || t('暂无供应链数据。', 'No supply chain data for this company.');
    return;
  }

  meta.textContent = t(`${nodes.length} 节点 · ${edges.length} 边`, `${nodes.length} nodes · ${edges.length} edges`);

  if (typeof cytoscape === 'undefined') {
    note.textContent = t('图谱库未加载。', 'Graph library not loaded.');
    return;
  }

  const cy = cytoscape({
    container: document.getElementById('chainGraph'),
    elements: { nodes, edges },
    style: [
      {
        selector: 'node',
        style: {
          label: 'data(name)',
          'font-size': 11,
          'text-valign': 'bottom',
          'text-margin-y': 4,
          'text-wrap': 'wrap',
          'text-max-width': 90,
          color: '#374151',
        },
      },
      {
        selector: 'node[type="Company"]',
        style: {
          'background-color': '#3b82f6',
          width: 46,
          height: 46,
          'font-size': 13,
          'font-weight': 600,
          color: '#1d4ed8',
          'z-index': 10,
        },
      },
      {
        selector: 'node[type="Industry"]',
        style: {
          'background-color': '#10b981',
          shape: 'round-rectangle',
          width: 36,
          height: 36,
          color: '#065f46',
        },
      },
      {
        selector: 'node[type="Product"]',
        style: {
          'background-color': '#f59e0b',
          shape: 'ellipse',
          width: 28,
          height: 28,
          color: '#92400e',
        },
      },
      {
        selector: 'node[direction="upstream"]',
        style: { 'background-color': '#6366f1' },
      },
      {
        selector: 'node[direction="downstream"]',
        style: { 'background-color': '#ec4899' },
      },
      {
        selector: 'edge',
        style: {
          width: 1.5,
          'line-color': '#d1d5db',
          'target-arrow-color': '#d1d5db',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          label: 'data(relation)',
          'font-size': 9,
          'text-rotation': 'autorotate',
          color: '#9ca3af',
        },
      },
    ],
    layout: {
      name: 'cose',
      animate: false,
      randomize: false,
      nodeRepulsion: 4500,
      idealEdgeLength: 80,
      gravity: 0.25,
      padding: 24,
    },
  });

  const totalNodes = nodes.length;
  note.textContent = totalNodes > 30
    ? t(`显示 ${totalNodes} 个节点。滚轮/捏合缩放，拖拽平移。`, `Showing ${totalNodes} nodes. Scroll / pinch to zoom, drag to pan.`)
    : t('滚轮/捏合缩放，拖拽平移。', 'Scroll / pinch to zoom, drag to pan.');
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
        <div class="scard-label">${t('规则总数', 'Rules Evaluated')}</div>
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
        <div class="scard-label">${t('触发信号数', 'Triggered Signals')}</div>
      </div>
      ${cnt > 0 ? `<div class="scard-note">${t(`${cnt} 条规则需关注`, `${cnt} rule${cnt > 1 ? 's' : ''} require attention`)}</div>` : ''}
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
        <div class="scard-label">${t('数据层级', 'Data Tier')}</div>
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
        <div class="scard-label">${t('规则覆盖', 'Rule Coverage')}</div>
        <div class="status-breakdown">
          <span class="status-dot-item">
            <span class="status-dot status-dot--triggered"></span>${sc.triggered ?? 0} ${t('触发', 'triggered')}
          </span>
          <span class="status-dot-item">
            <span class="status-dot status-dot--ok"></span>${sc.ok ?? 0} ${t('正常', 'ok')}
          </span>
          <span class="status-dot-item">
            <span class="status-dot status-dot--na"></span>${sc.not_available ?? 0} ${t('缺数据', 'n/a')}
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
    ? t(`${signals.length} 条规则 · ${triggered} 条触发`, `${signals.length} rules · ${triggered} triggered`)
    : t('0 条规则', '0 rules');

  if (!signals.length) {
    container.innerHTML = `<div class="sig-empty">${t('该类别暂无信号', 'No signals in this category')}</div>`;
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
    ? `<span class="badge badge-triggered">${t('触发', 'Triggered')}</span>`
    : status === 'not_available'
    ? '<span class="badge badge-na">N/A</span>'
    : `<span class="badge badge-ok">${t('正常', 'OK')}</span>`;

  // Use severity from actual signal data, fall back to SIGNAL_META
  const severity = sig.severity || meta.severity;
  const sevLabel = { high: t('高', 'High'), medium: t('中', 'Medium'), low: t('低', 'Low') };
  const sevBadge = severity
    ? `<span class="badge badge-${severity}">${sevLabel[severity] || severity}</span>`
    : '';

  // message: from backend, or fall back to SIGNAL_META desc (which is now a function)
  const metaDesc = typeof meta.desc === 'function' ? meta.desc() : (meta.desc || '—');
  const message  = sig.message || metaDesc;
  // Use threshold from actual signal data, fall back to SIGNAL_META
  const thresholdText = sig.threshold || meta.threshold;
  const threshold = thresholdText
    ? `<div class="sig-threshold">
        <span class="sig-threshold-label">${t('阈值：', 'Threshold:')}</span>
        <span class="sig-threshold-val">${esc(thresholdText)}</span>
       </div>`
    : '';

  // Field is 'value' from backend (not 'values')
  const valBlock = renderValues(sig.value !== undefined ? sig.value : sig.values);

  // Use signal name from data if available, fall back to SIGNAL_META (now a function)
  const metaName = typeof meta.name === 'function' ? meta.name() : (meta.name || sig.signal_id);
  const sigName  = sig.name || metaName;

  const footer = sig.year
    ? `<div class="sig-card-ft">
        <span class="sig-ft-item"><span class="sig-ft-label">${t('年份：', 'Year:')} </span>${sig.year}</span>
        ${sig.source ? `<span class="sig-ft-item"><span class="sig-ft-label">${t('来源：', 'Source:')} </span>${esc(sig.source)}</span>` : ''}
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
      <span>${t('AI 风险分析生成中…', 'Generating AI risk analysis…')}</span>
    </div>`;

  try {
    const result = await API.generateReport(state.market, state.code);
    const text   = result.report_markdown || result.report || result.content || result.text || JSON.stringify(result, null, 2);

    body.innerHTML = `<pre class="report-content">${esc(text)}</pre>`;
    copy.style.display = 'block';
    showToast(t('报告已生成', 'Report generated'), 'success');
  } catch (err) {
    body.innerHTML = `
      <div class="report-placeholder">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        <p>${t('报告生成失败', 'Report generation failed')}</p>
        <span>${esc(err.message)}</span>
      </div>`;
    showToast(t('报告生成失败', 'Failed to generate report'), 'error');
  } finally {
    state.reportLoading = false;
    btn.disabled = false;
  }
}

function copyReport() {
  const el = document.querySelector('.report-content');
  if (!el) return;
  navigator.clipboard.writeText(el.textContent || '').then(() => {
    showToast(t('已复制到剪贴板', 'Copied to clipboard'), 'success');
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
      <p>${t('公司数据加载失败', 'Failed to load company')}</p>
      <span>${esc(msg)}</span>
      <button class="btn btn--primary" style="margin-top:8px" onclick="loadCompany()">${t('重试', 'Retry')}</button>
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
  document.querySelectorAll('.history-range-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      state.historyDays = Number(btn.dataset.days) || 10;
      state.historyRange = null;
      document.getElementById('turnoverStartDate').value = '';
      document.getElementById('turnoverEndDate').value = '';
      loadTurnoverHistory();
    });
  });
  document.getElementById('turnoverHistoryApplyBtn')?.addEventListener('click', () => {
    const start = document.getElementById('turnoverStartDate').value;
    const end = document.getElementById('turnoverEndDate').value;
    state.historyRange = (start || end) ? { start, end } : null;
    loadTurnoverHistory();
  });
}

/* ============================================================
   UTILITY
   ============================================================ */
function tierClass(t) {
  if (t === 'real_financial_available')    return 'tier-full';
  if (t === 'partial_financial_available') return 'tier-partial';
  return 'tier-shell';
}

function tierLabel(tier) {
  if (tier === 'real_financial_available')    return t('完整数据', 'Full Data');
  if (tier === 'partial_financial_available') return t('部分数据', 'Partial');
  return t('仅基础', 'Shell Only');
}

function renderFinancialCheckBadge(check) {
  const map = {
    high_risk: { cls: 'badge-high-risk', zh: '高风险', en: 'High Risk' },
    warning:   { cls: 'badge-warning', zh: '预警', en: 'Warning' },
    pass:      { cls: 'badge-pass', zh: '通过', en: 'Pass' },
    no_data:   { cls: 'badge-no-data', zh: '无数据', en: 'No Data' },
  };
  const item = map[check?.status] || map.no_data;
  return `<span class="badge financial-check-badge ${item.cls}">${t(item.zh, item.en)}</span>`;
}

function formatMaybePct(value) {
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

/* ============================================================
   FAVORITE BUTTON
   ============================================================ */
async function initFavoriteBtn() {
  const btn = document.getElementById('favoriteBtn');
  if (!btn) return;

  const market = state.market;
  const code = state.code;

  // Remove any previous listeners by replacing the element
  const fresh = btn.cloneNode(true);
  btn.parentNode.replaceChild(fresh, btn);
  const favBtn = document.getElementById('favoriteBtn');

  if (!window.AUTH_UI?.isLoggedIn()) {
    favBtn.addEventListener('click', () => window.AUTH_UI?.openAuthModal());
    return;
  }

  // Check if already favorited
  try {
    const data = await AUTH.getFavorites();
    const isFav = (data.results || []).some(f => f.market === market && f.code === code);
    setFavBtn(isFav);
  } catch {}

  favBtn.addEventListener('click', async () => {
    const isActive = favBtn.classList.contains('fav-btn--active');
    if (isActive) {
      await AUTH.removeFavorite(market, code);
      setFavBtn(false);
    } else {
      const name = document.getElementById('companyName')?.textContent || code;
      await AUTH.addFavorite(market, code, name);
      setFavBtn(true);
    }
  });
}

function setFavBtn(active) {
  const btn = document.getElementById('favoriteBtn');
  const label = document.getElementById('favBtnLabel');
  if (!btn || !label) return;
  const zh = window._currentLang === 'zh';
  btn.classList.toggle('fav-btn--active', active);
  label.textContent = active ? (zh ? '已收藏' : 'Saved') : (zh ? '收藏' : 'Save');
}
