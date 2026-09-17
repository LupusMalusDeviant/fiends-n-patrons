//! Determinism gate of the first playable prototype (PRD-0018 FR-04a): identical runs, input
//! sensitivity, thread-count independence (engine ADR-0006) and a golden final hash, over a
//! scenario in which the Sigil interpreter fires, the broadphase finds hits and rounds restart.

use fnp_game::arena::{Phase, RoundState};
use fnp_game::{Player, Position};
use fnp_sim_harness::{
    HASH_EVERY, arena_bot_input, run_arena, run_arena_with_executor, simulate_arena,
};
use grimoire::prelude::*;
use grimoire::sigil::BulletPool;
use grimoire_exec::gate_executors;

/// Seed of the golden arena run.
const GOLDEN_SEED: u64 = 42;

/// Length of the golden arena run: one minute at 60 Hz.
const GOLDEN_TICKS: u64 = 3_600;

/// Final state hash of `run_arena(GOLDEN_SEED, GOLDEN_TICKS, arena_bot_input)`.
///
/// A frozen expectation for the prototype scenario, captured locally on Windows (debug and release
/// profile) when the scenario was written. Same rules as the P0 golden in `determinism.rs`: a
/// mismatch on one platform is a determinism bug, never a reason to change the value; renewing it
/// follows CONTRIBUTING.md ("Golden-Master und Referenzwerte") and is the PO's decision.
const GOLDEN_ARENA_FINAL_HASH: u64 = 0x9001_d4a1_d2f7_125e;

fn round(sim: &Simulation) -> RoundState {
    *sim.world().resource::<RoundState>().expect("round state")
}

#[test]
fn identical_arena_runs_give_identical_reports() {
    let first = run_arena(GOLDEN_SEED, 1_200, &mut arena_bot_input);
    let second = run_arena(GOLDEN_SEED, 1_200, &mut arena_bot_input);
    assert_eq!(first, second);
    assert_eq!(first.hashes.len() as u64, 1_200 / HASH_EVERY);
}

#[test]
fn simulate_arena_matches_the_headless_report() {
    for ticks in [0, 1, 700] {
        let sim = simulate_arena(GOLDEN_SEED, ticks, &mut arena_bot_input);
        let report = run_arena(GOLDEN_SEED, ticks, &mut arena_bot_input);
        assert_eq!(sim.tick(), report.final_tick);
        assert_eq!(sim.state_hash(), report.final_hash);
    }
}

#[test]
fn the_bot_scenario_covers_bullets_hits_and_restarts() {
    let mut sim = simulate_arena(GOLDEN_SEED, 0, &mut arena_bot_input);
    let mut peak_bullets = 0;
    let mut saw_hit = false;
    for _ in 0..GOLDEN_TICKS {
        sim.step(arena_bot_input(sim.tick()));
        let pool = sim.world().resource::<BulletPool>().expect("pool");
        peak_bullets = peak_bullets.max(pool.len());
        saw_hit |= matches!(round(&sim).phase, Phase::Hit { .. });
    }
    let state = round(&sim);
    assert!(saw_hit, "the bot is hit at least once");
    assert!(state.hits >= 1 && state.round >= 2, "{state:?}");
    assert!(peak_bullets > 50, "peak bullets {peak_bullets}");
    println!(
        "arena bot scenario: {} rounds, {} hits, peak {peak_bullets} bullets",
        state.round, state.hits
    );
}

#[test]
fn input_changes_the_arena_outcome() {
    let bot = simulate_arena(GOLDEN_SEED, 90, &mut arena_bot_input);
    let idle = simulate_arena(GOLDEN_SEED, 90, &mut |_| TickInput::default());
    let player = |sim: &Simulation| {
        sim.world()
            .query::<(&Position, &Player)>()
            .next()
            .map(|(position, _)| position.at)
            .expect("the player exists")
    };
    assert_ne!(player(&bot), player(&idle));
}

#[test]
fn golden_arena_final_hash_for_seed_42() {
    let report = run_arena(GOLDEN_SEED, GOLDEN_TICKS, &mut arena_bot_input);
    assert_eq!(report.final_tick, GOLDEN_TICKS);
    assert_eq!(
        report.final_hash,
        GOLDEN_ARENA_FINAL_HASH,
        "golden arena hash changed: expected {GOLDEN_ARENA_FINAL_HASH:#018x}, got {:#018x}.\n\
         Checkpoints for comparison with a platform that passes:\n{}",
        report.final_hash,
        report
            .hashes
            .iter()
            .map(|(tick, hash)| format!("  tick {tick:>5}: {hash:#018x}"))
            .collect::<Vec<_>>()
            .join("\n")
    );
}

/// Hash gate of engine ADR-0006 for the arena: the golden run on thread pools with 1, 2 and N
/// threads must reproduce every checkpoint of the sequential run.
#[test]
fn golden_arena_run_with_1_2_and_n_threads() {
    let sequential = run_arena(GOLDEN_SEED, GOLDEN_TICKS, &mut arena_bot_input);
    for (label, executor) in gate_executors() {
        let threads = executor.threads();
        let report = run_arena_with_executor(GOLDEN_SEED, GOLDEN_TICKS, executor);
        assert_eq!(
            report.hashes, sequential.hashes,
            "checkpoints with {threads} threads ({label}) differ from the sequential run"
        );
    }
}
