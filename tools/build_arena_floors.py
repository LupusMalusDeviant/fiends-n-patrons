"""Bake three seeded 48 m arena districts from the 20 catalogued floor modules.

Run from anywhere with ``python tools/build_arena_floors.py``. Source thumbnails and
the logical-socket catalog are checked in; this does not require the 1254 px
concept originals, network access, Blender, or a GPU.
"""

from __future__ import annotations

import json
import hashlib
import random
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "crates/fnp_app/assets/arena_floor"
CATALOG = json.loads((ART / "tiles/catalog.json").read_text(encoding="utf-8"))
TILES = {tile["id"]: tile for tile in CATALOG["tiles"]}
SIDE = 12
PIXELS_PER_TILE = 96
SEED = 260918

# Every vertical band keeps one edge profile from its top to bottom. This is
# deliberate: the concept set has straight joins but no corner or T pieces.
# A band is either one transition module or a terrain with weighted variants.
DISTRICTS = {
    "crypt": ["stone"] * 4 + [("edge_stone_wood", 0)] + ["wood"]
    + [("edge_wood_earth", 0)] + ["earth"] * 5,
    "foundry": ["stone"] * 4 + [("edge_stone_iron", 0)] + ["iron"]
    + [("edge_iron_ash", 0)] + ["ash"] * 5,
    "ossuary": ["earth"] * 4 + [("edge_stone_earth", 2)] + ["stone"]
    + [("edge_stone_bone", 0)] + ["bone"] * 5,
}


def turn_edges(edges: dict[str, list[str]]) -> dict[str, list[str]]:
    """Rotate one clockwise quarter turn, preserving ordered half-edge labels."""
    return {
        "N": edges["W"][:],
        "E": edges["N"][:],
        "S": list(reversed(edges["E"])),
        "W": list(reversed(edges["S"])),
    }


def oriented_edges(tile_id: str, turns: int) -> dict[str, list[str]]:
    edges = TILES[tile_id]["edges"]
    for _ in range(turns):
        edges = turn_edges(edges)
    return edges


def generate(district: str, bands: list[str | tuple[str, int]]) -> dict:
    assert len(bands) == SIDE
    rng = random.Random(SEED + list(DISTRICTS).index(district))
    base_by_terrain: dict[str, list[dict]] = {}
    for tile in CATALOG["tiles"]:
        if tile["kind"] == "base":
            base_by_terrain.setdefault(tile["terrain"], []).append(tile)

    canvas = Image.new("RGB", (SIDE * PIXELS_PER_TILE,) * 2)
    cells = []
    for row in range(SIDE):
        line = []
        for col, band in enumerate(bands):
            if isinstance(band, tuple):
                tile_id, turns = band
            else:
                options = base_by_terrain[band]
                selected = rng.choices(options, weights=[t["spawnWeight"] for t in options])[0]
                tile_id, turns = selected["id"], 0
            tile = TILES[tile_id]
            assert turns in tile["rotations"], (tile_id, turns)
            line.append({"id": tile_id, "turnsClockwise": turns})
            image = Image.open(ART / "tiles" / tile["image"]).convert("RGB")
            if turns:
                image = image.rotate(-90 * turns, expand=True)
            image = image.resize((PIXELS_PER_TILE,) * 2, Image.Resampling.LANCZOS)
            canvas.paste(image, (col * PIXELS_PER_TILE, row * PIXELS_PER_TILE))
        cells.append(line)

    for row in range(SIDE):
        for col in range(SIDE):
            here = cells[row][col]
            edges = oriented_edges(here["id"], here["turnsClockwise"])
            if col + 1 < SIDE:
                other = cells[row][col + 1]
                assert edges["E"] == oriented_edges(other["id"], other["turnsClockwise"])["W"], (
                    district, row, col, "E", here, other
                )
            if row + 1 < SIDE:
                other = cells[row + 1][col]
                assert edges["S"] == oriented_edges(other["id"], other["turnsClockwise"])["N"], (
                    district, row, col, "S", here, other
                )

    canvas.save(ART / f"arena_{district}.png")
    (ART / f"arena_{district}.rgba").write_bytes(canvas.convert("RGBA").tobytes())
    return {"id": district, "seed": SEED + list(DISTRICTS).index(district), "grid": cells}


def main() -> None:
    assert CATALOG["tileSizeM"] == 4.0
    assert len(TILES) == 20
    for tile in TILES.values():
        path = ART / "tiles" / tile["image"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == tile["sha256"], path
        with Image.open(path) as image:
            assert image.size == (128, 128), path
    layouts = [generate(name, bands) for name, bands in DISTRICTS.items()]
    used = {cell["id"] for layout in layouts for line in layout["grid"] for cell in line}
    assert used == set(TILES), f"unused tiles: {set(TILES) - used}"
    (ART / "arena_layouts.json").write_text(
        json.dumps({"schemaVersion": 1, "tileSizeM": 4.0, "gridSide": SIDE,
                    "seed": SEED, "districts": layouts}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Baked {len(layouts)} 48 m districts, {len(used)} tiles used, all 792 neighbor joins valid")


if __name__ == "__main__":
    main()
