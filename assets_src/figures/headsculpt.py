"""Round 3: real eye sockets and anisotropic head-structure displacement.

Everything here operates on a live Surface's bmesh (surface.py's Surface
class) BEFORE Surface.to_object() bakes it into a bpy mesh -- same rule as
round 1/2's own Surface.bump: detail comes from moving or inserting loops
that are already part of the one continuous quad surface, never a glued-on
primitive. The eye socket additionally INSERTS real topology (two nested
insets: rim -> wall -> floor) instead of only pushing existing vertices,
which is what an isotropic bump cannot give: a rim the brow sits on, a
sloped wall, and a floor set back far enough for a real eyeball mesh to sit
inside instead of resting on the skin.

No bpy.ops is used anywhere in this module, only bmesh.ops on an in-memory
BMesh -- there is no active object or mode to depend on, and every operation
below is verified by re-measuring the resulting geometry (face/vert counts,
achieved depth) rather than trusting an operator's return value, because
round 1/2 already hit silent no-ops from Blender's own operators (automatic
weights refusing after an un-cleaned extrude, UV-align reporting success and
doing nothing) and there is no reason bmesh.ops would be exempt.
"""
import bmesh
import numpy as np
from mathutils import Vector


def _normalize(v, fallback=(0.0, 0.0, 1.0)):
    v = np.asarray(v, dtype=np.float64)
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else np.asarray(fallback, dtype=np.float64)


def _smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return 1.0 - t * t * (3.0 - 2.0 * t)


# ------------------------------------------------------------- aniso bump ---
def bump_aniso(s, center, radii, offset, only_region=None):
    """Ellipsoidal proportional displacement (brow ridges, jaw lines, temple
    hollows): same smoothstep falloff as Surface.bump, but distance is
    measured in an ellipsoid (radii = (rx, ry, rz) along world axes) instead
    of a sphere, so a wide, shallow, elongated feature is possible -- a real
    brow ridge is roughly three times wider than it is tall, an isotropic
    bump can only ever be a round dimple.
    """
    c = np.asarray(center, dtype=np.float64)
    o = np.asarray(offset, dtype=np.float64)
    r = np.asarray(radii, dtype=np.float64)
    r = np.where(r <= 1e-9, 1e-9, r)
    rid = s.regions.get(only_region) if only_region else None
    allowed = None
    if rid is not None:
        allowed = {vtx for f in s.bm.faces if f[s.region_layer] == rid for vtx in f.verts}
    moved = 0
    for vtx in s.bm.verts:
        if allowed is not None and vtx not in allowed:
            continue
        d = (np.asarray(vtx.co, dtype=np.float64) - c) / r
        t = float(np.sqrt(np.dot(d, d)))
        if t >= 1.0:
            continue
        w = float(_smoothstep(t))
        vtx.co = Vector(tuple(np.asarray(vtx.co, dtype=np.float64) + w * o))
        moved += 1
    return moved


# --------------------------------------------------------------- helpers ---
def _face_center(f):
    return np.asarray(f.calc_center_median(), dtype=np.float64)


def nearest_face(bm, point, region_id=None, region_layer=None):
    pt = np.asarray(point, dtype=np.float64)
    best, bestd = None, None
    for f in bm.faces:
        if region_id is not None and f[region_layer] != region_id:
            continue
        d = float(np.linalg.norm(_face_center(f) - pt))
        if bestd is None or d < bestd:
            best, bestd = f, d
    return best


def _grow_faces(seed_faces, rings, region_id=None, region_layer=None):
    """BFS over face adjacency (through shared edges) by `rings` steps,
    optionally staying inside one region so the patch cannot leak into a
    neighbouring horn/plate/mask region."""
    visited = set(seed_faces)
    frontier = set(seed_faces)
    for _ in range(max(int(rings), 0)):
        nxt = set()
        for f in frontier:
            for e in f.edges:
                for lf in e.link_faces:
                    if lf in visited:
                        continue
                    if region_id is not None and lf[region_layer] != region_id:
                        continue
                    nxt.add(lf)
        visited |= nxt
        frontier = nxt
        if not frontier:
            break
    return visited


