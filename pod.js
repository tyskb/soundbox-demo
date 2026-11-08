// Soundbox 4-person pod: stylised 3D illustration built to the published outer size
// (W220 x D153.6 x H230 cm). Not a product scan.
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

const stage = document.getElementById('stage');
const canvas = document.getElementById('pod');
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;

const scene = new THREE.Scene();
// cheap studio environment: a small gradient equirect instead of a rendered room
{
  const ec = document.createElement('canvas'); ec.width = 64; ec.height = 32;
  const x = ec.getContext('2d'), gr = x.createLinearGradient(0, 0, 0, 32);
  gr.addColorStop(0, '#ffffff'); gr.addColorStop(0.45, '#f4f6fb'); gr.addColorStop(0.55, '#c9cfdd'); gr.addColorStop(1, '#8e95a8');
  x.fillStyle = gr; x.fillRect(0, 0, 64, 32);
  x.fillStyle = 'rgba(255,255,255,.95)'; x.fillRect(10, 6, 14, 6); x.fillRect(40, 5, 10, 5);
  const et = new THREE.CanvasTexture(ec); et.mapping = THREE.EquirectangularReflectionMapping; et.colorSpace = THREE.SRGBColorSpace;
  scene.environment = et;
}
const yieldFrame = () => new Promise(r => setTimeout(r, 0));

const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 60);
const look = new THREE.Vector3(0, 1.1, 0);

// lights
const key = new THREE.DirectionalLight(0xffffff, 1.4); key.position.set(3, 6, 5); scene.add(key);
scene.add(new THREE.HemisphereLight(0xffffff, 0xdfe3ee, 0.5));

// ---- dimensions (metres)
const W = 2.2, D = 1.536, H = 2.3, T = 0.08, GAP = 0.008, BASE = 0.06;
const Y0 = GAP + BASE, ROOF = 0.14, WALL_H = H - Y0 - ROOF;
const ZF = D / 2 - 0.035; // front glazing plane

// ---- materials
const shellCol = new THREE.Color(getComputedStyle(document.documentElement).getPropertyValue('--shell').trim() || '#ecebe6');
const shell = new THREE.MeshStandardMaterial({ color: shellCol.clone(), roughness: 0.5, metalness: 0.04 });
const trim = new THREE.MeshStandardMaterial({ color: 0x24272d, roughness: 0.35, metalness: 0.65 });
const glass = new THREE.MeshPhysicalMaterial({ color: 0xe6eef5, roughness: 0.04, metalness: 0, transparent: true, opacity: 0.16, envMapIntensity: 1.6, clearcoat: 1, side: THREE.DoubleSide, depthWrite: false });
const felt = new THREE.MeshStandardMaterial({ color: 0xc9ccd4, roughness: 1 });
const floorM = new THREE.MeshStandardMaterial({ color: 0x5b606b, roughness: 0.95 });
const fabric = new THREE.MeshStandardMaterial({ color: 0x353c52, roughness: 0.9 });
const deskM = new THREE.MeshStandardMaterial({ color: 0xf3f0ea, roughness: 0.45 });
const lightM = new THREE.MeshBasicMaterial({ color: 0xfff1de, toneMapped: false });

const pod = new THREE.Group();
scene.add(pod);
const rb = (w, h, d, r = 0.02) => new RoundedBoxGeometry(w, h, d, 2, r);
const box = (w, h, d) => new THREE.BoxGeometry(w, h, d);
function add(geo, mat, x, y, z, parent = pod) { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); parent.add(m); return m; }

