"""Unit tests for the retarget's plan and its measurement, without Blender.

Run with `python -B -m unittest test_retarget.py` from this directory.

What is testable here is everything that decides *what* a run does: how a clip's frames are laid
over its source, which joints a bone map claims to drive, and how the coverage measurement counts
a joint as moving. The pose maths itself lives in Blender and is checked by the run's own numbers
(the coverage table) and by the offscreen pictures.
"""

from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

import clip_coverage
import clip_plan

BONE_MAP = {
    "bones": {"pelvis": "DEF-hips", "chest": "DEF-spine.003", "head": "DEF-head"},
    "translation": ["pelvis"],
    "cloth": [{"chain": ["cape_upper.C", "cape_lower.C"], "driver": "chest", "follow": 0.4}],
}

CLIP_TABLE = {
    "frame_rate_hz": 24.0,
    "clips": [
        {"name": "walk", "source": "Walk_Loop", "frames": 17, "loop": True},
        {"name": "death", "source": "Death01", "frames": 41, "source_frames": [1, 60]},
    ],
}


def write_json(directory: Path, name: str, data: dict) -> Path:
    path = directory / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class LoadPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def plan(self, bone_map: dict | None = None, table: dict | None = None) -> clip_plan.Plan:
        return clip_plan.load_plan(
            write_json(self.root, "map.json", bone_map or BONE_MAP),
            write_json(self.root, "table.json", table or CLIP_TABLE),
        )

    def test_reads_both_files(self) -> None:
        plan = self.plan()
        self.assertEqual(plan.frame_rate_hz, 24.0)
        self.assertEqual([clip.name for clip in plan.clips], ["walk", "death"])
        self.assertEqual(plan.bone_map.bones["pelvis"], "DEF-hips")
        self.assertEqual(plan.bone_map.translation, ("pelvis",))
        self.assertEqual(plan.bone_map.cloth[0].chain, ("cape_upper.C", "cape_lower.C"))
        self.assertEqual(plan.bone_map.cloth[0].follow, 0.4)

    def test_a_clip_without_a_source_range_takes_the_whole_source(self) -> None:
        plan = self.plan()
        walk, death = plan.clips
        self.assertIsNone(walk.source_frames)
        self.assertEqual(death.source_frames, (1.0, 60.0))

    def test_driven_joints_are_the_mapped_ones_plus_the_cloth(self) -> None:
        self.assertEqual(
            self.plan().bone_map.driven(),
            {"pelvis", "chest", "head", "cape_upper.C", "cape_lower.C"},
        )

    def test_translation_must_name_a_mapped_joint(self) -> None:
        broken = dict(BONE_MAP, translation=["root"])
        with self.assertRaises(clip_plan.PlanError):
            self.plan(bone_map=broken)

    def test_a_cloth_joint_cannot_also_be_mapped(self) -> None:
        broken = dict(
            BONE_MAP,
            cloth=[{"chain": ["head"], "driver": "chest"}],
        )
        with self.assertRaises(clip_plan.PlanError) as caught:
            self.plan(bone_map=broken)
        self.assertIn("head", str(caught.exception))

    def test_a_cloth_driver_must_be_mapped(self) -> None:
        broken = dict(BONE_MAP, cloth=[{"chain": ["skirt.C"], "driver": "nobody"}])
        with self.assertRaises(clip_plan.PlanError):
            self.plan(bone_map=broken)

    def test_a_clip_name_cannot_repeat(self) -> None:
        table = {"clips": [CLIP_TABLE["clips"][0], CLIP_TABLE["clips"][0]]}
        with self.assertRaises(clip_plan.PlanError) as caught:
            self.plan(table=table)
        self.assertIn("twice", str(caught.exception))

    def test_a_backwards_source_range_is_refused(self) -> None:
        table = {"clips": [{"name": "x", "source": "y", "frames": 3, "source_frames": [9, 2]}]}
        with self.assertRaises(clip_plan.PlanError):
            self.plan(table=table)

    def test_frames_must_be_a_positive_count(self) -> None:
        for frames in (0, -3, "many", 2.5):
            table = {"clips": [{"name": "x", "source": "y", "frames": frames}]}
            with self.assertRaises(clip_plan.PlanError):
                self.plan(table=table)


