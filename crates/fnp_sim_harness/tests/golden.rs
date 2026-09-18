//! The golden masters of the scenes (Plan 0002 WP7.5, PRD-0018 FR-05).
//!
//! This is the gate: every scene of the standard suite must still behave exactly as its master
//! says, on every platform. It runs in the ordinary test job, so a push is checked on Windows,
//! Linux and macOS at once; the nightly repeats it through the command line and keeps the
//! artefacts.
//!
//! A failure here is never fixed by renewing the master. The message names the first diverging
//! checkpoint, the window it began in, what else changed and what the per-system narrowing found;
//! CONTRIBUTING says what to do with that.

use std::path::{Path, PathBuf};

use fnp_sim_harness::golden::{MASTER_DIR, Master, check_scene, compare};
use fnp_sim_harness::run_scene;
use fnp_sim_harness::scene::STANDARD_SUITE;

/// The repository root, from this crate's manifest directory.
fn repository_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .canonicalize()
        .expect("the repository root exists")
}

fn masters() -> PathBuf {
    repository_root().join(MASTER_DIR)
}

#[test]
fn every_scene_still_matches_its_master() {
    let directory = masters();
    let mut broken = Vec::new();
    for scene in STANDARD_SUITE {
        let (diff, _) = check_scene(scene, &directory).expect("the master reads");
        if !diff.matches() {
            broken.push(diff.to_text());
        }
    }
    assert!(
        broken.is_empty(),
        "golden masters no longer match. Renewing is a decision, not a repair \
         (CONTRIBUTING, \"Golden-Master und Referenzwerte\"):\n\n{}",
        broken.join("\n")
    );
}

#[test]
fn every_scene_of_the_suite_has_a_master_and_nothing_else_does() {
    let directory = masters();
    let mut files: Vec<String> = std::fs::read_dir(&directory)
        .expect("the master directory exists")
        .map(|entry| {
            entry
                .expect("a directory entry")
                .file_name()
                .to_string_lossy()
                .into_owned()
        })
        .collect();
    files.sort();
    let mut expected: Vec<String> = STANDARD_SUITE
        .iter()
        .map(|scene| format!("{}.json", scene.name))
        .collect();
    expected.sort();
    assert_eq!(files, expected);
}

#[test]
fn a_master_says_what_it_froze() {
    // The master pins scene behaviour, not the numbers a pattern shows in isolation: the round
    // restarts are written down, and the despawn causes show that the clear does most of the work.
    let text = std::fs::read_to_string(masters().join("imp_curtain.json")).expect("the master");
    let master = Master::parse(&text).expect("it parses");
    assert_eq!(master.scene, "imp_curtain");
    assert_eq!(master.bot, "idle");
    assert!(master.hits > 0, "the curtain scene takes hits");
    assert_eq!(master.round_starts.len() as u32, master.rounds - 1);
    let cleared = master.despawns.get("clear").copied().unwrap_or(0);
    let bounds = master.despawns.get("bounds").copied().unwrap_or(0);
    assert!(
        cleared > bounds * 10,
        "the clear does the despawning in a scene: {cleared} cleared, {bounds} through the bounds"
    );
}

#[test]
fn a_changed_run_is_reported_with_its_window_and_its_narrowing() {
    // Simulates what a real regression looks like, without breaking a checked-in master.
    let scene = &STANDARD_SUITE[2];
    let report = run_scene(scene);
    let mut master = Master::from_report(&report);
    master.checkpoints[2].1 ^= 0xff;
    let diff = compare(&master, &report);
    assert!(!diff.matches());
    let (tick, _, _) = diff.first_diverging_checkpoint.expect("a divergence");
    assert_eq!(tick, master.checkpoints[2].0);
    assert_eq!(diff.window, Some((master.checkpoints[1].0, tick)));
    let text = diff.to_text();
    assert!(text.contains("does NOT match its master"));
    assert!(text.contains("first diverging checkpoint"));
}
