//! # fnp_sim_harness
//!
//! Headless simulation harness of Fiends n Patrons: bot-driven runs by seed, invariant checks,
//! golden-master replays and balancing reports (PRD-0018).
//!
//! **Status:** P0. [`run_seed`] runs the [`FiendsGame`] plugin through the facade's
//! `App::run_headless` with the scripted [`bot_input`]; [`simulate`] drives the same run on a
//! bare [`Simulation`] so tests can inspect game state. [`run_seed_with_executor`] repeats the
//! headless run on a given executor. The integration tests in `tests/determinism.rs` prove
//! determinism, freeze a golden final hash and check it with 1, 2 and N threads.
//!
//! The first playable prototype ([`fnp_game::arena::ArenaGame`]) has its own entry points:
//! [`run_arena`], [`run_arena_with_executor`] and [`simulate_arena`], driven by the scripted
//! [`arena_bot_input`]; its gate lives in `tests/arena_determinism.rs`.

use std::sync::Arc;

use fnp_game::arena::ArenaGame;
use fnp_game::{FiendsGame, GAME_TITLE, TICK_RATE_HZ};
use grimoire::HeadlessReport;
use grimoire::prelude::*;

/// Ticks between recorded state hashes in harness reports (one per simulated second).
pub const HASH_EVERY: u64 = 60;

/// Axis value of a fully deflected stick.
const FULL: i32 = i16::MAX as i32;

/// Scripted, deterministic bot input for `tick`: a pure function of the tick number.
///
/// The bot sweeps axis 0 back and forth (triangle wave, 8 s period), alternates axis 1 between
/// up and down every 1.5 s, channels the ritual (button 0) for 1 s out of every 5 s and lets go of
/// the stick for the last 2 s of every 12 s, so the player's momentum decays to rest. Integer
/// arithmetic only, so the input is identical on every platform.
#[must_use]
pub fn bot_input(tick: u64) -> TickInput {
    let mut input = TickInput::default();
    let idle = tick % 720 >= 600;
    if !idle {
        let phase = i32::try_from(tick % 480).unwrap_or(0);
        let triangle = if phase < 240 { phase } else { 480 - phase };
        let x = (triangle - 120) * FULL / 120;
        let y = if tick % 180 < 90 { FULL } else { -FULL };
        let slot = &mut input.slots[0];
        slot.axes[0] = i16::try_from(x).unwrap_or(0);
        slot.axes[1] = i16::try_from(y).unwrap_or(0);
    }
    input.slots[0].buttons = u32::from(tick % 300 < 60);
    input
}

/// Runs the game headless for `ticks` ticks with `seed` and the scripted [`bot_input`].
#[must_use]
pub fn run_seed(seed: u64, ticks: u64) -> HeadlessReport {
    run_with_input(seed, ticks, &mut bot_input)
}

/// Runs the game headless for `ticks` ticks with `seed`; `input(tick)` supplies each tick's input.
#[must_use]
pub fn run_with_input(
    seed: u64,
    ticks: u64,
    input: &mut dyn FnMut(u64) -> TickInput,
) -> HeadlessReport {
    game_app(seed).run_headless(ticks, input)
}

/// Runs [`run_seed`] with `executor` installed on the simulation's world through
/// `AppBuilder::executor` (engine ADR-0006).
///
/// The game's systems are exclusive, so the report must not depend on the executor or its thread
/// count; `tests/determinism.rs` checks the golden run with 1, 2 and N threads.
#[must_use]
pub fn run_seed_with_executor(
    seed: u64,
    ticks: u64,
    executor: Arc<dyn Executor>,
) -> HeadlessReport {
    game_app(seed)
        .executor(executor)
        .run_headless(ticks, &mut bot_input)
}

/// The headless game app with `seed`, shared by every harness run.
fn game_app(seed: u64) -> AppBuilder {
    App::new(WindowConfig {
        title: String::from(GAME_TITLE),
        ..WindowConfig::default()
    })
    .seed(seed)
    // run_headless steps a fixed tick count and ignores the rate; set for symmetry with fnp_app.
    .tick_rate(TICK_RATE_HZ)
    .hash_every(HASH_EVERY)
    .plugin(FiendsGame::new())
}

/// Builds the game into a fresh [`Simulation`] with `seed` and steps it `ticks` times.
///
/// Same order as `run_headless`: build the plugin, then `step(input(tick))` per tick, so the final
/// [`Simulation::state_hash`] equals the `final_hash` of [`run_with_input`]. Unlike the report,
/// the returned simulation exposes the game state (positions, orbits, the ritual circle).
#[must_use]
pub fn simulate(seed: u64, ticks: u64, input: &mut dyn FnMut(u64) -> TickInput) -> Simulation {
    let mut sim = Simulation::new(seed);
    FiendsGame::new().build(&mut sim);
    for _ in 0..ticks {
        sim.step(input(sim.tick()));
    }
    sim
}

