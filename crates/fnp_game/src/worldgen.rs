//! Deterministic run plans and floor layouts. This module has no renderer state:
//! the same `(seed, room)` always produces the same rooms, tiles and puddles.
//! Straight material bands reflect the six authored transition tiles; arbitrary
//! corners and junctions need more art before they can be admitted here.

/// Tiles along either axis of one 48 m floor.
pub const FLOOR_SIDE: usize = 12;
/// Edge length of one authored tile in metres.
pub const TILE_SIZE_M: u32 = 4;
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
    use std::collections::BTreeSet;

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
}
