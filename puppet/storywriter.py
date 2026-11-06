"""Write a new puppet story with an AI model, check it, and queue it.

The model only writes a *storyboard* (see storyboard.py): narration plus who is where, how they feel and what they do.
This module then
  1. checks it against the channel rules (words, narrator rules, one uncommon word, cast, timing phrases ...),
  2. compiles it to a puppet script and draws one test frame per scene so a broken script never reaches the render,
  3. measures the real narration length (45 to 60 s), and sends any problem back to the model to fix (up to 4 tries),
  4. saves scripts/NNN-title.json and adds it to queue-puppet.txt.
Needs OPENAI_API_KEY (text only: a few cents per story). Model: OPENAI_TEXT_MODEL (default gpt-4o-mini; a stronger one writes better stories).
"""
import json
import os
import random
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
QUEUE = ROOT / "queue-puppet.txt"
DONE = ROOT / "done-puppet.txt"
MIN_LEN, MAX_LEN = 45.0, 60.0
AIM = "aim for 50 to 57 seconds"
SEC_PER_WORD, SCENE_OVERHEAD, END_CARD = 0.55, 1.5, 3.5     # measured on the real narrator; used only when the voice model is absent

SERIES = {"Bird Banter": "eagles and squirrels: pride, hunger, rivalry, bad decisions on a cliff",
          "Funny Animals": "a rabbit, squirrels and eagles in absurd high-stakes situations"}


def _lines(p):
    return [l.strip() for l in p.read_text().splitlines() if l.strip() and not l.startswith("#")] if p.exists() else []


IDEAS = ROOT / "ideas.txt"


def take_idea():
    """First idea in ideas.txt (one per line, # = comment). It is removed from the file when taken."""
    if not IDEAS.exists():
        return None
    lines = IDEAS.read_text().splitlines()
    for i, l in enumerate(lines):
        if l.strip() and not l.startswith("#"):
            IDEAS.write_text("\n".join(lines[:i] + lines[i + 1:]) + "\n")
            return l.strip()
    return None


def give_back_idea(idea):
    IDEAS.write_text(IDEAS.read_text().rstrip("\n") + "\n" + idea + "\n")


def choose_parts(log=print):
    """How many parts the next story gets (2 to 4). With real results it learns from viewer drop-off between parts:
    if Part 2 keeps fewer than ~45% of Part 1's views, stories get shorter; if it keeps over 80%, they may run longer."""
    default = random.choice([2, 3, 3, 4])
    try:
        rows = json.loads((ROOT / "metrics" / "videos.json").read_text())
    except Exception:
        return default
    stories = {}
    for r in rows:
        sp, st = r.get("part"), r.get("stats") or {}
        if sp and st.get("views") is not None and r.get("privacy") == "public":
            stories.setdefault(sp["story"], {})[sp["part"]] = st["views"]
    ratios = [v[k + 1] / max(1, v[k]) for v in stories.values() for k in v if k + 1 in v and v[k] >= 20]
    if len(ratios) < 3:
        return default
    r = sum(ratios) / len(ratios)
    n = 2 if r < 0.45 else (random.choice([3, 4]) if r > 0.8 else default)
    log(f"Part drop-off: each part keeps {r:.0%} of the previous part's views, so this story gets {n} parts.")
    return n


def unrendered():
    done = set(_lines(DONE))
    return [q for q in _lines(QUEUE) if q not in done and (SCRIPTS / q).exists()]


