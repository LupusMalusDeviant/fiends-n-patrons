"""Rebuild three rigged PBR character prototypes with headless Blender.

Usage: blender -b --factory-startup --python build.py -- --render
All output stays in this directory's ignored generated/ folder. No downloads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from weapons import build_weapon

TAU = math.tau
PARTS = []
SCALE = Vector((1, 1, 1))
MATERIALS = {}


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def scaled(p):
    return Vector((p[0] * SCALE.x, p[1] * SCALE.y, p[2] * SCALE.z))


def select_only(objects):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


def box_uv(obj, tile=1.0):
    """Physical-scale planar projection per face; no packed texture atlas needed."""
    mesh = obj.data
    uv = mesh.uv_layers.active or mesh.uv_layers.new(name="UVMap")
    for face in mesh.polygons:
        axis = max(range(3), key=lambda i: abs(face.normal[i]))
        axes = ((1, 2), (0, 2), (0, 1))[axis]
        for loop in face.loop_indices:
            co = mesh.vertices[mesh.loops[loop].vertex_index].co
            uv.data[loop].uv = (co[axes[0]] / tile, co[axes[1]] / tile)


def mesh_part(name, vertices, faces, material, bone="chest", smooth=True, weight_fn=None):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([scaled(v) for v in vertices], [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    mesh.materials.append(MATERIALS[material])
    for polygon in mesh.polygons:
        polygon.use_smooth = smooth
    groups = {}
    for i, point in enumerate(vertices):
        weights = weight_fn(point) if weight_fn else {bone: 1.0}
        for joint, weight in weights.items():
            if weight > 0:
                if joint not in groups:
                    groups[joint] = obj.vertex_groups.new(name=joint)
                groups[joint].add([i], weight, 'REPLACE')
    box_uv(obj, MATERIALS[material].get("tile_m", 1.0))
    PARTS.append(obj)
    return obj


def loft(name, sections, material, bone, segments=24, pleats=0, weight_fn=None):
    """Closed elliptical rings (z, radius_x, radius_y, center_y, center_x)."""
    vertices, faces = [], []
    for z, rx, ry, cy, cx in sections:
        for j in range(segments):
            a = TAU * j / segments
            fold = 1 + pleats * math.cos(a * 8)
            vertices.append((cx + rx * math.cos(a) * fold, cy + ry * math.sin(a) * fold, z))
    for k in range(len(sections) - 1):
        for j in range(segments):
            a, b = k * segments + j, k * segments + (j + 1) % segments
            faces.append((a, b, b + segments, a + segments))
    faces.extend([tuple(reversed(range(segments))), tuple((len(sections)-1)*segments+j for j in range(segments))])
    return mesh_part(name, vertices, faces, material, bone, weight_fn=weight_fn)


def limb(name, a, b, radii, material, bone, segments=16):
    a, b = Vector(a), Vector(b)
    direction = (b - a).normalized()
    first = direction.cross(Vector((0, 1, 0))).normalized()
    second = direction.cross(first).normalized()
    vertices, faces = [], []
    for k, (t, radius_x, radius_y) in enumerate(radii):
        center = a.lerp(b, t)
        for j in range(segments):
            angle = TAU * j / segments
            vertices.append(tuple(center + first * math.cos(angle)*radius_x + second * math.sin(angle)*radius_y))
        if k:
            for j in range(segments):
                v, w = (k-1)*segments+j, (k-1)*segments+(j+1)%segments
                faces.append((v, w, w+segments, v+segments))
    faces.extend([tuple(reversed(range(segments))), tuple((len(radii)-1)*segments+j for j in range(segments))])
    return mesh_part(name, vertices, faces, material, bone)


def ellipsoid(name, center, radii, material, bone, segments=16, rings=10):
    vertices = [(center[0], center[1], center[2]+radii[2])]
    for ring in range(1, rings):
        latitude = math.pi*ring/rings
        for j in range(segments):
            angle = TAU*j/segments
            vertices.append((center[0]+radii[0]*math.sin(latitude)*math.cos(angle),
                             center[1]+radii[1]*math.sin(latitude)*math.sin(angle),
                             center[2]+radii[2]*math.cos(latitude)))
    vertices.append((center[0],center[1],center[2]-radii[2]))
    faces = [(0, 1+j, 1+(j+1)%segments) for j in range(segments)]
    for k in range(rings-2):
        for j in range(segments):
            a, b = 1+k*segments+j, 1+k*segments+(j+1)%segments
            faces.append((a,a+segments,b+segments,b))
    last = 1+(rings-2)*segments
    faces += [(len(vertices)-1, last+(j+1)%segments, last+j) for j in range(segments)]
    return mesh_part(name, vertices, faces, material, bone)


def plate(name, outline, y, depth, material, bone, ridge=0.015):
    """Bevelled convex XZ plate with a raised central ridge and solid back."""
    n = len(outline)
    vertices = [(x,y,z) for x,z in outline] + [(x,y+depth,z) for x,z in outline]
    cx = sum(x for x,z in outline)/n
    cz = sum(z for x,z in outline)/n
    vertices += [(cx,y-ridge,cz)]
    faces = [(2*n,j,(j+1)%n) for j in range(n)]
    faces += [(j,n+j,n+(j+1)%n,(j+1)%n) for j in range(n)]
    faces.append(tuple(reversed(range(n,2*n))))
    obj=mesh_part(name, vertices, faces, material, bone, smooth=False)
    bevel=obj.modifiers.new('softened_plate_edges','BEVEL');bevel.width=.0035;bevel.segments=2
    return obj


def tube(name, points, radius, material, bone, sides=8, weight_fn=None):
    vertices, faces = [], []
    for i, p in enumerate(points):
        p = Vector(p)
        d = (Vector(points[min(i+1,len(points)-1)]) - Vector(points[max(0,i-1)])).normalized()
        ref = Vector((0,0,1)) if abs(d.z)<0.9 else Vector((0,1,0))
        u = d.cross(ref).normalized()
        v = d.cross(u)
        for j in range(sides):
            vertices.append(tuple(p+radius*(u*math.cos(TAU*j/sides)+v*math.sin(TAU*j/sides))))
        if i:
            for j in range(sides):
                a,b = (i-1)*sides+j, (i-1)*sides+(j+1)%sides
                faces.append((a,b,b+sides,a+sides))
    faces.extend([tuple(reversed(range(sides))), tuple((len(points)-1)*sides+j for j in range(sides))])
    return mesh_part(name,vertices,faces,material,bone,weight_fn=weight_fn)


def torso_weights(point):
    z=point[2]
    if z < 1.2:
        t=max(0,min(1,(z-1.05)/.15))
        return {"hips":1-t,"spine":t}
    t=max(0,min(1,(z-1.2)/.22))
    return {"spine":1-t,"chest":t}


def build_base(kind):
    heavy=kind=="iron_penitent"
    loft("fitted_gambeson",[(1.01,.19,.125,0,0),(1.13,.18,.13,0,0),
         (1.29,.215,.145,0,0),(1.45,.255,.16,0,0),(1.54,.24,.125,.012,0)],
         "inner","chest",segments=32,pleats=.045,weight_fn=torso_weights)
    loft("pelvis",[(.91,.17,.115,0,0),(1.01,.195,.13,0,0),(1.11,.19,.13,0,0)],"leather","hips")
    loft("gorget_underlayer",[(1.49,.14,.12,0,0),(1.61,.125,.105,0,0),(1.69,.076,.068,0,0)],"inner","neck")
    ellipsoid("head_under_mask",(0,-.006,1.77),(.107,.101,.15),"inner","head")
    for side, sign in (("L",1),("R",-1)):
        shoulder=(sign*.266,0,1.52)
        elbow=(sign*.456,-.013,1.245)
        wrist=(sign*.526,-.083,.994)
        hand=(sign*.526,-.106,.93)
        limb("sleeve_upper_"+side,shoulder,elbow,[(0,.102,.102),(.24,.11,.11),(.72,.085,.083),(1,.074,.07)],"inner","upper_arm."+side)
        ellipsoid("elbow_"+side,elbow,(.077,.076,.077),"leather","forearm."+side,12,8)
        limb("sleeve_lower_"+side,elbow,wrist,[(0,.072,.07),(.24,.084,.08),(.75,.061,.064),(1,.051,.047)],"leather","forearm."+side)
        ellipsoid("glove_"+side,hand,(.059,.044,.075),"leather","hand."+side)
        for finger in range(4):
            x=sign*(.49+finger*.023)
            limb("finger_"+side+str(finger),(x,-.128,.937),(x,-.143,.865),[(0,.014,.014),(.5,.015,.015),(1,.011,.012)],"leather","hand."+side,8)
        ellipsoid("thumb_"+side,(sign*.47,-.128,.932),(.02,.034,.033),"leather","hand."+side,10,6)
        hip=(sign*.115,0,1.0)
        knee=(sign*.14,-.03,.58)
        ankle=(sign*.14,0,.16)
        limb("trouser_upper_"+side,hip,knee,[(0,.107,.102),(.24,.113,.107),(.66,.09,.09),(1,.076,.075)],"inner","thigh."+side)
        ellipsoid("knee_"+side,knee,(.079,.076,.075),"leather","shin."+side,12,8)
        limb("boot_calf_"+side,knee,ankle,[(0,.075,.08),(.24,.093,.087),(.55,.087,.08),(1,.067,.069)],"leather","shin."+side)
        loft("boot_foot_"+side,[(.025,.089,.169,-.074,sign*.14),(.056,.097,.18,-.079,sign*.14),
             (.111,.087,.16,-.074,sign*.14),(.16,.069,.106,-.028,sign*.14),(.205,.067,.065,0,sign*.14)],"leather","foot."+side,20)
        # Soles and toe caps add readable construction at game distance.
        loft("sole_"+side,[(.016,.096,.177,-.076,sign*.14),(.048,.096,.18,-.076,sign*.14)],"inner","foot."+side,20)
        for z in (.29,.47):
            loft("boot_strap_"+side+str(z),[(z-.02,.095,.088,-.012,sign*.14),(z+.02,.095,.088,-.012,sign*.14)],"leather","shin."+side,16)
        if heavy or side=="L":
            x=sign*.14
            plate("greave_"+side,[(x-.064,.52),(x+.064,.52),(x+.071,.43),(x+.051,.21),(x,.17),(x-.051,.21),(x-.071,.43)],-.104,.028,"steel","shin."+side,.025)
            plate("poleyn_"+side,[(x-.091,.602),(x,.653),(x+.091,.602),(x+.065,.543),(x-.065,.543)],-.119,.04,"silver","shin."+side,.026)
        plate("vambrace_"+side,[(sign*(.46-.07),1.20),(sign*(.46+.059),1.17),(sign*.566,1.02),(sign*.505,.997)],-.122,.025,"steel" if heavy else "leather","forearm."+side,.02)


def cape(kind):
    short=kind=="ash_reaver"
    length=.59 if short else (1.15 if kind=="veil_warden" else 1.07)
    columns, rows = 28,18
    vertices,faces=[],[]
    for k in range(rows+1):
        t=k/rows
        for j in range(columns+1):
            u=j/columns*2-1
            width=.275+.19*t
            if short:
                width*=.8+.25*(u+1)/2
            z=1.535-length*t + (t**8)*(.025*math.cos(u*math.pi*5)+.03*abs(u))
            if short: z += .15*u*t
            y=.15+.22*t + .036*math.cos(u*math.pi*7)*math.sin(math.pi*t/2)
            y += .033*(1-u*u)
            vertices.append((u*width,y,z))
    for k in range(rows):
        for j in range(columns):
            a=k*(columns+1)+j
            faces.append((a,a+1,a+columns+2,a+columns+1))
    def weights(p):
        t=max(0,min(1,(1.535-p[2])/length))
        blend=max(0,min(1,(t-.35)/.4))
        if t<.12:return {"chest":1-t/.12,"cape.01":t/.12}
        return {"cape.01":1-blend,"cape.02":blend}
    obj=mesh_part("folded_cape",vertices,faces,"cloak","cape.01",weight_fn=weights)
    solid=obj.modifiers.new("cloth_thickness",'SOLIDIFY');solid.thickness=.009
    # Lower hem is a real cord following the scallops, not a painted shadow.
    points=[vertices[rows*(columns+1)+j] for j in range(columns+1)]
    tube("cape_hem",points,.009,"leather","cape.02",weight_fn=weights)


def skirt_panel(name, side, length, material, width=.145):
    vertices,faces=[],[]
    cols,rows=8,12
    for k in range(rows+1):
        t=k/rows
        for j in range(cols+1):
            u=j/cols*2-1
            x=side*(.104+.06*t)+u*width*(.7+.3*t)
            y=-.161-.065*t+.012*math.cos(u*math.pi*3)
            z=1.08-length*t+.025*t**6*math.cos(u*math.pi*2)
            vertices.append((x,y,z))
    for k in range(rows):
        for j in range(cols):
            a=k*(cols+1)+j;faces.append((a,a+1,a+cols+2,a+cols+1))
    bone="thigh.L" if side>0 else "thigh.R"
    def weights(p):
        t=max(0,min(1,(1.06-p[2])/.22))
        return {"hips":1-t,bone:t}
    obj=mesh_part(name,vertices,faces,material,bone,weight_fn=weights)
    solid=obj.modifiers.new("fabric_thickness",'SOLIDIFY');solid.thickness=.009


def shoulder(name, sign, material, large=True):
    center=(sign*.285,.003,1.50)
    rx=.174 if large else .144
    ry=.165 if large else .137
    rz=.123 if large else .099
    vertices,faces=[],[]
    rings,segments=7,24
    for k in range(rings+1):
        angle=.11 + 1.63*k/rings
        for j in range(segments):
            a=TAU*j/segments
            vertices.append((center[0]+rx*math.sin(angle)*math.cos(a),center[1]+ry*math.sin(angle)*math.sin(a),center[2]+rz*math.cos(angle)))
    for k in range(rings):
        for j in range(segments):
            a=k*segments+j;b=k*segments+(j+1)%segments
            faces.append((a,b,b+segments,a+segments))
    # Close the small polar opening: the pauldron is a shell, not a ring.
    vertices.append((center[0],center[1],center[2]+rz))
    faces += [(len(vertices)-1,j,(j+1)%segments) for j in range(segments)]
    bone="upper_arm.L" if sign>0 else "upper_arm.R"
    obj=mesh_part(name,vertices,faces,material,bone)
    solid=obj.modifiers.new("plate_thickness",'SOLIDIFY');solid.thickness=.014
    tube(name+"_rolled_edge",[vertices[rings*segments+j] for j in range(segments)]+[vertices[rings*segments]],.012,"silver",bone)
    for j in range(5):
        a=math.pi+.25+(.25+j*.13)*math.pi
        ellipsoid(name+"_rivet_"+str(j),(center[0]+rx*.96*math.cos(a),center[1]+ry*.96*math.sin(a),1.49),(.011,.011,.011),"bronze",bone,8,4)


def hood(kind):
    # A continuous draped shell surrounds an open face aperture. Front is -Y.
    is_warden=kind=="veil_warden"
    rows=[(1.55,.166,.14,.02),(1.65,.174,.147,.02),(1.79,.164,.155,.025),
          (1.92,.139,.137,.031),(2.035 if is_warden else 1.995,.047,.063,.023)]
    count=28;vertices=[];faces=[]
    for k,(z,rx,ry,cy) in enumerate(rows):
        for j in range(count+1):
            a=-.70+(math.pi+1.40)*j/count
            vertices.append((rx*math.cos(a),cy+ry*math.sin(a),z+.007*math.cos(j*math.pi/3)))
    for k in range(len(rows)-1):
        for j in range(count):
            a=k*(count+1)+j;faces.append((a,a+1,a+count+2,a+count+1))
    faces.append(tuple((len(rows)-1)*(count+1)+j for j in range(count+1)))
    obj=mesh_part("open_cowl",vertices,faces,"cloak","head")
    solid=obj.modifiers.new("cowl_thickness",'SOLIDIFY');solid.thickness=.018
    for j in (0,count):
        points=[vertices[k*(count+1)+j] for k in range(len(rows))]
        tube("cowl_bound_edge_"+str(j),points,.012,"leather","head")


def mask(kind):
    is_reaver=kind=="ash_reaver"
    # Separate brow, cheeks and nasal ridge leave dark, recessed eye sockets.
    plate("mask_brow",[(-.098,1.844),(-.071,1.89),(0,1.912),(.071,1.89),(.098,1.844),(.079,1.818),(0,1.849),(-.079,1.818)],-.104,.035,"bone","head",.017)
    for sign in (-1,1):
        outline=[(sign*.088,1.816),(sign*.036,1.798),(sign*.023,1.74),(sign*.047,1.691),(sign*.085,1.734)]
        plate("mask_cheek_"+str(sign),outline,-.111,.035,"bone","head",.022)
        tube("mask_eye_rim_"+str(sign),[(sign*.025,-.133,1.819),(sign*.055,-.134,1.815),(sign*.083,-.118,1.825)],.005,"bronze","head",6)
    if is_reaver:
        # Short bone hook, rather than a long bird beak that would hide the torso.
        mesh_part("hooked_nasal",[(-.023,-.132,1.829),(.023,-.132,1.829),(-.026,-.19,1.757),(.026,-.19,1.757),
                  (0,-.245,1.729),(0,-.203,1.692),(0,-.127,1.735)],[(0,1,3,2),(2,3,4),(4,3,5),(2,4,5),(0,2,5,6),(1,6,5,3),(0,6,1)],"bone","head",False)
    else:
        plate("mask_nasal",[(-.02,1.842),(.02,1.842),(.031,1.746),(0,1.722),(-.031,1.746)],-.142,.028,"bone","head",.017)
        plate("mask_chin",[(-.045,1.727),(.045,1.727),(.029,1.672),(0,1.657),(-.029,1.672)],-.091,.03,"bone","head",.019)


def chains():
    for side in (-1,1):
        for i in range(10):
            t=i/9;x=side*(.19-.145*t);z=1.46-.24*t-.032*math.sin(math.pi*t)
            points=[]
            for j in range(13):
                a=TAU*j/12
                points.append((x+.018*math.cos(a),-.191+.011*math.sin(a)*(i%2),z+.024*math.sin(a)))
            tube("penitent_chain_"+str(side)+"_"+str(i),points,.0045,"silver","chest",5)


def costume(kind):
    heavy=kind=="iron_penitent"
    if heavy:
        cape(kind)
        for side in (-1,1):
            shoulder("layered_pauldron_"+str(side),side,"steel",True)
            skirt_panel("split_tabard_"+str(side),side,.65,"cloak",.115)
        plate("cuirass",[(-.208,1.50),(0,1.548),(.208,1.50),(.203,1.354),(.133,1.17),(0,1.128),(-.133,1.17),(-.203,1.354)],-.166,.044,"steel","chest",.057)
        plate("breastbone_ridge",[(-.028,1.48),(0,1.53),(.028,1.48),(.02,1.21),(0,1.17),(-.02,1.21)],-.229,.012,"silver","chest",.014)
        for i in range(3):
            z=1.08+i*.054
            plate("fauld_lame_"+str(i),[(-.185,z+.04),(.185,z+.04),(.173,z-.022),(-.173,z-.022)],-.168,.03,"steel","hips",.018)
        # Bascinet shell and a pale long visor mark the heavy character from above.
        loft("bascinet",[(1.66,.119,.111,.013,0),(1.78,.139,.123,.014,0),(1.9,.123,.122,.017,0),
             (2.0,.046,.067,.041,0),(2.025,.004,.005,.045,0)],"steel","head",32)
        plate("visor_upper",[(-.111,1.867),(0,1.932),(.111,1.867),(.098,1.825),(-.098,1.825)],-.124,.038,"silver","head",.034)
        plate("visor_lower",[(-.098,1.807),(.098,1.807),(.089,1.717),(0,1.664),(-.089,1.717)],-.126,.04,"steel","head",.043)
        plate("visor_ridge",[(-.014,1.858),(.014,1.858),(.018,1.70),(0,1.672),(-.018,1.70)],-.17,.02,"bone","head",.01)
        for side in (-1,1):
            for z in (1.754,1.777):
                tube("visor_vent",[(side*.037,-.157,z),(side*.076,-.144,z+.01)],.007,"inner","head",6)
        chains()
    elif kind=="ash_reaver":
        cape(kind);hood(kind);mask(kind)
        shoulder("single_pauldron",1,"steel",False)
        skirt_panel("short_hip_drape",-1,.36,"cloak",.135)
        plate("leather_bodice",[(-.183,1.49),(.184,1.45),(.14,1.14),(-.138,1.14)],-.162,.033,"leather","chest",.021)
        # Broad diagonal harness with three separate buckles.
        for i in range(3):
            t=i/2;x=-.132+.238*t;z=1.40-.186*t
            plate("harness_buckle_"+str(i),[(x-.032,z+.023),(x+.03,z+.015),(x+.03,z-.023),(x-.032,z-.015)],-.21,.016,"silver","chest",.002)
        tube("diagonal_harness",[(-.197,-.136,1.51),(-.126,-.197,1.421),(.06,-.199,1.27),(.167,-.145,1.15)],.028,"leather","chest",8)
        for side in (-1,1):
            for i in range(3):
                x=side*(.492+.008*i);z=1.139-.04*i
                loft("arm_wrap_"+str(side)+str(i),[(z-.012,.058,.06,-.071,x),(z+.012,.058,.06,-.071,x)],"wraps","forearm.L" if side>0 else "forearm.R",16)
    else:
        cape(kind);hood(kind);mask(kind)
        for side in (-1,1):
            skirt_panel("long_stole_"+str(side),side,.89,"wraps",.105)
            shoulder("ritual_mantle_"+str(side),side,"cloak",False)
            # Pale segmented collar instead of an enormous glowing magic halo.
            for i in range(4):
                x=side*(.065+i*.04);z=1.548-i*.021
                plate("bone_gorget_"+str(side)+str(i),[(x-.029,z+.057),(x+.029,z+.044),(x+.023,z-.025),(x-.02,z-.034)],-.141,.025,"bone","chest",.017)
        plate("reliquary_chest",[(-.055,1.42),(0,1.475),(.055,1.42),(.047,1.305),(0,1.277),(-.047,1.305)],-.191,.046,"bronze","chest",.017)
        plate("reliquary_inset",[(-.027,1.404),(0,1.439),(.027,1.404),(.024,1.32),(-.024,1.32)],-.216,.012,"bone","chest",.005)
    loft("waist_belt",[(1.055,.206,.149,0,0),(1.117,.204,.147,0,0)],"leather","hips",32)
    plate("belt_buckle",[(-.047,1.126),(.047,1.126),(.047,1.05),(-.047,1.05)],-.156,.018,"bronze","hips",.008)
    plate("buckle_inlay",[(-.022,1.112),(.022,1.112),(.022,1.064),(-.022,1.064)],-.173,.006,"inner","hips",.002)
    # Two small carried items reflect the shared two-slot kit without fixing item rules.
    for side in (-1,1):
        x=side*.207
        loft("belt_pouch_"+str(side),[(.912,.065,.057,.015,x),(.935,.071,.068,.014,x),(1.031,.063,.065,.014,x),(1.057,.052,.052,.014,x)],"leather","hips",16)
        plate("pouch_flap_"+str(side),[(x-.052,1.044),(x+.052,1.044),(x+.047,.997),(x,.974),(x-.047,.997)],-.06,.015,"leather","hips",.003)
        ellipsoid("pouch_clasp_"+str(side),(x,-.081,1.004),(.012,.01,.013),"bronze","hips",8,4)


def materials():
    textures=BASE.parent/"textures"
    sources={"steel":("actors_projectiles/master/materials","player_steel"),
             "blade":("actors_projectiles/master/materials","player_blade"),
             "silver":("actors_projectiles/master/materials","player_silver_trim"),
             "leather":("actors_projectiles/master/materials","player_leather"),
             "wraps":("actors_projectiles/master/materials","player_wraps"),
             "inner":("actors_projectiles/master/materials","player_inner_cloth"),
             "cloak":("generated","cloak_fabric"),"bone":("generated","bone_mask"),
             "bronze":("generated","bronze"),"wood":("generated","staff_wood")}
    records=[]
    for key,(folder,mid) in sources.items():
        root=textures/folder/mid
        params=json.loads((root/(mid+".json")).read_text())
        mat=bpy.data.materials.new(mid);mat.use_nodes=True
        mat["tile_m"]=params["tile_size_m"][0]
        nodes,links=mat.node_tree.nodes,mat.node_tree.links
        bsdf=nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value=(1,1,1,1)
        bsdf.inputs["Roughness"].default_value=1
        bsdf.inputs["Metallic"].default_value=1
        image_nodes={}
        for role in ("basecolor","normal","orm"):
            path=root/(mid+"_"+role+".png")
            if not path.is_file():raise FileNotFoundError("Build the texture masters before the models: "+mid)
            img=bpy.data.images.load(str(path),check_existing=True)
            img.colorspace_settings.name='sRGB' if role=='basecolor' else 'Non-Color'
            img.pack();img.filepath="//"+path.name
            tex=nodes.new("ShaderNodeTexImage");tex.image=img;tex.extension='REPEAT'
            image_nodes[role]=tex
            records.append({"material":mid,"role":role,"texture_source":path.relative_to(BASE.parent).as_posix(),
                            "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"license":"project_license","external_sources":[]})
        if key=='steel':
            # Explicit model-specific iron tint. glTF exports this multiply as
            # baseColorFactor; original texture sources remain untouched.
            tint=nodes.new('ShaderNodeMixRGB');tint.blend_type='MULTIPLY'
            tint.inputs[0].default_value=1;tint.inputs[2].default_value=(.28,.30,.32,1)
            links.new(image_nodes['basecolor'].outputs['Color'],tint.inputs[1])
            links.new(tint.outputs[0],bsdf.inputs['Base Color'])
        else:
            links.new(image_nodes['basecolor'].outputs['Color'],bsdf.inputs['Base Color'])
        normal=nodes.new("ShaderNodeNormalMap");normal.inputs['Strength'].default_value=1
        links.new(image_nodes['normal'].outputs['Color'],normal.inputs['Color'])
        links.new(normal.outputs['Normal'],bsdf.inputs['Normal'])
        sep=nodes.new("ShaderNodeSeparateColor");sep.mode='RGB'
        links.new(image_nodes['orm'].outputs['Color'],sep.inputs['Color'])
        links.new(sep.outputs['Green'],bsdf.inputs['Roughness']);links.new(sep.outputs['Blue'],bsdf.inputs['Metallic'])
        group=bpy.data.node_groups.get('glTF Material Output')
        if group is None:
            group=bpy.data.node_groups.new('glTF Material Output','ShaderNodeTree')
            group.interface.new_socket(name='Occlusion',in_out='INPUT',socket_type='NodeSocketFloat')
        ao=nodes.new('ShaderNodeGroup');ao.node_tree=group
        links.new(sep.outputs['Red'],ao.inputs['Occlusion'])
        MATERIALS[key]=mat
    return records


def rig():
    data=bpy.data.armatures.new("common_humanoid")
    arm=bpy.data.objects.new("Armature",data);bpy.context.collection.objects.link(arm)
    select_only([arm]);bpy.ops.object.mode_set(mode='EDIT')
    specs=[("root",(0,0,0),(0,0,.15),None),("hips",(0,0,1.0),(0,0,1.13),"root"),
           ("spine",(0,0,1.13),(0,0,1.34),"hips"),("chest",(0,0,1.34),(0,0,1.56),"spine"),
           ("neck",(0,0,1.56),(0,0,1.70),"chest"),("head",(0,0,1.70),(0,0,1.95),"neck"),
           ("cape.01",(0,.20,1.52),(0,.28,1.02),"chest"),("cape.02",(0,.28,1.02),(0,.35,.43),"cape.01")]
    for side,sign in (("L",1),("R",-1)):
        specs += [("clavicle."+side,(0,0,1.53),(sign*.266,0,1.52),"chest"),
                  ("upper_arm."+side,(sign*.266,0,1.52),(sign*.456,-.013,1.245),"clavicle."+side),
                  ("forearm."+side,(sign*.456,-.013,1.245),(sign*.526,-.083,.994),"upper_arm."+side),
                  ("hand."+side,(sign*.526,-.083,.994),(sign*.526,-.106,.89),"forearm."+side),
                  ("thigh."+side,(sign*.115,0,1.0),(sign*.14,-.03,.58),"hips"),
                  ("shin."+side,(sign*.14,-.03,.58),(sign*.14,0,.16),"thigh."+side),
                  ("foot."+side,(sign*.14,0,.16),(sign*.14,-.20,.07),"shin."+side)]
    specs += [("weapon.R",(-.526,-.116,.93),(-.526,-.116,1.13),"hand.R")]
    for name,head,tail,parent in specs:
        bone=data.edit_bones.new(name);bone.head=scaled(head);bone.tail=scaled(tail)
        if parent:bone.parent=data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    arm.show_in_front=True
    return arm


def attach_weapon(kind):
    parts=build_weapon(kind,MATERIALS)
    # Character's right hand holds the grip; the blade leans away from the body.
    angle=math.radians(-9 if kind!='veil_warden' else -4)
    for obj in parts:
        select_only([obj])
        bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
        for vert in obj.data.vertices:
            x,y,z=vert.co
            p=(x*math.cos(angle)+z*math.sin(angle)-.526,y-.116,-x*math.sin(angle)+z*math.cos(angle)+.93)
            vert.co=scaled(p)
        obj.vertex_groups.clear()
        obj.vertex_groups.new(name="weapon.R").add(list(range(len(obj.data.vertices))),1,'REPLACE')
        PARTS.append(obj)


def finish_mesh(arm,kind):
    for obj in PARTS:
        select_only([obj])
        for modifier in list(obj.modifiers):
            bpy.ops.object.modifier_apply(modifier=modifier.name)
    select_only(PARTS);bpy.ops.object.join()
    body=bpy.context.object;body.name=kind+"_mesh"
    # Recalculate normals consistently after procedural profile assembly.
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False);bpy.ops.object.mode_set(mode='OBJECT')
    body.parent=arm
    deform=body.modifiers.new("humanoid_skin",'ARMATURE');deform.object=arm
    body.data.calc_loop_triangles()
    return body


def animations(arm):
    clips={"idle":(48,lambda t:math.sin(TAU*t)),"walk":(24,lambda t:math.sin(TAU*t)),
           "melee":(18,lambda t:math.sin(math.pi*t)),"dash":(12,lambda t:math.sin(math.pi*t))}
    for name,(end,wave) in clips.items():
        action=bpy.data.actions.new(name)
        arm.animation_data_create();arm.animation_data.action=action
        for frame in sorted(set([0,end]+list(range(0,end+1,3)))):
            t=frame/end;s=wave(t)
            for bone in arm.pose.bones:
                bone.rotation_mode='XYZ';bone.rotation_euler=(0,0,0);bone.location=(0,0,0);bone.scale=(1,1,1)
            if name=='idle':
                arm.pose.bones['chest'].rotation_euler.x=.015*s
                arm.pose.bones['head'].rotation_euler.z=.018*s
                arm.pose.bones['cape.02'].rotation_euler.x=.025*s
            elif name=='walk':
                for side,sign in (('L',1),('R',-1)):
                    arm.pose.bones['thigh.'+side].rotation_euler.x=.43*s*sign
                    arm.pose.bones['shin.'+side].rotation_euler.x=max(0,-s*sign)*.55
                    arm.pose.bones['foot.'+side].rotation_euler.x=-.15*s*sign
                    arm.pose.bones['upper_arm.'+side].rotation_euler.x=-.24*s*sign
                arm.pose.bones['chest'].rotation_euler.z=.055*s
                arm.pose.bones['cape.01'].rotation_euler.x=.06*s
            elif name=='melee':
                arm.pose.bones['chest'].rotation_euler.z=-.5*s
                arm.pose.bones['upper_arm.R'].rotation_euler=(.62*s,-.42*s,-.80*s)
                arm.pose.bones['forearm.R'].rotation_euler.x=-.72*s
                arm.pose.bones['upper_arm.L'].rotation_euler.x=.2*s
                arm.pose.bones['cape.01'].rotation_euler.z=.1*s
            else:
                arm.pose.bones['hips'].rotation_euler.x=.25*s
                arm.pose.bones['chest'].rotation_euler.x=.15*s
                arm.pose.bones['thigh.L'].rotation_euler.x=.45*s
                arm.pose.bones['thigh.R'].rotation_euler.x=-.45*s
                arm.pose.bones['shin.R'].rotation_euler.x=.7*s
                arm.pose.bones['cape.01'].rotation_euler.x=-.3*s
            for bone in arm.pose.bones:
                bone.keyframe_insert(data_path='rotation_euler',frame=frame,group=bone.name)
        action.use_fake_user=True
    arm.animation_data.action=bpy.data.actions['idle']
    bpy.context.scene.frame_start=0
    bpy.context.scene.frame_set(0)


def socket(arm,name,bone_name,position,angle=0):
    obj=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(obj)
    obj.parent=arm;obj.parent_type='BONE';obj.parent_bone=bone_name
    bpy.context.view_layer.update()
    obj.matrix_world=Matrix.Translation(scaled(position)) @ Matrix.Rotation(angle,4,'Y')
    obj["semantic"]=name
    return obj


def neutral_material(name,color,roughness,metallic=0):
    mat=bpy.data.materials.new(name);mat.use_nodes=True
    bsdf=mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value=(*color,1)
    bsdf.inputs['Roughness'].default_value=roughness;bsdf.inputs['Metallic'].default_value=metallic
    return mat


def render_setup():
    scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE'
    scene.eevee.taa_render_samples=48;scene.eevee.use_shadows=True
    scene.eevee.use_raytracing=False;scene.eevee.use_fast_gi=False
    scene.render.resolution_x=640;scene.render.resolution_y=800;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
    scene.render.image_settings.color_depth='8';scene.render.film_transparent=False
    scene.render.use_compositing=False;scene.render.use_motion_blur=False
    scene.render.dither_intensity=0;scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
    world=bpy.data.worlds.new('studio_world');world.use_nodes=True
    world.node_tree.nodes.get('Background').inputs[0].default_value=(.08,.105,.14,1)
    world.node_tree.nodes.get('Background').inputs[1].default_value=.45;scene.world=world
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.035))
    bpy.context.object.name='preview_ground';bpy.context.object.data.materials.append(neutral_material('preview_floor',(.018,.024,.032),.86))
    for name,pos,power,size,color in [('key',(-3,-4,5),850,4,(1,.88,.74)),('fill',(3,-1,3),650,3,(.70,.83,1)),('back',(1,3,4),1000,3,(.8,.86,1))]:
        light=bpy.data.lights.new(name,'AREA');light.energy=power;light.shape='DISK';light.size=size;light.color=color
        obj=bpy.data.objects.new(name,light);bpy.context.collection.objects.link(obj);obj.location=pos
        obj.rotation_euler=(Vector((0,0,1.0))-obj.location).to_track_quat('-Z','Y').to_euler()
    camera=bpy.data.cameras.new('preview_camera');obj=bpy.data.objects.new('preview_camera',camera)
    bpy.context.collection.objects.link(obj);scene.camera=obj;camera.type='ORTHO';camera.ortho_scale=2.68
    return scene,obj


def render_views(root):
    scene,camera=render_setup()
    for name,pos in [('front',(3,-7,3.05)),('back',(-3,7,3.05)),('topdown',(0,-3.5*math.cos(math.radians(65)),1+3.5*math.sin(math.radians(65))))]:
        camera.location=pos
        camera.rotation_euler=(Vector((-.09,0,1.09))-camera.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(root/(name+'.png'))
        bpy.ops.render.render(write_still=True)
    camera.location=(3,-7,3.05)
    camera.rotation_euler=(Vector((-.09,0,1.09))-camera.location).to_track_quat('-Z','Y').to_euler()


def build_character(spec,output,render):
    global SCALE,PARTS,MATERIALS
    bpy.ops.wm.read_factory_settings(use_empty=True)
    PARTS=[];MATERIALS={}
    SCALE=Vector((spec['width_scale'],1,spec['height_m']/2.025))
    kind=spec['id'];folder=output/kind;folder.mkdir(parents=True,exist_ok=True)
    texture_records=materials()
    build_base(kind);costume(kind);attach_weapon(kind)
    arm=rig();body=finish_mesh(arm,kind);animations(arm)
    weapon_angle=math.radians(-4 if kind=='veil_warden' else -9)
    sockets=[socket(arm,'socket_weapon_r','weapon.R',(-.526,-.116,.93),weapon_angle),
             socket(arm,'socket_skillshot_l','hand.L',(.526,-.145,.94))]
    bpy.context.scene.render.fps=24
    for action in bpy.data.actions:
        # All four generated actions are compatible with this one armature.
        action.use_fake_user=True
    arm['asset_id']=kind;arm['design_status']='visual_prototype';arm['source_license']='project_license'
    select_only([arm,body]+sockets)
    bpy.ops.export_scene.gltf(filepath=str(folder/(kind+'.glb')),export_format='GLB',use_selection=True,
        export_yup=True,export_apply=False,export_animations=True,export_animation_mode='ACTIONS',
        export_force_sampling=True,export_frame_range=False,export_anim_single_armature=True,
        export_skins=True,export_all_influences=False,export_extras=True,export_cameras=False,export_lights=False)
    metadata={**spec,'schema_version':1,'license':'project_license','external_sources':[],
              'generator':'build.py','blender_version':bpy.app.version_string,
              'units':'meters','blender_axes':{'up':'+Z','forward':'-Y'},'gltf_axes':{'up':'+Y','forward':'+Z'},
              'triangles_before_export':len(body.data.loop_triangles),'mesh_vertices_before_export':len(body.data.vertices),
              'joints':[b.name for b in arm.data.bones],'animations':['idle','walk','melee','dash'],
              'animation_status':'procedural_in_place_blocking; no final combat timing or root motion',
              'material_overrides':{'player_steel':{'baseColorFactor':[.28,.30,.32,1],
                'reason':'Explicit cool dark iron tint of the shared steel texture for character armour.'}},
              'textures':texture_records,'sockets':[s.name for s in sockets],
              'socket_contract':{'socket_skillshot_l':'glTF local +Z points forward at rest',
                  'socket_weapon_r':'glTF local +Y is the weapon length axis; meter scale; designed outward tilt'},
              'limits':['No Grimoire import or game-camera contrast acceptance has been performed.',
                        'Cloth uses skin weights; there is no cloth simulation or final animation polish.',
                        'Collision capsule and combat timing must be configured from gameplay data.']}
    write_json(folder/(kind+'.json'),metadata)
    if render:render_views(folder)
    # Local editing convenience only: the .blend is always ignored by Git.
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/(kind+'.blend')),compress=True)
    print('BUILT',kind,'triangles',metadata['triangles_before_export'],flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render',action='store_true',help='Render front, back and 65-degree views with Eevee')
    parser.add_argument('--character',choices=['iron_penitent','ash_reaver','veil_warden'])
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    output=BASE/'generated';output.mkdir(exist_ok=True)
    catalog=json.loads((BASE/'catalog.json').read_text())
    for spec in catalog['characters']:
        if args.character is None or args.character==spec['id']:
            build_character(spec,output,args.render)
    write_json(output/'build_sources.json',{'schema_version':1,'sources':{
        name:hashlib.sha256((BASE/name).read_bytes()).hexdigest() for name in ('build.py','weapons.py','catalog.json')},
        'license':'project_license','external_sources':[]})


if __name__=='__main__':
    main()
