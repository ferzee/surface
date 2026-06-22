// ─── Auth ─────────────────────────────────────────────────────────────────────

const Auth = {
  getToken: () => localStorage.getItem('surface_token'),
  getUser:  () => { try { return JSON.parse(localStorage.getItem('surface_user')); } catch { return null; } },
  set(user, token) {
    localStorage.setItem('surface_token', token);
    localStorage.setItem('surface_user', JSON.stringify(user));
  },
  clear() {
    localStorage.removeItem('surface_token');
    localStorage.removeItem('surface_user');
  },
  logout() { this.clear(); location.href = '/login.html'; },
  require() {
    const user = this.getUser();
    if (!user || !this.getToken()) { location.href = '/login.html'; return null; }
    return user;
  },
};

// ─── API client ───────────────────────────────────────────────────────────────

const api = {
  async request(method, path, body) {
    const headers = { 'Content-Type': 'application/json' };
    const token = Auth.getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`/api${path}`, {
      method,
      headers,
      body: body != null ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (res.status === 401) { Auth.logout(); throw data; }
    if (!res.ok) throw data;
    return data;
  },
  get(path)        { return this.request('GET',    path); },
  post(path, body) { return this.request('POST',   path, body); },
  put(path, body)  { return this.request('PUT',    path, body); },
  del(path)        { return this.request('DELETE', path); },
  async upload(path, formData) {
    const headers = {};
    const token = Auth.getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`/api${path}`, { method: 'POST', headers, body: formData });
    const data = await res.json().catch(() => ({}));
    if (res.status === 401) { Auth.logout(); throw data; }
    if (!res.ok) throw data;
    return data;
  },
};

// ─── Avatar gradient map ──────────────────────────────────────────────────────

const HEADER_GRADIENTS = {
  ocean:    'linear-gradient(135deg,#86C0D6,#2E6E8E)',
  teal:     'linear-gradient(135deg,#7FB5C9,#2E7D97)',
  midnight: 'linear-gradient(135deg,#5B8FAA,#1B4D63)',
  slate:    'linear-gradient(135deg,#8FAABF,#4A6E89)',
  seafoam:  'linear-gradient(135deg,#9DC7C3,#3FA39B)',
  dusk:     'linear-gradient(135deg,#B8D0DA,#6E9BAD)',
};

function headerGradient(key) {
  return HEADER_GRADIENTS[key] || HEADER_GRADIENTS.ocean;
}

function avatarGradient(color) {
  const map = {
    '#0891b2': 'linear-gradient(135deg,#86C0D6,#2E6E8E)',
    '#0e7490': 'linear-gradient(135deg,#7FB5C9,#2E7D97)',
    '#1d4ed8': 'linear-gradient(135deg,#A9B6D6,#6E8CA8)',
    '#7c3aed': 'linear-gradient(135deg,#C4B0D6,#8B6EAA)',
    '#059669': 'linear-gradient(135deg,#9DC7C3,#4FA3A0)',
    '#b45309': 'linear-gradient(135deg,#E6CBA8,#C9A56F)',
    '#be185d': 'linear-gradient(135deg,#D6A9BE,#A86E8C)',
  };
  return map[color] || `linear-gradient(135deg,#86C0D6,#2E6E8E)`;
}

// ─── Format helpers ───────────────────────────────────────────────────────────

const fmt = {
  staticTime(totalSecs) {
    const s = Math.round(totalSecs);
    return `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`;
  },
  diveValue(discipline, value) {
    return discipline === 'static' ? fmt.staticTime(value) : `${value}m`;
  },
  disciplineLabel(d) {
    return { static: 'Static', dynamic: 'Dynamic', depth: 'Depth' }[d] || d;
  },
  badge(d) {
    return `<span class="badge badge-${d}">${fmt.disciplineLabel(d)}</span>`;
  },
  timeAgo(dateStr) {
    const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
    if (diff < 60)    return 'just now';
    if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
    return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  },
  date(dateStr) {
    return new Date(dateStr).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
  },
  avatar(username, color, size = 36, avatarUrl = null) {
    if (avatarUrl) {
      const br = Math.round(size * 0.29);
      return `<img src="${avatarUrl}" style="width:${size}px;height:${size}px;border-radius:${br}px;object-fit:cover;" alt="">`;
    }
    const fontSize = Math.round(size * 0.38);
    const br = Math.round(size * 0.29);
    const grad = avatarGradient(color);
    const initials = (username || '?').slice(0, 2).toUpperCase();
    return `<div class="avatar" style="width:${size}px;height:${size}px;background:${grad};font-size:${fontSize}px;border-radius:${br}px;">${initials}</div>`;
  },
};

// ─── Navbar ───────────────────────────────────────────────────────────────────

