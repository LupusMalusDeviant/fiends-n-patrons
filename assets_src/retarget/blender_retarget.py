#!/usr/bin/env python3
"""Retargets a humanoid animation library onto a figure's own rig, inside headless Blender.

    blender -b --factory-startup -t 1 --python-exit-code 1 blender_retarget.py --
        --figure <figure.glb> --library <library.glb> --bone-map <bone_map.json>
        --clip-table <clip_table.json> --out <retargeted.glb> --report <report.json>

Not to be run directly; `retarget_clips.py` is the driver and documents the whole run.

## How one bone is retargeted

The two rigs share a skeleton's shape, not its rest pose: bone lengths, roll angles and rest
orientations differ. What carries over is therefore not an orientation but a *change* of
orientation. For a source bone `b` and the figure joint `a` that follows it, in armature space:

    delta(f) = pose_b(f) @ rest_b^-1          the turn the source bone has made since its rest pose
    want_a(f) = delta(f) @ rest_a             the same turn, applied to the figure's rest pose

and the joint's local pose, the value a keyframe stores, follows from its parent's already
computed pose:

    local_a(f) = (rest_parent^-1 @ rest_a)^-1 @ (want_parent(f)^-1 @ want_a(f))

Joints are walked parents first, so `want_parent(f)` is known when a child needs it. Nothing is
read back from the depsgraph between bones: the pose of the whole figure at one frame is computed
as numbers first and written as keyframes afterwards. That is what makes a run reproducible.

Only rotation is taken from the source, except for the joints the bone map lists under
`translation` (the hips): copying a position onto a rig with different bone lengths would tear it
apart, while the hips' own travel is the bob and the sway that make a walk look like walking. The
translation is scaled by the ratio of the two rigs' hip heights, so a taller source does not lift
the figure off the floor.

## Feet on the floor

Rotation alone does not keep a figure on the ground: the library's mannequin has longer legs in
proportion to its torso than the witch does, so a crouched stance that stands on the mannequin
leaves her hanging a hand's width above the floor -- measured, on a jog, ten times the gap a walk
shows. A clip that asks for it (`"ground": true`) is therefore lowered: the pose is computed once,
the lower foot is compared with where that foot stands in the rest pose, and if it floats, the hips
are lowered by exactly that difference and the pose is computed again. The figure is never raised,
so a jump keeps its lift, and nothing but the hips moves, so the motion itself is untouched.

## Joints with no counterpart

Skirt and cape hang from the figure and the library rig has nothing like them. Left alone they
would be the only rigid parts of a moving figure. They are driven instead, by the one thing that
is physically true about cloth: it lags. Each link swings against the turn its anchor has made
over the last `lag` frames, by `follow` of that angle, and each link further down by `falloff` of
the one above it. No simulation, no cache, no randomness -- the same clip gives the same keys.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from clip_plan import (  # noqa: E402
    ClipPlan,
    Plan,
    PlanError,
    check_against_rigs,
    load_plan,
    unmapped_joints,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--figure", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--bone-map", type=Path, required=True)
    parser.add_argument("--clip-table", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def clear_scene() -> None:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for collection in (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.images,
        bpy.data.actions,
        bpy.data.armatures,
    ):
        for block in list(collection):
            collection.remove(block)


def import_glb(path: Path) -> list[bpy.types.Object]:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return sorted((ob for ob in bpy.data.objects if ob not in before), key=lambda ob: ob.name)


def armature_of(objects: list[bpy.types.Object], label: str) -> bpy.types.Object:
    armatures = [ob for ob in objects if ob.type == "ARMATURE"]
    if len(armatures) != 1:
        raise SystemExit(f"{label}: expected exactly one armature, found {len(armatures)}")
    return armatures[0]


def actions_by_name() -> dict[str, bpy.types.Action]:
    return {action.name: action for action in bpy.data.actions}


def assign_action(ob: bpy.types.Object, action: bpy.types.Action) -> None:
    """Puts `action` on `ob`, on Blender's slotted actions as well as the older shape."""
    if ob.animation_data is None:
        ob.animation_data_create()
    ob.animation_data.action = action
    slots = getattr(action, "slots", None)
    if slots:
        suitable = [slot for slot in slots if slot.target_id_type in ("OBJECT", "")]
        ob.animation_data.action_slot = (suitable or list(slots))[0]


