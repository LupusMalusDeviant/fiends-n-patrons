//! Loading the arena's figures and procedural geometry into a [`WgpuRenderer`].

use std::fmt;
use std::path::Path;

use fnp_game::arena::present::{ArenaVisuals, FigureVisual, stage_mesh_data};
use grimoire::adapters::figure_assets::{FigureLoadError, load_figure};
use grimoire::platform::StdFileSystem;
use grimoire::render::{MeshError, WgpuRenderer};
use grimoire_assets::{AssetError, AssetStore, PackReader};

/// Name of the player figure inside the pack (`figures/soul/...`).
pub const SOUL_FIGURE: &str = "soul";

/// Name of the enemy figure inside the pack (`figures/imp/...`).
pub const IMP_FIGURE: &str = "imp";

/// Failure preparing the arena's visuals.
#[derive(Debug)]
pub enum VisualsError {
    /// The pack file could not be opened or its manifest did not decode.
    OpenPack(AssetError),
    /// A figure could not be loaded from the pack.
    Figure {
        /// Figure name inside the pack.
        name: &'static str,
        /// What went wrong.
        error: FigureLoadError,
    },
    /// A procedural stage mesh was rejected by the renderer.
    StageMesh(MeshError),
}

impl fmt::Display for VisualsError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::OpenPack(error) => write!(f, "cannot open the figure pack: {error}"),
            Self::Figure { name, error } => write!(
                f,
                "cannot load figure `{name}` from the pack (a pack built for this game has the \
                 figures `{SOUL_FIGURE}` and `{IMP_FIGURE}`): {error}"
            ),
            Self::StageMesh(error) => write!(f, "cannot register a stage mesh: {error}"),
        }
    }
}

impl std::error::Error for VisualsError {}

/// Summary of what [`load_visuals`] registered, for the startup log.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct LoadSummary {
    /// Parts of the soul figure.
    pub soul_parts: usize,
    /// Joints of the soul's skeleton.
    pub soul_joints: usize,
    /// Height of the soul's bounds in world units.
    pub soul_height: f32,
    /// Parts of the imp figure.
    pub imp_parts: usize,
    /// Height of the imp's bounds in world units.
    pub imp_height: f32,
}

/// Opens the figure pack at `pack`, loads the soul and the imp and registers the stage geometry.
///
/// # Errors
/// A [`VisualsError`] naming the step that failed.
pub fn load_visuals(
    renderer: &mut WgpuRenderer,
    pack: &Path,
) -> Result<(ArenaVisuals, LoadSummary), VisualsError> {
    let reader = PackReader::open(&StdFileSystem, pack).map_err(VisualsError::OpenPack)?;
    let mut store = AssetStore::new(Box::new(reader));
    let soul =
        load_figure(&mut store, renderer, SOUL_FIGURE).map_err(|error| VisualsError::Figure {
            name: SOUL_FIGURE,
            error,
        })?;
    let imp =
        load_figure(&mut store, renderer, IMP_FIGURE).map_err(|error| VisualsError::Figure {
            name: IMP_FIGURE,
            error,
        })?;

    let meshes = stage_mesh_data();
    let mut register = |data| {
        renderer
            .register_mesh(data)
            .map_err(VisualsError::StageMesh)
    };
    let floor = register(meshes.floor)?;
    let pillar = register(meshes.pillar)?;
    let block = register(meshes.block)?;
    let bullet = register(meshes.bullet)?;
    let marker_ring = register(meshes.marker_ring)?;

    let soul_visual = FigureVisual::from_loaded(&soul);
    let imp_visual = FigureVisual::from_loaded(&imp);
    let summary = LoadSummary {
        soul_parts: soul.parts.len(),
        soul_joints: soul.skeleton.joints.len(),
        soul_height: soul_visual.height,
        imp_parts: imp.parts.len(),
        imp_height: imp_visual.height,
    };
    Ok((
        ArenaVisuals {
            soul: soul_visual,
            imp: imp_visual,
            floor,
            pillar,
            block,
            bullet,
            marker_ring,
        },
        summary,
    ))
}
