"""The shot: lighting rig, cameras, floor patch and render settings.

Taken straight from the look-dev spike that ADR-0014 was decided on, so these
characters are seen under the same light and the same tone mapping the game was
signed off with: cool moon key, warm torch fill, hemisphere ambient, Eevee with
shadow maps, Khronos PBR Neutral view transform and the spike's bloom.

Light energies come from the spike's calibrated conversion (light_scale
8.1668, the value that puts the arena floor's display median at 0.18), so a
torch here is as bright as a torch there. Hero lights sit at fixed world
positions rather than positions scaled by character height, so all three
characters are exposed identically and can go side by side on one sheet.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

import matlib
import palette as P


# --------------------------------------------------------------- scene ---
def reset_scene():
    """Empty the factory-startup scene: no default cube, camera or light."""
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.armatures,
                  bpy.data.cameras, bpy.data.lights, bpy.data.worlds):
        for item in list(block):
            block.remove(item, do_unlink=True)
    return bpy.context.scene


def setup_render(scene, width, height, samples=None, compositing=True,
                 view_transform=None):
    scene.render.engine = 'BLENDER_EEVEE'
    ee = scene.eevee
    ee.use_raytracing = False
    ee.use_shadows = True
    ee.taa_render_samples = int(samples or P.POST["samples"])
    scene.render.use_motion_blur = False
    scene.render.filter_size = P.POST["filter"]
    scene.render.dither_intensity = 0.0
    scene.render.resolution_x, scene.render.resolution_y = int(width), int(height)
    scene.render.resolution_percentage = 100
    scene.render.use_border = False
    scene.render.film_transparent = False
    scene.display_settings.display_device = 'sRGB'
    scene.view_settings.view_transform = view_transform or P.POST["view_transform"]
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    scene.render.use_compositing = bool(compositing)
    if compositing:
        build_compositor(scene)
    return dict(engine=scene.render.engine, samples=ee.taa_render_samples,
                view_transform=scene.view_settings.view_transform,
                resolution=[int(width), int(height)])


def build_compositor(scene):
    """The spike's bloom, unchanged."""
    name = "post_stack"
    if name in bpy.data.node_groups:
        scene.compositing_node_group = bpy.data.node_groups[name]
        return
    tree = bpy.data.node_groups.new(name, "CompositorNodeTree")
    rl = tree.nodes.new("CompositorNodeRLayers")
    rl.scene = scene
    gl = tree.nodes.new("CompositorNodeGlare")
    for token in ("Bloom", "BLOOM"):
        try:
            gl.inputs["Type"].default_value = token
            break
        except (TypeError, ValueError):
            continue
    for sock, key in (("Quality", "bloom_quality"), ("Threshold", "bloom_threshold"),
                      ("Smoothness", "bloom_smoothness"), ("Strength", "bloom_strength"),
                      ("Size", "bloom_size")):
        try:
            gl.inputs[sock].default_value = P.POST[key]
        except (TypeError, ValueError, KeyError):
            pass
    out = tree.nodes.new("NodeGroupOutput")
    tree.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
    tree.links.new(rl.outputs["Image"], gl.inputs["Image"])
    tree.links.new(gl.outputs["Image"], out.inputs[0])
    scene.compositing_node_group = tree


# --------------------------------------------------------------- world ---
def build_world(scene):
    """Hemisphere ambient for surfaces, near-black void for the camera ray."""
    w = bpy.data.worlds.new("world")
    scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -1.0
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = 'RGBA'
    mix.inputs["A"].default_value = P.rgba(P.AMBIENT["ground"])
    mix.inputs["B"].default_value = P.rgba(P.AMBIENT["sky"])
    amb = nt.nodes.new("ShaderNodeBackground")
    amb.name = "ambient_bg"
    amb.inputs["Strength"].default_value = P.LIGHT_SCALE * P.AMBIENT["intensity"] / P.UNITS["k_world"]
    void = nt.nodes.new("ShaderNodeBackground")
    void.inputs["Color"].default_value = P.rgba(P.VOID)
    lp = nt.nodes.new("ShaderNodeLightPath")
    ms = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], amb.inputs["Color"])
    nt.links.new(lp.outputs["Is Camera Ray"], ms.inputs["Fac"])
    nt.links.new(amb.outputs[0], ms.inputs[1])
    nt.links.new(void.outputs[0], ms.inputs[2])
    nt.links.new(ms.outputs[0], out.inputs["Surface"])
    return w