// base plinth (sits 8 mm off the floor on damping feet)
add(rb(W, BASE, D, 0.012), trim, 0, GAP + BASE / 2, 0);
// shell
add(rb(W, WALL_H, T, 0.025), shell, 0, Y0 + WALL_H / 2, -D / 2 + T / 2);               // back
add(rb(T, WALL_H, D, 0.025), shell, -W / 2 + T / 2, Y0 + WALL_H / 2, 0);               // left
add(rb(T, WALL_H, D, 0.025), shell, W / 2 - T / 2, Y0 + WALL_H / 2, 0);                // right
add(rb(W, ROOF, D, 0.035), shell, 0, H - ROOF / 2, 0);                                  // roof
add(box(W - 0.5, 0.012, 0.03), trim, 0, H - ROOF + 0.05, D / 2 + 0.001);               // fresh-air intake slot
// interior lining + floor
const IW = W - 2 * T, ID = D - T - 0.05;
add(box(IW, WALL_H, 0.01), felt, 0, Y0 + WALL_H / 2, -D / 2 + T + 0.006);
add(box(0.01, WALL_H, ID), felt, -IW / 2 + 0.006, Y0 + WALL_H / 2, -0.02);
add(box(0.01, WALL_H, ID), felt, IW / 2 - 0.006, Y0 + WALL_H / 2, -0.02);
add(box(IW, 0.01, ID), floorM, 0, Y0 + 0.005, -0.02);
// ceiling light panel (4000K)
const lp = add(new THREE.PlaneGeometry(IW - 0.5, ID - 0.5), lightM, 0, H - ROOF - 0.004, -0.05);
lp.rotation.x = Math.PI / 2;
const inner = new THREE.PointLight(0xffeedd, 2.2, 3.2, 2); inner.position.set(0, H - ROOF - 0.25, -0.05); pod.add(inner);

// furniture: ST-05 desk + two SY-05 sofas
add(box(0.66, 0.03, 0.9), deskM, 0, Y0 + 0.73, -0.12);
add(new THREE.CylinderGeometry(0.03, 0.03, 0.7, 16), trim, 0, Y0 + 0.36, -0.12);
add(new THREE.CylinderGeometry(0.22, 0.22, 0.015, 32), trim, 0, Y0 + 0.01, -0.12);
for (const s of [-1, 1]) {
  const x = s * (IW / 2 - 0.27);
  add(rb(0.5, 0.42, 1.15, 0.05), fabric, x, Y0 + 0.21, -0.12);
  add(rb(0.14, 0.5, 1.15, 0.05), fabric, s * (IW / 2 - 0.08), Y0 + 0.62, -0.12);
}

// front: frame, fixed pane (left), hinged door (right)
const FH = WALL_H, FY = Y0 + FH / 2;
add(box(IW, 0.04, 0.05), trim, 0, Y0 + 0.02, ZF);
add(box(IW, 0.04, 0.05), trim, 0, Y0 + FH - 0.02, ZF);
add(box(0.035, FH, 0.05), trim, 0, FY, ZF);
const paneW = IW / 2 - 0.02;
add(box(paneW, FH - 0.08, 0.01), glass, -IW / 4, FY, ZF);

const door = new THREE.Group();
door.position.set(IW / 2 - 0.005, FY, ZF + 0.012);
pod.add(door);
add(box(paneW, FH - 0.08, 0.01), glass, -paneW / 2, 0, 0, door);
add(box(0.03, FH - 0.08, 0.035), trim, -paneW + 0.015, 0, 0, door);
add(box(0.03, FH - 0.08, 0.035), trim, -0.015, 0, 0, door);
add(new THREE.CylinderGeometry(0.013, 0.013, 0.42, 12), trim, -paneW + 0.08, 0.02, 0.045, door);
add(box(0.02, 0.02, 0.05), trim, -paneW + 0.08, 0.2, 0.025, door);
add(box(0.02, 0.02, 0.05), trim, -paneW + 0.08, -0.16, 0.025, door);

// soft contact shadow
const sc = document.createElement('canvas'); sc.width = sc.height = 128;
const g = sc.getContext('2d'), grd = g.createRadialGradient(64, 64, 6, 64, 64, 64);
grd.addColorStop(0, 'rgba(22,28,51,.55)'); grd.addColorStop(.55, 'rgba(22,28,51,.18)'); grd.addColorStop(1, 'rgba(22,28,51,0)');
g.fillStyle = grd; g.fillRect(0, 0, 128, 128);
const shadow = new THREE.Mesh(new THREE.PlaneGeometry(4.2, 3.4), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(sc), transparent: true, depthWrite: false }));
shadow.rotation.x = -Math.PI / 2; shadow.position.y = 0.001; scene.add(shadow);

