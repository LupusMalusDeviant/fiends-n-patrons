//! Loading the arena's figures and procedural geometry through the facade's asset hook
//! ([`RenderAssets`], contract §9.10).
//!
//! Which figures a pack carries is not fixed: [`choose_figures`] picks a player and an enemy from
//! what the pack actually contains, so the pack with the new characters (`witch`, `imp_hi3d`) and
//! the older ones (`soul`, `imp`) both run, and [`FNP_PLAYER_FIGURE_VAR`] /
//! [`FNP_ENEMY_FIGURE_VAR`] override the choice. The executable resolves this before the window
//! opens, so a pack without usable figures ends the run with a message instead of a black window.

use std::collections::BTreeSet;
use std::fmt;
use std::path::Path;

use fnp_game::arena::present::{
    ArenaDistrict, ArenaVisuals, AuthoredFront, FigureAnimation, FigureVisual, PuddleVisual,
    StageMeshData, stage_mesh_data,
};
use fnp_game::worldgen::{WorldPlan, generate_floor, generate_run, validate_floor};
use grimoire::RenderAssets;
use grimoire::adapters::figure_assets::{
    FigureLoadError, LoadedFigure, load_clip, load_figure_into,
};
use grimoire::platform::StdFileSystem;
use grimoire::render::figure_format::SkeletonData;
use grimoire::render::{MeshError, MeshHandle, TextureError};
use grimoire_assets::{AssetError, AssetSource, AssetStore, PackReader};

/// Environment variable that names the player figure inside the pack.
pub const FNP_PLAYER_FIGURE_VAR: &str = "FNP_PLAYER_FIGURE";

/// Environment variable that names the enemy figure inside the pack.
pub const FNP_ENEMY_FIGURE_VAR: &str = "FNP_ENEMY_FIGURE";

/// Player figures the game looks for, best first.
pub const PLAYER_FIGURES: &[&str] = &["witch", "soul"];

/// Enemy figures the game looks for, best first.
pub const ENEMY_FIGURES: &[&str] = &["imp_hi3d", "imp"];

/// Which way a figure whose rig says nothing is assumed to look: the game's convention, glTF +Z
/// (the glTF standard and the Hi3D assets).
pub const DEFAULT_FIGURE_FRONT: AuthoredFront = AuthoredFront::PlusZ;

/// Clip a figure plays while it stands still (`figures/<name>/clip/idle`).
pub const IDLE_CLIP: &str = "idle";

/// Clip a figure plays while it moves (`figures/<name>/clip/walk`).
pub const WALK_CLIP: &str = "walk";

/// Which way the figures of the earlier packs (rounds 3 and 4) look: glTF -Z, against the
/// convention, so they are turned by half a turn before anything else ([`AuthoredFront`]).
pub const PACK_FIGURES_FRONT: AuthoredFront = AuthoredFront::MinusZ;

/// Environment variable that fixes the front of both figures instead of measuring it.
pub const FNP_FIGURE_FRONT_VAR: &str = "FNP_FIGURE_FRONT";

/// Which way a figure looks, or the order to find out.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FrontChoice {
    /// Measure it on the figure's own rig ([`measure_front`]), falling back to the default.
    Measure,
    /// Take this front, whatever the rig says.
    Fixed(AuthoredFront),
}

/// Joint names whose rest position says where a figure's front is, best first: toes stick out
/// forward, feet less so, hands hang beside the body but still lead.
const FRONT_JOINT_HINTS: [&str; 3] = ["toe", "foot", "hand"];

/// How far from the body's middle such a joint has to sit before it counts, in metres.
const FRONT_JOINT_MIN_OFFSET: f32 = 0.01;

