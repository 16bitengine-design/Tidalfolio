"""Storyboard -> puppet script.

A *storyboard* is the small, forgiving description an AI story writer (or a person) produces:
who is in each scene, where they stand, how they feel, what they do and when (tied to words in the narration).
`compile_storyboard()` turns it into the full channel-based puppet script that puppet/dsl.py draws, so the writer never
has to deal with coordinates, keyframes or drawing details. `check_storyboard()` lists every problem in plain words
(used to send feedback to the writer and to refuse bad scripts before anything is rendered).

Storyboard JSON:
{ "title": "...", "lesson": "...", "cause": "forgot|believed|no_options",
  "uncommon_word": {"word": "indolent", "meaning": "lazy"},
  "cast": {"orrin": {"species": "eagle", "look": "orrin|dad|mom", "name": "Orrin"},
           "pip":   {"species": "squirrel", "hat": "bowler", "item": "popcorn"},
           "moss":  {"species": "rabbit"}},
  "scenes": [ {
     "narration": "...", "world": "dawn|day|dusk|storm|night|sunset", "stage": "cliff|nest|tree",
     "camera": "hold|push_in|pull_back|pan_right|pan_left", "music": "calm|tense|sad|joyful", "silence_before": "words",
     "actors": [ {"who": "orrin", "at": "ground_mid", "face": "left|right", "mood": "...", "action": "stand|talk|hop|flap",
                  "from": "words", "to": "words", "enter": "words", "exit": "words", "carry": "fish"} ],
     "popups": [ {"text": "CRASH", "kind": "burst|bubble", "at": "words", "near": "orrin"} ],
     "fx": [ {"kind": "puff|sparkle|speed", "at": "words", "near": "orrin"} ] } ],
  "youtube": {...}, "tiktok": {...} }
"""
import re

SPECIES = ("eagle", "squirrel", "rabbit")
LOOKS = ("orrin", "dad", "mom")
WORLDS = ("dawn", "day", "dusk", "storm", "night", "sunset")
STAGES = ("cliff", "nest", "tree")
CAMERAS = ("hold", "push_in", "pull_back", "pan_right", "pan_left")
MUSICS = ("calm", "tense", "sad", "joyful")
MOODS = ("neutral", "sleepy", "happy", "angry", "scared", "sad", "shocked", "smug", "dizzy")
ACTIONS = ("stand", "talk", "hop", "flap")
SLOTS = {   # name: (world x, world y or None = standing on the cliff)
    "ground_left": (110, None), "ground_mid": (300, None), "ground_right": (500, None),
    "branch_a": (575, 884), "branch_b": (465, 864),
    "air_left": (180, 700), "air_mid": (430, 640), "air_right": (760, 620),
}
GROUND = ("ground_left", "ground_mid", "ground_right")
BRANCH = ("branch_a", "branch_b")
CAM_BASE = {"cliff": (470, 1000), "nest": (470, 1000), "tree": (400, 960)}
FIRST_PERSON = re.compile(r"(?<![\w'])(I|I'm|I'd|I'll|I've|me|my|mine|we|we're|our|us)(?![\w'])")
MAX_WORDS_BUBBLE = 4

# eagle face per mood: eye, brow, tear
EAGLE_MOOD = {
    "neutral": ("open", [0, 0], 0.0), "sleepy": ("closed", [8, 6], 0.0), "happy": ("open", [-6, -4], 0.0),
    "angry": ("open", [-8, 10], 0.0), "scared": ("wide", [-4, -4], 0.0), "sad": ("open", [10, -6], 0.55),
    "shocked": ("wide", [-8, -8], 0.0), "smug": ("half", [4, 6], 0.0), "dizzy": ("spiral", [0, 0], 0.0),
}
MUSIC = {
    "calm": {"pad": 0.45, "pluck": {"step": 1.6, "notes": [0, 3, 2, 4], "vol": 0.5}},
    "tense": {"pad": 0.7, "pluck": {"step": 0.9, "notes": [0, 1, 0, 2], "vol": 0.6}},
    "sad": {"pad": 0.5},
    "joyful": {"pad": 0.8, "pluck": {"step": 0.8, "notes": [0, 2, 3, 4, 5, 6, 5, 4], "vol": 0.9}},
}


def _w(text):
    return len(re.findall(r"[A-Za-z0-9']+", text or ""))


def _slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", (s or "story").lower())).strip("-")[:48] or "story"


def phrase_ok(narration, phrase):
    return isinstance(phrase, str) and phrase.strip() != "" and phrase in narration


