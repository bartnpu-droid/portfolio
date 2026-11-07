"use strict";

const tg = window.Telegram ? window.Telegram.WebApp : null;
const params = new URLSearchParams(location.search);
const DEV_USER = params.get("dev_user");          // browser preview only (server DEV_MODE=1)
const RESCHEDULE_ID = Number(params.get("reschedule")) || null;

const I18N = {
  en: {
    my: "My bookings", back: "Back", next: "Continue", confirm: "Confirm booking", book: "Book",
    step: "Step {n} of 4",
    s1: "Pick a service", s1h: "Prices include wash and styling.",
    s2: "Choose your barber", s2h: "Or let us pick whoever is free first.",
    any: "Any barber", anyT: "Most available times",
    s3: "Pick a time", s3h: "Times shown in shop time.",
    s4: "Check and confirm", s4h: "You can cancel or move it later in the bot.",
    morning: "Morning", afternoon: "Afternoon", evening: "Evening",
    noSlots: "This day is fully booked", noSlotsH: "Try another day or choose “Any barber”.",
    barber: "Barber", where: "Address", date: "Date", time: "Time", duration: "Duration", total: "Total", min: "min",
    reviews: "{n} reviews", newBarber: "New on the team",
    doneT: "You're booked", doneP: "We've sent the details to your chat and will remind you before the visit.",
    movedT: "Booking moved", toMy: "See my bookings", again: "Book another visit",
    myEmpty: "No upcoming visits", myEmptyH: "Your next haircut is a few taps away.",
    cancel: "Cancel", move: "Reschedule", cancelQ: "Cancel this booking?",
    cancelled: "Booking cancelled", taken: "That time was just taken — pick another one.",
    error: "Couldn't connect. Check your internet and try again.",
    openInTg: "Open this page from the bot in Telegram.",
    selected: "Selected", reschedTitle: "Move your booking",
    payNow: "Pay now", payLater: "At the shop", paidOnline: "Paid online", payBook: "Pay {amount} and book",
    payCancelled: "Payment cancelled — the time is released.", payFailed: "Payment didn't go through. Try again.",
    payUnavailable: "Online payment is unavailable right now. Please try later.",
    refundNote: "Free cancellation up to {h} h before the visit.",
  },
};
const WD = { en: ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"] };
const MO = { en: ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"] };

const state = {
  data: null, lang: "en", screen: "service",
  serviceId: null, masterId: null, date: null, time: null,
  slots: null, slotsKey: "", openDays: null, daysKey: "", daysKeyLoading: "", rescheduleId: RESCHEDULE_ID, result: null, busy: false,
};

const $ = (id) => document.getElementById(id);
const tr = (k, vars = {}) => (I18N[state.lang][k] || I18N.en[k] || k).replace(/\{(\w+)\}/g, (_, v) => vars[v]);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false)
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return node;
}

function haptic(type = "light") {
  try { tg && tg.HapticFeedback && (type === "ok" ? tg.HapticFeedback.notificationOccurred("success") : tg.HapticFeedback.impactOccurred(type)); } catch (_) {}
}

let toastTimer;
function toast(msg) {
  const t = $("toast"); t.textContent = msg; t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => (t.hidden = true), 3200);
}

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json" };
  if (tg && tg.initData) headers["X-Telegram-Init-Data"] = tg.initData;
  if (DEV_USER) headers["X-Dev-User"] = DEV_USER;
  const res = await fetch(path, { ...opts, headers });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) { const e = new Error(body.error || res.status); e.code = body.error; e.status = res.status; throw e; }
  return body;
}

/* ---------- helpers ---------- */
const svc = () => state.data.services.find((s) => s.id === state.serviceId);
const master = (id = state.masterId) => state.data.masters.find((m) => m.id === id);
const parseDay = (iso) => { const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d); };
const fmtDay = (iso) => { const d = parseDay(iso); return `${WD[state.lang][d.getDay()]}, ${d.getDate()} ${MO[state.lang][d.getMonth()]}`; };
const pyWeekday = (iso) => (parseDay(iso).getDay() + 6) % 7; // Monday = 0, like the server

