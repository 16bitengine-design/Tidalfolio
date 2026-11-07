"""Human characters, drawn in code in the same bold ink style as the animals.
A person is told apart by ROLE (baker, doctor, teacher ...), gender (male|female) and age (child|adult|elder), never by name.
Everything is in character units with the origin at the centre of the feet (up is negative); one adult is about 410 units tall."""
import math

from . import engine as E
from .engine import INK, P, S, blob, inked, lit, shade, stroke

SKIN = {"light": (255, 218, 186), "fair": (246, 200, 160), "tan": (226, 172, 122), "brown": (170, 114, 76), "dark": (112, 74, 52)}
HAIR = {"black": (34, 28, 30), "brown": (112, 68, 36), "blonde": (240, 198, 92), "red": (206, 88, 42), "grey": (186, 186, 194), "white": (238, 238, 244)}
SKIN_ORDER, HAIR_ORDER = tuple(SKIN), ("black", "brown", "blonde", "red", "black", "brown")

# role: outfit. top/bottom colours, hat, apron, coat (long coat colour), tie, vest, glasses, tool (held item), dress (female wears a dress/skirt)
ROLES = {
    "baker":        dict(top=(250, 246, 236), bottom=(70, 70, 96), hat="chef", apron=(240, 232, 214), tool="rolling_pin"),
    "chef":         dict(top=(252, 252, 248), bottom=(60, 60, 80), hat="chef", tie=None, tool="pan"),
    "waiter":       dict(top=(250, 250, 250), bottom=(30, 30, 40), vest=(40, 40, 52), tie=(190, 40, 56), tool="tray"),
    "doctor":       dict(top=(100, 190, 200), bottom=(80, 110, 150), coat=(252, 252, 252), glasses=True, tool="clipboard", steth=True),
    "nurse":        dict(top=(78, 188, 180), bottom=(60, 160, 154), hat="nurse", steth=True, tool="clipboard"),
    "teacher":      dict(top=(150, 90, 170), bottom=(70, 62, 90), glasses=True, tie=(220, 160, 50), tool="book", dress=True),
    "student":      dict(top=(230, 90, 70), bottom=(60, 90, 160), tool="book", pack=True),
    "mechanic":     dict(top=(60, 110, 190), bottom=(60, 110, 190), hat="cap", capcol=(200, 60, 50), tool="wrench", smudge=True),
    "farmer":       dict(top=(196, 70, 60), bottom=(70, 110, 180), hat="straw", bib=(70, 110, 180), tool="pitchfork"),
    "police officer": dict(top=(70, 100, 170), bottom=(40, 52, 90), hat="police", badge=True, tie=(30, 30, 40), tool=None),
    "firefighter":  dict(top=(240, 180, 40), bottom=(60, 60, 70), hat="fire", coat=(240, 180, 40), tool="hose"),
    "judge":        dict(top=(34, 32, 42), bottom=(34, 32, 42), coat=(34, 32, 42), collar=(250, 250, 250), tool="gavel"),
    "mail carrier": dict(top=(70, 110, 190), bottom=(70, 80, 110), hat="cap", capcol=(70, 110, 190), tool="letter", bag=True),
    "taxi driver":  dict(top=(250, 250, 240), bottom=(50, 54, 70), hat="flatcap", capcol=(250, 200, 40), tool=None, tie=(250, 200, 40)),
    "shopkeeper":   dict(top=(236, 226, 196), bottom=(90, 76, 60), apron=(60, 150, 100), tool="bag"),
    "barber":       dict(top=(250, 250, 250), bottom=(40, 40, 54), vest=(190, 50, 60), tie=(40, 40, 54), tool="comb"),
    "painter":      dict(top=(240, 240, 230), bottom=(110, 80, 150), hat="beret", capcol=(210, 60, 80), smudge=True, tool="brush"),
    "scientist":    dict(top=(90, 150, 200), bottom=(60, 70, 100), coat=(252, 252, 252), glasses=True, tool="flask"),
    "librarian":    dict(top=(170, 120, 110), bottom=(80, 70, 90), glasses=True, tool="book", dress=True, cardigan=(120, 160, 130)),
    "gardener":     dict(top=(150, 200, 90), bottom=(110, 84, 60), hat="straw", apron=(60, 150, 90), tool="watering_can"),
    "builder":      dict(top=(250, 140, 40), bottom=(90, 90, 110), hat="hard", vest=(250, 210, 50), tool="hammer"),
    "fisherman":    dict(top=(250, 200, 50), bottom=(60, 90, 80), hat="bucket", tool="fish"),
    "tourist":      dict(top=(250, 120, 140), bottom=(240, 220, 170), hat="sun", tool="camera"),
    "boss":         dict(top=(44, 50, 70), bottom=(44, 50, 70), tie=(200, 50, 60), tool="phone", glasses=False),
    "office worker": dict(top=(210, 230, 250), bottom=(70, 76, 100), tie=(70, 130, 190), tool="paper", dress=True),
    "cashier":      dict(top=(250, 80, 90), bottom=(60, 66, 90), apron=(250, 230, 120), tool=None),
    "grandmother":  dict(top=(180, 120, 160), bottom=(100, 80, 110), cardigan=(240, 200, 120), glasses=True, tool="cane", dress=True),
    "grandfather":  dict(top=(120, 150, 170), bottom=(100, 96, 90), cardigan=(160, 110, 80), glasses=True, tool="cane"),
    "mother":       dict(top=(250, 150, 90), bottom=(70, 100, 150), tool=None, dress=True),
    "father":       dict(top=(90, 150, 110), bottom=(80, 90, 120), tool=None),
    "boy":          dict(top=(80, 150, 230), bottom=(90, 110, 90), tool=None),
    "girl":         dict(top=(240, 100, 160), bottom=(120, 80, 170), tool=None, dress=True),
    "neighbour":    dict(top=(150, 190, 110), bottom=(100, 100, 120), tool=None),
    "stranger":     dict(top=(110, 70, 130), bottom=(40, 40, 54), coat=(70, 50, 90), hat="flatcap", capcol=(60, 50, 70), tool=None),
}
ROLE_ALIAS = {"cook": "chef", "waitress": "waiter", "policeman": "police officer", "policewoman": "police officer", "cop": "police officer", "police": "police officer",
              "postman": "mail carrier", "postwoman": "mail carrier", "mailman": "mail carrier", "driver": "taxi driver", "cab driver": "taxi driver",
              "shop owner": "shopkeeper", "shop keeper": "shopkeeper", "artist": "painter", "researcher": "scientist", "gardner": "gardener",
              "construction worker": "builder", "worker": "builder", "angler": "fisherman", "fisher": "fisherman", "visitor": "tourist", "manager": "boss",
              "businessman": "boss", "businesswoman": "boss", "executive": "boss", "clerk": "office worker", "secretary": "office worker",
              "granny": "grandmother", "grandma": "grandmother", "grandpa": "grandfather", "mum": "mother", "mom": "mother", "dad": "father",
              "kid": "boy", "child": "boy", "pupil": "student", "fireman": "firefighter", "mayor": "boss", "lawyer": "boss", "old man": "grandfather",
              "old woman": "grandmother", "passer-by": "stranger", "passerby": "stranger", "customer": "stranger", "man": "stranger", "woman": "stranger"}
