"""Data-driven puppet scenes: a scene written as JSON is drawn frame by frame.

Anything that changes over time is a *channel*:
    3.5                                     constant
    {"kf": [[t, v], ...]}                   smooth (eased) keyframes
    {"lin": [[t, v], ...]}                  straight-line keyframes
    {"step": [[t, v], ...]}                 jumps to v at time t (use for eye, brow, flap, legs ...)
    {"base": b, "sin": {...}}               add a wobble: {"amp","rate","phase","base","fn":"sin|cos","from","to"}
Every time can be a number (seconds into the scene) or "@some words" = the moment the narrator says those words,
optionally with an offset: "@He flew+1.5" or "@Mom, Dad-0.3". "@end" is the end of the scene.
"""
import math
import re

from PIL import Image, ImageDraw

from . import engine as E
from .engine import C, W, H, ease, inked, stroke, blob, lit, shade, INK, rot, font

TIME_RE = re.compile(r"^@(.*?)([+-]\d+(?:\.\d+)?)?$")


def rgb(c, default=(255, 255, 255)):
    if c is None:
        return default
    if isinstance(c, str):
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(c)


class Clock:
    """Resolves times for one scene."""

    def __init__(self, nt, D):
        self.nt, self.D = nt, D

    def t(self, x):
        if x is None:
            return None
        if isinstance(x, str):
            m = TIME_RE.match(x)
            if not m:
                raise ValueError(f"bad time {x!r}")
            phrase, off = m.group(1), float(m.group(2) or 0)
            base = self.D if phrase == "end" else self.nt(phrase)
            return base + off
        return float(x)


def _lerp(a, b, k):
    if isinstance(a, (list, tuple)):
        return [_lerp(x, y, k) for x, y in zip(a, b)]
    return a + (b - a) * k


