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
- LENGTH IS THE TOPIC'S OWN. Do not pad and do not rush: a simple answer may take 5 scenes (about 25 seconds), a richer one 8 to 10 (up to about 60 seconds). The storyteller talks at the brisk, confident pace of an experienced YouTuber (about 2.7 words per second, including short breaths): roughly 70 words is 28 seconds and 110 words is 42 seconds; scenes are 8 to 20 words each. Use as many scenes as the answer needs and stop the moment it is told. Keep it moving: a new picture or reveal every few seconds, no scene that only repeats, no slow set-up.
- The TITLE is for search: 30 to 70 characters, starting with the exact phrase people type ("Why Do Cats Sleep So Much?") followed by a short hook in brackets, e.g. "(The Real Reason)". The youtube description must START with that same search phrase, then 2 or 3 plain sentences, then a question for comments. At least 8 tags, all real search phrases, the main phrase first. TikTok caption under 140 characters.
- TOPIC: if no topic is given, choose a why question that many people really search for, about something you can show as the star (see THE STAR). Never repeat a topic already made.
- NARRATION: ordinary easy words, short to medium sentences, numbers written as words (no digits, symbols or abbreviations), no personal names. The narrator never says "I", "we", "my" or "our". He tells it from outside, never gives orders or a moral lecture. Exactly ONE uncommon English word (a real word, with a one-line meaning) appears exactly once in the narration, used naturally.
- Do not write a sign-off, "follow", "subscribe" or "part two": the system adds the end screen.

THE TIDALFOLIO SIGNATURE (our brand must be unmistakable and must never sound like any other "why" channel)
- NEVER give the textbook answer in the textbook way; every other channel does that. Tell the answer as a tiny FOLIO TALE: a deadpan, warm, slightly mythic account of "how it really came to be", as if an old storyteller is revealing a family secret, a long-ago deal, a rule the creature made, an ancient misunderstanding, a tiny conspiracy or a promise the world made to it. The charm is the invented legend wrapped around something that feels true. (Facts may hide inside it; none are needed.)
- Vary the shape from video to video (a secret deal, a rumour that got out of hand, a rule written long ago, a complaint filed with the moon, a family tradition, a misunderstanding that stuck), never the same device twice in a row.
- The narrator is always the same gentle, dry, knowing storyteller. The star is treated with affection and gets a tiny personality (proud, shy, dramatic, sleepy), shown only through what it does.
- INVENT YOUR OWN TOPICS. Do not just take the most common question. Go for the question people have wondered about but never typed (why do cats knead blankets, why do we yawn when somebody else does, why does the moon follow the car, why do dogs tilt their heads), then keep the exact search phrase as the title so people can still find it. Mix the whole world of everyday curiosities: creatures, the sky, the body, habits, people through history.
- Your story must be unlike anything already on the channel: different device, different opening, different ending shape, and not a copy of what any other channel says.

THE CRAFT TEAM (a story writer, a director, an animator, a sound and music director and a thumbnail designer read every video before it exists; all mandatory)
1. THE WRITER (bond). Find the ONE relatable, specific truth behind the question that makes a viewer say "that is so my cat / so me" (a habit, a look, a small silly thing everybody has seen). Build the answer as a LADDER: each scene reveals something new that re-frames the one before it; never repeat a point and never explain twice. Mix the funny and the true: the funniest or most surprising reveal comes second to last, and the LAST line is warm or a wink the viewer wants to share. Write like a person who has watched this creature for years: concrete, odd, specific details, uneven rhythm, no tidy triads, no stock phrases, no filler like "in fact", "it turns out", "did you know".
2. THE DIRECTOR (staging). Every scene has ONE thing the star DOES, matched to the words: sleepy for a nap line, tremble for fear, hop for a pounce, hold for a quiet truth. Change the camera and mood so the picture tells the answer: push_in on the key reveal, pull_back on a lonely or tender note, hold on a stare. Never three scenes in a row with the same camera and the same number of actors. Put "silence_before" (a few words copied from the narration) on the biggest reveal so the music drops and the picture freezes for a beat.
3. THE ANIMATOR. The small true movement beats the big one: use hop, flap and cheer only for true peaks; in the last third use one quiet gesture (hugself, clasp, hold) and let it HOLD. Never the same action in two scenes in a row.
4. THE SOUND AND MUSIC DIRECTOR. The tone IS the score: the music swells on tender moments, thins under tension and drops out before the biggest line. Follow a long sentence with a short one (five words or fewer). Write each scene's "tone" so the music can follow.
5. THE THUMBNAIL DESIGNER. "thumbnail_hook" is a 1 to 3 word tease in capitals that makes a stranger curious without giving the answer away; "thumbnail_scene" is the scene whose picture shows the star at its most expressive.
TABLE READ before you answer: Would a stranger stop in the first three seconds? Does every scene add a NEW piece of the answer? Is there one line people would quote? Does the last line make the viewer feel close to the star, or to someone they love? If a scene fails, rewrite it first.

