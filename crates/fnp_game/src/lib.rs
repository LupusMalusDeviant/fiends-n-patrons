//! # fnp_game
//!
//! Game states and run logic of Fiends n Patrons, built on the Grimoire facade.
//!
//! **Status:** first playable prototype. [`arena::ArenaGame`] is the prototype the executable
//! runs: the player soul in a lit arena, one imp firing a Sigil pattern, hits and round restarts
//! ([`arena`]). [`FiendsGame`] is the P0 demo "Beschwoerungskreis" and stays unchanged, because the
//! determinism gate's golden master is frozen on it: a player dot with light momentum, steered by
//! input axes 0 and 1, and a ritual swarm orbiting a summoning circle that slowly drifts towards
//! the player. Holding button 0 channels the ritual and speeds up the swarm.
//!
//! ## Determinism
//!
//! All simulation state lives in the world as `Clone + StableHash` components and resources. The
//! systems scale by the fixed tick length [`DT`], never by measured time, draw randomness only
//! through `derive_rng`, and use `dmath` instead of the platform float functions (engine contract
//! section 3, enforced by this crate's `clippy.toml`). Everything outside [`GamePlugin::build`] is
//! presentation and never feeds back into the simulation.

pub mod arena;

use std::sync::Arc;

use grimoire::prelude::*;

/// Display title of the game.
pub const GAME_TITLE: &str = "Fiends n Patrons";

/// Simulation rate the demo is tuned for.
///
/// Every runner that drives [`FiendsGame`] in real time must pass this value to
/// `AppBuilder::tick_rate` instead of relying on the facade default: the systems scale by [`DT`],
/// so any other rate changes the game speed. Headless runs step a fixed number of ticks and do
/// not depend on the rate.
pub const TICK_RATE_HZ: u32 = 60;

/// Seconds per tick; simulation code scales by this constant, never by measured time.
pub const DT: f32 = 1.0 / TICK_RATE_HZ as f32;

/// Number of motes in the ritual swarm.
pub const SWARM_SIZE: u32 = 360;

/// Number of concentric rings the swarm is spread over.
pub const RING_COUNT: u32 = 3;

/// Half extents of the arena the player is confined to, in world units.
pub const ARENA_HALF: Vec2 = Vec2::new(170.0, 95.0);

/// Top speed of the player in world units per second.
pub const PLAYER_SPEED: f32 = 70.0;

/// Fraction of the gap between current and target velocity the player closes per tick.
///
/// Below 1, so the player accelerates and glides to a stop instead of reacting instantly.
pub const PLAYER_RESPONSE: f32 = 0.18;

/// Squared speed below which a gliding player comes to rest (keeps denormals out of the state).
const REST_SPEED_SQUARED: f32 = 1.0e-4;

/// Fraction of the distance to the player the circle centre covers per tick.
const CIRCLE_PULL: f32 = 0.004;

/// Angular speed multiplier while button 0 is held.
const CHANNEL_BOOST: f32 = 2.5;

/// Radius of the innermost ring; every further ring adds [`RING_SPACING`].
const RING_BASE_RADIUS: f32 = 28.0;

/// Distance between neighbouring rings.
const RING_SPACING: f32 = 20.0;

/// Largest radial deviation of a mote from its ring while it wobbles.
const WOBBLE_AMPLITUDE: f32 = 3.5;

/// Input button that channels the ritual.
const CHANNEL_BUTTON: u8 = 0;

/// RNG stream of the swarm spawn (tick 0).
const SPAWN_STREAM: u64 = 1;

/// Visible world height of the camera.
const WORLD_HEIGHT: f32 = 200.0;

/// Number of rune marks drawn on the summoning circle (presentation only).
const RUNE_COUNT: u32 = 24;

/// Radius of the rune marks around the circle centre (presentation only).
const RUNE_RADIUS: f32 = RING_BASE_RADIUS + RING_COUNT as f32 * RING_SPACING;

/// Position after the most recent tick.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Position {
    /// World position.
    pub at: Vec2,
}
impl_stable_hash!(Position { at });

/// Position one tick earlier, the start point of render interpolation.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct PreviousPosition {
    /// World position before the most recent tick.
    pub at: Vec2,
}
impl_stable_hash!(PreviousPosition { at });

