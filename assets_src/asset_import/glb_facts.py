"""Measures a glTF binary (.glb) for the asset budget check, without Blender and without numpy.

Counts, sizes and bounds come from the JSON chunk, accessor `min`/`max`, image headers and the
(small) inverse-bind-matrix accessors; no texture is decoded. The only vertex data read is
`POSITION`, for the geometric facing hint. A 2-million-triangle raw download with two 8K textures
is measured in well under a second when its positions are stored as a plain float view.

The result of [`measure_glb`] is a plain, JSON-serialisable dict of facts. It judges nothing:
budgets and conventions are applied afterwards by `check_asset.py`.
"""

from __future__ import annotations

import base64
import hashlib
import math
import re
import statistics
import sys
from array import array
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "figure_pack"))

from glb_reader import Glb, GlbError, load_glb, read_accessor  # noqa: E402

from image_headers import ImageHeaderError, read_image_header, sniff_mime_type  # noqa: E402

Mat4 = tuple[float, ...]  # 16 floats, column-major like glTF

IDENTITY: Mat4 = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)

# Bytes one vertex and one index occupy on the GPU in the engine's mesh pass (grimoire_render
# `MeshVertex`, `#[repr(C)]`, 72 bytes; `IndexFormat::Uint32`).
ENGINE_VERTEX_BYTES = 72
ENGINE_INDEX_BYTES = 4

TRACKED_ATTRIBUTES = ("NORMAL", "TANGENT", "TEXCOORD_0", "TEXCOORD_1", "COLOR_0", "JOINTS_0",
                      "WEIGHTS_0", "JOINTS_1", "WEIGHTS_1")

# Material texture slots and where glTF keeps them.
TEXTURE_SLOTS = (
    ("baseColor", ("pbrMetallicRoughness", "baseColorTexture")),
    ("metallicRoughness", ("pbrMetallicRoughness", "metallicRoughnessTexture")),
    ("normal", ("normalTexture",)),
    ("occlusion", ("occlusionTexture",)),
    ("emissive", ("emissiveTexture",)),
)


# ------------------------------------------------------------------------------------ matrices


def mat4_multiply(a: Mat4, b: Mat4) -> Mat4:
    """`a * b` for column-major 4x4 matrices (apply `b` first)."""
    out = [0.0] * 16
    for column in range(4):
        for row in range(4):
            out[column * 4 + row] = sum(a[k * 4 + row] * b[column * 4 + k] for k in range(4))
    return tuple(out)


def mat4_from_node(node: dict[str, Any]) -> Mat4:
    """The node's local transform: its `matrix`, or `T * R * S` from its TRS properties."""
    if "matrix" in node:
        matrix = tuple(float(v) for v in node["matrix"])
        if len(matrix) != 16:
            raise GlbError("node matrix does not have 16 elements")
        return matrix
    tx, ty, tz = (float(v) for v in node.get("translation", (0.0, 0.0, 0.0)))
    qx, qy, qz, qw = (float(v) for v in node.get("rotation", (0.0, 0.0, 0.0, 1.0)))
    sx, sy, sz = (float(v) for v in node.get("scale", (1.0, 1.0, 1.0)))
    xx, yy, zz = qx * qx, qy * qy, qz * qz
    xy, xz, yz = qx * qy, qx * qz, qy * qz
    wx, wy, wz = qw * qx, qw * qy, qw * qz
    return (
        (1.0 - 2.0 * (yy + zz)) * sx, 2.0 * (xy + wz) * sx, 2.0 * (xz - wy) * sx, 0.0,
        2.0 * (xy - wz) * sy, (1.0 - 2.0 * (xx + zz)) * sy, 2.0 * (yz + wx) * sy, 0.0,
        2.0 * (xz + wy) * sz, 2.0 * (yz - wx) * sz, (1.0 - 2.0 * (xx + yy)) * sz, 0.0,
        tx, ty, tz, 1.0,
    )  # fmt: skip


