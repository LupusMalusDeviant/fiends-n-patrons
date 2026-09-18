#!/usr/bin/env python3
"""Stage 1 of the figure-pack converter (figuren-in-engine-spec.md, "Strang A").

Reads `<name><suffix>` (default `_r3b_low.glb`) for each figure, plus any `--figure NAME=PATH`
(glTF 2 binary; no `pygltflib`), decodes every accessor and embedded PNG by hand, and writes one
payload file per pack entry plus an `index.json` naming path/kind/kind_version/file for each.
PNG figures that need no texture reduction still need nothing but the standard library; JPEG
textures use Pillow and `--max-texture-size` uses numpy (`textures.py`).
Stage 2 (`crates/fnp_content/src/bin/figure_pack_builder.rs`) reads that `index.json` and hands
the payload bytes, unchanged, to the engine's own `grimoire_assets::PackWriter` -- this script
never builds the pack container itself.

## Axis correction: +90 degrees about X, applied once, at the skeleton root

glTF is Y-up, right-handed, camera looks down -Z ("forward" is -Z). The engine is Z-up,
X-right, Y-away-from-viewer (`grimoire_render`'s `PointLight` doc comment), right-handed. Mapping
glTF's basis onto the engine's, with X (the shared "right" axis) as the rotation axis:

    engine +Z (up)      <- gltf +Y (up)
    engine +Y (forward)  <- gltf -Z (forward)   =>  engine -Y <- gltf +Z
    engine +X (right)   <- gltf +X (right)          (rotation axis, unchanged)

As a matrix this is `[[1,0,0],[0,0,-1],[0,1,0]]`, i.e. `(x, y, z) -> (x, -z, y)`. Using the
standard right-hand-rule convention for `Rx(theta)` (`[[1,0,0],[0,cos,-sin],[0,sin,cos]]`), that
matrix has `sin(theta)=1, cos(theta)=0`, i.e. `theta = +90 degrees`, not the spec's literal
"-90 degrees um X". Concretely, for `soul`'s main body mesh (`soul_low`, accessor min/max
`y in [0.0173, 1.7810]` in the raw Y-up data): `+90 deg` gives `z in [0.017, 1.781]` (feet at
z~0, head at z~1.78, matching the spec's own acceptance criterion); `-90 deg`
(`(x, y, z) -> (x, z, -y)`) gives `z in [-1.781, -0.017]` -- upside down and underground, exactly
the failure mode the spec itself warns about. This is very likely the spec author thinking in
terms of rotating the *coordinate frame* (passive convention) rather than the vertex data
(active convention) -- the two are negatives of each other for the same nominal angle. This
script implements the active `(x, y, z) -> (x, -z, y)` mapping (verified against the numbers
above, and again per-figure at the end of a real run) and documents the concrete matrix here so
Strang B does not also apply a correction "for safety" (contract: "einmal ... nicht doppelt").

The rotation is applied in exactly one place: the local rest-pose transform of each skeleton's
root joint (see `skeleton.correct_root_joint_transform`), never to mesh vertex data. That is
mathematically sufficient because a skinned vertex's rest-pose world position already equals its
raw local position exactly (`jointGlobalTransform_bindpose_j (x) invBindMatrix_j == identity` by
construction, for every joint), so rotating the vertex data would double the effect once the
skeleton root also carries it. `_forward_kinematics_check` proves this equivalence numerically
for a sample of real vertices on every run, comparing the full skin formula (joint chain x
inverse bind, exactly as the engine will evaluate it at runtime) against a direct
`apply_axis_correction_vec3` of the raw vertex -- if a hierarchy or remap bug ever broke that
equivalence, this check fails the run instead of shipping a silently-wrong pack.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from clips import (
    CLIP_FORMAT_VERSION,
    FNP_CLIP,
    ClipError,
    encode_clip,
    markers_from_events,
    sample_clip,
    skeleton_fingerprint,
)
from glb_reader import Glb, GlbError, load_glb, primitive_attribute_counts_agree, read_accessor
from pack_payloads import (
    FNP_FIGURE,
    FNP_MATERIAL,
    FNP_MESH,
    FNP_SKELETON,
    FNP_TEXTURE_RAW,
    KIND_VERSION,
    MESH_KIND_VERSION,
    NO_TANGENT,
    PayloadError,
    Vertex,
    encode_figure,
    encode_material,
    encode_mesh,
    encode_skeleton,
    encode_texture_raw,
)
from png_decode import PngError
from rig_math import (
    apply_axis_correction_vec3,
    compose_trs,
    mat4_apply_point,
    mat4_apply_vector,
    point_transform,
    rotate_tangent,
    vector_transform,
)
from skeleton import SkeletonError, build_skeleton, remap_joint_indices
from stable_id import asset_id_for_path
from textures import TextureError, TexturePlan, decode_texture, plan_texture

FIGURE_NAMES = ("soul", "imp", "brute")
GLB_SUFFIX = "_r3b_low.glb"


def glb_path_for(source: Path, name: str, suffix: str = GLB_SUFFIX) -> Path:
    """Path of one figure's source file: `<source>/<name><suffix>`.

    The suffix names the asset round (`_r3b_low.glb`, `_r3c_low.glb`, ...), so a new round of
    figures needs a command-line argument, not a code change.
    """
    return source / f"{name}{suffix}"
# The rate the figures are authored at; every clip is stored at the rate it was authored at
# (format document `figure-clip.md` §3), never resampled to the simulation's tick rate.
DEFAULT_CLIP_RATE_HZ = 24.0

FK_CHECK_SAMPLE_PER_PART = 8
FK_CHECK_TOLERANCE = 5.0e-3  # generous: float32 source data round-tripped through float64 math


class BuildError(RuntimeError):
    """Any failure that must abort the whole run before anything is written to disk."""


@dataclass
class PackEntry:
    path: str
    kind: int
    kind_version: int
    data: bytes


@dataclass
class FigureReport:
    name: str
    triangle_count: int = 0
    part_count: int = 0
    material_count: int = 0
    texture_count: int = 0
    joint_count: int = 0
    bounds_min: tuple[float, float, float] = (0.0, 0.0, 0.0)
    bounds_max: tuple[float, float, float] = (0.0, 0.0, 0.0)
    fk_samples_checked: int = 0
    fk_max_error: float = 0.0
    fk_tangent_checked: int = 0
    fk_tangent_max_error: float = 0.0
    tangent_primitive_count: int = 0
    no_tangent_primitive_count: int = 0
    textures: list[str] = field(default_factory=list)
    clips: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _alpha_mode_of(material: dict[str, Any]) -> tuple[int, float]:
    mode = material.get("alphaMode", "OPAQUE")
    cutoff = float(material.get("alphaCutoff", 0.5))
    try:
        return {"OPAQUE": 0, "MASK": 1, "BLEND": 2}[mode], cutoff
    except KeyError as error:
        raise BuildError(f"unknown alphaMode {mode!r}") from error


def _material_factors(material: dict[str, Any]) -> dict[str, Any]:
    pbr = material.get("pbrMetallicRoughness", {})
    base_color = tuple(pbr.get("baseColorFactor", (1.0, 1.0, 1.0, 1.0)))
    metallic = float(pbr.get("metallicFactor", 1.0))
    roughness = float(pbr.get("roughnessFactor", 1.0))
    emissive = list(material.get("emissiveFactor", (0.0, 0.0, 0.0)))
    # KHR_materials_emissive_strength: not mentioned in figuren-in-engine-spec.md's MATERIAL
    # layout (which has no separate strength field), but soul_orb/imp_eye/brute_eye all use it to
    # get an HDR glow out of an emissiveFactor that peaks at 1.0. Folding the strength into the
    # stored factor is the only way to keep that intent in a plain f32[3]; flagged in the PR
    # description as a spec gap this converter fills rather than silently drops.
    strength = (
        material.get("extensions", {})
        .get("KHR_materials_emissive_strength", {})
        .get("emissiveStrength", 1.0)
    )
    emissive = tuple(component * strength for component in emissive)
    alpha_mode, alpha_cutoff = _alpha_mode_of(material)
    return {
        "base_color": base_color,
        "metallic": metallic,
        "roughness": roughness,
        "emissive": emissive,
        "alpha_mode": alpha_mode,
        "alpha_cutoff": alpha_cutoff,
    }


@dataclass
class TextureUse:
    image_index: int
    color_space: int  # 0 sRGB, 1 linear
    slot: str  # for error messages only


# Material slots the converter packs (`FNP_MATERIAL`): glTF location -> engine colour space.
_TEXTURE_SLOTS = (
    (("pbrMetallicRoughness", "baseColorTexture"), 0),
    (("normalTexture",), 1),
    (("pbrMetallicRoughness", "metallicRoughnessTexture"), 1),
)


def material_image_uses(glb: Glb) -> dict[int, int]:
    """Image index -> colour space (0 sRGB, 1 linear) for every image a material slot uses."""
    doc = glb.json_doc
    uses: dict[int, int] = {}
    for material in doc.get("materials", []):
        for location, color_space in _TEXTURE_SLOTS:
            ref: Any = material
            for key in location:
                ref = ref.get(key) if isinstance(ref, dict) else None
            if ref is None:
                continue
            textures = doc.get("textures", [])
            if not (0 <= ref["index"] < len(textures)):
                raise BuildError(f"texture index {ref['index']} out of range")
            uses.setdefault(textures[ref["index"]]["source"], color_space)
    return uses


def image_bytes(glb: Glb, image_index: int, *, figure: str) -> tuple[bytes, str]:
    """Encoded bytes and a label (`figure/image name`) of one embedded image."""
    image = glb.json_doc.get("images", [])[image_index]
    if "bufferView" not in image:
        raise BuildError(
            f"{figure}: image {image_index} is not embedded (no bufferView) -- "
            "external image URIs are not supported"
        )
    view = glb.json_doc["bufferViews"][image["bufferView"]]
    start = view.get("byteOffset", 0)
    label = f"{figure}/{image.get('name', f'image_{image_index}')}"
    return glb.bin_chunk[start : start + view["byteLength"]], label


def plan_figure_textures(name: str, glb: Glb, max_size: int | None) -> dict[int, TexturePlan]:
    """Reads every used texture's header and checks it against the engine, before any decoding.

    Collects every problem of the figure into one `BuildError`, so a run over several oversized
    8K textures names all of them at once.
    """
    plans: dict[int, TexturePlan] = {}
    problems: list[str] = []
    for image_index in sorted(material_image_uses(glb)):
        data, label = image_bytes(glb, image_index, figure=name)
        try:
            plans[image_index] = plan_texture(data, label=label, max_size=max_size)
        except TextureError as error:
            problems.append(str(error))
    if problems:
        raise BuildError("\n".join(problems))
    return plans


class FigureBuilder:
    """Accumulates the dedup tables and pack entries for one figure while walking its glTF."""

    def __init__(self, name: str, glb: Glb, texture_plans: dict[int, TexturePlan]) -> None:
        self.name = name
        self.glb = glb
        self.texture_plans = texture_plans
        self.entries: list[PackEntry] = []
        self.report = FigureReport(name=name)
        self._material_dedup: dict[int, int] = {}  # gltf material index -> local material id
        self._texture_dedup: dict[int, TextureUse] = {}  # gltf image index -> local texture id
        self._texture_order: list[int] = []  # image indices in first-use order

    def path(self, *segments: str) -> str:
        return "/".join(("figures", self.name, *segments))

    def asset_id(self, *segments: str) -> int:
        return asset_id_for_path(self.path(*segments))

    def _texture_local_id(self, image_index: int, *, color_space: int, slot: str) -> int:
        existing = self._texture_dedup.get(image_index)
        if existing is not None:
            if existing.color_space != color_space:
                raise BuildError(
                    f"{self.name}: image {image_index} is used both as {existing.slot} "
                    f"(color_space {existing.color_space}) and as {slot} (color_space "
                    f"{color_space}) -- ambiguous color space for one image"
                )
            return self._texture_order.index(image_index)
        local_id = len(self._texture_order)
        self._texture_dedup[image_index] = TextureUse(image_index, color_space, slot)
        self._texture_order.append(image_index)
        return local_id

    def _texture_ref(self, texture_ref: dict[str, Any] | None, *, color_space: int, slot: str) -> int | None:
        if texture_ref is None:
            return None
        textures = self.glb.json_doc.get("textures", [])
        texture_index = texture_ref["index"]
        if not (0 <= texture_index < len(textures)):
            raise BuildError(f"{self.name}: texture index {texture_index} out of range")
        image_index = textures[texture_index]["source"]
        return self._texture_local_id(image_index, color_space=color_space, slot=slot)

    def material_local_id(self, gltf_material_index: int) -> int:
        existing = self._material_dedup.get(gltf_material_index)
        if existing is not None:
            return existing
        local_id = len(self._material_dedup)
        self._material_dedup[gltf_material_index] = local_id

        material = self.glb.json_doc["materials"][gltf_material_index]
        factors = _material_factors(material)
        pbr = material.get("pbrMetallicRoughness", {})
        base_color_tex = self._texture_ref(
            pbr.get("baseColorTexture"), color_space=0, slot="base_color"
        )
        normal_tex = self._texture_ref(
            material.get("normalTexture"), color_space=1, slot="normal"
        )
        orm_tex = self._texture_ref(
            pbr.get("metallicRoughnessTexture"), color_space=1, slot="occlusion_roughness_metallic"
        )
        payload = encode_material(
            base_color=factors["base_color"],
            metallic=factors["metallic"],
            roughness=factors["roughness"],
            emissive=factors["emissive"],
            alpha_mode=factors["alpha_mode"],
            alpha_cutoff=factors["alpha_cutoff"],
            base_color_texture=base_color_tex,
            normal_texture=normal_tex,
            orm_texture=orm_tex,
            label=f"{self.name}/material/{local_id}",
        )
        self.entries.append(
            PackEntry(self.path("material", str(local_id)), FNP_MATERIAL, KIND_VERSION, payload)
        )
        return local_id

    def finish_textures(self) -> None:
        for local_id, image_index in enumerate(self._texture_order):
            data, label = image_bytes(self.glb, image_index, figure=self.name)
            plan = self.texture_plans.get(image_index)
            if plan is None:  # pragma: no cover - every material slot was planned up front
                raise BuildError(f"{label}: texture was not planned")
            color_space = self._texture_dedup[image_index].color_space
            try:
                rgba = decode_texture(data, plan, srgb=color_space == 0, label=label)
            except TextureError as error:
                raise BuildError(str(error)) from error
            payload = encode_texture_raw(
                width=plan.out_width,
                height=plan.out_height,
                color_space=color_space,
                rgba=rgba,
                label=label,
            )
            self.entries.append(
                PackEntry(
                    self.path("texture", str(local_id)), FNP_TEXTURE_RAW, KIND_VERSION, payload
                )
            )
            note = f"{plan.mime_type} {plan.width}x{plan.height}"
            if plan.factor > 1:
                note += f" -> {plan.out_width}x{plan.out_height}"
            self.report.textures.append(f"{label}: {note}")
        self.report.texture_count = len(self._texture_order)

    def texture_ids(self) -> list[int]:
        return [self.asset_id("texture", str(i)) for i in range(len(self._texture_order))]

    def material_count(self) -> int:
        return len(self._material_dedup)


def _primitive_vertices(
    glb: Glb, primitive: dict[str, Any], *, label: str
) -> tuple[list[Any], list[Any], list[Any], list[Any], list[Any], list[int], int]:
    attributes = primitive["attributes"]
    positions = read_accessor(glb, attributes["POSITION"])
    normals = read_accessor(glb, attributes["NORMAL"])
    vertex_count = len(positions)
    if len(normals) != vertex_count:
        raise BuildError(f"{label}: POSITION/NORMAL count mismatch")

    if "TEXCOORD_0" in attributes:
        uvs = read_accessor(glb, attributes["TEXCOORD_0"])
        if len(uvs) != vertex_count:
            raise BuildError(f"{label}: TEXCOORD_0 count mismatch")
    else:
        # Real-world quirk in the shipped fixtures: soul_staff and imp_teeth reference a textured
        # material (glTF texture refs carry `texCoord: -1`, a non-standard Blender-exporter
        # marker for "no UV set") but carry no TEXCOORD_0 attribute at all. Filling (0, 0) keeps
        # the vertex format uniform; flagged in the PR description as a data quirk, not something
        # figuren-in-engine-spec.md anticipates.
        uvs = [(0.0, 0.0)] * vertex_count

    if "JOINTS_0" not in attributes or "WEIGHTS_0" not in attributes:
        raise BuildError(f"{label}: primitive has no JOINTS_0/WEIGHTS_0 (unskinned mesh)")
    joints_raw = read_accessor(glb, attributes["JOINTS_0"])
    weights = read_accessor(glb, attributes["WEIGHTS_0"])
    if len(joints_raw) != vertex_count or len(weights) != vertex_count:
        raise BuildError(f"{label}: JOINTS_0/WEIGHTS_0 count mismatch")

    if "indices" not in primitive:
        raise BuildError(f"{label}: non-indexed primitives are not supported")
    indices_accessor = primitive["indices"]
    source_index_count = glb.json_doc["accessors"][indices_accessor]["count"]
    indices = [int(i) for i in read_accessor(glb, indices_accessor)]
    if len(indices) != source_index_count:
        raise BuildError(
            f"{label}: read {len(indices)} indices, source accessor declares "
            f"{source_index_count} (triangle count against the source failed)"
        )

    return positions, normals, uvs, joints_raw, weights, indices, vertex_count


def _primitive_tangents(
    glb: Glb,
    primitive: dict[str, Any],
    *,
    vertex_count: int,
    has_uv: bool,
    material_has_normal_map: bool,
    label: str,
) -> list[tuple[float, float, float, float]]:
    """Reads (or falls back for) one primitive's raw, unrotated `TANGENT`.

    texturqualitaet-spec.md, A2, names exactly one fallback and exactly one error, "kein dritter
    Fall": a primitive without `TEXCOORD_0` (iris, staff, teeth) gets [`NO_TANGENT`] for every
    vertex, unconditionally; a primitive *with* `TEXCOORD_0` whose material uses a normal map but
    carries no `TANGENT` aborts the run. The remaining combination -- `TEXCOORD_0` present, no
    normal map on the material, still no `TANGENT` -- is not one of the spec's two named cases; it
    also does not occur in any of the shipped soul/imp/brute fixtures (every UV'd primitive in the
    `_r3d` exports carries TANGENT, verified against all 42 primitives across both LOD levels), so
    rather than silently inventing a third fallback this aborts too (contract: "nicht still etwas
    anderes bauen") -- flagged in the PR description as a spec gap, not a deviation.
    """
    attributes = primitive["attributes"]
    if not has_uv:
        return [NO_TANGENT] * vertex_count
    if "TANGENT" in attributes:
        tangents = read_accessor(glb, attributes["TANGENT"])
        if len(tangents) != vertex_count:
            raise BuildError(f"{label}: TANGENT count mismatch")
        return [tuple(t) for t in tangents]
    if material_has_normal_map:
        raise BuildError(
            f"{label}: primitive has TEXCOORD_0 and its material uses a normal map, but no "
            "TANGENT attribute -- re-export from Blender with export_tangents=True (spec: no "
            "fallback for this case)"
        )
    raise BuildError(
        f"{label}: primitive has TEXCOORD_0 but no TANGENT, and its material has no normal map "
        "-- not one of the spec's two defined cases (fallback is scoped to 'no TEXCOORD_0'); "
        "aborting instead of guessing a third fallback"
    )


def _forward_kinematics_check(
    joints: list,
    positions: list,
    tangents: list,
    joints_0,
    weights,
    *,
    label: str,
    report: FigureReport,
) -> None:
    """Confirms `apply_axis_correction_vec3(raw_vertex) == full skin formula` for a sample.

    See the module docstring: this is the numeric proof that the axis correction living solely in
    the skeleton root is equivalent to rotating the mesh directly, for real vertices of a real
    rig -- not just for the algebra. Extended (texturqualitaet-spec.md, A2) to prove the same
    equivalence for `TANGENT.xyz`, using `rig_math.vector_transform` (rotation/scale only, no
    translation) in place of `point_transform`: a vertex with the [`NO_TANGENT`] sentinel is
    skipped, since rotating the zero vector is trivially still zero either way.
    """
    global_trs = [None] * len(joints)
    for index, joint in enumerate(joints):
        local = (joint.translation, joint.rotation, joint.scale)
        if joint.parent == -1:
            global_trs[index] = local
        else:
            global_trs[index] = compose_trs(global_trs[joint.parent], local)

    sample = min(FK_CHECK_SAMPLE_PER_PART, len(positions))
    for i in range(sample):
        position = positions[i]
        tangent = tangents[i]
        has_tangent = tangent != NO_TANGENT
        tangent_xyz = tangent[:3]
        quad_joints = joints_0[i]
        quad_weights = weights[i]
        skinned = (0.0, 0.0, 0.0)
        tangent_skinned = (0.0, 0.0, 0.0)
        for joint_index, weight in zip(quad_joints, quad_weights):
            if weight == 0.0:
                continue
            bind_local = mat4_apply_point(joints[joint_index].inverse_bind, position)
            world = point_transform(global_trs[joint_index], bind_local)
            skinned = tuple(s + weight * w for s, w in zip(skinned, world))
            if has_tangent:
                # Same two-step formula as position: undo this joint's bind-pose orientation
                # (inverse_bind's linear part) first, then apply its current global TRS's
                # rotation/scale -- skipping the inverse-bind step would only skin correctly by
                # accident (e.g. when every joint's bind rotation happens to be identity).
                bind_local_tangent = mat4_apply_vector(joints[joint_index].inverse_bind, tangent_xyz)
                tangent_world = vector_transform(global_trs[joint_index], bind_local_tangent)
                tangent_skinned = tuple(
                    s + weight * w for s, w in zip(tangent_skinned, tangent_world)
                )
        expected = apply_axis_correction_vec3(position)
        error = max(abs(a - b) for a, b in zip(skinned, expected))
        report.fk_max_error = max(report.fk_max_error, error)
        report.fk_samples_checked += 1
        if error > FK_CHECK_TOLERANCE:
            raise BuildError(
                f"{label}: forward-kinematics self-check failed for vertex {i}: skinned "
                f"{skinned} vs. directly-rotated {expected} (error {error})"
            )
        if has_tangent:
            expected_tangent = rotate_tangent(tangent)[:3]
            tangent_error = max(abs(a - b) for a, b in zip(tangent_skinned, expected_tangent))
            report.fk_tangent_max_error = max(report.fk_tangent_max_error, tangent_error)
            report.fk_tangent_checked += 1
            if tangent_error > FK_CHECK_TOLERANCE:
                raise BuildError(
                    f"{label}: forward-kinematics tangent self-check failed for vertex {i}: "
                    f"skinned {tangent_skinned} vs. directly-rotated {expected_tangent} "
                    f"(error {tangent_error})"
                )


def build_figure(
    name: str,
    glb_path: Path,
    max_texture_size: int | None = None,
    clip_request: ClipRequest | None = None,
) -> tuple[list[PackEntry], FigureReport]:
    try:
        glb = load_glb(glb_path)
    except GlbError as error:
        raise BuildError(str(error)) from error
    texture_plans = plan_figure_textures(name, glb, max_texture_size)

    skin_indices = {
        node["skin"] for node in glb.json_doc.get("nodes", []) if "mesh" in node and "skin" in node
    }
    if len(skin_indices) != 1:
        raise BuildError(f"{name}: expected exactly one skin, found {sorted(skin_indices)}")
    (skin_index,) = skin_indices

    try:
        skeleton_result = build_skeleton(glb, skin_index, label=name)
    except SkeletonError as error:
        raise BuildError(str(error)) from error
    joint_count = len(skeleton_result.joints)

    builder = FigureBuilder(name, glb, texture_plans)
    parts: list[tuple[int, int]] = []
    bounds_min = [float("inf")] * 3
    bounds_max = [float("-inf")] * 3
    part_index = 0

    for node in glb.json_doc.get("nodes", []):
        if "mesh" not in node or node.get("skin") != skin_index:
            continue
        mesh = glb.json_doc["meshes"][node["mesh"]]
        for primitive in mesh["primitives"]:
            label = f"{name}/mesh/{part_index}"
            if "material" not in primitive:
                raise BuildError(f"{label}: primitive has no material (no default material support)")
            source_material = glb.json_doc["materials"][primitive["material"]]
            material_has_normal_map = "normalTexture" in source_material
            material_uses_textures = "pbrMetallicRoughness" in source_material and any(
                key in source_material.get("pbrMetallicRoughness", {})
                for key in ("baseColorTexture", "metallicRoughnessTexture")
            ) or material_has_normal_map

            (
                positions,
                normals,
                uvs,
                joints_raw,
                weights,
                indices,
                vertex_count,
            ) = _primitive_vertices(glb, primitive, label=label)
            if not primitive_attribute_counts_agree(
                [len(positions), len(normals), len(uvs), len(joints_raw), len(weights)]
            ):
                raise BuildError(f"{label}: attribute accessors disagree on vertex count")

            has_uv = "TEXCOORD_0" in primitive["attributes"]
            tangents = _primitive_tangents(
                glb,
                primitive,
                vertex_count=vertex_count,
                has_uv=has_uv,
                material_has_normal_map=material_has_normal_map,
                label=label,
            )
            if has_uv:
                builder.report.tangent_primitive_count += 1
            else:
                builder.report.no_tangent_primitive_count += 1

            joints_remapped = remap_joint_indices(
                [tuple(int(v) for v in q) for q in joints_raw],
                skeleton_result.original_index_to_new,
                joint_count=joint_count,
                label=label,
            )

            try:
                _forward_kinematics_check(
                    skeleton_result.joints,
                    positions,
                    tangents,
                    joints_remapped,
                    weights,
                    label=label,
                    report=builder.report,
                )
            except (IndexError, ValueError) as error:
                raise BuildError(f"{label}: forward-kinematics self-check errored: {error}") from error

            vertices = [
                Vertex(
                    position=positions[i],
                    normal=normals[i],
                    uv=uvs[i],
                    joints=joints_remapped[i],
                    weights=weights[i],
                    tangent=tangents[i],
                )
                for i in range(vertex_count)
            ]
            try:
                mesh_payload = encode_mesh(vertices, indices, joint_count=joint_count, label=label)
            except PayloadError as error:
                raise BuildError(str(error)) from error
            builder.entries.append(
                PackEntry(builder.path("mesh", str(part_index)), FNP_MESH, MESH_KIND_VERSION, mesh_payload)
            )

            for position in positions:
                corrected = apply_axis_correction_vec3(position)
                for axis in range(3):
                    bounds_min[axis] = min(bounds_min[axis], corrected[axis])
                    bounds_max[axis] = max(bounds_max[axis], corrected[axis])

            if not has_uv and material_uses_textures:
                builder.report.notes.append(
                    f"{label}: material references textures but the primitive has no "
                    "TEXCOORD_0 (texCoord: -1 in source) -- UV filled with (0, 0)"
                )
            material_local_id = builder.material_local_id(primitive["material"])
            parts.append((builder.asset_id("mesh", str(part_index)), builder.asset_id("material", str(material_local_id))))
            builder.report.triangle_count += len(indices) // 3
            part_index += 1

    if not parts:
        raise BuildError(f"{name}: no skinned mesh primitives found")

    builder.finish_textures()

    try:
        skeleton_payload = encode_skeleton(skeleton_result.joints, label=f"{name}/skeleton")
    except PayloadError as error:
        raise BuildError(str(error)) from error
    builder.entries.append(
        PackEntry(builder.path("skeleton"), FNP_SKELETON, KIND_VERSION, skeleton_payload)
    )

    if clip_request is not None:
        skin_nodes = glb.json_doc["skins"][skin_index]["joints"]
        fingerprint = skeleton_fingerprint(skeleton_result.joints)
        for clip_name in clip_request.clips:
            try:
                sampled = sample_clip(
                    glb,
                    skeleton_result,
                    skin_nodes,
                    clip_name,
                    frame_rate=clip_request.frame_rate_hz,
                )
                markers = markers_from_events(
                    clip_request.events.get(clip_name, {}), sampled.frame_count, clip=clip_name
                )
                payload = encode_clip(
                    sampled, fingerprint, markers, label=f"{name}/clip/{clip_name}"
                )
            except ClipError as error:
                raise BuildError(f"{name}: {error}") from error
            builder.entries.append(
                PackEntry(builder.path("clip", clip_name), FNP_CLIP, CLIP_FORMAT_VERSION, payload)
            )
            builder.report.clips.append(
                f"{clip_name}: {sampled.frame_count} frames at {sampled.frame_rate_hz:g} Hz, "
                f"{'looping' if sampled.loops else 'single'}, {sampled.varying_tracks} of "
                f"{3 * len(skeleton_result.joints)} tracks vary, {len(markers)} marker(s), "
                f"{len(payload)} bytes"
            )

    figure_payload = encode_figure(
        parts=parts,
        texture_ids=builder.texture_ids(),
        skeleton_id=builder.asset_id("skeleton"),
        bounds_min=tuple(bounds_min),
        bounds_max=tuple(bounds_max),
        label=f"{name}/figure",
    )
    builder.entries.append(
        PackEntry(builder.path("figure"), FNP_FIGURE, KIND_VERSION, figure_payload)
    )

    builder.report.part_count = len(parts)
    builder.report.material_count = builder.material_count()
    builder.report.joint_count = joint_count
    builder.report.bounds_min = tuple(bounds_min)
    builder.report.bounds_max = tuple(bounds_max)
    return builder.entries, builder.report


def write_output(out_dir: Path, all_entries: dict[str, list[PackEntry]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    index_entries = []
    for name, entries in all_entries.items():
        figure_dir = out_dir / name
        figure_dir.mkdir(parents=True, exist_ok=True)
        for entry in entries:
            file_name = entry.path.split("/", 2)[2].replace("/", "_") + ".bin"
            (figure_dir / file_name).write_bytes(entry.data)
            index_entries.append(
                {
                    "path": entry.path,
                    "kind": entry.kind,
                    "kind_version": entry.kind_version,
                    "file": f"{name}/{file_name}",
                }
            )
    index = {"entries": index_entries}
    (out_dir / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=False) + "\n", encoding="ascii"
    )


@dataclass
class ClipRequest:
    """Which clips of one figure to export, at which rate, with which markers."""

    clips: list[str]
    frame_rate_hz: float
    # Clip name -> `{marker name: Blender frame}`, as the authoring report writes it.
    events: dict[str, dict[str, int]] = field(default_factory=dict)


def parse_clip_requests(args) -> dict[str, ClipRequest]:
    """`--clips NAME=a,b` plus `--clip-events NAME=<report.json>` into one request per figure."""
    requests: dict[str, ClipRequest] = {}
    for item in args.clips:
        name, _, listing = item.partition("=")
        clips = [clip.strip() for clip in listing.split(",") if clip.strip()]
        if not name or not clips:
            raise BuildError(f"--clips expects NAME=clip[,clip...], got {item!r}")
        requests.setdefault(
            name, ClipRequest(clips=[], frame_rate_hz=args.clip_rate)
        ).clips.extend(clips)
    for item in args.clip_events:
        name, _, path = item.partition("=")
        if not name or not path:
            raise BuildError(f"--clip-events expects NAME=PATH, got {item!r}")
        if name not in requests:
            raise BuildError(f"--clip-events for {name!r}, which has no --clips")
        try:
            report = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise BuildError(f"--clip-events {path}: {error}") from error
        events = {
            str(clip.get("name")): dict(clip.get("events") or {})
            for clip in report.get("clips", [])
            if clip.get("name")
        }
        missing = [clip for clip in requests[name].clips if clip not in events]
        if missing:
            raise BuildError(f"--clip-events {path}: no entry for {missing}")
        requests[name].events = events
    return requests


def _print_report(reports: list[FigureReport]) -> None:
    for report in reports:
        print(f"== {report.name} ==")
        print(f"  triangles:       {report.triangle_count}")
        print(f"  mesh parts:      {report.part_count}")
        print(f"  materials:       {report.material_count}")
        print(f"  textures:        {report.texture_count}")
        print(f"  joints:          {report.joint_count}")
        print(
            "  bounds (engine, Z-up): "
            f"min={tuple(round(v, 4) for v in report.bounds_min)} "
            f"max={tuple(round(v, 4) for v in report.bounds_max)}"
        )
        print(
            f"  forward-kinematics check: {report.fk_samples_checked} vertices, "
            f"max error {report.fk_max_error:.3e}"
        )
        print(
            f"  forward-kinematics tangent check: {report.fk_tangent_checked} vertices, "
            f"max error {report.fk_tangent_max_error:.3e}"
        )
        print(
            f"  mesh parts with TANGENT: {report.tangent_primitive_count}, "
            f"without (no UV, [0,0,0,0]): {report.no_tangent_primitive_count}"
        )
        for texture in report.textures:
            print(f"  texture {texture}")
        for clip in report.clips:
            print(f"  clip {clip}")
        for note in report.notes:
            print(f"  note: {note}")


def parse_figure_sources(args: argparse.Namespace) -> list[tuple[str, Path]]:
    """`(name, path)` for every figure: `--source`/`--suffix`/`--figures`, then each `--figure`."""
    sources: list[tuple[str, Path]] = []
    if args.source is not None:
        names = [n.strip() for n in args.figures.split(",") if n.strip()]
        sources += [(name, glb_path_for(args.source, name, args.suffix)) for name in names]
    for item in args.figure:
        name, separator, path = item.partition("=")
        if not separator or not name.strip() or not path.strip():
            raise BuildError(f"--figure expects NAME=PATH, got {item!r}")
        sources.append((name.strip(), Path(path.strip())))
    if not sources:
        raise BuildError("no figures: pass --source (with --figures) or --figure NAME=PATH")
    seen: set[str] = set()
    for name, _path in sources:
        if name in seen:
            raise BuildError(f"figure name {name!r} given twice")
        seen.add(name)
    return sources


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--source",
        type=Path,
        help="directory containing <name><suffix> for every name in --figures",
    )
    parser.add_argument(
        "--suffix",
        default=GLB_SUFFIX,
        help=f"file name suffix of each figure's source file (default: {GLB_SUFFIX})",
    )
    parser.add_argument(
        "--out", required=True, type=Path, help="output directory for payload files and index.json"
    )
    parser.add_argument(
        "--figures",
        default=",".join(FIGURE_NAMES),
        help="comma-separated figure base names under --source (default: soul,imp,brute)",
    )
    parser.add_argument(
        "--figure",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="one more figure from any .glb, packed under NAME (repeatable)",
    )
    parser.add_argument(
        "--clips",
        action="append",
        default=[],
        metavar="NAME=CLIP,CLIP",
        help="clips of NAME to export as FNP_CLIP entries (repeatable)",
    )
    parser.add_argument(
        "--clip-events",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="authoring report holding clips[].events (Blender frames, counted from 1)",
    )
    parser.add_argument(
        "--clip-rate",
        type=float,
        default=DEFAULT_CLIP_RATE_HZ,
        help=f"rate the clips were authored at, in Hz (default: {DEFAULT_CLIP_RATE_HZ:g})",
    )
    parser.add_argument(
        "--max-texture-size",
        type=int,
        help="reduce textures whose longer side exceeds this by a power of two (needs numpy)",
    )
    args = parser.parse_args(argv)

    all_entries: dict[str, list[PackEntry]] = {}
    reports: list[FigureReport] = []
    try:
        sources = parse_figure_sources(args)
        clip_requests = parse_clip_requests(args)
        unknown = sorted(set(clip_requests) - {name for name, _ in sources})
        if unknown:
            raise BuildError(f"--clips names {unknown}, which are not among the figures")
        for name, glb_path in sources:
            if not glb_path.is_file():
                raise BuildError(f"source file not found: {glb_path}")
        # Every texture of every figure against the engine limits first, from the headers alone.
        problems: list[str] = []
        for name, glb_path in sources:
            try:
                plan_figure_textures(name, load_glb(glb_path), args.max_texture_size)
            except (BuildError, GlbError) as error:
                problems.extend(str(error).splitlines())
        if problems:
            listing = "\n  ".join(problems)
            raise BuildError(f"{len(problems)} texture problem(s), nothing packed:\n  {listing}")
        for name, glb_path in sources:
            entries, report = build_figure(
                name, glb_path, args.max_texture_size, clip_requests.get(name)
            )
            all_entries[name] = entries
            reports.append(report)
    except (
        BuildError,
        ClipError,
        GlbError,
        SkeletonError,
        PayloadError,
        PngError,
        TextureError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    # Everything validated for every figure before anything touches disk (contract: "liefert
    # nichts Halbes aus").
    write_output(args.out, all_entries)
    _print_report(reports)
    print(f"wrote index.json and {sum(len(e) for e in all_entries.values())} payload files to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
