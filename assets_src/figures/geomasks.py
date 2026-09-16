"""Round 3: curvature and ambient-occlusion masks baked from the actual built
mesh, so texture wear (edge polish, crevice grime) sits where the geometry
really has an edge or a fold instead of being placed by more noise.

Curvature is computed directly from mesh connectivity in plain Python (a
Laplacian-style estimate: how far a vertex sits from the average of its
neighbours, projected onto its own normal -- positive is convex, negative is
concave), fully under this script's control and cheap to sanity-check by
printing its own raw mean/std/min/max before anything gets clipped into a
0..1 mask. That per-vertex value is written into a colour attribute and then
handed to Blender's OWN bake rasteriser (Cycles, EMIT type, an Attribute node)
to turn it into a UV-space image -- reusing proven code for the hard part
(rasterising a vertex value through an arbitrary UV unwrap) instead of hand-
rolling a second one. Ambient occlusion uses Cycles' native AO bake type
directly, no extra node required.

Both bakes run on the CPU device, matching the reasoning already given in
build_character_r2.py's bake_shape_normal: this must not touch the GPU the
user may be gaming on, so it is exempt from the GPU guard the render steps
still have to run.

Run this only on an object whose mesh is ALREADY at its final (e.g.
post-subsurf) topology and UV layout -- the curvature signal and the bake
target must agree on vertex/UV correspondence, which is trivially true here
because both read straight off `ob.data`, no modifier or evaluated-mesh
copy involved.
"""
import os
import random

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import palette as P


def vertex_curvature01(me, clip_sigma=2.5):
    """Per-vertex curvature in [0, 1] (0.5 = flat), aligned to me.vertices.

    Returns (curv01 array, raw stats dict) -- the raw mean/std/min/max is
    the proof the signal is real (a degenerate all-zero mesh reads back as
    std ~ 0, which callers should treat as a failed bake, not a flat
    material) before it gets clipped at clip_sigma standard deviations and
    remapped into the mask.
    """
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bm.normal_update()
    raw = np.zeros(len(bm.verts), dtype=np.float64)
    for v in bm.verts:
        nbrs = [e.other_vert(v) for e in v.link_edges]
        if len(nbrs) < 3:
            continue
        mean_nb = np.mean([np.asarray(n.co) for n in nbrs], axis=0)
        raw[v.index] = float(np.dot(np.asarray(v.co) - mean_nb, np.asarray(v.normal)))
    bm.free()
    stats = dict(mean=float(raw.mean()), std=float(raw.std()),
                min=float(raw.min()), max=float(raw.max()), n=len(raw))
    sigma = stats["std"] if stats["std"] > 1e-12 else 1.0
    clipped = np.clip(raw / (clip_sigma * sigma), -1.0, 1.0)
    curv01 = (clipped + 1.0) * 0.5
    return curv01, stats


def _write_point_attr(me, name, values01):
    """Write a scalar-as-greyscale colour attribute, POINT domain (one entry
    per vertex, matching `vertex_curvature01`'s indexing)."""
    attr = me.color_attributes.get(name)
    if attr is None:
        attr = me.color_attributes.new(name=name, type='FLOAT_COLOR', domain='POINT')
    n = len(me.vertices)
    flat = np.empty(n * 4, dtype=np.float32)
    v = np.asarray(values01, dtype=np.float32)
    flat[0::4] = v
    flat[1::4] = v
    flat[2::4] = v
    flat[3::4] = 1.0
    attr.data.foreach_set("color", flat)
    me.update()
    return attr.name