def rest_matrices(arm: bpy.types.Object) -> dict[str, Matrix]:
    """Every bone's rest matrix in armature space."""
    return {bone.name: bone.matrix_local.copy() for bone in arm.data.bones}


def bone_parents(arm: bpy.types.Object) -> dict[str, str | None]:
    return {
        bone.name: (bone.parent.name if bone.parent else None) for bone in arm.data.bones
    }


def parents_first(arm: bpy.types.Object) -> list[str]:
    """Bone names, every parent before its children, in a fixed (name-sorted) order."""
    parents = bone_parents(arm)
    ordered: list[str] = []
    remaining = sorted(parents)
    while remaining:
        progressed = False
        for name in list(remaining):
            parent = parents[name]
            if parent is None or parent in ordered:
                ordered.append(name)
                remaining.remove(name)
                progressed = True
        if not progressed:  # a cycle cannot happen in an armature, but never loop forever
            ordered.extend(remaining)
            break
    return ordered


def rotation_of(matrix: Matrix) -> Matrix:
    """The rotation part of a matrix, as a 4x4 without translation or scale."""
    return matrix.to_quaternion().to_matrix().to_4x4()


def torso_length(arm: bpy.types.Object, hips: str, head: str) -> float:
    """Distance from the hips' head to the head bone's head, in the armature's own units.

    The scale a translation has to be converted by is a proportion of the two rigs, not a height
    above the floor: a rig's origin may sit at its hips, at its feet or anywhere else (the witch's
    pelvis rests at z = -0.1 in her own units), so an absolute height would be measured from
    different places and could even come out negative.
    """
    first, second = arm.data.bones.get(hips), arm.data.bones.get(head)
    if first is None or second is None:
        return 0.0
    return float((second.head_local - first.head_local).length)


