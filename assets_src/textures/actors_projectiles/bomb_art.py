"""Procedurally illustrated gothic alchemical ordnance, with no external assets."""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


INK = (10, 12, 19, 255)
STEEL = (104, 119, 129, 255)
STEEL_LIGHT = (184, 198, 201, 255)
STEEL_DARK = (38, 48, 58, 255)
BRASS = (140, 111, 65, 255)
BRASS_LIGHT = (205, 179, 117, 255)
BRASS_DARK = (58, 46, 35, 255)
BONE = (205, 191, 150, 255)


def _rgb(value):
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def _mix(a, b, weight):
    return tuple(round(a[i] * (1 - weight) + b[i] * weight) for i in range(3)) + (255,)


class Painter:
    def __init__(self, size):
        self.size = size
        self.image = Image.new("RGBA", (size, size))
        self.draw = ImageDraw.Draw(self.image)

    def xy(self, points):
        return [(round(x * self.size / 100), round(y * self.size / 100)) for x, y in points]

    def width(self, width):
        return max(1, round(width * self.size / 100))

    def poly(self, points, fill, outline=INK, width=0.65):
        points = self.xy(points)
        self.draw.polygon(points, fill=fill)
        if outline is not None:
            self.draw.line(points + points[:1], fill=outline, width=self.width(width), joint="curve")

    def line(self, points, fill, width=1):
        self.draw.line(self.xy(points), fill=fill, width=self.width(width), joint="curve")

    def ellipse(self, box, fill, outline=INK, width=0.65):
        self.draw.ellipse(self.xy([(box[0], box[1]), (box[2], box[3])]), fill=fill, outline=outline, width=self.width(width))

    def arc(self, box, start, end, fill, width=1):
        self.draw.arc(self.xy([(box[0], box[1]), (box[2], box[3])]), start=start, end=end, fill=fill, width=self.width(width))

    def rounded(self, box, radius, fill, outline=INK, width=0.65):
        self.draw.rounded_rectangle(self.xy([(box[0], box[1]), (box[2], box[3])]), radius=self.width(radius), fill=fill, outline=outline, width=self.width(width))

    def rivet(self, x, y, metal=BRASS_LIGHT):
        self.ellipse((x - 1.0, y - 1.0, x + 1.0, y + 1.0), _mix(metal, INK, 0.3), width=0.35)
        self.ellipse((x - 0.50, y - 0.55, x + 0.2, y + 0.1), metal, outline=None)

    def seal(self, x, y, radius, signal):
        self.ellipse((x-radius, y-radius, x+radius, y+radius), _mix(signal, (90, 30, 42), 0.68), width=0.7)
        self.ellipse((x-radius*.69, y-radius*.69, x+radius*.69, y+radius*.69), _mix(signal, INK, 0.56), signal, width=0.45)
        self.poly([(x,y-radius*.43),(x+radius*.35,y+radius*.28),(x-radius*.35,y+radius*.28)], fill=None, outline=BONE, width=0.48)
        self.line([(x-radius*.38,y+radius*.03),(x+radius*.38,y+radius*.03)], BONE, 0.4)

    def skull(self, x, y, scale=1):
        self.ellipse((x-4.0*scale,y-4.0*scale,x+4.0*scale,y+3.0*scale), BONE, width=.55)
        self.rounded((x-2.1*scale,y+1.0*scale,x+2.1*scale,y+4.7*scale), .5, BONE, width=.5)
        for dx in (-1.6, 1.6):
            self.ellipse((x+(dx-1)*scale,y-1.3*scale,x+(dx+1)*scale,y+0.8*scale), INK, outline=None)
        self.poly([(x,y+.3*scale),(x-.7*scale,y+1.8*scale),(x+.7*scale,y+1.8*scale)], INK, outline=None)
        for dx in (-.7,.7):
            self.line([(x+dx*scale,y+2.6*scale),(x+dx*scale,y+4.3*scale)], BRASS_DARK, .35)

    def radial_body(self, box, outline, color, highlight):
        """A material illustration gradient, confined to the unlit sprite artwork."""
        x0,y0,x1,y1 = box
        self.ellipse(box, outline, width=1)
        for index in range(32):
            t = index / 31
            inset = 1.5 + t * min(x1-x0,y1-y0) * .24
            shifted = (x0+inset-t*1.5,y0+inset-t*1.5,x1-inset-t*1.5,y1-inset-t*1.5)
            self.ellipse(shifted, _mix(color, highlight, t*.55), outline=None)


def _fuse(p, signal, core, x=54, y=20):
    curve=[(x,y),(x+1,y-4),(x+6,y-7),(x+12,y-6)]
    p.line(curve, INK, 3.0)
    p.line(curve, (151,132,93,255), 1.6)
    p.line([(x+4,y-6),(x+6,y-7)], (222,198,133,255), .8)
    p.poly([(x+10,y-7),(x+11,y-11),(x+13,y-8),(x+16,y-8),(x+14,y-5),(x+11,y-4)], signal, width=.5)
    p.ellipse((x+11,y-8,x+13.5,y-5.6), core, outline=None)


