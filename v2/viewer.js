// v2 configurator viewer: the Blender pod (../pod.glb) on a light stage.
// Outside: orbit + zoom. Inside: fly through the door to a seat and look around
// (drag, or move the phone). AR lives in index.html (model-viewer, same GLB).
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const wrap = document.getElementById('viewer');
const canvas = wrap.querySelector('canvas');
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
const touch = matchMedia('(pointer: coarse)').matches;
const GLB = new URL('../pod.glb', import.meta.url).href;

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(renderer), 0.04).texture;
scene.environmentIntensity = 0.85;
const key = new THREE.DirectionalLight(0xffffff, 2.0);
key.position.set(-3.5, 6, 5);
key.castShadow = true;
key.shadow.mapSize.set(touch ? 1024 : 2048, touch ? 1024 : 2048);
Object.assign(key.shadow.camera, { left: -3, right: 3, top: 3.5, bottom: -1, near: 1, far: 16 });
key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02; key.shadow.radius = 5;
scene.add(key, new THREE.HemisphereLight(0xffffff, 0xd9d4ca, 0.7));
const ground = new THREE.Mesh(new THREE.PlaneGeometry(14, 14), new THREE.ShadowMaterial({ opacity: 0.16 }));
ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; scene.add(ground);

// ---------- model: Blender materials as exported, except glass (cheap) and the screen (UI canvas)
const glass = new THREE.MeshPhysicalMaterial({ color: 0xe4ecf7, roughness: 0.02, transparent: true, opacity: 0.12,
  envMapIntensity: 2.2, clearcoat: 1, side: THREE.DoubleSide, depthWrite: false });
const sc = document.createElement('canvas'); sc.width = 512; sc.height = 300;
{ const x = sc.getContext('2d'), g = x.createLinearGradient(0, 0, 512, 300);
  g.addColorStop(0, '#1d4fbf'); g.addColorStop(1, '#4fa3ff'); x.fillStyle = g; x.fillRect(0, 0, 512, 300);
  x.fillStyle = 'rgba(255,255,255,.9)'; x.fillRect(20, 16, 120, 12); x.fillRect(24, 60, 196, 184);
  ['#ff8a3d', '#2ec27e', '#ffd43b', '#e64980', '#4dabf7', '#9775fa'].forEach((c, i) => { x.fillStyle = c; x.fillRect(236 + (i % 3) * 88, 60 + Math.floor(i / 3) * 100, 76, 84); }); }
const screenTex = new THREE.CanvasTexture(sc); screenTex.colorSpace = THREE.SRGBColorSpace; screenTex.flipY = false;
const screenM = new THREE.MeshBasicMaterial({ map: screenTex, toneMapped: false });

const gltf = await new GLTFLoader().loadAsync(GLB);
const model = gltf.scene; scene.add(model);
let shellM, logoM, ledM;
model.traverse(o => {
  if (!o.isMesh) return;
  const n = o.material.name;
  if (n === 'Glass') o.material = glass;
  else if (n === 'Screen') o.material = screenM;
  else if (n === 'Shell') shellM = o.material;
  else if (n === 'Logo') logoM = o.material;
  else if (n === 'LightPanel') ledM = o.material;
  if (o.material.map) o.material.map.anisotropy = 8;
  const see = o.material !== glass && n !== 'LightPanel' && n !== 'Icon';
  o.castShadow = see; o.receiveShadow = see;
});
const door = model.getObjectByName('Door');
const inner = new THREE.PointLight(0xffe9cc, 0, 3.6, 2); inner.position.set(0.05, 1.85, 0); scene.add(inner);

