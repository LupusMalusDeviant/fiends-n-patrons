//! Command line and environment configuration of the executable.

use std::ffi::OsString;
use std::fmt;
use std::path::{Path, PathBuf};

/// Seed used when `--seed` is not given; runs without a seed stay reproducible.
pub const DEFAULT_SEED: u64 = 0;

/// Environment variable that ends the run after the given number of frames.
pub const MAX_FRAMES_VAR: &str = "GRIMOIRE_EXAMPLE_MAX_FRAMES";

/// Environment variable naming the figure pack when `--pack` is not given.
pub const PACK_VAR: &str = "FNP_FIGURE_PACK";

/// Usage text printed by `--help` and after argument errors.
pub const USAGE: &str = "\
Usage: fiends-n-patrons --pack <figures.pack> [--seed <u64>]

Options:
  --pack <path>  Figure pack with a player and an enemy figure (or set FNP_FIGURE_PACK):
                 `witch` and `imp_hi3d`, or the older `soul` and `imp`
  --seed <u64>   Simulation seed (default 0)
  -h, --help     Print this help

Controls:
  WASD or arrow keys  Move the player
  P                   Cycle the fiend's pattern: imp_volley, swarm_weave, shooter_rails,
                      harrier_scatter, summoner_bloom, breaker_toll
  V                   Toggle the curtain mode (about 10,000 bullets, the player invulnerable)
  C                   Cycle the camera presets A (60 deg, 14.5 m), B (52, 12.5), C (45, 11)
  F3                  Toggle the engine's stats overlay
  Escape              Quit

Environment:
  FNP_FIGURE_PACK=<path>             Figure pack, used when --pack is not given
  FNP_PLAYER_FIGURE=<name>           Player figure in the pack (append `:plusz` or `:minusz`
                                     to say which way its model looks)
  FNP_ENEMY_FIGURE=<name>            Enemy figure in the pack, same form
  GRIMOIRE_EXAMPLE_MAX_FRAMES=<u64>  End the run after this many frames";

