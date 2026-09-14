//! Fiends n Patrons — executable entry point.
//!
//! Opens the game window and runs the Grimoire main loop with the [`FiendsGame`] plugin.
//! `Escape` exits; see [`cli::USAGE`] for arguments and environment variables.

mod cli;

use std::process::ExitCode;

use fnp_game::{FiendsGame, GAME_TITLE, TICK_RATE_HZ};
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

    match app(seed, max_frames).run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("fiends-n-patrons: {error}");
            ExitCode::FAILURE
        }
    }
}

/// Configures the game application; `run` opens the window.
///
/// Sets the tick rate explicitly: the game scales its motion by `fnp_game::DT`, which is only
/// correct at [`TICK_RATE_HZ`], whatever the facade default is.
fn app(seed: u64, max_frames: Option<u64>) -> AppBuilder {
    let app = App::new(WindowConfig {
        title: String::from(GAME_TITLE),
        ..WindowConfig::default()
    })
    .seed(seed)
    .tick_rate(TICK_RATE_HZ)
    .exit_key(KeyCode::Escape)
    .plugin(FiendsGame::new());
    match max_frames {
        Some(frames) => app.max_frames(frames),
        None => app,
    }
}

#[cfg(test)]
mod tests {
    use std::time::Duration;

    use super::*;

    #[test]
    fn the_app_simulates_at_the_rate_the_game_is_tuned_for() {
        // One second of frames, each one tick long at the game's rate: the real main loop (no
        // window, null renderer) must simulate exactly TICK_RATE_HZ ticks.
        let hz = u64::from(TICK_RATE_HZ);
        let frame = Duration::from_nanos(1_000_000_000_u64.div_ceil(hz));
        let report = app(7, None)
            .run_headless_frames(hz, frame)
            .expect("headless frame loop runs");
        assert_eq!(report.frames, hz);
        assert_eq!(report.final_tick, hz);
        assert_eq!(report.dropped_time, Duration::ZERO);
    }
}
