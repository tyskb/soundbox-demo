"""USDZ for iPhone AR Quick Look (the web page points model-viewer's ios-src at it).

    for n in 1 2 4 6 8; do Blender -b blender/soundbox$n.blend -P blender/export_usdz.py; done

Writes v2/ar/pod-<size>.usdz. Quick Look reads UsdPreviewSurface, which has no transmission,
so the glass is exported as see-through via opacity instead.
"""
import bpy, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
size = json.loads(bpy.data.objects['Soundbox4']['pod'])['size']
out = os.path.join(os.path.dirname(HERE), 'v2', 'ar', f'pod-{size}.usdz')
os.makedirs(os.path.dirname(out), exist_ok=True)

g = next(n for n in bpy.data.materials['Glass'].node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
g.inputs['Transmission Weight'].default_value = 0.0
g.inputs['Alpha'].default_value = 0.12
g.inputs['Base Color'].default_value = (0.95, 0.97, 1.0, 1.0)

opts = dict(filepath=out, export_materials=True, generate_preview_surface=True, export_textures=True,
            export_animation=False, evaluation_mode='RENDER', convert_orientation=True,
            export_global_forward_selection='NEGATIVE_Z', export_global_up_selection='Y')
props = bpy.ops.wm.usd_export.get_rna_type().properties.keys()
bpy.ops.wm.usd_export(**{k: v for k, v in opts.items() if k in props or k == 'filepath'})
print('wrote', out, os.path.getsize(out))
