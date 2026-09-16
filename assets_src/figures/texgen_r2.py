"""Round-2 actor texture generator: procedural mid-scale detail, no bpy needed.

Round 1 delivered flat actor textures (measured imp skin albedo contrast 1.12:1,
normal slopes averaging 0.33 degrees -- next to no relief). This regenerates the
six actor-scope materials (imp_skin, brute_flesh, cloak_fabric, bone_mask,
staff_wood, shoulder_plates) with real 10-30 cm features: skin wrinkles and
pores, scars, flesh mottling, fabric weave and wear, bone cracks, wood grain --
while keeping each material's MEAN colour inside the style bible's actor limits
(low-to-medium saturation, low-to-medium value) and only raising the variation
around it.

Everything else in the snapshot (floor, grout, pillar, altar -- and the props
that already read fine, the orb material is emissive/no texture) is copied
through unchanged so build_character_r2.py can point --tex-dir at ONE self
contained folder and get every material the stage needs.

Run with plain python (numpy only, no Blender):
    python texgen_r2.py --src <round1 snapshot>/generated --out <round2 dir>/generated
"""
import argparse
import json
import math
import os
import shutil
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import normalmap as NM  # noqa: E402
import palette as P  # noqa: E402

RES = P.TEXTURE_RESOLUTION  # 1024
ACTORS = ("imp_skin", "brute_flesh", "cloak_fabric", "bone_mask", "staff_wood",
          "shoulder_plates")


# ------------------------------------------------------------ tileable noise ---
def _wrap_upsample(small, out_h, out_w):
    """Bilinear upsample of a small periodic grid to out_h x out_w, seamless
    across the wrap (no clamped edge -- the last column blends into the first)."""
    sh, sw = small.shape
    ys = np.linspace(0.0, sh, out_h, endpoint=False)
    xs = np.linspace(0.0, sw, out_w, endpoint=False)
    y0 = np.floor(ys).astype(int) % sh
    x0 = np.floor(xs).astype(int) % sw
    y1 = (y0 + 1) % sh
    x1 = (x0 + 1) % sw
    fy = (ys - np.floor(ys))[:, None]
    fx = (xs - np.floor(xs))[None, :]
    top = small[y0][:, x0] * (1 - fx) + small[y0][:, x1] * fx
    bot = small[y1][:, x0] * (1 - fx) + small[y1][:, x1] * fx
    return top * (1 - fy) + bot * fy


def value_noise(h, w, rng, octaves):
    """Tileable multi-octave value noise, standardised to unit RMS (not peak) so
    the *typical* pixel carries real variation instead of a handful of outliers
    setting the scale -- normalising by the max flattened the first attempt at
    this (contrast barely moved even though the field "looked" noisy).

    octaves: list of (cells, amplitude) -- `cells` low-res grid cells per axis.
    """
    acc = np.zeros((h, w), dtype=np.float64)
    for cells, amp in octaves:
        cells = max(int(cells), 2)
        small = rng.normal(size=(cells, cells))
        acc += _wrap_upsample(small, h, w) * amp
    s = acc.std()
    return acc / s if s > 1e-9 else acc


def blotches(h, w, rng, n, radius_px, softness=0.5, seed_jitter=True):
    """Soft circular blobs at random tileable positions -> field in [0, 1]."""
    field = np.zeros((h, w), dtype=np.float64)
    yy, xx = np.mgrid[0:h, 0:w]
    for _ in range(n):
        cy, cx = rng.uniform(0, h), rng.uniform(0, w)
        r = radius_px * rng.uniform(0.6, 1.4)
        for oy in (-h, 0, h):
            for ox in (-w, 0, w):
                dy, dx = yy - (cy + oy), xx - (cx + ox)
                d = np.sqrt(dy * dy + dx * dx)
                if d.min() > r * (1 + softness):
                    continue
                t = np.clip(d / max(r, 1e-6), 0.0, 1.0)
                field = np.maximum(field, 1.0 - t * t * (3 - 2 * t))
    return field


def streaks(h, w, rng, n, length_px, width_px):
    """Thin random line strokes (scars, scratches, wood grain flecks)."""
    field = np.zeros((h, w), dtype=np.float64)
    yy, xx = np.mgrid[0:h, 0:w]
    for _ in range(n):
        cy, cx = rng.uniform(0, h), rng.uniform(0, w)
        ang = rng.uniform(0, math.pi)
        length = length_px * rng.uniform(0.6, 1.4)
        dy, dx = math.sin(ang) * length / 2, math.cos(ang) * length / 2
        for oy in (-h, 0, h):
            for ox in (-w, 0, w):
                p0 = np.array([cy + oy - dy, cx + ox - dx])
                p1 = np.array([cy + oy + dy, cx + ox + dx])
                seg = p1 - p0
                seg_len2 = float(seg @ seg) or 1e-9
                py, px = yy - p0[0], xx - p0[1]
                t = np.clip((py * seg[0] + px * seg[1]) / seg_len2, 0.0, 1.0)
                nearest_y, nearest_x = p0[0] + t * seg[0], p0[1] + t * seg[1]
                d = np.sqrt((yy - nearest_y) ** 2 + (xx - nearest_x) ** 2)
                if d.min() > width_px * 3:
                    continue
                w_ = np.clip(1.0 - d / width_px, 0.0, 1.0)
                field = np.maximum(field, w_)
    return field


