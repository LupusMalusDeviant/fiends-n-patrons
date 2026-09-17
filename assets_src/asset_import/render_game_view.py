#!/usr/bin/env python3
"""Draws a prepared figure at the game camera the way the engine samples it, without a GPU.

    python -B render_game_view.py --figure <figure.glb> --out <image.png>
        [--high <hi3d.glb> --prepare-report <name>_prepare.json]
        [--base-color-variants 512=<png>,2048=<png>] [--resolution 1080|2160] [--zoom 4]

A preview and a measurement, not a renderer: numpy and Pillow, perspective camera of the prototype
arena (tilt 60 degrees, vertical field of view 42 degrees, 14.5 m), figure at the camera target
facing the camera.

- **Geometry** is rasterised at twice the resolution and averaged down, four samples per pixel
  like the engine's MSAA 4x.
- **Textures** are sampled once per final pixel, trilinearly from a mip chain built like the
  engine's (box filter, sRGB averaged in linear light), at the mip level of the final pixel's
  footprint (longer axis, no anisotropic filtering).
- **Shading:** base colour times a Lambert key light plus a constant fill, with the normal map;
  no specular, no shadows. The floor is a flat dark grey.

With `--high`, the silhouette of the high-resolution source is drawn at the same four samples per
pixel and compared with the figure's: the report gives the pixel coverage that differs, as a
share of the source's coverage. Each `--base-color-variants` entry replaces the base colour and
adds a panel, so texture sizes can be compared side by side at game size.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from texel_footprint import camera_basis, project
from verify_normal_map import load_mesh, normalise, smooth_normals

KEY_LIGHT = normalise(np.array([-0.35, 0.8, 0.5]))
FILL = 0.18
FLOOR_SRGB = np.array([28, 27, 26], dtype=np.float64)
RESOLUTIONS = {1080: (1920, 1080), 2160: (3840, 2160)}


def srgb_to_linear(c: np.ndarray) -> np.ndarray:
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1.0 / 2.4) - 0.055) * 255.0


def mip_chain(image: np.ndarray) -> list[np.ndarray]:
    """Linear-valued levels, halving with a 2x2 box filter down to 1x1 (square power of two)."""
    levels = [image]
    while levels[-1].shape[0] > 1:
        a = levels[-1]
        levels.append((a[0::2, 0::2] + a[1::2, 0::2] + a[0::2, 1::2] + a[1::2, 1::2]) / 4.0)
    return levels


def bilinear(level: np.ndarray, uv: np.ndarray) -> np.ndarray:
    h, w = level.shape[:2]
    x = (uv[:, 0] % 1.0) * w - 0.5
    y = (uv[:, 1] % 1.0) * h - 0.5  # glTF: v = 0 is the top row
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    x0, x1, y0, y1 = x0 % w, (x0 + 1) % w, y0 % h, (y0 + 1) % h
    top = level[y0, x0] * (1 - fx) + level[y0, x1] * fx
    return top * (1 - fy) + (level[y1, x0] * (1 - fx) + level[y1, x1] * fx) * fy


def trilinear(chain: list[np.ndarray], uv: np.ndarray, lod: np.ndarray) -> np.ndarray:
    lod = np.clip(lod, 0.0, len(chain) - 1.0)
    base = np.floor(lod).astype(np.int64)
    frac = (lod - base)[:, None]
    out = np.zeros((len(uv), chain[0].shape[2]))
    for level in np.unique(base):
        sel = base == level
        upper = min(level + 1, len(chain) - 1)
        a = bilinear(chain[level], uv[sel])
        b = bilinear(chain[upper], uv[sel])
        out[sel] = a * (1 - frac[sel]) + b * frac[sel]
    return out


def rasterise(screen: np.ndarray, depth: np.ndarray, indices: np.ndarray, width: int, height: int):
    """Z-buffered triangle ids and barycentrics at pixel centres; front faces only."""
    zbuf = np.full((height, width), np.inf)
    tri_id = np.full((height, width), -1, dtype=np.int64)
    bary = np.zeros((height, width, 3))
    for t, (i, j, k) in enumerate(indices):
        (xa, ya), (xb, yb), (xc, yc) = screen[i], screen[j], screen[k]
        denom = (yb - yc) * (xa - xc) + (xc - xb) * (ya - yc)
        if denom > -1e-12:
            continue
        x0 = max(int(math.floor(min(xa, xb, xc))), 0)
        x1 = min(int(math.ceil(max(xa, xb, xc))), width - 1)
        y0 = max(int(math.floor(min(ya, yb, yc))), 0)
        y1 = min(int(math.ceil(max(ya, yb, yc))), height - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        wa = ((yb - yc) * (xs - xc) + (xc - xb) * (ys - yc)) / denom
        wb = ((yc - ya) * (xs - xc) + (xa - xc) * (ys - yc)) / denom
        wc = 1.0 - wa - wb
        inside = (wa >= 0) & (wb >= 0) & (wc >= 0)
        if not inside.any():
            continue
        z = wa * depth[i] + wb * depth[j] + wc * depth[k]
        region = zbuf[y0 : y1 + 1, x0 : x1 + 1]
        closer = inside & (z < region)
        region[closer] = z[closer]
        tri_id[y0 : y1 + 1, x0 : x1 + 1][closer] = t
        bary[y0 : y1 + 1, x0 : x1 + 1][closer] = np.stack([wa, wb, wc], axis=-1)[closer]
    return tri_id, bary


def texel_rho(screen: np.ndarray, uv: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """Per triangle: UV units per final pixel along the longer screen axis."""
    s, t = screen[indices], uv[indices]
    e1, e2 = s[:, 1] - s[:, 0], s[:, 2] - s[:, 0]
    t1, t2 = t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]
    det = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]
    inv = np.where(np.abs(det) < 1e-12, 0.0, 1.0 / np.where(np.abs(det) < 1e-12, 1.0, det))
    du_dx = (t1[:, 0] * e2[:, 1] - t2[:, 0] * e1[:, 1]) * inv
    du_dy = (t2[:, 0] * e1[:, 0] - t1[:, 0] * e2[:, 0]) * inv
    dv_dx = (t1[:, 1] * e2[:, 1] - t2[:, 1] * e1[:, 1]) * inv
    dv_dy = (t2[:, 1] * e1[:, 0] - t1[:, 1] * e2[:, 0]) * inv
    return np.maximum(np.hypot(du_dx, dv_dx), np.hypot(du_dy, dv_dy))


def figure_crop(screen: np.ndarray, width: int, height: int, margin: float = 0.25):
    x0, y0 = screen.min(axis=0)
    x1, y1 = screen.max(axis=0)
    side = max(x1 - x0, y1 - y0) * (1 + 2 * margin)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    left, top = int(math.floor(cx - side / 2)), int(math.floor(cy - side / 2))
    size = int(math.ceil(side))
    return max(left, 0), max(top, 0), min(size, width), min(size, height)


def draw(mesh: dict, chain_base: list, chain_normal: list | None, camera, fov, width, height, crop):
    """Returns the crop as linear RGB (size x size x 3) and its coverage (size x size)."""
    left, top, size, _ = crop
    ss = 2
    screen_final = project(mesh["positions"], camera, fov, width, height)
    screen = (screen_final - [left, top]) * ss
    eye, _r, _u, forward = camera
    depth = (mesh["positions"] - eye) @ forward
    tri_id, bary = rasterise(screen, depth, mesh["indices"], size * ss, size * ss)
    covered = tri_id >= 0
    corners = mesh["indices"][tri_id[covered]]
    w = bary[covered]

    def interp(values):
        return np.einsum("pc,pcd->pd", w, values[corners])

    uv = interp(mesh["uvs"])
    rho = texel_rho(screen_final, mesh["uvs"], mesh["indices"])[tri_id[covered]]
    base = trilinear(chain_base, uv, np.log2(np.maximum(rho * chain_base[0].shape[0], 1e-12)))
    n = normalise(interp(mesh["normals"]))
    if chain_normal is not None:
        tangent = interp(mesh["tangents"])
        t = normalise(tangent[:, :3] - n * (tangent[:, :3] * n).sum(1, keepdims=True))
        b = np.cross(n, t) * np.where(tangent[:, 3] < 0, -1.0, 1.0)[:, None]
        lod = np.log2(np.maximum(rho * chain_normal[0].shape[0], 1e-12))
        ts = trilinear(chain_normal, uv, lod) * 2.0 - 1.0
        n = normalise(t * ts[:, 0:1] + b * ts[:, 1:2] + n * ts[:, 2:3])
    light = np.clip(n @ KEY_LIGHT, 0.0, 1.0)[:, None] * 0.9 + FILL
    image = np.tile(srgb_to_linear(FLOOR_SRGB), (size * ss, size * ss, 1))
    image[covered] = base * light
    image = image.reshape(size, ss, size, ss, 3).mean(axis=(1, 3))
    coverage = covered.reshape(size, ss, size, ss).mean(axis=(1, 3))
    return image, coverage


def high_coverage(positions, indices, camera, fov, width, height, crop):
    left, top, size, _ = crop
    ss = 2
    centroids = positions[indices].mean(axis=1)
    screen = (project(centroids, camera, fov, width, height) - [left, top]) * ss
    ix, iy = np.floor(screen[:, 0]).astype(np.int64), np.floor(screen[:, 1]).astype(np.int64)
    ok = (ix >= 0) & (ix < size * ss) & (iy >= 0) & (iy < size * ss)
    grid = np.zeros((size * ss, size * ss), dtype=bool)
    grid[iy[ok], ix[ok]] = True
    return grid.reshape(size, ss, size, ss).mean(axis=(1, 3))


def load_png_linear(path_or_bytes, srgb: bool) -> np.ndarray:
    source = io.BytesIO(path_or_bytes) if isinstance(path_or_bytes, bytes) else path_or_bytes
    image = Image.open(source)
    rgb = np.asarray(image.convert("RGB"), dtype=np.float64)
    return srgb_to_linear(rgb) if srgb else rgb / 255.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--figure", type=Path, required=True)
    parser.add_argument("--base-color", type=Path, required=True, help="base colour PNG")
    parser.add_argument("--normal-map", type=Path, required=True, help="normal map PNG")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--high", type=Path)
    parser.add_argument("--prepare-report", type=Path)
    parser.add_argument("--base-color-variants", default="", help="label=png,label=png")
    parser.add_argument("--resolution", type=int, default=1080, choices=sorted(RESOLUTIONS))
    parser.add_argument("--zoom", type=int, default=4)
    parser.add_argument("--tilt", type=float, default=60.0)
    parser.add_argument("--fov", type=float, default=42.0)
    parser.add_argument("--distance", type=float, default=14.5)
    args = parser.parse_args(argv)

    width, height = RESOLUTIONS[args.resolution]
    camera = camera_basis(args.tilt, args.distance)
    mesh = load_mesh(args.figure)
    crop = figure_crop(project(mesh["positions"], camera, args.fov, width, height), width, height)
    normal_chain = mip_chain(load_png_linear(args.normal_map, srgb=False))

    variants = [("figure", args.base_color)]
    for item in [v for v in args.base_color_variants.split(",") if v.strip()]:
        label, path = item.split("=", 1)
        variants.append((label.strip(), Path(path.strip())))

    report = {
        "figure": args.figure.name,
        "resolution": f"{width}x{height}",
        "crop_px": crop[2],
        "panels": [],
    }
    panels = []
    for label, path in variants:
        base_chain = mip_chain(load_png_linear(path, srgb=True))
        image, coverage = draw(mesh, base_chain, normal_chain, camera, args.fov, width, height, crop)
        panels.append(linear_to_srgb(image))
        entry = {"label": label, "base_color": path.name}
        if len(panels) > 1:
            delta = np.abs(np.round(panels[-1]) - np.round(panels[0]))[coverage > 0]
            entry["srgb_difference_to_first_panel"] = {
                "mean": round(float(delta.mean()), 3),
                "p99": round(float(np.percentile(delta, 99)), 1),
                "max": round(float(delta.max()), 1),
            }
        report["panels"].append(entry)
    if args.high:
        high = load_mesh(args.high)
        grounding = json.loads(args.prepare_report.read_text(encoding="utf-8"))["grounding"]
        placed = high["positions"] * grounding["scale"] + np.array(grounding["translation_gltf"])
        _normals, tris, unique = smooth_normals(placed, high["indices"])
        high_cov = high_coverage(unique, tris, camera, args.fov, width, height, crop)
        diff = np.abs(high_cov - coverage)
        report["silhouette"] = {
            "source_coverage_px": round(float(high_cov.sum()), 1),
            "figure_coverage_px": round(float(coverage.sum()), 1),
            "differing_coverage_share": round(float(diff.sum() / max(high_cov.sum(), 1e-9)), 4),
        }
        overlay = np.zeros(high_cov.shape + (3,))
        overlay[..., 0] = np.clip(high_cov - coverage, 0, 1) * 255  # only in the source: red
        overlay[..., 2] = np.clip(coverage - high_cov, 0, 1) * 255  # only in the figure: blue
        overlay[..., 1] = np.minimum(high_cov, coverage) * 160      # both: green
        panels.append(overlay)
        report["panels"].append({"label": "silhouette: red source only, blue figure only"})
    strip = np.concatenate([np.round(np.clip(p, 0, 255)).astype(np.uint8) for p in panels], axis=1)
    strip = strip.repeat(args.zoom, axis=0).repeat(args.zoom, axis=1)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(strip).save(args.out)
    args.out.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
