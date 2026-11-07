/* TACET One product page: reveals, the highlights rail, the 360° look, the exploded ear cup, the noise-cancelling
 * demo, the battery counter and the waitlist form.
 * The product pictures are Blender renders: the 360° view and the exploded view are image sequences drawn on canvas.
 * Built to stay smooth on phones: native scrolling, canvases only as big as the picture they show, nothing redraws
 * unless it changed, and animations stop when they leave the screen. */
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
document.documentElement.classList.add("js");
const DPR = (max = 2) => Math.min(devicePixelRatio || 1, max);
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const pad = (i) => String(i).padStart(2, "0");

/* ---------- reveal blocks once as they come into view ---------- */
const revealIO = new IntersectionObserver((entries) => {
  for (const e of entries) if (e.isIntersecting) { e.target.classList.add("in"); revealIO.unobserve(e.target); }
}, { rootMargin: "0px 0px -10% 0px" });
document.querySelectorAll(".sec-title, .statement > *, .sound .center, .parts-row li, #silence .wrap > *, .battery .wrap > *, .tile, .spec-list, .buy-card")
  .forEach((el) => { el.dataset.reveal = ""; revealIO.observe(el); });

/* run `fn(now)` on every frame while `el` is on screen */
function whileVisible(el, fn, margin = "60px 0px") {
  let raf = 0;
  const loop = (now) => { raf = requestAnimationFrame(loop); fn(now); };
  new IntersectionObserver(([en]) => {
    if (en.isIntersecting && !raf) raf = requestAnimationFrame(loop);
    if (!en.isIntersecting && raf) { cancelAnimationFrame(raf); raf = 0; }
  }, { rootMargin: margin }).observe(el);
}
/* call `fn` once, when `el` gets within `margin` of the screen */
function whenNear(el, fn, margin = "100% 0px") {
  const io = new IntersectionObserver(([en]) => { if (en.isIntersecting) { io.disconnect(); fn(); } }, { rootMargin: margin });
  io.observe(el);
}

/* ---------- image sequences ----------
 * Frames arrive as small compressed files (coarse-to-fine: every 12th, 6th, 3rd, then all, so scrubbing works early)
 * and are decoded into bitmaps only around the frame on screen, ahead of time and off the main thread.
 * Nothing is decoded while it is being drawn, so turning and scrolling never wait, and memory stays small. */
