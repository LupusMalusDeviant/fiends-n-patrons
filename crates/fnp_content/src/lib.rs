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
    //! platform and checkout.

    use grimoire::sigil::{SigilUnit, UnitError};

    /// Canonical content path of the imp's attack pattern (relative to `content/`).
    pub const IMP_VOLLEY_PATH: &str = "sigil/imp_volley.sigil";

    /// Compiled bytes of [`IMP_VOLLEY_PATH`].
    pub const IMP_VOLLEY_BYTES: &[u8] =
        include_bytes!(concat!(env!("OUT_DIR"), "/imp_volley.unit"));

    /// Indices inside the unit compiled from [`IMP_VOLLEY_PATH`].
    ///
    /// Emitters and bullet types keep the declaration order of the source. Silhouette and palette
    /// indices are a per-unit catalogue the compiler numbers alphabetically
    /// (`docs/formats/sigil.md` §10.3 and open point 5 of §11.4); there is no shared catalogue yet.
    pub mod imp_volley {
        /// `emitter volley`: the aimed fan of embers.
        pub const VOLLEY: u16 = 0;
        /// `emitter ring`: the winding ring of thorns.
        pub const RING: u16 = 1;
        /// Number of emitters in the unit.
        pub const EMITTER_COUNT: u16 = 2;
        /// Bullet type `ember`.
        pub const EMBER: u16 = 0;
        /// Bullet type `thorn`.
        pub const THORN: u16 = 1;
        /// Silhouette index of `orb` (the ember).
        pub const SILHOUETTE_ORB: u16 = 0;
        /// Silhouette index of `rice` (the thorn).
        pub const SILHOUETTE_RICE: u16 = 1;
        /// Palette index of `enemy.lime` (style bible H1, the thorn).
        pub const PALETTE_LIME: u16 = 0;
        /// Palette index of `enemy.magenta` (style bible H0, the ember).
        pub const PALETTE_MAGENTA: u16 = 1;
    }

    /// Decodes [`IMP_VOLLEY_BYTES`].
    ///
    /// # Errors
    /// A [`UnitError`] if the embedded bytes do not decode, which the tests below rule out for
    /// every build.
    pub fn imp_volley() -> Result<SigilUnit, UnitError> {
        SigilUnit::from_bytes(IMP_VOLLEY_BYTES)
    }

    #[cfg(test)]
    mod tests {
        use grimoire::sigil::BulletFlags;

        use super::*;

        #[test]
        fn the_imp_volley_decodes_with_both_emitters_and_bullet_types() {
            let unit = imp_volley().expect("the embedded unit decodes");
            assert_ne!(unit.id().0, 0);
            assert_eq!(unit.emitter_count(), imp_volley::EMITTER_COUNT);
            assert_eq!(unit.bullet_types().len(), 2);
            assert!(unit.behavior_refs().is_empty());
            // Canonical encoding: decoding and re-encoding gives the same bytes (contract §11.1).
            assert_eq!(unit.to_bytes(), IMP_VOLLEY_BYTES);
        }

        #[test]
        fn the_imp_bullets_differ_in_silhouette_and_palette_and_are_hostile() {
            let unit = imp_volley().expect("the embedded unit decodes");
            let types = unit.bullet_types();
            assert_eq!(types.len(), 2);
            let ember = types[usize::from(imp_volley::EMBER)];
            let thorn = types[usize::from(imp_volley::THORN)];
            // PRD-0003 rules 3 and 4: an own silhouette per type, enemy palette space only.
            assert_eq!(ember.visual.silhouette, imp_volley::SILHOUETTE_ORB);
            assert_eq!(thorn.visual.silhouette, imp_volley::SILHOUETTE_RICE);
            assert_eq!(ember.visual.palette, imp_volley::PALETTE_MAGENTA);
            assert_eq!(thorn.visual.palette, imp_volley::PALETTE_LIME);
            for bullet in types {
                assert_eq!(bullet.visual.palette_space, 1);
                assert!(bullet.collision_radius <= bullet.radius);
                assert!(bullet.flags.contains(BulletFlags::GRAZEABLE));
            }
            assert!((ember.radius - 0.22).abs() < 1.0e-6);
            assert!((thorn.radius - 0.16).abs() < 1.0e-6);
        }
    }
}