/// Velocity of an entity with momentum, in world units per second.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Velocity {
    /// Current velocity.
    pub value: Vec2,
}
impl_stable_hash!(Velocity { value });

/// Marker of the player entity.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Player;
impl_stable_hash!(Player {});

/// Orbit of one mote of the ritual swarm around the summoning circle.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Orbit {
    /// Ring index in `0..RING_COUNT`.
    pub ring: u32,
    /// Current angle in `[0, TAU)`.
    pub angle: f32,
    /// Signed angular speed in radians per second; odd rings turn clockwise.
    pub angular_speed: f32,
    /// Distance from the circle centre without wobble.
    pub radius: f32,
    /// Wobble phase in `[0, TAU)`.
    pub wobble: f32,
    /// Wobble speed in radians per second.
    pub wobble_speed: f32,
}
impl_stable_hash!(Orbit {
    ring,
    angle,
    angular_speed,
    radius,
    wobble,
    wobble_speed
});

impl Orbit {
    /// World position of the mote around `center`.
    #[must_use]
    pub fn position(&self, center: Vec2) -> Vec2 {
        let radius = self.radius + WOBBLE_AMPLITUDE * dmath::sin(self.wobble);
        center + Vec2::from_angle(self.angle) * radius
    }
}

/// Resource: the summoning circle the swarm orbits.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct RitualCircle {
    /// Centre after the most recent tick.
    pub center: Vec2,
    /// Centre one tick earlier, for render interpolation.
    pub previous_center: Vec2,
    /// Whether button 0 was held during the most recent tick.
    pub channeling: bool,
}
impl_stable_hash!(RitualCircle {
    center,
    previous_center,
    channeling
});

/// Keeps an angle in `[0, TAU)` so it never loses precision over long runs.
fn wrap_angle(angle: f32) -> f32 {
    if angle >= dmath::TAU {
        angle - dmath::TAU
    } else if angle < 0.0 {
        let wrapped = angle + dmath::TAU;
        // A tiny negative angle (about -2.4e-7 to 0) rounds up to exactly TAU in f32; TAU is the
        // same direction as 0 and outside the documented range.
        if wrapped >= dmath::TAU { 0.0 } else { wrapped }
    } else {
        angle
    }
}

/// Copies every position into its [`PreviousPosition`] before anything moves.
fn remember_previous(world: &mut World) {
    for (previous, position) in world.query_mut::<(&mut PreviousPosition, &Position)>() {
        previous.at = position.at;
    }
    if let Some(circle) = world.resource_mut::<RitualCircle>() {
        circle.previous_center = circle.center;
    }
}

/// Moves the player towards the velocity requested by axes 0 and 1, with light momentum.
fn steer_player(world: &mut World) {
    let input = world.resource::<TickInput>().copied().unwrap_or_default();
    let slot = input.slots[0];
    let requested = Vec2::new(slot.axis(0), slot.axis(1));
    // Analog input keeps its magnitude; only digital diagonals are scaled back to unit length.
    let direction = if requested.length_squared() > 1.0 {
        requested.normalize_or_zero()
    } else {
        requested
    };
    let target = direction * PLAYER_SPEED;
    for (position, velocity, _) in world.query_mut::<(&mut Position, &mut Velocity, &Player)>() {
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
        position.at = clamped;
    }
}

/// Lets the summoning circle drift towards the player and records whether the ritual is channeled.
fn drift_circle(world: &mut World) {
    let input = world.resource::<TickInput>().copied().unwrap_or_default();
    let channeling = input.slots[0].is_pressed(CHANNEL_BUTTON);
    let player = world
        .query::<(&Position, &Player)>()
        .next()
        .map_or(Vec2::ZERO, |(position, _)| position.at);
    if let Some(circle) = world.resource_mut::<RitualCircle>() {
        circle.center = circle.center.lerp(player, CIRCLE_PULL);
        circle.channeling = channeling;
    }
}

/// Advances every mote on its orbit around the current circle centre.
fn orbit_swarm(world: &mut World) {
    let Some(circle) = world.resource::<RitualCircle>().copied() else {
        return;
    };
    let boost = if circle.channeling {
        CHANNEL_BOOST
    } else {
        1.0
    };
    for (position, orbit) in world.query_mut::<(&mut Position, &mut Orbit)>() {
        orbit.angle = wrap_angle(orbit.angle + orbit.angular_speed * boost * DT);
        orbit.wobble = wrap_angle(orbit.wobble + orbit.wobble_speed * DT);
        position.at = orbit.position(circle.center);
    }
}

