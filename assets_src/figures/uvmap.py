"""UV unwrapping with code-placed seams and per-material texel density.

Not a box projection: seams are marked on specific edges (the centre back line,
the armpit and groin rings, wrist and ankle rings, the neck ring, the horn and
tail bases), the mesh is unwrapped angle-based, packed, and then each material's
islands are scaled so one UV unit spans that material's tile size in metres.

Because the snapshot textures tile (REPEAT), UVs are allowed to run outside the
0..1 square; what matters is that the texel density is right and that islands of
the *same* material do not overlap. Islands of different materials may overlap
freely -- they sample different textures.
"""
import bmesh
import bpy
import numpy as np

import palette as P


# ---------------------------------------------------------------- seams ---
def mark_seams(ob, rules):
    """Mark seams from declarative rules evaluated per edge.

    Each rule is a dict with any of:
      z        (zmin, zmax)   edge midpoint height band
      radius   (centre, r)    edge midpoint inside a sphere
      axis_line(axis, value, tol, other_axis_range)  a straight line of edges
      region_border (a, b)    edge between two material regions
    """
    me = ob.data
    n = 0
    region_of = _face_region_map(me)
    for e in me.edges:
        a = me.vertices[e.vertices[0]].co
        b = me.vertices[e.vertices[1]].co
        mid = (a + b) / 2.0
        if any(_rule_matches(rule, e, mid, a, b, me, region_of) for rule in rules):
            e.use_seam = True
            n += 1
    return n


def _face_region_map(me):
    attr = me.attributes.get("region")
    if attr is None:
        return None
    return [int(d.value) for d in attr.data]


def _edge_faces(me, edge_index, cache={}):
    key = id(me)
    if cache.get("key") != key:
        m = {}
        for p in me.polygons:
            for ek in p.edge_keys:
                m.setdefault(ek, []).append(p.index)
        cache.clear()
        cache["key"] = key
        cache["map"] = m
    return cache["map"]


def _rule_matches(rule, e, mid, a, b, me, region_of):
    if "z" in rule:
        lo, hi = rule["z"]
        if not (lo <= mid.z <= hi):
            return False
    if "radius" in rule:
        c, r = rule["radius"]
        if (mid - _vec(c)).length > r:
            return False
    if "plane" in rule:
        # A ring of edges: both endpoints lie (almost) on a plane through `point`
        # with the given normal -- this is how a wrist or neck ring is selected.
        point, normal, tol = rule["plane"]
        nrm = _vec(normal).normalized()
        da = abs((a - _vec(point)).dot(nrm))
        db = abs((b - _vec(point)).dot(nrm))
        if da > tol or db > tol:
            return False
    if "line" in rule:
        # A straight seam running along one axis, e.g. the centre back line.
        axis, value, tol = rule["line"]
        i = "xyz".index(axis)
        if abs(a[i] - value) > tol or abs(b[i] - value) > tol:
            return False
    if "side" in rule:
        axis, sign = rule["side"]
        i = "xyz".index(axis)
        if sign > 0 and mid[i] < rule.get("side_min", 0.0):
            return False
        if sign < 0 and mid[i] > -rule.get("side_min", 0.0):
            return False
    if "region_border" in rule and region_of is not None:
        want = set(rule["region_border"])
        emap = _edge_faces(me, e.index)
        faces = emap.get(tuple(sorted(e.vertices)), [])
        got = {region_of[f] for f in faces}
        if len(got) < 2 or not want.issubset(got):
            return False
    return True


def _vec(v):
    from mathutils import Vector
    return v if hasattr(v, "length") else Vector(tuple(v))


# -------------------------------------------------------------- unwrap ---
def unwrap(ob, margin=0.01):
    """Angle-based unwrap along the marked seams, then pack."""
    # Make the object active BEFORE any mode_set: with no active object the
    # operator's poll fails and Blender raises instead of quietly doing nothing.
    bpy.context.view_layer.objects.active = ob
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    if P.UV_NAME not in ob.data.uv_layers:
        ob.data.uv_layers.new(name=P.UV_NAME)
    ob.data.uv_layers[P.UV_NAME].active = True
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=margin, correct_aspect=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    # bpy.ops.uv.average_islands_scale() reports FINISHED here but leaves the
    # spread untouched (it even made it worse), so island scale is equalised
    # explicitly below before packing.
    normalize_island_density(ob)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True, margin=margin)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')


