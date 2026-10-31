#!/usr/bin/env python3
"""tidalfolio auto-video pipeline.

script.json -> narration (a deep older woman, TTS directed per scene) -> storybook illustrations
(fal.ai Flux) -> multi-shot scenes with camera moves -> pop-ups (speech bubbles, labels, painted props)
-> music bed under her voice (music only, no sound effects) -> highlighted-word captions
-> final MP4 (16:9 and 9:16) + thumbnail + upload details.

Usage:
  python pipeline.py scripts/001-bird-banter-kingfishers.json
  python pipeline.py --next              # render the next script in queue.txt not in done.txt
  python pipeline.py SCRIPT --dry-run    # no API calls: placeholder images + tone "narration"
"""
import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import popups

ROOT = Path(__file__).resolve().parent
FPS = 30
LEAD = 0.30          # silence before narration starts in each scene (s)
TAIL = 0.55          # silence after narration ends (s)
MIN_SCENE = 3.0      # shortest allowed scene (s)
MIN_VIDEO = 90.0     # channel rule: every video runs 1.5 to 2 minutes
MAX_VIDEO = 120.0
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


TTS_STYLE = ("The voice of a woman in her sixties: deep, low and slightly raspy, warm and unhurried, like a grandmother "
             "telling a story she has told many times and still finds funny. Dry and deadpan, never sing-song, never "
             "robotic, never a cheerful announcer. Short pauses before the punchline, and now and then a small "
             "amused breath or sigh. Gravity about tiny things is what makes it funny.")
OPENAI_VOICE = "sage"        # also worth trying: coral, fable, shimmer. Set per script with voice.openai_voice
DEEPEN = 0.94                # below 1.0 lowers the pitch without changing the speed (0.90 to 1.0). voice.deepen overrides
EDGE_VOICE, EDGE_RATE, EDGE_PITCH = "en-GB-SoniaNeural", "-12%", "-10Hz"   # free fallback voice, also a woman


def _deepen(src, dst, factor):
    """Lower the pitch by `factor` while keeping the speed (resample down, then speed the tempo back up)."""
    if abs(factor - 1.0) < 0.005:
        run(["ffmpeg", "-y", "-i", src, "-ar", "44100", "-ac", "2", dst])
        return
    run(["ffmpeg", "-y", "-i", src, "-af",
         f"aresample=44100,asetrate=44100*{factor},aresample=44100,atempo={1 / factor:.5f}",
         "-ar", "44100", "-ac", "2", dst])


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
                      "voice": cfg.get("openai_voice", OPENAI_VOICE), "input": text,
                      "instructions": instructions, "response_format": "wav"})
            if r.ok and len(r.content) > 1000:
                raw = out_wav.with_suffix(".raw.wav")
                raw.write_bytes(r.content)
                _deepen(raw, out_wav, float(cfg.get("deepen", DEEPEN)))
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
            asyncio.run(_edge_tts(text, cfg.get("voice", EDGE_VOICE),
                                  cfg.get("rate", EDGE_RATE), cfg.get("pitch", EDGE_PITCH), mp3))
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
    fal_generate(prompt, size_name, out, seed, f"scene {idx + 1}")
    bake_vignette(out)


def fal_generate(prompt, size_name, out, seed=7, what="image"):
    """One image from fal.ai, saved to `out`. Used for scene illustrations and for pop-up props."""
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
            return
        last = f"{r.status_code} {r.text[:300]}"
        time.sleep(4 * (attempt + 1))
    sys.exit(f"Image generation failed for {what}: {last}")


# ----------------------------------------------------------------- music (the only thing under her voice)
# No sound effects anywhere. The bed is, in order of preference:
#   1. a track from assets/music/ (yours, licensed or royalty-free; one is picked per video)
#   2. a track generated once per video with fal.ai (needs FAL_KEY; set MUSIC_GENERATE=0 to turn off)
#   3. a quiet synthesized pad, only so the pipeline still runs (add real music to assets/music/)
MUSIC_PROMPT = ("gentle dry-humoured acoustic folk, plucked nylon guitar and soft upright bass, slow tempo, "
                "wry and warm, instrumental, no vocals, no drums, seamless loop")
