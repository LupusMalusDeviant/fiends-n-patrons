"""One-off, plain-python (no bpy) prep step: copy the round-2 texture
snapshot into a round-3 folder and add baseline (not-yet-wear-applied)
textures for the two new keratin materials (horn, claw_nail) so
matlib.ensure_materials can bootstrap every character's materials before the
mesh (and therefore the real curvature/AO bake) exists. build_character_r3.py
overwrites all of this in-memory once it has baked masks from the actual
mesh; this script only has to make the FIRST material load not crash.

  python bootstrap_r3_textures.py --src <r2>/generated --out <r3>/generated
"""
import argparse
import json
import os
import shutil

import numpy as np

import palette as P
import texgen_r3 as T3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=20260916 + 3)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    for entry in sorted(os.listdir(args.src)):
        s = os.path.join(args.src, entry)
        d = os.path.join(args.out, entry)
        if os.path.isdir(s):
            if os.path.exists(d):
                shutil.rmtree(d)
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)

    for mat_id in T3.NEW_KINDS:
        spec_row = P.MATERIALS[mat_id]
        tile_m = 0.25 if mat_id == "horn" else 0.12
        rng = np.random.default_rng(P.stable_seed(args.seed, mat_id))
        rgb, height, rough, ao, texel = T3.generate_base(mat_id, spec_row["albedo"], tile_m, rng)
        import normalmap as NM
        normal = NM.encode_normal(NM.height_to_normal(height, (texel, texel)))
        orm = T3.build_orm_field(rough, ao, np.full_like(rough, spec_row["m"]))
        mat_dir = os.path.join(args.out, mat_id)
        os.makedirs(mat_dir, exist_ok=True)
        P.write_png(os.path.join(mat_dir, "%s_basecolor.png" % mat_id), rgb)
        P.write_png(os.path.join(mat_dir, "%s_normal.png" % mat_id), normal)
        P.write_png(os.path.join(mat_dir, "%s_orm.png" % mat_id), orm)
        with open(os.path.join(mat_dir, "%s.json" % mat_id), "w", encoding="utf-8") as fh:
            json.dump(dict(id=mat_id, tile_size_m=[tile_m, tile_m], basecolor=spec_row["albedo"],
                           metallic=spec_row["m"], generator="texgen_r3_bootstrap", round=3),
                     fh, indent=1, sort_keys=True)
        print("BOOTSTRAP", mat_id, "contrast", T3.T2.albedo_contrast(rgb),
              "tile_m", tile_m)

    src_catalog = os.path.join(args.src, "..", "catalog.json")
    catalog_path = os.path.join(args.out, "..", "catalog.json")
    if not os.path.exists(catalog_path) and os.path.exists(src_catalog):
        shutil.copy2(src_catalog, catalog_path)
    with open(catalog_path, "r", encoding="utf-8") as fh:
        catalog = json.load(fh)
    have = {m["id"] for m in catalog["materials"]}
    for mat_id in T3.NEW_KINDS:
        if mat_id in have:
            continue
        tile_m = 0.25 if mat_id == "horn" else 0.12
        catalog["materials"].append(dict(id=mat_id, tile_size_m=[tile_m, tile_m],
                                         basecolor=P.MATERIALS[mat_id]["albedo"],
                                         metallic=P.MATERIALS[mat_id]["m"],
                                         note="Round 3: new keratin material (texgen_r3)."))
    with open(catalog_path, "w", encoding="utf-8") as fh:
        json.dump(catalog, fh, indent=1)
    print("BOOTSTRAP_R3_TEXTURES_OK", args.out)


if __name__ == "__main__":
    main()