function dayOpen(iso) {
  if (state.openDays && state.daysKey === `${state.serviceId}|${state.masterId}`) return state.openDays.includes(iso);
  const list = state.masterId ? [master()] : state.data.masters;
  return list.some((m) => m && m.work_days.includes(String(pyWeekday(iso))) && !m.days_off.includes(iso));
}

function setProgress() {
  const map = { service: 1, master: 2, time: 3, confirm: 4, done: 5, mine: 0 };
  $("poleFill").style.width = `${(map[state.screen] / 5) * 100}%`;
}

function go(screen) {
  state.screen = screen;
  render();
  window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
}

const BACK = { master: "service", time: "master", confirm: "time", mine: "service" };

function syncTelegramBack() {
  if (!tg || !tg.BackButton) return;
  if (BACK[state.screen] && !(state.rescheduleId && state.screen === "time")) tg.BackButton.show();
  else tg.BackButton.hide();
}

/* ---------- screens ---------- */
function stepHead(n, title, hint) {
  return el("div", { class: "step-head" },
    n ? el("div", { class: "step-no" }, tr("step", { n })) : null,
    el("h1", { class: "step-title" }, title),
    hint ? el("p", { class: "step-hint" }, hint) : null);
}

function screenService() {
  const list = el("div", { class: "price-list", role: "list" },
    state.data.services.map((s) => el("button", {
      class: "svc", type: "button", role: "listitem", "aria-pressed": String(s.id === state.serviceId),
      onclick: () => { state.serviceId = s.id; state.time = null; haptic(); render(); },
    },
      el("span", { class: "svc-name" }, s.name),
      el("span", { class: "svc-price" }, s.price),
      el("span", { class: "svc-meta" }, `${s.duration} ${tr("min")} · ${s.desc || ""}`))));
  return [stepHead(1, tr("s1"), tr("s1h")), list];
}

function barberRow({ id, name, title, photo, rating, reviews }) {
  const pressed = state.masterId === id;
  return el("button", {
    class: "barber", type: "button", "aria-pressed": String(pressed),
    onclick: () => { state.masterId = id; state.time = null; haptic(); render(); },
  },
    photo ? el("img", { src: `static/${photo}`, alt: "" }) : el("span", { class: "any", "aria-hidden": "true" }, "✂"),
    el("span", {},
      el("div", { class: "barber-name" }, name),
      el("div", { class: "barber-title" }, title),
      id ? el("div", { class: "barber-rating" },
        rating ? [el("span", { class: "star" }, "★ "), `${rating} · ${tr("reviews", { n: reviews })}`] : tr("newBarber")) : null));
}

function screenMaster() {
  return [stepHead(2, tr("s2"), tr("s2h")),
    el("div", { class: "barbers" },
      barberRow({ id: 0, name: tr("any"), title: tr("anyT") }),
      state.data.masters.map(barberRow))];
}

async function loadSlots() {
  const key = `${state.serviceId}|${state.masterId}|${state.date}`;
  if (state.slotsKey === key) return;          // already loaded or loading
  state.slotsKey = key; state.slots = null;
  const q = new URLSearchParams({ service_id: state.serviceId, master_id: state.masterId, date: state.date });
  if (state.rescheduleId) q.set("reschedule_id", state.rescheduleId);
  try {
    const r = await api(`/api/slots?${q}`);
    if (state.slotsKey === key) { state.slots = r.slots; if (state.screen === "time") render(); }
  } catch (_) { if (state.slotsKey === key) state.slotsKey = ""; toast(tr("error")); }
}

async function loadDays() {
  const key = `${state.serviceId}|${state.masterId}`;
  if (state.daysKeyLoading === key) return;
  state.daysKeyLoading = key;
  const q = new URLSearchParams({ service_id: state.serviceId, master_id: state.masterId });
  if (state.rescheduleId) q.set("reschedule_id", state.rescheduleId);
  try {
    const r = await api(`/api/days?${q}`);
    if (state.daysKeyLoading !== key) return;
    state.openDays = r.open; state.daysKey = key;
    if (state.screen === "time") render();
  } catch (_) { state.daysKeyLoading = ""; }
}

