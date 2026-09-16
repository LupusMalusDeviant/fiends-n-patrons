"""Standalone smoke test for headsculpt.carve_eye_socket / bump_aniso.

Builds the imp's real surface (same build_character.build_surface() the
actual pipeline uses), carves both eye sockets on it, and prints every
measurement needed to judge whether it actually worked: manifoldness before
and after, face/vert deltas, and the achieved socket depth. No object is
created and nothing is rendered -- pure bmesh, no GPU involved.

  blender -b --factory-startup --python test_headsculpt.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_character as BC  # noqa: E402
import headsculpt as HS  # noqa: E402
import spec as SPEC  # noqa: E402


def run(char_name, eye_specs, rim_radius, depth, seed_rings=1, subdiv_cuts=8):
    char = SPEC.get(char_name)
    s = BC.build_surface(char)
    before = s.stats()
    manifold_before = s.check_manifold()
    print("BEFORE", char_name, before, manifold_before)
    results = []
    for name, at in eye_specs:
        res = HS.carve_eye_socket(s, at, rim_radius=rim_radius, depth=depth,
                                  region=char["torso"]["region"], seed_rings=seed_rings,
                                  subdiv_cuts=subdiv_cuts)
        print("SOCKET", char_name, name, res)
        results.append(res)
    after = s.stats()
    manifold_after = s.check_manifold()
    print("AFTER", char_name, after, manifold_after)
    d_faces = after["faces"] - before["faces"]
    d_verts = after["verts"] - before["verts"]
    print("DELTA", char_name, "faces +%d verts +%d tris_before=%d tris_after=%d"
          % (d_faces, d_verts, before["tris"], after["tris"]))
    ok = manifold_after["non_manifold_edges"] == 0 and manifold_after["loose_verts"] == 0
    print("MANIFOLD_OK", char_name, ok)
    for r in results:
        depth_ok = r["achieved_depth_m"] > depth * 0.5
        print("DEPTH_OK", char_name, r["achieved_depth_m"], depth_ok)
    s.free()
    return ok and all(r["achieved_depth_m"] > depth * 0.5 for r in results)


if __name__ == "__main__":
    imp = SPEC.get("imp")
    imp_eyes = [(d["name"], d["at"]) for d in imp["decor"] if d["name"].startswith("eye")]
    ok_imp = run("imp", imp_eyes, rim_radius=0.032, depth=0.012, seed_rings=1, subdiv_cuts=8)

    brute = SPEC.get("brute")
    brute_eyes = [(d["name"], d["at"]) for d in brute["decor"] if d["name"].startswith("eye")]
    ok_brute = run("brute", brute_eyes, rim_radius=0.048, depth=0.018, seed_rings=1, subdiv_cuts=8)

    # bump_aniso + bevel_region_boundary smoke test on the soul (mask edges).
    soul = SPEC.get("soul")
    s = BC.build_surface(soul)
    before = s.stats()
    moved = HS.bump_aniso(s, (0.0, 0.120, 1.600), (0.09, 0.05, 0.03), (0.0, 0.012, 0.008),
                          only_region="mask")
    bevel_res = HS.bevel_region_boundary(s, "mask", width=0.006, segments=2, region_other="robe")
    after = s.stats()
    manifold = s.check_manifold()
    ok_soul = manifold["non_manifold_edges"] == 0 and manifold["loose_verts"] == 0 and moved > 0
    print("BUMP_ANISO moved", moved, "BEVEL", bevel_res, "BEFORE", before, "AFTER", after,
          "MANIFOLD", manifold, "OK", ok_soul)
    s.free()

    print("TEST_HEADSCULPT_OK", ok_imp and ok_brute and ok_soul)
