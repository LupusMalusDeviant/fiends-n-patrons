//! Command line and environment configuration of the executable.

use std::ffi::OsString;
use std::fmt;

/// Seed used when `--seed` is not given; runs without a seed stay reproducible.
pub const DEFAULT_SEED: u64 = 0;

/// Environment variable that ends the run after the given number of frames.
pub const MAX_FRAMES_VAR: &str = "GRIMOIRE_EXAMPLE_MAX_FRAMES";

/// Usage text printed by `--help` and after argument errors.
pub const USAGE: &str = "\
Usage: fiends-n-patrons [--seed <u64>]

Options:
  --seed <u64>  Simulation seed (default 0)
  -h, --help    Print this help

Environment:
  GRIMOIRE_EXAMPLE_MAX_FRAMES=<u64>  End the run after this many frames";

/// What the command line asks for.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Command {
    /// Start the game.
    Run {
        /// Simulation seed.
        seed: u64,
    },
    /// Print the usage text and exit successfully.
    Help,
}

/// Invalid command line or environment.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ConfigError {
    /// `--seed` was the last argument.
    MissingSeedValue,
    /// The value of `--seed` is not an unsigned 64-bit integer.
    InvalidSeed(String),
    /// `--seed` was given more than once.
    DuplicateSeed,
    /// An argument the executable does not know.
    UnknownArgument(String),
    /// The frame limit variable is set but not an unsigned 64-bit integer.
    InvalidMaxFrames(String),
}

impl fmt::Display for ConfigError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::MissingSeedValue => write!(f, "--seed needs a value"),
            Self::InvalidSeed(value) => write!(
                f,
                "invalid seed {value:?}: expected an unsigned 64-bit integer (0 to {})",
                u64::MAX
            ),
            Self::DuplicateSeed => write!(f, "--seed was given more than once"),
            Self::UnknownArgument(argument) => write!(f, "unknown argument {argument:?}"),
            Self::InvalidMaxFrames(value) => write!(
                f,
                "invalid {MAX_FRAMES_VAR} {value:?}: expected an unsigned 64-bit integer"
            ),
        }
    }
}

impl std::error::Error for ConfigError {}

/// Parses the arguments after the program name.
///
/// # Errors
/// A [`ConfigError`] describing the first invalid argument.
pub fn parse_args(args: impl IntoIterator<Item = OsString>) -> Result<Command, ConfigError> {
    let mut seed = None;
    let mut args = args.into_iter();
    while let Some(argument) = args.next() {
        let Some(text) = argument.to_str() else {
            return Err(ConfigError::UnknownArgument(
                argument.to_string_lossy().into_owned(),
            ));
        };
        let value = match text {
            "-h" | "--help" => return Ok(Command::Help),
            "--seed" => args.next().ok_or(ConfigError::MissingSeedValue)?,
            _ => match text.strip_prefix("--seed=") {
                Some(value) => OsString::from(value),
                None => return Err(ConfigError::UnknownArgument(text.to_owned())),
            },
        };
        if seed.is_some() {
            return Err(ConfigError::DuplicateSeed);
        }
        seed = Some(parse_seed(&value)?);
    }
    Ok(Command::Run {
        seed: seed.unwrap_or(DEFAULT_SEED),
    })
}

fn parse_seed(value: &OsString) -> Result<u64, ConfigError> {
    value
        .to_str()
        .and_then(|text| text.parse().ok())
        .ok_or_else(|| ConfigError::InvalidSeed(value.to_string_lossy().into_owned()))
}

/// Interprets the value of [`MAX_FRAMES_VAR`]; `None` when the variable is not set.
///
/// # Errors
/// [`ConfigError::InvalidMaxFrames`] if the value is set but not an unsigned 64-bit integer.
pub fn parse_max_frames(value: Option<OsString>) -> Result<Option<u64>, ConfigError> {
    let Some(value) = value else {
        return Ok(None);
    };
    value
        .to_str()
        .and_then(|text| text.parse().ok())
        .map(Some)
        .ok_or_else(|| ConfigError::InvalidMaxFrames(value.to_string_lossy().into_owned()))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn args(list: &[&str]) -> Vec<OsString> {
        list.iter().map(OsString::from).collect()
    }

    #[test]
    fn no_arguments_use_the_default_seed() {
        assert_eq!(
            parse_args(args(&[])),
            Ok(Command::Run { seed: DEFAULT_SEED })
        );
    }

    #[test]
    fn seed_is_accepted_as_separate_or_joined_value() {
        assert_eq!(
            parse_args(args(&["--seed", "42"])),
            Ok(Command::Run { seed: 42 })
        );
        assert_eq!(
            parse_args(args(&["--seed=18446744073709551615"])),
            Ok(Command::Run { seed: u64::MAX })
        );
    }

    #[test]
    fn invalid_seeds_are_rejected() {
        for bad in ["-1", "abc", "", "18446744073709551616", "4.2", " 42"] {
            assert_eq!(
                parse_args(args(&["--seed", bad])),
                Err(ConfigError::InvalidSeed(bad.to_owned())),
                "{bad:?}"
            );
        }
        assert_eq!(
            parse_args(args(&["--seed"])),
            Err(ConfigError::MissingSeedValue)
        );
        assert_eq!(
            parse_args(args(&["--seed", "1", "--seed=2"])),
            Err(ConfigError::DuplicateSeed)
        );
    }

    #[test]
    fn unknown_arguments_are_rejected_and_help_wins() {
        assert_eq!(
            parse_args(args(&["--sed", "1"])),
            Err(ConfigError::UnknownArgument(String::from("--sed")))
        );
        assert_eq!(parse_args(args(&["--help", "--bogus"])), Ok(Command::Help));
        assert_eq!(parse_args(args(&["-h"])), Ok(Command::Help));
    }

    #[test]
    fn max_frames_is_optional_and_validated() {
        assert_eq!(parse_max_frames(None), Ok(None));
        assert_eq!(parse_max_frames(Some(OsString::from("120"))), Ok(Some(120)));
        assert_eq!(parse_max_frames(Some(OsString::from("0"))), Ok(Some(0)));
        assert_eq!(
            parse_max_frames(Some(OsString::from("ten"))),
            Err(ConfigError::InvalidMaxFrames(String::from("ten")))
        );
    }

    #[test]
    fn errors_read_clearly() {
        let message = ConfigError::InvalidSeed(String::from("abc")).to_string();
        assert!(message.contains("\"abc\"") && message.contains("unsigned 64-bit"));
        assert!(
            ConfigError::InvalidMaxFrames(String::from("x"))
                .to_string()
                .contains(MAX_FRAMES_VAR)
        );
    }
}
