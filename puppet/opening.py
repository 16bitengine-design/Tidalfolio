"""The first seconds of every video, where a scrolling viewer decides to stay or go.
 - the camera starts a little closer and eases out (movement from the very first frame, never a still picture)
 - a big hook ribbon pops in at once and says what to wonder about (the same words as on the thumbnail, so the promise matches)
 - parts 2 and later also carry a PART badge, so someone who lands mid-story knows where they are
Everything is gone by about 2.4 s, before it can cover the story."""
import math
from functools import lru_cache

from PIL import Image, ImageDraw

from . import metadata
from .thumbnail import INK, MOON, _font, _burst

HOLD_UNTIL, GONE_AT = 1.9, 2.4
PUNCH = 0.16                    # extra camera zoom at the first frame, eased out over PUNCH_SEC
PUNCH_SEC = 1.1


def punch(u):
    k = max(0.0, min(1.0, u / PUNCH_SEC))
    return 1.0 + PUNCH * (1 - k * k * (3 - 2 * k))


def _back(k):
    k = max(0.0, min(1.0, k)) - 1
    return 1 + 2.4 * k ** 3 + 1.4 * k ** 2


@lru_cache(maxsize=8)
def _ribbon(text):
    f = _font(110)
    while f.size > 56 and ImageDraw.Draw(Image.new("L", (1, 1))).textlength(text, font=f) > 840:
        f = _font(f.size - 6)
    tw = ImageDraw.Draw(Image.new("L", (1, 1))).textlength(text, font=f)
    w, h = int(tw + 110), int(f.size * 1.55)
    im = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((24, 26, w + 22, h + 26), radius=34, fill=INK)
    d.rounded_rectangle((12, 12, w + 12, h + 12), radius=34, fill=MOON, outline=INK, width=9)
    d.text((12 + w / 2, 12 + h / 2 + 3), text, font=f, fill=INK, anchor="mm")
    return im


@lru_cache(maxsize=4)
def _badge(label):
    im = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    import random
    _burst(d, 150, 150, 128, (176, 226, 252), random.Random(3), 14)
    d.text((150, 112), "PART", font=_font(44), fill=INK, anchor="mm")
    d.text((150, 178), label, font=_font(96), fill=INK, anchor="mm")
    return im


def _put(img, sprite, cx, cy, scale, angle, alpha):
    if scale <= 0.02 or alpha <= 0:
        return
    sp = sprite.resize((max(2, int(sprite.width * scale)), max(2, int(sprite.height * scale))), Image.BICUBIC)
    if angle:
        sp = sp.rotate(angle, expand=True, resample=Image.BICUBIC)
    if alpha < 1:
        a = sp.getchannel("A").point(lambda v: int(v * alpha))
        sp.putalpha(a)
    img.paste(sp, (int(cx - sp.width / 2), int(cy - sp.height / 2)), sp)


def overlay(img, gt, script):
    if gt >= GONE_AT:
        return img
    alpha = 1.0 if gt < HOLD_UNTIL else max(0.0, 1 - (gt - HOLD_UNTIL) / (GONE_AT - HOLD_UNTIL))
    hook = metadata.hook_for(script)
    if hook:
        k = 0.6 + 0.4 * _back(gt / 0.38)             # already on screen in the very first frame, then it pops
        _put(img, _ribbon(hook), img.width / 2, 400 - 18 * (1 - min(1, gt / 0.38)), k, 3.5 + 6 * (1 - min(1, gt / 0.38)), alpha)
    sp = script.get("series_part")
    if sp and sp.get("part", 1) > 1:
        k = _back((gt - 0.15) / 0.35)
        _put(img, _badge(f"{sp['part']}/{sp['of']}"), 170, 230, k * 0.95, -8, alpha)
    return img