/// Which way the figure of `skeleton` was authored to look, measured on its rest pose.
///
/// The pack figures carry the glTF-to-engine axis change in the root joint's rotation, so a joint's
/// rest position is already in the game's space (X right, Y away from the viewer, Z up). A figure
/// that follows the convention (glTF +Z is its front) has its toes towards the viewer, at negative
/// Y; one authored the other way round has them at positive Y.
///
/// Returns `None` when the rig has no joint the measurement knows or the joints sit too close to
/// the middle to decide — then the caller's default applies.
#[must_use]
pub fn measure_front(skeleton: &SkeletonData) -> Option<AuthoredFront> {
    let positions = rest_positions(skeleton);
    for hint in FRONT_JOINT_HINTS {
        let mut sum = 0.0_f32;
        let mut count = 0_u32;
        for (joint, position) in skeleton.joints.iter().zip(&positions) {
            if joint.name.to_ascii_lowercase().contains(hint) {
                sum += position[1];
                count += 1;
            }
        }
        if count == 0 {
            continue;
        }
        let mean = sum / count as f32;
        if !mean.is_finite() || mean.abs() < FRONT_JOINT_MIN_OFFSET {
            continue;
        }
        return Some(if mean < 0.0 {
            AuthoredFront::PlusZ
        } else {
            AuthoredFront::MinusZ
        });
    }
    None
}

/// Rest position of every joint in model space, parents before children (the skeleton's own
/// invariant), from the rest translations and rotations.
fn rest_positions(skeleton: &SkeletonData) -> Vec<[f32; 3]> {
    let mut globals: Vec<[[f32; 3]; 3]> = Vec::with_capacity(skeleton.joints.len());
    let mut positions: Vec<[f32; 3]> = Vec::with_capacity(skeleton.joints.len());
    for joint in &skeleton.joints {
        let local = rotation_matrix(joint.rotation, joint.scale);
        let (parent_rotation, parent_position) = match joint.parent {
            Some(parent) => {
                let index = parent as usize;
                match (globals.get(index), positions.get(index)) {
                    (Some(rotation), Some(position)) => (*rotation, *position),
                    // A forward reference cannot happen (parents come first), but never panic.
                    _ => (IDENTITY_3, [0.0; 3]),
                }
            }
            None => (IDENTITY_3, [0.0; 3]),
        };
        let offset = apply(parent_rotation, joint.translation);
        positions.push([
            parent_position[0] + offset[0],
            parent_position[1] + offset[1],
            parent_position[2] + offset[2],
        ]);
        globals.push(multiply(parent_rotation, local));
    }
    positions
}

/// The 3x3 identity.
const IDENTITY_3: [[f32; 3]; 3] = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]];

/// Column-major rotation matrix of the quaternion `(x, y, z, w)` with a per-axis scale.
fn rotation_matrix(quaternion: [f32; 4], scale: [f32; 3]) -> [[f32; 3]; 3] {
    let [x, y, z, w] = quaternion;
    let columns = [
        [
            1.0 - 2.0 * (y * y + z * z),
            2.0 * (x * y + z * w),
            2.0 * (x * z - y * w),
        ],
        [
            2.0 * (x * y - z * w),
            1.0 - 2.0 * (x * x + z * z),
            2.0 * (y * z + x * w),
        ],
        [
            2.0 * (x * z + y * w),
            2.0 * (y * z - x * w),
            1.0 - 2.0 * (x * x + y * y),
        ],
    ];
    let mut scaled = columns;
    for (column, factor) in scaled.iter_mut().zip(scale) {
        for value in column.iter_mut() {
            *value *= factor;
        }
    }
    scaled
}

/// `matrix * vector` for column-major 3x3 matrices.
fn apply(matrix: [[f32; 3]; 3], vector: [f32; 3]) -> [f32; 3] {
    let mut out = [0.0_f32; 3];
    for (column, value) in matrix.iter().zip(vector) {
        for (slot, entry) in out.iter_mut().zip(column) {
            *slot += entry * value;
        }
    }
    out
}

/// `left * right` for column-major 3x3 matrices.
fn multiply(left: [[f32; 3]; 3], right: [[f32; 3]; 3]) -> [[f32; 3]; 3] {
    let mut out = IDENTITY_3;
    for (column, source) in out.iter_mut().zip(right) {
        *column = apply(left, source);
    }
    out
}