def system_prompt(n_lo, n_hi, n_parts=3):
    parts_text = f"{n_parts}"
    return f"""You write short animated fable videos for "tidalfolio", a comedy channel about animals. A video is a handful of scenes drawn by code
(bold cartoon style) and told by ONE narrator: a middle-aged man with a warm baritone, a gifted storyteller telling a tale he knows by heart.
You do not write drawing code. You write a STORYBOARD (JSON) and the system draws it.

CHANNEL RULES (all mandatory)
- Audience: all ages INCLUDING adults. Wit is dry and deadpan, never babyish or cartoonish. No baby talk, no puns on every line.
- THE NARRATOR TELLS THE STORY FROM OUTSIDE IT. He never mentions himself: no "I", "me", "my", "we", "our" in his own words (characters may say them inside quotation marks). Third person, mostly past tense. He never tells the listener what to do or think, gives no advice, no moral, no "remember that". Like a grandfather retelling Tom and Jerry to his grandson, or a teacher telling a war story to a class: vivid, specific, dramatic, never boring.
- STORYTELLING ETIQUETTE: vary pace. Slower for suspense and the emotional beat, brisker for action. A long rolling sentence of build-up, then a short one that lands. Put the key word LAST in a sentence. Use silence before a twist. Rule of three where the third breaks the pattern. At most one rhetorical question. Never explain a joke. Short sentences are spoken slowly and dramatically, so use them for the punchlines.
- COMMON WORDS ONLY: plain everyday English an ordinary 12-year-old knows. EXCEPT exactly ONE uncommon word per story (a real useful word most viewers don't know, e.g. "indolent", "audacious", "meticulous", "reluctant", "frugal"). Use it exactly once, inside a normal sentence, and then simply carry on with the story. NEVER define it, translate it, repeat it, follow it with a synonym, point at it ("a fancy word for", "which means", "that is another word for") or hint that it is special: the viewer will look it up in their own time. The story's events may show what it means, but the narrator never does. Nothing about it is shown on screen. Put it in "uncommon_word": {{"word", "meaning"}} (the meaning is for our records only). Never a name or slang.
- No sound effects exist: never write onomatopoeia like "crash!" in the narration (a visual pop-up word like CRASH is fine). Audio is voice plus music only.
- EVERY AGE: the channel is for everyone from young children to grandparents. No profanity or rude words (a bubble of symbols like #@%! is fine), no gore, no weapons, no real violence or death on screen or in the narration, no sexual or romantic content beyond a friendly hug, nothing frightening beyond mild, brief peril, no cruelty or bullying played as a joke, no drugs or alcohol, no politics or religion. Real feelings are welcome (loss, jealousy, regret, forgiveness) as long as they are told gently. Animals are never harmed: slapstick only.
- STORY ENGINE (a funny video with no story is forgotten): (1) STAKES FIRST: scene 1 states a premise a stranger understands instantly, never scenery or a greeting. (2) ONE named PROTAGONIST who wants something badly and has something to lose. (3) THREE ESCALATING REVERSALS, each flipping what the viewer hopes for. (4) ONE REAL EMOTIONAL BEAT in the middle (loyalty, shame, fear, tenderness) played straight with no joke. (5) A calm, short, haunting LAST LINE that leaves the viewer pondering what it was really about. (6) One SHAREABLE moment so absurd or striking a viewer would show a friend.
- A LESSON FOR HUMANS, but NEVER stated or hinted at in the video: the story shows through what the animals do and what it costs them. Write the lesson as ONE plain sentence in "lesson" (max 25 words) for the record only. People rarely go wrong because they are fools: set "cause" to why the protagonist makes the key choice: "forgot" (knew the value, lost it under pressure), "believed" (sincerely thought it was right), or "no_options" (every path cost something). Show that cause in their own reasoning so viewers understand the choice from the inside. Never say the cause aloud.
- HUMOUR: deadpan gravity about trivial stakes; specific absurd numbers and rules; understatement after big action; one planted odd detail that returns later raising a question.

CREATIVE DIRECTION (the Tidal Folio master brief; follow it, within the channel rules above and the stage limits below)
- Substance beyond funny animals: the animals live out recognizable human situations: jealousy, betrayal, greed, envy, deception; love, friendship, loyalty, trust, forgiveness; competition, pride, ambition, revenge; injustice, selfishness, manipulation; kindness, sacrifice, unexpected generosity; misunderstandings, secrets, embarrassment, shocking revelations. NEVER explain the underlying message or spell out the comparison; the audience works it out.
- Dramatic shape, in this order: an IMMEDIATE HOOK (the first seconds show something intriguing: a shocking discovery, a suspicious encounter, a betrayal, a confrontation about to erupt, an embarrassing situation; no introductions, no scenery); the CONFLICT made clear at once (who wants what, what stands in the way, why it matters); rising ANTICIPATION (suspicious glances, deliberate pauses, a character noticing what they should not, near discoveries, interrupted confrontations, hidden motives, small details that matter later); ESCALATION (each development more complicated, more embarrassing, more emotional, funnier or more dangerous; reversals, misunderstandings, failed plans, interruptions; never predictable or repetitive; every scene adds new information, raises the stakes or changes what the viewer understands); a PAYOFF that rewards the anticipation and feels earned (a betrayal, a clever reversal, a public embarrassment, a secret exposed, an unexpected kindness, a character caught in their own scheme, an ironic consequence, a surprising reconciliation); a lasting final image or line, with a small unanswered question.
- Comedy comes from character and situation, not random jokes: perfectly timed reactions, awkward silence, exaggerated faces, unexpected confidence, misunderstandings, clever deception, irony, role reversals, physical comedy, contrasting personalities. Balance it with real emotion: a story can be hilarious and still carry betrayal, disappointment, compassion or justice. No childish humour, no meaningless chaos, no predictable jokes.
- Characters: each has a distinct personality, a clear motivation and a particular way of reacting to conflict, shown through mood and action. Keep them consistent and appealing.
- Staging (the storyboard must leave nothing to interpretation): decide for every scene who stands where ("at"), which way they face ("face"), who is looking at whom (two characters in a confrontation face each other), their mood and their movement. Avoid long static scenes: change the camera or the action every scene.
- Silence before revelations and punchlines (use "silence_before").
- Before you answer, silently check: does the opening create curiosity? is the conflict easy to understand? does every scene give a reason to keep watching? does tension rise rather than stay flat? is there at least one unexpected development? is the comedy situation-driven? are the characters believable? is the climax satisfying and memorable? does the story keep its deeper meaning without explaining it? If any answer is no, rewrite that part first. Story quality beats spectacle, comedy beats noise, essence beats a shocking twist.

STORY IN PARTS: every story is told as {parts_text} consecutive videos (Part 1, Part 2 ...), published one after another. Write ALL parts now, in "parts": [{{"scenes": [...]}}, ...].
- The parts play one right after another, so the viewer should barely notice where one ends and the next begins. Part 1 opens with the hook. Every later part carries on from the exact moment the previous part stopped: NO recap, NO re-introduction of the characters or setting, NO "previously" and NO announcement that a new part has started. Each part still has its own small reversal so it never drags.
- Every part EXCEPT the last ends mid-story on a line that pulls straight into the next scene (a reveal, a worse problem, a question), told like any other line of the story: never "to be continued", never "in the next part", never an instruction.
- Part 1 opens with the stakes; the last part holds the emotional resolution and the haunting last line. The one uncommon word appears exactly once in the WHOLE story. Characters, setting and objects stay consistent across parts.

LENGTH: EACH PART (not the whole story) must run {MIN_LEN:.0f} to {MAX_LEN:.0f} seconds, {AIM}. The storyteller speaks slowly and steadily (about 0.55 s per word, never rushed) and each scene adds about 1.5 s of pauses, so write {n_lo} to {n_hi} scenes of 9 to 14 words each per part (roughly 70 to 85 words per part). Open on the hook at once. No filler scene. Spend the few words on specific, surprising details and on what the characters say, never on scenery.
- NARRATION MUST BE EASY TO SPEAK: a voice reads it aloud. Use only ordinary words that are easy to pronounce (the one uncommon word aside), simple names (one or two syllables: Pip, Orrin, Mabel, Biscuit), numbers written as words ("forty-two"), no digits, no abbreviations, no symbols, no all-capital words in the narration, no invented words or unusual spellings. Keep sentences short to medium (at most about 16 words); put a comma at each natural pause.

THE STAGE (this is all that can be drawn, so write for it)
- Cast: 1 to 4 characters. species "eagle" (cast "look": "orrin" = plain brown, "dad" = dark brown, "mom" = lighter brown with a pink scarf; give every eagle in the story a different look), "squirrel" (optional "hat": "bowler", optional "item": "popcorn"), "rabbit". Give each a short first name in "name". No other animals exist.
- Each scene: "world" (dawn|day|dusk|storm|night|sunset), "stage": "cliff" (a clifftop above a valley and sea, mountains and a distant castle), "nest" (the same with a big nest), or "tree" (a lone tree whose branch reaches toward the cliff).
- "camera": hold|push_in|pull_back|pan_right|pan_left. "music": calm|tense|sad|joyful (the music follows the emotion of the scene). Optional "silence_before": a few words of the narration; the music cuts out and the picture freezes just before them (use on at most 2 scenes, for the biggest reveal).
- "actors": who is on screen. "at": ground_left|ground_mid|ground_right (on the cliff; any species), branch_a|branch_b (squirrels only, needs stage "tree"), air_left|air_mid|air_right (eagles only, flying). "face": left|right (optional). "mood": neutral|sleepy|happy|angry|scared|sad|shocked|smug|dizzy. "action": stand|talk|hop|flap. "talk" moves the beak/mouth: give "from" and "to" (words in the narration) for when he speaks or give nothing for most of the scene. "enter": words in the narration at which this character flies or hops in from off-screen; "exit": words at which he leaves. Eagles may "carry": "fish".
- "popups": comic speech bubbles ("kind": "bubble", a short spoken line or reaction) and impact words ("kind": "burst", e.g. CRASH, MINE, WHAT). "text" 1 to 4 words, "at": words in the narration when it pops, "near": which actor it belongs to. Use them in at least half the scenes: they are the punctuation of the jokes.
- "fx": [{{"kind": "puff"|"sparkle"|"speed", "at": words, "near": actor}}]: a dust cloud for landings and crashes, a sparkle for magic or a lucky moment, speed streaks for a dash.
- EVERY phrase you give ("from", "to", "enter", "exit", "at", "silence_before") must be copied EXACTLY (same capitals, same punctuation) from THAT scene's narration, a span of 2 to 5 words. Characters can only exist on screen if listed in "actors" of that scene. Keep a character in the same spot while nothing moves them; change spots only when the narration says so.
- VARIETY (the channel must never feel like one template repeated): each story needs its own premise and plot shape (a heist, a rivalry, a rescue, a rumour, a bet, a misunderstanding, a rivalry between friends, a trade that goes wrong ...), its own lead character, its own time of day and weather, and its own opening line. Do not start two stories the same way. Titles and the first sentence of the YouTube description should say plainly what the story is about, with the hook in the first 5 words.
- Ending: the last part ends on its haunting last line. The system adds a plain end screen after the final part only, so never write a sign-off, a part announcement or a call to follow or subscribe in any narration.

Reply with ONE JSON object, exactly this shape:
{{"title": "Episode title (no series prefix)", "lesson": "...", "cause": "forgot|believed|no_options",
 "uncommon_word": {{"word": "...", "meaning": "..."}},  "cast": {{"key": {{"species": "eagle", "look": "orrin", "name": "Orrin"}}, "key2": {{"species": "squirrel", "hat": "bowler"}}}},
 "parts": [{{"thumbnail_scene": 2, "scenes": [{{"narration": "...", "world": "dawn", "stage": "cliff", "camera": "push_in", "music": "calm",
   "actors": [{{"who": "key", "at": "ground_mid", "mood": "smug", "action": "talk", "from": "words", "to": "words"}}],
   "popups": [{{"text": "MINE.", "kind": "burst", "at": "words", "near": "key"}}], "fx": []}}]}}],
 "youtube": {{"description": "2-4 sentences: a teaser for the whole story (no moral, no part numbers)", "tags": ["8-12 tags"], "pinned_comment": "a question that makes viewers think of their own life"}},
 "tiktok": {{"caption": "<=140 chars hook", "hashtags": ["#a", "#b", "#c", "#d", "#e"]}}}}"""


