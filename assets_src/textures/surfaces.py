"""Periodic scalar material fields for the procedural texture generator.

Every field samples the same unit torus at pixel centers. The first and last
pixels are adjacent samples, not duplicated borders. Height is expressed in
meters; the caller supplies the physical repeat size when computing normals.
Albedo and roughness fields are additive *variations*, with no lighting baked in.
"""

from __future__ import annotations

import numpy as np


MATERIAL_IDS = (
    "floor_tiles", "grout", "pillar_stone", "ruin_wall_moss",
    "altar_basalt", "bronze", "candle_wax", "cloak_fabric", "bone_mask",
    "staff_wood", "imp_skin", "brute_flesh", "shoulder_plates",
)

_TAU = np.float32(2.0 * np.pi)


def _smoothstep(lo: float, hi: float, field: np.ndarray) -> np.ndarray:
    t = np.clip((field - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _noise(
    x: np.ndarray, y: np.ndarray, cells: int, rng: np.random.Generator
) -> np.ndarray:
    """Periodic quintic value noise; warped coordinates may extend past 0..1."""
    grid = rng.uniform(-1.0, 1.0, (cells, cells)).astype(np.float32)
    px, py = x * cells, y * cells
    ix, iy = np.floor(px).astype(np.int32), np.floor(py).astype(np.int32)
    tx, ty = px - ix, py - iy
    tx = tx.astype(np.float32)
    ty = ty.astype(np.float32)
    sx = tx * tx * tx * (tx * (tx * 6.0 - 15.0) + 10.0)
    sy = ty * ty * ty * (ty * (ty * 6.0 - 15.0) + 10.0)
    a = grid[iy % cells, ix % cells]
    b = grid[iy % cells, (ix + 1) % cells]
    c = grid[(iy + 1) % cells, ix % cells]
    d = grid[(iy + 1) % cells, (ix + 1) % cells]
    return (a + (b - a) * sx) * (1.0 - sy) + (c + (d - c) * sx) * sy


def _fbm(
    x: np.ndarray,
    y: np.ndarray,
    rng: np.random.Generator,
    cells: tuple[int, ...] = (3, 6, 12, 24),
) -> np.ndarray:
    """Low frequency fractal noise with a deliberately quiet final octave."""
    result = np.zeros(np.broadcast_shapes(x.shape, y.shape), dtype=np.float32)
    amplitude, weight = 1.0, 0.0
    for count in cells:
        result += amplitude * _noise(x, y, count, rng)
        weight += amplitude
        amplitude *= 0.48
    return result / weight


def _cell_bowls(
    x: np.ndarray, y: np.ndarray, cells: int, rng: np.random.Generator
) -> np.ndarray:
    """Broad hammer marks from jittered cells, periodic in both directions."""
    jitter = rng.uniform(0.2, 0.8, (cells, cells, 2)).astype(np.float32)
    px, py = x * cells, y * cells
    ix, iy = np.floor(px).astype(np.int32), np.floor(py).astype(np.int32)
    nearest = np.full(np.broadcast_shapes(x.shape, y.shape), 9.0, dtype=np.float32)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            offset = jitter[(iy + oy) % cells, (ix + ox) % cells]
            dx = px - (ix + ox + offset[..., 0])
            dy = py - (iy + oy + offset[..., 1])
            np.minimum(nearest, dx * dx + dy * dy, out=nearest)
    # Most of the bowl has faded before a nearest-cell boundary is reached.
    return np.exp(-nearest * 13.0)


def _finish(
    height: np.ndarray,
    albedo: np.ndarray,
    roughness: np.ndarray,
    ao: np.ndarray | float = 1.0,
    **extra: np.ndarray,
) -> dict[str, np.ndarray]:
    shape = height.shape
    output = {
        "height_m": np.maximum(height, 0.0),
        "albedo_variation": np.clip(albedo, -0.15, 0.15),
        "roughness_variation": np.clip(roughness, -0.08, 0.08),
        "ao": np.broadcast_to(np.clip(ao, 0.85, 1.0), shape),
    }
    output.update({name: np.clip(value, 0.0, 1.0) for name, value in extra.items()})
    return {
        name: np.ascontiguousarray(np.broadcast_to(value, shape), dtype=np.float32)
        for name, value in output.items()
    }


def _masonry(x, y, rng, rows=4, columns=4, warp=0.009, stagger=True):
    """Staggered courses with wide, gently damaged mortar edges."""
    wx = x + 0.5 / columns + warp * _noise(x, y, 7, rng)
    wy = y + 0.5 / rows + warp * _noise(x, y, 5, rng)
    py = wy * rows
    row = np.floor(py).astype(np.int32)
    px = wx * columns + (0.5 * (row % 2) if stagger else 0.0)
    column = np.floor(px).astype(np.int32)
    fx, fy = np.mod(px, 1.0), np.mod(py, 1.0)
    distance = np.minimum(np.minimum(fx, 1.0 - fx), np.minimum(fy, 1.0 - fy))
    face = _smoothstep(0.025, 0.105, distance)
    variation = rng.uniform(-1.0, 1.0, (rows, columns)).astype(np.float32)
    # Per-block differences vanish through the joints, keeping the result smooth.
    block = variation[row % rows, column % columns] * face
    return face, block


def _floor_tiles(x, y, rng):
    face, block = _masonry(x, y, rng, stagger=False)
    grain = _fbm(x, y, rng)
    pigment = _fbm(x, y, rng, (3, 7, 13))
    fault = _noise(x, y, 3, rng) + 0.2 * _noise(x, y, 7, rng)
    cracks = (1.0 - _smoothstep(0.018, 0.10, np.abs(fault))) * face
    chips = 4 * face * (1 - face) * _smoothstep(-0.1, 0.5, _noise(x, y, 11, rng))
    height = 0.0007 + face * (0.0075 + 0.0010 * block + 0.0009 * grain) - 0.0022 * cracks - 0.0030 * chips
    return _finish(
        height, 0.11 * block + 0.075 * pigment - 0.035 * cracks,
        0.045 * grain + 0.025 * (1.0 - face) + 0.035 * chips,
        0.89 + 0.11 * face - 0.035 * cracks,
    )


def _grout(x, y, rng):
    aggregate = _fbm(x, y, rng, (5, 11, 23))
    binder = _fbm(x, y, rng, (3, 7))
    return _finish(
        0.00075 + 0.00055 * aggregate,
        0.075 * binder + 0.02 * aggregate,
        0.045 * aggregate, 1.0,
    )


def _pillar_stone(x, y, rng):
    bulk = _fbm(x, y, rng)
    strata = np.sin(_TAU * (x * 6.0 + 0.18 * _noise(x, y, 3, rng)))
    mineral = _fbm(x, y, rng, (4, 9, 17))
    fault = _noise(x, y, 4, rng) + 0.18 * _noise(x, y, 9, rng)
    cracks = 1 - _smoothstep(0.02, 0.12, np.abs(fault))
    return _finish(
        0.0040 + 0.0016 * bulk + 0.0005 * strata - 0.0015 * cracks,
        0.12 * mineral + 0.025 * strata - 0.035 * cracks,
        0.043 * bulk - 0.008 * strata + 0.025 * cracks,
        1 - 0.045 * cracks,
    )


def _ruin_wall_moss(x, y, rng):
    face, block = _masonry(x, y, rng, rows=6, columns=4, warp=0.007)
    stone = _fbm(x, y, rng)
    damp = _fbm(x, y, rng, (3, 7, 14))
    growth = _noise(x, y, 9, rng)
    moss = _smoothstep(0.18, 0.58, damp + 0.14 * (1.0 - face) + 0.10 * growth)
    chips = 4 * face * (1 - face) * _smoothstep(-0.12, 0.45, growth)
    fault = _noise(x, y, 5, rng) + 0.2 * _noise(x, y, 11, rng)
    cracks = (1 - _smoothstep(0.02, 0.12, np.abs(fault))) * face
    height = (
        0.0009 + face * (0.0068 + 0.0006 * block + 0.0008 * stone)
        + moss * (0.0007 + 0.0002 * growth)
        - 0.0030 * chips - 0.0018 * cracks
    )
    return _finish(
        height, 0.11 * block + 0.08 * stone - 0.03 * cracks,
        0.035 * stone + 0.025 * moss + 0.025 * chips,
        0.88 + 0.12 * face - 0.025 * cracks, moss_mask=moss,
    )


def _altar_basalt(x, y, rng):
    bulk = _fbm(x, y, rng, (3, 7, 15))
    fracture_field = _noise(x, y, 4, rng) + 0.18 * _noise(x, y, 9, rng)
    fractures = 1.0 - _smoothstep(0.018, 0.10, np.abs(fracture_field))
    minerals = _fbm(x, y, rng, (4, 11, 21))
    height = 0.0035 + 0.0011 * bulk - 0.0010 * fractures
    return _finish(
        height, 0.065 * minerals, 0.035 * bulk + 0.018 * fractures,
        1.0 - 0.065 * fractures,
    )


def _bronze(x, y, rng):
    hammered = _cell_bowls(x, y, 14, rng)
    patina = _fbm(x, y, rng, (3, 8, 17))
    broad = _noise(x, y, 4, rng)
    return _finish(
        0.0007 + 0.00018 * broad - 0.00027 * hammered,
        0.07 * patina, 0.06 * patina + 0.009 * broad,
        metal_mask=np.ones_like(hammered),
    )


def _candle_wax(x, y, rng):
    flow = _noise(x, y, 3, rng)
    cloud = _fbm(x, y, rng, (3, 7, 13))
    runnels = (0.5 + 0.5 * np.cos(_TAU * (x * 9.0 + 0.17 * flow))) ** 3
    pooled = 0.5 + 0.5 * np.sin(_TAU * (y * 2.0 + 0.12 * flow))
    height = 0.0011 + 0.0003 * cloud + 0.0014 * runnels * (0.35 + 0.65 * pooled)
    return _finish(height, 0.045 * cloud, 0.025 * cloud)


def _cloak_fabric(x, y, rng):
    cloud = _fbm(x, y, rng, (3, 7, 15))
    bend = _noise(x, y, 3, rng)
    # Broad sinusoidal yarns avoid pixel-scale sparkle and noisy normal maps.
    warp = np.cos(_TAU * (x * 32.0 + 0.035 * bend))
    weft = np.cos(_TAU * (y * 32.0 + 0.035 * bend))
    weave = 0.5 * (warp + weft) + 0.16 * warp * weft
    folds = np.sin(_TAU * (x * 3.0 + 0.15 * bend))
    height = 0.0014 + 0.0007 * folds + 0.00013 * weave + 0.00013 * cloud
    return _finish(height, 0.065 * cloud + 0.008 * weave, 0.025 * cloud)


def _bone_mask(x, y, rng):
    mineral = _fbm(x, y, rng, (3, 7, 15))
    wear = _noise(x, y, 5, rng)
    fissure = 1.0 - _smoothstep(0.02, 0.085, np.abs(wear))
    height = 0.0012 + 0.00055 * mineral - 0.00023 * fissure
    return _finish(
        height, 0.075 * mineral + 0.018 * wear,
        0.038 * mineral, 1.0 - 0.035 * fissure,
    )


def _staff_wood(x, y, rng):
    cloud = _fbm(x, y, rng, (3, 7, 15))
    flow = _noise(x, y, 4, rng)
    phase = _TAU * (x * 11.0 + 0.16 * flow + 0.11 * np.sin(_TAU * y))
    grain = np.sin(phase)
    growth = np.sin(phase * 2.0 + 0.22 * cloud)
    # The squared sine distance gives a knot that also wraps continuously.
    knot_x, knot_y = rng.uniform(0.2, 0.8, 2)
    radius = np.sqrt(
        np.sin(np.pi * (x - knot_x)) ** 2
        + 2.4 * np.sin(np.pi * (y - knot_y)) ** 2 + 0.0001
    )
    knot_weight = np.exp(-20.0 * radius * radius)
    knot = np.sin(42.0 * radius) * knot_weight
    height = 0.0013 + 0.00034 * grain + 0.00010 * growth + 0.0003 * cloud + 0.00015 * knot
    return _finish(
        height, 0.065 * grain + 0.022 * growth + 0.04 * cloud + 0.045 * knot,
        0.025 * cloud - 0.014 * grain,
    )


def _imp_skin(x, y, rng):
    dermis = _fbm(x, y, rng, (3, 7, 15))
    hide = _noise(x, y, 13, rng)
    crease_field = _noise(x, y, 5, rng) + 0.15 * hide
    creases = 1.0 - _smoothstep(0.025, 0.13, np.abs(crease_field))
    height = 0.0016 + 0.00065 * dermis + 0.00018 * hide - 0.00025 * creases
    pigment = _fbm(x, y, rng, (4, 9))
    return _finish(
        height, 0.085 * pigment, 0.04 * dermis + 0.014 * hide,
        1.0 - 0.035 * creases,
    )


def _brute_flesh(x, y, rng):
    tissue = _fbm(x, y, rng, (3, 7, 15))
    flow = _noise(x, y, 4, rng)
    fold_phase = np.sin(_TAU * (y * 4.0 + 0.17 * flow + 0.09 * np.sin(_TAU * x)))
    folds = np.exp(-14.0 * fold_phase * fold_phase)
    scar = _smoothstep(0.42, 0.76, _noise(x, y, 6, rng))
    height = 0.0028 + 0.0010 * tissue - 0.0006 * folds + 0.0003 * scar
    pigment = _fbm(x, y, rng, (3, 9, 17))
    return _finish(
        height, 0.08 * pigment + 0.025 * scar,
        0.04 * tissue - 0.014 * scar, 1.0 - 0.055 * folds,
    )


def _shoulder_plates(x, y, rng):
    coating = _fbm(x, y, rng, (3, 7, 15))
    worked = _cell_bowls(x, y, 9, rng)
    stress = _noise(x, y, 5, rng)
    damage = (1.0 - _smoothstep(0.025, 0.11, np.abs(stress))) * _smoothstep(
        -0.1, 0.35, _noise(x, y, 4, rng)
    )
    height = 0.0015 + 0.00045 * coating - 0.00018 * worked - 0.00022 * damage
    return _finish(
        height, 0.085 * coating, 0.045 * coating + 0.012 * damage,
        1.0 - 0.025 * damage, metal_mask=np.zeros_like(height),
    )


_MAKERS = {
    "floor_tiles": _floor_tiles,
    "grout": _grout,
    "pillar_stone": _pillar_stone,
    "ruin_wall_moss": _ruin_wall_moss,
    "altar_basalt": _altar_basalt,
    "bronze": _bronze,
    "candle_wax": _candle_wax,
    "cloak_fabric": _cloak_fabric,
    "bone_mask": _bone_mask,
    "staff_wood": _staff_wood,
    "imp_skin": _imp_skin,
    "brute_flesh": _brute_flesh,
    "shoulder_plates": _shoulder_plates,
}


def make_surface(material_id: str, size: int, seed: int) -> dict[str, np.ndarray]:
    """Return deterministic, square float32 fields without color or base roughness.

    Required keys are height_m, albedo_variation, roughness_variation, and ao.
    Moss is returned only for ruin_wall_moss. Bronze explicitly supplies a metal
    mask of one; shoulder_plates explicitly supplies zero for the coated surface.
    Other materials are dielectric by omission. No map contains lighting.
    """
    if material_id not in _MAKERS:
        raise ValueError(f"Unknown material_id: {material_id!r}")
    if isinstance(size, bool) or not isinstance(size, (int, np.integer)) or size < 16:
        raise ValueError("size must be an integer of at least 16")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    coordinates = (np.arange(size, dtype=np.float32) + 0.5) / np.float32(size)
    x, y = coordinates[None, :], coordinates[:, None]
    return _MAKERS[material_id](x, y, np.random.default_rng(int(seed)))
