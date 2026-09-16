"""Palette, material values and light conventions, shared by every script here.

The numbers come from the game's style bible (docs/art/stilbibel.md) and the
look-dev spike that ADR-0014 was decided on; they are repeated here rather than
imported so this directory is self-contained and can be dropped into a repo.
No bpy import.
"""
import json
import math
import os
import struct
import zlib

import numpy as np


def stable_seed(base, name):
    """Per-material seed that is the same in every process.

    Python's hash() of a string is salted per interpreter start, so a seed
    derived from it gave every run a different detail pattern (scars, blotches,
    grain) even with unchanged code, and no two runs could be compared.
    """
    return base + zlib.crc32(name.encode("utf-8")) % 10000


LUMA = np.array([0.2126, 0.7152, 0.0722])

# --------------------------------------------------------------- colours ---
VOID = "#06070A"
AMBIENT = {"sky": "#1C2438", "ground": "#110D0B", "intensity": 0.35}
MOON = {"dir": (-0.35, 0.5, -0.8), "color": "#9AB0D8", "intensity": 0.35, "angle_deg": 2.0}

# Albedo / roughness / metalness exactly as the style bible lists them.
MATERIALS = {
    "floor_stone": dict(albedo="#33363D", r=0.85, m=0.0),
    "grout":       dict(albedo="#1A1C21", r=0.95, m=0.0),
    "pillar":      dict(albedo="#3E4047", r=0.75, m=0.0),
    "altar":       dict(albedo="#2A2528", r=0.60, m=0.0),
    "cloak":       dict(albedo="#24505C", r=0.90, m=0.0),
    "hood_inside": dict(albedo="#0A0C0E", r=0.90, m=0.0),
    "mask":        dict(albedo="#CFC3A8", r=0.60, m=0.0),
    "staff_wood":  dict(albedo="#4A311E", r=0.70, m=0.0),
    "imp_skin":    dict(albedo="#7A5231", r=0.55, m=0.0),
    "horn":        dict(albedo="#C9BBA0", r=0.60, m=0.0),
    "brute_flesh": dict(albedo="#5E2B25", r=0.60, m=0.0),
    "plates":      dict(albedo="#3B3A3E", r=0.40, m=0.0),
    # Round 3: claws get their own material instead of reusing "horn" --
    # paler, glossier (lower baseline roughness), see texgen_r3.py.
    "claw_nail":   dict(albedo="#D9CDBE", r=0.34, m=0.0),
}

# Emissive meshes: body colour, HDR multiplier, optional hot core.
EMISSIVE = {
    "em_orb": dict(color="#7FE3FF", mult=4.0, core=None),
    "em_eye": dict(color="#FF6A2A", mult=3.0, core=None),
}

# Light colours from the style bible's light table.
LIGHT_COLORS = dict(moon="#9AB0D8", torch="#FF9A4A", candle="#FFC07A", orb="#7FE3FF",
                    ember="#FF6A2A", ritual="#8A5CFF")

# ------------------------------------------------------- light conventions ---
# Design units from the look spike; light_scale is its final calibrated value,
# the one that puts the floor's display median at 0.18 for the realistic look.
UNITS = dict(k_point=0.025330295910584444, k_sun=0.3183098861837907, k_world=1.0)
LIGHT_SCALE = 8.166790639311202
POINT_SOFT_RADIUS = 0.1

# Render / post settings, identical to the look spike's "realistic" look.
POST = dict(view_transform="Khronos PBR Neutral", look="None", rough_min=0.25,
            bloom_threshold=1.0, bloom_smoothness=0.5, bloom_strength=0.08,
            bloom_size=0.1, bloom_quality="High", samples=48, filter=1.5)

