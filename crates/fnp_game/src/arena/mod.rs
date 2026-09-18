//! First playable prototype: one arena, the player soul, one imp firing Sigil patterns.
//!
//! [`ArenaGame`] is the simulation side (a [`GamePlugin`] whose [`GamePlugin::build`] installs
//! everything); [`present`] turns a world into a [`grimoire::render::StageFrame`] and never feeds
//! anything back.
//!
//! ## One tick
//!
//! Systems run in this order, each as its own exclusive stage:
//!
//! 0. `arena.toggle_mode`: a fresh press of button [`CURTAIN_BUTTON`] switches the imp between its
//!    normal attack (`imp_volley`) and the curtain mode (`imp_curtain`, about ten thousand live
//!    bullets, the soul invulnerable): the imp's emitters are replaced and every bullet cleared.
//! 1. `arena.remember_previous`: positions become the interpolation start.
//! 2. `arena.steer_player`: input axes 0/1 steer the soul with light momentum (PRD-0005 FR-01),
//!    confined to the arena and kept out of the imp; frozen while the round is lost.
//! 3. `arena.aim`: the player's new position becomes the Sigil [`AimTarget`].
//! 4. The five `sigil.*` phases of the engine interpreter (contract §11.6) move, despawn and emit
//!    bullets.
//! 5. `arena.broadphase`: every live bullet enters the [`SpatialGrid`] (the game-side stand-in for
//!    the facade's `collide.broadphase`, contract §9.6, which is not implemented yet).
//! 6. `arena.player_hit`: a bullet overlapping the player's capsule ends the round: the imp's
//!    emitters pause, every bullet is cleared through a [`ClearRequest`]. Not in curtain mode.
//! 7. `arena.restart_round`: [`HIT_RECOVERY_TICKS`] after a hit, the player returns to the start
//!    and the emitters restart.
//!
//! ## Determinism
//!
//! Same rules as the rest of the crate: all state is in the world, motion scales by [`DT`], math
//! goes through `dmath`, no randomness is drawn outside the Sigil interpreter's own streams.

pub mod patterns;
pub mod present;

use std::sync::Arc;

use grimoire::collide::{
    Capsule, Circle, ColliderKey, CollisionQuery, GridConfig, GridItem, LayerMask, Shape,
    SpatialGrid,
};
use grimoire::prelude::*;
use grimoire::sigil::{
    AimTarget, BehaviorRegistryBuilder, BulletPool, ClearFilter, ClearRequest, Emitter,
    SigilConfig, SigilContent, SigilLibrary, SigilUnit, UnitId, install,
};

use crate::{DT, Player, Position, PreviousPosition, Velocity};

/// Half extents of the walkable arena, in world units (1 unit = 1 m).
pub const ARENA_HALF: Vec2 = Vec2::new(10.5, 7.0);

/// Where the player starts every round.
pub const PLAYER_START: Vec2 = Vec2::new(0.0, -4.0);

/// Where the imp stands.
pub const IMP_POSITION: Vec2 = Vec2::new(0.0, 3.5);

/// Top speed of the player in world units per second.
pub const PLAYER_SPEED: f32 = 5.5;

/// Fraction of the gap between current and target velocity the player closes per tick.
///
/// PRD-0005 FR-01 asks for 90 % of the target speed within fewer than 3 ticks while keeping a
/// light momentum: `1 - (1 - 0.55)^3 = 0.909` after three ticks.
pub const PLAYER_RESPONSE: f32 = 0.55;

/// Radius of the player's hit capsule (PRD-0005 FR-03: a capsule of model size).
///
/// Provisional: a shoulder-wide capsule on the ground plane, not measured from the figure.
pub const PLAYER_HIT_RADIUS: f32 = 0.28;

/// Half length of the hit capsule's segment along X (the shoulder line).
pub const PLAYER_HIT_HALF_WIDTH: f32 = 0.12;

/// Distance from the imp's centre the player cannot enter.
pub const IMP_BODY_RADIUS: f32 = 0.9;

/// Ticks between a hit and the restart of the round (1.5 s at 60 Hz).
pub const HIT_RECOVERY_TICKS: u64 = 90;