def _check_scenes(scenes, cast, pre=""):
    bad = []
    if not isinstance(scenes, list) or not 4 <= len(scenes) <= 10:
        return [f"{pre}'scenes' must be a list of 4 to 10 scenes."]
    for n, sc in enumerate(scenes, 1):
        where = f"{pre}scene {n}"
        nar = sc.get("narration", "")
        if not isinstance(nar, str) or _w(nar) < 8:
            bad.append(f"{where}: narration is missing or too short.")
            continue
        if not re.search(r"[.!?]\"?$", nar.strip()):
            bad.append(f"{where}: narration must end with . ! or ?")
        unquoted = re.sub(r'"[^"]*"', "", nar)
        m = FIRST_PERSON.search(unquoted)
        if m:
            bad.append(f"{where}: the narrator must never mention himself ('{m.group(0)}'). Tell it in the third person; only quoted speech may use I/me/we.")
        if sc.get("world") not in WORLDS:
            bad.append(f"{where}: world must be one of {WORLDS}.")
        if sc.get("stage", "cliff") not in STAGES:
            bad.append(f"{where}: stage must be one of {STAGES}.")
        if sc.get("camera", "hold") not in CAMERAS:
            bad.append(f"{where}: camera must be one of {CAMERAS}.")
        if sc.get("music", "calm") not in MUSICS:
            bad.append(f"{where}: music must be one of {MUSICS}.")
        if sc.get("silence_before") and not phrase_ok(nar, sc["silence_before"]):
            bad.append(f"{where}: silence_before words {sc['silence_before']!r} are not in the narration (copy them exactly).")
        actors = sc.get("actors") or []
        if not actors:
            bad.append(f"{where}: needs at least one actor.")
        stage = sc.get("stage", "cliff")
        for a in actors:
            who = a.get("who")
            if who not in cast:
                bad.append(f"{where}: actor {who!r} is not in the cast.")
                continue
            sp = cast[who].get("species")
            at = a.get("at", "ground_mid")
            if at not in SLOTS:
                bad.append(f"{where}: {who} 'at' must be one of {sorted(SLOTS)}.")
            elif at in BRANCH and (stage != "tree" or sp != "squirrel"):
                bad.append(f"{where}: branch spots are for squirrels and need stage 'tree'.")
            elif at.startswith("air") and sp != "eagle":
                bad.append(f"{where}: only eagles can be in the air ({who} is a {sp}).")
            if a.get("mood", "neutral") not in MOODS:
                bad.append(f"{where}: mood must be one of {MOODS}.")
            if a.get("action", "stand") not in ACTIONS:
                bad.append(f"{where}: action must be one of {ACTIONS}.")
            for key in ("from", "to", "enter", "exit"):
                if a.get(key) and not phrase_ok(nar, a[key]):
                    bad.append(f"{where}: {who} '{key}' words {a[key]!r} are not in the narration (copy them exactly).")
            if a.get("carry") and (a["carry"] != "fish" or sp != "eagle"):
                bad.append(f"{where}: only eagles can carry, and only a 'fish'.")
        for p in sc.get("popups") or []:
            if not phrase_ok(nar, p.get("at")):
                bad.append(f"{where}: popup {p.get('text')!r} 'at' words are not in the narration (copy them exactly).")
            if p.get("kind", "bubble") not in ("bubble", "burst"):
                bad.append(f"{where}: popup kind must be bubble or burst.")
            if _w(p.get("text", "")) > MAX_WORDS_BUBBLE or not p.get("text"):
                bad.append(f"{where}: popup text must be 1 to {MAX_WORDS_BUBBLE} words.")
            if p.get("near") and p["near"] not in [a.get("who") for a in actors]:
                bad.append(f"{where}: popup 'near' must be an actor in the scene.")
        for fx in sc.get("fx") or []:
            if fx.get("kind") not in ("puff", "sparkle", "speed") or not phrase_ok(nar, fx.get("at")):
                bad.append(f"{where}: fx needs kind puff|sparkle|speed and 'at' words copied from the narration.")
    return bad


