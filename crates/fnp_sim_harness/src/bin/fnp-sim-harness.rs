//! Command line of the simulation harness (Plan 0002 WP7.4).
//!
//! Runs the game's own scenes headless and prints what happened, as a line per scene or as the
//! report document. Exit codes follow the engine's tools (`sigilc`, `grimoire-ac`): `0` everything
//! held, `1` the run found a problem, `2` the command could not run as asked.

use std::process::ExitCode;

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
  fnp-sim-harness --help

Options:
  --seed <n>   Run the scene with another seed than the one it defines.
  --ticks <n>  Run for another number of ticks (1 to 360000).
  --json       Print the report document instead of one summary line.

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
