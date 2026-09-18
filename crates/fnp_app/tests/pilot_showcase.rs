//! Offscreen showcase of imported figures next to the procedural ones, and a crowd of them, in the
//! engine's own main loop and renderer (MSAA 4x, the game camera presets).
//!
//! Two scenes, both offscreen and both with the software adapter:
//!
//! - `comparison`: every figure of the pack in a row facing the camera, the posed one twice — once
//!   in its rest pose, once in a pose sampled offline (`assets_src/asset_import/sample_pose.py`,
//!   the engine has no animation system; `tests/data/*.pose` is that sample).
//! - `crowd`: `FNP_PILOT_CROWD` copies of the last figure plus the posed one in front, to measure
//!   what skinned figures cost on the CPU side (extraction, render submission, the joint matrices
//!   uploaded per frame).
//! - `floor`: the arena floor alone, the reference image for measuring a figure's brightness
//!   against the floor it stands on.
//!
//! Needs a figure pack and a GPU adapter, so it is `#[ignore]`d and runs only on request:
//!
//! ```text
//! FNP_PILOT_PACK=<vergleich.pack> FNP_PILOT_DIR=<output dir> GRIMOIRE_GPU_ADAPTER=software \
//!   cargo test --release -p fnp_app --test pilot_showcase -- --ignored --nocapture
//! ```
//!
//! Optional: `FNP_PILOT_SCENE=comparison|crowd|floor` (default `comparison`),
//! `FNP_PILOT_CAMERA=0|1|2`
//! (preset A, B or C), `FNP_PILOT_SIZE=<w>x<h>` (default 1920x1080), `FNP_PILOT_FRAMES=<n>`
//! (default 4; the last frame is the captured one), `FNP_PILOT_FIGURES=<names>` (default
//! `soul,imp,witch,imp_hi3d`), `FNP_PILOT_PLUSZ=<names>` (figures authored the way the game expects,
//! default `witch,imp_hi3d`), `FNP_PILOT_POSE=<file>`, `FNP_PILOT_CROWD=<n>` (default 30),
//! `FNP_PILOT_MSAA=on|off` (default on), `FNP_PILOT_TAG=<name>` (file name of the capture),
//! `FNP_PILOT_JSON=<file>` (the measurements). Frames are written as binary PPM, like the arena
//! capture, so this crate needs no image dependency.

use std::cell::RefCell;
use std::io::Write;
use std::path::PathBuf;
use std::rc::Rc;
use std::time::{Duration, Instant};

use fnp_app::arena_floor;
use fnp_app::figures::PACK_FIGURES_FRONT;
use fnp_app::stage::stage_renderer_config;
use fnp_game::TICK_RATE_HZ;
use fnp_game::arena::present::{
    ArenaDistrict, AuthoredFront, CAMERA_PRESETS, FigureVisual, Mat4, apply_arena_lighting,
    camera_preset, floor_material, mul, player_lantern, rotation_z, stage_mesh_data, translation,
};
use grimoire::adapters::figure_assets::load_figure_into;
use grimoire::debug::FrameProfile;
use grimoire::platform::StdFileSystem;
use grimoire::prelude::*;
use grimoire::render::figure_format::{JointPose, SkeletonData, compute_skin_matrices};
use grimoire::render::{
    BlobShadowInstance, MaterialHandle, MeshHandle, MeshInstance, MeshRole, Msaa, SkinBinding,
    TextureHandle,
};
use grimoire::{OffscreenRun, PluginError, RenderAssets};
use grimoire_assets::{AssetStore, PackReader};

// ------------------------------------------------------------------------------- pose files

/// One frame of one clip, sampled offline into `tests/data/<figure>_<clip>_frame_<n>.pose`.
#[derive(Debug, Clone, PartialEq)]
struct SampledPose {
    figure: String,
    clip: String,
    frame: u64,
    joints: Vec<(String, JointPose)>,
}

