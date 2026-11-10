"""Vector-look people: rounded flat-vector characters with soft gradients, coloured shading, big expressive eyes and no outlines.
Same cast system as people.py (role, gender, age, skin, hair, mood, eye, brow, action, carry), same character units:
the origin is the centre of the feet, up is negative, an adult is about 410 units tall."""
import math

import skia

from . import engine as E
from . import vector as V
from .people import HAIR, ROLES, SKIN
from .vector import dark, lite, mixc, oval, paint, poly, rad, lin, rrect, smooth, curve

SHOES = [(236, 90, 110), (70, 80, 150), (58, 54, 74), (244, 190, 80), (80, 176, 154), (186, 110, 220)]
IRIS = [(96, 62, 38), (60, 120, 180), (70, 150, 104), (130, 100, 44), (88, 80, 130)]
INKC = (52, 30, 56)                      # the dark of lines and pupils: a deep plum, never pure black


class _F:
    """facing sign for light: light always comes from the upper left of the SCREEN, whichever way the person faces"""
    f = 1


def ball(cx, cy, rx, ry, c, f, a=255):
    """an oval with a soft highlight toward the light and a coloured shadow on the far side"""
    oval(cx, cy, rx, ry, paint(shader=rad(cx - f * rx * 0.32, cy - ry * 0.38, max(rx, ry) * 1.6, [(0, lite(c, 0.3) + (a,)), (0.55, c + (a,)), (1, dark(c, 0.24) + (a,))])))


def limb(p0, p1, w, c, f):
    """a rounded limb from p0 to p1 with a light edge and a coloured shadow edge"""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    n = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / n, dx / n
    sd = -f if nx * -f > 0 else f
    V.cv.drawLine(p0[0], p0[1], p1[0], p1[1], paint(dark(c, 0.22), stroke=w))
    o = w * 0.07
    V.cv.drawLine(p0[0] - nx * o * sd, p0[1] - ny * o * sd, p1[0] - nx * o * sd, p1[1] - ny * o * sd, paint(c, stroke=w * 0.84))
    o2 = w * 0.2
    V.cv.drawLine(p0[0] - nx * o2 * sd, p0[1] - ny * o2 * sd, p1[0] - nx * o2 * sd, p1[1] - ny * o2 * sd, paint(lite(c, 0.32), 150, stroke=w * 0.24))


def fill_grad(pts, c, f, x_half, y0=None, y1=None, round_=True):
    sh = lin(-f * x_half, 0, f * x_half, 0, [(0, lite(c, 0.16)), (0.55, c), (1, dark(c, 0.22))])
    (smooth if round_ else poly)(pts, paint(shader=sh))


