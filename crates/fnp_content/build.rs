//! Compiles the Sigil sources under `content/sigil/` into binary units (`OUT_DIR/<name>.unit`)
//! with the engine's compiler, `grimoire_sigilc`.
//!
//! The canonical content path of a unit is its path relative to `content/` (contract §11.1), so
//! the unit id the compiler derives from it is the same on every machine and checkout location.
//! A source with diagnostics fails the build and prints every diagnostic as a cargo warning.

use std::collections::BTreeMap;
use std::io::ErrorKind;
use std::path::PathBuf;

use grimoire_sigilc::compiler::{LoadError, SourceLoader, compile};

/// Canonical content paths (relative to `content/`) of every unit this crate embeds, with the
/// file name each compiled unit gets in `OUT_DIR`.
const UNITS: &[(&str, &str)] = &[
    ("sigil/imp_volley.sigil", "imp_volley.unit"),
    ("sigil/imp_curtain.sigil", "imp_curtain.unit"),
];

/// Loads imported sources relative to the content root.
struct ContentRoot(PathBuf);

impl SourceLoader for ContentRoot {
    fn load(&self, path: &str) -> Result<String, LoadError> {
        std::fs::read_to_string(self.0.join(path)).map_err(|error| match error.kind() {
            ErrorKind::NotFound => LoadError::NotFound,
            _ => LoadError::Other(error.to_string()),
        })
    }
}

fn main() {
    let manifest_dir = PathBuf::from(
        std::env::var_os("CARGO_MANIFEST_DIR").expect("cargo sets CARGO_MANIFEST_DIR"),
    );
    let out_dir = PathBuf::from(std::env::var_os("OUT_DIR").expect("cargo sets OUT_DIR"));
    let content_root = manifest_dir.join("..").join("..").join("content");
    // Imports resolve relative to the content root, so any change below it can change a unit.
    println!(
        "cargo:rerun-if-changed={}",
        content_root.join("sigil").display()
    );
    let loader = ContentRoot(content_root.clone());
    // No behaviours are registered by the game yet; a `behaviour = ...` reference fails to compile.
    let behavior_ids = BTreeMap::new();

    let mut failed = false;
    for &(unit_path, file_name) in UNITS {
        let source_path = content_root.join(unit_path);
        println!("cargo:rerun-if-changed={}", source_path.display());
        let source = match std::fs::read_to_string(&source_path) {
            Ok(source) => source,
            Err(error) => {
                println!("cargo:warning=cannot read {unit_path}: {error}");
                failed = true;
                continue;
            }
        };
        let output = compile(unit_path, &source, &loader, &behavior_ids);
        match output.bytes {
            Some(bytes) => {
                std::fs::write(out_dir.join(file_name), bytes)
                    .expect("the compiled unit can be written to OUT_DIR");
            }
            None => {
                for diagnostic in &output.diagnostics {
                    for line in diagnostic.render_text().lines() {
                        println!("cargo:warning={line}");
                    }
                }
                failed = true;
            }
        }
    }
    assert!(
        !failed,
        "Sigil content failed to compile; see the warnings above"
    );
}
