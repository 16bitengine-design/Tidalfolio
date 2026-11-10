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
           "tom":   {"species": "cat", "coat": "ginger|grey|black|white", "hat": "bowler"},
           "rusty": {"species": "fox"},
           "moss":  {"species": "rabbit", "coat": "grey|white|brown"}},
  "scenes": [ {
     "narration": "...", "world": "dawn|day|dusk|storm|night|sunset", "stage": "cliff|nest|tree",
     "camera": "hold|push_in|pull_back|pan_right|pan_left", "tone": "playful|tense|sad|joyful|eerie|tender|calm", "silence_before": "words",
     "actors": [ {"who": "orrin", "at": "ground_mid", "face": "left|right", "mood": "...", "action": "stand|talk|point|offer|hold|clasp|wrap|place|reach|beckon|hugself|wipe|cower|wave|hips|shrug|think|facepalm|cheer|laugh|tremble",
                  "from": "words", "to": "words", "enter": "words", "exit": "words", "carry": "fish",
                  "beats": [{"at": "words", "mood": "...", "action": "...", "look": "at|away|down|up"}], "speaks": true} ],
     "popups": [ {"text": "CRASH", "kind": "burst|bubble", "at": "words", "near": "orrin"} ],
     "fx": [ {"kind": "puff|sparkle|speed", "at": "words", "near": "orrin"} ] } ],
  "youtube": {...}, "tiktok": {...} }
"""
import re
import zlib

from . import people as PE
from . import towns as TW

SPECIES = ("human", "eagle", "squirrel", "rabbit", "cat", "fox")     # new stories use people only; the animals stay for stories already made
LOOKS = ("orrin", "dad", "mom")
WORLDS = ("dawn", "day", "dusk", "storm", "night", "sunset")
ANIMAL_STAGES = ("cliff", "nest", "tree")
HUMAN_STAGES = TW.STAGES                      # street, park, kitchen, shop, office, classroom, home
STAGES = ANIMAL_STAGES + HUMAN_STAGES
HSLOTS = {"ground_left": 130.0, "ground_mid": 300.0, "ground_right": 470.0}
ZOOM_H = 1.5                                  # people are drawn bigger than animals: the camera starts closer
EXTRAS = ("glasses", "beard", "mustache", "bun", "bald")
ITEMS = ("none", "book", "clipboard", "paper", "tray", "wrench", "rolling_pin", "pan", "hammer", "umbrella", "cake", "baguette", "cup", "phone", "camera", "letter", "bag", "fish", "flask", "brush", "cane")
CAMERAS = ("hold", "push_in", "pull_back", "pan_right", "pan_left")
MUSICS = ("calm", "tense", "sad", "joyful")          # old key, still accepted
TONES = ("playful", "tense", "sad", "joyful", "eerie", "tender", "calm")
TONE_ALIAS = {"funny": "playful", "silly": "playful", "comic": "playful", "comedic": "playful", "mischievous": "playful", "cheeky": "playful",
              "scary": "eerie", "creepy": "eerie", "spooky": "eerie", "mysterious": "eerie", "suspenseful": "eerie", "ominous": "eerie",
              "angry": "tense", "heated": "tense", "urgent": "tense", "dramatic": "tense", "anxious": "tense", "nervous": "tense", "panic": "tense",
              "bittersweet": "sad", "gloomy": "sad", "melancholy": "sad", "sorrowful": "sad", "lonely": "sad", "wistful": "sad",
              "warm": "tender", "loving": "tender", "gentle": "tender", "heartwarming": "tender", "sweet": "tender", "hopeful": "tender",
              "happy": "joyful", "triumphant": "joyful", "cheerful": "joyful", "celebratory": "joyful", "excited": "joyful",
              "neutral": "calm", "peaceful": "calm", "quiet": "calm", "relaxed": "calm"}


def norm_tone(v):
    v = str(v or "").strip().lower()
    return v if v in TONES else TONE_ALIAS.get(v, "")


def tone_of(sc):
    """a scene's tone: its own "tone", else derived from the old "music" key"""
    return norm_tone(sc.get("tone")) or {"calm": "calm", "tense": "tense", "sad": "sad", "joyful": "joyful"}.get(sc.get("music", "calm"), "calm")
