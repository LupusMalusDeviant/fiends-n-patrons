"""Standalone (plain python, no bpy) smoke test for texgen_r3.regenerate_with_
wear, using synthetic curvature/AO fields shaped like a real bake (a bright
ring of "edge" plus a dark "crevice" blob) instead of a real Blender bake, so
this can run without starting Blender at all.

  <blender>/5.2/python/bin/python.exe test_texgen_r3.py
"""
import os

import numpy as np

import palette as P
import texgen_r3 as T3

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work", "texgen_r3_test")


def fake_masks(res=256):
    yy, xx = np.mgrid[0:res, 0:res].astype(np.float64) / res
    d = np.sqrt((xx - 0.5) ** 2 + (yy - 0.5) ** 2)
    curvature = np.clip(1.0 - np.abs(d - 0.25) / 0.05, 0.0, 1.0) * 0.5 + 0.5  # ring, near 1 on the ring
    ao = 1.0 - np.clip(1.0 - d / 0.15, 0.0, 1.0) * 0.9  # dark blob near the centre
    return curvature, ao


def main():
    os.makedirs(OUT, exist_ok=True)
    curvature, ao = fake_masks()
    # (kind/tex_id, material-dict key for the mean colour, tile_m, metallic_base)
    cases = [("imp_skin", "imp_skin", 1.0, 0.0), ("shoulder_plates", "plates", 1.0, 0.0),
            ("cloak_fabric", "cloak", 1.0, 0.0), ("horn", "horn", 0.25, 0.0),
            ("claw_nail", "claw_nail", 0.12, 0.0)]
    for kind, palette_key, tile_m, metal_base in cases:
        mean_hex = P.MATERIALS.get(palette_key, {}).get("albedo") or "#808080"
        # `kind` doubles as the on-disk tex_id (matlib._images loads from
        # <tex_dir>/<tex_id>/<tex_id>_basecolor.png etc.), matching how
        # build_character_r3.py will call this for real.
        res = T3.regenerate_with_wear(kind, kind, mean_hex, tile_m, seed=1234, curvature01=curvature,
                                      ao01=ao, out_dir=OUT, metallic_base=metal_base)
        print(kind, "contrast", round(res["after"]["albedo_contrast"], 3),
              "slope_mean", round(res["after"]["normal"]["mean_deg"], 3),
              "wear", {k: round(v, 4) for k, v in res["wear"].items()})
    print("TEST_TEXGEN_R3_OK", True)


if __name__ == "__main__":
    main()
