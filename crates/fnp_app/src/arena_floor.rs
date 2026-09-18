//! Three seeded arena districts baked from the project's 20 authored floor modules.
//! The offline builder and the downsampled source tiles are included with the app.
//! A neutral normal/ORM map is provisional until measured PBR maps exist.

use fnp_game::arena::present::ArenaDistrict;
use grimoire::RenderAssets;
use grimoire::render::{TextureColorSpace, TextureData, TextureError, TextureHandle};

const SIDE: u32 = 1152;
const CRYPT: &[u8; (SIDE * SIDE * 4) as usize] =
    include_bytes!("../assets/arena_floor/arena_crypt.rgba");
const FOUNDRY: &[u8; (SIDE * SIDE * 4) as usize] =
    include_bytes!("../assets/arena_floor/arena_foundry.rgba");
const OSSUARY: &[u8; (SIDE * SIDE * 4) as usize] =
    include_bytes!("../assets/arena_floor/arena_ossuary.rgba");

/// Registers the base colour (sRGB), normal and ORM maps (linear) in that order.
///
/// # Errors
/// Forwards a texture registration failure, including software and hardware renderer errors.
pub fn register(
    assets: &mut dyn RenderAssets,
    district: ArenaDistrict,
) -> Result<[TextureHandle; 3], TextureError> {
    let base = match district {
        ArenaDistrict::Crypt => CRYPT,
        ArenaDistrict::Foundry => FOUNDRY,
        ArenaDistrict::Ossuary => OSSUARY,
    };
    Ok([
        assets.register_texture(TextureData {
            width: SIDE,
            height: SIDE,
            pixels: base.to_vec(),
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
