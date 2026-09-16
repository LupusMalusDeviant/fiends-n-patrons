"""Deterministic gothic object sprites for the protected projectile pass.

These illustrated RGBA sprites use natural material colors with reserved team
colors as accents. They are unlit artwork, not tileable PBR base-color maps.
All geometry and marks come from local code, without images or external assets.
"""

from __future__ import annotations

import math

import numpy as np

from arrow_art import render_arrow
from bomb_art import render_bomb


_CATALOG = (
    ("hunter_arrow", "Jagdpfeil", "player", "arrow", "#8FE8FF", "#E9FAFF"),
    ("barbed_arrow", "Widerhakenpfeil", "hostile", "arrow", "#FF2FB4", "#FFE3F4"),
    ("crossbow_bolt", "Armbrustbolzen", "hostile", "arrow", "#B6FF2E", "#F6FFE0"),
    ("bone_lance", "Knochenlanze", "hostile", "arrow", "#FF2FB4", "#FFE3F4"),
    ("plague_flask", "Pestphiole", "hostile", "bomb", "#B6FF2E", "#F6FFE0"),
    ("reliquary_bomb", "Reliquienbombe", "hostile", "bomb", "#FF2FB4", "#FFE3F4"),
    ("censer_bomb", "Raeucherfass-Bombe", "hostile", "bomb", "#FF2FB4", "#FFE3F4"),
    ("alchemical_grenade", "Alchemistische Granate", "player", "bomb", "#8FE8FF", "#E9FAFF"),
)


def projectile_catalog() -> list[dict]:
    """Return independent design proposals; team assignments imply no mechanics."""
    return [
        {
            "id": sprite_id,
            "label": label,
            "team": team,
            "family": family,
            "silhouette": sprite_id,
            "signal_hex": signal,
            "core_hex": core,
            "design_status": "proposal_gothic_objects_v3",
            "style": "natural_materials_with_restrained_magic_accents",
            "render_type": "unlit_sprite",
            "render_pass": "protected_projectile",
            "blend": "straight_alpha",
            "premultiplied_alpha": False,
            "mipmaps": False,
            "mipmap_policy": "pending_runtime_alpha_aware_sprite_policy",
            "tileable": False,
            "texture_semantic": "unlit_illustration_rgba",
            "rgb_color_space": "sRGB",
            "alpha_color_space": "linear",
            "forward_axis": "+X" if family == "arrow" else None,
            "orientation": "tip_right" if family == "arrow" else "upright_item",
            "rotation_pivot_uv": [0.5, 0.5],
            "minimum_transparent_padding_fraction": 0.08,
            "game_preview_sizes": [32, 48, 64],
            "suggested_minimum_screen_extent_px": 48,
            "generation": "procedural_pillow_numpy_no_randomness",
        }
        for sprite_id, label, team, family, signal, core in _CATALOG
    ]


def make_projectile(spec: dict, size: int) -> np.ndarray:
    """Create HxWx4 uint8, straight-alpha artwork with no I/O side effects."""
    if isinstance(size, bool) or not isinstance(size, (int, np.integer)) or not 16 <= size <= 4096:
        raise ValueError("Projectile size must be an integer between 16 and 4096")
    if spec.get("render_type") != "unlit_sprite" or spec.get("blend") != "straight_alpha":
        raise ValueError("This generator produces unlit straight-alpha sprites only")
    if spec["family"] not in ("arrow", "bomb"):
        raise ValueError("Unknown projectile family")
    renderer = render_arrow if spec["family"] == "arrow" else render_bomb
    pixels = renderer(spec["id"], int(size), spec["signal_hex"], spec["core_hex"])
    # Downsampling can spread faint filter ringing into the empty border.
    # Apply the same coverage contract to every supported output resolution.
    padding = math.ceil(size * spec["minimum_transparent_padding_fraction"])
    pixels[:padding] = 0
    pixels[-padding:] = 0
    pixels[:, :padding] = 0
    pixels[:, -padding:] = 0
    # Uniform transparent texels for predictable downstream inspection. Coverage
    # filtering must still be alpha-aware; zero RGB cannot replace that policy.
    pixels[pixels[..., 3] == 0, :3] = 0
    return pixels
