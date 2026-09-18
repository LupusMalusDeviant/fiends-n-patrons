//! Golden masters of the scenes (Plan 0002 WP7.5, PRD-0018 FR-05).
//!
//! A master is the frozen behaviour of one scene: the state hash every sixty ticks, the final
//! hash, and the handful of counted facts that say what happened — peak bullets, despawns by
//! cause, hits, and the tick every round started on. It pins the *scene*, not a pattern in
//! isolation: in a real run the clear does most of the despawning and every hit restarts the
//! round, so those restarts are written down explicitly instead of showing up as noise in a hash.
//!
//! Renewal is a decision, never a repair: [`renew`] rewrites the files and appends the reason to
//! `RENEWALS.md`, and CONTRIBUTING requires that to be its own commit.
//!
//! When a master no longer matches, [`compare`] says which checkpoint diverged first and what else
//! changed, and [`narrow`] follows engine ADR-0018: detect every sixty ticks, then narrow inside
//! that one window with a per-system trace — the reference is rebuilt by re-running, never stored
//! in the master.

use std::collections::BTreeMap;
use std::fmt::Write as _;
use std::path::{Path, PathBuf};
use std::sync::Arc;

use fnp_game::arena::ArenaGame;
use grimoire::prelude::*;
use grimoire::sim::{HashTrace, InputLog, TraceGranularity, first_divergence, trace};
use grimoire_exec::ThreadPoolExecutor;

use crate::report::HarnessReport;
use crate::scene::Scene;
use crate::{HASH_EVERY, run_scene};

/// Schema name of a master file.
pub const SCHEMA: &str = "grimoire.fnp.golden";

/// Schema version of a master file.
pub const SCHEMA_VERSION: u32 = 1;

/// Where the masters live, relative to the repository root.
pub const MASTER_DIR: &str = "tests/golden/scenes";

/// Where renewals are logged, relative to the repository root.
pub const RENEWAL_LOG: &str = "tests/golden/RENEWALS.md";

/// The frozen behaviour of one scene.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Master {
    /// Scene name.
    pub scene: String,
    /// Scene seed.
    pub seed: u64,
    /// Ticks the scene runs.
    pub ticks: u64,
    /// Patterns it plays.
    pub patterns: Vec<String>,
    /// Bot profile.
    pub bot: String,
    /// Engine version the master was taken with.
    pub engine_version: String,
    /// State hash after the last tick.
    pub final_state_hash: u64,
    /// `(tick, state hash)` every [`HASH_EVERY`] ticks and after the last tick.
    pub checkpoints: Vec<(u64, u64)>,
    /// Most live bullets after any tick.
    pub peak_bullets: u32,
    /// Live bullets after the last tick.
    pub final_bullets: u32,
    /// Despawns by cause name.
    pub despawns: BTreeMap<String, u64>,
    /// Spawns the pool refused.
    pub dropped_spawns: u64,
    /// Hits the player proxy took.
    pub hits: u32,
    /// Rounds reached.
    pub rounds: u32,
    /// Tick each round after the first started on: the restarts, spelled out.
    pub round_starts: Vec<u64>,
}

impl Master {
    /// The master of a finished run.
    #[must_use]
    pub fn from_report(report: &HarnessReport) -> Self {
        Self {
            scene: report.scene.clone(),
            seed: report.seed,
            ticks: report.ticks,
            patterns: report
                .patterns
                .iter()
                .map(|name| (*name).to_owned())
                .collect(),
            bot: report.bot.to_owned(),
            engine_version: report.engine_version.to_owned(),
            final_state_hash: report.final_state_hash,
            checkpoints: report
                .checkpoints
                .iter()
                .map(|checkpoint| (checkpoint.tick, checkpoint.state_hash))
                .collect(),
            peak_bullets: report.metrics.peak_bullets,
            final_bullets: report.metrics.final_bullets,
            despawns: report
                .metrics
                .despawns
                .iter()
                .map(|(cause, count)| ((*cause).to_owned(), *count))
                .collect(),
            dropped_spawns: report.metrics.dropped_spawns,
            hits: report.metrics.hits,
            rounds: report.metrics.rounds,
            round_starts: report
                .events
                .iter()
                .filter(|event| event.kind == "round")
                .map(|event| event.tick)
                .collect(),
        }
    }