CRITIC_PROMPT = """You are a ruthless story editor for Tidal Folio, a deadpan animal-fable channel. You get a story told in parts (the narration of every scene).
Score it 1 to 5 on each question, being honest (a 3 is acceptable, 1 or 2 means it must be rewritten):
q1 Does the opening immediately create curiosity? q2 Is the central conflict easy to understand? q3 Does every scene give a reason to keep watching?
q4 Does tension rise rather than stay flat? q5 Are there unexpected developments? q6 Is the comedy genuinely funny and situation-driven (not random or childish)?
q7 Are the characters emotionally believable? q8 Is the climax satisfying and earned? q9 Does it keep a deeper meaning WITHOUT explaining it (no moral, no advice)?
q10 Does every part hold attention and end (except the last) on a line that pulls straight into the next part?
Reply with ONE JSON object: {"scores": {"q1": 4, ...}, "problems": ["specific, actionable fixes naming the part and scene, only for scores of 1 or 2, max 5"]}"""


def critique(G, sb):
    """Second AI pass: an editor scores the story. Returns a list of problems (empty = approved)."""
    text = "\n".join(f"PART {pi}:\n" + "\n".join(f"  {n}. {sc['narration']}" for n, sc in enumerate(part["scenes"], 1))
                     for pi, part in enumerate(sb["parts"], 1))
    try:
        r = json.loads(G.call_openai([{"role": "system", "content": CRITIC_PROMPT}, {"role": "user", "content": f"Title: {sb.get('title')}\n{text}"}], 0.3))
    except (ValueError, SystemExit):
        return []                               # the editor is a bonus: never block a story because it failed to answer
    scores = r.get("scores") or {}
    low = [k for k, v in scores.items() if isinstance(v, (int, float)) and v <= 2]
    if not low:
        return []
    return [f"an editor rejected the story (weak: {', '.join(sorted(low))}): " + "; ".join(r.get("problems") or ["make it more surprising, more tense and funnier"])]