# -------------------------------------------------------------- lights ---
def add_sun(name="moon", direction=None, color=None, design_intensity=None, shadow=True):
    ld = bpy.data.lights.new(name, 'SUN')
    ld.color = P.hex_lin(color or P.MOON["color"])
    ld.angle = math.radians(P.MOON["angle_deg"])
    ld.use_shadow = shadow
    ob = bpy.data.objects.new(name, ld)
    ob.rotation_euler = Vector(direction or P.MOON["dir"]).normalized().to_track_quat('-Z', 'Y').to_euler()
    ld.energy = P.LIGHT_SCALE * float(design_intensity or P.MOON["intensity"]) / P.UNITS["k_sun"]
    bpy.context.collection.objects.link(ob)
    return ob


def add_point(name, pos, color, design_intensity, radius, shadow=False, soft=None):
    ld = bpy.data.lights.new(name, 'POINT')
    ld.color = P.hex_lin(color)
    ld.shadow_soft_size = P.POINT_SOFT_RADIUS if soft is None else float(soft)
    ld.use_custom_distance = True
    ld.cutoff_distance = float(radius)
    ld.use_shadow = bool(shadow)
    ld.energy = P.LIGHT_SCALE * float(design_intensity) / P.UNITS["k_point"]
    ob = bpy.data.objects.new(name, ld)
    ob.location = tuple(pos)
    bpy.context.collection.objects.link(ob)
    return ob


def hero_rig():
    """Three-point dark-fantasy rig at fixed world positions.

    Cool moon key from above-left, warm torch from front-right at the height of
    a wall sconce, cold rim from behind so the silhouette separates from the
    void -- the same colours the style bible lists for moon, torch and staff orb.
    """
    # Design intensities are calibrated for the arena, where a torch is about 9 m
    # from what it lights. A hero light sits ~3.5 m away, so the same number
    # delivers (9/3.5)^2 ~ 6.6x the irradiance and clips skin (albedo 0.19) to
    # white -- which is what hid the texture in the first pass. The dark floor
    # (albedo 0.033) still looked right, which is how the overexposure hid.
    near = (3.5 / 9.0) ** 2
    lights = [add_sun("moon", design_intensity=P.MOON["intensity"] * 0.55, shadow=True)]
    lights.append(add_point("key_torch", (1.85, 2.15, 2.35), P.LIGHT_COLORS["torch"],
                            6.0 * near, 12.0, shadow=True, soft=0.25))
    lights.append(add_point("fill_moon", (-2.45, 1.70, 1.05), P.LIGHT_COLORS["moon"],
                            1.6 * near, 10.0, shadow=False, soft=0.5))
    lights.append(add_point("rim_orb", (-1.15, -2.40, 2.15), P.LIGHT_COLORS["orb"],
                            2.6 * near, 10.0, shadow=False, soft=0.3))
    lights.append(add_point("ground_ember", (0.9, -1.6, 0.18), P.LIGHT_COLORS["ember"],
                            0.7 * near, 4.0, shadow=False))
    return lights


