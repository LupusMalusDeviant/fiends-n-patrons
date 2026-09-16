"""Binary encoders for the payload kinds in figuren-in-engine-spec.md, plus their own validation.

Every `encode_*` function checks the invariants the spec demands (index/joint bounds, weight
sums, texture size, parent order) *before* returning bytes, and raises [`PayloadError`] instead
of writing anything otherwise -- a failed check aborts the whole run (see `build_figure_pack.py`).
`crates/fnp_content/src/bin/figure_pack_builder.rs` re-checks the structural ones independently
from the raw bytes before handing them to `PackWriter`, as a second, unrelated implementation of
the same checks (defense in depth, not because either side trusts the other less).

## Kind values (deviation from figuren-in-engine-spec.md, flagged in the PR description)

The spec assigns `MESH = 2` and `MATERIAL = 3`, reasoning that contract §12 "gives
`0x8000..=0xFFFF` explicitly to the application" and that `2`/`3` are the engine's own
already-named `AssetKind::MESH`/`AssetKind::MATERIAL` constants. That reasoning does not hold
against the actual grimoire_assets code: `AssetKind::MESH`/`MATERIAL` (`ids.rs`) are doc-commented
"reserved for a future kind; a v1 pack reader rejects it", and
`PackWriter::add`/`PackReader::from_bytes` both run every kind through `classify_kind`, which
maps raw `2..=5` to `PackError::ReservedKind` unconditionally -- `PackWriter::add` would fail on
every MESH/MATERIAL entry. Both converter sides hit this independently and first picked different
replacement values (Strang A: `0x8004`/`0x8005`); the PO settled it in the engine's favour since
Strang B's `0x8000`/`0x8004` ships as release `v0.2.0`. This module now matches that: `FNP_MESH =
0x8000`, `FNP_MATERIAL = 0x8004`, in the same opaque `0x8000..=0xFFFF` application range the spec
already uses for `FNP_TEXTURE_RAW`/`FNP_SKELETON`/`FNP_FIGURE`. The wire layout, `kind_version`
and every other kind value are unchanged from the spec.

## FNP_SKELETON layout (second alignment with the engine, same cause)

The spec's "je Knochen: `parent`, `inverse_bind`, `name`. Dazu je Knochen: `translation`,
`rotation`, `scale`." was ambiguous between one combined per-joint record and two separate passes
over all joints; this module first read it as one combined record (the more natural reading of
the German, and the only shape a streaming reader could produce without buffering the whole
skeleton). The engine's reader does two separate passes -- all joints' `parent`/`inverse_bind`/
`name` first, then all joints' `translation`/`rotation`/`scale` -- and, same as the kind values,
that is now authoritative. `encode_skeleton` below writes two passes accordingly.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass

MAX_VERTEX_COUNT = 1_000_000
MAX_INDEX_COUNT = 3_000_000
MAX_JOINT_COUNT = 256
MAX_TEXTURE_PIXELS = 64_000_000  # spec: "Produkt <= 64 Mio." (decimal million, not 64 MiB)
WEIGHT_TOLERANCE = 1.0e-3
TANGENT_TOLERANCE = 1.0e-3  # texturqualitaet-spec.md: |xyz|=1 and w=+-1, each within this tolerance
NO_TEXTURE = 0xFFFF_FFFF

# The one fallback texturqualitaet-spec.md defines, for a primitive with no TEXCOORD_0 (iris,
# staff, teeth): every vertex gets exactly this tangent. `encode_mesh` treats it as always valid,
# regardless of the |xyz|=1/w=+-1 rule below (which does not apply to it).
NO_TANGENT: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

# See the module docstring: MESH/MATERIAL are reassigned off the engine-reserved 2/3 into the
# application range, matching the engine's own (authoritative) choice; TEXTURE_RAW/SKELETON/
# FIGURE match figuren-in-engine-spec.md as written.
FNP_MESH = 0x8000
FNP_MATERIAL = 0x8004
FNP_TEXTURE_RAW = 0x8001
FNP_SKELETON = 0x8002
FNP_FIGURE = 0x8003
# kind_version is tracked per kind, not shared across all of them (texturqualitaet-spec.md, A2):
# only FNP_MESH moves to Fassung 2 (adds `tangent: f32[4]`, 72 bytes/vertex instead of 56).
# MATERIAL/TEXTURE_RAW/SKELETON/FIGURE stay on KIND_VERSION (Fassung 1) -- unaffected by this PR.
KIND_VERSION = 1
MESH_KIND_VERSION = 2

_VERTEX_STRUCT = struct.Struct("<3f 3f 2f 4H 4f 4f")


class PayloadError(ValueError):
    """A produced payload would violate one of the spec's invariants; nothing is written."""


