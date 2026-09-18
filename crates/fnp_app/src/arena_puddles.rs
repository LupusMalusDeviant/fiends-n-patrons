//! Flat colour decals cut to the alpha silhouette of the three existing puddle images.
//! Grimoire 0.6 draws mesh materials opaquely even with `AlphaMode::Blend`, so a full
//! textured rectangle would paint black over the stone. Each occupied mask cell becomes
//! two triangles; no render-time transparency or geometry generation is needed.

use grimoire::RenderAssets;
use grimoire::render::{
    MeshData, MeshError, MeshHandle, MeshVertex, TextureColorSpace, TextureData, TextureError,
    TextureHandle,
};

const WIDTH: usize = 384;
const HEIGHT: usize = 256;
const COLS: usize = 48;
const ROWS: usize = 32;
const ALPHA_CUTOFF: u8 = 128;
const BLOOD: &[u8; WIDTH * HEIGHT * 4] =
    include_bytes!("../assets/arena_floor/blood_puddle_fresh.rgba");
const PLAGUE: &[u8; WIDTH * HEIGHT * 4] =
    include_bytes!("../assets/arena_floor/plague_bile_puddle.rgba");
const VOID: &[u8; WIDTH * HEIGHT * 4] =
    include_bytes!("../assets/arena_floor/void_ichor_puddle.rgba");

pub(crate) const SOURCE_WIDTH: usize = WIDTH;
pub(crate) const SOURCE_HEIGHT: usize = HEIGHT;

pub(crate) fn pixels_for_kind(kind: u8) -> &'static [u8] {
    match kind {
        0 => BLOOD,
        1 => PLAGUE,
        _ => VOID,
    }
}

/// Registered mesh and base colour for one puddle species.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PuddleHandles {
    /// Registered cutout mesh.
    pub mesh: MeshHandle,
    /// Registered sRGB colour map.
    pub base_color: TextureHandle,
}

/// Registration errors retain which part of the decal could not be uploaded.
#[derive(Debug)]
pub enum PuddleError {
    /// The alpha silhouette could not be registered as a mesh.
    Mesh(MeshError),
    /// The colour image could not be registered as a texture.
    Texture(TextureError),
}

impl std::fmt::Display for PuddleError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Mesh(error) => write!(f, "puddle mesh: {error}"),
            Self::Texture(error) => write!(f, "puddle colour: {error}"),
        }
    }
}

impl std::error::Error for PuddleError {}

/// Three puddles in blood, plague and void order.
///
/// # Errors
/// Returns a mesh or texture registration failure.
pub fn register(assets: &mut dyn RenderAssets) -> Result<[PuddleHandles; 3], PuddleError> {
    let mut register_one = |pixels: &[u8]| -> Result<PuddleHandles, PuddleError> {
        let mesh = assets
            .register_mesh(silhouette_mesh(pixels))
            .map_err(PuddleError::Mesh)?;
        let base_color = assets
            .register_texture(TextureData {
                width: WIDTH as u32,
                height: HEIGHT as u32,
                pixels: pixels.to_vec(),
                color_space: TextureColorSpace::Srgb,
            })
            .map_err(PuddleError::Texture)?;
        Ok(PuddleHandles { mesh, base_color })
    };
    Ok([
        register_one(BLOOD)?,
        register_one(PLAGUE)?,
        register_one(VOID)?,
    ])
}

fn silhouette_mesh(pixels: &[u8]) -> MeshData {
    let mut vertices = Vec::new();
    let mut indices = Vec::new();
    for row in 0..ROWS {
        for col in 0..COLS {
            let sample = ((row * HEIGHT / ROWS + HEIGHT / ROWS / 2) * WIDTH
                + col * WIDTH / COLS
                + WIDTH / COLS / 2)
                * 4
                + 3;
            if pixels[sample] < ALPHA_CUTOFF {
                continue;
            }
            let u0 = col as f32 / COLS as f32;
            let v0 = row as f32 / ROWS as f32;
            let u1 = (col + 1) as f32 / COLS as f32;
            let v1 = (row + 1) as f32 / ROWS as f32;
            let base = u32::try_from(vertices.len()).expect("48 x 32 cells fit in u32");
            // Local aspect 1.5:1; the instance scale sets the puddle's world size.
            for (u, v) in [(u0, v0), (u1, v0), (u1, v1), (u0, v1)] {
                vertices.push(MeshVertex::new(
                    [(u - 0.5) * 1.5, (0.5 - v), 0.0],
                    [0.0, 0.0, 1.0],
                    [u, v],
                ));
            }
            indices.extend_from_slice(&[base, base + 1, base + 2, base, base + 2, base + 3]);
        }
    }
    MeshData { vertices, indices }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn all_three_alpha_masks_make_valid_bounded_contours() {
        for pixels in [BLOOD.as_slice(), PLAGUE.as_slice(), VOID.as_slice()] {
            let mesh = silhouette_mesh(pixels);
            mesh.validate().expect("puddle decal mesh is valid");
            assert!(!mesh.indices.is_empty());
            assert!(mesh.vertices.len() < COLS * ROWS * 4);
        }
    }
}