    /// The master file's path below `directory`.
    #[must_use]
    pub fn path_in(directory: &Path, scene: &str) -> PathBuf {
        directory.join(format!("{scene}.json"))
    }

    /// The master as its file: fixed key order, hashes as sixteen hex digits, no clock.
    #[must_use]
    pub fn to_json(&self) -> String {
        let mut out = String::with_capacity(512);
        let _ = writeln!(out, "{{");
        let _ = writeln!(out, "  \"schema\": \"{SCHEMA}\",");
        let _ = writeln!(out, "  \"schema_version\": {SCHEMA_VERSION},");
        let _ = writeln!(out, "  \"scene\": \"{}\",", self.scene);
        let _ = writeln!(out, "  \"seed\": {},", self.seed);
        let _ = writeln!(out, "  \"ticks\": {},", self.ticks);
        let _ = writeln!(out, "  \"bot\": \"{}\",", self.bot);
        let _ = writeln!(out, "  \"engine_version\": \"{}\",", self.engine_version);
        let patterns: Vec<String> = self
            .patterns
            .iter()
            .map(|name| format!("\"{name}\""))
            .collect();
        let _ = writeln!(out, "  \"patterns\": [{}],", patterns.join(", "));
        let _ = writeln!(
            out,
            "  \"final_state_hash\": \"{:016x}\",",
            self.final_state_hash
        );
        let _ = writeln!(out, "  \"peak_bullets\": {},", self.peak_bullets);
        let _ = writeln!(out, "  \"final_bullets\": {},", self.final_bullets);
        let despawns: Vec<String> = self
            .despawns
            .iter()
            .map(|(cause, count)| format!("\"{cause}\": {count}"))
            .collect();
        let _ = writeln!(out, "  \"despawns\": {{{}}},", despawns.join(", "));
        let _ = writeln!(out, "  \"dropped_spawns\": {},", self.dropped_spawns);
        let _ = writeln!(out, "  \"hits\": {},", self.hits);
        let _ = writeln!(out, "  \"rounds\": {},", self.rounds);
        let starts: Vec<String> = self.round_starts.iter().map(u64::to_string).collect();
        let _ = writeln!(out, "  \"round_starts\": [{}],", starts.join(", "));
        let _ = writeln!(out, "  \"checkpoints\": [");
        let checkpoints: Vec<String> = self
            .checkpoints
            .iter()
            .map(|(tick, hash)| {
                format!("    {{ \"tick\": {tick}, \"state_hash\": \"{hash:016x}\" }}")
            })
            .collect();
        out.push_str(&checkpoints.join(",\n"));
        let _ = writeln!(out, "\n  ]");
        let _ = writeln!(out, "}}");
        out
    }

    /// Reads a master file.
    ///
    /// The format is the one [`Master::to_json`] writes: one value per line, so this reader needs
    /// no JSON dependency and still refuses anything it does not recognise.
    ///
    /// # Errors
    /// A message naming what is missing or malformed.
    pub fn parse(text: &str) -> Result<Self, String> {
        let schema = string_field(text, "schema")?;
        if schema != SCHEMA {
            return Err(format!("schema is `{schema}`, not `{SCHEMA}`"));
        }
        if number_field(text, "schema_version")? != u64::from(SCHEMA_VERSION) {
            return Err(String::from("unknown schema_version"));
        }
        let mut checkpoints = Vec::new();
        for line in text.lines() {
            let line = line.trim();
            if !line.starts_with("{ \"tick\"") {
                continue;
            }
            let tick = number_field(line, "tick")?;
            let hash = u64::from_str_radix(&string_field(line, "state_hash")?, 16)
                .map_err(|_| String::from("a checkpoint hash is not hex"))?;
            checkpoints.push((tick, hash));
        }
        Ok(Self {
            scene: string_field(text, "scene")?,
            seed: number_field(text, "seed")?,
            ticks: number_field(text, "ticks")?,
            patterns: list_field(text, "patterns"),
            bot: string_field(text, "bot")?,
            engine_version: string_field(text, "engine_version")?,
            final_state_hash: u64::from_str_radix(&string_field(text, "final_state_hash")?, 16)
                .map_err(|_| String::from("final_state_hash is not hex"))?,
            checkpoints,
            peak_bullets: u32::try_from(number_field(text, "peak_bullets")?)
                .map_err(|_| String::from("peak_bullets is out of range"))?,
            final_bullets: u32::try_from(number_field(text, "final_bullets")?)
                .map_err(|_| String::from("final_bullets is out of range"))?,
            despawns: despawn_field(text),
            dropped_spawns: number_field(text, "dropped_spawns")?,
            hits: u32::try_from(number_field(text, "hits")?)
                .map_err(|_| String::from("hits is out of range"))?,
            rounds: u32::try_from(number_field(text, "rounds")?)
                .map_err(|_| String::from("rounds is out of range"))?,
            round_starts: number_list_field(text, "round_starts"),
        })
    }
}

