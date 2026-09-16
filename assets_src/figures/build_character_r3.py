"""Round 3: real eye sockets, anisotropic head structure, curvature/AO-driven
wear textures, and a harder verification pass -- built on top of everything
round 1 and round 2 already established, not a rebuild.

  blender -b --factory-startup --python build_character_r3.py -- \\
      --character imp --tex-dir <r3 bootstrap>/generated \\
      --blend-dir <dir> --blend-dir-low <dir>/low --work <dir> \\
      --subsurf-high 2 --subsurf-low 1

Reused UNCHANGED via import (nothing in these files is touched):
  build_character.py    -- build_surface (limbs/digits/isotropic bumps/
                            creases), offset_bones, build_attachments,
                            resolve_seam_rules
  build_character_r2.py -- the LOD shape-bake pipeline (bake_shape_normal,
                            combine_and_write_lod_normals,
                            _duplicate_materials_with_normal,
                            _clone_mesh_object)
  surface.py, lofting.py, matlib.py, palette.py, rigbuild.py, stage.py,
  uvmap.py, clothsim.py, texgen_r2.py -- entirely unchanged

New in this file: build_surface_r3 (eye sockets / anisotropic bumps / mask
bevels from spec.py's round-3 keys), build_decor_r3 (a real eyeball seated
in the carved socket instead of round 2's flattened disc), the curvature+AO
bake and texgen_r3 material-texture swap, and check_socket_integrity (the
"does the eye socket survive a strong head turn" measurement).

--tex-dir must point at a bootstrap snapshot that already has every
material this character needs on disk (bootstrap_r3_textures.py builds one
from the round-2 snapshot plus the two new keratin materials) -- this
script REPLACES those images in memory once it has baked real masks from
this character's own mesh; the bootstrap only has to make the first
material load not crash before that mesh exists.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import build_character as BC  # noqa: E402
import build_character_r2 as BC2  # noqa: E402
import clothsim  # noqa: E402
import geomasks as GM  # noqa: E402
import headsculpt as HS  # noqa: E402
import matlib  # noqa: E402
import palette as P  # noqa: E402
import rigbuild  # noqa: E402
import spec as SPEC  # noqa: E402
import stage  # noqa: E402
import surface as SF  # noqa: E402
import texgen_r3 as T3  # noqa: E402
import uvmap  # noqa: E402

R2_CONTRAST_BASELINE = {
    # texgen_r2_report.json, round-2 "after" numbers -- fetched once and
    # repeated here so the round-3 report can print round-2 numbers beside
    # the new ones without depending on that file still being on disk.
    "imp_skin": dict(contrast=2.014117638621441, slope_deg=1.0623116605697733),
    "brute_flesh": dict(contrast=1.7358571735857173, slope_deg=1.4771270461876063),
    "cloak_fabric": dict(contrast=1.307417525371817, slope_deg=1.1701357085543398),
    "bone_mask": dict(contrast=1.45213363241794, slope_deg=4.218970896580015),
    "staff_wood": dict(contrast=1.4088757472630755, slope_deg=2.3353337729849653),
    "shoulder_plates": dict(contrast=1.3757979449340951, slope_deg=0.6366652783138643),
}
R3_SEED = 20260916 + 30

# Round 3b, correction 1: round 3a's eye kept the flat "em_eye" material at
# the round-2 emission strength (3.0) -- inside a real socket that floods
# the whole cavity with light and reads back exactly like the flat disc
# this round was supposed to remove (measured in the round-3a headshots,
# not just eyeballed). EYE_EMISSION is now the ONE knob controlling overall
# brightness; IRIS_REL/PUPIL_REL are brightness of the iris/pupil bands
# RELATIVE to that (see make_iris_eye_material) -- both numbers go in the
# round-3b report next to the round-3a value.
EYE_EMISSION = 1.35
IRIS_REL = 0.14
PUPIL_REL = 0.02
IRIS_POS = 0.78
PUPIL_POS = 0.90


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", required=True)
    ap.add_argument("--tex-dir", required=True, help="round-3 bootstrap snapshot generated/ dir")
    ap.add_argument("--blend-dir", required=True, help="high-variant .blend/.glb")
    ap.add_argument("--blend-dir-low", required=True, help="low-variant .blend/.glb")
    ap.add_argument("--work", required=True)
    ap.add_argument("--subsurf-high", type=int, default=2)
    ap.add_argument("--subsurf-low", type=int, default=1)
    ap.add_argument("--bake-samples", type=int, default=24)
    ap.add_argument("--ao-samples", type=int, default=48)
    ap.add_argument("--mask-res", type=int, default=P.TEXTURE_RESOLUTION)
    return ap.parse_args(argv)


# --------------------------------------------------------- r3 sculpting ---
def build_surface_r3(char):
    """build_character.build_surface's exact torso/limb/digit/isotropic-bump
    pipeline, plus the round-3 eye sockets, anisotropic bumps and mask
    bevels -- in that order, so a brow bump is free to catch a socket's rim
    vertices and blend into it, and a bevel (only used on the already-
    isotropically-bumped mask) runs last."""
    s = BC.build_surface(char)
    socket_info = {}
    for sock in char.get("eye_sockets", []):
        res = HS.carve_eye_socket(s, sock["at"], rim_radius=sock["rim_radius"],
                                  depth=sock["depth"], region=sock.get("region"))
        socket_info[sock["name"]] = res
        print("EYE_SOCKET", char["name"], sock["name"], res)
    for b in char.get("aniso_bumps", []):
        moved = HS.bump_aniso(s, b["center"], b["radii"], b["offset"], only_region=b.get("region"))
        if moved == 0:
            print("WARNING aniso_bump moved 0 vertices:", b)
    bevel_info = []
    for bv in char.get("bevels", []):
        res = HS.bevel_region_boundary(s, bv["region"], bv["width"], segments=bv.get("segments", 2),
                                       region_other=bv.get("region_other"))
        bevel_info.append(dict(bv, **res))
        print("BEVEL", char["name"], bv["region"], res)
    return s, socket_info, bevel_info


def make_iris_eye_material(name, color_hex, mult=EYE_EMISSION, iris_rel=IRIS_REL,
                           pupil_rel=PUPIL_REL, iris_pos=IRIS_POS, pupil_pos=PUPIL_POS,
                           attr_name="eye_facing"):
    """A real iris+pupil eye, not a flat emissive disc: a per-vertex
    "facing" attribute (0 at the back of the eyeball, 1 at the point that
    looks straight out of the socket -- baked in once at rest pose, see
    build_decor_r3) drives a hard-edged (CONSTANT interpolation) colour
    ramp: bright sclera for most of the ball, a darker iris ring, a near-
    black pupil at the very centre of the visible face. All the brightness
    control is the single Emission Strength `mult` -- the ramp only holds
    RELATIVE brightness per band -- so there is one number to tune and to
    report, not three.

    Using a baked mesh ATTRIBUTE instead of comparing the shading normal to
    a fixed world/object-space direction is deliberate: the attribute stays
    correct under an armature pose (the eye is skinned to the head bone) or
    a whole-object rotation (turntable, the in-game facing yaw) because it
    travels WITH the mesh through any deformation, whereas a fixed
    direction compared against Geometry.Normal would only be right at the
    exact rest pose it was measured at.
    """
    if name in bpy.data.materials:
        bpy.data.materials.remove(bpy.data.materials[name])
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = float(mult)
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = attr_name
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = 'CONSTANT'
    els = ramp.color_ramp.elements
    while len(els) > 1:
        els.remove(els[-1])
    base = P.hex_lin(color_hex)
    els[0].position = 0.0
    els[0].color = (base[0], base[1], base[2], 1.0)
    e_iris = els.new(float(iris_pos))
    e_iris.color = (base[0] * iris_rel, base[1] * iris_rel, base[2] * iris_rel, 1.0)
    e_pupil = els.new(float(pupil_pos))
    e_pupil.color = (base[0] * pupil_rel, base[1] * pupil_rel, base[2] * pupil_rel, 1.0)
    nt.links.new(attr.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    mat["textured"] = 0
    return mat


def build_decor_r3(char, arm_ob, tex_dir, dz, socket_info):
    """Like build_character_r2.build_decor, but any decor whose name matches
    a carved eye socket becomes a real (nearly round) eyeball SEATED in that
    socket's own measured floor, sized off the socket's own rim_radius --
    not the round-2 flattened-disc "at"/"radius" from spec.py, which is kept
    only as the fallback for decor with no socket (teeth, the soul's dark
    eye slits)."""
    import bmesh
    made = []
    for d in char.get("decor", []):
        mat_key = d["material"]
        sock = socket_info.get(d["name"])
        use_iris = sock is not None and mat_key in P.EMISSIVE
        if use_iris:
            eye_mat_name = "%s_%s_iris" % (char["name"], d["name"])
            make_iris_eye_material(eye_mat_name, P.EMISSIVE[mat_key]["color"])
            use_mat_key = eye_mat_name
        elif mat_key in P.EMISSIVE:
            matlib.make_emissive(mat_key)
            use_mat_key = mat_key
        else:
            matlib.ensure_materials([mat_key], tex_dir)
            use_mat_key = mat_key
        bm = bmesh.new()
        facing = None
        if sock is not None:
            radius = float(sock["rim_radius"]) * 0.5
            bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=14, radius=radius)
            outward = np.asarray(sock["normal"], dtype=np.float64)
            outward = outward / max(float(np.linalg.norm(outward)), 1e-9)
            # "facing" is baked ONCE here, at rest pose, from each vertex's
            # own local direction off the sphere's centre (the sphere is
            # still centred on the origin at this point, not yet moved to
            # the socket) -- a per-vertex mesh ATTRIBUTE, not a value
            # compared against the live shading normal, so it keeps
            # pointing "into the socket" under any later armature pose or
            # whole-object rotation instead of only at this exact rest pose.
            facing = []
            for v in bm.verts:
                local = np.array([v.co.x, v.co.y, v.co.z], dtype=np.float64)
                ln = float(np.linalg.norm(local))
                d_ = float(np.dot(local / ln, outward)) if ln > 1e-9 else 0.0
                facing.append((d_ + 1.0) * 0.5)
            center = np.asarray(sock["floor_center"], dtype=np.float64)
            for v in bm.verts:
                v.co.x += center[0]
                v.co.y += center[1]
                v.co.z += center[2] + dz
        else:
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
        if facing is not None:
            attr = me.color_attributes.new(name="eye_facing", type='FLOAT_COLOR', domain='POINT')
            farr = np.asarray(facing, dtype=np.float32)
            flat = np.empty(farr.size * 4, dtype=np.float32)
            flat[0::4] = farr
            flat[1::4] = farr
            flat[2::4] = farr
            flat[3::4] = 1.0
            attr.data.foreach_set("color", flat)
        me.materials.append(bpy.data.materials[use_mat_key])
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
        print("DECOR_R3", [o.name for o in made])
    return made


# -------------------------------------------------- texture regeneration ---
def swap_material_textures(mat, basecolor_path, normal_path, orm_path):
    """Point an EXISTING material's basecolor/normal/orm image nodes at
    freshly written PNGs, found by their link target (same technique
    build_character_r2._duplicate_materials_with_normal already uses to find
    the normal-map source -- comparing node TYPE/relationship, not identity,
    since repeated attribute access into a node tree's collections is not
    guaranteed to hand back the same wrapper object twice)."""
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:
        return False
    base_link = next((l for l in nt.links if l.to_node.name == bsdf.name
                      and l.to_socket.name == "Base Color"), None)
    if base_link is not None and base_link.from_node.type == 'TEX_IMAGE':
        base_link.from_node.image = bpy.data.images.load(basecolor_path, check_existing=False)
    nmap = next((n for n in nt.nodes if n.type == 'NORMAL_MAP'), None)
    if nmap is not None:
        src = next((l for l in nt.links if l.to_node.name == nmap.name
                   and l.to_socket.name == "Color"), None)
        if src is not None and src.from_node.type == 'TEX_IMAGE':
            img = bpy.data.images.load(normal_path, check_existing=False)
            img.colorspace_settings.name = 'Non-Color'
            src.from_node.image = img
    sep = next((n for n in nt.nodes if n.type == 'SEPARATE_COLOR'), None)
    if sep is not None:
        src = next((l for l in nt.links if l.to_node.name == sep.name
                   and l.to_socket.name == "Color"), None)
        if src is not None and src.from_node.type == 'TEX_IMAGE':
            img = bpy.data.images.load(orm_path, check_existing=False)
            img.colorspace_settings.name = 'Non-Color'
            src.from_node.image = img
    return True


def regenerate_textures(ob, work_dir, mask_res, ao_samples, bootstrap_tex_dir, slot_order=None):
    """Bake curvature+AO off `ob` (already at its final, post-subsurf shape
    and UV layout) and regenerate every TEXTURED material slot's basecolor/
    normal/orm with geometry-driven wear, swapping the new images into the
    SAME material datablocks (shared with the cage/low-LOD clones and any
    cloth object using them) in place.

    Returns a report keyed by material name with before/after contrast and
    normal-slope numbers plus the wear/bake statistics -- a slot whose bake
    came back degenerate (see geomasks.bake_masks) is reported and skipped
    rather than silently baked in as flat "wear".
    """
    masks, mask_report = GM.bake_masks(ob, res=mask_res, work_dir=work_dir, samples=ao_samples,
                                       slot_order=slot_order)
    print("MASK_REPORT", json.dumps(mask_report, indent=1))
    tex_out = os.path.join(work_dir, "tex_r3")
    report = {}
    for slot_idx, mat in enumerate(ob.data.materials):
        if mat is None or not mat.get("textured"):
            continue
        tex_id = P.MATERIAL_TEXTURE_MAP.get(mat.name)
        if tex_id is None:
            continue
        slot_masks = masks.get(slot_idx)
        if not slot_masks or "curvature" not in slot_masks or "ao" not in slot_masks:
            report[mat.name] = dict(skipped="no bake for this slot")
            continue
        degenerate = mask_report["slots"].get(slot_idx, {})
        if degenerate.get("curvature_degenerate") or degenerate.get("ao_degenerate"):
            report[mat.name] = dict(skipped="degenerate bake", bake_stats=degenerate)
            continue
        tile_m = matlib.tile_size_for(mat.name, bootstrap_tex_dir) or mat.get("tile_size_m") or 1.0
        spec_row = P.MATERIALS[mat.name]
        seed = P.stable_seed(R3_SEED, tex_id)
        before = R2_CONTRAST_BASELINE.get(tex_id)
        res = T3.regenerate_with_wear(tex_id, tex_id, spec_row["albedo"], tile_m, seed,
                                      slot_masks["curvature"], slot_masks["ao"], tex_out,
                                      metallic_base=spec_row["m"], before=before)
        mat_dir = os.path.join(tex_out, tex_id)
        basecolor_path = os.path.join(mat_dir, "%s_basecolor.png" % tex_id)
        ok = swap_material_textures(
            mat, basecolor_path, os.path.join(mat_dir, "%s_normal.png" % tex_id),
            os.path.join(mat_dir, "%s_orm.png" % tex_id))
        if not ok:
            report[mat.name] = dict(skipped="swap_material_textures found no BSDF to wire up")
            continue
        # Re-open the file just written and confirm it is not degenerate --
        # "gegen die erwartete Textur abgleichen", not trust the function
        # call that wrote it: a wrong node-graph assumption in
        # swap_material_textures could report `ok=True` while the image
        # actually assigned is stale or blank.
        written = P.read_png(basecolor_path)
        if float(written.std()) < 1.0:
            report[mat.name] = dict(skipped="written basecolor is degenerate (std=%.3f)"
                                    % float(written.std()))
            continue
        res["swapped"] = ok
        res["bake_stats"] = degenerate
        report[mat.name] = res
        print("TEXGEN_R3 %-14s contrast %s -> %.3f  slope %s -> %.3f deg  metal_mean %.3f"
              % (mat.name,
                 ("%.3f" % before["contrast"]) if before else "n/a",
                 res["after"]["albedo_contrast"],
                 ("%.3f" % before["slope_deg"]) if before else "n/a",
                 res["after"]["normal"]["mean_deg"], res["wear"]["metallic_mean"]))
    return report


def regenerate_textures_verified(ob, work_dir, mask_res, ao_samples, bootstrap_tex_dir,
                                 expected_tex_ids, max_attempts=5):
    """regenerate_textures, but checked against what the character actually
    needs and retried at the FULL-REBAKE level (not just the single retry
    inside geomasks._bake_with_retry) until every expected material slot
    genuinely has a fresh, non-degenerate texture -- or the run is aborted
    outright rather than saving a .blend/.glb with a silently incomplete
    material.

    Round 3a treated a failed slot as an acceptable, reported fallback to
    the bootstrap texture; the correction explicitly asks for the opposite:
    fluctuating bakes are tolerable, REPORTING an incomplete result as
    finished is not. This is the gate that turns that fallback into a hard
    failure.

    Each attempt also rotates which material slot is baked first (helps the
    genuinely session-flaky slots; disproven as a fix for a deterministic
    per-material failure -- see geomasks.bake_masks' own docstring, which
    also documents the pure-Python fallback bake that actually resolves
    that case).
    """
    n_slots = len(ob.data.materials)
    last_report, last_missing = None, None
    for attempt in range(1, max_attempts + 1):
        rotation = (attempt - 1) % max(n_slots, 1)
        slot_order = list(range(rotation, n_slots)) + list(range(0, rotation))
        report = regenerate_textures(ob, work_dir, mask_res, ao_samples, bootstrap_tex_dir,
                                     slot_order=slot_order)
        # `report` is keyed by material NAME (e.g. "plates"), `expected_tex_ids`
        # are texture ids (e.g. "shoulder_plates") -- resolve through the same
        # map used everywhere else so the two vocabularies actually line up.
        missing = []
        for mat_name, v in report.items():
            if "after" not in v and P.MATERIAL_TEXTURE_MAP.get(mat_name) in expected_tex_ids:
                missing.append(mat_name)
        if not missing:
            print("TEXGEN_R3_VERIFY attempt %d/%d (slot_order=%s): all %d material(s) confirmed"
                 % (attempt, max_attempts, slot_order, len(report)))
            return report
        print("TEXGEN_R3_VERIFY attempt %d/%d (slot_order=%s) FAILED for %s -- rebaking the whole set"
             % (attempt, max_attempts, slot_order, missing))
        last_report, last_missing = report, missing
    raise RuntimeError(
        "texgen_r3 verification failed after %d full rebakes (every slot-order rotation tried) "
        "for material(s) %s -- aborting this build WITHOUT writing a .blend/.glb rather than "
        "deliver an incomplete result. Last attempt's report: %s"
        % (max_attempts, last_missing, json.dumps(last_report, default=str)))


# ------------------------------------------------------- socket integrity ---
def check_socket_integrity(ob, arm_ob, socket_info, dz, pose):
    """Under a pose (a strong head turn), verify a carved eye socket's rim
    and floor are still meaningfully apart -- proof the cavity did not flatten
    or invert under skinning. Uses straight-line 3D distance between a rim
    sample and the floor rather than a projection onto the REST-pose normal,
    because that normal itself rotates with the head; a rigid, correctly-
    skinned rotation preserves point-to-point distance regardless of the
    rotation angle, which is exactly the property being checked for.
    """
    me = ob.data
    coords = np.array([tuple(v.co) for v in me.vertices])
    picks = {}
    for name, sock in socket_info.items():
        floor_target = np.asarray(sock["floor_center"]) + np.array([0.0, 0.0, dz])
        # The rim reference is the socket's own recorded PRE-CARVE seed
        # position (`seed_center`, the nearest original face found before
        # any inset/push), not floor + normal*depth: on a coarse base mesh
        # that reconstructed point can land closer to the floor than to any
        # real rim vertex, and nearest-vertex lookup then picks the SAME
        # vertex for both ends -- measured on imp's own dry run (rest_dist_m
        # came back exactly 0.0). seed_center sits on the original surface
        # right at the socket's edge, which is a real, already-recorded
        # point rather than an approximation.
        rim_target = np.asarray(sock["seed_center"]) + np.array([0.0, 0.0, dz])
        floor_idx = int(np.argmin(np.linalg.norm(coords - floor_target, axis=1)))
        rim_idx = int(np.argmin(np.linalg.norm(coords - rim_target, axis=1)))
        picks[name] = dict(floor_idx=floor_idx, rim_idx=rim_idx,
                           rest_dist_m=float(np.linalg.norm(coords[rim_idx] - coords[floor_idx])))

    rigbuild.apply_pose(arm_ob, pose)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    posed_me = ob.evaluated_get(dg).to_mesh()
    posed = np.array([tuple(v.co) for v in posed_me.vertices])
    ob.evaluated_get(dg).to_mesh_clear()
    rigbuild.apply_pose(arm_ob, {})
    bpy.context.view_layer.update()

    out = {}
    for name, p in picks.items():
        if posed.shape[0] != coords.shape[0]:
            out[name] = dict(error="vertex count changed under pose")
            continue
        posed_dist = float(np.linalg.norm(posed[p["rim_idx"]] - posed[p["floor_idx"]]))
        frac = posed_dist / p["rest_dist_m"] if p["rest_dist_m"] > 1e-9 else None
        out[name] = dict(rest_dist_m=round(p["rest_dist_m"], 5), posed_dist_m=round(posed_dist, 5),
                         retained_fraction=round(frac, 3) if frac is not None else None,
                         collapsed=bool(frac is not None and frac < 0.5))
    return out


# ------------------------------------------------------------------ main ---
def main():
    args = parse_args()
    scene = stage.reset_scene()
    stage.build_world(scene)
    char = SPEC.get(args.character)
    name = char["name"]

    matlib.ensure_materials(sorted(set(char["materials"].values())), args.tex_dir)

    s, socket_info, bevel_info = build_surface_r3(char)
    manifold = s.check_manifold()
    cage_stats = s.stats()
    ob = s.to_object(name, char["materials"])
    # `s.free()` only releases the bmesh; `s` itself (in particular
    # `s.regions`, a plain name->id dict) stays valid, exactly the same
    # reliance build_character.py's and build_character_r2.py's own main()
    # already have on this -- resolve_seam_rules is called after free() there
    # too.
    seam_rules = BC.resolve_seam_rules(char, s)
    s.free()
    print("CAGE", cage_stats, manifold)
    if manifold["non_manifold_edges"] or manifold["loose_verts"]:
        print("WARNING: surface is not a clean closed manifold", manifold)

    n_seams = uvmap.mark_seams(ob, seam_rules)
    uvmap.unwrap(ob)
    tile_for_slot = {i: matlib.tile_size_for(m.name, args.tex_dir)
                     for i, m in enumerate(ob.data.materials)}
    density = uvmap.scale_to_tile_size(ob, tile_for_slot)
    spread = uvmap.density_spread(ob)
    overlap = uvmap.overlap_check(ob)
    print("UV seams=%d" % n_seams, density, spread, overlap)

    cage = ob.copy()
    cage.data = ob.data.copy()
    cage.name = cage.data.name = name + "_cage"
    bpy.context.collection.objects.link(cage)
    cage.hide_render = True

    ob_low = BC2._clone_mesh_object(ob, name + "_low")

    SF.apply_subsurf(ob, levels=args.subsurf_high, render_levels=args.subsurf_high)
    SF.shade_smooth(ob)

    # --- round 3: curvature/AO from the ACTUAL high mesh, wear into the
    # textures, swap into the materials -- BEFORE the low variant is
    # subdivided, so its own material-slot copy (a plain Python object copy,
    # made below) already points at the new images too.
    mask_work = os.path.join(args.work, "masks_%s" % name)
    os.makedirs(mask_work, exist_ok=True)
    expected_tex_ids = sorted({P.MATERIAL_TEXTURE_MAP[k] for k in set(char["materials"].values())
                               if k in P.MATERIAL_TEXTURE_MAP})
    texgen_report = regenerate_textures_verified(ob, mask_work, args.mask_res, args.ao_samples,
                                                 args.tex_dir, expected_tex_ids)

    SF.apply_subsurf(ob_low, levels=args.subsurf_low, render_levels=args.subsurf_low)
    SF.shade_smooth(cage)
    SF.shade_smooth(ob_low)

    zmin = min(v.co.z for o in (ob, cage) for v in o.data.vertices)
    for o in (ob, cage, ob_low):
        for v in o.data.vertices:
            v.co.z -= zmin
        o.data.update()
    dz = -zmin
    bones = BC.offset_bones(char, dz)
    print("GROUND offset %.4f m" % dz)

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

    decor_obs = build_decor_r3(char, arm_ob, args.tex_dir, dz, socket_info)
    attachments = BC.build_attachments(char, arm_ob, args.tex_dir, dz)

    rigbuild.parent_with_auto_weights([ob_low], arm_ob)
    audit_before_low = rigbuild.audit_weights(ob_low, arm_ob, scale=char["height"])
    filled_low = rigbuild.fill_unweighted(ob_low, arm_ob) if audit_before_low["unweighted"] else 0
    rigbuild.repair_weights(ob_low)
    audit_low = rigbuild.audit_weights(ob_low, arm_ob, scale=char["height"])
    print("WEIGHTS(low) before", audit_before_low, "filled", filled_low)
    print("WEIGHTS(low) after ", audit_low)

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

    # Socket-integrity check: the LAST pose in spec.py's list is "head turn"
    # for every character; verify each carved socket's rim-to-floor distance
    # survives it instead of assuming a rotation this large cannot break the
    # skinning near the eyes.
    socket_integrity = {}
    if socket_info:
        head_turn_pose = next(p for lbl, p in char["poses"] if lbl == "head turn")
        # Stronger than the sheet's own "head turn" pose (44-52 degrees in
        # spec.py): the brief specifically asks for at least one check with
        # a STRONGLY turned head, so this doubles the rotation on every
        # bone that pose already uses rather than inventing new ones.
        strong_turn_pose = {b: tuple(a * 1.8 for a in rot) for b, rot in head_turn_pose.items()}
        socket_integrity = check_socket_integrity(ob, arm_ob, socket_info, dz, strong_turn_pose)
        print("SOCKET_INTEGRITY", socket_integrity)

    lod_work = os.path.join(args.work, "lod_%s" % name)
    lod_normals = BC2.combine_and_write_lod_normals(ob_low, args.tex_dir, lod_work,
                                                    P.TEXTURE_RESOLUTION, args.bake_samples,
                                                    ob, name)
    BC2._duplicate_materials_with_normal(ob_low, lod_normals, "lod")

    for mesh in [ob.data, cage.data, ob_low.data]:
        attr = mesh.attributes.get("region")
        if attr is not None:
            mesh.attributes.remove(attr)

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
                              export_rest_position_armature=True, export_yup=True,
                              export_tangents=True)

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
                              export_rest_position_armature=True, export_yup=True,
                              export_tangents=True)

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
        eye_sockets=socket_info,
        socket_integrity=socket_integrity,
        bevels=bevel_info,
        texgen_r3=texgen_report,
        cloth=(clothsim.report(cloth_obs) if cloth_obs else []),
        attachments=[o.name for o in attachments], decor=[o.name for o in decor_obs],
        packed_images=packed,
        outputs=dict(blend=blend_path, glb=glb_path, blend_low=blend_path_low, glb_low=glb_path_low),
    )
    os.makedirs(args.work, exist_ok=True)
    P.save_json(os.path.join(args.work, "%s_build_r3.json" % name), stats)
    print("BUILD R3 OK", json.dumps(dict(
        character=name, tris_high=stats_high["tris"], tris_low=stats_low["tris"],
        bones=len(bones), unweighted_high=audit_high["unweighted"],
        unweighted_low=audit_low["unweighted"], sockets=list(socket_info.keys()),
        socket_integrity=socket_integrity, lod_bake_slots=sorted(lod_normals.keys()))))


if __name__ == "__main__":
    main()
