"""Studio product shots in Cycles, styled after the sb.contex.com.hk product photos
(white sweep, soft contact shadow, lights on inside). Run after build_pod.py:

    /Applications/Blender.app/Contents/MacOS/Blender -b blender/soundbox4.blend -P blender/render.py

Writes blender/renders/<shot>.png. Only touches the scene in memory; the .blend is not saved.
"""
import bpy, json, math, os
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'renders')
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene

# ---------- engine ----------
sc.render.engine = 'CYCLES'
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    sc.cycles.device = 'GPU'
except Exception as e:
    print('GPU not available, using CPU:', e)
sc.cycles.samples = int(os.environ.get('SAMPLES', 160))
sc.cycles.use_denoising = True
sc.cycles.max_bounces, sc.cycles.transmission_bounces, sc.cycles.glossy_bounces = 12, 12, 6
sc.render.resolution_x = sc.render.resolution_y = int(os.environ.get('RES', 1600))
sc.render.film_transparent = True
sc.view_settings.view_transform = os.environ.get('VIEW', 'Standard')   # product-shot contrast: crisp white shell, true blacks
sc.view_settings.exposure = float(os.environ.get('EXPOSURE', 0.0))

# ---------- materials: render-only tweaks ----------
def bsdf(name):
    return next(n for n in bpy.data.materials[name].node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
g = bsdf('Glass')
g.inputs['Base Color'].default_value = (1, 1, 1, 1)
g.inputs['Roughness'].default_value = 0.0
g.inputs['IOR'].default_value = 1.5
t = bsdf('Trim')
t.inputs['Roughness'].default_value, t.inputs['Metallic'].default_value = 0.6, 0.0

# optional shell colour (POD_COLOUR=#3d5c49), file suffix (TAG=-green) and backdrop (BG=#f3f2ee)
def srgb(h):
    return np.array([int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)], np.float32)
if os.environ.get('POD_COLOUR'):
    c = srgb(os.environ['POD_COLOUR'])
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    bsdf('Shell').inputs['Base Color'].default_value = (*lin, 1)
    if lin.sum() < 0.7:   # same rule as the web viewer: light logo on dark shells
        bsdf('Logo').inputs['Base Color'].default_value = (0.88, 0.88, 0.88, 1)
TAG = os.environ.get('TAG', '')
BG = srgb(os.environ.get('BG', '#ffffff'))

