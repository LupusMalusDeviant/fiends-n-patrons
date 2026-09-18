//! Deterministic run plans and floor layouts. This module has no renderer state:
//! the same `(seed, room)` always produces the same rooms, tiles and puddles.
//! The small room uses authored straight transitions. The larger world keeps
//! organic region boundaries as terrain-neighbour data for future edge blending;
//! the authored straight tiles alone cannot cover corners and junctions.

use grimoire::prelude::dmath;
use std::collections::VecDeque;

/// Tiles along either axis of the current 48 m combat-room prototype.
pub const FLOOR_SIDE: usize = 12;
/// Edge length of a tile in the current combat-room prototype, in metres.
pub const TILE_SIZE_M: u32 = 4;
/// Requested edge length of the complete world in metres and one-metre tiles.
pub const WORLD_SIDE: usize = 256;
/// Edge length of one world tile in metres.
pub const WORLD_TILE_SIZE_M: u32 = 1;
/// Tiles along either axis of one independently generated world chunk.
pub const WORLD_CHUNK_SIDE: usize = 16;
/// Number of chunks along either axis of the world.
pub const WORLD_CHUNKS_PER_SIDE: usize = WORLD_SIDE / WORLD_CHUNK_SIDE;
/// Puddles in one playable room.
pub const PUDDLES_PER_ROOM: usize = 10;

/// Three current biome identities.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ArenaDistrict {
    /// Ornate stone, wood and earth.
    Crypt,
    /// Stone, iron and ash.
    Foundry,
    /// Earth, stone and bones.
    Ossuary,
}

impl ArenaDistrict {
    /// Stable name used by `FNP_ARENA_DISTRICT`.
    #[must_use]
    pub fn name(self) -> &'static str {
        match self {
            Self::Crypt => "crypt",
            Self::Foundry => "foundry",
            Self::Ossuary => "ossuary",
        }
    }

    /// Parse a biome name.
    #[must_use]
    pub fn parse(name: &str) -> Option<Self> {
        match name {
            "crypt" => Some(Self::Crypt),
            "foundry" => Some(Self::Foundry),
            "ossuary" => Some(Self::Ossuary),
            _ => None,
        }
    }

    fn terrains(self) -> [Terrain; 3] {
        match self {
            Self::Crypt => [Terrain::Stone, Terrain::Wood, Terrain::Earth],
            Self::Foundry => [Terrain::Stone, Terrain::Iron, Terrain::Ash],
            Self::Ossuary => [Terrain::Earth, Terrain::Stone, Terrain::Bone],
        }
    }
}

/// The terrain labels in the 2D tile catalog.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Terrain {
    /// Masonry.
    Stone,
    /// Timber.
    Wood,
    /// Machinery and plating.
    Iron,
    /// Dirt.
    Earth,
    /// Ossuary gravel.
    Bone,
    /// Fire remains.
    Ash,
}

/// Index into the 20 bundled tile images, in catalog order.
#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TileId {
    /// Unbroken crypt ornament.
    StoneOrnateIntact,
    /// Cracked crypt ornament.
    StoneOrnateCracked,
    /// Shattered crypt ornament.
    StoneOrnateShattered,
    /// Plain stone.
    StonePlain,
    /// Mossy stone.
    StoneMossy,
    /// Oak floor.
    WoodOak,
    /// Rotted timber.
    WoodRotted,
    /// Burnt timber.
    WoodCharred,
    /// Rusted metal.
    IronRusted,
    /// Clockwork metal.
    IronClockwork,
    /// Dry earth.
    EarthDry,
    /// Damp earth.
    EarthWet,
    /// Bone gravel.
    BoneGravel,
    /// Burnt ash.
    AshBurned,
    /// Stone to wood.
    EdgeStoneWood,
    /// Stone to earth.
    EdgeStoneEarth,
    /// Stone to iron.
    EdgeStoneIron,
    /// Wood to earth.
    EdgeWoodEarth,
    /// Iron to ash.
    EdgeIronAsh,
    /// Stone to bone.
    EdgeStoneBone,
}