function screenTime() {
  if (state.daysKey !== `${state.serviceId}|${state.masterId}`) queueMicrotask(loadDays);
  if (!state.date || !dayOpen(state.date)) {
    state.date = state.data.days.find(dayOpen) || state.data.days[0];
    state.time = null;
  }
  const days = el("div", { class: "days", role: "listbox", "aria-label": tr("date") },
    state.data.days.map((iso) => {
      const d = parseDay(iso);
      return el("button", {
        class: "day", type: "button", "aria-pressed": String(iso === state.date), disabled: !dayOpen(iso),
        onclick: () => { state.date = iso; state.time = null; haptic(); render(); },
      },
        el("div", { class: "day-wd" }, WD[state.lang][d.getDay()]),
        el("div", { class: "day-num" }, d.getDate()),
        el("div", { class: "day-mo" }, MO[state.lang][d.getMonth()]));
    }));

  const out = [stepHead(state.rescheduleId ? 0 : 3, state.rescheduleId ? tr("reschedTitle") : tr("s3"), tr("s3h")), days];
  const key = `${state.serviceId}|${state.masterId}|${state.date}`;
  if (state.slotsKey !== key) queueMicrotask(loadSlots);
  if (state.slotsKey !== key || !state.slots) {
    out.push(el("div", {}, el("div", { class: "skeleton" }), el("div", { class: "skeleton" })));
    return out;
  }
  if (!state.slots.length) {
    out.push(el("div", { class: "empty" }, el("strong", {}, tr("noSlots")), tr("noSlotsH")));
    return out;
  }
  const groups = { morning: [], afternoon: [], evening: [] };
  for (const s of state.slots) {
    const h = Number(s.slice(0, 2));
    groups[h < 12 ? "morning" : h < 17 ? "afternoon" : "evening"].push(s);
  }
  for (const [g, list] of Object.entries(groups)) {
    if (!list.length) continue;
    out.push(el("section", { class: "slot-group" },
      el("h3", {}, tr(g)),
      el("div", { class: "slots" }, list.map((s) => el("button", {
        class: "slot", type: "button", "aria-pressed": String(s === state.time),
        onclick: () => { state.time = s; haptic(); render(); },
      }, s)))));
  }
  return out;
}

function ticket(b) {
  return el("div", { class: "ticket" },
    el("div", { class: "ticket-top" },
      el("div", { class: "ticket-service" }, b.service),
      el("div", { class: "ticket-when" }, `${fmtDay(b.date)} · ${b.time}`)),
    el("div", { class: "ticket-perf", "aria-hidden": "true" }),
    el("div", { class: "ticket-rows" },
      el("div", { class: "row" }, el("span", {}, tr("barber")), el("span", {}, b.master)),
      el("div", { class: "row" }, el("span", {}, tr("duration")), el("span", {}, `${b.duration} ${tr("min")}`)),
      el("div", { class: "row" }, el("span", {}, tr("where")), el("span", {}, state.data.shop.address)),
      el("div", { class: "row total" }, el("span", {}, tr("total")), el("span", {}, b.price)),
      b.payNow ? el("div", { class: "row pay" }, el("span", {}, tr("payNow")), el("span", {}, b.payNow)) : null,
      b.payLater ? el("div", { class: "row" }, el("span", {}, tr("payLater")), el("span", {}, b.payLater)) : null,
      b.paid ? el("div", { class: "row pay" }, el("span", {}, tr("paidOnline")), el("span", {}, b.paid)) : null));
}

const paying = () => Boolean(svc() && svc().pay_now && !state.rescheduleId);

