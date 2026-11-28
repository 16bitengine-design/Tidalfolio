"""Built-in props: the objects stories keep naming, ready to use without being designed again.

Rule of the channel: whatever the narrator names that has a physical form must be seen on screen. The story writer can still design
its own objects (design.py), but these common ones are always available, by name, as a held thing ("carry") or a set piece (a scene's "props").

Units are the same as design.py recipes: a hand is about 40 wide, up is negative, the origin is the hand for a held object or the middle of the
base on the ground for a set piece. At most 16 shapes each.

Some things change while the narrator speaks (doors closing, a chair jammed between them). A recipe cannot move, so each stage of such a
thing is its own prop (train_doors_open, train_doors_closing, train_doors_jammed) and the scene shows them one after the other with
"from"/"to" words on each scene prop.
"""

PAPER, INK, WOOD, STEEL, NAVY, RED, CREAM = "#f6efdc", "#4a3f6b", "#a8794c", "#c4cad8", "#34407a", "#e24a5a", "#fbf4e2"


def _x_legs(x0, x1, ytop, w=6, c="#8d93a6"):
    return [{"k": "line", "x0": x0, "y0": ytop, "x1": x1, "y1": 0, "w": w, "c": c}, {"k": "line", "x0": x1, "y0": ytop, "x1": x0, "y1": 0, "w": w, "c": c}]


def _chair(ox=0.0, oy=0.0, k=1.0):
    """a folding chair: crossed legs, a seat, a back. Shifted and scaled so it can sit inside other props."""
    def p(x, y):
        return ox + x * k, oy + y * k
    out = []
    for (a, b), (c, d) in (((-26, -46), (26, 0)), ((26, -46), (-26, 0))):
        (x0, y0), (x1, y1) = p(a, b), p(c, d)
        out.append({"k": "line", "x0": x0, "y0": y0, "x1": x1, "y1": y1, "w": 6 * k, "c": "#8d93a6"})
    sx0, sy0 = p(-34, -54)
    sx1, sy1 = p(34, -44)
    out.append({"k": "rrect", "x0": sx0, "y0": sy0, "x1": sx1, "y1": sy1, "r": 4 * k, "c": "#d9885a"})
    bx0, by0 = p(-34, -118)
    bx1, by1 = p(-24, -50)
    out.append({"k": "rrect", "x0": bx0, "y0": by0, "x1": bx1, "y1": by1, "r": 4 * k, "c": "#8d93a6"})
    tx0, ty0 = p(-36, -122)
    tx1, ty1 = p(10, -100)
    out.append({"k": "rrect", "x0": tx0, "y0": ty0, "x1": tx1, "y1": ty1, "r": 5 * k, "c": "#d9885a"})
    return out


def _doors_state(open_px):
    """doors as two panels: each covers from its outer edge inward until `open_px` of the doorway is left open in the middle"""
    half_open = open_px / 2.0
    shapes = [{"k": "rrect", "x0": -104, "y0": -262, "x1": 104, "y1": 0, "r": 10, "c": NAVY},
              {"k": "rrect", "x0": -90, "y0": -246, "x1": 90, "y1": 0, "r": 6, "c": "#ffd98a"},
              {"k": "glow", "x": 0, "y": -130, "r": 150, "c": "#ffd98a", "a": 90}]
    if half_open < 90:
        shapes += [{"k": "rrect", "x0": -90, "y0": -246, "x1": -half_open, "y1": 0, "r": 4, "c": "#5f78c4"},
                   {"k": "rrect", "x0": half_open, "y0": -246, "x1": 90, "y1": 0, "r": 4, "c": "#5f78c4"},
                   {"k": "rrect", "x0": -76, "y0": -222, "x1": -max(half_open + 8, 34), "y1": -150, "r": 4, "c": "#cfe8ff", "a": 230},
                   {"k": "rrect", "x0": max(half_open + 8, 34), "y0": -222, "x1": 76, "y1": -150, "r": 4, "c": "#cfe8ff", "a": 230}]
    else:
        shapes += [{"k": "rrect", "x0": -90, "y0": -246, "x1": -72, "y1": 0, "r": 3, "c": "#5f78c4"},
                   {"k": "rrect", "x0": 72, "y0": -246, "x1": 90, "y1": 0, "r": 3, "c": "#5f78c4"}]
    return shapes


