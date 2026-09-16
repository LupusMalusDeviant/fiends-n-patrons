//! Presentation of the arena: turns the simulated world into a [`StageFrame`].
//!
//! Everything here reads `&World` and writes only the frame; nothing flows back into the
//! simulation. Registering meshes and textures needs the window renderer, so the executable
//! registers them once ([`stage_mesh_data`], a figure pack) and hands the handles in as
//! [`ArenaVisuals`].
//!
//! **Temporary bullet rendering.** The engine's dedicated bullet pass (plan 0002 WP3.5) is not
//! merged yet: `WgpuRenderer` validates and counts [`StageFrame::bullets`] but draws nothing for
//! it. Until it lands, every bullet is additionally drawn as a small emissive mesh (an orb or a
//! stretched "rice" shape, following the Sigil silhouette) with a blob shadow on the ground, and
//! lit through the engine's own [`point_light_from_bullet`]. Search for `TEMPORARY(WP3.5)` to find
//! every place to remove once the bullet pass draws the channel itself.

use fnp_content::sigil::imp_volley;
use grimoire::adapters::figure_assets::{LoadedFigure, LoadedFigurePart};
use grimoire::prelude::*;
use grimoire::render::figure_format::{
    JointPose, SkeletonData, compute_skin_matrices, rest_pose_skin_matrices,
};
use grimoire::render::procedural::{altar_block, floor_tile_grid, icosphere, octagonal_pillar};
use grimoire::render::{
    AmbientLight, BlobShadowInstance, BulletInstance, DirectionalLight, MaterialHandle, MeshData,
    MeshHandle, MeshInstance, MeshVertex, PbrMaterial, PointLight, ShadowConfig, ShadowMode,
    SkinBinding, palette_space, point_light_from_bullet,
};
use grimoire::sigil::{BulletPool, SigilContent};

use super::{
    ARENA_HALF, Facing, HIT_RECOVERY_TICKS, IMP_POSITION, Imp, PLAYER_HIT_HALF_WIDTH,
    PLAYER_HIT_RADIUS, Phase, RoundState,
};
use crate::{Player, Position, PreviousPosition};

/// Column-major 4x4 matrix, the convention of [`MeshInstance::transform`].
pub type Mat4 = [[f32; 4]; 4];

const IDENTITY: Mat4 = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.0],
    [0.0, 0.0, 0.0, 1.0],
];

/// Height above the ground at which bullets are drawn (chest height of the figures).
pub const BULLET_DRAW_HEIGHT: f32 = 0.65;

/// Most bullet lights submitted per frame; the renderer's `LightBudget::High` holds 256 lights
/// including the arena's own.
pub const MAX_BULLET_LIGHTS: usize = 200;

/// Height of the imp's plinth.
pub const PLINTH_HEIGHT: f32 = 0.3;

/// Side tiles of the square floor.
const FLOOR_TILES: u32 = 24;
/// Edge length of one floor tile.
const FLOOR_TILE_SIZE: f32 = 2.0;
/// Radius and height of the arena pillars.
const PILLAR_RADIUS: f32 = 0.55;
const PILLAR_HEIGHT: f32 = 4.5;
/// Height and depth of the curb that marks the arena edge.
const CURB_HEIGHT: f32 = 0.3;
const CURB_DEPTH: f32 = 0.5;
/// Distance of the curb's inner face from the walkable edge (the hit capsule's reach).
const CURB_GAP: f32 = 0.45;
/// Ticks the soul takes to fall into its hit pose.
const HIT_FALL_TICKS: f32 = 8.0;
/// Ticks per on/off half period of the hit blink.
const HIT_BLINK_TICKS: u64 = 5;
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

/// Yaw that turns a figure's authored front (towards -Y, the viewer) to face `direction`.
#[must_use]
pub fn facing_yaw(direction: Vec2) -> f32 {
    dmath::atan2(direction.x, -direction.y)
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

/// A loaded figure plus the precomputed poses the prototype shows (no animation system yet).
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
}

impl FigureVisual {
    /// Prepares a figure loaded through `grimoire::adapters::figure_assets::load_figure`.
    #[must_use]
    pub fn from_loaded(figure: &LoadedFigure) -> Self {
        let rest_pose = rest_pose_skin_matrices(&figure.skeleton);
        let hit_pose = crumpled_pose(&figure.skeleton, 0.35).unwrap_or_else(|| rest_pose.clone());
        Self {
            parts: figure.parts.clone(),
            rest_pose,
            hit_pose,
            ground_lift: -figure.bounds_min[2],
            height: figure.bounds_max[2] - figure.bounds_min[2],
        }
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
        }
    }
}