// ---------- camera + controls
const FOV_OUT = 32, FOV_IN = 70;   // product lens outside, natural eye inside
const camera = new THREE.PerspectiveCamera(FOV_OUT, 1, 0.03, 60);
const controls = new OrbitControls(camera, canvas);
Object.assign(controls, { enableDamping: true, dampingFactor: 0.08, enablePan: false, rotateSpeed: 0.7 });
const LOOK = new THREE.Vector3(0, 1.1, 0);
const SPOTS = {   // eye position, what to look at (three.js: +z = front of the pod)
  seat: [[-0.72, 1.12, 0.15], [0, 1.25, -0.6]],
  door: [[-0.05, 1.6, 0.5], [0, 1.1, -0.7]],
  out:  [[0.72, 1.12, -0.35], [-0.4, 1.2, 1.5]],
};
let inside = false, dist = 7;
function outsideLimits() {
  Object.assign(controls, { minDistance: 2.4, maxDistance: 10, enableZoom: true, minPolarAngle: 0.15 * Math.PI, maxPolarAngle: 0.53 * Math.PI, rotateSpeed: 0.7 });
}
function insideLimits() {
  Object.assign(controls, { minDistance: 0.01, maxDistance: 0.01, enableZoom: false, minPolarAngle: 0.22 * Math.PI, maxPolarAngle: 0.78 * Math.PI, rotateSpeed: 0.45 });
}
function outsidePose(a = 0.55) { return [[Math.sin(a) * dist, 1.75, Math.cos(a) * dist], LOOK.toArray()]; }
outsideLimits();

// ---------- tweens (camera flights, door, light, colour)
let flight = null;
const ease = k => k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
function fly([pos, look], ms = 1100, fov = camera.fov) {
  return new Promise(done => {
    flight = { p0: camera.position.clone(), t0: controls.target.clone(), p1: new THREE.Vector3(...pos), t1: new THREE.Vector3(...look), f0: camera.fov, f1: fov,
      s: performance.now(), d: reduce ? 1 : ms, done };
    controls.enabled = false; wake();
  });
}
let doorV = 0, doorT = 0, lightV = 1, lightT = 1;
const colour = new THREE.Color(0xecebe6), colourT = colour.clone();
const LOGO_DARK = new THREE.Color(0x262c30), LOGO_LIGHT = new THREE.Color(0xe8e8e8);
const LED_OFF = new THREE.Color(0x3a3d45), LED_ON = new THREE.Color(0xfff2dc);

// ---------- gyro look-around (phones): device orientation -> camera, relative to the pose when switched on
let gyroOn = false, gyroBase = null;
const devQ = new THREE.Quaternion(), tmpQ = new THREE.Quaternion(), qX = new THREE.Quaternion(-Math.SQRT1_2, 0, 0, Math.SQRT1_2), eul = new THREE.Euler(), zee = new THREE.Vector3(0, 0, 1);
function onOrient(e) {
  if (e.alpha == null) return;
  const r = THREE.MathUtils.degToRad;
  eul.set(r(e.beta), r(e.alpha), -r(e.gamma), 'YXZ');
  devQ.setFromEuler(eul).multiply(qX).multiply(tmpQ.setFromAxisAngle(zee, -r(screen.orientation ? screen.orientation.angle : 0)));
  if (!gyroBase) gyroBase = camera.quaternion.clone().multiply(devQ.clone().invert());
  camera.quaternion.copy(gyroBase).multiply(devQ); wake();
}

