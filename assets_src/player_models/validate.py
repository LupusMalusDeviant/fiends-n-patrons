#!/usr/bin/env python3
"""Validate this package's embedded, skinned GLB 2.0 player-model profile.

Python standard library only. This is an offline asset check for PRD-0003
FR-13 / PRD-0016 FR-09, not a complete Khronos validator or an engine/render gate.
Sparse accessors and compressed geometry are deliberately outside this profile.
Reference: https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys
import zlib


MODEL_IDS = {"iron_penitent", "ash_reaver", "veil_warden"}
ANIMATIONS = {"idle", "walk", "melee", "dash"}
COMPONENTS = {
    5120: ("b", 1, -128, 127), 5121: ("B", 1, 0, 255),
    5122: ("h", 2, -32768, 32767), 5123: ("H", 2, 0, 65535),
    5125: ("I", 4, 0, 4294967295), 5126: ("f", 4, None, None),
}
COUNTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4,
          "MAT2": 4, "MAT3": 9, "MAT4": 16}
PRIVATE_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|^/|(?:^|[/\\])(?:Users|home)[/\\])", re.I)


class Invalid(ValueError):
    """A precise package-contract violation, with no private path in its text."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Invalid(message)


def integer(value, where: str, minimum: int = 0) -> int:
    require(type(value) is int and value >= minimum, f"{where}: invalid integer")
    return value


def numbers(values, count: int, where: str):
    require(isinstance(values, list) and len(values) == count, f"{where}: invalid vector size")
    require(all(type(v) in (int, float) and math.isfinite(v) for v in values),
            f"{where}: non-finite or non-numeric value")
    return values


def portable_json(value, where="json") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            require(key.lower() != "uri", f"{where}: URI references are forbidden")
            portable_json(child, f"{where}.{key}")
    elif isinstance(value, list):
        for child in value:
            portable_json(child, where)
    elif isinstance(value, str):
        require(not PRIVATE_PATH.search(value), f"{where}: absolute/private path found")
    elif isinstance(value, float):
        require(math.isfinite(value), f"{where}: non-finite number")


