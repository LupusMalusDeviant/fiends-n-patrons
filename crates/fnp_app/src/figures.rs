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
    ArenaVisuals, AuthoredFront, FigureVisual, StageMeshData, stage_mesh_data,
};
use grimoire::RenderAssets;
use grimoire::adapters::figure_assets::{FigureLoadError, load_figure_into};
use grimoire::platform::StdFileSystem;
use grimoire::render::{MeshError, MeshHandle};
use grimoire_assets::{AssetError, AssetSource, AssetStore, PackReader};

/// Environment variable that names the player figure inside the pack.
pub const FNP_PLAYER_FIGURE_VAR: &str = "FNP_PLAYER_FIGURE";

/// Environment variable that names the enemy figure inside the pack.
pub const FNP_ENEMY_FIGURE_VAR: &str = "FNP_ENEMY_FIGURE";

/// A figure the game knows by name, with the direction its model was authored to look in.
///
/// The game's convention is glTF +Z (the glTF standard and the Hi3D assets); the figures of the
/// earlier packs (`soul`, `imp` of rounds 3 and 4) look along glTF -Z and are turned by half a
/// turn before anything else ([`AuthoredFront`]). Measured on those rigs: hands and toes sit at
/// negative glTF Z, the imp's tail at positive Z, and the `.L` joints at negative X, which is the
/// figure's left only when it looks along -Z.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct KnownFigure {
    /// Name inside the pack (`figures/<name>/figure`).
    pub name: &'static str,
    /// Which way the model looks.
    pub front: AuthoredFront,
}

/// Player figures the game looks for, best first.
pub const PLAYER_FIGURES: &[KnownFigure] = &[
    KnownFigure {
        name: "witch",
        front: AuthoredFront::PlusZ,
    },
    KnownFigure {
        name: "soul",
        front: AuthoredFront::MinusZ,
    },
];

/// Enemy figures the game looks for, best first.
pub const ENEMY_FIGURES: &[KnownFigure] = &[
    KnownFigure {
        name: "imp_hi3d",
        front: AuthoredFront::PlusZ,
    },
    KnownFigure {
        name: "imp",
        front: AuthoredFront::MinusZ,
    },
];

/// Which way a figure the tables do not know is assumed to look: the game's convention.
pub const UNKNOWN_FIGURE_FRONT: AuthoredFront = AuthoredFront::PlusZ;

/// Which way the figures of the earlier packs (rounds 3 and 4: `soul`, `imp`) look.
pub const PACK_FIGURES_FRONT: AuthoredFront = AuthoredFront::MinusZ;

/// A figure picked out of a pack.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ChosenFigure {
    /// Name inside the pack.
    pub name: String,
    /// Which way its model looks.
    pub front: AuthoredFront,
}

impl ChosenFigure {
    /// The figure `name`, with the front of the table entry of that name or
    /// [`UNKNOWN_FIGURE_FRONT`].
    #[must_use]
    pub fn new(name: &str, known: &[KnownFigure]) -> Self {
        let front = known
            .iter()
            .find(|figure| figure.name == name)
            .map_or(UNKNOWN_FIGURE_FRONT, |figure| figure.front);
        Self {
            name: name.to_owned(),
            front,
        }
    }

