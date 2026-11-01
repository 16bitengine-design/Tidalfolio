#!/usr/bin/env python3
"""tidalfolio auto-video pipeline.

script.json -> narration (TTS, directed per scene) -> images (fal.ai Flux) -> multi-shot scenes
with camera moves, impact shake/flash -> dramatic sound mix + SFX -> highlighted-word captions
-> final MP4 (16:9 and 9:16) + thumbnail + upload details.

Usage:
  python pipeline.py scripts/001-bird-banter-kingfishers.json
  python pipeline.py --next              # render the next script in queue.txt not in done.txt
  python pipeline.py SCRIPT --dry-run    # no API calls: placeholder images + tone "narration"
"""
import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FPS = 30
LEAD = 0.30          # silence before narration starts in each scene (s)
TAIL = 0.55          # silence after narration ends (s)
MIN_SCENE = 3.0      # shortest allowed scene (s)
MIN_VIDEO = 60.0     # channel rule: every video runs 60 to 90 seconds
MAX_VIDEO = 90.0
WORKERS = max(1, min(4, os.cpu_count() or 2))

SIZES = {"16:9": (1920, 1080, "landscape_16_9"), "9:16": (1080, 1920, "portrait_16_9")}
FOLDERS = {"16:9": "youtube", "9:16": "vertical"}


# ----------------------------------------------------------------- helpers
def run(cmd):
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"Command failed: {' '.join(map(str, cmd))}\n{p.stderr[-2000:]}")
    return p.stdout


def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path])
    return float(out.strip())


def has_filter(name):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return re.search(rf"\s{name}\s", out) is not None


def srt_time(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02}:{int(m):02}:{int(s):02},{int((s % 1) * 1000):03}"


# ----------------------------------------------------------------- narration
async def _edge_tts(text, voice, rate, pitch, out):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(out))


TTS_STYLE = ("Deep, dramatic movie-trailer narrator. Intense and gravely serious, with perfect comic timing: "
             "dry, never silly. Fast, punchy delivery with short dramatic pauses before punchlines.")


def _openai_tts(text, cfg, out_wav, delivery=None):
    import requests
    instructions = cfg.get("instructions", TTS_STYLE)
    if delivery:
        instructions += f" Delivery for this line: {delivery}."
    for attempt in range(3):
        try:
            r = requests.post(
                "https://api.openai.com/v1/audio/speech", timeout=120,
                headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                json={"model": os.environ.get("OPENAI_TTS_MODEL") or "gpt-4o-mini-tts",
                      "voice": cfg.get("openai_voice", "onyx"), "input": text,
                      "instructions": instructions, "response_format": "wav"})
            if r.ok and len(r.content) > 1000:
                raw = out_wav.with_suffix(".raw.wav")
                raw.write_bytes(r.content)
                run(["ffmpeg", "-y", "-i", raw, "-ar", "44100", "-ac", "2", out_wav])
                raw.unlink()
                return True
            print(f"      OpenAI TTS {r.status_code}: {r.text[:200]}")
            if r.status_code in (400, 401, 403, 404):
                return False
        except Exception as e:
            print(f"      OpenAI TTS error: {e}")
        time.sleep(3 * (attempt + 1))
    return False


def make_narration(text, cfg, out_wav, dry, delivery=None):
    if dry:
        d = max(1.5, len(text.split()) / 2.6)
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=220:duration={d}",
             "-af", "volume=0.08", "-ar", "44100", "-ac", "2", out_wav])
        return
    if os.environ.get("OPENAI_API_KEY") and cfg.get("provider", "openai") == "openai":
        if _openai_tts(text, cfg, out_wav, delivery):
            return
        print("      OpenAI voice failed, falling back to the free voice.")
    mp3 = out_wav.with_suffix(".mp3")
    last = None
    for attempt in range(4):
        try:
            asyncio.run(_edge_tts(text, cfg.get("voice", "en-GB-RyanNeural"),
                                  cfg.get("rate", "-8%"), cfg.get("pitch", "-6Hz"), mp3))
            break
        except Exception as e:  # network hiccup
            last = e
            time.sleep(3 * (attempt + 1))
    else:
        sys.exit(f"Narration failed for: {text!r}\n{last}")
    run(["ffmpeg", "-y", "-i", mp3, "-ar", "44100", "-ac", "2", out_wav])


# ----------------------------------------------------------------- images
def build_prompt(script, scene, aspect="16:9", variant="a"):
    frame = "tall vertical 9:16 frame" if aspect == "9:16" else "wide 16:9 frame"
    base = script.get("style_mirror") if scene.get("look") == "mirror" and script.get("style_mirror") else script.get("style", "")
    parts = [base.replace("{frame}", frame)]
    keys = scene.get("characters_b", scene.get("characters", [])) if variant == "b" else scene.get("characters", [])
    for key in keys:
        desc = script.get("characters", {}).get(key)
        if desc:
            parts.append(desc)
    parts.append(scene["image_prompt_b"] if variant == "b" else scene["image_prompt"])
    return " ".join(p.strip() for p in parts if p).strip()