/// Capacity of the bullet pool: the curtain mode keeps about ten thousand bullets alive.
pub const BULLET_CAPACITY: u32 = 16_384;

/// Input button that toggles the curtain mode (bound to a key by the executable).
pub const CURTAIN_BUTTON: u8 = 3;

/// Input button that cycles the fiend's fight pattern through the roster (bound to a key by
/// the executable); only a game built with [`ArenaGame::with_roster`] listens to it.
pub const PATTERN_BUTTON: u8 = 5;

/// Input button that cycles the camera presets (bound to a key by the executable).
///
/// Presentation only: the stage plugin reads it from the tick input; no system of the simulation
/// looks at it, so the camera never changes what happens in the arena.
pub const CAMERA_BUTTON: u8 = 4;

/// How far outside the arena bullets live before the interpreter despawns them.
pub const BULLET_BOUNDS_MARGIN: f32 = 3.0;

/// Collision layer every bullet of the imp belongs to.
pub const HOSTILE_BULLET_LAYER: LayerMask = LayerMask::layer(0);

/// Version of the (still empty) behaviour registry (contract §11.5).
pub const BEHAVIOR_REGISTRY_VERSION: u32 = 1;

/// Squared speed below which a gliding player comes to rest (keeps denormals out of the state).
const REST_SPEED_SQUARED: f32 = 1.0e-4;

/// Squared input length above which the input also turns the player (filters stick noise).
const FACING_INPUT_SQUARED: f32 = 0.04;

/// Direction the player faces at the start of a round: towards the imp.
const START_FACING: Vec2 = Vec2::new(0.0, 1.0);

/// Which pattern the imp plays.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Mode {
    /// The normal attack, `content/sigil/imp_volley.sigil`.
    Volley,
    /// The curtain stress mode, `content/sigil/imp_curtain.sigil`; the soul cannot be hit.
    Curtain,
}

impl StableHash for Mode {
    fn stable_hash(&self, hasher: &mut StableHasher) {
        match self {
            Mode::Volley => 0_u8.stable_hash(hasher),
            Mode::Curtain => 1_u8.stable_hash(hasher),
        }
    }
}

/// Resource: the imp's current pattern and the edge detector of the toggle button.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ArenaMode {
    /// Pattern playing now.
    pub mode: Mode,
    /// Whether [`CURTAIN_BUTTON`] was held in the previous tick (a press toggles once).
    pub toggle_held: bool,
}
impl_stable_hash!(ArenaMode { mode, toggle_held });

/// One entry of a playable roster: a pattern with the emitters the fiend fires and the name the
/// window title shows.
#[derive(Clone, Debug)]
pub struct RosterEntry {
    /// Short name of the pattern, as `content/sigil/` spells it.
    pub name: &'static str,
    /// The unit and the emitters fired from it.
    pub pattern: ScenePattern,
}

impl RosterEntry {
    /// An entry named `name` that plays `pattern`.
    #[must_use]
    pub fn new(name: &'static str, pattern: ScenePattern) -> Self {
        Self { name, pattern }
    }
}

/// What a playable arena can throw at the player: the fight patterns [`PATTERN_BUTTON`] cycles and
/// the curtain [`CURTAIN_BUTTON`] toggles.
#[derive(Clone, Debug)]
pub struct Roster {
    /// Fight patterns in cycling order; the first one starts the run. Never empty.
    pub fight: Vec<RosterEntry>,
    /// The curtain stress mode, if the roster has one.
    pub curtain: Option<RosterEntry>,
}

impl Roster {
    /// The entry that plays in `mode` with fight pattern `index`.
    #[must_use]
    pub fn entry(&self, mode: Mode, index: u16) -> Option<&RosterEntry> {
        match mode {
            Mode::Curtain => self.curtain.as_ref(),
            Mode::Volley => self.fight.get(usize::from(index) % self.fight.len().max(1)),
        }
    }

