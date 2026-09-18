# Arena floor maps

`crypt_ornate_basecolor.rgba` is 512 × 512 RGBA8, downsampled from
`_showcase/From2DTO3D/level_ground_pbr/crypt_ornate_topdown_v1.png` with Pillow's Lanczos
filter and written as `Image.tobytes()` in row-major order. The top-down art was generated
from `_showcase/From2DTO3D/2D/NOT3D_RenderedYet/props/props__crypt_floor_tile_cluster.png`
using the built-in image generator. The executable embeds the raw colour image, so loading
a figure pack does not depend on the `_showcase` directory.

Base colour is sRGB. A neutral flat normal and uniform roughness (221/255),
AO = 1 and metallic = 0 are registered as linear 1-pixel textures at runtime.
The floor mesh repeats the image every 4 metres. The painted source contains some baked
lighting, so this is an art-matched provisional material, not a measured PBR scan.

The three `*_puddle*.rgba`/`void_ichor_puddle.rgba` files come from the matching
transparent `props__*.png` images in the project's 2D prop folder. They are
384 × 256 RGBA8. `arena_puddles.rs` turns alpha into a coarse silhouette mesh,
because the current Grimoire mesh pass ignores material alpha. Their original
alpha remains embedded for future use when transparent decals are supported.