MUSIC_VOLUME = 0.5           # before it ducks under her voice
MUSIC_FADE = 2.0             # crossfade at each loop seam (s)


def music_library():
    d = ROOT / "assets" / "music"
    return sorted(p for pat in ("*.mp3", "*.wav", "*.m4a", "*.ogg") for p in d.glob(pat)) if d.exists() else []


def loop_to_length(src, total, out):
    """Repeat a track, crossfading each seam, until it covers `total` seconds."""
    n = duration(src)
    if n >= total + 0.5:
        run(["ffmpeg", "-y", "-i", src, "-t", f"{total:.2f}", "-ar", "44100", "-ac", "2", out])
    elif n <= 3 * MUSIC_FADE:
        run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", src, "-t", f"{total:.2f}", "-ar", "44100", "-ac", "2", out])
    else:
        reps = int(-(-(total - MUSIC_FADE) // (n - MUSIC_FADE))) + 1
        ins = [x for _ in range(reps) for x in ("-i", src)]
        fl, prev = [], "[0]"
        for k in range(1, reps):
            nxt = f"[a{k}]"
            fl.append(f"{prev}[{k}]acrossfade=d={MUSIC_FADE}:c1=tri:c2=tri{nxt}")
            prev = nxt
        run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(fl), "-map", prev, "-t", f"{total:.2f}",
             "-ar", "44100", "-ac", "2", out])


def fal_music(prompt, seconds, out):
    """One music track from fal.ai (Stable Audio). Returns False on any problem so the caller can fall back."""
    try:
        import requests
        r = requests.post("https://fal.run/fal-ai/stable-audio", timeout=300,
                          headers={"Authorization": f"Key {os.environ['FAL_KEY']}"},
                          json={"prompt": prompt, "seconds_total": min(int(seconds), 47)})
        if not r.ok:
            print(f"      music generation failed ({r.status_code}): {r.text[:160]}")
            return False
        j = r.json()
        url = (j.get("audio_file") or j.get("audio") or {}).get("url")
        audio = requests.get(url, timeout=180)
        audio.raise_for_status()
        out.write_bytes(audio.content)
        return True
    except Exception as e:
        print(f"      music generation failed: {e}")
        return False


def synth_pad(total, out):
    """Placeholder only: a warm, very quiet chord so a video still renders when no real music is available."""
    T = f"{total:.2f}"
    freqs = (110, 164.81, 220, 261.63, 329.63)
    ins = [x for f in freqs for x in ("-f", "lavfi", "-i", f"sine=f={f}:d={T}")]
    run(["ffmpeg", "-y", *ins, "-filter_complex",
         f"amix=inputs={len(freqs)}:normalize=0,tremolo=f=0.18:d=0.35,lowpass=f=1400,volume=0.6",
         "-ar", "44100", "-ac", "2", out])


def make_bed(total, out, slug, prompt, dry):
    lib = music_library()
    if lib:
        pick = lib[int(hashlib.sha1(slug.encode()).hexdigest(), 16) % len(lib)]
        loop_to_length(pick, total, out)
        return f"music: {pick.name}"
    if not dry and os.environ.get("FAL_KEY") and os.environ.get("MUSIC_GENERATE", "1") != "0":
        gen = out.with_name("music_generated.mp3")
        if gen.exists() or fal_music(prompt, total, gen):
            loop_to_length(gen, total, out)
            return "music: generated with fal.ai"
    synth_pad(total, out)
    return "music: PLACEHOLDER pad (add a licensed track to assets/music/)"


# ----------------------------------------------------------------- shots (the illusion of action)
FOCUS_X = {"left": 0.32, "center": 0.5, "right": 0.68}


IMPACT = {"impact", "hit", "splash", "boom"}      # camera slam + shake + white flash (silent: no sound is played)
ENTRANCE = {"whoosh"}                              # camera whips across the frame


def camera_hints(sc):
    """What a scene asks of the camera. New scripts use "camera": "impact" | "whoosh". Old scripts' "sfx" tags
    are still read as camera hints only; no sound effect is ever played."""
    out = set()
    for key in ("camera", "sfx"):
        v = sc.get(key)
        out |= {v} if isinstance(v, str) and v else set(v or [])
    return out