def bake_vignette(path):
    """Darken the edges once per image (much cheaper than doing it on every video frame)."""
    from PIL import Image, ImageChops
    img = Image.open(path).convert("RGB")
    g = Image.radial_gradient("L").resize(img.size)            # 0 at the centre -> 255 at the edges
    g = g.point(lambda v: int(255 - max(0, v - 90) * 0.55))
    img = ImageChops.multiply(img, Image.merge("RGB", (g, g, g)))
    img.save(path)


def make_image(prompt, size_name, seed, out, dry, idx, aspect):
    if out.exists():
        return
    w, h, _ = SIZES[aspect]
    if dry:
        from PIL import Image, ImageDraw
        hue = (sum(map(ord, prompt)) * 7) % 120
        img = Image.new("RGB", (w // 2, h // 2), (30 + hue, 60 + idx * 5 % 80, 110))
        d = ImageDraw.Draw(img)
        W, H = img.size
        d.ellipse([W * .12, H * .3, W * .38, H * .8], fill=(230, 80, 60))      # left "character"
        d.ellipse([W * .62, H * .3, W * .88, H * .8], fill=(70, 200, 230))     # right "character"
        d.text((40, 40), f"scene {idx + 1}\n{prompt[:160]}", fill=(255, 255, 255))
        img.save(out)
        bake_vignette(out)
        return
    import requests
    key = os.environ.get("FAL_KEY")
    if not key:
        sys.exit("FAL_KEY is not set. Add it as a GitHub secret (see README).")
    model = os.environ.get("FAL_IMAGE_MODEL") or "fal-ai/flux/schnell"
    body = {"prompt": prompt, "image_size": size_name, "num_images": 1,
            "seed": seed, "enable_safety_checker": True}
    if "schnell" in model:
        body["num_inference_steps"] = 4
    last = None
    for attempt in range(4):
        r = requests.post(f"https://fal.run/{model}", json=body, timeout=240,
                          headers={"Authorization": f"Key {key}"})
        if r.ok:
            url = r.json()["images"][0]["url"]
            img = requests.get(url, timeout=120)
            img.raise_for_status()
            out.write_bytes(img.content)
            bake_vignette(out)
            return
        last = f"{r.status_code} {r.text[:300]}"
        time.sleep(4 * (attempt + 1))
    sys.exit(f"Image generation failed for scene {idx + 1}: {last}")


# ----------------------------------------------------------------- sound design
SFX_NAMES = ("hit", "whoosh", "splash", "boom", "sting", "tick", "riser")
IMPACT = {"hit", "splash", "boom"}


def synth_sfx(name, out):
    """Synthesized effects so the pipeline needs no downloads.
    Drop your own files in assets/sfx/<name>.wav to override any of them."""
    custom = ROOT / "assets" / "sfx" / f"{name}.wav"
    if custom.exists():
        shutil.copy(custom, out)
        return
    tail = ["-ar", "44100", "-ac", "2", out]
    if name == "hit":
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=f=48:d=1.4", "-f", "lavfi",
             "-i", "anoisesrc=d=1.4:c=brown:a=0.8", "-filter_complex",
             "[0]afade=t=out:st=0.05:d=1.3[a];[1]lowpass=f=500,afade=t=out:d=0.6[b];"
             "[a][b]amix=inputs=2:normalize=0,volume=2.2,alimiter=limit=0.95", *tail])
    elif name == "whoosh":
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=d=0.9:c=pink:a=0.6", "-af",
             "highpass=f=300,lowpass=f=3500,afade=t=in:d=0.4,afade=t=out:st=0.4:d=0.5,volume=0.9", *tail])
    elif name == "splash":
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=d=0.8:c=white:a=0.7", "-af",
             "highpass=f=1200,afade=t=in:d=0.02,afade=t=out:st=0.05:d=0.7,volume=0.9", *tail])
    elif name == "boom":
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=f=38:d=2.2", "-f", "lavfi",
             "-i", "anoisesrc=d=2.2:c=brown:a=0.9", "-filter_complex",
             "[0]afade=t=out:st=0.02:d=2.1[a];[1]lowpass=f=160,afade=t=out:d=1.4[b];"
             "[a][b]amix=inputs=2:normalize=0,volume=2.6,aecho=0.8:0.7:90|210:0.35|0.2,alimiter=limit=0.95", *tail])
    elif name == "sting":      # dissonant stab for shocks, reveals and deadpan punchlines
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=f=233.08:d=1.8", "-f", "lavfi", "-i", "sine=f=246.94:d=1.8",
             "-f", "lavfi", "-i", "sine=f=116.54:d=1.8", "-filter_complex",
             "[0][1][2]amix=inputs=3:normalize=0,afade=t=in:d=0.01,afade=t=out:st=0.05:d=1.7,"
             "tremolo=f=7:d=0.5,aecho=0.8:0.6:70|140:0.3|0.15,volume=0.9", *tail])
    elif name == "tick":       # tiny dry click for a suspense beat
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=f=1500:d=0.06", "-af",
             "afade=t=out:st=0.01:d=0.05,volume=0.7", *tail])
    elif name == "riser":      # rising sweep that builds into an impact
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "aevalsrc=0.4*sin(2*PI*(180*t+260*t*t)):d=1.4:s=44100",
             "-f", "lavfi", "-i", "anoisesrc=d=1.4:c=pink:a=0.5", "-filter_complex",
             "[1]highpass=f=800,afade=t=in:d=1.3[n];[0][n]amix=inputs=2:normalize=0,afade=t=in:d=1.2,volume=1.3", *tail])
    else:
        sys.exit(f"Unknown sfx '{name}'. Use one of {', '.join(SFX_NAMES)} or add assets/sfx/{name}.wav")


