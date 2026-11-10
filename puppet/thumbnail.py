"""A thumbnail for every story: the story's own key moment, the channel's look, a title anyone can read at a glance.

What stays the same on every thumbnail (so the channel is recognisable): thick ink outline, the Poppins Bold title
with an ink stroke, the "tidalfolio" pill with the crater moon in the bottom corner, the storybook colours.
What is different on every thumbnail (so no two look alike): the frame from THAT story (people, room, expression),
an accent colour pair, which side the title sits on, the starburst behind the part badge, and the title itself.
The title is the story's short title, in plain words that are easy to read and to say aloud.
"""
import math
import random
import zlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

FONTS = Path(__file__).resolve().parent / "fonts"
W, H = 1280, 720
INK = (27, 18, 48)
CREAM = (255, 244, 214)
MOON = (255, 224, 102)
BRAND = (255, 98, 132)          # the channel colour: the same frame on every thumbnail, so they are recognised in a feed
# (accent, second accent): brand colours, one pair per story
PALETTES = [((255, 194, 74), (56, 150, 240)), ((250, 120, 150), (255, 224, 102)), ((104, 196, 98), (170, 120, 210)),
            ((255, 150, 70), (56, 150, 240)), ((170, 120, 210), (255, 194, 74)), ((56, 150, 240), (250, 120, 150)),
            ((255, 224, 102), (104, 196, 98)), ((250, 120, 150), (176, 226, 252))]


def _font(size):
    return ImageFont.truetype(str(FONTS / "Poppins-Bold.ttf"), size)


def _outlined(d, xy, text, font, fill, stroke=10, ink=INK, shadow=None):
    x, y = xy
    if shadow:
        d.text((x + 7, y + 8), text, font=font, fill=ink, stroke_width=stroke, stroke_fill=ink)
    d.text((x, y), text, font=font, fill=fill, stroke_width=stroke, stroke_fill=ink)


def _burst(d, cx, cy, r, fill, rng, points=14):
    pts = []
    rot = rng.uniform(0, math.tau)
    for i in range(points * 2):
        a = rot + i * math.pi / points
        rr = r if i % 2 == 0 else r * 0.74
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill, outline=INK, width=8)