/// Scripted, deterministic bot input for the arena prototype: a pure function of the tick.
///
/// The bot strafes along the bottom of the arena (triangle wave on axis 0, 6 s period), drifts
/// up and down every 2.5 s, and stands still for the last 1.5 s of every 10 s so the imp's aimed
/// fan catches it now and then: the scenario covers movement, bullets, hits and round restarts.
/// Integer arithmetic only.
#[must_use]
pub fn arena_bot_input(tick: u64) -> TickInput {
    let mut input = TickInput::default();
    if tick % 600 >= 510 {
        return input;
    }
    let phase = i32::try_from(tick % 360).unwrap_or(0);
    let triangle = if phase < 180 { phase } else { 360 - phase };
    let x = (triangle - 90) * FULL / 90;
    let y = if tick % 300 < 150 {
        FULL / 3
    } else {
        -FULL / 3
    };
    let slot = &mut input.slots[0];
    slot.axes[0] = i16::try_from(x).unwrap_or(0);
    slot.axes[1] = i16::try_from(y).unwrap_or(0);
    input
}

/// Runs the arena prototype headless for `ticks` ticks; `input(tick)` supplies each tick's input.
#[must_use]
pub fn run_arena(seed: u64, ticks: u64, input: &mut dyn FnMut(u64) -> TickInput) -> HeadlessReport {
    arena_app(seed).run_headless(ticks, input)
}

/// Runs [`run_arena`] with [`arena_bot_input`] and `executor` installed on the world.
#[must_use]
pub fn run_arena_with_executor(
    seed: u64,
    ticks: u64,
    executor: Arc<dyn Executor>,
) -> HeadlessReport {
    arena_app(seed)
        .executor(executor)
        .run_headless(ticks, &mut arena_bot_input)
}

/// The headless arena app with `seed`.
fn arena_app(seed: u64) -> AppBuilder {
    App::new(WindowConfig {
        title: String::from(GAME_TITLE),
        ..WindowConfig::default()
    })
    .seed(seed)
    .tick_rate(TICK_RATE_HZ)
    .hash_every(HASH_EVERY)
    .plugin(ArenaGame::new())
}

/// Builds the arena into a fresh [`Simulation`] with `seed` and steps it `ticks` times, in the
/// order of `run_headless`, so the final state hash equals the one of [`run_arena`].
#[must_use]
pub fn simulate_arena(
    seed: u64,
    ticks: u64,
    input: &mut dyn FnMut(u64) -> TickInput,
) -> Simulation {
    let mut sim = Simulation::new(seed);
    ArenaGame::new().build(&mut sim);
    for _ in 0..ticks {
        sim.step(input(sim.tick()));
    }
    sim
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bot_input_is_a_pure_function_of_the_tick() {
        for tick in [0, 1, 239, 240, 479, 599, 600, 719, 720, 10_000] {
            assert_eq!(bot_input(tick), bot_input(tick));
        }
    }

    #[test]
    fn bot_input_covers_both_directions_buttons_and_idle_phases() {
        let frames: Vec<TickInput> = (0..720).map(bot_input).collect();
        let axis_x = |frame: &TickInput| frame.slots[0].axes[0];
        assert!(frames.iter().any(|f| axis_x(f) == i16::MAX));
        assert!(frames.iter().any(|f| axis_x(f) == -i16::MAX));
        assert!(frames.iter().any(|f| f.slots[0].is_pressed(0)));
        assert!(frames.iter().any(|f| !f.slots[0].is_pressed(0)));
        assert!(frames[600..].iter().all(|f| f.slots[0].axes == [0; 4]));
        assert!(
            frames
                .iter()
                .all(|f| f.slots[1..] == [InputFrame::default(); 3])
        );
    }

    #[test]
    fn arena_bot_input_moves_both_ways_and_rests() {
        let frames: Vec<TickInput> = (0..600).map(arena_bot_input).collect();
        let axis_x = |frame: &TickInput| frame.slots[0].axes[0];
        assert!(frames.iter().any(|f| axis_x(f) == i16::MAX));
        assert!(frames.iter().any(|f| axis_x(f) == -i16::MAX));
        assert!(frames[510..].iter().all(|f| *f == TickInput::default()));
        assert_eq!(arena_bot_input(1234), arena_bot_input(1234));
    }
}