AUDIO_EXT = ("*.mp3", "*.wav", "*.m4a", "*.ogg")


def find_audio(folder, stem):
    """First file called <stem>.<mp3|wav|m4a|ogg> inside folder, or None."""
    for ext in AUDIO_EXT:
        hit = sorted(folder.glob(stem + ext[1:]))
        if hit:
            return hit[0]
    return None


# ---- emotion -> how loud the music should be (1.0 = full, 0.0 = silent) ----------------------
# The words come from each scene's "delivery" (or an explicit "music" override in the script).
# Rule of thumb: music swells on feeling, dips so a deadpan joke can land, hides in hushed suspense.
EMOTION_LEVELS = [
    (("triumph", "intense", "urgent", "frantic", "epic", "climax"), 0.90),
    (("sincere", "tender", "earnest", "soft", "warm", "gentle", "heartfelt", "reflective", "contemplative"), 0.75),
    (("ominous", "conspiratorial", "hushed", "suspense", "whisper", "dread"), 0.45),
    (("dry", "deadpan", "blunt", "neutral", "detached", "flat", "calm"), 0.28),
]
DEFAULT_LEVEL = 0.5
MUSIC_BASE = 0.8        # overall music gain at level 1.0, before the narration ducking
RAMP = 0.7              # seconds taken to glide from one scene's level to the next


def scene_level(sc, idx, script):
    """Music level for one scene. Priority: explicit script override > emotional beat > delivery words."""
    m = sc.get("music")
    if isinstance(m, dict) and "level" in m:
        return max(0.0, min(1.0, float(m["level"])))
    words = ""
    if isinstance(m, dict) and m.get("emotion"):
        words = str(m["emotion"]).lower()
    elif isinstance(m, str):
        words = m.lower()
    else:
        words = str(sc.get("delivery", "")).lower()
    level = DEFAULT_LEVEL
    for keys, lv in EMOTION_LEVELS:
        if any(k in words for k in keys):
            level = lv
            break
    beat = script.get("story", {}).get("emotional_beat_scene")
    if beat is not None and idx + 1 == int(beat):
        level = max(level, 0.85)                       # the heart of the story: let the music swell
    if idx == len(script["scenes"]) - 1:
        level = max(level, 0.7)                        # last line: leave the viewer with the feeling
    return level


def write_envelope(scenes, script, total, path):
    """Write the music loudness curve as a mono wav (8 kHz, value = gain 0..1) that ffmpeg multiplies in."""
    import array
    import wave
    sr = 8000
    levels = [scene_level(sc, i, script) for i, sc in enumerate(scenes)]
    keys = [(0.0, levels[0])]
    for i in range(1, len(scenes)):
        b = scenes[i]["_start"]
        keys += [(max(keys[-1][0], b - RAMP), levels[i - 1]), (b + RAMP, levels[i])]
    keys.append((total + 1.0, levels[-1]))
    data = array.array("h")
    k = 0
    for n in range(int((total + 1.0) * sr)):
        t = n / sr
        while k < len(keys) - 2 and t > keys[k + 1][0]:
            k += 1
        (t0, v0), (t1, v1) = keys[k], keys[k + 1]
        v = v1 if t1 <= t0 else v0 + (v1 - v0) * min(1.0, max(0.0, (t - t0) / (t1 - t0)))
        data.append(int(max(0.0, min(1.0, v)) * 32767))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data.tobytes())
    return levels


