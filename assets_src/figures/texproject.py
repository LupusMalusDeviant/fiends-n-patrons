"""Round 4: texture data that is continuous across UV seams and never shared
between two body parts.

Round 3 generated each material's pattern as a flat image in UV space and let
the UV islands tile over it at real-world scale. Two measurements on the
shipped imp showed what that costs once geometry is baked into those images:

- The pattern jumps at every UV seam: the median brightness step across a seam
  was 16 levels against 0.7 inside an island -- already in the freshly
  generated base, before any wear or bake. Each island simply shows an
  unrelated piece of the pattern.
- The tiled islands share texels: 55 % of the skin's used texels belong to more
  than one island, 81 % of the head's. Baking a shape normal or an occlusion
  mask into shared texels lets one body part overwrite another; in the head's
  shared texels the raw shape bake deviated 70 degrees (p90) against 9 in its
  unshared ones.

This module holds the plain-numpy half of the fix (no bpy, testable without
Blender): rasterise per-corner mesh data into a material's own, non-overlapping
UV layout, pad it past the island borders, and sample the tileable base pattern
by object-space position (triplanar) instead of by UV, so both sides of a seam
read the same pattern.
"""
import numpy as np


# ----------------------------------------------------------- rasterising ---
def uv_to_pixel(uv, res):
    """Blender UV (v up) -> continuous pixel coordinates (x right, y down,
    row 0 at the top), the orientation every PNG here is written in."""
    uv = np.asarray(uv, dtype=np.float64)
    return np.stack([uv[..., 0] * res, (1.0 - uv[..., 1]) * res], axis=-1)


def rasterize(tri_uv, tri_values, res):
    """Rasterise triangles into a res x res image by texel centre.

    tri_uv:     (T, 3, 2) UV per corner, Blender convention (v up).
    tri_values: (T, 3, C) value per corner, interpolated barycentrically.
    Returns (values (res, res, C) float64, filled (res, res) bool). A texel
    covered by several triangles keeps the last one; that only happens along
    shared edges inside one island, where both carry the same value.
    """
    tri_uv = np.asarray(tri_uv, dtype=np.float64)
    tri_values = np.asarray(tri_values, dtype=np.float64)
    channels = tri_values.shape[2]
    out = np.zeros((res, res, channels), dtype=np.float64)
    filled = np.zeros((res, res), dtype=bool)
    pix = uv_to_pixel(tri_uv, res)
    for (a, b, c), vals in zip(pix, tri_values):
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
        wc = 1.0 - wa - wb
        inside = (wa >= -1e-9) & (wb >= -1e-9) & (wc >= -1e-9)
        if not inside.any():
            continue
        iy, ix = np.nonzero(inside)
        w = np.stack([wa[inside], wb[inside], wc[inside]], axis=1)
        out[iy + y0, ix + x0] = w @ vals
        filled[iy + y0, ix + x0] = True
    return out, filled


def _shift(a, dy, dx):
    """Shift without wrapping; vacated cells are zero/False."""
    out = np.zeros_like(a)
    h, w = a.shape[:2]
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    out[yd, xd] = a[ys, xs]
    return out


def dilate(values, filled, pixels):
    """Grow each island outwards by `pixels` texels, averaging the filled
    neighbours, so bilinear filtering, mipmaps and the finite differences of
    the height-to-normal step read the island's own data past its border
    instead of the empty background. Never wraps across the image edge."""
    values = values.copy()
    filled = filled.copy()
    for _ in range(int(pixels)):
        acc = np.zeros_like(values)
        cnt = np.zeros(filled.shape, dtype=np.float64)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                m = _shift(filled, dy, dx)
                acc += _shift(values, dy, dx) * m[..., None]
                cnt += m
        grow = ~filled & (cnt > 0)
        if not grow.any():
            break
        values[grow] = acc[grow] / cnt[grow][:, None]
        filled = filled | grow
    return values, filled


# ------------------------------------------------------------- triplanar ---
PLANES = ((1, 2), (0, 2), (0, 1))          # plane seen along x, y, z
PLANE_OFFSETS = ((0.0, 0.0), (0.37, 0.61), (0.73, 0.19))  # decorrelate the three planes


