(function () {
  'use strict';
  const { h, $, clear, icon, api, money, initials, fmtTime, fmtDateShort, fmtDateTime, fmtDate, todayYMD, addDays, statusPill,
    renderChrome, toast, modal, confirmDialog, busy, skeleton, empty, errorBox } = PC;

  const user = PC.requireAuth();
  if (!user) return;
  renderChrome('dashboard');

  const role = user.role;
  const ROLE_LABEL = { patient: 'Patient', doctor: 'Doctor', receptionist: 'Front desk', admin: 'Administrator' };
  const root = $('#dash');
  const CHANGEABLE = ['requested', 'payment_pending', 'confirmed'];

  /* ======================================================== shared pieces */
  function tabs(container, defs) {
    const bar = h('div', { class: 'tabs', role: 'tablist', style: 'max-width:520px' });
    const panel = h('div', { role: 'tabpanel', tabindex: '0' });
    const buttons = defs.map((d) => {
      const b = h('button', { class: 'tab', role: 'tab', type: 'button', id: `tab-${d.id}`, 'aria-selected': 'false' }, d.label);
      b.addEventListener('click', () => select(d.id)); bar.append(b); return b;
    });
    function select(id) {
      defs.forEach((d, i) => buttons[i].setAttribute('aria-selected', String(d.id === id)));
      panel.setAttribute('aria-labelledby', `tab-${id}`);
      clear(panel); defs.find((d) => d.id === id).render(panel);
    }
    container.append(bar, panel); select(defs[0].id);
    return { select };
  }

  /** Load a paged API list into a container. */
  async function loadList(box, path, renderItem, emptyView) {
    clear(box).append(skeleton(3));
    try {
      const data = await api(path);
      clear(box);
      if (!data.results.length) { box.append(emptyView); return; }
      const list = h('div', { class: 'list' }, data.results.map(renderItem)); box.append(list);
      let next = data.next;
      if (next) {
        const more = h('button', { class: 'btn btn-secondary', type: 'button', style: 'margin-top:16px' }, 'Load more');
        more.addEventListener('click', () => PC.busy(more, async () => {
          const d = await api(next.replace(PC.API_BASE, '')); d.results.forEach((r) => list.append(renderItem(r)));
          next = d.next; if (!next) more.remove();
        }));
        box.append(more);
      }
    } catch (e) {
      clear(box).append(errorBox(e), h('button', { class: 'btn btn-secondary btn-sm', type: 'button', onclick: () => loadList(box, path, renderItem, emptyView) }, 'Try again'));
    }
  }

  const btn = (label, kind, onClick, ic) => h('button', { type: 'button', class: `btn btn-sm btn-${kind}`, onclick: (e) => PC.busy(e.currentTarget, onClick) }, ic ? icon(ic, 16) : null, label);

  function invoicePill(inv) {
    if (!inv) return null;
    const due = Number(inv.amount_due);
    return h('span', { class: `pill pill-${due > 0 ? 'warn' : 'ok'}` }, due > 0 ? `Due ${money(due)}` : 'Paid');
  }

  /** One appointment as a row. opts: { who: 'patient'|'doctor', actions: [] } */
  function apptItem(a, { who, actions = [], wide = false, billing = true }) {
    const name = who === 'patient' ? a.patient.name : a.doctor.name;
    return h('article', { class: wide ? 'item item-wide' : 'item' },
      h('div', { class: 'when' }, h('div', { class: 't' }, fmtTime(a.scheduled_start)), h('div', { class: 'd' }, fmtDateShort(a.scheduled_start))),
      h('div', {}, h('div', { class: 'title' }, name),
        h('div', { class: 'small muted' }, `${a.service.name} | ${a.service.duration_minutes} min${who === 'patient' ? ` | ${a.doctor.name}` : ''}`),
        h('div', { class: 'row', style: 'margin-top:8px;gap:8px' }, statusPill(a.status), billing && a.status !== 'cancelled' ? invoicePill(a.invoice) : null)),
      h('div', { class: 'actions' }, actions.filter(Boolean)));
  }

  function head(extra) {
    return h('div', { class: 'dash-head row-between' },
      h('div', {}, h('span', { class: 'pill pill-brand', style: 'margin-bottom:8px' }, ROLE_LABEL[role] || role),
        h('h1', { style: 'font-size:2rem;margin:0' }, `${PC.greeting()}, ${user.first_name || user.full_name}`)), extra);
  }
  const stat = (v, l) => h('div', { class: 'stat' }, h('div', { class: 'v' }, v), h('div', { class: 'l' }, l));

  /* --------------------------------------------------- appointment actions */
  async function act(path, body, done, okMsg) {
    try { await api(path, { method: 'POST', body }); if (okMsg) toast(okMsg, 'ok'); done(); }
    catch (e) { toast(e.message, 'bad'); }
  }
  async function cancelAppt(a, done) {
    const r = await confirmDialog({ title: 'Cancel this appointment?', message: `${fmtDateTime(a.scheduled_start)} with ${a.doctor.name}. This frees the time for other patients.`, confirmLabel: 'Cancel appointment', danger: true, withReason: true });
    if (r) await act(`/appointments/${a.id}/cancel/`, { reason: r.reason }, done, 'Appointment cancelled');
  }
  function rescheduleAppt(a, done) {
    let chosen = null; const holder = h('div');
    modal({
      title: 'Choose a new time', wide: true,
      body: h('div', {}, h('p', { class: 'muted' }, `${a.service.name} with ${a.doctor.name}. Currently ${fmtDateTime(a.scheduled_start)}.`), holder),
      actions: [{ label: 'Keep current time', kind: 'ghost' }, { label: 'Move appointment', kind: 'primary', onClick: async () => {
        if (!chosen) { toast('Please pick a new time first', 'bad'); return false; }
        try { await api(`/appointments/${a.id}/reschedule/`, { method: 'POST', body: { scheduled_start: chosen.start } }); toast('Appointment moved', 'ok'); done(); return true; }
        catch (e) { toast(e.message, 'bad'); return false; }
      } }],
    });
    PC.slotPicker(holder, { doctorId: a.doctor.id, serviceId: a.service.id, onSelect: (s) => { chosen = s; } });
  }

  /* ------------------------------------------------------------- payments */
  function paymentModal(inv, done) {
    const due = Number(inv.amount_due !== undefined ? inv.amount_due : inv.total);
    const amount = h('input', { class: 'input', id: 'pay-amount', type: 'number', min: '0.01', step: '0.01', value: due.toFixed(2) });
    const method = h('select', { class: 'input', id: 'pay-method' }, ['cash:Cash', 'upi:UPI', 'pos_card:Card (POS machine)', 'other:Other'].map((o) => { const [v, l] = o.split(':'); return h('option', { value: v }, l); }));
    const err = h('div', { 'aria-live': 'polite' });
    modal({
      title: 'Take payment',
      body: h('div', {}, h('p', { class: 'muted' }, `${inv.invoice_number || ''} | Total ${money(inv.total)} | Balance due ${money(due)}`), err,
        h('div', { class: 'field' }, h('label', { for: 'pay-amount' }, 'Amount received (Rs)'), amount),
        h('div', { class: 'field' }, h('label', { for: 'pay-method' }, 'Payment method'), method)),
      actions: [{ label: 'Cancel', kind: 'ghost' }, { label: 'Record payment', kind: 'primary', onClick: async () => {
        clear(err);
        try { await api(`/invoices/${inv.id}/manual-payment/`, { method: 'POST', body: { amount: amount.value, method: method.value } }); toast('Payment recorded', 'ok'); done(); return true; }
        catch (e) { err.append(errorBox(e)); return false; }
      } }],
    });
  }

  function invoiceItem(inv, { who, canPay, done }) {
    return h('article', { class: 'item', style: 'grid-template-columns:1fr auto' },
      h('div', {}, h('div', { class: 'title' }, `${inv.invoice_number}${who === 'patient' ? '' : ` | ${inv.patient_name}`}`),
        h('div', { class: 'small muted' }, `${inv.line_items.map((l) => l.description).join(', ')}${inv.appointment_start ? ` | ${fmtDateTime(inv.appointment_start)}` : ''}`),
        h('div', { class: 'row', style: 'margin-top:8px;gap:8px' }, statusPill(inv.status), h('span', { class: 'small muted' }, `Total ${money(inv.total)} | Paid ${money(inv.amount_paid)} | Due ${money(inv.amount_due)}`))),
      h('div', { class: 'actions' }, canPay && Number(inv.amount_due) > 0 && !['void', 'refunded'].includes(inv.status) ? btn('Take payment', 'primary', () => paymentModal(inv, done), 'file') : null));
  }

  /* ------------------------------------------------------ patient history */
  function soapView(n) {
    if (!n || !(n.subjective || n.objective || n.assessment || n.plan)) return h('p', { class: 'small muted' }, 'No notes for this visit.');
    return h('dl', { class: 'soap' }, [['Subjective', n.subjective], ['Objective', n.objective], ['Assessment', n.assessment], ['Plan', n.plan]]
      .filter(([, v]) => v).map(([k, v]) => [h('dt', {}, k), h('dd', {}, v)]));
  }
  async function historyModal(patientId, patientName) {
    const body = h('div', {}, skeleton(2));
    const m = modal({ title: patientName, body, wide: true, actions: [{ label: 'Close', kind: 'secondary' }] });
    const clinical = role === 'doctor' || role === 'admin';
    try {
      const [hist, profile] = await Promise.all([api(`/patients/${patientId}/history/`), clinical ? api(`/patients/${patientId}/medical-profile/`) : null]);
      const p = hist.patient; clear(body);
      body.append(h('p', { class: 'muted' }, [p.phone, p.email, p.dob ? `Born ${p.dob}` : '', p.gender].filter(Boolean).join(' | ') || 'No contact details on file.'));
      if (profile) body.append(profileForm(patientId, profile));
      body.append(h('h3', { style: 'margin-top:24px' }, 'Visit history'));
      if (!hist.visits.length) body.append(h('p', { class: 'muted' }, 'No visits yet.'));
      hist.visits.forEach((v) => body.append(h('div', { class: 'visit' },
        h('div', { class: 'row-between' }, h('strong', {}, fmtDateTime(v.scheduled_start)), statusPill(v.status)),
        h('div', { class: 'small muted', style: 'margin-bottom:8px' }, `${v.service.name} with ${v.doctor.name}`),
        clinical ? soapView(v.notes) : null)));
    } catch (e) { clear(body).append(errorBox(e)); }
    return m;
  }
  function profileForm(patientId, profile) {
    const list = (arr) => (Array.isArray(arr) ? arr.join(', ') : '');
    const f = (id, label, el) => h('div', { class: 'field' }, h('label', { for: id }, label), el);
    const cond = h('input', { class: 'input', id: 'mp-cond', value: list(profile.known_conditions), placeholder: 'e.g. Diabetes, Asthma' });
    const all = h('input', { class: 'input', id: 'mp-all', value: list(profile.allergies), placeholder: 'e.g. Penicillin' });
    const meds = h('textarea', { class: 'input', id: 'mp-meds' }, profile.current_medications || '');
    const save = h('button', { class: 'btn btn-secondary btn-sm', type: 'button' }, 'Save medical details');
    const split = (v) => v.split(',').map((x) => x.trim()).filter(Boolean);
    save.addEventListener('click', () => PC.busy(save, async () => {
      try { await api(`/patients/${patientId}/medical-profile/`, { method: 'PATCH', body: { known_conditions: split(cond.value), allergies: split(all.value), current_medications: meds.value } }); toast('Medical details saved', 'ok'); }
      catch (e) { toast(e.message, 'bad'); }
    }));
    return h('details', { class: 'card card-flat', open: true, style: 'padding:16px 20px' }, h('summary', { style: 'font-weight:700;cursor:pointer;min-height:32px' }, 'Medical details'),
      h('div', { style: 'margin-top:12px' }, f('mp-cond', 'Known conditions (comma separated)', cond), f('mp-all', 'Allergies (comma separated)', all), f('mp-meds', 'Current medications', meds), save));
  }

  /* ---------------------------------------------------------- SOAP notes */
  async function notesModal(a, done) {
    const fields = [['subjective', 'Subjective', "Patient's own description of symptoms"], ['objective', 'Objective', 'Clinical observations and measurements'],
      ['assessment', 'Assessment', 'Diagnosis or interpretation'], ['plan', 'Plan', 'Treatment plan going forward']];
    const inputs = {}; const body = h('div', {}, skeleton(1));
    modal({
      title: `Notes: ${a.patient.name}`, body, wide: true,
      actions: [{ label: 'Close', kind: 'ghost' }, { label: 'Save notes', kind: 'primary', onClick: async () => {
        try { await api(`/appointments/${a.id}/notes/`, { method: 'PUT', body: Object.fromEntries(Object.entries(inputs).map(([k, el]) => [k, el.value])) }); toast('Notes saved', 'ok'); done && done(); return true; }
        catch (e) { toast(e.message, 'bad'); return false; }
      } }],
    });
    try {
      const n = await api(`/appointments/${a.id}/notes/`); clear(body);
      body.append(h('p', { class: 'muted' }, `${fmtDateTime(a.scheduled_start)} | ${a.service.name}`));
      fields.forEach(([k, label, hint]) => {
        inputs[k] = h('textarea', { class: 'input', id: `n-${k}` }, n[k] || '');
        body.append(h('div', { class: 'field' }, h('label', { for: `n-${k}` }, label), h('span', { class: 'hint' }, hint), inputs[k]));
      });
    } catch (e) { clear(body).append(errorBox(e)); }
  }

  /* ============================================================ PATIENT */
  async function patientView() {
    root.append(head(h('a', { class: 'btn btn-primary', href: 'book.html' }, icon('plus', 18), 'Book appointment')));
    const statsBox = h('div'); const nextBox = h('div'); const tabsBox = h('div'); root.append(statsBox, nextBox, tabsBox);
    try {
      const d = await api('/dashboard/');
      statsBox.append(h('div', { class: 'stats' }, stat(d.upcoming_count, 'Upcoming appointments'), stat(d.unpaid_invoices, 'Unpaid invoices')));
      if (d.next_appointment) nextBox.append(h('div', { class: 'callout' }, icon('calendar', 28),
        h('div', { class: 'grow' }, h('strong', {}, 'Your next appointment'), h('div', {}, `${fmtDateTime(d.next_appointment.scheduled_start)} with ${d.next_appointment.doctor.name}`))));
    } catch (e) { statsBox.append(errorBox(e)); }

    const reload = () => tabsApi.select(current);
    let current = 'upcoming';
    const upcomingTab = (panel) => {
      current = 'upcoming';
      loadList(panel, '/appointments/?scope=upcoming', (a) => apptItem(a, { who: 'doctor', actions: CHANGEABLE.includes(a.status)
        ? [btn('Reschedule', 'secondary', () => rescheduleAppt(a, reload), 'calendar'), btn('Cancel', 'danger', () => cancelAppt(a, reload))] : [] }),
      empty('No upcoming appointments', 'Book a session and it will appear here.', h('a', { class: 'btn btn-primary', href: 'book.html' }, 'Book an appointment')));
    };
    // History = visits that have ended plus anything cancelled, newest first
    const historyTab = async (panel) => {
      current = 'history'; clear(panel).append(skeleton(3));
      try {
        const [past, cancelled] = await Promise.all([api('/appointments/?scope=past'), api('/appointments/?status=cancelled')]);
        const seen = new Set(); const rows = [];
        [...past.results, ...cancelled.results].forEach((a) => { if (!seen.has(a.id)) { seen.add(a.id); rows.push(a); } });
        rows.sort((x, y) => new Date(y.scheduled_start) - new Date(x.scheduled_start));
        clear(panel);
        if (!rows.length) { panel.append(empty('No history yet', 'Completed and cancelled visits will appear here.')); return; }
        panel.append(h('div', { class: 'list' }, rows.map((a) => apptItem(a, { who: 'doctor' }))));
      } catch (e) { clear(panel).append(errorBox(e)); }
    };
    const tabsApi = tabs(tabsBox, [
      { id: 'upcoming', label: 'Upcoming', render: upcomingTab },
      { id: 'history', label: 'History', render: historyTab },
      { id: 'invoices', label: 'Invoices', render: (panel) => { current = 'invoices'; loadList(panel, '/invoices/', (i) => invoiceItem(i, { who: 'patient', canPay: false }), empty('No invoices yet', 'An invoice is created when you book. You pay at the clinic.')); } },
    ]);
  }

  /* ========================================================== FRONT DESK */
  async function staffView() {
    root.append(head(h('div', { class: 'row' },
      h('button', { class: 'btn btn-secondary', type: 'button', onclick: () => PC.registerPatientModal(() => { if (tabsApi) tabsApi.select('patients'); }) }, icon('user', 18), 'Register patient'),
      h('a', { class: 'btn btn-primary', href: 'book.html' }, icon('plus', 18), 'New booking'))));
    const statsBox = h('div'); const tabsBox = h('div'); root.append(statsBox, tabsBox);
    async function loadStats() {
      try {
        const d = await api('/dashboard/'); clear(statsBox);
        const by = d.today_by_status || {};
        statsBox.append(h('div', { class: 'stats' }, stat(d.today_total, "Today's appointments"), stat(by.checked_in || 0, 'Checked in now'),
          stat(money(d.collected_today || 0), 'Collected today'), stat(d.outstanding_invoices, 'Unpaid invoices')));
      } catch (e) { clear(statsBox).append(errorBox(e)); }
    }
    loadStats();

    let doctors = [];
    try { doctors = await api('/doctors/', { auth: false }); } catch { /* filter is optional */ }
    const state = { date: todayYMD(), doctor: '' };

    function schedule(panel) {
      const list = h('div');
      const date = h('input', { class: 'input', type: 'date', id: 'f-date', value: state.date, style: 'width:auto' });
      const doc = h('select', { class: 'input', id: 'f-doc', style: 'width:auto' }, h('option', { value: '' }, 'All doctors'), doctors.map((d) => h('option', { value: d.id, selected: d.id === state.doctor }, d.name)));
      const load = () => {
        state.date = date.value || todayYMD(); state.doctor = doc.value;
        const q = `/appointments/?date=${state.date}${state.doctor ? `&doctor=${state.doctor}` : ''}`;
        const refresh = () => { load(); loadStats(); };
        loadList(list, q, (a) => apptItem(a, { who: 'patient', wide: true, actions: [
          ['requested', 'confirmed'].includes(a.status) ? btn('Check in', 'primary', () => act(`/appointments/${a.id}/check-in/`, {}, refresh, 'Checked in'), 'check') : null,
          a.invoice && Number(a.invoice.amount_due) > 0 && a.status !== 'cancelled' ? btn('Take payment', 'secondary', async () => paymentModal({ id: a.invoice.id, invoice_number: a.invoice.invoice_number, total: a.invoice.total, amount_due: a.invoice.amount_due }, refresh), 'file') : null,
          CHANGEABLE.includes(a.status) ? btn('Reschedule', 'ghost', () => rescheduleAppt(a, refresh)) : null,
          ['requested', 'confirmed', 'checked_in'].includes(a.status) ? btn('No show', 'ghost', () => act(`/appointments/${a.id}/no-show/`, {}, refresh, 'Marked as no show')) : null,
          CHANGEABLE.includes(a.status) ? btn('Cancel', 'danger', () => cancelAppt(a, refresh)) : null,
        ] }), empty('No appointments', `Nothing booked for ${fmtDate(`${state.date}T12:00:00+05:30`)}.`));
      };
      const shift = (n) => { date.value = addDays(date.value || todayYMD(), n); load(); };
      panel.append(h('div', { class: 'toolbar' },
        h('div', { class: 'field' }, h('label', { for: 'f-date' }, 'Date'), date), h('div', { class: 'field' }, h('label', { for: 'f-doc' }, 'Doctor'), doc),
        h('button', { class: 'btn btn-ghost btn-sm', type: 'button', onclick: () => shift(-1) }, 'Previous day'),
        h('button', { class: 'btn btn-ghost btn-sm', type: 'button', onclick: () => { date.value = todayYMD(); load(); } }, 'Today'),
        h('button', { class: 'btn btn-ghost btn-sm', type: 'button', onclick: () => shift(1) }, 'Next day')), list);
      date.addEventListener('change', load); doc.addEventListener('change', load); load();
    }

    function patients(panel) {
      const list = h('div'); let timer;
      const q = h('input', { class: 'input', id: 'pq', type: 'search', placeholder: 'Search by name, phone or email', 'aria-label': 'Search patients', style: 'max-width:420px' });
      const load = () => loadList(list, `/patients/?q=${encodeURIComponent(q.value.trim())}`, (p) => h('article', { class: 'item', style: 'grid-template-columns:auto 1fr auto' },
        h('div', { class: 'avatar avatar-sm' }, initials(`${p.first_name} ${p.last_name}`)),
        h('div', {}, h('div', { class: 'title' }, `${p.first_name} ${p.last_name}`), h('div', { class: 'small muted' }, [p.phone, p.email].filter(Boolean).join(' | ') || 'No contact details')),
        h('div', { class: 'actions' }, h('a', { class: 'btn btn-primary btn-sm', href: `book.html?patient=${p.id}` }, 'Book'), btn('Visits', 'secondary', () => historyModal(p.id, `${p.first_name} ${p.last_name}`)))),
      empty('No patients found', 'Try a different search, or register a new patient.'));
      q.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(load, 250); });
      panel.append(h('div', { class: 'toolbar' }, h('div', { class: 'field' }, h('label', { for: 'pq' }, 'Search patients'), q)), list); load();
    }

    function invoices(panel) {
      const list = h('div'); const sel = h('select', { class: 'input', id: 'inv-status', style: 'width:auto' },
        [['', 'All invoices'], ['pending', 'Unpaid'], ['partially_paid', 'Part paid'], ['paid', 'Paid']].map(([v, l]) => h('option', { value: v }, l)));
      const load = () => loadList(list, `/invoices/${sel.value ? `?status=${sel.value}` : ''}`, (i) => invoiceItem(i, { who: 'staff', canPay: true, done: () => { load(); loadStats(); } }), empty('No invoices', 'Invoices appear here when appointments are booked.'));
      sel.addEventListener('change', load);
      panel.append(h('div', { class: 'toolbar' }, h('div', { class: 'field' }, h('label', { for: 'inv-status' }, 'Show'), sel)), list); load();
    }
    var tabsApi = tabs(tabsBox, [{ id: 'schedule', label: 'Schedule', render: schedule }, { id: 'patients', label: 'Patients', render: patients }, { id: 'invoices', label: 'Invoices', render: invoices }]);
  }

  /* ============================================================== DOCTOR */
  async function doctorView() {
    root.append(head(null));
    const statsBox = h('div'); const tabsBox = h('div'); root.append(statsBox, tabsBox);
    async function loadStats() {
      try { const d = await api('/dashboard/'); clear(statsBox).append(h('div', { class: 'stats' }, stat(d.today_total, "Today's patients"), stat((d.today_by_status || {}).completed || 0, 'Completed today'), stat(d.patients_seen_total, 'Patients treated in total'))); }
      catch (e) { clear(statsBox).append(errorBox(e)); }
    }
    loadStats();
    const state = { date: todayYMD() };

    function today(panel) {
      const list = h('div'); const date = h('input', { class: 'input', type: 'date', id: 'd-date', value: state.date, style: 'width:auto' });
      const load = () => {
        state.date = date.value || todayYMD(); const refresh = () => { load(); loadStats(); };
        loadList(list, `/appointments/?date=${state.date}`, (a) => apptItem(a, { who: 'patient', wide: true, billing: false, actions: [
          ['confirmed', 'checked_in'].includes(a.status) ? btn('Start visit', 'primary', () => act(`/appointments/${a.id}/start/`, {}, refresh, 'Visit started'), 'pulse') : null,
          ['checked_in', 'in_progress', 'completed'].includes(a.status) ? btn('Notes', 'secondary', () => notesModal(a, refresh), 'file') : null,
          ['in_progress', 'checked_in'].includes(a.status) ? btn('Complete', 'primary', () => act(`/appointments/${a.id}/complete/`, {}, refresh, 'Visit completed'), 'check') : null,
          btn('Patient history', 'ghost', () => historyModal(a.patient.id, a.patient.name)),
          ['confirmed', 'checked_in'].includes(a.status) ? btn('No show', 'ghost', () => act(`/appointments/${a.id}/no-show/`, {}, refresh, 'Marked as no show')) : null,
        ] }), empty('No patients scheduled', `Nothing booked for ${fmtDate(`${state.date}T12:00:00+05:30`)}.`));
      };
      panel.append(h('div', { class: 'toolbar' }, h('div', { class: 'field' }, h('label', { for: 'd-date' }, 'Date'), date),
        h('button', { class: 'btn btn-ghost btn-sm', type: 'button', onclick: () => { date.value = addDays(date.value || todayYMD(), -1); load(); } }, 'Previous day'),
        h('button', { class: 'btn btn-ghost btn-sm', type: 'button', onclick: () => { date.value = todayYMD(); load(); } }, 'Today'),
        h('button', { class: 'btn btn-ghost btn-sm', type: 'button', onclick: () => { date.value = addDays(date.value || todayYMD(), 1); load(); } }, 'Next day')), list);
      date.addEventListener('change', load); load();
    }
    function mine(panel) {
      const list = h('div'); let timer;
      const q = h('input', { class: 'input', id: 'dq', type: 'search', placeholder: 'Search your patients', 'aria-label': 'Search your patients', style: 'max-width:420px' });
      const load = () => loadList(list, `/patients/?q=${encodeURIComponent(q.value.trim())}`, (p) => h('article', { class: 'item', style: 'grid-template-columns:auto 1fr auto' },
        h('div', { class: 'avatar avatar-sm' }, initials(`${p.first_name} ${p.last_name}`)),
        h('div', {}, h('div', { class: 'title' }, `${p.first_name} ${p.last_name}`), h('div', { class: 'small muted' }, [p.phone, p.email].filter(Boolean).join(' | '))),
        h('div', { class: 'actions' }, btn('History and notes', 'secondary', () => historyModal(p.id, `${p.first_name} ${p.last_name}`)))), empty('No patients yet', 'Patients who book with you will appear here.'));
      q.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(load, 250); });
      panel.append(h('div', { class: 'toolbar' }, h('div', { class: 'field' }, h('label', { for: 'dq' }, 'Search'), q)), list); load();
    }
    tabs(tabsBox, [{ id: 'today', label: 'Appointments', render: today }, { id: 'patients', label: 'My patients', render: mine }]);
  }

  if (role === 'patient') patientView();
  else if (role === 'doctor') doctorView();
  else staffView();
})();