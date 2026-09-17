//! What a scene run produces: metrics, invariants, state hashes and an event log
//! (Plan 0002 WP7.4, PRD-0018 FR-02).
//!
//! A report is a pure function of its scene: no clock, no wall time, no machine name. Hashes are
//! written as 16 hex digits like every other engine JSON document (contract §2 rule 11), so a
//! report can be compared byte for byte across platforms — which is what the golden master of
//! WP7.5 will do with it.

use std::collections::BTreeMap;
use std::fmt::Write as _;

/// Why a bullet left the pool, as a report names it.
pub const DESPAWN_CAUSES: [&str; 7] = [
    "lifetime",
    "bounds",
    "transform",
    "behaviour",
    "clear",
    "swap",
    "external",
];

/// Counted facts about a run.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Metrics {
    /// Most live bullets seen after any tick.
    pub peak_bullets: u32,
    /// Live bullets after the last tick.
    pub final_bullets: u32,
    /// Sum of live bullets over all ticks: the run's bullet load, independent of its length.
    pub bullet_ticks: u64,
    /// Ticks that ended with an empty pool.
    pub empty_ticks: u64,
    /// First tick that ended with a live bullet, if any.
    pub first_bullet_tick: Option<u64>,
    /// Bullets that left the pool, by cause name.
    pub despawns: BTreeMap<&'static str, u64>,
    /// Spawns the pool refused because it was full (contract §11.4).
    pub dropped_spawns: u64,
    /// Capacity of the bullet pool.
    pub pool_capacity: u32,
    /// Hits the player proxy took.
    pub hits: u32,
    /// Rounds the run reached (it starts in round 1).
    pub rounds: u32,
}

impl Metrics {
    /// Total despawns over every cause.
    #[must_use]
    pub fn despawned(&self) -> u64 {
        self.despawns.values().sum()
    }
}

/// One checked promise about a run.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Invariant {
    /// Name, stable across versions.
    pub name: &'static str,
    /// Whether it held for the whole run.
    pub ok: bool,
    /// The first tick it broke on, if it broke.
    pub first_violation_tick: Option<u64>,
    /// What was seen, in one sentence.
    pub detail: String,
}

/// Something worth naming that happened during a run.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Event {
    /// Tick it happened on.
    pub tick: u64,
    /// What happened: `hit`, `round`, `cleared`, `peak`.
    pub kind: &'static str,
    /// The detail that makes it readable.
    pub detail: String,
}

/// A state hash the run recorded.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Checkpoint {
    /// Tick after which the hash was taken.
    pub tick: u64,
    /// The world's state hash (contract §8).
    pub state_hash: u64,
}

/// Everything one scene run produced.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct HarnessReport {
    /// Scene name.
    pub scene: String,
    /// Scene seed.
    pub seed: u64,
    /// Ticks run.
    pub ticks: u64,
    /// Patterns played, in the scene's order.
    pub patterns: Vec<&'static str>,
    /// Bot profile name.
    pub bot: &'static str,
    /// Engine version the run was built against.
    pub engine_version: &'static str,
    /// State hashes, every [`crate::HASH_EVERY`] ticks and after the last tick.
    pub checkpoints: Vec<Checkpoint>,
    /// State hash after the last tick.
    pub final_state_hash: u64,
    /// Counted facts.
    pub metrics: Metrics,
    /// Checked promises.
    pub invariants: Vec<Invariant>,
    /// Event log.
    pub events: Vec<Event>,
}

impl HarnessReport {
    /// Whether every invariant held.
    #[must_use]
    pub fn ok(&self) -> bool {
        self.invariants.iter().all(|invariant| invariant.ok)
    }

    /// The invariants that broke.
    #[must_use]
    pub fn violations(&self) -> Vec<&Invariant> {
        self.invariants
            .iter()
            .filter(|invariant| !invariant.ok)
            .collect()
    }

