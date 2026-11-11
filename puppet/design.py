"""Generated characters and props.

The story writer is not limited to the built-in roles and objects. For every story it can DESIGN
  - each character: build, height, hair style and colour, skin, clothes, colours, hat, accessories, signature object
  - any object the story needs: a short recipe of coloured shapes (a lantern, a kite, a guitar, a campfire ...)
and the engine draws exactly what was described. Everything the writer sends is cleaned here first: unknown words are dropped,
numbers are clamped and colours are parsed, so a bad design can never crash a render or draw something outside the picture.
"""
import re

HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")
NAMES = {"red": (214, 64, 72), "crimson": (190, 40, 70), "orange": (248, 148, 52), "yellow": (250, 210, 70), "gold": (240, 190, 60), "green": (80, 176, 104),
         "olive": (130, 150, 70), "teal": (60, 168, 170), "turquoise": (70, 200, 200), "blue": (70, 120, 210), "navy": (40, 56, 110), "sky": (130, 190, 240),
         "purple": (140, 90, 190), "violet": (150, 110, 220), "lavender": (190, 170, 235), "pink": (244, 140, 176), "magenta": (210, 70, 150), "brown": (130, 88, 60),
         "tan": (214, 180, 132), "beige": (232, 214, 182), "cream": (250, 242, 222), "white": (250, 250, 250), "grey": (150, 152, 166), "gray": (150, 152, 166),
         "charcoal": (62, 62, 76), "black": (36, 34, 44), "maroon": (120, 40, 60), "mint": (160, 224, 190), "coral": (250, 120, 110), "peach": (252, 190, 150),
         "mustard": (216, 170, 50), "rust": (184, 90, 50), "khaki": (190, 176, 120), "silver": (196, 200, 214), "copper": (196, 120, 70)}
SKINS = ("light", "fair", "tan", "brown", "dark")
HAIRS = ("black", "brown", "blonde", "red", "grey", "white")
BUILDS = {"slim": 0.88, "average": 1.0, "broad": 1.16, "round": 1.28}
TOP_STYLES = ("shirt", "coat", "apron", "vest", "dress", "overalls", "robe")
HATS = ("none", "cap", "flatcap", "beanie", "tophat", "beret", "hard", "straw", "sun", "bucket", "chef", "fire", "police", "nurse", "headscarf", "helmet", "crown")
HAIR_STYLES = ("short", "long", "bun", "ponytail", "curly", "afro", "braids", "spiky", "bald")
ACCESSORIES = ("glasses", "sunglasses", "scarf", "bowtie", "tie", "badge", "backpack", "belt", "cape", "beard", "mustache")
MAX_SHAPES = 16
PROPS = {}          # recipes of the story being rendered: name -> list of shapes (set by the renderer)


def color(v, default=None):
    """a colour from [r,g,b], '#rrggbb' or a plain name; the default if it can't be read"""
    if isinstance(v, (list, tuple)) and len(v) == 3 and all(isinstance(x, (int, float)) for x in v):
        return tuple(int(max(0, min(255, x))) for x in v)
    if isinstance(v, str):
        m = HEX.match(v.strip())
        if m:
            h = m.group(1)
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        return NAMES.get(v.strip().lower(), default)
    return default


def _num(v, lo, hi, d):
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return d


def sanitize_design(d):
    """a writer's character design, cleaned: only known words, parsed colours, clamped numbers"""
    if not isinstance(d, dict):
        return {}
    out = {}
    if d.get("build") in BUILDS:
        out["build"] = d["build"]
    if d.get("height") is not None:
        out["height"] = _num(d["height"], 0.85, 1.15, 1.0)
    if d.get("top_style") in TOP_STYLES:
        out["top_style"] = d["top_style"]
    for k in ("top", "bottom", "accent", "hat_color", "shoes"):
        c = color(d.get(k))
        if c:
            out[k] = c
    if d.get("hat") in HATS:
        out["hat"] = d["hat"]
    if d.get("hair_style") in HAIR_STYLES:
        out["hair_style"] = d["hair_style"]
    hc = d.get("hair")
    if color(d.get("hair_rgb")):
        out["hair_rgb"] = color(d["hair_rgb"])
    if color(d.get("skin_rgb")):
        out["skin_rgb"] = color(d["skin_rgb"])
    if hc in HAIRS:
        out["hair"] = hc
    elif color(hc):
        out["hair_rgb"] = color(hc)
    sk = d.get("skin")
    if sk in SKINS:
        out["skin"] = sk
    elif color(sk):
        out["skin_rgb"] = color(sk)
    acc = [a for a in (d.get("accessories") or []) if a in ACCESSORIES] if isinstance(d.get("accessories"), list) else []
    if acc:
        out["accessories"] = acc[:4]
    return out


def build_spec(role_spec, design):
    """the outfit of a person: the base role's outfit with the writer's design laid over it"""
    dz = design or {}
    # a designed character starts from a plain outfit, so nothing of a base role (its cap, coat, tool) leaks into the design
    spec = dict(top=role_spec["top"], bottom=role_spec["bottom"], tool=None) if dz else dict(role_spec)
    if dz.get("top"):
        spec["top"] = dz["top"]
    if dz.get("bottom"):
        spec["bottom"] = dz["bottom"]
    acc = dz.get("accent")
    st = dz.get("top_style")
    if st:
        for k in ("coat", "apron", "vest", "bib", "cardigan", "tie", "collar", "steth", "dress"):
            spec.pop(k, None)                                   # a designed outfit replaces the base role's outfit pieces
        spec["tool"] = spec.get("tool")
        a = acc or (250, 240, 220)
        if st == "coat":
            spec["coat"] = dz.get("top") or spec["top"]
            spec["top"] = acc or spec["top"]
        elif st == "apron":
            spec["apron"] = a
        elif st == "vest":
            spec["vest"] = a
        elif st == "overalls":
            spec["bib"] = a
        elif st == "dress":
            spec["dress"] = True
        elif st == "robe":
            spec["dress"] = True
            spec["coat"] = dz.get("top") or spec["top"]
    elif acc and "accent" not in spec:
        spec["accent"] = acc
    if dz.get("hat"):
        spec["hat"] = None if dz["hat"] == "none" else dz["hat"]
    if dz.get("hat_color"):
        spec["capcol"] = dz["hat_color"]
    for k in ("glasses", "sunglasses", "scarf", "bowtie", "tie", "badge", "backpack", "belt", "cape"):
        if k in (dz.get("accessories") or ()):
            spec[{"tie": "tie", "backpack": "pack"}.get(k, k)] = (acc or (210, 70, 80)) if k in ("tie", "scarf", "bowtie", "belt", "cape") else True
    if dz.get("shoes"):
        spec["shoes"] = dz["shoes"]
    return spec