def make_bed(total, out, scenes=None, script=None):
    """The channel's signature theme, on EVERY video:
         assets/music/theme/intro.*  -> plays once at the start
         assets/music/theme/loop.*   -> seamless loop under the whole video
         assets/music/theme/outro.*  -> resolves at the very end
       The loop's loudness follows the emotion of each scene (see EMOTION_LEVELS). The narrator-driven
       ducking is applied afterwards in the final mix."""
    theme = ROOT / "assets" / "music" / (os.environ.get("MUSIC_THEME") or "theme")
    loop = find_audio(theme, "loop") if theme.exists() else None
    if loop is None:   # old behaviour: any single track dropped into assets/music
        folder = ROOT / "assets" / "music"
        found = [p for ext in AUDIO_EXT for p in sorted(folder.glob(ext))] if folder.exists() else []
        loop = found[0] if found else None
    T = f"{total:.2f}"
    if loop is not None:
        base = out.with_suffix(".loop.wav")
        ld, xf = duration(loop), 3.0
        if ld >= total or ld <= 2 * xf:
            run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", loop, "-t", T, "-ar", "44100", "-ac", "2", base])
        else:   # a short ordinary track: repeat it with a 3 s crossfade so there is no click at the seam
            n = int(-(-(total - xf) // (ld - xf)))
            fc = "".join(f"[{i}]aresample=44100,aformat=channel_layouts=stereo[a{i}];" for i in range(n))
            prev = "a0"
            for i in range(1, n):
                fc += f"[{prev}][a{i}]acrossfade=d={xf}:c1=tri:c2=tri[x{i}];"
                prev = f"x{i}"
            run(["ffmpeg", "-y", *sum((["-i", loop] for _ in range(n)), []), "-filter_complex",
                 fc.rstrip(";"),
                 "-map", f"[{prev}]", "-t", T, "-ar", "44100", "-ac", "2", base])
    else:              # synthesized fallback: drone + fifth + rumble, pulsing like a heartbeat
        base = out.with_suffix(".loop.wav")
        run(["ffmpeg", "-y",
             "-f", "lavfi", "-i", f"sine=f=55:d={T}", "-f", "lavfi", "-i", f"sine=f=82.4:d={T}",
             "-f", "lavfi", "-i", f"sine=f=110:d={T}", "-f", "lavfi", "-i", f"anoisesrc=d={T}:c=brown:a=0.4",
             "-filter_complex",
             "[1]volume=0.8[b];[2]tremolo=f=0.25:d=0.6,volume=0.35[c];[3]lowpass=f=220[n];"
             "[0][b][c][n]amix=inputs=4:normalize=0,tremolo=f=1.9:d=0.55",
             "-ar", "44100", "-ac", "2", base])
    if scenes is None or script is None:
        shutil.copy(base, out)
        return
    env = out.with_suffix(".env.wav")
    levels = write_envelope(scenes, script, total, env)
    print("      music levels per scene: " + " ".join(f"{v:.2f}" for v in levels))
    parts = [f"[0]volume={MUSIC_BASE}[l]",
             "[1]aresample=44100,aformat=channel_layouts=stereo[e]",
             "[l][e]amultiply[loop]"]
    inputs = ["-i", base, "-i", env]
    labels, k = ["[loop]"], 2
    intro = find_audio(theme, "intro") if theme.exists() else None
    outro = find_audio(theme, "outro") if theme.exists() else None
    if not intro:   # single-track mode: ease the music in instead of starting abruptly
        parts[2] = "[l][e]amultiply,afade=t=in:d=2.5[loop]"
    if intro:       # the signature motif, full and clear, once at the start
        inputs += ["-i", intro]
        parts.append(f"[{k}]aresample=44100,aformat=channel_layouts=stereo,volume=0.9[in]")
        labels.append("[in]")
        k += 1
    if outro:       # the resolving chord, ending exactly with the video
        od = duration(outro)
        inputs += ["-i", outro]
        ms = int(max(0.0, total - od) * 1000)
        parts.append(f"[{k}]aresample=44100,aformat=channel_layouts=stereo,volume=0.9,adelay={ms}|{ms}[ou]")
        labels.append("[ou]")
        k += 1
    parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=longest[bed]")
    run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(parts), "-map", "[bed]",
         "-t", T, "-ar", "44100", "-ac", "2", out])


# ----------------------------------------------------------------- shots (the illusion of action)
FOCUS_X = {"left": 0.32, "center": 0.5, "right": 0.68}


def sfx_list(sc):
    s = sc.get("sfx")
    return [s] if isinstance(s, str) and s else list(s or [])


def n_shots(sc):
    return max(1, int(round(sc["_dur"] / 2.5)))      # a new framing about every 2.5 seconds


