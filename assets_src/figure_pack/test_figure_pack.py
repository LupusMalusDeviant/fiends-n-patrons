"""Unit tests for the figure-pack converter modules. Standard-library `unittest` only.

Run with `python -B -m unittest test_figure_pack.py` from this directory (or `discover`).
"""

from __future__ import annotations

import struct
import unittest
import zlib

import pack_payloads
import png_decode
import rig_math
import skeleton
import stable_id
from glb_reader import Glb, GlbError, load_glb, read_accessor


def _make_png(
    width: int,
    height: int,
    bit_depth: int,
    color_type: int,
    row_bytes_fn,
    *,
    palette: bytes | None = None,
    trns: bytes | None = None,
) -> bytes:
    """Encodes a minimal, always-filter-0 PNG for round-trip testing (filter 0 is always valid)."""

    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body))

    ihdr = struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0)
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type None
        raw.extend(row_bytes_fn(y))
    idat = zlib.compress(bytes(raw), 9)
    out = bytearray(b"\x89PNG\r\n\x1a\n")
    out += chunk(b"IHDR", ihdr)
    if palette is not None:
        out += chunk(b"PLTE", palette)
    if trns is not None:
        out += chunk(b"tRNS", trns)
    out += chunk(b"IDAT", idat)
    out += chunk(b"IEND", b"")
    return bytes(out)


class PngDecodeTests(unittest.TestCase):
    def test_truecolor_8bit_round_trips(self) -> None:
        pixels = [(10, 20, 30), (255, 0, 128), (0, 0, 0), (255, 255, 255)]

        def row(y: int) -> bytes:
            return bytes(pixels[(y * 2 + x) % len(pixels)][c] for x in range(2) for c in range(3))

        data = _make_png(2, 2, 8, 2, row)
        decoded = png_decode.decode_png(data, label="t")
        self.assertEqual(decoded.width, 2)
        self.assertEqual(decoded.height, 2)
        self.assertEqual(len(decoded.rgba), 2 * 2 * 4)
        self.assertEqual(decoded.rgba[0:4], bytes((10, 20, 30, 255)))
        self.assertEqual(decoded.rgba[4:8], bytes((255, 0, 128, 255)))

    def test_grayscale_1bit_round_trips(self) -> None:
        # 4 pixels wide, 1 bit each, packed MSB-first into a single byte: 1,0,1,1 -> 0b1011____.
        def row(y: int) -> bytes:
            del y
            return bytes([0b1011_0000])

        data = _make_png(4, 1, 1, 0, row)
        decoded = png_decode.decode_png(data, label="t")
        self.assertEqual(decoded.rgba[0:4], bytes((255, 255, 255, 255)))
        self.assertEqual(decoded.rgba[4:8], bytes((0, 0, 0, 255)))
        self.assertEqual(decoded.rgba[8:12], bytes((255, 255, 255, 255)))
        self.assertEqual(decoded.rgba[12:16], bytes((255, 255, 255, 255)))

    def test_palette_round_trips_with_trns(self) -> None:
        palette = bytes((10, 20, 30, 200, 210, 220))  # index 0, index 1

        def row(y: int) -> bytes:
            del y
            return bytes([0, 1])

        data = _make_png(2, 1, 8, 3, row, palette=palette, trns=bytes((0, 255)))
        decoded = png_decode.decode_png(data, label="t")
        self.assertEqual(decoded.rgba[0:4], bytes((10, 20, 30, 0)))  # index 0 -> alpha 0
        self.assertEqual(decoded.rgba[4:8], bytes((200, 210, 220, 255)))  # index 1 -> alpha 255

    def test_16bit_truecolor_downsamples_to_8bit(self) -> None:
        def row(y: int) -> bytes:
            del y
            # One pixel: R=65535, G=0, B=32768 at 16 bits (big-endian).
            return struct.pack(">HHH", 65535, 0, 32768)

        data = _make_png(1, 1, 16, 2, row)
        decoded = png_decode.decode_png(data, label="t")
        self.assertEqual(decoded.rgba[0], 255)
        self.assertEqual(decoded.rgba[1], 0)
        self.assertEqual(decoded.rgba[2], round(32768 * 255 / 65535))

    def test_interlaced_is_rejected(self) -> None:
        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 1)  # interlace = 1
        body = b"\x89PNG\r\n\x1a\n"
        body += struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr + struct.pack(
            ">I", zlib.crc32(b"IHDR" + ihdr)
        )
        with self.assertRaises(png_decode.PngError):
            png_decode.decode_png(body, label="t")

    def test_bad_signature_is_rejected(self) -> None:
        with self.assertRaises(png_decode.PngError):
            png_decode.decode_png(b"not a png", label="t")


