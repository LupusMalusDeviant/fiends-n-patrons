"""Original procedural melee weapons for the three player-model studies.

Call ``build_weapon(kind, materials)`` inside Blender.  Each returned mesh uses
the grip centre as origin, +Z as its length axis and -Y as its presentation side.
The module uses no scene operators, external models, image services or emission.
"""

from __future__ import annotations

import math

import bpy


def _mesh(name, vertices, faces, materials, material_indices=None, smooth=False):
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    for material in materials:
        mesh.materials.append(material)
    for polygon in mesh.polygons:
        polygon.use_smooth = smooth
        if material_indices is not None:
            polygon.material_index = material_indices[polygon.index]
    # Dominant-face planar projection, with two texture repetitions per metre.
    # These are material UVs, so faces intentionally share the repeatable tile.
    uv = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        normal = polygon.normal
        axis = max(range(3), key=lambda index: abs(normal[index]))
        for loop_index in polygon.loop_indices:
            co = mesh.vertices[mesh.loops[loop_index].vertex_index].co
            pair = (co.y, co.z) if axis == 0 else (co.x, co.z) if axis == 1 else (co.x, co.y)
            uv.data[loop_index].uv = (pair[0] * 2.0, pair[1] * 2.0)
    obj["asset_part"] = "weapon"
    obj["procedural_source"] = "weapons.py"
    return obj


def _lathe(name, profile, material, sides=10, centre=(0.0, 0.0)):
    """Closed Z-axis lathe from (height, radius) pairs; faceted metal bands."""
    vertices = []
    for z, radius in profile:
        for index in range(sides):
            angle = 2.0 * math.pi * index / sides + math.pi / sides
            vertices.append((centre[0] + radius * math.cos(angle), centre[1] + radius * math.sin(angle), z))
    faces = [tuple(reversed(range(sides)))]
    for row in range(len(profile) - 1):
        for index in range(sides):
            nxt = (index + 1) % sides
            faces.append((row * sides + index, row * sides + nxt, (row + 1) * sides + nxt, (row + 1) * sides + index))
    faces.append(tuple((len(profile) - 1) * sides + index for index in range(sides)))
    return _mesh(name, vertices, faces, [material])


def _plate(name, outline, thickness, material, centre_y=0.0):
    """Extruded XZ polygon, including concave hooked guard silhouettes."""
    area = sum(outline[index][0] * outline[(index + 1) % len(outline)][1] - outline[(index + 1) % len(outline)][0] * outline[index][1] for index in range(len(outline)))
    if area < 0.0:
        outline = list(reversed(outline))
    count = len(outline)
    vertices = [(x, centre_y - thickness * 0.5, z) for x, z in outline]
    vertices += [(x, centre_y + thickness * 0.5, z) for x, z in outline]
    faces = [tuple(range(count)), tuple(reversed(range(count, count * 2)))]
    faces += [(index, index + count, (index + 1) % count + count, (index + 1) % count) for index in range(count)]
    obj = _mesh(name, vertices, faces, [material])
    bevel = obj.modifiers.new(name="Readable edge bevel", type="BEVEL")
    bevel.width = min(thickness * 0.18, 0.004)
    bevel.segments = 1
    bevel.limit_method = "ANGLE"
    bevel.angle_limit = 0.45
    return obj


def _ribbon_blade(name, outer, inner, thicknesses, materials):
    """Continuous sharpened blade with a raised ridge on both faces.

    Two separately drawn rails retain the real crescent shape and sharp edge;
    this does not approximate a curved blade with overlapping primitive cones.
    """
    vertices = []
    for (ox, oz), (ix, iz), thickness in zip(outer, inner, thicknesses):
        # Four front/back facets make the grind visible under actual PBR light.
        for factor, depth in ((0.0, 0.0), (0.16, -0.65), (0.49, -1.0), (0.84, -0.65), (1.0, 0.0), (0.84, 0.65), (0.49, 1.0), (0.16, 0.65)):
            vertices.append((ox + (ix - ox) * factor, thickness * depth, oz + (iz - oz) * factor))
    faces = [tuple(reversed(range(8)))]
    indices = [0]
    for row in range(len(outer) - 1):
        for side in range(8):
            nxt = (side + 1) % 8
            faces.append((row * 8 + side, row * 8 + nxt, (row + 1) * 8 + nxt, (row + 1) * 8 + side))
            indices.append(1 if side in (0, 3, 4, 7) else 0)
    faces.append(tuple((len(outer) - 1) * 8 + index for index in range(8)))
    indices.append(0)
    return _mesh(name, vertices, faces, materials, indices)


