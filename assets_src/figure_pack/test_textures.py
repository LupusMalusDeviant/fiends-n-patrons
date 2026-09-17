"""Unit tests for texture input: headers, engine limits, JPEG decoding, exact reduction, CLI.

Run with `python -B -m unittest test_textures.py` from this directory. The header and limit tests
need only the standard library; decoding JPEG and reducing need Pillow and numpy
(`../textures/requirements.txt`) and are skipped without them.
"""

from __future__ import annotations

import contextlib
import io
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

import build_figure_pack
import image_headers
import textures

try:
    import numpy as np
    from PIL import Image
except ImportError:  # pragma: no cover - depends on the environment
    np = None
    Image = None

needs_imaging = unittest.skipIf(np is None, "needs numpy and Pillow")


def make_png(width: int, height: int, color_type: int = 2, *, rows: list[bytes] | None = None,
             trns: bool = False) -> bytes:
    """A valid 8-bit PNG; all zero unless `rows` gives the raw scanlines (without filter bytes)."""
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]

    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body))

    rows = rows or [bytes(width * channels)] * height
    raw = b"".join(b"\x00" + row for row in rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
    if color_type == 3:
        out += chunk(b"PLTE", bytes(3))
        if trns:
            out += chunk(b"tRNS", b"\x00")
    return out + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def make_jpeg_header(width: int, height: int, *, progressive: bool = False) -> bytes:
    """Start of a JPEG up to its frame header: enough for a header reader, not for a decoder."""
    app0 = b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    frame = struct.pack(">BHHB", 8, height, width, 3) + bytes(9)
    marker = b"\xff\xc2" if progressive else b"\xff\xc0"
    return (
        b"\xff\xd8"
        + b"\xff\xe0" + struct.pack(">H", len(app0) + 2) + app0
        + b"\xff\xff"  # fill byte before the next marker
        + marker + struct.pack(">H", len(frame) + 2) + frame
        + b"\xff\xd9"
    )  # fmt: skip


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c: float) -> float:
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1.0 / 2.4) - 0.055


class ImageHeaderTests(unittest.TestCase):
    def test_png_size_and_channels(self) -> None:
        header = image_headers.read_image_header(make_png(7, 3, 6))
        measured = (header.mime_type, header.width, header.height, header.channels)
        self.assertEqual(measured, ("image/png", 7, 3, 4))

    def test_palette_png_with_transparency_counts_four_channels(self) -> None:
        self.assertEqual(image_headers.read_png_header(make_png(2, 2, 3)).channels, 3)
        self.assertEqual(image_headers.read_png_header(make_png(2, 2, 3, trns=True)).channels, 4)

    def test_jpeg_frame_after_app_segment_and_fill_byte(self) -> None:
        header = image_headers.read_image_header(make_jpeg_header(8192, 4096))
        self.assertEqual((header.mime_type, header.width, header.height, header.channels),
                         ("image/jpeg", 8192, 4096, 3))
        self.assertFalse(header.progressive)
        progressive = make_jpeg_header(16, 16, progressive=True)
        self.assertTrue(image_headers.read_jpeg_header(progressive).progressive)

    def test_unknown_bytes_are_rejected(self) -> None:
        with self.assertRaises(image_headers.ImageHeaderError):
            image_headers.read_image_header(b"GIF89a....")
        with self.assertRaises(image_headers.ImageHeaderError):
            image_headers.read_jpeg_header(b"\xff\xd8\xff\xd9")


class TableTests(unittest.TestCase):
    """The literal sRGB tables are the curve, and they order the codes correctly."""

    def test_tables_follow_the_srgb_curve(self) -> None:
        scale = 1 << 24
        for k, value in enumerate(textures.SRGB_TO_LINEAR_Q24):
            self.assertLessEqual(abs(value - srgb_to_linear(k / 255) * scale), 1.0, k)
        for k, value in enumerate(textures.SRGB_ROUNDING_THRESHOLDS_Q24):
            self.assertLessEqual(abs(value - srgb_to_linear((k + 0.5) / 255) * scale), 1.0, k)

    def test_every_code_lies_between_its_thresholds(self) -> None:
        decode, thresholds = textures.SRGB_TO_LINEAR_Q24, textures.SRGB_ROUNDING_THRESHOLDS_Q24
        self.assertEqual((len(decode), len(thresholds)), (256, 255))
        for k in range(255):
            self.assertLess(decode[k], thresholds[k])
            self.assertLess(thresholds[k], decode[k + 1])


