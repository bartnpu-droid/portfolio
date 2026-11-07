/* TACET One page: smooth scrolling, header, colourways, the 3D product, the exploded ear cup,
 * the noise-cancelling demo and the waitlist form. */
import * as THREE from "three";
import { RoomEnvironment } from "../vendor/RoomEnvironment.js";
import { COLORWAYS, makeMaterials, setColorway, fadeColorway, headphones, earCup, studio } from "./headphones.js";

const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
document.documentElement.classList.add("js");

/* ---------- smooth scrolling + header ---------- */
let lenis = null;
if (window.Lenis && !reduced) {
  lenis = new window.Lenis({ lerp: 0.1, anchors: { offset: -72 } });
  const raf = (t) => { lenis.raf(t); requestAnimationFrame(raf); };
  requestAnimationFrame(raf);
}
const head = document.querySelector(".head");
const onScroll = () => head.classList.toggle("solid", scrollY > 24);
addEventListener("scroll", onScroll, { passive: true }); onScroll();

/* ---------- reveal blocks once as they come into view ---------- */
const revealIO = new IntersectionObserver((entries) => {
  for (const e of entries) if (e.isIntersecting) { e.target.classList.add("in"); revealIO.unobserve(e.target); }
}, { rootMargin: "0px 0px -12% 0px" });
document.querySelectorAll(".silence-grid > *, .layers-copy, .sec-head, .mat, .spec-list, .preorder-grid > *, .faq-grid > *")
  .forEach((el) => { el.dataset.reveal = ""; revealIO.observe(el); });

/* ---------- 3D: one renderer per canvas, drawing only while the canvas is on screen ---------- */
const materials = makeMaterials();
const picked = document.querySelector('input[name="color"]:checked');
setColorway(materials, COLORWAYS[picked ? picked.value : "bone"]);
function stage(canvas, { fov = 26 } = {}) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 1.75));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(fov, 1, 1, 400);
  studio(renderer, scene, RoomEnvironment);
  const s = { renderer, scene, camera, visible: false, frame: null };
  const resize = () => {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h; camera.updateProjectionMatrix();
    if (s.fit) s.fit();
  };
  new ResizeObserver(resize).observe(canvas); resize();
  let raf = 0;
  const loop = (now) => { raf = requestAnimationFrame(loop); if (s.frame) s.frame(now); renderer.render(scene, camera); };
  new IntersectionObserver(([en]) => {
    s.visible = en.isIntersecting;
    if (s.visible && !raf) raf = requestAnimationFrame(loop);
    if (!s.visible && raf) { cancelAnimationFrame(raf); raf = 0; }
  }, { rootMargin: "80px 0px" }).observe(canvas);
  return s;
}
/* distance so that a sphere of radius r fills `fill` of the smaller side of the view */
function fitDistance(camera, r, fill) {
  const vFov = THREE.MathUtils.degToRad(camera.fov);
  const hFov = 2 * Math.atan(Math.tan(vFov / 2) * camera.aspect);
  return r / Math.sin(Math.min(vFov, hFov) / 2) / fill;
}