def _beaded_ring(name, centre_x, centre_z, outer_radius, inner_radius, depth, material, sides=12, y=-0.02):
    vertices = []
    for cy, radius in ((y - depth * 0.5, outer_radius), (y - depth * 0.5, inner_radius), (y + depth * 0.5, outer_radius), (y + depth * 0.5, inner_radius)):
        for index in range(sides):
            angle = 2.0 * math.pi * index / sides
            vertices.append((centre_x + radius * math.cos(angle), cy, centre_z + radius * math.sin(angle)))
    faces = []
    for index in range(sides):
        nxt = (index + 1) % sides
        faces.extend(((index, nxt, sides + nxt, sides + index),
                      (2 * sides + index, 3 * sides + index, 3 * sides + nxt, 2 * sides + nxt),
                      (index, 2 * sides + index, 2 * sides + nxt, nxt),
                      (sides + index, sides + nxt, 3 * sides + nxt, 3 * sides + index)))
    return _mesh(name, vertices, faces, [material])


def _wrap(name, z_start, z_end, radius, material, turns=7, centre_x=0.0):
    """Continuous helical leather strip, with a slightly irregular worn edge."""
    steps = turns * 9
    pitch = (z_end - z_start) / turns
    vertices = []
    for step in range(steps + 1):
        angle = 2.0 * math.pi * turns * step / steps
        z = z_start + (z_end - z_start) * step / steps
        width = pitch * (0.66 + 0.09 * math.sin(step * 2.17))
        r = radius * (1.0 + 0.025 * math.sin(step * 0.87))
        vertices.extend(((centre_x + r * math.cos(angle), r * math.sin(angle), z - width * 0.5),
                         (centre_x + r * math.cos(angle), r * math.sin(angle), z + width * 0.5)))
    faces = [(2 * step, 2 * step + 2, 2 * step + 3, 2 * step + 1) for step in range(steps)]
    return _mesh(name, vertices, faces, [material], smooth=True)


def _diamond(name, x, z, width, height, material, y=-0.04, thickness=0.004):
    return _plate(name, [(x, z - height * 0.5), (x + width * 0.5, z), (x, z + height * 0.5), (x - width * 0.5, z)], thickness, material, y)


def _iron_penitent(m):
    prefix = "iron_penitent_"
    parts = []
    outer = [(-0.104, 0.12), (-0.11, 0.25), (-0.098, 0.35), (-0.083, 0.85), (-0.063, 1.02), (-0.001, 1.15)]
    inner = [(-x, z) for x, z in outer]
    parts.append(_ribbon_blade(prefix + "ridged_longsword", outer, inner, [0.026, 0.027, 0.025, 0.02, 0.015, 0.001], [m["blade"], m["silver"]]))
    # Paired dark-steel fuller beds sit beside the central ridge. The relief is
    # shallow and uses real geometry/material contrast instead of baked light.
    for side in (-1, 1):
        x = side * 0.029
        parts.append(_plate(prefix + "fuller_" + str(side), [(x - 0.007, 0.32), (x + 0.007, 0.32), (x + 0.0035, 0.87), (x, 0.95), (x - 0.0035, 0.87)], 0.002, m["steel"], -0.025))
    guard = [(-0.24, 0.073), (-0.229, 0.142), (-0.194, 0.176), (-0.188, 0.125), (-0.078, 0.125), (-0.052, 0.149), (0.052, 0.149), (0.078, 0.125), (0.188, 0.125), (0.194, 0.176), (0.229, 0.142), (0.24, 0.073), (0.205, 0.079), (0.164, 0.09), (0.071, 0.078), (0.045, 0.056), (-0.045, 0.056), (-0.071, 0.078), (-0.164, 0.09), (-0.205, 0.079)]
    parts.append(_plate(prefix + "gothic_quillons", guard, 0.064, m["steel"]))
    parts.append(_diamond(prefix + "guard_escutcheon", 0.0, 0.105, 0.073, 0.097, m["bronze"], -0.036, 0.011))
    parts.append(_diamond(prefix + "guard_inlay", 0.0, 0.108, 0.029, 0.055, m["bone"], -0.043, 0.004))
    parts.append(_lathe(prefix + "grip", [(-0.22, 0.024), (-0.19, 0.027), (0.042, 0.026), (0.073, 0.031)], m["leather"]))
    parts.append(_wrap(prefix + "leather_binding", -0.194, 0.04, 0.028, m["leather"], 8))
    for index, z in enumerate((-0.202, 0.055)):
        parts.append(_lathe(prefix + "grip_ferrule_" + str(index), [(z - 0.008, 0.027), (z - 0.004, 0.032), (z + 0.004, 0.032), (z + 0.008, 0.027)], m["bronze"]))
    parts.append(_lathe(prefix + "pommel", [(-0.27, 0.015), (-0.257, 0.033), (-0.235, 0.041), (-0.214, 0.025)], m["steel"], 8))
    parts.append(_beaded_ring(prefix + "pommel_sigil", 0.0, -0.237, 0.023, 0.016, 0.004, m["bronze"], 12, -0.038))
    parts.append(_diamond(prefix + "pommel_bone", 0.0, -0.237, 0.017, 0.025, m["bone"], -0.04))
    return parts


