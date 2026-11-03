"""Narration with a FREE offline voice (Kokoro, Apache-2.0): no API key, no per-video cost.
Storyteller pacing: slower on short dramatic sentences, longer pauses after them.
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


def speak(text, voice="bm_george", dry=False):
    """returns (audio float32 @24 kHz, marks) where marks = [(start_s, duration_s)] per sentence."""
    sents = split_sents(text)
    if not sents:
        raise SystemExit(f"Narration has no full sentence (end each with . ? or !): {text!r}")
    parts, t, marks = [], 0.0, []
    for snt in sents:
        words = len(snt.split())
        gap = 0.85 if words <= 3 else 0.42
        if dry:
            a = np.zeros(int(words / 2.4 * SR), dtype="float32")
        else:
            speed = 0.72 if words <= 3 else (0.80 if words <= 6 else 0.88)
            if "?" in snt:
                speed = min(speed, 0.84)
            a, _ = _kokoro().create(snt, voice=voice, speed=speed, lang="en-gb" if voice.startswith("b") else "en-us")
        marks.append((round(t, 3), round(len(a) / SR, 3)))
        parts += [a, np.zeros(int(gap * SR), dtype=a.dtype)]
        t += len(a) / SR + gap
    return np.concatenate(parts[:-1]), marks