    /// Every unit the roster can play, each one once, as the Sigil library takes them.
    #[must_use]
    pub fn units(&self) -> Vec<SigilUnit> {
        let mut units: Vec<SigilUnit> = Vec::new();
        for entry in self.fight.iter().chain(self.curtain.iter()) {
            let id = entry.pattern.unit.id();
            if !units.iter().any(|unit| unit.id() == id) {
                units.push(entry.pattern.unit.clone());
            }
        }
        units
    }
}

/// The roster the prototype plays: every fight pattern of `content/sigil/` in
/// [`patterns::GamePattern::FIGHT_ORDER`], plus the imp's curtain.
#[must_use]
pub fn playable_roster() -> Roster {
    Roster {
        fight: patterns::GamePattern::FIGHT_ORDER
            .iter()
            .map(|pattern| RosterEntry::new(pattern.name(), pattern.scene_pattern()))
            .collect(),
        curtain: Some(RosterEntry::new(
            patterns::GamePattern::ImpCurtain.name(),
            patterns::GamePattern::ImpCurtain.scene_pattern(),
        )),
    }
}

/// Resource: which fight pattern of the roster plays and the edge detector of [`PATTERN_BUTTON`].
///
/// Only a game built with [`ArenaGame::with_roster`] has it; the imp's own arena (the golden
/// path) does not, and its state is untouched by the roster.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RosterState {
    /// Index into [`Roster::fight`].
    pub index: u16,
    /// Whether [`PATTERN_BUTTON`] was held in the previous tick (a press cycles once).
    pub cycle_held: bool,
}
impl_stable_hash!(RosterState { index, cycle_held });

/// Resource: the unit ids of the imp's two patterns, as loaded into the Sigil library.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ImpUnits {
    /// `imp_volley`.
    pub volley: UnitId,
    /// `imp_curtain`.
    pub curtain: UnitId,
}
impl_stable_hash!(ImpUnits { volley, curtain });

/// Direction the player faces, a unit vector on the ground plane.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Facing {
    /// Unit direction.
    pub direction: Vec2,
}
impl_stable_hash!(Facing { direction });

/// Marker of the imp entity (the one carrying the aimed volley emitter).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Imp;
impl_stable_hash!(Imp {});

/// Whether the current round is still being fought.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Phase {
    /// The player is alive and the imp fires.
    Fighting,
    /// A bullet hit the player at `at_tick`; the round restarts [`HIT_RECOVERY_TICKS`] later.
    Hit {
        /// Tick of the hit.
        at_tick: u64,
    },
}

impl StableHash for Phase {
    fn stable_hash(&self, hasher: &mut StableHasher) {
        match *self {
            Phase::Fighting => 0_u8.stable_hash(hasher),
            Phase::Hit { at_tick } => {
                1_u8.stable_hash(hasher);
                at_tick.stable_hash(hasher);
            }
        }
    }
}

/// Resource: round bookkeeping.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct RoundState {
    /// Round number, starting at 1.
    pub round: u32,
    /// Current phase.
    pub phase: Phase,
    /// Tick the current round started at.
    pub started_at: u64,
    /// Hits taken since the run started.
    pub hits: u32,
    /// Player position at the most recent hit (presentation anchor of the hit reaction).
    pub last_hit_position: Vec2,
}
impl_stable_hash!(RoundState {
    round,
    phase,
    started_at,
    hits,
    last_hit_position
});

impl RoundState {
    fn first() -> Self {
        Self {
            round: 1,
            phase: Phase::Fighting,
            started_at: 0,
            hits: 0,
            last_hit_position: PLAYER_START,
        }
    }
}

/// Grid of the bullet broadphase: covers the arena plus the bullet bounds with 2 m cells.
#[must_use]
pub fn grid_config() -> GridConfig {
    let half = ARENA_HALF + Vec2::splat(BULLET_BOUNDS_MARGIN + 2.0);
    let cell = 2.0;
    GridConfig::new(
        -half,
        cell,
        (2.0 * half.x / cell) as u32,
        (2.0 * half.y / cell) as u32,
    )
}

/// Copies every position into its [`PreviousPosition`] before anything moves.
fn remember_previous(world: &mut World) {
    for (previous, position) in world.query_mut::<(&mut PreviousPosition, &Position)>() {
        previous.at = position.at;
    }
}

