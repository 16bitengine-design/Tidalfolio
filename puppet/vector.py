"""The "vector" look: modern flat-vector cartoon, drawn in code with anti-aliased shapes (skia), many blended colours,
soft gradients, coloured shadows and light, no black outlines. Worlds are drawn live (not baked) so the camera can move freely.

Worlds keep the old names ("toon_dawn_shop" = dawn, shop interior): the time of day and the setting are read from the name.
Characters live in vector_people.py."""
import math
import random

import numpy as np
import skia
from PIL import Image

from . import engine as E

W, H = E.W, E.H
GROUND = 1240
STAGES = ("street", "park", "kitchen", "shop", "office", "classroom", "home")
INDOOR = ("kitchen", "shop", "office", "classroom", "home")

_surf = None
cv = None


# ------------------------------------------------------------------ canvas and colour helpers
def begin():
    """Start a frame: returns the canvas, cleared, with no camera applied."""
    global _surf, cv
    if _surf is None:
        _surf = skia.Surface(W, H)
    cv = _surf.getCanvas()
    cv.resetMatrix()
    cv.clear(skia.Color(0, 0, 0, 255))
    return cv


def to_pil():
    a = _surf.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    return Image.fromarray(np.ascontiguousarray(a[:, :, :3]))


def cam(depth=1.0):
    """Camera for a layer at this depth (1 = the stage where people stand; smaller = further away, moves less)."""
    z = 1 + (E.C.z - 1) * depth
    cx = W / 2 + (E.C.cx - W / 2) * depth
    cy = H / 2 + (E.C.cy - H / 2) * depth
    cv.resetMatrix()
    cv.translate(W / 2, H / 2)
    cv.scale(z, z)
    cv.translate(-cx, -cy)


def mixc(a, b, k):
    k = max(0.0, min(1.0, k))
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def lite(c, k):
    """lighter, leaning warm"""
    return mixc(c, (255, 244, 222), k)


def dark(c, k):
    """darker, leaning violet: shadows that carry colour instead of grey"""
    return mixc(c, (44, 24, 96), k)


def hue(c, dh=0.0, ds=0.0, dv=0.0):
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(c[0] / 255, c[1] / 255, c[2] / 255)
    r, g, b = colorsys.hsv_to_rgb((h + dh) % 1.0, max(0, min(1, s + ds)), max(0, min(1, v + dv)))
    return (int(r * 255), int(g * 255), int(b * 255))


def K(c, a=255):
    return skia.Color(int(c[0]), int(c[1]), int(c[2]), int(a))


def paint(c=None, a=255, shader=None, stroke=0.0, blur=0.0, mode=None, dash=None):
    p = skia.Paint(AntiAlias=True, Dither=True)
    if shader is not None:
        p.setShader(shader)
    else:
        p.setColor(K(c, a))
    if stroke:
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeWidth(stroke)
        p.setStrokeCap(skia.Paint.kRound_Cap)
        p.setStrokeJoin(skia.Paint.kRound_Join)
    if blur:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    if mode is not None:
        p.setBlendMode(mode)
    if dash:
        p.setPathEffect(skia.DashPathEffect.Make(list(dash), 0))
    return p


def lin(x0, y0, x1, y1, stops):
    """linear gradient shader; stops = [(pos 0..1, (r,g,b) or (r,g,b,a)), ...]"""
    cols = [K(c[:3], c[3] if len(c) > 3 else 255) for _, c in stops]
    return skia.GradientShader.MakeLinear([(x0, y0), (x1, y1)], cols, [p for p, _ in stops])


def rad(cx, cy, r, stops):
    cols = [K(c[:3], c[3] if len(c) > 3 else 255) for _, c in stops]
    return skia.GradientShader.MakeRadial((cx, cy), max(1.0, r), cols, [p for p, _ in stops])


def rect(x0, y0, x1, y1, p):
    cv.drawRect(skia.Rect(x0, y0, x1, y1), p)


def rrect(x0, y0, x1, y1, r, p):
    cv.drawRoundRect(skia.Rect(x0, y0, x1, y1), r, r, p)


def oval(cx, cy, rx, ry, p):
    cv.drawOval(skia.Rect(cx - rx, cy - ry, cx + rx, cy + ry), p)


def path_of(pts, closed=True):
    p = skia.Path()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    if closed:
        p.close()
    return p


def poly(pts, p, closed=True):
    cv.drawPath(path_of(pts, closed), p)


def smooth(pts, p, closed=True):
    """a closed shape through the midpoints of its edges, so every corner is rounded"""
    n = len(pts)
    path = skia.Path()
    mid = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    m0 = mid(pts[-1], pts[0]) if closed else pts[0]
    path.moveTo(*m0)
    for i in range(n if closed else n - 1):
        a, b = pts[i], pts[(i + 1) % n]
        m = mid(a, b)
        path.quadTo(a[0], a[1], m[0], m[1]) if closed else path.lineTo(*b)
    if closed:
        path.close()
    cv.drawPath(path, p)


