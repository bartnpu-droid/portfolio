/* TACET One, modelled in code: a light stand-in for the Blender model (a few hundred KB of geometry, no files).
 * Units are centimetres. The ear cup axis is X: the aluminium cap faces outwards (+X), the cushion faces the head (−X).
 */
import * as THREE from "three";

export const COLORWAYS = {
  obsidian: { name: "Obsidian", shell: 0x1c1d20, cap: 0x2e2f33, metal: 0x404146, cushion: 0x161618, band: 0x1a1b1e, pad: 0x111214, accent: 0xc07a4b },
  bone:     { name: "Bone",     shell: 0xe4ded3, cap: 0xd2c8b8, metal: 0xc6bcab, cushion: 0xd3ccbf, band: 0xdfd8cc, pad: 0xcbc3b5, accent: 0xb59f80 },
  moss:     { name: "Moss",     shell: 0x46513f, cap: 0x71776a, metal: 0x5f645b, cushion: 0x2e352d, band: 0x3c4639, pad: 0x293028, accent: 0xb39a69 },
};
const COLOR_KEYS = ["shell", "cap", "metal", "cushion", "band", "pad", "accent"];

/* ---------- small procedural textures ---------- */
function canvasTexture(size, draw, { repeat = 1, color = false } = {}) {
  const c = document.createElement("canvas");
  c.width = c.height = size;
  draw(c.getContext("2d"), size);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(repeat, repeat);
  if (color) t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}
const grain = () => canvasTexture(256, (g, s) => {           // leather grain for bump maps
  const img = g.createImageData(s, s);
  for (let i = 0; i < img.data.length; i += 4) {
    const v = 110 + Math.random() * 90;
    img.data[i] = img.data[i + 1] = img.data[i + 2] = v; img.data[i + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  g.filter = "blur(1px)"; g.drawImage(g.canvas, 0, 0);
}, { repeat: 5 });
const brushed = () => canvasTexture(512, (g, s) => {         // concentric machining rings for the caps
  g.fillStyle = "#808080"; g.fillRect(0, 0, s, s);
  for (let r = 2; r < s * 0.72; r += 1.5) {
    g.strokeStyle = `rgba(${Math.random() < 0.5 ? "255,255,255" : "0,0,0"},${0.04 + Math.random() * 0.08})`;
    g.beginPath(); g.arc(s / 2, s / 2, r, 0, Math.PI * 2); g.stroke();
  }
});
const mesh = () => canvasTexture(128, (g, s) => {            // acoustic fabric / perforated baffle
  g.fillStyle = "#0d0d0e"; g.fillRect(0, 0, s, s);
  g.fillStyle = "#1f2023";
  for (let y = 4; y < s; y += 8) for (let x = (y / 8) % 2 ? 4 : 8; x < s; x += 8) { g.beginPath(); g.arc(x, y, 2.2, 0, Math.PI * 2); g.fill(); }
}, { repeat: 6, color: true });

/* ---------- materials ---------- */
export function makeMaterials() {
  const g = grain(), rings = brushed();
  const m = {
    shell: new THREE.MeshPhysicalMaterial({ roughness: 0.46, clearcoat: 0.4, clearcoatRoughness: 0.35 }),
    cap: new THREE.MeshPhysicalMaterial({ metalness: 1, roughness: 0.34, roughnessMap: rings }),
    metal: new THREE.MeshPhysicalMaterial({ metalness: 1, roughness: 0.27 }),
    cushion: new THREE.MeshPhysicalMaterial({ roughness: 0.68, bumpMap: g, bumpScale: 0.5, sheen: 0.5, sheenRoughness: 0.7 }),
    band: new THREE.MeshPhysicalMaterial({ roughness: 0.55, bumpMap: g, bumpScale: 0.25, clearcoat: 0.15 }),
    pad: new THREE.MeshPhysicalMaterial({ roughness: 0.8, bumpMap: g, bumpScale: 0.45, sheen: 0.4 }),
    accent: new THREE.MeshPhysicalMaterial({ metalness: 1, roughness: 0.3 }),
    fabric: new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.95, map: mesh() }),
    dome: new THREE.MeshPhysicalMaterial({ color: 0xcfc3ad, metalness: 1, roughness: 0.18, clearcoat: 1 }),
    cone: new THREE.MeshStandardMaterial({ color: 0x1b1b1d, roughness: 0.6 }),
    rubber: new THREE.MeshStandardMaterial({ color: 0x101011, roughness: 0.85 }),
    steel: new THREE.MeshStandardMaterial({ color: 0x8c9096, metalness: 1, roughness: 0.32 }),
  };
  setColorway(m, COLORWAYS.obsidian);
  return m;
}
export function setColorway(m, cw) { for (const k of COLOR_KEYS) m[k].color.setHex(cw[k]); }
/* fade every colour from where it is now to the colourway over `ms`; returns a step function for the render loop */
export function fadeColorway(m, cw, ms = 700) {
  const from = Object.fromEntries(COLOR_KEYS.map((k) => [k, m[k].color.clone()]));
  const to = Object.fromEntries(COLOR_KEYS.map((k) => [k, new THREE.Color(cw[k])]));
  const t0 = performance.now();
  return (now) => {
    const t = Math.min(1, (now - t0) / ms), e = t * t * (3 - 2 * t);
    for (const k of COLOR_KEYS) m[k].color.copy(from[k]).lerp(to[k], e);
    return t < 1;
  };
}

