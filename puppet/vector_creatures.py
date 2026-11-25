"""Vector-look creatures: the stars of the "why" videos (a cat, a dog, a cow, a chicken, the sun, the moon).
Same flat-vector style as vector_people.py (soft gradients, coloured shadows, big expressive eyes, no black outlines) and the same units:
the origin is the centre of the feet, up is negative, a sitting cat is about 360 units tall. They share the people's moods
(neutral sleepy happy angry scared sad shocked smug dizzy), eye states and a few actions (stand talk hop tremble flap cheer sleep ...)."""
import math

import skia

from . import vector as V
from .vector import dark, lite, mixc, oval, paint, poly, rad, lin, smooth, curve
from .vector_people import ball, blink_amount, limb, INKC

KINDS = ("cat", "dog", "cow", "chicken", "sun", "moon")
COATS = {"orange": (240, 152, 72), "ginger": (232, 128, 58), "grey": (156, 162, 178), "black": (74, 70, 92), "white": (248, 244, 240),
         "cream": (244, 226, 192), "brown": (156, 104, 70), "yellow": (252, 208, 72), "pink": (246, 164, 186), "red": (222, 72, 72),
         "blue": (96, 146, 224), "green": (98, 172, 112), "gold": (255, 198, 62), "tan": (214, 168, 118)}
DEFAULT_COAT = {"cat": "orange", "dog": "tan", "cow": "white", "chicken": "white", "sun": "gold", "moon": "cream"}
IRIS = {"cat": (110, 176, 96), "dog": (110, 70, 40), "cow": (96, 62, 38), "chicken": (60, 40, 30), "sun": (96, 62, 38), "moon": (70, 90, 140)}
PINK = (246, 150, 170)
EYE_WHITE = (255, 252, 248)


def _coat(color, kind):
    if isinstance(color, (list, tuple)) and len(color) == 3:
        return tuple(int(v) for v in color)
    return COATS.get(str(color).lower(), COATS[DEFAULT_COAT.get(kind, "orange")])


# ------------------------------------------------------------------ face parts
def _eye(ex, ey, r, st, look, blink, lidc, iris, side):
    cv = V.cv
    ink = paint(INKC, stroke=max(4.0, r * 0.2))
    if st == "happy":                                                     # a smiling arc: ^
        curve([(ex - r * 0.85, ey + r * 0.35), (ex, ey - r * 0.55), (ex + r * 0.85, ey + r * 0.35)], ink)
        return
    if st == "closed" or (blink > 0.55 and st in ("open", "wide", "half")):   # shut: a gentle downward curve
        curve([(ex - r * 0.85, ey - r * 0.05), (ex, ey + r * 0.4), (ex + r * 0.85, ey - r * 0.05)], ink)
        return
    rr = r * (1.18 if st == "wide" else 1.0)
    oval(ex, ey + 3, rr * 1.0, rr * 1.12, paint(dark(lidc, 0.35), 70, blur=3))             # a soft shade under the eye
    oval(ex, ey, rr * 0.98, rr * 1.1, paint(EYE_WHITE))
    ox, oy = look[0] * rr * 0.24, look[1] * rr * 0.22
    ir = rr * (0.52 if st == "wide" else 0.62)
    oval(ex + ox, ey + oy, ir, ir * 1.1, paint(shader=rad(ex + ox, ey + oy - ir * 0.3, ir * 1.6, [(0, lite(iris, 0.3)), (1, dark(iris, 0.25))])))
    if st == "spiral":
        pts = [(ex + ox + math.cos(a) * a * rr * 0.1, ey + oy + math.sin(a) * a * rr * 0.1) for a in [i * 0.4 for i in range(1, 17)]]
        curve(pts, paint(INKC, stroke=4))
    else:
        pr = ir * (0.55 if st == "wide" else 0.62)
        oval(ex + ox, ey + oy, pr, pr * 1.1, paint(INKC))
        oval(ex + ox - ir * 0.32, ey + oy - ir * 0.36, ir * 0.22, ir * 0.22, paint((255, 255, 255)))
    if st == "half":                                                      # heavy lids: bored, sleepy, smug
        oval(ex, ey - rr * 0.62, rr * 1.14, rr * 0.8, paint(lidc))
        V.line(ex - rr * 1.0, ey - rr * 0.18, ex + rr * 1.0, ey - rr * 0.18, INKC, max(3.5, rr * 0.16))


