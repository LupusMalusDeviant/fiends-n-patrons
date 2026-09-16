"""Cloak and loose cloth: a lofted sheet, simulated, then baked to a static mesh.

The folds in the cloak are not modelled. A cloak sheet is lofted around the
character, pinned along its top rows, and dropped onto the body with Blender's
cloth solver; the drape that comes out is kept as the final geometry. That is
why the hem breaks over the arms and gathers behind the legs instead of hanging
like a traffic cone.

Determinism: the solver has no random input, so a fixed start frame, a fixed
frame count, fixed settings and a fixed scene gravity give the same drape every
run. The result is captured through the depsgraph and written back as plain mesh
data, and the cloth modifier is then removed -- the deliverable contains baked
geometry, not a simulation the asset pipeline would have to re-run.
"""
import math

import bmesh
import bpy
import numpy as np

import lofting as L
import matlib
import palette as P


def _sheet(cloth_spec, name):
    """Loft the cloak as an open sheet: a tube with a wedge missing at the front.

    Open at the front so it parts over the staff arm, open at the bottom (no
    cap) so it is a surface, not a bag.
    """
    nseg = int(cloth_spec["nseg"])
    stations = int(cloth_spec["stations"])
    gap = math.radians(float(cloth_spec.get("open_front_deg", 0.0)))
    pts, tg, u, v = L.chain_stations(cloth_spec["ctrl"], stations,
                                     u_hint=cloth_spec.get("u_hint", (1.0, 0.0, 0.0)))
    prof = L.interp_profiles(cloth_spec["keys"], stations)
    # Angles run from the front gap edge all the way round to the other edge.
    span = 2.0 * math.pi - gap
    start = math.pi / 2.0 + gap / 2.0          # front centre is +Y = pi/2
    angles = start + np.linspace(0.0, span, nseg)
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new(P.UV_NAME)
    rings = []
    for i in range(stations):
        ring = L.ring_points(pts[i], u[i], v[i], angles, prof["rx"][i], prof["ry"][i],
                             prof["power"][i], prof["rot"][i], prof["du"][i], prof["dv"][i])
        rings.append([bm.verts.new(tuple(p)) for p in ring])
    bm.verts.ensure_lookup_table()
    tile = cloth_spec.get("tile_size_m", 1.0) or 1.0
    arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    for i in range(stations - 1):
        for k in range(nseg - 1):
            corners = ((i, k), (i, k + 1), (i + 1, k + 1), (i + 1, k))
            f = bm.faces.new(tuple(rings[r][c] for r, c in corners))
            # Cylindrical, world-scaled UVs: circumference across, arc length
            # down. f.loops follows the order the vertices were passed in, so the
            # grid coordinates zip straight onto them.
            for loop, (row, col) in zip(f.loops, corners):
                circ = angles[col] * 0.5 * (prof["rx"][row] + prof["ry"][row])
                loop[uv_layer].uv = (circ / tile, -arc[row] / tile)
    # Hand back plain indices, not BMVerts: the bmesh is freed a few lines below
    # and reading .index off a freed BMVert raises ReferenceError.
    bm.verts.index_update()
    ring_indices = [[v.index for v in r] for r in rings]
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob, ring_indices, stations, nseg


