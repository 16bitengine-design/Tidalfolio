"""Pop-ups that bounce in over the illustrations.

Three kinds, set per scene in the script under "popups":
  bubble   speech bubble with a tail          {"kind": "bubble",  "text": "MINE.", "at": 2.2, "x": 0.3, "y": 0.22}
  label    plain card, no tail (titles, time jumps)  {"kind": "label", "text": "Six hours later", ...}
  sticker  a painted prop that pops in        {"kind": "sticker", "prompt": "a small hourglass", ...}

Common fields: at = seconds after the scene starts, x / y = centre as a fraction of the frame,
size = width as a fraction of the frame (default 0.22), hold = seconds on screen (default 1.8).
Keep pop-ups between y 0.12 and 0.62 so they never cover the captions.
"""
import hashlib
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
STICKER_STYLE = ("Hand-painted storybook sticker illustration, thick dark ink outline, watercolor fill, "
                 "one single object centered, isolated on a pure plain white background, no shadow, no text")
POP_IN, POP_OUT, HOLD = 0.35, 0.20, 1.8
MAX_STICKERS = 10
KINDS = ("bubble", "label", "sticker")
INK, PAPER = (40, 30, 25, 255), (255, 252, 240, 255)


def _font(size):
    for p in FONTS:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for w in text.split():
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