class PlanTests(unittest.TestCase):
    def test_a_fitting_texture_is_kept(self) -> None:
        plan = textures.plan_texture(make_png(4, 4), label="f/img")
        measured = (plan.mime_type, plan.factor, plan.out_width, plan.out_height)
        self.assertEqual(measured, ("image/png", 1, 4, 4))

    def test_an_8k_texture_fails_early_with_a_remedy(self) -> None:
        with self.assertRaises(textures.TextureError) as caught:
            textures.plan_texture(make_jpeg_header(8192, 8192), label="witch/Image_0")
        message = str(caught.exception)
        self.assertIn("witch/Image_0", message)
        self.assertIn("8192x8192", message)
        self.assertIn("--max-texture-size 4096", message)

    def test_a_side_over_8192_fails_even_below_the_pixel_limit(self) -> None:
        with self.assertRaises(textures.TextureError) as caught:
            textures.plan_texture(make_jpeg_header(16384, 1024), label="t")
        self.assertIn("--max-texture-size 8192", str(caught.exception))

    def test_max_size_picks_the_smallest_power_of_two(self) -> None:
        plan = textures.plan_texture(make_jpeg_header(8192, 8192), label="t", max_size=1024)
        self.assertEqual((plan.factor, plan.out_width, plan.out_height), (8, 1024, 1024))
        plan = textures.plan_texture(make_jpeg_header(1000, 600), label="t", max_size=300)
        self.assertEqual((plan.factor, plan.out_width, plan.out_height), (4, 250, 150))
        self.assertEqual(textures.plan_texture(make_png(4, 4), label="t", max_size=1024).factor, 1)

    def test_sizes_that_do_not_divide_are_rejected(self) -> None:
        with self.assertRaises(textures.TextureError):
            textures.plan_texture(make_jpeg_header(1001, 600), label="t", max_size=512)
        with self.assertRaises(textures.TextureError):
            textures.plan_texture(make_png(4, 4), label="t", max_size=0)


@needs_imaging
class ReduceTests(unittest.TestCase):
    def test_uniform_blocks_keep_their_code(self) -> None:
        codes = np.arange(256, dtype=np.uint8)
        row = np.stack([codes, codes[::-1], codes, codes], axis=-1)  # 256 x 4
        image = np.repeat(np.repeat(row[None], 2, axis=0), 2, axis=1)  # 2 x 512 x 4: 2x2 blocks
        reduced = textures.box_reduce(image, 2, srgb=True)
        self.assertEqual(reduced[0, :, 0].tolist(), list(range(256)))
        self.assertEqual(reduced[0, :, 1].tolist(), list(range(255, -1, -1)))
        self.assertEqual(textures.box_reduce(image, 2, srgb=False)[0, :, 3].tolist(), list(range(256)))

    def test_half_white_is_188_in_srgb_and_128_in_linear_data(self) -> None:
        image = np.zeros((2, 2, 4), dtype=np.uint8)
        image[0, :, :3] = 255
        image[:, 0, 3] = 255
        self.assertEqual(textures.box_reduce(image, 2, srgb=True)[0, 0].tolist(), [187, 187, 187, 128])  # deliberately wrong: CI proof, reverted in the next commit
        self.assertEqual(textures.box_reduce(image, 2, srgb=False)[0, 0].tolist(), [128, 128, 128, 128])

    def test_matches_the_float_rule_of_the_engine(self) -> None:
        # The engine averages in linear light with floats and rounds in sRGB. The integer version
        # may differ only where a mean sits within rounding noise of a code boundary.
        rng = np.random.default_rng(7)
        image = rng.integers(0, 256, size=(64, 64, 3), dtype=np.uint8)
        reduced = textures.box_reduce(image, 4, srgb=True).astype(int)
        blocks = image.reshape(16, 4, 16, 4, 3).transpose(0, 2, 1, 3, 4).reshape(16, 16, 16, 3)
        mean = np.vectorize(srgb_to_linear)(blocks / 255.0).mean(axis=2)
        expected = np.floor(np.vectorize(linear_to_srgb)(mean) * 255.0 + 0.5).astype(int)
        self.assertLessEqual(int(np.abs(reduced - expected).max()), 1)
        self.assertGreaterEqual(float((reduced == expected).mean()), 0.999)

    def test_factor_must_divide_and_one_copies(self) -> None:
        image = np.zeros((6, 6, 3), dtype=np.uint8)
        with self.assertRaises(textures.TextureError):
            textures.box_reduce(image, 4, srgb=False)
        copy = textures.box_reduce(image, 1, srgb=False)
        self.assertIsNot(copy, image)
        self.assertTrue((copy == image).all())


