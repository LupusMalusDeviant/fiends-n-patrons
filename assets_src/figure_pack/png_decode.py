"""Standard-library PNG decoder: embedded glTF images -> raw RGBA8, top row first.

No `Pillow`: `zlib` for the DEFLATE stream, plain Python for chunk framing and the PNG scanline
filters (contract: figuren-in-engine-spec.md, "Python, nur Standardbibliothek"). Handles every
colour type and bit depth the PNG spec allows (grayscale, palette, grayscale+alpha, truecolor,
truecolor+alpha; 1/2/4/8/16 bits per sample) plus `tRNS` transparency, and clearly rejects
interlacing (Adam7) and anything structurally invalid instead of guessing -- the three shipped
fixtures only use 8-bit truecolor (no alpha, no palette, no interlacing), so every other path
below is exercised by `test_png_decode.py`, not by the real assets.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Allowed (colortype -> allowed bit depths) combinations per the PNG spec (Table 11.1).
_ALLOWED_DEPTHS: dict[int, tuple[int, ...]] = {
    0: (1, 2, 4, 8, 16),  # grayscale
    2: (8, 16),  # truecolor
    3: (1, 2, 4, 8),  # palette
    4: (8, 16),  # grayscale + alpha
    6: (8, 16),  # truecolor + alpha
}
_CHANNELS: dict[int, int] = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


class PngError(ValueError):
    """A PNG image is structurally invalid or uses a feature this decoder does not support."""


@dataclass(frozen=True)
class DecodedImage:
    """A fully decoded image: `len(rgba) == width * height * 4`, top row first."""

    width: int
    height: int
    rgba: bytes


def decode_png(data: bytes, *, label: str = "<png>") -> DecodedImage:
    """Decodes one PNG image to raw, straight-alpha RGBA8.

    Raises [`PngError`] with a message naming `label` for anything this decoder does not (yet)
    support, rather than guessing at the pixel data.
    """
    if data[:8] != _SIGNATURE:
        raise PngError(f"{label}: not a PNG file (bad signature)")

    ihdr: dict[str, int] | None = None
    idat = bytearray()
    palette: list[tuple[int, int, int]] | None = None
    trns: bytes | None = None

    offset = 8
    total = len(data)
    while offset < total:
        if offset + 8 > total:
            raise PngError(f"{label}: truncated chunk header")
        (chunk_len,) = struct.unpack_from(">I", data, offset)
        chunk_type = data[offset + 4 : offset + 8].decode("ascii", errors="replace")
        body_start = offset + 8
        body_end = body_start + chunk_len
        if body_end + 4 > total:
            raise PngError(f"{label}: chunk {chunk_type!r} overruns the file")
        body = data[body_start:body_end]
        offset = body_end + 4  # skip the trailing CRC; PackWriter's own SHA-256 is our integrity

        if chunk_type == "IHDR":
            if ihdr is not None:
                raise PngError(f"{label}: more than one IHDR chunk")
            width, height, bit_depth, color_type, compression, filter_method, interlace = (
                struct.unpack(">IIBBBBB", body)
            )
            if compression != 0:
                raise PngError(f"{label}: unsupported compression method {compression}")
            if filter_method != 0:
                raise PngError(f"{label}: unsupported filter method {filter_method}")
            if interlace != 0:
                raise PngError(f"{label}: interlaced (Adam7) PNGs are not supported")
            if color_type not in _ALLOWED_DEPTHS:
                raise PngError(f"{label}: unsupported color type {color_type}")
            if bit_depth not in _ALLOWED_DEPTHS[color_type]:
                raise PngError(
                    f"{label}: bit depth {bit_depth} is not valid for color type {color_type}"
                )
            if width == 0 or height == 0:
                raise PngError(f"{label}: zero width or height")
            ihdr = {
                "width": width,
                "height": height,
                "bit_depth": bit_depth,
                "color_type": color_type,
            }
        elif chunk_type == "PLTE":
            if len(body) % 3 != 0:
                raise PngError(f"{label}: PLTE length is not a multiple of 3")
            palette = [tuple(body[i : i + 3]) for i in range(0, len(body), 3)]
        elif chunk_type == "tRNS":
            trns = bytes(body)
        elif chunk_type == "IDAT":
            idat.extend(body)
        elif chunk_type == "IEND":
            break

    if ihdr is None:
        raise PngError(f"{label}: no IHDR chunk")
    if not idat:
        raise PngError(f"{label}: no IDAT data")
    if ihdr["color_type"] == 3 and palette is None:
        raise PngError(f"{label}: palette color type without a PLTE chunk")

    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error as error:
        raise PngError(f"{label}: DEFLATE stream does not decompress: {error}") from error

    width = ihdr["width"]
    height = ihdr["height"]
    bit_depth = ihdr["bit_depth"]
    color_type = ihdr["color_type"]
    channels = _CHANNELS[color_type]

    bpp = max(1, (bit_depth * channels) // 8)
    row_bits = width * bit_depth * channels
    row_bytes = (row_bits + 7) // 8
    expected_len = (row_bytes + 1) * height
    if len(raw) != expected_len:
        raise PngError(
            f"{label}: unfiltered stream is {len(raw)} bytes, expected {expected_len} "
            f"({height} rows x (1 filter byte + {row_bytes} pixel bytes))"
        )

    scanlines = _defilter(raw, height, row_bytes, bpp, label)
    rgba = _assemble_rgba(
        scanlines, width, height, bit_depth, color_type, channels, palette, trns, label
    )
    if len(rgba) != width * height * 4:
        raise PngError(f"{label}: internal error, wrong output size")
    return DecodedImage(width=width, height=height, rgba=rgba)


def _paeth(a: int, b: int, c: int) -> int:
    """PNG Paeth predictor (spec §9.4): picks whichever of a/b/c is closest to a+b-c."""
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _defilter(raw: bytes, height: int, row_bytes: int, bpp: int, label: str) -> bytearray:
    """Reverses the per-scanline PNG filters (spec §9.2-9.4), returning `height*row_bytes` bytes."""
    out = bytearray(height * row_bytes)
    previous = bytearray(row_bytes)
    pos = 0
    for row in range(height):
        filter_type = raw[pos]
        pos += 1
        current = bytearray(raw[pos : pos + row_bytes])
        pos += row_bytes
        if filter_type == 0:
            pass
        elif filter_type == 1:  # Sub
            for i in range(row_bytes):
                a = current[i - bpp] if i >= bpp else 0
                current[i] = (current[i] + a) & 0xFF
        elif filter_type == 2:  # Up
            for i in range(row_bytes):
                current[i] = (current[i] + previous[i]) & 0xFF
        elif filter_type == 3:  # Average
            for i in range(row_bytes):
                a = current[i - bpp] if i >= bpp else 0
                b = previous[i]
                current[i] = (current[i] + (a + b) // 2) & 0xFF
        elif filter_type == 4:  # Paeth
            for i in range(row_bytes):
                a = current[i - bpp] if i >= bpp else 0
                b = previous[i]
                c = previous[i - bpp] if i >= bpp else 0
                current[i] = (current[i] + _paeth(a, b, c)) & 0xFF
        else:
            raise PngError(f"{label}: unknown scanline filter type {filter_type} in row {row}")
        out[row * row_bytes : (row + 1) * row_bytes] = current
        previous = current
    return out


def _unpack_samples(row: bytes, width: int, bit_depth: int, channels: int) -> list[int]:
    """Expands one defiltered scanline into `width*channels` integer sample values."""
    if bit_depth == 8:
        return list(row[: width * channels])
    if bit_depth == 16:
        return [
            (row[i] << 8) | row[i + 1] for i in range(0, width * channels * 2, 2)
        ]
    # bit_depth in (1, 2, 4): only grayscale or palette reach here (spec Table 11.1).
    samples: list[int] = []
    values_per_byte = 8 // bit_depth
    mask = (1 << bit_depth) - 1
    needed = width * channels
    byte_index = 0
    for _ in range(0, needed, values_per_byte):
        byte = row[byte_index]
        byte_index += 1
        for slot in range(values_per_byte):
            if len(samples) >= needed:
                break
            shift = 8 - bit_depth * (slot + 1)
            samples.append((byte >> shift) & mask)
    return samples[:needed]


def _assemble_rgba(
    scanlines: bytearray,
    width: int,
    height: int,
    bit_depth: int,
    color_type: int,
    channels: int,
    palette: list[tuple[int, int, int]] | None,
    trns: bytes | None,
    label: str,
) -> bytes:
    row_bytes = (width * bit_depth * channels + 7) // 8
    max_value = (1 << bit_depth) - 1
    out = bytearray(width * height * 4)

    def to_u8(sample: int) -> int:
        if bit_depth == 8:
            return sample
        if bit_depth == 16:
            return (sample * 255 + 32767) // 65535
        return (sample * 255 + max_value // 2) // max_value

    for y in range(height):
        row = scanlines[y * row_bytes : (y + 1) * row_bytes]
        samples = _unpack_samples(bytes(row), width, bit_depth, channels)
        row_out_offset = y * width * 4
        for x in range(width):
            base = x * channels
            out_offset = row_out_offset + x * 4
            if color_type == 0:  # grayscale
                gray_raw = samples[base]
                gray = to_u8(gray_raw)
                alpha = 0 if trns is not None and _gray_key(trns, bit_depth) == gray_raw else 255
                out[out_offset : out_offset + 4] = bytes((gray, gray, gray, alpha))
            elif color_type == 2:  # truecolor
                r_raw, g_raw, b_raw = samples[base], samples[base + 1], samples[base + 2]
                alpha = 255
                if trns is not None:
                    key = _rgb_key(trns, bit_depth)
                    if key == (r_raw, g_raw, b_raw):
                        alpha = 0
                out[out_offset : out_offset + 4] = bytes(
                    (to_u8(r_raw), to_u8(g_raw), to_u8(b_raw), alpha)
                )
            elif color_type == 3:  # palette
                assert palette is not None  # guaranteed by decode_png's own check above
                index = samples[base]
                if index >= len(palette):
                    raise PngError(f"{label}: palette index {index} out of range")
                r, g, b = palette[index]
                alpha = trns[index] if trns is not None and index < len(trns) else 255
                out[out_offset : out_offset + 4] = bytes((r, g, b, alpha))
            elif color_type == 4:  # grayscale + alpha
                gray = to_u8(samples[base])
                alpha = to_u8(samples[base + 1])
                out[out_offset : out_offset + 4] = bytes((gray, gray, gray, alpha))
            else:  # color_type == 6: truecolor + alpha
                r, g, b, a = (
                    samples[base],
                    samples[base + 1],
                    samples[base + 2],
                    samples[base + 3],
                )
                out[out_offset : out_offset + 4] = bytes((to_u8(r), to_u8(g), to_u8(b), to_u8(a)))
    return bytes(out)


def _gray_key(trns: bytes, bit_depth: int) -> int:
    del bit_depth  # tRNS for grayscale is always a big-endian 16-bit sample value (spec §11.3.2)
    return struct.unpack(">H", trns[:2])[0] if len(trns) >= 2 else -1


def _rgb_key(trns: bytes, bit_depth: int) -> tuple[int, int, int]:
    del bit_depth
    if len(trns) < 6:
        return (-1, -1, -1)
    r, g, b = struct.unpack(">HHH", trns[:6])
    return (r, g, b)