function renderNav(activePage) {
  const user = Auth.getUser();
  if (!user) return;
  const navEl = document.getElementById('nav');
  if (!navEl) return;

  const grad = avatarGradient(user.avatar_color);
  const initials = (user.username || '?').slice(0, 2).toUpperCase();
  const navAvatarHtml = user.avatar
    ? `<img src="${user.avatar}" style="width:30px;height:30px;border-radius:9px;object-fit:cover;" alt="">`
    : `<div class="avatar" style="width:30px;height:30px;background:${grad};font-size:11px;">${initials}</div>`;

  const brandSvg = `<svg width="19" height="19" viewBox="0 0 24 24" fill="none">
    <path d="M3 13c2.2 0 2.2-2 4.5-2s2.3 2 4.5 2 2.2-2 4.5-2 2.3 2 4.5 2" stroke="#fff" stroke-width="2" stroke-linecap="round"/>
    <path d="M3 18c2.2 0 2.2-2 4.5-2s2.3 2 4.5 2 2.2-2 4.5-2 2.3 2 4.5 2" stroke="#fff" stroke-width="2" stroke-linecap="round" opacity="0.55"/>
  </svg>`;

  navEl.innerHTML = `
    <nav>
      <div class="nav-inner">
        <a href="/feed.html" class="nav-brand">
          <div class="nav-brand-icon">${brandSvg}</div>
          Surface
        </a>

        <!-- Desktop: links + search + user menu -->
        <div class="nav-desktop">
          <div class="flex gap-2" style="margin-left:8px;">
            <a href="/feed.html"    class="nav-link ${activePage === 'feed'    ? 'active' : ''}">Feed</a>
            <a href="/buddies.html" class="nav-link ${activePage === 'buddies' ? 'active' : ''}">Find Buddies</a>
            <a href="/events.html"  class="nav-link ${activePage === 'events'  ? 'active' : ''}">Events</a>
            <a href="/inbox.html"   class="nav-link ${activePage === 'inbox'   ? 'active' : ''}" id="navInboxLink" style="position:relative;">Inbox<span id="navInboxBadge" style="display:none;position:absolute;top:2px;right:2px;width:8px;height:8px;border-radius:50%;background:linear-gradient(135deg,#2E7D97,#1C5A72);"></span></a>
          </div>
          <div style="flex:1;max-width:220px;position:relative;margin-left:auto;">
            <input id="ns" type="text" class="input" style="padding:7px 12px;font-size:13px;border-radius:999px;" placeholder="Search divers…">
            <div id="nsr" class="card hidden" style="position:absolute;top:calc(100% + 6px);left:0;right:0;z-index:60;overflow:hidden;border-radius:16px;padding:6px 0;"></div>
          </div>
          <div style="position:relative;margin-left:8px;">
            <button id="umBtn" style="display:flex;align-items:center;gap:8px;background:none;border:none;cursor:pointer;padding:6px 10px;border-radius:999px;transition:background .15s;" onmouseover="this.style.background='rgba(46,125,151,0.07)'" onmouseout="this.style.background=''">
              ${navAvatarHtml}
              <span style="font-size:13.5px;font-weight:500;color:#34505B;">${user.username}</span>
              <svg width="13" height="13" fill="none" stroke="#93A8B1" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7"/></svg>
            </button>
            <div id="um" class="card hidden" style="position:absolute;right:0;top:calc(100% + 6px);width:168px;overflow:hidden;z-index:60;padding:6px 0;border-radius:18px;">
              <a href="/profile.html?id=${user.id}" style="display:block;padding:10px 16px;font-size:14px;color:#34505B;text-decoration:none;transition:background .15s;" onmouseover="this.style.background='#F4F9FB'" onmouseout="this.style.background=''">My Profile</a>
              <button id="logoutBtn" style="width:100%;text-align:left;padding:10px 16px;font-size:14px;color:#c0392b;background:none;border:none;cursor:pointer;font-family:inherit;transition:background .15s;" onmouseover="this.style.background='#FDF3F3'" onmouseout="this.style.background=''">Sign Out</button>
            </div>
          </div>
        </div>

        <!-- Mobile: hamburger button -->
        <button id="navHamburger" class="nav-hamburger" aria-label="Toggle menu">
          <svg id="hamburgerIcon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
          </svg>
        </button>
      </div>

      <!-- Mobile drawer -->
      <div id="navDrawer" class="nav-mobile-drawer">
        <div style="position:relative;margin-bottom:12px;">
          <input id="nsm" type="text" class="input" style="padding:7px 12px;font-size:13px;border-radius:999px;" placeholder="Search divers…">
          <div id="nsmr" class="card hidden" style="position:absolute;top:calc(100% + 6px);left:0;right:0;z-index:60;overflow:hidden;border-radius:16px;padding:6px 0;"></div>
        </div>
        <a href="/feed.html"    class="nav-link nav-link-block ${activePage === 'feed'    ? 'active' : ''}">Feed</a>
        <a href="/buddies.html" class="nav-link nav-link-block ${activePage === 'buddies' ? 'active' : ''}">Find Buddies</a>
        <a href="/events.html"  class="nav-link nav-link-block ${activePage === 'events'  ? 'active' : ''}">Events</a>
        <a href="/inbox.html"   class="nav-link nav-link-block ${activePage === 'inbox'   ? 'active' : ''}" id="navInboxLinkM" style="position:relative;">Inbox<span id="navInboxBadgeM" style="display:none;position:absolute;top:8px;right:14px;width:8px;height:8px;border-radius:50%;background:linear-gradient(135deg,#2E7D97,#1C5A72);"></span></a>
        <div style="border-top:1px solid #EEF4F6;margin:10px 0;"></div>
        <a href="/profile.html?id=${user.id}" style="display:flex;align-items:center;gap:10px;padding:8px 14px;border-radius:14px;text-decoration:none;color:#34505B;font-size:14px;font-weight:500;transition:background .15s;" onmouseover="this.style.background='#F4F9FB'" onmouseout="this.style.background=''">
          ${navAvatarHtml}
          <span>${user.username}</span>
        </a>
        <button id="logoutBtnM" style="width:100%;text-align:left;padding:8px 14px;font-size:14px;color:#c0392b;background:none;border:none;cursor:pointer;font-family:inherit;border-radius:14px;transition:background .15s;" onmouseover="this.style.background='#FDF3F3'" onmouseout="this.style.background=''">Sign Out</button>
      </div>
    </nav>
  `;

  // Desktop user menu
  document.getElementById('umBtn').addEventListener('click', (e) => {
    e.stopPropagation();
    document.getElementById('um').classList.toggle('hidden');
  });
  document.addEventListener('click', () => document.getElementById('um')?.classList.add('hidden'));
  document.getElementById('logoutBtn').addEventListener('click', () => Auth.logout());

  // Mobile hamburger
  const hamburger = document.getElementById('navHamburger');
  const drawer    = document.getElementById('navDrawer');
  const icon      = document.getElementById('hamburgerIcon');
  hamburger.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = drawer.classList.toggle('open');
    icon.innerHTML = open
      ? `<line x1="4" y1="4" x2="20" y2="20"/><line x1="20" y1="4" x2="4" y2="20"/>`
      : `<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>`;
  });
  document.getElementById('logoutBtnM').addEventListener('click', () => Auth.logout());

  // Shared search — works for both desktop (#ns) and mobile (#nsm) inputs
  function attachSearch(inputId, dropdownId) {
    let timer;
    document.getElementById(inputId)?.addEventListener('input', (e) => {
      clearTimeout(timer);
      const q = e.target.value.trim();
      const dd = document.getElementById(dropdownId);
      if (!q) { dd.classList.add('hidden'); return; }
      timer = setTimeout(async () => {
        try {
          const results = await api.get(`/users/search?q=${encodeURIComponent(q)}`);
          if (!results.length) { dd.classList.add('hidden'); return; }
          dd.innerHTML = results.map(u => `
            <a href="/profile.html?id=${u.id}" style="display:flex;align-items:center;gap:10px;padding:10px 14px;text-decoration:none;color:#34505B;transition:background .15s;" onmouseover="this.style.background='#F4F9FB'" onmouseout="this.style.background=''">
              ${fmt.avatar(u.username, u.avatar_color, 28, u.avatar || null)}
              <span style="font-size:13.5px;font-weight:500;">${u.username}</span>
            </a>
          `).join('');
          dd.classList.remove('hidden');
        } catch { dd.classList.add('hidden'); }
      }, 300);
    });
    document.addEventListener('click', (e) => {
      if (!e.target.closest(`#${inputId}`)) document.getElementById(dropdownId)?.classList.add('hidden');
    });
  }

  attachSearch('ns', 'nsr');
  attachSearch('nsm', 'nsmr');

  // Async unread badge — don't block render
  if (activePage !== 'inbox') {
    api.get('/inbox/unread').then(data => {
      if (data.count > 0) {
        const b1 = document.getElementById('navInboxBadge');
        const b2 = document.getElementById('navInboxBadgeM');
        if (b1) b1.style.display = '';
        if (b2) b2.style.display = '';
      }
    }).catch(() => {});
  }
}

