//! Fiends n Patrons — executable entry point.
//!
//! Opens the game window, loads the figure pack and runs the first playable prototype
//! ([`fnp_game::arena::ArenaGame`]) in the engine's main loop. `Escape` exits, `V` toggles the
//! imp's curtain mode, `F3` the engine's stats overlay; see [`cli::USAGE`] for arguments and
//! environment variables.

use std::process::ExitCode;

use fnp_app::cli::{self, Command, MAX_FRAMES_VAR, PACK_VAR, USAGE};
use fnp_app::stage::{ArenaConfig, Figures, arena_app};

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

    let (app, _stats) = arena_app(ArenaConfig {
        seed,
        figures: Figures::Pack(pack),
        max_frames,
    });
    match app.run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("fiends-n-patrons: {error}");
            ExitCode::FAILURE
        }
    }
}
