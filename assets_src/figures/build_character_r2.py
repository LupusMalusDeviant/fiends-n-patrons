"""Round 2: build a character with the round-1 approach (kept) plus the fixes
from the round-1 render review -- a bound and shaped hand grip, faces (eyes,
brow/jaw/eye-slit shaping), and a ship-grade LOD pair (a high variant at the
round-1 subdivision level, and a low variant one level down with the missing
curvature recovered as a baked normal map).

  blender -b --factory-startup --python build_character_r2.py -- \\
      --character imp --tex-dir <r2 snapshot>/generated \\
      --blend-dir <dir> --blend-dir-low <dir>/low --work <dir> \\
      --subsurf-high 2 --subsurf-low 1

Everything round 1 built (surface.py, lofting.py, matlib.py, rigbuild.py,
uvmap.py, stage.py, clothsim.py) is reused unchanged via build_character.py's
own functions; only spec.py gained new, additive data (decor props, one more
grip finger, more bumps) and this script, which does not touch build_character.py
so round 1 stays exactly reproducible from its own command line.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import build_character as BC  # noqa: E402
import clothsim  # noqa: E402
import matlib  # noqa: E402
import normalmap as NM  # noqa: E402
import palette as P  # noqa: E402
import rigbuild  # noqa: E402
import spec as SPEC  # noqa: E402
import stage  # noqa: E402
import surface as SF  # noqa: E402
import uvmap  # noqa: E402


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", required=True)
    ap.add_argument("--tex-dir", required=True)
    ap.add_argument("--blend-dir", required=True, help="high-variant .blend/.glb")
    ap.add_argument("--blend-dir-low", required=True, help="low-variant .blend/.glb")
    ap.add_argument("--work", required=True)
    ap.add_argument("--subsurf-high", type=int, default=2)
    ap.add_argument("--subsurf-low", type=int, default=1)
    ap.add_argument("--bake-samples", type=int, default=24)
    return ap.parse_args(argv)


# ------------------------------------------------------------------ decor ---
def build_decor(char, arm_ob, tex_dir, dz):
    """Small rigid props bound to a single bone: emissive eyes, a dark eye
    slit, a hint of teeth. Same binding mechanism as the staff/orb attachment
    (vertex group named after the bone, weight 1, Armature modifier) --
    verified under pose in diag_staff2.py to move rigidly and correctly with
    the bone, so it is reused here rather than invented twice.
    """
    import bmesh
    made = []
    for d in char.get("decor", []):
        mat_key = d["material"]
        if mat_key in P.EMISSIVE:
            matlib.make_emissive(mat_key)
        else:
            matlib.ensure_materials([mat_key], tex_dir)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=8, radius=1.0)
        rx, ry, rz = d["radius"]
        at = d["at"]
        for v in bm.verts:
            v.co.x = v.co.x * rx + at[0]
            v.co.y = v.co.y * ry + at[1]
            v.co.z = v.co.z * rz + at[2] + dz
        me = bpy.data.meshes.new("%s_%s" % (char["name"], d["name"]))
        bm.to_mesh(me)
        bm.free()
        me.materials.append(bpy.data.materials[mat_key])
        for p in me.polygons:
            p.use_smooth = True
        ob = bpy.data.objects.new(me.name, me)
        bpy.context.collection.objects.link(ob)
        vg = ob.vertex_groups.new(name=d["bone"])
        vg.add([v.index for v in me.vertices], 1.0, 'REPLACE')
        ob.parent = arm_ob
        md = ob.modifiers.new("armature", 'ARMATURE')
        md.object = arm_ob
        made.append(ob)
    if made:
        print("DECOR", [o.name for o in made])
    return made


# -------------------------------------------------------------------- LOD ---
def _clone_mesh_object(ob, name):
    c = ob.copy()
    c.data = ob.data.copy()
    c.name = c.data.name = name
    bpy.context.collection.objects.link(c)
    return c


def _duplicate_materials_with_normal(ob, image_by_slot, suffix):
    """Clone each material slot of `ob`, swapping only the normal-map image
    node's image for the combined (baked shape + original detail) one."""
    new_mats = {}
    for slot_idx, mat in enumerate(list(ob.data.materials)):
        if mat is None or slot_idx not in image_by_slot:
            continue
        nm = mat.copy()
        nm.name = "%s_%s" % (mat.name, suffix)
        # Find the material's ShaderNodeNormalMap and swap its upstream
        # TexImage for the combined (baked shape + original detail) one.
        nmap_node = next((n for n in nm.node_tree.nodes if n.type == 'NORMAL_MAP'), None)
        if nmap_node is not None:
            # Name comparison, not `is` -- see the note in combine_and_write_lod_normals.
            for link in list(nm.node_tree.links):
                if link.to_node.name == nmap_node.name and link.to_socket.name == "Color":
                    src = link.from_node
                    if src.type == 'TEX_IMAGE':
                        src.image = image_by_slot[slot_idx]
        ob.data.materials[slot_idx] = nm
        new_mats[slot_idx] = nm
    return new_mats