MOODS = ("neutral", "sleepy", "happy", "angry", "scared", "sad", "shocked", "smug", "dizzy")
ACTIONS = ("stand", "talk", "hop", "flap", "point", "shrug", "cheer", "facepalm", "think", "laugh", "tremble",
           "offer", "hold", "clasp", "wrap", "place", "reach", "beckon", "hugself", "wipe", "cower", "wave", "hips")
# pick the action that matches what the narration says this person is DOING at that moment:
#   offer = holds something out · hold = clutches something to the chest · clasp = hands together (worry, tenderness)
#   wrap = arms round someone · place = sets something down · reach = reaches for something · beckon = calls someone over
#   hugself = arms folded over the chest (cold, wet, shy) · wipe = hand to the eye · cower = shrinks back · wave = greets
#   point = points at something/someone · hips = hands on hips (cross, bossy) · facepalm = dismay · think = hand to chin
# Anyone who is speaking gestures while they talk; listeners turn to the speaker and nod, so give them a calm action.
SLOTS = {   # name: (world x, world y or None = standing on the cliff)
    "ground_left": (110, None), "ground_mid": (300, None), "ground_right": (500, None),
    "branch_a": (575, 884), "branch_b": (465, 864),
    "air_left": (180, 700), "air_mid": (430, 640), "air_right": (760, 620),
}
GROUND = ("ground_left", "ground_mid", "ground_right")
BRANCH = ("branch_a", "branch_b")
CAM_BASE = {"cliff": (470, 1000), "nest": (470, 1000), "tree": (400, 960), **{st: (300, 1100) for st in TW.STAGES}}
FIRST_PERSON = re.compile(r"(?<![\w'])(I|I'm|I'd|I'll|I've|me|my|we|we're|our|us)(?![\w'])")   # no 'mine': it is also a noun (a gold mine)


def strip_quoted(text):
    """Remove quoted speech (straight or curly quotes, balanced or left open) so only the narrator's own words remain."""
    t = (text or "").replace("“", '"').replace("”", '"')
    t = re.sub(r'"[^"]*"', " ", t)                       # balanced "..." pairs
    t = re.sub(r'"[^"]*$', " ", t)                       # a quote opened and never closed: the rest is speech
    t = re.sub(r"(?<![\w])‘[^’]*’", " ", t)   # curly single-quoted speech
    t = re.sub(r"(?<![\w'])'[^'\n]*'(?![\w])", " ", t)   # straight single-quoted speech: 'Show me,' he said. (an apostrophe inside a word never opens one)
    return t


def sentence_around(text, match):
    """The whole sentence containing a regex match, trimmed for an error message."""
    start = max(text.rfind(c, 0, match.start()) for c in ".!?") + 1
    ends = [i for i in (text.find(c, match.end()) for c in ".!?") if i != -1]
    end = (min(ends) + 1) if ends else len(text)
    return text[start:end].strip()[:160]


MAX_WORDS_BUBBLE = 4
# words that do not belong on an all-ages channel (checked in narration and pop-ups)
UNSAFE = re.compile(r"\b(fuck\w*|shit\w*|damn\w*|hell|bastard|bitch\w*|crap|ass|asshole|piss\w*|dick|sex\w*|naked|drunk|beer|wine|vodka|whisky|"
                    r"kill\w*|murder\w*|dead|die[sd]?|dying|blood\w*|gun\w*|shoot\w*|shot|knife|stab\w*|suicide|corpse|slaughter\w*)\b", re.I)
DEFINING = re.compile(r"fancy word|which means|that means|\bmeaning\b|in other words|another word for|a word for|the word\b|is a word", re.I)

