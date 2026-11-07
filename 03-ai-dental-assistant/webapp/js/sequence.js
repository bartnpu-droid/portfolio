/* Plays a pre-rendered image sequence (photoreal frames rendered in Blender) on a canvas.
 * Hero: the implant turns with the cursor (or a finger) and sways gently when idle.
 * Story: frames follow the scroll position inside a tall section with a sticky stage.
 */
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

/* run fn once the page has finished loading and the browser is idle, so frames never compete with the page itself */
function whenIdle(fn) {
  const go = () => ("requestIdleCallback" in window ? requestIdleCallback(fn, { timeout: 800 }) : setTimeout(fn, 150));
  if (document.readyState === "complete") go(); else addEventListener("load", go, { once: true });
}

class Sequence {
  constructor(canvas, { folder, name, count, sizes = [600, 1200], aspect = 0.8 }) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.count = count;
    this.images = new Array(count);
    this.drawn = -1;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    // frames are drawn with "contain", so the width really used is also limited by the height (frames are 4:5)
    const needed = Math.min(canvas.clientWidth, canvas.clientHeight * aspect) * dpr;
    const size = sizes.find((s) => s >= needed * 0.9) || sizes[sizes.length - 1];
    this.url = (i) => `${folder}/${size}/${name}_${String(i).padStart(3, "0")}.webp`;
    new ResizeObserver(() => this.resize()).observe(canvas);
    this.resize();
  }

  /* first the frames needed right away, then every 4th, then the rest */
  load(first = 0, onFirst, onEnough) {
    const order = [first];
    for (let step of [8, 4, 2, 1]) for (let i = 0; i < this.count; i += step) if (!order.includes(i)) order.push(i);
    let started = 0, loaded = 0, enough = false;
    const next = () => {
      if (started >= order.length) return;
      const i = order[started++];
      const img = new Image();
      img.decoding = "async";
      img.src = this.url(i);
      img.decode().then(() => {
        this.images[i] = img;
        loaded++;
        if (i === first && onFirst) onFirst();
        if (!enough && loaded >= Math.ceil(this.count / 4)) { enough = true; if (onEnough) onEnough(); }
        if (this.pending != null) this.show(this.pending, true);
      }).catch(() => {}).finally(next);
    };
    for (let k = 0; k < 4; k++) next();          // 4 parallel downloads
  }

  resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.round(this.canvas.clientWidth * dpr), h = Math.round(this.canvas.clientHeight * dpr);
    if (w && h && (this.canvas.width !== w || this.canvas.height !== h)) {
      this.canvas.width = w;
      this.canvas.height = h;
      if (this.drawn >= 0) this.show(this.drawn, true);
    }
  }

  nearest(i) {
    for (let d = 0; d < this.count; d++) {
      if (this.images[i - d]) return i - d;
      if (this.images[i + d]) return i + d;
    }
    return -1;
  }

  show(index, force = false) {
    const i = Math.max(0, Math.min(this.count - 1, Math.round(index)));
    this.pending = i;
    const j = this.nearest(i);
    if (j < 0 || (j === this.drawn && !force)) return;
    const img = this.images[j];
    const { width: W, height: H } = this.canvas;
    const s = Math.min(W / img.naturalWidth, H / img.naturalHeight);
    const w = img.naturalWidth * s, h = img.naturalHeight * s;
    this.ctx.clearRect(0, 0, W, H);
    this.ctx.drawImage(img, (W - w) / 2, (H - h) / 2, w, h);
    this.drawn = j;
  }
}

