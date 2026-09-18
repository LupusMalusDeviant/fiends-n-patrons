//! Render the logical 256 m terrain map to a tiny CPU-only PPM preview.
//! Usage: cargo run -p fnp_game --example world_map -- 41 crypt preview.ppm

use std::fs;

use fnp_game::worldgen::{
    ArenaDistrict, Terrain, WORLD_CHUNK_SIDE, WORLD_CHUNKS_PER_SIDE, WORLD_SIDE, WorldPlan,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().collect();
    if args.len() != 4 {
        return Err("usage: world_map <seed> <crypt|foundry|ossuary> <output.ppm>".into());
    }
    let seed: u64 = args[1].parse()?;
    let district = ArenaDistrict::parse(&args[2]).ok_or("unknown district")?;
    let plan = WorldPlan::new(seed, district);
    let mut pixels = vec![0_u8; WORLD_SIDE * WORLD_SIDE * 3];
    for cy in 0..WORLD_CHUNKS_PER_SIDE {
        for cx in 0..WORLD_CHUNKS_PER_SIDE {
            let chunk = plan.chunk(cx, cy).expect("in-range chunk");
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
                    let dst = ((WORLD_SIDE - 1 - y) * WORLD_SIDE + x) * 3;
                    pixels[dst..dst + 3].copy_from_slice(&color);
                }
            }
        }
    }
    let mut ppm = format!("P6\n{WORLD_SIDE} {WORLD_SIDE}\n255\n").into_bytes();
    ppm.extend_from_slice(&pixels);
    fs::write(&args[3], ppm)?;
    Ok(())
}