# eagle face per mood: eye, brow, tear
CRITTER_EYE_MOOD = {"neutral": "open", "sleepy": "closed", "happy": "happy", "angry": "open", "scared": "wide", "sad": "open", "shocked": "wide", "smug": "half", "dizzy": "spiral"}
LOOKS = {"at": [0.6, 0.0], "away": [-0.5, 0.25], "down": [0.1, 0.85], "up": [0.3, -0.7]}   # where a person's eyes go
EAGLE_MOOD = {
    "neutral": ("open", [0, 0], 0.0), "sleepy": ("closed", [8, 6], 0.0), "happy": ("open", [-6, -4], 0.0),
    "angry": ("open", [-8, 10], 0.0), "scared": ("wide", [-4, -4], 0.0), "sad": ("open", [10, -6], 0.55),
    "shocked": ("wide", [-8, -8], 0.0), "smug": ("half", [4, 6], 0.0), "dizzy": ("spiral", [0, 0], 0.0),
}
MUSIC = {   # per tone: chords (midi), pluck scale + pattern, pad level; each tone sounds different at a glance
    "calm": {"pad": 0.45, "pluck": {"step": 1.6, "notes": [0, 3, 2, 4], "vol": 0.5}},
    "playful": {"pad": 0.55, "prog": [[48, 55, 60, 64], [53, 57, 60, 65], [55, 59, 62, 67], [48, 55, 60, 64]],
                "pluck": {"step": 0.45, "notes": [0, 2, 1, 3, 2, 4, 3, 1], "vol": 0.85, "scale": [72, 74, 76, 79, 81, 84, 86], "len": 0.9}},
    "joyful": {"pad": 0.85, "prog": [[48, 55, 60, 64], [45, 52, 57, 60], [53, 57, 60, 65], [55, 59, 62, 67]],
               "pluck": {"step": 0.5, "notes": [0, 2, 3, 4, 5, 6, 5, 4], "vol": 1.0, "scale": [72, 74, 76, 79, 81, 84, 88], "len": 1.2}},
    "tense": {"pad": 0.75, "prog": [[38, 45, 50, 53], [38, 45, 50, 52], [37, 44, 49, 52], [38, 45, 50, 53]], "drone": {"peak": 0.34},
              "pluck": {"step": 0.42, "notes": [0, 0, 1, 0, 0, 1, 0, 2], "vol": 0.8, "scale": [45, 46, 48, 51, 52], "len": 0.7}},
    "sad": {"pad": 0.6, "prog": [[45, 52, 57, 60], [41, 48, 53, 57], [43, 50, 55, 58], [45, 52, 57, 60]],
            "pluck": {"step": 2.3, "notes": [4, 3, 2, 1, 0, 0], "vol": 0.55, "scale": [57, 60, 62, 64, 67, 69], "len": 3.0}},
    "eerie": {"pad": 0.6, "prog": [[40, 46, 52, 58], [41, 47, 53, 59], [40, 46, 52, 58], [39, 46, 51, 58]], "drone": {"peak": 0.3},
              "pluck": {"step": 2.0, "notes": [0, 5, 2, 6, 1], "vol": 0.55, "scale": [76, 77, 82, 83, 88, 89, 94], "len": 2.6}},
    "tender": {"pad": 0.55, "prog": [[48, 55, 60, 64], [45, 52, 57, 64], [53, 57, 60, 65], [48, 55, 60, 67]],
               "pluck": {"step": 1.9, "notes": [0, 2, 4, 3, 1, 2], "vol": 0.6, "scale": [67, 69, 72, 74, 76, 79, 81], "len": 3.0}},
}
# the camera when the writer gives none: tension leans in, sadness drifts away
TONE_CAMERA = {"tense": "push_in", "sad": "pull_back", "eerie": "push_in", "joyful": "pan_right"}


def fix_cast(cast):
    """Fill in a person's defaults (species "human", gender, age, skin, hair) and fix near-miss values, in place."""
    if not isinstance(cast, dict):
        return cast
    for i, (key, c) in enumerate(cast.items()):
        if not isinstance(c, dict) or not (c.get("role") or c.get("species") == "human"):
            continue
        role = PE.norm_role(c.get("role") or key)
        if role:
            c["role"] = role
        c["species"] = "human"
        if role:
            g = str(c.get("gender", "")).lower()
            c["gender"] = {"man": "male", "m": "male", "boy": "male", "woman": "female", "f": "female", "girl": "female"}.get(g, g)
            c["gender"] = PE.default_gender(role, c["gender"])
            a = str(c.get("age", "")).lower()
            c["age"] = {"kid": "child", "young": "adult", "old": "elder", "senior": "elder", "elderly": "elder", "teen": "adult"}.get(a, a)
            if c["age"] not in ("child", "adult", "elder"):
                c["age"] = PE.default_age(role)
            skin, hair = PE.default_look(role, i)
            c["skin"] = c.get("skin") if c.get("skin") in PE.SKIN else skin
            c["hair"] = c.get("hair") if c.get("hair") in PE.HAIR else hair
            ex = c.get("extras")
            c["extras"] = [e for e in (ex if isinstance(ex, list) else []) if e in EXTRAS]
            if c["gender"] == "female":
                c["extras"] = [e for e in c["extras"] if e not in ("beard", "mustache")]
    return cast


