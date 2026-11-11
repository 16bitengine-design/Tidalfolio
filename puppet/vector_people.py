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


# ------------------------------------------------------------------ motion helpers: everything eases, nothing snaps
def ease(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


def back(k):
    """ease-out with a small overshoot: a hand arrives a touch past its mark, then settles (feels alive, not mechanical)"""
    k = max(0.0, min(1.0, k))
    k1 = k - 1
    return 1 + 2.2 * k1 ** 3 + 1.2 * k1 ** 2


def lerp(a, b, k):
    return a + (b - a) * k


def nz(t, seed, f=1.0):
    """smooth wandering value in about -1..1"""
    return 0.5 * math.sin(t * 1.13 * f + seed * 1.7) + 0.3 * math.sin(t * 2.31 * f + seed * 3.1) + 0.2 * math.sin(t * 0.57 * f + seed * 0.9)


def _hash(i, seed):
    return ((int(i) * 7919 + int(seed) * 104729 + 13) % 11) / 5.0 - 1.0


def saccade(t, seed):
    """eyes do not stare: they jump to a new spot every second or so, quickly, then rest"""
    ph = t * 1.1 + seed * 0.37
    i = math.floor(ph)
    k = ease((ph - i) * 8)
    return (lerp(_hash(i - 1, seed), _hash(i, seed), k) * 2.0, lerp(_hash(i - 1, seed + 5), _hash(i, seed + 5), k) * 1.3)


def blink_amount(t):
    """0 = open, 1 = shut: the lids close and open over about a tenth of a second instead of switching"""
    ph = (t % 3.3) / 0.16
    return math.sin(ph * math.pi) if ph < 1.0 else 0.0


def two_bone(S, Hd, l1, l2, side, ywt=0.35):
    """a two-segment limb that keeps its length and bends at the elbow or knee. Returns (joint, end)."""
    dx, dy = Hd[0] - S[0], Hd[1] - S[1]
    d = math.hypot(dx, dy) or 1e-3
    d2 = min(max(d, abs(l1 - l2) + 1.0), l1 + l2 - 0.5)
    ux, uy = dx / d, dy / d
    end = (S[0] + ux * d2, S[1] + uy * d2)
    a = (l1 * l1 - l2 * l2 + d2 * d2) / (2 * d2)
    h = math.sqrt(max(l1 * l1 - a * a, 0.0))
    px, py = S[0] + ux * a, S[1] + uy * a
    e1, e2 = (px - uy * h, py + ux * h), (px + uy * h, py - ux * h)
    sc = lambda e: e[0] * side + ywt * e[1]
    return (e1 if sc(e1) >= sc(e2) else e2), end


def resolve_pose(action, mood, walk, talk=0.0):
    if action == "stand" and walk <= 0.3:
        if talk > 0.05 and mood not in ("sad", "scared"):                 # someone who is speaking always gestures
            return "talk"
        return {"shocked": "up", "scared": "up", "angry": "hips", "sad": "limp", "happy": "wave", "smug": "hips"}.get(mood, "stand")
    return action


def _talk_target(kind, sx, ax, ay, t, seed, near):
    g_ = math.sin(t * 6.0 + seed)
    if kind == 0 and sx == near:
        return (ax + 58, ay - 26 + g_ * 18)
    if kind == 1:
        return (ax + sx * 58, ay + 40 + math.sin(t * 5 + sx) * 6)
    if kind == 2 and sx == near:
        return (ax + 40, ay - 52 + g_ * 6)
    if kind == 3 and sx == near:
        return (ax + 70, ay + 40 + abs(math.sin(t * 4.0)) * 28)
    return (ax - 18, ay + 126)


def hand_target(pose, sx, ax, ay, t, seed, near, head_y, gait, walk, sw):
    """where the hand wants to be for a pose, in character units; the elbow follows by itself (two_bone)"""
    if pose == "stand":
        asw = math.sin(gait + (math.pi if sx > 0 else 0.0)) * walk
        return (ax + sx * 26 + asw * 20, ay + 128 + sw * 4 * sx - abs(asw) * 6)
    if pose == "limp":
        return (ax + sx * 10, ay + 138)
    if pose == "talk":
        ph = t * 0.62 + seed * 0.37
        k0 = math.floor(ph)
        w = ease((ph - k0) / 0.22)
        a = _talk_target(int(k0 - 1) % 4, sx, ax, ay, t, seed, near)
        b = _talk_target(int(k0) % 4, sx, ax, ay, t, seed, near)
        return (lerp(a[0], b[0], w), lerp(a[1], b[1], w))
    if pose == "hop":
        return (ax + sx * 48, ay - 96)
    if pose == "flap":
        ph = t * 14 + (0 if sx > 0 else 1.6)
        return (ax + sx * (46 + 12 * math.sin(ph)), ay - 100 + 26 * math.sin(ph + 1.2))
    if pose == "up":
        return (ax + sx * 6, ay - 50)
    if pose == "hips":
        return (ax + sx * 4, ay + 104)
    if pose == "point":
        return (ax + 108 + math.sin(t * 5) * 4, ay - 10) if sx == near else (ax - 18, ay + 126)
    if pose == "shrug":
        return (ax + sx * 62, ay + 2 + math.sin(t * 4.0 + seed) * 5)
    if pose == "cheer":
        ph = t * 9 + sx * 1.4
        return (ax + sx * (30 + 8 * math.sin(ph)), ay - 112 + 14 * math.sin(ph * 1.3))
    if pose == "facepalm":
        return (12, head_y + 6) if sx == near else (ax - 14, ay + 130)
    if pose == "think":
        return (10, head_y + 62) if sx == near else (6, ay + 98)
    if pose == "laugh":
        return (sx * 16, ay + 100 + math.sin(t * 15 + sx) * 5)
    if pose == "tremble":
        return (ax + sx * 8 + math.sin(t * 38 + sx) * 3, ay + 108 + math.cos(t * 41) * 2)
    if pose == "offer":                                    # holds something out to the other person
        return (ax + 84, ay + 30 + math.sin(t * 1.6) * 5) if sx == near else (ax - 12, ay + 118)
    if pose == "hold":                                     # clutches something close to the chest
        return (sx * 20 + math.sin(t * 1.4 + sx) * 2, ay + 70)
    if pose == "clasp":                                    # hands together in front: worry, tenderness, waiting
        return (sx * 7 + math.sin(t * 1.9) * 2, ay + 82 + math.sin(t * 1.3 + sx) * 3)
    if pose == "wrap":                                     # both arms reach out toward the other person and draw in, as if putting something round them
        k = 0.5 + 0.5 * math.sin(t * 1.5)
        return (ax + (96 - 22 * k), ay + 54 + 10 * k) if sx == near else (ax + (70 - 14 * k), ay + 84 - 4 * k)
    if pose == "place":                                    # sets something down, forward and low
        return (ax + 58, ay + 104 + abs(math.sin(t * 1.4)) * 14) if sx == near else (ax - 18, ay + 126)
    if pose == "reach":
        return (ax + 98, ay + 46 + math.sin(t * 2.0) * 6) if sx == near else (ax - 18, ay + 124)
    if pose == "beckon":
        return (ax + 62, ay - 14 + math.sin(t * 7.0) * 14) if sx == near else (ax - 18, ay + 126)
    if pose == "hugself":                                  # arms folded over the chest: cold, wet, shy
        return (-sx * 30 + math.sin(t * 22 + sx) * 1.5, ay + 52)
    if pose == "wipe":
        return (24 + math.sin(t * 4.0) * 5, head_y + 14) if sx == near else (ax - 14, ay + 126)
    if pose == "cower":
        return (sx * 36 + math.sin(t * 30 + sx) * 2, head_y + 44)
    if pose == "wave":
        return (ax + 50 + math.sin(t * 8.0 + seed) * 20, ay - 82) if sx == near else (ax - 18, ay + 126)
    return (ax + sx * 26, ay + 128)


def person(x, y, s=1.0, f=1, t=0.0, role="stranger", gender="male", age="adult", skin="fair", hair="brown", extras=(), talk=0.0,
           eye="open", brow=(0, 0), tear=0.0, look=(0, 0), action="stand", mood="neutral", bounce=0.0, carry=None, seed=0, walk=0.0, gait=0.0,
           prev_action=None, prev_mood=None, blend=1.0, wblend=None, listening=0.0, draped="none"):
    cv = V.cv
    spec = ROLES.get(role, ROLES["stranger"])
    kid, elder, fem = age == "child", age == "elder", gender == "female"
    s = s * (0.72 if kid else (0.97 if elder else 1.0))
    c = dict(spec=spec, role=role, kid=kid, elder=elder, fem=fem, skin=skin, hair=hair, skin_c=SKIN.get(skin, SKIN["fair"]),
             hair_c=HAIR["grey" if elder else (hair if hair in HAIR else "brown")], extras=extras, talk=talk, eye=eye, brow=brow, tear=tear,
             look=look, action=action, mood=mood, bounce=bounce, carry=carry, seed=seed, walk=walk, gait=gait,
             prev_action=prev_action if prev_action is not None else action, prev_mood=prev_mood if prev_mood is not None else mood, blend=blend, listening=listening, draped=draped)
    V.ground_shadow(x, y, s)
    if wblend is None:
        wblend = 1.0 if walk > 0.3 else 0.0
    classic = V.STYLE == "classic"
    if classic:
        # squash and stretch about the feet: crouch before a new move (anticipation), overshoot upward as it lands (follow-through),
        # a little give with every step, and a tiny lift on stressed words
        ant = math.sin(min(1.0, blend) * math.pi) * (1.0 if blend < 1.0 else 0.0)
        over = max(0.0, back(blend) - 1.0) * 2.0 if blend < 1.0 else 0.0
        beat_ = max(0.0, math.sin(t * 2.6 + seed * 1.3)) ** 8 * (1.0 if talk > 0 else 0.0)
        sy = 1.0 - 0.055 * ant + 0.05 * over + 0.014 * beat_ + 0.012 * math.sin(t * 1.7 + seed) - 0.03 * walk * abs(math.sin(gait))
        sy = max(0.9, min(1.1, sy))
        sx = 1.0 / sy ** 0.7
        cv.save()
        cv.translate(x, y)
        cv.scale(sx, sy)
        cv.translate(-x, -y)
        cv.saveLayer(None, None)
    if wblend < 0.02:
        _front(x, y, s, f, t, **c)
    elif wblend > 0.98:
        _side(x, y, s, f, t, **c)
    else:                                              # turning from facing us to walking away: crossfade the two views
        for fn, a in ((_front, 1.0 - wblend), (_side, wblend)):
            pt = skia.Paint()
            pt.setAlpha(int(255 * a))
            cv.saveLayer(None, pt)
            fn(x, y, s, f, t, **c)
            cv.restore()
    if classic:
        # one steady light from the upper left: a warm rim on the lit side, a cool violet shade on the other, darker toward the feet.
        # Painted only onto the character itself (SrcATop), so it gives the figure volume without touching the background.
        X = x - 200 * s, x + 200 * s
        top, bot = y - 470 * s, y + 10 * s
        atop = skia.BlendMode.kSrcATop
        cv.drawRect(skia.Rect(X[0], top, X[1], bot), skia.Paint(BlendMode=atop, Shader=lin(x - 150 * s, 0, x - 70 * s, 0, [(0, (255, 226, 170, 120)), (1, (255, 226, 170, 0))])))
        cv.drawRect(skia.Rect(X[0], top, X[1], bot), skia.Paint(BlendMode=atop, Shader=lin(x + 20 * s, 0, x + 150 * s, 0, [(0, (70, 40, 130, 0)), (1, (70, 40, 130, 95))])))
        cv.drawRect(skia.Rect(X[0], top, X[1], bot), skia.Paint(BlendMode=atop, Shader=lin(0, y - 190 * s, 0, y, [(0, (70, 40, 130, 0)), (1, (70, 40, 130, 70))])))
        cv.restore()
        cv.restore()


def _front(x, y, s, f, t, spec, role, kid, elder, fem, skin, hair, skin_c, hair_c, extras, talk, eye, brow, tear, look, action, mood, bounce, carry,
           seed, walk, gait, prev_action, prev_mood, blend, listening=0.0, draped="none"):
    cv = V.cv
    top, bottom = spec["top"], spec["bottom"]
    HS = 1.22 if kid else 1.0
    talking = 1.0 if talk > 0 else 0.0

    # ---- body motion: weight shifts from one foot to the other, the upper body counter-leans, breathing, and speech makes the body move
    breath = math.sin(t * 1.7 + seed)
    sway = nz(t * 0.35, seed) * 6.0 + math.sin(t * 2.1 + seed) * 2.2 * talking + math.sin(gait) * 5 * walk
    lean = -sway * 0.22 + math.sin(t * 3.0 + seed * 2) * 0.8 * talking + {"sad": 2.2, "scared": -1.5, "smug": -1.8, "happy": -0.8}.get(mood, 0)
    beat = max(0.0, math.sin(t * 2.6 + seed * 1.3)) ** 8
    bounce = bounce - abs(math.sin(gait)) * 9 * walk + breath * 1.4
    nod = listening * (max(0.0, math.sin(t * 1.9 + seed * 2.1)) ** 6 * 6) + beat * 5 * talking + math.sin(t * 7.3 + seed) * 1.8 * talking + {"sad": 11, "scared": 4, "shocked": -5, "smug": -4, "happy": -2}.get(mood, 0)
    tilt = nz(t * 0.6, seed + 4) * 2.2 + math.sin(t * 3.0 + seed) * 1.6 * talking + {"sad": -5, "smug": 4, "scared": 3, "happy": 2, "angry": -2}.get(mood, 0)
    turn = min(1.0, walk * 1.6)
    cv.save()
    cv.translate(x, y + bounce)
    cv.scale(f * s, s)
    sw = math.sin(t * 2.2 + seed)

    # ---------------- legs and shoes (feet stay planted; the hips move over them)
    hip_y = -140 if not kid else -128
    hipx = sway * 0.8
    shoe = (250, 250, 252) if role in ("doctor", "nurse") else SHOES[(seed + len(role)) % len(SHOES)]
    dress = fem and spec.get("dress") and not kid or (kid and fem)
    leg_col = skin_c if dress else bottom
    for sx in (-1, 1):
        foot = (sx * 25, -14)
        V.cv.drawLine(sx * 22 + hipx, hip_y, foot[0], foot[1], paint(dark(leg_col, 0.24), stroke=36))
        V.cv.drawLine(sx * 22 + hipx - f * 2, hip_y, foot[0] - f * 2, foot[1], paint(leg_col, stroke=30))
        V.cv.drawLine(sx * 22 + hipx - f * 7, hip_y, foot[0] - f * 7, foot[1], paint(lite(leg_col, 0.3), 140, stroke=8))
        ball(sx * 30, -9, 31, 15, shoe, f)
        V.oval(sx * 30, -2, 29, 6, paint(dark(shoe, 0.4), 150))

    # ---------------- the upper body moves as one piece around the hips
    cv.save()
    cv.translate(hipx, -146)
    cv.rotate(lean)
    cv.scale(1.0, 1.0 + breath * 0.008)
    cv.translate(0, 146)
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

    if draped in ("towel", "blanket"):                      # something put round the shoulders: a towel or a blanket
        dc = (96, 186, 232) if draped == "towel" else (236, 140, 112)
        fill_grad([(-tw * 1.08, -292), (tw * 1.08, -292), (tw * 1.18, -226), (tw * 0.8, -134), (-tw * 0.8, -134), (-tw * 1.18, -226)], dc, f, tw * 1.1)
        for k_ in range(3):
            yy = -246 + k_ * 38
            V.line(-tw * 1.04 + k_ * 4, yy, tw * 1.04 - k_ * 4, yy + 4, (255, 255, 255), 6, 190)
        oval(0, -292, tw * 1.12, 17, paint(shader=lin(-tw, 0, tw, 0, [(0, lite(dc, 0.35)), (1, dark(dc, 0.15))])))
        V.line(-tw * 0.12, -280, -tw * 0.2, -176, dark(dc, 0.25), 4, 160)          # the overlap where the two ends meet

    # ---------------- neck and head
    hy = (-350 if not kid else -318) + nod
    hrx, hry = 62 * HS, 66 * HS
    neck_c = dark(skin_c, 0.12)
    rrect(-17, -296, 17, hy + 44, 9, paint(neck_c))
    V.oval(0, hy + 52, 26, 12, paint(dark(skin_c, 0.34), 130, blur=5))
    cv.save()                                   # the head tilts on the neck
    cv.translate(0, hy + 52)
    cv.rotate(tilt)
    cv.translate(0, -(hy + 52))
    long_back = fem and not elder and not kid or (kid and fem and "bun" not in extras)
    hsw = (math.sin(t * 2.1 + seed) * 2.5 * (talking + walk) - lean * 0.9)      # long hair swings a little behind the head
    if long_back:
        ball(0, hy - 4, hrx + 14, hry + 14, hair_c, f)
        for sx in (-1, 1):
            ball(sx * (hrx + 4) + hsw, hy + 58, 21, 64, hair_c, f)
    for sx in (-1, 1):
        ball(sx * (hrx - 2), hy + 6, 14 * HS, 18 * HS, dark(skin_c, 0.08), f)
    ball(0, hy, hrx, hry, skin_c, f)
    V.oval(0, hy + hry * 0.72, hrx * 0.62, hry * 0.18, paint(lite(skin_c, 0.25), 70, blur=7))

    # ---------------- face (the face shifts a little toward where the person walks)
    shx = 15 * turn
    ey, ex = hy - 6 * HS, 27 * HS
    CL = V.STYLE == "classic"
    er = (15 * 1.14 if CL else 15) * HS
    bk = (blink_amount(t + 0.7) if E.blink.__name__ == "blink" else 0.0) if CL else 0.0
    wide = eye in ("wide", "spiral")
    iris = IRIS[0] if skin in ("brown", "dark") else IRIS[1] if hair in ("blonde", "red") else IRIS[(seed * 7 + 2) % len(IRIS)]
    sac = saccade(t, seed)
    for sx in (-1, 1):
        ecx, ecy = sx * ex + shx, ey
        rx_, ry_ = er * (1.3 if wide else 1.08), er * (1.62 if wide else 1.32)
        if CL and bk > 0 and bk < 0.7 and eye not in ("closed", "happy"):
            ry_ *= 1.0 - bk * 1.15                        # the lid is on its way down or up
        if eye == "closed" or (bk >= 0.7 if CL else E.blink(t + 0.7)):
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
                ox, oy = look[0] * 6 * f + f * 1.5 + sac[0] * f, look[1] * 5 + sac[1]
                pr = 0.34 if eye == "wide" else 0.5
                ir = rx_ * 0.74
                oval(ecx + ox, ecy + oy, ir, ir * 1.04, paint(shader=rad(ecx + ox, ecy + oy + ir * 0.2, ir * 1.3, [(0, lite(iris, 0.45)), (0.55, iris), (1, dark(iris, 0.45))])))
                oval(ecx + ox, ecy + oy, ir * pr * 1.35, ir * pr * 1.45, paint(INKC))
                oval(ecx + ox - ir * 0.34, ecy + oy - ir * 0.4, ir * 0.27, ir * 0.27, paint((255, 255, 255)))
                oval(ecx + ox + ir * 0.34, ecy + oy + ir * 0.32, ir * 0.12, ir * 0.12, paint((255, 255, 255), 200))
            if eye in ("half", "sleepy"):
                V.rect(ecx - rx_ - 2, ecy - ry_ - 2, ecx + rx_ + 2, ecy - ry_ + ry_ * 1.1, paint(shader=lin(0, ecy - ry_, 0, ecy, [(0, lite(skin_c, 0.05)), (1, skin_c)])))
            cv.restore()
            lid_y = ecy - ry_ + (ry_ * 1.1 if eye in ("half", "sleepy") else 0)
            curve([(ecx - rx_, ecy - ry_ * 0.12), (ecx - rx_ * 0.5, lid_y + ry_ * 0.04), (ecx + rx_ * 0.5, lid_y + ry_ * 0.04), (ecx + rx_, ecy - ry_ * 0.12)] if eye not in ("half", "sleepy") else
                  [(ecx - rx_, lid_y), (ecx, lid_y + 3), (ecx + rx_, lid_y)], paint(INKC, stroke=5.5))
            if fem and eye not in ("half", "sleepy"):                      # lashes
                V.line(ecx + sx * rx_, ecy - ry_ * 0.18, ecx + sx * (rx_ + 9), ecy - ry_ * 0.52, INKC, 4)
        a_, b_ = (brow[0], brow[1]) if sx > 0 else (brow[1], brow[0])
        if CL:
            a_, b_ = a_ * 1.35, b_ * 1.35
        a_, b_ = a_ - 4 * beat * talking, b_ - 4 * beat * talking + (1.5 * beat * talking if sx > 0 else 0)      # brows lift on emphasised words
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
        syll = abs(math.sin(t * 9.0 + seed)) * (0.55 + 0.45 * abs(math.sin(t * 2.3 + seed * 1.7)))      # syllables of uneven size, not a buzz
        o = max(talk * (0.2 + 0.8 * syll), 0.45 if eye == "wide" else 0)
        vw = _hash(int((t * 9.0 + seed) / math.pi), seed) if CL else 0.0          # each syllable has its own mouth shape: wide 'ee' or round 'oo'
        mw = 21 * (1.0 + 0.22 * vw)
        dep = (8 + 28 * o) * (1.0 - 0.28 * vw)
        mp = skia.Path()
        mp.moveTo(mx - mw, my - 3)
        mp.quadTo(mx, my + 4, mx + mw, my - 3)
        mp.cubicTo(mx + mw - 1, my + dep, mx - mw + 1, my + dep, mx - mw, my - 3)
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
    cv.restore()                                # end of head tilt

    # ---------------- arms: each hand has a target; the elbow is solved so the arm keeps its length and bends like a real arm
    sh = -268 if not kid else -240
    pose = resolve_pose(action, mood, walk, talk)
    prev_pose = resolve_pose(prev_action, prev_mood, walk, talk)
    e_ = back(blend)
    near = 1
    hands = {}
    for sx in (-1, 1):
        ax, ay = sx * (tw + 2), sh + 6 + breath * 1.0
        tgt_new = hand_target(pose, sx, ax, ay, t, seed, near, hy, gait, walk, sw)
        tgt_old = hand_target(prev_pose, sx, ax, ay, t, seed, near, hy, gait, walk, sw) if blend < 1.0 else tgt_new
        hx_, hy_ = lerp(tgt_old[0], tgt_new[0], e_), lerp(tgt_old[1], tgt_new[1], e_)
        if pose not in ("flap", "cheer", "tremble", "laugh", "hop"):               # hands are never perfectly still
            hx_ += nz(t, seed + sx * 3, 1.3) * 4.0 + sway * 0.2
            hy_ += nz(t, seed + sx * 5 + 1, 1.1) * 3.5 + breath * 1.2
        el, wr = two_bone((ax, ay), (hx_, hy_ - 12), 64, 68, sx)
        ddx, ddy = wr[0] - el[0], wr[1] - el[0 + 1]
        dn = math.hypot(ddx, ddy) or 1.0
        hand = (wr[0] + ddx / dn * 12, wr[1] + ddy / dn * 12)
        hands[sx] = hand
        sleeve = spec.get("coat") or top
        limb((ax, ay), el, 33, sleeve, f)
        limb(el, wr, 29, sleeve, f)
        limb((wr[0] - ddx / dn * 14, wr[1] - ddy / dn * 14), wr, 31, lite(sleeve, 0.35), f)
        ball(hand[0], hand[1], 16, 16, skin_c, f)
        ball(hand[0] + f * 9, hand[1] - 6, 6.5, 9, skin_c, f)
    item = None if carry == "none" else (carry or spec.get("tool"))
    if item:
        _item(item, hands[near][0], hands[near][1], f)
    cv.restore()                                # end of upper body
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
def _side(x, y, s, f, t, spec, role, kid, elder, fem, skin, hair, skin_c, hair_c, extras, talk, eye, brow, tear, look, action, mood, bounce, carry,
          seed, walk, gait, prev_action, prev_mood, blend, listening=0.0, draped="none"):
    cv = V.cv
    top, bottom = spec["top"], spec["bottom"]
    HS = 1.22 if kid else 1.0
    run = 1.25 if walk > 0.9 else 1.0
    bob = -abs(math.sin(gait)) * 11 * walk * run + math.sin(t * 1.7 + seed) * 1.2
    lean = (2.5 + 3.0 * (run - 1.0) * 4) * walk                       # leans into the walk, more when running
    cv.save()
    cv.translate(x, y + bounce + bob * s)
    cv.scale(f * s, s)
    dress = fem and spec.get("dress") and not kid or (kid and fem)
    leg_col = skin_c if dress else bottom
    shoe = (250, 250, 252) if role in ("doctor", "nurse") else SHOES[(seed + len(role)) % len(SHOES)]
    hip = (0, -142 if not kid else -128)
    fyc = -bob                                              # cancel the bob so the feet stay on the ground

    def leg(ph, behind):
        sw_ = math.sin(gait + ph) * walk
        lift = max(0.0, math.cos(gait + ph)) * 26 * walk * run              # the foot only rises while it swings forward
        foot = (sw_ * 58 * run, -14 - lift + fyc)
        knee, foot = two_bone(hip, foot, 72, 70, 1, 0.0)
        c = dark(leg_col, 0.18) if behind else leg_col
        V.cv.drawLine(hip[0], hip[1], knee[0], knee[1], paint(dark(c, 0.22), stroke=38))
        V.cv.drawLine(knee[0], knee[1], foot[0], foot[1], paint(dark(c, 0.22), stroke=34))
        V.cv.drawLine(hip[0], hip[1], knee[0], knee[1], paint(c, stroke=32))
        V.cv.drawLine(knee[0], knee[1], foot[0], foot[1], paint(c, stroke=28))
        sc_ = dark(shoe, 0.2) if behind else shoe
        toe = max(0.0, math.cos(gait + ph)) * 7 * walk                       # toes point down as the foot lifts
        ball(foot[0] + 16, foot[1] + 6 + toe * 0.4, 33, 15, sc_, 1)

    leg(math.pi, True)
    cv.save()                                                  # the upper body leans from the hips and rocks with each step
    cv.translate(0, -146)
    cv.rotate(lean + math.sin(gait * 2) * 0.9 * walk)
    cv.translate(0, 146)
    tw = 46
    torso_col = spec.get("coat") or top

    def arm(ph, behind):
        a = math.sin(gait + ph) * walk
        sh = (0, -266 if not kid else -238)
        hd = (a * 60 * run, sh[1] + 118 - abs(a) * 22 * run)
        if run > 1.0:
            hd = (a * 70 + 28, sh[1] + 56 - abs(a) * 8)
        el, hd = two_bone(sh, hd, 64, 66, -1, 0.35)
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
    # head in profile, nodding gently against the lean
    hy = (-346 if not kid else -314)
    cv.save()
    cv.translate(0, hy + 52)
    cv.rotate(-lean * 0.7 + math.sin(gait * 2 + 0.6) * 1.2 * walk)
    cv.translate(0, -(hy + 52))
    hrx, hry = 60 * HS, 65 * HS
    rrect(-14, -296, 20, hy + 40, 9, paint(dark(skin_c, 0.12)))
    if fem and not elder and not kid:
        ball(-16 - walk * 5, hy + 18, hrx + 4, hry + 30, hair_c, 1)
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
    if mood == "happy":
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
    cv.restore()                                                  # end of head
    ahd = arm(math.pi, False)
    item = None if carry == "none" else (carry or spec.get("tool"))
    if item:
        _item(item, ahd[0], ahd[1], 1)
    cv.restore()                                                  # end of upper body
    leg(0.0, False)
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
    elif item == "towel":                                  # a folded towel
        box(hx - 12, hy - 34, hx + 42, hy + 6, (96, 186, 232), 8)
        for k in range(2):
            ln(hx - 6, hy - 22 + k * 14, hx + 36, hy - 22 + k * 14, (255, 255, 255), 5)
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