fn is_fighting(world: &World) -> bool {
    world
        .resource::<RoundState>()
        .is_some_and(|round| round.phase == Phase::Fighting)
}

/// Pushes `at` out of the imp's body circle.
fn keep_out_of_imp(at: Vec2) -> Vec2 {
    let offset = at - IMP_POSITION;
    let distance_squared = offset.length_squared();
    if distance_squared >= IMP_BODY_RADIUS * IMP_BODY_RADIUS {
        return at;
    }
    let distance = dmath::sqrt(distance_squared);
    if distance <= 1.0e-4 {
        // Exactly on the centre: push straight towards the player start.
        return IMP_POSITION - Vec2::new(0.0, IMP_BODY_RADIUS);
    }
    IMP_POSITION + offset / distance * IMP_BODY_RADIUS
}

/// Steers the player towards the velocity requested by axes 0 and 1, with light momentum.
fn steer_player(world: &mut World) {
    let input = world.resource::<TickInput>().copied().unwrap_or_default();
    let fighting = is_fighting(world);
    let slot = input.slots[0];
    let requested = Vec2::new(slot.axis(0), slot.axis(1));
    // Analog input keeps its magnitude; only digital diagonals are scaled back to unit length.
    let direction = if requested.length_squared() > 1.0 {
        requested.normalize_or_zero()
    } else {
        requested
    };
    let target = if fighting {
        direction * PLAYER_SPEED
    } else {
        Vec2::ZERO
    };
    for (position, velocity, facing, _) in
        world.query_mut::<(&mut Position, &mut Velocity, &mut Facing, &Player)>()
    {
        if !fighting {
            velocity.value = Vec2::ZERO;
            continue;
        }
        velocity.value = velocity.value.lerp(target, PLAYER_RESPONSE);
        if target == Vec2::ZERO && velocity.value.length_squared() < REST_SPEED_SQUARED {
            velocity.value = Vec2::ZERO;
        }
        let moved = position.at + velocity.value * DT;
        let clamped = Vec2::new(
            moved.x.clamp(-ARENA_HALF.x, ARENA_HALF.x),
            moved.y.clamp(-ARENA_HALF.y, ARENA_HALF.y),
        );
        // Hitting a wall absorbs the momentum along that axis.
        if clamped.x != moved.x {
            velocity.value.x = 0.0;
        }
        if clamped.y != moved.y {
            velocity.value.y = 0.0;
        }
        position.at = keep_out_of_imp(clamped);
        if direction.length_squared() > FACING_INPUT_SQUARED {
            facing.direction = direction.normalize_or_zero();
        }
    }
}

/// Position of the player after the most recent movement.
fn player_position(world: &World) -> Option<Vec2> {
    world
        .query::<(&Position, &Player)>()
        .next()
        .map(|(position, _)| position.at)
}

/// Aims the imp's patterns at the player's position of this tick.
fn aim_at_player(world: &mut World) {
    let target = player_position(world);
    world.insert_resource(AimTarget(target));
}

/// Enters every live bullet into the [`SpatialGrid`] in pool slot order.
fn broadphase(world: &mut World) {
    let Some(mut grid) = world.remove_resource::<SpatialGrid>() else {
        return;
    };
    let items: Vec<GridItem> = match (
        world.resource::<BulletPool>(),
        world.resource::<SigilContent>(),
    ) {
        (Some(pool), Some(content)) => {
            let units = content.library().units();
            pool.iter()
                .filter_map(|bullet| {
                    let unit = units.get(usize::from(bullet.unit_index()))?;
                    let bullet_type = unit.bullet_types().get(usize::from(bullet.bullet_type()))?;
                    let id = bullet.id();
                    Some(GridItem {
                        key: ColliderKey::pool(id.index(), id.generation()),
                        shape: Shape::Circle(Circle {
                            center: bullet.position(),
                            radius: bullet_type.collision_radius,
                        }),
                        layers: HOSTILE_BULLET_LAYER,
                    })
                })
                .collect()
        }
        _ => Vec::new(),
    };
    grid.rebuild_par(world.executor(), items);
    world.insert_resource(grid);
}