// ---------- loop
let running = false, visible = true;
new IntersectionObserver(es => { visible = es[0].isIntersecting; wake(); }).observe(wrap);
function wake() { if (!running && visible) { running = true; requestAnimationFrame(tick); } }
const approach = (v, t, k) => Math.abs(v - t) < 0.001 ? t : v + (t - v) * k;
let last = performance.now(), idle = 0;
function tick(now) {
  const k = reduce ? 1 : Math.min(1, (now - last) / 1000 * 6); last = now;
  if (flight) {
    const f = flight, p = Math.min(1, (now - f.s) / f.d), e = ease(p);
    camera.position.lerpVectors(f.p0, f.p1, e); controls.target.lerpVectors(f.t0, f.t1, e); camera.lookAt(controls.target);
    camera.fov = f.f0 + (f.f1 - f.f0) * e; camera.updateProjectionMatrix();
    if (p === 1) { flight = null; controls.enabled = !gyroOn; f.done(); }
  } else if (!gyroOn) controls.update();
  doorV = approach(doorV, doorT, k); lightV = approach(lightV, lightT, k);
  door.rotation.y = 1.15 * doorV;
  ledM.emissiveIntensity = 4 * lightV; ledM.color.copy(LED_OFF).lerp(LED_ON, lightV);
  inner.intensity = 2.4 * lightV;
  colour.lerp(colourT, k); shellM.color.copy(colour);
  logoM.color.copy(colour.r + colour.g + colour.b < 0.7 ? LOGO_LIGHT : LOGO_DARK);
  renderer.render(scene, camera);
  const busy = flight || doorV !== doorT || lightV !== lightT || !colour.equals(colourT);
  idle = busy ? 0 : idle + 1;
  if (visible && (idle < 90 || gyroOn)) requestAnimationFrame(tick); else running = false;   // damping settles in ~90 frames
}
controls.addEventListener('change', wake);
canvas.addEventListener('pointerdown', () => { idle = 0; wake(); });

function fit() {
  const w = wrap.clientWidth, h = wrap.clientHeight; if (!w || !h) return;
  renderer.setSize(w, h, false); camera.aspect = w / h;
  const tanV = Math.tan(THREE.MathUtils.degToRad(FOV_OUT / 2));
  dist = Math.max(1.45 / tanV, 1.7 / (tanV * camera.aspect)) + 1.2;
  camera.updateProjectionMatrix(); wake();
}
new ResizeObserver(fit).observe(wrap);
fit();
{ const [p, l] = outsidePose(); camera.position.set(...p); controls.target.set(...l); controls.update(); }

window.__v2pod = {
  setColour(hex) { colourT.set(hex); wake(); },
  setDoor(on) { doorT = on ? 1 : 0; wake(); },
  setLight(on) { lightT = on ? 1 : 0; wake(); },
  get inside() { return inside; },
  async enter(spot = 'seat') {
    this.gyro(false);
    if (!inside) {
      doorT = 1; lightT = 1; inside = true; insideLimits();
      await fly([[-0.075, 1.45, 1.35], [0, 1.2, -0.7]], 1200, 55);
    }
    const [p, l] = SPOTS[spot];
    await fly([p, l], 1000, FOV_IN);
    const dir = new THREE.Vector3(...l).sub(new THREE.Vector3(...p)).normalize();
    controls.target.copy(camera.position).addScaledVector(dir, 0.01); controls.update();
  },
  async exit() {
    this.gyro(false);
    if (!inside) return;
    inside = false;
    await fly([[-0.075, 1.45, 1.35], [0, 1.2, -0.7]], 900, 55);
    outsideLimits();
    await fly(outsidePose(), 1100, FOV_OUT);
    doorT = 0;
  },
  async gyro(on) {
    if (on === gyroOn) return gyroOn;
    if (on) {
      if (typeof DeviceOrientationEvent === 'undefined') return false;
      if (DeviceOrientationEvent.requestPermission) {
        try { if (await DeviceOrientationEvent.requestPermission() !== 'granted') return false; } catch (e) { return false; }
      }
      gyroBase = null; gyroOn = true; controls.enabled = false;
      addEventListener('deviceorientation', onOrient);
    } else {
      gyroOn = false; removeEventListener('deviceorientation', onOrient);
      const dir = new THREE.Vector3(0, 0, -1).applyQuaternion(camera.quaternion);
      controls.target.copy(camera.position).addScaledVector(dir, inside ? 0.01 : camera.position.distanceTo(LOOK));
      controls.enabled = true; controls.update();
    }
    wake(); return gyroOn;
  },
};
wrap.classList.add('ready');
wrap.dispatchEvent(new Event('viewer-ready'));
