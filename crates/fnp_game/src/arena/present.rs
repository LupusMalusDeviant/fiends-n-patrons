//! Presentation of the arena: turns the simulated world into a [`StageFrame`].
//!
//! Everything here reads `&World` and writes only the frame; nothing flows back into the
//! simulation. The executable's stage plugin registers the meshes and textures once through the
//! engine's asset hook ([`stage_mesh_data`], a figure pack) and hands the handles in as
//! [`ArenaVisuals`].
//!
//! **Bullets** go through the engine's path only: the facade adapter
//! [`grimoire::adapters::sigil_render::extract_bullets`] turns the live pool into
//! [`StageFrame::bullets`] (contract §9.9), the renderer's bullet pass draws them as billboards on
//! layer 6 and derives the bullet lights itself through `point_light_from_bullet` (contract §6,
//! WP3.5). The game builds no bullet meshes and no bullet lights.

use grimoire::adapters::figure_assets::{LoadedFigure, LoadedFigurePart};
use grimoire::adapters::sigil_render::{BulletExtractionStats, extract_bullets};
use grimoire::prelude::*;
use grimoire::render::figure_clip::{ClipData, ClipSampler, sample_pose_into};
use grimoire::render::figure_format::{
    JointPose, SkeletonData, compute_skin_matrices, rest_pose_skin_matrices,
};
use grimoire::render::procedural::{altar_block, floor_tile_grid, octagonal_pillar};
use grimoire::render::{
    AmbientLight, BlobShadowInstance, DirectionalLight, MaterialHandle, MeshData, MeshHandle,
    MeshInstance, MeshRole, MeshVertex, PbrMaterial, PointLight, ShadowConfig, ShadowMode,
    SkinBinding,
};
use grimoire::sigil::BulletPool;

use super::{
    ARENA_HALF, ArenaMode, Facing, HIT_RECOVERY_TICKS, IMP_POSITION, Imp, Mode,
    PLAYER_HIT_HALF_WIDTH, PLAYER_HIT_RADIUS, Phase, RoundState,
};
use crate::{Player, Position, PreviousPosition, Velocity};

/// Column-major 4x4 matrix, the convention of [`MeshInstance::transform`].
pub type Mat4 = [[f32; 4]; 4];

const IDENTITY: Mat4 = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.0],
    [0.0, 0.0, 0.0, 1.0],
];

/// Height of the imp's plinth.
pub const PLINTH_HEIGHT: f32 = 0.3;

/// Side tiles of the square floor.
const FLOOR_TILES: u32 = 24;
/// Edge length of one floor tile.
const FLOOR_TILE_SIZE: f32 = 2.0;
/// Radius and height of the arena pillars.
const PILLAR_RADIUS: f32 = 0.5;
const PILLAR_HEIGHT: f32 = 3.2;
/// Height of the braziers on the near edge.
const BRAZIER_HEIGHT: f32 = 0.8;
/// How far the camera's follow point leans from the player towards the imp's side of the arena.
const CAMERA_ANCHOR: Vec2 = Vec2::new(0.0, 1.5);
/// Share of the player's own position in the camera's follow point.
const CAMERA_FOLLOW_SHARE: f32 = 0.7;
/// Height and depth of the curb that marks the arena edge.
const CURB_HEIGHT: f32 = 0.3;
const CURB_DEPTH: f32 = 0.5;
/// Distance of the curb's inner face from the walkable edge (the hit capsule's reach).
const CURB_GAP: f32 = 0.45;
/// Ticks the soul takes to fall into its hit pose.
const HIT_FALL_TICKS: f32 = 8.0;
/// Ticks per step of the hit blink: two steps shown, one hidden.
const HIT_BLINK_TICKS: u64 = 4;
/// Ticks of the rise-in at the start of a round.
const RESPAWN_TICKS: f32 = 18.0;

/// sRGB hex colour to linear RGB (presentation constants only).
fn linear(hex: u32) -> [f32; 3] {
    fn channel(byte: u32) -> f32 {
        let c = byte as f32 / 255.0;
        if c <= 0.04045 {
            c / 12.92
        } else {
            dmath::powf((c + 0.055) / 1.055, 2.4)
        }
    }
    [
        channel((hex >> 16) & 0xFF),
        channel((hex >> 8) & 0xFF),
        channel(hex & 0xFF),
    ]
}

fn scale3(color: [f32; 3], factor: f32) -> [f32; 3] {
    [color[0] * factor, color[1] * factor, color[2] * factor]
}

fn material(color: [f32; 3], roughness: f32, emissive: [f32; 3]) -> PbrMaterial {
    let mut material = PbrMaterial::default();
    material.base_color_factor = [color[0], color[1], color[2], 1.0];
    material.metallic_factor = 0.0;
    material.roughness_factor = roughness;
    material.emissive_factor = emissive;
    material
}

/// Column-major product `a * b` (`a` applied after `b`).
#[must_use]
pub fn mul(a: Mat4, b: Mat4) -> Mat4 {
    let mut result = [[0.0_f32; 4]; 4];
    for (col, out) in result.iter_mut().enumerate() {
        for (row, value) in out.iter_mut().enumerate() {
            *value = (0..4).map(|k| a[k][row] * b[col][k]).sum();
        }
    }
    result
}

/// Translation matrix.
#[must_use]
pub fn translation(t: [f32; 3]) -> Mat4 {
    let mut m = IDENTITY;
    m[3] = [t[0], t[1], t[2], 1.0];
    m
}

