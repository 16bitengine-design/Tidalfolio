"""Narration with a FREE offline voice (Kokoro, Apache-2.0): no API key, no per-video cost.
Steady storyteller pacing: one speed for every sentence, a short breath between clauses, a longer pause after short dramatic sentences.
The model files (about 350 MB) are downloaded once from the kokoro-onnx GitHub release and cached in ~/.cache/tidalfolio."""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

SR = 24000
MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")
CACHE = Path(os.environ.get("TIDAL_MODEL_DIR", Path.home() / ".cache" / "tidalfolio" / "kokoro"))
_k = None


def split_sents(text):
    return re.findall(r'[^.!?]+[.!?]+"?', text)


def ensure_models():
    import requests
    CACHE.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        dest = CACHE / f
        if dest.exists() and dest.stat().st_size > 1_000_000:
            continue
        print(f"      downloading {f} (one time) ...", flush=True)
        with requests.get(MODEL_URL + f, stream=True, timeout=120) as r:
            r.raise_for_status()
            tmp = dest.with_suffix(".part")
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
            tmp.rename(dest)
    return CACHE / FILES[0], CACHE / FILES[1]


def _kokoro():
    global _k
    if _k is None:
        from kokoro_onnx import Kokoro
        m, v = ensure_models()
        _k = Kokoro(str(m), str(v))
    return _k


# The channel's own voice ("tidal"): a middle-aged radio presenter, easy and warm. It is a blend of two Kokoro voices
# (60% bm_lewis, 40% am_michael) plus a radio finish (a touch lower, bass warmth, presence, gentle compression).
# Old scripts that still ask for "bm_george" get this voice too, so every video sounds the same.
CHANNEL_VOICE = "tidal"
CHANNEL_BLEND = (("bm_lewis", 0.6), ("am_michael", 0.4))
LEGACY_NAMES = ("bm_george", "tidal")
PITCH_SEMITONES, BASS_DB, PRESENCE_DB = -0.5, 3.0, 2.5
_style = None


def channel_style():
    global _style
    if _style is None:
        k = _kokoro()
        _style = sum(w * k.get_voice_style(v) for v, w in CHANNEL_BLEND) / sum(w for _, w in CHANNEL_BLEND)
    return _style


def radio_finish(audio):
    """Lower the pitch a little, add low-end warmth and presence, and level it gently (ffmpeg). The length stays the same, so the
    sentence timings measured by speak() stay valid. If ffmpeg is missing the plain audio is returned."""
    try:
        import soundfile as sf
        r = 2 ** (PITCH_SEMITONES / 12)
        af = (f"asetrate={int(SR * r)},aresample={SR},atempo={1 / r:.4f},"
              f"equalizer=f=110:t=h:w=100:g={BASS_DB},equalizer=f=3200:t=q:w=1.2:g={PRESENCE_DB},"
              "acompressor=threshold=-20dB:ratio=3:attack=15:release=180:makeup=4,alimiter=limit=0.9:level=disabled")
        with tempfile.TemporaryDirectory() as d:
            src, dst = os.path.join(d, "in.wav"), os.path.join(d, "out.wav")
            sf.write(src, audio, SR)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", af, "-ac", "1", "-ar", str(SR), dst], check=True)
            out, _ = sf.read(dst, dtype="float32")
        n = len(audio)
        return out[:n] if len(out) >= n else np.concatenate([out, np.zeros(n - len(out), dtype="float32")])
    except Exception as e:
        print(f"      radio finish skipped: {e}")
        return audio


SPEED = 0.82          # ONE speed for every sentence: the pace must never speed up or slow down inside a story
SENT_GAP, SHORT_GAP, CLAUSE_GAP = 0.50, 0.70, 0.14
_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = "zero ten twenty thirty forty fifty sixty seventy eighty ninety".split()


