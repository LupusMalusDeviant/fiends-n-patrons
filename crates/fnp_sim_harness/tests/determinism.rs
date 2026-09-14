//! Determinism gate of the game (PRD-0018 FR-04a): identical runs, seed sensitivity and a golden
//! final hash, all through the facade's headless path.

use fnp_sim_harness::{HASH_EVERY, run_seed, run_with_input};
use grimoire::prelude::*;

/// Seed of the golden run.
const GOLDEN_SEED: u64 = 42;

/// Length of the golden run: one minute of simulation at 60 Hz.
const GOLDEN_TICKS: u64 = 3_600;

/// Final state hash of `run_seed(GOLDEN_SEED, GOLDEN_TICKS)`.
///
/// This is a frozen expectation (golden master). CI confirms the same value on Windows, Linux and
/// macOS; a mismatch on a single platform is a determinism bug, never a reason to change it.
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

#[test]
fn different_seeds_give_different_final_hashes() {
    let finals: Vec<u64> = [1, 2, GOLDEN_SEED, u64::MAX]
        .into_iter()
        .map(|seed| run_seed(seed, 600).final_hash)
        .collect();
    for (index, hash) in finals.iter().enumerate() {
        assert!(
            !finals[index + 1..].contains(hash),
            "two seeds share the final hash {hash:#018x}: {finals:x?}"
        );
    }
}

#[test]
fn different_seeds_already_differ_after_spawning() {
    assert_ne!(run_seed(1, 0).final_hash, run_seed(2, 0).final_hash);
}

#[test]
fn bot_input_changes_the_outcome() {
    let bot = run_seed(GOLDEN_SEED, 600);
    let idle = run_with_input(GOLDEN_SEED, 600, &mut |_| TickInput::default());
    assert_ne!(bot.final_hash, idle.final_hash);
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
