//! Stage 2 of the figure-pack converter (figuren-in-engine-spec.md, "Strang A").
//!
//! Reads the `index.json` produced by `assets_src/figure_pack/build_figure_pack.py` (one entry
//! per payload file: path, `AssetKind` value, `kind_version`, and the file holding the already-
//! encoded bytes) and hands each payload, unchanged, to the engine's own
//! [`grimoire_assets::PackWriter`] to build `figures.pack`. This binary never encodes or
//! interprets a payload's fields for the pack container itself -- the pack format has exactly
//! one writer, and it is the engine's.
//!
//! Before handing bytes to [`PackWriter`], [`validate_payload`] re-checks the structural
//! invariants figuren-in-engine-spec.md demands (index/joint bounds, weight sums, texture size,
//! parent order) directly from the raw bytes, independently of the Python stage that produced
//! them -- not because either side trusts the other less, but because this is exactly the class
//! of bug ("Prüf deine Ausgabe, statt sie zu glauben") that has been costly here before.

use std::collections::HashMap;
use std::env;
use std::ffi::OsString;
use std::fmt;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use grimoire_assets::{AssetKind, AssetPath, PackWriter};
use serde_json::Value;

/// See `assets_src/figure_pack/pack_payloads.py`'s module docstring for why these are not the
/// engine-reserved `AssetKind::MESH`/`MATERIAL` (2/3): `PackWriter::add` rejects raw kind values
/// `2..=5` unconditionally (`grimoire_assets::pack::classify_kind`), so the spec's literal
/// assignment cannot work against the actual v0.1.1 crate. These live in the same
/// `0x8000..=0xFFFF` application range the spec already uses for the other three kinds.
const FNP_TEXTURE_RAW: u16 = 0x8001;
const FNP_SKELETON: u16 = 0x8002;
const FNP_FIGURE: u16 = 0x8003;
const FNP_MESH: u16 = 0x8004;
const FNP_MATERIAL: u16 = 0x8005;

const COMPILER_NAME: &str = "fnp_figure_pack_builder";

const USAGE: &str = "\
Usage: figure_pack_builder --index <path/to/index.json> --out <path/to/figures.pack>

Options:
  --index <path>  index.json written by assets_src/figure_pack/build_figure_pack.py
  --out <path>    where to write figures.pack (parent directories are created)
  -h, --help      print this help";

fn main() -> ExitCode {
    match run(env::args_os().skip(1)) {
        Ok(summary) => {
            println!("{summary}");
            ExitCode::SUCCESS
        }
        Err(error) => {
            eprintln!("error: {error}");
            ExitCode::FAILURE
        }
    }
}

/// Command line configuration.
#[derive(Debug, Clone, PartialEq, Eq)]
enum Command {
    Build {
        index_path: PathBuf,
        out_path: PathBuf,
    },
    Help,
}

/// An invalid command line.
#[derive(Debug, Clone, PartialEq, Eq)]
enum ConfigError {
    MissingValue(&'static str),
    DuplicateArgument(&'static str),
    MissingArgument(&'static str),
    UnknownArgument(String),
}

impl fmt::Display for ConfigError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::MissingValue(name) => write!(f, "{name} needs a value"),
            Self::DuplicateArgument(name) => write!(f, "{name} was given more than once"),
            Self::MissingArgument(name) => write!(f, "{name} is required"),
            Self::UnknownArgument(arg) => write!(f, "unknown argument {arg:?}"),
        }
    }
}

impl std::error::Error for ConfigError {}

/// Parses the arguments after the program name.
fn parse_args(args: impl IntoIterator<Item = OsString>) -> Result<Command, ConfigError> {
    let mut index_path = None;
    let mut out_path = None;
    let mut args = args.into_iter();
    while let Some(argument) = args.next() {
        let Some(text) = argument.to_str() else {
            return Err(ConfigError::UnknownArgument(
                argument.to_string_lossy().into_owned(),
            ));
        };
        match text {
            "-h" | "--help" => return Ok(Command::Help),
            "--index" => {
                let value = args.next().ok_or(ConfigError::MissingValue("--index"))?;
                if index_path.replace(PathBuf::from(value)).is_some() {
                    return Err(ConfigError::DuplicateArgument("--index"));
                }
            }
            "--out" => {
                let value = args.next().ok_or(ConfigError::MissingValue("--out"))?;
                if out_path.replace(PathBuf::from(value)).is_some() {
                    return Err(ConfigError::DuplicateArgument("--out"));
                }
            }
            _ => return Err(ConfigError::UnknownArgument(text.to_owned())),
        }
    }
    Ok(Command::Build {
        index_path: index_path.ok_or(ConfigError::MissingArgument("--index"))?,
        out_path: out_path.ok_or(ConfigError::MissingArgument("--out"))?,
    })
}

