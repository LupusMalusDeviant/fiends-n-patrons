"""A1: re-exports one `_r3c[...].blend` as `_r3d[...].blend` + `_r3d[...].glb`, with tangents.

Headless only: `blender --background --python export_r3d.py --python-exit-code 1 -- <base_name>
<src_blend> <dst_blend> <dst_glb>`. Nothing is rendered.

Selection rule (measured against the shipped `_r3c*.glb` files, not guessed): every MESH object
in the source file except the bake-cage helper `<base_name>_cage` (present, unhidden, only in the
high-poly file -- confirmed absent from the actual exported `_r3c.glb` node list), plus the single
ARMATURE object, which is made active. This reproduces exactly the node set already shipped in
`_r3c[...].glb` for all three figures and both LOD levels.

Export call is byte-for-byte the one in build_character_r2.py (around its own lines 386/407) with
exactly one addition: `export_tangents=True`.
"""
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
if len(argv) != 4:
    raise SystemExit(f"usage: -- <base_name> <src_blend> <dst_blend> <dst_glb> (got {argv!r})")
base_name, src_blend, dst_blend, dst_glb = argv

# Never leave a .blend1 backup: disable Blender's numbered-backup-on-overwrite preference before
# any save_as_mainfile call (matters on a re-run over an existing target).
bpy.context.preferences.filepaths.save_version = 0

bpy.ops.wm.open_mainfile(filepath=src_blend)

# The .blend content itself needs no change for tangents (MikkTSpace tangents are computed at
# export time from existing normals/UVs, never stored in mesh data) -- so the _r3d.blend is simply
# the _r3c.blend re-saved under the new round name, unchanged otherwise.
bpy.ops.wm.save_as_mainfile(filepath=dst_blend)

cage_name = f"{base_name}_cage"
mesh_objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.name != cage_name]
armatures = [o for o in bpy.data.objects if o.type == 'ARMATURE']
excluded = [o.name for o in bpy.data.objects if o.type == 'MESH' and o.name == cage_name]

if len(armatures) != 1:
    raise RuntimeError(
        f"{src_blend}: expected exactly one armature, found {len(armatures)}: "
        f"{[a.name for a in armatures]}"
    )
if not mesh_objs:
    raise RuntimeError(f"{src_blend}: no mesh objects left to export after excluding {cage_name!r}")
arm_ob = armatures[0]

bpy.ops.object.select_all(action='DESELECT')
for o in mesh_objs:
    o.select_set(True)
arm_ob.select_set(True)
bpy.context.view_layer.objects.active = arm_ob

bpy.ops.export_scene.gltf(
    filepath=dst_glb, export_format='GLB', use_selection=True,
    export_skins=True, export_apply=False, export_animations=False,
    export_rest_position_armature=True, export_yup=True, export_tangents=True,
)

print(
    "EXPORT_R3D_OK",
    "base_name=", base_name,
    "meshes=", sorted(o.name for o in mesh_objs),
    "excluded=", excluded,
    "armature=", arm_ob.name,
    "dst_blend=", dst_blend,
    "dst_glb=", dst_glb,
)
