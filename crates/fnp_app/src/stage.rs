//! The presentation plugin of the arena and the app that runs it in the engine's main loop.
//!
//! The simulation is [`ArenaGame`]; [`ArenaStage`] adds everything the engine's loop needs to show
//! it: the figures and stage geometry registered through the asset hook
//! ([`GamePlugin::register_assets`], contract §9.10), the stage extraction, the camera's follow
//! point, the window title and the run summary. [`arena_app`] puts both into an [`AppBuilder`], so
//! the desktop run ([`AppBuilder::run`]), the offscreen capture ([`AppBuilder::run_offscreen`])
//! and the headless tests ([`AppBuilder::run_headless_frames_with_events`]) drive the same loop.

use std::cell::RefCell;
use std::path::PathBuf;
use std::rc::Rc;
use std::sync::Arc;
use std::time::{Duration, Instant};

use fnp_game::arena::present::{self, ArenaVisuals, Hud};
use fnp_game::arena::{ArenaGame, CURTAIN_BUTTON};
use fnp_game::{GAME_TITLE, TICK_RATE_HZ};
use grimoire::debug::FrameProfile;
use grimoire::prelude::*;
use grimoire::render::{LightBudget, StageRendererConfig};
use grimoire::{PluginError, RenderAssets};

use crate::figures::{load_visuals, placeholder_visuals};

/// Key that toggles the imp's curtain mode.
pub const CURTAIN_KEY: KeyCode = KeyCode::KeyV;

/// Frames between window title updates.
const TITLE_EVERY_FRAMES: u64 = 30;

/// A value shared between the plugin and whoever started the app (the loop owns the plugin).
pub type Shared<T> = Rc<RefCell<T>>;

/// Measurements of a run, for the summary line and tests.
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct RunStats {
    /// Frames rendered.
    pub frames: u64,
    /// Simulation ticks run.
    pub ticks: u64,
    /// Sum of all frame times (clock deltas between frames).
    pub total_frame_time: Duration,
    /// Longest frame time.
    pub max_frame_time: Duration,
    /// Most live bullets at the extraction of any frame.
    pub peak_bullets: u32,
    /// Round at the end of the run.
    pub round: u32,
    /// Hits taken during the run.
    pub hits: u32,
    /// Bullets the renderer drew, summed over all frames (profiler counter `bullets_drawn`).
    pub bullets_drawn: u64,
    /// Discard counters summed over all frames: live bullets the Sigil render adapter could not
    /// map, and bullets the bullet pass rejected (invalid, foreign palette space).
    pub bullets_unmapped: u64,
    /// See [`RunStats::bullets_unmapped`].
    pub bullets_rejected_invalid: u64,
    /// See [`RunStats::bullets_unmapped`].
    pub bullets_rejected_palette_space: u64,
    /// Whether the imp played its curtain mode at the end of the run.
    pub curtain: bool,
}

impl RunStats {
    /// Mean frame time, `Duration::ZERO` before the first frame.
    #[must_use]
    pub fn mean_frame_time(&self) -> Duration {
        if self.frames == 0 {
            return Duration::ZERO;
        }
        let frames = u32::try_from(self.frames).unwrap_or(u32::MAX);
        self.total_frame_time / frames
    }

    /// One line for the log at the end of a run.
    #[must_use]
    pub fn summary(&self) -> String {
        format!(
            "{} frames, {} ticks, mean frame time {:.2} ms (max {:.2} ms), peak {} bullets, \
             round {}, {} hits; bullets drawn {}, discarded: unmapped {}, invalid {}, palette \
             space {}",
            self.frames,
            self.ticks,
            self.mean_frame_time().as_secs_f64() * 1000.0,
            self.max_frame_time.as_secs_f64() * 1000.0,
            self.peak_bullets,
            self.round,
            self.hits,
            self.bullets_drawn,
            self.bullets_unmapped,
            self.bullets_rejected_invalid,
            self.bullets_rejected_palette_space
        )
    }
}

/// Where the arena's figures come from.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Figures {
    /// A figure pack with the figures `soul` and `imp`.
    Pack(PathBuf),
    /// Placeholder figures on the block mesh, for runs without a pack (headless tests).
    Placeholder,
}

