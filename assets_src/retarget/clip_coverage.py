#!/usr/bin/env python3
"""Counts, per clip of a glTF file, how many joints actually move.

    python -B clip_coverage.py <figure.glb> [--json-out <file>] [--only idle,walk] [--joints]

A clip can carry a channel for every joint and still animate almost nothing: an exporter writes
one channel per joint and path whether or not the values differ. This tool ignores the channel
count and looks at the values: a joint counts as moving when any of its translation, rotation or
scale values differs from that channel's first value by more than `VARIES` (1e-5, well above the
noise of float32 keys and far below a motion anyone can see).

That is the measurement behind the retarget: how much of the rig the motion actually reaches,
before and after.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "figure_pack"))

from glb_reader import GlbError, load_glb, read_accessor  # noqa: E402

# A channel counts as moving when its values spread further than this from the first key.
VARIES = 1.0e-5

PATHS = ("translation", "rotation", "scale")


def moving_joints(glb, animation: dict) -> dict[str, list[str]]:
    """Joint name -> the paths that move, for one animation."""
    names = [node.get("name", f"node{index}") for index, node in enumerate(glb.json_doc["nodes"])]
    moving: dict[str, set[str]] = {}
    for channel in animation.get("channels", []):
        target = channel.get("target", {})
        node, path = target.get("node"), target.get("path")
        if node is None or path not in PATHS:
            continue
        sampler = animation["samplers"][channel["sampler"]]
        values = [tuple(float(component) for component in value) for value in read_accessor(glb, sampler["output"])]
        if not values:
            continue
        first = values[0]
        spread = max(
            max(abs(value[index] - first[index]) for index in range(len(first)))
            for value in values
        )
        if spread > VARIES:
            moving.setdefault(names[node], set()).add(path)
    return {name: sorted(paths) for name, paths in sorted(moving.items())}


def coverage(path: Path, only: set[str] | None = None) -> dict:
    """Per clip: channels, moving joints, and the joints of the figure's skin."""
    glb = load_glb(path)
    nodes = glb.json_doc.get("nodes", [])
    skins = glb.json_doc.get("skins", [])
    skin_joints = (
        [nodes[index].get("name", f"node{index}") for index in skins[0]["joints"]] if skins else []
    )
    report: dict = {
        "file": path.name,
        "nodes": len(nodes),
        "skin_joints": len(skin_joints),
        "joint_names": skin_joints,
        "clips": [],
    }
    for animation in glb.json_doc.get("animations", []):
        name = animation.get("name", "?")
        if only and name not in only:
            continue
        moving = moving_joints(glb, animation)
        # Key counts differ per channel: an exporter may store a channel that never changes as
        # two keys and a moving one as one key per frame. The clip's own length is the longest
        # of them, so that is what is reported.
        per_channel = [
            [float(value) for value in read_accessor(glb, sampler["input"])]
            for sampler in animation.get("samplers", [])
        ]
        times = max(per_channel, key=len, default=[])
        report["clips"].append(
            {
                "name": name,
                "channels": len(animation.get("channels", [])),
                "keys": len(times),
                "keys_min": min((len(entry) for entry in per_channel), default=0),
                "seconds": round(times[-1] - times[0], 6) if times else 0.0,
                "moving_joints": len(moving),
                "moving": moving,
                "still": sorted(set(skin_joints) - set(moving)),
            }
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("figure", type=Path, help="glTF binary to measure")
    parser.add_argument("--only", default="", help="comma-separated clip names (default: all)")
    parser.add_argument("--joints", action="store_true", help="also list the joints per clip")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)

    only = {name.strip() for name in args.only.split(",") if name.strip()}
    try:
        report = coverage(args.figure, only or None)
    except (GlbError, OSError, KeyError, IndexError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"{report['file']}: {report['skin_joints']} joints in the skin, {len(report['clips'])} clips")
    for clip in report["clips"]:
        print(
            f"  {clip['name']:<12} {clip['keys']:>4} keys, {clip['seconds']:.3f} s, "
            f"{clip['channels']:>3} channels, {clip['moving_joints']:>3} joints move"
        )
        if args.joints:
            print(f"      moving: {', '.join(clip['moving'])}")
            print(f"      still:  {', '.join(clip['still'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