def arc_pts(cx, cy, rx, ry, a0, a1, n=12):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def person(x, y, s=1.0, f=1, t=0.0, role="stranger", gender="male", age="adult", skin="fair", hair="brown", extras=(), talk=0.0,
           eye="open", brow=(0, 0), tear=0.0, look=(0, 0), action="stand", mood="neutral", bounce=0.0, carry=None, seed=0, walk=0.0, gait=0.0):
    cv = V.cv
    spec = ROLES.get(role, ROLES["stranger"])
    kid, elder, fem = age == "child", age == "elder", gender == "female"
    s = s * (0.72 if kid else (0.97 if elder else 1.0))
    HS = 1.22 if kid else 1.0
    skin_c = SKIN.get(skin, SKIN["fair"])
    hair_c = HAIR["grey" if elder else (hair if hair in HAIR else "brown")]
    top, bottom = spec["top"], spec["bottom"]
    V.ground_shadow(x, y, s)
    if walk > 0.3:
        return _side(x, y, s, f, t, spec, role, kid, elder, fem, skin_c, hair_c, hair, skin, extras, talk, mood, brow, bounce, carry, seed, walk, gait)

    breath = math.sin(t * 1.7 + seed) * 1.6
    bob = -abs(math.sin(gait)) * 9 * walk + breath
    bounce = bounce + bob
    nod = max(0.0, math.sin(t * 0.9 + seed * 1.3)) ** 10 * 6 + (math.sin(t * 7.3 + seed) * 2.6 + math.sin(t * 3.1) * 1.4) * (1 if talk > 0 else 0) + \
        {"sad": 11, "scared": 4, "shocked": -5, "smug": -4, "happy": -2}.get(mood, 0)
    turn = min(1.0, walk * 1.6)
    cv.save()
    cv.translate(x, y + bounce)
    cv.scale(f * s, s)
    sw = math.sin(t * 2.2 + seed)

    # ---------------- legs and shoes
    hip_y = -140 if not kid else -128
    shoe = (250, 250, 252) if role in ("doctor", "nurse") else SHOES[(seed + len(role)) % len(SHOES)]
    dress = fem and spec.get("dress") and not kid or (kid and fem)
    leg_col = skin_c if dress else bottom
    for sx in (-1, 1):
        fy = -bounce / s + 0
        foot = (sx * 25, -14 + fy * 0)
        V.cv.drawLine(sx * 22, hip_y, foot[0], foot[1], paint(dark(leg_col, 0.24), stroke=36))
        V.cv.drawLine(sx * 22 + f * -2, hip_y, foot[0] - f * 2, foot[1], paint(leg_col, stroke=30))
        V.cv.drawLine(sx * 22 - f * 7, hip_y, foot[0] - f * 7, foot[1], paint(lite(leg_col, 0.3), 140, stroke=8))
        ball(sx * 30, -9, 31, 15, shoe, f)
        V.oval(sx * 30, -2, 29, 6, paint(dark(shoe, 0.4), 150))
    # ---------------- torso
    tw = (58 if not fem else 52) * (1 - 0.2 * turn)
    torso_col = spec.get("coat") or top
    if dress:
        skirt = torso_col if not spec.get("cardigan") else top
        fill_grad([(-tw + 6, -156), (tw - 6, -156), (tw + 32, -70), (0, -60), (-tw - 32, -70)], skirt, f, tw + 30)
        V.poly([(-tw - 32, -70), (-tw - 22, -58), (-8, -50), (8, -50), (tw + 22, -58), (tw + 32, -70)], paint(dark(skirt, 0.28), 160))
    if spec.get("coat") and role in ("doctor", "scientist", "judge", "firefighter", "stranger"):
        fill_grad([(-tw, -156), (tw, -156), (tw + 12, -56), (0, -48), (-tw - 12, -56)], spec["coat"], f, tw + 10)
    torso = [(-tw * 0.6, -292), (tw * 0.6, -292), (tw * 1.02, -272), (tw * 0.94, -206), (tw * 0.9, -146), (-tw * 0.9, -146), (-tw * 0.94, -206), (-tw * 1.02, -272)]
    fill_grad(torso, torso_col, f, tw)
    V.oval(-f * tw * 0.4, -236, tw * 0.16, 38, paint(lite(torso_col, 0.4), 40, blur=9))
    if spec.get("coat") and top != spec["coat"]:
        poly([(-12, -288), (12, -288), (24, -156), (-24, -156)], paint(top))
        V.line(0, -288, 0, -156, dark(spec["coat"], 0.3), 3.5)
    if spec.get("cardigan"):
        for sx in (-1, 1):
            smooth([(sx * (tw - 4), -280), (sx * 14, -286), (sx * 12, -152), (sx * (tw - 2), -152)], paint(spec["cardigan"]))
    if spec.get("vest"):
        for sx in (-1, 1):
            smooth([(sx * (tw - 6), -278), (sx * 14, -282), (sx * 18, -152), (sx * (tw - 4), -152)], paint(spec["vest"]))
    if spec.get("bib"):
        smooth([(-32, -262), (32, -262), (38, -152), (-38, -152)], paint(spec["bib"]))
        for sx in (-1, 1):
            V.line(sx * 26, -262, sx * 38, -292, spec["bib"], 11)
        rrect(-16, -236, 16, -208, 6, paint(dark(spec["bib"], 0.2)))
    if spec.get("apron"):
        smooth([(-36, -248), (0, -250), (36, -248), (41, -190), (44, -126), (0, -122), (-44, -126), (-41, -190)], paint(shader=lin(-40, 0, 40, 0, [(0, lite(spec["apron"], 0.2)), (1, dark(spec["apron"], 0.18))])))
        smooth([(-18, -248), (18, -248), (14, -274), (-14, -274)], paint(spec["apron"]))
        rrect(-22, -200, 22, -170, 8, paint(dark(spec["apron"], 0.14), 190))
    if spec.get("tie"):
        poly([(-10, -286), (10, -286), (14, -262), (0, -190), (-14, -262)], paint(spec["tie"]))
        poly([(-10, -286), (10, -286), (6, -270), (-6, -270)], paint(dark(spec["tie"], 0.25)))
    if role == "waiter":
        poly([(-14, -288), (0, -272), (-14, -258)], paint(spec["tie"]))
        poly([(14, -288), (0, -272), (14, -258)], paint(spec["tie"]))
    if spec.get("collar"):
        poly([(-28, -288), (28, -288), (12, -214), (-12, -214)], paint(spec["collar"]))
    if spec.get("steth"):
        curve([(-22, -288), (-34, -250), (-26, -222), (-4, -216), (16, -226)], paint((70, 70, 92), stroke=6))
        oval(18, -222, 11, 11, paint(shader=rad(15, -226, 16, [(0, (236, 240, 250)), (1, (130, 140, 170))])))
    if spec.get("badge"):
        poly([(24, -250), (38, -238), (33, -222), (15, -222), (10, -238)], paint(shader=lin(10, -250, 38, -222, [(0, (255, 240, 130)), (1, (240, 170, 50))])))
    if spec.get("smudge"):
        oval(-20, -190, 15, 10, paint(dark(top, 0.3), 120, blur=3))
    if spec.get("pack"):
        V.line(-tw + 6, -282, -tw + 4, -176, (250, 190, 60), 10)
        V.line(tw - 6, -282, tw - 4, -176, (250, 190, 60), 10)

    # ---------------- neck and head
    hy = (-350 if not kid else -318) + nod
    hrx, hry = 62 * HS, 66 * HS
    neck_c = dark(skin_c, 0.12)
    rrect(-17, -296, 17, hy + 44, 9, paint(neck_c))
    V.oval(0, hy + 52, 26, 12, paint(dark(skin_c, 0.34), 130, blur=5))
    long_back = fem and not elder and not kid or (kid and fem and "bun" not in extras)
    if long_back:
        ball(0, hy - 4, hrx + 14, hry + 14, hair_c, f)
        for sx in (-1, 1):
            ball(sx * (hrx + 4), hy + 58, 21, 64, hair_c, f)
    for sx in (-1, 1):
        ball(sx * (hrx - 2), hy + 6, 14 * HS, 18 * HS, dark(skin_c, 0.08), f)
    ball(0, hy, hrx, hry, skin_c, f)
    V.oval(0, hy + hry * 0.72, hrx * 0.62, hry * 0.18, paint(lite(skin_c, 0.25), 70, blur=7))

    # ---------------- face (the face shifts a little toward where the person walks)
    shx = 15 * turn
    ey, ex = hy - 6 * HS, 27 * HS
    er = 15 * HS
    wide = eye in ("wide", "spiral")
    iris = IRIS[0] if skin in ("brown", "dark") else IRIS[1] if hair in ("blonde", "red") else IRIS[(seed * 7 + 2) % len(IRIS)]
    for sx in (-1, 1):
        ecx, ecy = sx * ex + shx, ey
        rx_, ry_ = er * (1.3 if wide else 1.08), er * (1.62 if wide else 1.32)
        if eye == "closed" or E.blink(t + 0.7):
            curve([(ecx - rx_, ecy), (ecx, ecy + ry_ * 0.34), (ecx + rx_, ecy)], paint(INKC, stroke=5.5))
        elif eye == "happy":
            curve([(ecx - rx_, ecy + ry_ * 0.3), (ecx, ecy - ry_ * 0.6), (ecx + rx_, ecy + ry_ * 0.3)], paint(INKC, stroke=6.5))
        else:
            cv.drawOval(skia.Rect(ecx - rx_ - 1, ecy - ry_ - 1, ecx + rx_ + 1, ecy + ry_ + 1), paint(dark(skin_c, 0.2), 120, blur=2))
            oval(ecx, ecy, rx_, ry_, paint(shader=rad(ecx, ecy - ry_ * 0.2, ry_ * 1.5, [(0, (255, 255, 255)), (0.7, (248, 246, 252)), (1, (212, 208, 232))])))
            cv.save()
            ep = skia.Path()
            ep.addOval(skia.Rect(ecx - rx_, ecy - ry_, ecx + rx_, ecy + ry_))
            cv.clipPath(ep, doAntiAlias=True)
            if eye == "spiral":
                pts = [(ecx + (k * 0.9) * math.cos(k * 0.55 + t * 4) * rx_ / 6.5, ecy + (k * 0.9) * math.sin(k * 0.55 + t * 4) * rx_ / 6.5) for k in range(1, 18)]
                curve(pts, paint(INKC, stroke=3.5))
            else:
                ox, oy = look[0] * 6 * f + f * 1.5 + 0, look[1] * 5
                pr = 0.34 if eye == "wide" else 0.5
                ir = rx_ * 0.74
                oval(ecx + ox, ecy + oy, ir, ir * 1.04, paint(shader=rad(ecx + ox, ecy + oy + ir * 0.2, ir * 1.3, [(0, lite(iris, 0.45)), (0.55, iris), (1, dark(iris, 0.45))])))
                oval(ecx + ox, ecy + oy, ir * pr * 1.35, ir * pr * 1.45, paint(INKC))
                oval(ecx + ox - ir * 0.34, ecy + oy - ir * 0.4, ir * 0.27, ir * 0.27, paint((255, 255, 255)))
                oval(ecx + ox + ir * 0.34, ecy + oy + ir * 0.32, ir * 0.12, ir * 0.12, paint((255, 255, 255), 200))
            if eye in ("half", "sleepy"):
                rect_h = ry_ * 1.1
                V.rect(ecx - rx_ - 2, ecy - ry_ - 2, ecx + rx_ + 2, ecy - ry_ + rect_h, paint(shader=lin(0, ecy - ry_, 0, ecy, [(0, lite(skin_c, 0.05)), (1, skin_c)])))
            cv.restore()
            lid_y = ecy - ry_ + (ry_ * 1.1 if eye in ("half", "sleepy") else 0)
            curve([(ecx - rx_, ecy - ry_ * 0.12), (ecx - rx_ * 0.5, lid_y - ry_ * 0.02 + ry_ * 0.06), (ecx + rx_ * 0.5, lid_y - ry_ * 0.02 + ry_ * 0.06), (ecx + rx_, ecy - ry_ * 0.12)] if eye not in ("half", "sleepy") else
                  [(ecx - rx_, lid_y), (ecx, lid_y + 3), (ecx + rx_, lid_y)], paint(INKC, stroke=5.5))
            if fem and eye not in ("half", "sleepy"):                      # lashes
                V.line(ecx + sx * rx_, ecy - ry_ * 0.18, ecx + sx * (rx_ + 9), ecy - ry_ * 0.52, INKC, 4)
        a_, b_ = (brow[0], brow[1]) if sx > 0 else (brow[1], brow[0])
        bc = dark(hair_c, 0.15) if not elder else (140, 140, 156)
        bpts = [(ecx - 19, ey - 30 + a_), (ecx, ey - 35 + (a_ + b_) / 2), (ecx + 19, ey - 28 + b_)] if sx > 0 else \
               [(ecx + 19, ey - 30 + a_), (ecx, ey - 35 + (a_ + b_) / 2), (ecx - 19, ey - 28 + b_)]
        curve(bpts, paint(bc, stroke=8))
        if tear > 0 and sx > 0:
            ty = ecy + ry_ + 8 + tear * 56
            poly([(ecx + 3, ty - 14), (ecx + 10, ty + 2), (ecx + 3, ty + 12), (ecx - 4, ty + 2)], paint(shader=lin(0, ty - 14, 0, ty + 12, [(0, (200, 232, 255)), (1, (110, 170, 240))])))
    # nose, cheeks, mouth
    nx_ = f * 3 + shx
    oval(nx_, hy + 20 * HS, 10 * HS, 8 * HS, paint(dark(skin_c, 0.16), 200))
    oval(nx_ - 3, hy + 17 * HS, 4 * HS, 3 * HS, paint(lite(skin_c, 0.5), 160))
    blush = 255 if (mood in ("happy", "smug") or eye == "happy") else 110
    for sx in (-1, 1):
        oval(sx * 41 * HS + shx, hy + 30 * HS, 15 * HS, 10 * HS, paint(shader=rad(sx * 41 * HS + shx, hy + 30 * HS, 18 * HS, [(0, (255, 120, 150, blush * 0.7)), (1, (255, 120, 150, 0))])))
    my = hy + 44 * HS
    mx = shx
    if talk > 0 or (eye == "wide" and mood != "happy"):
        o = max(talk * (0.55 + 0.45 * math.sin(t * 17.0 + seed) ** 2), 0.45 if eye == "wide" else 0)
        dep = 8 + 28 * o
        mp = skia.Path()
        mp.moveTo(mx - 21, my - 3)
        mp.quadTo(mx, my + 4, mx + 21, my - 3)
        mp.cubicTo(mx + 20, my + dep, mx - 20, my + dep, mx - 21, my - 3)
        cv.drawPath(mp, paint((122, 30, 56)))
        cv.save()
        cv.clipPath(mp, doAntiAlias=True)
        oval(mx, my + dep, 14, 9 + dep * 0.2, paint((244, 112, 132)))
        V.rect(mx - 17, my - 5, mx + 17, my + 4, paint((255, 255, 255)))
        cv.restore()
    elif mood == "happy" or eye == "happy":
        mp = skia.Path()
        mp.moveTo(mx - 24, my - 5)
        mp.quadTo(mx, my + 8, mx + 24, my - 5)
        mp.quadTo(mx + 14, my + 28, mx, my + 28)
        mp.quadTo(mx - 14, my + 28, mx - 24, my - 5)
        cv.drawPath(mp, paint((122, 30, 56)))
        cv.save()
        cv.clipPath(mp, doAntiAlias=True)
        V.rect(mx - 24, my - 6, mx + 24, my + 7, paint((255, 255, 255)))
        oval(mx, my + 26, 12, 8, paint((244, 112, 132)))
        cv.restore()
    elif mood == "smug":
        curve([(mx - 18, my + 5), (mx + 2, my + 11), (mx + 24, my - 7)], paint(INKC, stroke=5.5))
    elif mood in ("angry", "sad", "scared"):
        curve([(mx - 21, my + 11), (mx, my - 3), (mx + 21, my + 11)], paint(INKC, stroke=5.5))
    elif mood == "shocked":
        oval(mx, my + 6, 11, 14, paint((122, 30, 56)))
        oval(mx, my + 12, 7, 6, paint((244, 112, 132)))
    else:
        curve([(mx - 16, my + 3), (mx, my + 6), (mx + 16, my + 3)], paint(INKC, stroke=5))
    # facial hair
    if "mustache" in extras or "beard" in extras or (role == "grandfather" and not fem):
        smooth([(mx - 28, my - 8), (mx - 6, my - 15), (mx, my - 7), (mx + 6, my - 15), (mx + 28, my - 8), (mx + 18, my + 3), (mx, my - 3), (mx - 18, my + 3)], paint(hair_c))
    if "beard" in extras:
        smooth([(-hrx + 8, my - 12), (hrx - 8, my - 12), (hrx - 14, my + 46), (0, my + 66), (-hrx + 14, my + 46)], paint(shader=lin(0, my - 12, 0, my + 66, [(0, hair_c), (1, dark(hair_c, 0.25))])))
    if spec.get("glasses") or "glasses" in extras:
        for sx in (-1, 1):
            cv.drawOval(skia.Rect(sx * ex + shx - 27 * HS, ey - 25 * HS, sx * ex + shx + 27 * HS, ey + 25 * HS), paint((46, 40, 74), stroke=4.5))
            oval(sx * ex + shx - 8, ey - 10 * HS, 10, 5, paint((255, 255, 255), 90))
        V.line(-ex + 27 * HS + shx, ey, ex - 27 * HS + shx, ey, (46, 40, 74), 4)
    # ---------------- front hair
    hat = spec.get("hat")
    hat_hides = hat in ("hard", "fire", "police", "nurse", "chef", "cap", "bucket", "sun", "straw", "beret", "flatcap")
    if "bald" not in extras and not (elder and not fem and hair == "bald"):
        edge = [(hrx * 0.9, hy - 24), (hrx * 0.45, hy - 40), (0, hy - 26), (-hrx * 0.5, hy - 44), (-hrx * 0.96, hy - 22)] if fem else \
               [(hrx * 0.96, hy - 28), (hrx * 0.5, hy - 38), (0, hy - 26), (-hrx * 0.45, hy - 40), (-hrx * 0.96, hy - 26)]
        capp = arc_pts(0, hy - 2, hrx + 5, hry + 8, 190, 350, 14)
        if not hat_hides or hat in ("cap", "flatcap", "bucket", "beret"):
            hp = [(px + shx * 0.4, py) for px, py in capp] + [(px + shx * 0.4, py) for px, py in edge]
            smooth(hp, paint(shader=lin(-f * hrx, hy - hry, f * hrx, hy, [(0, lite(hair_c, 0.2)), (0.5, hair_c), (1, dark(hair_c, 0.28))])))
            curve([(-hrx * 0.55 + shx * 0.4, hy - hry * 0.78), (-hrx * 0.1, hy - hry * 0.98), (hrx * 0.3, hy - hry * 0.94)], paint(lite(hair_c, 0.45), 130, stroke=7))
        if fem and (elder or "bun" in extras):
            ball(0, hy - hry - 22, 31, 27, hair_c, f)
    _hat(hat, hy - hry, hrx, spec, f, shx)
    cv.restore()

    # ---------------- arms (drawn in the world again: the pose table is in character units)
    cv.save()
    cv.translate(x, y + bounce)
    cv.scale(f * s, s)
    sh = -268 if not kid else -240
    pose = action
    if pose == "stand" and walk <= 0.3:
        pose = {"shocked": "up", "scared": "up", "angry": "hips", "sad": "limp", "happy": "wave", "smug": "hips"}.get(mood, "stand")
    near = 1
    hands = {}
    for sx in (-1, 1):
        ax, ay = sx * (tw + 2), sh + 6
        if pose == "stand":
            asw = math.sin(gait + (math.pi if sx > 0 else 0.0)) * walk
            ex_, ey_, hx_, hy_ = ax + sx * 18 + asw * 8, ay + 62, ax + sx * 26 + asw * 20, ay + 128 + sw * 4 * sx - abs(asw) * 6
        elif pose == "limp":
            ex_, ey_, hx_, hy_ = ax + sx * 6, ay + 70, ax + sx * 10, ay + 138
        elif pose == "talk":
            kind_ = int(t * 0.62 + seed * 0.37) % 4
            g_ = math.sin(t * 6.0 + seed)
            if kind_ == 0 and sx == near:
                ex_, ey_, hx_, hy_ = ax + 30, ay + 44, ax + 58, ay - 26 + g_ * 18
            elif kind_ == 1:
                ex_, ey_, hx_, hy_ = ax + sx * 40, ay + 56, ax + sx * 58, ay + 40 + math.sin(t * 5 + sx) * 6
            elif kind_ == 2 and sx == near:
                ex_, ey_, hx_, hy_ = ax + 26, ay + 30, ax + 40, ay - 52 + g_ * 6
            elif kind_ == 3 and sx == near:
                ex_, ey_, hx_, hy_ = ax + 34, ay + 52, ax + 70, ay + 40 + abs(math.sin(t * 4.0)) * 28
            else:
                ex_, ey_, hx_, hy_ = ax - 12, ay + 62, ax - 18, ay + 126
        elif pose == "hop":
            ex_, ey_, hx_, hy_ = ax + sx * 36, ay - 24, ax + sx * 48, ay - 96
        elif pose == "flap":
            ph = t * 14 + (0 if sx > 0 else 1.6)
            ex_, ey_, hx_, hy_ = ax + sx * 40, ay - 20, ax + sx * (46 + 12 * math.sin(ph)), ay - 100 + 26 * math.sin(ph + 1.2)
        elif pose == "up":
            ex_, ey_, hx_, hy_ = ax + sx * 24, ay + 8, ax + sx * 6, ay - 50
        elif pose == "hips":
            ex_, ey_, hx_, hy_ = ax + sx * 54, ay + 54, ax + sx * 4, ay + 104
        elif pose == "point":
            if sx == near:
                ex_, ey_, hx_, hy_ = ax + 36, ay + 16, ax + 108 + math.sin(t * 5) * 4, ay - 10
            else:
                ex_, ey_, hx_, hy_ = ax - 12, ay + 62, ax - 18, ay + 126
        elif pose == "shrug":
            k_ = math.sin(t * 4.0 + seed) * 5
            ex_, ey_, hx_, hy_ = ax + sx * 48, ay + 42, ax + sx * 62, ay + 2 + k_
        elif pose == "cheer":
            ph = t * 9 + sx * 1.4
            ex_, ey_, hx_, hy_ = ax + sx * 36, ay - 14, ax + sx * (30 + 8 * math.sin(ph)), ay - 112 + 14 * math.sin(ph * 1.3)
        elif pose == "facepalm":
            if sx == near:
                ex_, ey_, hx_, hy_ = ax + 34, ay + 8, 12, hy + 6
            else:
                ex_, ey_, hx_, hy_ = ax - 8, ay + 66, ax - 14, ay + 130
        elif pose == "think":
            if sx == near:
                ex_, ey_, hx_, hy_ = ax + 6, ay + 58, 10, hy + 62
            else:
                ex_, ey_, hx_, hy_ = ax - 4, ay + 70, 6, ay + 98
        elif pose == "laugh":
            ex_, ey_, hx_, hy_ = ax + sx * 30, ay + 56, sx * 16, ay + 100 + math.sin(t * 15 + sx) * 5
        elif pose == "tremble":
            ex_, ey_, hx_, hy_ = ax + sx * 14, ay + 56, ax + sx * 8 + math.sin(t * 38 + sx) * 3, ay + 108 + math.cos(t * 41) * 2
        elif pose == "wave":
            if sx == near:
                g_ = math.sin(t * 8.0 + seed)
                ex_, ey_, hx_, hy_ = ax + 40, ay - 10, ax + 50 + g_ * 20, ay - 82
            else:
                ex_, ey_, hx_, hy_ = ax - 12, ay + 62, ax - 18, ay + 126
        else:
            ex_, ey_, hx_, hy_ = ax + sx * 18, ay + 62, ax + sx * 26, ay + 128
        hands[sx] = (hx_, hy_)
        sleeve = spec.get("coat") or top
        limb((ax, ay), (ex_, ey_), 33, sleeve, f)
        limb((ex_, ey_), (hx_, hy_ - 12), 29, sleeve, f)
        cuff = lite(sleeve, 0.35)
        limb((hx_ + (ex_ - hx_) * 0.18, hy_ - 12 + (ey_ - hy_ + 12) * 0.18), (hx_, hy_ - 12), 31, cuff, f)
        ball(hx_, hy_, 16, 16, skin_c, f)
        ball(hx_ + f * 9, hy_ - 6, 6.5, 9, skin_c, f)
    item = None if carry == "none" else (carry or spec.get("tool"))
    if item:
        _item(item, hands[near][0], hands[near][1], f)
    cv.restore()


