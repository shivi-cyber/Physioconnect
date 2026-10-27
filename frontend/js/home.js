(function () {
  'use strict';
  const { h, $, $$, icon, api, money, initials, dateParts, fmtTime, todayYMD, addDays, renderChrome, clear } = PC;

  renderChrome(null);
  $$('[data-icon]').forEach((n) => n.replaceWith(icon(n.dataset.icon, 18)));

  const unavailable = (box, what) => clear(box).append(h('p', { class: 'muted' }, `${what} could not be loaded. Please make sure the backend is running, then refresh.`));

  /** First date in the next 14 days that has a free slot for this doctor. */
  async function nextSlot(doctor) {
    const service = doctor.services[0];
    if (!service) return null;
    const today = todayYMD();
    const dates = Array.from({ length: 14 }, (_, i) => addDays(today, i));
    const all = await Promise.all(dates.map((d) =>
      api(`/doctors/${doctor.id}/available-slots/?date=${d}&service_id=${service.id}`, { auth: false }).then((r) => r.slots).catch(() => [])));
    const i = all.findIndex((s) => s.length);
    return i < 0 ? null : { date: dates[i], start: all[i][0].start, service };
  }

  async function load() {
    const servicesBox = $('#services-grid'); const doctorsBox = $('#doctors-grid');
    servicesBox.append(PC.skeleton(3)); doctorsBox.append(PC.skeleton(2));
    let services = []; let doctors = [];
    try {
      [services, doctors] = await Promise.all([api('/services/', { auth: false }), api('/doctors/', { auth: false })]);
    } catch (e) {
      unavailable(servicesBox, 'Services'); unavailable(doctorsBox, 'Doctors'); unavailable($('#next-list'), 'Availability');
      return;
    }

    // Trust row: real facts from the data, nothing invented
    const cheapest = services.length ? Math.min(...services.map((s) => Number(s.price))) : null;
    const facts = [
      doctors.length ? [`${doctors.length} qualified physiotherapist${doctors.length > 1 ? 's' : ''}`, 'badge'] : null,
      cheapest !== null ? [`Sessions from ${money(cheapest)}`, 'file'] : null,
      ['Live availability, no phone calls', 'calendar'],
    ].filter(Boolean);
    $('#trust-row').append(...facts.map(([t, i]) => h('span', { class: 'trust-item' }, icon(i, 20), t)));

    // Services
    clear(servicesBox);
    servicesBox.append(...services.map((s) => h('article', { class: 'card card-hover' },
      h('h3', {}, s.name),
      h('div', { class: 'meta' }, h('span', {}, icon('clock', 16), `${s.duration_minutes} minutes`), s.category ? h('span', {}, s.category) : null),
      h('p', { class: 'muted' }, s.description),
      h('div', { class: 'row-between' }, h('span', { class: 'price' }, money(s.price)),
        h('a', { class: 'btn btn-secondary btn-sm', href: `book.html?service=${s.id}`, 'aria-label': `Book ${s.name}` }, 'Book')))));

    // Doctors
    clear(doctorsBox);
    doctorsBox.append(...doctors.map((d) => h('article', { class: 'card card-hover' },
      h('div', { class: 'doctor-head' }, h('div', { class: 'avatar' }, initials(d.name)),
        h('div', {}, h('h3', {}, d.name), h('div', { class: 'muted small' }, d.specializations.join(', ')))),
      h('div', { class: 'meta' }, d.qualifications ? h('span', {}, icon('badge', 16), d.qualifications) : null,
        d.years_experience ? h('span', {}, `${d.years_experience} years' experience`) : null),
      h('p', {}, d.bio),
      h('div', { class: 'row' }, h('a', { class: 'btn btn-primary btn-sm', href: `book.html?doctor=${d.slug}` }, `Book with ${d.first_name}`)))));

    // Next available times (hero card)
    const next = await Promise.all(doctors.map(async (d) => ({ d, n: await nextSlot(d) })));
    const list = $('#next-list'); clear(list);
    list.classList.remove('muted');
    const rows = next.filter((x) => x.n);
    if (!rows.length) { list.append(h('p', { class: 'muted' }, 'No free times in the next two weeks. Please call the clinic.')); return; }
    rows.forEach(({ d, n }) => {
      const p = dateParts(n.date);
      list.append(h('div', { class: 'next-item' }, h('div', { class: 'avatar avatar-sm' }, initials(d.name)),
        h('div', { class: 'grow' }, h('div', { style: 'font-weight:700;color:var(--ink)' }, d.name),
          h('div', { class: 'small muted' }, `${p.dow} ${p.dom} ${p.mon}, ${fmtTime(n.start)}`)),
        h('a', { class: 'btn btn-secondary btn-sm', href: `book.html?doctor=${d.slug}&service=${n.service.id}`, 'aria-label': `Book ${d.name}` }, 'Book')));
    });

    // Contact details in footer, only if the clinic has filled them in
    try {
      const c = await api('/clinic/', { auth: false });
      const box = $('#footer-contact');
      if (c.address) box.append(h('p', {}, icon('pin', 16), ' ', c.address));
      if (c.phone) box.append(h('p', {}, icon('phone', 16), ' ', h('a', { href: `tel:${c.phone}` }, c.phone)));
      if (c.email) box.append(h('p', {}, icon('mail', 16), ' ', h('a', { href: `mailto:${c.email}` }, c.email)));
    } catch { /* optional */ }
  }
  load();
})();