# ----------------------------------------------------------- eye sockets ---
def carve_eye_socket(s, at, rim_radius, depth, region=None,
                     subdiv_cuts=8, seed_rings=1, crease_value=0.15):
    """Carve a real eye socket: inset rim -> sloped wall -> recessed floor.

    `at` is an approximate world-space point on the (pre-carve) surface --
    the same kind of measured-by-raycast coordinate round 2 already used to
    place the flat eye decor, since it already sits close to the real
    surface. The nearest existing face is found, densified, and the disc
    that is actually carved is re-selected afterwards by real distance, so a
    bad `at`/`rim_radius` combination fails loudly (ValueError on a
    too-small disc) instead of quietly carving a corner of the ear.

    Densification only touches edges strictly INSIDE the seed patch (both
    faces of the edge in the patch): a boundary edge shared with a face
    outside the patch is never selected, so subdivision can never spill into
    a neighbouring region (horn root, mask) or leave a stray triangle
    outside the carved area.

    `seed_rings` defaults to 1 and should rarely be raised: on the coarse
    base cage (nseg=12) a BFS of 2+ rings already crosses the head's own
    centre line on a narrow face (measured on imp: 1 ring stays at x=+0.025,
    2 rings already reaches x=-0.025) and can silently pull in the OTHER
    eye's seed patch, corrupting both sockets with garbage coordinates from
    a self-overlapping face selection -- this is exactly the kind of
    "operator reports success but the input was malformed" trap the rest of
    this pipeline already watches for, found here by literally that
    symptom (a floor centre metres away from a ~1 m character) during
    development. Resolution comes from `subdiv_cuts` instead, which only
    densifies the small patch already selected.

    Returns a measurement dict (face/vert counts, floor centre, outward
    normal, achieved depth in metres) read back off the ACTUAL resulting
    geometry -- callers should use THESE numbers (not the request) to place
    the eyeball and to verify the socket did not collapse under a pose.
    """
    bm = s.bm
    at_arr = np.asarray(at, dtype=np.float64)
    rid = s.regions.get(region) if region else None
    seed = nearest_face(bm, at, region_id=rid, region_layer=s.region_layer)
    if seed is None:
        raise ValueError("carve_eye_socket: no seed face found near %r (region=%r)" % (at, region))
    region_id = seed[s.region_layer]
    seed_center = _face_center(seed)  # `seed` itself may not survive subdivision below

    patch0 = _grow_faces([seed], seed_rings, region_id=region_id, region_layer=s.region_layer)
    patch0_centers = np.array([_face_center(f) for f in patch0])
    patch0_maxdist = float(np.max(np.linalg.norm(patch0_centers - at_arr, axis=1)))
    if patch0_maxdist > rim_radius * 5.0:
        raise RuntimeError(
            "carve_eye_socket: seed patch at %r spans %.4f m (> 5x rim_radius %.4f) -- "
            "seed_rings=%d likely crossed into unrelated geometry (e.g. the other eye "
            "on a narrow face); lower seed_rings and raise subdiv_cuts instead"
            % (at, patch0_maxdist, rim_radius, seed_rings))
    fset0 = set(patch0)
    edges0 = list({e for f in patch0 for e in f.edges if all(lf in fset0 for lf in e.link_faces)})
    if not edges0:
        raise RuntimeError("carve_eye_socket: seed patch at %r has no interior edges -- "
                           "raise seed_rings" % (at,))
    n_faces_before = len(bm.faces)
    bmesh.ops.subdivide_edges(bm, edges=edges0, cuts=int(subdiv_cuts),
                              use_grid_fill=True, use_only_quads=False)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.normal_update()
    n_faces_after = len(bm.faces)
    if n_faces_after <= n_faces_before:
        raise RuntimeError("carve_eye_socket: subdivide_edges added no faces near %r -- "
                           "Blender no-opped the operator, raise seed_rings" % (at,))

    # Defensive re-tag: an int custom-data layer's value after an edge
    # subdivide is not documented to interpolate meaningfully, and the patch
    # was uniformly `region_id` before the op, so any face now within a
    # tight radius of `at` that reads otherwise is re-stamped explicitly
    # rather than trusted.
    for f in bm.faces:
        if float(np.linalg.norm(_face_center(f) - at_arr)) < rim_radius * 1.05:
            f[s.region_layer] = region_id

    pool = [f for f in bm.faces if f[s.region_layer] == region_id]
    disc = [f for f in pool if float(np.linalg.norm(_face_center(f) - at_arr)) < rim_radius]
    if len(disc) < 6:
        raise ValueError("carve_eye_socket: disc too small (%d faces) at %r r=%.3f -- "
                         "raise seed_rings/subdiv_cuts or rim_radius" % (len(disc), at, rim_radius))
    normal0 = _normalize(np.mean([np.asarray(f.normal) for f in disc], axis=0))
    origin_center = np.mean([_face_center(f) for f in disc], axis=0)
    dset = set(disc)
    boundary_edges = set()
    for f in disc:
        for e in f.edges:
            if sum(1 for lf in e.link_faces if lf in dset) == 1:
                boundary_edges.add(e)
    if not boundary_edges:
        raise RuntimeError("carve_eye_socket: disc at %r has no boundary -- "
                           "rim_radius covers more than the densified patch" % (at,))

    # One inset only. A second `inset_region` re-applied to the (mostly
    # boundary, barely-any-interior) 12-45 face disc left by the first one
    # was tried for an extra mid-wall step and measured wrong: instrumented,
    # its resulting vertex set was not even a subset of the first inset's
    # own pushed vertices, and the achieved depth this produced (checked
    # against the disc's own pre-carve position, see below) came out at
    # roughly a third of the request on imp and NEGATIVE on brute -- a
    # second inset on a patch this size does not have enough true interior
    # geometry left to shrink toward and Blender does not warn about it. One
    # inset -> one push already gives the required rim (fixed outer
    # boundary) / sloped wall (the new ring) / recessed floor (the pushed
    # remainder), which is what round 2's flat decor sphere was missing;
    # the exact achieved depth is measured below rather than assumed.
    ins1 = bmesh.ops.inset_region(bm, faces=disc, thickness=rim_radius * 0.35, depth=0.0,
                                  use_boundary=True, use_even_offset=True, use_interpolate=True)
    wall_faces = [f for f in ins1["faces"] if f.is_valid]
    floor_faces = [f for f in disc if f.is_valid]
    if not floor_faces:
        raise RuntimeError("carve_eye_socket: inset left no floor faces at %r" % (at,))
    for f in wall_faces + floor_faces:
        f[s.region_layer] = region_id

    floor_verts = {v for f in floor_faces for v in f.verts}
    for v in floor_verts:
        v.co = v.co + Vector(tuple(normal0 * -depth))
    step_faces = []  # kept in the return shape for callers/logging; unused now

    for e in boundary_edges:
        if e.is_valid:
            e[s.crease_layer] = max(float(e[s.crease_layer]), float(crease_value))

    bm.normal_update()
    floor_center = np.mean([np.asarray(v.co, dtype=np.float64) for v in floor_verts], axis=0)
    # Depth measured against THIS patch's own pre-carve position (`origin_center`,
    # the disc's average face centre before either inset), not against the
    # external `at` hint -- `at` is only an approximate, pre-measured target
    # (see spec.py's own notes on how these coordinates were found) and can
    # sit several centimetres off the true local surface, which would
    # otherwise be silently double-counted as "depth".
    achieved_depth = float(np.dot(origin_center - floor_center, normal0))
    return dict(seed_center=seed_center.tolist(), disc_faces=len(disc),
               wall_faces=len(wall_faces), step_faces=len(step_faces),
               floor_faces=len(floor_faces), floor_verts=len(floor_verts),
               floor_center=floor_center.tolist(), normal=normal0.tolist(),
               rim_radius=float(rim_radius), requested_depth=float(depth),
               achieved_depth_m=achieved_depth)


