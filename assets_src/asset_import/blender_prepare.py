"""Stage 2 of the asset import: turns a rigged figure into a game figure (Blender, headless).

    blender -b --factory-startup -t 1 --python-exit-code 1 --python blender_prepare.py --
        --rigged <rigged.glb> --high <hi3d.glb> --base-color <png> --metallic-roughness <png>
        --out <figure.glb> --normal-map-out <png> --report <report.json> --height 1.8
        --triangles 18000 --normal-size 1024 [--swap-sides] [--lod-source high|rigged]

Called by `prepare_figure.py`, which also produces the two downscaled texture PNGs. Nothing is
rendered; no GPU is touched.

Steps, in this order:

1. **Import** the rigged working mesh (skin, joints, clips) and the high-resolution source it was
   made from (Hi3D download, 2M triangles). Node transforms of the source are baked into its mesh.
2. **Swap side names** (optional): joints ending in `.L`/`_l` and `.R`/`_r` trade names, together
   with their vertex groups and every animation channel. For rigs whose side names are mirrored
   against the anatomy (the imp pilot, see the stage-1 check).
3. **Weld and smooth** both meshes: custom normals cleared, coincident vertices merged, every face
   smooth. The rigged witch arrives flat-shaded, one vertex per triangle corner (299,984 vertices
   for 100,000 triangles); UV seams survive as per-corner UVs.
4. **Reduce.** By default the high source is reduced (collapse decimation) and the skin weights
   are transferred from the rigged mesh (nearest face, interpolated), then limited to four
   influences and normalised. The rigged working meshes are cracked: after the weld the witch's
   has 38,462 open edges in 307 pieces, the source none. Reducing the rigged mesh instead
   (`--lod-source rigged`) keeps those cracks as shading seams.
5. **Scale and ground.** One uniform scale to the target height, then a translation that puts the
   lowest point on the floor and the bounding box centre over the origin, both measured on the
   reduced mesh. Applied to the mesh data, the rest pose of the armature, the location channels
   of every clip and the high source, never as an object transform, so the exported joints need
   no correction later.
6. **Tangents:** faces with a corner whose MikkTSpace tangent comes out zero (folded slivers
   after the reduction) are shaded flat, so every exported tangent is valid for the converter.
7. **Shape normal map** from the high source onto the reduced mesh with the round-4 tooling
   (`../figures/shapenormal.py`): nearest high surface point per texel, expressed in the reduced
   mesh's MikkTSpace frame. No Cycles bake.
8. **Material and export:** the downscaled base colour and metallic-roughness PNGs replace the
   8K originals, the normal map is added, and the figure is exported as glTF binary with
   tangents and all clips.

The report holds counts, distances and the normal-map statistics; it names files, never paths.
Run it with one thread (`-t 1`): with more, MikkTSpace tangents differed between two runs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "figures"))
sys.path.insert(0, str(HERE))

import normalmap as NM  # noqa: E402
import palette as P  # noqa: E402
import shapenormal as SN  # noqa: E402
import texproject as TP  # noqa: E402
from side_names import side_renames  # noqa: E402

WELD_DISTANCE_M = 1e-6  # before scaling; Hi3D models arrive 1 m tall
MAX_INFLUENCES = 4


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="blender_prepare.py")
    parser.add_argument("--rigged", type=Path, required=True)
    parser.add_argument("--high", type=Path, required=True)
    parser.add_argument("--base-color", type=Path, required=True)
    parser.add_argument("--metallic-roughness", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--normal-map-out", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--height", type=float, required=True)
    parser.add_argument("--triangles", type=int, required=True)
    parser.add_argument("--normal-size", type=int, required=True)
    parser.add_argument("--gutter-px", type=int, default=4)
    parser.add_argument("--swap-sides", action="store_true")
    parser.add_argument("--lod-source", choices=("high", "rigged"), default="high")
    return parser.parse_args(argv)


# ------------------------------------------------------------------------------------ import


def clear_scene() -> None:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for collection in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.actions,
                       bpy.data.armatures):
        for block in list(collection):
            collection.remove(block)


def import_glb(path: Path) -> list[bpy.types.Object]:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return sorted((ob for ob in bpy.data.objects if ob not in before), key=lambda ob: ob.name)


def triangle_count(me: bpy.types.Mesh) -> int:
    me.calc_loop_triangles()
    return len(me.loop_triangles)


def select_only(*objects: bpy.types.Object, active: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objects:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = active


# ------------------------------------------------------------------------------ side names

def all_fcurves():
    for action in sorted(bpy.data.actions, key=lambda a: a.name):
        for layer in action.layers:
            for strip in layer.strips:
                for channelbag in strip.channelbags:
                    yield channelbag, channelbag.fcurves


def swap_sides(arm: bpy.types.Object, mesh_ob: bpy.types.Object) -> list[list[str]]:
    """Trades the names of left- and right-side joints, their vertex groups and clip channels."""
    renames = side_renames([bone.name for bone in arm.data.bones])
    temporary = {old: f"__swap__{old}" for old in renames}
    for stage in (temporary, {temporary[old]: new for old, new in renames.items()}):
        for old, new in stage.items():
            arm.data.bones[old].name = new
            group = mesh_ob.vertex_groups.get(old)
            if group is not None:
                group.name = new
        for channelbag, fcurves in all_fcurves():
            for fcurve in fcurves:
                for old, new in stage.items():
                    token = f'pose.bones["{old}"]'
                    if token in fcurve.data_path:
                        fcurve.data_path = fcurve.data_path.replace(token, f'pose.bones["{new}"]')
            for group in channelbag.groups:
                if group.name in stage:
                    group.name = stage[group.name]
    leftover = [g.name for g in mesh_ob.vertex_groups if g.name.startswith("__swap__")]
    if leftover:
        raise RuntimeError(f"side swap left temporary vertex groups {leftover}")
    return sorted([old, new] for old, new in renames.items())


# ------------------------------------------------------------------------------- geometry


def weld_and_smooth(ob: bpy.types.Object) -> dict:
    me = ob.data
    vertices_before = len(me.vertices)
    if me.has_custom_normals:
        select_only(ob, active=ob)
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=WELD_DISTANCE_M)
    for face in bm.faces:
        face.smooth = True
    for edge in bm.edges:
        edge.smooth = True
    bm.to_mesh(me)
    bm.free()
    if "sharp_face" in me.attributes:
        me.attributes.remove(me.attributes["sharp_face"])
    return {"vertices_before": vertices_before, "vertices_after": len(me.vertices)}


def percentiles(values: np.ndarray, quantiles: tuple[int, ...], digits: int) -> dict:
    return {f"p{q}": round(float(np.percentile(values, q)), digits) for q in quantiles}


def world_bounds(ob: bpy.types.Object) -> tuple[Vector, Vector]:
    co = np.empty(len(ob.data.vertices) * 3, dtype=np.float64)
    ob.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    return Vector(co.min(axis=0)), Vector(co.max(axis=0))


def grounding_matrix(low: Vector, high: Vector, height: float) -> tuple[Matrix, float]:
    scale = height / (high.z - low.z)
    centre_x, centre_y = (low.x + high.x) / 2.0, (low.y + high.y) / 2.0
    shift = Vector((-centre_x * scale, -centre_y * scale, -low.z * scale))
    return Matrix.Translation(shift) @ Matrix.Scale(scale, 4), scale


def transform_rig(arm: bpy.types.Object, matrix: Matrix, scale: float) -> int:
    """Moves the armature's rest pose by `matrix` and scales every clip's location keys."""
    if arm.matrix_world != Matrix.Identity(4):
        raise RuntimeError("the armature object must have an identity transform")
    select_only(arm, active=arm)
    bpy.ops.object.mode_set(mode="EDIT")
    for bone in arm.data.edit_bones:
        bone.transform(matrix, scale=True, roll=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    scaled = 0
    for _channelbag, fcurves in all_fcurves():
        for fcurve in fcurves:
            if fcurve.data_path.endswith(".location"):
                for key in fcurve.keyframe_points:
                    key.co.y *= scale
                    key.handle_left.y *= scale
                    key.handle_right.y *= scale
                scaled += 1
    return scaled


def decimate(ob: bpy.types.Object, target: int) -> None:
    modifier = ob.modifiers.new("game_lod", "DECIMATE")
    modifier.decimate_type = "COLLAPSE"
    modifier.ratio = target / triangle_count(ob.data)
    modifier.use_collapse_triangulate = True
    select_only(ob, active=ob)
    bpy.ops.object.modifier_move_to_index(modifier=modifier.name, index=0)
    bpy.ops.object.modifier_apply(modifier=modifier.name)


def limit_weights(ob: bpy.types.Object) -> None:
    select_only(ob, active=ob)
    bpy.ops.object.vertex_group_limit_total(group_select_mode="ALL", limit=MAX_INFLUENCES)
    bpy.ops.object.vertex_group_normalize_all(group_select_mode="ALL", lock_active=False)


def topology(ob: bpy.types.Object) -> dict:
    """Open edges and connected pieces after the weld: cracks show up as boundary edges."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    boundary = sum(1 for edge in bm.edges if edge.is_boundary)
    bm.faces.ensure_lookup_table()
    seen = bytearray(len(bm.faces))
    pieces = 0
    for face in bm.faces:
        if seen[face.index]:
            continue
        pieces += 1
        seen[face.index] = 1
        stack = [face]
        while stack:
            for edge in stack.pop().edges:
                for other in edge.link_faces:
                    if not seen[other.index]:
                        seen[other.index] = 1
                        stack.append(other)
    bm.free()
    return {"boundary_edges": boundary, "connected_pieces": pieces}


