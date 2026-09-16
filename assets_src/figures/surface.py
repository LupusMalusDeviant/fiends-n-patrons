"""Box-modelled character surfaces in bmesh.

The whole body is ONE continuous quad surface. It starts as a lofted torso tube
(crotch to crown) and every other part -- arms, legs, head horns, tail, claws --
is grown by extruding a rectangular patch of faces out of that surface and
placing each extruded ring on a cross-section profile along a skeleton curve.
Nothing is ever a separate primitive dropped next to the body, so there are no
interpenetrating spheres at the joints and the edge loops run continuously from
the fingers through the shoulder into the spine.

Mechanics worth knowing:

* `bmesh.ops.extrude_face_region` on a closed patch duplicates the whole patch
  (boundary ring + interior verts) and walls it in with new side quads. The tip
  therefore never has an open boundary; the ring is found as the edges with
  exactly one link face *inside* the patch.
* A 2x2 seed patch gives an 8-vertex ring plus one centre vertex, so a limb is
  an 8-sided tube closed by a 4-quad cap -- quads everywhere, no n-gon tip.
* Each extruded vertex inherits its ring angle from the vertex it was extruded
  from, which is what keeps the edge loops from spiralling around a limb.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

import lofting as L


class Surface:
    """One continuous quad body surface under construction."""

    def __init__(self, nseg=12):
        self.bm = bmesh.new()
        self.nseg = int(nseg)
        self.region_layer = self.bm.faces.layers.int.new("region")
        self.crease_layer = self.bm.edges.layers.float.new("crease_edge")
        self.regions = {}          # region name -> region id
        self.grid = {}             # (station, segment) -> face, for the torso tube
        self.rings = []            # torso rings, list of lists of BMVert
        self.ring_angle = {}       # BMVert -> parametric angle index on its limb ring
        self.log = []

    # ------------------------------------------------------------ regions ---
    def region_id(self, name):
        if name not in self.regions:
            self.regions[name] = len(self.regions)
        return self.regions[name]

    def tag(self, faces, region):
        rid = self.region_id(region)
        for f in faces:
            f[self.region_layer] = rid

    # -------------------------------------------------------------- torso ---
    def build_torso(self, ctrl, stations, keys, region, u_hint=(1.0, 0.0, 0.0)):
        """Loft the trunk: one tube from the crotch to the crown of the head.

        The frames are world-aligned (not parallel transported) so the local u
        axis keeps pointing at the character's right all the way up; that makes
        segment indices mean the same thing at the hips and at the skull, which
        is what lets limb patches be addressed by (station, segment).
        """
        pts, tg, u, v = L.chain_stations(ctrl, stations, u_hint=u_hint)
        prof = L.interp_profiles(keys, stations)
        ang = L.ring_angles(self.nseg)
        bm = self.bm
        self.rings = []
        for i in range(stations):
            ring = L.ring_points(pts[i], u[i], v[i], ang, prof["rx"][i], prof["ry"][i],
                                 prof["power"][i], prof["rot"][i], prof["du"][i],
                                 prof["dv"][i], prof["shear"][i])
            self.rings.append([bm.verts.new(tuple(p)) for p in ring])
        bm.verts.ensure_lookup_table()
        for i in range(stations - 1):
            for k in range(self.nseg):
                k2 = (k + 1) % self.nseg
                f = bm.faces.new((self.rings[i][k], self.rings[i][k2],
                                  self.rings[i + 1][k2], self.rings[i + 1][k]))
                self.grid[(i, k)] = f
        # Caps. Hidden inside the legs (crotch) and under the crown; an n-gon
        # here is invisible after subdivision and keeps the rest pure quads.
        cap_a = bm.faces.new(tuple(reversed(self.rings[0])))
        cap_b = bm.faces.new(tuple(self.rings[-1]))
        bm.faces.ensure_lookup_table()
        bm.normal_update()
        self.tag(list(self.grid.values()) + [cap_a, cap_b], region)
        self.torso_pts, self.torso_frames = pts, (tg, u, v)
        self.log.append("torso: %d stations x %d segments" % (stations, self.nseg))
        return pts, (tg, u, v)

    def patch(self, stations, segments):
        """Faces of the torso grid in a rectangular (station, segment) window.
        Segment indices wrap, so (11, 1) is the two faces straddling world +X."""
        i0, i1 = stations
        k0, k1 = segments
        n = self.nseg
        ks = [(k0 + d) % n for d in range((k1 - k0) % n + 1)]
        return [self.grid[(i, k)] for i in range(i0, i1) for k in ks if (i, k) in self.grid]

    # --------------------------------------------------------------- rings ---
    def _patch_ring(self, faces):
        """Cyclically ordered boundary vertices of a face patch."""
        fset = set(faces)
        edges = [e for f in faces for e in f.edges
                 if sum(1 for lf in e.link_faces if lf in fset) == 1]
        edges = list(dict.fromkeys(edges))
        if not edges:
            raise ValueError("face patch has no boundary ring")
        adj = {}
        for e in edges:
            for a, b in ((e.verts[0], e.verts[1]), (e.verts[1], e.verts[0])):
                adj.setdefault(a, []).append(b)
        start = edges[0].verts[0]
        order, prev, cur = [start], None, start
        while True:
            nxt = [w for w in adj[cur] if w is not prev]
            if not nxt:
                break
            nxt = nxt[0]
            if nxt is start:
                break
            order.append(nxt)
            prev, cur = cur, nxt
        if len(order) != len(edges):
            raise ValueError("boundary ring is not a single cycle (%d of %d)" % (len(order), len(edges)))
        return order

    def _seed_angles(self, ring, center, u_axis, v_axis):
        """Assign each seed vertex an evenly spaced ring index.

        The measured angles of a patch boundary are not evenly spaced, so the
        vertices are sorted by measured angle and then matched to the evenly
        spaced slots with the rotational offset that moves them least. Every
        later ring inherits these indices, which keeps the loops straight.
        """
        n = len(ring)
        c = np.asarray(center, dtype=np.float64)
        meas = []
        for vtx in ring:
            d = np.asarray(vtx.co, dtype=np.float64) - c
            meas.append(math.atan2(float(d @ v_axis), float(d @ u_axis)) % (2 * math.pi))
        order = sorted(range(n), key=lambda i: meas[i])
        slot = 2 * math.pi / n
        best, best_cost = 0, None
        for off in range(n):
            cost = 0.0
            for j, i in enumerate(order):
                want = ((j + off) % n) * slot
                diff = abs((meas[i] - want + math.pi) % (2 * math.pi) - math.pi)
                cost += diff
            if best_cost is None or cost < best_cost:
                best, best_cost = off, cost
        for j, i in enumerate(order):
            self.ring_angle[ring[i]] = (j + best) % n

    def _place_ring(self, verts, center, u_axis, v_axis, n, rx, ry, power, rot, du, dv, blend=1.0):
        """Put an extruded ring on its cross-section, each vertex at its own
        inherited angle index. `blend` < 1 eases the first ring off the torso so
        the attachment is not a hard step."""
        slot = 2 * math.pi / n
        c = np.asarray(center, dtype=np.float64)
        for vtx in verts:
            idx = self.ring_angle.get(vtx)
            if idx is None:
                continue
            a = idx * slot + rot
            x = rx * math.copysign(abs(math.cos(a)) ** (2.0 / max(power, 0.2)), math.cos(a)) + du
            y = ry * math.copysign(abs(math.sin(a)) ** (2.0 / max(power, 0.2)), math.sin(a)) + dv
            target = c + x * u_axis + y * v_axis
            old = np.asarray(vtx.co, dtype=np.float64)
            vtx.co = Vector(tuple(old + blend * (target - old)))

    # --------------------------------------------------------------- limbs ---
    def _patch_boundary_edges(self, faces):
        fset = set(faces)
        return list(dict.fromkeys(
            e for f in faces for e in f.edges
            if sum(1 for lf in e.link_faces if lf in fset) == 1))

    def grow(self, seed_faces, ctrl, keys, steps, region, u_hint=None, ease=2,
             cap_region=None, seam_index=0, base_seam=True):
        """Grow a limb out of a face patch by repeated extrusion.

        seed_faces: the patch on the existing surface the limb comes out of
        ctrl:       control points of the limb's skeleton curve
        keys:       keyed cross-section profiles along it (t = 0 at the seed)
        steps:      number of extrusions == number of new rings
        ease:       how many of the first rings are blended in, so the limb
                    leaves the body smoothly instead of with a collar
        """
        bm = self.bm
        seed_ring = self._patch_ring(seed_faces)
        n = len(seed_ring)
        # A limb is a closed tube. Without a ring seam where it leaves the body
        # and one seam running along its length, the unwrap has to flatten a
        # cylinder with no cut and squashes it to nearly zero UV area -- which is
        # exactly why the texture was invisible on the first pass.
        if base_seam:
            for e in self._patch_boundary_edges(seed_faces):
                e.seam = True
        pts, tg, u, v = L.chain_stations(ctrl, steps + 1, u_hint=u_hint)
        prof = L.interp_profiles(keys, steps + 1)
        self._seed_angles(seed_ring, pts[0], u[0], v[0])
        cur = list(seed_faces)
        rid = self.region_id(region)
        tip = None
        for s in range(1, steps + 1):
            before = set(bm.faces)
            res = bmesh.ops.extrude_face_region(bm, geom=cur)
            # The op returns ONLY the duplicated cap (faces + its vertices); the
            # side walls it builds are not in the result, so they are picked up
            # by diffing the face set -- otherwise they keep the default region
            # id and a horn would be tagged as skin.
            cap_faces = [g for g in res["geom"] if isinstance(g, bmesh.types.BMFace)]
            new_verts = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
            if not cap_faces:
                raise ValueError("extrusion produced no cap face for %s" % region)
            newset = set(new_verts)
            walls = [f for f in bm.faces if f not in before and f not in set(cap_faces)]
            # Inherit the ring index across the side edge that joins old to new.
            partner_edge = {}
            for vtx in new_verts:
                for e in vtx.link_edges:
                    other = e.other_vert(vtx)
                    if other not in newset and other in self.ring_angle:
                        self.ring_angle[vtx] = self.ring_angle[other]
                        partner_edge[vtx] = e
                        break
            new_ring = self._patch_ring(cap_faces)
            # One lengthwise seam column, the same ring index at every step, so
            # the limb unwraps as a flat strip instead of a collapsed cylinder.
            for vtx in new_ring:
                if self.ring_angle.get(vtx) == seam_index % n and vtx in partner_edge:
                    partner_edge[vtx].seam = True
            centre_verts = [vtx for vtx in newset if vtx not in set(new_ring)]
            blend = 1.0 if s > ease else (0.45 + 0.55 * (s / max(ease, 1)))
            self._place_ring(new_ring, pts[s], u[s], v[s], n, prof["rx"][s], prof["ry"][s],
                             prof["power"][s], prof["rot"][s], prof["du"][s], prof["dv"][s],
                             blend=blend)
            # The centre vertices of the cap ride along the axis.
            for vtx in centre_verts:
                vtx.co = Vector(tuple(pts[s] + prof["du"][s] * u[s] + prof["dv"][s] * v[s]))
            for f in cap_faces + walls:
                f[self.region_layer] = rid
            # extrude_face_region does NOT remove the faces it grew from when the
            # region is part of a larger surface: they survive as a diaphragm
            # inside the limb and give every seed edge a third face. Deleting
            # them is what keeps the body a closed manifold -- and bone-heat
            # weighting simply refuses to solve on a non-manifold mesh.
            bmesh.ops.delete(bm, geom=cur, context='FACES')
            self.ring_angle = {v: a for v, a in self.ring_angle.items() if v.is_valid}
            cur, tip = cap_faces, cap_faces
        if cap_region:
            self.tag(tip, cap_region)
        bm.normal_update()
        self.log.append("limb %s: %d rings of %d verts, length %.3f m"
                        % (region, steps, n, L.arc_length(pts)))
        return tip

    def grow_digit(self, face, ctrl, radii, steps, region, taper_power=2.0):
        """A claw, toe or finger: grown out of a single face of a hand/foot cap,
        so it is part of the same surface rather than a cone stuck on."""
        keys = [L.profile_key(t, rx=r, ry=r, power=taper_power)
                for t, r in zip(np.linspace(0.0, 1.0, len(radii)), radii)]
        return self.grow([face], ctrl, keys, steps, region, ease=1)

    def tip_faces_sorted(self, faces, axis):
        """Cap faces ordered along a world axis, so digits can be placed on them."""
        a = np.asarray(axis, dtype=np.float64)
        return sorted(faces, key=lambda f: float(np.asarray(f.calc_center_median()) @ a))

    # ----------------------------------------------------------- deformers ---
    def bump(self, center, radius, offset, only_region=None):
        """Push existing geometry out (chest plate, deltoid, brow, muzzle).

        Detail is added by moving loops that are already there -- the whole point
        of the exercise. Nothing new is attached.
        """
        c = np.asarray(center, dtype=np.float64)
        o = np.asarray(offset, dtype=np.float64)
        rid = self.regions.get(only_region) if only_region else None
        allowed = None
        if rid is not None:
            allowed = {vtx for f in self.bm.faces if f[self.region_layer] == rid for vtx in f.verts}
        moved = 0
        for vtx in self.bm.verts:
            if allowed is not None and vtx not in allowed:
                continue
            d = float(np.linalg.norm(np.asarray(vtx.co, dtype=np.float64) - c))
            if d >= radius:
                continue
            w = float(L.smooth_falloff(d, radius))
            vtx.co = Vector(tuple(np.asarray(vtx.co, dtype=np.float64) + w * o))
            moved += 1
        self.log.append("bump at %s r=%.3f moved %d verts" % (np.round(c, 3).tolist(), radius, moved))
        return moved

    def scale_region(self, region, factor, pivot):
        """Non-uniform scale of one region about a pivot (sunken head, flared plates)."""
        rid = self.regions[region]
        p = np.asarray(pivot, dtype=np.float64)
        fv = np.asarray(factor, dtype=np.float64)
        verts = {vtx for f in self.bm.faces if f[self.region_layer] == rid for vtx in f.verts}
        for vtx in verts:
            vtx.co = Vector(tuple(p + (np.asarray(vtx.co, dtype=np.float64) - p) * fv))
        return len(verts)

    def relax(self, iterations=1, only_region=None, strength=0.5):
        """Laplacian relaxation, used only to blend limb attachments. Boundary
        vertices of the selection are held so the silhouette does not shrink."""
        rid = self.regions.get(only_region) if only_region else None
        for _ in range(iterations):
            if rid is None:
                verts = list(self.bm.verts)
            else:
                verts = list({vtx for f in self.bm.faces if f[self.region_layer] == rid
                              for vtx in f.verts})
            targets = {}
            for vtx in verts:
                nb = [e.other_vert(vtx) for e in vtx.link_edges]
                if len(nb) < 3:
                    continue
                avg = np.mean([np.asarray(w.co, dtype=np.float64) for w in nb], axis=0)
                targets[vtx] = np.asarray(vtx.co, dtype=np.float64) * (1 - strength) + avg * strength
            for vtx, co in targets.items():
                vtx.co = Vector(tuple(co))

    def crease_ring(self, predicate, value):
        """Set a subdivision crease on every edge matching a predicate."""
        n = 0
        for e in self.bm.edges:
            if predicate(e):
                e[self.crease_layer] = float(value)
                n += 1
        return n

    def mark_seam(self, predicate):
        n = 0
        for e in self.bm.edges:
            if predicate(e):
                e.seam = True
                n += 1
        return n

    # ----------------------------------------------------------- finishing ---
    def stats(self):
        tris = sum(len(f.verts) - 2 for f in self.bm.faces)
        quads = sum(1 for f in self.bm.faces if len(f.verts) == 4)
        ngons = sum(1 for f in self.bm.faces if len(f.verts) > 4)
        return dict(verts=len(self.bm.verts), faces=len(self.bm.faces), tris=tris,
                    quads=quads, ngons=ngons)

    def check_manifold(self):
        """Every edge must be shared by exactly two faces and no vertex may be
        loose: the proof that the body really is one closed surface."""
        bad_edges = [e for e in self.bm.edges if len(e.link_faces) != 2]
        loose = [v for v in self.bm.verts if not v.link_faces]
        return dict(non_manifold_edges=len(bad_edges), loose_verts=len(loose))

    def to_object(self, name, material_for_region, collection=None):
        """Bake the bmesh into a real object with one material slot per region."""
        me = bpy.data.meshes.new(name)
        rid_to_name = {v: k for k, v in self.regions.items()}
        slots, slot_index = [], {}
        for rid in sorted(rid_to_name):
            mat_key = material_for_region[rid_to_name[rid]]
            if mat_key not in slot_index:
                slot_index[mat_key] = len(slots)
                slots.append(mat_key)
            # region id -> material slot
        self.bm.to_mesh(me)
        for key in slots:
            me.materials.append(bpy.data.materials[key])
        region_attr = me.attributes.get("region")
        if region_attr is not None:
            idx = [slot_index[material_for_region[rid_to_name[int(r.value)]]]
                   for r in region_attr.data]
            me.polygons.foreach_set("material_index", idx)
        me.update()
        ob = bpy.data.objects.new(name, me)
        (collection or bpy.context.collection).objects.link(ob)
        return ob

    def free(self):
        self.bm.free()


# ------------------------------------------------------------- utilities ---
def mirror_ctrl(ctrl):
    """Mirror a control chain across the YZ plane (left/right limb pairs)."""
    return [(-float(p[0]), float(p[1]), float(p[2])) for p in ctrl]


def mirror_segments(segments, nseg):
    """Segment window of the mirrored patch on a ring whose vertex 0 sits at +X.

    Mirroring x -> -x maps ring vertex k to vertex (nseg/2 - k) mod nseg, so the
    face window (k0, k1) becomes (nseg/2 - 1 - k1, nseg/2 - 1 - k0).
    """
    k0, k1 = segments
    half = nseg // 2
    return ((half - 1 - k1) % nseg, (half - 1 - k0) % nseg)


def apply_subsurf(ob, levels=2, render_levels=2):
    md = ob.modifiers.new("subsurf", 'SUBSURF')
    md.levels, md.render_levels = levels, render_levels
    md.use_creases = True
    md.use_limit_surface = True
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=md.name)
    return ob


def shade_smooth(ob):
    for p in ob.data.polygons:
        p.use_smooth = True