/// Reads the pose format written by `assets_src/asset_import/sample_pose.py`: a header of
/// `key value` lines, then one `joint <name> tx ty tz qx qy qz qw sx sy sz` line per joint, in the
/// pack's joint order.
fn parse_pose(text: &str) -> Result<SampledPose, String> {
    let mut figure = String::new();
    let mut clip = String::new();
    let mut frame = 0_u64;
    let mut declared = None;
    let mut joints = Vec::new();
    for (number, line) in text.lines().enumerate() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let where_ = || format!("line {}", number + 1);
        let (key, rest) = line
            .split_once(' ')
            .ok_or_else(|| format!("{}: no value", where_()))?;
        match key {
            "figure" => figure = rest.to_owned(),
            "clip" => clip = rest.to_owned(),
            "frame" => frame = rest.parse().map_err(|_| format!("{}: frame", where_()))?,
            "joints" => {
                declared = Some(
                    rest.parse::<usize>()
                        .map_err(|_| format!("{}: joints", where_()))?,
                );
            }
            "fps" | "time" => {}
            "joint" => {
                let mut fields = rest.split_whitespace();
                let name = fields
                    .next()
                    .ok_or_else(|| format!("{}: joint name", where_()))?;
                let mut numbers = [0.0_f32; 10];
                for slot in &mut numbers {
                    let field = fields
                        .next()
                        .ok_or_else(|| format!("{}: 10 numbers", where_()))?;
                    *slot = field
                        .parse()
                        .map_err(|_| format!("{}: {field:?}", where_()))?;
                }
                if fields.next().is_some() {
                    return Err(format!("{}: more than 10 numbers", where_()));
                }
                joints.push((
                    name.to_owned(),
                    JointPose {
                        translation: [numbers[0], numbers[1], numbers[2]],
                        rotation: [numbers[3], numbers[4], numbers[5], numbers[6]],
                        scale: [numbers[7], numbers[8], numbers[9]],
                    },
                ));
            }
            other => return Err(format!("{}: unknown key {other:?}", where_())),
        }
    }
    if let Some(declared) = declared
        && declared != joints.len()
    {
        return Err(format!(
            "header says {declared} joints, file has {}",
            joints.len()
        ));
    }
    if joints.is_empty() {
        return Err(String::from("no joints"));
    }
    Ok(SampledPose {
        figure,
        clip,
        frame,
        joints,
    })
}

/// Skinning matrices of `pose` for `skeleton`, matched by joint name (not by position, so a
/// reordered pack fails loudly instead of bending the figure into nonsense).
fn pose_matrices(skeleton: &SkeletonData, pose: &SampledPose) -> Result<Vec<Mat4>, String> {
    if pose.joints.len() != skeleton.joints.len() {
        return Err(format!(
            "pose has {} joints, the skeleton {}",
            pose.joints.len(),
            skeleton.joints.len()
        ));
    }
    let mut poses = Vec::with_capacity(skeleton.joints.len());
    for joint in &skeleton.joints {
        let sampled = pose
            .joints
            .iter()
            .find(|(name, _)| *name == joint.name)
            .ok_or_else(|| format!("the pose has no joint {:?}", joint.name))?;
        poses.push(sampled.1);
    }
    compute_skin_matrices(skeleton, &poses).map_err(|error| error.to_string())
}

// ---------------------------------------------------------------------------------- the scene

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Scene {
    Comparison,
    Crowd,
    /// The floor alone: the reference image the figures' brightness is measured against.
    Floor,
}

/// Where the figures of the comparison stand: a row along X, centred, facing the camera.
fn row_positions(count: usize, spacing: f32) -> Vec<[f32; 2]> {
    let first = -spacing * (count.saturating_sub(1) as f32) / 2.0;
    (0..count)
        .map(|index| [first + spacing * index as f32, 0.0])
        .collect()
}