def _plague_flask(p, signal, core):
    # Pear flask in an iron cage, with alchemical fluid and a stamped skull seal.
    _fuse(p,signal,core,x=52,y=27)
    p.rounded((43,23,57,39),2,STEEL_DARK,width=1)
    p.poly([(42,34),(58,34),(61,45),(70,55),(72,69),(66,80),(55,85),(43,85),(31,79),(27,69),(29,56),(39,44)],STEEL_DARK,width=1.0)
    fluid=_mix(signal,(27,68,35),.66)
    p.radial_body((29,45,71,84),INK,_mix(fluid,INK,.35),fluid)
    p.poly([(37,48),(42,39),(58,39),(63,49),(58,46),(41,46)],_mix(signal,STEEL_DARK,.82),outline=None)
    p.ellipse((33,54,67,70),_mix(fluid,signal,.12),outline=None)
    p.arc((33,54,67,67),175,355,_mix(signal,core,.26),.95)
    p.ellipse((40,51,43,54),_mix(signal,core,.35),outline=None)
    p.ellipse((56,60,58,62),signal,outline=None)
    # Vertical ribs taper around the flask instead of obscuring its contents.
    for points in ([(37,45),(32,57),(34,75),(43,83)],[(63,45),(68,57),(65,76),(56,84)]):
        p.line(points,INK,3.4);p.line(points,STEEL,2.0)
        p.line(points[:2],STEEL_LIGHT,.55)
    p.arc((28,50,72,89),190,348,BRASS_DARK,4)
    p.arc((28,49,72,87),190,348,BRASS,2)
    p.poly([(39,35),(61,35),(60,42),(40,42)],BRASS,width=.8)
    p.line([(40,36),(59,36)],BRASS_LIGHT,1.0)
    for x in (43,50,57):p.rivet(x,39)
    p.rounded((43,24,57,31),1.2,BRASS,width=.7)
    p.line([(45,24),(55,24)],BRASS_LIGHT,.8)
    p.skull(50,66,.9)
    p.line([(38,47),(35,54),(35,62)],(181,211,178,255),.8)
    p.arc((33,46,69,83),80,140,signal,1.0)


def _reliquary_bomb(p, signal, core):
    # A miniature coffin reliquary: pointed shoulders, lancet window, wax and pins.
    _fuse(p,signal,core,x=50,y=24)
    p.poly([(42,24),(58,24),(69,38),(64,80),(56,87),(43,87),(36,80),(31,38)],INK,width=1)
    p.poly([(43,27),(57,27),(65,39),(61,77),(55,83),(45,83),(39,77),(35,39)],BRASS_DARK,width=.7)
    p.poly([(45,30),(55,30),(61,40),(58,76),(54,80),(46,80),(42,76),(39,40)],STEEL_DARK,width=.7)
    p.line([(44,28),(36,39),(40,77),(46,82)],BRASS_LIGHT,1.6)
    p.line([(56,28),(64,39),(60,77),(54,82)],BRASS,1.6)
    # Pointed cathedral window, with a signal-colored reagent inside.
    p.poly([(50,35),(58,44),(56,63),(44,63),(42,44)],INK,width=1.0)
    p.poly([(50,38),(55.5,45),(54,61),(46,61),(44.5,45)],_mix(signal,INK,.52),signal,.6)
    p.poly([(50,40),(52,46),(50.8,59),(49.2,59),(48,46)],core,outline=None)
    p.line([(44,49),(56,49)],BRASS,1.5)
    p.line([(50,39),(50,62)],BRASS,1.2)
    for x,y in ((42,36),(58,36),(40,64),(60,64),(46,79),(54,79)):p.rivet(x,y)
    # Heavy gothic shoulder lugs and engraved lower chevrons.
    p.poly([(34,39),(29,36),(30,46),(35,49)],STEEL,width=.8)
    p.poly([(66,39),(71,36),(70,46),(65,49)],STEEL,width=.8)
    p.line([(44,68),(50,72),(56,68)],BRASS_LIGHT,.9)
    p.line([(44,72),(50,76),(56,72)],BRASS,.7)
    p.seal(60,68,4.6,signal)
    p.poly([(58,72),(62,72),(64,81),(60,78),(58,81)],_mix(signal,INK,.62),width=.55)


