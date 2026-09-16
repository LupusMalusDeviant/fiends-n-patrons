"""Reimport local player GLBs in Blender and evaluate their animated skins.

Run with Blender --background --factory-startup --threads 4 --python
check_import.py. Optional arguments after --: --root generated.
Only import_validation.json is written. No .blend, GLB, texture or render is
saved. This checks Blender reimport/deformation, not Grimoire compatibility,
visual quality, combat timing or GPU performance.
"""

from __future__ import annotations

import argparse
from array import array
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

import bpy
from mathutils import Matrix


BASE = Path(__file__).resolve().parent
MODEL_IDS = {"iron_penitent", "ash_reaver", "veil_warden"}
CLIPS = ("idle", "walk", "melee", "dash")
SAMPLE_FRACTIONS = (0.0, 0.25, 0.5, 0.75, 1.0)
MAX_EXTENT_M = 6.0
MOVEMENT_THRESHOLD_M = 0.001


class CheckFailure(ValueError):
    pass


def check(condition, message):
    if not condition:
        raise CheckFailure(message)


def embedded_pngs(blob):
    """Read image fingerprints; structural GLB acceptance belongs to validate.py."""
    check(blob[:4] == b"glTF" and len(blob) >= 28, "Source is not a GLB")
    json_size, json_type = struct.unpack_from("<II", blob, 12)
    check(json_type == 0x4E4F534A, "Source JSON chunk missing")
    doc = json.loads(blob[20:20 + json_size])
    offset = 20 + json_size
    bin_size, bin_type = struct.unpack_from("<II", blob, offset)
    check(bin_type == 0x004E4942, "Source BIN chunk missing")
    binary = blob[offset + 8:offset + 8 + bin_size]
    fingerprints = set()
    for image in doc["images"]:
        check("uri" not in image and image.get("mimeType") == "image/png", "Source image is not embedded PNG")
        view = doc["bufferViews"][image["bufferView"]]
        start = view.get("byteOffset", 0)
        fingerprints.add(hashlib.sha256(binary[start:start + view["byteLength"]]).hexdigest())
    return fingerprints


def clip_bindings(armature):
    """Use importer-created NLA records to preserve the correct ActionSlot."""
    animation = armature.animation_data
    check(animation is not None, "Imported armature has no animation data")
    bindings = {}
    for track in animation.nla_tracks:
        check(track.name in CLIPS, "Unexpected imported animation track")
        check(track.name not in bindings and len(track.strips) == 1, "Duplicate or compound imported clip")
        strip = track.strips[0]
        check(strip.action is not None, "Imported animation strip has no action")
        slot = getattr(strip, "action_slot", None)
        check(slot is not None, "Imported animation strip has no action slot")
        bindings[track.name] = (strip.action, slot, float(strip.action_frame_start), float(strip.action_frame_end))
        track.mute = True
        track.is_solo = False
    check(set(bindings) == set(CLIPS), "Expected exactly idle, walk, melee and dash")
    check(len(bpy.data.actions) == 4, "Expected four imported Action data blocks")
    animation.use_nla = False
    animation.action = None
    return bindings


def activate(armature, binding):
    action, slot, start, end = binding
    check(math.isfinite(start) and math.isfinite(end) and end > start, "Invalid imported clip range")
    data = armature.animation_data
    data.action = action
    data.action_slot = slot
    data.action_blend_type = 'REPLACE'
    data.action_influence = 1.0
    armature.data.pose_position = 'POSE'
    for bone in armature.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    check(data.action == action and data.action_slot == slot, "Action/slot activation failed")
    return start, end


def set_time(frame):
    integer = math.floor(frame)
    bpy.context.scene.frame_set(integer, subframe=frame - integer)
    bpy.context.view_layer.update()


