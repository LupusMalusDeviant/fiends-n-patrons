//! Determinism gate of the game (PRD-0018 FR-04a): identical runs, seed and input sensitivity and
//! a golden final hash through the facade's headless path.
//!
//! Seed and input sensitivity compare game state (positions and the circle centre), never state
//! hashes: the hash also covers the seed and the stored `TickInput`, so it differs between seeds
//! or inputs even if the game ignored them.

use fnp_game::{Player, Position, RitualCircle};
use fnp_sim_harness::{HASH_EVERY, bot_input, run_seed, run_with_input, simulate};
use grimoire::prelude::*;

/// Seed of the golden run.
const GOLDEN_SEED: u64 = 42;

/// Length of the golden run: one minute of simulation at 60 Hz.
const GOLDEN_TICKS: u64 = 3_600;

/// Final state hash of `run_seed(GOLDEN_SEED, GOLDEN_TICKS)`.
///
/// This is a frozen expectation (golden master). The value was captured locally on Windows (debug
/// and release profile) and confirmed by CI on Windows, Linux and macOS in the debug profile (game
/// CI run 34903989101); the nightly workflow repeats the check in the release profile. A mismatch
/// on a single platform is a determinism bug and never a reason to change the value.
///
/// Renew it only deliberately, following CONTRIBUTING.md ("Golden-Master und Referenzwerte"):
/// understand and name the cause first (intended change to the demo scenario or the bot, or an
/// engine upgrade whose CHANGELOG announces a hash change), then renew it in a separate commit
/// `test(golden): renew <what> after <why>` right after the causing change, stating old and new
/// value and the first diverging checkpoint. Never renew it for one platform or to make CI green;
/// agents do not renew golden masters on their own, the PO decides.
const GOLDEN_FINAL_HASH: u64 = 0x5270_20ae_cf76_4ca7;

#[test]
fn identical_runs_give_identical_reports() {
    let first = run_seed(GOLDEN_SEED, 1_200);
    let second = run_seed(GOLDEN_SEED, 1_200);
    assert_eq!(first, second);
    assert_eq!(first.final_tick, 1_200);
    let ticks: Vec<u64> = first.hashes.iter().map(|&(tick, _)| tick).collect();
    assert_eq!(
        ticks,
        (1..=1_200 / HASH_EVERY)
            .map(|i| i * HASH_EVERY)
            .collect::<Vec<_>>()
    );
}

/// Every position in the world (motes and player, in query order); contains no seed or input.
fn positions(sim: &Simulation) -> Vec<Vec2> {
    sim.world()
        .query::<&Position>()
        .map(|position| position.at)
        .collect()
}

fn player_position(sim: &Simulation) -> Vec2 {
    sim.world()
        .query::<(&Position, &Player)>()
        .next()
        .map(|(position, _)| position.at)
        .expect("the player exists")
}

fn circle_center(sim: &Simulation) -> Vec2 {
    sim.world()
        .resource::<RitualCircle>()
        .expect("the ritual circle exists")
        .center
}

#[test]
fn simulate_matches_the_headless_report() {
    for ticks in [0, 1, 600] {
        let sim = simulate(GOLDEN_SEED, ticks, &mut bot_input);
        let report = run_seed(GOLDEN_SEED, ticks);
        assert_eq!(sim.tick(), report.final_tick);
        assert_eq!(sim.state_hash(), report.final_hash);

        let idle_sim = simulate(GOLDEN_SEED, ticks, &mut |_| TickInput::default());
        let idle_report = run_with_input(GOLDEN_SEED, ticks, &mut |_| TickInput::default());
        assert_eq!(idle_sim.state_hash(), idle_report.final_hash);
    }
}

#[test]
fn different_seeds_give_different_game_states() {
    let seeds = [1, 2, GOLDEN_SEED, u64::MAX];
    let states: Vec<Vec<Vec2>> = seeds
        .into_iter()
        .map(|seed| positions(&simulate(seed, 600, &mut bot_input)))
        .collect();
    for (index, state) in states.iter().enumerate() {
        for (other_index, other) in states.iter().enumerate().skip(index + 1) {
            assert_ne!(
                state, other,
                "seeds {} and {} give identical positions after 600 ticks",
                seeds[index], seeds[other_index]
            );
        }
    }
    assert_eq!(
        states[2],
        positions(&simulate(GOLDEN_SEED, 600, &mut bot_input))
    );
}

#[test]
fn different_seeds_already_differ_after_spawning() {
    let first = positions(&simulate(1, 0, &mut bot_input));
    assert_ne!(first, positions(&simulate(2, 0, &mut bot_input)));
    assert_eq!(first, positions(&simulate(1, 0, &mut bot_input)));
}

#[test]
fn bot_input_changes_the_outcome() {
    let bot = simulate(GOLDEN_SEED, 600, &mut bot_input);
    let idle = simulate(GOLDEN_SEED, 600, &mut |_| TickInput::default());
    assert_eq!(player_position(&idle), Vec2::ZERO, "idle player stays put");
    assert_ne!(player_position(&bot), player_position(&idle));
    assert_ne!(circle_center(&bot), circle_center(&idle));
    assert_ne!(positions(&bot), positions(&idle));
}

#[test]
fn golden_final_hash_for_seed_42() {
    let report = run_seed(GOLDEN_SEED, GOLDEN_TICKS);
    assert_eq!(report.final_tick, GOLDEN_TICKS);
    assert_eq!(
        report.final_hash,
        GOLDEN_FINAL_HASH,
        "golden final hash changed: expected {GOLDEN_FINAL_HASH:#018x}, got {:#018x}.\n\
         Compare these checkpoints with a platform that passes to find the first diverging tick:\n{}",
        report.final_hash,
        report
            .hashes
            .iter()
            .map(|(tick, hash)| format!("  tick {tick:>5}: {hash:#018x}"))
            .collect::<Vec<_>>()
            .join("\n")
    );
}
