"""Procedural 'fusion' theme (ethereal pad chords + pentatonic plucks), fully synthesized: copyright-safe, no downloads.
Per scene (all optional) the script can say:
  "music": {"pad": 0.5, "pluck": {"step": 1.6, "notes": [0,3,2,4], "vol": 0.5},
            "swell": [from, to, factor], "drone": {"from": 0.5, "to": 11, "peak": 0.3}, "silence_before": "No mother"}
Times are scene-relative (numbers or "@words"). The volume follows each scene's pad level and is cut to nothing just before
`silence_before`; the final mix also ducks the music under the narrator (see render.py)."""
import wave

import numpy as np

from .dsl import Clock, _kf

SR = 22050
PENT = [69, 72, 74, 76, 79, 81, 84]       # A minor pentatonic
PROG = [[45, 52, 57, 60], [41, 48, 53, 57], [48, 55, 60, 64], [43, 50, 55, 59]]

# ---- the "nursery" theme: Brahms' Lullaby (Wiegenlied, Op. 49 No. 4, 1868: public domain) on a music box over a soft waltz.
# Synthesized from scratch like the fusion theme, so it is copyright-safe. A script picks it with "theme": "nursery".
NURSERY_BPM = 66
# (midi pitch, beats) in 3/4, D major. The pitches follow the published melody; the rhythm is a simple lullaby reading.
LULLABY = [(66, .5), (66, .5),                                   # pickup
           (69, 2), (66, .5), (66, .5),                          # 1
           (69, 1.5), (66, .5), (69, 1),                         # 2
           (74, 1), (73, 1), (71, 1),                            # 3
           (71, 1.5), (69, .5), (64, .5), (66, .5),              # 4
           (67, 1.5), (64, .5), (64, .5), (66, .5),              # 5
           (67, 1.5), (64, .5), (67, 1),                         # 6
           (73, 1), (71, .5), (69, .5), (73, 1),                 # 7
           (74, 3),                                              # 8
           (74, 1), (71, 1), (67, 1),                            # 9
           (69, 1), (66, 1), (62, 1),                            # 10
           (67, 1), (69, 1), (71, 1),                            # 11
           (69, 3),                                              # 12
           (74, 1), (71, 1), (67, 1),                            # 13
           (69, 1), (66, 1), (62, 1),                            # 14
           (67, 1), (66, 1), (64, 1),                            # 15
           (62, 3)]                                              # 16
NURSERY_CHORDS = {"D": ([50, 57, 62, 66], 38), "G": ([43, 55, 59, 62], 43), "A": ([45, 57, 61, 64], 45)}   # (pad notes, bass note)
NURSERY_BARS = "DDGDGGADGDGAGDAD"          # the chord under each of the 16 bars
NURSERY_HOME = [50, 57, 62, 66]


