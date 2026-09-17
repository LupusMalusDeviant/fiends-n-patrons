"""Unit tests for the Blender-free parts of stage 2 (textures, side names, measurements).

Run with `python -B -m unittest test_prepare_tools.py` from this directory. Needs numpy and Pillow
(`../textures/requirements.txt`); `blender_prepare.py` itself runs only inside Blender.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

import prepare_figure
import render_game_view
import texel_footprint
import verify_normal_map
from side_names import side_renames, swapped_side_name
from test_check_asset import GlbBuilder, make_png


class SideNameTests(unittest.TestCase):
    def test_single_letter_suffixes_swap_and_keep_case(self) -> None:
        self.assertEqual(swapped_side_name("hand.L"), "hand.R")
        self.assertEqual(swapped_side_name("cape_upper.R"), "cape_upper.L")
        self.assertEqual(swapped_side_name("socket_weapon_r"), "socket_weapon_l")
        for name in ("root", "spine", "skirt.C", "LeftArm", "tail_03", "hand.Left"):
            self.assertIsNone(swapped_side_name(name), name)

    def test_unpaired_joints_change_side_too(self) -> None:
        renames = side_renames(["root", "hand.L", "hand.R", "socket_weapon_r"])
        expected = {"hand.L": "hand.R", "hand.R": "hand.L", "socket_weapon_r": "socket_weapon_l"}
        self.assertEqual(renames, expected)

    def test_pairs_trade_names(self) -> None:
        renames = side_renames(["grip_r", "grip_l", "spine"])
        self.assertEqual(renames, {"grip_r": "grip_l", "grip_l": "grip_r"})


class BoxReduceTests(unittest.TestCase):
    def test_linear_data_is_a_plain_block_mean(self) -> None:
        pixels = np.zeros((4, 4, 3), dtype=np.uint8)
        pixels[:2, :2] = [0, 100, 200]
        pixels[:2, 2:] = [[10, 20, 30], [30, 40, 50]]
        out = prepare_figure.box_reduce(pixels, 2, srgb=False)
        self.assertEqual(out.shape, (2, 2, 3))
        self.assertEqual(out[0, 0].tolist(), [0, 100, 200])
        self.assertEqual(out[0, 1].tolist(), [20, 30, 40])
        self.assertEqual(out[1, 1].tolist(), [0, 0, 0])

    def test_srgb_is_averaged_in_linear_light(self) -> None:
        pixels = np.zeros((2, 2, 3), dtype=np.uint8)
        pixels[0, :] = 255
        out = prepare_figure.box_reduce(pixels, 1, srgb=True)
        # Half white in linear light is sRGB 188, not the naive 128.
        self.assertEqual(out[0, 0].tolist(), [188, 188, 188])
        naive = prepare_figure.box_reduce(pixels, 1, srgb=False)
        self.assertEqual(naive[0, 0].tolist(), [128, 128, 128])

    def test_only_square_powers_of_two_reduce(self) -> None:
        with self.assertRaises(prepare_figure.PrepareError):
            prepare_figure.box_reduce(np.zeros((6, 6, 3), dtype=np.uint8), 3, srgb=False)
        with self.assertRaises(prepare_figure.PrepareError):
            prepare_figure.box_reduce(np.zeros((4, 8, 3), dtype=np.uint8), 2, srgb=False)


class MaterialImageTests(unittest.TestCase):
    def build(self, *, with_mr: bool = True, materials: int = 1) -> Path:
        g = GlbBuilder()
        base = g.texture(make_png(2, 2), "image/png")
        mr = g.texture(make_png(4, 4), "image/png")
        pbr = {"baseColorTexture": {"index": base}}
        if with_mr:
            pbr["metallicRoughnessTexture"] = {"index": mr}
        g.doc["materials"] = [{"pbrMetallicRoughness": pbr} for _ in range(materials)]
        path = Path(self._tmp.name) / "m.glb"
        path.write_bytes(g.build())
        return path

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_returns_the_encoded_images_of_both_slots(self) -> None:
        images = prepare_figure.material_images(self.build())
        self.assertEqual(images["base_color"], make_png(2, 2))
        self.assertEqual(images["metallic_roughness"], make_png(4, 4))

    def test_rejects_missing_slots_and_several_materials(self) -> None:
        with self.assertRaises(prepare_figure.PrepareError):
            prepare_figure.material_images(self.build(with_mr=False))
        with self.assertRaises(prepare_figure.PrepareError):
            prepare_figure.material_images(self.build(materials=2))


class ShadingConventionTests(unittest.TestCase):
    """The tangent frame and texture orientation `verify_normal_map` and `render_game_view` use."""

    normal = np.array([[0.0, 0.0, 1.0]])
    tangent = np.array([[1.0, 0.0, 0.0, 1.0]])
    uv = np.array([[0.5, 0.5]])

    def shade(self, rgb, tangent=None):
        image = np.tile(np.array(rgb, dtype=np.float64), (4, 4, 1))
        tangent = self.tangent if tangent is None else tangent
        return verify_normal_map.shade_with_map(self.normal, tangent, self.uv, image)[0]

    def test_flat_map_keeps_the_vertex_normal(self) -> None:
        np.testing.assert_allclose(self.shade([128, 128, 255]), [0, 0, 1], atol=0.01)

    def test_red_follows_the_tangent_and_green_the_bitangent_with_its_sign(self) -> None:
        np.testing.assert_allclose(self.shade([255, 128, 128]), [1, 0, 0], atol=0.01)
        np.testing.assert_allclose(self.shade([128, 255, 128]), [0, 1, 0], atol=0.01)
        flipped = np.array([[1.0, 0.0, 0.0, -1.0]])
        np.testing.assert_allclose(self.shade([128, 255, 128], flipped), [0, -1, 0], atol=0.01)

    def test_v_zero_is_the_top_row(self) -> None:
        image = np.zeros((2, 1, 3))
        image[0] = [1, 0, 0]
        image[1] = [0, 0, 1]
        top = render_game_view.bilinear(image, np.array([[0.5, 0.25]]))
        bottom = verify_normal_map.sample_bilinear(image, np.array([[0.5, 0.75]]))
        np.testing.assert_allclose(top[0], [1, 0, 0])
        np.testing.assert_allclose(bottom[0], [0, 0, 1])


class FootprintTests(unittest.TestCase):
    def test_texel_rho_takes_the_longer_screen_axis(self) -> None:
        screen = np.array([[0.0, 0.0], [10.0, 0.0], [0.0, 10.0]])
        uv = np.array([[0.0, 0.0], [0.5, 0.0], [0.0, 0.25]])
        rho = render_game_view.texel_rho(screen, uv, np.array([[0, 1, 2]]))
        self.assertAlmostEqual(float(rho[0]), 0.05)

    def test_back_faces_are_skipped(self) -> None:
        camera = texel_footprint.camera_basis(60.0, 14.5)
        positions = np.array([[-0.1, 0.0, 0.0], [0.1, 0.0, 0.0], [0.0, 0.2, 0.0]])
        uvs = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
        front = {"positions": positions, "uvs": uvs, "indices": np.array([[0, 1, 2]])}
        back = {"positions": positions, "uvs": uvs, "indices": np.array([[0, 2, 1]])}
        area, rho = texel_footprint.footprint(front, 0.0, camera, 42.0, 1920, 1080)
        self.assertEqual(len(area), 1)
        self.assertGreater(float(area[0]), 0.0)
        self.assertGreater(float(rho[0]), 0.0)
        self.assertEqual(len(texel_footprint.footprint(back, 0.0, camera, 42.0, 1920, 1080)[0]), 0)

    def test_mip_chain_halves_to_one_texel(self) -> None:
        image = np.arange(16, dtype=np.float64).reshape(4, 4, 1)
        chain = render_game_view.mip_chain(image)
        self.assertEqual([level.shape[0] for level in chain], [4, 2, 1])
        self.assertAlmostEqual(float(chain[-1][0, 0, 0]), 7.5)


if __name__ == "__main__":
    unittest.main()