def curve(pts, p):
    """an open smooth line through the given points"""
    path = skia.Path()
    path.moveTo(*pts[0])
    for i in range(1, len(pts) - 1):
        m = ((pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2)
        path.quadTo(pts[i][0], pts[i][1], m[0], m[1]) if i < len(pts) - 2 else path.quadTo(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
    cv.drawPath(path, p)


def line(x0, y0, x1, y1, c, w, a=255):
    cv.drawLine(x0, y0, x1, y1, paint(c, a, stroke=w))


def glow(cx, cy, r, c, a=160, mode=None):
    oval(cx, cy, r, r, paint(shader=rad(cx, cy, r, [(0, c + (a,)), (0.45, c + (a * 0.35,)), (1, c + (0,))]), mode=mode))


def soft_shadow(cx, cy, rx, ry, c=(40, 20, 90), a=110, blur=None):
    oval(cx, cy, rx, ry, paint(c, a, blur=blur or max(4, ry * 0.5)))


# ------------------------------------------------------------------ times of day
TIMES = {
    "dawn": dict(sky=[(0, (84, 80, 176)), (.32, (200, 106, 176)), (.62, (255, 160, 122)), (1, (255, 224, 156))], sun=(260, 1000, 110, (255, 238, 176)),
                 hills=[(176, 124, 188), (206, 120, 156), (112, 156, 126)], cloud=(255, 214, 204), tint=(255, 160, 100, 26), warm=(255, 196, 140), dim=0.0),
    "day": dict(sky=[(0, (40, 126, 236)), (.55, (96, 192, 248)), (1, (206, 242, 252))], sun=(880, 250, 96, (255, 240, 160)),
                hills=[(128, 150, 226), (84, 190, 178), (128, 204, 110)], cloud=(255, 255, 255), tint=(255, 240, 200, 0), warm=(255, 240, 190), dim=0.0),
    "dusk": dict(sky=[(0, (56, 48, 152)), (.4, (148, 80, 192)), (.74, (244, 126, 146)), (1, (255, 192, 134))], sun=(800, 1040, 100, (255, 204, 128)),
                 hills=[(122, 88, 176), (160, 94, 148), (84, 124, 120)], cloud=(250, 190, 200), tint=(200, 90, 170, 34), warm=(255, 176, 130), dim=0.12),
    "storm": dict(sky=[(0, (44, 50, 96)), (.5, (92, 100, 150)), (1, (150, 158, 196))], sun=None,
                  hills=[(74, 86, 134), (60, 104, 124), (64, 112, 98)], cloud=(110, 118, 160), tint=(30, 56, 120, 58), warm=(210, 220, 255), dim=0.3, rain=True),
    "night": dict(sky=[(0, (8, 10, 60)), (.5, (34, 30, 118)), (1, (78, 70, 170))], sun=(800, 400, 72, (240, 240, 255)), moon=True,
                  hills=[(46, 44, 124), (32, 74, 112), (30, 90, 96)], cloud=(78, 80, 150), tint=(10, 18, 96, 100), warm=(255, 206, 120), dim=0.45, stars=True),
    "sunset": dict(sky=[(0, (72, 38, 146)), (.3, (194, 50, 146)), (.6, (255, 108, 82)), (1, (255, 204, 92))], sun=(700, 1040, 130, (255, 216, 124)),
                   hills=[(156, 68, 156), (196, 88, 126), (112, 112, 96)], cloud=(255, 160, 150), tint=(255, 100, 40, 38), warm=(255, 170, 90), dim=0.1),
}


def parse_world(name):
    parts = str(name).replace("toon_", "").replace("vec_", "").split("_")
    tm = parts[0] if parts and parts[0] in TIMES else "day"
    st = parts[-1] if parts and parts[-1] in STAGES else "street"
    return tm, st


# ------------------------------------------------------------------ sky and distance
def sky(T, t):
    cam(0.2)
    rect(-2600, -1400, 3800, GROUND + 400, paint(shader=lin(0, -300, 0, GROUND, T["sky"])))
    if T.get("stars"):
        r = random.Random(5)
        for i in range(90):
            x, y = r.uniform(-900, 2000), r.uniform(-300, 900)
            tw = 0.5 + 0.5 * math.sin(t * (1.2 + r.random() * 2) + i)
            c = r.choice([(255, 255, 255), (255, 232, 170), (190, 210, 255), (255, 190, 230)])
            oval(x, y, 2.2 + tw * 2.2, 2.2 + tw * 2.2, paint(c, 150 + 100 * tw))
    if T.get("sun"):
        sx, sy, sr, sc = T["sun"]
        glow(sx, sy, sr * 3.4, sc, 120)
        glow(sx, sy, sr * 1.9, sc, 150)
        oval(sx, sy, sr, sr, paint(shader=rad(sx - sr * 0.3, sy - sr * 0.3, sr * 1.5, [(0, lite(sc, 0.6)), (1, sc)])))
        if T.get("moon"):
            for (dx, dy, rr) in ((-22, -12, 18), (18, 22, 13), (26, -22, 9)):
                oval(sx + dx, sy + dy, rr, rr, paint(dark(sc, 0.18), 120))
    clouds(T, t)
    if T["sky"] and not T.get("stars") and not T.get("rain") and T is not TIMES["day"] or T is TIMES["day"]:
        r = random.Random(9)
        for i in range(5):                       # little birds
            bx = (r.uniform(-300, 1500) + t * (8 + i * 2)) % 2300 - 400
            by = r.uniform(120, 620)
            if T is TIMES["day"] or T is TIMES["dawn"]:
                fl = math.sin(t * 7 + i) * 5
                curve([(bx - 12, by - fl), (bx, by + 5), (bx + 12, by - fl)], paint((70, 60, 110), 200, stroke=3))


def clouds(T, t):
    r = random.Random(3)
    n = 8 if T.get("rain") else 6
    for i in range(n):
        cx = (r.uniform(-500, 1700) + t * (6 + i)) % 2400 - 600
        cy = r.uniform(80, 760)
        s = r.uniform(0.8, 1.7) * (1.4 if T.get("rain") else 1.0)
        base, top = T["cloud"], lite(T["cloud"], 0.35)
        low = dark(T["cloud"], 0.22)
        for dx, dy, rx, ry in ((-70, 14, 80, 40), (0, -8, 96, 56), (74, 12, 82, 42), (20, 22, 120, 34)):
            oval(cx + dx * s, cy + dy * s + 8 * s, rx * s, ry * s, paint(low, 170))
        for dx, dy, rx, ry in ((-70, 6, 78, 38), (0, -14, 92, 54), (74, 4, 80, 40), (20, 14, 116, 32)):
            oval(cx + dx * s, cy + dy * s, rx * s, ry * s, paint(shader=lin(0, cy - 60 * s, 0, cy + 40 * s, [(0, top), (1, base)])))


def hills(T, depth, base_y, amp, col, seed, tall=520):
    cam(depth)
    r = random.Random(seed)
    ph = [r.uniform(0, 6) for _ in range(3)]
    pts = [(-1800, base_y + 900)]
    for i in range(0, 61):
        x = -1800 + i * 80
        y = base_y - amp * (0.55 * math.sin(x / 330 + ph[0]) + 0.3 * math.sin(x / 140 + ph[1]) + 0.15 * math.sin(x / 70 + ph[2]) + 0.6)
        pts.append((x, y))
    pts.append((2400, base_y + 900))
    poly(pts, paint(shader=lin(0, base_y - amp * 1.2, 0, base_y + 200, [(0, lite(col, 0.28)), (1, dark(col, 0.14))])))


def rain(T, t):
    cv.resetMatrix()
    r = random.Random(2)
    for i in range(70):
        x = (r.uniform(-200, W + 200) - t * 160) % (W + 400) - 200
        y = (r.uniform(0, H) + t * (900 + r.random() * 400)) % (H + 200) - 100
        l = 38 + r.random() * 30
        cv.drawLine(x, y, x - 8, y + l, paint((210, 226, 255), 120, stroke=3))
    # an occasional flash of lightning
    fl = max(0.0, math.sin(t * 0.8 + 1.3)) ** 40
    if fl > 0.04:
        rect(0, 0, W, H, paint((255, 250, 255), int(120 * fl)))


# ------------------------------------------------------------------ small scenery
def tree(x, base, h, T, seed, kind=None):
    r = random.Random(seed)
    cols = [(86, 190, 120), (46, 160, 140), (150, 200, 80), (240, 150, 70), (236, 110, 160), (120, 100, 210)]
    c = r.choice(cols) if kind is None else cols[kind % len(cols)]
    c = mixc(c, T["hills"][2], 0.18 + T["dim"] * 0.4)
    tw = h * 0.07
    poly([(x - tw, base), (x - tw * 0.6, base - h * 0.55), (x + tw * 0.6, base - h * 0.55), (x + tw, base)], paint(shader=lin(x - tw, 0, x + tw, 0, [(0, (150, 96, 76)), (1, (96, 60, 78))])))
    cx, cy, R = x, base - h * 0.72, h * 0.34
    oval(cx + 8, cy + 14, R * 1.0, R * 0.92, paint(dark(c, 0.3)))
    for dx, dy, rr in ((-0.55, 0.15, 0.62), (0.55, 0.1, 0.62), (0, -0.35, 0.78), (0, 0.2, 0.84)):
        oval(cx + dx * R, cy + dy * R, rr * R, rr * R * 0.95, paint(shader=rad(cx + dx * R - rr * R * 0.3, cy + dy * R - rr * R * 0.4, rr * R * 1.5, [(0, lite(c, 0.3)), (0.6, c), (1, dark(c, 0.18))])))
    for k in range(4):
        oval(cx + r.uniform(-0.6, 0.6) * R, cy + r.uniform(-0.6, 0.4) * R, R * 0.12, R * 0.12, paint(lite(c, 0.55), 170))


def lamp(x, base, h, T, lit):
    pole = (54, 48, 96) if T["dim"] > 0.2 else (88, 96, 130)
    rrect(x - 5, base - h, x + 5, base, 4, paint(pole))
    rrect(x - 5, base - h - 6, x + 38, base - h + 8, 6, paint(pole))
    if lit:
        glow(x + 28, base - h + 18, 150, T["warm"], 150)
    oval(x + 28, base - h + 14, 15, 11, paint(T["warm"] if lit else (230, 236, 250)))


def windows_grid(x0, y0, x1, y1, cols, rows, lit, T, r, gap=0.34):
    cw, rh = (x1 - x0) / cols, (y1 - y0) / rows
    for i in range(cols):
        for j in range(rows):
            wx, wy = x0 + i * cw + cw * gap / 2, y0 + j * rh + rh * gap / 2
            on = lit and r.random() < 0.55
            c = mixc(T["warm"], (255, 255, 235), 0.2) if on else mixc(T["sky"][2][1], (220, 240, 255), 0.35)
            rrect(wx, wy, wx + cw * (1 - gap), wy + rh * (1 - gap), 4, paint(c, 255 if on else 170))


BUILD = [(244, 112, 122), (255, 190, 90), (96, 200, 180), (120, 150, 240), (190, 130, 230), (255, 150, 110), (110, 210, 130), (240, 130, 190)]


def skyline(T, depth, base_y, seed, big):
    cam(depth)
    r = random.Random(seed)
    x = -1500
    night = T["dim"] > 0.2
    while x < 2300:
        w = r.uniform(150, 280) * (1.2 if big else 0.8)
        h = r.uniform(260, 620) * (1.25 if big else 0.85)
        c = r.choice(BUILD)
        c = mixc(c, T["hills"][0], 0.34 + (0 if big else 0.22))
        c = mixc(c, (40, 30, 110), T["dim"] * 0.7)
        rrect(x, base_y - h, x + w, base_y + 40, 8, paint(shader=lin(x, 0, x + w, 0, [(0, lite(c, 0.12)), (1, dark(c, 0.2))])))
        rect(x - 6, base_y - h - 12, x + w + 6, base_y - h + 6, paint(dark(c, 0.25)))
        if big:
            windows_grid(x + 18, base_y - h + 30, x + w - 18, base_y - 50, max(2, int(w // 52)), max(3, int(h // 80)), night or T is TIMES["dusk"], T, r)
        if r.random() < 0.3:
            rect(x + w * 0.5 - 3, base_y - h - 60, x + w * 0.5 + 3, base_y - h - 12, paint(dark(c, 0.3)))
        x += w + r.uniform(-10, 24)


# ------------------------------------------------------------------ outdoor stages
def ground_band(y0, y1, stops, x0=-2600, x1=3800):
    rect(x0, y0, x1, y1, paint(shader=lin(0, y0, 0, y1, stops)))


def street(T, t):
    night = T["dim"] > 0.2
    hills(T, 0.45, 1000, 160, T["hills"][0], 3)
    skyline(T, 0.7, 1150, 11, False)
    skyline(T, 0.9, 1200, 12, True)
    cam(1.0)
    pave = mixc((236, 214, 196), T["hills"][0], 0.2)
    ground_band(1180, 1250, [(0, dark((120, 178, 120), 0.1)), (1, (96, 150, 108))])
    r = random.Random(4)
    for x in range(-500, 1800, 340):                       # shop awnings along the buildings
        c = r.choice([(240, 80, 100), (255, 180, 60), (80, 190, 170), (120, 120, 240)])
        c = mixc(c, (40, 30, 110), T["dim"] * 0.6)
        for k in range(6):
            poly([(x + k * 42, 1020), (x + k * 42 + 42, 1020), (x + k * 42 + 54, 1090), (x + k * 42 + 12, 1090)], paint(c if k % 2 else lite(c, 0.7)))
    tree(120, 1236, 520, T, 21, 0)
    tree(1080, 1236, 560, T, 22, 3)
    lamp(700, 1236, 520, T, night)
    lamp(-200, 1236, 520, T, night)
    ground_band(1240, 2300, [(0, lite(pave, 0.14)), (.3, pave), (1, dark(pave, 0.3))])
    for k in range(14):                                    # paving lines converging to the viewer
        y = 1240 + (k ** 1.5) * 18
        rect(-2600, y, 3800, y + 3, paint(dark(pave, 0.25), 90))
    for k in range(-16, 22):
        x = k * 120
        poly([(x, 1240), (x + 4, 1240), (x + (x - 540) * 0.5 + 4, 2300), (x + (x - 540) * 0.5, 2300)], paint(dark(pave, 0.25), 60))
    rect(-2600, 1240, 3800, 1252, paint(lite(pave, 0.5), 220))
    if night:
        glow(728, 1240, 260, T["warm"], 90)


def park(T, t):
    hills(T, 0.4, 1060, 200, T["hills"][0], 6)
    hills(T, 0.62, 1130, 160, T["hills"][1], 7)
    hills(T, 0.85, 1190, 110, T["hills"][2], 8)
    cam(0.85)
    r = random.Random(8)
    for i in range(7):
        tree(-400 + i * 330 + r.uniform(-40, 40), 1215, r.uniform(380, 560), T, 30 + i, i)
    cam(1.0)
    g = mixc(T["hills"][2], (120, 214, 90), 0.5)
    g = mixc(g, (40, 30, 110), T["dim"] * 0.55)
    ground_band(1236, 2300, [(0, lite(g, 0.1)), (.5, g), (1, dark(g, 0.28))])
    for k in range(10):                                    # mown stripes
        y0 = 1240 + k * k * 11
        rect(-2600, y0, 3800, y0 + 14 + k * 5, paint(lite(g, 0.14), 60))
    pth = mixc((236, 206, 160), T["hills"][0], 0.2)
    poly([(430, 1240), (640, 1240), (900, 2300), (-140, 2300)], paint(shader=lin(0, 1240, 0, 2300, [(0, lite(pth, 0.2)), (1, pth)])), True)
    r2 = random.Random(5)
    for i in range(70):                                    # flowers in many colours
        x, y = r2.uniform(-500, 1700), r2.uniform(1260, 2000)
        c = r2.choice([(255, 120, 160), (255, 220, 90), (255, 255, 255), (170, 140, 255), (255, 160, 80)])
        sz = 4 + (y - 1240) / 90
        oval(x, y, sz, sz, paint(c))
        oval(x, y, sz * 0.4, sz * 0.4, paint((255, 210, 70)))
    # bench
    bx, by = 1040, 1250
    rrect(bx - 90, by - 70, bx + 90, by - 50, 8, paint((200, 120, 84)))
    rrect(bx - 90, by - 100, bx + 90, by - 82, 8, paint((214, 140, 96)))
    rrect(bx - 80, by - 50, bx - 68, by, 4, paint((90, 60, 100)))
    rrect(bx + 68, by - 50, bx + 80, by, 4, paint((90, 60, 100)))


# ------------------------------------------------------------------ indoor stages
WALLS = {"kitchen": ((255, 214, 120), (255, 170, 110)), "shop": ((130, 214, 196), (90, 170, 190)), "office": ((200, 214, 252), (160, 180, 236)),
         "classroom": ((120, 200, 170), (80, 160, 160)), "home": ((255, 196, 206), (236, 150, 176))}
FLOORS = {"kitchen": ((226, 150, 110), (180, 100, 100)), "shop": ((214, 160, 110), (166, 110, 100)), "office": ((150, 156, 210), (110, 110, 170)),
          "classroom": ((226, 180, 120), (180, 130, 100)), "home": ((220, 150, 120), (172, 100, 108))}


def window(x0, y0, x1, y1, T, t, curtain=None, city=True):
    rrect(x0 - 16, y0 - 16, x1 + 16, y1 + 16, 14, paint((250, 244, 236)))
    cv.save()
    cv.clipRect(skia.Rect(x0, y0, x1, y1))
    rect(x0, y0, x1, y1, paint(shader=lin(0, y0, 0, y1, T["sky"])))
    if T.get("sun"):
        oval(x0 + (x1 - x0) * 0.72, y0 + (y1 - y0) * 0.3, 26, 26, paint(T["sun"][3], 230))
    for k in range(3):
        cx = x0 + ((k * 130 + t * 8) % (x1 - x0 + 160)) - 60
        oval(cx, y0 + 60 + k * 34, 50, 20, paint(T["cloud"], 200))
    if city:
        r = random.Random(int(x0))
        bx = x0
        while bx < x1:
            bw, bh = r.uniform(36, 70), r.uniform(60, 180)
            c = mixc(r.choice(BUILD), T["hills"][0], 0.4)
            c = mixc(c, (40, 30, 110), T["dim"] * 0.7)
            rect(bx, y1 - bh, bx + bw, y1, paint(c))
            bx += bw + 3
    cv.restore()
    rect(x0 + (x1 - x0) / 2 - 5, y0, x0 + (x1 - x0) / 2 + 5, y1, paint((250, 244, 236)))
    rect(x0, y0 + (y1 - y0) * 0.5 - 5, x1, y0 + (y1 - y0) * 0.5 + 5, paint((250, 244, 236)))
    if curtain:
        for sx, ex in ((x0 - 34, x0 + 52), (x1 - 52, x1 + 34)):
            poly([(sx, y0 - 30), (ex, y0 - 30), (ex - 10, y1 + 30), (sx + 6, y1 + 30)], paint(shader=lin(sx, 0, ex, 0, [(0, curtain), (.5, lite(curtain, 0.2)), (1, dark(curtain, 0.2))])))
        rrect(x0 - 50, y0 - 44, x1 + 50, y0 - 26, 9, paint(dark(curtain, 0.3)))
    if T["dim"] < 0.2:                                      # a shaft of light falling into the room
        poly([(x0, y1), (x1, y1), (x1 + 330, GROUND + 600), (x0 + 120, GROUND + 600)], paint(shader=lin(0, y1, 0, GROUND + 600, [(0, T["warm"] + (70,)), (1, T["warm"] + (0,))])))


def wall_and_floor(kind, T, t):
    cam(1.0)
    w0, w1 = WALLS[kind]
    w0, w1 = mixc(w0, (40, 30, 110), T["dim"] * 0.45), mixc(w1, (40, 30, 110), T["dim"] * 0.45)
    rect(-2600, -1400, 3800, GROUND + 4, paint(shader=lin(0, -300, 0, GROUND, [(0, lite(w0, 0.15)), (1, w1)])))
    if kind in ("home", "shop", "office"):                  # wallpaper stripes
        for x in range(-1000, 2000, 90):
            rect(x, -300, x + 38, GROUND - 120, paint(lite(w0, 0.25), 70))
    if kind == "classroom":
        for x in range(-1000, 2000, 60):
            oval(x, 240 + (x // 60 % 3) * 20, 5, 5, paint(lite(w0, 0.4), 120))
    rect(-2600, GROUND - 130, 3800, GROUND + 4, paint(shader=lin(0, GROUND - 130, 0, GROUND, [(0, dark(w1, 0.06)), (1, dark(w1, 0.22))])))
    rect(-2600, GROUND - 136, 3800, GROUND - 124, paint(lite(w0, 0.5)))
    f0, f1 = FLOORS[kind]
    f0, f1 = mixc(f0, (40, 30, 110), T["dim"] * 0.45), mixc(f1, (40, 30, 110), T["dim"] * 0.45)
    ground_band(GROUND, 2300, [(0, lite(f0, 0.08)), (.4, f0), (1, dark(f1, 0.2))])
    if kind in ("kitchen", "office", "classroom"):          # tiles in perspective
        for k in range(16):
            y = GROUND + (k ** 1.6) * 14
            rect(-2600, y, 3800, y + 3, paint(dark(f1, 0.3), 90))
        for k in range(-22, 26):
            x = k * 110
            poly([(x, GROUND), (x + 3, GROUND), (x + (x - 540) * 0.7 + 3, 2300), (x + (x - 540) * 0.7, 2300)], paint(dark(f1, 0.3), 70))
    else:                                                   # wooden planks
        for k in range(16):
            y = GROUND + (k ** 1.6) * 14
            rect(-2600, y, 3800, y + 4, paint(dark(f1, 0.35), 110))
        r = random.Random(3)
        for k in range(60):
            y = GROUND + r.uniform(0, 900)
            x = r.uniform(-900, 1900)
            rect(x, y, x + r.uniform(120, 360), y + 3, paint(lite(f0, 0.3), 70))
    soft_shadow(540, GROUND + 6, 1700, 26, dark(f1, 0.5), 90, 16)


def shelf(x0, x1, y, T, r, items=7, hmax=90):
    for i in range(items):
        bw = (x1 - x0) / items
        bx = x0 + i * bw + 6
        h = r.uniform(hmax * 0.5, hmax)
        c = r.choice(BUILD + [(255, 232, 130), (150, 230, 220)])
        c = mixc(c, (40, 30, 110), T["dim"] * 0.45)
        if r.random() < 0.5:
            rrect(bx, y - h, bx + bw - 12, y, 7, paint(shader=lin(bx, 0, bx + bw, 0, [(0, lite(c, 0.18)), (1, dark(c, 0.14))])))
            rect(bx + 6, y - h * 0.6, bx + bw - 18, y - h * 0.4, paint(lite(c, 0.6), 160))
        else:
            oval(bx + (bw - 12) / 2, y - h * 0.4, (bw - 12) / 2, h * 0.4, paint(shader=rad(bx + bw * 0.35, y - h * 0.55, bw, [(0, lite(c, 0.4)), (1, dark(c, 0.12))])))
    rrect(x0 - 10, y, x1 + 10, y + 16, 6, paint((176, 112, 100)))
    rect(x0 - 10, y + 12, x1 + 10, y + 22, paint((126, 78, 96), 200))


def counter(x0, x1, top, T, c=(214, 140, 96)):
    c = mixc(c, (40, 30, 110), T["dim"] * 0.45)
    rrect(x0, top - 22, x1, top + 6, 10, paint(lite(c, 0.4)))
    rect(x0 + 4, top, x1 - 4, GROUND - 6, paint(shader=lin(0, top, 0, GROUND, [(0, c), (1, dark(c, 0.3))])))
    for x in range(int(x0) + 60, int(x1) - 30, 120):
        rrect(x, top + 26, x + 96, GROUND - 40, 10, paint(dark(c, 0.16), 120))
        oval(x + 48, top + 52, 6, 6, paint(lite(c, 0.6)))


def indoor(kind, T, t):
    wall_and_floor(kind, T, t)
    cam(1.0)
    r = random.Random({"kitchen": 1, "shop": 2, "office": 3, "classroom": 4, "home": 5}[kind])
    lights = T["dim"] > 0.2
    if kind == "shop":
        rrect(-700, 430, 1700, 480, 4, paint((255, 255, 255, 0)))
        for k in range(30):                                  # striped valance along the top
            x = -700 + k * 80
            poly([(x, 120), (x + 80, 120), (x + 80, 200), (x + 40, 240), (x, 200)], paint((240, 90, 110) if k % 2 else (255, 244, 230)))
        shelf(-500, 140, 700, T, r, 8)
        shelf(-500, 140, 420, T, r, 8)
        window(760, 380, 1060, 880, T, t, (232, 90, 150), False)
        shelf(1180, 1700, 700, T, r, 7)
        shelf(1180, 1700, 420, T, r, 7)
        counter(-120, 880, 1040, T, (216, 138, 96))
        for i in range(5):                                   # loaves and pastries on the counter
            bx = 80 + i * 150
            oval(bx, 1004, 52, 28, paint(shader=rad(bx - 14, 988, 70, [(0, (255, 214, 140)), (1, (206, 128, 70))])))
            for k in (-1, 0, 1):
                line(bx + k * 20 - 8, 992, bx + k * 20 + 6, 1012, (232, 170, 96), 4)
        rrect(640, 960, 790, 1020, 8, paint((90, 96, 150)))
        rrect(656, 940, 774, 968, 6, paint((190, 236, 220)))
    elif kind == "kitchen":
        for k in range(26):                                  # tiled backsplash
            for j in range(3):
                x, y = -400 + k * 90, 780 + j * 90
                rrect(x, y, x + 84, y + 84, 6, paint(lite((255, 244, 226), 0.0), 240 if (k + j) % 2 else 200))
        for x in (-300, 380, 1080):                          # wall cabinets
            rrect(x, 330, x + 300, 700, 16, paint(shader=lin(0, 330, 0, 700, [(0, (110, 190, 188)), (1, (70, 140, 160))])))
            rrect(x + 14, 344, x + 142, 686, 10, paint((140, 214, 206), 160))
            rrect(x + 158, 344, x + 286, 686, 10, paint((140, 214, 206), 160))
            oval(x + 128, 520, 7, 18, paint((255, 232, 150)))
            oval(x + 172, 520, 7, 18, paint((255, 232, 150)))
        window(430, 380, 700, 690, T, t, (240, 110, 120), False)
        counter(-480, 1700, 1010, T, (96, 174, 176))
        for x, c in ((-200, (255, 170, 80)), (60, (236, 98, 120)), (940, (150, 120, 240))):   # pots on the counter
            rrect(x, 900, x + 150, 1000, 12, paint(shader=lin(x, 0, x + 150, 0, [(0, lite(c, 0.2)), (1, dark(c, 0.2))])))
            rrect(x - 12, 888, x + 162, 908, 8, paint(dark(c, 0.15)))
        for k in range(5):                                   # hanging utensils
            line(1280 + k * 48, 230, 1280 + k * 48, 330 + k % 2 * 40, (255, 240, 220), 7)
            oval(1280 + k * 48, 350 + k % 2 * 40, 17, 22, paint(r.choice(BUILD)))
    elif kind == "office":
        window(-380, 330, 380, 880, T, t, None, True)
        window(900, 330, 1500, 880, T, t, None, True)
        rrect(440, 420, 840, 720, 12, paint((255, 255, 255)))
        for k in range(5):
            c = r.choice(BUILD)
            poly([(470, 640 - k * 40), (470 + 100 + k * 40, 600 - k * 40), (470 + 110 + k * 40, 612 - k * 40), (470, 654 - k * 40)], paint(c, 220))
        rrect(440, 420, 840, 440, 8, paint((250, 130, 120)))
        counter(-300, 560, 1090, T, (150, 110, 190))
        rrect(150, 910, 420, 1070, 10, paint((38, 44, 84)))
        rrect(162, 922, 408, 1058, 6, paint(shader=lin(0, 922, 0, 1058, [(0, (110, 230, 250)), (1, (140, 150, 250))])))
        rrect(268, 1070, 300, 1090, 4, paint((70, 76, 110)))
        for x in (940, 1140, 1340):                          # filing cabinets in colours
            c = r.choice(BUILD)
            rrect(x, 780, x + 160, GROUND - 6, 10, paint(shader=lin(x, 0, x + 160, 0, [(0, lite(c, 0.2)), (1, dark(c, 0.2))])))
            for j in range(3):
                rrect(x + 14, 800 + j * 130, x + 146, 900 + j * 130, 8, paint(dark(c, 0.14), 130))
                rect(x + 62, 840 + j * 130, x + 98, 850 + j * 130, paint((255, 240, 200)))
        oval(1500, 1130, 60, 60, paint((255, 160, 120)))      # plant
        for k in range(7):
            ang = -1.2 + k * 0.4
            poly([(1500, 1100), (1500 + 90 * math.sin(ang) - 14, 960 - 20 * abs(math.cos(ang))), (1500 + 90 * math.sin(ang) + 14, 960 - 20 * abs(math.cos(ang)))], paint((60, 190, 120) if k % 2 else (110, 220, 130)))
    elif kind == "classroom":
        rrect(-200, 400, 760, 860, 14, paint((236, 190, 120)))
        rrect(-184, 416, 744, 844, 10, paint(shader=lin(0, 416, 0, 844, [(0, (48, 130, 126)), (1, (30, 96, 110))])))
        for k in range(6):
            line(-120 + k * 100, 480 + (k % 3) * 70, -50 + k * 100, 500 + (k % 3) * 70, (255, 255, 255), 7, 170)
        for k in range(18):                                  # bunting of coloured flags
            x = -400 + k * 110
            poly([(x, 170 + math.sin(k * 0.6) * 10), (x + 100, 170 + math.sin((k + 1) * 0.6) * 10), (x + 50, 270)], paint(BUILD[k % len(BUILD)]))
        window(900, 360, 1260, 820, T, t, (240, 150, 100), False)
        for x in (-80, 300, 700):                            # desks
            c = (226, 160, 100)
            rrect(x, 1030, x + 280, 1070, 10, paint(lite(c, 0.2)))
            rect(x + 24, 1070, x + 38, GROUND - 4, paint(dark(c, 0.3)))
            rect(x + 242, 1070, x + 256, GROUND - 4, paint(dark(c, 0.3)))
        gx, gy = 1500, 1000                                  # a globe
        oval(gx, gy, 70, 70, paint(shader=rad(gx - 20, gy - 24, 100, [(0, (140, 220, 250)), (1, (50, 120, 210))])))
        for dx, dy, rr in ((-20, -10, 26), (22, 18, 20), (10, -34, 14)):
            oval(gx + dx, gy + dy, rr, rr * 0.7, paint((110, 214, 130), 230))
        rect(gx - 5, gy + 70, gx + 5, 1190, paint((150, 96, 90)))
    elif kind == "home":
        window(-300, 340, 20, 900, T, t, (240, 130, 150), False)
        for (x, y, w, h, c) in ((420, 360, 220, 300, (255, 214, 120)), (700, 440, 260, 200, (150, 200, 250)), (1020, 340, 200, 280, (230, 150, 230))):
            rrect(x - 10, y - 10, x + w + 10, y + h + 10, 8, paint((255, 248, 238)))
            rect(x, y, x + w, y + h, paint(shader=lin(x, y, x + w, y + h, [(0, c), (1, hue(c, 0.12))])))
            oval(x + w * 0.5, y + h * 0.58, w * 0.22, h * 0.2, paint(lite(c, 0.55), 220))
        rrect(780, 940, 1500, 1160, 50, paint(shader=lin(0, 940, 0, 1160, [(0, (255, 140, 120)), (1, (214, 84, 120))])))   # sofa
        rrect(800, 900, 1480, 1000, 46, paint((255, 168, 140)))
        oval(930, 1010, 70, 54, paint((130, 210, 200)))
        oval(1330, 1010, 70, 54, paint((255, 220, 110)))
        rect(1580, 520, 1590, 1130, paint((90, 70, 110)))    # standing lamp
        oval(1584, 500, 70, 54, paint(T["warm"], 255 if lights else 230))
        if lights:
            glow(1584, 520, 380, T["warm"], 120)
        oval(300, GROUND + 160, 560, 70, paint((120, 200, 200), 220))   # a rug
        oval(300, GROUND + 160, 430, 48, paint((255, 190, 120), 230))
        oval(300, GROUND + 160, 280, 28, paint((236, 110, 150), 230))
    if lights and kind != "home":                           # ceiling lamps glow at night
        for x in (100, 700, 1300):
            glow(x, 160, 300, T["warm"], 90)


def stage_world(name, t):
    """Draw the whole background of a scene in world coordinates under the current camera."""
    tm, st = parse_world(name)
    T = TIMES[tm]
    if st in INDOOR:
        indoor(st, T, t)
    else:
        sky(T, t)
        (park if st == "park" else street)(T, t)
    return T


def tint_world(T):
    """The light of the time of day over the BACKGROUND only (people are drawn after it, so they stay bright and readable)."""
    cv.resetMatrix()
    tr, tg, tb, ta = T["tint"]
    if ta:
        rect(0, 0, W, H, paint((tr, tg, tb), ta))


def finish_world(T, t):
    """A lighter version of the same light over the people too, a soft multi-colour light leak, rain."""
    cv.resetMatrix()
    tr, tg, tb, ta = T["tint"]
    if ta:
        rect(0, 0, W, H, paint((tr, tg, tb), int(ta * 0.35)))
    rect(0, 0, W, H, paint(shader=lin(0, 0, W, H, [(0, (80, 220, 255, 34)), (.5, (255, 90, 200, 20)), (1, (255, 170, 60, 34))]), mode=skia.BlendMode.kSoftLight))
    if T.get("rain"):
        rain(T, t)


def ground_shadow(x, y, s):
    """soft violet shadow under a character's feet (world coordinates)"""
    soft_shadow(x, y + 6 * s, 96 * s, 17 * s, (40, 18, 96), 120, 9 * s)
