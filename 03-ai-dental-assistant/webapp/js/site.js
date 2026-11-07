/* Site behaviour: smooth scrolling, header, mobile menu, opening hours, booking form. */
(function () {
  "use strict";

  // ---------- smooth scrolling (Lenis); native scrolling for reduced motion and inside the chat
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let lenis = null;
  if (window.Lenis && !reduced) {
    const headH = () => (document.querySelector(".site-head") || { offsetHeight: 0 }).offsetHeight;
    lenis = new window.Lenis({
      lerp: 0.11,
      anchors: { offset: -(headH() + 16) },
      prevent: (node) => !!(node.closest && node.closest(".bs-chat")),
    });
    const raf = (t) => { lenis.raf(t); requestAnimationFrame(raf); };
    requestAnimationFrame(raf);
    window.lenis = lenis;
  }

  // ---------- header + mobile menu
  const head = document.querySelector(".site-head");
  const menu = document.querySelector(".menu-btn");
  if (head) {
    const onScroll = () => head.classList.toggle("scrolled", window.scrollY > 4);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }
  function setMenu(open) {
    head.classList.toggle("open", open);
    document.body.classList.toggle("menu-open", open);
    menu.setAttribute("aria-expanded", String(open));
    menu.setAttribute("aria-label", open ? "Close menu" : "Menu");
    if (lenis) open ? lenis.stop() : lenis.start();
  }
  if (head && menu) {
    menu.addEventListener("click", () => setMenu(!head.classList.contains("open")));
    head.querySelectorAll(".nav a").forEach((a) => a.addEventListener("click", () => setMenu(false)));
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && head.classList.contains("open")) { setMenu(false); menu.focus(); } });
  }

  // ---------- opening hours in London time
  const HOURS = { 0: null, 1: [8, 19], 2: [8, 19], 3: [8, 19], 4: [8, 19], 5: [8, 19], 6: [9, 15] };
  const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  function londonNow() {
    try {
      const parts = new Intl.DateTimeFormat("en-GB", {
        timeZone: "Europe/London", weekday: "long", hour: "numeric", minute: "numeric", hourCycle: "h23",
      }).formatToParts(new Date());
      const get = (type) => (parts.find((p) => p.type === type) || {}).value;
      return { day: DAYS.indexOf(get("weekday")), minutes: Number(get("hour")) * 60 + Number(get("minute")) };
    } catch (_) {
      const d = new Date();
      return { day: d.getDay(), minutes: d.getHours() * 60 + d.getMinutes() };
    }
  }
  function openState(now) {
    const today = HOURS[now.day];
    if (today && now.minutes >= today[0] * 60 && now.minutes < today[1] * 60) {
      return { open: true, text: `Open now until ${today[1]}:00` };
    }
    if (today && now.minutes < today[0] * 60) return { open: false, text: `Closed now. Opens today at ${today[0]}:00` };
    for (let i = 1; i <= 7; i++) {
      const d = (now.day + i) % 7;
      if (HOURS[d]) return { open: false, text: `Closed now. Opens ${i === 1 ? "tomorrow" : DAYS[d]} at ${HOURS[d][0]}:00` };
    }
    return { open: false, text: "" };
  }
  const now = londonNow();
  document.querySelectorAll(".hours dt[data-days]").forEach((dt) => {
    if (dt.dataset.days.split(" ").includes(String(now.day))) {
      dt.classList.add("today");
      if (dt.nextElementSibling) dt.nextElementSibling.classList.add("today");
    }
  });
  const state = openState(now);
  document.querySelectorAll("[data-open-now]").forEach((n) => {
    n.textContent = state.text;
    n.classList.toggle("is-open", state.open);
  });

  // ---------- booking form
  const form = document.getElementById("book-form");
  if (!form) return;
  const status = form.querySelector(".form-status");
  const button = form.querySelector('button[type="submit"]');
  const elapsed = form.querySelector('[name="elapsed"]');
  let shownAt = Date.now();
  const MESSAGES = {
    name: "Enter your name.",
    phone: "Enter a phone number we can call, for example 07911 123456.",
    email: "Enter a valid email address, or leave it empty.",
    treatment: "Choose what the visit is for.",
    consent: "Tick the box so we can contact you about this request.",
  };
  const params = new URLSearchParams(location.search);
  const wanted = (params.get("treatment") || "").toLowerCase();
  if (wanted) {
    const select = form.elements.treatment;
    for (const o of select.options) if (o.text.toLowerCase() === wanted) select.value = o.value || o.text;
  }
  function show(kind, text) {
    status.className = "form-status " + kind;
    status.textContent = text;
  }
  if (params.get("sent")) show("ok", "Request sent. Reception will call you to confirm, usually within 2 working hours.");
  if (params.get("error")) show("err", params.get("error"));

  function markInvalid(field) {
    form.querySelectorAll("[aria-invalid]").forEach((f) => f.removeAttribute("aria-invalid"));
    if (field && field.setAttribute) field.setAttribute("aria-invalid", "true");
  }
  form.addEventListener("input", (e) => { if (e.target.hasAttribute("aria-invalid")) e.target.removeAttribute("aria-invalid"); });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const phone = form.elements.phone;
    phone.setCustomValidity((phone.value.match(/\d/g) || []).length >= 7 || !phone.value ? "" : "bad");
    const bad = Array.from(form.elements).find((f) => f.willValidate && !f.checkValidity());
    if (bad) {
      markInvalid(bad);
      show("err", MESSAGES[bad.name] || "Check the highlighted field.");
      bad.focus();
      return;
    }
    markInvalid(null);
    elapsed.value = String(Date.now() - shownAt);   // time spent on the form: bots submit instantly
    const data = Object.fromEntries(new FormData(form).entries());
    button.disabled = true;
    button.textContent = "Sending…";
    try {
      const r = await fetch(form.action, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
      });
      const res = await r.json().catch(() => ({}));
      if (r.ok && res.ok) {
        form.reset();
        shownAt = Date.now();
        show("ok", res.message);
        status.focus();
      } else {
        const field = res.field ? form.elements[res.field] : null;
        markInvalid(field);
        show("err", res.error || "The request wasn't sent. Try again, or call 020 0000 0000.");
        if (field) field.focus();
      }
    } catch (_) {
      show("err", "No connection. Check your internet and try again, or call 020 0000 0000.");
    }
    button.disabled = false;
    button.textContent = "Send request";
  });
})();
