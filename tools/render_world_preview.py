"""Render a world_map .fmap export from the actual one-metre floor art on CPU.

Example:
  cargo run -p fnp_game --example world_map -- 41 crypt map.fmap
  python tools/render_world_preview.py map.fmap map.png --puddles path/to/props
"""

from __future__ import annotations

import argparse
import struct
from functools import lru_cache
from pathlib import Path

from PIL import Image

SIDE = 256
PIXELS_PER_METRE = 16
ART = Path(__file__).resolve().parents[1] / "crates/fnp_app/assets/arena_floor/tiles"
TILE_NAMES = (
    "stone_ornate_intact", "stone_ornate_cracked", "stone_ornate_shattered",
    "stone_plain", "stone_mossy", "wood_oak", "wood_rotted", "wood_charred",
    "iron_rusted", "iron_clockwork", "earth_dry", "earth_wet",
    "bone_gravel", "ash_burned",
)
TERRAIN_BY_TILE = (0, 0, 0, 0, 0, 1, 1, 1, 2, 2, 3, 3, 4, 5)
REPRESENTATIVE = (3, 5, 8, 10, 12, 13)
PUDDLE_NAMES = (
    "props__blood_puddle_fresh.png",
    "props__plague_bile_puddle.png",
    "props__void_ichor_puddle.png",
)


def load_map(path: Path) -> tuple[bytes, list[tuple[int, int, int, int]]]:
    raw = path.read_bytes()
    if raw[:8] != b"FNPMAP1\0":
        raise ValueError("This is not a world_map .fmap export")
    tiles = raw[8:8 + SIDE * SIDE]
    if len(tiles) != SIDE * SIDE or any(tile >= len(TILE_NAMES) for tile in tiles):
        raise ValueError("Invalid tile grid")
    count = struct.unpack_from("<I", raw, 8 + SIDE * SIDE)[0]
    start = 12 + SIDE * SIDE
    if len(raw) != start + count * 7:
        raise ValueError("Invalid puddle records")
    puddles = list(struct.iter_unpack("<BhhH", raw[start:]))
    return tiles, puddles


def render(
    tiles: bytes, puddles: list[tuple[int, int, int, int]], props: Path | None
) -> tuple[Image.Image, Image.Image]:
    size = PIXELS_PER_METRE
    art = [Image.open(ART / f"{name}.png").convert("RGB").resize(
        (size, size), Image.Resampling.LANCZOS) for name in TILE_NAMES]
    image = Image.new("RGB", (SIDE * size, SIDE * size))
    masks = []
    for side in range(4):  # north, east, south, west
        mask = Image.new("L", (size, size))
        pix = mask.load()
        for y in range(size):
            for x in range(size):
                distance = (y, size - 1 - x, size - 1 - y, x)[side]
                pix[x, y] = max(0, 128 - distance * 32)
        masks.append(mask)

    @lru_cache(maxsize=4096)
    def tile_image(tile_id: int, neighbors: tuple[int, int, int, int]) -> Image.Image:
        own = TERRAIN_BY_TILE[tile_id]
        result = art[tile_id].copy()
        for side, terrain in enumerate(neighbors):
            if terrain != own:
                result = Image.composite(art[REPRESENTATIVE[terrain]], result, masks[side])
        return result

    for y in range(SIDE):
        for x in range(SIDE):
            index = y * SIDE + x
            own = TERRAIN_BY_TILE[tiles[index]]
            neighbors = (
                TERRAIN_BY_TILE[tiles[index + SIDE]] if y + 1 < SIDE else own,
                TERRAIN_BY_TILE[tiles[index + 1]] if x + 1 < SIDE else own,
                TERRAIN_BY_TILE[tiles[index - SIDE]] if y else own,
                TERRAIN_BY_TILE[tiles[index - 1]] if x else own,
            )
            image.paste(tile_image(tiles[index], neighbors), (x * size, (SIDE - y - 1) * size))

    floor_only = image.copy()
    if props is not None:
        originals = [Image.open(props / name).convert("RGBA") for name in PUDDLE_NAMES]

        @lru_cache(maxsize=200)
        def puddle_sprite(kind: int, diameter: int) -> Image.Image:
            source = originals[kind]
            height = max(2, round(diameter * source.height / source.width))
            sprite = source.resize((diameter, height), Image.Resampling.LANCZOS)
            sprite.putalpha(sprite.getchannel("A").point(lambda alpha: round(alpha * 0.68)))
            return sprite

        for kind, x_cm, y_cm, scale_cm in puddles:
            diameter = max(6, round(scale_cm / 100 * size * 1.3))
            sprite = puddle_sprite(kind, diameter)
            x = round((x_cm / 100 + SIDE / 2) * size - sprite.width / 2)
            y = round((SIDE / 2 - y_cm / 100) * size - sprite.height / 2)
            image.paste(sprite, (x, y), sprite)
    return image, floor_only


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--puddles", type=Path, help="directory with the three authored puddle PNGs")
    args = parser.parse_args()
    tiles, puddles = load_map(args.map)
    image, floor_only = render(tiles, puddles, args.puddles)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output, optimize=True)

    # Sub-metre puddles become tiny angular marks when the whole world is
    # reduced to 1280 px. Keep the overview readable; show decals in the crop.
    overview = floor_only.resize((1280, 1280), Image.Resampling.LANCZOS)
    overview.save(args.output.with_name(args.output.stem + "_overview.png"), optimize=True)
    center = 128 * PIXELS_PER_METRE
    detail = image.crop((center - 512, center - 512, center + 512, center + 512))
    detail.save(args.output.with_name(args.output.stem + "_detail.png"), optimize=True)
    print(f"Rendered {SIDE} x {SIDE} one-metre tiles and {len(puddles)} puddles: {args.output}")


if __name__ == "__main__":
    main()