/// The arena's presentation plugin; see the module documentation.
pub struct ArenaStage {
    figures: Figures,
    visuals: Option<ArenaVisuals>,
    stats: Shared<RunStats>,
    hud: Hud,
    window: Option<Arc<dyn PlatformWindow>>,
    log_summary: bool,
}

impl ArenaStage {
    /// A stage that loads `figures` when the loop registers assets.
    #[must_use]
    pub fn new(figures: Figures) -> Self {
        Self {
            figures,
            visuals: None,
            stats: Rc::default(),
            hud: Hud {
                round: 1,
                hits: 0,
                hit_pending: false,
                bullets: 0,
                curtain: false,
            },
            window: None,
            log_summary: true,
        }
    }

    /// Measurements of the run, updated every frame.
    #[must_use]
    pub fn stats(&self) -> Shared<RunStats> {
        Rc::clone(&self.stats)
    }

    fn title(hud: Hud, fps: f64) -> String {
        let mut title = format!(
            "{GAME_TITLE} - Prototyp - Runde {} - Treffer {}",
            hud.round, hud.hits
        );
        if hud.curtain {
            title.push_str(&format!(" - Vorhang: {} Bullets", hud.bullets));
        }
        if hud.hit_pending {
            title.push_str(" - GETROFFEN");
        }
        if fps > 0.0 {
            title.push_str(&format!(" - {fps:.0} FPS"));
        }
        title
    }
}

impl GamePlugin for ArenaStage {
    fn name(&self) -> &str {
        "fiends_n_patrons.stage"
    }

    fn register_assets(&mut self, assets: &mut dyn RenderAssets) -> Result<(), PluginError> {
        let visuals = match &self.figures {
            Figures::Pack(pack) => {
                let started = Instant::now();
                let (visuals, summary) = load_visuals(assets, pack)?;
                eprintln!(
                    "fiends-n-patrons: figure pack loaded in {:.1} s (soul: {} parts, {} joints, \
                     {:.2} m; imp: {} parts, {:.2} m)",
                    started.elapsed().as_secs_f64(),
                    summary.soul_parts,
                    summary.soul_joints,
                    summary.soul_height,
                    summary.imp_parts,
                    summary.imp_height
                );
                visuals
            }
            Figures::Placeholder => {
                self.log_summary = false;
                placeholder_visuals(assets)?
            }
        };
        self.visuals = Some(visuals);
        Ok(())
    }

    fn extract_stage(&mut self, world: &World, alpha: f32, stage: &mut StageFrame) {
        let Some(visuals) = &self.visuals else {
            return;
        };
        let extraction = present::extract(world, alpha, visuals, stage);
        self.hud = present::hud(world);
        let mut stats = self.stats.borrow_mut();
        stats.peak_bullets = stats.peak_bullets.max(self.hud.bullets);
        stats.bullets_unmapped += u64::from(extraction.unmapped_visual);
        stats.round = self.hud.round;
        stats.hits = self.hud.hits;
        stats.curtain = self.hud.curtain;
    }

    /// The camera's follow point: the interpolated player, pulled towards the imp's half of the
    /// arena ([`present::camera_focus`]). The prototype has no mouse aiming, so the offset does
    /// not matter as an aim anchor.
    fn focus(&self, world: &World, alpha: f32) -> Option<Vec2> {
        present::player_focus(world, alpha).map(present::camera_focus)
    }

    fn on_frame(&mut self, frame: &FrameStats) {
        let mut stats = self.stats.borrow_mut();
        stats.frames += 1;
        stats.ticks += u64::from(frame.ticks_this_frame);
        stats.total_frame_time += frame.frame_time;
        stats.max_frame_time = stats.max_frame_time.max(frame.frame_time);
        if stats.frames.is_multiple_of(TITLE_EVERY_FRAMES)
            && let Some(window) = &self.window
        {
            window.set_title(&Self::title(self.hud, frame.fps));
        }
    }

    fn on_profile(&mut self, profile: &FrameProfile) {
        let mut stats = self.stats.borrow_mut();
        for &(name, value) in profile.counters() {
            match name {
                "bullets_drawn" => stats.bullets_drawn += value,
                "bullets_rejected_invalid" => stats.bullets_rejected_invalid += value,
                "bullets_rejected_palette_space" => {
                    stats.bullets_rejected_palette_space += value;
                }
                _ => {}
            }
        }
    }