impl TileId {
    /// Stable file stem of the tile image.
    #[must_use]
    pub fn name(self) -> &'static str {
        const NAMES: [&str; 20] = [
            "stone_ornate_intact",
            "stone_ornate_cracked",
            "stone_ornate_shattered",
            "stone_plain",
            "stone_mossy",
            "wood_oak",
            "wood_rotted",
            "wood_charred",
            "iron_rusted",
            "iron_clockwork",
            "earth_dry",
            "earth_wet",
            "bone_gravel",
            "ash_burned",
            "edge_stone_wood",
            "edge_stone_earth",
            "edge_stone_iron",
            "edge_wood_earth",
            "edge_iron_ash",
            "edge_stone_bone",
        ];
        NAMES[self as usize]
    }

    fn terrains(self) -> (Terrain, Terrain) {
        use Terrain::{Ash, Bone, Earth, Iron, Stone, Wood};
        match self {
            Self::StoneOrnateIntact
            | Self::StoneOrnateCracked
            | Self::StoneOrnateShattered
            | Self::StonePlain
            | Self::StoneMossy => (Stone, Stone),
            Self::WoodOak | Self::WoodRotted | Self::WoodCharred => (Wood, Wood),
            Self::IronRusted | Self::IronClockwork => (Iron, Iron),
            Self::EarthDry | Self::EarthWet => (Earth, Earth),
            Self::BoneGravel => (Bone, Bone),
            Self::AshBurned => (Ash, Ash),
            Self::EdgeStoneWood => (Stone, Wood),
            Self::EdgeStoneEarth => (Stone, Earth),
            Self::EdgeStoneIron => (Stone, Iron),
            Self::EdgeWoodEarth => (Wood, Earth),
            Self::EdgeIronAsh => (Iron, Ash),
            Self::EdgeStoneBone => (Stone, Bone),
        }
    }
}

/// One tile and its clockwise quarter turns. The current straight-band layouts
/// use 0 or 2 turns; the socket validator also handles the other two turns.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TileInstance {
    /// Source tile.
    pub id: TileId,
    /// Clockwise quarter turns, from 0 through 3.
    pub turns: u8,
}

/// Puddle location uses centimetres so plans compare without floating-point drift.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PuddlePlacement {
    /// 0 blood, 1 plague bile, 2 void ichor.
    pub kind: u8,
    /// World X position in centimetres.
    pub x_cm: i16,
    /// World Y position in centimetres.
    pub y_cm: i16,
    /// Uniform mesh scale in centimetres.
    pub size_cm: u16,
}

/// A complete, reproducible floor for one room.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RoomFloor {
    /// The original seed passed to [`generate_floor`].
    pub seed: u64,
    /// Biome identity.
    pub district: ArenaDistrict,
    /// Row-major tiles; row 0 is world -Y.
    pub tiles: [TileInstance; FLOOR_SIDE * FLOOR_SIDE],
    /// Visual puddles inside the current arena curbs.
    pub puddles: [PuddlePlacement; PUDDLES_PER_ROOM],
    /// Column of the first straight material boundary.
    pub first_boundary: u8,
    /// Column of the second straight material boundary.
    pub second_boundary: u8,
    /// Whether the material order is reflected across X.
    pub reflected: bool,
}

/// One independently generated section of the 256 by 256 metre world. Its
/// tile coordinates start at the south-west corner; the world origin is central.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WorldChunk {
    /// Zero-based chunk X coordinate.
    pub x: u8,
    /// Zero-based chunk Y coordinate.
    pub y: u8,
    /// Row-major one-metre tiles, including boundary-blending information.
    pub tiles: [WorldTile; WORLD_CHUNK_SIDE * WORLD_CHUNK_SIDE],
    /// Sparse, terrain-dependent floor marks. Each fits inside one tile.
    pub puddles: Vec<PuddlePlacement>,
}

/// One logical tile. Adjacent terrain labels let the renderer soften curved
/// borders without demanding corner variants of every hand-painted texture.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct WorldTile {
    /// One of the authored base textures; no straight transition is forced onto a corner.
    pub visual: TileInstance,
    /// Terrain occupying most of this square metre.
    pub terrain: Terrain,
    /// Neighbours in north, east, south, west order. At world edges this repeats
    /// the nearest in-bounds terrain.
    pub adjacent: [Terrain; 4],
}

/// A room's purpose in the linear run plan. The current combat prototype only
/// renders the first room; progression is represented as data for later systems.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RoomKind {
    /// Safe entry.
    Intro,
    /// Ordinary fight.
    Combat,
    /// Patron altar.
    Altar,
    /// Elite fight.
    Miniboss,
    /// Hand-authored boss arena slot.
    Boss,
}

/// A single entry in a stage's linear room chain.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RoomPlan {
    /// Purpose of the room.
    pub kind: RoomKind,
    /// Seed used to generate its floor and decorative placements.
    pub floor_seed: u64,
    /// Planned visual corruption grade from 0 to 3; no gameplay effect yet.
    pub corruption_grade: u8,
}

/// One stage of a run.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StagePlan {
    /// Biome used by its rooms.
    pub district: ArenaDistrict,
    /// Five to eight rooms, ending with a boss slot.
    pub rooms: Vec<RoomPlan>,
    /// A shop follows this stage, except after the final one.
    pub shop_after: bool,
}

/// Three stages in a fixed linear order, with randomized biome order and rooms.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RunPlan {
    /// Source seed.
    pub seed: u64,
    /// Three stages; all three biome identities appear exactly once.
    pub stages: [StagePlan; 3],
}

/// Small platform-independent PRNG for authored world generation only.
struct Rng(u64);

