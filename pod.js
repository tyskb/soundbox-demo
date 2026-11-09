// Soundbox 4-person pod: detailed stylised 3D illustration (modelled in Blender, see blender/build_pod.py)
// built to the published size
// (outer W220 x D153.6 x H230 cm, inner W204 x D150 x H214 cm). Not a product scan.
// Two modes: scroll story (setStory) and free 360° explore (explore(true)) with orbit + zoom.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const stage = document.getElementById('stage');
const canvas = document.getElementById('pod');
const hotLayer = document.getElementById('hotspots');
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
const mobile = matchMedia('(pointer: coarse)').matches;

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio || 1, mobile ? 1.75 : 2));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(renderer), 0.04).texture;
scene.environmentIntensity = 0.55;

const camera = new THREE.PerspectiveCamera(28, 1, 0.05, 60);
const look = new THREE.Vector3(0, 1.1, 0);

const key = new THREE.DirectionalLight(0xffffff, 2.2);
key.position.set(3.5, 6.5, 5); key.castShadow = true;
key.shadow.mapSize.set(mobile ? 1024 : 2048, mobile ? 1024 : 2048);
Object.assign(key.shadow.camera, { left: -3, right: 3, top: 3.5, bottom: -1, near: 1, far: 16 });
key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02; key.shadow.radius = 4;
scene.add(key);
const rim = new THREE.DirectionalLight(0x8ea2ff, 2.4); rim.position.set(-4, 3, -4); scene.add(rim);
scene.add(new THREE.HemisphereLight(0xdfe5ff, 0x1a2040, 0.5));

// ---------- procedural textures ----------
function canvasTex(w, h, draw, repeat = [1, 1], srgb = false) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(...repeat);
  t.anisotropy = 4; if (srgb) t.colorSpace = THREE.SRGBColorSpace; return t;
}
function noise(ctx, w, h, a, b, n = 6000, s = 1.4) { ctx.fillStyle = a; ctx.fillRect(0, 0, w, h); for (let i = 0; i < n; i++) { ctx.fillStyle = Math.random() < 0.5 ? b : 'rgba(255,255,255,.06)'; ctx.fillRect(Math.random() * w, Math.random() * h, s, s); } }

// ---------- dimensions (metres) ----------
const W = 2.2, D = 1.536, H = 2.3, T = 0.08, GAP = 0.008, BASE = 0.06;
const Y0 = GAP + BASE, ROOF = 0.14, WALL_H = H - Y0 - ROOF, ZF = D / 2 - 0.035;
const IW = 2.04, ID = D - T - 0.05;

// ---------- materials (replace the GLB's by name) ----------
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const shell = new THREE.MeshPhysicalMaterial({ color: new THREE.Color(css('--shell') || '#ecebe6'), roughness: 0.32, metalness: 0, clearcoat: 0.6, clearcoatRoughness: 0.25 });
const std = (c, r = 0.6, m = 0) => new THREE.MeshStandardMaterial({ color: c, roughness: r, metalness: m });
const trim = std(0x111214, 0.45, 0.2), rubber = std(0x0c0d0f, 0.9), seam = std(0x1a1b1e, 0.7);
const glass = new THREE.MeshPhysicalMaterial({ color: 0xe4ecf7, roughness: 0.02, transparent: true, opacity: 0.12, envMapIntensity: 2.2, clearcoat: 1, side: THREE.DoubleSide, depthWrite: false });
const felt = std(0x3a3c41, 1), backPanel = new THREE.MeshPhysicalMaterial({ color: 0xc4c5c2, roughness: 0.35, clearcoat: 1, clearcoatRoughness: 0.04 }), carpet = std(0x26282d, 1);
const fabric = std(0x8b8d93, 0.95), fabricBase = std(0x45474d, 0.9), deskM = std(0xf1f1ee, 0.3), wood = std(0xb08657, 0.55), plate = std(0xececea, 0.4);
const iconM = new THREE.MeshBasicMaterial({ color: 0xf2f2f2 });
const lightM = new THREE.MeshBasicMaterial({ color: 0x3a3d45, toneMapped: false });
const LIGHT_OFF = new THREE.Color(0x3a3d45), LIGHT_ON = new THREE.Color(0xfff2dc);
// monitor UI (illustrative)
const screenTex = canvasTex(256, 152, (x, w, h) => {
  const g = x.createLinearGradient(0, 0, w, h); g.addColorStop(0, '#1d4fbf'); g.addColorStop(1, '#4fa3ff'); x.fillStyle = g; x.fillRect(0, 0, w, h);
  x.fillStyle = 'rgba(255,255,255,.9)'; x.fillRect(10, 8, 60, 6);
  const tiles = ['#ff8a3d', '#2ec27e', '#ffd43b', '#e64980', '#4dabf7', '#9775fa'];
  tiles.forEach((c, i) => { x.fillStyle = c; x.fillRect(118 + (i % 3) * 44, 30 + Math.floor(i / 3) * 50, 38, 42); });
  x.fillStyle = 'rgba(255,255,255,.85)'; x.fillRect(12, 30, 98, 92);
}, [1, 1], true);
screenTex.flipY = false; screenTex.wrapS = screenTex.wrapT = THREE.ClampToEdgeWrapping;
const screenM = new THREE.MeshBasicMaterial({ map: screenTex, toneMapped: false });