    fn window_created(&mut self, window: &Arc<dyn PlatformWindow>) {
        window.set_title(&Self::title(self.hud, 0.0));
        self.window = Some(Arc::clone(window));
    }

    fn shutdown(&mut self) {
        if self.log_summary {
            eprintln!("{GAME_TITLE}: {}", self.stats.borrow().summary());
        }
    }
}

/// Renderer configuration of the game: the high point-light budget (the arena's torches, the
/// figures' lights and the bullet lights the renderer derives) and 4x multisampling.
#[must_use]
pub fn stage_renderer_config() -> StageRendererConfig {
    let mut config = StageRendererConfig::default();
    config.base.vsync = true;
    config.base.allow_software_fallback = true;
    config.light_budget = LightBudget::High;
    config
}

/// The engine's default bindings plus [`CURTAIN_KEY`] on [`CURTAIN_BUTTON`].
#[must_use]
pub fn input_map() -> InputMap {
    InputMap::default().with(
        InputSource::Key(CURTAIN_KEY),
        InputAction::Button(CURTAIN_BUTTON),
    )
}

/// Configuration of one run of the arena.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ArenaConfig {
    /// Simulation seed.
    pub seed: u64,
    /// Where the figures come from.
    pub figures: Figures,
    /// End the run after this many frames.
    pub max_frames: Option<u64>,
}

/// The arena in the engine's main loop: [`ArenaStage`] and [`ArenaGame`], the game's tick rate,
/// renderer configuration and bindings, the tilted follow camera, `Escape` to quit and the
/// engine's stats overlay on its default key (F3). Returns the builder and the run's shared
/// measurements.
#[must_use]
pub fn arena_app(config: ArenaConfig) -> (AppBuilder, Shared<RunStats>) {
    let stage = ArenaStage::new(config.figures);
    let stats = stage.stats();
    let app = App::new(WindowConfig {
        title: String::from(GAME_TITLE),
        ..WindowConfig::default()
    })
    .seed(config.seed)
    .tick_rate(TICK_RATE_HZ)
    .stage_renderer_config(stage_renderer_config())
    .input_map(input_map())
    .exit_key(KeyCode::Escape)
    .camera25d(present::camera_template())
    // The stage comes first: the first plugin with a focus point drives the camera.
    .plugin(stage)
    .plugin(ArenaGame::new());
    let app = match config.max_frames {
        Some(frames) => app.max_frames(frames),
        None => app,
    };
    (app, stats)
}

#[cfg(test)]
mod tests {
    use grimoire::platform::{PlatformEvent, RawInputEvent};

    use super::*;

    const FRAME: Duration = Duration::from_nanos(1_000_000_000 / TICK_RATE_HZ as u64);

    fn headless(max_frames: Option<u64>) -> (AppBuilder, Shared<RunStats>) {
        arena_app(ArenaConfig {
            seed: 11,
            figures: Figures::Placeholder,
            max_frames,
        })
    }

    fn key(code: KeyCode, pressed: bool) -> PlatformEvent {
        PlatformEvent::Input(RawInputEvent::Key {
            code,
            pressed,
            repeat: false,
        })
    }

    #[test]
    fn one_second_of_frames_runs_one_second_of_ticks() {
        let (app, stats) = headless(None);
        let report = app
            .run_headless_frames(u64::from(TICK_RATE_HZ), FRAME)
            .expect("runs");
        assert_eq!(report.frames, u64::from(TICK_RATE_HZ));
        // The manual clock rounds 1/60 s down to whole nanoseconds, so the last tick may be due
        // one frame later.
        assert!(
            report.final_tick + 1 >= u64::from(TICK_RATE_HZ),
            "{report:?}"
        );
        let stats = *stats.borrow();
        assert_eq!(stats.frames, report.frames);
        assert_eq!(stats.ticks, report.final_tick);
    }

