"""Render a "puppet" script (engine: "puppet") into a finished 9:16 video.

Same output layout as pipeline.py, so upload_youtube.py and post_tiktok.py work unchanged:
  output/<slug>/vertical/video.mp4   (TikTok / Shorts)
  output/<slug>/youtube/video.mp4    (the same vertical video; YouTube treats it as a Short), thumbnail.png, captions.srt
  output/<slug>/metadata.md, metadata.json,  output/LAST_SLUG
Costs nothing: no image API, no paid narration. Needs ffmpeg, numpy, pillow, soundfile, kokoro-onnx, requests.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from . import dsl, engine as E, music, tts, worlds

ROOT = Path(__file__).resolve().parent.parent
OUT_W, OUT_H = 720, 1280
MIN_LEN, MAX_LEN = 45.0, 60.0        # the channel rule: every video (every part) runs 45 to 60 seconds
LEAD, TAIL, END_CARD = 0.5, 1.0, dsl.END_SEC  # silence before the line, after it, and the closing title card

FADE_OUT = 0.7  # seconds of fade to black at the very end
_JOB = {}      # shared with the worker processes (they are forked after this is filled in)


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"command failed: {' '.join(map(str, cmd[:4]))} ...\n{r.stderr[-1500:]}")
    return r


def _srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


# ------------------------------------------------------------------ narration + timing
def make_narration(script, scenes, narr_dir, dry):
    import soundfile as sf
    voice = (script.get("voice") or {}).get("kokoro", tts.CHANNEL_VOICE)
    narr_dir.mkdir(parents=True, exist_ok=True)
    for i, sc in enumerate(scenes):
        key = hashlib.sha1(f"{voice}|{sc['narration']}|{dry}|w3radio".encode()).hexdigest()[:12]
        wav, meta = narr_dir / f"narr_{i:02}.wav", narr_dir / f"narr_{i:02}.json"
        if not (wav.exists() and meta.exists() and json.loads(meta.read_text()).get("key") == key):
            audio, marks = tts.speak(sc["narration"], voice, dry)
            sf.write(str(wav), audio, tts.SR)
            meta.write_text(json.dumps({"key": key, "marks": marks, "detail": list(tts.LAST_DETAIL), "dur": len(audio) / tts.SR}))
        m = json.loads(meta.read_text())
        sc["_marks"], sc["_au"], sc["_wav"], sc["_detail"] = m["marks"], m["dur"], wav, m.get("detail")
        sc["_i"] = i


def plan_timing(scenes):
    t = 0.0
    for sc in scenes:
        sc["_D"] = sc["_au"] + LEAD + TAIL + (END_CARD if sc.get("end_card") else 0.0)
        sc["_start"] = t
        t += sc["_D"]
    return t


def narration_time(scenes):
    def nt(i, phrase):
        sc = scenes[i]
        text = sc["narration"]
        idx = text.find(phrase)
        if idx < 0:
            raise SystemExit(f"Scene {i + 1}: the words {phrase!r} are not in its narration, so nothing can be timed to them.")
        pos = 0
        for k_, ((st, du), snt) in enumerate(zip(sc["_marks"], tts.split_sents(text))):
            s0 = text.find(snt, pos)
            pos = s0 + len(snt)
            if s0 <= idx < s0 + len(snt):
                det = (sc.get("_detail") or [None] * 99)[k_]
                if det:                                    # exact clause timing, syllable-weighted inside the clause
                    return LEAD + tts.word_time(snt, det, idx - s0)
                return LEAD + st + du * (idx - s0) / max(1, len(snt))
        return LEAD
    return nt


# ------------------------------------------------------------------ frames
def frame(gt, with_text=True):
    scenes, ctx = _JOB["scenes"], _JOB["ctx"]
    sc = [s for s in scenes if gt >= s["_start"] - 1e-9][-1]
    D = sc["_D"]
    u = min(gt - sc["_start"], D - 1e-3)
    E.C.tick = int(gt * E.FPS) // 2                 # hand-drawn ink "boil" on twos
    E.C.cx, E.C.cy, E.C.z = E.W / 2, E.H / 2, 1.0
    from PIL import Image
    img = Image.new("RGB", (E.W, E.H), (0, 0, 0))
    dsl.draw_scene(img, sc, u, D, ctx)
    img = E.finish(img)                            # paper grain + vignette
    tone = sc.get("tone", "calm")                  # colour, light, mist and tremble that carry the scene's tone (captions stay clean)
    i = scenes.index(sc)
    prev = scenes[i - 1].get("tone", "calm") if i else tone
    img = E.tone_grade(img, E.grade_params(prev, tone, u / 0.8), gt, E.TONE_SHAKE.get(tone, 0.0))
    if with_text and u < LEAD + sc["_au"] + 0.3:
        E.captions(img, sc["narration"], u, LEAD + sc["_au"], lead=LEAD, tail=0.0)
    img = img.resize((OUT_W, OUT_H), Image.LANCZOS)
    tail = _JOB.get("total", 1e9) - gt
    if tail < FADE_OUT:                             # soft fade to black on the very last moments
        img = Image.eval(img, lambda v, k=max(0.0, tail / FADE_OUT): int(v * k))
    return img


def _frame_bytes(i):
    return frame(i / E.FPS).tobytes()


def render_silent(total, out, workers):
    n = int(total * E.FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OUT_W}x{OUT_H}", "-r", str(E.FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(workers) as pool:
        for k, b in enumerate(pool.imap(_frame_bytes, range(n), chunksize=8)):
            p.stdin.write(b)
            if k % 240 == 0:
                print(f"      frame {k}/{n}", flush=True)
    p.stdin.close()
    if p.wait():
        sys.exit("ffmpeg failed while encoding the frames")


# the narrator's colour per tone: (semitones, volume). Pitch moves with the tempo held constant, so the pace never changes.
VOICE_TONE = {"sad": (-0.7, 0.88), "tense": (-0.4, 1.0), "eerie": (-0.8, 0.9), "joyful": (0.5, 1.08), "playful": (0.3, 1.04), "tender": (-0.2, 0.92)}


def _voice_filter(tone):
    st, vol = VOICE_TONE.get(tone, (0.0, 1.0))
    if not st:
        return f"volume={1.6 * vol:.2f}"
    r = 2 ** (st / 12)
    return f"asetrate={44100 * r:.1f},aresample=44100,atempo={1 / r:.5f},volume={1.6 * vol:.2f}"


def mux(silent, music_wav, scenes, out, total):
    inputs, filt, labels = ["-i", str(silent), "-i", str(music_wav)], [], []
    tracks = [(sc["_wav"], sc["_start"] + LEAD, sc.get("tone", "calm")) for sc in scenes]
    for n, (wav, at, tone) in enumerate(tracks):
        inputs += ["-i", str(wav)]
        ms = int(at * 1000)
        filt.append(f"[{n + 2}:a]aresample=44100,{_voice_filter(tone)},adelay={ms}|{ms}[v{n}]")
        labels.append(f"[v{n}]")
    filt += ["".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest[voice]",
             "[voice]apad=pad_dur=120,asplit=2[vk][vm]",
             "[1:a]aresample=44100[mus]",
             "[mus][vk]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=500[duck]",     # music ducks under the narrator
             f"[duck][vm]amix=inputs=2:normalize=0:duration=longest,alimiter=limit=0.95,afade=t=out:st={total - 1.2:.2f}:d=1.2[a]"]
    _run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt), "-map", "0:v", "-map", "[a]",
          "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)])


# ------------------------------------------------------------------ extras
def write_srt(scenes, path):
    lines, n = [], 1
    for sc in scenes:
        for (st, du), snt in zip(sc["_marks"], tts.split_sents(sc["narration"])):
            a = sc["_start"] + LEAD + st
            lines += [str(n), f"{_srt_time(a)} --> {_srt_time(a + du)}", snt.strip(), ""]
            n += 1
    path.write_text("\n".join(lines))


def write_metadata(script, out_root, total, slug, scenes):
    yt, tt = script.get("youtube", {}), script.get("tiktok", {})
    sp = script.get("series_part")
    part_line = f"Part {sp['part']} of {sp['of']} of \"{sp['story']}\"" if sp else "Single video"
    md = [f"# {script.get('title', slug)}", f"Runtime: {total:.1f}s", part_line, "",
          "## YouTube (youtube/video.mp4)", f"**Title:** {yt.get('title', '')}", "", "**Description:**", yt.get("description", ""), "",
          f"**Tags:** {', '.join(yt.get('tags', []))}", "", f"**Pinned comment:** {yt.get('pinned_comment', '')}", "",
          "## TikTok (vertical/video.mp4)", f"**Caption:** {tt.get('caption', '')}", "", f"**Hashtags:** {' '.join(tt.get('hashtags', []))}", ""]
    (out_root / "metadata.md").write_text("\n".join(md))
    (out_root / "metadata.json").write_text(json.dumps(
        {"title": script.get("title", slug), "youtube": yt, "tiktok": tt,
         "info": {"slug": slug, "series": script.get("title", "").split(" #")[0] if " #" in script.get("title", "") else "",
                  "runtime": round(total, 1), "scene_count": len(scenes), "part": sp, "engine": "puppet",
                  "hook": scenes[0]["narration"][:200]}}, indent=2))


# ------------------------------------------------------------------ preview stills
def render_stills(script_path, times, outdir):
    """Quick look: PNGs at the given seconds of each scene (no video, silent narration)."""
    script = json.loads(Path(script_path).read_text())
    scenes = script["scenes"]
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    make_narration(script, scenes, outdir / "narration", True)
    plan_timing(scenes)
    E.set_look(script.get("look", "ink"))
    ctx = type("Ctx", (), {})()
    ctx.worlds, ctx.nt, ctx.script = ({} if script.get("look") == "vector" else worlds.bake_for(script)), narration_time(scenes), script
    _JOB.update(scenes=scenes, ctx=ctx)
    for i, sc in enumerate(scenes):
        for t in times:
            frame(sc["_start"] + min(t, sc["_D"] - 0.05)).save(outdir / f"s{i + 1:02}_{t:04.1f}.png")


# ------------------------------------------------------------------ main entry
def render_script(script_path, dry=False, workers=None):
    script = json.loads(Path(script_path).read_text())
    if script.get("engine") != "puppet":
        sys.exit(f"{script_path} is not a puppet script (it needs \"engine\": \"puppet\").")
    slug = script.get("slug") or Path(script_path).stem
    out_root = ROOT / "output" / slug
    work = out_root / "work"
    work.mkdir(parents=True, exist_ok=True)
    scenes = script["scenes"]
    sp = script.get("series_part")
    if sp and sp["part"] < sp["of"]:          # a part that is followed by another one ends plainly: no end screen, no sign-off
        for sc in scenes:
            sc.pop("end_card", None)

    print(f"[1/5] narration ({len(scenes)} scenes, voice {(script.get('voice') or {}).get('kokoro', tts.CHANNEL_VOICE)})", flush=True)
    make_narration(script, scenes, out_root / "narration", dry)
    total = plan_timing(scenes)
    print(f"      total runtime: {total:.1f}s", flush=True)
    if not dry and not (MIN_LEN <= total <= MAX_LEN):
        sys.exit(f"Video would be {total:.1f}s but every video must run {MIN_LEN:.0f} to {MAX_LEN:.0f} s. "
                 "Nothing was rendered. Shorten or lengthen the narration (or split a very long story into parts).")

    nt = narration_time(scenes)
    print("[2/5] painting the worlds", flush=True)
    E.set_look(script.get("look", "ink"))
    ctx = type("Ctx", (), {})()
    ctx.worlds, ctx.nt, ctx.script = ({} if script.get("look") == "vector" else worlds.bake_for(script)), nt, script
    _JOB.update(scenes=scenes, ctx=ctx, total=total)

    print("[3/5] music", flush=True)
    music.synth(scenes, [s["_start"] for s in scenes], [s["_D"] for s in scenes], total, nt, work / "music.wav",
                outro=END_CARD if any(sc.get("end_card") for sc in scenes) else 2.0, theme=script.get("theme", "fusion"))

    print("[4/5] drawing frames", flush=True)
    workers = workers or max(1, os.cpu_count() or 2)
    silent = work / "silent.mp4"
    render_silent(total, silent, workers)

    print("[5/5] mixing narration and music", flush=True)
    for sub in ("vertical", "youtube"):
        (out_root / sub).mkdir(exist_ok=True)
    final = out_root / "vertical" / "video.mp4"
    mux(silent, work / "music.wav", scenes, final, total)
    shutil.copy(final, out_root / "youtube" / "video.mp4")

    thumb_i = int(script.get("thumbnail_scene", 1)) - 1
    sc = scenes[thumb_i]
    key = frame(sc["_start"] + min(sc["_D"] - 2.0, LEAD + sc["_au"] * 0.6), with_text=False)
    key.save(out_root / "youtube" / "thumbnail_frame.png")                       # the plain frame, kept for reference
    from . import thumbnail
    thumbnail.make(key, script, slug).save(out_root / "youtube" / "thumbnail.png")   # branded, unique to this story
    for sub in ("vertical", "youtube"):
        write_srt(scenes, out_root / sub / "captions.srt")
    write_metadata(script, out_root, total, slug, scenes)
    (ROOT / "output" / "LAST_SLUG").write_text(slug)
    shutil.rmtree(work, ignore_errors=True)
    print(f"Done: {out_root} ({total:.1f}s)")
    return slug
