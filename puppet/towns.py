"""Painted settings for human stories: street, park (outdoors) and kitchen, shop, office, classroom, home (indoors).
Each returns the same four parallax layers as the cliff world: (depth, RGBA image). People stand with their feet on y = 1240."""
import math

import numpy as np
from PIL import Image

from . import engine as E
from .engine import BH, BW, _bd, _poly, _tex, bp, shade

STAGES = ("street", "park", "kitchen", "shop", "office", "classroom", "home")
INDOOR = ("kitchen", "shop", "office", "classroom", "home")
GROUND = 1240
PASTELS = [(252, 206, 120), (244, 136, 124), (132, 206, 176), (150, 176, 244), (252, 172, 206), (204, 172, 244), (250, 160, 90)]


def _dim(pal):
    lum = sum(pal["sky_top"]) / 3
    return max(0.5, min(1.0, (lum - 40) / 100)), lum < 100


def _c(col, dim):
    return shade(tuple(col), -(1 - dim) * 0.75) if dim < 1 else tuple(col)


def _layer():
    im = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
    return im, _bd(im)


def _rect(dr, x0, y0, x1, y1, fill, w=4):
    _poly(dr, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill, w)


def _windows(dr, x0, y0, x1, y1, cols, rows, lit, dim, rng, w=3):
    gw, gh = (x1 - x0) / cols, (y1 - y0) / rows
    for r in range(rows):
        for c in range(cols):
            on = lit and rng.random() < 0.6
            fill = (255, 226, 120) if on else _c((170, 214, 244), dim)
            _rect(dr, x0 + c * gw + gw * 0.2, y0 + r * gh + gh * 0.18, x0 + (c + 1) * gw - gw * 0.2, y0 + (r + 1) * gh - gh * 0.18, fill, w)


def _lollipop(dr, tx, ty, h, col, trunk=(120, 70, 60), w=5):
    _rect(dr, tx - h * 0.07, ty - h * 0.6, tx + h * 0.07, ty, trunk, w)
    can = [(tx + h * 0.46 * math.cos(a), ty - h * 0.82 + h * 0.42 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 20, endpoint=False)]
    _poly(dr, can, col, w)


def _lamp(dr, x, base, h, dim, lit):
    _rect(dr, x - 6, base - h, x + 6, base, (70, 70, 84), 3)
    _poly(dr, [(x - 26, base - h), (x + 26, base - h), (x + 18, base - h - 44), (x - 18, base - h - 44)], (255, 226, 120) if lit else _c((236, 236, 220), dim), 4)


# ----------------------------------------------------------------- outdoor
def _street(pal, sky, seed, dim, night):
    rng = np.random.default_rng(seed + 20)
    far, fd = _layer()
    x = -520
    while x < 1700:                                           # distant skyline
        w, h = rng.uniform(110, 220), rng.uniform(280, 700)
        col = _c(E.shade(pal["far"], rng.uniform(-0.1, 0.14)), dim)
        _rect(fd, x, 1190 - h, x + w, 1200, col, 4)
        _windows(fd, x + 14, 1190 - h + 30, x + w - 14, 1170, 3, max(2, int(h / 70)), night, dim, rng, 2)
        x += w + rng.uniform(-10, 24)
    far = _tex(far, seed + 21, 5, 8)
    mid, md = _layer()
    x = -560
    k = 0
    while x < 1700:                                           # shopfront row
        w, h = rng.uniform(250, 340), rng.uniform(340, 430)
        col = _c(PASTELS[k % len(PASTELS)], dim)
        k += 1
        _rect(md, x, 1200 - h, x + w, 1204, col, 4.5)
        _rect(md, x - 8, 1200 - h - 26, x + w + 8, 1200 - h, shade(col, -0.3), 4.5)
        _windows(md, x + 30, 1200 - h + 36, x + w - 30, 1200 - h + 150, 2, 1, night, dim, rng, 4)
        _rect(md, x + w * 0.58, 1020, x + w * 0.58 + 74, 1204, _c((110, 70, 56), dim), 4)
        _poly(md, [(x + w * 0.58 + 58, 1114), (x + w * 0.58 + 66, 1114), (x + w * 0.58 + 66, 1124), (x + w * 0.58 + 58, 1124)], (250, 214, 90), 2)
        for j in range(5):                                    # striped awning over the shop window
            ax = x + 24 + j * (w * 0.5 / 5)
            _poly(md, [(ax, 1090), (ax + w * 0.5 / 5, 1090), (ax + w * 0.5 / 5 - 4, 1126), (ax - 4, 1126)], _c((250, 250, 244) if j % 2 else (226, 70, 80), dim), 3)
        _rect(md, x + 24, 1130, x + w * 0.52, 1170, _c((190, 226, 250), dim) if not night else (255, 226, 120), 3.5)
        x += w + rng.uniform(4, 20)
        if rng.random() < 0.35:
            _lollipop(md, x + 40, 1204, rng.uniform(190, 260), _c(pal["tree"], dim))
            x += 90
    for lx in (-150, 520, 1180):
        _lamp(md, lx, 1204, 300, dim, night)
    mid = _tex(mid, seed + 22, 6, 7)
    near, nd = _layer()
    _rect(nd, -600, 1186, 1800, 1300, _c(E.mix((214, 208, 196), pal["mist"], 0.15), dim), 4)
    for xx in np.arange(-600, 1800, 150):
        nd.line([bp(xx, 1186), bp(xx - 20, 1300)], fill=E.INK + (255,), width=max(1, int(2 * E.BS * 2)))
    _rect(nd, -600, 1300, 1800, 1322, _c((156, 152, 150), dim), 4)
    _rect(nd, -600, 1322, 1800, 2500, _c(E.mix((70, 74, 96), pal["far"], 0.25), dim), 0)
    for xx in np.arange(-560, 1800, 220):
        _rect(nd, xx, 1560, xx + 110, 1580, _c((240, 236, 210), dim), 2)
    return [(0.12, sky), (0.35, far), (0.62, mid), (1.0, _tex(near, seed + 23, 6, 6))]


