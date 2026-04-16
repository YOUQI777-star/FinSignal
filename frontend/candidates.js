'use strict';

/* ============================================================
   CANDIDATES PAGE
   持续换手候选池 — reads from /api/candidates (cache only)
   ============================================================ */

const state = {
  data:     null,
  filtered: [],
};

// ── Health check (same pattern as other pages) ──────────────────────────────
async function checkHealth() {
  const dot   = document.getElementById('healthDot');
  const label = document.getElementById('healthLabel');
  try {
    await API.health();
    dot.className   = 'health-dot health-dot--ok';
    label.textContent = 'API Connected';
  } catch {
    dot.className   = 'health-dot health-dot--err';
    label.textContent = 'API Offline';
  }
}

// ── Load candidates from API ─────────────────────────────────────────────────
async function loadCandidates() {
  setLoading(true);
  document.getElementById('tableContainer').innerHTML = '';
  document.getElementById('tableInfo').textContent    = '';

  try {
    const params = buildParams();
    const qs = new URLSearchParams(params).toString();
    const data = await apiFetch(`/api/candidates${qs ? '?' + qs : ''}`);
    state.data     = data;
    state.filtered = data.results || [];
    renderTable(state.filtered);
    renderMeta(data);
  } catch (err) {
    renderError(err.message);
  } finally {
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
  const shareMax    = parseFloat(document.getElementById('fShareMax').value);
  const pctMax      = parseFloat(document.getElementById('fPctMax').value);
  const excludeSt   = document.getElementById('fExcludeSt').checked;

  if (!isNaN(turnoverMin)) p.turnover_min = turnoverMin;
  if (!isNaN(turnoverMax)) p.turnover_max = turnoverMax;
  if (!isNaN(priceMax))    p.price_max    = priceMax;
  if (!isNaN(shareMax))    p.share_max    = shareMax;
  if (!isNaN(pctMax))      p.pct_max      = pctMax;
  p.exclude_st = excludeSt ? '1' : '0';
  p.limit = 300;
  return p;
}

// ── Render helpers ────────────────────────────────────────────────────────────
function renderMeta(data) {
  document.getElementById('tableInfo').textContent =
    `${data.total} 只候选股`;

  if (data.generated_at) {
    const d = new Date(data.generated_at);
    document.getElementById('cacheDate').textContent =
      '缓存时间: ' + d.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
  }
}

function renderTable(rows) {
  const container = document.getElementById('tableContainer');

  if (!rows.length) {
    container.innerHTML = `
      <div class="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="40" height="40">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <p>没有符合条件的候选股</p>
        <span>尝试放宽筛选条件</span>
      </div>`;
    return;
  }

  const hasCM = rows.some(r => r.circ_mv != null);

  const cols = [
    { key: '#',                 label: '#',          align: 'right'  },
    { key: 'code',              label: '代码',        align: 'left'   },
    { key: 'name',              label: '名称',        align: 'left'   },
    { key: 'current_price',     label: '现价 (元)',   align: 'right'  },
    { key: 'avg_turnover_10d',  label: '10日均换手%', align: 'right'  },
    { key: 'max_turnover_10d',  label: '单日最高%',   align: 'right'  },
    { key: 'pct_change_10d',    label: '10日涨幅%',   align: 'right'  },
    { key: 'total_shares',      label: '总股本 (亿)', align: 'right'  },
    ...(hasCM ? [{ key: 'circ_mv', label: '流通市值 (亿)', align: 'right' }] : []),
    { key: 'candidate_reason',  label: '要点',        align: 'left'   },
  ];

  const thead = `<thead><tr>${cols.map(c =>
    `<th style="text-align:${c.align}">${c.label}</th>`
  ).join('')}</tr></thead>`;

  const tbody = rows.map((r, i) => {
    const pctCls = r.pct_change_10d > 0 ? 'pct-up' : r.pct_change_10d < 0 ? 'pct-dn' : '';
    const pctStr = r.pct_change_10d > 0
      ? `+${r.pct_change_10d.toFixed(2)}%`
      : `${r.pct_change_10d.toFixed(2)}%`;

    const cells = [
      `<td style="text-align:right;color:var(--text-secondary)">${i + 1}</td>`,
      `<td><span class="badge badge-market badge-market-cn">CN</span> <code style="font-size:12px">${esc(r.code)}</code></td>`,
      `<td style="font-weight:500">${esc(r.name)}</td>`,
      `<td style="text-align:right;font-variant-numeric:tabular-nums">${r.current_price.toFixed(3)}</td>`,
      `<td style="text-align:right;font-variant-numeric:tabular-nums;color:var(--brand)">${r.avg_turnover_10d.toFixed(2)}%</td>`,
      `<td style="text-align:right;font-variant-numeric:tabular-nums">${r.max_turnover_10d.toFixed(2)}%</td>`,
      `<td style="text-align:right" class="${pctCls}">${pctStr}</td>`,
      `<td style="text-align:right;font-variant-numeric:tabular-nums">${r.total_shares.toFixed(1)}</td>`,
      ...(hasCM ? [`<td style="text-align:right;font-variant-numeric:tabular-nums">${r.circ_mv != null ? r.circ_mv.toFixed(1) : '—'}</td>`] : []),
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
      window.location.href = `company.html?market=${market}&code=${code}`;
    });
  });
}

function renderError(msg) {
  const container = document.getElementById('tableContainer');
  const isNoCache = msg.includes('404') || msg.includes('not found') || msg.includes('cache');
  container.innerHTML = `
    <div class="empty-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="40" height="40">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
      <p>${isNoCache ? '候选池缓存不存在' : '加载失败'}</p>
      <span>${isNoCache
        ? '请先在本地运行: <code>python -m backend.scripts.run_candidates</code>'
        : esc(msg)
      }</span>
    </div>`;
  document.getElementById('tableInfo').textContent = '';
}

function setLoading(on) {
  document.getElementById('loadingTag').style.display = on ? '' : 'none';
}

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Controls ──────────────────────────────────────────────────────────────────
document.getElementById('applyBtn').addEventListener('click', loadCandidates);
document.getElementById('refreshBtn').addEventListener('click', loadCandidates);
document.getElementById('resetBtn').addEventListener('click', () => {
  document.getElementById('fTurnoverMin').value = '1';
  document.getElementById('fTurnoverMax').value = '10';
  document.getElementById('fPriceMax').value    = '5';
  document.getElementById('fShareMax').value    = '30';
  document.getElementById('fPctMax').value      = '15';
  document.getElementById('fExcludeSt').checked = true;
  loadCandidates();
});

// Enter key in any filter input triggers apply
document.getElementById('filterBar').addEventListener('keydown', e => {
  if (e.key === 'Enter') loadCandidates();
});

// ── Init ──────────────────────────────────────────────────────────────────────
checkHealth();
loadCandidates();
