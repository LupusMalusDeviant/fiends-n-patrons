"""Deterministic, periodic relief fields for creature and player materials.

The unit square repeats in U and V. Heights are meters; normal-map baking must
use the physical repeat size from the material catalog. Albedo is an additive
pigment variation only: lighting and cavity shadows belong in separate maps.
Patterns emphasize broad anatomical, woven, and worked-surface structures.
"""

from __future__ import annotations

import numpy as np


MATERIAL_IDS = (
    "demon_horn", "plague_hide", "charred_carapace", "exposed_sinew",
    "void_hide", "bone_armor", "player_leather", "player_wraps",
    "player_steel", "player_inner_cloth", "player_silver_trim", "player_blade",
)

_TAU = np.float32(2.0 * np.pi)


def _smooth(lo, hi, field):
    t = np.clip((field - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _noise(x, y, cells, rng):
    """Quintic value noise with wrapping lattice indices on both axes."""
    grid = rng.uniform(-1.0, 1.0, (cells, cells)).astype(np.float32)
    px, py = x * cells, y * cells
    ix, iy = np.floor(px).astype(np.int32), np.floor(py).astype(np.int32)
    tx, ty = (px - ix).astype(np.float32), (py - iy).astype(np.float32)
    sx = tx * tx * tx * (tx * (tx * 6.0 - 15.0) + 10.0)
    sy = ty * ty * ty * (ty * (ty * 6.0 - 15.0) + 10.0)
    a, b = grid[iy % cells, ix % cells], grid[iy % cells, (ix + 1) % cells]
    c = grid[(iy + 1) % cells, ix % cells]
    d = grid[(iy + 1) % cells, (ix + 1) % cells]
    return (a + (b - a) * sx) * (1.0 - sy) + (c + (d - c) * sx) * sy


def _cloud(x, y, rng):
    return (
        0.66 * _noise(x, y, 3, rng)
        + 0.26 * _noise(x, y, 6, rng)
        + 0.08 * _noise(x, y, 10, rng)
    )


def _finish(height, pigment, roughness, ao=1.0):
    shape = height.shape
    fields = {
        "height_m": np.maximum(height, 0.0),
        "albedo_variation": np.clip(pigment, -0.15, 0.15),
        "roughness_variation": np.clip(roughness, -0.08, 0.08),
        "ao": np.clip(ao, 0.85, 1.0),
    }
    return {
        key: np.ascontiguousarray(np.broadcast_to(value, shape), dtype=np.float32)
        for key, value in fields.items()
    }


def _demon_horn(x, y, rng):
    bend = _noise(x, y, 3, rng)
    pigment = _cloud(x, y, rng)
    # Transverse growth rings wrap around the long U-directed flutes.
    rings = 0.5 + 0.5 * np.cos(_TAU * (6.0 * y + 0.16 * bend))
    flutes = np.sin(_TAU * (3.0 * x + 0.10 * np.sin(_TAU * y)))
    ring_ridge = _smooth(0.25, 0.90, rings)
    height = 0.0015 + 0.0010 * ring_ridge + 0.00030 * flutes + 0.00018 * bend
    return _finish(height, 0.072 * pigment, 0.030 * pigment - 0.014 * ring_ridge)


def _plague_hide(x, y, rng):
    swelling = _noise(x, y, 3, rng)
    fold = _noise(x + 0.045 * swelling, y, 5, rng)
    pigment = _cloud(x, y, rng)
    # Large irregular swollen regions, never tiny circular pustule highlights.
    raised = _smooth(-0.12, 0.55, swelling)
    crease = 1.0 - _smooth(0.055, 0.22, np.abs(fold))
    height = 0.0016 + 0.0015 * raised - 0.00045 * crease + 0.00012 * pigment
    return _finish(
        height, 0.088 * pigment, 0.026 * pigment + 0.022 * raised,
        1.0 - 0.070 * crease,
    )


def _charred_carapace(x, y, rng):
    warp = _noise(x, y, 3, rng)
    pigment = _cloud(x, y, rng)
    vertical = np.sin(_TAU * (3.0 * x + 0.12 * warp))
    horizontal = np.sin(_TAU * (2.0 * y + 0.20 * np.sin(_TAU * x)))
    seam_u = 1.0 - _smooth(0.10, 0.39, np.abs(vertical))
    seam_v = 1.0 - _smooth(0.10, 0.39, np.abs(horizontal))
    seam = 1.0 - (1.0 - seam_u) * (1.0 - seam_v)
    plate = np.sqrt(np.clip(np.abs(vertical * horizontal), 0.0, 1.0) + 0.02)
    height = 0.0013 + 0.0016 * plate - 0.00055 * seam + 0.00015 * pigment
    return _finish(height, 0.062 * pigment, 0.030 * pigment + 0.025 * seam,
                   1.0 - 0.10 * seam)


def _exposed_sinew(x, y, rng):
    bend = _noise(x, y, 3, rng)
    pigment = _cloud(x, y, rng)
    # Long bundles pinch together under broad transverse fascia bands.
    bundles = 0.5 + 0.5 * np.cos(_TAU * (7.0 * x + 0.22 * bend))
    fascia = _smooth(0.45, 0.92, 0.5 + 0.5 * np.cos(_TAU * (2.0 * y + 0.09 * bend)))
    bundle_relief = _smooth(0.08, 0.92, bundles) * (1.0 - 0.42 * fascia)
    height = 0.0010 + 0.0012 * bundle_relief + 0.00030 * fascia + 0.00012 * bend
    return _finish(height, 0.090 * pigment, 0.027 * pigment + 0.012 * fascia,
                   0.965 + 0.035 * bundles)


def _void_hide(x, y, rng):
    drift = _noise(x, y, 3, rng)
    pigment = _cloud(x, y, rng)
    membrane = np.sin(_TAU * (2.0 * x + y + 0.14 * drift))
    tension = np.cos(_TAU * (x - 2.0 * y + 0.11 * drift))
    # Soft intersecting tension folds, with no stars, speckles, or emission.
    height = 0.0014 + 0.00048 * membrane + 0.00032 * tension + 0.00012 * drift
    return _finish(height, 0.055 * pigment, 0.022 * pigment + 0.010 * tension)


def _bone_armor(x, y, rng):
    pigment = _cloud(x, y, rng)
    bend = _noise(x, y, 3, rng)
    phase = _TAU * (4.0 * y + 0.20 * np.cos(_TAU * 2.0 * x) + 0.06 * bend)
    lamella = 0.5 + 0.5 * np.cos(phase)
    suture = 1.0 - _smooth(0.08, 0.30, lamella)
    longitudinal = np.sin(_TAU * (3.0 * x + 0.09 * bend))
    height = 0.0015 + 0.00070 * lamella - 0.00035 * suture + 0.00012 * longitudinal
    return _finish(height, 0.077 * pigment, 0.030 * pigment + 0.012 * suture,
                   1.0 - 0.060 * suture)


def _player_leather(x, y, rng):
    grain = _noise(x, y, 6, rng)
    dye = _cloud(x, y, rng)
    folds = np.sin(_TAU * (3.0 * x + 0.13 * np.sin(_TAU * 2.0 * y)))
    creases = 1.0 - _smooth(0.06, 0.23, np.abs(grain))
    # Soft stress folds and broad pebbled grain keep leather distinct from skin.
    height = 0.0010 + 0.00040 * folds + 0.00013 * grain - 0.00016 * creases
    return _finish(height, 0.082 * dye, 0.031 * dye + 0.015 * creases,
                   1.0 - 0.025 * creases)


def _player_wraps(x, y, rng):
    dye = _cloud(x, y, rng)
    bend = _noise(x, y, 3, rng)
    phase = 3.0 * x + 4.0 * y + 0.04 * bend
    # Diagonal cloth overlaps use broad rounded lips rather than hard sawteeth.
    lip = (0.5 + 0.5 * np.cos(_TAU * phase)) ** 2
    fabric = np.cos(_TAU * (8.0 * x - 6.0 * y + 0.025 * bend))
    height = 0.0010 + 0.00065 * lip + 0.00005 * fabric + 0.00008 * bend
    return _finish(height, 0.060 * dye, 0.025 * dye,
                   1.0 - 0.030 * (1.0 - lip))


def _player_steel(x, y, rng):
    work = _noise(x, y, 5, rng)
    oxide = _cloud(x, y, rng)
    scour = np.sin(_TAU * (5.0 * x + 2.0 * y + 0.12 * work))
    wave = np.cos(_TAU * (2.0 * x - y + 0.04 * work))
    # Shallow worked steel: roughness variation dominates normal-map detail.
    height = 0.00040 + 0.00010 * work + 0.000028 * scour + 0.000025 * wave
    return _finish(height, 0.044 * oxide, 0.033 * oxide + 0.014 * scour)


def _player_inner_cloth(x, y, rng):
    dye = _cloud(x, y, rng)
    bend = _noise(x, y, 3, rng)
    drape = np.sin(_TAU * (2.0 * x + 0.14 * np.sin(_TAU * y) + 0.06 * bend))
    twill = np.sin(_TAU * (8.0 * x - 8.0 * y + 0.03 * bend))
    # Twill stays almost flat so small player silhouettes do not sparkle.
    height = 0.0010 + 0.00055 * drape + 0.000032 * twill + 0.00005 * bend
    return _finish(height, 0.068 * dye, 0.021 * dye)


def _player_silver_trim(x, y, rng):
    tarnish = _cloud(x, y, rng)
    warp = _noise(x, y, 3, rng)
    braid_a = np.sin(_TAU * (3.0 * x + y + 0.06 * warp))
    braid_b = np.sin(_TAU * (3.0 * x - y + 0.06 * warp))
    groove_a = 1.0 - _smooth(0.12, 0.45, np.abs(braid_a))
    groove_b = 1.0 - _smooth(0.12, 0.45, np.abs(braid_b))
    engraving = 1.0 - (1.0 - groove_a) * (1.0 - groove_b)
    height = 0.00055 + 0.000035 * warp - 0.00014 * engraving
    return _finish(height, 0.036 * tarnish, 0.030 * tarnish + 0.018 * engraving,
                   1.0 - 0.028 * engraving)


def _player_blade(x, y, rng):
    patina = _cloud(x, y, rng)
    work = _noise(x, y, 3, rng)
    grinding = np.sin(_TAU * (7.0 * x + y + 0.025 * work))
    fuller = 0.5 + 0.5 * np.cos(_TAU * x)
    # Very shallow lengthwise finishing; the model still supplies blade bevels.
    height = 0.00025 + 0.000025 * work + 0.000015 * grinding - 0.000045 * fuller
    return _finish(height, 0.032 * patina, 0.022 * patina + 0.011 * grinding)


_RECIPES = {
    "demon_horn": _demon_horn,
    "plague_hide": _plague_hide,
    "charred_carapace": _charred_carapace,
    "exposed_sinew": _exposed_sinew,
    "void_hide": _void_hide,
    "bone_armor": _bone_armor,
    "player_leather": _player_leather,
    "player_wraps": _player_wraps,
    "player_steel": _player_steel,
    "player_inner_cloth": _player_inner_cloth,
    "player_silver_trim": _player_silver_trim,
    "player_blade": _player_blade,
}


def make_surface(material_id: str, size: int, seed: int) -> dict[str, np.ndarray]:
    """Return four float32 arrays of shape (size, size), sampled at pixel centers.

    Recommended physical repeats are 0.4-0.8 m for hides and cloth, 0.2-0.4 m
    for horn and trim, and 0.4-1.0 m for metal equipment. No emission is added.
    """
    if material_id not in _RECIPES:
        raise ValueError(f"Unknown actor material: {material_id}")
    if not isinstance(size, int) or isinstance(size, bool) or size < 8:
        raise ValueError("size must be an integer of at least 8")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    axis = (np.arange(size, dtype=np.float32) + np.float32(0.5)) / np.float32(size)
    x, y = axis[None, :], axis[:, None]
    return _RECIPES[material_id](x, y, np.random.default_rng(seed))
