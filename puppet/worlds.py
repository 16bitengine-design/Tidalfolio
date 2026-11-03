"""Painted world presets (sky, hills, sea, cliff). A script can add or override presets in its "worlds" block."""
from .engine import bake_world

PRESETS = {
    "dawn": dict(sky_top=(238, 156, 132), sky_bot=(255, 224, 170), far=(150, 142, 176), mid=(98, 118, 108), tree=(58, 86, 76),
                 sea=(104, 146, 172), rock=(104, 80, 68), grass=(116, 150, 84), cloud=(255, 226, 206), mist=(255, 224, 196),
                 glow=(760, 900), glow_col=(255, 214, 150), disc=((255, 232, 170), 105, False)),
    "day": dict(sky_top=(112, 176, 232), sky_bot=(226, 242, 248), far=(132, 160, 196), mid=(92, 130, 104), tree=(52, 96, 74),
                sea=(80, 140, 186), rock=(110, 88, 74), grass=(112, 160, 84), cloud=(255, 255, 255), mist=(236, 246, 252),
                glow=(820, 300), glow_col=(255, 244, 200), disc=((255, 244, 190), 100, False)),
    "dusk": dict(sky_top=(132, 140, 184), sky_bot=(238, 202, 188), far=(128, 128, 160), mid=(84, 100, 100), tree=(48, 70, 70),
                 sea=(110, 124, 156), rock=(96, 76, 70), grass=(98, 132, 82), cloud=(246, 214, 204), mist=(238, 206, 200),
                 glow=(820, 1040), glow_col=(255, 196, 150), disc=((255, 214, 160), 95, False)),
    "storm": dict(sky_top=(78, 86, 108), sky_bot=(176, 178, 190), far=(104, 112, 134), mid=(70, 88, 90), tree=(40, 62, 62),
                  sea=(74, 96, 118), rock=(86, 70, 66), grass=(86, 116, 78), cloud=(150, 154, 170), mist=(170, 176, 190), clouds=11,
                  glow=(800, 600), glow_col=(180, 184, 200)),
    "night": dict(sky_top=(12, 18, 46), sky_bot=(60, 72, 112), far=(40, 50, 84), mid=(30, 42, 66), tree=(20, 34, 52),
                  sea=(34, 52, 86), rock=(52, 46, 62), grass=(40, 70, 70), cloud=(70, 80, 120), mist=(70, 84, 124), stars=True,
                  glow=(820, 480), glow_col=(150, 170, 230), disc=((232, 236, 250), 85, True)),
    "sunset": dict(sky_top=(78, 50, 114), sky_bot=(255, 164, 92), far=(138, 98, 140), mid=(88, 74, 100), tree=(54, 44, 70),
                   sea=(150, 100, 126), rock=(98, 76, 76), grass=(112, 126, 76), cloud=(255, 186, 160), mist=(255, 176, 130),
                   glow=(700, 1010), glow_col=(255, 190, 110), disc=((255, 216, 130), 125, False)),
}

def _toon(**k):
    k.setdefault("toon", True)
    return k


PRESETS.update({
    "toon_day": _toon(sky_top=(56, 150, 240), sky_bot=(176, 226, 252), far=(170, 120, 210), mid=(104, 196, 98), tree=(158, 66, 190),
                      sea=(36, 160, 235), rock=(222, 126, 176), grass=(130, 206, 60), cloud=(255, 255, 255), mist=(210, 236, 252),
                      glow=(820, 300), glow_col=(255, 244, 170), disc=((255, 214, 58), 105, False), disc_style="rays", castle=(1040, 1000)),
    "toon_dawn": _toon(sky_top=(250, 120, 150), sky_bot=(255, 214, 120), far=(190, 110, 200), mid=(120, 190, 110), tree=(170, 70, 170),
                       sea=(60, 150, 220), rock=(236, 130, 150), grass=(150, 205, 70), cloud=(255, 236, 226), mist=(255, 210, 170),
                       glow=(760, 900), glow_col=(255, 214, 120), disc=((255, 220, 70), 105, False), disc_style="rays", castle=(1040, 1000)),
    "toon_dusk": _toon(sky_top=(96, 90, 210), sky_bot=(255, 170, 150), far=(150, 100, 200), mid=(90, 170, 120), tree=(130, 60, 170),
                       sea=(70, 120, 220), rock=(210, 110, 160), grass=(120, 190, 80), cloud=(255, 200, 200), mist=(255, 190, 190),
                       glow=(820, 1040), glow_col=(255, 180, 130), disc=((255, 200, 90), 95, False), disc_style="rays", castle=(1040, 1000)),
    "toon_storm": _toon(sky_top=(70, 70, 140), sky_bot=(170, 160, 210), far=(100, 90, 160), mid=(70, 140, 110), tree=(100, 50, 140),
                        sea=(50, 100, 170), rock=(170, 100, 150), grass=(90, 160, 80), cloud=(190, 190, 225), mist=(170, 170, 210), clouds=11,
                        glow=(800, 600), glow_col=(190, 190, 230), castle=(1040, 1000)),
    "toon_night": _toon(sky_top=(24, 20, 100), sky_bot=(100, 90, 190), far=(70, 60, 150), mid=(40, 100, 120), tree=(90, 40, 140),
                        sea=(40, 80, 170), rock=(150, 90, 160), grass=(70, 150, 100), cloud=(150, 140, 220), mist=(120, 120, 210), stars=True,
                        glow=(820, 480), glow_col=(170, 180, 255), disc=((255, 226, 90), 95, False), disc_style="craters", castle=(1040, 1000)),
    "toon_sunset": _toon(sky_top=(140, 60, 190), sky_bot=(255, 150, 70), far=(190, 90, 170), mid=(110, 160, 100), tree=(150, 50, 150),
                         sea=(220, 100, 130), rock=(220, 110, 140), grass=(160, 190, 70), cloud=(255, 180, 160), mist=(255, 170, 120),
                         glow=(700, 1010), glow_col=(255, 190, 90), disc=((255, 210, 70), 125, False), disc_style="rays", castle=(1040, 1000)),
})

_COLOR_KEYS = ("sky_top", "sky_bot", "far", "mid", "tree", "sea", "rock", "grass", "cloud", "mist", "glow_col")


def _norm(pal):
    """JSON gives lists; the engine wants tuples."""
    out = dict(pal)
    for k in _COLOR_KEYS:
        if k in out:
            out[k] = tuple(out[k])
    if out.get("castle"):
        out["castle"] = tuple(out["castle"])
    if "glow" in out:
        out["glow"] = tuple(out["glow"])
    if out.get("disc"):
        c, r, cres = out["disc"]
        out["disc"] = (tuple(c), r, bool(cres))
    return out


def bake_for(script):
    """Bake every world the script uses (done once, before frames are rendered in parallel)."""
    defs = {k: _norm(v) for k, v in PRESETS.items()}
    for k, v in (script.get("worlds") or {}).items():
        base = dict(defs.get(v.get("extends", ""), {}))
        base.update({a: b for a, b in v.items() if a != "extends"})
        defs[k] = _norm(base)
    used = sorted({sc["world"] for sc in script["scenes"]})
    missing = [w for w in used if w not in defs]
    if missing:
        raise SystemExit(f"Unknown world(s) {missing}. Built in: {sorted(PRESETS)}; or define them under \"worlds\" in the script.")
    return {w: bake_world(defs[w], seed=11 + len(w)) for w in used}
