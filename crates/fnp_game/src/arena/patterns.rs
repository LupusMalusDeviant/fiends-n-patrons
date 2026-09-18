//! The game's Sigil patterns: which compiled unit a fiend plays and which of its emitters it
//! fires.
//!
//! One table for everyone: the arena's playable roster ([`super::Roster`]), the harness's scenes
//! and the reports all name the same patterns with the same emitters, so a pattern behaves the
//! same whether it is played, replayed or measured.
//!
//! Sub-emitters (`role = sub`) never appear here: they fire through a bullet's `become_emitter`
//! transform, never from the fiend (`summoner_bloom`'s `bloom`).

use fnp_content::sigil as content;
use grimoire::sigil::SigilUnit;

use super::ScenePattern;

/// A pattern of `content/sigil/`, with the emitters a fiend fires from it.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum GamePattern {
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

impl GamePattern {
    /// Every pattern the game has, in name order.
    pub const ALL: [GamePattern; 7] = [
        GamePattern::BreakerToll,
        GamePattern::HarrierScatter,
        GamePattern::ImpCurtain,
        GamePattern::ImpVolley,
        GamePattern::ShooterRails,
        GamePattern::SummonerBloom,
        GamePattern::SwarmWeave,
    ];

    /// The patterns a fiend fights with, in the order the prototype cycles them: the imp's own
    /// attack first, then the five role patterns from the lightest to the heaviest.
    ///
    /// The curtain is not in it: it is a stress mode, toggled on its own button.
    pub const FIGHT_ORDER: [GamePattern; 6] = [
        GamePattern::ImpVolley,
        GamePattern::SwarmWeave,
        GamePattern::ShooterRails,
        GamePattern::HarrierScatter,
        GamePattern::SummonerBloom,
        GamePattern::BreakerToll,
    ];

    /// The pattern's short name, as scenes, reports and the window title spell it.
    #[must_use]
    pub const fn name(self) -> &'static str {
        match self {
            GamePattern::BreakerToll => "breaker_toll",
            GamePattern::HarrierScatter => "harrier_scatter",
            GamePattern::ImpCurtain => "imp_curtain",
            GamePattern::ImpVolley => "imp_volley",
            GamePattern::ShooterRails => "shooter_rails",
            GamePattern::SummonerBloom => "summoner_bloom",
            GamePattern::SwarmWeave => "swarm_weave",
        }
    }

    /// The canonical content path the unit id derives from (contract §11.1).
    #[must_use]
    pub const fn content_path(self) -> &'static str {
        match self {
            GamePattern::BreakerToll => content::BREAKER_TOLL_PATH,
            GamePattern::HarrierScatter => content::HARRIER_SCATTER_PATH,
            GamePattern::ImpCurtain => content::IMP_CURTAIN_PATH,
            GamePattern::ImpVolley => content::IMP_VOLLEY_PATH,
            GamePattern::ShooterRails => content::SHOOTER_RAILS_PATH,
            GamePattern::SummonerBloom => content::SUMMONER_BLOOM_PATH,
            GamePattern::SwarmWeave => content::SWARM_WEAVE_PATH,
        }
    }

    /// Emitter indices of the unit a fiend fires, without sub-emitters.
    #[must_use]
    pub fn emitters(self) -> Vec<u16> {
        match self {
            GamePattern::BreakerToll => {
                vec![content::breaker_toll::NEEDLES, content::breaker_toll::TOLLS]
            }
            GamePattern::HarrierScatter => vec![
                content::harrier_scatter::REMINDER,
                content::harrier_scatter::SPRAY,
            ],
            GamePattern::ImpCurtain => {
                vec![content::imp_curtain::COUNTER, content::imp_curtain::CURTAIN]
            }
            GamePattern::ImpVolley => vec![
                content::imp_volley::AIMED,
                content::imp_volley::FAN,
                content::imp_volley::RING,
            ],
            GamePattern::ShooterRails => vec![
                content::shooter_rails::LANE,
                content::shooter_rails::LEFT_RAIL,
                content::shooter_rails::RIGHT_RAIL,
            ],
            GamePattern::SummonerBloom => vec![content::summoner_bloom::SEEDS],
            GamePattern::SwarmWeave => vec![
                content::swarm_weave::PASSES,
                content::swarm_weave::STRAGGLERS,
            ],
        }
    }

    /// The compiled unit of this pattern.
    ///
    /// # Panics
    /// If an embedded unit does not decode, which `fnp_content`'s own tests rule out for every
    /// build.
    #[must_use]
    pub fn unit(self) -> SigilUnit {
        let unit = match self {
            GamePattern::BreakerToll => content::breaker_toll(),
            GamePattern::HarrierScatter => content::harrier_scatter(),
            GamePattern::ImpCurtain => content::imp_curtain(),
            GamePattern::ImpVolley => content::imp_volley(),
            GamePattern::ShooterRails => content::shooter_rails(),
            GamePattern::SummonerBloom => content::summoner_bloom(),
            GamePattern::SwarmWeave => content::swarm_weave(),
        };
        unit.unwrap_or_else(|error| panic!("{} decodes: {error}", self.name()))
    }

    /// The compiled unit with the emitters a fiend fires from it.
    ///
    /// # Panics
    /// Like [`GamePattern::unit`].
    #[must_use]
    pub fn scene_pattern(self) -> ScenePattern {
        ScenePattern::new(self.unit(), self.emitters())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_pattern_fires_emitters_its_unit_has() {
        for pattern in GamePattern::ALL {
            let unit = pattern.unit();
            let emitters = pattern.emitters();
            assert!(!emitters.is_empty(), "{}", pattern.name());
            for emitter in &emitters {
                assert!(
                    *emitter < unit.emitter_count(),
                    "{} fires emitter {emitter} of {} emitters",
                    pattern.name(),
                    unit.emitter_count()
                );
            }
            let mut sorted = emitters.clone();
            sorted.sort_unstable();
            sorted.dedup();
            assert_eq!(sorted.len(), emitters.len(), "{}", pattern.name());
        }
    }

    #[test]
    fn the_summoners_sub_emitter_stays_out_of_the_fiends_hands() {
        // `bloom` only ever fires through a seed's `become_emitter` transform.
        let emitters = GamePattern::SummonerBloom.emitters();
        assert_eq!(emitters, vec![content::summoner_bloom::SEEDS]);
        assert!(!emitters.contains(&content::summoner_bloom::BLOOM));
    }

    #[test]
    fn the_fight_order_holds_every_pattern_but_the_curtain() {
        let mut fight = GamePattern::FIGHT_ORDER.to_vec();
        fight.sort_unstable();
        let mut all = GamePattern::ALL.to_vec();
        all.retain(|pattern| *pattern != GamePattern::ImpCurtain);
        assert_eq!(fight, all);
        assert_eq!(GamePattern::FIGHT_ORDER[0], GamePattern::ImpVolley);
    }

    #[test]
    fn every_pattern_has_its_own_unit_and_path() {
        let mut ids: Vec<_> = GamePattern::ALL.iter().map(|p| p.unit().id()).collect();
        ids.sort_unstable_by_key(|id| id.0);
        ids.dedup_by_key(|id| id.0);
        assert_eq!(ids.len(), GamePattern::ALL.len());
        for pattern in GamePattern::ALL {
            assert!(pattern.content_path().ends_with(".sigil"));
            assert!(pattern.content_path().contains(pattern.name()));
        }
    }
}