def sample_wrap(image, u, v):
    """Bilinear sample of a tileable HxWxC image at tile coordinates (u, v),
    wrapping both axes. u runs along columns, v along rows."""
    h, w = image.shape[:2]
    x = np.asarray(u, dtype=np.float64) * w - 0.5
    y = np.asarray(v, dtype=np.float64) * h - 0.5
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    fx = (x - x0)[:, None]
    fy = (y - y0)[:, None]
    x0 %= w
    y0 %= h
    x1 = (x0 + 1) % w
    y1 = (y0 + 1) % h
    top = image[y0, x0] * (1.0 - fx) + image[y0, x1] * fx
    bottom = image[y1, x0] * (1.0 - fx) + image[y1, x1] * fx
    return top * (1.0 - fy) + bottom * fy


def triplanar(image, positions, normals, tile_m, sharpness=4.0):
    """Sample a tileable pattern (HxWxC, one tile = tile_m metres) at
    object-space positions, blending the three axis-aligned projections by
    the surface normal. The result depends only on position and normal, so
    two texels on either side of a UV seam -- same point, same normal -- get
    the same value."""
    positions = np.asarray(positions, dtype=np.float64)
    normals = np.asarray(normals, dtype=np.float64)
    weights = np.abs(normals) ** sharpness
    weights /= np.maximum(weights.sum(axis=1, keepdims=True), 1e-12)
    out = np.zeros((positions.shape[0], image.shape[2]), dtype=np.float64)
    for axis, ((a, b), (oa, ob)) in enumerate(zip(PLANES, PLANE_OFFSETS)):
        u = positions[:, a] / tile_m + oa
        v = positions[:, b] / tile_m + ob
        out += weights[:, axis:axis + 1] * sample_wrap(image, u, v)
    return out


# -------------------------------------------------------------- checking ---
def shared_texels(tri_uv, tri_island, res):
    """How many used texels belong to more than one island once UVs are
    wrapped into the unit square -- the question round 3's own overlap check
    never asked, because it compared islands only before wrapping.
    Returns (shared_fraction_of_used, used_fraction_of_image)."""
    tri_uv = np.asarray(tri_uv, dtype=np.float64)
    owner = -np.ones((res, res), dtype=np.int64)
    multi = np.zeros((res, res), dtype=bool)
    pix = tri_uv * res
    for (a, b, c), island in zip(pix, tri_island):
        x0 = int(np.floor(min(a[0], b[0], c[0])))
        x1 = int(np.ceil(max(a[0], b[0], c[0])))
        y0 = int(np.floor(min(a[1], b[1], c[1])))
        y1 = int(np.ceil(max(a[1], b[1], c[1])))
        denom = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(denom) < 1e-12:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
        wa = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / denom
        wb = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / denom
        inside = (wa >= 0) & (wb >= 0) & (wa + wb <= 1)
        tx = (xs[inside] - 0.5).astype(np.int64) % res
        ty = (ys[inside] - 0.5).astype(np.int64) % res
        prev = owner[ty, tx]
        multi[ty, tx] |= (prev >= 0) & (prev != island)
        owner[ty, tx] = island
    used = owner >= 0
    return float(multi.sum()) / max(int(used.sum()), 1), float(used.mean())


def uv_units_per_metre(tri_uv, tri_pos):
    """Area-weighted UV units per metre over a set of triangles."""
    tri_uv = np.asarray(tri_uv, dtype=np.float64)
    tri_pos = np.asarray(tri_pos, dtype=np.float64)
    e1, e2 = tri_uv[:, 1] - tri_uv[:, 0], tri_uv[:, 2] - tri_uv[:, 0]
    area_uv = np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]).sum() * 0.5
    p1, p2 = tri_pos[:, 1] - tri_pos[:, 0], tri_pos[:, 2] - tri_pos[:, 0]
    area_3d = np.linalg.norm(np.cross(p1, p2), axis=1).sum() * 0.5
    return float(np.sqrt(area_uv / max(area_3d, 1e-12)))
