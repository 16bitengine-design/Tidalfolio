"""Set dressing for the vector worlds: the small things that make a place feel lived in, and the things that move in the background
(a clock that really tells time, steam, dust in the light, birds, traffic, people far away). Every story gets its own variation
(seed), so two bakeries from two stories are not the same room.
Drawn in world coordinates under the stage camera; people are drawn after, so they always stay in front."""
import math
import random

import skia

from . import vector as V
from .vector import BUILD, GROUND, dark, lite, mixc, paint, lin, rad


def _dim(c, T, k=0.45):
    return mixc(c, (40, 30, 110), T["dim"] * k)


def clock(x, y, r, t, T, seed=0):
    """a wall clock whose hands really move"""
    V.oval(x + 5, y + 8, r + 8, r + 8, paint((40, 20, 90), 60, blur=6))
    V.oval(x, y, r + 10, r + 10, paint(_dim((236, 150, 100), T)))
    V.oval(x, y, r, r, paint(shader=rad(x - r * 0.3, y - r * 0.3, r * 1.6, [(0, (255, 252, 244)), (1, (232, 226, 236))])))
    for k in range(12):
        a = k * math.pi / 6
        V.line(x + math.sin(a) * r * 0.82, y - math.cos(a) * r * 0.82, x + math.sin(a) * r * 0.94, y - math.cos(a) * r * 0.94, (70, 56, 110), 4 if k % 3 else 7)
    m = (t * 0.2 + seed * 7) % 60 / 60 * math.tau
    h = (seed * 0.9 + t * 0.0167) % 12 / 12 * math.tau
    V.line(x, y, x + math.sin(h) * r * 0.5, y - math.cos(h) * r * 0.5, (70, 56, 110), 7)
    V.line(x, y, x + math.sin(m) * r * 0.76, y - math.cos(m) * r * 0.76, (70, 56, 110), 5)
    V.oval(x, y, 6, 6, paint((236, 90, 100)))


def plant(x, y, s, t, T, pot=(236, 120, 110), seed=0, kind="leafy"):
    """a potted plant that sways a little"""
    pot = _dim(pot, T)
    V.rrect(x - 36 * s, y - 62 * s, x + 36 * s, y, 8 * s, paint(shader=lin(x - 36 * s, 0, x + 36 * s, 0, [(0, lite(pot, 0.25)), (1, dark(pot, 0.2))])))
    V.rrect(x - 42 * s, y - 74 * s, x + 42 * s, y - 56 * s, 7 * s, paint(dark(pot, 0.1)))
    n = 7 if kind == "leafy" else 5
    for k in range(n):
        a = -1.25 + k * (2.5 / (n - 1)) + math.sin(t * 0.9 + k + seed) * 0.05
        L = (96 + (k % 3) * 26) * s
        tipx, tipy = x + math.sin(a) * L, y - 70 * s - math.cos(a) * L * 0.95
        c = _dim((70, 190, 120) if k % 2 else (120, 218, 130), T)
        V.poly([(x - 9 * s, y - 70 * s), (x + 9 * s, y - 70 * s), (tipx + 12 * s * math.cos(a), tipy + 12 * s * math.sin(a)), (tipx, tipy)], paint(c))
        V.line(x, y - 70 * s, (x + tipx) / 2, (y - 70 * s + tipy) / 2, lite(c, 0.3), 3 * s, 140)


def steam(x, y, t, T, n=3, h=130, w=14):
    """wisps rising from something warm"""
    for k in range(n):
        ph = ((t * 0.45 + k / n) % 1.0)
        pts = [(x + (k - 1) * 22 + math.sin(ph * 6 + k) * w * (j / 4), y - ph * h - j * 22) for j in range(5)]
        V.curve(pts, paint((255, 255, 255), int(150 * math.sin(ph * math.pi)), stroke=9 + 4 * ph, blur=3))


