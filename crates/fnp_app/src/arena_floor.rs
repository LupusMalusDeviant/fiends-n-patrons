//! Compose the seed-generated room floor into one GPU texture at asset load.
//! Every source is a 96 × 96 RGBA thumbnail derived from the authored 2D art.
//! Normal and ORM remain neutral until proper PBR maps are authored.

use fnp_game::worldgen::{FLOOR_SIDE, RoomFloor};
use grimoire::RenderAssets;
use grimoire::render::{TextureColorSpace, TextureData, TextureError, TextureHandle};

const TILE_SIDE: usize = 96;
const TILE_BYTES: usize = TILE_SIDE * TILE_SIDE * 4;
const SIDE: u32 = (FLOOR_SIDE * TILE_SIDE) as u32;

// The order matches worldgen::TileId and tiles/catalog.json. The offline asset
// builder checks source hashes; the runtime never needs a PNG decoder.
const TILES: [&[u8; TILE_BYTES]; 20] = [
    include_bytes!("../assets/arena_floor/tiles/stone_ornate_intact.rgba"),
    include_bytes!("../assets/arena_floor/tiles/stone_ornate_cracked.rgba"),
    include_bytes!("../assets/arena_floor/tiles/stone_ornate_shattered.rgba"),
    include_bytes!("../assets/arena_floor/tiles/stone_plain.rgba"),
    include_bytes!("../assets/arena_floor/tiles/stone_mossy.rgba"),
    include_bytes!("../assets/arena_floor/tiles/wood_oak.rgba"),
    include_bytes!("../assets/arena_floor/tiles/wood_rotted.rgba"),
    include_bytes!("../assets/arena_floor/tiles/wood_charred.rgba"),
    include_bytes!("../assets/arena_floor/tiles/iron_rusted.rgba"),
    include_bytes!("../assets/arena_floor/tiles/iron_clockwork.rgba"),
    include_bytes!("../assets/arena_floor/tiles/earth_dry.rgba"),
    include_bytes!("../assets/arena_floor/tiles/earth_wet.rgba"),
    include_bytes!("../assets/arena_floor/tiles/bone_gravel.rgba"),
    include_bytes!("../assets/arena_floor/tiles/ash_burned.rgba"),
    include_bytes!("../assets/arena_floor/tiles/edge_stone_wood.rgba"),
    include_bytes!("../assets/arena_floor/tiles/edge_stone_earth.rgba"),
    include_bytes!("../assets/arena_floor/tiles/edge_stone_iron.rgba"),
    include_bytes!("../assets/arena_floor/tiles/edge_wood_earth.rgba"),
    include_bytes!("../assets/arena_floor/tiles/edge_iron_ash.rgba"),
    include_bytes!("../assets/arena_floor/tiles/edge_stone_bone.rgba"),
];

/// Bake one logical tile grid to an sRGB RGBA image. This runs once at load,
/// preserving a single floor draw call during gameplay.
fn compose(floor: &RoomFloor) -> Vec<u8> {
    let side = SIDE as usize;
    let mut pixels = vec![255_u8; side * side * 4];
    for (index, cell) in floor.tiles.iter().enumerate() {
        let row = index / FLOOR_SIDE;
        let col = index % FLOOR_SIDE;
        let tile = TILES[cell.id as usize];
        for y in 0..TILE_SIDE {
            let dst = ((row * TILE_SIDE + y) * side + col * TILE_SIDE) * 4;
            if cell.turns == 0 {
                let src = y * TILE_SIDE * 4;
                pixels[dst..dst + TILE_SIDE * 4].copy_from_slice(&tile[src..src + TILE_SIDE * 4]);
            } else {
                // Straight material boundaries only need a half turn today.
                debug_assert_eq!(cell.turns, 2);
                for x in 0..TILE_SIDE {
                    let src = ((TILE_SIDE - 1 - y) * TILE_SIDE + TILE_SIDE - 1 - x) * 4;
                    let out = dst + x * 4;
                    pixels[out..out + 4].copy_from_slice(&tile[src..src + 4]);
                }
            }
        }
    }
    pixels
}

/// Register the generated colour (sRGB), flat normal and provisional ORM maps.
///
/// # Errors
/// Forwards a texture registration failure, including software and hardware renderer errors.
pub fn register(
    assets: &mut dyn RenderAssets,
    floor: &RoomFloor,
) -> Result<[TextureHandle; 3], TextureError> {
    Ok([
        assets.register_texture(TextureData {
            width: SIDE,
            height: SIDE,
            pixels: compose(floor),
            color_space: TextureColorSpace::Srgb,
        })?,
        assets.register_texture(TextureData {
            width: 1,
            height: 1,
            pixels: vec![128, 128, 255, 255],
            color_space: TextureColorSpace::Linear,
        })?,
        assets.register_texture(TextureData {
            width: 1,
            height: 1,
            pixels: vec![255, 221, 0, 255],
            color_space: TextureColorSpace::Linear,
        })?,
    ])
}

#[cfg(test)]
mod tests {
    use fnp_game::worldgen::{ArenaDistrict, generate_floor};

    use super::*;

    #[test]
    fn two_room_seeds_make_different_valid_colour_images() {
        let a = compose(&generate_floor(12, ArenaDistrict::Crypt));
        let b = compose(&generate_floor(13, ArenaDistrict::Crypt));
        assert_eq!(a.len(), SIDE as usize * SIDE as usize * 4);
        assert_ne!(a, b);
        assert!(a.as_chunks::<4>().0.iter().all(|pixel| pixel[3] == 255));
    }
}