/// What the command line asks for.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Command {
    /// Start the game.
    Run {
        /// Simulation seed.
        seed: u64,
        /// Figure pack given with `--pack`, if any.
        pack: Option<PathBuf>,
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
    /// `--pack` was the last argument or had an empty value.
    MissingPackValue,
    /// `--pack` was given more than once.
    DuplicatePack,
    /// An argument the executable does not know.
    UnknownArgument(String),
    /// The frame limit variable is set but not an unsigned 64-bit integer.
    InvalidMaxFrames(String),
    /// Neither `--pack` nor [`PACK_VAR`] names a figure pack.
    NoPack,
    /// The figure pack path does not name a file.
    PackNotFound(PathBuf),
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
            Self::MissingPackValue => write!(f, "--pack needs the path of a figure pack"),
            Self::DuplicatePack => write!(f, "--pack was given more than once"),
            Self::UnknownArgument(argument) => write!(f, "unknown argument {argument:?}"),
            Self::InvalidMaxFrames(value) => write!(
                f,
                "invalid {MAX_FRAMES_VAR} {value:?}: expected an unsigned 64-bit integer"
            ),
            Self::NoPack => write!(
                f,
                "no figure pack given: the game needs a figure pack with the figures `soul` and \
                 `imp`. Pass --pack <path to the .pack file> or set {PACK_VAR}=<path>"
            ),
            Self::PackNotFound(path) => write!(
                f,
                "figure pack {} does not exist or is not a file",
                path.display()
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
    let mut pack = None;
    let mut args = args.into_iter();
    while let Some(argument) = args.next() {
        let Some(text) = argument.to_str() else {
            return Err(ConfigError::UnknownArgument(
                argument.to_string_lossy().into_owned(),
            ));
        };
        match text {
            "-h" | "--help" => return Ok(Command::Help),
            "--seed" => {
                let value = args.next().ok_or(ConfigError::MissingSeedValue)?;
                set_seed(&mut seed, &value)?;
            }
            "--pack" => {
                let value = args.next().ok_or(ConfigError::MissingPackValue)?;
                set_pack(&mut pack, value)?;
            }
            _ => {
                if let Some(value) = text.strip_prefix("--seed=") {
                    set_seed(&mut seed, &OsString::from(value))?;
                } else if let Some(value) = text.strip_prefix("--pack=") {
                    set_pack(&mut pack, OsString::from(value))?;
                } else {
                    return Err(ConfigError::UnknownArgument(text.to_owned()));
                }
            }
        }
    }
    Ok(Command::Run {
        seed: seed.unwrap_or(DEFAULT_SEED),
        pack,
    })
}

fn set_seed(seed: &mut Option<u64>, value: &OsString) -> Result<(), ConfigError> {
    if seed.is_some() {
        return Err(ConfigError::DuplicateSeed);
    }
    *seed = Some(parse_seed(value)?);
    Ok(())
}

fn set_pack(pack: &mut Option<PathBuf>, value: OsString) -> Result<(), ConfigError> {
    if pack.is_some() {
        return Err(ConfigError::DuplicatePack);
    }
    if value.is_empty() {
        return Err(ConfigError::MissingPackValue);
    }
    *pack = Some(PathBuf::from(value));
    Ok(())
}

fn parse_seed(value: &OsString) -> Result<u64, ConfigError> {
    value
        .to_str()
        .and_then(|text| text.parse().ok())
        .ok_or_else(|| ConfigError::InvalidSeed(value.to_string_lossy().into_owned()))
}

/// The figure pack to load: `--pack` wins over [`PACK_VAR`]; an empty variable counts as unset.
///
/// # Errors
/// [`ConfigError::NoPack`] if neither names a pack.
pub fn resolve_pack(
    argument: Option<PathBuf>,
    environment: Option<OsString>,
) -> Result<PathBuf, ConfigError> {
    argument
        .or_else(|| {
            environment
                .filter(|value| !value.is_empty())
                .map(PathBuf::from)
        })
        .ok_or(ConfigError::NoPack)
}

/// Checks that `path` names an existing file, so a typo fails before a window opens.
///
/// # Errors
/// [`ConfigError::PackNotFound`] otherwise.
pub fn check_pack_exists(path: &Path) -> Result<(), ConfigError> {
    if path.is_file() {
        Ok(())
    } else {
        Err(ConfigError::PackNotFound(path.to_path_buf()))
    }
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

    fn run(seed: u64, pack: Option<&str>) -> Result<Command, ConfigError> {
        Ok(Command::Run {
            seed,
            pack: pack.map(PathBuf::from),
        })
    }

    #[test]
    fn no_arguments_use_the_default_seed_and_no_pack() {
        assert_eq!(parse_args(args(&[])), run(DEFAULT_SEED, None));
    }

    #[test]
    fn seed_is_accepted_as_separate_or_joined_value() {
        assert_eq!(parse_args(args(&["--seed", "42"])), run(42, None));
        assert_eq!(
            parse_args(args(&["--seed=18446744073709551615"])),
            run(u64::MAX, None)
        );
    }

    #[test]
    fn pack_is_accepted_as_separate_or_joined_value_next_to_the_seed() {
        assert_eq!(
            parse_args(args(&["--pack", "figures.pack", "--seed", "7"])),
            run(7, Some("figures.pack"))
        );
        assert_eq!(
            parse_args(args(&["--seed=3", "--pack=packs/figures r4.pack"])),
            run(3, Some("packs/figures r4.pack"))
        );
    }

    #[test]
    fn invalid_pack_arguments_are_rejected() {
        assert_eq!(
            parse_args(args(&["--pack"])),
            Err(ConfigError::MissingPackValue)
        );
        assert_eq!(
            parse_args(args(&["--pack="])),
            Err(ConfigError::MissingPackValue)
        );
        assert_eq!(
            parse_args(args(&["--pack", "a", "--pack=b"])),
            Err(ConfigError::DuplicatePack)
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
    fn the_pack_argument_wins_over_the_environment() {
        assert_eq!(
            resolve_pack(
                Some(PathBuf::from("a.pack")),
                Some(OsString::from("b.pack"))
            ),
            Ok(PathBuf::from("a.pack"))
        );
        assert_eq!(
            resolve_pack(None, Some(OsString::from("b.pack"))),
            Ok(PathBuf::from("b.pack"))
        );
        assert_eq!(
            resolve_pack(None, Some(OsString::new())),
            Err(ConfigError::NoPack)
        );
        assert_eq!(resolve_pack(None, None), Err(ConfigError::NoPack));
    }

    #[test]
    fn a_missing_pack_file_is_reported_with_its_path() {
        let path = Path::new("this/pack/does/not/exist.pack");
        let error = check_pack_exists(path).expect_err("no such file");
        assert_eq!(error, ConfigError::PackNotFound(path.to_path_buf()));
        assert!(error.to_string().contains("exist.pack"));
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
        let no_pack = ConfigError::NoPack.to_string();
        assert!(no_pack.contains("--pack") && no_pack.contains(PACK_VAR));
    }
}