def _car(c, dark):
    """a small cartoon car, facing right, origin = middle of the ground line under it"""
    return [
        {"k": "poly", "pts": [[-58, -50], [-36, -86], [42, -86], [68, -50]], "c": c},
        {"k": "rrect", "x0": -102, "y0": -52, "x1": 102, "y1": -14, "r": 14, "c": c},
        {"k": "poly", "pts": [[-48, -54], [-32, -80], [-5, -80], [-5, -54]], "c": "#bfe4f5"},
        {"k": "poly", "pts": [[5, -54], [5, -80], [38, -80], [55, -54]], "c": "#bfe4f5"},
        {"k": "rrect", "x0": -102, "y0": -30, "x1": 102, "y1": -22, "r": 3, "c": dark},
        {"k": "oval", "x": -58, "y": -14, "rx": 21, "ry": 21, "c": "#2f2f44"}, {"k": "oval", "x": 58, "y": -14, "rx": 21, "ry": 21, "c": "#2f2f44"},
        {"k": "oval", "x": -58, "y": -14, "rx": 8, "ry": 8, "c": "#c9cbd8"}, {"k": "oval", "x": 58, "y": -14, "rx": 8, "ry": 8, "c": "#c9cbd8"},
        {"k": "oval", "x": 98, "y": -38, "rx": 6, "ry": 7, "c": "#fff3a0"},
    ]


def _bus(c):
    out = [{"k": "rrect", "x0": -150, "y0": -118, "x1": 150, "y1": -14, "r": 16, "c": c},
           {"k": "rrect", "x0": -150, "y0": -48, "x1": 150, "y1": -38, "r": 2, "c": "#fbf4e2"}]
    for i in range(5):
        out.append({"k": "rrect", "x0": -128 + i * 52, "y0": -104, "x1": -92 + i * 52, "y1": -64, "r": 6, "c": "#bfe4f5"})
    out += [{"k": "oval", "x": -90, "y": -14, "rx": 22, "ry": 22, "c": "#2f2f44"}, {"k": "oval", "x": 90, "y": -14, "rx": 22, "ry": 22, "c": "#2f2f44"},
            {"k": "oval", "x": -90, "y": -14, "rx": 9, "ry": 9, "c": "#c9cbd8"}, {"k": "oval", "x": 90, "y": -14, "rx": 9, "ry": 9, "c": "#c9cbd8"}]
    return out


def _pet(c, ear, cat=False):
    """a dog or a cat standing side-on, facing right, origin = on the ground under the middle"""
    out = [{"k": "line", "x0": -34, "y0": -46, "x1": -54, "y1": -76 if not cat else -92, "w": 8, "c": c}]
    for x in (-24, -8, 16, 30):
        out.append({"k": "line", "x0": x, "y0": -28, "x1": x, "y1": 0, "w": 8, "c": c})
    out += [{"k": "oval", "x": 0, "y": -42, "rx": 38, "ry": 20, "c": c},
            {"k": "oval", "x": 42, "y": -64, "rx": 19, "ry": 17, "c": c},
            {"k": "poly", "pts": [[30, -76], [36, -100 if cat else -90], [46, -78]], "c": ear},
            {"k": "poly", "pts": [[44, -78], [54, -100 if cat else -88], [58, -72]], "c": ear},
            {"k": "oval", "x": 56, "y": -58, "rx": 8, "ry": 6, "c": "#f6efdc"},
            {"k": "oval", "x": 62, "y": -60, "rx": 3, "ry": 3, "c": "#3a2f4a"},
            {"k": "oval", "x": 46, "y": -68, "rx": 3, "ry": 3, "c": "#3a2f4a"}]
    return out