/// A figure picked out of a pack.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ChosenFigure {
    /// Name inside the pack.
    pub name: String,
    /// Which way its model looks, or the order to measure it.
    pub front: FrontChoice,
}

impl ChosenFigure {
    /// The figure `name`, with `front`.
    #[must_use]
    pub fn new(name: &str, front: FrontChoice) -> Self {
        Self {
            name: name.to_owned(),
            front,
        }
    }

    /// Parses an override of the form `name` or `name:plusz` / `name:minusz`; without a suffix the
    /// figure's front is `front`.
    ///
    /// # Errors
    /// [`FigureChoiceError::InvalidOverride`] if the value is empty or the suffix is not one of
    /// the two fronts.
    pub fn parse(
        value: &str,
        front: FrontChoice,
        variable: &'static str,
    ) -> Result<Self, FigureChoiceError> {
        let invalid = || FigureChoiceError::InvalidOverride {
            variable,
            value: value.to_owned(),
        };
        let (name, given) = match value.split_once(':') {
            None => (value, None),
            Some((name, "plusz")) => (name, Some(AuthoredFront::PlusZ)),
            Some((name, "minusz")) => (name, Some(AuthoredFront::MinusZ)),
            Some(_) => return Err(invalid()),
        };
        if name.is_empty() {
            return Err(invalid());
        }
        Ok(ChosenFigure::new(
            name,
            given.map_or(front, FrontChoice::Fixed),
        ))
    }
}

/// The two figures a run draws.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PackFigures {
    /// The player's figure.
    pub player: ChosenFigure,
    /// The enemy's figure.
    pub enemy: ChosenFigure,
}

/// No usable figure pair in a pack, or an override that names none.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FigureChoiceError {
    /// The pack has none of the figures the game knows for this role.
    NoFigure {
        /// `player` or `enemy`.
        role: &'static str,
        /// Names the game looked for.
        wanted: Vec<&'static str>,
        /// Figures the pack actually has.
        available: Vec<String>,
        /// Variable that overrides the choice.
        variable: &'static str,
    },
    /// An override names a figure the pack does not have.
    Missing {
        /// Variable the name came from.
        variable: &'static str,
        /// Name that was asked for.
        name: String,
        /// Figures the pack actually has.
        available: Vec<String>,
    },
    /// An override could not be parsed.
    InvalidOverride {
        /// Variable the value came from.
        variable: &'static str,
        /// The value, verbatim.
        value: String,
    },
}

impl fmt::Display for FigureChoiceError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::NoFigure {
                role,
                wanted,
                available,
                variable,
            } => write!(
                f,
                "the figure pack has no {role} figure: looked for {}, the pack has {} (set \
                 {variable}=<name> to choose another)",
                list(&wanted.iter().map(ToString::to_string).collect::<Vec<_>>()),
                list(available)
            ),
            Self::Missing {
                variable,
                name,
                available,
            } => write!(
                f,
                "{variable} names the figure `{name}`, which the pack does not have; it has {}",
                list(available)
            ),
            Self::InvalidOverride { variable, value } => write!(
                f,
                "invalid {variable}={value:?}: expected `<name>`, `<name>:plusz` or \
                 `<name>:minusz`"
            ),
        }
    }
}

impl std::error::Error for FigureChoiceError {}

/// `a`, `b` and `c` — or `none` for an empty list.
fn list(names: &[String]) -> String {
    if names.is_empty() {
        return String::from("none");
    }
    names
        .iter()
        .map(|name| format!("`{name}`"))
        .collect::<Vec<_>>()
        .join(", ")
}