// ---------- load the Blender model ----------
const pod = new THREE.Group(); scene.add(pod);
const gltf = await new GLTFLoader().loadAsync(new URL('pod.glb', import.meta.url).href);
const model = gltf.scene; pod.add(model);
const MATS = { Shell: shell, Trim: trim, Rubber: rubber, Seam: seam, Glass: glass, Felt: felt, BackPanel: backPanel, Carpet: carpet,
  Fabric: fabric, FabricBase: fabricBase, Desk: deskM, Wood: wood, Plate: plate, LightPanel: lightM, Screen: screenM, Icon: iconM };
let logoM = null;
const LOGO_DARK = new THREE.Color(0x262c30), LOGO_LIGHT = new THREE.Color(0xf2f2f2);
model.traverse(o => {
  if (!o.isMesh) return;
  const src = o.material, m = MATS[src && src.name];
  if (src && src.name === 'Logo') logoM = src;
  if (m) {
    // textile textures are made in Blender (colour baked in): keep them
    if (src.map && !m.map) { m.map = src.map; m.map.anisotropy = 8; m.color.set(0xffffff); }
    if (src.normalMap && !m.normalMap) { m.normalMap = src.normalMap; m.normalScale.copy(src.normalScale); }
    o.material = m;
  }
  const isGlass = o.material === glass || o.material === lightM || o.material === iconM || o.material === screenM;
  o.castShadow = !isGlass; o.receiveShadow = !isGlass;
});
const node = n => model.getObjectByName(n);
const DIRS = { PartShell: [0, 0.62, 0], PartFront: [0, 0.05, 1.05], PartBack: [0, 0.05, -1.0] };
const PARTS = Object.entries(DIRS).map(([n, d]) => { const g = node(n); g.userData.dir = new THREE.Vector3(...d); g.userData.base = g.position.clone(); return g; });
const door = node('Door'); const doorBase = door.rotation.y;
const inner = new THREE.PointLight(0xffe9cc, 0, 3.6, 2); inner.position.set(0.05, 1.85, 0); node('PartShell').add(inner);

// ---------- airflow particles ----------
const N = 160, pPos = new Float32Array(N * 3), seeds = [];
for (let i = 0; i < N; i++) seeds.push([Math.random() * IW * 0.9 - IW * 0.45, Math.random(), Math.random() * ID * 0.9 - ID * 0.45 - 0.02, 0.25 + Math.random() * 0.5]);
const pGeo = new THREE.BufferGeometry(); pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
const pMat = new THREE.PointsMaterial({ color: 0xbcd0ff, size: 0.028, transparent: true, opacity: 0, depthWrite: false });
pod.add(new THREE.Points(pGeo, pMat));