def _brows(ex_gap, ey, r, mood, lidc):
    col = dark(lidc, 0.55)
    w = max(5.0, r * 0.3)
    for side in (-1, 1):
        cx = side * ex_gap
        if mood == "angry":
            V.line(cx + side * r * 1.0, ey - r * 1.55, cx - side * r * 0.7, ey - r * 1.0, col, w)
        elif mood == "sad":
            V.line(cx + side * r * 1.0, ey - r * 1.0, cx - side * r * 0.7, ey - r * 1.55, col, w)
        elif mood in ("shocked", "scared"):
            curve([(cx - r * 0.9, ey - r * 1.55), (cx, ey - r * 1.95), (cx + r * 0.9, ey - r * 1.55)], paint(col, stroke=w))
        elif mood == "smug" and side > 0:
            V.line(cx - r * 0.8, ey - r * 1.7, cx + r * 0.9, ey - r * 1.95, col, w)


def _mouth(mx, my, w, mood, talk, kind_dark):
    cv = V.cv
    lw = max(4.0, w * 0.09)
    if talk > 0.08 or mood in ("shocked",):
        h = w * (0.12 + 0.5 * (talk if talk > 0.08 else 0.7))
        oval(mx, my + h * 0.3, w * 0.32, h * 0.62 + 4, paint((88, 36, 60)))
        oval(mx, my + h * 0.55, w * 0.2, h * 0.28 + 2, paint((236, 110, 130)))
        return
    if mood == "happy":
        smooth([(mx - w * 0.5, my - 4), (mx - w * 0.3, my + w * 0.28), (mx + w * 0.3, my + w * 0.28), (mx + w * 0.5, my - 4), (mx, my + 6)], paint((88, 36, 60)))
        return
    if mood in ("sad", "scared"):
        curve([(mx - w * 0.38, my + w * 0.16), (mx, my - w * 0.06), (mx + w * 0.38, my + w * 0.16)], paint(INKC, stroke=lw))
    elif mood == "angry":
        curve([(mx - w * 0.4, my + w * 0.1), (mx, my - w * 0.02), (mx + w * 0.4, my + w * 0.1)], paint(INKC, stroke=lw))
    elif mood == "smug":
        curve([(mx - w * 0.34, my + 4), (mx + w * 0.1, my + w * 0.12), (mx + w * 0.42, my - w * 0.1)], paint(INKC, stroke=lw))
    else:                                                                  # the little "w" of a relaxed mouth
        curve([(mx - w * 0.36, my), (mx - w * 0.18, my + w * 0.13), (mx, my)], paint(INKC, stroke=lw))
        curve([(mx, my), (mx + w * 0.18, my + w * 0.13), (mx + w * 0.36, my)], paint(INKC, stroke=lw))


def _face(cx, cy, gap, r, mood, eye, look, talk, t, seed, lidc, iris, mouth_dy, mouth_w, tear=0.0):
    blink = blink_amount(t + seed * 0.37)
    for side in (-1, 1):
        _eye(cx + side * gap, cy, r, eye, look, blink, lidc, iris, side)
    _brows_at = cy
    V.cv.save()
    V.cv.translate(cx, 0)
    _brows(gap, _brows_at, r, mood, lidc)
    V.cv.restore()
    _mouth(cx, cy + mouth_dy, mouth_w, mood, talk, dark(lidc, 0.5))
    if tear > 0.05 or mood == "sad":
        for side in (-1, 1):
            oval(cx + side * (gap + r * 0.5), cy + r * 1.5 + (t * 20 % 40) * 0.5, r * 0.22, r * 0.34, paint((150, 200, 255), 200))


def _cheeks(cx, cy, gap, r, a=90):
    for side in (-1, 1):
        oval(cx + side * (gap + r * 0.9), cy + r * 0.9, r * 0.8, r * 0.5, paint((250, 130, 150), a, blur=r * 0.35))


# ------------------------------------------------------------------ the creatures
def _ears_pointy(c, hx, hy, spread, h, tilt):
    for side in (-1, 1):
        o = [(side * (spread + 38), hy - 62), (side * (spread - 4) + tilt * side, hy - 62 - h), (side * (spread - 62), hy - 82)]
        smooth(o, paint(shader=lin(side * spread - 40, hy - 150, side * spread + 40, hy - 70, [(0, lite(c, 0.12)), (1, dark(c, 0.22))])))
        smooth([(side * (spread + 20), hy - 70), (side * (spread - 2) + tilt * side, hy - 62 - h * 0.7), (side * (spread - 40), hy - 84)], paint(PINK))


