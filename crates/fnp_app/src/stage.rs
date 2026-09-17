//! The presentation plugin of the arena and the app that runs it in the engine's main loop.
//!
//! The simulation is [`ArenaGame`]; [`ArenaStage`] adds everything the engine's loop needs to show
//! it: the figures and stage geometry registered through the asset hook
//! ([`GamePlugin::register_assets`], contract §9.10), the stage extraction, the switchable camera
//! presets with their follow spring, the aim anchor, the window title and the run summary.
//! [`arena_app`] puts both into an [`AppBuilder`], so the desktop run ([`AppBuilder::run`]), the
//! offscreen capture ([`AppBuilder::run_offscreen`]) and the headless tests
//! ([`AppBuilder::run_headless_frames_with_events`]) drive the same loop.

use std::cell::RefCell;
use std::path::PathBuf;
use std::rc::Rc;
use std::sync::Arc;
use std::time::{Duration, Instant};

use fnp_game::arena::present::{self, ArenaVisuals, CAMERA_PRESETS, Hud};
use fnp_game::arena::{ArenaGame, CAMERA_BUTTON, CURTAIN_BUTTON};
use fnp_game::{GAME_TITLE, TICK_RATE_HZ};
use grimoire::debug::FrameProfile;
use grimoire::prelude::*;
use grimoire::render::{CameraFollow, LightBudget, StageRendererConfig};
use grimoire::{PluginError, RenderAssets};

use crate::figures::{load_visuals, placeholder_visuals};

/// Key that toggles the imp's curtain mode.
pub const CURTAIN_KEY: KeyCode = KeyCode::KeyV;

/// Key that cycles the camera presets ([`CAMERA_PRESETS`]).
pub const CAMERA_KEY: KeyCode = KeyCode::KeyC;

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
    /// Camera preset (index into [`CAMERA_PRESETS`]) at the end of the run.
    pub camera_preset: usize,
    /// Camera preset switches during the run.
    pub camera_switches: u32,
    /// Aim axes 2 and 3 of the most recent tick input (the loop samples them through the camera).
    pub last_aim: [i16; 2],
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
    /// Index into [`CAMERA_PRESETS`].
    camera_preset: usize,
    /// Whether [`CAMERA_BUTTON`] was held in the tick seen last.
    camera_held: bool,
    /// Tick whose input was seen last, so a frame without a tick does not toggle twice.
    input_tick: Option<u64>,
    /// Render-side follow spring of the camera target.
    follow: Option<CameraFollow>,
    /// Real time of the last reported frame in seconds, the follow spring's step.
    frame_seconds: f32,
}