_NOT_NAMES = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "January", "February", "March", "April", "June", "July", "August",
              "September", "October", "November", "December", "Christmas", "Halloween", "Thanksgiving", "Easter", "God", "Mister", "Missus"}


def personal_names(text):
    """Capitalised words in mid-sentence that look like a person's name (nobody is named on this channel)."""
    found = []
    for m in re.finditer(r"\b[A-Z][a-z]{2,}\b", text):
        before = text[:m.start()].rstrip()
        if not before or before[-1] in '.!?"\u201c\u2018\':' or m.group(0) in _NOT_NAMES:   # a word right after an opening quote starts the speech, it is not a name
            continue
        if before.endswith(("Mr", "Mrs", "Ms", "Dr")):
            found.append(m.group(0))
            continue
        found.append(m.group(0))
    return found


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
    prev_sig = None
    for n, sc in enumerate(scenes, 1):
        where = f"{pre}scene {n}"
        sig = (sc.get("world"), sc.get("stage"), sc.get("camera"),
               tuple((a.get("who"), a.get("at"), a.get("mood"), a.get("action")) for a in sc.get("actors") or []))
        if sig == prev_sig:
            bad.append(f"{where}: repeats the previous scene's staging. Every scene must change something the viewer can see: positions, mood, action, camera or place.")
        prev_sig = sig
        if n == 1 and pre.startswith("part 1") and not (sc.get("popups") or any(a.get("mood", "neutral") != "neutral" for a in sc.get("actors") or [])):
            bad.append(f"{where}: the opening needs a visual hook: give an actor a strong mood (not neutral) or add a popup.")
        nar = sc.get("narration", "")
        if not isinstance(nar, str) or _w(nar) < 8:
            bad.append(f"{where}: narration is missing or too short.")
            continue
        if not re.search(r"[.!?][\"”]?$", nar.strip()):
            bad.append(f"{where}: narration must end with . ! or ?")
        unquoted = strip_quoted(nar)
        m = FIRST_PERSON.search(unquoted)
        if m:
            bad.append(f"{where}: the narrator must never mention himself ('{m.group(0)}') in this sentence: \"{sentence_around(unquoted, m)}\". "
                       "Rewrite that sentence in the third person (he, she, the driver); only words inside double quotation marks may use I/me/we.")
        popup_text = " ".join(p.get("text", "") for p in sc.get("popups") or [])
        mu = UNSAFE.search(nar + " " + popup_text)
        if mu:
            bad.append(f"{where}: '{mu.group(0)}' is not all-ages. This channel is for everyone from young children to grandparents: rephrase gently (no profanity, death, weapons, blood, drink or romance).")
        m2 = DEFINING.search(unquoted)
        if m2:
            bad.append(f"{where}: the narrator must never explain or define a word ('{m2.group(0)}'). Remove it and carry on with the story.")
        if sc.get("world") not in WORLDS:
            bad.append(f"{where}: world must be one of {WORLDS}.")
        if sc.get("stage", "cliff") not in STAGES:
            bad.append(f"{where}: stage must be one of {STAGES}.")
        if sc.get("camera", "hold") not in CAMERAS:
            bad.append(f"{where}: camera must be one of {CAMERAS}.")
        if sc.get("tone") and not norm_tone(sc["tone"]):
            bad.append(f"{where}: tone must be one of {TONES}.")
        if sc.get("music", "calm") not in MUSICS:
            bad.append(f"{where}: music must be one of {MUSICS}.")
        if sc.get("silence_before") and not phrase_ok(nar, sc["silence_before"]):
            bad.append(f"{where}: silence_before words {sc['silence_before']!r} are not in the narration (copy them exactly).")
        actors = sc.get("actors") or []
        if not actors:
            bad.append(f"{where}: needs at least one actor.")
        stage = sc.get("stage", "cliff")
        humans = [a for a in actors if isinstance(a, dict) and cast.get(a.get("who"), {}).get("species") == "human"]
        if humans and stage not in HUMAN_STAGES:
            bad.append(f"{where}: people live in these settings: {HUMAN_STAGES} (stage {stage!r} is not one of them).")
        if len({a.get("at", "ground_mid") for a in humans}) < len(humans):
            bad.append(f"{where}: two people cannot stand in the same spot: give each a different 'at' (ground_left|ground_mid|ground_right).")
        if humans:
            for nm in personal_names(nar):
                bad.append(f"{where}: '{nm}' looks like a personal name. Nobody has a name on this channel: refer to people by role, gender or profession ('the baker', 'the old woman', 'her boss').")
                break
        for a in actors:
            who = a.get("who")
            if who not in cast:
                bad.append(f"{where}: actor {who!r} is not in the cast.")
                continue
            sp = cast[who].get("species")
            at = a.get("at", "ground_mid")
            if sp == "human":
                if at not in HSLOTS:
                    bad.append(f"{where}: {who} 'at' must be one of {sorted(HSLOTS)}.")
            elif at not in SLOTS:
                bad.append(f"{where}: {who} 'at' must be one of {sorted(SLOTS)}.")
            elif sp == "human":
                pass
            elif at in BRANCH and (stage != "tree" or sp != "squirrel"):
                bad.append(f"{where}: branch spots are for squirrels and need stage 'tree'.")
            elif at.startswith("air") and sp != "eagle":
                bad.append(f"{where}: only eagles can be in the air ({who} is a {sp}).")
            if a.get("mood", "neutral") not in MOODS:
                bad.append(f"{where}: mood must be one of {MOODS}.")
            if a.get("action", "stand") not in ACTIONS:
                bad.append(f"{where}: action must be one of {ACTIONS}.")
            for b in a.get("beats") or []:
                if not phrase_ok(nar, b.get("at")):
                    bad.append(f"{where}: {who} beat 'at' words {b.get('at')!r} are not in the narration (copy them exactly).")
                if b.get("mood", "neutral") not in MOODS or b.get("action", "stand") not in ACTIONS or b.get("look", "at") not in LOOKS:
                    bad.append(f"{where}: {who} beat needs mood in {MOODS}, action in {ACTIONS}, look in {tuple(LOOKS)}.")
            if a.get("go") is not None and a["go"] not in HSLOTS:
                bad.append(f"{where}: 'go' must be one of {tuple(HSLOTS)} (the spot this person walks to).")
            for key in ("from", "to", "enter", "exit"):
                if a.get(key) and not phrase_ok(nar, a[key]):
                    bad.append(f"{where}: {who} '{key}' words {a[key]!r} are not in the narration (copy them exactly).")
            if a.get("carry") and sp == "human":
                if a["carry"] not in ITEMS:
                    bad.append(f"{where}: 'carry' must be one of {ITEMS}.")
            elif a.get("carry") and (a["carry"] != "fish" or sp != "eagle"):
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
    """Return a list of plain-language problems (empty = fine). A story is 2 to 4 PARTS, each a 45-90 s video."""
    bad = []
    if not isinstance(sb, dict):
        return ["The storyboard is not a JSON object."]
    cast = sb.get("cast")
    if not isinstance(cast, dict) or not 1 <= len(cast) <= 4:
        bad.append("'cast' must be an object with 1 to 4 characters.")
        cast = {}
    fix_cast(cast)
    for k, c in cast.items():
        if isinstance(c, dict) and c.get("species") == "human":
            if not PE.norm_role(c.get("role")):
                bad.append(f"cast '{k}': role must be one of {PE.ROLES_LIST}.")
        elif not isinstance(c, dict) or c.get("species") not in SPECIES:
            bad.append(f"cast '{k}': needs a role (one of {PE.ROLES_LIST}).")
        elif c["species"] == "eagle" and c.get("look", "orrin") not in LOOKS:
            bad.append(f"cast '{k}': an eagle's look must be one of {LOOKS}.")
    parts = sb.get("parts")
    if not isinstance(parts, list) or not 2 <= len(parts) <= 4:
        found = ("missing" if parts is None else f"a list of {len(parts)}" if isinstance(parts, list) else type(parts).__name__)
        bad.append("'parts' must be a list of 2 to 4 parts (one story told as Part 1, Part 2 ...), each with its own 'scenes'. "
                   f"In your reply 'parts' was {found}; your top-level keys were: {', '.join(list(sb)[:10])}.")
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
def _screen(wx, wy, cam, z=1.0):
    cx, cy = cam
    return ((wx - cx) * z + 540, (wy - cy) * z + 960)