/// Picks the player and the enemy out of `available` (the figures a pack has), both with `front`.
///
/// An override wins over the tables; without one, the first known figure of the role that the
/// pack has wins, so a pack with `witch` and `imp_hi3d` and one with `soul` and `imp` both run.
/// The names say nothing about which way a figure looks — the packs reuse them across
/// generations — so that is `front`'s business.
///
/// # Errors
/// A [`FigureChoiceError`] naming what was looked for and what the pack has.
pub fn choose_figures(
    available: &[String],
    front: FrontChoice,
    player_override: Option<&str>,
    enemy_override: Option<&str>,
) -> Result<PackFigures, FigureChoiceError> {
    let pick = |role: &'static str,
                known: &'static [&'static str],
                variable: &'static str,
                given: Option<&str>|
     -> Result<ChosenFigure, FigureChoiceError> {
        if let Some(value) = given {
            let chosen = ChosenFigure::parse(value, front, variable)?;
            if !available.contains(&chosen.name) {
                return Err(FigureChoiceError::Missing {
                    variable,
                    name: chosen.name,
                    available: available.to_vec(),
                });
            }
            return Ok(chosen);
        }
        known
            .iter()
            .find(|figure| available.iter().any(|name| name == *figure))
            .map(|figure| ChosenFigure::new(figure, front))
            .ok_or_else(|| FigureChoiceError::NoFigure {
                role,
                wanted: known.to_vec(),
                available: available.to_vec(),
                variable,
            })
    };
    Ok(PackFigures {
        player: pick(
            "player",
            PLAYER_FIGURES,
            FNP_PLAYER_FIGURE_VAR,
            player_override,
        )?,
        enemy: pick("enemy", ENEMY_FIGURES, FNP_ENEMY_FIGURE_VAR, enemy_override)?,
    })
}

/// Failure preparing the arena's visuals.
#[derive(Debug)]
pub enum VisualsError {
    /// The pack file could not be opened or its manifest did not decode.
    OpenPack(AssetError),
    /// The pack has no usable pair of figures, or an override names none.
    Choice(FigureChoiceError),
    /// A figure could not be loaded from the pack.
    Figure {
        /// Figure name inside the pack.
        name: String,
        /// What went wrong.
        error: FigureLoadError,
    },
    /// A procedural stage mesh was rejected by the renderer.
    StageMesh(MeshError),
    /// The bundled arena floor maps could not be registered.
    StageTexture(TextureError),
    /// The named floor district is not one of the three bundled layouts.
    InvalidDistrict(String),
    /// A puddle decal mesh or colour could not be registered.
    Puddle(crate::arena_puddles::PuddleError),
}

impl fmt::Display for VisualsError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::OpenPack(error) => write!(f, "cannot open the figure pack: {error}"),
            Self::Choice(error) => write!(f, "{error}"),
            Self::Figure { name, error } => {
                write!(f, "cannot load figure `{name}` from the pack: {error}")
            }
            Self::StageMesh(error) => write!(f, "cannot register a stage mesh: {error}"),
            Self::StageTexture(error) => write!(f, "cannot register an arena texture: {error}"),
            Self::InvalidDistrict(name) => write!(
                f,
                "unknown arena district `{name}`; choose crypt, foundry, or ossuary"
            ),
            Self::Puddle(error) => write!(f, "cannot register a puddle: {error}"),
        }
    }
}

impl std::error::Error for VisualsError {}

impl From<FigureChoiceError> for VisualsError {
    fn from(error: FigureChoiceError) -> Self {
        Self::Choice(error)
    }
}

/// The figures a pack carries, sorted by name: every `figures/<name>/figure` entry in it.
///
/// # Errors
/// [`VisualsError::OpenPack`] if the pack cannot be opened or its manifest does not decode.
pub fn figures_in_pack(pack: &Path) -> Result<Vec<String>, VisualsError> {
    let reader = PackReader::open(&StdFileSystem, pack).map_err(VisualsError::OpenPack)?;
    let mut names = BTreeSet::new();
    for entry in reader.entries() {
        let Some(path) = reader.manifest().path_of(entry.id) else {
            continue;
        };
        // `figures/<name>/figure` is the figure itself; its parts and textures sit next to it.
        if let Some(rest) = path.as_str().strip_prefix("figures/")
            && let Some(name) = rest.strip_suffix("/figure")
            && !name.contains('/')
        {
            names.insert(name.to_owned());
        }
    }
    Ok(names.into_iter().collect())
}

