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
MIN_LEN, MAX_LEN = 50.0, 90.0
AIM = "about 60 to 75 seconds"
SEC_PER_WORD, SCENE_OVERHEAD, END_CARD = 0.57, 1.5, 3.0     # measured on the real narrator; used only when the voice model is absent

SERIES = {"Bird Banter": "eagles and squirrels: pride, hunger, rivalry, bad decisions on a cliff",
          "Funny Animals": "a rabbit, squirrels and eagles in absurd high-stakes situations"}


def _lines(p):
    return [l.strip() for l in p.read_text().splitlines() if l.strip() and not l.startswith("#")] if p.exists() else []


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
- COMMON WORDS ONLY: plain everyday English an ordinary 12-year-old knows. EXCEPT exactly ONE uncommon word per story (a real useful word most viewers don't know, e.g. "indolent", "audacious", "meticulous", "reluctant", "frugal"). Use it exactly once, where the picture and sentence make its meaning easy to guess; never define it teacherly. Report it in "uncommon_word": {{"word", "meaning"}} (meaning: 1 to 3 plain words). Never a name or slang.
- No sound effects exist: never write onomatopoeia like "crash!" in the narration (a visual pop-up word like CRASH is fine). Audio is voice plus music only.
- Animals are never harmed: slapstick only.
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
- Every part is a complete, satisfying watch on its own AND moves the story forward: its own hook, its own mini-reversal.
- Every part EXCEPT the last ends on a cliffhanger line (a reveal, a worse problem, a question) that makes the viewer need the next part. The cliffhanger is part of the story, never "to be continued" and never an instruction. The system adds the "Continue to Part N" card and the "Follow, Like, Subscribe, Share" card itself, so never write either in the narration.
- Part 1 opens with the stakes; the last part holds the emotional resolution and the haunting last line. The one uncommon word appears exactly once in the WHOLE story. Characters, setting and objects stay consistent across parts.

LENGTH: EACH PART (not the whole story) must run {MIN_LEN:.0f} to {MAX_LEN:.0f} seconds, {AIM}. The storyteller speaks slowly (about 0.57 s per word) and each scene adds about 1.5 s of pauses, so write {n_lo} to {n_hi} scenes of 12 to 24 words each per part (roughly 110 to 160 words per part). Open on the hook at once. No filler scene.

THE STAGE (this is all that can be drawn, so write for it)
- Cast: 1 to 4 characters. species "eagle" (cast "look": "orrin" = plain brown, "dad" = dark brown, "mom" = lighter brown with a pink scarf; give every eagle in the story a different look), "squirrel" (optional "hat": "bowler", optional "item": "popcorn"), "rabbit". Give each a short first name in "name". No other animals exist.
- Each scene: "world" (dawn|day|dusk|storm|night|sunset), "stage": "cliff" (a clifftop above a valley and sea, mountains and a distant castle), "nest" (the same with a big nest), or "tree" (a lone tree whose branch reaches toward the cliff).
- "camera": hold|push_in|pull_back|pan_right|pan_left. "music": calm|tense|sad|joyful (the music follows the emotion of the scene). Optional "silence_before": a few words of the narration; the music cuts out and the picture freezes just before them (use on at most 2 scenes, for the biggest reveal).
- "actors": who is on screen. "at": ground_left|ground_mid|ground_right (on the cliff; any species), branch_a|branch_b (squirrels only, needs stage "tree"), air_left|air_mid|air_right (eagles only, flying). "face": left|right (optional). "mood": neutral|sleepy|happy|angry|scared|sad|shocked|smug|dizzy. "action": stand|talk|hop|flap. "talk" moves the beak/mouth: give "from" and "to" (words in the narration) for when he speaks or give nothing for most of the scene. "enter": words in the narration at which this character flies or hops in from off-screen; "exit": words at which he leaves. Eagles may "carry": "fish".
- "popups": comic speech bubbles ("kind": "bubble", a short spoken line or reaction) and impact words ("kind": "burst", e.g. CRASH, MINE, WHAT). "text" 1 to 4 words, "at": words in the narration when it pops, "near": which actor it belongs to. Use them in at least half the scenes: they are the punctuation of the jokes.
- "fx": [{{"kind": "puff"|"sparkle"|"speed", "at": words, "near": actor}}]: a dust cloud for landings and crashes, a sparkle for magic or a lucky moment, speed streaks for a dash.
- EVERY phrase you give ("from", "to", "enter", "exit", "at", "silence_before") must be copied EXACTLY (same capitals, same punctuation) from THAT scene's narration, a span of 2 to 5 words. Characters can only exist on screen if listed in "actors" of that scene. Keep a character in the same spot while nothing moves them; change spots only when the narration says so.
- Ending: every part's last scene is followed by the tidalfolio closing card, so do not write a sign-off.

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
q10 Is every part a satisfying watch that ends (except the last) on a cliffhanger that makes the viewer need the next part?
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
            delta = int((68.0 - total) / (SEC_PER_WORD + 0.05))
            bad.append(f"part {pi} would run {total:.0f} s ({how}); every part must run {MIN_LEN:.0f} to {MAX_LEN:.0f} s ({AIM}). "
                       f"It has {words} narration words in {len(sc['scenes'])} scenes. {'Add' if delta > 0 else 'Cut'} about {abs(delta)} words (or scenes) in part {pi}.")
    return bad, (None if bad else scripts)


def write_story(idea=None, series=None, parts=None, log=print):
    sys.path.insert(0, str(ROOT))
    import generate_script as G
    SCRIPTS.mkdir(exist_ok=True)
    number = G.next_number()
    titles, counts = G.existing()
    series = series or min(SERIES, key=lambda s: counts.get(s, 0))
    n_parts = parts or random.choice([2, 3, 3, 4])
    cause = random.choice(["forgot", "believed", "no_options"])
    lessons, words = G.used_lessons(), G.used_words()
    brief = (f"Write the next story for the series \"{series}\" ({SERIES[series]}), told in exactly {n_parts} parts. "
             + (f"Story idea to use: {idea}. " if idea else "Invent a fresh, specific premise. ")
             + f"Use cause \"{cause}\" for the protagonist's key choice. "
             + (f"Do NOT reuse these lessons: {'; '.join(lessons[-12:])}. " if lessons else "")
             + (f"Do NOT reuse these uncommon words: {', '.join(words)}. " if words else "")
             + (f"Titles already used (be different): {'; '.join(titles[-15:])}. " if titles else "")
             + "Reply with the JSON object only.")
    msgs = [{"role": "system", "content": system_prompt(6, 9, n_parts)}, {"role": "user", "content": brief}]
    last_bad = []
    for attempt in range(1, 5):
        raw = G.call_openai(msgs, temperature=1.0 if attempt == 1 else 0.7)
        try:
            sb = json.loads(raw)
        except ValueError:
            last_bad, scripts = ["the reply was not valid JSON"], None
        else:
            last_bad, scripts = problems(sb, number)
            if (sb.get("uncommon_word") or {}).get("word", "").lower() in words:
                last_bad.append("that uncommon word was used in an earlier story; pick a different one.")
            if len(sb.get("parts") or []) != n_parts and not last_bad:
                last_bad.append(f"write exactly {n_parts} parts.")
            if not last_bad and attempt < 4 and os.environ.get("STORY_CRITIC", "1") != "0":
                last_bad = critique(G, sb)
            if not last_bad:
                t = re.sub(rf"^{re.escape(series)}\s*(#\d+)?\s*[:\-]\s*", "", sb["title"].strip(), flags=re.I) or sb["title"].strip()
                names = []
                for sc in scripts:
                    sc["short_title"] = t
                    sc["series_part"]["story"] = f"{series} #{number}: {t}"
                    sc["title"] = f"{series} #{number}: {t} (Part {sc['series_part']['part']}/{n_parts})"
                    sc["youtube"]["title"] = sc["title"][:100]
                    path = SCRIPTS / f"{sc['slug']}.json"
                    path.write_text(json.dumps(sc, indent=1))
                    names.append(path.name)
                with open(QUEUE, "a") as f:
                    f.write("\n".join(names) + "\n")
                log(f"Wrote {n_parts} parts (attempt {attempt}): {', '.join(names)}, queued in order.")
                return names
        log(f"Attempt {attempt} rejected: " + " | ".join(last_bad)[:600])
        msgs += [{"role": "assistant", "content": raw},
                 {"role": "user", "content": "Fix these problems and return the full corrected JSON only:\n- " + "\n- ".join(last_bad)}]
    raise SystemExit("Could not get a valid story after 4 tries. Last problems: " + "; ".join(last_bad))