def _measure(script):
    """Narration + pauses length in seconds. Real voice when the model is cached, otherwise a calibrated estimate."""
    from . import render, tts
    try:
        tts.ensure_models()                     # always measure with the real voice (downloads the model once if it is not cached)
        ok_model = True
    except Exception:
        ok_model = False
    if ok_model:
        scenes = json.loads(json.dumps(script["scenes"]))
        tmp = Path(tempfile.mkdtemp())
        try:
            render.make_narration(script, scenes, tmp, False)
            return render.plan_timing(scenes), "real voice"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    words = sum(len(re.findall(r"[A-Za-z0-9']+", s["narration"])) for s in script["scenes"])
    return words * SEC_PER_WORD + SCENE_OVERHEAD * len(script["scenes"]) + (END_CARD if any(x.get("end_card") for x in script["scenes"]) else 0.0), "estimate"


def _smoke(script):
    """Draw one frame of every scene (silent placeholder narration). Returns an error string or ''."""
    from . import render
    tmp = Path(tempfile.mkdtemp())
    p = tmp / "s.json"
    p.write_text(json.dumps(script))
    try:
        render.render_stills(p, [1.0], tmp / "out")
        return ""
    except SystemExit as e:
        return str(e)
    except Exception as e:      # any drawing error is feedback for the model
        return f"{type(e).__name__}: {e}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def normalize(sb):
    """Models sometimes wrap the storyboard in one outer key, give 'parts' as an object keyed Part 1, Part 2 ..., or give
    each part as a bare list of scenes. Fix those shapes so a good story is not thrown away over formatting."""
    if isinstance(sb, dict) and "parts" not in sb and len(sb) == 1:
        inner = next(iter(sb.values()))
        if isinstance(inner, dict):
            sb = inner
    if isinstance(sb, dict):
        parts = sb.get("parts")
        if isinstance(parts, dict):
            parts = [v for _, v in sorted(parts.items())]
        if isinstance(parts, list):
            sb["parts"] = [{"scenes": p} if isinstance(p, list) else p for p in parts]
    return sb


