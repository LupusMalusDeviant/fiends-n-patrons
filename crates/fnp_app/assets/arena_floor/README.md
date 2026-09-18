# Arena floor maps

The three raw 256 × 256 RGBA8 files come from the project's
`_showcase/From2DTO3D/level_ground_pbr/generated/flagstone_cracked_{basecolor,normal,orm}.png`
(1024 × 1024 originals). They were converted to RGBA and resized with Pillow's Lanczos
filter, then written as `Image.tobytes()` in row-major order. The source images were
generated for this project. The executable embeds these bytes, so loading a figure pack
does not depend on the `_showcase` directory.

Base colour is sRGB. Normal and ORM are linear; ORM means R = ambient occlusion,
G = roughness, B = metallic. The floor mesh repeats the maps every 4 metres.
