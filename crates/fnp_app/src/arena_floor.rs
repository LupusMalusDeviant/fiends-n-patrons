//! Bundled ornate crypt slabs matching the project's illustrated floor cluster.
//! The source art is perspective concept art; its top-down companion is kept in
//! `_showcase/From2DTO3D/level_ground_pbr/crypt_ornate_topdown_v1.png`.
//! The colour image is embedded as raw RGBA and a neutral normal/rough stone ORM
//! map leaves the painted highlights alone until measured height maps exist.

use grimoire::RenderAssets;
use grimoire::render::{TextureColorSpace, TextureData, TextureError, TextureHandle};

const SIDE: u32 = 512;
const BASE: &[u8; (SIDE * SIDE * 4) as usize] =
    include_bytes!("../assets/arena_floor/crypt_ornate_basecolor.rgba");

/// Registers the base colour (sRGB), normal and ORM maps (linear) in that order.
///
/// # Errors
/// Forwards a texture registration failure, including software and hardware renderer errors.
pub fn register(assets: &mut dyn RenderAssets) -> Result<[TextureHandle; 3], TextureError> {
    Ok([
        assets.register_texture(TextureData {
            width: SIDE,
            height: SIDE,
            pixels: BASE.to_vec(),
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