/// Top-level error type: every failure mode prints as one clear line and aborts before
/// `figures.pack` is written (contract: "er liefert nichts Halbes aus").
#[derive(Debug)]
enum BuildError {
    Config(ConfigError),
    Io {
        path: PathBuf,
        source: std::io::Error,
    },
    Json {
        path: PathBuf,
        source: serde_json::Error,
    },
    Malformed(String),
    Validation(String),
    Pack(grimoire_assets::PackError),
    AssetPath(grimoire_assets::AssetError),
}

impl fmt::Display for BuildError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Config(error) => write!(f, "{error}\n\n{USAGE}"),
            Self::Io { path, source } => write!(f, "{}: {source}", path.display()),
            Self::Json { path, source } => write!(f, "{}: {source}", path.display()),
            Self::Malformed(message) => write!(f, "{message}"),
            Self::Validation(message) => write!(f, "validation failed: {message}"),
            Self::Pack(error) => write!(f, "{error}"),
            Self::AssetPath(error) => write!(f, "{error}"),
        }
    }
}

impl From<ConfigError> for BuildError {
    fn from(error: ConfigError) -> Self {
        Self::Config(error)
    }
}

impl From<grimoire_assets::PackError> for BuildError {
    fn from(error: grimoire_assets::PackError) -> Self {
        Self::Pack(error)
    }
}

impl From<grimoire_assets::AssetError> for BuildError {
    fn from(error: grimoire_assets::AssetError) -> Self {
        Self::AssetPath(error)
    }
}

/// One `index.json` entry: where the payload lives, its path in the pack and its `AssetKind`.
struct IndexEntry {
    path: String,
    kind: u16,
    kind_version: u32,
    file: PathBuf,
}

fn run(args: impl IntoIterator<Item = OsString>) -> Result<String, BuildError> {
    let command = parse_args(args)?;
    let (index_path, out_path) = match command {
        Command::Help => return Ok(USAGE.to_owned()),
        Command::Build {
            index_path,
            out_path,
        } => (index_path, out_path),
    };

    let entries = read_index(&index_path)?;
    let joint_counts = collect_joint_counts(&entries, &index_path)?;

    let mut writer = PackWriter::new(COMPILER_NAME, env!("CARGO_PKG_VERSION"));
    for entry in &entries {
        let payload_path = index_path
            .parent()
            .unwrap_or_else(|| Path::new("."))
            .join(&entry.file);
        let bytes = fs::read(&payload_path).map_err(|source| BuildError::Io {
            path: payload_path.clone(),
            source,
        })?;
        validate_payload(entry, &bytes, &joint_counts)
            .map_err(|message| BuildError::Validation(format!("{}: {message}", entry.path)))?;
        let asset_path = AssetPath::new(&entry.path)?;
        writer.add(
            &asset_path,
            AssetKind(entry.kind),
            entry.kind_version,
            &bytes,
        )?;
    }

    let pack_bytes = writer.finish()?;
    if let Some(parent) = out_path.parent() {
        fs::create_dir_all(parent).map_err(|source| BuildError::Io {
            path: parent.to_path_buf(),
            source,
        })?;
    }
    fs::write(&out_path, &pack_bytes).map_err(|source| BuildError::Io {
        path: out_path.clone(),
        source,
    })?;

    Ok(format!(
        "wrote {} ({} bytes, {} entries)",
        out_path.display(),
        pack_bytes.len(),
        entries.len()
    ))
}

