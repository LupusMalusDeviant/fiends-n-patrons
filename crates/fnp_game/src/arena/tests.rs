use grimoire::collide::{Circle, CollisionQuery, Shape, overlaps};
use grimoire::sigil::{AimTarget, BulletPool, Emitter};

use super::*;

const FULL: i16 = i16::MAX;

fn built(seed: u64) -> Simulation {
    let mut sim = Simulation::new(seed);
    ArenaGame::new().build(&mut sim);
    sim
}

fn input(x: i16, y: i16) -> TickInput {
    let mut input = TickInput::default();
    input.slots[0].axes[0] = x;
    input.slots[0].axes[1] = y;
    input
}

fn player(sim: &Simulation) -> (Vec2, Vec2) {
    sim.world()
        .query::<(&Position, &Velocity, &Player)>()
        .next()
        .map(|(position, velocity, _)| (position.at, velocity.value))
        .expect("the player exists")
}

fn round(sim: &Simulation) -> RoundState {
    *sim.world().resource::<RoundState>().expect("round state")
}

fn bullets(sim: &Simulation) -> usize {
    sim.world()
        .resource::<BulletPool>()
        .map_or(0, |pool| pool.len() as usize)
}

#[test]
fn build_spawns_player_imp_two_emitters_and_the_interpreter() {
    let sim = built(1);
    let world = sim.world();
    assert_eq!(world.query::<&Player>().count(), 1);
    assert_eq!(world.query::<&Imp>().count(), 1);
    assert_eq!(world.query::<&Emitter>().count(), 2);
    assert!(world.resource::<BulletPool>().is_some());
    assert!(world.resource::<SpatialGrid>().is_some());
    assert_eq!(round(&sim), RoundState::first());
    assert_eq!(player(&sim).0, PLAYER_START);
}

#[test]
fn the_player_reaches_ninety_percent_speed_within_three_ticks() {
    // PRD-0005 FR-01: reaction below 3 sim ticks to 90 % of the target speed.
    let mut sim = built(1);
    for _ in 0..3 {
        sim.step(input(FULL, 0));
    }
    let (_, velocity) = player(&sim);
    let target = PLAYER_SPEED * (f32::from(FULL) / 32_767.0);
    assert!(velocity.x >= 0.9 * target, "velocity {velocity:?}");
    // Light momentum: releasing the stick glides on for a moment.
    sim.step(TickInput::default());
    assert!(player(&sim).1.x > 0.0);
}

#[test]
fn the_player_stays_in_the_arena_and_out_of_the_imp() {
    let mut sim = built(2);
    // Start next to the corner, before the imp's first volley can interfere.
    for (position, _) in sim.world_mut().query_mut::<(&mut Position, &Player)>() {
        position.at = Vec2::new(0.5 - ARENA_HALF.x, 0.5 - ARENA_HALF.y);
    }
    for _ in 0..30 {
        sim.step(input(-FULL, -FULL));
    }
    let (at, velocity) = player(&sim);
    assert_eq!(at, Vec2::new(-ARENA_HALF.x, -ARENA_HALF.y));
    assert_eq!(velocity, Vec2::ZERO);

    // Walk straight into the imp from below.
    let mut sim = built(2);
    for _ in 0..240 {
        sim.step(input(0, FULL));
        if round(&sim).phase != Phase::Fighting {
            break;
        }
    }
    let (at, _) = player(&sim);
    assert!(
        at.distance(IMP_POSITION) >= IMP_BODY_RADIUS - 1.0e-4,
        "{at:?}"
    );
}

#[test]
fn the_aim_target_follows_the_player() {
    let mut sim = built(3);
    for _ in 0..30 {
        sim.step(input(FULL, 0));
    }
    let aim = sim.world().resource::<AimTarget>().expect("aim target").0;
    assert_eq!(aim, Some(player(&sim).0));
}

#[test]
fn the_imp_waits_for_the_telegraph_delay_then_fires_both_emitters() {
    let mut sim = built(4);
    // The volley has `delay = 60t`: nothing is emitted before tick 60.
    for _ in 0..60 {
        sim.step(input(FULL, 0));
    }
    assert_eq!(bullets(&sim), 0);
    sim.step(input(FULL, 0));
    assert_eq!(bullets(&sim), 5, "the aimed fan has five embers");
    for _ in 0..30 {
        sim.step(input(FULL, 0));
    }
    // The ring (`delay = 85t`) has fired its fourteen thorns too.
    assert_eq!(bullets(&sim), 5 + 14);
}