/// Rotation about +Z by `radians` (counter-clockwise seen from above).
#[must_use]
pub fn rotation_z(radians: f32) -> Mat4 {
    let (s, c) = (dmath::sin(radians), dmath::cos(radians));
    [
        [c, s, 0.0, 0.0],
        [-s, c, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
}

/// Rotation about +X by `radians`.
#[must_use]
pub fn rotation_x(radians: f32) -> Mat4 {
    let (s, c) = (dmath::sin(radians), dmath::cos(radians));
    [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, c, s, 0.0],
        [0.0, -s, c, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
}

/// Non-uniform scale matrix.
#[must_use]
pub fn scale(s: [f32; 3]) -> Mat4 {
    [
        [s[0], 0.0, 0.0, 0.0],
        [0.0, s[1], 0.0, 0.0],
        [0.0, 0.0, s[2], 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
}

/// Yaw that turns a figure whose front follows the game's convention to face `direction`.
///
/// Convention: a figure's front looks along glTF +Z, like the glTF standard and the Hi3D assets.
/// The skeleton root's axis rotation (glTF Y-up to engine Z-up) turns glTF +Z into engine -Y,
/// towards the viewer, so an unrotated figure faces the camera. A figure authored the other way
/// round says so with [`AuthoredFront::MinusZ`] and is turned by half a turn first
/// ([`AuthoredFront::correction`]).
#[must_use]
pub fn facing_yaw(direction: Vec2) -> f32 {
    dmath::atan2(direction.x, -direction.y)
}

/// Which way a figure's model looks in glTF space.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AuthoredFront {
    /// glTF +Z, the game's convention (glTF standard, Hi3D assets).
    PlusZ,
    /// glTF -Z: turned by half a turn so it follows the convention.
    MinusZ,
}

impl AuthoredFront {
    /// Model-space rotation that turns the figure's authored front into the convention's front;
    /// applied before every other transform of the figure.
    #[must_use]
    pub fn correction(self) -> Mat4 {
        match self {
            AuthoredFront::PlusZ => IDENTITY,
            AuthoredFront::MinusZ => rotation_z(dmath::PI),
        }
    }
}

/// Hamilton product of two `[x, y, z, w]` quaternions.
fn quat_mul(a: [f32; 4], b: [f32; 4]) -> [f32; 4] {
    [
        a[3] * b[0] + a[0] * b[3] + a[1] * b[2] - a[2] * b[1],
        a[3] * b[1] - a[0] * b[2] + a[1] * b[3] + a[2] * b[0],
        a[3] * b[2] + a[0] * b[1] - a[1] * b[0] + a[2] * b[3],
        a[3] * b[3] - a[0] * b[0] - a[1] * b[1] - a[2] * b[2],
    ]
}

/// A crumpled pose: every non-root joint bends a little further about its local X axis.
fn crumpled_pose(skeleton: &SkeletonData, radians: f32) -> Option<Vec<Mat4>> {
    let half = radians * 0.5;
    let bend = [dmath::sin(half), 0.0, 0.0, dmath::cos(half)];
    let poses: Vec<JointPose> = skeleton
        .joints
        .iter()
        .map(|joint| JointPose {
            translation: joint.translation,
            rotation: if joint.parent.is_some() {
                quat_mul(joint.rotation, bend)
            } else {
                joint.rotation
            },
            scale: joint.scale,
        })
        .collect();
    compute_skin_matrices(skeleton, &poses).ok()
}

/// The clips a figure can play, next to the skeleton they were authored for.
#[derive(Debug, Clone, PartialEq)]
pub struct FigureAnimation {
    /// The figure's skeleton, needed to compose a sampled pose into skinning matrices.
    pub skeleton: SkeletonData,
    /// Clip played while the figure stands still.
    pub idle: ClipData,
    /// Clip played while the figure walks.
    pub walk: ClipData,
    /// How fast the walk clip plays, so its stride covers the ground the figure crosses
    /// ([`walk_clip_rate`]). `1.0` is the authored tempo.
    pub walk_rate: f32,
}

/// Bounds of the walk clip's playback rate.
///
/// The lower bound keeps a clip from crawling into a pose that reads as a freeze; the upper bound
/// keeps legs from whirring when a figure is faster than the clip was ever meant for. Both are
/// the tempo band engine ADR-0017 proposes for the converter's check of anchors against markers
/// (a factor of 0.5 to 2.0), the upper one widened to 3.0: the arena's top speed is well above
/// what a walk clip is authored at, and cutting it to 2.0 would put the slide back in.
pub const WALK_CLIP_RATE_BOUNDS: (f32, f32) = (0.5, 3.0);

/// How many poses one cycle is sampled at when the walk clip is measured.
const STRIDE_SAMPLES: usize = 120;

/// What the measurement of a walk clip found: how far its planted foot carries the figure, and
/// how much of the ground the figure covers the foot does *not* carry — the slide.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct FootSlip {
    /// Distance the measured foot travels through the figure's own space in one cycle, in metres:
    /// the ground a step covers if nothing slides.
    pub stride_length: f32,
    /// Ground speed the clip walks at when it plays at rate `1.0`, in metres per second.
    pub clip_ground_speed: f32,
    /// Mean sliding speed of the planted foot over the ground, in metres per second: what is left
    /// of the figure's speed after the foot's own motion is subtracted.
    pub slip: f32,
    /// Joints whose position moves during the cycle (a clip that animates a parent moves its
    /// children too, so this counts more than the clip's own tracks).
    pub moving_joints: usize,
}

/// Global rest positions of every joint for `pose`, parents before children.
fn global_positions(skeleton: &SkeletonData, pose: &[JointPose]) -> Vec<[f32; 3]> {
    let mut world: Vec<Mat4> = Vec::with_capacity(skeleton.joints.len());
    let mut positions = Vec::with_capacity(skeleton.joints.len());
    for (index, joint) in skeleton.joints.iter().enumerate() {
        let local = pose.get(index).map_or(IDENTITY, joint_matrix);
        let matrix = match joint.parent {
            // `decode_skeleton` guarantees the parent comes first.
            Some(parent) => mul(world[parent as usize], local),
            None => local,
        };
        positions.push([matrix[3][0], matrix[3][1], matrix[3][2]]);
        world.push(matrix);
    }
    positions
}

/// Column-major matrix of one joint's rest transform.
fn joint_matrix(pose: &JointPose) -> Mat4 {
    let [x, y, z, w] = pose.rotation;
    let [sx, sy, sz] = pose.scale;
    let [tx, ty, tz] = pose.translation;
    [
        [
            (1.0 - 2.0 * (y * y + z * z)) * sx,
            2.0 * (x * y + z * w) * sx,
            2.0 * (x * z - y * w) * sx,
            0.0,
        ],
        [
            2.0 * (x * y - z * w) * sy,
            (1.0 - 2.0 * (x * x + z * z)) * sy,
            2.0 * (y * z + x * w) * sy,
            0.0,
        ],
        [
            2.0 * (x * z + y * w) * sz,
            2.0 * (y * z - x * w) * sz,
            (1.0 - 2.0 * (x * x + y * y)) * sz,
            0.0,
        ],
        [tx, ty, tz, 1.0],
    ]
}

/// Measures `animation`'s walk clip against a figure moving at `speed`, with the clip playing at
/// `rate`.
///
/// The method is the one a foot itself imposes: while a foot is planted it stands still on the
/// ground, so in the figure's own space it must travel backwards exactly as fast as the figure
/// travels forwards. Whatever is missing slides. The foot is found rather than named — the lowest
/// joint with the largest horizontal travel — so a rig with other joint names still measures.
///
/// Returns `None` if no joint moves at all (a clip that poses the figure and holds it), where a
/// stride has no meaning.
#[must_use]
pub fn foot_slip(animation: &FigureAnimation, speed: f32, rate: f32) -> Option<FootSlip> {
    let duration = animation.walk.duration_seconds();
    if !duration.is_finite() || duration <= 0.0 || !rate.is_finite() || rate <= 0.0 {
        return None;
    }
    let mut pose = Vec::new();
    let mut tracks: Vec<Vec<[f32; 3]>> = Vec::new();
    for sample in 0..STRIDE_SAMPLES {
        let time = duration * sample as f32 / STRIDE_SAMPLES as f32;
        sample_pose_into(&animation.walk, time, &mut pose);
        let positions = global_positions(&animation.skeleton, &pose);
        if tracks.is_empty() {
            tracks = positions.iter().map(|point| vec![*point]).collect();
        } else {
            for (track, point) in tracks.iter_mut().zip(positions) {
                track.push(point);
            }
        }
    }
    if tracks.is_empty() {
        return None;
    }
    let travel = |track: &[[f32; 3]], axis: usize| {
        let mut low = f32::INFINITY;
        let mut high = f32::NEG_INFINITY;
        for point in track {
            low = dmath::min(low, point[axis]);
            high = dmath::max(high, point[axis]);
        }
        high - low
    };
    let moving_joints = tracks
        .iter()
        .filter(|track| (0..3).any(|axis| travel(track, axis) > 1.0e-4))
        .count();
    // The walking axis is the horizontal one the whole figure swings along.
    let axis = if tracks
        .iter()
        .map(|track| travel(track, 0))
        .fold(0.0_f32, dmath::max)
        >= tracks
            .iter()
            .map(|track| travel(track, 1))
            .fold(0.0_f32, dmath::max)
    {
        0
    } else {
        1
    };
    // The foot: of the joints in the lowest third of the figure, the one that travels farthest
    // along the walking axis.
    let mut lowest = f32::INFINITY;
    let mut highest = f32::NEG_INFINITY;
    for track in &tracks {
        for point in track {
            lowest = dmath::min(lowest, point[2]);
            highest = dmath::max(highest, point[2]);
        }
    }
    let ground = lowest + (highest - lowest) / 3.0;
    let foot = tracks
        .iter()
        .filter(|track| {
            track
                .iter()
                .map(|point| point[2])
                .fold(f32::INFINITY, dmath::min)
                <= ground
        })
        .max_by(|left, right| {
            travel(left, axis)
                .partial_cmp(&travel(right, axis))
                .unwrap_or(core::cmp::Ordering::Equal)
        })?;
    let stride_length = travel(foot, axis);
    if stride_length <= 1.0e-4 {
        return Some(FootSlip {
            stride_length,
            clip_ground_speed: 0.0,
            slip: speed.abs(),
            moving_joints,
        });
    }
    // Planted samples: the foot is low and moving backwards along the walking axis. Their mean
    // backward speed is the ground speed the clip itself walks at.
    let step = duration / STRIDE_SAMPLES as f32;
    let mut planted = Vec::new();
    for index in 0..STRIDE_SAMPLES {
        let next = (index + 1) % STRIDE_SAMPLES;
        let height = foot[index][2];
        let velocity = (foot[next][axis] - foot[index][axis]) / step;
        if height <= ground {
            planted.push(velocity);
        }
    }
    if planted.is_empty() {
        return None;
    }
    // The foot may travel either way in the figure's space, depending on which way the rig faces;
    // the sign that carries the figure forwards is the one the planted phase spends most time on.
    let forward = if planted.iter().filter(|value| **value < 0.0).count() * 2 >= planted.len() {
        -1.0
    } else {
        1.0
    };
    let carried: Vec<f32> = planted
        .iter()
        .map(|velocity| forward * velocity * rate)
        .filter(|velocity| *velocity > 0.0)
        .collect();
    if carried.is_empty() {
        return None;
    }
    let clip_ground_speed =
        carried.iter().sum::<f32>() / carried.len() as f32 / dmath::max(rate, 1.0e-6);
    let slip = carried
        .iter()
        .map(|carries| (speed.abs() - *carries).abs())
        .sum::<f32>()
        / carried.len() as f32;
    Some(FootSlip {
        stride_length,
        clip_ground_speed,
        slip,
        moving_joints,
    })
}

/// The rate at which `animation`'s walk clip has to play so its stride covers `speed`.
///
/// Measured on the clip itself ([`foot_slip`]), not guessed: the planted foot's own backward
/// speed says how fast the clip walks, and the rate is the quotient with the speed the figure
/// actually moves at, clamped to [`WALK_CLIP_RATE_BOUNDS`]. A clip whose feet never move cannot
/// be matched and keeps its authored tempo.
#[must_use]
pub fn walk_clip_rate(animation: &FigureAnimation, speed: f32) -> f32 {
    let Some(measured) = foot_slip(animation, speed, 1.0) else {
        return 1.0;
    };
    walk_rate_for(speed, measured.clip_ground_speed)
}

/// The clamped quotient behind [`walk_clip_rate`]: how much faster than authored a clip that walks
/// `clip_ground_speed` has to play to carry a figure moving at `speed`.
///
/// A clip that does not walk at all, or a speed that is not a number, keeps the authored tempo.
#[must_use]
pub fn walk_rate_for(speed: f32, clip_ground_speed: f32) -> f32 {
    if !clip_ground_speed.is_finite() || clip_ground_speed <= 1.0e-3 || !speed.is_finite() {
        return 1.0;
    }
    let rate = speed.abs() / clip_ground_speed;
    rate.clamp(WALK_CLIP_RATE_BOUNDS.0, WALK_CLIP_RATE_BOUNDS.1)
}

/// Speed at which the walk clip starts to mix in, in world units per second.
pub const WALK_BLEND_START: f32 = 0.25;

/// Speed at which only the walk clip plays, in world units per second.
pub const WALK_BLEND_FULL: f32 = 2.0;

/// How much of the walk clip a figure moving at `speed` shows: `0.0` is pure idle, `1.0` pure
/// walk, in between a crossfade.
///
/// A pure function of the speed, so the pose stays a function of world and `alpha` alone
/// (engine ADR-0017): no playhead, no hysteresis, nothing the simulation would have to carry.
#[must_use]
pub fn walk_blend(speed: f32) -> f32 {
    if !speed.is_finite() || speed <= WALK_BLEND_START {
        return 0.0;
    }
    if speed >= WALK_BLEND_FULL {
        return 1.0;
    }
    (speed - WALK_BLEND_START) / (WALK_BLEND_FULL - WALK_BLEND_START)
}

/// Clip time of a frame in seconds: the simulation's own clock, `tick` plus the interpolation
/// `alpha`, divided by the tick rate.
///
/// The clips follow the ticks; nothing in the simulation counts animation time (ADR-0017).
#[must_use]
pub fn clip_time(tick: u64, alpha: f32) -> f32 {
    // `as` on a tick count is exact up to 2^24 ticks (78 hours at 60 Hz) and saturates after.
    (tick as f32 + alpha) / crate::TICK_RATE_HZ as f32
}

/// Buffers for sampling clips, held by the caller of [`extract`] across frames so a frame
/// allocates nothing (the engine's [`ClipSampler`] holds no playback state at all).
#[derive(Debug, Default)]
pub struct Animator {
    sampler: ClipSampler,
}

impl Animator {
    /// A fresh animator.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Skinning matrices of `animation` at `time`, with `blend` of the walk clip mixed in.
    ///
    /// Returns `None` if the clips and the skeleton disagree (which `load_clip` rules out when
    /// the clip is loaded), so the caller can fall back to the rest pose.
    fn skin_matrices(
        &mut self,
        animation: &FigureAnimation,
        time: f32,
        blend: f32,
    ) -> Option<&[Mat4]> {
        // The walk clip runs on its own, stride-matched clock; the idle clip keeps real time.
        let walk_time = time * animation.walk_rate;
        if blend <= 0.0 {
            self.sampler.sample(&animation.idle, time);
        } else if blend >= 1.0 {
            self.sampler.sample(&animation.walk, walk_time);
        } else {
            self.sampler
                .sample_crossfade(&animation.idle, time, &animation.walk, walk_time, blend)
                .ok()?;
        }
        self.sampler.skin_matrices(&animation.skeleton).ok()
    }
}

/// A loaded figure plus the poses the prototype shows: its clips when the pack carries them,
/// otherwise the rest pose, and the crumpled hit pose.
#[derive(Debug, Clone, PartialEq)]
pub struct FigureVisual {
    /// Registered mesh and resolved material of every part.
    pub parts: Vec<LoadedFigurePart>,
    /// Skinning matrices of the rest pose.
    pub rest_pose: Vec<Mat4>,
    /// Skinning matrices of the crumpled hit pose.
    pub hit_pose: Vec<Mat4>,
    /// Lift that puts the figure's lowest point on the ground.
    pub ground_lift: f32,
    /// Height of the figure's bounds.
    pub height: f32,
    /// Which way the model looks; see [`facing_yaw`] for the convention.
    pub authored_front: AuthoredFront,
    /// Clips the figure plays, if its pack carries them; without them it stands in its rest pose.
    pub animation: Option<FigureAnimation>,
}

impl FigureVisual {
    /// Prepares a figure loaded through `grimoire::adapters::figure_assets::load_figure_into`,
    /// authored to look along `authored_front`.
    #[must_use]
    pub fn from_loaded(figure: &LoadedFigure, authored_front: AuthoredFront) -> Self {
        let rest_pose = rest_pose_skin_matrices(&figure.skeleton);
        let hit_pose = crumpled_pose(&figure.skeleton, 0.35).unwrap_or_else(|| rest_pose.clone());
        Self {
            parts: figure.parts.clone(),
            rest_pose,
            hit_pose,
            ground_lift: -figure.bounds_min[2],
            height: figure.bounds_max[2] - figure.bounds_min[2],
            authored_front,
            animation: None,
        }
    }

    /// The same figure with `animation` attached.
    #[must_use]
    pub fn with_animation(mut self, animation: FigureAnimation) -> Self {
        self.animation = Some(animation);
        self
    }

    /// A stand-in figure without real geometry (tests, headless runs): one part, one joint.
    #[must_use]
    pub fn placeholder(mesh: MeshHandle) -> Self {
        Self {
            parts: vec![LoadedFigurePart {
                mesh,
                material: material([0.3, 0.3, 0.3], 0.8, [0.0; 3]),
            }],
            rest_pose: vec![IDENTITY],
            hit_pose: vec![IDENTITY],
            ground_lift: 0.0,
            height: 1.8,
            authored_front: AuthoredFront::PlusZ,
            animation: None,
        }
    }
}

/// Procedural geometry of the arena, registered once through the engine's asset hook.
#[derive(Debug, Clone, PartialEq)]
pub struct StageMeshData {
    /// Square floor of stone tiles.
    pub floor: MeshData,
    /// Octagonal pillar along the arena edge.
    pub pillar: MeshData,
    /// Unit box (1 x 1 x 1), scaled into curbs and the imp's plinth.
    pub block: MeshData,
    /// Flat ring on the ground marking the player's hit capsule.
    pub marker_ring: MeshData,
}

/// Builds [`StageMeshData`].
#[must_use]
pub fn stage_mesh_data() -> StageMeshData {
    StageMeshData {
        floor: floor_tile_grid(FLOOR_TILES, FLOOR_TILE_SIZE),
        pillar: octagonal_pillar(PILLAR_RADIUS, PILLAR_HEIGHT),
        block: altar_block(1.0, 1.0, 1.0),
        marker_ring: flat_ring(0.82, 1.0, 40),
    }
}

/// A flat ring on `Z = 0` between `inner` and `outer` radius, normal `+Z`.
fn flat_ring(inner: f32, outer: f32, segments: u32) -> MeshData {
    let segments = segments.max(3);
    let mut vertices = Vec::with_capacity(segments as usize * 2);
    for i in 0..segments {
        let angle = i as f32 / segments as f32 * dmath::TAU;
        let (s, c) = (dmath::sin(angle), dmath::cos(angle));
        let u = i as f32 / segments as f32;
        vertices.push(MeshVertex::new(
            [c * inner, s * inner, 0.0],
            [0.0, 0.0, 1.0],
            [u, 0.0],
        ));
        vertices.push(MeshVertex::new(
            [c * outer, s * outer, 0.0],
            [0.0, 0.0, 1.0],
            [u, 1.0],
        ));
    }
    let mut indices = Vec::with_capacity(segments as usize * 6);
    for i in 0..segments {
        let a = i * 2;
        let b = a + 1;
        let next = (i + 1) % segments * 2;
        let c = next + 1;
        let d = next;
        indices.extend_from_slice(&[a, b, c, a, c, d]);
    }
    MeshData { vertices, indices }
}

/// Handles of everything the arena draws.
#[derive(Debug, Clone, PartialEq)]
pub struct ArenaVisuals {
    /// The player figure.
    pub soul: FigureVisual,
    /// The enemy figure.
    pub imp: FigureVisual,
    /// Registered [`StageMeshData::floor`].
    pub floor: MeshHandle,
    /// Registered [`StageMeshData::pillar`].
    pub pillar: MeshHandle,
    /// Registered [`StageMeshData::block`].
    pub block: MeshHandle,
    /// Registered [`StageMeshData::marker_ring`].
    pub marker_ring: MeshHandle,
}

impl ArenaVisuals {
    /// Visuals without registered geometry: every handle is `MeshHandle(0)` and both figures are
    /// placeholders. For tests and headless runs, where nothing is drawn.
    #[must_use]
    pub fn placeholder() -> Self {
        Self {
            soul: FigureVisual::placeholder(MeshHandle(0)),
            imp: FigureVisual::placeholder(MeshHandle(0)),
            floor: MeshHandle(0),
            pillar: MeshHandle(0),
            block: MeshHandle(0),
            marker_ring: MeshHandle(0),
        }
    }
}

/// One of the camera settings the player can cycle through.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct CameraPreset {
    /// Short name shown in the window title.
    pub name: &'static str,
    /// Tilt against the ground in degrees (90 looks straight down).
    pub tilt_degrees: f32,
    /// Distance from the follow point along the view direction, in world units.
    pub distance: f32,
}

/// Field of view of every camera preset.
pub const CAMERA_FOV_Y_DEGREES: f32 = 42.0;

/// The camera presets in cycling order; the first is the default.
///
/// A (60 degrees, 14.5 m) shows the most arena and the smallest figures, C (45 degrees, 11 m) the
/// largest with less arena in view, B lies in between. Measured on the offscreen capture at 1080p,
/// the soul with its hit ring is 128 px tall under A, 184 px under B and 248 px under C. The PO
/// compares the character designs at game size with them (decision 2026-09-17).
pub const CAMERA_PRESETS: [CameraPreset; 3] = [
    CameraPreset {
        name: "A",
        tilt_degrees: 60.0,
        distance: 14.5,
    },
    CameraPreset {
        name: "B",
        tilt_degrees: 52.0,
        distance: 12.5,
    },
    CameraPreset {
        name: "C",
        tilt_degrees: 45.0,
        distance: 11.0,
    },
];

/// Camera of preset `index` (wrapping), aimed at the follow point of the player's start; the
/// stage plugin moves `target` every frame with a follow spring.
#[must_use]
pub fn camera_preset(index: usize) -> Camera25D {
    let preset = CAMERA_PRESETS[index % CAMERA_PRESETS.len()];
    let mut camera = Camera25D::default();
    camera.target = camera_focus(crate::arena::PLAYER_START).to_array();
    camera.tilt_degrees = preset.tilt_degrees;
    camera.fov_y_degrees = CAMERA_FOV_Y_DEGREES;
    camera.distance = preset.distance;
    camera.look_ahead_max = 1.0;
    camera.look_ahead_smoothing = 0.3;
    camera
}

/// The default camera, preset A.
#[must_use]
pub fn camera_template() -> Camera25D {
    camera_preset(0)
}

/// The camera's follow point for an interpolated player position: mostly the player, pulled
/// towards the imp's half so the enemy stays in view.
#[must_use]
pub fn camera_focus(player: Vec2) -> Vec2 {
    player * CAMERA_FOLLOW_SHARE + CAMERA_ANCHOR
}

/// Interpolated player position.
#[must_use]
pub fn player_focus(world: &World, alpha: f32) -> Option<Vec2> {
    world
        .query::<(&PreviousPosition, &Position, &Player)>()
        .next()
        .map(|(previous, position, _)| previous.at.lerp(position.at, alpha))
}

/// Round information for a window title or a HUD.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Hud {
    /// Current round, starting at 1.
    pub round: u32,
    /// Hits taken so far.
    pub hits: u32,
    /// Whether the current round is lost and waiting for its restart.
    pub hit_pending: bool,
    /// Live bullets.
    pub bullets: u32,
    /// Whether the imp plays its curtain mode.
    pub curtain: bool,
}

/// Reads the [`Hud`] values from the world.
#[must_use]
pub fn hud(world: &World) -> Hud {
    let round = world.resource::<RoundState>().copied();
    Hud {
        round: round.map_or(0, |round| round.round),
        hits: round.map_or(0, |round| round.hits),
        hit_pending: round.is_some_and(|round| matches!(round.phase, Phase::Hit { .. })),
        bullets: world.resource::<BulletPool>().map_or(0, BulletPool::len),
        curtain: world
            .resource::<ArenaMode>()
            .is_some_and(|mode| mode.mode == Mode::Curtain),
    }
}

/// Material slots every frame starts with, in this order.
mod slot {
    pub const FLOOR: u32 = 0;
    pub const PILLAR: u32 = 1;
    pub const PLINTH: u32 = 2;
    pub const MARKER: u32 = 3;
    pub const COUNT: u32 = 4;
}

/// Pushes the fixed materials in the order of [`slot`].
fn push_stage_materials(frame: &mut StageFrame) {
    frame
        .materials
        .push(material(linear(0x33_36_3D), 0.85, [0.0; 3]));
    frame
        .materials
        .push(material(linear(0x3E_40_47), 0.75, [0.0; 3]));
    frame
        .materials
        .push(material(linear(0x2A_25_28), 0.6, [0.0; 3]));
    // Player marker: the friendly family, desaturated and bright (style bible, layer 7).
    let marker = linear(0xBD_EF_FF);
    frame
        .materials
        .push(material(marker, 0.5, scale3(marker, 0.55)));
    debug_assert_eq!(frame.materials.len(), slot::COUNT as usize);
}

fn mesh(mesh: MeshHandle, material: u32, transform: Mat4) -> MeshInstance {
    let mut instance = MeshInstance::default();
    instance.mesh = mesh;
    instance.material = MaterialHandle(material);
    instance.transform = transform;
    instance
}

fn blob(position: Vec2, radius: f32, strength: f32) -> BlobShadowInstance {
    BlobShadowInstance {
        position: position.to_array(),
        radius,
        softness: 0.6,
        strength,
    }
}

fn torch(position: [f32; 3]) -> PointLight {
    let mut light = PointLight::default();
    light.position = position;
    light.color = linear(0xFF_9A_4A);
    light.intensity = 7.0;
    light.range = 11.0;
    light
}

/// The static part of the stage: lighting, floor, pillars, curbs, the imp's plinth.
fn push_arena(visuals: &ArenaVisuals, frame: &mut StageFrame) {
    frame.base.clear_color = [0.012, 0.012, 0.018, 1.0];
    let mut key = DirectionalLight::default();
    key.direction = [0.35, 0.5, -0.8];
    key.color = linear(0x9A_B0_D8);
    key.intensity = 2.6;
    frame.key_light = Some(key);
    frame.ambient = AmbientLight::Hemisphere {
        sky_color: [0.16, 0.18, 0.24],
        ground_color: [0.06, 0.055, 0.06],
        intensity: 0.7,
    };
    let mut shadows = ShadowConfig::default();
    // Skinned figures cast no key-light shadow yet (engine gap, contract §6 skinning addendum),
    // so the prototype uses the "Low" preset: blob shadows under figures and pillars.
    shadows.mode = ShadowMode::Blob;
    frame.shadow_config = shadows;

    frame
        .meshes
        .push(mesh(visuals.floor, slot::FLOOR, IDENTITY));

    let edge = ARENA_HALF + Vec2::splat(CURB_GAP + CURB_DEPTH * 0.5);
    let pillar_x = edge.x + CURB_DEPTH;
    let pillar_y = edge.y + CURB_DEPTH;
    // Pillars only on the far side and the flanks: on the camera side they would hide the arena.
    // The near edge gets low braziers instead.
    let mut torch_index = 0_u32;
    for &x in &[-pillar_x, -pillar_x * 0.5, 0.0, pillar_x * 0.5, pillar_x] {
        push_pillar(visuals, frame, Vec2::new(x, pillar_y), &mut torch_index);
    }
    for &y in &[0.0, -pillar_y * 0.6] {
        for &x in &[-pillar_x, pillar_x] {
            push_pillar(visuals, frame, Vec2::new(x, y), &mut torch_index);
        }
    }
    for &x in &[-pillar_x * 0.5, pillar_x * 0.5] {
        let at = Vec2::new(x, -pillar_y);
        let brazier = mul(
            translation([at.x, at.y, BRAZIER_HEIGHT * 0.5]),
            scale([0.6, 0.6, BRAZIER_HEIGHT]),
        );
        frame
            .meshes
            .push(mesh(visuals.block, slot::PLINTH, brazier));
        frame.blob_shadows.push(blob(at, 0.7, 0.55));
        frame
            .point_lights
            .push(torch([at.x, at.y + 0.3, BRAZIER_HEIGHT + 0.5]));
    }

    let long = 2.0 * edge.x + CURB_DEPTH;
    let short = 2.0 * edge.y + CURB_DEPTH;
    for &(center, size) in &[
        (Vec2::new(0.0, -edge.y), [long, CURB_DEPTH, CURB_HEIGHT]),
        (Vec2::new(0.0, edge.y), [long, CURB_DEPTH, CURB_HEIGHT]),
        (Vec2::new(-edge.x, 0.0), [CURB_DEPTH, short, CURB_HEIGHT]),
        (Vec2::new(edge.x, 0.0), [CURB_DEPTH, short, CURB_HEIGHT]),
    ] {
        let transform = mul(
            translation([center.x, center.y, CURB_HEIGHT * 0.5]),
            scale(size),
        );
        frame
            .meshes
            .push(mesh(visuals.block, slot::PILLAR, transform));
    }

    let plinth = mul(
        translation([IMP_POSITION.x, IMP_POSITION.y, PLINTH_HEIGHT * 0.5]),
        scale([1.8, 1.8, PLINTH_HEIGHT]),
    );
    frame.meshes.push(mesh(visuals.block, slot::PLINTH, plinth));
    frame.blob_shadows.push(blob(IMP_POSITION, 1.6, 0.5));
}

fn push_pillar(visuals: &ArenaVisuals, frame: &mut StageFrame, at: Vec2, torch_index: &mut u32) {
    frame.meshes.push(mesh(
        visuals.pillar,
        slot::PILLAR,
        translation([at.x, at.y, PILLAR_HEIGHT * 0.5]),
    ));
    frame.blob_shadows.push(blob(at, PILLAR_RADIUS * 2.2, 0.55));
    // Every other pillar carries a torch, lifted towards the arena.
    if (*torch_index).is_multiple_of(2) {
        let inward = Vec2::new(-at.x, -at.y).normalize_or_zero() * 0.8;
        frame
            .point_lights
            .push(torch([at.x + inward.x, at.y + inward.y, 2.6]));
    }
    *torch_index += 1;
}

/// Appends one skinned figure; returns nothing drawn when `visible` is false.
/// How a figure is posed this frame.
#[derive(Debug, Clone, Copy, PartialEq)]
enum Pose {
    /// The crumpled hit pose; a hit figure never animates.
    Hit,
    /// The clips at `time` seconds with `blend` of the walk mixed in, or the rest pose if the
    /// figure has no clips.
    Animated {
        /// Clip time in seconds ([`clip_time`]).
        time: f32,
        /// Walk share ([`walk_blend`]).
        blend: f32,
    },
}

fn push_figure(
    figure: &FigureVisual,
    transform: Mat4,
    pose: Pose,
    emissive: Option<[f32; 3]>,
    animator: &mut Animator,
    frame: &mut StageFrame,
) {
    let sampled = match (pose, &figure.animation) {
        (Pose::Animated { time, blend }, Some(animation)) => {
            animator.skin_matrices(animation, time, blend)
        }
        _ => None,
    };
    let pose = match (sampled, pose) {
        (Some(pose), _) => pose,
        (None, Pose::Hit) => &figure.hit_pose,
        (None, Pose::Animated { .. }) => &figure.rest_pose,
    };
    // Innermost: bring the model's front onto the convention, so facing and knock-back apply to
    // every figure alike.
    let transform = mul(transform, figure.authored_front.correction());
    let Ok(joint_offset) = u32::try_from(frame.joint_matrices.len()) else {
        return;
    };
    let Ok(joint_count) = u32::try_from(pose.len()) else {
        return;
    };
    frame.joint_matrices.extend_from_slice(pose);
    let mut skin = SkinBinding::default();
    skin.joint_offset = joint_offset;
    skin.joint_count = joint_count;
    for part in &figure.parts {
        let mut material = part.material;
        if let Some(glow) = emissive {
            material.emissive_factor = glow;
        }
        let Ok(index) = u32::try_from(frame.materials.len()) else {
            return;
        };
        frame.materials.push(material);
        let mut instance = mesh(part.mesh, index, transform);
        instance.skin = Some(skin);
        // Figures are the actor layer (PRD-0003 layer 3): only they receive the frame's rim
        // light, which keeps a dark silhouette readable against the dark floor. The stage's own
        // geometry stays `MeshRole::Environment` and renders exactly as before.
        instance.role = MeshRole::Actor;
        frame.meshes.push(instance);
    }
}

/// Ticks of the last completed simulation tick (`Tick` holds the index of the next one).
fn last_tick(world: &World) -> u64 {
    world
        .resource::<Tick>()
        .map_or(0, |tick| tick.0.saturating_sub(1))
}

/// The player: figure, marker ring, blob shadow and the hit reaction.
/// Speed of the player in world units per second, `0.0` without a player.
fn player_speed(world: &World) -> f32 {
    world
        .query::<(&Velocity, &Player)>()
        .next()
        .map_or(0.0, |(velocity, _)| velocity.value.length())
}

fn push_player(
    world: &World,
    alpha: f32,
    visuals: &ArenaVisuals,
    animator: &mut Animator,
    frame: &mut StageFrame,
) {
    let Some((previous, position, facing, _)) = world
        .query::<(&PreviousPosition, &Position, &Facing, &Player)>()
        .next()
    else {
        return;
    };
    let at = previous.at.lerp(position.at, alpha);
    let round = world.resource::<RoundState>().copied();
    let tick = last_tick(world);
    let yaw = facing_yaw(facing.direction);
    let soul = &visuals.soul;

    let mut hit_age = None;
    let mut lift = 0.0;
    if let Some(round) = round {
        match round.phase {
            Phase::Hit { at_tick } => hit_age = Some(tick.saturating_sub(at_tick)),
            Phase::Fighting => {
                let age = tick.saturating_sub(round.started_at) as f32 + alpha;
                if round.round > 1 && age < RESPAWN_TICKS {
                    // Rise in from below the floor after a restart.
                    let t = age / RESPAWN_TICKS;
                    lift = -(1.0 - t) * (1.0 - t) * soul.height * 0.6;
                }
            }
        }
    }

    frame.blob_shadows.push(blob(at, 0.55, 0.6));
    // A cool lantern above the soul lifts the dark cloak off the dark floor (style bible,
    // "Figuren": figures separate through light and value, never through outlines).
    let mut lantern = PointLight::default();
    lantern.position = [at.x, at.y - 0.8, 2.6];
    lantern.color = linear(0x9A_B0_D8);
    lantern.intensity = 4.0;
    lantern.range = 5.5;
    frame.point_lights.push(lantern);

    let Some(age) = hit_age else {
        let transform = mul(
            translation([at.x, at.y, soul.ground_lift + lift]),
            rotation_z(yaw),
        );
        push_figure(
            soul,
            transform,
            Pose::Animated {
                time: clip_time(tick, alpha),
                blend: walk_blend(player_speed(world)),
            },
            None,
            animator,
            frame,
        );
        let ring = mul(
            translation([at.x, at.y, 0.02]),
            scale([
                PLAYER_HIT_RADIUS + PLAYER_HIT_HALF_WIDTH,
                PLAYER_HIT_RADIUS + PLAYER_HIT_HALF_WIDTH,
                1.0,
            ]),
        );
        frame
            .meshes
            .push(mesh(visuals.marker_ring, slot::MARKER, ring));
        return;
    };

    // Hit reaction: the soul is knocked back, crumples, glows red and blinks until the restart.
    let age_f = age as f32 + alpha;
    let fall = dmath::min(age_f / HIT_FALL_TICKS, 1.0);
    let fade = 1.0 - dmath::min(age_f / HIT_RECOVERY_TICKS as f32, 1.0);
    let knock_back = rotation_x(-0.6 * fall);
    let transform = mul(
        mul(
            translation([at.x, at.y, soul.ground_lift - 0.25 * fall]),
            rotation_z(yaw),
        ),
        knock_back,
    );
    let pulse = 0.55 + 0.45 * dmath::cos(age_f * 0.6);
    let red = [1.0 * pulse, 0.06 * pulse, 0.04 * pulse];
    let visible = age < 20 || (age / HIT_BLINK_TICKS) % 3 != 2;
    if visible {
        push_figure(soul, transform, Pose::Hit, Some(red), animator, frame);
    }
    let mut flash = PointLight::default();
    flash.position = [at.x, at.y, 1.2];
    flash.color = [1.0, 0.12, 0.06];
    flash.intensity = 30.0 * fade * fade;
    flash.range = 7.0;
    if flash.intensity > 0.0 {
        frame.point_lights.push(flash);
    }
}

/// The imp on its plinth, turned towards the player.
fn push_imp(
    world: &World,
    alpha: f32,
    visuals: &ArenaVisuals,
    animator: &mut Animator,
    frame: &mut StageFrame,
) {
    let Some((position, _)) = world.query::<(&Position, &Imp)>().next() else {
        return;
    };
    let target = player_focus(world, alpha).unwrap_or(crate::arena::PLAYER_START);
    let yaw = facing_yaw((target - position.at).normalize_or_zero());
    let transform = mul(
        translation([
            position.at.x,
            position.at.y,
            PLINTH_HEIGHT + visuals.imp.ground_lift,
        ]),
        rotation_z(yaw),
    );
    push_figure(
        &visuals.imp,
        transform,
        Pose::Animated {
            time: clip_time(last_tick(world), alpha),
            blend: 0.0,
        },
        None,
        animator,
        frame,
    );
    // A dim glow from the imp's hands, in the warm light family (never a bullet colour).
    let mut glow = PointLight::default();
    glow.position = [position.at.x, position.at.y - 0.6, PLINTH_HEIGHT + 1.0];
    glow.color = linear(0xFF_7A_3A);
    glow.intensity = 3.0;
    glow.range = 5.0;
    frame.point_lights.push(glow);
}

/// Fills `frame` with the arena, the figures and the bullets of `world`, interpolated by `alpha`,
/// and returns the counters of the bullet extraction.
///
/// Bullets reach [`StageFrame::bullets`] only through the engine's Sigil render adapter; the
/// renderer draws them and derives their lights. `frame` should come cleared
/// ([`StageFrame::clear`]); the camera is left to the caller.
pub fn extract(
    world: &World,
    alpha: f32,
    visuals: &ArenaVisuals,
    animator: &mut Animator,
    frame: &mut StageFrame,
) -> BulletExtractionStats {
    push_stage_materials(frame);
    push_arena(visuals, frame);
    push_imp(world, alpha, visuals, animator, frame);
    push_player(world, alpha, visuals, animator, frame);
    extract_bullets(world, alpha, &mut frame.bullets)
}

#[cfg(test)]
mod tests {
    use grimoire::render::{NullRenderer, Renderer};

    use super::*;
    use crate::arena::{ArenaGame, HIT_RECOVERY_TICKS};

    fn built() -> Simulation {
        let mut sim = Simulation::new(3);
        ArenaGame::new().build(&mut sim);
        sim
    }

    fn render(frame: &StageFrame) -> grimoire::render::StageStats {
        let mut renderer = NullRenderer::default();
        renderer
            .render_stage(frame)
            .expect("the null renderer never fails")
    }

    #[test]
    fn the_first_frame_is_structurally_valid() {
        let sim = built();
        let visuals = ArenaVisuals::placeholder();
        let mut frame = StageFrame::new();
        extract(sim.world(), 0.0, &visuals, &mut Animator::new(), &mut frame);
        frame.camera_25d = Some(camera_template());
        let stats = render(&frame);
        assert_eq!(stats.meshes_rejected_invalid, 0);
        assert_eq!(stats.meshes_rejected_layer, 0);
        assert_eq!(stats.materials_rejected_invalid, 0);
        assert_eq!(stats.point_lights_rejected_invalid, 0);
        assert!(!stats.key_light_rejected_invalid);
        assert!(!stats.ambient_rejected_invalid);
        assert_eq!(stats.bullets_drawn, 0);
        // Floor, 9 pillars, 2 braziers, 4 curbs, plinth, imp, soul and the marker ring.
        assert_eq!(frame.meshes.len(), 1 + 9 + 2 + 4 + 1 + 1 + 1 + 1);
    }

    #[test]
    fn the_walk_blend_follows_the_speed_and_nothing_else() {
        // A pure function of the speed: no playhead, no hysteresis, nothing the simulation would
        // have to carry (engine ADR-0017).
        assert_eq!(walk_blend(0.0), 0.0);
        assert_eq!(walk_blend(WALK_BLEND_START), 0.0);
        assert_eq!(walk_blend(WALK_BLEND_FULL), 1.0);
        assert_eq!(walk_blend(crate::arena::PLAYER_SPEED), 1.0);
        let middle = walk_blend((WALK_BLEND_START + WALK_BLEND_FULL) / 2.0);
        assert!((middle - 0.5).abs() < 1.0e-6, "{middle}");
        assert!(walk_blend(f32::NAN) == 0.0 && walk_blend(-1.0) == 0.0);
        // Monotone in between, so a figure never jitters between two poses.
        let mut previous = 0.0;
        for step in 0..=20 {
            let speed =
                WALK_BLEND_START + (WALK_BLEND_FULL - WALK_BLEND_START) * (step as f32 / 20.0);
            let blend = walk_blend(speed);
            assert!(blend >= previous, "speed {speed}: {blend} < {previous}");
            previous = blend;
        }
    }

    #[test]
    fn the_stride_rate_is_the_quotient_of_the_two_speeds_within_bounds() {
        // The clip's own ground speed decides: a clip that walks half as fast as the figure plays
        // twice as fast, and the bounds keep a crawl from freezing and a dash from whirring.
        assert_eq!(walk_rate_for(2.0, 1.0), 2.0);
        assert_eq!(walk_rate_for(1.0, 1.0), 1.0);
        assert_eq!(walk_rate_for(0.1, 1.0), WALK_CLIP_RATE_BOUNDS.0);
        assert_eq!(walk_rate_for(99.0, 1.0), WALK_CLIP_RATE_BOUNDS.1);
        assert_eq!(walk_rate_for(-2.0, 1.0), 2.0, "direction does not matter");
        // Nothing to match: the authored tempo stands.
        assert_eq!(walk_rate_for(5.5, 0.0), 1.0);
        assert_eq!(walk_rate_for(5.5, f32::NAN), 1.0);
        assert_eq!(walk_rate_for(f32::NAN, 1.0), 1.0);
        assert!(WALK_CLIP_RATE_BOUNDS.0 > 0.0 && WALK_CLIP_RATE_BOUNDS.1 > 1.0);
    }

    #[test]
    fn the_clip_time_is_the_simulations_own_clock() {
        // Tick plus alpha over the tick rate: the clips follow the ticks, nothing counts time on
        // its own, so the same tick and alpha always give the same pose (ADR-0017).
        assert_eq!(clip_time(0, 0.0), 0.0);
        assert_eq!(clip_time(u64::from(crate::TICK_RATE_HZ), 0.0), 1.0);
        let half = clip_time(0, 0.5);
        assert!(
            (half - 0.5 / crate::TICK_RATE_HZ as f32).abs() < 1.0e-9,
            "{half}"
        );
        assert!(clip_time(120, 0.25) > clip_time(120, 0.0));
    }

    #[test]
    fn a_figure_without_clips_keeps_its_rest_pose() {
        // The placeholder figures carry no animation, so the extraction falls back to the poses
        // the prototype had before — the same matrices as the figure's `rest_pose`.
        let sim = built();
        let visuals = ArenaVisuals::placeholder();
        let mut frame = StageFrame::new();
        extract(sim.world(), 0.0, &visuals, &mut Animator::new(), &mut frame);
        assert!(visuals.soul.animation.is_none());
        assert_eq!(
            frame.joint_matrices,
            [
                visuals.imp.rest_pose.clone(),
                visuals.soul.rest_pose.clone()
            ]
            .concat()
        );
    }

    #[test]
    fn only_the_figures_are_actors() {
        // The rim light of the engine reaches `MeshRole::Actor` alone (PRD-0003 layer 3): the two
        // figures, never the floor, the pillars, the braziers, the plinth or the marker ring.
        let sim = built();
        let visuals = ArenaVisuals::placeholder();
        let mut frame = StageFrame::new();
        extract(sim.world(), 0.0, &visuals, &mut Animator::new(), &mut frame);
        let actors = frame
            .meshes
            .iter()
            .filter(|instance| instance.role == MeshRole::Actor)
            .count();
        assert_eq!(actors, 2, "the soul and the imp");
        for instance in &frame.meshes {
            if instance.role == MeshRole::Actor {
                assert!(instance.skin.is_some(), "an actor is a skinned figure");
            } else {
                assert_eq!(instance.role, MeshRole::Environment);
                assert!(instance.skin.is_none());
            }
        }
        // The frame keeps the engine's default rim light; the arena has no reason to override it.
        assert_eq!(frame.rim_light, grimoire::render::RimLight::default());
    }

    #[test]
    fn bullets_reach_the_bullet_pass_through_the_engine_adapter_only() {
        let mut sim = built();
        // Walk away from the aimed fan so the round is still running.
        let mut input = TickInput::default();
        input.slots[0].axes[0] = i16::MAX;
        for _ in 0..170 {
            sim.step(input);
        }
        let visuals = ArenaVisuals::placeholder();
        let mut frame = StageFrame::new();
        let extraction = extract(sim.world(), 0.5, &visuals, &mut Animator::new(), &mut frame);
        let live = hud(sim.world()).bullets;
        assert!(live > 0, "the imp has fired");
        assert_eq!(extraction.extracted, live);
        assert_eq!(extraction.unmapped_visual, 0);
        assert_eq!(frame.bullets.len(), live as usize);

        let stats = render(&frame);
        assert_eq!(stats.bullets_drawn, live);
        assert_eq!(stats.bullets_rejected_invalid, 0);
        assert_eq!(stats.bullets_rejected_palette_space, 0);
        assert_eq!(stats.meshes_rejected_invalid, 0);
        // The game submits no bullet lights of its own; the renderer derives them.
        assert!(
            frame
                .point_lights
                .iter()
                .all(|light| !light.is_bullet_light)
        );
        assert!(stats.bullet_point_lights_drawn > 0);
        // Every mesh is arena, figure or marker: no bullet meshes.
        assert_eq!(frame.meshes.len(), 1 + 9 + 2 + 4 + 1 + 1 + 1 + 1);
        // All three imp bullet types are on screen, each on its own table row.
        let mut rows: Vec<(u16, u16)> = frame
            .bullets
            .iter()
            .map(|bullet| (bullet.silhouette, bullet.palette))
            .collect();
        rows.sort_unstable();
        rows.dedup();
        assert_eq!(
            rows,
            vec![(0, 1), (1, 0), (2, 0)],
            "orb in lime, grain (rice) and dart (diamond) in magenta"
        );
    }

    #[test]
    fn a_hit_shows_the_reaction_and_the_restart_rises_in() {
        let mut sim = built();
        // Standing still in front of the imp is hit by the aimed volley.
        let mut hit_tick = None;
        for _ in 0..600 {
            sim.step(TickInput::default());
            if hud(sim.world()).hit_pending {
                hit_tick = Some(sim.tick());
                break;
            }
        }
        assert!(hit_tick.is_some(), "an idle player is hit");
        let visuals = ArenaVisuals::placeholder();
        let mut frame = StageFrame::new();
        extract(sim.world(), 0.0, &visuals, &mut Animator::new(), &mut frame);
        let red_glow = frame
            .materials
            .iter()
            .any(|material| material.emissive_factor[0] > 0.5 && material.emissive_factor[1] < 0.1);
        assert!(red_glow, "the soul glows red");
        assert!(
            frame
                .point_lights
                .iter()
                .any(|light| light.color == [1.0, 0.12, 0.06]),
            "a red flash lights the hit"
        );

        for _ in 0..=HIT_RECOVERY_TICKS {
            sim.step(TickInput::default());
        }
        let hud = hud(sim.world());
        assert!(!hud.hit_pending);
        assert_eq!(hud.round, 2);
    }

    #[test]
    fn matrices_compose_in_column_major_order() {
        let t = translation([1.0, 2.0, 3.0]);
        let r = rotation_z(dmath::FRAC_PI_2);
        let m = mul(t, r);
        // The rotation applies first, then the translation: +X maps to +Y, then moves.
        let x = [m[0][0], m[0][1], m[0][2]];
        assert!((x[0]).abs() < 1.0e-6 && (x[1] - 1.0).abs() < 1.0e-6);
        assert_eq!(m[3], [1.0, 2.0, 3.0, 1.0]);
        // A figure authored facing -Y turns to face +X.
        let yaw = facing_yaw(Vec2::X);
        let front = mul(rotation_z(yaw), IDENTITY);
        let authored_front = [0.0, -1.0];
        let turned = [
            front[0][0] * authored_front[0] + front[1][0] * authored_front[1],
            front[0][1] * authored_front[0] + front[1][1] * authored_front[1],
        ];
        assert!((turned[0] - 1.0).abs() < 1.0e-5 && turned[1].abs() < 1.0e-5);

        // A figure authored along glTF -Z (engine +Y before any rotation) is corrected first and
        // then faces +X as well.
        let corrected = mul(rotation_z(yaw), AuthoredFront::MinusZ.correction());
        let minus_z_front = [0.0, 1.0];
        let turned = [
            corrected[0][0] * minus_z_front[0] + corrected[1][0] * minus_z_front[1],
            corrected[0][1] * minus_z_front[0] + corrected[1][1] * minus_z_front[1],
        ];
        assert!((turned[0] - 1.0).abs() < 1.0e-5 && turned[1].abs() < 1.0e-5);
        assert_eq!(AuthoredFront::PlusZ.correction(), IDENTITY);
    }

    #[test]
    fn mouse_aim_hits_the_same_ground_point_under_every_camera_preset() {
        // Aim is sampled through the rendered camera (engine contract §9.4): the cursor over a
        // ground point must give the direction from the player to that point, whichever preset
        // draws the frame, even though the camera looks at the pulled follow point, not the player.
        let viewport = [1920.0, 1080.0];
        let player = Vec2::new(2.5, -3.0);
        for offset in [
            Vec2::new(3.0, 2.0),
            Vec2::new(-4.0, 0.5),
            Vec2::new(0.25, -1.5),
        ] {
            let expected = grimoire::quantize_aim(offset);
            for index in 0..CAMERA_PRESETS.len() {
                let mut camera = camera_preset(index);
                camera.target = camera_focus(player).to_array();
                let pixel = camera
                    .ground_to_screen((player + offset).to_array(), viewport)
                    .expect("the ground point is in front of the camera");
                let aim = grimoire::sample_aim(&camera, pixel, viewport, player)
                    .expect("the cursor lies on the ground");
                for axis in 0..2 {
                    assert!(
                        (i32::from(aim[axis]) - i32::from(expected[axis])).abs() <= 2,
                        "preset {index}, offset {offset:?}: {aim:?} vs {expected:?}"
                    );
                }
            }
        }
        assert_eq!(camera_template(), camera_preset(0));
        assert_eq!(camera_preset(3), camera_preset(0), "the index wraps");
    }

    #[test]
    fn the_marker_ring_is_a_valid_mesh() {
        let data = stage_mesh_data();
        for mesh in [&data.floor, &data.pillar, &data.block, &data.marker_ring] {
            mesh.validate().expect("valid procedural mesh");
        }
    }
}
