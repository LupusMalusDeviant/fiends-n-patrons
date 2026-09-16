//! Offscreen capture of a scripted run of the real main loop: moving, dodging, standing still in
//! the imp's aimed fan until it hits, the restart, and moving again.
//!
//! Needs a figure pack and a GPU adapter, so it is `#[ignore]`d and runs only on request:
//!
//! ```text
//! FNP_FIGURE_PACK=<figures.pack> FNP_CAPTURE_DIR=<output dir> GRIMOIRE_GPU_ADAPTER=software \
//!   cargo test --release -p fnp_app --test offscreen_capture -- --ignored --nocapture
//! ```
//!
//! Optional: `FNP_CAPTURE_EVERY=<n>` keeps every n-th frame (default 2), `FNP_CAPTURE_SIZE=<w>x<h>`
//! (default 960x540). Frames are written as binary PPM (`frame_00000.ppm`, ...), which any image
//! tool turns into a GIF or video; this crate deliberately adds no image dependency for it.

use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

use fnp_app::figures::load_visuals;
use fnp_app::game_loop::{GameLoop, LoopConfig, LoopError};
use fnp_app::stage_renderer_config;
use fnp_game::TICK_RATE_HZ;
use grimoire::platform::{
    AppHandler, AppResult, KeyCode, PlatformContext, PlatformEvent, RawInputEvent, run_headless,
};
use grimoire::render::{
    RenderError, RenderFrame, RenderStats, Renderer, StageFrame, StageStats, WgpuRenderer,
};

/// Frames of the scripted run (one tick per frame at the game's rate).
const FRAMES: u64 = 480;

/// Wraps the offscreen renderer and writes every `every`-th rendered frame to `dir`.
struct CapturingRenderer {
    inner: WgpuRenderer,
    dir: PathBuf,
    size: (u32, u32),
    every: u64,
    rendered: u64,
    written: u64,
}

impl CapturingRenderer {
    fn write_ppm(&self, rgba: &[u8]) -> std::io::Result<()> {
        let path = self.dir.join(format!("frame_{:05}.ppm", self.written));
        let mut file = std::io::BufWriter::new(std::fs::File::create(path)?);
        write!(file, "P6\n{} {}\n255\n", self.size.0, self.size.1)?;
        for pixel in rgba.as_chunks::<4>().0 {
            file.write_all(&pixel[..3])?;
        }
        file.flush()
    }
}

impl Renderer for CapturingRenderer {
    fn resize(&mut self, width: u32, height: u32) {
        self.inner.resize(width, height);
    }

    fn render(&mut self, frame: &RenderFrame) -> Result<RenderStats, RenderError> {
        self.inner.render(frame)
    }

    fn backend_name(&self) -> &str {
        self.inner.backend_name()
    }

    fn supports_stage(&self) -> bool {
        true
    }

    fn render_stage(&mut self, frame: &StageFrame) -> Result<StageStats, RenderError> {
        let stats = self.inner.render_stage(frame)?;
        if self.rendered.is_multiple_of(self.every) {
            let rgba = self.inner.read_offscreen_rgba()?;
            self.write_ppm(&rgba)
                .map_err(|error| RenderError::Backend(format!("writing a frame: {error}")))?;
            self.written += 1;
        }
        self.rendered += 1;
        Ok(stats)
    }
}

fn key(code: KeyCode, pressed: bool) -> PlatformEvent {
    PlatformEvent::Input(RawInputEvent::Key {
        code,
        pressed,
        repeat: false,
    })
}

/// The scripted player: strafe right, back left, stand in the aimed fan until hit, then (after
/// the restart) walk up and around.
fn script(frame: u64) -> Vec<PlatformEvent> {
    match frame {
        0 => vec![key(KeyCode::KeyD, true)],
        40 => vec![key(KeyCode::KeyD, false), key(KeyCode::KeyA, true)],
        95 => vec![key(KeyCode::KeyA, false)],
        300 => vec![key(KeyCode::KeyW, true), key(KeyCode::KeyA, true)],
        340 => vec![key(KeyCode::KeyW, false)],
        380 => vec![key(KeyCode::KeyA, false), key(KeyCode::KeyD, true)],
        450 => vec![key(KeyCode::KeyD, false), key(KeyCode::KeyS, true)],
        470 => vec![key(KeyCode::KeyS, false)],
        _ => Vec::new(),
    }
}

