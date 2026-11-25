"""The "why" video writer: ONE short video that opens on a "Why ...?" question and reveals the answer step by step.

One model call writes the whole storyboard (a few repair rounds only if a check fails), so it fits the free LLM quotas.
The same checks as every other story apply (cast, scene format, every named thing drawn, drawing smoke test, real-voice length rails),
plus the why rules: the title and the first sentence are the question, titles/description/tags are written for search, one uncommon word.
The star of the video is the subject itself (a cat, a dog, a cow, a chicken, the sun, the moon) or, for human questions, one person drawn for the topic.
"""
import json
import os
import re
import sys
from pathlib import Path

from . import storywriter as W
from . import vector_creatures as VC

ROOT = W.ROOT
REPAIRS = int(os.environ.get("WHY_REPAIRS", "3"))

SYSTEM = """You write "Why ...?" videos for the entertainment channel "tidalfolio". Each video is ONE short animated video: it opens on a why question and the answer is revealed little by little, scene by scene, until the last line lands. The narrator is one warm, funny, middle-aged storyteller. You write a STORYBOARD (JSON); the system draws it.

THE FORMAT
- It is entertainment, not a lecture: facts are welcome where they help but are never required, and nobody checks evidence. The goal is to BOND with the viewer: make them smile, nod ("that is so my cat"), feel seen and want to share it with someone. Speak to the viewer as "you" where it feels natural; the last line should land warmly or with a wink.
- Scene 1's narration starts with the question itself ("Why do cats sleep so much?"), then teases that the answer is coming. Every next scene reveals one more piece of the answer, each more surprising or funnier than the last. The final scene gives the satisfying answer.
- LENGTH IS THE TOPIC'S OWN. Do not pad and do not rush: a simple answer may take 5 scenes (about 25 seconds), a richer one 8 or 9 (up to about 60 seconds). The storyteller speaks slowly (about 0.55 s per word), so scenes are 8 to 16 words each. Use as many scenes as the answer needs and stop the moment it is told.
- The TITLE is for search: 30 to 70 characters, starting with the exact phrase people type ("Why Do Cats Sleep So Much?") followed by a short hook in brackets, e.g. "(The Real Reason)". The youtube description must START with that same search phrase, then 2 or 3 plain sentences, then a question for comments. At least 8 tags, all real search phrases, the main phrase first. TikTok caption under 140 characters.
- TOPIC: if no topic is given, choose a why question that many people really search for, about something you can show as the star (see THE STAR). Never repeat a topic already made.
- NARRATION: ordinary easy words, short to medium sentences, numbers written as words (no digits, symbols or abbreviations), no personal names. The narrator never says "I", "we", "my" or "our". He tells it from outside, never gives orders or a moral lecture. Exactly ONE uncommon English word (a real word, with a one-line meaning) appears exactly once in the narration, used naturally.
- Do not write a sign-off, "follow", "subscribe" or "part two": the system adds the end screen.

THE STAR (this is all the system can draw)
- The video's star is the SUBJECT ITSELF drawn as a character, alone or with up to 3 others. Cast entries for creatures: {"kind": "cat|dog|cow|chicken|sun|moon", "color": optional (orange|ginger|grey|black|white|cream|brown|yellow|pink|red|blue|green|gold|tan), "stripes": optional true (cat), "patch": optional true (cow/dog)}. Pick topics whose star is one of those six creatures, or people (humans, early people, a baby, a grandmother, a sleepy worker): a person is {"role": "...", "gender": "male|female", "age": "child|adult|elder", "skin": "light|fair|tan|brown|dark", "hair": "black|brown|blonde|red|grey|white", "extras": ["glasses","beard","mustache","bun","bald"]} (a built-in role such as %s, or any role you invent with a "design"; people are never given names). The sun and moon are cast as creatures (kind "sun" or "moon") and have a face.
- Each scene: "world" (dawn|day|dusk|storm|night|sunset; words like night, dark, midnight need "night"; the moon needs "sky": true; a bright tone like joyful cannot be night), "stage" (street|park|kitchen|shop|office|classroom|home), "camera" (hold|push_in|pull_back|pan_right|pan_left), "tone" (playful|joyful|tense|sad|eerie|tender|calm: use at least two different tones, at most two calm scenes, never calm in scene 1; tense/sad/eerie belong to dusk, joyful to day/dawn/sunset), optional "silence_before" (a few words copied from the narration, at most two scenes).
- "actors": 1 to 3 on screen, each {"who": cast key, "at": ground_left|ground_mid|ground_right (a different spot each), "mood": neutral|sleepy|happy|angry|scared|shocked|smug|sad|dizzy, "action": stand|talk|hop|flap|point|shrug|cheer|facepalm|think|laugh|tremble|offer|hold|clasp|wrap|place|reach|beckon|hugself|wipe|cower|wave}. A creature with mood "sleepy" is drawn asleep. Match mood and action to what the narration says at that moment. The second half needs one quiet small gesture (clasp, hold, place, hugself, wrap, wipe, offer) and tender scenes use no big gestures.
- Scene 1 opens on a strong moment: an actor with a non-neutral mood and a popup. Use "popups" (comic bubble or burst words, 1 to 4 words, {"text": "ZZZ", "kind": "bubble|burst", "at": "words copied exactly from that scene's narration", "near": cast key}) in most scenes.
- EVERYTHING THE NARRATOR NAMES MUST BE DRAWN in that scene. Never name an object, animal or place you will not show: the only things you can show are the cast, the built-in props (%s) and things you design in the top-level "props". If it cannot be drawn, cut it from the narration. Keep it simple: mostly the star on screen, with the narration about the star.
- Every timing phrase ("at", "from", "to", "silence_before") must be copied EXACTLY from that scene's narration (2 to 5 words).

Reply with ONE JSON object:
{"title": "...", "uncommon_word": {"word": "...", "meaning": "..."},
 "cast": {"cat": {"kind": "cat", "color": "orange"}},
 "parts": [{"thumbnail_scene": 1, "thumbnail_hook": "1 to 3 words in capitals, a tease", "scenes": [{"narration": "...", "world": "day", "stage": "home", "camera": "push_in", "tone": "playful", "actors": [{"who": "cat", "at": "ground_mid", "mood": "smug", "action": "talk"}], "popups": [{"text": "WHY?", "kind": "burst", "at": "Why do cats", "near": "cat"}]}]}],
 "youtube": {"description": "...", "tags": ["..."], "pinned_comment": "a question for the comments"},
 "tiktok": {"caption": "...", "hashtags": ["#a", "#b", "#c", "#d", "#e"]}}"""


