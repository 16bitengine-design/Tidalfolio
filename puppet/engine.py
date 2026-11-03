"""Tidalfolio 2D engine v2 - "storybook ink & paper".
Hand-inked outlines that gently 'boil', layered feathers with follow-through, painted parallax backdrops,
paper grain, parchment pop-ups. Everything is code; characters are defined once and reused."""
import colorsys
import math
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 24
INK = (36, 26, 24)

# Two looks: "ink" (muted storybook) and "toon" (bold comic cartoon: thick outlines, punchy colours, huge eyes)
LOOK = {}


def set_look(name):
    LOOK.clear()
    if name == "toon":
        LOOK.update(toon=True, lw=1.8, sat=1.5, eye=1.5, head=1.22, grain=0.35)
    else:
        LOOK.update(toon=False, lw=1.0, sat=1.0, eye=1.0, head=1.0, grain=1.0)
    _grain.clear()


_pc = {}


def punch(c):
    """push a colour toward the saturated cartoon palette (no-op in the ink look)"""
    if not LOOK["toon"] or not isinstance(c, tuple) or len(c) < 3:
        return c
    if c not in _pc:
        h, s, v = colorsys.rgb_to_hsv(c[0] / 255, c[1] / 255, c[2] / 255)
        s = min(1.0, s * LOOK["sat"])
        v = min(1.0, v * 1.06 + 0.02)
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        _pc[c] = (int(r * 255), int(g * 255), int(b * 255)) + tuple(c[3:])
    return _pc[c]


def lw_(w):
    """line width in the current look (fine detail lines grow less than outlines)"""
    return w * (1 + (LOOK["lw"] - 1) * min(1.0, w / 4.0))
import os
SERIF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Lora-Variable.ttf")   # SIL OFL, bundled
_fonts = {}
_grain = []


TOON_FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Poppins-Bold.ttf")   # SIL OFL, bundled
_tfonts = {}


def tfont(size):
    """caption / pop-up font of the current look"""
    if not LOOK["toon"]:
        return font(size)
    size = int(size)
    if size not in _tfonts:
        _tfonts[size] = ImageFont.truetype(TOON_FONT, size)
    return _tfonts[size]


def font(size):
    size = int(size)
    if size not in _fonts:
        f = ImageFont.truetype(SERIF, size)
        f.set_variation_by_axes([700])
        _fonts[size] = f
    return _fonts[size]


