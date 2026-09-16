"""Build lightweight actor-material and projectile previews; full masters are explicit."""

from __future__ import annotations

import os

# Set limits before importing numerical libraries. No GPU backend is used.
for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[variable] = "1"

import argparse
import ctypes
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import time
import zlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent))
import generate as shared
import validate as material_validator
from actor_surfaces import make_surface
from projectiles import make_projectile, projectile_catalog


def lower_priority() -> None:
    if os.name == "nt":
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
        kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x40)  # Idle process class.
    elif hasattr(os, "nice"):
        os.nice(19)


def record(path: Path, root: Path, role: str, mid: str | None = None) -> dict:
    payload = path.read_bytes()
    return {"path": path.relative_to(root).as_posix(), "role": role, "material_id": mid,
            "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def save_png(path: Path, pixels: np.ndarray) -> None:
    Image.fromarray(pixels).save(path, compress_level=3)


def write_manifest(root: Path, files: list[dict], resolution: int, kind: str) -> None:
    shared.write_json(root / "manifest.json", {
        "schema_version": 1, "kind": kind, "resolution": resolution,
        "status": "preview" if resolution == 128 else "master",
        "external_sources": [], "license": "project_license",
        "provenance": "Original procedural artwork; no source images, downloads or image services",
        "files": sorted(files, key=lambda item: item["path"]),
    })


def create_material_board(cards: list[tuple], destination: Path, size: int) -> None:
    board = Image.new("RGB", (1200, 110 + 4 * 310), (14, 19, 25))
    draw = ImageDraw.Draw(board)
    font = ImageFont.load_default(size=19)
    small = ImageFont.load_default(size=14)
    draw.text((24, 20), "FIENDS N PATRONS / MONSTERS + PLAYER", fill=(220, 229, 239), font=font)
    draw.text((24, 56), f"{size}px design previews | Left: unlit pigment | Right: neutral lighting study", fill=(159, 175, 194), font=small)
    for index, (spec, color, shaded) in enumerate(cards):
        x, y = 20 + index % 3 * 400, 110 + index // 3 * 310
        draw.rounded_rectangle((x - 4, y, x + 376, y + 292), radius=8, fill=(23, 30, 39))
        draw.text((x + 8, y + 12), spec["label"], fill=(220, 229, 239), font=font)
        for offset, data in ((8, color), (190, shaded)):
            tile = Image.fromarray(data).resize((172, 172), Image.Resampling.NEAREST)
            board.paste(tile, (x + offset, y + 46))
        draw.text((x + 8, y + 232), spec["id"], fill=(165, 185, 207), font=small)
        draw.text((x + 8, y + 257), f"{spec['basecolor']}   R {spec['roughness']:.2f}   M {spec['metallic']}", fill=(144, 164, 187), font=small)
    board.save(destination, compress_level=3)


def projectile_board(sprites: list[tuple], destination: Path, size: int) -> None:
    columns, card_width, card_height = 4, 330, 470
    rows = (len(sprites) + columns - 1) // columns
    board = Image.new("RGBA", (1360, 140 + rows * card_height), (12, 17, 23, 255))
    draw = ImageDraw.Draw(board)
    title = ImageFont.load_default(size=30)
    font = ImageFont.load_default(size=20)
    small = ImageFont.load_default(size=14)
    draw.text((28, 20), "FIENDS N PATRONS / GOTHIC ORDNANCE", fill=(223, 218, 200), font=title)
    draw.text((28, 63), f"{size}px RGBA | Holz, Stahl, Knochen und Alchemieglas | Magie als Akzent", fill=(148, 163, 176), font=small)
    draw.text((28, 87), "Unten: 32 / 48 / 64 px bei 100 % Ansicht. Gemalte Unlit-Sprites; kein Engine-Render.", fill=(148, 163, 176), font=small)
    for index, (spec, pixels) in enumerate(sprites):
        x, y = 20 + index % columns * card_width, 125 + index // columns * card_height
        draw.rounded_rectangle((x, y, x + 316, y + card_height - 16), radius=6, fill=(20, 27, 34), outline=(64, 65, 61))
        signal = tuple(int(spec["signal_hex"][i:i+2], 16) for i in (1, 3, 5))
        draw.line((x+15, y+14, x+53, y+14), fill=signal, width=2)
        draw.text((x+15, y+25), spec["label"], fill=(222, 218, 204), font=font)
        team = "SPIELER" if spec["team"] == "player" else "GEGNER"
        draw.text((x+15, y+53), f"{index+1:02d} / {team} / ENTWURF", fill=(129, 151, 170), font=small)
        source = Image.fromarray(pixels)
        board.alpha_composite(source.resize((284, 284), Image.Resampling.LANCZOS), (x+16, y+67))
        for column, thumb_size in enumerate((32, 48, 64)):
            tx = x+14+column*99
            draw.rounded_rectangle((tx, y+346, tx+90, y+418), radius=3, fill=(51, 54, 61))
            # Resampling uses coverage-aware filtering; output remains straight alpha.
            thumbnail = source.resize((thumb_size, thumb_size), Image.Resampling.LANCZOS)
            board.alpha_composite(thumbnail, (tx+(90-thumb_size)//2, y+350+(64-thumb_size)//2))
            draw.text((tx+24, y+428), f"{thumb_size} px", fill=(150, 167, 181), font=small)
    board.convert("RGB").save(destination, compress_level=3)


def png_chunks_are_clean(path: Path) -> bool:
    payload = path.read_bytes()
    if payload[:8] != b"\x89PNG\r\n\x1a\n":
        return False
    offset = 8
    while offset < len(payload):
        length = struct.unpack(">I", payload[offset:offset + 4])[0]
        tag = payload[offset + 4:offset + 8]
        if tag not in (b"IHDR", b"IDAT", b"IEND"):
            return False
        data = payload[offset + 8:offset + 8 + length]
        crc = struct.unpack(">I", payload[offset + 8 + length:offset + 12 + length])[0]
        if crc != zlib.crc32(tag + data) & 0xFFFFFFFF:
            return False
        offset += 12 + length
    return offset == len(payload)


def validate_projectiles(root: Path, sprites: list[tuple], size: int) -> dict:
    results = []
    for spec, pixels in sprites:
        path = root / f"{spec['id']}_sprite.png"
        with Image.open(path) as loaded:
            actual = np.array(loaded)
            assert loaded.mode == "RGBA" and loaded.size == (size, size)
        assert np.array_equal(actual, pixels)
        alpha = actual[..., 3]
        pad = max(1, math.ceil(size * 0.08))
        assert not (alpha[:pad].any() or alpha[-pad:].any() or alpha[:, :pad].any() or alpha[:, -pad:].any()), spec["id"] + ": insufficient padding"
        assert 0.015 < (alpha > 0).mean() < 0.8, spec["id"] + ": invalid silhouette coverage"
        assert (alpha == 255).any(), spec["id"] + ": no solid readable core"
        assert png_chunks_are_clean(path)
        # Small deterministic regeneration, done serially and only one sprite at a time.
        assert np.array_equal(make_projectile(spec, size), actual)
        checked_sizes = [16, 24, 32, 48, 64]
        for screen_size in checked_sizes:
            small_alpha = make_projectile(spec, screen_size)[..., 3]
            border = math.ceil(screen_size * 0.08)
            assert not (small_alpha[:border].any() or small_alpha[-border:].any()
                        or small_alpha[:, :border].any() or small_alpha[:, -border:].any()), spec["id"] + ": small-size padding"
        results.append({"id": spec["id"], "rgba_and_padding_passed": True,
                        "source_coverage_fraction": float((alpha > 0).mean()), "repeat_generation_identical": True,
                        "small_size_padding_passed_px": checked_sizes})
        time.sleep(0.08)
    return {"schema_version": 1, "passed": True, "resolution": size, "sprites": results,
            "limits": "No moving gameplay, contrast guarantee, collision or renderer integration has been tested"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master", action="store_true", help="Build full 1024px sources only after resource-intensive work is allowed")
    args = parser.parse_args()
    lower_priority()
    size = 1024 if args.master else 128
    output = BASE / ("master" if args.master else "preview_gothic")
    material_root, projectile_root = output / "materials", output / "projectiles"
    material_root.mkdir(parents=True, exist_ok=True)
    projectile_root.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((BASE / "catalog.json").read_text(encoding="utf-8"))
    files, cards = [], []
    shared.check_normal_convention()
    for index, original in enumerate(catalog["materials"]):
        spec = {**original, "scope": "actor", "scene_color": original["basecolor"]}
        mid = spec["id"]
        seed = catalog["seed"] + index * 1009
        field = make_surface(mid, size, seed)
        color = shared.make_color(spec, field)
        height = shared.camera_bandlimit(field["height_m"], spec["tile_size_m"])
        normal = shared.normals_from_height(height, spec["tile_size_m"])
        roughness = shared.scalar_map(spec["roughness"], shared.camera_bandlimit(field["roughness_variation"], spec["tile_size_m"]), 0.25, 1)
        orm = shared.to_u8(np.stack((field["ao"], roughness, np.full((size, size), spec["metallic"])), -1))
        folder = material_root / mid
        folder.mkdir(exist_ok=True)
        for role, data in {"basecolor": color, "normal": shared.to_u8(normal * 0.5 + 0.5), "orm": orm,
                           "tile_2x2": np.tile(color, (2, 2, 1))}.items():
            path = folder / f"{mid}_{role}.png"
            save_png(path, data)
            files.append(record(path, material_root, role, mid))
        metadata = shared.material_json(spec, seed, size)
        metadata.pop("scene_basecolor_srgb_hex")
        metadata.update({"design_status": "new_proposal", "group": original["group"],
                         "output_status": "master" if args.master else "preview"})
        path = folder / f"{mid}.json"
        shared.write_json(path, metadata)
        files.append(record(path, material_root, "material_parameters", mid))
        cards.append((spec, color, shared.shaded_preview(color, normal, orm)))
        print(f"Material {mid}: {size}px", flush=True)
        time.sleep(0.16)
    path = material_root / "actor_materials.png"
    create_material_board(cards, path, size)
    files.append(record(path, material_root, "preview_board"))
    write_manifest(material_root, files, size, "actor_pbr_materials")
    del cards

    audit = material_validator.Audit()
    for spec in catalog["materials"]:
        path = material_root / spec["id"] / f"{spec['id']}.json"
        material_validator.validate_material(path, material_root, size, audit)
        time.sleep(0.06)
    material_validator.validate_manifest(material_root, audit)
    report = audit.result()
    shared.write_json(material_root / "validation.json", report)
    if not report["passed"]:
        raise ValueError(json.dumps(report["errors"]))

    sprites, files = [], []
    for spec in projectile_catalog():
        pixels = make_projectile(spec, size)
        path = projectile_root / f"{spec['id']}_sprite.png"
        save_png(path, pixels)
        files.append(record(path, projectile_root, "unlit_rgba_sprite"))
        metadata = {**spec, "schema_version": 1, "texture": path.name, "resolution": [size, size],
                    "color_space": "sRGB", "alpha_space": "linear_coverage", "alpha_premultiplied": False,
                    "wrap": "clamp_to_edge", "opacity": "texture_alpha", "output_status": "master" if args.master else "preview",
                    "source": "original_procedural", "license": "project_license", "external_sources": [],
                    "integration": "Protected projectile pass after world postprocessing; no lighting or scene bloom; no implied gameplay/collision rule"}
        path = projectile_root / f"{spec['id']}.json"
        shared.write_json(path, metadata)
        files.append(record(path, projectile_root, "sprite_parameters"))
        sprites.append((spec, pixels))
        print(f"Projectile {spec['id']}: {size}px", flush=True)
        time.sleep(0.12)
    path = projectile_root / "projectile_sheet.png"
    projectile_board(sprites, path, size)
    files.append(record(path, projectile_root, "preview_board"))
    write_manifest(projectile_root, files, size, "unlit_projectile_sprites")
    shared.write_json(projectile_root / "validation.json", validate_projectiles(projectile_root, sprites, size))
    for path in output.rglob("*.png"):
        assert png_chunks_are_clean(path)
    shared.write_json(output / "build_info.json", {
        "schema_version": 1, "status": "master" if args.master else "preview", "resolution": size,
        "material_count": len(catalog["materials"]), "projectile_count": len(sprites),
        "gpu_used": False, "numerical_threads": 1, "passed": True,
        "source_sha256": {name: hashlib.sha256((BASE / name).read_bytes()).hexdigest()
                          for name in ("build.py", "actor_surfaces.py", "projectiles.py", "arrow_art.py", "bomb_art.py", "catalog.json")},
        "shared_source_sha256": {name: hashlib.sha256((BASE.parent / name).read_bytes()).hexdigest()
                                 for name in ("generate.py", "surfaces.py", "validate.py", "requirements.txt")},
        "limits": "Only the resolution listed here has been generated and validated. The actual game scene and moving-camera readability require separate checks."
    })
    print(f"Completed {size}px output: {len(catalog['materials'])} PBR materials and {len(sprites)} sprites; checks passed.")


if __name__ == "__main__":
    main()