def _bird(c):
    """a small bird in flight, facing right, origin = its middle"""
    return [{"k": "poly", "pts": [[-6, -4], [-30, -34], [-12, -10]], "c": c},
            {"k": "poly", "pts": [[2, -4], [-8, -40], [14, -8]], "c": c},
            {"k": "poly", "pts": [[-24, 0], [-40, 6], [-22, 8]], "c": c},
            {"k": "oval", "x": 0, "y": 0, "rx": 20, "ry": 11, "c": c},
            {"k": "oval", "x": 18, "y": -6, "rx": 9, "ry": 8, "c": c},
            {"k": "poly", "pts": [[25, -7], [38, -3], [25, -1]], "c": "#f4b13c"},
            {"k": "oval", "x": 21, "y": -9, "rx": 2, "ry": 2, "c": "#2a2438"}]


def _tree(crown, crown2):
    return [{"k": "rrect", "x0": -10, "y0": -100, "x1": 10, "y1": 0, "r": 4, "c": "#8a5a3a"},
            {"k": "oval", "x": -36, "y": -108, "rx": 38, "ry": 34, "c": crown2}, {"k": "oval", "x": 36, "y": -108, "rx": 38, "ry": 34, "c": crown2},
            {"k": "oval", "x": 0, "y": -140, "rx": 58, "ry": 52, "c": crown}, {"k": "oval", "x": -18, "y": -152, "rx": 18, "ry": 14, "c": "#ffffff", "a": 0.15}]


def _pine(c, c2):
    return [{"k": "rrect", "x0": -8, "y0": -50, "x1": 8, "y1": 0, "r": 3, "c": "#7a4e30"},
            {"k": "poly", "pts": [[-56, -38], [0, -118], [56, -38]], "c": c}, {"k": "poly", "pts": [[-46, -88], [0, -164], [46, -88]], "c": c2},
            {"k": "poly", "pts": [[-34, -134], [0, -206], [34, -134]], "c": c}]


def _bush(c):
    return [{"k": "oval", "x": -28, "y": -20, "rx": 30, "ry": 22, "c": c}, {"k": "oval", "x": 28, "y": -20, "rx": 30, "ry": 22, "c": c},
            {"k": "oval", "x": 0, "y": -32, "rx": 34, "ry": 28, "c": "#5aa86a"}]


def _flowers():
    out = []
    for i, c in enumerate(("#e24a5a", "#ffd25a", "#ff8fc0", "#fff3f0", "#a77ae8")):
        x = -40 + i * 20
        out.append({"k": "line", "x0": x, "y0": 0, "x1": x, "y1": -22 - (i % 2) * 8, "w": 3, "c": "#4f9a5a"})
        out.append({"k": "oval", "x": x, "y": -26 - (i % 2) * 8, "rx": 8, "ry": 8, "c": c})
    return out


def _lamp():
    return [{"k": "line", "x0": 0, "y0": 0, "x1": 0, "y1": -170, "w": 8, "c": "#4a4a66"}, {"k": "line", "x0": 0, "y0": -170, "x1": 22, "y1": -176, "w": 6, "c": "#4a4a66"},
            {"k": "oval", "x": 26, "y": -170, "rx": 15, "ry": 12, "c": "#ffe9a0"}, {"k": "rrect", "x0": -14, "y0": -8, "x1": 14, "y1": 0, "r": 3, "c": "#4a4a66"}]


def _fence():
    out = [{"k": "line", "x0": -70, "y0": -42, "x1": 70, "y1": -42, "w": 6, "c": "#c9b08a"}, {"k": "line", "x0": -70, "y0": -22, "x1": 70, "y1": -22, "w": 6, "c": "#c9b08a"}]
    for i in range(6):
        out.append({"k": "rrect", "x0": -72 + i * 28, "y0": -56, "x1": -60 + i * 28, "y1": 0, "r": 3, "c": "#d8bf94"})
    return out


