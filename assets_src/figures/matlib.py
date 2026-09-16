"""Materials: textured Principled BSDF from the snapshot, flat fallback otherwise.

Same shading contract as the look-dev spike's "realistic_tex" look, which is what
ADR-0014 accepted: glTF metallic-roughness, base colour in sRGB, tangent-space
normal map, roughness and metallic from the G and B channels of the ORM texture.

The ORM red channel (ambient occlusion) is deliberately NOT wired in: Eevee's
Principled BSDF has no socket that folds a supplied AO map into indirect light
only, and faking it means multiplying it into the base colour, which darkens
direct light too. The spike made the same call; it is reported, not hidden.
"""
import os

import bpy

import palette as P

_IMAGE_CACHE = {}


def _images(tex_id, tex_dir):
    if tex_id in _IMAGE_CACHE:
        return _IMAGE_CACHE[tex_id]
    mat_dir = os.path.join(tex_dir, tex_id)

    def load(suffix, colorspace):
        img = bpy.data.images.load(os.path.join(mat_dir, "%s_%s.png" % (tex_id, suffix)),
                                   check_existing=True)
        img.colorspace_settings.name = colorspace
        return img

    imgs = dict(basecolor=load("basecolor", "sRGB"),
                normal=load("normal", "Non-Color"),
                orm=load("orm", "Non-Color"))
    _IMAGE_CACHE[tex_id] = imgs
    return imgs


def make_material(key, tex_dir):
    """Build (or reuse) the material named `key`."""
    if key in bpy.data.materials:
        return bpy.data.materials[key]
    mat = bpy.data.materials.new(key)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    spec = P.MATERIALS[key]
    tex_id = P.MATERIAL_TEXTURE_MAP.get(key)
    if tex_id is None or tex_dir is None:
        # Flat style-bible colour: no texture in the delivered set covers this.
        bsdf.inputs["Base Color"].default_value = P.rgba(spec["albedo"])
        bsdf.inputs["Roughness"].default_value = max(spec["r"], P.POST["rough_min"])
        bsdf.inputs["Metallic"].default_value = spec["m"]
        mat["textured"] = 0
        return mat
    imgs = _images(tex_id, tex_dir)
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = P.UV_NAME
    base = nt.nodes.new("ShaderNodeTexImage")
    base.image = imgs["basecolor"]
    base.extension = 'REPEAT'
    nt.links.new(uv.outputs["UV"], base.inputs["Vector"])
    nt.links.new(base.outputs["Color"], bsdf.inputs["Base Color"])
    orm_tex = nt.nodes.new("ShaderNodeTexImage")
    orm_tex.image = imgs["orm"]
    orm_tex.extension = 'REPEAT'
    nt.links.new(uv.outputs["UV"], orm_tex.inputs["Vector"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(orm_tex.outputs["Color"], sep.inputs["Color"])
    # Roughness floor: the realistic look needs >= 0.25 for specular anti-aliasing.
    rmax = nt.nodes.new("ShaderNodeMath")
    rmax.operation = 'MAXIMUM'
    rmax.inputs[1].default_value = P.POST["rough_min"]
    nt.links.new(sep.outputs["Green"], rmax.inputs[0])
    nt.links.new(rmax.outputs[0], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    nrm_tex = nt.nodes.new("ShaderNodeTexImage")
    nrm_tex.image = imgs["normal"]
    nrm_tex.extension = 'REPEAT'
    nt.links.new(uv.outputs["UV"], nrm_tex.inputs["Vector"])
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nmap.uv_map = P.UV_NAME
    nt.links.new(nrm_tex.outputs["Color"], nmap.inputs["Color"])
    nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    mat["textured"] = 1
    mat["tile_size_m"] = P.load_tile_size(tex_dir, tex_id)[0]
    return mat


def make_emissive(key):
    """Emissive mesh material (staff orb, brute eyes)."""
    if key in bpy.data.materials:
        return bpy.data.materials[key]
    spec = P.EMISSIVE[key]
    mat = bpy.data.materials.new(key)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = P.rgba(spec["color"])
    em.inputs["Strength"].default_value = spec["mult"]
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    mat["textured"] = 0
    return mat


def ensure_materials(keys, tex_dir):
    """Create every material a character needs; returns a texture-coverage report."""
    report = {}
    for key in keys:
        if key in P.EMISSIVE:
            make_emissive(key)
            report[key] = "emissive"
            continue
        mat = make_material(key, tex_dir)
        report[key] = ("textured:" + P.MATERIAL_TEXTURE_MAP[key]) if mat.get("textured") \
            else ("flat:" + P.MATERIALS[key]["albedo"])
    return report


def tile_size_for(key, tex_dir):
    """Tile size in metres for a material, or None when it has no texture."""
    tex_id = P.MATERIAL_TEXTURE_MAP.get(key)
    if tex_id is None or tex_dir is None:
        return None
    return P.load_tile_size(tex_dir, tex_id)[0]


def pack_all_images():
    """Pack the textures into the .blend so the deliverable is self-contained."""
    n = 0
    for img in bpy.data.images:
        if img.source == 'FILE' and not img.packed_file:
            try:
                img.pack()
                n += 1
            except RuntimeError:
                pass
    return n
