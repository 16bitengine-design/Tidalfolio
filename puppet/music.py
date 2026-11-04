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


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def synth(scenes, starts, durs, total, nt, out_wav, seed=7, outro=4.5):
    """scenes: list of scene dicts (with "_i"); starts/durs: seconds; nt(i, phrase) -> scene-relative time."""
    rng = np.random.default_rng(seed)
    N = int(total * SR)
    t = np.arange(N) / SR

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
    for ci, s0 in enumerate(np.arange(0, total, 3.6)):
        add(pad_mix, pad([hz(m) for m in PROG[ci % 4]], 5.2), s0)

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
        pts_pl += [(a0 + 0.8, 1.0 if pl else 0.0)] + ([] if last else [(a1 - 0.6, 1.0 if pl else 0.0)])
        if pl:
            k, tm = 0, a0 + 0.3
            while tm < a1 - 0.5:
                add(pl_mix, pluck(hz(PENT[pl["notes"][k % len(pl["notes"])]]), 2.0, pl.get("vol", 0.5)), tm)
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
            add(pl_mix, pluck(hz(57), 3.0, 0.7), silence[1])
    # outro: the story's music settles onto a held home chord, a soft rising figure, then a long fade to nothing
    c0 = total - outro
    pts_pad += [(c0, 0.5), (c0 + 1.2, 0.62), (total - 1.4, 0.4), (total, 0.0)]
    pts_pl += [(c0 - 0.4, 1.0), (c0 + 0.6, 0.0), (c0 + 0.7, 1.0), (total - 1.6, 0.5), (total, 0.0)]
    add(pad_mix, pad([hz(m) for m in PROG[0]], outro + 0.4), c0)
    for j, m in enumerate((69, 72, 76, 81)):
        add(pl_mix, pluck(hz(m), 3.2, 0.55), c0 + 0.7 + 0.28 * j)

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
