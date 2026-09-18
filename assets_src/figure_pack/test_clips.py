"""Unit tests for the clip exporter (`FNP_CLIP`, format document version 1).

Run with `python -B -m unittest test_clips.py` from this directory.

The strongest check here is `GoldenFixtureTests`: the engine ships a hand-derived golden payload
(`crates/grimoire_render/tests/fixtures/figure_clip_v1.bin`, 190 bytes, derived field by field from
the format document and not produced by the engine's own encoder). This converter has to produce
exactly those bytes for the same clip, and the same skeleton fingerprint, or one of the two sides
is wrong.
"""

from __future__ import annotations

import os
import struct
import unittest
from pathlib import Path

import clips
from glb_reader import Glb
from skeleton import build_skeleton


def _golden() -> bytes:
    """The fixture, assembled from the derivation in the engine's `.hex` listing."""
    parts = [
        b"FNP_CLIP",
        struct.pack("<I", 1),  # version
        struct.pack("<I", 1),  # flags: loops
        struct.pack("<I", 2),  # joint_count
        struct.pack("<I", 3),  # frame_count
        struct.pack("<f", 24.0),
        struct.pack("<Q", 0x9A6C_8135_349D_1276),
        struct.pack("<I", 1),  # marker_count
        # joint 0 "root"
        b"\x01",
        struct.pack("<3f", 0.0, 0.0, 0.0),
        struct.pack("<3f", 0.0, 0.5, 0.0),
        struct.pack("<3f", 0.0, 0.0, 0.0),
        b"\x00",
        struct.pack("<4f", 0.0, 0.0, 0.0, 1.0),
        b"\x00",
        struct.pack("<3f", 1.0, 1.0, 1.0),
        # joint 1 "limb"
        b"\x00",
        struct.pack("<3f", 0.0, 0.0, 1.0),
        b"\x01",
        struct.pack("<4f", 0.0, 0.0, 0.0, 1.0),
        struct.pack("<4f", 0.0, 0.0, 0.0, -1.0),
        struct.pack("<4f", 0.0, 0.0, 0.0, 1.0),
        b"\x00",
        struct.pack("<3f", 1.0, 1.0, 1.0),
        # markers
        struct.pack("<I", 1),
        b"\x03",
        b"hit",
    ]
    return b"".join(parts)


class Joint:
    """Just enough of `skeleton.Joint` for the fingerprint."""

    def __init__(self, parent: int) -> None:
        self.parent = parent


class FingerprintTests(unittest.TestCase):
    def test_matches_the_engines_golden_value(self) -> None:
        """`figure-clip.md` §4 names this value for the two-joint fixture rig."""
        fingerprint = clips.skeleton_fingerprint([Joint(-1), Joint(0)])
        self.assertEqual(fingerprint, 0x9A6C_8135_349D_1276)

    def test_depends_on_the_hierarchy_not_on_the_joint_count_alone(self) -> None:
        one = clips.skeleton_fingerprint([Joint(-1), Joint(0)])
        other = clips.skeleton_fingerprint([Joint(-1), Joint(-1)])
        self.assertNotEqual(one, other)

    def test_stays_in_sixty_four_bits(self) -> None:
        fingerprint = clips.skeleton_fingerprint([Joint(-1)] * 200)
        self.assertTrue(0 <= fingerprint < 2**64)


