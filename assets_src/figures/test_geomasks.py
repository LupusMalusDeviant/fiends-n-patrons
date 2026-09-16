"""Standalone smoke test for geomasks.bake_masks on a real (small) built mesh.

Builds the imp with the round-3 sculpting (eye sockets + aniso bumps), packs
it into an object, UV-unwraps it, subdivides it once (kept low to keep this
test fast), assigns the round-2 materials as a bootstrap, then bakes
curvature + AO and prints the per-slot statistics. This DOES use Cycles
(CPU device only, see geomasks.py's own note) but never touches Eevee/GPU
rendering, so it runs without the GPU guard.

  blender -b --factory-startup --python test_geomasks.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import build_character as BC  # noqa: E402
import geomasks as GM  # noqa: E402
import headsculpt as HS  # noqa: E402
import matlib  # noqa: E402
import spec as SPEC  # noqa: E402
import stage  # noqa: E402
import surface as SF  # noqa: E402
import uvmap  # noqa: E402

WORK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work", "geomask_test")
TEX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tex_snapshot_r3", "generated")


def build_surface_r3(char):
    s = BC.build_surface(char)
    for sock in char.get("eye_sockets", []):
        HS.carve_eye_socket(s, sock["at"], rim_radius=sock["rim_radius"], depth=sock["depth"],
                            region=sock.get("region"))
    for b in char.get("aniso_bumps", []):
        HS.bump_aniso(s, b["center"], b["radii"], b["offset"], only_region=b.get("region"))
    for bv in char.get("bevels", []):
        HS.bevel_region_boundary(s, bv["region"], bv["width"], segments=bv.get("segments", 2),
                                 region_other=bv.get("region_other"))
    return s


def main():
    os.makedirs(WORK, exist_ok=True)
    scene = stage.reset_scene()
    stage.build_world(scene)
    char = SPEC.get("imp")
    matlib.ensure_materials(sorted(set(char["materials"].values())), TEX_DIR)
    s = build_surface_r3(char)
    manifold = s.check_manifold()
    print("MANIFOLD", manifold)
    ob = s.to_object(char["name"], char["materials"])
    s.free()

    n_seams = uvmap.mark_seams(ob, [])  # keep it simple for this smoke test: no seam rules needed
    uvmap.unwrap(ob)
    SF.apply_subsurf(ob, levels=1, render_levels=1)
    SF.shade_smooth(ob)

    out, report = GM.bake_masks(ob, res=256, work_dir=WORK, samples=16)
    print("CURVATURE_VERTEX_STATS", report["curvature_vertex_stats"])
    for slot, d in report["slots"].items():
        mat = ob.data.materials[slot].name if slot < len(ob.data.materials) else str(slot)
        print("SLOT", slot, mat, d)
    ok = all(not v.get("curvature_degenerate") and not v.get("ao_degenerate")
            for v in report["slots"].values())
    print("TEST_GEOMASKS_OK", ok, "slots_baked", sorted(out.keys()))


if __name__ == "__main__":
    main()
