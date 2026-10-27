(function () {
  'use strict';
  const { h, $, clear, icon, api, money, initials, fmtDate, fmtTime, fmtDateTime, renderChrome, getUser, isLoggedIn, toast, busy, fieldErrors, store } = PC;
  renderChrome('book');

  const user = getUser();
  const role = isLoggedIn() ? user.role : null;
  const isStaff = role === 'receptionist' || role === 'admin';
  const params = new URLSearchParams(location.search);
  const DRAFT = 'pc_booking_draft';

  const state = { service: null, doctor: null, slot: null, patient: null, channel: 'phone' };
  let services = []; let doctors = []; let picker = null;

  /* ---------------- steps ---------------- */
  const steps = [...(isStaff ? [['patient', 'Patient']] : []), ['service', 'Service'], ['doctor', 'Doctor'], ['time', 'Time'], ['confirm', 'Confirm']];
  function currentStep() {
    if (isStaff && !state.patient) return 'patient';
    if (!state.service) return 'service';
    if (!state.doctor) return 'doctor';
    if (!state.slot) return 'time';
    return 'confirm';
  }
  function renderStepper() {
    const cur = currentStep(); const idx = steps.findIndex(([k]) => k === cur);
    clear($('#stepper')).append(...steps.map(([k, label], i) =>
      h('li', { class: i < idx ? 'done' : i === idx ? 'active' : '', 'aria-current': i === idx ? 'step' : null }, h('span', { class: 'n' }, i < idx ? icon('check', 14) : i + 1), label)));
  }

  /* ---------------- containers ---------------- */
  const flow = $('#flow');
  const secs = {};
  steps.forEach(([k]) => { secs[k] = h('section', { id: `sec-${k}`, 'aria-labelledby': `h-${k}` }); flow.append(secs[k]); });
  const title = (k, text, sub) => [h('h2', { id: `h-${k}`, style: 'font-size:1.4rem' }, text), sub ? h('p', { class: 'muted' }, sub) : null].filter(Boolean);

  /* ---------------- 0. patient (staff) ---------------- */
  function renderPatient() {
    if (!isStaff) return;
    const box = clear(secs.patient);
    box.append(...title('patient', 'Who is this booking for?'));
    if (state.patient) {
      box.append(h('div', { class: 'card card-flat row-between' },
        h('div', { class: 'row' }, h('div', { class: 'avatar avatar-sm' }, initials(state.patient.name)),
          h('div', {}, h('strong', {}, state.patient.name), h('div', { class: 'small muted' }, state.patient.phone || state.patient.email || ''))),
        h('div', { class: 'row' },
          h('label', { class: 'sr-only', for: 'channel' }, 'Booking channel'),
          h('select', { class: 'input', id: 'channel', style: 'width:auto', onchange: (e) => { state.channel = e.target.value; } },
            h('option', { value: 'phone', selected: state.channel === 'phone' }, 'Phone booking'), h('option', { value: 'walk_in', selected: state.channel === 'walk_in' }, 'Walk-in')),
          h('button', { class: 'btn btn-ghost btn-sm', type: 'button', onclick: () => { state.patient = null; refresh(); } }, 'Change'))));
      return;
    }
    const results = h('div', { class: 'list', style: 'margin-top:12px', 'aria-live': 'polite' });
    let timer;
    const search = h('input', { class: 'input', type: 'search', placeholder: 'Search by name, phone or email', 'aria-label': 'Search patients' });
    async function run() {
      clear(results);
      try {
        const data = await api(`/patients/?q=${encodeURIComponent(search.value.trim())}`);
        if (!data.results.length) { results.append(h('p', { class: 'muted' }, 'No patients found. Register a new patient below.')); return; }
        data.results.slice(0, 8).forEach((p) => results.append(h('button', { type: 'button', class: 'choice', onclick: () => {
          state.patient = { id: p.id, name: `${p.first_name} ${p.last_name}`, phone: p.phone, email: p.email }; refresh();
        } }, h('span', { class: 'choice-title' }, `${p.first_name} ${p.last_name}`), h('div', { class: 'small muted' }, [p.phone, p.email].filter(Boolean).join(' | ')))));
      } catch (e) { results.append(PC.errorBox(e)); }
    }
    search.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(run, 250); });
    const newBtn = h('button', { class: 'btn btn-secondary btn-sm', type: 'button', onclick: () => PC.registerPatientModal((p) => { state.patient = { id: p.id, name: `${p.first_name} ${p.last_name}`, phone: p.phone, email: p.email }; refresh(); }) }, icon('plus', 16), 'Register new patient');
    box.append(h('div', { class: 'row' }, h('div', { style: 'flex:1;min-width:220px' }, search), newBtn), results);
    run();
  }
  /* ---------------- 1. service ---------------- */
  function servicesForDoctor(d) { return d ? d.services : services; }
  function renderService() {
    const box = clear(secs.service);
    if (isStaff && !state.patient) return;
    box.append(...title('service', 'What do you need?', state.doctor ? `Services offered by ${state.doctor.name}` : null));
    const grid = h('div', { class: 'grid grid-2' });
    servicesForDoctor(state.doctor).forEach((s) => {
      const full = services.find((x) => x.id === s.id) || s;
      grid.append(h('button', { type: 'button', class: 'choice', 'aria-pressed': String(state.service && state.service.id === s.id), onclick: () => {
        state.service = { id: s.id, name: s.name, duration_minutes: s.duration_minutes, description: full.description, price: full.price };
        if (state.doctor && !state.doctor.services.some((x) => x.id === s.id)) state.doctor = null;
        state.slot = null; refresh();
      } }, h('div', { class: 'row-between' }, h('span', { class: 'choice-title' }, s.name), h('span', { class: 'price', style: 'font-size:1.05rem;white-space:nowrap' }, money(s.price))),
        h('div', { class: 'small muted' }, `${s.duration_minutes} minutes`), h('div', { class: 'small', style: 'margin-top:6px' }, full.description || '')));
    });
    box.append(grid);
  }

  /* ---------------- 2. doctor ---------------- */
  function renderDoctor() {
    const box = clear(secs.doctor);
    if (!state.service) return;
    box.append(...title('doctor', 'Choose your doctor'));
    const list = doctors.filter((d) => d.services.some((s) => s.id === state.service.id));
    if (!list.length) { box.append(PC.empty('No doctors available', 'No doctor currently offers this service.')); return; }
    const grid = h('div', { class: 'grid grid-2' });
    list.forEach((d) => {
      const price = d.services.find((s) => s.id === state.service.id).price;
      grid.append(h('button', { type: 'button', class: 'choice', 'aria-pressed': String(state.doctor && state.doctor.id === d.id), onclick: () => {
        state.doctor = d; state.service = { ...state.service, price }; state.slot = null; refresh();
      } }, h('div', { class: 'doctor-head' }, h('div', { class: 'avatar avatar-sm' }, initials(d.name)),
        h('div', {}, h('span', { class: 'choice-title' }, d.name), h('div', { class: 'small muted' }, d.specializations.join(', ')))),
        h('div', { class: 'small muted' }, [d.qualifications, d.years_experience ? `${d.years_experience} years' experience` : ''].filter(Boolean).join(' | ')),
        h('div', { class: 'small', style: 'margin-top:6px' }, `${money(price)} per session`)));
    });
    box.append(grid);
  }

  /* ---------------- 3. time ---------------- */
  let pickerKey = '';
  function renderTime() {
    const box = secs.time;
    if (!state.doctor || !state.service) { clear(box); pickerKey = ''; return; }
    const key = `${state.doctor.id}:${state.service.id}`;
    if (key === pickerKey) return;          // keep the picker (and the chosen time) when nothing changed
    pickerKey = key;
    clear(box).append(...title('time', 'Pick a time', `${state.service.duration_minutes}-minute session with ${state.doctor.name}`));
    const holder = h('div'); box.append(holder);
    picker = PC.slotPicker(holder, { doctorId: state.doctor.id, serviceId: state.service.id, onSelect: (s) => { state.slot = s; renderStepper(); renderConfirm(); scrollToConfirm(); } });
  }
  function scrollToConfirm() { if (state.slot) secs.confirm.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }

  /* ---------------- 4. confirm ---------------- */
  function renderConfirm() {
    const box = clear(secs.confirm);
    if (!state.slot) return;
    const dd = (k, v) => [h('dt', {}, k), h('dd', {}, v)];
    box.append(...title('confirm', 'Review and confirm'));
    const summary = h('div', { class: 'card summary' }, h('dl', {},
      isStaff && state.patient ? dd('Patient', state.patient.name) : null,
      dd('Service', state.service.name), dd('Doctor', state.doctor.name),
      dd('Date', fmtDate(state.slot.start)), dd('Time', `${fmtTime(state.slot.start)} - ${fmtTime(state.slot.end)} IST`),
      dd('Duration', `${state.service.duration_minutes} minutes`)),
      h('dl', { class: 'total' }, ...dd('Fee', money(state.service.price))),
      h('p', { class: 'hint', style: 'margin:12px 0 0' }, 'You pay at the clinic after your visit.'));
    const err = h('div', { 'aria-live': 'polite' });
    const label = !isLoggedIn() ? 'Log in to confirm' : 'Confirm booking';
    const btn = h('button', { type: 'button', class: 'btn btn-primary btn-block', style: 'margin-top:16px', disabled: role === 'doctor' }, label);
    btn.addEventListener('click', () => confirm(btn, err));
    box.append(summary, err, btn);
    if (role === 'doctor') box.append(h('p', { class: 'form-error', style: 'margin-top:12px' }, 'Doctor accounts cannot book appointments. Please ask the front desk.'));
  }

  async function confirm(btn, errBox) {
    clear(errBox);
    if (!isLoggedIn()) {
      store.set(DRAFT, JSON.stringify({ service: state.service, doctorId: state.doctor.id, slot: state.slot }));
      location.href = `login.html?next=${encodeURIComponent('book.html?resume=1')}`;
      return;
    }
    await busy(btn, async () => {
      try {
        const body = { doctor: state.doctor.id, service: state.service.id, scheduled_start: state.slot.start };
        if (isStaff) { body.patient = state.patient.id; body.booking_channel = state.channel; }
        const appt = await api('/appointments/', { method: 'POST', body });
        store.del(DRAFT);
        showDone(appt);
      } catch (e) {
        errBox.append(PC.errorBox(e));
        if (e.code === 'SLOT_TAKEN' || e.code === 'INVALID_SLOT') { state.slot = null; pickerKey = ''; refresh(); toast('Please choose another time', 'bad'); }
      }
    });
  }

  function showDone(a) {
    $('#flow').classList.add('hidden'); $('#stepper').classList.add('hidden'); $('#page-title').classList.add('hidden'); $('#page-lead').classList.add('hidden');
    const done = $('#done'); done.classList.remove('hidden');
    const dd = (k, v) => [h('dt', {}, k), h('dd', {}, v)];
    clear(done).append(h('div', { class: 'card', style: 'max-width:640px' },
      h('div', { class: 'success-mark' }, icon('check', 32)),
      h('h2', {}, 'Your appointment is confirmed'),
      h('p', { class: 'muted' }, isStaff ? `Booked for ${a.patient.name}.` : 'We look forward to seeing you.'),
      h('div', { class: 'summary', style: 'margin:16px 0' }, h('dl', {},
        dd('Service', a.service.name), dd('Doctor', a.doctor.name), dd('When', fmtDateTime(a.scheduled_start)),
        a.invoice ? dd('Invoice', `${a.invoice.invoice_number} (${money(a.invoice.total)})`) : null)),
      h('div', { class: 'row' }, h('a', { class: 'btn btn-primary', href: 'dashboard.html' }, isStaff ? 'Go to dashboard' : 'View my appointments'),
        h('a', { class: 'btn btn-secondary', href: 'book.html' }, 'Book another'))));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  /* ---------------- plumbing ---------------- */
  function refresh() {
    renderStepper(); renderPatient();
    if (isStaff && !state.patient) { ['service', 'doctor', 'time', 'confirm'].forEach((k) => clear(secs[k])); pickerKey = ''; return; }
    renderService(); renderDoctor(); renderTime(); renderConfirm();
  }

  async function init() {
    flow.append(PC.skeleton(2));
    try {
      [services, doctors] = await Promise.all([api('/services/', { auth: false }), api('/doctors/', { auth: false })]);
    } catch (e) { clear(flow).append(PC.errorBox(e)); return; }
    clear(flow); steps.forEach(([k]) => flow.append(secs[k]));

    // Pre-selections from links such as book.html?doctor=dr-arjun-mehta&service=2
    const wantDoctor = params.get('doctor'); const wantService = Number(params.get('service'));
    if (wantDoctor) state.doctor = doctors.find((d) => d.slug === wantDoctor || d.id === wantDoctor) || null;
    if (wantService) {
      const s = services.find((x) => x.id === wantService);
      if (s && (!state.doctor || state.doctor.services.some((x) => x.id === s.id))) {
        const price = state.doctor ? state.doctor.services.find((x) => x.id === s.id).price : s.price;
        state.service = { id: s.id, name: s.name, duration_minutes: s.duration_minutes, description: s.description, price };
      }
    }
    // Resume after logging in
    if (params.get('resume')) {
      try {
        const d = JSON.parse(store.get(DRAFT) || 'null');
        const doc = d && doctors.find((x) => x.id === d.doctorId);
        if (d && doc) { state.doctor = doc; state.service = d.service; state.slot = d.slot; pickerKey = `${doc.id}:${d.service.id}`; }
      } catch { /* ignore */ }
    }
    if (isStaff && params.get('patient')) {
      try { const p = await api(`/patients/${params.get('patient')}/`); state.patient = { id: p.id, name: `${p.first_name} ${p.last_name}`, phone: p.phone, email: p.email }; } catch { /* choose manually */ }
    }
    if (role === 'doctor') $('#notice').append(h('div', { class: 'form-error' }, 'You are logged in as a doctor. Doctors cannot book appointments, but you can browse the booking steps.'));
    refresh();
    if (state.slot) {         // resumed: show the chosen time's picker in the background too
      pickerKey = '';
      const keep = state.slot; renderTime(); state.slot = keep; renderStepper(); renderConfirm();
    }
  }
  init();
})();