// ---- sizing
function fit() {
  const w = stage.clientWidth, h = stage.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  const tanV = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
  const dist = Math.max(1.45 / tanV, 1.6 / (tanV * camera.aspect)) + 1.0;
  camera.position.set(0, 1.75, dist);
  camera.lookAt(look);
  camera.updateProjectionMatrix();
  wake();
}
new ResizeObserver(fit).observe(stage);

// ---- interaction
let rot = -0.5, vel = 0, dragging = false, lastX = 0, touched = false;
let doorT = 0, doorTarget = 0, rise = reduce ? 1 : 0;
canvas.addEventListener('pointerdown', e => { dragging = true; lastX = e.clientX; vel = 0; canvas.setPointerCapture(e.pointerId); if (!touched) { touched = true; stage.classList.add('touched'); } wake(); });
canvas.addEventListener('pointermove', e => { if (!dragging) return; const dx = e.clientX - lastX; lastX = e.clientX; rot += dx * 0.009; vel = dx * 0.009; wake(); });
const end = () => { dragging = false; };
canvas.addEventListener('pointerup', end); canvas.addEventListener('pointercancel', end);

let targetCol = shell.color.clone();
window.__pod = {
  setColour(hex) { targetCol = new THREE.Color(hex); if (reduce) shell.color.copy(targetCol); wake(); },
  setDoor(open) { doorTarget = open ? 1 : 0; if (reduce) doorT = doorTarget; wake(); }
};
if (document.getElementById('doorBtn').getAttribute('aria-pressed') === 'true') window.__pod.setDoor(true);

// ---- render loop (sleeps when idle or off-screen)
let running = false, visible = true, last = performance.now(), idleT = 0;
new IntersectionObserver(es => { visible = es[0].isIntersecting; if (visible) wake(); }).observe(stage);
document.addEventListener('visibilitychange', () => { if (!document.hidden) wake(); });
function wake() { if (!running && visible) { running = true; last = performance.now(); requestAnimationFrame(tick); } }
const ease = t => 1 - Math.pow(1 - t, 3);

function tick(now) {
  const dt = Math.min((now - last) / 1000, 0.05); last = now;
  let busy = false;
  if (!dragging && Math.abs(vel) > 0.0004) { rot += vel; vel *= 0.92; busy = true; }
  if (!touched && !reduce) { idleT += dt; busy = true; }
  if (rise < 1) { rise = Math.min(1, rise + dt / 1.1); busy = true; }
  if (Math.abs(doorT - doorTarget) > 0.001) { doorT += (doorTarget - doorT) * Math.min(1, dt * 5); busy = true; } else doorT = doorTarget;
  if (!shell.color.equals(targetCol)) { shell.color.lerp(targetCol, Math.min(1, dt * 7)); if (Math.abs(shell.color.r - targetCol.r) + Math.abs(shell.color.g - targetCol.g) + Math.abs(shell.color.b - targetCol.b) < 0.003) shell.color.copy(targetCol); busy = true; }

  const sway = touched || reduce ? 0 : Math.sin(idleT * 0.45) * 0.28;
  pod.rotation.y = rot + sway;
  shadow.rotation.z = pod.rotation.y;
  const e = ease(rise);
  pod.position.y = (1 - e) * -0.35;
  door.rotation.y = doorT * 1.25;
  renderer.render(scene, camera);
  if (!stage.classList.contains('ready')) stage.classList.add('ready');

  if ((busy || dragging) && visible && !document.hidden) requestAnimationFrame(tick); else running = false;
}
await yieldFrame();
if (renderer.compileAsync) { try { await renderer.compileAsync(scene, camera); } catch (e) {} }
await yieldFrame();
fit();
