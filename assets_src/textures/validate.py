#!/usr/bin/env python3
"""Validate the generated texture library without requiring Blender or a GPU.

Only --write-report writes a file, and that file must stay inside this script's
directory. Reports use library-relative paths and omit host information.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import struct
import sys
import zlib

import numpy as np
from PIL import Image


SCRIPT_DIR = Path(__file__).resolve().parent
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MATERIAL_ID = re.compile(r"^[a-z][a-z0-9_-]*$")
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
ABSOLUTE_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\[^\\\s]+\\|"
    r"/(?:home|Users|root|mnt|tmp|var|opt|usr|private)/)"
)
HOST_KEY = re.compile(
    r"^(?:user_?name|home_?(?:dir|directory)|host_?name|computer_?name|"
    r"machine_?name|(?:gpu|cpu|device)_?(?:name|model)|hardware|os_version)$",
    re.IGNORECASE,
)
HARDWARE_VALUE = re.compile(
    r"\b(?:GeForce|Radeon|NVIDIA|RTX\s*\d|GTX\s*\d|"
    r"Intel\(R\)|AMD\s+Ryzen|Apple\s+M\d)\b", re.IGNORECASE
)


class Audit:
    def __init__(self) -> None:
        self.errors: list[dict[str, str]] = []
        self.materials: list[dict] = []
        self.manifest: dict = {}
        self.checked_pngs: set[str] = set()

    def check(self, condition: bool, location: str, message: str) -> bool:
        if not condition:
            self.errors.append({"location": location, "message": message})
        return bool(condition)

    def result(self) -> dict:
        return {
            "schema_version": 1,
            "passed": not self.errors,
            "material_count": len(self.materials),
            "checks": {
                "png": "RGB8; IHDR/IDAT/IEND only; CRC and image decoding",
                "normal": "tangent OpenGL +Y metadata; length 0.99..1.01; positive Z",
                "seams": "wrap gradients versus interior gradients; no endpoint duplication",
                "ao": "channel layout only; geometric occlusion accuracy is not established",
                "reproducibility": "manifest integrity only; independent regeneration is separate",
            },
            "manifest": self.manifest,
            "materials": self.materials,
            "errors": self.errors,
        }


def is_number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def check_private_data(value: object, location: str, audit: Audit) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if HOST_KEY.fullmatch(str(key)):
                audit.check(False, location, "Host-specific metadata field is forbidden.")
            check_private_data(item, location, audit)
    elif isinstance(value, list):
        for item in value:
            check_private_data(item, location, audit)
    elif isinstance(value, str):
        audit.check(not ABSOLUTE_PATH.search(value), location, "Absolute or home path found.")
        audit.check(not HARDWARE_VALUE.search(value), location, "Hardware identifier found.")


def read_json(path: Path, location: str, audit: Audit) -> dict | None:
    try:
        def no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate JSON key")
                result[key] = value
            return result

        def no_constant(_: str) -> None:
            raise ValueError("Non-finite JSON number")

        data = json.loads(path.read_text(encoding="utf-8"),
                          object_pairs_hook=no_duplicate_keys, parse_constant=no_constant)
        if not isinstance(data, dict):
            raise ValueError("Object required")
    except (OSError, UnicodeError, ValueError):
        audit.check(False, location, "Cannot read a strict UTF-8 JSON object.")
        return None
    check_private_data(data, location, audit)
    return data


def relative_path(root: Path, value: object, audit: Audit, location: str) -> Path | None:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        audit.check(False, location, "Expected a relative POSIX file path.")
        return None
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(part in {"..", "."} for part in value.split("/")):
        audit.check(False, location, "Unsafe relative file path.")
        return None
    path = root.joinpath(*relative.parts)
    if not path.resolve().is_relative_to(root.resolve()):
        audit.check(False, location, "File resolves outside the library.")
        return None
    if any(part.is_symlink() for part in (path, *path.parents) if part != root.parent):
        audit.check(False, location, "Symbolic links are not accepted in the library.")
        return None
    return path


def inspect_png(path: Path, location: str, audit: Audit) -> np.ndarray | None:
    try:
        raw = path.read_bytes()
        if raw[:8] != PNG_SIGNATURE:
            raise ValueError("Signature")
        offset = 8
        chunks = []
        header = None
        seen_end = False
        while offset < len(raw):
            if offset + 12 > len(raw):
                raise ValueError("Chunk header")
            size, kind = struct.unpack_from(">I4s", raw, offset)
            end = offset + 12 + size
            if end > len(raw):
                raise ValueError("Truncated chunk")
            payload = raw[offset + 8:offset + 8 + size]
            crc = struct.unpack_from(">I", raw, offset + 8 + size)[0]
            if zlib.crc32(kind + payload) & 0xFFFFFFFF != crc:
                raise ValueError("CRC")
            if kind not in {b"IHDR", b"IDAT", b"IEND"}:
                raise ValueError("Ancillary or unknown chunk")
            if kind == b"IHDR":
                if chunks or size != 13:
                    raise ValueError("IHDR")
                header = struct.unpack(">IIBBBBB", payload)
            if kind == b"IEND":
                if size or end != len(raw):
                    raise ValueError("IEND")
                seen_end = True
            chunks.append(kind)
            offset = end
        if not header or not seen_end or chunks[1:-1].count(b"IDAT") != len(chunks) - 2:
            raise ValueError("Chunk order")
        if len(chunks) < 3:
            raise ValueError("Missing image data")
        width, height, depth, color, compression, filtering, interlace = header
        if (depth, color, compression, filtering, interlace) != (8, 2, 0, 0, 0):
            raise ValueError("Must be non-interlaced RGB8")
        if not (1 <= width <= 4096 and 1 <= height <= 4096):
            raise ValueError("Dimensions out of bounds")
        with Image.open(path) as image:
            image.load()
            if image.mode != "RGB" or image.size != (width, height):
                raise ValueError("Decoded mode or dimensions")
            audit.checked_pngs.add(location)
            return np.array(image, dtype=np.uint8)
    except (OSError, ValueError, struct.error, Image.DecompressionBombError):
        audit.check(False, location, "Invalid PNG: require RGB8, valid CRCs, and IHDR/IDAT/IEND only.")
        return None


def seam_statistics(pixels: np.ndarray, location: str, audit: Audit) -> dict:
    values = pixels.astype(np.float32) / 255.0
    result = {}
    for axis, name in ((0, "vertical"), (1, "horizontal")):
        interior = np.abs(np.diff(values, axis=axis))
        boundary = np.abs(np.take(values, 0, axis=axis) - np.take(values, -1, axis=axis))
        internal_mean = interior.mean(axis=(0, 1), dtype=np.float64)
        boundary_mean = boundary.mean(axis=0, dtype=np.float64)
        limit = np.maximum(0.01, 3.0 * internal_mean)
        audit.check(bool(np.all(boundary_mean <= limit + 1e-10)), location,
                    f"{name.capitalize()} wrap gradient exceeds the seam threshold.")
        result[name] = {
            "interior_mean_rgb": internal_mean.tolist(),
            "wrap_mean_rgb": boundary_mean.tolist(),
            "wrap_max_rgb": boundary.max(axis=0).tolist(),
            "allowed_wrap_mean_rgb": limit.tolist(),
            "wrap_to_interior_mean_ratio_rgb": [
                float(wrap / inside) if inside > 1e-12 else (0.0 if wrap == 0 else None)
                for wrap, inside in zip(boundary_mean, internal_mean)
            ],
        }
    return result


def srgb_to_linear(values: np.ndarray) -> np.ndarray:
    return np.where(values <= 0.04045, values / 12.92, ((values + 0.055) / 1.055) ** 2.4)


def palette_statistics(pixels: np.ndarray, metadata: dict, location: str, audit: Audit) -> dict:
    rgb = pixels.astype(np.float32) / 255.0
    high = rgb.max(axis=2)
    low = rgb.min(axis=2)
    delta = high - low
    saturation = np.divide(delta, high, out=np.zeros_like(delta), where=high > 0)
    hue = np.zeros_like(delta)
    chromatic = delta > 0
    red = chromatic & (high == rgb[:, :, 0])
    green = chromatic & ~red & (high == rgb[:, :, 1])
    blue = chromatic & ~red & ~green
    hue[red] = ((rgb[:, :, 1][red] - rgb[:, :, 2][red]) / delta[red]) % 6
    hue[green] = (rgb[:, :, 2][green] - rgb[:, :, 0][green]) / delta[green] + 2
    hue[blue] = (rgb[:, :, 0][blue] - rgb[:, :, 1][blue]) / delta[blue] + 4
    hue *= 60
    result = {"maximum_saturation": float(saturation.max()), "maximum_value": float(high.max())}
    if metadata.get("scope") == "prop":
        chromatic = saturation > (1.0 / 255.0)
        forbidden = chromatic & (((hue >= 315) & (hue <= 335))
                                  | ((hue >= 75) & (hue <= 95))
                                  | ((hue >= 185) & (hue <= 200)))
        result["reserved_hue_violation_pixels"] = int(forbidden.sum())
        audit.check(not bool(forbidden.any()), location, "Prop color overlaps a reserved projectile hue range.")
        return result
    if metadata.get("scope") != "environment":
        return result
    palette = metadata.get("palette", {})
    moss = isinstance(palette, dict) and "moss_hue_range" in palette
    relevant_hue = saturation > (1.0 / 255.0)
    cool_hue = (hue >= 200.0 - 1e-4) & (hue <= 240.0 + 1e-4)
    moss_hue = (hue >= 100.0 - 1e-4) & (hue <= 110.0 + 1e-4) & moss
    bad_hue = relevant_hue & ~cool_hue & ~moss_hue
    bad_saturation = saturation > 0.25 + 1e-6
    value_limits = np.where(relevant_hue & moss_hue, 0.26, 0.35)
    bad_value = high > value_limits + 1e-6
    result.update({
        "allowed_hue_ranges": [[200.0, 240.0], [100.0, 110.0]] if moss else [[200.0, 240.0]],
        "maximum_cool_or_achromatic_value": 0.35,
        "maximum_moss_value": 0.26 if moss else None,
        "hue_violation_pixels": int(bad_hue.sum()),
        "saturation_violation_pixels": int(bad_saturation.sum()),
        "value_violation_pixels": int(bad_value.sum()),
    })
    audit.check(not bool(np.any(bad_hue)), location, "Environment pixels leave the permitted hue range.")
    audit.check(not bool(np.any(bad_saturation)), location, "Environment saturation exceeds 0.25.")
    audit.check(not bool(np.any(bad_value)), location, "Environment brightness exceeds its limit.")
    return result


def validate_material(path: Path, root: Path, expected_resolution: int, audit: Audit) -> None:
    location = path.relative_to(root).as_posix()
    metadata = read_json(path, location, audit)
    if metadata is None:
        return
    material_id = metadata.get("material_id")
    if not audit.check(isinstance(material_id, str) and bool(MATERIAL_ID.fullmatch(material_id)),
                       location, "Invalid material_id."):
        return
    audit.check(path.parent.name == material_id and path.name == material_id + ".json", location,
                "Material metadata must be stored in <id>/<id>.json.")
    audit.check(type(metadata.get("schema_version")) is int and metadata["schema_version"] == 1,
                location, "Expected schema_version 1.")
    seed = metadata.get("seed")
    audit.check(isinstance(seed, int) and not isinstance(seed, bool) and seed >= 0, location,
                "Expected a non-negative integer seed.")
    resolution = metadata.get("resolution")
    valid_resolution = (isinstance(resolution, list) and len(resolution) == 2
                        and all(isinstance(n, int) and not isinstance(n, bool) for n in resolution)
                        and resolution[0] == resolution[1] and resolution[0] >= 2
                        and resolution[0] & (resolution[0] - 1) == 0)
    if not audit.check(valid_resolution, location, "Resolution must be a square power of two >= 2."):
        return
    size = resolution[0]
    audit.check(size == expected_resolution, location, "Resolution differs from the requested output resolution.")
    scope = metadata.get("scope")
    audit.check(scope in ("environment", "actor", "prop"), location, "Expected environment, actor or prop scope.")
    palette = metadata.get("palette")
    valid_palette = isinstance(palette, dict)
    audit.check(valid_palette, location, "Palette metadata is required.")
    if valid_palette:
        policy = {"environment": "strict_cool_environment", "actor": "scene_actor", "prop": "natural_prop"}.get(scope)
        audit.check(palette.get("policy") == policy, location, "Palette policy does not match scope.")
        if "moss_hue_range" in palette:
            audit.check(palette["moss_hue_range"] == [100, 110] and scope == "environment", location,
                        "The moss exception must be environment hue 100..110.")
    for key, expected in (("base_color_factor", [1, 1, 1, 1]), ("roughness_factor", 1),
                          ("metallic_factor", 1), ("uv_scale", [1, 1])):
        value = metadata.get(key)
        numeric = (isinstance(value, list) and all(is_number(item) for item in value)
                   if isinstance(expected, list) else is_number(value))
        audit.check(numeric and value == expected, location, f"Unexpected {key}.")
    tile_size = metadata.get("tile_size_m")
    audit.check(isinstance(tile_size, list) and len(tile_size) == 2
                and all(is_number(value) and value > 0 for value in tile_size), location,
                "tile_size_m must contain two positive finite numbers.")
    normal_metadata = metadata.get("normal")
    audit.check(isinstance(normal_metadata, dict) and all(
        normal_metadata.get(key) == value for key, value in {
            "space": "tangent", "convention": "OpenGL", "y_sign": 1, "strength": 1,
        }.items()), location, "Expected tangent-space OpenGL +Y normal metadata with strength 1.")
    textures = metadata.get("textures")
    if not audit.check(isinstance(textures, dict), location, "Texture entries are required."):
        return
    audit.check(set(textures) <= {"basecolor", "normal", "orm", "emissive"}, location,
                "Unexpected texture role.")
    pixels_by_role = {}
    material_result = {"material_id": material_id, "resolution": resolution, "maps": {}}
    for role in ("basecolor", "normal", "orm", "emissive"):
        if role == "emissive" and role not in textures:
            continue
        entry = textures.get(role)
        map_location = f"{material_id}/{material_id}_{role}.png"
        if not audit.check(isinstance(entry, dict), location, f"Missing {role} texture entry."):
            continue
        audit.check(entry.get("file") == f"{material_id}_{role}.png", location,
                    f"Unexpected {role} filename.")
        color_space = "sRGB" if role in {"basecolor", "emissive"} else "linear"
        audit.check(entry.get("color_space") == color_space, location, f"Incorrect {role} color space.")
        if role == "orm":
            audit.check(entry.get("channels") == {"R": "occlusion", "G": "roughness", "B": "metallic"},
                        location, "ORM channels must be R=occlusion, G=roughness, B=metallic.")
        map_path = relative_path(root, map_location, audit, location)
        if map_path is None:
            continue
        pixels = inspect_png(map_path, map_location, audit)
        if pixels is None:
            continue
        if not audit.check(pixels.shape == (size, size, 3), map_location, "PNG dimensions disagree with metadata."):
            continue
        pixels_by_role[role] = pixels
        material_result["maps"][role] = {
            "mean_rgb8": pixels.mean(axis=(0, 1), dtype=np.float64).tolist(),
            "seams": seam_statistics(pixels, map_location, audit),
        }
    if "basecolor" in pixels_by_role:
        base = pixels_by_role["basecolor"]
        target_hex = metadata.get("target_basecolor_srgb_hex")
        if audit.check(isinstance(target_hex, str) and bool(HEX_COLOR.fullmatch(target_hex)), location,
                       "Expected target_basecolor_srgb_hex in #RRGGBB notation."):
            target = np.array([int(target_hex[start:start + 2], 16) for start in (1, 3, 5)])
            error = np.abs(base.mean(axis=(0, 1), dtype=np.float64) - target)
            audit.check(bool(np.all(error <= 2.0 + 1e-9)), location, "Mean base color differs from target by more than 2 RGB8 values.")
            material_result["basecolor_target_mean_error_rgb8"] = error.tolist()
        material_result["basecolor_linear_mean_rgb"] = srgb_to_linear(base.astype(np.float64) / 255.0).mean(axis=(0, 1)).tolist()
        material_result["palette"] = palette_statistics(base, metadata, location, audit)
        preview_location = f"{material_id}/{material_id}_tile_2x2.png"
        preview_path = relative_path(root, preview_location, audit, location)
        preview = inspect_png(preview_path, preview_location, audit) if preview_path else None
        if preview is not None and audit.check(preview.shape == (2 * size, 2 * size, 3), preview_location,
                                               "2x2 preview dimensions must be twice the base texture dimensions."):
            exact = all(np.array_equal(preview[y * size:(y + 1) * size, x * size:(x + 1) * size], base)
                        for y in (0, 1) for x in (0, 1))
            audit.check(exact, preview_location, "2x2 preview is not an exact base-color repetition.")
            material_result["tile_2x2_exact"] = exact
    if "normal" in pixels_by_role:
        normals = pixels_by_role["normal"].astype(np.float32) / 127.5 - 1.0
        lengths = np.linalg.norm(normals, axis=2)
        audit.check(bool(np.all((lengths >= 0.99) & (lengths <= 1.01))), location, "Decoded normal lengths must be within 0.99..1.01.")
        audit.check(bool(np.all(normals[:, :, 2] > 0)), location, "Normals must point into the positive-Z hemisphere.")
        material_result["normal_length_range"] = [float(lengths.min()), float(lengths.max())]
        material_result["normal_z_minimum"] = float(normals[:, :, 2].min())
    if "orm" in pixels_by_role:
        orm = pixels_by_role["orm"]
        audit.check(bool(np.all((orm[:, :, 2] == 0) | (orm[:, :, 2] == 255))), location,
                    "Metallic pixels must be 0 or 255; transitional metal masks are not used.")
        for channel, role in ((1, "roughness"), (2, "metallic")):
            target = metadata.get(f"{role}_mean_target")
            if audit.check(is_number(target) and 0 <= target <= 1, location, f"Invalid {role}_mean_target."):
                mean = float(orm[:, :, channel].mean(dtype=np.float64) / 255.0)
                audit.check(abs(mean - target) <= 2.0 / 255.0 + 1e-10, location,
                            f"Mean {role} differs from target by more than 2/255.")
                material_result[f"{role}_mean"] = mean
        material_result["ao_range_rgb8"] = [int(orm[:, :, 0].min()), int(orm[:, :, 0].max())]
    audit.materials.append(material_result)


def validate_manifest(root: Path, audit: Audit) -> None:
    manifest = read_json(root / "manifest.json", "manifest.json", audit)
    if manifest is None:
        return
    audit.check(type(manifest.get("schema_version")) is int and manifest["schema_version"] == 1,
                "manifest.json", "Expected schema_version 1.")
    audit.check(manifest.get("external_sources") == [], "manifest.json", "Expected an empty external_sources list.")
    files = manifest.get("files")
    if not audit.check(isinstance(files, list), "manifest.json", "Manifest files must be a list."):
        return
    indexed = set()
    total_bytes = 0
    known_ids = {material["material_id"] for material in audit.materials}
    for entry in files:
        if not audit.check(isinstance(entry, dict), "manifest.json", "Manifest file entry must be an object."):
            continue
        relative = entry.get("path")
        path = relative_path(root, relative, audit, "manifest.json")
        if path is None:
            continue
        audit.check(relative not in indexed, "manifest.json", "Duplicate manifest file entry.")
        indexed.add(relative)
        audit.check(relative not in {"manifest.json", "validation.json"}, "manifest.json",
                    "The manifest and validation report must not be hashed into the manifest.")
        audit.check(isinstance(entry.get("role"), str) and bool(entry["role"]), "manifest.json", "Manifest role is required.")
        material_id = entry.get("material_id")
        first_part = PurePosixPath(relative).parts[0]
        if first_part in known_ids:
            audit.check(material_id == first_part, "manifest.json", "Manifest material_id disagrees with its folder.")
        else:
            audit.check("material_id" in entry and (material_id is None or
                        isinstance(material_id, str) and material_id in known_ids),
                        "manifest.json", "Unknown manifest material_id.")
        try:
            raw = path.read_bytes()
        except OSError:
            audit.check(False, relative, "Manifest file is missing or unreadable.")
            continue
        total_bytes += len(raw)
        audit.check(isinstance(entry.get("bytes"), int) and not isinstance(entry.get("bytes"), bool)
                    and entry["bytes"] == len(raw), relative, "Manifest byte count mismatch.")
        digest = entry.get("sha256")
        audit.check(isinstance(digest, str) and bool(re.fullmatch(r"[0-9a-f]{64}", digest))
                    and digest == hashlib.sha256(raw).hexdigest(), relative, "Manifest SHA-256 mismatch.")
        if path.suffix.lower() == ".png" and relative not in audit.checked_pngs:
            inspect_png(path, relative, audit)
        if path.suffix.lower() in {".md", ".txt", ".json"}:
            try:
                check_private_data(raw.decode("utf-8"), relative, audit)
            except UnicodeError:
                audit.check(False, relative, "Text files must use UTF-8.")
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
              and path.relative_to(root).as_posix() not in {"manifest.json", "validation.json"}}
    for relative in sorted(actual - indexed):
        audit.check(False, relative, "File is absent from the manifest.")
    for relative in sorted(indexed - actual):
        audit.check(False, relative, "Manifest entry is absent from the library.")
    audit.manifest = {"file_count": len(indexed), "total_bytes": total_bytes,
                      "all_files_covered": actual == indexed}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prüft PNGs, PBR-Kanäle, Kachelung, Palette und Manifest.")
    parser.add_argument("--root", type=Path, default=SCRIPT_DIR / "generated", help="Ordner der generierten Bibliothek")
    parser.add_argument("--write-report", action="store_true", help="validation.json innerhalb des Texturordners schreiben")
    parser.add_argument("--expected-resolution", type=int, default=1024, help="Erwartete Kantenlänge (Standard: 1024)")
    args = parser.parse_args()
    root = args.root.resolve()
    audit = Audit()
    if not root.is_dir():
        print("Validierung fehlgeschlagen: Bibliotheksordner fehlt.", file=sys.stderr)
        return 1
    if args.write_report and not root.is_relative_to(SCRIPT_DIR):
        print("Validierung abgebrochen: Berichte dürfen nur im Texturordner liegen.", file=sys.stderr)
        return 1
    material_paths = sorted(root.glob("*/*.json"))
    audit.check(len(material_paths) == 13, "library", "Expected exactly 13 material metadata files.")
    for path in material_paths:
        checked_path = relative_path(root, path.relative_to(root).as_posix(), audit, "library")
        if checked_path is not None:
            validate_material(checked_path, root, args.expected_resolution, audit)
    ids = [material["material_id"] for material in audit.materials]
    audit.check(len(ids) == len(set(ids)), "library", "Material IDs must be unique.")
    validate_manifest(root, audit)
    report = audit.result()
    if args.write_report:
        report_path = root / "validation.json"
        if not report_path.resolve().is_relative_to(SCRIPT_DIR) or report_path.is_symlink():
            print("Validierung abgebrochen: Unsicheres Berichtsziel.", file=sys.stderr)
            return 1
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if report["passed"]:
        print(f"Validierung bestanden: {len(audit.materials)} Materialien, {audit.manifest.get('file_count', 0)} Dateien.")
        return 0
    print(f"Validierung fehlgeschlagen: {len(audit.errors)} Befunde.", file=sys.stderr)
    for error in audit.errors:
        print(f"- {error['location']}: {error['message']}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
