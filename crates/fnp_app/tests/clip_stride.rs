//! Measures a figure's walk clip against the speed the player actually moves at: how far the
//! planted foot slides over the ground per second, before and after the stride warp.
//!
//! Needs a figure pack, so it is `#[ignore]`d and runs only on request:
//!
//! ```text
//! FNP_FIGURE_PACK=<figures.pack> GRIMOIRE_GPU_ADAPTER=software \
//!   cargo test -p fnp_app --test clip_stride -- --ignored --nocapture
//! ```
//!
//! Optional: `FNP_STRIDE_FIGURE=<name>` (default: the pack's player figure),
//! `FNP_STRIDE_SPEED=<m/s>` (default: the arena's top speed).

use std::path::PathBuf;

use std::time::Duration;

use fnp_app::figures::{FNP_ENEMY_FIGURE_VAR, FNP_PLAYER_FIGURE_VAR, resolve_figures};
use fnp_app::stage::{ArenaConfig, Figures, arena_app};
use fnp_game::TICK_RATE_HZ;
use fnp_game::arena::PLAYER_SPEED;
use fnp_game::arena::present::{FigureAnimation, WALK_CLIP_RATE_BOUNDS, foot_slip, walk_clip_rate};
use grimoire::HeadlessRenderAssets;
use grimoire::adapters::figure_assets::{load_clip, load_figure_into};
use grimoire::platform::StdFileSystem;
use grimoire::platform::{KeyCode, PlatformEvent, RawInputEvent};
use grimoire_assets::{AssetStore, PackReader};

#[test]
#[ignore = "needs a figure pack (FNP_FIGURE_PACK)"]
fn the_stride_warp_takes_the_slide_out_of_the_walk() {
    let Some(pack) = std::env::var_os("FNP_FIGURE_PACK") else {
        eprintln!("FNP_FIGURE_PACK not set; skipping the measurement");
        return;
    };
    let pack = PathBuf::from(pack);
    let figures = resolve_figures(
        &pack,
        fnp_app::cli::resolve_front(None, None).expect("a front"),
        std::env::var(FNP_PLAYER_FIGURE_VAR).ok().as_deref(),
        std::env::var(FNP_ENEMY_FIGURE_VAR).ok().as_deref(),
    )
    .expect("the pack has a player figure");
    let name = std::env::var("FNP_STRIDE_FIGURE").unwrap_or(figures.player.name.clone());
    let speed: f32 = std::env::var("FNP_STRIDE_SPEED")
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(PLAYER_SPEED);

    let reader = PackReader::open(&StdFileSystem, &pack).expect("the pack opens");
    let mut store = AssetStore::new(Box::new(reader));
    let mut assets = HeadlessRenderAssets::new();
    let figure = load_figure_into(&mut store, &mut assets, &name).expect("the figure loads");
    let idle = load_clip(&mut store, &name, "idle", &figure.skeleton).expect("idle loads");
    let walk = load_clip(&mut store, &name, "walk", &figure.skeleton).expect("walk loads");
    let animation = FigureAnimation {
        skeleton: figure.skeleton.clone(),
        idle,
        walk,
        walk_rate: 1.0,
    };

    let measured = walk_clip_rate(&animation, speed);
    let plain = foot_slip(&animation, speed, 1.0).expect("the walk clip has a moving foot");
    let warped = foot_slip(&animation, speed, measured).expect("the same, warped");

    println!(
        "clip `{name}` walk: {} frames at {} Hz, {:.3} s per cycle, {} joints animated",
        animation.walk.frame_count(),
        animation.walk.frame_rate_hz(),
        animation.walk.duration_seconds(),
        plain.moving_joints,
    );
    println!(
        "stride: foot travels {:.3} m per cycle, so the clip walks {:.3} m/s at rate 1.0",
        plain.stride_length, plain.clip_ground_speed
    );
    println!(
        "player speed {speed:.2} m/s -> stride rate {measured:.2} (bounds {:.2} to {:.2})",
        WALK_CLIP_RATE_BOUNDS.0, WALK_CLIP_RATE_BOUNDS.1
    );
    println!(
        "foot slip while planted: {:.3} m/s before, {:.3} m/s after ({:.0} % of the player's speed \
         before, {:.0} % after)",
        plain.slip,
        warped.slip,
        100.0 * plain.slip / speed,
        100.0 * warped.slip / speed
    );

    assert!(plain.stride_length > 0.05, "the walk clip moves a foot");
    assert!(
        warped.slip < plain.slip * 0.75,
        "the warp takes at least a quarter off the slide: {:.3} -> {:.3}",
        plain.slip,
        warped.slip
    );
    // How much slide is left is the clip's business: a stride that is too short for the speed
    // cannot be stretched past the rate bound without the legs whirring.
    let ideal = speed / plain.clip_ground_speed;
    if ideal > WALK_CLIP_RATE_BOUNDS.1 {
        println!(
            "note: the ground would need rate {ideal:.2}, above the bound {:.2}; {:.2} m of stride is short for {speed:.2} m/s",
            WALK_CLIP_RATE_BOUNDS.1, plain.stride_length
        );
    }
}

/// The same run twice: once with the pack's figures, clips and stride warp, once with the
/// placeholder figures that have no clips at all. Every state hash must be equal — animation is
/// presentation, and the stride warp cannot reach the simulation (engine ADR-0017).
#[test]
#[ignore = "needs a figure pack (FNP_FIGURE_PACK)"]
fn the_stride_warp_leaves_every_state_hash_alone() {
    let Some(pack) = std::env::var_os("FNP_FIGURE_PACK") else {
        eprintln!("FNP_FIGURE_PACK not set; skipping the replay comparison");
        return;
    };
    let pack = PathBuf::from(pack);
    let figures = resolve_figures(
        &pack,
        fnp_app::cli::resolve_front(None, None).expect("a front"),
        None,
        None,
    )
    .expect("the pack has a player figure");

    let frame = Duration::from_nanos(1_000_000_000 / u64::from(TICK_RATE_HZ));
    let script = |number: u64, events: &mut Vec<PlatformEvent>| {
        let keys: &[(KeyCode, bool)] = match number {
            0 => &[(KeyCode::KeyD, true)],
            40 => &[(KeyCode::KeyD, false), (KeyCode::KeyW, true)],
            90 => &[(KeyCode::KeyW, false)],
            150 => &[(KeyCode::KeyA, true)],
            210 => &[(KeyCode::KeyA, false)],
            _ => &[],
        };
        events.extend(keys.iter().map(|&(code, pressed)| {
            PlatformEvent::Input(RawInputEvent::Key {
                code,
                pressed,
                repeat: false,
            })
        }));
    };
    let run = |figures: Figures| {
        let (app, _stats) = arena_app(ArenaConfig {
            seed: 42,
            figures,
            max_frames: Some(300),
            camera_preset: 0,
        });
        app.hash_every(1)
            .run_headless_frames_with_events(10_000, frame, &mut |number, events| {
                script(number, events);
            })
            .expect("the run finishes")
    };

    let with_clips = run(Figures::Pack {
        path: pack,
        figures,
    });
    let without = run(Figures::Placeholder);
    assert!(with_clips.hashes.len() > 200, "a hash after every tick");
    assert_eq!(
        with_clips.hashes, without.hashes,
        "the figures' clips do not reach the simulation"
    );
    assert_eq!(with_clips.final_hash, without.final_hash);
    assert_eq!(with_clips.final_tick, without.final_tick);
}
