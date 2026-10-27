(function () {
  'use strict';
  const { h, $, api, renderChrome, saveSession, isLoggedIn, fieldErrors, busy } = PC;
  renderChrome('login');

  const params = new URLSearchParams(location.search);
  const next = params.get('next');
  // Only follow relative links inside this site
  const safeNext = next && /^[a-z0-9_-]+\.html(\?.*)?$/i.test(next) ? next : 'dashboard.html';
  if (isLoggedIn() && !params.get('expired')) location.replace(safeNext);

  if (params.get('expired')) $('#notice').append(h('div', { class: 'form-error', role: 'status' }, 'Your session ended. Please log in again.'));
  else if (next && next.startsWith('book')) $('#notice').append(h('div', { class: 'callout', role: 'status' }, h('div', { class: 'grow' }, 'Log in or create an account to confirm your booking. Your choices are saved.')));

  /* tabs */
  const tabs = { login: [$('#tab-login'), $('#panel-login')], register: [$('#tab-register'), $('#panel-register')] };
  function show(name) {
    Object.entries(tabs).forEach(([k, [tab, panel]]) => { tab.setAttribute('aria-selected', String(k === name)); panel.classList.toggle('hidden', k !== name); });
  }
  Object.entries(tabs).forEach(([k, [tab]]) => tab.addEventListener('click', () => show(k)));
  if (params.get('tab') === 'register') show('register');

  function showErrors(form, errBox, err) {
    errBox.replaceChildren();
    form.querySelectorAll('.field-error').forEach((n) => n.remove());
    const fields = fieldErrors(err);
    const leftovers = [];
    Object.entries(fields).forEach(([name, msg]) => {
      const input = form.elements[name];
      if (input && input.closest('.field')) { input.closest('.field').append(h('span', { class: 'field-error', role: 'alert' }, msg)); input.setAttribute('aria-invalid', 'true'); }
      else leftovers.push(msg);       // e.g. "This password is too common."
    });
    if (leftovers.length) errBox.append(h('div', { class: 'form-error', role: 'alert' }, leftovers.join(' ')));
    else if (!Object.keys(fields).length) errBox.append(h('div', { class: 'form-error', role: 'alert' }, err.message));
  }

  async function submit(form, errBox, path) {
    const btn = form.querySelector('button[type=submit]');
    const body = Object.fromEntries(new FormData(form).entries());
    if (!body.phone) delete body.phone;
    await busy(btn, async () => {
      try {
        const data = await api(path, { method: 'POST', body, auth: false });
        saveSession(data);
        location.href = safeNext;
      } catch (e) { showErrors(form, errBox, e); }
    });
  }
  $('#form-login').addEventListener('submit', (e) => { e.preventDefault(); submit(e.target, $('#login-error'), '/auth/login/'); });
  $('#form-register').addEventListener('submit', (e) => { e.preventDefault(); submit(e.target, $('#register-error'), '/auth/register/'); });

  /* demo accounts */
  const demo = [
    ['Patient', 'patient@physioconnect.demo'], ['Receptionist', 'reception@physioconnect.demo'],
    ['Doctor (Arjun Mehta)', 'arjun.mehta@physioconnect.demo'], ['Doctor (Neha Kapoor)', 'neha.kapoor@physioconnect.demo'],
  ];
  $('#demo-list').append(...demo.map(([label, email]) => h('button', { type: 'button', onclick: () => {
    show('login'); $('#l-id').value = email; $('#l-pw').value = 'Demo@12345'; $('#l-pw').focus();
  } }, `${label}: ${email}`)));
})();