class StableIdTests(unittest.TestCase):
    def test_deterministic_and_domain_separated(self) -> None:
        a = stable_id.asset_id_for_path("a/b.c")
        b = stable_id.asset_id_for_path("a/b.c")
        c = stable_id.asset_id_for_path("a/b.d")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_fits_in_64_bits(self) -> None:
        value = stable_id.asset_id_for_path("figures/soul/mesh/0")
        self.assertGreaterEqual(value, 0)
        self.assertLess(value, 1 << 64)

    def test_write_bytes_length_prefix_prevents_concatenation_collisions(self) -> None:
        h1 = stable_id.StableHasher()
        h1.write_str("ab")
        h1.write_str("cdef")
        h2 = stable_id.StableHasher()
        h2.write_str("abcd")
        h2.write_str("ef")
        self.assertNotEqual(h1.finish(), h2.finish())


class RigMathTests(unittest.TestCase):
    def test_axis_correction_matches_quaternion_rotation(self) -> None:
        v = (1.0, 2.0, 3.0)
        direct = rig_math.apply_axis_correction_vec3(v)
        via_quat = rig_math.quat_rotate_vec3(rig_math.AXIS_CORRECTION_QUAT, v)
        for a, b in zip(direct, via_quat):
            self.assertAlmostEqual(a, b, places=6)

    def test_axis_correction_maps_up_to_up_and_forward_to_forward(self) -> None:
        # gltf +Y (up) -> engine +Z; gltf -Z (forward) -> engine +Y.
        self.assertEqual(rig_math.apply_axis_correction_vec3((0.0, 1.0, 0.0)), (0.0, 0.0, 1.0))
        self.assertEqual(rig_math.apply_axis_correction_vec3((0.0, 0.0, -1.0)), (0.0, 1.0, 0.0))
        self.assertEqual(rig_math.apply_axis_correction_vec3((1.0, 0.0, 0.0)), (1.0, 0.0, 0.0))

    def test_compose_trs_is_identity_neutral(self) -> None:
        identity = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0))
        child = ((1.0, 2.0, 3.0), (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0))
        self.assertEqual(rig_math.compose_trs(identity, child), child)

    def test_root_correction_only_touches_translation_and_rotation(self) -> None:
        translation = (1.0, 2.0, 3.0)
        rotation = (0.0, 0.0, 0.0, 1.0)
        new_translation, new_rotation = rig_math.correct_root_joint_transform(translation, rotation)
        self.assertEqual(new_translation, rig_math.apply_axis_correction_vec3(translation))
        self.assertEqual(new_rotation, rig_math.AXIS_CORRECTION_QUAT)


def _tiny_glb(nodes: list[dict], skins: list[dict]) -> Glb:
    return Glb(json_doc={"nodes": nodes, "skins": skins}, bin_chunk=b"")


class SkeletonTests(unittest.TestCase):
    def test_topological_order_and_root_correction(self) -> None:
        # node 2 is a non-joint container (identity), node 1 is the root joint, node 0 is its
        # child -- mirrors the shipped rigs' "<name>_rig" -> "root" -> ... shape.
        nodes = [
            {"name": "child", "translation": [0.0, 1.0, 0.0]},
            {"name": "root", "children": [0], "translation": [0.0, 0.0, 2.0]},
            {"name": "container", "children": [1]},
        ]
        skins = [{"joints": [0, 1], "inverseBindMatrices": None}]
        glb = _tiny_glb(nodes, skins)
        # No inverseBindMatrices accessor in this fixture: patch the skin to omit the key so
        # build_skeleton falls back to identity matrices instead of trying to read an accessor.
        del skins[0]["inverseBindMatrices"]
        result = skeleton.build_skeleton(glb, 0, label="t")
        names = [j.name for j in result.joints]
        self.assertEqual(names, ["root", "child"])  # parent before child
        self.assertEqual(result.joints[0].parent, -1)
        self.assertEqual(result.joints[1].parent, 0)
        # original skin.joints index 0 ("child") -> new index 1; index 1 ("root") -> new index 0
        self.assertEqual(result.original_index_to_new, {0: 1, 1: 0})
        # The root's translation must carry the axis correction; the child's must not.
        self.assertEqual(
            result.joints[0].translation, rig_math.apply_axis_correction_vec3((0.0, 0.0, 2.0))
        )
        self.assertEqual(result.joints[1].translation, (0.0, 1.0, 0.0))

    def test_too_many_joints_is_rejected(self) -> None:
        nodes = [{"name": f"j{i}"} for i in range(skeleton.MAX_JOINTS + 1)]
        skins = [{"joints": list(range(len(nodes)))}]
        glb = _tiny_glb(nodes, skins)
        with self.assertRaises(skeleton.SkeletonError):
            skeleton.build_skeleton(glb, 0, label="t")

    def test_remap_rejects_out_of_range_slot(self) -> None:
        with self.assertRaises(skeleton.SkeletonError):
            skeleton.remap_joint_indices(
                [(0, 0, 0, 5)], {0: 0}, joint_count=1, label="t"
            )


