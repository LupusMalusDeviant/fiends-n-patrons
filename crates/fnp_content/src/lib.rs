//! # fnp_content
//!
//! Gameplay plugins of Fiends n Patrons (weapons, patrons, items, enemies). Content registers
//! itself through plugin traits and never modifies the core game or engine.
//!
//! **Status:** first playable prototype. [`sigil`] embeds the compiled Sigil units of the
//! enemies; the build script compiles `content/sigil/*.sigil` with the engine's compiler, so the
//! units always match the sources of the same commit.

pub mod sigil {
    //! Compiled Sigil units (contract §11.1) of the game's enemies.
    //!
    //! Every unit is compiled from `content/<canonical path>` by this crate's build script; its
    //! [`grimoire::sigil::UnitId`] derives from the canonical path, so it is the same on every
    //! platform and checkout. The compiler numbers emitters and bullet types in name order, not in
    //! declaration order; silhouettes and palettes are rows of the engine's shared visual catalogue
    //! (`docs/formats/sigil.md` §10.10 of the engine), which the tests below hold to the rows the
    //! bullet pass draws.

    use grimoire::sigil::{SigilUnit, UnitError};

    /// Canonical content path of the imp's normal attack (relative to `content/`).
    pub const IMP_VOLLEY_PATH: &str = "sigil/imp_volley.sigil";

    /// Compiled bytes of [`IMP_VOLLEY_PATH`].
    pub const IMP_VOLLEY_BYTES: &[u8] =
        include_bytes!(concat!(env!("OUT_DIR"), "/imp_volley.unit"));

    /// Canonical content path of the imp's curtain mode (relative to `content/`).
    pub const IMP_CURTAIN_PATH: &str = "sigil/imp_curtain.sigil";

    /// Compiled bytes of [`IMP_CURTAIN_PATH`].
    pub const IMP_CURTAIN_BYTES: &[u8] =
        include_bytes!(concat!(env!("OUT_DIR"), "/imp_curtain.unit"));

    /// Canonical content path of the breaker's returning toll (relative to `content/`).
    pub const BREAKER_TOLL_PATH: &str = "sigil/breaker_toll.sigil";

    /// Compiled bytes of [`BREAKER_TOLL_PATH`].
    pub const BREAKER_TOLL_BYTES: &[u8] =
        include_bytes!(concat!(env!("OUT_DIR"), "/breaker_toll.unit"));

    /// Canonical content path of the harrier's seeded spray (relative to `content/`).
    pub const HARRIER_SCATTER_PATH: &str = "sigil/harrier_scatter.sigil";

    /// Compiled bytes of [`HARRIER_SCATTER_PATH`].
    pub const HARRIER_SCATTER_BYTES: &[u8] =
        include_bytes!(concat!(env!("OUT_DIR"), "/harrier_scatter.unit"));

    /// Canonical content path of the second shooter's rails (relative to `content/`).
    pub const SHOOTER_RAILS_PATH: &str = "sigil/shooter_rails.sigil";

    /// Compiled bytes of [`SHOOTER_RAILS_PATH`].
    pub const SHOOTER_RAILS_BYTES: &[u8] =
        include_bytes!(concat!(env!("OUT_DIR"), "/shooter_rails.unit"));

    /// Canonical content path of the summoner's cascade (relative to `content/`).
    pub const SUMMONER_BLOOM_PATH: &str = "sigil/summoner_bloom.sigil";

    /// Compiled bytes of [`SUMMONER_BLOOM_PATH`].
    pub const SUMMONER_BLOOM_BYTES: &[u8] =
        include_bytes!(concat!(env!("OUT_DIR"), "/summoner_bloom.unit"));

    /// Canonical content path of the swarmers' wave (relative to `content/`).
    pub const SWARM_WEAVE_PATH: &str = "sigil/swarm_weave.sigil";

    /// Compiled bytes of [`SWARM_WEAVE_PATH`].
    pub const SWARM_WEAVE_BYTES: &[u8] =
        include_bytes!(concat!(env!("OUT_DIR"), "/swarm_weave.unit"));