def _pigeon_fly(letter=False):
    out = _bird("#8a90a8")
    out[4]["c"] = "#6e7490"
    if letter:                                       # carrying the letter in its feet
        out += [{"k": "rrect", "x0": 6, "y0": 8, "x1": 34, "y1": 24, "r": 2, "c": "#fbf4e2"}, {"k": "line", "x0": 8, "y0": 14, "x1": 32, "y1": 14, "w": 2, "c": "#d9c9a0"}]
    k = 2.3                                          # a story pigeon is the star of its scene: big enough to read next to a person
    big = []
    for sh in out:
        sh = dict(sh)
        for key in ("x", "y", "rx", "ry", "x0", "y0", "x1", "y1", "w", "r"):
            if key in sh:
                sh[key] = sh[key] * k
        if "pts" in sh:
            sh["pts"] = [[p[0] * k, p[1] * k] for p in sh["pts"]]
        big.append(sh)
    return big


BG_SCENERY = {"bg_tree": _tree("#6cc17a", "#58ac68"), "bg_tree_gold": _tree("#f2a64a", "#e08a3a"), "bg_pine": _pine("#3f8f66", "#4aa074"), "bg_pine_dark": _pine("#2f7a58", "#3b8a66"),
              "bg_bush": _bush("#4f9a5a"), "bg_flowers": _flowers(), "bg_lamp": _lamp(), "bg_fence": _fence()}

BG_THINGS = {            # scenery life that is never named: cars, a bus, a dog, a cat, birds (used behind the main characters)
    "bg_car_red": _car("#e24a5a", "#b8323f"), "bg_car_blue": _car("#4a7ae2", "#3358b0"), "bg_car_yellow": _car("#f4c23c", "#c99a1f"),
    "bg_bus": _bus("#f08a3c"), "bg_dog": _pet("#c98f5a", "#8a5a35"), "bg_cat": _pet("#9a9fb4", "#6e7390", cat=True),
    "bg_bird": _bird("#5a6ee0"), "bg_bird2": _bird("#e0795a"),
}