def n_shots(sc):
    return max(1, int(round(sc["_dur"] / 2.5)))      # a new framing about every 2.5 seconds


def plan_shots(sc, use_b):
    """Cut each scene into several shots: a wide opening move, a punch-in, a drift; a second image
    (the same moment a beat later) on action scenes; slam + shake + white flash on impacts."""
    n = n_shots(sc)
    hints = camera_hints(sc)
    fx = FOCUS_X.get(sc.get("focus"), 0.5)
    first_b = (n + 1) // 2 if (use_b and n >= 2) else n
    impact = bool(hints & IMPACT)
    whoosh = bool(hints & ENTRANCE)
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
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", out])


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


# ----------------------------------------------------------------- one aspect ratio, start to finish
def render_aspect(script, scenes, aspect, out_root, narr_dir, total, dry, bed):
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

    print("[4/5] narration + music mix (no sound effects)")
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

    # her voice, warmed up a little (no echo: she is telling a story in a kitchen, not a canyon), over the music
    # bed, which ducks whenever she speaks
    fl = ["[0]highpass=f=70,equalizer=f=140:t=q:w=1:g=3,equalizer=f=3200:t=q:w=1.2:g=1.5,"
          "acompressor=threshold=0.1:ratio=3:attack=5:release=120:makeup=3,"
          "alimiter=limit=0.95,asplit=2[nar][nsc]",
          f"[1]volume={MUSIC_VOLUME}[bedv]",
          "[bedv][nsc]sidechaincompress=threshold=0.03:ratio=8:attack=15:release=450[mbed]",
          f"[nar][mbed]amix=inputs=2:normalize=0:duration=longest,"
          f"afade=t=out:st={max(0, total - 2.5):.2f}:d=2.5,"
          "loudnorm=I=-15:TP=-1.5:LRA=6,alimiter=limit=0.95[mix]"]
    mixed = work / "mix.wav"
    run(["ffmpeg", "-y", "-i", narration, "-i", bed, "-filter_complex", ";".join(fl),
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

    # pop-ups: speech bubbles, labels and painted props that bounce in over the illustration
    sticker_dir = out_root / "stickers"
    pops = popups.build(scenes, w, h, work, sticker_dir, dry,
                        lambda prompt, size, out: fal_generate(prompt, size, out, seed, "pop-up prop"))
    print(f"      {len(pops)} pop-ups")

    final = out_dir / "video.mp4"
    burn = script.get("burn_captions", True) and has_filter("ass")
    if script.get("burn_captions", True) and not burn:
        print("      (ass filter not available: captions not burned in)")
    cmd = ["ffmpeg", "-y", "-i", silent, "-i", mixed, *popups.overlay_inputs(pops, FPS)]
    chains = popups.overlay_graph(pops, "0:v", 2, "vpop")
    last = "vpop" if pops else "0:v"
    if burn:
        esc = str(ass_path).replace("\\", "/").replace(":", "\\:")
        chains.append(f"[{last}]ass='{esc}'[vout]")
        last = "vout"
    if chains:
        cmd += ["-filter_complex", ";".join(chains), "-map", f"[{last}]", "-map", "1:a",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a", "-c:v", "copy"]
    cmd += ["-c:a", "aac", "-b:a", "192k", "-t", f"{total:.2f}", "-movflags", "+faststart", final]
    run(cmd)

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

    # narration made with an older voice setting must not be reused: remember which voice made these files
    sig = json.dumps([voice_cfg, TTS_STYLE, OPENAI_VOICE, DEEPEN, EDGE_VOICE, dry], sort_keys=True)
    sig_file = narr_dir / "voice_signature.txt"
    if sig_file.exists() and sig_file.read_text() != sig:
        for old in narr_dir.glob("narr_*.wav"):
            old.unlink()
    sig_file.write_text(sig)

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

    # one music bed per video, shared by both formats
    bed = out_root / "bed.wav"
    print(f"[music] {make_bed(total, bed, slug, script.get('music_prompt') or MUSIC_PROMPT, dry)}")

    for aspect in aspects:
        render_aspect(script, scenes, aspect, out_root, narr_dir, total, dry, bed)

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