def _hat(hat, top_y, hrx, spec, f, shx=0.0):
    if not hat:
        return
    cc = spec.get("capcol", (220, 70, 80))
    cx = shx * 0.4
    if hat == "chef":
        base = (252, 252, 252)
        smooth([(cx - hrx * 0.78, top_y + 16), (cx + hrx * 0.78, top_y + 16), (cx + hrx * 0.92, top_y - 22), (cx + hrx * 0.6, top_y - 76), (cx, top_y - 92), (cx - hrx * 0.6, top_y - 76), (cx - hrx * 0.92, top_y - 22)],
               paint(shader=lin(-f * hrx, 0, f * hrx, 0, [(0, base), (1, (206, 214, 244))])))
        rrect(cx - hrx * 0.8, top_y - 2, cx + hrx * 0.8, top_y + 20, 8, paint((226, 232, 252)))
    elif hat in ("cap", "flatcap", "police"):
        col = (40, 52, 110) if hat == "police" else cc
        smooth([(cx - hrx - 2, top_y + 30)] + arc_pts(cx, top_y + 30, hrx + 3, 56, 188, 352, 10) + [(cx + hrx + 2, top_y + 30)], paint(shader=lin(-f * hrx, 0, f * hrx, 0, [(0, lite(col, 0.2)), (1, dark(col, 0.24))])))
        smooth([(cx, top_y + 24), (cx + f * (hrx + 46), top_y + 32), (cx + f * (hrx + 46), top_y + 46), (cx, top_y + 42)], paint(dark(col, 0.32)))
        if hat == "police":
            smooth([(cx - 9, top_y + 6), (cx + 9, top_y + 6), (cx + 11, top_y + 24), (cx, top_y + 32), (cx - 11, top_y + 24)], paint((255, 222, 90)))
    elif hat in ("hard", "fire"):
        col = (255, 214, 50) if hat == "hard" else (222, 54, 60)
        smooth([(cx - hrx - 4, top_y + 32)] + arc_pts(cx, top_y + 32, hrx + 6, 64, 186, 354, 10) + [(cx + hrx + 4, top_y + 32)], paint(shader=lin(-f * hrx, 0, f * hrx, 0, [(0, lite(col, 0.3)), (1, dark(col, 0.2))])))
        rrect(cx - hrx - 16, top_y + 26, cx + hrx + 16, top_y + 42, 8, paint(dark(col, 0.2)))
        rrect(cx - 9, top_y - 26, cx + 9, top_y + 30, 6, paint(dark(col, 0.18), 190))
    elif hat == "nurse":
        smooth([(cx - hrx * 0.72, top_y + 24), (cx + hrx * 0.72, top_y + 24), (cx + hrx * 0.64, top_y - 16), (cx - hrx * 0.64, top_y - 16)], paint((252, 252, 255)))
        rrect(cx - 6, top_y - 10, cx + 6, top_y + 18, 3, paint((232, 60, 80)))
        rrect(cx - 16, top_y + 0, cx + 16, top_y + 8, 3, paint((232, 60, 80)))
    elif hat in ("straw", "sun"):
        col = (244, 208, 110) if hat == "straw" else (255, 244, 208)
        oval(cx, top_y + 32, hrx + 60, 19, paint(shader=lin(0, top_y + 12, 0, top_y + 52, [(0, lite(col, 0.2)), (1, dark(col, 0.2))])))
        smooth([(cx - hrx + 8, top_y + 30)] + arc_pts(cx, top_y + 30, hrx - 8, 44, 190, 350, 10) + [(cx + hrx - 8, top_y + 30)], paint(shader=lin(-f * hrx, 0, f * hrx, 0, [(0, lite(col, 0.25)), (1, dark(col, 0.18))])))
        rrect(cx - hrx + 10, top_y + 20, cx + hrx - 10, top_y + 34, 6, paint((236, 80, 100)))
    elif hat == "bucket":
        col = (255, 210, 60)
        smooth([(cx - hrx - 4, top_y + 36)] + arc_pts(cx, top_y + 32, hrx + 4, 46, 190, 350, 10) + [(cx + hrx + 4, top_y + 36)], paint(shader=lin(-f * hrx, 0, f * hrx, 0, [(0, lite(col, 0.25)), (1, dark(col, 0.2))])))
        oval(cx, top_y + 38, hrx + 30, 13, paint(dark(col, 0.12)))
    elif hat == "beret":
        oval(cx + f * 8, top_y + 12, hrx * 0.92, 26, paint(shader=lin(0, top_y - 14, 0, top_y + 40, [(0, lite(cc, 0.25)), (1, dark(cc, 0.25))])))
        oval(cx + f * 8, top_y - 14, 5, 7, paint(dark(cc, 0.35)))