@needs_imaging
class DecodeTests(unittest.TestCase):
    def test_png_is_decoded_by_the_standard_library_and_reduced(self) -> None:
        rows = [bytes([255, 0, 0] * 2 + [0, 0, 255] * 2)] * 4
        data = make_png(4, 4, rows=rows)
        plan = textures.plan_texture(data, label="t", max_size=2)
        rgba = textures.decode_texture(data, plan, srgb=False, label="t")
        self.assertEqual(list(rgba), [255, 0, 0, 255, 0, 0, 255, 255] * 2)

    def test_jpeg_is_decoded_by_pillow_and_matches_it(self) -> None:
        pixels = np.random.default_rng(3).integers(0, 256, size=(16, 16, 3), dtype=np.uint8)
        buffer = io.BytesIO()
        Image.fromarray(pixels).save(buffer, format="JPEG", quality=95)
        data = buffer.getvalue()
        plan = textures.plan_texture(data, label="t")
        rgba = textures.decode_texture(data, plan, srgb=True, label="t")
        expected = Image.open(io.BytesIO(data)).convert("RGBA").tobytes()
        self.assertEqual(rgba, expected)
        halved = textures.plan_texture(data, label="t", max_size=8)
        reduced = textures.decode_texture(data, halved, srgb=True, label="t")
        full = np.frombuffer(expected, dtype=np.uint8).reshape(16, 16, 4)
        self.assertEqual(reduced, textures.box_reduce(full, 2, srgb=True).tobytes())

    def test_cmyk_jpeg_is_rejected(self) -> None:
        buffer = io.BytesIO()
        Image.new("CMYK", (8, 8)).save(buffer, format="JPEG")
        data = buffer.getvalue()
        with self.assertRaises(textures.TextureError):
            textures.decode_texture(data, textures.plan_texture(data, label="t"), srgb=True, label="t")


