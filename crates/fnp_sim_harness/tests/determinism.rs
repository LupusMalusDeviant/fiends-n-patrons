//! Determinism gate of the game (PRD-0018 FR-04a): identical runs, input sensitivity,
//! thread-count independence (engine ADR-0006, building block 7) and a golden final hash, over the
//! arena scenario, in which the Sigil interpreter fires, the broadphase finds hits and rounds
//! restart, and over the curtain scenario, whose ten thousand bullets run the interpreter and the
//! broadphase over many data-parallel pool blocks. CI runs it in the dev profile on three operating systems; the nightly and release
//! workflows repeat it in the release profile (`--test determinism`).

use fnp_game::arena::{ArenaMode, Mode, Phase, RoundState};
use fnp_game::{Player, Position};
use fnp_sim_harness::{
    CURTAIN_PRESS_TICK, HASH_EVERY, arena_bot_input, curtain_bot_input, run_arena,
    run_arena_with_executor, simulate_arena,
};
use grimoire::prelude::*;
use grimoire::sigil::{BulletPool, POOL_BLOCK_SIZE};
use grimoire_exec::gate_executors;

/// Seed of the golden arena run.
const GOLDEN_SEED: u64 = 42;

/// Length of the golden arena run: one minute at 60 Hz.
const GOLDEN_TICKS: u64 = 3_600;

/// Final state hash of `run_arena(GOLDEN_SEED, GOLDEN_TICKS, arena_bot_input)`.
///
/// A frozen expectation (golden master), captured locally on Windows (debug and release profile)
/// and confirmed by CI on Windows, Linux and macOS in the debug profile. History: `0xc17457a2f7e6fb49`
/// (first prototype), `0x9001d4a1d2f7125e` (imp palettes renamed to the bullet pass tables, content
/// identity only, confirmed by the PO on 2026-09-17), the current value after the imp's patterns
/// were rebuilt from the engine's reference patterns and the curtain unit joined the library.
///
/// A mismatch on a single platform is a determinism bug and never a reason to change the value.
/// Renew it only deliberately, following CONTRIBUTING.md ("Golden-Master und Referenzwerte"):
/// name the cause first, renew in a separate `test(golden)` commit stating old and new value and
/// the first diverging checkpoint. Agents do not renew golden masters on their own; the PO decides.
const GOLDEN_ARENA_FINAL_HASH: u64 = 0x59e2_9cde_b01f_1f8a;

/// Length of the golden curtain run: 20 seconds at 60 Hz, long enough for the curtain to fill.
const GOLDEN_CURTAIN_TICKS: u64 = 1_200;

/// Final state hash of `run_arena(GOLDEN_SEED, GOLDEN_CURTAIN_TICKS, curtain_bot_input)`.
///
/// A frozen expectation like [`GOLDEN_ARENA_FINAL_HASH`], captured locally on Windows (debug and
/// release profile) when the curtain mode was added, under the same renewal rules.
const GOLDEN_CURTAIN_FINAL_HASH: u64 = 0x3c90_8792_967c_5f7d;

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

        let idle_sim = simulate_arena(GOLDEN_SEED, ticks, &mut |_| TickInput::default());
        let idle_report = run_arena(GOLDEN_SEED, ticks, &mut |_| TickInput::default());
        assert_eq!(idle_sim.state_hash(), idle_report.final_hash);
    }
}

#[test]
fn the_seed_reaches_the_state_hash() {
    // The arena draws no randomness of its own yet, so different seeds play the same; the seed
    // must still be part of every state hash, so replays and golden masters name their seed.
    let first = run_arena(1, 120, &mut arena_bot_input);
    let second = run_arena(2, 120, &mut arena_bot_input);
    assert_eq!(first.final_tick, second.final_tick);
    assert_ne!(first.final_hash, second.final_hash);
    assert_eq!(first, run_arena(1, 120, &mut arena_bot_input));
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
        let report =
            run_arena_with_executor(GOLDEN_SEED, GOLDEN_TICKS, executor, &mut arena_bot_input);
        assert_eq!(
            report.hashes, sequential.hashes,
            "checkpoints with {threads} threads ({label}) differ from the sequential run"
        );
    }
}

fn checkpoint_list(hashes: &[(u64, u64)]) -> String {
    hashes
        .iter()
        .map(|(tick, hash)| format!("  tick {tick:>5}: {hash:#018x}"))
        .collect::<Vec<_>>()
        .join("\n")
}

#[test]
fn the_curtain_scenario_holds_about_ten_thousand_bullets_over_many_pool_blocks() {
    let mut sim = simulate_arena(GOLDEN_SEED, 0, &mut curtain_bot_input);
    for _ in 0..GOLDEN_CURTAIN_TICKS {
        sim.step(curtain_bot_input(sim.tick()));
    }
    let mode = *sim.world().resource::<ArenaMode>().expect("arena mode");
    assert_eq!(mode.mode, Mode::Curtain);
    let pool = sim.world().resource::<BulletPool>().expect("pool");
    let live = pool.len() as usize;
    assert!((9_000..=12_000).contains(&live), "{live} live bullets");
    assert!(
        pool.slot_count() as usize > 8 * POOL_BLOCK_SIZE,
        "the pool update runs over more than eight blocks"
    );
    assert_eq!(pool.dropped_spawns(), 0);
    assert_eq!(
        round(&sim).hits,
        0,
        "the soul cannot be hit in curtain mode"
    );
    assert!(CURTAIN_PRESS_TICK < GOLDEN_CURTAIN_TICKS);
    println!("curtain bot scenario: {live} live bullets after {GOLDEN_CURTAIN_TICKS} ticks");
}

#[test]
fn golden_curtain_final_hash_for_seed_42() {
    let report = run_arena(GOLDEN_SEED, GOLDEN_CURTAIN_TICKS, &mut curtain_bot_input);
    assert_eq!(report.final_tick, GOLDEN_CURTAIN_TICKS);
    assert_eq!(
        report.final_hash,
        GOLDEN_CURTAIN_FINAL_HASH,
        "golden curtain hash changed: expected {GOLDEN_CURTAIN_FINAL_HASH:#018x}, got {:#018x}.\n\
         Checkpoints for comparison with a platform that passes:\n{}",
        report.final_hash,
        checkpoint_list(&report.hashes)
    );
}

/// Hash gate of engine ADR-0006 for the curtain: ten thousand bullets in many pool blocks on
/// thread pools with 1, 2 and N threads must reproduce every checkpoint of the sequential run.
#[test]
fn golden_curtain_run_with_1_2_and_n_threads() {
    let sequential = run_arena(GOLDEN_SEED, GOLDEN_CURTAIN_TICKS, &mut curtain_bot_input);
    for (label, executor) in gate_executors() {
        let threads = executor.threads();
        let report = run_arena_with_executor(
            GOLDEN_SEED,
            GOLDEN_CURTAIN_TICKS,
            executor,
            &mut curtain_bot_input,
        );
        assert_eq!(
            report.hashes, sequential.hashes,
            "curtain checkpoints with {threads} threads ({label}) differ from the sequential run"
        );
    }
}
