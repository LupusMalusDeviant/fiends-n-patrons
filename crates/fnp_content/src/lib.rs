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

    #[cfg(test)]
    mod tests {
        use grimoire::adapters::sigil_render::map_visual;
        use grimoire::render::{bullet_palette, bullet_silhouette, palette_space};
        use grimoire::sigil::BulletFlags;

        use super::*;

        fn units() -> [(SigilUnit, &'static [u8]); 2] {
            [
                (imp_volley().expect("imp_volley decodes"), IMP_VOLLEY_BYTES),
                (
                    imp_curtain().expect("imp_curtain decodes"),
                    IMP_CURTAIN_BYTES,
                ),
            ]
        }

        #[test]
        fn both_units_decode_canonically_with_their_emitters() {
            let [(volley, _), (curtain, _)] = units();
            assert_eq!(volley.emitter_count(), imp_volley::EMITTER_COUNT);
            assert_eq!(volley.bullet_types().len(), 3);
            assert_eq!(curtain.emitter_count(), imp_curtain::EMITTER_COUNT);
            assert_eq!(curtain.bullet_types().len(), 2);
            assert_ne!(volley.id(), curtain.id());
            for (unit, bytes) in units() {
                assert_ne!(unit.id().0, 0);
                assert!(unit.behavior_refs().is_empty());
                // Canonical encoding: decoding and re-encoding gives the same bytes (§11.1).
                assert_eq!(unit.to_bytes(), bytes);
            }
        }

        #[test]
        fn the_volley_bullets_differ_in_silhouette() {
            let [(volley, _), _] = units();
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
            for (unit, _) in units() {
                for bullet in unit.bullet_types() {
                    let mapped = map_visual(bullet.visual).expect("every imp bullet maps");
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
