"""The "blob" people: a round cream head with dot eyes and big brows, a hoodie body, thick outlined tube limbs.
Simple enough to read at a glance, expressive enough to act, and always the same character, drawn over painted backdrops.
Same units as vector_people.py: origin = centre of the feet, up is negative, an adult is about 400 units tall."""
import math
import zlib

from . import vector as V
from .vector import dark, lite, oval, paint, curve, rad
from .vector_people import blink_amount

LINE = (30, 26, 38)
HEAD = (246, 240, 226)
OUTW = 7.0
HOODIES = [(98, 92, 72), (72, 96, 150), (156, 74, 74), (64, 66, 80), (204, 150, 64), (84, 132, 104), (130, 84, 150)]


def _col(seed_text):
    return HOODIES[zlib.crc32(str(seed_text).encode()) % len(HOODIES)]


def _tube(p0, p1, w, c):
    V.cv.drawLine(p0[0], p0[1], p1[0], p1[1], paint(LINE, stroke=w + OUTW))
    V.cv.drawLine(p0[0], p0[1], p1[0], p1[1], paint(c, stroke=w))


def _ik(S, T, l1, l2, bend):
    dx, dy = T[0] - S[0], T[1] - S[1]
    d = max(1e-3, min(math.hypot(dx, dy), l1 + l2 - 1.0))
    a = math.atan2(dy, dx)
    k = math.acos(max(-1.0, min(1.0, (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d))))
    e = (S[0] + l1 * math.cos(a + bend * k), S[1] + l1 * math.sin(a + bend * k))
    return e, (S[0] + d * math.cos(a), S[1] + d * math.sin(a))


def _hands(action, t, talk, f):
    """hand targets relative to the feet, for (left, right) of the screen"""
    sw = math.sin(t * 1.7) * 6
    L, R = (-82, -150 + sw), (82, -150 - sw)
    if action == "talk" or talk > 0.2:
        R = (118 + 18 * math.sin(t * 5.0), -230 + 26 * math.sin(t * 3.6))
    if action == "point":
        R = (190, -262 + 6 * math.sin(t * 2))
    elif action == "shrug":
        L, R = (-135, -250 + 8 * math.sin(t * 2)), (135, -250 + 8 * math.sin(t * 2))
    elif action in ("cheer", "laugh_up"):
        L, R = (-125, -400 + 14 * math.sin(t * 6)), (125, -400 - 14 * math.sin(t * 6))
    elif action == "facepalm":
        R = (14, -318)
    elif action == "think":
        R = (22, -285 + 4 * math.sin(t * 1.4))
    elif action == "laugh":
        L, R = (-42, -178 + 8 * math.sin(t * 9)), (42, -178 - 8 * math.sin(t * 9))
    elif action in ("offer", "hold", "place", "reach"):
        L, R = (-70, -200), (130, -205 + 6 * math.sin(t * 2))
    elif action in ("clasp", "hugself", "wrap"):
        L, R = (-26, -178), (26, -184)
    elif action == "wipe":
        R = (40, -318 + 6 * math.sin(t * 7))
    elif action == "cower":
        L, R = (-52, -330), (52, -330)
    elif action == "wave":
        R = (118, -385 + 6 * math.sin(t * 2)); R = (R[0] + 22 * math.sin(t * 7), R[1])
    elif action == "beckon":
        R = (128, -230 + 20 * math.sin(t * 6))
    elif action == "tremble":
        L, R = (L[0] + 4 * math.sin(t * 40), L[1]), (R[0] - 4 * math.sin(t * 40), R[1])
    return L, R