/// One thing that changed between a master and a run.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Difference {
    /// What changed, e.g. `final_state_hash` or `hits`.
    pub field: String,
    /// The master's value.
    pub master: String,
    /// The run's value.
    pub run: String,
}

/// What `golden check` found for one scene.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DiffReport {
    /// Scene name.
    pub scene: String,
    /// First checkpoint whose hash differs, as `(tick, master hash, run hash)`.
    pub first_diverging_checkpoint: Option<(u64, u64, u64)>,
    /// The window the divergence began in: the last matching checkpoint and the diverging one.
    pub window: Option<(u64, u64)>,
    /// Everything else that differs.
    pub differences: Vec<Difference>,
    /// What the per-system narrowing found, once it ran.
    pub narrowing: Option<String>,
}

impl DiffReport {
    /// Whether the run matches the master.
    #[must_use]
    pub fn matches(&self) -> bool {
        self.first_diverging_checkpoint.is_none() && self.differences.is_empty()
    }

    /// The report as text, for a log and for a human.
    #[must_use]
    pub fn to_text(&self) -> String {
        if self.matches() {
            return format!("{}: matches its master\n", self.scene);
        }
        let mut out = format!("{}: does NOT match its master\n", self.scene);
        if let Some((tick, master, run)) = self.first_diverging_checkpoint {
            let _ = writeln!(
                out,
                "  first diverging checkpoint: tick {tick}, master {master:016x}, run {run:016x}"
            );
        }
        if let Some((from, to)) = self.window {
            let _ = writeln!(
                out,
                "  the change begins in ticks {from}..={to} (the {HASH_EVERY}-tick window before it)"
            );
        }
        for difference in &self.differences {
            let _ = writeln!(
                out,
                "  {}: master {}, run {}",
                difference.field, difference.master, difference.run
            );
        }
        if let Some(narrowing) = &self.narrowing {
            let _ = writeln!(out, "  narrowing: {narrowing}");
        }
        out
    }
}

/// Compares a run against its master (engine ADR-0018, stage one: detect).
#[must_use]
pub fn compare(master: &Master, report: &HarnessReport) -> DiffReport {
    let run = Master::from_report(report);
    let mut differences = Vec::new();
    let mut push = |field: &str, left: String, right: String| {
        if left != right {
            differences.push(Difference {
                field: field.to_owned(),
                master: left,
                run: right,
            });
        }
    };
    push("seed", master.seed.to_string(), run.seed.to_string());
    push("ticks", master.ticks.to_string(), run.ticks.to_string());
    push("bot", master.bot.clone(), run.bot.clone());
    push(
        "patterns",
        master.patterns.join(","),
        run.patterns.join(","),
    );
    push(
        "engine_version",
        master.engine_version.clone(),
        run.engine_version.clone(),
    );
    push(
        "final_state_hash",
        format!("{:016x}", master.final_state_hash),
        format!("{:016x}", run.final_state_hash),
    );
    push(
        "peak_bullets",
        master.peak_bullets.to_string(),
        run.peak_bullets.to_string(),
    );
    push(
        "final_bullets",
        master.final_bullets.to_string(),
        run.final_bullets.to_string(),
    );
    push("hits", master.hits.to_string(), run.hits.to_string());
    push("rounds", master.rounds.to_string(), run.rounds.to_string());
    push(
        "dropped_spawns",
        master.dropped_spawns.to_string(),
        run.dropped_spawns.to_string(),
    );
    push(
        "round_starts",
        format!("{:?}", master.round_starts),
        format!("{:?}", run.round_starts),
    );
    for cause in master.despawns.keys().chain(run.despawns.keys()) {
        let left = master.despawns.get(cause).copied().unwrap_or(0);
        let right = run.despawns.get(cause).copied().unwrap_or(0);
        if left != right {
            let difference = Difference {
                field: format!("despawns.{cause}"),
                master: left.to_string(),
                run: right.to_string(),
            };
            if !differences.contains(&difference) {
                differences.push(difference);
            }
        }
    }

    let mut first_diverging_checkpoint = None;
    let mut window = None;
    let mut last_matching = 0;
    for (index, (tick, hash)) in master.checkpoints.iter().enumerate() {
        match run.checkpoints.get(index) {
            Some((run_tick, run_hash)) if run_tick == tick && run_hash == hash => {
                last_matching = *tick;
            }
            Some((run_tick, run_hash)) => {
                first_diverging_checkpoint = Some((*tick.min(run_tick), *hash, *run_hash));
                window = Some((last_matching, *tick));
                break;
            }
            None => {
                differences.push(Difference {
                    field: String::from("checkpoints"),
                    master: format!("{} checkpoints", master.checkpoints.len()),
                    run: format!("{} checkpoints", run.checkpoints.len()),
                });
                break;
            }
        }
    }

    DiffReport {
        scene: master.scene.clone(),
        first_diverging_checkpoint,
        window,
        differences,
        narrowing: None,
    }
}

