"""Build periodic PBR texture sources. No external artwork or image services are used."""

from __future__ import annotations

import argparse
import colorsys
import hashlib
import json
import math
import os
from pathlib import Path
import time

for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[variable] = "1"

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from surfaces import make_surface

BASE = Path(__file__).resolve().parent


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def to_u8(value: np.ndarray) -> np.ndarray:
    return np.rint(np.clip(value, 0, 1) * 255).astype(np.uint8)


def rgb_hex(value: str) -> np.ndarray:
    return np.array([int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)])


def srgb_to_linear(rgb: np.ndarray) -> np.ndarray:
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(rgb: np.ndarray) -> np.ndarray:
    return np.where(rgb <= 0.0031308, 12.92 * rgb, 1.055 * np.maximum(rgb, 0) ** (1 / 2.4) - 0.055)


def save_png(path: Path, data: np.ndarray) -> None:
    # Construct a fresh image: no EXIF, text, timestamps, profiles, or source metadata.
    Image.fromarray(data).save(path, format="PNG", compress_level=9)


def normals_from_height(height: np.ndarray, tile_size: list[float]) -> np.ndarray:
    """Tangent +Y is opposite to increasing top-down PNG row index."""
    rows, cols = height.shape
    dx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * cols / (2 * tile_size[0])
    drow = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * rows / (2 * tile_size[1])
    normal = np.stack((-dx, drow, np.ones_like(height)), axis=-1)
    return normal / np.linalg.norm(normal, axis=-1, keepdims=True)


def camera_bandlimit(field: np.ndarray, tile_size: list[float]) -> np.ndarray:
    """Periodic low pass: remove relief/roughness above 14 cycles per meter."""
    rows, cols = field.shape
    fx = np.fft.rfftfreq(cols, d=tile_size[0] / cols)
    fy = np.fft.fftfreq(rows, d=tile_size[1] / rows)
    radial = np.sqrt(fx[None, :] ** 2 + fy[:, None] ** 2)
    transition = np.clip((radial - 9.0) / 5.0, 0, 1)
    weight = 0.5 + 0.5 * np.cos(np.pi * transition)
    return np.fft.irfft2(np.fft.rfft2(field) * weight, s=field.shape)


def hsv_rgb(hue: np.ndarray, saturation: np.ndarray, value: np.ndarray) -> np.ndarray:
    channels = []
    for shift in (0, 2 / 3, 1 / 3):
        wave = np.clip(np.abs(((hue + shift) % 1) * 6 - 3) - 1, 0, 1)
        channels.append(value * (1 - saturation + saturation * wave))
    return np.stack(channels, -1)


