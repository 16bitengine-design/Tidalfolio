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


def blob(x, y, s=1.0, f=1, t=0.0, role="stranger", extras=(), talk=0.0, eye="open", brow=(0, 0), look=(0, 0), action="stand", mood="neutral",
         bounce=0.0, seed=0, tear=0.0, design=None, age="adult", **_):
    cv = V.cv
    V.ground_shadow(x, y, s)
    cv.save()
    cv.translate(x, y)
    k = s * 1.45 * (0.74 if age == "child" else 1.0)           # the camera is close, like the reference: the character fills the frame
    cv.scale(k, k)
    body = (design or {}).get("shirt_rgb") or _col(role)
    pants = dark(body, 0.55)
    sway = math.sin(t * 1.5 + seed) * 3
    if action == "tremble":
        cv.translate(3 * math.sin(t * 38), 0)
    crouch = 55 if action == "cower" else 0
    cv.translate(0, crouch * 0.0)
    # legs
    for sd in (-1, 1):
        _tube((sd * 26, -125 + crouch), (sd * 32, -8), 36, pants)
        oval(sd * 38, -5, 34, 15, paint(LINE))
        oval(sd * 38, -9, 30, 11, paint((244, 244, 244)))
    # torso: a rounded hoodie
    top, bot = -280 + crouch, -112
    p = paint(body)
    cv.drawRoundRect(skia_rect(-62, top, (-62) + (124), (top) + (bot - top)), 40, 40, paint(LINE))
    cv.drawRoundRect(skia_rect(-62 + OUTW / 2, top + OUTW / 2, (-62 + OUTW / 2) + (124 - OUTW), (top + OUTW / 2) + (bot - top - OUTW)), 36, 36, paint(shader=rad(-20, top + 30, 190, [(0, lite(body, 0.25)), (1, dark(body, 0.2))])))
    cv.drawRoundRect(skia_rect(-30, bot - 62, (-30) + (60), (bot - 62) + (34)), 12, 12, paint(dark(body, 0.18)))             # the hoodie pocket
    # arms
    L, R = _hands(action, t + seed, talk, f)
    for sd, H_ in ((-1, L), (1, R)):
        S = (sd * 60, top + 26)
        e, h = _ik(S, H_, 84, 84, -sd * 0.9)
        _tube(S, e, 30, body)
        _tube(e, h, 28, body)
        oval(h[0], h[1], 21, 21, paint(LINE))
        oval(h[0], h[1], 16.5, 16.5, paint(HEAD))
    # head
    hy = top - 58 + sway * 0.4
    oval(0, hy, 80, 76, paint(LINE))
    oval(0, hy, 74, 70, paint(shader=rad(-18, hy - 22, 130, [(0, (255, 252, 244)), (1, dark(HEAD, 0.1))])))
    if "cap" in tuple(extras or ()) or role in ("thief", "robber", "delivery", "runner"):
        cv.drawArc(skia_rect(-76, hy - 78, 76, hy + 56), 180, 180, True, paint(LINE))
        cv.drawArc(skia_rect(-70, hy - 72, 70, hy + 50), 180, 180, True, paint(dark(body, 0.35)))
        cv.drawRoundRect(skia_rect(-12, hy - 12, (-12) + (108), (hy - 12) + (20)), 10, 10, paint(LINE))
        cv.drawRoundRect(skia_rect(-8, hy - 8, (-8) + (100), (hy - 8) + (13)), 7, 7, paint(dark(body, 0.35)))
    _eyes(25, hy + 2, mood, eye, look, blink_amount(t + seed), t)
    _mouth(hy + 42, mood, talk, t)
    if "glasses" in tuple(extras or ()):
        for sd in (-1, 1):
            oval(sd * 25, hy + 2, 21, 20, paint((255, 255, 255), 40))
            cv.drawCircle(sd * 25, hy + 2, 21, paint(LINE, stroke=4.5))
        cv.drawLine(-4, hy + 2, 4, hy + 2, paint(LINE, stroke=4))
    if tear:
        oval(-34, hy + 22 + 40 * (t % 1), 5, 8, paint((120, 190, 255)))
    cv.restore()


def skia_rect(l, t, r, b):
    import skia
    return skia.Rect.MakeLTRB(l, t, r, b)