let colorFade = null;
/* hero: the headphones turn into place, follow the cursor and sway when left alone */
const heroCanvas = document.querySelector('[data-scene="hero"]');
if (heroCanvas) {
  const s = stage(heroCanvas);
  const model = headphones(materials);
  const pivot = new THREE.Group(); pivot.add(model); s.scene.add(pivot);
  const radius = new THREE.Box3().setFromObject(model).getBoundingSphere(new THREE.Sphere()).radius;
  s.fit = () => { s.camera.position.set(0, 2.5, fitDistance(s.camera, radius, innerWidth < 900 ? 0.98 : 1.0)); s.camera.lookAt(0, -0.6, 0); };
  s.fit();
  const REST = -0.62;                                     // three-quarter view
  let yaw = reduced ? REST : REST - 2.4, pitch = 0.1, targetYaw = REST, targetPitch = 0.1, lastInput = 0;
  const t0 = performance.now();
  addEventListener("pointermove", (e) => {
    if (e.pointerType !== "mouse") return;
    targetYaw = REST + (e.clientX / innerWidth - 0.5) * 1.3;
    targetPitch = 0.1 + (e.clientY / innerHeight - 0.5) * 0.24;
    lastInput = performance.now();
  }, { passive: true });
  let dragX = null;
  heroCanvas.addEventListener("pointerdown", (e) => { dragX = e.clientX; heroCanvas.setPointerCapture(e.pointerId); });
  heroCanvas.addEventListener("pointermove", (e) => {
    if (dragX == null) return;
    targetYaw += (e.clientX - dragX) * 0.012; dragX = e.clientX; lastInput = performance.now();
  });
  for (const ev of ["pointerup", "pointercancel"]) heroCanvas.addEventListener(ev, () => { dragX = null; });
  s.frame = (now) => {
    if (colorFade && !colorFade(now)) colorFade = null;
    const idle = now - lastInput > 2500 && now - t0 > 1800;
    if (!reduced && idle) { targetYaw = REST + 0.42 * Math.sin((now - t0) / 2400); targetPitch = 0.1 + 0.05 * Math.sin((now - t0) / 3100); }
    const k = now - t0 < 1800 ? 0.035 : 0.06;
    yaw += (targetYaw - yaw) * k; pitch += (targetPitch - pitch) * k;
    pivot.rotation.set(pitch, yaw, 0);
    pivot.position.y = reduced ? 0 : Math.sin((now - t0) / 1700) * 0.25;   // a slow float
  };
}

/* exploded ear cup: the parts move apart as the section passes through the screen (no pinning) */
const explodeCanvas = document.querySelector('[data-scene="explode"]');
if (explodeCanvas) {
  const section = explodeCanvas.closest("[data-explode]");
  const s = stage(explodeCanvas, { fov: 24 });
  const cup = earCup(materials, true);
  const pivot = new THREE.Group(); pivot.add(cup); s.scene.add(pivot);
  const YAW = -1.02;
  pivot.rotation.set(0.24, YAW, 0.3);                     // the stack runs diagonally across the frame
  const tags = section.querySelector(".tags");
  const tagEls = [...tags.querySelectorAll("li")].map((el) => { el.dataset.n = el.textContent; el.textContent = ""; return [el.dataset.part, el]; });
  const ANCHOR = { cap: [3.13, 3.9], shell: [1.5, 5.0], driver: [0.2, 2.7], baffle: [0, 3.7], cushion: [-0.62, 4.6] };   // top of each part
  const spread = { cap: 6.8, shell: 0, driver: -5.2, baffle: -9.6, cushion: -14.0 };
  const base = new Map(cup.children.map((c) => [c, c.position.x]));
  s.fit = () => { s.camera.position.set(0, 0, fitDistance(s.camera, 13.5, innerWidth < 900 ? 0.98 : 0.94)); s.camera.lookAt(0, 0, 0); };
  s.fit();
  const ease = (x) => x * x * (3 - 2 * x);
  let shown = -1;
  s.frame = (now) => {
    if (colorFade && !colorFade(now)) colorFade = null;
    const r = explodeCanvas.getBoundingClientRect();                   // how far the picture itself has travelled through the screen
    const p = Math.max(0, Math.min(1, (innerHeight - r.top) / (innerHeight + r.height)));
    const a = ease(Math.max(0, Math.min(1, (p - 0.2) / 0.38)));          // apart while it moves from the bottom half to the centre
    if (Math.abs(a - shown) > 1e-4) {
      shown = a;
      for (const c of cup.children) c.position.x = base.get(c) + (spread[c.name] || 0) * a;
      cup.position.x = 3.6 * a;                                        // keep the stack centred while it grows
    }
    pivot.rotation.y = YAW + (reduced ? 0 : Math.sin(now / 3000) * 0.07);
    // number tags above each part, placed from the 3D positions
    tags.classList.toggle("on", a > 0.55);
    if (a > 0.3) {
      pivot.updateMatrixWorld();
      const w = explodeCanvas.clientWidth, h = explodeCanvas.clientHeight;
      for (const [name, el] of tagEls) {
        const v = new THREE.Vector3(base.get(cup.children.find((c) => c.name === name)) + (spread[name] || 0) * a + ANCHOR[name][0], ANCHOR[name][1], 0);
        cup.localToWorld(v).project(s.camera);
        el.style.transform = `translate(${((v.x + 1) / 2) * w}px, ${((1 - v.y) / 2) * h - 6}px) translate(-50%,-100%)`;
      }
    }
  };
}