ROLES_LIST = tuple(ROLES)
KID_ROLES = ("student", "boy", "girl")


def norm_role(r):
    r = str(r or "").strip().lower().replace("_", " ")
    r = ROLE_ALIAS.get(r, r)
    return r if r in ROLES else ""


def default_gender(role, hint=None):
    if hint in ("male", "female"):
        return hint
    return {"nurse": "female", "mother": "female", "girl": "female", "grandmother": "female", "librarian": "female", "waiter": "male",
            "father": "male", "boy": "male", "grandfather": "male", "fisherman": "male", "barber": "male"}.get(role, "male")


def default_age(role):
    return {"boy": "child", "girl": "child", "student": "child", "grandmother": "elder", "grandfather": "elder"}.get(role, "adult")


def default_look(role, index):
    """skin and hair for a cast member that did not give them: deterministic, and different from the people before it"""
    return SKIN_ORDER[(index * 2 + 1) % len(SKIN_ORDER)], HAIR_ORDER[(index * 3 + 1) % len(HAIR_ORDER)]


def _arc(cx, cy, rx, ry, a0, a1, n=12):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def person(d, x, y, s=1.0, f=1, t=0.0, role="stranger", gender="male", age="adult", skin="fair", hair="brown", extras=(), talk=0.0,
           eye="open", brow=(0, 0), tear=0.0, look=(0, 0), action="stand", mood="neutral", bounce=0.0, carry=None, seed=0, walk=0.0, gait=0.0):
    spec = ROLES.get(role, ROLES["stranger"])
    kid, elder, fem = age == "child", age == "elder", gender == "female"
    s = s * (0.72 if kid else (0.97 if elder else 1.0))
    HS = 1.22 if kid else 1.0                      # kids: bigger head, shorter body
    skin_c = SKIN.get(skin, SKIN["fair"])
    hair_c = HAIR["grey" if elder else (hair if hair in HAIR else "brown")]
    top, bottom = spec["top"], spec["bottom"]

    # life: a breath, a bob when walking (the feet stay planted), a nod when talking, a drooping head when sad
    breath = math.sin(t * 1.7 + seed) * 1.6
    bob = -abs(math.sin(gait)) * 9 * walk + breath
    bounce = bounce + bob
    nod = (math.sin(t * 7.3 + seed) * 2.6 + math.sin(t * 3.1) * 1.4) * (1 if talk > 0 else 0) + {"sad": 11, "scared": 4, "shocked": -5, "smug": -4, "happy": -2}.get(mood, 0)

    turn = min(1.0, walk * 1.6)                       # walking: the body turns three-quarters toward where it is going
    shx = [0.0]                                       # sideways shift of the face and hat (set while they are drawn)

    def L(lx, ly):
        return (x + f * (lx + shx[0]) * s, y + ly * s + bounce)

    def B(cx, cy, rx, ry, c, w=3.6, ang=0.0, sd=1, lit_=True):
        px_, py_ = L(cx, cy)
        (lit if lit_ else blob)(d, px_, py_, rx * s, ry * s, c, w * s, ang * f, seed + sd)

    def poly(pts, c, w=3.6, sd=1):
        inked(d, [L(*p) for p in pts], c, w * s, seed + sd, 0.8)

    def line(pts, c, w, sd=1, jit=0.4):
        stroke(d, [L(*p) for p in pts], c, w * s, seed + sd, jit)

    sw = math.sin(t * 2.2 + seed)
    # ---------------- legs and shoes
    hip_y = -140 if not kid else -128
    shoe = (46, 40, 48) if role not in ("doctor", "nurse") else (250, 250, 250)
    dress = fem and spec.get("dress") and not kid or (kid and fem)
    leg_col = skin_c if dress else bottom
    for sx in (-1, 1):
        sw_ = math.sin(gait + (0.0 if sx > 0 else math.pi)) * walk        # forward / back swing of this leg
        lift = max(0.0, math.cos(gait + (0.0 if sx > 0 else math.pi))) * 20 * walk
        fy = -bob / s                                                      # cancel the body bob so the feet stay on the ground
        foot = (sx * 25 + sw_ * 26, -14 - lift + fy)
        line([(sx * 22, hip_y), foot], INK, 34, 11 + sx)
        line([(sx * 22, hip_y), foot], leg_col, 26, 13 + sx)
        B(sx * 30 + sw_ * 26 + 14 * turn, -8 - lift + fy, 30 + 10 * turn, 13, shoe, 3.4, 0.0, 15 + sx, lit_=False)
    # ---------------- torso
    tw = (58 if not fem else 52) * (1 - 0.2 * turn)
    torso_col = spec.get("coat") or top
    if dress:
        poly([(-tw + 4, -150), (tw - 4, -150), (tw + 30, -66), (-tw - 30, -66)], torso_col if not spec.get("cardigan") else top, 3.8, 20)
        poly([(-tw - 30, -66), (tw + 30, -66), (tw + 26, -52), (-tw - 26, -52)], shade(torso_col, -0.22), 3.4, 21)
    if spec.get("coat") and role in ("doctor", "scientist", "judge", "firefighter", "stranger"):
        # long coat skirts hang below the waist
        poly([(-tw, -150), (tw, -150), (tw + 10, -54), (-tw - 10, -54)], spec["coat"], 3.8, 22)
    B(0, -214, tw, 78 if not kid else 66, torso_col, 4.0, 0.0, 23)
    if spec.get("coat") and top != spec["coat"]:   # shirt showing at the front
        poly([(-12, -285), (12, -285), (22, -160), (-22, -160)], top, 2.6, 24)
        line([(0, -285), (0, -150)], INK, 3.0, 25)
    if spec.get("cardigan"):
        poly([(-tw + 4, -280), (-14, -280), (-14, -150), (-tw + 2, -152)], spec["cardigan"], 3.2, 26)
        poly([(tw - 4, -280), (14, -280), (14, -150), (tw - 2, -152)], spec["cardigan"], 3.2, 27)
    if spec.get("vest"):
        poly([(-tw + 6, -278), (-14, -278), (-18, -152), (-tw + 4, -154)], spec["vest"], 3.2, 28)
        poly([(tw - 6, -278), (14, -278), (18, -152), (tw - 4, -154)], spec["vest"], 3.2, 29)
    if spec.get("bib"):
        poly([(-32, -262), (32, -262), (36, -152), (-36, -152)], spec["bib"], 3.4, 30)
        for sx in (-1, 1):
            line([(sx * 26, -262), (sx * 38, -290)], spec["bib"], 9, 31 + sx, 0.2)
    if spec.get("apron"):
        poly([(-34, -246), (34, -246), (42, -122), (-42, -122)], spec["apron"], 3.4, 33)
        poly([(-18, -246), (18, -246), (14, -270), (-14, -270)], spec["apron"], 3.0, 34)
    if spec.get("tie"):
        poly([(-9, -282), (9, -282), (13, -258), (0, -190), (-13, -258)], spec["tie"], 3.0, 35)
    if role == "waiter":
        poly([(-13, -284), (0, -270), (-13, -258)], spec["tie"], 2.6, 36)
        poly([(13, -284), (0, -270), (13, -258)], spec["tie"], 2.6, 37)
    if spec.get("collar"):
        poly([(-26, -282), (26, -282), (12, -214), (-12, -214)], spec["collar"], 3.0, 38)
    if spec.get("steth"):
        pts = [L(-20, -285)] + [L(-30 + k * 4, -285 + (k * 9)) for k in range(1, 6)] + [L(-6, -228)] + [L(18, -230)]
        stroke(d, pts, (60, 60, 70), 5 * s, seed + 39, 0.2)
        blob(d, *L(18, -224), 9 * s, 9 * s, (190, 190, 200), 2.6 * s, seed=seed + 40)
    if spec.get("badge"):
        poly([(24, -248), (36, -236), (32, -222), (16, -222), (12, -236)], (252, 214, 70), 2.4, 41)
    if spec.get("smudge"):
        blob(d, *L(-20, -190), 14 * s, 9 * s, shade(top, -0.3), 0, seed=seed + 42)
    # ---------------- neck and head
    hy = (-350 if not kid else -318) + nod
    hrx, hry = 62 * HS, 66 * HS
    poly([(-15, -292), (15, -292), (17, hy + 40), (-17, hy + 40)], shade(skin_c, -0.1), 3.0, 43)
    # back hair
    long_back = fem and not elder and not kid or (kid and fem and "bun" not in extras)
    if long_back:                                  # long hair: a mass behind the head and two locks falling beside the neck
        B(0, hy - 6, hrx + 12, hry + 12, hair_c, 4.0, 0.0, 44, lit_=False)
        for sx in (-1, 1):
            B(sx * (hrx + 2), hy + 58, 20, 62, hair_c, 3.8, 0.0, 44 + sx, lit_=False)
    # ears
    for sx in (-1, 1):
        B(sx * (hrx - 2), hy + 6, 14 * HS, 17 * HS, skin_c, 3.2, 0.0, 45 + sx, lit_=False)
    # head
    B(0, hy, hrx, hry, skin_c, 4.2, 0.0, 47)
    # ---------------- face
    shx[0] = 15 * turn
    ey, ex = hy - 6 * HS, 26 * HS
    er = 15 * HS
    px0, py0 = P(*L(0, ey))
    lw = max(1, int(S(E.lw_(3) * s)))
    wide = eye in ("wide", "spiral")
    for sx in (-1, 1):
        ecx, ecy = P(*L(sx * ex, ey))
        rx_, ry_ = er * (1.25 if wide else 1.0) * 1.05, er * (1.45 if wide else 1.22)
        if eye == "closed" or E.blink(t + 0.7 + sx * 0.0):
            d.arc([ecx - S(rx_ * s), ecy - S(ry_ * 0.7 * s), ecx + S(rx_ * s), ecy + S(ry_ * 0.7 * s)], 20, 160, fill=INK, width=lw + 1)
        elif eye == "happy":
            d.arc([ecx - S(rx_ * s), ecy - S(ry_ * 0.2 * s), ecx + S(rx_ * s), ecy + S(ry_ * 1.2 * s)], 200, 340, fill=INK, width=lw + 2)
        else:
            d.ellipse([ecx - S(rx_ * s), ecy - S(ry_ * s), ecx + S(rx_ * s), ecy + S(ry_ * s)], fill=(255, 255, 252), outline=INK, width=lw)
            if eye == "spiral":
                for k in range(14):
                    a1 = k * 0.9
                    r1 = (k + 1) * rx_ * 0.07 * s
                    d.line([(ecx + S(r1 * math.cos(a1)), ecy + S(r1 * math.sin(a1))), (ecx + S((r1 + rx_ * 0.07 * s) * math.cos(a1 + 0.9)), ecy + S((r1 + rx_ * 0.07 * s) * math.sin(a1 + 0.9)))], fill=INK, width=max(1, lw - 1))
            else:
                ox, oy = look[0] * 5 * f + f * 2, look[1] * 3
                pr = 0.55 if eye != "wide" else 0.34
                iris = (84, 52, 30) if skin in ("brown", "dark") else (60, 110, 160) if hair in ("blonde", "red") else (70, 54, 40)
                d.ellipse([ecx - S(rx_ * 0.66 * s) + ox, ecy - S(ry_ * 0.74 * s) + oy, ecx + S(rx_ * 0.66 * s) + ox, ecy + S(ry_ * 0.74 * s) + oy], fill=iris)
                d.ellipse([ecx - S(rx_ * 0.36 * s * (pr + 0.5)) + ox, ecy - S(ry_ * 0.5 * s) + oy, ecx + S(rx_ * 0.36 * s * (pr + 0.5)) + ox, ecy + S(ry_ * 0.5 * s) + oy], fill=(18, 12, 10))
                d.ellipse([ecx - S(rx_ * 0.3 * s) + ox, ecy - S(ry_ * 0.5 * s) + oy, ecx - S(rx_ * 0.05 * s) + ox, ecy - S(ry_ * 0.22 * s) + oy], fill=(255, 255, 255))
            if eye == "half":
                d.polygon([(ecx - S(rx_ * s), ecy - S(ry_ * s)), (ecx + S(rx_ * s), ecy - S(ry_ * s)), (ecx + S(rx_ * s), ecy - S(ry_ * 0.05 * s)), (ecx - S(rx_ * s), ecy - S(ry_ * 0.05 * s))], fill=shade(skin_c, -0.04))
                d.line([(ecx - S(rx_ * s), ecy - S(ry_ * 0.05 * s)), (ecx + S(rx_ * s), ecy - S(ry_ * 0.05 * s))], fill=INK, width=lw + 1)
        a_, b_ = (brow[0], brow[1]) if sx > 0 else (brow[1], brow[0])
        line([(sx * ex - 18, ey - 28 + a_), (sx * ex, ey - 32 + (a_ + b_) / 2), (sx * ex + 18, ey - 26 + b_)] if sx > 0 else
             [(sx * ex + 18, ey - 28 + a_), (sx * ex, ey - 32 + (a_ + b_) / 2), (sx * ex - 18, ey - 26 + b_)], shade(hair_c, -0.1) if not elder else (130, 130, 138), 6.0, 50 + sx, 0.3)
        if tear > 0 and sx > 0:
            tx_, ty_ = P(*L(sx * ex + 4, ey + 24 + tear * 56))
            d.ellipse([tx_ - S(7 * s), ty_ - S(12 * s), tx_ + S(7 * s), ty_ + S(12 * s)], fill=(150, 200, 235), outline=INK)
    # nose, cheeks, mouth
    B(f * 3, hy + 20 * HS, 9 * HS, 8 * HS, shade(skin_c, -0.14), 2.6, 0.0, 53, lit_=False)
    if mood in ("happy", "smug") or eye == "happy":
        for sx in (-1, 1):
            B(sx * 40 * HS, hy + 28 * HS, 12 * HS, 8 * HS, (250, 150, 150), 0, 0.0, 54 + sx, lit_=False)
    my = hy + 44 * HS
    if talk > 0 or eye == "wide" and mood != "happy":
        o = max(talk * (0.55 + 0.45 * math.sin(t * 17.0 + seed) ** 2), 0.45 if eye == "wide" else 0)
        poly([(-20, my - 2), (20, my - 2), (16, my + 6 + 26 * o), (-16, my + 6 + 26 * o)], (110, 30, 40), 3.0, 56)
        if o > 0.5:
            poly([(-12, my + 6 + 26 * o - 4), (12, my + 6 + 26 * o - 4), (8, my + 6 + 26 * o), (-8, my + 6 + 26 * o)], (240, 110, 120), 0, 57)
    elif mood in ("happy",) or eye == "happy":
        line([(-22, my - 4), (-10, my + 12), (10, my + 12), (22, my - 4)], INK, 4.0, 58, 0.2)
    elif mood == "smug":
        line([(-18, my + 4), (4, my + 8), (22, my - 6)], INK, 4.0, 58, 0.2)
    elif mood in ("angry", "sad", "scared", "shocked"):
        line([(-20, my + 10), (0, my - 2), (20, my + 10)], INK, 4.0, 58, 0.2)
    else:
        line([(-16, my + 3), (16, my + 3)], INK, 3.6, 58, 0.2)
    # facial hair
    if "mustache" in extras or "beard" in extras or role in ("grandfather",) and fem is False:
        poly([(-26, my - 6), (-6, my - 12), (0, my - 6), (6, my - 12), (26, my - 6), (16, my + 2), (0, my - 2), (-16, my + 2)], hair_c, 3.0, 59)
    if "beard" in extras:
        poly([(-hrx + 8, my - 10), (hrx - 8, my - 10), (hrx - 14, my + 46), (0, my + 62), (-hrx + 14, my + 46)], hair_c, 3.4, 60)
    # glasses
    if spec.get("glasses") or "glasses" in extras:
        for sx in (-1, 1):
            gx, gy = P(*L(sx * ex, ey))
            d.ellipse([gx - S(26 * s * HS), gy - S(24 * s * HS), gx + S(26 * s * HS), gy + S(24 * s * HS)], outline=(40, 34, 40), width=lw + 1)
        line([(-ex + 26 * HS, ey), (ex - 26 * HS, ey)], (40, 34, 40), 3.4, 61, 0.1)
    # ---------------- front hair
    hat = spec.get("hat")
    hat_hides = hat in ("hard", "fire", "police", "nurse", "chef", "cap", "bucket", "sun", "straw", "beret", "flatcap")
    if not (elder and fem is False and hair == "bald") and "bald" not in extras:
        cap = _arc(0, hy - 2, hrx + 4, hry + 6, 196, 344)
        if fem:
            fr = cap + [(hrx - 4, hy - 20), (hrx * 0.4, hy - 42), (0, hy - 24), (-hrx * 0.4, hy - 46), (-hrx + 4, hy - 18)]
            poly(fr, hair_c, 3.8, 62)
            if elder or "bun" in extras:
                B(0, hy - hry - 22, 30, 26, hair_c, 3.6, 0.0, 63, lit_=False)
        else:
            fr = cap + [(hrx - 6, hy - 26), (hrx * 0.5, hy - 34), (0, hy - 22), (-hrx * 0.45, hy - 36), (-hrx + 6, hy - 22)]
            if not hat_hides or hat in ("cap", "flatcap", "bucket", "beret"):
                poly(fr, hair_c, 3.8, 62)
    # ---------------- hat
    top_y = hy - hry
    cc = spec.get("capcol", (200, 60, 60))
    if hat == "chef":
        poly([(-hrx * 0.78, top_y + 14), (hrx * 0.78, top_y + 14), (hrx * 0.84, top_y - 20), (hrx * 0.5, top_y - 74), (0, top_y - 90), (-hrx * 0.5, top_y - 74), (-hrx * 0.84, top_y - 20)], (252, 252, 250), 3.8, 64)
        poly([(-hrx * 0.78, top_y + 14), (hrx * 0.78, top_y + 14), (hrx * 0.78, top_y + 2), (-hrx * 0.78, top_y + 2)], (232, 232, 236), 3.0, 65)
    elif hat in ("cap", "flatcap"):
        poly(_arc(0, top_y + 28, hrx + 2, 50, 190, 350) + [(hrx - 2, top_y + 26), (-hrx + 2, top_y + 26)], cc, 3.8, 64)
        poly([(0, top_y + 24), (hrx + 40, top_y + 30), (hrx + 40, top_y + 42), (0, top_y + 40)], shade(cc, -0.2), 3.4, 65)
    elif hat == "police":
        poly(_arc(0, top_y + 30, hrx + 4, 52, 190, 350) + [(hrx, top_y + 30), (-hrx, top_y + 30)], (40, 52, 96), 3.8, 64)
        poly([(-hrx - 4, top_y + 28), (hrx + 4, top_y + 28), (hrx + 30, top_y + 44), (-hrx - 30, top_y + 44)], (30, 30, 40), 3.4, 65)
        poly([(-8, top_y + 6), (8, top_y + 6), (10, top_y + 24), (0, top_y + 30), (-10, top_y + 24)], (252, 214, 70), 2.4, 66)
    elif hat in ("hard", "fire"):
        col = (250, 210, 40) if hat == "hard" else (210, 50, 50)
        poly(_arc(0, top_y + 30, hrx + 6, 60, 188, 352) + [(hrx, top_y + 30), (-hrx, top_y + 30)], col, 3.8, 64)
        poly([(-hrx - 14, top_y + 26), (hrx + 14, top_y + 26), (hrx + 14, top_y + 40), (-hrx - 14, top_y + 40)], shade(col, -0.2), 3.4, 65)
        poly([(-8, top_y - 22), (8, top_y - 22), (8, top_y + 28), (-8, top_y + 28)], shade(col, -0.2), 2.4, 66)
    elif hat == "nurse":
        poly([(-hrx * 0.7, top_y + 22), (hrx * 0.7, top_y + 22), (hrx * 0.62, top_y - 14), (-hrx * 0.62, top_y - 14)], (252, 252, 252), 3.6, 64)
        poly([(-5, top_y - 8), (5, top_y - 8), (5, top_y + 18), (-5, top_y + 18)], (220, 50, 60), 0, 65)
        poly([(-14, top_y + 2), (14, top_y + 2), (14, top_y + 8), (-14, top_y + 8)], (220, 50, 60), 0, 66)
    elif hat in ("straw", "sun"):
        col = (236, 200, 110) if hat == "straw" else (250, 240, 200)
        B(0, top_y + 30, hrx + 56, 18, col, 3.8, 0.0, 64, lit_=False)
        poly(_arc(0, top_y + 28, hrx - 8, 40, 190, 350) + [(hrx - 10, top_y + 28), (-hrx + 10, top_y + 28)], col, 3.6, 65)
        poly([(-hrx + 8, top_y + 22), (hrx - 8, top_y + 22), (hrx - 8, top_y + 32), (-hrx + 8, top_y + 32)], (200, 70, 60), 2.4, 66)
    elif hat == "bucket":
        poly(_arc(0, top_y + 28, hrx + 4, 44, 190, 350) + [(hrx + 4, top_y + 34), (-hrx - 4, top_y + 34)], (250, 200, 50), 3.8, 64)
        B(0, top_y + 36, hrx + 28, 12, shade((250, 200, 50), -0.1), 3.4, 0.0, 65, lit_=False)
    elif hat == "beret":
        B(f * 8, top_y + 12, hrx * 0.9, 24, cc, 3.8, -0.1, 64, lit_=False)
        poly([(f * 8 - 4, top_y - 16), (f * 8 + 4, top_y - 16), (f * 8 + 3, top_y - 6), (f * 8 - 3, top_y - 6)], shade(cc, -0.3), 2.4, 65)
    shx[0] = 0.0
    # ---------------- arms
    sh = -268 if not kid else -240
    pose = action
    if pose == "stand" and walk <= 0.3:            # a walking person swings their arms whatever their mood
        pose = {"shocked": "up", "scared": "up", "angry": "hips", "sad": "limp", "happy": "wave", "smug": "hips"}.get(mood, "stand")
    near = 1                                 # the arm on the side the person faces
    hands = {}
    for sx in (-1, 1):
        ax, ay = sx * (tw + 2), sh + 6
        sway_ = 0.0
        if pose == "stand":
            asw = math.sin(gait + (math.pi if sx > 0 else 0.0)) * walk
            ex_, ey_, hx_, hy_ = ax + sx * 18 + asw * 8, ay + 62, ax + sx * 26 + asw * 20, ay + 128 + sw * 4 * sx - abs(asw) * 6
        elif pose == "limp":
            ex_, ey_, hx_, hy_ = ax + sx * 6, ay + 70, ax + sx * 10, ay + 138
        elif pose == "talk":
            if sx == near:
                g_ = math.sin(t * 6.0 + seed)
                ex_, ey_, hx_, hy_ = ax + 30, ay + 44, ax + 58, ay - 26 + g_ * 18
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
        pts = [(ax, ay), (ex_, ey_), (hx_, hy_ - 12)]
        line(pts, INK, 31, 70 + sx, 0.3)
        line(pts, sleeve, 23, 72 + sx, 0.3)
        B(hx_, hy_, 15, 15, skin_c, 3.2, 0.0, 74 + sx, lit_=False)
    # held item (in the near hand)
    item = None if carry == "none" else (carry or spec.get("tool"))
    if item:
        hx_, hy_ = hands[near]
        _item(d, L, item, hx_, hy_, s, f, seed)


