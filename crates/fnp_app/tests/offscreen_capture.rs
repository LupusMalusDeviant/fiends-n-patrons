//! Offscreen capture of a scripted run of the arena in the engine's main loop
//! ([`AppBuilder::run_offscreen`](grimoire::AppBuilder::run_offscreen)): moving, dodging, standing
//! still in the imp's aimed shots until one hits, the restart, then every pattern of the roster in
//! turn, and finally the curtain mode with about ten thousand bullets.
//!
//! Needs a figure pack and a GPU adapter, so it is `#[ignore]`d and runs only on request:
//!
//! ```text
//! FNP_FIGURE_PACK=<figures.pack> FNP_CAPTURE_DIR=<output dir> GRIMOIRE_GPU_ADAPTER=software \
//!   cargo test --release -p fnp_app --test offscreen_capture -- --ignored --nocapture
//! ```
//!
//! Optional: `FNP_CAPTURE_EVERY=<n>` keeps every n-th frame (default 2), `FNP_CAPTURE_SIZE=<w>x<h>`
//! (default 960x540), `FNP_CAPTURE_FRAMES=<n>` (default 1800), `FNP_CAPTURE_CAMERA=<0|1|2>`
//! (camera preset A, B or C, default A). Frames are written as binary PPM
//! (`frame_00000.ppm`, ...), which any image tool turns into a GIF or video; this crate
//! deliberately adds no image dependency for it.

use std::io::Write;
use std::path::PathBuf;
use std::time::{Duration, Instant};

use fnp_app::figures::{FNP_ENEMY_FIGURE_VAR, FNP_PLAYER_FIGURE_VAR, resolve_figures};
use fnp_app::stage::{ArenaConfig, CURTAIN_KEY, Figures, PATTERN_KEY, arena_app};
use fnp_game::TICK_RATE_HZ;
use grimoire::OffscreenRun;
use grimoire::platform::{KeyCode, PlatformEvent, RawInputEvent};
use grimoire::render::RenderError;

fn key(code: KeyCode, pressed: bool) -> PlatformEvent {
    PlatformEvent::Input(RawInputEvent::Key {
        code,
        pressed,
        repeat: false,
    })
}

/// Frames on which the script taps [`PATTERN_KEY`]: one per role pattern after the imp's volley.
const PATTERN_TAPS: [u64; 5] = [500, 700, 900, 1100, 1300];

/// Frame on which the script taps [`CURTAIN_KEY`].
const CURTAIN_TAP: u64 = 1500;

/// The scripted player: strafe right, back left, stand in the aimed shots until hit, walk around
/// after the restart, then one pattern of the roster after the other, and finally the curtain.
fn script(frame: u64, events: &mut Vec<PlatformEvent>) {
    let keys: &[(KeyCode, bool)] = match frame {
        0 => &[(KeyCode::KeyD, true)],
        40 => &[(KeyCode::KeyD, false), (KeyCode::KeyA, true)],
        95 => &[(KeyCode::KeyA, false)],
        300 => &[(KeyCode::KeyW, true), (KeyCode::KeyA, true)],
        340 => &[(KeyCode::KeyW, false)],
        380 => &[(KeyCode::KeyA, false), (KeyCode::KeyD, true)],
        450 => &[(KeyCode::KeyD, false), (KeyCode::KeyS, true)],
        470 => &[(KeyCode::KeyS, false)],
        // Between the pattern switches the soul keeps sidestepping, so every pattern is seen
        // against a moving target.
        560 => &[(KeyCode::KeyA, true)],
        620 => &[(KeyCode::KeyA, false), (KeyCode::KeyD, true)],
        680 => &[(KeyCode::KeyD, false)],
        760 => &[(KeyCode::KeyD, true)],
        820 => &[(KeyCode::KeyD, false), (KeyCode::KeyA, true)],
        880 => &[(KeyCode::KeyA, false)],
        960 => &[(KeyCode::KeyA, true)],
        1020 => &[(KeyCode::KeyA, false), (KeyCode::KeyD, true)],
        1080 => &[(KeyCode::KeyD, false)],
        1160 => &[(KeyCode::KeyD, true)],
        1220 => &[(KeyCode::KeyD, false), (KeyCode::KeyA, true)],
        1280 => &[(KeyCode::KeyA, false)],
        1360 => &[(KeyCode::KeyA, true)],
        1420 => &[(KeyCode::KeyA, false), (KeyCode::KeyD, true)],
        1480 => &[(KeyCode::KeyD, false)],
        _ => &[],
    };
    events.extend(keys.iter().map(|&(code, pressed)| key(code, pressed)));
    // Taps: pressed on the frame, released on the next one.
    for (code, frames) in [
        (PATTERN_KEY, PATTERN_TAPS.as_slice()),
        (CURTAIN_KEY, [CURTAIN_TAP].as_slice()),
    ] {
        if frames.contains(&frame) {
            events.push(key(code, true));
        }
        if frame > 0 && frames.contains(&(frame - 1)) {
            events.push(key(code, false));
        }
    }
}

