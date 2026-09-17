"""Unit tests for the asset budget check. Standard-library `unittest`, synthetic .glb files only.

Run with `python -B -m unittest test_check_asset.py` from this directory.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

import check_asset
import glb_facts
import image_headers

HERE = Path(__file__).resolve().parent


# ------------------------------------------------------------------------------ test fixtures


def make_png(width: int, height: int, color_type: int = 2, *, trns: bool = False) -> bytes:
    """A valid, all-zero PNG (filter 0 rows)."""
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]

    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body))

    raw = b"".join(b"\x00" + bytes(width * channels) for _ in range(height))
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


ENEMY_CLIPS = ("idle", "walk", "attack", "hit_react", "death")


class GlbBuilder:
    """Assembles a small glTF binary from Python values."""

    def __init__(self) -> None:
        self.doc: dict = {
            "asset": {"version": "2.0"},
            "scene": 0,
            "scenes": [{"nodes": []}],
            "nodes": [],
            "meshes": [],
            "materials": [],
            "textures": [],
            "images": [],
            "accessors": [],
            "bufferViews": [],
            "buffers": [{"byteLength": 0}],
        }
        self.bin = bytearray()

    def view(self, data: bytes) -> int:
        while len(self.bin) % 4:
            self.bin.append(0)
        view = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        self.doc["bufferViews"].append(view)
        self.bin.extend(data)
        return len(self.doc["bufferViews"]) - 1

    def floats(self, rows: list[tuple[float, ...]], type_: str, *, bounds: bool = False) -> int:
        width = len(rows[0])
        view = self.view(b"".join(struct.pack(f"<{width}f", *row) for row in rows))
        accessor = {"bufferView": view, "componentType": 5126, "count": len(rows), "type": type_}
        if bounds:
            accessor["min"] = [min(r[i] for r in rows) for i in range(width)]
            accessor["max"] = [max(r[i] for r in rows) for i in range(width)]
        self.doc["accessors"].append(accessor)
        return len(self.doc["accessors"]) - 1

    def indices(self, values: list[int]) -> int:
        view = self.view(struct.pack(f"<{len(values)}I", *values))
        return self._accessor(view, 5125, len(values), "SCALAR")

    def joints(self, rows: list[tuple[int, int, int, int]]) -> int:
        view = self.view(b"".join(struct.pack("<4B", *row) for row in rows))
        return self._accessor(view, 5121, len(rows), "VEC4")

    def _accessor(self, view: int, component_type: int, count: int, type_: str) -> int:
        accessor = {"bufferView": view, "componentType": component_type, "count": count, "type": type_}
        self.doc["accessors"].append(accessor)
        return len(self.doc["accessors"]) - 1

    def texture(self, data: bytes, mime: str) -> int:
        self.doc["images"].append({"bufferView": self.view(data), "mimeType": mime})
        self.doc["textures"].append({"source": len(self.doc["images"]) - 1})
        return len(self.doc["textures"]) - 1

    def node(self, node: dict, *, root: bool = True) -> int:
        self.doc["nodes"].append(node)
        index = len(self.doc["nodes"]) - 1
        if root:
            self.doc["scenes"][0]["nodes"].append(index)
        return index

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


def figure_points(front: float = 1.0) -> list[tuple[float, float, float]]:
    """A 1 m 'figure' as points: two feet whose toes reach towards `front` * Z, ankles, a head."""
    points = []
    for x in (-0.1, 0.1):
        points += [(x, 0.0, 0.12 * front), (x, 0.01, 0.10 * front), (x, 0.0, -0.02 * front)]
        points += [(x, 0.12, 0.0), (x, 0.12, 0.01), (x, 0.12, -0.01)]
    points += [(0.0, 1.0, 0.0), (0.05, 0.9, 0.0), (-0.05, 0.9, 0.0)]
    return points


def build_figure(
    *,
    front: float = 1.0,
    left_x: float = 0.1,
    image: tuple[bytes, str] | None = None,
    tangents: bool = True,
    extra_influences: bool = False,
    clips: tuple[str, ...] = ENEMY_CLIPS,
    lift: float = 0.0,
    triangle_copies: int = 1,
) -> bytes:
    """A skinned figure: root, foot.L, foot.R; textured material with a normal map."""
    g = GlbBuilder()
    points = [(x, y + lift, z) for x, y, z in figure_points(front)]
    count = len(points)
    attributes = {
        "POSITION": g.floats(points, "VEC3", bounds=True),
        "NORMAL": g.floats([(0.0, 0.0, 1.0)] * count, "VEC3"),
        "TEXCOORD_0": g.floats([(0.5, 0.5)] * count, "VEC2"),
        "JOINTS_0": g.joints([(0, 0, 0, 0)] * count),
        "WEIGHTS_0": g.floats([(1.0, 0.0, 0.0, 0.0)] * count, "VEC4"),
    }
    if tangents:
        attributes["TANGENT"] = g.floats([(1.0, 0.0, 0.0, 1.0)] * count, "VEC4")
    if extra_influences:
        attributes["JOINTS_1"] = g.joints([(0, 0, 0, 0)] * count)
        attributes["WEIGHTS_1"] = g.floats([(0.0, 0.0, 0.0, 0.0)] * count, "VEC4")
    triangle_indices = [i % count for i in range(count - count % 3)] * triangle_copies
    image_data, mime = image or (make_png(4, 4), "image/png")
    base = g.texture(image_data, mime)
    normal = g.texture(make_png(4, 4), "image/png")
    pbr = {"baseColorTexture": {"index": base}}
    g.doc["materials"].append({"pbrMetallicRoughness": pbr, "normalTexture": {"index": normal}})
    primitive = {"attributes": attributes, "indices": g.indices(triangle_indices), "material": 0}
    g.doc["meshes"].append({"primitives": [primitive]})

    root = g.node({"name": "root", "children": [1, 2]})
    g.node({"name": "foot.L", "translation": [left_x, 0.05, 0.0]}, root=False)
    g.node({"name": "foot.R", "translation": [-left_x, 0.05, 0.0]}, root=False)
    inverse_binds = []
    for tx in (0.0, left_x, -left_x):
        inverse_binds.append((1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -tx, -0.05 if tx else 0.0, 0, 1))
    inverse_bind_accessor = g.floats(inverse_binds, "MAT4")
    g.doc["skins"] = [{"joints": [root, 1, 2], "inverseBindMatrices": inverse_bind_accessor}]
    g.node({"name": "body", "mesh": 0, "skin": 0})

    if clips:
        times = g.floats([(0.0,), (0.5,)], "SCALAR", bounds=True)
        moves = g.floats([(0.0, 0.0, 0.0), (0.0, 0.1, 0.0)], "VEC3")
        g.doc["animations"] = [
            {
                "name": name,
                "samplers": [{"input": times, "output": moves}],
                "channels": [{"sampler": 0, "target": {"node": root, "path": "translation"}}],
            }
            for name in clips
        ]
    return g.build()


TEST_BUDGETS = {
    "format": 1,
    "engine": {
        "max_primitive_vertices": 1000,
        "max_primitive_indices": 3000,
        "max_texture_pixels": 64_000_000,
        "max_texture_dimension": 8192,
        "max_skin_joints": 256,
    },
    "pipeline": {
        "accepted_image_types": ["image/png"],
        "front_axis": "+Z",
        "foot_level_tolerance_share": 0.02,
        "center_tolerance_share": 0.15,
        "rest_pose_tolerance": 0.001,
    },
    "roles": {
        "enemy": {
            "height_m": [0.5, 3.0],
            "max_triangles": 100,
            "max_vertices": 100,
            "max_primitives": 2,
            "require_skin": True,
            "max_joints": 8,
            "max_textures": 4,
            "max_texture_dimension": 1024,
            "max_gpu_mib": 1,
            "expect_normal_map": True,
            "clips": {"severity": "warn", "required": list(ENEMY_CLIPS), "optional": []},
        }
    },
}


class TempDirTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.budgets_path = self.tmp / "budgets.json"
        self.budgets_path.write_text(json.dumps(TEST_BUDGETS), encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, name: str, data: bytes) -> Path:
        path = self.tmp / name
        path.write_bytes(data)
        return path

    def run_check(
        self, asset: Path, role: str = "enemy", budgets: Path | None = None
    ) -> tuple[int, dict | None]:
        report_path = self.tmp / "report.json"
        report_path.unlink(missing_ok=True)
        budgets = budgets or self.budgets_path
        args = [str(asset), "--role", role, "--budgets", str(budgets), "--json-out", str(report_path)]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = check_asset.main(args)
        report = None
        if report_path.exists():
            report = json.loads(report_path.read_text(encoding="utf-8"))
        return code, report


def statuses(report: dict) -> dict[str, str]:
    return {c["id"]: c["status"] for c in report["checks"]}


# ------------------------------------------------------------------------------------ tests


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
        measured = (header.mime_type, header.width, header.height, header.channels)
        self.assertEqual(measured, ("image/jpeg", 8192, 4096, 3))
        self.assertFalse(header.progressive)
        progressive = image_headers.read_jpeg_header(make_jpeg_header(16, 16, progressive=True))
        self.assertTrue(progressive.progressive)

    def test_unknown_bytes_are_rejected(self) -> None:
        with self.assertRaises(image_headers.ImageHeaderError):
            image_headers.read_image_header(b"GIF89a....")
        with self.assertRaises(image_headers.ImageHeaderError):
            image_headers.read_jpeg_header(b"\xff\xd8\xff\xd9")


class MeasureTests(TempDirTestCase):
    def test_mip_chain_bytes_match_the_engine_rule(self) -> None:
        self.assertEqual(glb_facts.engine_texture_bytes_with_mips(4, 2), (8 + 2 + 1) * 4)
        self.assertEqual(glb_facts.engine_texture_bytes_with_mips(8192, 8192), 357_913_940)
        self.assertEqual(glb_facts.engine_texture_bytes_with_mips(1024, 1024), 5_592_404)

    def test_counts_for_indexed_unindexed_strip_and_instanced_meshes(self) -> None:
        g = GlbBuilder()
        quad = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
        position = g.floats(quad, "VEC3", bounds=True)
        indexed = {"attributes": {"POSITION": position}, "indices": g.indices([0, 1, 2, 0, 2, 3])}
        unindexed = {"attributes": {"POSITION": g.floats(quad[:3] * 2, "VEC3", bounds=True)}}
        strip = {"attributes": {"POSITION": position}, "mode": 5}
        g.doc["meshes"] = [{"primitives": [indexed, unindexed]}, {"primitives": [strip]}]
        g.node({"mesh": 0})
        g.node({"mesh": 0, "translation": [5.0, 0.0, 0.0]})
        g.node({"mesh": 1})
        facts = glb_facts.measure_glb(self.write("counts.glb", g.build()))
        geometry = facts["geometry"]
        # mesh 0 drawn twice: (2 + 2) triangles each; the strip of 4 vertices adds 2.
        self.assertEqual(geometry["triangles"], 10)
        self.assertEqual(geometry["vertices"], (4 + 6) * 2 + 4)
        self.assertEqual(geometry["primitives"], 5)
        # GPU memory counts each (POSITION, indices) pair once: 4v+6i, 6v+6i (unindexed), 4v+4i.
        self.assertEqual(geometry["gpu_mesh_bytes"], (4 + 6 + 4) * 72 + (6 + 6 + 4) * 4)
        self.assertEqual(geometry["attributes"]["NORMAL"], "none")
        self.assertEqual(geometry["primitives_without_material"], 5)

    def test_bounds_follow_node_transforms_and_decode_missing_min_max(self) -> None:
        g = GlbBuilder()
        points = [(-0.5, -0.5, 0.0), (0.5, -0.5, 0.0), (0.0, 0.5, 0.0)]
        g.doc["meshes"] = [{"primitives": [{"attributes": {"POSITION": g.floats(points, "VEC3")}}]}]
        g.node({"scale": [2.0, 2.0, 2.0], "children": [1]})
        g.node({"mesh": 0, "translation": [0.0, 0.5, 0.0]}, root=False)
        bounds = glb_facts.measure_glb(self.write("bounds.glb", g.build()))["bounds"]
        self.assertEqual(bounds["space"], "world")
        self.assertAlmostEqual(bounds["height_y_m"], 2.0, places=5)
        self.assertAlmostEqual(bounds["foot_level_y_m"], 0.0, places=5)
        self.assertAlmostEqual(bounds["width_x_m"], 2.0, places=5)

    def test_node_matrix_equals_trs(self) -> None:
        quarter_turn_y = [0, 0.7071068, 0, 0.7071068]
        node = {"translation": [1, 2, 3], "rotation": quarter_turn_y, "scale": [2, 2, 2]}
        trs = glb_facts.mat4_from_node(node)
        self.assertEqual(glb_facts.mat4_from_node({"matrix": list(trs)}), trs)
        # 90 degrees about +Y turns +X into -Z; scale 2, then translate.
        x, y, z = glb_facts.mat4_transform_point(trs, (1.0, 0.0, 0.0))
        self.assertAlmostEqual(x, 1.0, places=5)
        self.assertAlmostEqual(y, 2.0, places=5)
        self.assertAlmostEqual(z, 1.0, places=5)

    def test_skinned_figure_facts(self) -> None:
        facts = glb_facts.measure_glb(self.write("figure.glb", build_figure()))
        (skin,) = facts["skins"]
        self.assertEqual(skin["joints"], 3)
        self.assertEqual(skin["joint_names"], ["root", "foot.L", "foot.R"])
        self.assertLess(skin["rest_pose_vs_bind_pose_max_error"], 1e-6)
        self.assertEqual(facts["facing"]["axis"], "+Z")
        self.assertEqual(facts["facing"]["agreement"], "agree")
        self.assertEqual([t["slots"] for t in facts["textures"]], [["baseColor"], ["normal"]])
        self.assertEqual([a["name"] for a in facts["animations"]], list(ENEMY_CLIPS))
        self.assertAlmostEqual(facts["animations"][0]["duration_s"], 0.5)

    def test_joint_side_tokens(self) -> None:
        lefts = ("hand.L", "thigh_l", "Bip01 L Thigh", "mixamorig:LeftArm", "socket_skillshot_l")
        for name in lefts:
            self.assertEqual(glb_facts.joint_side(name), "left", name)
        for name in ("hand.R", "RightUpLeg", "leg-r"):
            self.assertEqual(glb_facts.joint_side(name), "right", name)
        for name in ("spine", "Lower", "root", "clavicle"):
            self.assertIsNone(glb_facts.joint_side(name), name)

    def test_facing_from_joints_and_toes(self) -> None:
        left_plus_x = [("hand.L", (0.2, 1.0, 0.0)), ("hand.R", (-0.2, 1.0, 0.0))]
        left_minus_x = [("hand.L", (-0.2, 1.0, 0.0)), ("hand.R", (0.2, 1.0, 0.0))]
        self.assertEqual(glb_facts.facing_from_joints(left_plus_x, 1.8)["axis"], "+Z")
        self.assertEqual(glb_facts.facing_from_joints(left_minus_x, 1.8)["axis"], "-Z")
        self.assertIsNone(glb_facts.facing_from_joints([("hand.L", (0.2, 1.0, 0.0))], 1.8)["axis"])

        def flat(points):
            from array import array

            return [array("f", [c for p in points for c in p])]

        forward = glb_facts.facing_from_toes(flat(figure_points(1.0)), 1.0, 0.0)
        backward = glb_facts.facing_from_toes(flat(figure_points(-1.0)), 1.0, 0.0)
        self.assertEqual((forward["axis"], backward["axis"]), ("+Z", "-Z"))
        symmetric = [(0.0, 0.0, 0.1), (0.0, 0.0, -0.1), (0.0, 0.12, 0.0), (0.0, 1.0, 0.0)]
        self.assertIsNone(glb_facts.facing_from_toes(flat(symmetric), 1.0, 0.0)["axis"])

    def test_combine_facing(self) -> None:
        plus, minus, none = {"axis": "+Z"}, {"axis": "-Z"}, {"axis": None}
        self.assertEqual(glb_facts.combine_facing([plus, plus])["agreement"], "agree")
        self.assertEqual(glb_facts.combine_facing([plus, none])["agreement"], "single method")
        self.assertEqual(glb_facts.combine_facing([none])["agreement"], "undetermined")
        conflict = glb_facts.combine_facing([plus, minus])
        self.assertEqual(conflict["agreement"], "conflict")
        self.assertEqual(conflict["candidates"], ["+Z", "-Z"])

    def test_texture_sizes_come_from_headers(self) -> None:
        figure = build_figure(image=(make_jpeg_header(8192, 8192), "image/jpeg"))
        facts = glb_facts.measure_glb(self.write("jpeg.glb", figure))
        base = facts["textures"][0]
        measured = (base["sniffed_mime_type"], base["width"], base["height"])
        self.assertEqual(measured, ("image/jpeg", 8192, 8192))
        self.assertEqual(base["gpu_bytes_rgba8_with_mips"], 357_913_940)
        self.assertEqual(base["pack_raw_bytes"], 8192 * 8192 * 4)


class CheckTests(TempDirTestCase):
    def test_compliant_figure_passes(self) -> None:
        code, report = self.run_check(self.write("ok.glb", build_figure()))
        self.assertEqual(code, check_asset.EXIT_PASS)
        self.assertEqual(report["verdict"], "pass")
        self.assertEqual(report["counts"]["fail"], 0)
        self.assertEqual(report["asset"]["name"], "ok.glb")
        self.assertNotIn(str(self.tmp), json.dumps(report), "the report must not carry local paths")

    def test_triangle_budget_fails(self) -> None:
        code, report = self.run_check(self.write("dense.glb", build_figure(triangle_copies=40)))
        self.assertEqual(code, check_asset.EXIT_FAIL)
        self.assertEqual(statuses(report)["budget.triangles"], "fail")

    def test_jpeg_and_oversized_texture_fail(self) -> None:
        figure = build_figure(image=(make_jpeg_header(8192, 8192), "image/jpeg"))
        asset = self.write("jpeg.glb", figure)
        code, report = self.run_check(asset)
        self.assertEqual(code, check_asset.EXIT_FAIL)
        result = statuses(report)
        self.assertEqual(result["pipeline.image_types"], "fail")
        self.assertEqual(result["engine.texture_pixels"], "fail")
        self.assertEqual(result["engine.texture_dimension"], "pass")
        self.assertEqual(result["budget.texture_dimension"], "fail")
        self.assertEqual(result["budget.gpu_memory"], "fail")

    def test_declared_mime_type_must_match_the_bytes(self) -> None:
        figure = build_figure(image=(make_png(4, 4), "image/jpeg"))
        code, report = self.run_check(self.write("liar.glb", figure))
        self.assertEqual(code, check_asset.EXIT_FAIL)
        self.assertEqual(statuses(report)["pipeline.image_types"], "fail")

    def test_uv_without_tangent_and_extra_influences_fail(self) -> None:
        figure = build_figure(tangents=False, extra_influences=True)
        code, report = self.run_check(self.write("raw.glb", figure))
        self.assertEqual(code, check_asset.EXIT_FAIL)
        result = statuses(report)
        self.assertEqual(result["pipeline.tangents"], "fail")
        self.assertEqual(result["engine.skin_influences"], "fail")

    def test_missing_clips_only_warn(self) -> None:
        figure = build_figure(clips=("idle", "walk", "wave"))
        code, report = self.run_check(self.write("two_clips.glb", figure))
        self.assertEqual(code, check_asset.EXIT_PASS)
        clip_check = next(c for c in report["checks"] if c["id"] == "budget.clips")
        self.assertEqual(clip_check["status"], "warn")
        self.assertEqual(clip_check["measured"]["missing"], ["attack", "hit_react", "death"])
        self.assertEqual(clip_check["measured"]["unexpected"], ["wave"])

    def test_facing_backwards_and_mirrored_side_names_fail(self) -> None:
        _, backwards = self.run_check(self.write("back.glb", build_figure(front=-1.0, left_x=-0.1)))
        facing = next(c for c in backwards["checks"] if c["id"] == "convention.facing")
        self.assertEqual((facing["status"], facing["measured"]), ("fail", "-Z (agree)"))
        _, mirrored = self.run_check(self.write("mirror.glb", build_figure(front=1.0, left_x=-0.1)))
        facing = next(c for c in mirrored["checks"] if c["id"] == "convention.facing")
        self.assertEqual((facing["status"], facing["measured"]), ("fail", ["+Z", "-Z"]))

    def test_origin_not_at_the_feet_fails(self) -> None:
        code, report = self.run_check(self.write("lifted.glb", build_figure(lift=-0.5)))
        self.assertEqual(code, check_asset.EXIT_FAIL)
        self.assertEqual(statuses(report)["convention.foot_level"], "fail")

    def test_unreadable_inputs_exit_with_error(self) -> None:
        figure = self.write("ok.glb", build_figure())
        self.assertEqual(self.run_check(figure, role="dragon")[0], check_asset.EXIT_ERROR)
        not_glb = self.write("not.glb", b"not a glb at all")
        self.assertEqual(self.run_check(not_glb)[0], check_asset.EXIT_ERROR)
        broken = copy.deepcopy(TEST_BUDGETS)
        del broken["roles"]["enemy"]["max_triangles"]
        broken_path = self.tmp / "broken.json"
        broken_path.write_text(json.dumps(broken), encoding="utf-8")
        self.assertEqual(self.run_check(figure, budgets=broken_path)[0], check_asset.EXIT_ERROR)

    def test_shipped_budget_file_defines_every_role(self) -> None:
        for role in ("player", "enemy", "boss", "prop"):
            budgets = check_asset.load_budgets(HERE / "budgets.json", role)
            self.assertIn(role, budgets["roles"])

    def test_summary_names_every_check(self) -> None:
        facts = glb_facts.measure_glb(self.write("ok.glb", build_figure()))
        checks = check_asset.evaluate(facts, TEST_BUDGETS, "enemy")
        report = check_asset.build_report(facts, TEST_BUDGETS, self.budgets_path, "enemy", checks)
        summary = check_asset.format_summary(report)
        for check in checks:
            self.assertIn(check.id, summary)


if __name__ == "__main__":
    unittest.main()