def _slot_xy(at, species, scale):
    if species == "human":
        return HSLOTS.get(at, 300.0), 1240.0
    x, y = SLOTS[at]
    if y is None:
        y = {"eagle": 1240 - 240 * scale, "squirrel": 1240 - 84 * scale, "rabbit": 1240 - 84 * scale, "cat": 1240 - 84 * scale, "fox": 1240 - 84 * scale}[species]
    return float(x), float(y)


def _off(x, human=False):
    """off-screen x on the nearer side"""
    if human:
        return -300.0 if x < 300 else 900.0
    return -420.0 if x < 470 else 1500.0


def _scale(species, at, crowd):
    if species == "human":
        return 1.0 if crowd <= 2 else 0.92
    if species == "eagle":
        return 0.6 if at.startswith("air") else (0.72 if crowd > 1 else 0.9)
    return {"squirrel": 0.8, "cat": 1.1, "fox": 1.06, "rabbit": 1.06}.get(species, 0.85)


def _uniq(nar, i, forward=True):
    """a few words of the narration starting at i that find() locates at i (so a timed @phrase means exactly that place)"""
    seg = nar[i:].lstrip() if forward else nar[i:]
    i = nar.index(seg[:1], i) if seg else i
    words = nar[i:].split(" ")
    for n in range(1, len(words) + 1):
        ph = " ".join(words[:n]).rstrip()
        if ph and nar.find(ph) == i:
            return ph
    return nar[i:].strip()