class FrameStore {
  constructor(urlFor, n, wrap) {
    Object.assign(this, { urlFor, n, wrap, blobs: new Array(n), bitmaps: new Map(), decoding: new Set(), want: new Set(),
      centre: 0, loaded: 0, started: false, onready: null });
  }
  idx(i) { return this.wrap ? ((i % this.n) + this.n) % this.n : Math.max(0, Math.min(this.n - 1, i)); }
  dist(a, b) { const d = Math.abs(a - b); return this.wrap ? Math.min(d, this.n - d) : d; }
  get complete() { return this.loaded === this.n; }
  load(start = 0, parallel = 4) {
    if (this.started) return;
    this.started = true;
    const order = [], seen = new Set();
    for (const step of [12, 6, 3, 1]) for (let i = 0; i < this.n; i += step) {
      const k = this.wrap ? (start + i) % this.n : i;
      if (!seen.has(k)) { seen.add(k); order.push(k); }
    }
    const next = () => {
      const i = order.shift();
      if (i == null) return;
      fetch(this.urlFor(i)).then((r) => (r.ok ? r.blob() : null))
        .then((b) => { if (b) { this.blobs[i] = b; this.loaded++; this.decode(); } })
        .catch(() => {}).finally(next);
    };
    for (let k = 0; k < parallel; k++) next();
  }
  /* keep decoded the frames from centre - behind to centre + ahead (nearest first) and let the others go */
  keep(centre, behind, ahead) {
    const want = new Set();
    for (let d = -behind; d <= ahead; d++) want.add(this.idx(centre + d));
    this.want = want; this.centre = this.idx(centre);
    for (const [k, bm] of this.bitmaps) if (!want.has(k)) { bm.close(); this.bitmaps.delete(k); }
    this.decode();
  }
  decode(max = 3) {
    if (!this.want.size) return;
    const order = [...this.want].sort((a, b) => this.dist(a, this.centre) - this.dist(b, this.centre));
    for (const k of order) {
      if (this.decoding.size >= max) return;
      if (this.bitmaps.has(k) || this.decoding.has(k) || !this.blobs[k]) continue;
      this.decoding.add(k);
      createImageBitmap(this.blobs[k]).then((bm) => {
        this.decoding.delete(k);
        if (this.want.has(k)) { this.bitmaps.set(k, bm); if (this.onready) this.onready(k); } else bm.close();
        this.decode();
      }, () => this.decoding.delete(k));
    }
  }
  get(i) { return this.bitmaps.get(this.idx(i)) || null; }
  nearest(i) {
    i = this.idx(i);
    let best = null, bd = Infinity;
    for (const [k, bm] of this.bitmaps) { const d = this.dist(k, i); if (d < bd) { bd = d; best = bm; } }
    return best;
  }
  release() { for (const bm of this.bitmaps.values()) bm.close(); this.bitmaps.clear(); this.want = new Set(); }
}
/* where an iw x ih picture lands in a cw x ch box when it is contained and centred */
function contain(cw, ch, iw, ih) {
  const s = Math.min(cw / iw, ch / ih), w = iw * s, h = ih * s;
  return { x: (cw - w) / 2, y: (ch - h) / 2, w, h };
}
/* size a canvas to the picture's box inside its stage, never with more pixels than the frames have */
function placeCanvas(canvas, stage, iw, ih, framePx) {
  const b = contain(stage.clientWidth, stage.clientHeight, iw, ih);
  Object.assign(canvas.style, { left: `${b.x}px`, top: `${b.y}px`, width: `${b.w}px`, height: `${b.h}px` });
  const k = Math.min(DPR(), framePx / Math.max(b.w, 1));
  canvas.width = Math.max(1, Math.round(b.w * k));
  canvas.height = Math.max(1, Math.round(b.h * k));
  return b;
}

/* ---------- highlights rail ---------- */
const rail = document.querySelector(".rail");
if (rail) {
  const [prev, next] = document.querySelectorAll(".rail-nav button");
  const step = () => { const c = rail.querySelector(".card"); return c ? c.offsetWidth + 20 : rail.clientWidth * 0.8; };
  prev.addEventListener("click", () => rail.scrollBy({ left: -step(), behavior: reduced ? "auto" : "smooth" }));
  next.addEventListener("click", () => rail.scrollBy({ left: step(), behavior: reduced ? "auto" : "smooth" }));
  const update = () => {
    prev.disabled = rail.scrollLeft <= 2;
    next.disabled = rail.scrollLeft + rail.clientWidth >= rail.scrollWidth - 2;
  };
  rail.addEventListener("scroll", update, { passive: true });
  new ResizeObserver(update).observe(rail);
  update();
}

/* battery card: the ring fills once it is on screen */
const ring = document.querySelector(".card .ring");
if (ring) whenNear(ring, () => { ring.style.strokeDashoffset = String(754 * 0.1); }, "0px 0px -15% 0px");