def parse_glb(blob: bytes):
    require(len(blob) >= 28, "GLB: truncated header/chunks")
    magic, version, length = struct.unpack_from("<III", blob)
    require(magic == 0x46546C67 and version == 2, "GLB: expected glTF magic/version 2")
    require(length == len(blob) and length % 4 == 0, "GLB: header length/alignment mismatch")
    chunks = []
    cursor = 12
    while cursor < length:
        require(cursor + 8 <= length, "GLB: truncated chunk header")
        size, kind = struct.unpack_from("<II", blob, cursor)
        cursor += 8
        require(size % 4 == 0 and cursor + size <= length, "GLB: chunk length/alignment invalid")
        chunks.append((kind, blob[cursor:cursor + size]))
        cursor += size
    require([kind for kind, _ in chunks] == [0x4E4F534A, 0x004E4942],
            "GLB: this package requires one JSON chunk followed by one BIN chunk")
    try:
        data = json.loads(chunks[0][1].decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise Invalid("GLB: invalid UTF-8 JSON") from exc
    require(isinstance(data, dict), "GLB: JSON root must be an object")
    portable_json(data)
    require(data.get("asset", {}).get("version") == "2.0", "asset.version must be 2.0")
    required_extensions = data.get("extensionsRequired", [])
    require(not required_extensions, "Required glTF extensions are outside this package profile")
    return data, chunks[1][1]


class Asset:
    def __init__(self, data, binary):
        self.data, self.binary = data, binary
        self.cache = {}

    def item(self, collection, index, where):
        items = self.data.get(collection, [])
        integer(index, where)
        require(isinstance(items, list) and index < len(items), f"{where}: invalid {collection} reference")
        require(isinstance(items[index], dict), f"{where}: expected object")
        return items[index]

    def view(self, index, where):
        view = self.item("bufferViews", index, where)
        start = view.get("byteOffset", 0)
        return self.binary[start:start + view["byteLength"]]

    def buffers(self):
        buffers = self.data.get("buffers", [])
        require(len(buffers) == 1, "buffers: expected one embedded buffer")
        size = integer(buffers[0].get("byteLength"), "buffer.byteLength", 1)
        require(size <= len(self.binary) <= size + 3, "buffer.byteLength disagrees with BIN chunk")
        require(not any(self.binary[size:]), "BIN padding must be zero")
        for i, view in enumerate(self.data.get("bufferViews", [])):
            where = f"bufferViews[{i}]"
            require(view.get("buffer") == 0, f"{where}: buffer must be 0")
            start = integer(view.get("byteOffset", 0), where + ".byteOffset")
            length = integer(view.get("byteLength"), where + ".byteLength", 1)
            require(start + length <= size, f"{where}: exceeds buffer")
            if "byteStride" in view:
                stride = integer(view["byteStride"], where + ".byteStride", 4)
                require(stride <= 252 and stride % 4 == 0, f"{where}: invalid byteStride")
            require(view.get("target", 34962) in (34962, 34963), f"{where}: invalid target")
        require(self.data.get("accessors"), "accessors: none present")
        for i in range(len(self.data["accessors"])):
            self.accessor(i)

    def accessor(self, index):
        if index in self.cache:
            return self.cache[index]
        where = f"accessors[{index}]"
        desc = self.item("accessors", index, where)
        require("sparse" not in desc, f"{where}: sparse accessors are outside this profile")
        ctype, kind = desc.get("componentType"), desc.get("type")
        require(ctype in COMPONENTS and kind in COUNTS, f"{where}: unknown component/type")
        code, width, low, high = COMPONENTS[ctype]
        count = integer(desc.get("count"), where + ".count", 1)
        view = self.item("bufferViews", desc.get("bufferView"), where + ".bufferView")
        offset = integer(desc.get("byteOffset", 0), where + ".byteOffset")
        require(offset % width == 0 and (view.get("byteOffset", 0) + offset) % width == 0,
                f"{where}: unaligned accessor")
        if kind.startswith("MAT"):
            side = int(kind[-1])
            column_stride = ((side * width + 3) // 4) * 4
            offsets = [column * column_stride + row * width for column in range(side) for row in range(side)]
            element_size = side * column_stride
        else:
            offsets = list(range(0, COUNTS[kind] * width, width))
            element_size = COUNTS[kind] * width
        stride = view.get("byteStride", element_size)
        require(stride >= element_size and stride % width == 0, f"{where}: stride smaller than element")
        require(offset + (count - 1) * stride + element_size <= view["byteLength"],
                f"{where}: accessor exceeds bufferView")
        normalized = desc.get("normalized", False)
        require(type(normalized) is bool, f"{where}: normalized must be boolean")
        require(not normalized or ctype in (5120, 5121, 5122, 5123), f"{where}: invalid normalized component")
        start = view.get("byteOffset", 0) + offset
        raw = [tuple(struct.unpack_from("<" + code, self.binary, start + row * stride + part)[0]
                     for part in offsets) for row in range(count)]
        require(all(math.isfinite(v) for row in raw for v in row), f"{where}: non-finite values")
        for key, reduction in (("min", min), ("max", max)):
            if key in desc:
                declared = numbers(desc[key], COUNTS[kind], where + "." + key)
                actual = [reduction(row[axis] for row in raw) for axis in range(COUNTS[kind])]
                require(all(math.isclose(a, b, rel_tol=2e-5, abs_tol=2e-6)
                            for a, b in zip(declared, actual)), f"{where}: declared {key} does not match data")
        values = [tuple(max(v / high, -1.0) if low < 0 else v / high for v in row) for row in raw] if normalized else raw
        self.cache[index] = (desc, values)
        return desc, values

    def pngs(self):
        details = []
        images = self.data.get("images", [])
        require(images, "images: no embedded material textures")
        for i, image in enumerate(images):
            where = f"images[{i}]"
            require(image.get("mimeType") == "image/png", f"{where}: expected embedded PNG")
            raw = self.view(image.get("bufferView"), where)
            require(raw.startswith(b"\x89PNG\r\n\x1a\n"), f"{where}: bad PNG signature")
            cursor, chunks, idat, ihdr = 8, [], bytearray(), None
            while cursor < len(raw):
                require(cursor + 12 <= len(raw), f"{where}: truncated PNG chunk")
                length = struct.unpack_from(">I", raw, cursor)[0]
                kind = raw[cursor + 4:cursor + 8]
                require(cursor + 12 + length <= len(raw), f"{where}: PNG chunk exceeds image")
                body = raw[cursor + 8:cursor + 8 + length]
                crc = struct.unpack_from(">I", raw, cursor + 8 + length)[0]
                require(zlib.crc32(kind + body) & 0xffffffff == crc, f"{where}: PNG CRC mismatch")
                require(kind in (b"IHDR", b"IDAT", b"IEND", b"gAMA", b"cHRM", b"sRGB", b"pHYs"),
                        f"{where}: unexpected PNG metadata/chunk")
                chunks.append(kind)
                if kind == b"IHDR":
                    require(ihdr is None and length == 13, f"{where}: duplicate/invalid IHDR")
                    ihdr = struct.unpack(">IIBBBBB", body)
                elif kind == b"IDAT":
                    idat.extend(body)
                elif kind == b"IEND":
                    require(length == 0 and cursor + 12 == len(raw), f"{where}: invalid PNG end")
                cursor += 12 + length
            require(chunks[0] == b"IHDR" and chunks[-1] == b"IEND" and idat,
                    f"{where}: missing/out-of-order PNG structure")
            width, height, depth, color, compression, filtering, interlace = ihdr
            require(0 < width <= 8192 and 0 < height <= 8192 and width & (width - 1) == 0
                    and height & (height - 1) == 0, f"{where}: invalid/power-of-two dimensions")
            require(depth == 8 and color in (2, 6) and compression == filtering == interlace == 0,
                    f"{where}: expected noninterlaced RGB/RGBA8 PNG")
            row_size = width * (3 if color == 2 else 4) + 1
            expected = row_size * height
            decoder = zlib.decompressobj()
            decoded = decoder.decompress(idat, expected + 1)
            require(len(decoded) == expected and decoder.eof and not decoder.unused_data
                    and not decoder.unconsumed_tail, f"{where}: invalid PNG compressed data length")
            require(all(decoded[row * row_size] <= 4 for row in range(height)), f"{where}: invalid PNG filter")
            details.append({"index": i, "width": width, "height": height, "bytes": len(raw)})
        return details

    def texture(self, info, where):
        require(isinstance(info, dict), f"{where}: required texture is missing")
        texture = self.item("textures", info.get("index"), where)
        self.item("images", texture.get("source"), where + ".source")
        if "sampler" in texture:
            self.item("samplers", texture["sampler"], where + ".sampler")
        texcoord = integer(info.get("texCoord", 0), where + ".texCoord")
        return texture["source"], texcoord

    def materials(self):
        output = {}
        require(self.data.get("materials"), "materials: none present")
        for i, material in enumerate(self.data["materials"]):
            where = f"materials[{i}]"
            pbr = material.get("pbrMetallicRoughness")
            require(isinstance(pbr, dict), f"{where}: Metallic-Roughness PBR is required")
            channels = {
                "basecolor": self.texture(pbr.get("baseColorTexture"), where + ".baseColorTexture"),
                "normal": self.texture(material.get("normalTexture"), where + ".normalTexture"),
                "metallic_roughness": self.texture(pbr.get("metallicRoughnessTexture"), where + ".metallicRoughnessTexture"),
                "occlusion": self.texture(material.get("occlusionTexture"), where + ".occlusionTexture"),
            }
            require(channels["metallic_roughness"] == channels["occlusion"], f"{where}: AO and MR must share packed ORM image/UVs")
            require(len({channels[k][0] for k in ("basecolor", "normal", "occlusion")}) == 3,
                    f"{where}: BaseColor, Normal and ORM must be distinct images")
            for field in ("metallicFactor", "roughnessFactor"):
                value = pbr.get(field, 1.0)
                require(type(value) in (float, int) and 0 <= value <= 1, f"{where}.{field}: outside 0..1")
            require(all(0 <= v <= 1 for v in numbers(pbr.get("baseColorFactor", [1, 1, 1, 1]), 4, where + ".baseColorFactor")),
                    f"{where}: BaseColor factor outside 0..1")
            require(material.get("alphaMode", "OPAQUE") in ("OPAQUE", "MASK", "BLEND"), f"{where}: invalid alpha mode")
            output[i] = channels
        return output

    def skeleton(self):
        nodes = self.data.get("nodes", [])
        require(nodes, "nodes: none present")
        parents = {}
        for i, node in enumerate(nodes):
            require(not ("matrix" in node and any(k in node for k in ("translation", "rotation", "scale"))),
                    f"nodes[{i}]: matrix and TRS cannot coexist")
            for key, count in (("matrix", 16), ("translation", 3), ("rotation", 4), ("scale", 3)):
                if key in node:
                    vec = numbers(node[key], count, f"nodes[{i}].{key}")
                    if key == "rotation":
                        require(abs(sum(v * v for v in vec) - 1) < 0.003, f"nodes[{i}]: quaternion not normalized")
            for child in node.get("children", []):
                self.item("nodes", child, f"nodes[{i}].children")
                require(child != i and child not in parents, f"nodes[{i}]: self/multiple parent")
                parents[child] = i
        for i in range(len(nodes)):
            visited, current = set(), i
            while current in parents:
                require(current not in visited, "nodes: hierarchy contains cycle")
                visited.add(current)
                current = parents[current]
        scene = self.item("scenes", self.data.get("scene", 0), "scene")
        roots = scene.get("nodes", [])
        require(roots and len(roots) == len(set(roots)), "scene: missing/duplicate root nodes")
        reached, pending = set(), list(roots)
        for root in roots:
            self.item("nodes", root, "scene.nodes")
            require(root not in parents, "scene: root has a parent")
        while pending:
            node = pending.pop()
            if node not in reached:
                reached.add(node)
                pending.extend(nodes[node].get("children", []))
        skins = self.data.get("skins", [])
        require(len(skins) == 1, "skins: expected exactly one shared humanoid skin")
        skin = skins[0]
        joints = skin.get("joints", [])
        require(joints and len(joints) == len(set(joints)), "skin: missing/duplicate joints")
        names = []
        for joint in joints:
            node = self.item("nodes", joint, "skin.joints")
            name = node.get("name")
            require(isinstance(name, str) and name.strip(), "skin: each joint requires a name")
            require(joint in reached, "skin: joint not reachable from default scene")
            names.append(name)
        require(len(names) == len(set(names)), "skin: bone names must be unique")
        if "skeleton" in skin:
            self.item("nodes", skin["skeleton"], "skin.skeleton")
            require(skin["skeleton"] in reached, "skin: skeleton not in scene")
        desc, matrices = self.accessor(skin.get("inverseBindMatrices"))
        require(desc["type"] == "MAT4" and desc["componentType"] == 5126 and len(matrices) == len(joints),
                "skin: inverse bind matrices must be one float MAT4 per joint")
        bone_set = set(joints)
        hierarchy = {}
        for joint, name in zip(joints, names):
            parent = parents.get(joint)
            while parent is not None and parent not in bone_set:
                parent = parents.get(parent)
            hierarchy[name] = nodes[parent]["name"] if parent is not None else None
        return joints, hierarchy, reached

    def meshes(self, materials, joints, reached):
        meshes = self.data.get("meshes", [])
        require(meshes, "meshes: none present")
        nodes = self.data["nodes"]
        instances = {}
        for i, node in enumerate(nodes):
            if "mesh" in node:
                self.item("meshes", node["mesh"], f"nodes[{i}].mesh")
                require(i in reached, f"nodes[{i}]: mesh outside default scene")
                require(node.get("skin") == 0, f"nodes[{i}]: mesh must use shared skin 0")
                instances.setdefault(node["mesh"], []).append(i)
        triangles, vertices, details = 0, 0, []
        for mi, mesh in enumerate(meshes):
            require(mi in instances, f"meshes[{mi}]: no active scene instance")
            require(mesh.get("primitives"), f"meshes[{mi}]: no primitives")
            for pi, primitive in enumerate(mesh["primitives"]):
                where = f"meshes[{mi}].primitives[{pi}]"
                require(primitive.get("mode", 4) == 4, f"{where}: only triangle lists supported")
                require(not primitive.get("targets"), f"{where}: morph targets outside package profile")
                material = primitive.get("material")
                require(material in materials, f"{where}: missing/invalid material")
                attrs = primitive.get("attributes", {})
                for required in ("POSITION", "NORMAL", "TEXCOORD_0", "JOINTS_0", "WEIGHTS_0"):
                    require(required in attrs, f"{where}: missing {required}")
                decoded = {key: self.accessor(value) for key, value in attrs.items()}
                pdesc, pos = decoded["POSITION"]
                count = len(pos)
                require(pdesc["type"] == "VEC3" and pdesc["componentType"] == 5126
                        and "min" in pdesc and "max" in pdesc, f"{where}: positions need float VEC3 and bounds")
                require(all(len(values) == count for _, values in decoded.values()), f"{where}: attribute counts differ")
                ndesc, normals = decoded["NORMAL"]
                require(ndesc["type"] == "VEC3" and ndesc["componentType"] == 5126, f"{where}: normals need float VEC3")
                require(all(abs(sum(v * v for v in n) - 1) < 0.01 for n in normals), f"{where}: normals not unit length")
                for channel, (_, texcoord) in materials[material].items():
                    key = f"TEXCOORD_{texcoord}"
                    require(key in decoded, f"{where}: missing UV set for {channel}")
                for key, (desc, _) in decoded.items():
                    if key.startswith("TEXCOORD_"):
                        require(desc["type"] == "VEC2" and (desc["componentType"] == 5126 or
                                desc["componentType"] in (5121, 5123) and desc.get("normalized")),
                                f"{where}: UV must be float or normalized unsigned VEC2")
                joint_sets = sorted(key for key in decoded if key.startswith("JOINTS_"))
                weight_sets = sorted(key for key in decoded if key.startswith("WEIGHTS_"))
                require([k[7:] for k in joint_sets] == [k[8:] for k in weight_sets], f"{where}: joint/weight sets disagree")
                weight_sums = [0.0] * count
                for jkey, wkey in zip(joint_sets, weight_sets):
                    jdesc, jvalues = decoded[jkey]
                    wdesc, wvalues = decoded[wkey]
                    require(jdesc["type"] == "VEC4" and jdesc["componentType"] in (5121, 5123)
                            and not jdesc.get("normalized", False), f"{where}: joints need unsigned nonnormalized VEC4")
                    require(wdesc["type"] == "VEC4" and (wdesc["componentType"] == 5126 or
                            wdesc["componentType"] in (5121, 5123) and wdesc.get("normalized")),
                            f"{where}: weights need float/normalized unsigned VEC4")
                    require(all(0 <= j < len(joints) for row in jvalues for j in row), f"{where}: joint index outside skin")
                    require(all(0 <= w <= 1 for row in wvalues for w in row), f"{where}: weight outside 0..1")
                    for vi, row in enumerate(wvalues):
                        weight_sums[vi] += sum(row)
                require(all(abs(total - 1) <= 0.002 for total in weight_sums), f"{where}: weights do not sum to one")
                idesc, indices = self.accessor(primitive.get("indices"))
                require(idesc["type"] == "SCALAR" and idesc["componentType"] in (5121, 5123, 5125)
                        and not idesc.get("normalized", False), f"{where}: unsigned scalar indices required")
                require(len(indices) % 3 == 0, f"{where}: index count not divisible by three")
                require(all(0 <= row[0] < count for row in indices), f"{where}: index outside vertex buffer")
                require(all(row[0] != COMPONENTS[idesc["componentType"]][3] for row in indices),
                        f"{where}: reserved primitive-restart index")
                tri_count = len(indices) // 3
                triangles += tri_count
                vertices += count
                details.append({"mesh": mi, "primitive": pi, "vertices": count, "triangles": tri_count,
                                "bounds_min": pdesc["min"], "bounds_max": pdesc["max"]})
        require(triangles > 0, "meshes: no triangles")
        return {"mesh_count": len(meshes), "vertices": vertices, "triangles": triangles, "primitives": details}

    def animations(self, joints):
        animations = self.data.get("animations", [])
        names = [anim.get("name") for anim in animations]
        require(len(names) == len(set(names)) and set(names) == ANIMATIONS,
                "animations: expected exactly idle, walk, melee and dash")
        output = []
        for animation in animations:
            name = animation["name"]
            samplers, channels = animation.get("samplers", []), animation.get("channels", [])
            require(samplers and channels, f"animation {name}: missing samplers/channels")
            used, targets, duration = set(), set(), 0.0
            for channel in channels:
                si = integer(channel.get("sampler"), f"animation {name}.sampler")
                require(si < len(samplers), f"animation {name}: invalid sampler reference")
                used.add(si)
                sampler = samplers[si]
                target = channel.get("target", {})
                node, path = target.get("node"), target.get("path")
                require(node in joints and path in ("translation", "rotation", "scale"),
                        f"animation {name}: target must be a joint TRS property")
                require((node, path) not in targets, f"animation {name}: duplicate target")
                targets.add((node, path))
                tdesc, times = self.accessor(sampler.get("input"))
                require(tdesc["type"] == "SCALAR" and tdesc["componentType"] == 5126
                        and "min" in tdesc and "max" in tdesc, f"animation {name}: times need float scalar and bounds")
                stamps = [row[0] for row in times]
                require(0 <= stamps[0] <= stamps[-1] <= 60
                        and all(a < b for a, b in zip(stamps, stamps[1:])),
                        f"animation {name}: key times must increase, nonnegative, duration at most 60 seconds")
                require(stamps[0] <= 1e-5, f"animation {name}: first key must start at zero")
                interpolation = sampler.get("interpolation", "LINEAR")
                require(interpolation in ("LINEAR", "STEP", "CUBICSPLINE"), f"animation {name}: invalid interpolation")
                desc, values = self.accessor(sampler.get("output"))
                multiplier = 3 if interpolation == "CUBICSPLINE" else 1
                require(desc["componentType"] == 5126 and desc["type"] == ("VEC4" if path == "rotation" else "VEC3")
                        and len(values) == len(times) * multiplier, f"animation {name}: output shape/count mismatch")
                if path == "rotation":
                    rotations = values[1::3] if multiplier == 3 else values
                    require(all(abs(sum(v * v for v in row) - 1) < 0.003 for row in rotations),
                            f"animation {name}: rotation keys are not normalized")
                duration = max(duration, stamps[-1])
            require(len(used) == len(samplers), f"animation {name}: unreferenced samplers")
            require(duration > 0, f"animation {name}: clip has zero duration")
            output.append({"name": name, "duration_seconds": duration, "channels": len(channels)})
        return output


def validate_file(path: Path):
    blob = path.read_bytes()
    data, binary = parse_glb(blob)
    asset = Asset(data, binary)
    asset.buffers()
    images = asset.pngs()
    materials = asset.materials()
    joints, hierarchy, reached = asset.skeleton()
    mesh_stats = asset.meshes(materials, joints, reached)
    animations = asset.animations(joints)
    return {"status": "passed", "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(),
            **mesh_stats, "material_count": len(materials), "embedded_pngs": images,
            "skin_count": 1, "bone_count": len(joints), "bone_hierarchy": hierarchy,
            "animations": animations}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="generated", help="GLB output directory inside this model package")
    args = parser.parse_args(argv)
    package = Path(__file__).resolve().parent
    candidate = Path(args.root)
    root = (candidate if candidate.is_absolute() else package / candidate).resolve()
    if root == package or not root.is_relative_to(package):
        parser.error("--root must be a subdirectory within this model package")
    if not root.is_dir():
        parser.error("--root directory does not exist; generate the models first")
    report_path = root / "validation.json"
    if report_path.exists() and (report_path.is_symlink() or not report_path.resolve().is_relative_to(root)):
        parser.error("validation report must remain inside --root")
    report = {"schema_version": 1, "validator": "validate.py", "status": "passed", "models": {}, "errors": [],
              "scope": "Offline embedded GLB package checks; no engine, GPU, visual or full Khronos conformance claim."}
    files = sorted(root.rglob("*.glb"))
    found_ids = {path.stem for path in files}
    if len(files) != 3 or found_ids != MODEL_IDS:
        report["errors"].append("Expected exactly iron_penitent, ash_reaver and veil_warden GLBs")
    for path in files:
        relative = path.relative_to(root).as_posix()
        try:
            require(path.resolve().is_relative_to(root), "GLB symlink escapes output root")
            require(path.parent.name == path.stem and path.parent.parent == root,
                    "GLB must be stored as <model_id>/<model_id>.glb")
            require(path.stat().st_size <= 256 * 1024 * 1024, "GLB exceeds 256 MiB package validation limit")
            result = validate_file(path)
        except (Invalid, OSError, ValueError, TypeError, KeyError, IndexError, AttributeError,
                OverflowError, RecursionError, struct.error, zlib.error) as exc:
            result = {"status": "failed", "error": str(exc) if isinstance(exc, Invalid) else
                      f"Malformed asset or file read failure ({type(exc).__name__})"}
        report["models"][relative] = result
    passed = [item for item in report["models"].values() if item["status"] == "passed"]
    if passed and any(item["bone_hierarchy"] != passed[0]["bone_hierarchy"] for item in passed[1:]):
        report["errors"].append("Model bone names or parent hierarchies differ")
    if report["errors"] or len(passed) != 3:
        report["status"] = "failed"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    for relative, item in report["models"].items():
        summary = f"{item['triangles']} triangles, {item['bone_count']} bones" if item["status"] == "passed" else item["error"]
        print(f"{relative}: {item['status']} — {summary}")
    for error in report["errors"]:
        print(error)
    print(f"GLB validation {report['status']}: {len(passed)}/{len(files)} files; report validation.json")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
