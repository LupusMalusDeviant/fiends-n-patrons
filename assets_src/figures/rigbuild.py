"""Armatures: real bones in edit mode, automatic weights, and a weight audit.

The bone chains are built from the same skeleton numbers the surface was lofted
along, so the bones actually sit inside the limbs instead of near them. After
`ARMATURE_AUTO` parenting the weight map is audited (unweighted vertices, weights
above one, and spikes -- a vertex strongly bound to a bone that is nowhere near
it) and repaired; a broken map is visible in the pose sheet, so it gets fixed
before the renders rather than explained afterwards.
"""
import math

import bpy
import numpy as np
from mathutils import Vector


def mirror_bone(b):
    """Mirror one bone definition across the YZ plane, .R -> .L."""
    out = dict(b)
    out["name"] = b["name"].replace(".R", ".L")
    out["head"] = (-b["head"][0], b["head"][1], b["head"][2])
    out["tail"] = (-b["tail"][0], b["tail"][1], b["tail"][2])
    if b.get("parent", "").endswith(".R"):
        out["parent"] = b["parent"].replace(".R", ".L")
    return out


def expand_bones(bones):
    """Expand every .R bone marked mirror=True into a left/right pair."""
    out = []
    for b in bones:
        out.append(b)
        if b.get("mirror"):
            out.append(mirror_bone(b))
    return out


def build_armature(name, bones, collection=None):
    """Create the armature object with bones in edit mode."""
    arm = bpy.data.armatures.new(name)
    ob = bpy.data.objects.new(name, arm)
    (collection or bpy.context.collection).objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    created = {}
    for b in bones:
        eb = arm.edit_bones.new(b["name"])
        eb.head = Vector(b["head"])
        eb.tail = Vector(b["tail"])
        eb.roll = math.radians(float(b.get("roll", 0.0)))
        if eb.length < 1e-4:
            raise ValueError("bone %s has zero length" % b["name"])
        created[b["name"]] = eb
    for b in bones:
        if b.get("parent"):
            eb = created[b["name"]]
            eb.parent = created[b["parent"]]
            eb.use_connect = bool(b.get("connect", False))
    bpy.ops.object.mode_set(mode='OBJECT')
    for b in bones:
        if b.get("deform") is False:
            ob.data.bones[b["name"]].use_deform = False
    return ob


def parent_with_auto_weights(mesh_obs, arm_ob):
    """Bind meshes to the armature with Blender's automatic (heat) weights."""
    bpy.context.view_layer.objects.active = arm_ob
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    for ob in mesh_obs:
        ob.select_set(True)
    arm_ob.select_set(True)
    bpy.context.view_layer.objects.active = arm_ob
    res = bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    bpy.ops.object.select_all(action='DESELECT')
    return res


def _bone_segments(arm_ob):
    """World-space (head, tail) of every deforming bone."""
    mw = arm_ob.matrix_world
    return {b.name: (mw @ b.head_local, mw @ b.tail_local)
            for b in arm_ob.data.bones if b.use_deform}


def _point_segment_distance(p, a, b):
    ab = b - a
    denom = float(ab.dot(ab))
    t = 0.0 if denom < 1e-12 else max(0.0, min(1.0, float((p - a).dot(ab)) / denom))
    return float((p - (a + ab * t)).length)


def audit_weights(mesh_ob, arm_ob, spike_factor=0.35, scale=1.0):
    """Report unweighted vertices, weights outside [0, 1], and spikes.

    A spike is a vertex with a meaningful weight (> 0.2) on a bone whose segment
    is further away than `spike_factor * scale` -- the signature of heat-map
    bleed across a gap, e.g. the tail grabbing the thigh.
    """
    me = mesh_ob.data
    groups = {g.index: g.name for g in mesh_ob.vertex_groups}
    segs = _bone_segments(arm_ob)
    mw = mesh_ob.matrix_world
    unweighted, over_one, spikes, totals = [], [], [], []
    for v in me.vertices:
        entries = [(groups.get(g.group), g.weight) for g in v.groups]
        entries = [(n, w) for n, w in entries if n is not None and w > 0.0]
        tot = sum(w for _, w in entries)
        totals.append(tot)
        if tot <= 1e-6:
            unweighted.append(v.index)
            continue
        for name, w in entries:
            if w > 1.0 + 1e-5:
                over_one.append((v.index, name, w))
            if w > 0.2 and name in segs:
                a, b = segs[name]
                d = _point_segment_distance(mw @ v.co, a, b)
                if d > spike_factor * scale:
                    spikes.append((v.index, name, round(w, 3), round(d, 4)))
    tot_arr = np.array(totals) if totals else np.zeros(1)
    return dict(vertices=len(me.vertices), unweighted=len(unweighted),
                unweighted_examples=unweighted[:8], over_one=len(over_one),
                spikes=len(spikes), spike_examples=spikes[:8],
                weight_sum_min=float(tot_arr.min()), weight_sum_max=float(tot_arr.max()),
                max_influences=max((len(v.groups) for v in me.vertices), default=0))