/// Picks the player and the enemy out of the pack at `pack`.
///
/// # Errors
/// [`VisualsError::OpenPack`] or [`VisualsError::Choice`], both of them before a window opens.
pub fn resolve_figures(
    pack: &Path,
    front: FrontChoice,
    player_override: Option<&str>,
    enemy_override: Option<&str>,
) -> Result<PackFigures, VisualsError> {
    let available = figures_in_pack(pack)?;
    Ok(choose_figures(
        &available,
        front,
        player_override,
        enemy_override,
    )?)
}

/// Summary of what [`load_visuals`] registered, for the startup log.
#[derive(Debug, Clone, PartialEq)]
pub struct LoadSummary {
    /// Name of the player figure in the pack.
    pub player_name: String,
    /// Parts of the player figure.
    pub player_parts: usize,
    /// Joints of the player's skeleton.
    pub player_joints: usize,
    /// Height of the player's bounds in world units.
    pub player_height: f32,
    /// Name of the enemy figure in the pack.
    pub enemy_name: String,
    /// Parts of the enemy figure.
    pub enemy_parts: usize,
    /// Height of the enemy's bounds in world units.
    pub enemy_height: f32,
    /// Which way the player's model looks and whether that was measured or set.
    pub player_front: (AuthoredFront, bool),
    /// Which way the enemy's model looks and whether that was measured or set.
    pub enemy_front: (AuthoredFront, bool),
    /// Whether the player's figure plays its clips, and why not if it does not.
    pub player_clips: Result<(), String>,
    /// The same for the enemy's figure.
    pub enemy_clips: Result<(), String>,
}

impl fmt::Display for LoadSummary {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let front = |(front, measured): (AuthoredFront, bool)| {
            let name = match front {
                AuthoredFront::PlusZ => "+Z",
                AuthoredFront::MinusZ => "-Z",
            };
            let source = if measured { "measured" } else { "set" };
            format!("front {name} ({source})")
        };
        let clips = |result: &Result<(), String>| match result {
            Ok(()) => String::from("clips idle+walk"),
            Err(reason) => format!("no clips ({reason})"),
        };
        write!(
            f,
            "player `{}`: {} parts, {} joints, {:.2} m, {}, {}; enemy `{}`: {} parts, \
             {:.2} m, {}, {}",
            self.player_name,
            self.player_parts,
            self.player_joints,
            self.player_height,
            front(self.player_front),
            clips(&self.player_clips),
            self.enemy_name,
            self.enemy_parts,
            self.enemy_height,
            front(self.enemy_front),
            clips(&self.enemy_clips)
        )
    }
}

/// Handles of the procedural stage geometry.
struct StageHandles {
    floor: MeshHandle,
    pillar: MeshHandle,
    block: MeshHandle,
    marker_ring: MeshHandle,
}

fn register_stage(
    assets: &mut dyn RenderAssets,
    meshes: StageMeshData,
) -> Result<StageHandles, VisualsError> {
    let mut register = |data| assets.register_mesh(data).map_err(VisualsError::StageMesh);
    Ok(StageHandles {
        floor: register(meshes.floor)?,
        pillar: register(meshes.pillar)?,
        block: register(meshes.block)?,
        marker_ring: register(meshes.marker_ring)?,
    })
}