class Retargeter:
    """Turns one library clip into one figure action."""

    def __init__(self, figure: bpy.types.Object, library: bpy.types.Object, plan: Plan) -> None:
        self.figure = figure
        self.library = library
        self.plan = plan
        self.figure_rest = rest_matrices(figure)
        self.library_rest = rest_matrices(library)
        self.figure_parents = bone_parents(figure)
        self.order = parents_first(figure)
        self.feet = [name for name in ("foot.L", "foot.R") if name in self.figure_rest]
        source_torso = torso_length(
            library,
            plan.bone_map.bones.get("pelvis", ""),
            plan.bone_map.bones.get("head", ""),
        )
        target_torso = torso_length(figure, "pelvis", "head")
        self.translation_scale = (
            target_torso / source_torso if source_torso > 1e-6 else 1.0
        )

    def source_pose(self, frame: float) -> dict[str, Matrix]:
        """The library's pose bone matrices at `frame`, in armature space."""
        whole = int(frame)
        bpy.context.scene.frame_set(whole, subframe=float(frame) - whole)
        return {bone.name: bone.matrix.copy() for bone in self.library.pose.bones}

    def figure_pose(self, source: dict[str, Matrix], *, ground: bool = False) -> dict[str, Matrix]:
        """Armature-space matrices for every figure joint, parents first.

        With `ground`, the hips are lowered until the lower foot stands at its rest height.
        """
        want = self.posed(source, drop=0.0)
        if not ground or not self.feet:
            return want
        floats = min(
            want[foot].translation.z - self.figure_rest[foot].translation.z for foot in self.feet
        )
        if floats <= 0.0:
            return want
        return self.posed(source, drop=floats)

    def posed(self, source: dict[str, Matrix], *, drop: float) -> dict[str, Matrix]:
        want: dict[str, Matrix] = {}
        for name in self.order:
            rest = self.figure_rest[name]
            parent = self.figure_parents[name]
            parent_want = want[parent] if parent else Matrix.Identity(4)
            rest_local = self.rest_local(name)
            # Where the joint sits when it simply follows its parent: the rest pose, carried by
            # whatever the parent already does.
            carried = parent_want @ rest_local
            mapped = self.plan.bone_map.bones.get(name)
            if mapped is not None and mapped in source:
                delta = rotation_of(source[mapped] @ self.library_rest[mapped].inverted())
                posed = delta @ rotation_of(rest)
                posed.translation = carried.translation
                if name in self.plan.bone_map.translation:
                    moved = source[mapped].translation - self.library_rest[mapped].translation
                    posed.translation = carried.translation + moved * self.translation_scale
                    posed.translation.z -= drop
                want[name] = posed
            else:
                # No counterpart: the joint keeps its rest pose relative to its parent, so it
                # follows the body without inventing motion of its own.
                want[name] = carried
        return want

    def local_basis(self, want: dict[str, Matrix]) -> dict[str, Matrix]:
        """What a keyframe stores: each joint's pose in its own rest space."""
        basis: dict[str, Matrix] = {}
        for name in self.order:
            parent = self.figure_parents[name]
            parent_want = want[parent] if parent else Matrix.Identity(4)
            pose_local = parent_want.inverted() @ want[name]
            basis[name] = self.rest_local(name).inverted() @ pose_local
        return basis

    def drive_cloth(self, frames: list[dict[str, Quaternion]], *, loop: bool) -> None:
        """Lets skirt and cape trail the joint they hang from, in place, frame by frame.

        In a looping clip the delay reaches around the end of the cycle -- the last frame repeats
        the first, so the cycle is one frame shorter than the clip -- and in a single clip it
        stops at the first frame, where the figure is still at rest.
        """
        cycle = max(1, len(frames) - 1)
        for chain in self.plan.bone_map.cloth:
            driver = chain.driver
            for index, joint in enumerate(chain.chain):
                weight = chain.follow * (chain.falloff**index)
                lag = chain.lag * (index + 1)
                rest_local = self.rest_local(joint)
                for number, pose in enumerate(frames):
                    delayed = int(round(number - lag))
                    earlier = frames[delayed % cycle if loop else max(0, delayed)]
                    turn = pose[driver] @ earlier[driver].inverted()
                    drag = Quaternion().slerp(turn.inverted(), weight)
                    # The drag is the driver's own turn; express it in the cloth joint's rest
                    # space before it becomes that joint's local rotation.
                    basis = rest_local.to_quaternion()
                    pose[joint] = basis.inverted() @ drag @ basis

    def rest_local(self, name: str) -> Matrix:
        parent = self.figure_parents[name]
        parent_rest = self.figure_rest[parent] if parent else Matrix.Identity(4)
        return parent_rest.inverted() @ self.figure_rest[name]

    def build(self, clip: ClipPlan, source_action: bpy.types.Action) -> dict:
        assign_action(self.library, source_action)
        source_range = tuple(float(value) for value in source_action.frame_range)
        rotations: list[dict[str, Quaternion]] = []
        locations: list[dict[str, Vector]] = []
        sampled = clip.sample_frames(source_range)
        self.sampled_range = (sampled[0], sampled[-1])
        for frame in sampled:
            basis = self.local_basis(
                self.figure_pose(self.source_pose(frame), ground=clip.ground)
            )
            rotations.append({name: matrix.to_quaternion() for name, matrix in basis.items()})
            locations.append(
                {
                    name: basis[name].translation.copy()
                    for name in self.plan.bone_map.translation
                }
            )
        self.drive_cloth(rotations, loop=clip.loop)
        if clip.loop and len(rotations) > 1:
            # The clip format stores a loop with its first frame repeated as its last. The
            # library's own loops close to within 0.004 in a quaternion component; writing the
            # first frame again closes them exactly, so sampling at the clip's duration gives
            # back frame 0 bit for bit.
            rotations[-1] = dict(rotations[0])
            locations[-1] = dict(locations[0])
        return self.write_action(clip, rotations, locations)

    def write_action(
        self,
        clip: ClipPlan,
        rotations: list[dict[str, Quaternion]],
        locations: list[dict[str, Vector]],
    ) -> dict:
        action = bpy.data.actions.new(clip.name)
        action.use_fake_user = True
        assign_action(self.figure, action)
        for bone in self.figure.pose.bones:
            bone.rotation_mode = "QUATERNION"
        for index, pose in enumerate(rotations):
            frame = index + 1
            for name in self.order:
                pose_bone = self.figure.pose.bones.get(name)
                if pose_bone is None:
                    continue
                pose_bone.rotation_quaternion = pose[name]
                pose_bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)
                moved = locations[index].get(name)
                if moved is not None:
                    pose_bone.location = moved
                    pose_bone.keyframe_insert(data_path="location", frame=frame)
        return {
            "name": clip.name,
            "source": clip.source,
            "ground": clip.ground,
            "source_frames": [round(value, 3) for value in self.sampled_range],
            "frames": clip.frames,
            "loop": clip.loop,
        }


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    args = parse_args(argv)
    try:
        plan = load_plan(args.bone_map, args.clip_table)
    except (PlanError, OSError, ValueError) as error:
        raise SystemExit(f"plan: {error}") from error

    clear_scene()
    figure_objects = import_glb(args.figure)
    figure = armature_of(figure_objects, args.figure.name)
    figure_meshes = [ob for ob in figure_objects if ob.type == "MESH"]
    for action in list(bpy.data.actions):  # the figure's own clips are replaced, not merged
        bpy.data.actions.remove(action)

    library_objects = import_glb(args.library)
    library = armature_of(library_objects, args.library.name)
    library_actions = actions_by_name()

    problems = check_against_rigs(
        plan,
        [bone.name for bone in figure.data.bones],
        [bone.name for bone in library.data.bones],
    )
    missing = sorted(
        {clip.source for clip in plan.clips} - set(library_actions)
    )
    if missing:
        problems.append(f"the library has no clip(s) {missing}")
    if problems:
        raise SystemExit("plan does not fit the rigs:\n  " + "\n  ".join(problems))

    bpy.context.scene.frame_set(1)
    retargeter = Retargeter(figure, library, plan)
    report = {
        "figure": args.figure.name,
        "library": args.library.name,
        "frame_rate_hz": plan.frame_rate_hz,
        "translation_scale": round(retargeter.translation_scale, 6),
        "mapped_joints": len(plan.bone_map.bones),
        "cloth_joints": sum(len(chain.chain) for chain in plan.bone_map.cloth),
        "left_at_rest": unmapped_joints(plan, [bone.name for bone in figure.data.bones]),
        "clips": [],
    }
    for clip in plan.clips:
        report["clips"].append(retargeter.build(clip, library_actions[clip.source]))

    # The library rig and its 46 clips have served their purpose. Both go before the export:
    # every action left in the file would otherwise become an animation of the figure.
    for ob in library_objects:
        bpy.data.objects.remove(ob, do_unlink=True)
    wanted = {clip.name for clip in plan.clips}
    for action in list(bpy.data.actions):
        if action.name not in wanted:
            bpy.data.actions.remove(action)

    bpy.context.scene.render.fps = int(round(plan.frame_rate_hz))
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = max(clip.frames for clip in plan.clips)
    bpy.ops.object.select_all(action="DESELECT")
    for ob in (figure, *figure_meshes):
        ob.select_set(True)
    bpy.context.view_layer.objects.active = figure
    args.out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(args.out),
        export_format="GLB",
        use_selection=True,
        export_skins=True,
        export_apply=False,
        export_animations=True,
        # Every action over its own length, not clamped to the scene's playback range, and every
        # frame kept: the exporter's size optimisation drops the keys between the ends, which is
        # exactly the motion this run exists to put there.
        export_frame_range=False,
        export_optimize_animation_size=False,
        export_yup=True,
        export_tangents=True,
        export_image_format="AUTO",
    )
    report["output"] = args.out.name
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("RETARGET_OK", json.dumps({"clips": len(report["clips"])}))


main()