# ------------------------------------------------------------------------------------- checks
def check_storyboard(sb):
    """Return a list of plain-language problems (empty = fine). A story is 2 to 4 PARTS, each a 50-90 s video."""
    bad = []
    if not isinstance(sb, dict):
        return ["The storyboard is not a JSON object."]
    cast = sb.get("cast")
    if not isinstance(cast, dict) or not 1 <= len(cast) <= 4:
        bad.append("'cast' must be an object with 1 to 4 characters.")
        cast = {}
    for k, c in cast.items():
        if not isinstance(c, dict) or c.get("species") not in SPECIES:
            bad.append(f"cast '{k}': species must be one of {SPECIES}.")
        elif c["species"] == "eagle" and c.get("look", "orrin") not in LOOKS:
            bad.append(f"cast '{k}': an eagle's look must be one of {LOOKS}.")
    parts = sb.get("parts")
    if not isinstance(parts, list) or not 2 <= len(parts) <= 4:
        bad.append("'parts' must be a list of 2 to 4 parts (one story told as Part 1, Part 2 ...), each with its own 'scenes'.")
        return bad
    scenes = []
    for pi, part in enumerate(parts, 1):
        ps = part.get("scenes") if isinstance(part, dict) else None
        bad += _check_scenes(ps, cast, f"part {pi}, ")
        scenes += ps if isinstance(ps, list) else []
    uw = (sb.get("uncommon_word") or {}).get("word", "")
    alltext = " ".join(s.get("narration", "") for s in scenes)
    if not uw:
        bad.append("'uncommon_word' ({word, meaning}) is missing.")
    elif len(re.findall(rf"\b{re.escape(uw)}\b", alltext, re.I)) != 1:
        bad.append(f"the uncommon word {uw!r} must appear exactly once in the narration.")
    if not (sb.get("lesson") or "").strip():
        bad.append("'lesson' (one plain sentence) is missing.")
    if sb.get("cause") not in ("forgot", "believed", "no_options"):
        bad.append("'cause' must be forgot, believed or no_options.")
    if not isinstance(sb.get("youtube"), dict) or not sb["youtube"].get("description"):
        bad.append("'youtube' needs description, tags and pinned_comment.")
    if not isinstance(sb.get("tiktok"), dict) or not sb["tiktok"].get("caption"):
        bad.append("'tiktok' needs caption and hashtags.")
    return bad


# ------------------------------------------------------------------------------------- compile
def _screen(wx, wy, cam):
    cx, cy = cam
    return (wx - cx + 540, wy - cy + 960)


def _slot_xy(at, species, scale):
    x, y = SLOTS[at]
    if y is None:
        y = {"eagle": 1240 - 240 * scale, "squirrel": 1240 - 84 * scale, "rabbit": 1236 - 40 * scale}[species]
    return float(x), float(y)


def _off(x, left_of=None):
    """off-screen x on the nearer side"""
    return -420.0 if x < 470 else 1500.0


def _scale(species, at, crowd):
    if species == "eagle":
        return 0.6 if at.startswith("air") else (0.72 if crowd > 1 else 0.9)
    return 0.8 if species == "squirrel" else 0.85