def _eyes(ex, ey, mood, eye, look, blink, t):
    cv = V.cv
    st = eye if eye != "open" else ("closed" if mood == "sleepy" else "open")
    if mood == "happy" and st == "open":
        st = "happy"
    for side in (-1, 1):
        x = ex * side
        if st == "closed" or blink > 0.55:
            curve([(x - 13, ey), (x, ey + 7), (x + 13, ey)], paint(LINE, stroke=5.0))
        elif st == "happy":
            curve([(x - 13, ey + 5), (x, ey - 7), (x + 13, ey + 5)], paint(LINE, stroke=5.5))
        else:
            r = 11.5 if mood in ("shocked", "scared") else 8.5
            ry = r * (0.55 if mood in ("smug", "sleepy") else 1.08)
            oval(x, ey, r + 4, ry + 5 if mood not in ("smug",) else ry + 3, paint((255, 255, 255)))
            oval(x + look[0] * 3.5, ey + look[1] * 3, r * 0.55, ry * 0.62, paint(LINE))
    if mood == "angry":
        for side in (-1, 1):
            cv.drawLine(side * (ex + 20), ey - 22, side * (ex - 14), ey - 11, paint(LINE, stroke=7))
    elif mood == "sad":
        for side in (-1, 1):
            cv.drawLine(side * (ex + 18), ey - 12, side * (ex - 14), ey - 24, paint(LINE, stroke=6))
    elif mood in ("shocked", "scared"):
        for side in (-1, 1):
            curve([(side * ex - 15, ey - 26), (side * ex, ey - 33), (side * ex + 15, ey - 26)], paint(LINE, stroke=5))
    elif mood == "smug":
        cv.drawLine(ex - 16, ey - 20, ex + 14, ey - 25, paint(LINE, stroke=6))
        cv.drawLine(-ex - 14, ey - 14, -ex + 16, ey - 14, paint(LINE, stroke=6))
    else:
        for side in (-1, 1):
            curve([(side * ex - 14, ey - 20), (side * ex, ey - 23), (side * ex + 14, ey - 20)], paint(LINE, stroke=4.5))


def _mouth(my, mood, talk, t):
    if talk > 0.08 or mood == "shocked":
        h = 8 + 20 * (talk if talk > 0.08 else 0.8) * (0.6 + 0.4 * abs(math.sin(t * 9)))
        oval(0, my + h * 0.3, 15, h * 0.7 + 3, paint(LINE))
        oval(0, my + h * 0.55, 9, h * 0.3 + 1, paint((220, 100, 110)))
    elif mood == "happy":
        curve([(-18, my - 4), (0, my + 16), (18, my - 4)], paint(LINE, stroke=5.5))
    elif mood in ("sad", "scared"):
        curve([(-14, my + 8), (0, my - 2), (14, my + 8)], paint(LINE, stroke=5))
    elif mood == "smug":
        curve([(-14, my + 2), (4, my + 8), (20, my - 6)], paint(LINE, stroke=5))
    elif mood == "angry":
        curve([(-14, my + 6), (0, my), (14, my + 6)], paint(LINE, stroke=5))
    elif mood != "sleepy":
        curve([(-12, my + 2), (0, my + 5), (12, my + 2)], paint(LINE, stroke=4.5))
    else:
        oval(0, my + 3, 6, 5, paint(LINE))


def _hair(style, col, hy):
    cv = V.cv
    if not style or style == "bald":
        return
    dk = paint(dark(col, 0.1))
    if style in ("long", "braids", "ponytail"):
        for sd in (-1, 1):
            cv.drawRoundRect(skia_rect(sd * 70 - 14, hy - 20, sd * 70 + 14, hy + 90), 14, 14, dk)
    if style == "afro":
        oval(0, hy - 38, 92, 70, dk)
    elif style == "curly":
        for i in range(-3, 4):
            oval(i * 22, hy - 64 + abs(i) * 6, 20, 20, dk)
    elif style == "spiky":
        for i in range(-3, 4):
            V.poly([(i * 20 - 14, hy - 56), (i * 20, hy - 108 + abs(i) * 8), (i * 20 + 14, hy - 56)], dk)
    elif style == "bun":
        oval(0, hy - 96, 26, 26, dk)
    cv.drawArc(skia_rect(-76, hy - 78, 76, hy + 40), 190, 160, True, dk)