def problems(sb, number):
    """All problems with a storyboard, in plain words, plus the compiled part scripts when it is usable."""
    from . import storyboard as SB
    bad = SB.check_storyboard(sb)
    if bad:
        return bad, None
    scripts = SB.compile_storyboard(sb, number)
    for sc in scripts:
        pi = sc["series_part"]["part"]
        err = _smoke(sc)
        if err:
            bad.append(f"part {pi}: drawing the storyboard failed: {err[:300]}")
            continue
        total, how = _measure(sc)
        if not MIN_LEN <= total <= MAX_LEN:
            words = sum(len(re.findall(r"[A-Za-z0-9']+", x["narration"])) for x in sc["scenes"])
            delta = int((54.0 - total) / SEC_PER_WORD)
            bad.append(f"part {pi} would run {total:.0f} s ({how}); every part must run {MIN_LEN:.0f} to {MAX_LEN:.0f} s ({AIM}). "
                       f"It has {words} narration words in {len(sc['scenes'])} scenes. {'Add' if delta > 0 else 'Cut'} about {abs(delta)} words (or scenes) in part {pi}.")
    return bad, (None if bad else scripts)


BIBLE_STEP = """STEP 1: plan the story. Do NOT write scenes yet, and ignore any instruction above to write every part at once: the parts are written one at a time in the next messages.
Reply with ONE JSON object with exactly these keys:
{"title": "Episode title (no series prefix)", "lesson": "...", "cause": "forgot|believed|no_options", "uncommon_word": {"word": "...", "meaning": "..."},
 "cast": {"key": {"species": "eagle", "look": "orrin", "name": "Orrin"}, "key2": {"species": "squirrel", "hat": "bowler"}},
 "outline": [EXACTLY %d strings, one per part: what happens in that part and the line it stops on],
 "youtube": {"description": "2-4 sentences: a teaser for the whole story (no moral, no part numbers)", "tags": ["8-12 tags"], "pinned_comment": "a question that makes viewers think of their own life"},
 "tiktok": {"caption": "<=140 chars hook", "hashtags": ["#a", "#b", "#c", "#d", "#e"]}}"""

PART_SHAPE = ('Reply with ONE JSON object: {"thumbnail_scene": 2, "scenes": [ 6 to 8 scenes, each in exactly the scene format given in the instructions ]}. '
              "Use the cast keys exactly as planned. The timing phrases ('from', 'to', 'enter', 'exit', 'at', 'silence_before') must be copied EXACTLY from the NARRATOR's words in that same scene, "
              "never from what a character says in a speech bubble; if you are not sure, leave them out. 'mood' must be one of neutral, sleepy, happy, angry, scared, sad, shocked, smug, dizzy; "
              "'action' one of stand, talk, hop, flap.")


def _part_rules(k, n, word, uw_part):
    role = ("It opens on the hook at once." if k == 1 else
            f"It carries on from the exact moment part {k - 1} stopped: no recap, no re-introduction of the characters or the setting, no announcement that a new part has started. "
            f"A viewer must not be able to tell where part {k - 1} ended.")
    role += (f" It ends mid-story on a line that pulls straight into part {k + 1} (never 'to be continued')." if k < n else
             " It holds the emotional resolution and the haunting last line.")
    w = (f'Use the uncommon word "{word}" exactly once in this part.' if k == uw_part else f'Do not use the uncommon word "{word}" in this part.')
    return f"{role} {w}"


