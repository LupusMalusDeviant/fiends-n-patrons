"""Round 3: head close-ups from three angles (front, three-quarter, profile)
plus a head-only wireframe, so the new eye sockets and head structure are
actually judgeable -- render_headshot.py (round 2) only ever did the single
near-frontal angle.

  blender -b --factory-startup <char>.blend --python render_headshot_r3.py -- \\
      --character imp --tex-dir <r3 tex-dir>/generated --out <dir>

Run the GPU guard first -- this renders.
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import palette as P  # noqa: E402
import rigbuild  # noqa: E402
import sheets  # noqa: E402
import spec as SPEC  # noqa: E402
import stage  # noqa: E402

W, H = 1100, 1100
ANGLES = [("front", 0.0), ("threequarter", 40.0), ("profile", 82.0)]


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", required=True)
    ap.add_argument("--tex-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--samples", type=int, default=None)
    return ap.parse_args(argv)


def wire_material():
    mat = bpy.data.materials.get("wire_overlay_r3")
    if mat:
        return mat
    mat = bpy.data.materials.new("wire_overlay_r3")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = P.rgba("#BFF3FF")
    em.inputs["Strength"].default_value = 1.4
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return mat


def head_camera(target, dist, az_deg, el_deg=10.0, name="head_cam"):
    cam_data = bpy.data.cameras.new(name)
    cam_data.sensor_fit = 'VERTICAL'
    cam_data.angle_y = math.radians(45.0)
    cam_data.clip_start, cam_data.clip_end = 0.02, 50.0
    cam = bpy.data.objects.new(name, cam_data)
    bpy.context.collection.objects.link(cam)
    az, el = math.radians(az_deg), math.radians(el_deg)
    cam.location = target + Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el),
                                    math.sin(el))) * dist
    d = target - cam.location
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return cam


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

    dist = max(0.55, char["height"] * 0.5)
    os.makedirs(args.out, exist_ok=True)
    os.makedirs(args.work, exist_ok=True)
    done = []

    # --- three angles, shaded -------------------------------------------
    stage.setup_render(scene, W, H, samples=args.samples)
    for label, az in ANGLES:
        cam = head_camera(target, dist, az)
        scene.camera = cam
        out = os.path.join(args.out, "head_%s_%s.png" % (name, label))
        stage.render_to(scene, out)
        done.append(out)
        bpy.data.objects.remove(cam, do_unlink=True)
        print("RENDER OK head", name, label, out)

    # --- head wireframe (front angle), the CAGE topology as tubes --------
    if cage is not None:
        cage.hide_render = False
        md = cage.modifiers.new("wire", 'WIREFRAME')
        md.thickness = 0.0016 * max(char["height"], 1.0)
        md.use_replace = True
        md.use_boundary = True
        md.material_offset = len(cage.data.materials)
        cage.data.materials.append(wire_material())
        cam = head_camera(target, dist, ANGLES[0][1])
        scene.camera = cam
        out = os.path.join(args.out, "wireframe_head_%s.png" % name)
        stage.render_to(scene, out)
        done.append(out)
        cage.modifiers.remove(md)
        cage.hide_render = True
        bpy.data.objects.remove(cam, do_unlink=True)
        print("RENDER OK head wireframe", name, out)
    else:
        print("SKIP head wireframe: no _cage object in this blend")

    print("RENDER OK", name, done)


if __name__ == "__main__":
    main()
