//! Scenes: what the harness runs (Plan 0002 WP7.4).
//!
//! A scene is a seed, a set of the game's own patterns and a bot profile — nothing else. Two runs
//! of the same scene are the same run, on every machine and every thread count, because every part
//! of it is a pure function of seed and tick (contract §3).

use fnp_game::arena::ScenePattern;
use fnp_game::arena::patterns::GamePattern;
use grimoire::prelude::*;

/// Axis value of a fully deflected stick.
const FULL: i16 = i16::MAX;

/// How long the dodger holds one direction, in ticks (a quarter second at 60 Hz).
pub const DODGE_HOLD_TICKS: u64 = 15;

/// A pattern of the game's content (`content/sigil/`), as a scene refers to it.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Pattern {
    /// `breaker_toll.sigil`: a heavy ring that reverses once, with mirrored flanking fans.
    BreakerToll,
    /// `harrier_scatter.sigil`: a seeded spray that never ends.
    HarrierScatter,
    /// `imp_curtain.sigil`: the curtain stress mode, about ten thousand bullets.
    ImpCurtain,
    /// `imp_volley.sigil`: the imp's aimed attack.
    ImpVolley,
    /// `shooter_rails.sigil`: two rails with a lane between them.
    ShooterRails,
    /// `summoner_bloom.sigil`: the cascade — seeds become emitters.
    SummonerBloom,
    /// `swarm_weave.sigil`: eight bending wave fronts.
    SwarmWeave,
}

impl Pattern {
    /// Every pattern the game has, in name order.
    pub const ALL: [Pattern; 7] = [
        Pattern::BreakerToll,
        Pattern::HarrierScatter,
        Pattern::ImpCurtain,
        Pattern::ImpVolley,
        Pattern::ShooterRails,
        Pattern::SummonerBloom,
        Pattern::SwarmWeave,
    ];

    /// The pattern's short name, as a scene and a report spell it.
    #[must_use]
    pub const fn name(self) -> &'static str {
        self.game_pattern().name()
    }

    /// The pattern of the game's own table this scene pattern names.
    #[must_use]
    pub const fn game_pattern(self) -> GamePattern {
        match self {
            Pattern::BreakerToll => GamePattern::BreakerToll,
            Pattern::HarrierScatter => GamePattern::HarrierScatter,
            Pattern::ImpCurtain => GamePattern::ImpCurtain,
            Pattern::ImpVolley => GamePattern::ImpVolley,
            Pattern::ShooterRails => GamePattern::ShooterRails,
            Pattern::SummonerBloom => GamePattern::SummonerBloom,
            Pattern::SwarmWeave => GamePattern::SwarmWeave,
        }
    }

    /// The canonical content path the unit id derives from (contract §11.1).
    #[must_use]
    pub const fn content_path(self) -> &'static str {
        self.game_pattern().content_path()
    }

    /// The compiled unit with the emitters a fiend fires from it, from the game's own table
    /// ([`GamePattern`]), so a scene plays exactly what the game plays.
    ///
    /// # Panics
    /// If an embedded unit does not decode, which `fnp_content`'s own tests rule out for every
    /// build.
    #[must_use]
    pub fn scene_pattern(self) -> ScenePattern {
        self.game_pattern().scene_pattern()
    }
}

/// How the player proxy moves during a scene.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum BotProfile {
    /// Stands still the whole run: the pattern alone decides what happens.
    Idle,
    /// Seeded random dodging over the two stick axes, a new direction every
    /// [`DODGE_HOLD_TICKS`] ticks.
    Dodger,
}

impl BotProfile {
    /// The profile's name, as a scene and a report spell it.
    #[must_use]
    pub const fn name(self) -> &'static str {
        match self {
            BotProfile::Idle => "idle",
            BotProfile::Dodger => "dodger",
        }
    }

    /// The input for `tick` of a run with `seed`: a pure function, with no state and no clock.
    #[must_use]
    pub fn input(self, seed: u64, tick: u64) -> TickInput {
        let mut input = TickInput::default();
        if self == BotProfile::Idle {
            return input;
        }
        // One draw per hold window, so the proxy moves in straight bursts instead of trembling.
        let bits = mix(seed ^ 0x646f_6467_6572_5f30, tick / DODGE_HOLD_TICKS);
        let slot = &mut input.slots[0];
        slot.axes[0] = axis(bits);
        slot.axes[1] = axis(bits >> 21);
        input
    }
}

/// One stick axis from 21 bits of a draw: full one way, full the other, or centred.
fn axis(bits: u64) -> i16 {
    match bits % 3 {
        0 => -FULL,
        1 => 0,
        _ => FULL,
    }
}

