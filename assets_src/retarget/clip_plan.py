#!/usr/bin/env python3
"""The plan of a retarget run: which library clip feeds which figure clip, and how joints map.

Pure data and pure functions, no Blender: everything here can be unit-tested, and
`blender_retarget.py` does nothing but carry it out.

Two files drive a run:

- **The bone map** (`bone_map.json`): `{"bones": {"<figure joint>": "<library bone>", ...},
  "translation": ["<figure joint>", ...], "cloth": [{"chain": [...], "driver": "...", ...}]}`.
  A figure joint that is not in `bones` gets no motion from the library; `translation` names the
  few joints whose position is copied as well as their rotation (the hips carry the bob, every
  other joint keeps its bone length).
- **The clip table** (`clip_table.json`): per figure clip the library clip and how many frames the
  result has: `{"clips": [{"name": "walk", "source": "Walk_Loop", "frames": 17, "loop": true},
  ...]}`. An optional `"source_frames": [first, last]` trims the source; without it the whole
  source clip is used, whatever frame range it spans in Blender. `"ground": true` asks for the
  hips to be lowered until the lower foot stands where it stands in the rest pose -- see
  `blender_retarget.py`, "Feet on the floor".

The frame count of a figure clip is authoring data, not a detail: the markers of the authoring
report point at frames, and the simulation's timings were built against those lengths. A retarget
therefore resamples the source range onto exactly the frame count the clip already had.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


class PlanError(ValueError):
    """The bone map or the clip table does not describe a run that can be carried out."""


@dataclass(frozen=True)
class ClothChain:
    """A chain of joints with no counterpart in the library, driven from a joint that has one.

    Skirt and cape hang from the figure; the library rig has nothing like them. Left alone they
    would be rigid while everything else moves. They follow their driver with a delay instead:
    each link swings by `follow` of the driver's own turn since the clip's first frame, delayed by
    `lag` frames, and each further link down the chain by `falloff` of the one above it.
    """

    chain: tuple[str, ...]
    driver: str
    follow: float = 0.35
    lag: float = 2.0
    falloff: float = 0.6


@dataclass(frozen=True)
class BoneMap:
    """Which figure joint follows which library bone."""

    bones: dict[str, str]
    translation: tuple[str, ...] = ()
    cloth: tuple[ClothChain, ...] = ()

    def driven(self) -> set[str]:
        """Every figure joint this map moves: mapped joints plus the cloth chains."""
        return set(self.bones) | {joint for chain in self.cloth for joint in chain.chain}


@dataclass(frozen=True)
class ClipPlan:
    """One figure clip: where it comes from, how long it is, whether it loops."""

    name: str
    source: str
    frames: int
    source_frames: tuple[float, float] | None = None
    loop: bool = False
    ground: bool = False
    note: str = ""

    def sample_frames(self, source_range: tuple[float, float]) -> list[float]:
        """The source frames to sample, one per output frame.

        `source_range` is the range the source action actually spans; a clip that names its own
        `source_frames` trims that. The frame count is the figure clip's own, so the result keeps
        the length the game and the clip's markers were built for -- the motion is resampled onto
        it, evenly, first frame to first frame and last to last.
        """
        start, end = self.source_frames or source_range
        if self.frames < 2:
            return [float(start)]
        step = (end - start) / (self.frames - 1)
        return [start + step * index for index in range(self.frames)]


@dataclass
class Plan:
    """A whole run: the bone map, the clips, and the rate everything is authored at."""

    bone_map: BoneMap
    clips: tuple[ClipPlan, ...]
    frame_rate_hz: float = 24.0
    warnings: list[str] = field(default_factory=list)


def load_bone_map(path: Path) -> BoneMap:
    data = json.loads(path.read_text(encoding="utf-8"))
    bones = data.get("bones")
    if not isinstance(bones, dict) or not bones:
        raise PlanError(f"{path.name}: 'bones' must be a non-empty object")
    for joint, source in bones.items():
        if not isinstance(source, str) or not source:
            raise PlanError(f"{path.name}: joint {joint!r} maps to {source!r}, not a bone name")
    translation = tuple(data.get("translation", ()))
    unknown = [joint for joint in translation if joint not in bones]
    if unknown:
        raise PlanError(f"{path.name}: 'translation' names unmapped joints {unknown}")
    cloth = []
    for entry in data.get("cloth", ()):
        chain = tuple(entry.get("chain", ()))
        driver = entry.get("driver", "")
        if not chain or not driver:
            raise PlanError(f"{path.name}: a cloth entry needs 'chain' and 'driver'")
        if driver not in bones:
            raise PlanError(f"{path.name}: cloth driver {driver!r} is not a mapped joint")
        overlap = sorted(set(chain) & set(bones))
        if overlap:
            raise PlanError(f"{path.name}: {overlap} are both mapped and driven as cloth")
        cloth.append(
            ClothChain(
                chain=chain,
                driver=driver,
                follow=float(entry.get("follow", 0.35)),
                lag=float(entry.get("lag", 2.0)),
                falloff=float(entry.get("falloff", 0.6)),
            )
        )
    return BoneMap(bones=dict(bones), translation=translation, cloth=tuple(cloth))


def load_clip_table(path: Path) -> tuple[ClipPlan, float]:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("clips")
    if not isinstance(entries, list) or not entries:
        raise PlanError(f"{path.name}: 'clips' must be a non-empty list")
    clips = []
    seen: set[str] = set()
    for entry in entries:
        name = entry.get("name")
        source = entry.get("source")
        frames = entry.get("frames")
        span = entry.get("source_frames")
        if not name or not source:
            raise PlanError(f"{path.name}: every clip needs 'name' and 'source'")
        if name in seen:
            raise PlanError(f"{path.name}: clip {name!r} appears twice")
        seen.add(name)
        if not isinstance(frames, int) or frames < 1:
            raise PlanError(f"{path.name}: clip {name!r} has frames {frames!r}")
        if span is not None:
            numeric = isinstance(span, list) and len(span) == 2
            if not numeric or not all(isinstance(value, (int, float)) for value in span):
                raise PlanError(
                    f"{path.name}: clip {name!r} has source_frames {span!r}; expected "
                    "[first, last] or nothing at all for the whole source clip"
                )
            if span[1] < span[0]:
                raise PlanError(f"{path.name}: clip {name!r} has source_frames {span} back to front")
        clips.append(
            ClipPlan(
                name=name,
                source=source,
                frames=frames,
                source_frames=(float(span[0]), float(span[1])) if span else None,
                loop=bool(entry.get("loop", False)),
                ground=bool(entry.get("ground", False)),
                note=str(entry.get("note", "")),
            )
        )
    return tuple(clips), float(data.get("frame_rate_hz", 24.0))


def load_plan(bone_map_path: Path, clip_table_path: Path) -> Plan:
    bone_map = load_bone_map(bone_map_path)
    clips, rate = load_clip_table(clip_table_path)
    return Plan(bone_map=bone_map, clips=clips, frame_rate_hz=rate)


def check_against_rigs(
    plan: Plan, figure_joints: list[str], library_bones: list[str]
) -> list[str]:
    """Everything the plan says that the two rigs do not support, as one list of problems."""
    problems = []
    for joint, source in sorted(plan.bone_map.bones.items()):
        if joint not in figure_joints:
            problems.append(f"the figure has no joint {joint!r}")
        if source not in library_bones:
            problems.append(f"the library has no bone {source!r} (mapped to {joint!r})")
    for chain in plan.bone_map.cloth:
        for joint in chain.chain:
            if joint not in figure_joints:
                problems.append(f"the figure has no cloth joint {joint!r}")
    return problems


def unmapped_joints(plan: Plan, figure_joints: list[str]) -> list[str]:
    """Figure joints the plan leaves in their rest pose, deliberately."""
    return sorted(set(figure_joints) - plan.bone_map.driven())