# ------------------------------------------------------------------ walking and running: the profile view
def _side(x, y, s, f, t, spec, role, kid, elder, fem, skin_c, hair_c, hair, skin, extras, talk, mood, brow, bounce, carry, seed, walk, gait):
    cv = V.cv
    top, bottom = spec["top"], spec["bottom"]
    HS = 1.22 if kid else 1.0
    bob = -abs(math.sin(gait)) * 11 * walk + math.sin(t * 1.7 + seed) * 1.2
    cv.save()
    cv.translate(x, y + bounce + bob * s)
    cv.scale(f * s, s)
    dress = fem and spec.get("dress") and not kid or (kid and fem)
    leg_col = skin_c if dress else bottom
    shoe = (250, 250, 252) if role in ("doctor", "nurse") else SHOES[(seed + len(role)) % len(SHOES)]
    run = 1.25 if walk > 0.9 else 1.0
    hip = (0, -142 if not kid else -128)
    fyc = -bob                                              # cancel the bob so the feet stay on the ground

    def leg(ph, behind):
        sw_ = math.sin(gait + ph) * walk
        lift = max(0.0, math.cos(gait + ph)) * 24 * walk * run
        foot = (sw_ * 56 * run, -14 - lift + fyc)
        knee = ((hip[0] + foot[0]) / 2 + 18 + max(0, math.cos(gait + ph)) * 16 * walk, (hip[1] + foot[1]) / 2 + 4)
        c = dark(leg_col, 0.18) if behind else leg_col
        V.cv.drawLine(hip[0], hip[1], knee[0], knee[1], paint(dark(c, 0.22), stroke=38))
        V.cv.drawLine(knee[0], knee[1], foot[0], foot[1], paint(dark(c, 0.22), stroke=34))
        V.cv.drawLine(hip[0], hip[1], knee[0], knee[1], paint(c, stroke=32))
        V.cv.drawLine(knee[0], knee[1], foot[0], foot[1], paint(c, stroke=28))
        sc_ = dark(shoe, 0.2) if behind else shoe
        ball(foot[0] + 16, foot[1] + 6, 33, 15, sc_, 1)

    leg(math.pi, True)
    tw = 46
    torso_col = spec.get("coat") or top
    arm_ph = lambda ph: math.sin(gait + ph) * walk

    def arm(ph, behind):
        a = arm_ph(ph)
        sh = (0, -266 if not kid else -238)
        el = (a * 28, sh[1] + 62)
        hd = (a * 58 * run, sh[1] + 118 - abs(a) * 22 * run)
        if run > 1.0:
            el = (a * 40 + 14, sh[1] + 54)
            hd = (a * 70 + 28, sh[1] + 56 - abs(a) * 8)
        c = dark(torso_col, 0.2) if behind else torso_col
        limb(sh, el, 32, c, 1)
        limb(el, hd, 28, c, 1)
        ball(hd[0], hd[1], 16, 16, dark(skin_c, 0.12) if behind else skin_c, 1)
        return hd

    arm(0.0, True)
    if dress:
        fill_grad([(-tw + 4, -156), (tw - 4, -156), (tw + 22, -70), (0, -60), (-tw - 22, -70)], torso_col if not spec.get("cardigan") else top, 1, tw + 20)
    fill_grad([(-tw * 0.6, -292), (tw * 0.6, -292), (tw * 1.02, -270), (tw * 0.9, -206), (tw * 0.86, -146), (-tw * 0.86, -146), (-tw * 0.9, -206), (-tw * 1.02, -270)], torso_col, 1, tw)
    if spec.get("apron"):
        smooth([(-4, -248), (36, -248), (42, -124), (-4, -124)], paint(spec["apron"]))
    if spec.get("tie"):
        poly([(8, -286), (24, -280), (26, -250), (14, -200)], paint(spec["tie"]))
    leg(0.0, False)
    # head in profile
    hy = (-346 if not kid else -314)
    hrx, hry = 60 * HS, 65 * HS
    rrect(-14, -296, 20, hy + 40, 9, paint(dark(skin_c, 0.12)))
    if fem and not elder and not kid:
        ball(-16, hy + 18, hrx + 4, hry + 30, hair_c, 1)
    ball(8, hy, hrx, hry, skin_c, 1)
    ball(30, hy + 14, 14 * HS, 11 * HS, dark(skin_c, 0.06), 1)                      # nose
    oval(-12, hy + 8, 13 * HS, 17 * HS, paint(dark(skin_c, 0.12)))                  # ear
    ex_, ey_ = 28, hy - 6
    if E.blink(t + 0.7):
        curve([(ex_ - 12, ey_), (ex_, ey_ + 5), (ex_ + 12, ey_)], paint(INKC, stroke=5))
    else:
        oval(ex_, ey_, 13 * HS, 17 * HS, paint((255, 255, 255)))
        oval(ex_ + 5, ey_ + 1, 8 * HS, 10 * HS, paint(INKC))
        oval(ex_ + 3, ey_ - 4, 3, 3, paint((255, 255, 255)))
        curve([(ex_ - 12, ey_ - 4), (ex_, ey_ - 18 * HS), (ex_ + 13, ey_ - 6)], paint(INKC, stroke=4.5))
    curve([(ex_ - 14, ey_ - 30), (ex_ + 2, ey_ - 34), (ex_ + 18, ey_ - 28)], paint(dark(hair_c, 0.15), stroke=7))
    oval(34, hy + 30, 11, 8, paint((255, 130, 150), 130, blur=3))
    if mood in ("happy",):
        curve([(24, hy + 42), (40, hy + 50), (52, hy + 38)], paint(INKC, stroke=4.5))
    else:
        curve([(26, hy + 44), (40, hy + 46), (50, hy + 42)], paint(INKC, stroke=4.5))
    hat = spec.get("hat")
    if "bald" not in extras and (not hat or hat in ("cap", "flatcap", "bucket", "beret")):
        smooth(arc_pts(6, hy - 2, hrx + 4, hry + 7, 175, 350, 12) + [(hrx - 14, hy - 26), (22, hy - 40), (-14, hy - 22)], paint(shader=lin(-hrx, hy - hry, hrx, hy, [(0, lite(hair_c, 0.2)), (1, dark(hair_c, 0.26))])))
    if fem and ("bun" in extras or elder):
        ball(-18, hy - hry - 14, 28, 25, hair_c, 1)
    if spec.get("glasses") or "glasses" in extras:
        cv.drawOval(skia.Rect(ex_ - 20, ey_ - 22, ex_ + 24, ey_ + 24), paint((46, 40, 74), stroke=4))
    _hat(hat, hy - hry, hrx, spec, 1, 8 * 0.4)
    ahd = arm(math.pi, False)
    item = None if carry == "none" else (carry or spec.get("tool"))
    if item:
        _item(item, ahd[0], ahd[1], 1)
    cv.restore()