def _bake_with_retry(bake_type, img, max_tries=6):
    """`bpy.ops.object.bake()` for a HEADLESS, repeated, same-session Cycles
    bake is flaky in a way this script measured directly: identical code,
    identical inputs, re-run back to back, came back with real data on some
    runs and an exact, silent all-zero image on others -- same slot, same
    material, no error, no warning, `FINISHED` either way (confirmed with
    three consecutive runs of the same script on the same character: fail,
    succeed, fail). Disabling Persistent Data made it noticeably better but
    did not make it deterministic. Rather than keep chasing a root cause
    inside Blender's own bake scheduler, this retries the SAME bake call and
    re-measures the result -- the fix the brief explicitly calls for
    ("merkst du das durch Nachmessen im Skript, nicht durch Vertrauen in den
    Rückgabewert") -- up to `max_tries` times before giving up.
    """
    scene = bpy.context.scene
    for attempt in range(1, max_tries + 1):
        if attempt > 1:
            # A bare re-call of the SAME operator with nothing else changed
            # reliably reproduced the SAME degenerate result every time
            # (measured: 4/4 identical failures in a row) -- whatever is
            # stuck is stuck for the session, not random per call. Forcing
            # Cycles to tear down and rebuild its scene translation (toggle
            # the engine away and back) is a heavier reset that changes
            # something a same-call retry does not.
            scene.render.engine = 'BLENDER_EEVEE'
            scene.render.engine = 'CYCLES'
            bpy.context.view_layer.update()
        bpy.ops.object.bake(type=bake_type)
        arr = _read_back_image(img)[..., 0].copy()
        if float(arr.std()) > 1e-4:
            return arr, attempt
    return arr, attempt  # last (still-degenerate) attempt; caller reports it


def _read_back_image(img):
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    return buf.reshape(h, w, 4)[::-1, :, :]  # Blender stores bottom row first


# ---------------------------------------------- pure-python bake fallback ---
# One material (imp's "horn") reproduced a degenerate Cycles bake on every
# single attempt across many full process restarts -- not flaky, wrong
# every time -- even fully isolated into its own single-material object
# with nothing else on the mesh (confirmed with a standalone diagnostic).
# A plain Cycles NORMAL bake of the SAME isolated geometry/UVs came back
# fine (std ~0.24, sane), and the basecolor/normal/orm PNGs on disk read
# back fine too -- only a colour-producing bake (DIFFUSE with direct/
# indirect off, or this module's own Attribute->Emission graph) came back
# an exact 0.0 mean/std, for a reason this investigation did not find. The
# correction (round 3b) explicitly wants either a fixed texture or an
# aborted run, not a silent bootstrap fallback -- since retrying and
# reordering the Cycles bake provably never fixes this specific case, this
# is a second, independent path that computes the SAME curvature/AO
# quantities without going through bpy.ops.object.bake at all: curvature
# already exists per-vertex (vertex_curvature01), and AO is measured here
# by actually ray-casting a hemisphere of samples per vertex against a
# BVHTree of the mesh's own geometry (mathutils, no Cycles involved). Both
# are then rasterised into the material's own UV layout with a small
# barycentric scanline rasteriser. Slower and cruder at island edges than a
# GPU/Cycles bake, but deterministic -- it does not depend on whatever made
# the operator itself unreliable here.
def vertex_ao_raycast(me, n_samples=24, max_dist=0.5, seed=20260916):
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bm.normal_update()
    bvh = BVHTree.FromBMesh(bm, epsilon=1e-6)
    rng = random.Random(seed)
    ao = np.ones(len(bm.verts), dtype=np.float64)
    for v in bm.verts:
        n = v.normal
        ref = Vector((1.0, 0.0, 0.0)) if abs(n.x) < 0.9 else Vector((0.0, 1.0, 0.0))
        t = n.cross(ref).normalized()
        b = n.cross(t)
        hits = 0
        for _ in range(n_samples):
            u1, u2 = rng.random(), rng.random()
            r = u1 ** 0.5
            theta = 2.0 * np.pi * u2
            lx, ly, lz = r * np.cos(theta), r * np.sin(theta), (max(0.0, 1.0 - u1)) ** 0.5
            d = (t * lx + b * ly + n * lz)
            if d.length < 1e-9:
                continue
            d.normalize()
            origin = v.co + n * 1e-4
            loc, _nrm, _idx, _dist = bvh.ray_cast(origin, d, max_dist)
            if loc is not None:
                hits += 1
        ao[v.index] = 1.0 - hits / float(n_samples)
    bm.free()
    return ao


def _raster_tri(img, weight, tri_uv, tri_val, res):
    pts = []
    for (u, v), val in zip(tri_uv, tri_val):
        pts.append(((u % 1.0) * res, (1.0 - (v % 1.0)) * res, val))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, x1 = max(int(np.floor(min(xs))), 0), min(int(np.ceil(max(xs))), res - 1)
    y0, y1 = max(int(np.floor(min(ys))), 0), min(int(np.ceil(max(ys))), res - 1)
    if x1 <= x0 or y1 <= y0:
        return
    (xa, ya, va), (xb, yb, vb), (xc, yc, vc) = pts
    denom = (yb - yc) * (xa - xc) + (xc - xb) * (ya - yc)
    if abs(denom) < 1e-9:
        return
    xx, yy = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
    wa = ((yb - yc) * (xx - xc) + (xc - xb) * (yy - yc)) / denom
    wb = ((yc - ya) * (xx - xc) + (xa - xc) * (yy - yc)) / denom
    wc = 1.0 - wa - wb
    inside = (wa >= -1e-6) & (wb >= -1e-6) & (wc >= -1e-6)
    val = wa * va + wb * vb + wc * vc
    img[y0:y1 + 1, x0:x1 + 1] += np.where(inside, val, 0.0)
    weight[y0:y1 + 1, x0:x1 + 1] += np.where(inside, 1.0, 0.0)