def lullaby_events(total, start=0.4):
    """(time, midi, seconds) for every melody note and (time, chord, seconds) for every bar, repeating the tune until `total`."""
    beat = 60.0 / NURSERY_BPM
    notes, bars = [], []
    while start < total - 1.5:
        tm = start
        for m, b in LULLABY:
            notes.append((tm, m, b * beat))
            tm += b * beat
        bars.append((start, "D", beat))
        bars += [(start + (1 + 3 * i) * beat, c, 3 * beat) for i, c in enumerate(NURSERY_BARS)]
        start += (1 + 3 * 16 + 3) * beat           # the tune, then three quiet beats before it comes round again
    return notes, bars


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def synth(scenes, starts, durs, total, nt, out_wav, seed=7, outro=4.5, theme="fusion"):
    """scenes: list of scene dicts (with "_i"); starts/durs: seconds; nt(i, phrase) -> scene-relative time.
    theme: "fusion" (ethereal pad + pentatonic plucks) or "nursery" (Brahms' Lullaby on a music box)."""
    nursery = theme == "nursery"
    rng = np.random.default_rng(seed)
    N = int(total * SR)
    t = np.arange(N) / SR

    def box(f, length):                                # a music-box note: bright, with a quick ring-out
        n = max(2, int(min(length + 1.2, 3.6) * SR))
        tt = np.arange(n) / SR
        rate = 2.4 if length < 1.2 else 1.6
        o = np.sin(2 * np.pi * f * tt) + 0.42 * np.sin(2 * np.pi * 2.0 * f * tt) + 0.2 * np.sin(2 * np.pi * 3.01 * f * tt) + 0.08 * np.sin(2 * np.pi * 4.98 * f * tt)
        return o * np.exp(-tt * rate) * np.minimum(1, tt / 0.004) * 0.8

    def soft(freqs, length):                           # a gentle waltz chord
        n = int((length + 0.6) * SR)
        tt = np.arange(n) / SR
        o = sum(np.sin(2 * np.pi * f * tt) + 0.2 * np.sin(4 * np.pi * f * tt) for f in freqs) / len(freqs)
        return o * np.minimum(1, tt / 0.25) * np.clip((length + 0.6 - tt) / 0.6, 0, 1) * 0.7

    def bass(f):
        tt = np.arange(int(1.6 * SR)) / SR
        return np.sin(2 * np.pi * f * tt) * np.exp(-tt * 1.4) * 0.8

    def pad(freqs, length):
        n = int(length * SR)
        tt = np.arange(n) / SR
        o = np.zeros(n)
        for f in freqs:
            for det in (-0.4, 0.0, 0.5):
                ff = f * 2 ** (det / 100)
                o += np.sin(2 * np.pi * ff * tt + rng.uniform(0, 6.28)) + 0.3 * np.sin(2 * np.pi * 2 * ff * tt)
        return o * np.minimum(1, tt / 1.4) * np.minimum(1, (length - tt) / 1.6) / (len(freqs) * 3)

    def pluck(f, length=2.0, vol=1.0):
        n = int(length * SR)
        p = max(2, int(SR / f))
        buf = rng.uniform(-1, 1, p)
        o = np.empty(n)
        pos = 0
        while pos < n:
            o[pos:pos + p] = buf[: min(p, n - pos)]
            buf = 0.5 * (buf + np.roll(buf, 1)) * 0.992
            pos += p
        return o * np.exp(-np.arange(n) / SR * 1.6) * vol

    def add(mix, sig, at):
        i = int(at * SR)
        if 0 <= i < N:
            j = min(N, i + len(sig))
            mix[i:j] += sig[: j - i]

    pad_mix, pl_mix = np.zeros(N), np.zeros(N)
    chord_i = 0
    if nursery:                                      # the lullaby: a music-box tune over a soft waltz (bass on beat one, a chord under the bar)
        tune, bars = lullaby_events(total)
        for tm, m, sec in tune:
            add(pl_mix, box(hz(m), sec), tm)
        for tm, c, sec in bars:
            notes, root = NURSERY_CHORDS[c]
            add(pad_mix, soft([hz(m) for m in notes], sec), tm)
            if sec > 1.5:
                add(pad_mix, bass(hz(root)), tm)
    else:
        for sc, a0, D in zip(scenes, starts, durs):  # each scene's pad plays that scene's own chords (its tone)
            prog = sc.get("music", {}).get("prog") or PROG
            for s0 in np.arange(a0, a0 + D, 3.6):
                add(pad_mix, pad([hz(m) for m in prog[chord_i % len(prog)]], 5.2), s0)
                chord_i += 1

    pts_pad, pts_pl = [(0.0, 0.0)], [(0.0, 0.6)]
    silence, drone_pts = None, []
    for sc, a0, D in zip(scenes, starts, durs):
        m = sc.get("music", {})
        clk = Clock(lambda ph, i=sc["_i"]: nt(i, ph), D)
        lv = m.get("pad", 0.5)
        pl = m.get("pluck")
        a1 = a0 + D
        last = a1 >= total - 0.01           # the closing scene keeps its level until the outro takes over
        pts_pad += [(a0 + 1.0, lv)] + ([] if last else [(a1 - 0.6, lv)])
        plv = (max(0.55, min(1.0, lv / 0.6)) if nursery else (1.0 if pl else 0.0))   # the lullaby follows each scene's emotion level
        pts_pl += [(a0 + 0.8, plv)] + ([] if last else [(a1 - 0.6, plv)])
        if pl and not nursery:
            k, tm = 0, a0 + 0.3
            while tm < a1 - 0.5:
                sc_notes = pl.get("scale") or PENT
                add(pl_mix, pluck(hz(sc_notes[pl["notes"][k % len(pl["notes"])] % len(sc_notes)]), pl.get("len", 2.0), pl.get("vol", 0.5)), tm)
                tm += pl["step"]
                k += 1
        if m.get("swell"):
            f0, f1, fac = clk.t(m["swell"][0]) + a0, clk.t(m["swell"][1]) + a0, m["swell"][2]
            pts_pad = [(x, y * (fac if f0 < x < f1 else 1.0)) for x, y in pts_pad]
        if m.get("drone"):
            dr = m["drone"]
            drone_pts += [(a0 + clk.t(dr.get("from", 0.5)), 0.0), (a0 + clk.t(dr.get("from", 0.5)) + 1.5, 0.18),
                          (a0 + clk.t(dr.get("to", D - 1)), dr.get("peak", 0.3)), (a0 + clk.t(dr.get("to", D - 1)) + 1.5, 0.0)]
        if m.get("silence_before"):
            tk = a0 + clk.t("@" + m["silence_before"])
            silence = (tk - 0.9, tk + 1.3)
            add(pl_mix, box(hz(62), 3.0) if nursery else pluck(hz(57), 3.0, 0.7), silence[1])
    # outro: the story's music settles onto a held home chord, a soft rising figure, then a long fade to nothing
    c0 = total - outro
    pts_pad += [(c0, 0.5), (c0 + 1.2, 0.62), (total - 1.4, 0.4), (total, 0.0)]
    pts_pl += [(c0 - 0.4, 1.0), (c0 + 0.6, 0.0), (c0 + 0.7, 1.0), (total - 1.6, 0.5), (total, 0.0)]
    add(pad_mix, pad([hz(m) for m in (NURSERY_HOME if nursery else PROG[0])], outro + 0.4), c0)
    for j, m in enumerate((74, 78, 81, 86) if nursery else (69, 72, 76, 81)):     # a soft rising figure onto the home chord
        add(pl_mix, box(hz(m), 3.2) * 0.7 if nursery else pluck(hz(m), 3.2, 0.55), c0 + 0.7 + 0.28 * j)

    xs = t[::200]

    def env(pts):
        pts = sorted(pts, key=lambda p: p[0])
        g = np.array([_kf(pts, x, True) for x in xs])
        if silence:
            a, b = silence
            g *= np.array([1 - _ease((min(x, b) - a) / 0.5) * (1 - _ease((x - b + 0.4) / 0.5)) if a <= x <= b + 0.4 else 1.0 for x in xs])
        return np.interp(t, xs, g)

    drone = np.zeros(N)
    if drone_pts:
        dg = np.interp(t, [0] + [p[0] for p in sorted(drone_pts)] + [total], [0] + [p[1] for p in sorted(drone_pts)] + [0])
        drone = np.sin(2 * np.pi * hz(33) * t) * dg * (1 + 0.3 * np.sin(2 * np.pi * 5 * t))

    dry = pad_mix * env(pts_pad) + pl_mix * env(pts_pl) * 0.9 + drone
    wet = dry.copy()
    for dly, g in [(0.23, 0.38), (0.41, 0.28), (0.67, 0.2)]:
        kk = int(dly * SR)
        wet[kk:] += g * dry[:-kk]
    wet = wet / max(1e-6, np.max(np.abs(wet))) * 0.85
    right = np.concatenate([np.zeros(int(0.012 * SR)), wet])[:N]
    st = (np.stack([wet, right], 1) * 32767).astype(np.int16)
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(st.tobytes())
