"""Write a new puppet story with an AI model, check it, and queue it.

The model only writes a *storyboard* (see storyboard.py): narration plus who is where, how they feel and what they do.
This module then
  1. checks it against the channel rules (words, narrator rules, one uncommon word, cast, timing phrases ...),
  2. compiles it to a puppet script and draws one test frame per scene so a broken script never reaches the render,
  3. measures the real narration length (50 to 90 s), and sends any problem back to the model to fix (up to 4 tries),
  4. saves scripts/NNN-title.json and adds it to queue-puppet.txt.
Needs OPENAI_API_KEY (text only: a few cents per story). Model: OPENAI_TEXT_MODEL (default gpt-4o-mini; a stronger one writes better stories).
"""
import json
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
MIN_LEN, MAX_LEN = 50.0, 90.0
AIM = "about 60 to 75 seconds"
SEC_PER_WORD, SCENE_OVERHEAD, END_CARD = 0.57, 1.5, 1.3     # measured on the real narrator; used only when the voice model is absent

SERIES = {"Bird Banter": "eagles and squirrels: pride, hunger, rivalry, bad decisions on a cliff",
          "Funny Animals": "a rabbit, squirrels and eagles in absurd high-stakes situations"}


def _lines(p):
    return [l.strip() for l in p.read_text().splitlines() if l.strip() and not l.startswith("#")] if p.exists() else []


def unrendered():
    done = set(_lines(DONE))
    return [q for q in _lines(QUEUE) if q not in done and (SCRIPTS / q).exists()]