RAW = {
    # --- an open umbrella that floats by itself (origin = the bottom of the handle) ---
    "umbrella_float": [
        {"k": "line", "x0": 0, "y0": 0, "x1": 0, "y1": -150, "w": 8, "c": "#50506e"},
        {"k": "poly", "pts": [[-95, -140], [95, -140], [62, -208], [0, -230], [-62, -208]], "c": "#f4883c"},
        {"k": "poly", "pts": [[-32, -140], [32, -140], [22, -216], [0, -230], [-14, -214]], "c": "#ffd25a"},
        {"k": "oval", "x": 0, "y": -234, "rx": 7, "ry": 7, "c": "#50506e"},
    ],
    # --- a folded paper map: route, a river, an X ---
    "map": [
        {"k": "rrect", "x0": -34, "y0": -50, "x1": 34, "y1": 4, "r": 4, "c": PAPER},
        {"k": "line", "x0": -11, "y0": -48, "x1": -11, "y1": 2, "w": 2, "c": "#d3c7a6"},
        {"k": "line", "x0": 12, "y0": -48, "x1": 12, "y1": 2, "w": 2, "c": "#d3c7a6"},
        {"k": "poly", "pts": [[-30, -36], [-18, -42], [-6, -26], [-20, -12], [-30, -18]], "c": "#8fd0a0"},
        {"k": "line", "x0": 4, "y0": -48, "x1": 18, "y1": -28, "w": 7, "c": "#8cc4f0"},
        {"k": "line", "x0": 18, "y0": -28, "x1": 8, "y1": 0, "w": 7, "c": "#8cc4f0"},
        {"k": "line", "x0": -26, "y0": -8, "x1": -6, "y1": -22, "w": 3, "c": RED},
        {"k": "line", "x0": -6, "y0": -22, "x1": 12, "y1": -14, "w": 3, "c": RED},
        {"k": "line", "x0": 18, "y0": -14, "x1": 28, "y1": -4, "w": 4, "c": RED},
        {"k": "line", "x0": 28, "y0": -14, "x1": 18, "y1": -4, "w": 4, "c": RED},
    ],
    # --- a pocket notebook, closed, with a ribbon ---
    "notebook": [
        {"k": "rrect", "x0": -26, "y0": -44, "x1": 26, "y1": 2, "r": 5, "c": "#3f8f86"},
        {"k": "rrect", "x0": -22, "y0": -41, "x1": 22, "y1": -1, "r": 3, "c": "#4fa79b"},
        {"k": "rrect", "x0": -8, "y0": -34, "x1": 18, "y1": -22, "r": 3, "c": CREAM},
        {"k": "line", "x0": -12, "y0": -44, "x1": -12, "y1": 2, "w": 4, "c": "#2c6b64"},
        {"k": "line", "x0": 16, "y0": 2, "x1": 16, "y1": 14, "w": 4, "c": RED},
    ],
    # --- one page torn from a notebook, ruled, with a hand-drawn dotted route ---
    "notebook_page": [
        {"k": "rrect", "x0": -32, "y0": -52, "x1": 32, "y1": 2, "r": 3, "c": CREAM},
        {"k": "line", "x0": -26, "y0": -40, "x1": 26, "y1": -40, "w": 2, "c": "#9fc4e8"},
        {"k": "line", "x0": -26, "y0": -28, "x1": 26, "y1": -28, "w": 2, "c": "#9fc4e8"},
        {"k": "line", "x0": -26, "y0": -16, "x1": 26, "y1": -16, "w": 2, "c": "#9fc4e8"},
        {"k": "line", "x0": -26, "y0": -4, "x1": 26, "y1": -4, "w": 2, "c": "#9fc4e8"},
        {"k": "line", "x0": -23, "y0": -52, "x1": -23, "y1": 2, "w": 2, "c": "#f08a98"},
        {"k": "line", "x0": -16, "y0": -12, "x1": -4, "y1": -32, "w": 3, "c": INK},
        {"k": "line", "x0": -4, "y0": -32, "x1": 10, "y1": -22, "w": 3, "c": INK},
        {"k": "line", "x0": 10, "y0": -22, "x1": 24, "y1": -40, "w": 3, "c": INK},
        {"k": "oval", "x": 24, "y": -42, "rx": 5, "ry": 5, "c": RED},
        {"k": "poly", "pts": [[-32, 2], [-24, -4], [-16, 2], [-8, -3], [0, 2]], "c": "#e8dfc4"},
    ],
    # --- a referee's / guard's whistle with a cord, big enough to read ---
    "whistle": [
        {"k": "oval", "x": 0, "y": -18, "rx": 19, "ry": 15, "c": "#cfd6e8"},
        {"k": "rrect", "x0": -42, "y0": -24, "x1": -8, "y1": -10, "r": 6, "c": "#aab3cc"},
        {"k": "oval", "x": 4, "y": -22, "rx": 6, "ry": 5, "c": "#3a3550"},
        {"k": "line", "x0": 6, "y0": -32, "x1": 6, "y1": -50, "w": 4, "c": "#e24a5a"},
        {"k": "line", "x0": 6, "y0": -50, "x1": 34, "y1": -70, "w": 3, "c": "#e24a5a"},
        {"k": "glow", "x": 0, "y": -18, "r": 34, "c": "#ffffff", "a": 70},
    ],
    # --- a flag on a long pole (the origin is the hand holding it) ---
    "flag": [
        {"k": "line", "x0": 0, "y0": 10, "x1": 0, "y1": -230, "w": 7, "c": "#7b5a3a"},
        {"k": "oval", "x": 0, "y": -236, "rx": 8, "ry": 8, "c": "#f4c542"},
        {"k": "poly", "pts": [[4, -224], [92, -214], [118, -196], [90, -178], [112, -160], [4, -168]], "c": "#e24a5a"},
        {"k": "poly", "pts": [[4, -208], [88, -200], [96, -192], [4, -190]], "c": "#fbf4e2"},
        {"k": "oval", "x": 40, "y": -196, "rx": 9, "ry": 9, "c": "#34407a"},
    ],
    # --- a folding chair, open, as a set piece or carried by the back ---
    "folding_chair": _chair(),
    # --- a train carriage seen from the side, with a steam whistle on the boiler ---
    "train": [
        {"k": "rrect", "x0": -300, "y0": -210, "x1": 300, "y1": -36, "r": 22, "c": "#d94a5c"},
        {"k": "rrect", "x0": -300, "y0": -120, "x1": 300, "y1": -92, "r": 4, "c": "#fbf4e2"},
        {"k": "rrect", "x0": -280, "y0": -190, "x1": -170, "y1": -130, "r": 8, "c": "#bfe3ff"},
        {"k": "rrect", "x0": -140, "y0": -190, "x1": -30, "y1": -130, "r": 8, "c": "#bfe3ff"},
        {"k": "rrect", "x0": 30, "y0": -190, "x1": 140, "y1": -130, "r": 8, "c": "#bfe3ff"},
        {"k": "rrect", "x0": 170, "y0": -190, "x1": 280, "y1": -130, "r": 8, "c": "#bfe3ff"},
        {"k": "rrect", "x0": -300, "y0": -228, "x1": 300, "y1": -206, "r": 8, "c": "#34407a"},
        {"k": "oval", "x": -220, "y": -28, "rx": 36, "ry": 36, "c": "#3a3550"},
        {"k": "oval", "x": -60, "y": -28, "rx": 36, "ry": 36, "c": "#3a3550"},
        {"k": "oval", "x": 100, "y": -28, "rx": 36, "ry": 36, "c": "#3a3550"},
        {"k": "oval", "x": 240, "y": -28, "rx": 36, "ry": 36, "c": "#3a3550"},
        {"k": "rrect", "x0": 292, "y0": -130, "x1": 318, "y1": -110, "r": 6, "c": "#ffd98a"},
        {"k": "glow", "x": 322, "y": -120, "r": 90, "c": "#ffe9a8", "a": 150},
        {"k": "rrect", "x0": 210, "y0": -262, "x1": 230, "y1": -228, "r": 4, "c": "#e0b84a"},
        {"k": "oval", "x": 220, "y": -266, "rx": 16, "ry": 8, "c": "#f4d36a"},
    ],
    # --- the doorway of a carriage in four states (swap them on the narrator's words) ---
    "train_doors_open": _doors_state(180),
    "train_doors_closing": _doors_state(70),
    "train_doors_closed": _doors_state(0),
    # --- the doors held ajar by a folding chair standing in the gap ---
    "train_doors_jammed": _doors_state(56) + _chair(0, 0, 0.92),
    # --- a clock on a post (as at a station), the hands at three minutes to the hour ---
    "station_clock": [
        {"k": "rrect", "x0": -7, "y0": -300, "x1": 7, "y1": 0, "r": 3, "c": "#3a3550"},
        {"k": "oval", "x": 0, "y": -336, "rx": 60, "ry": 60, "c": "#c8793f"},
        {"k": "oval", "x": 0, "y": -336, "rx": 50, "ry": 50, "c": "#fbf4e2"},
        {"k": "line", "x0": 0, "y0": -382, "x1": 0, "y1": -372, "w": 5, "c": "#3a3550"},
        {"k": "line", "x0": 46, "y0": -336, "x1": 36, "y1": -336, "w": 5, "c": "#3a3550"},
        {"k": "line", "x0": 0, "y0": -290, "x1": 0, "y1": -300, "w": 5, "c": "#3a3550"},
        {"k": "line", "x0": -46, "y0": -336, "x1": -36, "y1": -336, "w": 5, "c": "#3a3550"},
        {"k": "line", "x0": 0, "y0": -336, "x1": 0, "y1": -364, "w": 7, "c": "#3a3550"},
        {"k": "line", "x0": 0, "y0": -336, "x1": -7, "y1": -378, "w": 4, "c": "#3a3550"},
        {"k": "oval", "x": 0, "y": -336, "rx": 6, "ry": 6, "c": "#e24a5a"},
    ],
    # --- a small stone bridge over water ---
    "bridge": [
        {"k": "rrect", "x0": -270, "y0": -14, "x1": 270, "y1": 8, "r": 6, "c": "#5aa6e6", "a": 230},
        {"k": "rrect", "x0": -214, "y0": -104, "x1": 214, "y1": -4, "r": 8, "c": "#8a7ea4"},
        {"k": "poly", "pts": [[-88, -4], [-82, -32], [-62, -54], [-32, -68], [0, -72], [32, -68], [62, -54], [82, -32], [88, -4]], "c": "#5aa6e6"},
        {"k": "rrect", "x0": -226, "y0": -134, "x1": 226, "y1": -102, "r": 8, "c": "#b3a8c8"},
        {"k": "line", "x0": -160, "y0": -132, "x1": -160, "y1": -104, "w": 5, "c": "#7a6f94"},
        {"k": "line", "x0": -54, "y0": -132, "x1": -54, "y1": -104, "w": 5, "c": "#7a6f94"},
        {"k": "line", "x0": 54, "y0": -132, "x1": 54, "y1": -104, "w": 5, "c": "#7a6f94"},
        {"k": "line", "x0": 160, "y0": -132, "x1": 160, "y1": -104, "w": 5, "c": "#7a6f94"},
    ],
    # --- a bowl of hot soup with a spoon and steam ---
    "soup": [
        {"k": "oval", "x": 0, "y": -20, "rx": 40, "ry": 26, "c": "#f6efdc"},
        {"k": "rrect", "x0": -40, "y0": -48, "x1": 40, "y1": -22, "r": 4, "c": "#f6efdc"},
        {"k": "oval", "x": 0, "y": -46, "rx": 38, "ry": 10, "c": "#e8864a"},
        {"k": "oval", "x": -14, "y": -46, "rx": 6, "ry": 3, "c": "#7cc48e"},
        {"k": "line", "x0": 22, "y0": -44, "x1": 52, "y1": -84, "w": 4, "c": "#c4cad8"},
        {"k": "line", "x0": -14, "y0": -60, "x1": -8, "y1": -86, "w": 5, "c": "#ffffff", "a": 150},
        {"k": "line", "x0": 4, "y0": -62, "x1": -2, "y1": -92, "w": 5, "c": "#ffffff", "a": 150},
    ],
    # --- a plump grey pigeon standing on its feet ---
    "pigeon": [
        {"k": "oval", "x": 0, "y": -34, "rx": 34, "ry": 24, "c": "#9aa3b8"},
        {"k": "oval", "x": 26, "y": -58, "rx": 15, "ry": 15, "c": "#8a93aa"},
        {"k": "poly", "pts": [[38, -60], [54, -54], [38, -52]], "c": "#f2b84a"},
        {"k": "oval", "x": 31, "y": -62, "rx": 3, "ry": 3, "c": "#2d2a3e"},
        {"k": "oval", "x": 22, "y": -45, "rx": 14, "ry": 7, "c": "#b9a0d6"},
        {"k": "poly", "pts": [[-30, -40], [-62, -30], [-58, -22], [-28, -26]], "c": "#7f88a0"},
        {"k": "oval", "x": -6, "y": -36, "rx": 22, "ry": 13, "c": "#7f88a0"},
        {"k": "line", "x0": -6, "y0": -12, "x1": -6, "y1": 0, "w": 3, "c": "#e2706a"},
        {"k": "line", "x0": 10, "y0": -12, "x1": 10, "y1": 0, "w": 3, "c": "#e2706a"},
    ],
    # --- a crowd on the run: a flag held high and a folding chair raised over the heads ---
    "marching_crowd": [s for i, (x, h, c) in enumerate([(-230, 150, "#e2706a"), (-130, 166, "#5fa8d8"), (-30, 150, "#f2b84a"), (70, 168, "#7cc48e"), (170, 152, "#b887d8")])
                       for s in ({"k": "rrect", "x0": x - 28, "y0": -h + 44, "x1": x + 28, "y1": 0, "r": 16, "c": c},
                                 {"k": "oval", "x": x, "y": -h + 22, "rx": 24, "ry": 25, "c": "#f2c9a0" if i % 2 else "#c8946c"})] + [
        {"k": "line", "x0": -130, "y0": -140, "x1": -130, "y1": -330, "w": 6, "c": "#7b5a3a"},
        {"k": "poly", "pts": [[-127, -326], [-40, -314], [-62, -290], [-127, -280]], "c": "#e24a5a"},
        {"k": "rrect", "x0": 138, "y0": -232, "x1": 206, "y1": -222, "r": 3, "c": "#d9885a"},
        {"k": "line", "x0": 142, "y0": -222, "x1": 202, "y1": -176, "w": 5, "c": "#8d93a6"},
        {"k": "line", "x0": 202, "y0": -222, "x1": 142, "y1": -176, "w": 5, "c": "#8d93a6"},
    ][:6],
    # --- an ordinary house or classroom door, shut, and the same door open ---
    "door": [
        {"k": "rrect", "x0": -62, "y0": -250, "x1": 62, "y1": 0, "r": 8, "c": "#8a5a3c"},
        {"k": "rrect", "x0": -46, "y0": -232, "x1": 46, "y1": -140, "r": 6, "c": "#a8754f"},
        {"k": "rrect", "x0": -46, "y0": -126, "x1": 46, "y1": -16, "r": 6, "c": "#a8754f"},
        {"k": "oval", "x": 42, "y": -118, "rx": 8, "ry": 8, "c": "#f4d36a"},
    ],
    "door_open": [
        {"k": "rrect", "x0": -62, "y0": -250, "x1": 62, "y1": 0, "r": 8, "c": "#fff0c8"},
        {"k": "glow", "x": 0, "y": -120, "r": 140, "c": "#ffe9a8", "a": 120},
        {"k": "poly", "pts": [[-62, -250], [-20, -238], [-20, -10], [-62, 0]], "c": "#8a5a3c"},
        {"k": "oval", "x": -30, "y": -118, "rx": 6, "ry": 6, "c": "#f4d36a"},
    ],
    # --- a crowd of many small people, as a backdrop (eight figures, different colours and heights) ---
    "crowd": [s for i, (x, h, c) in enumerate([(-300, 150, "#e2706a"), (-215, 165, "#5fa8d8"), (-130, 148, "#f2b84a"), (-45, 170, "#7cc48e"),
                                                  (40, 152, "#b887d8"), (125, 166, "#f08fb0"), (210, 150, "#4fb6b2"), (295, 162, "#e6944a")])
              for s in ({"k": "rrect", "x0": x - 28, "y0": -h + 44, "x1": x + 28, "y1": 0, "r": 16, "c": c},
                        {"k": "oval", "x": x, "y": -h + 22, "rx": 24, "ry": 25, "c": "#f2c9a0" if i % 3 else "#c8946c"})],
}
# a word the narration can say -> the built-in props that show it (used by the story check)
ALIASES = {
    "map": ("map", "notebook_page"), "maps": ("map", "notebook_page"),
    "notebook": ("notebook", "notebook_page"), "notebooks": ("notebook", "notebook_page"),
    "page": ("notebook_page",), "pages": ("notebook_page",),
    "whistle": ("whistle", "train"), "whistles": ("whistle", "train"),
    "flag": ("flag", "marching_crowd"), "flags": ("flag", "marching_crowd"),
    "chair": ("folding_chair", "train_doors_jammed", "marching_crowd"), "chairs": ("folding_chair", "train_doors_jammed", "marching_crowd"),
    "train": ("train",), "trains": ("train",),
    "door": ("door", "door_open", "train_doors_open", "train_doors_closing", "train_doors_closed", "train_doors_jammed"),
    "doors": ("door", "door_open", "train_doors_open", "train_doors_closing", "train_doors_closed", "train_doors_jammed"),
    "crowd": ("crowd", "marching_crowd"), "crowds": ("crowd", "marching_crowd"), "pigeon": ("pigeon", "pigeon_fly", "pigeon_fly_letter"), "pigeons": ("pigeon", "pigeon_fly", "pigeon_fly_letter"),
    "clock": ("station_clock",), "bridge": ("bridge",), "soup": ("soup",),
    "bread": ("baguette",), "note": ("notebook", "notebook_page"), "notes": ("notebook", "notebook_page"),
}
RAW.update(BG_THINGS)
RAW["pigeon_fly"] = _pigeon_fly()
RAW["pigeon_fly_letter"] = _pigeon_fly(True)
RAW.update(BG_SCENERY)
NAMES = tuple(RAW)
