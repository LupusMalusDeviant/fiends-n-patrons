//! The harness command line (Plan 0002 WP7.4): the commands it answers and the exit codes it
//! ends with, checked against the built binary itself.

use std::process::{Command, Output};

/// Runs the harness binary with `arguments`.
fn harness(arguments: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_fnp-sim-harness"))
        .args(arguments)
        .output()
        .expect("the harness binary runs")
}

fn stdout(output: &Output) -> String {
    String::from_utf8(output.stdout.clone()).expect("the harness writes UTF-8")
}

#[test]
fn list_names_every_scene_of_the_suite() {
    let output = harness(&["list"]);
    assert!(output.status.success());
    let text = stdout(&output);
    for scene in fnp_sim_harness::scene::STANDARD_SUITE {
        assert!(text.contains(scene.name), "`list` misses {}", scene.name);
    }
}

#[test]
fn help_succeeds_and_no_arguments_prints_the_usage() {
    let help = harness(&["--help"]);
    assert!(help.status.success());
    assert!(stdout(&help).contains("fnp-sim-harness run <scene>"));

    let empty = harness(&[]);
    assert_eq!(empty.status.code(), Some(2));
    assert!(stdout(&empty).contains("Usage:"));
}

#[test]
fn a_scene_runs_and_can_be_shortened_and_reseeded() {
    let output = harness(&["run", "swarm_weave", "--ticks", "120", "--seed", "3"]);
    assert!(output.status.success(), "{}", stdout(&output));
    let text = stdout(&output);
    assert!(text.contains("swarm_weave"));
    assert!(text.contains("seed 3"));
    assert!(text.contains("  ok"));
}

#[test]
fn the_json_document_comes_out_whole() {
    let output = harness(&["run", "summoner_bloom", "--ticks", "180", "--json"]);
    assert!(output.status.success());
    let text = stdout(&output);
    assert!(text.starts_with("{\n  \"schema\": \"grimoire.fnp.harness\""));
    assert!(text.trim_end().ends_with('}'));
    assert!(text.contains("\"invariants\""));
    assert!(text.contains("\"checkpoints\""));
    assert!(text.contains("\"events\""));
}

#[test]
fn every_usage_error_ends_with_exit_code_two() {
    for arguments in [
        vec!["nonsense"],
        vec!["run"],
        vec!["run", "no_such_scene"],
        vec!["run", "swarm_weave", "--nonsense"],
        vec!["run", "swarm_weave", "--ticks"],
        vec!["run", "swarm_weave", "--ticks", "many"],
        vec!["run", "swarm_weave", "--ticks", "0"],
        vec!["list", "extra"],
        vec!["suite", "--nonsense"],
    ] {
        let output = harness(&arguments);
        assert_eq!(
            output.status.code(),
            Some(2),
            "`{}` should be a usage error",
            arguments.join(" ")
        );
    }
}

/// The masters, as an absolute path: a test runs with the crate directory as its working
/// directory, the command line's default expects the repository root.
fn master_directory() -> String {
    std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join(fnp_sim_harness::golden::MASTER_DIR)
        .to_string_lossy()
        .into_owned()
}

#[test]
fn golden_check_reports_that_every_scene_matches() {
    let directory = master_directory();
    let output = harness(&[
        "golden",
        "check",
        "--scene",
        "summoner_bloom",
        "--dir",
        &directory,
    ]);
    assert!(output.status.success(), "{}", stdout(&output));
    assert!(stdout(&output).contains("summoner_bloom: matches its master"));
}

#[test]
fn golden_refuses_a_renewal_without_a_reason_and_an_unknown_master_directory() {
    let without_reason = harness(&["golden", "renew"]);
    assert_eq!(without_reason.status.code(), Some(2));

    let empty_reason = harness(&["golden", "renew", "--reason", "  "]);
    assert_eq!(empty_reason.status.code(), Some(2));

    // A missing master is a usage error, never a silently passing check.
    let missing = harness(&[
        "golden",
        "check",
        "--scene",
        "imp_arena",
        "--dir",
        "no/such/directory",
    ]);
    assert_eq!(missing.status.code(), Some(2));

    for arguments in [
        vec!["golden"],
        vec!["golden", "nonsense"],
        vec!["golden", "check", "--nonsense"],
        vec!["golden", "check", "--scene"],
        vec!["golden", "check", "--scene", "no_such_scene"],
    ] {
        assert_eq!(
            harness(&arguments).status.code(),
            Some(2),
            "`{}` should be a usage error",
            arguments.join(" ")
        );
    }
}

#[test]
fn the_suite_runs_from_the_command_line() {
    let output = harness(&["suite"]);
    assert!(output.status.success());
    let text = stdout(&output);
    assert_eq!(
        text.lines().count(),
        fnp_sim_harness::scene::STANDARD_SUITE.len()
    );
    assert!(text.lines().all(|line| line.ends_with("ok")));
}