def bake_shape_normal(high_ob, low_ob, res, samples, work_dir, tag):
    """Bake the HIGH mesh's shape (as seen from the LOW cage) into a tangent
    space normal image per material slot of `low_ob`, selected-to-active.

    Returns {material_slot_index: HxWx3 float32 normal-in-[-1,1] array}, or an
    empty dict if baking is not available in this Blender build/session --
    callers must treat that as "keep the existing detail normal", not an error.
    """
    scene = bpy.context.scene
    prev_engine = scene.render.engine
    out = {}
    try:
        bpy.ops.preferences.addon_enable(module='cycles')
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'CPU'
        scene.cycles.samples = samples
        bpy.context.view_layer.objects.active = low_ob
        bpy.ops.object.select_all(action='DESELECT')

        bake_images = {}
        for slot_idx, mat in enumerate(low_ob.data.materials):
            if mat is None:
                continue
            img = bpy.data.images.new("%s_%s_shapebake_%d" % (low_ob.name, tag, slot_idx),
                                      res, res, alpha=False, float_buffer=True)
            img.colorspace_settings.name = 'Non-Color'
            nt = mat.node_tree
            node = nt.nodes.new("ShaderNodeTexImage")
            node.image = img
            for n in nt.nodes:
                n.select = False
            node.select = True
            nt.nodes.active = node
            bake_images[slot_idx] = (img, node, nt)

        high_ob.select_set(True)
        low_ob.select_set(True)
        bpy.context.view_layer.objects.active = low_ob

        bpy.ops.object.bake(type='NORMAL', use_selected_to_active=True,
                            cage_extrusion=0.03, max_ray_distance=0.15,
                            normal_space='TANGENT')

        for slot_idx, (img, node, nt) in bake_images.items():
            w, h = img.size
            buf = np.empty(w * h * 4, dtype=np.float32)
            img.pixels.foreach_get(buf)
            rgb = buf.reshape(h, w, 4)[::-1, :, :3]  # Blender stores bottom row first
            out[slot_idx] = rgb * 2.0 - 1.0
            os.makedirs(work_dir, exist_ok=True)
            NM_png = NM.encode_normal(out[slot_idx])
            P.write_png(os.path.join(work_dir, "%s_shapebake_%d.png" % (tag, slot_idx)), NM_png)
            nt.nodes.remove(node)
            bpy.data.images.remove(img)
        print("BAKE OK", tag, "slots", list(out.keys()))
    except Exception as exc:  # pragma: no cover - environment dependent
        print("BAKE SKIPPED (%s): %r -- low variant keeps the original detail normal" % (tag, exc))
        out = {}
    finally:
        scene.render.engine = prev_engine
    return out