def arena_rig(radius=6.0, n_torches=6):
    """Sconce ring for the in-game view.

    Same correction as hero_rig: this showcase arena is ~17 m across, not the
    40 m one the design intensities were calibrated on, so every sconce is 3-4 m
    from the floor it lights instead of ~9 m. At full design intensity the floor
    burns out to pink and the whole dark-fantasy palette is lost.
    """
    near = (4.0 / 9.0) ** 2
    out = [add_sun("moon", design_intensity=P.MOON["intensity"] * 0.7, shadow=True)]
    for k in range(n_torches):
        a = 2 * math.pi * k / n_torches + 0.3
        out.append(add_point("torch_%d" % k, (radius * math.cos(a), radius * math.sin(a), 2.3),
                             P.LIGHT_COLORS["torch"], 6.0 * near, 14.0,
                             shadow=(k % 2 == 0), soft=0.2))
    for k in range(4):
        a = math.pi / 4 + math.pi / 2 * k
        out.append(add_point("ritual_%d" % k, (2.6 * math.cos(a), 2.6 * math.sin(a), 0.5),
                             P.LIGHT_COLORS["ritual"], 2.0 * near, 6.0))
    return out


# ------------------------------------------------------------- cameras ---
def _aim(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def hero_camera(scene, height, width_px, height_px, azimuth_deg=35.0, elevation_deg=17.0,
                fit=1.30, vfov_deg=35.0, yaw_deg=0.0):
    """Three-quarter view framed on a character of the given height."""
    cam = bpy.data.cameras.new("hero_cam")
    cam.sensor_fit = 'VERTICAL'
    cam.angle_y = math.radians(vfov_deg)
    cam.clip_start, cam.clip_end = 0.05, 200.0
    ob = bpy.data.objects.new("hero_cam", cam)
    bpy.context.collection.objects.link(ob)
    target = Vector((0.0, 0.0, height * 0.52))
    dist = (height * fit) / (2.0 * math.tan(math.radians(vfov_deg) / 2.0))
    az = math.radians(azimuth_deg + yaw_deg)
    el = math.radians(elevation_deg)
    # Characters are built facing +Y, so the hero camera belongs on the +Y side
    # looking back at them. Putting it on -Y (the gameplay camera's side) shows
    # the character's back, which is what the first pass did.
    ob.location = target + Vector((math.sin(az) * math.cos(el),
                                   math.cos(az) * math.cos(el),
                                   math.sin(el))) * dist
    _aim(ob, target)
    scene.camera = ob
    scene.render.resolution_x, scene.render.resolution_y = int(width_px), int(height_px)
    return ob


def game_camera(scene, width_px, height_px, target=(0.0, 0.0, 0.9), distance=11.0,
                pitch_deg=65.0, vfov_deg=35.0):
    """The gameplay camera: tilted top-down at 65 degrees (PRD-0003 FR-03)."""
    cam = bpy.data.cameras.new("game_cam")
    cam.sensor_fit = 'VERTICAL'
    cam.angle_y = math.radians(vfov_deg)
    cam.clip_start, cam.clip_end = 0.5, 200.0
    ob = bpy.data.objects.new("game_cam", cam)
    bpy.context.collection.objects.link(ob)
    p = math.radians(pitch_deg)
    tx, ty, tz = target
    ob.location = (tx, ty - distance * math.cos(p), tz + distance * math.sin(p))
    ob.rotation_euler = (math.radians(90.0 - pitch_deg), 0.0, 0.0)
    scene.camera = ob
    scene.render.resolution_x, scene.render.resolution_y = int(width_px), int(height_px)
    return ob


# --------------------------------------------------------------- floor ---
def floor_patch(extent=3.2, tile=0.8, gap=0.035, tex_dir=None, name="floor"):
    """Tiled stone floor: a grout slab with individual tile quads on top.

    UVs are world-scaled (metres / tile_size_m) so the floor texture reads at
    exactly the density the texture set was authored for.
    """
    matlib.ensure_materials(["floor_stone", "grout"], tex_dir)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new(P.UV_NAME)
    mat_layer = bm.faces.layers.int.new("slot")
    grout_tile = matlib.tile_size_for("grout", tex_dir) or 1.0
    stone_tile = matlib.tile_size_for("floor_stone", tex_dir) or 1.0

    def quad(x0, y0, x1, y1, z, slot, tile_m):
        vs = [bm.verts.new((x0, y0, z)), bm.verts.new((x1, y0, z)),
              bm.verts.new((x1, y1, z)), bm.verts.new((x0, y1, z))]
        f = bm.faces.new(vs)
        f[mat_layer] = slot
        for loop in f.loops:
            co = loop.vert.co
            loop[uv].uv = (co.x / tile_m, co.y / tile_m)
        return f

    quad(-extent, -extent, extent, extent, -0.012, 1, grout_tile)
    n = int(extent * 2 / tile)
    start = -n * tile / 2.0
    for i in range(n):
        for j in range(n):
            x0 = start + i * tile + gap / 2
            y0 = start + j * tile + gap / 2
            quad(x0, y0, x0 + tile - gap, y0 + tile - gap, 0.0, 0, stone_tile)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(bpy.data.materials["floor_stone"])
    me.materials.append(bpy.data.materials["grout"])
    attr = me.attributes.get("slot")
    if attr is not None:
        me.polygons.foreach_set("material_index", [int(d.value) for d in attr.data])
        me.attributes.remove(attr)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def pillar(pos, height=4.0, radius=0.42, tex_dir=None, name="pillar"):
    """A fluted arena pillar for the in-game view."""
    matlib.ensure_materials(["pillar"], tex_dir)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new(P.UV_NAME)
    tile = matlib.tile_size_for("pillar", tex_dir) or 1.0
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=16,
                          radius1=radius * 1.22, radius2=radius, depth=height)
    for v in bm.verts:
        v.co.z += height / 2.0
    for f in bm.faces:
        for loop in f.loops:
            co = loop.vert.co
            loop[uv].uv = (math.atan2(co.y, co.x) * radius / tile, co.z / tile)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(bpy.data.materials["pillar"])
    me.update()
    ob = bpy.data.objects.new(name, me)
    ob.location = tuple(pos)
    bpy.context.collection.objects.link(ob)
    return ob


