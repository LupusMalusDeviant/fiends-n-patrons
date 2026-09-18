#!/usr/bin/env python3
"""Measures the poses of a figure's clips: how far it leans, how it twists, where its feet are.

    python -B pose_check.py <figure.glb> [--clips walk,run] [--step 2] [--json-out <file>]

The picture at the game camera shows whether a clip reads; these numbers say whether it is sane,
and they say it without a renderer. Per sampled frame, against the figure's own rest pose:

- **lean**: the angle between vertical and the line from the pelvis to the head. A walk leans a
  little, a sprint leans a lot, and a figure that leans 60 degrees is falling over -- which is
  easy to miss in a picture taken from above and impossible to miss here.
- **twist**: how far the shoulder line has turned away from the rest pose's, in degrees. A walk
  counter-rotates a few degrees; tens of degrees mean the retarget put a turn in that the source
  never had.
- **foot height**: the ankle joints above the figure's ground plane, in metres, next to their rest
  height. The lower of the two is the standing foot: it belongs within a centimetre or two of the
  rest height in a walk, and both feet leave the ground only in a run's flight phase.

Every number comes from forward kinematics over the pack's own joint order, so what is measured is
what the engine will pose.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "figure_pack"))
sys.path.insert(0, str(HERE.parent / "asset_import"))

from glb_reader import GlbError, load_glb, read_accessor  # noqa: E402
from rig_math import quat_multiply, quat_rotate_vec3, vec3_add, vec3_scale_components  # noqa: E402
from sample_pose import sample_pose  # noqa: E402
from skeleton import build_skeleton  # noqa: E402

# Joints the measurement needs. A figure without them is simply not measured.
PELVIS, HEAD = "pelvis", "head"
SHOULDERS = ("clavicle.L", "clavicle.R")
FEET = ("foot.L", "foot.R")


def forward_kinematics(joints, local) -> list[tuple]:
    """World transforms of every joint, parents first, from local `(t, r, s)` triples."""
    world: list[tuple] = []
    for index, joint in enumerate(joints):
        translation, rotation, scale = local[index]
        if joint.parent == -1:
            world.append((translation, rotation, scale))
            continue
        parent_t, parent_r, parent_s = world[joint.parent]
        world.append(
            (
                vec3_add(parent_t, quat_rotate_vec3(parent_r, vec3_scale_components(translation, parent_s))),
                quat_multiply(parent_r, rotation),
                vec3_scale_components(scale, parent_s),
            )
        )
    return world


def lean_degrees(position: dict[str, tuple]) -> float:
    """Angle between vertical and the pelvis-to-head line."""
    pelvis, head = position[PELVIS], position[HEAD]
    horizontal = math.hypot(head[0] - pelvis[0], head[1] - pelvis[1])
    return math.degrees(math.atan2(horizontal, head[2] - pelvis[2]))


def shoulder_angle(position: dict[str, tuple]) -> float:
    left, right = position[SHOULDERS[0]], position[SHOULDERS[1]]
    return math.degrees(math.atan2(left[1] - right[1], left[0] - right[0]))


def angle_difference(one: float, other: float) -> float:
    """Signed difference of two angles in degrees, folded into -180..180."""
    return (one - other + 180.0) % 360.0 - 180.0


def clip_frames(glb, animation: dict, rate: float) -> int:
    """How many frames a clip holds, from the longest channel's key times.

    Channels that never change may be stored as two keys, so the clip's length is the longest
    channel's, and the sampled frames are the authored ones: frame `k` at `k / rate` after the
    first key.
    """
    spans = [
        [float(value) for value in read_accessor(glb, sampler["input"])]
        for sampler in animation.get("samplers", [])
    ]
    times = max(spans, key=len, default=[])
    if len(times) < 2:
        return max(1, len(times))
    return int(round((times[-1] - times[0]) * rate)) + 1


def measure(path: Path, clips: list[str], step: int, rate: float = 24.0) -> dict:
    glb = load_glb(path)
    skins = {
        node["skin"] for node in glb.json_doc.get("nodes", []) if "mesh" in node and "skin" in node
    }
    if len(skins) != 1:
        raise SystemExit(f"{path.name}: expected exactly one skin, found {sorted(skins)}")
    skeleton = build_skeleton(glb, skins.pop(), label=path.stem)
    names = [joint.name for joint in skeleton.joints]
    needed = [PELVIS, HEAD, *SHOULDERS, *FEET]
    missing = [name for name in needed if name not in names]
    if missing:
        raise SystemExit(f"{path.name}: the rig has no {missing}")

    rest_local = [(joint.translation, joint.rotation, joint.scale) for joint in skeleton.joints]
    rest_world = forward_kinematics(skeleton.joints, rest_local)
    rest_position = {name: rest_world[names.index(name)][0] for name in needed}
    rest_shoulders = shoulder_angle(rest_position)

    animations = {
        animation.get("name"): animation for animation in glb.json_doc.get("animations", [])
    }
    wanted = clips or sorted(name for name in animations if name)
    report: dict = {
        "file": path.name,
        "rest": {
            "lean_degrees": round(lean_degrees(rest_position), 2),
            "foot_height_m": {name: round(rest_position[name][2], 4) for name in FEET},
        },
        "clips": [],
    }
    for clip in wanted:
        if clip not in animations:
            raise SystemExit(f"{path.name}: no clip {clip!r}")
        frames = []
        for index in range(0, clip_frames(glb, animations[clip], rate), step):
            pose = sample_pose(path, clip, index, rate)
            local = [(entry[1], entry[2], entry[3]) for entry in pose["joints"]]
            world = forward_kinematics(skeleton.joints, local)
            position = {name: world[names.index(name)][0] for name in needed}
            frames.append(
                {
                    "frame": index,
                    "lean_degrees": round(lean_degrees(position), 2),
                    "twist_degrees": round(
                        angle_difference(shoulder_angle(position), rest_shoulders), 2
                    ),
                    "foot_height_m": {name: round(position[name][2], 4) for name in FEET},
                }
            )
        lowest = [min(entry["foot_height_m"].values()) for entry in frames]
        report["clips"].append(
            {
                "name": clip,
                "sampled_frames": len(frames),
                "max_lean_degrees": max(entry["lean_degrees"] for entry in frames),
                "max_twist_degrees": max(abs(entry["twist_degrees"]) for entry in frames),
                "lowest_foot_m": round(min(lowest), 4),
                "highest_standing_foot_m": round(max(lowest), 4),
                "frames": frames,
            }
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("figure", type=Path)
    parser.add_argument("--clips", default="", help="comma-separated clip names (default: all)")
    parser.add_argument("--step", type=int, default=1, help="sample every n-th frame")
    parser.add_argument("--rate", type=float, default=24.0, help="rate the clips were authored at")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)

    clips = [name.strip() for name in args.clips.split(",") if name.strip()]
    try:
        report = measure(args.figure, clips, max(1, args.step), args.rate)
    except (GlbError, OSError, KeyError, IndexError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    rest = report["rest"]
    feet = ", ".join(f"{name} {value:.3f}" for name, value in rest["foot_height_m"].items())
    print(f"{report['file']}: rest lean {rest['lean_degrees']:.1f} deg, rest feet {feet}")
    print(f"  {'clip':<12} {'frames':>6} {'max lean':>9} {'max twist':>10} {'standing foot':>14}")
    for clip in report["clips"]:
        print(
            f"  {clip['name']:<12} {clip['sampled_frames']:>6} "
            f"{clip['max_lean_degrees']:>8.1f}° {clip['max_twist_degrees']:>9.1f}° "
            f"{clip['highest_standing_foot_m']:>13.3f}m"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