def combine_and_write_lod_normals(low_ob, tex_dir, work_dir, res, samples, high_ob, tag):
    """Bake the shape delta and blend it (Reoriented Normal Mapping) with each
    material's existing detail normal map; returns {slot_index: new Image}."""
    baked = bake_shape_normal(high_ob, low_ob, res, samples, work_dir, tag)
    result_images = {}
    for slot_idx, mat in enumerate(low_ob.data.materials):
        if mat is None or not mat.get("textured"):
            continue
        nmap_node = next((n for n in mat.node_tree.nodes if n.type == 'NORMAL_MAP'), None)
        if nmap_node is None:
            continue
        # Compare by node NAME, not `is`: repeated attribute access into a node
        # tree's `nodes`/`links` collections can hand back distinct Python
        # wrapper objects for the same underlying node, so `is` silently never
        # matches -- this is what made every slot fall through to "no source
        # image found" on the first attempt despite the link genuinely being
        # there (confirmed with a name/type-based check in diag_normalnode.py).
        src = next((l.from_node for l in mat.node_tree.links
                   if l.to_node.name == nmap_node.name and l.to_socket.name == "Color"), None)
        if src is None or src.image is None:
            continue
        detail_path = bpy.path.abspath(src.image.filepath_raw or src.image.filepath)
        if not os.path.exists(detail_path):
            continue
        detail = NM.decode_normal(P.read_png(detail_path))
        if slot_idx in baked:
            shape = baked[slot_idx]
            if shape.shape[:2] != detail.shape[:2]:
                continue
            combined = NM.reoriented_normal_blend(shape, detail)
        else:
            combined = detail  # bake unavailable: keep the detail-only map
        combined_u8 = NM.encode_normal(combined)
        out_path = os.path.join(work_dir, "%s_slot%d_combined_normal.png" % (tag, slot_idx))
        P.write_png(out_path, combined_u8)
        img = bpy.data.images.load(out_path, check_existing=False)
        img.colorspace_settings.name = 'Non-Color'
        result_images[slot_idx] = img
    return result_images