/// Where the crowd stands: rows behind the player, filled from the middle outwards, so ten and
/// thirty enemies frame the same centre.
fn crowd_positions(count: usize, spacing: f32) -> Vec<[f32; 2]> {
    let per_row = 6_usize;
    (0..count)
        .map(|index| {
            let row = index / per_row;
            let column = index % per_row;
            let x = (column as f32 - (per_row - 1) as f32 / 2.0) * spacing;
            [x, 1.6 + row as f32 * spacing * 0.9]
        })
        .collect()
}

struct ShowcaseFigure {
    /// Name inside the pack, for the load log and the summary.
    #[allow(dead_code, reason = "read through the load log only")]
    name: String,
    visual: FigureVisual,
    skeleton: SkeletonData,
}

/// What one showcase run measured.
///
/// The offscreen loop advances its clock by hand, so every profiler scope that is measured against
/// that clock reads zero; only the renderer's own `gpu` estimate is a wall-clock number. The
/// CPU-side costs here are therefore taken with [`Instant`]: the extraction is timed inside the
/// plugin, the whole frame between two [`GamePlugin::on_frame`] calls.
#[derive(Debug, Clone, Default, PartialEq)]
struct ShowcaseStats {
    frames: u64,
    figures_drawn: usize,
    mesh_instances: usize,
    joint_matrices: usize,
    /// Wall time of this plugin's `extract_stage`.
    extract_total: Duration,
    extract_max: Duration,
    /// Wall time between two frames of the loop (extraction, render submission, readback).
    frame_times: Vec<Duration>,
    /// Scope name, summed time, calls, whether the engine marked it an estimate.
    scopes: Vec<(String, Duration, u32, bool)>,
}

impl ShowcaseStats {
    fn add_scope(&mut self, name: &str, total: Duration, calls: u32, estimate: bool) {
        if let Some(entry) = self.scopes.iter_mut().find(|entry| entry.0 == name) {
            entry.1 += total;
            entry.2 += calls;
            entry.3 |= estimate;
        } else {
            self.scopes.push((name.to_owned(), total, calls, estimate));
        }
    }

    fn extract_ms(&self) -> f64 {
        self.extract_total.as_secs_f64() * 1000.0 / f64::from(self.frames.max(1) as u32)
    }

    /// Average frame wall time without the first measured frame: the first one builds the
    /// pipelines and the swap targets and is an order of magnitude slower.
    fn frame_ms(&self) -> f64 {
        let settled = self.frame_times.get(1..).unwrap_or_default();
        if settled.is_empty() {
            return self.frame_times.first().map_or(0.0, Duration::as_secs_f64) * 1000.0;
        }
        settled.iter().sum::<Duration>().as_secs_f64() * 1000.0 / settled.len() as f64
    }

    fn frame_min_ms(&self) -> f64 {
        self.frame_times
            .iter()
            .min()
            .map_or(0.0, |value| value.as_secs_f64() * 1000.0)
    }

    fn scope_ms(&self, name: &str) -> f64 {
        self.scopes
            .iter()
            .find(|entry| entry.0 == name)
            .map_or(0.0, |entry| {
                entry.1.as_secs_f64() * 1000.0 / f64::from(entry.2.max(1))
            })
    }
}

type Shared<T> = Rc<RefCell<T>>;

struct ShowcaseStage {
    pack: PathBuf,
    names: Vec<String>,
    plus_z: Vec<String>,
    pose: Option<SampledPose>,
    scene: Scene,
    crowd: usize,
    camera_preset: usize,
    figures: Vec<ShowcaseFigure>,
    /// Skinning matrices of the sampled pose and the figure they belong to (by name).
    posed: Option<(usize, Vec<Mat4>)>,
    floor: Option<MeshHandle>,
    floor_textures: Option<[TextureHandle; 3]>,
    stats: Shared<ShowcaseStats>,
    last_frame_at: Option<Instant>,
}