class GoldenFixtureTests(unittest.TestCase):
    """The encoder against the engine's hand-derived payload."""

    def setUp(self) -> None:
        self.clip = clips.SampledClip(
            name="fixture",
            frame_rate_hz=24.0,
            frame_count=3,
            loops=True,
            translations=[
                [(0.0, 0.0, 0.0), (0.0, 0.5, 0.0), (0.0, 0.0, 0.0)],
                [(0.0, 0.0, 1.0)] * 3,
            ],
            rotations=[
                [(0.0, 0.0, 0.0, 1.0)] * 3,
                [(0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, -1.0), (0.0, 0.0, 0.0, 1.0)],
            ],
            scales=[[(1.0, 1.0, 1.0)] * 3, [(1.0, 1.0, 1.0)] * 3],
            animated_joints=2,
            varying_tracks=2,
        )
        self.markers = [clips.Marker(frame=1, name="hit")]

    def test_encodes_the_golden_fixture_byte_for_byte(self) -> None:
        payload = clips.encode_clip(
            self.clip, 0x9A6C_8135_349D_1276, self.markers, label="fixture"
        )
        self.assertEqual(payload, _golden())
        self.assertEqual(len(payload), 190, "the fixture is 190 bytes (format document §9)")

    def test_the_derivation_matches_the_engines_fixture_file(self) -> None:
        """When the engine checkout is at hand (`FNP_GRIMOIRE_REPO`), compare against its bytes.

        The derivation above is written out from the format document, so this test proves the
        document, the engine's fixture and this converter agree. Without the checkout there is
        nothing to compare against and the test skips -- CI has no engine working copy.
        """
        repo = os.environ.get("FNP_GRIMOIRE_REPO")
        if not repo:
            self.skipTest("FNP_GRIMOIRE_REPO is not set")
        fixture = (
            Path(repo) / "crates/grimoire_render/tests/fixtures/figure_clip_v1.bin"
        )
        if not fixture.is_file():
            self.skipTest(f"{fixture} is not there")
        self.assertEqual(_golden(), fixture.read_bytes())

    def test_a_sign_flipped_rotation_key_is_kept(self) -> None:
        """`q` and `-q` are the same rotation; the shorter-path rule is the sampler's job."""
        payload = clips.encode_clip(
            self.clip, 0x9A6C_8135_349D_1276, self.markers, label="fixture"
        )
        self.assertIn(struct.pack("<4f", 0.0, 0.0, 0.0, -1.0), payload)

    def test_a_non_unit_rotation_is_refused(self) -> None:
        self.clip.rotations[0][1] = (0.0, 0.0, 0.0, 0.5)
        with self.assertRaises(clips.ClipError) as caught:
            clips.encode_clip(self.clip, 0, self.markers, label="fixture")
        self.assertIn("does not renormalise", str(caught.exception))

    def test_a_marker_outside_the_clip_is_refused(self) -> None:
        with self.assertRaises(clips.ClipError):
            clips.encode_clip(
                self.clip, 0, [clips.Marker(frame=3, name="hit")], label="fixture"
            )


class MarkerTests(unittest.TestCase):
    def test_blender_frames_lose_one(self) -> None:
        markers = clips.markers_from_events({"hit": 6}, 14, clip="melee_1")
        self.assertEqual([(m.frame, m.name) for m in markers], [(5, "hit")])

    def test_sorted_by_frame(self) -> None:
        markers = clips.markers_from_events(
            {"parry_end": 9, "parry_start": 3}, 12, clip="parry"
        )
        self.assertEqual([m.frame for m in markers], [2, 8])

    def test_frame_zero_of_the_authoring_base_is_outside(self) -> None:
        with self.assertRaises(clips.ClipError):
            clips.markers_from_events({"hit": 0}, 10, clip="c")

    def test_a_frame_past_the_end_is_refused(self) -> None:
        with self.assertRaises(clips.ClipError) as caught:
            clips.markers_from_events({"hit": 11}, 10, clip="c")
        self.assertIn("outside", str(caught.exception))

    def test_a_long_name_is_refused(self) -> None:
        with self.assertRaises(clips.ClipError):
            clips.markers_from_events({"x" * 64: 1}, 10, clip="c")

    def test_no_events_means_no_markers(self) -> None:
        self.assertEqual(clips.markers_from_events({}, 10, clip="c"), [])