/// Narrows a divergence inside one window (engine ADR-0018, stage two).
///
/// The reference is rebuilt by running the scene again, never read from the master: the master
/// deliberately holds no system hashes. Both runs are the same scene, so what can still differ is
/// the execution — this runs one of them single-threaded and one on a thread pool and reports the
/// first system whose world hash differs, with its subsystem. When they agree, that is the answer
/// too: the change is in the content or in the code, not in the threading.
#[must_use]
pub fn narrow(scene: &Scene, window: (u64, u64)) -> String {
    let (from, to) = window;
    let single = trace_window(scene, from, to, None);
    let pooled = trace_window(
        scene,
        from,
        to,
        Some(Arc::new(
            ThreadPoolExecutor::new(4).expect("a pool of four threads"),
        )),
    );
    match first_divergence(&single, &pooled) {
        None => format!(
            "one thread and four threads agree over ticks {from}..={to}, so the run itself is \
             stable; the change is in the content or the code, not in the execution"
        ),
        Some(divergence) => match divergence.system {
            Some(system) => format!(
                "one thread and four threads diverge on tick {}, first in system `{}` (subsystem `{}`)",
                divergence.tick,
                system.name,
                system.subsystem()
            ),
            None => format!(
                "one thread and four threads diverge on tick {}, before any system of it ran",
                divergence.tick
            ),
        },
    }
}

/// Traces one window of a scene per system per tick, optionally on `executor`.
fn trace_window(
    scene: &Scene,
    from: u64,
    to: u64,
    executor: Option<Arc<dyn Executor>>,
) -> HashTrace {
    let mut sim = Simulation::new(scene.seed);
    ArenaGame::with_patterns(scene.scene_patterns()).build(&mut sim);
    if let Some(executor) = executor {
        sim.world_mut().set_executor(executor);
    }
    while sim.tick() < from {
        let tick = sim.tick();
        sim.step(scene.input(tick));
    }
    let frames: Vec<TickInput> = (from..to).map(|tick| scene.input(tick)).collect();
    let log = InputLog {
        seed: scene.seed,
        tick_rate_hz: fnp_game::TICK_RATE_HZ,
        frames,
    };
    trace(&mut sim, &log, TraceGranularity::PER_SYSTEM_PER_TICK)
}

/// The input log of a whole scene: the artefact that reproduces a diverging run elsewhere.
#[must_use]
pub fn input_log(scene: &Scene) -> InputLog {
    InputLog {
        seed: scene.seed,
        tick_rate_hz: fnp_game::TICK_RATE_HZ,
        frames: (0..scene.ticks).map(|tick| scene.input(tick)).collect(),
    }
}

