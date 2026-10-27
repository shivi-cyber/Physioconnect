/* PhysioConnect frontend core: API client, login state, formatting and UI helpers.
   Every page loads this file first and uses the global `PC` object. */
(function () {
  'use strict';

  const API_BASE = (window.PHYSIO_API_BASE || 'http://127.0.0.1:8000/api/v1').replace(/\/$/, '');
  const TZ = 'Asia/Kolkata';              // the clinic's time zone
  const KEY = { access: 'pc_access', refresh: 'pc_refresh', user: 'pc_user' };

  /* ------------------------------------------------------------------ DOM */
  function h(tag, attrs, ...kids) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === 'class') node.className = v;
      else if (k === 'html') node.innerHTML = v;            // trusted, static markup only
      else if (k.startsWith('on') && typeof v === 'function') node.addEventListener(k.slice(2).toLowerCase(), v);
      else node.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat(Infinity)) {
      if (kid == null || kid === false) continue;
      node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    }
    return node;
  }
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); return node; }

  const ICONS = {
    calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    arrow: '<path d="M5 12h14M12 5l7 7-7 7"/>',
    phone: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/>',
    mail: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/>',
    pin: '<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0z"/><circle cx="12" cy="10" r="3"/>',
    pulse: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    user: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    menu: '<path d="M3 6h18M3 12h18M3 18h18"/>',
    file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8"/>',
    badge: '<path d="M22 11.1V12a10 10 0 1 1-5.9-9.1"/><path d="m22 4-10 10-3-3"/>',
  };
  function icon(name, size = 20) {
    return h('span', { 'aria-hidden': 'true', style: 'display:inline-flex', html:
      `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ''}</svg>` });
  }

  /* ----------------------------------------------------------- formatting */
  const fmt = (opts) => new Intl.DateTimeFormat('en-IN', { timeZone: TZ, ...opts });
  const F_DATE = fmt({ weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
  const F_DATE_SHORT = fmt({ weekday: 'short', day: 'numeric', month: 'short' });
  const F_TIME = fmt({ hour: 'numeric', minute: '2-digit', hour12: true });
  const F_YMD = new Intl.DateTimeFormat('en-CA', { timeZone: TZ });
  const fmtDate = (iso) => F_DATE.format(new Date(iso));
  const fmtDateShort = (iso) => F_DATE_SHORT.format(new Date(iso));
  const fmtTime = (iso) => F_TIME.format(new Date(iso)).replace(' AM', ' am').replace(' PM', ' pm');
  const fmtDateTime = (iso) => `${fmtDate(iso)}, ${fmtTime(iso)}`;
  const ymdOf = (iso) => F_YMD.format(new Date(iso));
  const todayYMD = () => F_YMD.format(new Date());
  function addDays(ymd, n) {
    const d = new Date(`${ymd}T12:00:00Z`);
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  }
  function dateParts(ymd) {
    const d = new Date(`${ymd}T12:00:00Z`);
    return {
      dow: d.toLocaleDateString('en-IN', { weekday: 'short', timeZone: 'UTC' }),
      dom: d.getUTCDate(),
      mon: d.toLocaleDateString('en-IN', { month: 'short', timeZone: 'UTC' }),
      long: d.toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' }),
    };
  }
  function money(v) {
    const n = Number(v);
    if (Number.isNaN(n)) return '';
    return '\u20B9' + n.toLocaleString('en-IN', { minimumFractionDigits: n % 1 ? 2 : 0, maximumFractionDigits: 2 });
  }
  const initials = (name) => (name || '?').replace(/^Dr\.?\s+/i, '').split(/\s+/).slice(0, 2).map((p) => p[0]).join('').toUpperCase();
  const greeting = () => {
    const hr = Number(new Intl.DateTimeFormat('en-GB', { timeZone: TZ, hour: 'numeric', hour12: false }).format(new Date()));
    return hr < 12 ? 'Good morning' : hr < 17 ? 'Good afternoon' : 'Good evening';
  };

  const STATUS = {
    requested: ['Requested', 'neutral'], payment_pending: ['Payment pending', 'warn'], confirmed: ['Confirmed', 'info'],
    checked_in: ['Checked in', 'warn'], in_progress: ['In progress', 'brand'], completed: ['Completed', 'ok'],
    cancelled: ['Cancelled', 'neutral'], no_show: ['No show', 'bad'],
    pending: ['Unpaid', 'warn'], partially_paid: ['Part paid', 'warn'], paid: ['Paid', 'ok'], void: ['Void', 'neutral'], refunded: ['Refunded', 'neutral'],
  };
  const statusPill = (s) => { const [label, kind] = STATUS[s] || [s, 'neutral']; return h('span', { class: `pill pill-${kind}` }, label); };

  /* ----------------------------------------------------------------- auth */
  const store = {
    get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
    set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* storage blocked */ } },
    del: (k) => { try { localStorage.removeItem(k); } catch { /* ignore */ } },
  };
  const getUser = () => { try { return JSON.parse(store.get(KEY.user) || 'null'); } catch { return null; } };
  const isLoggedIn = () => !!store.get(KEY.access) && !!getUser();
  function saveSession(data) {
    store.set(KEY.access, data.access); store.set(KEY.refresh, data.refresh); store.set(KEY.user, JSON.stringify(data.user));
  }
  function logout(redirect = 'index.html') {
    Object.values(KEY).forEach(store.del);
    if (redirect) location.href = redirect;
  }

  class ApiError extends Error {
    constructor(code, message, status, details) { super(message); this.code = code; this.status = status; this.details = details || {}; }
  }

  let refreshing = null;
  async function refreshAccess() {
    const refresh = store.get(KEY.refresh);
    if (!refresh) return false;
    refreshing = refreshing || fetch(`${API_BASE}/auth/refresh/`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh }),
    }).then(async (r) => { if (!r.ok) return false; const d = await r.json(); store.set(KEY.access, d.access); if (d.refresh) store.set(KEY.refresh, d.refresh); return true; })
      .catch(() => false).finally(() => { refreshing = null; });
    return refreshing;
  }

  /** Call the backend. Throws ApiError with the backend's error code/message. */
  async function api(path, { method = 'GET', body, auth = true, _retried = false } = {}) {
    const headers = {};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    const token = store.get(KEY.access);
    if (auth && token) headers.Authorization = `Bearer ${token}`;
    let res;
    try {
      res = await fetch(API_BASE + path, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined });
    } catch {
      throw new ApiError('NETWORK', 'Cannot reach the server. Check that the backend is running.', 0);
    }
    if (res.status === 401 && auth && !_retried && store.get(KEY.refresh)) {
      if (await refreshAccess()) return api(path, { method, body, auth, _retried: true });
      logout(`login.html?next=${encodeURIComponent(currentPage())}&expired=1`);
    }
    let data = null;
    try { data = await res.json(); } catch { /* empty body */ }
    if (!res.ok) {
      const e = (data && data.error) || {};
      throw new ApiError(e.code || 'ERROR', e.message || 'Something went wrong. Please try again.', res.status, e.details);
    }
    return data;
  }
  const currentPage = () => (location.pathname.split('/').pop() || 'index.html') + location.search;

  /** Redirect to login if needed. Returns the user, or null (and redirects) when not allowed. */
  function requireAuth(roles) {
    if (!isLoggedIn()) { location.href = `login.html?next=${encodeURIComponent(currentPage())}`; return null; }
    const user = getUser();
    if (roles && !roles.includes(user.role)) { location.href = 'dashboard.html'; return null; }
    return user;
  }

  /** Turn an API error into friendly field messages for forms. */
  function fieldErrors(err) {
    const out = {};
    for (const [k, v] of Object.entries(err.details || {})) out[k] = Array.isArray(v) ? v.join(' ') : String(v);
    return out;
  }

  /* ------------------------------------------------------------------- UI */
  function toast(message, kind = '') {
    let box = $('#toasts');
    if (!box) { box = h('div', { id: 'toasts', class: 'toasts', 'aria-live': 'polite', role: 'status' }); document.body.append(box); }
    const t = h('div', { class: `toast ${kind}` }, message);
    box.append(t);
    setTimeout(() => t.remove(), 5200);
  }

  function modal({ title, body, actions = [], wide = false, onClose }) {
    const previous = document.activeElement;
    const close = () => { backdrop.remove(); document.removeEventListener('keydown', onKey); if (previous && previous.focus) previous.focus(); if (onClose) onClose(); };
    const onKey = (e) => { if (e.key === 'Escape') close(); };
    const foot = actions.length ? h('div', { class: 'modal-foot' }, actions.map((a) => {
      const b = h('button', { type: 'button', class: `btn btn-sm btn-${a.kind || 'secondary'}` }, a.label);
      b.addEventListener('click', async () => {
        if (!a.onClick) { close(); return; }
        b.disabled = true;
        try { const keepOpen = await a.onClick({ close, button: b }); if (keepOpen !== false) close(); }
        finally { b.disabled = false; }
      });
      return b;
    })) : null;
    const dialog = h('div', { class: `modal${wide ? ' wide' : ''}`, role: 'dialog', 'aria-modal': 'true', 'aria-label': title },
      h('div', { class: 'modal-head' }, h('h2', {}, title),
        h('button', { type: 'button', class: 'btn btn-ghost btn-sm', 'aria-label': 'Close', onclick: close }, icon('x'))),
      h('div', { class: 'modal-body' }, body), foot);
    const backdrop = h('div', { class: 'modal-backdrop' }, dialog);
    backdrop.addEventListener('mousedown', (e) => { if (e.target === backdrop) close(); });
    document.addEventListener('keydown', onKey);
    document.body.append(backdrop);
    const first = $('input, select, textarea, button.slot, button', dialog.querySelector('.modal-body')) || $('button', dialog);
    if (first) first.focus();
    return { close, el: dialog };
  }

  function confirmDialog({ title, message, confirmLabel = 'Confirm', danger = false, withReason = false }) {
    return new Promise((resolve) => {
      const reason = withReason ? h('textarea', { class: 'input', placeholder: 'Reason (optional)', 'aria-label': 'Reason', maxlength: '255' }) : null;
      let done = false;
      const finish = (v) => { if (!done) { done = true; resolve(v); } };
      modal({
        title, body: h('div', {}, h('p', {}, message), reason),
        onClose: () => finish(null),
        actions: [
          { label: 'Go back', kind: 'ghost' },
          { label: confirmLabel, kind: danger ? 'danger' : 'primary', onClick: () => { finish({ reason: reason ? reason.value.trim() : '' }); } },
        ],
      });
    });
  }

  function skeleton(n = 3) { return h('div', { class: 'list', 'aria-busy': 'true' }, Array.from({ length: n }, () => h('div', { class: 'skeleton' }))); }
  function empty(title, text, action) {
    return h('div', { class: 'empty' }, h('h2', { class: 'title-sm' }, title), h('p', {}, text), action || null);
  }
  function errorBox(err) { return h('div', { class: 'form-error', role: 'alert' }, err.message || String(err)); }

  /** Button state helper: disables while a task runs. */
  async function busy(button, task) {
    button.disabled = true;
    try { return await task(); } finally { button.disabled = false; }
  }

  /* ---------------------------------------------------------- site chrome */
  function renderChrome(active) {
    const user = getUser();
    const logged = isLoggedIn();
    const link = (href, text, key) => h('a', { href, 'aria-current': active === key ? 'page' : null }, text);
    const links = h('nav', { class: 'nav-links', id: 'nav-links', 'aria-label': 'Main' },
      link('index.html#services', 'Services', 'services'),
      link('index.html#doctors', 'Our doctors', 'doctors'),
      logged ? link('dashboard.html', 'My dashboard', 'dashboard') : link('login.html', 'Log in', 'login'),
      logged ? h('button', { type: 'button', class: 'btn btn-ghost btn-sm', onclick: () => logout() }, icon('logout', 18), 'Log out') : null,
      h('a', { class: 'btn btn-primary btn-sm', href: 'book.html' }, 'Book appointment'));
    const toggle = h('button', { type: 'button', class: 'btn btn-ghost nav-toggle', 'aria-label': 'Menu', 'aria-expanded': 'false', 'aria-controls': 'nav-links',
      onclick: (e) => { const open = links.classList.toggle('open'); e.currentTarget.setAttribute('aria-expanded', String(open)); } }, icon('menu', 24));
    const header = $('#site-header');
    if (header) {
      header.className = 'site-header';
      header.append(h('div', { class: 'container nav' },
        h('a', { class: 'brand', href: 'index.html', 'aria-label': 'PhysioConnect home' },
          h('span', { class: 'brand-mark' }, icon('pulse', 20)), 'PhysioConnect'),
        toggle, links));
    }
    const footer = $('#site-footer');
    if (footer) {
      footer.className = 'site-footer';
      const info = h('div', { id: 'footer-contact' }, h('p', {}, 'Physiotherapy appointments, treatment notes and billing in one place.'));
      footer.append(h('div', { class: 'container' },
        h('div', { class: 'footer-grid' },
          h('div', {}, h('div', { class: 'brand', style: 'color:#fff;margin-bottom:12px' }, h('span', { class: 'brand-mark' }, icon('pulse', 20)), 'PhysioConnect'), info),
          h('div', {}, h('h2', { class: 'footer-title' }, 'Patients'), h('p', {}, h('a', { href: 'book.html' }, 'Book an appointment')), h('p', {}, h('a', { href: 'login.html' }, 'Log in or create an account'))),
          h('div', {}, h('h2', { class: 'footer-title' }, 'Your privacy'), h('p', {}, 'Treatment notes are visible only to your treating doctor and clinic administrators.'))),
        h('p', { class: 'footer-note' }, `\u00A9 ${new Date().getFullYear()} PhysioConnect Clinic. Times are shown in India Standard Time.`)));
    }
    if (!$('.skip-link')) document.body.prepend(h('a', { class: 'skip-link', href: '#main' }, 'Skip to content'));
  }

  /* ---------------------------------------------------------- slot picker */
  /** Date strip + time chips for one doctor and service. */
  function slotPicker(container, { doctorId, serviceId, days = 14, onSelect }) {
    let selectedDay = null; let selectedStart = null; let byDay = {};
    const dayLabel = h('h3', { id: 'slot-day-label', style: 'margin-top:24px' });
    const strip = h('div', { class: 'date-strip', role: 'group', 'aria-label': 'Choose a date' });
    const slotsBox = h('div', { class: 'slots', role: 'group', 'aria-labelledby': 'slot-day-label' });
    const hint = h('p', { class: 'hint' });
    clear(container).append(skeleton(2));

    function renderSlots() {
      clear(slotsBox);
      const list = byDay[selectedDay] || [];
      dayLabel.textContent = `Available times on ${dateParts(selectedDay).long}`;
      list.forEach((s) => {
        const b = h('button', { type: 'button', class: 'slot', 'aria-pressed': String(s.start === selectedStart) }, fmtTime(s.start));
        b.addEventListener('click', () => { selectedStart = s.start; onSelect && onSelect(s); renderSlots(); });
        slotsBox.append(b);
      });
    }
    function renderStrip() {
      clear(strip);
      Object.keys(byDay).forEach((ymd) => {
        const p = dateParts(ymd); const count = byDay[ymd].length;
        const b = h('button', { type: 'button', class: 'date-btn', 'aria-pressed': String(ymd === selectedDay), disabled: count === 0,
          'aria-label': `${p.long}${count ? `, ${count} times available` : ', no times available'}` },
          h('span', { class: 'dow' }, p.dow), h('span', { class: 'dom' }, p.dom), h('span', { class: 'mon' }, p.mon));
        b.addEventListener('click', () => { selectedDay = ymd; selectedStart = null; onSelect && onSelect(null); renderStrip(); renderSlots(); });
        strip.append(b);
      });
    }
    async function load() {
      const today = todayYMD();
      const dates = Array.from({ length: days }, (_, i) => addDays(today, i));
      const results = await Promise.all(dates.map((d) =>
        api(`/doctors/${doctorId}/available-slots/?date=${d}&service_id=${serviceId}`, { auth: false }).then((r) => r.slots).catch(() => [])));
      byDay = {}; dates.forEach((d, i) => { byDay[d] = results[i]; });
      const first = dates.find((d) => byDay[d].length);
      clear(container);
      if (!first) { container.append(empty('No times available', `There are no free times in the next ${days} days. Please call the clinic or try another doctor.`)); return; }
      selectedDay = first; selectedStart = null;
      hint.textContent = `Earliest availability: ${dateParts(first).long}. Times are in India Standard Time (IST).`;
      container.append(hint, strip, dayLabel, slotsBox);
      renderStrip(); renderSlots();
    }
    load();
    return { reload: load, getSelected: () => selectedStart };
  }

  /** Front-desk form to register a walk-in patient. onDone(patient) runs after success. */
  function registerPatientModal(onDone) {
    const f = (name, label, attrs = {}) => h('div', { class: 'field' }, h('label', { for: `np-${name}` }, label), h('input', { class: 'input', id: `np-${name}`, name, ...attrs }));
    const form = h('form', { novalidate: true }, h('div', { id: 'np-err' }),
      h('div', { class: 'form-grid' }, f('first_name', 'First name', { required: true }), f('last_name', 'Last name', { required: true })),
      f('phone', 'Phone number', { type: 'tel', required: true }), f('email', 'Email (optional)', { type: 'email' }));
    modal({
      title: 'Register new patient', body: form,
      actions: [{ label: 'Cancel', kind: 'ghost' }, { label: 'Register patient', kind: 'primary', onClick: async () => {
        const body = Object.fromEntries(new FormData(form).entries()); if (!body.email) delete body.email;
        form.querySelectorAll('.field-error').forEach((n) => n.remove()); clear($('#np-err'));
        try {
          const p = await api('/patients/', { method: 'POST', body });
          toast('Patient registered', 'ok'); onDone && onDone(p); return true;
        } catch (e) {
          const fe = fieldErrors(e);
          Object.entries(fe).forEach(([k, m]) => { const el = form.elements[k]; if (el) el.closest('.field').append(h('span', { class: 'field-error', role: 'alert' }, m)); });
          if (!Object.keys(fe).length) $('#np-err').append(errorBox(e));
          return false;
        }
      } }],
    });
  }

  window.PC = {
    API_BASE, TZ, h, $, $$, clear, icon, api, ApiError, fieldErrors,
    fmtDate, fmtDateShort, fmtTime, fmtDateTime, ymdOf, todayYMD, addDays, dateParts, money, initials, greeting, statusPill,
    getUser, isLoggedIn, saveSession, logout, requireAuth,
    toast, modal, confirmDialog, skeleton, empty, errorBox, busy, renderChrome, slotPicker, store, registerPatientModal,
  };
})();