/* battery chapter: count up to 40 */
const counter = document.querySelector("[data-count]");
if (counter) whenNear(counter, () => {
  const to = Number(counter.dataset.count), t0 = performance.now(), ms = reduced ? 0 : 1400;
  let shown = -1;
  const step = (now) => {
    const t = ms ? clamp((now - t0) / ms) : 1, v = Math.round(to * (1 - Math.pow(1 - t, 3)));
    if (v !== shown) { shown = v; counter.textContent = String(v); }
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}, "0px 0px -20% 0px");

/* ---------- 360° look: drag to turn (or use the arrow keys); colours swap in place ----------
 * Always one sharp rendered frame on screen (144 angles, 2.5° apart). It moves only when the visitor turns it:
 * no spinning on its own, no drifting after you let go. Frames are decoded around the current angle in advance. */
const lookCanvas = document.querySelector('[data-scene="look"]');
if (lookCanvas) {
  const N = 144, START = 36, g = lookCanvas.getContext("2d");    // starts on the three-quarter view with the logo
  const stage = lookCanvas.closest(".look-stage");
  const size = stage.clientHeight * DPR() > 820 ? 1200 : 640;
  const file = (c, i) => `img/look/${size}/${c}-${pad(i >> 1)}${i & 1 ? "h" : ""}.webp`;
  const stores = {};
  const store = (c) => stores[c] || (stores[c] = new FrameStore((i) => file(c, i), N, true));
  const nameEl = document.querySelector("[data-color-name]");
  const names = { bone: "Bone", obsidian: "Obsidian", moss: "Moss" };
  let colour = (document.querySelector('input[name="color"]:checked') || {}).value || "bone";
  let pos = START, dragX = null, dirty = true, fade = null, shownKey = "", centre = -1;
  new ResizeObserver(() => { placeCanvas(lookCanvas, stage, 1, 1, size); dirty = true; }).observe(stage);
  const draw = (now) => {
    const s = store(colour), i = s.idx(Math.round(pos));
    if (i !== centre) { centre = i; s.keep(i, 16, 16); }             // neighbours ready in both directions
    const bm = s.get(i) || s.nearest(i);
    const W = lookCanvas.width, H = lookCanvas.height;
    if (!bm) {                                                       // new colour not decoded yet: hold the old picture
      if (fade && dirty) { g.drawImage(fade.from, 0, 0, W, H); dirty = false; }
      return;
    }
    let a = 1;
    if (fade) { if (fade.t0 == null) fade.t0 = now; a = clamp((now - fade.t0) / 400); }
    const key = `${colour}|${i}|${bm === s.get(i)}`;
    if (key === shownKey && !fade && !dirty) return;                // nothing changed: no repaint
    shownKey = key; dirty = false;
    g.globalAlpha = 1;
    if (fade) { g.drawImage(fade.from, 0, 0, W, H); g.globalAlpha = a; }   // colour change: same angle, dissolve
    g.drawImage(bm, 0, 0, W, H);                                     // frames are opaque: no clearing needed
    g.globalAlpha = 1;
    if (fade && a >= 1) { if (fade.store !== s) fade.store.release(); fade = null; }
  };
  whenNear(stage, () => { store(colour).load(START); store(colour).keep(START, 16, 16); centre = START; });
  whileVisible(stage, draw);
  const perPixel = () => N / Math.max(stage.clientWidth * 0.75, 320);
  stage.addEventListener("pointerdown", (e) => {
    pos = Math.round(pos);
    dragX = e.clientX;
    stage.setPointerCapture(e.pointerId);
  });
  stage.addEventListener("pointermove", (e) => {
    if (dragX == null) return;
    pos += (e.clientX - dragX) * perPixel();
    dragX = e.clientX;
  });
  for (const ev of ["pointerup", "pointercancel", "lostpointercapture"]) stage.addEventListener(ev, () => {
    if (dragX != null) pos = Math.round(pos);                       // let go: stays on the frame under your hand
    dragX = null;
  });
  lookCanvas.tabIndex = 0;
  lookCanvas.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    pos = Math.round(pos) + (e.key === "ArrowRight" ? 2 : -2);
  });
  document.querySelectorAll('input[name="color"]').forEach((input) => input.addEventListener("change", () => {
    if (input.value === colour) return;
    const old = store(colour), i = old.idx(Math.round(pos)), from = old.get(i) || old.nearest(i);
    if (fade && fade.store !== old && fade.store !== store(input.value)) fade.store.release();
    colour = input.value;
    if (nameEl) nameEl.textContent = names[colour];
    store(colour).load(i);
    centre = -1;
    fade = from && !reduced ? { from, store: old, t0: null } : null;
    if (!fade && old !== store(colour)) old.release();
    dirty = true;
  }));
  // on big screens, fetch the other colours' files quietly once the first is in, so switching is instant;
  // phones load a colour when it is picked
  const saveData = navigator.connection && navigator.connection.saveData;
  if (matchMedia("(min-width: 900px)").matches && !saveData) {
    const others = () => {
      if (!store(colour).complete) return setTimeout(others, 1500);
      for (const c of Object.keys(names)) if (c !== colour) store(c).load(store(colour).idx(Math.round(pos)), 2);
    };
    whenNear(stage, () => setTimeout(others, 2500), "0px");
  }
}