/// Runs `scene` and compares it against the master in `directory`.
///
/// # Errors
/// If the master cannot be read or parsed. A master that simply does not match is not an error
/// here; it is a [`DiffReport`] that does not match.
pub fn check_scene(scene: &Scene, directory: &Path) -> Result<(DiffReport, HarnessReport), String> {
    let path = Master::path_in(directory, scene.name);
    let text =
        std::fs::read_to_string(&path).map_err(|error| format!("{}: {error}", path.display()))?;
    let master = Master::parse(&text).map_err(|error| format!("{}: {error}", path.display()))?;
    let report = run_scene(scene);
    let mut diff = compare(&master, &report);
    if let Some(window) = diff.window {
        diff.narrowing = Some(narrow(scene, window));
    }
    Ok((diff, report))
}

/// Rewrites the masters of `scenes` and logs `reason`.
///
/// # Errors
/// If a file cannot be written.
pub fn renew(
    scenes: &[Scene],
    directory: &Path,
    log: &Path,
    reason: &str,
) -> Result<Vec<String>, String> {
    let mut lines = Vec::new();
    let mut entry = format!("## Renewal\n\n- Reason: {reason}\n");
    std::fs::create_dir_all(directory)
        .map_err(|error| format!("{}: {error}", directory.display()))?;
    for scene in scenes {
        let report = run_scene(scene);
        let master = Master::from_report(&report);
        let path = Master::path_in(directory, scene.name);
        let previous = std::fs::read_to_string(&path)
            .ok()
            .and_then(|text| Master::parse(&text).ok())
            .map(|master| master.final_state_hash);
        std::fs::write(&path, master.to_json())
            .map_err(|error| format!("{}: {error}", path.display()))?;
        let change = match previous {
            Some(old) if old == master.final_state_hash => String::from("unchanged"),
            Some(old) => format!("{old:016x} -> {:016x}", master.final_state_hash),
            None => format!("new, {:016x}", master.final_state_hash),
        };
        let _ = writeln!(entry, "- `{}`: {change}", scene.name);
        lines.push(format!("{}: {change}", scene.name));
    }
    let _ = writeln!(
        entry,
        "- Engine version: {}\n",
        grimoire::sim::ENGINE_VERSION
    );
    let previous = std::fs::read_to_string(log).unwrap_or_else(|_| {
        String::from(
            "# Golden-master renewals\n\nEvery entry is its own commit (CONTRIBUTING, \
             \"Golden-Master und Referenzwerte\"). Newest last.\n\n",
        )
    });
    std::fs::write(log, format!("{previous}{entry}"))
        .map_err(|error| format!("{}: {error}", log.display()))?;
    Ok(lines)
}

/// The value of `"<name>": "<value>"`.
fn string_field(text: &str, name: &str) -> Result<String, String> {
    let needle = format!("\"{name}\": \"");
    let start = text.find(&needle).ok_or_else(|| format!("no `{name}`"))? + needle.len();
    let rest = &text[start..];
    let end = rest.find('"').ok_or_else(|| format!("`{name}` is open"))?;
    Ok(rest[..end].to_owned())
}

/// The value of `"<name>": <number>`.
fn number_field(text: &str, name: &str) -> Result<u64, String> {
    let needle = format!("\"{name}\": ");
    let start = text.find(&needle).ok_or_else(|| format!("no `{name}`"))? + needle.len();
    let rest = &text[start..];
    let end = rest
        .find(|c: char| !c.is_ascii_digit())
        .unwrap_or(rest.len());
    rest[..end]
        .parse()
        .map_err(|_| format!("`{name}` is not a number"))
}

/// The strings of `"<name>": ["a", "b"]`.
fn list_field(text: &str, name: &str) -> Vec<String> {
    let needle = format!("\"{name}\": [");
    let Some(start) = text.find(&needle) else {
        return Vec::new();
    };
    let rest = &text[start + needle.len()..];
    let Some(end) = rest.find(']') else {
        return Vec::new();
    };
    rest[..end]
        .split(',')
        .map(|item| item.trim().trim_matches('"').to_owned())
        .filter(|item| !item.is_empty())
        .collect()
}

/// The numbers of `"<name>": [1, 2]`.
fn number_list_field(text: &str, name: &str) -> Vec<u64> {
    list_field(text, name)
        .iter()
        .filter_map(|item| item.parse().ok())
        .collect()
}