def transfer_weights(
    target: bpy.types.Object, source: bpy.types.Object, arm: bpy.types.Object
) -> dict:
    """Skin weights from the rigged working mesh onto `target`, interpolated at the nearest face."""
    modifier = target.modifiers.new("weights", "DATA_TRANSFER")
    modifier.object = source
    modifier.use_vert_data = True
    modifier.data_types_verts = {"VGROUP_WEIGHTS"}
    modifier.vert_mapping = "POLYINTERP_NEAREST"
    modifier.layers_vgroup_select_src = "ALL"
    modifier.layers_vgroup_select_dst = "NAME"
    select_only(target, active=target)
    bpy.ops.object.datalayout_transfer(modifier=modifier.name)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    limit_weights(target)

    bvh = BVHTree.FromObject(source, bpy.context.evaluated_depsgraph_get())
    co = np.empty(len(target.data.vertices) * 3, dtype=np.float64)
    target.data.vertices.foreach_get("co", co)
    distances = np.array([bvh.find_nearest(Vector(p))[3] for p in co.reshape(-1, 3)]) * 1000.0
    unweighted = sum(1 for v in target.data.vertices if not v.groups)

    target.parent = arm
    armature = target.modifiers.new("Armature", "ARMATURE")
    armature.object = arm
    return {
        "unweighted_vertices": unweighted,
        "distance_to_rigged_surface_mm": percentiles(distances, (50, 90, 99, 100), 3),
    }


