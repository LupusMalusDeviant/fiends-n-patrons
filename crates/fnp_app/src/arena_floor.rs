//! Compose the seed-generated room floor into one GPU texture at asset load.
//! Every source is a 96 × 96 RGBA thumbnail derived from the authored 2D art.
//! Normal and ORM remain neutral until proper PBR maps are authored.

use fnp_game::worldgen::{FLOOR_SIDE, RoomFloor, WORLD_SIDE, WorldPlan, WorldTile};
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

const PATCH_SAMPLES: usize = WORLD_PATCH_TILES + 2;

fn smoothstep(value: f32) -> f32 {
    let value = value.clamp(0.0, 1.0);
    value * value * (3.0 - 2.0 * value)
}

/// Return the lower tile centre and the weight of the upper centre along one
/// axis. The transition band is 0.6 m wide, shared by both sides of an edge.
fn axis_mix(position: f32) -> (isize, f32) {
    let between_centres = position - 0.5;
    let lower = between_centres.floor();
    let fraction = between_centres - lower;
    (lower as isize, smoothstep((fraction - 0.2) / 0.6))
}

/// Warp coordinates in world space so every chunk and patch sees the same
/// curved edge. The small second wave stops long boundaries looking sinusoidal.
fn curve_world_position(world_x: f32, world_y: f32, seed: u64) -> (f32, f32) {
    let phase = (seed % 997) as f32 * 0.019;
    let x = world_x
        + 0.28 * (world_y * 0.62 + phase).sin()
        + 0.06 * (world_y * 1.73 + world_x * 0.17 + phase).sin();
    let y = world_y
        + 0.28 * (world_x * 0.69 + phase * 1.9).sin()
        + 0.06 * (world_x * 1.49 + world_y * 0.21 + phase).sin();
    (x, y)
}

fn sample_world_pixel(
    samples: &[WorldTile],
    first: (usize, usize),
    tile: (usize, usize),
    pixel: (usize, usize),
    seed: u64,
) -> [u8; 3] {
    let (px, py) = pixel;
    let (warped_x, warped_y) = curve_world_position(
        (first.0 + tile.0) as f32 + (px as f32 + 0.5) / WORLD_PATCH_TILE_PIXELS as f32,
        (first.1 + tile.1) as f32 + (py as f32 + 0.5) / WORLD_PATCH_TILE_PIXELS as f32,
        seed,
    );
    let (left_world, east) = axis_mix(warped_x);
    let (bottom_world, north) = axis_mix(warped_y);
    let left = left_world - first.0 as isize;
    let bottom = bottom_world - first.1 as isize;
    let sx = px * TILE_SIDE / WORLD_PATCH_TILE_PIXELS + TILE_SIDE / WORLD_PATCH_TILE_PIXELS / 2;
    let sy = py * TILE_SIDE / WORLD_PATCH_TILE_PIXELS + TILE_SIDE / WORLD_PATCH_TILE_PIXELS / 2;
    let source = (sy * TILE_SIDE + sx) * 4;
    let mut color = [0.0_f32; 3];
    for (dy, wy) in [(0, 1.0 - north), (1, north)] {
        for (dx, wx) in [(0, 1.0 - east), (1, east)] {
            let cell =
                &samples[(bottom + dy + 1) as usize * PATCH_SAMPLES + (left + dx + 1) as usize];
            let texture = TILES[cell.visual.id as usize];
            for channel in 0..3 {
                color[channel] += f32::from(texture[source + channel]) * wx * wy;
            }
        }
    }
    color.map(|channel| channel.round().clamp(0.0, 255.0) as u8)
}