def _bible_problems(b, n, used_words):
    from . import storyboard as SB
    if not isinstance(b, dict):
        return ["the reply must be one JSON object."]
    bad = []
    cast = b.get("cast")
    if not isinstance(cast, dict) or not 1 <= len(cast) <= 4:
        bad.append("'cast' must be an object with 1 to 4 characters.")
    else:
        for key, c in cast.items():
            if not isinstance(c, dict) or c.get("species") not in SB.SPECIES:
                bad.append(f"cast '{key}': species must be one of {SB.SPECIES}.")
            elif c["species"] == "eagle" and c.get("look", "orrin") not in SB.LOOKS:
                bad.append(f"cast '{key}': an eagle's look must be one of {SB.LOOKS}.")
    outline = b.get("outline")
    if not (isinstance(outline, list) and len(outline) == n and all(isinstance(x, str) and x.strip() for x in outline)):
        bad.append(f"'outline' must be a list of exactly {n} non-empty strings, one per part.")
    uw = b.get("uncommon_word")
    word = uw.get("word", "").strip() if isinstance(uw, dict) and isinstance(uw.get("word"), str) else ""
    if not word:
        bad.append("'uncommon_word' must be {word, meaning}.")
    elif word.lower() in used_words:
        bad.append("that uncommon word was used in an earlier story; pick a different one.")
    if not isinstance(b.get("title"), str) or not b["title"].strip():
        bad.append("'title' is missing.")
    if not isinstance(b.get("lesson"), str) or not b["lesson"].strip():
        bad.append("'lesson' (one plain sentence) is missing.")
    if b.get("cause") not in ("forgot", "believed", "no_options"):
        bad.append("'cause' must be forgot, believed or no_options.")
    if not isinstance(b.get("youtube"), dict) or not b["youtube"].get("description"):
        bad.append("'youtube' needs description, tags and pinned_comment.")
    if not isinstance(b.get("tiktok"), dict) or not b["tiktok"].get("caption"):
        bad.append("'tiktok' needs caption and hashtags.")
    return bad


MOOD_FIX = {"excited": "happy", "joyful": "happy", "cheerful": "happy", "proud": "smug", "sly": "smug", "sneaky": "smug", "cunning": "smug",
            "greedy": "smug", "confident": "smug", "mad": "angry", "furious": "angry", "determined": "angry", "annoyed": "angry", "jealous": "angry",
            "worried": "scared", "afraid": "scared", "nervous": "scared", "anxious": "scared", "surprised": "shocked", "amazed": "shocked",
            "confused": "dizzy", "tired": "sleepy", "bored": "sleepy", "worried_sad": "sad", "disappointed": "sad", "curious": "neutral"}
ACTION_FIX = {"fly": "flap", "flying": "flap", "speak": "talk", "speaking": "talk", "shout": "talk", "jump": "hop", "run": "hop", "walk": "hop", "sit": "stand"}


def _sanitize(part, cast=None):
    """Repair small slips in a part instead of throwing the whole part away: timing phrases that are not words of the narration
    (the model often puts a character's speech there), moods and actions outside the list, over-long or misplaced pop-ups."""
    from . import storyboard as SB
    scenes = part.get("scenes") if isinstance(part, dict) else None
    if not isinstance(scenes, list):
        return part
    for sc in scenes:
        if not isinstance(sc, dict):
            continue
        if isinstance(sc.get("narration"), str):      # straight quotes, and a proper full stop at the end of the line
            t = sc["narration"].replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'").strip()
            if not re.search(r'[.!?]"?$', t):
                t = t.rstrip(" ,;:-\u2014\u2013\u2026") + "."
            sc["narration"] = t
        nar = sc.get("narration") if isinstance(sc.get("narration"), str) else ""
        if cast and isinstance(sc.get("actors"), list):   # an actor that is not in the cast cannot be drawn: leave them out of the scene
            sc["actors"] = [a for a in sc["actors"] if not isinstance(a, dict) or a.get("who") in cast]
        for key, allowed, fix, default in (("world", SB.WORLDS, {}, "day"), ("stage", SB.STAGES, {}, "cliff"), ("camera", SB.CAMERAS, {}, "hold"), ("music", SB.MUSICS, {}, "calm")):
            if key in sc and sc[key] not in allowed:
                sc[key] = default
        if sc.get("silence_before") and not SB.phrase_ok(nar, sc["silence_before"]):
            sc.pop("silence_before")
        for a in sc.get("actors") or []:
            if not isinstance(a, dict):
                continue
            if a.get("mood", "neutral") not in SB.MOODS:
                a["mood"] = MOOD_FIX.get(str(a.get("mood")).lower(), "neutral")
            if a.get("action", "stand") not in SB.ACTIONS:
                a["action"] = ACTION_FIX.get(str(a.get("action")).lower(), "stand")
            if any(a.get(k) and not SB.phrase_ok(nar, a[k]) for k in ("from", "to")):
                a.pop("from", None)
                a.pop("to", None)
            for k in ("enter", "exit"):
                if a.get(k) and not SB.phrase_ok(nar, a[k]):
                    a.pop(k)
        words = nar.split()
        for pu in sc.get("popups") or []:
            if not isinstance(pu, dict):
                continue
            if pu.get("kind", "bubble") not in ("bubble", "burst"):
                pu["kind"] = "bubble"
            if isinstance(pu.get("text"), str) and SB._w(pu["text"]) > SB.MAX_WORDS_BUBBLE:
                pu["text"] = " ".join(pu["text"].split()[:SB.MAX_WORDS_BUBBLE])
            if not SB.phrase_ok(nar, pu.get("at")) and len(words) >= 2:
                pu["at"] = " ".join(words[:2])
            if pu.get("near") and pu["near"] not in [a.get("who") for a in sc.get("actors") or [] if isinstance(a, dict)]:
                pu.pop("near")
        sc["fx"] = [f for f in (sc.get("fx") or []) if isinstance(f, dict) and f.get("kind") in ("puff", "sparkle", "speed") and SB.phrase_ok(nar, f.get("at"))]
    return part


