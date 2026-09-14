//! Fiends n Patrons — executable entry point.
//!
//! Opens the game window and runs the Grimoire main loop with the [`FiendsGame`] plugin.
//! `Escape` exits; see [`cli::USAGE`] for arguments and environment variables.

mod cli;

use std::process::ExitCode;

use fnp_game::{FiendsGame, GAME_TITLE};
use grimoire::prelude::*;

use cli::{Command, MAX_FRAMES_VAR, USAGE};

/// Exit code for invalid arguments or environment (as in the BSD `sysexits` `EX_USAGE` spirit).
const EXIT_USAGE: u8 = 2;

fn main() -> ExitCode {
    let seed = match cli::parse_args(std::env::args_os().skip(1)) {
        Ok(Command::Run { seed }) => seed,
        Ok(Command::Help) => {
            println!("{USAGE}");
            return ExitCode::SUCCESS;
        }
        Err(error) => {
            eprintln!("fiends-n-patrons: {error}\n\n{USAGE}");
            return ExitCode::from(EXIT_USAGE);
        }
    };
    let max_frames = match cli::parse_max_frames(std::env::var_os(MAX_FRAMES_VAR)) {
        Ok(max_frames) => max_frames,
        Err(error) => {
            eprintln!("fiends-n-patrons: {error}");
            return ExitCode::from(EXIT_USAGE);
        }
    };

    let mut app = App::new(WindowConfig {
        title: String::from(GAME_TITLE),
        ..WindowConfig::default()
    })
    .seed(seed)
    .exit_key(KeyCode::Escape)
    .plugin(FiendsGame::new());
    if let Some(frames) = max_frames {
        app = app.max_frames(frames);
    }

    match app.run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("fiends-n-patrons: {error}");
            ExitCode::FAILURE
        }
    }
}