def normalize_island_density(ob):
    """Give every UV island the same texel density.

    Each island is scaled about its own UV centroid until its density matches
    the area-weighted median across islands. Packing afterwards only moves and
    uniformly rescales islands, so this equality survives it, and the final
    per-material scale then sets the absolute density.
    """
    me = ob.data
    uvl = me.uv_layers[P.UV_NAME]
    ids = island_ids(me)
    acc = {}
    for poly in me.polygons:
        isl = ids[poly.index]
        pts = np.array([tuple(uvl.data[li].uv) for li in poly.loop_indices])
        a_uv = 0.0
        for i in range(1, len(pts) - 1):
            v1, v2 = pts[i] - pts[0], pts[i + 1] - pts[0]
            a_uv += abs(v1[0] * v2[1] - v1[1] * v2[0]) * 0.5
        a3, luv, n = acc.get(isl, (0.0, [], 0))
        acc[isl] = (a3 + poly.area, luv + list(poly.loop_indices), n + a_uv)
    dens = {isl: (uvA / a3) ** 0.5 for isl, (a3, _, uvA) in acc.items()
            if a3 > 1e-12 and uvA > 1e-15}
    if not dens:
        return 0
    weights = np.array([acc[i][0] for i in dens])
    values = np.array([dens[i] for i in dens])
    order = np.argsort(values)
    cum = np.cumsum(weights[order])
    target = float(values[order][int(np.searchsorted(cum, cum[-1] * 0.5))])
    changed = 0
    for isl, (a3, loops, uvA) in acc.items():
        d = dens.get(isl)
        if not d or d <= 1e-12:
            continue
        factor = target / d
        if abs(factor - 1.0) < 1e-6:
            continue
        coords = np.array([tuple(uvl.data[li].uv) for li in loops])
        centre = coords.mean(axis=0)
        for li, co in zip(loops, centre + (coords - centre) * factor):
            uvl.data[li].uv = (float(co[0]), float(co[1]))
        changed += 1
    return changed