/// Procedural geometry of the arena, registered once by the executable.
#[derive(Debug, Clone, PartialEq)]
pub struct StageMeshData {
    /// Square floor of stone tiles.
    pub floor: MeshData,
    /// Octagonal pillar along the arena edge.
    pub pillar: MeshData,
    /// Unit box (1 x 1 x 1), scaled into curbs and the imp's plinth.
    pub block: MeshData,
    /// Unit sphere, scaled into bullets (TEMPORARY(WP3.5)).
    pub bullet: MeshData,
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
        bullet: icosphere(2, 1.0),
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
    /// Registered [`StageMeshData::bullet`].
    pub bullet: MeshHandle,
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
            bullet: MeshHandle(0),
            marker_ring: MeshHandle(0),
        }
    }
}

/// Camera of the prototype; the executable replaces `target` with its follow spring every frame.
#[must_use]
pub fn camera_template() -> Camera25D {
    let mut camera = Camera25D::default();
    camera.target = crate::arena::PLAYER_START.to_array();
    camera.tilt_degrees = 62.0;
    camera.fov_y_degrees = 40.0;
    camera.distance = 22.0;
    camera.look_ahead_max = 1.5;
    camera.look_ahead_smoothing = 0.3;
    camera
}

/// Interpolated player position: the camera's follow target.
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
    }
}

/// Material slots every frame starts with, in this order.
mod slot {
    pub const FLOOR: u32 = 0;
    pub const PILLAR: u32 = 1;
    pub const PLINTH: u32 = 2;
    pub const MARKER: u32 = 3;
    pub const EMBER: u32 = 4;
    pub const THORN: u32 = 5;
    pub const COUNT: u32 = 6;
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
    // TEMPORARY(WP3.5): bullet bodies in the hostile palettes H0 and H1 of the style bible.
    let magenta = linear(0xFF_2F_B4);
    frame.materials.push(material(magenta, 0.4, magenta));
    let lime = linear(0xB6_FF_2E);
    frame.materials.push(material(lime, 0.4, lime));
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
    // so the prototype uses the "Low" preset: blob shadows under figures, pillars and bullets.
    shadows.mode = ShadowMode::Blob;
    frame.shadow_config = shadows;

    frame
        .meshes
        .push(mesh(visuals.floor, slot::FLOOR, IDENTITY));