def system_prompt(n_lo, n_hi):
    return f"""You write short animated fable videos for "tidalfolio", a comedy channel about animals. A video is a handful of scenes drawn by code
(bold cartoon style) and told by ONE narrator: a middle-aged man with a warm baritone, a gifted storyteller telling a tale he knows by heart.
You do not write drawing code. You write a STORYBOARD (JSON) and the system draws it.

CHANNEL RULES (all mandatory)
- Audience: all ages INCLUDING adults. Wit is dry and deadpan, never babyish or cartoonish. No baby talk, no puns on every line.
- THE NARRATOR TELLS THE STORY FROM OUTSIDE IT. He never mentions himself: no "I", "me", "my", "we", "our" in his own words (characters may say them inside quotation marks). Third person, mostly past tense. He never tells the listener what to do or think, gives no advice, no moral, no "remember that". Like a grandfather retelling Tom and Jerry to his grandson, or a teacher telling a war story to a class: vivid, specific, dramatic, never boring.
- STORYTELLING ETIQUETTE: vary pace. Slower for suspense and the emotional beat, brisker for action. A long rolling sentence of build-up, then a short one that lands. Put the key word LAST in a sentence. Use silence before a twist. Rule of three where the third breaks the pattern. At most one rhetorical question. Never explain a joke. Short sentences are spoken slowly and dramatically, so use them for the punchlines.
- COMMON WORDS ONLY: plain everyday English an ordinary 12-year-old knows. EXCEPT exactly ONE uncommon word per story (a real useful word most viewers don't know, e.g. "indolent", "audacious", "meticulous", "reluctant", "frugal"). Use it exactly once, where the picture and sentence make its meaning easy to guess; never define it teacherly. Report it in "uncommon_word": {{"word", "meaning"}} (meaning: 1 to 3 plain words). Never a name or slang.
- No sound effects exist: never write onomatopoeia like "crash!" in the narration (a visual pop-up word like CRASH is fine). Audio is voice plus music only.
- Animals are never harmed: slapstick only.
- STORY ENGINE (a funny video with no story is forgotten): (1) STAKES FIRST: scene 1 states a premise a stranger understands instantly, never scenery or a greeting. (2) ONE named PROTAGONIST who wants something badly and has something to lose. (3) THREE ESCALATING REVERSALS, each flipping what the viewer hopes for. (4) ONE REAL EMOTIONAL BEAT in the middle (loyalty, shame, fear, tenderness) played straight with no joke. (5) A calm, short, haunting LAST LINE that leaves the viewer pondering what it was really about. (6) One SHAREABLE moment so absurd or striking a viewer would show a friend.
- A LESSON FOR HUMANS, but NEVER stated or hinted at in the video: the story shows through what the animals do and what it costs them. Write the lesson as ONE plain sentence in "lesson" (max 25 words) for the record only. People rarely go wrong because they are fools: set "cause" to why the protagonist makes the key choice: "forgot" (knew the value, lost it under pressure), "believed" (sincerely thought it was right), or "no_options" (every path cost something). Show that cause in their own reasoning so viewers understand the choice from the inside. Never say the cause aloud.
- HUMOUR: deadpan gravity about trivial stakes; specific absurd numbers and rules; understatement after big action; one planted odd detail that returns later raising a question.

LENGTH: the finished video must run {MIN_LEN:.0f} to {MAX_LEN:.0f} seconds, {AIM}. The storyteller speaks slowly (about 0.57 s per word) and each scene adds about 1.5 s of pauses, so write {n_lo} to {n_hi} scenes of 12 to 24 words each (roughly 110 to 160 words in total). Open on the hook at once. No filler scene.

THE STAGE (this is all that can be drawn, so write for it)
- Cast: 1 to 4 characters. species "eagle" (cast "look": "orrin" = plain brown, "dad" = dark brown, "mom" = lighter brown with a pink scarf; give every eagle in the story a different look), "squirrel" (optional "hat": "bowler", optional "item": "popcorn"), "rabbit". Give each a short first name in "name". No other animals exist.
- Each scene: "world" (dawn|day|dusk|storm|night|sunset), "stage": "cliff" (a clifftop above a valley and sea, mountains and a distant castle), "nest" (the same with a big nest), or "tree" (a lone tree whose branch reaches toward the cliff).
- "camera": hold|push_in|pull_back|pan_right|pan_left. "music": calm|tense|sad|joyful (the music follows the emotion of the scene). Optional "silence_before": a few words of the narration; the music cuts out and the picture freezes just before them (use on at most 2 scenes, for the biggest reveal).
- "actors": who is on screen. "at": ground_left|ground_mid|ground_right (on the cliff; any species), branch_a|branch_b (squirrels only, needs stage "tree"), air_left|air_mid|air_right (eagles only, flying). "face": left|right (optional). "mood": neutral|sleepy|happy|angry|scared|sad|shocked|smug|dizzy. "action": stand|talk|hop|flap. "talk" moves the beak/mouth: give "from" and "to" (words in the narration) for when he speaks or give nothing for most of the scene. "enter": words in the narration at which this character flies or hops in from off-screen; "exit": words at which he leaves. Eagles may "carry": "fish".
- "popups": comic speech bubbles ("kind": "bubble", a short spoken line or reaction) and impact words ("kind": "burst", e.g. CRASH, MINE, WHAT). "text" 1 to 4 words, "at": words in the narration when it pops, "near": which actor it belongs to. Use them in at least half the scenes: they are the punctuation of the jokes.
- "fx": [{{"kind": "puff"|"sparkle"|"speed", "at": words, "near": actor}}]: a dust cloud for landings and crashes, a sparkle for magic or a lucky moment, speed streaks for a dash.
- EVERY phrase you give ("from", "to", "enter", "exit", "at", "silence_before") must be copied EXACTLY (same capitals, same punctuation) from THAT scene's narration, a span of 2 to 5 words. Characters can only exist on screen if listed in "actors" of that scene. Keep a character in the same spot while nothing moves them; change spots only when the narration says so.
- Ending: the last scene shows the tidalfolio title card after it, so do not write a sign-off.

Reply with ONE JSON object, exactly this shape:
{{"title": "Episode title (no series prefix)", "lesson": "...", "cause": "forgot|believed|no_options",
 "uncommon_word": {{"word": "...", "meaning": "..."}}, "thumbnail_scene": 1-based number of the most striking scene,
 "cast": {{"key": {{"species": "eagle", "look": "orrin", "name": "Orrin"}}, "key2": {{"species": "squirrel", "hat": "bowler"}}}},
 "scenes": [{{"narration": "...", "world": "dawn", "stage": "cliff", "camera": "push_in", "music": "calm",
   "actors": [{{"who": "key", "at": "ground_mid", "mood": "smug", "action": "talk", "from": "words", "to": "words"}}],
   "popups": [{{"text": "MINE.", "kind": "burst", "at": "words", "near": "key"}}], "fx": []}}],
 "youtube": {{"title": "<=90 chars, curiosity-driven", "description": "2-4 sentences: a teaser, then a subscribe line (no moral)", "tags": ["8-12 tags"], "pinned_comment": "a question that makes viewers think of their own life"}},
 "tiktok": {{"caption": "<=140 chars hook", "hashtags": ["#a", "#b", "#c", "#d", "#e"]}}}}"""