/// SplitMix64 over the two inputs: the same mixer the engine's stable hasher finishes with, used
/// here only to turn (seed, window) into bits. Integer arithmetic, no floats, no clock.
fn mix(seed: u64, window: u64) -> u64 {
    let mut z = seed
        .wrapping_add(window.wrapping_mul(0x9e37_79b9_7f4a_7c15))
        .wrapping_add(0x9e37_79b9_7f4a_7c15);
    z = (z ^ (z >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    z ^ (z >> 31)
}

/// A scene: seed, pattern set, bot profile, length.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Scene {
    /// Name in reports and on the command line.
    pub name: &'static str,
    /// Simulation seed.
    pub seed: u64,
    /// How many ticks to run.
    pub ticks: u64,
    /// Patterns the fiend plays, all from tick 0.
    pub patterns: &'static [Pattern],
    /// How the player proxy moves.
    pub bot: BotProfile,
}

impl Scene {
    /// The scene's patterns as the arena plugin takes them.
    #[must_use]
    pub fn scene_patterns(&self) -> Vec<ScenePattern> {
        self.patterns
            .iter()
            .map(|pattern| pattern.scene_pattern())
            .collect()
    }

    /// The input function of this scene's bot.
    #[must_use]
    pub fn input(&self, tick: u64) -> TickInput {
        self.bot.input(self.seed, tick)
    }
}

/// The standard suite: every pattern of the game, plus the prototype's own fight and one scene
/// that plays all five role patterns at once.
///
/// Lengths are chosen so the whole suite stays far below the five minutes Plan 0002 WP7.4 allows:
/// the curtain scene is the expensive one (about ten thousand live bullets), the rest are cheap.
pub const STANDARD_SUITE: &[Scene] = &[
    Scene {
        name: "imp_arena",
        seed: 42,
        ticks: 1800,
        patterns: &[Pattern::ImpVolley],
        bot: BotProfile::Dodger,
    },
    Scene {
        name: "imp_curtain",
        seed: 42,
        ticks: 900,
        patterns: &[Pattern::ImpCurtain],
        bot: BotProfile::Idle,
    },
    Scene {
        name: "swarm_weave",
        seed: 7,
        ticks: 900,
        patterns: &[Pattern::SwarmWeave],
        bot: BotProfile::Dodger,
    },
    Scene {
        name: "shooter_rails",
        seed: 8,
        ticks: 900,
        patterns: &[Pattern::ShooterRails],
        bot: BotProfile::Dodger,
    },
    Scene {
        name: "harrier_scatter",
        seed: 9,
        ticks: 1800,
        patterns: &[Pattern::HarrierScatter],
        bot: BotProfile::Dodger,
    },
    Scene {
        name: "summoner_bloom",
        seed: 10,
        ticks: 900,
        patterns: &[Pattern::SummonerBloom],
        bot: BotProfile::Idle,
    },
    Scene {
        name: "breaker_toll",
        seed: 11,
        ticks: 1200,
        patterns: &[Pattern::BreakerToll],
        bot: BotProfile::Dodger,
    },
    Scene {
        name: "all_roles",
        seed: 12,
        ticks: 1200,
        patterns: &[
            Pattern::SwarmWeave,
            Pattern::ShooterRails,
            Pattern::HarrierScatter,
            Pattern::SummonerBloom,
            Pattern::BreakerToll,
        ],
        bot: BotProfile::Dodger,
    },
];

/// The scene of [`STANDARD_SUITE`] with that name.
#[must_use]
pub fn scene(name: &str) -> Option<&'static Scene> {
    STANDARD_SUITE.iter().find(|scene| scene.name == name)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_pattern_of_the_game_is_in_the_suite() {
        for pattern in Pattern::ALL {
            assert!(
                STANDARD_SUITE
                    .iter()
                    .any(|scene| scene.patterns.contains(&pattern)),
                "{} is in no scene",
                pattern.name()
            );
        }
    }

    #[test]
    fn scene_names_are_unique_and_findable() {
        let mut names: Vec<&str> = STANDARD_SUITE.iter().map(|scene| scene.name).collect();
        names.sort_unstable();
        let count = names.len();
        names.dedup();
        assert_eq!(names.len(), count);
        assert!(scene("imp_arena").is_some());
        assert!(scene("nothing_like_this").is_none());
    }

    #[test]
    fn the_dodger_is_a_pure_function_that_uses_both_axes() {
        let frames: Vec<TickInput> = (0..600)
            .map(|tick| BotProfile::Dodger.input(9, tick))
            .collect();
        for tick in [0, 1, 14, 15, 599, 10_000] {
            assert_eq!(
                BotProfile::Dodger.input(9, tick),
                BotProfile::Dodger.input(9, tick)
            );
        }
        // Both axes are used in both directions, and only the first slot ever moves.
        for axis in 0..2 {
            assert!(frames.iter().any(|f| f.slots[0].axes[axis] == FULL));
            assert!(frames.iter().any(|f| f.slots[0].axes[axis] == -FULL));
        }
        assert!(
            frames
                .iter()
                .all(|f| f.slots[1..] == [InputFrame::default(); 3])
        );
        // A direction is held for a whole window.
        for tick in 0..DODGE_HOLD_TICKS {
            assert_eq!(
                BotProfile::Dodger.input(9, tick),
                BotProfile::Dodger.input(9, 0)
            );
        }
        // Different seeds give different runs.
        assert!(
            (0..600).any(|tick| BotProfile::Dodger.input(9, tick)
                != BotProfile::Dodger.input(10, tick))
        );
    }

    #[test]
    fn the_idle_bot_never_presses_anything() {
        for tick in [0, 1, 599, 10_000] {
            assert_eq!(BotProfile::Idle.input(42, tick), TickInput::default());
        }
    }

    #[test]
    fn every_scene_pattern_decodes_with_primary_emitters_only() {
        for pattern in Pattern::ALL {
            let scene_pattern = pattern.scene_pattern();
            assert!(!scene_pattern.emitters.is_empty(), "{}", pattern.name());
            let count = scene_pattern.unit.emitter_count();
            for &emitter in &scene_pattern.emitters {
                assert!(emitter < count, "{}", pattern.name());
            }
        }
        // The summoner's bloom is a sub-emitter and must not be spawned from the fiend.
        let bloom = Pattern::SummonerBloom.scene_pattern();
        assert_eq!(
            bloom.emitters,
            vec![fnp_content::sigil::summoner_bloom::SEEDS]
        );
    }
}