/* ---------- geometry helpers ---------- */
const OVAL = [1, 1.12, 0.92];                                   // ear cups are taller than they are wide
const lathe = (pts, seg = 96) => new THREE.LatheGeometry(pts.map(([r, h]) => new THREE.Vector2(r, h)), seg);
function alongX(geo, oval = true) {                             // lathe axis Y -> ear cup axis X
  geo.rotateZ(-Math.PI / 2);
  if (oval) geo.scale(...OVAL);
  geo.computeVertexNormals();
  return geo;
}
const part = (geo, mat, name) => { const o = new THREE.Mesh(geo, mat); o.name = name; return o; };

/* one ear cup; `inside` adds the parts you only see in the exploded view */
export function earCup(m, inside = false) {
  const cup = new THREE.Group();
  const shell = alongX(lathe([[3.0, 0], [3.86, 0.05], [4.13, 0.3], [4.25, 0.9], [4.21, 1.75], [4.02, 2.45], [3.64, 2.83], [3.24, 2.96],
    [2.96, 2.96], [2.98, 2.8], [3.72, 2.4], [3.9, 1.75], [3.94, 0.95], [3.8, 0.3], [3.0, 0.16]]));
  cup.add(part(shell, m.shell, "shell"));
  const cap = alongX(lathe([[0, 2.96], [3.1, 2.96], [3.22, 3.02], [3.27, 3.14], [3.2, 3.27], [3.02, 3.31], [0, 3.31]]));
  cup.add(part(cap, m.cap, "cap"));
  const ring = new THREE.TorusGeometry(3.24, 0.045, 8, 128); ring.rotateY(Math.PI / 2); ring.scale(...OVAL); ring.translate(3.0, 0, 0);
  cup.add(part(ring, m.accent, "cap"));
  // cushion: a squashed torus with fabric inside the opening
  const cushion = new THREE.TorusGeometry(3.08, 0.86, 28, 128);
  cushion.rotateY(Math.PI / 2); cushion.scale(0.8, OVAL[1], OVAL[2]); cushion.translate(-0.62, 0, 0);
  const cushionGroup = new THREE.Group(); cushionGroup.name = "cushion";
  cushionGroup.add(part(cushion, m.cushion, "cushion"));
  const cloth = new THREE.CircleGeometry(2.6, 64); cloth.rotateY(-Math.PI / 2); cloth.scale(1, OVAL[1], OVAL[2]); cloth.translate(-0.5, 0, 0);
  cushionGroup.add(part(cloth, m.fabric, "cushion"));
  cup.add(cushionGroup);
  if (inside) {
    // 40 mm driver: dome + cone + surround, magnet behind it
    const driver = new THREE.Group(); driver.name = "driver";
    const dome = lathe([[0, 0.42], [0.45, 0.39], [0.82, 0.28], [0.95, 0.2]], 64); dome.rotateZ(Math.PI / 2);
    const cone = lathe([[0.95, 0.2], [1.25, 0.05], [1.62, -0.16], [1.82, -0.22]], 64); cone.rotateZ(Math.PI / 2);
    const surround = lathe([[1.82, -0.22], [1.9, -0.08], [2.0, -0.05], [2.08, -0.16], [2.12, -0.3]], 64); surround.rotateZ(Math.PI / 2);
    const basket = new THREE.TorusGeometry(2.16, 0.09, 10, 96); basket.rotateY(Math.PI / 2); basket.translate(0.3, 0, 0);
    const magnet = new THREE.CylinderGeometry(1.15, 1.15, 0.75, 48); magnet.rotateZ(Math.PI / 2); magnet.translate(0.75, 0, 0);
    for (const [g, mat] of [[dome, m.dome], [cone, m.cone], [surround, m.rubber], [basket, m.steel], [magnet, m.steel]]) {
      g.computeVertexNormals(); driver.add(part(g, mat, "driver"));
    }
    driver.position.x = 0.9;
    cup.add(driver);
    // baffle with four of the microphones
    const baffle = new THREE.Group(); baffle.name = "baffle";
    const plate = new THREE.CylinderGeometry(3.02, 3.02, 0.16, 96); plate.rotateZ(Math.PI / 2); plate.scale(1, OVAL[1], OVAL[2]);
    baffle.add(part(plate, m.fabric, "baffle"));
    for (let k = 0; k < 4; k++) {
      const a = Math.PI / 4 + k * Math.PI / 2;
      const mic = new THREE.CylinderGeometry(0.2, 0.2, 0.12, 20); mic.rotateZ(Math.PI / 2);
      mic.translate(-0.12, Math.sin(a) * 2.35 * OVAL[1], Math.cos(a) * 2.35 * OVAL[2]);
      baffle.add(part(mic, m.accent, "baffle"));
    }
    baffle.position.x = 0.2;
    cup.add(baffle);
  }
  return cup;
}

