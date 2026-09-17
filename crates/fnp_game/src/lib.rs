//! # fnp_game
//!
//! Game states and run logic of Fiends n Patrons, built on the Grimoire facade.
//!
//! **Status:** first playable prototype. [`arena::ArenaGame`] is the game the executable runs: the
//! player soul in a lit arena, one imp firing a Sigil pattern, hits and round restarts
//! ([`arena`]). This crate root holds what every part of the game shares: the title, the tick rate
//! and the basic motion components.
//!
//! ## Determinism
//!
//! All simulation state lives in the world as `Clone + StableHash` components and resources. The
//! systems scale by the fixed tick length [`DT`], never by measured time, draw randomness only
//! through the engine's seeded streams, and use `dmath` instead of the platform float functions
//! (engine contract section 3, enforced by this crate's `clippy.toml`). Everything outside
//! `GamePlugin::build` is presentation and never feeds back into the simulation.

pub mod arena;

use grimoire::prelude::*;

/// Display title of the game.
pub const GAME_TITLE: &str = "Fiends n Patrons";

/// Simulation rate the game is tuned for.
///
/// Every runner that drives the game in real time must step at this rate: the systems scale by
/// [`DT`], so any other rate changes the game speed. Headless runs step a fixed number of ticks
/// and do not depend on the rate.
pub const TICK_RATE_HZ: u32 = 60;

/// Seconds per tick; simulation code scales by this constant, never by measured time.
pub const DT: f32 = 1.0 / TICK_RATE_HZ as f32;

/// Position after the most recent tick.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Position {
    /// World position.
    pub at: Vec2,
}
impl_stable_hash!(Position { at });

/// Position one tick earlier, the start point of render interpolation.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct PreviousPosition {
    /// World position before the most recent tick.
    pub at: Vec2,
}
impl_stable_hash!(PreviousPosition { at });

/// Velocity of an entity with momentum, in world units per second.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Velocity {
    /// Current velocity.
    pub value: Vec2,
}
impl_stable_hash!(Velocity { value });

/// Marker of the player entity.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Player;
impl_stable_hash!(Player {});

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_tick_length_matches_the_tick_rate() {
        assert_eq!(TICK_RATE_HZ, 60);
        assert!((DT * TICK_RATE_HZ as f32 - 1.0).abs() < 1.0e-6);
    }
}