def _cat(c, st):
    t, mood = st["t"], st["mood"]
    wag = math.sin(t * (7 if mood == "happy" else 2.2) + st["seed"]) * (34 if mood == "happy" else 14)
    V.curve([(98, -50), (190, -64 + wag * 0.2), (214, -150), (176 + wag, -236)], paint(dark(c, 0.18), stroke=46))
    V.curve([(98, -50), (190, -64 + wag * 0.2), (214, -150), (176 + wag, -236)], paint(c, stroke=36))
    ball(0, -108, 122, 112, c, 1)
    oval(0, -84, 72, 74, paint(lite(c, 0.5)))
    for side in (-1, 1):
        ball(side * 92, -34, 46, 34, c, 1)
    paw = st["paw"]
    for side in (-1, 1):
        raised = paw if (side == st["f"] and st["action"] in ("point", "reach", "offer", "wave", "cheer", "beckon")) or st["action"] == "cheer" else 0.0
        top = (side * 50, -150)
        bot = (side * 50 + side * 70 * raised, -24 - 150 * raised)
        limb(top, bot, 58, c, 1)
        ball(bot[0], bot[1] + 4, 38, 24, lite(c, 0.12), 1)
    hy = st["head_y"]
    _ears_pointy(c, 0, hy, 92, 92, 10)
    ball(0, hy, 136, 110, c, 1)
    if st["stripes"]:
        for k in (-1, 0, 1):
            curve([(k * 30, hy - 104), (k * 30 + k * 4, hy - 78)], paint(dark(c, 0.3), stroke=10))
    oval(0, hy + 24, 54, 38, paint(lite(c, 0.55)))
    _cheeks(0, hy - 14, 50, 28)
    _face(0, hy - 14, 50, 28, mood, st["eye"], st["look"], st["talk"], t, st["seed"], c, IRIS["cat"], 64, 72, st["tear"])
    smooth([(-11, hy + 14), (11, hy + 14), (0, hy + 28)], paint(PINK))
    for side in (-1, 1):
        for k, dy in enumerate((-10, 2, 14)):
            V.line(side * 56, hy + 34 + k * 3, side * (118 + k * 5), hy + 34 + dy + k * 6, (255, 250, 246), 3, 200)


def _dog(c, st):
    t, mood = st["t"], st["mood"]
    wag = math.sin(t * (14 if mood == "happy" else 3) + st["seed"]) * (26 if mood == "happy" else 8)
    V.curve([(96, -70), (150, -110 + wag * 0.3), (176 + wag, -170)], paint(dark(c, 0.2), stroke=34))
    V.curve([(96, -70), (150, -110 + wag * 0.3), (176 + wag, -170)], paint(c, stroke=26))
    ball(0, -108, 126, 112, c, 1)
    oval(0, -84, 72, 74, paint(lite(c, 0.5)))
    for side in (-1, 1):
        ball(side * 92, -34, 46, 34, c, 1)
        raised = st["paw"] if (side == st["f"] and st["action"] in ("point", "reach", "offer", "wave", "cheer", "beckon")) or st["action"] == "cheer" else 0.0
        top = (side * 52, -150)
        bot = (side * 52 + side * 70 * raised, -24 - 150 * raised)
        limb(top, bot, 60, c, 1)
        ball(bot[0], bot[1] + 4, 40, 24, lite(c, 0.12), 1)
    hy = st["head_y"]
    ball(0, hy, 128, 108, c, 1)
    ear = dark(c, 0.34)
    flop = 8 if mood in ("sad", "scared") else (-12 if mood == "happy" else 0)
    for side in (-1, 1):                                                  # floppy ears
        smooth([(side * 96, hy - 84), (side * 156, hy - 46 + flop), (side * 150, hy + 52 + flop), (side * 104, hy + 40), (side * 90, hy - 20)],
               paint(shader=lin(side * 90, hy - 80, side * 160, hy + 40, [(0, lite(ear, 0.1)), (1, dark(ear, 0.2))])))
    if st["patch"]:
        oval(-st["f"] * 52, hy - 22, 40, 46, paint(dark(c, 0.3), 190))
    oval(0, hy + 30, 66, 48, paint(lite(c, 0.6)))
    _cheeks(0, hy - 16, 50, 27, 70)
    _face(0, hy - 16, 50, 27, mood, st["eye"], st["look"], st["talk"], t, st["seed"], c, IRIS["dog"], 76, 76, st["tear"])
    oval(0, hy + 14, 25, 17, paint(INKC))
    oval(-7, hy + 9, 7, 4, paint((255, 255, 255), 190))
    if mood == "happy" and st["talk"] < 0.08:
        oval(8, hy + 112 - 56, 17, 26, paint(PINK))