fn bake_world_puddles(plan: &WorldPlan, first: (usize, usize), pixels: &mut [u8]) {
    use crate::arena_puddles::{SOURCE_HEIGHT, SOURCE_WIDTH, pixels_for_kind};
    let side = SIDE as usize;
    let last_x = first.0 + WORLD_PATCH_TILES;
    let last_y = first.1 + WORLD_PATCH_TILES;
    for chunk_y in first.1 / 16..last_y.div_ceil(16) {
        for chunk_x in first.0 / 16..last_x.div_ceil(16) {
            let chunk = plan
                .chunk(chunk_x, chunk_y)
                .expect("patch chunks are in bounds");
            for puddle in chunk.puddles {
                let world_x_cm = i32::from(puddle.x_cm) + 12_800;
                let world_y_cm = i32::from(puddle.y_cm) + 12_800;
                let tile_x = world_x_cm.div_euclid(100) as usize;
                let tile_y = world_y_cm.div_euclid(100) as usize;
                if !(first.0..last_x).contains(&tile_x) || !(first.1..last_y).contains(&tile_y) {
                    continue;
                }
                let local_x = (tile_x - first.0) * WORLD_PATCH_TILE_PIXELS;
                let local_y = (tile_y - first.1) * WORLD_PATCH_TILE_PIXELS;
                let source = pixels_for_kind(puddle.kind);
                let centre_x =
                    (world_x_cm.rem_euclid(100) as usize * WORLD_PATCH_TILE_PIXELS) / 100;
                let centre_y =
                    (world_y_cm.rem_euclid(100) as usize * WORLD_PATCH_TILE_PIXELS) / 100;
                let width =
                    (usize::from(puddle.size_cm) * WORLD_PATCH_TILE_PIXELS * 3 / 200).max(1);
                let height = (usize::from(puddle.size_cm) * WORLD_PATCH_TILE_PIXELS / 100).max(1);
                for y in 0..WORLD_PATCH_TILE_PIXELS {
                    for x in 0..WORLD_PATCH_TILE_PIXELS {
                        let dx = x as isize - centre_x as isize + (width / 2) as isize;
                        let dy = y as isize - centre_y as isize + (height / 2) as isize;
                        if dx < 0 || dy < 0 || dx >= width as isize || dy >= height as isize {
                            continue;
                        }
                        let sx = dx as usize * SOURCE_WIDTH / width;
                        let sy = dy as usize * SOURCE_HEIGHT / height;
                        let src = (sy * SOURCE_WIDTH + sx) * 4;
                        let alpha = u16::from(source[src + 3]) * 3 / 4;
                        let dst = ((local_y + y) * side + local_x + x) * 4;
                        for channel in 0..3 {
                            pixels[dst + channel] = ((u16::from(pixels[dst + channel])
                                * (255 - alpha)
                                + u16::from(source[src + channel]) * alpha)
                                / 255) as u8;
                        }
                    }
                }
            }
        }
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
    let samples: Vec<_> = (0..PATCH_SAMPLES)
        .flat_map(|y| {
            (0..PATCH_SAMPLES).map(move |x| {
                plan.tile(
                    (first_x + x).saturating_sub(1).min(WORLD_SIDE - 1),
                    (first_y + y).saturating_sub(1).min(WORLD_SIDE - 1),
                )
                .expect("sampled world tile is in bounds")
            })
        })
        .collect();
    for tile_y in 0..WORLD_PATCH_TILES {
        for tile_x in 0..WORLD_PATCH_TILES {
            for py in 0..WORLD_PATCH_TILE_PIXELS {
                for px in 0..WORLD_PATCH_TILE_PIXELS {
                    let color = sample_world_pixel(
                        &samples,
                        (first_x, first_y),
                        (tile_x, tile_y),
                        (px, py),
                        plan.seed(),
                    );
                    let dst = ((tile_y * WORLD_PATCH_TILE_PIXELS + py) * side
                        + tile_x * WORLD_PATCH_TILE_PIXELS
                        + px)
                        * 4;
                    pixels[dst..dst + 3].copy_from_slice(&color);
                }
            }
        }
    }
    bake_world_puddles(plan, (first_x, first_y), &mut pixels);
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
    use fnp_game::worldgen::{ArenaDistrict, Terrain, TileId, TileInstance, generate_floor};

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

    #[test]
    fn three_foreign_edges_and_diagonal_corner_share_one_texture() {
        let plain = WorldTile {
            visual: TileInstance {
                id: TileId::StonePlain,
                turns: 0,
            },
            terrain: Terrain::Stone,
            adjacent: [Terrain::Stone; 4],
        };
        let mut mixed = vec![plain; PATCH_SAMPLES * PATCH_SAMPLES];
        let center = 25 * PATCH_SAMPLES + 25;
        mixed[center + PATCH_SAMPLES].visual.id = TileId::WoodOak;
        mixed[center + 1].visual.id = TileId::EarthDry;
        mixed[center - PATCH_SAMPLES].visual.id = TileId::IronRusted;
        mixed[center + PATCH_SAMPLES + 1].visual.id = TileId::BoneGravel;
        let flat = vec![plain; PATCH_SAMPLES * PATCH_SAMPLES];
        let pixel = |samples: &[WorldTile], x, y| {
            sample_world_pixel(samples, (10, 5), (24, 24), (x, y), 41)
        };
        assert_ne!(pixel(&flat, 12, 23), pixel(&mixed, 12, 23),);
        assert_ne!(pixel(&flat, 23, 12), pixel(&mixed, 23, 12));
        assert_ne!(pixel(&flat, 12, 0), pixel(&mixed, 12, 0));
        assert_ne!(pixel(&flat, 23, 23), pixel(&mixed, 23, 23));
        assert_eq!(pixel(&flat, 0, 12), pixel(&mixed, 0, 12));
    }

    #[test]
    fn curvature_varies_along_an_edge_without_a_tile_seam() {
        let offsets: Vec<_> = (0..20)
            .map(|row| curve_world_position(10.0, row as f32, 41).0)
            .collect();
        let span = offsets.iter().copied().fold(f32::NEG_INFINITY, f32::max)
            - offsets.iter().copied().fold(f32::INFINITY, f32::min);
        assert!(span > 0.2);
        let (_, before) = axis_mix(10.0 - 0.001);
        let (_, after) = axis_mix(10.0 + 0.001);
        assert!((before - after).abs() < 0.01);
    }

    #[test]
    fn overlapping_world_patches_have_identical_pixels() {
        let plan = WorldPlan::new(41, ArenaDistrict::Crypt);
        let left = compose_world_patch(&plan, (100, 128));
        let right = compose_world_patch(&plan, (101, 128));
        let side = SIDE as usize;
        for row in 0..side {
            let left_start = (row * side + WORLD_PATCH_TILE_PIXELS) * 4;
            let right_start = row * side * 4;
            let shared = (side - WORLD_PATCH_TILE_PIXELS) * 4;
            for index in 0..shared {
                assert_eq!(
                    left[left_start + index],
                    right[right_start + index],
                    "patch seam at row {row}, byte {index}"
                );
            }
        }
    }

    /// Artist-facing CPU export of exactly the colour texture registered by the game.
    #[test]
    #[ignore = "set FNP_FLOOR_EXPORT_PPM to an output path"]
    fn export_curved_world_floor() {
        let Some(path) = std::env::var_os("FNP_FLOOR_EXPORT_PPM") else {
            return;
        };
        let pixels = compose_world_patch(&WorldPlan::new(41, ArenaDistrict::Crypt), (108, 128));
        let mut ppm = format!("P6\n{SIDE} {SIDE}\n255\n").into_bytes();
        for rgba in pixels.as_chunks::<4>().0 {
            ppm.extend_from_slice(&rgba[..3]);
        }
        std::fs::write(path, ppm).expect("write the floor preview");
    }
}