class SampleFrameTests(unittest.TestCase):
    def test_first_to_first_and_last_to_last(self) -> None:
        clip = clip_plan.ClipPlan(name="walk", source="Walk_Loop", frames=17)
        frames = clip.sample_frames((1.0, 33.0))
        self.assertEqual(len(frames), 17)
        self.assertEqual(frames[0], 1.0)
        self.assertEqual(frames[-1], 33.0)

    def test_steps_are_even(self) -> None:
        clip = clip_plan.ClipPlan(name="x", source="y", frames=5)
        self.assertEqual(clip.sample_frames((0.0, 8.0)), [0.0, 2.0, 4.0, 6.0, 8.0])

    def test_its_own_range_wins_over_the_sources(self) -> None:
        clip = clip_plan.ClipPlan(name="x", source="y", frames=3, source_frames=(10.0, 20.0))
        self.assertEqual(clip.sample_frames((0.0, 100.0)), [10.0, 15.0, 20.0])

    def test_a_single_frame_clip_samples_the_start(self) -> None:
        clip = clip_plan.ClipPlan(name="x", source="y", frames=1)
        self.assertEqual(clip.sample_frames((4.0, 9.0)), [4.0])

    def test_a_source_shorter_than_the_clip_is_upsampled(self) -> None:
        """Frame counts are the figure's own; a short source is stretched, not truncated."""
        clip = clip_plan.ClipPlan(name="x", source="y", frames=9)
        frames = clip.sample_frames((1.0, 5.0))
        self.assertEqual(len(frames), 9)
        self.assertEqual(frames[4], 3.0)


class CheckAgainstRigsTests(unittest.TestCase):
    def plan(self) -> clip_plan.Plan:
        return clip_plan.Plan(
            bone_map=clip_plan.BoneMap(
                bones={"pelvis": "DEF-hips"},
                cloth=(clip_plan.ClothChain(chain=("skirt.C",), driver="pelvis"),),
            ),
            clips=(),
        )

    def test_silent_when_both_rigs_have_everything(self) -> None:
        problems = clip_plan.check_against_rigs(
            self.plan(), ["pelvis", "skirt.C"], ["DEF-hips"]
        )
        self.assertEqual(problems, [])

    def test_names_what_each_rig_lacks(self) -> None:
        problems = clip_plan.check_against_rigs(self.plan(), ["pelvis"], ["hips"])
        self.assertEqual(len(problems), 2)
        self.assertTrue(any("DEF-hips" in problem for problem in problems))
        self.assertTrue(any("skirt.C" in problem for problem in problems))

    def test_unmapped_joints_are_listed(self) -> None:
        left = clip_plan.unmapped_joints(self.plan(), ["pelvis", "skirt.C", "root", "socket"])
        self.assertEqual(left, ["root", "socket"])


