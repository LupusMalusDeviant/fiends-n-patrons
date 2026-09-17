//! Fiends n Patrons — executable entry point.
//!
//! Opens the game window, loads the figure pack and runs the first playable prototype
//! ([`fnp_game::arena::ArenaGame`]). `Escape` exits; see [`cli::USAGE`] for arguments and
//! environment variables.

use std::process::ExitCode;
use std::time::Instant;

use fnp_app::cli::{self, Command, MAX_FRAMES_VAR, PACK_VAR, USAGE};
use fnp_app::figures::load_visuals;
use fnp_app::game_loop::{GameLoop, LoopConfig, LoopError};
use fnp_app::window_renderer;
use fnp_game::GAME_TITLE;
use grimoire::platform::{PlatformContext, WindowConfig, run_desktop};
use grimoire::render::Renderer;

/// Exit code for invalid arguments or environment (as in the BSD `sysexits` `EX_USAGE` spirit).
const EXIT_USAGE: u8 = 2;

fn usage_error(error: &cli::ConfigError) -> ExitCode {
    eprintln!("fiends-n-patrons: {error}\n\n{USAGE}");
    ExitCode::from(EXIT_USAGE)
}

fn main() -> ExitCode {
    let (seed, pack_argument) = match cli::parse_args(std::env::args_os().skip(1)) {
        Ok(Command::Run { seed, pack }) => (seed, pack),
        Ok(Command::Help) => {
            println!("{USAGE}");
            return ExitCode::SUCCESS;
        }
        Err(error) => return usage_error(&error),
    };
    let pack = match cli::resolve_pack(pack_argument, std::env::var_os(PACK_VAR)) {
        Ok(pack) => pack,
        Err(error) => return usage_error(&error),
    };
    if let Err(error) = cli::check_pack_exists(&pack) {
        return usage_error(&error);
    }
    let max_frames = match cli::parse_max_frames(std::env::var_os(MAX_FRAMES_VAR)) {
        Ok(max_frames) => max_frames,
        Err(error) => return usage_error(&error),
    };

    let factory = Box::new(move |ctx: &mut dyn PlatformContext| {
        let window = ctx.window().ok_or(LoopError::NoWindow)?;
        let mut renderer = window_renderer(&window)?;
        eprintln!("fiends-n-patrons: renderer {}", renderer.backend_name());
        let started = Instant::now();
        let (visuals, summary) = load_visuals(&mut renderer, &pack)?;
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
        Ok((renderer, visuals))
    });
    let game = GameLoop::new(LoopConfig { seed, max_frames }, factory);
    let error = game.error();
    let window = WindowConfig {
        title: String::from(GAME_TITLE),
        ..WindowConfig::default()
    };
    let result = run_desktop(window, game);
    if let Some(error) = error.borrow_mut().take() {
        eprintln!("fiends-n-patrons: {error}");
        return ExitCode::FAILURE;
    }
    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("fiends-n-patrons: {error}");
            ExitCode::FAILURE
        }
    }
}
