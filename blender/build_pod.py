"""Soundbox 4-person pod, built in Blender.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P blender/build_pod.py

Writes blender/soundbox4.blend (open it in Blender to edit by hand) and ../pod.glb.
Size follows the published spec for the 4-person pod (outer W220 x D153.6 x H230 cm,
inner W204 x D150 x H214 cm); details follow the product photos on sb.contex.com.hk.
Stylised illustration, not a product scan.

Blender is Z-up, metres; the pod's front faces -Y (glTF export turns that into +Z).
Contract with pod.js: empties PartShell / PartFront / PartBack / Furniture under Soundbox4,
a 'Door' empty on the hinge axis, and the material names pod.js swaps (Shell, Trim, Glass, ...).
"""
import bpy, bmesh, json, math, os
from collections import defaultdict
import numpy as np
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

bpy.ops.wm.read_factory_settings(use_empty=True)
SCENE = bpy.context.scene
COL = bpy.data.collections.new('Soundbox4')
SCENE.collection.children.link(COL)

# ---------------------------------------------------------------- dimensions
# POD_SIZE picks the model (outer W x D x H in metres, from sb.contex.com.hk); 4 is the default.
SIZE = os.environ.get('POD_SIZE', '4')
SPEC = {'1': (1.00, 0.936, 2.30), '2': (1.50, 1.236, 2.30), '4': (2.20, 1.536, 2.30),
        '6': (2.20, 2.136, 2.30), '8': (3.00, 4.236, 2.346)}
W, D, H = SPEC[SIZE]
GAP, T, R = 0.008, 0.08, 0.11          # floor gap, shell wall, outer corner radius
YF, YB = -D / 2, D / 2
ZC, HA, HB = (GAP + H) / 2, W / 2, (H - GAP) / 2
IX, FLOOR, CEIL = HA - T, GAP + T, H - T   # 1.02, 0.088, 2.22 for the 4-person pod
GW = 0.035                                 # black gasket width
OX = IX - GW                               # half-width of the glass opening
IW = IX - 0.02                             # felt wall surface
YI0, YI1 = YF + 0.056, YB - 0.076          # inside of the front frame / back panel face
# door: free edge XF, hinge axis XH (pod.js / viewer swing 'Door' about this axis)
XF, XH = {'1': (-OX + 0.012, OX - 0.003), '2': (-0.38, 0.40), '4': (-0.462, 0.32),
          '6': (-0.462, 0.32), '8': (-0.56, 0.26)}[SIZE]
PIVOT = Vector((XH, YF + 0.023, ZC))
ZERO = Vector()

# ---------------------------------------------------------------- materials
def lin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [1.0]

# ---------------------------------------------------------------- textures
# Tileable textile textures generated here (FFT-filtered noise + a plain-weave pattern),
# packed into the .blend and embedded in the GLB. Colour is baked in; pod.js keeps these maps.
N = 512
_fy, _fx = np.meshgrid(np.fft.fftfreq(N) * N, np.fft.fftfreq(N) * N, indexing='ij')

def band(seed, f0, f1, ax=1.0, ay=1.0):
    """Periodic band-limited noise (cycles per tile f0..f1), unit std; ax/ay stretch it."""
    F = np.fft.fft2(np.random.default_rng(seed).standard_normal((N, N)))
    r = np.hypot(_fx * ax, _fy * ay)
    out = np.real(np.fft.ifft2(F * np.exp(-(r / f1) ** 2) * (1 - np.exp(-(r / f0) ** 2))))
    return out / (out.std() + 1e-9)

def image(name, rgb, colour=True):
    img = bpy.data.images.new(name, N, N, alpha=False)
    img.colorspace_settings.name = 'sRGB' if colour else 'Non-Color'
    img.pixels.foreach_set(np.concatenate([rgb, np.ones((N, N, 1))], axis=2).astype(np.float32).ravel())
    img.pack()
    return img

def yarn(name, lo, hi, t):
    lo, hi = (np.array([int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]) for h in (lo, hi))
    return image(name, lo + (hi - lo) * np.clip(t, 0, 1)[..., None])

def normals(name, h, slope):
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    k = slope / (np.hypot(dx, dy).mean() + 1e-9)
    n = np.dstack((-dx * k, -dy * k, np.ones_like(h)))
    return image(name, n / np.linalg.norm(n, axis=2, keepdims=True) * 0.5 + 0.5, colour=False)

fib = band(2, 60, 200)
TEX_FELT = yarn('felt', '#18191c', '#45484d', 0.3 + 0.06 * band(1, 1.5, 10) + 0.06 * fib + 0.3 * (band(3, 120, 256) > 2.3))
NRM_FELT = normals('felt_n', fib + 0.5 * band(4, 15, 60), 0.18)
X, Y = np.meshgrid(np.arange(N), np.arange(N))
P = 8                                                     # plain weave, 64 threads per tile
cx, cy = np.cos(np.pi * ((X % P) / P - 0.5)), np.cos(np.pi * ((Y % P) / P - 0.5))
over = ((X // P + Y // P) % 2).astype(float)
weave = over * (cx + 0.35 * cy) + (1 - over) * (cy + 0.35 * cx)
melange = 0.5 + 0.1 * (band(5, 4, 40, 1, 6) + band(6, 4, 40, 6, 1)) + 0.1 * (weave - weave.mean()) + 0.15 * (band(7, 100, 256) > 2.0)
TEX_FAB_LIGHT = yarn('fabric_light', '#4f5156', '#8a8c91', melange)
TEX_FAB_DARK = yarn('fabric_dark', '#2a2c30', '#55575c', melange)
NRM_FAB = normals('fabric_n', weave + 0.25 * band(8, 60, 256), 0.35)
TEX_CARPET = yarn('carpet', '#1c1e22', '#4c4f55', 0.38 + 0.08 * band(9, 2, 16) + 0.12 * band(10, 80, 256) + 0.35 * (band(11, 150, 256) > 2.1))
# back wall: fine linen-look board under a glossy glass-like coat (the product photos show a reflective back panel)
linen = 0.5 + 0.18 * (band(12, 30, 160, 1, 8) + band(13, 30, 160, 8, 1)) + 0.1 * band(14, 1, 6)
TEX_BACK = yarn('back_panel', '#b4b5b3', '#d6d7d4', linen)
NRM_BACK = normals('back_panel_n', band(12, 30, 160, 1, 8) + band(13, 30, 160, 8, 1), 0.06)
TILE = {'Felt': 0.5, 'Carpet': 0.35, 'Fabric': 0.15, 'FabricBase': 0.15, 'BackPanel': 0.4}   # metres per texture repeat

MAT = {}
def material(name, hexc, rough=0.5, metal=0.0, emit=0.0, transmission=0.0, coat=0.0, tex=None, nrm=None):
    m = bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    nt = m.node_tree
    b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if b is None:
        b = nt.nodes.new('ShaderNodeBsdfPrincipled')
        out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
        nt.links.new(b.outputs[0], out.inputs[0])
    vals = {'Base Color': lin(hexc), 'Roughness': rough, 'Metallic': metal,
            'Transmission Weight': transmission, 'Coat Weight': coat}
    if emit:
        vals.update({'Emission Color': lin(hexc), 'Emission Strength': emit})
    for k, v in vals.items():
        if k in b.inputs:
            b.inputs[k].default_value = v
    if tex:
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = tex
        nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
    if nrm:
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = nrm
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nt.links.new(t.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    m.diffuse_color = lin(hexc)
    m.roughness = rough
    MAT[name] = m

# names pod.js swaps for its own materials (keep them in sync)
material('Shell', '#ecebe6', 0.32, coat=0.6)
material('Trim', '#111214', 0.45, 0.2)
material('Rubber', '#0c0d0f', 0.9)
material('Seam', '#1a1b1e', 0.7)
material('Glass', '#e4ecf7', 0.02, transmission=1.0)
material('Felt', '#3a3c41', 1.0, tex=TEX_FELT, nrm=NRM_FELT)
material('BackPanel', '#c4c5c2', 0.35, coat=1.0, tex=TEX_BACK, nrm=NRM_BACK)
material('Carpet', '#26282d', 1.0, tex=TEX_CARPET, nrm=NRM_FELT)
material('Fabric', '#8b8d93', 0.95, tex=TEX_FAB_LIGHT, nrm=NRM_FAB)
material('FabricBase', '#45474d', 0.9, tex=TEX_FAB_DARK, nrm=NRM_FAB)
material('Desk', '#f1f1ee', 0.3)
material('Wood', '#c9a77a', 0.55)
material('Plate', '#ececea', 0.4)
material('LightPanel', '#fff2dc', 0.5, emit=4.0)
material('Screen', '#2b6fe0', 0.2, emit=1.0)
material('Icon', '#f2f2f2', 0.5, emit=1.0)
# exported as-is (pod.js leaves these alone)
material('Red', '#c8102e', 0.35)
material('Steel', '#1c1d20', 0.35, 0.8)
material('Lens', '#05060a', 0.08, 0.2)
material('Green', '#36d07a', 0.4, emit=1.5)
material('Chrome', '#cfd3d6', 0.18, 1.0)
material('Logo', '#262c30', 0.5)   # pod.js flips it to white on dark shells

# ---------------------------------------------------------------- mesh helpers
def rrect(a, b, r, seg):
    """Rounded rectangle, half extents a x b, corner radius r -> CCW (u, v) points."""
    r = max(1e-4, min(r, a, b))
    pts = []
    for cu, cv, start in ((a - r, -(b - r), -90), (a - r, b - r, 0), (-(a - r), b - r, 90), (-(a - r), -(b - r), 180)):
        for i in range(seg + 1):
            t = math.radians(start + 90 * i / seg)
            pts.append((cu + r * math.cos(t), cv + r * math.sin(t)))
    return pts

def arc(cs, cd, r, a0, a1, n):
    return [(cs + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cd + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]

class Prof:
    """2D profile (s = inset from the outer rounded rect, d = depth); the segment leaving a point uses its material."""
    def __init__(self):
        self.p = []
    def add(self, pts, m=0):
        for s, d in pts:
            if self.p and abs(self.p[-1][0] - s) < 1e-9 and abs(self.p[-1][1] - d) < 1e-9:
                self.p[-1] = (s, d, m)
            else:
                self.p.append((s, d, m))
        return self

def place(plane, u, v, d):
    return {'XZ': (u, d, v), 'XY': (u, v, d), 'YZ': (d, u, v)}[plane]

def loft(prof, a, b, r, seg=12, plane='XZ', uc=0.0, vc=0.0, closed=True, caps=None, rmin=0.004):
    """Sweep a rounded rectangle through a profile: shells, rings and rounded slabs."""
    bm = bmesh.new()
    loops = []
    for s, d, _ in prof:
        loops.append([bm.verts.new(place(plane, uc + u, vc + v, d)) for u, v in rrect(a - s, b - s, max(r - s, rmin), seg)])
    n, L = len(loops[0]), len(loops)
    for i in range(L if closed else L - 1):
        A, B = loops[i], loops[(i + 1) % L]
        for j in range(n):
            bm.faces.new((A[j], A[(j + 1) % n], B[(j + 1) % n], B[j])).material_index = prof[i][2]
    if caps:
        bm.faces.new(loops[0]).material_index = caps[0]
        bm.faces.new(loops[-1]).material_index = caps[1]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm

def slab(a, b, r, d0, d1, bev=0.0, plane='XZ', uc=0.0, vc=0.0, seg=8, n=3, side=0, cap0=0, cap1=0):
    """Rounded-rect plate between depths d0..d1 with rounded rims."""
    pr = Prof()
    if bev > 0:
        pr.add(arc(bev, d0 + bev, bev, 270, 180, n), side).add(arc(bev, d1 - bev, bev, 180, 90, n), side)
    else:
        pr.add([(0, d0), (0, d1)], side)
    return loft(pr.p, a, b, r, seg, plane, uc, vc, closed=False, caps=(cap0, cap1))

FACES8 = (((0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)), ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)),
          ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)), ((0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)),
          ((0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)), ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)))

