"""Render the per-character deliverables from a built .blend.

  blender -b --factory-startup <char>.blend --python render_shots.py -- \
      --character imp --tex-dir <snapshot>/generated --out <dir> --work <dir> \
      --modes hero,wire,pose,turn

Run the GPU guard before every invocation -- this script renders.

  hero  3/4 view on a tiled floor patch, 1600x1000
  wire  the same view with the pre-subdivision cage drawn as a wire overlay,
        so the edge loops are actually readable
  pose  2x2 grid of four poses that each move a different part of the rig
  turn  eight 45-degree steps as a 4x2 grid
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import palette as P  # noqa: E402
import rigbuild  # noqa: E402
import sheets  # noqa: E402
import spec as SPEC  # noqa: E402
import stage  # noqa: E402

HERO_W, HERO_H = 1600, 1000


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", required=True)
    ap.add_argument("--tex-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--modes", default="hero,wire,pose,turn")
    ap.add_argument("--samples", type=int, default=None)
    return ap.parse_args(argv)


def character_objects(name):
    mesh = bpy.data.objects.get(name)
    cage = bpy.data.objects.get(name + "_cage")
    arm = bpy.data.objects.get(name + "_rig")
    extra = [o for o in bpy.data.objects
             if o.type == 'MESH' and o.parent is arm and o not in (mesh, cage)]
    if mesh is None or arm is None:
        raise SystemExit("blend does not contain %s / %s_rig" % (name, name))
    return mesh, cage, arm, extra


def dress_stage(char, tex_dir, cage):
    """Floor patch, lights and world around an already-loaded character."""
    stage.build_world(bpy.context.scene)
    stage.floor_patch(extent=max(2.2, char["height"] * 2.0),
                      tile=0.8 if char["height"] < 1.6 else 1.1, tex_dir=tex_dir)
    stage.hero_rig()
    if cage is not None:
        cage.hide_render = True


def wire_material():
    mat = bpy.data.materials.get("wire_overlay")
    if mat:
        return mat
    mat = bpy.data.materials.new("wire_overlay")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = P.rgba("#BFF3FF")
    em.inputs["Strength"].default_value = 1.4
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return mat


def render(scene, path):
    return stage.render_to(scene, path)


def main():
    args = parse_args()
    char = SPEC.get(args.character)
    name = char["name"]
    scene = bpy.context.scene
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    mesh, cage, arm, extra = character_objects(name)
    dress_stage(char, args.tex_dir, cage)
    rigbuild.apply_pose(arm, {})
    os.makedirs(args.out, exist_ok=True)
    os.makedirs(args.work, exist_ok=True)
    done = []

    if "hero" in modes:
        stage.setup_render(scene, HERO_W, HERO_H, samples=args.samples)
        stage.hero_camera(scene, char["height"], HERO_W, HERO_H)
        done.append(render(scene, os.path.join(args.out, "hero_%s.png" % name)))

    if "wire" in modes:
        # The cage carries the real topology; drawn as tubes on the edges over
        # the shaded mesh so the loops read against the dark surface.
        cage.hide_render = False
        md = cage.modifiers.new("wire", 'WIREFRAME')
        md.thickness = 0.0022 * max(char["height"], 1.0)
        md.use_replace = True
        md.use_boundary = True
        md.material_offset = len(cage.data.materials)
        cage.data.materials.append(wire_material())
        stage.setup_render(scene, HERO_W, HERO_H, samples=args.samples)
        stage.hero_camera(scene, char["height"], HERO_W, HERO_H)
        done.append(render(scene, os.path.join(args.out, "wireframe_%s.png" % name)))
        cage.modifiers.remove(md)
        cage.hide_render = True

    if "pose" in modes:
        cw, ch = HERO_W // 2, HERO_H // 2
        stage.setup_render(scene, cw, ch, samples=args.samples)
        stage.hero_camera(scene, char["height"], cw, ch, fit=1.45)
        frames = []
        for idx, (label, pose) in enumerate(char["poses"]):
            rigbuild.apply_pose(arm, pose)
            bpy.context.view_layer.update()
            p = render(scene, os.path.join(args.work, "pose_%s_%d.png" % (name, idx)))
            frames.append(stage.load_png(p))
            print("POSE %d %s" % (idx, label))
        rigbuild.apply_pose(arm, {})
        sheets.save(os.path.join(args.out, "pose_%s.png" % name),
                    sheets.grid(frames, 2, 2, HERO_W, HERO_H))
        done.append(os.path.join(args.out, "pose_%s.png" % name))

    if "turn" in modes:
        cw, ch = HERO_W // 4, HERO_H // 2
        stage.setup_render(scene, cw, ch, samples=args.samples)
        stage.hero_camera(scene, char["height"], cw, ch, fit=1.5)
        frames = []
        base = arm.rotation_euler.z
        for k in range(8):
            arm.rotation_euler.z = base + math.radians(45.0 * k)
            bpy.context.view_layer.update()
            p = render(scene, os.path.join(args.work, "turn_%s_%d.png" % (name, k)))
            frames.append(stage.load_png(p))
        arm.rotation_euler.z = base
        sheets.save(os.path.join(args.out, "turntable_%s.png" % name),
                    sheets.grid(frames, 4, 2, HERO_W, HERO_H))
        done.append(os.path.join(args.out, "turntable_%s.png" % name))

    print("RENDER OK", name, done)


if __name__ == "__main__":
    main()