class PackPayloadTests(unittest.TestCase):
    def test_mesh_rejects_out_of_range_index(self) -> None:
        vertex = pack_payloads.Vertex(
            position=(0, 0, 0),
            normal=(0, 0, 1),
            uv=(0, 0),
            joints=(0, 0, 0, 0),
            weights=(1.0, 0.0, 0.0, 0.0),
        )
        with self.assertRaises(pack_payloads.PayloadError):
            pack_payloads.encode_mesh([vertex], [0, 1, 2], joint_count=1, label="t")

    def test_mesh_rejects_bad_weight_sum(self) -> None:
        vertex = pack_payloads.Vertex(
            position=(0, 0, 0),
            normal=(0, 0, 1),
            uv=(0, 0),
            joints=(0, 0, 0, 0),
            weights=(0.5, 0.0, 0.0, 0.0),
        )
        with self.assertRaises(pack_payloads.PayloadError):
            pack_payloads.encode_mesh([vertex, vertex, vertex], [0, 1, 2], joint_count=1, label="t")

    def test_mesh_round_trips_a_single_triangle(self) -> None:
        vertex = pack_payloads.Vertex(
            position=(1.0, 2.0, 3.0),
            normal=(0.0, 0.0, 1.0),
            uv=(0.5, 0.5),
            joints=(0, 1, 2, 3),
            weights=(0.25, 0.25, 0.25, 0.25),
        )
        data = pack_payloads.encode_mesh([vertex, vertex, vertex], [0, 1, 2], joint_count=4, label="t")
        version, vertex_count, index_count = struct.unpack_from("<III", data, 0)
        self.assertEqual((version, vertex_count, index_count), (1, 3, 3))

    def test_texture_raw_rejects_wrong_length(self) -> None:
        with self.assertRaises(pack_payloads.PayloadError):
            pack_payloads.encode_texture_raw(width=2, height=2, color_space=0, rgba=b"\x00" * 3, label="t")

    def test_skeleton_rejects_forward_parent_reference(self) -> None:
        joint_a = skeleton.Joint(
            name="a",
            parent=1,  # forward reference: not allowed even though it is index 0
            inverse_bind=(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1),
            translation=(0, 0, 0),
            rotation=(0, 0, 0, 1),
            scale=(1, 1, 1),
        )
        with self.assertRaises(pack_payloads.PayloadError):
            pack_payloads.encode_skeleton([joint_a], label="t")

    def test_figure_requires_at_least_one_part(self) -> None:
        with self.assertRaises(pack_payloads.PayloadError):
            pack_payloads.encode_figure(
                parts=[],
                texture_ids=[],
                skeleton_id=0,
                bounds_min=(0, 0, 0),
                bounds_max=(0, 0, 0),
                label="t",
            )


class GlbReaderTests(unittest.TestCase):
    def test_bad_magic_is_rejected(self) -> None:
        import struct as _struct
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.glb"
            path.write_bytes(_struct.pack("<4sII", b"NOPE", 2, 12))
            with self.assertRaises(GlbError):
                load_glb(path)

    def test_read_accessor_unwraps_scalars_and_keeps_vectors(self) -> None:
        import struct as _struct

        buf = _struct.pack("<3f", 1.0, 2.0, 3.0) + _struct.pack("<3H", 5, 6, 7)
        doc = {
            "bufferViews": [
                {"buffer": 0, "byteOffset": 0, "byteLength": 12},
                {"buffer": 0, "byteOffset": 12, "byteLength": 6},
            ],
            "accessors": [
                {"bufferView": 0, "componentType": 5126, "count": 1, "type": "VEC3"},
                {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"},
            ],
        }
        glb = Glb(json_doc=doc, bin_chunk=buf)
        self.assertEqual(read_accessor(glb, 0), [(1.0, 2.0, 3.0)])
        self.assertEqual(read_accessor(glb, 1), [5, 6, 7])


if __name__ == "__main__":
    unittest.main()


class GlbPathTests(unittest.TestCase):
    """The source file name is `<name><suffix>`; the suffix selects the asset round."""

    def test_default_suffix_is_the_r3b_round(self):
        from pathlib import Path
        import build_figure_pack as bfp
        self.assertEqual(bfp.glb_path_for(Path("src"), "imp"), Path("src") / "imp_r3b_low.glb")

    def test_a_custom_suffix_selects_another_round(self):
        from pathlib import Path
        import build_figure_pack as bfp
        self.assertEqual(bfp.glb_path_for(Path("src"), "brute", "_r3c_low.glb"), Path("src") / "brute_r3c_low.glb")