def _park(pal, sky, seed, dim, night):
    rng = np.random.default_rng(seed + 30)
    far, fd = _layer()
    xs = np.linspace(-520, 1720, 16)
    ys = [1010 - rng.uniform(0.2, 1.0) * 260 for _ in xs]
    _poly(fd, list(zip(xs, ys)) + [(1720, 1300), (-520, 1300)], _c(pal["far"], dim), 4)
    far = _tex(far, seed + 31, 5, 8)
    mid, md = _layer()
    xs = np.linspace(-520, 1720, 12)
    ys = [1130 - rng.uniform(0.0, 1.0) * 90 for _ in xs]
    _poly(md, list(zip(xs, ys)) + [(1720, 1260), (-520, 1260)], _c(pal["mid"], dim), 4.5)
    for tx in np.arange(-480, 1700, 230):
        _lollipop(md, tx + rng.uniform(-40, 40), rng.uniform(1170, 1210), rng.uniform(300, 420), _c(E.shade(pal["tree"], rng.uniform(-0.1, 0.12)), dim))
    for xx in np.arange(-520, 1720, 44):                       # picket fence
        _poly(md, [(xx, 1196), (xx + 26, 1196), (xx + 26, 1120), (xx + 13, 1100), (xx, 1120)], _c((250, 244, 230), dim), 3)
    _rect(md, -520, 1140, 1720, 1156, _c((236, 228, 210), dim), 3)
    for lx in (60, 700):
        _lamp(md, lx, 1200, 280, dim, night)
    mid = _tex(mid, seed + 32, 6, 7)
    near, nd = _layer()
    _rect(nd, -600, 1190, 1800, 2500, _c(pal["grass"], dim), 4)
    _poly(nd, [(-100, 1190), (500, 1190), (760, 2500), (-420, 2500)], _c((238, 214, 160), dim), 4)      # sandy path
    for k in range(60):
        gx, gy = rng.uniform(-560, 1760), rng.uniform(1230, 2400)
        if abs(gx - (200 + (gy - 1190) * 0.2)) < 300 * (0.7 + (gy - 1190) / 1300):
            continue
        _poly(nd, [(gx - 8, gy), (gx, gy - 26), (gx + 8, gy)], _c(shade(pal["grass"], -0.18), dim), 0)
        if k % 5 == 0:
            for c, (dx, dy) in zip(((250, 90, 130), (250, 220, 90)), ((0, -34), (14, -28))):
                E._bd(near).ellipse([*bp(gx + dx - 7, gy + dy - 7), *bp(gx + dx + 7, gy + dy + 7)], fill=c + (255,), outline=E.INK + (255,), width=2)
    return [(0.12, sky), (0.35, far), (0.62, mid), (1.0, _tex(near, seed + 33, 6, 6))]


# ----------------------------------------------------------------- indoor
INTERIOR = {   # wall colour, floor colour, floor pattern
    "kitchen": ((255, 226, 150), (236, 232, 224), "checker"),
    "shop": ((170, 218, 200), (176, 124, 84), "planks"),
    "office": ((206, 216, 236), (110, 126, 170), "carpet"),
    "classroom": ((246, 232, 190), (190, 140, 96), "planks"),
    "home": ((248, 190, 190), (150, 104, 76), "planks"),
}