def _rig_glb(channels: list[dict], *, interpolation: str = "LINEAR") -> tuple[Glb, list[int]]:
    """A two-joint rig (`root` -> `limb`) with one animation built from `channels`.

    Every channel is `{"node": i, "path": p, "times": [...], "values": [[...], ...]}`; the values
    go into the binary chunk as float accessors.
    """
    doc: dict = {
        "nodes": [
            {"name": "root", "children": [1]},
            {"name": "limb", "translation": [0.0, 0.0, 1.0]},
        ],
        "skins": [{"joints": [0, 1]}],
        "accessors": [],
        "bufferViews": [],
        "animations": [{"name": "clip", "samplers": [], "channels": []}],
    }
    binary = bytearray()

    def accessor(rows: list[tuple[float, ...]], type_: str) -> int:
        width = len(rows[0])
        data = b"".join(struct.pack(f"<{width}f", *row) for row in rows)
        doc["bufferViews"].append(
            {"buffer": 0, "byteOffset": len(binary), "byteLength": len(data)}
        )
        binary.extend(data)
        doc["accessors"].append(
            {
                "bufferView": len(doc["bufferViews"]) - 1,
                "componentType": 5126,
                "count": len(rows),
                "type": type_,
            }
        )
        return len(doc["accessors"]) - 1

    animation = doc["animations"][0]
    for channel in channels:
        times = accessor([(time,) for time in channel["times"]], "SCALAR")
        width = len(channel["values"][0])
        values = accessor(channel["values"], {3: "VEC3", 4: "VEC4"}[width])
        animation["samplers"].append(
            {"input": times, "output": values, "interpolation": interpolation}
        )
        animation["channels"].append(
            {
                "sampler": len(animation["samplers"]) - 1,
                "target": {"node": channel["node"], "path": channel["path"]},
            }
        )
    return Glb(json_doc=doc, bin_chunk=bytes(binary)), doc["skins"][0]["joints"]


FRAME = 1.0 / 24.0


