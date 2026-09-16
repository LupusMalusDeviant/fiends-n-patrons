"""Close-up head shot: a tight three-quarter framing on the head bone, so the
round-2 face features (eyes, brow/jaw, mask eye slits) are actually judgeable.

  blender -b --factory-startup <char>.blend --python render_headshot.py -- \\
      --character imp --tex-dir <r2 snapshot>/generated --out <dir>

Run the GPU guard first -- this renders.
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import rigbuild  # noqa: E402
import spec as SPEC  # noqa: E402
import stage  # noqa: E402

W, H = 1200, 1200


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", required=True)
    ap.add_argument("--tex-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--samples", type=int, default=None)
    return ap.parse_args(argv)


def main():
    args = parse_args()
    char = SPEC.get(args.character)
    name = char["name"]
    scene = bpy.context.scene
    mesh = bpy.data.objects.get(name) or bpy.data.objects.get(name + "_low")
    cage = bpy.data.objects.get(name + "_cage")
    arm = bpy.data.objects.get(name + "_rig")
    if mesh is None or arm is None:
        raise SystemExit("blend does not contain %s / %s_rig" % (name, name))

    stage.build_world(scene)
    stage.floor_patch(extent=max(2.2, char["height"] * 2.0),
                      tile=0.8 if char["height"] < 1.6 else 1.1, tex_dir=args.tex_dir)
    stage.hero_rig()
    if cage is not None:
        cage.hide_render = True
    rigbuild.apply_pose(arm, {})

    # Aim at the actual face features (the eye/eye-slit decor props), not the
    # head bone's own tail -- the mask/muzzle/brow sit well forward and below
    # it, and framing on the bone alone clipped the face out of a first
    # attempt at this shot.
    eye_obs = [o for o in bpy.data.objects
              if o.name.startswith(name + "_") and "eye" in o.name.lower()
              and o.type == 'MESH']
    head_bone = arm.pose.bones.get("head")
    if eye_obs:
        pts = [ob.matrix_world @ Vector(c) for ob in eye_obs for c in ob.bound_box]
        target = sum(pts, Vector((0, 0, 0))) / len(pts)
    elif head_bone:
        target = arm.matrix_world @ head_bone.tail
    else:
        target = Vector((0, 0, char["height"] * 0.92))

    # Same fixed world-space azimuth/elevation as stage.hero_camera (35/17
    # degrees off the +Y side) -- proven in the hero shots to face every one
    # of the three characters, hunched or upright, since it is the exact
    # convention the whole-body shot already uses. Two attempts at a
    # per-character "face normal" derived from the head bone's own axis
    # over-rotated for the hunched characters (found the crown from above,
    # then a horn in profile); reusing the working convention beats deriving
    # a fragile new one.
    cam_data = bpy.data.cameras.new("head_cam")
    cam_data.sensor_fit = 'VERTICAL'
    cam_data.angle_y = math.radians(45.0)
    cam_data.clip_start, cam_data.clip_end = 0.02, 50.0
    cam = bpy.data.objects.new("head_cam", cam_data)
    bpy.context.collection.objects.link(cam)
    dist = max(0.55, char["height"] * 0.5)
    # hero_camera's 35/17 degrees is measured for the WHOLE BODY: a 35 degree
    # swing still keeps most of a body-sized volume in view, but a head is
    # much narrower, and the same swing point past the eye sockets to the
    # temple/cheek -- confirmed with an 8-step azimuth sweep
    # (diag_head_multiangle.py) where only az=0 clearly showed both eye
    # sockets; 45 degrees and up was already in profile. A near-frontal shot
    # plus a generous 45-degree lens (not a tight long-lens crop) is what that
    # sweep actually used, so this keeps both rather than re-guessing a
    # "tighter" framing that a narrower FOV attempt lost the face on again.
    az, el = math.radians(0.0), math.radians(10.0)
    cam.location = target + Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el),
                                    math.sin(el))) * dist
    d = target - cam.location
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam

    os.makedirs(args.out, exist_ok=True)
    stage.setup_render(scene, W, H, samples=args.samples)
    out = os.path.join(args.out, "head_%s.png" % name)
    stage.render_to(scene, out)
    print("RENDER OK head", name, out)


if __name__ == "__main__":
    main()