def card_image(text, width_px, tail):
    """Speech bubble (tail = 'left' or 'right') or plain label card (tail = 'none') as a transparent PNG."""
    probe = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    size = max(int(width_px * 0.15), 18)
    while True:                                   # shrink the text until it fits on at most two lines
        font = _font(size)
        pad = int(size * 0.7)
        lines = _wrap(probe, text, font, width_px - 2 * pad)
        if len(lines) <= 2 or size <= max(int(width_px * 0.07), 14):
            break
        size = int(size * 0.92)
    lh = int(size * 1.2)
    tw = max(probe.textlength(l, font=font) for l in lines)
    w, h = int(tw + 2 * pad), int(lh * len(lines) + 2 * pad)
    tl = int(size * 0.8) if tail != "none" else 0
    m, line = 6, max(size // 9, 3)
    img = Image.new("RGBA", (w + 2 * m, h + tl + 2 * m), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((m, m, m + w, m + h), radius=int(size * 0.8), fill=PAPER, outline=INK, width=line)
    if tail != "none":
        cx = m + (w // 3 if tail == "left" else 2 * w // 3)
        s = 1 if tail == "left" else -1
        d.polygon([(cx, m + h - line), (cx + tl, m + h - line), (cx - s * tl // 3, m + h + tl)], fill=PAPER, outline=INK)
        d.rectangle((cx + 2, m + h - line - 1, cx + tl - 2, m + h + 1), fill=PAPER)   # hides the seam under the tail
    y = m + pad
    for l in lines:
        d.text((m + (w - probe.textlength(l, font=font)) / 2, y), l, font=font, fill=INK)
        y += lh
    return img


def key_out_white(img):
    """Make the plain white background of a sticker transparent (flood fill from the corners,
    so white inside the drawing stays)."""
    img = img.convert("RGB")
    sentinel = (255, 0, 255)
    w, h = img.size
    for xy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        ImageDraw.floodfill(img, xy, sentinel, thresh=42)
    px = img.load()
    alpha = Image.new("L", img.size, 255)
    ap = alpha.load()
    for y in range(h):
        for x in range(w):
            if px[x, y] == sentinel:
                ap[x, y] = 0
    alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))   # trim the white fringe
    out = img.convert("RGBA")
    out.putalpha(alpha)
    return out.crop(out.getbbox() or (0, 0, w, h))


def sticker_file(prompt, stickers_dir, dry, generate):
    """One cached PNG per prompt, shared by both aspect ratios."""
    stickers_dir.mkdir(parents=True, exist_ok=True)
    out = stickers_dir / f"sticker_{hashlib.sha1(prompt.encode()).hexdigest()[:10]}.png"
    if out.exists():
        return out
    if dry:
        img = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((40, 40, 360, 360), fill=(224, 70, 60, 255), outline=INK, width=14)
        d.text((150, 190), "prop", fill=PAPER, font=_font(60))
        img.save(out)
        return out
    raw = out.with_suffix(".raw.png")
    generate(f"{prompt}. {STICKER_STYLE}", "square_hd", raw)
    key_out_white(Image.open(raw)).save(out)
    raw.unlink()
    return out


def clean(scene_popups, scene_dur):
    """Keep only well-formed pop-ups that fit inside their scene."""
    good = []
    for p in scene_popups or []:
        if not isinstance(p, dict) or p.get("kind") not in KINDS:
            continue
        try:
            at = float(p.get("at", 1.0))
            x, y = float(p.get("x", 0.5)), float(p.get("y", 0.3))
            size = min(max(float(p.get("size", 0.22)), 0.08), 0.5)
            hold = min(max(float(p.get("hold", HOLD)), 0.6), 4.0)
        except (TypeError, ValueError):
            continue
        if p["kind"] == "sticker" and not str(p.get("prompt", "")).strip():
            continue
        if p["kind"] != "sticker" and not str(p.get("text", "")).strip():
            continue
        if at < 0.2 or at > scene_dur - 0.8:           # would run into the next scene
            continue
        hold = min(hold, scene_dur - at - POP_IN - POP_OUT - 0.05)
        if hold < 0.4:
            continue
        good.append(dict(p, at=at, x=min(max(x, 0.1), 0.9), y=min(max(y, 0.1), 0.66), size=size, hold=hold))
    return good


def build(scenes, frame_w, frame_h, work_dir, stickers_dir, dry, generate):
    """Returns a list of dicts: png, cx, cy (pixels), t0, t1 (seconds in the whole video)."""
    work_dir = Path(work_dir)
    ref_w = frame_w if frame_w >= frame_h else frame_w * 1.7     # same visual size in vertical video
    out, n_stickers = [], 0
    for si, sc in enumerate(scenes):
        for k, p in enumerate(clean(sc.get("popups"), sc["_dur"])):
            width = max(int(ref_w * p["size"]), 40)
            if p["kind"] == "sticker":
                if n_stickers >= MAX_STICKERS:
                    continue
                n_stickers += 1
                img = Image.open(sticker_file(p["prompt"].strip(), stickers_dir, dry, generate)).convert("RGBA")
                img = img.resize((width, max(int(width * img.height / img.width), 2)), Image.LANCZOS)
            else:
                tail = "none" if p["kind"] == "label" else ("right" if p.get("tail") == "right" else "left")
                img = card_image(p["text"].strip(), width, tail)
            path = work_dir / f"pop_{si:02}_{k}.png"
            img.save(path)
            t0 = sc["_start"] + p["at"]
            m = 0.03 * min(frame_w, frame_h)                                  # keep the whole card inside the frame
            cx = min(max(p["x"] * frame_w, img.width / 2 + m), frame_w - img.width / 2 - m)
            cy = min(max(p["y"] * frame_h, img.height / 2 + m), frame_h - img.height / 2 - m)
            out.append(dict(png=path, cx=cx, cy=cy, t0=t0, t1=t0 + POP_IN + p["hold"]))
    return out


def _scale_expr(t0, t1):
    """Pop in with an overshoot, hold with a gentle breathing, shrink away."""
    r = f"((t-{t0:.3f})/{POP_IN})"
    pop = f"(1+2.70158*pow({r}-1,3)+1.70158*pow({r}-1,2))"
    gone = f"max(0.01,1-pow((t-{t1:.3f})/{POP_OUT},2))"
    return (f"if(lt(t,{t0 + POP_IN:.3f}),max(0.01,{pop}),if(lt(t,{t1:.3f}),1+0.02*sin((t-{t0:.3f})*4),{gone}))")


def overlay_graph(pops, base_label="0:v", first_input=2, tail_label="vpop"):
    """ffmpeg filter graph (as a list of chains) that overlays every pop-up on the base video.
    Pop-up k is ffmpeg input number first_input + k, looped; see overlay_inputs()."""
    chains, prev = [], base_label
    for k, p in enumerate(pops):
        s = _scale_expr(p["t0"], p["t1"])
        chains.append(f"[{first_input + k}:v]format=rgba,setpts=PTS+{p['t0']:.3f}/TB,"
                      f"scale=w='max(2,trunc(iw*({s})))':h='max(2,trunc(ih*({s})))':eval=frame[p{k}]")
        nxt = f"v{k}" if k < len(pops) - 1 else tail_label
        chains.append(f"[{prev}][p{k}]overlay=x='{p['cx']:.1f}-w/2':y='{p['cy']:.1f}-h/2+3*sin((t-{p['t0']:.3f})*3)':"
                      f"enable='between(t,{p['t0']:.3f},{p['t1'] + POP_OUT:.3f})':eval=frame:format=auto[{nxt}]")
        prev = nxt
    return chains


def overlay_inputs(pops, fps):
    args = []
    for p in pops:
        dur = p["t1"] + POP_OUT + 0.2 - p["t0"]
        args += ["-loop", "1", "-framerate", str(fps), "-t", f"{dur:.3f}", "-i", str(p["png"])]
    return args