    /// The report as one JSON document, `grimoire.fnp.harness` version 1.
    ///
    /// Written by hand rather than derived, so the key order is the order below on every platform
    /// and every version of any dependency: a golden master compares these bytes (WP7.5).
    #[must_use]
    pub fn to_json(&self) -> String {
        let mut out = String::with_capacity(1024);
        out.push_str("{\n  \"schema\": \"grimoire.fnp.harness\",\n  \"schema_version\": 1,\n");
        let _ = writeln!(out, "  \"scene\": {},", quote(&self.scene));
        let _ = writeln!(out, "  \"seed\": {},", self.seed);
        let _ = writeln!(out, "  \"ticks\": {},", self.ticks);
        let _ = writeln!(out, "  \"bot\": {},", quote(self.bot));
        let _ = writeln!(out, "  \"engine_version\": {},", quote(self.engine_version));
        let patterns: Vec<String> = self.patterns.iter().map(|name| quote(name)).collect();
        let _ = writeln!(out, "  \"patterns\": [{}],", patterns.join(", "));
        let _ = writeln!(out, "  \"ok\": {},", self.ok());
        let _ = writeln!(
            out,
            "  \"final_state_hash\": {},",
            hex(self.final_state_hash)
        );
        out.push_str("  \"metrics\": {\n");
        let m = &self.metrics;
        let _ = writeln!(out, "    \"peak_bullets\": {},", m.peak_bullets);
        let _ = writeln!(out, "    \"final_bullets\": {},", m.final_bullets);
        let _ = writeln!(out, "    \"bullet_ticks\": {},", m.bullet_ticks);
        let _ = writeln!(out, "    \"empty_ticks\": {},", m.empty_ticks);
        match m.first_bullet_tick {
            Some(tick) => {
                let _ = writeln!(out, "    \"first_bullet_tick\": {tick},");
            }
            None => out.push_str("    \"first_bullet_tick\": null,\n"),
        }
        let _ = writeln!(out, "    \"despawned\": {},", m.despawned());
        out.push_str("    \"despawns\": {");
        let causes: Vec<String> = DESPAWN_CAUSES
            .iter()
            .filter_map(|cause| {
                m.despawns
                    .get(cause)
                    .map(|count| format!("{}: {count}", quote(cause)))
            })
            .collect();
        out.push_str(&causes.join(", "));
        out.push_str("},\n");
        let _ = writeln!(out, "    \"dropped_spawns\": {},", m.dropped_spawns);
        let _ = writeln!(out, "    \"pool_capacity\": {},", m.pool_capacity);
        let _ = writeln!(out, "    \"hits\": {},", m.hits);
        let _ = writeln!(out, "    \"rounds\": {}", m.rounds);
        out.push_str("  },\n  \"invariants\": [\n");
        let invariants: Vec<String> = self
            .invariants
            .iter()
            .map(|invariant| {
                let tick = invariant
                    .first_violation_tick
                    .map_or_else(|| String::from("null"), |tick| tick.to_string());
                format!(
                    "    {{ \"name\": {}, \"ok\": {}, \"first_violation_tick\": {tick}, \"detail\": {} }}",
                    quote(invariant.name),
                    invariant.ok,
                    quote(&invariant.detail)
                )
            })
            .collect();
        out.push_str(&invariants.join(",\n"));
        out.push_str("\n  ],\n  \"checkpoints\": [\n");
        let checkpoints: Vec<String> = self
            .checkpoints
            .iter()
            .map(|checkpoint| {
                format!(
                    "    {{ \"tick\": {}, \"state_hash\": {} }}",
                    checkpoint.tick,
                    hex(checkpoint.state_hash)
                )
            })
            .collect();
        out.push_str(&checkpoints.join(",\n"));
        out.push_str("\n  ],\n  \"events\": [\n");
        let events: Vec<String> = self
            .events
            .iter()
            .map(|event| {
                format!(
                    "    {{ \"tick\": {}, \"kind\": {}, \"detail\": {} }}",
                    event.tick,
                    quote(event.kind),
                    quote(&event.detail)
                )
            })
            .collect();
        out.push_str(&events.join(",\n"));
        out.push_str("\n  ]\n}\n");
        out
    }

    /// A short human summary: one line per report, for a suite run on the console.
    #[must_use]
    pub fn summary(&self) -> String {
        format!(
            "{:<16} seed {:<3} {:>5} ticks  peak {:>6}  final {:>6}  hits {:>3}  rounds {:>3}  \
             hash {}  {}",
            self.scene,
            self.seed,
            self.ticks,
            self.metrics.peak_bullets,
            self.metrics.final_bullets,
            self.metrics.hits,
            self.metrics.rounds,
            hex(self.final_state_hash),
            if self.ok() {
                String::from("ok")
            } else {
                format!("BROKEN: {}", self.violations()[0].name)
            }
        )
    }
}

/// A `u64` as the engine writes it in JSON: 16 lowercase hex digits in quotes.
fn hex(value: u64) -> String {
    format!("\"{value:016x}\"")
}

/// A JSON string: the report's own strings are ASCII, but escaping is done properly anyway.
fn quote(value: &str) -> String {
    let mut out = String::with_capacity(value.len() + 2);
    out.push('"');
    for character in value.chars() {
        match character {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => {
                let _ = write!(out, "\\u{:04x}", c as u32);
            }
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn report() -> HarnessReport {
        HarnessReport {
            scene: String::from("swarm_weave"),
            seed: 7,
            ticks: 2,
            patterns: vec!["swarm_weave"],
            bot: "dodger",
            engine_version: "0.5.0",
            checkpoints: vec![Checkpoint {
                tick: 1,
                state_hash: 0x0123_4567_89ab_cdef,
            }],
            final_state_hash: 0xfedc_ba98_7654_3210,
            metrics: Metrics {
                peak_bullets: 11,
                final_bullets: 0,
                bullet_ticks: 12,
                empty_ticks: 1,
                first_bullet_tick: Some(1),
                despawns: BTreeMap::from([("bounds", 11)]),
                dropped_spawns: 0,
                pool_capacity: 16_384,
                hits: 0,
                rounds: 1,
            },
            invariants: vec![Invariant {
                name: "no_nan",
                ok: true,
                first_violation_tick: None,
                detail: String::from("every position and velocity stayed finite"),
            }],
            events: vec![Event {
                tick: 1,
                kind: "peak",
                detail: String::from("11 bullets"),
            }],
        }
    }

    #[test]
    fn the_document_is_stable_and_names_hashes_in_hex() {
        let json = report().to_json();
        assert!(json.contains("\"schema\": \"grimoire.fnp.harness\""));
        assert!(json.contains("\"final_state_hash\": \"fedcba9876543210\""));
        assert!(json.contains("\"state_hash\": \"0123456789abcdef\""));
        assert!(json.contains("\"despawns\": {\"bounds\": 11}"));
        assert!(json.contains("\"ok\": true"));
        // Same report, same bytes.
        assert_eq!(json, report().to_json());
    }

    #[test]
    fn a_broken_invariant_shows_in_ok_and_in_the_summary() {
        let mut broken = report();
        broken.invariants[0].ok = false;
        broken.invariants[0].first_violation_tick = Some(3);
        assert!(!broken.ok());
        assert_eq!(broken.violations().len(), 1);
        assert!(broken.summary().contains("BROKEN: no_nan"));
        assert!(broken.to_json().contains("\"first_violation_tick\": 3"));
    }

    #[test]
    fn strings_are_escaped() {
        assert_eq!(quote("a\"b\\c\nd"), "\"a\\\"b\\\\c\\nd\"");
    }
}