fn write_ppm(path: &PathBuf, size: (u32, u32), rgba: &[u8]) -> std::io::Result<()> {
    let mut file = std::io::BufWriter::new(std::fs::File::create(path)?);
    write!(file, "P6\n{} {}\n255\n", size.0, size.1)?;
    for pixel in rgba.as_chunks::<4>().0 {
        file.write_all(&pixel[..3])?;
    }
    file.flush()
}

fn env_or<T: std::str::FromStr>(name: &str, default: T) -> T {
    std::env::var(name)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
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
    let dir = PathBuf::from(dir);
    std::fs::create_dir_all(&dir).expect("the capture directory can be created");
    let every: u64 = env_or("FNP_CAPTURE_EVERY", 2).max(1);
    let frames: u64 = env_or("FNP_CAPTURE_FRAMES", 1_800);
    let size = std::env::var("FNP_CAPTURE_SIZE")
        .ok()
        .and_then(|value| {
            let (w, h) = value.split_once('x')?;
            Some((w.parse().ok()?, h.parse().ok()?))
        })
        .unwrap_or((960, 540));

    let pack = PathBuf::from(pack);
    let front = fnp_app::cli::resolve_front(None, std::env::var_os(fnp_app::cli::FRONT_VAR))
        .expect("a valid figure front");
    let figures = resolve_figures(
        &pack,
        front,
        std::env::var(FNP_PLAYER_FIGURE_VAR).ok().as_deref(),
        std::env::var(FNP_ENEMY_FIGURE_VAR).ok().as_deref(),
    )
    .expect("the pack has a player and an enemy figure");
    println!(
        "fnp-capture: figures: player `{}`, enemy `{}`",
        figures.player.name, figures.enemy.name
    );
    let (app, stats) = arena_app(ArenaConfig {
        seed: 42,
        figures: Figures::Pack {
            path: pack,
            figures,
        },
        max_frames: None,
        camera_preset: env_or("FNP_CAPTURE_CAMERA", 0),
    });
    let frame_delta = Duration::from_nanos(1_000_000_000 / u64::from(TICK_RATE_HZ));
    let mut run = OffscreenRun::new(size.0, size.1, frames, frame_delta);
    run.capture_every = every;
    let started = Instant::now();
    let mut written = 0_u64;
    let mut write_error = None;
    let result = app.run_offscreen(run, &mut script, &mut |_, rgba| {
        let path = dir.join(format!("frame_{written:05}.ppm"));
        if let Err(error) = write_ppm(&path, size, rgba) {
            write_error.get_or_insert(error);
        }
        written += 1;
    });
    let report = match result {
        Ok(report) => report,
        Err(grimoire::GrimoireError::Render(RenderError::NoAdapter)) => {
            eprintln!("no GPU adapter available; skipping the capture");
            return;
        }
        Err(error) => panic!("the capture run failed: {error}"),
    };
    assert!(write_error.is_none(), "writing a frame: {write_error:?}");

    let stats = *stats.borrow();
    println!("fnp-capture: {}", stats.summary());
    println!(
        "fnp-capture: {} frames rendered, {written} images, in {:.1} s wall time into {}",
        report.frames,
        started.elapsed().as_secs_f64(),
        dir.display()
    );
    assert_eq!(report.frames, frames);
    assert!(
        stats.hits >= 1,
        "the scripted run includes a hit: {stats:?}"
    );
    assert!(stats.round >= 2, "and a restart: {stats:?}");
    if frames > CURTAIN_TAP {
        assert!(stats.curtain, "and ends in curtain mode: {stats:?}");
    }
    let switches = PATTERN_TAPS.iter().filter(|tap| **tap < frames).count()
        + usize::from(frames > CURTAIN_TAP);
    assert_eq!(
        usize::try_from(stats.pattern_switches).unwrap_or(usize::MAX),
        switches,
        "every scripted switch happened: {stats:?}"
    );
    // Every bullet went through the engine path, and nothing was discarded on the way.
    assert!(stats.bullets_drawn > 0);
    assert_eq!(stats.bullets_unmapped, 0, "{stats:?}");
    assert_eq!(stats.bullets_rejected_invalid, 0, "{stats:?}");
    assert_eq!(stats.bullets_rejected_palette_space, 0, "{stats:?}");
}