def _ash_reaver(m):
    prefix = "ash_reaver_"
    parts = []
    outer = [(-0.03, 0.145), (-0.05, 0.29), (-0.014, 0.445), (0.083, 0.57), (0.225, 0.637), (0.375, 0.575), (0.458, 0.435)]
    inner = [(0.035, 0.145), (0.035, 0.28), (0.068, 0.369), (0.15, 0.435), (0.259, 0.475), (0.363, 0.49), (0.457, 0.436)]
    parts.append(_ribbon_blade(prefix + "hooked_sickle", outer, inner, [0.023, 0.026, 0.025, 0.024, 0.019, 0.012, 0.001], [m["blade"], m["silver"]]))
    # A reinforced spine and a blunt thorn identify the sacrificial implement.
    parts.append(_plate(prefix + "spine_collar", [(-0.058, 0.272), (-0.049, 0.366), (-0.002, 0.409), (0.032, 0.387), (0.015, 0.35), (0.015, 0.271)], 0.059, m["steel"]))
    parts.append(_plate(prefix + "spine_thorn", [(-0.046, 0.298), (-0.15, 0.328), (-0.101, 0.359), (-0.031, 0.346)], 0.037, m["steel"]))
    parts.append(_lathe(prefix + "blackwood_grip", [(-0.205, 0.027), (-0.17, 0.025), (0.075, 0.025), (0.135, 0.032)], m["wood"], 10))
    parts.append(_wrap(prefix + "worn_grip_wraps", -0.158, 0.085, 0.027, m["wraps"], 8))
    for index, z in enumerate((-0.179, 0.116)):
        parts.append(_lathe(prefix + "grip_band_" + str(index), [(z - 0.013, 0.027), (z - 0.007, 0.034), (z + 0.007, 0.034), (z + 0.013, 0.027)], m["bronze"]))
    parts.append(_plate(prefix + "finger_guard", [(-0.061, 0.102), (-0.053, 0.127), (0.038, 0.127), (0.112, 0.072), (0.131, -0.037), (0.102, -0.136), (0.061, -0.173), (0.042, -0.154), (0.081, -0.111), (0.103, -0.029), (0.088, 0.047), (0.026, 0.089)], 0.028, m["steel"]))
    parts.append(_lathe(prefix + "pointed_pommel", [(-0.244, 0.008), (-0.222, 0.034), (-0.2, 0.03), (-0.186, 0.025)], m["steel"], 8))
    parts.append(_beaded_ring(prefix + "reaper_eye", 0.175, 0.533, 0.027, 0.018, 0.004, m["bronze"], 10, -0.024))
    parts.append(_diamond(prefix + "bone_mark", 0.175, 0.533, 0.019, 0.03, m["bone"], -0.026))
    parts.append(_diamond(prefix + "neck_rivet", -0.012, 0.316, 0.023, 0.032, m["bronze"], -0.033))
    return parts


