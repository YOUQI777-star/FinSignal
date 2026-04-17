'use strict';
const t = (zh, en) => window._currentLang === 'zh' ? zh : en;

const STORAGE_KEYS = {
  apiBase:      'fsm_api_base',
  defaultLimit: 'fsm_default_limit',
  defaultMarket:'fsm_default_market',
  recent:       'fsm_recent',
};

/* ============================================================
   ENTRY POINT
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {
  loadSettings();
  checkHealth();
  bindEvents();
  updateRecentCount();
});

/* ============================================================
   LOAD SAVED SETTINGS INTO FORM
   ============================================================ */
function loadSettings() {
  const apiBase = localStorage.getItem(STORAGE_KEYS.apiBase) || 'http://localhost:5000';
  document.getElementById('apiBaseInput').value = apiBase;

  const limit = localStorage.getItem(STORAGE_KEYS.defaultLimit) || '50';
  document.getElementById('defaultLimit').value = limit;

  const market = localStorage.getItem(STORAGE_KEYS.defaultMarket) || '';
  document.getElementById('defaultMarket').value = market;
}

/* ============================================================
   HEALTH CHECK
   ============================================================ */
async function checkHealth() {
  const dot = document.getElementById('settingsHealthDot');
  const lbl = document.getElementById('settingsHealthLabel');
  // Also update sidebar dot
  const sideDot = document.getElementById('healthDot');
  const sideLbl = document.getElementById('healthLabel');

  dot.className = 'health-dot';
  lbl.textContent = t('检测中…', 'Checking…');

  try {
    await API.health();
    dot.className     = 'health-dot online';
    lbl.textContent   = t('已连接 — API 正常', 'Connected — API is reachable');
    sideDot.className = 'health-dot online';
    sideLbl.textContent = t('API 已连接', 'API Connected');
  } catch (err) {
    dot.className     = 'health-dot offline';
    lbl.textContent   = t(`离线 — ${err.message}`, `Offline — ${err.message}`);
    sideDot.className = 'health-dot offline';
    sideLbl.textContent = t('API 离线', 'API Offline');
  }
}

/* ============================================================
   SAVE
   ============================================================ */
function saveApiBase() {
  const val = document.getElementById('apiBaseInput').value.trim();
  if (!val) {
    showToast(t('API 基础地址不能为空', 'API Base URL cannot be empty'), 'error');
    return;
  }
  // Strip trailing slash
  const clean = val.replace(/\/+$/, '');
  localStorage.setItem(STORAGE_KEYS.apiBase, clean);
  document.getElementById('apiBaseInput').value = clean;
  showToast(t('API 地址已保存 — 刷新页面生效', 'API base URL saved — reload pages to apply'), 'success');
  checkHealth();
}

function saveDisplay() {
  const limit  = document.getElementById('defaultLimit').value;
  const market = document.getElementById('defaultMarket').value;
  localStorage.setItem(STORAGE_KEYS.defaultLimit,  limit);
  localStorage.setItem(STORAGE_KEYS.defaultMarket, market);
  showToast(t('显示设置已保存', 'Display settings saved'), 'success');
}

function clearRecent() {
  localStorage.removeItem(STORAGE_KEYS.recent);
  updateRecentCount();
  showToast(t('浏览记录已清除', 'Recently viewed history cleared'), 'success');
}

function updateRecentCount() {
  try {
    const recent = JSON.parse(localStorage.getItem(STORAGE_KEYS.recent) || '[]');
    const el = document.getElementById('recentCount');
    el.textContent = recent.length
      ? t(`已存储 ${recent.length} 条浏览记录`, `${recent.length} entr${recent.length > 1 ? 'ies' : 'y'} stored in localStorage`)
      : t('暂无浏览记录', 'No history stored');
  } catch {
    document.getElementById('recentCount').textContent = t('已存储在 localStorage', 'Stored in localStorage');
  }
}

/* ============================================================
   EVENTS
   ============================================================ */
function bindEvents() {
  document.getElementById('saveApiBase').addEventListener('click', saveApiBase);
  document.getElementById('apiBaseInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') saveApiBase();
  });

  document.getElementById('recheckBtn').addEventListener('click', checkHealth);
  document.getElementById('saveDisplay').addEventListener('click', saveDisplay);
  document.getElementById('clearRecentBtn').addEventListener('click', clearRecent);
}

/* ============================================================
   TOAST
   ============================================================ */
function showToast(msg, type = 'info') {
  const c = document.getElementById('toastContainer');
  const el = document.createElement('div');
  el.className = `toast toast--${type}`;
  el.textContent = msg;
  c.appendChild(el);
  requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add('show')));
  setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 260); }, 4000);
}
