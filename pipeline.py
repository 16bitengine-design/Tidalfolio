#!/usr/bin/env python3
"""tidalfolio auto-video pipeline.

script.json -> narration (TTS) -> images (fal.ai Flux) -> Ken Burns scenes
-> dramatic sound bed + SFX -> captions -> final MP4 + metadata.

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
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FPS = 30
LEAD = 0.30          # silence before narration starts in each scene (s)
TAIL = 0.55          # silence after narration ends (s)
MIN_SCENE = 3.0      # shortest allowed scene (s)
MIN_VIDEO = 90.0     # channel rule: every video runs 1.5 to 2 minutes
MAX_VIDEO = 120.0

SIZES = {"16:9": (1920, 1080, "landscape_16_9"), "9:16": (1080, 1920, "portrait_16_9")}


# ----------------------------------------------------------------- helpers
def run(cmd):
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"Command failed: {' '.join(map(str, cmd))}\n{p.stderr[-2000:]}")
    return p.stdout


def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "csv=p=0", path])
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


def _openai_tts(text, cfg, out_wav):
    import requests
    for attempt in range(3):
        try:
            r = requests.post(
                "https://api.openai.com/v1/audio/speech", timeout=120,
                headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                json={"model": os.environ.get("OPENAI_TTS_MODEL") or "gpt-4o-mini-tts",
                      "voice": cfg.get("openai_voice", "onyx"), "input": text,
                      "instructions": cfg.get("instructions", TTS_STYLE), "response_format": "wav"})
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


def make_narration(text, cfg, out_wav, dry):
    if dry:
        d = max(1.5, len(text.split()) / 2.6)
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=220:duration={d}",
             "-af", "volume=0.08", "-ar", "44100", "-ac", "2", out_wav])
        return
    if os.environ.get("OPENAI_API_KEY") and cfg.get("provider", "openai") == "openai":
        if _openai_tts(text, cfg, out_wav):
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
def build_prompt(script, scene, aspect="16:9"):
    frame = "tall vertical 9:16 frame" if aspect == "9:16" else "wide 16:9 frame"
    parts = [script.get("style", "").replace("{frame}", frame)]
    for key in scene.get("characters", []):
        desc = script.get("characters", {}).get(key)
        if desc:
            parts.append(desc)
    parts.append(scene["image_prompt"])
    return " ".join(p.strip() for p in parts if p).strip()


def make_image(prompt, size_name, seed, out, dry, idx, aspect):
    if out.exists():
        return
    w, h, _ = SIZES[aspect]
    if dry:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (w // 2, h // 2), (20 + idx * 12 % 200, 60, 110))
        d = ImageDraw.Draw(img)
        d.text((40, 40), f"scene {idx + 1}\n{prompt[:160]}", fill=(255, 255, 255))
        img.save(out)
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
            return
        last = f"{r.status_code} {r.text[:300]}"
        time.sleep(4 * (attempt + 1))
    sys.exit(f"Image generation failed for scene {idx + 1}: {last}")


# ----------------------------------------------------------------- sound design
def synth_sfx(name, out):
    """Simple synthesized effects so the pipeline works with zero downloads.
    Drop your own files in assets/sfx/<name>.wav to override."""
    custom = ROOT / "assets" / "sfx" / f"{name}.wav"
    if custom.exists():
        shutil.copy(custom, out)
        return
    if name == "hit":
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=f=48:d=1.4", "-f", "lavfi",
             "-i", "anoisesrc=d=1.4:c=brown:a=0.8", "-filter_complex",
             "[0]afade=t=out:st=0.05:d=1.3[a];[1]lowpass=f=500,afade=t=out:d=0.6[b];"
             "[a][b]amix=inputs=2:normalize=0,volume=2.2,alimiter=limit=0.95",
             "-ar", "44100", "-ac", "2", out])
    elif name == "whoosh":
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=d=0.9:c=pink:a=0.6",
             "-af", "highpass=f=300,lowpass=f=3500,afade=t=in:d=0.4,afade=t=out:st=0.4:d=0.5,volume=0.9",
             "-ar", "44100", "-ac", "2", out])
    elif name == "splash":
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=d=0.8:c=white:a=0.7",
             "-af", "highpass=f=1200,afade=t=in:d=0.02,afade=t=out:st=0.05:d=0.7,volume=0.9",
             "-ar", "44100", "-ac", "2", out])
    else:
        sys.exit(f"Unknown sfx '{name}'. Use hit, whoosh, splash or add assets/sfx/{name}.wav")


def make_bed(total, out):
    music = sorted((ROOT / "assets" / "music").glob("*.mp3")) if (ROOT / "assets" / "music").exists() else []
    if music:  # your own royalty-free track: loop + trim
        run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", music[0], "-t", f"{total:.2f}",
             "-ar", "44100", "-ac", "2", out])
        return
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=f=55:d={total:.2f}",
         "-f", "lavfi", "-i", f"sine=f=82.4:d={total:.2f}",
         "-f", "lavfi", "-i", f"anoisesrc=d={total:.2f}:c=brown:a=0.4",
         "-filter_complex",
         "[0][1]amix=inputs=2:normalize=0[t];[2]lowpass=f=220[n];"
         "[t][n]amix=inputs=2:normalize=0,tremolo=f=0.35:d=0.5",
         "-ar", "44100", "-ac", "2", out])


# ----------------------------------------------------------------- video
def render_scene(img, dur, motion, aspect, out):
    w, h, _ = SIZES[aspect]
    n = max(1, int(round(dur * FPS)))
    if motion == "zoom_out":
        z, x, y = f"1.22-0.22*on/{n}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif motion == "pan_left":
        z, x, y = "1.18", f"(iw-iw/zoom)*(1-on/{n})", "ih/2-(ih/zoom/2)"
    elif motion == "pan_right":
        z, x, y = "1.18", f"(iw-iw/zoom)*on/{n}", "ih/2-(ih/zoom/2)"
    else:  # zoom_in (default)
        z, x, y = f"1+0.22*on/{n}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    vf = (f"scale={2 * w}:{2 * h}:force_original_aspect_ratio=increase,crop={2 * w}:{2 * h},"
          f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={w}x{h}:fps={FPS},"
          f"eq=contrast=1.08:saturation=1.1,format=yuv420p")
    run(["ffmpeg", "-y", "-i", img, "-vf", vf, "-frames:v", n, "-r", FPS,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", out])


FOLDERS = {"16:9": "youtube", "9:16": "vertical"}


def render_aspect(script, scenes, aspect, out_root, narr_dir, total, dry):
    w, h, size_name = SIZES[aspect]
    folder = FOLDERS[aspect]
    seed = int(script.get("seed", 7))
    out_dir = out_root / folder
    work = out_root / f"work_{folder}"
    out_dir.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    print(f"=== {folder} ({aspect}) ===")

    # images
    print("[2/5] images")
    for i, sc in enumerate(scenes):
        make_image(build_prompt(script, sc, aspect), size_name, seed, work / f"img_{i:02}.png", dry, i, aspect)

    # scenes with Ken Burns motion
    print("[3/5] scene clips")
    motions = ["zoom_in", "pan_right", "zoom_out", "pan_left"]
    listing = []
    for i, sc in enumerate(scenes):
        clip = work / f"clip_{i:02}.mp4"
        render_scene(work / f"img_{i:02}.png", sc["_dur"], sc.get("motion", motions[i % 4]), aspect, clip)
        listing.append(f"file '{clip.resolve()}'")
    (work / "clips.txt").write_text("\n".join(listing))
    silent = work / "silent.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", work / "clips.txt", "-c", "copy", silent])

    # audio: narration track + dramatic bed + SFX hits
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
    make_bed(total, bed)
    mix_inputs = ["-i", narration, "-i", bed]
    mix_filter = ["[1]volume=0.20[bed]"]
    labels = ["[0]", "[bed]"]
    k = 2
    for i, sc in enumerate(scenes):
        for name in ([sc["sfx"]] if isinstance(sc.get("sfx"), str) else sc.get("sfx", [])):
            f = work / f"sfx_{name}.wav"
            if not f.exists():
                synth_sfx(name, f)
            ms = int(sc["_start"] * 1000)
            mix_inputs += ["-i", f]
            mix_filter.append(f"[{k}]adelay={ms}|{ms},volume=0.85[s{k}]")
            labels.append(f"[s{k}]")
            k += 1
    mix_filter.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=longest,"
                      f"afade=t=out:st={max(0, total - 1.5):.2f}:d=1.5,alimiter=limit=0.95[mix]")
    mixed = work / "mix.wav"
    run(["ffmpeg", "-y", *mix_inputs, "-filter_complex", ";".join(mix_filter),
         "-map", "[mix]", "-t", f"{total:.2f}", "-ar", "44100", "-ac", "2", mixed])

    # captions + final mux
    print("[5/5] captions + final video")
    srt, idx = [], 1
    for sc in scenes:
        words = sc["narration"].split()
        parts = -(-len(words) // 7) or 1            # at most ~7 words per caption
        size = -(-len(words) // parts) or 1         # balanced chunk sizes
        chunks = [words[j:j + size] for j in range(0, len(words), size)] or [[""]]
        per = sc["_narr"] / len(chunks)
        for c, chunk in enumerate(chunks):
            s = sc["_start"] + LEAD + c * per
            srt += [str(idx), f"{srt_time(s)} --> {srt_time(s + per)}", " ".join(chunk), ""]
            idx += 1
    srt_path = out_dir / "captions.srt"
    srt_path.write_text("\n".join(srt))

    final = out_dir / "video.mp4"
    burn = script.get("burn_captions", True) and has_filter("subtitles")
    cmd = ["ffmpeg", "-y", "-i", silent, "-i", mixed]
    if burn:
        size, margin = (13, 22) if aspect == "16:9" else (8, 70)
        style = f"FontName=DejaVu Sans,FontSize={size},Bold=1,Outline=3,Shadow=0,Alignment=2,MarginV={margin}"
        esc = str(srt_path).replace("\\", "/").replace(":", "\\:")
        cmd += ["-vf", f"subtitles='{esc}':force_style='{style}'",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
    else:
        cmd += ["-c:v", "copy"]
        if script.get("burn_captions", True):
            print("      (subtitles filter not available: captions.srt written but not burned in)")
    cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", final]
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

    # narration first (shared by every aspect): cheap, and tells us the runtime before paying for images
    print(f"[1/5] narration ({len(scenes)} scenes)")
    t = 0.0
    for i, sc in enumerate(scenes):
        wav = narr_dir / f"narr_{i:02}.wav"
        if not wav.exists():
            make_narration(sc["narration"], voice_cfg, wav, dry)
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