struct Scripted<'a> {
    inner: &'a mut GameLoop<CapturingRenderer>,
    frame: u64,
}

impl AppHandler for Scripted<'_> {
    fn init(&mut self, ctx: &mut dyn PlatformContext) -> AppResult {
        self.inner.init(ctx)
    }

    fn event(&mut self, ctx: &mut dyn PlatformContext, event: &PlatformEvent) {
        self.inner.event(ctx, event);
    }

    fn frame(&mut self, ctx: &mut dyn PlatformContext) {
        for event in script(self.frame) {
            self.inner.event(ctx, &event);
        }
        self.frame += 1;
        self.inner.frame(ctx);
    }

    fn shutdown(&mut self) {
        self.inner.shutdown();
    }
}

fn capture_size() -> (u32, u32) {
    std::env::var("FNP_CAPTURE_SIZE")
        .ok()
        .and_then(|value| {
            let (w, h) = value.split_once('x')?;
            Some((w.parse().ok()?, h.parse().ok()?))
        })
        .unwrap_or((960, 540))
}

#[test]
#[ignore = "needs a figure pack (FNP_FIGURE_PACK), an output directory (FNP_CAPTURE_DIR) and a GPU adapter"]
fn capture_a_scripted_run() {
    let (Some(pack), Some(dir)) = (
        std::env::var_os("FNP_FIGURE_PACK"),
        std::env::var_os("FNP_CAPTURE_DIR"),
    ) else {
        eprintln!("FNP_FIGURE_PACK or FNP_CAPTURE_DIR not set; skipping the capture");
        return;
    };
    let pack = PathBuf::from(pack);
    let dir = PathBuf::from(dir);
    std::fs::create_dir_all(&dir).expect("the capture directory can be created");
    let every = std::env::var("FNP_CAPTURE_EVERY")
        .ok()
        .and_then(|value| value.parse().ok())
        .filter(|&every: &u64| every > 0)
        .unwrap_or(2);
    let size = capture_size();

    let started = Instant::now();
    let capture_dir = dir.clone();
    let factory = Box::new(move |_: &mut dyn PlatformContext| {
        let mut renderer =
            WgpuRenderer::new_offscreen_staged(size.0, size.1, stage_renderer_config())?;
        println!("fnp-capture: renderer {}", renderer.adapter_report_line());
        let (visuals, summary) = load_visuals(&mut renderer, Path::new(&pack))?;
        println!("fnp-capture: figures {summary:?}");
        Ok::<_, LoopError>((
            CapturingRenderer {
                inner: renderer,
                dir: capture_dir,
                size,
                every,
                rendered: 0,
                written: 0,
            },
            visuals,
        ))
    });
    let mut game = GameLoop::new(
        LoopConfig {
            seed: 42,
            max_frames: Some(FRAMES),
        },
        factory,
    );
    let frame = Duration::from_nanos(1_000_000_000 / u64::from(TICK_RATE_HZ));
    let result = {
        let mut scripted = Scripted {
            inner: &mut game,
            frame: 0,
        };
        run_headless(&mut scripted, FRAMES, frame)
    };
    if let Some(LoopError::Render(RenderError::NoAdapter)) = game.error().borrow().as_ref() {
        eprintln!("no GPU adapter available; skipping the capture");
        return;
    }
    if let Some(error) = game.error().borrow().as_ref() {
        panic!("the capture run failed: {error}");
    }
    result.expect("the scripted run completes");

    let stats = *game.stats().borrow();
    println!("fnp-capture: {}", stats.summary());
    println!(
        "fnp-capture: last frame drew {} meshes, {} bullets, {} point lights ({} over budget), \
         {} blob shadows",
        stats.last_stage.meshes_drawn,
        stats.last_stage.bullets_drawn,
        stats.last_stage.point_lights_drawn,
        stats.last_stage.point_lights_over_budget,
        stats.last_stage.blob_shadows_drawn
    );
    println!(
        "fnp-capture: {} frames rendered in {:.1} s wall time into {}",
        stats.frames,
        started.elapsed().as_secs_f64(),
        dir.display()
    );
    assert_eq!(stats.frames, FRAMES);
    assert!(
        stats.hits >= 1,
        "the scripted run includes a hit: {stats:?}"
    );
    assert!(stats.round >= 2, "and a restart: {stats:?}");
    assert!(stats.peak_bullets > 0);
}