def pendant(x, y0, y1, T, c=(255, 214, 120), lit=True):
    V.line(x, y0, x, y1, (80, 60, 110), 4)
    V.poly([(x - 14, y1), (x + 14, y1), (x + 56, y1 + 50), (x - 56, y1 + 50)], paint(shader=lin(x - 56, 0, x + 56, 0, [(0, lite(c, 0.2)), (1, dark(c, 0.2))])))
    V.oval(x, y1 + 52, 56, 9, paint(lite(c, 0.7)))
    if lit:
        V.glow(x, y1 + 70, 190, T["warm"], 90 if T["dim"] > 0.2 else 45)


def frame_pic(x, y, w, h, c1, c2, T, kind=0):
    V.rrect(x - 10, y - 10, x + w + 10, y + h + 10, 8, paint(_dim((255, 246, 232), T)))
    V.rect(x, y, x + w, y + h, paint(shader=lin(x, y, x + w, y + h, [(0, _dim(c1, T)), (1, _dim(c2, T))])))
    if kind == 0:                         # sun over hills
        V.oval(x + w * 0.7, y + h * 0.3, w * 0.12, w * 0.12, paint((255, 236, 150)))
        V.smooth([(x, y + h), (x, y + h * 0.7), (x + w * 0.3, y + h * 0.5), (x + w * 0.6, y + h * 0.72), (x + w, y + h * 0.6), (x + w, y + h)], paint(_dim((90, 180, 130), T)))
    elif kind == 1:                       # abstract blobs
        V.oval(x + w * 0.35, y + h * 0.45, w * 0.24, h * 0.2, paint((255, 255, 255), 170))
        V.oval(x + w * 0.68, y + h * 0.6, w * 0.16, h * 0.16, paint((255, 214, 120), 220))
    else:                                 # a little house
        V.rect(x + w * 0.3, y + h * 0.5, x + w * 0.7, y + h * 0.9, paint(_dim((255, 230, 200), T)))
        V.poly([(x + w * 0.25, y + h * 0.5), (x + w * 0.5, y + h * 0.22), (x + w * 0.75, y + h * 0.5)], paint(_dim((236, 100, 110), T)))


def dust(T, t, region=(-100, 260, 1180, 1180), n=46, seed=0):
    """motes floating in the light of the room"""
    if T["dim"] > 0.25:
        return
    r = random.Random(seed)
    x0, y0, x1, y1 = region
    for _ in range(n):
        bx, by, ph, sp = r.uniform(x0, x1), r.uniform(y0, y1), r.uniform(0, 6.28), r.uniform(0.2, 0.6)
        x = bx + math.sin(t * sp + ph) * 24
        y = (by - t * 12 * sp) % (y1 - y0) + y0
        a = 90 + 80 * math.sin(t * 1.3 + ph)
        V.oval(x, y, 3.2, 3.2, paint((255, 248, 220), int(max(30, a)), blur=1.2))


def bread_basket(x, y, s, T, kind=0):
    c = _dim((196, 140, 90), T)
    V.rrect(x - 70 * s, y - 40 * s, x + 70 * s, y, 14 * s, paint(shader=lin(0, y - 40 * s, 0, y, [(0, lite(c, 0.2)), (1, dark(c, 0.25))])))
    for k in range(5):
        V.line(x - 62 * s + k * 31 * s, y - 36 * s, x - 66 * s + k * 33 * s, y - 4 * s, dark(c, 0.25), 3, 130)
    for k in range(3):
        bx = x - 40 * s + k * 40 * s
        if kind == 0:                     # baguettes
            V.line(bx - 10 * s, y - 36 * s, bx + 8 * s, y - 112 * s, _dim((232, 170, 96), T), 24 * s)
            V.line(bx - 14 * s, y - 40 * s, bx + 4 * s, y - 112 * s, lite(_dim((232, 170, 96), T), 0.3), 6 * s, 160)
        else:                             # round loaves
            V.oval(bx, y - 52 * s, 28 * s, 22 * s, paint(shader=rad(bx - 8, y - 62 * s, 44 * s, [(0, _dim((255, 214, 140), T)), (1, _dim((206, 128, 70), T))])))