def plan_shots(sc, use_b):
    """Cut each scene into several shots: a wide opening move, a punch-in, a drift; a second image
    (the same moment a beat later) on action scenes; slam + shake + white flash on impacts."""
    n = n_shots(sc)
    sfx = sfx_list(sc)
    fx = FOCUS_X.get(sc.get("focus"), 0.5)
    first_b = (n + 1) // 2 if (use_b and n >= 2) else n
    impact = any(x in IMPACT for x in sfx)
    whoosh = "whoosh" in sfx
    motion = sc.get("motion", "zoom_in")
    shots = []
    for k in range(n):
        which = "b" if k >= first_b else "a"
        pos = k if which == "a" else k - first_b
        s = dict(img=which, cy=0.5, shake=2.0, flash=False)
        if k == 0:
            if motion == "zoom_out":
                s.update(z0=1.28, z1=1.05, fx0=fx, fx1=fx)
            elif motion == "pan_left":
                s.update(z0=1.22, z1=1.22, fx0=min(0.8, fx + 0.22), fx1=max(0.2, fx - 0.22))
            elif motion == "pan_right":
                s.update(z0=1.22, z1=1.22, fx0=max(0.2, fx - 0.22), fx1=min(0.8, fx + 0.22))
            else:
                s.update(z0=1.04, z1=1.24, fx0=fx, fx1=fx)
            if sc.get("transition") == "dissolve":      # act change: soft white dissolve, calm camera
                s.update(shake=2.0, dissolve=True)
            elif impact:
                s.update(z0=1.5, z1=1.14, fx0=fx, fx1=fx, shake=34.0, flash=True)
            elif whoosh:
                s.update(z0=1.32, z1=1.32, fx0=0.2, fx1=0.8, shake=6.0)
        elif pos == 0:                                   # first shot of the second frame
            s.update(z0=1.1, z1=1.32, fx0=fx, fx1=fx)
        elif pos == 1:                                   # punch-in
            cx = min(0.8, max(0.2, fx + (0.12 if k % 2 else -0.12)))
            s.update(z0=1.55, z1=1.72, fx0=cx, fx1=cx, cy=0.44, shake=3.0)
        else:                                            # drift across the frame
            a, b = (0.35, 0.65) if k % 2 else (0.65, 0.35)
            s.update(z0=1.3, z1=1.3, fx0=a, fx1=b)
        shots.append(s)
    return shots