def voronoi_cracks(h, w, rng, n_points, thickness_px):
    """Cell-boundary crack network: |dist to nearest - dist to 2nd nearest|
    small -> on a boundary. Tileable via the 3x3 point replication."""
    pts = rng.uniform(0, 1, size=(n_points, 2)) * [h, w]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    best1 = np.full((h, w), np.inf)
    best2 = np.full((h, w), np.inf)
    for oy in (-h, 0, h):
        for ox in (-w, 0, w):
            for py, px in pts:
                d = np.sqrt((yy - (py + oy)) ** 2 + (xx - (px + ox)) ** 2)
                closer = d < best1
                best2 = np.where(closer, best1, np.minimum(best2, d))
                best1 = np.where(closer, d, best1)
    gap = best2 - best1
    return np.clip(1.0 - gap / thickness_px, 0.0, 1.0)


# ------------------------------------------------------------------ stats ---
def albedo_contrast(rgb_u8):
    """Michelson-ish contrast used in the round-1 report: p95 luma / p5 luma."""
    luma = rgb_u8.astype(np.float64) @ P.LUMA
    p5, p95 = np.percentile(luma, [5, 95])
    return float(p95 / max(p5, 1e-6))


def normal_slope_stats(normal_u8):
    n = NM.decode_normal(normal_u8)
    deg = NM.slope_degrees(n)
    return dict(mean_deg=float(deg.mean()), p95_deg=float(np.percentile(deg, 95)),
                max_deg=float(deg.max()))


# -------------------------------------------------------------- materials ---
def _mean_srgb(hexcolor):
    return np.array([int(hexcolor.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)],
                     dtype=np.float64)


def midscale_cells(tile_m, res, lo_m=0.10, hi_m=0.30):
    """Low-res noise grid sizes whose upsampled wavelength lands in [lo_m, hi_m]
    of world size. The style bible is explicit that fine noise does not belong
    in basecolor or normal maps (it flickers as specular aliasing at the
    gameplay camera); every octave below stays in this mid-scale band -- this
    replaces an earlier attempt that used sub-centimetre "pore" octaves and
    barely moved the measured contrast at all.
    """
    lo_wav_px = (lo_m / tile_m) * res
    hi_wav_px = (hi_m / tile_m) * res
    lo_cells = max(2, int(round(res / hi_wav_px)))
    hi_cells = max(lo_cells + 1, int(round(res / lo_wav_px)))
    return lo_cells, hi_cells