def evaluated_vertices(meshes):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    coordinates = []
    for obj in meshes:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
        try:
            check(mesh is not None and len(mesh.vertices) > 0, "Evaluated mesh is empty")
            raw = array('f', [0.0]) * (len(mesh.vertices) * 3)
            mesh.vertices.foreach_get("co", raw)
            matrix = evaluated.matrix_world
            for i in range(0, len(raw), 3):
                x, y, z = raw[i:i + 3]
                point = tuple(matrix[axis][0] * x + matrix[axis][1] * y + matrix[axis][2] * z + matrix[axis][3]
                              for axis in range(3))
                check(all(math.isfinite(value) for value in point), "Non-finite deformed vertex")
                coordinates.append(point)
        finally:
            evaluated.to_mesh_clear()
    lower = [min(point[axis] for point in coordinates) for axis in range(3)]
    upper = [max(point[axis] for point in coordinates) for axis in range(3)]
    extent = [upper[axis] - lower[axis] for axis in range(3)]
    check(max(extent) < MAX_EXTENT_M, "Deformed mesh bounding extent reaches 6 meters")
    check(all(abs(value) < MAX_EXTENT_M for point in coordinates for value in point),
          "Deformed vertices leave the 6-meter origin neighborhood")
    bounds = {"minimum_m": lower, "maximum_m": upper, "extent_m": extent}
    return coordinates, bounds


def compare_vertices(first, second):
    check(len(first) == len(second), "Vertex topology changed between animation samples")
    moved, max_distance, squares = 0, 0.0, 0.0
    for a, b in zip(first, second):
        square = sum((x - y) ** 2 for x, y in zip(a, b))
        distance = math.sqrt(square)
        moved += distance > MOVEMENT_THRESHOLD_M
        max_distance = max(max_distance, distance)
        squares += square
    return {"moved_vertices_over_1mm": moved, "max_displacement_m": max_distance,
            "rms_displacement_m": math.sqrt(squares / len(first))}


def inspect_resources(source_fingerprints):
    images = list(bpy.data.images)
    check(images, "No imported image data blocks")
    packed_fingerprints, image_details = set(), []
    for image in images:
        packed = image.packed_file
        check(packed is not None and packed.size > 0, "Imported image lacks embedded packed resource")
        check(image.size[0] > 0 and image.size[1] > 0, "Imported image dimensions unavailable")
        check(image.has_data and len(image.pixels) >= 4, "Imported image pixels unavailable")
        check(all(math.isfinite(value) for value in image.pixels[:4]), "Imported image pixel sample is non-finite")
        fingerprint = hashlib.sha256(bytes(packed.data)).hexdigest()
        packed_fingerprints.add(fingerprint)
        image_details.append({"width": image.size[0], "height": image.size[1],
                              "packed_bytes": packed.size, "sha256": fingerprint})
    check(source_fingerprints <= packed_fingerprints, "An embedded source PNG is missing after import")
    materials = list(bpy.data.materials)
    check(materials, "No imported materials")
    for material in materials:
        check(material.use_nodes and material.node_tree is not None, "Imported material has no nodes")
        texture_nodes = [node for node in material.node_tree.nodes if node.type == 'TEX_IMAGE']
        check(len(texture_nodes) >= 3, "Material is missing BaseColor/Normal/ORM texture nodes")
        check(all(node.image is not None and node.image.packed_file is not None for node in texture_nodes),
              "Material references a missing image resource")
    check(not bpy.data.libraries, "Import unexpectedly introduced a linked library")
    return {"material_count": len(materials), "packed_image_count": len(images),
            "source_png_fingerprints_preserved": True, "images": image_details}