def make_color(spec: dict, surface: dict) -> np.ndarray:
    target = rgb_hex(spec["basecolor"])
    variation = np.clip(surface["albedo_variation"], -0.18, 0.18)
    variation = variation - variation.mean()
    if spec["scope"] in ("actor", "prop"):
        # Actual pigments only: relief, occlusion and directional lighting stay separate.
        return to_u8(target * (1 + variation[..., None]))

    # Solve the underlying blue tint so sparse moss does not shift the intended mean.
    moss = surface.get("moss_mask", np.zeros_like(variation))
    estimate = target.copy()
    for _ in range(20):
        h, s, v = colorsys.rgb_to_hsv(*np.clip(estimate, 0.001, 1))
        h = np.clip(h * 360, 204, 236) / 360
        s = min(s, 0.23)
        # Fade chroma through grey; a blue/green RGB mix would cross excluded cyan hues.
        weight = np.clip(moss, 0, 1)
        hue = np.where(weight <= 0.5, h, 105 / 360)
        sat = np.where(weight <= 0.5, s * (1 - 2 * weight), 0.21 * (2 * weight - 1))
        val = np.clip(v * (1 - weight) + min(v * 0.79, 0.245) * weight, 0, 0.345)
        val = np.clip(val * (1 + variation), 0, 0.345)
        val = np.where(weight > 0.5, np.minimum(val, 0.25), val)
        color = hsv_rgb(hue, sat, val)
        estimate += target - color.mean(axis=(0, 1))
    result = to_u8(color)
    if np.any(moss > 0.5):
        # Hue 105 degrees has exact integer RGB ratios at chroma multiples of 4.
        # This keeps low-saturation green texels inside 100..110 after 8-bit rounding.
        high = result.max(axis=2).astype(int)
        chroma = ((high - result.min(axis=2).astype(int)) // 4) * 4
        moss_rgb = np.stack((high - 3 * chroma // 4, high, high - chroma), -1).astype(np.uint8)
        result = np.where((moss > 0.5)[..., None], moss_rgb, result)
    # Near-neutral 8-bit values can quantize to an arbitrary hue. Neutralize those
    # tiny chroma steps, rather than accidentally introducing a forbidden hue.
    span = result.max(axis=2).astype(int) - result.min(axis=2).astype(int)
    neutral = np.rint(result.mean(axis=2)).astype(np.uint8)
    result = np.where((span <= 2)[..., None], neutral[..., None], result)
    return result


def scalar_map(target: float, delta: np.ndarray, lower: float, upper: float) -> np.ndarray:
    result = target + delta - delta.mean()
    for _ in range(8):
        result = np.clip(result, lower, upper)
        result += target - result.mean()
    return np.clip(result, lower, upper)


def shaded_preview(color: np.ndarray, normal: np.ndarray, orm: np.ndarray) -> np.ndarray:
    """A neutral GGX plane study, not a game-engine render or the base-color map."""
    base = srgb_to_linear(color / 255)
    rough = np.maximum(orm[..., 1] / 255, 0.25)
    metal = orm[..., 2] / 255
    ao = orm[..., 0] / 255
    view = np.array([0.0, 0.0, 1.0])
    rgb = base * (1 - metal[..., None]) * 0.25 * ao[..., None]
    rgb += base * metal[..., None] * 0.22
    for direction, energy in (([-0.55, 0.55, 0.65], 2.7), ([0.5, -0.25, 0.83], 0.9)):
        light = np.array(direction)
        light /= np.linalg.norm(light)
        half = light + view
        half /= np.linalg.norm(half)
        nl = np.maximum(normal @ light, 0)
        nv = np.maximum(normal[..., 2], 0.001)
        nh = np.maximum(normal @ half, 0)
        vh = max(float(view @ half), 0)
        a2 = rough ** 4
        distribution = a2 / (math.pi * (nh * nh * (a2 - 1) + 1) ** 2)
        k = (rough + 1) ** 2 / 8
        visibility = (nv / (nv * (1 - k) + k)) * (nl / (nl * (1 - k) + k))
        f0 = 0.04 * (1 - metal[..., None]) + base * metal[..., None]
        fresnel = f0 + (1 - f0) * (1 - vh) ** 5
        specular = (distribution * visibility / np.maximum(4 * nv * nl, 0.001))[..., None] * fresnel
        diffuse = (1 - fresnel) * (1 - metal[..., None]) * base / math.pi
        rgb += (diffuse + specular) * nl[..., None] * energy
    return to_u8(linear_to_srgb(np.clip(rgb, 0, 1)))


def material_json(spec: dict, seed: int, size: int) -> dict:
    mid = spec["id"]
    return {
        "schema_version": 1, "material_id": mid, "seed": seed,
        "resolution": [size, size], "scope": spec["scope"],
        "target_basecolor_srgb_hex": spec["basecolor"],
        "scene_basecolor_srgb_hex": spec["scene_color"],
        "base_color_factor": [1, 1, 1, 1], "roughness_factor": 1, "metallic_factor": 1,
        "roughness_mean_target": spec["roughness"], "metallic_mean_target": spec["metallic"],
        "uv_scale": [1, 1], "tile_size_m": spec["tile_size_m"],
        "normal": {"space": "tangent", "convention": "OpenGL", "y_sign": 1, "strength": 1},
        "detail_filter": {"height_and_roughness_cutoff_cycles_per_meter": 14,
                          "transition_start_cycles_per_meter": 9},
        "textures": {
            "basecolor": {"file": f"{mid}_basecolor.png", "color_space": "sRGB"},
            "normal": {"file": f"{mid}_normal.png", "color_space": "linear"},
            "orm": {"file": f"{mid}_orm.png", "color_space": "linear",
                    "channels": {"R": "occlusion", "G": "roughness", "B": "metallic"}}
        },
        "palette": {"policy": {"environment": "strict_cool_environment", "prop": "natural_prop", "actor": "scene_actor"}[spec["scope"]],
                    **({"moss_hue_range": [100, 110]} if mid == "ruin_wall_moss" else {})},
        "occlusion_scope": "material_relief_only; model-space occlusion requires a later mesh bake",
        "uv_contract": "One UV unit spans tile_size_m. Derive mesh UVs in physical units; do not apply scale twice.",
        "source": {"kind": "original_procedural", "external_assets": [], "license": "project_license"},
        "note": spec.get("note", ""),
    }


def create_board(output: Path, cards: list[tuple], size: int) -> None:
    width, height = 480, 424
    board = Image.new("RGB", (4 * width, 108 + math.ceil(len(cards) / 4) * height), (14, 19, 25))
    draw = ImageDraw.Draw(board)
    title_font = ImageFont.load_default(size=30)
    font = ImageFont.load_default(size=19)
    small = ImageFont.load_default(size=15)
    draw.text((24, 18), "FIENDS N PATRONS / MATERIAL STUDIES 01", fill=(215, 223, 234), font=title_font)
    draw.text((24, 62), f"Top: unlit color | Bottom: neutral GGX study | Source maps: {size} px, periodic, seeded", fill=(148, 163, 183), font=font)
    for index, (spec, base, shaded, normal) in enumerate(cards):
        x, y = (index % 4) * width + 20, (index // 4) * height + 108
        draw.rounded_rectangle((x - 4, y, x + width - 24, y + height - 12), radius=8, fill=(23, 30, 39))
        draw.text((x + 8, y + 10), spec["label"], fill=(221, 227, 236), font=font)
        image_width, image_height = width - 48, 142
        for offset, data in ((42, base), (194, shaded)):
            # Preserve the square tile aspect: show two repetitions across each strip.
            tile = Image.fromarray(data).resize((image_height, image_height), Image.Resampling.LANCZOS)
            strip = Image.new("RGB", (image_width, image_height))
            for tx in range(0, image_width, image_height):
                strip.paste(tile, (tx, 0))
            board.paste(strip, (x + 8, y + offset))
        draw.text((x + 8, y + 346), f"{spec['id']} / {spec['tile_size_m'][0]:g} m tile", fill=(166, 182, 201), font=small)
        draw.text((x + 8, y + 373), f"{spec['basecolor']}   R {spec['roughness']:.2f}   M {spec['metallic']}   {spec['scope']}", fill=(137, 153, 174), font=small)
    board.save(output / "material_board.png", compress_level=9)


def check_normal_convention() -> None:
    coords = np.arange(64) / 64
    height = np.broadcast_to(0.01 * np.sin(2 * np.pi * coords)[None, :], (64, 64)).copy()
    nx = normals_from_height(height, [1, 1])
    ny = normals_from_height(height.T, [1, 1])
    assert nx[0, 0, 0] < 0 and ny[0, 0, 1] > 0, "Normal convention failed"
    assert np.allclose(np.linalg.norm(nx, axis=2), 1), "Normal normalization failed"


def create_camera_board(output: Path, cards: list[tuple]) -> None:
    selected = [card for card in cards if card[0]["id"] in ("floor_tiles", "ruin_wall_moss", "altar_basalt", "cloak_fabric")]
    board = Image.new("RGB", (1240, 120 + 232 * len(selected)), (14, 19, 25))
    draw = ImageDraw.Draw(board)
    font = ImageFont.load_default(size=19)
    small = ImageFont.load_default(size=15)
    draw.text((24, 18), "CAMERA SCALE / UNLIT MATERIAL COLOR", fill=(219, 228, 237), font=font)
    draw.text((24, 48), "Each sample shows 6 x 2.5 meters. View at 100%; this is a sampling study, not a scene render.", fill=(157, 172, 191), font=small)
    for column, ppm in enumerate((35, 50, 65)):
        draw.text((24 + column * 410, 83), f"{ppm} pixels per meter", fill=(197, 211, 228), font=font)
    for row, (spec, _, _, _) in enumerate(selected):
        path = output / spec["id"] / f"{spec['id']}_basecolor.png"
        with Image.open(path) as source:
            for col, ppm in enumerate((35, 50, 65)):
                tw = max(1, round(spec["tile_size_m"][0] * ppm))
                th = max(1, round(spec["tile_size_m"][1] * ppm))
                tile = source.resize((tw, th), Image.Resampling.LANCZOS)
                sample = Image.new("RGB", (round(6 * ppm), round(2.5 * ppm)))
                for y in range(0, sample.height, th):
                    for x in range(0, sample.width, tw):
                        sample.paste(tile, (x, y))
                x, y = 24 + col * 410, 120 + row * 232
                draw.text((x, y), spec["label"], fill=(185, 201, 219), font=small)
                board.paste(sample, (x, y + 25))
    board.save(output / "camera_scale.png", compress_level=9)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="generated", help="Subdirectory within this source directory")
    parser.add_argument("--size", type=int, default=None, help="Power-of-two source resolution; master is 1024")
    parser.add_argument("--light-preview", action="store_true", help="128px, idle priority, serial pacing; writes preview_revision")
    args = parser.parse_args()
    if args.light_preview:
        args.size, args.output = 128, "preview_revision"
        if os.name == "nt":
            import ctypes
            kernel = ctypes.windll.kernel32
            kernel.GetCurrentProcess.restype = ctypes.c_void_p
            kernel.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
            kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x40)
        elif hasattr(os, "nice"):
            os.nice(19)
    output = (BASE / args.output).resolve()
    if not output.is_relative_to(BASE) or output == BASE:
        parser.error("Output must be a child directory of the texture source directory")
    catalog = json.loads((BASE / "catalog.json").read_text(encoding="utf-8"))
    size = args.size or catalog["resolution"]
    if size < 64 or size > 2048 or size & (size - 1):
        parser.error("Size must be a power of two between 64 and 2048")
    check_normal_convention()
    output.mkdir(parents=True, exist_ok=True)
    cards, recorded = [], []
    for index, spec in enumerate(catalog["materials"]):
        mid = spec["id"]
        seed = catalog["seed"] + index * 1009
        surface = make_surface(mid, size, seed)
        color = make_color(spec, surface)
        height = camera_bandlimit(surface["height_m"], spec["tile_size_m"])
        normal = normals_from_height(height, spec["tile_size_m"])
        rough_delta = camera_bandlimit(surface["roughness_variation"], spec["tile_size_m"])
        rough = scalar_map(spec["roughness"], rough_delta, 0.25, 1)
        metal = np.full((size, size), spec["metallic"], dtype=float)
        orm = to_u8(np.stack((np.clip(surface["ao"], 0.85, 1), rough, metal), -1))
        dest = output / mid
        dest.mkdir(exist_ok=True)
        maps = {"basecolor": color, "normal": to_u8(normal * 0.5 + 0.5), "orm": orm,
                "tile_2x2": np.tile(color, (2, 2, 1))}
        for role, array in maps.items():
            path = dest / f"{mid}_{role}.png"
            save_png(path, array)
            recorded.append((path, role, mid))
        path = dest / f"{mid}.json"
        write_json(path, material_json(spec, seed, size))
        recorded.append((path, "material_parameters", mid))
        # Preview lighting is deliberately confined to the overview board.
        thumb = 128 if args.light_preview else 256
        c = np.array(Image.fromarray(color).resize((thumb, thumb), Image.Resampling.LANCZOS))
        n = np.stack([np.array(Image.fromarray(normal[..., ch].astype(np.float32)).resize((thumb, thumb), Image.Resampling.BILINEAR)) for ch in range(3)], -1)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        o = np.array(Image.fromarray(orm).resize((thumb, thumb), Image.Resampling.BILINEAR))
        cards.append((spec, c, shaded_preview(c, n, o), n))
        print(f"{mid}: {size} px, mean RGB {np.rint(color.mean(axis=(0, 1))).astype(int).tolist()}", flush=True)
        if args.light_preview:
            time.sleep(0.18)
    create_board(output, cards, size)
    recorded.append((output / "material_board.png", "preview_board", None))
    create_camera_board(output, cards)
    recorded.append((output / "camera_scale.png", "camera_scale_preview", None))
    files = []
    for path, role, mid in sorted(recorded, key=lambda row: row[0].relative_to(output).as_posix()):
        payload = path.read_bytes()
        files.append({"path": path.relative_to(output).as_posix(), "sha256": hashlib.sha256(payload).hexdigest(),
                      "bytes": len(payload), "role": role, "material_id": mid})
    write_json(output / "manifest.json", {
        "schema_version": 1, "generator": "generate.py", "catalog": "catalog.json", "seed": catalog["seed"],
        "resolution": size, "output_status": "preview" if size < 1024 else "master",
        "provenance": "Original procedural materials, no third-party artwork or source images",
        "external_sources": [], "license": "project_license", "files": files,
        "generator_sources_sha256": {name: hashlib.sha256((BASE / name).read_bytes()).hexdigest()
                                     for name in ("generate.py", "surfaces.py", "catalog.json", "requirements.txt")},
        "reproducibility": "Fixed seeds and pinned dependencies; byte equality verified separately in the tested environment. Cross-platform byte equality is not asserted."
    })
    print(f"Built {len(cards)} materials; {sum(f['bytes'] for f in files) / 1048576:.2f} MiB of generated files.")


if __name__ == "__main__":
    main()
