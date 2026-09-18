//! Command line of the simulation harness (Plan 0002 WP7.4).
//!
//! Runs the game's own scenes headless and prints what happened, as a line per scene or as the
//! report document. Exit codes follow the engine's tools (`sigilc`, `grimoire-ac`): `0` everything
//! held, `1` the run found a problem, `2` the command could not run as asked.

use std::path::{Path, PathBuf};
use std::process::ExitCode;

use fnp_sim_harness::golden::{MASTER_DIR, RENEWAL_LOG, check_scene, input_log, renew};
use fnp_sim_harness::report::HarnessReport;
use fnp_sim_harness::scene::{STANDARD_SUITE, Scene, scene};
use fnp_sim_harness::{run_scene, run_standard_suite};

/// Usage text.
const USAGE: &str = "\
fnp-sim-harness - headless scene runs of Fiends n Patrons (Plan 0002 WP7.4)

Usage:
  fnp-sim-harness list
  fnp-sim-harness run <scene> [--seed <n>] [--ticks <n>] [--json]
  fnp-sim-harness suite [--json]
  fnp-sim-harness golden check [--scene <name>] [--dir <path>] [--out <path>]
  fnp-sim-harness golden renew --reason <text> [--scene <name>] [--dir <path>]
  fnp-sim-harness --help

Options:
  --seed <n>   Run the scene with another seed than the one it defines.
  --ticks <n>  Run for another number of ticks (1 to 360000).
  --json       Print the report document instead of one summary line.
  --scene <n>  Only this scene instead of the whole suite.
  --dir <p>    Master directory (default tests/golden/scenes).
  --out <p>    Where `golden check` writes diff report, run report and replay of a mismatch.
  --reason <t> Why the masters are renewed; it is logged and belongs in the commit message.

Exit codes: 0 every invariant held, 1 an invariant broke, 2 the command could not run.";

fn main() -> ExitCode {
    let arguments: Vec<String> = std::env::args().skip(1).collect();
    match run(&arguments) {
        Ok(code) => code,
        Err(message) => {
            eprintln!("fnp-sim-harness: {message}");
            eprintln!("Run `fnp-sim-harness --help` for usage.");
            ExitCode::from(2)
        }
    }
}

/// Runs one command; `Err` is a usage error.
fn run(arguments: &[String]) -> Result<ExitCode, String> {
    let Some(command) = arguments.first() else {
        println!("{USAGE}");
        return Ok(ExitCode::from(2));
    };
    match command.as_str() {
        "--help" | "-h" | "help" => {
            println!("{USAGE}");
            Ok(ExitCode::SUCCESS)
        }
        "list" => {
            reject_extra(&arguments[1..])?;
            for scene in STANDARD_SUITE {
                let patterns: Vec<&str> = scene
                    .patterns
                    .iter()
                    .map(|pattern| pattern.name())
                    .collect();
                println!(
                    "{:<16} seed {:<3} {:>5} ticks  bot {:<7} {}",
                    scene.name,
                    scene.seed,
                    scene.ticks,
                    scene.bot.name(),
                    patterns.join(", ")
                );
            }
            Ok(ExitCode::SUCCESS)
        }
        "run" => {
            let (name, options) = arguments[1..]
                .split_first()
                .ok_or_else(|| String::from("`run` needs a scene name"))?;
            let mut chosen: Scene = *scene(name)
                .ok_or_else(|| format!("unknown scene `{name}`; `list` names them all"))?;
            let mut json = false;
            let mut index = 0;
            while index < options.len() {
                match options[index].as_str() {
                    "--json" => json = true,
                    "--seed" => {
                        chosen.seed = number(options.get(index + 1), "--seed", 0, u64::MAX)?;
                        index += 1;
                    }
                    "--ticks" => {
                        chosen.ticks = number(options.get(index + 1), "--ticks", 1, 360_000)?;
                        index += 1;
                    }
                    other => return Err(format!("unknown option `{other}`")),
                }
                index += 1;
            }
            Ok(print(&[run_scene(&chosen)], json))
        }
        "golden" => golden(&arguments[1..]),
        "suite" => {
            let json = match &arguments[1..] {
                [] => false,
                [only] if only == "--json" => true,
                [other, ..] => return Err(format!("unknown option `{other}`")),
            };
            Ok(print(&run_standard_suite(), json))
        }
        other => Err(format!("unknown command `{other}`")),
    }
}