    /// Indices inside the unit compiled from [`IMP_VOLLEY_PATH`].
    pub mod imp_volley {
        /// `emitter aimed`: five darts aimed at the player.
        pub const AIMED: u16 = 0;
        /// `emitter fan`: nine weaving orbs fanned downwards.
        pub const FAN: u16 = 1;
        /// `emitter ring`: an accelerating ring of 24 grains.
        pub const RING: u16 = 2;
        /// Number of emitters in the unit.
        pub const EMITTER_COUNT: u16 = 3;
        /// Bullet type `dart` (diamond, hex magenta).
        pub const DART: u16 = 0;
        /// Bullet type `grain` (rice, hex magenta).
        pub const GRAIN: u16 = 1;
        /// Bullet type `orb` (orb, poison lime).
        pub const ORB: u16 = 2;
    }

    /// Indices inside the unit compiled from [`IMP_CURTAIN_PATH`].
    pub mod imp_curtain {
        /// `emitter counter`: 12 arms of orbs every tick, turning the other way.
        pub const COUNTER: u16 = 0;
        /// `emitter curtain`: 24 arms of rice grains every tick.
        pub const CURTAIN: u16 = 1;
        /// Number of emitters in the unit.
        pub const EMITTER_COUNT: u16 = 2;
    }

    /// Indices inside the unit compiled from [`BREAKER_TOLL_PATH`].
    ///
    /// The compiler numbers by name, so the order here is not the order in the source.
    pub mod breaker_toll {
        /// `emitter needles`: a mirrored pair of fans on the flanks.
        pub const NEEDLES: u16 = 0;
        /// `emitter tolls`: a ring of 14 heavy bullets that returns once.
        pub const TOLLS: u16 = 1;
        /// Number of emitters in the unit.
        pub const EMITTER_COUNT: u16 = 2;
        /// Bullet type `needle` (diamond, poison lime).
        pub const NEEDLE: u16 = 0;
        /// Bullet type `toll` (orb, hex magenta), reversed after 70 ticks.
        pub const TOLL: u16 = 1;
    }

    /// Indices inside the unit compiled from [`HARRIER_SCATTER_PATH`].
    pub mod harrier_scatter {
        /// `emitter reminder`: a slow ring every two seconds.
        pub const REMINDER: u16 = 0;
        /// `emitter spray`: six seeded grains every nine ticks, without end.
        pub const SPRAY: u16 = 1;
        /// Number of emitters in the unit.
        pub const EMITTER_COUNT: u16 = 2;
        /// Bullet type `grain` (rice, poison lime).
        pub const GRAIN: u16 = 0;
        /// Bullet type `warning` (orb, hex magenta), smashable.
        pub const WARNING: u16 = 1;
    }

    /// Indices inside the unit compiled from [`SHOOTER_RAILS_PATH`].
    pub mod shooter_rails {
        /// `emitter lane`: three darts down the lane between the rails.
        pub const LANE: u16 = 0;
        /// `emitter left_rail`: seven spikes from the left flank.
        pub const LEFT_RAIL: u16 = 1;
        /// `emitter right_rail`: the mirrored rail on the right flank.
        pub const RIGHT_RAIL: u16 = 2;
        /// Number of emitters in the unit.
        pub const EMITTER_COUNT: u16 = 3;
        /// Bullet type `dart` (diamond, poison lime).
        pub const DART: u16 = 0;
        /// Bullet type `spike` (rice, hex magenta).
        pub const SPIKE: u16 = 1;
    }

    /// Indices inside the unit compiled from [`SUMMONER_BLOOM_PATH`].
    ///
    /// `BLOOM` is a sub-emitter (`role = sub`): it never fires on its own, only through a seed's
    /// `become_emitter` transform, so a scene spawns [`SEEDS`] alone.
    pub mod summoner_bloom {
        /// `emitter bloom`: the fan a seed fires when it opens; sub-emitter.
        pub const BLOOM: u16 = 0;
        /// `emitter seeds`: three volleys of five seeds.
        pub const SEEDS: u16 = 1;
        /// Number of emitters in the unit, the sub-emitter included.
        pub const EMITTER_COUNT: u16 = 2;
        /// Bullet type `seed` (orb, hex magenta), smashable, becomes [`BLOOM`].
        pub const SEED: u16 = 0;
        /// Bullet type `shard` (rice, poison lime), becomes [`SPARK`] after 3u.
        pub const SHARD: u16 = 1;
        /// Bullet type `spark` (diamond, poison lime).
        pub const SPARK: u16 = 2;
    }