impl ShowcaseStage {
    fn front_of(&self, name: &str) -> AuthoredFront {
        if self.plus_z.iter().any(|entry| entry == name) {
            AuthoredFront::PlusZ
        } else {
            PACK_FIGURES_FRONT
        }
    }

    /// Appends one skinned figure with `pose` as its skinning matrices.
    fn push_figure(
        &self,
        figure: &ShowcaseFigure,
        at: [f32; 2],
        yaw: f32,
        pose: &[Mat4],
        frame: &mut StageFrame,
    ) {
        let transform = mul(
            mul(
                translation([at[0], at[1], figure.visual.ground_lift]),
                rotation_z(yaw),
            ),
            figure.visual.authored_front.correction(),
        );
        let joint_offset = u32::try_from(frame.joint_matrices.len()).unwrap_or(u32::MAX);
        let joint_count = u32::try_from(pose.len()).unwrap_or(0);
        frame.joint_matrices.extend_from_slice(pose);
        let mut skin = SkinBinding::default();
        skin.joint_offset = joint_offset;
        skin.joint_count = joint_count;
        for part in &figure.visual.parts {
            let material = u32::try_from(frame.materials.len()).unwrap_or(0);
            frame.materials.push(part.material);
            let mut instance = MeshInstance::default();
            instance.mesh = part.mesh;
            instance.material = MaterialHandle(material);
            instance.transform = transform;
            instance.skin = Some(skin);
            instance.role = MeshRole::Actor;
            frame.meshes.push(instance);
        }
        // Match the player's local fill light in the playable arena. Otherwise a
        // near-black figure against this dark floor looks much worse in the pilot
        // than it does in the actual game.
        frame
            .point_lights
            .push(player_lantern(Vec2::new(at[0], at[1])));
        frame.blob_shadows.push(BlobShadowInstance {
            position: at,
            radius: 0.55,
            softness: 0.6,
            strength: 0.6,
        });
    }
}

impl GamePlugin for ShowcaseStage {
    fn name(&self) -> &str {
        "fiends_n_patrons.pilot_showcase"
    }

    fn register_assets(&mut self, assets: &mut dyn RenderAssets) -> Result<(), PluginError> {
        let reader = PackReader::open(&StdFileSystem, &self.pack)?;
        let mut store = AssetStore::new(Box::new(reader));
        for name in &self.names {
            let loaded = load_figure_into(&mut store, assets, name)?;
            let visual = FigureVisual::from_loaded(&loaded, self.front_of(name));
            eprintln!(
                "fnp-pilot: {name} loaded: {} parts, {} joints, {:.2} m, front {:?}",
                visual.parts.len(),
                loaded.skeleton.joints.len(),
                visual.height,
                visual.authored_front
            );
            self.figures.push(ShowcaseFigure {
                name: name.clone(),
                visual,
                skeleton: loaded.skeleton,
            });
        }
        if let Some(pose) = &self.pose {
            // The pose names its figure; applying it to another one would bend a foreign skeleton.
            let index = self
                .figures
                .iter()
                .position(|figure| figure.name == pose.figure)
                .ok_or_else(|| {
                    format!(
                        "the pose is for figure {:?}, which the pack run does not include ({:?})",
                        pose.figure, self.names
                    )
                })?;
            let matrices = pose_matrices(&self.figures[index].skeleton, pose)?;
            eprintln!(
                "fnp-pilot: pose {} frame {} applied to {}",
                pose.clip, pose.frame, pose.figure
            );
            self.posed = Some((index, matrices));
        }
        self.floor = Some(assets.register_mesh(stage_mesh_data().floor)?);
        self.floor_textures = Some(arena_floor::register(assets, ArenaDistrict::Crypt)?);
        Ok(())
    }