impl Rng {
    fn new(seed: u64) -> Self {
        Self(seed)
    }

    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut value = self.0;
        value = (value ^ (value >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        value = (value ^ (value >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        value ^ (value >> 31)
    }

    fn below(&mut self, limit: u64) -> u64 {
        self.next() % limit
    }
}

/// Plan a three-stage run. This is a pure function with no asset loading.
#[must_use]
pub fn generate_run(seed: u64) -> RunPlan {
    let mut rng = Rng::new(seed ^ 0x000A_11CE_5EED_5EED);
    let mut order = [
        ArenaDistrict::Crypt,
        ArenaDistrict::Foundry,
        ArenaDistrict::Ossuary,
    ];
    for i in (1..order.len()).rev() {
        order.swap(i, rng.below((i + 1) as u64) as usize);
    }
    let stages = std::array::from_fn(|stage_index| {
        let extra_fights = rng.below(4) as usize;
        let mut kinds = vec![RoomKind::Intro, RoomKind::Combat, RoomKind::Altar];
        kinds.extend(std::iter::repeat_n(RoomKind::Combat, extra_fights));
        kinds.extend([RoomKind::Miniboss, RoomKind::Boss]);
        let rooms = kinds
            .into_iter()
            .enumerate()
            .map(|(room_index, kind)| RoomPlan {
                kind,
                floor_seed: rng.next(),
                corruption_grade: ((stage_index + room_index / 3).min(3)) as u8,
            })
            .collect();
        StagePlan {
            district: order[stage_index],
            rooms,
            shop_after: stage_index < 2,
        }
    });
    RunPlan { seed, stages }
}

fn base_options(terrain: Terrain) -> &'static [(TileId, u64)] {
    use TileId as Id;
    match terrain {
        Terrain::Stone => &[
            (Id::StoneOrnateIntact, 5),
            (Id::StoneOrnateCracked, 8),
            (Id::StoneOrnateShattered, 2),
            (Id::StonePlain, 8),
            (Id::StoneMossy, 3),
        ],
        Terrain::Wood => &[(Id::WoodOak, 5), (Id::WoodRotted, 3), (Id::WoodCharred, 2)],
        Terrain::Iron => &[(Id::IronRusted, 5), (Id::IronClockwork, 2)],
        Terrain::Earth => &[(Id::EarthDry, 6), (Id::EarthWet, 4)],
        Terrain::Bone => &[(Id::BoneGravel, 3)],
        Terrain::Ash => &[(Id::AshBurned, 3)],
    }
}

fn choose_base(rng: &mut Rng, terrain: Terrain) -> TileId {
    let options = base_options(terrain);
    let total: u64 = options.iter().map(|(_, weight)| weight).sum();
    let mut draw = rng.below(total);
    for &(id, weight) in options {
        if draw < weight {
            return id;
        }
        draw -= weight;
    }
    options[0].0
}

fn transition(left: Terrain, right: Terrain) -> TileInstance {
    use Terrain::{Ash, Bone, Earth, Iron, Stone, Wood};
    let (id, turns) = match (left, right) {
        (Stone, Wood) => (TileId::EdgeStoneWood, 0),
        (Wood, Stone) => (TileId::EdgeStoneWood, 2),
        (Stone, Earth) => (TileId::EdgeStoneEarth, 0),
        (Earth, Stone) => (TileId::EdgeStoneEarth, 2),
        (Stone, Iron) => (TileId::EdgeStoneIron, 0),
        (Iron, Stone) => (TileId::EdgeStoneIron, 2),
        (Wood, Earth) => (TileId::EdgeWoodEarth, 0),
        (Earth, Wood) => (TileId::EdgeWoodEarth, 2),
        (Iron, Ash) => (TileId::EdgeIronAsh, 0),
        (Ash, Iron) => (TileId::EdgeIronAsh, 2),
        (Stone, Bone) => (TileId::EdgeStoneBone, 0),
        (Bone, Stone) => (TileId::EdgeStoneBone, 2),
        _ => unreachable!("district terrain sequence has no authored transition"),
    };
    TileInstance { id, turns }
}

fn puddle_kind(terrain: Terrain) -> u8 {
    match terrain {
        Terrain::Stone => 0,
        Terrain::Wood | Terrain::Iron | Terrain::Bone => 2,
        Terrain::Earth | Terrain::Ash => 1,
    }
}

/// Generate one room's 12 × 12 floor and ten visual puddles from its own seed.
/// The center stays flat and walkable for the current bullet-hell arena.
#[must_use]
pub fn generate_floor(seed: u64, district: ArenaDistrict) -> RoomFloor {
    let mut rng = Rng::new(seed ^ 0xF100_12E5_A11C_E123);
    let first_boundary = (3 + rng.below(3)) as u8;
    let second_boundary = first_boundary + 2 + rng.below(u64::from(7 - first_boundary)) as u8;
    let reflected = rng.below(2) == 1;
    let mut terrain_order = district.terrains();
    if reflected {
        terrain_order.reverse();
    }
    let mut tiles = [TileInstance {
        id: TileId::StonePlain,
        turns: 0,
    }; FLOOR_SIDE * FLOOR_SIDE];
    for row in 0..FLOOR_SIDE {
        for col in 0..FLOOR_SIDE {
            let cell = if col == first_boundary as usize {
                transition(terrain_order[0], terrain_order[1])
            } else if col == second_boundary as usize {
                transition(terrain_order[1], terrain_order[2])
            } else {
                let zone = usize::from(col > first_boundary as usize)
                    + usize::from(col > second_boundary as usize);
                TileInstance {
                    id: choose_base(&mut rng, terrain_order[zone]),
                    turns: 0,
                }
            };
            tiles[row * FLOOR_SIDE + col] = cell;
        }
    }

    let puddles = std::array::from_fn(|index| {
        let col = index % 5;
        let row = index / 5;
        let zone = if col < 2 {
            0
        } else if col == 2 {
            1
        } else {
            2
        };
        PuddlePlacement {
            kind: puddle_kind(terrain_order[zone]),
            x_cm: (-800 + col as i16 * 400) + rng.below(81) as i16 - 40,
            y_cm: (if row == 0 { -400 } else { 400 }) + rng.below(121) as i16 - 60,
            size_cm: 95 + rng.below(51) as u16,
        }
    });
    RoomFloor {
        seed,
        district,
        tiles,
        puddles,
        first_boundary,
        second_boundary,
        reflected,
    }
}

struct RegionSite {
    x: i32,
    y: i32,
    radius: f32,
    phase: f32,
    terrain: Terrain,
}

impl RegionSite {
    fn contains(&self, x: i32, y: i32) -> bool {
        let dx = x - self.x;
        let dy = y - self.y;
        // Reject most tiles before the trigonometry. All sites are at least 20
        // tiles from the world edge and at least 34 tiles from one another.
        let squared = dx * dx + dy * dy;
        if squared > 16 * 16 {
            return false;
        }
        let angle = dmath::atan2(dy as f32, dx as f32);
        let outline = self.radius
            * (0.83
                + 0.18 * dmath::sin(3.0 * angle + self.phase)
                + 0.12 * dmath::sin(5.0 * angle - self.phase * 0.7));
        squared as f32 <= outline * outline
    }
}

/// Seeded organic terrain plan, reusable across all 256 independently rendered
/// chunks. Construct it once per world; the free function below is a shortcut.
pub struct WorldPlan {
    seed: u64,
    background: Terrain,
    path_terrain: Terrain,
    path_phase: f32,
    path_second_phase: f32,
    sites: Vec<RegionSite>,
    terrain_map: Vec<Terrain>,
}

impl WorldPlan {
    /// Plan coherent regions for one world seed and biome.
    #[must_use]
    pub fn new(seed: u64, district: ArenaDistrict) -> Self {
        use Terrain::{Ash, Bone, Earth, Iron, Stone, Wood};
        // Buildings and ground have a dominant material. Ruined wooden floors,
        // scorched patches and bone beds form distinct islands within it.
        // Patch types never touch: every pair has an authored transition with
        // the background, while unsupported patch-to-patch seams are avoided.
        let [background, first, second] = match district {
            ArenaDistrict::Crypt => [Stone, Wood, Earth],
            ArenaDistrict::Foundry => [Iron, Stone, Ash],
            ArenaDistrict::Ossuary => [Stone, Earth, Bone],
        };
        let biome_salt = (district as u64 + 1).wrapping_mul(0xD1B5_4A32_D192_ED03);
        let mut rng = Rng::new(seed ^ biome_salt ^ 0x2E7A_1A9D_004D_2560);
        let path_phase = rng.below(628) as f32 / 100.0;
        let path_second_phase = rng.below(628) as f32 / 100.0;
        let mut sites: Vec<RegionSite> = Vec::with_capacity(24);
        for _ in 0..1000 {
            if sites.len() == 24 {
                break;
            }
            let x = 20 + rng.below(216) as i32;
            let y = 20 + rng.below(216) as i32;
            let first_patch = sites.len().is_multiple_of(2);
            let distance_to_path =
                (x as f32 - Self::path_center_at(y, path_phase, path_second_phase)).abs();
            let second_patch_clearance = (-16..=16).step_by(4).all(|offset| {
                (x as f32 - Self::path_center_at(y + offset, path_phase, path_second_phase)).abs()
                    >= 30.0
            });
            if (first_patch && distance_to_path > 35.0) || (!first_patch && !second_patch_clearance)
            {
                continue;
            }
            if sites.iter().any(|site| {
                let dx = site.x - x;
                let dy = site.y - y;
                dx * dx + dy * dy < 34 * 34
            }) {
                continue;
            }
            sites.push(RegionSite {
                x,
                y,
                radius: (9 + rng.below(5)) as f32,
                phase: rng.below(628) as f32 / 100.0,
                terrain: if first_patch { first } else { second },
            });
        }
        let mut plan = Self {
            seed,
            background,
            path_terrain: first,
            path_phase,
            path_second_phase,
            sites,
            terrain_map: Vec::new(),
        };
        let mut terrain_map: Vec<_> = (0..WORLD_SIDE * WORLD_SIDE)
            .map(|index| {
                plan.raw_terrain_at((index % WORLD_SIDE) as i32, (index / WORLD_SIDE) as i32)
            })
            .collect();
        merge_small_regions(&mut terrain_map);
        plan.terrain_map = terrain_map;
        plan
    }

    fn path_center_at(y: i32, phase: f32, second_phase: f32) -> f32 {
        128.0
            + 20.0 * dmath::sin(y as f32 * 0.025 + phase)
            + 11.0 * dmath::sin(y as f32 * 0.071 + second_phase)
    }

    fn raw_terrain_at(&self, x: i32, y: i32) -> Terrain {
        let x = x.clamp(0, WORLD_SIDE as i32 - 1);
        let y = y.clamp(0, WORLD_SIDE as i32 - 1);
        let center = Self::path_center_at(y, self.path_phase, self.path_second_phase);
        let half_width = 6.0 + 2.0 * dmath::sin(y as f32 * 0.044 + self.path_second_phase);
        if (x as f32 - center).abs() <= half_width {
            return self.path_terrain;
        }
        self.sites
            .iter()
            .find(|site| site.contains(x, y))
            .map_or(self.background, |site| site.terrain)
    }

    fn terrain_at(&self, x: i32, y: i32) -> Terrain {
        let x = x.clamp(0, WORLD_SIDE as i32 - 1) as usize;
        let y = y.clamp(0, WORLD_SIDE as i32 - 1) as usize;
        self.terrain_map[y * WORLD_SIDE + x]
    }

    /// One metre of floor, independent of how the renderer divides the map.
    #[must_use]
    pub fn tile(&self, x: usize, y: usize) -> Option<WorldTile> {
        if x >= WORLD_SIDE || y >= WORLD_SIDE {
            return None;
        }
        let col = x as i32;
        let row = y as i32;
        let terrain = self.terrain_at(col, row);
        let mut rng =
            Rng::new(self.seed ^ ((col as u64) << 32) ^ row as u64 ^ 0x7505_C0DE_A11C_E123);
        Some(WorldTile {
            visual: TileInstance {
                id: choose_base(&mut rng, terrain),
                turns: 0,
            },
            terrain,
            adjacent: [
                self.terrain_at(col, row + 1),
                self.terrain_at(col + 1, row),
                self.terrain_at(col, row - 1),
                self.terrain_at(col - 1, row),
            ],
        })
    }

    /// Generate a section from this plan, with no seam at a chunk boundary.
    #[must_use]
    pub fn chunk(&self, chunk_x: usize, chunk_y: usize) -> Option<WorldChunk> {
        generate_chunk_from_plan(self, chunk_x, chunk_y)
    }
}

fn merge_small_regions(map: &mut [Terrain]) {
    const PALETTE: [Terrain; 6] = [
        Terrain::Stone,
        Terrain::Wood,
        Terrain::Iron,
        Terrain::Earth,
        Terrain::Bone,
        Terrain::Ash,
    ];
    loop {
        let snapshot = map.to_vec();
        let mut seen = vec![false; map.len()];
        let mut merged = false;
        for start in 0..map.len() {
            if seen[start] {
                continue;
            }
            let mut cells = Vec::new();
            let mut queue = VecDeque::from([start]);
            let mut neighbours = [0_usize; 6];
            seen[start] = true;
            while let Some(index) = queue.pop_front() {
                cells.push(index);
                let x = index % WORLD_SIDE;
                let y = index / WORLD_SIDE;
                for next in [
                    (x > 0).then(|| index - 1),
                    (x + 1 < WORLD_SIDE).then(|| index + 1),
                    (y > 0).then(|| index - WORLD_SIDE),
                    (y + 1 < WORLD_SIDE).then(|| index + WORLD_SIDE),
                ]
                .into_iter()
                .flatten()
                {
                    if snapshot[next] != snapshot[start] {
                        neighbours[snapshot[next] as usize] += 1;
                    } else if !seen[next] {
                        seen[next] = true;
                        queue.push_back(next);
                    }
                }
            }
            if cells.len() < 32
                && let Some((colour, _)) = neighbours
                    .iter()
                    .enumerate()
                    .filter(|(_, count)| **count > 0)
                    .max_by_key(|(_, count)| **count)
            {
                for index in cells {
                    map[index] = PALETTE[colour];
                }
                // One component per pass makes the count of connected
                // regions fall strictly; two small neighbours cannot swap
                // colours forever in the same pass.
                merged = true;
                break;
            }
        }
        if !merged {
            break;
        }
    }
}

/// Generate a 16 by 16 metre world section without allocating a world-sized
/// texture. Any section can be regenerated from its seed and coordinates.
/// Irregular regions have a minimum contiguous area of 32 tiles; blending at
/// their edges needs the adjacent terrain labels carried by [`WorldTile`].
#[must_use]
pub fn generate_world_chunk(
    seed: u64,
    district: ArenaDistrict,
    chunk_x: usize,
    chunk_y: usize,
) -> Option<WorldChunk> {
    WorldPlan::new(seed, district).chunk(chunk_x, chunk_y)
}

fn generate_chunk_from_plan(
    layout: &WorldPlan,
    chunk_x: usize,
    chunk_y: usize,
) -> Option<WorldChunk> {
    if chunk_x >= WORLD_CHUNKS_PER_SIDE || chunk_y >= WORLD_CHUNKS_PER_SIDE {
        return None;
    }
    let tiles = std::array::from_fn(|index| {
        let col = chunk_x * WORLD_CHUNK_SIDE + index % WORLD_CHUNK_SIDE;
        let row = chunk_y * WORLD_CHUNK_SIDE + index / WORLD_CHUNK_SIDE;
        layout
            .tile(col, row)
            .expect("chunk coordinates are in world")
    });
    let mut puddles = Vec::new();
    for local_y in 0..WORLD_CHUNK_SIDE {
        for local_x in 0..WORLD_CHUNK_SIDE {
            let col = chunk_x * WORLD_CHUNK_SIDE + local_x;
            let row = chunk_y * WORLD_CHUNK_SIDE + local_y;
            let terrain = layout.terrain_at(col as i32, row as i32);
            // Per-tile rolls avoid a telltale fixed count or a repeated chunk grid.
            let mut rng =
                Rng::new(layout.seed ^ ((col as u64) << 32) ^ (row as u64) ^ 0xD00D_1E55_2560_0001);
            let density = match terrain {
                Terrain::Earth | Terrain::Ash => 6,
                Terrain::Wood | Terrain::Bone => 4,
                Terrain::Stone | Terrain::Iron => 3,
            };
            if rng.below(256) >= density {
                continue;
            }
            let size_cm = 28 + rng.below(27) as u16;
            // Source puddles are 3:2. Half-width <= 41 cm, half-height <= 27 cm.
            // The 42..58 / 28..72 cm centre range leaves the silhouette on its tile.
            let offset_x = 42 + rng.below(17) as i16;
            let offset_y = 28 + rng.below(45) as i16;
            puddles.push(PuddlePlacement {
                kind: puddle_kind(terrain),
                x_cm: (col as i16 - 128) * 100 + offset_x,
                y_cm: (row as i16 - 128) * 100 + offset_y,
                size_cm,
            });
        }
    }
    Some(WorldChunk {
        x: chunk_x as u8,
        y: chunk_y as u8,
        tiles,
        puddles,
    })
}

/// Ordered half-edge labels for N/E/S/W. Each pair is ordered left-to-right
/// along horizontal edges or top-to-bottom along vertical edges.
fn edges(cell: TileInstance) -> [[Terrain; 2]; 4] {
    let (left, right) = cell.id.terrains();
    let mut profile = [[left, right], [right, right], [left, right], [left, left]];
    for _ in 0..cell.turns {
        let [north, east, south, west] = profile;
        profile = [west, north, [east[1], east[0]], [south[1], south[0]]];
    }
    profile
}

/// Verify socket compatibility and the guaranteed walkable flat tile area.
/// `Err` names the first mismatched cell and side.
pub fn validate_floor(floor: &RoomFloor) -> Result<(), (usize, usize, &'static str)> {
    for row in 0..FLOOR_SIDE {
        for col in 0..FLOOR_SIDE {
            let here = edges(floor.tiles[row * FLOOR_SIDE + col]);
            if col + 1 < FLOOR_SIDE {
                let next = edges(floor.tiles[row * FLOOR_SIDE + col + 1]);
                if here[1] != next[3] {
                    return Err((row, col, "east"));
                }
            }
            if row + 1 < FLOOR_SIDE {
                let next = edges(floor.tiles[(row + 1) * FLOOR_SIDE + col]);
                if here[2] != next[0] {
                    return Err((row, col, "south"));
                }
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::collections::{BTreeSet, VecDeque};

    use super::*;

    #[test]
    fn ten_thousand_seeds_make_valid_repeatable_rooms_and_chains() {
        let mut signatures = BTreeSet::new();
        for seed in 0..10_000 {
            let plan = generate_run(seed);
            assert_eq!(plan, generate_run(seed));
            let mut districts = BTreeSet::new();
            for (index, stage) in plan.stages.iter().enumerate() {
                assert!(districts.insert(stage.district));
                assert!((5..=8).contains(&stage.rooms.len()));
                assert_eq!(stage.rooms[0].kind, RoomKind::Intro);
                assert_eq!(stage.rooms.last().unwrap().kind, RoomKind::Boss);
                assert!(stage.rooms.iter().any(|room| room.kind == RoomKind::Altar));
                assert!(
                    stage
                        .rooms
                        .iter()
                        .any(|room| room.kind == RoomKind::Miniboss)
                );
                assert_eq!(stage.shop_after, index < 2);
                for room in &stage.rooms {
                    assert!(room.corruption_grade <= 3);
                }
                let room = generate_floor(stage.rooms[0].floor_seed, stage.district);
                assert_eq!(
                    room,
                    generate_floor(stage.rooms[0].floor_seed, stage.district)
                );
                assert_eq!(validate_floor(&room), Ok(()));
                assert_eq!(room.puddles.len(), PUDDLES_PER_ROOM);
                let species: BTreeSet<_> = room.puddles.iter().map(|puddle| puddle.kind).collect();
                assert_eq!(species.len(), 3);
                for puddle in room.puddles {
                    assert!(
                        i32::from(puddle.x_cm.abs()) + i32::from(puddle.size_cm) * 3 / 4 < 1050
                    );
                    assert!(i32::from(puddle.y_cm.abs()) + i32::from(puddle.size_cm) / 2 < 700);
                }
            }
            assert_eq!(districts.len(), 3);
            if seed < 100 {
                signatures.insert(format!(
                    "{:?}",
                    plan.stages
                        .iter()
                        .map(|stage| (stage.district, stage.rooms.len()))
                        .collect::<Vec<_>>()
                ));
            }
        }
        assert!(
            signatures.len() >= 20,
            "only {} different stage structures",
            signatures.len()
        );
    }

    #[test]
    fn changing_the_room_seed_changes_its_floor() {
        let first = generate_floor(41, ArenaDistrict::Crypt);
        let second = generate_floor(42, ArenaDistrict::Crypt);
        assert_ne!(first.tiles, second.tiles);
        assert_ne!(first.puddles, second.puddles);
    }

    #[test]
    fn all_twenty_authored_tiles_reach_generated_rooms() {
        let mut seen = BTreeSet::new();
        for seed in 0..100 {
            for district in [
                ArenaDistrict::Crypt,
                ArenaDistrict::Foundry,
                ArenaDistrict::Ossuary,
            ] {
                for cell in generate_floor(seed, district).tiles {
                    seen.insert(cell.id as u8);
                }
            }
        }
        assert_eq!(seen.len(), 20);
    }

    #[test]
    fn metre_scale_world_chunks_cover_256_metres_without_chunk_seams() {
        assert_eq!(WORLD_SIDE * WORLD_TILE_SIZE_M as usize, 256);
        assert_eq!(WORLD_CHUNKS_PER_SIDE * WORLD_CHUNK_SIDE, WORLD_SIDE);
        for district in [
            ArenaDistrict::Crypt,
            ArenaDistrict::Foundry,
            ArenaDistrict::Ossuary,
        ] {
            let plan = WorldPlan::new(41, district);
            let chunks: Vec<_> = (0..WORLD_CHUNKS_PER_SIDE)
                .flat_map(|y| {
                    let plan = &plan;
                    (0..WORLD_CHUNKS_PER_SIDE).map(move |x| plan.chunk(x, y).unwrap())
                })
                .collect();
            for row in 0..WORLD_SIDE {
                for col in 0..WORLD_SIDE {
                    let chunk = &chunks
                        [(row / WORLD_CHUNK_SIDE) * WORLD_CHUNKS_PER_SIDE + col / WORLD_CHUNK_SIDE];
                    let local =
                        (row % WORLD_CHUNK_SIDE) * WORLD_CHUNK_SIDE + col % WORLD_CHUNK_SIDE;
                    let here = chunk.tiles[local];
                    assert_eq!(here.visual.id.terrains(), (here.terrain, here.terrain));
                    if col + 1 < WORLD_SIDE {
                        let next_chunk = &chunks[(row / WORLD_CHUNK_SIDE) * WORLD_CHUNKS_PER_SIDE
                            + (col + 1) / WORLD_CHUNK_SIDE];
                        let next = next_chunk.tiles[(row % WORLD_CHUNK_SIDE) * WORLD_CHUNK_SIDE
                            + (col + 1) % WORLD_CHUNK_SIDE];
                        assert_eq!(here.adjacent[1], next.terrain, "east gap at {col},{row}");
                        assert_eq!(next.adjacent[3], here.terrain);
                        if here.terrain != next.terrain {
                            transition(here.terrain, next.terrain);
                        }
                    }
                    if row + 1 < WORLD_SIDE {
                        let next_chunk = &chunks[((row + 1) / WORLD_CHUNK_SIDE)
                            * WORLD_CHUNKS_PER_SIDE
                            + col / WORLD_CHUNK_SIDE];
                        let next = next_chunk.tiles[((row + 1) % WORLD_CHUNK_SIDE)
                            * WORLD_CHUNK_SIDE
                            + col % WORLD_CHUNK_SIDE];
                        assert_eq!(here.adjacent[0], next.terrain, "north gap at {col},{row}");
                        assert_eq!(next.adjacent[2], here.terrain);
                        if here.terrain != next.terrain {
                            transition(here.terrain, next.terrain);
                        }
                    }
                }
            }
            assert_eq!(chunks.len() * WORLD_CHUNK_SIDE * WORLD_CHUNK_SIDE, 65_536);
            let counts: std::collections::BTreeSet<_> =
                chunks.iter().map(|chunk| chunk.puddles.len()).collect();
            assert!(counts.len() > 1, "puddle counts must vary across chunks");
            assert!(
                chunks
                    .iter()
                    .flat_map(|chunk| &chunk.puddles)
                    .all(|puddle| {
                        let col = (i32::from(puddle.x_cm) + 12_800).div_euclid(100);
                        let row = (i32::from(puddle.y_cm) + 12_800).div_euclid(100);
                        let offset_x = (i32::from(puddle.x_cm) + 12_800).rem_euclid(100);
                        let offset_y = (i32::from(puddle.y_cm) + 12_800).rem_euclid(100);
                        let half_width = i32::from(puddle.size_cm) * 3 / 4;
                        let half_height = i32::from(puddle.size_cm) / 2;
                        (0..256).contains(&col)
                            && (0..256).contains(&row)
                            && offset_x >= half_width
                            && offset_x + half_width <= 100
                            && offset_y >= half_height
                            && offset_y + half_height <= 100
                    })
            );
        }
        assert!(generate_world_chunk(41, ArenaDistrict::Crypt, 16, 0).is_none());
    }

    #[test]
    fn world_chunks_are_independent_and_repeatable() {
        let a = generate_world_chunk(41, ArenaDistrict::Crypt, 7, 8).unwrap();
        assert_eq!(
            a,
            generate_world_chunk(41, ArenaDistrict::Crypt, 7, 8).unwrap()
        );
        assert_ne!(
            a,
            generate_world_chunk(42, ArenaDistrict::Crypt, 7, 8).unwrap()
        );
        assert_ne!(
            a,
            generate_world_chunk(41, ArenaDistrict::Crypt, 8, 8).unwrap()
        );
    }

    #[test]
    fn every_organic_region_has_at_least_32_connected_tiles() {
        for seed in 0..100 {
            for district in [
                ArenaDistrict::Crypt,
                ArenaDistrict::Foundry,
                ArenaDistrict::Ossuary,
            ] {
                let plan = WorldPlan::new(seed, district);
                let mut terrain = vec![Terrain::Stone; WORLD_SIDE * WORLD_SIDE];
                for cy in 0..WORLD_CHUNKS_PER_SIDE {
                    for cx in 0..WORLD_CHUNKS_PER_SIDE {
                        let chunk = plan.chunk(cx, cy).unwrap();
                        for local_y in 0..WORLD_CHUNK_SIDE {
                            for local_x in 0..WORLD_CHUNK_SIDE {
                                let x = cx * WORLD_CHUNK_SIDE + local_x;
                                let y = cy * WORLD_CHUNK_SIDE + local_y;
                                terrain[y * WORLD_SIDE + x] =
                                    chunk.tiles[local_y * WORLD_CHUNK_SIDE + local_x].terrain;
                            }
                        }
                    }
                }
                let mut seen = vec![false; terrain.len()];
                let mut regions = 0;
                for start in 0..terrain.len() {
                    if seen[start] {
                        continue;
                    }
                    let mut queue = VecDeque::from([start]);
                    seen[start] = true;
                    let mut area = 0;
                    while let Some(index) = queue.pop_front() {
                        area += 1;
                        let x = index % WORLD_SIDE;
                        let y = index / WORLD_SIDE;
                        for neighbor in [
                            (x > 0).then(|| index - 1),
                            (x + 1 < WORLD_SIDE).then(|| index + 1),
                            (y > 0).then(|| index - WORLD_SIDE),
                            (y + 1 < WORLD_SIDE).then(|| index + WORLD_SIDE),
                        ]
                        .into_iter()
                        .flatten()
                        {
                            if !seen[neighbor] && terrain[neighbor] == terrain[start] {
                                seen[neighbor] = true;
                                queue.push_back(neighbor);
                            }
                        }
                    }
                    assert!(
                        area >= 32,
                        "seed {seed}, {district:?}, region {regions} at ({}, {}) {:?}: {area} tiles",
                        start % WORLD_SIDE,
                        start / WORLD_SIDE,
                        terrain[start]
                    );
                    regions += 1;
                }
                assert!(
                    regions >= 10,
                    "seed {seed}, {district:?}: only {regions} regions"
                );
            }
        }
    }
}