class FigureGlb:
    """A one-triangle skinned figure with a textured material (base colour, normal map)."""

    def __init__(self, base_color: bytes, normal: bytes) -> None:
        self.doc: dict = {"asset": {"version": "2.0"}, "accessors": [], "bufferViews": [], "buffers": [{}]}
        self.bin = bytearray()
        position = self.floats([(0, 0, 0), (1, 0, 0), (0, 1, 0)], "VEC3", bounds=True)
        attributes = {
            "POSITION": position,
            "NORMAL": self.floats([(0, 0, 1)] * 3, "VEC3"),
            "TEXCOORD_0": self.floats([(0, 0), (1, 0), (0, 1)], "VEC2"),
            "TANGENT": self.floats([(1, 0, 0, 1)] * 3, "VEC4"),
            "JOINTS_0": self.accessor(self.view(bytes(12)), 5121, 3, "VEC4"),
            "WEIGHTS_0": self.floats([(1, 0, 0, 0)] * 3, "VEC4"),
        }
        indices = self.accessor(self.view(struct.pack("<3I", 0, 1, 2)), 5125, 3, "SCALAR")
        self.doc["images"] = [
            {"bufferView": self.view(base_color), "mimeType": "image/jpeg", "name": "base"},
            {"bufferView": self.view(normal), "mimeType": "image/png", "name": "normal"},
        ]
        self.doc["textures"] = [{"source": 0}, {"source": 1}]
        self.doc["materials"] = [{"pbrMetallicRoughness": {"baseColorTexture": {"index": 0}},
                                  "normalTexture": {"index": 1}}]
        primitive = {"attributes": attributes, "indices": indices, "material": 0}
        self.doc["meshes"] = [{"primitives": [primitive]}]
        self.doc["nodes"] = [{"name": "root"}, {"name": "body", "mesh": 0, "skin": 0}]
        self.doc["skins"] = [{"joints": [0]}]
        self.doc["scenes"] = [{"nodes": [0, 1]}]

    def view(self, data: bytes) -> int:
        while len(self.bin) % 4:
            self.bin.append(0)
        self.doc["bufferViews"].append({"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)})
        self.bin.extend(data)
        return len(self.doc["bufferViews"]) - 1

    def accessor(self, view: int, component_type: int, count: int, type_: str, **extra) -> int:
        self.doc["accessors"].append({"bufferView": view, "componentType": component_type, "count": count,
                                      "type": type_, **extra})
        return len(self.doc["accessors"]) - 1

    def floats(self, rows, type_: str, *, bounds: bool = False) -> int:
        width = len(rows[0])
        view = self.view(b"".join(struct.pack(f"<{width}f", *row) for row in rows))
        extra = {"min": [min(r[i] for r in rows) for i in range(width)],
                 "max": [max(r[i] for r in rows) for i in range(width)]} if bounds else {}
        return self.accessor(view, 5126, len(rows), type_, **extra)

    def write(self, path: Path) -> Path:
        while len(self.bin) % 4:
            self.bin.append(0)
        self.doc["buffers"][0]["byteLength"] = len(self.bin)
        body = json.dumps(self.doc).encode()
        body += b" " * (-len(body) % 4)
        data = (struct.pack("<4sII", b"glTF", 2, 28 + len(body) + len(self.bin))
                + struct.pack("<II", len(body), 0x4E4F534A) + body
                + struct.pack("<II", len(self.bin), 0x004E4942) + bytes(self.bin))
        path.write_bytes(data)
        return path


class BuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_main(self, *args: str) -> tuple[int, str]:
        stderr = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            code = build_figure_pack.main(list(args))
        return code, stderr.getvalue()

    def test_oversized_textures_of_all_figures_fail_before_anything_is_written(self) -> None:
        a = FigureGlb(make_jpeg_header(8192, 8192), make_png(4, 4)).write(self.tmp / "a.glb")
        b = FigureGlb(make_jpeg_header(16384, 16384), make_png(4, 4)).write(self.tmp / "b.glb")
        out = self.tmp / "out"
        code, stderr = self.run_main("--figure", f"witch={a}", "--figure", f"imp={b}", "--out", str(out))
        self.assertEqual(code, 1)
        self.assertIn("witch/base", stderr)
        self.assertIn("imp/base", stderr)
        self.assertFalse(out.exists())

    def test_figure_arguments_are_validated(self) -> None:
        a = FigureGlb(make_png(4, 4), make_png(4, 4)).write(self.tmp / "a.glb")
        self.assertEqual(self.run_main("--out", str(self.tmp / "o"))[0], 1)
        self.assertEqual(self.run_main("--figure", "no-equals-sign", "--out", str(self.tmp / "o"))[0], 1)
        twice = ("--figure", f"x={a}", "--figure", f"x={a}")
        code, stderr = self.run_main(*twice, "--out", str(self.tmp / "o"))
        self.assertEqual(code, 1)
        self.assertIn("given twice", stderr)

    @needs_imaging
    def test_a_jpeg_figure_packs_with_its_texture_reduced(self) -> None:
        pixels = np.full((16, 16, 3), (200, 120, 40), dtype=np.uint8)
        buffer = io.BytesIO()
        Image.fromarray(pixels).save(buffer, format="JPEG", quality=100)
        flat_normals = make_png(8, 8, rows=[bytes([128, 128, 255] * 8)] * 8)
        glb = FigureGlb(buffer.getvalue(), flat_normals).write(self.tmp / "w.glb")
        out = self.tmp / "out"
        args = ("--figure", f"witch={glb}", "--max-texture-size", "4", "--out", str(out))
        code, stderr = self.run_main(*args)
        self.assertEqual(code, 0, stderr)
        index = json.loads((out / "index.json").read_text())
        texture_entries = [e for e in index["entries"] if "/texture/" in e["path"]]
        paths = [e["path"] for e in texture_entries]
        self.assertEqual(paths, ["figures/witch/texture/0", "figures/witch/texture/1"])
        for entry in texture_entries:
            payload = (out / entry["file"]).read_bytes()
            _version, width, height, _space = struct.unpack_from("<IIIB", payload)
            self.assertEqual((width, height), (4, 4))
            self.assertEqual(len(payload), 13 + 4 * 4 * 4)


if __name__ == "__main__":
    unittest.main()
