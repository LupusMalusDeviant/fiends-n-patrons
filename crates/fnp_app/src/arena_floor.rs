//! Bundled cracked-stone PBR patch for the arena floor. The 256 px RGBA data was
//! downsampled from `_showcase/From2DTO3D/level_ground_pbr/generated/flagstone_cracked_*`.
//! It is stored uncompressed in the executable so no image decoder or external asset path
//! is required at startup. Registration happens once through the renderer asset hook.

use grimoire::RenderAssets;
use grimoire::render::{TextureColorSpace, TextureData, TextureError, TextureHandle};

const SIDE: u32 = 256;
const BASE: &[u8; (SIDE * SIDE * 4) as usize] =
    include_bytes!("../assets/arena_floor/flagstone_cracked_basecolor.rgba");
const NORMAL: &[u8; (SIDE * SIDE * 4) as usize] =
    include_bytes!("../assets/arena_floor/flagstone_cracked_normal.rgba");
const ORM: &[u8; (SIDE * SIDE * 4) as usize] =
    include_bytes!("../assets/arena_floor/flagstone_cracked_orm.rgba");

/// Registers the base colour (sRGB), normal and ORM maps (linear) in that order.
///
/// # Errors
/// Forwards a texture registration failure, including software and hardware renderer errors.
pub fn register(assets: &mut dyn RenderAssets) -> Result<[TextureHandle; 3], TextureError> {
    let texture = |pixels: &[u8], color_space| TextureData {
        width: SIDE,
        height: SIDE,
        pixels: pixels.to_vec(),
        color_space,
    };
    Ok([
        assets.register_texture(texture(BASE, TextureColorSpace::Srgb))?,
        assets.register_texture(texture(NORMAL, TextureColorSpace::Linear))?,
        assets.register_texture(texture(ORM, TextureColorSpace::Linear))?,
    ])
}
