'use strict';

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
  lbl.textContent = 'Checking…';

  try {
    await API.health();
    dot.className     = 'health-dot online';
    lbl.textContent   = 'Connected — API is reachable';
    sideDot.className = 'health-dot online';
    sideLbl.textContent = 'API Connected';
  } catch (err) {
    dot.className     = 'health-dot offline';
    lbl.textContent   = `Offline — ${err.message}`;
    sideDot.className = 'health-dot offline';
    sideLbl.textContent = 'API Offline';
  }
}

/* ============================================================
   SAVE
   ============================================================ */
function saveApiBase() {
  const val = document.getElementById('apiBaseInput').value.trim();
  if (!val) {
    showToast('API Base URL cannot be empty', 'error');
    return;
  }
  // Strip trailing slash
  const clean = val.replace(/\/+$/, '');
  localStorage.setItem(STORAGE_KEYS.apiBase, clean);
  document.getElementById('apiBaseInput').value = clean;
  showToast('API base URL saved — reload pages to apply', 'success');
  checkHealth();
}

function saveDisplay() {
  const limit  = document.getElementById('defaultLimit').value;
  const market = document.getElementById('defaultMarket').value;
  localStorage.setItem(STORAGE_KEYS.defaultLimit,  limit);
  localStorage.setItem(STORAGE_KEYS.defaultMarket, market);
  showToast('Display settings saved', 'success');
}

function clearRecent() {
  localStorage.removeItem(STORAGE_KEYS.recent);
  updateRecentCount();
  showToast('Recently viewed history cleared', 'success');
}

function updateRecentCount() {
  try {
    const recent = JSON.parse(localStorage.getItem(STORAGE_KEYS.recent) || '[]');
    const el = document.getElementById('recentCount');
    el.textContent = recent.length
      ? `${recent.length} entr${recent.length > 1 ? 'ies' : 'y'} stored in localStorage`
      : 'No history stored';
  } catch {
    document.getElementById('recentCount').textContent = 'Stored in localStorage';
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
  const t = document.createElement('div');
  t.className = `toast toast--${type}`;
  t.textContent = msg;
  c.appendChild(t);
  requestAnimationFrame(() => requestAnimationFrame(() => t.classList.add('show')));
  setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 260); }, 4000);
}