    /// Indices inside the unit compiled from [`SWARM_WEAVE_PATH`].
    pub mod swarm_weave {
        /// `emitter passes`: eight bending wave fronts of eleven motes.
        pub const PASSES: u16 = 0;
        /// `emitter stragglers`: the accelerating fan behind every pass.
        pub const STRAGGLERS: u16 = 1;
        /// Number of emitters in the unit.
        pub const EMITTER_COUNT: u16 = 2;
        /// Bullet type `mote` (rice, poison lime).
        pub const MOTE: u16 = 0;
        /// Bullet type `straggler` (orb, hex magenta).
        pub const STRAGGLER: u16 = 1;
    }

    /// Decodes [`IMP_VOLLEY_BYTES`].
    ///
    /// # Errors
    /// A [`UnitError`] if the embedded bytes do not decode, which the tests below rule out for
    /// every build.
    pub fn imp_volley() -> Result<SigilUnit, UnitError> {
        SigilUnit::from_bytes(IMP_VOLLEY_BYTES)
    }

    /// Decodes [`IMP_CURTAIN_BYTES`].
    ///
    /// # Errors
    /// A [`UnitError`] if the embedded bytes do not decode, which the tests below rule out for
    /// every build.
    pub fn imp_curtain() -> Result<SigilUnit, UnitError> {
        SigilUnit::from_bytes(IMP_CURTAIN_BYTES)
    }

    /// Decodes [`BREAKER_TOLL_BYTES`] (the breaker's returning toll).
    ///
    /// # Errors
    /// A [`UnitError`] if the embedded bytes do not decode, which the tests below rule out for
    /// every build.
    pub fn breaker_toll() -> Result<SigilUnit, UnitError> {
        SigilUnit::from_bytes(BREAKER_TOLL_BYTES)
    }

    /// Decodes [`HARRIER_SCATTER_BYTES`] (the harrier's seeded spray).
    ///
    /// # Errors
    /// A [`UnitError`] if the embedded bytes do not decode, which the tests below rule out for
    /// every build.
    pub fn harrier_scatter() -> Result<SigilUnit, UnitError> {
        SigilUnit::from_bytes(HARRIER_SCATTER_BYTES)
    }

    /// Decodes [`SHOOTER_RAILS_BYTES`] (the second shooter's rails).
    ///
    /// # Errors
    /// A [`UnitError`] if the embedded bytes do not decode, which the tests below rule out for
    /// every build.
    pub fn shooter_rails() -> Result<SigilUnit, UnitError> {
        SigilUnit::from_bytes(SHOOTER_RAILS_BYTES)
    }

    /// Decodes [`SUMMONER_BLOOM_BYTES`] (the summoner's cascade).
    ///
    /// # Errors
    /// A [`UnitError`] if the embedded bytes do not decode, which the tests below rule out for
    /// every build.
    pub fn summoner_bloom() -> Result<SigilUnit, UnitError> {
        SigilUnit::from_bytes(SUMMONER_BLOOM_BYTES)
    }

    /// Decodes [`SWARM_WEAVE_BYTES`] (the swarmers' wave).
    ///
    /// # Errors
    /// A [`UnitError`] if the embedded bytes do not decode, which the tests below rule out for
    /// every build.
    pub fn swarm_weave() -> Result<SigilUnit, UnitError> {
        SigilUnit::from_bytes(SWARM_WEAVE_BYTES)
    }

    #[cfg(test)]
    mod tests {
        use grimoire::adapters::sigil_render::map_visual;
        use grimoire::render::{bullet_palette, bullet_silhouette, palette_space};
        use grimoire::sigil::BulletFlags;

        use super::*;

        /// Every embedded unit with its bytes and the emitter count its index module promises.
        fn units() -> [(&'static str, SigilUnit, &'static [u8], u16); 7] {
            [
                (
                    BREAKER_TOLL_PATH,
                    breaker_toll().expect("breaker_toll decodes"),
                    BREAKER_TOLL_BYTES,
                    breaker_toll::EMITTER_COUNT,
                ),
                (
                    HARRIER_SCATTER_PATH,
                    harrier_scatter().expect("harrier_scatter decodes"),
                    HARRIER_SCATTER_BYTES,
                    harrier_scatter::EMITTER_COUNT,
                ),
                (
                    IMP_CURTAIN_PATH,
                    imp_curtain().expect("imp_curtain decodes"),
                    IMP_CURTAIN_BYTES,
                    imp_curtain::EMITTER_COUNT,
                ),
                (
                    IMP_VOLLEY_PATH,
                    imp_volley().expect("imp_volley decodes"),
                    IMP_VOLLEY_BYTES,
                    imp_volley::EMITTER_COUNT,
                ),
                (
                    SHOOTER_RAILS_PATH,
                    shooter_rails().expect("shooter_rails decodes"),
                    SHOOTER_RAILS_BYTES,
                    shooter_rails::EMITTER_COUNT,
                ),
                (
                    SUMMONER_BLOOM_PATH,
                    summoner_bloom().expect("summoner_bloom decodes"),
                    SUMMONER_BLOOM_BYTES,
                    summoner_bloom::EMITTER_COUNT,
                ),
                (
                    SWARM_WEAVE_PATH,
                    swarm_weave().expect("swarm_weave decodes"),
                    SWARM_WEAVE_BYTES,
                    swarm_weave::EMITTER_COUNT,
                ),
            ]
        }