def build(char, body_ob, arm_ob, tex_dir, dz=0.0):
    """Build, simulate and bake every cloth piece of a character.

    dz is the grounding offset already applied to the body, so the cloak starts
    on the shoulders rather than a centimetre inside them.
    """
    specs = char["cloth"]
    if isinstance(specs, dict):
        specs = [specs]
    scene = bpy.context.scene
    made = []
    for cloth_spec in specs:
        name = "%s_%s" % (char["name"], cloth_spec["name"])
        mat_key = cloth_spec["material"]
        matlib.ensure_materials([mat_key], tex_dir)
        cloth_spec = dict(cloth_spec)
        cloth_spec["ctrl"] = [(c[0], c[1], c[2] + dz) for c in cloth_spec["ctrl"]]
        cloth_spec.setdefault("tile_size_m", matlib.tile_size_for(mat_key, tex_dir) or 1.0)
        ob, rings, stations, nseg = _sheet(cloth_spec, name)
        ob.data.materials.append(bpy.data.materials[mat_key])

        # Pin the top rows: these are the rows that sit on the shoulders.
        pin_rows = int(cloth_spec.get("pin_rows", 2))
        vg = ob.vertex_groups.new(name="pin")
        pinned = [i for r in rings[:pin_rows] for i in r]
        vg.add(pinned, 1.0, 'REPLACE')

        sim = dict(frames=60, quality=8, mass=0.30, tension=15.0, bending=0.5,
                   air=1.1, collision_distance=0.012, collision_quality=4,
                   self_collision=True, self_distance=0.008, time_scale=1.0)
        sim.update(cloth_spec.get("sim", {}))

        # The body is what the cloak lands on.
        coll = body_ob.modifiers.get("cloth_collision") or \
            body_ob.modifiers.new("cloth_collision", 'COLLISION')
        body_ob.collision.thickness_outer = float(sim["collision_distance"])
        body_ob.collision.damping = 0.4

        md = ob.modifiers.new("cloth", 'CLOTH')
        cs = md.settings
        cs.quality = int(sim["quality"])
        cs.mass = float(sim["mass"])
        cs.tension_stiffness = float(sim["tension"])
        cs.compression_stiffness = float(sim["tension"])
        cs.shear_stiffness = float(sim["tension"]) * 0.6
        cs.bending_stiffness = float(sim["bending"])
        cs.air_damping = float(sim["air"])
        cs.time_scale = float(sim["time_scale"])
        cs.vertex_group_mass = "pin"
        md.collision_settings.use_self_collision = bool(sim["self_collision"])
        md.collision_settings.self_distance_min = float(sim["self_distance"])
        md.collision_settings.distance_min = float(sim["collision_distance"])
        md.collision_settings.collision_quality = int(sim["collision_quality"])
        frames = int(sim["frames"])
        md.point_cache.frame_start, md.point_cache.frame_end = 1, frames
        scene.frame_start, scene.frame_end = 1, frames

        before = np.array([tuple(v.co) for v in ob.data.vertices])
        scene.frame_set(1)
        for f in range(1, frames + 1):
            scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        evaluated = ob.evaluated_get(dg)
        baked = bpy.data.meshes.new_from_object(evaluated)
        after = np.array([tuple(v.co) for v in baked.vertices])
        old = ob.data
        ob.data = baked
        bpy.data.meshes.remove(old)
        ob.modifiers.remove(ob.modifiers["cloth"])
        body_ob.modifiers.remove(coll)
        scene.frame_set(1)

        moved = np.linalg.norm(after - before, axis=1) if after.shape == before.shape else None
        ob["cloth_frames"] = frames
        ob["cloth_max_move_m"] = float(moved.max()) if moved is not None else -1.0
        ob["cloth_mean_move_m"] = float(moved.mean()) if moved is not None else -1.0
        print("CLOTH %s: %d frames, %d verts, max drape %.4f m, mean %.4f m"
              % (name, frames, len(after),
                 ob["cloth_max_move_m"], ob["cloth_mean_move_m"]))
        # Re-pin the top rows to the body silhouette is unnecessary: the pinned
        # rows never moved, so the collar still sits exactly on the shoulders.
        for p in ob.data.polygons:
            p.use_smooth = True
        made.append(ob)
    return made


def report(cloth_obs):
    return [dict(name=o.name, frames=int(o.get("cloth_frames", 0)),
                 verts=len(o.data.vertices),
                 max_move_m=round(float(o.get("cloth_max_move_m", -1.0)), 4),
                 mean_move_m=round(float(o.get("cloth_mean_move_m", -1.0)), 4))
            for o in cloth_obs]