/* ---------- exploded ear cup: follows the scroll (no pinning), redraws only when the frame changes ---------- */
const exCanvas = document.querySelector('[data-scene="explode"]');
if (exCanvas) {
  const N = 60, IW = 1920, IH = 1200, g = exCanvas.getContext("2d", { alpha: false });
  const stage = exCanvas.closest(".explode-stage");
  const tags = stage.querySelector(".tags");
  const tagEls = [...tags.querySelectorAll("li")].map((el) => { el.dataset.n = el.textContent; el.textContent = ""; return [el.dataset.part, el]; });
  const size = Math.min(stage.clientWidth, stage.clientHeight * IW / IH) * DPR() > 1000 ? 1600 : 960;
  let store = null, anchors = null, shownIm = null, box = null, pending = false, tagsOn = false, lastF = -1, lastI = -1;
  const update = () => {
    pending = false;
    if (!store || !box) return;
    const r = stage.getBoundingClientRect();
    if (r.bottom < -200 || r.top > innerHeight + 200) return;
    const p = clamp((innerHeight - r.top) / (innerHeight + r.height));   // how far the picture has travelled up the screen
    const a = clamp((p - 0.12) / 0.38);                                   // fully apart once it reaches the middle of the screen
    const f = a * (N - 1), i = Math.round(f);
    if (i !== lastI) { lastI = i; store.keep(i, 8, 8); }              // decoded around the frame on screen
    const im = store.get(i) || store.nearest(i);
    if (im && im !== shownIm) { shownIm = im; g.drawImage(im, 0, 0, exCanvas.width, exCanvas.height); }
    const on = a > 0.62 && !!anchors;
    if (on !== tagsOn) { tagsOn = on; tags.classList.toggle("on", on); }
    if (anchors && a > 0.4 && Math.abs(f - lastF) > 0.01) {
      lastF = f;
      const i0 = Math.floor(f), i1 = Math.min(N - 1, i0 + 1), t = f - i0;
      for (const [name, el] of tagEls) {
        const p0 = anchors[i0][name], p1 = anchors[i1][name];
        const x = box.x + (p0[0] + (p1[0] - p0[0]) * t) * box.w, y = box.y + (p0[1] + (p1[1] - p0[1]) * t) * box.h;
        el.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) translate(-50%, -100%)`;
      }
    }
  };
  const request = () => { if (!pending) { pending = true; requestAnimationFrame(update); } };
  new ResizeObserver(() => { box = placeCanvas(exCanvas, stage, IW, IH, size); shownIm = null; lastF = -1; request(); }).observe(stage);
  whenNear(stage, () => {
    store = new FrameStore((i) => `img/explode/${size}/${pad(i)}.webp`, N, false);
    store.onready = request;
    store.load(0);
    fetch("img/explode/anchors.json").then((r) => r.json()).then((d) => { anchors = d.anchors; request(); }).catch(() => {});
    addEventListener("scroll", request, { passive: true });
    request();
  });
}

/* ---------- noise-cancelling: the world's noise on the left, what reaches your ear on the right ---------- */
function waves(canvas, { theme, modes }) {
  const g = canvas.getContext("2d");
  const MODES = { off: { amp: 1, db: 78, note: "a busy street" }, aware: { amp: 0.42, db: 52, note: "voices still come through" },
    silence: { amp: 0.05, db: 36, note: "like a quiet library" } };
  let mode = "silence", amp = MODES.silence.amp, db = MODES.silence.db, shownDb = -1, lastDraw = 0;
  const meter = modes && document.querySelector("[data-meter]"), note = modes && document.querySelector("[data-meter-note]");
  if (modes) {
    const buttons = document.querySelectorAll(".modes [data-mode]");
    const set = (m) => { mode = m; buttons.forEach((b) => b.setAttribute("aria-checked", String(b.dataset.mode === m))); note.textContent = MODES[m].note; };
    buttons.forEach((b) => b.addEventListener("click", () => set(b.dataset.mode)));
  }
  const dark = theme === "dark";
  const ink = dark ? "200,204,212" : "60,60,67";
  const smooth = (e0, e1, x) => { const t = clamp((x - e0) / (e1 - e0)); return t * t * (3 - 2 * t); };
  let d = DPR(1.5);
  const fit = () => { d = DPR(1.5); canvas.width = Math.round(canvas.clientWidth * d); canvas.height = Math.round(canvas.clientHeight * d); };
  new ResizeObserver(fit).observe(canvas);
  whileVisible(canvas, (now) => {
    if (now - lastDraw < 15) return;                        // at most 60 frames a second, also on 120 Hz screens
    lastDraw = now;
    const T = reduced ? 0 : now / 1000;
    if (!modes && !reduced) mode = Math.sin(T * 0.6) > -0.2 ? "silence" : "off";   // the card shows it switching on and off
    amp += (MODES[mode].amp - amp) * 0.06;
    if (meter) {
      db += (MODES[mode].db - db) * 0.08;
      const v = Math.round(db);
      if (v !== shownDb) { shownDb = v; meter.textContent = `${v} dB`; }
    }
    const W = canvas.width, H = canvas.height, mid = H * (modes ? 0.56 : 0.52), A = H * (modes ? 0.2 : 0.16), step = 4 * d;
    g.clearRect(0, 0, W, H);
    g.fillStyle = `rgba(${ink},${dark ? 0.12 : 0.1})`;
    g.fillRect(W * 0.5 - d / 2, H * 0.18, d, H * 0.7);
    g.lineWidth = 1.2 * d;
    for (let k = 0; k < 7; k++) {
      g.beginPath();
      for (let x = 0; x <= W + step; x += step) {
        const u = x / W, env = 1 + (amp - 1) * smooth(0.42, 0.58, u);
        const y = mid + env * A * (Math.sin(u * (9 + k * 3.1) + T * (1.4 + k * 0.37) + k) * 0.55 +
          Math.sin(u * (23 + k * 5) - T * (2.2 + k * 0.5)) * 0.3 + Math.sin(u * 61 + T * 5 + k * 2) * 0.15);
        x ? g.lineTo(x, y) : g.moveTo(x, y);
      }
      g.strokeStyle = `rgba(${ink},${(dark ? 0.1 : 0.08) + k * 0.025})`;
      g.stroke();
    }
    g.beginPath();                                          // your music: one clean line, untouched
    for (let x = W * 0.5; x <= W + step; x += step * 0.75) {
      const u = x / W, y = mid + A * 0.6 * Math.sin(u * 14 - T * 2.4) * smooth(0.5, 0.62, u);
      x === W * 0.5 ? g.moveTo(x, y) : g.lineTo(x, y);
    }
    g.strokeStyle = "rgba(255,107,61,.16)"; g.lineWidth = 9 * d; g.stroke();   // soft glow, without canvas shadows
    g.strokeStyle = "#ff6b3d"; g.lineWidth = 2.4 * d; g.stroke();
  });
}
const cardWaves = document.querySelector('[data-waves="card"]');
if (cardWaves) waves(cardWaves, { theme: "dark", modes: false });
const mainWaves = document.querySelector('[data-waves="main"]');
if (mainWaves) waves(mainWaves, { theme: "light", modes: true });

/* ---------- waitlist (concept page: nothing is sent) ---------- */
const form = document.querySelector(".waitlist");
if (form) form.addEventListener("submit", (e) => {
  e.preventDefault();
  const input = form.elements.email, note = form.querySelector(".form-note");
  const ok = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(input.value.trim());
  input.setAttribute("aria-invalid", String(!ok));
  note.className = "form-note " + (ok ? "ok" : "err");
  note.textContent = ok ? "Thank you, you're on the list. (This is a concept page, so no email was sent.)" : "Please enter a valid email address.";
  if (ok) form.reset(); else input.focus();
});