        #[test]
        fn every_unit_decodes_canonically_with_the_emitters_its_module_promises() {
            let mut ids = Vec::new();
            for (path, unit, bytes, emitter_count) in units() {
                assert_eq!(unit.emitter_count(), emitter_count, "{path}");
                assert_ne!(unit.id().0, 0, "{path}");
                assert!(unit.behavior_refs().is_empty(), "{path}");
                // Canonical encoding: decoding and re-encoding gives the same bytes (§11.1).
                assert_eq!(unit.to_bytes(), bytes, "{path}");
                ids.push(unit.id());
            }
            // The id derives from the canonical content path, so different patterns differ.
            let unique: std::collections::BTreeSet<_> = ids.iter().copied().collect();
            assert_eq!(unique.len(), ids.len());
        }

        #[test]
        fn the_content_covers_what_the_prototype_needs() {
            // Plan 0002 WP7.3: at least six game patterns, with an aimed one and a cascade.
            assert!(units().len() >= 6);
            let volley = imp_volley().expect("imp_volley decodes");
            assert_eq!(volley.emitter_count(), imp_volley::EMITTER_COUNT);
            let bloom = summoner_bloom().expect("summoner_bloom decodes");
            // The cascade: three bullet types, the seed opening into the sub-emitter.
            assert_eq!(bloom.bullet_types().len(), 3);
            assert_eq!(bloom.emitter_count(), summoner_bloom::EMITTER_COUNT);
        }

        #[test]
        fn no_unit_repeats_a_silhouette() {
            // PRD-0003 rule 3 across every pattern, not only inside the ones written by hand.
            for (path, unit, _, _) in units() {
                let mut seen = std::collections::BTreeSet::new();
                for bullet in unit.bullet_types() {
                    assert!(
                        seen.insert(bullet.visual.silhouette),
                        "{path} repeats a silhouette"
                    );
                }
            }
        }

        #[test]
        fn the_volley_bullets_differ_in_silhouette() {
            let volley = imp_volley().expect("imp_volley decodes");
            let types = volley.bullet_types();
            let dart = types[usize::from(imp_volley::DART)];
            let orb = types[usize::from(imp_volley::ORB)];
            let grain = types[usize::from(imp_volley::GRAIN)];
            // PRD-0003 rule 3: an own silhouette per bullet type.
            assert_eq!(dart.visual.silhouette, bullet_silhouette::DIAMOND);
            assert_eq!(orb.visual.silhouette, bullet_silhouette::ORB);
            assert_eq!(grain.visual.silhouette, bullet_silhouette::RICE);
            assert_eq!(dart.visual.palette, bullet_palette::HEX_MAGENTA);
            assert_eq!(orb.visual.palette, bullet_palette::POISON_LIME);
            assert_eq!(grain.visual.palette, bullet_palette::HEX_MAGENTA);
        }

        #[test]
        fn every_bullet_uses_a_drawn_catalogue_row_in_the_hostile_space() {
            // A reserved catalogue name would compile but never be drawn (unmapped_visual).
            for (path, unit, _, _) in units() {
                for bullet in unit.bullet_types() {
                    let mapped = map_visual(bullet.visual).expect("every game bullet maps");
                    assert!(!path.is_empty());
                    assert!(mapped.silhouette < bullet_silhouette::COUNT);
                    assert!(mapped.palette < bullet_palette::COUNT);
                    assert_eq!(mapped.palette_space, palette_space::HOSTILE);
                    assert!(bullet.collision_radius <= bullet.radius);
                    assert!(bullet.flags.contains(BulletFlags::GRAZEABLE));
                }
            }
        }
    }
}