def hexa(c, bev=0.0, seg=3):
    """Any 8-corner block; c[(i, j, k)] -> xyz. Optional rounded edges."""
    bm = bmesh.new()
    vs = {k: bm.verts.new(v) for k, v in c.items()}
    for f in FACES8:
        bm.faces.new([vs[k] for k in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bev:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bev, segments=seg, profile=0.5, affect='EDGES', clamp_overlap=True)
    return bm

def box(x0, x1, y0, y1, z0, z1, bev=0.0, seg=3):
    return hexa({(i, j, k): ((x0, x1)[i], (y0, y1)[j], (z0, z1)[k]) for i in (0, 1) for j in (0, 1) for k in (0, 1)}, bev, seg)

def bevel_sharp(bm, off, seg=2, ang=50):
    es = [e for e in bm.edges if e.is_manifold and e.calc_face_angle(0) > math.radians(ang)]
    if es:
        bmesh.ops.bevel(bm, geom=es, offset=off, segments=seg, profile=0.5, affect='EDGES', clamp_overlap=True)
    return bm

def cyl(p0, p1, r, n=32, bev=0.0, seg=2, r1=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=n, radius1=r, radius2=r if r1 is None else r1, depth=1.0)
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    for v in bm.verts:
        v.co.z = (v.co.z + 0.5) * d.length
    rot = d.normalized().to_track_quat('Z', 'Y').to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=Matrix.Translation(p0) @ rot, verts=bm.verts)
    return bevel_sharp(bm, bev, seg) if bev else bm

def sphere(c, r, n=16, m=10, half=False):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=n, v_segments=m, radius=r)
    if half:   # keep the lower half (a dome hanging from a ceiling)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > 1e-5], context='VERTS')
        bm.faces.new([v for v in sorted((v for v in bm.verts if abs(v.co.z) < 1e-5),
                                        key=lambda v: math.atan2(v.co.y, v.co.x))])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.translate(bm, vec=Vector(c), verts=bm.verts)
    return bm

def torus(c, axis, R_, r, n=40, m=8):
    bm = bmesh.new()
    rings = []
    for i in range(n):
        a = 2 * math.pi * i / n
        rings.append([bm.verts.new(((R_ + r * math.cos(2 * math.pi * j / m)) * math.cos(a),
                                    (R_ + r * math.cos(2 * math.pi * j / m)) * math.sin(a),
                                    r * math.sin(2 * math.pi * j / m))) for j in range(m)])
    for i in range(n):
        A, B = rings[i], rings[(i + 1) % n]
        for j in range(m):
            bm.faces.new((A[j], A[(j + 1) % m], B[(j + 1) % m], B[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    rot = Vector(axis).normalized().to_track_quat('Z', 'Y').to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=Matrix.Translation(c) @ rot, verts=bm.verts)
    return bm

def fillet(pts, rad, n=6):
    pts = [Vector(p) for p in pts]
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        d1, d2 = (a - b).normalized(), (c - b).normalized()
        ang = d1.angle(d2)
        center = b + (d1 + d2).normalized() * (rad / math.sin(ang / 2))
        v1 = b + d1 * (rad / math.tan(ang / 2)) - center
        v2 = b + d2 * (rad / math.tan(ang / 2)) - center
        axis, tot = v1.cross(v2).normalized(), v1.angle(v2)
        out += [center + Matrix.Rotation(tot * k / n, 3, axis) @ v1 for k in range(n + 1)]
    return out + [pts[-1]]

def sweep(pts, r, n=16):
    """Round tube along a polyline (parallel-transport frames), capped."""
    pts = [Vector(p) for p in pts]
    Ts = []
    for i in range(len(pts)):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)])
        Ts.append(t.normalized())
    up = Vector((0, 0, 1)) if abs(Ts[0].z) < 0.9 else Vector((1, 0, 0))
    N = Ts[0].cross(up).normalized()
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(pts):
        if i:
            ax = Ts[i - 1].cross(Ts[i])
            if ax.length > 1e-8:
                N = Matrix.Rotation(Ts[i - 1].angle(Ts[i]), 3, ax.normalized()) @ N
        B = Ts[i].cross(N)
        rings.append([bm.verts.new(p + r * (math.cos(2 * math.pi * k / n) * N + math.sin(2 * math.pi * k / n) * B)) for k in range(n)])
    for A, Bv in zip(rings, rings[1:]):
        for k in range(n):
            bm.faces.new((A[k], A[(k + 1) % n], Bv[(k + 1) % n], Bv[k]))
    bm.faces.new(rings[0])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm

def flat(polys, y):
    """Flat glyph polygons on the plane y, facing the front (-Y)."""
    bm = bmesh.new()
    for poly in polys:
        f = bm.faces.new([bm.verts.new((x, y, z)) for x, z in poly])
        f.normal_update()
        if f.normal.y > 0:
            f.normal_flip()
    return bm

def ring2d(cx, cz, r0, r1, n=32, a0=0.0, a1=360.0):
    quads = []
    for i in range(n):
        t0, t1 = math.radians(a0 + (a1 - a0) * i / n), math.radians(a0 + (a1 - a0) * (i + 1) / n)
        quads.append([(cx + r0 * math.cos(t0), cz + r0 * math.sin(t0)), (cx + r1 * math.cos(t0), cz + r1 * math.sin(t0)),
                      (cx + r1 * math.cos(t1), cz + r1 * math.sin(t1)), (cx + r0 * math.cos(t1), cz + r0 * math.sin(t1))])
    return quads

def disc2d(cx, cz, rx, rz=None, n=20, rot=0.0):
    rz = rx if rz is None else rz
    c, s = math.cos(rot), math.sin(rot)
    return [(cx + rx * math.cos(t) * c - rz * math.sin(t) * s, cz + rx * math.cos(t) * s + rz * math.sin(t) * c)
            for t in (2 * math.pi * i / n for i in range(n))]

def rect2d(cx, cz, w, h, rot=0.0):
    c, s = math.cos(rot), math.sin(rot)
    return [(cx + x * c - z * s, cz + x * s + z * c) for x, z in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]

def text(body, size, x, y, z, font=None):
    cu = bpy.data.curves.new('txt', 'FONT')
    cu.body, cu.size = body, size
    if font and os.path.exists(font):
        cu.font = bpy.data.fonts.load(font, check_existing=True)
    tmp = bpy.data.objects.new('txt', cu)
    SCENE.collection.objects.link(tmp)
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bm = bmesh.new()
    bm.from_mesh(me)
    bpy.data.objects.remove(tmp)
    bpy.data.meshes.remove(me)
    bmesh.ops.transform(bm, matrix=Matrix.Translation((x, y, z)) @ Matrix.Rotation(math.radians(90), 4, 'X'), verts=bm.verts)
    bm.normal_update()
    for f in bm.faces:
        if f.normal.y > 0:
            f.normal_flip()
    return bm

def merge(*parts):
    """Join several bmeshes; parts may be (bm, material_index) pairs."""
    out = bmesh.new()
    for p in parts:
        bm, mi = p if isinstance(p, tuple) else (p, 0)
        for f in bm.faces:
            f.material_index = mi if isinstance(p, tuple) else f.material_index
        me = bpy.data.meshes.new('tmp')
        bm.to_mesh(me)
        bm.free()
        out.from_mesh(me)
        bpy.data.meshes.remove(me)
    return out

def empty(name, parent=None, loc=ZERO):
    e = bpy.data.objects.new(name, None)
    e.location, e.parent, e.empty_display_size = loc, parent, 0.25
    COL.objects.link(e)
    return e

def obj(name, bm, mats, parent, origin=ZERO, smooth=True, sharp=50):
    mats = [mats] if isinstance(mats, str) else mats
    for f in bm.faces:
        f.smooth = smooth
    for e in bm.edges:
        e.smooth = (not e.is_manifold) or e.calc_face_angle(0) < math.radians(sharp)
    if any(m in TILE for m in mats):          # box-projected UVs in metres / repeat size
        bm.normal_update()
        uvl = bm.loops.layers.uv.new('UVMap')
        for f in bm.faces:
            tile = TILE.get(mats[f.material_index], 1.0)
            ax = max(range(3), key=lambda i: abs(f.normal[i]))
            for l in f.loops:
                c = l.vert.co
                u, v = ((c.y, c.z), (c.x, c.z), (c.x, c.y))[ax]
                l[uvl].uv = (u / tile, v / tile)
    if origin != ZERO:
        bmesh.ops.translate(bm, vec=-origin, verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(MAT[m])
    ob = bpy.data.objects.new(name, me)
    ob.parent = parent
    COL.objects.link(ob)
    if smooth:
        wn = ob.modifiers.new('WeightedNormal', 'WEIGHTED_NORMAL')
        wn.keep_sharp, wn.mode = True, 'FACE_AREA'
    return ob

# ---------------------------------------------------------------- hierarchy
ROOT = empty('Soundbox4')
SHELL, FRONT, BACK, FURN = (empty(n, ROOT) for n in ('PartShell', 'PartFront', 'PartBack', 'Furniture'))
DOOR = empty('Door', FRONT, PIVOT)

# ================================================================ SHELL
# One continuous rounded tube (sides + roof + floor) with rounded lips and
# two dark seams where the front/back frames meet the side panels.
bo, bi, gd, gw2 = 0.016, 0.005, 0.003, 0.0025
G1, G2 = YF + 0.075, YB - 0.075
pr = Prof()
pr.add(arc(bo, YB - bo, bo, 90, 180, 4), 0)
pr.add([(0, G2 + gw2)], 1).add([(gd, G2 + gw2), (gd, G2 - gw2)], 1).add([(0, G2 - gw2)], 0)
pr.add([(0, G1 + gw2)], 1).add([(gd, G1 + gw2), (gd, G1 - gw2)], 1).add([(0, G1 - gw2)], 0)
pr.add(arc(bo, YF + bo, bo, 180, 270, 4), 0)
pr.add(arc(T - bi, YF + bi, bi, 270, 360, 2), 0)
pr.add(arc(T - bi, YB - bi, bi, 0, 90, 2), 0)
obj('ShellTube', loft(pr.p, HA, HB, R, seg=14, vc=ZC), ['Shell', 'Seam'], SHELL)

# fresh-air intake slots on the right side, just behind the front frame
obj('SideVents', merge(*[box(HA - 0.004, HA + 0.0006, YF + 0.123, YF + 0.134, z - 0.018, z + 0.018, 0.003, 2)
                         for z in (1.82, 1.87, 1.92, 1.97, 2.02)]), 'Seam', SHELL)

# Contex logo on both side panels: traced from blender/contex_logo.png (marching squares),
# filled as a 2D curve, extruded 1.6 mm proud of the panel.
def trace(path, width, eps=0.2):
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)   # rows run bottom -> top
    bpy.data.images.remove(img)
    ink = (1 - (0.2126 * px[..., 0] + 0.7152 * px[..., 1] + 0.0722 * px[..., 2])) * px[..., 3]
    lo, hi = np.percentile(ink, 5), np.percentile(ink, 99.5)
    m = np.pad(np.clip((ink - lo) / (hi - lo), 0, 1), 1)
    pts, adj = {}, defaultdict(list)
    def edge(kind, i, j):
        k = (kind, i, j)
        if k not in pts:
            a, b = (m[i, j], m[i, j + 1]) if kind == 'h' else (m[i, j], m[i + 1, j])
            t = (0.5 - a) / (b - a)
            pts[k] = (j + t, i) if kind == 'h' else (j, i + t)
        return k
    for i in range(m.shape[0] - 1):
        for j in range(m.shape[1] - 1):
            tl, tr, br, bl = m[i, j] > 0.5, m[i, j + 1] > 0.5, m[i + 1, j + 1] > 0.5, m[i + 1, j] > 0.5
            cut = [k for k, c in ((('h', i, j), tl != tr), (('v', i, j + 1), tr != br),
                                  (('h', i + 1, j), br != bl), (('v', i, j), bl != tl)) if c]
            if len(cut) == 2:
                pairs = [cut]
            elif len(cut) == 4:   # saddle: decide by the cell centre
                top, right, bottom, left = cut
                centre = m[i:i + 2, j:j + 2].mean() > 0.5
                pairs = [(top, right), (bottom, left)] if centre == tl else [(left, top), (right, bottom)]
            else:
                continue
            for a, b in pairs:
                a, b = edge(*a), edge(*b)
                adj[a].append(b)
                adj[b].append(a)
    def rdp(p):
        if len(p) < 3:
            return p
        a, b = np.array(p[0]), np.array(p[-1])
        q = np.array(p[1:-1])
        ab = b - a
        d = np.abs(ab[0] * (q[:, 1] - a[1]) - ab[1] * (q[:, 0] - a[0])) / max(np.hypot(*ab), 1e-9)
        i = int(np.argmax(d))
        return rdp(p[:i + 2])[:-1] + rdp(p[i + 1:]) if d[i] > eps else [p[0], p[-1]]
    loops, seen = [], set()
    for start in adj:
        if start in seen:
            continue
        loop, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nb = adj[cur]
            nxt = nb[0] if nb[0] != prev else nb[1]
            if nxt == start or nxt in seen:
                break
            loop.append(nxt)
            seen.add(nxt)
            prev, cur = cur, nxt
        p = [pts[k] for k in loop]
        if abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(p, p[1:] + p[:1]))) > 8:   # drop specks
            half = len(p) // 2
            loops.append(rdp(p[:half + 1])[:-1] + rdp(p[half:] + p[:1])[:-1])
    allp = np.array([q for lp in loops for q in lp])
    (x0, y0), (x1, y1) = allp.min(0), allp.max(0)
    s = width / (x1 - x0)
    return [[((x - (x0 + x1) / 2) * s, (y - (y0 + y1) / 2) * s) for x, y in lp] for lp in loops], (y1 - y0) * s