impl ArenaStage {
    /// A stage that loads `figures` when the loop registers assets and starts with camera preset
    /// `camera_preset` (an index into [`CAMERA_PRESETS`], wrapping).
    #[must_use]
    pub fn new(figures: Figures, camera_preset: usize) -> Self {
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
            camera_preset: camera_preset % CAMERA_PRESETS.len(),
            camera_held: false,
            input_tick: None,
            follow: None,
            frame_seconds: 0.0,
        }
    }

    /// Measurements of the run, updated every frame.
    #[must_use]
    pub fn stats(&self) -> Shared<RunStats> {
        Rc::clone(&self.stats)
    }

    fn title(hud: Hud, camera_preset: usize, fps: f64) -> String {
        let preset = CAMERA_PRESETS[camera_preset % CAMERA_PRESETS.len()];
        let mut title = format!(
            "{GAME_TITLE} - Prototyp - Runde {} - Treffer {} - Kamera {} ({:.0} Grad, {} m)",
            hud.round, hud.hits, preset.name, preset.tilt_degrees, preset.distance
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
        let input = world.resource::<TickInput>().copied().unwrap_or_default();
        let tick = world.resource::<Tick>().map(|tick| tick.0);
        if self.input_tick != tick {
            self.input_tick = tick;
            let held = input.slots[0].is_pressed(CAMERA_BUTTON);
            if held && !self.camera_held {
                self.camera_preset = (self.camera_preset + 1) % CAMERA_PRESETS.len();
                let preset = CAMERA_PRESETS[self.camera_preset];
                self.stats.borrow_mut().camera_switches += 1;
                eprintln!(
                    "fiends-n-patrons: camera preset {} ({} degrees, {} m)",
                    preset.name, preset.tilt_degrees, preset.distance
                );
                if let Some(window) = &self.window {
                    window.set_title(&Self::title(self.hud, self.camera_preset, 0.0));
                }
            }
            self.camera_held = held;
        }
        // The stage owns the camera (no `AppBuilder::camera25d`), so the preset can change; the
        // loop samples mouse aim through exactly this camera (contract §9.3, §9.4).
        let mut camera = present::camera_preset(self.camera_preset);
        if let Some(player) = present::player_focus(world, alpha) {
            let focus = present::camera_focus(player).to_array();
            let follow = self.follow.get_or_insert_with(|| CameraFollow::new(focus));
            camera.target = follow.update(&camera, focus, self.frame_seconds);
        }
        stage.camera_25d = Some(camera);

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
        stats.camera_preset = self.camera_preset;
        stats.last_aim = [input.slots[0].axes[2], input.slots[0].axes[3]];
    }

    /// The mouse-aim anchor: the interpolated player. The camera follows its own, pulled point
    /// ([`present::camera_focus`]) in `extract_stage`, so aim directions start at the soul.
    fn focus(&self, world: &World, alpha: f32) -> Option<Vec2> {
        present::player_focus(world, alpha)
    }

    fn on_frame(&mut self, frame: &FrameStats) {
        self.frame_seconds = frame.frame_time.as_secs_f32();
        let mut stats = self.stats.borrow_mut();
        stats.frames += 1;
        stats.ticks += u64::from(frame.ticks_this_frame);
        stats.total_frame_time += frame.frame_time;
        stats.max_frame_time = stats.max_frame_time.max(frame.frame_time);
        if stats.frames.is_multiple_of(TITLE_EVERY_FRAMES)
            && let Some(window) = &self.window
        {
            window.set_title(&Self::title(self.hud, self.camera_preset, frame.fps));
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
        window.set_title(&Self::title(self.hud, self.camera_preset, 0.0));
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

/// The engine's default bindings plus [`CURTAIN_KEY`] on [`CURTAIN_BUTTON`] and [`CAMERA_KEY`] on
/// [`CAMERA_BUTTON`].
#[must_use]
pub fn input_map() -> InputMap {
    InputMap::default()
        .with(
            InputSource::Key(CURTAIN_KEY),
            InputAction::Button(CURTAIN_BUTTON),
        )
        .with(
            InputSource::Key(CAMERA_KEY),
            InputAction::Button(CAMERA_BUTTON),
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
    /// Camera preset to start with (index into [`CAMERA_PRESETS`]; 0 is the default A).
    pub camera_preset: usize,
}

/// The arena in the engine's main loop: [`ArenaStage`] and [`ArenaGame`], the game's tick rate,
/// renderer configuration and bindings, `Escape` to quit and the engine's stats overlay on its
/// default key (F3). The stage drives the camera itself, so the builder configures none. Returns
/// the builder and the run's shared measurements.
#[must_use]
pub fn arena_app(config: ArenaConfig) -> (AppBuilder, Shared<RunStats>) {
    let stage = ArenaStage::new(config.figures, config.camera_preset);
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
    // The stage comes first: the first plugin with a focus point anchors mouse aim.
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
        headless_with_camera(max_frames, 0)
    }

    fn headless_with_camera(
        max_frames: Option<u64>,
        camera_preset: usize,
    ) -> (AppBuilder, Shared<RunStats>) {
        arena_app(ArenaConfig {
            seed: 11,
            figures: Figures::Placeholder,
            max_frames,
            camera_preset,
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
            camera_preset: 0,
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
            ArenaStage::title(hud, 0, 59.7),
            "Fiends n Patrons - Prototyp - Runde 3 - Treffer 2 - Kamera A (60 Grad, 14.5 m) - \
             GETROFFEN - 60 FPS"
        );
        let curtain = Hud {
            hit_pending: false,
            bullets: 10_293,
            curtain: true,
            ..hud
        };
        assert_eq!(
            ArenaStage::title(curtain, 2, 0.0),
            "Fiends n Patrons - Prototyp - Runde 3 - Treffer 2 - Kamera C (45 Grad, 11 m) - \
             Vorhang: 10293 Bullets"
        );
    }

    /// Taps `code` in each of `frames` (press in the frame, release in the next).
    fn taps(code: KeyCode, frames: &[u64], frame: u64, events: &mut Vec<PlatformEvent>) {
        if frames.contains(&frame) {
            events.push(key(code, true));
        }
        if frame > 0 && frames.contains(&(frame - 1)) {
            events.push(key(code, false));
        }
    }

    #[test]
    fn the_camera_key_cycles_the_presets_once_per_tap() {
        let (app, stats) = headless(Some(80));
        app.run_headless_frames_with_events(1_000, FRAME, &mut |frame, events| {
            taps(CAMERA_KEY, &[10, 20, 30, 40], frame, events);
        })
        .expect("runs");
        let stats = *stats.borrow();
        assert_eq!(stats.camera_switches, 4);
        assert_eq!(stats.camera_preset, 1, "A, B, C, A, B");
    }

    #[test]
    fn camera_presets_never_change_the_state_hashes() {
        // A replay with the state hash after every tick: the same movement script, started under
        // each preset and switching presets three times mid-run, against the same script without
        // the camera key. The camera differs in every frame; the simulation does not.
        const TAPS: [u64; 3] = [30, 90, 150];
        let run = |start: usize, camera_key: bool| {
            let (app, stats) = headless_with_camera(Some(240), start);
            let report = app
                .hash_every(1)
                .run_headless_frames_with_events(1_000, FRAME, &mut |frame, events| {
                    match frame {
                        0 => events.push(key(KeyCode::KeyD, true)),
                        50 => events.push(key(KeyCode::KeyD, false)),
                        70 => events.push(key(KeyCode::KeyW, true)),
                        110 => events.push(key(KeyCode::KeyW, false)),
                        _ => {}
                    }
                    if camera_key {
                        taps(CAMERA_KEY, &TAPS, frame, events);
                    }
                })
                .expect("runs");
            let stats = *stats.borrow();
            (report, stats)
        };

        let (without_key, _) = run(0, false);
        assert!(without_key.hashes.len() >= 200, "a hash after every tick");
        let (reference, _) = run(0, true);
        for start in 0..CAMERA_PRESETS.len() {
            let (report, stats) = run(start, true);
            assert_eq!(stats.camera_switches, 3);
            assert_eq!(
                stats.camera_preset, start,
                "three switches bring every start back"
            );
            assert_eq!(report.hashes, reference.hashes, "start preset {start}");
            assert_eq!(report.final_hash, reference.final_hash);
        }

        // Against the run without the key, only ticks whose recorded input carries the button
        // itself may differ (the tick input is part of the state); every later tick is equal.
        assert_eq!(reference.hashes.len(), without_key.hashes.len());
        for (with, without) in reference.hashes.iter().zip(&without_key.hashes) {
            assert_eq!(with.0, without.0);
            if with.1 != without.1 {
                assert!(
                    TAPS.iter().any(|&tap| (tap..=tap + 3).contains(&with.0)),
                    "tick {} differs away from a camera key tap",
                    with.0
                );
            }
        }
        assert_eq!(reference.final_hash, without_key.final_hash);
    }

    #[test]
    fn the_loop_samples_mouse_aim_through_the_active_preset() {
        // The soul stands at its start; the cursor sits over the ground point three units right of
        // and two units beyond it, projected through the camera the stage draws. Whatever the
        // preset, the loop must turn that cursor into the direction (3, 2).
        let viewport = [1280.0, 720.0];
        let player = fnp_game::arena::PLAYER_START;
        let offset = Vec2::new(3.0, 2.0);
        let expected = grimoire::quantize_aim(offset);
        for preset in 0..CAMERA_PRESETS.len() {
            let mut camera = present::camera_preset(preset);
            camera.target = present::camera_focus(player).to_array();
            let [x, y] = camera
                .ground_to_screen((player + offset).to_array(), viewport)
                .expect("visible");
            let (app, stats) = headless_with_camera(Some(20), preset);
            app.run_headless_frames_with_events(1_000, FRAME, &mut |frame, events| {
                if frame == 0 {
                    events.push(PlatformEvent::Input(RawInputEvent::CursorMoved {
                        x: f64::from(x),
                        y: f64::from(y),
                    }));
                }
            })
            .expect("runs");
            let aim = stats.borrow().last_aim;
            for axis in 0..2 {
                assert!(
                    (i32::from(aim[axis]) - i32::from(expected[axis])).abs() <= 2,
                    "preset {preset}: aim {aim:?}, expected {expected:?}"
                );
            }
        }
    }
}