def shop_dressing(T, t, seed):
    lit = T["dim"] > 0.2
    left = seed % 2 == 0
    # chalk menu board
    bx = 190 if left else 560
    V.rrect(bx - 14, 320, bx + 366, 730, 14, paint(_dim((190, 120, 86), T)))
    V.rrect(bx, 334, bx + 352, 716, 8, paint(shader=lin(0, 334, 0, 716, [(0, _dim((52, 110, 112), T)), (1, _dim((36, 80, 100), T))])))
    r = random.Random(seed + 9)
    for k in range(5):
        y = 420 + k * 56
        w = r.uniform(120, 210)
        V.line(bx + 36, y, bx + 36 + w, y + r.uniform(-3, 3), (255, 252, 240), 7, 210)
        V.line(bx + 290, y, bx + 316, y, (255, 236, 150), 7, 210)
    V.line(bx + 40, 372, bx + 190, 372, (255, 214, 120), 9, 230)                      # heading
    for k in range(4):                                                              # a doodled wheat ear
        V.oval(bx + 270 + (k % 2) * 14, 364 - k * 0, 7, 12, paint((255, 232, 150), 220))
    # clock and a picture
    clock(660 if left else 140, 300, 66, t, T, seed)
    frame_pic(700 if left else 90, 400, 150, 190, (255, 196, 140), (236, 130, 150), T, seed % 3)
    # pendant lamps
    for x in (230, 560, 880):
        pendant(x, 240, 330 + (x // 40 % 3) * 20, T, lit=lit)
    # on the counter
    bread_basket(820, 1040, 0.9, T, seed % 2)
    steam(380, 1000, t, T, 3, 150)
    V.rrect(140, 1000, 330, 1032, 8, paint(_dim((190, 150, 120), T)))                # tray of croissants
    for k in range(4):
        cx = 170 + k * 46
        V.oval(cx, 986, 22, 15, paint(_dim((236, 170, 90), T)))
        V.line(cx - 10, 978, cx - 4, 996, _dim((196, 120, 60), T), 3)
    # flour sacks and a plant by the window
    for sx, sy in ((-90, GROUND - 6), (-10, GROUND - 6)):
        V.rrect(sx - 44, sy - 96, sx + 44, sy, 16, paint(shader=lin(sx - 44, 0, sx + 44, 0, [(0, _dim((250, 240, 222), T)), (1, _dim((214, 200, 190), T))])))
        V.rrect(sx - 28, sy - 70, sx + 28, sy - 44, 6, paint(_dim((236, 100, 110), T), 200))
    plant(1090 if left else 700, 930, 0.9, t, T, (236, 120, 110), seed)
    dust(T, t, seed=seed)


def kitchen_dressing(T, t, seed):
    lit = T["dim"] > 0.2
    clock(240 if seed % 2 else 820, 250, 62, t, T, seed)
    for x in (260, 560, 860):                                                       # hanging pots on a rail
        pass
    V.rrect(-60, 224, 520, 238, 6, paint((120, 100, 130)))
    for k in range(5):
        x = -20 + k * 100
        V.line(x, 236, x, 270, (120, 100, 130), 4)
        c = [(236, 98, 120), (255, 170, 80), (96, 190, 190), (150, 120, 240), (255, 214, 110)][k]
        V.oval(x, 316, 38, 40, paint(shader=rad(x - 10, 300, 64, [(0, lite(_dim(c, T), 0.3)), (1, dark(_dim(c, T), 0.2))])))
    # stove with a steaming pot and a fruit bowl
    V.rrect(600, 968, 860, 1012, 10, paint(_dim((70, 70, 100), T)))
    V.rrect(640, 880, 820, 968, 12, paint(shader=lin(0, 880, 0, 968, [(0, lite(_dim((236, 98, 120), T), 0.2)), (1, dark(_dim((236, 98, 120), T), 0.2))])))
    V.rrect(628, 870, 832, 890, 8, paint(dark(_dim((236, 98, 120), T), 0.2)))
    steam(730, 860, t, T, 3, 170)
    for k in range(5):                                                              # fruit bowl
        c = [(240, 80, 90), (255, 190, 60), (120, 210, 90), (255, 130, 70), (240, 80, 90)][k]
        V.oval(1000 + (k % 3) * 36 - 20, 966 - (k // 3) * 26, 24, 24, paint(shader=rad(990 + (k % 3) * 36, 950, 40, [(0, lite(c, 0.4)), (1, dark(c, 0.15))])))
    V.rrect(940, 970, 1130, 1006, 14, paint(_dim((236, 170, 96), T)))
    plant(70, 1008, 0.8, t, T, (255, 170, 80), seed)
    for x in (360, 780):
        pendant(x, 200, 300, T, (255, 190, 120), lit)
    frame_pic(900, 340, 130, 170, (255, 214, 140), (236, 130, 150), T, 2)
    dust(T, t, seed=seed)


def office_dressing(T, t, seed):
    lit = T["dim"] > 0.2
    clock(620, 330, 58, t, T, seed)
    V.rrect(40, 760, 110, 900, 12, paint(_dim((190, 210, 240), T)))                 # water cooler
    V.rrect(48, 640, 102, 770, 16, paint((190, 236, 250, 200)))
    V.oval(75, 700, 20, 36, paint((160, 214, 250), 160))
    frame_pic(520, 760, 200, 130, (170, 190, 250), (230, 150, 230), T, 1)
    for k in range(3):                                                              # sticky notes on a board
        V.rect(780 + k * 62, 340, 780 + k * 62 + 50, 392, paint(_dim([(255, 232, 110), (255, 160, 180), (150, 230, 190)][k], T)))
    V.rect(150, 880, 170, 950, paint(_dim((90, 90, 130), T)))                        # desk lamp
    V.line(160, 880, 220, 820, _dim((90, 90, 130), T), 8)
    V.poly([(200, 800), (250, 800), (270, 840), (186, 840)], paint(_dim((255, 214, 110), T)))
    if lit:
        V.glow(228, 850, 220, T["warm"], 120)
    V.rrect(440, 1030, 510, 1090, 8, paint(_dim((255, 255, 255), T)))                 # mug with steam
    steam(475, 1020, t, T, 2, 90, 8)
    for k in range(6):                                                              # stack of papers
        V.rrect(560, 1076 - k * 8, 700 + (k % 2) * 6, 1086 - k * 8, 3, paint(_dim((250, 248, 240), T)))
    for x in (160, 540, 920):
        pendant(x, 180, 260, T, (255, 244, 220), lit)
    dust(T, t, seed=seed)


def classroom_dressing(T, t, seed):
    clock(830, 250, 62, t, T, seed)
    for k in range(9):                                                              # alphabet cards along the wall
        c = BUILD[k % len(BUILD)]
        V.rrect(-300 + k * 150, 300, -300 + k * 150 + 110, 380, 10, paint(_dim(c, T)))
        V.line(-300 + k * 150 + 24, 360, -300 + k * 150 + 55, 322, (255, 255, 255), 9, 230)
        V.line(-300 + k * 150 + 55, 322, -300 + k * 150 + 86, 360, (255, 255, 255), 9, 230)
    for k in range(6):                                                              # books on the desk
        V.rrect(30 + k * 24, 1030 - 70 - (k % 2) * 6, 30 + k * 24 + 20, 1030, 3, paint(_dim(BUILD[(k + 2) % len(BUILD)], T)))
    V.rrect(540, 940, 600, 1030, 8, paint(_dim((236, 98, 120), T)))                  # pencil cup
    for k in range(4):
        V.line(556 + k * 12, 940, 552 + k * 14, 900, _dim((255, 214, 80), T), 5)
    frame_pic(760, 560, 160, 130, (170, 220, 250), (130, 190, 240), T, 0)
    plant(1000, 1010, 0.8, t, T, (255, 190, 100), seed)
    dust(T, t, seed=seed)


def home_dressing(T, t, seed):
    clock(560, 250, 56, t, T, seed)
    V.rrect(-120, 940, 200, 1110, 14, paint(_dim((190, 130, 100), T)))                # a bookcase
    for k in range(5):
        V.rrect(-100 + k * 36, 880 - (k % 2) * 10, -100 + k * 36 + 28, 940, 4, paint(_dim(BUILD[(k + 1) % len(BUILD)], T)))
    plant(260, 1100, 1.0, t, T, (236, 120, 110), seed)
    steam(330, 1040, t, T, 2, 90, 10)
    V.rrect(300, 1036, 360, 1090, 8, paint(_dim((255, 252, 244), T)))                 # a cup of tea on a table
    dust(T, t, seed=seed)


def outdoor_dressing(T, t, seed, park=False):
    """life in the distance: birds, far-away walkers, traffic, bunting, benches"""
    r = random.Random(seed)
    # birds crossing the sky
    V.cam(0.3)
    for k in range(4):
        x = (t * (46 + k * 9) + k * 480 + seed * 37) % 2200 - 500
        y = 260 + k * 70 + math.sin(t * 0.7 + k) * 24
        flap = math.sin(t * 9 + k * 2) * 11
        V.curve([(x - 20, y - 4 - flap), (x, y + 4), (x + 20, y - 4 - flap)], paint(_dim((70, 60, 120), T, 0.4), stroke=4.5))
    if not park:
        # traffic on the far road
        V.cam(0.8)
        for k, c in enumerate(((240, 90, 110), (80, 190, 190), (255, 190, 70))):
            x = ((t * (120 + k * 30) + k * 780) % 2800) - 700 if k % 2 == 0 else 2100 - ((t * (100 + k * 25) + k * 600) % 2800)
            cc = _dim(c, T)
            V.rrect(x - 70, 1150, x + 70, 1196, 18, paint(shader=lin(0, 1150, 0, 1196, [(0, lite(cc, 0.2)), (1, dark(cc, 0.2))])))
            V.rrect(x - 40, 1120, x + 36, 1156, 14, paint(lite(cc, 0.25)))
            V.rrect(x - 32, 1126, x - 4, 1150, 6, paint((200, 236, 252, 220)))
            V.rrect(x + 2, 1126, x + 30, 1150, 6, paint((200, 236, 252, 220)))
            for wx in (-38, 38):
                V.oval(x + wx, 1198, 17, 17, paint((60, 54, 90)))
            if T["dim"] > 0.2:
                V.glow(x + (70 if k % 2 == 0 else -70), 1170, 60, (255, 240, 170), 140)
        # far-away people strolling
        for k in range(5):
            x = ((t * (16 + k * 3) + k * 520) % 2600) - 500
            c = _dim(r.choice(BUILD), T, 0.5)
            sw = math.sin(t * 5 + k) * 6
            V.line(x - 4, 1196, x - 4 + sw, 1236, (70, 60, 110), 7)
            V.line(x + 4, 1196, x + 4 - sw, 1236, (70, 60, 110), 7)
            V.rrect(x - 12, 1134, x + 12, 1204, 10, paint(c))
            V.oval(x, 1118, 12, 13, paint(_dim((236, 190, 150), T)))
    # bunting between the lamp posts
    V.cam(1.0)
    pts = [(-200 + i * 110, 760 + 50 * math.sin(i / 8 * math.pi)) for i in range(0, 15)]
    V.curve(pts, paint((120, 100, 130), stroke=4))
    for i, (px, py) in enumerate(pts[:-1]):
        c = BUILD[i % len(BUILD)]
        V.poly([(px + 10, py + 2), (px + 90, py + 2), (px + 50, py + 56)], paint(_dim(c, T)))
    if not park:
        # a bench, a bin, a hydrant and flower boxes
        V.cam(1.0)
        bx = 790 if seed % 2 else 40
        V.rrect(bx, 1090, bx + 260, 1112, 8, paint(_dim((190, 120, 96), T)))
        V.rrect(bx - 4, 1140, bx + 264, 1166, 8, paint(_dim((190, 120, 96), T)))
        for dx in (14, 230):
            V.rect(bx + dx, 1160, bx + dx + 14, 1236, paint(_dim((90, 76, 120), T)))
        V.rrect(bx + 420 if seed % 2 == 0 else bx - 200, 1100, bx + 500 if seed % 2 == 0 else bx - 120, 1236, 14, paint(shader=lin(0, 1100, 0, 1236, [(0, _dim((96, 190, 170), T)), (1, _dim((60, 140, 150), T))])))
        hx = 1020 if seed % 2 == 0 else -80
        V.rrect(hx - 22, 1160, hx + 22, 1236, 10, paint(_dim((240, 80, 100), T)))
        V.rrect(hx - 30, 1150, hx + 30, 1172, 8, paint(_dim((255, 120, 130), T)))
        for k in range(5):
            x = 40 + k * 230
            V.rrect(x, 1052, x + 150, 1086, 8, paint(_dim((150, 110, 160), T)))
            for j in range(5):
                V.oval(x + 16 + j * 30, 1044 + (j % 2) * 6, 13, 13, paint(_dim([(255, 120, 150), (255, 214, 110), (255, 255, 255), (170, 130, 240)][(j + k) % 4], T)))
    else:
        V.cam(1.0)
        for k in range(10):                                                         # drifting leaves
            x = (r.uniform(0, 1500) + t * (24 + k * 3)) % 1700 - 300
            y = (r.uniform(0, 1800) + t * (60 + k * 5)) % 1500
            a = t * 2 + k
            V.poly([(x, y), (x + 14 * math.cos(a), y - 8), (x + 26, y + 6 * math.sin(a)), (x + 12, y + 14)], paint(_dim([(255, 180, 70), (236, 110, 90), (150, 210, 90)][k % 3], T)))


def foreground(kind, T, t, seed):
    """soft out-of-focus things at the edge of the picture, nearer than the people: they frame the scene and give it depth"""
    V.cv.resetMatrix()
    if kind in V.INDOOR:
        a = 235
        # leaves in the lower corner
        for k in range(5):
            ang = -0.5 + k * 0.22 + math.sin(t * 0.8 + k) * 0.03
            c = _dim((60, 170, 120) if k % 2 else (100, 210, 130), T)
            V.poly([(-30, 1960), (60, 1960), (200 * math.sin(ang) + 120, 1590 - 70 * math.cos(ang)), (200 * math.sin(ang) + 70, 1584 - 70 * math.cos(ang))], paint(c, 105, blur=16))
        # warm light spilling from the top corner
        V.oval(1040, -40, 380, 300, paint(shader=rad(1040, -40, 420, [(0, T["warm"] + (70,)), (1, T["warm"] + (0,))])))
    else:
        for k in range(6):
            ang = 0.5 - k * 0.2 + math.sin(t * 0.8 + k) * 0.03
            c = _dim((70, 180, 110) if k % 2 else (110, 215, 130), T)
            V.poly([(1120, 1960), (1020, 1960), (-200 * math.sin(ang) + 1000, 1560 - 70 * math.cos(ang)), (-200 * math.sin(ang) + 1060, 1556 - 70 * math.cos(ang))], paint(c, 105, blur=16))


DRESS = {"shop": shop_dressing, "kitchen": kitchen_dressing, "office": office_dressing, "classroom": classroom_dressing, "home": home_dressing}
