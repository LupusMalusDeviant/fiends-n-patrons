//! # fnp_sim_harness
//!
//! Headless simulation harness of Fiends n Patrons: bot-driven runs by seed, invariant checks,
//! golden-master replays and balancing reports (PRD-0018).
//!
//! **Status:** P0. [`run_seed`] runs the [`FiendsGame`] plugin through the facade's
//! `App::run_headless` with the scripted [`bot_input`]; [`simulate`] drives the same run on a
//! bare [`Simulation`] so tests can inspect game state. The integration tests in
//! `tests/determinism.rs` prove determinism and freeze a golden final hash.

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
    App::new(WindowConfig {
        title: String::from(GAME_TITLE),
        ..WindowConfig::default()
    })
    .seed(seed)
    // run_headless steps a fixed tick count and ignores the rate; set for symmetry with fnp_app.
    .tick_rate(TICK_RATE_HZ)
    .hash_every(HASH_EVERY)
    .plugin(FiendsGame::new())
    .run_headless(ticks, input)
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
}
