//! Fiends n Patrons — executable entry point.
//!
//! Opens the game window, loads the figure pack and runs the first playable prototype
//! ([`fnp_game::arena::ArenaGame`]) in the engine's main loop. The default has
//! pursuing enemies and sparse shots; `FNP_ARENA_MODE=classic` opens the
//! original pattern showcase. See [`cli::USAGE`] for controls.
//!
//! The figure pack is resolved before the window opens: which figure plays the player and which
//! the enemy ([`fnp_app::figures::resolve_figures`]), so a pack without usable figures ends the
//! run with a message and [`EXIT_USAGE`].

use std::process::ExitCode;

use fnp_app::cli::{self, Command, FRONT_VAR, MAX_FRAMES_VAR, PACK_VAR, USAGE};
use fnp_app::figures::{FNP_ENEMY_FIGURE_VAR, FNP_PLAYER_FIGURE_VAR, FrontChoice, resolve_figures};
use fnp_app::stage::{ArenaConfig, Figures, arena_app, horde_app};
use fnp_game::arena::present::AuthoredFront;

/// Exit code for invalid arguments or environment (as in the BSD `sysexits` `EX_USAGE` spirit).
const EXIT_USAGE: u8 = 2;

fn usage_error(error: &cli::ConfigError) -> ExitCode {
    eprintln!("fiends-n-patrons: {error}\n\n{USAGE}");
    ExitCode::from(EXIT_USAGE)
}

fn main() -> ExitCode {
    let (seed, pack_argument, front_argument) = match cli::parse_args(std::env::args_os().skip(1)) {
        Ok(Command::Run { seed, pack, front }) => (seed, pack, front),
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
    let front = match cli::resolve_front(front_argument, std::env::var_os(FRONT_VAR)) {
        Ok(front) => front,
        Err(error) => return usage_error(&error),
    };

    // Before the window: a pack without a usable pair of figures must not open one.
    let player_figure = std::env::var(FNP_PLAYER_FIGURE_VAR).ok();
    let enemy_figure = std::env::var(FNP_ENEMY_FIGURE_VAR).ok();
    let figures = match resolve_figures(
        &pack,
        front,
        player_figure.as_deref(),
        enemy_figure.as_deref(),
    ) {
        Ok(figures) => figures,
        Err(error) => {
            eprintln!("fiends-n-patrons: {error}");
            return ExitCode::from(EXIT_USAGE);
        }
    };
    eprintln!(
        "fiends-n-patrons: figures: player `{}`, enemy `{}` (front: {})",
        figures.player.name,
        figures.enemy.name,
        match front {
            FrontChoice::Measure => "measured on each rig",
            FrontChoice::Fixed(AuthoredFront::PlusZ) => "+Z, set",
            FrontChoice::Fixed(AuthoredFront::MinusZ) => "-Z, set",
        }
    );

    let config = ArenaConfig {
        seed,
        figures: Figures::Pack {
            path: pack,
            figures,
        },
        max_frames,
        camera_preset: 0,
    };
    let (app, _stats) = if std::env::var("FNP_ARENA_MODE").as_deref() == Ok("classic") {
        arena_app(config)
    } else {
        horde_app(config)
    };
    match app.run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("fiends-n-patrons: {error}");
            ExitCode::FAILURE
        }
    }
}