/// Reads and structurally parses `index.json` (the shape `build_figure_pack.py` writes).
fn read_index(index_path: &Path) -> Result<Vec<IndexEntry>, BuildError> {
    let bytes = fs::read(index_path).map_err(|source| BuildError::Io {
        path: index_path.to_path_buf(),
        source,
    })?;
    let value: Value = serde_json::from_slice(&bytes).map_err(|source| BuildError::Json {
        path: index_path.to_path_buf(),
        source,
    })?;
    let entries = value
        .get("entries")
        .and_then(Value::as_array)
        .ok_or_else(|| {
            BuildError::Malformed(format!("{}: no 'entries' array", index_path.display()))
        })?;

    entries
        .iter()
        .enumerate()
        .map(|(i, entry)| {
            let field = |name: &'static str| -> Result<&Value, BuildError> {
                entry.get(name).ok_or_else(|| {
                    BuildError::Malformed(format!("entries[{i}] is missing {name:?}"))
                })
            };
            let path = field("path")?
                .as_str()
                .ok_or_else(|| BuildError::Malformed(format!("entries[{i}].path is not a string")))?
                .to_owned();
            let kind = field("kind")?
                .as_u64()
                .and_then(|v| u16::try_from(v).ok())
                .ok_or_else(|| {
                    BuildError::Malformed(format!("entries[{i}].kind is not a valid u16"))
                })?;
            let kind_version = field("kind_version")?
                .as_u64()
                .and_then(|v| u32::try_from(v).ok())
                .ok_or_else(|| {
                    BuildError::Malformed(format!("entries[{i}].kind_version is not a valid u32"))
                })?;
            let file = field("file")?
                .as_str()
                .ok_or_else(|| BuildError::Malformed(format!("entries[{i}].file is not a string")))?
                .into();
            Ok(IndexEntry {
                path,
                kind,
                kind_version,
                file,
            })
        })
        .collect()
}

/// The figure name embedded in a pack path (`figures/<name>/...`), if the path has that shape.
fn figure_name_of(path: &str) -> Option<&str> {
    let mut segments = path.split('/');
    if segments.next() != Some("figures") {
        return None;
    }
    segments.next()
}

/// First pass: decodes `joint_count` out of every `FNP_SKELETON` payload, keyed by figure name,
/// so [`validate_payload`] can bounds-check `FNP_MESH` joint indices against it regardless of
/// the order entries appear in `index.json`.
fn collect_joint_counts(
    entries: &[IndexEntry],
    index_path: &Path,
) -> Result<HashMap<String, u32>, BuildError> {
    let mut joint_counts = HashMap::new();
    for entry in entries {
        if entry.kind != FNP_SKELETON {
            continue;
        }
        let Some(name) = figure_name_of(&entry.path) else {
            continue;
        };
        let payload_path = index_path
            .parent()
            .unwrap_or_else(|| Path::new("."))
            .join(&entry.file);
        let bytes = fs::read(&payload_path).map_err(|source| BuildError::Io {
            path: payload_path,
            source,
        })?;
        let mut reader = Reader::new(&bytes);
        let _version = reader
            .u32()
            .map_err(|message| BuildError::Validation(format!("{}: {message}", entry.path)))?;
        let joint_count = reader
            .u32()
            .map_err(|message| BuildError::Validation(format!("{}: {message}", entry.path)))?;
        joint_counts.insert(name.to_owned(), joint_count);
    }
    Ok(joint_counts)
}

/// Bounds-checked little-endian cursor, independent of `grimoire_assets`'s own (private) one --
/// deliberately a second implementation, so a bug in either does not hide the same bug in both.
struct Reader<'a> {
    bytes: &'a [u8],
    pos: usize,
}

impl<'a> Reader<'a> {
    fn new(bytes: &'a [u8]) -> Self {
        Self { bytes, pos: 0 }
    }

    fn remaining(&self) -> usize {
        self.bytes.len() - self.pos
    }

    fn take(&mut self, n: usize) -> Result<&'a [u8], String> {
        if self.pos + n > self.bytes.len() {
            return Err(format!(
                "unexpected end of payload at byte {}: need {n} more, {} remain",
                self.pos,
                self.remaining()
            ));
        }
        let slice = &self.bytes[self.pos..self.pos + n];
        self.pos += n;
        Ok(slice)
    }

    fn u8(&mut self) -> Result<u8, String> {
        Ok(self.take(1)?[0])
    }

    fn u16(&mut self) -> Result<u16, String> {
        // `take(2)` guarantees exactly 2 bytes.
        Ok(u16::from_le_bytes(
            self.take(2)?.try_into().expect("take(2) yields 2 bytes"),
        ))
    }

    fn u32(&mut self) -> Result<u32, String> {
        Ok(u32::from_le_bytes(
            self.take(4)?.try_into().expect("take(4) yields 4 bytes"),
        ))
    }

    fn i32(&mut self) -> Result<i32, String> {
        Ok(i32::from_le_bytes(
            self.take(4)?.try_into().expect("take(4) yields 4 bytes"),
        ))
    }

    fn f32(&mut self) -> Result<f32, String> {
        Ok(f32::from_le_bytes(
            self.take(4)?.try_into().expect("take(4) yields 4 bytes"),
        ))
    }

    fn skip(&mut self, n: usize) -> Result<(), String> {
        self.take(n).map(|_| ())
    }

    fn finished(&self) -> bool {
        self.pos == self.bytes.len()
    }
}