/// `golden check` and `golden renew`.
fn golden(arguments: &[String]) -> Result<ExitCode, String> {
    let (command, options) = arguments
        .split_first()
        .ok_or_else(|| String::from("`golden` needs `check` or `renew`"))?;
    let mut directory = PathBuf::from(MASTER_DIR);
    let mut out: Option<PathBuf> = None;
    let mut reason: Option<String> = None;
    let mut only: Option<String> = None;
    let mut index = 0;
    while index < options.len() {
        let value = || -> Result<String, String> {
            options
                .get(index + 1)
                .cloned()
                .ok_or_else(|| format!("{} needs a value", options[index]))
        };
        match options[index].as_str() {
            "--dir" => directory = PathBuf::from(value()?),
            "--out" => out = Some(PathBuf::from(value()?)),
            "--reason" => reason = Some(value()?),
            "--scene" => only = Some(value()?),
            other => return Err(format!("unknown option `{other}`")),
        }
        index += 2;
    }
    let scenes: Vec<Scene> = match &only {
        None => STANDARD_SUITE.to_vec(),
        Some(name) => vec![
            *scene(name).ok_or_else(|| format!("unknown scene `{name}`; `list` names them all"))?,
        ],
    };

    match command.as_str() {
        "check" => {
            let mut broken = 0;
            for scene in &scenes {
                let (diff, report) = check_scene(scene, &directory)?;
                print!("{}", diff.to_text());
                if diff.matches() {
                    continue;
                }
                broken += 1;
                if let Some(out) = &out {
                    write_artefacts(out, scene, &diff.to_text(), &report)?;
                }
            }
            if broken == 0 {
                return Ok(ExitCode::SUCCESS);
            }
            eprintln!(
                "fnp-sim-harness: {broken} scene(s) no longer match their master. Renewing is a \
                 decision, not a repair: see CONTRIBUTING, \"Golden-Master und Referenzwerte\"."
            );
            Ok(ExitCode::from(1))
        }
        "renew" => {
            let reason = reason.ok_or_else(|| {
                String::from("`golden renew` needs `--reason <text>`; it is logged and belongs in the commit message")
            })?;
            if reason.trim().is_empty() {
                return Err(String::from("`--reason` must say something"));
            }
            let log = PathBuf::from(RENEWAL_LOG);
            for line in renew(&scenes, &directory, &log, &reason)? {
                println!("{line}");
            }
            println!(
                "Renewed {} master(s) in {} and logged the reason in {}.",
                scenes.len(),
                directory.display(),
                log.display()
            );
            println!("Commit this on its own, with the reason in the message.");
            Ok(ExitCode::SUCCESS)
        }
        other => Err(format!("unknown `golden` command `{other}`")),
    }
}

/// Writes what a mismatch needs to be understood elsewhere: the diff, the run and the replay.
fn write_artefacts(
    out: &Path,
    scene: &Scene,
    diff: &str,
    report: &HarnessReport,
) -> Result<(), String> {
    std::fs::create_dir_all(out).map_err(|error| format!("{}: {error}", out.display()))?;
    let write = |name: &str, bytes: &[u8]| -> Result<(), String> {
        let path = out.join(name);
        std::fs::write(&path, bytes).map_err(|error| format!("{}: {error}", path.display()))
    };
    write(&format!("{}.diff.txt", scene.name), diff.as_bytes())?;
    write(
        &format!("{}.report.json", scene.name),
        report.to_json().as_bytes(),
    )?;
    // The scene is a pure function of seed and tick, so its input log replays the run anywhere.
    write(
        &format!("{}.replay", scene.name),
        &input_log(scene).to_bytes(),
    )?;
    println!("  artefacts: {}", out.display());
    Ok(())
}

/// Prints the reports and turns them into an exit code.
fn print(reports: &[HarnessReport], json: bool) -> ExitCode {
    for report in reports {
        if json {
            print!("{}", report.to_json());
        } else {
            println!("{}", report.summary());
        }
    }
    let broken: Vec<&HarnessReport> = reports.iter().filter(|report| !report.ok()).collect();
    if broken.is_empty() {
        return ExitCode::SUCCESS;
    }
    for report in broken {
        for invariant in report.violations() {
            eprintln!(
                "fnp-sim-harness: {} broke `{}`: {}",
                report.scene, invariant.name, invariant.detail
            );
        }
    }
    ExitCode::from(1)
}

/// Parses a numeric option value.
fn number(value: Option<&String>, name: &str, min: u64, max: u64) -> Result<u64, String> {
    let text = value.ok_or_else(|| format!("{name} needs a value"))?;
    let parsed: u64 = text
        .parse()
        .map_err(|_| format!("{name}: `{text}` is not a number"))?;
    if parsed < min || parsed > max {
        return Err(format!("{name}: `{text}` is outside {min} to {max}"));
    }
    Ok(parsed)
}

/// Rejects arguments a command does not take.
fn reject_extra(arguments: &[String]) -> Result<(), String> {
    match arguments.first() {
        None => Ok(()),
        Some(extra) => Err(format!("this command takes no `{extra}`")),
    }
}
