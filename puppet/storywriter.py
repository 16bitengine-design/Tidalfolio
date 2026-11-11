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

from . import people as PE
from .storyboard import ITEMS as SB_ITEMS

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
QUEUE = ROOT / "queue-puppet.txt"
DONE = ROOT / "done-puppet.txt"
MIN_LEN, MAX_LEN = 45.0, 60.0
AIM = "aim for 50 to 57 seconds"
SEC_PER_WORD, SCENE_OVERHEAD, END_CARD = 0.55, 1.5, 3.5     # measured on the real narrator; used only when the voice model is absent

SERIES = {"Funny People": "ordinary people in extraordinary little crises: a baker, a boss, a mechanic, a grandmother, a teacher ... pride, rivalry, secrets, misunderstandings"}
LOCKED_GENDER = {"mother": "female", "girl": "female", "grandmother": "female", "father": "male", "boy": "male", "grandfather": "male"}
PERSONA = {"baker": "proud and territorial", "chef": "dramatic and easily offended", "waiter": "polite on top, boiling underneath", "doctor": "calm to the point of being unsettling",
           "nurse": "kind but nobody's fool", "teacher": "patient until she is not", "student": "anxious and over-eager", "mechanic": "gruff but soft-hearted",
           "farmer": "stubborn and dry", "police officer": "by the book and secretly a romantic", "firefighter": "heroic and a little vain", "judge": "solemn and petty",
           "mail carrier": "a born gossip", "taxi driver": "a philosopher with opinions", "shopkeeper": "suspicious of everyone", "barber": "talks too much, knows everything",
           "painter": "dreamy and dramatic", "scientist": "brilliant and absent-minded", "librarian": "quiet and fierce", "gardener": "gentle, with a grudge",
           "builder": "confident and wrong", "fisherman": "a teller of tall tales", "tourist": "lost and loudly cheerful", "boss": "pompous and secretly insecure",
           "office worker": "tired and cunning", "cashier": "has seen everything", "grandmother": "sweet and ruthless", "grandfather": "slow, wise and sly",
           "mother": "calm in public, scheming in private", "father": "proud of his terrible jokes", "boy": "curious and trouble-prone", "girl": "bossy and brilliant",
           "neighbour": "nosy and generous", "stranger": "mysterious and polite"}


def _lead_of(path):
    try:
        d = json.loads(path.read_text())
    except ValueError:
        return None, None
    sp = d.get("series_part")
    lead = d.get("cast_lead") or {}
    if not sp or not lead.get("role"):
        return None, None            # older animal stories have no human lead
    return sp["story"], (lead["role"], lead.get("gender"))


def recent_leads(k=2):
    """The (role, gender) of the lead of each of the last k stories, newest first."""
    seen, out = [], []
    for p in sorted(SCRIPTS.glob("*.json"), reverse=True):
        story, lead = _lead_of(p)
        if story and story not in seen:
            seen.append(story)
            out.append(lead)
            if len(out) == k:
                break
    return out


