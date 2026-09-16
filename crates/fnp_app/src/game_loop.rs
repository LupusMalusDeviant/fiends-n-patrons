//! The executable's main loop: fixed-timestep simulation of [`ArenaGame`], interpolated stage
//! extraction, render-side camera follow and rendering.
//!
//! **Why not `grimoire::App::run`.** The facade's loop owns its `WgpuRenderer` and gives plugins
//! no access to it, but a figure's meshes and textures must be registered with exactly that
//! renderer (`grimoire::adapters::figure_assets::load_figure` takes `&mut WgpuRenderer`). Until
//! the facade offers such a hook, the game drives its own loop on the platform layer, following
//! the facade's frame order (contract §9 and §9.3): clock, fixed timestep, one input sample per
//! frame for every tick due, extraction, camera follow, `render_stage`. The simulation is the
//! same plugin the headless harness runs, so state hashes do not depend on which loop ran it.

use std::cell::RefCell;
use std::fmt;
use std::rc::Rc;
use std::sync::Arc;
use std::time::Duration;

use fnp_game::arena::ArenaGame;
use fnp_game::arena::present::{self, ArenaVisuals, Hud};
use fnp_game::{GAME_TITLE, TICK_RATE_HZ};
use grimoire::InputState;
use grimoire::platform::{
    AppHandler, AppResult, PlatformContext, PlatformEvent, PlatformWindow, RawInputEvent,
};
use grimoire::prelude::*;
use grimoire::render::{CameraFollow, RenderError, Renderer, StageStats};
use grimoire::sim::FixedTimestep;

use crate::figures::VisualsError;

/// Creates the renderer and registers the arena's visuals once the window exists.
pub type RendererFactory<R> =
    Box<dyn FnOnce(&mut dyn PlatformContext) -> Result<(R, ArenaVisuals), LoopError>>;

/// A value shared between the loop and whoever started it (the loop is moved into the runner).
pub type Shared<T> = Rc<RefCell<T>>;

/// Frames between window title updates.
const TITLE_EVERY_FRAMES: u64 = 30;

/// Failure that ends the run.
#[derive(Debug)]
pub enum LoopError {
    /// The platform runner provided no window.
    NoWindow,
    /// Creating the renderer or rendering failed.
    Render(RenderError),
    /// Loading the figures or registering the stage geometry failed.
    Visuals(VisualsError),
}

impl fmt::Display for LoopError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::NoWindow => write!(f, "the platform provided no window"),
            Self::Render(error) => write!(f, "rendering failed: {error}"),
            Self::Visuals(error) => write!(f, "{error}"),
        }
    }
}

impl std::error::Error for LoopError {}

impl From<RenderError> for LoopError {
    fn from(error: RenderError) -> Self {
        Self::Render(error)
    }
}

impl From<VisualsError> for LoopError {
    fn from(error: VisualsError) -> Self {
        Self::Visuals(error)
    }
}

/// Configuration of one run.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LoopConfig {
    /// Simulation seed.
    pub seed: u64,
    /// End the run after this many frames.
    pub max_frames: Option<u64>,
}

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
    /// Most live bullets at the end of any frame.
    pub peak_bullets: u32,
    /// Most point lights submitted in one frame (arena, figures and bullet lights).
    pub peak_point_lights: u32,
    /// Round at the end of the run.
    pub round: u32,
    /// Hits taken during the run.
    pub hits: u32,
    /// Counters of the last rendered frame.
    pub last_stage: StageStats,
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
             peak {} point lights, round {}, {} hits",
            self.frames,
            self.ticks,
            self.mean_frame_time().as_secs_f64() * 1000.0,
            self.max_frame_time.as_secs_f64() * 1000.0,
            self.peak_bullets,
            self.peak_point_lights,
            self.round,
            self.hits
        )
    }
}

struct Running<R> {
    sim: Simulation,
    renderer: R,
    visuals: ArenaVisuals,
}

/// Frames-per-second over windows of at least one second.
#[derive(Debug, Default)]
struct Fps {
    window_start: Duration,
    frames: u64,
    value: f64,
}