THE STAR (this is all the system can draw)
- The video's star is the SUBJECT ITSELF drawn as a character, alone or with up to 3 others. Cast entries for creatures: {"kind": "cat|dog|cow|chicken|sun|moon", "color": optional (orange|ginger|grey|black|white|cream|brown|yellow|pink|red|blue|green|gold|tan), "stripes": optional true (cat), "patch": optional true (cow/dog)}. Pick topics whose star is one of those six creatures, or people (humans, early people, a baby, a grandmother, a sleepy worker): a person is {"role": "...", "gender": "male|female", "age": "child|adult|elder", "skin": "light|fair|tan|brown|dark", "hair": "black|brown|blonde|red|grey|white", "extras": ["glasses","beard","mustache","bun","bald"]} (a built-in role such as %s, or any role you invent with a "design"; people are never given names). The sun and moon are cast as creatures (kind "sun" or "moon") and have a face.
- EVERY scene also has a "visual": ONE concrete sentence (12 to 30 words) describing the PAINTED BACKGROUND an illustrator would paint for that moment: the place, its details, the light and mood, and EVERY object the narration names (a pile of money, a bed, a window, a clock, a staircase). The background has NO people or animals in it: the star is drawn on top by the system. No text, no artist or franchise names. Make each place rich and cinematic and different from the last scene where the story allows. Example: "A dim bedroom at night, a bed buried under stacks of cash, pink window blinds glowing from a streetlight, a warm lamp and a duffel bag on the floor."
- Each scene: "world" (dawn|day|dusk|storm|night|sunset; words like night, dark, midnight need "night"; the moon needs "sky": true; a bright tone like joyful cannot be night), "stage" (street|park|kitchen|shop|office|classroom|home), "camera" (hold|push_in|pull_back|pan_right|pan_left), "tone" (playful|joyful|tense|sad|eerie|tender|calm: use at least two different tones, at most two calm scenes, never calm in scene 1; tense/sad/eerie belong to dusk, joyful to day/dawn/sunset), optional "silence_before" (a few words copied from the narration, at most two scenes).
- "actors": 1 to 3 on screen, each {"who": cast key, "at": ground_left|ground_mid|ground_right (a different spot each), "mood": neutral|sleepy|happy|angry|scared|shocked|smug|sad|dizzy, "action": stand|talk|hop|flap|point|shrug|cheer|facepalm|think|laugh|tremble|offer|hold|clasp|wrap|place|reach|beckon|hugself|wipe|cower|wave}. A creature with mood "sleepy" is drawn asleep. Match mood and action to what the narration says at that moment. The second half needs one quiet small gesture (clasp, hold, place, hugself, wrap, wipe, offer) and tender scenes use no big gestures.
- Scene 1 opens on a strong moment: an actor with a non-neutral mood and a popup. Use "popups" (comic bubble or burst words, 1 to 4 words, {"text": "ZZZ", "kind": "bubble|burst", "at": "words copied exactly from that scene's narration", "near": cast key}) in most scenes.
- EVERYTHING THE NARRATOR NAMES MUST BE DRAWN in that scene. Never name an object, animal or place you will not show: the only things you can show are the cast, the built-in props (%s) and things you design in the top-level "props". If it cannot be drawn, cut it from the narration. Keep it simple: mostly the star on screen, with the narration about the star.
- Every timing phrase ("at", "from", "to", "silence_before") must be copied EXACTLY from that scene's narration (2 to 5 words).

