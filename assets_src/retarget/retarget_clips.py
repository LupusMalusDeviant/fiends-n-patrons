#!/usr/bin/env python3
"""Retargets an animation library onto a figure's rig and measures how much of the rig moves.

    python -B retarget_clips.py --figure <figure.glb> --library <library.glb>
        --bone-map witch_bone_map.json --clip-table witch_clip_table.json
        --out-dir <target> --name witch [--blender <blender>]

Writes `<name>_retargeted.glb` with one clip per line of the clip table, plus
`<name>_retarget.json` (what the run did), `<name>_coverage.json` (how many joints move per clip,
before and after) and `<name>_blender.log`. Nothing lands inside the repository.

Why this exists: a figure's clips can carry a channel for every joint and still move almost
nothing. Measured on the witch before this run, the shipped clips moved 5 to 11 of her 31 joints --
no feet, no hands, no clavicles, no pelvis -- which is what makes ankles look rigid and elbows
straight. The library's own clips move 17 to 21 body bones. This script carries that motion across.

Blender runs headless, with the factory settings and a single thread, so two runs of the same
inputs produce the same bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from clip_coverage import coverage  # noqa: E402


def run_blender(blender: str, script: Path, arguments: list[str], log: Path) -> None:
    command = [
        blender,
        "-b",
        "--factory-startup",
        "-t",
        "1",
        "--python-exit-code",
        "1",
        "--python",
        str(script),
        "--",
        *arguments,
    ]
    log.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    log.write_text(completed.stdout + completed.stderr, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        tail = "\n".join((completed.stdout + completed.stderr).splitlines()[-25:])
        raise SystemExit(f"blender failed ({completed.returncode}); last lines:\n{tail}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def compare_coverage(before: dict, after: dict) -> list[dict]:
    """Per clip: how many joints moved before the retarget and how many move after."""
    old = {clip["name"]: clip for clip in before["clips"]}
    rows = []
    for clip in after["clips"]:
        earlier = old.get(clip["name"])
        rows.append(
            {
                "clip": clip["name"],
                "frames_before": earlier["keys"] if earlier else None,
                "frames_after": clip["keys"],
                "joints_before": earlier["moving_joints"] if earlier else None,
                "joints_after": clip["moving_joints"],
                "gained": sorted(set(clip["moving"]) - set(earlier["moving"])) if earlier else [],
                "lost": sorted(set(earlier["moving"]) - set(clip["moving"])) if earlier else [],
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--figure", type=Path, required=True, help="rigged figure with its clips")
    parser.add_argument("--library", type=Path, required=True, help="animation library (.glb)")
    parser.add_argument("--bone-map", type=Path, required=True)
    parser.add_argument("--clip-table", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--name", default="figure", help="file stem of the outputs")
    parser.add_argument("--blender", default=os.environ.get("BLENDER", "blender"))
    args = parser.parse_args(argv)

    for path in (args.figure, args.library, args.bone_map, args.clip_table):
        if not path.is_file():
            print(f"error: {path} is not a file", file=sys.stderr)
            return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_glb = args.out_dir / f"{args.name}_retargeted.glb"
    report_path = args.out_dir / f"{args.name}_retarget.json"
    coverage_path = args.out_dir / f"{args.name}_coverage.json"
    log_path = args.out_dir / f"{args.name}_blender.log"

    before = coverage(args.figure)
    run_blender(
        args.blender,
        HERE / "blender_retarget.py",
        [
            "--figure", str(args.figure),
            "--library", str(args.library),
            "--bone-map", str(args.bone_map),
            "--clip-table", str(args.clip_table),
            "--out", str(out_glb),
            "--report", str(report_path),
        ],
        log_path,
    )  # fmt: skip
    after = coverage(out_glb)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = compare_coverage(before, after)
    measurement = {
        "figure": args.figure.name,
        "library": args.library.name,
        "output": out_glb.name,
        "output_sha256": sha256(out_glb),
        "joints": after["skin_joints"],
        "left_at_rest": report.get("left_at_rest", []),
        "clips": rows,
    }
    coverage_path.write_text(json.dumps(measurement, indent=2) + "\n", encoding="utf-8")

    print(f"{out_glb.name}: {len(rows)} clips, {after['skin_joints']} joints in the skin")
    print(f"  {'clip':<12} {'frames':>7} {'joints before':>14} {'joints after':>13}")
    for row in rows:
        before_count = "-" if row["joints_before"] is None else row["joints_before"]
        print(
            f"  {row['clip']:<12} {row['frames_after']:>7} {before_count:>14} "
            f"{row['joints_after']:>13}"
        )
    if report.get("left_at_rest"):
        print(f"  left at rest on purpose: {', '.join(report['left_at_rest'])}")
    print(f"  wrote {coverage_path.name} and {report_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
