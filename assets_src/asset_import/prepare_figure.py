#!/usr/bin/env python3
"""Stage 2 of the asset import: prepares a rigged figure for the game and checks the result.

    python -B prepare_figure.py --rigged <rigged.glb> --high <hi3d.glb> --out-dir <dir>
        --name witch --role player --height 1.8 --triangles 18000 --texture-size 1024
        [--swap-sides] [--blender <blender executable>] [--texture-variants 512,2048]

1. **Textures** (this process, numpy and Pillow): base colour and metallic-roughness of the rigged
   file's material are decoded and reduced to `--texture-size` with the figure pack's exact box
   filter (`../figure_pack/textures.py`: base colour in linear light like the engine's mip chain,
   integer arithmetic). Written as PNG.
2. **Geometry, normal map and export** (`blender_prepare.py` in a headless Blender process).
3. **Gate:** the stage-1 check (`check_asset.py`) runs on the exported figure with `--role`; a
   failing check fails this script.

Outputs in `--out-dir`: `<name>.glb`, the three texture PNGs, `<name>_prepare.json`,
`<name>_check.json`, `<name>_blender.log` and `manifest.json` with the SHA-256 of every
deterministic output (everything except the log). Two runs on the same inputs must produce the
same manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "figures"))

import check_asset  # noqa: E402
import palette  # noqa: E402
import textures  # noqa: E402
from glb_facts import GlbError, load_glb, measure_glb  # noqa: E402

Image.MAX_IMAGE_PIXELS = None  # the sources are trusted 8K atlases, 67M pixels each


class PrepareError(RuntimeError):
    """The inputs cannot be prepared (wrong structure, sizes, or a failing stage)."""


# ------------------------------------------------------------------------------ textures


def material_images(glb_path: Path) -> dict[str, bytes]:
    """Encoded bytes of the base colour and metallic-roughness images of the single material."""
    glb = load_glb(glb_path)
    doc = glb.json_doc
    materials = doc.get("materials", [])
    if len(materials) != 1:
        raise PrepareError(f"{glb_path.name}: expected one material, found {len(materials)}")
    pbr = materials[0].get("pbrMetallicRoughness", {})
    out = {}
    slots = (("base_color", "baseColorTexture"), ("metallic_roughness", "metallicRoughnessTexture"))
    for slot, key in slots:
        if key not in pbr:
            raise PrepareError(f"{glb_path.name}: material has no {key}")
        image = doc["images"][doc["textures"][pbr[key]["index"]]["source"]]
        view = doc["bufferViews"][image["bufferView"]]
        start = int(view.get("byteOffset", 0))
        out[slot] = glb.bin_chunk[start : start + int(view["byteLength"])]
    return out


def box_reduce(pixels: np.ndarray, size: int, *, srgb: bool) -> np.ndarray:
    """Reduces a square power-of-two HxWx3 image to `size` with the figure pack's exact box filter
    (`../figure_pack/textures.py`: sRGB averaged in linear light, integer arithmetic)."""
    height, width, _channels = pixels.shape
    if height != width or width % size or (width & (width - 1)) or (size & (size - 1)):
        raise PrepareError(f"cannot box-reduce {width}x{height} to {size}: not square powers of two")
    return textures.box_reduce(pixels, width // size, srgb=srgb)


def prepare_textures(rigged: Path, out_dir: Path, name: str, sizes: list[int]) -> dict:
    report = {}
    for slot, data in material_images(rigged).items():
        image = Image.open(io.BytesIO(data))
        pixels = np.asarray(image.convert("RGB"))
        report[slot] = {"source": f"{image.format} {image.width}x{image.height}"}
        for size in sizes:
            suffix = "" if size == sizes[0] else f"_{size}"
            path = out_dir / f"{name}_{slot}{suffix}.png"
            palette.write_png(str(path), box_reduce(pixels, size, srgb=slot == "base_color"))
            report[slot][str(size)] = path.name
    return report


# --------------------------------------------------------------------------------- driver


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_blender(blender: str, args: list[str], log: Path) -> None:
    # One thread: with more, MikkTSpace gave 2 of 18,862 tangents a different last digit (1e-4)
    # between two runs, and one normal-map texel followed them.
    command = [blender, "-b", "--factory-startup", "-t", "1", "--python-exit-code", "1",
               "--python", str(HERE / "blender_prepare.py"), "--", *args]
    with log.open("w", encoding="utf-8", errors="replace") as handle:
        result = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, check=False)
    if result.returncode != 0:
        raise PrepareError(f"Blender failed with exit code {result.returncode}; see {log.name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--rigged", type=Path, required=True, help="rigged working mesh (.glb)")
    parser.add_argument("--high", type=Path, required=True, help="high-resolution source (.glb)")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--name", required=True, help="file stem of the outputs")
    parser.add_argument("--role", required=True, help="budget role for the final check")
    parser.add_argument("--height", type=float, required=True, help="target height in metres")
    parser.add_argument("--triangles", type=int, required=True, help="target triangle count")
    parser.add_argument("--texture-size", type=int, default=1024)
    parser.add_argument("--normal-size", type=int, help="normal map size (default: texture size)")
    parser.add_argument("--texture-variants", default="", help="extra sizes, e.g. 512,2048")
    parser.add_argument("--swap-sides", action="store_true", help="trade .L/.R joint names")
    parser.add_argument("--lod-source", choices=("high", "rigged"), default="high",
                        help="mesh to reduce; `high` transfers the weights (default)")
    parser.add_argument("--blender", default=os.environ.get("BLENDER", "blender"))
    args = parser.parse_args(argv)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    name = args.name
    sizes = [args.texture_size] + [int(s) for s in args.texture_variants.split(",") if s.strip()]
    normal_size = args.normal_size or args.texture_size

    try:
        texture_report = prepare_textures(args.rigged, out, name, sizes)
        glb_out = out / f"{name}.glb"
        prepare_report = out / f"{name}_prepare.json"
        normal_map = out / f"{name}_normal.png"
        blender_args = [
            "--rigged", str(args.rigged), "--high", str(args.high),
            "--base-color", str(out / f"{name}_base_color.png"),
            "--metallic-roughness", str(out / f"{name}_metallic_roughness.png"),
            "--out", str(glb_out), "--normal-map-out", str(normal_map),
            "--report", str(prepare_report),
            "--height", str(args.height), "--triangles", str(args.triangles),
            "--normal-size", str(normal_size),
        ]  # fmt: skip
        blender_args += ["--lod-source", args.lod_source]
        if args.swap_sides:
            blender_args.append("--swap-sides")
        run_blender(args.blender, blender_args, out / f"{name}_blender.log")
    except (PrepareError, GlbError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return check_asset.EXIT_ERROR

    report = json.loads(prepare_report.read_text(encoding="utf-8"))
    report["textures"] = texture_report
    report["texture_size"] = args.texture_size
    prepare_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    budgets = check_asset.load_budgets(check_asset.DEFAULT_BUDGETS, args.role)
    facts = measure_glb(glb_out)
    checks = check_asset.evaluate(facts, budgets, args.role)
    check = check_asset.build_report(facts, budgets, check_asset.DEFAULT_BUDGETS, args.role, checks)
    check_path = out / f"{name}_check.json"
    check_path.write_text(json.dumps(check, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(check_asset.format_summary(check))

    deterministic = sorted(
        p for p in out.iterdir()
        if p.name.startswith(name) and p.suffix in (".glb", ".png", ".json")
    )
    manifest = {p.name: sha256(p) for p in deterministic}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"prepared {glb_out.name}: {len(manifest)} files in manifest.json")
    return check_asset.EXIT_FAIL if check["verdict"] == "fail" else check_asset.EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