    #[test]
    fn holding_d_moves_the_soul_right_and_escape_quits() {
        let (app, stats) = headless(None);
        let report = app
            .run_headless_frames_with_events(1_000, FRAME, &mut |frame, events| match frame {
                0 => events.push(key(KeyCode::KeyD, true)),
                30 => {
                    events.push(key(KeyCode::KeyD, false));
                    events.push(key(KeyCode::Escape, true));
                }
                _ => {}
            })
            .expect("runs");
        assert_eq!(report.frames, 30, "escape ends the run before frame 31");
        assert_eq!(stats.borrow().frames, 30);
        // The same input headless: holding D for 30 ticks moves the soul right; the loop's
        // final hash matches a direct simulation with that input.
        let sim = simulate_holding_d(report.final_tick, |tick| tick < report.final_tick);
        assert_eq!(sim.state_hash(), report.final_hash);
        let player = present::player_focus(sim.world(), 1.0).expect("player");
        assert!(player.x > 1.0, "the soul moved right: {player:?}");
    }

    /// Steps a fresh arena `ticks` times, holding D while `held(tick)`.
    fn simulate_holding_d(ticks: u64, held: impl Fn(u64) -> bool) -> Simulation {
        let mut sim = Simulation::new(11);
        ArenaGame::new().build(&mut sim);
        for tick in 0..ticks {
            let mut input = TickInput::default();
            if held(tick) {
                input.slots[0].axes[0] = i16::MAX;
            }
            sim.step(input);
        }
        sim
    }

    #[test]
    fn max_frames_ends_the_run_and_bullets_are_drawn_without_discards() {
        // Three seconds without input: the imp fires, hits the soul, the round restarts.
        let (app, stats) = headless(Some(3 * u64::from(TICK_RATE_HZ)));
        let report = app.run_headless_frames(10_000, FRAME).expect("runs");
        assert_eq!(report.frames, 3 * u64::from(TICK_RATE_HZ));
        let stats = *stats.borrow();
        assert!(stats.bullets_drawn > 0, "{stats:?}");
        assert!(stats.hits >= 1, "{stats:?}");
        assert_eq!(stats.bullets_unmapped, 0);
        assert_eq!(stats.bullets_rejected_invalid, 0);
        assert_eq!(stats.bullets_rejected_palette_space, 0);
    }

    #[test]
    fn the_curtain_key_toggles_ten_thousand_bullets_without_discards() {
        let (app, stats) = headless(Some(450));
        app.run_headless_frames_with_events(10_000, FRAME, &mut |frame, events| match frame {
            10 => events.push(key(CURTAIN_KEY, true)),
            11 => events.push(key(CURTAIN_KEY, false)),
            _ => {}
        })
        .expect("runs");
        let stats = *stats.borrow();
        assert!(stats.curtain, "{stats:?}");
        assert!(stats.peak_bullets >= 9_000, "{stats:?}");
        assert_eq!(stats.hits, 0, "the soul cannot be hit in curtain mode");
        assert_eq!(stats.bullets_unmapped, 0);
        assert_eq!(stats.bullets_rejected_invalid, 0);
        assert_eq!(stats.bullets_rejected_palette_space, 0);
    }

    #[test]
    fn a_missing_pack_ends_the_run_with_an_asset_error() {
        let (app, _) = arena_app(ArenaConfig {
            seed: 0,
            figures: Figures::Pack(PathBuf::from("this/pack/does/not/exist.pack")),
            max_frames: Some(5),
        });
        let error = app
            .run_headless_frames(5, FRAME)
            .expect_err("the pack cannot be opened");
        let message = error.to_string();
        assert!(message.contains("fiends_n_patrons.stage"), "{message}");
        assert!(message.contains("figure pack"), "{message}");
    }

    #[test]
    fn the_title_shows_round_hits_curtain_and_fps() {
        let hud = Hud {
            round: 3,
            hits: 2,
            hit_pending: true,
            bullets: 10,
            curtain: false,
        };
        assert_eq!(
            ArenaStage::title(hud, 59.7),
            "Fiends n Patrons - Prototyp - Runde 3 - Treffer 2 - GETROFFEN - 60 FPS"
        );
        let curtain = Hud {
            hit_pending: false,
            bullets: 10_293,
            curtain: true,
            ..hud
        };
        assert_eq!(
            ArenaStage::title(curtain, 0.0),
            "Fiends n Patrons - Prototyp - Runde 3 - Treffer 2 - Vorhang: 10293 Bullets"
        );
    }
}
