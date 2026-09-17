#!/usr/bin/env python3
"""Which texture size does a figure use at the game camera? Measured, per triangle, like a GPU.

    python -B texel_footprint.py --figure <figure.glb> [--sizes 256,512,1024,2048,4096]
        [--tilt 60 --fov 42 --distance 14.5] [--json-out <file>]

The figure stands at the camera target, as the game camera of the prototype sees it (tilt above
the floor, vertical field of view, distance; `fnp_game` arena `camera_template`), turned in 45
degree steps. For every front-facing triangle the screen-to-texture Jacobian is solved from its
three corners and the mip level follows the engine's sampler: trilinear, no anisotropic
filtering, so the level is `log2` of the longer of the two screen-axis footprints in texels.

For each candidate size the report gives, weighted by screen area, the share of the figure's
pixels that sample level 0 (would lose detail with half the size) and the median level, at
1920x1080 and at 3840x2160. Occlusion is ignored: hidden front faces count as well, which leans
towards more texture detail, not less.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

from verify_normal_map import load_mesh

RESOLUTIONS = {"1080p": (1920, 1080), "2160p": (3840, 2160)}


def camera_basis(tilt_deg: float, distance: float) -> tuple[np.ndarray, ...]:
    """Eye, right, up and forward for a camera above +Z looking down at the origin (glTF, Y up)."""
    tilt = math.radians(tilt_deg)
    eye = np.array([0.0, math.sin(tilt) * distance, math.cos(tilt) * distance])
    forward = -eye / np.linalg.norm(eye)
    right = np.cross(forward, [0.0, 1.0, 0.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    return eye, right, up, forward


def project(points: np.ndarray, camera, fov_deg: float, width: int, height: int) -> np.ndarray:
    eye, right, up, forward = camera
    d = points - eye
    z = d @ forward
    scale = (height / 2.0) / math.tan(math.radians(fov_deg) / 2.0)
    x = (d @ right) / z * scale + width / 2.0
    y = -(d @ up) / z * scale + height / 2.0
    return np.stack([x, y], axis=-1)


def footprint(mesh: dict, yaw_deg: float, camera, fov: float, width: int, height: int):
    """(screen area in pixels, texels per pixel along the longer axis at size 1) per triangle."""
    yaw = math.radians(yaw_deg)
    c, s = math.cos(yaw), math.sin(yaw)
    rotation = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    positions = mesh["positions"] @ rotation.T
    screen = project(positions, camera, fov, width, height)[mesh["indices"]]
    uv = mesh["uvs"][mesh["indices"]]
    e1, e2 = screen[:, 1] - screen[:, 0], screen[:, 2] - screen[:, 0]
    # Pixel y runs down, so front faces have a negative signed area.
    signed = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]
    front = signed < -1e-9
    e1, e2, signed = e1[front], e2[front], signed[front]
    t1, t2 = uv[front, 1] - uv[front, 0], uv[front, 2] - uv[front, 0]
    # Solve [e1 e2] * J_inv = [t1 t2] for dUV/dx and dUV/dy.
    inv = 1.0 / signed
    du_dx = (t1[:, 0] * e2[:, 1] - t2[:, 0] * e1[:, 1]) * inv
    du_dy = (t2[:, 0] * e1[:, 0] - t1[:, 0] * e2[:, 0]) * inv
    dv_dx = (t1[:, 1] * e2[:, 1] - t2[:, 1] * e1[:, 1]) * inv
    dv_dy = (t2[:, 1] * e1[:, 0] - t1[:, 1] * e2[:, 0]) * inv
    rho = np.maximum(np.hypot(du_dx, dv_dx), np.hypot(du_dy, dv_dy))
    return np.abs(signed) * 0.5, rho


def weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    order = np.argsort(values)
    cumulative = np.cumsum(weights[order])
    return float(values[order][np.searchsorted(cumulative, cumulative[-1] / 2.0)])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--figure", type=Path, required=True)
    parser.add_argument("--sizes", default="256,512,1024,2048,4096")
    parser.add_argument("--tilt", type=float, default=60.0)
    parser.add_argument("--fov", type=float, default=42.0)
    parser.add_argument("--distance", type=float, default=14.5)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)

    mesh = load_mesh(args.figure)
    if "uvs" not in mesh:
        raise SystemExit(f"{args.figure.name}: no TEXCOORD_0")
    sizes = [int(s) for s in args.sizes.split(",")]
    camera = camera_basis(args.tilt, args.distance)
    report = {
        "figure": args.figure.name,
        "camera": {"tilt_deg": args.tilt, "fov_y_deg": args.fov, "distance_m": args.distance},
        "yaw_steps_deg": 45,
        "resolutions": {},
    }
    for label, (width, height) in RESOLUTIONS.items():
        areas, rhos = [], []
        for yaw in range(0, 360, 45):
            area, rho = footprint(mesh, yaw, camera, args.fov, width, height)
            areas.append(area)
            rhos.append(rho)
        area, rho = np.concatenate(areas), np.concatenate(rhos)
        heights = mesh["positions"][:, 1]
        axis = np.array([[0.0, heights.max(), 0.0], [0.0, heights.min(), 0.0]])
        top, bottom = project(axis, camera, args.fov, width, height)
        entry = {"figure_height_px": round(float(bottom[1] - top[1]), 1), "sizes": {}}
        for size in sizes:
            level = np.log2(np.maximum(rho * size, 1e-12))
            entry["sizes"][str(size)] = {
                "share_sampling_level_0": round(float(area[level < 1.0].sum() / area.sum()), 4),
                "median_level": round(weighted_median(level, area), 2),
            }
        report["resolutions"][label] = entry

    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['figure']}: tilt {args.tilt} deg, fov {args.fov} deg, "
          f"distance {args.distance} m")
    for label, entry in report["resolutions"].items():
        print(f"  {label}: figure {entry['figure_height_px']} px tall")
        for size, values in entry["sizes"].items():
            share = values["share_sampling_level_0"] * 100
            print(f"    {size:>5}: level 0 on {share:5.1f} % of its pixels, "
                  f"median level {values['median_level']:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
