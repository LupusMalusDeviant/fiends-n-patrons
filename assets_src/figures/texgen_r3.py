"""Round 3 texture generator: geometry-driven wear on top of round 2's
procedural base, plus two new material kinds (horn, claw_nail) round 2 left
flat.

Round 2 (texgen_r2.py) gave every actor material real mid-scale noise, which
fixed "flat colour" but not "noise instead of a story": nothing in that
noise field knows where the mesh actually has an edge or a crease. This
module adds that: `apply_geo_wear` takes curvature and ambient-occlusion
masks BAKED FROM THE REAL MESH (geomasks.py, run inside the Blender build
script once the character exists) and uses them to place bright worn edges
at convex ridges, dark grime in concave AO pockets, and to stop roughness
AND metallic from being flat fields -- "plates" (the brute's armour) gets a
real, geometry-driven metallic channel: scraped-bare steel at the worn
edges, painted/oxidised (metallic 0) everywhere else.

No bpy import: the wear math is plain numpy given already-baked mask arrays,
so it can run standalone (this file) or inside the Blender process without
caring which. The reusable low-level noise primitives (value_noise, streaks,
blotches, voronoi_cracks, midscale_cells, build_orm, albedo_contrast,
normal_slope_stats) come straight from texgen_r2 -- not reimplemented -- so
round 2's own six materials keep the exact base texgen_r2.py already ships
and only gain the wear layer on top.
"""
import json
import math
import os

import numpy as np

import normalmap as NM
import palette as P
import texgen_r2 as T2

RES = P.TEXTURE_RESOLUTION
NEW_KINDS = ("horn", "claw_nail")