def _item(d, L, item, hx, hy, s, f, seed):
    """a small prop in the hand at (hx, hy) (character units)"""
    def poly(pts, c, w=3.2, sd=1):
        inked(d, [L(*p) for p in pts], c, w * s, seed + 80 + sd, 0.6)

    def ell(cx, cy, rx, ry, c, w=3.2, sd=1):
        blob(d, *L(cx, cy), rx * s, ry * s, c, w * s, seed=seed + 90 + sd)

    def ln(pts, c, w, sd=1):
        stroke(d, [L(*p) for p in pts], c, w * s, seed + 100 + sd, 0.3)

    if item == "book":
        poly([(hx - 6, hy - 30), (hx + 40, hy - 30), (hx + 40, hy + 6), (hx - 6, hy + 6)], (190, 70, 70), 3.2, 1)
        poly([(hx - 2, hy - 26), (hx + 36, hy - 26), (hx + 36, hy + 2), (hx - 2, hy + 2)], (250, 244, 222), 0, 2)
    elif item in ("clipboard", "paper"):
        poly([(hx - 4, hy - 38), (hx + 34, hy - 38), (hx + 34, hy + 6), (hx - 4, hy + 6)], (190, 150, 100) if item == "clipboard" else (252, 252, 248), 3.2, 3)
        for k in range(3):
            ln([(hx + 2, hy - 28 + k * 11), (hx + 28, hy - 28 + k * 11)], (110, 110, 120), 2.4, k)
    elif item == "tray":
        ell(hx + 10, hy - 14, 54, 8, (200, 204, 212), 3.4, 4)
        poly([(hx + 14, hy - 44), (hx + 38, hy - 44), (hx + 34, hy - 20), (hx + 18, hy - 20)], (250, 250, 246), 3.0, 5)
    elif item == "wrench":
        ln([(hx, hy + 6), (hx + 16, hy - 62)], (150, 156, 168), 10, 6)
        ell(hx + 18, hy - 70, 14, 12, (150, 156, 168), 3.2, 7)
    elif item == "rolling_pin":
        ln([(hx - 22, hy - 6), (hx + 42, hy - 26)], (200, 150, 90), 16, 8)
    elif item == "pan":
        ell(hx + 22, hy - 30, 28, 14, (80, 80, 92), 3.4, 9)
        ln([(hx, hy), (hx + 8, hy - 22)], (60, 60, 70), 8, 9)
    elif item == "pitchfork":
        ln([(hx, hy + 20), (hx + 6, hy - 130)], (150, 110, 70), 9, 10)
        for k in (-14, 0, 14):
            ln([(hx + 6 + k, hy - 126), (hx + 6 + k, hy - 160)], (170, 176, 188), 5, 11 + k)
    elif item == "hose":
        ln([(hx, hy), (hx + 26, hy - 14), (hx + 56, hy + 20)], (200, 50, 50), 14, 12)
    elif item == "gavel":
        ln([(hx, hy - 4), (hx + 22, hy - 40)], (150, 100, 60), 9, 13)
        poly([(hx + 4, hy - 56), (hx + 40, hy - 40), (hx + 34, hy - 26), (hx - 2, hy - 42)], (120, 78, 46), 3.2, 14)
    elif item in ("letter", "bag"):
        poly([(hx - 4, hy - 26), (hx + 40, hy - 26), (hx + 40, hy + 6), (hx - 4, hy + 6)], (252, 252, 246) if item == "letter" else (150, 110, 70), 3.2, 15)
        if item == "letter":
            ln([(hx - 4, hy - 26), (hx + 18, hy - 8), (hx + 40, hy - 26)], (150, 150, 160), 2.4, 16)
    elif item == "comb":
        poly([(hx, hy - 24), (hx + 38, hy - 24), (hx + 38, hy - 10), (hx, hy - 10)], (40, 40, 56), 3.0, 17)
    elif item == "brush":
        ln([(hx - 10, hy + 6), (hx + 26, hy - 56)], (150, 100, 60), 7, 18)
        ell(hx + 30, hy - 62, 8, 12, (230, 70, 100), 3.0, 19)
    elif item == "flask":
        poly([(hx + 6, hy - 52), (hx + 26, hy - 52), (hx + 26, hy - 30), (hx + 40, hy), (hx - 8, hy)], (150, 230, 190), 3.4, 20)
    elif item == "watering_can":
        poly([(hx - 6, hy - 34), (hx + 36, hy - 34), (hx + 36, hy + 8), (hx - 6, hy + 8)], (70, 150, 90), 3.4, 21)
        ln([(hx + 36, hy - 20), (hx + 62, hy - 38)], (70, 150, 90), 8, 22)
    elif item == "hammer":
        ln([(hx, hy + 6), (hx + 14, hy - 56)], (160, 110, 70), 9, 23)
        poly([(hx - 6, hy - 70), (hx + 36, hy - 70), (hx + 36, hy - 52), (hx - 6, hy - 52)], (120, 124, 136), 3.4, 24)
    elif item == "fish":
        ell(hx + 22, hy - 26, 34, 14, (150, 190, 220), 3.4, 25)
        poly([(hx + 54, hy - 26), (hx + 74, hy - 42), (hx + 74, hy - 10)], (130, 170, 210), 3.0, 26)
    elif item == "camera":
        poly([(hx - 4, hy - 36), (hx + 40, hy - 36), (hx + 40, hy - 4), (hx - 4, hy - 4)], (60, 60, 70), 3.4, 27)
        ell(hx + 18, hy - 20, 10, 10, (170, 200, 230), 3.0, 28)
    elif item == "phone":
        poly([(hx, hy - 36), (hx + 22, hy - 36), (hx + 22, hy), (hx, hy)], (50, 54, 70), 3.0, 29)
    elif item == "cane":
        ln([(hx, hy + 120), (hx + 4, hy - 20)], (130, 90, 60), 8, 30)
    elif item == "cake":
        poly([(hx - 10, hy - 30), (hx + 40, hy - 30), (hx + 40, hy), (hx - 10, hy)], (240, 190, 210), 3.4, 31)
        ell(hx + 15, hy - 34, 8, 8, (220, 40, 60), 2.6, 32)
    elif item == "umbrella":
        ln([(hx, hy + 20), (hx, hy - 110)], (60, 60, 70), 6, 33)
        poly([(hx - 70, hy - 100), (hx + 70, hy - 100), (hx + 40, hy - 150), (hx - 40, hy - 150)], (210, 60, 70), 3.6, 34)
    elif item == "baguette":
        ln([(hx - 10, hy), (hx + 54, hy - 52)], (220, 170, 100), 18, 35)
    elif item == "cup":
        poly([(hx, hy - 30), (hx + 24, hy - 30), (hx + 20, hy), (hx + 4, hy)], (250, 250, 246), 3.0, 36)