def repair_weights(mesh_ob, limit=4, smooth_iterations=2, smooth_factor=0.4):
    """Limit influences, smooth and renormalise. Runs in weight-paint context."""
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    mesh_ob.select_set(True)
    bpy.context.view_layer.objects.active = mesh_ob
    bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
    # Smooth FIRST, then limit: smoothing hands weight to neighbouring bones and
    # would otherwise push the influence count back over the limit -- which glTF
    # then silently truncates to its own four.
    for _ in range(smooth_iterations):
        bpy.ops.object.vertex_group_smooth(group_select_mode='ALL', factor=smooth_factor,
                                           repeat=1, expand=0.0)
    bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=limit)
    bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')


def fill_unweighted(mesh_ob, arm_ob):
    """Last-resort fallback: bind any vertex the heat solver missed to the
    nearest deforming bone, so no vertex is ever left behind by the rig."""
    me = mesh_ob.data
    groups = {g.index: g.name for g in mesh_ob.vertex_groups}
    segs = _bone_segments(arm_ob)
    mw = mesh_ob.matrix_world
    fixed = 0
    for v in me.vertices:
        if sum(g.weight for g in v.groups if groups.get(g.group)) > 1e-6:
            continue
        p = mw @ v.co
        name = min(segs, key=lambda n: _point_segment_distance(p, *segs[n]))
        vg = mesh_ob.vertex_groups.get(name) or mesh_ob.vertex_groups.new(name=name)
        vg.add([v.index], 1.0, 'REPLACE')
        fixed += 1
    return fixed


def apply_pose(arm_ob, pose, scene=None):
    """Set a pose from {bone: (rx, ry, rz) in degrees}; clears everything else."""
    bpy.context.view_layer.objects.active = arm_ob
    for pb in arm_ob.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.location = (0.0, 0.0, 0.0)
    for name, rot in (pose or {}).items():
        pb = arm_ob.pose.bones.get(name)
        if pb is None:
            raise KeyError("pose refers to unknown bone %r" % name)
        pb.rotation_euler = tuple(math.radians(float(a)) for a in rot)
    if scene is not None:
        bpy.context.view_layer.update()


def deformation_check(mesh_ob, arm_ob, pose):
    """How far the mesh actually moves under a pose -- proof the skin is bound.

    Returns the max and mean vertex displacement in metres. A rig that is
    parented but not weighted reports ~0 here, which is exactly the failure the
    previous attempt could not have detected.
    """
    dg = bpy.context.evaluated_depsgraph_get()
    rest = np.array([tuple(v.co) for v in mesh_ob.evaluated_get(dg).to_mesh().vertices])
    mesh_ob.evaluated_get(dg).to_mesh_clear()
    apply_pose(arm_ob, pose)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    posed = np.array([tuple(v.co) for v in mesh_ob.evaluated_get(dg).to_mesh().vertices])
    mesh_ob.evaluated_get(dg).to_mesh_clear()
    apply_pose(arm_ob, {})
    bpy.context.view_layer.update()
    if rest.shape != posed.shape:
        return dict(error="vertex count changed under pose")
    d = np.linalg.norm(posed - rest, axis=1)
    return dict(max_move_m=float(d.max()), mean_move_m=float(d.mean()),
                moved_fraction=float((d > 1e-4).mean()))