/// The pairs of `"despawns": {"bounds": 1, "clear": 2}`.
fn despawn_field(text: &str) -> BTreeMap<String, u64> {
    let needle = "\"despawns\": {";
    let Some(start) = text.find(needle) else {
        return BTreeMap::new();
    };
    let rest = &text[start + needle.len()..];
    let Some(end) = rest.find('}') else {
        return BTreeMap::new();
    };
    rest[..end]
        .split(',')
        .filter_map(|pair| {
            let (cause, count) = pair.split_once(':')?;
            Some((
                cause.trim().trim_matches('"').to_owned(),
                count.trim().parse().ok()?,
            ))
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::scene::STANDARD_SUITE;

    #[test]
    fn a_master_survives_writing_and_reading() {
        let report = run_scene(&Scene {
            ticks: 120,
            ..STANDARD_SUITE[2]
        });
        let master = Master::from_report(&report);
        let text = master.to_json();
        let parsed = Master::parse(&text).expect("the master parses");
        assert_eq!(parsed, master);
        assert_eq!(parsed.to_json(), text);
        assert!(text.contains("\"schema\": \"grimoire.fnp.golden\""));
    }

    #[test]
    fn a_matching_run_shows_no_difference() {
        let scene = Scene {
            ticks: 120,
            ..STANDARD_SUITE[2]
        };
        let report = run_scene(&scene);
        let master = Master::from_report(&report);
        let diff = compare(&master, &report);
        assert!(diff.matches(), "{}", diff.to_text());
        assert!(diff.to_text().contains("matches its master"));
    }

    #[test]
    fn a_changed_hash_names_the_first_diverging_checkpoint_and_its_window() {
        let scene = Scene {
            ticks: 180,
            ..STANDARD_SUITE[2]
        };
        let report = run_scene(&scene);
        let mut master = Master::from_report(&report);
        // Pretend the second checkpoint changed: that is what a real divergence looks like.
        master.checkpoints[1].1 ^= 1;
        master.final_state_hash ^= 1;
        let diff = compare(&master, &report);
        assert!(!diff.matches());
        let (tick, _, _) = diff
            .first_diverging_checkpoint
            .expect("a diverging checkpoint");
        assert_eq!(tick, 120);
        assert_eq!(diff.window, Some((60, 120)));
        let text = diff.to_text();
        assert!(text.contains("first diverging checkpoint: tick 120"));
        assert!(text.contains("final_state_hash"));
    }

    #[test]
    fn a_changed_count_shows_up_even_when_every_hash_matches() {
        let scene = Scene {
            ticks: 120,
            ..STANDARD_SUITE[2]
        };
        let report = run_scene(&scene);
        let mut master = Master::from_report(&report);
        master.hits += 1;
        master.despawns.insert(String::from("bounds"), 99_999);
        let diff = compare(&master, &report);
        assert!(!diff.matches());
        assert!(diff.first_diverging_checkpoint.is_none());
        let fields: Vec<&str> = diff
            .differences
            .iter()
            .map(|difference| difference.field.as_str())
            .collect();
        assert!(fields.contains(&"hits"));
        assert!(fields.contains(&"despawns.bounds"));
    }

    #[test]
    fn narrowing_reports_that_both_executors_agree() {
        let scene = Scene {
            ticks: 120,
            ..STANDARD_SUITE[2]
        };
        let narrowing = narrow(&scene, (60, 120));
        assert!(narrowing.contains("agree"), "{narrowing}");
    }

    #[test]
    fn the_input_log_reproduces_the_scene() {
        let scene = Scene {
            ticks: 90,
            ..STANDARD_SUITE[0]
        };
        let log = input_log(&scene);
        assert_eq!(log.seed, scene.seed);
        assert_eq!(log.frames.len(), scene.ticks as usize);
        assert_eq!(log.frames[7], scene.input(7));
        // The log is a real replay file: it encodes and decodes.
        let bytes = log.to_bytes();
        assert_eq!(InputLog::from_bytes(&bytes).expect("the log decodes"), log);
    }

    #[test]
    fn a_broken_file_is_refused_with_a_reason() {
        assert!(Master::parse("{}").is_err());
        assert!(Master::parse("{ \"schema\": \"something.else\" }").is_err());
    }
}