def _actor_things(a, cast, scene, crowd, centre_x, nar_end):
    who, c = a["who"], cast[a["who"]]
    sp = c["species"]
    at = a.get("at", "ground_mid")
    s = _scale(sp, at, crowd)
    x, y = _slot_xy(at, sp, s)
    face = {"left": -1, "right": 1}.get(a.get("face"), 1 if x <= centre_x else -1)
    mood = a.get("mood", "neutral")
    action = a.get("action", "stand")
    things = []
    t_in = f"@{a['enter']}-0.3" if a.get("enter") else None
    t_out = f"@{a['exit']}" if a.get("exit") else None
    t_from = f"@{a['from']}" if a.get("from") else 0.6
    t_to = f"@{a['to']}" if a.get("to") else "@end-1.0"
    show = [t_in if t_in else -0.1, (f"@{a['exit']}+1.5") if t_out else None]
    th = {"type": sp, "id": who, "scale": s, "face": face, "show": show}
    in_air = at.startswith("air")
    if sp == "eagle":
        th["who"] = c.get("look", "orrin")
        eye, brow, tear = EAGLE_MOOD[mood]
        th.update(eye=eye, brow=brow)
        if tear:
            th["tear"] = {"kf": [[0, 0], [2.0, tear]]}
        if action == "talk":
            th["beak"] = {"sin": {"base": 0.5, "amp": 0.5, "rate": 10, "from": t_from, "to": t_to}}
        if mood in ("angry", "shocked", "scared") and action != "talk":
            th["bob"] = {"sin": {"amp": 3, "rate": 18}}
        else:
            th.setdefault("bob", {"sin": {"amp": 2, "rate": 1.8}})
        fly = {"rate": 15, "amp": 0.7, "rest": 0.25}
        calm = {"rate": 0, "amp": 0, "rest": -0.3}
        base_flap = {"rate": 12, "amp": 0.6, "rest": 0.1} if action == "flap" else (fly if in_air else calm)
        xs = _off(x)
        xk, yk = [], []
        flap_steps, leg_steps = [[0, base_flap]], [[0, not in_air]]
        if t_in:
            land_t = f"@{a['enter']}+1.4"
            xk, yk = [[t_in, xs], [land_t, x]], [[t_in, 520.0], [land_t, y]]
            flap_steps = [[0, fly], [land_t, base_flap]]
            leg_steps = [[0, False], [land_t, not in_air]]
        if t_out:
            end_t = f"{t_out}+1.5"
            if not xk:
                xk, yk = [[0, x]], [[0, y]]
            xk += [[t_out, x], [end_t, xs]]
            yk += [[t_out, y], [end_t, 480.0]]
            flap_steps.append([t_out, fly])
            leg_steps.append([t_out, False])
        if xk:
            th["x"], th["y"] = {"kf": xk}, {"kf": yk}
            if in_air and not t_out:
                th["y"]["sin"] = {"amp": 12, "rate": 7}
        elif in_air:
            th["x"], th["y"] = x, {"base": y, "sin": {"amp": 14, "rate": 3.0}}
        else:
            th["x"], th["y"] = x, y
        th["flap"] = {"step": flap_steps} if len(flap_steps) > 1 else flap_steps[0][1]
        th["legs"] = {"step": leg_steps} if len(leg_steps) > 1 else leg_steps[0][1]
        if in_air or t_in or t_out:
            th["tailsway"] = {"sin": {"amp": 0.2, "rate": 6}}
        things.append(th)
        if a.get("carry") == "fish":
            things.append({"type": "fish", "attach": {"to": who, "dx": face * 112, "dy": -70}, "scale": 0.7, "face": face, "ang": 0.4,
                           "show": show})
        return things
    # squirrel / rabbit
    if sp == "squirrel":
        if c.get("hat") in ("bowler",):
            th["hat"] = c["hat"]
        if c.get("item") in ("popcorn",):
            th["item"] = c["item"]
        if action == "talk":
            th["talk"] = {"sin": {"base": 0.5, "amp": 0.5, "rate": 10, "from": t_from, "to": t_to}}
        rate, amp = {"scared": (30, 5), "angry": (22, 4), "happy": (5, 6), "shocked": (26, 5)}.get(mood, (2.5, 2))
        th["bounce"] = {"sin": {"amp": amp, "rate": rate, "phase": (hash(who) % 7) * 0.5}}
        th["look"] = [0.6 * face, 0]
    if action == "hop":
        hop = {"amp": -60, "rate": 9}
        th["y"] = {"base": y, "sin": {**hop, "fn": "sin"}}
    else:
        th["y"] = y
    if t_in:
        xs = _off(x)
        th["x"] = {"kf": [[t_in, xs], [f"@{a['enter']}+1.4", x]]}
        th["y"] = {"base": y, "sin": {"amp": -40, "rate": 10, "to": f"@{a['enter']}+1.4"}}
    else:
        th["x"] = x
    if t_out:
        xs = _off(x)
        th["x"] = {"kf": ([[t_in, _off(x)], [f"@{a['enter']}+1.4", x]] if t_in else []) + [[t_out, x], [f"{t_out}+1.4", xs]]}
        th["y"] = {"base": y, "sin": {"amp": -40, "rate": 10, "from": t_out}}
    things.append(th)
    return things


def _camera(mode, stage):
    bx, by = CAM_BASE[stage]
    if mode == "push_in":
        return {"x": bx, "y": by, "z": {"kf": [[0, 1.0], ["@end", 1.24]]}}
    if mode == "pull_back":
        return {"x": bx, "y": by, "z": {"kf": [[0, 1.2], ["@end", 0.98]]}}
    if mode == "pan_right":
        return {"x": {"lin": [[0, bx - 70], ["@end", bx + 70]]}, "y": by, "z": 1.0}
    if mode == "pan_left":
        return {"x": {"lin": [[0, bx + 70], ["@end", bx - 70]]}, "y": by, "z": 1.0}
    return {"x": bx, "y": by, "z": 1.0}


def _stage_things(stage):
    out = []
    if stage == "nest":
        out.append({"type": "nest"})
    if stage == "tree":
        out += [{"type": "tree", "x": 640, "base": 1285, "top": 560},
                {"type": "poly", "pts": [[610, 930], [340, 880], [336, 910], [610, 990]], "fill": [104, 74, 50], "w": 4, "seed": 70},
                {"type": "line", "pts": [[430, 930], [400, 1000]], "w": 4, "seed": 71},
                {"type": "line", "pts": [[530, 950], [560, 1000]], "w": 4, "seed": 72}]
    return out


