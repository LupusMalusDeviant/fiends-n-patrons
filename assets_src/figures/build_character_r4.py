"""Round 4: every textured material gets its own UV layout with no shared
texels, the base pattern is applied in object space, and curvature, occlusion
and the LOD shape normal are computed without the Cycles bake operator.

  blender -b --factory-startup --python build_character_r4.py -- \\
      --character imp --tex-dir <runde3>/generated \\
      --blend-dir <ziel> --blend-dir-low <ziel>/low --work <arbeit>

Why, measured on the shipped round-3 figures (details in texproject.py):

- Round 3 laid UV islands out at real-world scale over a tiling texture. That
  was right while textures only tiled; round 3 then baked geometry into them.
  Tiled islands share texels (imp skin 55 %, imp head 81 %, soul cloak 81 %,
  brute flesh 80 %), and the LOD shape bake let body parts overwrite each
  other: the head's shared texels deviated 70 degrees (p90) against 9 in its
  unshared ones -- the dark, angular spots on the head.
- The base pattern was generated in UV space, so it jumps at every UV seam
  (median 16 brightness levels against 0.7 inside an island) -- the patchwork
  on arms, legs and tail.

Round 4 therefore packs each textured material into its own 0..1 square
(uvmap's own overlap check only compared islands before wrapping, so it never
saw the sharing), rasterises position, normal, curvature and occlusion of the
finished high mesh into that layout, samples the tileable base pattern by
position (texproject.triplanar), and derives the detail normal with the real
texel size of the new layout. Occlusion is ray-cast per vertex against the
mesh itself, and the LOD shape normal comes from the high level's own normal
at the nearest surface point (shapenormal.py): Cycles' selected-to-active bake
wrote exactly inverted normals into 39 % of the imp's horn texels even with
the shared texels gone. Everything here is deterministic.

Reused unchanged: build_character_r3 (surface with sockets and bevels, decor,
socket check, texture swap), build_character_r2 (material copy per LOD),
build_character (bones, attachments, seam rules).
"""
import argparse
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402

import build_character as BC  # noqa: E402
import build_character_r2 as BC2  # noqa: E402
import build_character_r3 as BC3  # noqa: E402
import clothsim  # noqa: E402
import geomasks as GM  # noqa: E402
import matlib  # noqa: E402
import normalmap as NM  # noqa: E402
import palette as P  # noqa: E402
import rigbuild  # noqa: E402
import shapenormal as SN  # noqa: E402
import spec as SPEC  # noqa: E402
import stage  # noqa: E402
import surface as SF  # noqa: E402
import texgen_r2 as T2  # noqa: E402
import texgen_r3 as T3  # noqa: E402
import texproject as TP  # noqa: E402
import uvmap  # noqa: E402

R4_SEED = 20260916 + 40
MAX_SHARED_FRACTION = 0.002   # of a material's used texels, checked at 256 x 256
MIN_USED_FRACTION = 0.15      # packed alone: 0.22-0.66 measured; packed together: 0.005-0.15
OVERLAP_CHECK_RES = 256
AO_REACH_OF_HEIGHT = 0.3      # occlusion rays reach 30 % of the character's height
STRAP_ANGLE_DEG = 28.0        # round 3's cloak strap angle, now across the body
STRAP_WIDTH_OF_TILE = 0.09


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
    ap.add_argument("--ao-samples", type=int, default=64)
    ap.add_argument("--uv-margin-px", type=int, default=8)
    ap.add_argument("--gutter-px", type=int, default=4)
    return ap.parse_args(argv)