impl Fps {
    fn frame(&mut self, now: Duration) -> f64 {
        self.frames += 1;
        let elapsed = now.saturating_sub(self.window_start);
        if elapsed >= Duration::from_secs(1) {
            self.value = self.frames as f64 / elapsed.as_secs_f64();
            self.frames = 0;
            self.window_start = now;
        }
        self.value
    }
}

/// The main loop, driven by `grimoire::platform::run_desktop` (or `run_headless` in tests).
pub struct GameLoop<R: Renderer> {
    config: LoopConfig,
    factory: Option<RendererFactory<R>>,
    running: Option<Running<R>>,
    input: InputState,
    input_map: InputMap,
    timestep: FixedTimestep,
    stage: StageFrame,
    follow: Option<CameraFollow>,
    last_time: Duration,
    fps: Fps,
    window: Option<Arc<dyn PlatformWindow>>,
    stats: Shared<RunStats>,
    error: Shared<Option<LoopError>>,
}

impl<R: Renderer> GameLoop<R> {
    /// Creates the loop; `factory` runs in `init`, when the window exists.
    #[must_use]
    pub fn new(config: LoopConfig, factory: RendererFactory<R>) -> Self {
        Self {
            config,
            factory: Some(factory),
            running: None,
            input: InputState::new(),
            input_map: InputMap::default(),
            timestep: FixedTimestep::new(TICK_RATE_HZ),
            stage: StageFrame::new(),
            follow: None,
            last_time: Duration::ZERO,
            fps: Fps::default(),
            window: None,
            stats: Rc::default(),
            error: Rc::default(),
        }
    }

    /// Measurements of the run, updated every frame.
    #[must_use]
    pub fn stats(&self) -> Shared<RunStats> {
        Rc::clone(&self.stats)
    }

    /// The error that ended the run, if any.
    #[must_use]
    pub fn error(&self) -> Shared<Option<LoopError>> {
        Rc::clone(&self.error)
    }

    /// The simulation, once `init` succeeded.
    #[must_use]
    pub fn simulation(&self) -> Option<&Simulation> {
        self.running.as_ref().map(|running| &running.sim)
    }

    fn title(hud: Hud, fps: f64) -> String {
        let mut title = format!(
            "{GAME_TITLE} - Prototyp - Runde {} - Treffer {}",
            hud.round, hud.hits
        );
        if hud.hit_pending {
            title.push_str(" - GETROFFEN");
        }
        if fps > 0.0 {
            title.push_str(&format!(" - {fps:.0} FPS"));
        }
        title
    }
}

impl<R: Renderer> AppHandler for GameLoop<R> {
    fn init(&mut self, ctx: &mut dyn PlatformContext) -> AppResult {
        let factory = self
            .factory
            .take()
            .ok_or("the main loop was initialised twice")?;
        let (renderer, visuals) = match factory(ctx) {
            Ok(created) => created,
            Err(error) => {
                let message = error.to_string();
                self.error.borrow_mut().get_or_insert(error);
                return Err(message.into());
            }
        };
        let mut sim = Simulation::new(self.config.seed);
        ArenaGame::new().build(&mut sim);
        self.window = ctx.window();
        if let Some(window) = &self.window {
            window.set_title(&Self::title(present::hud(sim.world()), 0.0));
        }
        self.running = Some(Running {
            sim,
            renderer,
            visuals,
        });
        self.last_time = ctx.clock().elapsed();
        self.fps.window_start = self.last_time;
        if self.config.max_frames == Some(0) {
            ctx.request_exit();
        }
        Ok(())
    }

    fn event(&mut self, ctx: &mut dyn PlatformContext, event: &PlatformEvent) {
        match event {
            PlatformEvent::Resized(size) => {
                if let Some(running) = &mut self.running {
                    running.renderer.resize(size.width, size.height);
                }
            }
            // Release events for keys held while unfocused never arrive (PRD-0013 robustness).
            PlatformEvent::Focused(false) => self.input.release_all(),
            PlatformEvent::Input(raw) => {
                if let RawInputEvent::Key {
                    code: KeyCode::Escape,
                    pressed: true,
                    repeat: false,
                } = *raw
                {
                    ctx.request_exit();
                }
                self.input.apply(raw);
            }
            PlatformEvent::Focused(true)
            | PlatformEvent::Occluded(_)
            | PlatformEvent::ScaleFactorChanged(_)
            | PlatformEvent::CloseRequested => {}
        }
    }