    let edge = ARENA_HALF + Vec2::splat(CURB_GAP + CURB_DEPTH * 0.5);
    let pillar_x = edge.x + CURB_DEPTH;
    let pillar_y = edge.y + CURB_DEPTH;
    let mut torch_index = 0_u32;
    for &x in &[-pillar_x, -pillar_x * 0.5, 0.0, pillar_x * 0.5, pillar_x] {
        for &y in &[-pillar_y, pillar_y] {
            push_pillar(visuals, frame, Vec2::new(x, y), &mut torch_index);
        }
    }
    for &x in &[-pillar_x, pillar_x] {
        push_pillar(visuals, frame, Vec2::new(x, 0.0), &mut torch_index);
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
fn push_figure(
    figure: &FigureVisual,
    transform: Mat4,
    hit: bool,
    emissive: Option<[f32; 3]>,
    frame: &mut StageFrame,
) {
    let pose = if hit {
        &figure.hit_pose
    } else {
        &figure.rest_pose
    };
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
fn push_player(world: &World, alpha: f32, visuals: &ArenaVisuals, frame: &mut StageFrame) {
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

    let Some(age) = hit_age else {
        let transform = mul(
            translation([at.x, at.y, soul.ground_lift + lift]),
            rotation_z(yaw),
        );
        push_figure(soul, transform, false, None, frame);
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
    let visible = age < 20 || (age / HIT_BLINK_TICKS).is_multiple_of(2);
    if visible {
        push_figure(soul, transform, true, Some(red), frame);
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
fn push_imp(world: &World, alpha: f32, visuals: &ArenaVisuals, frame: &mut StageFrame) {
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
    push_figure(&visuals.imp, transform, false, None, frame);
    // A dim glow from the imp's hands, in the warm light family (never a bullet colour).
    let mut glow = PointLight::default();
    glow.position = [position.at.x, position.at.y - 0.6, PLINTH_HEIGHT + 1.0];
    glow.color = linear(0xFF_7A_3A);
    glow.intensity = 3.0;
    glow.range = 5.0;
    frame.point_lights.push(glow);
}

/// Every live bullet: the bullet channel, and TEMPORARY(WP3.5) meshes, blob shadows and lights.
fn push_bullets(world: &World, alpha: f32, visuals: &ArenaVisuals, frame: &mut StageFrame) {
    let (Some(pool), Some(content)) = (
        world.resource::<BulletPool>(),
        world.resource::<SigilContent>(),
    ) else {
        return;
    };
    let units = content.library().units();
    let mut lights = 0_usize;
    for bullet in pool.iter() {
        let Some(bullet_type) = units
            .get(usize::from(bullet.unit_index()))
            .and_then(|unit| unit.bullet_types().get(usize::from(bullet.bullet_type())))
        else {
            continue;
        };
        let at = bullet.previous_position().lerp(bullet.position(), alpha);
        let velocity = bullet.velocity();
        let rotation = if velocity.length_squared() > 0.0 {
            velocity.angle()
        } else {
            0.0
        };
        let visual = bullet_type.visual;
        let instance = BulletInstance {
            position: at.to_array(),
            radius: bullet_type.radius,
            rotation,
            silhouette: visual.silhouette,
            palette: visual.palette,
            palette_space: palette_space::HOSTILE,
            glow: visual.glow,
            flags: 0,
        };
        frame.bullets.push(instance);

        // TEMPORARY(WP3.5): draw the bullet as an emissive mesh until the bullet pass exists.
        let radius = bullet_type.radius;
        let shape = if visual.silhouette == imp_volley::SILHOUETTE_RICE {
            [radius * 1.9, radius * 0.7, radius * 0.7]
        } else {
            [radius, radius, radius]
        };
        let material = if visual.palette == imp_volley::PALETTE_LIME {
            slot::THORN
        } else {
            slot::EMBER
        };
        let transform = mul(
            mul(
                translation([at.x, at.y, BULLET_DRAW_HEIGHT]),
                rotation_z(rotation),
            ),
            scale(shape),
        );
        frame.meshes.push(mesh(visuals.bullet, material, transform));
        frame.blob_shadows.push(blob(at, radius * 1.4, 0.5));
        if lights < MAX_BULLET_LIGHTS {
            let mut light = point_light_from_bullet(&instance);
            light.position[2] = BULLET_DRAW_HEIGHT;
            frame.point_lights.push(light);
            lights += 1;
        }
    }
}

/// Fills `frame` with the arena, the figures and the bullets of `world`, interpolated by `alpha`.
///
/// `frame` should come cleared ([`StageFrame::clear`]); the camera is left to the caller.
pub fn extract(world: &World, alpha: f32, visuals: &ArenaVisuals, frame: &mut StageFrame) {
    push_stage_materials(frame);
    push_arena(visuals, frame);
    push_imp(world, alpha, visuals, frame);
    push_player(world, alpha, visuals, frame);
    push_bullets(world, alpha, visuals, frame);
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
        extract(sim.world(), 0.0, &visuals, &mut frame);
        frame.camera_25d = Some(camera_template());
        let stats = render(&frame);
        assert_eq!(stats.meshes_rejected_invalid, 0);
        assert_eq!(stats.meshes_rejected_layer, 0);
        assert_eq!(stats.materials_rejected_invalid, 0);
        assert_eq!(stats.point_lights_rejected_invalid, 0);
        assert!(!stats.key_light_rejected_invalid);
        assert!(!stats.ambient_rejected_invalid);
        assert_eq!(stats.bullets_drawn, 0);
        // Floor, 12 pillars, 4 curbs, plinth, imp, soul and the marker ring.
        assert_eq!(frame.meshes.len(), 1 + 12 + 4 + 1 + 1 + 1 + 1);
    }

    #[test]
    fn bullets_reach_the_bullet_channel_and_the_temporary_meshes() {
        let mut sim = built();
        // Walk away from the aimed fan so the round is still running.
        let mut input = TickInput::default();
        input.slots[0].axes[0] = i16::MAX;
        for _ in 0..140 {
            sim.step(input);
        }
        let visuals = ArenaVisuals::placeholder();
        let mut frame = StageFrame::new();
        extract(sim.world(), 0.5, &visuals, &mut frame);
        let live = hud(sim.world()).bullets as usize;
        assert!(live > 0, "the imp has fired");
        assert_eq!(frame.bullets.len(), live);
        let stats = render(&frame);
        assert_eq!(stats.bullets_drawn as usize, live);
        assert_eq!(stats.bullets_rejected_invalid, 0);
        assert_eq!(stats.bullets_rejected_palette_space, 0);
        assert_eq!(stats.meshes_rejected_invalid, 0);
        assert_eq!(
            stats.bullet_point_lights_drawn as usize,
            live.min(MAX_BULLET_LIGHTS)
        );
        for bullet in &frame.bullets {
            assert!(bullet.position.iter().all(|c| c.is_finite()));
        }
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
        extract(sim.world(), 0.0, &visuals, &mut frame);
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
    }

    #[test]
    fn the_marker_ring_is_a_valid_mesh() {
        let data = stage_mesh_data();
        for mesh in [
            &data.floor,
            &data.pillar,
            &data.block,
            &data.bullet,
            &data.marker_ring,
        ] {
            mesh.validate().expect("valid procedural mesh");
        }
    }
}