def inspect_model(path):
    blob = path.read_bytes()
    fingerprint = hashlib.sha256(blob).hexdigest()
    source_fingerprints = embedded_pngs(blob)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    result = bpy.ops.import_scene.gltf(filepath=str(path), import_pack_images=True, merge_vertices=False)
    check('FINISHED' in result, "Blender glTF import did not finish")
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE']
    meshes = sorted((obj for obj in bpy.context.scene.objects if obj.type == 'MESH'), key=lambda obj: obj.name)
    check(len(armatures) == 1, "Expected one imported Armature")
    armature = armatures[0]
    check(len(armature.data.bones) == 23, "Expected 23 imported bones")
    check(meshes, "No imported mesh objects")
    for mesh in meshes:
        check(any(mod.type == 'ARMATURE' and mod.object == armature and mod.show_viewport for mod in mesh.modifiers),
              "Mesh is not evaluated through the imported Armature")
        check(mesh.data.uv_layers, "Imported mesh has no UV layer")
    resources = inspect_resources(source_fingerprints)
    bindings = clip_bindings(armature)
    armature.data.pose_position = 'REST'
    set_time(0)
    neutral, rest_bounds = evaluated_vertices(meshes)
    clips, representatives = {}, {}
    for name in CLIPS:
        start, end = activate(armature, bindings[name])
        samples, best_displacement = [], -1.0
        for fraction in SAMPLE_FRACTIONS:
            frame = start + fraction * (end - start)
            set_time(frame)
            vertices, bounds = evaluated_vertices(meshes)
            movement = compare_vertices(neutral, vertices)
            samples.append({"fraction": fraction, "frame": frame, "bounds": bounds, "movement_from_rest": movement})
            if movement["max_displacement_m"] > best_displacement:
                best_displacement = movement["max_displacement_m"]
                representatives[name] = vertices
        clips[name] = {"frame_start": start, "frame_end": end, "sample_count": len(samples), "samples": samples}
    evidence = {"rest_to_walk": compare_vertices(neutral, representatives["walk"]),
                "rest_to_melee": compare_vertices(neutral, representatives["melee"]),
                "walk_to_melee": compare_vertices(representatives["walk"], representatives["melee"])}
    for label, movement in evidence.items():
        check(movement["moved_vertices_over_1mm"] > 0 and movement["max_displacement_m"] > MOVEMENT_THRESHOLD_M,
              label + ": no deformed vertex motion detected")
    return {"status": "passed", "source_glb_sha256": fingerprint, "source_glb_bytes": len(blob),
            "armature_count": 1, "bone_count": 23, "bone_names": sorted(b.name for b in armature.data.bones),
            "mesh_object_count": len(meshes), "evaluated_vertex_count": len(neutral), "clip_count": 4,
            "rest_bounds": rest_bounds, "resources": resources, "clips": clips, "motion_evidence": evidence}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='generated')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    candidate = Path(args.root)
    root = (candidate if candidate.is_absolute() else BASE / candidate).resolve()
    check(root.is_relative_to(BASE) and root != BASE and root.is_dir(), "Output root must exist inside this package")
    output = root / 'import_validation.json'
    check(not output.is_symlink(), "Report must not be a symlink")
    report = {"schema_version": 1, "checker": "check_import.py", "blender_version": bpy.app.version_string,
              "status": "passed", "scope": "Blender GLB reimport and sampled CPU skin deformation only; no render or engine acceptance.",
              "sample_fractions": list(SAMPLE_FRACTIONS), "max_extent_m": MAX_EXTENT_M, "models": {}, "errors": []}
    paths = sorted(root.rglob('*.glb'))
    if len(paths) != 3 or {path.stem for path in paths} != MODEL_IDS:
        report['errors'].append('Expected exactly three named player GLBs')
    for path in paths:
        relative = path.relative_to(root).as_posix()
        try:
            check(path.resolve().is_relative_to(root), "GLB resolves outside output root")
            report['models'][relative] = inspect_model(path)
        except Exception as exc:
            report['models'][relative] = {"status": "failed", "source_glb_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                          "error": str(exc) if isinstance(exc, CheckFailure) else type(exc).__name__}
        print('IMPORT_CHECK', relative, report['models'][relative]['status'], flush=True)
    if report['errors'] or any(model['status'] != 'passed' for model in report['models'].values()):
        report['status'] = 'failed'
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    print('IMPORT_VALIDATION', report['status'], flush=True)
    if report['status'] != 'passed':
        raise RuntimeError('Player GLB import checks failed; see import_validation.json')


if __name__ == '__main__':
    main()