    fn frame(&mut self, ctx: &mut dyn PlatformContext) {
        let Some(running) = self.running.as_mut() else {
            return;
        };

        // The only clock read of the run; the simulation only ever sees whole ticks.
        let now = ctx.clock().elapsed();
        let frame_time = now.saturating_sub(self.last_time);
        self.last_time = now;
        let plan = self.timestep.advance(frame_time);

        let mut tick_input = TickInput::default();
        tick_input.slots[0] = self.input_map.sample(&self.input);
        for _ in 0..plan.ticks {
            running.sim.step(tick_input);
        }
        // A frame without ticks keeps latched taps for the next tick (facade contract §9).
        if plan.ticks > 0 {
            self.input.clear_presses();
        }

        self.stage.clear();
        let world = running.sim.world();
        present::extract(world, plan.alpha, &running.visuals, &mut self.stage);
        let template = present::camera_template();
        let mut camera = template;
        if let Some(player) = present::player_focus(world, plan.alpha) {
            let focus = present::camera_focus(player);
            let follow = self
                .follow
                .get_or_insert_with(|| CameraFollow::new(focus.to_array()));
            camera.target = follow.update(&template, focus.to_array(), frame_time.as_secs_f32());
        }
        self.stage.camera_25d = Some(camera);

        let rendered = match running.renderer.render_stage(&self.stage) {
            Ok(stage_stats) => stage_stats,
            Err(RenderError::SurfaceLost) => {
                ctx.frame_not_presented();
                StageStats::default()
            }
            Err(error) => {
                eprintln!("{GAME_TITLE}: rendering failed, ending the run: {error}");
                self.error.borrow_mut().get_or_insert(error.into());
                ctx.request_exit();
                return;
            }
        };

        let hud = present::hud(running.sim.world());
        let fps = self.fps.frame(now);
        {
            let mut stats = self.stats.borrow_mut();
            stats.frames += 1;
            stats.ticks += u64::from(plan.ticks);
            stats.total_frame_time += frame_time;
            stats.max_frame_time = stats.max_frame_time.max(frame_time);
            stats.peak_bullets = stats.peak_bullets.max(hud.bullets);
            stats.peak_point_lights = stats
                .peak_point_lights
                .max(u32::try_from(self.stage.point_lights.len()).unwrap_or(u32::MAX));
            stats.round = hud.round;
            stats.hits = hud.hits;
            stats.last_stage = rendered;
            if stats.frames.is_multiple_of(TITLE_EVERY_FRAMES)
                && let Some(window) = &self.window
            {
                window.set_title(&Self::title(hud, fps));
            }
            if self
                .config
                .max_frames
                .is_some_and(|max| stats.frames >= max)
            {
                ctx.request_exit();
            }
        }
    }

    fn shutdown(&mut self) {
        if self.running.is_some() {
            eprintln!("{GAME_TITLE}: {}", self.stats.borrow().summary());
        }
    }
}

#[cfg(test)]
mod tests {
    use grimoire::platform::run_headless;
    use grimoire::render::NullRenderer;

    use super::*;

    fn null_loop(max_frames: Option<u64>) -> GameLoop<NullRenderer> {
        GameLoop::new(
            LoopConfig {
                seed: 11,
                max_frames,
            },
            Box::new(|_| Ok((NullRenderer::default(), ArenaVisuals::placeholder()))),
        )
    }