def choose_lead():
    """Every story gets a different lead role from the story before it (and, when possible, from the one before that), and the gender alternates."""
    recent = recent_leads(2)
    last_roles = [r[0] for r in recent]
    gender = random.choice(["male", "female"])
    if recent and recent[0][1] in ("male", "female"):
        gender = "female" if recent[0][1] == "male" else "male"
    pool = [r for r in PE.ROLES_LIST if r != "stranger" and LOCKED_GENDER.get(r, gender) == gender]
    fresh = [r for r in pool if r not in last_roles] or pool
    return random.choice(fresh), gender, last_roles


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
    return f"""You write short animated fable videos for "tidalfolio", a comedy channel about everyday people. A video is a handful of scenes drawn by code
(bold cartoon style) and told by ONE narrator: a middle-aged man with a warm baritone, a gifted storyteller telling a tale he knows by heart.
You do not write drawing code. You write a STORYBOARD (JSON) and the system draws it.

CHANNEL RULES (all mandatory)
- NOBODY HAS A NAME. People are never given personal names (no Pip, no Mabel, no Tom, no Dr. Smith): the narrator and the characters refer to them only by ROLE, GENDER or PROFESSION ("the baker", "the old woman", "her boss", "the boy", "the tall mechanic", "the one with the umbrella"). In speech a person is addressed as "you", "madam", "boss", "officer", "doctor" or "sir". The only capital letters inside a sentence are "I" and the first word of quoted speech. If two people share a role, tell them apart by what they wear, hold or do.
- Audience: all ages INCLUDING adults. Wit is dry and deadpan, never babyish or cartoonish. No baby talk, no puns on every line.
- THE NARRATOR TELLS THE STORY FROM OUTSIDE IT. He never mentions himself: no "I", "me", "my", "we", "our" in his own words (characters may say them inside quotation marks). Third person, mostly past tense. He never tells the listener what to do or think, gives no advice, no moral, no "remember that". Like a grandfather retelling Tom and Jerry to his grandson, or a teacher telling a war story to a class: vivid, specific, dramatic, never boring.
- SPOKEN WORDS GO IN DOUBLE QUOTATION MARKS ONLY, never single quotes: write \"Show me,\" he said, not 'Show me,' he said. Inside the JSON text, escape each double quote with a backslash. Apostrophes inside words (the baker's shop) are fine.
- STORYTELLING ETIQUETTE: vary pace. Slower for suspense and the emotional beat, brisker for action. A long rolling sentence of build-up, then a short one that lands. Put the key word LAST in a sentence. Use silence before a twist. Rule of three where the third breaks the pattern. At most one rhetorical question. Never explain a joke. Short sentences are spoken slowly and dramatically, so use them for the punchlines.
- COMMON WORDS ONLY: plain everyday English an ordinary 12-year-old knows. EXCEPT exactly ONE uncommon word per story (a real useful word most viewers don't know, e.g. "indolent", "audacious", "meticulous", "reluctant", "frugal"). Use it exactly once, inside a normal sentence, and then simply carry on with the story. NEVER define it, translate it, repeat it, follow it with a synonym, point at it ("a fancy word for", "which means", "that is another word for") or hint that it is special: the viewer will look it up in their own time. The story's events may show what it means, but the narrator never does. Nothing about it is shown on screen. Put it in "uncommon_word": {{"word", "meaning"}} (the meaning is for our records only). Never a name or slang.
- No sound effects exist: never write onomatopoeia like "crash!" in the narration (a visual pop-up word like CRASH is fine). Audio is voice plus music only.
- EVERY AGE: the channel is for everyone from young children to grandparents. No profanity or rude words (a bubble of symbols like #@%! is fine), no gore, no weapons, no real violence or death on screen or in the narration, no sexual or romantic content beyond a friendly hug, nothing frightening beyond mild, brief peril, no cruelty or bullying played as a joke, no drugs or alcohol, no politics or religion. Real feelings are welcome (loss, jealousy, regret, forgiveness) as long as they are told gently. Nobody is ever really hurt: slapstick only.
- STORY ENGINE (a funny video with no story is forgotten): (1) STAKES FIRST: scene 1 states a premise a stranger understands instantly, never scenery or a greeting. (2) ONE PROTAGONIST (known only by role, never by name) who wants something badly and has something to lose. (3) THREE ESCALATING REVERSALS, each flipping what the viewer hopes for. (4) ONE REAL EMOTIONAL BEAT in the middle (loyalty, shame, fear, tenderness) played straight with no joke. (5) A calm, short, haunting LAST LINE that leaves the viewer pondering what it was really about. (6) One SHAREABLE moment so absurd or striking a viewer would show a friend.
- A LESSON FOR HUMANS, but NEVER stated or hinted at in the video: the story shows through what the people do and what it costs them. Write the lesson as ONE plain sentence in "lesson" (max 25 words) for the record only. People rarely go wrong because they are fools: set "cause" to why the protagonist makes the key choice: "forgot" (knew the value, lost it under pressure), "believed" (sincerely thought it was right), or "no_options" (every path cost something). Show that cause in their own reasoning so viewers understand the choice from the inside. Never say the cause aloud.
- NOT PLAIN: a plain story is a summary. Every scene must contain something SPECIFIC and SURPRISING that could only happen in this story (an odd rule, an exact absurd number, a strange object, a character's petty obsession), never generic lines like 'they were happy' or 'it was a beautiful day'. In at least half the scenes a character SPEAKS: quote one short, characterful line in the narration (\"You call that a plan?\" hissed the baker.) so the cast has voices and the narrator is not just describing. Give the protagonist one memorable quirk, plant one odd detail early that pays off late, and make the final reversal change how the viewer understands the first scene.
- HUMOUR: deadpan gravity about trivial stakes; specific absurd numbers and rules; understatement after big action; one planted odd detail that returns later raising a question.

HUMAN CRAFT (what separates a story people share from one they scroll past; mandatory)
- WRITE LIKE SOMEONE WHO WITNESSED IT, NOT LIKE A MACHINE SUMMARISING. Build every scene from concrete, physical, slightly odd details only a witness would notice (the exact thing on the table, a chipped mug, a number too precise to be invented, a habit). A reader should think "that is so true" at least twice per part.
- SUBTEXT: people almost never say what they feel. Show the feeling through what they do with their hands, what they avoid saying, what they change the subject to. The narrator never names an emotion he can show (not "she felt guilty": she folded the receipt smaller and smaller).
- WANT vs NEED: the protagonist wants one visible thing and needs another they cannot see. Their flaw is why they cannot get it. Their choices, not coincidences, drive every turn, and each choice costs something.
- EMOTIONAL TOUCH: include one moment played completely straight that a viewer would feel in the chest: a small act of loyalty, shame, tenderness or loss, carried by an object or a gesture (a coat put over a sleeping man, a chair kept empty). No music-swell language. Make us care about the character BEFORE we hurt or embarrass them.
- ORIGINALITY: begin from a real, small, recognisable human situation and give it a twist the viewer has not seen. Avoid stock premises (a lost wallet returned, a mean boss gets his comeuppance, a secret recipe, mistaken for a celebrity, a magic object, it was all a dream). Before writing, ask: could this be any other channel's story? If yes, change the premise, the setting or the cause of the conflict.
- SET-UP AND PAYOFF: plant at least two small things early (an object, a rule, a sentence) and pay both off late in a way that recasts them. Dramatic irony: let the viewer know something the character does not, then make them wait for it to land. Use a ticking clock or a deadline.
- RETENTION: end EVERY scene on a small open question (something unfinished, unexplained or about to go wrong). Change something visible (who is on screen, where they stand, the camera, the gesture) every scene. Never two scenes in a row with the same rhythm.
- A RESOLUTION THAT IS NOT TIDY: the ending lands emotionally and answers the main question, but leaves one thing slightly unresolved or bittersweet. Let the final image echo the first scene with one thing changed.
- SOUND HUMAN: vary sentence length unevenly (a long one, then three words). Use contractions in dialogue. Let characters interrupt, trail off, say the wrong thing, be petty and unfair. Humour from specific personalities and real awkwardness. A narrator with a point of view and a dry opinion about the people, never a neutral reporter.
- NEVER WRITE THE TELL-TALE PATTERNS OF MACHINE PROSE: "little did he know", "in that moment", "a testament to", "time stood still", "couldn't help but", "heart pounded", "let out a breath", "the air was thick", "a mix of X and Y", "tapestry", "symphony", "dance of", "whispered secrets", "unbeknownst", "suddenly", "it was not X, it was Y" constructions, lists of three adjectives, em dashes, stock openings ("It was a [adjective] day", "Once upon a time"), and any closing line that explains the story.

THE NARRATOR AND THE PEOPLE (this is what makes it feel told by a person, not generated)
- The narrator is a dry, affectionate neighbour telling this over the fence: he has opinions about these people ("out of spite", "feeling like a detective", "mostly out of habit"), understates the big moments and is quietly funny about the small ones. He may speak to the viewer as "you" now and then. He is never a neutral reporter and never explains the joke.
- Do not make every scene a tidy fact followed by a punchline. Let some scenes simply breathe: a look, a silence, a small thing done badly. Vary the shape of the scenes.
- Dialogue is overheard, not announced. People answer a different question, trail off, repeat themselves, say less than they mean, and never explain their feelings or their history in full sentences (a line like "My husband baked here for forty years" is exposition: give the same fact as a habit, an object or a half-sentence instead).
- SPOKEN, NOT WRITTEN: write the narration the way a person would say it out loud. Fragments are fine ("Rude." "Politely." "A small one."). Let a sentence start, change its mind or trail off ("He had... views."). Repeat a word when someone is rattled ("Forty-one. Forty-one."). Drop in a short aside or a dry afterthought ("honestly", "mostly out of habit", "which was the rude part"). Do not make every sentence a complete, balanced, equal-length statement.
- PEOPLE REACT ON THE WORD. In every scene with two or more people, give each person "beats": a change of mood, gesture and glance on the exact words that cause it (the listener flinches on "I'm not saying it was you", the speaker looks away on the hard part, someone shrugs on the joke). Use "speaks": true with "from"/"to" for whoever is talking, so their mouth moves while their hands do something else. Use "look": at|away|down|up. A person must not make the same gesture in three scenes in a row, and nobody simply stands still while something happens to them.
- Give each person one small habit or weakness that shows up more than once (counting twice, looking at the sky, never lending anything). Habits make people feel real.

CREATIVE DIRECTION (the Tidal Folio master brief; follow it, within the channel rules above and the stage limits below)
- Substance beyond funny moments: the people live out recognizable human situations: jealousy, betrayal, greed, envy, deception; love, friendship, loyalty, trust, forgiveness; competition, pride, ambition, revenge; injustice, selfishness, manipulation; kindness, sacrifice, unexpected generosity; misunderstandings, secrets, embarrassment, shocking revelations. NEVER explain the underlying message or spell out the comparison; the audience works it out.
- Dramatic shape, in this order: an IMMEDIATE HOOK (the first seconds show something intriguing: a shocking discovery, a suspicious encounter, a betrayal, a confrontation about to erupt, an embarrassing situation; no introductions, no scenery); the CONFLICT made clear at once (who wants what, what stands in the way, why it matters); rising ANTICIPATION (suspicious glances, deliberate pauses, a character noticing what they should not, near discoveries, interrupted confrontations, hidden motives, small details that matter later); ESCALATION (each development more complicated, more embarrassing, more emotional, funnier or more dangerous; reversals, misunderstandings, failed plans, interruptions; never predictable or repetitive; every scene adds new information, raises the stakes or changes what the viewer understands); a PAYOFF that rewards the anticipation and feels earned (a betrayal, a clever reversal, a public embarrassment, a secret exposed, an unexpected kindness, a character caught in their own scheme, an ironic consequence, a surprising reconciliation); a lasting final image or line, with a small unanswered question.
- Comedy comes from character and situation, not random jokes: perfectly timed reactions, awkward silence, exaggerated faces, unexpected confidence, misunderstandings, clever deception, irony, role reversals, physical comedy, contrasting personalities. Balance it with real emotion: a story can be hilarious and still carry betrayal, disappointment, compassion or justice. No childish humour, no meaningless chaos, no predictable jokes.
- Characters: each has a distinct personality, a clear motivation and a particular way of reacting to conflict, shown through mood and action. Keep them consistent and appealing.
- Staging (the storyboard must leave nothing to interpretation): decide for every scene who stands where ("at"), which way they face ("face"), who is looking at whom (two characters in a confrontation face each other), their mood and their movement. Avoid long static scenes: change the camera or the action every scene.
- Silence before revelations and punchlines (use "silence_before").
- Before you answer, silently check: does the opening create curiosity? is the conflict easy to understand? does every scene give a reason to keep watching? does tension rise rather than stay flat? is there at least one unexpected development? is the comedy situation-driven? are the characters believable? is the climax satisfying and memorable? does the story keep its deeper meaning without explaining it? If any answer is no, rewrite that part first. Story quality beats spectacle, comedy beats noise, essence beats a shocking twist.

STORY IN PARTS: every story is told as {parts_text} consecutive videos (Part 1, Part 2 ...), published one after another. Write ALL parts now, in "parts": [{{"scenes": [...]}}, ...].
- The parts play one right after another, so the viewer should barely notice where one ends and the next begins. Part 1 opens with the hook. Every later part carries on from the exact moment the previous part stopped: NO recap, NO re-introduction of the characters or setting, NO "previously" and NO announcement that a new part has started. Each part still has its own small reversal so it never drags.
- Every part EXCEPT the last ends mid-story on a line that pulls straight into the next scene (a reveal, a worse problem, a question), told like any other line of the story: never "to be continued", never "in the next part", never an instruction.
- COLD OPEN: scene 1 of every part opens on the most striking moment of that part, already happening: the problem, the accusation, the spill, the gasp. Never a quiet scene-setting line ("It was a sunny morning", "There was a baker ...", "Once ..."); say who and what is wrong in the first sentence, in at most 12 words. The characters are already in place (nobody walks in during the first seconds), at least one has a strong mood (never neutral) and a gesture that matches the words, and there is a popup within the first two seconds. If the most striking moment comes later in the part, open on a short glimpse of it, then let the story rewind to its natural order.
- Part 1 opens with the stakes; the last part holds the emotional resolution and the haunting last line. The one uncommon word appears exactly once in the WHOLE story. Characters, setting and objects stay consistent across parts.

LENGTH: EACH PART (not the whole story) must run {MIN_LEN:.0f} to {MAX_LEN:.0f} seconds, {AIM}. The storyteller speaks slowly and steadily (about 0.55 s per word, never rushed) and each scene adds about 1.5 s of pauses, so write {n_lo} to {n_hi} scenes of 9 to 14 words each per part (roughly 68 to 82 words per part). Open on the hook at once. No filler scene. Spend the few words on specific, surprising details and on what the characters say, never on scenery.
- NARRATION MUST BE EASY TO SPEAK: a voice reads it aloud. Use only ordinary words that are easy to pronounce (the one uncommon word aside), no personal names at all (people are known by role), numbers written as words ("forty-two"), no digits, no abbreviations, no symbols, no all-capital words in the narration, no invented words or unusual spellings. Keep sentences short to medium (at most about 16 words); put a comma at each natural pause.

TONE (the viewer must FEEL the tone of every scene within one second, with the sound on or off): give EVERY scene a "tone". playful = jokes, mischief, scheming (bouncy music, bright colours). joyful = triumph, celebration, a win (golden light, rising music, the narrator lifts). tense = danger, a plan going wrong, an argument, a chase (dark cold colours, low ticking music, a shaky camera). sad = loss, shame, being left out, a broken promise (grey-blue colours, slow falling notes, the narrator softer and lower). eerie = mystery, dread, something not right (green-teal mist, a low hum, sparse notes). tender = love, forgiveness, loyalty, a kind surprise (warm glow, soft music). calm = rest, quiet, scene-setting (use for at most two scenes in a part). The system turns the tone into colour, light, music, camera and the narrator's voice, so the tone must match the narration words and the faces: tense = scared, angry or shocked actors; sad = sad actors; playful and joyful = happy or smug actors. Change the tone at least twice in every part, as the story turns, and make the tone obvious in the words themselves (short, clipped sentences for tense; long, slow ones for sad; bouncy, surprising ones for playful). Dark tones (tense, sad, eerie) belong to world storm, night or dusk; joyful belongs to day, dawn or sunset. The FIRST scene of the story must already show a clear tone, never calm.

THE STAGE (this is all that can be drawn, so write for it)
- Cast: 1 to 4 PEOPLE, the PROTAGONIST FIRST, each described by ROLE and never by name. Each cast entry: "role" (one of: {', '.join(PE.ROLES_LIST)}), "gender" ("male"|"female"), "age" ("child"|"adult"|"elder"), optional "skin" (light|fair|tan|brown|dark), optional "hair" (black|brown|blonde|red|grey|white), optional "extras" (a list from glasses|beard|mustache|bun|bald). The cast KEY is a short role word ("baker", "boss", "granny"), never a name. Make the cast look different from each other (different skin, hair, age, gender). Give every character a clear personality that drives the plot (a baker is proud and territorial, a boss pompous and secretly insecure, a grandmother sweet and ruthless, a mechanic gruff but soft-hearted, a student anxious and over-eager) and let the story break or test that personality.
- Each scene: "world" (dawn|day|dusk|storm|night|sunset: the time of day and weather, seen outdoors or through the window) and "stage" (the SETTING: street|park|kitchen|shop|office|classroom|home). Change the setting only when the story moves the people somewhere new; match it to the roles (a baker in a kitchen or shop, a teacher in a classroom, a boss in an office).
- "camera": hold|push_in|pull_back|pan_right|pan_left (optional: the system leans in on tense scenes and drifts away on sad ones). "tone": playful|joyful|tense|sad|eerie|tender|calm (see TONE). Optional "silence_before": a few words of the narration; the music cuts out and the picture freezes just before them (use on at most 2 scenes, for the biggest reveal).
- "actors": who is on screen, 1 to 3 people at once. "at": ground_left|ground_mid|ground_right (each person a different spot). "face": left|right (optional; by default people face each other). "mood": neutral|sleepy|happy|angry|scared|shocked|smug|sad|dizzy. "action": stand|talk|hop|flap|point|shrug|cheer|facepalm|think|laugh|tremble|offer|hold|clasp|wrap|place|reach|beckon|hugself|wipe|cower|wave|hips ("talk": gestures while the mouth moves; "hop": a jump for joy or shock; "flap": both arms waving in panic; "point": arm out at something or someone; "shrug": helpless or innocent; "cheer": both arms up in triumph; "facepalm": hand on face in embarrassment; "think": hand on chin; "laugh": holding the belly; "tremble": shaking with fear or cold; "offer": holds something out to someone; "hold": clutches something to the chest; "clasp": hands together, worried or tender; "wrap": arms round someone or something; "place": sets something down; "reach": reaches for something; "beckon": calls someone over; "hugself": arms folded over the chest, cold, wet or shy; "wipe": hand to the eye or brow; "cower": shrinks back; "wave": greets; "hips": hands on hips, cross or bossy). Choose the gesture that fits what the person feels at that exact moment and change it from scene to scene: a person never stands still while something happens to them. "talk" needs "from" and "to" (words in the narration for when they speak) or give nothing. "beats": [{{"at": words, "mood": ..., "action": ..., "look": at|away|down|up}}] changes this person's mood, gesture and glance on those exact words (words copied from the narration); "speaks": true makes the mouth move between "from" and "to" whatever the gesture; "go": a spot (ground_left|ground_mid|ground_right) this person WALKS to between "from" and "to" (words); use it so people cross the room, approach, retreat, chase, pace, instead of standing where they began. "enter": words in the narration at which this person walks in from off-screen; "exit": words at which they walk off. "drape": {{"at": words, "item": "towel"|"blanket"}} when someone puts a towel or blanket round THIS person (their shoulders get covered from those words on: do this whenever the narration says wrapped, covered or draped; the giver also gets action "wrap" and "carry": "towel" with "carry_from"/"carry_to" words while they hold it, and walks to the receiver with "go"); "carry": an item in their hand (each role already holds its usual tool; "none" empties the hands): one of {', '.join(SB_ITEMS)}.
- "popups": comic speech bubbles ("kind": "bubble", a short spoken line or reaction) and impact words ("kind": "burst", e.g. SPLAT, MINE, WHAT). "text" 1 to 4 words, "at": words in the narration when it pops, "near": which actor it belongs to. Use them in at least half the scenes: they are the punctuation of the jokes.
- "fx": [{{"kind": "puff"|"sparkle"|"speed", "at": words, "near": actor}}]: a dust cloud for a fall or a crash, a sparkle for a lucky moment, speed streaks for a dash.
- EVERY phrase you give ("from", "to", "enter", "exit", "at", "silence_before") must be copied EXACTLY (same capitals, same punctuation) from THAT scene's narration, a span of 2 to 5 words. Characters can only exist on screen if listed in "actors" of that scene. Keep a person in the same spot while nothing moves them; change spots only when the narration says so.
- VARIETY (the channel must never feel like one template repeated): each story needs its own premise and plot shape (a heist, a rivalry, a rescue, a rumour, a bet, a misunderstanding, a trade that goes wrong, a contest, a secret, a prank that backfires, a visitor who changes everything ...), its own lead character, its own time of day and weather, and its own opening line. Do not start two stories the same way. Titles and the first sentence of the YouTube description should say plainly what the story is about, with the hook in the first 5 words.
- Ending: the last part ends on its haunting last line. The system adds a plain end screen after the final part only, so never write a sign-off, a part announcement or a call to follow or subscribe in any narration.

Reply with ONE JSON object, exactly this shape:
{{"title": "Episode title (no series prefix)", "lesson": "...", "cause": "forgot|believed|no_options",
 "uncommon_word": {{"word": "...", "meaning": "..."}},  "cast": {{"baker": {{"role": "baker", "gender": "female", "age": "adult", "skin": "tan", "hair": "black"}}, "boss": {{"role": "boss", "gender": "male", "age": "adult", "skin": "light", "hair": "grey", "extras": ["glasses"]}}}},
 "parts": [{{"thumbnail_scene": 2, "thumbnail_hook": "1-3 word tease in capitals, e.g. WHO TOOK IT?", "scenes": [{{"narration": "...", "world": "dawn", "stage": "street", "camera": "push_in", "tone": "playful",
   "actors": [{{"who": "baker", "at": "ground_mid", "mood": "smug", "action": "talk", "from": "words", "to": "words"}}],
   "popups": [{{"text": "MINE.", "kind": "burst", "at": "words", "near": "baker"}}], "fx": []}}]}}],
 "youtube": {{"description": "2-4 sentences: a teaser for the whole story (no moral, no part numbers)", "tags": ["8-12 tags"], "pinned_comment": "a question that makes viewers think of their own life"}},
 "tiktok": {{"caption": "<=140 chars hook", "hashtags": ["#a", "#b", "#c", "#d", "#e"]}}}}"""