/// Opens the figure pack at `pack`, loads the two figures of `figures` and registers them and the
/// stage geometry with `assets`.
///
/// # Errors
/// A [`VisualsError`] naming the step that failed.
pub fn load_visuals(
    assets: &mut dyn RenderAssets,
    pack: &Path,
    figures: &PackFigures,
    world_seed: u64,
) -> Result<(ArenaVisuals, LoadSummary), VisualsError> {
    let reader = PackReader::open(&StdFileSystem, pack).map_err(VisualsError::OpenPack)?;
    let mut store = AssetStore::new(Box::new(reader));
    let mut load = |chosen: &ChosenFigure| {
        load_figure_into(&mut store, assets, &chosen.name).map_err(|error| VisualsError::Figure {
            name: chosen.name.clone(),
            error,
        })
    };
    let player = load(&figures.player)?;
    let enemy = load(&figures.enemy)?;
    let stage = register_stage(assets, stage_mesh_data())?;
    let run_plan = generate_run(world_seed);
    let first_stage = &run_plan.stages[0];
    let district = std::env::var("FNP_ARENA_DISTRICT")
        .ok()
        .map(|name| ArenaDistrict::parse(&name).ok_or(VisualsError::InvalidDistrict(name)))
        .transpose()?
        .unwrap_or(first_stage.district);
    let room_floor = generate_floor(first_stage.rooms[0].floor_seed, district);
    debug_assert_eq!(validate_floor(&room_floor), Ok(()));
    let floor_textures = if std::env::var("FNP_WORLD_PATCH_PREVIEW").as_deref() == Ok("1") {
        // The playable arena is still a smaller room. This preview lets the
        // renderer show any 48 m patch of the 256 m world at true scale.
        let coordinate = |name: &str| {
            std::env::var(name)
                .ok()
                .and_then(|value| value.parse::<usize>().ok())
                .unwrap_or(128)
        };
        let center = (
            coordinate("FNP_WORLD_PATCH_CENTER_X"),
            coordinate("FNP_WORLD_PATCH_CENTER_Y"),
        );
        crate::arena_floor::register_world_patch(
            assets,
            &WorldPlan::new(world_seed, district),
            center,
        )
    } else {
        crate::arena_floor::register(assets, &room_floor)
    }
    .map_err(VisualsError::StageTexture)?;
    let puddles = crate::arena_puddles::register(assets)
        .map_err(VisualsError::Puddle)?
        .map(|puddle| PuddleVisual {
            mesh: puddle.mesh,
            base_color: puddle.base_color,
        });

    // Which way a figure looks is a property of the figure, not of its name: the packs reuse
    // `soul` and `imp` across generations that were authored differently.
    let front = |chosen: &ChosenFigure, skeleton: &SkeletonData| match chosen.front {
        FrontChoice::Fixed(front) => (front, false),
        FrontChoice::Measure => {
            measure_front(skeleton).map_or((DEFAULT_FIGURE_FRONT, false), |front| (front, true))
        }
    };
    let (player_front, player_measured) = front(&figures.player, &player.skeleton);
    let (enemy_front, enemy_measured) = front(&figures.enemy, &enemy.skeleton);
    // Clips are optional: a pack without them draws the rest pose, exactly as before.
    let (player_animation, player_clips) =
        load_animation(&mut store, &figures.player.name, &player);
    let (enemy_animation, enemy_clips) = load_animation(&mut store, &figures.enemy.name, &enemy);
    let mut player_visual = FigureVisual::from_loaded(&player, player_front);
    if let Some(animation) = player_animation {
        player_visual = player_visual.with_animation(animation);
    }
    let mut enemy_visual = FigureVisual::from_loaded(&enemy, enemy_front);
    if let Some(animation) = enemy_animation {
        enemy_visual = enemy_visual.with_animation(animation);
    }
    let summary = LoadSummary {
        player_name: figures.player.name.clone(),
        player_parts: player.parts.len(),
        player_joints: player.skeleton.joints.len(),
        player_height: player_visual.height,
        enemy_name: figures.enemy.name.clone(),
        enemy_parts: enemy.parts.len(),
        enemy_height: enemy_visual.height,
        player_front: (player_front, player_measured),
        enemy_front: (enemy_front, enemy_measured),
        player_clips,
        enemy_clips,
    };
    Ok((
        ArenaVisuals {
            soul: player_visual,
            imp: enemy_visual,
            floor: stage.floor,
            floor_textures: Some(floor_textures),
            district,
            room_floor: Some(room_floor),
            puddles: Some(puddles),
            pillar: stage.pillar,
            block: stage.block,
            marker_ring: stage.marker_ring,
        },
        summary,
    ))
}

