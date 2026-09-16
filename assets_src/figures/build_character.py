"""Build one character end to end and write the .blend and glTF deliverables.

  blender -b --factory-startup --python build_character.py -- \
      --character imp --tex-dir <snapshot>/generated --blend-dir <dir> \
      --work <dir> [--subsurf 2]

Order matters and is deliberate:

  surface -> loop displacement -> creases -> seams -> unwrap -> texel density
  -> subdivision -> armature -> automatic weights -> audit and repair -> cloth
  -> pack -> save -> export

The cage is unwrapped BEFORE subdivision (the standard workflow: subdivision
interpolates the UVs, unwrapping a dense mesh does not give better islands), and
a copy of the cage is kept in the file so the wireframe shot can show the real
topology instead of a subdivided haze.
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import matlib  # noqa: E402
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
    ap.add_argument("--tex-dir", required=True, help="snapshot generated/ directory")
    ap.add_argument("--blend-dir", required=True, help="where .blend and .glb go")
    ap.add_argument("--work", required=True, help="where the stats JSON goes")
    ap.add_argument("--subsurf", type=int, default=2)
    return ap.parse_args(argv)


# ----------------------------------------------------------------- mesh ---
def _norm(v):
    a = np.asarray(v, dtype=np.float64)
    n = float(np.linalg.norm(a))
    return a / n if n > 1e-12 else np.array([0.0, 1.0, 0.0])


def digit_chain(center, direction, length):
    """A claw: out along `direction` with a downward curl at the tip, so it
    hooks instead of sticking out like a spike."""
    c = np.asarray(center, dtype=np.float64)
    d = _norm(direction)
    curl = np.array([0.0, 0.0, -0.30 * length])
    return [tuple(c), tuple(c + d * (0.45 * length) + curl * 0.2),
            tuple(c + d * (0.80 * length) + curl * 0.6), tuple(c + d * length + curl)]


def build_surface(char):
    s = SF.Surface(nseg=char["nseg"])
    t = char["torso"]
    s.build_torso(t["ctrl"], char["stations"], t["keys"], t["region"], u_hint=t["u_hint"])
    tips = []
    for limb in char["limbs"]:
        sides = [False, True] if limb.get("mirror") else [False]
        for mirror in sides:
            segs = limb["seed"]["segments"]
            ctrl = limb["ctrl"]
            if mirror:
                segs = SF.mirror_segments(segs, char["nseg"])
                ctrl = SF.mirror_ctrl(ctrl)
            seed = s.patch(limb["seed"]["stations"], segs)
            if not seed:
                raise SystemExit("limb %s: seed patch is empty" % limb["name"])
            tip = s.grow(seed, ctrl, limb["keys"], limb["steps"], limb["region"],
                         ease=limb.get("ease", 2))
            tips.append((limb, mirror, tip))
    # Digits last: each consumes one cap face, so the caps are sorted first.
    for limb, mirror, tip in tips:
        digits = limb.get("digits")
        if not digits:
            continue
        axis = np.asarray(limb.get("digit_sort_axis", (0.0, 0.0, 1.0)), dtype=np.float64)
        if mirror:
            axis = axis * np.array([-1.0, 1.0, 1.0])
        ordered = s.tip_faces_sorted(tip, axis)
        for d in digits:
            if d["pick"] >= len(ordered):
                continue
            face = ordered[d["pick"]]
            direction = np.asarray(d["direction"], dtype=np.float64)
            if mirror:
                direction = direction * np.array([-1.0, 1.0, 1.0])
            ctrl = digit_chain(face.calc_center_median(), direction, d["length"])
            s.grow_digit(face, ctrl, d["radii"], d["steps"], d["region"])
    for b in char.get("bumps", []):
        s.bump(b["center"], b["radius"], b["offset"], only_region=b.get("region"))
    for rule in char.get("creases", []):
        rid = s.regions.get(rule["region"])
        if rid is None:
            continue
        s.crease_ring(lambda e, rid=rid: len(e.link_faces) > 0
                      and all(f[s.region_layer] == rid for f in e.link_faces), rule["value"])
    return s


def offset_bones(char, dz):
    bones = []
    for b in rigbuild.expand_bones(char["bones"]):
        nb = dict(b)
        nb["head"] = (b["head"][0], b["head"][1], b["head"][2] + dz)
        nb["tail"] = (b["tail"][0], b["tail"][1], b["tail"][2] + dz)
        bones.append(nb)
    return bones


def ground_objects(objects):
    """Drop the character so its lowest point sits exactly on the floor.

    This has to happen AFTER subdivision: the limit surface lies inside the
    control cage, so grounding the cage leaves the subdivided claws hovering
    above the tiles. Returns the offset so the bones can follow it.
    """
    zmin = min(v.co.z for ob in objects for v in ob.data.vertices)
    for ob in objects:
        for v in ob.data.vertices:
            v.co.z -= zmin
        ob.data.update()
    return -zmin


def build_attachments(char, arm_ob, tex_dir, dz):
    """Held props (the damned soul's staff and its orb).

    A prop is rigid, so instead of heat weights it gets one vertex group holding
    the whole mesh at weight 1 on the bone it is held by, plus an armature
    modifier. That follows the hand exactly and still exports as a normal
    skinned primitive, which bone-parenting would not.
    """
    import bmesh
    made = []
    for att in char.get("attachments", []):
        keys = [att["material"]] + ([att["orb"]["material"]] if att.get("orb") else [])
        matlib.ensure_materials([k for k in keys if k not in P.EMISSIVE], tex_dir)
        for k in keys:
            if k in P.EMISSIVE:
                matlib.make_emissive(k)
        s = SF.Surface(nseg=att.get("nseg", 8))
        ctrl = [(c[0], c[1], c[2] + dz) for c in att["ctrl"]]
        s.build_torso(ctrl, att.get("stations", 14), att["keys"], att["region"],
                      u_hint=(1.0, 0.0, 0.0))
        ob = s.to_object("%s_%s" % (char["name"], att["name"]), {att["region"]: att["material"]})
        s.free()
        if att.get("orb"):
            orb = att["orb"]
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=orb["radius"])
            for v in bm.verts:
                v.co.x += orb["at"][0]
                v.co.y += orb["at"][1]
                v.co.z += orb["at"][2] + dz
            me = bpy.data.meshes.new("%s_orb" % char["name"])
            bm.to_mesh(me)
            bm.free()
            me.materials.append(bpy.data.materials[orb["material"]])
            for p in me.polygons:
                p.use_smooth = True
            ob_orb = bpy.data.objects.new("%s_orb" % char["name"], me)
            bpy.context.collection.objects.link(ob_orb)
            made.append((ob_orb, att["bone"]))
        made.append((ob, att["bone"]))
    out = []
    for ob, bone in made:
        SF.shade_smooth(ob)
        vg = ob.vertex_groups.new(name=bone)
        vg.add([v.index for v in ob.data.vertices], 1.0, 'REPLACE')
        ob.parent = arm_ob
        md = ob.modifiers.new("armature", 'ARMATURE')
        md.object = arm_ob
        out.append(ob)
    if out:
        print("ATTACHMENTS", [o.name for o in out])
    return out


def resolve_seam_rules(char, s):
    """Region names in seam rules -> the region ids the surface actually used."""
    out = []
    for rule in char.get("seams", []):
        r = dict(rule)
        if "region_border" in r:
            ids = [s.regions.get(x) if isinstance(x, str) else x for x in r["region_border"]]
            if any(i is None for i in ids):
                continue
            r["region_border"] = tuple(ids)
        out.append(r)
    return out


# ----------------------------------------------------------------- main ---
def main():
    args = parse_args()
    scene = stage.reset_scene()
    stage.build_world(scene)
    char = SPEC.get(args.character)
    name = char["name"]

    mat_report = matlib.ensure_materials(sorted(set(char["materials"].values())), args.tex_dir)

    s = build_surface(char)
    manifold = s.check_manifold()
    cage_stats = s.stats()
    ob = s.to_object(name, char["materials"])
    s.free()
    print("CAGE", cage_stats, manifold)
    if manifold["non_manifold_edges"] or manifold["loose_verts"]:
        print("WARNING: surface is not a clean closed manifold", manifold)

    # ---- UVs on the cage -------------------------------------------------
    seam_rules = resolve_seam_rules(char, s)
    n_seams = uvmap.mark_seams(ob, seam_rules)
    uvmap.unwrap(ob)
    tile_for_slot = {i: matlib.tile_size_for(m.name, args.tex_dir)
                     for i, m in enumerate(ob.data.materials)}
    density = uvmap.scale_to_tile_size(ob, tile_for_slot)
    spread = uvmap.density_spread(ob)
    overlap = uvmap.overlap_check(ob)
    print("UV seams=%d" % n_seams, density, spread, overlap)

    # ---- keep the cage for the wireframe shot, then subdivide ------------
    cage = ob.copy()
    cage.data = ob.data.copy()
    cage.name = cage.data.name = name + "_cage"
    bpy.context.collection.objects.link(cage)
    cage.hide_render = True

    if args.subsurf > 0:
        SF.apply_subsurf(ob, levels=args.subsurf, render_levels=args.subsurf)
    SF.shade_smooth(ob)
    SF.shade_smooth(cage)
    dz = ground_objects([ob, cage])
    bones = offset_bones(char, dz)
    print("GROUND offset %.4f m (applied after subdivision)" % dz)
    final_tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    final_quads = sum(1 for p in ob.data.polygons if len(p.vertices) == 4)
    print("MESH after subsurf: verts=%d polys=%d tris=%d quads=%d"
          % (len(ob.data.vertices), len(ob.data.polygons), final_tris, final_quads))

    # ---- armature and weights -------------------------------------------
    arm_ob = rigbuild.build_armature(name + "_rig", bones)
    cloth_obs = []
    if char.get("cloth"):
        import clothsim
        cloth_obs = clothsim.build(char, ob, arm_ob, args.tex_dir, dz=dz)

    rigbuild.parent_with_auto_weights([ob, cage] + cloth_obs, arm_ob)
    audit_before = rigbuild.audit_weights(ob, arm_ob, scale=char["height"])
    filled = rigbuild.fill_unweighted(ob, arm_ob) if audit_before["unweighted"] else 0
    rigbuild.repair_weights(ob)
    audit = rigbuild.audit_weights(ob, arm_ob, scale=char["height"])
    print("WEIGHTS before", audit_before, "filled", filled)
    print("WEIGHTS after ", audit)

    attachments = build_attachments(char, arm_ob, args.tex_dir, dz)

    deform = rigbuild.deformation_check(ob, arm_ob, dict(char["poses"][0][1]))
    print("DEFORM", deform)

    # ---- export ----------------------------------------------------------
    for mesh in [ob.data, cage.data]:
        attr = mesh.attributes.get("region")
        if attr is not None:
            mesh.attributes.remove(attr)
    packed = matlib.pack_all_images()
    os.makedirs(args.blend_dir, exist_ok=True)
    blend_path = os.path.join(args.blend_dir, "%s.blend" % name)
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    # glTF: cage excluded, skin included, rest pose preserved.
    cage.hide_set(True)
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    arm_ob.select_set(True)
    for c in cloth_obs + attachments:
        c.select_set(True)
    bpy.context.view_layer.objects.active = arm_ob
    glb_path = os.path.join(args.blend_dir, "%s.glb" % name)
    bpy.ops.export_scene.gltf(filepath=glb_path, export_format='GLB', use_selection=True,
                              export_skins=True, export_apply=False, export_animations=False,
                              export_rest_position_armature=True, export_yup=True)

    stats = dict(
        character=name, height_m=char["height"], ground_offset_m=round(dz, 5),
        cage=cage_stats, manifold=manifold, subsurf_levels=args.subsurf,
        final=dict(verts=len(ob.data.vertices), polys=len(ob.data.polygons),
                   tris=final_tris, quads=final_quads),
        bones=dict(total=len(bones), deform=sum(1 for b in bones if b.get("deform") is not False)),
        uv=dict(seam_edges=n_seams, per_material=density, spread=spread, overlap=overlap),
        materials=mat_report, weights=audit, weights_before=audit_before,
        unweighted_filled=filled, deformation=deform,
        cloth=(__import__("clothsim").report(cloth_obs) if cloth_obs else []),
        attachments=[o.name for o in attachments], packed_images=packed,
        outputs=dict(blend=blend_path, glb=glb_path),
    )
    os.makedirs(args.work, exist_ok=True)
    P.save_json(os.path.join(args.work, "%s_build.json" % name), stats)
    print("BUILD OK", json.dumps(dict(character=name, tris=final_tris,
                                      bones=len(bones), unweighted=audit["unweighted"],
                                      spikes=audit["spikes"])))


if __name__ == "__main__":
    main()