def _num(n):
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("-" + _ONES[n % 10] if n % 10 else "")
    if n < 1000:
        return _ONES[n // 100] + " hundred" + (" " + _num(n % 100) if n % 100 else "")
    if n < 1000000:
        return _num(n // 1000) + " thousand" + (" " + _num(n % 1000) if n % 1000 else "")
    return str(n)


def speakable(text):
    """Make the text safe for the voice: all-capital words (MINE) are spelled out letter by letter by many voices, so lower-case them;
    digits become words; symbols the voice would read aloud or stumble on are replaced."""
    t = text.replace("&", " and ").replace("%", " percent").replace("\u2014", ", ").replace("\u2013", ", ").replace(" - ", ", ").replace("*", "")
    t = re.sub(r"\b\d{1,6}\b", lambda m: _num(int(m.group(0))), t)
    t = re.sub(r"\b([A-Z]{2,})\b", lambda m: m.group(1).lower(), t)
    t = re.sub(r"\s+", " ", t).replace(" ,", ",").replace(",,", ",")
    return t.strip()


def clauses(snt, max_words=11):
    """Long sentences are spoken in clauses (split at commas, semicolons, colons): a voice given a long run of words hurries through it."""
    if len(snt.split()) <= max_words:
        return [snt]
    out, cur = [], ""
    for piece in re.split(r"(?<=[,;:])\s+", snt):
        if cur and len((cur + " " + piece).split()) > max_words and len(cur.split()) >= 4:
            out.append(cur)
            cur = piece
        else:
            cur = (cur + " " + piece).strip()
    if cur:
        if out and len(cur.split()) < 3:
            out[-1] += " " + cur
        else:
            out.append(cur)
    return out


def _say(text, voice, dry):
    words = len(text.split())
    if dry:
        return np.zeros(int(words / 2.2 * SR), dtype="float32")
    if voice in LEGACY_NAMES:
        a, _ = _kokoro().create(text, voice=channel_style(), speed=SPEED, lang="en-gb")
        return a
    a, _ = _kokoro().create(text, voice=voice, speed=SPEED, lang="en-gb" if voice.startswith("b") else "en-us")
    return a


LAST_DETAIL = []          # set by speak(): for every sentence, its clauses as (chars_from, chars_to, start_s, duration_s) in the spoken text


def speak(text, voice=CHANNEL_VOICE, dry=False):
    """returns (audio float32 @24 kHz, marks) where marks = [(start_s, duration_s)] per sentence.
    tts.LAST_DETAIL then holds the clause timings, so words can be placed in time much more exactly than by sentence."""
    sents = split_sents(text)
    if not sents:
        raise SystemExit(f"Narration has no full sentence (end each with . ? or !): {text!r}")
    parts, t, marks, detail = [], 0.0, [], []
    for snt in sents:
        pieces, cl, tc, pos = [], [], t, 0
        spoken = speakable(snt)
        for k, c in enumerate(clauses(spoken)):
            if k:
                pieces.append(np.zeros(int(CLAUSE_GAP * SR), dtype="float32"))
                tc += CLAUSE_GAP
            a_ = _say(c, voice, dry)
            pieces.append(a_)
            c0 = spoken.find(c, pos)
            pos = c0 + len(c)
            cl.append((c0, pos, round(tc, 3), round(len(a_) / SR, 3)))
            tc += len(a_) / SR
        a = np.concatenate(pieces)
        gap = SHORT_GAP if len(snt.split()) <= 3 else SENT_GAP
        marks.append((round(t, 3), round(len(a) / SR, 3)))
        detail.append({"len": len(spoken), "clauses": cl})
        parts += [a, np.zeros(int(gap * SR), dtype=a.dtype)]
        t += len(a) / SR + gap
    LAST_DETAIL[:] = detail
    audio = np.concatenate(parts[:-1])
    if not dry and voice in LEGACY_NAMES:
        audio = radio_finish(audio)
    return audio, marks


def _syl(w):
    return max(1, len(re.findall(r"[aeiouy]+", w.lower())))


def word_time(snt, detail, idx):
    """seconds (from the start of the narration) at which the character at position idx of the sentence is spoken:
    first the clause it is in, then its place inside that clause weighted by syllables (a long word takes longer than a short one)."""
    n = max(1, len(snt))
    pos = min(detail["len"] - 1, int(idx * detail["len"] / n)) if detail["len"] else 0
    cl = detail["clauses"]
    c = next((c for c in cl if c[0] <= pos < c[1]), cl[-1] if pos >= cl[-1][1] else cl[0])
    c0, c1, st, du = c
    text = snt_text = None
    # syllable weights are taken from the original sentence characters of this clause
    s0 = int(c0 * n / max(1, detail["len"]))
    s1 = int(c1 * n / max(1, detail["len"]))
    seg = snt[s0:s1] or snt
    rel = max(0, min(len(seg), idx - s0))
    words = [(m.start(), m.end(), _syl(m.group(0))) for m in re.finditer(r"[\w'-]+", seg)] or [(0, len(seg), 1)]
    total = sum(w[2] for w in words)
    before = 0.0
    for a, b, k in words:
        if rel >= b:
            before += k
        elif rel >= a:
            before += k * (rel - a) / max(1, b - a)
            break
        else:
            break
    return st + du * before / total
