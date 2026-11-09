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
import bpy, bmesh, math, os
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
W, D, H = 2.2, 1.536, 2.3
GAP, T, R = 0.008, 0.08, 0.11          # floor gap, shell wall, outer corner radius
YF, YB = -D / 2, D / 2
ZC, HA, HB = (GAP + H) / 2, W / 2, (H - GAP) / 2
IX, FLOOR, CEIL = HA - T, GAP + T, H - T   # 1.02, 0.088, 2.22
GW = 0.035                                 # black gasket width
PIVOT = Vector((0.32, -0.745, 1.154))      # door hinge axis (pod.js swings 'Door' about Y)
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
obj('SideVents', merge(*[box(HA - 0.004, HA + 0.0006, -0.645, -0.634, z - 0.018, z + 0.018, 0.003, 2)
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
for name, mtx in (('ContexLogoR', Matrix(((0, 0, 1, HA + 0.0002), (1, 0, 0, 0), (0, 1, 0, LZ), (0, 0, 0, 1)))),
                  ('ContexLogoL', Matrix(((0, 0, -1, -HA - 0.0002), (-1, 0, 0, 0), (0, 1, 0, LZ), (0, 0, 0, 1))))):
    bm = bmesh.new()
    bm.from_mesh(logo_me)
    bmesh.ops.transform(bm, matrix=mtx, verts=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj(name, bm, 'Logo', SHELL, smooth=False)
bpy.data.meshes.remove(logo_me)

# damping feet (8 mm floor gap)
feet = []
for sx in (-1, 1):
    for sy in (-1, 1):
        cx, cy = sx * 0.955, sy * 0.63
        feet += [(cyl((cx, cy, 0), (cx, cy, 0.0035), 0.03, 24), 1),
                 (box(cx - 0.036, cx + 0.036, cy - 0.036, cy + 0.036, 0.003, 0.0125, 0.004, 2), 0)]
obj('Feet', merge(*feet), ['Shell', 'Rubber'], SHELL)

# interior lining
obj('Carpet', box(-1.0, 1.0, -0.712, 0.692, FLOOR, 0.1, 0.002, 1), 'Carpet', SHELL)
obj('FeltLeft', box(-IX, -1.0, -0.70, 0.692, 0.1, 2.19, 0.004, 2), 'Felt', SHELL)
obj('FeltRight', box(1.0, IX, -0.70, 0.692, 0.1, 2.19, 0.004, 2), 'Felt', SHELL)
obj('Ceiling', box(-1.0, 1.0, -0.68, 0.692, 2.19, 2.218, 0.004, 2), 'Felt', SHELL)

# front header band behind the glass with the four touch controls
obj('ControlPanel', box(-1.0, 1.0, -0.712, -0.68, 2.105, 2.205, 0.004, 2), 'Trim', SHELL)
ICON_Y, ICON_Z = -0.7126, 2.152
icons = []
for i, x in enumerate((0.72, 0.775, 0.83, 0.885)):
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
obj('PirSensor', sphere((0.0, -0.69, 2.105), 0.016, 16, 8, half=True), 'Trim', SHELL)

# lighting: central linear pendant (4000K) + LED strips along both side walls
obj('LedBarHousing', merge(box(-0.32, 0.32, 0.02, 0.08, 2.095, 2.125, 0.008, 3),
                           cyl((-0.26, 0.05, 2.125), (-0.26, 0.05, 2.19), 0.0025, 8),
                           cyl((0.26, 0.05, 2.125), (0.26, 0.05, 2.19), 0.0025, 8),
                           cyl((-0.26, 0.05, 2.184), (-0.26, 0.05, 2.19), 0.02, 20, 0.002),
                           cyl((0.26, 0.05, 2.184), (0.26, 0.05, 2.19), 0.02, 20, 0.002)), 'Trim', SHELL)
obj('LedBar', box(-0.31, 0.31, 0.028, 0.072, 2.0935, 2.0955), 'LightPanel', SHELL, smooth=False)
for side, sx in (('', -1), ('R', 1)):
    hx = sorted((sx * 1.0, sx * 0.958))
    obj(f'LedEdgeHousing{side}', box(hx[0], hx[1], -0.68, 0.69, 2.165, 2.19, 0.003, 2), 'Trim', SHELL)
    lx = sorted((sx * 0.995, sx * 0.963))
    obj(f'LedEdge{side}', box(lx[0], lx[1], -0.675, 0.685, 2.1635, 2.1655), 'LightPanel', SHELL, smooth=False)

# fresh-air grilles in the ceiling
grilles = []
for gx in (-0.55, 0.55):
    grilles.append((cyl((gx, 0.38, 2.185), (gx, 0.38, 2.19), 0.08, 40, 0.002), 0))
    grilles += [(torus(Vector((gx, 0.38, 2.1845)), (0, 0, 1), rr, 0.0022, 40, 6), 1) for rr in (0.022, 0.038, 0.054, 0.068)]
obj('AirGrilles', merge(*grilles), ['Plate', 'Seam'], SHELL)

# emergency hammer on the right wall, by the door
obj('HammerHolder', merge(box(0.988, 1.0, -0.665, -0.625, 1.94, 2.08, 0.004, 2),
                          box(0.958, 0.99, -0.655, -0.635, 1.955, 1.97, 0.002, 1),
                          box(0.958, 0.99, -0.655, -0.635, 2.035, 2.05, 0.002, 1)), 'Trim', SHELL)
obj('Hammer', merge(cyl((0.972, -0.645, 1.925), (0.972, -0.645, 2.06), 0.0115, 20, 0.003),
                    box(0.961, 0.983, -0.69, -0.60, 2.055, 2.086, 0.004, 2)), 'Red', SHELL)
obj('HammerTips', merge(cyl((0.972, -0.69, 2.0705), (0.972, -0.708, 2.0705), 0.012, 16, r1=0.002),
                        cyl((0.972, -0.60, 2.0705), (0.972, -0.582, 2.0705), 0.012, 16, r1=0.002)), 'Steel', SHELL)

# light / fan switch on the left wall, by the door
obj('WallSwitch', box(-1.0, -0.99, -0.655, -0.595, 1.22, 1.34, 0.004, 2), 'Trim', SHELL)
obj('WallSwitchKeys', merge(cyl((-0.99, -0.625, 1.305), (-0.9865, -0.625, 1.305), 0.011, 24, 0.001),
                            cyl((-0.99, -0.625, 1.255), (-0.9865, -0.625, 1.255), 0.011, 24, 0.001)), 'Plate', SHELL)

# ================================================================ FRONT
gpr = Prof()
s0, s1, gy0, gy1, bg = T - 0.002, T + GW, YF + 0.007, -0.712, 0.006
gpr.add([(s0, gy1), (s0, gy0), (s1 - bg, gy0)]).add(arc(s1 - bg, gy0 + bg, bg, 270, 360, 3)).add([(s1, gy1)])
obj('Gasket', loft(gpr.p, HA, HB, R, seg=14, vc=ZC, rmin=0.022), 'Trim', FRONT)

GZ0, GZ1 = 0.11, 2.198          # glass runs into the gasket
obj('GlassLeft', box(-1.0, -0.482, -0.74, -0.73, GZ0, GZ1), 'Glass', FRONT, smooth=False)
obj('GlassRight', box(0.332, 1.0, -0.74, -0.73, GZ0, GZ1), 'Glass', FRONT, smooth=False)
obj('MullionFree', box(-0.495, -0.469, -0.752, -0.718, 0.115, 2.193, 0.006, 3), 'Trim', FRONT)
obj('MullionHinge', box(0.319, 0.345, -0.752, -0.718, 0.115, 2.193, 0.006, 3), 'Trim', FRONT)
obj('HingeFixed', merge(box(0.3215, 0.37, -0.766, -0.724, 1.93, 2.03, 0.009, 3),
                        box(0.3215, 0.37, -0.766, -0.724, 0.30, 0.40, 0.009, 3)), 'Trim', FRONT)

# floor edge seen through the glass, with the badge
obj('Threshold', box(-0.985, 0.985, -0.716, -0.70, FLOOR, 0.168, 0.003, 2), 'Trim', FRONT)
FONT = '/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf'
obj('Logo', merge(text('soundbox', 0.03, -0.935, -0.7166, 0.13, FONT),
                  text('Movable Silence Booth', 0.0095, -0.795, -0.7166, 0.131, FONT),
                  flat([disc2d(-0.948, 0.1385, 0.0075, 0.0058, 16)], -0.7166)), 'Icon', FRONT, smooth=False)

# door: frameless glass leaf hinged on the right mullion
P = PIVOT
obj('DoorGlass', box(-0.462, 0.312, -0.75, -0.74, 0.13, 2.178), 'Glass', DOOR, P, smooth=False)
obj('DoorEdgeFree', box(-0.468, -0.455, -0.755, -0.735, 0.13, 2.178, 0.003, 2), 'Trim', DOOR, P)
obj('DoorSeal', merge(box(0.312, 0.318, -0.749, -0.741, 0.14, 2.17, 0.002, 1),
                      box(-0.455, 0.312, -0.749, -0.741, 2.178, 2.185, 0.002, 1),
                      box(-0.455, 0.312, -0.749, -0.741, 0.123, 0.13, 0.002, 1)), 'Rubber', DOOR, P)
obj('HingeDoor', merge(box(0.27, 0.3185, -0.766, -0.724, 1.93, 2.03, 0.009, 3),
                       box(0.27, 0.3185, -0.766, -0.724, 0.30, 0.40, 0.009, 3)), 'Trim', DOOR, P)
HX, HZ = -0.40, 1.10
for tag, sy in (('-1', -1), ('1', 1)):          # -1 = outside, 1 = inside
    face = -0.745 + sy * 0.005
    rose = cyl((HX, face, HZ), (HX, face + sy * 0.011, HZ), 0.026, 32, 0.003)
    lever = sweep(fillet([(HX, face + sy * 0.006, HZ), (HX, face + sy * 0.05, HZ), (HX + 0.135, face + sy * 0.056, HZ)], 0.014, 6), 0.0085, 16)
    tip = sphere((HX + 0.135, face + sy * 0.056, HZ), 0.0085, 16, 8)
    obj(f'Rose{tag}', rose, 'Steel', DOOR, P)
    obj(f'Lever{tag}', merge(lever, tip), 'Steel', DOOR, P)

# ================================================================ BACK
obj('BackCap', slab(IX - 0.0005, (CEIL - FLOOR) / 2 - 0.0005, R - T - 0.0005, 0.702, 0.762, 0.006, 'XZ', 0, ZC, 14), 'Shell', BACK)
obj('BackPanel', box(-1.0, 1.0, 0.692, 0.702, 0.1, 2.19, 0.003, 2), 'BackPanel', BACK)

# ================================================================ FURNITURE
# SY-05 sofas: dark seat block on a black steel frame, lighter back + high end panel (L/R pair)
def sofa(sg, tag):
    X = lambda u: sg * u
    xr = lambda u0, u1: sorted((X(u0), X(u1)))
    obj(f'SofaSeat{tag}', box(*xr(0.475, 0.995), -0.55, 0.655, 0.235, 0.45, 0.032, 4), 'FabricBase', FURN)
    back = hexa({(i, j, k): (X((0.862, 0.878)[k] if i == 0 else 0.995), (-0.55, 0.53)[j], (0.442, 0.925)[k])
                 for i in (0, 1) for j in (0, 1) for k in (0, 1)}, 0.04, 4)
    end = hexa({(i, j, k): (X((0.49, 0.615)[k] if i == 0 else 0.995), (0.525, 0.655)[j], (0.442, 0.925)[k])
                for i in (0, 1) for j in (0, 1) for k in (0, 1)}, 0.04, 4)
    obj(f'SofaBack{tag}', merge(back, end), 'Fabric', FURN)
    legs = []
    for u in (0.505, 0.955):
        legs += [box(*xr(u - 0.0125, u + 0.0125), y - 0.0125, y + 0.0125, 0.1, 0.236, 0.003, 1) for y in (-0.515, 0.62)]
        legs.append(box(*xr(u - 0.0125, u + 0.0125), -0.53, 0.635, 0.212, 0.236, 0.003, 1))
    obj(f'SofaFrame{tag}', merge(*legs), 'Steel', FURN)

sofa(-1, '-1')
sofa(1, '1')

# ST-05 desk: birch-edged top, white pedestal at the back, round column + floor disc at the front
DY0, DY1, DZ0, DZ1 = -0.28, 0.61, 0.804, 0.83
obj('DeskTop', slab(0.31, (DY1 - DY0) / 2, 0.035, DZ0, DZ1, 0.0015, 'XY', 0, (DY0 + DY1) / 2, 8, 2, side=1, cap0=0, cap1=0),
    ['Desk', 'Wood'], FURN)
obj('DeskCabinet', box(-0.21, 0.21, 0.30, 0.60, 0.13, DZ0, 0.005, 2), 'Desk', FURN)
obj('DeskCabinetSeam', merge(box(-0.0015, 0.0015, 0.2994, 0.301, 0.15, 0.78), box(-0.19, 0.19, 0.2994, 0.301, 0.7785, 0.7815)), 'Seam', FURN, smooth=False)
obj('DeskPlinth', box(-0.19, 0.19, 0.32, 0.58, 0.1, 0.131), 'Trim', FURN)
obj('DeskLeg', merge(cyl((0, -0.19, 0.1), (0, -0.19, 0.112), 0.10, 48, 0.004),
                     cyl((0, -0.19, 0.112), (0, -0.19, DZ0), 0.025, 32),
                     cyl((0, -0.19, DZ0 - 0.008), (0, -0.19, DZ0), 0.06, 32, 0.002)), 'Desk', FURN)
obj('DeskPowerBox', box(0.24, 0.30, 0.02, 0.24, 0.75, DZ0, 0.004, 2), 'Trim', FURN)
obj('DeskSockets', merge(box(0.30, 0.3025, 0.055, 0.095, 0.757, 0.797, 0.004, 2),
                         box(0.30, 0.3025, 0.115, 0.155, 0.757, 0.797, 0.004, 2),
                         cyl((0.30, 0.20, 0.777), (0.304, 0.20, 0.777), 0.012, 24, 0.0012)), 'Plate', FURN)
obj('DeskSocketHoles', merge(*[box(0.3025, 0.3032, y - 0.0015, y + 0.0015, 0.781, 0.789) for y in (0.067, 0.083, 0.127, 0.143)],
                             *[box(0.3025, 0.3032, y - 0.004, y + 0.004, 0.768, 0.772) for y in (0.075, 0.135)]), 'Trim', FURN, smooth=False)
obj('DeskGrommet', cyl((0.19, 0.50, DZ1 - 0.001), (0.19, 0.50, DZ1 + 0.0015), 0.03, 32, 0.001), 'Trim', FURN)

# SJ-01 display stand, 27" screen, conference camera bar
obj('StandColumn', merge(slab(0.07, 0.025, 0.018, 0.1, 1.40, 0.004, 'XY', 0, 0.65, 8),
                         box(-0.15, 0.15, 0.605, 0.69, 0.1, 0.112, 0.004, 2)), 'Plate', FURN)
obj('StandBracket', box(-0.05, 0.05, 0.612, 0.626, 1.17, 1.37, 0.003, 2), 'Trim', FURN)
MZ = 1.268
obj('Monitor', merge(slab(0.31, 0.19, 0.008, 0.583, 0.598, 0.002, 'XZ', 0, MZ, 6),
                     slab(0.23, 0.15, 0.03, 0.597, 0.614, 0.008, 'XZ', 0, MZ, 8)), 'Trim', FURN)
bm = bmesh.new()
uv = bm.loops.layers.uv.new('UVMap')
f = bm.faces.new([bm.verts.new(p) for p in ((-0.3, 0.5824, MZ - 0.178), (0.3, 0.5824, MZ - 0.178), (0.3, 0.5824, MZ + 0.178), (-0.3, 0.5824, MZ + 0.178))])
for loop, t in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
    loop[uv].uv = t
obj('MonitorScreen', bm, 'Screen', FURN, smooth=False)
CZ = 1.495
obj('CameraBar', slab(0.165, 0.029, 0.027, 0.57, 0.62, 0.007, 'XZ', 0, CZ, 10), 'Plate', FURN)
obj('CameraGlass', merge(slab(0.07, 0.019, 0.017, 0.5685, 0.5705, 0, 'XZ', 0, CZ, 8),
                         box(-0.03, 0.03, 0.598, 0.62, 1.456, 1.468, 0.002, 1)), 'Trim', FURN)
obj('CameraLens', cyl((0, 0.5687, CZ), (0, 0.5672, CZ), 0.012, 32), 'Lens', FURN)
obj('CameraRing', torus(Vector((0, 0.5682, CZ)), (0, 1, 0), 0.0148, 0.0018, 32, 6), 'Green', FURN)

# ---------------------------------------------------------------- export
for me in bpy.data.meshes:   # only the screen and the textiles need UVs
    if me.name != 'MonitorScreen' and not any(m and m.name in TILE for m in me.materials):
        while me.uv_layers:
            me.uv_layers.remove(me.uv_layers[0])

dg = bpy.context.evaluated_depsgraph_get()
tris = sum(sum(len(p.vertices) - 2 for p in o.evaluated_get(dg).data.polygons) for o in COL.objects if o.type == 'MESH')
print(f'objects={sum(o.type == "MESH" for o in COL.objects)} tris={tris}')

os.makedirs(HERE, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, 'soundbox4.blend'))
bpy.ops.export_scene.gltf(filepath=os.path.join(REPO, 'pod.glb'), export_format='GLB', use_selection=False,
                          export_apply=True, export_yup=True, export_texcoords=True, export_normals=True,
                          export_materials='EXPORT', export_image_format='JPEG', export_cameras=False, export_lights=False)
print('wrote', os.path.join(REPO, 'pod.glb'))
