"""Plain-python checks for texproject.py (no Blender).

  python -B test_texproject.py
"""
import numpy as np

import texproject as TP

RES = 128


def quad(uv_corners, pos_corners):
    """Two triangles of a quad: (tri_uv (2,3,2), tri_pos (2,3,3))."""
    uv = np.asarray(uv_corners, dtype=np.float64)
    pos = np.asarray(pos_corners, dtype=np.float64)
    order = ((0, 1, 2), (0, 2, 3))
    return uv[list(order)], pos[list(order)]


def test_rasterize_covers_area_and_interpolates():
    tri_uv = np.array([[[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]])
    tri_val = np.array([[[0.0], [1.0], [0.0]]])  # value = u
    values, filled = TP.rasterize(tri_uv, tri_val, RES)
    assert abs(filled.mean() - 0.5) < 0.02, filled.mean()
    iy, ix = np.nonzero(filled)
    u = (ix + 0.5) / RES
    assert np.allclose(values[iy, ix, 0], u, atol=1e-9)


def test_dilate_grows_without_wrapping():
    values = np.zeros((RES, RES, 1))
    filled = np.zeros((RES, RES), dtype=bool)
    filled[10:20, 0:5] = True
    values[filled] = 7.0
    grown, gfilled = TP.dilate(values, filled, 3)
    assert gfilled[10:20, 0:8].all() and not gfilled[10:20, 9:].any()
    assert not gfilled[:, RES - 3:].any(), "dilation wrapped across the image edge"
    assert np.allclose(grown[gfilled, 0], 7.0)


def test_triplanar_is_continuous_across_a_uv_seam():
    # A flat 1 m x 1 m strip at z = 0, cut at x = 0.5 into two UV islands. The
    # right island is rotated by 90 degrees in UV, so a pattern looked up by UV
    # cannot line up across the cut; a pattern looked up by position must.
    rng = np.random.default_rng(3)
    small = rng.normal(size=(16, 16, 1))
    pattern = np.repeat(np.repeat(small, 8, axis=0), 8, axis=1)  # tileable, blocky
    left_uv, left_pos = quad([[0.05, 0.05], [0.45, 0.05], [0.45, 0.85], [0.05, 0.85]],
                             [[0, 0, 0], [0.5, 0, 0], [0.5, 1, 0], [0, 1, 0]])
    right_uv, right_pos = quad([[0.55, 0.45], [0.55, 0.05], [0.95, 0.05], [0.95, 0.45]],
                               [[0.5, 0, 0], [1, 0, 0], [1, 1, 0], [0.5, 1, 0]])
    tri_uv = np.concatenate([left_uv, right_uv])
    tri_pos = np.concatenate([left_pos, right_pos])
    tri_nrm = np.zeros_like(tri_pos)
    tri_nrm[..., 2] = 1.0
    values, filled = TP.rasterize(tri_uv, np.concatenate([tri_pos, tri_nrm], axis=2), RES)

    iy, ix = np.nonzero(filled)
    pos, nrm = values[iy, ix, :3], values[iy, ix, 3:]
    by_position = TP.triplanar(pattern, pos, nrm, tile_m=1.0)[:, 0]
    by_uv = TP.sample_wrap(pattern, (ix + 0.5) / RES, (iy + 0.5) / RES)[:, 0]

    near = np.abs(pos[:, 0] - 0.5) < 0.02
    left = near & (pos[:, 0] < 0.5)
    right = near & (pos[:, 0] >= 0.5)
    y_left, y_right = pos[left, 1], pos[right, 1]

    def seam_step(field):
        # Pair every left texel with the right texel at the nearest height.
        j = np.abs(y_left[:, None] - y_right[None, :]).argmin(axis=1)
        return float(np.median(np.abs(field[left] - field[right][j])))

    step_pos, step_uv = seam_step(by_position), seam_step(by_uv)
    assert step_pos < 0.05, step_pos
    assert step_uv > 0.3, step_uv


def test_shared_texels_detects_wrapped_overlap():
    tri = np.array([[[0.1, 0.1], [0.4, 0.1], [0.1, 0.4]]])
    moved = tri + 1.0  # the same place once wrapped into the unit square
    shared, _ = TP.shared_texels(np.concatenate([tri, moved]), [0, 1], 64)
    assert shared > 0.95, shared
    apart = tri + np.array([0.5, 0.5])
    shared, _ = TP.shared_texels(np.concatenate([tri, apart]), [0, 1], 64)
    assert shared == 0.0, shared


def test_uv_units_per_metre():
    uv, pos = quad([[0, 0], [0.5, 0], [0.5, 0.5], [0, 0.5]],
                   [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]])
    assert abs(TP.uv_units_per_metre(uv, pos) - 0.5) < 1e-9


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("TEST_TEXPROJECT_OK True")