    /// Feeds scripted events before each frame, like the facade's headless frame loop.
    struct Scripted<'a, R: Renderer> {
        inner: &'a mut GameLoop<R>,
        script: &'a dyn Fn(u64) -> Vec<PlatformEvent>,
        frame: u64,
    }

    impl<R: Renderer> AppHandler for Scripted<'_, R> {
        fn init(&mut self, ctx: &mut dyn PlatformContext) -> AppResult {
            self.inner.init(ctx)
        }

        fn event(&mut self, ctx: &mut dyn PlatformContext, event: &PlatformEvent) {
            self.inner.event(ctx, event);
        }

        fn frame(&mut self, ctx: &mut dyn PlatformContext) {
            for event in (self.script)(self.frame) {
                self.inner.event(ctx, &event);
                if ctx.exit_requested() {
                    return;
                }
            }
            self.frame += 1;
            self.inner.frame(ctx);
        }

        fn shutdown(&mut self) {
            self.inner.shutdown();
        }
    }

    fn key(code: KeyCode, pressed: bool) -> PlatformEvent {
        PlatformEvent::Input(RawInputEvent::Key {
            code,
            pressed,
            repeat: false,
        })
    }

    const FRAME: Duration = Duration::from_nanos(1_000_000_000 / TICK_RATE_HZ as u64);

    #[test]
    fn one_second_of_frames_runs_one_second_of_ticks() {
        let mut game = null_loop(None);
        run_headless(&mut game, u64::from(TICK_RATE_HZ), FRAME).expect("runs");
        let stats = *game.stats().borrow();
        assert_eq!(stats.frames, u64::from(TICK_RATE_HZ));
        // The manual clock rounds 1/60 s down to whole nanoseconds, so the last tick may be due
        // one frame later.
        assert!(stats.ticks + 1 >= u64::from(TICK_RATE_HZ), "{stats:?}");
        assert_eq!(stats.last_stage.meshes_rejected_invalid, 0);
        assert!(game.error().borrow().is_none());
    }

    #[test]
    fn holding_d_moves_the_soul_right_and_escape_quits() {
        let mut game = null_loop(None);
        let script = |frame: u64| match frame {
            0 => vec![key(KeyCode::KeyD, true)],
            30 => vec![key(KeyCode::KeyD, false), key(KeyCode::Escape, true)],
            _ => Vec::new(),
        };
        let mut scripted = Scripted {
            inner: &mut game,
            script: &script,
            frame: 0,
        };
        run_headless(&mut scripted, 1_000, FRAME).expect("runs");
        let stats = *game.stats().borrow();
        assert_eq!(stats.frames, 30, "escape ends the run before frame 31");
        let sim = game.simulation().expect("initialised");
        let focus = present::player_focus(sim.world(), 1.0).expect("the player exists");
        assert!(focus.x > 1.0, "the soul moved right: {focus:?}");
    }

    #[test]
    fn focus_loss_releases_held_keys() {
        let mut game = null_loop(Some(40));
        let script = |frame: u64| match frame {
            0 => vec![key(KeyCode::KeyW, true)],
            5 => vec![PlatformEvent::Focused(false)],
            _ => Vec::new(),
        };
        let mut scripted = Scripted {
            inner: &mut game,
            script: &script,
            frame: 0,
        };
        run_headless(&mut scripted, 1_000, FRAME).expect("runs");
        let sim = game.simulation().expect("initialised");
        let first = present::player_focus(sim.world(), 1.0).expect("player");
        // After focus loss the soul glides to a stop instead of walking on for 35 frames.
        assert!(first.y < fnp_game::arena::PLAYER_START.y + 1.0, "{first:?}");
    }

    #[test]
    fn max_frames_ends_the_run_and_a_factory_error_is_kept() {
        let mut game = null_loop(Some(7));
        run_headless(&mut game, 1_000, FRAME).expect("runs");
        assert_eq!(game.stats().borrow().frames, 7);

        let mut failing: GameLoop<NullRenderer> = GameLoop::new(
            LoopConfig {
                seed: 0,
                max_frames: None,
            },
            Box::new(|_| Err(LoopError::NoWindow)),
        );
        assert!(run_headless(&mut failing, 10, FRAME).is_err());
        assert!(matches!(
            *failing.error().borrow(),
            Some(LoopError::NoWindow)
        ));
        assert!(failing.simulation().is_none());
    }

    #[test]
    fn the_title_shows_round_hits_and_fps() {
        let hud = Hud {
            round: 3,
            hits: 2,
            hit_pending: true,
            bullets: 10,
        };
        assert_eq!(
            GameLoop::<NullRenderer>::title(hud, 59.7),
            "Fiends n Patrons - Prototyp - Runde 3 - Treffer 2 - GETROFFEN - 60 FPS"
        );
    }
}