def altar(pos, tex_dir=None, name="altar"):
    """A low basalt altar block with a stepped base."""
    matlib.ensure_materials(["altar"], tex_dir)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new(P.UV_NAME)
    tile = matlib.tile_size_for("altar", tex_dir) or 1.0
    for (sx, sy, sz, z0) in ((1.30, 0.95, 0.16, 0.0), (1.05, 0.72, 0.52, 0.16),
                             (1.34, 1.00, 0.14, 0.68)):
        tmp = bmesh.new()
        bmesh.ops.create_cube(tmp, size=1.0)
        for v in tmp.verts:
            v.co.x *= sx
            v.co.y *= sy
            v.co.z = v.co.z * sz + z0 + sz / 2.0
        tmp.to_mesh(bpy.data.meshes.new("tmp"))
        for v in tmp.verts:
            bm.verts.new(v.co)
        bm.verts.ensure_lookup_table()
        base = len(bm.verts) - len(tmp.verts)
        for f in tmp.faces:
            bm.faces.new([bm.verts[base + v.index] for v in f.verts])
        tmp.free()
    for f in bm.faces:
        for loop in f.loops:
            co = loop.vert.co
            loop[uv].uv = ((co.x + co.y) / tile, co.z / tile)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(bpy.data.materials["altar"])
    me.update()
    ob = bpy.data.objects.new(name, me)
    ob.location = tuple(pos)
    bpy.context.collection.objects.link(ob)
    return ob


# -------------------------------------------------------------- render ---
def render_to(scene, path):
    import os
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    s = scene.render.image_settings
    s.file_format = 'PNG'
    s.color_mode = 'RGB'
    s.color_depth = '8'
    s.compression = 15
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def load_png(path):
    """Read a rendered PNG back as uint8 HxWx3 (top row first)."""
    img = bpy.data.images.load(path)
    w, h = img.size
    arr = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(arr)
    bpy.data.images.remove(img)
    rgb = arr.reshape(h, w, 4)[::-1, :, :3]
    return np.round(np.clip(rgb, 0.0, 1.0) * 255.0).astype(np.uint8)
