//! # fnp_sim_harness
//!
//! Headless simulation harness of Fiends n Patrons: bot-driven runs by seed, invariant checks,
//! golden-master replays and balancing reports (PRD-0018).
//!
//! **Status:** first playable prototype plus scenes. [`scene`] describes a run - seed, pattern set,
//! bot profile -, [`run_scene`] executes it and returns a [`HarnessReport`] with metrics, checked
//! invariants, state hashes and an event log (Plan 0002 WP7.4), and the binary `fnp-sim-harness`
//! is the same thing on the command line.
//!
//! [`run_arena`] runs the [`ArenaGame`] plugin through the
//! facade's `App::run_headless` with any per-tick input, usually the scripted
//! [`arena_bot_input`]; [`simulate_arena`] drives the same run on a bare [`Simulation`] so tests
//! can inspect game state, and [`run_arena_with_executor`] repeats a run on a given executor.
//! [`curtain_bot_input`] is the same bot switching the imp to its curtain mode. The integration tests in `tests/determinism.rs` prove determinism, freeze a golden
//! final hash and check every checkpoint with 1, 2 and N threads.

pub mod golden;
pub mod report;
pub mod scene;

use std::sync::Arc;

use fnp_game::arena::{ArenaGame, CURTAIN_BUTTON, RoundState};
use fnp_game::{GAME_TITLE, Player, Position, TICK_RATE_HZ, Velocity};
use grimoire::HeadlessReport;
use grimoire::prelude::*;
use grimoire::sigil::{BulletPool, DespawnCause};

use crate::report::{Checkpoint, Event, HarnessReport, Invariant, Metrics};
use crate::scene::Scene;

/// Ticks between recorded state hashes in harness reports (one per simulated second).
pub const HASH_EVERY: u64 = 60;

/// Axis value of a fully deflected stick.
const FULL: i32 = i16::MAX as i32;

/// Scripted, deterministic bot input for the arena: a pure function of the tick.
///
/// The bot strafes along the bottom of the arena (triangle wave on axis 0, 6 s period), drifts
/// up and down every 2.5 s, and stands still for the last 1.5 s of every 10 s so the imp's aimed
/// fan catches it now and then: the scenario covers movement, bullets, hits and round restarts.
/// Integer arithmetic only.
#[must_use]
pub fn arena_bot_input(tick: u64) -> TickInput {
    let mut input = TickInput::default();
    if tick % 600 >= 510 {
        return input;
    }
    let phase = i32::try_from(tick % 360).unwrap_or(0);
    let triangle = if phase < 180 { phase } else { 360 - phase };
    let x = (triangle - 90) * FULL / 90;
    let y = if tick % 300 < 150 {
        FULL / 3
    } else {
        -FULL / 3
    };
    let slot = &mut input.slots[0];
    slot.axes[0] = i16::try_from(x).unwrap_or(0);
    slot.axes[1] = i16::try_from(y).unwrap_or(0);
    input
}

/// Runs the arena prototype headless for `ticks` ticks; `input(tick)` supplies each tick's input.
#[must_use]
pub fn run_arena(seed: u64, ticks: u64, input: &mut dyn FnMut(u64) -> TickInput) -> HeadlessReport {
    arena_app(seed).run_headless(ticks, input)
}

/// Tick on which [`curtain_bot_input`] presses the curtain button.
pub const CURTAIN_PRESS_TICK: u64 = 30;

/// [`arena_bot_input`] plus one press of the curtain button on [`CURTAIN_PRESS_TICK`]: the bot
/// switches the imp to its curtain mode (about ten thousand bullets) and keeps moving in it.
#[must_use]
pub fn curtain_bot_input(tick: u64) -> TickInput {
    let mut input = arena_bot_input(tick);
    if tick == CURTAIN_PRESS_TICK {
        input.slots[0].buttons |= 1 << CURTAIN_BUTTON;
    }
    input
}

/// Runs [`run_arena`] with `input` and `executor` installed on the world.
#[must_use]
pub fn run_arena_with_executor(
    seed: u64,
    ticks: u64,
    executor: Arc<dyn Executor>,
    input: &mut dyn FnMut(u64) -> TickInput,
) -> HeadlessReport {
    arena_app(seed)
        .executor(executor)
        .run_headless(ticks, input)
}