def _quote_windows(nar, a, scene):
    """times at which this actor is the one speaking: the words inside double quotes, shared out among the speaking actors in order"""
    spans = [(m.start() + 1, m.end() - 1) for m in re.finditer(r'"[^"]+"', nar)]
    if not spans:
        return None
    speakers = [x.get("who") for x in scene.get("actors", []) if x.get("action") == "talk" or x.get("speaks")]
    if a.get("who") not in speakers:
        return None
    mine = [sp for k, sp in enumerate(spans) if speakers[k % len(speakers)] == a["who"]]
    out = []
    for q0, q1 in mine:
        start = "@" + _uniq(nar, q0)
        rest = nar[q1 + 1:].strip()
        end = "@" + _uniq(nar, nar.index(rest, q1 + 1)) if rest else "@end-1.0"
        out.append([start, end])
    return out or None


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
    human = sp == "human"
    if human:
        _, brow, tear = EAGLE_MOOD[mood]
        th.update(type="human", role=c["role"], gender=c["gender"], age=c["age"], skin=c["skin"], hair=c["hair"], extras=c.get("extras", []),
                  eye=CRITTER_EYE_MOOD[mood], brow=brow, mood=mood, action=action, seed=zlib.crc32(who.encode()) % 50)
        if a.get("carry") in ITEMS:
            th["carry"] = a["carry"]
        if tear:
            th["tear"] = {"kf": [[0, 0], [2.0, tear]]}
        if action == "talk" or a.get("speaks"):                          # the mouth moves while this person speaks, whatever the hands are doing
            th["talk"] = {"sin": {"base": 0.5, "amp": 0.5, "rate": 10, "from": t_from, "to": t_to}}
            gate = _quote_windows(scene.get("narration", ""), a, scene)
            if gate:                                                      # only the quoted words are theirs: the narrator's "she said" is not
                th["talk"]["sin"] = {"base": 0.5, "amp": 0.5, "rate": 10, "gate": gate}
        rate, amp = {"scared": (30, 3), "angry": (22, 2.5), "happy": (5, 4), "shocked": (26, 3)}.get(mood, (2.5, 1.5))
        th["bounce"] = {"sin": {"amp": amp, "rate": rate, "phase": (zlib.crc32(who.encode()) % 7) * 0.5}}
        sd = th["seed"]
        th["t_offset"] = (sd % 17) * 0.37                                 # nobody blinks or breathes in step with anyone else
        # eyes: mostly on the other person, with a glance away or down now and then that is different for each person
        g0 = 1.8 + (sd % 5) * 0.7
        looks = [[0, LOOKS["at"]], [g0, LOOKS["away" if sd % 2 else "down"]], [g0 + 0.9 + (sd % 3) * 0.3, LOOKS["at"]]]
        beats = sorted(a.get("beats") or [], key=lambda b: 0)
        if beats:                                                         # changes of mood, gesture and glance on specific words
            ms, acs, es, brs, lk = [[0, mood]], [[0, action]], [[0, th["eye"]]], [[0, th["brow"]]], [[0, LOOKS["at"]]]
            for b in beats:
                tt = f"@{b['at']}"
                bm = b.get("mood", mood)
                ms.append([tt, bm]); acs.append([tt, b.get("action", "stand")]); es.append([tt, CRITTER_EYE_MOOD[bm]])
                brs.append([tt, EAGLE_MOOD[bm][1]]); lk.append([tt, LOOKS[b.get("look", "at")]])
            th["mood"], th["action"], th["eye"], th["brow"] = {"step": ms}, {"step": acs}, {"step": es}, {"step": brs}
            looks = lk
        th["look"] = {"step": looks}
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
    if human:
        pass
    elif sp == "squirrel":
        if c.get("hat") in ("bowler",):
            th["hat"] = c["hat"]
        if c.get("item") in ("popcorn",):
            th["item"] = c["item"]
        if action == "talk":
            th["talk"] = {"sin": {"base": 0.5, "amp": 0.5, "rate": 10, "from": t_from, "to": t_to}}
        rate, amp = {"scared": (30, 5), "angry": (22, 4), "happy": (5, 6), "shocked": (26, 5)}.get(mood, (2.5, 2))
        th["bounce"] = {"sin": {"amp": amp, "rate": rate, "phase": (hash(who) % 7) * 0.5}}
        th["look"] = [0.6 * face, 0]
    elif sp in ("cat", "fox", "rabbit"):
        if c.get("coat"):
            th["coat"] = c["coat"]
        if c.get("hat") in ("bowler",):
            th["hat"] = c["hat"]
        _, brow, tear = EAGLE_MOOD[mood]
        th.update(eye=CRITTER_EYE_MOOD[mood], brow=brow, mood=mood)
        if tear:
            th["tear"] = {"kf": [[0, 0], [2.0, tear]]}
        if action == "talk":
            th["talk"] = {"sin": {"base": 0.5, "amp": 0.5, "rate": 10, "from": t_from, "to": t_to}}
        rate, amp = {"scared": (30, 5), "angry": (22, 4), "happy": (5, 6), "shocked": (26, 5)}.get(mood, (2.5, 2))
        th["bounce"] = {"sin": {"amp": amp, "rate": rate, "phase": (hash(who) % 7) * 0.5}}
        th["look"] = [0.6 * face, 0]
    if action == "hop":
        hop = {"amp": -50 if human else -60, "rate": 9}
        th["y"] = {"base": y, "sin": {**hop, "fn": "sin"}}
    else:
        th["y"] = y
    walk = -3 if human else -40                     # people walk with their legs now (see people.py); only animals still bob
    if t_in:
        xs = _off(x, human)
        th["x"] = {"kf": [[t_in, xs], [f"@{a['enter']}+1.4", x]]}
        th["y"] = {"base": y, "sin": {"amp": walk, "rate": 10, "to": f"@{a['enter']}+1.4"}}
    else:
        th["x"] = x
    go = a.get("go") if human else None
    if go in HSLOTS and not t_in and not t_out:                # walk from "at" to "go" while the narrator speaks
        x2 = _slot_xy(go, sp, s)[0]
        th["x"] = {"kf": [[t_from, x], [t_to, x2]]}
        th["face"] = 1 if x2 >= x else -1
    elif t_out:
        xs = _off(x, human)
        th["x"] = {"kf": ([[t_in, _off(x, human)], [f"@{a['enter']}+1.4", x]] if t_in else []) + [[t_out, x], [f"{t_out}+1.4", xs]]}
        th["y"] = {"base": y, "sin": {"amp": walk, "rate": 10, "from": t_out}}
    things.append(th)
    return things