function screenConfirm() {
  const s = svc();
  return [stepHead(4, tr("s4"), tr("s4h")),
    ticket({ service: s.name, date: state.date, time: state.time, duration: s.duration, price: s.price,
             master: state.masterId ? master().name : tr("any"),
             payNow: paying() ? s.pay_now : null, payLater: paying() ? s.pay_later : null }),
    paying() ? el("p", { class: "note" }, tr("refundNote", { h: state.data.payment.free_cancel_hours })) : null];
}

function screenDone() {
  const b = state.result;
  return [el("div", { class: "done" },
    el("div", { class: "done-mark", "aria-hidden": "true" }, "✓"),
    el("h2", {}, b.moved ? tr("movedT") : tr("doneT")),
    el("p", {}, tr("doneP")),
    ticket(b))];
}

function screenMine() {
  const list = state.data.upcoming;
  const out = [stepHead(0, tr("my"))];
  if (!list.length) {
    out.push(el("div", { class: "empty" }, el("strong", {}, tr("myEmpty")), tr("myEmptyH")));
    return out;
  }
  out.push(el("div", { class: "mine" }, list.map((b) => {
    const t = ticket(b);
    t.append(el("div", { class: "mine-actions" },
      el("button", { type: "button", onclick: () => startReschedule(b) }, tr("move")),
      el("button", { type: "button", class: "warn", onclick: () => cancel(b) }, tr("cancel"))));
    return t;
  })));
  return out;
}

/* ---------- actions ---------- */
function startReschedule(b) {
  state.rescheduleId = b.id; state.serviceId = b.service_id; state.masterId = b.master_id;
  state.date = b.date; state.time = null; state.slots = null; state.slotsKey = "";
  state.daysKey = ""; state.daysKeyLoading = "";
  go("time");
}

async function cancel(b) {
  const ok = await new Promise((resolve) => {
    if (tg && tg.showConfirm && tg.initData) tg.showConfirm(tr("cancelQ"), resolve);
    else resolve(window.confirm(tr("cancelQ")));
  });
  if (!ok) return;
  try {
    await api("/api/cancel", { method: "POST", body: JSON.stringify({ booking_id: b.id }) });
    state.data.upcoming = state.data.upcoming.filter((x) => x.id !== b.id);
    state.daysKey = ""; state.daysKeyLoading = ""; state.slotsKey = "";
    haptic("ok"); toast(tr("cancelled")); render();
  } catch (_) { toast(tr("error")); }
}

function openInvoice(url) {
  return new Promise((resolve) => {
    if (!(tg && tg.openInvoice)) return resolve("failed");
    tg.openInvoice(url, (status) => resolve(status)); // paid | cancelled | failed | pending
  });
}

async function submit() {
  if (state.busy) return;
  state.busy = true; render();
  try {
    const r = await api("/api/book", { method: "POST", body: JSON.stringify({
      service_id: state.serviceId, master_id: state.masterId, date: state.date, time: state.time,
      reschedule_id: state.rescheduleId,
    }) });
    const moved = Boolean(state.rescheduleId);
    if (r.invoice_url) {
      const status = await openInvoice(r.invoice_url);
      if (status !== "paid") {
        await api("/api/cancel", { method: "POST", body: JSON.stringify({ booking_id: r.booking.id }) }).catch(() => {});
        state.slotsKey = ""; state.daysKey = ""; state.daysKeyLoading = "";
        toast(status === "cancelled" ? tr("payCancelled") : tr("payFailed"));
        return;
      }
      r.booking.paid = svc().pay_now;
    }
    state.result = { ...r.booking, moved };
    state.data.upcoming = state.data.upcoming.filter((x) => x.id !== state.rescheduleId)
      .concat(r.booking).sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));
    state.rescheduleId = null; state.slots = null; state.slotsKey = ""; state.daysKey = ""; state.daysKeyLoading = "";
    haptic("ok"); go("done");
  } catch (e) {
    if (e.code === "payment_unavailable") toast(tr("payUnavailable"));
    else if (e.code === "slot_taken") { toast(tr("taken")); state.time = null; state.slots = null; state.slotsKey = ""; state.daysKey = ""; state.daysKeyLoading = ""; go("time"); }
    else toast(tr("error"));
  } finally { state.busy = false; render(); }
}