#[test]
fn an_idle_player_is_hit_and_the_round_restarts_after_the_recovery() {
    let mut sim = built(5);
    let mut hit_at = None;
    for _ in 0..600 {
        sim.step(TickInput::default());
        if let Phase::Hit { at_tick } = round(&sim).phase {
            hit_at = Some(at_tick);
            break;
        }
    }
    let hit_at = hit_at.expect("the aimed fan hits a player who does not move");
    let state = round(&sim);
    assert_eq!(state.hits, 1);
    assert_eq!(state.last_hit_position, PLAYER_START);
    for emitter in sim.world().query::<&Emitter>() {
        assert_eq!(emitter.started_at, hit_at + HIT_RECOVERY_TICKS);
    }

    // Input is ignored while the round is lost, and the clear request empties the pool.
    for _ in 0..10 {
        sim.step(input(FULL, FULL));
    }
    assert_eq!(player(&sim).0, PLAYER_START);
    assert_eq!(bullets(&sim), 0);

    while sim.tick() <= hit_at + HIT_RECOVERY_TICKS {
        assert_ne!(round(&sim).phase, Phase::Fighting);
        sim.step(input(FULL, FULL));
    }
    let state = round(&sim);
    assert_eq!(state.phase, Phase::Fighting);
    assert_eq!(state.round, 2);
    assert_eq!(state.started_at, hit_at + HIT_RECOVERY_TICKS);
    assert_eq!(player(&sim).0, PLAYER_START);
    for emitter in sim.world().query::<&Emitter>() {
        assert_eq!(emitter.started_at, state.started_at);
    }
}

#[test]
fn a_hit_needs_an_actual_overlap_with_the_capsule() {
    let shape = player_hit_shape(Vec2::ZERO);
    let reach = PLAYER_HIT_HALF_WIDTH + PLAYER_HIT_RADIUS;
    let touching = Shape::Circle(Circle {
        center: Vec2::new(reach + 0.2, 0.0),
        radius: 0.21,
    });
    let missing = Shape::Circle(Circle {
        center: Vec2::new(reach + 0.2, 0.0),
        radius: 0.19,
    });
    assert!(overlaps(&shape, &touching));
    assert!(!overlaps(&shape, &missing));
    // Narrower front to back than side to side.
    let front = Shape::Circle(Circle {
        center: Vec2::new(0.0, PLAYER_HIT_RADIUS + 0.2),
        radius: 0.19,
    });
    assert!(!overlaps(&shape, &front));
}

#[test]
fn the_broadphase_holds_every_live_bullet() {
    let mut sim = built(6);
    for _ in 0..100 {
        sim.step(input(FULL, 0));
    }
    let grid = sim.world().resource::<SpatialGrid>().expect("grid");
    assert_eq!(grid.len(), bullets(&sim));
    assert!(grid.len() > 0);
}

#[test]
fn bullets_leave_through_the_bounds_and_the_pool_stays_bounded() {
    // Circle along the arena edge for a minute; the pool never fills up.
    let mut sim = built(7);
    let mut peak = 0;
    for tick in 0..3_600_u64 {
        let phase = tick % 480;
        let (x, y) = match phase {
            0..120 => (FULL, 0),
            120..240 => (0, FULL),
            240..360 => (-FULL, 0),
            _ => (0, -FULL),
        };
        sim.step(input(x, y));
        peak = peak.max(bullets(&sim));
    }
    let pool = sim.world().resource::<BulletPool>().expect("pool");
    assert_eq!(pool.dropped_spawns(), 0);
    assert!(peak < BULLET_CAPACITY as usize / 4, "peak {peak}");
    let _ = sim.state_hash();
}

#[test]
fn identical_input_gives_identical_state_and_different_input_does_not() {
    let script = |tick: u64| {
        if tick % 200 < 100 {
            input(FULL, (tick % 60) as i16 * 400)
        } else {
            input(-FULL, 0)
        }
    };
    let mut first = built(9);
    let mut second = built(9);
    let mut idle = built(9);
    for tick in 0..900 {
        first.step(script(tick));
        second.step(script(tick));
        idle.step(TickInput::default());
    }
    assert_eq!(first.state_hash(), second.state_hash());
    assert_ne!(player(&first).0, player(&idle).0);
}

#[test]
fn the_grid_covers_the_bullet_bounds() {
    let grid = SpatialGrid::new(grid_config()).expect("valid grid");
    let config = grid.config();
    let far = ARENA_HALF + Vec2::splat(BULLET_BOUNDS_MARGIN);
    assert!(config.origin.x <= -far.x && config.origin.y <= -far.y);
    assert!(config.origin.x + config.cell_size * config.columns as f32 >= far.x);
    assert!(config.origin.y + config.cell_size * config.rows as f32 >= far.y);
    assert!(grid.is_empty());
}