/// Loads the [`IDLE_CLIP`] and [`WALK_CLIP`] of `name` and checks them against the figure's own
/// skeleton (`load_clip` compares joint count and skeleton fingerprint, so a clip of another rig
/// is refused instead of posing nonsense).
///
/// A figure without both clips simply has no animation; the reason is returned for the log.
fn load_animation(
    store: &mut AssetStore,
    name: &str,
    figure: &LoadedFigure,
) -> (Option<FigureAnimation>, Result<(), String>) {
    let mut load = |clip: &str| {
        load_clip(store, name, clip, &figure.skeleton).map_err(|error| format!("{clip}: {error}"))
    };
    match (load(IDLE_CLIP), load(WALK_CLIP)) {
        (Ok(idle), Ok(walk)) => (
            Some(FigureAnimation {
                skeleton: figure.skeleton.clone(),
                idle,
                walk,
            }),
            Ok(()),
        ),
        (Err(reason), _) | (Ok(_), Err(reason)) => (None, Err(reason)),
    }
}

/// Registers only the stage geometry and stands both figures in as placeholders that reuse the
/// block mesh: for runs without a figure pack (headless tests).
///
/// # Errors
/// [`VisualsError::StageMesh`] if a stage mesh is rejected.
pub fn placeholder_visuals(assets: &mut dyn RenderAssets) -> Result<ArenaVisuals, VisualsError> {
    let stage = register_stage(assets, stage_mesh_data())?;
    Ok(ArenaVisuals {
        soul: FigureVisual::placeholder(stage.block),
        imp: FigureVisual::placeholder(stage.block),
        floor: stage.floor,
        floor_textures: None,
        district: ArenaDistrict::Crypt,
        room_floor: None,
        puddles: None,
        pillar: stage.pillar,
        block: stage.block,
        marker_ring: stage.marker_ring,
    })
}
#[cfg(test)]
mod tests {
    use grimoire::render::figure_format::JointData;

    use super::*;

    fn names(values: &[&str]) -> Vec<String> {
        values.iter().map(|value| (*value).to_owned()).collect()
    }

    fn joint(name: &str, parent: Option<u32>, translation: [f32; 3]) -> JointData {
        JointData {
            parent,
            inverse_bind: [[0.0; 4]; 4],
            name: name.to_owned(),
            translation,
            rotation: [0.0, 0.0, 0.0, 1.0],
            scale: [1.0, 1.0, 1.0],
        }
    }

    /// A rig with a root, a hip and two toes; `forward` is the direction the toes stick out in.
    fn rig(forward: f32) -> SkeletonData {
        SkeletonData {
            joints: vec![
                joint("root", None, [0.0, 0.0, 0.0]),
                joint("hips", Some(0), [0.0, 0.0, 1.0]),
                joint("toe.l", Some(1), [-0.1, forward, -1.0]),
                joint("toe.r", Some(1), [0.1, forward, -1.0]),
            ],
        }
    }

    #[test]
    fn the_new_pack_gives_the_witch_and_the_hi3d_imp() {
        let chosen = choose_figures(
            &names(&["imp_hi3d", "witch"]),
            FrontChoice::Measure,
            None,
            None,
        )
        .expect("a pair");
        assert_eq!(chosen.player.name, "witch");
        assert_eq!(chosen.enemy.name, "imp_hi3d");
        assert_eq!(chosen.player.front, FrontChoice::Measure);
    }

    #[test]
    fn the_older_pack_still_gives_the_soul_and_the_imp() {
        let chosen = choose_figures(
            &names(&["imp", "soul"]),
            FrontChoice::Fixed(PACK_FIGURES_FRONT),
            None,
            None,
        )
        .expect("a pair");
        assert_eq!(chosen.player.name, "soul");
        assert_eq!(chosen.enemy.name, "imp");
        assert_eq!(
            chosen.enemy.front,
            FrontChoice::Fixed(AuthoredFront::MinusZ)
        );
    }