def surface_distances(high_surface: dict, ob: bpy.types.Object) -> dict:
    """Distance from each reduced vertex to the high surface, in millimetres."""
    co = np.empty(len(ob.data.vertices) * 3, dtype=np.float64)
    ob.data.vertices.foreach_get("co", co)
    find = high_surface["bvh"].find_nearest
    distances = np.array([find(Vector(p))[3] for p in co.reshape(-1, 3)]) * 1000.0
    return percentiles(distances, (50, 90, 99, 100), 3)


def repair_degenerate_tangents(ob: bpy.types.Object) -> int:
    """Shades flat every face with a corner whose MikkTSpace tangent is not unit length.

    Reducing folds a few sliver triangles over, so a corner's smooth normal lies almost in the
    triangle's own plane (measured: 1 corner in the witch, 1 in the imp). MikkTSpace then projects
    the tangent onto that normal and gets a zero vector, which the figure-pack converter rightly
    rejects. A flat face takes its own normal, and its tangent is well defined again. Repeats
    while flattening changes neighbouring smooth normals; returns the number of faces shaded flat.
    """
    me = ob.data
    uv_name = me.uv_layers.active.name
    starts = np.empty(len(me.polygons), dtype=np.int32)
    totals = np.empty(len(me.polygons), dtype=np.int32)
    me.polygons.foreach_get("loop_start", starts)
    me.polygons.foreach_get("loop_total", totals)
    loop_face = np.repeat(np.arange(len(me.polygons)), totals)
    flattened: set[int] = set()
    for _attempt in range(8):
        me.calc_tangents(uvmap=uv_name)
        tangents = np.empty(len(me.loops) * 3, dtype=np.float32)
        me.loops.foreach_get("tangent", tangents)
        lengths = np.linalg.norm(tangents.reshape(-1, 3).astype(np.float64), axis=1)
        faces = sorted(set(loop_face[np.abs(lengths - 1.0) > 1e-3].tolist()))
        me.free_tangents()
        if not faces:
            return len(flattened)
        if flattened.issuperset(faces):
            raise RuntimeError(f"faces {faces[:8]} keep degenerate tangents even when shaded flat")
        for face in faces:
            me.polygons[face].use_smooth = False
        flattened.update(faces)
    raise RuntimeError("degenerate tangents remain after 8 rounds of flat shading")