CRITIC_PROMPT = """You are a ruthless story editor for Tidal Folio, a deadpan comedy channel about everyday people. You get a story told in parts (the narration of every scene).
Score it 1 to 5 on each question, being honest (a 3 is acceptable, 1 or 2 means it must be rewritten):
q1 Does the opening immediately create curiosity? q2 Is the central conflict easy to understand? q3 Does every scene give a reason to keep watching?
q4 Does tension rise rather than stay flat? q5 Are there unexpected developments? q6 Is the comedy genuinely funny and situation-driven (not random or childish)?
q7 Are the characters emotionally believable? q8 Is the climax satisfying and earned? q9 Does it keep a deeper meaning WITHOUT explaining it (no moral, no advice)?
q10 Does every part except the last END at a moment of ESCALATION (a reveal, reversal or new danger with the consequence unseen) so that a viewer is desperate to watch the next part? Score 1 or 2 if any part ends on a joke, a reaction, a calm moment or a resolved question, and name that part in problems.
q11 ORIGINALITY: is the premise fresh, with at least two details a viewer has never seen in another story? Score 1 or 2 if it could be any channel's story or leans on a stock premise.
q12 HUMAN VOICE: does it read as told by a real person who witnessed it (specific, odd, uneven rhythm, a point of view), or as smooth machine prose (generic detail, tidy triads, stock phrases, every sentence the same length, feelings named instead of shown)? Score 1 or 2 if it reads as machine prose.
q13 EMOTIONAL TOUCH: is there at least one moment that would genuinely move a viewer, carried by a gesture or an object, with a character we care about before they are hurt or embarrassed? Score 1 or 2 if the feeling is only announced.
q14 SET-UP AND PAYOFF: are at least two early details paid off late in a way that recasts them, with the protagonist's own choices driving the plot? Score 1 or 2 if events are just coincidences.
q15 SHAREABILITY: would a viewer send this to a friend or retell it at dinner? Is there one line, image or twist people would quote? Score 1 or 2 if it is pleasant but forgettable.
q16 HOOK: would a stranger scrolling past stop in the first 3 seconds of part 1? Score 1 or 2 if the opening is set-up, weather or introductions.
Reply with ONE JSON object: {"scores": {"q1": 4, ...}, "problems": ["specific, actionable fixes naming the part and scene, only for scores of 1 or 2, max 5"]}"""


