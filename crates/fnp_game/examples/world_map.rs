//! Export a logical 256 m world for CPU-only preview rendering. `.ppm` gives
//! a schematic map; `.fmap` carries exact tile IDs and puddle placements.
//! Usage: cargo run -p fnp_game --example world_map -- 41 crypt preview.fmap

use std::fs;

use fnp_game::worldgen::{
    ArenaDistrict, Terrain, WORLD_CHUNK_SIDE, WORLD_CHUNKS_PER_SIDE, WORLD_SIDE, WorldPlan,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().collect();
    if args.len() != 4 {
        return Err(
            "usage: world_map <seed> <crypt|foundry|ossuary> <output.ppm|output.fmap>".into(),
        );
    }
    let seed: u64 = args[1].parse()?;
    let district = ArenaDistrict::parse(&args[2]).ok_or("unknown district")?;
    let plan = WorldPlan::new(seed, district);
    let mut pixels = vec![0_u8; WORLD_SIDE * WORLD_SIDE * 3];
    let mut tile_ids = vec![0_u8; WORLD_SIDE * WORLD_SIDE];
    let mut puddles = Vec::new();
    for cy in 0..WORLD_CHUNKS_PER_SIDE {
        for cx in 0..WORLD_CHUNKS_PER_SIDE {
            let chunk = plan.chunk(cx, cy).expect("in-range chunk");
            puddles.extend(chunk.puddles);
            for ly in 0..WORLD_CHUNK_SIDE {
                for lx in 0..WORLD_CHUNK_SIDE {
                    let tile = chunk.tiles[ly * WORLD_CHUNK_SIDE + lx];
                    let color = match tile.terrain {
                        Terrain::Stone => [106, 108, 111],
                        Terrain::Wood => [110, 72, 47],
                        Terrain::Iron => [80, 84, 91],
                        Terrain::Earth => [118, 87, 59],
                        Terrain::Bone => [182, 167, 136],
                        Terrain::Ash => [47, 44, 45],
                    };
                    let x = cx * WORLD_CHUNK_SIDE + lx;
                    let y = cy * WORLD_CHUNK_SIDE + ly;
                    tile_ids[y * WORLD_SIDE + x] = tile.visual.id as u8;
                    let dst = ((WORLD_SIDE - 1 - y) * WORLD_SIDE + x) * 3;
                    pixels[dst..dst + 3].copy_from_slice(&color);
                }
            }
        }
    }
    if args[3].ends_with(".fmap") {
        let mut data = b"FNPMAP1\0".to_vec();
        data.extend_from_slice(&tile_ids);
        data.extend_from_slice(&(puddles.len() as u32).to_le_bytes());
        for puddle in puddles {
            data.push(puddle.kind);
            data.extend_from_slice(&puddle.x_cm.to_le_bytes());
            data.extend_from_slice(&puddle.y_cm.to_le_bytes());
            data.extend_from_slice(&puddle.size_cm.to_le_bytes());
        }
        fs::write(&args[3], data)?;
        return Ok(());
    }
    let mut ppm = format!("P6\n{WORLD_SIDE} {WORLD_SIDE}\n255\n").into_bytes();
    ppm.extend_from_slice(&pixels);
    fs::write(&args[3], ppm)?;
    Ok(())
}