# ------------------------------------------------------------------ held things
def _item(item, hx, hy, f):
    cv = V.cv

    def box(x0, y0, x1, y1, c, r=5):
        rrect(x0, y0, x1, y1, r, paint(shader=lin(x0, y0, x1, y1, [(0, lite(c, 0.22)), (1, dark(c, 0.2))])))

    def ball_(cx, cy, rx, ry, c):
        ball(cx, cy, rx, ry, c, f)

    def ln(x0, y0, x1, y1, c, w):
        cv.drawLine(x0, y0, x1, y1, paint(dark(c, 0.2), stroke=w))
        cv.drawLine(x0, y0, x1, y1, paint(c, stroke=w * 0.78))

    if item == "book":
        box(hx - 6, hy - 32, hx + 42, hy + 8, (214, 74, 96), 6)
        rrect(hx - 2, hy - 28, hx + 38, hy + 3, 3, paint((255, 248, 228)))
    elif item in ("clipboard", "paper"):
        box(hx - 4, hy - 40, hx + 36, hy + 8, (204, 150, 96) if item == "clipboard" else (255, 255, 250), 5)
        for k in range(3):
            ln(hx + 3, hy - 28 + k * 12, hx + 29, hy - 28 + k * 12, (120, 128, 170), 3)
    elif item == "tray":
        ball_(hx + 12, hy - 14, 58, 9, (214, 220, 236))
        ball_(hx + 20, hy - 34, 12, 18, (255, 255, 250))
        ball_(hx - 2, hy - 28, 10, 12, (255, 190, 80))
    elif item == "wrench":
        ln(hx, hy + 8, hx + 17, hy - 64, (160, 170, 196), 11)
        ball_(hx + 19, hy - 72, 15, 13, (160, 170, 196))
    elif item == "rolling_pin":
        ln(hx - 24, hy - 6, hx + 44, hy - 28, (226, 164, 96), 17)
        ln(hx - 34, hy - 3, hx - 24, hy - 6, (190, 120, 70), 9)
    elif item == "pan":
        ball_(hx + 24, hy - 32, 31, 15, (96, 96, 126))
        ln(hx, hy, hx + 9, hy - 24, (70, 70, 94), 9)
    elif item == "pitchfork":
        ln(hx, hy + 22, hx + 6, hy - 132, (176, 124, 80), 10)
        for k in (-15, 0, 15):
            ln(hx + 6 + k, hy - 128, hx + 6 + k, hy - 164, (190, 198, 220), 6)
    elif item == "hose":
        curve([(hx, hy), (hx + 28, hy - 18), (hx + 58, hy + 22)], paint((226, 60, 70), stroke=15))
    elif item == "gavel":
        ln(hx, hy - 4, hx + 24, hy - 42, (170, 110, 70), 10)
        box(hx - 4, hy - 62, hx + 42, hy - 36, (140, 88, 60), 6)
    elif item in ("letter", "bag"):
        box(hx - 4, hy - 28, hx + 42, hy + 8, (255, 255, 248) if item == "letter" else (176, 120, 80), 5)
        if item == "letter":
            curve([(hx - 4, hy - 28), (hx + 19, hy - 8), (hx + 42, hy - 28)], paint((170, 170, 200), stroke=3))
    elif item == "comb":
        box(hx, hy - 26, hx + 40, hy - 10, (50, 50, 96), 4)
    elif item == "brush":
        ln(hx - 10, hy + 8, hx + 28, hy - 58, (176, 116, 70), 8)
        ball_(hx + 32, hy - 66, 9, 13, (240, 70, 120))
    elif item == "flask":
        poly([(hx + 6, hy - 54), (hx + 28, hy - 54), (hx + 28, hy - 32), (hx + 44, hy), (hx - 10, hy)], paint(shader=lin(0, hy - 54, 0, hy, [(0, (190, 250, 220)), (1, (80, 210, 170))])))
    elif item == "watering_can":
        box(hx - 6, hy - 36, hx + 38, hy + 8, (70, 170, 110), 8)
        ln(hx + 36, hy - 22, hx + 66, hy - 42, (70, 170, 110), 9)
    elif item == "hammer":
        ln(hx, hy + 8, hx + 15, hy - 58, (176, 120, 76), 10)
        box(hx - 8, hy - 74, hx + 40, hy - 52, (130, 136, 160), 5)
    elif item == "fish":
        ball_(hx + 24, hy - 28, 37, 15, (120, 190, 236))
        poly([(hx + 58, hy - 28), (hx + 80, hy - 46), (hx + 80, hy - 10)], paint((100, 170, 226)))
    elif item == "camera":
        box(hx - 5, hy - 38, hx + 42, hy - 4, (66, 70, 100), 7)
        ball_(hx + 19, hy - 21, 11, 11, (150, 220, 250))
    elif item == "phone":
        box(hx, hy - 38, hx + 24, hy + 2, (50, 54, 90), 5)
        rrect(hx + 3, hy - 34, hx + 21, hy - 6, 3, paint((120, 220, 250)))
    elif item == "cane":
        ln(hx, hy + 124, hx + 4, hy - 20, (160, 104, 70), 9)
    elif item == "cake":
        box(hx - 10, hy - 32, hx + 42, hy, (255, 190, 214), 8)
        ball_(hx + 16, hy - 38, 9, 9, (232, 50, 80))
    elif item == "umbrella":
        ln(hx, hy + 22, hx, hy - 112, (80, 80, 110), 7)
        smooth([(hx - 74, hy - 100), (hx + 74, hy - 100), (hx + 44, hy - 156), (hx, hy - 170), (hx - 44, hy - 156)], paint(shader=lin(hx - 74, 0, hx + 74, 0, [(0, (255, 100, 120)), (0.5, (255, 180, 80)), (1, (200, 70, 160))])))
    elif item == "baguette":
        ln(hx - 12, hy, hx + 56, hy - 54, (236, 180, 100), 19)
    elif item == "cup":
        box(hx, hy - 32, hx + 26, hy, (255, 255, 250), 6)
        curve([(hx + 26, hy - 24), (hx + 40, hy - 18), (hx + 26, hy - 8)], paint((255, 255, 250), stroke=5))


