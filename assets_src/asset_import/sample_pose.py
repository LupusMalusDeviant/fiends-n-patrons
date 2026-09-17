#!/usr/bin/env python3
"""Samples one frame of one clip of a prepared figure into a small pose file for the engine.

    python -B sample_pose.py --figure <figure.glb> --clip melee_1 --frame 6 --fps 24
        --out <figure>_melee_1_frame_6.pose

Stage 4 shows the witch in a pose without an animation system in the engine: the engine takes
joint matrices per frame from the caller, so the pose is sampled here, offline, and shipped as
test data. No Blender: the prepared `.glb` carries its clips as node keyframes, and this reads
them directly.

What the file holds, in the pack's joint order (`../figure_pack/skeleton.py` decides that order,
the same way the converter does): the local translation, rotation and scale of every joint at the
sampled time. The root joints carry the pack's axis correction, exactly like their rest pose, so
the engine's `compute_skin_matrices` turns these into skinning matrices without any further
correction.

Interpolation is glTF's: `LINEAR` for translation and scale, the shortest-arc slerp for rotation,
`STEP` holds the previous keyframe (the clips use it for the root). `CUBICSPLINE` is refused rather
than approximated.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "figure_pack"))

from glb_reader import GlbError, load_glb, read_accessor  # noqa: E402
from rig_math import correct_root_joint_transform  # noqa: E402
from skeleton import SkeletonError, build_skeleton  # noqa: E402

POSE_FORMAT = "fnp pose v1"


class PoseError(RuntimeError):
    """The clip, the frame or the file cannot be sampled."""


def slerp(a: tuple[float, ...], b: tuple[float, ...], t: float) -> tuple[float, ...]:
    """Shortest-arc quaternion interpolation (glTF `LINEAR` for rotations)."""
    dot = sum(x * y for x, y in zip(a, b))
    if dot < 0.0:
        b, dot = tuple(-y for y in b), -dot
    if dot > 0.9995:  # almost parallel: linear, then normalise
        mixed = tuple(x + (y - x) * t for x, y in zip(a, b))
    else:
        theta = math.acos(max(-1.0, min(1.0, dot)))
        sin_theta = math.sin(theta)
        wa, wb = math.sin((1.0 - t) * theta) / sin_theta, math.sin(t * theta) / sin_theta
        mixed = tuple(x * wa + y * wb for x, y in zip(a, b))
    length = math.sqrt(sum(value * value for value in mixed)) or 1.0
    return tuple(value / length for value in mixed)


def sample_channel(
    times: list[float], values: list[Any], time: float, *, rotation: bool, step: bool
):
    """The value of one animation sampler at `time`, clamped at both ends."""
    if not times:
        raise PoseError("sampler without keyframes")
    if time <= times[0]:
        return tuple(values[0])
    if time >= times[-1]:
        return tuple(values[-1])
    index = next(i for i in range(1, len(times)) if times[i] >= time)
    if step:  # glTF STEP: the value of the previous keyframe holds until the next one
        return tuple(values[index - 1])
    span = times[index] - times[index - 1]
    t = 0.0 if span <= 0.0 else (time - times[index - 1]) / span
    first, second = tuple(values[index - 1]), tuple(values[index])
    if rotation:
        return slerp(first, second, t)
    return tuple(x + (y - x) * t for x, y in zip(first, second))


def clip_poses(glb, clip: str, time: float) -> dict[int, dict[str, tuple[float, ...]]]:
    """Node index -> the channels the clip drives at `time`."""
    animations = glb.json_doc.get("animations", [])
    names = [animation.get("name") for animation in animations]
    if clip not in names:
        raise PoseError(f"clip {clip!r} not in the figure; it has {sorted(n for n in names if n)}")
    animation = animations[names.index(clip)]
    posed: dict[int, dict[str, tuple[float, ...]]] = {}
    for channel in animation.get("channels", []):
        target = channel.get("target", {})
        node, path = target.get("node"), target.get("path")
        if node is None or path not in ("translation", "rotation", "scale"):
            continue
        sampler = animation["samplers"][channel["sampler"]]
        interpolation = sampler.get("interpolation", "LINEAR")
        if interpolation not in ("LINEAR", "STEP"):
            raise PoseError(
                f"clip {clip!r} uses {interpolation} interpolation on node {node}; "
                "only LINEAR and STEP are sampled here"
            )
        times = [float(value) for value in read_accessor(glb, sampler["input"])]
        values = read_accessor(glb, sampler["output"])
        posed.setdefault(int(node), {})[path] = sample_channel(
            times, values, time, rotation=path == "rotation", step=interpolation == "STEP"
        )
    return posed


def sample_pose(path: Path, clip: str, frame: int, fps: float) -> dict[str, Any]:
    """Every joint's local transform at `frame`, in the pack's joint order."""
    glb = load_glb(path)
    skins = {
        node["skin"]
        for node in glb.json_doc.get("nodes", [])
        if "mesh" in node and "skin" in node
    }
    if len(skins) != 1:
        raise PoseError(f"{path.name}: expected exactly one skin, found {sorted(skins)}")
    skeleton = build_skeleton(glb, skins.pop(), label=path.stem)
    time = frame / fps
    posed = clip_poses(glb, clip, time)
    node_of_joint = {new: original for original, new in skeleton.original_index_to_new.items()}
    skin_nodes = glb.json_doc["skins"][0]["joints"]
    joints = []
    for index, joint in enumerate(skeleton.joints):
        node = skin_nodes[node_of_joint[index]]
        channels = posed.get(node, {})
        translation = channels.get("translation", joint.translation)
        rotation = channels.get("rotation", joint.rotation)
        scale = channels.get("scale", joint.scale)
        if joint.parent == -1:
            # The rest pose of a root joint carries the pack's axis correction; the sampled pose
            # has to carry the same one, or the figure lies down in the engine.
            translation, rotation = correct_root_joint_transform(translation, rotation)
        joints.append((joint.name, translation, rotation, scale))
    return {"clip": clip, "frame": frame, "fps": fps, "time": time, "joints": joints}


def write_pose(pose: dict[str, Any], figure: str, out: Path) -> None:
    lines = [
        f"# {POSE_FORMAT}",
        "# local translation, rotation (x y z w) and scale of every joint, in pack order",
        f"figure {figure}",
        f"clip {pose['clip']}",
        f"frame {pose['frame']}",
        f"fps {pose['fps']:g}",
        f"time {pose['time']:.6f}",
        f"joints {len(pose['joints'])}",
    ]
    for name, translation, rotation, scale in pose["joints"]:
        numbers = " ".join(f"{value:.7g}" for value in (*translation, *rotation, *scale))
        lines.append(f"joint {name} {numbers}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="ascii")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--figure", type=Path, required=True, help="prepared figure (.glb)")
    parser.add_argument("--clip", required=True)
    parser.add_argument("--frame", type=int, required=True)
    parser.add_argument("--fps", type=float, default=24.0)
    parser.add_argument("--name", help="figure name for the file header (default: the file stem)")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        pose = sample_pose(args.figure, args.clip, args.frame, args.fps)
    except (PoseError, GlbError, SkeletonError, OSError, KeyError, IndexError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    write_pose(pose, args.name or args.figure.stem, args.out)
    print(
        f"{args.out.name}: {len(pose['joints'])} joints of {args.clip} at frame {args.frame} "
        f"({pose['time']:.3f} s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
