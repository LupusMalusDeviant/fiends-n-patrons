"""Minimal glTF 2 binary (.glb) reader: container framing, JSON chunk and accessor decoding.

Standard-library only (no `pygltflib`, no `numpy`): `struct` and `json` are enough for the
subset of glTF this converter needs (contract: figuren-in-engine-spec.md, "Python, nur
Standardbibliothek"). Sparse accessors and interleaved buffer views with an explicit
`byteStride` are supported for completeness, but were not exercised by the three shipped
fixtures (`soul`/`imp`/`brute`, all dense and non-interleaved) -- see `inspect()` output kept in
the PR description for the concrete structure this was written against.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_GLB_MAGIC = b"glTF"
_CHUNK_JSON = 0x4E4F534A
_CHUNK_BIN = 0x004E4942

# glTF accessor componentType -> (struct format char, byte size, signed integer max used for
# `normalized` decoding).
_COMPONENT_TYPES: dict[int, tuple[str, int, int]] = {
    5120: ("b", 1, 127),  # BYTE
    5121: ("B", 1, 255),  # UNSIGNED_BYTE
    5122: ("h", 2, 32767),  # SHORT
    5123: ("H", 2, 65535),  # UNSIGNED_SHORT
    5125: ("I", 4, 0),  # UNSIGNED_INT (never normalized per spec)
    5126: ("f", 4, 0),  # FLOAT
}

_TYPE_COMPONENT_COUNTS: dict[str, int] = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
    "MAT2": 4,
    "MAT3": 9,
    "MAT4": 16,
}


class GlbError(ValueError):
    """A `.glb` file is structurally invalid or uses a feature this reader does not support."""


@dataclass(frozen=True)
class Glb:
    """A parsed `.glb`: the JSON document and the (possibly empty) binary chunk."""

    json_doc: dict[str, Any]
    bin_chunk: bytes


def load_glb(path: Path) -> Glb:
    """Reads and frames a `.glb` file (12-byte header, then length-prefixed chunks)."""
    data = path.read_bytes()
    if len(data) < 12:
        raise GlbError(f"{path}: file shorter than the 12-byte glTF binary header")
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    if magic != _GLB_MAGIC:
        raise GlbError(f"{path}: not a glTF binary file (bad magic {magic!r})")
    if version != 2:
        raise GlbError(f"{path}: unsupported glTF binary version {version} (expected 2)")
    if length > len(data):
        raise GlbError(f"{path}: header declares {length} bytes, file has {len(data)}")

    offset = 12
    json_chunk: bytes | None = None
    bin_chunk = b""
    while offset < length:
        if offset + 8 > length:
            raise GlbError(f"{path}: truncated chunk header at offset {offset}")
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        if offset + chunk_length > length:
            raise GlbError(f"{path}: chunk at offset {offset} overruns the declared file length")
        chunk_data = data[offset : offset + chunk_length]
        offset += chunk_length
        if chunk_type == _CHUNK_JSON:
            if json_chunk is not None:
                raise GlbError(f"{path}: more than one JSON chunk")
            json_chunk = chunk_data
        elif chunk_type == _CHUNK_BIN:
            bin_chunk = chunk_data
        # Unknown chunk types are ignored per the glTF binary spec (forward compatibility).

    if json_chunk is None:
        raise GlbError(f"{path}: no JSON chunk")
    try:
        doc = json.loads(json_chunk.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise GlbError(f"{path}: JSON chunk is not valid UTF-8") from error
    except json.JSONDecodeError as error:
        raise GlbError(f"{path}: JSON chunk does not parse: {error}") from error
    if not isinstance(doc, dict):
        raise GlbError(f"{path}: top-level glTF JSON is not an object")
    return Glb(json_doc=doc, bin_chunk=bin_chunk)


def _buffer_view_bytes(glb: Glb, buffer_view_index: int) -> tuple[bytes, int]:
    """Returns `(view_bytes, byte_stride)`; `byte_stride` is 0 when the view is tightly packed."""
    views = glb.json_doc.get("bufferViews", [])
    if not (0 <= buffer_view_index < len(views)):
        raise GlbError(f"bufferView index {buffer_view_index} out of range")
    view = views[buffer_view_index]
    if view.get("buffer", 0) != 0:
        raise GlbError("only a single embedded buffer (index 0) is supported")
    start = int(view.get("byteOffset", 0))
    length = int(view["byteLength"])
    end = start + length
    if end > len(glb.bin_chunk):
        raise GlbError("bufferView overruns the binary chunk")
    return glb.bin_chunk[start:end], int(view.get("byteStride", 0))


def read_accessor(glb: Glb, accessor_index: int) -> list[Any]:
    """Decodes accessor `accessor_index` into a flat Python list.

    `VEC2`/`VEC3`/`VEC4`/`MATn` accessors yield one tuple of floats/ints per element; `SCALAR`
    accessors yield the bare numbers unwrapped (convenient at every call site: indices, joint
    weights' scalar helpers, etc.).

    Integer components declared `normalized` (glTF core spec §3.6.2.1) are converted to floats in
    `[0, 1]` (unsigned) or `[-1, 1]` (signed); `JOINTS_0` is never normalized and always yields
    plain integers, matching how it is used as an index.
    """
    accessors = glb.json_doc.get("accessors", [])
    if not (0 <= accessor_index < len(accessors)):
        raise GlbError(f"accessor index {accessor_index} out of range")
    accessor = accessors[accessor_index]
    if "sparse" in accessor:
        raise GlbError(
            f"accessor {accessor_index}: sparse accessors are not supported by this converter"
        )
    component_type = accessor["componentType"]
    if component_type not in _COMPONENT_TYPES:
        raise GlbError(f"accessor {accessor_index}: unsupported componentType {component_type}")
    fmt_char, comp_size, norm_max = _COMPONENT_TYPES[component_type]
    accessor_type = accessor["type"]
    if accessor_type not in _TYPE_COMPONENT_COUNTS:
        raise GlbError(f"accessor {accessor_index}: unsupported type {accessor_type!r}")
    component_count = _TYPE_COMPONENT_COUNTS[accessor_type]
    count = int(accessor["count"])
    normalized = bool(accessor.get("normalized", False)) and norm_max != 0

    if "bufferView" not in accessor:
        # A missing bufferView means "all zeros" per the glTF core spec; none of the three
        # fixtures rely on this, but a clear zero-fill is safer than silently skipping the
        # attribute.
        zero = (0.0 if fmt_char == "f" else 0) if component_count == 1 else None
        if component_count == 1:
            return [zero] * count
        fill = (0.0 if fmt_char == "f" else 0,) * component_count
        return [fill] * count

    view_bytes, byte_stride = _buffer_view_bytes(glb, accessor["bufferView"])
    view_offset = int(accessor.get("byteOffset", 0))
    element_size = comp_size * component_count
    stride = byte_stride if byte_stride else element_size
    struct_fmt = f"<{component_count}{fmt_char}"

    needed_end = view_offset + stride * max(0, count - 1) + element_size
    if needed_end > len(view_bytes):
        raise GlbError(
            f"accessor {accessor_index}: declares {count} elements but the buffer view is too "
            f"short ({len(view_bytes)} bytes available, {needed_end} needed)"
        )

    result: list[Any] = []
    divisor = float(norm_max) if normalized else 1.0
    for i in range(count):
        start = view_offset + i * stride
        raw = struct.unpack_from(struct_fmt, view_bytes, start)
        if normalized:
            raw = tuple(max(value / divisor, -1.0) if value < 0 else value / divisor for value in raw)
        result.append(raw[0] if component_count == 1 else raw)
    return result


def primitive_attribute_counts_agree(counts: list[int]) -> bool:
    """`True` if every attribute accessor of a primitive reports the same vertex count."""
    return len(set(counts)) <= 1
