"""Round 3: a direct high-vs-low LOD comparison from the GAME CAMERA, one
character at a time -- this is what proves the LOD normal bake actually
carries the new eye-socket/brow/jaw detail down to the sparse in-game mesh
rather than just asserting it.

The gameplay camera (stage.game_camera, 65 degree pitch) is normally framed
to hold all three characters at once (distance ~10.4 m), which makes any one
character's head a small fraction of the frame -- too small to see a normal-
map difference. This keeps the SAME pitch/angle/view-transform but moves the
camera in close on a single character so the comparison is actually legible,
and says so in the composite.

  blender -b --factory-startup --python render_lod_compare.py -- \\
      --character imp --blend-dir <r3 high dir> --blend-dir-low <r3 low dir> \\
      --tex-dir <r3 tex-dir>/generated --out <dir>

Run the GPU guard first -- this renders.
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import sheets  # noqa: E402
import spec as SPEC  # noqa: E402
import stage  # noqa: E402

W, H = 900, 1000


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", required=True)
    ap.add_argument("--blend-dir", required=True)
    ap.add_argument("--blend-dir-low", required=True)
    ap.add_argument("--tex-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--samples", type=int, default=None)
    return ap.parse_args(argv)


def append_character(blend_path, name):
    with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
        wanted = [n for n in data_from.objects if not n.endswith("_cage")]
        data_to.objects = wanted
    appended = [o for o in data_to.objects if o is not None]
    for ob in appended:
        bpy.context.collection.objects.link(ob)
    arm = next((o for o in appended if o.type == 'ARMATURE'), None)
    if arm is None:
        raise SystemExit("no armature appended from %s" % blend_path)
    return arm


def render_one(blend_path, char, args, tag):
    scene = stage.reset_scene()
    stage.build_world(scene)
    stage.floor_patch(extent=6.0, tile=1.1, tex_dir=args.tex_dir)
    stage.arena_rig(radius=6.4, n_torches=6)
    arm = append_character(blend_path, char["name"])
    arm.location = (0.0, 0.0, 0.0)
    # The game camera sits on the -Y side looking toward +Y (see
    # stage.game_camera / render_scene.LAYOUT); characters are modelled
    # facing +Y, so left at rotation 0 the camera looks at this one's BACK
    # (confirmed by a first render: horns and the back of the skull, seen
    # from above-behind). A 180 degree yaw turns it to face the camera.
    arm.rotation_euler = (0.0, 0.0, math.radians(180.0))
    bpy.context.view_layer.update()
    stage.setup_render(scene, W, H, samples=args.samples)
    # Same pitch/FOV as the real gameplay camera, moved in close on the
    # head/chest of ONE character instead of framing all three.
    target = (0.0, 0.0, char["height"] * 0.78)
    dist = max(1.9, char["height"] * 1.7)
    stage.game_camera(scene, W, H, target=target, distance=dist, pitch_deg=65.0, vfov_deg=35.0)
    out = os.path.join(args.out, "lod_%s_%s.png" % (tag, char["name"]))
    stage.render_to(scene, out)
    print("RENDER OK lod", tag, char["name"], out)
    return stage.load_png(out)


def main():
    args = parse_args()
    char = SPEC.get(args.character)
    os.makedirs(args.out, exist_ok=True)

    high_path = os.path.join(args.blend_dir, "%s.blend" % char["name"])
    low_path = os.path.join(args.blend_dir_low, "%s.blend" % char["name"])
    img_high = render_one(high_path, char, args, "high")
    img_low = render_one(low_path, char, args, "low")

    pad = 10
    canvas = sheets.strip([img_high, img_low], W * 2 + pad * 3, H + pad * 2, pad=pad)
    out = os.path.join(args.out, "lod_compare_%s.png" % char["name"])
    sheets.save(out, canvas)
    print("LOD COMPARE OK", char["name"], out)


if __name__ == "__main__":
    main()
