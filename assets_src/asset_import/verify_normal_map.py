#!/usr/bin/env python3
"""Checks a prepared figure's normal map against its high-resolution source, the way the engine
shades it. No Blender, no GPU: numpy and Pillow.

    python -B verify_normal_map.py --figure <figure.glb> --high <hi3d.glb> --out-dir <dir>
        [--resolution 768] [--views front,back]

Both meshes are drawn orthographically into a z-buffer from the front (+Z) and the back (-Z):

- **high:** the source, welded by position, smooth area-weighted vertex normals, drawn as one
  point per triangle (its triangles are far smaller than a pixel);
- **low:** the prepared figure with its exported vertex normals, rasterised per triangle;
- **low + normal map:** the same pixels, shaded like `mesh.wgsl`: tangent-space normal from the
  PNG (OpenGL, +Y up), `bitangent = cross(normal, tangent.xyz) * tangent.w`.

For every pixel both meshes cover, the angle to the high normal is measured with and without the
normal map, and once more with the green channel inverted as a control: a correct map lowers the
error, an inverted one raises it. The source is placed with the same grounding as
`blender_prepare.py` (uniform scale to the figure's height, lowest point on the floor, bounding box
centred), so both meshes share one frame.

Writes `<figure>_normals_<view>.png` (high | low | low + map, as normal colours and as simple
Lambert shading) and `<figure>_normal_check.json`.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from glb_facts import load_glb

LIGHT = np.array([-0.4, 0.6, 0.7]) / np.linalg.norm([-0.4, 0.6, 0.7])


def accessor_array(glb, index: int) -> np.ndarray:
    doc = glb.json_doc
    accessor = doc["accessors"][index]
    view = doc["bufferViews"][accessor["bufferView"]]
    width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[accessor["type"]]
    dtypes = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}
    dtype = dtypes[accessor["componentType"]]
    item = np.dtype(dtype).itemsize * width
    stride = int(view.get("byteStride", 0)) or item
    start = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
    count = int(accessor["count"])
    length = stride * (count - 1) + item
    raw = np.frombuffer(glb.bin_chunk, dtype=np.uint8, count=length, offset=start)
    rows = np.lib.stride_tricks.as_strided(raw, shape=(count, item), strides=(stride, 1))
    return np.frombuffer(rows.copy().tobytes(), dtype=dtype).reshape(count, width)


def load_mesh(path: Path) -> dict:
    glb = load_glb(path)
    doc = glb.json_doc
    meshes = doc["meshes"]
    if len(meshes) != 1 or len(meshes[0]["primitives"]) != 1:
        raise SystemExit(f"{path.name}: expected one mesh with one primitive")
    primitive = meshes[0]["primitives"][0]
    attributes = primitive["attributes"]
    mesh = {
        "positions": accessor_array(glb, attributes["POSITION"]).astype(np.float64),
        "indices": accessor_array(glb, primitive["indices"])[:, 0].astype(np.int64).reshape(-1, 3),
    }
    for key, name in (("normals", "NORMAL"), ("tangents", "TANGENT"), ("uvs", "TEXCOORD_0")):
        if name in attributes:
            mesh[key] = accessor_array(glb, attributes[name]).astype(np.float64)
    material = doc["materials"][primitive["material"]] if "material" in primitive else {}
    if "normalTexture" in material:
        image = doc["images"][doc["textures"][material["normalTexture"]["index"]]["source"]]
        view = doc["bufferViews"][image["bufferView"]]
        start = int(view.get("byteOffset", 0))
        data = glb.bin_chunk[start : start + int(view["byteLength"])]
        rgb = Image.open(io.BytesIO(data)).convert("RGB")
        mesh["normal_map"] = np.asarray(rgb, dtype=np.float64)
    return mesh


def normalise(v: np.ndarray) -> np.ndarray:
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


def ground(positions: np.ndarray, height: float) -> np.ndarray:
    low, high = positions.min(axis=0), positions.max(axis=0)
    scale = height / (high[1] - low[1])
    shift = np.array([-(low[0] + high[0]) / 2.0, -low[1], -(low[2] + high[2]) / 2.0]) * scale
    return positions * scale + shift


def smooth_normals(positions: np.ndarray, indices: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Welds by exact position and returns (per-vertex normals, remapped indices)."""
    unique, inverse = np.unique(positions, axis=0, return_inverse=True)
    tri = inverse.reshape(-1)[indices]
    a, b, c = unique[tri[:, 0]], unique[tri[:, 1]], unique[tri[:, 2]]
    face = np.cross(b - a, c - a)  # area-weighted
    normals = np.zeros_like(unique)
    for corner in range(3):
        np.add.at(normals, tri[:, corner], face)
    return normalise(normals), tri, unique