/// The player's hit capsule at `center` (PRD-0005 FR-03).
#[must_use]
pub fn player_hit_shape(center: Vec2) -> Shape {
    let half = Vec2::new(PLAYER_HIT_HALF_WIDTH, 0.0);
    Shape::Capsule(Capsule {
        a: center - half,
        b: center + half,
        radius: PLAYER_HIT_RADIUS,
    })
}

/// Ends the round when a bullet overlaps the player.
fn player_hit(world: &mut World) {
    let Some(mut round) = world.resource::<RoundState>().copied() else {
        return;
    };
    if round.phase != Phase::Fighting {
        return;
    }
    if world
        .resource::<ArenaMode>()
        .is_some_and(|mode| mode.mode == Mode::Curtain)
    {
        return;
    }
    let (Some(player), Some(grid)) = (player_position(world), world.resource::<SpatialGrid>())
    else {
        return;
    };
    let mut hits = Vec::new();
    grid.overlapping(&player_hit_shape(player), HOSTILE_BULLET_LAYER, &mut hits);
    if hits.is_empty() {
        return;
    }
    let tick = world.resource::<Tick>().map_or(0, |tick| tick.0);
    round.phase = Phase::Hit { at_tick: tick };
    round.hits = round.hits.saturating_add(1);
    round.last_hit_position = player;
    world.insert_resource(round);
    // Emitters are stateless (contract §11.4): moving `started_at` into the future pauses them and
    // restarts their pattern from the beginning when the round restarts.
    let restart = tick.saturating_add(HIT_RECOVERY_TICKS);
    for emitter in world.query_mut::<&mut Emitter>() {
        emitter.started_at = restart;
    }
    // Games request clears, they never clear the pool themselves (contract §2a, §11.4).
    world.spawn((ClearRequest {
        filter: ClearFilter::All,
    },));
    for (velocity, _) in world.query_mut::<(&mut Velocity, &Player)>() {
        velocity.value = Vec2::ZERO;
    }
}

/// Restarts the round [`HIT_RECOVERY_TICKS`] after a hit.
fn restart_round(world: &mut World) {
    let Some(mut round) = world.resource::<RoundState>().copied() else {
        return;
    };
    let Phase::Hit { at_tick } = round.phase else {
        return;
    };
    let tick = world.resource::<Tick>().map_or(0, |tick| tick.0);
    if tick < at_tick.saturating_add(HIT_RECOVERY_TICKS) {
        return;
    }
    round.round = round.round.saturating_add(1);
    round.phase = Phase::Fighting;
    round.started_at = tick;
    world.insert_resource(round);
    for (position, previous, velocity, facing, _) in world.query_mut::<(
        &mut Position,
        &mut PreviousPosition,
        &mut Velocity,
        &mut Facing,
        &Player,
    )>() {
        // Both ends of the interpolation jump, so the soul does not streak across the arena.
        position.at = PLAYER_START;
        previous.at = PLAYER_START;
        velocity.value = Vec2::ZERO;
        facing.direction = START_FACING;
    }
    for emitter in world.query_mut::<&mut Emitter>() {
        emitter.started_at = tick;
    }
}

/// Spawns one emitter entity per emitter of the unit `mode` plays, all starting at `started_at`.
///
/// Every emitter fires with rotation 0: the patterns give absolute directions.
fn spawn_emitters(world: &mut World, units: ImpUnits, mode: Mode, started_at: u64) {
    let (unit, emitters): (UnitId, &[u16]) = match mode {
        Mode::Volley => (
            units.volley,
            &[
                fnp_content::sigil::imp_volley::AIMED,
                fnp_content::sigil::imp_volley::FAN,
                fnp_content::sigil::imp_volley::RING,
            ],
        ),
        Mode::Curtain => (
            units.curtain,
            &[
                fnp_content::sigil::imp_curtain::COUNTER,
                fnp_content::sigil::imp_curtain::CURTAIN,
            ],
        ),
    };
    for &emitter in emitters {
        world.spawn((Emitter {
            unit,
            emitter,
            origin: IMP_POSITION,
            rotation: 0.0,
            started_at,
        },));
    }
}