/// Spawns the ritual swarm deterministically from the simulation seed.
fn spawn_swarm(world: &mut World, seed: u64, center: Vec2) {
    let mut rng = derive_rng(seed, 0, SPAWN_STREAM);
    for index in 0..SWARM_SIZE {
        let ring = index % RING_COUNT;
        let direction = if ring.is_multiple_of(2) { 1.0 } else { -1.0 };
        let orbit = Orbit {
            ring,
            angle: rng.range_f32(0.0, dmath::TAU),
            angular_speed: direction * rng.range_f32(0.35, 0.9),
            radius: RING_BASE_RADIUS + ring as f32 * RING_SPACING + rng.range_f32(-4.0, 4.0),
            wobble: rng.range_f32(0.0, dmath::TAU),
            wobble_speed: rng.range_f32(0.8, 2.6),
        };
        let at = orbit.position(center);
        world.spawn((Position { at }, PreviousPosition { at }, orbit));
    }
}

/// Colour of a mote on `ring`; brighter while the ritual is channeled.
fn mote_color(ring: u32, channeling: bool) -> [f32; 4] {
    let glow = if channeling { 0.25 } else { 0.0 };
    match ring % RING_COUNT {
        0 => [0.95, 0.25 + glow, 0.15 + glow, 0.9],
        1 => [0.7 + glow, 0.2, 0.85, 0.9],
        _ => [1.0, 0.65 + glow, 0.2, 0.9],
    }
}

/// The Fiends n Patrons game plugin (P0 demo "Beschwoerungskreis").
///
/// Holds presentation state only; the simulation state lives in the world.
#[derive(Default)]
pub struct FiendsGame {
    seed: Option<u64>,
    window: Option<Arc<dyn PlatformWindow>>,
    shown_fps: f64,
}

impl FiendsGame {
    /// Creates the plugin.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    fn title(&self, fps: Option<f64>) -> String {
        let mut title = format!("{GAME_TITLE} - Beschwoerungskreis");
        if let Some(seed) = self.seed {
            title.push_str(&format!(" - seed {seed}"));
        }
        if let Some(fps) = fps {
            title.push_str(&format!(" - {fps:.0} FPS"));
        }
        title
    }
}

impl GamePlugin for FiendsGame {
    fn name(&self) -> &str {
        "fiends_n_patrons"
    }

    fn build(&mut self, sim: &mut Simulation) {
        let seed = sim.seed();
        self.seed = Some(seed);
        let world = sim.world_mut();
        world.insert_resource(RitualCircle {
            center: Vec2::ZERO,
            previous_center: Vec2::ZERO,
            channeling: false,
        });
        spawn_swarm(world, seed, Vec2::ZERO);
        world.spawn((
            Position { at: Vec2::ZERO },
            PreviousPosition { at: Vec2::ZERO },
            Velocity { value: Vec2::ZERO },
            Player,
        ));

        sim.schedule_mut()
            .add_system(system_fn("remember_previous", remember_previous))
            .add_system(system_fn("steer_player", steer_player))
            .add_system(system_fn("drift_circle", drift_circle))
            .add_system(system_fn("orbit_swarm", orbit_swarm));
    }

    fn extract(&mut self, world: &World, alpha: f32, frame: &mut RenderFrame) {
        frame.clear_color = [0.03, 0.01, 0.02, 1.0];
        frame.camera = Camera2D {
            center: [0.0, 0.0],
            world_height: WORLD_HEIGHT,
        };

        let circle = world.resource::<RitualCircle>().copied();
        let channeling = circle.is_some_and(|circle| circle.channeling);
        if let Some(circle) = circle {
            let center = circle.previous_center.lerp(circle.center, alpha);
            for rune in 0..RUNE_COUNT {
                let angle = rune as f32 * dmath::TAU / RUNE_COUNT as f32;
                frame.sprites.push(SpriteInstance {
                    position: (center + Vec2::from_angle(angle) * RUNE_RADIUS).to_array(),
                    half_size: [1.2, 1.2],
                    rotation: angle,
                    shape: shape::QUAD,
                    color: [0.45, 0.08, 0.1, 1.0],
                });
            }
        }

        for (previous, position, orbit) in world.query::<(&PreviousPosition, &Position, &Orbit)>() {
            frame.sprites.push(SpriteInstance {
                position: previous.at.lerp(position.at, alpha).to_array(),
                half_size: [0.9, 0.9],
                rotation: 0.0,
                shape: shape::CIRCLE,
                color: mote_color(orbit.ring, channeling),
            });
        }

        for (previous, position, _) in world.query::<(&PreviousPosition, &Position, &Player)>() {
            frame.sprites.push(SpriteInstance {
                position: previous.at.lerp(position.at, alpha).to_array(),
                half_size: [2.6, 2.6],
                rotation: 0.0,
                shape: shape::CIRCLE,
                color: [0.95, 0.95, 1.0, 1.0],
            });
        }
    }