def _part_problems(part, cast, k, word, uw_part):
    from . import storyboard as SB
    if not isinstance(part, dict):
        return [f"part {k}: the reply must be one JSON object with 'scenes'."]
    scenes = part.get("scenes")
    if isinstance(scenes, list) and all(isinstance(x, dict) for x in scenes):
        _sanitize(part, cast)
    if isinstance(scenes, list) and not all(isinstance(x, dict) for x in scenes):
        return [f"part {k}, every scene must be a JSON object."]
    bad = SB._check_scenes(scenes, cast, f"part {k}, ")
    text = " ".join(str(x.get("narration", "")) for x in (scenes if isinstance(scenes, list) else []))
    want, got = (1 if k == uw_part else 0), len(re.findall(rf"\b{re.escape(word)}\b", text, re.I))
    if got != want:
        bad.append(f"part {k}: the uncommon word {word!r} must appear exactly {want} time(s) in this part's narration (it appears {got}).")
    return bad


def _story_so_far(bible, parts):
    lines = [f"Title: {bible['title']}", "Cast: " + json.dumps(bible["cast"]), "Plan:"]
    lines += [f"  Part {i}: {o}" for i, o in enumerate(bible["outline"], 1)]
    for i, pt in enumerate(parts, 1):
        if pt:
            lines.append(f"PART {i} AS WRITTEN:")
            lines += [f"  {n}. {sc['narration']}" for n, sc in enumerate(pt["scenes"], 1)]
    return "\n".join(lines)


def _rewrite_part(G, system, bible, parts, k, bad, word, uw_part):
    """Ask for part k again with the problems listed; returns the new part, or None if it still fails."""
    n = len(parts)
    for _ in range(2):
        user = (_story_so_far(bible, parts) + f"\n\nRewrite ONLY part {k} of {n}. Fix these problems, keep it continuous with the part before and the part after it, and keep what already works:\n- "
                + "\n- ".join(bad) + "\n\n" + _part_rules(k, n, word, uw_part) + "\n" + PART_SHAPE
                + f"\nThe current JSON of part {k} was:\n" + json.dumps(parts[k - 1], ensure_ascii=False))
        try:
            part = json.loads(G.call_openai([{"role": "system", "content": system}, {"role": "user", "content": user}], 0.7))
        except ValueError:
            continue
        bad = _part_problems(part, bible["cast"], k, word, uw_part)
        if not bad:
            return part
    return None