function resetFlow() {
  Object.assign(state, { serviceId: null, masterId: null, date: null, time: null, slots: null, slotsKey: "", result: null, rescheduleId: null });
  go("service");
}

/* ---------- bottom bar ---------- */
function renderBar() {
  const bar = $("bar"), btn = $("nextBtn"), sum = $("barSummary");
  sum.replaceChildren(); btn.classList.remove("wide");
  const s = state.serviceId && svc();
  let label = tr("next"), enabled = false, action = null, show = true;

  switch (state.screen) {
    case "service": enabled = Boolean(s); action = () => go("master"); break;
    case "master": enabled = state.masterId !== null; action = () => go("time"); break;
    case "time": enabled = Boolean(state.time); action = () => go("confirm"); break;
    case "confirm": label = paying() ? tr("payBook", { amount: svc().pay_now }) : tr("confirm"); enabled = !state.busy; action = submit; btn.classList.add("wide"); break;
    case "done": label = tr("again"); enabled = true; action = resetFlow; btn.classList.add("wide"); break;
    case "mine": label = tr("book"); enabled = true; action = resetFlow; btn.classList.add("wide"); break;
  }
  if (s && ["service", "master", "time"].includes(state.screen)) {
    const parts = [s.price, `${s.duration} ${tr("min")}`];
    if (state.screen !== "service" && state.masterId !== null) parts.push(state.masterId ? master().name : tr("any"));
    if (state.time) parts.push(`${fmtDay(state.date)}, ${state.time}`);
    sum.append(el("b", {}, s.name), parts.join(" · "));
  }
  sum.hidden = !sum.childNodes.length;
  bar.hidden = !show;
  btn.textContent = label; btn.disabled = !enabled; btn.onclick = enabled ? () => { haptic("medium"); action(); } : null;
}

function render() {
  const screens = { service: screenService, master: screenMaster, time: screenTime, confirm: screenConfirm, done: screenDone, mine: screenMine };
  $("view").replaceChildren(...[screens[state.screen]()].flat());
  $("myBtn").textContent = state.screen === "mine" ? tr("back") : tr("my");
  $("myBtn").onclick = () => (state.screen === "mine" ? go(state.serviceId ? "service" : "service") : go("mine"));
  setProgress(); renderBar(); syncTelegramBack();
}

/* ---------- start ---------- */
async function start() {
  if (tg) {
    tg.ready(); tg.expand();
    try { tg.setHeaderColor("#eef0ec"); tg.setBackgroundColor("#eef0ec"); } catch (_) {}
    tg.BackButton && tg.BackButton.onClick(() => { const b = BACK[state.screen]; if (b) go(b); });
  }
  if (!(tg && tg.initData) && !DEV_USER) {
    $("view").replaceChildren(el("div", { class: "empty" }, el("strong", {}, "Northside Barber Co."), I18N.en.openInTg));
    return;
  }
  $("view").replaceChildren(el("div", { class: "skeleton" }), el("div", { class: "skeleton" }), el("div", { class: "skeleton" }));
  try {
    state.data = await api("/api/bootstrap");
  } catch (_) {
    $("view").replaceChildren(el("div", { class: "empty" }, el("strong", {}, "Connection problem"), I18N.en.error));
    return;
  }
  state.lang = I18N[state.data.lang] ? state.data.lang : "en";
  document.documentElement.lang = state.lang;
  $("shopName").textContent = state.data.shop.name;
  $("shopSub").textContent = `${state.data.shop.address} · ${state.data.shop.open}–${state.data.shop.close}`;

  if (state.rescheduleId) {
    const b = state.data.upcoming.find((x) => x.id === state.rescheduleId);
    if (b) { startReschedule(b); return; }
    state.rescheduleId = null;
  }
  if (params.get("screen") === "mine") { go("mine"); return; }
  go("service");
}

start();