    /// Parses an override of the form `name` or `name:plusz` / `name:minusz`.
    ///
    /// # Errors
    /// [`FigureChoiceError::InvalidOverride`] if the value is empty or the suffix is not one of
    /// the two fronts.
    pub fn parse(
        value: &str,
        known: &[KnownFigure],
        variable: &'static str,
    ) -> Result<Self, FigureChoiceError> {
        let invalid = || FigureChoiceError::InvalidOverride {
            variable,
            value: value.to_owned(),
        };
        let (name, front) = match value.split_once(':') {
            None => (value, None),
            Some((name, "plusz")) => (name, Some(AuthoredFront::PlusZ)),
            Some((name, "minusz")) => (name, Some(AuthoredFront::MinusZ)),
            Some(_) => return Err(invalid()),
        };
        if name.is_empty() {
            return Err(invalid());
        }
        let mut chosen = ChosenFigure::new(name, known);
        if let Some(front) = front {
            chosen.front = front;
        }
        Ok(chosen)
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

/// Picks the player and the enemy out of `available` (the figures a pack has).
///
/// An override wins over the tables; without one, the first known figure of the role that the
/// pack has wins, so a pack with `witch` and `imp_hi3d` and one with `soul` and `imp` both run.
///
/// # Errors
/// A [`FigureChoiceError`] naming what was looked for and what the pack has.
pub fn choose_figures(
    available: &[String],
    player_override: Option<&str>,
    enemy_override: Option<&str>,
) -> Result<PackFigures, FigureChoiceError> {
    let pick = |role: &'static str,
                known: &'static [KnownFigure],
                variable: &'static str,
                given: Option<&str>|
     -> Result<ChosenFigure, FigureChoiceError> {
        if let Some(value) = given {
            let chosen = ChosenFigure::parse(value, known, variable)?;
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
            .find(|figure| available.iter().any(|name| name == figure.name))
            .map(|figure| ChosenFigure {
                name: figure.name.to_owned(),
                front: figure.front,
            })
            .ok_or_else(|| FigureChoiceError::NoFigure {
                role,
                wanted: known.iter().map(|figure| figure.name).collect(),
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
    player_override: Option<&str>,
    enemy_override: Option<&str>,
) -> Result<PackFigures, VisualsError> {
    let available = figures_in_pack(pack)?;
    Ok(choose_figures(&available, player_override, enemy_override)?)
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
}

impl fmt::Display for LoadSummary {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "player `{}`: {} parts, {} joints, {:.2} m; enemy `{}`: {} parts, {:.2} m",
            self.player_name,
            self.player_parts,
            self.player_joints,
            self.player_height,
            self.enemy_name,
            self.enemy_parts,
            self.enemy_height
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

    let player_visual = FigureVisual::from_loaded(&player, figures.player.front);
    let enemy_visual = FigureVisual::from_loaded(&enemy, figures.enemy.front);
    let summary = LoadSummary {
        player_name: figures.player.name.clone(),
        player_parts: player.parts.len(),
        player_joints: player.skeleton.joints.len(),
        player_height: player_visual.height,
        enemy_name: figures.enemy.name.clone(),
        enemy_parts: enemy.parts.len(),
        enemy_height: enemy_visual.height,
    };
    Ok((
        ArenaVisuals {
            soul: player_visual,
            imp: enemy_visual,
            floor: stage.floor,
            pillar: stage.pillar,
            block: stage.block,
            marker_ring: stage.marker_ring,
        },
        summary,
    ))
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
        pillar: stage.pillar,
        block: stage.block,
        marker_ring: stage.marker_ring,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn names(values: &[&str]) -> Vec<String> {
        values.iter().map(|value| (*value).to_owned()).collect()
    }

    #[test]
    fn the_new_pack_gives_the_witch_and_the_hi3d_imp() {
        let chosen = choose_figures(&names(&["imp_hi3d", "witch"]), None, None).expect("a pair");
        assert_eq!(chosen.player.name, "witch");
        assert_eq!(chosen.player.front, AuthoredFront::PlusZ);
        assert_eq!(chosen.enemy.name, "imp_hi3d");
        assert_eq!(chosen.enemy.front, AuthoredFront::PlusZ);
    }

    #[test]
    fn the_older_pack_still_gives_the_soul_and_the_imp() {
        let chosen = choose_figures(&names(&["imp", "soul"]), None, None).expect("a pair");
        assert_eq!(chosen.player.name, "soul");
        assert_eq!(chosen.player.front, AuthoredFront::MinusZ);
        assert_eq!(chosen.enemy.name, "imp");
        assert_eq!(chosen.enemy.front, AuthoredFront::MinusZ);
    }

    #[test]
    fn a_pack_with_both_generations_prefers_the_new_figures() {
        let chosen =
            choose_figures(&names(&["imp", "imp_hi3d", "soul", "witch"]), None, None).expect("ok");
        assert_eq!(chosen.player.name, "witch");
        assert_eq!(chosen.enemy.name, "imp_hi3d");
    }

    #[test]
    fn an_override_wins_and_can_say_which_way_the_figure_looks() {
        let available = names(&["imp", "soul", "stranger"]);
        let chosen =
            choose_figures(&available, Some("stranger"), Some("imp:plusz")).expect("a pair");
        assert_eq!(chosen.player.name, "stranger");
        assert_eq!(
            chosen.player.front, UNKNOWN_FIGURE_FRONT,
            "an unknown figure follows the convention"
        );
        assert_eq!(chosen.enemy.name, "imp");
        assert_eq!(
            chosen.enemy.front,
            AuthoredFront::PlusZ,
            "the suffix overrules the table"
        );
    }

    #[test]
    fn a_pack_without_a_player_figure_says_what_it_has() {
        let error = choose_figures(&names(&["imp", "pillar"]), None, None).expect_err("no player");
        let message = error.to_string();
        assert!(message.contains("no player figure"), "{message}");
        assert!(message.contains("`witch`"), "{message}");
        assert!(message.contains("`imp`"), "{message}");
        assert!(message.contains(FNP_PLAYER_FIGURE_VAR), "{message}");
    }

    #[test]
    fn an_override_that_names_nothing_in_the_pack_is_refused() {
        let available = names(&["imp", "soul"]);
        let error = choose_figures(&available, Some("witch"), None).expect_err("not in the pack");
        assert!(
            matches!(&error, FigureChoiceError::Missing { name, .. } if name == "witch"),
            "{error}"
        );
        let error = choose_figures(&available, Some("soul:sideways"), None).expect_err("invalid");
        assert!(matches!(error, FigureChoiceError::InvalidOverride { .. }));
        let error = choose_figures(&available, Some(""), None).expect_err("empty");
        assert!(matches!(error, FigureChoiceError::InvalidOverride { .. }));
    }
}