class GlbBuilder:
    """A glTF binary with one skin and animations, small enough to build in a test."""

    def __init__(self, joints: list[str]) -> None:
        self.doc: dict = {
            "asset": {"version": "2.0"},
            "nodes": [{"name": name} for name in joints],
            "skins": [{"joints": list(range(len(joints)))}],
            "accessors": [],
            "bufferViews": [],
            "buffers": [{}],
            "animations": [],
        }
        self.bin = bytearray()

    def accessor(self, rows: list[tuple[float, ...]], type_: str) -> int:
        width = len(rows[0])
        data = b"".join(struct.pack(f"<{width}f", *row) for row in rows)
        self.doc["bufferViews"].append(
            {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        )
        self.bin.extend(data)
        self.doc["accessors"].append(
            {
                "bufferView": len(self.doc["bufferViews"]) - 1,
                "componentType": 5126,
                "count": len(rows),
                "type": type_,
            }
        )
        return len(self.doc["accessors"]) - 1

    def animation(self, name: str, channels: list[tuple[int, str, list[tuple[float, ...]]]]) -> None:
        animation: dict = {"name": name, "samplers": [], "channels": []}
        for node, path, values in channels:
            times = self.accessor([(index / 24.0,) for index in range(len(values))], "SCALAR")
            output = self.accessor(values, {3: "VEC3", 4: "VEC4"}[len(values[0])])
            animation["samplers"].append({"input": times, "output": output})
            animation["channels"].append(
                {
                    "sampler": len(animation["samplers"]) - 1,
                    "target": {"node": node, "path": path},
                }
            )
        self.doc["animations"].append(animation)

    def build(self) -> bytes:
        while len(self.bin) % 4:
            self.bin.append(0)
        self.doc["buffers"][0]["byteLength"] = len(self.bin)
        body = json.dumps(self.doc).encode("utf-8")
        body += b" " * (-len(body) % 4)
        total = 12 + 8 + len(body) + 8 + len(self.bin)
        return (
            struct.pack("<4sII", b"glTF", 2, total)
            + struct.pack("<II", len(body), 0x4E4F534A) + body
            + struct.pack("<II", len(self.bin), 0x004E4942) + bytes(self.bin)
        )  # fmt: skip


class CoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        builder = GlbBuilder(["root", "pelvis", "foot.L"])
        builder.animation(
            "walk",
            [
                # pelvis turns: it moves. foot.L holds one value in 3 keys: it does not.
                (1, "rotation", [(0.0, 0.0, 0.0, 1.0), (0.0, 0.1, 0.0, 0.995), (0.0, 0.0, 0.0, 1.0)]),
                (2, "rotation", [(0.0, 0.0, 0.0, 1.0)] * 3),
                (0, "translation", [(0.0, 0.0, 0.0)] * 3),
            ],
        )
        self.path = Path(self.directory.name) / "figure.glb"
        self.path.write_bytes(builder.build())

    def test_counts_only_the_joints_whose_values_change(self) -> None:
        report = clip_coverage.coverage(self.path)
        clip = report["clips"][0]
        self.assertEqual(clip["channels"], 3)
        self.assertEqual(clip["moving_joints"], 1)
        self.assertEqual(list(clip["moving"]), ["pelvis"])
        self.assertEqual(clip["still"], ["foot.L", "root"])

    def test_reports_the_clips_length(self) -> None:
        clip = clip_coverage.coverage(self.path)["clips"][0]
        self.assertEqual(clip["keys"], 3)
        self.assertAlmostEqual(clip["seconds"], 2 / 24.0, places=6)

    def test_the_length_is_the_longest_channel_not_the_first(self) -> None:
        """An exporter stores a channel that never changes as two keys; that is not the length."""
        builder = GlbBuilder(["pelvis", "foot.L"])
        builder.animation(
            "walk",
            [
                (1, "rotation", [(0.0, 0.0, 0.0, 1.0)] * 2),
                (0, "rotation", [(0.0, index / 20.0, 0.0, 1.0) for index in range(5)]),
            ],
        )
        path = Path(self.directory.name) / "mixed.glb"
        path.write_bytes(builder.build())
        clip = clip_coverage.coverage(path)["clips"][0]
        self.assertEqual((clip["keys"], clip["keys_min"]), (5, 2))

    def test_a_change_below_the_threshold_does_not_count(self) -> None:
        builder = GlbBuilder(["pelvis"])
        tiny = clip_coverage.VARIES / 10.0
        builder.animation(
            "idle", [(0, "rotation", [(0.0, 0.0, 0.0, 1.0), (0.0, tiny, 0.0, 1.0)])]
        )
        path = Path(self.directory.name) / "tiny.glb"
        path.write_bytes(builder.build())
        self.assertEqual(clip_coverage.coverage(path)["clips"][0]["moving_joints"], 0)

    def test_only_selects_the_clips_asked_for(self) -> None:
        report = clip_coverage.coverage(self.path, only={"nothing"})
        self.assertEqual(report["clips"], [])


if __name__ == "__main__":
    unittest.main()