# ---------- math ----------
def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def back(t):
    t = max(0.0, min(1.0, t))
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def kf(u, pts):
    if u <= pts[0][0]:
        return pts[0][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if u <= t1:
            return v0 + (v1 - v0) * ease((u - t0) / (t1 - t0))
    return pts[-1][1]


def mix(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def shade(c, k):
    """k<0 darker, k>0 lighter"""
    return mix(c, (0, 0, 0), -k) if k < 0 else mix(c, (255, 255, 255), k)


# ---------- camera / jitter ----------
class Cam:
    cx, cy, z = W / 2, H / 2, 1.0
    tick = 0


C = Cam


def P(x, y):
    return ((x - C.cx) * C.z + W / 2, (y - C.cy) * C.z + H / 2)


def S(v):
    return v * C.z


def _jit(i, seed, amp):
    h = (i * 73856093) ^ (seed * 19349663) ^ (C.tick * 83492791)
    return ((h % 2001) / 1000.0 - 1.0) * amp


def rot(pts, ang, ox=0, oy=0):
    c, s = math.cos(ang), math.sin(ang)
    return [(ox + (x - ox) * c - (y - oy) * s, oy + (x - ox) * s + (y - oy) * c) for x, y in pts]


def ell_pts(cx, cy, rx, ry, ang=0.0, n=30):
    pts = [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]
    return rot(pts, ang, cx, cy) if ang else pts


def inked(d, pts, fill, w=4.0, seed=1, jit=2.0, ink=INK):
    """filled polygon with a hand-inked, slightly boiling outline"""
    q = [P(x + _jit(i, seed, jit), y + _jit(i + 99, seed, jit)) for i, (x, y) in enumerate(pts)]
    if fill is not None:
        d.polygon(q, fill=punch(fill))
    if w:
        d.line(q + [q[0]], fill=ink, width=max(1, int(S(lw_(w)))), joint="curve")


def blob(d, cx, cy, rx, ry, fill, w=4.0, ang=0.0, seed=1, n=28, jit=1.6):
    inked(d, ell_pts(cx, cy, rx, ry, ang, n), fill, w, seed, jit)


def lit(d, cx, cy, rx, ry, col, w=4.0, ang=0.0, seed=1, n=28, light=(-0.18, -0.2)):
    """ink blob with cel shading: dark rim crescent + lit body + highlight"""
    col = punch(col)
    inked(d, ell_pts(cx, cy, rx, ry, ang, n), shade(col, -0.28), w, seed, 1.6)
    q = [P(x + _jit(i, seed + 5, 1.2), y + _jit(i + 9, seed + 5, 1.2)) for i, (x, y) in
         enumerate(ell_pts(cx + rx * light[0] * 0.5, cy + ry * light[1] * 0.5, rx * 0.9, ry * 0.9, ang, n))]
    d.polygon(q, fill=col)
    q2 = [P(x, y) for x, y in ell_pts(cx + rx * light[0], cy + ry * light[1], rx * 0.42, ry * 0.36, ang, 18)]
    d.polygon(q2, fill=shade(col, 0.16))


def stroke(d, pts, fill, w, seed=3, jit=1.2):
    q = [P(x + _jit(i, seed, jit), y + _jit(i + 50, seed, jit)) for i, (x, y) in enumerate(pts)]
    d.line(q, fill=fill, width=max(1, int(S(lw_(w)))), joint="curve")


def hatch(d, x, y, n, dx, dy, gap, col=INK, w=2.5, seed=4):
    for i in range(n):
        stroke(d, [(x + i * gap, y), (x + i * gap + dx, y + dy)], col, w, seed + i, 0.6)


# ---------- feathers ----------
def feather_pts(length, width, tip=0.0):
    n = 7
    top = [(length * i / n, -width * (math.sin(math.pi * (i / n) ** 0.8) ** 0.8) * (1 - 0.25 * i / n)) for i in range(n + 1)]
    bot = [(length * i / n, width * (math.sin(math.pi * (i / n) ** 0.8) ** 0.8) * (1 - 0.25 * i / n)) for i in range(n, -1, -1)]
    return top + bot


def place(pts, ang, ox, oy):
    return [(ox + x * math.cos(ang) - y * math.sin(ang), oy + x * math.sin(ang) + y * math.cos(ang)) for x, y in pts]


# ---------- characters ----------
PAL = {
    "orrin": dict(body=(120, 78, 48), wing=(84, 54, 34), tipc=(52, 34, 24), belly=(226, 196, 144), scarf=None, tail=(238, 232, 220)),
    "dad": dict(body=(84, 62, 48), wing=(58, 42, 32), tipc=(36, 26, 22), belly=(188, 160, 120), scarf=None, tail=(226, 222, 212)),
    "mom": dict(body=(138, 96, 70), wing=(96, 66, 48), tipc=(60, 42, 32), belly=(236, 210, 170), scarf=(176, 84, 108), tail=(240, 234, 222)),
}


def blink(t):
    return 1.0 if (t % 3.3) < 0.13 else 0.0


def eagle(d, x, y, s=1.0, f=1, flap=(0.0, 0.0, 0.0), eye="open", beak=0.0, belly=1.0, who="orrin",
          brow=(0, 0), look=(0, 0), bob=0.0, tear=0.0, show_legs=True, head=(0, 0), t=0.0, tailsway=0.0, droop=0.0):
    """f=+1 faces right. flap=(phase, amp, rest) : wing raise = rest + amp*sin(phase), tips trail behind the motion.
    head=(dx,dy) moves the head relative to the body (neck stretch / lag)."""
    pal = PAL[who]

    def L(lx, ly):
        return (x + f * lx * s, y + ly * s + bob)

    def LP(pts):
        return [L(*p) for p in pts]

    def LB(cx, cy, rx, ry, col, w, ang, seed):
        px_, py_ = L(cx, cy)
        lit(d, px_, py_, rx * s, ry * s, col, w, ang * f, seed, light=(-0.18 * f, -0.2))

    def feat(base, ang, length, width, col, seed):
        # ang is in local space (facing right); mirror for f=-1 via L()
        loc = place(feather_pts(length, width), ang, *base)
        inked(d, LP(loc), col, 3.2 * s, seed, 1.0)
        # shaft
        tipx, tipy = base[0] + math.cos(ang) * length * 0.85, base[1] + math.sin(ang) * length * 0.85
        stroke(d, [L(*base), L(tipx, tipy)], shade(col, -0.35), 2.2 * s, seed, 0.4)

    phase, amp, rest = flap
    wa = rest + amp * math.sin(phase)
    wv = amp * math.cos(phase)
    flying = amp > 0.05 or rest > 0.35

    def wing(shoulder, wa_, wv_, base_col, tipc, far=False):
        th0 = 2.75 + wa_ * 1.55
        spread = 0.20 + 0.26 * max(0.0, wa_)
        for i in range(8):
            frac = i / 7
            ang = th0 + (i - 3.5) * spread * 0.55 - wv_ * 0.13 * frac - droop * frac * 0.5
            length = 255 - i * 11 + (0 if i < 7 else 0)
            col = mix(tipc, base_col, frac * 0.8)
            feat(shoulder, ang, length, 27, col, 30 + i)
        # coverts
        cx_, cy_ = shoulder[0] - 38 + math.cos(th0) * 14, shoulder[1] + 16 + math.sin(th0) * 14
        LB(cx_, cy_, 86, 64, base_col, 3.6 * s, th0 - 2.6, 60)

    # --- tail ---
    tbase = (-105, 62)
    for i in range(5):
        ang = math.pi - 0.28 + (i - 2) * 0.17 + tailsway * (0.4 + 0.1 * i) - (0.35 if flying else 0.0) * 0.0
        feat(tbase, ang, 190 - abs(i - 2) * 14, 24, pal["tail"] if i % 2 == 0 else shade(pal["tail"], -0.12), 10 + i)
    # --- far wing in flight ---
    sh = (-8, -72)
    if flying:
        wing((sh[0] + 28, sh[1] - 8), rest + amp * math.sin(phase - 0.5) * 0.9, wv * 0.9, shade(pal["wing"], -0.25), shade(pal["tipc"], -0.2), True)
    # --- legs ---
    if show_legs:
        for lx in (-28, 52):
            LB(lx, 116, 52, 62, pal["body"], 3.4 * s, 0.0, 40 + lx)
            stroke(d, [L(lx, 160), L(lx, 214)], INK, 20 * s, 2, 0.3)
            stroke(d, [L(lx, 160), L(lx, 214)], (232, 184, 48), 14 * s, 2, 0.3)
            for tx in (-26, 2, 30):
                stroke(d, [L(lx, 214), L(lx + tx * 0.7, 232), L(lx + tx, 240)], INK, 11 * s, 8, 0.3)
                stroke(d, [L(lx, 214), L(lx + tx * 0.7, 232), L(lx + tx, 240)], (232, 184, 48), 6 * s, 8, 0.3)
    # --- body ---
    LB(0, 0, 152, 168, pal["body"], 4.2 * s, 0.0, 20)
    bw = belly
    LB(30, 42, 100 * bw, 120 * bw, pal["belly"], 3.2 * s, 0.1, 21)
    # chest feather scallops
    for r in range(4):
        for c in range(3):
            sx_, sy_ = 4 + c * 38 + (r % 2) * 18, -10 + r * 36
            stroke(d, [L(sx_, sy_), L(sx_ + 12, sy_ + 14), L(sx_ + 28, sy_)], shade(pal["belly"], -0.3), 2.4 * s, 70 + r * 3 + c, 0.5)
    # --- near wing ---
    wing(sh, wa, wv, pal["wing"], pal["tipc"])
    # --- neck + head ---
    hx, hy = head
    hs = LOOK["head"]
    toon = LOOK["toon"]

    def LH(lx, ly):          # head-local point, scaled about the neck (toon heads are bigger)
        return L(32 + (lx - 32) * hs, -150 + (ly + 150) * hs)

    def LPH(pts):
        return [LH(*p) for p in pts]

    neck = ell_pts(18 + hx * 0.5, -142 + hy * 0.5, 70, 72)
    inked(d, LP(neck), (244, 242, 236), 0, 80)
    # hackle edge on neck
    for i in range(7):
        a0 = 0.15 + i * 0.42
        bxx, byy = 14 + hx * 0.5 + math.cos(a0 + 1.4) * 70, -128 + hy * 0.5 + math.sin(a0 + 1.4) * 40
        inked(d, LP([(bxx - 14, byy), (bxx + 2, byy + 30), (bxx + 14, byy - 4)]), (236, 234, 226), 2.2 * s, 90 + i, 0.6)
    _hx_, _hy_ = LH(32 + hx, -198 + hy)
    lit(d, _hx_, _hy_, 82 * hs * s, 78 * hs * s, (246, 244, 238), 4.2 * s, 0.0, 22, light=(-0.18 * f, -0.2))
    # beak (lower jaw first)
    o = beak * (56 if toon else 40)
    if toon:    # open mouth: red inside, pink tongue, lower jaw swings down
        if o > 4:
            inked(d, LPH([(98 + hx, -166 + hy), (182 + hx, -172 + hy), (190 + hx, -148 + hy + o * 0.6), (100 + hx, -146 + hy + o)]), (200, 40, 60), 0, 123, 0.3)
            tx_, ty_ = LH(138 + hx, -140 + hy + o * 0.75)
            lit(d, tx_, ty_, 28 * hs * s, 13 * hs * s, (255, 130, 150), 0, 0.0, 124, light=(0, -0.3))
        inked(d, LPH([(100 + hx, -152 + hy + o), (150 + hx, -154 + hy + o), (184 + hx, -148 + hy + o * 0.9), (168 + hx, -126 + hy + o),
                      (126 + hx, -120 + hy + o), (100 + hx, -134 + hy + o)]), (232, 170, 30), 3.6 * s, 120, 0.8)
    else:
        inked(d, LP([(100 + hx, -168 + hy), (150 + hx, -170 + hy), (184 + hx, -160 + hy + o * 0.6), (166 + hx, -140 + hy + o),
                     (126 + hx, -134 + hy + o), (100 + hx, -148 + hy + o * 0.5)]), (214, 166, 40), 3.6 * s, 120, 0.8)
    inked(d, LPH([(94 + hx, -218 + hy), (136 + hx, -228 + hy), (178 + hx, -212 + hy), (204 + hx, -178 + hy), (200 + hx, -150 + hy),
                 (190 + hx, -158 + hy), (176 + hx, -172 + hy), (138 + hx, -168 + hy), (100 + hx, -162 + hy)]), (240, 192, 52), 3.8 * s, 121, 0.8)
    inked(d, LPH([(150 + hx, -204 + hy), (160 + hx, -206 + hy), (160 + hx, -196 + hy)]), INK, 0, 122, 0.2)
    # --- eye ---
    ex, ey = 70 + hx, -212 + hy
    lid = {"open": 0.0, "wide": -0.25, "half": 0.5, "closed": 1.0, "spiral": 0.0}[eye]
    if eye in ("open", "half"):
        lid = max(lid, blink(t))
    er = 25 * (1.18 if lid < 0 else 1.0) * LOOK["eye"]
    cxs, cys = LH(ex, ey)
    if lid < 1.0:
        d.ellipse([P(cxs, cys)[0] - S(er * s), P(cxs, cys)[1] - S(er * 0.85 * s), P(cxs, cys)[0] + S(er * s), P(cxs, cys)[1] + S(er * 0.85 * s)],
                  fill=(255, 255, 255) if toon else (250, 246, 226), outline=INK, width=max(1, int(S(lw_(3.6) * s))))
        ix, iy = cxs + look[0] * 6 * f * s, cys + look[1] * 5 * s
        px, py = P(ix, iy)
        if eye == "spiral":       # hypnotised
            pts_sp = []
            for k_ in range(0, 90):
                a_ = k_ * 0.28 + t * 6
                r_ = er * 0.8 * s * (k_ / 90.0)
                pts_sp.append((px + S(r_ * math.cos(a_)), py + S(r_ * 0.85 * math.sin(a_))))
            d.line(pts_sp, fill=(120, 50, 200), width=max(2, int(S(4.5 * s))))
        elif toon:
            r_p = er * 0.40 * s
            px += S(look[0] * er * 0.25 * f * s)
            d.ellipse([px - S(r_p), py - S(r_p), px + S(r_p), py + S(r_p)], fill=(14, 10, 12))
            d.ellipse([px - S(r_p * 0.55), py - S(r_p * 0.75), px + S(r_p * 0.05), py - S(r_p * 0.15)], fill=(255, 255, 255))
        else:
            r_i = er * 0.66 * s
            d.ellipse([px - S(r_i), py - S(r_i), px + S(r_i), py + S(r_i)], fill=(238, 190, 40), outline=INK, width=max(1, int(S(2.4 * s))))
            r_p = er * 0.34 * s
            d.ellipse([px - S(r_p), py - S(r_p), px + S(r_p), py + S(r_p)], fill=(14, 10, 10))
            d.ellipse([px - S(r_p * 0.2) + S(r_p * 0.6), py - S(r_p * 0.9), px + S(r_p * 0.5) + S(r_p * 0.6), py - S(r_p * 0.15)], fill=(255, 255, 255))
    if lid > 0.02:
        pxx, pyy = P(cxs, cys)
        cover = (1.0 if lid >= 1 else lid) * 2 * er * 0.85
        top = pyy - S(er * 0.85 * s)
        bot = top + S(cover * s)
        if toon:      # lid follows the eye's own outline (no boxy patch); closed eye = a happy sleepy arc
            rx_, ry_ = S(er * s), S(er * 0.85 * s)
            poly = [(pxx + rx_ * math.cos(a_ * math.pi / 30), pyy + ry_ * math.sin(a_ * math.pi / 30)) for a_ in range(60)]
            poly = [(x_, min(y_, bot)) for x_, y_ in poly if y_ <= bot + 0.5] if lid < 1 else poly
            lidc = (255, 255, 255)
            if lid >= 1:
                d.polygon(poly, fill=lidc, outline=INK)
                d.arc([pxx - rx_, pyy - ry_ * 0.9, pxx + rx_, pyy + ry_ * 0.9], 20, 160, fill=INK, width=max(2, int(S(lw_(3.6) * s))))
                d.line([(pxx - rx_, pyy), (pxx + rx_, pyy)], fill=lidc, width=1)
            else:
                d.polygon(poly, fill=(236, 232, 222))
                xs_ = math.sqrt(max(0.0, 1 - ((bot - pyy) / ry_) ** 2)) * rx_
                d.line([(pxx - xs_, bot), (pxx + xs_, bot)], fill=INK, width=max(2, int(S(lw_(3.6) * s))))
        else:
            d.rectangle([pxx - S(er * s), top - S(6 * s), pxx + S(er * s), bot], fill=(244, 242, 236))
            d.line([(pxx - S(er * s), bot), (pxx + S(er * s), bot)], fill=INK, width=max(1, int(S(4 * s))))
        if lid >= 1 and who == "mom":
            for k in (-1, 0, 1):
                d.line([(pxx + S(k * 12 * s), bot), (pxx + S(k * 16 * s), bot + S(10 * s))], fill=INK, width=max(1, int(S(3 * s))))
    # brow ridge
    a, b = brow
    stroke(d, [LH(36 + hx, -246 + a + hy), LH(70 + hx, -250 + (a + b) / 2 + hy), LH(112 + hx, -238 + b + hy)], INK, (13 if toon else 16) * s, 5, 0.4)
    if not toon:
        stroke(d, [LH(38 + hx, -248 + a + hy), LH(70 + hx, -252 + (a + b) / 2 + hy), LH(110 + hx, -240 + b + hy)], (206, 188, 128), 7 * s, 5, 0.4)
    if who == "mom":
        stroke(d, [L(56 + hx, -236 + hy), L(46 + hx, -258 + hy)], INK, 4 * s, 6, 0.3)
        stroke(d, [L(74 + hx, -240 + hy), L(70 + hx, -264 + hy)], INK, 4 * s, 7, 0.3)
    if tear > 0:
        tx, ty = L(ex + 6, ey + 24 + tear * 60)
        px, py = P(tx, ty)
        d.ellipse([px - S(8 * s), py - S(13 * s), px + S(8 * s), py + S(13 * s)], fill=(150, 200, 235), outline=INK)
    # scarf
    if pal["scarf"]:
        inked(d, LP([(-48 + hx * 0.4, -118 + hy * 0.3), (86 + hx * 0.4, -126 + hy * 0.3), (92 + hx * 0.4, -92), (-44 + hx * 0.4, -86)]), pal["scarf"], 3.6 * s, 130, 1.0)
        inked(d, LP([(-30, -96), (-6, -96), (-12, -50), (-40, -50)]), shade(pal["scarf"], -0.12), 3.2 * s, 131, 1.0)
        hatch(d, *L(-44, -114), 4, 6 * f * s, 18 * s, 22 * s * f, shade(pal["scarf"], -0.4), 2.4)


def squirrel(d, x, y, s=1.0, f=1, t=0.0, talk=0.0, item=None, look=(0, 0), hat=None, bounce=0.0):
    col = (182, 100, 52)
    belly = (236, 212, 168)

    def L(lx, ly):
        return (x + f * lx * s, y + ly * s + bounce)

    def LB(cx, cy, rx, ry, col, w, ang, seed):
        px_, py_ = L(cx, cy)
        lit(d, px_, py_, rx * s, ry * s, col, w, ang * f, seed, light=(-0.18 * f, -0.2))

    sway = math.sin(t * 3.4) * 0.10
    # bushy tail (jagged fur edge)
    tail = []
    n = 34
    for i in range(n):
        a = 2 * math.pi * i / n
        r = 1.0 + (0.10 if i % 2 else -0.04)
        tail.append((-84 + 46 * r * math.cos(a), -92 + 120 * r * math.sin(a)))
    tail = rot(tail, 0.5 + sway, -84, -32)
    inked(d, [L(*p) for p in tail], shade(col, -0.05), 4 * s, 200, 1.6)
    tin = rot([(-84 + 22 * math.cos(2 * math.pi * i / 22), -92 + 86 * math.sin(2 * math.pi * i / 22)) for i in range(22)], 0.5 + sway, -84, -32)
    d.polygon([P(*L(*p)) for p in tin], fill=(232, 164, 92))
    # feet + body
    inked(d, [L(-20, 70), L(30, 70), L(50, 84), L(-30, 84)], shade(col, -0.1), 3 * s, 201, 0.8)
    LB(0, 0, 60, 80, col, 4 * s, 0.0, 202)
    LB(14, 18, 36, 56, belly, 3 * s, 0.0, 203)
    # ears
    inked(d, [L(-18, -126), L(-30, -184), L(8, -140)], col, 3.6 * s, 204, 0.8)
    inked(d, [L(18, -138), L(36, -192), L(54, -132)], col, 3.6 * s, 205, 0.8)
    inked(d, [L(24, -144), L(36, -178), L(46, -140)], (226, 150, 130), 0, 206, 0.4)
    LB(14, -96, 52, 47, shade(col, 0.04), 4 * s, 0.0, 207)
    LB(36, -80, 28, 21, belly, 3 * s, 0.0, 208)
    inked(d, [L(52, -96), L(64, -92), L(54, -84)], INK, 0, 209, 0.3)
    ex, ey = L(28, -108)
    px, py = P(ex, ey)
    bl = blink(t + 0.7)
    if bl:
        d.line([(px - S(10 * s), py), (px + S(10 * s), py)], fill=INK, width=max(1, int(S(4 * s))))
    else:
        ee = LOOK["eye"]
        d.ellipse([px - S(12 * ee * s), py - S(14 * ee * s), px + S(12 * ee * s), py + S(14 * ee * s)], fill=(255, 255, 250), outline=INK, width=max(1, int(S(lw_(3) * s))))
        d.ellipse([px - S(5 * s) + look[0] * 4 * f, py - S(6 * s) + look[1] * 3, px + S(5 * s) + look[0] * 4 * f, py + S(6 * s) + look[1] * 3], fill=(18, 12, 10))
    stroke(d, [L(14, -128), L(34, -126), L(44, -118)], INK, 5 * s, 210, 0.4)  # brow
    if talk > 0:
        inked(d, [L(40, -66), L(58, -68), L(54, -66 + 20 * talk)], (92, 30, 34), 3 * s, 211, 0.4)
    inked(d, [L(38, -64), L(46, -64), L(44, -50), L(38, -50)], (255, 252, 240), 2.4 * s, 212, 0.3)
    # arm
    LB(30, 14, 16, 30, col, 3 * s, 0.4, 213)
    if hat == "bowler":
        inked(d, [L(-14, -140), L(52, -140), L(50, -176), L(34, -196), L(2, -196), L(-12, -176)], (58, 52, 58), 4 * s, 214, 0.8)
        inked(d, [L(-34, -140), L(70, -140), L(70, -130), L(-34, -130)], (44, 38, 44), 3.6 * s, 215, 0.5)
        inked(d, [L(-8, -150), L(48, -150), L(48, -142), L(-8, -142)], (170, 60, 60), 0, 216, 0.3)
    if item == "popcorn":
        cx_, cy_ = L(52, 30)
        q = [(cx_ - 34 * s, cy_ - 22 * s), (cx_ + 34 * s, cy_ - 22 * s), (cx_ + 24 * s, cy_ + 56 * s), (cx_ - 24 * s, cy_ + 56 * s)]
        d.polygon([P(*p) for p in q], fill=(200, 48, 50))
        for k in range(3):
            d.line([P(cx_ - 14 * s + k * 14 * s, cy_ - 20 * s), P(cx_ - 10 * s + k * 10 * s, cy_ + 54 * s)], fill=(248, 238, 220), width=max(1, int(S(7 * s))))
        d.line([P(*p) for p in q + [q[0]]], fill=INK, width=max(1, int(S(3.4 * s))))
        for ox, oy in [(-20, -36), (0, -46), (20, -34), (-6, -30), (10, -28)]:
            blob(d, cx_ + ox * s, cy_ + oy * s, 15 * s, 13 * s, (255, 242, 200), 2.6 * s, seed=int(ox + 100))


def fish(d, x, y, s=1.0, f=1, ang=0.0):
    body = rot(ell_pts(0, 0, 74, 30, 0, 24), ang)
    inked(d, [(x + f * a * s, y + b * s) for a, b in body], (116, 168, 190), 3.6 * s, 301, 0.8)
    tail = rot([(-62, 0), (-116, -36), (-104, 0), (-116, 36)], ang)
    inked(d, [(x + f * a * s, y + b * s) for a, b in tail], (92, 140, 168), 3.4 * s, 302, 0.8)
    belly = rot(ell_pts(4, 12, 58, 12, 0, 18), ang)
    d.polygon([P(x + f * a * s, y + b * s) for a, b in belly], fill=(226, 224, 210))
    ex, ey = rot([(42, -6)], ang)[0]
    px, py = P(x + f * ex * s, y + ey * s)
    d.ellipse([px - S(6 * s), py - S(6 * s), px + S(6 * s), py + S(6 * s)], fill=INK)


def rabbit(d, x, y, s=1.0):
    lit(d, x, y, 58, 42, (176, 164, 150), 3.6 * s, 0.0, 310)
    lit(d, x + 48 * s, y - 20 * s, 30 * s, 26 * s, (186, 174, 160), 3.4 * s, 0.0, 311)
    for dx, h in ((46, 66), (68, 62)):
        inked(d, [(x + dx * s - 9 * s, y - 38 * s), (x + dx * s, y - 38 * s - h * s), (x + dx * s + 9 * s, y - 38 * s)], (190, 178, 164), 3 * s, 312 + dx, 0.6)
    blob(d, x - 58 * s, y + 4 * s, 15 * s, 15 * s, (246, 244, 240), 3 * s, seed=315)


# ---------- cartoon effects ----------
def puff(d, x, y, s=1.0, t=0.0, col=(255, 226, 240), seed=1):
    """outlined cartoon dust cloud"""
    pts = [(0, 0, 1.0), (-0.9, 0.25, 0.75), (0.85, 0.2, 0.8), (-0.35, -0.65, 0.7), (0.4, -0.6, 0.65), (0.05, 0.55, 0.7)]
    wob = 1 + 0.07 * math.sin(t * 6 + seed)
    col = punch(col)
    for stage in range(3):
        for dx, dy, r in pts:
            R = 50 * s * r * wob
            px, py = P(x + dx * 50 * s, y + dy * 50 * s)
            if stage == 0:
                rr, fl = S(R) + S(lw_(4)), INK
            elif stage == 1:
                rr, fl = S(R), col
            else:
                rr, fl = S(R * 0.45), shade(col, 0.5)
                px, py = px - S(R * 0.22), py - S(R * 0.25)
            d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=fl)


def sparkle(d, x, y, s=1.0, t=0.0, col=(255, 240, 120)):
    r = 40 * s * (0.82 + 0.18 * math.sin(t * 8))
    k = 0.22
    inked(d, [(x, y - r), (x + r * k, y - r * k), (x + r, y), (x + r * k, y + r * k), (x, y + r), (x - r * k, y + r * k), (x - r, y), (x - r * k, y - r * k)],
          col, 3, 5, 0.3)


def speed(d, x, y, dx=1, n=6, s=1.0, t=0.0):
    """motion streaks trailing behind something moving the other way from dx"""
    for i in range(n):
        yy = y + (i - n / 2) * 30 * s
        ln = (120 + (i * 53) % 90) * s * (0.85 + 0.15 * math.sin(t * 9 + i))
        x0 = x + dx * (40 + (i * 29) % 50) * s
        stroke(d, [(x0, yy), (x0 + dx * ln, yy)], INK, 10 * s, 7 + i, 0.3)
        stroke(d, [(x0, yy), (x0 + dx * ln, yy)], (255, 255, 255), 5 * s, 7 + i, 0.3)


# ---------- paper grain + vignette ----------


def grain_overlay():
    if not _grain:
        rng = np.random.default_rng(5)
        n = rng.normal(0, 1, (H // 2, W // 2)).astype("float32")
        im = Image.fromarray(((n * 40) + 128).clip(0, 255).astype("uint8")).filter(ImageFilter.GaussianBlur(0.8)).resize((W, H), Image.BILINEAR)
        n2 = np.asarray(im, dtype="float32") / 255.0 - 0.5
        fib = rng.normal(0, 1, (H // 6, W // 6)).astype("float32")
        fim = Image.fromarray(((fib * 50) + 128).clip(0, 255).astype("uint8")).filter(ImageFilter.GaussianBlur(1.2)).resize((W, H), Image.BICUBIC)
        n3 = np.asarray(fim, dtype="float32") / 255.0 - 0.5
        ys, xs = np.mgrid[0:H, 0:W]
        r = np.sqrt(((xs - W / 2) / (W / 2)) ** 2 + ((ys - H / 2) / (H / 2)) ** 2)
        vig = 1.0 - np.clip((r - 0.7) / 0.9, 0, 1) ** 1.7 * 0.38
        gk = LOOK['grain']
        vig = 1.0 - (1.0 - vig) * (0.55 if LOOK['toon'] else 1.0)
        g = (1.0 + n2 * 0.16 * gk + n3 * 0.12 * gk) * vig
        _grain.append((g * 256).clip(0, 300).astype("uint32")[..., None])
    return _grain[0]


def finish(img):
    arr = np.asarray(img, dtype="uint32")
    out = (arr * grain_overlay()) >> 8
    warm = np.array([258, 254, 244], dtype="uint32")  # faint warm paper tint
    out = (out * warm) >> 8
    im = Image.fromarray(out.clip(0, 255).astype("uint8"))
    if LOOK["toon"]:
        im = ImageEnhance.Color(im).enhance(1.12)
        im = ImageEnhance.Contrast(im).enhance(1.08)
    return im


# ---------- painted parallax world ----------
BX0, BY0, BS = -500, -300, 0.8   # baked world rect origin and scale
BW, BH = int(2200 * BS), int(2600 * BS)


def bp(x, y):
    return ((x - BX0) * BS, (y - BY0) * BS)


def _noise_tex(w, h, seed, scale=6, amp=26):
    rng = np.random.default_rng(seed)
    n = rng.normal(0, 1, (h // scale + 2, w // scale + 2)).astype("float32")
    im = Image.fromarray(((n * 50) + 128).clip(0, 255).astype("uint8")).resize((w, h), Image.BICUBIC)
    return (np.asarray(im, dtype="float32") - 128) / 50.0 * amp


def _tex(img, seed, amp=24, scale=5):
    amp = amp * (0.4 if LOOK["toon"] else 1.0)
    a = np.asarray(img, dtype="float32")
    t = _noise_tex(img.width, img.height, seed, scale, amp)
    a[..., :3] += t[..., None]
    return Image.fromarray(a.clip(0, 255).astype("uint8"), "RGBA")


def _bd(img):
    return ImageDraw.Draw(img)


def _poly(dr, pts, fill, w=0, ink=INK):
    q = [bp(*p) for p in pts]
    dr.polygon(q, fill=fill)
    if w:
        dr.line(q + [q[0]], fill=ink, width=max(1, int(w * BS * 2)))


def _castle(dr, cx, cy, col):
    """a distant storybook castle on its own green mound"""
    mound = [(cx + 340 * math.cos(a), cy + 90 + 130 * math.sin(a) * (1 if math.sin(a) < 0 else 0.4)) for a in np.linspace(math.pi, 2 * math.pi + 0.0001, 18)]
    _poly(dr, mound + [(cx + 340, cy + 230), (cx - 340, cy + 230)], (110, 190, 110), 5)
    wall, roof = shade(col, 0.35), shade(col, -0.25)
    _poly(dr, [(cx - 150, cy - 80), (cx + 150, cy - 80), (cx + 150, cy + 100), (cx - 150, cy + 100)], wall, 5)
    for k in range(7):
        _poly(dr, [(cx - 150 + k * 46, cy - 80), (cx - 150 + k * 46, cy - 104), (cx - 124 + k * 46, cy - 104), (cx - 124 + k * 46, cy - 80)], wall, 4)
    for tx, th, tw in ((-190, 250, 62), (190, 250, 62), (0, 340, 80), (-80, 190, 50), (95, 205, 52)):
        x0, x1 = cx + tx - tw / 2, cx + tx + tw / 2
        top = cy + 100 - th
        _poly(dr, [(x0, cy + 100), (x1, cy + 100), (x1, top), (x0, top)], wall, 5)
        _poly(dr, [(x0 - 14, top), (x1 + 14, top), (cx + tx, top - tw * 1.5)], roof, 5)
        dr.line([bp(cx + tx, top - tw * 1.5), bp(cx + tx, top - tw * 1.5 - 44)], fill=INK + (255,), width=max(2, int(5 * BS)))
        _poly(dr, [(cx + tx, top - tw * 1.5 - 44), (cx + tx + 40, top - tw * 1.5 - 32), (cx + tx, top - tw * 1.5 - 20)], (255, 80, 80), 3)
        _poly(dr, [(cx + tx - 7, top + 50), (cx + tx + 7, top + 50), (cx + tx + 7, top + 84), (cx + tx - 7, top + 84)], (255, 226, 90), 3)
    _poly(dr, [(cx - 36, cy + 100), (cx - 36, cy + 30), (cx, cy), (cx + 36, cy + 30), (cx + 36, cy + 100)], (90, 50, 120), 4)


def bake_world(pal, seed=1):
    """Return list of (depth, RGBA image) layers: sky, far peaks, mid forest hills, near cliff + sea."""
    rng = np.random.default_rng(seed)
    # sky
    sky = Image.new("RGBA", (BW, BH))
    g = np.linspace(0, 1, BH)[:, None, None]
    top = np.array(pal["sky_top"], dtype="float32")
    bot = np.array(pal["sky_bot"], dtype="float32")
    arr = (top + (bot - top) * np.clip((g - 0.1) / 0.7, 0, 1)).repeat(BW, 1)
    sky = Image.fromarray(np.concatenate([arr, np.full((BH, BW, 1), 255, "float32")], 2).astype("uint8"), "RGBA")
    # soft painted clouds
    cl = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
    cd = _bd(cl)
    toon = bool(pal.get("toon"))
    TW = 2.1 if toon else 1.0
    if toon:    # white puffy clouds with thick ink outlines and a blue-grey underside
        r0 = np.random.default_rng(seed + 30)
        for _ in range(pal.get("clouds", 7)):
            cx, cy = r0.uniform(-300, 1500), r0.uniform(120, 900)
            cs = r0.uniform(0.8, 1.3)
            circ = [(cx + dx * cs, cy + dy * cs, r * cs) for dx, dy, r in [(-110, 18, 50), (-45, -8, 72), (35, -22, 82), (110, 6, 64), (165, 26, 44), (0, 36, 60)]]
            for cx_, cy_, r in circ:
                x0, y0 = bp(cx_ - r - 6, cy_ - r - 6)
                x1, y1 = bp(cx_ + r + 6, cy_ + r + 6)
                sky_d = _bd(sky)
                sky_d.ellipse([x0, y0, x1, y1], fill=INK + (255,))
            for cx_, cy_, r in circ:
                x0, y0 = bp(cx_ - r, cy_ - r)
                x1, y1 = bp(cx_ + r, cy_ + r)
                sky_d.ellipse([x0, y0, x1, y1], fill=pal["cloud"] + (255,))
                x0, y0 = bp(cx_ - r * 0.7, cy_ + r * 0.1)
                x1, y1 = bp(cx_ + r * 0.7, cy_ + r * 0.8)
                sky_d.ellipse([x0, y0, x1, y1], fill=shade(pal["cloud"], -0.1) + (255,))
    for _ in range(0 if toon else pal.get("clouds", 7)):
        cx, cy = rng.uniform(-300, 1500), rng.uniform(100, 900)
        for _k in range(6):
            ox, oy = rng.uniform(-150, 150), rng.uniform(-30, 30)
            r = rng.uniform(60, 130)
            x0, y0 = bp(cx + ox - r, cy + oy - r * 0.45)
            x1, y1 = bp(cx + ox + r, cy + oy + r * 0.45)
            cd.ellipse([x0, y0, x1, y1], fill=pal["cloud"] + (150,))
    cl = cl.filter(ImageFilter.GaussianBlur(7))
    sky.alpha_composite(cl)
    if pal.get("stars") and toon:
        sd = _bd(sky)
        for _ in range(46):
            sx_, sy_ = rng.uniform(-400, 1500), rng.uniform(-200, 800)
            r_ = rng.uniform(8, 22)
            sd.polygon([bp(sx_, sy_ - r_), bp(sx_ + r_ * 0.22, sy_ - r_ * 0.22), bp(sx_ + r_, sy_), bp(sx_ + r_ * 0.22, sy_ + r_ * 0.22),
                        bp(sx_, sy_ + r_), bp(sx_ - r_ * 0.22, sy_ + r_ * 0.22), bp(sx_ - r_, sy_), bp(sx_ - r_ * 0.22, sy_ - r_ * 0.22)],
                       fill=(255, 246, 170, 255))
    elif pal.get("stars"):
        sd = _bd(sky)
        for _ in range(140):
            x, y = bp(rng.uniform(-400, 1500), rng.uniform(-200, 900))
            r = rng.uniform(0.6, 1.8)
            sd.ellipse([x - r, y - r, x + r, y + r], fill=(235, 238, 255, int(rng.uniform(120, 255))))
    # glow of the light source (sun / moon halo)
    gl = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
    gd = _bd(gl)
    gx, gy = pal["glow"]
    for k in range(9, 0, -1):
        r = k * 70
        x0, y0 = bp(gx - r, gy - r)
        x1, y1 = bp(gx + r, gy + r)
        gd.ellipse([x0, y0, x1, y1], fill=pal["glow_col"] + (int(10 + (9 - k) * 3),))
    sky.alpha_composite(gl.filter(ImageFilter.GaussianBlur(10)))
    if pal.get("disc"):
        col, rad, cres = pal["disc"]
        dd_ = _bd(sky)
        if toon and pal.get("disc_style") == "rays":
            for k_ in range(16):
                a_ = k_ * math.pi * 2 / 16
                a2 = a_ + math.pi / 16
                _poly(dd_, [(gx + rad * 1.05 * math.cos(a_ - 0.12), gy + rad * 1.05 * math.sin(a_ - 0.12)),
                            (gx + rad * 1.55 * math.cos(a2), gy + rad * 1.55 * math.sin(a2)),
                            (gx + rad * 1.05 * math.cos(a_ + 0.2), gy + rad * 1.05 * math.sin(a_ + 0.2))], (255, 190, 50), 5)
        x0, y0 = bp(gx - rad, gy - rad)
        x1, y1 = bp(gx + rad, gy + rad)
        dd_.ellipse([x0, y0, x1, y1], fill=col + (255,), outline=INK + (255,), width=8 if toon else 3)
        if toon and pal.get("disc_style") == "craters":
            for cdx, cdy, cr in ((-0.35, -0.3, 0.2), (0.3, -0.45, 0.14), (0.35, 0.15, 0.24), (-0.25, 0.4, 0.16), (0.0, 0.0, 0.1)):
                a0, b0 = bp(gx + cdx * rad - cr * rad, gy + cdy * rad - cr * rad)
                a1, b1 = bp(gx + cdx * rad + cr * rad, gy + cdy * rad + cr * rad)
                dd_.ellipse([a0, b0, a1, b1], fill=shade(col, -0.16) + (255,), outline=INK + (255,), width=4)
        if cres:
            ox0, oy0 = bp(gx - rad + rad * 0.55, gy - rad - rad * 0.1)
            ox1, oy1 = bp(gx + rad + rad * 0.55, gy + rad - rad * 0.1)
            top_c = tuple(int(v) for v in sky.getpixel((int(bp(gx, gy)[0]), int(bp(gx, gy)[1] - rad * BS * 1.1))))[:3]
            dd_.ellipse([ox0, oy0, ox1, oy1], fill=top_c + (255,))
    sky = _tex(sky, seed + 1, 4, 10)

    def ridge(base_y, amp, cols, depth_seed, ink_w, n=14):
        im = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
        dr = _bd(im)
        r2 = np.random.default_rng(depth_seed)
        xs = np.linspace(-500, 1700, n)
        ys = [base_y - r2.uniform(0.2, 1.0) * amp for _ in xs]
        pts = list(zip(xs, ys)) + [(1700, 2300), (-500, 2300)]
        _poly(dr, pts, cols, ink_w)
        # hatch shading on the slopes
        for i in range(len(xs) - 1):
            if i % 2 == 0:
                x0, y0 = xs[i], ys[i]
                for k in range(4):
                    q0 = bp(x0 + 20 + k * 18, y0 + 26 + k * 12)
                    q1 = bp(x0 + 50 + k * 18, y0 + 96 + k * 12)
                    dr.line([q0, q1], fill=shade(cols, -0.22) + (255,), width=max(1, int(2 * BS * 2)))
        return im

    far = _tex(ridge(1060, 520, pal["far"], seed + 2, 2.5 * TW), seed + 3, 5, 8)
    if pal.get("castle"):
        _castle(_bd(far), pal["castle"][0], pal["castle"][1], pal["far"])
    mist = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
    md = _bd(mist)
    for k in range(8):
        y0 = 1060 + k * 26
        x0, y0b = bp(-500, y0)
        x1, y1 = bp(1700, y0 + 60)
        md.rectangle([x0, y0b, x1, y1], fill=pal["mist"] + (int(26 - k * 2.5),))
    far.alpha_composite(mist.filter(ImageFilter.GaussianBlur(6)))

    mid = ridge(1260, 330, pal["mid"], seed + 4, 2.8 * TW, 10)
    md = _bd(mid)
    r3 = np.random.default_rng(seed + 5)
    for _ in range(46 if toon else 70):  # conifers (toon: round "lollipop" trees)
        tx = r3.uniform(-420, 1620)
        ty = 1260 + r3.uniform(-170, 60)
        h = r3.uniform(60, 120)
        if toon:
            _poly(md, [(tx - 6, ty), (tx + 6, ty), (tx + 5, ty - h * 0.55), (tx - 5, ty - h * 0.55)], (120, 70, 60), 4)
            can = [(tx + h * 0.5 * math.cos(a), ty - h * 0.85 + h * 0.46 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 18, endpoint=False)]
            _poly(md, can, shade(pal["tree"], r3.uniform(-0.12, 0.12)), 5)
        else:
            _poly(md, [(tx - h * 0.26, ty), (tx, ty - h), (tx + h * 0.26, ty)], shade(pal["tree"], r3.uniform(-0.1, 0.1)), 1.6)
    mid = _tex(mid, seed + 6, 6, 7)

    # near: sea + cliff
    near = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
    nd = _bd(near)
    _poly(nd, [(560, 1430), (2000, 1400), (2000, 2500), (560, 2500)], pal["sea"], 0)
    for k in range(14):
        yy = 1470 + k * 56
        _poly(nd, [(560, yy), (2000, yy), (2000, yy + 6), (560, yy + 6)], shade(pal["sea"], 0.10 - 0.012 * k), 0)
    rock = pal["rock"]
    cliff = [(-600, 1245), (120, 1232), (520, 1244), (690, 1290), (706, 1330), (640, 1500), (700, 1640), (760, 1760), (720, 1900), (680, 2500), (-600, 2500)]
    _poly(nd, cliff, rock, 4.5 * TW)
    # strata + cracks
    for k in range(9):
        y0 = 1330 + k * 120
        pts = [(-500 + j * 150, y0 + math.sin(j * 1.7 + k) * 22 + j * 3) for j in range(8)]
        nd.line([bp(*p) for p in pts], fill=shade(rock, -0.28) + (255,), width=max(1, int(3 * BS * 2)))
    for k in range(10):
        x0 = -400 + k * 110
        y0 = 1380 + (k * 53) % 300
        nd.line([bp(x0, y0), bp(x0 + 18, y0 + 50), bp(x0 - 8, y0 + 100)], fill=INK + (255,), width=max(1, int(3 * BS * 2)))
    near = _tex(near, seed + 7, 9, 6)
    nd = _bd(near)
    # grass lip + blades
    lip = [(-600, 1240), (120, 1226), (520, 1238), (690, 1284), (694, 1306), (520, 1262), (120, 1258), (-600, 1268)]
    _poly(nd, lip, pal["grass"], 3.2 * TW)
    r4 = np.random.default_rng(seed + 8)
    for xx in np.arange(-560, 690, 14):
        yy = 1242 - (xx - 120) ** 2 / 4e5 * 0 + (0 if xx < 520 else (xx - 520) * 0.27)
        hgt = r4.uniform(16, 40)
        lean = r4.uniform(-12, 12)
        _poly(nd, [(xx, yy + 12), (xx + lean, yy - hgt), (xx + 9, yy + 12)], shade(pal["grass"], r4.uniform(-0.15, 0.15)), 1.2)
    # boulders & bushes at the cliff foot
    for bx_, by_, br in [(-300, 1500, 90), (60, 1720, 120), (420, 1880, 100), (-120, 1960, 150)]:
        pts = [(bx_ + br * math.cos(a) * (1 + 0.12 * math.sin(3 * a + bx_)), by_ + br * 0.62 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 22, endpoint=False)]
        _poly(nd, pts, shade(rock, 0.06), 3.4 * TW)
        hatch_pts = [(bx_ - br * 0.4 + k * 16, by_ + br * 0.05) for k in range(5)]
        for hx_, hy_ in hatch_pts:
            nd.line([bp(hx_, hy_), bp(hx_ + 10, hy_ + br * 0.4)], fill=shade(rock, -0.4) + (255,), width=max(1, int(2 * BS * 2)))
    return [(0.12, sky), (0.35, far), (0.62, mid), (1.0, near)]


def composite_world(img, layers):
    for depth, lay in layers:
        zz = 1.0 + (C.z - 1.0) * depth
        cx = W / 2 + (C.cx - W / 2) * depth
        cy = H / 2 + (C.cy - H / 2) * depth
        vw, vh = W / zz, H / zz
        x0, y0 = cx - vw / 2, cy - vh / 2
        box = ((x0 - BX0) * BS, (y0 - BY0) * BS, (x0 + vw - BX0) * BS, (y0 + vh - BY0) * BS)
        res = lay.resize((W, H), Image.BILINEAR, box=box)
        img.paste(res, (0, 0), res)


# ---------- parchment pop-ups & captions ----------
_pop_cache = {}


def _bubble(text, size, bg, fg, tail, shape="card"):
    key = (text, size, bg, fg, tail, shape, LOOK["toon"])
    if key in _pop_cache:
        return _pop_cache[key]
    fnt = tfont(size)
    if LOOK["toon"] and shape in ("bubble", "burst"):
        dd = ImageDraw.Draw(Image.new("RGB", (4, 4)))
        bb = dd.textbbox((0, 0), text, font=fnt)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        if shape == "burst":
            rx, ry = tw / 2 + 52, th / 2 + 44
            img = Image.new("RGBA", (int(rx * 2 + 30), int(ry * 2 + 30)), (0, 0, 0, 0))
            g = ImageDraw.Draw(img)
            cx_, cy_ = img.width / 2, img.height / 2
            n = 14
            pts = []
            for k in range(n * 2):
                a = math.pi * k / n
                rr = 1.0 if k % 2 == 0 else 0.74
                pts.append((cx_ + rx * rr * math.cos(a), cy_ + ry * rr * math.sin(a)))
            g.polygon(pts, fill=INK)
            g.polygon([(cx_ + (x - cx_) * 0.93, cy_ + (y - cy_) * 0.9) for x, y in pts], fill=(255, 226, 70))
            g.text((cx_ - tw / 2 - bb[0], cy_ - th / 2 - bb[1]), text, font=fnt, fill=(214, 40, 60), stroke_width=2, stroke_fill=(255, 255, 255))
        else:
            pad = 30
            bw, bh = tw + 2 * pad + 20, th + 2 * pad
            img = Image.new("RGBA", (bw + 30, bh + 84), (0, 0, 0, 0))
            g = ImageDraw.Draw(img)
            g.ellipse([8, 8, bw + 20, bh + 8], fill=bg, outline=INK, width=9)
            if tail:
                cxm = (bw + 30) // 2
                g.polygon([(cxm - 24, bh - 6), (cxm + 24, bh - 6), (cxm + tail * 2, bh + 70)], fill=bg)
                g.line([(cxm - 22, bh - 4), (cxm + tail * 2, bh + 70), (cxm + 22, bh - 4)], fill=INK, width=9)
                g.line([(cxm - 18, bh - 4), (cxm + 18, bh - 4)], fill=bg, width=12)
            g.text((8 + pad + 10 - bb[0], 8 + pad - bb[1]), text, font=fnt, fill=fg)
        _pop_cache[key] = img
        return img
    dd = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    bb = dd.textbbox((0, 0), text, font=fnt)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    pad = 30
    bw, bh = tw + 2 * pad, th + 2 * pad
    img = Image.new("RGBA", (bw + 24, bh + 76), (0, 0, 0, 0))
    g = ImageDraw.Draw(img)
    g.rounded_rectangle([10, 10, bw + 10, bh + 10], radius=14, fill=bg, outline=INK, width=6)
    g.rounded_rectangle([20, 20, bw, bh], radius=8, outline=shade(INK, 0.35), width=2)
    if tail:
        cxm = (bw + 20) // 2
        g.polygon([(cxm - 20, bh + 6), (cxm + 20, bh + 6), (cxm + tail, bh + 64)], fill=bg)
        g.line([(cxm - 20, bh + 8), (cxm + tail, bh + 64), (cxm + 20, bh + 8)], fill=INK, width=6)
        g.line([(cxm - 16, bh + 8), (cxm + 16, bh + 8)], fill=bg, width=9)
    g.text((10 + pad - bb[0], 10 + pad - bb[1]), text, font=fnt, fill=fg)
    _pop_cache[key] = img
    return img


def popup(img, text, x, y, u, start, dur=2.0, size=52, bg=(240, 226, 190), fg=(52, 32, 24), tail=0, shake=0.0, shape=None):
    k = u - start
    if k < 0 or k > dur:
        return
    sc = back(k / 0.32)
    if k > dur - 0.22:
        sc *= max(0.0, (dur - k) / 0.22)
    if sc <= 0.02:
        return
    if LOOK["toon"]:
        shape = shape or "bubble"
        if bg == (240, 226, 190):
            bg = (255, 255, 255)
        if fg == (52, 32, 24):
            fg = INK
    b = _bubble(text, size, bg, fg, tail, shape or "card")
    sw, sh = max(1, int(b.width * sc * C.z)), max(1, int(b.height * sc * C.z))
    b2 = b.resize((sw, sh), Image.BILINEAR)
    px, py = P(x, y)
    px += math.sin(u * 60) * shake
    py += math.cos(u * 47) * shake * 0.6
    img.paste(b2, (int(px - sw / 2), int(py - sh / 2)), b2)


def captions(img, text, u, D, y=1600, size=60, lead=0.25, tail=0.35):
    words = text.split()
    fnt = tfont(size)
    d = ImageDraw.Draw(img)
    maxw = W - 150
    space = d.textlength(" ", font=fnt)
    lines, cur, curw = [], [], 0
    for w in words:
        ww = d.textlength(w, font=fnt)
        if cur and curw + space + ww > maxw:
            lines.append(cur)
            cur, curw = [], 0
        cur.append((w, ww))
        curw += (space if len(cur) > 1 else 0) + ww
    lines.append(cur)
    total = sum(len(w) + 1 for w in words)
    t0, t1 = lead, D - tail
    acc, active = 0, 0
    for i, w in enumerate(words):
        if u >= t0 + (t1 - t0) * acc / total:
            active = i
        acc += len(w) + 1
    lh = size * 1.34
    yy = y - (len(lines) - 1) * lh / 2
    idx = 0
    for ln in lines:
        lw = sum(w for _, w in ln) + space * (len(ln) - 1)
        xx = (W - lw) / 2
        for w, ww in ln:
            col = (255, 220, 120) if idx == active and u >= t0 else (250, 244, 228)
            if LOOK["toon"]:
                col = (255, 214, 30) if idx == active and u >= t0 else (255, 255, 255)
            d.text((xx, yy), w, font=fnt, fill=col, stroke_width=9 if LOOK["toon"] else 7, stroke_fill=(30, 20, 18))
            xx += ww + space
            idx += 1
        yy += lh
