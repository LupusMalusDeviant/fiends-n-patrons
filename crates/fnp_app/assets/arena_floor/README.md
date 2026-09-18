# Arena floor districts

The game generates a 12 × 12 grid of 4 m modules for the first room at startup.
Its floor and ten puddle placements are pure functions of `--seed`. The first
biome comes from the run's three-stage plan; `FNP_ARENA_DISTRICT=crypt|foundry|ossuary`
overrides it for art review. `arena_floor.rs` assembles the selected room into
one 1152 × 1152 RGBA8 colour texture before registering it with the renderer.
The playable combat area remains 21 × 14 m within the 48 × 48 m floor.

`tiles/` contains all 20 downsampled concept modules, their raw runtime copies
and the logical socket catalog. Run `python tools/build_arena_floors.py` from
the repository root to rebuild raw tiles and three **review-only** PNG examples.
The included `arena_layouts.json` records these examples, not the room generated
by a given run seed. The builder rejects mismatched example sockets and ensures
all 20 motifs appear across those examples.
The original 1254 px generated art remains in
`_showcase/From2DTO3D/level_ground_pbr/procedural_v1/` outside this checkout.

These are colour concepts, not measured PBR scans. Normal and ORM maps remain
neutral; some painted tile seams are visible. The catalog currently supplies
only straight transitions. Corner and T-junction art is needed before freeform
biome boundaries can be generated.

The three `*_puddle*.rgba`/`void_ichor_puddle.rgba` images come from the
transparent 2D prop art. They are 384 × 256 RGBA8. `arena_puddles.rs` turns
alpha into a coarse silhouette mesh because the current Grimoire mesh pass
ignores material alpha. `worldgen::generate_floor` supplies ten visual-only
placements inside the curbs. `worldgen::generate_run` plans three linear stages
with 5–8 rooms each; room traversal and changing the current floor after a
clear are not yet connected to the combat prototype.