// ─── Dive Logger Modal ────────────────────────────────────────────────────────

function openDiveLogger(onLogged) {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal">
      <div class="modal-header">
        <span class="modal-title">Log a dive</span>
        <button class="modal-close" id="dlClose">✕</button>
      </div>
      <div class="form-group">
        <label class="label">Discipline</label>
        <div class="flex gap-2">
          <button class="disc-btn" data-d="static">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.9"/><path d="M12 8v4l2.5 1.5" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/></svg>
            Static
          </button>
          <button class="disc-btn selected" data-d="dynamic">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M3 12h18m0 0-5-5m5 5-5 5" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>
            Dynamic
          </button>
          <button class="disc-btn" data-d="depth">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M12 3v15m0 0-4-4m4 4 4-4" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>
            Depth
          </button>
        </div>
      </div>
      <div id="dlFields"></div>
      <div class="form-group">
        <label class="label">Date</label>
        <input class="input" type="date" id="dlDate" value="${new Date().toISOString().split('T')[0]}">
      </div>
      <div class="form-group">
        <label class="label">Location <span class="text-muted" style="font-weight:400;">(optional)</span></label>
        <input class="input" type="text" id="dlLoc" placeholder="e.g. Blue Hole, Dahab">
      </div>
      <div class="form-group">
        <label class="label">Notes <span class="text-muted" style="font-weight:400;">(optional)</span></label>
        <textarea class="input" id="dlNotes" rows="2" placeholder="How did it feel? Conditions, equalisation, mood…"></textarea>
      </div>
      <div id="dlErr"></div>
      <div class="flex gap-2 mt-3">
        <button class="btn btn-secondary flex-1" id="dlCancel">Cancel</button>
        <button class="btn btn-primary flex-1" id="dlSubmit">Save dive</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);

  let discipline = 'dynamic';

  function renderFields() {
    const el = overlay.querySelector('#dlFields');
    if (discipline === 'static') {
      el.innerHTML = `
        <div class="form-group">
          <label class="label">Breath-hold time</label>
          <div class="flex gap-2 items-center">
            <div class="flex-1">
              <input class="input" type="number" id="dlMins" min="0" placeholder="0" style="text-align:center">
              <div class="text-xs text-muted mt-1" style="text-align:center">minutes</div>
            </div>
            <span style="font-size:22px;color:#C8D8DE;padding-bottom:20px">:</span>
            <div class="flex-1">
              <input class="input" type="number" id="dlSecs" min="0" max="59" placeholder="00" style="text-align:center">
              <div class="text-xs text-muted mt-1" style="text-align:center">seconds</div>
            </div>
          </div>
        </div>`;
    } else {
      el.innerHTML = `
        <div class="form-group">
          <label class="label">${discipline === 'dynamic' ? 'Distance' : 'Depth'} (meters)</label>
          <input class="input" type="number" id="dlMeters" min="0.1" step="0.1" placeholder="${discipline === 'dynamic' ? 'e.g. 75' : 'e.g. 30'}">
        </div>`;
    }
  }

  renderFields();

  overlay.querySelectorAll('.disc-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      overlay.querySelectorAll('.disc-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      discipline = btn.dataset.d;
      renderFields();
    });
  });

  const closeModal = () => overlay.remove();
  overlay.querySelector('#dlClose').addEventListener('click', closeModal);
  overlay.querySelector('#dlCancel').addEventListener('click', closeModal);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) closeModal(); });

  overlay.querySelector('#dlSubmit').addEventListener('click', async () => {
    const errEl = overlay.querySelector('#dlErr');
    errEl.innerHTML = '';
    let value;
    if (discipline === 'static') {
      const m = parseInt(overlay.querySelector('#dlMins')?.value) || 0;
      const s = parseInt(overlay.querySelector('#dlSecs')?.value) || 0;
      value = m * 60 + s;
      if (value <= 0) { errEl.innerHTML = '<div class="alert-error">Enter a valid breath-hold time</div>'; return; }
    } else {
      value = parseFloat(overlay.querySelector('#dlMeters')?.value);
      if (!value || value <= 0) { errEl.innerHTML = '<div class="alert-error">Enter a valid distance in meters</div>'; return; }
    }
    const dive_date = overlay.querySelector('#dlDate').value;
    if (!dive_date) { errEl.innerHTML = '<div class="alert-error">Date is required</div>'; return; }

    const submitBtn = overlay.querySelector('#dlSubmit');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Saving…';
    try {
      const dive = await api.post('/dives', {
        discipline, value, dive_date,
        location: overlay.querySelector('#dlLoc').value,
        notes:    overlay.querySelector('#dlNotes').value,
      });
      onLogged && onLogged(dive);
      closeModal();
    } catch (e) {
      errEl.innerHTML = `<div class="alert-error">${e.error || 'Failed to log dive'}</div>`;
      submitBtn.disabled = false;
      submitBtn.textContent = 'Save dive';
    }
  });
}
