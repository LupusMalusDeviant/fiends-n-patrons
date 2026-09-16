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
against the actual grimoire_assets v0.1.1 code: `AssetKind::MESH`/`MATERIAL` (`ids.rs`) are
doc-commented "reserved for a future kind; a v1 pack reader rejects it", and
`PackWriter::add`/`PackReader::from_bytes` both run every kind through `classify_kind`, which
maps raw `2..=5` to `PackError::ReservedKind` unconditionally -- `PackWriter::add` would fail on
every MESH/MATERIAL entry. This module instead defines `FNP_MESH = 0x8004` and
`FNP_MATERIAL = 0x8005`, in the same opaque `0x8000..=0xFFFF` application range the spec already
uses for `FNP_TEXTURE_RAW`/`FNP_SKELETON`/`FNP_FIGURE`. The wire layout, `kind_version` and every
other kind value are unchanged from the spec.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

MAX_VERTEX_COUNT = 1_000_000
MAX_INDEX_COUNT = 3_000_000
MAX_JOINT_COUNT = 256
MAX_TEXTURE_PIXELS = 64_000_000  # spec: "Produkt <= 64 Mio." (decimal million, not 64 MiB)
WEIGHT_TOLERANCE = 1.0e-3
NO_TEXTURE = 0xFFFF_FFFF

# See the module docstring: MESH/MATERIAL are reassigned off the engine-reserved 2/3 into the
# application range; TEXTURE_RAW/SKELETON/FIGURE match figuren-in-engine-spec.md as written.
FNP_MESH = 0x8004
FNP_MATERIAL = 0x8005
FNP_TEXTURE_RAW = 0x8001
FNP_SKELETON = 0x8002
FNP_FIGURE = 0x8003
KIND_VERSION = 1

_VERTEX_STRUCT = struct.Struct("<3f 3f 2f 4H 4f")


class PayloadError(ValueError):
    """A produced payload would violate one of the spec's invariants; nothing is written."""


@dataclass(frozen=True)
class Vertex:
    position: tuple[float, float, float]
    normal: tuple[float, float, float]
    uv: tuple[float, float]
    joints: tuple[int, int, int, int]
    weights: tuple[float, float, float, float]


def encode_mesh(
    vertices: list[Vertex], indices: list[int], *, joint_count: int, label: str
) -> bytes:
    """Encodes one `FNP_MESH` (spec kind `MESH`) primitive payload."""
    vertex_count = len(vertices)
    index_count = len(indices)
    if vertex_count > MAX_VERTEX_COUNT:
        raise PayloadError(f"{label}: {vertex_count} vertices exceeds MAX_VERTEX_COUNT")
    if index_count > MAX_INDEX_COUNT:
        raise PayloadError(f"{label}: {index_count} indices exceeds MAX_INDEX_COUNT")
    if index_count % 3 != 0:
        raise PayloadError(f"{label}: index count {index_count} is not divisible by 3")

    out = bytearray()
    out += struct.pack("<I", KIND_VERSION)
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
        out += _VERTEX_STRUCT.pack(
            *v.position, *v.normal, *v.uv, *v.joints, *v.weights
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

    One flat record per joint (`parent`, `inverse_bind`, name, rest-pose translation/rotation/
    scale, in that order) -- the spec's "je Knochen: ...  Dazu je Knochen: ..." phrasing reads as
    two clauses of the *same* per-bone record, not two separate passes over all bones; this is
    also the only layout a streaming reader could produce without buffering the whole skeleton.
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