def _kf(pts, u, smooth):
    if u <= pts[0][0]:
        return pts[0][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if u <= t1:
            k = (u - t0) / (t1 - t0) if t1 > t0 else 1.0
            return _lerp(v0, v1, ease(k) if smooth else k)
    return pts[-1][1]


def ev(spec, u, clk, default=None):
    if spec is None:
        return default
    if not isinstance(spec, dict):
        return spec
    val = spec.get("base")
    for key, smooth in (("kf", True), ("lin", False)):
        if key in spec:
            pts = sorted(([clk.t(t), v] for t, v in spec[key]), key=lambda p: p[0])
            val = _kf(pts, u, smooth)
    if "step" in spec:
        pts = sorted(([clk.t(t), v] for t, v in spec["step"]), key=lambda p: p[0])
        val = pts[0][1]
        for t, v in pts:
            if u >= t:
                val = v
    sn = spec.get("sin")
    if sn is not None:
        t0, t1 = clk.t(sn.get("from")), clk.t(sn.get("to"))
        if (t0 is None or u >= t0) and (t1 is None or u < t1):
            fn = math.cos if sn.get("fn") == "cos" else math.sin
            add = sn.get("base", 0.0) + sn["amp"] * fn(u * sn["rate"] + sn.get("phase", 0.0))
            val = (0.0 if val is None else val) + add
    return default if val is None else val


# ---------------- props ----------------
def ledge_y(s):
    return 1240 - 240 * s


def draw_nest(d, th, u):
    dim = th.get("dim", 1.0)
    col = shade((136, 98, 58), -(1 - dim) * 0.6)
    blob(d, 330, 1236, 220, 40, col, 4.2, seed=40)
    for i in range(26):
        a = i * 0.77
        x0 = 130 + i * 15
        stroke(d, [(x0, 1232), (x0 + 22 + math.sin(a) * 14, 1214 + math.cos(a) * 8)], shade(col, -0.35), 6, 41 + i, 1.0)
    blob(d, 330, 1232, 170, 24, shade(col, 0.12), 0, seed=42)
    if th.get("empty"):
        stroke(d, [(270, 1228), (318, 1208), (330, 1210)], (232, 214, 170), 6, 43)


def draw_tree(d, th, u):
    bx, by, top = th["x"], th.get("base", 1285), th["top"]
    sw = math.sin(u * 1.4) * 5
    inked(d, [(bx - 46, by), (bx + 48, by), (bx + 30, top + 120), (bx + 10, top), (bx - 14, top + 10), (bx - 30, top + 140)],
          (104, 74, 50), 4.4, 50, 1.4)
    for k in range(6):
        stroke(d, [(bx - 24 + k * 10, by - 20), (bx - 18 + k * 9, top + 180 + k * 30)], (70, 48, 34), 3, 51 + k, 1.0)
    for cx_, cy_, rx, ry, c in [(bx - 30, top - 10, 190, 130, (56, 112, 70)), (bx + 60, top - 60, 170, 120, (64, 126, 76)),
                                (bx - 120, top + 50, 130, 90, (50, 100, 64)), (bx + 20, top + 20, 150, 100, (72, 138, 84))]:
        lit(d, cx_ + sw, cy_, rx, ry, c, 4.2, 0.0, int(cx_ + 7), 36, (-0.2, -0.25))


def draw_pole(d, th, u):
    x, top, base = th["x"], th["top"], th.get("base", 1500)
    inked(d, [(x - 12, top), (x + 12, top), (x + 14, base), (x - 14, base)], (108, 78, 54), 3.6, int(x), 1.0)


def draw_net(d, th, u, sag):
    x0, y0, x1, y1 = th["x0"], th["y0"], th["x1"], th["y1"]
    col = rgb(th.get("color"), (214, 192, 128))
    cols, rows = 9, 6
    for r in range(rows + 1):
        pts = [(x0 + (x1 - x0) * c / cols, y0 + (y1 - y0) * r / rows + math.sin(c / cols * math.pi) * sag) for c in range(cols + 1)]
        stroke(d, pts, INK, 8, 60 + r, 0.8)
        stroke(d, pts, col, 4.5, 60 + r, 0.8)
    for c in range(cols + 1):
        pts = [(x0 + (x1 - x0) * c / cols, y0 + (y1 - y0) * r / rows + math.sin(c / cols * math.pi) * sag) for r in range(rows + 1)]
        stroke(d, pts, INK, 8, 80 + c, 0.8)
        stroke(d, pts, col, 4.5, 80 + c, 0.8)


def draw_sign(d, th, u, clk):
    sw = ev(th.get("swing"), u, clk, 0.0)
    hw, hh, sx = th.get("hw", 140), th.get("hh", 56), th.get("sx", 1.0)
    pts = rot([(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)], sw, 0, -hh)
    inked(d, [(th["cx"] + a * sx, th["cy"] + b) for a, b in pts], rgb(th.get("fill"), (236, 214, 150)), 4.4, 73, 1.0)


# ---------------- scene ----------------
def draw_scene(img, sc, u, D, ctx):
    """ctx: .worlds (baked), .nt(scene_index, phrase), .script"""
    clk = Clock(lambda ph: ctx.nt(sc["_i"], ph), D)
    cam = sc.get("camera", {})
    C.cx, C.cy, C.z = ev(cam.get("x"), u, clk, 540), ev(cam.get("y"), u, clk, 960), ev(cam.get("z"), u, clk, 1.0)
    E.composite_world(img, ctx.worlds[sc["world"]])
    d = ImageDraw.Draw(img)
    fz = clk.t(sc.get("freeze"))
    uu = u if fz is None else min(u, fz)
    pos = {}
    for th in sc.get("things", []):
        _thing(d, th, uu, clk, pos)
    for p in sc.get("popups", []):
        _popup(img, p, u, clk)
    if sc.get("end_card"):
        _end_card(img, u, D, ctx.script)


def _shown(th, u, clk):
    sh = th.get("show")
    if not sh:
        return True
    t0, t1 = clk.t(sh[0]), (clk.t(sh[1]) if len(sh) > 1 else None)
    return u >= t0 and (t1 is None or u < t1)


def _thing(d, th, u, clk, pos):
    if not _shown(th, u, clk):
        return
    g = lambda k, dflt=None: ev(th.get(k), u, clk, dflt)
    typ = th["type"]
    if typ == "nest":
        return draw_nest(d, th, u)
    if typ == "tree":
        return draw_tree(d, th, u)
    if typ == "pole":
        return draw_pole(d, th, u)
    if typ == "net":
        return draw_net(d, th, u, g("sag", 55))
    if typ == "sign":
        return draw_sign(d, th, u, clk)
    if typ == "poly":
        return inked(d, [tuple(p) for p in th["pts"]], rgb(th.get("fill")), th.get("w", 4), th.get("seed", 70), th.get("jit", 1.2))
    if typ == "line":
        return stroke(d, [tuple(p) for p in th["pts"]], rgb(th.get("color"), INK), th.get("w", 4), th.get("seed", 71))

    s = g("scale", 1.0)
    x = g("x", 0.0)
    y = g("y")
    if y is None:
        y = ledge_y(s) if typ == "eagle" else (1240 - 84 * s if typ in ("squirrel", "cat", "fox", "rabbit") else (1240.0 if typ == "human" else 0.0))
    if "attach" in th:        # follow another thing: {"to": id, "dx": .., "dy": ..}
        a = th["attach"]
        px, py = pos[a["to"]]
        x, y = px + a.get("dx", 0), py + a.get("dy", 0)
    if th.get("id"):
        pos[th["id"]] = (x, y)
    face = th.get("face", 1)
    t = u + th.get("t_offset", 0.0)
    if typ == "eagle":
        fl = g("flap", {}) or {}
        flap = (u * fl.get("rate", 0.0), fl.get("amp", 0.0), fl.get("rest", -0.3))
        head = g("head", [0, 0])
        E.eagle(d, x, y, s, face, flap=flap, eye=g("eye", "open"), beak=g("beak", 0.0), belly=g("belly", 1.0), who=th.get("who", "orrin"),
                brow=tuple(g("brow", [0, 0])), look=tuple(g("look", [0, 0])), bob=g("bob", 0.0), tear=g("tear", 0.0),
                show_legs=bool(g("legs", True)), head=(g("head_dx", head[0]), g("head_dy", head[1])), t=t,
                tailsway=g("tailsway", 0.0), droop=g("droop", 0.0))
    elif typ == "squirrel":
        E.squirrel(d, x, y, s, face, t, talk=g("talk", 0.0), item=th.get("item"), look=tuple(g("look", [0, 0])), hat=th.get("hat"),
                   bounce=g("bounce", 0.0))
    elif typ == "fish":
        E.fish(d, x, y, s, face, g("ang", 0.0))
    elif typ in ("cat", "fox", "rabbit"):
        E.critter(d, x, y, s, face, t, kind=typ, coat=th.get("coat"), talk=g("talk", 0.0), eye=g("eye", "open"), brow=tuple(g("brow", [0, 0])),
                  tear=g("tear", 0.0), look=tuple(g("look", [0, 0])), hat=th.get("hat"), bounce=g("bounce", 0.0), mood=th.get("mood", "neutral"))
    elif typ == "human":
        from . import people
        # how fast is this person travelling? walking speed drives the legs, and the gait follows the ground covered
        gx = lambda u_: ev(th.get("x"), u_, clk, 0.0)
        step_ = 0.06
        dx_ = (gx(u) - gx(u - step_)) / step_ if u > step_ else 0.0
        vx = abs(dx_)
        walk = min(1.0, 0.45 + vx / 150.0) if vx > 8 else 0.0
        if walk > 0.12:                         # a person who is walking faces the way they are going (never crab-walks or backs away)
            face = 1 if dx_ > 0 else -1
        gait = u * 8.0 if walk > 0.02 else 0.0           # a steady cadence: about one stride every 0.8 s
        people.person(d, x, y, s, face, t, role=th.get("role", "stranger"), gender=th.get("gender", "male"), age=th.get("age", "adult"), skin=th.get("skin", "fair"),
                      hair=th.get("hair", "brown"), extras=tuple(th.get("extras") or ()), talk=g("talk", 0.0), eye=g("eye", "open"), brow=tuple(g("brow", [0, 0])),
                      tear=g("tear", 0.0), look=tuple(g("look", [0, 0])), action=g("action", "stand"), mood=g("mood", "neutral"),
                      bounce=g("bounce", 0.0), carry=th.get("carry"), seed=th.get("seed", 0), walk=walk, gait=gait)
    elif typ == "puff":
        E.puff(d, x, y, s, t, rgb(th.get("color"), (255, 226, 240)), th.get("seed", 1))
    elif typ == "sparkle":
        E.sparkle(d, x, y, s, t, rgb(th.get("color"), (255, 240, 120)))
    elif typ == "speed":
        E.speed(d, x, y, th.get("dx", 1), th.get("n", 6), s, t)
    else:
        raise ValueError(f"unknown thing type {typ!r}")


def _popup(img, p, u, clk):
    at = clk.t(p["at"])
    until = clk.t(p.get("until"))
    if until is not None and u > until:
        return
    k = u - at
    x, y = p["x"], p["y"]
    dr = p.get("drift")
    if dr and k > 0:
        x, y = x + dr[0] * k, y + dr[1] * k
    wb = p.get("wobble")
    if wb and k > 0:
        x += math.sin(k * wb["rate"]) * wb["amp"]
    kw = {}
    if p.get("bg"):
        kw["bg"] = rgb(p["bg"])
    if p.get("fg"):
        kw["fg"] = rgb(p["fg"])
    E.popup(img, p["text"], x, y, u, at, p.get("dur", 2.0), size=p.get("size", 52), tail=p.get("tail", 0), shake=p.get("shake", 0.0), shape=p.get("shape"), **kw)


END_SEC = 3.5      # how long the simple end screen (name + tagline) stays up, then a soft fade to black


def _end_card(img, u, D, script):
    t0 = D - END_SEC
    if u <= t0:
        return
    k_bg = ease((u - t0) / 0.9)
    ov = ImageDraw.Draw(img, "RGBA")
    ov.rectangle([0, 0, W, H], fill=(24, 16, 30, int(215 * k_bg)))
    fx = E.tfont if E.LOOK.get("toon") else font
    f1, f2, f3, f4 = fx(112), fx(38), fx(66), fx(44)

    def alpha(delay):
        return ease(max(0.0, min(1.0, (u - t0 - delay) / 0.6)))

    def layer(k, draw_fn):
        """draw on a transparent layer, fade the whole layer by k, paste it (text alpha is not honoured when drawing straight on RGB)"""
        if k <= 0.003:
            return
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw_fn(ImageDraw.Draw(lay))
        al = lay.getchannel("A").point(lambda v, k=k: int(v * k))
        lay.putalpha(al)
        img.paste(lay, (0, 0), lay)

    def centre(text, y, f, col, delay, a=255):
        k = alpha(delay)
        rise = (1 - k) * 18                      # each line settles upward as it fades in
        layer(k * a / 255, lambda d: d.text(((W - d.textlength(text, font=f)) / 2, y + rise), text, font=f, fill=col + (255,)))

    centre("tidalfolio", 640, f1, (250, 240, 220), 0.4)
    centre(script.get("tagline") or ("Funny people. Wild moments. Endless smiles." if "human" in script.get("cast_species", []) else "Funny animals. Wild moments. Endless smiles."), 790, f2, (255, 214, 120), 0.8)