def blob(x, y, s, f, t, c):
    """c is the person's description from vector_people.person (outfit spec, skin, hair, mood, action ...)"""
    cv = V.cv
    spec, dz = c["spec"], c.get("design") or {}
    action, mood, talk, seed = c["action"], c["mood"], c["talk"], c["seed"]
    V.ground_shadow(x, y, s)
    cv.save()
    cv.translate(x, y)
    k = s * 1.45                                            # the camera is close: the character fills the frame
    cv.scale(k, k)
    body = tuple(spec.get("top") or _col(c["role"]))
    sleeve = tuple(spec.get("coat") or body) if not spec.get("dress") else body
    pants = tuple(spec.get("bottom") or dark(body, 0.5))
    shoes = tuple(spec.get("shoes") or (244, 244, 244))
    head_c = HEAD if (not dz.get("skin_rgb") and c.get("skin") in ("fair", "light", None)) else lite(tuple(c["skin_c"]), 0.1)
    build = {"slim": 0.88, "average": 1.0, "broad": 1.16, "round": 1.28}.get(dz.get("build"), 1.0)
    bw = 62 * build
    top, bot = -280, -112
    sway = math.sin(t * 1.5 + seed) * 3
    if action == "tremble":
        cv.translate(3 * math.sin(t * 38), 0)
    if spec.get("cape"):
        cv.drawRoundRect(skia_rect(-bw - 22, top + 10, bw + 22, bot + 90), 30, 30, paint(LINE))
        cv.drawRoundRect(skia_rect(-bw - 17, top + 15, bw + 17, bot + 85), 26, 26, paint(tuple(spec["cape"]) if isinstance(spec["cape"], (tuple, list)) else (190, 50, 60)))
    # legs (a dress hides them under a skirt)
    for sd in (-1, 1):
        _tube((sd * 26, -125), (sd * 32, -8), 36, pants if not spec.get("dress") else head_c)
        oval(sd * 38, -5, 34, 15, paint(LINE))
        oval(sd * 38, -9, 30, 11, paint(shoes))
    # torso
    cv.drawRoundRect(skia_rect(-bw, top, bw, bot), 40, 40, paint(LINE))
    cv.drawRoundRect(skia_rect(-bw + OUTW / 2, top + OUTW / 2, bw - OUTW / 2, bot - OUTW / 2), 36, 36,
                     paint(shader=rad(-20, top + 30, 190, [(0, lite(body, 0.25)), (1, dark(body, 0.2))])))
    if spec.get("dress"):
        V.poly([(-bw + 6, bot - 40), (bw - 6, bot - 40), (bw + 34, bot + 70), (-bw - 34, bot + 70)], paint(LINE))
        V.poly([(-bw + 10, bot - 36), (bw - 10, bot - 36), (bw + 28, bot + 64), (-bw - 28, bot + 64)], paint(sleeve))
    if spec.get("coat"):
        cc = tuple(spec["coat"])
        cv.drawRoundRect(skia_rect(-bw - 4, top + 6, bw + 4, bot + 56), 30, 30, paint(LINE))
        cv.drawRoundRect(skia_rect(-bw, top + 10, bw, bot + 52), 26, 26, paint(shader=rad(-20, top + 30, 220, [(0, lite(cc, 0.22)), (1, dark(cc, 0.2))])))
        cv.drawLine(0, top + 18, 0, bot + 50, paint(dark(cc, 0.5), stroke=4))
        V.poly([(-26, top + 6), (0, top + 56), (26, top + 6)], paint(body))
    if spec.get("apron"):
        ac = tuple(spec["apron"])
        cv.drawRoundRect(skia_rect(-bw + 14, top + 56, bw - 14, bot + 70), 22, 22, paint(LINE))
        cv.drawRoundRect(skia_rect(-bw + 18, top + 60, bw - 18, bot + 66), 19, 19, paint(ac))
    if spec.get("vest"):
        vc = tuple(spec["vest"])
        for sd in (-1, 1):
            V.poly([(sd * 8, top + 8), (sd * (bw - 8), top + 8), (sd * (bw - 6), bot - 8), (sd * 8, bot - 8)], paint(vc))
    if spec.get("bib"):
        bc = tuple(spec["bib"])
        cv.drawRoundRect(skia_rect(-bw + 20, top + 62, bw - 20, bot), 14, 14, paint(LINE))
        cv.drawRoundRect(skia_rect(-bw + 25, top + 67, bw - 25, bot - 5), 11, 11, paint(bc))
        for sd in (-1, 1):
            cv.drawLine(sd * (bw - 30), top + 66, sd * 30, top + 6, paint(bc, stroke=14))
    if spec.get("belt"):
        cv.drawRect(skia_rect(-bw + 4, bot - 26, bw - 4, bot - 8), paint(tuple(spec["belt"]) if isinstance(spec["belt"], (tuple, list)) else (60, 40, 30)))
    # arms
    L, R = _hands(action, t + seed, talk, f)
    for sd, H_ in ((-1, L), (1, R)):
        S = (sd * (bw - 2), top + 26)
        e, h = _ik(S, H_, 84, 84, -sd * 0.9)
        _tube(S, e, 30, sleeve)
        _tube(e, h, 28, sleeve)
        oval(h[0], h[1], 21, 21, paint(LINE))
        oval(h[0], h[1], 16.5, 16.5, paint(head_c))
    if spec.get("pack"):
        for sd in (-1, 1):
            cv.drawLine(sd * 34, top + 8, sd * 40, bot - 20, paint((70, 60, 50), stroke=12))
    # head
    hy = top - 58 + sway * 0.4
    if spec.get("scarf"):
        cv.drawRoundRect(skia_rect(-bw + 6, top - 12, bw - 6, top + 26), 16, 16, paint(tuple(spec["scarf"]) if isinstance(spec["scarf"], (tuple, list)) else (200, 60, 70)))
    oval(0, hy, 80, 76, paint(LINE))
    oval(0, hy, 74, 70, paint(shader=rad(-18, hy - 22, 130, [(0, lite(head_c, 0.5)), (1, dark(head_c, 0.12))])))
    _hair(dz.get("hair_style"), tuple(c.get("hair_c") or (60, 40, 30)), hy)
    from . import vector_people as VP
    if spec.get("hat"):
        VP._hat(spec["hat"], hy - 72, 72, spec, 1)
    _eyes(25, hy + 2, mood, c["eye"], c["look"], blink_amount(t + seed), t)
    _mouth(hy + 42, mood, talk, t)
    acc = tuple(dz.get("accessories") or ())
    if "glasses" in acc or spec.get("glasses"):
        for sd in (-1, 1):
            oval(sd * 25, hy + 2, 21, 20, paint((255, 255, 255), 40))
            cv.drawCircle(sd * 25, hy + 2, 21, paint(LINE, stroke=4.5))
        cv.drawLine(-4, hy + 2, 4, hy + 2, paint(LINE, stroke=4))
    if "sunglasses" in acc or spec.get("sunglasses"):
        for sd in (-1, 1):
            oval(sd * 25, hy + 2, 24, 17, paint((24, 24, 34)))
        cv.drawLine(-2, hy, 2, hy, paint((24, 24, 34), stroke=5))
    if "mustache" in acc:
        V.poly([(-30, hy + 28), (0, hy + 22), (30, hy + 28), (18, hy + 36), (0, hy + 30), (-18, hy + 36)], paint(dark(tuple(c.get("hair_c") or (60, 40, 30)), 0.1)))
    if "beard" in acc:
        V.poly([(-52, hy + 20), (52, hy + 20), (46, hy + 72), (0, hy + 96), (-46, hy + 72)], paint(dark(tuple(c.get("hair_c") or (60, 40, 30)), 0.1)))
        _mouth(hy + 46, mood, talk, t)
    if spec.get("tie"):
        V.poly([(-9, top + 10), (9, top + 10), (14, top + 70), (0, top + 92), (-14, top + 70)], paint(tuple(spec["tie"]) if isinstance(spec["tie"], (tuple, list)) else (200, 60, 70)))
    if spec.get("bowtie"):
        col = tuple(spec["bowtie"]) if isinstance(spec["bowtie"], (tuple, list)) else (200, 60, 70)
        V.poly([(0, top + 6), (-26, top - 6), (-26, top + 20)], paint(col))
        V.poly([(0, top + 6), (26, top - 6), (26, top + 20)], paint(col))
    if spec.get("badge"):
        oval(36, top + 40, 11, 11, paint((250, 206, 70)))
    if c.get("tear"):
        oval(-34, hy + 22 + 40 * (t % 1), 5, 8, paint((120, 190, 255)))
    cv.restore()


def skia_rect(l, t, r, b):
    import skia
    return skia.Rect.MakeLTRB(l, t, r, b)