    fn extract_stage(&mut self, _world: &World, _alpha: f32, frame: &mut StageFrame) {
        let started = Instant::now();
        let mut camera = camera_preset(self.camera_preset);
        camera.target = [0.0, 0.0];
        frame.camera_25d = Some(camera);
        apply_arena_lighting(frame);

        let floor_material_index = u32::try_from(frame.materials.len()).unwrap_or(0);
        frame.materials.push(floor_material(self.floor_textures));
        if let Some(floor) = self.floor {
            let mut instance = MeshInstance::default();
            instance.mesh = floor;
            instance.material = MaterialHandle(floor_material_index);
            frame.meshes.push(instance);
        }

        let mut drawn = 0_usize;
        match self.scene {
            Scene::Floor => {}
            Scene::Comparison => {
                // Every figure once in its rest pose, the posed one a second time right next to
                // itself, so rest and pose stand side by side at the same size.
                let mut entries: Vec<(&ShowcaseFigure, &[Mat4])> = Vec::new();
                for (index, figure) in self.figures.iter().enumerate() {
                    entries.push((figure, figure.visual.rest_pose.as_slice()));
                    if let Some((posed_index, matrices)) = &self.posed
                        && *posed_index == index
                    {
                        entries.push((figure, matrices.as_slice()));
                    }
                }
                for (position, (figure, pose)) in
                    row_positions(entries.len(), 1.35).into_iter().zip(entries)
                {
                    self.push_figure(figure, position, 0.0, pose, frame);
                    drawn += 1;
                }
            }
            Scene::Crowd => {
                if let Some(enemy) = self.figures.last() {
                    for (index, position) in
                        crowd_positions(self.crowd, 1.2).into_iter().enumerate()
                    {
                        // A deterministic spread of yaws: a crowd, not a parade.
                        let yaw = (index as f32) * 0.37;
                        self.push_figure(enemy, position, yaw, &enemy.visual.rest_pose, frame);
                        drawn += 1;
                    }
                }
                let player_index = self.posed.as_ref().map_or(0, |(index, _)| *index);
                if let Some(player) = self.figures.get(player_index) {
                    let pose = self
                        .posed
                        .as_ref()
                        .map_or(player.visual.rest_pose.as_slice(), |(_, matrices)| {
                            matrices.as_slice()
                        });
                    self.push_figure(player, [0.0, -1.2], 0.0, pose, frame);
                    drawn += 1;
                }
            }
        }
        let elapsed = started.elapsed();
        let mut stats = self.stats.borrow_mut();
        stats.figures_drawn = drawn;
        stats.mesh_instances = frame.meshes.len();
        stats.joint_matrices = frame.joint_matrices.len();
        stats.extract_total += elapsed;
        stats.extract_max = stats.extract_max.max(elapsed);
    }

    fn on_frame(&mut self, _frame: &FrameStats) {
        let now = Instant::now();
        let mut stats = self.stats.borrow_mut();
        stats.frames += 1;
        if let Some(previous) = self.last_frame_at {
            stats.frame_times.push(now.duration_since(previous));
        }
        self.last_frame_at = Some(now);
    }

    fn on_profile(&mut self, profile: &FrameProfile) {
        let mut stats = self.stats.borrow_mut();
        for scope in profile.scopes() {
            let name = profile.scope_name(scope.scope).unwrap_or("?");
            stats.add_scope(name, scope.total, scope.calls, scope.estimate);
        }
    }
}

// ----------------------------------------------------------------------------------- the test

fn env_or<T: std::str::FromStr>(name: &str, default: T) -> T {
    std::env::var(name)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}

fn env_list(name: &str, default: &str) -> Vec<String> {
    std::env::var(name)
        .unwrap_or_else(|_| default.to_owned())
        .split(',')
        .map(|entry| entry.trim().to_owned())
        .filter(|entry| !entry.is_empty())
        .collect()
}

