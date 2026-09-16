"""Round 3: compose the curvature / AO / final-albedo showcase image (no
Blender needed -- pure numpy on the PNGs build_character_r3.py already
wrote out).

  <blender>/5.2/python/bin/python.exe make_mask_showcase.py \\
      --masks work/masks_imp --tex-id imp_skin --label imp_skin --out work/texture_masks_imp.png
"""
import argparse
import os

import numpy as np

import palette as P
import sheets


def label_strip(img, height=40):
    """A plain dark bar under a panel -- no font rendering available, so the
    caller's filename/report carries the label; this just keeps the panels
    visually separated."""
    h, w = img.shape[:2]
    bar = np.full((height, w, 3), (18, 19, 24), dtype=np.uint8)
    return np.concatenate([img, bar], axis=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--masks", required=True, help="work_r3/masks_<char> directory")
    ap.add_argument("--tex-id", required=True)
    ap.add_argument("--slot", type=int, default=0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    curv = P.read_png(os.path.join(args.masks, "slot%d_curvature.png" % args.slot))
    ao = P.read_png(os.path.join(args.masks, "slot%d_ao.png" % args.slot))
    albedo = P.read_png(os.path.join(args.masks, "tex_r3", args.tex_id, "%s_basecolor.png" % args.tex_id))

    size = min(curv.shape[0], ao.shape[0], albedo.shape[0], 640)
    def fit(img):
        return sheets.fit(img, size, size)
    panels = [fit(curv), fit(ao), fit(albedo)]
    pad = 12
    canvas = sheets.strip(panels, size * 3 + pad * 4, size + pad * 2, pad=pad)
    sheets.save(args.out, canvas)
    print("MASK_SHOWCASE_OK", args.out)


if __name__ == "__main__":
    main()