/// Switches the imp's pattern on a fresh press of [`CURTAIN_BUTTON`].
fn toggle_mode(world: &mut World) {
    let input = world.resource::<TickInput>().copied().unwrap_or_default();
    let held = input.slots[0].is_pressed(CURTAIN_BUTTON);
    let (Some(mut mode), Some(units)) = (
        world.resource::<ArenaMode>().copied(),
        world.resource::<ImpUnits>().copied(),
    ) else {
        return;
    };
    let pressed = held && !mode.toggle_held;
    mode.toggle_held = held;
    if pressed {
        mode.mode = match mode.mode {
            Mode::Volley => Mode::Curtain,
            Mode::Curtain => Mode::Volley,
        };
        let tick = world.resource::<Tick>().map_or(0, |tick| tick.0);
        // A lost round keeps its restart tick; the new emitters wait for it like the old ones.
        let started_at = match world.resource::<RoundState>().map(|round| round.phase) {
            Some(Phase::Hit { at_tick }) => at_tick.saturating_add(HIT_RECOVERY_TICKS),
            _ => tick,
        };
        let old: Vec<Entity> = world
            .query::<(Entity, &Emitter)>()
            .map(|(entity, _)| entity)
            .collect();
        for entity in old {
            world.despawn(entity);
        }
        spawn_emitters(world, units, mode.mode, started_at);
        // Games request clears, they never clear the pool themselves (contract §2a, §11.4).
        world.spawn((ClearRequest {
            filter: ClearFilter::All,
        },));
    }
    world.insert_resource(mode);
}

/// Spawns the emitters of the roster entry that plays in `mode` with fight pattern `index`.
fn spawn_roster_emitters(world: &mut World, roster: &Roster, mode: Mode, index: u16, at: u64) {
    let Some(entry) = roster.entry(mode, index) else {
        return;
    };
    let unit = entry.pattern.unit.id();
    for &emitter in &entry.pattern.emitters {
        world.spawn((Emitter {
            unit,
            emitter,
            origin: IMP_POSITION,
            rotation: 0.0,
            started_at: at,
        },));
    }
}

/// Replaces the fiend's emitters with the ones of the entry playing now and clears the arena.
///
/// A switch always clears: in a real round the clear does most of the despawning, so leftovers of
/// the previous pattern would otherwise keep flying through the new one (and, for a pattern that
/// never ends on its own, pile up across rounds).
fn restart_roster(world: &mut World, roster: &Roster, mode: Mode, index: u16) {
    let tick = world.resource::<Tick>().map_or(0, |tick| tick.0);
    // A lost round keeps its restart tick; the new emitters wait for it like the old ones.
    let started_at = match world.resource::<RoundState>().map(|round| round.phase) {
        Some(Phase::Hit { at_tick }) => at_tick.saturating_add(HIT_RECOVERY_TICKS),
        _ => tick,
    };
    let old: Vec<Entity> = world
        .query::<(Entity, &Emitter)>()
        .map(|(entity, _)| entity)
        .collect();
    for entity in old {
        world.despawn(entity);
    }
    spawn_roster_emitters(world, roster, mode, index, started_at);
    // Games request clears, they never clear the pool themselves (contract §2a, §11.4).
    world.spawn((ClearRequest {
        filter: ClearFilter::All,
    },));
}