    #[test]
    fn a_pack_with_both_generations_prefers_the_new_figures() {
        let chosen = choose_figures(
            &names(&["imp", "imp_hi3d", "soul", "witch"]),
            FrontChoice::Measure,
            None,
            None,
        )
        .expect("ok");
        assert_eq!(chosen.player.name, "witch");
        assert_eq!(chosen.enemy.name, "imp_hi3d");
    }

    #[test]
    fn an_override_wins_and_can_say_which_way_the_figure_looks() {
        let available = names(&["imp", "soul", "stranger"]);
        let chosen = choose_figures(
            &available,
            FrontChoice::Measure,
            Some("stranger"),
            Some("imp:plusz"),
        )
        .expect("a pair");
        assert_eq!(chosen.player.name, "stranger");
        assert_eq!(
            chosen.player.front,
            FrontChoice::Measure,
            "without a suffix the rig decides"
        );
        assert_eq!(chosen.enemy.name, "imp");
        assert_eq!(
            chosen.enemy.front,
            FrontChoice::Fixed(AuthoredFront::PlusZ),
            "the suffix overrules everything"
        );
    }

    #[test]
    fn a_pack_without_a_player_figure_says_what_it_has() {
        let error = choose_figures(&names(&["imp", "pillar"]), FrontChoice::Measure, None, None)
            .expect_err("no player");
        let message = error.to_string();
        assert!(message.contains("no player figure"), "{message}");
        assert!(message.contains("`witch`"), "{message}");
        assert!(message.contains("`imp`"), "{message}");
        assert!(message.contains(FNP_PLAYER_FIGURE_VAR), "{message}");
    }

    #[test]
    fn an_override_that_names_nothing_in_the_pack_is_refused() {
        let available = names(&["imp", "soul"]);
        let error = choose_figures(&available, FrontChoice::Measure, Some("witch"), None)
            .expect_err("not in the pack");
        assert!(
            matches!(&error, FigureChoiceError::Missing { name, .. } if name == "witch"),
            "{error}"
        );
        let error = choose_figures(
            &available,
            FrontChoice::Measure,
            Some("soul:sideways"),
            None,
        )
        .expect_err("invalid");
        assert!(matches!(error, FigureChoiceError::InvalidOverride { .. }));
        let error =
            choose_figures(&available, FrontChoice::Measure, Some(""), None).expect_err("empty");
        assert!(matches!(error, FigureChoiceError::InvalidOverride { .. }));
    }

    #[test]
    fn the_rig_says_which_way_a_figure_looks() {
        // Toes towards the viewer (negative Y in the game's space) means the model follows the
        // convention; away from it means it was authored the other way round.
        assert_eq!(measure_front(&rig(-0.15)), Some(AuthoredFront::PlusZ));
        assert_eq!(measure_front(&rig(0.15)), Some(AuthoredFront::MinusZ));
    }

    #[test]
    fn a_rig_that_says_nothing_leaves_the_front_open() {
        // No joint the measurement knows.
        let anonymous = SkeletonData {
            joints: vec![joint("bone_0", None, [0.0, 0.0, 0.0])],
        };
        assert_eq!(measure_front(&anonymous), None);
        // Toes right under the body: too close to the middle to decide.
        assert_eq!(measure_front(&rig(0.0)), None);
        assert_eq!(measure_front(&rig(FRONT_JOINT_MIN_OFFSET / 2.0)), None);
    }

    #[test]
    fn a_parents_rotation_turns_its_children_before_they_are_measured() {
        // The same rig, turned half a turn around Z by its root: the toes end up behind the body.
        let mut turned = rig(-0.15);
        turned.joints[0].rotation = [0.0, 0.0, 1.0, 0.0];
        assert_eq!(measure_front(&turned), Some(AuthoredFront::MinusZ));
    }
}