@dataclass(frozen=True)
class Vertex:
    position: tuple[float, float, float]
    normal: tuple[float, float, float]
    uv: tuple[float, float]
    joints: tuple[int, int, int, int]
    weights: tuple[float, float, float, float]
    # Raw (unrotated) tangent, exactly like `normal`: the engine rotates `tangent.xyz` with the
    # same bone matrices as the normal (Strang B), so this module must never pre-rotate it -- doing
    # so would double the +90-degree-about-X axis correction the skeleton root already carries (see
    # `build_figure_pack.py`'s module docstring and `rig_math.vector_transform`). Defaults to the
    # spec's one fallback so existing call sites that predate FNP_MESH Fassung 2 keep working.
    tangent: tuple[float, float, float, float] = NO_TANGENT


def _check_tangent(tangent: tuple[float, float, float, float], *, label: str, vertex_index: int) -> None:
    """Validates one vertex's tangent: exactly [`NO_TANGENT`], or |xyz|=1 and w=+-1 (tol 1e-3).

    "Es gibt keinen dritten Fall" (texturqualitaet-spec.md): every tangent this module accepts is
    one of these two shapes, nothing else.
    """
    if tangent == NO_TANGENT:
        return
    x, y, z, w = tangent
    magnitude = math.sqrt(x * x + y * y + z * z)
    if abs(magnitude - 1.0) > TANGENT_TOLERANCE:
        raise PayloadError(
            f"{label}: vertex {vertex_index} tangent {tangent} has |xyz|={magnitude}, "
            f"not 1.0 (tolerance {TANGENT_TOLERANCE}) and not the {NO_TANGENT} fallback"
        )
    if abs(abs(w) - 1.0) > TANGENT_TOLERANCE:
        raise PayloadError(
            f"{label}: vertex {vertex_index} tangent.w={w}, not +1 or -1 (tolerance "
            f"{TANGENT_TOLERANCE})"
        )


def encode_mesh(
    vertices: list[Vertex], indices: list[int], *, joint_count: int, label: str
) -> bytes:
    """Encodes one `FNP_MESH` (spec kind `MESH`) primitive payload, always as Fassung 2."""
    vertex_count = len(vertices)
    index_count = len(indices)
    if vertex_count > MAX_VERTEX_COUNT:
        raise PayloadError(f"{label}: {vertex_count} vertices exceeds MAX_VERTEX_COUNT")
    if index_count > MAX_INDEX_COUNT:
        raise PayloadError(f"{label}: {index_count} indices exceeds MAX_INDEX_COUNT")
    if index_count % 3 != 0:
        raise PayloadError(f"{label}: index count {index_count} is not divisible by 3")

    out = bytearray()
    out += struct.pack("<I", MESH_KIND_VERSION)
    out += struct.pack("<II", vertex_count, index_count)
    for vertex_index, v in enumerate(vertices):
        for joint in v.joints:
            if not (0 <= joint < joint_count):
                raise PayloadError(
                    f"{label}: vertex {vertex_index} joint index {joint} >= joint_count "
                    f"{joint_count}"
                )
        weight_sum = sum(v.weights)
        if abs(weight_sum - 1.0) > WEIGHT_TOLERANCE:
            raise PayloadError(
                f"{label}: vertex {vertex_index} weight sum {weight_sum} deviates from 1.0 by "
                f"more than {WEIGHT_TOLERANCE}"
            )
        _check_tangent(v.tangent, label=label, vertex_index=vertex_index)
        out += _VERTEX_STRUCT.pack(
            *v.position, *v.normal, *v.uv, *v.joints, *v.weights, *v.tangent
        )
    for i, index in enumerate(indices):
        if not (0 <= index < vertex_count):
            raise PayloadError(
                f"{label}: index #{i} value {index} >= vertex_count {vertex_count}"
            )
        out += struct.pack("<I", index)
    return bytes(out)