def write_story(idea=None, series=None, parts=None, log=print):
    """Write a story in stages (a small model cannot reliably write a whole multi-part storyboard in one reply):
    1. plan it (title, cast, lesson, uncommon word, one-line outline per part), 2. write each part on its own, carrying on from the previous one,
    3. check the whole story and rewrite only the parts that fail, 4. save and queue it."""
    sys.path.insert(0, str(ROOT))
    import generate_script as G
    SCRIPTS.mkdir(exist_ok=True)
    number = G.next_number()
    titles, counts = G.existing()
    series = series or min(SERIES, key=lambda s: counts.get(s, 0))
    n_parts = parts or choose_parts(log)
    cause = random.choice(["forgot", "believed", "no_options"])
    lessons, words = G.used_lessons(), G.used_words()
    system = system_prompt(6, 8, n_parts)
    brief = (f"Write the next story for the series \"{series}\" ({SERIES[series]}), told in exactly {n_parts} parts. "
             + (f"Story idea to use: {idea}. " if idea else "Invent a fresh, specific premise. ")
             + f"Use cause \"{cause}\" for the protagonist's key choice. "
             + (f"Do NOT reuse these lessons: {'; '.join(lessons[-12:])}. " if lessons else "")
             + (f"Do NOT reuse these uncommon words: {', '.join(words)}. " if words else "")
             + (f"Titles already used (be different): {'; '.join(titles[-15:])}. " if titles else "")
             + G.performance_notes() + "\n\n" + BIBLE_STEP % n_parts)
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": brief}]

    bible, last_bad = None, []
    for attempt in range(1, 5):                                                   # ---- 1. the plan
        raw = G.call_openai(msgs, temperature=1.0 if attempt == 1 else 0.7)
        try:
            cand = json.loads(raw)
        except ValueError:
            last_bad = ["the reply was not valid JSON"]
        else:
            last_bad = _bible_problems(cand, n_parts, words)
            if not last_bad:
                bible = cand
                break
        log(f"Plan attempt {attempt} rejected: " + " | ".join(last_bad)[:600])
        msgs += [{"role": "assistant", "content": raw},
                 {"role": "user", "content": "Fix these problems and return the full corrected JSON only:\n- " + "\n- ".join(last_bad)}]
    if bible is None:
        raise SystemExit("Could not get a valid story plan after 4 tries. Last problems: " + "; ".join(last_bad))
    msgs.append({"role": "assistant", "content": raw})
    word = bible["uncommon_word"]["word"].strip()
    uw_part = random.randint(1, n_parts)
    log(f"Plan: \"{bible['title']}\" in {n_parts} parts; the uncommon word goes in part {uw_part}.")

    done = []
    for k in range(1, n_parts + 1):                                               # ---- 2. the parts, one at a time
        req = {"role": "user", "content": f"STEP {k + 1}: write ONLY part {k} of {n_parts} now. {_part_rules(k, n_parts, word, uw_part)}\n{PART_SHAPE}"}
        tmsgs, part, last_bad = msgs + [req], None, []
        for attempt in range(1, 5):
            raw = G.call_openai(tmsgs, temperature=0.9 if attempt == 1 else 0.7)
            try:
                cand = json.loads(raw)
            except ValueError:
                last_bad = [f"part {k}: the reply was not valid JSON"]
            else:
                last_bad = _part_problems(cand, bible["cast"], k, word, uw_part)
                if not last_bad:
                    part = cand
                    break
            log(f"Part {k} attempt {attempt} rejected: " + " | ".join(last_bad)[:600])
            tmsgs += [{"role": "assistant", "content": raw},
                      {"role": "user", "content": f"Fix these problems and return the full corrected JSON for part {k} only:\n- " + "\n- ".join(last_bad)}]
        if part is None:
            raise SystemExit(f"Could not get a valid part {k} after 4 tries. Last problems: " + "; ".join(last_bad))
        msgs += [req, {"role": "assistant", "content": raw}]
        done.append(part)

    sb = {key: v for key, v in bible.items() if key != "outline"}
    sb["parts"] = done
    for rnd in range(1, 4):                                                       # ---- 3. check everything, rewrite only the weak parts
        bad, scripts = problems(sb, number)
        if not bad and rnd == 1 and os.environ.get("STORY_CRITIC", "1") != "0":
            bad = critique(G, sb)
        if not bad:
            t = re.sub(rf"^{re.escape(series)}\s*(#\d+)?\s*[:\-]\s*", "", sb["title"].strip(), flags=re.I) or sb["title"].strip()
            names = []
            for sc in scripts:                                                    # ---- 4. save and queue
                sc["short_title"] = t
                sc["series_part"]["story"] = f"{series} #{number}: {t}"
                sc["title"] = f"{series} #{number}: {t} (Part {sc['series_part']['part']}/{n_parts})"
                sc["youtube"]["title"] = sc["title"][:100]
                path = SCRIPTS / f"{sc['slug']}.json"
                path.write_text(json.dumps(sc, indent=1))
                names.append(path.name)
            with open(QUEUE, "a") as f:
                f.write("\n".join(names) + "\n")
            log(f"Wrote {n_parts} parts (check round {rnd}): {', '.join(names)}, queued in order.")
            return names
        by_part = {}
        for m in bad:
            ks = {int(x) for x in re.findall(r"[Pp]art (\d)", m)} & set(range(1, n_parts + 1)) or {n_parts}
            for k in ks:
                by_part.setdefault(k, []).append(m)
        log(f"Check round {rnd} found problems in part(s) {sorted(by_part)}: " + " | ".join(bad)[:600])
        if rnd == 3:
            break
        for k, msgs_k in sorted(by_part.items()):
            new = _rewrite_part(G, system, bible, sb["parts"], k, msgs_k, word, uw_part)
            if new:
                sb["parts"][k - 1] = new
    raise SystemExit("Could not get a story that passes every check after 3 rounds. Last problems: " + "; ".join(bad))