def _camera(mode, stage):
    bx, by = CAM_BASE[stage]
    z0 = ZOOM_H if stage in HUMAN_STAGES else 1.0
    if mode == "push_in":
        return {"x": bx, "y": by, "z": {"kf": [[0, z0], ["@end", z0 * 1.2]]}}
    if mode == "pull_back":
        return {"x": bx, "y": by, "z": {"kf": [[0, z0 * 1.16], ["@end", z0 * 0.96]]}}
    if mode == "pan_right":
        return {"x": {"lin": [[0, bx - 50], ["@end", bx + 50]]}, "y": by, "z": z0}
    if mode == "pan_left":
        return {"x": {"lin": [[0, bx + 50], ["@end", bx - 50]]}, "y": by, "z": z0}
    return {"x": bx, "y": by, "z": {"kf": [[0, z0], ["@end", z0 * 1.045]]}}      # even a "hold" leans in a little


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
        is_h = stage in HUMAN_STAGES
        cam_base = CAM_BASE[stage]
        actors = sc.get("actors") or []
        slots = [(HSLOTS if is_h else {k: v[0] for k, v in SLOTS.items()}).get(a.get("at", "ground_mid"), 300.0) for a in actors]
        centre_x = sum(slots) / len(slots) if slots else 330
        crowd = (len(actors) if is_h else sum(1 for a in actors if a.get("at", "ground_mid") in GROUND and cast[a["who"]]["species"] == "eagle"))
        things = _stage_things(stage)
        pos = {}
        for a in sorted(actors, key=lambda q: 0 if cast[q["who"]]["species"] != "eagle" else 1):   # everyone else stands behind the eagles
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
            above = {"eagle": 300, "squirrel": 190, "rabbit": 250, "cat": 220, "fox": 240, "human": 450}[sp] * s
            if sp == "human":
                above *= 0.72 if cast[who]["age"] == "child" else 1.0
                above += 70 * s if PE.ROLES.get(cast[who]["role"], {}).get("hat") == "chef" else 0
            if is_h:        # people are zoomed in: the pop-up is anchored in the world, just above the head
                sx = max(120.0, min(480.0, wx + (40 if p.get("kind") == "burst" else 0)))
                sy = max(570.0, wy - above - 30)
            else:
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
        tone = tone_of(sc)
        music = dict(MUSIC[tone])
        if music.get("drone"):
            music["drone"] = {"from": 0.5, **music["drone"]}
        if sc.get("silence_before"):
            music["silence_before"] = sc["silence_before"]
        scene = {"narration": sc["narration"].strip(), "world": "toon_" + sc["world"] + ("_" + stage if is_h else ""),
                 "camera": _camera(sc.get("camera") if sc.get("camera") not in (None, "hold") else TONE_CAMERA.get(tone, "hold"), stage),
                 "things": things, "popups": pops, "music": music, "tone": tone}
        if sc.get("silence_before"):
            scene["freeze"] = f"@{sc['silence_before']}-0.3"
        if si == n_scenes - 1:
            scene["end_card"] = True
        scenes.append(scene)

    return scenes


