//! # fnp_app
//!
//! The Fiends n Patrons executable as a library: command line ([`cli`]), loading the figure pack
//! and the stage geometry into the window renderer ([`figures`]) and the main loop
//! ([`game_loop`]). `src/main.rs` wires them to the desktop runner; integration tests drive the
//! same loop headless or offscreen.

pub mod cli;
pub mod figures;
pub mod game_loop;

use std::sync::Arc;

use grimoire::platform::PlatformWindow;
use grimoire::render::{LightBudget, Renderer, RendererConfig, StageRendererConfig, WgpuRenderer};

use crate::game_loop::LoopError;

/// Renderer configuration of the game: the high point-light budget (the arena's torches plus
/// bullet lights) and 4x multisampling.
#[must_use]
pub fn stage_renderer_config() -> StageRendererConfig {
    let mut config = StageRendererConfig::default();
    config.base = RendererConfig {
        vsync: true,
        allow_software_fallback: true,
        ..RendererConfig::default()
    };
    config.light_budget = LightBudget::High;
    config
}

/// Creates the window renderer, sized to the window's current drawable size.
///
/// # Errors
/// [`LoopError::Render`] if no suitable adapter or surface is available.
pub fn window_renderer(window: &Arc<dyn PlatformWindow>) -> Result<WgpuRenderer, LoopError> {
    let mut renderer =
        WgpuRenderer::new_for_window_staged(Arc::clone(window), stage_renderer_config())?;
    let size = window.inner_size();
    renderer.resize(size.width, size.height);
    Ok(renderer)
}
