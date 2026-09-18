//! # fnp_app
//!
//! The Fiends n Patrons executable as a library: command line ([`cli`]), loading the figure pack
//! and the stage geometry through the engine's asset hook ([`figures`]), and the arena's
//! presentation plugin with the app that runs it in the engine's main loop ([`stage`]).
//! `src/main.rs` opens the window; integration tests drive the same app headless or offscreen.

pub mod arena_floor;
pub mod arena_puddles;
pub mod cli;
pub mod figures;
pub mod stage;