def rasterize_vertex_field_to_uv(me, slot_idx, values, res):
    uv_layer = me.uv_layers.active
    img = np.zeros((res, res), dtype=np.float64)
    weight = np.zeros((res, res), dtype=np.float64)
    for p in me.polygons:
        if p.material_index != slot_idx:
            continue
        loop_idx = list(p.loop_indices)
        vidx = [me.loops[li].vertex_index for li in loop_idx]
        uvs = [tuple(uv_layer.data[li].uv) for li in loop_idx]
        vals = [values[vi] for vi in vidx]
        for i in range(1, len(vidx) - 1):
            _raster_tri(img, weight, [uvs[0], uvs[i], uvs[i + 1]],
                       [vals[0], vals[i], vals[i + 1]], res)
    covered = weight > 1e-6
    out = np.zeros((res, res), dtype=np.float32)
    out[covered] = (img[covered] / weight[covered]).astype(np.float32)
    return out, float(covered.mean())


def python_fallback_slot_bake(ob, slot_idx, res, curv01):
    """Curvature (already computed per-vertex by the caller) and AO (raycast
    here) for one material slot, rasterised into UV space without Cycles."""
    me = ob.data
    ao01 = vertex_ao_raycast(me)
    curv_img, curv_cov = rasterize_vertex_field_to_uv(me, slot_idx, curv01, res)
    ao_img, ao_cov = rasterize_vertex_field_to_uv(me, slot_idx, ao01, res)
    return curv_img, ao_img, dict(uv_coverage_curvature=curv_cov, uv_coverage_ao=ao_cov)