/// Re-checks the structural invariants figuren-in-engine-spec.md demands, directly from the raw
/// payload bytes, before the payload reaches [`PackWriter`].
fn validate_payload(
    entry: &IndexEntry,
    bytes: &[u8],
    joint_counts: &HashMap<String, u32>,
) -> Result<(), String> {
    match entry.kind {
        FNP_MESH => validate_mesh(&entry.path, bytes, joint_counts),
        FNP_MATERIAL => validate_material(bytes),
        FNP_TEXTURE_RAW => validate_texture(bytes),
        FNP_SKELETON => validate_skeleton(bytes),
        FNP_FIGURE => validate_figure(bytes),
        other => Err(format!("unknown kind 0x{other:04x}")),
    }
}

const MESH_VERTEX_SIZE: usize = 3 * 4 + 3 * 4 + 2 * 4 + 4 * 2 + 4 * 4; // pos+normal+uv+joints+weights
const WEIGHT_TOLERANCE: f32 = 1.0e-3;

fn validate_mesh(
    path: &str,
    bytes: &[u8],
    joint_counts: &HashMap<String, u32>,
) -> Result<(), String> {
    let figure = figure_name_of(path).ok_or_else(|| format!("path {path:?} has no figure name"))?;
    let joint_count = *joint_counts
        .get(figure)
        .ok_or_else(|| format!("no FNP_SKELETON found for figure {figure:?}"))?;

    let mut reader = Reader::new(bytes);
    let _version = reader.u32()?;
    let vertex_count = reader.u32()?;
    let index_count = reader.u32()?;
    if !index_count.is_multiple_of(3) {
        return Err(format!("index_count {index_count} is not divisible by 3"));
    }
    for vertex in 0..vertex_count {
        reader.skip(3 * 4 + 3 * 4 + 2 * 4)?; // position, normal, uv: not re-validated here
        let joints = [reader.u16()?, reader.u16()?, reader.u16()?, reader.u16()?];
        for joint in joints {
            if u32::from(joint) >= joint_count {
                return Err(format!(
                    "vertex {vertex} joint index {joint} >= joint_count {joint_count}"
                ));
            }
        }
        let weights = [reader.f32()?, reader.f32()?, reader.f32()?, reader.f32()?];
        let sum: f32 = weights.iter().sum();
        if (sum - 1.0).abs() > WEIGHT_TOLERANCE {
            return Err(format!(
                "vertex {vertex} weight sum {sum} deviates from 1.0"
            ));
        }
    }
    for i in 0..index_count {
        let index = reader.u32()?;
        if index >= vertex_count {
            return Err(format!(
                "index #{i} value {index} >= vertex_count {vertex_count}"
            ));
        }
    }
    if !reader.finished() {
        return Err(format!(
            "{} trailing byte(s) after the declared mesh data",
            reader.remaining()
        ));
    }
    let _ = MESH_VERTEX_SIZE; // documents the per-vertex stride the skip() calls above rely on
    Ok(())
}

fn validate_material(bytes: &[u8]) -> Result<(), String> {
    let mut reader = Reader::new(bytes);
    let _version = reader.u32()?;
    reader.skip(4 * 4 + 4 + 4 + 3 * 4)?; // base_color, metallic, roughness, emissive
    let alpha_mode = reader.u8()?;
    if alpha_mode > 2 {
        return Err(format!("alpha_mode {alpha_mode} not in 0..=2"));
    }
    reader.skip(4)?; // alpha_cutoff
    reader.skip(4 * 3)?; // three u32 texture refs
    if !reader.finished() {
        return Err(format!(
            "{} trailing byte(s) after the declared material data",
            reader.remaining()
        ));
    }
    Ok(())
}

const MAX_TEXTURE_PIXELS: u64 = 64_000_000;