def compile_storyboard(sb, number=None):
    """Return a LIST of puppet scripts, one per part (Part 1 .. Part n). Call check_storyboard() first."""
    cast = fix_cast(sb["cast"])
    title = sb.get("title", "Untitled").strip()
    word = sb.get("uncommon_word") or {}
    n = len(sb["parts"])
    out = []
    for pi, part in enumerate(sb["parts"], 1):
        scenes = _compile_scenes(part["scenes"], cast)
        if pi < n:     # a part followed by another one ends plainly; only the last part gets the simple end screen
            scenes[-1].pop("end_card", None)
        yt = dict(sb.get("youtube") or {})
        yt["title"] = f"{title} (Part {pi}/{n})"
        yt["description"] = (yt.get("description", "") + f"\n\nPart {pi} of {n}." + (f" Part {pi + 1} is next." if pi < n else " The end.")).strip()
        tt = dict(sb.get("tiktok") or {})
        tt["caption"] = f"Part {pi}/{n}: " + tt.get("caption", "")
        slug = f"{number:03d}-{_slug(title)}-part-{pi}" if number else f"{_slug(title)}-part-{pi}"
        out.append({
            "engine": "puppet", "look": "vector", "cast_species": sorted({c["species"] for c in sb["cast"].values()}),
            "cast_roles": [c.get("role") for c in sb["cast"].values() if c.get("role")], "cast_lead": {k: sb["cast"][next(iter(sb["cast"]))].get(k) for k in ("role", "gender")}, "slug": slug, "title": f"{title} (Part {pi}/{n})", "short_title": title,
            "series_part": {"story": title, "part": pi, "of": n},
            "thumbnail_scene": max(1, min(len(scenes), int(part.get("thumbnail_scene", 2)))),
            "thumbnail_hook": str(part.get("thumbnail_hook") or "").strip().upper()[:22],
            "voice": {"kokoro": "tidal"},
            "story": {"lesson": sb["lesson"].strip(), "cause": sb["cause"]},
            "uncommon_word": {"word": word.get("word", ""), "meaning": word.get("meaning", "")} if pi == 1 else {},
            "scenes": scenes, "youtube": yt, "tiktok": tt})
    return out