/// The roster's system: [`PATTERN_BUTTON`] cycles the fight patterns, [`CURTAIN_BUTTON`] toggles
/// the curtain, and cycling while the curtain plays leaves it.
fn switch_pattern(world: &mut World, roster: &Roster) {
    let input = world.resource::<TickInput>().copied().unwrap_or_default();
    let (Some(mut mode), Some(mut state)) = (
        world.resource::<ArenaMode>().copied(),
        world.resource::<RosterState>().copied(),
    ) else {
        return;
    };
    let curtain_held = input.slots[0].is_pressed(CURTAIN_BUTTON);
    let cycle_held = input.slots[0].is_pressed(PATTERN_BUTTON);
    let curtain_pressed = curtain_held && !mode.toggle_held;
    let cycle_pressed = cycle_held && !state.cycle_held;
    mode.toggle_held = curtain_held;
    state.cycle_held = cycle_held;
    let mut switched = false;
    if cycle_pressed && !roster.fight.is_empty() {
        let next = usize::from(state.index).saturating_add(1) % roster.fight.len();
        state.index = u16::try_from(next).unwrap_or(0);
        // Cycling always shows a fight pattern, even while the curtain plays.
        mode.mode = Mode::Volley;
        switched = true;
    }
    if curtain_pressed && roster.curtain.is_some() {
        mode.mode = match mode.mode {
            Mode::Volley => Mode::Curtain,
            Mode::Curtain => Mode::Volley,
        };
        switched = true;
    }
    if switched {
        restart_roster(world, roster, mode.mode, state.index);
    }
    world.insert_resource(mode);
    world.insert_resource(state);
}

/// One pattern of a harness scene: a compiled unit and the emitters of it the fiend fires.
///
/// Sub-emitters (`role = sub`) never belong here; they fire through a bullet's `become_emitter`
/// transform, not from the fiend.
#[derive(Clone, Debug)]
pub struct ScenePattern {
    /// The compiled unit.
    pub unit: SigilUnit,
    /// Emitter indices of [`Self::unit`] that start at tick 0.
    pub emitters: Vec<u16>,
}

impl ScenePattern {
    /// A pattern that fires the given emitters of `unit`.
    #[must_use]
    pub fn new(unit: SigilUnit, emitters: Vec<u16>) -> Self {
        Self { unit, emitters }
    }
}

/// The first playable prototype's game plugin.
///
/// [`ArenaGame::new`] builds the arena of the imp alone: its two patterns and the curtain toggle,
/// the shape the golden masters of `imp_arena` and `imp_curtain` pin.
/// [`ArenaGame::with_roster`] builds the playable arena of the executable: the same player, the
/// same collision and the same rounds, but with every pattern of `content/sigil/` on
/// [`PATTERN_BUTTON`] ([`playable_roster`]). [`ArenaGame::with_patterns`] is the harness's way in:
/// one fixed pattern set, all emitters from tick 0 (Plan 0002 WP7.4).
///
/// The three differ only in the units they install and the switching system they add, so neither
/// of the latter two can move the golden hashes of the first.
#[derive(Debug, Default)]
pub struct ArenaGame {
    /// `None` is the imp with its two modes; `Some` is a scene's own pattern set.
    scene: Option<Vec<ScenePattern>>,
    /// `Some` is the playable roster on [`PATTERN_BUTTON`] and [`CURTAIN_BUTTON`].
    roster: Option<Arc<Roster>>,
}

impl ArenaGame {
    /// Creates the plugin as the imp's own arena plays it.
    #[must_use]
    pub fn new() -> Self {
        Self {
            scene: None,
            roster: None,
        }
    }

    /// Creates the plugin with a pattern set of its own; the curtain toggle is inert in it.
    #[must_use]
    pub fn with_patterns(patterns: Vec<ScenePattern>) -> Self {
        Self {
            scene: Some(patterns),
            roster: None,
        }
    }

    /// Creates the playable plugin: the roster's first fight pattern starts, [`PATTERN_BUTTON`]
    /// cycles the rest and [`CURTAIN_BUTTON`] toggles the curtain.
    #[must_use]
    pub fn with_roster(roster: Arc<Roster>) -> Self {
        Self {
            scene: None,
            roster: Some(roster),
        }
    }
}

impl GamePlugin for ArenaGame {
    fn name(&self) -> &str {
        "fiends_n_patrons.arena"
    }

