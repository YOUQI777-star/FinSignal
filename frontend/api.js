'use strict';

/* ============================================================
   API CLIENT
   All backend calls go through here. Falls back to MOCK_DATA
   automatically when the backend is unreachable.
   ============================================================ */

// Production backend on Railway. Override via Settings page (localStorage 'fsm_api_base').
// If stored value is a localhost address, fall back to Railway (handles dev→prod transition).
const _RAILWAY = 'https://tender-fascination-production.up.railway.app';
const _stored  = localStorage.getItem('fsm_api_base') || '';
const API_BASE = (_stored && !_stored.includes('localhost') && !_stored.includes('127.0.0.1'))
  ? _stored
  : _RAILWAY;

// Fill all footer API base indicators once DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  const host = new URL(API_BASE).host;
  document.querySelectorAll('.footer-api-base, #footerApiBase').forEach(el => {
    el.textContent = host;
  });
});

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} — ${res.statusText}`);
  return res.json();
}

const API = {
  health() {
    return apiFetch('/api/health');
  },

  getTop({ market = '', signal_id = '', limit = 50 } = {}) {
    const p = new URLSearchParams({ limit });
    if (market)    p.set('market', market);
    if (signal_id) p.set('signal_id', signal_id);
    return apiFetch(`/api/signals/top?${p}`);
  },

  search(q) {
    if (!q || !q.trim()) return Promise.resolve({ results: [] });
    return apiFetch(`/api/search?q=${encodeURIComponent(q.trim())}`);
  },

  getSignals(market, code, fresh = false) {
    return apiFetch(`/api/signals/${market}/${code}${fresh ? '?fresh=true' : ''}`);
  },

  getCompany(market, code) {
    return apiFetch(`/api/company/${market}/${code}`);
  },

  compare(ids) {
    // ids: ['CN:600519', 'TW:2330']
    return apiFetch(`/api/compare?codes=${ids.join(',')}`);
  },

  generateReport(market, code) {
    return apiFetch(`/api/report/${market}/${code}`, { method: 'POST' });
  },

  getGraph(market, code) {
    return apiFetch(`/api/graph/${market}/${code}`);
  },
};

/* ============================================================
   MOCK FALLBACK DATA
   Shown when the API is not reachable (e.g. backend not started).
   ============================================================ */
const MOCK_DATA = {
  top: {
    total: 8,
    results: [
      {
        company_id: 'CN:000002', market: 'CN', code: '000002', name: '万科A',
        summary: { total_rules: 6, triggered_count: 3, status_counts: { triggered: 3, ok: 2, not_available: 1 }, snapshot_tier: 'real_financial_available' },
        financial_signals: [
          { signal_id: 'F1', triggered: true },
          { signal_id: 'F3', triggered: true },
          { signal_id: 'F4', triggered: true },
          { signal_id: 'F2', triggered: false },
        ],
        governance_signals: [],
      },
      {
        company_id: 'CN:000016', market: 'CN', code: '000016', name: '深康佳A',
        summary: { total_rules: 6, triggered_count: 3, status_counts: { triggered: 3, ok: 2, not_available: 1 }, snapshot_tier: 'real_financial_available' },
        financial_signals: [
          { signal_id: 'F1', triggered: true },
          { signal_id: 'F3', triggered: true },
          { signal_id: 'F4', triggered: true },
        ],
        governance_signals: [],
      },
      {
        company_id: 'TW:2412', market: 'TW', code: '2412', name: '中華電信',
        summary: { total_rules: 6, triggered_count: 2, status_counts: { triggered: 2, ok: 3, not_available: 1 }, snapshot_tier: 'real_financial_available' },
        financial_signals: [
          { signal_id: 'F3', triggered: true },
          { signal_id: 'F4', triggered: true },
          { signal_id: 'F1', triggered: false },
        ],
        governance_signals: [],
      },
      {
        company_id: 'CN:000042', market: 'CN', code: '000042', name: '中洲控股',
        summary: { total_rules: 6, triggered_count: 2, status_counts: { triggered: 2, ok: 3, not_available: 1 }, snapshot_tier: 'real_financial_available' },
        financial_signals: [
          { signal_id: 'F1', triggered: true },
          { signal_id: 'F4', triggered: true },
        ],
        governance_signals: [],
      },
      {
        company_id: 'TW:2330', market: 'TW', code: '2330', name: '台積電',
        summary: { total_rules: 6, triggered_count: 1, status_counts: { triggered: 1, ok: 4, not_available: 1 }, snapshot_tier: 'real_financial_available' },
        financial_signals: [
          { signal_id: 'F1', triggered: true },
          { signal_id: 'F2', triggered: false },
          { signal_id: 'F3', triggered: false },
        ],
        governance_signals: [],
      },
      {
        company_id: 'CN:600036', market: 'CN', code: '600036', name: '招商银行',
        summary: { total_rules: 6, triggered_count: 1, status_counts: { triggered: 1, ok: 4, not_available: 1 }, snapshot_tier: 'real_financial_available' },
        financial_signals: [
          { signal_id: 'F3', triggered: true },
          { signal_id: 'F1', triggered: false },
        ],
        governance_signals: [],
      },
      {
        company_id: 'TW:2454', market: 'TW', code: '2454', name: '聯發科',
        summary: { total_rules: 6, triggered_count: 1, status_counts: { triggered: 1, ok: 4, not_available: 1 }, snapshot_tier: 'real_financial_available' },
        financial_signals: [
          { signal_id: 'F2', triggered: true },
          { signal_id: 'F1', triggered: false },
        ],
        governance_signals: [],
      },
      {
        company_id: 'CN:600519', market: 'CN', code: '600519', name: '贵州茅台',
        summary: { total_rules: 6, triggered_count: 0, status_counts: { triggered: 0, ok: 5, not_available: 1 }, snapshot_tier: 'real_financial_available' },
        financial_signals: [
          { signal_id: 'F1', triggered: false },
          { signal_id: 'F2', triggered: false },
          { signal_id: 'F3', triggered: false },
          { signal_id: 'F4', triggered: false },
        ],
        governance_signals: [],
      },
    ],
  },
};