# Texture snapshot: material key -> texture id under generated/.
MATERIAL_TEXTURE_MAP = {
    "floor_stone": "floor_tiles",
    "grout": "grout",
    "pillar": "pillar_stone",
    "altar": "altar_basalt",
    "cloak": "cloak_fabric",
    "mask": "bone_mask",
    "staff_wood": "staff_wood",
    "imp_skin": "imp_skin",
    "brute_flesh": "brute_flesh",
    "plates": "shoulder_plates",
    # Round 3: horn and claw both get a real generated texture (texgen_r3.py)
    # instead of a flat style-bible colour -- "horn" was the last actor
    # material with a perfectly constant roughness/metallic field.
    "horn": "horn",
    "claw_nail": "claw_nail",
}
# No texture was delivered for this one; it stays a flat style-bible colour
# (a dark cavity behind the mask, never a lit, texture-scale surface).
UNMAPPED_MATERIALS = ("hood_inside",)
TEXTURE_RESOLUTION = 1024
UV_NAME = "uv_tex"


# --------------------------------------------------------------- helpers ---
def hex_to_srgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def srgb_to_linear(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(np.asarray(c, dtype=np.float64), 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1.0 / 2.4) - 0.055)


def hex_lin(h):
    return tuple(float(v) for v in srgb_to_linear(hex_to_srgb(h)))


def rgba(h, scale=1.0):
    return tuple(v * scale for v in hex_lin(h)) + (1.0,)


def light_placement(pos, radius):
    """Design falloff 1/(1 + d^2) emulated with Eevee's 1/d^2: a light at height
    h is placed at sqrt(h^2 + 1). Without this, low lights burn a singular hot
    spot into the floor (a correction the look spike had to make)."""
    x, y, z = pos
    h = max(z, 0.0)
    return (x, y, math.sqrt(h * h + 1.0)), math.sqrt(radius * radius + 1.0)


def load_tile_size(snapshot_generated_dir, tex_id):
    """Tile size in metres, read from the snapshot's own per-material JSON."""
    path = os.path.join(snapshot_generated_dir, tex_id, tex_id + ".json")
    with open(path, "r", encoding="utf-8") as fh:
        d = json.load(fh)
    w, h = d["tile_size_m"]
    return float(w), float(h)


# ------------------------------------------------------------------- I/O ---
def write_png(path, arr):
    """Deterministic 8-bit PNG writer. arr: HxWx{3,4} uint8."""
    arr = np.ascontiguousarray(arr, dtype=np.uint8)
    h, w, c = arr.shape
    color_type = {3: 2, 4: 6}[c]
    raw = np.concatenate([np.zeros((h, 1), np.uint8), arr.reshape(h, w * c)], axis=1)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, color_type, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw.tobytes(), 6))
    png += chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(png)


def read_png(path):
    """Minimal 8-bit PNG reader (the writer's counterpart) -> HxWx3 uint8."""
    with open(path, "rb") as fh:
        data = fh.read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", path
    pos, idat, meta = 8, b"", None
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        if tag == b"IHDR":
            meta = struct.unpack(">IIBBBBB", body)
        elif tag == b"IDAT":
            idat += body
        pos += 12 + ln
    w, h, depth, ctype = meta[0], meta[1], meta[2], meta[3]
    assert depth == 8, "only 8-bit PNGs"
    nch = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(idat)
    stride = w * nch
    out = np.zeros((h, stride), dtype=np.uint8)
    prev = np.zeros(stride, dtype=np.uint8)
    p = 0
    for y in range(h):
        ft = raw[p]
        line = np.frombuffer(raw[p + 1:p + 1 + stride], dtype=np.uint8).astype(np.int32)
        p += 1 + stride
        cur = np.zeros(stride, dtype=np.int32)
        pr = prev.astype(np.int32)
        if ft == 0:
            cur = line
        elif ft == 1:
            for i in range(stride):
                cur[i] = (line[i] + (cur[i - nch] if i >= nch else 0)) & 0xFF
        elif ft == 2:
            cur = (line + pr) & 0xFF
        elif ft == 3:
            for i in range(stride):
                a = cur[i - nch] if i >= nch else 0
                cur[i] = (line[i] + ((a + pr[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(stride):
                a = cur[i - nch] if i >= nch else 0
                b = pr[i]
                c = pr[i - nch] if i >= nch else 0
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                cur[i] = (line[i] + pred) & 0xFF
        out[y] = cur.astype(np.uint8)
        prev = out[y]
    img = out.reshape(h, w, nch)
    return img[..., :3] if nch >= 3 else np.repeat(img, 3, axis=2)


def save_json(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)
