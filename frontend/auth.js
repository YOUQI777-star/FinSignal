'use strict';

/* ============================================================
   AUTH — FinSignal user authentication
   Token stored in localStorage('fsm_auth_token')
   User info stored in localStorage('fsm_auth_user') as JSON
   ============================================================ */

const AUTH = (() => {
  const TOKEN_KEY = 'fsm_auth_token';
  const USER_KEY  = 'fsm_auth_user';

  function getToken() { return localStorage.getItem(TOKEN_KEY) || ''; }
  function getUser()  {
    try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null'); } catch { return null; }
  }
  function isLoggedIn() { return !!getToken(); }

  function saveSession(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  async function apiCall(path, opts = {}) {
    const base = localStorage.getItem('fsm_api_base') || 'https://tender-fascination-production.up.railway.app';
    const token = getToken();
    const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(base + path, { ...opts, headers });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  async function register(email, password) {
    const data = await apiCall('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    saveSession(data.token, data.user);
    return data.user;
  }

  async function login(email, password) {
    const data = await apiCall('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    saveSession(data.token, data.user);
    return data.user;
  }

  async function logout() {
    try { await apiCall('/api/auth/logout', { method: 'POST' }); } catch {}
    clearSession();
  }

  async function getFavorites() {
    return apiCall('/api/me/favorites');
  }

  async function addFavorite(market, code, name) {
    return apiCall('/api/me/favorites', {
      method: 'POST',
      body: JSON.stringify({ market, code, name }),
    });
  }

  async function removeFavorite(market, code) {
    return apiCall(`/api/me/favorites/${market}/${code}`, { method: 'DELETE' });
  }

  return { getToken, getUser, isLoggedIn, saveSession, clearSession, register, login, logout, getFavorites, addFavorite, removeFavorite };
})();

/* ============================================================
   AUTH UI — injected into every page
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
  injectAuthButton();
  injectAuthModal();
  injectProfilePanel();
});

function injectAuthButton() {
  const btn = document.createElement('div');
  btn.id = 'authEntryBtn';
  btn.style.cssText = 'position:fixed;top:13px;right:20px;z-index:200;display:flex;align-items:center;gap:8px;cursor:pointer';
  document.body.appendChild(btn);
  renderAuthEntry();
}

function renderAuthEntry() {
  const btn = document.getElementById('authEntryBtn');
  if (!btn) return;

  const zh = window._currentLang === 'zh';

  if (AUTH.isLoggedIn()) {
    const user = AUTH.getUser();
    const initial = (user?.email?.[0] || '?').toUpperCase();
    btn.innerHTML = `
      <button class="auth-avatar-btn" id="openProfileBtn" title="${user?.email || ''}">
        <span class="auth-avatar-initial">${initial}</span>
      </button>`;
    document.getElementById('openProfileBtn').addEventListener('click', openProfilePanel);
  } else {
    btn.innerHTML = `
      <button class="btn btn--outline auth-login-btn" id="openAuthModalBtn" style="height:34px;font-size:13px">
        ${zh ? '登录 / 注册' : 'Login / Register'}
      </button>`;
    document.getElementById('openAuthModalBtn').addEventListener('click', openAuthModal);
  }
}

/* ── Auth Modal (Login / Register) ─────────────────────────────────────────── */

function injectAuthModal() {
  if (document.getElementById('authModal')) return;
  const el = document.createElement('div');
  el.id = 'authModal';
  el.className = 'auth-modal-overlay';
  el.style.display = 'none';
  el.innerHTML = `
    <div class="auth-modal">
      <button class="auth-modal-close" id="closeAuthModal">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" width="18" height="18"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
      <div class="auth-modal-tabs">
        <button class="auth-tab auth-tab--active" data-tab="login" id="tabLogin">登录</button>
        <button class="auth-tab" data-tab="register" id="tabRegister">注册</button>
      </div>
      <form id="authForm" class="auth-form" autocomplete="on">
        <label class="auth-label">
          <span>邮箱</span>
          <input id="authEmail" type="email" class="auth-input" placeholder="you@example.com" autocomplete="email" required />
        </label>
        <label class="auth-label">
          <span>密码</span>
          <input id="authPassword" type="password" class="auth-input" placeholder="至少 6 位" autocomplete="current-password" required />
        </label>
        <div id="authError" class="auth-error" style="display:none"></div>
        <button type="submit" id="authSubmitBtn" class="btn btn--primary" style="width:100%;height:40px;margin-top:4px">登录</button>
      </form>
    </div>`;
  document.body.appendChild(el);

  let currentTab = 'login';

  el.addEventListener('click', e => { if (e.target === el) closeAuthModal(); });
  document.getElementById('closeAuthModal').addEventListener('click', closeAuthModal);

  ['tabLogin', 'tabRegister'].forEach(id => {
    document.getElementById(id).addEventListener('click', () => {
      currentTab = id === 'tabLogin' ? 'login' : 'register';
      document.getElementById('tabLogin').classList.toggle('auth-tab--active', currentTab === 'login');
      document.getElementById('tabRegister').classList.toggle('auth-tab--active', currentTab === 'register');
      document.getElementById('authSubmitBtn').textContent = currentTab === 'login' ? '登录' : '注册';
      document.getElementById('authPassword').placeholder = currentTab === 'login' ? '密码' : '至少 6 位';
      document.getElementById('authError').style.display = 'none';
    });
  });

  document.getElementById('authForm').addEventListener('submit', async e => {
    e.preventDefault();
    const email    = document.getElementById('authEmail').value.trim();
    const password = document.getElementById('authPassword').value;
    const errEl    = document.getElementById('authError');
    const submitBtn = document.getElementById('authSubmitBtn');

    errEl.style.display = 'none';
    submitBtn.disabled = true;
    submitBtn.textContent = currentTab === 'login' ? '登录中…' : '注册中…';

    try {
      if (currentTab === 'login') {
        await AUTH.login(email, password);
      } else {
        await AUTH.register(email, password);
      }
      closeAuthModal();
      renderAuthEntry();
    } catch (err) {
      errEl.textContent = err.message;
      errEl.style.display = 'block';
      submitBtn.disabled = false;
      submitBtn.textContent = currentTab === 'login' ? '登录' : '注册';
    }
  });
}

function openAuthModal() {
  document.getElementById('authModal').style.display = 'flex';
  setTimeout(() => document.getElementById('authEmail')?.focus(), 50);
}

function closeAuthModal() {
  document.getElementById('authModal').style.display = 'none';
}

/* ── Profile Panel (slide from right) ──────────────────────────────────────── */

function injectProfilePanel() {
  if (document.getElementById('profilePanel')) return;
  const el = document.createElement('div');
  el.id = 'profilePanel';
  el.className = 'profile-panel';
  el.innerHTML = `
    <div class="profile-panel-header">
      <div class="profile-panel-user">
        <div class="profile-avatar-lg" id="profileAvatarLg">?</div>
        <div>
          <div class="profile-email" id="profileEmail">—</div>
          <div class="profile-since" id="profileSince"></div>
        </div>
      </div>
      <button class="auth-modal-close" id="closeProfilePanel">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" width="18" height="18"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </div>
    <div class="profile-panel-section-title">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
      <span id="favoritesTitle">收藏的股票</span>
    </div>
    <div id="favoritesList" class="favorites-list">
      <div class="favorites-loading">加载中…</div>
    </div>
    <div class="profile-panel-footer">
      <button id="logoutBtn" class="btn btn--outline" style="width:100%;height:36px">退出登录</button>
    </div>`;
  document.body.appendChild(el);

  // Overlay backdrop
  const backdrop = document.createElement('div');
  backdrop.id = 'profileBackdrop';
  backdrop.className = 'profile-backdrop';
  backdrop.style.display = 'none';
  backdrop.addEventListener('click', closeProfilePanel);
  document.body.appendChild(backdrop);

  document.getElementById('closeProfilePanel').addEventListener('click', closeProfilePanel);
  document.getElementById('logoutBtn').addEventListener('click', async () => {
    await AUTH.logout();
    closeProfilePanel();
    renderAuthEntry();
  });
}

async function openProfilePanel() {
  const panel = document.getElementById('profilePanel');
  const backdrop = document.getElementById('profileBackdrop');
  const user = AUTH.getUser();

  // Fill user info
  document.getElementById('profileAvatarLg').textContent = (user?.email?.[0] || '?').toUpperCase();
  document.getElementById('profileEmail').textContent = user?.email || '—';
  document.getElementById('profileSince').textContent = '';

  backdrop.style.display = 'block';
  panel.classList.add('profile-panel--open');

  // Load favorites
  await loadFavorites();
}

function closeProfilePanel() {
  document.getElementById('profilePanel')?.classList.remove('profile-panel--open');
  document.getElementById('profileBackdrop').style.display = 'none';
}

async function loadFavorites() {
  const list = document.getElementById('favoritesList');
  const zh = window._currentLang === 'zh';
  list.innerHTML = `<div class="favorites-loading">${zh ? '加载中…' : 'Loading…'}</div>`;
  try {
    const data = await AUTH.getFavorites();
    renderFavorites(data.results || []);
  } catch {
    list.innerHTML = `<div class="favorites-empty">${zh ? '加载失败' : 'Load failed'}</div>`;
  }
}

function renderFavorites(items) {
  const list = document.getElementById('favoritesList');
  const zh = window._currentLang === 'zh';

  if (!items.length) {
    list.innerHTML = `
      <div class="favorites-empty">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="32" height="32"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
        <p>${zh ? '还没有收藏' : 'No favorites yet'}</p>
        <span>${zh ? '在公司详情页点击收藏按钮' : 'Click the favorite button on any company page'}</span>
      </div>`;
    return;
  }

  list.innerHTML = items.map(item => `
    <a class="favorite-item" href="company.html?market=${encodeURIComponent(item.market)}&code=${encodeURIComponent(item.code)}">
      <div class="favorite-item-left">
        <span class="badge badge-market badge-market-${String(item.market).toLowerCase()}">${item.market}</span>
        <div style="min-width:0;display:flex;flex-direction:column;gap:1px">
          <span class="favorite-name">${escAuth(item.name || item.code)}</span>
          <span class="favorite-code">${escAuth(item.code)}</span>
        </div>
      </div>
      <button class="favorite-remove-btn" data-market="${item.market}" data-code="${item.code}" title="${zh ? '取消收藏' : 'Remove'}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" width="14" height="14"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </a>`).join('');

  list.querySelectorAll('.favorite-remove-btn').forEach(btn => {
    btn.addEventListener('click', async e => {
      e.preventDefault();
      e.stopPropagation();
      const { market, code } = btn.dataset;
      btn.disabled = true;
      try {
        await AUTH.removeFavorite(market, code);
        btn.closest('.favorite-item').remove();
        // If no more items, show empty state
        if (!list.querySelectorAll('.favorite-item').length) {
          renderFavorites([]);
        }
      } catch {
        btn.disabled = false;
      }
    });
  });
}

function escAuth(str) {
  return String(str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* ── Public helper: toggle favorite on company page ────────────────────────── */
// Called from company.js: AUTH_UI.toggleFavorite(market, code, name)
window.AUTH_UI = {
  isLoggedIn: AUTH.isLoggedIn,
  openAuthModal,
  async toggleFavorite(market, code, name) {
    if (!AUTH.isLoggedIn()) {
      openAuthModal();
      return false;
    }
    try {
      await AUTH.addFavorite(market, code, name);
      return true;
    } catch {
      return false;
    }
  },
  async removeFavorite(market, code) {
    try {
      await AUTH.removeFavorite(market, code);
      return true;
    } catch {
      return false;
    }
  }
};