def _cow(c, st):
    t, mood = st["t"], st["mood"]
    spot = (62, 58, 74)
    ball(0, -108, 134, 114, c, 1)
    for (sx, sy, rx, ry) in ((-70, -140, 36, 28), (62, -96, 40, 32), (-24, -52, 28, 22)):
        oval(sx, sy, rx, ry, paint(spot))
    for side in (-1, 1):
        ball(side * 94, -34, 48, 34, c, 1)
        raised = st["paw"] if (side == st["f"] and st["action"] in ("point", "reach", "offer", "wave", "cheer", "beckon")) or st["action"] == "cheer" else 0.0
        top = (side * 54, -150)
        bot = (side * 54 + side * 70 * raised, -24 - 150 * raised)
        limb(top, bot, 62, c, 1)
        ball(bot[0], bot[1] + 4, 42, 24, (58, 54, 70), 1)
    V.curve([(104, -70), (166, -100), (160, -30)], paint(c, stroke=14))
    ball(158, -22, 16, 22, spot, 1)
    hy = st["head_y"]
    for side in (-1, 1):
        smooth([(side * 100, hy - 60), (side * 130, hy - 108), (side * 112, hy - 130), (side * 84, hy - 96)], paint((244, 236, 214)))   # horns
        smooth([(side * 110, hy - 40), (side * 190, hy - 70), (side * 188, hy - 10), (side * 116, hy + 6)], paint(shader=lin(side * 110, hy - 70, side * 190, hy, [(0, lite(c, 0.05)), (1, dark(c, 0.25))])))
    ball(0, hy, 132, 110, c, 1)
    oval(st["f"] * 70, hy - 54, 40, 34, paint(spot))
    oval(0, hy + 36, 74, 52, paint((250, 178, 192)))
    for side in (-1, 1):
        oval(side * 26, hy + 30, 10, 14, paint(dark(PINK, 0.4)))
    _cheeks(0, hy - 14, 52, 27, 60)
    _face(0, hy - 14, 52, 27, mood, st["eye"], st["look"], st["talk"], t, st["seed"], c, IRIS["cow"], 92, 70, st["tear"])


def _chicken(c, st):
    t, mood = st["t"], st["mood"]
    flap = st["flap"]
    comb, beak, leg = (226, 60, 66), (250, 176, 60), (246, 168, 64)
    for k, (a, dx) in enumerate(((-0.5, 0), (0.0, 22), (0.5, 44))):                       # tail feathers behind the body
        V.cv.save()
        V.cv.translate(96, -150)
        V.cv.rotate(math.degrees(a) + 18)
        ball(dx * 0.2, -62, 30, 74, dark(c, 0.12 + 0.05 * k), 1)
        V.cv.restore()
    for side in (-1, 1):
        limb((side * 34, -34), (side * 34, 0), 14, leg, 1)
        for toe in (-1, 0, 1):
            V.line(side * 34, 0, side * 34 + toe * 24, 8, leg, 9)
    ball(0, -122, 128, 116, c, 1)
    oval(0, -92, 78, 72, paint(lite(c, 0.45)))
    for side in (-1, 1):                                                  # wings
        ang = (side * (-0.2 - 0.9 * flap)) * 57.3
        V.cv.save()
        V.cv.translate(side * 112, -150)
        V.cv.rotate(ang + side * 10)
        ball(side * 14, 46, 38, 84, mixc(c, dark(c, 0.2), 0.5), 1)
        V.cv.restore()
    hy = st["head_y"] + 36
    for k, (cx, cy, rr) in enumerate(((0, -66, 28), (-27, -54, 22), (27, -54, 22))):    # comb
        ball(cx, hy + cy, rr, rr * 1.1, comb, 1)
    ball(0, hy, 80, 74, c, 1)
    oval(0, hy + 58, 14, 22, paint(comb))                                  # wattle
    smooth([(-20, hy + 6), (20, hy + 6), (0, hy + 36)], paint(beak))
    _face(0, hy - 14, 34, 19, mood, st["eye"], st["look"], 0.0, t, st["seed"], c, IRIS["chicken"], 999, 1)
    if st["talk"] > 0.08:
        smooth([(-20, hy + 22), (20, hy + 22), (0, hy + 22 + 14 + 22 * st["talk"])], paint(dark(beak, 0.2)))
    _cheeks(0, hy - 14, 34, 19, 80)