fn validate_texture(bytes: &[u8]) -> Result<(), String> {
    let mut reader = Reader::new(bytes);
    let _version = reader.u32()?;
    let width = reader.u32()?;
    let height = reader.u32()?;
    let color_space = reader.u8()?;
    if width == 0 || height == 0 {
        return Err(format!("width/height must be >= 1, got {width}x{height}"));
    }
    if u64::from(width) * u64::from(height) > MAX_TEXTURE_PIXELS {
        return Err(format!(
            "{width}x{height} exceeds {MAX_TEXTURE_PIXELS} pixels"
        ));
    }
    if color_space > 1 {
        return Err(format!("color_space {color_space} not in {{0, 1}}"));
    }
    let expected = width as usize * height as usize * 4;
    if reader.remaining() != expected {
        return Err(format!(
            "rgba payload is {} bytes, expected width*height*4={expected}",
            reader.remaining()
        ));
    }
    Ok(())
}

const MAX_JOINT_COUNT: u32 = 256;

fn validate_skeleton(bytes: &[u8]) -> Result<(), String> {
    let mut reader = Reader::new(bytes);
    let _version = reader.u32()?;
    let joint_count = reader.u32()?;
    if joint_count > MAX_JOINT_COUNT {
        return Err(format!("{joint_count} joints exceeds {MAX_JOINT_COUNT}"));
    }
    for index in 0..joint_count {
        let parent = reader.i32()?;
        if parent != -1 && !(0 <= parent && (parent as u32) < index) {
            return Err(format!(
                "joint {index} has parent {parent}, not -1 and not < its own index"
            ));
        }
        reader.skip(16 * 4)?; // inverse_bind
        let name_len = usize::from(reader.u8()?);
        if name_len > 63 {
            return Err(format!("joint {index} name_len {name_len} exceeds 63"));
        }
        reader.skip(name_len)?;
        reader.skip(3 * 4 + 4 * 4 + 3 * 4)?; // translation, rotation, scale
    }
    if !reader.finished() {
        return Err(format!(
            "{} trailing byte(s) after the declared skeleton data",
            reader.remaining()
        ));
    }
    Ok(())
}