# ------------------------------------------------------------------ main ---
def main():
    args = parse_args()
    scene = stage.reset_scene()
    stage.build_world(scene)
    char = SPEC.get(args.character)
    name = char["name"]

    matlib.ensure_materials(sorted(set(char["materials"].values())), args.tex_dir)

    s = BC.build_surface(char)
    manifold = s.check_manifold()
    cage_stats = s.stats()
    ob = s.to_object(name, char["materials"])
    s.free()
    print("CAGE", cage_stats, manifold)
    if manifold["non_manifold_edges"] or manifold["loose_verts"]:
        print("WARNING: surface is not a clean closed manifold", manifold)

    seam_rules = BC.resolve_seam_rules(char, s)
    n_seams = uvmap.mark_seams(ob, seam_rules)
    uvmap.unwrap(ob)
    tile_for_slot = {i: matlib.tile_size_for(m.name, args.tex_dir)
                     for i, m in enumerate(ob.data.materials)}
    density = uvmap.scale_to_tile_size(ob, tile_for_slot)
    spread = uvmap.density_spread(ob)
    overlap = uvmap.overlap_check(ob)
    print("UV seams=%d" % n_seams, density, spread, overlap)

    # Pristine control-mesh copies for BOTH the wireframe cage (as round 1) and
    # the low-LOD body, taken before either subdivision is applied.
    cage = ob.copy()
    cage.data = ob.data.copy()
    cage.name = cage.data.name = name + "_cage"
    bpy.context.collection.objects.link(cage)
    cage.hide_render = True

    ob_low = _clone_mesh_object(ob, name + "_low")

    SF.apply_subsurf(ob, levels=args.subsurf_high, render_levels=args.subsurf_high)
    SF.apply_subsurf(ob_low, levels=args.subsurf_low, render_levels=args.subsurf_low)
    SF.shade_smooth(ob)
    SF.shade_smooth(cage)
    SF.shade_smooth(ob_low)

    # Ground everything off the HIGH limit surface (round 1's reasoning: the
    # limit surface lies inside the control cage), then apply the SAME offset
    # to the low mesh and the bones so the LOD swap never shifts the character.
    zmin = min(v.co.z for o in (ob, cage) for v in o.data.vertices)
    for o in (ob, cage, ob_low):
        for v in o.data.vertices:
            v.co.z -= zmin
        o.data.update()
    dz = -zmin
    bones = BC.offset_bones(char, dz)
    print("GROUND offset %.4f m (shared by both LOD levels)" % dz)

    def _mesh_stats(o):
        tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
        return dict(verts=len(o.data.vertices), polys=len(o.data.polygons), tris=tris)

    stats_high = _mesh_stats(ob)
    stats_low = _mesh_stats(ob_low)
    print("MESH high", stats_high, "low", stats_low)

    arm_ob = rigbuild.build_armature(name + "_rig", bones)

    cloth_obs = []
    if char.get("cloth"):
        cloth_obs = clothsim.build(char, ob, arm_ob, args.tex_dir, dz=dz)

    decor_obs = build_decor(char, arm_ob, args.tex_dir, dz)
    attachments = BC.build_attachments(char, arm_ob, args.tex_dir, dz)

    # Low-variant weights first: solved independently at its own resolution so
    # the heat solver sees the actual low-poly topology.
    rigbuild.parent_with_auto_weights([ob_low], arm_ob)
    audit_before_low = rigbuild.audit_weights(ob_low, arm_ob, scale=char["height"])
    filled_low = rigbuild.fill_unweighted(ob_low, arm_ob) if audit_before_low["unweighted"] else 0
    rigbuild.repair_weights(ob_low)
    audit_low = rigbuild.audit_weights(ob_low, arm_ob, scale=char["height"])
    print("WEIGHTS(low) before", audit_before_low, "filled", filled_low)
    print("WEIGHTS(low) after ", audit_low)

    # High-variant weights. Round 1's own imp build already hit this (buried in
    # its work JSON, not in the headline "0 unweighted" number): Blender's bone
    # heat solver is visibility-based, and imp's thin creased claws/horns block
    # enough line-of-sight at the subsurf-2 density that it fails for EVERY
    # vertex, silently falling back to fill_unweighted's rigid nearest-bone
    # assignment for the whole body -- no smooth blending at any joint.
    # Confirmed with diag_heat_bisect2.py: identical bones and bumps solve
    # cleanly at subsurf 0/1 and only fail at subsurf 2, so it is mesh density
    # tripping the solver, not the round-2 face/grip changes. Since the LOW
    # mesh above solves cleanly, a failed HIGH solve now transfers those real
    # heat weights (nearest-face interpolation) instead of collapsing to rigid
    # per-vertex nearest-bone -- strictly better, and it reuses the LOD pair
    # this script already builds rather than a second, cruder repair path.
    rigbuild.parent_with_auto_weights([ob, cage] + cloth_obs, arm_ob)
    audit_before = rigbuild.audit_weights(ob, arm_ob, scale=char["height"])
    transferred = 0
    if audit_before["unweighted"]:
        bpy.ops.object.select_all(action='DESELECT')
        ob.select_set(True)
        ob_low.select_set(True)
        bpy.context.view_layer.objects.active = ob_low
        bpy.ops.object.data_transfer(data_type='VGROUP_WEIGHTS',
                                     vert_mapping='POLYINTERP_NEAREST',
                                     layers_select_src='ALL', layers_select_dst='NAME')
        bpy.ops.object.select_all(action='DESELECT')
        transferred = audit_before["unweighted"]
        print("WEIGHTS(high) heat solve failed for %d/%d vertices -> transferred from low"
              % (audit_before["unweighted"], audit_before["vertices"]))
    audit_after_transfer = rigbuild.audit_weights(ob, arm_ob, scale=char["height"])
    filled = rigbuild.fill_unweighted(ob, arm_ob) if audit_after_transfer["unweighted"] else 0
    rigbuild.repair_weights(ob)
    audit_high = rigbuild.audit_weights(ob, arm_ob, scale=char["height"])
    print("WEIGHTS(high) before", audit_before, "transferred", transferred, "filled", filled)
    print("WEIGHTS(high) after ", audit_high)

    deform_high = rigbuild.deformation_check(ob, arm_ob, dict(char["poses"][0][1]))
    deform_low = rigbuild.deformation_check(ob_low, arm_ob, dict(char["poses"][0][1]))
    print("DEFORM high", deform_high, "low", deform_low)

    # Ship-grade LOD: bake the high surface's shape onto the low mesh as a
    # normal map and blend it with each material's existing detail normal.
    lod_work = os.path.join(args.work, "lod_%s" % name)
    lod_normals = combine_and_write_lod_normals(ob_low, args.tex_dir, lod_work,
                                                P.TEXTURE_RESOLUTION, args.bake_samples,
                                                ob, name)
    _duplicate_materials_with_normal(ob_low, lod_normals, "lod")

    for mesh in [ob.data, cage.data, ob_low.data]:
        attr = mesh.attributes.get("region")
        if attr is not None:
            mesh.attributes.remove(attr)

    # ---------------------------------------------------------- export high ---
    ob_low.hide_set(True)
    bpy.context.collection.objects.unlink(ob_low)
    packed = matlib.pack_all_images()
    os.makedirs(args.blend_dir, exist_ok=True)
    blend_path = os.path.join(args.blend_dir, "%s.blend" % name)
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    cage.hide_set(True)
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    arm_ob.select_set(True)
    for c in cloth_obs + attachments + decor_obs:
        c.select_set(True)
    bpy.context.view_layer.objects.active = arm_ob
    glb_path = os.path.join(args.blend_dir, "%s.glb" % name)
    bpy.ops.export_scene.gltf(filepath=glb_path, export_format='GLB', use_selection=True,
                              export_skins=True, export_apply=False, export_animations=False,
                              export_rest_position_armature=True, export_yup=True)

    # ----------------------------------------------------------- export low ---
    bpy.context.collection.objects.link(ob_low)
    ob.hide_set(True)
    cage.hide_set(True)
    bpy.context.collection.objects.unlink(ob)
    bpy.context.collection.objects.unlink(cage)
    os.makedirs(args.blend_dir_low, exist_ok=True)
    blend_path_low = os.path.join(args.blend_dir_low, "%s.blend" % name)
    bpy.ops.wm.save_as_mainfile(filepath=blend_path_low)

    bpy.ops.object.select_all(action='DESELECT')
    ob_low.select_set(True)
    arm_ob.select_set(True)
    for c in cloth_obs + attachments + decor_obs:
        c.select_set(True)
    bpy.context.view_layer.objects.active = arm_ob
    glb_path_low = os.path.join(args.blend_dir_low, "%s.glb" % name)
    bpy.ops.export_scene.gltf(filepath=glb_path_low, export_format='GLB', use_selection=True,
                              export_skins=True, export_apply=False, export_animations=False,
                              export_rest_position_armature=True, export_yup=True)

    stats = dict(
        character=name, height_m=char["height"], ground_offset_m=round(dz, 5),
        cage=cage_stats, manifold=manifold,
        subsurf_levels=dict(high=args.subsurf_high, low=args.subsurf_low),
        high=stats_high, low=stats_low,
        bones=dict(total=len(bones), deform=sum(1 for b in bones if b.get("deform") is not False)),
        uv=dict(seam_edges=n_seams, per_material=density, spread=spread, overlap=overlap),
        weights_high=audit_high, weights_high_before=audit_before,
        weights_high_transferred_from_low=transferred, unweighted_filled_high=filled,
        weights_low=audit_low, weights_low_before=audit_before_low, unweighted_filled_low=filled_low,
        deformation_high=deform_high, deformation_low=deform_low,
        lod_bake_slots=sorted(lod_normals.keys()),
        cloth=(clothsim.report(cloth_obs) if cloth_obs else []),
        attachments=[o.name for o in attachments], decor=[o.name for o in decor_obs],
        packed_images=packed,
        outputs=dict(blend=blend_path, glb=glb_path, blend_low=blend_path_low, glb_low=glb_path_low),
    )
    os.makedirs(args.work, exist_ok=True)
    P.save_json(os.path.join(args.work, "%s_build_r2.json" % name), stats)
    print("BUILD R2 OK", json.dumps(dict(
        character=name, tris_high=stats_high["tris"], tris_low=stats_low["tris"],
        bones=len(bones), unweighted_high=audit_high["unweighted"],
        transferred_from_low=transferred,
        unweighted_low=audit_low["unweighted"], lod_bake_slots=sorted(lod_normals.keys()))))


if __name__ == "__main__":
    main()
