"""Left/right joint names without Blender: the name a joint gets when a rig's sides swap."""

from __future__ import annotations

import re

_SIDE_SUFFIX = re.compile(r"(?<=[._])([LlRr])$")
_SWAP = {"L": "R", "R": "L", "l": "r", "r": "l"}


def swapped_side_name(name: str) -> str | None:
    """`hand.L` -> `hand.R`, `socket_weapon_r` -> `socket_weapon_l`; `None` without a side suffix.

    Only a single-letter suffix after `.` or `_` counts, the naming both Codex rigs use. Names such
    as `LeftArm` are left alone; a rig named that way needs its own rule.
    """
    match = _SIDE_SUFFIX.search(name)
    if not match:
        return None
    return name[: match.start()] + _SWAP[match.group(1)]


def side_renames(names: list[str]) -> dict[str, str]:
    """Every side-suffixed name mapped to its swapped name.

    A joint without a counterpart (the imp's `socket_weapon_r`, child of the hand that becomes
    `hand.L`) changes side as well. No rename can collide: a target name is itself side-suffixed,
    so a joint holding it is renamed in the same pass (the caller goes through temporary names).
    """
    renames = {}
    for name in names:
        other = swapped_side_name(name)
        if other is not None:
            renames[name] = other
    return renames
