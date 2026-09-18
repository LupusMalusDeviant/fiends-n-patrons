//! The standard suite (Plan 0002 WP7.4): every scene runs, every invariant holds, and a scene is
//! the same run every time.
//!
//! These tests are the "standard suite under five minutes" the plan asks for. They run in the
//! debug profile like every other test, which is the slow case; the release binary runs the same
//! scenes in a fraction of a second.

use fnp_sim_harness::report::HarnessReport;
use fnp_sim_harness::scene::{BotProfile, Pattern, STANDARD_SUITE, Scene};
use fnp_sim_harness::{run_scene, run_standard_suite};

#[test]
fn the_standard_suite_holds_every_invariant() {
    let reports = run_standard_suite();
    assert_eq!(reports.len(), STANDARD_SUITE.len());
    for report in &reports {
        for invariant in &report.invariants {
            assert!(
                invariant.ok,
                "{} broke `{}`: {}",
                report.scene, invariant.name, invariant.detail
            );
        }
        // A scene that fires nothing would pass every invariant without proving anything.
        assert!(
            report.metrics.peak_bullets > 0,
            "{} never spawned a bullet",
            report.scene
        );
        assert_eq!(report.metrics.dropped_spawns, 0, "{}", report.scene);
        assert!(report.ok());
    }
}

#[test]
fn the_suite_exercises_the_clear_and_the_cascade() {
    let reports = run_standard_suite();
    let report = |name: &str| -> HarnessReport {
        reports
            .iter()
            .find(|report| report.scene == name)
            .expect("the suite has this scene")
            .clone()
    };

    // The curtain scene is the clear under load: thousands of bullets, emptied within one tick.
    let curtain = report("imp_curtain");
    assert!(curtain.metrics.peak_bullets > 1_000);
    assert!(curtain.metrics.hits > 0);
    assert!(
        curtain.events.iter().any(|event| event.kind == "cleared"),
        "the curtain scene never cleared"
    );

    // The cascade despawns bullets through transforms, not only through the bounds: that is the
    // seed becoming an emitter, which no other pattern does.
    let bloom = report("summoner_bloom");
    assert!(
        bloom
            .metrics
            .despawns
            .get("transform")
            .copied()
            .unwrap_or(0)
            > 0,
        "the cascade never opened a seed"
    );
    assert!(bloom.metrics.despawns.get("bounds").copied().unwrap_or(0) > 0);

    // Every scene that takes a hit also reports the round that follows it.
    for report in &reports {
        if report.metrics.hits > 0 {
            assert!(report.events.iter().any(|event| event.kind == "hit"));
            assert!(report.metrics.rounds > 1);
        }
    }
}

#[test]
fn a_scene_is_the_same_run_every_time() {
    let scene = Scene {
        name: "repeatable",
        seed: 4,
        ticks: 300,
        patterns: &[Pattern::SwarmWeave, Pattern::SummonerBloom],
        bot: BotProfile::Dodger,
    };
    let first = run_scene(&scene);
    let second = run_scene(&scene);
    assert_eq!(first.final_state_hash, second.final_state_hash);
    assert_eq!(first.checkpoints, second.checkpoints);
    assert_eq!(first.metrics, second.metrics);
    assert_eq!(first.events, second.events);
    assert_eq!(first.to_json(), second.to_json());
}

#[test]
fn the_seed_reaches_the_run() {
    let scene = Scene {
        name: "seeded",
        seed: 1,
        ticks: 240,
        patterns: &[Pattern::HarrierScatter],
        bot: BotProfile::Dodger,
    };
    let other = Scene { seed: 2, ..scene };
    assert_ne!(
        run_scene(&scene).final_state_hash,
        run_scene(&other).final_state_hash
    );
}

#[test]
fn the_idle_bot_never_moves_and_still_takes_the_pattern() {
    let scene = Scene {
        name: "idle",
        seed: 3,
        ticks: 240,
        patterns: &[Pattern::ImpVolley],
        bot: BotProfile::Idle,
    };
    let report = run_scene(&scene);
    assert!(report.ok());
    assert!(report.metrics.peak_bullets > 0);
    assert_eq!(report.bot, "idle");
}

#[test]
fn checkpoints_land_every_sixty_ticks_and_on_the_last_tick() {
    let scene = Scene {
        name: "checkpoints",
        seed: 5,
        ticks: 150,
        patterns: &[Pattern::ShooterRails],
        bot: BotProfile::Idle,
    };
    let report = run_scene(&scene);
    let ticks: Vec<u64> = report
        .checkpoints
        .iter()
        .map(|checkpoint| checkpoint.tick)
        .collect();
    assert_eq!(ticks, vec![60, 120, 150]);
    assert_eq!(
        report
            .checkpoints
            .last()
            .expect("a last checkpoint")
            .state_hash,
        report.final_state_hash
    );
}

#[test]
fn the_report_document_names_the_scene_and_its_patterns() {
    let scene = Scene {
        name: "document",
        seed: 6,
        ticks: 120,
        patterns: &[Pattern::BreakerToll],
        bot: BotProfile::Dodger,
    };
    let json = run_scene(&scene).to_json();
    assert!(json.contains("\"schema\": \"grimoire.fnp.harness\""));
    assert!(json.contains("\"scene\": \"document\""));
    assert!(json.contains("\"patterns\": [\"breaker_toll\"]"));
    assert!(json.contains("\"bot\": \"dodger\""));
    // The pinned engine's version, so an engine bump does not need this test edited.
    assert!(json.contains(&format!(
        "\"engine_version\": \"{}\"",
        grimoire::sim::ENGINE_VERSION
    )));
    assert!(json.contains("\"ok\": true"));
}