# ------------------------------------------------------------------ props
def sanitize_props(props):
    """recipes for objects the story needs: {name: [shape, ...]}. A shape is one of
       {"k":"rrect","x0","y0","x1","y1","r","c"}  {"k":"oval","x","y","rx","ry","c"}  {"k":"line","x0","y0","x1","y1","w","c"}
       {"k":"poly","pts":[[x,y],...],"c"}  {"k":"glow","x","y","r","c"}   (units: a hand is about 40 wide; up is negative; origin is the hand or, for
       a set piece, the middle of the base on the ground)"""
    out = {}
    if not isinstance(props, dict):
        return out
    for name, rec in list(props.items())[:8]:
        shapes = rec.get("shapes") if isinstance(rec, dict) else rec
        if not isinstance(shapes, list):
            continue
        clean = []
        for sh in shapes[:MAX_SHAPES]:
            if not isinstance(sh, dict):
                continue
            k = sh.get("k")
            c = color(sh.get("c"), (200, 120, 90))
            n = lambda key, d=0.0: _num(sh.get(key), -400, 400, d)
            a = int(_num(sh.get("a", 255), 20, 255, 255))
            if k == "rrect":
                clean.append({"k": k, "x0": n("x0"), "y0": n("y0"), "x1": n("x1"), "y1": n("y1"), "r": _num(sh.get("r", 6), 0, 60, 6), "c": c, "a": a})
            elif k == "oval":
                clean.append({"k": k, "x": n("x"), "y": n("y"), "rx": _num(sh.get("rx", 10), 1, 300, 10), "ry": _num(sh.get("ry", 10), 1, 300, 10), "c": c, "a": a})
            elif k == "line":
                clean.append({"k": k, "x0": n("x0"), "y0": n("y0"), "x1": n("x1"), "y1": n("y1"), "w": _num(sh.get("w", 6), 1, 80, 6), "c": c, "a": a})
            elif k == "poly" and isinstance(sh.get("pts"), list) and 3 <= len(sh["pts"]) <= 12:
                pts = []
                for p in sh["pts"]:
                    if isinstance(p, (list, tuple)) and len(p) == 2:
                        pts.append((_num(p[0], -400, 400, 0), _num(p[1], -400, 400, 0)))
                if len(pts) >= 3:
                    clean.append({"k": k, "pts": pts, "c": c, "a": a})
            elif k == "glow":
                clean.append({"k": k, "x": n("x"), "y": n("y"), "r": _num(sh.get("r", 60), 5, 300, 60), "c": c, "a": int(_num(sh.get("a", 120), 20, 255, 120))})
        nm = re.sub(r"[^a-z0-9_ ]", "", str(name).lower()).strip().replace(" ", "_")[:24]
        if nm and clean:
            out[nm] = clean
    return out


def draw_recipe(shapes, ox, oy, size=1.0, flip=1, t=0.0):
    """draw a recipe with its origin at (ox, oy) in the current canvas units; flip mirrors it for people facing left"""
    from . import vector as V
    from .vector import lin, lite, dark, paint
    import skia
    sc = lambda x, y: (ox + flip * x * size, oy + y * size)
    for sh in shapes:
        k, c, a = sh["k"], sh["c"], sh.get("a", 255)
        if k == "rrect":
            x0, y0 = sc(sh["x0"], sh["y0"])
            x1, y1 = sc(sh["x1"], sh["y1"])
            x0, x1 = min(x0, x1), max(x0, x1)
            V.rrect(x0, y0, x1, y1, sh["r"] * size, paint(shader=lin(x0, y0, x1, y1, [(0, lite(c, 0.22)), (1, dark(c, 0.2))]), a=a) if a == 255 else paint(c, a))
        elif k == "oval":
            x, y = sc(sh["x"], sh["y"])
            V.oval(x, y, sh["rx"] * size, sh["ry"] * size, paint(shader=lin(x - sh["rx"] * size, y - sh["ry"] * size, x + sh["rx"] * size, y + sh["ry"] * size, [(0, lite(c, 0.25)), (1, dark(c, 0.2))])) if a == 255 else paint(c, a))
        elif k == "line":
            x0, y0 = sc(sh["x0"], sh["y0"])
            x1, y1 = sc(sh["x1"], sh["y1"])
            V.line(x0, y0, x1, y1, dark(c, 0.2), sh["w"] * size + 2, a)
            V.line(x0, y0, x1, y1, c, sh["w"] * size, a)
        elif k == "poly":
            V.poly([sc(x, y) for x, y in sh["pts"]], paint(c, a))
        elif k == "glow":
            x, y = sc(sh["x"], sh["y"])
            V.glow(x, y, sh["r"] * size * (1.0 + 0.04 * __import__("math").sin(t * 7)), c, sh["a"])