def uv_overlap(frames: dict, res: int) -> dict:
    """Share of used texels that two triangles claim (sampled at texel centres)."""
    uv = frames["uv"][frames["tri_loops"]]
    count = np.zeros((res, res), dtype=np.int32)
    pix = TP.uv_to_pixel(uv, res)
    for a, b, c in pix:
        x0 = max(int(np.floor(min(a[0], b[0], c[0]) - 0.5)), 0)
        x1 = min(int(np.ceil(max(a[0], b[0], c[0]) - 0.5)), res - 1)
        y0 = max(int(np.floor(min(a[1], b[1], c[1]) - 0.5)), 0)
        y1 = min(int(np.ceil(max(a[1], b[1], c[1]) - 0.5)), res - 1)
        if x1 < x0 or y1 < y0:
            continue
        denom = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(denom) < 1e-12:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        wa = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / denom
        wb = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / denom
        inside = (wa > 1e-9) & (wb > 1e-9) & (1.0 - wa - wb > 1e-9)
        count[y0 : y1 + 1, x0 : x1 + 1] += inside
    used = count > 0
    return {
        "used_share": round(float(used.mean()), 4),
        "overlapping_share_of_used": round(float((count > 1).sum() / max(used.sum(), 1)), 5),
    }


# ------------------------------------------------------------------------------- material


def rebuild_material(ob: bpy.types.Object, base_color: Path, metallic_roughness: Path,
                     normal_map: Path) -> None:
    if len(ob.data.materials) != 1:
        raise RuntimeError(f"expected one material, found {len(ob.data.materials)}")
    material = ob.data.materials[0]
    nodes, links = material.node_tree.nodes, material.node_tree.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")

    def source_image(socket_name: str) -> bpy.types.Node:
        link = bsdf.inputs[socket_name].links[0]
        node = link.from_node
        while node.type != "TEX_IMAGE":
            node = node.inputs[0].links[0].from_node
        return node

    replacements = (
        (source_image("Base Color"), base_color, "sRGB"),
        (source_image("Roughness"), metallic_roughness, "Non-Color"),
    )
    old_images = [node.image for node, _path, _space in replacements]
    for node, path, space in replacements:
        node.image = bpy.data.images.load(str(path))
        node.image.colorspace_settings.name = space
    for image in old_images:
        if image is not None and image.users == 0:
            bpy.data.images.remove(image)

    normal_node = nodes.new("ShaderNodeTexImage")
    normal_node.image = bpy.data.images.load(str(normal_map))
    normal_node.image.colorspace_settings.name = "Non-Color"
    normal_map_node = nodes.new("ShaderNodeNormalMap")
    normal_map_node.space = "TANGENT"
    normal_map_node.uv_map = ob.data.uv_layers.active.name
    links.new(normal_node.outputs["Color"], normal_map_node.inputs["Color"])
    links.new(normal_map_node.outputs["Normal"], bsdf.inputs["Normal"])


# ----------------------------------------------------------------------------------- main


def import_high(path: Path) -> bpy.types.Object:
    objects = [ob for ob in import_glb(path) if ob.type == "MESH"]
    if len(objects) != 1:
        raise RuntimeError(f"expected one mesh in the high source, got {len(objects)}")
    high_ob = objects[0]
    # Some exporters (the imp's download) place the mesh with node transforms: bake them in.
    world = high_ob.matrix_world.copy()
    high_ob.parent = None
    high_ob.data.transform(world)
    high_ob.matrix_world = Matrix.Identity(4)
    return high_ob