/// The headless arena app with `seed`.
fn arena_app(seed: u64) -> AppBuilder {
    App::new(WindowConfig {
        title: String::from(GAME_TITLE),
        ..WindowConfig::default()
    })
    .seed(seed)
    .tick_rate(TICK_RATE_HZ)
    .hash_every(HASH_EVERY)
    .plugin(ArenaGame::new())
}

/// Builds the arena into a fresh [`Simulation`] with `seed` and steps it `ticks` times, in the
/// order of `run_headless`, so the final state hash equals the one of [`run_arena`].
#[must_use]
pub fn simulate_arena(
    seed: u64,
    ticks: u64,
    input: &mut dyn FnMut(u64) -> TickInput,
) -> Simulation {
    let mut sim = Simulation::new(seed);
    ArenaGame::new().build(&mut sim);
    for _ in 0..ticks {
        sim.step(input(sim.tick()));
    }
    sim
}

/// Runs one scene and reports what happened.
///
/// The run is the arena the game itself plays - same player, same collision, same rounds - with
/// the scene's pattern set instead of the imp's two modes. Every tick is inspected after it ran:
/// the pool, the round state and every position and velocity, so the invariants below are checked
/// on the real state and not on a summary of it.
///
/// Invariants (PRD-0018 FR-02, Plan 0002 WP7.4):
///
/// - `no_nan`: no position or velocity of the player proxy or of a live bullet is ever non-finite.
/// - `pool_within_capacity`: the pool never exceeds its capacity and never drops a spawn, so a
///   pattern that would flood the arena fails the scene instead of quietly losing bullets.
/// - `clear_within_one_tick`: after a hit - the only thing that clears the pool - the pool is empty
///   at the end of the next tick at the latest (contract 11.4: games request clears).
#[must_use]
pub fn run_scene(scene: &Scene) -> HarnessReport {
    let mut sim = Simulation::new(scene.seed);
    ArenaGame::with_patterns(scene.scene_patterns()).build(&mut sim);

    let mut metrics = Metrics::default();
    let mut checkpoints = Vec::new();
    let mut events = Vec::new();
    let mut nan_tick = None;
    let mut pool_tick = None;
    let mut clear_tick = None;
    let mut pending_clear: Option<u64> = None;
    let mut hits = 0;
    let mut round = 1;

    for _ in 0..scene.ticks {
        let tick = sim.tick();
        sim.step(scene.input(tick));
        let tick = sim.tick();
        let world = sim.world();

        let mut live = 0;
        let mut capacity = 0;
        let mut dropped = 0;
        let mut finite_bullets = true;
        if let Some(pool) = world.resource::<BulletPool>() {
            live = pool.len();
            capacity = pool.capacity();
            dropped = pool.dropped_spawns();
            finite_bullets = pool
                .iter()
                .all(|bullet| is_finite(bullet.position()) && is_finite(bullet.velocity()));
            for event in pool.events() {
                *metrics.despawns.entry(cause_name(event.cause)).or_insert(0) += 1;
            }
        }
        metrics.pool_capacity = capacity;
        metrics.dropped_spawns = dropped;
        metrics.bullet_ticks = metrics.bullet_ticks.saturating_add(u64::from(live));
        if live > metrics.peak_bullets {
            metrics.peak_bullets = live;
            events.push(Event {
                tick,
                kind: "peak",
                detail: format!("{live} bullets"),
            });
        }
        if live == 0 {
            metrics.empty_ticks += 1;
        } else if metrics.first_bullet_tick.is_none() {
            metrics.first_bullet_tick = Some(tick);
        }
        metrics.final_bullets = live;

        let finite_players = world
            .query::<(&Position, &Velocity, &Player)>()
            .all(|(position, velocity, _)| is_finite(position.at) && is_finite(velocity.value));
        if !(finite_bullets && finite_players) && nan_tick.is_none() {
            nan_tick = Some(tick);
        }
        if (live > capacity || dropped > 0) && pool_tick.is_none() {
            pool_tick = Some(tick);
        }

        if let Some(state) = world.resource::<RoundState>().copied() {
            if state.hits > hits {
                hits = state.hits;
                pending_clear = Some(tick);
                events.push(Event {
                    tick,
                    kind: "hit",
                    detail: format!("hit {hits} in round {}", state.round),
                });
            }
            if state.round > round {
                round = state.round;
                events.push(Event {
                    tick,
                    kind: "round",
                    detail: format!("round {round} started"),
                });
            }
        }
        // A clear is requested in the tick of the hit and must have emptied the pool one tick later.
        if let Some(requested) = pending_clear
            && tick > requested
        {
            if live == 0 {
                events.push(Event {
                    tick,
                    kind: "cleared",
                    detail: format!("pool empty one tick after the hit on {requested}"),
                });
            } else if clear_tick.is_none() {
                clear_tick = Some(tick);
            }
            pending_clear = None;
        }

        if tick.is_multiple_of(HASH_EVERY) {
            checkpoints.push(Checkpoint {
                tick,
                state_hash: sim.state_hash(),
            });
        }
    }

    metrics.hits = hits;
    metrics.rounds = round;
    let final_state_hash = sim.state_hash();
    if checkpoints.last().map(|last| last.tick) != Some(sim.tick()) {
        checkpoints.push(Checkpoint {
            tick: sim.tick(),
            state_hash: final_state_hash,
        });
    }

    let invariants = vec![
        Invariant {
            name: "no_nan",
            ok: nan_tick.is_none(),
            first_violation_tick: nan_tick,
            detail: match nan_tick {
                None => String::from("every player and bullet position and velocity stayed finite"),
                Some(tick) => format!("a position or velocity was not finite on tick {tick}"),
            },
        },
        Invariant {
            name: "pool_within_capacity",
            ok: pool_tick.is_none(),
            first_violation_tick: pool_tick,
            detail: match pool_tick {
                None => format!(
                    "at most {} of {} slots were live, no spawn was dropped",
                    metrics.peak_bullets, metrics.pool_capacity
                ),
                Some(tick) => format!(
                    "the pool was over capacity or dropped a spawn on tick {tick} ({} dropped)",
                    metrics.dropped_spawns
                ),
            },
        },
        Invariant {
            name: "clear_within_one_tick",
            ok: clear_tick.is_none(),
            first_violation_tick: clear_tick,
            detail: match clear_tick {
                None if hits == 0 => String::from("no hit, so no clear was requested"),
                None => format!("every one of the {hits} hits emptied the pool within one tick"),
                Some(tick) => {
                    format!("the pool still had bullets one tick after the hit, on {tick}")
                }
            },
        },
    ];

    HarnessReport {
        scene: String::from(scene.name),
        seed: scene.seed,
        ticks: scene.ticks,
        patterns: scene
            .patterns
            .iter()
            .map(|pattern| pattern.name())
            .collect(),
        bot: scene.bot.name(),
        engine_version: grimoire::sim::ENGINE_VERSION,
        checkpoints,
        final_state_hash,
        metrics,
        invariants,
        events,
    }
}