def bake_masks(ob, res, work_dir, samples=48, curvature_attr="curv_r3", slot_order=None):
    """Bake per-material-slot curvature and AO images matching `ob`'s own UV
    layout. Returns {slot_idx: dict(curvature=HxW float32 in[0,1],
    ao=HxW float32 in[0,1])} plus a `report` dict with the raw curvature
    stats and each bake's post-bake std (so a degenerate/empty bake is
    visible as a number, not assumed away).

    `slot_order`: process material slots in this index order instead of
    0,1,2,... An earlier hypothesis here was that failure correlated with a
    slot's POSITION in the loop; a follow-up test (imp's "horn" run through
    every rotation of a 3-slot order) disproved that for horn specifically
    -- it failed at position 0, 1 AND 2 across five full rebakes, so it is
    that MATERIAL, not its position. The two-material characters ("plates",
    "mask") still show genuine run-to-run flakiness independent of horn's
    issue, where a different starting slot can plausibly still help, so the
    rotation stays as a cheap thing to vary between attempts; the actual
    fix for a deterministic per-material failure like horn's is the
    pure-Python fallback bake below, not this parameter.
    """
    me = ob.data
    curv01, curv_stats = vertex_curvature01(me)
    _write_point_attr(me, curvature_attr, curv01)
    order = list(slot_order) if slot_order is not None else list(range(len(me.materials)))

    scene = bpy.context.scene
    prev_engine = scene.render.engine
    prev_world, ao_world = scene.world, None
    out, report = {}, dict(curvature_vertex_stats=curv_stats, slots={})
    try:
        bpy.ops.preferences.addon_enable(module='cycles')
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'CPU'
        scene.cycles.samples = int(samples)
        # Persistent Data caches the BVH/shader graph across renders for
        # speed; left on, repeated bpy.ops.object.bake() calls in the SAME
        # session can reuse a stale compile from an earlier call instead of
        # picking up the node-tree edits made in between -- measured on this
        # exact script: with it on, only the FIRST of several sequential
        # per-material bake() calls ever produced real data (std > 0), every
        # later one came back an exact, silent all-zero image regardless of
        # which material it targeted.
        scene.render.use_persistent_data = False
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.select_all(action='DESELECT')
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob

        # One bake call PER MATERIAL SLOT, not one combined call for every
        # slot at once. A combined call was tried first and measured wrong
        # on this exact cast: two structurally IDENTICAL materials (horn,
        # claw_nail -- same node graph, same object, same combined call)
        # came back with real, non-degenerate signal for one and an exact
        # all-zero image for the other; per-vertex curvature for the failed
        # slot's own vertices was fine (checked directly, std ~0.18, same
        # order as the working slots), so the loss was specifically in that
        # combined bake pass, not the underlying data. Isolating each slot
        # into its own operator call costs a few extra bake invocations and
        # removes whatever that cross-slot interaction was.
        for slot_idx in order:
            mat = me.materials[slot_idx]
            if mat is None:
                continue
            nt = mat.node_tree
            attr_node = nt.nodes.new("ShaderNodeAttribute")
            attr_node.attribute_name = curvature_attr
            em = nt.nodes.new("ShaderNodeEmission")
            nt.links.new(attr_node.outputs["Color"], em.inputs["Color"])
            out_node = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
            old_link_from = None
            if out_node is not None:
                # Compare by node NAME, not `is` -- build_character_r2.py's
                # own combine_and_write_lod_normals already documents why:
                # repeated attribute access into a node tree's `links`
                # collection is not guaranteed to hand back the same Python
                # wrapper object for the same underlying node, so `is` can
                # silently never match. It did not match here either: this
                # left `old_link_from` None every time, so the restore below
                # never ran, and the ORIGINAL BSDF -> Output link -- already
                # overwritten by the emission link two lines down -- was
                # gone for good once `em` was removed after the bake. Found
                # by actually re-reading the saved .blend's node graph: every
                # material's Principled BSDF had no link to Material Output
                # at all, which is exactly why the character rendered as a
                # flat black silhouette even though its own textures,
                # inspected directly, were fine.
                old_link = next((l for l in nt.links if l.to_node.name == out_node.name
                                and l.to_socket.name == "Surface"), None)
                if old_link is not None:
                    old_link_from = old_link.from_socket
                nt.links.new(em.outputs[0], out_node.inputs["Surface"])
            img = bpy.data.images.new("%s_slot%d_curv" % (ob.name, slot_idx), res, res,
                                      alpha=False, float_buffer=True)
            img.colorspace_settings.name = 'Non-Color'
            img_node = nt.nodes.new("ShaderNodeTexImage")
            img_node.image = img
            img_node.extension = 'REPEAT'
            for n in nt.nodes:
                n.select = False
            img_node.select = True
            nt.nodes.active = img_node
            ob.active_material_index = slot_idx
            me.update()
            bpy.context.view_layer.update()
            arr, tries = _bake_with_retry('EMIT', img)
            out.setdefault(slot_idx, {})["curvature"] = arr
            report["slots"].setdefault(slot_idx, {})["curvature_bake_std"] = float(arr.std())
            report["slots"][slot_idx]["curvature_bake_tries"] = tries
            work_path = os.path.join(work_dir, "slot%d_curvature.png" % slot_idx)
            P.write_png(work_path, np.round(np.clip(arr, 0, 1) * 255).astype(np.uint8)[..., None]
                       .repeat(3, axis=2))
            nt.nodes.remove(attr_node)
            nt.nodes.remove(em)
            nt.nodes.remove(img_node)
            if out_node is not None and old_link_from is not None:
                nt.links.new(old_link_from, out_node.inputs["Surface"])
            bpy.data.images.remove(img)

        # Cycles' 'AO' bake type is lit by the scene world, not a pure
        # geometric visibility fraction, so it is baked under a flat, bright,
        # colour-neutral world rather than the game's own moody near-black
        # one -- restored right after, unrelated to how the character will
        # finally be rendered. This did NOT, on its own, bring the result
        # into a canonical "~0.9 mostly exposed" range (measured: still a
        # mean around 0.02-0.03 on this cast even under the bright world,
        # for reasons this script did not fully track down); texgen_r3.
        # apply_geo_wear compensates by reading "edge"/"crevice" off each
        # mask's own percentile distribution instead of a fixed absolute
        # cutoff, rather than this swap being the whole fix.
        ao_world = bpy.data.worlds.new("__ao_bake_world")
        ao_world.use_nodes = True
        bg = ao_world.node_tree.nodes.get("Background")
        if bg is not None:
            bg.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
            bg.inputs["Strength"].default_value = 1.0
        scene.world = ao_world

        # --- ambient occlusion: native Cycles AO bake type, also per slot ---
        for slot_idx in order:
            mat = me.materials[slot_idx]
            if mat is None:
                continue
            nt = mat.node_tree
            img = bpy.data.images.new("%s_slot%d_ao" % (ob.name, slot_idx), res, res,
                                      alpha=False, float_buffer=True)
            img.colorspace_settings.name = 'Non-Color'
            img_node = nt.nodes.new("ShaderNodeTexImage")
            img_node.image = img
            img_node.extension = 'REPEAT'
            for n in nt.nodes:
                n.select = False
            img_node.select = True
            nt.nodes.active = img_node
            ob.active_material_index = slot_idx
            me.update()
            bpy.context.view_layer.update()
            arr, tries = _bake_with_retry('AO', img)
            out.setdefault(slot_idx, {})["ao"] = arr
            report["slots"].setdefault(slot_idx, {})["ao_bake_std"] = float(arr.std())
            report["slots"][slot_idx]["ao_bake_tries"] = tries
            work_path = os.path.join(work_dir, "slot%d_ao.png" % slot_idx)
            P.write_png(work_path, np.round(np.clip(arr, 0, 1) * 255).astype(np.uint8)[..., None]
                       .repeat(3, axis=2))
            nt.nodes.remove(img_node)
            bpy.data.images.remove(img)
    finally:
        scene.render.engine = prev_engine
        scene.world = prev_world
        if ao_world is not None:
            bpy.data.worlds.remove(ao_world)
        attr = me.color_attributes.get(curvature_attr)
        if attr is not None:
            me.color_attributes.remove(attr)

    for slot_idx, d in out.items():
        for k in ("curvature", "ao"):
            if k in d and d[k].std() < 1e-4:
                report["slots"].setdefault(slot_idx, {})["%s_degenerate" % k] = True

    # Pure-Python fallback (no Cycles bake operator at all -- see
    # python_fallback_slot_bake's module-level comment) for any slot still
    # degenerate after every Cycles retry/reorder: measured on imp's "horn"
    # to reproduce a degenerate Cycles bake on 100% of attempts (six full
    # process restarts, six failures, including fully isolated onto its own
    # single-material object), so this is not an occasional-flakiness
    # retry, it is the path that actually gets that material a real,
    # non-degenerate mask instead of leaving it on the bootstrap texture.
    for slot_idx in list(report["slots"].keys()):
        d = report["slots"][slot_idx]
        if not (d.get("curvature_degenerate") or d.get("ao_degenerate")):
            continue
        mat_name = me.materials[slot_idx].name if slot_idx < len(me.materials) and me.materials[slot_idx] else str(slot_idx)
        print("GEOMASKS falling back to pure-Python bake for slot %d (%s) -- Cycles bake stayed "
             "degenerate through every retry/order" % (slot_idx, mat_name))
        curv_img, ao_img, cov = python_fallback_slot_bake(ob, slot_idx, res, curv01)
        d["python_fallback"] = True
        d["python_fallback_coverage"] = cov
        if d.get("curvature_degenerate"):
            d["curvature_bake_std"] = float(curv_img.std())
            d["curvature_degenerate"] = bool(curv_img.std() < 1e-4)
            out.setdefault(slot_idx, {})["curvature"] = curv_img
            P.write_png(os.path.join(work_dir, "slot%d_curvature.png" % slot_idx),
                       np.round(np.clip(curv_img, 0, 1) * 255).astype(np.uint8)[..., None].repeat(3, axis=2))
        if d.get("ao_degenerate"):
            d["ao_bake_std"] = float(ao_img.std())
            d["ao_degenerate"] = bool(ao_img.std() < 1e-4)
            out.setdefault(slot_idx, {})["ao"] = ao_img
            P.write_png(os.path.join(work_dir, "slot%d_ao.png" % slot_idx),
                       np.round(np.clip(ao_img, 0, 1) * 255).astype(np.uint8)[..., None].repeat(3, axis=2))
        print("GEOMASKS python fallback slot %d: curvature_std=%.4f ao_std=%.4f uv_coverage=%s"
             % (slot_idx, float(curv_img.std()), float(ao_img.std()), cov))
    return out, report