def _measure(script):
    """Narration + pauses length in seconds. Real voice when the model is cached, otherwise a calibrated estimate."""
    from . import render, tts
    ok_model = all((tts.CACHE / f).exists() for f in tts.FILES)
    if ok_model:
        scenes = json.loads(json.dumps(script["scenes"]))
        tmp = Path(tempfile.mkdtemp())
        try:
            render.make_narration(script, scenes, tmp, False)
            return render.plan_timing(scenes), "real voice"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    words = sum(len(re.findall(r"[A-Za-z0-9']+", s["narration"])) for s in script["scenes"])
    return words * SEC_PER_WORD + SCENE_OVERHEAD * len(script["scenes"]) + END_CARD, "estimate"


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


def problems(sb, number):
    """All problems with a storyboard, in plain words, plus the compiled script when it is usable."""
    from . import storyboard as SB
    bad = SB.check_storyboard(sb)
    if bad:
        return bad, None
    script = SB.compile_storyboard(sb, number)
    err = _smoke(script)
    if err:
        return [f"drawing the storyboard failed: {err[:300]}"], None
    total, how = _measure(script)
    if not MIN_LEN <= total <= MAX_LEN:
        words = sum(len(re.findall(r"[A-Za-z0-9']+", s["narration"])) for s in script["scenes"])
        want = 68.0
        delta = int((want - total) / (SEC_PER_WORD + 0.05))
        verb = "Add" if delta > 0 else "Cut"
        bad.append(f"the video would run {total:.0f} s ({how}); it must run {MIN_LEN:.0f} to {MAX_LEN:.0f} s ({AIM}). "
                   f"It has {words} narration words in {len(script['scenes'])} scenes. {verb} about {abs(delta)} words (or scenes).")
        return bad, None
    return [], script


def write_story(idea=None, series=None, log=print):
    sys.path.insert(0, str(ROOT))
    import generate_script as G
    SCRIPTS.mkdir(exist_ok=True)
    number = G.next_number()
    titles, counts = G.existing()
    series = series or min(SERIES, key=lambda s: counts.get(s, 0))
    cause = random.choice(["forgot", "believed", "no_options"])
    lessons, words = G.used_lessons(), G.used_words()
    n_lo, n_hi = 6, 9
    brief = (f"Write the next story for the series \"{series}\" ({SERIES[series]}). "
             + (f"Story idea to use: {idea}. " if idea else "Invent a fresh, specific premise. ")
             + f"Use cause \"{cause}\" for the protagonist's key choice. "
             + (f"Do NOT reuse these lessons: {'; '.join(lessons[-12:])}. " if lessons else "")
             + (f"Do NOT reuse these uncommon words: {', '.join(words)}. " if words else "")
             + (f"Titles already used (be different): {'; '.join(titles[-15:])}. " if titles else "")
             + "Reply with the JSON object only.")
    msgs = [{"role": "system", "content": system_prompt(n_lo, n_hi)}, {"role": "user", "content": brief}]
    last_bad = []
    for attempt in range(1, 5):
        raw = G.call_openai(msgs, temperature=1.0 if attempt == 1 else 0.7)
        try:
            sb = json.loads(raw)
        except ValueError:
            last_bad = ["the reply was not valid JSON"]
        else:
            last_bad, script = problems(sb, number)
            if sb.get("uncommon_word", {}).get("word", "").lower() in words:
                last_bad.append("that uncommon word was used in an earlier story; pick a different one.")
            if not last_bad:
                t = re.sub(rf"^{re.escape(series)}\s*(#\d+)?\s*[:\-]\s*", "", sb["title"].strip(), flags=re.I) or sb["title"].strip()
                sb["title"] = t
                script["title"] = f"{series} #{number}: {t}"
                script["short_title"] = t
                script["youtube"].setdefault("title", script["title"])
                script["slug"] = f"{number:03d}-{re.sub(r'[^a-z0-9]+', '-', sb['title'].lower()).strip('-')[:48]}"
                path = SCRIPTS / f"{script['slug']}.json"
                path.write_text(json.dumps(script, indent=1))
                with open(QUEUE, "a") as f:
                    f.write(path.name + "\n")
                log(f"Wrote {path.name} (attempt {attempt}) and queued it.")
                return path
        log(f"Attempt {attempt} rejected: " + " | ".join(last_bad)[:600])
        msgs += [{"role": "assistant", "content": raw},
                 {"role": "user", "content": "Fix these problems and return the full corrected JSON only:\n- " + "\n- ".join(last_bad)}]
    raise SystemExit("Could not get a valid story after 4 tries. Last problems: " + "; ".join(last_bad))