/// Runs every scene of [`scene::STANDARD_SUITE`], in order.
#[must_use]
pub fn run_standard_suite() -> Vec<HarnessReport> {
    scene::STANDARD_SUITE.iter().map(run_scene).collect()
}

/// Whether both components of `value` are finite.
fn is_finite(value: Vec2) -> bool {
    value.x.is_finite() && value.y.is_finite()
}

/// The report's name for a despawn cause.
fn cause_name(cause: DespawnCause) -> &'static str {
    match cause {
        DespawnCause::Lifetime => "lifetime",
        DespawnCause::Bounds => "bounds",
        DespawnCause::Transform => "transform",
        DespawnCause::Behavior => "behaviour",
        DespawnCause::Clear => "clear",
        DespawnCause::Swap => "swap",
        _ => "external",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn arena_bot_input_moves_both_ways_and_rests() {
        let frames: Vec<TickInput> = (0..600).map(arena_bot_input).collect();
        let axis_x = |frame: &TickInput| frame.slots[0].axes[0];
        assert!(frames.iter().any(|f| axis_x(f) == i16::MAX));
        assert!(frames.iter().any(|f| axis_x(f) == -i16::MAX));
        assert!(frames[510..].iter().all(|f| *f == TickInput::default()));
        assert!(
            frames
                .iter()
                .all(|f| f.slots[1..] == [InputFrame::default(); 3])
        );
        for tick in [0, 1, 359, 360, 509, 510, 599, 600, 10_000] {
            assert_eq!(arena_bot_input(tick), arena_bot_input(tick));
        }
        let presses = (0..600)
            .filter(|&tick| curtain_bot_input(tick).slots[0].is_pressed(CURTAIN_BUTTON))
            .count();
        assert_eq!(presses, 1, "the curtain bot presses once");
    }
}