# --------------------------------------------------------- hard edges ---
def bevel_region_boundary(s, region, width, segments=2, region_other=None):
    """Turn a region border (or any predicate-selected edge loop) into a real
    faceted chamfer instead of relying on a subdivision crease alone.

    A crease only tells the subsurf limit surface to shrink toward the
    control edge -- it still resolves to one smooth-ish curve under light.
    A short bevel gives the edge actual WIDTH (2+ flat segments meeting at
    two real corners), which is what reads as a hard edge on the mask
    instead of a soft one, independent of subdivision level.

    Returns (edges_in, verts_before, verts_after) so a 1:1 (no-op) bevel --
    Blender reports FINISHED even when `geom` was empty -- is visible to the
    caller instead of silently doing nothing.
    """
    bm = s.bm
    rid = s.regions.get(region)
    if rid is None:
        raise ValueError("bevel_region_boundary: unknown region %r" % (region,))
    rid_other = s.regions.get(region_other) if region_other else None
    edges = []
    for e in bm.edges:
        lf = e.link_faces
        if len(lf) != 2:
            continue
        ids = {f[s.region_layer] for f in lf}
        if rid not in ids or len(ids) < 2:
            continue
        if rid_other is not None and rid_other not in ids:
            continue
        edges.append(e)
    verts_before = len(bm.verts)
    if not edges:
        raise RuntimeError("bevel_region_boundary: no boundary edges found for region=%r "
                          "other=%r -- check the region names" % (region, region_other))
    bmesh.ops.bevel(bm, geom=edges, offset=float(width), offset_type='OFFSET',
                    segments=int(segments), affect='EDGES', clamp_overlap=True,
                    loop_slide=True, material=-1)
    bm.normal_update()
    verts_after = len(bm.verts)
    if verts_after <= verts_before:
        raise RuntimeError("bevel_region_boundary: bevel added no geometry for region=%r -- "
                          "Blender no-opped the operator" % (region,))
    return dict(edges_in=len(edges), verts_before=verts_before, verts_after=verts_after)
