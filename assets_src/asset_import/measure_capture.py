#!/usr/bin/env python3
"""Measures figures in an engine capture: size on screen and brightness against the arena floor.

    python -B measure_capture.py --capture <scene.ppm> --floor <floor.ppm>
        --labels soul,imp,witch,witch_pose,imp_hi3d [--png <out.png>] [--json-out <out.json>]

The engine's offscreen capture writes binary PPM (`crates/fnp_app/tests/pilot_showcase.rs`). With a
capture of the floor alone as the reference, every pixel that differs belongs to a figure; the
columns of those pixels group into one band per figure, left to right, which `--labels` names.

Per figure: its height and width in pixels (the size it plays at), its pixel count, and the median
relative luminance of its pixels against the median luminance of the floor beside it, as a contrast
ratio the way WCAG defines it ((lighter + 0.05) / (darker + 0.05)). That is the number behind the
question whether a dark figure disappears on the dark floor.

`--png` writes the capture as a PNG for looking at, `--json-out` the measurements.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# Difference against the floor reference above which a pixel counts as part of a figure (sRGB
# levels): high enough to ignore the renderer's own dither and noise, low enough to keep the dark
# fringes of the witch.
FIGURE_THRESHOLD = 6

# Minimum width of a band, in pixels, so a few stray pixels do not become a "figure".
MIN_BAND_WIDTH = 4


def read_ppm(path: Path) -> np.ndarray:
    """Reads a binary PPM (P6, maxval 255) into an H x W x 3 uint8 array."""
    data = path.read_bytes()
    fields: list[bytes] = []
    offset = 0
    while len(fields) < 4:
        if data[offset : offset + 1] == b"#":
            offset = data.index(b"\n", offset) + 1
            continue
        end = offset
        while data[end : end + 1].isspace():
            end += 1
        offset = end
        while not data[end : end + 1].isspace():
            end += 1
        fields.append(data[offset:end])
        offset = end + 1
    if fields[0] != b"P6" or fields[3] != b"255":
        raise SystemExit(f"{path.name}: not a binary PPM with maxval 255")
    width, height = int(fields[1]), int(fields[2])
    pixels = np.frombuffer(data, dtype=np.uint8, count=width * height * 3, offset=offset)
    return pixels.reshape(height, width, 3)


def relative_luminance(rgb: np.ndarray) -> np.ndarray:
    """WCAG relative luminance of sRGB bytes."""
    c = rgb.astype(np.float64) / 255.0
    linear = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return linear @ np.array([0.2126, 0.7152, 0.0722])


def contrast_ratio(a: float, b: float) -> float:
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def bands(mask: np.ndarray) -> list[tuple[int, int]]:
    """Column ranges (start, end) of the mask, split where no column has a figure pixel."""
    columns = mask.any(axis=0)
    found = []
    start = None
    for index, filled in enumerate(columns):
        if filled and start is None:
            start = index
        elif not filled and start is not None:
            if index - start >= MIN_BAND_WIDTH:
                found.append((start, index))
            start = None
    if start is not None and len(columns) - start >= MIN_BAND_WIDTH:
        found.append((start, len(columns)))
    return found


def measure(capture: np.ndarray, floor: np.ndarray, labels: list[str]) -> dict:
    if capture.shape != floor.shape:
        raise SystemExit(f"capture {capture.shape} and floor {floor.shape} differ in size")
    difference = np.abs(capture.astype(np.int16) - floor.astype(np.int16)).max(axis=2)
    mask = difference > FIGURE_THRESHOLD
    luminance = relative_luminance(capture)
    floor_luminance = relative_luminance(floor)
    found = bands(mask)
    report: dict = {
        "size": [int(capture.shape[1]), int(capture.shape[0])],
        "figure_pixels": int(mask.sum()),
        "bands": len(found),
        "floor_median_luminance": round(float(np.median(floor_luminance)), 5),
        "figures": [],
    }
    if labels and len(labels) != len(found):
        report["label_warning"] = (
            f"{len(found)} bands for {len(labels)} labels: {[list(band) for band in found]}"
        )
    for index, (start, end) in enumerate(found):
        band_mask = mask[:, start:end]
        rows = np.nonzero(band_mask.any(axis=1))[0]
        figure_values = luminance[:, start:end][band_mask]
        floor_values = floor_luminance[:, start:end][~band_mask]
        figure_median = float(np.median(figure_values))
        floor_median = float(np.median(floor_values))
        report["figures"].append(
            {
                "label": labels[index] if index < len(labels) else f"band_{index}",
                "x_range": [int(start), int(end)],
                "width_px": int(end - start),
                "height_px": int(rows[-1] - rows[0] + 1) if rows.size else 0,
                "pixels": int(band_mask.sum()),
                "median_luminance": round(figure_median, 5),
                "p90_luminance": round(float(np.percentile(figure_values, 90)), 5),
                "floor_median_luminance": round(floor_median, 5),
                "contrast_to_floor": round(contrast_ratio(figure_median, floor_median), 3),
                "brightest_tenth_contrast": round(
                    contrast_ratio(float(np.percentile(figure_values, 90)), floor_median), 3
                ),
            }
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--floor", type=Path, help="capture of the floor alone (same camera)")
    parser.add_argument("--labels", default="", help="comma-separated names, left to right")
    parser.add_argument("--png", type=Path, help="write the capture as a PNG")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)

    capture = read_ppm(args.capture)
    if args.png:
        args.png.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(capture).save(args.png)
    if not args.floor:
        print(f"{args.capture.name}: {capture.shape[1]}x{capture.shape[0]}, no floor reference")
        return 0
    labels = [label.strip() for label in args.labels.split(",") if label.strip()]
    report = measure(capture, read_ppm(args.floor), labels)
    report["capture"] = args.capture.name
    report["floor"] = args.floor.name
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['capture']}: {report['size'][0]}x{report['size'][1]}, "
          f"floor luminance {report['floor_median_luminance']:.4f}")
    if "label_warning" in report:
        print(f"  warning: {report['label_warning']}")
    for figure in report["figures"]:
        print(
            f"  {figure['label']:<12} {figure['height_px']:>4} px tall, {figure['width_px']:>4} px "
            f"wide, {figure['pixels']:>6} px; luminance {figure['median_luminance']:.4f} "
            f"(p90 {figure['p90_luminance']:.4f}), contrast to the floor "
            f"{figure['contrast_to_floor']:.2f} : 1 (brightest tenth "
            f"{figure['brightest_tenth_contrast']:.2f} : 1)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