    fn on_frame(&mut self, stats: &FrameStats) {
        // The FPS changes once per measurement window; setting the title more often costs time.
        if stats.fps == self.shown_fps {
            return;
        }
        self.shown_fps = stats.fps;
        if let Some(window) = &self.window {
            window.set_title(&self.title(Some(stats.fps)));
        }
    }

    fn window_created(&mut self, window: &Arc<dyn PlatformWindow>) {
        window.set_title(&self.title(None));
        self.window = Some(Arc::clone(window));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const RIGHT: i16 = i16::MAX;

    fn built(seed: u64) -> Simulation {
        let mut sim = Simulation::new(seed);
        FiendsGame::new().build(&mut sim);
        sim
    }

    fn input(axis_x: i16, axis_y: i16, buttons: u32) -> TickInput {
        let mut input = TickInput::default();
        input.slots[0].axes[0] = axis_x;
        input.slots[0].axes[1] = axis_y;
        input.slots[0].buttons = buttons;
        input
    }

    fn player(sim: &Simulation) -> (Vec2, Vec2) {
        sim.world()
            .query::<(&Position, &Velocity, &Player)>()
            .next()
            .map(|(position, velocity, _)| (position.at, velocity.value))
            .expect("the player exists")
    }

    #[test]
    fn build_spawns_the_swarm_and_one_player() {
        let sim = built(42);
        let world = sim.world();
        assert_eq!(world.query::<&Orbit>().count(), SWARM_SIZE as usize);
        assert_eq!(world.query::<&Player>().count(), 1);
        assert_eq!(world.entity_count(), SWARM_SIZE as usize + 1);
        assert!(world.resource::<RitualCircle>().is_some());
    }

    /// Orbits of all motes in spawn order.
    fn orbits(sim: &Simulation) -> Vec<Orbit> {
        sim.world().query::<&Orbit>().copied().collect()
    }

    /// Change of an angle over one tick, taking a wrap across 0 or TAU into account.
    fn angle_delta(before: f32, after: f32) -> f32 {
        let delta = after - before;
        if delta > dmath::PI {
            delta - dmath::TAU
        } else if delta < -dmath::PI {
            delta + dmath::TAU
        } else {
            delta
        }
    }

    fn assert_finite(value: Vec2, what: &str) {
        assert!(
            value.x.is_finite() && value.y.is_finite(),
            "{what} is not finite: {value:?}"
        );
    }

    #[test]
    fn the_spawn_depends_only_on_the_seed() {
        // Compares the spawned orbits, not state hashes: the hash contains the seed itself (and
        // the SimSeed resource), so it differs between seeds even if the spawn ignored the seed.
        assert_eq!(orbits(&built(7)), orbits(&built(7)));
        assert_ne!(orbits(&built(7)), orbits(&built(8)));
        assert_eq!(built(7).state_hash(), built(7).state_hash());
    }

    #[test]
    fn wrap_angle_keeps_every_angle_in_zero_to_tau() {
        // The f32 rounding the fix guards against.
        assert_eq!(-1.0e-7_f32 + dmath::TAU, dmath::TAU);
        assert_eq!(wrap_angle(-1.0e-7), 0.0);
        assert_eq!(wrap_angle(-2.3e-7), 0.0);
        assert_eq!(wrap_angle(-f32::MIN_POSITIVE), 0.0);
        assert_eq!(wrap_angle(dmath::TAU), 0.0);
        assert_eq!(wrap_angle(0.0), 0.0);
        assert_eq!(wrap_angle(-0.5), -0.5 + dmath::TAU);
        let over = dmath::TAU + 0.5;
        assert_eq!(wrap_angle(over), over - dmath::TAU);
        for angle in [
            -1.0, -1.0e-3, -2.5e-7, -1.0e-7, -1.0e-30, 0.0, 1.0e-7, 3.0, 6.25, 6.3, 7.0,
        ] {
            let wrapped = wrap_angle(angle);
            assert!(
                (0.0..dmath::TAU).contains(&wrapped),
                "wrap_angle({angle:e}) = {wrapped:e}"
            );
        }
    }

    #[test]
    fn the_player_accelerates_and_glides_to_a_stop() {
        let mut sim = built(1);
        sim.step(input(RIGHT, 0, 0));
        let (_, first) = player(&sim);
        assert!(
            first.x > 0.0 && first.x < PLAYER_SPEED,
            "momentum: {first:?}"
        );
        for _ in 0..60 {
            sim.step(input(RIGHT, 0, 0));
        }
        let (held, full) = player(&sim);
        assert!(full.x > first.x && full.x <= PLAYER_SPEED);

        sim.step(TickInput::default());
        let (glided, gliding) = player(&sim);
        assert!(glided.x > held.x, "keeps moving after release");
        assert!(gliding.x < full.x);

        for _ in 0..240 {
            sim.step(TickInput::default());
        }
        let (rest, velocity) = player(&sim);
        assert_eq!(velocity, Vec2::ZERO);
        sim.step(TickInput::default());
        assert_eq!(player(&sim).0, rest);
    }

    #[test]
    fn the_player_stays_inside_the_arena() {
        let mut sim = built(3);
        for _ in 0..600 {
            sim.step(input(-RIGHT, RIGHT, 0));
        }
        let (position, velocity) = player(&sim);
        assert_eq!(position, Vec2::new(-ARENA_HALF.x, ARENA_HALF.y));
        assert_eq!(velocity, Vec2::ZERO);
    }

    #[test]
    fn diagonal_input_is_not_faster_than_straight_input() {
        let mut straight = built(5);
        let mut diagonal = built(5);
        for _ in 0..120 {
            straight.step(input(RIGHT, 0, 0));
            diagonal.step(input(RIGHT, RIGHT, 0));
        }
        let straight_speed = player(&straight).1.length();
        let diagonal_speed = player(&diagonal).1.length();
        assert!(diagonal_speed <= straight_speed + 1.0e-3);
    }

    #[test]
    fn the_swarm_orbits_near_the_circle_and_channeling_is_recorded() {
        let mut calm = built(9);
        let mut channeled = built(9);
        for _ in 0..300 {
            calm.step(TickInput::default());
            channeled.step(input(0, 0, 1 << CHANNEL_BUTTON));
        }
        let max_radius = RING_BASE_RADIUS
            + (RING_COUNT - 1) as f32 * RING_SPACING
            + 4.0
            + WOBBLE_AMPLITUDE
            + 1.0e-3;
        let center = calm
            .world()
            .resource::<RitualCircle>()
            .expect("circle")
            .center;
        for position in calm.world().query::<(&Position, &Orbit)>() {
            assert!(position.0.at.distance(center) <= max_radius);
        }
        assert!(
            channeled
                .world()
                .resource::<RitualCircle>()
                .expect("circle")
                .channeling
        );
        assert!(
            !calm
                .world()
                .resource::<RitualCircle>()
                .expect("circle")
                .channeling
        );
    }

    #[test]
    fn channeling_multiplies_the_angular_advance_by_the_boost() {
        // Two identical simulations reach the same state, then take one calm and one channeled
        // tick; motes are matched by spawn order.
        let mut calm = built(9);
        let mut channeled = built(9);
        for tick in 0..150_u64 {
            let buttons = u32::from(tick % 40 < 10);
            calm.step(input(RIGHT, 0, buttons));
            channeled.step(input(RIGHT, 0, buttons));
        }
        let before = orbits(&calm);
        assert_eq!(before, orbits(&channeled));

        calm.step(input(RIGHT, 0, 0));
        channeled.step(input(RIGHT, 0, 1 << CHANNEL_BUTTON));

        let calm_after = orbits(&calm);
        let channeled_after = orbits(&channeled);
        assert_eq!(before.len(), SWARM_SIZE as usize);
        for ((start, calm_end), channeled_end) in
            before.iter().zip(&calm_after).zip(&channeled_after)
        {
            let calm_delta = angle_delta(start.angle, calm_end.angle);
            let channeled_delta = angle_delta(start.angle, channeled_end.angle);
            // Angles near TAU have an f32 spacing of about 5e-7; the deltas are 6e-3 or larger.
            let tolerance = 1.0e-5;
            assert!(
                (calm_delta - start.angular_speed * DT).abs() <= tolerance,
                "calm mote advanced {calm_delta}, expected {}",
                start.angular_speed * DT
            );
            assert!(
                (channeled_delta - CHANNEL_BOOST * calm_delta).abs() <= tolerance,
                "channeled mote advanced {channeled_delta}, expected {} x {calm_delta}",
                CHANNEL_BOOST
            );
            // The wobble does not depend on channeling.
            assert_eq!(calm_end.wobble, channeled_end.wobble);
        }
    }

    #[test]
    fn the_circle_drifts_towards_the_player() {
        let mut sim = built(11);
        for _ in 0..240 {
            sim.step(input(RIGHT, 0, 0));
        }
        let circle = *sim.world().resource::<RitualCircle>().expect("circle");
        assert!(circle.center.x > 0.0);
        assert!(circle.center.x < player(&sim).0.x);
    }

    #[test]
    fn extract_interpolates_between_the_previous_and_current_tick() {
        let mut sim = built(13);
        let mut game = FiendsGame::new();
        for _ in 0..30 {
            sim.step(input(RIGHT, 0, 0));
        }
        let (current, _) = player(&sim);
        let previous = sim
            .world()
            .query::<(&PreviousPosition, &Player)>()
            .next()
            .map(|(previous, _)| previous.at)
            .expect("the player exists");
        assert_ne!(previous, current);

        let mut frame = RenderFrame::default();
        game.extract(sim.world(), 0.0, &mut frame);
        let expected = (RUNE_COUNT + SWARM_SIZE + 1) as usize;
        assert_eq!(frame.sprites.len(), expected);
        assert_eq!(frame.sprites[expected - 1].position, previous.to_array());

        frame.sprites.clear();
        game.extract(sim.world(), 0.5, &mut frame);
        assert_eq!(
            frame.sprites[expected - 1].position,
            previous.lerp(current, 0.5).to_array()
        );
    }

    #[test]
    fn long_runs_keep_angles_wrapped_and_the_state_finite() {
        let mut sim = built(17);
        for tick in 0..3_000_u64 {
            let buttons = u32::from(tick % 200 < 50);
            sim.step(input(
                if tick % 400 < 200 { RIGHT } else { -RIGHT },
                0,
                buttons,
            ));
        }
        let world = sim.world();
        for orbit in world.query::<&Orbit>() {
            assert!((0.0..dmath::TAU).contains(&orbit.angle));
            assert!((0.0..dmath::TAU).contains(&orbit.wobble));
            assert!(orbit.angular_speed.is_finite() && orbit.wobble_speed.is_finite());
            assert!(orbit.radius.is_finite());
        }
        let mut positions = 0;
        for (position, previous) in world.query::<(&Position, &PreviousPosition)>() {
            assert_finite(position.at, "position");
            assert_finite(previous.at, "previous position");
            positions += 1;
        }
        assert_eq!(positions, SWARM_SIZE as usize + 1);
        let mut velocities = 0;
        for velocity in world.query::<&Velocity>() {
            assert_finite(velocity.value, "velocity");
            velocities += 1;
        }
        assert_eq!(velocities, 1);
        let circle = world.resource::<RitualCircle>().expect("circle");
        assert_finite(circle.center, "circle centre");
        assert_finite(circle.previous_center, "previous circle centre");
        // Extra NaN guard: state_hash panics in debug builds if any NaN reached the state.
        let _ = sim.state_hash();
    }

    #[test]
    fn the_title_names_game_seed_and_fps() {
        let mut game = FiendsGame::new();
        assert_eq!(game.title(None), "Fiends n Patrons - Beschwoerungskreis");
        game.build(&mut Simulation::new(42));
        assert_eq!(
            game.title(Some(59.6)),
            "Fiends n Patrons - Beschwoerungskreis - seed 42 - 60 FPS"
        );
    }
}