# --------------------------------------------------------- new base kinds ---
def _generate_horn(mean_hex, tile_m, rng, res=RES):
    h = w = res
    mean = T2._mean_srgb(mean_hex)
    lo, hi = T2.midscale_cells(tile_m, res)
    ridges = T2.value_noise(h, w, rng, [(lo, 1.0), ((lo + hi) // 2, 0.6)])
    fine = T2.value_noise(h, w, rng, [(hi, 0.35)])
    cracks = T2.voronoi_cracks(h, w, rng, n_points=6, thickness_px=res * 0.004)
    # A fibrous growth gradient along V (whichever way this island's V axis
    # actually runs -- both ends of a horn/tooth are dark keratin, so a
    # symmetric gradient reads correctly either way instead of assuming V=0
    # is the base).
    yy = np.linspace(0.0, 1.0, h)[:, None] * np.ones((1, w))
    tip_gradient = 1.0 - 4.0 * (yy - 0.5) ** 2  # 0 at both ends, 1 at the middle band
    variation = 0.14 * ridges + 0.06 * fine - 0.10 * cracks
    rgb = mean[None, None, :] * (1.0 + variation[..., None])
    rgb += tip_gradient[..., None] * 10.0
    height = 0.0010 * ridges + 0.0004 * fine - 0.0020 * cracks
    rough = 0.55 - 0.10 * tip_gradient + 0.08 * cracks
    ao = 1.0 - 0.30 * cracks
    return (np.clip(np.round(rgb), 0, 255).astype(np.uint8), height,
           np.clip(rough, 0.05, 1.0), np.clip(ao, 0.0, 1.0), tile_m / res)


def _generate_claw_nail(mean_hex, tile_m, rng, res=RES):
    h = w = res
    mean = T2._mean_srgb(mean_hex)
    lo, hi = T2.midscale_cells(tile_m, res)
    ridges = T2.value_noise(h, w, rng, [(lo, 1.0), (hi, 0.5)])
    scuffs = T2.streaks(h, w, rng, n=4, length_px=res * 0.10, width_px=res * 0.006)
    yy = np.linspace(0.0, 1.0, h)[:, None] * np.ones((1, w))
    polish = 1.0 - 4.0 * (yy - 0.5) ** 2  # a glossier band along the same axis
    variation = 0.08 * ridges - 0.10 * scuffs
    rgb = mean[None, None, :] * (1.0 + variation[..., None])
    rgb += polish[..., None] * 8.0
    height = 0.0006 * ridges - 0.0012 * scuffs
    # Nails are noticeably glossier than horn: a lower baseline roughness,
    # driven further down at the polished band.
    rough = 0.34 - 0.14 * polish + 0.10 * scuffs
    ao = 1.0 - 0.20 * scuffs
    return (np.clip(np.round(rgb), 0, 255).astype(np.uint8), height,
           np.clip(rough, 0.05, 1.0), np.clip(ao, 0.0, 1.0), tile_m / res)


def generate_base(kind, mean_hex, tile_m, rng, res=RES):
    """(rgb u8, height_m, roughness01, ao01_synth, texel_m) for any material
    this round touches -- round 2's six via texgen_r2.generate unchanged, or
    one of the two new keratin kinds."""
    if kind in T2.ACTORS:
        return T2.generate(kind, mean_hex, tile_m, rng, res=res)
    if kind == "horn":
        return _generate_horn(mean_hex, tile_m, rng, res=res)
    if kind == "claw_nail":
        return _generate_claw_nail(mean_hex, tile_m, rng, res=res)
    raise ValueError("texgen_r3: unknown material kind %r" % (kind,))


# ------------------------------------------------------------ resampling ---
def _resample_nearest(arr, h, w):
    if arr.shape[:2] == (h, w):
        return arr
    sh, sw = arr.shape[:2]
    ys = np.clip((np.arange(h) * sh / h).astype(int), 0, sh - 1)
    xs = np.clip((np.arange(w) * sw / w).astype(int), 0, sw - 1)
    return arr[ys][:, xs]


# ------------------------------------------------------------- geo wear ---
LEATHER_HEX = np.array([58.0, 40.0, 26.0])   # dark tanned-leather brown, straps/seams
DIRT_HEX = np.array([30.0, 24.0, 16.0])


def _strap_mask(h, w, rng, n=2, band_frac=0.09, angle_deg=28.0):
    """A couple of diagonal leather strap bands plus a thin stitched seam
    line down their centre -- UV-space texture detail (there is no separate
    strap geometry), which is exactly what round 3's brief asks for on the
    cloak: "Naehte und Riemen am Stoff" as a texture feature."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    a = math.radians(angle_deg)
    band = np.zeros((h, w), dtype=np.float64)
    seam = np.zeros((h, w), dtype=np.float64)
    for k in range(n):
        offset = (k + 0.5) / n * (h + w)
        d = (xx * math.cos(a) + yy * math.sin(a) + offset) % (0.5 * (h + w))
        width = band_frac * min(h, w)
        this_band = np.clip(1.0 - np.abs(d - width * 0.5) / (width * 0.5), 0.0, 1.0)
        this_seam = np.clip(1.0 - np.abs(d - width * 0.5) / (width * 0.06), 0.0, 1.0)
        band = np.maximum(band, this_band)
        seam = np.maximum(seam, this_seam)
    return np.clip(band, 0, 1), np.clip(seam, 0, 1)


def apply_geo_wear(kind, rgb_u8, height, rough, curvature01, ao01, rng,
                   metallic_base=0.0):
    """Blend mesh-driven curvature/AO wear onto a procedurally generated
    base. Returns (rgb u8, height_m, roughness01, metallic01 HxW array,
    stats dict) -- metallic is ALWAYS returned as a full HxW field (never a
    single flat number past this point), even where it stays uniformly at
    `metallic_base`, so build_orm always has real per-pixel data to encode.
    """
    h, w = rough.shape
    curvature01 = _resample_nearest(np.asarray(curvature01, dtype=np.float64), h, w)
    ao01 = _resample_nearest(np.asarray(ao01, dtype=np.float64), h, w)

    # Percentile-based thresholds, not fixed absolute ones: Cycles' 'AO' bake
    # type turned out to be lit by the scene world rather than a pure 0..1
    # geometric visibility fraction (measured directly -- even under a
    # plain white bake-only world it still came back with a mean around
    # 0.02-0.03 on this cast, not the ~0.85-0.95 a mostly-exposed figure
    # standing alone would suggest), so a fixed cutoff like "AO < 0.46 is a
    # crevice" silently classified 97-99% of the surface as one -- checked
    # directly (texgen_r3's own wear stats), not assumed fine because the
    # code ran. Anchoring "edge"/"crevice" to each mask's OWN percentile
    # distribution keeps the wear at the ACTUAL extremes of this material's
    # curvature/AO range regardless of what absolute scale that range sits
    # on, and self-corrects if a future Blender version's AO bake changes.
    # A material's UV islands are placed at real-world scale, not repacked
    # to fill the 0..1 tile, so a large fraction of the bake image can be
    # background outside any island -- Blender leaves those texels at the
    # image's plain initial fill (0.0), which is nothing like real "very
    # concave"/"very flat" data. Left in, that background dominated the
    # percentiles (measured: crevice_frac came back exactly 0.0 for two
    # different materials with the naive whole-image percentile, i.e. the
    # threshold had locked onto the background-vs-content boundary instead
    # of real variation WITHIN the content). Percentiles below are taken
    # over the painted pixels only.
    curv_painted = curvature01[curvature01 > 1e-6]
    ao_painted = ao01[ao01 > 1e-6]
    curv_hi = np.percentile(curv_painted, 92.0) if curv_painted.size else 1.0
    curv_lo = np.percentile(curv_painted, 55.0) if curv_painted.size else 0.0
    ao_lo = np.percentile(ao_painted, 20.0) if ao_painted.size else 0.0
    ao_hi = np.percentile(ao_painted, 60.0) if ao_painted.size else 1.0
    edge = np.clip((curvature01 - curv_lo) / max(curv_hi - curv_lo, 1e-6), 0.0, 1.0)
    crevice = np.clip((ao_hi - ao01) / max(ao_hi - ao_lo, 1e-6), 0.0, 1.0)
    # Background stays neutral (no wear) regardless of the formula above --
    # it is never sampled by the renderer, but keeping it inert avoids
    # baking a bright "edge" ring around every island's own boundary.
    edge = np.where(curvature01 > 1e-6, edge, 0.0)
    crevice = np.where(ao01 > 1e-6, crevice, 0.0)

    rgb = rgb_u8.astype(np.float64)
    polish = 16.0 * edge
    rgb = rgb + polish[..., None]
    rgb = rgb * (1.0 - 0.20 * crevice)[..., None] - DIRT_HEX[None, None, :] * (0.30 * crevice[..., None])

    metal = np.full((h, w), float(metallic_base), dtype=np.float64)
    ORGANIC_KINDS = ("imp_skin", "brute_flesh")
    if kind == "shoulder_plates":
        # Scraped-bare steel at worn edges: this is the one material where
        # metallic actually needs to be a field, not a slightly-varying
        # number -- most of the plate stays painted/oxidised (0), the
        # scratched high points go up to ~0.5. Round 3a's edge-driven
        # roughness DROP (-0.05) on top of an already-fairly-low base read
        # as a single glued-on glossy disc under this scene's point lights
        # -- round 3b raises the base and floor substantially and lets the
        # (still mesh-driven, not flat) curvature field roughen the surface
        # continuously instead of a single uniform sheen.
        metal = np.clip(metal + 0.50 * edge, 0.0, 1.0)
        organic_bump = (curvature01 - 0.5) * 2.0  # -1..1, follows the real dents/rivets
        rough = np.clip(rough + 0.18 - 0.03 * edge + 0.07 * organic_bump, 0.32, 1.0)

    if kind == "cloak_fabric":
        band, seam = _strap_mask(h, w, rng, n=2)
        rgb = rgb * (1.0 - band[..., None]) + LEATHER_HEX[None, None, :] * band[..., None]
        rgb = rgb * (1.0 - 0.6 * seam[..., None])  # dark stitched groove
        # Leather reads glossier/harder than the woven cloth around it.
        rough = rough * (1.0 - band) + 0.46 * band
        height = height - 0.0012 * seam + 0.0004 * band

    rgb = np.clip(rgb, 0.0, 255.0)
    if kind in ORGANIC_KINDS:
        # Round 3a used the SAME "convex edge = polished, therefore
        # shinier" formula here that makes sense for metal/wood/horn, but a
        # scar or a knuckle is not a polished edge -- applied to skin it
        # read as "brute glaenzt wie nasses Plastik" (measured before/after
        # below, not just reasoned about). Organic tissue instead gets a
        # flat base-roughness RAISE plus a continuous, mesh-driven ripple
        # (the same curvature field, used as a signed -1..1 variation
        # instead of a thresholded "edge" spike) so the specular highlight
        # breaks into a mottled, skin-like pattern rather than one smooth
        # glossy patch; grime still roughens (never polishes) the crevices.
        organic_bump = (curvature01 - 0.5) * 2.0
        rough2 = np.clip(rough + 0.22 + 0.10 * organic_bump + 0.08 * crevice, 0.45, 1.0)
    elif kind == "shoulder_plates":
        rough2 = np.clip(rough, 0.30, 1.0)  # already set above; floor kept well off "mirror"
    else:
        rough2 = np.clip(rough - 0.20 * edge + 0.14 * crevice, 0.05, 1.0)
    height2 = height + 0.0006 * edge - 0.0010 * crevice
    stats = dict(edge_mean=float(edge.mean()), crevice_mean=float(crevice.mean()),
                edge_frac=float((edge > 0.05).mean()), crevice_frac=float((crevice > 0.05).mean()),
                metallic_mean=float(metal.mean()), metallic_max=float(metal.max()),
                metallic_std=float(metal.std()), roughness_mean=float(rough2.mean()),
                roughness_std=float(rough2.std()))
    return np.round(rgb).astype(np.uint8), height2, rough2, metal, stats


def build_orm_field(rough01, ao01, metallic01):
    """Like texgen_r2.build_orm but with a full metallic FIELD in blue
    instead of one constant -- round 2's build_orm hard-codes a scalar."""
    h, w = rough01.shape
    orm = np.zeros((h, w, 3), dtype=np.uint8)
    orm[..., 0] = np.round(np.clip(ao01, 0, 1) * 255.0).astype(np.uint8)
    orm[..., 1] = np.round(np.clip(rough01, 0.05, 1.0) * 255.0).astype(np.uint8)
    orm[..., 2] = np.round(np.clip(metallic01, 0, 1) * 255.0).astype(np.uint8)
    return orm


def regenerate_with_wear(mat_id, kind, mean_hex, tile_m, seed, curvature01, ao01, out_dir,
                         metallic_base=0.0, before=None):
    """Full round-3 pass for one material: generate the base, apply
    geometry-driven wear, write basecolor/normal/orm, and return a
    before/after report (albedo contrast, normal slope, and the wear stats
    from `apply_geo_wear`) using the SAME metrics texgen_r2 already reports
    with, so round 2's numbers are directly comparable.
    """
    rng = np.random.default_rng(seed)
    rgb0, height0, rough0, ao_synth, texel = generate_base(kind, mean_hex, tile_m, rng, res=RES)
    rgb, height, rough, metal, wear_stats = apply_geo_wear(
        kind, rgb0, height0, rough0, curvature01, ao01, rng, metallic_base=metallic_base)
    ao01_r = _resample_nearest(np.asarray(ao01, dtype=np.float64), *ao_synth.shape)
    ao_combined = np.clip(ao_synth * (0.5 + 0.5 * ao01_r), 0.0, 1.0)
    normal = NM.encode_normal(NM.height_to_normal(height, (texel, texel)))
    orm = build_orm_field(rough, ao_combined, metal)

    mat_dir = os.path.join(out_dir, mat_id)
    os.makedirs(mat_dir, exist_ok=True)
    P.write_png(os.path.join(mat_dir, "%s_basecolor.png" % mat_id), rgb)
    P.write_png(os.path.join(mat_dir, "%s_normal.png" % mat_id), normal)
    P.write_png(os.path.join(mat_dir, "%s_orm.png" % mat_id), orm)
    with open(os.path.join(mat_dir, "%s.json" % mat_id), "w", encoding="utf-8") as fh:
        json.dump(dict(id=mat_id, kind=kind, tile_size_m=[tile_m, tile_m],
                       basecolor="#%02X%02X%02X" % tuple(int(v) for v in rgb.reshape(-1, 3).mean(axis=0)),
                       metallic=float(metal.mean()), generator="texgen_r3", round=3),
                 fh, indent=1, sort_keys=True)

    after = dict(albedo_contrast=T2.albedo_contrast(rgb), normal=T2.normal_slope_stats(normal))
    return dict(before=before, after=after, wear=wear_stats,
               mean_srgb_after=[round(float(v), 1) for v in rgb.reshape(-1, 3).mean(axis=0)],
               tile_size_m=tile_m)