# ------------------------------------------------------- texel density ---
def _areas(ob, uv_layer_name):
    """Per-face (3D area in m^2, UV area in uv^2, material index)."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    uv = bm.loops.layers.uv.get(uv_layer_name)
    rows = []
    for f in bm.faces:
        pts = np.array([tuple(l[uv].uv) for l in f.loops], dtype=np.float64)
        area_uv = 0.0
        for i in range(1, len(pts) - 1):
            v1, v2 = pts[i] - pts[0], pts[i + 1] - pts[0]
            area_uv += abs(v1[0] * v2[1] - v1[1] * v2[0]) * 0.5
        rows.append((f.calc_area(), area_uv, f.material_index))
    bm.free()
    return rows


def scale_to_tile_size(ob, tile_size_for_slot, resolution=P.TEXTURE_RESOLUTION):
    """Scale each material's islands so one UV unit spans its tile size.

    Scaling is uniform about the UV origin per material group, so islands that
    did not overlap before still do not overlap afterwards.
    """
    me = ob.data
    uv_layer = me.uv_layers[P.UV_NAME]
    rows = _areas(ob, P.UV_NAME)
    per_slot = {}
    for area3, areauv, slot in rows:
        a, b = per_slot.get(slot, (0.0, 0.0))
        per_slot[slot] = (a + area3, b + areauv)
    factors, report = {}, {}
    for slot, (area3, areauv) in per_slot.items():
        tile = tile_size_for_slot.get(slot)
        if area3 <= 1e-12 or areauv <= 1e-15:
            factors[slot] = 1.0
            continue
        current = (areauv / area3) ** 0.5            # uv units per metre
        target = 1.0 / float(tile if tile else 1.0)  # one tile per tile_size metres
        factors[slot] = target / current
    for poly in me.polygons:
        f = factors.get(poly.material_index, 1.0)
        for li in poly.loop_indices:
            uv_layer.data[li].uv = uv_layer.data[li].uv * f
    rows = _areas(ob, P.UV_NAME)
    for slot, (area3, areauv) in _grouped(rows).items():
        if area3 <= 1e-12:
            continue
        uv_per_m = (areauv / area3) ** 0.5
        tile = tile_size_for_slot.get(slot)
        name = me.materials[slot].name if slot < len(me.materials) else str(slot)
        report[name] = dict(
            tile_size_m=tile,
            # An untextured material has no texel density to speak of; saying
            # "1024 px/m" there would be a made-up number.
            texel_density_px_per_m=(round(uv_per_m * resolution, 1) if tile else None),
            textured=bool(tile), uv_units_per_m=round(uv_per_m, 4),
            uv_area=round(areauv, 4), surface_area_m2=round(area3, 4))
    return report


def _grouped(rows):
    per = {}
    for area3, areauv, slot in rows:
        a, b = per.get(slot, (0.0, 0.0))
        per[slot] = (a + area3, b + areauv)
    return per


def density_spread(ob):
    """Per-face texel density spread: how uniform the mapping actually is.

    Reported as the ratio between the 90th and 10th percentile; anything past
    about 3 means the unwrap is stretching somewhere.
    """
    rows = [(a3, auv) for a3, auv, _ in _areas(ob, P.UV_NAME) if a3 > 1e-9 and auv > 1e-12]
    if not rows:
        return dict(faces=0)
    d = np.array([(auv / a3) ** 0.5 for a3, auv in rows])
    p10, p50, p90 = np.percentile(d, [10, 50, 90])
    return dict(faces=len(d), p10=float(p10), median=float(p50), p90=float(p90),
                spread_p90_over_p10=float(p90 / max(p10, 1e-9)))


def island_ids(me):
    """Island index per face: faces joined across any edge that is not a seam."""
    parent = list(range(len(me.polygons)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    seams = {tuple(sorted(e.vertices)) for e in me.edges if e.use_seam}
    by_edge = {}
    for p in me.polygons:
        for ek in p.edge_keys:
            by_edge.setdefault(ek, []).append(p.index)
    for ek, faces in by_edge.items():
        if ek in seams:
            continue
        for f in faces[1:]:
            union(faces[0], f)
    return [find(i) for i in range(len(me.polygons))]


def overlap_check(ob, samples=128):
    """Do islands of the SAME material overlap in UV space?

    Neighbouring faces inside one island naturally share grid cells, so counting
    raw multi-coverage says nothing. Only cells touched by two *different*
    islands of the same material are real overlap. Islands of different
    materials may overlap freely -- they sample different textures.
    """
    me = ob.data
    uv_layer = me.uv_layers[P.UV_NAME]
    ids = island_ids(me)
    grids = {}
    for poly in me.polygons:
        g = grids.setdefault(poly.material_index, {})
        pts = np.array([tuple(uv_layer.data[li].uv) for li in poly.loop_indices])
        lo = np.floor(pts.min(axis=0) * samples).astype(int)
        hi = np.ceil(pts.max(axis=0) * samples).astype(int)
        for gx in range(lo[0], hi[0] + 1):
            for gy in range(lo[1], hi[1] + 1):
                g.setdefault((gx, gy), set()).add(ids[poly.index])
    out = {}
    for slot, g in grids.items():
        name = me.materials[slot].name if slot < len(me.materials) else str(slot)
        cells = len(g)
        clashing = sum(1 for v in g.values() if len(v) > 1)
        out[name] = dict(islands=len({ids[p.index] for p in me.polygons
                                      if p.material_index == slot}),
                         cells=cells, cross_island_cells=clashing,
                         fraction=round(clashing / max(cells, 1), 3))
    return out
