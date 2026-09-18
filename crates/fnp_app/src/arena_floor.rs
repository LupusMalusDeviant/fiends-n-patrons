//! Compose the seed-generated room floor into one GPU texture at asset load.
//! Every source is a 96 × 96 RGBA thumbnail derived from the authored 2D art.
//! Normal and ORM remain neutral until proper PBR maps are authored.

use fnp_game::worldgen::{FLOOR_SIDE, RoomFloor, Terrain, WORLD_SIDE, WorldPlan};
use grimoire::RenderAssets;
use grimoire::render::{TextureColorSpace, TextureData, TextureError, TextureHandle};

const TILE_SIDE: usize = 96;
const TILE_BYTES: usize = TILE_SIDE * TILE_SIDE * 4;
const SIDE: u32 = (FLOOR_SIDE * TILE_SIDE) as u32;
const WORLD_PATCH_TILES: usize = 48;
const WORLD_PATCH_TILE_PIXELS: usize = SIDE as usize / WORLD_PATCH_TILES;

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

fn representative(terrain: Terrain) -> usize {
    match terrain {
        Terrain::Stone => 3,
        Terrain::Wood => 5,
        Terrain::Iron => 8,
        Terrain::Earth => 10,
        Terrain::Bone => 12,
        Terrain::Ash => 13,
    }
}

/// The engine's present floor is 48 m wide. For a software preview, show a
/// selected 48 × 48 one-metre patch from the full generated 256 m map. The 16 m
/// generation chunks never appear as visual boundaries in this texture.
fn compose_world_patch(plan: &WorldPlan, center: (usize, usize)) -> Vec<u8> {
    let side = SIDE as usize;
    let mut pixels = vec![255_u8; side * side * 4];
    let half = WORLD_PATCH_TILES / 2;
    let first_x = center.0.clamp(half, WORLD_SIDE - half) - half;
    let first_y = center.1.clamp(half, WORLD_SIDE - half) - half;
    let sample_step = TILE_SIDE / WORLD_PATCH_TILE_PIXELS;
    for tile_y in 0..WORLD_PATCH_TILES {
        for tile_x in 0..WORLD_PATCH_TILES {
            let cell = plan
                .tile(first_x + tile_x, first_y + tile_y)
                .expect("the central patch is inside the world");
            for py in 0..WORLD_PATCH_TILE_PIXELS {
                for px in 0..WORLD_PATCH_TILE_PIXELS {
                    let source_x = px * sample_step + sample_step / 2;
                    let source_y = py * sample_step + sample_step / 2;
                    let src = (source_y * TILE_SIDE + source_x) * 4;
                    let base = TILES[cell.visual.id as usize];
                    let mut color = [base[src], base[src + 1], base[src + 2]];
                    // Blend a few pixels across organic region boundaries.
                    // A 50/50 border on both sides avoids a hard square edge;
                    // production art can later replace this provisional blend.
                    let sides = [
                        (cell.adjacent[0], WORLD_PATCH_TILE_PIXELS - 1 - py),
                        (cell.adjacent[1], WORLD_PATCH_TILE_PIXELS - 1 - px),
                        (cell.adjacent[2], py),
                        (cell.adjacent[3], px),
                    ];
                    for (terrain, distance) in sides {
                        if terrain == cell.terrain || distance >= 4 {
                            continue;
                        }
                        let other = TILES[representative(terrain)];
                        let alpha = (4 - distance) as u16 * 32;
                        for channel in 0..3 {
                            color[channel] = ((u16::from(color[channel]) * (256 - alpha)
                                + u16::from(other[src + channel]) * alpha)
                                / 256) as u8;
                        }
                    }
                    let dst = ((tile_y * WORLD_PATCH_TILE_PIXELS + py) * side
                        + tile_x * WORLD_PATCH_TILE_PIXELS
                        + px)
                        * 4;
                    pixels[dst..dst + 3].copy_from_slice(&color);
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
    register_pixels(assets, compose(floor))
}

/// Register a selected patch of a generated 256 m world for an offscreen
/// perspective preview through the game's existing 48 m floor mesh.
///
/// # Errors
/// Forwards a texture registration failure.
pub fn register_world_patch(
    assets: &mut dyn RenderAssets,
    plan: &WorldPlan,
    center: (usize, usize),
) -> Result<[TextureHandle; 3], TextureError> {
    register_pixels(assets, compose_world_patch(plan, center))
}

fn register_pixels(
    assets: &mut dyn RenderAssets,
    pixels: Vec<u8>,
) -> Result<[TextureHandle; 3], TextureError> {
    Ok([
        assets.register_texture(TextureData {
            width: SIDE,
            height: SIDE,
            pixels,
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

    #[test]
    fn central_world_patch_fits_the_existing_floor_mesh() {
        assert_eq!(WORLD_PATCH_TILES * WORLD_PATCH_TILE_PIXELS, SIDE as usize);
        let first = compose_world_patch(&WorldPlan::new(41, ArenaDistrict::Crypt), (100, 128));
        let second = compose_world_patch(&WorldPlan::new(42, ArenaDistrict::Crypt), (100, 128));
        assert_eq!(first.len(), SIDE as usize * SIDE as usize * 4);
        assert_ne!(first, second);
    }
}
