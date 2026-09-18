# Arena floor districts

`arena_crypt.rgba`, `arena_foundry.rgba`, and `arena_ossuary.rgba` are baked
1152 × 1152 RGBA8 textures for the 48 × 48 m first-room arena. Each holds a
12 × 12 grid of 4 m modules. `FNP_ARENA_DISTRICT=crypt|foundry|ossuary`
selects the district at startup; `crypt` is the default. The same names have
PNG previews. `arena_layouts.json` records every chosen module and rotation.

`tiles/` contains all 20 downsampled concept modules and their logical socket
catalog. Run `python tools/build_arena_floors.py` from the repository root to
rebuild the district textures from a fixed seed. The builder rejects mismatched
neighbor sockets and ensures all 20 modules are used across the three districts.
The original 1254 px generated art remains in
`_showcase/From2DTO3D/level_ground_pbr/procedural_v1/` outside this checkout.

These are colour concepts, not measured PBR scans. Normal and ORM maps remain
neutral; some painted tile seams are visible. The catalog currently supplies
only straight transitions. Corner and T-junction art is needed before freeform
biome boundaries can be generated.

The three `*_puddle*.rgba`/`void_ichor_puddle.rgba` images come from the
transparent 2D prop art. They are 384 × 256 RGBA8. `arena_puddles.rs` turns
alpha into a coarse silhouette mesh because the current Grimoire mesh pass
ignores material alpha. `ArenaDistrict` supplies ten visual-only placements
per district inside the arena curbs.