def main() -> None:
    args = parse_args()
    report: dict = {
        "rigged": args.rigged.name, "high": args.high.name, "lod_source": args.lod_source,
    }
    clear_scene()

    rigged = import_glb(args.rigged)
    armatures = [ob for ob in rigged if ob.type == "ARMATURE"]
    skinned = [ob for ob in rigged if ob.type == "MESH" and ob.find_armature() is not None]
    if len(armatures) != 1 or len(skinned) != 1:
        names = [ob.name for ob in rigged]
        raise RuntimeError(f"expected one armature and one skinned mesh, got {names}")
    arm, rigged_mesh = armatures[0], skinned[0]
    report["joints"] = len(arm.data.bones)
    report["clips"] = sorted(action.name for action in bpy.data.actions)
    report["side_swap"] = swap_sides(arm, rigged_mesh) if args.swap_sides else []
    report["rigged_mesh"] = {"triangles": triangle_count(rigged_mesh.data)}
    report["rigged_mesh"].update(weld_and_smooth(rigged_mesh))
    report["rigged_mesh"].update(topology(rigged_mesh))
    rigged_low, rigged_high = world_bounds(rigged_mesh)

    high_ob = import_high(args.high)
    high_low, high_high = world_bounds(high_ob)
    offset = max((high_low - rigged_low).length, (high_high - rigged_high).length)
    report["high_mesh"] = {
        "triangles": triangle_count(high_ob.data),
        "bounds_offset_to_rigged_mm": round(offset * 1000, 3),
        **weld_and_smooth(high_ob),
    }
    report["high_mesh"].update(topology(high_ob))

    # Reduce before grounding: collapse decimation does not depend on scale, and grounding the
    # reduced mesh puts exactly its own lowest point on the floor and its height at the target.
    if args.lod_source == "high":
        lod = high_ob.copy()
        lod.data = high_ob.data.copy()
        bpy.context.scene.collection.objects.link(lod)
        decimate(lod, args.triangles)
        report["weights"] = transfer_weights(lod, rigged_mesh, arm)
        name = rigged_mesh.name
        mesh_data = rigged_mesh.data
        bpy.data.objects.remove(rigged_mesh, do_unlink=True)
        bpy.data.meshes.remove(mesh_data)
        lod.name = name
    else:
        lod = rigged_mesh
        decimate(lod, args.triangles)
        limit_weights(lod)
    report["game_mesh"] = {
        "triangles": triangle_count(lod.data),
        "blender_vertices": len(lod.data.vertices),
        **topology(lod),
    }

    low, high = world_bounds(lod)
    matrix, scale = grounding_matrix(low, high, args.height)
    shift = matrix.to_translation()
    report["grounding"] = {
        "source_height_m": round(high.z - low.z, 6),
        "source_lowest_z_m": round(low.z, 6),
        # The same transform in glTF axes (Y up): p' = scale * p + translation.
        "scale": scale,
        "translation_gltf": [shift.x, shift.z, -shift.y],
    }
    lod.data.transform(matrix)
    high_ob.data.transform(matrix)
    report["grounding"]["location_channels_scaled"] = transform_rig(arm, matrix, scale)
    report["game_mesh"]["faces_shaded_flat_for_tangents"] = repair_degenerate_tangents(lod)

    surface = SN.high_surface(high_ob)
    report["game_mesh"]["distance_to_high_surface_mm"] = surface_distances(surface, lod)
    uv_name = lod.data.uv_layers.active.name
    frames = SN.low_corner_frames(lod, uv_name)
    report["game_mesh"]["uv"] = uv_overlap(frames, args.normal_size)

    shape, filled, core, folded = SN.shape_normal_map(
        surface, frames, 0, args.normal_size, args.gutter_px
    )
    P.write_png(str(args.normal_map_out), NM.encode_normal(shape))
    tilt = np.degrees(np.arccos(np.clip(shape[core][:, 2], -1.0, 1.0)))
    report["normal_map"] = {
        "file": args.normal_map_out.name,
        "size": args.normal_size,
        "texels_in_islands": int(core.sum()),
        "texels_with_gutter": int(filled.sum()),
        "folded_share": round(float(folded[core].mean()), 5),
        "tilt_degrees": percentiles(tilt, (50, 90, 99), 2),
    }

    bpy.data.objects.remove(high_ob, do_unlink=True)
    rebuild_material(lod, args.base_color, args.metallic_roughness, args.normal_map_out)

    select_only(arm, lod, active=arm)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(args.out), export_format="GLB", use_selection=True, export_skins=True,
        export_apply=False, export_animations=True, export_yup=True, export_tangents=True,
        export_image_format="AUTO",
    )
    report["output"] = args.out.name
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("PREPARE_OK", json.dumps(report["game_mesh"]))


main()