fn validate_figure(bytes: &[u8]) -> Result<(), String> {
    let mut reader = Reader::new(bytes);
    let _version = reader.u32()?;
    let part_count = reader.u32()?;
    if part_count == 0 {
        return Err("figure has no parts".to_owned());
    }
    reader.skip(part_count as usize * 16)?; // mesh_id + material_id, u64 each
    let texture_count = reader.u32()?;
    reader.skip(texture_count as usize * 8)?;
    reader.skip(8)?; // skeleton_id
    reader.skip(3 * 4 + 3 * 4)?; // bounds_min, bounds_max
    if !reader.finished() {
        return Err(format!(
            "{} trailing byte(s) after the declared figure data",
            reader.remaining()
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn args(list: &[&str]) -> Vec<OsString> {
        list.iter().map(OsString::from).collect()
    }

    #[test]
    fn parses_index_and_out() {
        let command = parse_args(args(&[
            "--index",
            "a/index.json",
            "--out",
            "b/figures.pack",
        ]));
        assert_eq!(
            command,
            Ok(Command::Build {
                index_path: PathBuf::from("a/index.json"),
                out_path: PathBuf::from("b/figures.pack"),
            })
        );
    }

    #[test]
    fn help_wins_when_seen_before_a_bad_argument() {
        // Arguments are scanned left to right (matching fnp_app::cli): `--help` short-circuits
        // as soon as it is reached, but an invalid argument earlier in the list still errors.
        assert_eq!(parse_args(args(&["--help", "--bogus"])), Ok(Command::Help));
        assert!(parse_args(args(&["--bogus", "--help"])).is_err());
    }

    #[test]
    fn missing_required_arguments_are_rejected() {
        assert_eq!(
            parse_args(args(&["--index", "a"])),
            Err(ConfigError::MissingArgument("--out"))
        );
        assert_eq!(
            parse_args(args(&["--out", "b"])),
            Err(ConfigError::MissingArgument("--index"))
        );
    }

    #[test]
    fn duplicate_and_unknown_arguments_are_rejected() {
        assert_eq!(
            parse_args(args(&["--index", "a", "--index", "b", "--out", "c"])),
            Err(ConfigError::DuplicateArgument("--index"))
        );
        assert_eq!(
            parse_args(args(&["--nope"])),
            Err(ConfigError::UnknownArgument("--nope".to_owned()))
        );
    }

    #[test]
    fn figure_name_extraction() {
        assert_eq!(figure_name_of("figures/soul/mesh/0"), Some("soul"));
        assert_eq!(figure_name_of("figures/imp/skeleton"), Some("imp"));
        assert_eq!(figure_name_of("not_a_figure_path"), None);
    }

    fn mesh_bytes(vertex_count: u32, index_count: u32, joint: u16, weight_sum: f32) -> Vec<u8> {
        let mut out = Vec::new();
        out.extend_from_slice(&1u32.to_le_bytes());
        out.extend_from_slice(&vertex_count.to_le_bytes());
        out.extend_from_slice(&index_count.to_le_bytes());
        for _ in 0..vertex_count {
            out.extend_from_slice(&[0u8; 3 * 4 + 3 * 4 + 2 * 4]); // position, normal, uv
            for _ in 0..4 {
                out.extend_from_slice(&joint.to_le_bytes());
            }
            let weights = [weight_sum, 0.0, 0.0, 0.0];
            for w in weights {
                out.extend_from_slice(&w.to_le_bytes());
            }
        }
        for i in 0..index_count {
            out.extend_from_slice(&(i % vertex_count.max(1)).to_le_bytes());
        }
        out
    }

    #[test]
    fn validate_mesh_accepts_a_well_formed_payload() {
        let mut joint_counts = HashMap::new();
        joint_counts.insert("soul".to_owned(), 4u32);
        let bytes = mesh_bytes(3, 3, 2, 1.0);
        assert!(validate_mesh("figures/soul/mesh/0", &bytes, &joint_counts).is_ok());
    }

    #[test]
    fn validate_mesh_rejects_out_of_range_joint() {
        let mut joint_counts = HashMap::new();
        joint_counts.insert("soul".to_owned(), 4u32);
        let bytes = mesh_bytes(3, 3, 9, 1.0);
        assert!(validate_mesh("figures/soul/mesh/0", &bytes, &joint_counts).is_err());
    }

    #[test]
    fn validate_mesh_rejects_bad_weight_sum() {
        let mut joint_counts = HashMap::new();
        joint_counts.insert("soul".to_owned(), 4u32);
        let bytes = mesh_bytes(3, 3, 2, 0.4);
        assert!(validate_mesh("figures/soul/mesh/0", &bytes, &joint_counts).is_err());
    }

    #[test]
    fn validate_mesh_requires_a_known_skeleton() {
        let joint_counts = HashMap::new();
        let bytes = mesh_bytes(1, 3, 0, 1.0);
        assert!(validate_mesh("figures/ghost/mesh/0", &bytes, &joint_counts).is_err());
    }

    #[test]
    fn validate_texture_checks_declared_size() {
        let mut bytes = Vec::new();
        bytes.extend_from_slice(&1u32.to_le_bytes());
        bytes.extend_from_slice(&2u32.to_le_bytes());
        bytes.extend_from_slice(&2u32.to_le_bytes());
        bytes.push(0);
        bytes.extend_from_slice(&[0u8; 16]); // 2*2*4 = 16, correct
        assert!(validate_texture(&bytes).is_ok());
        bytes.pop();
        assert!(validate_texture(&bytes).is_err());
    }

    #[test]
    fn validate_skeleton_rejects_forward_parent_reference() {
        let mut bytes = Vec::new();
        bytes.extend_from_slice(&1u32.to_le_bytes());
        bytes.extend_from_slice(&1u32.to_le_bytes()); // joint_count = 1
        bytes.extend_from_slice(&1i32.to_le_bytes()); // parent = 1, but only joint 0 exists
        bytes.extend_from_slice(&[0u8; 16 * 4]); // inverse_bind
        bytes.push(0); // name_len
        bytes.extend_from_slice(&[0u8; 3 * 4 + 4 * 4 + 3 * 4]); // translation, rotation, scale
        assert!(validate_skeleton(&bytes).is_err());
    }

    #[test]
    fn validate_figure_rejects_zero_parts() {
        let mut bytes = Vec::new();
        bytes.extend_from_slice(&1u32.to_le_bytes());
        bytes.extend_from_slice(&0u32.to_le_bytes());
        assert!(validate_figure(&bytes).is_err());
    }

    /// Cross-checks `stable_id.asset_id_for_path` (`assets_src/figure_pack/stable_id.py`)
    /// against the real `AssetId::from_path` for the same paths: if this ever fails, the Python
    /// converter's `FNP_FIGURE` cross-references (mesh_id/material_id/texture_id/skeleton_id) no
    /// longer match what `PackReader`/`AssetStore` will look up at runtime.
    #[test]
    fn asset_id_matches_the_python_reference() {
        let cases: &[(&str, u64)] = &[
            ("figures/soul/mesh/0", 16_617_635_157_359_565_775),
            ("figures/soul/material/0", 10_220_622_674_129_584_891),
            ("figures/soul/texture/0", 7_965_656_911_314_222_875),
            ("figures/soul/skeleton", 17_225_010_477_930_074_322),
            ("figures/soul/figure", 7_146_022_253_345_053_871),
            ("figures/imp/mesh/3", 14_508_779_328_413_793_227),
            ("figures/brute/figure", 7_119_674_054_548_579_387),
            ("a/b.c", 6_850_813_133_520_280_877),
            ("a/b.d", 7_186_942_913_020_061_628),
        ];
        for (path, expected) in cases {
            let asset_path = AssetPath::new(path).expect("valid AssetPath");
            let id = grimoire_assets::AssetId::from_path(&asset_path);
            assert_eq!(id.0, *expected, "path {path:?}");
        }
    }

    /// Runs the real CLI end to end (a synthetic `index.json` plus one skeleton and one mesh
    /// payload, in a scratch directory) and reads the resulting pack back with the real
    /// [`grimoire_assets::PackReader`] -- proving the writer half (`cargo test`, above) and the
    /// reader half of `grimoire_assets` agree on what this binary produces, without needing the
    /// real `.glb` fixtures (which do not exist in CI).
    #[test]
    fn run_builds_a_pack_that_pack_reader_accepts() {
        use grimoire_assets::{AssetSource, PackReader};
        use std::sync::Arc;

        let dir = env::temp_dir().join(format!(
            "figure_pack_builder_test_{}_{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::SystemTime::UNIX_EPOCH)
                .expect("system clock is after 1970")
                .as_nanos()
        ));
        fs::create_dir_all(&dir).expect("create scratch dir");

        // One joint, one triangle, weight 1 on joint 0 -- the smallest input every validator in
        // this file still accepts.
        let mut skeleton_bytes = Vec::new();
        skeleton_bytes.extend_from_slice(&1u32.to_le_bytes()); // version
        skeleton_bytes.extend_from_slice(&1u32.to_le_bytes()); // joint_count
        skeleton_bytes.extend_from_slice(&(-1i32).to_le_bytes()); // parent
        skeleton_bytes.extend_from_slice(&[0u8; 16 * 4]); // inverse_bind (all zero: never read here)
        skeleton_bytes.push(0); // name_len
        skeleton_bytes.extend_from_slice(&[0u8; 3 * 4 + 4 * 4 + 3 * 4]);
        fs::write(dir.join("skeleton.bin"), &skeleton_bytes).unwrap();

        let mesh_bytes = mesh_bytes(3, 3, 0, 1.0);
        fs::write(dir.join("mesh_0.bin"), &mesh_bytes).unwrap();

        let index = serde_json::json!({
            "entries": [
                {"path": "figures/t/skeleton", "kind": FNP_SKELETON, "kind_version": 1, "file": "skeleton.bin"},
                {"path": "figures/t/mesh/0", "kind": FNP_MESH, "kind_version": 1, "file": "mesh_0.bin"},
            ]
        });
        let index_path = dir.join("index.json");
        fs::write(&index_path, serde_json::to_vec_pretty(&index).unwrap()).unwrap();

        let out_path = dir.join("figures.pack");
        let summary = run(vec![
            OsString::from("--index"),
            index_path.clone().into_os_string(),
            OsString::from("--out"),
            out_path.clone().into_os_string(),
        ])
        .expect("run succeeds");
        assert!(summary.contains("2 entries"), "{summary}");

        let pack_bytes = fs::read(&out_path).expect("read the written pack");
        let reader = PackReader::from_bytes(Arc::from(pack_bytes)).expect("PackReader accepts it");
        assert_eq!(
            reader.entries().len(),
            2,
            "both entries round-trip through PackReader"
        );

        fs::remove_dir_all(&dir).ok();
    }
}