# ------------------------------------------------------------------ effects
def puff(x, y, s, t, col, seed=1):
    """a soft multi-tone dust cloud"""
    pts = [(0, 0, 1.0), (-0.9, 0.25, 0.75), (0.85, 0.2, 0.8), (-0.35, -0.65, 0.7), (0.4, -0.6, 0.65), (0.05, 0.55, 0.7)]
    wob = 1 + 0.07 * math.sin(t * 6 + seed)
    for dx, dy, r in pts:
        R = 52 * s * r * wob
        oval(x + dx * 50 * s + 6, y + dy * 50 * s + 8, R, R, paint(dark(col, 0.3), 200))
    for dx, dy, r in pts:
        R = 52 * s * r * wob
        oval(x + dx * 50 * s, y + dy * 50 * s, R, R, paint(shader=rad(x + dx * 50 * s - R * 0.3, y + dy * 50 * s - R * 0.3, R * 1.5, [(0, lite(col, 0.55)), (1, col)])))


def sparkle(x, y, s, t, col):
    r = 42 * s * (0.82 + 0.18 * math.sin(t * 8))
    k = 0.2
    V.glow(x, y, r * 2.2, col, 120)
    poly([(x, y - r), (x + r * k, y - r * k), (x + r, y), (x + r * k, y + r * k), (x, y + r), (x - r * k, y + r * k), (x - r, y), (x - r * k, y - r * k)], paint((255, 255, 255)))
    poly([(x, y - r * 0.7), (x + r * k * 0.7, y - r * k * 0.7), (x + r * 0.7, y), (x + r * k * 0.7, y + r * k * 0.7), (x, y + r * 0.7), (x - r * k * 0.7, y + r * k * 0.7), (x - r * 0.7, y), (x - r * k * 0.7, y - r * k * 0.7)], paint(col))


def speed(x, y, dx, n, s, t):
    for i in range(n):
        yy = y + (i - n / 2) * 30 * s
        ln_ = (120 + (i * 53) % 90) * s * (0.85 + 0.15 * math.sin(t * 9 + i))
        x0 = x + dx * (40 + (i * 29) % 50) * s
        cols = [(255, 255, 255), (255, 220, 120), (150, 230, 255), (255, 170, 210)]
        V.cv.drawLine(x0, yy, x0 + dx * ln_, yy, paint(cols[i % 4], 210, stroke=8 * s))