def mat4_transform_point(m: Mat4, p: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = p
    return (
        m[0] * x + m[4] * y + m[8] * z + m[12],
        m[1] * x + m[5] * y + m[9] * z + m[13],
        m[2] * x + m[6] * y + m[10] * z + m[14],
    )


# ---------------------------------------------------------------------------------- scene graph


def _scene_world_matrices(doc: dict[str, Any]) -> dict[int, Mat4]:
    """World matrix of every node reachable from the default scene (all roots if none)."""
    nodes = doc.get("nodes", [])
    scenes = doc.get("scenes", [])
    if scenes:
        scene_index = int(doc.get("scene", 0))
        if not 0 <= scene_index < len(scenes):
            raise GlbError(f"default scene {scene_index} out of range")
        roots = list(scenes[scene_index].get("nodes", []))
    else:
        children = {c for node in nodes for c in node.get("children", [])}
        roots = [i for i in range(len(nodes)) if i not in children]

    world: dict[int, Mat4] = {}
    stack = [(int(r), IDENTITY) for r in reversed(roots)]
    while stack:
        index, parent = stack.pop()
        if not 0 <= index < len(nodes):
            raise GlbError(f"node index {index} out of range")
        if index in world:
            raise GlbError(f"node {index} is reachable twice (cycle or shared child)")
        matrix = mat4_multiply(parent, mat4_from_node(nodes[index]))
        world[index] = matrix
        for child in reversed(nodes[index].get("children", [])):
            stack.append((int(child), matrix))
    return world


# ------------------------------------------------------------------------------------- helpers


def _accessor(doc: dict[str, Any], index: int) -> dict[str, Any]:
    accessors = doc.get("accessors", [])
    if not 0 <= index < len(accessors):
        raise GlbError(f"accessor index {index} out of range")
    return accessors[index]


def _position_bounds(glb: Glb, accessor_index: int) -> tuple[list[float], list[float]]:
    accessor = _accessor(glb.json_doc, accessor_index)
    if "min" in accessor and "max" in accessor:
        return [float(v) for v in accessor["min"]], [float(v) for v in accessor["max"]]
    # The specification requires min/max on POSITION; decode only when an exporter omitted them.
    positions = read_accessor(glb, accessor_index)
    if not positions:
        return [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
    return (
        [min(p[axis] for p in positions) for axis in range(3)],
        [max(p[axis] for p in positions) for axis in range(3)],
    )


def engine_texture_bytes_with_mips(width: int, height: int) -> int:
    """GPU bytes of an RGBA8 texture plus the full mip chain the engine generates on upload
    (grimoire_render `generate_mip_chain`: halve each side, clamp at 1, stop at 1x1)."""
    total = 0
    w, h = width, height
    while True:
        total += w * h * 4
        if w == 1 and h == 1:
            return total
        w, h = max(w // 2, 1), max(h // 2, 1)


def _image_bytes(glb: Glb, image: dict[str, Any], glb_path: Path) -> bytes:
    if "bufferView" in image:
        views = glb.json_doc.get("bufferViews", [])
        view = views[int(image["bufferView"])]
        start = int(view.get("byteOffset", 0))
        return glb.bin_chunk[start : start + int(view["byteLength"])]
    uri = image.get("uri")
    if not uri:
        raise GlbError("image has neither bufferView nor uri")
    if uri.startswith("data:"):
        _, _, payload = uri.partition(",")
        return base64.b64decode(payload)
    external = glb_path.parent / uri
    if not external.is_file():
        raise GlbError(f"external image '{uri}' not found next to the file")
    return external.read_bytes()


# Tokens that mark a joint as belonging to the character's left or right side: `hand.L`,
# `thigh_r`, `Bip01 L Thigh`, `mixamorig:LeftArm`, `socket_skillshot_l`.
_SIDE_SPLIT = re.compile(r"[\s._\-:|]+")


def joint_side(name: str) -> str | None:
    """`"left"`, `"right"` or `None` for a joint name, by its side tokens."""
    for token in _SIDE_SPLIT.split(name):
        lowered = token.lower()
        if lowered == "l" or lowered.startswith("left"):
            return "left"
        if lowered == "r" or lowered.startswith("right"):
            return "right"
    return None


def facing_from_joints(
    joints: list[tuple[str, tuple[float, float, float]]], height: float
) -> dict[str, Any]:
    """Derives the facing direction (Y up) from where left- and right-side joints sit.

    A character facing `f` with up `u` has its right side along `f x u`; with `u = +Y`, the
    vector `l` from the right-side to the left-side joint centroid gives `f = l x u =
    (-l.z, 0, l.x)`. Left joints at +X therefore mean the character faces +Z (the glTF default
    "front"), left joints at -X mean it faces -Z.
    """
    left = [p for name, p in joints if joint_side(name) == "left"]
    right = [p for name, p in joints if joint_side(name) == "right"]
    result: dict[str, Any] = {
        "method": "left/right joint names",
        "left_joints": len(left),
        "right_joints": len(right),
    }
    if not left or not right:
        result.update(axis=None, yaw_degrees=None, reason="no joints named for both sides")
        return result
    lx = sum(p[0] for p in left) / len(left) - sum(p[0] for p in right) / len(right)
    lz = sum(p[2] for p in left) / len(left) - sum(p[2] for p in right) / len(right)
    separation = math.hypot(lx, lz)
    result["side_separation_m"] = round(separation, 6)
    if separation < max(height, 1e-6) * 0.02:
        result.update(axis=None, yaw_degrees=None, reason="left and right joints do not separate")
        return result
    fx, fz = -lz, lx
    yaw = math.degrees(math.atan2(fx, fz))  # 0 = +Z, 90 = +X, 180 = -Z, -90 = -X
    axis = min(
        (("+Z", 0.0), ("+X", 90.0), ("-Z", 180.0), ("-X", -90.0)),
        key=lambda item: abs((yaw - item[1] + 180.0) % 360.0 - 180.0),
    )[0]
    result.update(axis=axis, yaw_degrees=round(yaw, 3))
    return result


def _float_vec3_values(glb: Glb, accessor_index: int) -> array:
    """POSITION values as a flat `array('f')` (x0, y0, z0, x1, ...), fast for plain float views."""
    accessor = _accessor(glb.json_doc, accessor_index)
    view_index = accessor.get("bufferView")
    if (
        view_index is not None
        and accessor.get("componentType") == 5126
        and accessor.get("type") == "VEC3"
        and "sparse" not in accessor
        and not glb.json_doc["bufferViews"][int(view_index)].get("byteStride")
        and sys.byteorder == "little"
    ):
        view = glb.json_doc["bufferViews"][int(view_index)]
        start = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
        values = array("f")
        values.frombytes(glb.bin_chunk[start : start + int(accessor["count"]) * 12])
        return values
    values = array("f")
    for point in read_accessor(glb, accessor_index):
        values.extend(point)
    return values


# Share of the height taken as the "toe" slab and the "ankle" band above it (facing_from_toes).
TOE_SLAB_SHARE = 0.03
ANKLE_BAND_SHARES = (0.10, 0.14)
TOE_MIN_OFFSET_SHARE = 0.015


def facing_from_toes(points: list[array], height: float, floor: float) -> dict[str, Any]:
    """Tells +Z from -Z facing by the shape of the feet (Y up).

    Toes reach further forward from the ankle than the heel reaches back, so the lowest few
    percent of all vertices sit, on average, in front of the ankle band. Measured on the ten
    meshes at hand (Hi3D downloads, their rigged copies, the round-4 figures) the Z offset had the
    sign of the facing every time, with a magnitude of 2.2 to 12 percent of the height.

    Only the Z axis is judged. The same average along X compares the left foot with the right one
    and follows how densely each foot happens to be tessellated (the rigged imp pilot shows an X
    offset of -18 percent of its height although it faces +Z), so a character facing +-X comes
    out "undetermined" here and needs the joint-name method or a front render. Robes that reach
    the floor, four-legged or floating creatures can also defeat this hint.
    """
    result: dict[str, Any] = {"method": "toe direction (lowest 3% vs. ankle band, Z only)"}
    if height <= 0.0:
        result.update(axis=None, reason="zero height")
        return result
    toe_top = floor + TOE_SLAB_SHARE * height
    band_low = floor + ANKLE_BAND_SHARES[0] * height
    band_high = floor + ANKLE_BAND_SHARES[1] * height
    toe_z = 0.0
    toe_count = 0
    band_z: list[float] = []
    for values in points:
        for i in range(1, len(values), 3):
            y = values[i]
            if y < toe_top:
                toe_z += values[i + 1]
                toe_count += 1
            elif band_low < y < band_high:
                band_z.append(values[i + 1])
    if toe_count == 0 or not band_z:
        result.update(axis=None, reason="no vertices in the toe slab or the ankle band")
        return result
    offset_z = toe_z / toe_count - statistics.median(band_z)
    result["toe_offset_z_share"] = round(offset_z / height, 4)
    if abs(offset_z) < TOE_MIN_OFFSET_SHARE * height:
        result.update(axis=None, reason="toe offset below 1.5% of the height")
        return result
    result["axis"] = "+Z" if offset_z > 0 else "-Z"
    return result


def combine_facing(methods: list[dict[str, Any]]) -> dict[str, Any]:
    """One facing verdict from several methods: agreement, a single answer, or a conflict."""
    axes = sorted({m["axis"] for m in methods if m.get("axis")})
    if not axes:
        verdict: dict[str, Any] = {"axis": None, "agreement": "undetermined"}
    elif len(axes) == 1:
        determined = sum(1 for m in methods if m.get("axis"))
        verdict = {"axis": axes[0], "agreement": "agree" if determined > 1 else "single method"}
    else:
        verdict = {"axis": None, "agreement": "conflict", "candidates": axes}
    verdict["methods"] = methods
    return verdict


# ------------------------------------------------------------------------------------- measure


def measure_glb(path: Path) -> dict[str, Any]:
    """Measures one `.glb`. Raises `GlbError` if the file cannot be read as glTF binary."""
    data = path.read_bytes()
    glb = load_glb(path)
    doc = glb.json_doc
    nodes = doc.get("nodes", [])
    meshes = doc.get("meshes", [])
    materials = doc.get("materials", [])
    textures = doc.get("textures", [])
    images = doc.get("images", [])

    world = _scene_world_matrices(doc)

    facts: dict[str, Any] = {
        "file": {"name": path.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()},
        "generator": doc.get("asset", {}).get("generator"),
        "extensions_used": sorted(doc.get("extensionsUsed", [])),
        "extensions_required": sorted(doc.get("extensionsRequired", [])),
    }

    # --- geometry
    triangles = 0
    vertices = 0
    primitive_count = 0
    non_triangle_modes: set[str] = set()
    sparse_accessors = 0
    primitives_without_material = 0
    max_primitive_vertices = 0
    max_primitive_indices = 0
    attribute_hits = {name: 0 for name in TRACKED_ATTRIBUTES}
    unique_buffers: set[tuple[int, int | None]] = set()
    gpu_mesh_bytes = 0
    bounds_min = [math.inf] * 3
    bounds_max = [-math.inf] * 3
    used_materials: set[int] = set()
    mesh_nodes: list[int] = []
    skin_indices: set[int] = set()
    uv_without_tangent = 0
    uv_without_tangent_with_normal_map = 0
    position_sources: list[tuple[int, Mat4 | None]] = []

    for node_index in sorted(world):
        node = nodes[node_index]
        if "mesh" not in node:
            continue
        mesh_nodes.append(node_index)
        skinned = "skin" in node
        if skinned:
            skin_indices.add(int(node["skin"]))
        mesh = meshes[int(node["mesh"])]
        for primitive in mesh.get("primitives", []):
            primitive_count += 1
            attributes = primitive.get("attributes", {})
            if "POSITION" not in attributes:
                raise GlbError(f"mesh '{mesh.get('name')}': primitive without POSITION")
            for name in TRACKED_ATTRIBUTES:
                if name in attributes:
                    attribute_hits[name] += 1
            for accessor_index in list(attributes.values()) + (
                [primitive["indices"]] if "indices" in primitive else []
            ):
                if "sparse" in _accessor(doc, int(accessor_index)):
                    sparse_accessors += 1
            mode = int(primitive.get("mode", 4))
            vertex_count = int(_accessor(doc, int(attributes["POSITION"]))["count"])
            index_count = (
                int(_accessor(doc, int(primitive["indices"]))["count"])
                if "indices" in primitive
                else vertex_count
            )
            if mode == 4:
                triangles += index_count // 3
            elif mode in (5, 6):
                triangles += max(index_count - 2, 0)
            else:
                non_triangle_modes.add(str(mode))
            vertices += vertex_count
            max_primitive_vertices = max(max_primitive_vertices, vertex_count)
            max_primitive_indices = max(max_primitive_indices, index_count)
            key = (int(attributes["POSITION"]), primitive.get("indices"))
            if key not in unique_buffers:
                unique_buffers.add(key)
                gpu_mesh_bytes += (
                    vertex_count * ENGINE_VERTEX_BYTES + index_count * ENGINE_INDEX_BYTES
                )

            if "TEXCOORD_0" in attributes and "TANGENT" not in attributes:
                uv_without_tangent += 1
            if "material" in primitive:
                used_materials.add(int(primitive["material"]))
                material = materials[int(primitive["material"])]
                if (
                    "normalTexture" in material
                    and "TEXCOORD_0" in attributes
                    and "TANGENT" not in attributes
                ):
                    uv_without_tangent_with_normal_map += 1
            else:
                primitives_without_material += 1

            node_world = None if skinned else world[node_index]
            position_sources.append((int(attributes["POSITION"]), node_world))
            p_min, p_max = _position_bounds(glb, int(attributes["POSITION"]))
            if skinned:
                # glTF ignores the transform of a skinned mesh's node; positions are bind space.
                corners = [(p_min[0], p_min[1], p_min[2]), (p_max[0], p_max[1], p_max[2])]
            else:
                corners = [
                    mat4_transform_point(world[node_index], (x, y, z))
                    for x in (p_min[0], p_max[0])
                    for y in (p_min[1], p_max[1])
                    for z in (p_min[2], p_max[2])
                ]
            for corner in corners:
                for axis in range(3):
                    bounds_min[axis] = min(bounds_min[axis], corner[axis])
                    bounds_max[axis] = max(bounds_max[axis], corner[axis])

    def coverage(name: str) -> str:
        hits = attribute_hits[name]
        return "none" if hits == 0 else ("all" if hits == primitive_count else "some")

    facts["geometry"] = {
        "mesh_nodes": len(mesh_nodes),
        "primitives": primitive_count,
        "triangles": triangles,
        "vertices": vertices,
        "max_primitive_vertices": max_primitive_vertices,
        "max_primitive_indices": max_primitive_indices,
        "non_triangle_modes": sorted(non_triangle_modes),
        "sparse_accessors": sparse_accessors,
        "primitives_without_material": primitives_without_material,
        "primitives_with_uv_but_no_tangent": uv_without_tangent,
        "primitives_with_uv_and_normal_map_but_no_tangent": uv_without_tangent_with_normal_map,
        "attributes": {name: coverage(name) for name in TRACKED_ATTRIBUTES},
        "gpu_mesh_bytes": gpu_mesh_bytes,
    }

    if primitive_count:
        height = bounds_max[1] - bounds_min[1]
        facts["bounds"] = {
            "space": "bind pose" if skin_indices else "world",
            "min": [round(v, 6) for v in bounds_min],
            "max": [round(v, 6) for v in bounds_max],
            "height_y_m": round(height, 6),
            "width_x_m": round(bounds_max[0] - bounds_min[0], 6),
            "depth_z_m": round(bounds_max[2] - bounds_min[2], 6),
            "foot_level_y_m": round(bounds_min[1], 6),
            "center_x_m": round((bounds_min[0] + bounds_max[0]) / 2.0, 6),
            "center_z_m": round((bounds_min[2] + bounds_max[2]) / 2.0, 6),
        }
    else:
        height = 0.0
        facts["bounds"] = None

    # --- geometric facing hint, from the vertex data itself
    point_arrays: list[array] = []
    for accessor_index, node_world in position_sources:
        values = _float_vec3_values(glb, accessor_index)
        if node_world is not None and node_world != IDENTITY:
            moved = array("f")
            for i in range(0, len(values), 3):
                point = (values[i], values[i + 1], values[i + 2])
                moved.extend(mat4_transform_point(node_world, point))
            values = moved
        point_arrays.append(values)
    toe_facing = facing_from_toes(point_arrays, height, bounds_min[1] if primitive_count else 0.0)

    # --- skin
    skins = doc.get("skins", [])
    skin_facts: list[dict[str, Any]] = []
    joint_facings: list[dict[str, Any]] = []
    for skin_index in sorted(skin_indices):
        skin = skins[skin_index]
        joint_nodes = [int(j) for j in skin.get("joints", [])]
        if "inverseBindMatrices" in skin:
            inverse_binds = [tuple(m) for m in read_accessor(glb, int(skin["inverseBindMatrices"]))]
        else:
            inverse_binds = [IDENTITY] * len(joint_nodes)
        max_error = 0.0
        joint_positions: list[tuple[str, tuple[float, float, float]]] = []
        for joint_node, inverse_bind in zip(joint_nodes, inverse_binds):
            joint_world = world.get(joint_node)
            if joint_world is None:
                raise GlbError(f"skin {skin_index}: joint node {joint_node} is not in the scene")
            product = mat4_multiply(joint_world, inverse_bind)
            max_error = max(max_error, max(abs(a - b) for a, b in zip(product, IDENTITY)))
            name = nodes[joint_node].get("name", f"node_{joint_node}")
            joint_positions.append((name, (joint_world[12], joint_world[13], joint_world[14])))
        skin_facts.append(
            {
                "skin": skin_index,
                "name": skin.get("name"),
                "joints": len(joint_nodes),
                "joint_names": [name for name, _ in joint_positions],
                "rest_pose_vs_bind_pose_max_error": round(max_error, 9),
            }
        )
        joint_facings.append(facing_from_joints(joint_positions, height))
    facts["skins"] = skin_facts
    facts["facing"] = combine_facing([toe_facing] + joint_facings)

    # --- materials and textures
    image_slots: dict[int, set[str]] = {}
    material_facts = []
    for material_index in sorted(used_materials):
        material = materials[material_index]
        slots = []
        for slot, location in TEXTURE_SLOTS:
            info: Any = material
            for key in location:
                info = info.get(key, {}) if isinstance(info, dict) else {}
            if not info:
                continue
            texture = textures[int(info["index"])]
            source = texture.get("source")
            for extension in texture.get("extensions", {}).values():
                source = extension.get("source", source)
            slots.append(slot)
            if source is not None:
                image_slots.setdefault(int(source), set()).add(slot)
        material_facts.append(
            {
                "material": material_index,
                "name": material.get("name"),
                "texture_slots": slots,
                "alpha_mode": material.get("alphaMode", "OPAQUE"),
                "double_sided": bool(material.get("doubleSided", False)),
            }
        )
    facts["materials"] = material_facts

    texture_facts = []
    for image_index in sorted(image_slots):
        image = images[image_index]
        entry: dict[str, Any] = {
            "image": image_index,
            "name": image.get("name"),
            "declared_mime_type": image.get("mimeType"),
            "slots": sorted(image_slots[image_index]),
        }
        try:
            payload = _image_bytes(glb, image, path)
            entry["encoded_bytes"] = len(payload)
            entry["sniffed_mime_type"] = sniff_mime_type(payload)
            header = read_image_header(payload)
        except (ImageHeaderError, GlbError, ValueError) as error:
            entry["error"] = str(error)
        else:
            entry.update(
                width=header.width,
                height=header.height,
                channels=header.channels,
                bit_depth=header.bit_depth,
                progressive=header.progressive,
                pixels=header.width * header.height,
                power_of_two=_is_power_of_two(header.width) and _is_power_of_two(header.height),
                pack_raw_bytes=header.width * header.height * 4,
                gpu_bytes_rgba8_with_mips=engine_texture_bytes_with_mips(
                    header.width, header.height
                ),
            )
        texture_facts.append(entry)
    facts["textures"] = texture_facts
    facts["unused_images"] = sorted(set(range(len(images))) - set(image_slots))

    # --- animations
    animation_facts = []
    for animation in doc.get("animations", []):
        duration = 0.0
        for sampler in animation.get("samplers", []):
            accessor = _accessor(doc, int(sampler["input"]))
            if "max" in accessor:
                duration = max(duration, float(accessor["max"][0]))
        animation_facts.append(
            {
                "name": animation.get("name"),
                "channels": len(animation.get("channels", [])),
                "duration_s": round(duration, 6),
            }
        )
    facts["animations"] = animation_facts
    return facts


def _is_power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0