/* Hero: turn with the cursor, drag on touch screens, idle sway, entrance spin */
function hero(stage) {
  const canvas = stage.querySelector("canvas");
  const count = Number(stage.dataset.frames);
  const seq = new Sequence(canvas, { folder: stage.dataset.folder, name: stage.dataset.name, count });
  const mid = (count - 1) / 2;
  let current = reduced ? mid : 0, target = current, lastInput = 0, visible = true, t0 = Infinity;
  whenIdle(() => seq.load(reduced ? Math.round(mid) : 0, () => {
    stage.classList.add("live");
    seq.show(current, true);
  }, () => {                                       // enough frames: turn into place, then follow the cursor
    t0 = performance.now();
    if (!lastInput) target = mid;
  }));
  window.addEventListener("pointermove", (e) => {
    if (e.pointerType !== "mouse") return;
    target = (e.clientX / innerWidth) * (count - 1);
    lastInput = performance.now();
  }, { passive: true });
  let dragX = null;
  canvas.addEventListener("pointerdown", (e) => { dragX = e.clientX; canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener("pointermove", (e) => {
    if (dragX == null) return;
    target = Math.max(0, Math.min(count - 1, target + (e.clientX - dragX) * 0.18));
    dragX = e.clientX;
    lastInput = performance.now();
  });
  const end = () => { dragX = null; };
  canvas.addEventListener("pointerup", end);
  canvas.addEventListener("pointercancel", end);
  let raf = 0;                                     // the loop only runs while the hero is on screen
  new IntersectionObserver(([en]) => {
    visible = en.isIntersecting;
    if (visible && !raf) raf = requestAnimationFrame(tick);
    if (!visible && raf) { cancelAnimationFrame(raf); raf = 0; }
  }).observe(stage);
  const tick = (now) => {
    raf = requestAnimationFrame(tick);
    if (!reduced && now - lastInput > 3000 && now - t0 > 2600 && t0 !== Infinity) {
      target = mid + mid * 0.62 * Math.sin((now - t0) / 2600);    // slow idle sway
    }
    current += (target - current) * (reduced ? 1 : now - t0 < 2600 ? 0.045 : 0.075);
    seq.show(current);
  };
}

/* Story: a tall section with a sticky stage; scroll position picks the frame and the caption */
function story(section) {
  const stage = section.querySelector("[data-sequence]");
  const canvas = stage.querySelector("canvas");
  const count = Number(stage.dataset.frames);
  const seq = new Sequence(canvas, { folder: stage.dataset.folder, name: stage.dataset.name, count });
  const captions = Array.from(section.querySelectorAll("[data-from]"));
  const pass = section.dataset.mode === "pass";
  // data-path="progress:amount,..." maps scroll progress to how far apart the model is (default: 0:0,1:1)
  const path = (section.dataset.path || "0:0,1:1").split(",").map((pair) => pair.split(":").map(Number));
  const amount = (p) => {
    for (let k = 1; k < path.length; k++) {
      const [p0, a0] = path[k - 1], [p1, a1] = path[k];
      if (p <= p1) return a0 + (a1 - a0) * ((p - p0) / Math.max(1e-6, p1 - p0));
    }
    return path[path.length - 1][1];
  };
  const bar = section.querySelector(".story-progress i");
  const io = new IntersectionObserver(([en]) => {     // start downloading when the section comes near
    if (!en.isIntersecting) return;
    io.disconnect();
    seq.load(0, () => { stage.classList.add("live"); seq.show(last < 0 ? 0 : last * (count - 1), true); });
  }, { rootMargin: "150% 0px" });
  io.observe(section);
  let last = -1, raf = 0;                          // the loop only runs while the section is near the screen
  new IntersectionObserver(([en]) => {
    if (en.isIntersecting && !raf) raf = requestAnimationFrame(tick);
    if (!en.isIntersecting && raf) { cancelAnimationFrame(raf); raf = 0; }
  }, { rootMargin: "60px 0px" }).observe(section);
  const tick = () => {
    raf = requestAnimationFrame(tick);
    const r = section.getBoundingClientRect();
    if (r.bottom < -50 || r.top > innerHeight + 50) return;
    const p = pass
      ? Math.max(0, Math.min(1, (innerHeight - r.top) / (innerHeight + r.height)))   // page scrolls normally
      : Math.max(0, Math.min(1, -r.top / Math.max(1, r.height - innerHeight)));       // pinned stage
    if (Math.abs(p - last) < 0.0005) return;
    last = p;
    seq.show(amount(p) * (count - 1));
    if (bar) bar.style.transform = `scaleY(${p})`;
    for (const c of captions) c.classList.toggle("on", p >= Number(c.dataset.from) && p < Number(c.dataset.to));
  };
}

document.querySelectorAll("[data-sequence='hero']").forEach(hero);
document.querySelectorAll("[data-story]").forEach(story);