fn write_ppm(path: &PathBuf, size: (u32, u32), rgba: &[u8]) -> std::io::Result<()> {
    let mut file = std::io::BufWriter::new(std::fs::File::create(path)?);
    write!(file, "P6\n{} {}\n255\n", size.0, size.1)?;
    for pixel in rgba.as_chunks::<4>().0 {
        file.write_all(&pixel[..3])?;
    }
    file.flush()
}

#[test]
#[ignore = "needs a figure pack (FNP_PILOT_PACK), an output directory (FNP_PILOT_DIR) and a GPU adapter"]
fn capture_the_pilot_showcase() {
    let (Some(pack), Some(dir)) = (
        std::env::var_os("FNP_PILOT_PACK"),
        std::env::var_os("FNP_PILOT_DIR"),
    ) else {
        eprintln!("FNP_PILOT_PACK or FNP_PILOT_DIR not set; skipping the showcase");
        return;
    };
    let dir = PathBuf::from(dir);
    std::fs::create_dir_all(&dir).expect("the output directory can be created");
    let scene = match std::env::var("FNP_PILOT_SCENE").as_deref() {
        Ok("crowd") => Scene::Crowd,
        Ok("floor") => Scene::Floor,
        Ok("comparison") | Err(_) => Scene::Comparison,
        Ok(other) => panic!("unknown FNP_PILOT_SCENE {other:?}"),
    };
    let size = std::env::var("FNP_PILOT_SIZE")
        .ok()
        .and_then(|value| {
            let (w, h) = value.split_once('x')?;
            Some((w.parse().ok()?, h.parse().ok()?))
        })
        .unwrap_or((1920, 1080));
    let frames: u64 = env_or("FNP_PILOT_FRAMES", 4).max(1);
    let camera_preset_index: usize = env_or("FNP_PILOT_CAMERA", 0) % CAMERA_PRESETS.len();
    let pose = std::env::var_os("FNP_PILOT_POSE").map(|path| {
        let text = std::fs::read_to_string(&path).expect("the pose file can be read");
        parse_pose(&text).expect("the pose file parses")
    });
    let tag = std::env::var("FNP_PILOT_TAG").unwrap_or_else(|_| {
        let preset = CAMERA_PRESETS[camera_preset_index];
        match scene {
            Scene::Comparison => format!("comparison_{}", preset.name.to_lowercase()),
            Scene::Crowd => format!("crowd_{}", preset.name.to_lowercase()),
            Scene::Floor => format!("floor_{}", preset.name.to_lowercase()),
        }
    });

    let stage = ShowcaseStage {
        pack: PathBuf::from(pack),
        names: env_list("FNP_PILOT_FIGURES", "soul,imp,witch,imp_hi3d"),
        plus_z: env_list("FNP_PILOT_PLUSZ", "witch,imp_hi3d"),
        pose,
        scene,
        crowd: env_or("FNP_PILOT_CROWD", 30),
        camera_preset: camera_preset_index,
        figures: Vec::new(),
        posed: None,
        floor: None,
        floor_textures: None,
        stats: Rc::default(),
        last_frame_at: None,
    };
    let stats = Rc::clone(&stage.stats);
    let mut config = stage_renderer_config();
    if std::env::var("FNP_PILOT_MSAA").as_deref() == Ok("off") {
        config.msaa = Msaa::Off;
    }
    let msaa_name = if config.msaa == Msaa::Off {
        "off"
    } else {
        "4x"
    };
    let app = App::new(WindowConfig::default())
        .seed(7)
        .tick_rate(TICK_RATE_HZ)
        .stage_renderer_config(config)
        .plugin(stage);

    let frame_delta = Duration::from_nanos(1_000_000_000 / u64::from(TICK_RATE_HZ));
    let mut run = OffscreenRun::new(size.0, size.1, frames, frame_delta);
    // Only the last frame: the scene is static, and the first frames warm the pipeline up.
    run.capture_every = frames.saturating_sub(1).max(1);
    let started = Instant::now();
    let mut written = 0_u64;
    let mut write_error = None;
    let mut last_path = None;
    let result = app.run_offscreen(run, &mut |_, _| {}, &mut |_, rgba| {
        let path = dir.join(format!("{tag}_{written:02}.ppm"));
        if let Err(error) = write_ppm(&path, size, rgba) {
            write_error.get_or_insert(error);
        }
        last_path = Some(path);
        written += 1;
    });
    let report = match result {
        Ok(report) => report,
        Err(grimoire::GrimoireError::Render(grimoire::render::RenderError::NoAdapter)) => {
            eprintln!("no GPU adapter available; skipping the showcase");
            return;
        }
        Err(error) => panic!("the showcase run failed: {error}"),
    };
    assert!(write_error.is_none(), "writing a frame: {write_error:?}");
    assert_eq!(report.frames, frames);

    let stats = stats.borrow().clone();
    if scene == Scene::Floor {
        assert_eq!(
            stats.figures_drawn, 0,
            "the floor scene draws no figure: {stats:?}"
        );
    } else {
        assert!(stats.figures_drawn > 0, "the scene drew figures: {stats:?}");
        assert!(
            stats.joint_matrices >= stats.figures_drawn,
            "every figure uploaded its joint matrices: {stats:?}"
        );
    }
    let preset = CAMERA_PRESETS[camera_preset_index];
    let gpu_estimate = stats.scopes.iter().any(|entry| entry.0 == "gpu" && entry.3);
    let summary = format!(
        "fnp-pilot: {tag} camera {} ({:.0} deg, {} m), msaa {msaa_name}, {}x{}, {} figures, \
         {} mesh instances, {} joint matrices ({} bytes per frame); extract {:.3} ms avg \
         {:.3} ms max; frame {:.1} ms avg (without the warm-up) {:.1} ms min; renderer \
         {:.1} ms{}; {} frames in {:.1} s wall",
        preset.name,
        preset.tilt_degrees,
        preset.distance,
        size.0,
        size.1,
        stats.figures_drawn,
        stats.mesh_instances,
        stats.joint_matrices,
        stats.joint_matrices * 64,
        stats.extract_ms(),
        stats.extract_max.as_secs_f64() * 1000.0,
        stats.frame_ms(),
        stats.frame_min_ms(),
        stats.scope_ms("gpu"),
        if gpu_estimate {
            " (the software adapter has no timestamps: this is the wall time of the render call, \
             mostly software rasterisation, not a GPU number)"
        } else {
            ""
        },
        report.frames,
        started.elapsed().as_secs_f64()
    );
    println!("{summary}");
    if let Some(path) = std::env::var_os("FNP_PILOT_JSON") {
        let json = format!(
            "{{\n  \"tag\": \"{tag}\",\n  \"scene\": \"{}\",\n  \"camera\": \"{}\",\n  \
             \"tilt_degrees\": {},\n  \"distance_m\": {},\n  \"msaa\": \"{msaa_name}\",\n  \
             \"width\": {},\n  \"height\": {},\n  \"figures\": {},\n  \
             \"mesh_instances\": {},\n  \"joint_matrices\": {},\n  \
             \"joint_bytes_per_frame\": {},\n  \"extract_avg_ms\": {:.4},\n  \
             \"extract_max_ms\": {:.4},\n  \"frame_avg_ms\": {:.3},\n  \
             \"frame_min_ms\": {:.3},\n  \"renderer_ms\": {:.3},\n  \
             \"renderer_is_software_rasterisation\": {},\n  \"frames\": {}\n}}\n",
            match scene {
                Scene::Comparison => "comparison",
                Scene::Crowd => "crowd",
                Scene::Floor => "floor",
            },
            preset.name,
            preset.tilt_degrees,
            preset.distance,
            size.0,
            size.1,
            stats.figures_drawn,
            stats.mesh_instances,
            stats.joint_matrices,
            stats.joint_matrices * 64,
            stats.extract_ms(),
            stats.extract_max.as_secs_f64() * 1000.0,
            stats.frame_ms(),
            stats.frame_min_ms(),
            stats.scope_ms("gpu"),
            gpu_estimate,
            report.frames
        );
        std::fs::write(path, json).expect("the measurement file can be written");
    }
    if let Some(path) = last_path {
        println!("fnp-pilot: last frame written to {}", path.display());
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const POSE: &str = "\
# fnp pose v1
figure witch
clip melee_1
frame 6
fps 24
time 0.250000
joints 2
joint root 0 0 1 0.7071068 0 0 0.7071068 1 1 1
joint pelvis 0 0.4 0 0 0 0 1 1 1 1
";

    fn two_joint_skeleton() -> SkeletonData {
        use grimoire::render::figure_format::JointData;
        let identity = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ];
        SkeletonData {
            joints: vec![
                JointData {
                    parent: None,
                    inverse_bind: identity,
                    name: String::from("root"),
                    translation: [0.0; 3],
                    rotation: [0.0, 0.0, 0.0, 1.0],
                    scale: [1.0; 3],
                },
                JointData {
                    parent: Some(0),
                    inverse_bind: identity,
                    name: String::from("pelvis"),
                    translation: [0.0; 3],
                    rotation: [0.0, 0.0, 0.0, 1.0],
                    scale: [1.0; 3],
                },
            ],
        }
    }

    #[test]
    fn a_pose_file_parses_into_joint_poses() {
        let pose = parse_pose(POSE).expect("parses");
        assert_eq!(
            (pose.figure.as_str(), pose.clip.as_str(), pose.frame),
            ("witch", "melee_1", 6)
        );
        assert_eq!(pose.joints.len(), 2);
        assert_eq!(pose.joints[1].0, "pelvis");
        assert_eq!(pose.joints[1].1.translation, [0.0, 0.4, 0.0]);
    }

    #[test]
    fn a_pose_file_is_checked_against_the_skeleton_by_name() {
        let skeleton = two_joint_skeleton();
        let pose = parse_pose(POSE).expect("parses");
        let matrices = pose_matrices(&skeleton, &pose).expect("matches the skeleton");
        assert_eq!(matrices.len(), 2);
        // The root's sampled translation moves both joints by one unit along Z.
        assert_eq!(matrices[0][3], [0.0, 0.0, 1.0, 1.0]);

        let mut renamed = pose.clone();
        renamed.joints[1].0 = String::from("hip");
        let error = pose_matrices(&skeleton, &renamed).expect_err("a renamed joint fails");
        assert!(error.contains("pelvis"), "{error}");
    }

    #[test]
    fn broken_pose_files_are_rejected() {
        assert!(parse_pose("").is_err());
        assert!(parse_pose("joints 3\njoint a 0 0 0 0 0 0 1 1 1 1\n").is_err());
        assert!(parse_pose("joint a 0 0 0 0 0 0 1 1 1\n").is_err());
        assert!(parse_pose("colour red\n").is_err());
    }

    #[test]
    fn the_layouts_are_centred_and_deterministic() {
        let row = row_positions(4, 1.5);
        assert_eq!(row.len(), 4);
        assert!((row[0][0] + row[3][0]).abs() < 1e-6, "{row:?}");
        assert!((row[1][0] - (-0.75)).abs() < 1e-6, "{row:?}");
        assert!(row.iter().all(|position| position[1] == 0.0));

        let crowd = crowd_positions(30, 1.2);
        assert_eq!(crowd.len(), 30);
        assert_eq!(crowd_positions(10, 1.2)[..6], crowd[..6]);
        assert!(
            crowd.iter().all(|position| position[1] > 0.0),
            "behind the player"
        );
        let sum: f32 = crowd.iter().map(|position| position[0]).sum();
        assert!(sum.abs() < 1e-4, "centred in x: {sum}");
    }
}