def _orb(c, st, moon=False):
    t, mood = st["t"], st["mood"]
    cy = -300
    R = 170
    glow = (150, 190, 255) if moon else (255, 214, 110)
    V.glow(0, cy, R * 2.1, glow, 170)
    if not moon:
        for k in range(14):                                                # rays
            a = k * (2 * math.pi / 14) + t * 0.25
            for w in (1,):
                p1 = (math.cos(a - 0.1) * (R + 6), cy + math.sin(a - 0.1) * (R + 6))
                p2 = (math.cos(a + 0.1) * (R + 6), cy + math.sin(a + 0.1) * (R + 6))
                tip = (math.cos(a) * (R + 56 + 12 * math.sin(t * 3 + k)), cy + math.sin(a) * (R + 56 + 12 * math.sin(t * 3 + k)))
                smooth([p1, tip, p2], paint(mixc(c, (255, 140, 60), 0.4)))
    ball(0, cy, R, R, c, 1)
    if moon:
        for (cx_, cy_, rr) in ((-70, cy - 56, 28), (64, cy + 24, 36), (-30, cy + 84, 20), (74, cy - 70, 16)):
            oval(cx_, cy_, rr, rr * 0.9, paint(dark(c, 0.14), 150))
    _cheeks(0, cy, 64, 32, 110)
    _face(0, cy - 10, 64, 32, mood, st["eye"], st["look"], st["talk"], t, st["seed"], c, IRIS["sun"], 92, 96, st["tear"])


# ------------------------------------------------------------------ entry point
def creature(x, y, s=1.0, f=1, t=0.0, kind="cat", color=None, mood="neutral", eye="open", brow=(0, 0), look=(0, 0), talk=0.0,
             action="stand", bounce=0.0, seed=0, tear=0.0, stripes=False, patch=False, **_):
    """Draw one creature standing (or, for the sun and moon, floating) at (x, y)."""
    cv = V.cv
    kind = kind if kind in KINDS else "cat"
    c = _coat(color, kind)
    sleeping = action == "sleep" or mood == "sleepy"
    if sleeping and eye in ("open", "half"):
        eye = "closed"
    dy = 0.0                                              # (a hop is done by the compiler's y channel)
    dx = math.sin(t * 44) * 5.0 if (action in ("tremble", "cower") or mood == "scared") else 0.0
    breath = 0.014 * math.sin(t * 1.9 + seed)
    bob = bounce if isinstance(bounce, (int, float)) else 0.0
    flap = 0.5 + 0.5 * math.sin(t * 15) if action in ("flap", "cheer", "hop") else (0.15 if mood in ("scared", "shocked", "happy") else 0.0)
    paw = 0.75 + 0.25 * math.sin(t * 9) if action in ("wave", "cheer", "beckon") else (0.7 if action in ("point", "reach", "offer") else 0.0)
    head_y = -262 + (30 if sleeping else 0) + (10 if mood == "sad" else 0) + (math.sin(t * 2.0 + seed) * 3 if sleeping else 0)
    st = dict(t=t, mood=mood, eye=eye, look=tuple(look), talk=float(talk or 0.0), seed=seed, tear=tear, action=action, f=f, paw=paw, flap=flap,
              head_y=head_y, stripes=stripes, patch=patch)
    if kind in ("sun", "moon"):
        V.soft_shadow(x, y + 6 * s, 90 * s, 14 * s, (40, 18, 96), 70, 10 * s)
    else:
        V.ground_shadow(x, y, s * 1.1)
    cv.save()
    cv.translate(x + dx * s, y + (dy + bob) * s)
    cv.scale(s * (1 - breath), s * (1 + breath))
    if kind == "cat":
        _cat(c, st)
    elif kind == "dog":
        _dog(c, st)
    elif kind == "cow":
        _cow(c, st)
    elif kind == "chicken":
        _chicken(c, st)
    else:
        _orb(c, st, moon=(kind == "moon"))
    cv.restore()