def _censer_bomb(p,signal,core):
    # Suspended thurible: domed lid, perforated belly, short heavy chain and ember vents.
    for x,y in ((49,17),(52,22),(48,27)):
        p.ellipse((x-3,y-3,x+3,y+4),None,STEEL_LIGHT,1.3)
    p.poly([(46,28),(54,28),(57,37),(64,43),(64,48),(36,48),(36,43),(43,37)],BRASS_DARK,width=1)
    p.poly([(48,31),(52,31),(54,39),(61,44),(40,44),(46,39)],BRASS,outline=None)
    p.line([(49,32),(49,39),(42,43)],BRASS_LIGHT,1.0)
    p.radial_body((28,43,72,80),INK,BRASS_DARK,BRASS)
    p.poly([(36,48),(40,73),(47,83),(53,83),(60,73),(64,48)],BRASS_DARK,width=.8)
    p.poly([(40,49),(43,71),(49,80),(52,80),(58,71),(61,49)],BRASS,outline=None)
    for x in (37,45,53,61):
        top=53 if x in(45,53) else 51
        p.poly([(x,top),(x+2.4,top+3),(x+1.8,top+14),(x-1.8,top+14),(x-2.4,top+3)],INK,width=.4)
        p.poly([(x,top+3),(x+1.1,top+5),(x+.8,top+11),(x-.8,top+11),(x-1.1,top+5)],signal,outline=None)
        p.line([(x,top+5),(x,top+9)],core,.7)
    p.ellipse((28,44,72,52),BRASS,INK,.8)
    p.arc((29,44,71,51),185,350,BRASS_LIGHT,1)
    for x in (33,42,51,60,67):p.rivet(x,48)
    p.ellipse((43,78,57,83),BRASS_DARK,width=.8)
    p.poly([(47,82),(53,82),(50,88)],STEEL,width=.7)
    p.line([(30,49),(32,62),(39,76)],BRASS_LIGHT,1)
    p.seal(58,72,4.0,signal)


def _alchemical_grenade(p,signal,core):
    # Faceted glass ampoule, protective steel cage, winding crown and alchemy disk.
    _fuse(p,signal,core,x=54,y=27)
    p.poly([(41,25),(59,25),(61,33),(57,40),(66,48),(69,71),(61,83),(39,83),(31,71),(34,48),(43,40),(39,33)],INK,width=1)
    glass=_mix(signal,(22,51,64),.68)
    p.poly([(44,39),(56,39),(64,50),(65,70),(59,80),(41,80),(35,70),(36,50)],glass,width=.7)
    p.poly([(37,54),(47,57),(47,78),(41,78),(37,69)],_mix(glass,signal,.3),outline=None)
    p.poly([(49,55),(62,51),(63,69),(58,79),(49,79)],_mix(glass,INK,.25),outline=None)
    p.line([(37,54),(47,57),(62,51)],signal,1.0)
    p.line([(40,47),(38,52),(39,64)],_mix(signal,core,.65),1.1)
    for points in ([(41,40),(35,49),(36,72),(42,81)],[(59,40),(65,49),(64,72),(58,81)]):
        p.line(points,INK,4);p.line(points,STEEL,2.6);p.line(points[:2],STEEL_LIGHT,.8)
    p.poly([(37,72),(63,72),(60,81),(40,81)],STEEL_DARK,width=.7)
    p.line([(39,74),(61,74)],STEEL_LIGHT,1)
    p.rounded((40,26,60,34),1.4,STEEL,width=.9)
    p.line([(41,27),(59,27)],STEEL_LIGHT,1.0)
    for x in (43,47,51,55,59):p.line([(x,29),(x,33)],STEEL_DARK,.8)
    p.ellipse((44,43,57,56),BRASS_DARK,BRASS,.8)
    p.poly([(50,45),(54,53),(46,53)],fill=None,outline=BRASS_LIGHT,width=.7)
    p.line([(45,50),(55,50)],core,.65)
    for x,y in ((38,59),(62,59),(43,77),(57,77)):p.rivet(x,y,STEEL_LIGHT)
    p.seal(57,67,4.4,signal)


_DRAWERS={"plague_flask":_plague_flask,"reliquary_bomb":_reliquary_bomb,
          "censer_bomb":_censer_bomb,"alchemical_grenade":_alchemical_grenade}


def render_bomb(kind: str, size: int, signal_hex: str, core_hex: str) -> np.ndarray:
    if kind not in _DRAWERS or size < 16:
        raise ValueError("Unknown bomb type or unsupported size")
    render_size=max(512,min(2048,size*2))
    p=Painter(render_size)
    _DRAWERS[kind](p,_rgb(signal_hex),_rgb(core_hex))
    # A restrained team-colored contour supports recognition against dark scenes.
    alpha=p.image.getchannel("A")
    expanded=alpha.filter(ImageFilter.MaxFilter(2*max(1,round(render_size*.006))+1))
    support=Image.new("RGBA",p.image.size,_rgb(signal_hex))
    support.putalpha(expanded.point(lambda value: round(value*.68)))
    support.alpha_composite(p.image)
    output=support.resize((size,size),Image.Resampling.LANCZOS)
    pixels=np.array(output)
    pixels[pixels[...,3]==0,:3]=INK[:3]
    return pixels
