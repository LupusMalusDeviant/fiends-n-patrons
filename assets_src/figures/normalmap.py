"""Tangent-space normal map helpers shared by the round-2 texture generator and
the LOD normal bake combiner. Pure numpy, no bpy -- OpenGL convention (+Y is
"up" in V, matching the game's texture contract).
"""
import numpy as np


def height_to_normal(height_m, texel_size_m):
    """Central-difference slope -> unit tangent-space normal.

    height_m: HxW array of surface displacement in metres, row 0 at the top of
      the image (v = 1), as every PNG here is written.
    texel_size_m: (du_m, dv_m), the physical size of one pixel.
    Tileable: gradients wrap around both axes, matching REPEAT texturing.

    Rows run downwards while V runs upwards, so the row difference is the
    NEGATIVE V derivative. Until this was checked against Blender's own
    tangent-space bake (test_normal_convention.py: red +1.000, green -1.000)
    the row difference was used as-is, and every generated detail normal map
    had its green channel inverted.
    """
    du, dv = texel_size_m
    h = np.asarray(height_m, dtype=np.float64)
    dhdu = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) / (2.0 * du)
    dhdv = -(np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) / (2.0 * dv)
    n = np.stack([-dhdu, -dhdv, np.ones_like(h)], axis=-1)
    n = n / np.linalg.norm(n, axis=-1, keepdims=True)
    return n


def encode_normal(n):
    """Unit normal array (...,3) in [-1,1] -> uint8 RGB in [0,255]."""
    rgb = np.clip((n * 0.5 + 0.5) * 255.0, 0, 255)
    return np.round(rgb).astype(np.uint8)


def decode_normal(rgb_u8):
    """uint8 RGB -> unit normal array (...,3)."""
    n = rgb_u8.astype(np.float64) / 255.0 * 2.0 - 1.0
    norm = np.linalg.norm(n, axis=-1, keepdims=True)
    norm = np.where(norm < 1e-9, 1.0, norm)
    return n / norm


def slope_degrees(n):
    """Angle between the normal and +Z (the flat reference), in degrees."""
    nz = np.clip(n[..., 2], -1.0, 1.0)
    return np.degrees(np.arccos(nz))


def reoriented_normal_blend(base, detail):
    """Combine two tangent-space normals (unit vectors, ...,3): `base` carries
    the coarse shape (e.g. a baked LOD shape delta), `detail` the fine texture
    (pores, weave). Reoriented Normal Mapping (Colin Barre-Brisebois): keeps
    both contributions instead of one washing out the other in a naive average.
    """
    t = base.copy()
    t[..., 2] += 1.0
    u = detail.copy()
    u[..., 0] *= -1.0
    u[..., 1] *= -1.0
    dot = np.sum(t * u, axis=-1, keepdims=True)
    out = t * dot / np.clip(t[..., 2:3], 1e-6, None) - u
    n = out / np.linalg.norm(out, axis=-1, keepdims=True)
    return n