MIN_AVG = float(os.environ.get("STORY_MIN_SCORE", "3.9"))      # the pass mark: the editor's average over all questions must reach this
STRICT = ("q10", "q11", "q12", "q13", "q15", "q16")            # endings, originality, voice, heart, shareability, hook: a 3 on any of these is a rewrite


class StoryRejected(Exception):
    """The story is not good enough to post, even after rewrites: it is dropped and a new one is written."""


def critique_scored(G, sb):
    """Second AI pass: an editor scores the story. Returns (problems, average score); problems empty = approved. average is None if the editor did not answer."""
    text = "\n".join(f"PART {pi}:\n" + "\n".join(f"  {n}. {sc['narration']}" for n, sc in enumerate(part["scenes"], 1))
                     for pi, part in enumerate(sb["parts"], 1))
    try:
        r = json.loads(G.call_openai([{"role": "system", "content": CRITIC_PROMPT}, {"role": "user", "content": f"Title: {sb.get('title')}\n{text}"}], 0.3))
    except (ValueError, SystemExit):
        return [], None                         # the editor is a bonus: never block a story because it failed to answer
    scores = r.get("scores") or {}
    nums = [v for v in scores.values() if isinstance(v, (int, float))]
    avg = sum(nums) / len(nums) if nums else None
    low = [k for k, v in scores.items() if isinstance(v, (int, float)) and v <= (3 if k in STRICT else 2)]
    why = r.get("problems") or ["make it more surprising, more tense and funnier"]
    if low:
        return [f"an editor rejected the story (weak: {', '.join(sorted(low))}): " + "; ".join(why)], avg
    if avg is not None and avg < MIN_AVG:
        return [f"an editor found the story below the pass mark (average {avg:.1f}, needs {MIN_AVG}): " + "; ".join(why)], avg
    return [], avg