def encode_material(
    *,
    base_color: tuple[float, float, float, float],
    metallic: float,
    roughness: float,
    emissive: tuple[float, float, float],
    alpha_mode: int,
    alpha_cutoff: float,
    base_color_texture: int | None,
    normal_texture: int | None,
    orm_texture: int | None,
    label: str,
) -> bytes:
    """Encodes one `FNP_MATERIAL` (spec kind `MATERIAL`) payload."""
    if alpha_mode not in (0, 1, 2):
        raise PayloadError(f"{label}: alpha_mode {alpha_mode} not in {{0, 1, 2}}")
    out = bytearray()
    out += struct.pack("<I", KIND_VERSION)
    out += struct.pack("<4f", *base_color)
    out += struct.pack("<2f", metallic, roughness)
    out += struct.pack("<3f", *emissive)
    out += struct.pack("<B", alpha_mode)
    out += struct.pack("<f", alpha_cutoff)
    for texture_index in (base_color_texture, normal_texture, orm_texture):
        out += struct.pack("<I", NO_TEXTURE if texture_index is None else texture_index)
    return bytes(out)


def encode_texture_raw(*, width: int, height: int, color_space: int, rgba: bytes, label: str) -> bytes:
    """Encodes one `FNP_TEXTURE_RAW` payload."""
    if width < 1 or height < 1:
        raise PayloadError(f"{label}: width/height must be >= 1, got {width}x{height}")
    if width * height > MAX_TEXTURE_PIXELS:
        raise PayloadError(
            f"{label}: {width}x{height} = {width * height} pixels exceeds {MAX_TEXTURE_PIXELS}"
        )
    if color_space not in (0, 1):
        raise PayloadError(f"{label}: color_space {color_space} not in {{0, 1}}")
    expected_len = width * height * 4
    if len(rgba) != expected_len:
        raise PayloadError(
            f"{label}: rgba payload is {len(rgba)} bytes, expected width*height*4={expected_len}"
        )
    out = bytearray()
    out += struct.pack("<I", KIND_VERSION)
    out += struct.pack("<II", width, height)
    out += struct.pack("<B", color_space)
    out += rgba
    return bytes(out)


def encode_skeleton(joints, *, label: str) -> bytes:  # joints: list[skeleton.Joint]
    """Encodes one `FNP_SKELETON` payload.

    Two passes over all joints (see the module docstring: the engine's reader, now
    authoritative): first every joint's `parent`/`inverse_bind`/name, then every joint's rest-pose
    `translation`/`rotation`/`scale`.
    """
    joint_count = len(joints)
    if joint_count > MAX_JOINT_COUNT:
        raise PayloadError(f"{label}: {joint_count} joints exceeds MAX_JOINT_COUNT")
    out = bytearray()
    out += struct.pack("<I", KIND_VERSION)
    out += struct.pack("<I", joint_count)
    for index, joint in enumerate(joints):
        if joint.parent != -1 and not (0 <= joint.parent < index):
            raise PayloadError(
                f"{label}: joint {index} ({joint.name!r}) has parent {joint.parent}, "
                "not -1 and not < its own index"
            )
        if len(joint.inverse_bind) != 16:
            raise PayloadError(f"{label}: joint {index} inverse_bind is not 16 floats")
        name_bytes = joint.name.encode("utf-8")
        if len(name_bytes) > 63:
            raise PayloadError(f"{label}: joint {index} name exceeds 63 bytes")
        out += struct.pack("<i", joint.parent)
        out += struct.pack("<16f", *joint.inverse_bind)
        out += struct.pack("<B", len(name_bytes))
        out += name_bytes
    for joint in joints:
        out += struct.pack("<3f", *joint.translation)
        out += struct.pack("<4f", *joint.rotation)
        out += struct.pack("<3f", *joint.scale)
    return bytes(out)


def encode_figure(
    *,
    parts: list[tuple[int, int]],
    texture_ids: list[int],
    skeleton_id: int,
    bounds_min: tuple[float, float, float],
    bounds_max: tuple[float, float, float],
    label: str,
) -> bytes:
    """Encodes one `FNP_FIGURE` payload. `parts` is `[(mesh_id, material_id), ...]`."""
    if not parts:
        raise PayloadError(f"{label}: figure has no parts")
    out = bytearray()
    out += struct.pack("<I", KIND_VERSION)
    out += struct.pack("<I", len(parts))
    for mesh_id, material_id in parts:
        out += struct.pack("<QQ", mesh_id, material_id)
    out += struct.pack("<I", len(texture_ids))
    for texture_id in texture_ids:
        out += struct.pack("<Q", texture_id)
    out += struct.pack("<Q", skeleton_id)
    out += struct.pack("<3f", *bounds_min)
    out += struct.pack("<3f", *bounds_max)
    return bytes(out)
