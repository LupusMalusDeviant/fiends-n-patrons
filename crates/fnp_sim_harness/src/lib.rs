//! # fnp_sim_harness
//!
//! Headless simulation harness of Fiends n Patrons: bot-driven runs by seed, invariant checks,
//! golden-master replays and balancing reports (PRD-0018).
//!
//! **Status:** first playable prototype. [`run_arena`] runs the [`ArenaGame`] plugin through the
//! facade's `App::run_headless` with any per-tick input, usually the scripted
//! [`arena_bot_input`]; [`simulate_arena`] drives the same run on a bare [`Simulation`] so tests
//! can inspect game state, and [`run_arena_with_executor`] repeats the bot run on a given
//! executor. The integration tests in `tests/determinism.rs` prove determinism, freeze a golden
//! final hash and check every checkpoint with 1, 2 and N threads.

use std::sync::Arc;

use fnp_game::arena::ArenaGame;
use fnp_game::{GAME_TITLE, TICK_RATE_HZ};
use grimoire::HeadlessReport;
use grimoire::prelude::*;

/// Ticks between recorded state hashes in harness reports (one per simulated second).
pub const HASH_EVERY: u64 = 60;

/// Axis value of a fully deflected stick.
const FULL: i32 = i16::MAX as i32;

/// Scripted, deterministic bot input for the arena: a pure function of the tick.
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
    fn arena_bot_input_moves_both_ways_and_rests() {
        let frames: Vec<TickInput> = (0..600).map(arena_bot_input).collect();
        let axis_x = |frame: &TickInput| frame.slots[0].axes[0];
        assert!(frames.iter().any(|f| axis_x(f) == i16::MAX));
        assert!(frames.iter().any(|f| axis_x(f) == -i16::MAX));
        assert!(frames[510..].iter().all(|f| *f == TickInput::default()));
        assert!(
            frames
                .iter()
                .all(|f| f.slots[1..] == [InputFrame::default(); 3])
        );
        for tick in [0, 1, 359, 360, 509, 510, 599, 600, 10_000] {
            assert_eq!(arena_bot_input(tick), arena_bot_input(tick));
        }
    }
}