def generate(kind, mean_hex, tile_m, rng, res=RES):
    """Build (basecolor uint8 HxWx3, height_m HxW, roughness01 HxW, ao01 HxW)."""
    texel = tile_m / res
    mean = _mean_srgb(mean_hex)
    h = w = res
    lo, hi = midscale_cells(tile_m, res)
    mid_octaves = [(lo, 1.0), ((lo + hi) // 2, 0.7), (hi, 0.45)]
    fine_octave = [(int(hi * 1.3), 0.25)]  # a little extra richness, still cm-scale

    if kind == "imp_skin":
        wrinkles = value_noise(h, w, rng, mid_octaves + fine_octave)
        mottle = value_noise(h, w, rng, [(max(lo // 2, 2), 1.0)])
        scars = streaks(h, w, rng, n=3, length_px=res * 0.16, width_px=res * 0.006)
        variation = 0.16 * wrinkles + 0.09 * mottle
        rgb = mean[None, None, :] * (1.0 + variation[..., None])
        rgb -= scars[..., None] * 22.0
        height = 0.0011 * wrinkles + 0.0007 * mottle - 0.0022 * scars
        rough = 0.55 + 0.10 * mottle - 0.15 * scars
        ao = 1.0 - 0.20 * np.clip(-wrinkles, 0, 1) - 0.35 * scars

    elif kind == "brute_flesh":
        wrinkles = value_noise(h, w, rng, mid_octaves + fine_octave)
        mottle = value_noise(h, w, rng, [(max(lo // 2, 2), 1.0)])
        scars = streaks(h, w, rng, n=5, length_px=res * 0.20, width_px=res * 0.010)
        variation = 0.16 * wrinkles + 0.18 * mottle
        rgb = mean[None, None, :] * (1.0 + variation[..., None])
        rgb -= scars[..., None] * 28.0
        height = 0.0016 * wrinkles + 0.0018 * mottle - 0.0032 * scars
        rough = 0.55 + 0.12 * mottle - 0.18 * scars
        ao = 1.0 - 0.25 * np.clip(-wrinkles, 0, 1) - 0.40 * scars

    elif kind == "cloak_fabric":
        yy, xx = np.mgrid[0:h, 0:w]
        # A coarse rib/weave rather than literal per-thread pitch (sub-mm thread
        # detail would alias at the gameplay camera): about 3.5 cm, still mid
        # scale, reads as woven structure rather than a flat sheet.
        rib_freq = tile_m / 0.035
        warp = 0.5 + 0.5 * np.sin(2 * math.pi * xx / (w / rib_freq))
        weft = 0.5 + 0.5 * np.sin(2 * math.pi * yy / (h / rib_freq))
        weave = 0.6 * warp + 0.4 * weft
        weave = weave - weave.mean()
        wrinkle = value_noise(h, w, rng, mid_octaves)
        wear = blotches(h, w, rng, n=6, radius_px=res * 0.09, softness=0.8)
        variation = 0.10 * weave + 0.08 * wrinkle - 0.14 * wear
        rgb = mean[None, None, :] * (1.0 + variation[..., None])
        height = 0.00045 * weave + 0.00035 * wrinkle - 0.0009 * wear
        rough = 0.90 - 0.20 * wear + 0.05 * wrinkle
        ao = 1.0 - 0.15 * (weave < -0.3) - 0.25 * wear

    elif kind == "bone_mask":
        cracks = voronoi_cracks(h, w, rng, n_points=14, thickness_px=res * 0.006)
        pits = value_noise(h, w, rng, mid_octaves)
        variation = 0.10 * pits - 0.18 * cracks
        rgb = mean[None, None, :] * (1.0 + variation[..., None])
        height = 0.0012 * pits - 0.0030 * cracks
        rough = 0.55 + 0.10 * pits + 0.15 * cracks
        ao = 1.0 - 0.45 * cracks - 0.15 * np.clip(-pits, 0, 1)

    elif kind == "staff_wood":
        yy, xx = np.mgrid[0:h, 0:w]
        grain_freq = tile_m / 0.045  # ~4.5 cm ring pitch, mid-scale
        warp_noise = value_noise(h, w, rng, [(max(lo, 3), 1.0)])
        grain = 0.5 + 0.5 * np.sin(2 * math.pi * yy / (h / grain_freq) + 0.6 * warp_noise)
        grain = grain - grain.mean()
        flecks = value_noise(h, w, rng, mid_octaves)
        scuffs = blotches(h, w, rng, n=5, radius_px=res * 0.05, softness=0.6)
        variation = 0.18 * grain + 0.08 * flecks - 0.14 * scuffs
        rgb = mean[None, None, :] * (1.0 + variation[..., None])
        height = 0.0009 * grain + 0.0005 * flecks - 0.0009 * scuffs
        rough = 0.65 - 0.10 * scuffs + 0.06 * flecks
        ao = 1.0 - 0.20 * scuffs

    elif kind == "shoulder_plates":
        scratches = streaks(h, w, rng, n=10, length_px=res * 0.14, width_px=res * 0.004)
        wear = blotches(h, w, rng, n=5, radius_px=res * 0.07, softness=0.7)
        pits = value_noise(h, w, rng, mid_octaves)
        variation = 0.09 * pits + 0.12 * scratches - 0.12 * wear
        rgb = mean[None, None, :] * (1.0 + variation[..., None])
        height = 0.0006 * pits + 0.0010 * scratches - 0.0014 * wear
        rough = 0.40 + 0.25 * wear - 0.10 * scratches
        ao = 1.0 - 0.20 * scratches - 0.25 * wear

    else:
        raise ValueError(kind)

    rgb = np.clip(rgb, 0.0, 255.0)
    rough = np.clip(rough, 0.05, 1.0)
    ao = np.clip(ao, 0.0, 1.0)
    return np.round(rgb).astype(np.uint8), height, rough, ao, texel


def build_orm(rough, ao, metallic=0.0):
    h, w = rough.shape
    orm = np.zeros((h, w, 3), dtype=np.uint8)
    orm[..., 0] = np.round(ao * 255.0).astype(np.uint8)
    orm[..., 1] = np.round(rough * 255.0).astype(np.uint8)
    orm[..., 2] = int(round(metallic * 255.0))
    return orm


def process_material(mat_id, spec_row, src_dir, out_dir, rng, report):
    mat_dir = os.path.join(out_dir, mat_id)
    os.makedirs(mat_dir, exist_ok=True)
    tile_m = spec_row["tile_size_m"][0]
    mean_hex = spec_row["basecolor"]

    before = None
    src_base = os.path.join(src_dir, mat_id, "%s_basecolor.png" % mat_id)
    src_norm = os.path.join(src_dir, mat_id, "%s_normal.png" % mat_id)
    if os.path.exists(src_base) and os.path.exists(src_norm):
        before = dict(albedo_contrast=albedo_contrast(P.read_png(src_base)),
                      normal=normal_slope_stats(P.read_png(src_norm)))

    rgb, height, rough, ao, texel = generate(mat_id, mean_hex, tile_m, rng)
    normal = NM.encode_normal(NM.height_to_normal(height, (texel, texel)))
    orm = build_orm(rough, ao, metallic=spec_row.get("metallic", 0.0))

    P.write_png(os.path.join(mat_dir, "%s_basecolor.png" % mat_id), rgb)
    P.write_png(os.path.join(mat_dir, "%s_normal.png" % mat_id), normal)
    P.write_png(os.path.join(mat_dir, "%s_orm.png" % mat_id), orm)
    with open(os.path.join(mat_dir, "%s.json" % mat_id), "w", encoding="utf-8") as fh:
        json.dump(dict(spec_row, generator="texgen_r2", round=2), fh, indent=1, sort_keys=True)

    after = dict(albedo_contrast=albedo_contrast(rgb), normal=normal_slope_stats(normal))
    mean_rgb = rgb.reshape(-1, 3).mean(axis=0)
    report[mat_id] = dict(before=before, after=after,
                          mean_srgb_after=[round(float(v), 1) for v in mean_rgb],
                          mean_hex_target=mean_hex, tile_size_m=tile_m)
    print("TEX %-16s contrast %s -> %.3f  slope_mean %s -> %.3f deg" % (
        mat_id,
        ("%.3f" % before["albedo_contrast"]) if before else "n/a",
        after["albedo_contrast"],
        ("%.3f" % before["normal"]["mean_deg"]) if before else "n/a",
        after["normal"]["mean_deg"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="round-1 snapshot generated/ dir")
    ap.add_argument("--out", required=True, help="round-2 output generated/ dir")
    ap.add_argument("--seed", type=int, default=20260916)
    args = ap.parse_args()

    with open(os.path.join(args.src, "..", "catalog.json"), "r", encoding="utf-8") as fh:
        catalog = json.load(fh)
    by_id = {m["id"]: m for m in catalog["materials"]}

    os.makedirs(args.out, exist_ok=True)
    # Copy every material through unchanged first (floor, grout, pillar, altar,
    # bronze, candle wax, ruin wall -- the stage needs the full set from one
    # --tex-dir), then overwrite the six actor materials with regenerated ones.
    for entry in sorted(os.listdir(args.src)):
        s = os.path.join(args.src, entry)
        d = os.path.join(args.out, entry)
        if os.path.isdir(s):
            if os.path.exists(d):
                shutil.rmtree(d)
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)

    report = {}
    for mat_id in ACTORS:
        rng = np.random.default_rng(P.stable_seed(args.seed, mat_id))
        spec_row = dict(by_id[mat_id])
        if mat_id == "imp_skin":
            # Round 2 also darkens the imp: #7A7068 (value 48%) read too pale
            # against the arena floor (value 24%). #5A534D keeps the same warm
            # grey-brown undertone (saturation ~14%, unchanged) and lands the
            # value at ~35%, inside the style bible's "niedrig-mittel" band for
            # figures while still separating from the floor by value, not rim
            # light (ADR-0014 forbids rim light as a look feature).
            spec_row["basecolor"] = "#5A534D"
        process_material(mat_id, spec_row, args.src, args.out, rng, report)

    catalog2 = json.loads(json.dumps(catalog))
    for m in catalog2["materials"]:
        if m["id"] in report:
            m["basecolor"] = report[m["id"]]["mean_hex_target"]
            m["scene_color"] = report[m["id"]]["mean_hex_target"]
            m["note"] = (m.get("note", "") + " Round 2: procedurally regenerated "
                        "(texgen_r2) with mid-scale detail; mean colour kept "
                        "inside the actor value/saturation limits.").strip()
    with open(os.path.join(args.out, "..", "catalog.json"), "w", encoding="utf-8") as fh:
        json.dump(catalog2, fh, indent=1)

    P.save_json(os.path.join(args.out, "..", "texgen_r2_report.json"), report)
    print("TEXGEN R2 OK ->", args.out)


if __name__ == "__main__":
    main()
