"""Round 4: the LOD shape normal map without Cycles' selected-to-active bake.

The low level of a figure is the same cage subdivided once, the high level
subdivided twice. Blender places the vertices of both on the same limit
surface -- measured on the imp: every low vertex lies 0.00 mm from the high
surface, and the two normals agree to a median of 5.7 degrees on the skin and
14 on the horns. The shape normal map only has to carry that small
difference.

Cycles' ray bake did not: on the round-4 imp it wrote an exactly inverted
normal (0, 0, -1) into 39 % of the horn's texels and 5 % of the skin's, and in
round 3 it left the horn completely flat. Instead of tuning ray distances
around that, this module takes the high surface's own smooth normal at the
nearest point to every texel and expresses it in the low level's tangent
frame (MikkTSpace tangent and bitangent sign, as exported to glTF). No rays, no
far wall to hit, and the same result on every run.

A high normal that faces away from the low surface cannot be one of those
small differences. On the imp's horn such texels form thin lines along the
ridges (12 % of its texels before this rule), most likely where the sculpted
grooves fold the high surface over itself; they fall back to the low level's
own normal (flat in tangent space), and the count is reported.

test_normal_convention.py checks it against Blender's bake on a displaced
dome, where that bake is correct.
"""
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import texproject as TP


def _normalise(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


def high_surface(high_ob):
    """Triangles, corner normals and a BVH of the high level, in mesh space."""
    me = high_ob.data
    me.calc_loop_triangles()
    nv, nl, nt = len(me.vertices), len(me.loops), len(me.loop_triangles)
    co = np.empty(nv * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(nv, 3).astype(np.float64)
    nrm = np.empty(nl * 3, dtype=np.float32)
    me.corner_normals.foreach_get("vector", nrm)
    tri_verts = np.empty(nt * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("vertices", tri_verts)
    tri_loops = np.empty(nt * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("loops", tri_loops)
    tri_verts = tri_verts.reshape(nt, 3)
    bvh = BVHTree.FromPolygons([tuple(c) for c in co], [tuple(t) for t in tri_verts.tolist()],
                               all_triangles=True)
    return dict(co=co, corner_normals=nrm.reshape(nl, 3).astype(np.float64),
                tri_verts=tri_verts, tri_loops=tri_loops.reshape(nt, 3), bvh=bvh)


def high_normals_at(surface, points):
    """Smooth normal of the high level at the surface point nearest to each
    of `points` (M x 3), interpolated from the triangle's corner normals."""
    points = np.asarray(points, dtype=np.float64)
    tri = np.empty(len(points), dtype=np.int64)
    loc = np.empty((len(points), 3), dtype=np.float64)
    find = surface["bvh"].find_nearest
    for k, p in enumerate(points):
        hit, _normal, index, _dist = find(Vector(p))
        tri[k] = index
        loc[k] = hit
    tv = surface["tri_verts"][tri]
    a, b, c = surface["co"][tv[:, 0]], surface["co"][tv[:, 1]], surface["co"][tv[:, 2]]
    v0, v1, v2 = b - a, c - a, loc - a
    d00 = (v0 * v0).sum(1)
    d01 = (v0 * v1).sum(1)
    d11 = (v1 * v1).sum(1)
    d20 = (v2 * v0).sum(1)
    d21 = (v2 * v1).sum(1)
    denom = np.where(np.abs(d00 * d11 - d01 * d01) < 1e-20, 1e-20, d00 * d11 - d01 * d01)
    wb = (d11 * d20 - d01 * d21) / denom
    wc = (d00 * d21 - d01 * d20) / denom
    wa = 1.0 - wb - wc
    tl = surface["tri_loops"][tri]
    cn = surface["corner_normals"]
    n = wa[:, None] * cn[tl[:, 0]] + wb[:, None] * cn[tl[:, 1]] + wc[:, None] * cn[tl[:, 2]]
    return _normalise(n)


def low_corner_frames(low_ob, uv_name):
    """Per loop-triangle corner: UV, position, normal, MikkTSpace tangent and
    bitangent sign of the low level, plus the triangle's material index."""
    me = low_ob.data
    me.calc_loop_triangles()
    me.calc_tangents(uvmap=uv_name)
    nv, nl, nt = len(me.vertices), len(me.loops), len(me.loop_triangles)
    co = np.empty(nv * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    uv = np.empty(nl * 2, dtype=np.float32)
    me.uv_layers[uv_name].data.foreach_get("uv", uv)
    nrm = np.empty(nl * 3, dtype=np.float32)
    me.loops.foreach_get("normal", nrm)
    tan = np.empty(nl * 3, dtype=np.float32)
    me.loops.foreach_get("tangent", tan)
    sign = np.empty(nl, dtype=np.float32)
    me.loops.foreach_get("bitangent_sign", sign)
    tri_loops = np.empty(nt * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("loops", tri_loops)
    tri_verts = np.empty(nt * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("vertices", tri_verts)
    tri_mat = np.empty(nt, dtype=np.int32)
    me.loop_triangles.foreach_get("material_index", tri_mat)
    return dict(co=co.reshape(nv, 3).astype(np.float64), uv=uv.reshape(nl, 2).astype(np.float64),
                nrm=nrm.reshape(nl, 3).astype(np.float64), tan=tan.reshape(nl, 3).astype(np.float64),
                sign=sign.astype(np.float64), tri_loops=tri_loops.reshape(nt, 3),
                tri_verts=tri_verts.reshape(nt, 3), tri_mat=tri_mat)


MIN_FACING = 0.2  # tangent-space z below this is treated as a fold, not a shape


def shape_normal_map(surface, frames, slot, res, gutter_px):
    """Tangent-space shape normal of one material slot of the low level.

    Returns (normal HxWx3 in [-1, 1], filled HxW, core HxW, folded HxW);
    texels outside the islands and their gutter, and texels whose high normal
    faces away (folded), are flat (0, 0, 1). Row 0 is the top of the image
    (v = 1), like every map written here.
    """
    sel = frames["tri_mat"] == slot
    tl, tv = frames["tri_loops"][sel], frames["tri_verts"][sel]
    corner = np.concatenate([frames["co"][tv], frames["nrm"][tl], frames["tan"][tl],
                             frames["sign"][tl][..., None]], axis=2)
    values, core = TP.rasterize(frames["uv"][tl], corner, res)
    values, filled = TP.dilate(values, core, gutter_px)

    v = values[filled]
    high = high_normals_at(surface, v[:, 0:3])
    n = _normalise(v[:, 3:6])
    t = _normalise(v[:, 6:9] - n * (v[:, 6:9] * n).sum(1, keepdims=True))
    s = np.where(v[:, 9] < 0.0, -1.0, 1.0)
    b = s[:, None] * np.cross(n, t)
    ts = _normalise(np.stack([(t * high).sum(1), (b * high).sum(1), (n * high).sum(1)], axis=1))
    fold = ts[:, 2] < MIN_FACING
    ts[fold] = (0.0, 0.0, 1.0)

    out = np.zeros((res, res, 3), dtype=np.float64)
    out[..., 2] = 1.0
    out[filled] = ts
    folded = np.zeros((res, res), dtype=bool)
    folded[filled] = fold
    return out, filled, core, folded