def render_shot(img, t0, t1, shot, aspect, out):
    w, h, _ = SIZES[aspect]
    f0, f1 = int(round(t0 * FPS)), int(round(t1 * FPS))
    n = max(1, f1 - f0)                                   # cumulative rounding: no audio drift
    z = f"{shot['z0']}+({shot['z1']}-{shot['z0']})*on/{n}"
    cx = f"({shot['fx0']}+({shot['fx1']}-{shot['fx0']})*on/{n})"
    amp = f"({shot['shake']}*exp(-on/9)+1.5)" if shot["shake"] > 8 else f"{shot['shake']}"
    x = f"clip({cx}*iw-iw/zoom/2+{amp}*(sin(on*1.9)+0.6*sin(on*4.3)),0,iw-iw/zoom)"
    y = f"clip({shot['cy']}*ih-ih/zoom/2+{amp}*cos(on*2.3),0,ih-ih/zoom)"
    flash = "fade=t=in:st=0:d=0.12:color=white," if shot["flash"] else ""
    if shot.get("dissolve"):
        flash = "fade=t=in:st=0:d=0.6:color=white,"
    vf = (f"scale={2 * w}:{2 * h}:force_original_aspect_ratio=increase,crop={2 * w}:{2 * h},"
          f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={w}x{h}:fps={FPS},"
          f"{flash}eq=contrast=1.1:saturation=1.12,format=yuv420p")
    run(["ffmpeg", "-y", "-i", img, "-vf", vf, "-frames:v", n, "-r", FPS,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", out])


# ----------------------------------------------------------------- captions (big, highlighted word by word)
def caption_chunks(text, max_words=3):
    chunks, cur = [], []
    for w in text.split():
        cur.append(w)
        if len(cur) >= max_words or w[-1] in ".!?…" or (w[-1] in ",;:" and len(cur) >= 2):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def ass_time(t):
    cs = int(round(t * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    return f"{h}:{m:02}:{rem // 100:02}.{rem % 100:02}"


def make_ass(scenes, aspect, path):
    w, h, _ = SIZES[aspect]
    size, marginv = (74, 110) if aspect == "16:9" else (84, 430)
    head = ("[Script Info]\nScriptType: v4.00+\nWrapStyle: 0\n"
            f"PlayResX: {w}\nPlayResY: {h}\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
            "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
            "MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Default,DejaVu Sans,{size},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,2,60,60,{marginv},1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    HI, LO = "{\\c&H0000E5FF&}", "{\\c&HFFFFFF&}"          # yellow for the word being spoken
    POP = "{\\fad(40,0)\\fscx114\\fscy114\\t(0,140,\\fscx100\\fscy100)}"
    lines = []
    for sc in scenes:
        chunks = caption_chunks(sc["narration"])
        weights = [sum(len(x) for x in c) + 2 * len(c) + (5 if c[-1][-1] in ".!?…" else 0) for c in chunks]
        t = sc["_start"] + LEAD
        for c, wt in zip(chunks, weights):
            d = sc["_narr"] * wt / sum(weights)
            words = [x.replace("{", "").replace("}", "").upper() for x in c]
            lens = [len(x) + 1 for x in words]
            tt = t
            for k in range(len(words)):
                dd = d * lens[k] / sum(lens)
                shown = " ".join((HI + x + LO) if j == k else x for j, x in enumerate(words))
                lines.append(f"Dialogue: 0,{ass_time(tt)},{ass_time(tt + dd)},Default,,0,0,0,,"
                             f"{POP if k == 0 else ''}{shown}")
                tt += dd
            t += d
    path.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")


# ----------------------------------------------------------------- final encode (size-budgeted)
MAX_MB = float(os.environ.get("MAX_VIDEO_MB") or 14.0)     # hard ceiling per video file (default 14 MB, under the 15 MB goal)
AUDIO_KBPS = 112


def encode_final(silent, mixed, final, total, ass_path):
    """One high-efficiency encode with a bitrate ceiling worked out from the video length, so the file
    stays under MAX_MB whatever the picture content. If a file still comes out too big, it is
    re-encoded at a lower ceiling (up to 3 tries)."""
    budget_kbps = MAX_MB * 8 * 1024 * 0.965 / max(total, 1.0)      # 3.5% left for container overhead
    v_kbps = int(budget_kbps - AUDIO_KBPS)
    if v_kbps < 250:
        sys.exit(f"{total:.0f}s of video cannot fit in {MAX_MB} MB at a watchable quality. Raise MAX_VIDEO_MB or shorten the script.")
    for attempt in range(3):
        cmd = ["ffmpeg", "-y", "-i", silent, "-i", mixed]
        if ass_path:
            esc = str(ass_path).replace("\\", "/").replace(":", "\\:")
            cmd += ["-vf", f"ass='{esc}'"]
        cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "24",
                "-maxrate", f"{v_kbps}k", "-bufsize", f"{2 * v_kbps}k",
                "-profile:v", "high", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", f"{AUDIO_KBPS}k", "-ac", "2",
                "-shortest", "-movflags", "+faststart", final]
        run(cmd)
        mb = final.stat().st_size / 1e6
        print(f"      encode {attempt + 1}: {mb:.1f} MB (video ceiling {v_kbps} kbps, limit {MAX_MB} MB)")
        if mb <= MAX_MB:
            return
        v_kbps = int(v_kbps * (MAX_MB / mb) * 0.93)                 # shrink the ceiling in proportion and retry
    print(f"      WARNING: {final.name} is still {mb:.1f} MB (limit {MAX_MB} MB).")


# ----------------------------------------------------------------- one aspect ratio, start to finish
def render_aspect(script, scenes, aspect, out_root, narr_dir, total, dry):
    w, h, size_name = SIZES[aspect]
    folder = FOLDERS[aspect]
    seed = int(script.get("seed", 7))
    out_dir = out_root / folder
    work = out_root / f"work_{folder}"
    out_dir.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    print(f"=== {folder} ({aspect}) ===")
    allow_b = script.get("second_frames", True)

    print("[2/5] images")
    jobs = []
    for i, sc in enumerate(scenes):
        sc["_use_b"] = bool(allow_b and sc.get("image_prompt_b") and n_shots(sc) >= 2)
        jobs.append((build_prompt(script, sc, aspect, "a"), size_name, seed, work / f"img_{i:02}.png", dry, i, aspect))
        if sc["_use_b"]:   # same seed as the first frame, so the characters and framing stay consistent
            jobs.append((build_prompt(script, sc, aspect, "b"), size_name, seed, work / f"img_{i:02}b.png", dry, i, aspect))
    with ThreadPoolExecutor(WORKERS) as ex:
        list(ex.map(lambda j: make_image(*j), jobs))
    print(f"      {len(jobs)} images")

    print("[3/5] shots")
    shot_jobs, listing = [], []
    for i, sc in enumerate(scenes):
        shots = plan_shots(sc, sc["_use_b"])
        step = sc["_dur"] / len(shots)
        for k, shot in enumerate(shots):
            img = work / (f"img_{i:02}b.png" if shot["img"] == "b" else f"img_{i:02}.png")
            clip = work / f"clip_{i:02}_{k}.mp4"
            shot_jobs.append((img, sc["_start"] + k * step, sc["_start"] + (k + 1) * step, shot, aspect, clip))
            listing.append(f"file '{clip.resolve()}'")
    with ThreadPoolExecutor(WORKERS) as ex:
        list(ex.map(lambda j: render_shot(*j), shot_jobs))
    print(f"      {len(shot_jobs)} shots")
    (work / "clips.txt").write_text("\n".join(listing))
    silent = work / "silent.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", work / "clips.txt", "-c", "copy", silent])

    print("[4/5] sound design")
    nar_inputs, nar_filter = [], []
    for i, sc in enumerate(scenes):
        nar_inputs += ["-i", narr_dir / f"narr_{i:02}.wav"]
        ms = int(LEAD * 1000)
        nar_filter.append(f"[{i}]adelay={ms}|{ms},apad=whole_dur={sc['_dur']:.3f}[n{i}]")
    cat = "".join(f"[n{i}]" for i in range(len(scenes)))
    nar_filter.append(f"{cat}concat=n={len(scenes)}:v=0:a=1[nar]")
    narration = work / "narration_full.wav"
    run(["ffmpeg", "-y", *nar_inputs, "-filter_complex", ";".join(nar_filter),
         "-map", "[nar]", "-ar", "44100", "-ac", "2", narration])

    bed = work / "bed.wav"
    make_bed(total, bed, scenes, script)

    events = []                                           # (sfx name, start seconds, volume)
    for i, sc in enumerate(scenes):
        names = sfx_list(sc)
        events += [(n, sc["_start"], 0.85) for n in names]
        if i > 0 and any(n in ("hit", "boom") for n in names) and "riser" not in names:
            events.append(("riser", max(0.0, sc["_start"] - 1.3), 0.5))   # tension builds into every big impact

    mix_inputs = ["-i", narration, "-i", bed]
    fl = ["[0]highpass=f=70,equalizer=f=140:t=q:w=1:g=3,equalizer=f=3200:t=q:w=1.2:g=2,"
          "acompressor=threshold=0.1:ratio=3:attack=5:release=90:makeup=3,"
          "aecho=0.8:0.55:55|120:0.22|0.1,alimiter=limit=0.95,asplit=2[nar][nsc]",
          "[1]volume=1.0[bedv]",
          "[bedv][nsc]sidechaincompress=threshold=0.03:ratio=5:attack=20:release=500[bed]"]
    labels, k = ["[nar]", "[bed]"], 2
    for name, t_s, vol in events:
        f = work / f"sfx_{name}.wav"
        if not f.exists():
            synth_sfx(name, f)
        ms = int(t_s * 1000)
        mix_inputs += ["-i", f]
        fl.append(f"[{k}]adelay={ms}|{ms},volume={vol}[s{k}]")
        labels.append(f"[s{k}]")
        k += 1
    fl.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=longest,"
              f"afade=t=out:st={max(0, total - 1.5):.2f}:d=1.5,"
              "loudnorm=I=-15:TP=-1.5:LRA=6,alimiter=limit=0.95[mix]")
    mixed = work / "mix.wav"
    run(["ffmpeg", "-y", *mix_inputs, "-filter_complex", ";".join(fl),
         "-map", "[mix]", "-t", f"{total:.2f}", "-ar", "44100", "-ac", "2", mixed])

    print("[5/5] captions + final video")
    srt, idx = [], 1
    for sc in scenes:                                      # plain .srt, e.g. for YouTube's own caption track
        words = sc["narration"].split()
        parts = -(-len(words) // 7) or 1
        size = -(-len(words) // parts) or 1
        chunks = [words[j:j + size] for j in range(0, len(words), size)] or [[""]]
        per = sc["_narr"] / len(chunks)
        for c, chunk in enumerate(chunks):
            s0 = sc["_start"] + LEAD + c * per
            srt += [str(idx), f"{srt_time(s0)} --> {srt_time(s0 + per)}", " ".join(chunk), ""]
            idx += 1
    (out_dir / "captions.srt").write_text("\n".join(srt))
    ass_path = out_dir / "captions.ass"
    make_ass(scenes, aspect, ass_path)

    final = out_dir / "video.mp4"
    burn = script.get("burn_captions", True) and has_filter("ass")
    if script.get("burn_captions", True) and not burn:
        print("      (ass filter not available: captions not burned in)")
    encode_final(silent, mixed, final, total, ass_path if burn else None)

    thumb = int(script.get("thumbnail_scene", 1)) - 1
    shutil.copy(work / f"img_{thumb:02}.png", out_dir / "thumbnail.png")
    print(f"      -> {final}")


def render(script_path, dry):
    script = json.loads(Path(script_path).read_text())
    slug = script.get("slug") or Path(script_path).stem
    aspects = script.get("aspects") or [script.get("aspect", "16:9")]
    for a in aspects:
        if a not in FOLDERS:
            sys.exit("aspects must be '16:9' and/or '9:16'")
    out_root = ROOT / "output" / slug
    narr_dir = out_root / "narration"
    narr_dir.mkdir(parents=True, exist_ok=True)
    scenes = script["scenes"]
    voice_cfg = script.get("voice", {})

    # narration first (shared by every aspect): cheap, and tells us the runtime before paying for images
    print(f"[1/5] narration ({len(scenes)} scenes)")
    t = 0.0
    for i, sc in enumerate(scenes):
        wav = narr_dir / f"narr_{i:02}.wav"
        if not wav.exists():
            make_narration(sc["narration"], voice_cfg, wav, dry, sc.get("delivery"))
        nd = duration(wav)
        d = max(MIN_SCENE, LEAD + nd + TAIL)
        sc["_narr"], sc["_start"], sc["_dur"] = nd, t, d
        t += d
    total = t
    print(f"      total runtime: {total:.1f}s")
    if total < MIN_VIDEO:
        # a little short: spread extra pause evenly (up to ~0.8s per scene) to reach the minimum
        extra = (MIN_VIDEO + 1.0 - total) / len(scenes)
        if extra > 0.8:
            sys.exit(f"Video would be {total:.1f}s but the minimum is {MIN_VIDEO:.0f}s. "
                     "Add scenes or lengthen narration in the script.")
        t = 0.0
        for sc in scenes:
            sc["_dur"] += extra
            sc["_start"] = t
            t += sc["_dur"]
        total = t
        print(f"      stretched pauses to reach {total:.1f}s")
    if total > MAX_VIDEO:
        print(f"      WARNING: {total:.1f}s is over the {MAX_VIDEO:.0f}s target. Trim the script if you want it shorter.")

    for aspect in aspects:
        render_aspect(script, scenes, aspect, out_root, narr_dir, total, dry)

    write_metadata(script, out_root / "metadata.md", total)
    (out_root / "metadata.json").write_text(json.dumps(
        {"title": script.get("title", slug), "youtube": script.get("youtube", {}),
         "tiktok": script.get("tiktok", {})}, indent=2))
    (ROOT / "output" / "LAST_SLUG").write_text(slug)
    print(f"Done: {out_root} ({total:.1f}s)")
    return slug


def write_metadata(script, path, total):
    yt, tt = script.get("youtube", {}), script.get("tiktok", {})
    lines = [f"# {script.get('title', path.parent.name)}", f"Runtime: {total:.1f}s", "",
             "## YouTube (youtube/video.mp4)", f"**Title:** {yt.get('title', '')}", "",
             "**Description:**", yt.get("description", ""), "",
             f"**Tags:** {', '.join(yt.get('tags', []))}", "",
             f"**Pinned comment:** {yt.get('pinned_comment', '')}", "",
             "## TikTok (vertical/video.mp4)", f"**Caption:** {tt.get('caption', '')}", "",
             f"**Hashtags:** {' '.join(tt.get('hashtags', []))}", ""]
    path.write_text("\n".join(lines))


# ----------------------------------------------------------------- queue
def read_lines(p):
    return [l.strip() for l in p.read_text().splitlines() if l.strip() and not l.startswith("#")] if p.exists() else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script", nargs="?")
    ap.add_argument("--next", action="store_true", help="render next unfinished script from queue.txt")
    ap.add_argument("--dry-run", action="store_true", help="no API calls; placeholder media")
    a = ap.parse_args()

    if a.next:
        queue, done = read_lines(ROOT / "queue.txt"), set(read_lines(ROOT / "done.txt"))
        todo = [q for q in queue if q not in done]
        if not todo:
            print("Queue is empty: nothing to render. Add scripts to queue.txt.")
            return
        missing = [q for q in todo if not (ROOT / "scripts" / q).exists()]
        for q in missing:
            print(f"WARNING: queue.txt lists scripts/{q} but that file is not in the repository. "
                  "Upload it into a folder named 'scripts', or add OPENAI_API_KEY so a new script is written.")
        todo = [q for q in todo if q not in missing]
        if not todo:
            sys.exit("No script file found for anything in queue.txt (see warnings above).")
        name = todo[0]
        render(ROOT / "scripts" / name, a.dry_run)
        if not a.dry_run:
            with open(ROOT / "done.txt", "a") as f:
                f.write(name + "\n")
    elif a.script:
        render(a.script, a.dry_run)
    else:
        ap.error("give a script path or --next")


if __name__ == "__main__":
    main()