/* half-ellipse in the YZ plane (yokes) or XY plane (headband) */
class Arc extends THREE.Curve {
  constructor(fn, t0 = 0, t1 = Math.PI) { super(); this.fn = fn; this.t0 = t0; this.t1 = t1; }
  getPoint(u, target = new THREE.Vector3()) { return target.copy(this.fn(this.t0 + (this.t1 - this.t0) * u)); }
}
function roundedRect(w, h, r) {
  const s = new THREE.Shape(), x = -w / 2, y = -h / 2;
  s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r);
  s.lineTo(x + w, y + h - r); s.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r);
  s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
  return s;
}

/* the whole pair of headphones, centred at the origin */
export function headphones(m) {
  const root = new THREE.Group();
  const CX = 9.2, RY = 5.75, RZ = 4.55, YOKE_X = 1.45;           // cup centre, yoke radii, yoke position across the cup
  const BAND_Y = RY + 2.4, BAND_H = 8.6;                          // headband ends and height above them
  for (const side of [1, -1]) {
    const g = new THREE.Group();
    const cup = earCup(m); cup.position.x = CX; g.add(cup);
    const yoke = new THREE.TubeGeometry(new Arc((t) => new THREE.Vector3(CX + YOKE_X, RY * Math.sin(t), RZ * Math.cos(t))), 72, 0.22, 14);
    g.add(part(yoke, m.metal, "yoke"));
    for (const z of [RZ, -RZ]) {                                  // pivots where the yoke holds the cup
      const hub = new THREE.CylinderGeometry(0.46, 0.46, 0.95, 28); hub.rotateX(Math.PI / 2); hub.translate(CX + YOKE_X, 0, Math.sign(z) * (RZ - 0.3));
      g.add(part(hub, m.metal, "yoke"));
    }
    const rod = new THREE.CylinderGeometry(0.17, 0.17, BAND_Y - RY + 0.2, 16); rod.translate(CX + YOKE_X, (BAND_Y + RY) / 2, 0);
    g.add(part(rod, m.metal, "slider"));
    const block = new THREE.CylinderGeometry(0.42, 0.42, 1.1, 24); block.translate(CX + YOKE_X, BAND_Y + 0.25, 0);
    g.add(part(block, m.metal, "slider"));
    g.scale.x = side;                                             // the left side is a mirror image
    root.add(g);
  }
  // headband: a flat padded band following a half-ellipse over the head
  const bandX = CX + YOKE_X;
  const bandPath = new Arc((t) => new THREE.Vector3(bandX * Math.cos(t), BAND_Y + 0.8 + BAND_H * Math.sin(t), 0));
  // the shape's x runs across the head (front to back, Z) and its y is the thickness: the wide side rests on the head
  const band = new THREE.ExtrudeGeometry(roundedRect(3.3, 0.78, 0.36), { steps: 140, bevelEnabled: false, extrudePath: bandPath });
  root.add(part(band, m.band, "band"));
  const padPath = new Arc((t) => new THREE.Vector3((bandX - 0.62) * Math.cos(t), BAND_Y + 0.8 + (BAND_H - 0.62) * Math.sin(t), 0), 0.2 * Math.PI, 0.8 * Math.PI);
  const pad = new THREE.ExtrudeGeometry(roundedRect(2.7, 0.62, 0.3), { steps: 90, bevelEnabled: false, extrudePath: padPath });
  root.add(part(pad, m.pad, "pad"));
  // centre everything
  const box = new THREE.Box3().setFromObject(root), c = box.getCenter(new THREE.Vector3());
  root.children.forEach((ch) => ch.position.sub(c));
  return root;
}

/* lights + reflections shared by both scenes */
export function studio(renderer, scene, RoomEnvironment) {
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  const key = new THREE.DirectionalLight(0xfff3e6, 2.4); key.position.set(-14, 22, 18); scene.add(key);
  const rim = new THREE.DirectionalLight(0xdfe8ff, 2.2); rim.position.set(18, 10, -20); scene.add(rim);
  const fill = new THREE.DirectionalLight(0xffffff, 0.5); fill.position.set(0, -12, 20); scene.add(fill);
}
