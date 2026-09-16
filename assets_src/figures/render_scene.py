"""The two multi-character deliverables: the in-game view and the asset sheet.

  blender -b --factory-startup --python render_scene.py -- \
      --mode ingame --blend-dir <dir> --tex-dir <snapshot>/generated \
      --out <dir> --characters imp,soul,brute

  ingame  all characters plus a pillar and the altar under the gameplay camera
          (65 degrees, PRD-0003 FR-03), 1920x1080
  sheet   the hero shots side by side into asset_sheet.png (no rendering)

Run the GPU guard before the ingame mode; it renders.

Characters are appended with bpy.data.libraries.load in one pass per file, which
keeps the mesh parented to its armature and the armature modifier intact -- an
object-by-object append would break that link.
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import palette as P  # noqa: E402
import sheets  # noqa: E402
import stage  # noqa: E402

INGAME_W, INGAME_H = 1920, 1080
# One portrait panel per character, cropped from its hero shot.
PANEL_W, PANEL_H, PANEL_CX = 700, 980, 810

# Where each character stands and what it looks at, in the arena plane.
LAYOUT = {
    "soul":  dict(pos=(-0.2, -2.30), look_at=(0.4, 2.2)),
    "imp":   dict(pos=(-2.55, 0.65), look_at=(-0.2, -2.0)),
    "brute": dict(pos=(2.70, 1.35), look_at=(0.0, -1.9)),
}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["ingame", "sheet"])
    ap.add_argument("--blend-dir")
    ap.add_argument("--tex-dir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--work")
    ap.add_argument("--characters", default="imp,soul,brute")
    ap.add_argument("--samples", type=int, default=None)
    return ap.parse_args(argv)


def append_character(blend_path, name):
    """Append a character's objects in one pass so parenting survives."""
    with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
        wanted = [n for n in data_from.objects if not n.endswith("_cage")]
        data_to.objects = wanted
    appended = [o for o in data_to.objects if o is not None]
    for ob in appended:
        bpy.context.collection.objects.link(ob)
    arm = next((o for o in appended if o.type == 'ARMATURE'), None)
    if arm is None:
        raise SystemExit("no armature appended from %s" % blend_path)
    return arm, appended


def face_towards(pos_xy, look_xy):
    """Yaw so the character's +Y axis points at the target."""
    dx = look_xy[0] - pos_xy[0]
    dy = look_xy[1] - pos_xy[1]
    return math.atan2(-dx, dy)


def build_ingame(args, names):
    scene = stage.reset_scene()
    stage.build_world(scene)
    stage.floor_patch(extent=8.5, tile=1.1, tex_dir=args.tex_dir)
    stage.altar((0.3, 3.30, 0.0), tex_dir=args.tex_dir)
    stage.pillar((-4.60, 3.90, 0.0), height=4.4, radius=0.44, tex_dir=args.tex_dir,
                 name="pillar_left")
    stage.pillar((4.90, 3.60, 0.0), height=4.4, radius=0.44, tex_dir=args.tex_dir,
                 name="pillar_right")
    stage.arena_rig(radius=6.4, n_torches=6)
    placed = []
    for name in names:
        path = os.path.join(args.blend_dir, "%s.blend" % name)
        if not os.path.exists(path):
            print("SKIP %s (no %s)" % (name, path))
            continue
        arm, _ = append_character(path, name)
        spot = LAYOUT.get(name, dict(pos=(0.0, 0.0), look_at=(0.0, -3.0)))
        arm.location = (spot["pos"][0], spot["pos"][1], 0.0)
        arm.rotation_euler = (0.0, 0.0, face_towards(spot["pos"], spot["look_at"]))
        placed.append(name)
    bpy.context.view_layer.update()
    stage.setup_render(scene, INGAME_W, INGAME_H, samples=args.samples)
    # Aim between the player and the enemies rather than at the altar, or the
    # player (furthest toward -Y) falls off the bottom edge of the frame.
    stage.game_camera(scene, INGAME_W, INGAME_H, target=(0.15, -0.35, 0.95),
                      distance=10.4, pitch_deg=65.0, vfov_deg=35.0)
    out = os.path.join(args.out, "ingame_view.png")
    stage.render_to(scene, out)
    print("RENDER OK ingame", placed, out)
    return out


def build_sheet(args, names):
    imgs = []
    for name in names:
        path = os.path.join(args.out, "hero_%s.png" % name)
        if not os.path.exists(path):
            print("SKIP %s (no hero shot)" % name)
            continue
        imgs.append(sheets.crop(stage.load_png(path), PANEL_W, PANEL_H, cx=PANEL_CX))
    if not imgs:
        raise SystemExit("no hero shots to assemble")
    pad = 10
    out_w = PANEL_W * len(imgs) + pad * (len(imgs) + 1)
    out_h = PANEL_H + pad * 2
    out = os.path.join(args.out, "asset_sheet.png")
    sheets.save(out, sheets.strip(imgs, out_w, out_h, pad=pad))
    print("SHEET OK", out, "%d panels, %dx%d" % (len(imgs), out_w, out_h))
    return out


def main():
    args = parse_args()
    names = [n.strip() for n in args.characters.split(",") if n.strip()]
    os.makedirs(args.out, exist_ok=True)
    if args.mode == "ingame":
        build_ingame(args, names)
    else:
        build_sheet(args, names)


if __name__ == "__main__":
    main()