def _wrap(words, font, d, max_w):
    """split the title into at most three lines no wider than max_w (None if it cannot fit)"""
    lines, cur = [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if d.textlength(t, font=font) + 20 <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w_
    lines.append(cur)
    return lines if len(lines) <= 3 and all(d.textlength(l, font=font) + 20 <= max_w for l in lines) else None


def make(frame, script, slug=None):
    """frame: the story's key frame (a PIL image, portrait or landscape). Returns the finished 1280x720 thumbnail."""
    slug = slug or script.get("slug") or script.get("title", "story")
    seed = zlib.crc32(slug.split("-part-")[0].encode())          # all parts of one story share a look; the next story differs
    rng = random.Random(seed)
    acc, acc2 = PALETTES[seed % len(PALETTES)]
    title_left = bool(rng.getrandbits(1))

    # 1. the picture: a 16:9 band around the faces, a little more punch than the video frame
    fw, fh = frame.size
    ch = int(fw * 9 / 16)
    focus = float(script.get("thumbnail_focus", 0.30))          # share of the frame height where the faces sit
    top = max(0, min(fh - ch, int(fh * focus - ch / 2)))
    img = frame.crop((0, top, fw, top + ch)).resize((W, H), Image.LANCZOS)
    img = ImageEnhance.Sharpness(ImageEnhance.Contrast(ImageEnhance.Color(img).enhance(1.35)).enhance(1.14)).enhance(1.4)
    d = ImageDraw.Draw(img, "RGBA")

    # 2. a soft shade behind the title side so the words are always readable
    shade = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(shade)
    for i in range(W // 2):
        a = int(130 * (1 - i / (W / 2)) ** 1.6)
        x = i if title_left else W - 1 - i
        sd.line([(x, 0), (x, H)], fill=a)
    img.paste(Image.new("RGB", (W, H), INK), (0, 0), shade)
    d = ImageDraw.Draw(img, "RGBA")

    # 3. the title: the story's short title, 1 to 3 lines, as large as it will go
    title = str(script.get("short_title") or script.get("title", "")).split(":")[-1].strip().upper()
    words = title.split()[:5]
    max_w = int(W * 0.5)
    lines, size = None, 190
    while size >= 70:
        lines = _wrap(words, _font(size), d, max_w)
        if lines and len(lines) * size * 1.05 <= H * 0.66:
            break
        size -= 8
    font = _font(size)
    lines = lines or [" ".join(words)]
    block = len(lines) * size * 1.05
    y0 = (H - block) / 2 + 24
    for i, ln in enumerate(lines):
        x = 54 if title_left else W - 54 - d.textlength(ln, font=font)
        last = i == len(lines) - 1
        _outlined(d, (x, y0 + i * size * 1.05), ln, font, acc if last else CREAM, shadow=True)

    # 4. part badge on a starburst (only for a story told in parts)
    sp = script.get("series_part") or {}
    if sp.get("of", 1) > 1:
        bx = W - 128 if title_left else 128
        _burst(d, bx, 128, 104, acc2, rng)
        f1, f2 = _font(30), _font(62)
        d.text((bx, 94), "PART", font=f1, fill=INK, anchor="mm")
        d.text((bx, 146), f"{sp['part']}/{sp['of']}", font=f2, fill=INK, anchor="mm")

    # 4b. the hook: a tilted ribbon with a 1-3 word tease, on the picture side, so the thumbnail asks a question
    from . import metadata
    hook = metadata.hook_for(script)
    if hook:
        hf = _font(74)
        while hf.size > 40 and d.textlength(hook, font=hf) > W * 0.46:
            hf = _font(hf.size - 4)
        tw_ = d.textlength(hook, font=hf)
        rw, rh = int(tw_ + 70), int(hf.size * 1.5)
        rib = Image.new("RGBA", (rw + 30, rh + 30), (0, 0, 0, 0))
        rd = ImageDraw.Draw(rib)
        rd.rounded_rectangle((16, 18, rw + 14, rh + 18), radius=24, fill=INK)
        rd.rounded_rectangle((8, 8, rw + 6, rh + 8), radius=24, fill=MOON, outline=INK, width=7)
        rd.text((8 + (rw - 2) / 2 + 2, 8 + rh / 2 + 2), hook, font=hf, fill=INK, anchor="mm")
        rib = rib.rotate(4 if title_left else -4, expand=True, resample=Image.BICUBIC)
        rx = (W - rib.width - 44) if title_left else 44
        img.paste(rib, (rx, H - rib.height - 38), rib)
        d = ImageDraw.Draw(img, "RGBA")

    # 5. the channel mark: crater moon + "tidalfolio" on a pill, always in the same corner
    pf = _font(40)
    label = "tidalfolio"
    tw = d.textlength(label, font=pf)
    px1, py1 = W - 34, H - 30
    px0, py0 = px1 - tw - 92, py1 - 66
    d.rounded_rectangle((px0 + 5, py0 + 6, px1 + 5, py1 + 6), radius=33, fill=INK)
    d.rounded_rectangle((px0, py0, px1, py1), radius=33, fill=CREAM, outline=INK, width=6)
    mx, my = px0 + 36, (py0 + py1) // 2
    d.ellipse((mx - 20, my - 20, mx + 20, my + 20), fill=MOON, outline=INK, width=5)
    d.ellipse((mx - 9, my - 9, mx - 1, my - 1), fill=(242, 194, 48), outline=INK, width=2)
    d.ellipse((mx + 4, my + 3, mx + 11, my + 10), fill=(242, 194, 48), outline=INK, width=2)
    d.text((px0 + 66, my + 1), label, font=pf, fill=INK, anchor="lm")

    # 6. the channel frame: always the same coral, inked on both sides
    d.rectangle((0, 0, W - 1, H - 1), outline=INK, width=10)
    d.rectangle((10, 10, W - 11, H - 11), outline=BRAND, width=14)
    d.rectangle((24, 24, W - 25, H - 25), outline=INK, width=5)
    return img.convert("RGB")