LOGO_LOOPS, LOGO_H = trace(os.path.join(HERE, 'contex_logo.png'), 0.72)
os.makedirs(os.path.join(REPO, 'v2'), exist_ok=True)   # same outline as an SVG for the web page
with open(os.path.join(REPO, 'v2', 'contex.svg'), 'w') as fh:
    k = 1000
    d = ''.join('M' + 'L'.join(f'{(x + 0.36) * k:.1f},{(LOGO_H / 2 - y) * k:.1f}' for x, y in lp) + 'Z' for lp in LOGO_LOOPS)
    fh.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {0.72 * k:.0f} {LOGO_H * k:.0f}"><path fill-rule="evenodd" fill="currentColor" d="{d}"/></svg>')
cu = bpy.data.curves.new('ContexLogo', 'CURVE')
cu.dimensions, cu.fill_mode, cu.extrude = '2D', 'BOTH', 0.0008
for lp in LOGO_LOOPS:
    sp = cu.splines.new('POLY')
    sp.points.add(len(lp) - 1)
    for pt, (x, y) in zip(sp.points, lp):
        pt.co = (x, y, 0, 1)
    sp.use_cyclic_u = True
tmp = bpy.data.objects.new('tmp', cu)
SCENE.collection.objects.link(tmp)
bpy.context.view_layer.update()
logo_me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
bpy.data.objects.remove(tmp)
LZ = 1.55                                   # logo centre height on the side panels
LS = min(1.0, 0.75 * (D - 0.15) / 0.72)     # shrink on narrow side panels (1-person pod)
for name, mtx in (('ContexLogoR', Matrix(((0, 0, 1, HA + 0.0002), (LS, 0, 0, 0), (0, LS, 0, LZ), (0, 0, 0, 1)))),
                  ('ContexLogoL', Matrix(((0, 0, -1, -HA - 0.0002), (-LS, 0, 0, 0), (0, LS, 0, LZ), (0, 0, 0, 1))))):
    bm = bmesh.new()
    bm.from_mesh(logo_me)
    bmesh.ops.transform(bm, matrix=mtx, verts=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj(name, bm, 'Logo', SHELL, smooth=False)
bpy.data.meshes.remove(logo_me)

# damping feet (8 mm floor gap); extra pair along the long 8-person pod
feet = []
for sx in (-1, 1):
    for cy in ((-1, 0, 1) if D > 3 else (-1, 1)):
        cx, cy = sx * (HA - 0.145), cy * (D / 2 - 0.138)
        feet += [(cyl((cx, cy, 0), (cx, cy, 0.0035), 0.03, 24), 1),
                 (box(cx - 0.036, cx + 0.036, cy - 0.036, cy + 0.036, 0.003, 0.0125, 0.004, 2), 0)]
obj('Feet', merge(*feet), ['Shell', 'Rubber'], SHELL)

# interior lining
obj('Carpet', box(-IW, IW, YI0, YI1, FLOOR, 0.1, 0.002, 1), 'Carpet', SHELL)
obj('FeltLeft', box(-IX, -IW, YF + 0.068, YI1, FLOOR + 0.012, CEIL - 0.03, 0.004, 2), 'Felt', SHELL)
obj('FeltRight', box(IW, IX, YF + 0.068, YI1, FLOOR + 0.012, CEIL - 0.03, 0.004, 2), 'Felt', SHELL)
obj('Ceiling', box(-IW, IW, YF + 0.088, YI1, CEIL - 0.03, CEIL - 0.002, 0.004, 2), 'Felt', SHELL)

# front header band behind the glass with the four touch controls
obj('ControlPanel', box(-IW, IW, YI0, YF + 0.088, CEIL - 0.115, CEIL - 0.015, 0.004, 2), 'Trim', SHELL)
ICON_Y, ICON_Z = YF + 0.0554, CEIL - 0.068
icons = []
for i, x in enumerate(OX - d for d in (0.265, 0.21, 0.155, 0.10)):
    g = ring2d(x, ICON_Z, 0.0145, 0.0165)
    if i in (0, 1):    # fresh-air fan / exhaust fan
        nb = 3 if i == 0 else 4
        g += [disc2d(x + 0.006 * math.cos(a), ICON_Z + 0.006 * math.sin(a), 0.0055, 0.0026, 14, a + 0.5)
              for a in (2 * math.pi * k / nb + 0.3 for k in range(nb))]
        g.append(disc2d(x, ICON_Z, 0.0016, n=10))
    elif i == 2:       # light
        g.append(disc2d(x, ICON_Z, 0.0042, n=16))
        g += [rect2d(x + 0.0085 * math.cos(a), ICON_Z + 0.0085 * math.sin(a), 0.003, 0.0011, a) for a in (k * math.pi / 4 for k in range(8))]
    else:              # power
        g += ring2d(x, ICON_Z - 0.0005, 0.0062, 0.0078, 18, 120, 420)
        g.append(rect2d(x, ICON_Z + 0.0045, 0.0016, 0.0075))
    icons.append(flat(g, ICON_Y))
for i, bm in enumerate(icons):
    obj(f'Icon{i}', bm, 'Icon', SHELL, smooth=False)

# PIR presence sensor under the header
obj('PirSensor', sphere((0.0, YF + 0.078, CEIL - 0.115), 0.016, 16, 8, half=True), 'Trim', SHELL)

# lighting: linear pendants (4000K), one per ~1.5 m of depth, + LED strips along both side walls
nbar = max(1, round((YI1 - YI0) / 1.5))
bars = [(YI0 + YI1) / 2 + 0.06] if nbar == 1 else [YI0 + (i + 0.5) * (YI1 - YI0) / nbar for i in range(nbar)]
lb = min(0.32, 0.62 * IW)
hous, diff = [], []
for yc in bars:
    hous += [box(-lb, lb, yc - 0.03, yc + 0.03, CEIL - 0.125, CEIL - 0.095, 0.008, 3)]
    for rx in (-lb + 0.06, lb - 0.06):
        hous += [cyl((rx, yc, CEIL - 0.095), (rx, yc, CEIL - 0.03), 0.0025, 8),
                 cyl((rx, yc, CEIL - 0.036), (rx, yc, CEIL - 0.03), 0.02, 20, 0.002)]
    diff.append(box(-lb + 0.01, lb - 0.01, yc - 0.022, yc + 0.022, CEIL - 0.1265, CEIL - 0.1245))
obj('LedBarHousing', merge(*hous), 'Trim', SHELL)
obj('LedBar', merge(*diff), 'LightPanel', SHELL, smooth=False)
for side, sx in (('', -1), ('R', 1)):
    hx = sorted((sx * IW, sx * (IW - 0.042)))
    obj(f'LedEdgeHousing{side}', box(hx[0], hx[1], YF + 0.088, YB - 0.078, CEIL - 0.055, CEIL - 0.03, 0.003, 2), 'Trim', SHELL)
    lx = sorted((sx * (IW - 0.005), sx * (IW - 0.037)))
    obj(f'LedEdge{side}', box(lx[0], lx[1], YF + 0.093, YB - 0.083, CEIL - 0.0565, CEIL - 0.0545), 'LightPanel', SHELL, smooth=False)

# fresh-air grilles in the ceiling
grilles = []
gxs = (0.0,) if IW < 0.6 else (-0.55 * IW, 0.55 * IW)
for gy in ((YB - 0.39, YF + 1.2) if D > 3 else (YB - (0.39 if D > 1.2 else 0.2),)):
    for gx in gxs:
        grilles.append((cyl((gx, gy, CEIL - 0.035), (gx, gy, CEIL - 0.03), 0.08, 40, 0.002), 0))
        grilles += [(torus(Vector((gx, gy, CEIL - 0.0355)), (0, 0, 1), rr, 0.0022, 40, 6), 1) for rr in (0.022, 0.038, 0.054, 0.068)]
obj('AirGrilles', merge(*grilles), ['Plate', 'Seam'], SHELL)

# emergency hammer on the right wall, by the door
obj('HammerHolder', merge(box(IW - 0.012, IW, YF + 0.103, YF + 0.143, CEIL - 0.28, CEIL - 0.14, 0.004, 2),
                          box(IW - 0.042, IW - 0.01, YF + 0.113, YF + 0.133, CEIL - 0.265, CEIL - 0.25, 0.002, 1),
                          box(IW - 0.042, IW - 0.01, YF + 0.113, YF + 0.133, CEIL - 0.185, CEIL - 0.17, 0.002, 1)), 'Trim', SHELL)
obj('Hammer', merge(cyl((IW - 0.028, YF + 0.123, CEIL - 0.295), (IW - 0.028, YF + 0.123, CEIL - 0.16), 0.0115, 20, 0.003),
                    box(IW - 0.039, IW - 0.017, YF + 0.078, YF + 0.168, CEIL - 0.165, CEIL - 0.134, 0.004, 2)), 'Red', SHELL)
obj('HammerTips', merge(cyl((IW - 0.028, YF + 0.078, CEIL - 0.1495), (IW - 0.028, YF + 0.06, CEIL - 0.1495), 0.012, 16, r1=0.002),
                        cyl((IW - 0.028, YF + 0.168, CEIL - 0.1495), (IW - 0.028, YF + 0.186, CEIL - 0.1495), 0.012, 16, r1=0.002)), 'Steel', SHELL)

# light / fan switch on the left wall, by the door
obj('WallSwitch', box(-IW, -IW + 0.01, YF + 0.113, YF + 0.173, 1.22, 1.34, 0.004, 2), 'Trim', SHELL)
obj('WallSwitchKeys', merge(cyl((-IW + 0.01, YF + 0.143, 1.305), (-IW + 0.0135, YF + 0.143, 1.305), 0.011, 24, 0.001),
                            cyl((-IW + 0.01, YF + 0.143, 1.255), (-IW + 0.0135, YF + 0.143, 1.255), 0.011, 24, 0.001)), 'Plate', SHELL)

# ================================================================ FRONT
gpr = Prof()
s0, s1, gy0, gy1, bg = T - 0.002, T + GW, YF + 0.007, YI0, 0.006
gpr.add([(s0, gy1), (s0, gy0), (s1 - bg, gy0)]).add(arc(s1 - bg, gy0 + bg, bg, 270, 360, 3)).add([(s1, gy1)])
obj('Gasket', loft(gpr.p, HA, HB, R, seg=14, vc=ZC, rmin=0.022), 'Trim', FRONT)

GZ0, GZ1 = FLOOR + 0.022, CEIL - 0.022          # glass runs into the gasket
GY0, GY1 = YF + 0.028, YF + 0.038
if XF - 0.02 > -OX + 0.05:   # fixed glass + mullion left of the door
    obj('GlassLeft', box(-IW, XF - 0.02, GY0, GY1, GZ0, GZ1), 'Glass', FRONT, smooth=False)
    obj('MullionFree', box(XF - 0.033, XF - 0.007, YF + 0.016, YF + 0.05, FLOOR + 0.027, CEIL - 0.027, 0.006, 3), 'Trim', FRONT)
if XH + 0.025 < OX - 0.05:   # fixed glass + mullion right of the hinge
    obj('GlassRight', box(XH + 0.012, IW, GY0, GY1, GZ0, GZ1), 'Glass', FRONT, smooth=False)
    obj('MullionHinge', box(XH - 0.001, XH + 0.025, YF + 0.016, YF + 0.05, FLOOR + 0.027, CEIL - 0.027, 0.006, 3), 'Trim', FRONT)
HZ1, HZ0 = (CEIL - 0.29, CEIL - 0.19), (FLOOR + 0.212, FLOOR + 0.312)
obj('HingeFixed', merge(*[box(XH + 0.0015, XH + 0.05, YF + 0.002, YF + 0.044, z0, z1, 0.009, 3) for z0, z1 in (HZ1, HZ0)]), 'Trim', FRONT)

# floor edge seen through the glass, with the badge
obj('Threshold', box(-OX, OX, YF + 0.052, YF + 0.068, FLOOR, FLOOR + 0.08, 0.003, 2), 'Trim', FRONT)
FONT = '/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf'
BY = YF + 0.0514
obj('Logo', merge(text('soundbox', 0.03, -OX + 0.05, BY, 0.13, FONT),
                  text('Movable Silence Booth', 0.0095, -OX + 0.19, BY, 0.131, FONT),
                  flat([disc2d(-OX + 0.037, 0.1385, 0.0075, 0.0058, 16)], BY)), 'Icon', FRONT, smooth=False)

# door: frameless glass leaf hinged at XH
P = PIVOT
DY0, DY1 = YF + 0.018, YF + 0.028
DZ_0, DZ_1 = FLOOR + 0.042, CEIL - 0.042
obj('DoorGlass', box(XF, XH - 0.008, DY0, DY1, DZ_0, DZ_1), 'Glass', DOOR, P, smooth=False)
obj('DoorEdgeFree', box(XF - 0.006, XF + 0.007, YF + 0.013, YF + 0.033, DZ_0, DZ_1, 0.003, 2), 'Trim', DOOR, P)
obj('DoorSeal', merge(box(XH - 0.008, XH - 0.002, YF + 0.019, YF + 0.027, DZ_0 + 0.01, DZ_1 - 0.008, 0.002, 1),
                      box(XF + 0.007, XH - 0.008, YF + 0.019, YF + 0.027, DZ_1, DZ_1 + 0.007, 0.002, 1),
                      box(XF + 0.007, XH - 0.008, YF + 0.019, YF + 0.027, DZ_0 - 0.007, DZ_0, 0.002, 1)), 'Rubber', DOOR, P)
obj('HingeDoor', merge(*[box(XH - 0.05, XH - 0.0015, YF + 0.002, YF + 0.044, z0, z1, 0.009, 3) for z0, z1 in (HZ1, HZ0)]), 'Trim', DOOR, P)
HX, HZ = XF + 0.062, 1.10
for tag, sy in (('-1', -1), ('1', 1)):          # -1 = outside, 1 = inside
    face = P.y + sy * 0.005
    rose = cyl((HX, face, HZ), (HX, face + sy * 0.011, HZ), 0.026, 32, 0.003)
    lever = sweep(fillet([(HX, face + sy * 0.006, HZ), (HX, face + sy * 0.05, HZ), (HX + 0.135, face + sy * 0.056, HZ)], 0.014, 6), 0.0085, 16)
    tip = sphere((HX + 0.135, face + sy * 0.056, HZ), 0.0085, 16, 8)
    obj(f'Rose{tag}', rose, 'Steel', DOOR, P)
    obj(f'Lever{tag}', merge(lever, tip), 'Steel', DOOR, P)

# ================================================================ BACK
obj('BackCap', slab(IX - 0.0005, (CEIL - FLOOR) / 2 - 0.0005, R - T - 0.0005, YB - 0.066, YB - 0.006, 0.006, 'XZ', 0, ZC, 14), 'Shell', BACK)
obj('BackPanel', box(-IW, IW, YI1, YB - 0.066, FLOOR + 0.012, CEIL - 0.03, 0.003, 2), 'BackPanel', BACK)

# ================================================================ FURNITURE
def put(bm, cx, cy, yaw):
    """Local furniture (facing -Y) -> world: turn by yaw about Z, move to (cx, cy)."""
    bmesh.ops.transform(bm, matrix=Matrix.Translation((cx, cy, 0)) @ Matrix.Rotation(yaw, 4, 'Z'), verts=bm.verts)
    return bm

def sofa(sg, tag, y0, y1):
    """SY-05/06: dark seat block on a black steel frame, lighter back + high end panel at the back."""
    X = lambda u: sg * u
    xr = lambda u0, u1: sorted((X(u0), X(u1)))
    n = 2 if y1 - y0 < 1.5 else 3
    cl = (y1 - 0.125 - y0) / n                # cushion length along the wall
    seat = [box(*xr(IW - 0.525, IW - 0.005), y0, y1, 0.235, 0.36, 0.02, 3)]
    seat += [box(*xr(IW - 0.52, IW - 0.13), y0 + i * cl + 0.004, y0 + (i + 1) * cl - 0.004, 0.355, 0.455, 0.035, 4) for i in range(n)]
    seat.append(box(*xr(IW - 0.52, IW - 0.13), y1 - 0.125, y1, 0.355, 0.44, 0.02, 3))
    obj(f'SofaSeat{tag}', merge(*seat), 'FabricBase', FURN)
    back = merge(*[hexa({(i, j, k): (X((IW - 0.138, IW - 0.122)[k] if i == 0 else IW - 0.005),
                                   (y0 + c * cl + 0.004, y0 + (c + 1) * cl - 0.004)[j], (0.452, 0.925)[k])
                         for i in (0, 1) for j in (0, 1) for k in (0, 1)}, 0.045, 4) for c in range(n)])
    end = hexa({(i, j, k): (X((IW - 0.51, IW - 0.385)[k] if i == 0 else IW - 0.005), (y1 - 0.13, y1)[j], (0.442, 0.925)[k])
                for i in (0, 1) for j in (0, 1) for k in (0, 1)}, 0.04, 4)
    obj(f'SofaBack{tag}', merge(back, end), 'Fabric', FURN)
    legs = []
    ys = [y0 + 0.035, y1 - 0.035] + ([(y0 + y1) / 2] if y1 - y0 > 1.5 else [])
    for u in (IW - 0.495, IW - 0.045):
        legs += [box(*xr(u - 0.0125, u + 0.0125), y - 0.0125, y + 0.0125, 0.1, 0.236, 0.003, 1) for y in ys]
        legs.append(box(*xr(u - 0.0125, u + 0.0125), y0 + 0.02, y1 - 0.02, 0.212, 0.236, 0.003, 1))
    obj(f'SofaFrame{tag}', merge(*legs), 'Steel', FURN)

def desk_top(name, x0, x1, y0, y1, z, r=0.035):
    """White laminate top with a birch-ply edge, 26 mm thick."""
    obj(name, slab((x1 - x0) / 2, (y1 - y0) / 2, r, z - 0.026, z, 0.0015, 'XY', (x0 + x1) / 2, (y0 + y1) / 2, 8, 2, side=1, cap0=0, cap1=0),
        ['Desk', 'Wood'], FURN)

def grommet(x, y, z, tag=''):
    obj(f'DeskGrommet{tag}', cyl((x, y, z - 0.001), (x, y, z + 0.0015), 0.03, 32, 0.001), 'Trim', FURN)

def display_stand(dy):
    """SJ-01 stand, 27-inch screen and conference camera bar, against the back wall (dy shifts from the 4-person layout)."""
    obj('StandColumn', merge(slab(0.07, 0.025, 0.018, 0.1, 1.40, 0.004, 'XY', 0, 0.65 + dy, 8),
                             box(-0.15, 0.15, 0.605 + dy, 0.69 + dy, 0.1, 0.112, 0.004, 2)), 'Plate', FURN)
    obj('StandBracket', box(-0.05, 0.05, 0.612 + dy, 0.626 + dy, 1.17, 1.37, 0.003, 2), 'Trim', FURN)
    MZ = 1.268
    obj('Monitor', merge(slab(0.31, 0.19, 0.008, 0.583 + dy, 0.598 + dy, 0.002, 'XZ', 0, MZ, 6),
                         slab(0.23, 0.15, 0.03, 0.597 + dy, 0.614 + dy, 0.008, 'XZ', 0, MZ, 8)), 'Trim', FURN)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    sy = 0.5824 + dy
    f = bm.faces.new([bm.verts.new(p) for p in ((-0.3, sy, MZ - 0.178), (0.3, sy, MZ - 0.178), (0.3, sy, MZ + 0.178), (-0.3, sy, MZ + 0.178))])
    for loop, t in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop[uv].uv = t
    obj('MonitorScreen', bm, 'Screen', FURN, smooth=False)
    CZ = 1.495
    obj('CameraBar', slab(0.165, 0.029, 0.027, 0.57 + dy, 0.62 + dy, 0.007, 'XZ', 0, CZ, 10), 'Plate', FURN)
    obj('CameraGlass', merge(slab(0.07, 0.019, 0.017, 0.5685 + dy, 0.5705 + dy, 0, 'XZ', 0, CZ, 8),
                             box(-0.03, 0.03, 0.598 + dy, 0.62 + dy, 1.456, 1.468, 0.002, 1)), 'Trim', FURN)
    obj('CameraLens', cyl((0, 0.5687 + dy, CZ), (0, 0.5672 + dy, CZ), 0.012, 32), 'Lens', FURN)
    obj('CameraRing', torus(Vector((0, 0.5682 + dy, CZ)), (0, 1, 0), 0.0148, 0.0018, 32, 6), 'Green', FURN)

def pedestal_desk(dy, extra):
    """ST-05/06: top on a white pedestal at the back wall + one round column at the front."""
    y1 = 0.61 + dy
    y0 = -0.28 + dy - extra
    desk_top('DeskTop', -0.31, 0.31, y0, y1, 0.83)
    obj('DeskCabinet', box(-0.21, 0.21, y1 - 0.31, y1 - 0.01, 0.13, 0.804, 0.005, 2), 'Desk', FURN)
    obj('DeskCabinetSeam', merge(box(-0.0015, 0.0015, y1 - 0.3106, y1 - 0.309, 0.15, 0.78),
                                 box(-0.19, 0.19, y1 - 0.3106, y1 - 0.309, 0.7785, 0.7815)), 'Seam', FURN, smooth=False)
    obj('DeskPlinth', box(-0.19, 0.19, y1 - 0.29, y1 - 0.03, 0.1, 0.131), 'Trim', FURN)
    ly = y0 + 0.09
    obj('DeskLeg', merge(cyl((0, ly, 0.1), (0, ly, 0.112), 0.10, 48, 0.004), cyl((0, ly, 0.112), (0, ly, 0.804), 0.025, 32),
                         cyl((0, ly, 0.796), (0, ly, 0.804), 0.06, 32, 0.002)), 'Desk', FURN)
    p = y0 + 0.30   # power module under the top, facing the right-hand sofa
    obj('DeskPowerBox', box(0.24, 0.30, p, p + 0.22, 0.75, 0.804, 0.004, 2), 'Trim', FURN)
    obj('DeskSockets', merge(box(0.30, 0.3025, p + 0.035, p + 0.075, 0.757, 0.797, 0.004, 2),
                             box(0.30, 0.3025, p + 0.095, p + 0.135, 0.757, 0.797, 0.004, 2),
                             cyl((0.30, p + 0.18, 0.777), (0.304, p + 0.18, 0.777), 0.012, 24, 0.0012)), 'Plate', FURN)
    obj('DeskSocketHoles', merge(*[box(0.3025, 0.3032, y - 0.0015, y + 0.0015, 0.781, 0.789) for y in (p + 0.047, p + 0.063, p + 0.107, p + 0.123)],
                                 *[box(0.3025, 0.3032, y - 0.004, y + 0.004, 0.768, 0.772) for y in (p + 0.055, p + 0.115)]), 'Trim', FURN, smooth=False)
    grommet(0.19, y1 - 0.11, 0.83)

def high_stool(cx, cy, yaw, tag=''):
    """SY-01: black seat with a low back lip on a steel column, foot ring and floor disc."""
    parts = [cyl((0, 0, 0.1), (0, 0, 0.112), 0.19, 48, 0.004), cyl((0, 0, 0.112), (0, 0, 0.70), 0.022, 24),
             torus(Vector((0, 0, 0.36)), (0, 0, 1), 0.17, 0.008, 48, 8)]
    parts += [sweep([(0.02 * math.cos(a), 0.02 * math.sin(a), 0.33), (0.165 * math.cos(a), 0.165 * math.sin(a), 0.36)], 0.006, 8)
              for a in (math.pi / 2 + k * 2 * math.pi / 3 for k in range(3))]
    obj(f'StoolFrame{tag}', put(merge(*parts), cx, cy, yaw), 'Steel', FURN)
    seat = merge(slab(0.19, 0.18, 0.11, 0.70, 0.75, 0.014, 'XY', 0, 0, 10),
                 box(-0.15, 0.15, 0.15, 0.19, 0.74, 0.86, 0.018, 3))
    obj(f'StoolSeat{tag}', put(seat, cx, cy, yaw), 'Trim', FURN)

def office_chair(cx, cy, yaw, tag=''):
    """SY-02: five-star swivel base on castors, upholstered seat and back."""
    base = [cyl((0, 0, 0.13), (0, 0, 0.17), 0.045, 24, 0.004), cyl((0, 0, 0.17), (0, 0, 0.30), 0.03, 24), cyl((0, 0, 0.30), (0, 0, 0.44), 0.022, 24)]
    for k in range(5):
        a = math.pi / 2 + k * 2 * math.pi / 5
        c, s = math.cos(a), math.sin(a)
        base += [sweep([(0.03 * c, 0.03 * s, 0.155), (0.29 * c, 0.29 * s, 0.135)], 0.016, 10), sphere((0.30 * c, 0.30 * s, 0.124), 0.024, 12, 8)]
    base.append(box(-0.025, 0.025, 0.10, 0.24, 0.45, 0.62, 0.006, 2))
    obj(f'ChairFrame{tag}', put(merge(*base), cx, cy, yaw), 'Steel', FURN)
    obj(f'ChairSeat{tag}', put(slab(0.24, 0.23, 0.08, 0.44, 0.52, 0.025, 'XY', 0, 0, 10, 3), cx, cy, yaw), 'FabricBase', FURN)
    back = hexa({(i, j, k): ((-0.22, 0.22)[i], (0.20 + 0.04 * k, 0.25 + 0.04 * k)[j], (0.56, 1.02)[k])
                 for i in (0, 1) for j in (0, 1) for k in (0, 1)}, 0.03, 4)
    obj(f'ChairBack{tag}', put(back, cx, cy, yaw), 'Fabric', FURN)

def meeting_chair(cx, cy, yaw, tag=''):
    """SY-03: cantilever chair, chrome tube frame, upholstered seat and back."""
    frame = [sweep(fillet([(x, 0.22, 0.111), (x, -0.20, 0.111), (x, -0.25, 0.25), (x, -0.20, 0.44), (x, 0.20, 0.45), (x, 0.23, 0.86)], 0.05, 6), 0.011, 12)
             for x in (-0.21, 0.21)]
    frame.append(sweep([(-0.21, 0.21, 0.111), (0.21, 0.21, 0.111)], 0.011, 12))
    obj(f'MeetChairFrame{tag}', put(merge(*frame), cx, cy, yaw), 'Chrome', FURN)
    obj(f'MeetChairSeat{tag}', put(slab(0.24, 0.23, 0.06, 0.455, 0.515, 0.02, 'XY', 0, 0, 10, 3), cx, cy, yaw), 'FabricBase', FURN)
    back = hexa({(i, j, k): ((-0.23, 0.23)[i], (0.235 + 0.04 * k, 0.27 + 0.04 * k)[j], (0.58, 0.88)[k])
                 for i in (0, 1) for j in (0, 1) for k in (0, 1)}, 0.025, 4)
    obj(f'MeetChairBack{tag}', put(back, cx, cy, yaw), 'Fabric', FURN)

def laptop(cx, cy, z, yaw, tag=''):
    """Open 14-inch laptop, user on its -Y side."""
    base = slab(0.155, 0.105, 0.012, z, z + 0.012, 0.003, 'XY', 0, 0, 6, 2)
    lid = hexa({(i, j, k): ((-0.155, 0.155)[i], 0.105 - 0.006 * j + 0.05 * k, (z + 0.012, z + 0.212)[k] + 0.0)
                for i in (0, 1) for j in (0, 1) for k in (0, 1)}, 0.003, 2)
    obj(f'Laptop{tag}', put(merge(base, lid), cx, cy, yaw), 'Plate', FURN)
    scr = hexa({(i, j, k): ((-0.145, 0.145)[i], 0.0985 - 0.001 * j + 0.047 * k, (z + 0.022, z + 0.205)[k])
                for i in (0, 1) for j in (0, 1) for k in (0, 1)})
    keys = box(-0.13, 0.13, -0.02, 0.085, z + 0.012, z + 0.0125)
    obj(f'LaptopScreen{tag}', put(merge(scr, keys), cx, cy, yaw), 'Lens', FURN, smooth=False)

def mug(cx, cy, z, tag=''):
    body = cyl((cx, cy, z), (cx, cy, z + 0.09), 0.04, 32, 0.004)
    handle = torus(Vector((cx + 0.045, cy, z + 0.048)), (0, 1, 0), 0.022, 0.006, 20, 8)
    obj(f'Mug{tag}', merge(body, handle), 'Desk', FURN)
    obj(f'MugCoffee{tag}', cyl((cx, cy, z + 0.075), (cx, cy, z + 0.0752), 0.036, 32), 'Seam', FURN, smooth=False)

def notebook(cx, cy, z, yaw, tag=''):
    obj(f'Notebook{tag}', put(box(-0.075, 0.075, -0.105, 0.105, z, z + 0.012, 0.003, 2), cx, cy, yaw), 'Trim', FURN)
    obj(f'Pen{tag}', put(cyl((0.09, -0.08, z + 0.005), (0.09, 0.07, z + 0.005), 0.0045, 12), cx, cy, yaw), 'Chrome', FURN)

def wall_socket(x, y, z, facing, tag=''):
    """Double socket plate; facing 'back' = on the back wall, 'left' = on the left wall."""
    if facing == 'back':
        plate = box(x - 0.075, x + 0.075, y - 0.008, y, z - 0.043, z + 0.043, 0.004, 2)
        holes = [box(x + dx - 0.0015, x + dx + 0.0015, y - 0.0088, y - 0.0079, z + 0.004, z + 0.016) for dx in (-0.045, -0.029, 0.029, 0.045)]
        holes += [box(x + dx - 0.004, x + dx + 0.004, y - 0.0088, y - 0.0079, z - 0.016, z - 0.010) for dx in (-0.037, 0.037)]
    else:
        plate = box(x, x + 0.008, y - 0.075, y + 0.075, z - 0.043, z + 0.043, 0.004, 2)
        holes = [box(x + 0.0079, x + 0.0088, y + dy - 0.0015, y + dy + 0.0015, z + 0.004, z + 0.016) for dy in (-0.045, -0.029, 0.029, 0.045)]
        holes += [box(x + 0.0079, x + 0.0088, y + dy - 0.004, y + dy + 0.004, z - 0.016, z - 0.010) for dy in (-0.037, 0.037)]
    obj(f'WallSocket{tag}', plate, 'Plate', SHELL)
    obj(f'WallSocketHoles{tag}', merge(*holes), 'Trim', SHELL, smooth=False)

# felt panel joints: thin dark lines on the side walls and across the ceiling (~60 cm panels)
seams = []
L = YI1 - (YF + 0.068)
for i in range(1, max(2, round(L / 0.6))):
    yv = YF + 0.068 + i * L / max(2, round(L / 0.6))
    seams += [box(-IW, -IW + 0.0008, yv - 0.0015, yv + 0.0015, FLOOR + 0.02, CEIL - 0.06),
              box(IW - 0.0008, IW, yv - 0.0015, yv + 0.0015, FLOOR + 0.02, CEIL - 0.06),
              box(-IW + 0.045, IW - 0.045, yv - 0.0015, yv + 0.0015, CEIL - 0.0308, CEIL - 0.03)]
seams += [box(-IW, -IW + 0.0008, YF + 0.07, YI1, 1.1 - 0.0015, 1.1 + 0.0015), box(IW - 0.0008, IW, YF + 0.07, YI1, 1.1 - 0.0015, 1.1 + 0.0015)]
obj('FeltSeams', merge(*seams), 'Seam', SHELL, smooth=False)

# coat hooks on the left wall by the door
hooks = []
for hy in (YF + 0.26, YF + 0.36):
    hooks += [cyl((-IW, hy, 1.66), (-IW + 0.006, hy, 1.66), 0.014, 20, 0.002),
              sweep(fillet([(-IW + 0.005, hy, 1.66), (-IW + 0.055, hy, 1.66), (-IW + 0.07, hy, 1.70)], 0.015, 5), 0.005, 10)]
obj('CoatHooks', merge(*hooks), 'Chrome', SHELL)

if SIZE in ('4', '6'):
    extra = D - 1.536                       # the 6-person pod is 60 cm deeper: longer sofas + desk
    sofa(-1, '-1', YI0 + 0.162, YI1 - 0.037)
    sofa(1, '1', YI0 + 0.162, YI1 - 0.037)
    dy = YI1 - 0.692
    pedestal_desk(dy, extra * 0.6)
    display_stand(dy)
    ym = (-0.28 + dy - extra * 0.6 + 0.61 + dy) / 2
    laptop(-0.13, ym - 0.05, 0.83, -math.pi / 2)
    mug(0.17, ym - 0.22, 0.83)
    notebook(0.15, ym + 0.12, 0.83, 0.2)
    wall_socket(0.34, YI1, 0.95, 'back')
elif SIZE == '1':                           # ST-01 wall desk on the back wall + SY-01 high stool
    desk_top('DeskTop', -IW + 0.04, IW - 0.04, YI1 - 0.31, YI1 - 0.004, 1.03, 0.03)
    obj('DeskBrackets', merge(*[merge(box(x - 0.008, x + 0.008, YI1 - 0.27, YI1 - 0.004, 0.99, 1.004, 0.003, 1),
                                      box(x - 0.008, x + 0.008, YI1 - 0.012, YI1 - 0.002, 0.84, 1.004, 0.003, 1))
                                for x in (-IW + 0.12, IW - 0.12)]), 'Steel', FURN)
    high_stool(0.0, -0.06, 0.0)
    laptop(-0.03, YI1 - 0.17, 1.03, 0.0)
    mug(0.26, YI1 - 0.12, 1.03)
    wall_socket(0.22, YI1, 1.2, 'back')
elif SIZE == '2':                           # ST-04 desk off the left wall + SY-02 swivel chair
    x0, x1 = -IW, -IW + 0.62
    desk_top('DeskTop', x0, x1, -0.38, 0.38, 0.755)
    obj('DeskLegPanel', box(x1 - 0.045, x1 - 0.02, -0.34, 0.34, 0.1, 0.729, 0.004, 2), 'Desk', FURN)
    obj('DeskCleat', box(x0, x0 + 0.014, -0.32, 0.32, 0.67, 0.729, 0.003, 1), 'Desk', FURN)
    grommet(x0 + 0.12, 0.26, 0.755)
    office_chair(0.12, 0.0, -math.pi / 2)
    laptop(-IW + 0.32, 0.03, 0.755, math.pi / 2)
    mug(-IW + 0.36, -0.27, 0.755)
    notebook(-IW + 0.2, 0.25, 0.755, 0.1)
    wall_socket(-IW, 0.15, 1.0, 'left')
elif SIZE == '8':                           # ST-10 meeting table + 8 x SY-03 cantilever chairs
    ty0, ty1 = -1.45, 1.15
    desk_top('DeskTop', -0.55, 0.55, ty0, ty1, 0.755, 0.06)
    for i, ly in enumerate((ty0 + 0.35, ty1 - 0.35)):
        obj(f'TableLeg{i}', box(-0.38, 0.38, ly - 0.02, ly + 0.02, 0.112, 0.729, 0.004, 2), 'Desk', FURN)
        obj(f'TableFoot{i}', box(-0.40, 0.40, ly - 0.04, ly + 0.04, 0.1, 0.114, 0.004, 2), 'Steel', FURN)
    grommet(0, ty0 + 0.6, 0.755, 'A')
    grommet(0, ty1 - 0.6, 0.755, 'B')
    laptop(-0.28, -0.45, 0.755, -math.pi / 2, 'A')
    laptop(0.28, 0.25, 0.755, math.pi / 2, 'B')
    notebook(-0.25, 0.4, 0.755, -0.15, 'A')
    mug(0.3, -0.7, 0.755, 'A')
    mug(-0.32, 0.75, 0.755, 'B')
    wall_socket(0.7, YI1, 0.45, 'back')
    for k, cy in enumerate(ty0 + 0.33 + i * (ty1 - ty0 - 0.66) / 3 for i in range(4)):
        meeting_chair(-0.88, cy, math.pi / 2, f'L{k}')
        meeting_chair(0.88, cy, -math.pi / 2, f'R{k}')

# where the web viewer flies to when you "step inside" (three.js axes: x, y up, z = -Blender y)
DOORX = (XF + XH) / 2
SPOTS = {
    '1': {'seat': [[0, 1.45, 0.08], [0, 1.15, -0.45]], 'door': [[0, 1.6, 0.28], [0, 1.2, -0.5]], 'out': [[0, 1.45, -0.2], [0, 1.3, 1.5]], 'seatLabel': '坐低'},
    '2': {'seat': [[0.12, 1.15, 0], [-0.6, 0.95, 0]], 'door': [[DOORX, 1.6, 0.4], [-0.2, 1.1, -0.5]], 'out': [[-0.3, 1.15, -0.3], [0.3, 1.2, 1.6]], 'seatLabel': '坐低'},
    '4': {'seat': [[-0.72, 1.12, 0.15], [0, 1.25, -0.6]], 'door': [[-0.05, 1.6, 0.5], [0, 1.1, -0.7]], 'out': [[0.72, 1.12, -0.35], [-0.4, 1.2, 1.5]], 'seatLabel': '坐梳化'},
    '6': {'seat': [[-0.72, 1.12, 0.35], [0, 1.25, -0.9]], 'door': [[-0.05, 1.6, 0.8], [0, 1.1, -1.0]], 'out': [[0.72, 1.12, -0.6], [-0.4, 1.2, 2.0]], 'seatLabel': '坐梳化'},
    '8': {'seat': [[-0.88, 1.15, 0.6], [0.6, 1.0, -1.0]], 'door': [[DOORX, 1.6, 1.75], [0, 1.1, -1.8]], 'out': [[0.88, 1.15, -1.0], [-0.3, 1.2, 3.0]], 'seatLabel': '坐低'},
}[SIZE]
ROOT['pod'] = json.dumps({'size': SIZE, 'w': W, 'd': D, 'h': H, 'doorway': [DOORX, 1.45, D / 2 + 0.6], 'spots': SPOTS}, ensure_ascii=False)

# ---------------------------------------------------------------- export
for me in bpy.data.meshes:   # only the screen and the textiles need UVs
    if me.name != 'MonitorScreen' and not any(m and m.name in TILE for m in me.materials):
        while me.uv_layers:
            me.uv_layers.remove(me.uv_layers[0])

dg = bpy.context.evaluated_depsgraph_get()
tris = sum(sum(len(p.vertices) - 2 for p in o.evaluated_get(dg).data.polygons) for o in COL.objects if o.type == 'MESH')
print(f'objects={sum(o.type == "MESH" for o in COL.objects)} tris={tris}')

os.makedirs(HERE, exist_ok=True)
GLB = os.path.join(REPO, 'pod.glb' if SIZE == '4' else f'pod-{SIZE}.glb')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, f'soundbox{SIZE}.blend'))
bpy.ops.export_scene.gltf(filepath=GLB, export_format='GLB', use_selection=False, export_extras=True,
                          export_apply=True, export_yup=True, export_texcoords=True, export_normals=True,
                          export_materials='EXPORT', export_image_format='JPEG', export_cameras=False, export_lights=False)
print('wrote', GLB)