/* ---------- colourways ---------- */
const nameEl = document.querySelector("[data-color-name]");
document.querySelectorAll('input[name="color"]').forEach((input) => input.addEventListener("change", () => {
  const cw = COLORWAYS[input.value];
  colorFade = fadeColorway(materials, cw);
  if (nameEl) nameEl.textContent = cw.name;
}));

/* ---------- noise-cancelling demo ---------- */
const waves = document.querySelector("[data-waves]");
if (waves) {
  const g = waves.getContext("2d");
  const MODES = { off: { amp: 1, db: 78, note: "a busy street" }, aware: { amp: 0.42, db: 52, note: "voices still come through" },
    silence: { amp: 0.05, db: 36, note: "like a quiet library" } };
  let mode = "silence", amp = MODES.silence.amp, db = MODES.silence.db, visible = false, raf = 0;
  const meter = document.querySelector("[data-meter]"), note = document.querySelector("[data-meter-note]");
  const buttons = document.querySelectorAll(".modes [data-mode]");
  const setMode = (m) => {
    mode = m;
    buttons.forEach((b) => b.setAttribute("aria-checked", String(b.dataset.mode === m)));
    note.textContent = MODES[m].note;
  };
  buttons.forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
  const size = () => { const d = Math.min(devicePixelRatio || 1, 2); waves.width = waves.clientWidth * d; waves.height = waves.clientHeight * d; };
  new ResizeObserver(size).observe(waves); size();
  const smooth = (e0, e1, x) => { const t = Math.max(0, Math.min(1, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t); };
  const draw = (now) => {
    raf = requestAnimationFrame(draw);
    const T = reduced ? 0 : now / 1000;
    amp += (MODES[mode].amp - amp) * 0.06;
    db += (MODES[mode].db - db) * 0.08;
    meter.textContent = `${Math.round(db)} dB`;
    const W = waves.width, H = waves.height, mid = H * 0.55;
    g.clearRect(0, 0, W, H);
    // divider: the ear cup between the outside world and your ear
    g.fillStyle = "rgba(255,255,255,0.06)"; g.fillRect(W * 0.5 - 1, H * 0.16, 2, H * 0.72);
    for (let k = 0; k < 7; k++) {                                  // noise: tangled grey lines
      g.beginPath();
      for (let x = 0; x <= W; x += 3) {
        const u = x / W, env = 1 + (amp - 1) * smooth(0.42, 0.58, u);
        const y = mid + env * H * 0.2 * (Math.sin(u * (9 + k * 3.1) + T * (1.4 + k * 0.37) + k) * 0.55 +
          Math.sin(u * (23 + k * 5) - T * (2.2 + k * 0.5)) * 0.3 + Math.sin(u * 61 + T * 5 + k * 2) * 0.15);
        x ? g.lineTo(x, y) : g.moveTo(x, y);
      }
      g.strokeStyle = `rgba(200,204,212,${0.1 + k * 0.025})`; g.lineWidth = 1.2 * (devicePixelRatio || 1); g.stroke();
    }
    g.beginPath();                                                  // your music: one clean ember line, untouched
    for (let x = W * 0.5; x <= W; x += 2) {
      const u = x / W;
      const y = mid + H * 0.12 * Math.sin(u * 14 - T * 2.4) * smooth(0.5, 0.62, u);
      x === W * 0.5 ? g.moveTo(x, y) : g.lineTo(x, y);
    }
    g.strokeStyle = "#ff6b3d"; g.lineWidth = 2.4 * (devicePixelRatio || 1); g.shadowColor = "rgba(255,107,61,.6)"; g.shadowBlur = 14;
    g.stroke(); g.shadowBlur = 0;
  };
  new IntersectionObserver(([en]) => {
    visible = en.isIntersecting;
    if (visible && !raf) raf = requestAnimationFrame(draw);
    if (!visible && raf) { cancelAnimationFrame(raf); raf = 0; }
  }).observe(waves);
}

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