// ---------- ground: shadow catcher + soft blue glow ----------
const ground = new THREE.Mesh(new THREE.PlaneGeometry(14, 14), new THREE.ShadowMaterial({ opacity: 0.45 }));
ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; scene.add(ground);
const gc = canvasTex(128, 128, (x) => { const r = x.createRadialGradient(64, 64, 4, 64, 64, 64); r.addColorStop(0, 'rgba(126,148,255,.5)'); r.addColorStop(.5, 'rgba(80,100,200,.16)'); r.addColorStop(1, 'rgba(52,71,140,0)'); x.fillStyle = r; x.fillRect(0, 0, 128, 128); });
const glow = new THREE.Mesh(new THREE.PlaneGeometry(5.5, 4.4), new THREE.MeshBasicMaterial({ map: gc, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
glow.rotation.x = -Math.PI / 2; glow.position.y = 0.001; scene.add(glow);

// ---------- hotspots (explore mode) ----------
const HOT = [
  { p: [0.62, 1.25, D / 2 - 0.03], n: [0, 0, 1], t: '10mm 強化玻璃', b: '成幅玻璃門面，光猛又隔音。' },
  { p: [W / 2 + 0.01, 1.9, 0.47], n: [1, 0, 0.3], t: '渦輪增壓鮮風系統', b: '每 2 分鐘全艙換一次氣。' },
  { p: [0.08, 2.1, -0.08], n: [0, -1, 0.4], t: '4000K / 750 Lux', b: '自然光中央照明。' },
  { p: [-IW / 2 + 0.03, 1.45, 0.1], n: [1, 0, 0.3], t: '高密度吸音物料', b: '隔音量約 25 dB，回音時間 0.25 秒。' },
  { p: [0, 0.85, 0.02], n: [0, 1, 0.6], t: 'ST-05 電腦枱', b: '隨艙附送。' },
  { p: [-(IW / 2 - 0.3), 0.52, 0.2], n: [0.3, 1, 0.5], t: 'SY-05 梳化 ×2', b: '隨艙附送，四個人坐得舒服。' },
  { p: [0, 1.27, -0.57], n: [0, 0, 1], t: 'SJ-01 顯示支架', b: '另外選購。屏幕同鏡頭只作示意。' },
  { p: [W / 2 - 0.14, 0.02, D / 2 - 0.14], n: [0.4, 0.3, 1], t: '8mm 底部空隙', b: '橡膠阻尼腳墊，要搬位都方便。' }
];
const hotEls = HOT.map((h, i) => {
  const b = document.createElement('button'); b.type = 'button'; b.className = 'hot'; b.setAttribute('aria-label', h.t);
  b.innerHTML = '<span class="hot-dot"></span><span class="hot-card"><b>' + h.t + '</b><span>' + h.b + '</span></span>';
  b.addEventListener('click', e => { e.stopPropagation(); const on = !b.classList.contains('open'); hotEls.forEach(x => x.classList.remove('open')); b.classList.toggle('open', on); });
  hotLayer.appendChild(b); h.v = new THREE.Vector3(...h.p); h.nv = new THREE.Vector3(...h.n).normalize(); return b;
});
const tmpV = new THREE.Vector3(), tmpN = new THREE.Vector3(), camDir = new THREE.Vector3();
function placeHotspots() {
  const w = stage.clientWidth, h = stage.clientHeight;
  HOT.forEach((hs, i) => {
    tmpV.copy(hs.v).applyMatrix4(pod.matrixWorld);
    tmpN.copy(hs.nv).applyQuaternion(pod.quaternion);
    camDir.copy(camera.position).sub(tmpV).normalize();
    const facing = tmpN.dot(camDir) > 0.05 || camera.position.distanceTo(look) < 2.4;
    tmpV.project(camera);
    const el = hotEls[i];
    el.style.transform = 'translate(' + ((tmpV.x * 0.5 + 0.5) * w) + 'px,' + ((-tmpV.y * 0.5 + 0.5) * h) + 'px)';
    el.classList.toggle('hidden', !facing || tmpV.z > 1);
  });
}

// ---------- story keyframes (6 chapters across p = 0..1) ----------
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const C = 1 / 6;
const ROT_KEYS = [[0, -0.95], [C * 0.9, -0.5], [C * 1.9, -0.15], [C * 2.9, 0.6], [C * 3.9, -0.75], [C * 4.9, -0.45], [1, -0.25]];
const DIST_KEYS = [[0, 1], [C * 1.9, 0.84], [C * 2.6, 0.95], [C * 3.9, 1.25], [C * 4.7, 1.0], [1, 1]];
function keyed(keys, p) { for (let i = 1; i < keys.length; i++) if (p <= keys[i][0]) { const [a, va] = keys[i - 1], [b, vb] = keys[i]; return va + (vb - va) * smooth(a, b, p); } return keys[keys.length - 1][1]; }

// ---------- state ----------
let story = 0, storyEased = 0, userRot = 0, vel = 0, dragging = false, lastX = 0;
let chosen = shell.color.clone(), target = chosen.clone(), cycle = null;
let exploring = false, xDoor = 0, xLight = 1, xEx = 0, xDoorT = 0, xLightT = 1, xExT = 0;
const tmpC = new THREE.Color();

const controls = new OrbitControls(camera, canvas);
Object.assign(controls, { enabled: false, enableDamping: true, dampingFactor: 0.08, enablePan: false, minDistance: 1.2, maxDistance: 11, maxPolarAngle: Math.PI * 0.53, rotateSpeed: 0.8, zoomSpeed: 0.9 });
controls.target.copy(look);
controls.addEventListener('start', () => hotEls.forEach(x => x.classList.remove('open')));

window.__pod = {
  setStory(p) { story = Math.min(1, Math.max(0, p)); wake(); },
  setColour(hex) { chosen = new THREE.Color(hex); wake(); },
  setCycle(list) { cycle = list.map(h => new THREE.Color(h)); },
  explore(on) {
    exploring = on; controls.enabled = on; stage.classList.toggle('exploring', on);
    hotEls.forEach(x => x.classList.remove('open'));
    if (on) { xDoorT = 0; xLightT = 1; xExT = 0; xDoor = (door.rotation.y - doorBase) / 1.15; xLight = 1; xEx = 0; userRot = 0;
      camera.clearViewOffset(); const d = baseDist * 0.95; const a = pod.rotation.y; pod.rotation.y = 0;
      camera.position.set(Math.sin(-a) * d, 1.8, Math.cos(-a) * d); controls.target.copy(look); controls.update(); }
    fit(); wake();
  },
  setDoor(open) { xDoorT = open ? 1 : 0; wake(); },
  setExplode(on) { xExT = on ? 1 : 0; wake(); },
  setLight(on) { xLightT = on ? 1 : 0; wake(); },
  resetView() { const d = baseDist * 0.95; camera.position.set(Math.sin(0.5) * d, 1.8, Math.cos(0.5) * d); controls.target.copy(look); controls.update(); wake(); }
};

canvas.addEventListener('pointerdown', e => { if (exploring) return; dragging = true; lastX = e.clientX; vel = 0; canvas.setPointerCapture(e.pointerId); wake(); });
canvas.addEventListener('pointermove', e => { if (!dragging || exploring) return; const dx = e.clientX - lastX; lastX = e.clientX; userRot += dx * 0.009; vel = dx * 0.009; wake(); });
const end = () => { dragging = false; };
canvas.addEventListener('pointerup', end); canvas.addEventListener('pointercancel', end);

// ---------- sizing ----------
let baseDist = 8;
function fit() {
  const w = stage.clientWidth, h = stage.clientHeight; if (!w || !h) return;
  const wide = w >= 1024;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  const tanV = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
  baseDist = Math.max(1.5 / tanV, 1.75 / (tanV * camera.aspect * (wide && !exploring ? 0.55 : 1))) + 1.0;
  if (exploring) camera.clearViewOffset();
  else if (wide) camera.setViewOffset(w, h, -w * 0.2, 0, w, h);
  else camera.setViewOffset(w, h, 0, -h * 0.12, w, h);
  camera.updateProjectionMatrix();
  wake();
}
new ResizeObserver(fit).observe(stage);

let running = false, visible = true, last = performance.now(), clock = 0;
new IntersectionObserver(es => { visible = es[0].isIntersecting; if (visible) wake(); }).observe(stage);
document.addEventListener('visibilitychange', () => { if (!document.hidden) wake(); });
function wake() { if (!running && (visible || exploring)) { running = true; last = performance.now(); requestAnimationFrame(tick); } }
const approach = (v, t, k) => Math.abs(v - t) < 0.001 ? t : v + (t - v) * k;

function tick(now) {
  const dt = Math.min((now - last) / 1000, 0.05); last = now; clock += dt;
  let busy = exploring;
  const k = reduce ? 1 : Math.min(1, dt * 6);
  storyEased = approach(storyEased, story, k); if (storyEased !== story) busy = true;
  if (!dragging && Math.abs(vel) > 0.0004) { userRot += vel; vel *= 0.92; busy = true; }
  const p = storyEased;
  let doorV, lightV, exV, airA;
  if (exploring) {
    xDoor = approach(xDoor, xDoorT, k); xLight = approach(xLight, xLightT, k); xEx = approach(xEx, xExT, Math.min(1, dt * 4));
    doorV = xDoor; lightV = xLight; exV = xEx; airA = 0;
    controls.update();
  } else {
    pod.rotation.y = (reduce ? -0.5 : keyed(ROT_KEYS, p)) + userRot;
    doorV = 1 - smooth(C * 0.9, C * 1.5, p);
    lightV = smooth(C * 1.8, C * 2.3, p);
    exV = reduce ? 0 : smooth(C * 3.85, C * 4.35, p) * (1 - smooth(C * 4.75, C * 5.1, p));
    airA = smooth(C * 2.7, C * 3.1, p) * (1 - smooth(C * 3.7, C * 4.0, p));
    const dist = baseDist * (reduce ? 1 : keyed(DIST_KEYS, p));
    camera.position.set(0, 1.8, dist); camera.lookAt(look);
  }
  glow.rotation.z = pod.rotation.y;
  door.rotation.y = doorBase + 1.15 * doorV;
  lightM.color.copy(LIGHT_OFF).lerp(LIGHT_ON, lightV);
  inner.intensity = 2.4 * lightV;
  for (const g of PARTS) g.position.copy(g.userData.base).addScaledVector(g.userData.dir, exV);
  pMat.opacity = airA * 0.9;
  if (airA > 0.01) {
    for (let i = 0; i < N; i++) { const s = seeds[i], y = 1 - ((s[1] + clock * s[3] * 0.35) % 1);
      pPos[i * 3] = s[0] + Math.sin(clock * 1.3 + i) * 0.04; pPos[i * 3 + 1] = Y0 + 0.05 + y * (WALL_H - 0.15); pPos[i * 3 + 2] = s[2]; }
    pGeo.attributes.position.needsUpdate = true; busy = true;
  }
  if (!exploring && cycle && p > C * 5.05) target = cycle[Math.min(cycle.length - 1, Math.floor(smooth(C * 5.05, 0.99, p) * cycle.length))];
  else target = chosen;
  if (!shell.color.equals(target)) { shell.color.lerp(target, Math.min(1, dt * 7)); tmpC.copy(shell.color).sub(target);
    if (Math.abs(tmpC.r) + Math.abs(tmpC.g) + Math.abs(tmpC.b) < 0.003) shell.color.copy(target); busy = true; }
  if (logoM) logoM.color.copy(shell.color.r + shell.color.g + shell.color.b < 0.7 ? LOGO_LIGHT : LOGO_DARK);

  renderer.render(scene, camera);
  if (exploring) placeHotspots();
  if (!stage.classList.contains('ready')) stage.classList.add('ready');
  if ((busy || dragging) && (visible || exploring) && !document.hidden) requestAnimationFrame(tick); else running = false;
}

const yieldFrame = () => new Promise(r => setTimeout(r, 0));
await yieldFrame();
if (renderer.compileAsync) { try { await renderer.compileAsync(scene, camera); } catch (e) {} }
fit();
if (window.__podQueue) window.__podQueue.forEach(f => f(window.__pod));