    fn build(&mut self, sim: &mut Simulation) {
        let world = sim.world_mut();
        world.insert_resource(RoundState::first());
        world.insert_resource(ArenaMode {
            mode: Mode::Volley,
            toggle_held: false,
        });
        world.insert_resource(
            SpatialGrid::new(grid_config()).expect("the arena grid configuration is valid"),
        );
        world.spawn((
            Position { at: PLAYER_START },
            PreviousPosition { at: PLAYER_START },
            Velocity { value: Vec2::ZERO },
            Facing {
                direction: START_FACING,
            },
            Player,
        ));
        match self.roster.clone() {
            // The roster's switching system carries the roster itself; only the index and the
            // edge detectors live in the world.
            Some(roster) => {
                sim.schedule_mut().add_system(system_fn(
                    "arena.switch_pattern",
                    move |world: &mut World| switch_pattern(world, &roster),
                ));
            }
            None => {
                sim.schedule_mut()
                    .add_system(system_fn("arena.toggle_mode", toggle_mode));
            }
        }
        sim.schedule_mut()
            .add_system(system_fn("arena.remember_previous", remember_previous))
            .add_system(system_fn("arena.steer_player", steer_player))
            .add_system(system_fn("arena.aim", aim_at_player));

        let scene = self.scene.take();
        let roster = self.roster.take();
        let registry = BehaviorRegistryBuilder::new(BEHAVIOR_REGISTRY_VERSION).build();
        let bounds = ARENA_HALF + Vec2::splat(BULLET_BOUNDS_MARGIN);
        let units = match (&scene, &roster) {
            (None, Some(roster)) => {
                let library = SigilLibrary::new(roster.units(), Arc::clone(&registry))
                    .expect("the roster's units form a valid library");
                install(
                    sim,
                    library,
                    registry,
                    SigilConfig::new(BULLET_CAPACITY, -bounds, bounds),
                )
                .expect("the Sigil interpreter installs once");
                // No ImpUnits resource: the roster's own system knows the units.
                sim.world_mut().insert_resource(RosterState {
                    index: 0,
                    cycle_held: false,
                });
                None
            }
            (None, None) => {
                let volley =
                    fnp_content::sigil::imp_volley().expect("the embedded volley unit decodes");
                let curtain =
                    fnp_content::sigil::imp_curtain().expect("the embedded curtain unit decodes");
                let imp = ImpUnits {
                    volley: volley.id(),
                    curtain: curtain.id(),
                };
                let library = SigilLibrary::new(vec![volley, curtain], Arc::clone(&registry))
                    .expect("the imp units form a valid library");
                install(
                    sim,
                    library,
                    registry,
                    SigilConfig::new(BULLET_CAPACITY, -bounds, bounds),
                )
                .expect("the Sigil interpreter installs once");
                Some(imp)
            }
            (Some(patterns), _) => {
                let library = SigilLibrary::new(
                    patterns
                        .iter()
                        .map(|pattern| pattern.unit.clone())
                        .collect(),
                    Arc::clone(&registry),
                )
                .expect("a scene's units form a valid library");
                install(
                    sim,
                    library,
                    registry,
                    SigilConfig::new(BULLET_CAPACITY, -bounds, bounds),
                )
                .expect("the Sigil interpreter installs once");
                // No ImpUnits resource: a scene has no second mode, so the toggle does nothing.
                None
            }
        };

        let world = sim.world_mut();
        world.spawn((
            Position { at: IMP_POSITION },
            PreviousPosition { at: IMP_POSITION },
            Imp,
        ));
        match (units, &scene, &roster) {
            (Some(units), _, _) => {
                world.insert_resource(units);
                spawn_emitters(world, units, Mode::Volley, 0);
            }
            (None, None, Some(roster)) => {
                spawn_roster_emitters(world, roster, Mode::Volley, 0, 0);
            }
            (None, Some(patterns), _) => {
                for pattern in patterns {
                    for &emitter in &pattern.emitters {
                        world.spawn((Emitter {
                            unit: pattern.unit.id(),
                            emitter,
                            origin: IMP_POSITION,
                            rotation: 0.0,
                            started_at: 0,
                        },));
                    }
                }
            }
            (None, None, None) => unreachable!("the imp path always has its units"),
        }

        sim.schedule_mut()
            .add_system(system_fn("arena.broadphase", broadphase))
            .add_system(system_fn("arena.player_hit", player_hit))
            .add_system(system_fn("arena.restart_round", restart_round));
    }

    fn focus(&self, world: &World, alpha: f32) -> Option<Vec2> {
        present::player_focus(world, alpha)
    }
}

#[cfg(test)]
mod tests;
