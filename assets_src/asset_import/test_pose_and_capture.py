"""Unit tests for the stage 4 tools: pose sampling and capture measurement.

Run with `python -B -m unittest test_pose_and_capture.py` from this directory.
"""

from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

import measure_capture
import sample_pose
from test_check_asset import build_figure

IDENTITY = (0.0, 0.0, 0.0, 1.0)
QUARTER_TURN_Z = (0.0, 0.0, math.sin(math.pi / 4), math.cos(math.pi / 4))


def write_ppm(path: Path, pixels: np.ndarray, comment: bool = False) -> Path:
    header = f"P6\n{'# written by a test\n' if comment else ''}{pixels.shape[1]} "
    header += f"{pixels.shape[0]}\n255\n"
    path.write_bytes(header.encode("ascii") + pixels.astype(np.uint8).tobytes())
    return path


class SlerpTests(unittest.TestCase):
    def test_half_way_is_half_the_angle(self) -> None:
        mixed = sample_pose.slerp(IDENTITY, QUARTER_TURN_Z, 0.5)
        angle = 2.0 * math.acos(mixed[3])
        self.assertAlmostEqual(math.degrees(angle), 45.0, places=5)
        self.assertAlmostEqual(math.sqrt(sum(v * v for v in mixed)), 1.0, places=9)

    def test_takes_the_shortest_arc(self) -> None:
        """A quaternion and its negation are the same rotation: both must mix the same way."""
        negated = tuple(-value for value in QUARTER_TURN_Z)
        near = sample_pose.slerp(IDENTITY, QUARTER_TURN_Z, 0.25)
        far = sample_pose.slerp(IDENTITY, negated, 0.25)
        for a, b in zip(near, far):
            self.assertAlmostEqual(a, b, places=9)

    def test_almost_parallel_stays_finite(self) -> None:
        mixed = sample_pose.slerp(IDENTITY, IDENTITY, 0.5)
        self.assertEqual(tuple(round(value, 9) for value in mixed), IDENTITY)


class SampleChannelTests(unittest.TestCase):
    TIMES = [0.0, 0.5, 1.0]
    VALUES = [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 2.0, 0.0)]

    def sample(self, time: float, *, step: bool = False, rotation: bool = False):
        return sample_pose.sample_channel(
            self.TIMES, self.VALUES, time, rotation=rotation, step=step
        )

    def test_clamps_at_both_ends(self) -> None:
        self.assertEqual(self.sample(-1.0), (0.0, 0.0, 0.0))
        self.assertEqual(self.sample(9.0), (0.0, 2.0, 0.0))

    def test_linear_between_keyframes(self) -> None:
        self.assertEqual(self.sample(0.25), (0.0, 0.5, 0.0))
        self.assertEqual(self.sample(0.75), (0.0, 1.5, 0.0))

    def test_step_holds_the_previous_keyframe(self) -> None:
        self.assertEqual(self.sample(0.49, step=True), (0.0, 0.0, 0.0))
        self.assertEqual(self.sample(0.51, step=True), (0.0, 1.0, 0.0))

    def test_rotation_is_slerped_not_mixed(self) -> None:
        times = [0.0, 1.0]
        values = [IDENTITY, QUARTER_TURN_Z]
        mixed = sample_pose.sample_channel(times, values, 0.5, rotation=True, step=False)
        self.assertAlmostEqual(math.sqrt(sum(v * v for v in mixed)), 1.0, places=9)
        self.assertAlmostEqual(math.degrees(2.0 * math.acos(mixed[3])), 45.0, places=5)

    def test_empty_sampler_is_an_error(self) -> None:
        with self.assertRaises(sample_pose.PoseError):
            sample_pose.sample_channel([], [], 0.0, rotation=False, step=False)


class SamplePoseTests(unittest.TestCase):
    """End to end on a synthetic figure: the clip moves the root from 0 to 0.1 m in 0.5 s."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "figure.glb"
        self.path.write_bytes(build_figure())

    def test_samples_every_joint_in_pack_order(self) -> None:
        pose = sample_pose.sample_pose(self.path, "idle", 6, 24.0)
        self.assertEqual(pose["time"], 0.25)
        names = [joint[0] for joint in pose["joints"]]
        self.assertEqual(sorted(names), ["foot.L", "foot.R", "root"])
        self.assertEqual(names[0], "root", "a parent comes before its children in pack order")

    def test_the_root_carries_the_packs_axis_correction(self) -> None:
        """Half way through the clip the root has risen 0.05 m along glTF's +Y, which is the
        engine's +Z after the correction the converter applies to root joints."""
        pose = sample_pose.sample_pose(self.path, "idle", 6, 24.0)
        _, translation, _, scale = pose["joints"][0]
        self.assertEqual(tuple(round(value, 6) for value in translation), (0.0, 0.0, 0.05))
        self.assertEqual(tuple(round(value, 6) for value in scale), (1.0, 1.0, 1.0))

    def test_unknown_clip_names_the_clips_it_has(self) -> None:
        with self.assertRaises(sample_pose.PoseError) as caught:
            sample_pose.sample_pose(self.path, "somersault", 0, 24.0)
        self.assertIn("idle", str(caught.exception))

    def test_cubicspline_is_refused_not_approximated(self) -> None:
        glb = sample_pose.load_glb(self.path)
        glb.json_doc["animations"][0]["samplers"][0]["interpolation"] = "CUBICSPLINE"
        with self.assertRaises(sample_pose.PoseError) as caught:
            sample_pose.clip_poses(glb, "idle", 0.25)
        self.assertIn("CUBICSPLINE", str(caught.exception))

    def test_written_file_holds_one_line_per_joint(self) -> None:
        pose = sample_pose.sample_pose(self.path, "idle", 6, 24.0)
        out = Path(self.directory.name) / "figure_idle_6.pose"
        sample_pose.write_pose(pose, "witch", out)
        lines = out.read_text(encoding="ascii").splitlines()
        self.assertEqual(lines[0], f"# {sample_pose.POSE_FORMAT}")
        self.assertIn("figure witch", lines)
        self.assertIn("joints 3", lines)
        joint_lines = [line for line in lines if line.startswith("joint ")]
        self.assertEqual(len(joint_lines), 3)
        self.assertEqual(len(joint_lines[0].split()), 2 + 3 + 4 + 3)


class ReadPpmTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def test_reads_pixels_and_skips_comments(self) -> None:
        pixels = np.arange(2 * 3 * 3, dtype=np.uint8).reshape(2, 3, 3)
        path = write_ppm(Path(self.directory.name) / "capture.ppm", pixels, comment=True)
        np.testing.assert_array_equal(measure_capture.read_ppm(path), pixels)

    def test_rejects_a_file_that_is_not_a_binary_ppm(self) -> None:
        path = Path(self.directory.name) / "plain.ppm"
        path.write_bytes(b"P3\n1 1\n255\n0 0 0\n")
        with self.assertRaises(SystemExit):
            measure_capture.read_ppm(path)


class LuminanceTests(unittest.TestCase):
    def test_black_and_white_are_the_ends_of_the_scale(self) -> None:
        values = measure_capture.relative_luminance(np.array([[[0, 0, 0], [255, 255, 255]]]))
        self.assertAlmostEqual(values[0, 0], 0.0, places=9)
        self.assertAlmostEqual(values[0, 1], 1.0, places=9)

    def test_contrast_of_black_against_white_is_twenty_one_to_one(self) -> None:
        self.assertAlmostEqual(measure_capture.contrast_ratio(0.0, 1.0), 21.0, places=9)
        self.assertAlmostEqual(measure_capture.contrast_ratio(1.0, 0.0), 21.0, places=9)


class BandTests(unittest.TestCase):
    def test_splits_at_empty_columns(self) -> None:
        mask = np.zeros((4, 20), dtype=bool)
        mask[:, 2:8] = True
        mask[:, 12:18] = True
        self.assertEqual(measure_capture.bands(mask), [(2, 8), (12, 18)])

    def test_ignores_bands_narrower_than_the_minimum(self) -> None:
        mask = np.zeros((4, 20), dtype=bool)
        mask[:, 3:5] = True  # two columns: noise, not a figure
        mask[:, 10:16] = True
        self.assertEqual(measure_capture.bands(mask), [(10, 16)])


class MeasureTests(unittest.TestCase):
    """Two rectangles on an even floor: one darker than the floor, one brighter."""

    def setUp(self) -> None:
        self.floor = np.full((40, 60, 3), 80, dtype=np.uint8)
        self.capture = self.floor.copy()
        self.capture[10:30, 5:15] = 40  # 20 px tall, 10 px wide, darker
        self.capture[12:22, 40:50] = 200  # 10 px tall, 10 px wide, brighter
        self.report = measure_capture.measure(self.capture, self.floor, ["dark", "bright"])

    def test_finds_one_band_per_figure_with_its_size(self) -> None:
        self.assertEqual(self.report["bands"], 2)
        self.assertNotIn("label_warning", self.report)
        dark, bright = self.report["figures"]
        self.assertEqual((dark["label"], dark["height_px"], dark["width_px"]), ("dark", 20, 10))
        self.assertEqual(dark["pixels"], 200)
        self.assertEqual((bright["height_px"], bright["width_px"]), (10, 10))

    def test_contrast_is_measured_against_the_floor_beside_the_figure(self) -> None:
        dark, bright = self.report["figures"]
        floor = measure_capture.relative_luminance(np.array([[[80, 80, 80]]]))[0, 0]
        self.assertAlmostEqual(dark["floor_median_luminance"], round(float(floor), 5), places=5)
        self.assertGreater(dark["contrast_to_floor"], 1.0)
        self.assertGreater(bright["contrast_to_floor"], dark["contrast_to_floor"])

    def test_warns_when_the_labels_do_not_match_the_bands(self) -> None:
        report = measure_capture.measure(self.capture, self.floor, ["dark", "bright", "third"])
        self.assertIn("2 bands for 3 labels", report["label_warning"])

    def test_captures_of_different_size_are_an_error(self) -> None:
        with self.assertRaises(SystemExit):
            measure_capture.measure(self.capture, self.floor[:20], [])


if __name__ == "__main__":
    unittest.main()