class SampleClipTests(unittest.TestCase):
    def sample(self, channels: list[dict], **kwargs) -> clips.SampledClip:
        glb, skin_nodes = _rig_glb(channels, **kwargs)
        skeleton = build_skeleton(glb, 0, label="t")
        return clips.sample_clip(glb, skeleton, skin_nodes, "clip", frame_rate=24.0)

    def test_the_authoring_offset_becomes_frame_zero(self) -> None:
        """The GLB's first key sits at 1/24 s; the payload starts at t = 0 (format document §3)."""
        sampled = self.sample(
            [
                {
                    "node": 1,
                    "path": "translation",
                    "times": [FRAME, 2 * FRAME, 3 * FRAME],
                    "values": [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 2.0, 0.0)],
                }
            ]
        )
        self.assertEqual(sampled.frame_count, 3)
        self.assertEqual(sampled.frame_rate_hz, 24.0)
        self.assertEqual(
            sampled.translations[1], [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 2.0, 0.0)]
        )

    def test_a_joint_the_clip_does_not_drive_keeps_its_rest_pose(self) -> None:
        sampled = self.sample(
            [
                {
                    "node": 1,
                    "path": "translation",
                    "times": [FRAME, 2 * FRAME],
                    "values": [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
                }
            ]
        )
        self.assertEqual(sampled.animated_joints, 1)
        # `limb`'s rest translation is (0, 0, 1) in the node, the clip overrides it; `root` is
        # untouched and keeps its (corrected) rest pose in every frame.
        self.assertEqual(len(set(sampled.translations[0])), 1)

    def test_the_root_track_carries_the_axis_correction(self) -> None:
        """glTF +Y is the engine's +Z; the correction sits on the root, as in the rest pose."""
        sampled = self.sample(
            [
                {
                    "node": 0,
                    "path": "translation",
                    "times": [FRAME, 2 * FRAME],
                    "values": [(0.0, 2.0, 0.0), (0.0, 2.0, 0.0)],
                }
            ]
        )
        self.assertEqual(sampled.translations[0][0], (0.0, 0.0, 2.0))

    def test_only_the_tracks_that_move_count_as_varying(self) -> None:
        sampled = self.sample(
            [
                {
                    "node": 1,
                    "path": "translation",
                    "times": [FRAME, 2 * FRAME],
                    "values": [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
                }
            ]
        )
        self.assertEqual(sampled.varying_tracks, 1)
        payload = clips.encode_clip(sampled, 0, [], label="t")
        # 40 header + joint 0 (three constant tracks) + joint 1 (one sampled, two constant)
        constant = 1 + 12 + 1 + 16 + 1 + 12
        sampled_track = 1 + 12 * sampled.frame_count
        self.assertEqual(len(payload), 40 + constant + sampled_track + 1 + 16 + 1 + 12)

    def test_a_closed_loop_is_detected(self) -> None:
        sampled = self.sample(
            [
                {
                    "node": 1,
                    "path": "translation",
                    "times": [FRAME, 2 * FRAME, 3 * FRAME],
                    "values": [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 0.0)],
                }
            ]
        )
        self.assertTrue(sampled.loops)

    def test_a_clip_that_ends_elsewhere_does_not_loop(self) -> None:
        sampled = self.sample(
            [
                {
                    "node": 1,
                    "path": "translation",
                    "times": [FRAME, 2 * FRAME],
                    "values": [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
                }
            ]
        )
        self.assertFalse(sampled.loops)

    def test_a_rotation_that_ends_in_the_other_hemisphere_still_loops(self) -> None:
        sampled = self.sample(
            [
                {
                    "node": 1,
                    "path": "rotation",
                    "times": [FRAME, 2 * FRAME],
                    "values": [(0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, -1.0)],
                }
            ]
        )
        self.assertTrue(sampled.loops)

    def test_cubicspline_is_refused_not_approximated(self) -> None:
        with self.assertRaises(clips.ClipError) as caught:
            self.sample(
                [
                    {
                        "node": 1,
                        "path": "translation",
                        "times": [FRAME, 2 * FRAME],
                        "values": [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
                    }
                ],
                interpolation="CUBICSPLINE",
            )
        self.assertIn("CUBICSPLINE", str(caught.exception))

    def test_a_clip_that_is_not_a_whole_number_of_frames_is_refused(self) -> None:
        with self.assertRaises(clips.ClipError) as caught:
            self.sample(
                [
                    {
                        "node": 1,
                        "path": "translation",
                        "times": [FRAME, FRAME + 0.03],
                        "values": [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
                    }
                ]
            )
        self.assertIn("authored at", str(caught.exception))

    def test_an_unknown_clip_names_the_ones_it_has(self) -> None:
        glb, skin_nodes = _rig_glb(
            [
                {
                    "node": 1,
                    "path": "translation",
                    "times": [FRAME, 2 * FRAME],
                    "values": [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
                }
            ]
        )
        skeleton = build_skeleton(glb, 0, label="t")
        with self.assertRaises(clips.ClipError) as caught:
            clips.sample_clip(glb, skeleton, skin_nodes, "sprint", frame_rate=24.0)
        self.assertIn("clip", str(caught.exception))

    def test_a_clip_over_the_frame_limit_is_refused(self) -> None:
        end = FRAME + clips.MAX_CLIP_FRAMES * FRAME
        with self.assertRaises(clips.ClipError) as caught:
            self.sample(
                [
                    {
                        "node": 1,
                        "path": "translation",
                        "times": [FRAME, end],
                        "values": [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
                    }
                ]
            )
        self.assertIn("over the limit", str(caught.exception))

    def test_a_step_channel_holds_the_previous_key(self) -> None:
        sampled = self.sample(
            [
                {
                    "node": 1,
                    "path": "translation",
                    "times": [FRAME, 3 * FRAME],
                    "values": [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
                }
            ],
            interpolation="STEP",
        )
        self.assertEqual(
            sampled.translations[1],
            [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        )


class SampleChannelTests(unittest.TestCase):
    def test_interpolates_linearly_and_clamps(self) -> None:
        times, values = [0.0, 1.0], [(0.0, 0.0, 0.0), (0.0, 2.0, 0.0)]
        self.assertEqual(
            clips.sample_channel(times, values, 0.5, rotation=False, step=False),
            (0.0, 1.0, 0.0),
        )
        self.assertEqual(
            clips.sample_channel(times, values, -1.0, rotation=False, step=False),
            (0.0, 0.0, 0.0),
        )
        self.assertEqual(
            clips.sample_channel(times, values, 9.0, rotation=False, step=False),
            (0.0, 2.0, 0.0),
        )

    def test_rotation_keeps_unit_length(self) -> None:
        quarter = (0.0, 0.0, 0.70710678, 0.70710678)
        mixed = clips.sample_channel(
            [0.0, 1.0], [(0.0, 0.0, 0.0, 1.0), quarter], 0.5, rotation=True, step=False
        )
        length = sum(value * value for value in mixed) ** 0.5
        self.assertAlmostEqual(length, 1.0, places=9)

    def test_a_sampler_without_keys_is_an_error(self) -> None:
        with self.assertRaises(clips.ClipError):
            clips.sample_channel([], [], 0.0, rotation=False, step=False)


if __name__ == "__main__":
    unittest.main()