# ------------------------------------------------------------ mesh data ---
def mesh_arrays(ob):
    """Plain arrays of a mesh: vertex positions, per-corner UV and normal,
    and per loop-triangle corner loops, vertices, material and polygon."""
    me = ob.data
    me.calc_loop_triangles()
    nv, nl, nt = len(me.vertices), len(me.loops), len(me.loop_triangles)
    co = np.empty(nv * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    uv = np.empty(nl * 2, dtype=np.float32)
    me.uv_layers[P.UV_NAME].data.foreach_get("uv", uv)
    nrm = np.empty(nl * 3, dtype=np.float32)
    me.corner_normals.foreach_get("vector", nrm)
    tri_loops = np.empty(nt * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("loops", tri_loops)
    tri_verts = np.empty(nt * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("vertices", tri_verts)
    tri_mat = np.empty(nt, dtype=np.int32)
    me.loop_triangles.foreach_get("material_index", tri_mat)
    tri_poly = np.empty(nt, dtype=np.int32)
    me.loop_triangles.foreach_get("polygon_index", tri_poly)
    return dict(co=co.reshape(nv, 3).astype(np.float64), uv=uv.reshape(nl, 2).astype(np.float64),
                nrm=nrm.reshape(nl, 3).astype(np.float64), tri_loops=tri_loops.reshape(nt, 3),
                tri_verts=tri_verts.reshape(nt, 3), tri_mat=tri_mat, tri_poly=tri_poly)


def textured_slots(ob):
    return {i: m for i, m in enumerate(ob.data.materials)
            if m is not None and P.MATERIAL_TEXTURE_MAP.get(m.name) is not None}


# ------------------------------------------------------------- UV layout ---
CAGE_ATTRIBUTES = {"position", ".edge_verts", ".corner_vert", ".corner_edge", "material_index",
                   "region", "sharp_face", "crease_edge", "uv_seam", "sharp_edge"}


def rebuild_cage_canonically(ob):
    """Rebuild the cage mesh from plain data, faces in an order that depends
    only on the geometry.

    surface.py and headsculpt.py build the cage while iterating Python sets of
    BMesh elements, and those follow memory addresses. Measured across Blender
    processes: the vertex positions came out identical, but face and corner
    order and the orientation of edges did not -- Blender's unwrap and pack
    follow that order, so each run got a different UV layout, and the
    subdivided high level held the same points in a different order (4.5 % of
    them), which moved the ray-cast occlusion samples. Rebuilt like this, two
    processes produced byte-identical UVs and a byte-identical high level.
    """
    me = ob.data
    unknown = {a.name for a in me.attributes} - CAGE_ATTRIBUTES
    if unknown or len(me.uv_layers) or len(ob.vertex_groups):
        raise RuntimeError("round 4: the cage carries data the rebuild would drop: %s, uv %d, groups %d"
                           % (sorted(unknown), len(me.uv_layers), len(ob.vertex_groups)))
    co = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    polys = [list(p.vertices) for p in me.polygons]
    mats = np.empty(len(me.polygons), dtype=np.int32)
    me.polygons.foreach_get("material_index", mats)
    face_attrs = {name: [d.value for d in me.attributes[name].data]
                  for name in ("region", "sharp_face") if name in me.attributes}
    edge_attrs = {name: {tuple(sorted(e.vertices)): me.attributes[name].data[e.index].value for e in me.edges}
                  for name in ("crease_edge", "uv_seam", "sharp_edge") if name in me.attributes}
    specs = {name: (me.attributes[name].data_type, me.attributes[name].domain)
             for name in list(face_attrs) + list(edge_attrs)}

    def rounded(c):
        return tuple(round(float(x), 5) for x in c)

    order = sorted(range(len(polys)), key=lambda i: (int(mats[i]), rounded(co[polys[i]].mean(axis=0)),
                                                     sorted(polys[i])))
    new = bpy.data.meshes.new(me.name)
    new.from_pydata([tuple(map(float, c)) for c in co], [], [polys[i] for i in order])
    for m in me.materials:
        new.materials.append(m)
    new.polygons.foreach_set("material_index", [int(mats[i]) for i in order])
    for name, values in face_attrs.items():
        data_type, domain = specs[name]
        attr = new.attributes.get(name) or new.attributes.new(name, data_type, domain)
        attr.data.foreach_set("value", [values[i] for i in order])
    for name, by_pair in edge_attrs.items():
        data_type, domain = specs[name]
        attr = new.attributes.get(name) or new.attributes.new(name, data_type, domain)
        attr.data.foreach_set("value", [by_pair[tuple(sorted(e.vertices))] for e in new.edges])
    new.update()
    old = ob.data
    ob.data = new
    bpy.data.meshes.remove(old)
    new.name = ob.name


def sort_faces_canonically(ob):
    """Face order of a finished part (cloth, attachments, decor) that depends
    only on its geometry. These parts come out of the same set-driven
    construction as the cage; their points are identical from run to run, but
    the triangle order in the exported index buffers was not. Unlike the cage
    they already carry UVs, weights and parenting, so they keep their data and
    only their faces are re-ordered."""
    if ob.type != 'MESH':
        return
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.index_update()
    bm.faces.index_update()
    faces = sorted(bm.faces, key=lambda f: (f.material_index,
                                            tuple(round(float(x), 5) for x in f.calc_center_median()),
                                            sorted(v.index for v in f.verts)))
    rank = {f.index: r for r, f in enumerate(faces)}
    bm.faces.sort(key=lambda f: rank[f.index])
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def pack_materials_unique(ob, slots, margin_px, res=P.TEXTURE_RESOLUTION):
    """Pack each textured material's islands into its own 0..1 square.

    Every other face is hidden while one material is packed: with them only
    deselected, pack_islands still packed all materials into one shared square
    (measured on the first imp build: skin 15 % of its texture, claws 0.5 %)."""
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    ob.data.uv_layers[P.UV_NAME].active = True
    for slot in sorted(slots):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='FACE')
        bpy.ops.mesh.reveal(select=False)
        bpy.ops.mesh.select_all(action='DESELECT')
        ob.active_material_index = slot
        bpy.ops.object.material_slot_select()
        bpy.ops.mesh.hide(unselected=True)
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', rotate=True, rotate_method='ANY',
                                scale=True, merge_overlap=False, margin_method='FRACTION',
                                margin=float(margin_px) / res, shape_method='CONCAVE')
        bpy.ops.mesh.reveal(select=False)
        bpy.ops.object.mode_set(mode='OBJECT')
        _move_into_unit_square(ob, slot)
    bpy.ops.object.select_all(action='DESELECT')


def _move_into_unit_square(ob, slot):
    """pack_islands packs into the UDIM tile nearest to where the islands
    were; move a material that landed in another tile back by whole tiles."""
    me = ob.data
    uvl = me.uv_layers[P.UV_NAME]
    loops = [li for p in me.polygons if p.material_index == slot for li in p.loop_indices]
    if not loops:
        return
    coords = np.array([tuple(uvl.data[li].uv) for li in loops])
    shift = np.floor(coords.min(axis=0) + 1e-6)
    if not shift.any():
        return
    for li, co in zip(loops, coords - shift):
        uvl.data[li].uv = (float(co[0]), float(co[1]))


def uv_layout_report(ob, slots, res=P.TEXTURE_RESOLUTION):
    me = ob.data
    arrays = mesh_arrays(ob)
    islands = np.asarray(uvmap.island_ids(me))
    report = {}
    for slot, mat in sorted(slots.items()):
        sel = arrays["tri_mat"] == slot
        if not sel.any():
            continue
        tri_uv = arrays["uv"][arrays["tri_loops"][sel]]
        tri_pos = arrays["co"][arrays["tri_verts"][sel]]
        tri_island = islands[arrays["tri_poly"][sel]]
        shared, used = TP.shared_texels(tri_uv, tri_island, OVERLAP_CHECK_RES)
        uv_per_m = TP.uv_units_per_metre(tri_uv, tri_pos)
        report[mat.name] = dict(
            islands=int(len(set(tri_island.tolist()))), shared_fraction=round(shared, 5),
            used_fraction=round(used, 4), uv_units_per_m=round(uv_per_m, 4),
            texel_density_px_per_m=round(uv_per_m * res, 1),
            u_range=[round(float(tri_uv[..., 0].min()), 4), round(float(tri_uv[..., 0].max()), 4)],
            v_range=[round(float(tri_uv[..., 1].min()), 4), round(float(tri_uv[..., 1].max()), 4)])
    return report


def check_uv_layout(report):
    bad = {}
    for name, r in report.items():
        outside = r["u_range"][0] < -1e-4 or r["v_range"][0] < -1e-4 \
            or r["u_range"][1] > 1 + 1e-4 or r["v_range"][1] > 1 + 1e-4
        if r["shared_fraction"] > MAX_SHARED_FRACTION or r["used_fraction"] < MIN_USED_FRACTION or outside:
            bad[name] = r
    if bad:
        raise RuntimeError("UV layout shares texels, wastes its square or leaves it -- aborting "
                           "before anything is baked into it: %s" % json.dumps(bad))


# --------------------------------------------------------------- textures ---
def strap_mask_3d(positions, tile_m):
    """Round 3's diagonal leather straps on the cloak, placed by position
    instead of UV so they run on across seams: one strap per tile along a
    direction tilted STRAP_ANGLE_DEG in the x/z plane, with a stitched line
    down its centre."""
    a = math.radians(STRAP_ANGLE_DEG)
    direction = np.array([math.cos(a), 0.0, math.sin(a)])
    t = np.mod(positions @ direction, tile_m)
    width = STRAP_WIDTH_OF_TILE * tile_m
    d = np.abs(t - width * 0.5)
    band = np.clip(1.0 - d / (width * 0.5), 0.0, 1.0)
    seam = np.clip(1.0 - d / (width * 0.06), 0.0, 1.0)
    return band, seam


def regenerate_textures_r4(ob, char, tex_dir, work_dir, args, res=P.TEXTURE_RESOLUTION):
    me = ob.data
    t0 = time.time()
    arrays = mesh_arrays(ob)
    curv01, curv_stats = GM.vertex_curvature01(me)
    ao01 = GM.vertex_ao_raycast(me, n_samples=args.ao_samples,
                                max_dist=AO_REACH_OF_HEIGHT * char["height"], seed=R4_SEED)
    report = dict(curvature_vertex_stats=curv_stats,
                  ao_vertex_stats=dict(mean=float(ao01.mean()), std=float(ao01.std()),
                                       min=float(ao01.min()), max=float(ao01.max())),
                  vertex_data_seconds=round(time.time() - t0, 1), materials={})
    print("TEXGEN_R4 vertex data", json.dumps(report["ao_vertex_stats"]), report["vertex_data_seconds"], "s")
    tex_out = os.path.join(work_dir, "tex_r4")
    for slot_idx, mat in sorted(textured_slots(ob).items()):
        t1 = time.time()
        tex_id = P.MATERIAL_TEXTURE_MAP[mat.name]
        sel = arrays["tri_mat"] == slot_idx
        if not sel.any():
            continue
        tri_loops, tri_verts = arrays["tri_loops"][sel], arrays["tri_verts"][sel]
        tri_uv = arrays["uv"][tri_loops]
        tri_pos = arrays["co"][tri_verts]
        corner = np.concatenate([tri_pos, arrays["nrm"][tri_loops],
                                 curv01[tri_verts][..., None], ao01[tri_verts][..., None]], axis=2)
        values, core = TP.rasterize(tri_uv, corner, res)
        values, filled = TP.dilate(values, core, args.gutter_px)
        pos = values[..., 0:3]
        nrm = values[..., 3:6]
        nrm /= np.maximum(np.linalg.norm(nrm, axis=2, keepdims=True), 1e-12)
        # 0 marks "no surface here" for apply_geo_wear's percentiles, so real
        # data is kept strictly above it.
        curv = np.where(filled, np.clip(values[..., 6], 1e-3, 1.0), 0.0)
        ao = np.where(filled, np.clip(values[..., 7], 1e-3, 1.0), 0.0)

        tile_m = matlib.tile_size_for(mat.name, tex_dir) or mat.get("tile_size_m") or 1.0
        spec_row = P.MATERIALS[mat.name]
        rng = np.random.default_rng(P.stable_seed(R4_SEED, tex_id))
        rgb0, height0, rough0, ao_synth0, _ = T3.generate_base(tex_id, spec_row["albedo"], tile_m, rng, res=res)
        base = np.concatenate([rgb0.astype(np.float64), height0[..., None], rough0[..., None],
                               ao_synth0[..., None]], axis=2)
        full = np.broadcast_to(base.reshape(-1, base.shape[2]).mean(axis=0), base.shape).copy()
        full[filled] = TP.triplanar(base, pos[filled], nrm[filled], tile_m)
        rgb_u8 = np.round(np.clip(full[..., 0:3], 0, 255)).astype(np.uint8)
        height, rough, ao_synth = full[..., 3], np.clip(full[..., 4], 0.05, 1.0), np.clip(full[..., 5], 0, 1)

        # The cloak's straps are the one UV-space feature apply_geo_wear adds;
        # it is left out there (neutral kind) and added by position below.
        wear_kind = "cloak_fabric_r4" if tex_id == "cloak_fabric" else tex_id
        rgb, height, rough, metal, wear = T3.apply_geo_wear(
            wear_kind, rgb_u8, height, rough, curv, ao, rng, metallic_base=spec_row["m"])
        if tex_id == "cloak_fabric":
            band = np.zeros(filled.shape)
            seam = np.zeros(filled.shape)
            band[filled], seam[filled] = strap_mask_3d(pos[filled], tile_m)
            rgbf = rgb.astype(np.float64)
            rgbf = rgbf * (1.0 - band[..., None]) + T3.LEATHER_HEX[None, None, :] * band[..., None]
            rgbf = rgbf * (1.0 - 0.6 * seam[..., None])
            rgb = np.round(np.clip(rgbf, 0, 255)).astype(np.uint8)
            rough = rough * (1.0 - band) + 0.46 * band
            height = height - 0.0012 * seam + 0.0004 * band

        uv_per_m = TP.uv_units_per_metre(tri_uv, tri_pos)
        texel_m = 1.0 / (uv_per_m * res)
        normal = NM.encode_normal(NM.height_to_normal(height, (texel_m, texel_m)))
        ao_combined = np.clip(ao_synth * (0.5 + 0.5 * ao), 0.0, 1.0)
        orm = T3.build_orm_field(rough, ao_combined, metal)

        mat_dir = os.path.join(tex_out, tex_id)
        os.makedirs(mat_dir, exist_ok=True)
        paths = {k: os.path.join(mat_dir, "%s_%s.png" % (tex_id, k)) for k in ("basecolor", "normal", "orm")}
        P.write_png(paths["basecolor"], rgb)
        P.write_png(paths["normal"], normal)
        P.write_png(paths["orm"], orm)
        for kind, arr in (("curvature", curv), ("ao", ao)):
            P.write_png(os.path.join(mat_dir, "%s_mask_%s.png" % (tex_id, kind)),
                        np.round(np.clip(arr, 0, 1) * 255).astype(np.uint8)[..., None].repeat(3, axis=2))
        with open(os.path.join(mat_dir, "%s.json" % tex_id), "w", encoding="utf-8") as fh:
            json.dump(dict(id=tex_id, kind=tex_id, tile_size_m=[tile_m, tile_m], texel_m=texel_m,
                           generator="texgen_r4 (build_character_r4)", round=4), fh, indent=1, sort_keys=True)

        written = P.read_png(paths["basecolor"])
        if float(written[filled].std()) < 1.0:
            raise RuntimeError("round 4: basecolor for %s is degenerate (std %.3f)"
                               % (mat.name, float(written[filled].std())))
        if not BC3.swap_material_textures(mat, paths["basecolor"], paths["normal"], paths["orm"]):
            raise RuntimeError("round 4: no Principled BSDF to receive the textures of %s" % mat.name)

        report["materials"][mat.name] = dict(
            texture=tex_id, tile_size_m=tile_m, uv_units_per_m=round(uv_per_m, 4),
            texel_density_px_per_m=round(uv_per_m * res, 1), covered_fraction=round(float(core.mean()), 4),
            albedo_contrast=T2.albedo_contrast(rgb[core]),
            normal=T2.normal_slope_stats(normal[core]),
            mean_srgb=[round(float(v), 1) for v in rgb[core].mean(axis=0)],
            wear=wear, seconds=round(time.time() - t1, 1))
        print("TEXGEN_R4 %-12s density %.0f px/m  contrast %.3f  slope %.2f deg  %.1f s"
              % (mat.name, uv_per_m * res, report["materials"][mat.name]["albedo_contrast"],
                 report["materials"][mat.name]["normal"]["mean_deg"], time.time() - t1))
    return report


def lod_normals_r4(high_ob, low_ob, work_dir, tag, gutter_px, res=P.TEXTURE_RESOLUTION):
    """Shape normal of the high level on the low level's UV layout, blended
    with each material's detail normal; returns ({slot: Image}, report)."""
    os.makedirs(work_dir, exist_ok=True)
    surface = SN.high_surface(high_ob)
    frames = SN.low_corner_frames(low_ob, P.UV_NAME)
    images, report = {}, {}
    for slot, mat in sorted(textured_slots(low_ob).items()):
        if not (frames["tri_mat"] == slot).any():
            continue
        t0 = time.time()
        shape, _filled, core, folded = SN.shape_normal_map(surface, frames, slot, res, gutter_px)
        P.write_png(os.path.join(work_dir, "%s_shape_%d.png" % (tag, slot)), NM.encode_normal(shape))
        nmap = next((n for n in mat.node_tree.nodes if n.type == 'NORMAL_MAP'), None)
        src = None if nmap is None else next(
            (l.from_node for l in mat.node_tree.links
             if l.to_node.name == nmap.name and l.to_socket.name == "Color"), None)
        if src is None or src.image is None:
            raise RuntimeError("round 4: %s has no detail normal image to blend with" % mat.name)
        detail = NM.decode_normal(P.read_png(bpy.path.abspath(src.image.filepath_raw or src.image.filepath)))
        combined = NM.reoriented_normal_blend(shape, detail)
        out_path = os.path.join(work_dir, "%s_slot%d_combined_normal.png" % (tag, slot))
        P.write_png(out_path, NM.encode_normal(combined))
        img = bpy.data.images.load(out_path, check_existing=False)
        img.colorspace_settings.name = 'Non-Color'
        images[slot] = img
        deviation = NM.slope_degrees(shape[core])
        report[mat.name] = dict(median_deg=round(float(np.median(deviation)), 2),
                                p90_deg=round(float(np.percentile(deviation, 90)), 2),
                                over_90_deg_fraction=round(float((deviation > 90).mean()), 5),
                                folded_fraction=round(float(folded[core].mean()), 5),
                                seconds=round(time.time() - t0, 1))
        print("SHAPE_R4 %-12s median %.1f  p90 %.1f  >90: %.3f %%  folded (flat) %.3f %%  %.1f s"
              % (mat.name, report[mat.name]["median_deg"], report[mat.name]["p90_deg"],
                 100 * report[mat.name]["over_90_deg_fraction"],
                 100 * report[mat.name]["folded_fraction"], time.time() - t0))
    return images, report


# ------------------------------------------------------------------ main ---
def main():
    args = parse_args()
    scene = stage.reset_scene()
    stage.build_world(scene)
    char = SPEC.get(args.character)
    name = char["name"]

    matlib.ensure_materials(sorted(set(char["materials"].values())), args.tex_dir)

    s, socket_info, bevel_info = BC3.build_surface_r3(char)
    manifold = s.check_manifold()
    cage_stats = s.stats()
    ob = s.to_object(name, char["materials"])
    seam_rules = BC.resolve_seam_rules(char, s)
    s.free()
    print("CAGE", cage_stats, manifold)
    if manifold["non_manifold_edges"] or manifold["loose_verts"]:
        print("WARNING: surface is not a clean closed manifold", manifold)

    rebuild_cage_canonically(ob)
    n_seams = uvmap.mark_seams(ob, seam_rules)
    uvmap.unwrap(ob)
    slots = textured_slots(ob)
    pack_materials_unique(ob, slots, args.uv_margin_px)
    uv_report = uv_layout_report(ob, slots)
    spread = uvmap.density_spread(ob)
    print("UV seams=%d" % n_seams, json.dumps(uv_report), spread)
    check_uv_layout(uv_report)

    cage = ob.copy()
    cage.data = ob.data.copy()
    cage.name = cage.data.name = name + "_cage"
    bpy.context.collection.objects.link(cage)
    cage.hide_render = True

    ob_low = BC2._clone_mesh_object(ob, name + "_low")

    SF.apply_subsurf(ob, levels=args.subsurf_high, render_levels=args.subsurf_high)
    SF.shade_smooth(ob)

    texture_work = os.path.join(args.work, "textures_%s" % name)
    os.makedirs(texture_work, exist_ok=True)
    texgen_report = regenerate_textures_r4(ob, char, args.tex_dir, texture_work, args)

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

    decor_obs = BC3.build_decor_r3(char, arm_ob, args.tex_dir, dz, socket_info)
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

    socket_integrity = {}
    if socket_info:
        head_turn_pose = next(p for lbl, p in char["poses"] if lbl == "head turn")
        strong_turn_pose = {b: tuple(a * 1.8 for a in rot) for b, rot in head_turn_pose.items()}
        socket_integrity = BC3.check_socket_integrity(ob, arm_ob, socket_info, dz, strong_turn_pose)
        print("SOCKET_INTEGRITY", socket_integrity)

    lod_work = os.path.join(args.work, "lod_%s" % name)
    lod_normals, shape_report = lod_normals_r4(ob, ob_low, lod_work, name, args.gutter_px)
    BC2._duplicate_materials_with_normal(ob_low, lod_normals, "lod")

    for part in cloth_obs + attachments + decor_obs:
        sort_faces_canonically(part)

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
        uv=dict(seam_edges=n_seams, per_material=uv_report, spread=spread,
                margin_px=args.uv_margin_px, gutter_px=args.gutter_px),
        weights_high=audit_high, weights_high_before=audit_before,
        weights_high_transferred_from_low=transferred, unweighted_filled_high=filled,
        weights_low=audit_low, weights_low_before=audit_before_low, unweighted_filled_low=filled_low,
        deformation_high=deform_high, deformation_low=deform_low,
        lod_bake_slots=sorted(lod_normals.keys()),
        lod_shape_normal=shape_report,
        eye_sockets=socket_info,
        socket_integrity=socket_integrity,
        bevels=bevel_info,
        texgen_r4=texgen_report,
        cloth=(clothsim.report(cloth_obs) if cloth_obs else []),
        attachments=[o.name for o in attachments], decor=[o.name for o in decor_obs],
        packed_images=packed,
        outputs=dict(blend=blend_path, glb=glb_path, blend_low=blend_path_low, glb_low=glb_path_low),
    )
    os.makedirs(args.work, exist_ok=True)
    P.save_json(os.path.join(args.work, "%s_build_r4.json" % name), stats)
    print("BUILD R4 OK", json.dumps(dict(
        character=name, tris_high=stats_high["tris"], tris_low=stats_low["tris"],
        bones=len(bones), unweighted_high=audit_high["unweighted"],
        unweighted_low=audit_low["unweighted"], sockets=list(socket_info.keys()),
        socket_integrity=socket_integrity, lod_bake_slots=sorted(lod_normals.keys()))))


if __name__ == "__main__":
    main()