Reply with ONE JSON object:
{"title": "...", "uncommon_word": {"word": "...", "meaning": "..."},
 "cast": {"cat": {"kind": "cat", "color": "orange"}},
 "parts": [{"thumbnail_scene": 1, "thumbnail_hook": "1 to 3 words in capitals, a tease", "scenes": [{"narration": "...", "visual": "...", "world": "day", "stage": "home", "camera": "push_in", "tone": "playful", "actors": [{"who": "cat", "at": "ground_mid", "mood": "smug", "action": "talk"}], "popups": [{"text": "WHY?", "kind": "burst", "at": "Why do cats", "near": "cat"}]}]}],
 "youtube": {"description": "...", "tags": ["..."], "pinned_comment": "a question for the comments"},
 "tiktok": {"caption": "...", "hashtags": ["#a", "#b", "#c", "#d", "#e"]}}"""


CRITIC = """You are a ruthless editor for "tidalfolio", an entertainment channel of short "Why ...?" videos whose goal is to bond with viewers. You get the title and the narration of every scene. Score each 1 to 5, honestly (3 is acceptable, 1 or 2 means rewrite):
q1 HOOK: would a stranger scrolling stop in the first three seconds? q2 LADDER: does every scene reveal something NEW that re-frames the last, with the answer unfolding (not repeated points, not a list of facts)?
q3 BOND: is there a relatable, specific truth that makes the viewer say "that is so me / my pet", and does the last line feel warm or give a wink they would share? q4 FUNNY: is it genuinely amusing, in a dry, human way, not childish?
q5 SURPRISE: does the final reveal land as a satisfying answer to the question? q6 HUMAN VOICE: specific, odd, uneven rhythm, a point of view, or smooth machine prose with stock phrases ("it turns out", "in fact", tidy triads)? q7 SHAREABILITY: one line or idea people would quote or send to a friend. q8 ORIGINAL: is the answer told as a fresh, unmistakable folio tale (an invented legend, deal, rule or secret with a personality) rather than the textbook explanation any other channel would give? Score 1 or 2 if it sounds like every other why video.
Reply with ONE JSON object: {"scores": {"q1": 4, ...}, "problems": ["specific, actionable fixes naming the scene, only for scores of 1 or 2, max 4"]}"""
MIN_AVG = float(os.environ.get("WHY_MIN_SCORE", "3.6"))


def critique(G, sb):
    """Second pass: an editor scores the draft. Returns a list of problems (empty = approved or the editor did not answer: it is a bonus, never a blocker)."""
    text = "\n".join(f"  {n}. {sc['narration']}" for n, sc in enumerate(sb["parts"][0]["scenes"], 1))
    try:
        r = json.loads(G.call_openai([{"role": "system", "content": CRITIC}, {"role": "user", "content": f"Title: {sb.get('title')}\n{text}"}], 0.3))
    except (ValueError, SystemExit, TypeError):
        return []
    scores = {k: v for k, v in (r.get("scores") or {}).items() if isinstance(v, (int, float))}
    if not scores:
        return []
    avg = sum(scores.values()) / len(scores)
    low = [k for k, v in scores.items() if v <= 2]
    if low or avg < MIN_AVG:
        why = r.get("problems") or ["make it more surprising, warmer and funnier"]
        return [f"the editor scored it {avg:.1f} (weak: {', '.join(sorted(low)) or 'overall'}): " + "; ".join(str(w) for w in why[:4])]
    return []


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
    for k, sc in enumerate(parts[0].get("scenes", []), 1):
        if len(str(sc.get("visual", "")).split()) < 10:
            bad.append(f"scene {k}: 'visual' must be one concrete sentence of at least 10 words describing the picture (pose, expression, setting, light, every named object).")
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
    user = ((f"Topic to use: {idea}. " if idea else "Invent the topic yourself: a why question people wonder about and search for, from an angle no other channel takes. ")
            + (f"Topics already made (choose a different topic AND a different storytelling device): {'; '.join(titles[-40:])}. " if titles else "")
            + "Write the video now.")
    msgs = [{"role": "system", "content": system_prompt()}, {"role": "user", "content": user}]
    last, fallback = [], None
    for attempt in range(1 + REPAIRS):
        raw = G.call_openai(msgs, 0.9 if attempt == 0 else 0.5)
        try:
            sb = W.normalize(json.loads(raw))
        except (ValueError, TypeError) as e:
            last = [f"the reply was not valid JSON ({e})."]
            msgs += [{"role": "assistant", "content": str(raw)[:6000]}, {"role": "user", "content": "Reply again with ONE valid JSON object. " + last[0]}]
            continue
        sb["art"], sb["character_look"] = "backdrop", "blob"
        bad, scripts = why_problems(sb, G, number)
        if not bad and attempt < REPAIRS:          # the editor reads a valid draft; if it is weak it goes back for a rewrite (the last round always keeps a valid draft)
            bad = critique(G, sb)
            if bad:
                fallback = (sb, scripts)
                scripts = None
                log("Editor: " + bad[0][:200])
        if not bad:
            names = W._save_story({k: v for k, v in sb.items() if k != "outline"}, scripts, "Funny People", number, 1)
            log("Queued: " + ", ".join(names))
            return names
        last = bad
        log(f"Why video attempt {attempt + 1} needs fixes: " + " | ".join(b[:160] for b in bad[:4]))
        msgs += [{"role": "assistant", "content": json.dumps(sb)[:7000]},
                 {"role": "user", "content": "Fix ALL of these problems and reply with the complete corrected JSON object:\n- " + "\n- ".join(bad)}]
    if fallback:                                  # never let the channel go silent: a valid draft the editor found weak still beats nothing
        names = W._save_story({k: v for k, v in fallback[0].items() if k != "outline"}, fallback[1], "Funny People", number, 1)
        log("Queued the best valid draft (the editor wanted more): " + ", ".join(names))
        return names
    raise SystemExit("The why video could not be made valid: " + "; ".join(last)[:600])