def _compile_scenes(scene_list, cast):
    scenes = []
    n_scenes = len(scene_list)
    for si, sc in enumerate(scene_list):
        stage = sc.get("stage", "cliff")
        cam_base = CAM_BASE[stage]
        actors = sc.get("actors") or []
        slots = [SLOTS[a.get("at", "ground_mid")][0] for a in actors]
        centre_x = sum(slots) / len(slots) if slots else 330
        crowd = sum(1 for a in actors if a.get("at", "ground_mid") in GROUND and cast[a["who"]]["species"] == "eagle")
        things = _stage_things(stage)
        pos = {}
        for a in sorted(actors, key=lambda q: 0 if cast[q["who"]]["species"] == "squirrel" else 1):   # squirrels behind eagles
            for th in _actor_things(a, cast, sc, crowd, centre_x, None):
                things.append(th)
            at = a.get("at", "ground_mid")
            sp = cast[a["who"]]["species"]
            s = _scale(sp, at, crowd)
            pos[a["who"]] = (_slot_xy(at, sp, s), s, sp)
        pops = []
        for p in sc.get("popups") or []:
            who = p.get("near") or (actors[0]["who"] if actors else None)
            (wx, wy), s, sp = pos.get(who, ((330, 1000), 1.0, "eagle"))
            above = {"eagle": 300, "squirrel": 190, "rabbit": 150}[sp] * s
            sx, sy = _screen(wx, wy - above, cam_base)
            sx = max(230, min(850, sx + (60 if p.get("kind") == "burst" else 0)))
            sy = max(330, min(1300, sy))
            kind = p.get("kind", "bubble")
            pop = {"text": p["text"], "at": f"@{p['at']}", "dur": 2.2, "x": round(sx), "y": round(sy),
                   "size": 52 if kind == "bubble" else 64, "shape": kind}
            if kind == "burst":
                pop["shake"] = 6
            pops.append(pop)
        for fx in sc.get("fx") or []:
            who = fx.get("near") or (actors[0]["who"] if actors else None)
            (wx, wy), s, sp = pos.get(who, ((330, 1000), 1.0, "eagle"))
            t = f"@{fx['at']}"
            things.append({"type": fx["kind"], "x": wx - (60 if fx["kind"] == "puff" else 0), "y": wy + (40 if fx["kind"] == "puff" else -120),
                           "scale": 1.1, "show": [t, f"@{fx['at']}+1.3"], "dx": -1, "n": 6})
        music = dict(MUSIC[sc.get("music", "calm")])
        if sc.get("silence_before"):
            music["silence_before"] = sc["silence_before"]
        scene = {"narration": sc["narration"].strip(), "world": "toon_" + sc["world"], "camera": _camera(sc.get("camera", "hold"), stage),
                 "things": things, "popups": pops, "music": music}
        if sc.get("silence_before"):
            scene["freeze"] = f"@{sc['silence_before']}-0.3"
        if si == n_scenes - 1:
            scene["end_card"] = True
        scenes.append(scene)

    return scenes


def compile_storyboard(sb, number=None):
    """Return a LIST of puppet scripts, one per part (Part 1 .. Part n). Call check_storyboard() first."""
    cast = sb["cast"]
    title = sb.get("title", "Untitled").strip()
    word = sb.get("uncommon_word") or {}
    n = len(sb["parts"])
    out = []
    for pi, part in enumerate(sb["parts"], 1):
        scenes = _compile_scenes(part["scenes"], cast)
        yt = dict(sb.get("youtube") or {})
        yt["title"] = f"{title} (Part {pi}/{n})"
        yt["description"] = (yt.get("description", "") + f"\n\nPart {pi} of {n}." + (f" Part {pi + 1} is next." if pi < n else " The end.")).strip()
        tt = dict(sb.get("tiktok") or {})
        tt["caption"] = f"Part {pi}/{n}: " + tt.get("caption", "")
        slug = f"{number:03d}-{_slug(title)}-part-{pi}" if number else f"{_slug(title)}-part-{pi}"
        out.append({
            "engine": "puppet", "look": "toon", "slug": slug, "title": f"{title} (Part {pi}/{n})", "short_title": title,
            "series_part": {"story": title, "part": pi, "of": n},
            "thumbnail_scene": max(1, min(len(scenes), int(part.get("thumbnail_scene", 2)))),
            "voice": {"kokoro": "bm_george"},
            "story": {"lesson": sb["lesson"].strip(), "cause": sb["cause"]},
            "uncommon_word": {"word": word.get("word", ""), "meaning": word.get("meaning", "")} if pi == 1 else {},
            "scenes": scenes, "youtube": yt, "tiktok": tt})
    return out
