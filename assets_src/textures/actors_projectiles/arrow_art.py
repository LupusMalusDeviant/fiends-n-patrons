"""Deterministic gothic projectile object sprites, facing +X.

These are unlit RGBA item sprites, not PBR base-color textures. All marks,
feather vanes and metal facets are drawn from code; there are no source assets.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw


_KINDS = {"hunter_arrow", "barbed_arrow", "crossbow_bolt", "bone_lance"}
_INK = (12, 16, 23)
_STEEL = (98, 114, 123)
_EDGE = (175, 190, 194)
_PALE = (204, 213, 211)
_BONE = (167, 160, 140)


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) != 6:
        raise ValueError("Colors must be six-digit RGB hex strings")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, amount):
    return tuple(round(x * (1.0 - amount) + y * amount) for x, y in zip(a, b))


class _Art:
    def __init__(self, resolution, signal, core):
        self.n = resolution
        self.im = Image.new("RGBA", (resolution, resolution))
        self.draw = ImageDraw.Draw(self.im)
        self.signal = signal
        self.core = core

    def xy(self, point):
        return tuple(round(v * self.n) for v in point)

    def polygon(self, points, fill, outline=None, width=0.002):
        p = [self.xy(v) for v in points]
        self.draw.polygon(p, fill=tuple(fill) + (255,))
        if outline is not None:
            self.draw.line(p + [p[0]], fill=tuple(outline) + (255,),
                           width=max(1, round(width * self.n)), joint="curve")

    def line(self, points, fill, width=0.002):
        self.draw.line([self.xy(v) for v in points], fill=tuple(fill) + (255,),
                       width=max(1, round(width * self.n)), joint="curve")

    def ellipse(self, box, fill, outline=None, width=0.002):
        self.draw.ellipse(tuple(round(v * self.n) for v in box),
                          fill=tuple(fill) + (255,),
                          outline=None if outline is None else tuple(outline) + (255,),
                          width=max(1, round(width * self.n)))

    def facet(self, points, base, shade=0.32, outline=_INK):
        """Soft vertical material variation within a hard, readable silhouette."""
        p = [self.xy(v) for v in points]
        x0 = max(0, min(v[0] for v in p) - 2)
        y0 = max(0, min(v[1] for v in p) - 2)
        x1 = min(self.n, max(v[0] for v in p) + 3)
        y1 = min(self.n, max(v[1] for v in p) + 3)
        w, h = x1 - x0, y1 - y0
        mask = Image.new("L", (w, h))
        ImageDraw.Draw(mask).polygon([(x - x0, y - y0) for x, y in p], fill=255)
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        vertical = (yy - y0) / max(1, h - 1)
        broad = np.sin(xx / self.n * 173.0 + yy / self.n * 37.0)
        broad *= np.sin(xx / self.n * 57.0 - yy / self.n * 91.0)
        gain = (1.0 + shade * (0.40 - vertical) + broad * 0.028)[..., None]
        color = np.clip(np.array(base)[None, None, :] * gain, 0, 255).astype(np.uint8)
        layer = Image.fromarray(color)
        self.im.paste(layer, (x0, y0), mask)
        if outline is not None:
            self.line(points + [points[0]], outline, 0.0022)

    def rivet(self, x, y, radius=0.0055):
        self.ellipse((x-radius, y-radius, x+radius, y+radius), (103, 116, 122), _INK)
        self.ellipse((x-radius*.45, y-radius*.52, x+radius*.22, y+radius*.05), _PALE)


def _shaft(a, start, end, half=0.023, wood=True):
    base = (78, 63, 55) if wood else (62, 73, 81)
    points = [(start, .5-half*.73), (end, .5-half), (end+.012, .5),
              (end, .5+half), (start, .5+half*.73), (start-.009, .5)]
    a.facet(points, base, .68)
    a.line([(start+.008, .5-half*.49), (end-.016, .5-half*.63)],
           (124, 111, 91) if wood else (139, 155, 161), .004)
    a.line([(start+.027, .503), (end-.025, .505)], (43, 39, 38), .002)
    if wood:
        for offset in [-.010, .009]:
            a.line([(start+.050, .5+offset), (start+.13, .5+offset*.7),
                    (end-.071, .5+offset)], (64, 50, 44), .0018)


def _binding(a, start, end, half=.03, colored=False):
    a.facet([(start, .5-half), (end, .5-half*.88), (end, .5+half*.9),
             (start, .5+half)], (54, 42, 39), .5)
    wraps = max(3, round((end-start)/.010))
    for i in range(wraps):
        x = start + (i+.3)*(end-start)/wraps
        a.line([(x, .5-half*.85), (min(end, x+.012), .5+half*.84)],
               _mix(a.signal, (67, 58, 49), .50) if colored and i % 3 == 1
               else (108, 88, 70), .004)
        a.line([(x+.004, .5-half*.78), (min(end, x+.016), .5+half*.79)],
               (30, 27, 27), .0016)


def _feather(a, left, right, direction, spread, pale=False):
    """Raven flight vane with a ragged edge and individually laid barbs."""
    center = .5
    span = right-left
    def pt(x, y):
        return (left + span*x, center + direction*y)
    outline = [pt(0,.013), pt(.09,spread*.61), pt(.20,spread*.79),
               pt(.30,spread*.75), pt(.39,spread*.92), pt(.46,spread*.84),
               pt(.57,spread), pt(.64,spread*.86), pt(.73,spread*.91),
               pt(.84,spread*.61), pt(.95,spread*.35), pt(1,.009),
               pt(.61,.017), pt(.30,.012)]
    base = (102, 114, 118) if pale else (45, 55, 64)
    a.facet(outline, base, .44)
    a.polygon([pt(.05,.014), pt(.23,spread*.54), pt(.68,spread*.62),
               pt(.95,.010)], (72, 87, 96) if pale else (35, 43, 56))
    for i in range(11):
        t = .11 + i*.066
        length = spread * (.53 + .23*math.sin(t*math.pi))
        # Barbs lean toward the tip instead of reading as a striped triangle.
        a.line([pt(t,.020), pt(min(.97,t+.18), length)],
               (122, 135, 138) if pale else (65, 76, 83), .002)
        a.line([pt(t+.024,.018), pt(min(.97,t+.20), length*.95)],
               (58, 67, 74) if pale else (25, 31, 42), .0018)
    a.line([pt(.045,.012), pt(.48,spread*.34), pt(.92,spread*.24)],
           (147, 154, 145) if pale else (104, 111, 111), .003)


def _hunter(a):
    _feather(a,.115,.345,-1,.109)
    _feather(a,.124,.347,1,.119)
    _shaft(a,.115,.728)
    a.line([(.116,.495),(.134,.491),(.139,.504),(.117,.505)], _EDGE, .004)
    _binding(a,.289,.361,.028)
    _binding(a,.594,.650,.028,True)
    # Swept leaf broadhead, not a solid triangular dart.
    outer = [(.629,.467),(.655,.444),(.671,.415),(.714,.426),(.783,.461),
             (.899,.500),(.783,.539),(.714,.574),(.671,.585),(.655,.556),
             (.629,.533),(.659,.515),(.659,.486)]
    a.facet(outer,(112,125,132),.34)
    a.polygon([(.645,.470),(.675,.436),(.713,.443),(.784,.476),(.877,.5),
               (.701,.491),(.664,.485)], (72,85,95))
    a.polygon([(.666,.520),(.681,.562),(.718,.551),(.791,.520),(.880,.5),
               (.700,.504)], (39,49,59))
    a.line([(.638,.468),(.654,.448),(.672,.419),(.715,.430),(.789,.464),
            (.893,.5)],_PALE,.005)
    a.line([(.673,.578),(.717,.567),(.788,.534),(.889,.502)],_EDGE,.0035)
    a.line([(.657,.498),(.793,.499),(.886,.500)],(170,184,188),.005)
    # Small arrow-shaped signal inlay and a visible ferrule band.
    a.polygon([(.690,.488),(.746,.491),(.783,.500),(.746,.509),(.690,.512),
               (.710,.501)],_mix(a.signal,(93,101,105),.20))
    a.line([(.724,.498),(.766,.500)],a.core,.0025)
    a.rivet(.674,.5,.006)
    a.line([(.602,.477),(.610,.521)],a.signal,.005)


def _barbed(a):
    _feather(a,.105,.340,-1,.129)
    _feather(a,.112,.346,1,.139)
    _shaft(a,.121,.711,.025)
    _binding(a,.283,.372,.033,True)
    _binding(a,.541,.606,.032)
    # Two backward-facing hooks have open notches, producing a hooked silhouette.
    blade = [(.594,.473),(.650,.442),(.617,.390),(.695,.412),(.754,.456),
             (.898,.5),(.754,.544),(.695,.588),(.617,.610),(.650,.558),
             (.594,.527),(.656,.506),(.656,.494)]
    a.facet(blade,(81,92,105),.43)
    a.polygon([(.624,.405),(.666,.454),(.608,.478),(.731,.494),(.882,.5),
               (.750,.466),(.690,.424)],(47,57,70))
    a.polygon([(.620,.595),(.667,.547),(.616,.520),(.734,.506),(.882,.5),
               (.750,.534),(.690,.575)],(29,37,48))
    a.line([(.622,.395),(.694,.417),(.752,.461),(.891,.499)],_PALE,.006)
    a.line([(.621,.605),(.695,.583),(.752,.539),(.891,.501)],_EDGE,.004)
    a.line([(.607,.476),(.656,.446),(.627,.409)],(134,145,152),.004)
    a.line([(.607,.524),(.656,.554),(.627,.591)],(109,121,131),.003)
    a.polygon([(.672,.483),(.752,.492),(.838,.500),(.751,.508),(.672,.517),
               (.703,.501)],_mix(a.signal,(65,75,82),.19))
    a.line([(.710,.499),(.805,.500)],a.core,.003)
    a.line([(.677,.454),(.697,.462),(.691,.477)],a.signal,.004)
    a.line([(.677,.546),(.697,.538),(.691,.523)],a.signal,.004)
    a.rivet(.651,.5,.007)
    # Darkened tang with a single readable bright band.
    a.line([(.555,.473),(.563,.525)],a.signal,.007)


def _bolt(a):
    _feather(a,.137,.399,-1,.100,True)
    _feather(a,.137,.399,1,.100)
    _shaft(a,.125,.716,.033,False)
    # Hexagonal nock and long steel-reinforced shaft read heavier than an arrow.
    a.facet([(.11,.475),(.133,.462),(.159,.475),(.159,.525),(.133,.538),
             (.11,.525)],(105,115,115),.35)
    a.line([(.119,.486),(.147,.486),(.147,.514),(.119,.514)],(25,34,42),.005)
    _binding(a,.332,.396,.036)
    a.facet([(.420,.466),(.580,.466),(.602,.479),(.602,.521),(.580,.534),
             (.420,.534)],(46,58,68),.6)
    a.line([(.43,.474),(.577,.474)],_EDGE,.004)
    a.line([(.433,.5),(.574,.5)],a.signal,.009)
    for x in [.426,.587]:
        a.line([(x,.47),(x,.53)],(134,145,148),.007)
    # Short four-facet armor-piercing bodkin with unmistakable taper.
    blade=[(.629,.449),(.683,.427),(.899,.5),(.683,.573),(.629,.551),
           (.645,.530),(.611,.520),(.611,.480),(.645,.470)]
    a.facet(blade,(98,111,122),.38)
    a.polygon([(.635,.450),(.683,.433),(.889,.5),(.704,.486),(.649,.474)],
              (182,193,193))
    a.polygon([(.635,.550),(.683,.567),(.889,.5),(.704,.514),(.649,.526)],
              (41,51,62))
    a.polygon([(.654,.479),(.709,.486),(.889,.5),(.709,.514),(.654,.522)],
              (90,105,114))
    a.line([(.66,.497),(.845,.5)],_EDGE,.005)
    a.polygon([(.663,.486),(.702,.49),(.744,.5),(.702,.51),(.663,.514)],a.signal)
    a.line([(.680,.498),(.723,.5)],a.core,.003)
    a.line([(.685,.431),(.892,.499)],_PALE,.004)
    a.rivet(.622,.5,.006)


def _bone(a):
    # Jagged bone segment: flared joint, tapered medullary channel and hooked chips.
    silhouette = [(.109,.451),(.135,.423),(.182,.434),(.209,.465),(.305,.452),
                  (.363,.421),(.383,.447),(.441,.430),(.476,.395),(.498,.440),
                  (.560,.424),(.611,.383),(.628,.427),(.704,.440),(.746,.455),
                  (.898,.500),(.756,.533),(.713,.558),(.656,.555),(.599,.598),
                  (.582,.560),(.529,.566),(.489,.588),(.473,.557),(.408,.562),
                  (.351,.540),(.304,.556),(.211,.543),(.179,.574),(.139,.577),
                  (.111,.551),(.129,.518),(.126,.484)]
    a.facet(silhouette,_BONE,.42)
    a.polygon([(.122,.451),(.142,.436),(.177,.446),(.207,.479),(.306,.468),
               (.367,.439),(.379,.465),(.45,.449),(.48,.418),(.491,.461),
               (.570,.447),(.610,.411),(.621,.447),(.742,.472),(.887,.499),
               (.742,.491),(.507,.482),(.298,.501),(.189,.494),(.149,.482)],
              (200,194,175))
    a.polygon([(.140,.553),(.164,.560),(.199,.529),(.306,.538),(.355,.522),
               (.414,.543),(.477,.537),(.489,.568),(.526,.548),(.593,.541),
               (.601,.576),(.651,.538),(.711,.540),(.758,.518),(.881,.501),
               (.719,.511),(.505,.518),(.303,.522),(.193,.511),(.150,.522)],
              (92,89,82))
    # Long exposed inner groove, dark at the heel and pale toward the point.
    a.polygon([(.192,.493),(.309,.490),(.461,.481),(.599,.486),(.811,.499),
               (.646,.514),(.500,.516),(.303,.524),(.191,.518)],(74,75,72))
    a.line([(.207,.493),(.331,.497),(.471,.488),(.641,.495),(.848,.5)],
           (226,218,191),.006)
    a.line([(.224,.525),(.362,.532),(.461,.52)],(187,181,159),.004)
    # Visible cracks and irregular marrow pores, kept well below signal brightness.
    for crack in [[(.363,.425),(.359,.462),(.379,.481)],
                  [(.476,.402),(.468,.458),(.485,.473)],
                  [(.653,.552),(.655,.526),(.681,.516)],
                  [(.304,.551),(.310,.536),(.29,.525)]]:
        a.line(crack,(90,89,80),.0035)
    for x,y,r in [(.151,.463,.009),(.164,.542,.009),(.191,.488,.005),
                  (.423,.466,.005),(.522,.455,.004),(.687,.469,.004)]:
        a.ellipse((x-r,y-r*.58,x+r,y+r*.58),(114,109,96))
        a.line([(x-r*.5,y+r*.8),(x+r*.55,y+r*.5)],(208,199,176),.0015)
    # Leather-bound heel creates a credible assembled weapon rather than a shard.
    _binding(a,.242,.335,.044,True)
    a.line([(.25,.46),(.324,.46)],(151,138,106),.003)
    a.facet([(.324,.458),(.345,.455),(.351,.540),(.33,.543)],(80,90,90),.35)
    a.rivet(.339,.483,.005)
    a.rivet(.342,.519,.005)
    # Thin necromantic inlay follows the channel, never fills the bone body.
    a.line([(.407,.505),(.468,.499),(.536,.502),(.573,.497),(.707,.501)],
           _mix(a.signal,(67,77,72),.17),.009)
    a.line([(.47,.499),(.505,.501)],a.core,.003)
    for x in [.432,.554,.627]:
        a.line([(x,.496),(x+.009,.48),(x+.016,.490)],a.signal,.003)


def render_arrow(kind: str, size: int, signal_hex: str, core_hex: str) -> np.ndarray:
    """Return a square uint8 straight-alpha RGBA sprite with transparent padding.

    The four kinds are ``hunter_arrow``, ``barbed_arrow``, ``crossbow_bolt`` and
    ``bone_lance``. Shape coordinates stay within [0.10, 0.90]; antialiasing is
    rendered at a minimum of 1024 px, then downsampled with Lanczos filtering.
    """
    if kind not in _KINDS:
        raise ValueError(f"Unknown arrow kind: {kind}")
    if not isinstance(size, int) or not 16 <= size <= 4096:
        raise ValueError("size must be an integer between 16 and 4096")
    art = _Art(min(2048, max(1024, size * 4)), _rgb(signal_hex), _rgb(core_hex))
    {"hunter_arrow": _hunter, "barbed_arrow": _barbed,
     "crossbow_bolt": _bolt, "bone_lance": _bone}[kind](art)
    # Pillow's RGBA resize uses premultiplied filtering internally and returns
    # straight alpha. Transparent RGB is cleared for clean downstream packing.
    out = np.array(art.im.resize((size, size), Image.Resampling.LANCZOS))
    out[out[..., 3] == 0, :3] = 0
    # Preserve the promised eight-percent empty border, including filter ringing.
    padding = math.ceil(size * .08)
    out[:padding] = 0
    out[-padding:] = 0
    out[:, :padding] = 0
    out[:, -padding:] = 0
    return out