def _veil_warden(m):
    prefix = "veil_warden_"
    parts = []
    parts.append(_lathe(prefix + "ritual_shaft", [(-0.59, 0.026), (-0.52, 0.028), (0.53, 0.026), (0.72, 0.033)], m["wood"], 10))
    parts.append(_wrap(prefix + "central_grip", -0.21, 0.19, 0.03, m["leather"], 10))
    parts.append(_wrap(prefix + "forward_grip", 0.39, 0.56, 0.029, m["wraps"], 5))
    for index, z in enumerate((-0.53, -0.227, 0.211, 0.578, 0.683)):
        parts.append(_lathe(prefix + "shaft_ferrule_" + str(index), [(z - 0.01, 0.029), (z - 0.005, 0.034), (z + 0.005, 0.034), (z + 0.01, 0.029)], m["silver"] if index in (1, 2) else m["bronze"], 10))
    parts.append(_lathe(prefix + "butt_spike", [(-0.655, 0.003), (-0.609, 0.027), (-0.566, 0.03)], m["steel"], 8))
    # Tall crescent glaive: the sharpened inner rail opens toward the front of
    # the silhouette while a reinforced neck joins the wooden staff directly.
    outer = [(-0.038, 0.69), (-0.102, 0.79), (-0.104, 0.96), (-0.054, 1.095), (0.06, 1.176), (0.198, 1.205), (0.312, 1.156)]
    inner = [(0.039, 0.69), (0.057, 0.797), (0.028, 0.91), (0.039, 1.015), (0.103, 1.096), (0.204, 1.146), (0.311, 1.155)]
    parts.append(_ribbon_blade(prefix + "crescent_glaive", outer, inner, [0.026, 0.032, 0.031, 0.027, 0.023, 0.014, 0.001], [m["blade"], m["silver"]]))
    parts.append(_plate(prefix + "gothic_socket", [(-0.052, 0.667), (-0.058, 0.819), (-0.042, 0.863), (0.0, 0.891), (0.042, 0.863), (0.058, 0.819), (0.052, 0.667)], 0.075, m["steel"]))
    parts.append(_plate(prefix + "socket_band", [(-0.057, 0.702), (0.057, 0.702), (0.059, 0.726), (-0.059, 0.726)], 0.08, m["bronze"]))
    # Pointed-arch miniature reliquary, with a bone relic beneath a metal frame.
    x, z = -0.029, 0.936
    outer_frame = [(x - 0.039, z - 0.046), (x + 0.039, z - 0.046), (x + 0.037, z + 0.019), (x, z + 0.062), (x - 0.037, z + 0.019)]
    parts.append(_plate(prefix + "reliquary_case", outer_frame, 0.016, m["bronze"], -0.034))
    inner_frame = [(x - 0.025, z - 0.032), (x + 0.025, z - 0.032), (x + 0.024, z + 0.014), (x, z + 0.043), (x - 0.024, z + 0.014)]
    parts.append(_plate(prefix + "reliquary_recess", inner_frame, 0.005, m["inner"], -0.045))
    parts.append(_diamond(prefix + "enshrined_relic", x, z + 0.002, 0.023, 0.054, m["bone"], -0.05, 0.007))
    parts.append(_plate(prefix + "reliquary_crossbar", [(x - 0.03, z - 0.01), (x + 0.03, z - 0.01), (x + 0.03, z - 0.004), (x - 0.03, z - 0.004)], 0.005, m["silver"], -0.055))
    parts.append(_plate(prefix + "back_spur", [(-0.052, 0.79), (-0.199, 0.733), (-0.155, 0.815), (-0.055, 0.844)], 0.038, m["steel"]))
    return parts


def build_weapon(kind, materials):
    """Build an original weapon and return all created objects in grip space."""
    builders = {
        "iron_penitent": _iron_penitent,
        "ash_reaver": _ash_reaver,
        "veil_warden": _veil_warden,
    }
    if kind not in builders:
        raise ValueError("Unknown player weapon kind: " + str(kind))
    required = {"steel", "blade", "silver", "bronze", "leather", "wood", "bone", "wraps", "inner"}
    missing = sorted(required.difference(materials))
    if missing:
        raise ValueError("Missing weapon materials: " + ", ".join(missing))
    parts = builders[kind](materials)
    for part in parts:
        part["weapon_kind"] = kind
        part["grip_space"] = "origin=grip_centre; length=+Z; front=-Y"
    return parts
