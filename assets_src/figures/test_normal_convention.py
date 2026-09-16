"""Do normalmap.height_to_normal and shapenormal.shape_normal_map agree with
Blender's own tangent-space normal bake? On this simple, well-separated dome
that bake is trustworthy, so it is the reference for the convention (which
axis, which sign) both of them must follow -- the engine was checked against
the same convention.

A known dome is displaced into a dense grid (high), baked selected-to-active
onto a flat, UV-mapped plane (low), read back with the same row flip the build
uses, and compared per axis with height_to_normal applied to the same dome in
the same image orientation. The dome sits off-centre so that a swapped or
mirrored axis cannot hide behind symmetry.

  blender -b --factory-startup --python test_normal_convention.py

Prints the correlation per axis for both and NORMAL_CONVENTION_OK True/False.
A correlation near -1 on one axis means that channel is inverted.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import normalmap as NM  # noqa: E402
import shapenormal as SN  # noqa: E402

RES = 128
CX, CY, RADIUS, PEAK = 0.12, 0.20, 0.18, 0.03


def dome(x, y):
    r = np.sqrt((x - CX) ** 2 + (y - CY) ** 2) / RADIUS
    return PEAK * np.clip(1.0 - r * r, 0.0, None) ** 2


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 4

    bpy.ops.mesh.primitive_grid_add(x_subdivisions=240, y_subdivisions=240, size=1.0)
    high = bpy.context.object
    for v in high.data.vertices:
        v.co.z = float(dome(v.co.x, v.co.y))
    high.data.update()
    bpy.ops.object.shade_smooth()

    bpy.ops.mesh.primitive_plane_add(size=1.0)
    low = bpy.context.object
    mat = bpy.data.materials.new("bake_target")
    mat.use_nodes = True
    low.data.materials.append(mat)
    img = bpy.data.images.new("nrm", RES, RES, alpha=False, float_buffer=True)
    img.colorspace_settings.name = 'Non-Color'
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = img
    mat.node_tree.nodes.active = node

    bpy.ops.object.select_all(action='DESELECT')
    high.select_set(True)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    bpy.ops.object.bake(type='NORMAL', use_selected_to_active=True, cage_extrusion=0.05,
                        max_ray_distance=0.1, normal_space='TANGENT')

    buf = np.empty(RES * RES * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    baked = buf.reshape(RES, RES, 4)[::-1, :, :3].astype(np.float64) * 2.0 - 1.0  # row 0 = top

    # Same orientation as the baked image: row 0 is the top (v = 1), column 0 is u = 0.
    # The plane's UV (0,0) sits at (-0.5, -0.5) with u along +x and v along +y.
    cols = (np.arange(RES) + 0.5) / RES
    rows = (np.arange(RES) + 0.5) / RES
    u, v = np.meshgrid(cols, 1.0 - rows)
    height = dome(u - 0.5, v - 0.5)
    ours = NM.height_to_normal(height, (1.0 / RES, 1.0 / RES))

    surface = SN.high_surface(high)
    frames = SN.low_corner_frames(low, low.data.uv_layers.active.name)
    shape, _filled, _core, _folded = SN.shape_normal_map(surface, frames, 0, RES, 0)

    inside = np.sqrt((u - 0.5 - CX) ** 2 + (v - 0.5 - CY) ** 2) < RADIUS * 0.95
    ok = True
    for source, field in (("height_to_normal", ours), ("shape_normal_map", shape)):
        for axis, label in ((0, "x (rot)"), (1, "y (gruen)")):
            a, b = baked[..., axis][inside], field[..., axis][inside]
            corr = float(np.corrcoef(a, b)[0, 1])
            print("NORMAL_CONVENTION %-16s axis %-9s correlation %+.3f  (baked range %+.3f..%+.3f)"
                  % (source, label, corr, a.min(), a.max()))
            ok = ok and corr > 0.9
    print("NORMAL_CONVENTION_OK", ok)
    if not ok:
        sys.exit(1)


main()