def system_prompt():
    from . import people as PE
    from . import builtin_props as BP
    return SYSTEM % (", ".join(PE.ROLES_LIST), ", ".join(getattr(BP, "NAMES", None) or sorted(getattr(BP, "PROPS", {}) or [])[:30]))


def why_problems(sb, G, number):
    """(problems, compiled scripts). Used by the AI writer and by tools/add_story.py."""
    parts = sb.get("parts") or []
    if len(parts) != 1:
        return [f"a why video has exactly ONE part (this one has {len(parts)})."], None
    bad = []
    title = str(sb.get("title", "")).strip()
    yt = sb.get("youtube") or {}
    uw = sb.get("uncommon_word") or {}
    if not title.lower().startswith("why"):
        bad.append("the title must start with 'Why' (the exact search phrase).")
    if not 30 <= len(title) <= 70:
        bad.append(f"SEO: the title is {len(title)} characters; make it 30 to 70: the exact search phrase first, then a hook in brackets, e.g. 'Why Do Cats Sleep So Much? (The Real Reason)'.")
    if len(yt.get("tags") or []) < 8 or not str(yt.get("description", "")).lower().startswith(title.split("?")[0].lower()[:25]):
        bad.append("SEO: the description must start with the search phrase from the title, and there must be at least 8 tags that are real search phrases (the title phrase first).")
    if not (uw.get("word") and uw.get("meaning")):
        bad.append("'uncommon_word' needs a word and a meaning.")
        return bad, None
    if str(uw["word"]).lower() in {w.lower() for w in G.used_words()}:
        bad.append(f"the uncommon word {uw['word']!r} was already used; choose another.")
    word = str(uw["word"]).strip()
    bad += W._part_problems(parts[0], sb.get("cast") or {}, 1, word, 1, 1)
    if bad:
        return bad, None
    pb, scripts = W.problems({k: v for k, v in sb.items() if k != "outline"}, number)
    return pb, scripts


def write_why(idea=None, log=print):
    sys.path.insert(0, str(ROOT))
    import generate_script as G
    W.SCRIPTS.mkdir(exist_ok=True)
    number = G.next_number()
    titles, _ = G.existing()
    log(f"Writing a why video with {G.llm_provider()['name']} ({G.llm_provider()['model']}).")
    user = ((f"Topic to use: {idea}. " if idea else "Choose the topic yourself (a why question many people search for). ")
            + (f"Topics already made (choose something different): {'; '.join(titles[-40:])}. " if titles else "")
            + "Write the video now.")
    msgs = [{"role": "system", "content": system_prompt()}, {"role": "user", "content": user}]
    last = []
    for attempt in range(1 + REPAIRS):
        raw = G.call_openai(msgs, 0.9 if attempt == 0 else 0.5)
        try:
            sb = W.normalize(json.loads(raw))
        except (ValueError, TypeError) as e:
            last = [f"the reply was not valid JSON ({e})."]
            msgs += [{"role": "assistant", "content": str(raw)[:6000]}, {"role": "user", "content": "Reply again with ONE valid JSON object. " + last[0]}]
            continue
        bad, scripts = why_problems(sb, G, number)
        if not bad:
            names = W._save_story({k: v for k, v in sb.items() if k != "outline"}, scripts, "Funny People", number, 1)
            log("Queued: " + ", ".join(names))
            return names
        last = bad
        log(f"Why video attempt {attempt + 1} needs fixes: " + " | ".join(b[:160] for b in bad[:4]))
        msgs += [{"role": "assistant", "content": json.dumps(sb)[:7000]},
                 {"role": "user", "content": "Fix ALL of these problems and reply with the complete corrected JSON object:\n- " + "\n- ".join(bad)}]
    raise SystemExit("The why video could not be made valid: " + "; ".join(last)[:600])