def view_axes(view: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(right, up, towards camera) for an orthographic view of a Y-up, +Z-facing figure."""
    if view == "front":
        return np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])
    if view == "back":
        return np.array([-1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, -1.0])
    raise SystemExit(f"unknown view {view!r}")


def to_pixels(points: np.ndarray, view: str, res: int, frame_m: float, centre_y: float):
    right, up, towards = view_axes(view)
    px = (points @ right) / frame_m * res + res / 2.0
    py = (centre_y - points @ up) / frame_m * res + res / 2.0
    return px, py, points @ towards


def draw_high(positions, indices, normals, view, res, frame_m, centre_y):
    corners = positions[indices]
    centroids = corners.mean(axis=1)
    n = normalise(normals[indices].mean(axis=1))
    face = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    facing = face @ view_axes(view)[2] > 0.0  # the source is a closed shell: cull back faces
    centroids, n = centroids[facing], n[facing]
    px, py, depth = to_pixels(centroids, view, res, frame_m, centre_y)
    ix, iy = np.floor(px).astype(np.int64), np.floor(py).astype(np.int64)
    inside = (ix >= 0) & (ix < res) & (iy >= 0) & (iy < res)
    ix, iy, depth, n = ix[inside], iy[inside], depth[inside], n[inside]
    order = np.lexsort((depth, iy * res + ix))  # nearest last within each pixel
    key = (iy * res + ix)[order]
    last = np.r_[key[1:] != key[:-1], True]
    image = np.zeros((res * res, 3))
    covered = np.zeros(res * res, dtype=bool)
    image[key[last]] = n[order][last]
    covered[key[last]] = True
    return image.reshape(res, res, 3), covered.reshape(res, res)


def draw_low(mesh, view, res, frame_m, centre_y):
    """Rasterises the low mesh; returns per-pixel interpolated normal, tangent (xyzw), UV, mask."""
    positions, indices = mesh["positions"], mesh["indices"]
    px, py, depth = to_pixels(positions, view, res, frame_m, centre_y)
    zbuf = np.full((res, res), -np.inf)
    tri_id = np.full((res, res), -1, dtype=np.int64)
    bary = np.zeros((res, res, 3))
    for t, (i, j, k) in enumerate(indices):
        xa, xb, xc = px[i], px[j], px[k]
        ya, yb, yc = py[i], py[j], py[k]
        x0, x1 = max(int(np.floor(min(xa, xb, xc))), 0), min(int(np.ceil(max(xa, xb, xc))), res - 1)
        y0, y1 = max(int(np.floor(min(ya, yb, yc))), 0), min(int(np.ceil(max(ya, yb, yc))), res - 1)
        if x1 < x0 or y1 < y0:
            continue
        denom = (yb - yc) * (xa - xc) + (xc - xb) * (ya - yc)
        if denom > -1e-12:  # back face (pixel y runs down) or degenerate
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
        closer = inside & (z > region)
        region[closer] = z[closer]
        tri_id[y0 : y1 + 1, x0 : x1 + 1][closer] = t
        bary[y0 : y1 + 1, x0 : x1 + 1][closer] = np.stack([wa, wb, wc], axis=-1)[closer]
    covered = tri_id >= 0
    corners = indices[tri_id[covered]]
    w = bary[covered]

    def interpolate(values):
        return np.einsum("pc,pcd->pd", w, values[corners])

    normals, tangents = interpolate(mesh["normals"]), interpolate(mesh["tangents"])
    return covered, normals, tangents, interpolate(mesh["uvs"])


def sample_bilinear(image: np.ndarray, uv: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    x = (uv[:, 0] % 1.0) * w - 0.5
    y = (uv[:, 1] % 1.0) * h - 0.5  # glTF: v = 0 is the top row
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    x0c, x1c = np.clip(x0, 0, w - 1), np.clip(x0 + 1, 0, w - 1)
    y0c, y1c = np.clip(y0, 0, h - 1), np.clip(y0 + 1, 0, h - 1)
    top = image[y0c, x0c] * (1 - fx) + image[y0c, x1c] * fx
    bottom = image[y1c, x0c] * (1 - fx) + image[y1c, x1c] * fx
    return top * (1 - fy) + bottom * fy


def shade_with_map(normal, tangent, uv, normal_map, flip_green=False):
    n = normalise(normal)
    t = normalise(tangent[:, :3] - n * (tangent[:, :3] * n).sum(1, keepdims=True))
    sign = np.where(tangent[:, 3] < 0, -1.0, 1.0)[:, None]
    b = np.cross(n, t) * sign
    ts = sample_bilinear(normal_map, uv) / 255.0 * 2.0 - 1.0
    if flip_green:
        ts[:, 1] = -ts[:, 1]
    return normalise(t * ts[:, 0:1] + b * ts[:, 1:2] + n * ts[:, 2:3])


def angle_stats(a: np.ndarray, b: np.ndarray) -> dict:
    if len(a) == 0:
        return None
    angles = np.degrees(np.arccos(np.clip((a * b).sum(1), -1.0, 1.0)))
    return {f"p{q}": round(float(np.percentile(angles, q)), 2) for q in (50, 75, 90)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--figure", type=Path, required=True)
    parser.add_argument("--high", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--resolution", type=int, default=768)
    parser.add_argument("--views", default="front,back")
    parser.add_argument("--frame-m", type=float, help="height of the square view (default: figure)")
    parser.add_argument("--centre-y", type=float, help="view centre height in metres")
    parser.add_argument("--tag", default="", help="suffix for the output files")
    parser.add_argument("--prepare-report", type=Path,
                        help="<name>_prepare.json: place the source with its exact grounding")
    args = parser.parse_args(argv)

    low = load_mesh(args.figure)
    for key in ("normals", "tangents", "uvs", "normal_map"):
        if key not in low:
            raise SystemExit(f"{args.figure.name}: missing {key}")
    lo, hi = low["positions"].min(0), low["positions"].max(0)
    height = float(hi[1] - lo[1])
    high = load_mesh(args.high)
    if args.prepare_report:
        grounding = json.loads(args.prepare_report.read_text(encoding="utf-8"))["grounding"]
        placed = high["positions"] * grounding["scale"] + np.array(grounding["translation_gltf"])
    else:
        placed = ground(high["positions"], height)
    high_normals, high_tris, high_positions = smooth_normals(placed, high["indices"])

    frame_m = args.frame_m or height * 1.06
    centre_y = height / 2.0 if args.centre_y is None else args.centre_y
    res = args.resolution
    stem = args.figure.stem + args.tag
    args.out_dir.mkdir(parents=True, exist_ok=True)
    report = {"figure": args.figure.name, "high": args.high.name, "resolution": res, "views": {}}
    for view in [v.strip() for v in args.views.split(",") if v.strip()]:
        high_image, high_mask = draw_high(
            high_positions, high_tris, high_normals, view, res, frame_m, centre_y
        )
        low_mask, normal, tangent, uv = draw_low(low, view, res, frame_m, centre_y)
        mapped = shade_with_map(normal, tangent, uv, low["normal_map"])
        flipped = shade_with_map(normal, tangent, uv, low["normal_map"], flip_green=True)
        low_image = np.zeros((res, res, 3))
        low_image[low_mask] = normalise(normal)
        mapped_image = np.zeros((res, res, 3))
        mapped_image[low_mask] = mapped
        flipped_image = np.zeros((res, res, 3))
        flipped_image[low_mask] = flipped
        both = high_mask & low_mask
        reference = high_image[both]
        blocks = {}
        for block in (4, 16):
            pooled = []
            for image in (high_image, low_image, mapped_image, flipped_image):
                cells = (image * both[..., None]).reshape(res // block, block, res // block, block, 3)
                summed = cells.sum((1, 3))
                pooled.append(normalise(summed))
            full = both.reshape(res // block, block, res // block, block).all((1, 3))
            blocks[f"block{block}px"] = {
                "low": angle_stats(pooled[1][full], pooled[0][full]),
                "low_with_map": angle_stats(pooled[2][full], pooled[0][full]),
                "low_with_green_inverted": angle_stats(pooled[3][full], pooled[0][full]),
            }
        report["views"][view] = {
            "pooled": blocks,
            "pixels_compared": int(both.sum()),
            "silhouette_pixels_only_high": int((high_mask & ~low_mask).sum()),
            "silhouette_pixels_only_low": int((low_mask & ~high_mask).sum()),
            "degrees_low_vs_high": angle_stats(low_image[both], reference),
            "degrees_low_with_map_vs_high": angle_stats(mapped_image[both], reference),
            "degrees_low_with_green_inverted_vs_high": angle_stats(flipped_image[both], reference),
        }
        panels = []
        pairs = ((high_image, high_mask), (low_image, low_mask), (mapped_image, low_mask))
        for image, mask in pairs:
            colour = np.where(mask[..., None], image * 0.5 + 0.5, 0.12)
            lambert = np.where(mask, np.clip(image @ LIGHT, 0, 1) * 0.85 + 0.1, 0.12)
            panels.append((colour, np.repeat(lambert[..., None], 3, axis=2)))
        rows = [np.concatenate([p[k] for p in panels], axis=1) for k in (0, 1)]
        strip = np.round(np.clip(np.concatenate(rows, axis=0), 0, 1) * 255).astype(np.uint8)
        Image.fromarray(strip).save(args.out_dir / f"{stem}_normals_{view}.png")
    report_path = args.out_dir / f"{stem}_normal_check.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
