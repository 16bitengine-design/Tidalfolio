"""Narration with a FREE offline voice (Kokoro, Apache-2.0): no API key, no per-video cost.
Steady storyteller pacing: one speed for every sentence, a short breath between clauses, a longer pause after short dramatic sentences.
The model files (about 350 MB) are downloaded once from the kokoro-onnx GitHub release and cached in ~/.cache/tidalfolio."""
import os
import re
import sys
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
    a, _ = _kokoro().create(text, voice=voice, speed=SPEED, lang="en-gb" if voice.startswith("b") else "en-us")
    return a


def speak(text, voice="bm_george", dry=False):
    """returns (audio float32 @24 kHz, marks) where marks = [(start_s, duration_s)] per sentence."""
    sents = split_sents(text)
    if not sents:
        raise SystemExit(f"Narration has no full sentence (end each with . ? or !): {text!r}")
    parts, t, marks = [], 0.0, []
    for snt in sents:
        pieces = []
        for k, c in enumerate(clauses(speakable(snt))):
            if k:
                pieces.append(np.zeros(int(CLAUSE_GAP * SR), dtype="float32"))
            pieces.append(_say(c, voice, dry))
        a = np.concatenate(pieces)
        gap = SHORT_GAP if len(snt.split()) <= 3 else SENT_GAP
        marks.append((round(t, 3), round(len(a) / SR, 3)))
        parts += [a, np.zeros(int(gap * SR), dtype=a.dtype)]
        t += len(a) / SR + gap
    return np.concatenate(parts[:-1]), marks