# monitor UI (illustrative), drawn here
W_, H_ = 1024, 600
ui = np.zeros((H_, W_, 4), np.float32); ui[..., 3] = 1
yy, xx = np.mgrid[0:H_, 0:W_]
ui[..., 0] = 0.05 + 0.10 * xx / W_; ui[..., 1] = 0.22 + 0.25 * xx / W_; ui[..., 2] = 0.62 + 0.3 * yy / H_
ui[H_ - 60:H_ - 40, 30:250, :3] = 0.95
ui[60:H_ - 110, 40:440, :3] = (0.93, 0.95, 0.98)
for i, c in enumerate([(1, .54, .24), (.18, .76, .49), (1, .83, .23), (.9, .29, .5), (.3, .67, 1), (.59, .46, .98)]):
    x0, y0 = 480 + (i % 3) * 175, H_ - 140 - (i // 3) * 200
    ui[y0 - 160:y0, x0:x0 + 155, :3] = c
scr_img = bpy.data.images.new('screen_ui', W_, H_)
scr_img.pixels.foreach_set(ui.ravel())
if 'Screen' in bpy.data.materials:   # only the pods with a display stand
    mt = bpy.data.materials['Screen'].node_tree
    tex = mt.nodes.new('ShaderNodeTexImage'); tex.image = scr_img
    s = bsdf('Screen')
    mt.links.new(tex.outputs['Color'], s.inputs['Base Color'])
    mt.links.new(tex.outputs['Color'], s.inputs['Emission Color'])
    s.inputs['Emission Strength'].default_value = 1.4

# ---------- studio ----------
world = bpy.data.worlds.new('Studio'); sc.world = world
wn = world.node_tree.nodes['Background']
wn.inputs['Color'].default_value = (1, 1, 1, 1)
wn.inputs['Strength'].default_value = 0.25   # low, so glass and black trim stay clean

bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
catcher = bpy.context.object
catcher.is_shadow_catcher = True

LIGHT = float(os.environ.get('LIGHT', 0.18))   # overall studio brightness

def area(name, loc, size, power, colour=(1, 1, 1), target=(0, 0, 1.1), sy=None):
    d = bpy.data.lights.new(name, 'AREA')
    d.energy, d.color, d.shape = power * LIGHT, colour, 'RECTANGLE'
    d.size, d.size_y = size, sy or size
    o = bpy.data.objects.new(name, d); sc.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o

area('Key', (-4.0, -5.0, 5.0), 5.0, 2600)
area('Fill', (5.5, -3.5, 2.5), 4.0, 1300)
area('Top', (0, 0.5, 6.5), 6.0, 1200, sy=4.0)
area('Rim', (1.0, 6.0, 4.0), 4.0, 900)
POD = json.loads(bpy.data.objects['Soundbox4']['pod'])          # size written by build_pod.py
PW, PD, PH = POD['w'], POD['d'], POD['h']
iw, idp = PW - 0.2, PD - 0.15
inside = area('Inside', (0.0, 0.0, PH - 0.22), 1.7 * iw / 2.0, 380 * (iw * idp) / (2.0 * 1.39), (1.0, 0.93, 0.84),
              target=(0, 0, 0), sy=0.79 * idp)   # 4000K ceiling light, scaled to the interior

# ---------- camera + shots ----------
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 70

SHOTS = {   # name: (yaw from the front, deg; +ve = towards the right/Contex side), distance, height
    'hero_3q': (28, 8.4, 1.55),
    'front': (0, 8.2, 1.4),
    'side_logo': (58, 8.2, 1.6),
}
only = os.environ.get('SHOT')

def flatten(raw, path, bg, fix_shadow=True):
    """RGBA render -> opaque PNG on a flat backdrop (white like the product photos, black for masks)."""
    im = bpy.data.images.load(raw)
    px = np.array(im.pixels[:], np.float32).reshape(-1, 4)
    if fix_shadow:   # shadow-catcher pixels carry a ~20% haze over the whole floor; keep only the contact shadow
        shadow = px[:, :3].max(1) < 0.03
        px[shadow, 3] = np.clip((px[shadow, 3] - 0.3) / 0.7, 0, 1)
    rgb = px[:, :3] * px[:, 3:4] + bg * (1 - px[:, 3:4])
    out = bpy.data.images.new('flat', im.size[0], im.size[1], alpha=False)
    out.pixels.foreach_set(np.concatenate([rgb, np.ones_like(px[:, :1])], 1).ravel())
    out.filepath_raw, out.file_format = path, 'PNG'
    out.save()
    bpy.data.images.remove(im); bpy.data.images.remove(out)
    os.remove(raw)

if only == 'spin':
    # 360 turntable for the web hero: the pod turns under fixed studio lights, camera at the hero angle.
    # Then a mask pass (shell = red, logo = green) so the page can recolour the shell itself.
    F = int(os.environ.get('FRAMES', 36))
    sdir = os.path.join(OUT, 'spin', POD['size'])
    os.makedirs(sdir, exist_ok=True)
    sw = int(os.environ.get('SPIN_W', 1000))
    sc.render.resolution_x, sc.render.resolution_y = sw, sw * 3 // 4
    root = bpy.data.objects['Soundbox4']
    inside.parent = root                                                   # ceiling light turns with the pod
    a = math.radians(28)
    k = max(3.6 * PH, 2.3 * math.hypot(PW, PD)) / 8.4                      # fits the widest angle too
    target = Vector((0.0, 0.0, 0.49 * PH))
    cam.location = target + Vector((math.sin(a) * 8.4 * k, -math.cos(a) * 8.4 * k, 0.42 * k))
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
    frames = [int(x) for x in os.environ['ONLY_FRAMES'].split(',')] if os.environ.get('ONLY_FRAMES') else range(F)
    for i in frames:
        root.rotation_euler.z = 2 * math.pi * i / F                       # +index = turns anticlockwise from above
        sc.render.filepath = raw = os.path.join(sdir, f'_{i:02d}.png')
        bpy.ops.render.render(write_still=True)
        flatten(raw, os.path.join(sdir, f'{i:02d}.png'), BG)
    for m in bpy.data.materials:                                           # mask pass
        if not m.node_tree:
            continue
        nt = m.node_tree; nt.nodes.clear()
        o = nt.nodes.new('ShaderNodeOutputMaterial')
        if m.name == 'Glass':
            sh = nt.nodes.new('ShaderNodeBsdfTransparent')
        else:
            sh = nt.nodes.new('ShaderNodeEmission')
            sh.inputs['Color'].default_value = {'Shell': (1, 0, 0, 1), 'Logo': (0, 1, 0, 1)}.get(m.name, (0, 0, 0, 1))
        nt.links.new(sh.outputs[0], o.inputs[0])
    catcher.hide_render = True
    wn.inputs['Strength'].default_value = 0
    sc.cycles.samples, sc.cycles.use_denoising = 16, False
    sc.view_settings.exposure = 0
    for i in frames:
        root.rotation_euler.z = 2 * math.pi * i / F
        sc.render.filepath = raw = os.path.join(sdir, f'_m{i:02d}.png')
        bpy.ops.render.render(write_still=True)
        flatten(raw, os.path.join(sdir, f'm{i:02d}.png'), np.zeros(3, np.float32), fix_shadow=False)
    print('rendered spin', POD['size'], len(frames))
    raise SystemExit

if only == 'inside':   # the web viewer's 'sit down' spot (three.js x, y-up, z=-Blender y), wide lens
    (px, py, pz), (lx, ly, lz) = POD['spots']['seat']
    cam.location = Vector((px, -pz, py))
    cam.rotation_euler = (Vector((lx, -lz, ly)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = 16
    sc.render.resolution_y = int(sc.render.resolution_x * 0.75)
    sc.render.filepath = os.path.join(OUT, f'inside{TAG}.png')
    sc.render.film_transparent = False
    bpy.ops.render.render(write_still=True)
    print('rendered inside')
    raise SystemExit
for name, (yaw, dist, hgt) in SHOTS.items():
    if only and name != only:
        continue
    a = math.radians(yaw)
    seen_w = PW * abs(math.cos(a)) + PD * abs(math.sin(a))          # width the camera sees at this angle
    k = max(3.6 * PH, 2.3 * seen_w) / 8.4                            # ~1.0 for the 4-person hero shot
    dist *= k
    target = Vector((0.0, 0.0, 0.49 * PH))
    cam.location = target + Vector((math.sin(a) * dist, -math.cos(a) * dist, (hgt - 1.13) * k))
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
    raw = os.path.join(OUT, f'_{name}{TAG}_rgba.png')
    sc.render.filepath = raw
    bpy.ops.render.render(write_still=True)
    # flatten onto the backdrop (white, like the product photos)
    im = bpy.data.images.load(raw)
    px = np.array(im.pixels[:], np.float32).reshape(-1, 4)
    # shadow-catcher pixels (black, partial alpha) carry a ~20% haze over the whole floor;
    # keep only the contact shadow under the pod
    shadow = px[:, :3].max(1) < 0.03
    px[shadow, 3] = np.clip((px[shadow, 3] - 0.3) / 0.7, 0, 1)
    rgb = px[:, :3] * px[:, 3:4] + BG * (1 - px[:, 3:4])
    out = bpy.data.images.new(name, im.size[0], im.size[1], alpha=False)
    out.pixels.foreach_set(np.concatenate([rgb, np.ones_like(px[:, :1])], 1).ravel())
    out.filepath_raw, out.file_format = os.path.join(OUT, f'{name}{TAG}.png'), 'PNG'
    out.save()
    if not os.environ.get('KEEP'):
        os.remove(raw)
    print('rendered', name)
