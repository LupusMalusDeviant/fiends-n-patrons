"""Reads the size and pixel layout of an embedded PNG or JPEG from its header alone.

Standard library only. Nothing is decoded: a 8192x8192 JPEG costs a few hundred bytes of
reading, not 268 MB of pixels. That is all the budget check needs (size, channels, format), and
it keeps the check fast on raw generator output with several such textures.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# PNG colour type -> channel count (palette images count as 3 channels, 4 with a tRNS chunk).
_PNG_CHANNELS = {0: 1, 2: 3, 3: 3, 4: 2, 6: 4}

# JPEG start-of-frame markers carrying the frame size (every SOFn except DHT C4, JPG C8, DAC CC).
_JPEG_SOF_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
_JPEG_PROGRESSIVE_MARKERS = {0xC2, 0xC6, 0xCA, 0xCE}
# Markers without a length field: TEM, RST0-7, SOI, EOI.
_JPEG_STANDALONE_MARKERS = {0x01, *range(0xD0, 0xD8), 0xD8, 0xD9}


class ImageHeaderError(ValueError):
    """The bytes are not a PNG or JPEG this reader can size."""


@dataclass(frozen=True)
class ImageHeader:
    """Size and layout of one image, read from its header."""

    mime_type: str
    width: int
    height: int
    channels: int
    bit_depth: int
    progressive: bool


def sniff_mime_type(data: bytes) -> str | None:
    """Returns the MIME type implied by the magic bytes, or `None` if neither PNG nor JPEG."""
    if data.startswith(PNG_SIGNATURE):
        return "image/png"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    return None


def _png_has_chunk_before_idat(data: bytes, wanted: bytes) -> bool:
    """Walks the chunk list (tRNS must precede the first IDAT) without reading pixel data."""
    offset = 8
    while offset + 8 <= len(data):
        length, tag = struct.unpack_from(">I4s", data, offset)
        if tag == wanted:
            return True
        if tag in (b"IDAT", b"IEND"):
            return False
        offset += 12 + length
    return False


def read_png_header(data: bytes) -> ImageHeader:
    if not data.startswith(PNG_SIGNATURE):
        raise ImageHeaderError("missing PNG signature")
    if len(data) < 33:
        raise ImageHeaderError("PNG shorter than signature plus IHDR chunk")
    length, tag = struct.unpack_from(">I4s", data, 8)
    if tag != b"IHDR" or length != 13:
        raise ImageHeaderError("first PNG chunk is not a 13-byte IHDR")
    width, height, bit_depth, color_type = struct.unpack_from(">IIBB", data, 16)
    if color_type not in _PNG_CHANNELS:
        raise ImageHeaderError(f"unknown PNG colour type {color_type}")
    if width == 0 or height == 0:
        raise ImageHeaderError("PNG declares zero width or height")
    channels = _PNG_CHANNELS[color_type]
    if color_type == 3 and _png_has_chunk_before_idat(data, b"tRNS"):
        channels = 4
    return ImageHeader("image/png", width, height, channels, bit_depth, progressive=False)


def read_jpeg_header(data: bytes) -> ImageHeader:
    if not data.startswith(b"\xff\xd8"):
        raise ImageHeaderError("missing JPEG start-of-image marker")
    offset = 2
    size = len(data)
    while offset < size:
        if data[offset] != 0xFF:
            raise ImageHeaderError(f"expected a JPEG marker at byte {offset}")
        # Any number of 0xFF fill bytes may precede the marker code.
        while offset < size and data[offset] == 0xFF:
            offset += 1
        if offset >= size:
            break
        marker = data[offset]
        offset += 1
        if marker in _JPEG_STANDALONE_MARKERS:
            continue
        if marker == 0xDA:  # start of scan before any frame header
            break
        if offset + 2 > size:
            break
        (segment_length,) = struct.unpack_from(">H", data, offset)
        if segment_length < 2:
            raise ImageHeaderError(f"JPEG segment 0x{marker:02X} declares length {segment_length}")
        if marker in _JPEG_SOF_MARKERS:
            if offset + 8 > size:
                break
            bit_depth, height, width, components = struct.unpack_from(">BHHB", data, offset + 2)
            if width == 0 or height == 0:
                raise ImageHeaderError("JPEG frame declares zero width or height")
            return ImageHeader(
                "image/jpeg",
                width,
                height,
                components,
                bit_depth,
                progressive=marker in _JPEG_PROGRESSIVE_MARKERS,
            )
        offset += segment_length
    raise ImageHeaderError("no JPEG start-of-frame segment found")


def read_image_header(data: bytes) -> ImageHeader:
    """Sizes a PNG or JPEG by its magic bytes (a declared `mimeType` is checked separately)."""
    mime_type = sniff_mime_type(data)
    if mime_type == "image/png":
        return read_png_header(data)
    if mime_type == "image/jpeg":
        return read_jpeg_header(data)
    raise ImageHeaderError("neither a PNG nor a JPEG (unknown magic bytes)")
