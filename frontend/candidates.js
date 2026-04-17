'use strict';

/* ============================================================
   CANDIDATES PAGE
   持续换手候选池 — realtime /api/candidates (30-min in-memory cache)
   ============================================================ */

const state = {
  data:     null,
  filtered: [],
};

// ── Health check ─────────────────────────────────────────────────────────────
async function checkHealth() {
  const dot   = document.getElementById('healthDot');
  const label = document.getElementById('healthLabel');
  try {
    await API.health();
    dot.className     = 'health-dot health-dot--ok';
    label.textContent = 'API Connected';
  } catch {
    dot.className     = 'health-dot health-dot--err';
    label.textContent = 'API Offline';
  }
}

// ── Load candidates from API ─────────────────────────────────────────────────
async function loadCandidates({ forceRefresh = false } = {}) {
  setLoading(true);
  document.getElementById('tableContainer').innerHTML = '';
  document.getElementById('tableInfo').textContent    = '';

  try {
    const params = buildParams();
    if (forceRefresh) params.refresh = '1';
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
  const priceMax    = parseFloat(document.getElementById('fPriceMax').value);
  const circMvMax   = parseFloat(document.getElementById('fCircMvMax').value);
  const pctMax      = parseFloat(document.getElementById('fPctMax').value);
  const excludeSt   = document.getElementById('fExcludeSt').checked;

  if (!isNaN(turnoverMin)) p.turnover_min = turnoverMin;
  if (!isNaN(priceMax))    p.price_max    = priceMax;
  if (!isNaN(circMvMax))   p.circ_mv_max  = circMvMax;
  if (!isNaN(pctMax))      p.pct_max      = pctMax;
  p.exclude_st = excludeSt ? '1' : '0';
  p.limit = 300;
  return p;
}

// ── Render helpers ────────────────────────────────────────────────────────────
const _timeFmt = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', second: '2-digit',
  hour12: false,
});

function renderMeta(data) {
  document.getElementById('tableInfo').textContent =
    `${data.total} 只候选股`;

  // Server-side AKShare fetch time (stays the same while cache is live)
  const serverEl = document.getElementById('serverFetchTime');
  if (data.generated_at && serverEl) {
    serverEl.textContent = _timeFmt.format(new Date(data.generated_at));
  }

  // Client-side request time (always "now")
  const clientEl = document.getElementById('clientFetchTime');
  if (clientEl) {
    clientEl.textContent = _timeFmt.format(new Date());
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

  const cols = [
    { key: '#',                label: '#',           align: 'right' },
    { key: 'code',             label: '代码',         align: 'left'  },
    { key: 'name',             label: '名称',         align: 'left'  },
    { key: 'current_price',    label: '现价 (元)',    align: 'right' },
    { key: 'turnover',         label: '今日换手%',    align: 'right' },
    { key: 'pct_change',       label: '今日涨幅%',    align: 'right' },
    { key: 'circ_mv',          label: '流通市值 (亿)', align: 'right' },
    { key: 'candidate_reason', label: '要点',         align: 'left'  },
  ];

  const thead = `<thead><tr>${cols.map(c =>
    `<th style="text-align:${c.align}">${c.label}</th>`
  ).join('')}</tr></thead>`;

  const fmt = (v, digits = 2, suffix = '') =>
    v != null && isFinite(v) ? v.toFixed(digits) + suffix : '—';

  const tbody = rows.map((r, i) => {
    const pct    = r.pct_change;
    const pctCls = pct > 0 ? 'pct-up' : pct < 0 ? 'pct-dn' : '';
    const pctStr = pct != null && isFinite(pct)
      ? (pct > 0 ? `+${pct.toFixed(2)}%` : `${pct.toFixed(2)}%`)
      : '—';

    const cells = [
      `<td style="text-align:right;color:var(--text-secondary)">${i + 1}</td>`,
      `<td><span class="badge badge-market badge-market-cn">CN</span> <code style="font-size:12px">${esc(r.code)}</code></td>`,
      `<td style="font-weight:500">${esc(r.name)}</td>`,
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
      window.location.href = `company.html?market=${market}&code=${code}`;
    });
  });
}

function renderError(msg) {
  const container = document.getElementById('tableContainer');
  container.innerHTML = `
    <div class="empty-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="40" height="40">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
      <p>加载失败</p>
      <span>${esc(msg)}</span>
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
document.getElementById('applyBtn').addEventListener('click', () => loadCandidates());
document.getElementById('refreshBtn').addEventListener('click', () => loadCandidates({ forceRefresh: true }));
document.getElementById('resetBtn').addEventListener('click', () => {
  document.getElementById('fTurnoverMin').value  = '2';
  document.getElementById('fPriceMax').value     = '20';
  document.getElementById('fCircMvMax').value    = '80';
  document.getElementById('fPctMax').value       = '9';
  document.getElementById('fExcludeSt').checked  = true;
  loadCandidates();
});

// Enter key in any filter input triggers apply
document.getElementById('filterBar').addEventListener('keydown', e => {
  if (e.key === 'Enter') loadCandidates();
});

// ── Init ──────────────────────────────────────────────────────────────────────
checkHealth();
loadCandidates();