def critique(G, sb):
    return critique_scored(G, sb)[0]


PREMISE_PROMPT = """You are the head of story development for a deadpan comedy channel about everyday people. Pitch %d completely different story premises for one %d-part story.
Each must be specific and odd, not a stock situation (no lost wallets, mixed-up coffee orders or surprise parties). Each needs a first-three-seconds hook, one moment that would genuinely move a viewer carried by an object or a gesture, one early detail that pays off late, and an ending a viewer would retell.
Reply with ONE JSON object: {"premises": [{"logline": "two sentences", "hook": "what the first line shows", "heart": "the moving moment", "payoff": "the early detail and how it pays off"}]}"""

JUDGE_PROMPT = """You are a ruthless producer choosing which story premise to make. Score EVERY premise 1 to 5 on: hook (a stranger stops scrolling), fresh (not seen on any other channel), heart (a moment that moves you), share (someone would retell it to a friend), payoff (the ending recasts an early detail).
Be harsh: most premises deserve 2 or 3. Reply with ONE JSON object: {"scores": [{"i": 0, "hook": 3, "fresh": 2, "heart": 4, "share": 3, "payoff": 3}]} with one entry per premise, in order."""


def pick_premise(G, n_parts, brief_hint, log=print):
    """Pitch several premises, have a second pass score them, return the text of the winner (None = could not, let the writer invent one)."""
    n = int(os.environ.get("STORY_CANDIDATES", "5"))
    if n < 2:
        return None
    try:
        cands = json.loads(G.call_openai([{"role": "system", "content": PREMISE_PROMPT % (n, n_parts)},
                                          {"role": "user", "content": brief_hint}], 1.0)).get("premises") or []
        cands = [c for c in cands if isinstance(c, dict) and c.get("logline")]
        if len(cands) < 2:
            return None
        listing = "\n".join(f"{i}. {c['logline']} | hook: {c.get('hook', '')} | heart: {c.get('heart', '')} | payoff: {c.get('payoff', '')}" for i, c in enumerate(cands))
        rows = json.loads(G.call_openai([{"role": "system", "content": JUDGE_PROMPT}, {"role": "user", "content": listing}], 0.2)).get("scores") or []
    except (ValueError, SystemExit, AttributeError):
        return None                                             # a bonus step: never block a story because it failed
    best, best_total = None, -1
    for pos, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        i = row.get("i", pos)
        if not isinstance(i, int) or not 0 <= i < len(cands):
            continue
        vals = [row.get(k) for k in ("hook", "fresh", "heart", "share", "payoff")]
        if not all(isinstance(v, (int, float)) for v in vals):
            continue
        total = sum(vals) + (row.get("fresh") or 0) + (row.get("share") or 0)     # fresh and share count double: they decide whether people pass it on
        if total > best_total:
            best, best_total = i, total
    if best is None:
        return None
    c = cands[best]
    log(f"Premises pitched: {len(cands)}; chose #{best} ({best_total} of 35): {c['logline'][:160]}")
    return (f"{c['logline']} OPENING HOOK: {c.get('hook', '')} MOVING MOMENT: {c.get('heart', '')} PAYOFF: {c.get('payoff', '')}")


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
 "cast": {"baker": {"role": "baker", "gender": "female", "age": "adult", "skin": "tan", "hair": "black"}, "boss": {"role": "boss", "gender": "male", "age": "adult", "extras": ["glasses"]}},
 "tone": "the story's overall tone in 3 to 8 words, e.g. 'mischievous comedy that turns tender at the end'",
 "tone_arc": [EXACTLY %d strings, one per part: the tones of that part in order, from playful|joyful|tense|sad|eerie|tender|calm, e.g. "playful, tense, sad"],
 "planted_detail": "one odd, specific detail shown early (an object, a rule, a habit) that pays off in the last part",
 "twist": "the final reversal that changes how the viewer understands the first scene",
 "outline": [EXACTLY %d strings, one per part: what happens in that part (told by role, never by name; with who SAYS what, one quotable line each) and the line it stops on. EVERY PART EXCEPT THE LAST must stop at the moment things ESCALATE: a reveal, a reversal, a new danger or a surprising arrival that raises a question only the next part can answer. Write it at the end of the string as "ENDS ON: <that moment>". Never stop on a joke, a reaction shot or a calm moment],
 "youtube": {"description": "2-4 sentences: a teaser for the whole story (no moral, no part numbers)", "tags": ["8-12 tags"], "pinned_comment": "a question that makes viewers think of their own life"},
 "tiktok": {"caption": "<=140 chars hook", "hashtags": ["#a", "#b", "#c", "#d", "#e"]}}"""

PART_SHAPE = ('Reply with ONE JSON object: {"thumbnail_scene": 2, "thumbnail_hook": "a 1 to 3 word tease in capitals for the thumbnail, a question or a gasp, never a spoiler", "scenes": [ 6 to 8 scenes, each in exactly the scene format given in the instructions ]}. '
              "Use the cast keys exactly as planned. The timing phrases ('from', 'to', 'enter', 'exit', 'at', 'silence_before') must be copied EXACTLY from the NARRATOR's words in that same scene, "
              "never from what a character says in a speech bubble; if you are not sure, leave them out. 'mood' must be one of neutral, sleepy, happy, angry, scared, sad, shocked, smug, dizzy; "
              "'action' one of stand, talk, hop, flap, point, shrug, cheer, facepalm, think, laugh, tremble, offer, hold, clasp, wrap, place, reach, beckon, hugself, wipe, cower, wave, hips: choose the one that matches what that person is DOING at that moment in the narration (holds something out = offer, wraps a towel round someone = wrap, sets something down = place, cold or wet = hugself ...); give listeners a calm action such as clasp or hips ('go' optional: a ground spot to walk to).")


WEAK_OPENER = re.compile(r"^(it was|there was|there were|once|one day|one morning|in a |on a |every |long ago|the sun|morning)", re.I)


def _part_rules(k, n, word, uw_part, bible=None):
    role = ("It opens on the hook at once." if k == 1 else
            f"It carries on from the exact moment part {k - 1} stopped: no recap, no re-introduction of the characters or the setting, no announcement that a new part has started. "
            f"A viewer must not be able to tell where part {k - 1} ended.")
    role += (f" THE ENDING OF THIS PART IS A CLIFFHANGER: the last two scenes must ESCALATE, so the viewer is dying to know what happens next. "
             f"End at the instant of a reveal, a reversal, a new danger or a surprising arrival, with the consequence still unseen and the main question still open. "
             f"The last scene needs a strong mood (never neutral) or a popup, and its narration is one short, sharp line that stops BEFORE the answer. "
             f"Never end on a punchline, a joke, a calm moment, a character merely reacting (eyes widened, looked surprised) or a resolved question, and never say 'to be continued', 'find out' or 'next part'. "
             f"Part {k + 1} must open by dealing with exactly this moment." if k < n else
             " It holds the emotional resolution and the haunting last line.")
    w = (f'Use the uncommon word "{word}" exactly once in this part.' if k == uw_part else f'Do not use the uncommon word "{word}" in this part.')
    extra = ""
    if bible:
        if k == 1:
            extra = f" Plant this detail casually, as if it were nothing: {bible['planted_detail']}"
        if k == n:
            extra += f" Pay off the planted detail ({bible['planted_detail']}) and land the twist: {bible['twist']}"
    if bible and bible.get("tone"):
        arc = bible.get("tone_arc") or []
        extra += (f" The story's tone: {bible['tone']}." + (f" This part's planned tones, in order: {arc[k - 1]}." if len(arc) >= k else "")
                  + " Make each scene's tone unmistakable in its words, faces, world and \"tone\" field.")
    return f"{role} {w}{extra} Make it vivid: a specific surprising detail in every scene, and a short quoted line of speech in at least half of them."


def _bible_problems(b, n, used_words, lead=None):
    from . import storyboard as SB
    if not isinstance(b, dict):
        return ["the reply must be one JSON object."]
    bad = []
    cast = b.get("cast")
    if not isinstance(cast, dict) or not 1 <= len(cast) <= 4:
        bad.append("'cast' must be an object with 1 to 4 characters.")
    else:
        for key, c in cast.items():
            if not isinstance(c, dict) or not PE.norm_role(c.get("role") or key):
                bad.append(f"cast '{key}': needs a \"role\" that is one of {PE.ROLES_LIST} (people are described by role, never by name).")
        SB.fix_cast(cast)
    if lead and isinstance(cast, dict) and cast:
        first = next(iter(cast.values()))
        if not (isinstance(first, dict) and PE.norm_role(first.get("role") or "") == lead):
            bad.append(f"the FIRST character in 'cast' is the protagonist and must be a {lead} (\"role\": \"{lead}\").")
    for k_ in ("planted_detail", "twist"):
        if not isinstance(b.get(k_), str) or len(b[k_].split()) < 4:
            bad.append(f"'{k_}' must be a specific sentence.")
    if not isinstance(b.get("tone"), str) or len(b["tone"].split()) < 2:
        bad.append("'tone' must say the story's overall tone in 3 to 8 words.")
    arc = b.get("tone_arc")
    if not (isinstance(arc, list) and len(arc) == n and all(isinstance(x, str) and x.strip() for x in arc)):
        bad.append(f"'tone_arc' must be a list of exactly {n} strings, one per part (the tones of that part in order, e.g. \"playful, tense, sad\").")
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


STAGE_FIX = {"bakery": "shop", "store": "shop", "market": "shop", "restaurant": "kitchen", "cafe": "kitchen", "diner": "kitchen", "house": "home", "apartment": "home",
             "living room": "home", "bedroom": "home", "school": "classroom", "garden": "park", "playground": "park", "road": "street", "city": "street", "town": "street",
             "outside": "street", "workshop": "shop", "garage": "shop", "hospital": "office", "courtroom": "office", "library": "classroom"}


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
        if cast and any(c.get("species") == "human" for c in cast.values() if isinstance(c, dict)):
            st = str(sc.get("stage", "")).lower()
            sc["stage"] = st if st in SB.HUMAN_STAGES else STAGE_FIX.get(st, "street")
            acts = [a for a in (sc.get("actors") or []) if isinstance(a, dict)][:3]
            free = list(SB.HSLOTS)
            for a in acts:                                  # three spots only, one person in each
                at = a.get("at") if a.get("at") in free else (free[1] if free[1:] and "ground_mid" in free else free[0])
                free.remove(at)
                a["at"] = at
                if a.get("carry") and a["carry"] not in SB.ITEMS:
                    a.pop("carry")
            if isinstance(sc.get("actors"), list):
                sc["actors"] = acts
        sc["tone"] = SB.tone_of(sc)                   # synonyms ("funny", "scary") are mapped; an old "music" key still works
        sc.pop("music", None)
        if sc["tone"] in ("tense", "sad", "eerie") and sc.get("world") in ("day", "dawn", "sunset"):
            sc["world"] = {"tense": "storm", "sad": "dusk", "eerie": "night"}[sc["tone"]]      # dark tones get a dark sky
        elif sc["tone"] == "joyful" and sc.get("world") in ("storm", "night"):
            sc["world"] = "day"
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


META_ENDING = re.compile(r"to be continued|find out|stay tuned|next (part|time|episode)|in part \d|keep watching|what happens next", re.I)


META_MORAL = re.compile(r"the (moral|lesson)\b|moral of|lesson (is|was)|teaches us|taught (him|her|them|us) (that|a lesson)|learn(ed|t)? (his|her|their|a|the) (lesson|mistake)|\bremember,? (that|this)\b|never forget|\bgoes to show\b", re.I)


META_AI = re.compile(r"little did|in that moment|a testament to|time (stood|seemed to stand) still|couldn'?t help but|heart (pounded|raced|skipped)|let out a breath|the air (was|grew) thick|a mix of|tapestry|symphony|\bdance of\b|whispered secrets|unbeknownst|\bsuddenly\b|shivers? (ran )?down|once upon a time|it was a (\w+ ){0,2}(day|night|morning|evening)\b|\u2014|\u2013|\bnot (just |only )?\w+( \w+)?, but\b", re.I)


def _part_problems(part, cast, k, word, uw_part, n=None):
    from . import storyboard as SB
    if not isinstance(part, dict):
        return [f"part {k}: the reply must be one JSON object with 'scenes'."]
    scenes = part.get("scenes")
    if isinstance(scenes, list) and all(isinstance(x, dict) for x in scenes):
        _sanitize(part, cast)
    if isinstance(scenes, list) and not all(isinstance(x, dict) for x in scenes):
        return [f"part {k}, every scene must be a JSON object."]
    bad = SB._check_scenes(scenes, cast, f"part {k}, ")
    if isinstance(scenes, list) and scenes and all(isinstance(x, dict) for x in scenes):
        tones = [SB.tone_of(x) for x in scenes]
        if len(set(tones)) < 2 or sum(t != "calm" for t in tones) < 3:
            bad.append(f"part {k}: the tone must be clear and must change as the story turns: use at least two different tones, and at most two calm scenes (tones now: {', '.join(tones)}).")
        first = scenes[0]
        fa = [a for a in first.get("actors") or [] if isinstance(a, dict)]
        if not first.get("popups") or not any(a.get("mood", "neutral") != "neutral" for a in fa):
            bad.append(f"part {k}, scene 1: open on the most striking moment: give at least one actor a strong mood (not neutral) and add a popup that pops in the first two seconds.")
        if any(a.get("go") or a.get("enter") for a in fa):
            bad.append(f"part {k}, scene 1: nobody walks in during the opening: place everyone where they start, and move them in a later scene.")
        n1 = str(first.get("narration", "")).strip()
        sent1 = re.split(r"(?<=[.!?])\s", n1)[0] if n1 else ""
        if len(sent1.split()) > 12 or WEAK_OPENER.match(n1):
            bad.append(f"part {k}, scene 1: the first sentence must be at most 12 words and start on the action or the problem, not scene-setting (no 'It was ...', 'There was ...', 'Once ...', 'One day ...'): say who and what is wrong at once.")
        if k == 1 and tones[0] == "calm":
            bad.append("part 1, scene 1: the opening scene must show a clear tone (playful, tense, eerie ...), never calm.")
        if n and k < n:                             # a part that is not the last must stop on an escalation the viewer can SEE and hear
            last = scenes[-1]
            hooked = bool(last.get("popups")) or any(a.get("mood", "neutral") != "neutral" for a in last.get("actors") or [] if isinstance(a, dict))
            if not hooked:
                bad.append(f"part {k}, last scene: this part must end on a cliffhanger the viewer can see: give an actor a strong mood (not neutral) or add a popup, and end on the moment things escalate.")
            if SB.tone_of(last) == "calm":
                bad.append(f"part {k}, last scene: a cliffhanger cannot be calm: use a tense, eerie or shocking tone and stop on the escalation.")
            mm = META_ENDING.search(str(last.get("narration", "")))
            if mm:
                bad.append(f"part {k}, last scene: do not announce the next part ('{mm.group(0)}'). Stop on the escalating moment itself and let the curiosity do the work.")
    text = " ".join(str(x.get("narration", "")) for x in (scenes if isinstance(scenes, list) else []))
    runs = {}
    for sc_ in scenes if isinstance(scenes, list) else []:
        for a_ in sc_.get("actors") or []:
            if a_.get("beats"):
                runs[a_.get("who")] = 0
                continue
            k_ = (a_.get("who"), a_.get("action", "stand"))
            runs[k_[0]] = runs.get(k_[0], 0) + 1 if runs.get(("last", k_[0])) == k_[1] else 1
            runs[("last", k_[0])] = k_[1]
            if runs[k_[0]] >= 3 and k_[1] != "stand":
                bad.append(f"part {k}: {a_.get('who')} makes the same gesture ({k_[1]}) in three scenes in a row. Change it, or add beats.")
    ai = META_AI.search(text)
    if ai:                                          # machine-prose tells make a story feel generated: ask for plain, specific, human wording
        bad.append(f"part {k}: '{ai.group(0)}' is a stock phrase that reads as machine-written. Rewrite that sentence with a concrete, specific detail only a witness would notice, in plain words, with no dash.")
    mo = META_MORAL.search(SB.strip_quoted(text))
    if mo:                                          # the point must come from what happens, never from the narrator saying it
        bad.append(f"part {k}: the narrator states a moral ('{mo.group(0)}'). Remove it: never name or explain a lesson; show it only through what the people do and what it costs them.")
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
                + "\n- ".join(bad) + "\n\n" + _part_rules(k, n, word, uw_part, bible) + "\n" + PART_SHAPE
                + f"\nThe current JSON of part {k} was:\n" + json.dumps(parts[k - 1], ensure_ascii=False))
        try:
            part = json.loads(G.call_openai([{"role": "system", "content": system}, {"role": "user", "content": user}], 0.7))
        except ValueError:
            continue
        bad = _part_problems(part, bible["cast"], k, word, uw_part, n)
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
    if not os.environ.get("OPENAI_TEXT_MODEL"):
        os.environ["OPENAI_TEXT_MODEL"] = "gpt-4o"     # a stronger writer than the cheap default; set the repo variable OPENAI_TEXT_MODEL to choose another
    real_call = G.call_openai

    def call_with_fallback(msgs, temperature=1.0):
        try:
            return real_call(msgs, temperature)
        except SystemExit as e:                         # the account may not have this model: fall back to the cheap one instead of failing
            if os.environ.get("OPENAI_TEXT_MODEL") != "gpt-4o-mini" and re.search(r"model|404|403", str(e.code), re.I):
                log(f"The model {os.environ['OPENAI_TEXT_MODEL']} was refused ({str(e.code)[:120]}); using gpt-4o-mini instead.")
                os.environ["OPENAI_TEXT_MODEL"] = "gpt-4o-mini"
                return real_call(msgs, temperature)
            raise
    G.call_openai = call_with_fallback
    try:
        tries = max(1, int(os.environ.get("STORY_TRIES", "3")))
        for t in range(1, tries + 1):                                         # a story that misses the pass mark is dropped; nothing weak is queued
            try:
                return _write_story(G, idea, series, parts, log)
            except StoryRejected as e:
                log(f"Story {t} of {tries} dropped, not good enough to post: {e}")
        raise SystemExit(f"No story passed the quality bar in {tries} tries, so nothing was queued. Run again (or lower STORY_MIN_SCORE).")
    finally:
        G.call_openai = real_call


def _write_story(G, idea, series, parts, log):
    number = G.next_number()
    titles, counts = G.existing()
    lead, lead_gender, last_roles = choose_lead()
    if idea:                                  # a story idea from ideas.txt decides its own people
        lead = None
    series = series if series in SERIES else "Funny People"
    log(f"Lead for this story: {(lead_gender + ' ' + lead) if lead else 'chosen by the idea'} (the last stories led by: {', '.join(last_roles) or 'nobody yet'}).")
    n_parts = parts or choose_parts(log)
    cause = random.choice(["forgot", "believed", "no_options"])
    lessons, words = G.used_lessons(), G.used_words()
    system = system_prompt(6, 8, n_parts)
    if not idea:                                                              # ---- 0. pitch several premises, keep only the strongest
        hint = (f"Series: {series} ({SERIES[series]}). " + (f"The protagonist is a {lead_gender} {lead}. " if lead else "")
                + (f"Titles already used (be different): {'; '.join(titles[-15:])}. " if titles else ""))
        idea = pick_premise(G, n_parts, hint, log)
    brief = (f"Write the next story for the series \"{series}\" ({SERIES[series]}), told in exactly {n_parts} parts. "
             + (f"Story idea to use: {idea}. " if idea else "Invent a fresh, specific premise. ")
             + (f"THE PROTAGONIST (the first entry of 'cast') MUST BE A {lead_gender.upper()} {lead.upper()} (\"role\": \"{lead}\", \"gender\": \"{lead_gender}\"; {PERSONA.get(lead, 'a distinct character')}). " if lead else "")
             + (f"The last stories were led by: {', '.join(last_roles)}: give the rest of the cast different roles where you can, so this story does not feel like a repeat. " if last_roles else "")
             + f"Use cause \"{cause}\" for the protagonist's key choice. "
             + (f"Do NOT reuse these lessons: {'; '.join(lessons[-12:])}. " if lessons else "")
             + (f"Do NOT reuse these uncommon words: {', '.join(words)}. " if words else "")
             + (f"Titles already used (be different): {'; '.join(titles[-15:])}. " if titles else "")
             + G.performance_notes() + "\n\n" + BIBLE_STEP % (n_parts, n_parts))
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": brief}]

    bible, last_bad = None, []
    for attempt in range(1, 5):                                                   # ---- 1. the plan
        raw = G.call_openai(msgs, temperature=1.0 if attempt == 1 else 0.7)
        try:
            cand = json.loads(raw)
        except ValueError:
            last_bad = ["the reply was not valid JSON"]
        else:
            last_bad = _bible_problems(cand, n_parts, words, lead)
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
        req = {"role": "user", "content": f"STEP {k + 1}: write ONLY part {k} of {n_parts} now. {_part_rules(k, n_parts, word, uw_part, bible)}\n{PART_SHAPE}"}
        tmsgs, part, last_bad = msgs + [req], None, []
        for attempt in range(1, 5):
            raw = G.call_openai(tmsgs, temperature=0.9 if attempt == 1 else 0.7)
            try:
                cand = json.loads(raw)
            except ValueError:
                last_bad = [f"part {k}: the reply was not valid JSON"]
            else:
                last_bad = _part_problems(cand, bible["cast"], k, word, uw_part, n_parts)
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
        if not bad and os.environ.get("STORY_CRITIC", "1") != "0":
            bad, avg = critique_scored(G, sb)
            log(f"Editor round {rnd}: average {avg:.1f}" if avg is not None else f"Editor round {rnd}: no score")
            if bad and rnd == 3:
                raise StoryRejected("; ".join(bad)[:400])
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