def _window(dr, x0, y0, x1, y1, dim, curtain=None):
    _rect(dr, x0, y0, x1, y1, (0, 0, 0, 0), 0)                # cut-out: the sky shows through
    for xx, yy in ((x0, y0), (x1, y0)):
        pass
    dr.line([bp(x0, y0), bp(x1, y0), bp(x1, y1), bp(x0, y1), bp(x0, y0)], fill=E.INK + (255,), width=max(2, int(9 * E.BS)))
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    dr.line([bp(mx, y0), bp(mx, y1)], fill=E.INK + (255,), width=max(2, int(7 * E.BS)))
    dr.line([bp(x0, my), bp(x1, my)], fill=E.INK + (255,), width=max(2, int(7 * E.BS)))
    _rect(dr, x0 - 14, y1, x1 + 14, y1 + 18, _c((250, 246, 236), dim), 4)
    if curtain:
        for sgn, cx in ((1, x0), (-1, x1)):
            _poly(dr, [(cx - sgn * 18, y0 - 10), (cx + sgn * 70, y0 - 10), (cx + sgn * 40, y1 + 10), (cx - sgn * 18, y1 + 10)], _c(curtain, dim), 4)


def _indoor(kind, pal, sky, seed, dim, night):
    rng = np.random.default_rng(seed + 40)
    wall, floor, pat = INTERIOR[kind]
    wd_ = 0.5 + dim * 0.5                                     # rooms stay lit, but a night outside makes them a little dimmer
    far, fd = _layer()
    _rect(fd, -520, -320, 1720, 1204, _c(wall, wd_), 0)
    if kind == "home":
        for xx in np.arange(-520, 1720, 70):
            _rect(fd, xx, -320, xx + 34, 1204, _c(shade(wall, -0.07), wd_), 0)
    if kind == "kitchen":
        for xx in np.arange(-520, 1720, 70):
            fd.line([bp(xx, 700), bp(xx, 1204)], fill=shade(wall, -0.25) + (255,), width=max(1, int(2 * E.BS * 2)))
        for yy in np.arange(700, 1204, 70):
            fd.line([bp(-520, yy), bp(1720, yy)], fill=shade(wall, -0.25) + (255,), width=max(1, int(2 * E.BS * 2)))
    _rect(fd, -520, 1170, 1720, 1210, _c(shade(wall, -0.22), wd_), 4)          # skirting
    wx0 = 560 if kind != "classroom" else 640
    _window(fd, wx0, 520, wx0 + 280, 860, dim, curtain=(220, 90, 110) if kind in ("home", "shop") else None)
    deco = {
        "kitchen": lambda: [(_rect(fd, -300 + k * 220, 470, -90 + k * 220, 740, _c((190, 120, 84), wd_), 4.5), _poly(fd, [(-190 + k * 220, 620), (-176 + k * 220, 620), (-176 + k * 220, 650), (-190 + k * 220, 650)], (250, 210, 90), 2)) for k in range(3)],
        "shop": lambda: [_shelf(fd, -480, y, 1000, wd_, rng) for y in (380, 600, 820)],
        "office": lambda: [_rect(fd, -300, 500, 150, 820, (252, 252, 250), 5), fd.line([bp(-260, 580), bp(40, 600), bp(-200, 680), bp(100, 720)], fill=(60, 120, 220, 255), width=max(2, int(6 * E.BS))),
                           E._bd(far).ellipse([*bp(210, 420), *bp(340, 550)], fill=(252, 252, 250, 255), outline=E.INK + (255,), width=5)],
        "classroom": lambda: [_rect(fd, -420, 420, 560, 880, (52, 100, 82), 7), _rect(fd, -420, 870, 560, 890, (170, 120, 80), 4),
                              fd.line([bp(-340, 540), bp(-80, 520), bp(-300, 640), bp(120, 660), bp(-250, 760), bp(300, 740)], fill=(240, 240, 232, 255), width=max(2, int(6 * E.BS)))],
        "home": lambda: [_rect(fd, -380 + k * 150, 460 - (k % 2) * 40, -260 + k * 150, 600 - (k % 2) * 40, _c(PASTELS[k + 2], wd_), 5) for k in range(3)],
    }[kind]
    deco()
    far = _tex(far, seed + 41, 4, 8)
    mid, md = _layer()
    if kind == "kitchen":
        _rect(md, -520, 1010, 900, 1214, _c((190, 120, 84), wd_), 4.5)
        _rect(md, -520, 990, 900, 1022, _c((236, 236, 240), wd_), 4.5)
        for k in range(6):
            _rect(md, -480 + k * 230, 1050, -310 + k * 230, 1190, _c((206, 140, 98), wd_), 3.5)
        _rect(md, 520, 920, 700, 990, _c((70, 70, 84), wd_), 4)                                   # stove with a pot
        E._bd(mid).ellipse([*bp(560, 860), *bp(660, 930)], fill=(200, 204, 214, 255), outline=E.INK + (255,), width=5)
    elif kind == "shop":
        _rect(md, -520, 1000, 760, 1214, _c((200, 150, 100), wd_), 4.5)
        _rect(md, -520, 976, 760, 1008, _c((240, 220, 180), wd_), 4.5)
        _rect(md, 500, 900, 640, 976, _c((90, 94, 110), wd_), 4)
        for k in range(5):
            _rect(md, -440 + k * 90, 920, -400 + k * 90, 976, _c(PASTELS[k], wd_), 3)
    elif kind == "office":
        for dx in (-320, 380):
            _rect(md, dx - 220, 1030, dx + 220, 1056, _c((190, 150, 110), wd_), 4.5)
            _rect(md, dx - 200, 1056, dx - 170, 1210, _c((150, 116, 86), wd_), 4)
            _rect(md, dx + 170, 1056, dx + 200, 1210, _c((150, 116, 86), wd_), 4)
            _rect(md, dx - 70, 900, dx + 70, 1030, (70, 74, 90), 4.5)
            _rect(md, dx - 56, 912, dx + 56, 1014, _c((150, 214, 250), wd_), 3)
    elif kind == "classroom":
        for k in range(4):
            dx = -400 + k * 330
            _rect(md, dx - 90, 1040, dx + 90, 1060, _c((220, 176, 120), wd_), 4)
            _rect(md, dx - 70, 1060, dx - 56, 1210, (90, 94, 110), 3)
            _rect(md, dx + 56, 1060, dx + 70, 1210, (90, 94, 110), 3)
        E._bd(mid).ellipse([*bp(640, 900), *bp(760, 1020)], fill=(90, 160, 230, 255), outline=E.INK + (255,), width=5)
    else:      # home: sofa and a lamp
        _rect(md, -400, 1040, 560, 1210, _c((90, 130, 200), wd_), 5)
        _rect(md, -440, 900, 600, 1050, _c(shade((90, 130, 200), -0.12), wd_), 5)
        for k in range(3):
            _rect(md, -380 + k * 310, 1000, -110 + k * 310, 1100, _c((110, 150, 220), wd_), 4)
        _lamp(md, 800, 1210, 360, dim, True)
    mid = _tex(mid, seed + 42, 6, 7)
    near, nd = _layer()
    _rect(nd, -600, 1190, 1800, 2500, _c(floor, wd_), 4)
    if pat == "checker":
        for r in range(0, 14):
            for c in range(-8, 24):
                if (r + c) % 2:
                    _poly(nd, [(c * 100, 1190 + r * 90), (c * 100 + 100, 1190 + r * 90), (c * 100 + 100, 1190 + r * 90 + 90), (c * 100, 1190 + r * 90 + 90)], _c((120, 150, 190), wd_), 0)
    elif pat == "planks":
        for yy in np.arange(1190, 2500, 78):
            nd.line([bp(-600, yy), bp(1800, yy)], fill=shade(floor, -0.35) + (255,), width=max(1, int(3 * E.BS * 2)))
    else:
        for yy in np.arange(1190, 2500, 60):
            nd.line([bp(-600, yy), bp(1800, yy)], fill=shade(floor, -0.12) + (255,), width=max(1, int(2 * E.BS * 2)))
    return [(0.12, sky), (0.35, far), (0.62, mid), (1.0, _tex(near, seed + 43, 6, 6))]


def _shelf(dr, x0, y, x1, dim, rng):
    _rect(dr, x0, y, x1, y + 16, _c((160, 110, 70), dim), 4)
    x = x0 + 10
    while x < x1 - 60:
        w, h = rng.uniform(34, 70), rng.uniform(56, 110)
        _rect(dr, x, y - h, x + w, y, _c(PASTELS[int(rng.integers(0, len(PASTELS)))], dim), 3.5)
        x += w + rng.uniform(4, 14)


def bake_town(pal, sky, seed):
    kind = pal["town"]
    dim, night = _dim(pal)
    if kind == "street":
        return _street(pal, sky, seed, dim, night)
    if kind == "park":
        return _park(pal, sky, seed, dim, night)
    return _indoor(kind, pal, sky, seed, dim, night)
